"""Worker process pool, scheduling, and Qt signals. Runs in the GUI process.

The GUI-process half of `ARC-002`: it starts a worker per job, tracks its lifetime, cancels it,
reaps it, turns what the worker says into persisted job state, and turns a worker that died
without saying anything into `WORKER_CRASH` (`REQ-028`).

This is the one `downloader/` module allowed to import Qt, because it emits signals.
`worker.py` still may not — it runs in the child.

## A pool of exactly one

Concurrency is Phase 2. Building a pool for N now would mean designing scheduling policy with
no queue to test it against, so `start()` refuses while a session is running and the "pool" is a
dictionary that happens to hold at most one entry. The shape is kept because the lifetime rules
below are per-session and do not become simpler by being written for a single global.

## Persistence is injected, never imported

`ARCHITECTURE.md` §3 gives `DownloadManager` a repository, and Phase 1 promises durable
transitions — but this module must not know SQLite exists. It takes `JobStore`, a protocol with
the two operations it actually uses, and `app.py` hands it the real `JobRepository` at
composition time (`T-036`). A test asserts that no `persistence` import ever appears here, so
the boundary cannot quietly collapse into a direct dependency.

## Everything decided on the GUI thread

`ResultPump` emits; this object decides. Every slot below, and every tick of `_timer`, runs on
the GUI thread, which is what makes the session bookkeeping safe without a single lock — and
what keeps `ARCHITECTURE.md` §8's rule that Qt objects are touched only on the GUI thread.

Nothing here blocks it. Process liveness is polled with `is_alive()`, cancellation escalates on
timer ticks, and no method waits on a worker — with one deliberate exception, `shutdown()`,
which is documented at its own definition.

## What the parent guarantees the pump

**A sentinel always arrives.** A worker that is killed, or that exits without sending
`WorkerFinished`, leaves `ResultPump` blocked in `Queue.get()` forever unless somebody ends the
stream for it. So on reaping a process whose stream has not ended, this module puts a
`WorkerFinished` carrying the real exit code onto that session's queue. `validate_sequence()`
then does the rest: a session with no outcome is a violation, and the job fails as
`WORKER_CRASH` rather than looking like a success nobody reported.

## `entry_point`

The function the child runs is a constructor parameter, defaulting to `worker.spawn_session`.
It is not a mocking seam — `ai/TESTING.md` §6 forbids mocking the process boundary, and the
tests that use it spawn a *real* process over a *real* queue. It exists because the streams the
receiving half has to survive are ones a correct worker cannot produce: two outcomes for one
job, a bare dict on the queue, an exit with nothing reported. Without it those paths could only
be tested by breaking the worker.

## The exit code is not the outcome

The naive lifetime check is "the process exited non-zero, so the job failed", and it is wrong in
both directions. A worker that reports `Succeeded` and then dies during interpreter shutdown
produced a file; a worker that exits 0 having reported nothing did not. So the **message**
decides whenever there is one, and the exit code decides only when there is not.
"""

import multiprocessing
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Protocol

from PySide6.QtCore import QObject, QTimer, Signal

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import Job
from tracks_and_trails.downloader import worker
from tracks_and_trails.downloader.protocol import (
    Failed,
    Probed,
    Progress,
    ResolutionReport,
    SessionKind,
    Stage,
    Succeeded,
    WorkerFinished,
)
from tracks_and_trails.downloader.result_pump import ResultPump

#: How often process liveness and cancellation deadlines are checked. Fifty milliseconds is
#: below `NFR-001`'s ~100 ms interaction budget, so an escalation never *adds* a perceptible
#: delay, and it costs one `is_alive()` per tick per running job.
DEFAULT_POLL_INTERVAL_MS: Final = 50

#: `REQ-015`: cancel must terminate the underlying work promptly. The two grace periods below
#: are the cooperative and the polite phases; together with the poll interval they must fit
#: inside this, because this is the number the acceptance criterion measures.
CANCEL_BUDGET_SECONDS: Final = 2.0

#: How long the worker is given to notice the cancel event and unwind through yt-dlp, leaving
#: partial files in a known state, before `terminate()` is issued.
DEFAULT_COOPERATIVE_SECONDS: Final = 1.0

#: How long `terminate()` (`SIGTERM`) is given before `kill()` (`SIGKILL`). A worker that is
#: wedged in a C extension will not handle either; this is the window in which Python-level
#: cleanup can still run.
DEFAULT_TERMINATE_SECONDS: Final = 0.5

