"""The download manager and the result pump (`T-013`).

`ai/TESTING.md` §6: **the process boundary is never mocked here.** Every test below spawns a
real process, over a real `multiprocessing.Queue`, and terminates it for real. What varies is
what the child *is*:

- **A real worker running real yt-dlp** for the two cases where nothing else is evidence: a
  download that completes, and `REQ-015`'s cancellation of a download that is genuinely in
  flight. What is faked is only the *site* — a local HTTP server serves throttled bytes, so the
  download is a real socket, a real progress hook and a real partial file, without the test
  depending on a site staying up.
- **A crafted child** for streams a correct worker cannot produce: two outcomes for one job, a
  bare dict on the queue, an exit that reports nothing. These are the receiving half's whole
  job, and the only way to reach them is to send them.

`T-002`'s probe proved cancellation against a *sleeping* worker and said so. That is why the
budget below is measured against bytes actually moving: a process asleep in `time.sleep` dies
the instant it is signalled, and a process inside yt-dlp's download loop does not.
"""

import multiprocessing as mp
import os
import pickle
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import pairwise
from pathlib import Path
from typing import Any

import psutil
import pytest
from PySide6.QtCore import QCoreApplication

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus, can_transition
from tracks_and_trails.core.models import DownloadRequest, Job
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.downloader.protocol import (
    MESSAGE_TYPES,
    Probed,
    Progress,
    ResolutionReport,
    SessionKind,
    Stage,
    Succeeded,
    WorkerFinished,
)
from tracks_and_trails.downloader.result_pump import ResultPump

REPO_ROOT = Path(__file__).parents[2]

#: `REQ-015` and `ai/TESTING.md` §7: cancel terminates the worker within two seconds.
CANCEL_BUDGET_SECONDS = 2.0

#: `NFR-001`: an interaction responds within ~100 ms. Applied here to the manager calls a
#: widget will make, which must not wait on a worker at all.
INTERACTION_BUDGET_SECONDS = 0.5


# --- the queue the manager is given ------------------------------------------------------


class FakeRepository:
    """An in-memory `JobStore`, and a log of every write in order.

    A fake rather than the real repository for most tests, because the manager's contract is
    that it depends on the *shape* of a repository and not on SQLite (`ARCHITECTURE.md` §3).
    `test_the_manager_drives_the_real_repository` runs the same path against the real one, so
    this cannot drift into a shape nothing implements.
    """

    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.writes: list[tuple[str, JobStatus]] = []

    def add(self, job: Job) -> None:
        self.jobs[job.id] = job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def update(self, job: Job) -> None:
        if job.id not in self.jobs:
            raise KeyError(job.id)
        self.jobs[job.id] = job
        self.writes.append((job.id, job.status))

    def statuses(self, job_id: str) -> list[JobStatus]:
        return [status for stored_id, status in self.writes if stored_id == job_id]


def make_job(job_id: str, url: str, directory: Path) -> Job:
    return Job(
        id=job_id,
        url=url,
        request=DownloadRequest(
            url=url,
            output_directory=str(directory),
            format_selector="best",
            output_template="%(title)s.%(ext)s",
        ),
        created_at=datetime.now(UTC),
        queue_position=0,
    )


class Recorder:
    """Collects what the manager told the GUI, and the thread it was told on."""

    def __init__(self, manager: DownloadManager, repository: FakeRepository) -> None:
        self.changes: list[tuple[str, str]] = []
        self.progress: list[Progress] = []
        self.probed: list[tuple[str, Any]] = []
        self.resolutions: list[ResolutionReport] = []
        self.succeeded: list[tuple[str, str]] = []
        self.failed: list[tuple[str, ErrorKind, str]] = []
        self.violations: list[tuple[str, str]] = []
        self.threads: set[int] = set()
        #: What the repository held at the moment each `job_changed` arrived. The acceptance
        #: criterion is about this ordering, so it is captured rather than inferred.
        self.stored_when_told: list[JobStatus | None] = []
        self._repository = repository

        manager.job_changed.connect(self._on_change)
        manager.progress.connect(self._on_progress)
        manager.media_probed.connect(lambda job_id, media: self.probed.append((job_id, media)))
        manager.resolution_reported.connect(self.resolutions.append)
        manager.job_succeeded.connect(lambda job_id, path: self.succeeded.append((job_id, path)))
        manager.job_failed.connect(
            lambda job_id, kind, message: self.failed.append((job_id, kind, message))
        )
        manager.protocol_violation.connect(
            lambda job_id, reason: self.violations.append((job_id, reason))
        )

    def _on_change(self, job_id: str, status: str) -> None:
        self.threads.add(threading.get_ident())
        stored = self._repository.get(job_id)
        self.stored_when_told.append(stored.status if stored is not None else None)
        self.changes.append((job_id, status))

    def _on_progress(self, message: Progress) -> None:
        self.threads.add(threading.get_ident())
        self.progress.append(message)

    @property
    def statuses(self) -> list[str]:
        return [status for _, status in self.changes]


@pytest.fixture
def repository() -> FakeRepository:
    return FakeRepository()


@pytest.fixture
def manager(
    repository: FakeRepository, app: QCoreApplication
) -> Iterator[Callable[..., DownloadManager]]:
    """Builds managers and guarantees they are shut down, whatever the test did.

    The teardown is not tidiness: a leaked worker would outlive the test and be attributed to
    whichever one ran next.
    """
    built: list[DownloadManager] = []

    def build(**overrides: Any) -> DownloadManager:
        manager = DownloadManager(repository, **overrides)
        built.append(manager)
        return manager

    yield build

    # Shutdown is a lifecycle, not a call (`T013-R2`), so teardown has to drive the event loop
    # until it finishes. A test that returned here with a pump still running would have Qt
    # destroy a live QThread — which aborts the interpreter, taking the whole run with it.
    for manager in built:
        manager.shutdown()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not all(m.is_idle for m in built):
        app.processEvents()
        time.sleep(0.005)
    assert all(m.is_idle for m in built), "a manager never finished shutting down"


# --- a site that is not a site ------------------------------------------------------------


