"""The add-URL dialog: paste a URL, see what it is, choose a preset, queue it (`T-016`).

The first widget that talks to the download manager, and therefore the first place a blocking
call would freeze the application.

## Nothing here waits — not on a worker, and not on the database

**Probing is a worker process, not a "quick" inline call** (`ARCHITECTURE.md` §8, `NFR-001`).
Probe latency is unbounded — a network round trip through an extractor that may itself fetch
several pages — so `probe()` starts a session and returns. Results arrive on `DownloadManager`'s
signals, on the GUI thread, one event-loop turn later.

**Persistence is asynchronous too** (`ARC-005`). The first version called `JobRepository` straight
from a button slot, and `T016-R3` measured 0.302 s of frozen GUI under a contended writer lock
followed by an `OperationalError` no user ever saw. Jobs now go to a `JobSink` that answers on a
callback. `REQ-012`'s persist-before-close rule is *strengthened* by that: this dialog closes
**inside** the success callback, so it cannot close before the rows exist, and a failed write
leaves it open with the user's input intact.

The thumbnail is the third: `MediaInfo` carries a *URL*, so a pixmap means fetching bytes, and
that fetch is asynchronous and injected (`ThumbnailLoader`).

## A probe belongs to a URL, not just to a job id

`T016-R1` was Critical and this is its lesson. The first version bound a result to the job id it
asked about, invalidated a *finished* probe when the input changed, and returned early while one
was still in flight — so a late result was accepted for a URL that was no longer on screen, and
`Add to queue` started the old one while dropping what the user had actually typed.

Every probe now records **the input line it was started for** and the generation of the URL box
at that moment. A result is accepted only if that line is still the first one. When the first
line changes, an in-flight probe is cancelled rather than left to land later, which also returns
the pool-of-one manager to idle.

The same state model closes the second edge: **`Add to queue` is disabled while a probe is
outstanding**, so the state in which the dialog held one persisted job and was about to create
another for the same line is unreachable rather than reconciled. Making an invalid state
unrepresentable is what this project has learned four times over — see `T-014`'s proxy
credentials and `T-044`'s exports.

## Closing is abandoning

Rejecting, closing, or pressing Escape cancels an outstanding probe (`T016-R2`). Without that,
closing the dialog stranded a worker and left the pool-of-one manager permanently busy, so every
later Add-URL dialog could only report "a session is already running". `done()` is the single
choke point every one of those routes goes through.

## What the user is shown

Every field `REQ-002` names — title, uploader, duration, thumbnail, and whether the URL is a
single item or a playlist — and on failure the extractor's own message, character for character
(`REQ-005`, `NFR-006`).

**Every label that displays text this application did not write is `PlainText`** (`T016-R6`).
A title of `<b>VISIBLE</b>` is a title, not markup: under Qt's default `AutoText` it was being
rendered as rich text, which consumes the tags and shows something the site did not send.

`NFR-005` throughout: an accessible name on every control, the **complete** keyboard order stated
and asserted — including the selectable result fields, which `T016-R4` found focusable but
undeclared — and no state signalled by colour.
"""

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
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

#: The thumbnail box's four states, each in words. `NFR-005` forbids conveying a state by
#: appearance alone, and "not probed", "the site supplied none", "the fetch failed" and "loading"
#: are four different things a blank frame cannot distinguish. `T016-R5`: the failed state did
#: not exist, so a failed fetch claimed to be loading forever.
NOT_PROBED_TEXT: Final = "Not probed yet"
LOADING_THUMBNAIL_TEXT: Final = "Loading thumbnail…"
NO_THUMBNAIL_TEXT: Final = "No thumbnail"
THUMBNAIL_FAILED_TEXT: Final = "Thumbnail unavailable"

#: What an unfilled `REQ-002` field reads as. `MediaInfo` models these as genuinely optional —
#: yt-dlp omits an uploader for some sites and a duration for a live stream — so this is the
#: honest rendering of a missing value rather than an invented one.
UNKNOWN_TEXT: Final = "Unknown"

#: How a failed withdrawal announces itself. A prefix rather than a whole message, because the
#: URL and the reason belong in it and `NFR-005` forbids signalling the state any other way.
WITHDRAW_FAILED_PREFIX: Final = "Still queued:"

