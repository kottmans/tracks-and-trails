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
from typing import Any, Final, Protocol

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, QTimer
from PySide6.QtCore import QPersistentModelIndex as _PersistentIndex
from PySide6.QtGui import QAction, QPixmap
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
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.ui.row_delegate import (
    DETAIL_ROLE,
    EDIT_HINT,
    HEADLINE_ROLE,
    HUE_ROLE,
    INHERITED_TEXT,
    PRESET_CHOICES_ROLE,
    PRESET_ROLE,
    ROW_PRESET_NAME,
    SELECTOR_ROLE,
    STATE_ROLE,
    THUMBNAIL_URL_ROLE,
    RowDelegate,
)
from tracks_and_trails.ui.staging import Row, RowState, Staging, placeholder_hue, summarise
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

#: How a failed withdrawal announces itself. A prefix rather than a whole message, because the
#: URL and the reason belong in it and `NFR-005` forbids signalling the state any other way.
WITHDRAW_FAILED_PREFIX: Final = "Still queued:"

#: What each row state says, in words (`NFR-005`). Derived from the state rather than written
#: beside it, so a state cannot acquire a colour and no sentence.
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


def describe_kind(media: MediaInfo) -> str:
    """Whether this URL is one item or a playlist, and how big (`REQ-002`)."""
    if not media.is_playlist:
        return "Single item"
    if media.entry_count is None:
        return "Playlist"
    return f"Playlist ({media.entry_count} items)"


def describe_quality(preset: Preset) -> str:
    """The applicable quality for `preset`, or nothing when it has none.

    Omitted rather than shown as "n/a": a bitrate beside a video download would put a number on
    screen for something that ignores it, which is `_show_selector`'s reasoning applied per row.
    """
    if preset.audio_codec is not AudioCodec.MP3:
        return ""
    return f" · {preset.audio_quality} kbps {preset.audio_codec.value.upper()}"


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
    """
    source = "this row only" if isinstance(row.preset, Preset) else "following the batch"
    selector = preset_registry.effective_selector(effective)
    return f"{effective.name} — {source} · Format selector: {selector}{describe_quality(effective)}"


def headline_text(row: Row) -> str:
    """The row's first line: the extractor's title once there is one, else the pasted URL.

    Never empty. A row nobody can identify is worse than a long URL.
    """
    media = row.media
    return media.title if isinstance(media, MediaInfo) else row.url


def detail_text(row: Row) -> str:
    """The row's second line, without its state — the fields `REQ-002` names.

    **A failed row shows the extractor's words unchanged** (`NFR-006`). They are not folded into a
    sentence, because a sentence that contains them is not the same as them.
    """
    if row.state is RowState.FAILED:
        return row.message or "no reason was given"
    media = row.media
    if not isinstance(media, MediaInfo):
        return ""
    return " · ".join(
        (
            media.uploader or UNKNOWN_TEXT,
            format_duration(media.duration_seconds),
            describe_kind(media),
        )
    )


def selector_text(row: Row, effective: Preset | None) -> str:
    """The row's third line: what it will be downloaded as, spelled out (`T118-R8`, `REQ-009`)."""
    if effective is None or not isinstance(row.media, MediaInfo):
        return ""
    return f"Download as: {describe_preset(row, effective)}"


def row_text(row: Row, effective: Preset | None = None) -> str:
    """What one row reads as, whole: headline, detail and state, and what it downloads as.

    A module function rather than a method so the wording is asserted without a `QApplication`,
    and so the failure case cannot drift from the success case.

    **Composed from the very pieces the delegate's roles carry** (`T-119`), rather than written a
    second time beside them. The drawn row and this string are then the same sentence by
    construction — which is the property the old two-writers arrangement kept losing, most
    recently as `T118-R8`.
    """
    second = " — ".join(part for part in (detail_text(row), STATE_TEXT[row.state]) if part)
    tail = selector_text(row, effective)
    return f"{headline_text(row)}\n{second}" + (f"\n{tail}" if tail else "")


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
        return 0 if parent.isValid() else len(self._dialog.rows)

    def data(
        self, index: QModelIndex | _PersistentIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        rows = self._dialog.rows
        if not index.isValid() or not 0 <= index.row() < len(rows):
            return None
        row = rows[index.row()]
        effective = self._dialog.preset_for(row)

        if role == HEADLINE_ROLE:
            return headline_text(row)
        if role == DETAIL_ROLE:
            return detail_text(row)
        if role == STATE_ROLE:
            return STATE_TEXT[row.state]
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
        rows = self._dialog.rows
        if not index.isValid() or not 0 <= index.row() < len(rows):
            return False
        name = value if isinstance(value, str) else None
        rows[index.row()].preset = next(
            (preset for preset in self._dialog.presets if preset.name == name), None
        )
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
            return

        self._dialog.commit_open_editor()
        self.beginResetModel()
        self._shown = rows
        self.endResetModel()


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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._manager = manager
        self._jobs = jobs
        self._output_directory = output_directory
        self._presets = tuple(presets)
        #: Fetches, decodes and caches thumbnails, and is asked for one **only while painting**
        #: (`T-119`). The dialog no longer holds pixmaps: a row that scrolls out of view has its
        #: picture released by the cache's own bound, which a dict keyed by job id could not do.
        self._thumbnails = ThumbnailStore(
            loader=thumbnail_loader, cache_root=cache_root, parent=self
        )

        self._staging = Staging()
        #: A batch write is outstanding. Every control that could start a second one is disabled.
        self._saving = False
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
        layout.addWidget(self._urls)

        layout.addWidget(self._build_list())

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

        self._list = QListView(box)
        self._list.setObjectName("stagingList")
        self._list.setAccessibleName("The URLs you pasted, and what each one is")
        self._list.setAccessibleDescription(
            "Each line you pasted, with what it turned out to be. " + EDIT_HINT
        )
        self._list.setModel(self._model)
        self._list.setItemDelegate(RowDelegate(thumbnails=self._thumbnails, parent=self._list))
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
            self._add_button,
            self._close_button,
        ]

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

        The list and the model both index into `Staging.visible`, so this is the one place that
        turns a position into a row — an index carried on the item itself is what went stale when
        the count changed underneath it.
        """
        visible = self._staging.visible
        return visible[index] if 0 <= index < len(visible) else None

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
        committable = self._staging.committable()
        if not committable:
            self._status.setText(
                "Nothing has been read yet, so there is nothing to add. "
                "Paste a URL, or retry the ones that failed."
            )
            return

        # Entry order, which becomes `queue_position` order: the repository allocates `MAX + 1`
        # inside the insert transaction, so submitting in this order is what the pool will start
        # in (`T115-R1`).
        fresh = [(row, self._durable_job(row)) for row in committable]
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
            for job_id in self._committed:
                self._manager.admit(job_id)
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

    def _durable_job(self, row: Row) -> Job:
        """The queue job for a resolved row, carrying everything the probe learned.

        `title` and `thumbnail_url` come across from the staging probe rather than being left for
        the download session to rediscover (`T-117`): the row on screen already knows them, and a
        queue that showed a URL until its download started would be `UX-003` undone at the moment
        of committing.
        """
        media = row.media
        return Job(
            id=str(uuid.uuid4()),
            url=row.url,
            request=self._request_for(row),
            status=JobStatus.READY if isinstance(media, MediaInfo) else JobStatus.QUEUED,
            title=media.title if isinstance(media, MediaInfo) else None,
            thumbnail_url=media.thumbnail_url if isinstance(media, MediaInfo) else None,
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