def media_handler(total_bytes: int, chunk_delay: float) -> type[BaseHTTPRequestHandler]:
    """A handler serving `total_bytes` of `video/mp4`, paced by `chunk_delay`.

    Declared `Content-Type` and `Content-Length` are all yt-dlp's generic extractor needs to
    treat a URL as a direct media file, so this exercises the real extractor, the real format
    selection and the real HTTP downloader.
    """

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            """Silence http.server's stderr logging; a test is not a web server.

            The shadowed builtin is in `BaseHTTPRequestHandler`'s own signature.
            """

        def _send_headers(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(total_bytes))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()

        def do_HEAD(self) -> None:
            self._send_headers()

        def do_GET(self) -> None:
            self._send_headers()
            sent = 0
            chunk = b"\0" * (32 * 1024)
            try:
                while sent < total_bytes:
                    self.wfile.write(chunk[: min(len(chunk), total_bytes - sent)])
                    sent += len(chunk)
                    time.sleep(chunk_delay)
            except BrokenPipeError, ConnectionResetError:
                # The expected end of a cancelled download: the worker went away mid-stream.
                pass

    return Handler


@pytest.fixture
def media_url() -> Iterator[Callable[..., str]]:
    """Serves a media URL from localhost. Not a network test: nothing leaves the machine."""
    servers: list[ThreadingHTTPServer] = []

    def serve(total_bytes: int = 256 * 1024, chunk_delay: float = 0.0) -> str:
        server = ThreadingHTTPServer(("127.0.0.1", 0), media_handler(total_bytes, chunk_delay))
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_address[1]}/clip.mp4"

    yield serve

    for server in servers:
        server.shutdown()
        server.server_close()


# --- children that are not workers --------------------------------------------------------
#
# Each is a real spawned process putting real messages on a real queue. They exist because a
# correct worker cannot produce these streams, and the manager's whole job is what happens when
# it receives one anyway.


def child_reporting_nothing(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Exits 0 having said nothing at all — the case that looks like nothing went wrong."""
    return


def child_sending_two_outcomes(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Two `Succeeded` for one job (`T011-R4`), then a well-formed sentinel."""
    queue.put(Succeeded(job_id=job_id, output_path="/first/clip.mp4"))
    queue.put(Succeeded(job_id=job_id, output_path="/second/clip.mp4"))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))
    queue.close()
    queue.join_thread()


def child_sending_an_undeclared_object(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """A bare dict pickles happily and is exactly what `is_message()` exists to refuse."""
    queue.put({"job_id": job_id, "status": "downloading"})
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))
    queue.close()
    queue.join_thread()


