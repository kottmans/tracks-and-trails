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

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal

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

        # The pump first: a worker that fails immediately must not find nobody reading.
        pump.start()
        try:
            process.start()
        except BaseException as error:
            # Spawning can fail before the child exists at all — an unpicklable argument, a
            # process limit, a frozen build without `freeze_support()`. The pump is already
            # blocked in `Queue.get()` on a queue no worker will ever write to, so this must
            # end the stream itself; otherwise the one failure mode that never reaches a
            # worker is also the one that leaks a thread.
            session.sentinel_sent = True
            queue.put(WorkerFinished(job_id=job_id, exit_code=1))
            self._on_violation(job_id, f"the worker process could not be started: {error!r}")
            self._timer.start()
            raise
        session.started = True
        self._timer.start()

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
        """Stop everything and do not return while a worker is still running.

        **This is the one call here that blocks the GUI thread, and it is deliberate.** It runs
        during application teardown, when the event loop is ending: the timer that drives
        escalation will not fire again, so a non-blocking shutdown would return with workers
        still alive and nothing left to reap them. `NFR-001`'s responsiveness budget is about
        interactions; there are none left to be responsive to, and the alternative is a
        download that keeps writing to the user's disk after the window closes.

        Bounded by `timeout`, after which anything still alive is killed outright.
        """
        for job_id in list(self._sessions):
            self.cancel(job_id)

        deadline = time.monotonic() + timeout
        while self._sessions and time.monotonic() < deadline:
            self._tick()
            # Queued signals from the pump threads are delivered here; without this the
            # session would never be seen to end, because that news arrives as an event.
            application = QCoreApplication.instance()
            if application is not None:
                application.processEvents()
            time.sleep(0.005)

        for session in list(self._sessions.values()):
            self._force_stop(session)
        self._timer.stop()

    # --- the tick -----------------------------------------------------------------------

    def _tick(self) -> None:
        """Escalate cancellations, reap dead workers, and release finished sessions.

        Everything time-based lives here so there is one place where the lifetime rules are
        applied, and so none of them is implemented as a wait.
        """
        now = time.monotonic()
        for session in list(self._sessions.values()):
            self._escalate(session, now)

            alive = session.process.is_alive()
            if not alive and not session.sentinel_sent and not session.ended:
                self._end_the_stream(session)
            if session.ended and not alive:
                self._release(session)
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
        """
        session.sentinel_sent = True
        exit_code = session.process.exitcode
        session.queue.put(WorkerFinished(job_id=session.job_id, exit_code=exit_code or 0))

    def _release(self, session: _Session) -> None:
        """Drop a session whose process is gone and whose pump has returned."""
        if not session.pump_finished:
            return
        if session.started:
            session.process.join(0)
        session.queue.close()
        self._sessions.pop(session.job_id, None)

    def _force_stop(self, session: _Session) -> None:
        """Last resort, used only by `shutdown()` and by the reap deadline.

        Kills the process, ends the stream so the pump cannot be left blocked in `Queue.get()`,
        and waits briefly for the thread. `QThread.terminate()` is the final fallback: it is
        unsafe in general, and leaving a running thread behind at application exit is worse —
        Qt destroys it and the process aborts.
        """
        if session.process.is_alive():
            session.process.kill()
            session.process.join(1.0)
        if not session.ended and not session.sentinel_sent:
            self._end_the_stream(session)
        if not session.pump.wait(1000):
            session.pump.terminate()
            session.pump.wait(500)
        session.queue.close()
        self._sessions.pop(session.job_id, None)

    # --- slots: everything below runs on the GUI thread ---------------------------------

    def _on_probed(self, message: Probed) -> None:
        session = self._sessions.get(message.job_id)
        if session is None or not self._claim_outcome(session, message):
            return
        job = self._require(message.job_id)
        self._save_and_announce(
            replace(self._advance(job, JobStatus.READY), title=message.media.title)
        )
        self.media_probed.emit(message.job_id, message.media)

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
        session = self._sessions.get(message.job_id)
        if session is None or not self._claim_outcome(session, message):
            return
        job = self._require(message.job_id)
        completed = replace(
            self._advance(job, JobStatus.COMPLETED),
            output_path=message.output_path,
            bytes_total=message.total_bytes or job.bytes_total,
            finished_at=_now(),
        )
        self._save_and_announce(completed)
        self.job_succeeded.emit(message.job_id, message.output_path)

    def _on_failed(self, message: Failed) -> None:
        session = self._sessions.get(message.job_id)
        if session is None or not self._claim_outcome(session, message):
            return
        job = self._require(message.job_id)
        if message.kind is ErrorKind.CANCELLED:
            # Not a failure: the user asked for it, and `CANCELLED` is terminal, so presenting
            # it as `FAILED` would offer a retry for something nobody wants retried.
            self._save_and_announce(self._cancelled(job, message.message))
        else:
            self._save_and_announce(
                replace(job.with_failure(message.kind, message.message), finished_at=_now())
            )
            self.job_failed.emit(message.job_id, message.kind, message.message)

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
        """The stream is over. Decide what a job with no outcome means (`REQ-028`)."""
        session = self._sessions.get(job_id)
        if session is None or session.finalized:
            return
        session.ended = True
        session.finalized = True

        if session.outcome is not None:
            # The worker said what happened, and it has already been persisted. Its exit code
            # is not consulted: a worker that reports success and then dies on the way out
            # still produced the file.
            return

        job = self._require(job_id)
        if session.cancelling:
            self._save_and_announce(self._cancelled(job))
            return

        detail = "; ".join(session.violations) if session.violations else "no outcome was reported"
        exit_code = session.exit_code if session.exit_code is not None else session.process.exitcode
        message = (
            f"The download worker stopped without reporting a result (exit code {exit_code}). "
            f"{detail}."
        )
        self._save_and_announce(
            replace(job.with_failure(ErrorKind.WORKER_CRASH, message), finished_at=_now())
        )
        self.job_failed.emit(job_id, ErrorKind.WORKER_CRASH, message)

    def _on_pump_finished(self, job_id: str) -> None:
        session = self._sessions.get(job_id)
        if session is not None:
            session.pump_finished = True

    # --- helpers ------------------------------------------------------------------------

    def _claim_outcome(self, session: _Session, message: Probed | Succeeded | Failed) -> bool:
        """Record the session's one outcome, or refuse a second (`T011-R4`).

        `ResultPump` already suppresses a duplicate before it becomes a signal. This is the
        same rule stated where the state lives, so that a second route to these slots — a
        replayed signal, a future direct call — cannot produce a second transition either.
        """
        if session.outcome is not None:
            self._on_violation(
                session.job_id,
                f"a second outcome ({type(message).__name__}) reached the manager for "
                f"{session.job_id!r}; the first one stands",
            )
            return False
        session.outcome = message
        return True

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
