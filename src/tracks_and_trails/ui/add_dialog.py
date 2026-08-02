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

**A row is persisted before it is probed** (`REQ-012`), because the manager works in job ids. So a
line that fails, or that the user takes away, does have a row on disk — and `UX-003`'s promise is
that it never becomes *queued* work. `done()` withdraws every such row and refuses to close until
those cancellations are durable, which is `T016-R1` generalised from one probe to a batch.

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
"""

import uuid
from collections.abc import Callable, Sequence
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import Any, Final, Protocol

from PySide6.QtCore import QObject, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
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
from tracks_and_trails.downloader.protocol import SessionKind
from tracks_and_trails.ui.staging import Row, RowState, Staging, placeholder_hue, summarise

#: The size a row's thumbnail is drawn at. A fixed box rather than the image's own size, so a
#: 1920-wide thumbnail does not resize the dialog around it.
THUMBNAIL_SIZE: Final = (96, 54)

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


class ThumbnailLoader(Protocol):
    """Fetches thumbnail bytes without blocking the GUI thread.

    Injected rather than constructed inline so a test can hand over bytes without a network. The
    real one is `NetworkThumbnailLoader`; nothing in the dialog knows the difference.
    """

    def load(self, url: str, done: Callable[[bytes | None], None]) -> None: ...

    def cancel(self) -> None: ...


class NetworkThumbnailLoader(QObject):
    """Fetches thumbnails over HTTP, one request at a time per dialog."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        from PySide6.QtNetwork import QNetworkAccessManager

        self._network = QNetworkAccessManager(self)
        self._replies: list[Any] = []

    def load(self, url: str, done: Callable[[bytes | None], None]) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtNetwork import QNetworkRequest

        reply = self._network.get(QNetworkRequest(QUrl(url)))
        self._replies.append(reply)

        def finished() -> None:
            if reply in self._replies:
                self._replies.remove(reply)
            data = (
                bytes(reply.readAll().data())
                if reply.error() == reply.NetworkError.NoError
                else None
            )
            reply.deleteLater()
            done(data)

        reply.finished.connect(finished)

    def cancel(self) -> None:
        for reply in list(self._replies):
            reply.abort()
        self._replies.clear()


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