#: Every label that renders text this application did not author: extractor messages, site
#: metadata, and the selector a user may have typed. All are forced to `PlainText` (`T016-R6`).
UNTRUSTED_TEXT_LABELS: Final = (
    "titleValue",
    "uploaderValue",
    "durationValue",
    "kindValue",
    "selectorValue",
    "statusMessage",
)


class JobSink(Protocol):
    """Persists jobs **without blocking the caller** (`ARC-005`).

    `done` is called exactly once, on the GUI thread, with `None` on success or a message on
    failure. The whole sequence is one transaction: either every job of an interaction is stored
    or none is, so a half-queued paste cannot exist.

    Narrower than `manager.JobStore`, and deliberately a separate protocol: the manager *updates*
    jobs that exist, this creates them. Depending on the shape rather than the class is what keeps
    `ui/` free of any knowledge that SQLite exists (`ARCHITECTURE.md` §3) — including, now, that
    it is written from another thread.
    """

    def submit(self, jobs: Sequence[Job], done: Callable[[str | None], None]) -> None: ...


class ThumbnailLoader(Protocol):
    """Fetches thumbnail bytes without blocking the GUI thread.

    `done` receives the bytes, or **`None` when the fetch failed** — the half `T016-R5` found
    missing, which left the dialog claiming to be loading a thumbnail that was never coming.

    A seam, not a mock: `NetworkThumbnailLoader` below is the real implementation and is what
    ships. It exists as a protocol because `REQ-002`'s thumbnail is the one field not in the
    probe's reply, and a suite that decoded it for real would have to reach the network.
    """

    def load(self, url: str, done: Callable[[bytes | None], None]) -> None: ...

    def cancel(self) -> None: ...


