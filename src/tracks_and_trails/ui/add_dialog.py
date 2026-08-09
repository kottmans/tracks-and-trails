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
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import Any, Final, Protocol, cast

from PySide6.QtCore import QAbstractListModel, QEvent, QModelIndex, QSize, Qt, QTimer, Signal
from PySide6.QtCore import QPersistentModelIndex as _PersistentIndex
from PySide6.QtGui import QAction, QFontMetrics, QKeyEvent, QPalette, QPixmap, QResizeEvent
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
    DETAIL_ROLE,
    EDIT_HINT,
    EXPANDED_ROLE,
    FORMAT_PANEL_HEIGHT_ROLE,
    FORMATS_AVAILABLE_ROLE,
    HEADLINE_ROLE,
    HUE_ROLE,
    INHERITED_TEXT,
    JOB_ID_ROLE,
    MANAGE_PRESETS_DATA,
    OPTIONS_AVAILABLE_ROLE,
    OPTIONS_DATA,
    PRESET_CHOICES_ROLE,
    PRESET_INHERITABLE_ROLE,
    PRESET_ROLE,
    PRESETS_MANAGEABLE_ROLE,
    ROW_PRESET_NAME,
    SELECTOR_ROLE,
    STATE_ROLE,
    TEMPLATE_AVAILABLE_ROLE,
    TEMPLATE_DATA,
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
    "INHERITED_TEXT",
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

#: How many lines of URL the paste box asks for before it stops growing (`T-209`).
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

