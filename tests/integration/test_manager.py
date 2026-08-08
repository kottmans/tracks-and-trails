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
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import pairwise
from pathlib import Path
from typing import Any, Final

import psutil
import pytest
from PySide6.QtCore import QCoreApplication

from tests.qt_lifecycle import drain
from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus, can_transition
from tracks_and_trails.core.models import DownloadRequest, Job
from tracks_and_trails.downloader import manager as manager_module
from tracks_and_trails.downloader import process_tree, worker
from tracks_and_trails.downloader.manager import DownloadManager, _PendingStart
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
        #: Ids removed, in order (`T-080`). A list rather than a count, so a test can assert
        #: *which* job left the queue rather than only that something did.
        self.removals: list[str] = []
        #: Orders asked for, and ids cleared (`T-081`), for the same reason.
        self.reorderings: list[tuple[str, ...]] = []
        self.cleared: list[str] = []

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

    def requeue_at_end(self, job: Job, done: Callable[[str | None], None]) -> None:
        """`JobStore.requeue_at_end` — a write that allocates a tail position (`T-080`).

        **The position is allocated here, as the real one allocates it inside the transaction.**
        A fake that stored the job with the position it arrived carrying would let a manual retry
        keep its old place and still satisfy the ordering assertion, which is the one claim this
        method exists to support.
        """
        placed = max((stored.queue_position or 0) for stored in self.jobs.values()) + 1
        self.update(replace(job, queue_position=placed), done)

    def remove(self, job_id: str, done: Callable[[str | None], None]) -> None:
        """`JobStore.remove` — delete the row and nothing else (`UX-001`, `T-080`).

        **No filesystem call, deliberately.** The fake can only be as honest as the real one about
        this, and what makes the promise checkable is that a test asserts on the output directory
        rather than on this method.
        """
        self.jobs.pop(job_id, None)
        self.removals.append(job_id)
        done(None)

    def reorder(self, job_ids: Sequence[str], done: Callable[[str | None], None]) -> None:
        """`JobStore.reorder` — redeal the positions those jobs hold (`REQ-016`, `T-081`).

        **Redealt, not renumbered**, exactly as the real one does: a fake that renumbered from zero
        would move jobs nobody touched and still satisfy a test where the reordered jobs are the
        whole queue.
        """
        positions = sorted(self.jobs[job_id].queue_position or 0 for job_id in job_ids)
        for position, job_id in zip(positions, job_ids, strict=True):
            self.jobs[job_id] = replace(self.jobs[job_id], queue_position=position)
        self.reorderings.append(tuple(job_ids))
        done(None)

    def clear_completed(self, done: Callable[[str | None], None]) -> None:
        """`JobStore.clear_completed` — drop terminal rows, keep `FAILED` (`REQ-016`, `T-081`)."""
        for job_id, job in list(self.jobs.items()):
            if job.status in (JobStatus.COMPLETED, JobStatus.CANCELLED):
                del self.jobs[job_id]
                self.cleared.append(job_id)
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
        #: The same, for `job_succeeded`, and it needs its own list (`T-175`).
        #:
        #: `T050-R2`'s rule covers both signals, and until 2026-08-06 only one of them was
        #: watched. A mutant that emitted `job_succeeded` **before** the completion write settled
        #: left every `job_changed` ordering intact and the whole suite green — the success
        #: announcement is a separate emission on a separate path, and the change-signal capture
        #: cannot see past it. Found while collapsing the completion seam, which `T-175` allows
        #: only if this ordering is covered by something that fails when it inverts.
        self.stored_when_succeeded: list[JobStatus | None] = []
        self._repository = repository

        manager.job_changed.connect(self._on_change)
        manager.progress.connect(self._on_progress)
        manager.media_probed.connect(lambda job_id, media: self.probed.append((job_id, media)))
        manager.resolution_reported.connect(self.resolutions.append)
        manager.job_succeeded.connect(self._on_succeeded)
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

    def _on_succeeded(self, job_id: str, path: str) -> None:
        stored = self._repository.get(job_id)
        self.stored_when_succeeded.append(stored.status if stored is not None else None)
        self.succeeded.append((job_id, path))

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

    def build(*, running: bool = True, **overrides: Any) -> DownloadManager:
        """A manager, **started by default** — which is not the application's default (`UX-006`).

        `T-181` made the gate stopped at construction, so a manager nobody starts runs nothing.
        Almost every test in this file predates that and is about something else entirely: the
        pool, the pump, cancellation, reordering, the process tree. Making each of them press
        Start would be several hundred edits that say nothing about what they assert.

        So the fixture presses it, and the tests that are *about* the gate pass `running=False`
        to get the real construction-time state. The default is a test-harness convenience and is
        deliberately the opposite of the product's, which is why
        `test_a_manager_starts_stopped_and_runs_nothing_until_it_is_started` builds one directly
        rather than through here — a fixture that hid the shipped default could not assert it.
        """
        manager = DownloadManager(repository, **overrides)
        manager.start_queue()
        built.append(manager)
        if running:
            manager.start_queue()
        return manager

    yield build

    # Shutdown is a lifecycle, not a call (`T013-R2`), so teardown has to drive the event loop
    # until it finishes. A test that returned here with a pump still running would have Qt
    # destroy a live QThread — which aborts the interpreter, taking the whole run with it.
    for manager in built:
        manager.shutdown()
    # **`drain` waits for the timer as well as the work** (`T-128`). This polled `is_idle` alone,
    # which answers a question about the *queue* — no sessions, no reservations, nothing waiting —
    # and goes true up to one poll interval before the tick that stops the manager's own timer. So
    # this loop returned, `built` died, and a QObject with a registered timer became garbage. Two
    # full-suite runs in 39 then died in `activateTimers()` on freed memory.
    drain(app, built)


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
            except BrokenPipeError, ConnectionResetError, ConnectionAbortedError:
                # The expected end of a cancelled download: the worker went away mid-stream.
                #
                # **`ConnectionAbortedError` is the Windows spelling of exactly that** (`T-121`),
                # and it was missing — so on Windows the abort escaped this handler entirely and
                # `socketserver` printed a traceback for a condition the line above already calls
                # expected. `WinError 10053`, seen in run `30853680183`.
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