def row_text(row: Row) -> str:
    """What one row reads as, headline and detail (`REQ-002`, `NFR-005`).

    A module function rather than a method so the wording is asserted without a `QApplication`,
    and so the failure case cannot drift from the success case.

    **A failed row shows the extractor's words unchanged** (`NFR-006`). They are not folded into a
    sentence, because a sentence that contains them is not the same as them.
    """
    state = STATE_TEXT[row.state]
    if row.state is RowState.FAILED:
        return f"{row.url}\n{state} — {row.message or 'no reason was given'}"

    media = row.media
    if not isinstance(media, MediaInfo):
        return f"{row.url}\n{state}"

    details = " · ".join(
        (
            media.uploader or UNKNOWN_TEXT,
            format_duration(media.duration_seconds),
            describe_kind(media),
        )
    )
    return f"{media.title}\n{details} — {state}"


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
        resolve_delay_ms: int = DEFAULT_RESOLVE_DELAY_MS,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._manager = manager
        self._jobs = jobs
        self._output_directory = output_directory
        self._presets = tuple(presets)
        self._thumbnails: ThumbnailLoader = thumbnail_loader or NetworkThumbnailLoader(self)

        self._staging = Staging()
        #: Decoded thumbnails, by job id. Held here rather than on `Row` so `staging.py` stays
        #: Qt-free — a pixmap is the one thing in a row that cannot cross that line.
        self._pixmaps: dict[str, QPixmap] = {}
        #: A batch write is outstanding. Every control that could start a second one is disabled.
        self._saving = False
        #: Jobs committed by `add_to_queue`, in the order they will be admitted.
        self._committed: tuple[str, ...] = ()
        #: Retargets still settling before the batch can be admitted as one decision (`T115-R1`).
        self._retargets_pending = 0
        self._retarget_failure: str | None = None

        #: Jobs this dialog has withdrawn, until their `CANCELLED` is durable (`T016-R1`).
        #:
        #: A withdrawal is the Critical consequence in reverse: the row exists, the user has taken
        #: the URL away, and until the cancellation actually reaches disk that row is still live
        #: work a restart would pick up. So the dialog owns the outcome instead of firing
        #: `cancel()` and hoping — it refuses to close or queue while one is outstanding.
        self._withdrawing: dict[str, str] = {}
        self._withdraw_error: str | None = None
        #: A close asked for and refused because it created a withdrawal. Holds the result code so
        #: the dialog finishes that exact close once the cancellation lands, rather than making
        #: the user press Close again to achieve nothing but waiting.
        self._closing_with: int | None = None

        self._resolve_timer = QTimer(self)
        self._resolve_timer.setSingleShot(True)
        self._resolve_timer.setInterval(max(resolve_delay_ms, 0))
        self._resolve_timer.timeout.connect(self.resolve)

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

        self._list = QListWidget(box)
        self._list.setObjectName("stagingList")
        self._list.setAccessibleName("The URLs you pasted, and what each one is")
        self._list.setIconSize(QSize(*THUMBNAIL_SIZE))
        self._list.setUniformItemSizes(True)
        # **A plain item list, not a widget per row.** A paste is unbounded — this application is
        # public and cannot assume twenty — and one `QWidget` per row makes five hundred URLs a
        # five-hundred-widget layout pass on the GUI thread (`NFR-001`). Items carry an icon and
        # two lines of text, which is every field `REQ-002` names for a row at this stage.
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_row_menu)
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
        self._manager.start_rejected.connect(self._on_start_rejected)
        self._manager.persistence_failed.connect(self._on_persistence_failed)
        self._manager.job_removed.connect(self._on_job_removed)

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

    @property
    def withdrawing(self) -> tuple[str, ...]:
        return tuple(self._withdrawing)

    @property
    def withdraw_failed(self) -> str | None:
        return self._withdraw_error

    def status_text(self) -> str:
        """What the dialog is telling the user. A method, as it has always been."""
        return self._status.text()

    @property
    def selected_preset(self) -> Preset:
        preset = self._presets[max(self._preset_choice.currentIndex(), 0)]
        if preset.audio_codec is not AudioCodec.MP3:
            return preset
        return preset_registry.with_audio_quality(preset, self.selected_bitrate)

    @property
    def selected_bitrate(self) -> str:
        return str(self._bitrate_choice.currentData())

    def thumbnail_for(self, row: Row) -> QPixmap | None:
        """The decoded thumbnail for `row`, or `None` if none has arrived."""
        return self._pixmaps.get(row.job_id or "")

    # --- resolving --------------------------------------------------------------------

    def _on_urls_changed(self) -> None:
        """Restart the debounce. **Nothing is started from a keystroke.**

        A probe per character would spawn an interpreter per character (`ARC-002`). Restarting the
        timer means a paste resolves once, and a URL typed by hand resolves once the typing stops.
        """
        self._resolve_timer.start()
        self._refresh()

    def resolve(self) -> None:
        """Reconcile the rows with what is entered, and start what has not been started.

        Public so a test drives it directly rather than waiting on wall-clock time — the timer
        calls exactly this and nothing else, so the tested path is the real one.

        **A superseded row's job is withdrawn here**, not left to `done()`: the user has taken the
        line away, and until its cancellation is durable that row is live work a restart would run
        (`T016-R1`).
        """
        self._resolve_timer.stop()
        if self._saving:
            # A batch write is already outstanding. Its callback resolves again, so nothing is
            # lost by returning — and starting a second write would create a second job for lines
            # the first one is already storing.
            return

        before = {row.job_id for row in self._staging.rows if row.state is RowState.SUPERSEDED}
        self._staging.reconcile(split_urls(self._urls.toPlainText()))
        for row in self._staging.rows:
            newly_gone = (
                row.state is RowState.SUPERSEDED
                and row.job_id is not None
                and row.job_id not in before
                and row.job_id not in self._withdrawing
            )
            if newly_gone:
                assert row.job_id is not None
                self._withdraw(row.job_id, row.url)

        pending = self._staging.pending()
        if not pending:
            self._refresh()
            return

        fresh = {row: self._new_job(row.url) for row in pending}
        for row in pending:
            row.state = RowState.SAVING
        self._saving = True
        self._refresh()
        self._jobs.submit(
            list(fresh.values()),
            lambda error: self._on_rows_saved(fresh, error),
        )

    def _on_rows_saved(self, fresh: dict[Row, Job], error: str | None) -> None:
        """The rows are stored, or they are not. Only then is a worker asked for anything.

        `REQ-012`'s order, and `T016-R1`'s ownership: a row whose line went away while the write
        was in flight is withdrawn rather than left durably `QUEUED`, where whatever runs the
        queue next would download a URL the user had already taken back.
        """
        self._saving = False
        if error is not None:
            for row in fresh:
                if row.state is RowState.SAVING:
                    row.state = RowState.FAILED
                    row.message = error
            self._status.setText(f"Nothing was saved, so nothing was read. {error}")
            self._refresh()
            return

        for row, job in fresh.items():
            row.job_id = job.id
            if row.state is RowState.SUPERSEDED:
                self._withdraw(job.id, row.url)
                continue
            self._start_probe(row)
        self._refresh()

    def _start_probe(self, row: Row) -> None:
        """Ask for a probe session, and record what happens.

        **`admit`, not `start`** (`T-116`). `start()` raises when the probe lane is full, which a
        paste of twenty will reach immediately; admission expresses durable intent and the lane
        drains in `queue_position` order. The refusal path stays for the errors that are still
        real — a vanished row, or a state the machine will not move from.
        """
        if row.job_id is None:
            return
        try:
            self._manager.admit(row.job_id, SessionKind.PROBE)
        except (RuntimeError, ValueError) as refusal:
            row.state = RowState.FAILED
            row.message = str(refusal)
            return
        # **`WAITING`, not `PROBING`** (`T-116`). `admit` expresses intent; the lane decides when.
        # Marking the row as being read here said five hundred pasted URLs were all in flight at
        # once, when four were. `_on_job_changed` promotes it when the manager actually starts it.
        row.state = RowState.WAITING

    def retry_failed(self) -> None:
        """Read the failed URLs again (`UX-003`).

        A timeout costs a button press rather than the paste. The old job is withdrawn and the row
        goes back to `PENDING` with a **new** job rather than being restarted in place: its
        existing row may be `FAILED` on disk, and `ARC-004` has no edge back to `QUEUED` that does
        not go through a retry the queue owns.
        """
        failed = self._staging.failed()
        if not failed:
            return
        for row in failed:
            if row.job_id is not None:
                self._withdraw(row.job_id, row.url)
                self._pixmaps.pop(row.job_id, None)
            row.job_id = None
            row.message = None
            row.state = RowState.PENDING
        self.resolve()

    def remove_row(self, row: Row) -> None:
        """Take one line out of the batch without editing the box.

        The row is superseded and its job withdrawn, exactly as editing the line away would do —
        one route, one set of consequences.
        """
        if row.state is RowState.SUPERSEDED:
            return
        remaining = [other.url for other in self._staging.visible if other is not row]
        row.state = RowState.SUPERSEDED
        if row.job_id is not None and row.job_id not in self._withdrawing:
            self._withdraw(row.job_id, row.url)
        # The box is the source of truth for what is entered, so it changes too. Blocked so the
        # edit does not restart the debounce and reconcile against a list already correct.
        self._urls.blockSignals(True)
        self._urls.setPlainText("\n".join(remaining))
        self._urls.blockSignals(False)
        self._refresh()

    def _show_row_menu(self, position: Any) -> None:
        """Retry or remove one row. **A context menu, reachable from the keyboard.**

        `CustomContextMenu` rather than `contextMenuEvent`, for the reason `T-086`'s file actions
        use it: the menu key and Shift+F10 both raise it, so the actions are not mouse-only
        (`NFR-005`).
        """
        item = self._list.itemAt(position)
        if item is None:
            return
        row = self._row_for_item(item)
        if row is None:
            return

        menu = QMenu(self._list)
        if row.state is RowState.FAILED:
            retry = QAction("Read this URL again", menu)
            retry.triggered.connect(lambda: self._retry_row(row))
            menu.addAction(retry)
        remove = QAction("Remove this URL", menu)
        remove.triggered.connect(lambda: self.remove_row(row))
        menu.addAction(remove)
        menu.exec(self._list.viewport().mapToGlobal(position))

    def _retry_row(self, row: Row) -> None:
        if row.state is not RowState.FAILED:
            return
        if row.job_id is not None:
            self._withdraw(row.job_id, row.url)
            self._pixmaps.pop(row.job_id, None)
        row.job_id = None
        row.message = None
        row.state = RowState.PENDING
        self.resolve()

    def _row_for_item(self, item: QListWidgetItem) -> Row | None:
        index = item.data(Qt.ItemDataRole.UserRole)
        visible = self._staging.visible
        if not isinstance(index, int) or not 0 <= index < len(visible):
            return None
        return visible[index]

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
        self._load_thumbnail(row, media)
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

    def _on_job_removed(self, job_id: str) -> None:
        """A withdrawal landed. **Durable at last**, which is what the dialog was waiting for.

        `job_removed` is emitted from the delete's own callback, so seeing it here means the row
        really is gone from disk rather than merely asked to go (`T016-R3`, `T016-R1`).
        """
        if job_id not in self._withdrawing:
            return
        del self._withdrawing[job_id]
        if not self._withdrawing:
            self._withdraw_error = None
            if self._status.text().startswith(WITHDRAW_FAILED_PREFIX):
                self._status.setText(summarise(self._staging.visible))
        self._refresh()
        self._finish_closing()

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

    def _on_persistence_failed(self, job_id: str, reason: str) -> None:
        """A withdrawal that could not be written is the Critical consequence, not a detail.

        Until it lands, the row the user took away is still queued work a restart would run
        (`T016-R1`). The dialog says so and refuses to close or add until it is retried
        successfully, because closing on it silently is exactly the outcome the finding is about.
        """
        if job_id not in self._withdrawing:
            return
        self._withdraw_error = reason
        self._status.setText(
            f"{WITHDRAW_FAILED_PREFIX} {self._withdrawing[job_id]} is still in the queue "
            f"because it could not be withdrawn: {reason} "
            "Press Close again to retry; the queue is not safe to leave until it succeeds."
        )
        self._refresh()

    def _withdraw(self, job_id: str, url: str) -> None:
        """Take a row this dialog wrote out of the queue, and own the outcome.

        **`remove`, not `cancel`** — and this reverses what `T016-R1` chose, deliberately.

        That ruling kept a withdrawn row as `CANCELLED` rather than deleting it, on the reasoning
        that it was "an honest record of something asked for and withdrawn". It was: the user had
        pressed *Probe* on that URL, so the row recorded an intent they really had. `UX-003`
        removes that intent — a row is written because the manager works in job ids and a probe
        needs one, not because the user committed to anything by pasting. A queue full of
        `CANCELLED` rows for URLs somebody typed and thought better of is not a record, it is
        litter.

        It is also the only route that works. `ARC-004` has `FAILED → QUEUED` and nothing else, so
        cancelling a row whose probe failed raises `IllegalTransitionError` — the exact case
        `UX-003` says must not reach the queue. A rule needing two disposal routes, one of which
        is unreachable for the commonest case, is the wrong rule.

        `remove` cancels a live session first and deletes only once it has ended, so the
        `T016-R2` guarantee is unchanged: nothing is stranded and no worker outlives the dialog.
        """
        self._withdrawing[job_id] = url
        self._manager.remove(job_id)

    def retry_withdrawals(self) -> None:
        """Re-issue every outstanding cancellation. Reached by pressing Close again.

        **Only once a failure has been reported.** A cancellation that is merely slow is already
        on its way, and re-issuing it would ask the manager to cancel a job its own pending write
        has already moved to `CANCELLED`. Waiting is the correct answer to "not finished yet";
        retrying is the correct answer to "it failed".
        """
        if self._withdraw_error is None:
            self._status.setText(
                f"{WITHDRAW_FAILED_PREFIX} still withdrawing "
                f"{', '.join(self._withdrawing.values())} from the queue. One moment."
            )
            self._refresh()
            return
        self._withdraw_error = None
        self._status.setText("Retrying the withdrawal …")
        for job_id in list(self._withdrawing):
            self._manager.remove(job_id)
        self._refresh()

    # --- queueing -----------------------------------------------------------------------

    def add_to_queue(self) -> None:
        """Commit the rows that resolved, and only those (`UX-003`, `REQ-012`).

        **The count is what resolved, not what was pasted.** A URL that would not read never
        becomes queued work; it stays on screen with its message and its retry.

        The rows are already on disk — they had to be, to be probed — so this is a retarget
        followed by one admission rather than a write. `T-075`: the request that runs is the one
        selected **now**, not whichever preset happened to be current when the row was saved.
        """
        if self._saving or self._withdrawing:
            if self._withdrawing:
                self._status.setText(
                    f"{WITHDRAW_FAILED_PREFIX} a withdrawn URL is still in the queue. "
                    "Press Close to retry before adding more."
                )
            return
        committable = self._staging.committable()
        if not committable:
            self._status.setText(
                "Nothing has been read yet, so there is nothing to add. "
                "Paste a URL, or retry the ones that failed."
            )
            return

        # **Every unresolved row is withdrawn as part of committing** (`UX-003`). Leaving them
        # would put rows in the database that the queue never runs and the dialog has forgotten.
        for job_id in self._staging.unresolved_job_ids():
            if job_id not in self._withdrawing:
                row = self._staging.for_job(job_id)
                self._withdraw(job_id, row.url if row is not None else job_id)

        self._committed = tuple(row.job_id for row in committable if row.job_id is not None)
        self._retargets_pending = len(self._committed)
        self._retarget_failure = None
        self._status.setText(f"Adding {len(self._committed)} to the queue …")
        self._refresh()

        for row in committable:
            if row.job_id is None:
                continue
            self._manager.retarget(
                row.job_id,
                self._request_for(row.url),
                then=self._on_retarget_settled,
                otherwise=self._on_retarget_failed,
            )

    def _on_retarget_settled(self) -> None:
        self._retargets_pending -= 1
        self._admit_when_ready()

    def _on_retarget_failed(self, reason: str) -> None:
        """`T-075`: a row whose request could not be stored is not started with the old one."""
        self._retarget_failure = reason
        self._retargets_pending -= 1
        self._admit_when_ready()

    def _admit_when_ready(self) -> None:
        """Admit the whole batch **once**, in durable queue order (`T115-R1`).

        Admitting each row as its own retarget settled would let a later `queue_position` take a
        slot the head of the queue was still waiting for — with a pool of one, the row the user
        sees at the top waits while the second one downloads. `T-081` establishes that the table
        and the scheduler agree, and an asynchronous prerequisite does not get to suspend that.

        The order is the order the rows were written in, which is `queue_position` order:
        positions are allocated `MAX + 1` inside the insert transaction, and the rows were
        submitted in entry order. Reading them back to sort would put a database read in front of
        a GUI callback for an ordering the writes already fixed (`ARC-005`).
        """
        if self._retargets_pending > 0:
            return
        if self._retarget_failure is not None:
            self._status.setText(
                f"Your format choice could not be saved, so nothing was started: "
                f"{self._retarget_failure} The URLs are still here; press Add to queue again."
            )
            self._committed = ()
            self._refresh()
            return

        refusal: str | None = None
        try:
            for job_id in self._committed:
                self._manager.admit(job_id)
        except (RuntimeError, ValueError) as error:
            refusal = str(error)

        if refusal is not None:
            self._status.setText(
                f"Queued, but the downloads did not start: {refusal} "
                "They stay in the queue and can be started from there."
            )
            self._refresh()
            return
        self.accept()

    def _request_for(self, url: str) -> DownloadRequest:
        """The request the **currently selected** preset would download `url` with (`T-075`).

        One place builds a request, so "what the user chose" cannot mean two different things in
        two code paths — which is the shape the preset defect had.
        """
        return preset_registry.to_request(
            self.selected_preset, url=url, output_directory=str(self._output_directory)
        )

    def _new_job(self, url: str) -> Job:
        """A `QUEUED` job for `url`, with **no** queue position.

        The position is allocated by the writer, inside the same transaction as the insert
        (`ARC-005`). Reading `MAX(queue_position)` here would be both a GUI-thread database call
        and a guess against every other writer.
        """
        return Job(
            id=str(uuid.uuid4()),
            url=url,
            request=self._request_for(url),
            status=JobStatus.QUEUED,
            created_at=datetime.now().astimezone(),
        )

    # --- closing ------------------------------------------------------------------------

    # Qt's override name, hence the camelCase: this is not a project naming choice.
    def done(self, result: int) -> None:
        """Every exit route funnels through here, so every exit route abandons the batch.

        `T016-R2`: closing used to leave a never-returning worker alive and the pool permanently
        busy. Escape, the window button, `reject()` and `accept()` all reach `done()`, which is why
        the ownership lives here rather than on the Close button.

        **A row that has been committed is not withdrawn.** Its job is the queue's now, and
        `_admit_when_ready` may have just started it downloading.

        **The close that *creates* a withdrawal is refused too** (`T016-R1`). The first correction
        checked `_withdrawing` on the way in and then, four lines later, retired a started probe —
        which populates it — and carried straight on. So the dialog went invisible with a
        cancellation that had not been written: a crash in that window brings the disowned URL back
        as live work. The check therefore happens **after** the retirement as well as before it.
        """
        if self._withdrawing:
            self._closing_with = result
            self.retry_withdrawals()
            return

        self._resolve_timer.stop()
        committed = set(self._committed)
        # **Every job written, not only the unresolvable ones.** A `READY` row nobody committed is
        # the case that looks like success and is not: closing on it leaves a download in the
        # queue that the user never added (`UX-003`).
        for job_id in self._staging.written_job_ids():
            if job_id not in committed and job_id not in self._withdrawing:
                row = self._staging.for_job(job_id)
                self._withdraw(job_id, row.url if row is not None else job_id)

        if self._withdrawing:
            # Created by the loop above. The dialog stays up until the cancellations are durable
            # and then finishes this same close by itself — the user asked once.
            self._closing_with = result
            self._status.setText(
                f"{WITHDRAW_FAILED_PREFIX} {', '.join(self._withdrawing.values())} is still in "
                "the queue until its withdrawal is written. This closes as soon as it is."
            )
            self._refresh()
            return

        self._thumbnails.cancel()
        super().done(result)

    def _finish_closing(self) -> None:
        """Complete a close that was held open by a withdrawal, now that they have all landed."""
        result = self._closing_with
        if result is None or self._withdrawing:
            return
        self._closing_with = None
        self._thumbnails.cancel()
        super().done(result)

    # --- display ------------------------------------------------------------------------

    def _load_thumbnail(self, row: Row, media: MediaInfo) -> None:
        """Fetch the picture, if the site named one. The row is already drawn either way."""
        if not media.thumbnail_url or row.job_id is None:
            return
        url = media.thumbnail_url
        job_id = row.job_id

        def delivered(data: bytes | None) -> None:
            # Guards a reply that arrives after the row went away: the loader is asked to cancel,
            # but a fetch already in flight can still land.
            if data is None or self._staging.for_job(job_id) is not row:
                return
            if row.state is RowState.SUPERSEDED:
                return
            pixmap = QPixmap()
            if not pixmap.loadFromData(data):
                # Undecodable bytes and a failed fetch are the same thing to a user — no picture —
                # and neither is worth reporting as an error. The derived tile stays.
                return
            self._pixmaps[job_id] = pixmap
            self._refresh()

        self._thumbnails.load(url, delivered)

    def _tile_for(self, row: Row) -> QIcon:
        """The row's picture, or the tile derived from its URL until one arrives (`UX-003`).

        Never an empty box. A column of empty wells reads as a broken application, and it reads
        worse the more URLs are pasted — which is the case this design is for.
        """
        existing = self._pixmaps.get(row.job_id or "")
        if existing is not None:
            return QIcon(existing)

        width, height = THUMBNAIL_SIZE
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor.fromHsv(placeholder_hue(row.url), 90, 110))
        painter = QPainter(pixmap)
        painter.setPen(QColor.fromHsv(placeholder_hue(row.url), 60, 190))
        painter.drawRect(0, 0, width - 1, height - 1)
        painter.end()
        return QIcon(pixmap)

    def _refresh(self) -> None:
        """Redraw the list and re-enable exactly the controls that can do something.

        One method rather than a repaint and a separate enable pass: they read the same state, and
        two readers of one state is how a button ends up offering something the list says is
        impossible.
        """
        visible = self._staging.visible
        # `setUpdatesEnabled` around the rebuild, so a paste of five hundred is one paint rather
        # than five hundred (`NFR-001`).
        self._list.setUpdatesEnabled(False)
        while self._list.count() > len(visible):
            self._list.takeItem(self._list.count() - 1)
        while self._list.count() < len(visible):
            self._list.addItem(QListWidgetItem())
        for index, row in enumerate(visible):
            item = self._list.item(index)
            item.setText(row_text(row))
            item.setIcon(self._tile_for(row))
            item.setData(Qt.ItemDataRole.UserRole, index)
            # Everything a sighted user reads from the row, for a screen reader (`NFR-005`).
            item.setData(Qt.ItemDataRole.AccessibleTextRole, row_text(row).replace("\n", ". "))
        self._list.setUpdatesEnabled(True)

        if not self._status.text().startswith(WITHDRAW_FAILED_PREFIX):
            self._status.setText(summarise(visible))

        stuck = bool(self._withdrawing)
        ready = bool(self._staging.committable())
        self._add_button.setEnabled(ready and not self._saving and not stuck)
        self._retry_button.setEnabled(
            bool(self._staging.failed()) and not self._saving and not stuck
        )
        # `T-076`: a bitrate applies only to a preset that converts audio. Disabled rather than
        # hidden, so the chain a keyboard walks does not change and the layout does not move.
        is_mp3 = self.selected_preset.audio_codec is AudioCodec.MP3
        self._bitrate_choice.setEnabled(is_mp3 and not self._saving)

    def _on_preset_changed(self) -> None:
        """A different preset may or may not convert audio, so the bitrate control follows it."""
        self._refresh()
        self._show_selector()

    def _show_selector(self) -> None:
        """Display what the chosen preset actually downloads with (`REQ-009`).

        The bitrate is shown alongside the selector when the preset converts audio, because it is
        equally part of what will run and `REQ-009`'s promise is about that, not about the
        selector string specifically. It is omitted otherwise rather than shown as "n/a", which
        would put a number on screen for a download that ignores it.
        """
        preset = self.selected_preset
        selector = preset_registry.effective_selector(preset)
        text = f"Format selector: {selector}"
        if preset.audio_codec is AudioCodec.MP3:
            text += f"  ·  {preset.audio_quality} kbps {preset.audio_codec.value.upper()}"
        self._selector_value.setText(text)