#: A worker that has sent its sentinel is finished by definition. If its process is somehow
#: still there after this long, it is stopped — an exited stream and a live process is exactly
#: the shape an orphan has.
DEFAULT_REAP_SECONDS: Final = 5.0

#: The bound on `shutdown()`. Long enough for a cancel budget plus the reaping that follows it.
DEFAULT_SHUTDOWN_SECONDS: Final = 5.0

#: The pipeline states, in order, transcribed by hand from `ARCHITECTURE.md` §5's diagram
#: rather than derived from `core.job_state` — the two must agree, and a walker that read the
#: transition table to find its own path would agree with it unconditionally (`ai/TESTING.md`
#: §13). Every step is still validated by `Job.with_status`, so a wrong entry here raises
#: `IllegalTransitionError` instead of writing a state the machine forbids.
_PIPELINE: Final[tuple[JobStatus, ...]] = (
    JobStatus.QUEUED,
    JobStatus.PROBING,
    JobStatus.READY,
    JobStatus.RUNNING,
    JobStatus.POST_PROCESSING,
    JobStatus.COMPLETED,
)

#: Which pipeline state each reported stage means the job has reached (`REQ-014`).
#:
#: `PROBING` is absent deliberately: `start()` has already moved the job there, and mapping it
#: would make an ordinary probe progress message look like a transition every time it arrived.
_STAGE_STATUS: Final[dict[Stage, JobStatus]] = {
    Stage.DOWNLOADING_VIDEO: JobStatus.RUNNING,
    Stage.DOWNLOADING_AUDIO: JobStatus.RUNNING,
    Stage.MERGING: JobStatus.POST_PROCESSING,
    Stage.POST_PROCESSING: JobStatus.POST_PROCESSING,
}


class JobStore(Protocol):
    """The persistence the manager needs, and nothing more.

    Two operations, named as a protocol so this module depends on the *shape* of a repository
    rather than on `persistence.JobRepository`. `JobRepository` satisfies it structurally; so
    does a dictionary-backed fake in a test, which is the point (`ARCHITECTURE.md` §3).
    """

    def get(self, job_id: str) -> Job | None: ...

    def update(self, job: Job) -> None: ...


class ProcessLike(Protocol):
    """The `multiprocessing.Process` surface used here.

    Named so the manager's lifetime handling can be driven by a stand-in in a test without
    weakening what the real thing has to do. The integration tests use real processes
    (`ai/TESTING.md` §6); this exists for the parts that are about *policy* — which escalation
    happens when — rather than about the process model.
    """

    @property
    def exitcode(self) -> int | None: ...

    def is_alive(self) -> bool: ...

    def start(self) -> None: ...

    def join(self, timeout: float | None = None) -> None: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...


@dataclass
class _Session:
    """One worker process and everything the manager knows about its lifetime.

    Mutable and lock-free on purpose: it is only ever touched on the GUI thread.
    """

    job_id: str
    kind: SessionKind
    process: ProcessLike
    queue: Any
    cancel: Any
    pump: ResultPump

    #: Whether `Process.start()` actually returned. `join()` on an unstarted process raises, and
    #: the one path that gets here without a live child is a spawn that failed outright.
    started: bool = False

    #: Set when the user asks to cancel. It changes what "no outcome" means at the end of the
    #: session: a job the user stopped is `CANCELLED`, not a crash.
    cancelling: bool = False

    #: Monotonic deadlines for the two escalation steps, set when cancellation starts.
    terminate_at: float | None = None
    kill_at: float | None = None
    terminated: bool = False
    killed: bool = False

    #: The outcome message, if one arrived. `None` here at the end of a session is what
    #: `REQ-028` calls a crash.
    outcome: Probed | Succeeded | Failed | None = None
    exit_code: int | None = None

    #: Set once the stream has ended, and once the pump thread has actually returned. They are
    #: different moments: the thread emits `session_ended` from inside `run()`.
    ended: bool = False
    pump_finished: bool = False
    sentinel_sent: bool = False
    reap_at: float | None = None

    #: Set when the session has been stopped by force. `abandon_at` bounds how long the pump
    #: thread is given to notice, so nothing has to wait for it (`T013-R2`). `abandoned` records
    #: that `terminate()` has already been issued — it is a request, not an event, so the
    #: session is still owned until the thread reports itself finished (`T013-R4`).
    forced: bool = False
    abandoned: bool = False
    abandon_at: float | None = None

    violations: list[str] = field(default_factory=list)
    finalized: bool = False