def child_reporting_a_clean_success(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """The ordinary happy path, with nothing else in it.

    Every other success in this file carries a second fault for its test to catch. This one is
    deliberately unremarkable, because the thing being asserted about it is a *timing* property
    of the parent and any extra message would give the assertion somewhere else to fail.
    """
    queue.put(Succeeded(job_id=job_id, output_path="/written/clip.mp4", total_bytes=10))
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


def child_probe_reporting_then_lingering(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """End a valid probe stream, then keep its process alive long enough to expose handoff races."""
    if kind is SessionKind.PROBE:
        from tracks_and_trails.core.models import MediaInfo

        queue.put(Probed(job_id=job_id, media=MediaInfo(url=request.url, title="Resolved")))
        queue.put(WorkerFinished(job_id=job_id, exit_code=0))
        queue.close()
        queue.join_thread()
        time.sleep(2)
        return
    queue.put(Progress(job_id=job_id, stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=1))
    while True:
        time.sleep(0.05)


def child_probe_failing_then_lingering(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Fail a probe with a kind that is never retried, then keep the process alive.

    The lingering half is the point: a probe whose *stream* has ended still owns a session until
    `_release` establishes that its process is gone, so this reproduces the window in which a
    staged job is both `FAILED` and still an occupant.
    """
    from tracks_and_trails.core.errors import ErrorKind
    from tracks_and_trails.downloader.protocol import Failed

    queue.put(Failed(job_id=job_id, kind=ErrorKind.UNSUPPORTED_URL, message="no extractor"))
    queue.put(WorkerFinished(job_id=job_id, exit_code=1))
    queue.close()
    queue.join_thread()
    time.sleep(3)


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
        #
        # **Depth below *this* process, not one hop below `child`** (`T-066`). This asserted
        # `ppid() == child.pid`, which is a stronger claim than the test needs and is true only
        # when `sys.executable` starts the interpreter directly. In a virtualenv on Windows it
        # does not: `.venv\Scripts\python.exe` is a launcher that *spawns* the real interpreter,
        # so `child.pid` is the launcher and the grandchild sits one level further down. The test
        # failed with "this test is not about a grandchild at all" while looking at a tree that
        # was, if anything, deeper than it expected.
        #
        # CI installs without a virtualenv while `docs/DEVELOPMENT.md` documents one, so this
        # held on every runner and failed for a developer following our own instructions.
        #
        # What the detector must actually do is reach a process that is **not a direct child of
        # the process doing the walking**, which is exactly `worker_processes(existing_children)`'s
        # subject. Two generations from here is that property, and it holds under both install
        # shapes rather than pinning the one CI happens to use.
        generations = _generations_between(os.getpid(), grandchild_pid)
        assert generations is not None and generations >= 2, (
            f"{grandchild_pid} is {generations} generation(s) below this test process, so it is "
            "not the second-level process this test is about"
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


def _generations_between(ancestor_pid: int, descendant_pid: int) -> int | None:
    """How many parent hops separate the two pids, or `None` if they are unrelated (`T-066`).

    Walks up rather than down: a descendant walk would have to enumerate every child at every
    level, and the question here is only about one process's ancestry.

    Bounded rather than trusting the walk to terminate. A pid whose parent chain is longer than
    this is not the shape any test here creates, and an unbounded loop over a process tree that
    is being torn down concurrently is a hang rather than a failure.
    """
    hops = 0
    process = psutil.Process(descendant_pid)
    while hops < 20:
        parent = process.parent()
        if parent is None:
            return None
        hops += 1
        if parent.pid == ancestor_pid:
            return hops
        process = parent
    return None


def test_the_detector_still_ignores_the_resource_tracker(existing_children: set[int]) -> None:
    """The one exclusion that is right, kept honest (`ai/TESTING.md` §13).

    Widening the detector to "every descendant" reintroduces the failure the old filter was
    written to avoid: `multiprocessing`'s resource tracker is a child of this process for the
    whole session, and counting it as a leak made a cancellation test fail in isolation and pass
    in a full run. It must be excluded **by being the resource tracker**, not by everything else
    being excluded too.
    """
    mp.get_context("spawn").Event()  # starts the tracker if nothing else has

    def is_tracker(process: psutil.Process) -> bool:
        """Whether `process` is the resource tracker, tolerating one that is no longer readable.

        **`cmdline()` raises on a zombie**, and a zombie is an ordinary transient state: a child
        that has exited and whose parent has not collected it yet. This preamble read every child
        unguarded, which was harmless while the suite spawned a worker at a time and became a
        reliable failure once `T-118` gave every pasted URL a probe. `worker_processes` — the
        helper this test is *about* — has skipped zombies since it was written; the gap was here,
        in the question this test asks before it starts.
        """
        try:
            return RESOURCE_TRACKER_MARKER in " ".join(process.cmdline())
        except psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied:
            return False

    trackers = [
        process
        for process in psutil.Process(os.getpid()).children(recursive=True)
        if is_tracker(process)
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


def test_a_success_is_announced_only_after_the_row_says_completed(
    tmp_path: Path,
    repository: FakeRepository,
    manager: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`T050-R2`, for `job_succeeded` rather than for `job_changed` (`T-175`).

    **This is the gap the seam cleanup found.** The vertical-slice test above checks that each
    *status change* was already durable when announced, and that assertion is real — but it says
    nothing about the success signal, which is a separate emission the manager makes from the
    completion write's own callback. Emitting it one line earlier, ahead of the write, left every
    `job_changed` ordering intact and the entire suite green. So the rule was stated in three
    docstrings and enforced nowhere for the signal the user's "it finished" actually rides on.

    Asserted at the moment of the signal, because that is the only moment it is observable:
    afterwards the row and the announcement agree no matter which came first. A crash in the gap
    is what the rule prevents — the UI saying a download finished while the queue still says it
    is running, and a restart disagreeing with what the user was told.

    Driven by a scripted child rather than a real download, so the coverage does not depend on
    binding a loopback server. The vertical slice keeps the same assertion against a real one.
    """
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    download = manager(entry_point=child_reporting_a_clean_success)
    recorder = Recorder(download, repository)

    download.start("job-1")
    assert spin(lambda: download.is_idle, timeout=30)

    assert recorder.succeeded == [("job-1", "/written/clip.mp4")], (
        f"the success was never announced: {recorder.violations}"
    )
    assert recorder.stored_when_succeeded == [JobStatus.COMPLETED], (
        "job_succeeded was emitted while the stored row said "
        f"{recorder.stored_when_succeeded}. A crash in that gap leaves the user told their "
        "download finished and the queue, on restart, saying it never did (T050-R2)."
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
        download.start_queue()
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
    # **The `.part` assertion that stood here is gone, and its signal is not lost** (`T046-R1`).
    # The download now happens in a staging directory that is discarded whatever the outcome, so a
    # cancelled job leaves nothing in the user's folder — including no partial. What that assertion
    # actually established, that the worker unwound *cooperatively* rather than being killed, is
    # carried by the message check immediately above: "parent process cancelled" is the worker's
    # own word and a forced stop cannot produce it.
    #
    # **The behaviour change is deliberate and stated.** Before this, cancelling left a `.part` in
    # the user's downloads folder with nothing specified about its lifetime. `REQ-017` (Phase 3,
    # `T-113`) is where resuming a partial download is decided, and it will have to say where
    # partials live; a randomly named per-run directory is not resumable across restarts either
    # way. Until then, cancel leaves the folder as it found it.
    assert not list(tmp_path.glob("*.part")), (
        f"a partial file was left in the user's folder: {list(tmp_path.glob('*.part'))}"
    )
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".tracks-and-trails-staging")], (
        "a staging directory outlived the cancelled download"
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

    # **The complete persisted sequence, not selected terminal states** (`T013-R5`, `T-052`).
    # Excluding `COMPLETED` and `READY` by name left `RUNNING` unexamined, so a receiver that
    # routed an illegal *progress* message before validating it wrote a state that never
    # legitimately existed and no assertion here noticed. A crash-recovery pass reads that state
    # and believes it (`T-014`), which is the cost.
    persisted = repository.statuses("job-1")
    legitimate = ([JobStatus.PROBING, JobStatus.FAILED], [JobStatus.RUNNING, JobStatus.FAILED])
    assert persisted in legitimate, (
        f"the job passed through states it never legitimately reached: "
        f"{[status.value for status in persisted]}"
    )
    assert repository.jobs["job-1"].status is JobStatus.FAILED
    assert repository.jobs["job-1"].error_kind is ErrorKind.WORKER_CRASH

    # **Every public route, not only the outcomes.** `succeeded` and `probed` were checked and
    # `progress` and `resolution_reported` were not, so a message the validator rejected could
    # still have reached a widget on its way to being discarded.
    assert not recorder.succeeded, "an illegal outcome was announced to the GUI"
    assert not recorder.probed, "an illegal outcome was announced to the GUI"
    assert not recorder.progress, (
        f"an illegal message was forwarded as progress before it was rejected: {recorder.progress}"
    )
    assert len(recorder.resolutions) <= 1, (
        f"a duplicate resolution report reached the GUI: {recorder.resolutions}"
    )


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
        # `UX-006`: a manager is constructed stopped, and this child exists to spawn a worker
        # and be killed. Without Start it waits forever and so does the parent.
        "manager.start_queue()\n"
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
        # `UX-006`, as above: nothing spawns until the queue is started.
        "manager.start_queue()\n"
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

        def requeue_at_end(self, job: Job, done: Callable[[str | None], None]) -> None:
            """Part of `JobStore` since `T-080`. Unused here; present so the fake satisfies it."""
            raise NotImplementedError

        def remove(self, job_id: str, done: Callable[[str | None], None]) -> None:
            """Part of `JobStore` since `T-080`. Unused here; present so the fake satisfies it."""
            raise NotImplementedError

        def reorder(self, job_ids: Sequence[str], done: Callable[[str | None], None]) -> None:
            """Part of `JobStore` since `T-081`. Unused here; present so the fake satisfies it."""
            raise NotImplementedError

        def clear_completed(self, done: Callable[[str | None], None]) -> None:
            """Part of `JobStore` since `T-081`. Unused here; present so the fake satisfies it."""
            raise NotImplementedError

    store = HeldStore()
    store.jobs["job-1"] = make_job("job-1", "https://example.invalid/x", tmp_path)
    download = DownloadManager(store, entry_point=child_reporting_nothing)
    download.start_queue()
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

        def requeue_at_end(self, job: Job, done: Callable[[str | None], None]) -> None:
            """Part of `JobStore` since `T-080`. Unused here; present so the fake satisfies it."""
            raise NotImplementedError

        def remove(self, job_id: str, done: Callable[[str | None], None]) -> None:
            """Part of `JobStore` since `T-080`. Unused here; present so the fake satisfies it."""
            raise NotImplementedError

        def reorder(self, job_ids: Sequence[str], done: Callable[[str | None], None]) -> None:
            """Part of `JobStore` since `T-081`. Unused here; present so the fake satisfies it."""
            raise NotImplementedError

        def clear_completed(self, done: Callable[[str | None], None]) -> None:
            """Part of `JobStore` since `T-081`. Unused here; present so the fake satisfies it."""
            raise NotImplementedError

    store = HeldStore()
    store.jobs["job-1"] = make_job("job-1", "https://example.invalid/x", tmp_path)
    store.jobs["job-2"] = make_job("job-2", "https://example.invalid/y", tmp_path)
    download = DownloadManager(store, entry_point=child_downloading_forever)
    download.start_queue()

    try:
        download.start("job-1")
        assert download.active_job_ids() == ("job-1",), "the reservation is what refuses the next"
        assert not download.is_idle

        with pytest.raises(RuntimeError, match="lane is full"):
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

        def requeue_at_end(self, job: Job, done: Callable[[str | None], None]) -> None:
            """Part of `JobStore` since `T-080`. Unused here; present so the fake satisfies it."""
            raise NotImplementedError

        def remove(self, job_id: str, done: Callable[[str | None], None]) -> None:
            """Part of `JobStore` since `T-080`. Unused here; present so the fake satisfies it."""
            raise NotImplementedError

        def reorder(self, job_ids: Sequence[str], done: Callable[[str | None], None]) -> None:
            """Part of `JobStore` since `T-081`. Unused here; present so the fake satisfies it."""
            raise NotImplementedError

        def clear_completed(self, done: Callable[[str | None], None]) -> None:
            """Part of `JobStore` since `T-081`. Unused here; present so the fake satisfies it."""
            raise NotImplementedError

    store = RefusingStore()
    store.jobs["job-1"] = make_job("job-1", "https://example.invalid/x", tmp_path)
    download = DownloadManager(store, entry_point=child_downloading_forever)
    download.start_queue()
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
    """A full pool refuses rather than quietly queueing.

    **The default limit is 1, so this is the same contract Phase 1 had** (`T-078`). What changed is
    why: the refusal is now "the download lane is full at 1" rather than "concurrency is Phase 2",
    because the bound is a configured limit rather than a fixed assumption. A manager built with a
    larger limit accepts more — `test_the_limit_is_respected_exactly` is where that is asserted.

    Refusing rather than queueing is the point here. `start()` is a direct request and its caller
    gets an answer; the waiting list is for work this manager has already accepted, which is
    `retry()`'s path and `_fill_free_slots`'.
    """
    repository.add(make_job("job-1", "https://example.invalid/x", tmp_path))
    repository.add(make_job("job-2", "https://example.invalid/y", tmp_path))
    download = manager(entry_point=child_downloading_forever)
    download.start("job-1")

    with pytest.raises(RuntimeError, match="lane is full"):
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
        #: Removals queued and not yet released (`T-080`). **A second list rather than a sentinel
        #: in `pending`**: every reader of `pending` unpacks a `Job`, and a `None` in there would
        #: turn a fake's bookkeeping into an `AttributeError` inside the code under test. Ordering
        #: between the two is preserved by `_order`, which is the property the chain relies on.
        self.removals: list[tuple[str, Callable[[str | None], None]]] = []
        #: The order writes and removals were asked for, so `release` can replay it exactly.
        self._order: list[str] = []
        self.written: list[tuple[str, JobStatus]] = []
        self.removed: list[str] = []
        self.failing = False

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def update(self, job: Job, done: Callable[[str | None], None]) -> None:
        self.pending.append((job, done))
        self._order.append("write")

    def requeue_at_end(self, job: Job, done: Callable[[str | None], None]) -> None:
        """`JobStore.requeue_at_end` — a write that allocates a tail position (`T-080`).

        **The position is allocated here, as the real one allocates it inside the transaction.**
        A fake that stored the job with the position it arrived carrying would let a manual retry
        keep its old place and still pass the ordering test, which is the one claim this method
        exists to support.
        """
        placed = max((stored.queue_position or 0) for stored in self.jobs.values()) + 1
        self.update(replace(job, queue_position=placed), done)

    def remove(self, job_id: str, done: Callable[[str | None], None]) -> None:
        """`JobStore.remove` — delete the row, touching nothing else (`UX-001`, `T-080`)."""
        self.removals.append((job_id, done))
        self._order.append("remove")

    def reorder(self, job_ids: Sequence[str], done: Callable[[str | None], None]) -> None:
        """`JobStore.reorder` — settles immediately; this store holds *job* writes, not orders."""
        positions = sorted(self.jobs[job_id].queue_position or 0 for job_id in job_ids)
        for position, job_id in zip(positions, job_ids, strict=True):
            self.jobs[job_id] = replace(self.jobs[job_id], queue_position=position)
        done(None)

    def clear_completed(self, done: Callable[[str | None], None]) -> None:
        """`JobStore.clear_completed` — settles immediately, for `reorder`'s reason."""
        for job_id, job in list(self.jobs.items()):
            if job.status in (JobStatus.COMPLETED, JobStatus.CANCELLED):
                del self.jobs[job_id]
        done(None)

    def release(self) -> None:
        """Complete every queued write and removal, **oldest first**, as the writer would.

        One interleaved replay rather than writes-then-removals: removal of a running job is a
        cancel's write followed by a delete, and a fake that always settled the delete last would
        hide an ordering the real single writer guarantees and the manager depends on.
        """
        order, self._order = self._order, []
        pending, self.pending = self.pending, []
        removals, self.removals = self.removals, []
        writes = iter(pending)
        deletes = iter(removals)
        for kind in order:
            if kind == "write":
                job, done = next(writes)
                if self.failing:
                    done("the writer refused this transition")
                    continue
                self.jobs[job.id] = job
                self.written.append((job.id, job.status))
                done(None)
            else:
                job_id, done = next(deletes)
                if self.failing:
                    done("the writer refused this removal")
                    continue
                self.jobs.pop(job_id, None)
                self.removed.append(job_id)
                done(None)

    def statuses(self, job_id: str) -> list[JobStatus]:
        return [status for stored_id, status in self.written if stored_id == job_id]


class OverlayingHeldStore(HeldStore):
    """`HeldStore`, but `get()` answers with the newest **queued** revision, as the real one does.

    `PersistentJobStore.get()` returns "the newest revision this process has queued, or what the
    database holds" — durable or not. `HeldStore` answers only from what has landed, which is
    simpler and cannot express `T075-R1`: that defect exists precisely because a reader can see a
    revision that has not landed and may never land.

    A fake that cannot represent the failure is a fake the test passes against for the wrong
    reason, so this one overlays the queue the way the store under test does.
    """

    def get(self, job_id: str) -> Job | None:
        for job, _ in reversed(self.pending):
            if job.id == job_id:
                return job
        return self.jobs.get(job_id)


def test_a_retarget_never_starts_against_a_revision_that_did_not_land(
    tmp_path: Path, app: QCoreApplication
) -> None:
    """`T075-R1`, Critical: the successor must not run on a request the database does not hold.

    `retarget` skips the write when the job already carries the request asked for — worth doing,
    since writing anyway adds a revision for no change. The first version decided that **before
    enqueuing anything**, by reading the store and comparing. But the store answers with the
    newest *queued* revision, so the comparison could match a write still in flight; and if that
    write then failed, `then` had already run and the download started against the request the
    database actually held. The dialog would have reported the user's choice as saved.

    Asserted as the invariant rather than as the mechanism: **whenever the successor runs, the
    durable request is the one that was asked for.** A test that checked "no shortcut was taken"
    would pass against any number of other wrong implementations.
    """
    store = OverlayingHeldStore()
    job = make_job("job-1", "https://example.invalid/x", tmp_path)
    store.jobs["job-1"] = job.with_status(JobStatus.PROBING).with_status(JobStatus.READY)
    manager = DownloadManager(store)
    manager.start_queue()

    wanted = replace(job.request, format_selector="bestaudio/best")
    seen_when_started: list[str] = []

    def record() -> None:
        stored = store.jobs["job-1"]
        seen_when_started.append(stored.request.format_selector)

    try:
        manager.retarget("job-1", wanted, then=record)
        # A second ask while the first is still on the writer thread. `get()` now answers with the
        # queued revision, which is what the old pre-check compared against.
        manager.retarget("job-1", wanted, then=record)
        assert seen_when_started == [], "a successor ran while nothing had been written at all"

        # The in-flight write fails, so the durable row still carries the original request.
        store.failing = True
        store.release()
        assert seen_when_started == [], (
            f"a successor ran after a failed write, with the database still holding "
            f"{store.jobs['job-1'].request.format_selector!r}"
        )

        store.failing = False
        for _ in range(4):
            store.release()

        assert seen_when_started, "the retarget never completed at all"
        assert set(seen_when_started) == {"bestaudio/best"}, (
            f"a successor ran while the database held {seen_when_started}; the request that runs "
            "must be the one that was stored"
        )
    finally:
        manager.shutdown()


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
    download.start_queue()
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
    download.start_queue()
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
    download.start_queue()
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
    download.start_queue()
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


from tracks_and_trails.persistence import db  # noqa: E402
from tracks_and_trails.persistence.repositories import (  # noqa: E402
    JobRepository,
)

# --- completion durability (`NFR-003`) ------------------------------------------------------


def _completion_probe(tmp_path: Path) -> Path:
    """Write a child that drives one real completion and hard-exits the way a power cut would.

    *(It took a `die_before_history` flag that replaced `repositories._write_history` with
    `os._exit`, so the process died **inside** a completion transaction between its two statements
    — the only injection point that could tell an atomic completion from a split one. A completion
    writes one statement since `REQ-020` was withdrawn, so there is no longer a between.)*
    """
    probe = tmp_path / "probe_after.py"
    probe.write_text(
        "\n".join(
            [
                "import os, sys",
                "from dataclasses import replace",
                "from datetime import UTC, datetime",
                "from PySide6.QtCore import QCoreApplication",
                "from tracks_and_trails.core.job_state import JobStatus",
                "from tracks_and_trails.core.models import DownloadRequest, Job",
                "from tracks_and_trails.persistence import db",
                "from tracks_and_trails.persistence.repositories import JobRepository",
                "from tracks_and_trails.persistence.store import PersistentJobStore",
                "from tracks_and_trails.persistence.writer import QueueWriter",
                "",
                "path = sys.argv[1]",
                "application = QCoreApplication([])",
                "connection = db.connect(path)",
                "request = DownloadRequest(",
                "    url='https://example.com/x',",
                "    output_directory=os.path.dirname(path),",
                "    format_selector='best',",
                "    output_template='%(title)s.%(ext)s',",
                ")",
                "queued = Job(id='j', url=request.url, request=request,",
                "             created_at=datetime.now(UTC))",
                "JobRepository(connection).add(queued)",
                "finished = queued",
                "for status in (JobStatus.PROBING, JobStatus.READY, JobStatus.RUNNING,",
                "               JobStatus.POST_PROCESSING, JobStatus.COMPLETED):",
                "    finished = finished.with_status(status)",
                "finished = replace(finished, finished_at=datetime.now(UTC))",
                "",
                "writer = QueueWriter(lambda: db.connect(path))",
                "store = PersistentJobStore(connection, writer)",
                "",
                "def settled(error):",
                "    # The statement has committed. Die the way a power cut would.",
                "    os._exit(0 if error is None else 3)",
                "",
                # `store.update`, not a `store.complete`: the completion seam was collapsed by
                # `T-175` once it wrote the same single row. What this probe is about -- a
                # process that stops existing the instant a completion settles -- is unchanged.
                "store.update(finished, settled)",
                "application.exec()",
            ]
        )
    )
    return probe


def _run_probe(probe: Path, database: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(probe), str(database)],
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        check=False,
    )


def test_a_hard_exit_after_a_completion_settles_keeps_the_job_row(tmp_path: Path) -> None:
    """A committed completion survives a process that stops existing (`NFR-003`).

    **Stated limit: this is a positive durability check, not an atomicity gate.** It exits from the
    settlement callback, so every statement has already run — which is why `T093-R1` rejected it as
    the gate for `T050-R1`. What it establishes is that once a completion has settled, WAL has it:
    no `atexit`, no flush and no Qt teardown are needed for the row to be there on restart.

    *(It asserted "both rows" and checked the ledger beside the job. `REQ-020` was withdrawn on
    2026-08-06 and a completion writes one row, so the atomicity this pair was written to protect
    has nothing left to be atomic with — `T050-R1`'s reasoning is preserved at `store.update`,
    which is where the completion path went when `T-175` collapsed it.)*
    """
    database = tmp_path / "library.sqlite3"
    probe = _completion_probe(tmp_path)
    result = _run_probe(probe, database)
    assert result.returncode == 0, f"the completion did not settle cleanly: {result.stderr}"

    with db.open_database(database) as connection:
        stored = JobRepository(connection).get("j")

    assert stored is not None
    assert stored.status is JobStatus.COMPLETED, "a settled completion lost its row to the exit"


# --- T-078: the pool is N, and N is respected exactly ---------------------------------------


def queued(repository: FakeRepository, *job_ids: str, directory: Path) -> None:
    """Put `job_ids` in the store in queue order, so the pool has something to schedule."""
    for position, job_id in enumerate(job_ids):
        job = make_job(job_id, "https://example.invalid/clip", directory)
        repository.add(replace(job, queue_position=position))


def test_the_limit_is_respected_exactly_at_saturation(
    tmp_path: Path, media_url: Callable[..., str], spin: Callable[..., bool]
) -> None:
    """`T-078`: **not "about N"** — counted at the moment the pool is full.

    Three real sessions against a slow local server, with a fourth `start()` attempted while all
    three are live. The assertion is on `active_job_ids()` at saturation rather than on how many
    ever ran, because a pool that admitted a fourth and then tidied up would pass a total count.
    """
    repository = FakeRepository()
    url = media_url(total_bytes=4 * 1024 * 1024, chunk_delay=0.02)
    for position, job_id in enumerate(("job-1", "job-2", "job-3", "job-4")):
        repository.add(replace(make_job(job_id, url, tmp_path), queue_position=position))

    download = DownloadManager(repository, concurrency=3)
    download.start_queue()
    try:
        for job_id in ("job-1", "job-2", "job-3"):
            download.start(job_id)
        assert spin(lambda: len(download.active_job_ids()) == 3, timeout=60)

        with pytest.raises(RuntimeError, match="the download lane is full at 3"):
            download.start("job-4")

        assert len(download.active_job_ids()) == 3, (
            "a fourth session was admitted past the limit, or the refusal left state behind"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_lowering_the_limit_drains_rather_than_killing(
    tmp_path: Path, media_url: Callable[..., str], spin: Callable[..., bool]
) -> None:
    """`T-078`, `UX-001`'s reasoning applied to the limit: in-flight work was asked for.

    Lowering to 1 with three running must leave **three running** and start nothing new. Asserted
    on the live session ids rather than on a status, because a killed session would also stop being
    active — the distinction is whether the processes are still there a moment later.
    """
    repository = FakeRepository()
    url = media_url(total_bytes=8 * 1024 * 1024, chunk_delay=0.05)
    for position, job_id in enumerate(("job-1", "job-2", "job-3")):
        repository.add(replace(make_job(job_id, url, tmp_path), queue_position=position))

    download = DownloadManager(repository, concurrency=3)
    download.start_queue()
    try:
        for job_id in ("job-1", "job-2", "job-3"):
            download.start(job_id)
        assert spin(lambda: len(download.active_job_ids()) == 3, timeout=60)

        download.set_concurrency(1)

        # Still three, and still three after the event loop has had a chance to act on it.
        assert len(download.active_job_ids()) == 3
        spin(lambda: False, timeout=0.5)
        assert len(download.active_job_ids()) == 3, (
            "lowering the limit stopped work already in flight; UX-001 chose draining precisely "
            "because a stopped download leaves a partial file nothing can resume in this phase"
        )
        assert download.concurrency == 1
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_raising_the_limit_starts_waiting_jobs_without_waiting_for_a_tick(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T-078`: *"without waiting for a tick that happens to fire"* — asserted literally.

    The manager's timer is what would eventually notice a free slot, and it fires every
    `poll_interval_ms`. This test **never spins the event loop**: it starts a job, queues two more
    behind the limit, raises the limit, and asserts they are active immediately. A `set_concurrency`
    that only marked the limit and left the filling to the tick would fail here and pass anything
    written with a `spin()` in it.

    A child that never finishes, so a started slot stays occupied — otherwise a process that exits
    immediately would free the slot it was meant to hold and the assertion would measure timing.
    """
    repository = FakeRepository()
    queued(repository, "job-1", "job-2", "job-3", directory=tmp_path)

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.start("job-1")
        download._start_when_free("job-2")
        download._start_when_free("job-3")

        # Occupancy is what the limit governs; the waiting pair is held but holds no slot.
        assert download._occupant_ids() == ("job-1",), "the limit of 1 did not hold"
        assert download._waiting == ["job-2", "job-3"]

        download.set_concurrency(3)

        assert len(download._occupant_ids()) == 3, (
            "raising the limit did not start the waiting jobs immediately; nothing here spins the "
            "event loop, so a tick-driven fill cannot have run"
        )
        assert download._waiting == []
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_waiting_jobs_start_in_queue_order_not_arrival_order(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T-078`: the scheduling order is stated, and it is `queue_position`.

    Queued deliberately out of order — `job-3` asks to wait first — so arrival order and queue order
    disagree. `queue_position` is allocated inside the insert transaction (`JobRepository.append`),
    which makes it the only ordering that survives a restart and the only one two callers cannot
    disagree about.
    """
    repository = FakeRepository()
    queued(repository, "job-1", "job-2", "job-3", directory=tmp_path)

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.start("job-1")
        download._start_when_free("job-3")
        download._start_when_free("job-2")
        assert download._waiting == ["job-3", "job-2"], "arrival order, before scheduling"

        # One more slot, so exactly one of the two waiting jobs starts. Which one is the contract.
        download.set_concurrency(2)

        assert "job-2" in download.active_job_ids(), (
            f"active {download.active_job_ids()}; job-3 arrived first but job-2 has the lower "
            "queue_position, and queue_position is the order this pool promises"
        )
        assert download._waiting == ["job-3"]
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_waiting_job_holds_idle_open_and_shutdown_drops_it(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T-078`: `is_idle` accounts for every slot, reservation **and** waiting job (`T036-R1`).

    Composition treats `idle` as permission to quit, so a job this manager has accepted and not yet
    started must hold the door — and `shutdown()` must then drop it, or the door never closes.
    """
    repository = FakeRepository()
    queued(repository, "job-1", "job-2", directory=tmp_path)

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.start("job-1")
        download._start_when_free("job-2")

        assert download._waiting == ["job-2"]
        assert not download.is_idle
    finally:
        download.shutdown()
        assert download._waiting == [], "shutdown left work that will never start"
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_job_waiting_with_nothing_running_still_holds_idle_open(tmp_path: Path) -> None:
    """The state the test above **cannot** reach, and the one `is_idle` is actually about.

    With a session running, `is_idle` is false whether or not it counts waiting jobs — so that test
    passes against a manager that ignores the waiting list entirely. Measured: removing
    `and not self._waiting` from `is_idle` left it green.

    The state that discriminates is *waiting with nothing running*, which occurs for an instant
    every time the last session is released before a slot is filled. It is reached here by putting a
    job on the list directly, because arranging that instant deterministically would make this a
    test about timing rather than about accounting.
    """
    repository = FakeRepository()
    queued(repository, "job-1", directory=tmp_path)
    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()

    assert download.is_idle, "nothing has been asked for yet"
    download._waiting.append("job-1")

    assert not download.is_idle, (
        "a job this manager has accepted but not started must hold idle open. Composition treats "
        "idle as permission to quit (T-036), so quitting here would abandon accepted work"
    )


def test_a_reservation_occupies_a_slot_at_a_limit_above_one(
    tmp_path: Path, qapp: QCoreApplication
) -> None:
    """`T016-R3` generalised: a start whose write has not landed still costs a slot.

    A reservation has no process yet, so a pool counting only running sessions would admit more
    starts in the window between a write and its callback. At a limit of 1 the existing
    `test_a_second_session_is_refused_while_the_first_is_still_being_stored` covers this; nothing
    covered it at N, and removing `len(self._reserved)` from the capacity check left every other
    pool test green.
    """
    store = HeldStore()
    for position, job_id in enumerate(("job-1", "job-2", "job-3")):
        job = make_job(job_id, "https://example.invalid/clip", tmp_path)
        store.jobs[job_id] = replace(job, queue_position=position)

    download = DownloadManager(store, concurrency=2, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.start("job-1")
        download.start("job-2")

        # Neither write has landed, so neither job has a process — but both hold a slot.
        assert download.active_job_ids() == ("job-1", "job-2")
        assert not download.is_idle

        with pytest.raises(RuntimeError, match="the download lane is full at 2"):
            download.start("job-3")
    finally:
        download.shutdown()
        store.release()
        qapp.processEvents()


def test_a_waiting_job_is_part_of_what_the_manager_reports_it_is_holding(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T078-R1`: the method said "every job this manager is holding" and omitted one.

    The expected value is the **pair**, so this cannot pass on the running job alone — which is
    exactly how the omission survived. An assertion of the shape `active_job_ids() != ()`, or one
    counting occupancy, is true whether or not the waiting list is included; only naming both ids
    distinguishes them.

    `_occupant_ids()` is asserted beside it to show the two answer different questions. One job
    holds the only slot; two jobs are held. Collapsing that distinction is what would make the
    refusal in `start()` name jobs that are themselves waiting for the slot being asked for.
    """
    repository = FakeRepository()
    queued(repository, "job-1", "job-2", directory=tmp_path)

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.start("job-1")
        download._start_when_free("job-2")

        assert download.active_job_ids() == ("job-1", "job-2"), (
            "a job accepted into the waiting list is work this manager is holding: nothing else "
            "will ever start it, and `is_idle` already refuses to go out while it is there"
        )
        assert download._occupant_ids() == ("job-1",), (
            "the waiting job holds no slot — the limit of 1 is the reason it is waiting at all"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_the_holding_report_names_a_job_once_when_two_collections_hold_it(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """Three collections now feed one answer, so the answer has to be a set (`T078-R1`).

    The overlap is not reachable through the ordinary path — `_start_when_free` discards the
    waiting entry before starting — so it is arranged directly here. That is the point: the
    ordering guarantee callers rely on should not depend on an invariant enforced somewhere else.
    """
    repository = FakeRepository()
    queued(repository, "job-1", directory=tmp_path)

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.start("job-1")
        download._waiting.append("job-1")

        assert download.active_job_ids() == ("job-1",), (
            "one job held in two collections is still one job; a caller diffing this report "
            "would otherwise see a phantom arrive"
        )
    finally:
        download._waiting.clear()
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_lowering_the_limit_holds_a_waiting_job_until_the_pool_drains(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """The half of lowering that `..._drains_rather_than_killing` structurally cannot see.

    That test has **nothing waiting**, so it proves only "does not kill". A scheduler that started
    waiting work while the live count was above the lowered limit passed it and all six other pool
    tests (`T078-R2`) — the limit was being written down and not enforced on the way down.

    So: three jobs saturate a limit of 3, a fourth is accepted behind them, and the limit drops to
    1. The three must survive *and* the fourth must stay put — three running is not below one. It
    becomes eligible only when the pool actually drains, which the cancels then make happen.
    """
    repository = FakeRepository()
    queued(repository, "job-1", "job-2", "job-3", "job-4", directory=tmp_path)

    download = DownloadManager(repository, concurrency=3, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        for job_id in ("job-1", "job-2", "job-3"):
            download.start(job_id)
        download._start_when_free("job-4")
        assert download._waiting == ["job-4"], "the fourth job was never accepted behind the limit"

        download.set_concurrency(1)

        # The tick is the other caller of `_fill_free_slots`, so let several fire before judging.
        spin(lambda: False, timeout=0.5)
        assert download._occupant_ids() == ("job-1", "job-2", "job-3"), (
            "lowering the limit stopped work already in flight; UX-001 chose draining because a "
            "stopped download leaves a partial file nothing can resume in this phase"
        )
        assert download._waiting == ["job-4"], (
            f"a waiting job was started while {len(download._occupant_ids())} were live and the "
            "limit was 1. The new limit governs what starts next, and filling a slot that does "
            "not exist is how a pool of N becomes a pool of N plus whatever was queued"
        )

        for job_id in ("job-1", "job-2", "job-3"):
            download.cancel(job_id)

        assert spin(lambda: download._occupant_ids() == ("job-4",), timeout=60), (
            "the waiting job never started once the pool drained below the new limit; occupants "
            f"{download._occupant_ids()}, waiting {download._waiting}"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


# --- T-083: bounded automatic retry, for network failures only -------------------------------


def job_row(repository: FakeRepository, job_id: str) -> Job:
    """`repository.get`, but typed as present.

    The retry tests read the row constantly and every one of them would otherwise carry an
    `is not None` that says nothing: a job vanishing from the store is a different failure, and
    it should be reported as itself rather than as an attribute error.
    """
    job = repository.get(job_id)
    assert job is not None, f"{job_id} is no longer in the store"
    return job


def child_failing_with_the_kind_its_job_id_names(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Fail with the `ErrorKind` named in the job id, e.g. `job-NETWORK`.

    The kind travels in the id because a spawned entry point takes no test-supplied arguments:
    `spawn` pickles the function and the manager chooses what it is called with. One child that
    reads its own id keeps every kind on the same code path, which is what makes "only `NETWORK`
    retries" a comparison rather than two different children.
    """
    from tracks_and_trails.core.errors import ErrorKind
    from tracks_and_trails.downloader.protocol import Failed

    named = ErrorKind[job_id.rsplit("-", 1)[1]]
    queue.put(Failed(job_id=job_id, kind=named, message=f"failed as {named.value}"))
    queue.put(WorkerFinished(job_id=job_id, exit_code=1))


def quick_backoff(monkeypatch: pytest.MonkeyPatch, seconds: float = 0.05) -> None:
    """Shorten every backoff so a test measures the *rule* rather than the wall clock.

    Patched on the module rather than passed in, because the values are read at scheduling time
    and `T-083` deliberately does not make them a constructor argument — they are policy awaiting
    a `DECISIONS.md` entry, not per-manager configuration.
    """
    monkeypatch.setattr(
        manager_module, "RETRY_BACKOFF_SECONDS", (seconds,) * manager_module.AUTOMATIC_RETRY_LIMIT
    )


@pytest.mark.parametrize(
    "kind_name",
    ["UNSUPPORTED_URL", "EXTRACTOR_ERROR", "AUTH_REQUIRED", "DRM_PROTECTED", "DISK"],
)
def test_only_a_network_failure_retries_itself(
    tmp_path: Path, spin: Callable[..., bool], monkeypatch: pytest.MonkeyPatch, kind_name: str
) -> None:
    """`T-083`'s first criterion, **by driving each other kind and observing none**.

    The narrowness is the whole requirement. An `UNSUPPORTED_URL` retried on a timer is a request
    the site refuses identically forever, and `DRM_PROTECTED` is a workaround this product exists
    to refuse (`SEC-001`, `REQ-EXCL-001`). `is_retryable` is a wider question — whether a *person*
    may retry — so deriving automatic retry from it would put `WORKER_CRASH` into a loop.
    """
    quick_backoff(monkeypatch)
    repository = FakeRepository()
    job_id = f"job-{kind_name}"
    repository.add(make_job(job_id, "https://example.invalid/clip", tmp_path))
    download = DownloadManager(repository, entry_point=child_failing_with_the_kind_its_job_id_names)
    download.start_queue()
    try:
        download.start(job_id)
        assert spin(lambda: job_row(repository, job_id).status is JobStatus.FAILED, timeout=60)

        # Long enough that a scheduled retry would have fired several times over.
        spin(lambda: False, timeout=1.0)

        job = job_row(repository, job_id)
        assert job.status is JobStatus.FAILED, (
            f"{kind_name} retried itself; only NETWORK may, and this one will fail identically"
        )
        assert job.attempts == 0, f"{kind_name} spent an automatic attempt"
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_network_failure_retries_itself_and_counts_the_attempt(
    tmp_path: Path, spin: Callable[..., bool], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other side of the comparison, and `REQ-018`'s "the attempt count is visible".

    `attempts` was a schema column nothing ever incremented — the dead counter `T079-R1` could
    not key an attempt boundary to. This is what brings it to life, so the assertion is on the
    **persisted** number rather than on a signal.
    """
    quick_backoff(monkeypatch)
    repository = FakeRepository()
    repository.add(make_job("job-NETWORK", "https://example.invalid/clip", tmp_path))
    download = DownloadManager(repository, entry_point=child_failing_with_the_kind_its_job_id_names)
    download.start_queue()
    try:
        download.start("job-NETWORK")
        assert spin(lambda: job_row(repository, "job-NETWORK").attempts >= 1, timeout=60), (
            "a network failure never retried itself"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def child_recording_kind_then_failing_network(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Record which session kind an automatic retry actually launches."""
    from tracks_and_trails.downloader.protocol import Failed

    with (Path(request.output_directory) / "session-kinds.txt").open(
        "a", encoding="utf-8"
    ) as stream:
        stream.write(f"{kind.value}\n")
    queue.put(Failed(job_id=job_id, kind=ErrorKind.NETWORK, message="temporary network failure"))
    queue.put(WorkerFinished(job_id=job_id, exit_code=1))


def test_an_automatic_retry_preserves_a_probe_as_a_probe(
    tmp_path: Path, spin: Callable[..., bool], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed add-dialog probe must not turn into an unattended download.

    The manager accepts both probe and download sessions, but the retry bookkeeping currently
    remembers only the job id.  Falling back to ``start(job_id)`` selects DOWNLOAD, which changes
    the user's requested operation at the retry boundary.
    """
    quick_backoff(monkeypatch)
    repository = FakeRepository()
    repository.add(make_job("job-NETWORK", "https://example.invalid/clip", tmp_path))
    download = DownloadManager(repository, entry_point=child_recording_kind_then_failing_network)
    download.start_queue()
    try:
        download.start("job-NETWORK", SessionKind.PROBE)
        kinds_path = tmp_path / "session-kinds.txt"
        assert spin(
            lambda: kinds_path.exists() and len(kinds_path.read_text("utf-8").splitlines()) >= 2,
            timeout=60,
        ), "the probe's automatic retry never ran"

        kinds = kinds_path.read_text("utf-8").splitlines()
        assert kinds[:2] == [SessionKind.PROBE.value, SessionKind.PROBE.value], (
            "the automatic retry changed a probe into a download, so a transient preview "
            f"failure can start writing without confirmation: {kinds[:2]}"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_the_attempt_count_is_bounded_and_the_last_error_survives(
    tmp_path: Path, spin: Callable[..., bool], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Second and fourth criteria: the bound holds, and exhausting it is not a silent give-up.

    A job that retried for ever would be a loop nobody asked for; one that forgot why it failed
    would leave the user with a `FAILED` row and no reason. Both are asserted, and the job must
    still be *manually* retryable afterwards — `is_retryable(NETWORK)` is true, and the bound is
    about what this queue does unattended, not about what a person may ask for.
    """
    quick_backoff(monkeypatch)
    repository = FakeRepository()
    repository.add(make_job("job-NETWORK", "https://example.invalid/clip", tmp_path))
    download = DownloadManager(repository, entry_point=child_failing_with_the_kind_its_job_id_names)
    download.start_queue()
    try:
        download.start("job-NETWORK")

        def the_bound_was_reached_and_settled() -> bool:
            """The last automatic attempt has been counted **and** has reported its outcome.

            Both halves, read from one snapshot. `attempts` is incremented by the retry that
            *starts* an attempt (`_perform_due_retries`), so the bound is reached a whole
            session before that session's failure lands — and waiting on the count alone left
            the assertions below racing a spawn. That is not academic: a session costs ~0.25 s
            on this maintainer's Linux box and ~1.07 s on `STARBASE`, so the fixed 1.0 s wait
            that used to stand here passed on one and failed on the other (runs `30822454998`
            and `30823595744`, both `PROBING is FAILED`). The manager was not at fault either
            time.
            """
            job = job_row(repository, "job-NETWORK")
            return (
                job.attempts >= manager_module.AUTOMATIC_RETRY_LIMIT
                and job.status is JobStatus.FAILED
            )

        assert spin(the_bound_was_reached_and_settled, timeout=120), (
            "the automatic attempts never reached the bound and settled"
        )

        # Well past another backoff: if the bound did not hold, this is where it would show.
        # Derived from the backoff `quick_backoff` installed rather than written as a number,
        # so "well past" stays true of the delay actually in force.
        spin(lambda: False, timeout=20 * manager_module.RETRY_BACKOFF_SECONDS[0])
        job = job_row(repository, "job-NETWORK")

        assert job.attempts == manager_module.AUTOMATIC_RETRY_LIMIT, (
            f"the bound of {manager_module.AUTOMATIC_RETRY_LIMIT} did not hold: {job.attempts}"
        )
        assert job.status is JobStatus.FAILED
        assert job.error_kind is ErrorKind.NETWORK
        assert job.error_message == "failed as network", (
            f"the last error was lost on the way through the retries: {job.error_message!r}"
        )

        download.retry("job-NETWORK")
        assert spin(
            lambda: job_row(repository, "job-NETWORK").status is not JobStatus.FAILED, 60
        ), "a job that exhausted its automatic attempts can no longer be retried by hand"
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_the_backoff_is_waited_rather_than_declared(
    tmp_path: Path, spin: Callable[..., bool], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Third criterion: the delay is **real**, measured, not asserted from the constant.

    A retry that fires immediately would satisfy every count-based assertion in this file while
    hammering a site that is briefly unreachable — which is the whole reason the delay exists.
    """
    quick_backoff(monkeypatch, seconds=1.0)
    repository = FakeRepository()
    repository.add(make_job("job-NETWORK", "https://example.invalid/clip", tmp_path))
    download = DownloadManager(repository, entry_point=child_failing_with_the_kind_its_job_id_names)
    download.start_queue()

    # **Both instants come from the manager, not from a poll** (`T083-R2`).
    #
    # This measured `failed_at` immediately after a `spin` loop *noticed* the failure — so the lag
    # between the transition and the poll that saw it was subtracted from the interval being
    # bounded, and a correct one-second backoff could read as short. `spin` sleeps 5 ms between
    # turns and pumps events in between, so under load that lag is not bounded at all, against a
    # margin of 0.1 s. Same defect class as `T118-R10`: an interval whose start is an observation.
    #
    # A signal fires on the thread that made the transition, at the moment it was made.
    failed_at: list[float] = []
    restarted_at: list[float] = []
    download.job_failed.connect(lambda *_: failed_at.append(time.monotonic()))
    download.job_changed.connect(
        lambda _job_id, status: (
            restarted_at.append(time.monotonic())
            if status == JobStatus.QUEUED.value and failed_at
            else None
        )
    )

    try:
        download.start("job-NETWORK")
        assert spin(lambda: bool(failed_at), timeout=60), "the job never reported a failure"
        assert spin(lambda: bool(restarted_at), timeout=60), "the retry never re-queued the job"

        waited = restarted_at[0] - failed_at[0]

        assert waited >= 0.9, (
            f"the retry fired {waited:.2f}s after the failure, inside its one-second backoff. "
            f"Both instants are the manager's own (`T083-R2`), so this is the delay itself rather "
            f"than the delay minus however long a poll took to notice."
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_retry_does_not_jump_ahead_of_a_job_that_has_never_run(tmp_path: Path) -> None:
    """Third criterion's other half, and it is not what `queue_position` alone would do.

    A re-queued job keeps its original position, which is *earlier* than everything added since —
    so ordering on position alone runs one job's second attempt before another job's first. The
    job that has never run goes first, on data already on the row.
    """
    repository = FakeRepository()
    repository.add(
        replace(
            make_job("job-retried", "https://example.invalid/clip", tmp_path),
            queue_position=0,
            attempts=1,
        )
    )
    repository.add(
        replace(
            make_job("job-fresh", "https://example.invalid/clip", tmp_path),
            queue_position=5,
            attempts=0,
        )
    )
    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download._waiting.extend(["job-retried", "job-fresh"])

        assert download._next_waiting() == "job-fresh", (
            "a job on its second attempt was scheduled ahead of one that has never run, even "
            "though it holds the earlier queue position"
        )
    finally:
        download._waiting.clear()
        download.shutdown()


def test_idle_is_not_announced_while_a_retry_is_waiting(
    tmp_path: Path, spin: Callable[..., bool], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T036-R1`'s rule, one more kind of accepted work.

    Composition treats `idle` as permission to quit, so announcing it with a retry pending would
    quit into work this manager has already decided to do.
    """
    quick_backoff(monkeypatch, seconds=30.0)
    repository = FakeRepository()
    repository.add(make_job("job-NETWORK", "https://example.invalid/clip", tmp_path))
    download = DownloadManager(repository, entry_point=child_failing_with_the_kind_its_job_id_names)
    download.start_queue()
    try:
        download.start("job-NETWORK")
        assert spin(
            lambda: job_row(repository, "job-NETWORK").status is JobStatus.FAILED, timeout=60
        )
        spin(lambda: False, timeout=0.5)

        assert not download.is_idle, (
            "idle went out with an automatic retry still waiting; composition would have quit "
            "into work this manager had accepted"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60), (
            "shutdown did not drop the pending retry, so the application could not quit"
        )


# --- T-080/T-181: the queue-level run gate; per-job cancel, retry and remove ----------------
#
# `UX-001` is the decision these gate, and it is a decision about *granularity* before it is one
# about behaviour: start and stop act on the queue, cancel and retry and remove act on a job.
# The assertions below are written to fail if that split is reversed, because the previous version
# of `T-080` described queue-level behaviour under a per-job title and an implementer reading it
# received mutually exclusive instructions.
#
# `UX-006` moved the gate's **default** and kept its semantics, so what follows is in two halves:
# the drain, which `T-080` established and which is unchanged, and the construction-time state,
# which `T-181` added and which the fixture above deliberately overrides for every other test.


def test_a_manager_starts_stopped_and_runs_nothing_until_it_is_started(
    tmp_path: Path, media_url: Callable[..., str], spin: Callable[..., bool]
) -> None:
    """`UX-006`: a restored queue starts nothing, and `Start` is what starts it.

    **Built directly rather than through the `manager` fixture**, which presses Start for the
    hundred tests that predate this one. A fixture that hid the shipped default could not assert
    it, and this is the assertion with the widest reach and the least visible symptom: an
    application that resumes a queue on launch looks exactly like one that does not, until it has
    spent somebody's bandwidth on a decision they never made.

    **Asserted on `_sessions` and on the durable status, and deliberately not on
    `active_job_ids()`.** That method counts waiting jobs as active on purpose (`T078-R1`) —
    they are a commitment this manager has accepted — so it answers "what is this manager
    holding", which a parked job is part of. It cannot express "nothing started", and the first
    version of this test used it and failed against correct code.
    """
    repository = FakeRepository()
    url = media_url(total_bytes=4 * 1024 * 1024, chunk_delay=0.02)
    for position, job_id in enumerate(("job-1", "job-2")):
        repository.add(replace(make_job(job_id, url, tmp_path), queue_position=position))

    download = DownloadManager(repository, concurrency=2)
    try:
        # Read into locals: mypy narrows a property across asserts, so asserting the opposite
        # afterwards types the rest of the test as unreachable and stops it being a gate. The same
        # idiom `test_the_composed_run_control_changes_the_real_manager` uses, and the one
        # `ci.yml`'s typed-tests step exists to catch — it caught this.
        constructed = download.is_running
        assert not constructed, "a freshly constructed manager was already running"

        for job_id in ("job-1", "job-2"):
            download.start(job_id)

        # **Long enough that a running queue would have started both.** The negative needs a
        # window in which the positive would have been observable, or it passes against a manager
        # that is merely slow — the shape `test_a_paused_queue_admits_and_still_starts_nothing`
        # already uses one layer up.
        assert not spin(lambda: bool(download._sessions), timeout=3), (
            f"a stopped queue spawned {sorted(download._sessions)}"
        )
        assert all(
            repository.jobs[job_id].status is JobStatus.QUEUED for job_id in ("job-1", "job-2")
        ), "the parked jobs did not stay durably QUEUED"
        assert set(download.active_job_ids()) == {"job-1", "job-2"}, (
            "the stopped queue dropped the jobs instead of parking them; they are accepted work "
            "waiting for a slot, which is what T078-R1 makes them"
        )

        download.start_queue()
        started = download.is_running
        assert started
        assert spin(lambda: len(download._sessions) == 2, timeout=60), (
            "Start did not run the jobs the stopped queue had parked"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_started_queue_stays_started_for_work_added_afterwards(
    tmp_path: Path, media_url: Callable[..., str], spin: Callable[..., bool]
) -> None:
    """`UX-006` chose a **mode**, not a one-shot batch commit.

    Draining does not re-arm the gate: a queue that empties and then receives a URL starts it.
    The rejected alternative — `Start` releasing only what was queued at that instant — would
    leave a row sitting `Held` beside running jobs with the difference visible nowhere.
    """
    repository = FakeRepository()
    url = media_url(total_bytes=64 * 1024)
    repository.add(replace(make_job("job-1", url, tmp_path), queue_position=0))

    download = DownloadManager(repository, concurrency=1)
    try:
        download.start_queue()
        download.start("job-1")
        assert spin(lambda: repository.jobs["job-1"].status is JobStatus.COMPLETED, timeout=60), (
            "the first job never finished, so the queue never drained"
        )
        assert spin(lambda: download.is_idle, timeout=60), "the queue never went idle"
        assert download.is_running, "draining the queue stopped it; the gate re-armed itself"

        repository.add(replace(make_job("job-2", url, tmp_path), queue_position=1))
        download.start("job-2")
        assert spin(lambda: repository.jobs["job-2"].status is JobStatus.COMPLETED, timeout=60), (
            "a job added to a drained-but-started queue needed a second Start"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_stopped_queue_parks_an_automatic_retry_until_it_is_started(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`UX-006` §7: **everything that begins work observes the gate**, retry included.

    This is the one path where the gate and the clock interact. `UX-002` schedules an automatic
    retry two seconds out, so a queue stopped in between has a decision already made and pending —
    and a retry is a *new* session rather than the continuation of a draining one, which is what
    makes parking it the right answer rather than an inconsistency with `UX-001`'s drain.

    **The backoff is waited out rather than mocked.** What is under test is that the deadline
    firing does not bypass the gate, and a fake clock that never fires would pass against an
    implementation with no gate at all.

    **The job starts `READY`, and that is load-bearing.** A `QUEUED` job's session is a *probe*
    (`ARC-004`), so its automatic retry is a probe too — and a probe is exempt from the gate, by
    the same rule that lets a stopped queue read a paste. The first version of this test used a
    `QUEUED` job, watched the retry run, and would have reported a correct exemption as a defect.
    A download retry is the one the criterion is about.

    **Mutation-checked, and the result was not what this docstring first claimed.** It said
    removing `_gate_blocks` from `_start_when_free` would fail this test. It does not: the gate is
    enforced twice, and a retry released there still meets `start()`'s guard through
    `_start_or_report`. Removing `start()`'s guard alone does not fail it either, for the mirror
    reason. **Only removing both** lets a stopped queue run the retry — measured 2026-08-07, all
    three mutants run.

    That is worth keeping rather than tidying away: it means no single-point mutation can
    demonstrate this criterion, and a reviewer who asks for one is asking for something the
    design does not offer. It also means neither guard is individually load-bearing, so a future
    simplification that deletes one will find the suite still green.
    """
    repository = FakeRepository()
    repository.add(
        replace(
            make_job("job-network", "https://retry.invalid/clip", tmp_path),
            status=JobStatus.READY,
        )
    )

    download = DownloadManager(
        repository, entry_point=child_recording_kind_then_failing_network, concurrency=1
    )
    try:
        download.start_queue()
        download.start("job-network")

        def failed() -> bool:
            return repository.jobs["job-network"].status is JobStatus.FAILED

        assert spin(failed, timeout=60), (
            "the job never failed, so no automatic retry was ever scheduled"
        )

        # Stopped *after* the failure and *before* the backoff expires, which is the window the
        # criterion is about.
        download.stop_queue()

        # **Wait for the failed session to be released before asserting no session exists.** The
        # process outlives its outcome — `_release` runs on a later tick — so an assertion made
        # straight after the failure catches the *dying original* and reports it as a retry. The
        # first version of this test did exactly that and failed against a correct gate.
        assert spin(lambda: not download._sessions, timeout=60), (
            "the failed session was never released, so nothing here can be attributed to a retry"
        )

        # `_sessions`, not `active_job_ids()`: a parked retry is *accepted* work and counts as
        # active by design (`T078-R1`). What must not exist is a spawned session. Six seconds
        # comfortably outlives `RETRY_BACKOFF_SECONDS[0]`, so the deadline really does fire inside
        # this window — a shorter wait would assert that nothing happened before anything could.
        assert not spin(lambda: bool(download._sessions), timeout=6), (
            f"a stopped queue ran an automatic retry: {sorted(download._sessions)}. The backoff "
            "fired and the gate did not hold it"
        )
        assert repository.jobs["job-network"].status is JobStatus.QUEUED, (
            "the retry's deadline never fired at all, so this proved nothing about the gate"
        )

        download.start_queue()
        assert spin(lambda: bool(download._sessions), timeout=60), (
            "starting the queue never released the retry the stop had parked"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_stopped_queue_still_probes(tmp_path: Path, spin: Callable[..., bool]) -> None:
    """`T080-R1` under `UX-006`, where the exemption stopped being a courtesy.

    A probe is exempt from the gate because reading a URL moves no bytes. That mattered rarely
    while a stopped queue was an unusual state; now it is the state every window opens in, so a
    gate that blocked probes would leave a first run unable to read anything the user pasted.
    """
    repository = FakeRepository()
    repository.add(make_job("job-probe", "https://probe.invalid/clip", tmp_path))

    # `child_downloading_forever` simply keeps its session alive; what is under test is whether
    # the *admission* happens, not what the child says once it has.
    download = DownloadManager(repository, entry_point=child_downloading_forever)
    try:
        assert not download.is_running
        download.start("job-probe", kind=SessionKind.PROBE)
        assert spin(lambda: tuple(download._sessions) == ("job-probe",), timeout=60), (
            "a stopped queue refused a probe, so a first-run paste can never be read"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_pausing_a_saturated_queue_drains_it_and_starts_nothing(
    tmp_path: Path, media_url: Callable[..., str], spin: Callable[..., bool]
) -> None:
    """`UX-001`, `T-080`: pause lets in-flight work finish and starts none of the waiting jobs.

    **The pool is saturated and there are jobs behind it**, which is the only arrangement where
    pause is distinguishable from doing nothing. A test that paused an idle queue would pass
    against an implementation whose `pause()` was `return None`.

    Real sessions against the slow local server, because "the in-flight ones finish" is a claim
    about processes rather than about rows: a killed session also stops being active.
    """
    repository = FakeRepository()
    url = media_url(total_bytes=4 * 1024 * 1024, chunk_delay=0.02)
    for position, job_id in enumerate(("job-1", "job-2", "job-3", "job-4")):
        repository.add(replace(make_job(job_id, url, tmp_path), queue_position=position))

    download = DownloadManager(repository, concurrency=2)
    download.start_queue()
    try:
        download.start("job-1")
        download.start("job-2")
        download._start_when_free("job-3")
        download._start_when_free("job-4")
        assert spin(lambda: len(download._sessions) == 2, timeout=60), "the pool never saturated"

        download.stop_queue()
        assert not download.is_running

        # The two in flight are still in flight, and stay so after the loop has had its chance.
        live = set(download._sessions)
        spin(lambda: False, timeout=0.5)
        assert set(download._sessions) == live, (
            "pausing stopped work already in flight; UX-001 chose draining precisely because a "
            "stopped download leaves a partial file nothing can resume in this phase"
        )
        assert download._waiting == ["job-3", "job-4"], (
            f"waiting {download._waiting}; a paused queue must start none of them"
        )

        # And a slot opening while paused still starts nothing — the tick is the path that would.
        download.set_concurrency(4)
        spin(lambda: False, timeout=0.5)
        assert download._waiting == ["job-3", "job-4"], (
            "a free slot started a waiting job while the queue was paused; the pause guard is not "
            "on the path the tick takes"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_resuming_starts_the_waiting_jobs(tmp_path: Path, spin: Callable[..., bool]) -> None:
    """`UX-001`, `T-080`: the other half, and it is a separate test on purpose.

    A `pause()` that set a flag nothing ever cleared would pass the drain assertion above. This is
    what says the queue comes back.

    **Resume fills the slots without spinning the event loop**, which is `set_concurrency`'s rule
    for the same reason: a tick is up to `poll_interval_ms` away, invisible in a test that spins
    and perfectly visible to somebody who just pressed Resume.
    """
    repository = FakeRepository()
    queued(repository, "job-1", "job-2", directory=tmp_path)

    download = DownloadManager(repository, concurrency=2, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.stop_queue()
        download._start_when_free("job-1")
        download._start_when_free("job-2")
        assert download._waiting == ["job-1", "job-2"], "a paused queue started something"
        assert not download._sessions

        download.start_queue()

        assert download.is_running
        assert download._waiting == [], (
            f"waiting {download._waiting}; resume must take the work, and take it now rather than "
            "on whichever tick happens to fire next"
        )
        assert set(download.active_job_ids()) == {"job-1", "job-2"}
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_pause_leaves_no_partial_file_because_it_stops_nothing(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`UX-001`, `T-080`: asserted by **looking at the output directory**, not at the code path.

    This is the whole reason pause drains rather than stops. `REQ-017`'s resume is Phase 3, so a
    paused download's partial file would have no defined meaning — nothing could resume from it and
    nothing was specified to clean it up. Draining means the question never arises, and the way to
    show that is that pausing a queue with nothing running writes nothing at all.
    """
    outputs = tmp_path / "downloads"
    outputs.mkdir()
    repository = FakeRepository()
    queued(repository, "job-1", "job-2", directory=outputs)

    download = DownloadManager(repository, concurrency=2, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.stop_queue()
        download._start_when_free("job-1")
        download._start_when_free("job-2")
        spin(lambda: False, timeout=0.5)

        assert list(outputs.iterdir()) == [], (
            f"pausing produced files: {[p.name for p in outputs.iterdir()]}. A paused queue has "
            "not started the work, so there is nothing partial for a phase without REQ-017 to "
            "have a rule about"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_no_job_ever_reaches_a_paused_status_because_there_is_no_such_status(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T-080`'s fourth criterion, asserted against the **stored status** and against the enum.

    Two assertions, because they fail for different reasons. The stored-status one would catch an
    implementation that invented a paused state under another name; the enum one records the
    maintainer decision of 2026-07-31 — `JobStatus.PAUSED` is gone, so an implementation that
    wanted to write it cannot even spell it.

    `RUNNING → PAUSED` was the edge that made it look reachable. Removing the member is what makes
    the removal of the edge checkable: a member left behind with no transitions would still let
    `replace(job, status=PAUSED)` build a job nothing could move.
    """
    assert not hasattr(JobStatus, "PAUSED"), (
        "JobStatus.PAUSED is back. UX-001 makes pause a queue-level drain, so no job enters it; "
        "T-080 removed it because an unreachable status reads as capability without being it"
    )

    repository = FakeRepository()
    queued(repository, "job-1", directory=tmp_path)
    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.start("job-1")
        # **Settled before pausing, not merely started.** `child_downloading_forever` walks
        # `PROBING → READY → RUNNING` and then stays, so a snapshot taken the moment a session
        # exists can be overtaken by the pipeline's own next step — which made the first version of
        # this test fail intermittently under the full suite while passing alone. Waiting for the
        # status the worker settles at means any later change is one pause caused.
        assert spin(lambda: job_row(repository, "job-1").status is JobStatus.RUNNING, timeout=60), (
            "the session never reached RUNNING, so there was no settled status to pause against"
        )

        download.stop_queue()
        spin(lambda: False, timeout=0.5)

        stored = repository.get("job-1")
        assert stored is not None
        assert stored.status is JobStatus.RUNNING, (
            f"a paused queue moved a running job to {stored.status.value}; pause is a property of "
            "the queue and of nothing else, which is why T-080 could delete JobStatus.PAUSED"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_removing_a_job_takes_it_out_of_the_queue_and_leaves_the_files_alone(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`UX-001`, `REQ-015` as amended: remove is per job, and it **never deletes a file**.

    The file assertion looks at the directory rather than trusting that no `unlink` was called,
    because that is the promise a user cares about and the only form of it a future refactor
    cannot quietly break.
    """
    outputs = tmp_path / "downloads"
    outputs.mkdir()
    already_there = outputs / "something the user already had.mp4"
    already_there.write_bytes(b"not ours to delete")

    repository = FakeRepository()
    queued(repository, "job-1", "job-2", directory=outputs)
    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    removed: list[str] = []
    download.job_removed.connect(removed.append)
    try:
        download.remove("job-2")
        assert spin(lambda: removed == ["job-2"], timeout=10), (
            "job_removed never arrived; removal is announced from the write callback, so a "
            "removal that is never announced is one that may never have landed"
        )
        assert repository.get("job-2") is None
        assert repository.removals == ["job-2"]
        assert repository.get("job-1") is not None, "removing one job took another with it"

        assert already_there.exists(), (
            "removing a job deleted a file. UX-001: remove takes the job out of the queue, and "
            "nothing this application deletes from disk goes by that route"
        )
        assert already_there.read_bytes() == b"not ours to delete"
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_removing_a_waiting_job_stops_the_pool_from_ever_starting_it(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T-080`: a removed job must not be started by the tick that fires while its delete is queued.

    The window is real — `remove()` returns before the row is gone — and the waiting list is what
    the tick reads. Dropping the id from it is therefore part of removing the job, not tidying up
    afterwards.
    """
    repository = FakeRepository()
    queued(repository, "job-1", "job-2", directory=tmp_path)
    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.start("job-1")
        download._start_when_free("job-2")
        assert download._waiting == ["job-2"]

        download.remove("job-2")

        assert download._waiting == [], "a removed job was left waiting for a slot"
        download.set_concurrency(2)
        spin(lambda: False, timeout=0.5)
        assert "job-2" not in download.active_job_ids(), (
            "a removed job was started when a slot opened; it was still on the waiting list"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_removing_a_running_job_cancels_it_first_and_inside_the_budget(
    tmp_path: Path,
    media_url: Callable[..., str],
    spin: Callable[..., bool],
    existing_children: set[int],
    record_property: Callable[[str, object], None],
) -> None:
    """`T-080`: removing a running job is a cancel **plus** a delete, and cancel keeps its budget.

    `REQ-015`'s two seconds is not relaxed by the delete being queued behind it, so the clock is
    the same one `test_cancel_stops_a_real_in_flight_download_within_the_budget` runs.

    **The row must outlive the process**, which is the ordering half. Deleting it when the cancel
    was asked for would leave a live worker whose next message reaches a job that is not there.
    """
    repository = FakeRepository()
    url = media_url(total_bytes=512 * 1024 * 1024, chunk_delay=0.01)
    repository.add(make_job("job-1", url, tmp_path))
    download = DownloadManager(repository, concurrency=1)
    download.start_queue()
    removed: list[str] = []
    download.job_removed.connect(removed.append)
    recorder = Recorder(download, repository)
    try:
        download.start("job-1")
        assert spin(lambda: bool(recorder.progress), timeout=60), "the download never moved"
        assert worker_processes(existing_children), "there was no worker process to remove"

        started = time.monotonic()
        download.remove("job-1")
        stopped = spin(
            lambda: not worker_processes(existing_children), timeout=CANCEL_BUDGET_SECONDS + 3.0
        )
        elapsed = time.monotonic() - started

        assert stopped, "a worker process outlived the removal of its job"
        record_property("remove_seconds", round(elapsed, 3))
        assert elapsed < CANCEL_BUDGET_SECONDS, (
            f"removing a running job took {elapsed:.2f}s to stop it (REQ-015: 2s)"
        )

        assert spin(lambda: removed == ["job-1"], timeout=10), "the row was never removed"
        assert repository.get("job-1") is None
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_manual_retry_re_enters_the_queue_at_the_back(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`P2PLAN-R7`, confirmed 2026-07-31: manual retry does not jump jobs that have not run.

    **The jobs behind it have never run**, which is the arrangement the rule is about. A failed job
    keeps the `queue_position` it was added with — earlier than everything queued since — so a
    retry that re-queued in place would run a second attempt before another job's first.

    Asserted on `queue_position` rather than only on which job starts next, because the position is
    what the table shows: a scheduling rule the column disagrees with is a view that lies about
    what happens next, which is `T-081`'s criterion one task early.
    """
    repository = FakeRepository()
    queued(repository, "job-1", "job-2", "job-3", directory=tmp_path)
    failed = repository.get("job-1")
    assert failed is not None
    repository.jobs["job-1"] = failed.with_failure(ErrorKind.NETWORK, "the transfer stalled")

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        before = repository.get("job-1")
        assert before is not None and before.queue_position == 0

        # Paused so the retry parks instead of starting immediately, which keeps this test about
        # the position it was written with rather than about how far the restarted job got.
        download.stop_queue()
        download.retry("job-1")

        after = repository.get("job-1")
        assert after is not None
        assert after.status is JobStatus.QUEUED
        assert after.queue_position is not None
        assert after.queue_position > 2, (
            f"a manual retry kept position {after.queue_position}; job-2 and job-3 have never run "
            "and sit at 1 and 2, so re-queuing in place puts a second attempt ahead of two firsts"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_manual_retry_starts_after_the_jobs_that_have_not_run(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """The same rule, observed as **the order jobs actually start** rather than as a column.

    Two assertions of one contract, deliberately: the position could be written correctly and read
    by nothing, or the scheduler could order correctly and leave the table disagreeing. `T-075` is
    what a view and a scheduler disagreeing looks like when only one of them is gated.
    """
    repository = FakeRepository()
    queued(repository, "job-1", "job-2", directory=tmp_path)
    failed = repository.get("job-1")
    assert failed is not None
    repository.jobs["job-1"] = failed.with_failure(ErrorKind.NETWORK, "the transfer stalled")

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        # Saturate with a job that is not part of the comparison, so both candidates must wait.
        repository.add(
            replace(make_job("job-hold", "https://example.invalid/x", tmp_path), queue_position=99)
        )
        download.start("job-hold")
        assert spin(lambda: "job-hold" in download.active_job_ids(), timeout=60)

        download.retry("job-1")
        download._start_when_free("job-2")
        assert set(download._waiting) == {"job-1", "job-2"}

        assert download._next_waiting() == "job-2", (
            "the retried job was scheduled ahead of a job that has never run; P2PLAN-R7 puts a "
            "manual retry at the back"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_pause_does_not_refuse_a_probe_the_user_just_asked_for(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`UX-001` scopes pause to the queue draining; a probe is not queue work waiting for a slot.

    The add-URL dialog calls `start(..., PROBE)` when the user types a URL. Refusing it silently
    while the queue is paused would hang the dialog on "Probing …" with nothing to say why — the
    exact shape `start_rejected` exists to prevent.

    Recorded as a test rather than a comment because it is the one place the pause guard is
    deliberately *absent*, and an absence that nothing asserts is indistinguishable from an
    oversight.
    """
    repository = FakeRepository()
    queued(repository, "job-1", directory=tmp_path)
    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.stop_queue()
        download.start("job-1", SessionKind.PROBE)

        # **Occupancy, not `active_job_ids()`.** That accounting deliberately includes jobs merely
        # *waiting* for a slot (`T078-R1`), so a probe the guard had wrongly parked would still
        # appear in it — the assertion would pass while the dialog hung. A probe that really ran
        # holds a slot.
        assert "job-1" in download._occupant_ids(), (
            f"occupants {download._occupant_ids()}; a paused queue refused or parked a directly "
            "requested probe. Pause governs downloads waiting in the queue, not the metadata "
            "request the user just made, and a parked probe hangs the add dialog on 'Probing ...'"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_pause_does_not_allow_a_direct_download_start(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`UX-001`: the probe exemption must not exempt a download from queue pause.

    The add dialog calls ``start(..., DOWNLOAD)`` after a successful probe.  That is new queue
    work, unlike the metadata probe itself, so allowing every direct ``start`` through makes the
    ordinary Add path start a download while the queue says it is paused.
    """
    repository = FakeRepository()
    queued(repository, "job-1", directory=tmp_path)
    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.stop_queue()
        with contextlib.suppress(RuntimeError):
            download.start("job-1", SessionKind.DOWNLOAD)

        assert download._occupant_ids() == (), (
            "a direct DOWNLOAD start bypassed queue pause; only PROBE has the user-requested "
            "metadata exemption"
        )
        stored = repository.get("job-1")
        assert stored is not None and stored.status is JobStatus.QUEUED
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


# --- T-081: reordering and clearing, through the manager ----------------------------------


def test_reordering_changes_the_order_the_pool_starts_jobs_in(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T-081`'s fourth criterion: the order the pool starts jobs in is the order the table shows.

    **Asserted through `_next_waiting`, which is what actually decides**, rather than through the
    stored column alone. `T-075` is what a view and a scheduler disagreeing looks like when only
    one of them is gated, and `queue_position` is the single fact both read — so a reordering that
    wrote the column without the scheduler noticing would be that defect again.
    """
    repository = FakeRepository()
    queued(repository, "job-1", "job-2", "job-3", directory=tmp_path)

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    ordered: list[tuple[str, ...]] = []
    download.queue_reordered.connect(ordered.append)
    try:
        download.stop_queue()
        for job_id in ("job-1", "job-2", "job-3"):
            download._start_when_free(job_id)
        assert download._next_waiting() == "job-1", "before reordering, position decides"

        download.reorder(["job-3", "job-2", "job-1"])

        assert ordered == [("job-3", "job-2", "job-1")], (
            "the reordering was not announced; a view that is not told keeps showing the order the "
            "user replaced"
        )
        assert download._next_waiting() == "job-3", (
            "the pool still starts the old first job; queue_position is the one fact the table and "
            "the scheduler share, and reordering must move it"
        )
        assert repository.reorderings == [("job-3", "job-2", "job-1")]
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_pool_does_not_start_from_the_old_order_while_reordering_is_in_flight(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`REQ-016`: an asynchronous reorder must gate scheduling on the order it replaces.

    The writer serialises the *writes*, but the scheduler chooses a job on the GUI thread before
    its start transition is submitted.  If it reads while the reorder is still in flight, it can
    choose job-1 from the old order, after which the writer commits job-2 first and then starts
    job-1.  Both writes succeed, but the pool has started a job behind the new head.

    Holding only the reorder callback reproduces that exact window.  The store otherwise settles
    job writes synchronously, so any active job before ``release_reorder`` is one the scheduler
    chose from the old positions rather than one allowed by the new order.
    """

    class HeldReorderStore(FakeRepository):
        def __init__(self) -> None:
            super().__init__()
            self.pending_reorder: tuple[tuple[str, ...], Callable[[str | None], None]] | None = None

        def reorder(self, job_ids: Sequence[str], done: Callable[[str | None], None]) -> None:
            assert self.pending_reorder is None
            self.pending_reorder = (tuple(job_ids), done)

        def release_reorder(self) -> None:
            assert self.pending_reorder is not None
            job_ids, done = self.pending_reorder
            self.pending_reorder = None
            super().reorder(job_ids, done)

    repository = HeldReorderStore()
    queued(repository, "job-1", "job-2", directory=tmp_path)
    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.stop_queue()
        download._start_when_free("job-1")
        download._start_when_free("job-2")

        download.reorder(["job-2", "job-1"])
        download.start_queue()

        assert download._occupant_ids() == (), (
            "the pool chose a job while the reorder was still in flight; that choice used the "
            "old queue positions"
        )

        repository.release_reorder()
        download._fill_free_slots()

        assert "job-2" in download._occupant_ids(), (
            "after the reorder landed, the pool did not start the new first job"
        )
        assert "job-1" not in download._occupant_ids(), (
            "the pool started job-1 even though the committed order puts job-2 first"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_clearing_finished_jobs_announces_and_keeps_the_unfinished(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`REQ-016`: completed and cancelled go; queued and failed stay, and the queue is told."""
    repository = FakeRepository()
    queued(repository, "done", "stopped", "waiting", "broken", directory=tmp_path)
    for job_id, status in (
        ("done", JobStatus.COMPLETED),
        ("stopped", JobStatus.CANCELLED),
        ("broken", JobStatus.FAILED),
    ):
        stored = repository.get(job_id)
        assert stored is not None
        repository.jobs[job_id] = replace(stored, status=status)

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    cleared: list[int] = []
    download.queue_cleared.connect(lambda: cleared.append(1))
    try:
        download.clear_completed()

        assert cleared == [1], "clearing was not announced"
        assert sorted(repository.cleared) == ["done", "stopped"]
        assert repository.get("waiting") is not None
        assert repository.get("broken") is not None, (
            "a failed job was cleared; it is still in the queue offering a retry"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_cancelling_a_waiting_job_drops_it_from_the_waiting_list(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T-103`: cancelling a job that is only *waiting* stops it waiting, at the cancel.

    This used to be left behind. The id stayed on `_waiting`, the next free slot picked it, and
    `start()` refused it because a `CANCELLED` job is not startable — one swallowed refusal, and
    harmless while the row existed. `T-081`'s clear-finished deletes that row, at which point the
    same path reaches `_require` with an id that resolves to nothing.

    *(`T-081` carried a sweep in `_settle_clear` for the narrow case it made reachable, and a test
    here asserting the stale premise so it would fail loudly when this landed. It did. The sweep is
    removed with this change: every path that can delete a waiting job's row now drops it from the
    list first, so the sweep could not fire and a guard nothing can reach is `ai/TESTING.md` §13's
    shape.)*
    """
    repository = FakeRepository()
    queued(repository, "job-1", "job-2", directory=tmp_path)

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    rejections: list[tuple[str, str]] = []
    download.start_rejected.connect(lambda job_id, reason: rejections.append((job_id, reason)))
    try:
        download.start("job-1")
        download._start_when_free("job-2")
        assert download._waiting == ["job-2"]

        download.cancel("job-2")

        assert download._waiting == [], (
            "a cancelled job is still queued for a slot it can never use"
        )

        # And the pool does not later try to start it, which is what produced the swallowed
        # refusal — asserted on the signal rather than on the absence of a session, because a
        # refused start leaves no session either way.
        download.set_concurrency(2)
        spin(lambda: False, timeout=0.5)
        assert not [job_id for job_id, _ in rejections if job_id == "job-2"], (
            f"the pool tried to start a cancelled job: {rejections}"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_queue_whose_only_waiting_job_was_cancelled_goes_idle(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T-103`'s observable cost: `is_idle` counts waiting jobs (`T036-R1`, `T-078`).

    A cancelled job left on the list held the shutdown door open until a slot happened to free —
    the manager reported work it would never do. Nothing here is running, so idle must be immediate
    rather than eventual.
    """
    repository = FakeRepository()
    queued(repository, "job-1", directory=tmp_path)

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.stop_queue()
        download._start_when_free("job-1")
        assert not download.is_idle, "a job waiting for a slot is work this manager has accepted"

        download.cancel("job-1")

        assert download.is_idle, (
            "the manager still reports work in hand after its only waiting job was cancelled"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_clearing_after_a_cancel_leaves_nothing_looking_up_a_missing_row(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """The end-to-end property `T-081`'s sweep used to hold, now held by `cancel` alone.

    Kept as a test of the *property* rather than of the removed mechanism: clearing finished jobs
    after cancelling a waiting one must leave nothing queued to start, and must not have the pool
    reach for a row that has been deleted.
    """
    repository = FakeRepository()
    queued(repository, "job-1", "job-2", directory=tmp_path)

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.start("job-1")
        download._start_when_free("job-2")
        download.cancel("job-2")
        download.clear_completed()

        assert repository.get("job-2") is None, "the cancelled job's row was not cleared"
        assert download._waiting == []
        download.set_concurrency(2)
        spin(lambda: False, timeout=0.5)
        assert "job-2" not in download.active_job_ids()
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


class ReorderHoldingRepository(FakeRepository):
    """`FakeRepository`, but reorder settles only when the test says so.

    The defect `T081-R1` reports lives entirely inside the window between asking for a reorder and
    it landing, and a store that settles immediately closes that window and proves nothing. Same
    reasoning as `HeldStore`, applied to the one operation that needs it.
    """

    def __init__(self) -> None:
        super().__init__()
        self.held: list[tuple[list[str], Callable[[str | None], None]]] = []

    def reorder(self, job_ids: Sequence[str], done: Callable[[str | None], None]) -> None:
        self.held.append((list(job_ids), done))

    def release_reorders(self, error: str | None = None) -> None:
        """Settle every held reorder, applying it first unless this one failed."""
        held, self.held = self.held, []
        for job_ids, done in held:
            if error is None:
                super().reorder(job_ids, lambda _: None)
            done(error)


def test_a_reorder_in_flight_stops_the_pool_admitting_the_old_head(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T081-R1`: the stale read happens on the GUI thread, before either write is queued.

    `ARC-005`'s single writer serialises writes and does nothing about the scheduling decision that
    precedes one. With a reorder in flight, a tick or a resume could run `_next_waiting()` against
    the positions the reorder was replacing, pick the old head, and start it — and because the
    writer is FIFO the reorder committed *first*, leaving the queue durably saying one thing and
    the running job saying another.

    **Asserted at the moment of the race, not after it.** Waiting for the dust to settle would
    show a consistent queue and hide that the wrong job was chosen.
    """
    repository = ReorderHoldingRepository()
    queued(repository, "job-1", "job-2", directory=tmp_path)

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.stop_queue()
        download._start_when_free("job-1")
        download._start_when_free("job-2")

        download.reorder(["job-2", "job-1"])
        download.start_queue()

        assert download._occupant_ids() == (), (
            f"occupants {download._occupant_ids()}; a job was admitted while the order deciding "
            "which job runs next had not landed"
        )

        repository.release_reorders()

        assert "job-2" in download._occupant_ids(), (
            f"occupants {download._occupant_ids()}; once the reorder settled the pool must start "
            "the job the *new* order puts first"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_refused_reorder_releases_the_barrier_and_uses_the_old_order(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """A failed write must not leave the pool shut. The order is simply unchanged.

    The barrier exists to stop a decision being made against positions that are about to change.
    When the change does not happen, the positions are still authoritative and the queue must run
    on them — holding it closed would turn one failed write into a stalled application.
    """
    repository = ReorderHoldingRepository()
    queued(repository, "job-1", "job-2", directory=tmp_path)

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    refusals: list[tuple[str, str]] = []
    download.persistence_failed.connect(lambda job_id, reason: refusals.append((job_id, reason)))
    try:
        download.stop_queue()
        download._start_when_free("job-1")
        download._start_when_free("job-2")
        download.reorder(["job-2", "job-1"])
        download.start_queue()
        assert download._occupant_ids() == ()

        repository.release_reorders(error="the writer refused this reorder")

        assert refusals, "a refused reorder was not surfaced"
        assert "job-1" in download._occupant_ids(), (
            f"occupants {download._occupant_ids()}; the reorder did not happen, so the stored "
            "order still puts job-1 first and the pool must run on it rather than stay shut"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_two_reorders_in_flight_hold_the_barrier_until_both_settle(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T081-R1` names this case: a boolean cleared by the first callback reopens the window.

    Two reorders are asked for and released one at a time. After the first settles the second is
    still in flight, so its positions are still about to change and nothing may be admitted yet.
    """
    repository = ReorderHoldingRepository()
    queued(repository, "job-1", "job-2", "job-3", directory=tmp_path)

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.stop_queue()
        for job_id in ("job-1", "job-2", "job-3"):
            download._start_when_free(job_id)

        download.reorder(["job-2", "job-1"])
        download.reorder(["job-3", "job-2"])
        download.start_queue()
        assert download._occupant_ids() == ()

        # Settle exactly one of the two.
        first, repository.held = repository.held[:1], repository.held[1:]
        for job_ids, done in first:
            FakeRepository.reorder(repository, job_ids, lambda _: None)
            done(None)

        assert download._occupant_ids() == (), (
            f"occupants {download._occupant_ids()}; one reorder settled but another is still in "
            "flight, and a counter is what stops the first callback reopening the window"
        )

        repository.release_reorders()
        assert download._occupant_ids(), "the barrier never lifted once both reorders settled"
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_direct_download_start_cannot_bypass_the_reorder_barrier(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T081-R1`: the public download entry point is an admission path too.

    The scheduler normally reaches ``start`` through ``_fill_free_slots`` or
    ``_start_when_free``, but the add dialog calls ``start(..., DOWNLOAD)`` directly after a
    probe. While a reorder is in flight that call must not admit a queued job using the order
    being replaced. Metadata probes retain their separate exemption.
    """
    repository = ReorderHoldingRepository()
    queued(repository, "job-1", "job-2", directory=tmp_path)
    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.reorder(["job-2", "job-1"])
        download.start("job-1", SessionKind.DOWNLOAD)

        assert download._occupant_ids() == (), (
            f"occupants {download._occupant_ids()}; direct DOWNLOAD bypassed the in-flight "
            "reorder barrier and admitted a job from the order being replaced"
        )

        repository.release_reorders()
        # The first reviewer version asserted that job-2 starts here. That invented a product
        # rule: only job-1 has been admitted, so the reorder may delay that intent but may not
        # replace it with an unattended start of a different row. Ordering decides between work
        # already waiting; it does not make every row in the durable table waiting.
        assert "job-1" in download._occupant_ids(), (
            f"occupants {download._occupant_ids()}; after the reorder landed the explicitly "
            "started job did not run"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_settling_a_reorder_does_not_admit_a_job_nobody_started(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T081-R4`: re-deciding order must not invent admission intent.

    The durable table contains jobs that this manager is not currently meant to run: most
    concretely, a `QUEUED` row recovered after an interrupted application start.  Reordering says
    where admitted work runs; it is not itself a request to restart every row named by the order.

    Hold a reorder while the user explicitly starts only the READY job.  When the write settles,
    the recovered job is first in the new order but still has no start intent.  Starting it would
    turn one requested download into unattended work on a different job.
    """
    repository = ReorderHoldingRepository()
    queued(repository, "recovered", "requested", directory=tmp_path)
    requested = repository.get("requested")
    assert requested is not None
    repository.add(replace(requested, status=JobStatus.READY))

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.reorder(["recovered", "requested"])
        download.start("requested", SessionKind.DOWNLOAD)
        assert download._waiting == ["requested"], "the explicit start intent was not parked"

        repository.release_reorders()

        assert "requested" in download._occupant_ids(), (
            f"occupants {download._occupant_ids()}; settling the order dropped the job the user "
            "actually started"
        )
        assert "recovered" not in download.active_job_ids(), (
            f"active jobs {download.active_job_ids()}; reordering admitted a recovered job that "
            "nobody asked this manager to start"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_removing_a_job_awaiting_an_automatic_retry_drops_the_retry(
    tmp_path: Path, spin: Callable[..., bool], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T-103`, the half the waiting list does not cover: `_retry_at` is a second list of intent.

    A `NETWORK` failure schedules an automatic retry (`UX-002`) and the job sits in `_retry_at`
    until its backoff expires. `is_idle` counts that list exactly as it counts `_waiting`, so a job
    the user has taken out of the queue must not go on holding the shutdown door open for work the
    manager will never do.

    **Remove, not cancel.** A job awaiting a retry is `FAILED`, and `FAILED` allows only `QUEUED`
    (`T010-R3`: cancelling stops in-flight work, and a failed job has none). Cancelling one raises
    out of the state machine, which is why `cancel()` carries no `_retry_at` pop — the first
    version of `T-103` added one and a mutation showed nothing could reach it.
    """
    quick_backoff(monkeypatch)
    repository = FakeRepository()
    queued(repository, "job-1", directory=tmp_path)
    stored = repository.get("job-1")
    assert stored is not None
    repository.jobs["job-1"] = stored.with_failure(ErrorKind.NETWORK, "the transfer stalled")

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download._schedule_automatic_retry("job-1", ErrorKind.NETWORK)
        # Read into locals for `test_composition`'s reason: mypy narrows a property across
        # asserts, and asserting the opposite afterwards makes the rest of the test unreachable.
        waiting = download.is_idle
        assert not waiting, "a job waiting out its backoff is work this manager will do"

        download.remove("job-1")

        idle = download.is_idle
        assert idle, "the manager still reports work in hand for a removed job's automatic retry"
        spin(lambda: False, timeout=0.5)
        assert repository.get("job-1") is None, "the removed job came back when its retry fired"
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


# --- T083-R1: a retry restarts the operation that failed -----------------------------------


def test_an_automatic_retry_of_a_download_stays_a_download(
    tmp_path: Path, spin: Callable[..., bool], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The paired half of `T083-R1`, and the one every committed retry test already covered.

    Written as a pair with `test_an_automatic_retry_preserves_a_probe_as_a_probe` because the fix
    carries the failed session's kind: it must not quietly become "always probe" either. The
    reviewer's probe test alone would pass against exactly that mistake.

    Uses the same file-based recorder, because `ARC-002` puts the entry point in another process
    and an in-memory list would record nothing.
    """
    quick_backoff(monkeypatch)
    repository = FakeRepository()
    repository.add(make_job("job-NETWORK", "https://example.invalid/clip", tmp_path))
    download = DownloadManager(repository, entry_point=child_recording_kind_then_failing_network)
    download.start_queue()
    try:
        download.start("job-NETWORK", SessionKind.DOWNLOAD)
        kinds_path = tmp_path / "session-kinds.txt"
        assert spin(
            lambda: kinds_path.exists() and len(kinds_path.read_text("utf-8").splitlines()) >= 2,
            timeout=60,
        ), "the download's automatic retry never ran"

        kinds = kinds_path.read_text("utf-8").splitlines()
        assert kinds[:2] == [SessionKind.DOWNLOAD.value, SessionKind.DOWNLOAD.value], (
            f"spawned kinds {kinds[:2]}; a failed download must be retried as a download"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_retried_probe_writes_no_output(
    tmp_path: Path, spin: Callable[..., bool], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T083-R1`'s consequence, asserted where the user would feel it.

    The finding is not "the enum is wrong" — it is that a transient failure while *previewing* a
    URL began writing media nobody had confirmed. So this asserts the output directory, which is
    the thing a probe must never touch and the only assertion a future regression cannot satisfy
    by relabelling a session.
    """
    quick_backoff(monkeypatch)
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    repository = FakeRepository()
    repository.add(make_job("job-NETWORK", "https://example.invalid/clip", downloads))
    download = DownloadManager(repository, entry_point=child_recording_kind_then_failing_network)
    download.start_queue()
    try:
        download.start("job-NETWORK", SessionKind.PROBE)
        kinds_path = downloads / "session-kinds.txt"
        assert spin(
            lambda: kinds_path.exists() and len(kinds_path.read_text("utf-8").splitlines()) >= 2,
            timeout=60,
        ), "the probe's automatic retry never ran"

        produced = [p for p in downloads.iterdir() if p.name != "session-kinds.txt"]
        assert produced == [], (
            f"a retried probe produced {[p.name for p in produced]}; probing must never write"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_parked_probe_still_resumes_as_a_probe(tmp_path: Path, spin: Callable[..., bool]) -> None:
    """`T083-R1`'s second path: the retry defers, and `_fill_free_slots` is what restarts it.

    `_perform_due_retries` passes the kind explicitly, so a retry that starts *immediately* keeps
    it either way. When the probe parks instead, it is later picked up by `_fill_free_slots`,
    which has no kind of its own — taking `start`'s default there turns the parked probe into a
    download at the moment it resumes.

    Found by mutation: replacing the recorded-kind lookup with a plain `DOWNLOAD` survived the
    whole battery, because every existing test exercised the immediate path.

    **Parked behind a full probe lane** (`T-116`). It used to hold the single *download* slot,
    which parked a probe only while both drew on one budget. A version between the two parked it
    behind **pause**, which stopped working when pause became kind-aware — `UX-003` needs a paused
    queue to keep reading URLs, so pause parks downloads and admits probes. The lane is the only
    thing left that parks a probe, which is as it should be.
    """
    repository = FakeRepository()
    queued(repository, "holder", "job-1", directory=tmp_path)

    download = DownloadManager(
        repository, concurrency=3, probe_concurrency=1, entry_point=child_downloading_forever
    )
    download.start_queue()
    try:
        download.start("holder", SessionKind.PROBE)
        assert spin(lambda: "holder" in download._occupant_ids(SessionKind.PROBE), timeout=60)

        download._start_when_free("job-1", SessionKind.PROBE)
        assert download._waiting == ["job-1"], "the probe was not parked behind the full lane"

        download.cancel("holder")

        assert spin(lambda: "job-1" in download._sessions, timeout=60), (
            "the parked probe never started once the lane freed"
        )
        assert download._sessions["job-1"].kind is SessionKind.PROBE, (
            f"the parked probe resumed as {download._sessions['job-1'].kind.value}; a slot opening "
            "must not change what operation the user asked for"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


# --- T-116: the metadata lane -------------------------------------------------------------------
#
# `UX-003` makes probing what happens when a user pastes, rather than a button covering one URL.
# Under a single budget that meant adding URLs took the download slots, so the transfers a user was
# watching stopped while their paste resolved. These assert the two lanes are actually two.


def test_a_probe_is_released_before_the_same_job_starts_downloading(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """Separate lane capacity must not overwrite the previous session for the same job.

    `media_probed` is emitted after the probe stream ends but before its process is necessarily
    gone. Starting the download from that callback must wait for release; otherwise `_spawn()`
    replaces the probe in `_sessions`, and the manager loses the only object that can reap it.
    """
    before = {child.pid for child in psutil.Process(os.getpid()).children(recursive=True)}
    repository = FakeRepository()
    repository.add(make_job("job-1", "https://example.invalid/video", tmp_path))
    download = DownloadManager(
        repository,
        concurrency=1,
        probe_concurrency=1,
        entry_point=child_probe_reporting_then_lingering,
    )
    download.start_queue()
    download.media_probed.connect(lambda job_id, _: download.admit(job_id))

    try:
        download.start("job-1", SessionKind.PROBE)
        assert spin(
            lambda: (
                "job-1" in download._sessions
                and download._sessions["job-1"].kind is SessionKind.DOWNLOAD
                and download._sessions["job-1"].process.is_alive()
            ),
            timeout=60,
        ), "the download never started after probing"

        workers = worker_processes(before)
        assert len(workers) == 1, (
            f"{len(workers)} worker processes exist for one job; the probe session was replaced "
            "before its process was released"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)
        assert spin(lambda: not worker_processes(before), timeout=10), (
            "the overwritten probe process survived the test"
        )


def test_start_refuses_a_job_that_already_has_a_session(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T116-R1`: one session per job, whichever lane it is in — and `start()` says so.

    `admit()` parks; `start()` raises, because its caller named a job and asked for a session
    *now*. A mutation deleting this guard survived the whole battery: the reviewer's regression
    reaches the barrier through `admit`, so the raising path had no test of its own.
    """
    repository = FakeRepository()
    queued(repository, "job-1", directory=tmp_path)

    download = DownloadManager(
        repository, concurrency=3, probe_concurrency=3, entry_point=child_downloading_forever
    )
    download.start_queue()
    try:
        download.start("job-1", SessionKind.PROBE)
        assert spin(lambda: "job-1" in download._occupant_ids(), timeout=60)

        with pytest.raises(RuntimeError, match="already has a"):
            download.start("job-1")

        assert download._sessions["job-1"].kind is SessionKind.PROBE, (
            "the refused download replaced the probe session it was refused for"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_staged_job_cannot_be_downloaded(tmp_path: Path, spin: Callable[..., bool]) -> None:
    """`T118-R1`: a staging probe is not queue work, so it has nothing to download.

    It has no row, no `queue_position` and no recovery. Downloading it would produce a file for
    something the user never added — `UX-003`'s whole point — and the durable job Add creates is a
    different id. A mutation deleting this guard survived the battery.
    """
    repository = FakeRepository()
    download = DownloadManager(repository, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        staged = download.stage(make_job("unused", "https://example.invalid/x", tmp_path).request)
        assert download.is_staged(staged)

        with pytest.raises(ValueError, match="staging probe"):
            download.start(staged)

        assert repository.jobs == {}, "a staging probe reached the store"
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_cancelling_a_failed_job_declines_instead_of_raising_out_of_the_state_machine(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T-118`: `FAILED` is not terminal here, so the terminal guard let an illegal write through.

    `FAILED` allows `QUEUED` and nothing else — retry re-enters the queue. `is_terminal(FAILED)` is
    therefore `False`, so `cancel()` computed a cancellation and `Job.with_status` refused it with
    `IllegalTransitionError`, **raised out of a Qt slot**.

    `shutdown()` cancels every occupant, and an occupant can be `FAILED` by the time it gets there
    — which is how this surfaced: a teardown error on the self-hosted desktop runner (run
    `30826638984`), in a test that still reported as passed.

    Driven through the public verb on a durable row, because that is the line `shutdown()` reaches.
    The staging case that found it is the same call with a staged record instead of a durable one;
    `cancel()` cannot tell them apart and must not need to.
    """
    repository = FakeRepository()
    failed = replace(
        make_job("job-1", "https://example.invalid/x", tmp_path),
        status=JobStatus.FAILED,
        error_kind=ErrorKind.UNSUPPORTED_URL,
        error_message="no extractor",
    )
    repository.add(failed)
    download = DownloadManager(repository, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        assert not can_transition(JobStatus.FAILED, JobStatus.CANCELLED), (
            "this test is about an illegal transition and the state machine now allows it"
        )

        download.cancel("job-1")

        assert spin(lambda: download.is_idle, timeout=60)
        assert job_row(repository, "job-1").status is JobStatus.FAILED, (
            "cancelling a failed job moved it"
        )
        assert all(status is not JobStatus.CANCELLED for _, status in repository.writes), (
            "a CANCELLED write was attempted for a job that cannot reach it"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_abandoning_a_failed_staging_probe_leaves_no_durable_trace(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T-118`: the staging case that found the guard above, end to end.

    A staging probe that *fails* still owns its session until the process is reaped, so abandoning
    it in that window is `unstage()` cancelling a `FAILED` job. The window is opened deliberately
    here: the child reports its failure and then lingers.

    This asserts the outcome — the record goes and nothing is written — rather than the absence of
    the exception, because with a live session `cancel()` takes its session branch and never
    reaches the write. **Stated because the first version of this test claimed to cover the
    illegal transition and a mutation showed it did not**; the transition is covered by the test
    above, which reaches the write the way `shutdown()` does.
    """
    repository = FakeRepository()
    download = DownloadManager(repository, entry_point=child_probe_failing_then_lingering)
    download.start_queue()
    try:
        staged = download.stage(make_job("unused", "https://example.invalid/x", tmp_path).request)

        assert spin(
            lambda: (
                download.is_staged(staged) and download._staged[staged].status is JobStatus.FAILED
            ),
            timeout=60,
        ), "the staged probe never reached FAILED"
        # **The child's own failure, not a crash.** `mypy` caught this helper using an unimported
        # `Failed`, which would have crashed the child — and the job would have reached `FAILED`
        # anyway, as `WORKER_CRASH`. The test passed either way until this line existed.
        assert download._staged[staged].error_kind is ErrorKind.UNSUPPORTED_URL, (
            f"the probe failed as {download._staged[staged].error_kind}, not as it was told to"
        )
        assert staged in download._occupant_ids(), "the session was released before the assertion"

        download.unstage(staged)

        assert spin(lambda: not download.is_staged(staged), timeout=60), (
            "the staged record outlived its cancellation"
        )
        assert repository.jobs == {}, "abandoning a staging probe wrote to the store"
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_cancelling_an_id_the_queue_can_no_longer_answer_for_is_a_no_op(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T-118`: `shutdown()` cancels every occupant, and an occupant can outlive its record.

    `cancel()` reached `_require` for an id that is neither staged nor durable and raised
    `KeyError` out of a Qt slot — seen twice on the self-hosted desktop runner (runs
    `30822454998`, `30826638984`), both times in **teardown**, so the tests they hung off still
    reported as passed.

    `cancel()`'s own comment already names this hazard for the *waiting* list and `_discard_waiting`
    handles it there. A reservation reaches it by other routes: a staged job dropped as it is
    abandoned, or a durable row deleted by `T-081`'s clear-finished.

    **The occupant is constructed directly rather than raced into existence.** The race that
    produced it on Windows is not reproducible on demand, and a test that waits for it would be a
    test that passes because the race did not happen. What is asserted here is the property the
    crash violated — cancelling an id the queue cannot answer for asks it to stop something it is
    not doing — which holds whatever produced the id.
    """
    repository = FakeRepository()
    download = DownloadManager(repository, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        orphan = "an-id-with-no-record"
        download._reserved[orphan] = _PendingStart(job_id=orphan, kind=SessionKind.PROBE)
        assert orphan in download._occupant_ids(), "the orphan is not an occupant"
        assert not download._known(orphan), "the orphan has a record after all"

        download.cancel(orphan)
        download.shutdown()

        assert repository.jobs == {}, "cancelling an unknown id wrote to the store"
        assert spin(lambda: download.is_idle, timeout=60)
    finally:
        download.shutdown()


def test_a_saturated_download_lane_no_longer_parks_a_probe(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T-116`: the download lane being full says nothing about whether a probe may start.

    The single download slot is held by a download that never ends. Before separate lanes the
    probe parked behind it and waited for a *download* to finish, which is the delay `UX-003`
    exists to remove — with a limit of three and twenty URLs pasted, the twentieth resolved only
    after the nineteenth had downloaded.

    Asserted on the session's kind rather than only on its presence: a probe that started as a
    download would also be "started".
    """
    repository = FakeRepository()
    queued(repository, "holder", "job-1", directory=tmp_path)

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.start("holder")
        assert spin(lambda: "holder" in download._occupant_ids(), timeout=60)
        assert not download._has_capacity(SessionKind.DOWNLOAD), "the download lane is not full"

        download.start("job-1", SessionKind.PROBE)

        assert download._waiting == [], "the probe was parked behind a full download lane"
        assert download._sessions["job-1"].kind is SessionKind.PROBE
        assert "holder" in download._sessions, (
            "starting a probe disturbed the download already running, which is the whole thing "
            "separate lanes exist to prevent"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_the_probe_lane_has_its_own_ceiling(tmp_path: Path, spin: Callable[..., bool]) -> None:
    """`T-116`: probes are bounded too, and by a number `REQ-013` does not supply.

    **Two, which the default cannot produce.** `DEFAULT_PROBE_CONCURRENCY` is 4 and the download
    limit here is 3, so a lane that ignored its own setting and read either of the others would
    admit a third probe and pass a weaker test. `T-088`'s pool test measured the default for a
    week for exactly this reason.
    """
    repository = FakeRepository()
    queued(repository, "job-1", "job-2", "job-3", directory=tmp_path)

    download = DownloadManager(
        repository, concurrency=3, probe_concurrency=2, entry_point=child_downloading_forever
    )
    download.start_queue()
    try:
        download.start("job-1", SessionKind.PROBE)
        download.start("job-2", SessionKind.PROBE)
        assert spin(lambda: len(download._occupant_ids(SessionKind.PROBE)) == 2, timeout=60)

        with pytest.raises(RuntimeError, match="the probe lane is full at 2"):
            download.start("job-3", SessionKind.PROBE)

        assert download._occupant_ids(SessionKind.PROBE) == ("job-1", "job-2"), (
            "a third probe was admitted past the lane's own ceiling"
        )
        assert download._has_capacity(SessionKind.DOWNLOAD), (
            "two probes consumed the download lane, which is the defect this task is about"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_probes_beyond_the_lane_queue_in_queue_order_rather_than_being_refused(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T-116`: a pasted batch expresses intent, so the surplus waits rather than being dropped.

    `start()` raises when a lane is full, and is right to — its caller asked for a session now.
    `admit()` is the durable-intent door and `T-116` gave it a kind, because the only public route
    to a probe used to be the one that raises. A user pasting twenty URLs should no more have to
    decide which probes to drop than a user adding twenty downloads.

    **Admitted out of queue order on purpose.** The two surplus probes are admitted highest
    position first, so a scheduler that ran them in arrival order would pass a test that only
    counted them.
    """
    repository = FakeRepository()
    queued(repository, "job-1", "job-2", "job-3", directory=tmp_path)

    download = DownloadManager(
        repository, concurrency=3, probe_concurrency=1, entry_point=child_downloading_forever
    )
    download.start_queue()
    try:
        download.admit("job-1", SessionKind.PROBE)
        assert spin(lambda: "job-1" in download._occupant_ids(SessionKind.PROBE), timeout=60)

        download.admit("job-3", SessionKind.PROBE)
        download.admit("job-2", SessionKind.PROBE)

        assert sorted(download._waiting) == ["job-2", "job-3"], (
            "a probe beyond the lane's ceiling was refused instead of queued"
        )
        assert download._next_startable() is None, "the full probe lane admitted another probe"
        assert download._next_waiting() == "job-2", (
            "the surplus probes would start in the order they were asked for rather than in "
            "queue_position order, which is the only order that survives a restart"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_waiting_download_does_not_hold_up_a_waiting_probe(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T-116`: the fill loop takes the next job it *can* start, not the next job.

    Both lanes are saturated and both a download and a probe are waiting, with the **download at
    the lower queue position**. Freeing the probe lane must start the probe, stepping over a
    download whose own lane is still full. The loop used to stop at the first job it could not
    start — correct with one budget, and with two it makes a probe wait for a download to finish
    all over again.

    An earlier version parked both behind **pause** and resumed. That stopped proving anything
    when pause became kind-aware for `UX-003`: a paused queue admits probes, so the probe never
    reached the waiting list and the fill loop was never the thing that started it. Saturating the
    lane is the only way to park a probe, and therefore the only way to test this.
    """
    repository = FakeRepository()
    queued(
        repository,
        "holder-download",
        "holder-probe",
        "waiting-download",
        "job-probe",
        directory=tmp_path,
    )

    download = DownloadManager(
        repository, concurrency=1, probe_concurrency=1, entry_point=child_downloading_forever
    )
    download.start_queue()
    try:
        download.start("holder-download")
        download.start("holder-probe", SessionKind.PROBE)
        assert spin(lambda: len(download._occupant_ids()) == 2, timeout=60)

        download.admit("waiting-download")
        download.admit("job-probe", SessionKind.PROBE)
        assert download._waiting == ["waiting-download", "job-probe"], "both should be parked"

        download.cancel("holder-probe")

        assert spin(lambda: "job-probe" in download._sessions, timeout=60), (
            "the probe was stuck behind a waiting download it shares no budget with"
        )
        assert download._sessions["job-probe"].kind is SessionKind.PROBE
        assert "waiting-download" in download._waiting, (
            "the download started while its own lane was still full"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_paused_queue_still_reads_urls(tmp_path: Path, spin: Callable[..., bool]) -> None:
    """`UX-001`, `T080-R1`, `UX-003`: pause stops downloads, not reading.

    `start()` has admitted a probe on a paused queue since `T080-R1`. `admit()` did not, which was
    invisible while probing was a button nobody pressed on a paused queue — and immediately fatal
    once `UX-003` made the add dialog probe through `admit`: every pasted URL stayed unread and
    the dialog had nothing it could ever offer to queue. The phase proof found it by hanging.

    Both halves asserted together, because the rule is a distinction: the probe starts **and** the
    download does not. A pause that stopped nothing would pass half of this.
    """
    repository = FakeRepository()
    queued(repository, "to-read", "to-download", directory=tmp_path)

    download = DownloadManager(repository, concurrency=2, entry_point=child_downloading_forever)
    download.start_queue()
    try:
        download.stop_queue()

        download.admit("to-read", SessionKind.PROBE)
        download.admit("to-download")

        assert spin(lambda: "to-read" in download._sessions, timeout=60), (
            "a paused queue refused to read a URL, which is not the work pause exists to stop"
        )
        assert download._sessions["to-read"].kind is SessionKind.PROBE
        assert download._waiting == ["to-download"], (
            "a paused queue started a download, which is exactly the work it exists to stop"
        )
        assert "to-download" not in download._sessions
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_cancelling_a_queued_probe_stops_it_ever_starting(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T-116`, `T-103`: closing the dialog must not leave a lane full of unwanted probes.

    A probe waiting for a lane has no process to kill, so cancelling it is a bookkeeping question
    rather than a lifecycle one — and `T-103` is what happens when the id is left on the waiting
    list: the next free slot picks it up and `start()` refuses a job that is already cancelled.

    Asserted by freeing the lane afterwards and finding nothing started, rather than by reading the
    waiting list alone. A list this test cleared and then never drained would prove nothing.
    """
    repository = FakeRepository()
    queued(repository, "holder", "job-1", directory=tmp_path)

    download = DownloadManager(
        repository, concurrency=3, probe_concurrency=1, entry_point=child_downloading_forever
    )
    download.start_queue()
    try:
        download.start("holder", SessionKind.PROBE)
        assert spin(lambda: "holder" in download._occupant_ids(SessionKind.PROBE), timeout=60)
        download.admit("job-1", SessionKind.PROBE)
        assert download._waiting == ["job-1"], "the probe was not queued"

        download.cancel("job-1")

        assert download._waiting == [], "the cancelled probe kept its claim on the lane"
        download.cancel("holder")
        assert spin(lambda: not download._occupant_ids(SessionKind.PROBE), timeout=60)
        assert "job-1" not in download._sessions, (
            "the cancelled probe started anyway once the lane freed, which is T-103's shape"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_shutdown_drains_both_lanes(tmp_path: Path, spin: Callable[..., bool]) -> None:
    """`T-116`, `ARC-002`: no worker of either kind outlives the application.

    `is_idle` is the whole-manager answer, so this asserts the lanes are empty *by kind* as well —
    an accounting split that only ever adds could report idle while one lane still held a session.
    """
    repository = FakeRepository()
    queued(repository, "downloading", "probing", directory=tmp_path)

    download = DownloadManager(
        repository, concurrency=1, probe_concurrency=1, entry_point=child_downloading_forever
    )
    download.start_queue()
    download.start("downloading")
    download.start("probing", SessionKind.PROBE)
    assert spin(lambda: len(download._occupant_ids()) == 2, timeout=60)

    download.shutdown()

    assert spin(lambda: download.is_idle, timeout=60)
    assert download._occupant_ids(SessionKind.DOWNLOAD) == ()
    assert download._occupant_ids(SessionKind.PROBE) == ()


# --- T-117: the probe's thumbnail URL reaches the row -------------------------------------------


def child_probing_with_a_thumbnail(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """A probe that resolves a title **and** an address for the picture."""
    from tracks_and_trails.core.models import MediaInfo

    queue.put(
        Probed(
            job_id=job_id,
            media=MediaInfo(
                url="https://example.invalid/x",
                title="Trail running in the Cairngorms",
                thumbnail_url="https://example.invalid/thumb.jpg",
            ),
        )
    )
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))
    queue.close()
    queue.join_thread()


def child_probing_without_a_thumbnail(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """A probe against a site that offers no thumbnail at all."""
    from tracks_and_trails.core.models import MediaInfo

    queue.put(
        Probed(
            job_id=job_id,
            media=MediaInfo(url="https://example.invalid/x", title="No picture here"),
        )
    )
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))
    queue.close()
    queue.join_thread()


def test_a_probe_stores_the_thumbnail_url_in_the_same_revision_as_the_title(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T-117`: the address survives the dialog that asked for it.

    `MediaInfo` has carried a thumbnail URL since `T-016` and nothing stored it, so a queued row
    could show a title and never a picture. Both fields arrive in one `Probed` message and are
    written in one revision — asserted on the *number of writes* as well as their content, because
    a second write for the thumbnail could fail on its own and leave a row that knows what it is
    called but not what it looks like.
    """
    repository = FakeRepository()
    queued(repository, "job-1", directory=tmp_path)

    download = DownloadManager(repository, entry_point=child_probing_with_a_thumbnail)
    download.start_queue()
    try:
        download.start("job-1", SessionKind.PROBE)
        assert spin(lambda: repository.jobs["job-1"].status is JobStatus.READY, timeout=60)

        stored = repository.jobs["job-1"]
        assert stored.title == "Trail running in the Cairngorms"
        assert stored.thumbnail_url == "https://example.invalid/thumb.jpg"
        assert repository.statuses("job-1") == [JobStatus.PROBING, JobStatus.READY], (
            "the thumbnail took a revision of its own, which is a write that can half-land"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_probe_that_found_no_thumbnail_stores_null(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T-117`: "the site offered none" is an answer, and it is recorded as one.

    The row is `READY`, so it *has* been probed — which is what distinguishes this `None` from the
    `None` an unprobed job carries. `T-119` draws the placeholder either way and must never draw
    an error: a missing picture is not a failed download.
    """
    repository = FakeRepository()
    queued(repository, "job-1", directory=tmp_path)

    download = DownloadManager(repository, entry_point=child_probing_without_a_thumbnail)
    download.start_queue()
    try:
        download.start("job-1", SessionKind.PROBE)
        assert spin(lambda: repository.jobs["job-1"].status is JobStatus.READY, timeout=60)

        stored = repository.jobs["job-1"]
        assert stored.thumbnail_url is None
        assert stored.title == "No picture here", "a probe with no thumbnail lost its title too"
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_a_durable_probe_carries_the_job_on_into_its_download(
    app: QCoreApplication, tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`T137-R2` / `ARC-009`: probing a durable row is not the end of that row's journey.

    `admit()` schedules one session and has never chained, which was complete while the only probe
    in the system was a staging probe. `T-137`'s playlist entries are durable `QUEUED` rows, so
    admitting them as probes without a continuation would leave every entry of a playlist probed
    and then permanently parked — trading one broken promise for another.
    """
    repository = FakeRepository()
    queued(repository, "job-1", directory=tmp_path)
    download = DownloadManager(
        repository, concurrency=1, entry_point=child_probe_reporting_then_lingering
    )
    download.start_queue()
    try:
        download.admit("job-1", SessionKind.PROBE)

        def status_of(job_id: str) -> JobStatus | None:
            job = repository.get(job_id)
            return job.status if job is not None else None

        assert spin(lambda: status_of("job-1") is JobStatus.RUNNING), (
            f"job-1 settled at {status_of('job-1')}; a probed durable row must go on to download, "
            "or UX-003's probe-first rule simply strands it"
        )
    finally:
        # **`drain`, not `shutdown()` alone** (`T-128`, `T137-R3`). This test runs *two* sessions
        # in sequence — the probe, then the download the continuation admits — and returning while
        # the second pump was still live had Qt destroy a running `QThread`, aborting the
        # interpreter: 143 passed, exit 134. `is_idle` is not enough either; it answers a question
        # about the queue and goes true up to one poll interval before the tick that stops the
        # manager's own timer, which is the whole of `T-128`.
        download.shutdown()
        drain(app, [download])


def test_a_staged_probe_does_not_start_a_download(
    app: QCoreApplication, tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """The discriminator `ARC-009` turns on, asserted rather than assumed.

    A staging probe exists so the add dialog can show the user what they pasted **before** anything
    is committed. Continuing it into a download would start the very thing the dialog is asking
    about — and would do it while the user is still looking at the row.
    """
    repository = FakeRepository()
    download = DownloadManager(
        repository, concurrency=1, entry_point=child_probe_reporting_then_lingering
    )
    download.start_queue()
    try:
        probed: list[str] = []
        download.media_probed.connect(lambda job_id, _media: probed.append(job_id))

        staged_id = download.stage(
            make_job("unused", "https://example.invalid/clip", tmp_path).request
        )

        assert spin(lambda: probed == [staged_id]), "the staging probe never reported"

        # The continuation runs inside the same `then` as that signal, so by the time it has
        # fired the decision not to download has already been taken or missed.
        assert repository.get(staged_id) is None, (
            "a staged row reached the durable store; staging is deliberately not persistence"
        )
        kinds = [session.kind for session in download._sessions.values()]
        assert SessionKind.DOWNLOAD not in kinds, (
            f"sessions {kinds}; a staging probe started a download, so the add dialog began "
            "fetching the very thing it was still asking the user about"
        )

        # **Why the guard is a guard and not decoration.** Without it the continuation admits a
        # staged id, and `admit()` does not refuse that outright -- `_start_when_free` *parks* it
        # while the probe still holds the job. The refusal (`start()`'s `ValueError`) then arrives
        # later, on drain, from a timer's thread of control. So the damage is a deferred exception
        # rather than a visible one, which is precisely why the queue state is asserted here
        # rather than the call being expected to throw.
        assert staged_id not in download._waiting, (
            f"waiting {download._waiting}; a staging probe parked a download for a row that has "
            "no queue position and no recovery, and start() will raise for it on drain"
        )
    finally:
        download.shutdown()
        drain(app, [download])


# --- T-113: removing a job ends its partial's life (REQ-017, UX-008) --------------------------


def test_removing_a_job_discards_the_partial_it_was_keeping(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`UX-008`'s table: discarded on remove, and **only** this job's own bytes.

    Since `T-113` a failed attempt deliberately keeps its `.part` so the retry has a head start.
    Removing the row is the user saying there will be no retry — and the row is the only thing
    that could ever have explained the directory, so leaving it makes an invisible partial in the
    user's download folder.

    The neighbouring job's partial is asserted alongside, because a cleanup keyed on anything
    looser than the job id would take it too, and `remove` is a per-job verb.
    """
    outputs = tmp_path / "downloads"
    outputs.mkdir()
    repository = FakeRepository()
    queued(repository, "job-1", "job-2", directory=outputs)

    for job_id in ("job-1", "job-2"):
        staging = worker.staging_directory(outputs, job_id)
        staging.mkdir()
        (staging / "Clip.mp4.part").write_bytes(b"half a download")
    keepsake = outputs / "something the user already had.mp4"
    keepsake.write_bytes(b"not ours to delete")

    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    removed: list[str] = []
    download.job_removed.connect(removed.append)
    try:
        download.remove("job-2")
        assert spin(lambda: removed == ["job-2"], timeout=10)

        assert worker.resumable_partial(outputs, "job-2") is None, (
            "the removed job left its partial behind, with no row left to explain it"
        )
        assert worker.resumable_partial(outputs, "job-1") is not None, (
            "removing one job discarded another's partial"
        )
        assert keepsake.read_bytes() == b"not ours to delete", (
            "the cleanup reached outside this job's own directory (UX-001)"
        )
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)


def test_removing_a_job_that_never_ran_is_not_an_error(
    tmp_path: Path, spin: Callable[..., bool]
) -> None:
    """`remove` is called from routes that cannot know whether a job ever downloaded anything."""
    outputs = tmp_path / "downloads"
    outputs.mkdir()
    repository = FakeRepository()
    queued(repository, "job-1", directory=outputs)
    download = DownloadManager(repository, concurrency=1, entry_point=child_downloading_forever)
    removed: list[str] = []
    download.job_removed.connect(removed.append)
    try:
        download.remove("job-1")
        assert spin(lambda: removed == ["job-1"], timeout=10)
    finally:
        download.shutdown()
        assert spin(lambda: download.is_idle, timeout=60)