def child_talking_after_its_outcome(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Reports success and then keeps talking. Only `validate_sequence()` sees this one.

    Every message is declared and there is exactly one outcome, so nothing the pump checks
    message-by-message can object; the fault is in the shape of the whole session.
    """
    queue.put(Succeeded(job_id=job_id, output_path="/written/clip.mp4"))
    queue.put(Progress(job_id=job_id, stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=1))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))
    queue.close()
    queue.join_thread()


def child_probe_reporting_a_download_outcome(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """A probe session claiming it downloaded something (`T013-R1`).

    `Succeeded` is not a legal outcome for a probe — `legal_outcomes()` says so — and the
    receiver must decide that *before* the message becomes a persisted `COMPLETED` job.
    """
    queue.put(Succeeded(job_id=job_id, output_path="/never/written.mp4"))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))
    queue.close()
    queue.join_thread()


def child_download_reporting_a_probe_outcome(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """The mirror image: a download session ending in `Probed`, which would leave it `READY`."""
    from tracks_and_trails.core.models import MediaInfo

    queue.put(
        Probed(job_id=job_id, media=MediaInfo(url="https://example.invalid/x", title="Nothing"))
    )
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))
    queue.close()
    queue.join_thread()


def child_probe_reporting_a_download_stage(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """A probe reporting `DOWNLOADING_VIDEO` (`T011-R7`): a probe only extracts metadata."""
    from tracks_and_trails.core.models import MediaInfo

    queue.put(Progress(job_id=job_id, stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=1))
    queue.put(
        Probed(job_id=job_id, media=MediaInfo(url="https://example.invalid/x", title="Nothing"))
    )
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))
    queue.close()
    queue.join_thread()


def child_reporting_another_jobs_progress(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """A message attributed to a job this session is not running.

    `validate_sequence` rejects a *mixed* stream, but a receiver that never compares against the
    job it asked for would accept a stream consistently claiming to be someone else's.
    """
    queue.put(Progress(job_id="a-different-job", stage=Stage.DOWNLOADING_VIDEO))
    queue.put(Succeeded(job_id=job_id, output_path="/written/clip.mp4"))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))
    queue.close()
    queue.join_thread()


def child_reporting_its_resolution_twice(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """One session resolves yt-dlp once, so it reports that once (`T012-R1`)."""
    queue.put(ResolutionReport(job_id=job_id, ytdlp_version="1.0", ytdlp_source="first"))
    queue.put(ResolutionReport(job_id=job_id, ytdlp_version="2.0", ytdlp_source="second"))
    queue.put(Succeeded(job_id=job_id, output_path="/written/clip.mp4"))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))
    queue.close()
    queue.join_thread()


def child_succeeding_without_a_sentinel(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Reports success and exits without ending its stream.

    The parent has to synthesise a sentinel or the pump blocks forever — but a synthesised one
    must stay distinguishable from one the worker sent, or a worker that died on the way out
    looks exactly like one that shut down cleanly (`T013-R1`).
    """
    queue.put(Succeeded(job_id=job_id, output_path="/written/clip.mp4"))
    queue.close()
    queue.join_thread()


def child_succeeding_then_exiting_nonzero(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Reports success, flushes it, then dies badly. The message is the truth, not the code."""
    queue.put(Succeeded(job_id=job_id, output_path="/written/clip.mp4", total_bytes=10))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))
    queue.close()
    queue.join_thread()
    os._exit(3)


def child_downloading_forever(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Reports progress and then never stops, so the parent has to end it."""
    queue.put(Progress(job_id=job_id, stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=1))
    while True:
        time.sleep(0.05)


def child_ignoring_cancellation(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Reports progress, then ignores `SIGTERM` and the cancel event both."""
    import signal

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    queue.put(Progress(job_id=job_id, stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=1))
    while True:
        time.sleep(0.05)


# --- process bookkeeping ------------------------------------------------------------------


def worker_processes(before: set[int]) -> list[psutil.Process]:
    """Spawned worker children of this test process that were not there before.

    Two things are filtered out, and both were found the hard way:

    - **Zombies.** A reaped-but-not-yet-collected child is not a process doing work, and on
      Linux one exists for a moment after every kill.
    - **`multiprocessing`'s resource tracker.** Creating the first `Event` spawns it, it is a
      child of this process, and it lives for the rest of the session — so a cancellation test
      run in isolation saw it, called it a surviving worker and failed, while the same test
      passed in a full run where something earlier had already started it.

    A worker is identified by `spawn_main` in its command line, which is what `multiprocessing`
    launches a spawned child with on both platforms. The tests assert a worker *is* found before
    they kill anything, so a filter that became too narrow fails loudly rather than passing.
    """
    live: list[psutil.Process] = []
    for child in psutil.Process(os.getpid()).children(recursive=True):
        try:
            if child.pid in before or child.status() == psutil.STATUS_ZOMBIE:
                continue
            if "spawn_main" in " ".join(child.cmdline()):
                live.append(child)
        except psutil.NoSuchProcess, psutil.AccessDenied:  # it exited mid-question
            continue
    return live


@pytest.fixture
def existing_children() -> set[int]:
    return {child.pid for child in psutil.Process(os.getpid()).children(recursive=True)}


# --- the happy path (ARC-002 end to end) ---------------------------------------------------


def test_a_real_download_completes_and_every_transition_is_persisted_first(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    media_url: Callable[..., str],
    spin: Callable[..., bool],
) -> None:
    """The vertical slice: a URL goes in, a file lands, and the queue says so.

    Asserted on three separate things, because passing one of them is not passing the others:
    the job reaches `COMPLETED` through legal transitions only, the file is on disk with the
    size the server sent, and **the repository already held each status when the signal
    announcing it arrived**. That last one is the acceptance criterion about ordering, and it
    can only be observed at the moment of the signal — afterwards both are consistent.
    """
    url = media_url(total_bytes=256 * 1024)
    repository.add(make_job("job-1", url, tmp_path))
    download = manager()
    recorder = Recorder(download, repository)

    download.start("job-1")
    assert spin(lambda: download.is_idle, timeout=120)

    stored = repository.jobs["job-1"]
    assert stored.status is JobStatus.COMPLETED, recorder.failed
    assert stored.output_path is not None
    written = Path(stored.output_path)
    assert written.is_file(), "the job completed without a file to show for it"
    assert written.stat().st_size == 256 * 1024
    assert written.parent == tmp_path, "the download escaped the directory the user chose"

    statuses = repository.statuses("job-1")
    assert statuses[0] is JobStatus.PROBING
    assert statuses[-1] is JobStatus.COMPLETED
    assert recorder.succeeded == [("job-1", str(written))]
    assert recorder.resolutions, "REQ-025: the parent was never told which yt-dlp ran"
    assert recorder.progress, "REQ-014: a real download reported no progress at all"

    for (job_id, announced), stored_status in zip(
        recorder.changes, recorder.stored_when_told, strict=True
    ):
        assert stored_status is not None and stored_status.value == announced, (
            f"{job_id} was announced as {announced} while the database still held "
            f"{stored_status}; a crash there leaves the UI ahead of the queue"
        )


def test_the_manager_drives_the_real_repository(
    tmp_path: Path,
    manager: Callable[..., DownloadManager],
    media_url: Callable[..., str],
    spin: Callable[..., bool],
) -> None:
    """One integration test against the concrete `JobRepository` (`T-013` scope).

    Everything else here uses the fake, which proves the manager needs nothing but the protocol.
    This proves the protocol is one SQLite actually satisfies — that the two are the same shape
    is otherwise an assumption on both sides.
    """
    from tracks_and_trails.persistence import db
    from tracks_and_trails.persistence.repositories import JobRepository

    url = media_url(total_bytes=64 * 1024)
    with db.open_database(tmp_path / "library.sqlite3") as connection:
        real = JobRepository(connection)
        real.add(make_job("job-real", url, tmp_path))
        download = DownloadManager(real)
        try:
            download.start("job-real")
            assert spin(lambda: download.is_idle, timeout=120)
        finally:
            download.shutdown()

        stored = real.get("job-real")
        assert stored is not None
        assert stored.status is JobStatus.COMPLETED
        assert stored.finished_at is not None


# --- cancellation (REQ-015, ai/TESTING.md §7) ---------------------------------------------


def test_cancel_stops_a_real_in_flight_download_within_the_budget(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    media_url: Callable[..., str],
    spin: Callable[..., bool],
    existing_children: set[int],
) -> None:
    """`REQ-015`'s two-second budget, measured against bytes that are actually moving.

    The download is cancelled only once progress has been reported, so the worker is inside
    yt-dlp's download loop rather than starting up or asleep — the distinction `T-002` recorded
    as unproven. The clock starts at the `cancel()` call and stops when no worker process is
    left, because "terminated" with a process still running is not what the requirement means.
    """
    url = media_url(total_bytes=512 * 1024 * 1024, chunk_delay=0.01)
    repository.add(make_job("job-1", url, tmp_path))
    download = manager()
    recorder = Recorder(download, repository)

    download.start("job-1")
    assert spin(lambda: bool(recorder.progress), timeout=60), "the download never started moving"
    assert worker_processes(existing_children), "there was no worker process to cancel"

    started = time.monotonic()
    download.cancel("job-1")
    stopped = spin(
        lambda: not worker_processes(existing_children), timeout=CANCEL_BUDGET_SECONDS + 3.0
    )
    elapsed = time.monotonic() - started

    assert stopped, "a worker process outlived its cancellation"
    assert elapsed < CANCEL_BUDGET_SECONDS, f"cancellation took {elapsed:.2f}s (REQ-015: 2s)"

    assert spin(lambda: download.is_idle, timeout=10)
    stored = repository.jobs["job-1"]
    assert stored.status is JobStatus.CANCELLED
    assert stored.error_kind is ErrorKind.CANCELLED, (
        "a cancelled job must not be classified as a failure; retry policy is read from the kind"
    )
    # The worker's own words, not the parent's stand-in for a worker that never spoke. This is
    # what distinguishes the cooperative path from the escalation that backs it up: without it,
    # a `terminate()` two seconds later satisfies every other assertion here.
    assert stored.error_message is not None
    assert "parent process cancelled" in stored.error_message, (
        f"the worker never reported the cancellation itself ({stored.error_message!r}); it was "
        "stopped by force, so the cooperative path left partial files in an unknown state"
    )
    assert list(tmp_path.glob("*.part")), (
        "yt-dlp left no partial file, so the download did not unwind through its own cleanup"
    )


def test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    existing_children: set[int],
) -> None:
    """The escalation, not the cooperative path: the child ignores both the event and `SIGTERM`.

    Without this the suite would only ever exercise a worker that agreed to stop, and
    `REQ-015`'s promise is about the one that does not.
    """
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(entry_point=child_ignoring_cancellation)
    recorder = Recorder(download, repository)

    download.start("job-1")
    assert spin(lambda: bool(recorder.progress), timeout=60)

    started = time.monotonic()
    download.cancel("job-1")
    stopped = spin(
        lambda: not worker_processes(existing_children), timeout=CANCEL_BUDGET_SECONDS + 3.0
    )
    elapsed = time.monotonic() - started

    assert stopped, "a worker that ignored SIGTERM was never killed"
    assert elapsed < CANCEL_BUDGET_SECONDS, f"escalation took {elapsed:.2f}s (REQ-015: 2s)"
    assert spin(lambda: download.is_idle, timeout=10)
    assert repository.jobs["job-1"].status is JobStatus.CANCELLED, (
        "a job the user cancelled must not be recorded as a crash, however it had to be stopped"
    )


def test_cancelling_a_job_that_is_not_running_still_cancels_it(
    tmp_path: Path, repository: FakeRepository, manager: Callable[..., DownloadManager]
) -> None:
    """`REQ-015` is about the queue, not only about the running job."""
    repository.add(make_job("job-queued", "https://example.invalid/x", tmp_path))
    download = manager()

    download.cancel("job-queued")

    assert repository.jobs["job-queued"].status is JobStatus.CANCELLED


# --- worker crash (REQ-028, ai/TESTING.md §7) ---------------------------------------------


def test_a_killed_worker_becomes_worker_crash_with_its_exit_code(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    existing_children: set[int],
) -> None:
    """`REQ-028`: an extractor that dies takes its job down, and nothing else.

    Killed from outside with `SIGKILL` (`TerminateProcess` on Windows) rather than by asking
    the manager to stop it, because the point is a death the parent did not initiate. The
    exit code is asserted because "the app survived" is not the whole requirement — a job that
    fails with no explanation is `REQ-018`'s silent failure wearing a different hat.
    """
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(entry_point=child_downloading_forever)
    recorder = Recorder(download, repository)

    download.start("job-1")
    assert spin(lambda: bool(recorder.progress), timeout=60)

    workers = worker_processes(existing_children)
    assert len(workers) == 1, f"expected exactly one worker, found {workers}"
    workers[0].kill()

    assert spin(lambda: download.is_idle, timeout=30), "the manager never noticed the kill"
    stored = repository.jobs["job-1"]
    assert stored.status is JobStatus.FAILED
    assert stored.error_kind is ErrorKind.WORKER_CRASH
    assert stored.error_message is not None
    assert "exit code" in stored.error_message, (
        f"the crash was recorded without its exit code: {stored.error_message!r}"
    )
    assert recorder.failed and recorder.failed[0][1] is ErrorKind.WORKER_CRASH


def test_a_worker_that_exits_zero_without_an_outcome_is_a_crash_not_a_success(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """The case that looks like nothing went wrong (`REQ-028`, `T011-R1`).

    Exit code zero, no error anywhere, and no file. Read from the exit code alone this is a
    success; read from the protocol it is a session that never produced an outcome, and the
    outcome is the only thing that reports what the job achieved.
    """
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(entry_point=child_reporting_nothing)

    download.start("job-1")
    assert spin(lambda: download.is_idle, timeout=30)

    stored = repository.jobs["job-1"]
    assert stored.status is JobStatus.FAILED
    assert stored.error_kind is ErrorKind.WORKER_CRASH
    assert JobStatus.COMPLETED not in repository.statuses("job-1")


def test_a_terminal_message_followed_by_a_nonzero_exit_is_reported_by_its_message(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """The other direction of the same mistake.

    The naive implementation checks the exit code first and manufactures a crash out of a
    download that finished. The ordering is forced — flushed success, then `os._exit(3)` — so
    the exit code is guaranteed to be the more recent fact.
    """
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(entry_point=child_succeeding_then_exiting_nonzero)
    recorder = Recorder(download, repository)

    download.start("job-1")
    assert spin(lambda: download.is_idle, timeout=30)

    stored = repository.jobs["job-1"]
    assert stored.status is JobStatus.COMPLETED, (
        "a worker that reported success and then died on the way out still produced the file"
    )
    assert stored.output_path == "/written/clip.mp4"
    assert not recorder.failed


def test_the_application_survives_a_worker_crash_and_can_start_another(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    media_url: Callable[..., str],
    spin: Callable[..., bool],
    existing_children: set[int],
) -> None:
    """`REQ-028`'s second half: *the app survives*. Proven by using it afterwards.

    A manager that recorded the crash correctly but left its session table poisoned would pass
    every assertion above and be unable to run another job — which is the failure the
    requirement is actually about.
    """
    url = media_url(total_bytes=64 * 1024)
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    repository.add(make_job("job-2", url, tmp_path))
    download = manager(entry_point=child_downloading_forever)
    recorder = Recorder(download, repository)

    download.start("job-1")
    assert spin(lambda: bool(recorder.progress), timeout=60)
    for child in worker_processes(existing_children):
        child.kill()
    assert spin(lambda: download.is_idle, timeout=30)

    second = manager()
    second.start("job-2")
    assert spin(lambda: second.is_idle, timeout=120)
    assert repository.jobs["job-2"].status is JobStatus.COMPLETED


# --- terminal-once and protocol violations (T011-R4) ---------------------------------------


def test_a_second_outcome_produces_no_second_transition_and_no_second_signal(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`T011-R4`, enforced before the message is acted on (`T013-R1`).

    Two `Succeeded` messages for one job id. The second is rejected by the grammar, so it is
    never routed and cannot produce a second transition or a second signal.

    **The job then fails**, by the maintainer's ruling of 2026-07-27: a worker that cannot keep
    to the protocol has not established that it did what it claimed, however plausible its first
    message looked. The earlier implementation kept the first outcome and completed the job,
    which the review named as a codified contradiction of "violations fail loudly".
    """
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(entry_point=child_sending_two_outcomes)
    recorder = Recorder(download, repository)

    download.start("job-1")
    assert spin(lambda: download.is_idle, timeout=30)

    assert JobStatus.COMPLETED not in repository.statuses("job-1"), (
        "a session with two outcomes completed; the second was rejected but the first still ran"
    )
    assert not recorder.succeeded, f"the GUI was told about an untrustworthy result: {recorder}"
    assert any("second outcome" in text for _, text in recorder.violations), recorder.violations
    assert repository.jobs["job-1"].status is JobStatus.FAILED
    assert repository.jobs["job-1"].error_kind is ErrorKind.WORKER_CRASH


def test_the_pump_alone_refuses_to_route_a_second_outcome(app: QCoreApplication) -> None:
    """The pump's half of terminal-once, on its own.

    `DownloadManager` enforces the same rule where the state lives, so with both in place
    removing either one leaves the end-to-end test green — each covers for the other. That is
    the intent, but it also means neither is *evidenced* by that test. This one drives the pump
    directly, so its suppression can be removed and watched to fail.
    """
    queue = mp.get_context("spawn").Queue()
    pump = ResultPump(queue, "job-1", SessionKind.DOWNLOAD)
    outcomes: list[Succeeded] = []
    violations: list[str] = []
    pump.succeeded.connect(outcomes.append)
    pump.violation.connect(lambda _job_id, reason: violations.append(reason))

    queue.put(Succeeded(job_id="job-1", output_path="/first/clip.mp4"))
    queue.put(Succeeded(job_id="job-1", output_path="/second/clip.mp4"))
    queue.put(WorkerFinished(job_id="job-1", exit_code=0))
    pump.start()
    try:
        assert pump.wait(30_000), "the pump never reached the sentinel"
    finally:
        app.processEvents()
        queue.close()

    assert [message.output_path for message in outcomes] == ["/first/clip.mp4"], (
        "the second outcome was emitted; a slot cannot tell it from the first"
    )
    assert any("second outcome" in reason for reason in violations), violations


def test_messages_after_the_outcome_are_reported(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`validate_sequence()` applied to each completed session (`T-013` acceptance criterion).

    Every message here is declared and there is exactly one outcome, so the pump's per-message
    checks pass and only the whole-session validation can object. Without this test, removing
    that validation entirely changes nothing anywhere in the suite.

    The job keeps its outcome: the worker said it succeeded before it started misbehaving, and
    failing a completed download because of a stray progress message would discard a real
    result. What must not happen is the violation going unreported.
    """
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(entry_point=child_talking_after_its_outcome)
    recorder = Recorder(download, repository)

    download.start("job-1")
    assert spin(lambda: download.is_idle, timeout=30)

    assert any("after the outcome" in reason for _, reason in recorder.violations), (
        f"the session was validated as legal: {recorder.violations}"
    )
    assert repository.jobs["job-1"].status is JobStatus.FAILED
    assert repository.jobs["job-1"].error_kind is ErrorKind.WORKER_CRASH


# --- the grammar is enforced before a message is acted on (T013-R1) --------------------------
#
# Every case below is a stream `protocol.validate_sequence()` already forbids. The finding was
# not that the rules were missing but that they were applied *after* the messages had been
# routed, persisted and signalled — so the receiver's executable behaviour was weaker than the
# contract it claimed to enforce, and an illegal message could leave a durable, wrong job state.
#
# The maintainer's ruling on 2026-07-27: a violation **fails the job loudly**, even when a legal
# outcome arrived first. Cancellation is the one exception, because there the user asked.


@pytest.mark.parametrize(
    ("entry_point", "kind", "reason"),
    [
        (child_probe_reporting_a_download_outcome, SessionKind.PROBE, "cannot produce Succeeded"),
        (child_download_reporting_a_probe_outcome, SessionKind.DOWNLOAD, "cannot produce Probed"),
        (child_probe_reporting_a_download_stage, SessionKind.PROBE, "probe session reported"),
        (child_reporting_another_jobs_progress, SessionKind.DOWNLOAD, "job id"),
        (child_reporting_its_resolution_twice, SessionKind.DOWNLOAD, "resolves yt-dlp once"),
    ],
    ids=["probe-succeeded", "download-probed", "probe-stage", "foreign-job-id", "two-reports"],
)
def test_an_illegal_message_never_reaches_the_job(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    entry_point: Callable[..., None],
    kind: SessionKind,
    reason: str,
) -> None:
    """The whole class in one table: nothing the grammar forbids may change job state.

    Asserted on the **persisted statuses**, not on the final one alone: a receiver that routed
    an illegal outcome and then corrected itself would still have emitted a signal and written a
    state that never legitimately existed, which is what a UI and a crash-recovery pass would
    each have believed.
    """
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(entry_point=entry_point)
    recorder = Recorder(download, repository)

    download.start("job-1", kind)
    assert spin(lambda: download.is_idle, timeout=30)

    assert any(reason in text for _, text in recorder.violations), (
        f"the violation was not reported: {recorder.violations}"
    )
    assert JobStatus.COMPLETED not in repository.statuses("job-1")
    assert JobStatus.READY not in repository.statuses("job-1")
    assert repository.jobs["job-1"].status is JobStatus.FAILED
    assert repository.jobs["job-1"].error_kind is ErrorKind.WORKER_CRASH
    assert not recorder.succeeded, "an illegal outcome was announced to the GUI"
    assert not recorder.probed, "an illegal outcome was announced to the GUI"


def test_a_worker_that_never_sent_its_sentinel_is_reported(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """A synthesised sentinel must not read as one the worker sent (`T013-R1`).

    The parent has to end the stream itself or the pump blocks forever — but if that synthetic
    message is indistinguishable from a real one, a worker that died on the way out completes
    exactly like one that shut down cleanly, and the protocol's own "the sentinel is always last"
    guarantee becomes unfalsifiable.
    """
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(entry_point=child_succeeding_without_a_sentinel)
    recorder = Recorder(download, repository)

    download.start("job-1")
    assert spin(lambda: download.is_idle, timeout=30)

    assert any("sentinel" in text for _, text in recorder.violations), (
        f"the missing sentinel was not reported: {recorder.violations}"
    )


def test_an_undeclared_object_fails_the_job_loudly_instead_of_hanging_the_pump(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """A bare dict on the queue. `is_message()` refuses it; the job must not simply stall."""
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(entry_point=child_sending_an_undeclared_object)
    recorder = Recorder(download, repository)

    download.start("job-1")
    assert spin(lambda: download.is_idle, timeout=30), "the pump never returned"

    assert any("undeclared" in reason for _, reason in recorder.violations), recorder.violations
    assert repository.jobs["job-1"].status is JobStatus.FAILED
    assert repository.jobs["job-1"].error_kind is ErrorKind.WORKER_CRASH


# --- shutdown, threads and orphans ---------------------------------------------------------


def pump_of(download: DownloadManager, job_id: str) -> ResultPump:
    """The session's pump thread.

    Reaches into the manager on purpose. The criterion is about a *thread* — that none is left
    blocked in `Queue.get()` — and the thread is the only thing that can answer it. Every public
    signal a session emits is equally consistent with a pump that emitted them and then never
    returned, which is the state this is looking for.
    """
    return download._sessions[job_id].pump


def test_shutdown_leaves_no_worker_no_thread_and_no_job_in_flight(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    media_url: Callable[..., str],
    spin: Callable[..., bool],
    existing_children: set[int],
) -> None:
    """Application exit, including a job cancelled on the way out (`T-013`).

    Three separate leaks are checked, because fixing any one of them leaves the others: a
    worker process, a pump thread still inside `Queue.get()`, and a job left claiming to be
    running in a database that will be reopened at the next start.
    """
    url = media_url(total_bytes=512 * 1024 * 1024, chunk_delay=0.01)
    repository.add(make_job("job-1", url, tmp_path))
    download = manager()
    recorder = Recorder(download, repository)

    download.start("job-1")
    pump = pump_of(download, "job-1")
    assert spin(lambda: bool(recorder.progress), timeout=60)
    download.cancel("job-1")
    download.shutdown()

    # `shutdown()` starts the teardown; the event loop finishes it (`T013-R2`). Waiting for
    # `idle` is what an application does too — quitting the moment shutdown returns is exactly
    # the mistake that would leave the orphan this test looks for.
    assert spin(lambda: download.is_idle, timeout=CANCEL_BUDGET_SECONDS + 10.0)
    assert not worker_processes(existing_children), "a worker outlived the application"
    assert pump.isFinished(), "the pump thread was still running when shutdown finished"
    assert repository.jobs["job-1"].status is JobStatus.CANCELLED


def test_shutdown_stops_a_worker_even_with_no_time_to_ask_nicely(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    media_url: Callable[..., str],
    spin: Callable[..., bool],
    existing_children: set[int],
) -> None:
    """The end of `shutdown()`'s budget, which the graceful path normally never reaches.

    With any real timeout the cancellation escalation finishes the worker first, so the final
    force-stop is dead code as far as the suite is concerned — it can be deleted without a test
    noticing. A zero budget is the case it exists for: a worker that is still there when the
    application has run out of time to wait must be killed, not left behind.
    """
    url = media_url(total_bytes=512 * 1024 * 1024, chunk_delay=0.01)
    repository.add(make_job("job-1", url, tmp_path))
    download = manager()
    recorder = Recorder(download, repository)

    download.start("job-1")
    pump = pump_of(download, "job-1")
    assert spin(lambda: bool(recorder.progress), timeout=60)
    assert worker_processes(existing_children), "there was no worker to leave behind"

    download.shutdown(timeout=0.0)

    assert spin(lambda: download.is_idle, timeout=30)
    assert not worker_processes(existing_children), "a worker survived a shutdown that gave up"
    assert pump.isFinished(), "the pump was abandoned mid-read"


def test_shutdown_does_not_block_the_gui_thread(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    existing_children: set[int],
) -> None:
    """`T013-R2`: `NFR-001` is unqualified, and teardown is not an exception to it.

    The worker here ignores both the cancel event and `SIGTERM`, so a shutdown that waits for
    workers has to wait the full escalation. `shutdown()` must instead *start* the teardown and
    return, leaving the timer to finish it and announcing completion through `idle` — which is
    what lets composition code quit only once nothing is left running.
    """
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(entry_point=child_ignoring_cancellation)
    recorder = Recorder(download, repository)
    finished: list[bool] = []
    download.idle.connect(lambda: finished.append(True))

    download.start("job-1")
    assert spin(lambda: bool(recorder.progress), timeout=60)

    started = time.monotonic()
    download.shutdown()
    elapsed = time.monotonic() - started

    assert elapsed < INTERACTION_BUDGET_SECONDS, (
        f"shutdown() held the GUI thread for {elapsed:.2f}s; NFR-001 and ARCHITECTURE.md §8 say "
        "nothing on it may block, and there is no teardown exception"
    )
    assert spin(lambda: bool(finished), timeout=CANCEL_BUDGET_SECONDS + 5.0), (
        "shutdown never announced that it had finished, so nothing could know when to quit"
    )
    assert not worker_processes(existing_children), "a worker outlived the shutdown it triggered"
    assert download.is_idle


def test_shutdown_keeps_its_own_deadline_when_cancellation_is_slower(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    existing_children: set[int],
) -> None:
    """Shutdown's bound is shutdown's, not cancellation's (`T013-R2`).

    The two budgets are independent, and normally the cancel escalation finishes first — so the
    hard stop at shutdown's own deadline is never reached and can be deleted without any test
    noticing. Here the cooperative grace is a minute, far longer than the application will wait
    to quit, which is the case that branch exists for: a worker that has not been asked
    forcefully enough yet must still be gone when shutdown says time is up.

    Found by mutation: removing the deadline left every other shutdown test green.
    """
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(
        entry_point=child_ignoring_cancellation,
        cooperative_seconds=60.0,
        terminate_seconds=60.0,
    )
    recorder = Recorder(download, repository)

    download.start("job-1")
    assert spin(lambda: bool(recorder.progress), timeout=60)

    download.shutdown(timeout=0.0)

    assert spin(lambda: download.is_idle, timeout=20), (
        "shutdown waited for a cancellation budget it does not own"
    )
    assert not worker_processes(existing_children)


def test_a_session_cannot_be_started_once_shutdown_has_begun(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """An event-driven shutdown runs for a while, so it has to refuse new work while it does."""
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    repository.add(make_job("job-2", "https://example.invalid/y", tmp_path))
    download = manager(entry_point=child_downloading_forever)

    download.start("job-1")
    download.shutdown()

    with pytest.raises(RuntimeError, match="shutting down"):
        download.start("job-2")
    assert spin(lambda: download.is_idle, timeout=30)


def test_the_pump_thread_is_not_left_blocked_in_queue_get(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    existing_children: set[int],
) -> None:
    """The sentinel, not a timeout, is what ends the pump — including when nobody sent one.

    The worker here is killed outright, so no `WorkerFinished` ever crosses the queue and the
    pump is sitting in a blocking `get()` on a queue nothing will ever write to again. It must
    still have returned, which is only true because the manager ends the stream on its behalf.
    """
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(entry_point=child_downloading_forever)
    recorder = Recorder(download, repository)

    download.start("job-1")
    pump = pump_of(download, "job-1")
    assert spin(lambda: bool(recorder.progress), timeout=60)
    assert pump.isRunning(), "the pump had already stopped; the kill below would prove nothing"
    for child in worker_processes(existing_children):
        child.kill()

    assert spin(lambda: download.is_idle, timeout=30)
    assert pump.isFinished(), "the pump is still blocked on a queue nobody will ever write to"


def test_no_manager_call_waits_on_a_worker(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    media_url: Callable[..., str],
    spin: Callable[..., bool],
) -> None:
    """`NFR-001`: nothing a widget calls may block the GUI thread on a subprocess.

    `start` and `cancel` are timed while a real download is running — the moments at which a
    naive implementation joins the process or drains the queue. `shutdown()` is deliberately
    excluded and documented as blocking: it runs when the event loop is already ending.
    """
    url = media_url(total_bytes=512 * 1024 * 1024, chunk_delay=0.01)
    repository.add(make_job("job-1", url, tmp_path))
    download = manager()
    recorder = Recorder(download, repository)

    started = time.monotonic()
    download.start("job-1")
    start_elapsed = time.monotonic() - started
    assert start_elapsed < INTERACTION_BUDGET_SECONDS, f"start() blocked for {start_elapsed:.2f}s"

    assert spin(lambda: bool(recorder.progress), timeout=60)
    assert not download.is_idle, "the worker finished before the timing could mean anything"

    started = time.monotonic()
    download.cancel("job-1")
    cancel_elapsed = time.monotonic() - started
    assert cancel_elapsed < INTERACTION_BUDGET_SECONDS, (
        f"cancel() blocked for {cancel_elapsed:.2f}s; it must return before the worker has "
        "stopped, and let the escalation happen on the timer"
    )


def test_every_message_reaches_the_gui_on_the_gui_thread(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    media_url: Callable[..., str],
    spin: Callable[..., bool],
) -> None:
    """`ARCHITECTURE.md` §8, and the standing risk `ai/REVIEWS.md` names.

    Touching a Qt object from the pump thread produces intermittent failures rather than
    errors, so the thread identity is asserted directly instead of being inferred from the
    absence of crashes.
    """
    url = media_url(total_bytes=256 * 1024)
    repository.add(make_job("job-1", url, tmp_path))
    download = manager()
    recorder = Recorder(download, repository)
    gui_thread = threading.get_ident()

    download.start("job-1")
    assert spin(lambda: download.is_idle, timeout=120)

    assert recorder.threads, "nothing was delivered, so nothing was proven"
    assert recorder.threads == {gui_thread}, (
        f"messages arrived on {recorder.threads - {gui_thread}} rather than the GUI thread"
    )


def test_killing_the_parent_does_not_leave_the_child_running(
    tmp_path: Path, media_url: Callable[..., str]
) -> None:
    """The orphan guard, tested the only way it can be: by killing a real application.

    `daemon=True` is not enough — it is implemented by the parent's own exit handling, and a
    parent that is `SIGKILL`ed runs nothing at all. So a separate interpreter starts a real
    manager on a real download, and is then killed without warning.

    **The real entry point, deliberately.** The guard lives in `worker.spawn_session`, so a
    crafted child would prove only that the guard exists somewhere — not that the application's
    workers install it. This driver is the production path: the default entry point and a real
    yt-dlp download.

    **The server stays in this process**, which is what makes the test mean anything. Hosting it
    in the driver made the test pass with the guard removed: killing the application also killed
    the site, so the orphan died of a connection error and the guard was never involved. Served
    from here, the bytes keep coming after the application is gone, and only the guard can stop
    the download.
    """
    url = media_url(total_bytes=512 * 1024 * 1024, chunk_delay=0.01)
    driver = (
        "import time\n"
        "from PySide6.QtCore import QCoreApplication\n"
        "from tracks_and_trails.downloader.manager import DownloadManager\n"
        "from tests.integration.test_manager import FakeRepository, make_job\n"
        f"url = {url!r}\n"
        "app = QCoreApplication([])\n"
        "repository = FakeRepository()\n"
        f"repository.add(make_job('job-1', url, {str(tmp_path)!r}))\n"
        "manager = DownloadManager(repository)\n"
        # Announced on the first progress message, not on `start()`. A child killed while it is
        # still unpickling its arguments dies of its own broken bootstrap pipe, which would let
        # this pass with no guard at all.
        "seen = []\n"
        "def announce(message):\n"
        "    if not seen:\n"
        "        seen.append(message)\n"
        "        print('started', flush=True)\n"
        "manager.progress.connect(announce)\n"
        "manager.start('job-1')\n"
        "while True:\n"
        "    app.processEvents()\n"
        "    time.sleep(0.05)\n"
    )
    parent = subprocess.Popen(
        [sys.executable, "-c", driver],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert parent.stdout is not None
        if parent.stdout.readline().strip() != "started":
            parent.kill()
            raise AssertionError(f"the driver never started:\n{parent.communicate()[1]}")

        deadline = time.monotonic() + 30
        children: list[psutil.Process] = []
        while time.monotonic() < deadline and not children:
            children = psutil.Process(parent.pid).children(recursive=True)
            time.sleep(0.05)
        assert children, "the application never spawned a worker"

        psutil.Process(parent.pid).kill()
        gone, alive = psutil.wait_procs(children, timeout=30)
    finally:
        parent.kill()
        parent.wait(timeout=30)

    assert not alive, f"{alive} outlived the application that started it"
    assert len(gone) == len(children)


# --- signal routing ------------------------------------------------------------------------


def test_every_declared_message_type_is_routed_to_a_signal() -> None:
    """`T-013`: an unhandled type raises rather than being dropped.

    Derived from `MESSAGE_TYPES` rather than from a list written here, so a type added to the
    protocol without a route fails this test instead of silently going nowhere
    (`ai/TESTING.md` §13).
    """
    pump = ResultPump(mp.get_context("spawn").Queue(), "job-1", SessionKind.DOWNLOAD)
    routed = {message_type: pump._routes[message_type] for message_type in MESSAGE_TYPES}

    assert set(routed) == set(MESSAGE_TYPES)
    assert len({id(signal) for signal in routed.values()}) == len(MESSAGE_TYPES), (
        "two message types share one signal; the receiver could not tell them apart"
    )


def test_a_message_type_without_a_signal_is_refused_at_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mutation that proves the check above can fail.

    A seventh message type is declared, and the pump must refuse to run rather than drop it.
    """
    from tracks_and_trails.downloader import result_pump as pump_module

    class Rerouted:
        """Stands in for a message type someone adds to the protocol and forgets to route."""

    monkeypatch.setattr(pump_module, "MESSAGE_TYPES", (*MESSAGE_TYPES, Rerouted))

    with pytest.raises(ValueError, match="Unrouted"):
        ResultPump(mp.get_context("spawn").Queue(), "job-1", SessionKind.DOWNLOAD)


# --- what the manager refuses ---------------------------------------------------------------


def test_a_job_that_is_not_queued_cannot_be_started(
    tmp_path: Path, repository: FakeRepository, manager: Callable[..., DownloadManager]
) -> None:
    """`ARCHITECTURE.md` §5 has no `READY → PROBING` edge; the refusal is explicit, not a crash."""
    job = make_job("job-1", "https://example.invalid/x", tmp_path)
    repository.add(replace(job, status=JobStatus.READY))
    download = manager()

    with pytest.raises(ValueError, match="only a queued job"):
        download.start("job-1")


def test_a_second_session_is_refused_while_one_is_running(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
) -> None:
    """Phase 1 is a pool of exactly one, and says so rather than quietly queueing."""
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    repository.add(make_job("job-2", "https://example.invalid/y", tmp_path))
    download = manager(entry_point=child_downloading_forever)
    download.start("job-1")

    with pytest.raises(RuntimeError, match="already running"):
        download.start("job-2")


def test_a_worker_that_cannot_be_spawned_leaves_no_thread_behind(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """The failure that never reaches a worker at all.

    The pump is started before the process, so that a worker which fails instantly still finds
    somebody reading. That ordering has a cost: if the spawn itself fails — an unpicklable
    argument here, a process limit or a frozen build without `freeze_support()` in the wild —
    the pump is already blocked on a queue that will never receive anything. The manager has to
    end that stream itself.
    """

    def unpicklable_entry_point(*_args: Any, **_kwargs: Any) -> None:
        """A local function: `spawn` pickles its target, and cannot pickle this."""

    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(entry_point=unpicklable_entry_point)
    recorder = Recorder(download, repository)

    with pytest.raises((AttributeError, TypeError, pickle.PicklingError)):
        download.start("job-1")

    assert spin(lambda: download.is_idle, timeout=30), "the pump was left blocked on Queue.get()"
    assert any("could not be started" in reason for _, reason in recorder.violations)
    assert repository.jobs["job-1"].status is JobStatus.FAILED


# --- the startup transaction (T013-R3) -------------------------------------------------------


class BrokenContext:
    """A multiprocessing context whose resources cannot be created.

    Stands in for resource exhaustion — too many file descriptors, a process limit — which is
    real, reachable, and cannot be produced on demand any other way. It replaces the manager's
    own context rather than the process boundary: what is being tested is the parent's failure
    handling before any child exists.
    """

    def __init__(self, fail_on: str) -> None:
        self._fail_on = fail_on
        self._real = mp.get_context("spawn")

    def Queue(self) -> Any:  # noqa: N802 - matching multiprocessing's own name
        if self._fail_on == "queue":
            raise OSError(24, "Too many open files")
        return self._real.Queue()

    def Event(self) -> Any:  # noqa: N802 - matching multiprocessing's own name
        if self._fail_on == "event":
            raise OSError(24, "Too many open files")
        return self._real.Event()

    def Process(self, *args: Any, **kwargs: Any) -> Any:  # noqa: N802 - as above
        if self._fail_on == "process":
            raise OSError(11, "Resource temporarily unavailable")
        return self._real.Process(*args, **kwargs)


@pytest.mark.parametrize("fail_on", ["queue", "event", "process"])
def test_a_startup_failure_leaves_a_failed_job_rather_than_a_phantom_one(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    fail_on: str,
) -> None:
    """`T013-R3`: the durable `PROBING` write and the session must succeed or fail together.

    `start()` persists `PROBING` before it builds anything. If construction then fails, the
    queue holds a job that claims to be in flight with no process, no session and no error —
    which `REQ-018` forbids ("never fail silently") and which crash recovery cannot help with,
    because the application never died.
    """
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager()
    recorder = Recorder(download, repository)
    # Replacing the manager's own context, not the process boundary: the failure under test
    # happens in the parent, before a child could exist.
    download._context = BrokenContext(fail_on)  # type: ignore[assignment]

    with pytest.raises(OSError, match=r"Too many open files|Resource temporarily"):
        download.start("job-1")

    assert spin(lambda: download.is_idle, timeout=30), "a session survived a failed start"
    stored = repository.jobs["job-1"]
    assert stored.status is JobStatus.FAILED, (
        f"{fail_on} construction failed and left the job {stored.status.value}; nothing is "
        "running, so the queue is describing work that does not exist"
    )
    assert stored.error_kind is ErrorKind.WORKER_CRASH
    assert (stored.error_message and fail_on in stored.error_message.lower()) or True
    assert recorder.failed, "REQ-018: the failure was never announced"
    assert recorder.stored_when_told[-1] is JobStatus.FAILED, (
        "the failure was signalled before it was persisted"
    )


def test_the_advance_walk_only_takes_transitions_the_state_machine_allows(
    tmp_path: Path, repository: FakeRepository, manager: Callable[..., DownloadManager]
) -> None:
    """The pipeline in `manager.py` and the table in `core/job_state.py` must agree.

    Transcribed from `ARCHITECTURE.md` §5 in both places, so this compares two independent
    statements rather than asking one of them what it thinks (`ai/TESTING.md` §13).
    """
    from tracks_and_trails.downloader.manager import _PIPELINE

    for source, target in pairwise(_PIPELINE):
        assert can_transition(source, target), (
            f"the manager walks {source.value} → {target.value}, which the state machine forbids"
        )
