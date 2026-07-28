"""The add-URL dialog (`T-016`).

**The process boundary is not mocked** (`ai/TESTING.md` §6). Every probe below spawns a real
process over a real `multiprocessing.Queue`; what the child *is* varies, exactly as in
`tests/integration/test_manager.py`:

- **A child that replays a recorded fixture** through the real `project_media`, for the cases
  about what the dialog displays. The projection is the one that ships, so an upstream schema
  change `T-018` catches would fail here too rather than being papered over by a hand-built
  `MediaInfo`.
- **A child that never answers**, for cancellation. A probe that returns cannot prove that one
  which does not can be stopped.

What *is* faked is the network: fixtures instead of sites (`ai/TESTING.md` §1), and an injected
`ThumbnailLoader` handing over the bytes of a file already in this repository. Qt still decodes
the pixmap for real, which is the half `REQ-002` is about.

The dialog is driven through its **object names** rather than through accessors added for the
suite. Every control it builds is named for `NFR-005` anyway, so reading the widget tree costs
nothing and keeps the production class free of methods only a test calls.
"""

import json
import time
from collections.abc import Callable, Iterator
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
from tracks_and_trails.ui.add_dialog import (
    NO_THUMBNAIL_TEXT,
    NOT_PROBED_TEXT,
    UNKNOWN_TEXT,
    AddUrlDialog,
    describe_kind,
    format_duration,
    split_urls,
)
from tracks_and_trails.ui.main_window import MainWindow

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
INFODICTS: Final = REPO_ROOT / "tests" / "fixtures" / "infodicts"
ERRORS: Final = REPO_ROOT / "tests" / "fixtures" / "errors"

#: A real image already in this repository, used as thumbnail bytes. Reusing the application icon
#: rather than committing a second PNG: the claim is that Qt decoded *something* into a pixmap,
#: and any real image establishes that while an invented byte string would not.
THUMBNAIL_SOURCE: Final = (
    REPO_ROOT / "src" / "tracks_and_trails" / "resources" / "icons" / "icon.png"
)

#: `NFR-001`: an interaction responds within ~100 ms. Half a second here, for the same reason
#: `tests/integration/test_manager.py` uses that figure — `spawn` genuinely costs a process start
#: on a loaded runner, and the property under test is that nothing *waits on the worker*, which a
#: blocking probe would miss by seconds rather than by milliseconds.
INTERACTION_BUDGET_SECONDS: Final = 0.5

SINGLE_ITEM: Final = "archive_org_big_buck_bunny"
PLAYLIST: Final = "archive_org_art_of_war_playlist"
AUDIO_ONLY: Final = "archive_org_test_mp3"


# --- the recorded fixtures, read the same way here and in the spawned child -------------------


def load_info(name: str) -> dict[str, Any]:
    """One recorded `info_dict`, as `T-018` committed it."""
    data = json.loads((INFODICTS / f"{name}.json").read_text(encoding="utf-8"))
    return dict(data["info_dict"])


def load_error(name: str) -> dict[str, Any]:
    data = json.loads((ERRORS / f"{name}.json").read_text(encoding="utf-8"))
    return dict(data["error"])


