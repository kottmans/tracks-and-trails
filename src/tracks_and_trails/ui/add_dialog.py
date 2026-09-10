"""The add-URL dialog: paste URLs, watch them resolve, queue the ones that did (`T-118`).

`UX-003`: **nothing enters the queue unprobed.** Pasting starts the work — there is no second
control to press and no route to queueing a URL nobody has looked at. Each entered line becomes a
row that resolves in place into a title, an uploader, a duration and a thumbnail, and *Add to
queue* commits what resolved.

This replaces a dialog whose Probe button covered the **first URL only**. Everything else a user
pasted went into the queue never having been looked at, which is where a title-less row came from.
Nothing decided that; it fell out of Phase 1 running a pool of exactly one, where probing a batch
would have been a queue of probes with no scheduler to run it. `T-116` gave probing its own lane,
which is what makes this affordable.

## Nothing here waits — not on a worker, and not on the database

**Probing is a worker process, not a "quick" inline call** (`ARCHITECTURE.md` §8, `NFR-001`).
Probe latency is unbounded — a network round trip through an extractor that may itself fetch
several pages — so resolving starts sessions and returns. Results arrive on `DownloadManager`'s
signals, on the GUI thread, one event-loop turn later.

**Persistence is asynchronous too** (`ARC-005`). `T016-R3` measured 0.302 s of frozen GUI from
calling `JobRepository` straight from a button slot, under a contended writer lock, ending in an
`OperationalError` no user ever saw. Jobs go to a `JobSink` that answers on a callback.

**Nothing is persisted before it is probed** (`T118-R1`, `UX-003`). Reading a line is a *staging*
probe: the manager holds a transient job for it and never writes a row, so a line that fails or
that the user takes away has nothing on disk to withdraw. `done()` unstages rather than cancelling,
and closes immediately.

*(This paragraph read the opposite — "a row is persisted before it is probed … `done()` withdraws
every such row and refuses to close until those cancellations are durable" — for as long as that
was true. `T118-R1` was **Critical** precisely because it was: `compose()` admits every durable
`QUEUED` or `READY` row at startup, so a crash after a probe succeeded downloaded a URL the user
had never committed to. `T118-R11` found this sentence still here afterwards, pointing maintenance
at the design that defect was.)*

## Resolution is debounced, not fired per keystroke

"Pasting starts the work" is unambiguous for a paste and impossible for typing: a probe per
keystroke would spawn an interpreter per character. The text box restarts a short timer instead,
and resolution happens once it settles. `resolve()` is public so a test drives it directly rather
than waiting on wall-clock time.

## A row belongs to a line, not to a job id

`T016-R1` was Critical and its lesson is unchanged. Every row records the text of the line it was
started for and the generation of the box at that moment; a row whose line is gone is superseded
rather than deleted, so a result already queued as a signal is refused **by name** rather than by
having nothing to match. `ui/staging.py` holds that state machine, Qt-free and tested directly.

## What the user is shown

Every field `REQ-002` names, per row, and on failure the extractor's own message character for
character (`REQ-005`, `NFR-006`). Every state is named in words as well as drawn — `NFR-005`
forbids colour carrying it alone — and every label showing text this application did not author is
`PlainText` (`T016-R6`): a title of `<b>VISIBLE</b>` is a title, not markup.

**Every row is filled from the moment it appears.** A thumbnail exists only after a probe, so a
fresh paste would otherwise be a column of empty wells, which reads as a broken application rather
than as work in progress. Until real bytes arrive a row carries a tile derived from its URL
(`staging.placeholder_hue`) — decoration, never the only thing telling two rows apart.

## The list is a model and a delegate, not widgets

**`T118-R7`, `T118-R9` and `T118-R10` were one defect wearing three faces**, and this is the shape
that answers all three. The list used to be a `QListWidget` carrying a `QWidget` on every row: the
widget collided with the item delegate and clipped a 54 px thumbnail into a 25 px row, its combo
box sat outside the declared focus order and landed after *Close*, and building 150 of them cost
0.722 s on hosted Windows against `NFR-001`'s budget.

`StagingModel` answers `ui/row_delegate.py`'s roles and `RowDelegate` draws them, so there is one
row anatomy for this dialog and the queue both (`T-119`). The per-row format control is an
**editor** the delegate opens for the row being edited — one control at a time, reached with
`EDIT_KEY`, and never in the tab order because it does not exist until it is asked for.
"""

import uuid
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import Any, Final, Protocol, cast