class NetworkThumbnailLoader(QObject):
    """Fetches a thumbnail with `QNetworkAccessManager`, which never blocks.

    Qt's own network stack rather than `urllib`: it is asynchronous by construction, so there is
    no version of this that accidentally waits on a socket from the GUI thread.

    **Both outcomes are reported.** The first version called back only on `NoError` and left
    every other ending silent (`T016-R5`) — an expired or offline thumbnail is the ordinary case,
    not an exotic one, and silence rendered as a permanent "Loading…".
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # Imported inside the constructor rather than at module scope so importing this module
        # does not require QtNetwork: the dialog takes an injected loader, and only this default
        # implementation needs those classes.
        from PySide6.QtNetwork import QNetworkAccessManager

        self._access = QNetworkAccessManager(self)
        self._reply: Any = None

    def load(self, url: str, done: Callable[[bytes | None], None]) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtNetwork import QNetworkRequest

        self.cancel()
        reply = self._access.get(QNetworkRequest(QUrl(url)))
        self._reply = reply

        def finished() -> None:
            if self._reply is not reply:
                # Superseded by a later request; that one owns the answer.
                reply.deleteLater()
                return
            self._reply = None
            failed = reply.error() != reply.NetworkError.NoError
            done(None if failed else bytes(reply.readAll().data()))
            reply.deleteLater()

        reply.finished.connect(finished)

    def cancel(self) -> None:
        """Abandon any request in flight. Its callback will not fire."""
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


@dataclass
class _Probe:
    """One probe, and the input it belongs to (`T016-R1`).

    `url` is the text of the first line **as the user typed it**, not `MediaInfo.url`: yt-dlp's
    canonical `webpage_url` routinely differs from what was pasted, so comparing against that
    would discard valid results. `generation` counts changes to the first line, so a result can
    be attributed even if the same text is typed, cleared and retyped.
    """

    job_id: str
    url: str
    generation: int

    #: `start()` has been issued for this job — the session is genuinely in flight.
    started: bool = False
    #: The probe reported `Probed`; the job is `READY` and can be downloaded.
    ready: bool = False

    #: The input this probe belongs to has moved on. **The record is kept rather than dropped**,
    #: which is what makes the identity check in `_on_media_probed` reachable: a result already
    #: queued as a signal still arrives, and something has to refuse it by name. Clearing the
    #: probe instead left that refusal unreachable — a guard that reads as protection while
    #: protecting nothing, which `ai/TESTING.md` §13 exists to catch.
    superseded: bool = False

    @property
    def in_flight(self) -> bool:
        """A worker is running for this probe and its answer is still wanted."""
        return self.started and not self.ready and not self.superseded

    @property
    def usable(self) -> bool:
        """This probe still describes what the user is looking at."""
        return not self.superseded


@dataclass
class _Persisted:
    """The jobs this dialog has written, counted **per entered occurrence** (`T016-R1`).

    Keyed by URL *membership* originally, which quietly broke `REQ-001`: two identical lines are
    two things the user asked for and `split_urls` keeps both, but after probing the first of
    them `Add` skipped every line whose text was already present and stored one job for two
    entries. A count answers the real question — how many of these did we already store? — and
    the difference is what still needs creating.
    """

    #: URL text → the ids stored for it, oldest first.
    by_url: dict[str, list[str]] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)

    def record(self, url: str, job_id: str) -> None:
        self.by_url.setdefault(url, []).append(job_id)
        self.order.append(job_id)

    def forget(self, url: str, job_id: str) -> None:
        stored = self.by_url.get(url)
        if stored is not None and job_id in stored:
            stored.remove(job_id)
            if not stored:
                del self.by_url[url]

    def covered(self) -> dict[str, int]:
        """How many entered occurrences of each URL already have a job."""
        return {url: len(ids) for url, ids in self.by_url.items()}


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

        self._probe: _Probe | None = None
        self._persisted = _Persisted()
        self._media: MediaInfo | None = None
        self._thumbnail: QPixmap | None = None
        #: Bumped whenever the first input line changes. See `_Probe`.
        self._generation = 0
        self._first_url: str | None = None
        #: A write is outstanding. Every control that could start a second one is disabled.
        self._saving = False

        #: Jobs this dialog has withdrawn, until their `CANCELLED` is durable (`T016-R1`).
        #:
        #: A withdrawal is the Critical consequence in reverse: the row exists, the user has
        #: taken the URL away, and until the cancellation actually reaches disk that row is still
        #: live work a restart would pick up. So the dialog owns the outcome instead of firing
        #: `cancel()` and hoping — it refuses to close or queue while one is outstanding, and
        #: says why.
        self._withdrawing: dict[str, str] = {}
        self._withdraw_error: str | None = None

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

        self._status = QLabel(self)
        self._status.setObjectName("statusMessage")
        self._status.setAccessibleName("Status")
        self._status.setWordWrap(True)
        # Selectable so the user can copy an extractor message into a search or a bug report. A
        # message kept verbatim (`NFR-006`) that cannot be copied is only half of the point.
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self._status.setText("Paste a URL, then probe it or add it to the queue.")
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

        # `T016-R6`: every label carrying text this application did not author is plain. Applied
        # from one list rather than at each construction site, so a label added to that list is
        # protected without anyone remembering a second call.
        for name in UNTRUSTED_TEXT_LABELS:
            label = self.findChild(QLabel, name)
            if label is not None:
                label.setTextFormat(Qt.TextFormat.PlainText)

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

        These are **keyboard focusable**, because `TextBrowserInteraction` includes
        `TextSelectableByKeyboard`. That is deliberate — a screen-reader user has to be able to
        reach the answer — and `T016-R4` found the consequence: they belong in the declared tab
        order, not filtered out of it.
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
        """The **complete** keyboard order, stated rather than inherited (`NFR-005`).

        `T016-R4`: the first version declared only the editor, buttons and preset, while six
        result and status labels were keyboard-focusable too — so Qt put them after Close, and
        the test filtered them out of its own observation. A tab order that omits reachable
        controls is not a tab order; it is a subset that happens to be asserted.

        The order follows the task the dialog exists for, which is what its prose always claimed:
        type the URLs, probe them, **read the result**, choose how to download, then act.
        """
        for earlier, later in pairwise(self.focus_chain()):
            self.setTabOrder(earlier, later)

    def focus_chain(self) -> list[QWidget]:
        """Every keyboard-focusable control, in its intended order.

        `tests/ui/test_add_dialog.py` asserts that this list is exactly the set of focusable
        widgets Qt reports, so a control that gains focus without being placed here fails rather
        than silently landing at the end.
        """
        return [
            self._urls,
            self._probe_button,
            self._cancel_button,
            self._title_value,
            self._uploader_value,
            self._duration_value,
            self._kind_value,
            self._status,
            self._preset_choice,
            self._selector_value,
            self._add_button,
            self._close_button,
        ]

    def _connect_manager(self) -> None:
        self._manager.media_probed.connect(self._on_media_probed)
        self._manager.job_failed.connect(self._on_job_failed)
        self._manager.job_changed.connect(self._on_job_changed)
        self._manager.persistence_failed.connect(self._on_persistence_failed)

    # --- queries used by callers and tests -----------------------------------------------

    @property
    def probing_job_id(self) -> str | None:
        """The job whose probe session is in flight, if any."""
        probe = self._probe
        return probe.job_id if probe is not None and probe.in_flight else None

    @property
    def probed_job_id(self) -> str | None:
        """The job a finished probe left in `READY`, if any."""
        probe = self._probe
        return probe.job_id if probe is not None and probe.ready and probe.usable else None

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
        return tuple(self._persisted.order)

    @property
    def withdrawing(self) -> tuple[str, ...]:
        """Jobs whose withdrawal has not yet reached disk (`T016-R1`)."""
        return tuple(self._withdrawing)

    @property
    def withdraw_failed(self) -> str | None:
        """Why the outstanding withdrawal could not be written, if it could not."""
        return self._withdraw_error

    @property
    def is_saving(self) -> bool:
        """A write is outstanding. Nothing may start another, and nothing may close."""
        return self._saving

    @property
    def selected_preset(self) -> Preset:
        return self._presets[max(self._preset_choice.currentIndex(), 0)]

    def status_text(self) -> str:
        """Whatever the status line currently says."""
        return self._status.text()

    def first_url(self) -> str | None:
        """The first input line, or `None` when the box holds nothing usable."""
        urls = split_urls(self._urls.toPlainText())
        return urls[0] if urls else None

    # --- probing ------------------------------------------------------------------------

    def probe(self) -> None:
        """Persist the first URL, then start a probe session for it. **Returns immediately.**

        Two asynchronous steps, in that order: the job is stored before any worker is asked about
        it (`REQ-012`), and neither step blocks the GUI thread (`NFR-001`, `ARC-005`).

        The first URL rather than all of them: Phase 1 runs a pool of exactly one
        (`downloader/manager.py`), so probing a pasted batch would be a queue of probes with no
        scheduler to run it.
        """
        url = self.first_url()
        if url is None:
            self._status.setText("Enter a URL first.")
            return
        if (self._probe is not None and self._probe.usable) or self._saving:
            return

        job = self._new_job(url)
        probe = _Probe(job_id=job.id, url=url, generation=self._generation)
        self._probe = probe
        self._media = None
        self._reset_fields()
        self._begin_saving(f"Saving {url} …")
        self._jobs.submit([job], lambda error: self._on_probe_saved(probe, job, error))

    def _on_probe_saved(self, probe: _Probe, job: Job, error: str | None) -> None:
        """The probe's job is stored, or it is not. Only then is a worker asked for anything."""
        self._saving = False
        if error is not None:
            probe.superseded = True
            self._status.setText(f"Nothing was saved, so nothing was probed. {error}")
            self._refresh_actions()
            return

        if probe.superseded or self._probe is not probe or probe.url != self.first_url():
            # **The input moved on while the write was in flight** (`T016-R1`, `T016-R2`). The row
            # is now on disk for a URL the user has replaced or a dialog that has closed, and the
            # first version simply recorded it and returned — leaving it durably `QUEUED`, where
            # whatever runs the queue next would download the URL that was taken away.
            #
            # So it is cancelled rather than kept. `QUEUED → CANCELLED` is legal and needs no
            # worker, and the row survives as an honest record of something asked for and
            # withdrawn instead of as pending work nobody wants.
            self._withdraw(job.id, probe.url)
            self._refresh_actions()
            return
        self._persisted.record(probe.url, job.id)

        try:
            self._manager.start(job.id, SessionKind.PROBE)
        except (RuntimeError, ValueError) as start_error:
            # A busy manager, or a job the state machine refuses. Reported rather than raised out
            # of a callback: the dialog stays usable, and the job is already safely stored.
            probe.superseded = True
            self._status.setText(f"Could not start a probe: {start_error}")
            self._refresh_actions()
            return
        probe.started = True
        self._status.setText(f"Probing {probe.url} …")
        self._refresh_actions()

    def cancel_probe(self) -> None:
        """Ask the manager to stop the running probe (`REQ-015`).

        The worker and everything it spawned are reaped by `DownloadManager.cancel`, which
        escalates on its own timer; nothing here waits for that.
        """
        if self._probe is None:
            return
        self._discard_probe("Probe cancelled. The URL is still queued.")

    def _discard_probe(self, message: str | None) -> None:
        """Retire the current probe, cancelling its session if one is in flight.

        The single place a probe stops mattering, reached by cancelling, by editing the first
        URL, and by closing the dialog. One route means one set of consequences: the session is
        cancelled, the URL stops counting as already-persisted so re-entering it queues it again,
        and nothing is left claiming to be probed.

        **The record is marked, not deleted.** A `Probed` signal already queued still arrives
        after this returns, and `_on_media_probed` refuses it by name. Deleting the record would
        make that refusal unreachable and leave the acceptance rule resting on this method being
        called first — which is exactly the ordering assumption `T016-R1` was.
        """
        probe = self._probe
        if probe is None:
            return
        probe.superseded = True
        self._persisted.forget(probe.url, probe.job_id)
        if probe.started and not probe.ready:
            self._withdraw(probe.job_id, probe.url)
        self._media = None
        self._reset_fields()
        if message is not None:
            self._status.setText(message)
        self._refresh_actions()

    def _on_media_probed(self, job_id: str, media: object) -> None:
        """Accept a result only if it describes the URL still on screen (`T016-R1`)."""
        probe = self._probe
        if probe is None or probe.job_id != job_id or not isinstance(media, MediaInfo):
            return
        if probe.superseded or probe.url != self.first_url():
            # **This is the binding**, not a backstop for it. `_on_urls_changed` retires a probe
            # whose line changed, but the signal carrying its result may already be queued, so
            # the refusal has to live where the result is received (`T016-R1`).
            return
        probe.ready = True
        self._media = media
        self._show(media)
        self._refresh_actions()

    def _on_job_failed(self, job_id: str, kind: object, message: str) -> None:
        """Show the extractor's message **verbatim** (`REQ-005`, `NFR-006`).

        Not summarised, not paraphrased, and not folded into a sentence that changes it. The
        classification is shown beside it rather than instead of it: the kind tells the user
        whether retrying could help, and the text is the only thing that says what happened.
        """
        probe = self._probe
        if probe is None or probe.job_id != job_id or probe.superseded:
            return
        probe.superseded = True
        self._media = None
        self._reset_fields()
        label = kind.value if isinstance(kind, ErrorKind) else str(kind)
        self._status.setText(f"{label}\n{message}")
        self._refresh_actions()

    def _on_job_changed(self, job_id: str, status: str) -> None:
        """Drop a probed job that stopped being startable.

        A job left `READY` by a probe can still be cancelled from elsewhere — the queue view
        (`T-017`), or a shutdown — and `Add to queue` would then call `start()` on a job the
        state machine refuses.
        """
        if job_id in self._withdrawing and status == JobStatus.CANCELLED.value:
            # Durable at last: `job_changed` is emitted from the write's own callback
            # (`T016-R3`), so seeing it here means the row really is `CANCELLED` on disk.
            del self._withdrawing[job_id]
            if not self._withdrawing:
                self._withdraw_error = None
                if self._status.text().startswith(WITHDRAW_FAILED_PREFIX):
                    self._status.setText("The URL changed. Probe again to see what it is.")
            self._refresh_actions()
            return

        probe = self._probe
        if probe is None or probe.job_id != job_id or not probe.ready or probe.superseded:
            return
        if status != JobStatus.READY.value:
            probe.superseded = True
            self._refresh_actions()

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
        self._refresh_actions()

    def _withdraw(self, job_id: str, url: str) -> None:
        """Cancel a stored row this dialog no longer wants, and own the outcome."""
        self._withdrawing[job_id] = url
        self._manager.cancel(job_id)

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
            self._refresh_actions()
            return
        self._withdraw_error = None
        self._status.setText("Retrying the withdrawal …")
        for job_id in list(self._withdrawing):
            self._manager.cancel(job_id)
        self._refresh_actions()

    # --- queueing -----------------------------------------------------------------------

    def add_to_queue(self) -> None:
        """Persist a job per URL, start the probed one, and close (`REQ-001`, `REQ-012`).

        **The dialog closes inside the success callback**, so it cannot close before the rows
        exist. A failed write leaves it open with the user's input untouched, which is the only
        way the user can retry (`ARC-005`).

        **Refused while a probe is outstanding.** The button is disabled then, and this checks
        again: that is the state in which the first line already had a persisted job and a second
        would have been created for it (`T016-R1`).
        """
        if self._saving:
            return
        if self._withdrawing:
            self._status.setText(
                f"{WITHDRAW_FAILED_PREFIX} a withdrawn URL is still in the queue. "
                "Press Close to retry before adding more."
            )
            return
        urls = split_urls(self._urls.toPlainText())
        if not urls:
            self._status.setText("Enter a URL first.")
            return
        probe = self._probe
        if probe is not None and probe.in_flight:
            self._status.setText("A probe is still running. Wait for it, or cancel it.")
            return

        # One job per **entered line**, and never a second for a line already stored. Counted
        # rather than tested for membership, so two identical lines still become two jobs when
        # one of them has already been stored by a probe (`T016-R1`, `REQ-001`).
        remaining = self._persisted.covered()
        fresh: list[tuple[str, Job]] = []
        for url in urls:
            if remaining.get(url, 0) > 0:
                remaining[url] -= 1
                continue
            fresh.append((url, self._new_job(url)))
        self._begin_saving("Saving to the queue …")
        self._jobs.submit(
            [job for _, job in fresh], lambda error: self._on_queue_saved(fresh, error)
        )

    def _on_queue_saved(self, fresh: Sequence[tuple[str, Job]], error: str | None) -> None:
        self._saving = False
        if error is not None:
            self._status.setText(
                f"Nothing was saved and the queue is unchanged. {error} "
                "Your URLs are still here; try again."
            )
            self._refresh_actions()
            return
        for url, job in fresh:
            self._persisted.record(url, job.id)

        probe = self._probe
        if probe is not None and probe.ready and probe.usable:
            try:
                self._manager.start(probe.job_id, SessionKind.DOWNLOAD)
            except (RuntimeError, ValueError) as start_error:
                # The jobs are stored, so nothing is lost by not starting: whatever runs the
                # queue picks it up. Saying so beats closing on a silent failure.
                self._status.setText(
                    f"Queued, but the download did not start: {start_error} "
                    "It stays in the queue and can be started from there."
                )
                self._refresh_actions()
                return
        self.accept()

    def _begin_saving(self, message: str) -> None:
        self._saving = True
        self._status.setText(message)
        self._refresh_actions()

    def _new_job(self, url: str) -> Job:
        """A `QUEUED` job for `url`, with **no** queue position.

        The position is allocated by the writer, inside the same transaction as the insert
        (`ARC-005`). Reading `MAX(queue_position)` here would be both a GUI-thread database call
        and a guess against every other writer.
        """
        request = preset_registry.to_request(
            self.selected_preset, url=url, output_directory=str(self._output_directory)
        )
        return Job(
            id=str(uuid.uuid4()),
            url=url,
            request=request,
            status=JobStatus.QUEUED,
            created_at=datetime.now().astimezone(),
        )

    # --- closing ------------------------------------------------------------------------

    # Qt's override name, hence the camelCase: this is not a project naming choice.
    def done(self, result: int) -> None:
        """Every exit route funnels through here, so every exit route abandons the probe.

        `T016-R2`: closing the dialog used to leave a never-returning worker alive and the
        pool-of-one manager permanently busy, with the only cancel control now hidden — so every
        later Add-URL dialog could report nothing but "a session is already running". Escape, the
        window button, `reject()` and `accept()` all reach `done()`, which is why the ownership
        lives here rather than on the Close button.

        A probe that has already returned is **not** cancelled: its job is `READY`, and
        `add_to_queue` may just have started it downloading.
        """
        if self._withdrawing:
            # **Closing is refused while a withdrawal is outstanding** (`T016-R1`). The row the
            # user took away is still queued work until its cancellation is on disk, and a
            # dialog that closed here would leave it for the next run to download. Pressing
            # Close again retries, which is the visible progress the alternative lacks.
            self.retry_withdrawals()
            return

        probe = self._probe
        if probe is not None and probe.usable and not probe.ready:
            # **`usable`, not `in_flight`** (`T016-R2`). A probe whose row is still being written
            # has `started is False`, so the first version left it alone — and its completion
            # callback then started a worker for a dialog the user had already closed: one start,
            # zero cancellations, and a pool-of-one manager busy on behalf of nothing.
            #
            # Retiring it here is what `_on_probe_saved` reads to refuse the start. The session
            # is cancelled only if there is one; the row is cancelled by that callback.
            probe.superseded = True
            if probe.started:
                self._withdraw(probe.job_id, probe.url)
        self._thumbnails.cancel()
        super().done(result)

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
        self._thumbnail_label.setText(LOADING_THUMBNAIL_TEXT)
        self._thumbnail_label.setAccessibleDescription(f"Thumbnail for {media.title}")
        url = media.thumbnail_url

        def delivered(data: bytes | None) -> None:
            # Guards a reply that arrives after the user probed something else: the loader is
            # asked to cancel, but a fetch already in flight can still land.
            if self._media is None or self._media.thumbnail_url != url:
                return
            self._set_thumbnail(data)

        self._thumbnails.load(url, delivered)

    def _set_thumbnail(self, data: bytes | None) -> None:
        """Render the fetch's outcome, whatever it was (`T016-R5`).

        Failure and undecodable bytes are the same thing to a user — no picture — and neither is
        worth interrupting the probe result they actually asked for. What matters is that the
        label stops claiming to be loading something.
        """
        if data is None:
            self._thumbnail_label.setText(THUMBNAIL_FAILED_TEXT)
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            self._thumbnail_label.setText(THUMBNAIL_FAILED_TEXT)
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
        """A changed first line invalidates the probe bound to the old one (`T016-R1`).

        Fired on every keystroke, and it acts only when the *first* line actually changes —
        appending a second URL leaves a completed probe alone, which is the ordinary
        probe-one-then-paste-more flow.

        An in-flight probe is **cancelled**, not merely ignored. Ignoring would leave the
        pool-of-one manager busy on a result nobody will read, so the next probe could not start.
        """
        current = self.first_url()
        if current != self._first_url:
            self._first_url = current
            self._generation += 1
            if self._probe is not None:
                self._discard_probe("The URL changed. Probe again to see what it is.")
                return
        self._refresh_actions()

    def _refresh_actions(self) -> None:
        """Enable exactly the controls that can do something right now.

        `core.job_state.can_transition` exists so a UI can disable an action rather than offer it
        and catch the exception; the same reasoning applies to a probe already running, a write
        already outstanding, and an empty URL box.

        **Add is disabled while a probe is outstanding** (`T016-R1`). That is not cosmetic: it is
        what makes "one persisted job per entered line" hold, by removing the state in which the
        dialog would have created a second job for a line it had already stored.
        """
        probing = self.probing_job_id is not None
        has_urls = bool(split_urls(self._urls.toPlainText()))
        # A withdrawal that has not landed blocks every forward move (`T016-R1`): the queue holds
        # a row the user disowned, and adding to it or probing past it would build on a queue
        # that is already wrong.
        stuck = bool(self._withdrawing)
        self._probe_button.setEnabled(has_urls and not probing and not self._saving and not stuck)
        self._cancel_button.setEnabled(probing and not self._saving)
        self._add_button.setEnabled(has_urls and not probing and not self._saving and not stuck)