def fixture_url(name: str) -> str:
    """The URL a fixture describes, which is what a test pastes into the dialog.

    The recorded `webpage_url` rather than an invented string, so the child finds its fixture by
    the URL it was asked to probe — the lookup a real extractor performs against a real site,
    minus the site.
    """
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
    session, so a child that sent one regardless would fail the job it was meant to be running
    and this file would be testing the violation path by accident.
    """
    if kind is SessionKind.PROBE:
        from tracks_and_trails.downloader.ytdlp_adapter import project_media

        queue.put(Probed(job_id=job_id, media=project_media(_fixture_for(request.url))))
        queue.put(WorkerFinished(job_id=job_id, exit_code=0))
        return

    queue.put(Progress(job_id=job_id, stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=1))
    while True:
        time.sleep(0.05)


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


class FakeRepository:
    """An in-memory store satisfying both `JobSink` and the manager's `JobStore`.

    A fake rather than SQLite for most tests, because the contract is the *shape* of a repository
    (`ARCHITECTURE.md` §3). `test_the_dialog_drives_the_real_repository` runs the same path
    against `JobRepository`, so this cannot drift into a shape nothing implements.
    """

    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.writes: list[tuple[str, JobStatus]] = []

    def add(self, job: Job) -> None:
        self.jobs[job.id] = job
        self.writes.append((job.id, job.status))

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def update(self, job: Job) -> None:
        if job.id not in self.jobs:
            raise KeyError(job.id)
        self.jobs[job.id] = job
        self.writes.append((job.id, job.status))

    def next_queue_position(self) -> int:
        return len(self.jobs)

    def statuses(self, job_id: str) -> list[JobStatus]:
        return [status for stored_id, status in self.writes if stored_id == job_id]


class RecordingThumbnailLoader:
    """Hands over real image bytes without a network, and records what it was asked for."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self.requested: list[str] = []
        self.cancels = 0

    def load(self, url: str, deliver: Callable[[bytes], None]) -> None:
        self.requested.append(url)
        deliver(self._data)

    def cancel(self) -> None:
        self.cancels += 1


# --- fixtures ---------------------------------------------------------------------------------


@pytest.fixture
def repository() -> FakeRepository:
    return FakeRepository()


@pytest.fixture
def managers(
    repository: FakeRepository, qapp: QApplication
) -> Iterator[Callable[..., DownloadManager]]:
    """Builds managers and guarantees they are shut down, whatever the test did.

    Teardown is not tidiness: a leaked worker would outlive the test and be attributed to
    whichever one ran next.
    """
    built: list[DownloadManager] = []

    def build(**overrides: Any) -> DownloadManager:
        manager = DownloadManager(repository, **overrides)
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
    repository: FakeRepository,
    thumbnails: RecordingThumbnailLoader,
    tmp_path: Path,
    qapp: QApplication,
) -> Iterator[Callable[..., AddUrlDialog]]:
    """Builds dialogs and destroys them, so no widget outlives the test that made it."""
    built: list[AddUrlDialog] = []

    def build(manager: DownloadManager, **overrides: Any) -> AddUrlDialog:
        dialog = AddUrlDialog(
            manager=manager,
            jobs=repository,
            output_directory=tmp_path / "downloads",
            thumbnail_loader=thumbnails,
            **overrides,
        )
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


def probe_of(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    name: str,
) -> tuple[AddUrlDialog, DownloadManager]:
    """Paste a fixture-backed URL, probe it, and return once the result has landed.

    The manager is returned as well, and is spun to idle: a probe session is released a tick
    after its result is emitted, and Phase 1 runs a pool of exactly one, so a test that queued a
    download immediately would be refused for reasons that have nothing to do with what it
    asserts.
    """
    manager = managers(entry_point=child_replaying_a_fixture)
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
    """Field by field, because "populates the dialog" would pass with four of five missing.

    Each expected value is read out of the fixture here and compared with what the widget shows,
    so this also fails for a dialog that renders the right *shape* from the wrong data.
    """
    info = load_info(SINGLE_ITEM)
    dialog, _ = probe_of(dialogs, managers, spin, SINGLE_ITEM)

    assert text_of(dialog, "titleValue") == info["title"] == "Big Buck Bunny"
    assert text_of(dialog, "uploaderValue") == info["uploader"] == "jake@archive.org"
    # 596.46 s. Truncated rather than rounded: a duration is a fact about the file, and rounding
    # up to 9:57 would report a second that does not exist.
    assert text_of(dialog, "durationValue") == "9:56"
    assert text_of(dialog, "kindValue") == "Single item"

    # The thumbnail is a decoded pixmap, not the URL it came from — the distinction the criterion
    # is about. Asserted on the widget as well as on the property, so a pixmap held but never
    # shown would still fail.
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
    # This fixture records no duration and no thumbnail, and the dialog says so rather than
    # rendering `0:00` and an empty frame.
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


# --- 2. the GUI thread is never blocked (`NFR-001`) -------------------------------------------


