"""`T-038`: a real worker's diagnostics reach the parent's log, redacted (`REQ-026`).

The unit tests prove the queue handler and the formatter separately. This proves the thing the
acceptance criterion actually names — that a **spawned** worker's line lands in the application's
log file with the credential gone — against a real process, a real queue and a real file
(`ai/TESTING.md` §6: the process boundary is not mocked).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QCoreApplication

from tests.integration.test_manager import FakeRepository, make_job
from tracks_and_trails.core import logging as app_logging
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.downloader.protocol import Succeeded, WorkerFinished

#: Shaped like a real signed-URL parameter, and unmistakable in a diff if it ever escapes.
TOKEN = "sk-live-7c6c-must-not-appear"  # noqa: S105 - a marker, not a secret

#: How long a gated handler holds the listener before giving up. Long enough that a teardown
#: which forgets to release it is a clear failure, short enough that the run still ends.
GATE_SECONDS = 5.0


class GatedHandler(logging.Handler):
    """A handler that parks the listener thread inside `emit` until it is let go.

    This is the reviewer's probe, made into a fixture. Delaying the listener is what separates
    "the per-job log happened to be written first" from "the per-job log is written because the
    ordering is established" — and, for shutdown, what turns a join on the GUI thread from an
    invisible cost into a measurable one.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.entered = threading.Event()
        self.left = threading.Event()
        self.let_go = threading.Event()

    def emit(self, record: logging.LogRecord) -> None:
        self.entered.set()
        self.let_go.wait(GATE_SECONDS)
        self.left.set()


def quiet_the_logging() -> None:
    """Stop the process-wide listener, **wait for it**, and take the handlers down.

    The waiting is the point and it is a test's job rather than the application's: production
    stops the listener without joining it (`T038-R2`), so a teardown that did not wait could let
    a thread from this test dispatch a record into the next test's handlers.
    """
    app_logging.stop_listening_for_worker_logs()
    assert app_logging.wait_for_the_log_listener_to_stop(30.0), (
        "the worker-log listener thread never returned"
    )
    tree = logging.getLogger("tracksandtrails")
    for handler in list(tree.handlers):
        tree.removeHandler(handler)
        handler.close()


def a_worker_that_logs(kind: Any, job_id: str, request: Any, queue: Any, **kwargs: Any) -> None:
    """A real spawned child that logs a tokenised URL and then finishes its session.

    Deliberately **not** formatting anything itself: it calls `prepare_this_worker`, which is
    what production calls, and lets the record travel. That is the property under test — a worker
    cannot emit an unredacted line because it does not do the rendering.
    """
    from tracks_and_trails.downloader import worker

    worker.prepare_this_worker(kwargs.get("log_queue"))
    logging.getLogger("tracksandtrails.worker").warning(
        "probing https://example.invalid/v?token=%s", TOKEN
    )
    queue.put(Succeeded(job_id=job_id, output_path="/written/clip.mp4", total_bytes=1))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))


def test_a_spawned_workers_line_reaches_the_parents_log_without_its_token(
    tmp_path: Path, qapp: QCoreApplication
) -> None:
    repository = FakeRepository()
    repository.add(make_job("job-1", "https://example.invalid/clip", tmp_path))
    log_path = app_logging.configure_logging(directory=tmp_path, level=logging.DEBUG)
    download = DownloadManager(repository, entry_point=a_worker_that_logs)

    try:
        download.start("job-1")
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and not download.is_idle:
            qapp.processEvents()
            time.sleep(0.05)

        # The listener is a thread draining a queue; the record is in flight, not lost.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and "probing" not in log_path.read_text("utf-8"):
            qapp.processEvents()
            time.sleep(0.05)
        for handler in logging.getLogger("tracksandtrails").handlers:
            handler.flush()
        written = log_path.read_text("utf-8")
    finally:
        quiet_the_logging()

    assert "probing" in written, (
        f"the worker's line never reached the parent's log. Written:\n{written}"
    )
    assert "example.invalid" in written, "the diagnostic lost the address it was about"
    assert TOKEN not in written, (
        "the worker's token reached the log file. Records travel unformatted so the parent's "
        "handlers redact them; if this fails, something formatted in the child."
    )