from PySide6.QtCore import (
    QAbstractItemModel,
    QAbstractListModel,
    QEvent,
    QModelIndex,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtCore import QPersistentModelIndex as _PersistentIndex
from PySide6.QtGui import (
    QAction,
    QFontMetrics,
    QKeyEvent,
    QPalette,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core import presets as preset_registry
from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import (
    AudioCodec,
    DownloadRequest,
    Job,
    MediaInfo,
    NetworkOptions,
    Preset,
)
from tracks_and_trails.core.output_template import OutputPreview
from tracks_and_trails.core.paths import sanitize_component
from tracks_and_trails.core.presets import format_choice_of
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.downloader.protocol import SessionKind
from tracks_and_trails.ui.format_selection import (
    FormatSelection,
    merge_refusal,
)
from tracks_and_trails.ui.format_table import FormatTable
from tracks_and_trails.ui.format_text import FORMAT_PREFIX, format_name
from tracks_and_trails.ui.options_dialog import OptionsDialog, PresetSink
from tracks_and_trails.ui.playlist_picker import PlaylistPicker
from tracks_and_trails.ui.playlist_selection import PlaylistSelection, describe_chosen
from tracks_and_trails.ui.row_delegate import (
    CHOOSE_FORMATS_DATA,
    CHOOSE_FORMATS_TEXT,
    DETAIL_ROLE,
    EDIT_HINT,
    EXPANDED_ROLE,
    FORMAT_PANEL_HEIGHT_ROLE,
    FORMATS_AVAILABLE_ROLE,
    HEADLINE_ROLE,
    HUE_ROLE,
    INHERITED_SUFFIX,
    JOB_ID_ROLE,
    MANAGE_PRESETS_DATA,
    MANAGE_PRESETS_TEXT,
    MEDIA_KIND_ROLE,
    MENU_AVAILABLE_ROLE,
    OPTIONS_AVAILABLE_ROLE,
    OPTIONS_DATA,
    OPTIONS_TEXT,
    PRESET_CHOICES_ROLE,
    PRESET_INHERITABLE_ROLE,
    PRESET_INHERITED_ROLE,
    PRESET_ROLE,
    PRESETS_MANAGEABLE_ROLE,
    ROW_PRESET_NAME,
    SELECTOR_ROLE,
    STATE_ROLE,
    TEMPLATE_AVAILABLE_ROLE,
    TEMPLATE_DATA,
    TEMPLATE_TEXT,
    THUMBNAIL_URL_ROLE,
    RowDelegate,
    minimum_row_width,
)
from tracks_and_trails.ui.staging import (
    DUPLICATE_TEXT,
    Row,
    RowState,
    Staging,
    placeholder_hue,
    summarise,
)
from tracks_and_trails.ui.template_editor import TemplateEditor
from tracks_and_trails.ui.thumbnails import (
    THUMBNAIL_SIZE,
    NetworkThumbnailLoader,
    ThumbnailLoader,
    ThumbnailStore,
)

#: Re-exported so the loader seam keeps its name at this dialog's boundary even though the
#: implementation moved to `ui/thumbnails.py` with the cache it feeds.
__all__ = [
    "INHERITED_SUFFIX",
    "ROW_PRESET_NAME",
    "THUMBNAIL_SIZE",
    "AddUrlDialog",
    "NetworkThumbnailLoader",
    "StagingModel",
    "ThumbnailLoader",
]

#: The invalid index, meaning "the root" in Qt's model API. A value rather than state, so one
#: instance serves every default argument — the same reasoning as `queue_view._ROOT`.
_ROOT: Final = QModelIndex()

#: The flag that lets a row open its editor. Named once because it is read in two places that must
#: agree — `flags`, which Qt asks, and the accessible text, which tells a screen-reader user the
#: control is there (`NFR-005`).
_EDITABLE: Final = Qt.ItemFlag.ItemIsEditable

#: How long the input box must be quiet before resolving. Long enough that typing a URL by hand is
#: one resolve rather than forty, short enough that a paste feels immediate.
DEFAULT_RESOLVE_DELAY_MS: Final = 400

#: What an unfilled `REQ-002` field reads as. `MediaInfo` models these as genuinely optional —
#: yt-dlp omits an uploader for some sites and a duration for a live stream — so this is the
#: honest rendering of a missing value rather than an invented one.
UNKNOWN_TEXT: Final = "Unknown"

#: How many lines of URL the paste box asks for before it stops growing (`T-210`).
#:
#: **Four, chosen against the work rather than picked.** A single URL is the common paste and a
#: handful is the rest; beyond that the box scrolls, which is what a text box does. It was
#: previously unbounded, and Qt gave one line of URL about as much of the dialog as sixteen staged
#: rows — which is what put an opened playlist's *Done* button below the fold.
URL_BOX_LINES: Final = 4

#: Breathing room left below an opened row, so its last control is not flush against the fold.
#:
#: A panel sized to the viewport exactly would put *Done* on the final pixel of the visible area,
#: where it reads as clipped even when it is not.
PANEL_VIEWPORT_MARGIN: Final = 8

#: Breathing room around the empty-list hint, so it is not flush against the frame.
EMPTY_HINT_MARGIN: Final = 24

#: What each row state says, in words (`NFR-005`). Derived from the state rather than written
#: beside it, so a state cannot acquire a colour and no sentence.
#: How a duplicate is joined to the row's state (`P-26`, `T-114`). One separator, named once,
#: because the drawn state and the accessible text both compose it.
DUPLICATE_SEPARATOR: Final = " · "

STATE_TEXT: Final[dict[RowState, str]] = {
    RowState.PENDING: "Waiting",
    RowState.SAVING: "Saving",
    RowState.WAITING: "Waiting to be read",
    RowState.PROBING: "Reading",
    RowState.READY: "Read",
    RowState.FAILED: "Couldn't read",
    RowState.SUPERSEDED: "Removed",
}

#: Every label that renders text this application did not author: extractor messages and site
#: metadata. All are forced to `PlainText` (`T016-R6`).
UNTRUSTED_TEXT_LABELS: Final = ("statusMessage", "selectorValue")


class JobSink(Protocol):
    """Where new jobs are written. Asynchronous, because `ARC-005` forbids blocking here."""

    def submit(self, jobs: Sequence[Job], done: Callable[[str | None], None]) -> None: ...


class QueuedUrls(Protocol):
    """What the queue currently holds, for `REQ-022`'s duplicate check (`T-114`).

    **A callable over an in-memory list, and never a query** (`T079-R2`). The check runs on every
    refresh — which is every keystroke, through the debounce — so a database read here would put
    one on the GUI thread's path for each of them, which is the shape `T016-R3` measured at 0.302 s
    of frozen window. `QueueModel` already holds every visible row, so the answer is a list
    comprehension over memory the application has anyway.

    A protocol rather than a `QueueModel` parameter, so this dialog does not learn what a queue view
    is and a test can hand it a tuple.
    """

    def __call__(self) -> Sequence[str]: ...


def split_urls(text: str) -> list[str]:
    """One URL per line, blank lines discarded, order preserved (`REQ-001`).

    **Duplicates are kept.** Two identical lines are two things the user asked for, and deciding
    otherwise here would silently halve a paste.
    """
    return [line.strip() for line in text.splitlines() if line.strip()]


def format_duration(seconds: float | None) -> str:
    """`H:MM:SS`, or `M:SS` under an hour. `None` is unknown rather than zero."""
    if seconds is None:
        return UNKNOWN_TEXT
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def state_text(row: Row) -> str:
    """What the row's state reads, including whether it repeats something (`P-26`, `REQ-022`).

    **In the state, and `UX-007` ruled that it is not a modal.** A modal per duplicate in a paste
    of thirty is unusable, and the row is where every other fact about a staged line already is.

    **A statement, not a warning.** `REQ-022` as rescoped says a duplicate is *confirmed rather
    than refused*: wanting the same URL twice — at two formats, or after a failure — is an ordinary
    thing to want, so the row says what is true and *Add to queue* remains the one action (`P-27`).

    Composed here rather than in the delegate so the drawn state, `row_text` and the accessible
    text are one sentence — `T118-R8`'s rule, which this project has had to relearn twice.
    """
    said = STATE_TEXT[row.state]
    kind = row.duplicate
    if kind is None:
        return said
    return f"{said}{DUPLICATE_SEPARATOR}{DUPLICATE_TEXT[kind]}"


def describe_kind(media: MediaInfo) -> str:
    """Whether this URL is one item or a playlist, and how big (`REQ-002`)."""
    if not media.is_playlist:
        return "Single item"
    if media.entry_count is None:
        return "Playlist"
    return f"Playlist ({media.entry_count} items)"


def describe_preset(row: Row, effective: Preset) -> str:
    """What `row` will be downloaded as — **literally** — and whether that is its own choice.

    `effective` is the very `Preset` the caller passes to `to_request` (`T118-R8`), so the words
    here and the request cannot describe different downloads. Taking the row's raw preset and
    re-deriving from it is what let a display and a request disagree twice.

    **The selector is spelled out, not just the preset's name** (`REQ-009`, `T118-R8`). A name is
    not the promise `T-118` makes: *"the effective selector shown stays the one that will run"*.
    Showing only `Audio only (MP3)` left the sole literal selector on screen describing the batch,
    so an audio override under a video batch displayed the video selector.

    **Inherited is spelled out too**, not left blank — a blank reads as "no format chosen" rather
    than "the one below" (`T118-R4`).

    **One line**, since `T-119`'s delegate draws a row of three: the name, whose choice it is, and
    the literal selector, separated rather than stacked.

    **The name comes from `format_text`, not from `effective.name`** (`T-156`). This used to append
    the bitrate itself, through a `describe_quality` helper that lived here — so the dialog held one
    opinion about how to name a download and the queue and History held another, which is the split
    `T-159` wrote that module to end. It now carries the bitrate because `format_name` does, and the
    surfaces that name a download say the same words about the same request by construction rather
    than by anyone keeping them in step. *(This said "the three surfaces"; History was one of them
    and went with `T-169`/`T-170`. The count is not restated, because a number in prose goes stale
    and the property does not — `T-186`.)*
    """
    source = "this row only" if isinstance(row.preset, Preset) else "following the batch"
    selector = preset_registry.effective_selector(effective)
    return f"{format_name(format_choice_of(effective))} — {source} · Format selector: {selector}"


def remove_label(row: Row) -> str:
    """What removing this row takes with it (`UX-012`, `T-223`).

    **A playlist row names the batch, because removing the line removes all of it.** *"Remove this
    URL"* on a row standing for sixteen downloads understates what the click does, and a label owes
    the user its blast radius.

    **A single item stays "this URL" rather than becoming "this video".** A row can be audio-only,
    so *video* would be a lie on exactly the rows `UX-005` spends its effort keeping honest.

    **Playlist-ness is `is_playlist`, not "did we enumerate anything"** (`T223-R1`). The first
    version read `entries`, which collapses the state the model keeps deliberately apart: an
    **unenumerated** playlist has `entries == ()` and a real `entry_count`, and it is a supported
    shape — `MediaInfo(is_playlist=True, entry_count=9, entries=())` stays one job by design. That
    version called it a URL and understated exactly the blast radius this label exists to name.

    **The count is the site's when the site gives one.** `entry_count` is what the extractor
    reported; `entries` is what this extraction materialised. Removing the row removes the whole
    batch, so the site's number is the honest one, and the materialised length is the fallback for
    a playlist enumerated without a reported count.

    **A playlist with no count keeps its noun and loses its number.** `entry_count is None` means
    *unknown*, not zero — the model says so in terms — so *"(0 items)"* would be the confident lie
    `Job.progress` already refuses to tell. It reads `Remove this playlist`, which is still the
    truth that matters: the click takes more than one thing.
    """
    media = row.media
    if not isinstance(media, MediaInfo) or not media.is_playlist:
        return "Remove this URL"

    count = media.entry_count if media.entry_count is not None else len(media.entries) or None
    if count is None:
        return "Remove this playlist"
    return f"Remove this playlist ({count} item{'' if count == 1 else 's'})"


def headline_text(row: Row) -> str:
    """The row's first line: the extractor's title once there is one, else the pasted URL.

    Never empty. A row nobody can identify is worse than a long URL.
    """
    media = row.media
    return media.title if isinstance(media, MediaInfo) else row.url


def entry_selection_of(row: Row) -> PlaylistSelection | None:
    """`row`'s playlist selection, or `None` when it has no entries to choose between.

    **Reconciled against the entries the row currently holds**, because a retry re-probes and a
    playlist can come back a different length. A stale selection applied to a shorter tuple would
    enqueue a different set of items than the one on screen, which `PlaylistSelection.chosen`
    refuses outright — this is where the refusal is avoided honestly rather than caught.
    """
    media = row.media
    if not isinstance(media, MediaInfo) or not media.entries:
        return None
    chosen = row.entry_selection
    if isinstance(chosen, PlaylistSelection):
        return chosen.with_count(len(media.entries))
    return PlaylistSelection.all_of(len(media.entries))


def detail_text(row: Row) -> str:
    """The row's second line, without its state — the fields `REQ-002` names.

    **A failed row shows the extractor's words unchanged** (`NFR-006`). They are not folded into a
    sentence, because a sentence that contains them is not the same as them.

    **A playlist says how much of itself is chosen** (`REQ-004`, `T-110`). Without it the only
    place the choice appears is inside the picker, so a user who closes the row cannot see what
    Add is about to queue — and `UX-003`'s promise is that the staging list is where the batch is
    read. The phrase comes from `describe_chosen`, which the picker's own summary also calls.
    """
    if row.state is RowState.FAILED:
        return row.message or "no reason was given"
    media = row.media
    if not isinstance(media, MediaInfo):
        return ""
    selection = entry_selection_of(row)
    parts = [
        media.uploader or UNKNOWN_TEXT,
        format_duration(media.duration_seconds),
        describe_kind(media),
    ]
    if selection is not None:
        parts.append(describe_chosen(selection))
    return " · ".join(parts)


def selector_text(row: Row, effective: Preset | None) -> str:
    """The row's third line: what it will be downloaded as, spelled out (`T118-R8`, `REQ-009`)."""
    if effective is None or not isinstance(row.media, MediaInfo):
        return ""
    return f"{FORMAT_PREFIX}{describe_preset(row, effective)}"


def selector_candidates(presets: Sequence[Preset]) -> tuple[str, ...]:
    """Every third line these presets can produce, for the width the list asks for (`T-150`).

    **Built through `describe_preset`, not beside it.** A separately written worst case would
    measure a string the row does not draw, and the first change to the wording would leave the
    dialog sized for the old one. Both halves of its *"whose choice is this"* phrase are included
    because the row's own choice and the batch's differ in length.

    A `Row` is cheap and carries nothing here but its preset, which is the only field
    `describe_preset` reads.
    """
    return tuple(
        f"{FORMAT_PREFIX}{describe_preset(Row(url='', generation=0, preset=owner), preset)}"
        for preset in presets
        for owner in (None, preset)
    )


def row_text(row: Row, effective: Preset | None = None) -> str:
    """What one row reads as, whole: headline, detail and state, and what it downloads as.

    A module function rather than a method so the wording is asserted without a `QApplication`,
    and so the failure case cannot drift from the success case.

    **Composed from the very pieces the delegate's roles carry** (`T-119`), rather than written a
    second time beside them. The drawn row and this string are then the same sentence by
    construction — which is the property the old two-writers arrangement kept losing, most
    recently as `T118-R8`.
    """
    tail = selector_text(row, effective)
    return row_summary(row) + (f"\n{tail}" if tail else "")


def row_summary(row: Row) -> str:
    """The row without what it downloads as — headline and detail only (`T-210`).

    **What an opened row says about itself.** `RowPanel` reproduces the row it covers, and using
    the whole of `row_text` put the format selector in there too:
    `bestvideo[height<=1080][ext=mp4]+bestaudio[...]` wrapped to two more lines, and the entry
    table got what was left. In a 700px window that was **one visible entry** out of sixteen.

    The selector is worth showing on the *closed* row, where it is the only place the choice is
    visible. Inside the panel it is answered by the control the user came through, and it costs
    the picker the space it exists for.

    **Still composed from the delegate's own pieces** rather than written again — `row_text` is
    now this plus the tail, so the two cannot drift (`T118-R8`).
    """
    second = " — ".join(part for part in (detail_text(row), state_text(row)) if part)
    return f"{headline_text(row)}\n{second}"


#: How many closed rows the list asks to show before an opened one has to fight for room (`T-210`).
#:
#: **Seven, tuned against the built window rather than picked.** Eight opened the dialog taller than
#: the maintainer wanted — *"slightly smaller"* — and five took too much off. The list grows
#: when a row opens anyway, so the hint only has to give an opened row somewhere to start.
#: `VISIBLE_ENTRIES` is a different number for a different question: how many entries the picker
#: shows before it scrolls.
WANTED_ROWS: Final = 7

#: Used only before the first row exists, when `sizeHintForRow` has nothing to measure.
_CLOSED_ROW_ESTIMATE: Final = 64


class StagingList(QListView):
    """The staged rows, asking for the width the row anatomy was designed for (`T-150`).

    **The dialog set no size at all** — no `resize`, no minimum, no size hint — so Qt gave it
    whatever its layout's hints added up to, which was 302 px. Measured there, the list's viewport
    was 254 px and `_control_rect` had already narrowed the format control to
    `MIN_CONTROL_WIDTH`: the dialog opened with the control at the narrowest it is *allowed* to be.
    That was not a decision anybody took; `MainWindow` declares `DEFAULT_SIZE` and this did not.

    **A hint, not a minimum, and that is the difference that matters.** A minimum would open the
    dialog wide *and stop the user narrowing it*, and narrow has to keep working — `T-135`'s
    overflow and `T-160`'s narrowing control are the behaviours that make it safe, and a floor
    would put them out of reach rather than honour them. A hint sizes the first paint and leaves
    the drag alone. It is set on the list rather than on the dialog so that Qt's layout adds the
    frame, the group box and the margins, instead of this counting them and getting it wrong.
    """

    #: `bool` — the user pressed `→` (open) or `←` (close) on the current row.
    #:
    #: `docs/UX_SPEC.md` §7's own keyboard row, and the route `T140-R5` established on the queue.
    #: A signal rather than a call into the dialog so this widget stays a view: it knows a key was
    #: pressed on a row, and what a row *opens onto* is the dialog's business.
    disclosure_requested = Signal(bool)

    def __init__(self, parent: QWidget | None, *, selectors: Sequence[str]) -> None:
        super().__init__(parent)
        # **By pixels, not items** (`T-210`). `QListView` scrolls per *item* by default and a wheel
        # notch is three of them — reasonable when rows are a line high, and a catapult here, where
        # one "item" can be a whole opened playlist: the moment the wheel reached this list it
        # jumped past the panel to the end. The maintainer's words: *"the screen still jumps
        # instead of gradually scrolling for the outside scroll bar."* Per-pixel makes a notch a
        # notch, whatever is open. *(A first correction consumed the wheel at the inner table's
        # edge instead — fixing the handoff rather than the jump. The handoff was fine.)*
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        #: What the third line may have to hold, from the catalogue the dialog was given.
        self._selectors = tuple(selectors)
        #: Cached because `sizeHint` is called on every layout pass and the answer searches for a
        #: wrap width. Dropped on a font or style change, which is exactly when it stops being
        #: true — `T118-R15` is this project's record of a width promise that held at one font.
        self._wanted: int | None = None

        # Qt's override names, hence the camelCase.
        # **A label over the viewport, not a `paintEvent`** (`T-218`). The first build painted the
        # hint in `paintEvent`; `viewport().grab()` never routed to it, so the text was invisible
        # to every test that could have proved it — the mutation deleting the painting changed
        # nothing. A child of the viewport can be asserted directly: shown, hidden, and read.
        #
        # It holds no slot in the focus chain (`T-060`): a `QLabel` takes `NoFocus` by default, and
        # it is transparent to the mouse so a click still reaches the list underneath.
        self._empty_hint = QLabel(self.EMPTY_HINT, self.viewport())
        self._empty_hint.setObjectName("stagingEmptyHint")
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_hint.setWordWrap(True)
        self._empty_hint.setMargin(EMPTY_HINT_MARGIN)
        self._empty_hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._empty_hint.setForegroundRole(QPalette.ColorRole.PlaceholderText)

    def updateGeometries(self) -> None:
        """Keep the wheel gradual whatever is open (`T-210`).

        Per-pixel mode alone was not enough, and the regression measured why: on every geometry
        update `QListView` resets the vertical scrollbar's `singleStep` **to the first item's
        height** — so with an opened playlist first in the list, one wheel notch (three steps) was
        three panels, and the list still flew to its end (166px of 166). The step is re-pinned to a
        text line here, after Qt's reset, which is the only place that survives it.
        """
        super().updateGeometries()
        self.verticalScrollBar().setSingleStep(max(self.fontMetrics().height(), 12))

    def sizeHint(self) -> QSize:
        """The width the row anatomy needs, and the height an opened one does (`T-150`, `T-210`).

        **Height was left to Qt and it split the dialog evenly**, so the list opened too short to
        hold an expanded playlist and the maintainer had to drag the window taller every time. The
        hint asks for `WANTED_ROWS` closed rows — enough that opening one has somewhere to go.

        A hint, not a minimum, for the reason the class docstring gives about width: short has to
        keep working, and a floor would put that out of reach rather than honour it.
        """
        hint = super().sizeHint()
        row = self.sizeHintForRow(0) if self.model().rowCount() else 0
        wanted = (row or _CLOSED_ROW_ESTIMATE) * WANTED_ROWS + 2 * self.frameWidth()
        return QSize(max(hint.width(), self._row_width()), max(hint.height(), wanted))

    def changeEvent(self, event: QEvent) -> None:
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._wanted = None
            self.updateGeometry()
        super().changeEvent(event)

    #: Emitted when the viewport's height changes, so whoever sizes rows against it can re-measure.
    #:
    #: **A row's height depends on the viewport now** (`T-210`): an opened row is bounded by what
    #: the list can show, so a resize changes the answer. Qt does not re-ask a delegate for
    #: `sizeHint` when the viewport changes, so without this the row kept a height measured against
    #: the *old* viewport while the panel inside it was laid out to the new one — the two
    #: disagreed, and an expanded row showed nothing at all.
    viewport_resized = Signal()

    #: What the empty list says, in the space it is explaining (`T-218`).
    #:
    #: **The instruction moved here rather than being written a third time.** The dialog said the
    #: same thing twice — the paste box's placeholder and a label under the list — while the list
    #: itself, the largest thing on the screen, said nothing at all. This teaches what the list is
    #: *for*, which the placeholder cannot: that a pasted line is read and shown here, with its
    #: title and thumbnail, before anything is queued (`UX-003`).
    #:
    #: **Mounted as a child of the viewport, not painted** (`T-231`). Painting it was the first
    #: build and it was rejected: `viewport().grab()` never routes to a `QListView.paintEvent`, so
    #: the text was invisible to every assertion that could have proved it — 1209 distinct colours
    #: with and without the painting, and the mutation deleting it changed nothing. A child can be
    #: asserted directly.
    #:
    #: **It costs nothing in the focus chain**, which is what painting was reached for: a `QLabel`
    #: takes `NoFocus`, and `WA_TransparentForMouseEvents` keeps clicks going through to the list.
    #: `T-060` declares that chain and `T016-R4` keeps it stable; both are asserted.
    EMPTY_HINT: Final = (
        "Paste URLs above.\n\n"
        "Each line is read here — title, channel and thumbnail —\nbefore anything is queued."
    )

    # Qt's override name, hence the camelCase.
    def setModel(self, model: QAbstractItemModel | None) -> None:
        """Take the model, and follow it so the hint knows when to leave."""
        super().setModel(model)
        if model is not None:
            for signal in (model.rowsInserted, model.rowsRemoved, model.modelReset):
                signal.connect(self._show_hint_when_empty)
        self._show_hint_when_empty()

    def _show_hint_when_empty(self, *_: object) -> None:
        """Visible exactly while there is nothing to read instead."""
        model: QAbstractItemModel | None = self.model()
        self._empty_hint.setVisible(model is None or model.rowCount() == 0)
        self._empty_hint.setGeometry(self.viewport().rect())

    # Qt's override name, hence the camelCase.
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._empty_hint.setGeometry(self.viewport().rect())
        if event.oldSize().height() != event.size().height():
            self.viewport_resized.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """`→` opens the current row, `←` closes it (`docs/UX_SPEC.md` §7).

        Taken here rather than left to Qt: a single-column `QListView` does nothing with either
        key, so nothing is being overridden — and a route the spec declares has to exist without a
        pointer having been used first (`T-152`).
        """
        key = event.key()
        if key in (int(Qt.Key.Key_Right), int(Qt.Key.Key_Left)):
            self.disclosure_requested.emit(key == int(Qt.Key.Key_Right))
            return
        super().keyPressEvent(event)

    def _row_width(self) -> int:
        """What a row needs, plus the chrome between this widget's edge and its viewport."""
        if self._wanted is None:
            bar = self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent, None, self)
            # The scrollbar is counted even though an empty list has none: a paste is what this
            # dialog is *for*, and a row must keep its anatomy once the list is long enough to
            # scroll rather than lose it at the moment the bar appears.
            self._wanted = (
                minimum_row_width(QFontMetrics(self.font()), self._selectors)
                + 2 * self.frameWidth()
                + bar
            )
        return self._wanted


class RowPanel(QWidget):
    """A staging row, opened. The shape both `P-1` and `P-19` are (`UX-007`).

    **The row expanded, not a modal over a modal.** `UX-007` ruled against `docs/UX_SPEC.md`'s own
    proposal of a dialog: the add dialog is already modal, and the staging list is already a list
    of rows that open. `P-1` gives the format table that shape and `P-19` gives the playlist picker
    the same one, and the ruling says why in as many words — *"the two surfaces are **one
    mechanism** rather than two"*.

    So the mechanism is here, once, and a subclass supplies only the body it opens onto. Writing
    the second panel beside the first would have made the ruling a coincidence that the next change
    breaks.

    **The summary line is `row_text`, the very function the delegate's roles compose.** Qt's
    `setIndexWidget` covers the item it is set on, so an opened row's painted anatomy is hidden and
    something has to say what row this is. Writing that sentence here would be a second author for
    it — `T118-R8`'s defect exactly — so the one that already exists is called instead. The
    thumbnail and the format control are *not* reproduced: they are what the user came through, and
    a copy of a control that edits the same row from two places is worse than its absence.

    `Esc` closes it choosing nothing, which is `docs/UX_SPEC.md` §4's own keyboard row.
    """

    #: The user is finished with this panel. `bool` — whether to keep what was chosen.
    closed = Signal(bool)

    def __init__(
        self,
        row: Row,
        summary: str,
        *,
        object_name: str,
        summary_name: str,
        done_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self._row = row
        # **Opaque, and it is still opaque for a reason** (`T-210`, kept by `T-312`). It was made
        # opaque because `setIndexWidget` put it *over* the row: a `QWidget` paints nothing by
        # default, so the delegate's own anatomy showed through wherever the panel had no child —
        # the thumbnail behind the heading, the row's *Download as* line behind the summary. **A
        # panel is a page now and nothing is painted beneath it**, so that specific defect cannot
        # recur; what remains is that a page filling the dialog should carry the window's own
        # ground rather than let whatever the stack paints show through. The three steps below are
        # what make a style sheet reach a plain `QWidget` at all, and none of them is about rows.
        # **Three things, and it takes all three** (`T-210`). This took two attempts that changed
        # nothing on screen while passing their tests, so each is spelled out:
        #
        # 1. `setAutoFillBackground` is **ignored once a stylesheet is set**, so the opacity has to
        #    come from a sheet rule. It is kept for the unstyled case a test window runs in.
        # 2. A plain `QWidget` subclass **does not paint a stylesheet background at all** unless
        #    `WA_StyledBackground` is set. Without it the sheet's rule matches and draws nothing,
        #    which is why the delegate's row kept showing through a panel that "had" a background.
        # 3. A property set **after** the sheet was applied needs a repolish, or the rule never
        #    matches. That is `T-192`'s lesson, applied one widget over.
        self.setAutoFillBackground(True)
        self.setBackgroundRole(QPalette.ColorRole.Base)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("rowPanel", True)
        self.style().unpolish(self)
        self.style().polish(self)

        layout = QVBoxLayout(self)

        # **The way out sits at the top** (`T-210`; the reason narrowed by `T-312`). It was put
        # there because `setIndexWidget` covered the row's own disclosure and a control at the
        # *bottom* was the first thing to fall below the fold on a tall panel. A page cannot push
        # its own controls off — its layout compresses the body instead — so that hazard is gone;
        # the triangle stays because it is the affordance a user has learned for *go back*, and it
        # is where they will look for it. `Done` is still there for the keyboard order and for the
        # reader who works downward.
        heading = QHBoxLayout()
        self._collapse = QToolButton(self)
        self._collapse.setObjectName("formatPanelCollapse")
        self._collapse.setAccessibleName(f"Collapse {summary_name.lower()}")
        self._collapse.setArrowType(Qt.ArrowType.DownArrow)
        self._collapse.setAutoRaise(True)
        # Styled by role, not by name, so the next panel with a disclosure inherits the look
        # instead of remembering it — the convention `T-192` established and
        # `test_the_sheet_styles_by_class_so_a_new_widget_inherits_it` enforces.
        self._collapse.setProperty("disclosure", True)
        self._collapse.clicked.connect(lambda: self.closed.emit(True))
        heading.addWidget(self._collapse, 0, Qt.AlignmentFlag.AlignTop)

        self._summary = QLabel(summary, self)
        self._summary.setObjectName("formatPanelSummary")
        self._summary.setAccessibleName(summary_name)
        self._summary.setWordWrap(True)
        # Site metadata, so it is never interpreted as markup (`T016-R6`'s rule; this label is
        # created here rather than in `_build`, so it sets its own format).
        self._summary.setTextFormat(Qt.TextFormat.PlainText)
        heading.addWidget(self._summary, 1)
        layout.addLayout(heading)

        self._body = self._build_body(row)
        layout.addWidget(self._body)

        self._close = QPushButton("&Done", self)
        self._close.setObjectName("formatPanelDone")
        self._close.setAccessibleName(done_name)
        self._close.clicked.connect(lambda: self.closed.emit(True))
        layout.addWidget(self._close)

    def _build_body(self, row: Row) -> QWidget:
        """What this panel opens onto. The one thing a subclass supplies."""
        raise NotImplementedError

    @property
    def row(self) -> Row:
        return self._row

    @property
    def done_button(self) -> QPushButton:
        return self._close

    @property
    def collapse_button(self) -> QToolButton:
        """The always-visible way out, at the top of the panel (`T-210`)."""
        return self._collapse

    def focus_chain(self) -> list[QWidget]:
        """The keyboard order through the panel, stated rather than left to construction order."""
        raise NotImplementedError

    def initial_focus(self) -> QWidget:
        """Where focus lands when the panel opens.

        **Not simply the first tab stop.** Both panels put a *mode* or a *group* control ahead of
        the list in the tab order — `docs/UX_SPEC.md` §5's rule that a mode which changes what
        `Enter` does is reachable before the thing it changes — and both open onto the list itself,
        because that is what the user came to look at. The two orders are different questions and
        answering them with one list is how a panel opens focused on a checkbox.
        """
        return self.focus_chain()[0]

    # Qt's override name, hence the camelCase.
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """`Esc` closes, choosing nothing (`docs/UX_SPEC.md` §4).

        Handled here rather than on the dialog: `QDialog` treats `Esc` as *reject*, so leaving it
        to fall through would close the whole add dialog and discard the batch. Taking it at the
        panel is what makes the spec's row mean what it says.
        """
        if event.key() == int(Qt.Key.Key_Escape):
            self.closed.emit(False)
            return
        super().keyPressEvent(event)


class FormatPanel(RowPanel):
    """A staging row opened onto its formats (`UX-007`'s `P-1`, `REQ-003`, `REQ-008`)."""

    def __init__(
        self,
        row: Row,
        summary: str,
        *,
        ffmpeg_available: bool,
        parent: QWidget | None = None,
    ) -> None:
        self._ffmpeg_available = ffmpeg_available
        super().__init__(
            row,
            summary,
            object_name="formatPanel",
            summary_name="The URL these formats belong to",
            done_name="Use the chosen formats and close",
            parent=parent,
        )

    def _build_body(self, row: Row) -> QWidget:
        media = row.media
        formats = media.formats if isinstance(media, MediaInfo) else ()
        self._table = FormatTable(formats, self, ffmpeg_available=self._ffmpeg_available)
        return self._table

    @property
    def table(self) -> FormatTable:
        return self._table

    def focus_chain(self) -> list[QWidget]:
        """Both lists, each body-then-header-then-button, then the way out (`T-310`).

        The mode control this used to lead with is gone; `docs/UX_SPEC.md` §5's reason for putting
        it first — *"a mode that changes what `Enter` does must be reachable before the thing it
        changes"* — went with it, because nothing changes what `Enter` does any more.
        """
        return [*self._table.focus_chain(), self._close]

    def initial_focus(self) -> QWidget:
        """The table body, which is what `docs/UX_SPEC.md` §4's *current row* is about."""
        return self._table.table


class PlaylistPanel(RowPanel):
    """A staging row opened onto its playlist's entries (`UX-007`'s `P-19`, `REQ-004`, `T-110`).

    The body is `ui/playlist_picker.PlaylistPicker`, which owns the checkboxes, the tri-state group
    header and the keyboard `docs/UX_SPEC.md` §7 declares. Everything about *being a row that
    opens* is `RowPanel`'s, which is what makes this and `FormatPanel` one mechanism.
    """

    def __init__(
        self,
        row: Row,
        summary: str,
        *,
        selection: PlaylistSelection | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self._initial = selection
        super().__init__(
            row,
            summary,
            object_name="playlistPanel",
            summary_name="The playlist these entries belong to",
            done_name="Use the chosen entries and close",
            parent=parent,
        )

    def _build_body(self, row: Row) -> QWidget:
        media = row.media
        entries = media.entries if isinstance(media, MediaInfo) else ()
        self._picker = PlaylistPicker(entries, self._initial, self)
        return self._picker

    @property
    def picker(self) -> PlaylistPicker:
        return self._picker

    def focus_chain(self) -> list[QWidget]:
        return [*self._picker.focus_chain(), self._close]

    def initial_focus(self) -> QWidget:
        """The entry table: `Space` toggles the current entry, so there has to be one to toggle."""
        return self._picker.table


class TemplatePanel(RowPanel):
    """A staging row opened onto its output template (`REQ-011`, `docs/UX_SPEC.md` §9.1, `T-112`).

    **The third panel, and it needed no new mechanism.** `P-19` made the row-that-opens one class
    when the playlist picker arrived; this is what that buys — the editor supplies a body and a
    focus order and nothing else, and `Esc`, the mount, the reset survival and the height all come
    from `RowPanel`.

    A row rather than a dialog for the same reason as the other two: the add dialog is already
    modal, and a modal over a modal to type one line into is a window the user has to dismiss
    before they can look at the row it is about.
    """

    def __init__(
        self,
        row: Row,
        summary: str,
        *,
        template: str,
        parent: QWidget | None = None,
    ) -> None:
        self._initial_template = template
        super().__init__(
            row,
            summary,
            object_name="templatePanel",
            summary_name="The URL this name is for",
            done_name="Use this template and close",
            parent=parent,
        )

    def _build_body(self, row: Row) -> QWidget:
        self._editor = TemplateEditor(self._initial_template, self)
        return self._editor

    @property
    def editor(self) -> TemplateEditor:
        return self._editor

    def focus_chain(self) -> list[QWidget]:
        return [*self._editor.focus_chain(), self._close]

    def initial_focus(self) -> QWidget:
        """The input, which is the only thing here a user came to change."""
        return self._editor.input_field


class StagingModel(QAbstractListModel):
    """The staging rows, answered through `row_delegate`'s roles (`T118-R7`, `T-119`).

    **It holds no rows of its own.** `Staging` is the state machine and stays the single owner;
    this reads it. A model with its own copy would be a second place for "what is entered" to be
    decided, which is the shape `T016-R1` was.

    The dialog is the source of the two things a row cannot answer alone — the effective preset,
    which depends on the batch's controls, and whether a commit is in flight — so it is held
    rather than duplicated here.
    """

    def __init__(self, dialog: AddUrlDialog) -> None:
        super().__init__(dialog)
        self._dialog = dialog
        #: The rows this model has told the view about. Compared by identity to tell a value
        #: change from a structural one (`T118-R14`).
        self._shown: tuple[Row, ...] = ()

    # Qt's override names, hence the camelCase: these are not project naming choices.
    def rowCount(self, parent: QModelIndex | _PersistentIndex = _ROOT) -> int:
        return 0 if parent.isValid() else len(self._shown)

    @property
    def shown(self) -> tuple[Row, ...]:
        """The rows this model has told the view about. **The only index mapping** (`T118-R14`)."""
        return self._shown

    def row_at(self, index: int) -> Row | None:
        """The row a model index names, resolved against what the view believes."""
        return self._shown[index] if 0 <= index < len(self._shown) else None

    def data(
        self, index: QModelIndex | _PersistentIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        row = self.row_at(index.row()) if index.isValid() else None
        if row is None:
            return None
        effective = self._dialog.preset_for(row)

        if role == HEADLINE_ROLE:
            return headline_text(row)
        if role == DETAIL_ROLE:
            return detail_text(row)
        if role == STATE_ROLE:
            return state_text(row)
        if role == SELECTOR_ROLE:
            return selector_text(row, effective)
        if role == HUE_ROLE:
            return placeholder_hue(row.url)
        if role == MEDIA_KIND_ROLE:
            # The *effective* preset, which is what this row would actually be committed as — the
            # dialog's own resolution of a per-row choice against the default (`T-217`). It is
            # always a preset here; `preset_for` falls back to the default rather than answering
            # `None`, which is why this does not guard.
            return effective.media_kind
        if role == THUMBNAIL_URL_ROLE:
            media = row.media
            return media.thumbnail_url if isinstance(media, MediaInfo) else None
        if role == PRESET_ROLE:
            picked = row.format_selection
            if isinstance(picked, FormatSelection) and picked.is_complete:
                # **What this row will actually download, which is what the control must show**
                # (`T313-R1`). `T-311` stopped writing a hand-picked selector into `row.preset`, so
                # a row that had picked streams answered here **exactly as an untouched one does**
                # — and `T-313`'s guard, which compares the committed value against this role,
                # therefore read the user deliberately choosing *follow the batch* as Qt committing
                # an editor nobody touched. The promised way back was inert from the one state it
                # was promised for.
                #
                # Answering with the composed name separates them by *value*, which is the guard
                # the queue settled on (`T126-R3`) rather than a second one about how `setData` was
                # reached: an untouched commit re-states `137+140` and changes nothing, while the
                # inherited entry is now a different value and clears the pick.
                #
                # It also makes the control agree with the row, which paints
                # *"Download as: 137+140 — following the batch"* on its detail line — and revives
                # `RowDelegate.createEditor`'s branch for a row's own non-catalogue preset, which
                # `T-311` left unreachable.
                return format_name(format_choice_of(self._dialog.preset_for(row)))
            own = row.preset
            return own.name if isinstance(own, Preset) else None
        if role == MENU_AVAILABLE_ROLE:
            # **Always, on this list** (`T315-R2`). Every staging row's menu holds something —
            # `row_menu` draws the per-item section when the row offers one and the line's own
            # entries regardless — so the `⋮` here never opens nothing. Answered explicitly rather
            # than left to the role's absence, because "the model said nothing" and "the model said
            # no" would then be the same answer, and the queue relies on them differing.
            return True
        if role == PRESET_CHOICES_ROLE:
            # **A row that cannot be committed cannot usefully be retargeted either**, and a row
            # whose commit is already in flight must not change the request being written. An
            # empty answer is what makes the delegate offer no editor at all.
            if not row.committable or self._dialog.is_saving:
                return None
            return tuple(preset.name for preset in self._dialog.presets)
        if role == FORMATS_AVAILABLE_ROLE:
            # **A probe result with formats in it, and no commit in flight** (`T-108`). A row that
            # cannot be retargeted cannot usefully open a table either, and a URL whose probe found
            # no formats — a playlist, whose formats belong to its entries (`T-110`) — would open
            # an empty one. `UX-005` §5: nothing is offered that would be refused.
            media = row.media
            return (
                row.committable
                and not self._dialog.is_saving
                and isinstance(media, MediaInfo)
                and bool(media.formats)
            )
        if role == OPTIONS_AVAILABLE_ROLE:
            # **The same admission as the format table, and one condition fewer** (`T-109`).
            # `REQ-010`'s options do not need a format list — an audio-only source with one format
            # can still be converted, embedded into and subtitled — so this asks only that the row
            # is committable and nothing is being written. What it does need is a probe result,
            # because the subtitle languages the editor offers come from it (`P-17`).
            return (
                row.committable and not self._dialog.is_saving and isinstance(row.media, MediaInfo)
            )
        if role == FORMAT_PANEL_HEIGHT_ROLE:
            # **No row is grown for a panel now** (`T-312`): the panel is a page of the dialog, so
            # the list keeps its ordinary row heights whether or not one is open.
            return 0
        if role == TEMPLATE_AVAILABLE_ROLE:
            # **One condition fewer than the options editor** (`T-112`). `REQ-011`'s preview does
            # not need a probe: it renders whatever the row knows and labels what it cannot promise,
            # which is the whole of `REQ-011`'s *intended path* amendment. What it does need is a
            # row whose request has not been written yet.
            return row.committable and not self._dialog.is_saving
        if role == PRESETS_MANAGEABLE_ROLE:
            # **Not a question about this row** (`T-111`). The manager edits the catalogue every row
            # chooses from, so the only condition is that composition wired somewhere to save to —
            # a control with nowhere to write is the one `UX-005` §5 forbids drawing. Not gated on
            # `committable` or `is_saving`: a batch being written still has a preset list, and
            # editing it changes nothing about the requests already in flight.
            return self._dialog.can_manage_presets
        if role == EXPANDED_ROLE:
            # **Three-valued, and the third value is what makes it correct** (`T-140`'s rule).
            # Absent means *not a playlist*, which draws no disclosure at all; `False` means a
            # playlist that is closed. A row with no entries to choose between answers absent
            # rather than `False`, because a triangle that opens an empty picker is `UX-005` §5's
            # never-draw-what-would-be-refused.
            if entry_selection_of(row) is None:
                return None
            # **An open row always offers the way to close itself** (`T-204`). The two conditions
            # below are about whether a *closed* row should offer to open; once a panel is mounted
            # the question is different, and the honest answer is always yes.
            #
            # `RowDelegate` both paints the triangle and hit-tests the click on
            # `isinstance(..., bool)`, so answering `None` here removed the affordance **and** the
            # target under it — while `close_panel` and `remount_panel`, driven by `_expanded` and
            # by index validity, kept the panel mounted. A row that left `READY` with its picker
            # open could only be escaped by cancelling the dialog.
            #
            # **Chosen over closing the panel on the state change**, which was the other way to
            # satisfy `T-204`. The reachable case is a row whose **job left the queue** —
            # `_on_job_changed` turns a non-startable status into `FAILED` — and closing there would
            # take the picker away from a user who was still choosing, without being asked. It would
            # not necessarily *lose* the choice: `close_panel(keep=True)` writes it through, and
            # `_on_entries_chosen` has already written each toggle onto the row. **What closing
            # costs is the interaction, not the data.** Keeping the control costs neither: it
            # continues to do exactly what it says.
            #
            # *(`T204-R1` corrected an earlier version of this comment, which reasoned from a
            # `READY` row entering `PROBING`. Production only reaches `PROBING` from `WAITING`, so
            # that path does not exist.)*
            if row is self._dialog.expanded_row:
                return True
            if not row.committable:
                return None
            return False
        if role == JOB_ID_ROLE:
            # **What the delegate's disclosure signal carries** (`RowDelegate.editorEvent`). The
            # staging probe's id is the only string identifying a row that both the delegate and
            # the dialog can resolve, and the dialog resolves it through `Staging.for_job` — the
            # lookup `T016-R1` established, which finds the row that *owns* the id rather than one
            # at a remembered position (`T118-R14`).
            return row.job_id
        if role == PRESET_INHERITED_ROLE:
            # **The batch's preset, whatever this row currently is** (`UX-004`, `T-284`).
            #
            # **Not `effective.name`, and `T284-R1` is why that was Critical.** `effective` is the
            # row's *own* preset when it has one, and the entry this role labels does the opposite
            # of showing it: choosing it **clears the override** and returns the row to the batch.
            # So an Audio-overridden row under a Video batch offered *"Audio only (MP3) — following
            # the batch"* and, when chosen, built the Video request. The control told the user one
            # format and the queue got another.
            #
            # The role's meaning is fixed by the entry it labels: **what this row would follow**,
            # which is the batch's and never the row's.
            return self._dialog.selected_preset.name
        if role == PRESET_INHERITABLE_ROLE:
            # **This surface has an "all" to be the same as** (`UX-004`, `T126-R4`): the paste
            # carries one format and a row may defer to it, which is what `PRESET_ROLE`'s `None`
            # means here. The delegate offers its inherited entry only where a model says this,
            # because the queue reuses the same delegate and has no group format at all — there,
            # the entry was a control that silently did nothing.
            return True
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return row_text(row, effective)
        if role == Qt.ItemDataRole.AccessibleTextRole:
            # Everything a sighted user reads from the row, for a screen reader (`NFR-005`), plus
            # the way to reach the control they can see and a screen-reader user cannot.
            spoken = row_text(row, effective).replace("\n", ". ")
            return f"{spoken}. {EDIT_HINT}" if self.flags(index) & _EDITABLE else spoken
        return None

    def setData(
        self,
        index: QModelIndex | _PersistentIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        """Give one row its own preset, or send it back to following the batch (`UX-004`).

        **Bound to the row, not to a widget's position.** The control this replaces was connected
        with its list index baked in, so it depended on `_refresh` rebuilding every slot whenever
        the count changed. An editor is opened against a model index that Qt keeps valid, and the
        row is looked up when the choice is made rather than when the control was built.
        """
        if role != PRESET_ROLE:
            return False
        row = self.row_at(index.row()) if index.isValid() else None
        if row is None:
            return False
        if value == CHOOSE_FORMATS_DATA:
            # **Not a preset name — a request to open the table** (`T-108`). Intercepted before the
            # lookup below, which would find no preset by that name and clear the row's format: a
            # wrong download rather than a no-op. The sentinel is unspellable for exactly this
            # reason; the interception is what makes that guarantee load-bearing rather than
            # decorative.
            self._dialog.open_format_table(row)
            return True
        if value == OPTIONS_DATA:
            # Intercepted before the preset lookup for `CHOOSE_FORMATS_DATA`'s reason: no preset is
            # called this, so the lookup would clear the row's format instead of opening anything.
            self._dialog.open_options(row)
            return True
        if value == TEMPLATE_DATA:
            # The third sentinel, intercepted for the same reason as the first two (`T-112`).
            self._dialog.open_template_editor(row)
            return True
        if value == MANAGE_PRESETS_DATA:
            # The fourth, and the only one that does not edit this row (`T-111`). Intercepted for
            # the same reason regardless: no preset is called this, so the lookup below would clear
            # the row's format instead of opening the manager.
            self._dialog.open_preset_manager()
            return True
        name = value if isinstance(value, str) else None
        if name == self.data(index, PRESET_ROLE):
            # **A commit that re-states what the row already says is not a gesture** (`T126-R3`,
            # brought to this dialog by `T-313`). The queue settled this and its reasoning holds
            # here: *the guard is on the value, not on the caller* — knowing **how** `setData` was
            # reached would be state about the call rather than about the row, and it would have to
            # be right at every future call site, while "the row already says this" is true or
            # false on its own.
            #
            # **Compared against `PRESET_ROLE` itself**, which is what filled the editor being
            # committed, so the two cannot drift into disagreeing about what the row says.
            #
            # **What it fixes.** Qt commits an open editor on every refresh, and for a row that
            # *inherits* the batch preset the committed value is the inherited entry's `None` — so
            # merely opening the control and clicking elsewhere reached the clear below and
            # **silently discarded a hand-picked format**. Reported from the built window: *"the
            # format reverted back to 'best video available' despite me not actually selecting it
            # in the dropdown."* `T-311` created the gap by design — it stopped writing the pick
            # into `row.preset`, so an inheriting row with a pick answers `None` here exactly as an
            # untouched one does, and the old guard below could not tell them apart.
            #
            # It also subsumes `T-108`'s narrower case, which is the same shape one state over: a
            # row whose *own* non-catalogue preset is offered as an entry and re-selected.
            self.dataChanged.emit(index, index)
            return True
        row.preset = next((preset for preset in self._dialog.presets if preset.name == name), None)
        if name is None:
            # **Only *follow the batch* gives up a hand-picked format** (`T-313`, restoring what
            # `T-311` ruled). This cleared on **every** preset change, which `T310-R4`'s audit was
            # right about at the time: the format panel then wrote its selector into `row.preset`,
            # so naming a preset really did replace what the row would download and a surviving
            # `format_selection` would have kept answering `REQ-024`'s *"was a merge chosen?"*
            # about a choice that was gone.
            #
            # **`T-311` made those two facts independent and this line was not reconciled with
            # it.** The preset is *how* to download and the selection is *what*; `preset_for`
            # composes them. So naming a preset now keeps the streams and applies the preset over
            # them — the fourth rendered sequence, ruled by the maintainer on 2026-09-10: *"the row
            # remembers only which streams you picked, and whichever preset governs is applied over
            # it."* As built it did the opposite, silently, which is the same data loss the
            # maintainer reported one route over.
            #
            # **The way back is this branch and it is unchanged**, which is `T-311`'s answer to
            # *"how is a stream choice cleared?"*: the inherited entry means *stop using what I
            # picked*, and it is reachable from every state because naming a preset no longer
            # consumes it. The guard above is what makes choosing it distinguishable from Qt
            # committing an untouched control.
            row.format_selection = None
        self.dataChanged.emit(index, index)
        self._dialog.refresh()
        return True

    def flags(self, index: QModelIndex | _PersistentIndex) -> Qt.ItemFlag:
        base = super().flags(index)
        if index.isValid() and self.data(index, PRESET_CHOICES_ROLE):
            return base | _EDITABLE
        return base

    def refresh(self) -> None:
        """Say what actually changed: values, or the set of rows (`T118-R14`).

        **A reset is not free, and this used to do one for every value change.** Qt invalidates a
        live editor's model index on reset, so a sibling row finishing its probe — an ordinary
        multi-row path, not teardown — orphaned the format control the user was in the middle of
        using and discarded the choice without a word. That defeats the per-row request this task
        exists to deliver.

        So a value-only change emits `dataChanged`, which leaves the editor and the current index
        alone. A reset is reserved for the set of rows actually changing, and the editor is
        committed and closed **first**, while its index is still valid.

        Row identity is what distinguishes the two: `Row` is `eq=False` (`REQ-001`, so two
        identical pasted lines stay two rows), so comparing the tuples compares the objects.
        """
        rows = self._dialog.rows
        if rows == self._shown:
            if rows:
                self.dataChanged.emit(self.index(0, 0), self.index(len(rows) - 1, 0))
                # **A value-only refresh re-lays the row out too, and the panel does not follow**
                # (`T204-R4`). This emit names no roles, so it carries `SizeHintRole` with the
                # rest and the view re-measures the row — but an index widget keeps whatever
                # geometry it was last given, so the mounted panel collapsed toward its minimum
                # while the row stayed tall: **the picker and its `Done` button were clipped and
                # the delegate's painting showed through underneath.** The structural path already
                # remounts (below); this one only has to put the geometry back.
            return

        # **Commit while `_shown` is still the old tuple** (`T118-R14`). This is the whole of the
        # fix and it is a one-line ordering point: `commit_open_editor` reaches `setData`, which
        # resolves the editor's index through `row_at` — and `row_at` reads `_shown`. Swap the
        # tuple first and the editor's row number, still numerically valid, names a *different
        # URL*: with A/B/C reconciled to B/C, old index 1 meant B and now means C, so the format
        # the user chose for B is written to C and Add queues the wrong request for both. That is
        # `T118-R6`'s consequence — a silently wrong download — reached from a new direction.
        self._dialog.commit_open_editor()
        self.beginResetModel()
        self._shown = rows
        self.endResetModel()
        # **A reset drops the open panel's index widget, and nothing was putting it back**
        # (`T108-R2`). Qt forgets the widget-to-index association, so the row stayed tall and blank
        # while `_expanded` still pointed at it — and `open_format_table` then returned early
        # because the row *was* the expanded one, so it could never be reopened. Remounting by row
        # identity is what makes a reset survivable; the editor above is committed rather than
        # remounted because a combo box holds no state the row does not already have.


class StatusLabel(QLabel):
    """The dialog's status line, which is a tab stop exactly when it has something to say.

    **Two decisions met here and neither was wrong on its own** (`T-294`). The label is given
    `TextBrowserInteraction` so an extractor's message can be copied into a bug report
    (`NFR-006`) — and that flag carries `LinksAccessibleByKeyboard`, which makes Qt promote the
    label from `NoFocus` to `StrongFocus` as a side effect. Then `T-218` made the empty summary the
    **empty string**, because the hint it used to carry moved into the list. Together they left a
    full-width 17 px tab stop with nothing in it, which the sheet's `*:focus` rule then outlined in
    accent: *"this section gets highlighted even if there isn't anything there."*

    **The ring is right and the tab stop is wrong.** For a borderless control the outline *is* the
    non-colour channel (`T202-R1`), so what had to give is the focusability of a widget with no
    text — copy-ability that exists exactly when there is something to copy.

    **Decided by the text, in the one place the text is set**, rather than by the eight call sites
    that set it. A `_set_status` helper on the dialog would work until the ninth writer, and the
    ninth writer is the one that would forget. The widget never hides and never leaves the chain,
    so the layout does not move and `focus_chain()` stays a single declaration — which is the half
    of `T-060`'s rule this keeps.
    """

    def setText(self, text: str) -> None:
        """Set the message, and be reachable by keyboard only while there is one."""
        super().setText(text)
        # Re-asked on every change rather than only on the empty→non-empty edge: a policy this
        # cheap to compute has no business being stateful.
        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus if text else Qt.FocusPolicy.NoFocus,
        )


class AddUrlDialog(QDialog):
    """Paste URLs, watch them resolve, and queue the ones that did (`UX-003`)."""

    def __init__(
        self,
        *,
        manager: DownloadManager,
        jobs: JobSink,
        output_directory: Path,
        presets: Sequence[Preset] = preset_registry.BUILT_IN_PRESETS,
        thumbnail_loader: ThumbnailLoader | None = None,
        cache_root: Path | None = None,
        resolve_delay_ms: int = DEFAULT_RESOLVE_DELAY_MS,
        ffmpeg_available: bool = True,
        default_cookie_browser: Callable[[], str | None] | None = None,
        default_network: Callable[[], NetworkOptions] | None = None,
        queued_urls: QueuedUrls | None = None,
        save_preset: PresetSink | None = None,
        manage_presets: Callable[[], object] | None = None,
        default_preset: str = "",
        default_output_template: str = preset_registry.DEFAULT_OUTPUT_TEMPLATE,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._manager = manager
        self._jobs = jobs
        #: What the queue holds right now, asked afresh on every refresh (`REQ-022`, `T-114`).
        #:
        #: **Defaults to nothing rather than to a lookup.** A dialog built without it — every test
        #: that is about something else, and any future caller — reports no duplicates, which is
        #: the honest answer for a caller that never said what the queue contains. Guessing would
        #: mean this dialog deciding where a queue lives.
        self._queued_urls: QueuedUrls = queued_urls if queued_urls is not None else (lambda: ())
        #: Where `P-4`'s *Save as preset…* writes (`T109-R5`). Passed straight through to the
        #: options editor, which draws the control only where there is one — this dialog does not
        #: learn what a preset store is, for `QueuedUrls`' reason.
        self._save_preset = save_preset
        #: How `docs/UX_SPEC.md` §8's *Manage presets…* opens (`T-111`).
        #:
        #: **A callable rather than a `Settings`**, for `_save_preset`'s reason one step further on:
        #: this dialog does not learn what a preset store is, and the manager is a screen whose
        #: lifetime and parent belong to whoever composed it. `None` means the entry is not offered
        #: at all — a control with nothing behind it is what `UX-005` §5 forbids drawing.
        self._manage_presets = manage_presets
        #: The name of the preset a new paste inherits (`REQ-007`, `P-7`, `T-111`).
        #:
        #: A resolved *name* rather than a `Settings`, for `presets`' reason: this dialog is handed
        #: the catalogue and what to start on, and does not learn where either is stored. Empty
        #: means the first entry, which is what the control did before there was a default at all.
        self._default_preset = default_preset
        #: How a row is named when its preset states no template of its own (`REQ-023`, `T-195`).
        #:
        #: A resolved *template* rather than a `Settings`, for `_default_preset`'s reason: this
        #: dialog is handed what to use and does not learn where it is stored. The shipped presets
        #: state no template at all, so without this the editor would open empty and a request
        #: would carry nothing — which is why it is resolved here rather than left to `to_request`'s
        #: own fallback.
        self._default_output_template = default_output_template
        self._output_directory = output_directory
        #: **The catalogue, minus what this installation cannot perform** (`REQ-024`, `T199-R1`,
        #: `UX-005` §5). Filtered here rather than at each control because this one tuple feeds
        #: every offer in the dialog — the batch combo, the row selectors, and each row's own
        #: picker through `presets` — so filtering it is what makes *anywhere in the add dialog*
        #: true rather than one surface at a time.
        #:
        #: The review found `Audio only (MP3)`, `Audio only (original)` and `Video with embedded
        #: subtitles` all offered with ffmpeg absent, every one of them refused by the worker's
        #: `_ffmpeg_gap` before a byte moves.
        #:
        #: **`needs_ffmpeg` rather than the definitive `requires_ffmpeg`**, which imports `yt_dlp`
        #: and is barred from `ui/` (`ARCHITECTURE.md` §6). A unit test binds the two over the
        #: whole built-in catalogue so they cannot drift.
        offerable = tuple(presets)
        if not ffmpeg_available:
            without_ffmpeg = tuple(
                preset for preset in offerable if not preset_registry.needs_ffmpeg(preset)
            )
            # **Unless that leaves nothing to offer.** A picker with no entries is a dialog that
            # cannot be used at all, which is worse than an offer the worker refuses with a
            # message naming ffmpeg. The built-in catalogue always keeps at least one video preset,
            # so this is a guard against a user catalogue rather than the ordinary path.
            offerable = without_ffmpeg or offerable
        self._presets = offerable
        #: Whether a merge is possible at all on this installation (`REQ-024`, `P-13`).
        #:
        #: **Passed in rather than looked up here.** `find_ffmpeg` lives in `downloader/` and
        #: `app.py` already calls it once for the manager and the status bar; asking again here
        #: would be a second answer to one question, and the two could differ — `ARC-007`'s reason
        #: for the manager receiving a value rather than reading settings.
        self._ffmpeg_available = ffmpeg_available
        #: The browser a request inherits when its preset names none (`REQ-026`, `T197-R4`).
        #:
        #: **Stamped here, at request construction, which is queue time** — `DAT-003` rules that a
        #: browser profile binds when the job is queued, because it is a field the job carries.
        #: The cookies *file* is the opposite and binds when a worker starts, because it may not
        #: live on the model at all.
        self._default_cookie_browser = default_cookie_browser
        #: The network options a request inherits (`REQ-023`, `T-196`). A callable rather than a
        #: value, for the reason `presets` is one: this dialog outlives any single answer, and
        #: the Settings screen can be used while it is open.
        self._default_network = default_network
        #: The one row that is open, by identity (`T-108`, `T-110`). At most one, and at most one
        #: panel on it: two open tables would be two answers to *"which formats are we looking
        #: at"*, and the list would spend most of its height on them. The playlist picker shares
        #: the slot rather than having one of its own — `P-19` makes them one mechanism, and a
        #: second slot would be the place they could both be open at once.
        self._expanded: Row | None = None
        self._panel: RowPanel | None = None
        #: How to put the row back to what it was before the panel opened, so `Esc` can mean
        #: *choosing nothing*, and what to write onto the row when it closes keeping the choice.
        #: Both are supplied by whichever `open_…` built the panel, because only it knows which of
        #: the row's fields its panel edits.
        #:
        #: **Two panels write as the user acts and one writes on close**, which is why `commit`
        #: exists at all rather than every panel behaving the same way. A format and a set of
        #: checked entries are each a complete choice the moment they are made; a template is a
        #: string that passes through half-typed states its own validator accepts.
        self._undo_panel: Callable[[], None] | None = None
        self._commit_panel: Callable[[], None] | None = None
        #: Fetches, decodes and caches thumbnails, and is asked for one **only while painting**
        #: (`T-119`). The dialog no longer holds pixmaps: a row that scrolls out of view has its
        #: picture released by the cache's own bound, which a dict keyed by job id could not do.
        self._thumbnails = ThumbnailStore(
            loader=thumbnail_loader, cache_root=cache_root, parent=self
        )

        self._staging = Staging()
        #: A batch write is outstanding. Every control that could start a second one is disabled.
        self._saving = False
        #: A refresh is running. See `_refresh` — the structural path re-enters through `setData`.
        self._refreshing = False
        #: Jobs committed by `add_to_queue`, in the order they will be admitted.
        self._committed: tuple[str, ...] = ()
        # `T118-R11`: `_committing` was here too, written and never read. `_saving` is the flag
        # that actually holds the close (`T118-R3`), and a second one that no branch consults is a
        # claim the code does not make.

        self._resolve_timer = QTimer(self)
        self._resolve_timer.setSingleShot(True)
        self._resolve_timer.setInterval(max(resolve_delay_ms, 0))
        self._resolve_timer.timeout.connect(self.resolve)

        self._model = StagingModel(self)
        # A picture arriving is a repaint, not a rebuild: the rows have not changed, only what one
        # of them can draw. `dataChanged` over the whole list lets the view repaint the part it is
        # showing and ignore the rest, which is the point of the store being paint-driven.
        self._thumbnails.ready.connect(self._on_thumbnail_ready)

        self.setObjectName("addUrlDialog")
        self.setWindowTitle("Add URLs")
        self._build()
        self._connect_manager()
        self._set_tab_order()
        self._refresh()

    # --- construction -------------------------------------------------------------------

    def _build(self) -> None:
        # **Two pages in one window** (`T-312`). The staging list is one; an opened panel is the
        # other. `P-1` refused *"a modal over a modal"* and this is not one — the same window shows
        # one page or the other, and *Done* comes back.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._pages = QStackedWidget(self)
        self._pages.setObjectName("dialogPages")
        outer.addWidget(self._pages)

        staging = QWidget(self._pages)
        staging.setObjectName("stagingPage")
        layout = QVBoxLayout(staging)

        self._urls = QPlainTextEdit(self)
        self._urls.setObjectName("urlInput")
        self._urls.setAccessibleName("URLs to download, one per line")
        self._urls.setAccessibleDescription(
            "Paste or type one URL per line. Each line becomes a separate download, and each is "
            "read for its title and thumbnail before it can be queued."
        )
        self._urls.setPlaceholderText("https://…  (one URL per line)")
        self._urls.textChanged.connect(self._on_urls_changed)
        # **The box holds URLs; the list is what the user reads** (`T-210`). Qt split the dialog
        # roughly evenly between them, so a single pasted line was given about as much height as
        # sixteen staged rows — and an opened playlist then had nowhere to go. Capped at
        # `URL_BOX_LINES` and given the layout's *last* claim on spare height, so the rows take the
        # growth. A maximum rather than a fixed height: a short box still shrinks with the window.
        self._urls.setMaximumHeight(self._urls.fontMetrics().lineSpacing() * URL_BOX_LINES)
        layout.addWidget(self._urls)

        listing = self._build_list()
        layout.addWidget(listing)
        # Spare height goes to the rows, which is the half of the dialog that grows with the work.
        layout.setStretchFactor(listing, 1)

        self._status = StatusLabel(self)
        self._status.setObjectName("statusMessage")
        self._status.setAccessibleName("Status")
        self._status.setWordWrap(True)
        # Selectable so the user can copy an extractor message into a search or a bug report. A
        # message kept verbatim (`NFR-006`) that cannot be copied is only half of the point.
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        # **After the flags, because the flags are what promote the policy** (`T-294`).
        # `TextBrowserInteraction` carries `LinksAccessibleByKeyboard`, and setting it moves the
        # label to `StrongFocus`; the text is what decides, so the text is set last.
        self._status.setText(summarise(()))  # empty: the list carries the hint now
        layout.addWidget(self._status)

        layout.addWidget(self._build_preset_row())

        self._buttons = QDialogButtonBox(self)
        self._buttons.setObjectName("dialogButtons")

        self._add_button = QPushButton("&Add to queue", self)
        self._add_button.setObjectName("addButton")
        self._add_button.setAccessibleName("Add to queue")
        self._add_button.setDefault(True)
        self._add_button.clicked.connect(self.add_to_queue)
        self._buttons.addButton(self._add_button, QDialogButtonBox.ButtonRole.AcceptRole)

        self._close_button = QPushButton("&Close", self)
        self._close_button.setObjectName("closeButton")
        self._close_button.setAccessibleName("Close without adding")
        self._close_button.clicked.connect(self.reject)
        self._buttons.addButton(self._close_button, QDialogButtonBox.ButtonRole.RejectRole)

        # **`UX-009`: a library-wide action does not belong on a row.** *Manage presets…* edits the
        # catalogue every row chooses from and does the same thing from every one of them, so it was
        # offered N times to mean one thing. `ResetRole` is what puts it at the *left* of the box,
        # away from the two buttons that decide the dialog's outcome.
        # **One definition of this label** (`T-213`). The negative assertions — that the row
        # combo no longer offers it — import `MANAGE_PRESETS_TEXT`, while this button spelled
        # it a second time. Two spellings of one label is how a guard comes to police a string
        # nothing says any more. The accelerator is inserted rather than stored, because it
        # belongs to this button and not to the name of the action.
        self._manage_presets_button = QPushButton(f"&{MANAGE_PRESETS_TEXT}", self)
        self._manage_presets_button.setObjectName("managePresetsButton")
        self._manage_presets_button.setAccessibleName("Manage presets")
        self._manage_presets_button.setAutoDefault(False)
        self._manage_presets_button.clicked.connect(self.open_preset_manager)
        # **Disabled, not hidden, when nothing wired a manager.** The combo entry it replaces was
        # omitted entirely in that case, but this row of buttons has its own rule and `focus_chain`
        # states it: *"nothing here hides: the retry button is disabled rather than removed … so the
        # chain is the same in every state and the layout does not move under the user."* Hiding
        # would make the declared keyboard order depend on composition's wiring, which is exactly
        # what `T016-R4` and `T-060` are about.
        self._manage_presets_button.setEnabled(self.can_manage_presets)
        self._buttons.addButton(self._manage_presets_button, QDialogButtonBox.ButtonRole.ResetRole)
        layout.addWidget(self._buttons)

        self._pages.addWidget(staging)

        self._panel_page = QWidget(self._pages)
        self._panel_page.setObjectName("panelPage")
        panel_layout = QVBoxLayout(self._panel_page)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        self._pages.addWidget(self._panel_page)

        # `T016-R6`: applied from one list rather than at each construction site, so a label added
        # to that list is protected without anyone remembering a second call.
        for name in UNTRUSTED_TEXT_LABELS:
            label = self.findChild(QLabel, name)
            if label is not None:
                label.setTextFormat(Qt.TextFormat.PlainText)

    def _build_list(self) -> QWidget:
        box = QGroupBox("What you pasted", self)
        box.setObjectName("stagingBox")
        layout = QVBoxLayout(box)

        header = QHBoxLayout()
        self._retry_button = QPushButton("&Retry the ones that failed", box)
        self._retry_button.setObjectName("retryFailedButton")
        self._retry_button.setAccessibleName("Retry the URLs that could not be read")
        self._retry_button.setAccessibleDescription(
            "Read the failed URLs again. A URL that will not read is never added to the queue."
        )
        self._retry_button.clicked.connect(self.retry_failed)
        header.addWidget(self._retry_button)
        header.addStretch(1)
        layout.addLayout(header)

        self._list = StagingList(box, selectors=selector_candidates(self._presets))
        # A taller or shorter list changes how tall an opened row may be, so the rows are
        # re-measured and the open panel put back over the one it belongs to (`T-210`).
        self._list.setObjectName("stagingList")
        self._list.setAccessibleName("The URLs you pasted, and what each one is")
        self._list.setAccessibleDescription(
            "Each line you pasted, with what it turned out to be. " + EDIT_HINT
        )
        self._list.setModel(self._model)
        delegate = RowDelegate(thumbnails=self._thumbnails, parent=self._list)
        # **The disclosure triangle opens the playlist picker** (`P-19`, `docs/UX_SPEC.md` §7).
        # The same signal the queue's groups use, so the gesture means the same thing on both
        # lists — and `StagingList` gives it the `→` / `←` half the spec's keyboard table names.
        delegate.disclosure_toggled.connect(self.toggle_playlist)
        # **The `⋮` zone is the context menu's second door** (`T-203`, `UX-011` option *E*). The
        # delegate emits the click's viewport position, so the same slot the context-menu routes
        # use resolves the row the same way — one menu, not two lookalikes.
        delegate.menu_requested.connect(self._show_row_menu)
        self._list.setItemDelegate(delegate)
        self._list.setUniformItemSizes(True)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        # **The declared keyboard route to a row's control** (`T118-R9`). `EditKeyPressed` is
        # `row_delegate.EDIT_KEY`; `SelectedClicked` is the mouse half. The control is therefore
        # reached *through the row it belongs to* and is never a tab stop of its own, which is what
        # left it landing after Close.
        self._list.setEditTriggers(
            QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        # **A model and a delegate, not a widget per row** (`T118-R10`). A paste is unbounded —
        # this application is public and cannot assume twenty — and one `QWidget` per row made 150
        # URLs a 150-widget layout pass on the GUI thread, measured at 0.722 s on hosted Windows.
        # The delegate paints every row and builds one editor, for the row being edited.
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_row_menu)
        self._list.disclosure_requested.connect(self._on_disclosure_key)
        # The copyable selector below the list follows whichever row is current (`T118-R8`).
        selection = self._list.selectionModel()
        if selection is not None:
            selection.currentChanged.connect(self._show_selector)
        layout.addWidget(self._list)

        return box

    def _build_preset_row(self) -> QWidget:
        box = QGroupBox("Download as", self)
        box.setObjectName("presetBox")
        layout = QVBoxLayout(box)

        # **Two controls in this box announced the same name** (`T200-R7`). Neither had a label, so
        # the only `Label` relation either could offer was the group box — *"Download as"* — and a
        # combo box publishes its selected item as its accessible name on Linux rather than what
        # `setAccessibleName` says. The preset picker and the bitrate picker were therefore
        # indistinguishable to a screen reader, both announcing the section they sit in.
        # **Beside the control, not above it, and the height is why** (`T200-R7`). A label on its
        # own row makes this box taller, and `test_the_panel_fits_the_viewport_at_the_size_the
        # _criteria_claim` measures the playlist panel against a viewport this box shares —
        # measured, two stacked labels pushed it to 210 px inside 198. A `QHBoxLayout` row is as
        # tall as the combo it holds, so the criterion is untouched.
        preset_row = QHBoxLayout()
        preset_label = QLabel("Preset", box)
        preset_label.setObjectName("presetChoiceLabel")
        preset_row.addWidget(preset_label)

        self._preset_choice = QComboBox(box)
        self._preset_choice.setObjectName("presetChoice")
        self._preset_choice.setAccessibleName("Download preset")
        preset_label.setBuddy(self._preset_choice)
        for preset in self._presets:
            self._preset_choice.addItem(preset.name)
        # **The batch opens on the default preset** (`REQ-007`, `P-7`, `T-111`). *"The default
        # preset is what a new paste inherits"* — the whole purpose of there always being exactly
        # one, and until this the control opened on whatever happened to be first in the catalogue.
        #
        # **Set before the signal is connected**, so construction stays as silent as it was when
        # the answer was always index 0: `setCurrentIndex` emits, and `_on_preset_changed` refreshes
        # a dialog that has not finished being built.
        #
        # A name that is not in the catalogue leaves the control on the first entry. That is not
        # reachable through `default_preset_of`, which only ever answers with a preset that exists —
        # but this dialog is constructible directly, and falling back is cheaper than requiring
        # every caller to have resolved the name first.
        wanted = self._preset_choice.findText(self._default_preset) if self._default_preset else -1
        self._preset_choice.setCurrentIndex(max(wanted, 0))
        self._preset_choice.currentIndexChanged.connect(self._on_preset_changed)
        preset_row.addWidget(self._preset_choice, 1)
        layout.addLayout(preset_row)

        # `T-076`, `REQ-010`. A property of the conversion, not a different preset — five MP3
        # presets would encode one parameter as five products, and the model already carries it
        # as `audio_quality`.
        bitrate_row = QHBoxLayout()
        bitrate_label = QLabel("MP3 bitrate", box)
        bitrate_label.setObjectName("audioBitrateLabel")
        bitrate_row.addWidget(bitrate_label)

        self._bitrate_choice = QComboBox(box)
        self._bitrate_choice.setObjectName("audioBitrateChoice")
        self._bitrate_choice.setAccessibleName("MP3 bitrate")
        bitrate_label.setBuddy(self._bitrate_choice)
        self._bitrate_choice.setAccessibleDescription(
            "The constant bitrate to convert to, in kilobits per second. Higher is larger and "
            "closer to the source."
        )
        for bitrate in preset_registry.MP3_BITRATES:
            self._bitrate_choice.addItem(f"{bitrate} kbps", bitrate)
        self._bitrate_choice.setCurrentIndex(
            preset_registry.MP3_BITRATES.index(preset_registry.MP3_QUALITY)
        )
        self._bitrate_choice.currentIndexChanged.connect(self._show_selector)
        bitrate_row.addWidget(self._bitrate_choice, 1)
        layout.addLayout(bitrate_row)

        self._selector_value = QLabel(box)
        self._selector_value.setObjectName("selectorValue")
        self._selector_value.setAccessibleName("Effective format selector")
        self._selector_value.setWordWrap(True)
        # `REQ-009`: the selector is shown so a user can learn the syntax and then write their
        # own, which means it has to be selectable text rather than decoration.
        self._selector_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(self._selector_value)
        self._show_selector()
        return box

    def _set_tab_order(self) -> None:
        for earlier, later in pairwise(self.focus_chain()):
            self.setTabOrder(earlier, later)

    def focus_chain(self) -> list[QWidget]:
        """The keyboard order, stated rather than left to construction order (`NFR-005`, `T-060`).

        **Hidden widgets must not be in the chain** (`T-060`), and nothing here hides: the retry
        button is disabled rather than removed when nothing has failed, so the chain is the same
        in every state and the layout does not move under the user.

        **The chain is a declaration of order, not a claim that every entry is reachable right
        now** (`T-294`). It was read as the second thing, and that is what put an empty status
        label in it as a full-width tab stop with nothing to say. Two widgets here are deliberately
        unreachable in some states and neither leaves: the retry button is *disabled* when nothing
        has failed, and the status line is `NoFocus` while it has no message — see `StatusLabel`.
        Both keep their place, so this list is declared once at construction and the layout never
        moves under the user, which is the property `T-060` was protecting.

        `T016-R4`'s lesson survives the rewrite: a control that can hold focus belongs here even
        when it is read-only. The list is focusable — it is how a keyboard reaches a row's menu.
        """
        return [
            self._urls,
            self._retry_button,
            # `T-203`'s verb bar sat here until `UX-011` moved its three verbs into the row's
            # menu: real `QAction`s reached through the list itself (the Menu key, Shift+F10), so
            # the chain has nothing separate to hold for them.
            self._list,
            # Focusable because it is selectable: a message kept verbatim (`NFR-006`) that cannot
            # be copied into a bug report is half the point. `T016-R4` is what happens when a
            # widget like this is reachable and undeclared.
            self._status,
            self._preset_choice,
            self._bitrate_choice,
            self._selector_value,
            # **Before the two that decide the dialog**, because `ResetRole` draws it at the
            # left of the button box and `T-200`'s rule is that the keyboard follows the eye.
            # `UX-009` put it here; until 2026-08-09 it was an entry in every row's control.
            # It is disabled rather than hidden when no manager is wired, so it is in the chain
            # in every state — the rule stated at the top of this method.
            self._manage_presets_button,
            self._add_button,
            self._close_button,
        ]

    # --- a row, opened (`T-108`'s `P-1` and `T-110`'s `P-19` — one mechanism) --------------

    @property
    def expanded_row(self) -> Row | None:
        """The row that is open, if any. Read by `StagingModel` for `EXPANDED_ROLE`."""
        return self._expanded

    def open_format_table(self, row: Row) -> None:
        """Open `row` into its formats (`REQ-008`, `docs/UX_SPEC.md` §4)."""

        def build() -> RowPanel:
            panel = FormatPanel(
                row,
                row_summary(row),
                ffmpeg_available=self._ffmpeg_available,
                parent=self._list,
            )
            panel.table.format_chosen.connect(self._on_format_chosen)
            panel.table.selection_changed.connect(self._on_selection_changed)
            panel.table.selection_refused.connect(self._show_message)
            return panel

        # **`Esc` puts back *both* halves of the row's earlier format choice** (`T310-R4`).
        #
        # `_on_selection_changed` wrote two fields when this was found — the preset that carried
        # the selector, and `row.format_selection`, the *decision* `REQ-024`'s ffmpeg gate reads.
        # This restored only the first, so abandoning a pair left the decision behind: the reviewer
        # opened the panel
        # without ffmpeg, chose `137` and `140`, pressed `Esc`, and *Add* then submitted no job and
        # reported that merging needs ffmpeg — for a row whose preset `Esc` had correctly returned
        # to `None`. A refusal about a choice the user had just abandoned.
        #
        # **`T-310` is what made it reachable.** A finished pair used to close the panel itself, so
        # there was no open panel left to press `Esc` on; now the panel stays open and the route
        # exists. The two fields are one fact and are restored as one.
        #
        # **Both are still restored, and still for `T310-R4`'s reason** (`T311-R2`). `T-311` stopped
        # the panel writing `row.preset`, so on this route it is usually unchanged — but the
        # options editor and the row's own preset control both reach a row while its panel is open,
        # and restoring one field of a pair is what this finding was about in the first place.
        before_preset = row.preset if isinstance(row.preset, Preset) else None
        before_selection = row.format_selection

        def restore() -> None:
            row.preset = before_preset
            row.format_selection = before_selection

        self._open_panel(row, build, kind=FormatPanel, undo=restore)

    def open_playlist_picker(self, row: Row) -> None:
        """Open `row` into its playlist's entries (`REQ-004`, `docs/UX_SPEC.md` §7, `T-110`).

        **The same machinery the format table uses**, which is `P-19` honoured rather than
        described: one panel slot, one mount, one close, one remount after a reset.
        """
        selection = entry_selection_of(row)
        if selection is None:
            # Not a playlist, or one that enumerated nothing. `UX-005` §5 — nothing is offered
            # that would be refused, and this is the refusal for a route that reached here anyway.
            return

        def build() -> RowPanel:
            panel = PlaylistPanel(
                row,
                row_summary(row),
                selection=selection,
                parent=self._list,
            )
            panel.picker.selection_changed.connect(
                lambda chosen: self._on_entries_chosen(row, chosen)
            )
            return panel

        before = row.entry_selection
        self._open_panel(
            row, build, kind=PlaylistPanel, undo=lambda: setattr(row, "entry_selection", before)
        )

    def open_template_editor(self, row: Row) -> None:
        """Open `row` into `REQ-011`'s template editor and its live preview (`T-112`).

        **The preview is asked for as the panel opens**, not on the first keystroke: a field that
        shows a path only once you have typed into it makes the user prove the feature works before
        it tells them anything, and the interesting case — *what does the template I already have
        produce?* — is the one they arrived with.
        """
        # A preset that states none shows the application default, because that is what the
        # row would actually be named (`T-195`). An empty box would say the row has no
        # template, which is not what an empty `output_template` means.
        template = self.preset_for(row).output_template or self._default_output_template

        panel_holder: list[TemplatePanel] = []

        def build() -> RowPanel:
            panel = TemplatePanel(
                row,
                row_summary(row),
                template=template,
                parent=self._list,
            )
            panel.editor.template_changed.connect(
                lambda text: panel.editor.show_preview(self.preview_for(row, text))
            )
            panel.editor.show_preview(self.preview_for(row, template))
            panel_holder.append(panel)
            return panel

        # **Nothing is written until the panel closes**, which is what makes *"an invalid template
        # never reaches a download"* enforceable at one point rather than at every keystroke. It
        # is also the only correct answer: a user typing `%(title)s` passes through `%`, `%(` and
        # `%(title` — each of which yt-dlp accepts as a literal — so writing as they type left the
        # row holding whichever half-typed prefix happened to be valid last. The first version of
        # this did exactly that and its own test caught it.
        self._open_panel(
            row,
            build,
            kind=TemplatePanel,
            undo=lambda: None,
            commit=lambda: self._commit_template(row, panel_holder),
        )

    def preview_for(self, row: Row, template: str) -> OutputPreview:
        """Where `row` would be written under `template` (`REQ-011`).

        **Through the manager**, which is the only route `ARC-002` leaves open — `ui/` may not
        reach yt-dlp, and rendering an output template is a yt-dlp operation. It is also what makes
        the preview and the write one function rather than two: `DownloadManager` composes the same
        `contained_output_path` the worker calls, over the same `prepare_filename`.

        A row with no probe result yet is previewed against what the row *does* know — its URL as a
        title — so the shape of the path is visible before the probe lands. That is a weaker claim
        than the probed one and the field says so, because the title is what most templates are
        mostly made of.
        """
        media = row.media
        described = (
            media
            if isinstance(media, MediaInfo)
            else MediaInfo(url=row.url, title=row.url, is_playlist=False)
        )
        request = self._with_settings_defaults(
            preset_registry.to_request(
                preset_registry.with_output_template(self.preset_for(row), template or " "),
                url=row.url,
                output_directory=str(self._output_directory),
                default_output_template=self._default_output_template,
            )
        )
        return self._manager.preview_output_path(request, described)

    def _commit_template(self, row: Row, panel_holder: Sequence[TemplatePanel]) -> None:
        """Write the edited template onto `row`, unless it is one that would be refused.

        **`T-112`'s criterion, and this is the single point that enforces it**: *an invalid
        template never reaches a download*. Closing with a refused template keeps the one the row
        already had and says so, rather than either queueing it or discarding the edit in silence —
        the message is the same one the editor was showing, so the reason does not disappear with
        the panel that carried it.
        """
        if not panel_holder:
            return
        text = panel_holder[-1].editor.template
        preview = self.preview_for(row, text)
        if preview.is_refused:
            self._show_message(
                f"{headline_text(row)} keeps its existing file name template. {preview.refusal}"
            )
            return
        row.preset = preset_registry.with_output_template(self.preset_for(row), text)

    def toggle_playlist(self, job_id: str) -> None:
        """Open or close the playlist a staging row holds — the disclosure's own route.

        `docs/UX_SPEC.md` §7: *"`→` / `←` on a header opens / closes the playlist"*, and the
        delegate's disclosure triangle is the pointer half of the same gesture. Resolved through
        `Staging.for_job` rather than by row number, for `T118-R14`'s reason.
        """
        row = self._staging.for_job(job_id)
        if row is None:
            return
        # **The same guard through another door** (`T-295`). Keyed on the row alone, `→` on a row
        # holding a *format* panel closed that panel instead of opening the playlist — the toggle
        # answering for a panel it is not the toggle of. It closes what it opens and swaps
        # everything else, which is what the menu verbs do.
        if self._showing(row, PlaylistPanel):
            self.close_panel(keep=True)
            return
        self.open_playlist_picker(row)

    def _showing(self, row: Row, kind: type[RowPanel]) -> bool:
        """Whether `row` is already open on a panel of `kind` — the question the guards ask.

        **The row alone is not the question, and that was `T-295`** (`UX-005` §5). Every guard here
        keyed on the row, so with a playlist picker open, *Naming and folders…* on that same row
        returned early and did nothing at all: the menu offered it, the menu was reachable, and
        choosing it silently declined. One guard swallowed the other two verbs with the one it was
        written for.

        **Asked in one place**, because `P-19` says the panels are one mechanism rather than
        several: a swap written per panel kind would be three of them, and the third would be the
        one that got forgotten. The kind is the panel's own class, which is what already
        distinguishes them — `open_format_panel` below reads it exactly this way.
        """
        return self._expanded is row and isinstance(self._panel, kind)

    def _open_panel(
        self,
        row: Row,
        build: Callable[[], RowPanel],
        *,
        kind: type[RowPanel],
        undo: Callable[[], None],
        commit: Callable[[], None] = lambda: None,
    ) -> None:
        """Mount one panel on `row`, closing whatever was open (`T-108`, `T-110`, `T-295`).

        **Any other open panel closes first, keeping its choice.** Two open panels would be two
        answers to which row is being looked at, and closing without keeping would silently discard
        a selection the user had already made. A *different* panel on the row that is already open
        is that same swap and always was — the docstring promised it before the guard allowed it.

        **Re-choosing the panel that is already there is still a no-op**, which is the idempotence
        the guard was written for and the half of it that was right.
        """
        if self._showing(row, kind):
            return
        self.close_panel(keep=True)
        index = self._index_of(row)
        if not index.isValid():
            return

        self._expanded = row
        self._undo_panel = undo
        self._commit_panel = commit
        panel = build()
        panel.closed.connect(self._on_panel_closed)
        self._panel = panel

        # **Uniform sizes is a promise this row breaks** (`T118-R10`). The list sets it because a
        # paste is unbounded and measuring every row costs; one open row makes the sizes genuinely
        # non-uniform, so the promise has to be withdrawn while it is open and restored after. Left
        # on, Qt draws every row at the open one's height.
        # **Shown on the next turn, because the control that opened it is still open** (`T108-R2`,
        # one mechanism over). This is reached from `StagingModel.setData`, which Qt calls from
        # inside `commitData` while the row's combo box is live.
        QTimer.singleShot(0, self._show_panel_page)

    def _show_panel_page(self) -> None:
        """Put the panel on its page and show it, once the editor that opened it has gone.

        **The reparent is deferred too, and that is the whole of it** (`T-312`). A panel is built
        with the staging list as its parent, so adding it to this page's layout *moves it out of
        the list* — and doing that while Qt is inside `commitData` on the row's combo box leaves
        the view unable to open another editor ever again: `edit_row` returns true, Qt logs *"edit:
        editing failed"*, and no control appears. That is `T108-R2`'s defect in different clothes,
        and an earlier attempt lost hours to it by deferring only the page switch and reparenting
        immediately — focus changes and `RowDelegate.commit_and_close_editor` both failed to help,
        because neither addressed the reparent.
        """
        panel = self._panel
        if panel is None:
            return
        layout = self._panel_page.layout()
        assert layout is not None
        layout.addWidget(panel)
        self._widen_for(panel)
        self._pages.setCurrentWidget(self._panel_page)
        panel.initial_focus().setFocus()

    def _widen_for(self, panel: RowPanel) -> None:
        """Grow the dialog if the panel needs more width than it has (`T-310`, `T-312`).

        **The page did not remove this, and deleting it was over-eager.** `T-312` makes the panel
        fill the dialog; it does not make the dialog wide. The format table asks for about 1100px
        at the 10pt control font and the dialog opens at 666, so without this the two lists scroll
        sideways in a window that has simply not been told to grow — which the mounted-fit tests
        caught immediately.

        **What the page did remove is the arithmetic.** The old version measured the chrome between
        the dialog and the staging list's viewport, and that quantity *changed when it was acted
        on*: widening the dialog could take the list's vertical scrollbar away, so a figure computed
        from the narrow window was wrong by exactly that much and the whole thing had to iterate to
        a fixed point (`T310-R2`, `WIDEN_PASSES`). A page has no such chrome — the stack fills the
        dialog's content area with zero margins — so one measurement is the answer.

        **Bounded by the screen**, because a panel may ask for more room than exists and a dialog
        wider than the display is one whose buttons cannot be reached.
        """
        outside = self.width() - self._pages.width()
        wanted = min(panel.sizeHint().width() + outside, self.screen().availableGeometry().width())
        if wanted > self.width():
            self.resize(wanted, self.height())

    def close_panel(self, *, keep: bool) -> None:
        """Close the open panel, keeping what was chosen or restoring what was there before.

        `keep=False` is `Esc`'s route — *"closes, choosing nothing"* — and putting the row's earlier
        choice back is what makes "nothing" true. Leaving the selection applied and merely hiding
        the panel would make `Esc` a confirm with extra steps.

        **What "before" means is the opener's to say**, and it must be: a format panel restores the
        row's preset and a playlist panel restores its entry selection, and a close that restored
        both would send a playlist row back to inheriting a format it had chosen for itself.
        """
        row, panel = self._expanded, self._panel
        if row is None or panel is None:
            return
        index = self._index_of(row)
        self._expanded = None
        self._panel = None
        if keep:
            if self._commit_panel is not None:
                self._commit_panel()
        elif self._undo_panel is not None:
            self._undo_panel()
        self._undo_panel = None
        self._commit_panel = None
        # **Off the page and destroyed** (`T-312`). There is no `setIndexWidget(None)` to undo and
        # no row geometry to invalidate: the two branches this replaces were both about a widget Qt
        # owned inside a list item, including the one for a row that vanished underneath it.
        layout = self._panel_page.layout()
        if layout is not None:
            layout.removeWidget(panel)
        panel.setParent(None)
        panel.deleteLater()
        self._pages.setCurrentIndex(0)

        # **Come back to the row that was open.** The panel *was* the row before this, so returning
        # could not lose your place; from a page it can. This is what `_mount_panel` did on the way
        # in, for the same reason.
        if index.isValid():
            # **This reaps the row's editor, and nothing else does** (`T-312`). It looks like dead
            # teardown — no index widget is ever set any more — and removing it cost hours twice.
            # `QAbstractItemView::indexWidget` returns the **editor** registered for an index, so
            # setting it to `None` removes and deletes that editor. The combo box that opened this
            # panel belongs to the list and is still registered: hiding the list does not close it,
            # and Qt's `shouldEdit` then refuses *every* later `edit()` on that index — `edit_row`
            # returns true, Qt logs *"edit: editing failed"*, and no row can be opened again.
            #
            # `RowDelegate.commit_and_close_editor` is **not** a substitute and was tried twice: it
            # clears the delegate's own reference, not the view's registration.
            self._list.setIndexWidget(index, cast("QWidget", None))
            self._model.dataChanged.emit(index, index, [Qt.ItemDataRole.SizeHintRole])
            self._list.setCurrentIndex(index)
            self._list.scrollTo(index, QAbstractItemView.ScrollHint.EnsureVisible)
        self._list.setFocus(Qt.FocusReason.OtherFocusReason)
        self.refresh()

    @property
    def open_panel(self) -> RowPanel | None:
        """The open panel, whichever kind, for a test or a surface that needs to drive it."""
        return self._panel

    @property
    def open_format_panel(self) -> FormatPanel | None:
        """The open panel **when it is the format table**, and `None` when it is anything else.

        Narrowed rather than cast at each call site: a playlist picker is not a format table, and
        a caller reaching for `.table` on one would be asking a question the panel cannot answer.
        """
        return self._panel if isinstance(self._panel, FormatPanel) else None

    @property
    def open_playlist_panel(self) -> PlaylistPanel | None:
        """The open panel **when it is the playlist picker** (`T-110`)."""
        return self._panel if isinstance(self._panel, PlaylistPanel) else None

    @property
    def open_template_panel(self) -> TemplatePanel | None:
        """The open panel **when it is the output template editor** (`T-112`)."""
        return self._panel if isinstance(self._panel, TemplatePanel) else None

    def _index_of(self, row: Row) -> QModelIndex:
        """The model index `row` currently occupies, or an invalid one (`T118-R14`'s rule).

        Resolved through `StagingModel.shown`, which is *the* index mapping — the dialog's own row
        order and the view's belief are different things whenever a reset has not happened yet.
        """
        shown = self._model.shown
        for position, candidate in enumerate(shown):
            if candidate is row:
                return self._model.index(position, 0)
        return QModelIndex()

    def _on_format_chosen(self, _chosen: object) -> None:
        """A row was taken into the selection. **The panel does not close** (`T-310`).

        *Ruled by the maintainer on 2026-09-09 from the built window: "double clicking on both
        selections will also close the window, and I don't think that should happen. The user
        should have to say 'Done' or 'Apply' before that happens."*

        **This supersedes `docs/UX_SPEC.md` §4's "chooses the current format and closes".** That
        sentence was written for a single grid where one press ended the interaction; with two
        lists a choice is rarely the last thing a person wants to do, and closing on it takes the
        surface away mid-task — most sharply on the second half of a pair, where the panel vanished
        the instant the audio row was taken and there was no way back without reopening.

        Closing is now only ever asked for: *Done*, the disclosure triangle, or `Esc`. The choice
        is written to the row as it is made (`_on_selection_changed`), so nothing is lost by the
        panel staying open, and `Esc` still undoes it.
        """

    def _on_selection_changed(self, selection: object) -> None:
        """Write the chosen **streams** onto the row (`REQ-008`, `REQ-009`, `T-311`).

        **The streams alone — the preset is not this method's to touch.** `preset_for` composes the
        two through `with_format_selector`, so the selector reaches the request unchanged while the
        row keeps the conversion, the filename pattern and the media kind it was set up with. The
        row's third line then reads whatever `format_text.format_name` says about the *composed*
        preset — which for a selector no built-in describes is the literal, and that is `UX_SPEC`
        §5's rule honoured by *asking* the shared naming rule rather than by writing the selector
        out here (`T140-R3`, `T126-R2`, `T-159` were all this same defect).

        An incomplete selection writes nothing: half a pair is not a download, and a selector built
        from one half would name `137` for a merge the user has not finished stating.

        *(This docstring described writing a `custom_preset` onto the row, which is what `T-311`
        removed and what `T311-R2` found still described here.)*
        """
        row = self._expanded
        if row is None or not isinstance(selection, FormatSelection):
            return
        if not selection.is_complete:
            return
        # **Only the streams are written** (`T-311`, ruled 2026-09-10). This used to put
        # `custom_preset(selector)` on the row as well — a `Preset` built from nothing, which
        # silently discarded the row's conversion, its filename pattern and its media kind. The
        # selector is not a preset; it is one field of whichever preset governs, and `preset_for`
        # is where the two are joined.
        #
        # `Row.format_selection` was already written here and already carried the *decision*
        # `REQ-024`'s refusal reads — recovering that from `137+140` would mean scanning for a `+`,
        # which is `T-061`'s defect returning by the front door. It is now the single record of the
        # choice rather than a second one kept beside a preset.
        row.format_selection = selection
        self.refresh()

    def _on_panel_closed(self, keep: bool) -> None:
        self.close_panel(keep=keep)

    def _on_entries_chosen(self, row: Row, chosen: object) -> None:
        """Write the checked entries onto the row (`REQ-004`, `T-110`).

        **Written as they are chosen, not when the panel closes.** The row's own detail line says
        how many are chosen, so a user who has unchecked four can see it on the row underneath the
        panel — and `Add to queue` pressed with the picker still open commits what is on screen
        rather than what it was opened with, which is the ordering `T118-R14` established one
        widget over.
        """
        if not isinstance(chosen, PlaylistSelection):
            return
        row.entry_selection = chosen
        self.refresh()

    def _on_disclosure_key(self, opening: bool) -> None:
        """`→` / `←` on the current row (`docs/UX_SPEC.md` §7).

        `→` on a row with no playlist to open does nothing, which is `open_playlist_picker`'s own
        refusal rather than a second copy of the test for it.
        """
        row = self._current_row()
        if row is None:
            return
        if opening:
            self.open_playlist_picker(row)
        elif row is self._expanded:
            self.close_panel(keep=True)

    # --- the post-processing editor (`REQ-010`, `T-109`, `docs/UX_SPEC.md` §6) --------------

    def open_options(self, row: Row) -> None:
        """Open `REQ-010`'s options for `row`, once the control that asked has closed.

        **Deferred by one turn, for `T108-R2`'s reason and one of its own.** This is reached from
        `StagingModel.setData`, which Qt calls from inside `commitData` while the row's combo box
        is still open — and this opens a *modal* dialog, so a synchronous call would run a nested
        event loop underneath a widget Qt is in the middle of closing. Deferring lets the view
        finish first, which is the only ordering in which both can exist.
        """
        QTimer.singleShot(0, lambda: self._show_options(row))

    def _show_options(self, row: Row) -> None:
        """Edit `row`'s options and, if accepted, make the answer the row's own preset.

        **The editor opens on the row's *effective* preset**, which is its own if it has one and
        the batch's otherwise (`UX-004`). Opening on the batch's while the row has its own would
        silently discard the row's choice the moment the user pressed OK.

        **Accepting always gives the row a preset of its own**, even where the values are the ones
        it was already following: the user has now stated them for this row, and leaving it
        inheriting would let a later change to the batch's format overwrite what they said.
        """
        if row not in self.rows or not row.committable:
            # The row went away, or stopped being committable, between the choice and this turn.
            return
        media = row.media
        dialog = OptionsDialog(
            self.preset_for(row),
            subtitle_languages=(media.subtitle_languages if isinstance(media, MediaInfo) else ()),
            save_preset=self._save_preset,
            parent=self,
            # `REQ-024`, `T-199`: what ffmpeg performs is not offered when ffmpeg is absent. The
            # same answer this dialog already gates the format table's merge mode on (`P-13`), so
            # the two surfaces cannot disagree about the same fact.
            ffmpeg_available=self._ffmpeg_available,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        row.preset = dialog.result_preset()
        # **The chosen formats survive the options, and the statement with them.** A row that
        # picked `137+140` from the table and then set options is still a chosen merge, and
        # `REQ-024`'s refusal reads `format_selection` rather than the selector (`T-061`).
        self.refresh()

    def _merge_refusals(self, rows: Sequence[Row]) -> str | None:
        """The first reason a chosen merge cannot be committed, or `None` (`REQ-024`).

        **Named per row**, because a batch of twenty with one offending row needs to say *which*.
        The first is enough: fixing it means reopening that row's table, and listing every one would
        be a paragraph the user has to read before they can act on its first sentence.

        `close_panel` runs before this, so the open panel's selection is already on its row.
        """
        for row in rows:
            selection = row.format_selection
            if not isinstance(selection, FormatSelection):
                continue
            refusal = merge_refusal(selection, ffmpeg_available=self._ffmpeg_available)
            if refusal is not None:
                return f"{headline_text(row)}: {refusal}"
        return None

    def _show_message(self, message: str) -> None:
        """Put a refusal where the user is already looking — the dialog's own status line.

        The panel has no status line of its own, and adding one would give this dialog two places a
        message can appear. `_refresh` overwrites this with the batch summary on the next change,
        which is right: a refusal is about the press that caused it.
        """
        self._status.setText(message)

    def _connect_manager(self) -> None:
        self._manager.media_probed.connect(self._on_media_probed)
        self._manager.job_failed.connect(self._on_job_failed)
        self._manager.job_changed.connect(self._on_job_changed)
        # Staging probes report on their own channel (`T118-R1`), because they are not queue work.
        self._manager.staged_changed.connect(self._on_job_changed)
        self._manager.start_rejected.connect(self._on_start_rejected)
        self._manager.persistence_failed.connect(self._on_persistence_failed)

    # --- queries ------------------------------------------------------------------------

    @property
    def rows(self) -> tuple[Row, ...]:
        """The rows describing what is entered, in entry order."""
        return self._staging.visible

    @property
    def queued_job_ids(self) -> tuple[str, ...]:
        """The jobs this dialog committed, in the order they were admitted."""
        return self._committed

    @property
    def is_saving(self) -> bool:
        return self._saving

    def status_text(self) -> str:
        """What the dialog is telling the user. A method, as it has always been."""
        return self._status.text()

    def effective(self, preset: Preset) -> Preset:
        """`preset` with every field the dialog's controls decide filled in (`T118-R6`).

        **One derivation, reachable from every path that needs one.** The batch had this and the
        per-row override did not: choosing *Audio only (MP3)* for one row stored the registry's
        preset, whose `audio_quality` is the 192 kbps default, while the visible bitrate control
        said 320. `T-076` requires the displayed bitrate to be the one that runs, and derives the
        preset precisely so display and request cannot drift — this is the second time that pair
        has been split apart, and both times by a caller that reached for the raw preset.

        Bitrate is the only such field today. It is written as a derivation rather than a special
        case so that the next one is added here instead of beside the next caller.
        """
        if preset.audio_codec is not AudioCodec.MP3:
            return preset
        return preset_registry.with_audio_quality(preset, self.selected_bitrate)

    @property
    def selected_preset(self) -> Preset:
        return self.effective(self._presets[max(self._preset_choice.currentIndex(), 0)])

    @property
    def selected_bitrate(self) -> str:
        return str(self._bitrate_choice.currentData())

    @property
    def presets(self) -> tuple[Preset, ...]:
        """The batch's choices, which are also each row's. Read by `StagingModel`."""
        return self._presets

    @property
    def can_manage_presets(self) -> bool:
        """Whether *Manage presets…* is offered. Read by `StagingModel` (`T-111`)."""
        return self._manage_presets is not None

    def open_preset_manager(self) -> None:
        """Open `docs/UX_SPEC.md` §8's manager, once the control that asked has closed.

        **Does not touch this dialog's row** (`T-111`). The catalogue a row chooses from is
        composition's, not this dialog's: `presets` was handed over at construction and the manager
        writes to the settings store behind it. Whoever wired `manage_presets` decides whether a
        change is reflected here, which is the same division `save_preset` already has.

        **Deferred by one turn, exactly as `open_options` is** (`T111-R3`, `T108-R2`). This is
        reached from `StagingModel.setData`, which Qt calls from inside `commitData` while the row's
        combo box is still open, and composition's callback opens a *modal* manager — so calling it
        synchronously runs a nested event loop underneath a widget Qt is in the middle of closing.
        That is the dead-editor class `T108-R2` records, and the sibling route already defers for
        this reason; this one was written without the deferral and its test called `setData`
        directly, so it exercised everything about the route except the stack it actually runs on.
        """
        QTimer.singleShot(0, self._show_preset_manager)

    def _show_preset_manager(self) -> None:
        """Hand off to composition's manager callback, a turn after the row editor closed."""
        if self._manage_presets is not None:
            self._manage_presets()

    @property
    def model(self) -> StagingModel:
        """What the list draws from. The surface a test reads a row's fields by value."""
        return self._model

    @property
    def thumbnails(self) -> ThumbnailStore:
        return self._thumbnails

    def thumbnail_for(self, row: Row) -> QPixmap | None:
        """The decoded thumbnail for `row`, or `None` if none has arrived.

        **`peek`, not `pixmap`**: asking whether a picture exists must not cause it to be fetched,
        or this method would quietly become a second fetch path and `T-119`'s "no fetch for a row
        the view never painted" would be false whenever anything asked.
        """
        media = row.media
        url = media.thumbnail_url if isinstance(media, MediaInfo) else None
        return self._thumbnails.peek(url)

    def _on_thumbnail_ready(self, _url: str) -> None:
        """A picture arrived, so the rows showing it repaint. Nothing else changed."""
        count = self._model.rowCount()
        if count:
            self._model.dataChanged.emit(self._model.index(0, 0), self._model.index(count - 1, 0))

    def _on_urls_changed(self) -> None:
        """Restart the debounce. **Nothing is started from a keystroke.**

        A probe per character would spawn an interpreter per character (`ARC-002`). Restarting the
        timer means a paste resolves once, and a URL typed by hand resolves once the typing stops.
        """
        self._resolve_timer.start()
        self._refresh()

    def resolve(self) -> None:
        """Reconcile the rows with what is entered, and read whatever has not been read.

        Public so a test drives it directly rather than waiting on wall-clock time — the timer
        calls exactly this and nothing else, so the tested path is the real one.

        **Nothing is persisted here** (`T118-R1`, `UX-003`). Reading is a *staging* probe: the
        manager holds a transient job for it and never writes a row. The first version submitted
        `QUEUED` jobs in order to have ids to probe, and `compose()` admits every durable `QUEUED`
        or `READY` row at startup — so a crash after a probe succeeded downloaded a URL the user
        had never committed to. Add is the only thing that writes.

        **A row whose line is gone is unstaged, not withdrawn.** There is no queue row to cancel
        or delete, which is the whole of the ruling: what the queue never held, it never has to be
        told about.
        """
        self._resolve_timer.stop()
        self._staging.reconcile(split_urls(self._urls.toPlainText()))
        for row in self._staging.rows:
            if row.state is RowState.SUPERSEDED and row.job_id is not None:
                self._manager.unstage(row.job_id)
                row.job_id = None

        for row in self._staging.pending():
            self._read(row)
        self._refresh()

    def _read(self, row: Row) -> None:
        """Start a staging probe for one row.

        **Synchronous up to the id**, which is what closes `T118-R2`: the first version wrote the
        jobs first and started the probes in the write's callback, so editing or closing during
        that window left the dialog with rows it had no ids for — `done()` withdrew nothing, and
        the callback then persisted and started the URL the user had just taken away. There is no
        such window now. `stage()` returns the id before it returns at all.
        """
        try:
            row.job_id = self._manager.stage(self._request_for(row))
        except (RuntimeError, ValueError) as refusal:
            row.state = RowState.FAILED
            row.message = str(refusal)
            return
        row.state = RowState.WAITING

    def retry_failed(self) -> None:
        """Read the failed URLs again (`UX-003`).

        A timeout costs a button press rather than the paste. The row goes back to `PENDING` and is
        staged afresh; there is no durable row to withdraw, because a staging probe never was one
        (`T118-R1`).
        """
        failed = self._staging.failed()
        if not failed:
            return
        for row in failed:
            if row.job_id is not None:
                self._manager.unstage(row.job_id)
            row.job_id = None
            row.message = None
            row.state = RowState.PENDING
        self.resolve()

    def remove_row(self, row: Row) -> None:
        """Take one line out of the batch without editing the box.

        The row is superseded and its staging probe stopped, exactly as editing the line away would
        do — one route, one set of consequences.
        """
        if row.state is RowState.SUPERSEDED:
            return
        remaining = [other.url for other in self._staging.visible if other is not row]
        row.state = RowState.SUPERSEDED
        if row.job_id is not None:
            self._manager.unstage(row.job_id)
            row.job_id = None
        # The box is the source of truth for what is entered, so it changes too. Blocked so the
        # edit does not restart the debounce and reconcile against a list already correct.
        self._urls.blockSignals(True)
        self._urls.setPlainText("\n".join(remaining))
        self._urls.blockSignals(False)
        self._refresh()

    def edit_row(self, index: int) -> bool:
        """Open the format control for one row. **The keyboard route, as a method** (`T118-R9`).

        Public because the route has to be assertable: `EditKeyPressed` is a Qt setting, and a
        test that only pressed the key would prove Qt works rather than that this dialog offers
        the control on the row where a user expects it. The context menu uses this too, so the
        mouse and the keyboard reach one editor rather than two lookalikes.

        Answers `False` for a row with no editor — one that has not resolved, or one whose commit
        is already being written — which is the same question `flags` answers Qt.
        """
        model_index = self._model.index(index, 0)
        if not model_index.isValid() or not model_index.flags() & _EDITABLE:
            return False
        self._list.setCurrentIndex(model_index)
        self._list.edit(model_index)
        return True

    def row_menu(self, row: Row) -> QMenu:
        """The row's own menu: its per-item verbs, then what can be done to the line (`T-203`).

        **One menu, two doors** (`UX-011`, option *E*): the `⋮` zone painted on the row's format
        control and the context-menu routes — right-click, the Menu key, Shift+F10 — all land in
        `_show_row_menu`, which builds here. Public because the criterion is that the doors
        produce **the same actions**, and that has to be assertable on the actions rather than on
        two menus happening to agree.

        **The target is structural.** The menu is built for the row it was opened from — which
        need not be the current row — so nothing announces a target and nothing can drift:
        `T203-R1` was the shared bar failing to *say* which row it meant, and this shape has no
        saying to get wrong.

        **It offers what the row can actually do**, reading the model's own roles the way the
        bar's enablement did (`UX-005` §5) — but by the menu's own idiom for conditional entries,
        which is absence: Retry appears only on a failed row, and a playlist's formats entry is
        not there at all, because its formats belong to its entries (`T-110`).
        """
        menu = QMenu(self._list)
        shown = self._model.shown
        index = self._model.index(shown.index(row), 0) if row in shown else QModelIndex()

        offers_formats = index.isValid() and bool(index.data(FORMATS_AVAILABLE_ROLE))
        offers_options = index.isValid() and bool(index.data(OPTIONS_AVAILABLE_ROLE))
        offers_template = index.isValid() and bool(index.data(TEMPLATE_AVAILABLE_ROLE))
        if offers_formats or offers_options or offers_template:
            # `UX-011`'s heading, and its order: the per-item verbs sit **above** the entries the
            # menu already held, first `Choose specific formats…`, per `docs/UX_SPEC.md` §4.
            menu.addSection("Just this item")
            if offers_formats:
                formats = QAction(CHOOSE_FORMATS_TEXT, menu)
                formats.triggered.connect(lambda: self.open_format_table(row))
                menu.addAction(formats)
            if offers_options:
                options = QAction(OPTIONS_TEXT, menu)
                options.triggered.connect(lambda: self.open_options(row))
                menu.addAction(options)
            if offers_template:
                template = QAction(TEMPLATE_TEXT, menu)
                template.triggered.connect(lambda: self.open_template_editor(row))
                menu.addAction(template)
            menu.addSeparator()

        if row.state is RowState.FAILED:
            retry = QAction("Read this URL again", menu)
            retry.triggered.connect(lambda: self._retry_row(row))
            menu.addAction(retry)
        # **`T118-R9`'s discoverability alias is gone** (`UX-012`, `T-223`). It opened the row's
        # format combo through `edit_row` — a control already visible on the row — so on a single
        # item it named a thing the user was looking at, and on a playlist row it read as a no-op
        # that highlights a combo and changes nothing. **The keyboard route it advertised is
        # untouched**: the edit key still reaches `edit_row`, which is what made the entry
        # redundant rather than what made it useful.
        remove = QAction(remove_label(row), menu)
        remove.triggered.connect(lambda: self.remove_row(row))
        menu.addAction(remove)
        return menu

    def _show_row_menu(self, position: Any) -> None:
        """Show one row's menu. **A context menu, reachable from the keyboard.**

        `CustomContextMenu` rather than `contextMenuEvent`, for the reason `T-086`'s file actions
        use it: the menu key and Shift+F10 both raise it, so the actions are not mouse-only
        (`NFR-005`). The delegate's `⋮` zone lands here too, carrying the click's viewport
        position — so every pointer door resolves the row the same way: whatever row is under
        the point.

        **The current row when the position names none** (`T203-R3`, the queue's `T124-R1`
        lesson relearned): Qt raises a keyboard-reason request with a position derived from the
        widget rather than from a row, so resolving through `indexAt` alone answered "no row"
        for every Menu-key/Shift+F10 request and the declared route silently did nothing. The
        painted `⋮` has no accessibility node by design, so this fallback *is* the keyboard
        door `NFR-005` requires. The popup then anchors on the resolved row rather than at the
        widget-derived point, so the menu opens beside what it acts on.

        **`popup`, not `exec`** (`T-203`). The same menu with the same grabs, shown without a
        nested event loop — `exec` cannot be returned from headlessly, so a door that exec'd
        would be a route no test can drive to its actions. Deleted on close, so each opening is
        one widget with one lifetime rather than a child accumulating per right-click.
        """
        clicked = self._list.indexAt(position)
        index = clicked if clicked.isValid() else self._list.currentIndex()
        row = self._row_at(index.row()) if index.isValid() else None
        if row is None:
            return
        anchor = position if clicked.isValid() else self._list.visualRect(index).center()
        menu = self.row_menu(row)
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        menu.popup(self._list.viewport().mapToGlobal(anchor))

    def _retry_row(self, row: Row) -> None:
        if row.state is not RowState.FAILED:
            return
        if row.job_id is not None:
            self._manager.unstage(row.job_id)
        row.job_id = None
        row.message = None
        row.state = RowState.PENDING
        self.resolve()

    def _row_at(self, index: int) -> Row | None:
        """The row a model index describes, or `None` if it describes nothing.

        **Through the model's own snapshot, never through live staging** (`T118-R14`). Between a
        reconcile and the reset that announces it, `Staging.visible` has already changed while the
        view still holds the old indices — so resolving here against staging would answer for a
        row the user is not looking at, which is how an open editor's choice reached the following
        URL.
        """
        return self._model.row_at(index)

    # --- manager signals ------------------------------------------------------------------

    def _on_media_probed(self, job_id: str, media: object) -> None:
        """Accept a result only if it describes a line still on screen (`T016-R1`)."""
        row = self._staging.for_job(job_id)
        if row is None or not isinstance(media, MediaInfo):
            return
        if row.state is RowState.SUPERSEDED:
            # **This is the binding**, not a backstop for it. `resolve()` retires a row whose line
            # changed, but the signal carrying its result may already be queued, so the refusal
            # has to live where the result is received.
            return
        row.media = media
        row.state = RowState.READY
        # **A fresh probe replaces the entries, so it replaces the choice made against them**
        # (`T-110`). A retry can return a playlist of a different length, and a selection of
        # positions held over from the previous extraction would name different items. Everything
        # chosen is the state `REQ-004` starts from — see `PlaylistSelection.all_of`.
        row.entry_selection = (
            PlaylistSelection.all_of(len(media.entries)) if media.entries else None
        )
        # **No fetch is started here** (`T-119`). The row now knows a thumbnail URL; whether the
        # bytes are ever wanted is decided by whether the view paints the row. A probe result for
        # row four hundred of a paste costs nothing until row four hundred is on screen.
        self._refresh()

    def _on_job_failed(self, job_id: str, kind: object, message: str) -> None:
        """Keep the extractor's message **verbatim** (`REQ-005`, `NFR-006`).

        Not summarised, not paraphrased, and not folded into a sentence that changes it. The
        classification is shown beside it rather than instead of it: the kind tells the user
        whether retrying could help, and the text is the only thing that says what happened.
        """
        row = self._staging.for_job(job_id)
        if row is None or row.state is RowState.SUPERSEDED:
            return
        label = kind.value if isinstance(kind, ErrorKind) else str(kind)
        row.state = RowState.FAILED
        row.message = f"{label}: {message}"
        self._refresh()

    def _on_job_changed(self, job_id: str, status: str) -> None:
        """Notice a resolved row that stopped being startable."""
        row = self._staging.for_job(job_id)
        if row is None:
            return
        if row.state is RowState.WAITING and status == JobStatus.PROBING.value:
            # The lane took it. This is the only honest moment to say so: `admit` returns before
            # the manager has decided anything.
            row.state = RowState.PROBING
            self._refresh()
            return
        if row.state is not RowState.READY:
            return
        if status not in (JobStatus.READY.value, JobStatus.RUNNING.value):
            # Cancelled from the queue view, or lost to a shutdown. Committing it would call
            # `admit` on a job the state machine refuses.
            row.state = RowState.FAILED
            row.message = f"this URL left the queue while the dialog was open (now {status})"
            self._refresh()

    def _on_persistence_failed(self, job_id: str, reason: str) -> None:
        """A durable write failed for something this dialog is responsible for.

        **Not swallowed**, which is `T016-R1`'s rule surviving the change of mechanism. The
        withdrawal machinery that used to own this signal is gone — there is nothing to withdraw
        before Add — but a write that fails *after* Add is a row the queue may now be wrong about,
        and the person who just pressed the button is the one who should hear.

        Scoped to ids this dialog knows. A failure for someone else's job is the queue's business,
        and reporting it here would put a message about an unrelated download in front of a user
        who is adding URLs. **That leaves a real gap** — nothing owns this signal once the dialog
        closes — and it is recorded rather than papered over: the dialog was this signal's only
        listener before this change too.
        """
        mine = job_id in self._committed or self._staging.for_job(job_id) is not None
        if not mine:
            return
        self._status.setText(
            f"The queue's record of this download could not be written: {reason} "
            "The download itself may be running; the queue is what is behind."
        )
        self._refresh()

    def _on_start_rejected(self, job_id: str, reason: str) -> None:
        """The probe this dialog asked for never became a session (`T016-R3`).

        `admit()` returns once the transition is *queued*, so its synchronous refusals are not the
        whole answer: the write can fail, or a cancel can win the race. Without this the row would
        say "Reading" for ever.
        """
        row = self._staging.for_job(job_id)
        if row is None or row.state is RowState.SUPERSEDED:
            return
        if row.state is RowState.READY:
            # A rejection for a row that already resolved is about the *commit*, not the probe.
            row.state = RowState.FAILED
        elif row.state not in (RowState.PROBING, RowState.SAVING, RowState.WAITING):
            return
        else:
            row.state = RowState.FAILED
        row.message = f"could not be read: {reason}"
        self._refresh()

    # --- queueing -----------------------------------------------------------------------

    def add_to_queue(self) -> None:
        """Persist the rows that resolved, and only those (`UX-003`, `REQ-012`, `T118-R3`).

        **This is the first and only write.** Each committable row becomes a durable `Job` built
        from *its own* effective preset (`UX-004`), so the request that runs is the one selected
        when Add was pressed and there is nothing to retarget afterwards. `T-075`'s rule, applied
        per row and satisfied by construction rather than by a second write.

        The retarget it replaces is what `T118-R3` was about: Add stayed enabled while retargets
        were outstanding, and `done()` exempted the committed ids from cleanup before their chosen
        request was durable — so a dialog closed in that window left a `READY` row carrying the
        *old* request, which startup then admitted and downloaded in the wrong format. No request
        is ever stored and then changed, so that window does not exist.

        **The count is what resolved, not what was pasted.** A URL that would not read never
        becomes queued work; it stays on screen with its message and its retry.
        """
        if self._saving:
            return
        # **Commit the open panel's choice first** (`T118-R14`'s ordering, one widget over). A user
        # who picked formats and pressed Add without closing the table has chosen; discarding it
        # because a widget was still open would queue the format they replaced.
        self.close_panel(keep=True)
        committable = self._staging.committable()
        if not committable:
            self._status.setText(
                "Nothing has been read yet, so there is nothing to add. "
                "Paste a URL, or retry the ones that failed."
            )
            return

        # **An explicitly chosen video + audio pair is refused before the download starts**
        # (`REQ-024`, `docs/UX_SPEC.md` §5). `P-13` means the mode is not even drawn without ffmpeg,
        # so this normally cannot trigger — it is the check that survives ffmpeg going away between
        # opening the table and pressing Add, and it is where `REQ-024`'s *"before, not at merge
        # time"* is actually satisfied for a stated merge.
        refused = self._merge_refusals(committable)
        if refused is not None:
            self._status.setText(refused)
            return

        # Entry order, which becomes `queue_position` order: the repository allocates `MAX + 1`
        # inside the insert transaction, so submitting in this order is what the pool will start
        # in (`T115-R1`).
        # **A playlist becomes one job per entry** (`T-137`, `UX-005` row 9). One staged row can
        # therefore produce many queue rows, which is why this flattens rather than maps: the
        # pairing is kept so `_on_committed` can still report per staged row.
        fresh = [(row, job) for row in committable for job in self._durable_jobs(row)]
        if not fresh:
            # **Every committable row is a playlist with nothing checked** (`REQ-004`, `T-110`).
            # Submitting an empty batch would succeed, close the dialog and add nothing — the
            # user's choice honoured and their whole paste silently discarded. Said instead, with
            # the batch left on screen so unchecking everything is one keystroke from being undone.
            self._status.setText(
                "Nothing is chosen. Open a playlist and choose the entries you want, "
                "or choose all of them."
            )
            return
        self._saving = True
        self._status.setText(f"Adding {len(fresh)} to the queue …")
        self._refresh()
        self._jobs.submit([job for _, job in fresh], lambda error: self._on_committed(fresh, error))

    def _on_committed(self, fresh: Sequence[tuple[Row, Job]], error: str | None) -> None:
        """The rows are durable, or they are not. Only then is anything admitted.

        `REQ-012`'s persist-before-start, and the dialog closes **inside** this callback so it
        cannot close before the rows exist. A failed write leaves it open with the user's input
        intact and nothing staged discarded.
        """
        self._saving = False
        if error is not None:
            self._status.setText(
                f"Nothing was added and the queue is unchanged. {error} "
                "Your URLs are still here; try again."
            )
            self._refresh()
            return

        # The staging probes have served their purpose; the durable rows are different ids.
        for row, _ in fresh:
            if row.job_id is not None:
                self._manager.unstage(row.job_id)

        self._committed = tuple(job.id for _, job in fresh)
        refusal: str | None = None
        try:
            for _, job in fresh:
                # **An unprobed row is admitted as a probe, not a download** (`T137-R2`,
                # `UX-003`). A pasted URL arrives here already `READY` — the staging list probed
                # it, which is the whole of `UX-003` — and downloads from there. A playlist's
                # entries arrive `QUEUED`, because `T-137` builds them from a *flat* extraction
                # that names them without resolving them; admitting those as `DOWNLOAD` is what
                # made every entry of a playlist download unprobed.
                #
                # Read from the job's own status rather than from whether the row was a playlist,
                # so the rule is "unprobed things get probed" rather than a second place that has
                # to know what a playlist is. `ARC-009` carries each one into its download once
                # the probe lands.
                kind = SessionKind.PROBE if job.status is JobStatus.QUEUED else SessionKind.DOWNLOAD
                self._manager.admit(job.id, kind)
        except (RuntimeError, ValueError) as start_error:
            refusal = str(start_error)

        if refusal is not None:
            self._status.setText(
                f"Added, but the downloads did not start: {refusal} "
                "They stay in the queue and can be started from there."
            )
            self._refresh()
            return
        self.accept()

    def _durable_jobs(self, row: Row) -> list[Job]:
        """The queue jobs for a resolved row: one, or one per playlist entry (`T-137`).

        **A playlist that enumerated is expanded here rather than by the downloader.** Every entry
        becomes an ordinary job — its own progress, its own verbs, its own row — which is exactly
        what `UX-005` row 9 buys by grouping them in the *view* instead of in the queue. The
        downloader is untouched: it still sees single downloads and has never heard of a playlist.

        **A playlist that did not enumerate stays one job**, and that is not a fallback so much as
        the honest answer: `entries` is what this extraction materialised, and with none of them
        there is nothing to expand into. It downloads as the user's URL, which is what it did
        before `T-137` — the difference is that it no longer *claims* sixteen items while doing it.
        """
        media = row.media
        probed = media if isinstance(media, MediaInfo) else None
        if probed is None or not probed.entries:
            return [self._durable_job(row)]

        # **Only the entries the user checked** (`REQ-004`, `T-110`). An unopened picker means all
        # of them — see `PlaylistSelection.all_of` — and an emptied one means none, which produces
        # no jobs at all rather than falling back to the whole playlist. `add_to_queue` is where
        # that is reported; silently queueing the lot would be the wrong download this task exists
        # to prevent.
        selection = entry_selection_of(row)
        chosen = (
            selection.chosen_with_index(probed.entries)
            if selection is not None
            else tuple(enumerate(probed.entries))
        )
        if not chosen:
            return []

        playlist_id = str(uuid.uuid4())
        # **Into a folder named for the playlist** (`UX-005` row 10). Sanitised through the same
        # function the output path uses, so a title with a slash in it cannot escape the download
        # directory — the entries land together or they do not land at all.
        folder = sanitize_component(probed.title)
        directory = self._output_directory / folder if folder else self._output_directory
        return [
            Job(
                id=str(uuid.uuid4()),
                url=entry.url,
                # **Every entry, not only the pasted line** (`T197-R4`). A playlist expands into
                # children built here, and stamping the default in `_request_for` alone left every
                # one of them unauthenticated — the case a user most often has cookies *for*.
                request=self._with_settings_defaults(
                    preset_registry.to_request(
                        self.preset_for(row),
                        url=entry.url,
                        output_directory=str(directory),
                        default_output_template=self._default_output_template,
                    )
                ),
                # **Queued, not ready.** `UX-003` makes a pasted URL a probed one; a flat entry is
                # named but not extracted, so calling it `READY` would claim a probe nobody ran.
                status=JobStatus.QUEUED,
                title=entry.title,
                thumbnail_url=entry.thumbnail_url,
                duration_seconds=entry.duration_seconds,
                playlist_id=playlist_id,
                # **The entry's own position, not its position among the chosen ones** — see
                # `PlaylistSelection.chosen_with_index`.
                playlist_index=index,
                playlist_title=probed.title,
                created_at=datetime.now().astimezone(),
            )
            for index, entry in chosen
        ]

    def _durable_job(self, row: Row) -> Job:
        """The queue job for a resolved row, carrying everything the probe learned.

        `title` and `thumbnail_url` come across from the staging probe rather than being left for
        the download session to rediscover (`T-117`): the row on screen already knows them, and a
        queue that showed a URL until its download started would be `UX-003` undone at the moment
        of committing.

        **`uploader` and `duration_seconds` come across for the same reason** (`T124-R4`,
        `UX-005` §3). They were the two fields this method knew and dropped: the staging row draws
        them, `Add` closed the dialog, and the queue row that replaced it could not — so the
        accepted row anatomy held while a URL was being staged and stopped holding the moment it
        was committed. The whole set the probe learned now crosses together, which is also why
        adding the next one is a schema change and not a second omission.
        """
        media = row.media
        probed = media if isinstance(media, MediaInfo) else None
        return Job(
            id=str(uuid.uuid4()),
            url=row.url,
            request=self._request_for(row),
            status=JobStatus.READY if probed is not None else JobStatus.QUEUED,
            title=probed.title if probed is not None else None,
            thumbnail_url=probed.thumbnail_url if probed is not None else None,
            uploader=probed.uploader if probed is not None else None,
            duration_seconds=probed.duration_seconds if probed is not None else None,
            # **`REQ-017`'s only knowable-in-advance refusal** (`T-113`). The probe says whether
            # this is live and the queue row is where it has to be said, so it crosses with the
            # rest of what the probe learned rather than dying with the dialog — which is what
            # `thumbnail_url` and `uploader` each had to be corrected for.
            is_live=probed.is_live if probed is not None else False,
            created_at=datetime.now().astimezone(),
        )

    def _request_for(self, row: Row) -> DownloadRequest:
        """The request `row`'s **effective** preset would download it with (`T-075`, `UX-004`).

        One place builds a request, so "what the user chose" cannot mean two different things in
        two code paths — which is the shape the preset defect had. `UX-004` made that choice
        per row: a row with its own preset uses it, and a row without follows the batch.
        """
        request = preset_registry.to_request(
            self.preset_for(row),
            url=row.url,
            output_directory=str(self._output_directory),
            default_output_template=self._default_output_template,
        )
        return self._with_settings_defaults(request)

    def _with_settings_defaults(self, request: DownloadRequest) -> DownloadRequest:
        """The settings a request inherits at queue time (`ARCHITECTURE.md` §8).

        **One entry point for the whole freeze**, so a second settings-level default cannot be
        added to one of the three request-building routes and forgotten on the other two —
        `T197-R4` is that finding: the cookie browser was stamped in `_request_for` alone, and
        every child of an expanded playlist went out unauthenticated.
        """
        return self._with_default_network(self._with_default_cookie_browser(request))

    def _with_default_network(self, request: DownloadRequest) -> DownloadRequest:
        """Fill in the Settings network options where the request states none (`T-196`).

        **Applied at construction, which is what binding at queue time means** — the same
        sentence as the cookie browser below, and the same reason: `ARCHITECTURE.md` §8 freezes
        settings into the job, so a change afterwards belongs to the *next* download rather than
        to this one.

        **A value already on the request wins**, field by field. Nothing sets one today — a preset
        cannot carry these — but `REQ-031`'s per-job escape hatch is where one would come from,
        and a global default that overwrote a deliberate per-job answer would be the defect
        `_with_default_cookie_browser` states one method down.
        """
        if self._default_network is None:
            return request
        options = self._default_network()
        return replace(
            request,
            proxy=request.proxy if request.proxy is not None else options.proxy,
            rate_limit_bytes=(
                request.rate_limit_bytes
                if request.rate_limit_bytes is not None
                else options.rate_limit_bytes
            ),
            retries=request.retries if request.retries is not None else options.retries,
        )

    def _with_default_cookie_browser(self, request: DownloadRequest) -> DownloadRequest:
        """Fill in the Settings browser where the preset named none (`REQ-026`, `T197-R4`).

        **The preset wins**, because a preset naming a browser is a deliberate per-download
        choice and this is only a default. Applied at construction so the value is *in the job*,
        which is what binding at queue time means.
        """
        if request.cookies_from_browser or self._default_cookie_browser is None:
            return request
        default = self._default_cookie_browser()
        if not default:
            return request
        return replace(request, cookies_from_browser=default)

    def preset_for(self, row: Row) -> Preset:
        """`row`'s **effective** preset: its own if it has one, the batch's otherwise (`UX-004`).

        `None` on a row means *inherited*, not "no preset" — the row shows the batch's name so a
        blank cannot read as an absent choice.

        **`effective()`, not the raw row preset** (`T118-R6`). This returned `row.preset` verbatim,
        so an overridden MP3 row carried the registry's 192 kbps into `to_request` while the
        control on screen said 320 — a silent wrong download, and the same split `T-076` exists to
        prevent. The row test that was meant to cover this checked only `media_kind`, which both
        bitrates satisfy.
        """
        chosen = row.preset
        governing = self.effective(chosen) if isinstance(chosen, Preset) else self.selected_preset
        # **The row's own streams, over whichever preset governs** (`T-311`). The two are different
        # facts: the preset is *how* to download, the selection is *what*. Joining them here rather
        # than baking the selector into a preset at choosing time is what lets the batch control
        # keep reaching a row that has picked streams — and what stops picking streams from
        # discarding everything else the row was set up with.
        picked = row.format_selection
        if isinstance(picked, FormatSelection) and picked.is_complete:
            return preset_registry.with_format_selector(governing, picked.selector())
        return governing

    # --- closing ------------------------------------------------------------------------

    # Qt's override name, hence the camelCase: this is not a project naming choice.
    def done(self, result: int) -> None:
        """Every exit route funnels through here, so every exit route abandons the staging list.

        `T016-R2`: closing used to leave a never-returning worker alive and the pool permanently
        busy. Escape, the window button, `reject()` and `accept()` all reach `done()`, which is why
        the ownership lives here rather than on the Close button.

        **Unstaging, not withdrawing** (`T118-R1`). Nothing here was ever written, so there is no
        `CANCELLED` row to manufacture and no temporary row to delete — the probes are stopped and
        their processes reaped, and the queue is not told about work it never held. That is what
        lets this close immediately instead of holding the window open for a durable cancellation.

        **A commit in flight holds the close** (`T118-R3`). The dialog used to disappear while its
        rows were still being made durable, which left the outcome of the user's Add with nobody
        watching. Refused rather than queued: the window stays, `_on_committed` closes it, and a
        failed write leaves the input intact.
        """
        if self._saving:
            self._status.setText(
                "Still adding to the queue. This closes as soon as the rows are written."
            )
            self._refresh()
            return

        self._resolve_timer.stop()
        for row in self._staging.rows:
            if row.job_id is not None:
                self._manager.unstage(row.job_id)
                row.job_id = None

        self._thumbnails.close()
        super().done(result)

    # --- display ------------------------------------------------------------------------

    def refresh(self) -> None:
        """Redraw the list and re-enable exactly the controls that can do something.

        Public because `StagingModel` calls it after a row's preset changes, and because it is
        what the whole dialog means by "something moved". One method rather than a repaint and a
        separate enable pass: they read the same state, and two readers of one state is how a
        button ends up offering something the list says is impossible.

        **The rows are not rebuilt here any more** (`T118-R10`). The model says its contents
        changed and the view repaints the part of them it is showing; what used to happen was a
        loop over every row building a widget, which is why the cost grew with the paste rather
        than with the screen.
        """
        self._refresh()

    def _refresh(self) -> None:
        # **Re-entrancy guard** (`T118-R14`). The structural path commits the open editor from
        # inside `StagingModel.refresh`, and `setData` calls back here — so without this, one
        # reconcile re-enters the reset it is in the middle of. The outer call finishes the work,
        # so returning early loses nothing.
        #
        # *(This set the flag and never read it, which is a guard in name only. The mutation run
        # found it by failing to locate the branch it was trying to delete.)*
        if self._refreshing:
            return
        self._refreshing = True
        try:
            self._refresh_once()
        finally:
            self._refreshing = False

    def _refresh_once(self) -> None:
        # **Recomputed here, on every refresh, and never accumulated** (`REQ-022`, `T-114`). The
        # queue moves underneath an open dialog — a job finishes, a row is removed — so a marking
        # set once would go on saying *already in the queue* about a job that has left it. An
        # in-memory scan of a list the user can see the length of; see `QueuedUrls` for why it is
        # never a query (`T079-R2`).
        self._staging.mark_duplicates(self._queued_urls())

        # **A panel cannot outlive the row it belongs to** (`T-312`). While a panel was a row's
        # index widget Qt destroyed it with the row, so deleting the URL line took the open table
        # with it and nothing here had to notice. A page has no such owner: the panel went on
        # showing, for a row that no longer exists, and *Done* would have written a choice onto
        # nothing. Closed rather than kept, because there is nothing left to keep it for.
        expanded = self._expanded
        if expanded is not None and expanded not in self._staging.visible:
            self.close_panel(keep=False)

        visible = self._staging.visible
        # **By identity, not by row number** (`T118-R14`). A value-only refresh no longer resets
        # the model at all, so nothing needs restoring; a structural one may have moved or removed
        # the current row, and carrying a bare index across a changing set is how the selection
        # lands on somebody else's row.
        current = self._current_row()
        self._model.refresh()
        if current is not None:
            restored = next((i for i, row in enumerate(visible) if row is current), None)
            if restored is not None:
                self._list.setCurrentIndex(self._model.index(restored, 0))
        self._show_selector()

        if not self._saving:
            self._status.setText(summarise(visible))

        # **`_saving` covers the whole commit, and Add is disabled for all of it** (`T118-R3`).
        # It used to track only the retarget's *request*, so a second click scheduled a duplicate
        # commit for rows that were already being written.
        ready = bool(self._staging.committable())
        self._add_button.setEnabled(ready and not self._saving)
        self._retry_button.setEnabled(bool(self._staging.failed()) and not self._saving)

        # `T-076`: a bitrate applies only to a preset that converts audio. Disabled rather than
        # hidden, so the chain a keyboard walks does not change and the layout does not move.
        is_mp3 = self.selected_preset.audio_codec is AudioCodec.MP3
        self._bitrate_choice.setEnabled(is_mp3 and not self._saving)

    def commit_open_editor(self) -> bool:
        """Commit and close the row editor, if one is open. `True` if there was (`T118-R14`).

        Public because `StagingModel` calls it before a structural reset, and a test drives it to
        show the choice survives one. The delegate owns the editor, so it does the work.
        """
        delegate = self._list.itemDelegate()
        return delegate.commit_and_close_editor() if isinstance(delegate, RowDelegate) else False

    def _on_preset_changed(self) -> None:
        """A different preset may or may not convert audio, so the bitrate control follows it."""
        self._refresh()
        self._show_selector()

    def _show_selector(self) -> None:
        """Display what will actually be downloaded, **for the row in hand** (`REQ-009`, `T118-R8`).

        The bitrate is shown alongside the selector when the preset converts audio, because it is
        equally part of what will run and `REQ-009`'s promise is about that, not about the
        selector string specifically. It is omitted otherwise rather than shown as "n/a", which
        would put a number on screen for a download that ignores it.

        **This label follows the current row**, and falls back to the batch when no row is current.
        `REQ-009` asks for a selector a user can *learn the syntax from and then write their own*,
        which means it has to be selectable text they can copy — and a delegate paints pixels, not
        selectable text. The row draws its own selector so a mixed batch can be read at a glance;
        this is where the one in hand can be taken away.

        `T118-R8` was reported twice. The first time the row named a preset instead of a selector;
        the second time the row's selector was right-elided to nothing at a realistic width. The
        drawn line wraps now rather than eliding, and this label is the copyable half.
        """
        row = self._current_row()
        preset = self.preset_for(row) if row is not None else self.selected_preset
        selector = preset_registry.effective_selector(preset)
        scope = "This row" if row is not None else "Every row"
        text = f"{scope} · Format selector: {selector}"
        if preset.audio_codec is AudioCodec.MP3:
            text += f"  ·  {preset.audio_quality} kbps {preset.audio_codec.value.upper()}"
        self._selector_value.setText(text)

    def _current_row(self) -> Row | None:
        """The row the list has landed on, or `None` when nothing is current."""
        index = self._list.currentIndex()
        return self._row_at(index.row()) if index.isValid() else None
