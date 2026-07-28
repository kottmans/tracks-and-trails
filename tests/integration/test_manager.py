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

import contextlib
import multiprocessing as mp
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import replace
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import pairwise
from pathlib import Path
from typing import Any, Final

import psutil
import pytest
from PySide6.QtCore import QCoreApplication

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus, can_transition
from tracks_and_trails.core.models import DownloadRequest, Job
from tracks_and_trails.downloader import process_tree
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
from tracks_and_trails.downloader.result_pump import POLL_SECONDS, ResultPump

REPO_ROOT = Path(__file__).parents[2]

#: **These are back in the default run** (`T-019`, 2026-07-27).
#:
#: They spent one day behind `-m process_tree`. Every test here spawns a real worker and most of
#: them kill it, so they were the first to suffer from the defect `T-019` owned — cancelling
#: reaped the worker but not what the worker spawned, and the loose descendants wedged later runs
#: intermittently: the same suite finishing in 19 seconds twice and then sitting past ten minutes.
#:
#: The defect is fixed, so the reason is gone and the marker with it. `ai/TESTING.md` §7's
#: Cancellation and Worker-crash areas live in this file, and they are covered by a plain
#: `pytest` again.
#:
#: The episode is worth remembering rather than marking: while the exclusion stood, `T019-R1`
#: found that `addopts` had removed these from **CI** as well, so two mandatory areas gated
#: nothing anywhere for a day while three records said otherwise.

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

    def update(self, job: Job, done: Callable[[str | None], None] | None = None) -> None:
        """`ARC-005`'s asynchronous shape, completed synchronously.

        A zero-latency stand-in: these tests are about what the manager persists and in what
        order, not about how long a disk takes. `test_the_manager_drives_the_real_repository`
        runs the same path through `PersistentJobStore` and the real writer, so this cannot
        drift into a shape nothing implements.
        """
        if job.id not in self.jobs:
            raise KeyError(job.id)
        self.jobs[job.id] = job
        self.writes.append((job.id, job.status))
        if done is not None:
            done(None)

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


#: A string that appears in the command line of every process these tests spawn as a stand-in
#: for `ffmpeg`, and nowhere else. It is how the teardown below finds strays it can safely kill —
#: including ones that have been reparented away and are no longer descendants of this process.
GRANDCHILD_MARKER: Final = "tracks-and-trails-test-descendant"

#: What a leaked grandchild runs: a process that outlives anything short of being killed.
#:
#: It ignores `SIGTERM` where that exists, so a test that passes has actually reached the
#: `SIGKILL` half of the escalation rather than being flattered by a polite descendant.
GRANDCHILD_PROGRAM: Final = (
    f"# {GRANDCHILD_MARKER}\n"
    "import signal, sys, time\n"
    "if hasattr(signal, 'SIGTERM'):\n"
    "    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "print('up', flush=True)\n"
    "while True:\n"
    "    time.sleep(0.05)\n"
)

#: A process that spawns one of the above and reports its pid — a **real** second level, which
#: is what the detector self-test needs and what its first version did not have.
NESTED_GRANDCHILD_PROGRAM: Final = (
    f"# {GRANDCHILD_MARKER}\n"
    "import subprocess, sys, time\n"
    f"child = subprocess.Popen([sys.executable, '-c', {GRANDCHILD_PROGRAM!r}])\n"
    "print(child.pid, flush=True)\n"
    "while True:\n"
    "    time.sleep(0.05)\n"
)