class DownloadManager(QObject):
    """Starts, watches, cancels and reaps worker processes, and persists what they report."""

    #: `(job_id, status)` — a persisted state change. Emitted **after** the write, so a slot
    #: that reads the repository never sees a state older than the one it was told about.
    job_changed = Signal(str, str)

    #: `protocol.Progress`, forwarded as-is (`REQ-014`). Not persisted per message: a progress
    #: update every few hundred milliseconds per job is an unbounded write rate for a fact that
    #: is worthless after a crash, and crash recovery re-queues the job anyway (`T-014`).
    progress = Signal(object)

    #: `(job_id, MediaInfo)` — a probe session's result.
    media_probed = Signal(str, object)

    #: `protocol.ResolutionReport` — which yt-dlp ran, and what it rejected (`REQ-025`).
    resolution_reported = Signal(object)

    #: `(job_id, output_path)`.
    job_succeeded = Signal(str, str)

    #: `(job_id, ErrorKind, message)`. Carries the kind separately from the text because retry
    #: policy is decided from the kind (`REQ-018`) and the text is shown verbatim (`NFR-006`).
    job_failed = Signal(str, object, str)

    #: `(job_id, reason)` — the worker broke the IPC contract. Surfaced rather than swallowed;
    #: `ai/REVIEWS.md` has this class of fault ending in a hang when it is not.
    protocol_violation = Signal(str, str)

    #: Emitted when the last session has been released. `T-036` uses it to know that quitting
    #: is safe.
    idle = Signal()

    def __init__(
        self,
        repository: JobStore,
        *,
        parent: QObject | None = None,
        poll_interval_ms: int = DEFAULT_POLL_INTERVAL_MS,
        cooperative_seconds: float = DEFAULT_COOPERATIVE_SECONDS,
        terminate_seconds: float = DEFAULT_TERMINATE_SECONDS,
        reap_seconds: float = DEFAULT_REAP_SECONDS,
        user_ytdlp_directory: Path | None = None,
        ffmpeg_override: Path | None = None,
        entry_point: Callable[..., None] = worker.spawn_session,
    ) -> None:
        super().__init__(parent)
        self._repository = repository
        self._entry_point = entry_point
        self._cooperative_seconds = cooperative_seconds
        self._terminate_seconds = terminate_seconds
        self._reap_seconds = reap_seconds
        self._user_ytdlp_directory = user_ytdlp_directory
        self._ffmpeg_override = ffmpeg_override
        self._sessions: dict[str, _Session] = {}
        self._shutting_down = False
        self._shutdown_deadline: float | None = None
        # `spawn` on every platform, including Linux: forking a process that has already created
        # a `QApplication` is unsafe, and Windows has only spawn — so choosing it everywhere
        # means both platforms exercise the same path (`ARC-002`, `ARCHITECTURE.md` §3).
        self._context = multiprocessing.get_context("spawn")
        self._timer = QTimer(self)
        self._timer.setInterval(poll_interval_ms)
        self._timer.timeout.connect(self._tick)

    # --- queries ------------------------------------------------------------------------

    @property
    def is_idle(self) -> bool:
        return not self._sessions

    def active_job_ids(self) -> tuple[str, ...]:
        return tuple(self._sessions)

    # --- starting -----------------------------------------------------------------------

    def start(self, job_id: str, kind: SessionKind = SessionKind.DOWNLOAD) -> None:
        """Spawn a worker for `job_id` and move the job to `PROBING`.

        Both session kinds start by probing, because a download session probes first so DRM and
        a missing ffmpeg are caught before any bytes move (`downloader/worker.py`).

        **Only a `QUEUED` job may be started.** `ARCHITECTURE.md` §5 has no `READY → PROBING`
        edge, so a job that a previous probe left in `READY` cannot be handed to a download
        session that will probe again. Phase 1's flow — queue a URL, download it — never
        produces that state; a probe-then-download flow needs the state machine amended first,
        which is a Planner decision rather than something to paper over here.
        """
        if self._shutting_down:
            raise RuntimeError("the manager is shutting down; no new session can be started")
        if self._sessions:
            raise RuntimeError(
                f"a session is already running for {sorted(self._sessions)}; Phase 1 runs a pool "
                "of exactly one (T-013 scope, concurrency is Phase 2)"
            )
        job = self._require(job_id)
        if job.status is not JobStatus.QUEUED:
            raise ValueError(
                f"{job_id!r} is {job.status.value}; only a queued job can be started. See the "
                "note on READY in DownloadManager.start."
            )

        started = self._advance(replace(job, started_at=_now()), JobStatus.PROBING)
        self._save_and_announce(started)

        # Everything from here to `process.start()` is one transaction with that durable write
        # (`T013-R3`). The job now says it is in flight; if any of it fails, the queue is
        # describing work that does not exist, `REQ-018`'s "never fail silently" is broken, and
        # crash recovery cannot help — the application did not crash.
        queue: Any = None
        pump: ResultPump | None = None
        try:
            queue = self._context.Queue()
            cancel = self._context.Event()
            pump = ResultPump(queue, job_id, kind, parent=None)
            process = self._context.Process(
                target=self._entry_point,
                args=(kind, job_id, job.request, queue),
                kwargs={
                    "cancel": cancel,
                    "user_ytdlp_directory": self._user_ytdlp_directory,
                    "ffmpeg_override": self._ffmpeg_override,
                },
                # Belt and braces with the child's own parent watchdog: this covers an orderly
                # parent exit, the watchdog covers a parent that was killed.
                daemon=True,
            )
            session = _Session(
                job_id=job_id,
                kind=kind,
                process=process,
                queue=queue,
                cancel=cancel,
                pump=pump,
            )
            self._sessions[job_id] = session

            pump.probed.connect(self._on_probed)
            pump.progress.connect(self._on_progress)
            pump.resolution_reported.connect(self._on_resolution)
            pump.succeeded.connect(self._on_succeeded)
            pump.failed.connect(self._on_failed)
            pump.worker_finished.connect(self._on_worker_finished)
            pump.violation.connect(self._on_violation)
            pump.session_ended.connect(self._on_session_ended)
            # `finished` carries no argument, so the job id is closed over rather than routed.
            pump.finished.connect(lambda: self._on_pump_finished(job_id))

            # **The process first, then the pump** (`T013-R3`, second pass). The original order
            # was the other way round, on the theory that a worker failing immediately must not
            # find nobody reading — but a `multiprocessing.Queue` writes into a pipe that
            # buffers, so nothing a worker sends before the reader starts is lost.
            #
            # The order matters for failure, not for success. Starting the pump first meant a
            # failed spawn left a live thread already blocked in `Queue.get()`, and the only
            # ways to end it are a sentinel the broken queue may refuse and a `terminate()` that
            # does not reliably interrupt a blocked read. Probed both: closing the queue does not
            # wake a reader already inside `get()` either. So that cleanup had no reliable
            # answer, and the fix is to not create the situation — after this order, a spawn
            # failure has no running thread to unwind.
            process.start()
            pump.start()
        except BaseException as error:
            self._abort_start(job_id, queue, pump, error)
            raise
        session.started = True
        self._timer.start()

    def _abort_start(
        self, job_id: str, queue: Any, pump: ResultPump | None, error: BaseException
    ) -> None:
        """Undo a half-built session and leave the job durably failed (`T013-R3`).

        Three things have to happen, and the order matters. The pump — if it got as far as
        running — is sitting in `Queue.get()` on a queue no worker will ever write to, so its
        stream is ended first. The session is dropped, because there is nothing to watch. And the
        job is moved from the `PROBING` this method already persisted to a recorded failure,
        written before it is announced, so nothing is ever told about a state the database does
        not hold.
        """
        session = self._sessions.pop(job_id, None)
        reason = f"the worker session could not be started: {error!r}"

        # **The durable record comes first, and nothing below may pre-empt it** (`T013-R3`,
        # second pass). Whatever broke the session is quite capable of having broken its queue
        # too, so the cleanup write can fail — and when it did, its exception replaced the
        # original cause on the way out and the job was left claiming to be in flight with
        # nothing running. Tidying up is never worth more than the record of what happened.
        self._on_violation(job_id, reason)
        job = self._require(job_id)
        message = f"The download could not be started. {reason}"
        self._save_and_announce(
            replace(job.with_failure(ErrorKind.WORKER_CRASH, message), finished_at=_now())
        )
        self.job_failed.emit(job_id, ErrorKind.WORKER_CRASH, message)

        if session is not None:
            # The job is already resolved; stop the session from resolving it again.
            session.finalized = True
        self._release_half_built(job_id, session, queue, pump)

    def _release_half_built(
        self, job_id: str, session: _Session | None, queue: Any, pump: ResultPump | None
    ) -> None:
        """Dispose of whatever `start()` managed to build, without ever raising.

        Called only when the job has already been recorded as failed, so every step here is
        best-effort: a failure to clean up is reported and moved past, never allowed to escape
        and mask the failure that caused it.
        """
        running = pump is not None and pump.isRunning()
        if not running:
            self._close_quietly(job_id, queue)
            return

        if pump is not None and not self._end_the_stream_quietly(job_id, queue):
            # The sentinel could not be delivered, so the thread cannot end the ordinary way.
            pump.terminate()

        if session is not None:
            # Keep watching it until the thread actually returns (`T013-R4`). The tick releases
            # it; `finalized` stops it from touching a job this method has already failed.
            session.sentinel_sent = True
            session.forced = True
            session.abandoned = True
            session.abandon_at = time.monotonic() + self._reap_seconds
            self._sessions[job_id] = session
            self._timer.start()

    def _end_the_stream_quietly(self, job_id: str, queue: Any) -> bool:
        """Try to put the sentinel; report and return `False` if the queue will not take it."""
        if queue is None:
            return False
        try:
            queue.put(WorkerFinished(job_id=job_id, exit_code=1))
        except Exception as error:
            self._on_violation(
                job_id,
                f"the session's queue would not accept the closing sentinel: {error!r}; "
                "the reader thread was stopped instead",
            )
            return False
        return True

    def _close_quietly(self, job_id: str, queue: Any) -> None:
        if queue is None:
            return
        try:
            queue.close()
        except Exception as error:
            self._on_violation(job_id, f"the session's queue would not close: {error!r}")

    # --- cancelling ---------------------------------------------------------------------

    def cancel(self, job_id: str) -> None:
        """Ask `job_id` to stop, and make sure it does (`REQ-015`).

        Three phases, escalating on the timer rather than on a wait:

        1. **Cooperative.** Set the event the worker's progress hooks check; yt-dlp unwinds its
           own download, so partial files are left in a known state.
        2. **`terminate()`** after `cooperative_seconds`, for a worker that is not running hooks
           — one stuck in extraction, or in a socket read.
        3. **`kill()`** after a further `terminate_seconds`, for one that cannot handle signals
           at all.

        A job that is not running is cancelled directly in the repository, because "cancel" on a
        queued job means the same thing to the user and there is no process to ask.
        """
        session = self._sessions.get(job_id)
        if session is None:
            job = self._require(job_id)
            self._save_and_announce(self._cancelled(job))
            return

        if session.cancelling:
            return
        session.cancelling = True
        session.cancel.set()
        now = time.monotonic()
        session.terminate_at = now + self._cooperative_seconds
        session.kill_at = session.terminate_at + self._terminate_seconds
        # Ticked immediately so a cancel with a zero cooperative budget does not wait for the
        # next timer interval to escalate.
        self._tick()

    def shutdown(self, timeout: float = DEFAULT_SHUTDOWN_SECONDS) -> None:
        """Begin teardown and return. **Nothing here waits** (`T013-R2`).

        The first version blocked the GUI thread until every worker was gone, arguing that
        teardown is not an interaction. The review rejected that, and correctly: `NFR-001` and
        `ARCHITECTURE.md` §8 are unqualified, and a blocking loop that pumps events to make
        progress also re-enters arbitrary GUI code while claiming to be shutting it down.

        So shutdown is a **lifecycle, not a call**. It refuses new sessions, cancels the running
        ones, and lets the same timer that drives cancellation finish the job. When the last
        session is released, `idle` is emitted — that signal is how composition code
        (`T-036`) knows it may quit, and quitting before it arrives is what would leave an
        orphan. `timeout` bounds the escalation, after which anything still alive is killed by
        the tick rather than by a wait here.

        The application therefore closes in two steps: ask, then quit when told. A window that
        calls `QCoreApplication.quit()` immediately after this returns has not shut down; it has
        stopped watching.
        """
        if self._shutting_down:
            return
        self._shutting_down = True
        self._shutdown_deadline = time.monotonic() + timeout
        for job_id in list(self._sessions):
            self.cancel(job_id)
        if not self._sessions:
            self._timer.stop()
            self.idle.emit()
            return
        # Keep the timer running: it is the only thing left that can finish this.
        self._timer.start()

    # --- the tick -----------------------------------------------------------------------

    def _tick(self) -> None:
        """Escalate cancellations, reap dead workers, and release finished sessions.

        Everything time-based lives here so there is one place where the lifetime rules are
        applied, and so none of them is implemented as a wait.
        """
        now = time.monotonic()
        overdue = self._shutdown_deadline is not None and now >= self._shutdown_deadline
        for session in list(self._sessions.values()):
            self._escalate(session, now)

            alive = session.process.is_alive()
            if not alive and not session.sentinel_sent and not session.ended:
                self._end_the_stream(session)
            if session.ended and not alive:
                self._release(session)
            elif session.forced and session.abandon_at is not None and now >= session.abandon_at:
                self._abandon(session)
            elif overdue:
                # Shutdown has run out of patience. The hard stop happens here, on a timer tick,
                # rather than inside a wait on the GUI thread (`T013-R2`).
                self._force_stop(session)
            elif session.ended and alive:
                # The stream is over but the process is still there. Give it a moment to exit
                # on its own, then stop it: this shape is an orphan in the making.
                session.reap_at = session.reap_at or now + self._reap_seconds
                if now >= session.reap_at:
                    self._force_stop(session)

        if not self._sessions:
            self._timer.stop()
            self.idle.emit()

    def _escalate(self, session: _Session, now: float) -> None:
        if not session.cancelling or not session.process.is_alive():
            return
        terminate_at = session.terminate_at
        if not session.terminated and terminate_at is not None and now >= terminate_at:
            session.terminated = True
            session.process.terminate()
        kill_at = session.kill_at
        if not session.killed and kill_at is not None and now >= kill_at:
            session.killed = True
            session.process.kill()

    def _end_the_stream(self, session: _Session) -> None:
        """Put the sentinel the dead worker did not send, carrying its real exit code.

        The pump is blocked in `Queue.get()` and nothing else will ever wake it. Writing to the
        same queue is ordered after everything the child wrote, because the child is gone, so
        this cannot overtake a message that was already on its way.

        **Synthesising it is recorded as a violation** (`T013-R1`). The protocol's guarantee is
        that the worker sends the sentinel last; a parent that quietly manufactures one makes a
        worker that died on the way out indistinguishable from one that shut down cleanly, and
        turns "the sentinel is always last" into something no test could falsify.
        """
        session.sentinel_sent = True
        exit_code = session.process.exitcode
        self._on_violation(
            session.job_id,
            f"the worker exited (code {exit_code}) without sending its WorkerFinished sentinel; "
            "the parent supplied one so the receiver could stop reading",
        )
        # The same sibling as `T013-R3`: this write runs *because* something already went
        # wrong, so the queue it writes to may be exactly as broken as the worker was. Raising
        # here would escape into a timer slot and leave the session unfinishable.
        if not self._end_the_stream_quietly(session.job_id, session.queue):
            session.forced = True
            session.abandon_at = time.monotonic() + self._reap_seconds

    def _release(self, session: _Session) -> None:
        """Drop a session whose process is gone and whose pump has returned.

        Both facts are required, and the thread is asked twice: `pump_finished` records the
        `finished` signal, and `isFinished()` is asked directly because a *terminated* thread
        may never deliver that signal to a slot. Releasing on either is what keeps a forced
        stop from claiming completion it has not got (`T013-R4`).
        """
        if not (session.pump_finished or session.pump.isFinished()):
            return
        if session.started:
            session.process.join(0)
        self._close_quietly(session.job_id, session.queue)
        self._sessions.pop(session.job_id, None)

    def _force_stop(self, session: _Session) -> None:
        """Kill the worker and end its stream. **Waits for nothing** (`T013-R2`).

        Used by the reap deadline and by shutdown's own deadline. The previous version joined
        the process and waited on the pump thread here, which is exactly the GUI-thread blocking
        the review rejected — and it was reached from `shutdown()`, so the "teardown only"
        argument did not even limit it.

        What replaces the waits is a deadline: the pump is given `_reap_seconds` to notice the
        sentinel, checked on later ticks, and abandoned after that. Nothing here can stall.
        """
        session.forced = True
        if session.process.is_alive():
            session.process.kill()
        # Non-blocking reap. A process that has not finished dying yet is collected by a later
        # tick's `is_alive()`.
        if session.started:
            session.process.join(0)
        if not session.ended and not session.sentinel_sent:
            self._end_the_stream(session)
        session.abandon_at = session.abandon_at or time.monotonic() + self._reap_seconds

    def _abandon(self, session: _Session) -> None:
        """Force a pump thread that will not return — and keep owning it until it has.

        `QThread.terminate()` is unsafe in general and is the last resort here: the alternative
        is a thread Qt destroys while it is still running, which aborts the process. Reached only
        when a killed worker's queue is so damaged that even the synthetic sentinel cannot be
        read — the case the pump's own exception guard exists for, one layer deeper.

        **Terminate is a request, not an event** (`T013-R4`). The first version of this dropped
        the session as soon as `terminate()` had been *issued*, so the next tick found nothing
        left and announced `idle` while the thread was still running and the job was still in
        flight — the exact opposite of what the shutdown criterion promises. So the job is
        resolved durably here, and the session stays until the thread reports itself finished.
        Nothing releases it early, and if it never finishes this manager never claims to be idle,
        which is the honest answer.
        """
        if not session.abandoned:
            session.abandoned = True
            self._on_violation(
                session.job_id,
                "the result pump did not stop after its worker was killed and its stream ended; "
                "the thread was terminated",
            )
            session.pump.terminate()
            # Before anything can announce completion: leave no job in flight.
            self._on_session_ended(session.job_id)
        self._release(session)

    # --- slots: everything below runs on the GUI thread ---------------------------------

    def _on_probed(self, message: Probed) -> None:
        self._claim_outcome(message)

    def _on_progress(self, message: Progress) -> None:
        session = self._sessions.get(message.job_id)
        if session is not None and session.outcome is None:
            target = _STAGE_STATUS.get(message.stage)
            if target is not None:
                job = self._require(message.job_id)
                if job.status is not target:
                    moved = self._advance(job, target)
                    self._save_and_announce(
                        replace(
                            moved,
                            bytes_done=message.downloaded_bytes or moved.bytes_done,
                            bytes_total=message.total_bytes or moved.bytes_total,
                        )
                    )
        self.progress.emit(message)

    def _on_resolution(self, message: ResolutionReport) -> None:
        self.resolution_reported.emit(message)

    def _on_succeeded(self, message: Succeeded) -> None:
        self._claim_outcome(message)

    def _on_failed(self, message: Failed) -> None:
        self._claim_outcome(message)

    def _on_worker_finished(self, message: WorkerFinished) -> None:
        session = self._sessions.get(message.job_id)
        if session is not None:
            session.exit_code = message.exit_code

    def _on_violation(self, job_id: str, reason: str) -> None:
        session = self._sessions.get(job_id)
        if session is not None:
            session.violations.append(reason)
        self.protocol_violation.emit(job_id, reason)

    def _on_session_ended(self, job_id: str) -> None:
        """The stream is over. Apply its outcome, or decide what its absence meant.

        **The terminal transition happens here, not when the outcome arrived** (`T013-R1`). A
        message is only known to be legal in the context of the whole session: an outcome that
        was legal on arrival can still be followed by a stream that turns out to be illegal, and
        `COMPLETED` and `CANCELLED` are terminal, so a job moved there on arrival could not be
        corrected afterwards. Holding the transition until the stream ends is what makes the
        maintainer's ruling of 2026-07-27 implementable at all: **a violation fails the job
        loudly, even when a legal outcome arrived first.**

        The cost is one event-loop turn of latency on the final state, which no user can
        perceive. The alternative was a terminal state that could not be taken back.
        """
        session = self._sessions.get(job_id)
        if session is None:
            return
        # `ended` is a fact about the stream and is recorded even when the job has already been
        # finalised — a start that failed halfway (`_abort_start`) has both, and the tick needs
        # the first to release the session.
        session.ended = True
        if session.finalized:
            return
        session.finalized = True
        job = self._require(job_id)

        if session.cancelling:
            # Cancellation outranks everything, including violations. Killing a worker mid-write
            # routinely leaves a truncated queue and no sentinel — reporting that as a crash
            # would tell the user their own cancel button broke something.
            #
            # The worker's own words are kept when it managed to send them, because they are the
            # evidence that the *cooperative* path ran and left partial files in a known state
            # (`REQ-015`). The generic text is for a worker that was killed before it could say
            # anything, where claiming a clean stop would be a guess.
            spoken = session.outcome
            reason = (
                spoken.message
                if isinstance(spoken, Failed) and spoken.kind is ErrorKind.CANCELLED
                else None
            )
            self._save_and_announce(self._cancelled(job, reason))
            return

        if session.violations:
            self._fail_loudly(job, session)
            return

        outcome = session.outcome
        if outcome is None:
            self._fail_loudly(job, session)
        elif isinstance(outcome, Succeeded):
            completed = replace(
                self._advance(job, JobStatus.COMPLETED),
                output_path=outcome.output_path,
                bytes_total=outcome.total_bytes or job.bytes_total,
                finished_at=_now(),
            )
            self._save_and_announce(completed)
            self.job_succeeded.emit(job_id, outcome.output_path)
        elif isinstance(outcome, Probed):
            self._save_and_announce(
                replace(self._advance(job, JobStatus.READY), title=outcome.media.title)
            )
            self.media_probed.emit(job_id, outcome.media)
        elif outcome.kind is ErrorKind.CANCELLED:
            # Not a failure: the user asked for it, and `CANCELLED` is terminal, so presenting
            # it as `FAILED` would offer a retry for something nobody wants retried.
            self._save_and_announce(self._cancelled(job, outcome.message))
        else:
            self._save_and_announce(
                replace(job.with_failure(outcome.kind, outcome.message), finished_at=_now())
            )
            self.job_failed.emit(job_id, outcome.kind, outcome.message)

    def _fail_loudly(self, job: Job, session: _Session) -> None:
        """Record a session that cannot be believed as `WORKER_CRASH` (`REQ-028`, `REQ-018`).

        Covers both shapes of untrustworthy: a session that reported no outcome, and one whose
        stream broke the contract. The maintainer ruled on 2026-07-27 that the second fails the
        job even when an outcome had already arrived legally — a worker that cannot follow the
        protocol has not established that it did what it claimed, and `REQ-018`'s rule is that a
        failure is recorded rather than assumed away.
        """
        detail = "; ".join(session.violations) if session.violations else "no outcome was reported"
        exit_code = session.exit_code if session.exit_code is not None else session.process.exitcode
        message = (
            f"The download worker did not report a result this queue can trust "
            f"(exit code {exit_code}). {detail}."
        )
        self._save_and_announce(
            replace(job.with_failure(ErrorKind.WORKER_CRASH, message), finished_at=_now())
        )
        self.job_failed.emit(job.id, ErrorKind.WORKER_CRASH, message)

    def _on_pump_finished(self, job_id: str) -> None:
        session = self._sessions.get(job_id)
        if session is not None:
            session.pump_finished = True

    # --- helpers ------------------------------------------------------------------------

    def _claim_outcome(self, message: Probed | Succeeded | Failed) -> None:
        """Hold the session's one outcome until the stream ends (`T013-R1`).

        Recording rather than applying: see `_on_session_ended`. A second outcome cannot reach
        here — `SessionValidator` rejects it before the pump routes it — but the check stays as
        defence in depth, because a second route to these slots would otherwise overwrite the
        outcome the session will be judged on (`T011-R4`).
        """
        session = self._sessions.get(message.job_id)
        if session is None:
            return
        if session.outcome is not None:
            self._on_violation(
                session.job_id,
                f"a second outcome ({type(message).__name__}) reached the manager for "
                f"{session.job_id!r}; the first one stands",
            )
            return
        session.outcome = message

    def _advance(self, job: Job, target: JobStatus) -> Job:
        """Walk `job` along `_PIPELINE` to `target`, one validated step at a time.

        A single reported fact can cross more than one state: the first downloading progress
        message means a job has left `PROBING`, passed `READY` and reached `RUNNING`, because
        the pipeline has no edge that skips. The intermediate states are bookkeeping for one
        observable event, so the walk is in memory and only the result is written — but every
        step still goes through `Job.with_status`, so an illegal one raises rather than being
        stored.
        """
        if job.status not in _PIPELINE or target not in _PIPELINE:
            raise ValueError(
                f"{job.status.value} → {target.value} is not a walk along the pipeline; "
                "failure and cancellation are reached directly, not by advancing"
            )
        current = _PIPELINE.index(job.status)
        goal = _PIPELINE.index(target)
        if goal < current:
            # Returning `job` unchanged would be the quiet version of this, and a job that
            # stayed in `RUNNING` because something asked it to go back to `READY` is precisely
            # the silent state corruption `core/job_state.py` exists to prevent.
            raise ValueError(
                f"cannot advance a job backwards, from {job.status.value} to {target.value}"
            )
        for status in _PIPELINE[current + 1 : goal + 1]:
            job = job.with_status(status)
        return job

    def _cancelled(self, job: Job, message: str | None = None) -> Job:
        """`CANCELLED`, with the reason recorded but not classified as a failure."""
        return replace(
            job.with_status(JobStatus.CANCELLED),
            error_kind=ErrorKind.CANCELLED,
            error_message=message or "Cancelled at your request.",
            finished_at=_now(),
        )

    def _require(self, job_id: str) -> Job:
        job = self._repository.get(job_id)
        if job is None:
            raise KeyError(f"no job with id {job_id!r}")
        return job

    def _save_and_announce(self, job: Job) -> None:
        """Persist, **then** signal (`T-013` acceptance criterion).

        This order is the whole guarantee: a crash between the two leaves the database ahead of
        the UI, which recovery corrects at the next startup. The other order leaves the UI
        showing a state that was never stored, and nothing ever corrects that.
        """
        self._repository.update(job)
        self.job_changed.emit(job.id, job.status.value)


def _now() -> datetime:
    """Timezone-aware local time, matching what `persistence` stores (`T-014`)."""
    return datetime.now().astimezone()