def test_the_dialog_stays_responsive_while_a_probe_is_outstanding(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    qapp: QApplication,
) -> None:
    """Two halves, because either alone would pass while the application froze.

    First: `probe()` returns without waiting for the worker. Second: with a probe genuinely
    outstanding — this child never answers — the dialog still processes events and its slots
    still run, which is what "responsive" means to a user holding the mouse.
    """
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

    # A slot still fires: changing the preset re-renders the selector while the worker runs.
    before = text_of(dialog, "selectorValue")
    choose_preset(dialog, BUILT_IN_PRESETS[2].name)
    qapp.processEvents()
    after = text_of(dialog, "selectorValue")
    assert after != before
    assert effective_selector(BUILT_IN_PRESETS[2]) in after
    assert dialog.probing_job_id is not None, "the probe finished; this proved nothing"


def test_adding_to_the_queue_does_not_wait_on_a_worker(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """The other call a widget makes into the manager, held to the same budget."""
    dialog, _ = probe_of(dialogs, managers, spin, SINGLE_ITEM)
    started = time.monotonic()
    dialog.add_to_queue()
    elapsed = time.monotonic() - started
    assert elapsed < INTERACTION_BUDGET_SECONDS, f"add_to_queue() blocked for {elapsed:.3f}s"


# --- 3. the extractor's own words (`REQ-005`, `NFR-006`) --------------------------------------


def test_an_unsupported_url_shows_the_extractors_message_character_for_character(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """Equality against the recorded message, not a substring and not a paraphrase.

    An `in` assertion would pass for a dialog that wrapped the text in an apology, and wrapping
    it is what `NFR-006` forbids. The classification is shown *beside* the message, on its own
    line, so the message itself survives unaltered.
    """
    recorded = load_error("unsupported_url")
    dialog = dialogs(managers(entry_point=child_failing_as_recorded))
    type_urls(dialog, "https://example.com/")
    dialog.probe()

    assert spin(lambda: recorded["message"] in dialog.status_text()), dialog.status_text()

    kind_line, _, message = dialog.status_text().partition("\n")
    assert message == recorded["message"] == "Unsupported URL: https://example.com/"
    assert kind_line == ErrorKind.UNSUPPORTED_URL.value
    # Nothing was probed, so nothing may be presented as probed.
    assert dialog.media is None
    assert dialog.probed_job_id is None
    assert text_of(dialog, "titleValue") == UNKNOWN_TEXT


def test_a_failed_probe_leaves_the_job_failed_and_recorded(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    repository: FakeRepository,
    spin: Callable[..., bool],
) -> None:
    """`REQ-018`: a failure is recorded, never assumed away, and the URL stays in the queue."""
    dialog = dialogs(managers(entry_point=child_failing_as_recorded))
    type_urls(dialog, "https://example.com/")
    dialog.probe()
    assert spin(lambda: dialog.probing_job_id is None)

    (job_id,) = dialog.queued_job_ids
    assert spin(lambda: repository.jobs[job_id].status is JobStatus.FAILED)
    stored = repository.jobs[job_id]
    assert stored.error_kind is ErrorKind.UNSUPPORTED_URL
    assert stored.error_message == load_error("unsupported_url")["message"]


# --- 4. cancellation (`REQ-015`) --------------------------------------------------------------


def test_a_probe_that_never_returns_can_be_cancelled_and_leaves_no_worker_behind(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    repository: FakeRepository,
    spin: Callable[..., bool],
) -> None:
    """The probe under test genuinely never answers, so only cancellation can end it."""
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    type_urls(dialog, "https://example.invalid/never")
    dialog.probe()

    job_id = dialog.probing_job_id
    assert job_id is not None
    process = live_session_process(manager, job_id)
    assert spin(lambda: process.pid is not None)
    pid = process.pid

    dialog.cancel_probe()
    assert dialog.probing_job_id is None
    assert "cancelled" in dialog.status_text().lower()

    assert spin(lambda: manager.is_idle, timeout=30), "the session was never released"
    assert not process.is_alive(), f"worker {pid} outlived its cancelled probe"
    assert repository.jobs[job_id].status is JobStatus.CANCELLED


def test_cancelling_clears_the_probe_without_claiming_a_result(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """A cancelled probe leaves nothing that `Add to queue` could start from `READY`."""
    dialog = dialogs(managers(entry_point=child_never_returning))
    type_urls(dialog, "https://example.invalid/never")
    dialog.probe()
    dialog.cancel_probe()

    assert dialog.probed_job_id is None
    assert dialog.media is None
    assert button(dialog, "cancelProbeButton").isEnabled() is False
    assert button(dialog, "probeButton").isEnabled() is True
    assert spin(lambda: True)


# --- 5. multi-line paste (`REQ-001`) ----------------------------------------------------------


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
    repository: FakeRepository,
) -> None:
    """`REQ-001`: three lines, three jobs, each carrying its own URL and its own request."""
    dialog = dialogs(managers(entry_point=child_never_returning))
    urls = ["https://a.invalid/1", "https://b.invalid/2", "https://c.invalid/3"]
    type_urls(dialog, "\n".join(urls))

    dialog.add_to_queue()

    queued = [repository.jobs[job_id] for job_id in dialog.queued_job_ids]
    assert [job.url for job in queued] == urls
    assert [job.request.url for job in queued] == urls
    assert len({job.id for job in queued}) == 3
    assert all(job.status is JobStatus.QUEUED for job in queued)
    # Distinct queue positions, so the order the user pasted survives into the queue.
    assert len({job.queue_position for job in queued}) == 3


def test_the_chosen_preset_reaches_every_queued_job(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    repository: FakeRepository,
) -> None:
    """`REQ-009`: the selector the user was shown is the one the job carries."""
    dialog = dialogs(managers(entry_point=child_never_returning))
    type_urls(dialog, "https://a.invalid/1\nhttps://b.invalid/2")
    chosen = BUILT_IN_PRESETS[2]
    choose_preset(dialog, chosen.name)

    assert effective_selector(chosen) in text_of(dialog, "selectorValue")
    dialog.add_to_queue()

    for job_id in dialog.queued_job_ids:
        request = repository.jobs[job_id].request
        assert request.format_selector == effective_selector(chosen)
        assert request.media_kind is chosen.media_kind
        assert request.audio_codec is chosen.audio_codec


# --- 6. persistence before the dialog closes (`REQ-012`) --------------------------------------


def test_queuing_persists_every_job_before_the_dialog_closes(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    repository: FakeRepository,
) -> None:
    """The ordering is the guarantee, so the ordering is what is asserted.

    Recorded from the `accepted` signal rather than checked afterwards: a dialog that wrote its
    jobs during teardown would satisfy "the rows exist" while losing everything to a crash
    between closing and the queue view opening.
    """
    dialog = dialogs(managers(entry_point=child_never_returning))
    type_urls(dialog, "https://a.invalid/1\nhttps://b.invalid/2")

    stored_when_accepted: list[str] = []
    dialog.accepted.connect(lambda: stored_when_accepted.extend(repository.jobs))

    dialog.add_to_queue()

    assert len(stored_when_accepted) == 2, "a job was still unwritten when the dialog closed"
    assert set(stored_when_accepted) == set(dialog.queued_job_ids)
    assert not dialog.isVisible()


def test_a_probed_url_is_persisted_before_its_session_starts(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    repository: FakeRepository,
) -> None:
    """A probe that crashes the application still leaves the URL in the queue (`REQ-012`)."""
    dialog = dialogs(managers(entry_point=child_never_returning))
    type_urls(dialog, fixture_url(SINGLE_ITEM))
    dialog.probe()

    job_id = dialog.probing_job_id
    assert job_id is not None
    assert job_id in repository.jobs
    # The first write is the creation, before the manager moved it on to `PROBING`.
    assert repository.statuses(job_id)[0] is JobStatus.QUEUED


def test_the_dialog_drives_the_real_repository(
    tmp_path: Path, qapp: QApplication, thumbnails: RecordingThumbnailLoader
) -> None:
    """The same path against `JobRepository`, so `FakeRepository` cannot drift.

    A fake satisfying a protocol nothing real implements is a test that passes alone
    (`ai/TESTING.md` §13). SQLite is used for real, in `tmp_path`.
    """
    from tracks_and_trails.persistence.db import connect, migrate
    from tracks_and_trails.persistence.repositories import JobRepository

    connection = connect(tmp_path / "queue.db")
    migrate(connection)
    real = JobRepository(connection)
    manager = DownloadManager(real, entry_point=child_never_returning)
    dialog = AddUrlDialog(
        manager=manager,
        jobs=real,
        output_directory=tmp_path / "downloads",
        thumbnail_loader=thumbnails,
    )
    try:
        type_urls(dialog, "https://a.invalid/1\nhttps://b.invalid/2")
        dialog.add_to_queue()

        stored = [real.get(job_id) for job_id in dialog.queued_job_ids]
        assert [job.url for job in stored if job is not None] == [
            "https://a.invalid/1",
            "https://b.invalid/2",
        ]
        assert all(job is not None and job.status is JobStatus.QUEUED for job in stored)
    finally:
        dialog.close()
        dialog.deleteLater()
        manager.shutdown()
        qapp.processEvents()
        connection.close()


# --- 7. the two entry points (`ARC-004`) ------------------------------------------------------


def test_a_probed_job_downloads_from_ready_without_re_entering_probing(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    repository: FakeRepository,
    spin: Callable[..., bool],
) -> None:
    """`ARC-004`, asserted as the whole persisted sequence rather than as the final state.

    The sequence is what the decision is about: a second `PROBING` anywhere in it would mean the
    dialog re-probed a job that had already been probed, which is what `READY → PROBING` was
    refused for. Reading only the last status would miss it entirely.
    """
    dialog, _ = probe_of(dialogs, managers, spin, SINGLE_ITEM)
    (job_id,) = dialog.queued_job_ids
    assert repository.jobs[job_id].status is JobStatus.READY
    assert repository.statuses(job_id) == [JobStatus.QUEUED, JobStatus.PROBING, JobStatus.READY]

    dialog.add_to_queue()

    assert spin(lambda: repository.jobs[job_id].status is JobStatus.RUNNING)
    assert repository.statuses(job_id) == [
        JobStatus.QUEUED,
        JobStatus.PROBING,
        JobStatus.READY,
        JobStatus.RUNNING,
    ]
    assert repository.statuses(job_id).count(JobStatus.PROBING) == 1


def test_a_queued_job_still_starts_at_probing(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    repository: FakeRepository,
    spin: Callable[..., bool],
) -> None:
    """The second entry point did not replace the first (`ARC-004`)."""
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    type_urls(dialog, "https://a.invalid/1")
    dialog.add_to_queue()

    (job_id,) = dialog.queued_job_ids
    assert repository.jobs[job_id].status is JobStatus.QUEUED

    manager.start(job_id, SessionKind.DOWNLOAD)
    assert spin(lambda: repository.jobs[job_id].status is JobStatus.PROBING)
    assert repository.statuses(job_id) == [JobStatus.QUEUED, JobStatus.PROBING]


def test_editing_the_url_after_a_probe_discards_the_stale_result(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """Otherwise `Add to queue` would download what was probed a minute ago.

    The recurring defect in this project is a value computed correctly and then applied to the
    wrong thing; a `READY` job held against a URL box that has since changed is that shape.
    """
    dialog, _ = probe_of(dialogs, managers, spin, SINGLE_ITEM)
    # Read into a local before asserting. Asserting on `dialog.probed_job_id` directly narrows
    # that member expression to `str` for the rest of the function, so the `is None` check after
    # the edit becomes statically impossible and mypy calls everything below it unreachable —
    # which would silently stop type-checking the real assertions.
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
    """The guard above must not fire on an edit that did not change the first URL.

    Appending a second line is the ordinary case — probe one, then paste more — and discarding
    the result there would make the probe button useless for a batch.
    """
    url = fixture_url(SINGLE_ITEM)
    dialog, _ = probe_of(dialogs, managers, spin, SINGLE_ITEM)
    probed = dialog.probed_job_id

    type_urls(dialog, f"{url}\nhttps://second.invalid/2")

    assert dialog.probed_job_id == probed
    assert dialog.media is not None


def test_the_probed_job_is_not_queued_a_second_time(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    repository: FakeRepository,
    spin: Callable[..., bool],
) -> None:
    """`ARC-004`: reuse the probed record rather than stranding or duplicating it."""
    url = fixture_url(SINGLE_ITEM)
    dialog, _ = probe_of(dialogs, managers, spin, SINGLE_ITEM)
    type_urls(dialog, f"{url}\nhttps://second.invalid/2")

    dialog.add_to_queue()

    urls = [repository.jobs[job_id].url for job_id in dialog.queued_job_ids]
    assert urls == [url, "https://second.invalid/2"], "the probed URL was queued twice"


# --- 8. accessibility (`NFR-005`) -------------------------------------------------------------


def test_every_control_has_an_accessible_name(
    dialogs: Callable[..., AddUrlDialog], managers: Callable[..., DownloadManager]
) -> None:
    """Not "the visible text is usually announced": `NFR-005` asks for the label to be set.

    Every focusable control plus the read-only result fields, which a screen-reader user reaches
    by review cursor and which would otherwise be announced as bare text with no field name.
    """
    dialog = dialogs(managers(entry_point=child_never_returning))
    named: list[QWidget] = [
        *dialog.focus_chain(),
        *(
            label(dialog, name)
            for name in (
                "thumbnail",
                "titleValue",
                "uploaderValue",
                "durationValue",
                "kindValue",
                "selectorValue",
                "statusMessage",
            )
        ),
    ]
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


#: The tab order `NFR-005` requires, **transcribed by hand** rather than read from the dialog.
#:
#: The first version of the test below derived its expectation from `AddUrlDialog.focus_chain()`
#: — the same list `_set_tab_order` feeds to Qt — so it proved only that the list equals itself.
#: A mutation reversing two entries survived it. Transcribe one side and derive the other
#: (`ai/TESTING.md` §13): this literal is the statement of intent, Qt's own chain is the
#: observation, and changing the dialog's order now has to change this line too.
EXPECTED_TAB_ORDER: Final = (
    "urlInput",
    "probeButton",
    "cancelProbeButton",
    "presetChoice",
    "addButton",
    "closeButton",
)


def test_the_tab_order_is_the_declared_one(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    qapp: QApplication,
) -> None:
    """Walk Qt's own chain, so a reordering fails here rather than being found by a user.

    `nextInFocusChain` reports what Qt will actually do, which is the point: the dialog's own
    list says what was *intended*, and only Qt can say what was achieved.
    """
    dialog = dialogs(managers(entry_point=child_never_returning))
    dialog.show()
    qapp.processEvents()

    # The dialog's declared chain and the transcription must agree as *sets*, so a control added
    # to the dialog and forgotten here fails rather than being silently skipped by the walk.
    declared = {widget.objectName() for widget in dialog.focus_chain()}
    assert declared == set(EXPECTED_TAB_ORDER), (
        "the dialog's focus chain and this test's transcription name different controls"
    )

    node: QWidget | None = dialog.findChild(QWidget, EXPECTED_TAB_ORDER[0])
    assert node is not None
    walked = [node.objectName()]
    for _ in range(500):
        # Qt documents the chain as circular, so this should never run out. It is typed as
        # optional and is treated as optional: a chain that ended would otherwise raise here
        # rather than failing the comparison below with something a reader can act on.
        node = node.nextInFocusChain()
        if node is None:
            break
        name = node.objectName()
        if name not in declared:
            continue
        if name == EXPECTED_TAB_ORDER[0]:
            break
        walked.append(name)
    assert tuple(walked) == EXPECTED_TAB_ORDER

    dialog.close()


def test_no_state_is_conveyed_by_colour_alone(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """Every state the dialog can be in says what it is, in words (`NFR-005`).

    Two assertions, because either alone is weak: the four states must produce four *distinct*
    texts, and no widget may carry a stylesheet — the only way this dialog could start signalling
    with colour, and the thing a future edit would reach for first.
    """
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


# --- 9. the way in from the shell window -----------------------------------------------------


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
    repository: FakeRepository,
    managers: Callable[..., DownloadManager],
    tmp_path: Path,
) -> None:
    """`T-016`'s way in, exercised the way a user reaches it."""
    window = MainWindow(
        geometry_file=tmp_path / "window.toml",
        manager=managers(entry_point=child_never_returning),
        jobs=repository,
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