def start_a_grandchild() -> subprocess.Popen[str]:
    """A real process, one level below whoever calls this. Stands in for `ffmpeg`."""
    child = subprocess.Popen(
        [sys.executable, "-c", GRANDCHILD_PROGRAM],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    assert child.stdout is not None
    child.stdout.readline()  # it is running, not merely created
    return child


#: A grandchild that stops *politely*: it handles `SIGTERM` by recording that it was asked.
#:
#: The marker file is what distinguishes the two ways a descendant can die. Being killed with
#: the session leaves no marker; being asked first, at the cooperative deadline, leaves one.
POLITE_GRANDCHILD_PROGRAM: Final = (
    "import signal, sys, time\n"
    "marker = sys.argv[1]\n"
    "def asked(signum, frame):\n"
    "    open(marker, 'w').write('asked')\n"
    "    raise SystemExit(0)\n"
    "signal.signal(signal.SIGTERM, asked)\n"
    "print('up', flush=True)\n"
    "while True:\n"
    "    time.sleep(0.05)\n"
)


def child_with_a_polite_grandchild(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """A worker whose descendant exits cleanly when asked, and records that it was asked."""
    from tracks_and_trails.downloader import worker

    worker.prepare_this_worker()
    marker = str(Path(request.output_directory) / "the-grandchild-was-asked")
    child = subprocess.Popen(
        [sys.executable, "-c", POLITE_GRANDCHILD_PROGRAM, marker],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    assert child.stdout is not None
    child.stdout.readline()
    queue.put(Progress(job_id=job_id, stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=1))
    while True:
        time.sleep(0.05)


def child_with_a_grandchild_of_its_own(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """A worker shaped like the real one: contained, reporting progress, holding a child.

    **`prepare_this_worker()` is exactly what production runs**, from `worker.spawn_session`,
    before the session starts. Calling the same function rather than repeating its two steps is
    what keeps a stand-in worker the same shape as a real one; that `spawn_session` calls it is
    proven separately against real workers.

    yt-dlp's `ffmpeg` is the process this stands in for. Reproducing the real thing would need a
    mergeable source and an ffmpeg on the runner; what matters to `T-019` is that the worker has
    a descendant that does not die when the worker does, and this is exactly that.
    """
    from tracks_and_trails.downloader import worker

    worker.prepare_this_worker()
    start_a_grandchild()
    queue.put(Progress(job_id=job_id, stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=1))
    while True:
        time.sleep(0.05)


# --- process bookkeeping ------------------------------------------------------------------


#: The one thing that is *not* a leaked process: `multiprocessing`'s resource tracker.
#:
#: Creating the first `Event` spawns it, it is a child of this process, and it lives for the rest
#: of the session — so a cancellation test run in isolation saw it, called it a surviving worker
#: and failed, while the same test passed in a full run where something earlier had started it.
RESOURCE_TRACKER_MARKER: Final = "multiprocessing.resource_tracker"


def worker_processes(before: set[int]) -> list[psutil.Process]:
    """Every process this test process has spawned, at any depth, that was not there before.

    **This used to filter to `spawn_main` in the command line, and that made the `T-019` defect
    invisible.** An `ffmpeg` grandchild is not a worker, so every orphan assertion in this file
    was blind to exactly the process that was surviving cancellation — the tests passed while a
    merge kept writing to the disk.

    The exclusion that was right stays, and is now the *only* one: `multiprocessing`'s resource
    tracker is infrastructure, not a leak. Everything else that appeared under this process is
    reported, because "a process we started that is still running" is the property these tests
    are actually about. Zombies are excluded for the same reason as before — a reaped-but-not-yet
    collected child is not doing work, and on Linux one exists for a moment after every kill.

    The tests assert something *is* found before they kill anything, so a filter that narrows
    back into blindness fails loudly rather than passing quietly.
    """
    live: list[psutil.Process] = []
    for child in psutil.Process(os.getpid()).children(recursive=True):
        try:
            if child.pid in before or child.status() == psutil.STATUS_ZOMBIE:
                continue
            if RESOURCE_TRACKER_MARKER in " ".join(child.cmdline()):
                continue
            live.append(child)
        except psutil.NoSuchProcess, psutil.AccessDenied:  # it exited mid-question
            continue
    return live


def still_running(pids: Iterable[int]) -> list[int]:
    """Which of `pids` are still alive — **whoever their parent is now**.

    `worker_processes()` walks descendants, and a descendant walk goes blind at precisely the
    moment `T-019` is about: when the worker dies, its child is reparented to `init` and stops
    being our descendant at all. "No descendants remain" then becomes true without anything
    having been reaped, and the test that removed the reaping passed.

    Verified rather than reasoned about: a probe spawned a child and a grandchild, killed the
    child, and watched the grandchild keep running while vanishing from the recursive walk.

    So a test that is about survival captures the pids while the tree is still intact and asks
    about them by identity afterwards.

    **On Windows, aliveness is decided by exit status rather than by visibility** (`T-056`). The
    previous form asked `status()` everywhere and treated anything but `STATUS_ZOMBIE` as running.
    That is a POSIX answer: Windows has no zombie state, and a terminated process stays visible
    for as long as any handle to it remains open — including the `Popen` handle the test that
    killed it is still holding. `windows-latest` produced the consequence once, in run
    `30323328299`, where `still_running([dead_pid])` returned a pid the test had already reaped.

    `wait(timeout=0)` asks whether the process has *ended*: it returns an exit status if it has,
    raises `TimeoutExpired` if it has not, and raises `NoSuchProcess` if there is nothing there.
    On Windows psutil implements it with `WaitForSingleObject` on its own handle, which neither
    disturbs anyone else's handle nor depends on visibility.

    **It is deliberately not used on POSIX**, and the reason is a defect this correction caused
    before it caught it: there, `wait()` on a child of this process is `waitpid`, so it *reaps*
    the worker and steals the exit status `multiprocessing` is waiting for. `is_alive()` then
    never reports the process as gone and the manager never goes idle —
    `test_cancelling_a_download_kills_what_the_worker_spawned` failed exactly that way. On POSIX
    the zombie state is the terminated-but-visible state, so `status()` is already the right
    question and there is nothing to fix.

    **Could the previous form have reported a live process as dead?** No, and this is worth
    stating rather than assuming, because a false *dead* would make a reaping assertion pass
    without anything having been reaped. It answered "dead" only on `NoSuchProcess` — raised when
    the pid is gone, and by `ZombieProcess`, its subclass — or on a `STATUS_ZOMBIE` that a live
    process never has. `AccessDenied` was not caught, so it would have failed loudly rather than
    lied. Its one error direction was **false alive**, which fails an assertion in the open.
    """
    alive = []
    for pid in pids:
        try:
            process = psutil.Process(pid)
            if sys.platform == "win32":
                process.wait(timeout=0)
            elif process.status() != psutil.STATUS_ZOMBIE:
                alive.append(pid)
        except psutil.NoSuchProcess:
            continue
        except psutil.TimeoutExpired:
            alive.append(pid)
    return alive


@pytest.fixture
def existing_children() -> set[int]:
    return {child.pid for child in psutil.Process(os.getpid()).children(recursive=True)}


@pytest.fixture(autouse=True)
def no_test_descendant_outlives_its_test() -> Iterator[None]:
    """Reap this file's stand-in `ffmpeg` processes however the test ends (`T019-R4`).

    Cleanup that runs *after* the assertions never runs when an assertion fails — and a mutation
    is meant to make assertions fail. The review of `T-019` found **111** of these still alive,
    some for over two hours, left behind by mutation runs that were working exactly as intended.
    They then wedge later runs, which is how a test suite starts lying about unrelated things.

    So it is a fixture, not a `finally` inside each test: it runs on every exit path including a
    failure, an error, and a keyboard interrupt. Identification is by the exact marker these
    programs carry, so it can only ever kill this file's own helpers — and it finds them by
    scanning all processes rather than by walking descendants, because the ones that matter have
    been reparented away from us by the time anything goes wrong.
    """
    yield
    for process in psutil.process_iter(["cmdline"]):
        with contextlib.suppress(psutil.Error):
            if any(GRANDCHILD_MARKER in part for part in (process.info["cmdline"] or ())):
                process.kill()


def test_the_survival_check_can_tell_a_live_process_from_a_dead_one() -> None:
    """`still_running` decides every T-019 assertion, so it needs one of its own.

    A mutation that made it always return "nothing alive" left the whole process-tree suite
    green: every `assert not still_running(...)` became trivially true. A helper that carries
    assertions is a guard, and a guard nobody watches fail is the shape `ai/TESTING.md` §13 is
    about — the same lesson as the orphan detector, one layer up.
    """
    alive = start_a_grandchild()
    dead = start_a_grandchild()
    dead_pid = dead.pid
    dead.kill()
    dead.wait(timeout=30)

    # **Killed and deliberately not waited on** (`T-056`). This is the shape that failed on
    # `windows-latest` in run `30323328299`: the process has ended, and the handle the killer is
    # still holding keeps it visible, so a presence check calls it alive. On POSIX the same shape
    # is a zombie, which the previous form already handled — which is exactly why the gap could
    # only ever have been found on Windows, and why this assertion means more there than here.
    unreaped = start_a_grandchild()
    unreaped_pid = unreaped.pid
    unreaped.kill()
    try:
        assert still_running([alive.pid]) == [alive.pid], "a running process was reported dead"
        assert still_running([dead_pid]) == [], "a reaped process was reported alive"
        assert still_running([]) == []
        # A short spin rather than an instant assertion: `kill()` asks, and the process ends a
        # moment later on either platform.
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and still_running([unreaped_pid]):
            time.sleep(0.02)
        assert still_running([unreaped_pid]) == [], (
            "a killed process that nobody has waited on was reported alive; on Windows that is "
            "the whole of T-056, and every T-019 reaping assertion rests on this answer"
        )
        assert still_running([alive.pid]) == [alive.pid], (
            "asking about the dead one changed the answer about the live one"
        )
    finally:
        alive.kill()
        alive.wait(timeout=30)
        unreaped.wait(timeout=30)


def test_the_detector_sees_a_grandchild_and_not_just_a_worker(
    existing_children: set[int],
) -> None:
    """`T-019`: the orphan detector is permanently self-tested.

    This is the test that would have caught the defect. `worker_processes()` filtered on
    `spawn_main` in the command line, so an `ffmpeg` grandchild was invisible to it — every
    orphan assertion in this file was passing while the exact process that survived cancellation
    was excluded from the question by construction.

    A detector nobody re-exercises looks identical to one that works, which is the Phase 0
    evidence problem in miniature. So this leaks a real child **and** a real grandchild, and
    asserts both are reported by pid.
    """
    child = subprocess.Popen(
        [sys.executable, "-c", NESTED_GRANDCHILD_PROGRAM],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    grandchild_pid: int | None = None
    try:
        assert child.stdout is not None
        grandchild_pid = int(child.stdout.readline())

        # **A real second level, asserted before anything else.** The first version of this test
        # spawned two *siblings* and asserted their relationship with `... or True`, which cannot
        # fail — so it proved the detector saw two direct children and said nothing at all about
        # the depth it exists to check (`T019-R4`).
        assert psutil.Process(grandchild_pid).ppid() == child.pid, (
            f"{grandchild_pid} is not a child of {child.pid}, so this test is not about a "
            "grandchild at all"
        )

        found = {process.pid for process in worker_processes(existing_children)}

        assert child.pid in found, "the detector missed a direct child"
        assert grandchild_pid in found, (
            "the detector missed a second-level process. This is the T-019 blindness: an ffmpeg "
            "grandchild is not a worker, and a filter that only recognises workers cannot see it."
        )
    finally:
        for pid in (grandchild_pid, child.pid):
            if pid is not None:
                with contextlib.suppress(psutil.Error):
                    psutil.Process(pid).kill()
        child.wait(timeout=30)


def test_the_detector_still_ignores_the_resource_tracker(existing_children: set[int]) -> None:
    """The one exclusion that is right, kept honest (`ai/TESTING.md` §13).

    Widening the detector to "every descendant" reintroduces the failure the old filter was
    written to avoid: `multiprocessing`'s resource tracker is a child of this process for the
    whole session, and counting it as a leak made a cancellation test fail in isolation and pass
    in a full run. It must be excluded **by being the resource tracker**, not by everything else
    being excluded too.
    """
    mp.get_context("spawn").Event()  # starts the tracker if nothing else has
    trackers = [
        process
        for process in psutil.Process(os.getpid()).children(recursive=True)
        if RESOURCE_TRACKER_MARKER in " ".join(process.cmdline())
    ]
    if not trackers:  # pragma: no cover - it exists on both supported platforms
        pytest.skip("no resource tracker is running, so there is nothing to exclude")

    reported = {process.pid for process in worker_processes(set())}

    assert not {tracker.pid for tracker in trackers} & reported, (
        "the resource tracker was reported as a leaked process"
    )


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
    """One integration test against the concrete persistence stack (`T-013` scope, `ARC-005`).

    Everything else here uses the fake, which proves the manager needs nothing but the protocol.
    This proves the protocol is one SQLite actually satisfies — that the two are the same shape
    is otherwise an assumption on both sides.

    **`JobRepository` alone no longer satisfies it**, and that is the point of `ARC-005`: its
    `update` is synchronous and blocked the GUI thread for a measured 5.017 s under a held writer
    lock (`T016-R3`). The manager is given `PersistentJobStore`, which serialises every write
    through the one writer thread and answers reads from a write-through view. The assertions
    below read through the *repository*, not the store, so they see what actually reached disk
    rather than what the view remembers.
    """
    from tracks_and_trails.persistence import db
    from tracks_and_trails.persistence.repositories import JobRepository
    from tracks_and_trails.persistence.store import PersistentJobStore
    from tracks_and_trails.persistence.writer import QueueWriter

    path = tmp_path / "library.sqlite3"
    url = media_url(total_bytes=64 * 1024)
    with db.open_database(path) as connection:
        real = JobRepository(connection)
        real.add(make_job("job-real", url, tmp_path))
        writer = QueueWriter(lambda: db.connect(path))
        store = PersistentJobStore(connection, writer)
        download = DownloadManager(store)
        try:
            download.start("job-real")
            assert spin(lambda: download.is_idle, timeout=120)
            # The final transition is announced from the write's callback, so idleness alone does
            # not mean it is on disk yet. Reading the repository is what proves it landed.
            assert spin(
                lambda: (
                    (job := real.get("job-real")) is not None and job.status is JobStatus.COMPLETED
                ),
                timeout=30,
            )
        finally:
            download.shutdown()
            writer.close()
            assert spin(lambda: not writer.is_running, timeout=30), "the writer thread never quit"

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
    record_property: Callable[[str, object], None],
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
    # Recorded, not just compared (`T019-R4`). The criterion asks for timings that can be seen
    # trending; a number that only ever becomes pass or fail cannot show the margin shrinking.
    # `record_property` puts it in the junit XML CI already uploads as evidence.
    record_property("cancel_seconds", round(elapsed, 3))
    record_property("cancel_budget_seconds", CANCEL_BUDGET_SECONDS)
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
    # **And nothing finished** (`T019-R4`). Asserting only that a `.part` exists would pass if a
    # completed file sat beside it, and a cancel that leaves a finished download is a cancel the
    # user cannot distinguish from a success.
    finished = [
        path
        for path in tmp_path.iterdir()
        if path.is_file() and path.suffix != ".part" and not path.name.startswith(".")
    ]
    assert not finished, (
        f"cancelling produced a completed file: {[p.name for p in finished]}. The partial must "
        "stay partial; a rename here is indistinguishable from a finished download."
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


# --- the process tree (T-019) ---------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="process groups are the POSIX mechanism")
def test_a_real_worker_leads_its_own_process_group(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    media_url: Callable[..., str],
    spin: Callable[..., bool],
    existing_children: set[int],
) -> None:
    """The containment the tree-killing depends on, asserted on a **production** worker.

    Everything else in this section uses a stand-in worker that spawns a grandchild, and a
    stand-in can only prove what it was written to do. This asserts the property on the real
    entry point: after `worker.spawn_session` runs `contain_this_process()`, the worker's process
    group id *is* its own pid — which is what makes `killpg(pid, …)` address the worker and its
    descendants without any risk of addressing ours.

    The Windows half of the same guarantee is a Job object, which has no equivalent external
    observation; the behaviour it delivers is covered by the three tests below, which run on both
    platforms.
    """
    url = media_url(total_bytes=512 * 1024 * 1024, chunk_delay=0.01)
    repository.add(make_job("job-1", url, tmp_path))
    download = manager()
    recorder = Recorder(download, repository)

    download.start("job-1")
    assert spin(lambda: bool(recorder.progress), timeout=60), "the download never started"
    workers = worker_processes(existing_children)
    assert workers, "there was no worker process to inspect"
    # Asked through `group_of`, which is the function the manager actually uses, and which is
    # typed on both platforms — reading `os.getpgid` here made `mypy --platform win32` fail over
    # `tests/`, a check CI runs and a `mypy --platform win32 src` locally does not.
    groups = {process.pid: process_tree.group_of(process.pid) for process in workers}

    download.cancel("job-1")
    assert spin(lambda: download.is_idle, timeout=CANCEL_BUDGET_SECONDS + 10.0)

    for pid, group in groups.items():
        assert group == pid, (
            f"worker {pid} reported group {group}, not its own pid. Either it never called "
            "setsid(), or it shares this process's group — which `group_of` reports as None, "
            "because signalling it would kill the test runner instead of the worker's children."
        )


def test_cancelling_a_download_kills_what_the_worker_spawned(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    existing_children: set[int],
    record_property: Callable[[str, object], None],
) -> None:
    """`T-019`'s defect, from the user's side: cancel must stop the merge, not just the worker.

    Before this, `cancel()` signalled the worker and nothing else. yt-dlp spawns `ffmpeg` as a
    child of the worker, and on POSIX killing a parent does not touch its children — so a merge
    cancelled mid-flight kept writing to the user's disk, reparented to `init`, with nothing left
    in the application that could stop it. `REQ-015` says cancel terminates the underlying work.

    The grandchild here ignores `SIGTERM`, so passing means the escalation reached the group with
    `SIGKILL` rather than being flattered by a descendant that would have exited anyway.
    """
    repository.add(make_job("job-1", "https://example.invalid/clip", tmp_path))
    download = manager(entry_point=child_with_a_grandchild_of_its_own)
    recorder = Recorder(download, repository)

    download.start("job-1")
    assert spin(lambda: bool(recorder.progress), timeout=30), "the worker never reported progress"
    running = worker_processes(existing_children)
    assert len(running) >= 2, f"expected a worker and a grandchild, saw {running}"
    # Captured while the tree is intact: see `still_running`. Watching the descendant walk empty
    # would pass the moment the *worker* died, whether or not the grandchild went with it.
    tree = [process.pid for process in running]

    started = time.monotonic()
    download.cancel("job-1")
    stopped = spin(lambda: not still_running(tree), timeout=CANCEL_BUDGET_SECONDS + 3.0)
    elapsed = time.monotonic() - started

    assert stopped, f"pids {still_running(tree)} outlived the cancellation"
    record_property("tree_cleanup_seconds", round(elapsed, 3))
    assert elapsed < CANCEL_BUDGET_SECONDS + 1.0, (
        f"tree cleanup took {elapsed:.2f}s; REQ-015's budget is {CANCEL_BUDGET_SECONDS}s and the "
        "descendant reaping must fit inside it rather than extend it"
    )
    assert spin(lambda: download.is_idle, timeout=10)


@pytest.mark.skipif(sys.platform == "win32", reason="the cooperative signal is POSIX-only")
def test_a_descendant_is_asked_to_stop_before_it_is_killed(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    existing_children: set[int],
) -> None:
    """Cancellation reaches the descendants **at the cooperative deadline**, not just at the end.

    Without this, the escalation's group signalling has no evidence of its own: a grandchild that
    is never signalled still dies moments later, when the session is released and the group is
    reaped with `SIGKILL`. A mutation removing the escalation step passed the whole suite. That
    is the shape `ai/TESTING.md` §13 is about — a guard that looks like it works because
    something else quietly does its job.

    The difference the user gets is the one `REQ-015` cares about: `ffmpeg` asked to stop can
    close its output and leave a partial file in a known state; `ffmpeg` killed cannot. So the
    grandchild here handles `SIGTERM`, and the marker it writes is proof it was *asked* rather
    than merely stopped.
    """
    repository.add(make_job("job-1", "https://example.invalid/clip", tmp_path))
    download = manager(entry_point=child_with_a_polite_grandchild)
    recorder = Recorder(download, repository)
    marker = tmp_path / "the-grandchild-was-asked"

    download.start("job-1")
    assert spin(lambda: bool(recorder.progress), timeout=30), "the worker never reported progress"
    running = worker_processes(existing_children)
    assert len(running) >= 2, "no grandchild to signal"
    tree = [process.pid for process in running]

    download.cancel("job-1")
    assert spin(lambda: download.is_idle, timeout=CANCEL_BUDGET_SECONDS + 10.0)

    assert not still_running(tree), f"pids {still_running(tree)} outlived the cancellation"
    assert marker.exists(), (
        "the grandchild was killed without being asked to stop first. Cancellation signals the "
        "worker's group at the cooperative deadline; if it does not, a descendant only dies when "
        "the session is released, with no chance to close what it was writing."
    )


def test_a_worker_killed_from_outside_does_not_leave_its_grandchild_behind(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    existing_children: set[int],
) -> None:
    """The path no cancellation covers: the worker dies and nobody asked it to.

    A crash, an OOM kill, or a stray `kill -9` leaves the descendants with no parent and no
    cancellation in flight — the manager never runs its escalation, because there is nothing left
    to escalate against. So the reaping happens on the way to releasing the session instead,
    before the process is joined and its pid becomes reusable.
    """
    repository.add(make_job("job-1", "https://example.invalid/clip", tmp_path))
    download = manager(entry_point=child_with_a_grandchild_of_its_own)
    recorder = Recorder(download, repository)

    download.start("job-1")
    assert spin(lambda: bool(recorder.progress), timeout=30), "the worker never reported progress"
    running = worker_processes(existing_children)
    assert len(running) >= 2, f"expected a worker and a grandchild, saw {running}"
    tree = [process.pid for process in running]

    # The worker is the one this process actually started; the rest of the tree hangs off it.
    worker = min(
        (process for process in running if process.ppid() == os.getpid()), key=lambda p: p.pid
    )
    grandchildren = [pid for pid in tree if pid != worker.pid]
    assert grandchildren, "the stand-in worker never got a child of its own"
    worker.kill()

    assert spin(lambda: download.is_idle, timeout=30), "the manager never finished the session"
    # Bounded rather than immediate: the reaping is a signal, and a signal is delivered when the
    # kernel gets to it. Asserting on the instant the manager goes idle races that delivery.
    spin(lambda: not still_running(grandchildren), timeout=10.0)
    survivors = still_running(grandchildren)
    assert not survivors, (
        f"pids {survivors} outlived the worker that spawned them. A killed worker's descendants "
        "are reaped when the session is released — and they are no longer *descendants* of this "
        "process by then, which is why this asks by pid (see `still_running`)."
    )
    assert repository.jobs["job-1"].status is JobStatus.FAILED


def test_shutdown_leaves_no_descendant_either(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    existing_children: set[int],
) -> None:
    """The third path: the application exits while a worker holds a child of its own."""
    repository.add(make_job("job-1", "https://example.invalid/clip", tmp_path))
    download = manager(entry_point=child_with_a_grandchild_of_its_own)
    recorder = Recorder(download, repository)

    download.start("job-1")
    assert spin(lambda: bool(recorder.progress), timeout=30), "the worker never reported progress"
    running = worker_processes(existing_children)
    assert len(running) >= 2
    tree = [process.pid for process in running]

    download.shutdown()

    assert spin(lambda: download.is_idle, timeout=CANCEL_BUDGET_SECONDS + 10.0)
    assert spin(lambda: not still_running(tree), timeout=10.0), (
        f"pids {still_running(tree)} outlived the application that started them"
    )


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


def test_killing_the_parent_takes_the_grandchild_too(tmp_path: Path) -> None:
    """The watchdog's other half (`T-019`): exiting is not the same as taking your children.

    `test_killing_the_parent_does_not_leave_the_child_running` proves the worker dies when the
    application is `SIGKILL`ed. It cannot prove anything about `ffmpeg`, because a plain HTTP
    download never spawns one — so the guard exited the worker and left its descendants running,
    reparented to `init`, and every test agreed that was fine.

    The stand-in worker holds a real child that ignores `SIGTERM`, so the watchdog has to kill
    the *group* rather than politely ask or merely exit. Killing the group takes the worker with
    it, which is why the exit code stops being observable on this path and is documented as such.
    """
    driver = (
        "import time\n"
        "from PySide6.QtCore import QCoreApplication\n"
        "from tracks_and_trails.downloader.manager import DownloadManager\n"
        "from tests.integration.test_manager import (\n"
        "    FakeRepository, make_job, child_with_a_grandchild_of_its_own,\n"
        ")\n"
        "app = QCoreApplication([])\n"
        "repository = FakeRepository()\n"
        f"repository.add(make_job('job-1', 'https://example.invalid/clip', {str(tmp_path)!r}))\n"
        "manager = DownloadManager(repository, entry_point=child_with_a_grandchild_of_its_own)\n"
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
        descendants: list[psutil.Process] = []
        while time.monotonic() < deadline and len(descendants) < 2:
            descendants = psutil.Process(parent.pid).children(recursive=True)
            time.sleep(0.05)
        assert len(descendants) >= 2, f"expected a worker and its child, saw {descendants}"

        psutil.Process(parent.pid).kill()
        _, alive = psutil.wait_procs(descendants, timeout=30)
    finally:
        parent.kill()
        parent.wait(timeout=30)

    assert not alive, (
        f"{alive} outlived the application. The worker's watchdog must kill its process group, "
        "not merely exit: the descendant it spawned has no other parent left to stop it."
    )


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


#: The two statuses `ARC-004` makes entry points, **transcribed** from `ARCHITECTURE.md` §5's
#: table rather than read from `manager._ENTRY_STATUS` (`T016-R7`). Deriving them from the
#: production mapping would make the refusal test agree with whatever that mapping said,
#: including a wrong one — `ai/TESTING.md` §13.
ENTRY_POINT_STATUSES: Final = (JobStatus.QUEUED, JobStatus.READY)

#: Everything else, as the *complement* over the whole enum rather than a hand-picked sample.
#: The previous list named four of the seven and its docstring claimed "every status that is not
#: an entry point"; `PROBING`, `COMPLETED` and `CANCELLED` went untested. A complement cannot
#: silently omit a status, and a status added to `JobStatus` joins this set the day it appears.
NON_ENTRY_STATUSES: Final = tuple(
    status for status in JobStatus if status not in ENTRY_POINT_STATUSES
)


def test_the_entry_point_statuses_are_the_ones_the_manager_implements() -> None:
    """The transcription and the production mapping must agree — asserted once, here.

    This is the one place the two sides are compared. Every other test below reads only the
    transcription, so a wrong `_ENTRY_STATUS` fails *this* test rather than quietly redefining
    what the others are checking.
    """
    from tracks_and_trails.downloader.manager import _ENTRY_STATUS

    assert tuple(_ENTRY_STATUS) == ENTRY_POINT_STATUSES
    assert set(NON_ENTRY_STATUSES) | set(ENTRY_POINT_STATUSES) == set(JobStatus)
    assert not set(NON_ENTRY_STATUSES) & set(ENTRY_POINT_STATUSES)


@pytest.mark.parametrize("status", NON_ENTRY_STATUSES)
def test_a_job_outside_the_two_entry_points_cannot_be_started(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    status: JobStatus,
) -> None:
    """`ARC-004` gives a start two entry points, not "anything the pipeline can reach".

    **This test used to assert that only a `QUEUED` job could start**, which was right until
    `T-051` ruled on the probe-then-download flow. `READY` is now the second entry point and has
    its own tests below; the rest are still refused explicitly rather than by a crash.
    """
    job = make_job("job-1", "https://example.invalid/x", tmp_path)
    repository.add(replace(job, status=status))
    download = manager(entry_point=child_downloading_forever)

    with pytest.raises(ValueError, match="a session starts from"):
        download.start("job-1")

    assert repository.jobs["job-1"].status is status, "a refused start still moved the job"


def test_no_companion_signal_arrives_before_its_transition_is_durable(
    tmp_path: Path, app: QCoreApplication
) -> None:
    """`T-013`'s acceptance criterion, restored under asynchronous persistence (`T016-R3`).

    Every signal that accompanies a state change waits for that change to be on disk. The first
    `ARC-005` implementation gated only `job_changed`, so `job_succeeded` arrived while the row
    still said `RUNNING` and a startup failure announced itself before `FAILED` was durable.

    A worker that reports nothing gives a real `job_failed` to hold, and the store completes
    writes only when told — against a fast writer both orders look identical.
    """

    class HeldStore:
        """Accepts writes and completes them only when released."""

        def __init__(self) -> None:
            self.jobs: dict[str, Job] = {}
            self.pending: list[tuple[Job, Callable[[str | None], None]]] = []

        def get(self, job_id: str) -> Job | None:
            return self.jobs.get(job_id)

        def update(self, job: Job, done: Callable[[str | None], None]) -> None:
            self.pending.append((job, done))

        def release(self) -> None:
            pending, self.pending = self.pending, []
            for job, done in pending:
                self.jobs[job.id] = job
                done(None)

    store = HeldStore()
    store.jobs["job-1"] = make_job("job-1", "https://example.invalid/x", tmp_path)
    download = DownloadManager(store, entry_point=child_reporting_nothing)
    failures: list[JobStatus | None] = []
    download.job_failed.connect(
        lambda *_: failures.append(store.jobs["job-1"].status if "job-1" in store.jobs else None)
    )

    try:
        download.start("job-1")
        # A reserved start is work in flight and says so (`T016-R3`). This assertion previously
        # read `== ()`, which encoded the defect: the reservation was invisible to every query,
        # so shutdown skipped it and `idle` could go out while a worker was still about to be
        # built. That no worker exists yet is gated by
        # `test_no_worker_exists_while_the_row_still_says_queued`.
        assert download.active_job_ids() == ("job-1",)
        assert not download.is_idle, "idle while a start is reserved would let composition quit"
        store.release()
        app.processEvents()
        assert store.jobs["job-1"].status is JobStatus.PROBING
        assert download.active_job_ids() == ("job-1",)

        # The worker exits having said nothing, so the session ends as WORKER_CRASH. Its write is
        # held, so `job_failed` must not have arrived yet.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not store.pending:
            app.processEvents()
            time.sleep(0.005)
        assert store.pending, "the session never produced a terminal transition"
        assert failures == [], "job_failed arrived before the failure was durable"

        store.release()
        app.processEvents()
        assert failures, "job_failed never arrived once the failure was stored"
        assert failures[0] is JobStatus.FAILED, (
            f"job_failed observed the job as {failures[0]}, not the status it announces"
        )
    finally:
        download.shutdown()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not download.is_idle:
            store.release()
            app.processEvents()
            time.sleep(0.005)


def test_a_second_session_is_refused_while_the_first_is_still_being_stored(
    tmp_path: Path, app: QCoreApplication
) -> None:
    """The pool of one covers a start whose transition has not landed yet (`T016-R3`).

    Without that, the pool would be "however many `start()` calls fit between a write and its
    completion" — a gap `ARC-005` created by deferring session construction.
    """

    class HeldStore:
        def __init__(self) -> None:
            self.jobs: dict[str, Job] = {}
            self.pending: list[tuple[Job, Callable[[str | None], None]]] = []

        def get(self, job_id: str) -> Job | None:
            return self.jobs.get(job_id)

        def update(self, job: Job, done: Callable[[str | None], None]) -> None:
            self.pending.append((job, done))

        def release(self) -> None:
            pending, self.pending = self.pending, []
            for job, done in pending:
                self.jobs[job.id] = job
                done(None)

    store = HeldStore()
    store.jobs["job-1"] = make_job("job-1", "https://example.invalid/x", tmp_path)
    store.jobs["job-2"] = make_job("job-2", "https://example.invalid/y", tmp_path)
    download = DownloadManager(store, entry_point=child_downloading_forever)

    try:
        download.start("job-1")
        assert download.active_job_ids() == ("job-1",), "the reservation is what refuses the next"
        assert not download.is_idle

        with pytest.raises(RuntimeError, match="already running"):
            download.start("job-2")
    finally:
        download.shutdown()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not download.is_idle:
            store.release()
            app.processEvents()
            time.sleep(0.005)


def test_a_transition_that_cannot_be_stored_is_reported_and_not_announced(
    tmp_path: Path, app: QCoreApplication
) -> None:
    """`ARC-005`: persist, **then** signal — so a write that failed announces nothing.

    `T016-R3` found the synchronous version raising an `OperationalError` that reached no user at
    all. The replacement must do the opposite of both halves: no `job_changed` for a state that
    was never stored, and a `persistence_failed` that says so.

    Not a job failure, deliberately: the download may be running perfectly while the queue's
    record of it falls behind, and recovery re-queues an interrupted job at the next startup.
    """

    class RefusingStore:
        """Accepts the read contract, refuses every write."""

        def __init__(self) -> None:
            self.jobs: dict[str, Job] = {}

        def get(self, job_id: str) -> Job | None:
            return self.jobs.get(job_id)

        def update(self, job: Job, done: Callable[[str | None], None]) -> None:
            self.jobs[job.id] = job  # read-your-writes still holds
            done("OperationalError: database is locked")

    store = RefusingStore()
    store.jobs["job-1"] = make_job("job-1", "https://example.invalid/x", tmp_path)
    download = DownloadManager(store, entry_point=child_downloading_forever)
    announced: list[tuple[str, str]] = []
    reported: list[tuple[str, str]] = []
    download.job_changed.connect(lambda job_id, status: announced.append((job_id, status)))
    download.persistence_failed.connect(lambda job_id, why: reported.append((job_id, why)))

    try:
        download.start("job-1")
        app.processEvents()

        assert announced == [], f"a state that was never stored was announced: {announced}"
        assert [job_id for job_id, _ in reported] == ["job-1"]
        assert "locked" in reported[0][1]
        # And the success-side effect did not run: a start whose transition was never stored must
        # not produce a worker (`T016-R3`).
        assert download.active_job_ids() == (), "a session was built on a write that failed"
    finally:
        download.shutdown()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not download.is_idle:
            app.processEvents()
            time.sleep(0.005)


def test_a_ready_job_starts_a_download_at_running(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`ARC-004`'s second entry point: `READY → RUNNING`, never back through `PROBING`.

    The whole persisted sequence is asserted rather than the final state. A start that re-entered
    `PROBING` would still end at `RUNNING` once the worker reported progress, so reading only the
    last status would miss exactly the thing the decision refused.
    """
    job = make_job("job-1", "https://example.invalid/x", tmp_path)
    repository.add(replace(job, status=JobStatus.READY))
    download = manager(entry_point=child_downloading_forever)

    download.start("job-1", SessionKind.DOWNLOAD)

    assert spin(lambda: repository.jobs["job-1"].status is JobStatus.RUNNING)
    assert repository.statuses("job-1") == [JobStatus.RUNNING]
    assert JobStatus.PROBING not in repository.statuses("job-1")


def test_a_probe_session_is_refused_for_a_ready_job(
    tmp_path: Path, repository: FakeRepository, manager: Callable[..., DownloadManager]
) -> None:
    """`READY → PROBING` does not exist, and a probe has no other status it could claim.

    Without this, the `READY` entry point would quietly have let probe sessions in: they would
    move the job to `RUNNING`, which says a download holds a job that is not downloading.
    """
    job = make_job("job-1", "https://example.invalid/x", tmp_path)
    repository.add(replace(job, status=JobStatus.READY))
    download = manager(entry_point=child_downloading_forever)

    with pytest.raises(ValueError, match="probe session starts from queued only"):
        download.start("job-1", SessionKind.PROBE)

    assert repository.jobs["job-1"].status is JobStatus.READY


def test_starting_from_ready_keeps_the_time_the_job_actually_began(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """A download from `READY` continues one attempt rather than beginning a new one.

    Overwriting `started_at` there would report a job as having begun when the user pressed
    *download* rather than when they queued it. A start from `QUEUED` does stamp it — including a
    retry, which re-enters `QUEUED` — and the test below is the other half of that pair.
    """
    began = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    job = make_job("job-1", "https://example.invalid/x", tmp_path)
    repository.add(replace(job, status=JobStatus.READY, started_at=began))
    download = manager(entry_point=child_downloading_forever)

    download.start("job-1", SessionKind.DOWNLOAD)

    assert spin(lambda: repository.jobs["job-1"].status is JobStatus.RUNNING)
    assert repository.jobs["job-1"].started_at == began


def test_starting_from_queued_stamps_this_attempt(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """The other half: a job entering `PROBING` records when this attempt began."""
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(entry_point=child_downloading_forever)

    download.start("job-1", SessionKind.DOWNLOAD)

    assert spin(lambda: repository.jobs["job-1"].status is JobStatus.PROBING)
    assert repository.jobs["job-1"].started_at is not None


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

    # **`start()` no longer raises for a spawn failure** (`ARC-005`, `T016-R3`). The session is
    # built from the completion callback of the job's own transition write, so by the time
    # construction fails there is nobody left to raise to. The failure is reported exactly as it
    # was before — durably stored, then announced — and every assertion below is unchanged; only
    # the delivery mechanism moved from an exception to the signals this manager already had.
    download.start("job-1")

    assert spin(lambda: download.is_idle, timeout=30), "the pump was left blocked on Queue.get()"
    assert any("could not be started" in reason for _, reason in recorder.violations)
    assert repository.jobs["job-1"].status is JobStatus.FAILED


# --- the startup transaction (T013-R3) -------------------------------------------------------


class UnwritableQueue:
    """A real queue that has stopped accepting writes.

    The state a queue is in when the thing that broke the session also broke it: a closed pipe,
    an exhausted descriptor table. Everything except `put` is the real object's.
    """

    def __init__(self, real: Any) -> None:
        self._real = real

    def put(self, item: Any) -> None:
        raise RuntimeError("the queue can no longer be written to")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


class BrokenContext:
    """A multiprocessing context whose resources cannot be created.

    Stands in for resource exhaustion — too many file descriptors, a process limit — which is
    real, reachable, and cannot be produced on demand any other way. It replaces the manager's
    own context rather than the process boundary: what is being tested is the parent's failure
    handling before any child exists.
    """

    def __init__(self, fail_on: str, *, queue_writes_fail: bool = False) -> None:
        self._fail_on = fail_on
        self._queue_writes_fail = queue_writes_fail
        self._real = mp.get_context("spawn")

    def Queue(self) -> Any:  # noqa: N802 - matching multiprocessing's own name
        if self._fail_on == "queue":
            raise OSError(24, "Too many open files")
        queue = self._real.Queue()
        return UnwritableQueue(queue) if self._queue_writes_fail else queue

    def Event(self) -> Any:  # noqa: N802 - matching multiprocessing's own name
        if self._fail_on == "event":
            raise OSError(24, "Too many open files")
        return self._real.Event()

    def Process(self, *args: Any, **kwargs: Any) -> Any:  # noqa: N802 - as above
        if self._fail_on == "process":
            raise OSError(11, "Resource temporarily unavailable")
        process = self._real.Process(*args, **kwargs)
        return UnstartableProcess(process) if self._fail_on == "process_start" else process


class UnstartableProcess:
    """A process that fails at `start()` rather than at construction.

    The distinction matters to the cleanup path: by `start()` the pump is already running and
    already blocked on the queue, so the failure has something to clean up. A failure during
    construction has not built anything yet, and takes a much shorter route out.
    """

    def __init__(self, real: Any) -> None:
        self._real = real

    def start(self) -> None:
        raise OSError(11, "Resource temporarily unavailable")

    def is_alive(self) -> bool:
        return False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


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

    # **`start()` no longer raises for a spawn failure** (`ARC-005`, `T016-R3`). The session is
    # built from the completion callback of the job's own transition write, so by the time
    # construction fails there is nobody left to raise to. The failure is reported exactly as it
    # was before — durably stored, then announced — and every assertion below is unchanged; only
    # the delivery mechanism moved from an exception to the signals this manager already had.
    download.start("job-1")

    assert spin(lambda: download.is_idle, timeout=30), "a session survived a failed start"
    stored = repository.jobs["job-1"]
    assert stored.status is JobStatus.FAILED, (
        f"{fail_on} construction failed and left the job {stored.status.value}; nothing is "
        "running, so the queue is describing work that does not exist"
    )
    assert stored.error_kind is ErrorKind.WORKER_CRASH
    # **The original failure, not the cleanup's** (`T013-R5`, `T-052`). This assertion used to
    # end in `or True` and could not fail. Removing that showed the production behaviour was
    # right all along and the *assertion* was wrong: it looked for the parametrised component
    # name, which the message never claimed to carry. What the message must carry — and does —
    # is the `OSError` that actually stopped the start, rather than whatever the unwind hit
    # afterwards while tidying up.
    assert stored.error_message, "a failed start stored no diagnostic at all"
    # The *words* of the original error, not its type name: `BrokenContext` raises `OSError` for
    # two cases and `BlockingIOError` — a subclass — for the third, so the class name is not the
    # invariant. What the user needs is what actually went wrong.
    assert any(
        phrase in stored.error_message.lower()
        for phrase in ("too many open files", "resource temporarily")
    ), (
        f"the stored diagnostic does not carry the failure that caused the abort, only that "
        f"something failed: {stored.error_message!r}"
    )
    assert recorder.failed, "REQ-018: the failure was never announced"
    assert recorder.stored_when_told[-1] is JobStatus.FAILED, (
        "the failure was signalled before it was persisted"
    )


def test_a_failure_while_cleaning_up_cannot_hide_the_failure_that_caused_it(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`T013-R3`, second pass: the cleanup path is itself a failure path.

    Whatever broke the session is quite capable of having broken the queue too, so the sentinel
    write during cleanup can fail. When it did, its exception replaced the original spawn error
    and the durable failure was never written — the job stayed `PROBING` with nothing running,
    which is the very state the finding exists to prevent.

    The order that survives this: **record the failure first, clean up second.** Nothing done
    for tidiness may pre-empt the fact that the job failed.
    """
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(reap_seconds=0.2)
    recorder = Recorder(download, repository)
    download._context = BrokenContext("process_start", queue_writes_fail=True)  # type: ignore[assignment]

    # **`start()` no longer raises for a spawn failure** (`ARC-005`, `T016-R3`). The session is
    # built from the completion callback of the job's own transition write, so by the time
    # construction fails there is nobody left to raise to. The failure is reported exactly as it
    # was before — durably stored, then announced — and every assertion below is unchanged; only
    # the delivery mechanism moved from an exception to the signals this manager already had.
    download.start("job-1")

    # The cause is read from what was *stored* rather than from a raised exception, for the same
    # reason: there is no longer one to inspect. It is the stronger reading anyway — the stored
    # diagnostic is what a user and a later session actually see.
    assert "no longer be written" not in (repository.jobs["job-1"].error_message or ""), (
        "the cleanup failure replaced the spawn failure, so the record names the wrong cause"
    )
    stored = repository.jobs["job-1"]
    assert stored.status is JobStatus.FAILED, (
        f"the job is {stored.status.value} after a start that failed and cleaned up badly; "
        "nothing is running, so the queue is describing work that does not exist"
    )
    assert stored.error_kind is ErrorKind.WORKER_CRASH
    assert recorder.stored_when_told[-1] is JobStatus.FAILED, (
        "the failure was announced before it was persisted"
    )
    assert download.is_idle, (
        "a half-built session was left to be cleaned up later. Nothing was running: the pump "
        "starts after the process, so a spawn failure has no thread to unwind"
    )


class WatchingQueue:
    """A queue that records what the repository held at the moment it was written to.

    The only way to observe *ordering* rather than outcome. Both the persistence and the
    cleanup end in the same state, so a test that checks the end state passes whichever came
    first — which is how the ordering guard survived its mutation.
    """

    def __init__(self, real: Any, repository: FakeRepository, job_id: str) -> None:
        self._real = real
        self._repository = repository
        self._job_id = job_id
        self.status_when_written: list[JobStatus | None] = []

    def put(self, item: Any) -> None:
        job = self._repository.get(self._job_id)
        self.status_when_written.append(job.status if job is not None else None)
        raise RuntimeError("the queue can no longer be written to")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


def test_the_failure_is_recorded_before_anything_is_cleaned_up(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`T013-R3`, pinned at the ordering rather than at the outcome.

    The assertion is not that the job ends up failed; it is that the job was **already** failed
    when cleanup was attempted. Written after the end-state version survived a mutation that put
    cleanup first.
    """
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(reap_seconds=0.2)
    download.start("job-1")
    session = download._sessions["job-1"]
    real_queue = session.queue
    watching = WatchingQueue(real_queue, repository, "job-1")
    session.queue = watching

    download._abort_start("job-1", session, watching, OSError(11, "spawn refused"))
    recorded = list(watching.status_when_written)

    # Restore so the real thread can end on a real sentinel and the fixture can tear down.
    session.queue = real_queue
    real_queue.put(WorkerFinished(job_id="job-1", exit_code=1))

    assert recorded == [JobStatus.FAILED], (
        f"cleanup ran while the job was {recorded}; a cleanup failure at that point would have "
        "replaced the real cause and left the job in flight"
    )
    assert spin(lambda: download.is_idle, timeout=30)


def test_a_failure_signal_never_arrives_before_the_failure_is_stored(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`T013-R3`, third pass: `protocol_violation` was emitted before the `FAILED` write.

    An observer that reacted to it read `PROBING` — a state the database was about to leave and
    that nothing was any longer working on. The rule is the same one `_save_and_announce` keeps
    for every other transition, applied to the two signals a failed start emits.
    """
    from tracks_and_trails.downloader import manager as manager_module

    class UnstartablePump(ResultPump):
        def start(self, priority: Any = None) -> None:
            raise OSError(11, "cannot create a thread")

    monkeypatch.setattr(manager_module, "ResultPump", UnstartablePump)
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(entry_point=child_downloading_forever, reap_seconds=0.2)
    seen: list[JobStatus | None] = []
    download.protocol_violation.connect(
        lambda job_id, _reason: seen.append(
            repository.jobs[job_id].status if job_id in repository.jobs else None
        )
    )

    # **`start()` no longer raises for a spawn failure** (`ARC-005`, `T016-R3`). The session is
    # built from the completion callback of the job's own transition write, so by the time
    # construction fails there is nobody left to raise to. The failure is reported exactly as it
    # was before — durably stored, then announced — and every assertion below is unchanged; only
    # the delivery mechanism moved from an exception to the signals this manager already had.
    download.start("job-1")

    assert seen == [JobStatus.FAILED], f"a violation was announced while the job read {seen}"
    assert spin(lambda: download.is_idle, timeout=30)


def test_a_pump_that_cannot_start_does_not_leave_its_worker_running(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    existing_children: set[int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`T013-R3`, third pass and the other half: the worker was already running.

    Starting the process before the pump removed one failure and created its mirror. When the
    pump then failed to start, the unwind looked for a *running pump*, found none, closed the
    queue and dropped the session — leaving a live worker that nobody was reading and nothing
    would ever stop. It downloads to the user's disk under a job the queue calls failed.

    The two starts are now recorded separately, so the unwind stops what was actually started.
    """
    from tracks_and_trails.downloader import manager as manager_module

    class UnstartablePump(ResultPump):
        def start(self, priority: Any = None) -> None:
            raise OSError(11, "cannot create a thread")

    monkeypatch.setattr(manager_module, "ResultPump", UnstartablePump)
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(entry_point=child_downloading_forever, reap_seconds=0.2)

    # **`start()` no longer raises for a spawn failure** (`ARC-005`, `T016-R3`). The session is
    # built from the completion callback of the job's own transition write, so by the time
    # construction fails there is nobody left to raise to. The failure is reported exactly as it
    # was before — durably stored, then announced — and every assertion below is unchanged; only
    # the delivery mechanism moved from an exception to the signals this manager already had.
    download.start("job-1")

    assert spin(lambda: not worker_processes(existing_children), timeout=30), (
        "the worker was left running after its reader failed to start"
    )
    assert repository.jobs["job-1"].status is JobStatus.FAILED
    assert download.is_idle


def test_abandoning_a_pump_resolves_its_job_first(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`T013-R4`, pinned at `_abandon` itself.

    The end-to-end version passes even when `_abandon` resolves nothing, because a killed
    worker's dying queue eventually ends the stream by another route and *that* resolves the
    job. Driving `_abandon` directly removes the second route, so the assertion is about this
    method's own obligation: nothing may announce completion while a job is still in flight.
    """
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(entry_point=child_downloading_forever, reap_seconds=0.2)
    download.start("job-1")
    session = download._sessions["job-1"]
    before: JobStatus = repository.jobs["job-1"].status
    assert before is JobStatus.PROBING, "the precondition this test rests on has changed"

    real_pump, real_queue = session.pump, session.queue
    session.pump = StubbornPump(real_pump)  # type: ignore[assignment]

    download._abandon(session)
    # Annotated so mypy widens it back: narrowing from the precondition above would otherwise
    # make the assertion below statically false, and everything after it unreachable.
    status_after: JobStatus = repository.jobs["job-1"].status
    idle_after = download.is_idle

    # Restore before asserting, so a failure cannot leave a wedged thread behind it.
    session.pump = real_pump
    real_queue.put(WorkerFinished(job_id="job-1", exit_code=0))

    assert status_after is not JobStatus.PROBING, "the pump was abandoned with its job in flight"
    assert idle_after is False, "the session was released before its thread finished"
    assert spin(lambda: download.is_idle, timeout=30)


class StubbornPump:
    """A pump thread that does not stop when it is told to.

    `stop()` is a request, and a thread inside a slow read may take a poll or several to honour
    it — or, if something has gone badly wrong, never. This is that thread, made deterministic:
    it accepts the stop and keeps reporting itself unfinished.
    """

    def __init__(self, real: Any) -> None:
        self._real = real
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True

    def isFinished(self) -> bool:  # noqa: N802 - Qt's own name
        return False

    def isRunning(self) -> bool:  # noqa: N802 - Qt's own name
        return True

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


def test_a_pump_that_will_not_stop_keeps_the_manager_from_claiming_it_is_idle(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    existing_children: set[int],
) -> None:
    """`T013-R4`: a correction regression from the event-driven shutdown.

    Removing the blocking waits was right; dropping the session the moment a stop was *issued*
    was not. A stop is asynchronous, so the next tick could find no sessions and announce `idle`
    while the thread was still alive and the job still in flight — which is precisely what the
    shutdown criterion says must never be true. (`T019-R5` changed the mechanism from
    `QThread.terminate()` to a cooperative `stop()`; the asymmetry it exercises is unchanged, and
    it is the reason the mechanism could be swapped without touching this test's substance.)

    Ownership has to last until the thread actually reports itself finished, and the job has to
    be durably resolved before anything announces completion.
    """
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(entry_point=child_downloading_forever, reap_seconds=0.2)
    recorder = Recorder(download, repository)
    announced: list[bool] = []
    download.idle.connect(lambda: announced.append(True))

    download.start("job-1")
    assert spin(lambda: bool(recorder.progress), timeout=60)

    session = download._sessions["job-1"]
    real_pump, real_queue = session.pump, session.queue
    # Both halves are needed to make the situation real. Taking the queue's writes away is what
    # keeps the *actual* thread blocked — otherwise the closing sentinel reaches it, it finishes
    # normally, and the stubborn facade is never consulted.
    session.queue = UnwritableQueue(real_queue)
    session.pump = StubbornPump(real_pump)  # type: ignore[assignment]

    download.shutdown(timeout=0.0)
    spin(lambda: False, timeout=2.0)  # let several ticks pass

    try:
        assert not announced, "idle was announced while the pump thread was still running"
        assert not download.is_idle, "the session was dropped before its thread finished"
        assert repository.jobs["job-1"].status is not JobStatus.PROBING, (
            "the job was abandoned in flight: nothing is running it and nothing says so"
        )
    finally:
        # Give the real thread its queue and its sentinel back, so it ends the ordinary way and
        # the fixture can tear down. A test that leaves a wedged QThread aborts the interpreter.
        session.queue = real_queue
        session.pump = real_pump
        real_queue.put(WorkerFinished(job_id="job-1", exit_code=0))

    assert spin(lambda: download.is_idle, timeout=30)
    assert not worker_processes(existing_children)


def test_a_stopped_pump_actually_stops_rather_than_being_killed(
    tmp_path: Path, qapp: QCoreApplication
) -> None:
    """`T019-R5`: the pump ends by **returning**, and does it within a bounded time.

    The distinction this asserts is the one that cost a working test gate. `QThread.terminate()`
    ended a thread by killing it wherever it stood — including inside CPython's internals, holding
    a lock nothing would release — and a bare `pytest` then wedged about one run in five, parked
    on that lock inside `Thread.start()`. Twenty-two consecutive clean runs with `terminate()`
    removed identified it.

    So the assertion is not "stop was called". It is that the thread reports itself finished, and
    that it emitted its own end-of-session — which only a thread that reached its `finally` can do.
    """
    queue: Any = mp.get_context("spawn").Queue()
    pump = ResultPump(queue, "job-1", SessionKind.DOWNLOAD)
    ended: list[str] = []
    pump.session_ended.connect(ended.append)
    violations: list[tuple[str, str]] = []
    pump.violation.connect(lambda job, why: violations.append((job, why)))

    try:
        pump.start()
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not pump.isRunning():
            qapp.processEvents()
            time.sleep(0.01)
        assert pump.isRunning(), "the pump never started, so stopping it proves nothing"

        started = time.monotonic()
        pump.stop()
        deadline = started + 5.0
        while time.monotonic() < deadline and not pump.isFinished():
            qapp.processEvents()
            time.sleep(0.01)
        elapsed = time.monotonic() - started
    finally:
        pump.stop()
        pump.wait(5000)
        queue.close()

    assert pump.isFinished(), (
        f"the pump was still running {elapsed:.2f}s after stop(). Nothing else may kill it — a "
        "thread that does not return here is one that would have had to be terminated."
    )
    assert elapsed < 1.0, (
        f"the pump took {elapsed:.2f}s to notice, against a {POLL_SECONDS}s poll; a stop that is "
        "only honoured slowly turns every shutdown into a wait"
    )
    qapp.processEvents()
    assert ended == ["job-1"], (
        "the pump did not emit session_ended, so it never reached its finally block — which is "
        "what a killed thread looks like and what this test exists to rule out"
    )
    assert any("stopped this reader" in why for _, why in violations), (
        "a stream ended by the parent must be reported as a violation, not passed off as a "
        "clean shutdown"
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


# --- the third correction: an ordered per-job lifecycle (`T016-R1`, `T016-R3`) ------------------


class HeldStore:
    """A `JobStore` whose writes complete only when the test says so.

    The shape every claim below needs: `ARC-005` made writes asynchronous, and the defects the
    third review found all live in the window between asking for a write and it landing. A store
    that completes immediately closes that window and proves nothing about what happens inside it.

    `failing` decides how the *next* release completes, which is how a failed transition is
    reproduced without breaking SQLite. Read when the write completes rather than when it was
    queued, because several transitions of one interaction are queued from inside each other's
    callbacks and a test cannot get between them.
    """

    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.pending: list[tuple[Job, Callable[[str | None], None]]] = []
        self.written: list[tuple[str, JobStatus]] = []
        self.failing = False

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def update(self, job: Job, done: Callable[[str | None], None]) -> None:
        self.pending.append((job, done))

    def release(self) -> None:
        """Complete every queued write, oldest first, as the writer thread would."""
        pending, self.pending = self.pending, []
        for job, done in pending:
            if self.failing:
                done("the writer refused this transition")
                continue
            self.jobs[job.id] = job
            self.written.append((job.id, job.status))
            done(None)

    def statuses(self, job_id: str) -> list[JobStatus]:
        return [status for stored_id, status in self.written if stored_id == job_id]


def test_cancelling_a_reserved_start_stops_the_worker_from_ever_being_built(
    tmp_path: Path, app: QCoreApplication
) -> None:
    """`T016-R1`: a start that is cancelled before it exists must not become a process.

    The reviewer's probe, restated. Cancelling while `start()`'s transition is still on the
    writer thread used to queue `CANCELLED` behind `PROBING` — correct on its own — while the
    `PROBING` write's success callback still spawned unconditionally. The durable record ended
    `CANCELLED` and a worker ran for it: work for the URL the user had just taken away, which is
    the Critical consequence in its strongest form.
    """
    store = HeldStore()
    store.jobs["job-1"] = make_job("job-1", "https://example.invalid/x", tmp_path)
    download = DownloadManager(store, entry_point=child_downloading_forever)
    rejections: list[tuple[str, str]] = []
    download.start_rejected.connect(lambda job_id, why: rejections.append((job_id, why)))

    try:
        download.start("job-1")
        download.cancel("job-1")
        store.release()
        app.processEvents()
        store.release()
        app.processEvents()

        assert store.statuses("job-1") == [JobStatus.PROBING, JobStatus.CANCELLED]
        assert store.jobs["job-1"].status is JobStatus.CANCELLED
        assert not download._sessions, (
            "a worker was built for a job whose cancellation is already durable"
        )
        assert download.is_idle, "the reservation outlived the start it was holding"
        assert rejections and rejections[0][0] == "job-1", (
            "the caller was never told its start had been abandoned"
        )
    finally:
        download.shutdown()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not download.is_idle:
            store.release()
            app.processEvents()
            time.sleep(0.005)


def test_shutdown_while_a_start_is_reserved_neither_spawns_nor_claims_to_be_idle(
    tmp_path: Path, app: QCoreApplication
) -> None:
    """`T016-R3`: `idle` is composition's permission to quit, so a reservation has to hold it.

    Two halves, and the first version had neither: `shutdown()` cancelled `_sessions` only, and
    `is_idle` read `_sessions` only. So shutdown could announce `idle` with a start still on the
    writer thread, and the callback that arrived afterwards would build a worker into an
    application that had already been told it was safe to quit.
    """
    store = HeldStore()
    store.jobs["job-1"] = make_job("job-1", "https://example.invalid/x", tmp_path)
    download = DownloadManager(store, entry_point=child_downloading_forever)
    idles: list[None] = []
    download.idle.connect(lambda: idles.append(None))

    try:
        download.start("job-1")
        download.shutdown()
        app.processEvents()
        # Read into a local first. Asserting on the property directly narrows it to `False` for
        # the rest of the function, and mypy then calls the later `assert download.is_idle`
        # unreachable — a test whose second half is not analysed at all is the `T-016` lesson in
        # miniature (`ai/TESTING.md` §12).
        idle_while_reserved = download.is_idle
        assert not idle_while_reserved, "idle was claimed while a start was still reserved"
        assert idles == [], "idle was announced while a start was still reserved"

        store.release()
        app.processEvents()
        assert not download._sessions, "shutdown spawned a worker from a reserved start"

        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not download.is_idle:
            store.release()
            app.processEvents()
            time.sleep(0.005)
        assert download.is_idle
        assert not download._sessions
        # `idle` arrives when the reservation is released, which is before the cancellation it
        # queued has been written — so the writes are drained explicitly rather than inferred
        # from idleness.
        while store.pending:
            store.release()
            app.processEvents()
        # Shutdown has to *cancel* the reservation, not merely decline to spawn it. A job left
        # durably `PROBING` by a shutdown is a job in flight with nothing flying it, which
        # recovery would have to clean up at the next start (`T-014`).
        assert store.statuses("job-1") == [JobStatus.PROBING, JobStatus.CANCELLED], (
            f"the reserved start was never withdrawn: {store.statuses('job-1')}"
        )
    finally:
        download.shutdown()


def test_a_second_progress_message_waits_for_the_first_ones_write(
    tmp_path: Path, app: QCoreApplication
) -> None:
    """`T016-R3`: effects for one job are ordered behind that job's outstanding writes.

    The measured defect: the first `DOWNLOADING_VIDEO` message queues `PROBING → RUNNING`, the
    second reads the queued value back, concludes there is nothing to persist, and emits at once.
    An observer that reads the repository when it is told about progress therefore saw `PROBING`
    while being told the job was downloading — the ordering `T-013` was approved for, lost to the
    write-through view being mistaken for completion.

    Driven through the manager's own slot rather than a worker, because the claim is about the
    order of two messages and a real worker cannot be asked to send them one event apart.
    """
    store = HeldStore()
    store.jobs["job-1"] = make_job("job-1", "https://example.invalid/x", tmp_path)
    download = DownloadManager(store, entry_point=child_downloading_forever)
    seen: list[JobStatus | None] = []
    download.progress.connect(
        lambda _: seen.append(store.jobs["job-1"].status if "job-1" in store.jobs else None)
    )

    try:
        download.start("job-1")
        store.release()
        app.processEvents()
        assert download._sessions, "the session never started"
        assert store.jobs["job-1"].status is JobStatus.PROBING

        def message(stage: Stage) -> Progress:
            return Progress(job_id="job-1", stage=stage, downloaded_bytes=1, total_bytes=2)

        # Three messages, covering both routes out of `_on_progress`. The first moves the job and
        # therefore writes; the second finds it already moving there; the third carries a stage
        # that maps to no status at all and never writes. All three must stay behind the first
        # one's transition, because all three tell an observer the job is downloading.
        download._on_progress(message(Stage.DOWNLOADING_VIDEO))
        download._on_progress(message(Stage.DOWNLOADING_VIDEO))
        download._on_progress(message(Stage.PROBING))
        app.processEvents()
        assert seen == [], "progress was forwarded while its own transition was still in flight"

        store.release()
        app.processEvents()
        assert seen == [JobStatus.RUNNING] * 3, (
            "a progress message reached an observer while the row still said probing"
        )
    finally:
        download.shutdown()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not download.is_idle:
            store.release()
            app.processEvents()
            time.sleep(0.005)


def test_a_startup_failure_that_cannot_be_stored_announces_nothing_but_still_cleans_up(
    tmp_path: Path, app: QCoreApplication
) -> None:
    """`T016-R3`: mandatory cleanup and durable-state announcements are different things.

    The previous correction passed one function as both `then` and `otherwise`, so a *failed*
    `FAILED` write still emitted `job_failed` and `protocol_violation` — and every observer that
    read the row back found `PROBING`, which is the guarantee the change existed to establish.
    What must still happen either way is the teardown: a failure that could not be recorded must
    not also leak a process.
    """

    def refuses_to_spawn(*_: Any, **__: Any) -> None:  # pragma: no cover - never runs
        raise AssertionError("the entry point should never be reached")

    class ExplodingProcess:
        """A process whose `start()` fails, which is what `_abort_start` exists for."""

        exitcode: int | None = None
        pid: int | None = None

        def is_alive(self) -> bool:
            return False

        def start(self) -> None:
            raise OSError("no process for you")

        def join(self, timeout: float | None = None) -> None:
            return None

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

    store = HeldStore()
    store.jobs["job-1"] = make_job("job-1", "https://example.invalid/x", tmp_path)
    download = DownloadManager(store, entry_point=refuses_to_spawn)
    download._context = type(
        "Context",
        (),
        {
            "Queue": staticmethod(mp.get_context("spawn").Queue),
            "Event": staticmethod(mp.get_context("spawn").Event),
            "Process": staticmethod(lambda **_: ExplodingProcess()),
        },
    )()
    failures: list[tuple[str, ErrorKind, str]] = []
    violations: list[tuple[str, str]] = []
    persistence: list[tuple[str, str]] = []
    download.job_failed.connect(lambda *args: failures.append(args))
    download.protocol_violation.connect(lambda *args: violations.append(args))
    download.persistence_failed.connect(lambda *args: persistence.append(args))

    try:
        download.start("job-1")
        store.release()
        app.processEvents()
        # The spawn has failed by now and `_abort_start` has queued the `FAILED` transition.
        store.failing = True
        assert store.pending, "no failure transition was queued"
        store.release()
        app.processEvents()

        assert store.jobs["job-1"].status is JobStatus.PROBING, (
            "the failure write was supposed to fail; this proves nothing otherwise"
        )
        assert failures == [], "job_failed was announced while the row still said probing"
        assert violations == [], "protocol_violation was announced before the failure was durable"
        assert persistence and persistence[0][0] == "job-1", (
            "a write that failed has to be reported as one"
        )
        assert not download._sessions, "the session survived a failure it could not record"
    finally:
        download.shutdown()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not download.is_idle:
            store.release()
            app.processEvents()
            time.sleep(0.005)
