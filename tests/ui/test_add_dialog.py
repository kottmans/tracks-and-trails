"""The add-URL dialog (`T-016`), including the six blocking findings of its first review.

**The process boundary is not mocked** (`ai/TESTING.md` §6). Every probe below spawns a real
process over a real `multiprocessing.Queue`; what the child *is* varies, exactly as in
`tests/integration/test_manager.py` — a child replaying a recorded fixture, a child that fails
with recorded text, a child that never answers, and a child that answers only when told to.

What *is* faked is the network: fixtures instead of sites (`ai/TESTING.md` §1), and an injected
`ThumbnailLoader` over bytes already in this repository. Qt still decodes the pixmap for real.
The **shipping** loader's failure path is exercised too (`T016-R5`), against a local URL that
cannot resolve — a loader that can only succeed cannot prove what happens when one does not.

Persistence is real where the claim is about persistence. `FakeSink` is a zero-latency stand-in
for the tests that are about the dialog's logic; the `ARC-005` tests drive the concrete
`QueueWriter` over a real SQLite file, under a genuinely held writer lock (`T016-R3`).

The dialog is driven through its **object names** rather than accessors added for the suite.
"""

import json
import sqlite3
import sys
import time
import uuid
from collections.abc import Callable, Iterator, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
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
    MediaKind,
    Preset,
)
from tracks_and_trails.core.presets import (
    BUILT_IN_PRESETS,
    MP3_QUALITY,
    effective_selector,
)
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.downloader.protocol import (
    Failed,
    Probed,
    Progress,
    SessionKind,
    Stage,
    WorkerFinished,
)
from tracks_and_trails.persistence.db import connect
from tracks_and_trails.persistence.repositories import JobRepository
from tracks_and_trails.persistence.store import PersistentJobStore
from tracks_and_trails.persistence.writer import QueueWriter
from tracks_and_trails.ui.add_dialog import (
    LOADING_THUMBNAIL_TEXT,
    NO_THUMBNAIL_TEXT,
    NOT_PROBED_TEXT,
    THUMBNAIL_FAILED_TEXT,
    UNKNOWN_TEXT,
    WITHDRAW_FAILED_PREFIX,
    AddUrlDialog,
    NetworkThumbnailLoader,
    describe_kind,
    format_duration,
    split_urls,
)
from tracks_and_trails.ui.main_window import MainWindow

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
INFODICTS: Final = REPO_ROOT / "tests" / "fixtures" / "infodicts"
ERRORS: Final = REPO_ROOT / "tests" / "fixtures" / "errors"

#: A real image already in this repository, used as thumbnail bytes. Reusing the application icon
#: rather than committing a second PNG: the claim is that Qt decoded *something* into a pixmap.
THUMBNAIL_SOURCE: Final = (
    REPO_ROOT / "src" / "tracks_and_trails" / "resources" / "icons" / "icon.png"
)

#: `NFR-001`: an interaction responds within ~100 ms. Half a second here for the same reason
#: `tests/integration/test_manager.py` uses that figure — `spawn` genuinely costs a process start
#: on a loaded runner, and the property under test is that nothing *waits*, which a blocking call
#: misses by seconds rather than by milliseconds.
INTERACTION_BUDGET_SECONDS: Final = 0.5

SINGLE_ITEM: Final = "archive_org_big_buck_bunny"
PLAYLIST: Final = "archive_org_art_of_war_playlist"
AUDIO_ONLY: Final = "archive_org_test_mp3"

#: The complete keyboard order `NFR-005` requires, **transcribed by hand** (`T016-R4`).
#:
#: Two corrections live in this one constant. The first version of the test derived it from
#: `AddUrlDialog.focus_chain()` — the list the dialog feeds to Qt — so it proved only that the
#: list equalled itself, and a mutation reversing two entries survived. The second version was
#: independent but named only the editor, buttons and preset, and *filtered every other focusable
#: node out of its own observation*; six selectable result and status labels were reachable by
#: keyboard, landed after Close, and gated nothing. This names all twelve.
EXPECTED_TAB_ORDER: Final = (
    "urlInput",
    "probeButton",
    "cancelProbeButton",
    "titleValue",
    "uploaderValue",
    "durationValue",
    "kindValue",
    "statusMessage",
    "presetChoice",
    # `T-076`. Placed with the preset it qualifies rather than at the end: a user who has just
    # chosen "Audio only (MP3)" is one Tab away from the bitrate that preset will convert at.
    "audioBitrateChoice",
    "selectorValue",
    "addButton",
    "closeButton",
)


# --- the recorded fixtures, read the same way here and in the spawned child -------------------


def load_info(name: str) -> dict[str, Any]:
    """One recorded `info_dict`, as `T-018` committed it."""
    data = json.loads((INFODICTS / f"{name}.json").read_text(encoding="utf-8"))
    return dict(data["info_dict"])


def load_error(name: str) -> dict[str, Any]:
    data = json.loads((ERRORS / f"{name}.json").read_text(encoding="utf-8"))
    return dict(data["error"])


def fixture_url(name: str) -> str:
    """The URL a fixture describes, which is what a test pastes into the dialog."""
    info = load_info(name)
    url = info.get("webpage_url") or info.get("original_url") or info.get("url")
    assert isinstance(url, str) and url, f"{name} records no URL to probe"
    return url


def _fixture_for(url: str) -> dict[str, Any]:
    for path in sorted(INFODICTS.glob("*.json")):
        info = load_info(path.stem)
        if url in (info.get("webpage_url"), info.get("original_url"), info.get("url")):
            return info
    raise LookupError(f"no recorded fixture describes {url!r}")


# --- the children -----------------------------------------------------------------------------
#
# Module level and picklable by reference: `spawn` imports this module in the child and looks the
# function up by name, so a closure or a local would not survive the boundary.


