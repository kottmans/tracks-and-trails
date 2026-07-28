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
import time
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

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import DownloadRequest, Job, MediaInfo
from tracks_and_trails.core.presets import BUILT_IN_PRESETS, effective_selector
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
from tracks_and_trails.persistence.writer import QueueWriter
from tracks_and_trails.ui.add_dialog import (
    LOADING_THUMBNAIL_TEXT,
    NO_THUMBNAIL_TEXT,
    NOT_PROBED_TEXT,
    THUMBNAIL_FAILED_TEXT,
    UNKNOWN_TEXT,
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

    def insert(self, job: Job) -> None:
        self.jobs[job.id] = job
        self.writes.append((job.id, job.status))

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def update(self, job: Job) -> None:
        if job.id not in self.jobs:
            raise KeyError(job.id)
        self.jobs[job.id] = job
        self.writes.append((job.id, job.status))

    def statuses(self, job_id: str) -> list[JobStatus]:
        return [status for stored_id, status in self.writes if stored_id == job_id]


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


# --- 4. `T016-R3` (High): nothing waits on SQLite ---------------------------------------------


@pytest.fixture
def real_queue(tmp_path: Path, qapp: QApplication) -> Iterator[tuple[QueueWriter, JobRepository]]:
    """A real `QueueWriter` over a real SQLite file, with a GUI-thread repository for reads."""
    path = tmp_path / "queue.db"
    connection = connect(path)
    writer = QueueWriter(lambda: connect(path))
    try:
        yield writer, JobRepository(connection)
    finally:
        writer.close()
        connection.close()
        qapp.processEvents()


def test_adding_never_blocks_the_gui_thread_on_a_contended_database(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    real_queue: tuple[QueueWriter, JobRepository],
    tmp_path: Path,
    spin: Callable[..., bool],
) -> None:
    """The concrete repository, under a genuinely held writer lock (`ARC-005`).

    The reviewer measured 0.302 s of blocked GUI thread and then an `OperationalError`. Here a
    second connection holds SQLite's write lock outright; `add_to_queue()` must still return
    within an interaction budget, and the write must land once the lock is released.
    """
    writer, repository = real_queue
    dialog = dialogs(managers(entry_point=child_never_returning), jobs=writer)
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
