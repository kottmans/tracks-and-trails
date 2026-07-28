"""The add-URL dialog: paste a URL, see what it is, choose a preset, queue it (`T-016`).

The first widget that talks to the download manager, and therefore the first place a blocking
call would freeze the application.

## Nothing here waits for a worker

**Probing is a worker process, not a "quick" inline call** (`ARCHITECTURE.md` §8, `NFR-001`).
Probe latency is unbounded — a network round trip through an extractor that may itself fetch
several pages — so `probe()` starts a session and returns. What comes back arrives on
`DownloadManager`'s signals, on the GUI thread, one event-loop turn later.

The same rule covers the thumbnail, which is the one piece of `REQ-002` that is not in the
probe's own reply: `MediaInfo` carries a *URL*, and turning it into a pixmap means fetching
bytes. That fetch is asynchronous too (`ThumbnailLoader`), and it is injected rather than
imported so the suite can decode a recorded image without touching the network.

## Probe first, then download the job you probed

`ARC-004` settled what happens between the two. A probed job is left in `READY`, and **Add to
queue starts the download from `READY`** — the same job, the same record, no second one and no
return to `PROBING`. URLs the user pasted but did not probe become `QUEUED` jobs, which start by
probing when something runs them (`T-036`).

**Every job is persisted before this dialog closes** (`REQ-012`). A crash on the way out loses
nothing, which is only true because the write happens here rather than in whatever runs the
queue next.

## What the user is shown

Every field `REQ-002` names — title, uploader, duration, thumbnail, and whether the URL is a
single item or a playlist — and on failure the extractor's own message, character for character
(`REQ-005`, `NFR-006`). Not a paraphrase and not a generic "could not fetch": the extractor's
text is usually the only actionable thing the user has.

`NFR-005` throughout: every control has an accessible name, the tab order is stated rather than
inherited from construction order, and **no state is signalled by colour**. Each outcome —
probing, probed, failed, cancelled — says what it is in words.
"""

import uuid
from collections.abc import Callable, Sequence
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import Any, Final, Protocol

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core import presets as preset_registry
from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import Job, MediaInfo, Preset
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.downloader.protocol import SessionKind

#: The size the thumbnail is displayed at. A fixed box rather than the image's own size, so a
#: 1920-wide thumbnail does not resize the dialog around it.
THUMBNAIL_SIZE: Final = (192, 108)

#: Shown in place of the thumbnail before there is one, and when the extractor supplied no URL.
#: Text rather than an empty frame: `NFR-005` forbids conveying a state by appearance alone, and
#: "no thumbnail" and "not probed yet" are different states a blank box cannot distinguish.
NO_THUMBNAIL_TEXT: Final = "No thumbnail"
NOT_PROBED_TEXT: Final = "Not probed yet"

#: What an unfilled `REQ-002` field reads as. `MediaInfo` models these as genuinely optional —
#: yt-dlp omits an uploader for some sites and a duration for a live stream — so this is the
#: honest rendering of a missing value rather than an invented one.
UNKNOWN_TEXT: Final = "Unknown"


class JobSink(Protocol):
    """The persistence this dialog needs, and nothing more.

    Narrower than `manager.JobStore`, and deliberately a separate protocol: the manager *updates*
    jobs that exist, while this creates them. `persistence.JobRepository` satisfies both, and
    `app.py` hands the real one over at composition time (`T-036`). Depending on the shape rather
    than the class is what keeps `ui/` free of any knowledge that SQLite exists
    (`ARCHITECTURE.md` §3).
    """

    def add(self, job: Job) -> None: ...

    def next_queue_position(self) -> int: ...


class ThumbnailLoader(Protocol):
    """Fetches thumbnail bytes without blocking the GUI thread.

    A seam, not a mock: `NetworkThumbnailLoader` below is the real implementation and is what
    ships. It exists as a protocol because `REQ-002`'s thumbnail is the one field that is not in
    the probe's reply — `MediaInfo` carries a URL — and a suite that decoded it for real would
    have to reach the network, which `ai/TESTING.md` §1 keeps out of the default run.
    """

    def load(self, url: str, deliver: Callable[[bytes], None]) -> None: ...

    def cancel(self) -> None: ...