def a_worker_logging_its_own_id(
    kind: Any, job_id: str, request: Any, queue: Any, **kwargs: Any
) -> None:
    """A worker that says which job it is, so a crossed line names the file it should not be in."""
    from tracks_and_trails.downloader import worker

    worker.prepare_this_worker(kwargs.get("log_queue"), kwargs.get("log_job_id"))
    logging.getLogger("tracksandtrails.worker").warning("this line belongs to %s", job_id)
    queue.put(Succeeded(job_id=job_id, output_path="/written/clip.mp4", total_bytes=1))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))


def test_two_jobs_cannot_write_into_each_others_logs(
    tmp_path: Path, qapp: QCoreApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T038-R2`: a per-job log holds **that** job, or it is not a per-job log.

    The isolation is the whole claim. Attaching a file handler to the application logger without
    it would give every open job a copy of every worker's output the moment Phase 2 allows two at
    once — a file that looks authoritative and is not. Phase 1 runs one session at a time, so the
    two jobs here run in sequence; what is asserted is that the *routing* is per job, which is the
    property that has to hold before concurrency arrives rather than after.
    """
    monkeypatch.setattr(
        app_logging,
        "job_log_path",
        lambda job_id, directory=None: tmp_path / "jobs" / f"{job_id}.log",
    )
    app_logging.configure_logging(directory=tmp_path, level=logging.DEBUG)
    repository = FakeRepository()

    try:
        for job_id in ("job-alpha", "job-beta"):
            repository.add(make_job(job_id, "https://example.invalid/clip", tmp_path))
            download = DownloadManager(repository, entry_point=a_worker_logging_its_own_id)
            download.start(job_id)
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and not download.is_idle:
                qapp.processEvents()
                time.sleep(0.05)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                path = tmp_path / "jobs" / f"{job_id}.log"
                if path.exists() and job_id in path.read_text("utf-8"):
                    break
                qapp.processEvents()
                time.sleep(0.05)
            download.shutdown()
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and not download.is_idle:
                qapp.processEvents()
                time.sleep(0.05)

        alpha = (tmp_path / "jobs" / "job-alpha.log").read_text("utf-8")
        beta = (tmp_path / "jobs" / "job-beta.log").read_text("utf-8")
    finally:
        quiet_the_logging()

    assert "job-alpha" in alpha, f"job-alpha's own line is missing from its log: {alpha!r}"
    assert "job-beta" in beta, f"job-beta's own line is missing from its log: {beta!r}"
    assert "job-beta" not in alpha, (
        f"job-beta's output was written into job-alpha's log: {alpha!r}. A per-job log whose "
        "contents depend on which other jobs were open is worse than none."
    )
    assert "job-alpha" not in beta, f"job-alpha's output leaked into job-beta's log: {beta!r}"


def test_a_records_late_arrival_still_reaches_the_job_it_belongs_to(
    tmp_path: Path,
    qapp: QCoreApplication,
    spin: Callable[..., bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`T038-R2`: the per-job handler outlives the session until the log queue has caught up.

    **The two queues are the defect.** Results and log records travel separately, and only the
    result queue tells the manager the session is over. So the worker's last line can still be in
    the log queue when `WorkerFinished` has already been read, the session released and — in the
    version this test was written against — the per-job handler closed. The line then reached the
    application log alone and the per-job file, the one a user is pointed at, stayed empty.

    Nothing here is timed. The gate holds the listener inside a handler until this test lets go,
    so "the record was still in flight when the session was released" is established rather than
    hoped for, and releasing it afterwards is what proves the handler was still there to catch it.
    """
    monkeypatch.setattr(
        app_logging,
        "job_log_path",
        lambda job_id, directory=None: tmp_path / "jobs" / f"{job_id}.log",
    )
    app_logging.configure_logging(directory=tmp_path, level=logging.DEBUG)
    gate = GatedHandler()
    # After the application's own handler and before the session's, which is the order that made
    # the reviewer's probe fail the way it did: the line reached the application log, and the
    # per-job handler was gone by the time the loop got to it.
    tree = logging.getLogger("tracksandtrails")
    tree.addHandler(gate)
    before = list(tree.handlers)
    repository = FakeRepository()
    repository.add(make_job("job-late", "https://example.invalid/clip", tmp_path))
    download = DownloadManager(repository, entry_point=a_worker_logging_its_own_id)
    job_log = tmp_path / "jobs" / "job-late.log"

    try:
        download.start("job-late")
        assert spin(gate.entered.is_set, 60.0), "the worker's record never reached the listener"
        assert spin(lambda: download.is_idle, 60.0), (
            "the session never finished, so nothing was released while the record was held"
        )
        assert not gate.left.is_set(), "the gate let the record through early; it proved nothing"

        gate.let_go.set()
        arrived = spin(lambda: job_log.exists() and "job-late" in job_log.read_text("utf-8"), 30.0)
        # And then it goes. Staying attached is what the drain is for; staying attached *after*
        # the drain would be a per-job file handle living as long as the process.
        handed_back = spin(lambda: list(tree.handlers) == before, 30.0)
    finally:
        gate.let_go.set()
        download.shutdown()
        spin(lambda: download.is_idle, 30.0)
        quiet_the_logging()

    assert arrived, (
        "the worker's line never reached its own log. It was still in the log queue when the "
        f"session was released, and the per-job handler was closed before it arrived: "
        f"{job_log.read_text('utf-8') if job_log.exists() else '<no file at all>'!r}"
    )
    assert handed_back, (
        "the drained per-job handler was never taken off the application's logger, so its file "
        "stays open for the rest of the process"
    )


def test_shutdown_does_not_wait_for_a_blocked_log_listener(
    tmp_path: Path, qapp: QCoreApplication
) -> None:
    """`T013-R2` again, through the logging correction: teardown must not join a listener thread.

    `QueueListener.stop()` joins, and `shutdown()` runs on the GUI thread — so one slow handler
    call held the whole teardown for as long as it lasted. The reviewer measured 2.001 s against
    a two-second delay, which is the same blocking teardown `T013-R2` rejected, with log I/O in
    place of a process wait.

    The bound is deliberately loose and the real assertion is the one beside it: `shutdown()`
    returned **while the handler was still inside `emit`**. A version that joins cannot do that,
    whatever the timings on the machine happen to be.
    """
    app_logging.configure_logging(directory=tmp_path, level=logging.DEBUG)
    gate = GatedHandler()
    logging.getLogger("tracksandtrails").addHandler(gate)
    download = DownloadManager(FakeRepository())

    try:
        app_logging.worker_log_queue().put(
            logging.LogRecord(
                name="tracksandtrails.worker",
                level=logging.WARNING,
                pathname=__file__,
                lineno=1,
                msg="a line the listener is about to get stuck on",
                args=None,
                exc_info=None,
            )
        )
        assert gate.entered.wait(30.0), "the listener never picked the record up"

        started = time.monotonic()
        download.shutdown()
        elapsed = time.monotonic() - started
        still_blocked = not gate.left.is_set()
    finally:
        gate.let_go.set()
        quiet_the_logging()

    assert still_blocked, (
        f"the handler had already returned after {elapsed:.3f} s, so this run proved nothing "
        "about whether shutdown waited for it"
    )
    assert elapsed < 1.0, (
        f"shutdown() took {elapsed:.3f} s while a log handler was blocked. It joined the "
        "listener thread on the GUI thread, which is the teardown wait T013-R2 rejected."
    )


def test_a_job_id_never_chooses_its_own_path(tmp_path: Path) -> None:
    """`T038-R2`: `Job.id` is any non-empty string, so it is sanitised rather than trusted."""
    escaping = app_logging.job_log_path("../../etc/passwd", tmp_path)

    assert escaping.parent == tmp_path / "jobs", (
        f"a job id chose its own directory: {escaping}. Every id this application makes is a "
        "UUID, but the type permits anything, and core/paths.py exists for exactly this."
    )
    # The dots survive as *characters* and that is fine — what matters is that no separator
    # does, so the name cannot be more than one component and cannot climb out.
    assert "/" not in escaping.name and "\\" not in escaping.name, escaping.name
    assert escaping.resolve().is_relative_to((tmp_path / "jobs").resolve())