#: How a failed withdrawal announces itself. A prefix rather than a whole message, because the
#: URL and the reason belong in it and `NFR-005` forbids signalling the state any other way.
WITHDRAW_FAILED_PREFIX: Final = "Still queued:"

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
        #: What the third line may have to hold, from the catalogue the dialog was given.
        self._selectors = tuple(selectors)
        #: Cached because `sizeHint` is called on every layout pass and the answer searches for a
        #: wrap width. Dropped on a font or style change, which is exactly when it stops being
        #: true — `T118-R15` is this project's record of a width promise that held at one font.
        self._wanted: int | None = None

    # Qt's override names, hence the camelCase.
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

    # Qt's override name, hence the camelCase.
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
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
        # **Opaque, because the row is still painted underneath** (`T-210`). `setIndexWidget` puts
        # this widget over the item, but a `QWidget` paints nothing by default — so the delegate's
        # own anatomy showed through wherever the panel had no child: the thumbnail behind the
        # heading, and the row's *Download as* line behind the summary. Filling the background is
        # what makes "the row, opened" look like one thing instead of two stacked.
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

        # **The way out sits at the top** (`T-210`). `setIndexWidget` covers the row's own
        # disclosure while the panel is open, so the panel has to supply the control that closes
        # it — and a control at the *bottom* is the first thing to fall below the fold when the
        # panel is tall, which is exactly when a user most wants it. `Done` is still there for the
        # keyboard order and for the reader who works downward; this is the one that is always
        # visible, and it is drawn as the triangle it replaces.
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
        controls: list[QWidget] = []
        mode = self._table.mode_control
        if mode is not None:
            controls.append(mode)
        return [*controls, self._table.table, self._table.header, self._close]

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
        if role == THUMBNAIL_URL_ROLE:
            media = row.media
            return media.thumbnail_url if isinstance(media, MediaInfo) else None
        if role == PRESET_ROLE:
            own = row.preset
            return own.name if isinstance(own, Preset) else None
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
            return self._dialog.panel_height_for(row)
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
        own = row.preset
        if name is not None and isinstance(own, Preset) and own.name == name:
            # **The row's own chosen formats, re-selected** (`T-108`). `createEditor` offers a row's
            # non-catalogue preset as an entry so the control can show what the row actually picked;
            # choosing that entry must be a no-op, and the lookup below would instead find no preset
            # by that name and clear the format the user chose from the table. Compared by name
            # because that is what the control carries, and the name of a chosen selection *is* its
            # selector, so two rows can share one without either being the other's.
            self.dataChanged.emit(index, index)
            return True
        row.preset = next((preset for preset in self._dialog.presets if preset.name == name), None)
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
                self._dialog.relayout_panel()
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
        self._dialog.remount_panel()


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
        queued_urls: QueuedUrls | None = None,
        save_preset: PresetSink | None = None,
        manage_presets: Callable[[], None] | None = None,
        default_preset: str = "",
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
        self._output_directory = output_directory
        self._presets = tuple(presets)
        #: Whether a merge is possible at all on this installation (`REQ-024`, `P-13`).
        #:
        #: **Passed in rather than looked up here.** `find_ffmpeg` lives in `downloader/` and
        #: `app.py` already calls it once for the manager and the status bar; asking again here
        #: would be a second answer to one question, and the two could differ — `ARC-007`'s reason
        #: for the manager receiving a value rather than reading settings.
        self._ffmpeg_available = ffmpeg_available
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
        layout = QVBoxLayout(self)

        self._urls = QPlainTextEdit(self)
        self._urls.setObjectName("urlInput")
        self._urls.setAccessibleName("URLs to download, one per line")
        self._urls.setAccessibleDescription(
            "Paste or type one URL per line. Each line becomes a separate download, and each is "
            "read for its title and thumbnail before it can be queued."
        )
        self._urls.setPlaceholderText("https://…  (one URL per line)")
        self._urls.textChanged.connect(self._on_urls_changed)
        # **The box holds URLs; the list is what the user reads** (`T-209`). Qt split the dialog
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

        self._status = QLabel(self)
        self._status.setObjectName("statusMessage")
        self._status.setAccessibleName("Status")
        self._status.setWordWrap(True)
        # Selectable so the user can copy an extractor message into a search or a bug report. A
        # message kept verbatim (`NFR-006`) that cannot be copied is only half of the point.
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self._status.setText(summarise(()))
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
        self._manage_presets_button = QPushButton("&Manage presets…", self)
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
        self._list.viewport_resized.connect(self._on_list_resized)
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

        self._preset_choice = QComboBox(box)
        self._preset_choice.setObjectName("presetChoice")
        self._preset_choice.setAccessibleName("Download preset")
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
        layout.addWidget(self._preset_choice)

        # `T-076`, `REQ-010`. A property of the conversion, not a different preset — five MP3
        # presets would encode one parameter as five products, and the model already carries it
        # as `audio_quality`.
        self._bitrate_choice = QComboBox(box)
        self._bitrate_choice.setObjectName("audioBitrateChoice")
        self._bitrate_choice.setAccessibleName("MP3 bitrate")
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
        layout.addWidget(self._bitrate_choice)

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

        `T016-R4`'s lesson survives the rewrite: a control that can hold focus belongs here even
        when it is read-only. The list is focusable — it is how a keyboard reaches a row's menu.
        """
        return [
            self._urls,
            self._retry_button,
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

    def panel_height_for(self, row: Row) -> int:
        """How tall `row` must be drawn, because it is open. `0` when it is not.

        The panel's own `sizeHint`, asked of the widget rather than assumed: a constant here would
        be a second opinion about how tall a table is, and the first font change would make it the
        wrong one — `T118-R15` is this project's record of exactly that promise.

        **Bounded by what the list can actually show** (`T-209`). Unbounded, a playlist picker asked
        for its summary, eight entries and a *Done* button, the row was drawn taller than the list,
        and the bottom of it went below the fold — taking with it **the only pointer route out of
        the panel**, since `setIndexWidget` covers the row's own disclosure. `Esc` and `←` still
        worked, which is why nothing caught it: the keyboard was fine and the pointer had nothing.

        The panel's layout absorbs the difference by compressing the entry table, which is the one
        part of it that should give: the summary says which row this is and *Done* is the way out,
        so neither may be the thing that shrinks. `T-193`'s cap stays the **maximum** number of
        entries; this decides how many of them fit.
        """
        if row is not self._expanded or self._panel is None:
            return 0
        wanted = self._panel.sizeHint().height()
        available = self._list.viewport().height() - PANEL_VIEWPORT_MARGIN
        # **Never below the panel's own minimum.** The cap exists to keep *Done* reachable, so
        # shrinking past the height that shows *Done* would defeat it — and a list that has not been
        # laid out yet reports a viewport that means nothing, which is the trap `T193-R1` caught one
        # widget over. The floor makes both cases the same answer: show the panel's controls.
        return max(self._panel.minimumSizeHint().height(), min(wanted, available))

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

        # `Esc` puts the row's earlier format back, which is what *"choosing nothing"* means.
        before = row.preset if isinstance(row.preset, Preset) else None
        self._open_panel(row, build, undo=lambda: setattr(row, "preset", before))

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
        self._open_panel(row, build, undo=lambda: setattr(row, "entry_selection", before))

    def open_template_editor(self, row: Row) -> None:
        """Open `row` into `REQ-011`'s template editor and its live preview (`T-112`).

        **The preview is asked for as the panel opens**, not on the first keystroke: a field that
        shows a path only once you have typed into it makes the user prove the feature works before
        it tells them anything, and the interesting case — *what does the template I already have
        produce?* — is the one they arrived with.
        """
        template = self.preset_for(row).output_template

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
        request = preset_registry.to_request(
            preset_registry.with_output_template(self.preset_for(row), template or " "),
            url=row.url,
            output_directory=str(self._output_directory),
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
        if row is self._expanded:
            self.close_panel(keep=True)
            return
        self.open_playlist_picker(row)

    def _open_panel(
        self,
        row: Row,
        build: Callable[[], RowPanel],
        *,
        undo: Callable[[], None],
        commit: Callable[[], None] = lambda: None,
    ) -> None:
        """Mount one panel on `row`, closing whatever was open (`T-108`, `T-110`).

        **Any other open panel closes first, keeping its choice.** Two open panels would be two
        answers to which row is being looked at, and closing without keeping would silently discard
        a selection the user had already made.
        """
        if self._expanded is row:
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
        # **Mounted on the next turn, because Qt keeps index widgets and item editors in one map**
        # (`T108-R2`). This is reached from `StagingModel.setData`, which Qt calls from inside
        # `commitData` while the row's combo box is still open — and `setIndexWidget` on that index
        # *destroys the editor Qt is in the middle of using*. The delegate went on holding the dead
        # pointer, and the next structural reset called `commitData` on it: **libshiboken: Internal
        # C++ object already deleted.** Deferring by one turn lets the view finish closing the
        # editor first, which is the only ordering in which both can exist.
        QTimer.singleShot(0, self._mount_panel)

    def _mount_panel(self) -> None:
        """Put the panel on its row, once the editor that opened it is gone (`T108-R2`)."""
        row, panel = self._expanded, self._panel
        if row is None or panel is None:
            return
        index = self._index_of(row)
        if not index.isValid():
            # The row went away between the choice and this turn — a retype in the same breath.
            self.close_panel(keep=True)
            return
        self._list.setUniformItemSizes(False)
        # **Re-lay the items before handing Qt the widget** (`T-108`). `QListView` caches each
        # item's rectangle, and it sizes an index widget to the rectangle it believes in *at the
        # moment the widget is set*. Setting first and announcing afterwards gave the panel the
        # closed row's height — the table came out zero pixels tall inside a full-width panel, which
        # is `T107-R2`'s collapse arriving from the mounting side rather than the widget's.
        self._model.dataChanged.emit(index, index, [Qt.ItemDataRole.SizeHintRole])
        self._list.setIndexWidget(index, panel)
        # **Placed here, not left to the view's next paint** (`T-108`). `setIndexWidget` registers
        # the widget and defers its geometry to `updateEditorGeometries`, which runs on paint — so
        # until something repaints, the panel keeps its own minimum. Measured: **190x26 inside a row
        # whose `visualRect` was already 485x366**, which left the table zero pixels tall. That is
        # `T107-R2`'s collapse arriving from the mounting side, and the widget's own layout contract
        # cannot prevent it, because the widget was never given the size.
        #
        # Qt keeps ownership afterwards: scrolling and resizing re-place it through the same pass.
        # This only makes the *first* geometry true immediately rather than one paint later.
        panel.setGeometry(self._list.visualRect(index))
        self._list.scrollTo(index, QAbstractItemView.ScrollHint.EnsureVisible)
        for earlier, later in pairwise(panel.focus_chain()):
            self.setTabOrder(earlier, later)
        # **Focus lands where the panel says**, rather than on whatever this method knows how to
        # reach into. That is what lets a second kind of panel exist without this one learning
        # what it contains — `P-19`'s "one mechanism", made true rather than described.
        panel.initial_focus().setFocus(Qt.FocusReason.OtherFocusReason)

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
        if index.isValid():
            # `None` is how Qt is told to drop the widget, and it is what `QAbstractItemView`
            # documents; PySide's stub declares the parameter as `QWidget`, so the cast is a
            # narrowing of the *annotation* rather than of the behaviour.
            self._list.setIndexWidget(index, cast("QWidget", None))
            self._model.dataChanged.emit(index, index, [Qt.ItemDataRole.SizeHintRole])
        else:
            # The row went away underneath the panel — a retype, so its index is gone and Qt has
            # already discarded the widget with the row. Nothing to unset; the panel is dropped
            # with the reference above.
            panel.deleteLater()
        self._list.setUniformItemSizes(True)
        self.refresh()
        self._list.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_list_resized(self) -> None:
        """Re-measure the rows and re-place the open panel after the list changes height.

        **Only when something is open.** A closed row's height does not depend on the viewport, so
        a resize with nothing expanded costs one comparison.
        """
        if self._expanded is None or self._panel is None:
            return
        index = self._index_of(self._expanded)
        if index.isValid():
            self._model.dataChanged.emit(index, index, [Qt.ItemDataRole.SizeHintRole])
        self.relayout_panel()

    def relayout_panel(self) -> None:
        """Put the open panel back over its row, without remounting it (`T204-R4`).

        **Geometry only.** `remount_panel` exists for a *structural* reset, where Qt has forgotten
        the widget-to-index association entirely and `setIndexWidget` must be called again. A
        value-only `dataChanged` keeps the association and merely re-measures the row, so calling
        `setIndexWidget` here would tear down and rebuild a live panel — and the picker holds the
        user's half-made selection.

        Silent when nothing is open, because every value refresh reaches this and most of them have
        no panel to move.
        """
        row, panel = self._expanded, self._panel
        if row is None or panel is None:
            return

        def restore() -> None:
            # **Read after Qt has re-laid the view out, not during the emit.** `dataChanged` is
            # delivered *before* the view re-measures, so `visualRect` still answers the old
            # geometry — and stamping that onto the panel is worse than leaving it alone: the first
            # version of this fix wrote a stale, sometimes empty, rectangle over a live panel and
            # **made it vanish on open**. Deferred by a turn, which is the ordering `T108-R2`
            # already established one widget over.
            if row is not self._expanded or panel is not self._panel:
                return
            index = self._index_of(row)
            if not index.isValid():
                return
            rect = self._list.visualRect(index)
            # **An empty rectangle is not an answer.** A row scrolled out of view, or measured
            # before layout, reports one — and it would hide the panel rather than move it.
            if rect.isEmpty():
                return
            panel.setGeometry(rect)

        QTimer.singleShot(0, restore)

    def remount_panel(self) -> None:
        """Put the open panel back on its row after a model reset, or close it if the row is gone.

        **`T108-R2`.** A structural reset — adding a URL, removing one, retyping, reordering —
        drops the index widget, and the panel was left pointing at a row it was no longer mounted
        on: the row stayed tall and blank, and `open_format_table` refused to reopen it because
        `_expanded is row` was still true. Every one of those is an ordinary thing to do while
        choosing a format, not a teardown path.

        **By row identity, never by row number** (`T118-R14`'s rule). Reconciling A/B to B/A leaves
        row 0 valid and meaning a *different URL*, so remounting by position would hang one row's
        format table under another's — the same class of defect as writing a chosen preset to the
        wrong row, and with the same consequence.

        A row that is gone takes its panel with it, **keeping** what was chosen: the selection was
        already written to the row when it was made, and the row itself no longer exists.
        """
        row, panel = self._expanded, self._panel
        if row is None or panel is None:
            return
        index = self._index_of(row)
        if not index.isValid():
            self.close_panel(keep=True)
            return
        self._list.setUniformItemSizes(False)
        self._list.setIndexWidget(index, panel)
        panel.setGeometry(self._list.visualRect(index))

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
        """A row was taken into the selection. Close once the selection names a download.

        `docs/UX_SPEC.md` §4: *"`Enter` chooses the current format and closes"*. In **one format**
        mode that is the first press, exactly as written. In **video + audio** it cannot be, because
        one press has filled one slot — so the rule is *closes when the selection is complete*,
        which is the same sentence for the mode the spec was describing.
        """
        panel = self.open_format_panel
        if panel is not None and panel.table.selection.is_complete:
            self.close_panel(keep=True)

    def _on_selection_changed(self, selection: object) -> None:
        """Write the chosen formats onto the row, as its own preset (`REQ-008`, `REQ-009`).

        **A custom preset, through `custom_preset`, so the selector reaches the request unchanged.**
        The row's third line then reads whatever `format_text.format_name` says about it — which for
        a selector no built-in describes is the literal, and that is `UX_SPEC` §5's rule honoured by
        *asking* the shared naming rule rather than by writing the selector out here (`T140-R3`,
        `T126-R2`, `T-159` were all this same defect).

        An incomplete selection writes nothing: half a pair is not a download, and `custom_preset`
        would be handed `137` for a merge the user has not finished stating.
        """
        row = self._expanded
        if row is None or not isinstance(selection, FormatSelection):
            return
        if not selection.is_complete:
            return
        selector = selection.selector()
        row.preset = preset_registry.custom_preset(selector, name=selector)
        # **The statement, kept beside the selector it produced** — see `Row.format_selection`.
        # `REQ-024`'s refusal needs to know a merge was *chosen*, and reading that back out of
        # `137+140` means scanning for a `+`, which is `T-061`'s defect returning by the front door.
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

    def _show_row_menu(self, position: Any) -> None:
        """Retry or remove one row. **A context menu, reachable from the keyboard.**

        `CustomContextMenu` rather than `contextMenuEvent`, for the reason `T-086`'s file actions
        use it: the menu key and Shift+F10 both raise it, so the actions are not mouse-only
        (`NFR-005`).
        """
        clicked = self._list.indexAt(position)
        row = self._row_at(clicked.row()) if clicked.isValid() else None
        if row is None:
            return

        menu = QMenu(self._list)
        if row.state is RowState.FAILED:
            retry = QAction("Read this URL again", menu)
            retry.triggered.connect(lambda: self._retry_row(row))
            menu.addAction(retry)
        if clicked.flags() & _EDITABLE:
            # **The same editor the keyboard reaches** (`T118-R9`), offered here so the route is
            # discoverable rather than only documented. Both go through `edit_row`.
            choose = QAction("Choose a format for this URL…", menu)
            choose.triggered.connect(lambda: self.edit_row(clicked.row()))
            menu.addAction(choose)
        remove = QAction("Remove this URL", menu)
        remove.triggered.connect(lambda: self.remove_row(row))
        menu.addAction(remove)
        menu.exec(self._list.viewport().mapToGlobal(position))

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
                request=preset_registry.to_request(
                    self.preset_for(row), url=entry.url, output_directory=str(directory)
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
        return preset_registry.to_request(
            self.preset_for(row), url=row.url, output_directory=str(self._output_directory)
        )

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
        return self.effective(chosen) if isinstance(chosen, Preset) else self.selected_preset

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