def child_replaying_a_fixture(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Probe from a recorded fixture; download by starting and not stopping.

    Kind-aware because `SessionValidator` is: `Probed` is not a legal outcome for a download
    session, so a child that sent one regardless would fail the job it was meant to be running.
    """
    if kind is SessionKind.PROBE:
        from tracks_and_trails.downloader.ytdlp_adapter import project_media

        try:
            info = _fixture_for(request.url)
        except LookupError:
            # **A URL with no fixture never answers**, rather than dying. A child that exits
            # ends its session and returns the manager to idle, which silently satisfied
            # `test_a_later_dialog_can_still_probe_after_one_is_closed_mid_probe` even with the
            # `T016-R2` fix reverted — the mutation survived because the worker died on its own.
            while True:
                time.sleep(0.05)
        queue.put(Probed(job_id=job_id, media=project_media(info)))
        queue.put(WorkerFinished(job_id=job_id, exit_code=0))
        return

    queue.put(Progress(job_id=job_id, stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=1))
    while True:
        time.sleep(0.05)


def child_probing_a_markup_title(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """A site whose title and uploader look like HTML (`T016-R6`).

    Not hypothetical: a title is arbitrary text chosen by whoever uploaded the item, and `<b>` is
    two keystrokes. What matters is that the dialog shows it rather than interpreting it.
    """
    media = MediaInfo(
        url=request.url,
        title="<b>VISIBLE</b>",
        uploader="<i>uploader</i>",
        duration_seconds=61.0,
    )
    queue.put(Probed(job_id=job_id, media=media))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))


def child_failing_as_recorded(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Fail with the extractor's own recorded words (`REQ-005`, `NFR-006`)."""
    error = load_error("unsupported_url")
    queue.put(
        Failed(job_id=job_id, kind=ErrorKind(error["expected_kind"]), message=error["message"])
    )
    queue.put(WorkerFinished(job_id=job_id, exit_code=1))


def child_never_returning(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """A session that never answers. The only thing that can prove cancellation works."""
    while True:
        time.sleep(0.05)


# --- the queue the dialog writes into ---------------------------------------------------------


class FakeStore:
    """An in-memory `JobStore` for the manager, and the rows `FakeSink` writes into."""

    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.writes: list[tuple[str, JobStatus]] = []
        self.completions: list[tuple[str, str | None]] = []

    def insert(self, job: Job) -> None:
        self.jobs[job.id] = job
        self.writes.append((job.id, job.status))

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def update(self, job: Job, done: Callable[[str | None], None] | None = None) -> None:
        """`ARC-005`'s asynchronous shape, completed synchronously."""
        if job.id not in self.jobs:
            raise KeyError(job.id)
        self.jobs[job.id] = job
        self.writes.append((job.id, job.status))
        if done is not None:
            done(None)

    def complete(
        self, job: Job, format_used: str | None, done: Callable[[str | None], None]
    ) -> None:
        """`JobStore.complete` — the job row and its history record, atomically (`T050-R1`).

        A fake, so "atomically" is trivial: one dict assignment cannot half-happen. What it
        preserves is the *shape* — one call, one settlement — so the manager cannot be
        written against two separate writes and still pass here.
        """
        self.completions.append((job.id, format_used))
        self.update(job, done)

    def statuses(self, job_id: str) -> list[JobStatus]:
        return [status for stored_id, status in self.writes if stored_id == job_id]

    def requeue_at_end(self, job: Any, done: Any) -> None:
        """Part of `JobStore` since `T-080`. Unused here; present so the fake satisfies it."""
        raise NotImplementedError

    def remove(self, job_id: str, done: Any) -> None:
        """Part of `JobStore` since `T-080`. Unused here; present so the fake satisfies it."""
        raise NotImplementedError

    def reorder(self, job_ids: Any, done: Any) -> None:
        """Part of `JobStore` since `T-081`. Unused here; present so the fake satisfies it."""
        raise NotImplementedError

    def clear_completed(self, done: Any) -> None:
        """Part of `JobStore` since `T-081`. Unused here; present so the fake satisfies it."""
        raise NotImplementedError


class FakeSink:
    """A `JobSink` whose completion the test controls.

    Zero-latency by default, because most tests are about the dialog's logic rather than about
    storage. `defer=True` holds every submission until `release()`, which is how the ordering
    claims — persist *before* close, probe only after the write lands — are asserted without a
    sleep.
    """

    def __init__(self, store: FakeStore) -> None:
        self._store = store
        self.defer = False
        self.error: str | None = None
        self.pending: list[tuple[list[Job], Callable[[str | None], None]]] = []
        self.submissions: list[list[Job]] = []

    def submit(self, jobs: Sequence[Job], done: Callable[[str | None], None]) -> None:
        batch = list(jobs)
        self.submissions.append(batch)
        if self.defer:
            self.pending.append((batch, done))
            return
        self._apply(batch, done)

    def release(self) -> None:
        pending, self.pending = self.pending, []
        for batch, done in pending:
            self._apply(batch, done)

    def _apply(self, jobs: list[Job], done: Callable[[str | None], None]) -> None:
        if self.error is not None:
            done(self.error)
            return
        start = len(self._store.jobs)
        for offset, job in enumerate(jobs):
            self._store.insert(replace(job, queue_position=start + offset))
        done(None)


class RecordingThumbnailLoader:
    """Hands over real image bytes without a network, and records what it was asked for."""

    def __init__(self, data: bytes | None) -> None:
        self._data = data
        self.requested: list[str] = []
        self.cancels = 0

    def load(self, url: str, done: Callable[[bytes | None], None]) -> None:
        self.requested.append(url)
        done(self._data)

    def cancel(self) -> None:
        self.cancels += 1


# --- fixtures ---------------------------------------------------------------------------------


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def sink(store: FakeStore) -> FakeSink:
    return FakeSink(store)


@pytest.fixture
def managers(store: FakeStore, qapp: QApplication) -> Iterator[Callable[..., DownloadManager]]:
    """Builds managers and guarantees they are shut down, whatever the test did.

    Teardown is not tidiness: a leaked worker would outlive the test and be attributed to
    whichever one ran next.
    """
    built: list[DownloadManager] = []

    def build(**overrides: Any) -> DownloadManager:
        manager = DownloadManager(store, **overrides)
        built.append(manager)
        return manager

    yield build

    for manager in built:
        manager.shutdown()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not all(m.is_idle for m in built):
        qapp.processEvents()
        time.sleep(0.005)
    assert all(m.is_idle for m in built), "a manager never finished shutting down"


@pytest.fixture
def thumbnails() -> RecordingThumbnailLoader:
    return RecordingThumbnailLoader(THUMBNAIL_SOURCE.read_bytes())


@pytest.fixture
def dialogs(
    sink: FakeSink,
    thumbnails: RecordingThumbnailLoader,
    tmp_path: Path,
    qapp: QApplication,
) -> Iterator[Callable[..., AddUrlDialog]]:
    """Builds dialogs and destroys them, so no widget outlives the test that made it."""
    built: list[AddUrlDialog] = []

    def build(manager: DownloadManager, **overrides: Any) -> AddUrlDialog:
        overrides.setdefault("jobs", sink)
        overrides.setdefault("thumbnail_loader", thumbnails)
        dialog = AddUrlDialog(manager=manager, output_directory=tmp_path / "downloads", **overrides)
        built.append(dialog)
        return dialog

    yield build

    for dialog in built:
        dialog.close()
        dialog.deleteLater()
    qapp.processEvents()


# --- reading the dialog through its object names ----------------------------------------------


def label(dialog: AddUrlDialog, name: str) -> QLabel:
    found = dialog.findChild(QLabel, name)
    assert found is not None, f"no QLabel named {name!r}"
    return found


def button(dialog: AddUrlDialog, name: str) -> QPushButton:
    found = dialog.findChild(QPushButton, name)
    assert found is not None, f"no QPushButton named {name!r}"
    return found


def text_of(dialog: AddUrlDialog, name: str) -> str:
    return label(dialog, name).text()


def type_urls(dialog: AddUrlDialog, text: str) -> None:
    box = dialog.findChild(QPlainTextEdit, "urlInput")
    assert box is not None
    box.setPlainText(text)


def choose_preset(dialog: AddUrlDialog, name: str) -> None:
    box = dialog.findChild(QComboBox, "presetChoice")
    assert box is not None
    box.setCurrentText(name)


def choose_bitrate(dialog: AddUrlDialog, kbps: str) -> None:
    box = dialog.findChild(QComboBox, "audioBitrateChoice")
    assert box is not None
    index = box.findData(kbps)
    assert index >= 0, f"no {kbps} kbps entry; offered {preset_registry.MP3_BITRATES}"
    box.setCurrentIndex(index)


def focusable_widgets(dialog: AddUrlDialog) -> list[QWidget]:
    """Every keyboard-focusable widget belonging to this dialog's own window.

    The only exclusion is by **window**, not by name: `QComboBox` owns a popup `QListView` that is
    focusable but lives in its own top-level window and is never in the dialog's tab chain.
    Excluding by name is what `T016-R4` found — the observation filtered to the declared subset,
    so undeclared focusable controls could not fail it.
    """
    return [
        widget
        for widget in dialog.findChildren(QWidget)
        if widget.focusPolicy() & Qt.FocusPolicy.TabFocus and widget.window() is dialog
    ]


def probe_of(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    name: str,
    entry_point: Any = child_replaying_a_fixture,
) -> tuple[AddUrlDialog, DownloadManager]:
    """Paste a fixture-backed URL, probe it, and return once the result has landed.

    The manager is spun to idle: a probe session is released a tick after its result is emitted,
    and Phase 1 runs a pool of exactly one, so a test that queued a download immediately would be
    refused for reasons that have nothing to do with what it asserts.
    """
    manager = managers(entry_point=entry_point)
    dialog = dialogs(manager)
    type_urls(dialog, fixture_url(name))
    dialog.probe()
    assert spin(lambda: dialog.media is not None), "the probe result never reached the dialog"
    assert spin(lambda: manager.is_idle), "the probe session was never released"
    return dialog, manager


def live_session_process(manager: DownloadManager, job_id: str) -> Any:
    """The worker process the manager is holding for `job_id`.

    Reads the manager's own record rather than searching the process table: the claim under test
    is that the manager left nothing behind, and its bookkeeping is what has to agree with the
    operating system.
    """
    return manager._sessions[job_id].process


def session_job_ids(manager: DownloadManager) -> tuple[str, ...]:
    """The jobs that actually have a worker — not the ones whose start is merely reserved.

    `active_job_ids()` reports both since `T016-R3`, because a reservation *is* work in flight
    and hiding it is what let shutdown announce `idle` and then spawn. A test about **worker
    construction** therefore has to ask about sessions specifically, or it would pass on a
    reservation and prove nothing about the process.
    """
    return tuple(manager._sessions)


# --- 1. what a probe shows (`REQ-002`) --------------------------------------------------------


def test_a_probe_populates_every_field_req_002_names(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    thumbnails: RecordingThumbnailLoader,
    spin: Callable[..., bool],
) -> None:
    """Field by field, because "populates the dialog" would pass with four of five missing."""
    info = load_info(SINGLE_ITEM)
    dialog, _ = probe_of(dialogs, managers, spin, SINGLE_ITEM)

    assert text_of(dialog, "titleValue") == info["title"] == "Big Buck Bunny"
    assert text_of(dialog, "uploaderValue") == info["uploader"] == "jake@archive.org"
    # 596.46 s. Truncated rather than rounded: rounding up to 9:57 would report a second that
    # does not exist.
    assert text_of(dialog, "durationValue") == "9:56"
    assert text_of(dialog, "kindValue") == "Single item"

    assert thumbnails.requested == [info["thumbnail"]]
    pixmap = dialog.thumbnail
    assert pixmap is not None and not pixmap.isNull()
    assert pixmap.width() > 0 and pixmap.height() > 0
    assert not label(dialog, "thumbnail").pixmap().isNull()
    assert text_of(dialog, "thumbnail") == ""


def test_a_playlist_is_shown_as_a_playlist_with_its_recorded_count(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`REQ-002`'s single-item-or-playlist distinction, which `T-018` made expressible."""
    info = load_info(PLAYLIST)
    dialog, _ = probe_of(dialogs, managers, spin, PLAYLIST)

    media = dialog.media
    assert media is not None and media.is_playlist
    assert media.entry_count == info["playlist_count"] == 7
    assert text_of(dialog, "kindValue") == "Playlist (7 items)"
    assert text_of(dialog, "titleValue") == "The Art of War"
    assert text_of(dialog, "durationValue") == UNKNOWN_TEXT
    assert dialog.thumbnail is None
    assert text_of(dialog, "thumbnail") == NO_THUMBNAIL_TEXT


def test_an_audio_only_url_is_probed_like_any_other(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """Audio is a first-class citizen, not video with something missing (`README`, `REQ-002`)."""
    dialog, _ = probe_of(dialogs, managers, spin, AUDIO_ONLY)
    assert text_of(dialog, "kindValue") == "Single item"
    assert text_of(dialog, "titleValue") not in ("", UNKNOWN_TEXT)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (None, UNKNOWN_TEXT),
        (0.0, "0:00"),
        (9.0, "0:09"),
        (596.46, "9:56"),
        (3600.0, "1:00:00"),
        (3661.0, "1:01:01"),
    ],
)
def test_duration_is_rendered_without_inventing_a_value(
    seconds: float | None, expected: str
) -> None:
    """`None` is not zero: a live stream has no duration, and `0:00` would be a lie about it."""
    assert format_duration(seconds) == expected


def test_a_playlist_of_unknown_length_says_so_rather_than_showing_zero() -> None:
    """`MediaInfo.entry_count` models unknown as `None`; "0 items" is not what that means."""
    unknown = MediaInfo(url="https://example.invalid/p", title="P", is_playlist=True)
    assert describe_kind(unknown) == "Playlist (item count unknown)"
    assert describe_kind(replace(unknown, entry_count=0)) == "Playlist (0 items)"


# --- 2. `T016-R1` (Critical): a result belongs to a URL, not just to a job id -----------------


def test_a_result_arriving_after_the_url_changed_is_never_accepted(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """The Critical defect, reproduced in the shape the reviewer reported it.

    A probe is started for the first URL, the user replaces that line before the worker answers,
    and the result then lands. Previously the dialog accepted it, `add_to_queue()` skipped the
    displayed URL because "a probe existed", and the only job started was the one the user had
    already replaced — downloading the wrong thing and silently dropping the right one.
    """
    manager = managers(entry_point=child_replaying_a_fixture)
    dialog = dialogs(manager)
    old = fixture_url(SINGLE_ITEM)
    type_urls(dialog, old)
    dialog.probe()
    old_job = dialog.probing_job_id
    assert old_job is not None

    type_urls(dialog, "https://new.invalid/wanted")

    # Whatever the worker does now, nothing about the old URL may reach the display.
    assert spin(lambda: manager.is_idle), "the superseded probe was left holding the pool"
    assert dialog.media is None
    assert dialog.probed_job_id is None
    assert text_of(dialog, "titleValue") == UNKNOWN_TEXT
    assert store.jobs[old_job].status is JobStatus.CANCELLED, (
        "the superseded probe's session was not cancelled"
    )

    dialog.add_to_queue()

    queued = [store.jobs[job_id] for job_id in dialog.queued_job_ids]
    assert "https://new.invalid/wanted" in [job.url for job in queued], (
        "the URL the user actually submitted was dropped"
    )
    started = [job for job in queued if job.status is not JobStatus.CANCELLED]
    assert [job.url for job in started] == ["https://new.invalid/wanted"]


def test_a_result_for_a_superseded_probe_is_ignored_even_if_it_arrives(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """The binding is a property of the result, not of one code path remembering to fire.

    `_on_media_probed` is called directly with the superseded job's id, which is what a signal
    already queued before the cancellation would do.
    """
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    type_urls(dialog, "https://old.invalid/x")
    dialog.probe()
    stale_job = dialog.probing_job_id
    assert stale_job is not None

    type_urls(dialog, "https://new.invalid/y")
    dialog._on_media_probed(stale_job, MediaInfo(url="https://old.invalid/x", title="STALE"))

    assert dialog.media is None
    assert text_of(dialog, "titleValue") == UNKNOWN_TEXT
    assert spin(lambda: manager.is_idle)


def test_adding_while_a_probe_is_outstanding_cannot_store_a_url_twice(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """The second edge of the same incomplete state model.

    `probe()` had already persisted the first URL, and `add_to_queue()` skipped it only once a
    *completed* probe existed — so pressing the still-enabled default button mid-probe stored the
    same line a second time. The state is now unreachable: Add is disabled while a probe is
    outstanding, and the method refuses as well.
    """
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    type_urls(dialog, "https://only.invalid/once")
    dialog.probe()
    assert dialog.probing_job_id is not None

    assert not button(dialog, "addButton").isEnabled(), "Add stays clickable during a probe"
    dialog.add_to_queue()

    urls = [store.jobs[job_id].url for job_id in dialog.queued_job_ids]
    assert urls.count("https://only.invalid/once") == 1, f"stored twice: {urls}"
    assert dialog.isVisible() is False or not dialog.result()
    assert spin(lambda: True)


def test_a_probed_url_is_not_stored_again_when_the_batch_is_added(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """`ARC-004`: reuse the probed record rather than stranding or duplicating it."""
    url = fixture_url(SINGLE_ITEM)
    dialog, _ = probe_of(dialogs, managers, spin, SINGLE_ITEM)
    type_urls(dialog, f"{url}\nhttps://second.invalid/2")

    dialog.add_to_queue()

    urls = [store.jobs[job_id].url for job_id in dialog.queued_job_ids]
    assert urls == [url, "https://second.invalid/2"], "the probed URL was queued twice"


def test_a_cancelled_probes_url_can_be_queued_again(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """Cancelling must not make a URL permanently unqueueable.

    The job the probe created is `CANCELLED`, which is terminal — so if the dialog kept counting
    that line as "already stored", Add would silently skip it and the user would lose the URL.
    """
    dialog = dialogs(managers(entry_point=child_never_returning))
    type_urls(dialog, "https://retry.invalid/x")
    dialog.probe()
    (cancelled,) = dialog.queued_job_ids
    dialog.cancel_probe()
    # Cancellation is a lifecycle, not a call: the manager escalates on its own timer, so the
    # job reaches CANCELLED some ticks later. Asserting before that would compare against a job
    # still in PROBING and pass for the wrong reason.
    assert spin(lambda: store.jobs[cancelled].status is JobStatus.CANCELLED, timeout=30)

    dialog.add_to_queue()

    live = [
        store.jobs[job_id]
        for job_id in dialog.queued_job_ids
        if store.jobs[job_id].status is not JobStatus.CANCELLED
    ]
    assert [job.url for job in live] == ["https://retry.invalid/x"]


def test_editing_the_url_after_a_completed_probe_discards_the_stale_result(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """The already-covered half: a finished probe is dropped when its line changes."""
    dialog, _ = probe_of(dialogs, managers, spin, SINGLE_ITEM)
    probed_before = dialog.probed_job_id
    assert probed_before is not None

    type_urls(dialog, "https://somewhere.else.invalid/x")

    assert dialog.probed_job_id is None
    assert dialog.media is None
    assert text_of(dialog, "titleValue") == UNKNOWN_TEXT
    assert text_of(dialog, "thumbnail") == NOT_PROBED_TEXT


def test_re_typing_the_same_url_keeps_the_probe_result(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """Appending a second line must not discard the first line's result."""
    url = fixture_url(SINGLE_ITEM)
    dialog, _ = probe_of(dialogs, managers, spin, SINGLE_ITEM)
    probed = dialog.probed_job_id

    type_urls(dialog, f"{url}\nhttps://second.invalid/2")

    assert dialog.probed_job_id == probed
    assert dialog.media is not None


# --- 3. `T016-R2` (High): closing abandons the probe ------------------------------------------


def test_closing_the_dialog_cancels_an_outstanding_probe(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """A never-returning child, closed rather than cancelled, must still leave nothing behind.

    Previously the worker stayed alive and the pool-of-one manager stayed busy forever, with the
    only cancel control now hidden — so every later dialog could report nothing but "a session is
    already running".
    """
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    type_urls(dialog, "https://example.invalid/never")
    dialog.probe()
    job_id = dialog.probing_job_id
    assert job_id is not None
    process = live_session_process(manager, job_id)
    assert spin(lambda: process.pid is not None)

    dialog.reject()

    assert spin(lambda: manager.is_idle, timeout=30), "the session outlived the dialog"
    assert not process.is_alive(), "the worker outlived the dialog that started it"
    assert store.jobs[job_id].status is JobStatus.CANCELLED


def test_a_later_dialog_can_still_probe_after_one_is_closed_mid_probe(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """The consequence the finding is really about: the feature must not be dead afterwards."""
    manager = managers(entry_point=child_replaying_a_fixture)
    first = dialogs(manager)
    type_urls(first, "https://example.invalid/never")
    first.probe()
    first.reject()
    assert spin(lambda: manager.is_idle, timeout=30)

    second = dialogs(manager)
    type_urls(second, fixture_url(SINGLE_ITEM))
    second.probe()

    assert spin(lambda: second.media is not None), (
        "a closed dialog left the manager unusable for the next one"
    )


@pytest.mark.parametrize("route", ["reject", "close", "done"])
def test_every_exit_route_abandons_the_probe(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    route: str,
) -> None:
    """Escape, the window button and `reject()` all reach `done()`, so all three are covered.

    **Shown first, deliberately.** `QWidget.close()` on a widget that was never visible returns
    without delivering a close event, so a hidden dialog would take no route at all and the
    `close` case would pass for the wrong reason. A user closes a window they can see.
    """
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    dialog.show()
    type_urls(dialog, "https://example.invalid/never")
    dialog.probe()
    assert dialog.probing_job_id is not None

    routes: dict[str, Callable[[], object]] = {
        "reject": dialog.reject,
        "close": dialog.close,
        "done": lambda: dialog.done(0),
    }
    routes[route]()

    assert spin(lambda: manager.is_idle, timeout=30), f"{route}() left the session running"


def a_queued_job(url: str) -> Job:
    """A minimal `QUEUED` job, for tests that drive the store directly."""
    return Job(
        id=f"job-{uuid.uuid4()}",
        url=url,
        request=DownloadRequest(
            url=url,
            output_directory=str(REPO_ROOT / "not-written-to"),
            format_selector="best",
            output_template="%(title)s.%(ext)s",
        ),
        status=JobStatus.QUEUED,
    )


# --- 3b. `T016-R1`/`T016-R2`: the window while the row is still being written -----------------


def test_editing_during_a_pending_probe_save_leaves_no_live_job_for_the_old_url(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    sink: FakeSink,
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """The Critical defect's remaining window (`T016-R1`).

    Between `probe()` and its write landing, `started` is false — so the earlier correction could
    neither cancel the probe nor refuse its result, and the callback simply recorded the row.
    Under a real held lock the reviewer watched the replaced URL stay durably `QUEUED`, where
    whatever runs the queue next would download the thing the user had taken away.
    """
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    sink.defer = True
    type_urls(dialog, "https://old.invalid/unwanted")
    dialog.probe()
    assert dialog.probing_job_id is None, "the worker started before the row was written"

    type_urls(dialog, "https://new.invalid/wanted")
    sink.release()

    assert spin(lambda: manager.is_idle)
    live = [job for job in store.jobs.values() if job.status is not JobStatus.CANCELLED]
    assert [job.url for job in live] == [], (
        f"the replaced URL survived as live queued work: {[job.url for job in live]}"
    )
    assert dialog.media is None
    assert dialog.probing_job_id is None


def test_adding_after_editing_during_a_pending_save_queues_only_what_is_displayed(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    sink: FakeSink,
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """The reviewer's second observation: adding afterwards left **both** rows queued."""
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    sink.defer = True
    type_urls(dialog, "https://old.invalid/unwanted")
    dialog.probe()
    type_urls(dialog, "https://new.invalid/wanted")
    sink.release()
    assert spin(lambda: manager.is_idle)

    sink.defer = False
    dialog.add_to_queue()

    live = [job for job in store.jobs.values() if job.status is not JobStatus.CANCELLED]
    assert [job.url for job in live] == ["https://new.invalid/wanted"]


def test_closing_during_a_pending_probe_save_starts_no_worker(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    sink: FakeSink,
    spin: Callable[..., bool],
) -> None:
    """`T016-R2`: the callback must not create a worker for a dialog that has closed.

    The committed close tests all waited for `probing_job_id`, which put them *after* the write —
    so this lifecycle stage had no coverage at all, and releasing the save produced one start and
    zero cancellations.
    """
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    dialog.show()
    sink.defer = True
    type_urls(dialog, "https://example.invalid/never")
    dialog.probe()

    dialog.reject()
    sink.release()

    assert manager.is_idle, "a worker was started for a dialog that had already closed"
    assert spin(lambda: manager.is_idle, timeout=30)


@pytest.mark.parametrize("route", ["reject", "close", "done"])
def test_every_exit_route_survives_a_pending_probe_save(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    sink: FakeSink,
    spin: Callable[..., bool],
    route: str,
) -> None:
    """And a later dialog can still probe — the consequence the finding is about."""
    manager = managers(entry_point=child_replaying_a_fixture)
    dialog = dialogs(manager)
    dialog.show()
    sink.defer = True
    type_urls(dialog, "https://example.invalid/never")
    dialog.probe()

    routes: dict[str, Callable[[], object]] = {
        "reject": dialog.reject,
        "close": dialog.close,
        "done": lambda: dialog.done(0),
    }
    routes[route]()
    sink.release()
    assert spin(lambda: manager.is_idle, timeout=30), f"{route}() left a session running"

    sink.defer = False
    second = dialogs(manager)
    type_urls(second, fixture_url(SINGLE_ITEM))
    second.probe()
    assert spin(lambda: second.media is not None), "the manager was left unusable"


def test_two_identical_lines_are_two_jobs_even_when_one_was_probed(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """`REQ-001` and `split_urls` agree that two identical lines are two requests (`T016-R1`).

    `_Persisted` was keyed by URL *membership*, so once a probe had stored one occurrence, Add
    skipped every line with that text and one entry silently vanished.
    """
    url = fixture_url(SINGLE_ITEM)
    dialog, _ = probe_of(dialogs, managers, spin, SINGLE_ITEM)
    type_urls(dialog, f"{url}\n{url}")

    dialog.add_to_queue()

    stored = [store.jobs[job_id].url for job_id in dialog.queued_job_ids]
    assert stored == [url, url], f"two identical lines produced {stored}"


# --- 4. `T016-R3` (High): nothing waits on SQLite ---------------------------------------------


@pytest.fixture
def real_queue(
    tmp_path: Path, qapp: QApplication, spin: Callable[..., bool]
) -> Iterator[tuple[PersistentJobStore, JobRepository]]:
    """The concrete persistence stack: one writer thread, one store, one read connection.

    What composition (`T-036`) will build. The store is both the dialog's `JobSink` and the
    manager's `JobStore`, which is `ARC-005`'s "one persistence owner" — giving them separate
    owners is how the manager's writes stayed synchronous while the dialog's moved (`T016-R3`).
    """
    path = tmp_path / "queue.db"
    connection = connect(path)
    writer = QueueWriter(lambda: connect(path))
    try:
        yield PersistentJobStore(connection, writer), JobRepository(connection)
    finally:
        writer.close()
        assert spin(lambda: not writer.is_running, timeout=30), "the writer thread never quit"
        connection.close()
        qapp.processEvents()


def test_closing_the_writer_does_not_block_the_gui_thread(
    real_queue: tuple[PersistentJobStore, JobRepository],
    tmp_path: Path,
    spin: Callable[..., bool],
) -> None:
    """Shutdown is a lifecycle, not a call (`T016-R3`, and `T013-R2` before it).

    A contended write is submitted and the lock held, so the writer thread is genuinely stuck
    inside SQLite when `close()` is asked for. The previous `QThread.wait(5000)` held the GUI
    thread here for a measured 4.921 s.
    """
    store, _ = real_queue
    blocker = sqlite3.connect(tmp_path / "queue.db")
    blocker.execute("BEGIN IMMEDIATE")
    answers: list[str | None] = []
    try:
        store.submit([a_queued_job("https://a.invalid/1")], answers.append)

        started = time.monotonic()
        store._writer.close()
        elapsed = time.monotonic() - started
        assert elapsed < INTERACTION_BUDGET_SECONDS, (
            f"close() held the GUI thread for {elapsed:.3f}s while a write was contended"
        )
    finally:
        blocker.rollback()
        blocker.close()

    assert spin(lambda: not store._writer.is_running, timeout=30), "the thread never finished"
    assert answers, "the submitted write was never answered"


def test_adding_never_blocks_the_gui_thread_on_a_contended_database(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    real_queue: tuple[PersistentJobStore, JobRepository],
    tmp_path: Path,
    spin: Callable[..., bool],
) -> None:
    """The concrete repository, under a genuinely held writer lock (`ARC-005`).

    The reviewer measured 0.302 s of blocked GUI thread and then an `OperationalError`. Here a
    second connection holds SQLite's write lock outright; `add_to_queue()` must still return
    within an interaction budget, and the write must land once the lock is released.
    """
    store_under_test, repository = real_queue
    dialog = dialogs(managers(entry_point=child_never_returning), jobs=store_under_test)
    type_urls(dialog, "https://a.invalid/1\nhttps://b.invalid/2\nhttps://c.invalid/3")

    blocker = sqlite3.connect(tmp_path / "queue.db")
    blocker.execute("BEGIN IMMEDIATE")
    try:
        started = time.monotonic()
        dialog.add_to_queue()
        elapsed = time.monotonic() - started
        assert elapsed < INTERACTION_BUDGET_SECONDS, (
            f"add_to_queue() held the GUI thread for {elapsed:.3f}s under contention"
        )
        assert dialog.is_saving, "the write was not actually outstanding"
        assert dialog.isVisible() is False or not dialog.result()
    finally:
        blocker.rollback()
        blocker.close()

    assert spin(lambda: not dialog.is_saving, timeout=30), "the deferred write never completed"
    stored = sorted(job.url for job in repository.all_jobs())
    assert stored == ["https://a.invalid/1", "https://b.invalid/2", "https://c.invalid/3"]
    assert sorted(job.queue_position or 0 for job in repository.all_jobs()) == [0, 1, 2]


def test_the_integrated_probe_path_never_blocks_or_raises_under_contention(
    dialogs: Callable[..., AddUrlDialog],
    real_queue: tuple[PersistentJobStore, JobRepository],
    tmp_path: Path,
    qapp: QApplication,
    spin: Callable[..., bool],
) -> None:
    """The concrete flow the reviewer reproduced, end to end (`T016-R3`).

    Writer commits the probe row → its GUI callback runs → that callback reaches
    `DownloadManager.start()`, which persists `QUEUED → PROBING`. With another connection holding
    the writer lock, that transition blocked the GUI event loop for **5.017 s** and then raised an
    uncaught `sqlite3.OperationalError` out of the writer's completion slot, because `ARC-005`
    had been implemented for appends only.

    Nothing is faked here: real writer thread, real store, real manager, real repository, real
    lock. The assertion is that the event loop keeps turning and no exception escapes a slot.
    """
    store_under_test, repository = real_queue
    manager = DownloadManager(store_under_test, entry_point=child_never_returning)
    dialog = dialogs(manager, jobs=store_under_test)
    escaped: list[BaseException] = []

    def record(kind: type[BaseException], value: BaseException, traceback: object) -> None:
        escaped.append(value)

    original, sys.excepthook = sys.excepthook, record
    blocker = sqlite3.connect(tmp_path / "queue.db")
    try:
        type_urls(dialog, "https://contended.invalid/x")
        dialog.probe()

        # **The lock has to be taken between the append committing and its callback running.**
        # An earlier version waited for the callback first, by which time `start()` had already
        # issued the status write — so nothing was contended, and the mutation restoring the
        # synchronous write survived. So: poll the database *without* processing events, which
        # leaves the queued callback undelivered, and only then take the lock.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not repository.all_jobs():
            time.sleep(0.005)
        stored = repository.all_jobs()
        assert stored, "the appended row never landed"
        job_id = stored[0].id
        assert stored[0].status is JobStatus.QUEUED
        blocker.execute("BEGIN IMMEDIATE")

        # Now deliver the callback. It reaches `DownloadManager.start()`, which persists
        # `QUEUED -> PROBING` against a lock somebody else is holding.
        started = time.monotonic()
        for _ in range(20):
            qapp.processEvents()
            time.sleep(0.005)
        elapsed = time.monotonic() - started
        assert dialog.probing_job_id is not None, "the probe never started; nothing was contended"
        assert elapsed < INTERACTION_BUDGET_SECONDS, (
            f"the event loop was held for {elapsed:.3f}s by a contended status write"
        )
    finally:
        blocker.rollback()
        blocker.close()
        sys.excepthook = original
        manager.shutdown()
        assert spin(lambda: manager.is_idle, timeout=30)

    assert not escaped, f"an exception escaped a slot: {escaped}"
    assert spin(
        lambda: (job := repository.get(job_id)) is not None and job.status is not JobStatus.QUEUED,
        timeout=30,
    ), "the status transition never reached disk once the lock was released"


def test_no_worker_exists_while_the_row_still_says_queued(
    dialogs: Callable[..., AddUrlDialog],
    real_queue: tuple[PersistentJobStore, JobRepository],
    tmp_path: Path,
    qapp: QApplication,
    spin: Callable[..., bool],
) -> None:
    """Persistence gates worker construction, read from the concrete row (`T016-R3`).

    The previous correction moved `job_changed` into the write's callback and left everything
    else on the synchronous path, so the process and the pump started while SQLite still said
    `QUEUED`. Asserted against the repository — not the write-through view, which by design
    already shows the pending state.
    """
    store_under_test, repository = real_queue
    manager = DownloadManager(store_under_test, entry_point=child_never_returning)
    dialog = dialogs(manager, jobs=store_under_test)
    type_urls(dialog, "https://gated.invalid/x")
    dialog.probe()

    # Wait for the append without pumping events, so the start's transition is the contended one.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not repository.all_jobs():
        time.sleep(0.005)
    stored = repository.all_jobs()
    assert stored and stored[0].status is JobStatus.QUEUED
    job_id = stored[0].id

    blocker = sqlite3.connect(tmp_path / "queue.db")
    blocker.execute("BEGIN IMMEDIATE")
    try:
        for _ in range(20):
            qapp.processEvents()
            time.sleep(0.005)
        on_disk = repository.get(job_id)
        assert on_disk is not None and on_disk.status is JobStatus.QUEUED, (
            "the contended transition somehow landed; this proves nothing"
        )
        assert session_job_ids(manager) == (), (
            "a worker was constructed while the row still said queued"
        )
        assert manager.active_job_ids() == (job_id,), (
            "the reserved start is still owned, and has to be reported as such (T016-R3)"
        )
    finally:
        blocker.rollback()
        blocker.close()

    assert spin(lambda: session_job_ids(manager) != (), timeout=30), (
        "the session never started once the transition became durable"
    )
    landed = repository.get(job_id)
    assert landed is not None and landed.status is JobStatus.PROBING
    manager.shutdown()
    assert spin(lambda: manager.is_idle, timeout=30)
    qapp.processEvents()


def test_the_store_reflects_a_write_it_has_only_queued(
    real_queue: tuple[PersistentJobStore, JobRepository],
    tmp_path: Path,
    spin: Callable[..., bool],
) -> None:
    """Read-your-writes, asserted while the write is demonstrably still pending (`ARC-005`).

    This obligation is what let `ARC-005` land without restructuring ten call sites of approved
    `T-013` code: `DownloadManager` reads a job back immediately before advancing it, so a store
    answering from disk alone would hand it the state it had just replaced. Asserted under a held
    lock, because against a fast writer the read would pass either way.
    """
    store_under_test, repository = real_queue
    job = a_queued_job("https://a.invalid/1")
    saved: list[str | None] = []
    store_under_test.submit([job], saved.append)
    assert spin(lambda: bool(saved), timeout=30)
    assert saved == [None]

    blocker = sqlite3.connect(tmp_path / "queue.db")
    blocker.execute("BEGIN IMMEDIATE")
    try:
        store_under_test.update(replace(job, status=JobStatus.PROBING), lambda _error: None)

        on_disk = repository.get(job.id)
        assert on_disk is not None and on_disk.status is JobStatus.QUEUED, (
            "the write reached disk, so this proves nothing about a pending one"
        )
        seen = store_under_test.get(job.id)
        assert seen is not None and seen.status is JobStatus.PROBING, (
            "the store did not reflect a write it had accepted but not yet completed"
        )
    finally:
        blocker.rollback()
        blocker.close()


def test_a_withdrawal_that_cannot_be_written_blocks_the_dialog_and_is_retryable(
    dialogs: Callable[..., AddUrlDialog],
    real_queue: tuple[PersistentJobStore, JobRepository],
    tmp_path: Path,
    qapp: QApplication,
    spin: Callable[..., bool],
) -> None:
    """The Critical consequence, gated against the concrete repository (`T016-R1`).

    A probe's row is durable; the user replaces the URL; the cancellation that withdraws it
    cannot be written because another connection holds the lock. Previously the dialog said only
    "The URL changed", the write-through view claimed `CANCELLED`, and SQLite still held the row
    as `QUEUED` — so a restart, which has no view, brought the replaced URL back as live work.

    Everything below is read from the **repository**, and the final check opens a **fresh store**
    to stand in for that restart.

    The lock is taken between the append landing and its callback being delivered, which is what
    makes this deterministic: an earlier version waited for the probe to be running first, so
    whether the status write had already succeeded depended on machine load.
    """
    store_under_test, repository = real_queue
    manager = DownloadManager(store_under_test, entry_point=child_never_returning)
    dialog = dialogs(manager, jobs=store_under_test)
    type_urls(dialog, "https://old.invalid/unwanted")
    dialog.probe()

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not repository.all_jobs():
        time.sleep(0.005)
    stored = repository.all_jobs()
    assert stored, "the appended row never landed"
    job_id = stored[0].id
    assert stored[0].status is JobStatus.QUEUED

    blocker = sqlite3.connect(tmp_path / "queue.db")
    blocker.execute("BEGIN IMMEDIATE")
    try:
        # Deliver the append callback: the dialog starts its probe and the manager's `PROBING`
        # write is issued against the held lock.
        assert spin(lambda: dialog.probing_job_id is not None, timeout=30)

        type_urls(dialog, "https://new.invalid/wanted")
        assert spin(lambda: dialog.withdraw_failed is not None, timeout=60), (
            "the failed withdrawal was never surfaced"
        )
        assert dialog.withdrawing == (job_id,)
        assert not button(dialog, "addButton").isEnabled()
        assert WITHDRAW_FAILED_PREFIX in dialog.status_text(), (
            f"the failure was not stated in words: {dialog.status_text()!r}"
        )

        # Close retries rather than closing, which is the visible progress the finding asked for.
        dialog.reject()
        assert dialog.withdrawing == (job_id,), "the dialog gave up on the withdrawal"
        assert "Retrying" in dialog.status_text()

        on_disk = repository.get(job_id)
        assert on_disk is not None and on_disk.status is not JobStatus.CANCELLED
    finally:
        blocker.rollback()
        blocker.close()

    dialog.retry_withdrawals()
    assert spin(lambda: not dialog.withdrawing, timeout=60), "the retry never succeeded"

    # A restart has no in-memory view. This is the read that previously exposed live work.
    fresh_connection = connect(tmp_path / "queue.db")
    try:
        restarted = JobRepository(fresh_connection).get(job_id)
        assert restarted is not None
        assert restarted.status is JobStatus.CANCELLED, (
            f"a fresh reader still sees the replaced URL as {restarted.status.value}"
        )
    finally:
        fresh_connection.close()
    manager.shutdown()
    assert spin(lambda: manager.is_idle, timeout=30)
    qapp.processEvents()


def test_a_failed_write_keeps_the_dialog_open_with_the_input_intact(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    sink: FakeSink,
    spin: Callable[..., bool],
) -> None:
    """Persistence failure is surfaced, not swallowed, and costs the user nothing typed."""
    dialog = dialogs(managers(entry_point=child_never_returning))
    sink.error = "OperationalError: database is locked"
    type_urls(dialog, "https://a.invalid/1\nhttps://b.invalid/2")

    dialog.add_to_queue()

    assert "database is locked" in dialog.status_text()
    assert dialog.queued_job_ids == ()
    box = dialog.findChild(QPlainTextEdit, "urlInput")
    assert box is not None
    assert box.toPlainText() == "https://a.invalid/1\nhttps://b.invalid/2"
    assert not dialog.is_saving
    assert button(dialog, "addButton").isEnabled(), "the user cannot retry"
    assert spin(lambda: True)


def test_the_dialog_closes_only_after_the_rows_exist(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    sink: FakeSink,
    store: FakeStore,
) -> None:
    """`REQ-012`, strengthened by `ARC-005`: close happens *inside* the success callback.

    The write is held open, so if the dialog could close before the rows existed it would do so
    here — the ordering is asserted against a write that has demonstrably not completed yet.
    """
    dialog = dialogs(managers(entry_point=child_never_returning))
    dialog.show()
    sink.defer = True
    type_urls(dialog, "https://a.invalid/1\nhttps://b.invalid/2")

    dialog.add_to_queue()
    assert dialog.isVisible(), "the dialog closed before its jobs were stored"
    assert store.jobs == {}

    stored_when_accepted: list[int] = []
    dialog.accepted.connect(lambda: stored_when_accepted.append(len(store.jobs)))
    sink.release()

    assert stored_when_accepted == [2], "accepted fired without both rows written"
    assert not dialog.isVisible()


def test_a_probe_starts_no_worker_until_its_job_is_stored(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    sink: FakeSink,
    store: FakeStore,
) -> None:
    """The same ordering on the probe path (`REQ-012`)."""
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    sink.defer = True
    type_urls(dialog, fixture_url(SINGLE_ITEM))

    dialog.probe()
    assert store.jobs == {}
    assert manager.is_idle, "a worker was started for a job that was not stored"
    assert dialog.probing_job_id is None

    sink.release()
    assert len(store.jobs) == 1
    assert dialog.probing_job_id is not None


def test_one_paste_is_one_transaction(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    sink: FakeSink,
) -> None:
    """A batch is submitted once, not once per URL (`ARC-005`).

    The previous shape performed a `SELECT` and an `INSERT` with its own commit per line, which is
    what made a large paste's cost unbounded in round trips.
    """
    dialog = dialogs(managers(entry_point=child_never_returning))
    type_urls(dialog, "\n".join(f"https://a.invalid/{index}" for index in range(25)))

    dialog.add_to_queue()

    assert len(sink.submissions) == 1
    assert len(sink.submissions[0]) == 25


# --- 5. the GUI thread is never blocked (`NFR-001`) -------------------------------------------


def test_the_dialog_stays_responsive_while_a_probe_is_outstanding(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    qapp: QApplication,
) -> None:
    """`probe()` returns without waiting, and slots still fire while a worker is outstanding."""
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    type_urls(dialog, "https://example.invalid/never")

    started = time.monotonic()
    dialog.probe()
    elapsed = time.monotonic() - started
    assert elapsed < INTERACTION_BUDGET_SECONDS, f"probe() blocked for {elapsed:.3f}s"
    assert dialog.probing_job_id is not None, "the probe was not actually outstanding"

    for _ in range(5):
        qapp.processEvents()
        assert dialog.probing_job_id is not None
        assert dialog.isEnabled()

    before = text_of(dialog, "selectorValue")
    choose_preset(dialog, BUILT_IN_PRESETS[2].name)
    qapp.processEvents()
    after = text_of(dialog, "selectorValue")
    assert after != before
    assert effective_selector(BUILT_IN_PRESETS[2]) in after
    assert dialog.probing_job_id is not None, "the probe finished; this proved nothing"


# --- 6. the extractor's own words (`REQ-005`, `NFR-006`) --------------------------------------


def test_an_unsupported_url_shows_the_extractors_message_character_for_character(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """Equality against the recorded message, not a substring and not a paraphrase."""
    recorded = load_error("unsupported_url")
    dialog = dialogs(managers(entry_point=child_failing_as_recorded))
    type_urls(dialog, "https://example.com/")
    dialog.probe()

    assert spin(lambda: recorded["message"] in dialog.status_text()), dialog.status_text()

    kind_line, _, message = dialog.status_text().partition("\n")
    assert message == recorded["message"] == "Unsupported URL: https://example.com/"
    assert kind_line == ErrorKind.UNSUPPORTED_URL.value
    assert dialog.media is None
    assert dialog.probed_job_id is None
    assert text_of(dialog, "titleValue") == UNKNOWN_TEXT


def test_a_failed_probe_leaves_the_job_failed_and_recorded(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """`REQ-018`: a failure is recorded, never assumed away, and the URL stays in the queue."""
    dialog = dialogs(managers(entry_point=child_failing_as_recorded))
    type_urls(dialog, "https://example.com/")
    dialog.probe()
    assert spin(lambda: dialog.probing_job_id is None)

    (job_id,) = dialog.queued_job_ids
    assert spin(lambda: store.jobs[job_id].status is JobStatus.FAILED)
    stored = store.jobs[job_id]
    assert stored.error_kind is ErrorKind.UNSUPPORTED_URL
    assert stored.error_message == load_error("unsupported_url")["message"]


# --- 7. `T016-R6`: site text is data, never markup --------------------------------------------


@pytest.mark.parametrize("name", ["titleValue", "uploaderValue", "statusMessage", "selectorValue"])
def test_labels_that_show_foreign_text_are_plain_text(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    name: str,
) -> None:
    """The property, asserted directly: Qt's default `AutoText` guesses, and guessed wrong."""
    dialog = dialogs(managers(entry_point=child_never_returning))
    assert label(dialog, name).textFormat() == Qt.TextFormat.PlainText


def test_a_markup_shaped_title_is_displayed_and_not_interpreted(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    qapp: QApplication,
) -> None:
    """Asserted on what is **rendered**, not on `QLabel.text()`.

    Reading the text back returns the input under either format, which is why the defect survived
    the first round of tests entirely.

    **The comparison is the same widget against itself**, with only the text format changed. An
    earlier version compared `sizeHint().width()` against a font-metrics advance and passed on
    Linux by luck: the label wraps, so its size hint is a wrapped-layout figure rather than a
    string width, and on Windows the numbers landed the other way round. Rendering the identical
    widget — same geometry, same font, same string — under each format removes every variable
    except the one under test, and proves the setting is load-bearing rather than merely present.
    """
    manager = managers(entry_point=child_probing_a_markup_title)
    dialog = dialogs(manager)
    dialog.show()
    type_urls(dialog, "https://markup.invalid/x")
    dialog.probe()
    assert spin(lambda: dialog.media is not None)

    title = label(dialog, "titleValue")
    assert title.text() == "<b>VISIBLE</b>"

    # Room to draw the difference. On the Windows runner the laid-out label came out 84 px wide,
    # narrow enough that both renderings clipped to the same pixels and the comparison below
    # could not fail — the second way this assertion found to be vacuous. The width is set here
    # rather than assumed, so the observation does not depend on how a platform lays the dialog
    # out.
    title.setWordWrap(False)
    title.resize(600, 40)
    qapp.processEvents()

    as_shipped = title.grab().toImage()
    title.setTextFormat(Qt.TextFormat.RichText)
    as_markup = title.grab().toImage()
    title.setTextFormat(Qt.TextFormat.PlainText)

    assert as_shipped.size() == as_markup.size(), (
        "the two renderings were not compared like for like"
    )
    assert as_shipped != as_markup, (
        "the title renders identically whether or not Qt is told to interpret markup, so the "
        "tags are being consumed rather than displayed"
    )
    assert title.grab().toImage() == as_shipped


# --- 8. `T016-R5`: the thumbnail's failure half -----------------------------------------------


def test_a_failed_thumbnail_fetch_stops_claiming_to_be_loading(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """An expired or offline thumbnail is ordinary; a permanent "Loading…" is a false state."""
    manager = managers(entry_point=child_replaying_a_fixture)
    dialog = dialogs(manager, thumbnail_loader=RecordingThumbnailLoader(None))
    type_urls(dialog, fixture_url(SINGLE_ITEM))
    dialog.probe()
    assert spin(lambda: dialog.media is not None)

    assert dialog.thumbnail is None
    assert text_of(dialog, "thumbnail") == THUMBNAIL_FAILED_TEXT
    assert text_of(dialog, "thumbnail") != LOADING_THUMBNAIL_TEXT


def test_undecodable_thumbnail_bytes_are_reported_as_unavailable(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """Bytes that arrive but are not an image are the same thing to a user: no picture."""
    manager = managers(entry_point=child_replaying_a_fixture)
    dialog = dialogs(manager, thumbnail_loader=RecordingThumbnailLoader(b"not an image"))
    type_urls(dialog, fixture_url(SINGLE_ITEM))
    dialog.probe()
    assert spin(lambda: dialog.media is not None)

    assert dialog.thumbnail is None
    assert text_of(dialog, "thumbnail") == THUMBNAIL_FAILED_TEXT


@pytest.fixture
def shipping_loader(qapp: QApplication) -> Iterator[NetworkThumbnailLoader]:
    """The real loader, owned for exactly as long as the test.

    Parented and explicitly torn down because it holds a `QNetworkAccessManager` and a live
    reply: letting a local go out of scope while a request is in flight segfaults the
    interpreter, which is how the first version of these two tests ended.
    """
    owner = QWidget()
    loader = NetworkThumbnailLoader(owner)
    yield loader
    loader.cancel()
    qapp.processEvents()
    owner.deleteLater()
    qapp.processEvents()


def test_the_shipping_loader_reports_a_failed_fetch(
    shipping_loader: NetworkThumbnailLoader, spin: Callable[..., bool], tmp_path: Path
) -> None:
    """The **shipping** `QNetworkAccessManager` loader, not a stand-in that can only succeed.

    A `file://` URL to a path that does not exist: a real request through the real stack, with a
    real error, and no network. The seam is honest only if the thing behind it reports both
    outcomes — `T016-R5` was precisely the missing one.
    """
    answers: list[bytes | None] = []
    shipping_loader.load((tmp_path / "absent.png").as_uri(), answers.append)

    assert spin(lambda: bool(answers), timeout=10), "the shipping loader never called back"
    assert answers == [None]


def test_the_shipping_loader_delivers_bytes_it_can_read(
    shipping_loader: NetworkThumbnailLoader, spin: Callable[..., bool], tmp_path: Path
) -> None:
    """The success half, through the same real stack, so the failure test is not vacuous."""
    image = tmp_path / "present.png"
    image.write_bytes(THUMBNAIL_SOURCE.read_bytes())
    answers: list[bytes | None] = []
    shipping_loader.load(image.as_uri(), answers.append)

    assert spin(lambda: bool(answers), timeout=10)
    assert answers[0] == THUMBNAIL_SOURCE.read_bytes()


# --- 9. multi-line paste (`REQ-001`) ----------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", []),
        ("   \n\t\n", []),
        ("https://a.invalid/1", ["https://a.invalid/1"]),
        (
            "  https://a.invalid/1  \n\nhttps://b.invalid/2\n",
            ["https://a.invalid/1", "https://b.invalid/2"],
        ),
        (
            "https://a.invalid/1\nhttps://a.invalid/1",
            ["https://a.invalid/1", "https://a.invalid/1"],
        ),
    ],
)
def test_urls_are_split_one_per_line(text: str, expected: list[str]) -> None:
    """Duplicates are kept: two identical lines are two things the user asked for."""
    assert split_urls(text) == expected


def test_multi_line_paste_queues_each_url_as_a_separate_job(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
) -> None:
    """`REQ-001`: three lines, three jobs, each carrying its own URL and its own request."""
    dialog = dialogs(managers(entry_point=child_never_returning))
    urls = ["https://a.invalid/1", "https://b.invalid/2", "https://c.invalid/3"]
    type_urls(dialog, "\n".join(urls))

    dialog.add_to_queue()

    queued = [store.jobs[job_id] for job_id in dialog.queued_job_ids]
    assert [job.url for job in queued] == urls
    assert [job.request.url for job in queued] == urls
    assert len({job.id for job in queued}) == 3
    assert all(job.status is JobStatus.QUEUED for job in queued)
    assert len({job.queue_position for job in queued}) == 3


def test_the_chosen_preset_reaches_every_queued_job(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
) -> None:
    """`REQ-009`: the selector the user was shown is the one the job carries."""
    dialog = dialogs(managers(entry_point=child_never_returning))
    type_urls(dialog, "https://a.invalid/1\nhttps://b.invalid/2")
    chosen = BUILT_IN_PRESETS[2]
    choose_preset(dialog, chosen.name)

    assert effective_selector(chosen) in text_of(dialog, "selectorValue")
    dialog.add_to_queue()

    for job_id in dialog.queued_job_ids:
        request = store.jobs[job_id].request
        assert request.format_selector == effective_selector(chosen)
        assert request.media_kind is chosen.media_kind
        assert request.audio_codec is chosen.audio_codec


# --- 10. the two entry points (`ARC-004`) -----------------------------------------------------


def test_the_chosen_bitrate_is_what_gets_stored(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """`T-076`, `REQ-010`: the MP3 bitrate is the user's to choose, not the preset's to fix.

    Asserted at 320 rather than at the default, so a control that is wired to nothing cannot pass
    by accident — which is what "it stores 192" would have proved about a dialog that ignored the
    box entirely.
    """
    dialog = dialogs(managers())
    type_urls(dialog, "https://example.invalid/clip")
    choose_preset(dialog, "Audio only (MP3)")
    choose_bitrate(dialog, "320")

    dialog.add_to_queue()
    assert spin(lambda: bool(dialog.queued_job_ids))

    (job_id,) = dialog.queued_job_ids
    stored = store.jobs[job_id].request
    assert stored.audio_quality == "320"
    assert stored.audio_codec is AudioCodec.MP3


def test_the_bitrate_is_offered_only_where_it_applies(
    dialogs: Callable[..., AddUrlDialog], managers: Callable[..., DownloadManager]
) -> None:
    """A control that cannot change the outcome must not invite a choice (`NFR-005`).

    The video presets do not convert audio, so a bitrate has nothing to apply to — and
    `with_audio_quality` refuses one rather than accepting a number it would drop. Disabled rather
    than hidden, so the layout does not move under a user who is reading it.
    """
    dialog = dialogs(managers())
    box = dialog.findChild(QComboBox, "audioBitrateChoice")
    assert box is not None

    choose_preset(dialog, "Best video available")
    assert not box.isEnabled()

    choose_preset(dialog, "Audio only (MP3)")
    assert box.isEnabled()

    # The original-audio preset keeps the source codec, so there is nothing to convert *to*.
    choose_preset(dialog, "Audio only (original)")
    assert not box.isEnabled()


def test_what_is_displayed_includes_the_bitrate_that_will_run(
    dialogs: Callable[..., AddUrlDialog], managers: Callable[..., DownloadManager]
) -> None:
    """`REQ-009` is about what will run, not about the selector string specifically (`T-076`).

    `T-075` is the standing lesson here: a dialog that displays one thing and queues another is
    the defect that motivated all of this, so a bitrate that changes the download and not the
    display would be the same shape one field over.
    """
    dialog = dialogs(managers())
    choose_preset(dialog, "Audio only (MP3)")
    choose_bitrate(dialog, "320")

    shown = label(dialog, "selectorValue").text()
    assert "320 kbps" in shown, shown
    assert dialog.selected_preset.audio_quality == "320"

    choose_preset(dialog, "Best video available")
    assert "kbps" not in label(dialog, "selectorValue").text()


def test_the_preset_chosen_after_probing_is_the_one_that_downloads(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """`T-075`, reported by the maintainer against a real YouTube URL.

    **The order a user works in is the order that was broken.** You paste a URL, probe it to find
    out *what* it is, and only then decide *how* to download it — and `probe()` has to persist a
    job before asking a worker anything (`REQ-012`), so it wrote one built from whichever preset
    happened to be selected at that moment. Choosing another afterwards updated the displayed
    selector and nothing else, and `add_to_queue` started the job the probe had written.

    So the dialog showed `Format selector: bestaudio/best` while queueing a 1080p video request.
    Downloading something other than what the user selected, silently, is `AGENTS.md` §10's
    Critical row — and the visible-but-wrong selector makes it worse, because `REQ-009` shows that
    string precisely so it can be trusted.

    Asserted on the **stored request**, not on the label: the label was already right.
    """
    dialog, _ = probe_of(dialogs, managers, spin, SINGLE_ITEM)
    (job_id,) = dialog.queued_job_ids
    assert store.jobs[job_id].request.audio_codec is not AudioCodec.MP3, (
        "this test needs the probe to have stored something other than the preset it will choose"
    )

    choose_preset(dialog, "Audio only (MP3)")
    dialog.add_to_queue()
    assert spin(lambda: store.jobs[job_id].status is JobStatus.RUNNING)

    stored = store.jobs[job_id].request
    assert stored.format_selector == "bestaudio/best", (
        f"queued {stored.format_selector!r}, but the user chose the MP3 preset"
    )
    assert stored.audio_codec is AudioCodec.MP3
    assert stored.audio_quality == MP3_QUALITY


def test_a_preset_left_alone_is_still_the_one_that_downloads(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """The other half, so the fix cannot be "always overwrite with whatever is selected now".

    A user who probes and adds without touching the dropdown must get exactly what the probe
    stored — and must not pay for a second revision of the row to find that out, which is what
    `test_a_probed_job_downloads_from_ready_without_re_entering_probing` asserts one test below.
    """
    dialog, _ = probe_of(dialogs, managers, spin, SINGLE_ITEM)
    (job_id,) = dialog.queued_job_ids
    before = store.jobs[job_id].request

    dialog.add_to_queue()
    assert spin(lambda: store.jobs[job_id].status is JobStatus.RUNNING)

    assert store.jobs[job_id].request == before


def test_a_probed_job_downloads_from_ready_without_re_entering_probing(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """`ARC-004`, asserted as the whole persisted sequence rather than as the final state."""
    dialog, _ = probe_of(dialogs, managers, spin, SINGLE_ITEM)
    (job_id,) = dialog.queued_job_ids
    assert store.jobs[job_id].status is JobStatus.READY
    assert store.statuses(job_id) == [JobStatus.QUEUED, JobStatus.PROBING, JobStatus.READY]

    dialog.add_to_queue()

    assert spin(lambda: store.jobs[job_id].status is JobStatus.RUNNING)
    assert store.statuses(job_id) == [
        JobStatus.QUEUED,
        JobStatus.PROBING,
        JobStatus.READY,
        JobStatus.RUNNING,
    ]
    assert store.statuses(job_id).count(JobStatus.PROBING) == 1


def test_a_queued_job_still_starts_at_probing(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """The second entry point did not replace the first (`ARC-004`)."""
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    type_urls(dialog, "https://a.invalid/1")
    dialog.add_to_queue()

    (job_id,) = dialog.queued_job_ids
    assert store.jobs[job_id].status is JobStatus.QUEUED

    manager.start(job_id, SessionKind.DOWNLOAD)
    assert spin(lambda: store.jobs[job_id].status is JobStatus.PROBING)
    assert store.statuses(job_id) == [JobStatus.QUEUED, JobStatus.PROBING]


# --- 11. accessibility (`NFR-005`) ------------------------------------------------------------


def test_every_control_has_an_accessible_name(
    dialogs: Callable[..., AddUrlDialog], managers: Callable[..., DownloadManager]
) -> None:
    """Every focusable control plus the thumbnail, which a review cursor reaches."""
    dialog = dialogs(managers(entry_point=child_never_returning))
    named: list[QWidget] = [*focusable_widgets(dialog), label(dialog, "thumbnail")]
    unnamed = [
        widget.objectName() or type(widget).__name__
        for widget in named
        if not widget.accessibleName()
    ]
    assert not unnamed, f"controls with no accessible name: {unnamed}"


def test_every_control_is_reachable_and_actuable_by_keyboard(
    dialogs: Callable[..., AddUrlDialog], managers: Callable[..., DownloadManager]
) -> None:
    """Reachable — a real tab focus policy — and actuable, via a mnemonic."""
    dialog = dialogs(managers(entry_point=child_never_returning))
    for widget in dialog.focus_chain():
        policy = widget.focusPolicy()
        assert policy & Qt.FocusPolicy.TabFocus, f"{widget.objectName()} cannot be tabbed to"

    names = ("probeButton", "cancelProbeButton", "addButton", "closeButton")
    without = [name for name in names if "&" not in button(dialog, name).text()]
    assert not without, f"buttons with no keyboard mnemonic: {without}"


def test_no_keyboard_focusable_control_is_left_out_of_the_declared_order(
    dialogs: Callable[..., AddUrlDialog], managers: Callable[..., DownloadManager]
) -> None:
    """`T016-R4`: the set is observed from Qt, not taken from the dialog's own list.

    This is the assertion whose absence let six focusable labels sit after Close, unnoticed,
    while a green test reported the tab order was gated.
    """
    dialog = dialogs(managers(entry_point=child_never_returning))
    observed = sorted(widget.objectName() for widget in focusable_widgets(dialog))
    assert observed == sorted(EXPECTED_TAB_ORDER), (
        "the focusable controls Qt reports differ from the transcribed order"
    )
    assert sorted(widget.objectName() for widget in dialog.focus_chain()) == observed


def test_the_tab_order_is_the_declared_one(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    qapp: QApplication,
) -> None:
    """Walk Qt's own chain and keep **every** focusable node in this window (`T016-R4`).

    The only exclusion is the combo box's popup view, which lives in its own top-level window and
    is never in the dialog's tab chain. Filtering by declared name — the previous version — meant
    an undeclared control could not fail this.
    """
    dialog = dialogs(managers(entry_point=child_never_returning))
    dialog.show()
    qapp.processEvents()

    start = dialog.findChild(QWidget, EXPECTED_TAB_ORDER[0])
    assert start is not None
    node: QWidget | None = start
    walked = [start.objectName()]
    for _ in range(500):
        assert node is not None
        node = node.nextInFocusChain()
        if node is None:
            break
        if not (node.focusPolicy() & Qt.FocusPolicy.TabFocus) or node.window() is not dialog:
            continue
        if node.objectName() == EXPECTED_TAB_ORDER[0]:
            break
        walked.append(node.objectName())
    assert tuple(walked) == EXPECTED_TAB_ORDER

    dialog.close()


def test_no_state_is_conveyed_by_colour_alone(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """Every state the dialog can be in says what it is, in words (`NFR-005`)."""
    dialog, _ = probe_of(dialogs, managers, spin, SINGLE_ITEM)
    probed_text = dialog.status_text()

    type_urls(dialog, "https://changed.invalid/x")
    changed_text = dialog.status_text()

    failing = dialogs(managers(entry_point=child_failing_as_recorded))
    type_urls(failing, "https://example.com/")
    failing.probe()
    probing_text = failing.status_text()
    assert spin(lambda: failing.probing_job_id is None)
    failed_text = failing.status_text()

    texts = [probed_text, changed_text, probing_text, failed_text]
    assert all(texts), "a state left the status line empty"
    assert len(set(texts)) == 4, f"two states read identically: {texts}"

    for widget in [dialog, *dialog.findChildren(QWidget)]:
        assert not widget.styleSheet(), f"{widget.objectName()} signals with a stylesheet"


# --- 12. the way in from the shell window -----------------------------------------------------


def add_action(window: MainWindow) -> QAction:
    found = window.findChild(QAction, "actionAddUrls")
    assert found is not None, "the File menu has no Add URLs action"
    return found


def test_the_menu_item_is_disabled_until_composition_supplies_the_queue(
    qapp: QApplication, tmp_path: Path
) -> None:
    """An action that appears to work and does nothing is worse than one that says it cannot."""
    window = MainWindow(geometry_file=tmp_path / "window.toml")
    try:
        assert not window.can_add_urls
        action = add_action(window)
        assert not action.isEnabled()
        assert "T-036" in action.statusTip()
        with pytest.raises(RuntimeError, match="no download manager"):
            window.open_add_dialog()
    finally:
        window.close()
        window.deleteLater()
        qapp.processEvents()


def test_the_menu_item_opens_the_dialog_once_the_queue_is_wired(
    qapp: QApplication,
    sink: FakeSink,
    managers: Callable[..., DownloadManager],
    tmp_path: Path,
) -> None:
    """`T-016`'s way in, exercised the way a user reaches it."""
    window = MainWindow(
        geometry_file=tmp_path / "window.toml",
        manager=managers(entry_point=child_never_returning),
        jobs=sink,
        output_directory=tmp_path / "downloads",
    )
    try:
        assert window.can_add_urls
        action = add_action(window)
        assert action.isEnabled()
        assert "T-036" not in action.statusTip()

        action.trigger()
        qapp.processEvents()
        dialog = window.findChild(AddUrlDialog)
        assert dialog is not None
        assert dialog.isVisible()
        dialog.close()
        dialog.deleteLater()
    finally:
        window.close()
        window.deleteLater()
        qapp.processEvents()


# --- the third correction (`T016-R1`, `T016-R3`) ----------------------------------------------


class StubWriter:
    """A `QueueWriter` stand-in whose revisions complete when, and how, the test says.

    A real writer cannot be made to fail two consecutive writes without breaking SQLite itself,
    and what is under test is the store's *rollback rule* rather than the database's behaviour.
    The repository underneath is real, so "what the disk says" is a genuine read.
    """

    def __init__(self) -> None:
        self.pending: list[tuple[Job, Callable[[str | None], None]]] = []
        self.failing = False

    def revise(self, job: Job, done: Callable[[str | None], None]) -> None:
        self.pending.append((job, done))

    def submit(self, jobs: Sequence[Job], done: Callable[[str | None], None]) -> None:
        self.pending.append((next(iter(jobs)), done))

    def settle_one(self) -> None:
        """Complete the oldest outstanding write, as the writer thread would."""
        job, done = self.pending.pop(0)
        done("the writer refused this revision" if self.failing else None)
        _ = job


def test_two_failed_revisions_leave_the_store_agreeing_with_the_disk(
    tmp_path: Path, qapp: QApplication
) -> None:
    """`T016-R1`: a rollback target that itself failed is not a state anything reached.

    The reviewer's third probe. Revision A is queued, then B; A fails, then B fails. The previous
    rule kept the newest value and, on failure, restored the value it had displaced — so B's
    failure restored **A**, which had also failed. The concrete measurement was SQLite holding
    `QUEUED` while `PersistentJobStore.get()` answered `PROBING`: the view disagreeing with the
    disk about a write that never happened, which is the whole of the Critical finding.

    Correct for one failure and wrong for two is exactly the shape `ai/TESTING.md` §13 warns
    about, so this drives two.
    """
    path = tmp_path / "queue.db"
    connection = connect(path)
    repository = JobRepository(connection)
    writer = StubWriter()
    # `StubWriter` is a stand-in rather than a `QueueWriter`: what is under test is the
    # store's rollback rule, and a real writer cannot be made to fail twice without
    # breaking SQLite itself.
    store_under_test = PersistentJobStore(connection, writer)  # type: ignore[arg-type]
    try:
        job = a_queued_job("https://a.invalid/1")
        repository.append([job])
        assert repository.get(job.id) is not None

        writer.failing = True
        store_under_test.update(replace(job, status=JobStatus.PROBING), lambda _e: None)
        store_under_test.update(
            replace(job, status=JobStatus.CANCELLED, error_kind=ErrorKind.CANCELLED),
            lambda _e: None,
        )
        writer.settle_one()
        writer.settle_one()

        on_disk = repository.get(job.id)
        assert on_disk is not None and on_disk.status is JobStatus.QUEUED, (
            "both revisions were supposed to fail; this proves nothing otherwise"
        )
        seen = store_under_test.get(job.id)
        assert seen is not None and seen.status is JobStatus.QUEUED, (
            "the store answered with a revision that never reached the disk"
        )
        assert [job.status for job in store_under_test.all_jobs()] == [JobStatus.QUEUED]
    finally:
        connection.close()
        qapp.processEvents()


def test_the_close_that_creates_a_withdrawal_is_refused_and_completes_itself(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    sink: FakeSink,
    qapp: QApplication,
    spin: Callable[..., bool],
) -> None:
    """`T016-R1`: the dialog may not go invisible while a cancellation is unwritten.

    The previous correction tested `_withdrawing` on the way into `done()` and then, four lines
    later, retired a started probe — which populates it — and carried straight on to
    `super().done()`. The reviewer watched the dialog become invisible with `withdrawing`
    populated and no cancellation durable: a restart in that window brings the disowned URL back
    as live work, having shown the user nothing but "The URL changed".

    No write has to be held to see it: a probe that is actually running is cancelled through its
    worker, so `CANCELLED` is not written until that worker has been stopped and its stream has
    ended. The window is the real one, and once it closes the dialog has to finish the close the
    user already asked for rather than make them ask again.
    """
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    # Shown for real, because the finding is about the dialog *disappearing*: a widget that was
    # never on screen is hidden whatever `done()` does, so a test that skipped this would report
    # the correction working while observing nothing.
    dialog.show()
    qapp.processEvents()
    assert dialog.isVisible()
    type_urls(dialog, "https://held.invalid/x")
    dialog.probe()
    assert spin(lambda: dialog.probing_job_id is not None, timeout=30)
    job_id = dialog.probing_job_id
    assert job_id is not None

    dialog.reject()
    qapp.processEvents()
    assert list(dialog.withdrawing) == [job_id], "closing did not withdraw the probed row"
    assert store.jobs[job_id].status is not JobStatus.CANCELLED, (
        "the cancellation was already durable, so there was no window to observe"
    )
    assert dialog.isVisible(), (
        "the dialog closed while the withdrawal it had just created was still unwritten"
    )

    assert spin(lambda: dialog.withdrawing == (), timeout=30), "the withdrawal never landed"
    assert not dialog.isVisible(), (
        "the close the user asked for never completed once it was safe to complete it"
    )
    assert store.statuses(job_id)[-1] is JobStatus.CANCELLED


def test_a_probe_whose_start_is_rejected_stops_claiming_to_be_probing(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    qapp: QApplication,
    spin: Callable[..., bool],
) -> None:
    """`T016-R3`: `start()` returning is not a worker running.

    It returns once the transition is *queued*, so the rejections it can raise are only the
    synchronous ones. When the write itself fails the manager abandons the reservation — and with
    nothing listening for that, the dialog sat at "Probing …" forever, offering a Cancel button
    for a worker that was never built.
    """
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    type_urls(dialog, "https://rejected.invalid/x")

    failed: list[tuple[Job, Callable[[str | None], None]]] = []
    original = store.update

    def refuse(job: Job, done: Callable[[str | None], None] | None = None) -> None:
        assert done is not None
        failed.append((job, done))

    store.update = refuse  # type: ignore[method-assign]
    try:
        dialog.probe()
        assert spin(lambda: bool(failed), timeout=30), "the start never asked for a transition"
        for _job, done in failed:
            done("the writer refused this transition")
        qapp.processEvents()
    finally:
        store.update = original  # type: ignore[method-assign]

    assert dialog.probing_job_id is None, "the dialog still claims a probe is running"
    assert "did not start" in dialog.status_text(), (
        f"the rejection was never reported; the dialog says {dialog.status_text()!r}"
    )
    assert manager.is_idle, "the manager kept a reservation for a start it abandoned"


# --- T-089: the MP3 bitrate control's whole UI contract -------------------------------------


def test_the_offered_bitrates_are_exactly_these_in_this_order(
    dialogs: Callable[..., AddUrlDialog], managers: Callable[..., DownloadManager]
) -> None:
    """`T-089`: transcribed, **not** derived from `MP3_BITRATES`.

    Deriving the expectation from the same constant the dialog reads makes the assertion a tautology
    — reorder the constant, or drop a value from it, and both sides move together. Writing the list
    out is the only version of this that can fail for the reason it exists.

    The order is part of the contract, not an accident: highest first, so the most common deliberate
    choice is the shortest reach from the top of the list.
    """
    dialog = dialogs(managers())
    box = dialog.findChild(QComboBox, "audioBitrateChoice")
    assert box is not None

    offered = [box.itemData(index) for index in range(box.count())]
    assert offered == ["320", "256", "192", "160", "128"]

    labels = [box.itemText(index) for index in range(box.count())]
    assert labels == [
        "320 kbps",
        "256 kbps",
        "192 kbps",
        "160 kbps",
        "128 kbps",
    ], "the label is what the user reads; a bare number would not say what the unit is"

    assert box.currentData() == "192", "the default is 192, and it is the middle of the scale"


def test_probing_then_choosing_mp3_at_320_stores_both(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """`T-089`: the historically load-bearing order — probe, **then** decide how (`T-075`).

    `probe()` persists a job before asking a worker anything (`REQ-012`), so it writes a request
    built from whatever preset was selected at that moment. `T-075` was that choosing afterwards
    updated the label and nothing else. This asserts the same for the *bitrate*, which is the field
    `T-076` added after that defect was fixed — the same shape one field over, and the reason
    `T076-R2` wanted it gated rather than inferred.

    Asserted on the **durable request**, never the label.
    """
    dialog, _ = probe_of(dialogs, managers, spin, SINGLE_ITEM)
    (job_id,) = dialog.queued_job_ids
    assert store.jobs[job_id].request.audio_codec is not AudioCodec.MP3, (
        "this test needs the probe to have stored something the later choice will change"
    )

    choose_preset(dialog, "Audio only (MP3)")
    choose_bitrate(dialog, "320")
    dialog.add_to_queue()
    assert spin(lambda: store.jobs[job_id].status is JobStatus.RUNNING)

    stored = store.jobs[job_id].request
    assert stored.audio_codec is AudioCodec.MP3
    assert stored.audio_quality == "320", (
        f"stored {stored.audio_quality!r}. The bitrate chosen after the probe must reach the "
        "durable request, not just the label — T-075 one field over"
    )


def flac_preset() -> Preset:
    """A converting preset that is **not** MP3, which no built-in currently is.

    `T076-R1` is the reason this has to be injected rather than picked: the built-ins are MP3 or
    `ORIGINAL`, so every dialog assertion about "not MP3" is really an assertion about "does not
    convert". Those are different rules — `CONVERTING_AUDIO_CODECS` is every codec but `ORIGINAL` —
    and a gate that widened from one to the other would pass every existing test.
    """
    return Preset(
        name="Audio only (FLAC)",
        media_kind=MediaKind.AUDIO,
        format_selector="bestaudio/best",
        output_template="%(title)s.%(ext)s",
        audio_codec=AudioCodec.FLAC,
        built_in=False,
    )


def test_a_converting_preset_that_is_not_mp3_offers_no_bitrate(
    dialogs: Callable[..., AddUrlDialog], managers: Callable[..., DownloadManager]
) -> None:
    """`T-089`, `T076-R1`: FLAC converts, and these bitrates are MP3's.

    Three things at once, because the contract is all three and a partial version of it is what
    `T076-R2` reported: the control is **disabled**, the display shows **no** bitrate, and
    `selected_preset` returns the base preset **unmodified** rather than one carrying a number that
    could not mean anything.

    The third is the one nothing else covers. `with_audio_quality` raises for a non-MP3 codec, so a
    dialog that applied it unconditionally would crash rather than mislead — but a dialog that
    applied it *conditionally on converting* would silently attach 192 kbps to a FLAC download.
    """
    dialog = dialogs(
        managers(), presets=[flac_preset(), preset_registry.by_name("Audio only (MP3)")]
    )
    box = dialog.findChild(QComboBox, "audioBitrateChoice")
    assert box is not None

    choose_preset(dialog, "Audio only (FLAC)")

    assert not box.isEnabled(), "a bitrate that cannot apply must not invite a choice"
    shown = label(dialog, "selectorValue").text()
    assert "kbps" not in shown, f"a bitrate was displayed for a FLAC download: {shown!r}"

    chosen = dialog.selected_preset
    assert chosen.audio_codec is AudioCodec.FLAC
    assert chosen == flac_preset(), (
        "selected_preset altered a non-MP3 preset. The base preset is what runs; attaching an MP3 "
        "bitrate to FLAC would store a number the download ignores"
    )


def test_the_bitrate_is_offered_for_mp3_even_beside_a_converting_neighbour(
    dialogs: Callable[..., AddUrlDialog], managers: Callable[..., DownloadManager]
) -> None:
    """The other half, so the test above cannot pass by the control never being enabled at all."""
    dialog = dialogs(
        managers(), presets=[flac_preset(), preset_registry.by_name("Audio only (MP3)")]
    )
    box = dialog.findChild(QComboBox, "audioBitrateChoice")
    assert box is not None

    choose_preset(dialog, "Audio only (MP3)")
    assert box.isEnabled()
    assert "kbps" in label(dialog, "selectorValue").text()