class NetworkThumbnailLoader(QObject):
    """Fetches a thumbnail with `QNetworkAccessManager`, which never blocks.

    Qt's own network stack rather than `urllib`: it is asynchronous by construction, so there is
    no version of this that accidentally waits on a socket from the GUI thread. A failed or
    refused fetch is simply not delivered — a missing thumbnail is a cosmetic loss, and turning
    it into an error message would bury the probe result that did arrive.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # Imported inside the constructor rather than at module scope so importing this module
        # does not require QtNetwork: the dialog takes an injected loader, and only this default
        # implementation needs those classes.
        from PySide6.QtNetwork import QNetworkAccessManager

        self._access = QNetworkAccessManager(self)
        self._reply: Any = None

    def load(self, url: str, deliver: Callable[[bytes], None]) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtNetwork import QNetworkRequest

        self.cancel()
        reply = self._access.get(QNetworkRequest(QUrl(url)))
        self._reply = reply

        def finished() -> None:
            if self._reply is not reply:
                return
            self._reply = None
            if reply.error() == reply.NetworkError.NoError:
                deliver(bytes(reply.readAll().data()))
            reply.deleteLater()

        reply.finished.connect(finished)

    def cancel(self) -> None:
        reply, self._reply = self._reply, None
        if reply is not None:
            reply.abort()
            reply.deleteLater()


def split_urls(text: str) -> list[str]:
    """One URL per line, blank lines dropped (`REQ-001`'s multi-line paste).

    Whitespace-stripped per line because a pasted list routinely carries trailing spaces, and a
    URL with one is a URL the extractor refuses for a reason the user cannot see.

    Duplicates are **kept**. Two identical lines are two things the user asked for, and silently
    collapsing them would make the queue disagree with what was pasted.
    """
    return [line.strip() for line in text.splitlines() if line.strip()]


def format_duration(seconds: float | None) -> str:
    """`H:MM:SS`, or `M:SS` under an hour, or `UNKNOWN_TEXT`.

    `None` is not zero. A live stream has no duration and neither does a playlist the extractor
    did not enumerate; rendering either as `0:00` would be a confident lie of the kind
    `Job.progress` already refuses to tell.
    """
    if seconds is None:
        return UNKNOWN_TEXT
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def describe_kind(media: MediaInfo) -> str:
    """Whether the URL is a single item or a playlist, in words (`REQ-002`).

    The count is included when the extractor supplied one and omitted when it did not, because
    `MediaInfo.entry_count` models "unknown" as `None` rather than as zero — a playlist whose
    length could not be determined is a real state, and "0 items" is not what it means.
    """
    if not media.is_playlist:
        return "Single item"
    if media.entry_count is None:
        return "Playlist (item count unknown)"
    return f"Playlist ({media.entry_count} items)"


class AddUrlDialog(QDialog):
    """Paste URLs, probe one, choose a preset, and queue them all."""

    def __init__(
        self,
        *,
        manager: DownloadManager,
        jobs: JobSink,
        output_directory: Path,
        presets: Sequence[Preset] = preset_registry.BUILT_IN_PRESETS,
        thumbnail_loader: ThumbnailLoader | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._manager = manager
        self._jobs = jobs
        self._output_directory = output_directory
        self._presets = tuple(presets)
        self._thumbnails: ThumbnailLoader = thumbnail_loader or NetworkThumbnailLoader(self)

        #: The job whose probe session is in flight, and the job a finished probe left in
        #: `READY`. Separate fields: a cancelled probe clears the first and must not leave the
        #: second pointing at a job that never resolved.
        self._probing_job_id: str | None = None
        self._probed_job_id: str | None = None

        #: The URL text that was probed, as the user typed it. `MediaInfo.url` is yt-dlp's
        #: canonical `webpage_url` and routinely differs from what was pasted, so comparing
        #: against that would drop a valid probe result the moment the user touched the box.
        self._probed_input_url: str | None = None

        self._media: MediaInfo | None = None
        self._thumbnail: QPixmap | None = None

        #: Every job this dialog persisted, oldest first.
        self._queued_job_ids: list[str] = []

        self.setObjectName("addUrlDialog")
        self.setWindowTitle("Add URLs")
        self._build()
        self._connect_manager()
        self._set_tab_order()
        self._refresh_actions()

    # --- construction -------------------------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        self._urls = QPlainTextEdit(self)
        self._urls.setObjectName("urlInput")
        self._urls.setAccessibleName("URLs to download, one per line")
        self._urls.setAccessibleDescription(
            "Paste or type one URL per line. Each line becomes a separate download."
        )
        self._urls.setPlaceholderText("https://…  (one URL per line)")
        self._urls.textChanged.connect(self._on_urls_changed)
        layout.addWidget(self._urls)

        layout.addWidget(self._build_probe_row())
        layout.addWidget(self._build_results())
        layout.addWidget(self._build_preset_row())

        self._status = QLabel(self)
        self._status.setObjectName("statusMessage")
        self._status.setAccessibleName("Status")
        self._status.setWordWrap(True)
        # Selectable so the user can copy an extractor message into a search or a bug report. A
        # message kept verbatim (`NFR-006`) that cannot be copied is only half of the point.
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self._status.setText("Paste a URL, then probe it or add it to the queue.")
        layout.addWidget(self._status)

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

    def _build_probe_row(self) -> QWidget:
        row = QWidget(self)
        row.setObjectName("probeRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        self._probe_button = QPushButton("&Probe first URL", row)
        self._probe_button.setObjectName("probeButton")
        self._probe_button.setAccessibleName("Probe the first URL")
        self._probe_button.setAccessibleDescription(
            "Fetch the title, uploader, duration and thumbnail without downloading anything."
        )
        self._probe_button.clicked.connect(self.probe)
        layout.addWidget(self._probe_button)

        self._cancel_button = QPushButton("Cancel pro&be", row)
        self._cancel_button.setObjectName("cancelProbeButton")
        self._cancel_button.setAccessibleName("Cancel the running probe")
        self._cancel_button.clicked.connect(self.cancel_probe)
        layout.addWidget(self._cancel_button)

        layout.addStretch(1)
        return row

    def _build_results(self) -> QWidget:
        box = QGroupBox("What this URL is", self)
        box.setObjectName("probeResults")
        layout = QHBoxLayout(box)

        self._thumbnail_label = QLabel(box)
        self._thumbnail_label.setObjectName("thumbnail")
        self._thumbnail_label.setAccessibleName("Thumbnail")
        self._thumbnail_label.setFixedSize(*THUMBNAIL_SIZE)
        self._thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail_label.setText(NOT_PROBED_TEXT)
        layout.addWidget(self._thumbnail_label)

        fields = QFormLayout()
        self._title_value = self._field(box, "titleValue", "Title")
        self._uploader_value = self._field(box, "uploaderValue", "Uploader")
        self._duration_value = self._field(box, "durationValue", "Duration")
        self._kind_value = self._field(box, "kindValue", "Single item or playlist")
        fields.addRow("Title:", self._title_value)
        fields.addRow("Uploader:", self._uploader_value)
        fields.addRow("Duration:", self._duration_value)
        fields.addRow("Kind:", self._kind_value)
        layout.addLayout(fields, 1)
        return box

    def _field(self, parent: QWidget, name: str, accessible: str) -> QLabel:
        """One read-only result field, named for a screen reader (`NFR-005`).

        The accessible name is set explicitly rather than left to the form's label text: Qt
        associates the two on most platforms, and "most" is what regresses without anyone
        noticing.
        """
        label = QLabel(parent)
        label.setObjectName(name)
        label.setAccessibleName(accessible)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        label.setText(UNKNOWN_TEXT)
        return label

    def _build_preset_row(self) -> QWidget:
        box = QGroupBox("Download as", self)
        box.setObjectName("presetBox")
        layout = QVBoxLayout(box)

        self._preset_choice = QComboBox(box)
        self._preset_choice.setObjectName("presetChoice")
        self._preset_choice.setAccessibleName("Download preset")
        for preset in self._presets:
            self._preset_choice.addItem(preset.name)
        self._preset_choice.currentIndexChanged.connect(self._show_selector)
        layout.addWidget(self._preset_choice)

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
        """The tab order, stated rather than inherited (`NFR-005`).

        Construction order already produces something close to this, which is exactly why it is
        written down: an order that is merely a side effect of the order widgets were built in
        changes silently the first time a widget moves. `tests/ui/test_add_dialog.py` asserts
        this chain, so a reordering has to be deliberate.

        It follows the task the dialog exists for: type the URLs, probe them, read the result,
        choose how to download, then act.
        """
        for earlier, later in pairwise(self.focus_chain()):
            self.setTabOrder(earlier, later)

    def focus_chain(self) -> list[QWidget]:
        """The controls in their intended tab order. One list, used and asserted."""
        return [
            self._urls,
            self._probe_button,
            self._cancel_button,
            self._preset_choice,
            self._add_button,
            self._close_button,
        ]

    def _connect_manager(self) -> None:
        self._manager.media_probed.connect(self._on_media_probed)
        self._manager.job_failed.connect(self._on_job_failed)
        self._manager.job_changed.connect(self._on_job_changed)

    # --- queries used by callers and tests -----------------------------------------------

    @property
    def probing_job_id(self) -> str | None:
        """The job whose probe session is in flight, if any."""
        return self._probing_job_id

    @property
    def probed_job_id(self) -> str | None:
        """The job a finished probe left in `READY`, if any."""
        return self._probed_job_id

    @property
    def media(self) -> MediaInfo | None:
        """What the last successful probe reported."""
        return self._media

    @property
    def thumbnail(self) -> QPixmap | None:
        """The decoded thumbnail — a real pixmap, not the URL it came from (`REQ-002`)."""
        return self._thumbnail

    @property
    def queued_job_ids(self) -> tuple[str, ...]:
        """Every job this dialog persisted, oldest first."""
        return tuple(self._queued_job_ids)

    @property
    def selected_preset(self) -> Preset:
        return self._presets[max(self._preset_choice.currentIndex(), 0)]

    def status_text(self) -> str:
        """Whatever the status line currently says.

        The one piece of the dialog's *display* exposed as an accessor rather than left to be
        read off the widget: it is the only place an extractor message appears (`NFR-006`), and
        composition will want to surface the same text elsewhere.
        """
        return self._status.text()

    # --- probing ------------------------------------------------------------------------

    def probe(self) -> None:
        """Start a probe session for the first URL. **Returns immediately** (`NFR-001`).

        The first URL rather than all of them: Phase 1 runs a pool of exactly one
        (`downloader/manager.py`), so probing a pasted batch would be a queue of probes with no
        scheduler to run it. The rest of the batch is still queued by `add_to_queue`, and each
        starts by probing when something runs it.
        """
        urls = split_urls(self._urls.toPlainText())
        if not urls:
            self._status.setText("Enter a URL first.")
            return
        if self._probing_job_id is not None:
            return

        job = self._new_job(urls[0])
        # Persisted before the session starts, because `start()` reads the job back out of the
        # repository — and because a probe that crashes the application should still leave the
        # URL the user pasted in the queue (`REQ-012`).
        self._jobs.add(job)
        self._queued_job_ids.append(job.id)
        self._probing_job_id = job.id
        self._probed_job_id = None
        self._probed_input_url = job.url
        self._media = None
        self._reset_fields()
        self._status.setText(f"Probing {job.url} …")
        self._refresh_actions()
        try:
            self._manager.start(job.id, SessionKind.PROBE)
        except (RuntimeError, ValueError) as error:
            # A busy manager, or a job the state machine refuses. Reported rather than raised out
            # of a button press: the dialog stays usable, and an unhandled exception in a slot
            # would take down the event loop over something the user can simply retry.
            self._probing_job_id = None
            self._status.setText(f"Could not start a probe: {error}")
            self._refresh_actions()

    def cancel_probe(self) -> None:
        """Ask the manager to stop the running probe (`REQ-015`).

        The worker and everything it spawned are reaped by `DownloadManager.cancel`, which
        escalates on its own timer; nothing here waits for that. The dialog stops *waiting* on
        the probe immediately, which is what the user asked for.
        """
        job_id = self._probing_job_id
        if job_id is None:
            return
        self._probing_job_id = None
        self._probed_job_id = None
        self._probed_input_url = None
        self._status.setText("Probe cancelled. The URL is still queued.")
        self._manager.cancel(job_id)
        self._refresh_actions()

    def _on_media_probed(self, job_id: str, media: object) -> None:
        if job_id != self._probing_job_id or not isinstance(media, MediaInfo):
            return
        self._probing_job_id = None
        self._probed_job_id = job_id
        self._media = media
        self._show(media)
        self._refresh_actions()

    def _on_job_failed(self, job_id: str, kind: object, message: str) -> None:
        """Show the extractor's message **verbatim** (`REQ-005`, `NFR-006`).

        Not summarised, not paraphrased, and not folded into a sentence that changes it. The
        classification is shown beside it rather than instead of it: the kind tells the user
        whether retrying could help, and the text is the only thing that says what happened.
        """
        if job_id != self._probing_job_id:
            return
        self._probing_job_id = None
        self._probed_job_id = None
        self._probed_input_url = None
        self._media = None
        self._reset_fields()
        label = kind.value if isinstance(kind, ErrorKind) else str(kind)
        self._status.setText(f"{label}\n{message}")
        self._refresh_actions()

    def _on_job_changed(self, job_id: str, status: str) -> None:
        """Drop a probed job that stopped being startable.

        A job left `READY` by a probe can still be cancelled from elsewhere — the queue view
        (`T-017`), or a shutdown — and `Add to queue` would then call `start()` on a job the
        state machine refuses. Reading the persisted status rather than assuming this dialog is
        the only thing touching the job is the cheaper half of that (`ARC-004`).
        """
        if job_id != self._probed_job_id:
            return
        if status != JobStatus.READY.value:
            self._probed_job_id = None
            self._refresh_actions()

    # --- queueing -----------------------------------------------------------------------

    def add_to_queue(self) -> None:
        """Persist a job per URL, start the probed one, and close (`REQ-001`, `REQ-012`).

        **Every job is written before `accept()`**, so a crash between this dialog closing and
        the queue view opening cannot lose what the user asked for.

        The probed job is the one already in `READY`; it starts as a download and moves
        `READY → RUNNING` without re-entering `PROBING` (`ARC-004`). The rest are new `QUEUED`
        jobs that start by probing when something runs them — scheduling those is `T-036`'s work,
        not this dialog's.
        """
        urls = split_urls(self._urls.toPlainText())
        if not urls:
            self._status.setText("Enter a URL first.")
            return

        probed = self._probed_job_id
        # The probed job already covers the first URL. Skipping it here is what keeps
        # probe-then-add from queueing the same URL twice — `ARC-004` names that as stranding or
        # duplicating the probed record.
        remaining = urls[1:] if probed is not None else urls
        for url in remaining:
            job = self._new_job(url)
            self._jobs.add(job)
            self._queued_job_ids.append(job.id)

        if probed is not None:
            try:
                self._manager.start(probed, SessionKind.DOWNLOAD)
            except (RuntimeError, ValueError) as error:
                # The jobs are already persisted, so nothing is lost by not starting: whatever
                # runs the queue picks it up. Saying so beats closing on a silent failure.
                self._status.setText(
                    f"Queued, but the download did not start: {error} "
                    "It stays in the queue and can be started from there."
                )
                self._refresh_actions()
                return
        self.accept()

    def _new_job(self, url: str) -> Job:
        request = preset_registry.to_request(
            self.selected_preset, url=url, output_directory=str(self._output_directory)
        )
        return Job(
            id=str(uuid.uuid4()),
            url=url,
            request=request,
            status=JobStatus.QUEUED,
            created_at=datetime.now().astimezone(),
            queue_position=self._jobs.next_queue_position(),
        )

    # --- display ------------------------------------------------------------------------

    def _show(self, media: MediaInfo) -> None:
        self._title_value.setText(media.title)
        self._uploader_value.setText(media.uploader or UNKNOWN_TEXT)
        self._duration_value.setText(format_duration(media.duration_seconds))
        self._kind_value.setText(describe_kind(media))
        self._status.setText("Probed. Choose a preset and add it to the queue.")
        self._load_thumbnail(media)

    def _load_thumbnail(self, media: MediaInfo) -> None:
        self._thumbnail = None
        self._thumbnail_label.setPixmap(QPixmap())
        if not media.thumbnail_url:
            self._thumbnail_label.setText(NO_THUMBNAIL_TEXT)
            self._thumbnail_label.setAccessibleDescription(
                f"No thumbnail was supplied for {media.title}"
            )
            return
        self._thumbnail_label.setText("Loading thumbnail…")
        self._thumbnail_label.setAccessibleDescription(f"Thumbnail for {media.title}")
        url = media.thumbnail_url

        def deliver(data: bytes) -> None:
            # Guards a reply that arrives after the user probed something else: the loader is
            # asked to cancel, but a fetch already in flight can still land.
            if self._media is None or self._media.thumbnail_url != url:
                return
            self._set_thumbnail(data)

        self._thumbnails.load(url, deliver)

    def _set_thumbnail(self, data: bytes) -> None:
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            # Undecodable bytes are not worth interrupting the user for; the probe result they
            # asked for is on screen either way.
            self._thumbnail_label.setText(NO_THUMBNAIL_TEXT)
            return
        scaled = pixmap.scaled(
            *THUMBNAIL_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._thumbnail = scaled
        self._thumbnail_label.setText("")
        self._thumbnail_label.setPixmap(scaled)

    def _reset_fields(self) -> None:
        for label in (
            self._title_value,
            self._uploader_value,
            self._duration_value,
            self._kind_value,
        ):
            label.setText(UNKNOWN_TEXT)
        self._thumbnail = None
        self._thumbnails.cancel()
        self._thumbnail_label.setPixmap(QPixmap())
        self._thumbnail_label.setText(NOT_PROBED_TEXT)
        self._thumbnail_label.setAccessibleDescription("")

    def _show_selector(self) -> None:
        """Display the selector the chosen preset actually downloads with (`REQ-009`)."""
        selector = preset_registry.effective_selector(self.selected_preset)
        self._selector_value.setText(f"Format selector: {selector}")

    def _on_urls_changed(self) -> None:
        """A changed URL box invalidates a probe of the old first URL.

        Otherwise `Add to queue` would start a download of whatever was probed a minute ago
        while the box shows something else — the shape of silent wrong result this project keeps
        finding, where a value is computed correctly and then applied to the wrong thing.
        """
        if self._probed_job_id is None:
            self._refresh_actions()
            return
        urls = split_urls(self._urls.toPlainText())
        if urls and urls[0] == self._probed_input_url:
            self._refresh_actions()
            return
        self._probed_job_id = None
        self._probed_input_url = None
        self._media = None
        self._reset_fields()
        self._status.setText("The URL changed. Probe again to see what it is.")
        self._refresh_actions()

    def _refresh_actions(self) -> None:
        """Enable exactly the controls that can do something right now.

        `core.job_state.can_transition` exists so a UI can disable an action rather than offer it
        and catch the exception; the same reasoning applies to a probe that is already running
        and to an empty URL box.
        """
        probing = self._probing_job_id is not None
        has_urls = bool(split_urls(self._urls.toPlainText()))
        self._probe_button.setEnabled(has_urls and not probing)
        self._cancel_button.setEnabled(probing)
        self._add_button.setEnabled(has_urls)
