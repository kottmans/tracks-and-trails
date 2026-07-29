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

import logging
import multiprocessing
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Protocol

from PySide6.QtCore import QObject, QTimer, Signal

from tracks_and_trails.core import logging as app_logging
from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus, is_terminal
from tracks_and_trails.core.models import DownloadRequest, Job
from tracks_and_trails.downloader import process_tree, worker
from tracks_and_trails.downloader.environment import APP_SLUG
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

#: The status each starting state moves to, which is the status that says a worker holds the job
#: (`ARC-004`, decided by `T-051`, implemented by `T-016`).
#:
#: Two entry points, using two edges `ARCHITECTURE.md` §5 already draws. `READY → PROBING` is not
#: among them and is not added: a job that has been probed does not become unprobed, and a
#: download session's own extraction is part of downloading rather than a return to an earlier
#: state. A start from any other status is refused — the invariant is that a job with a live
#: session is `PROBING` or `RUNNING`, so the manager's active set and the persisted statuses
#: cannot disagree about whether work is in flight.
_ENTRY_STATUS: Final[dict[JobStatus, JobStatus]] = {
    JobStatus.QUEUED: JobStatus.PROBING,
    JobStatus.READY: JobStatus.RUNNING,
}

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
    rather than on `persistence.JobRepository`. `persistence.PersistentJobStore` satisfies it; so
    does a dictionary-backed fake in a test, which is the point (`ARCHITECTURE.md` §3).

    **`update` is asynchronous and `get` is not** (`ARC-005`). `done` is called on the GUI thread
    with `None` on success or a message on failure, and it is called exactly once. The
    corresponding obligation on the implementation is that **`get` reflects a queued `update`
    immediately** — the manager reads a job back before advancing it, and a store that answered
    from disk alone would hand it the state it had just replaced.

    `JobRepository` alone no longer satisfies this: its `update` is synchronous and blocked the
    GUI thread for a measured 5.017 s under contention (`T016-R3`). It is now reached through
    `PersistentJobStore`, which owns that contract.
    """

    def get(self, job_id: str) -> Job | None: ...

    def update(self, job: Job, done: Callable[[str | None], None]) -> None: ...


class ProcessLike(Protocol):
    """The `multiprocessing.Process` surface used here.

    Named so the manager's lifetime handling can be driven by a stand-in in a test without
    weakening what the real thing has to do. The integration tests use real processes
    (`ai/TESTING.md` §6); this exists for the parts that are about *policy* — which escalation
    happens when — rather than about the process model.
    """

    @property
    def exitcode(self) -> int | None: ...

    @property
    def pid(self) -> int | None: ...

    def is_alive(self) -> bool: ...

    def start(self) -> None: ...

    def join(self, timeout: float | None = None) -> None: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...


@dataclass
class _PendingStart:
    """A start whose transition is on the writer thread and whose worker does not exist yet.

    **A reservation is part of the lifecycle, not a lock** (`T016-R1`, `T016-R3`). It was a bare
    set of ids, held only to keep the pool at one — so cancellation, shutdown and `is_idle` all
    looked straight past it, and the reviewer watched a cancelled job spawn a worker anyway:
    `CANCELLED` was queued behind the `PROBING` write, and that write's success callback still
    ran unconditionally. What the set could not express is the thing that matters — that a start
    which has been asked for can stop being wanted before it exists.
    """

    job_id: str
    kind: SessionKind

    #: Something has withdrawn this start: `cancel()`, or `shutdown()`. The transition already
    #: queued still lands, because a job that reached `PROBING` did reach it; what is withheld
    #: is everything that would have followed.
    withdrawn: bool = False
    reason: str = ""


@dataclass
class _Chain:
    """One job's writes and the effects that must follow them, in the order asked for.

    **Per job, one thing at a time** (`T016-R3`). Writes are asynchronous now, so two facts about
    one job can be in flight at once, and the second was being decided against the first's
    *queued* value as though it were durable. The reviewer measured it on progress: the first
    stage change queued `RUNNING`, the second message read `RUNNING` back, concluded there was
    nothing to persist, and emitted immediately — while the row on disk still said `PROBING`.

    Chains are per job rather than global. Two jobs have nothing to sequence between them, and a
    global queue would make one job's slow write hold up another's progress.
    """

    running: bool = False
    steps: deque[Callable[[], None]] = field(default_factory=deque)


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

    #: The two starts, recorded separately and the instant each returns (`T013-R3`). They fail
    #: independently — a process can be running while its pump never started — and an unwind
    #: that inferred them from one flag left a live worker nobody was reading. `join()` on an
    #: unstarted process raises, so the first is load-bearing for reaping too.
    process_started: bool = False
    pump_started: bool = False

    #: This job's own log file, open for exactly as long as the session is (`T038-R2`).
    #:
    #: Held on the session rather than in a dictionary keyed by job id, so it cannot outlive the
    #: thing it belongs to: every path that drops a session goes through `_release`, which closes
    #: this. An open file handle for a finished job is a leak with a filename.
    log_handler: Any = None

    #: The worker's process group, learned while it is still alive and kept afterwards
    #: (`T-019`). It cannot be looked up later: `os.getpgid` needs the process to exist, and
    #: `Process.is_alive()` reaps the zombie as a side effect of asking — so by the time a dead
    #: session is released there is no pid left to resolve, and the descendants it left behind
    #: would be unaddressable. A group keeps its id reserved while it still has members, which
    #: is exactly the case where there is something to reap.
    group_id: int | None = None

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
    #: is safe, and it is that meaning — not the session count — that decides when it goes out.
    #:
    #: **During shutdown it also waits for the worker-log listener** (`T038-R2`). Sessions being
    #: gone is not the whole of "safe to quit": the listener is a daemon thread, so a record it
    #: is still holding is dropped by interpreter exit and never written. Outside shutdown the
    #: listener stays running for the next session and this is emitted as soon as the sessions
    #: are.
    idle = Signal()

    #: `(job_id, reason)` — a start that was accepted and then never became a session.
    #:
    #: **The asynchronous half of `start()`'s answer** (`T016-R3`). `start()` returns as soon as
    #: the transition is queued, so its refusals — shutting down, a busy pool, an illegal status —
    #: are only the ones it can still check synchronously. Everything after that point is decided
    #: while the caller has already returned: the write can fail, a cancel can win the race, or
    #: shutdown can begin. Without this the add-URL dialog sat at "Probing …" forever with no
    #: worker anywhere, because nothing ever told it the start had been abandoned.
    start_rejected = Signal(str, str)

    #: `(job_id, reason)` — a transition that could not be stored (`ARC-005`, `T016-R3`).
    #:
    #: Separate from `job_failed`, and not a job failure: the download may be running perfectly
    #: while the queue's *record* of it falls behind. Surfaced rather than swallowed, because the
    #: previous synchronous write raised an `OperationalError` that reached no user at all.
    persistence_failed = Signal(str, str)

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
        #: Jobs whose starting transition is queued but whose worker does not exist yet.
        self._reserved: dict[str, _PendingStart] = {}
        #: Per job, the writes and effects still to happen, in order. See `_Chain`.
        self._chains: dict[str, _Chain] = {}
        #: A job re-queued by `retry()` and waiting for the pool of one to free up (`T036-R1`).
        self._pending_retry: str | None = None
        self._shutting_down = False
        self._shutdown_deadline: float | None = None
        # The log listener's ending, which `idle` now waits on (`T038-R2`). Three states rather
        # than one flag: asked, still going, and given up on — the last is how a wedged listener
        # fails to stop the application from closing.
        self._logging_stopped = False
        self._logging_deadline: float | None = None
        self._gave_up_on_logging = False
        self._stopping_listener: threading.Thread | None = None
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
        """Nothing is running **and nothing is about to be** (`T016-R3`).

        A reserved start counts. It used to not, so `idle` could go out while a start's write was
        still on the writer thread — and composition (`T-036`) treats that signal as permission
        to quit, which would have quit into a callback that then spawned a worker.

        So does a retry waiting for the pool (`T036-R1`): it is work this manager has accepted and
        will begin. `shutdown()` drops it, which is what stops that from holding the door.
        """
        return not self._sessions and not self._reserved and self._pending_retry is None

    @property
    def gave_up_on_the_log(self) -> bool:
        """Whether shutdown stopped waiting for the worker-log listener (`T038-R2`).

        `True` means the listener was still inside a handler when the deadline expired and
        records it was holding went with the process. Exposed rather than logged, because the
        state it reports is one where writing a log line is what blocks — see
        `_the_log_has_finished`.
        """
        return self._gave_up_on_logging

    def active_job_ids(self) -> tuple[str, ...]:
        """Every job this manager is holding, including starts that have no worker yet.

        Sorted so the answer does not depend on which of the two collections an id happens to be
        in — a caller that saw a job appear, vanish, and reappear as its start became a session
        would be watching bookkeeping rather than the job (`T016-R3`).
        """
        return tuple(sorted(set(self._sessions) | set(self._reserved)))

    # --- starting -----------------------------------------------------------------------

    def start(self, job_id: str, kind: SessionKind = SessionKind.DOWNLOAD) -> None:
        """Spawn a worker for `job_id` and move it to the status that says a worker holds it.

        **Two entry points** (`ARC-004`, decided by `T-051` and implemented here by `T-016`):

        | The job is | It moves to | Because |
        |---|---|---|
        | `QUEUED` | `PROBING` | nothing is resolved yet; the session's first act is to extract |
        | `READY` | `RUNNING` | a probe resolved it; this session downloads what was chosen |

        A download session started from `QUEUED` still probes first, so DRM and a missing ffmpeg
        are caught before any bytes move (`downloader/worker.py`). One started from `READY`
        re-extracts rather than re-probing — `YoutubeDL.download()` resolves the URL itself and
        cannot be handed a previous extraction — and reports no `Probed` outcome, so the title
        the probe recorded stands.

        **A probe session may only start from `QUEUED`.** `READY → PROBING` does not exist, and
        moving a probe session to `RUNNING` would say a download holds a job that is not
        downloading. A job that has been probed does not become unprobed; probe it again by
        creating a job, not by re-entering an earlier state.

        This is the one place the previous version of this docstring pointed at when it said the
        flow "needs the state machine amended first". Nothing was amended: both edges were
        already in `ARCHITECTURE.md` §5's diagram, and what was missing was the ruling on which
        one a start uses.
        """
        if self._shutting_down:
            raise RuntimeError("the manager is shutting down; no new session can be started")
        if self._sessions or self._reserved:
            # `_reserved` holds the starts whose transition is still being written. Without it
            # the pool of one would be a pool of however many `start()` calls fit between a write
            # and its completion — the gap `ARC-005` created and `T016-R3` is about.
            busy = self.active_job_ids()
            raise RuntimeError(
                f"a session is already running for {busy}; Phase 1 runs a pool "
                "of exactly one (T-013 scope, concurrency is Phase 2)"
            )
        job = self._require(job_id)
        target = _ENTRY_STATUS.get(job.status)
        if target is None:
            raise ValueError(
                f"{job_id!r} is {job.status.value}; a session starts from "
                f"{' or '.join(sorted(status.value for status in _ENTRY_STATUS))} only (ARC-004)."
            )
        if kind is SessionKind.PROBE and job.status is not JobStatus.QUEUED:
            raise ValueError(
                f"{job_id!r} is {job.status.value}; a probe session starts from "
                f"{JobStatus.QUEUED.value} only. ARC-004 has no READY -> PROBING edge, and a "
                "probe that moved the job to running would say a download holds it."
            )

        def entering(current: Job) -> Job | None:
            # Recomputed when the write runs rather than reused from the check above, because a
            # queued step is decided at the moment it happens (`_persist`). Here the two are the
            # same — the pool of one means nothing else is in this job's chain — and it is written
            # this way so the rule holds for every caller rather than for most of them.
            goal = _ENTRY_STATUS.get(current.status)
            if goal is not target:
                return None
            # `started_at` marks when this attempt began, so it is stamped on the way into
            # `PROBING` — including a retry, which re-enters `QUEUED` — and left alone on the way
            # into `RUNNING` from `READY`. That start is the same attempt continuing, and
            # overwriting it there would report a job as having begun when the user pressed
            # *download* rather than when they queued it.
            stamped = current if goal is JobStatus.RUNNING else replace(current, started_at=_now())
            return self._advance(stamped, goal)

        # **Nothing is built until the transition is durable** (`T016-R3`). The synchronous write
        # this replaced sequenced everything after it for free; an asynchronous one does not, and
        # the first attempt at `ARC-005` moved only `job_changed` into the callback — so a worker
        # was spawned, and a pump started, while the row still said `QUEUED`. A start that is
        # never stored must never produce a process.
        self._reserved[job_id] = _PendingStart(job_id=job_id, kind=kind)
        self._persist(
            job_id,
            entering,
            then=lambda: self._spawn(job_id),
            otherwise=lambda reason: self._abandon_start(job_id, reason),
        )

    def _abandon_start(self, job_id: str, reason: str) -> None:
        """Release a reservation that will never become a session, and say so (`T016-R3`).

        Reached when the starting transition could not be stored, or could no longer be computed
        because something moved the job first. The caller has long since returned from `start()`,
        so the only honest way to report this is the signal — and until there was one, the
        add-URL dialog kept showing "Probing …" for a worker that was never built.
        """
        if self._reserved.pop(job_id, None) is None:
            return
        self.start_rejected.emit(job_id, reason)

    def _spawn(self, job_id: str) -> None:
        """Build and start the session. Runs only once the job's transition is on disk.

        **A reservation can be withdrawn between `start()` and here** (`T016-R1`). This used to
        build unconditionally, so a cancel that arrived while the transition was still being
        written produced a durable `CANCELLED` *and* a running worker for the URL the user had
        just taken away — the Critical consequence in its strongest form, since the work that
        started was work nobody had asked for any more. Shutdown had the same hole.

        **This cannot report by raising** (`T016-R3`). It is reached from a write's completion
        callback, so an exception would escape into a Qt slot rather than to whoever called
        `start()`. `_abort_start` therefore records the failure durably and announces it, and
        `start()`'s contract narrows to the refusals it can still check synchronously — shutting
        down, a busy pool, an illegal status.

        (`T013-R3`, third pass) has now failed review three times, in three different places,
        and every one had the same cause: the unwind inferred what existed from whichever locals
        happened to be in scope. So the session is created as soon as there is anything to own,
        each start is recorded on it the instant it succeeds, and `_abort_start` reads that
        record instead of guessing.
        """
        reservation = self._reserved.get(job_id)
        if reservation is None:
            return
        if reservation.withdrawn or self._shutting_down:
            reason = reservation.reason or "the manager began shutting down before it could start"
            self._abandon_start(job_id, reason)
            return
        del self._reserved[job_id]
        kind = reservation.kind
        job = self._require(job_id)
        session: _Session | None = None
        queue: Any = None
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
                    # `T-038`: the worker's diagnostics come back here as records and are
                    # rendered — and therefore redacted — by this process's handlers. The job id
                    # travels with them so each line reaches that job's own file (`T038-R2`).
                    "log_queue": app_logging.worker_log_queue(),
                    "log_job_id": job_id,
                },
                # Belt and braces with the child's own parent watchdog: this covers an orderly
                # parent exit, the watchdog covers a parent that was killed.
                daemon=True,
            )
            session = _Session(
                job_id=job_id, kind=kind, process=process, queue=queue, cancel=cancel, pump=pump
            )
            self._sessions[job_id] = session
            self._open_job_log(session)
            self._connect(session)

            # **The process first, then the pump.** The original order was the other way round,
            # on the theory that a worker failing immediately must not find nobody reading — but
            # a `multiprocessing.Queue` writes into a pipe that buffers, so nothing sent before
            # the reader starts is lost.
            #
            # The order matters for failure, not for success. Starting the pump first meant a
            # failed spawn left a thread blocked in `Queue.get()` with no reliable end: the
            # sentinel can be refused, `terminate()` does not interrupt a blocked read, and
            # closing the queue does not wake a reader already inside `get()` — all three
            # probed. Each start is recorded separately because the *other* order has a failure
            # too: a pump that will not start leaves a worker already running.
            process.start()
            session.process_started = True
            pump.start()
            session.pump_started = True
        except BaseException as error:
            self._abort_start(job_id, session, queue, error)
            return
        self._timer.start()

    def _connect(self, session: _Session) -> None:
        """Wire one session's pump to the slots that decide what its messages mean."""
        pump = session.pump
        pump.probed.connect(self._on_probed)
        pump.progress.connect(self._on_progress)
        pump.resolution_reported.connect(self._on_resolution)
        pump.succeeded.connect(self._on_succeeded)
        pump.failed.connect(self._on_failed)
        pump.worker_finished.connect(self._on_worker_finished)
        pump.violation.connect(self._on_violation)
        pump.session_ended.connect(self._on_session_ended)
        # `finished` carries no argument, so the job id is closed over rather than routed.
        job_id = session.job_id
        pump.finished.connect(lambda: self._on_pump_finished(job_id))

    def _abort_start(
        self, job_id: str, session: _Session | None, queue: Any, error: BaseException
    ) -> None:
        """Leave the job durably failed, then take apart exactly what was built (`T013-R3`).

        **Persistence comes first, and both signals come after it.** Whatever broke the session
        can break its queue too, so an unguarded cleanup write once replaced the original cause;
        and an observer of `protocol_violation` once read `PROBING`, because the violation was
        emitted before the failure was stored. Nothing about tidying up is worth more than the
        record of what happened, and nothing is announced before it is true.

        **Cleanup is mandatory; the announcement is not** (`T016-R3`). The first correction ran
        one function on both sides of the write, which meant a *failed* `FAILED` write still
        emitted `job_failed` — and every observer that read the row back found `PROBING`, which is
        precisely the guarantee the change was made to establish. So the two are separated: the
        process and the pump are taken apart whichever way the write went, because a failure that
        could not be recorded must not also leak a process, while the signals that assert a
        durable outcome wait for one. On the failure path `persistence_failed` goes out instead,
        from `_settle`, and the violation is written to the log so the cause is not lost with it.
        """
        reason = f"the worker session could not be started: {error!r}"
        message = f"The download could not be started. {reason}"
        self._reserved.pop(job_id, None)

        def unwind() -> None:
            if session is None:
                # Nothing was owned yet: construction failed before there was a session.
                self._close_quietly(job_id, queue)
                return
            session.finalized = True
            self._sessions.pop(job_id, None)
            self._unwind(session)

        def announce_and_unwind() -> None:
            self._on_violation(job_id, reason)
            self.job_failed.emit(job_id, ErrorKind.WORKER_CRASH, message)
            unwind()

        def unwind_only(_: str) -> None:
            logging.getLogger(f"{APP_SLUG}.manager").error(
                "%s could not be recorded as failed: %s", job_id, reason
            )
            unwind()

        self._persist(
            job_id,
            lambda current: (
                None
                if is_terminal(current.status)
                else replace(
                    current.with_failure(ErrorKind.WORKER_CRASH, message), finished_at=_now()
                )
            ),
            then=announce_and_unwind,
            otherwise=unwind_only,
        )

    def _unwind(self, session: _Session) -> None:
        """Stop whatever a failed `start()` actually got running, reading its own record.

        The two halves fail independently, and the review found each of them in turn:

        - **A started process with no pump** is a worker nobody is reading and nobody will stop.
          It is killed here — it has done no work worth unwinding, since the pump that would
          have carried its messages never ran.
        - **A started pump** is a thread blocked reading, ended the ordinary way with a sentinel
          and by `stop()` if the queue will not take one. The session is put back under watch
          until the thread reports itself finished (`T013-R4`), because a stop that has merely
          been *asked for* is not a thread that has stopped.
        """
        if session.process_started and session.process.is_alive():
            # The tree, not just the worker (`T-019`). A start that failed after the process was
            # spawned is one of the three paths a descendant can outlive.
            self._stop_tree(session, force=True)
            session.process.kill()
            self._reap_tree(session)
            session.process.join(0)

        if not session.pump_started:
            self._close_quietly(session.job_id, session.queue)
            self._close_job_log(session)
            return

        if not self._end_the_stream_quietly(session.job_id, session.queue):
            session.pump.stop()
        session.sentinel_sent = True
        session.forced = True
        session.abandoned = True
        session.abandon_at = time.monotonic() + self._reap_seconds
        self._sessions[session.job_id] = session
        self._timer.start()

    def _end_the_stream_quietly(self, job_id: str, queue: Any) -> bool:
        """Try to put the sentinel; report and return `False` if the queue will not take it.

        Every caller runs *because* something already went wrong, so the queue being written to
        may be exactly as broken as whatever broke first. Raising from here would replace the
        original cause, or escape into a timer slot (`T013-R3`).
        """
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

        **A start that has been reserved but not yet spawned is cancellable too** (`T016-R1`).
        There is no process to signal, so cancelling it is two things rather than one: withdraw
        the reservation, so the transition's success callback builds nothing, *and* record the
        cancellation. Doing only the second left a durable `CANCELLED` row with a worker running
        for it.
        """
        reservation = self._reserved.get(job_id)
        if reservation is not None and not reservation.withdrawn:
            reservation.withdrawn = True
            reservation.reason = "the job was cancelled before its worker could be started"

        session = self._sessions.get(job_id)
        if session is None:
            # Queued behind the starting transition when there is one, so `CANCELLED` is written
            # after the `PROBING` it supersedes rather than racing it (`_Chain`).
            self._persist(
                job_id,
                lambda current: None if is_terminal(current.status) else self._cancelled(current),
            )
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

    def retarget(
        self,
        job_id: str,
        request: DownloadRequest,
        *,
        then: Callable[[], None] | None = None,
        otherwise: Callable[[str], None] | None = None,
    ) -> None:
        """Replace a not-yet-started job's download request, then run `then` (`T-075`).

        **Why the manager owns this rather than the dialog writing through the store.** `T036-R1`
        is the precedent and it cost a review round: composition wrote a status change through the
        store directly, so nothing announced it — `job_changed` is emitted from *this* object's
        write callback — and a view went on showing a state the row no longer held. A request
        change has the same shape, so it takes the same route.

        Ordered, not fired-and-forgotten. `then` runs **after** the new request is durable, which
        is what lets the caller start the job knowing the worker will read what the user chose.
        A start issued alongside the write would be a race whose loser is a download of the wrong
        thing.

        A job past `Job.RETARGETABLE` is left alone and `otherwise` is told why, rather than
        raising: this is reached from a button, and a job that started while the dialog was open
        is an ordinary outcome rather than a programming error.
        """

        current = self._repository.get(job_id)
        if current is not None and current.request == request:
            # **Already what was asked for, so no write.** `DownloadRequest` is frozen, so this
            # is a structural comparison rather than an identity one. Writing anyway would add a
            # second `READY` revision to every probed job's history for no change — and
            # `test_a_probed_job_downloads_from_ready_without_re_entering_probing` asserts that
            # history as a sequence, which is the right thing for it to assert (`ARC-004`).
            if then is not None:
                then()
            return

        def revise(candidate: Job) -> Job | None:
            if candidate.status not in Job.RETARGETABLE:
                return None
            return candidate.with_request(request)

        self._persist(job_id, revise, then=then, otherwise=otherwise)

    def retry(self, job_id: str) -> None:
        """Re-queue a failed job and start it as soon as the pool can take it (`REQ-018`).

        **The manager owns this, and `T036-R1` is what it cost to have composition own it.** A
        retry is a state transition plus a start, and both are this object's business — so when
        composition wrote `FAILED → QUEUED` through the store itself, two things went wrong at
        once. Nothing announced the transition, because `job_changed` is emitted from *this*
        object's write callback and the store has no signal; so a progress view went on showing
        `FAILED` over a row that said `QUEUED`. And the start was attempted exactly once,
        immediately, while the failed session was still being released — the pool of one refused
        it, the refusal was logged and swallowed, and nothing ever tried again. The reviewer
        measured no transitions at all five seconds after pressing Retry.

        The waiting half is deliberately small. This is **not** Phase 2's scheduler: one job may
        be waiting, it is the one the user just asked for, and it starts on the tick that finds
        the pool free — which is normally the next one, because what it is waiting for is a
        session that has already ended being released.

        A job that is not `FAILED` is not retried, and saying so beats raising: this is reached
        from a widget's signal (`T-017`), and `FAILED → QUEUED` is the state machine's only edge
        back.
        """
        job = self._repository.get(job_id)
        if job is None or job.status is not JobStatus.FAILED:
            return
        self._persist(
            job_id,
            lambda current: (
                current.with_status(JobStatus.QUEUED)
                if current.status is JobStatus.FAILED
                else None
            ),
            then=lambda: self._start_when_free(job_id),
        )

    def _start_when_free(self, job_id: str) -> None:
        """Start `job_id` now, or on the first tick that finds the pool of one free."""
        if self._shutting_down:
            return
        if self._sessions or self._reserved:
            self._pending_retry = job_id
            # The tick is what will notice; without this the timer may not be running at all.
            self._timer.start()
            return
        self._pending_retry = None
        try:
            self.start(job_id)
        except (RuntimeError, ValueError) as refusal:
            # Reported, not swallowed. `start_rejected` is the asynchronous half of `start()`'s
            # answer and the dialog already listens to it; a retry that cannot start has exactly
            # the same shape as a probe that cannot.
            self.start_rejected.emit(job_id, str(refusal))

    def shutdown(self, timeout: float = DEFAULT_SHUTDOWN_SECONDS) -> None:
        """Begin teardown and return. **Nothing here waits** (`T013-R2`).

        The first version blocked the GUI thread until every worker was gone, arguing that
        teardown is not an interaction. The review rejected that, and correctly: `NFR-001` and
        `ARCHITECTURE.md` §8 are unqualified, and a blocking loop that pumps events to make
        progress also re-enters arbitrary GUI code while claiming to be shutting it down.

        So shutdown is a **lifecycle, not a call**. It refuses new sessions, cancels the running
        ones, and lets the same timer that drives cancellation finish the job. When the last
        session is released **and the worker-log listener has stopped**, `idle` is emitted — that
        signal is how composition code (`T-036`) knows it may quit, and quitting before it
        arrives is what would leave an orphan, or drop the records the listener was still
        holding. `timeout` bounds the escalation, after which anything still alive is killed by
        the tick rather than by a wait here; the listener has its own bound so it cannot keep the
        application open either.

        The application therefore closes in two steps: ask, then quit when told. A window that
        calls `QCoreApplication.quit()` immediately after this returns has not shut down; it has
        stopped watching.
        """
        if self._shutting_down:
            return
        self._shutting_down = True
        self._shutdown_deadline = time.monotonic() + timeout
        # A retry that has not started yet never will. Dropped rather than carried, so `idle`
        # is not held open by work this manager has just decided not to do (`T036-R1`).
        self._pending_retry = None
        # Reserved starts as well as running sessions (`T016-R3`). A start whose transition is
        # still on the writer thread has no process to cancel yet, and skipping it here is how
        # shutdown used to announce `idle` and then spawn a worker from the callback that
        # arrived afterwards.
        for job_id in self.active_job_ids():
            self.cancel(job_id)
        # Keep the timer running: it is the only thing left that can finish this, and that now
        # includes the log listener's own ending. Even with no sessions to cancel, `idle` is the
        # tick's to emit rather than this method's — see `_tick` (`T038-R2`).
        self._timer.start()
        self._tick()

    # --- the tick -----------------------------------------------------------------------

    def _tick(self) -> None:
        """Escalate cancellations, reap dead workers, and release finished sessions.

        Everything time-based lives here so there is one place where the lifetime rules are
        applied, and so none of them is implemented as a wait.
        """
        now = time.monotonic()
        overdue = self._shutdown_deadline is not None and now >= self._shutdown_deadline
        for session in list(self._sessions.values()):
            self._learn_the_group(session)
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

        waiting = self._pending_retry
        if waiting is not None and not self._sessions and not self._reserved:
            # The pool freed up. This is the whole of the retry's "scheduling" (`T036-R1`).
            self._pending_retry = None
            self._start_when_free(waiting)

        if self._sessions or self._reserved or self._pending_retry is not None:
            # A reservation counts as work in flight (`T016-R3`). Its transition is still on the
            # writer thread, and the callback that settles it is what decides whether a worker
            # appears — so `idle` here would be a promise this manager cannot keep. A retry
            # waiting for the pool is the same claim.
            return
        if self._shutting_down and not self._the_log_has_finished(now):
            # Not idle yet, and the timer stays running. `idle` is what tells composition it may
            # quit (`T-036`), and quitting while the listener thread still holds records drops
            # them: it is a daemon thread, so nothing at interpreter exit will write them
            # (`T038-R2`). The wait is the tick's, never the GUI thread's.
            return
        self._timer.stop()
        self.idle.emit()

    def _the_log_has_finished(self, now: float) -> bool:
        """Ask the listener to stop the first time, then report whether it has. **Never waits.**

        Bounded, because a log must not be able to stop the application from closing. If the
        listener is still inside a handler after `reap_seconds` the manager says so and goes
        idle anyway — the same shape as the pump's abandon deadline, and for the same reason:
        every wait here is a deadline checked on a tick rather than a thread being joined.
        """
        if not self._logging_stopped:
            self._logging_stopped = True
            self._stopping_listener = self._stop_logging()
            self._logging_deadline = now + self._reap_seconds
        # **The thread this manager stopped**, not "the listener". The queue and its listener are
        # process-wide, so asking the module later would make a manager that never started a
        # worker wait on a thread somebody else is responsible for.
        thread = self._stopping_listener
        if self._gave_up_on_logging or thread is None or not thread.is_alive():
            return True
        deadline = self._logging_deadline
        if deadline is not None and now >= deadline:
            # **Recorded, not logged**, and that is the whole point of the flag. `Handler.handle`
            # takes the handler's lock *before* calling `emit`, so a warning written here would
            # block this thread on the lock the wedged listener is holding — the GUI thread
            # stopped by log I/O, on the one path that exists because log I/O has stopped. A
            # probe measured five seconds of frozen event loop from exactly that call.
            #
            # This is the general shape rather than a defect of this method: every GUI-thread
            # `logger` call in this application blocks on a handler that will not return. What is
            # specific here is that this path *knows* one is stuck, so it does not add one more.
            self._gave_up_on_logging = True
            return True
        return False

    def _stop_logging(self) -> threading.Thread | None:
        """Ask the thread draining worker log records to finish (`T038-R2`). **Does not wait.**

        Only on the way out, and only once: the queue and its listener are process-wide, so a
        manager that stopped them while another was running would silently swallow that one's
        worker output. Done here rather than left to interpreter exit because a listener thread
        that is still blocked on a queue is a process that does not finish quitting — the same
        shape as the orphan worker this file spends most of its length preventing.

        **Asking is all it does.** This runs on the GUI thread, from `shutdown()` or from the
        timer tick that finishes it, and the listener may be inside a slow handler. The first
        version joined the thread and a two-second handler call held `shutdown()` for 2.001 s —
        `T013-R2`'s blocking teardown restored under a different name. The sentinel is queued
        behind whatever this session's release put there, so the ordering the per-job logs
        depend on survives the stop.

        Returns the thread it asked to stop, which is what `idle` then watches — see
        `_the_log_has_finished`.
        """
        return app_logging.stop_listening_for_worker_logs()

    def _escalate(self, session: _Session, now: float) -> None:
        """Walk one session through the two deadlines, signalling the **tree** at each.

        `terminate()` and `kill()` reach the worker and nothing else, and yt-dlp's `ffmpeg` is a
        child *of* the worker (`T-019`). Each step therefore signals the worker's process group —
        or, where there is no group of its own to signal, falls back to the single process, which
        is what `Process.terminate()` did all along.
        """
        if not session.cancelling or not session.process.is_alive():
            return
        terminate_at = session.terminate_at
        if not session.terminated and terminate_at is not None and now >= terminate_at:
            session.terminated = True
            self._stop_tree(session, force=False)
            session.process.terminate()
        kill_at = session.kill_at
        if not session.killed and kill_at is not None and now >= kill_at:
            session.killed = True
            self._stop_tree(session, force=True)
            session.process.kill()

    def _stop_tree(self, session: _Session, *, force: bool) -> None:
        """Signal the worker's descendants, if this platform needs the parent to.

        On Windows it does not: the child's Job object kills its members when the worker's last
        handle closes, so `Process.terminate()` alone reaps the tree. On POSIX this is the whole
        fix. Both call sites still signal the process itself afterwards, because a group with no
        members of its own is exactly the case where this does nothing.
        """
        if session.group_id is None:
            return
        if force:
            process_tree.kill_group(session.group_id)
        else:
            process_tree.terminate_group(session.group_id)

    def _open_job_log(self, session: _Session) -> None:
        """Give this session its own log file for as long as it runs (`T038-R2`, §8).

        Failing to open one must not fail the download: a job that cannot be *logged* is still a
        job that can be *done*, and the application log has the same lines regardless. So this
        records the problem and carries on — the opposite of `contain_this_process()`, where the
        missing guarantee was the user's ability to stop the work.
        """
        try:
            handler = app_logging.open_job_log(session.job_id)
        except OSError as error:
            logging.getLogger(f"{APP_SLUG}.manager").warning(
                "no per-job log for %s: %s", session.job_id, error
            )
            return
        session.log_handler = handler
        logging.getLogger(APP_SLUG).addHandler(handler)

    def _close_job_log(self, session: _Session) -> None:
        """Hand this session's log file back, to be closed **once its records have arrived**.

        Not closed here (`T038-R2`). Log records and result messages travel on two different
        queues, and only the second one is what tells this manager the session is over — so at
        the moment a session is released, a line the worker wrote before its `WorkerFinished`
        can still be in the log queue. Closing the handler on the spot sent that line to the
        application log alone and left the per-job file empty, which a delayed listener
        reproduced every time.

        `close_job_log_when_drained` establishes the ordering instead of waiting for it, and the
        close happens on the listener thread. Safe to call more than once; the session forgets
        the handler here either way.
        """
        handler = session.log_handler
        if handler is None:
            return
        session.log_handler = None
        app_logging.close_job_log_when_drained(session.job_id, handler)

    def _learn_the_group(self, session: _Session) -> None:
        """Record the worker's process group the first tick it can be read.

        Not at `start()`: the pid exists before the child has run `contain_this_process()`, so an
        answer taken there is the group the worker was *born* into — ours — and would be refused
        forever. Asked on each tick until it returns something, which is at most one extra
        `getpgid` per 50 ms and only until the child has settled.
        """
        if session.group_id is None and session.process_started:
            pid = session.process.pid
            if pid is not None:
                session.group_id = process_tree.group_of(pid)

    def _reap_tree(self, session: _Session) -> None:
        """Kill anything still in a finished worker's group.

        Uses the group learned while the worker was alive, because there is nothing left to
        resolve now: see `_Session.group_id`. Without it the tests looked green — a descendant
        whose parent has died is reparented to `init` and stops being one of ours, so "no
        descendants remain" was true while `ffmpeg` kept writing.
        """
        if session.group_id is not None:
            process_tree.kill_group(session.group_id)

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
        `finished` signal, and `isFinished()` is asked directly because a thread that ended
        without the event loop running may never deliver that signal to a slot. Releasing on
        either is what keeps a forced stop from claiming completion it has not got (`T013-R4`).
        """
        if session.pump_started and not (session.pump_finished or session.pump.isFinished()):
            return
        if session.process_started:
            # **Reap the group on every path** (`T-019`). The path nothing else covers is the
            # ordinary one: a worker that crashed, was killed from outside, or simply finished
            # leaves its `ffmpeg` behind, and no cancellation ever runs to notice. The group
            # outlives its leader, which is what makes it addressable at all — and it is
            # addressable only because the id was learned while the worker was alive, since
            # `is_alive()` reaps the zombie and there is no pid left to resolve by now. A
            # completed session pays one signal to an empty group for the cases that are not.
            self._reap_tree(session)
            session.process.join(0)
        self._close_quietly(session.job_id, session.queue)
        self._close_job_log(session)
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
            self._stop_tree(session, force=True)
            session.process.kill()
        # Non-blocking reap. A process that has not finished dying yet is collected by a later
        # tick's `is_alive()`.
        if session.process_started:
            session.process.join(0)
        if not session.ended and not session.sentinel_sent:
            self._end_the_stream(session)
        session.abandon_at = session.abandon_at or time.monotonic() + self._reap_seconds

    def _abandon(self, session: _Session) -> None:
        """Stop a pump thread that will not return — and keep owning it until it has.

        Reached only when a killed worker's queue is so damaged that even the synthetic sentinel
        cannot be written — the case the pump's own exception guard exists for, one layer deeper.

        **This used to call `QThread.terminate()`, and that was the wrong tool** (`T019-R5`).
        Killing a thread wherever it happens to be includes killing it inside CPython's own
        internals, holding a lock nothing will ever release; the observable cost was a bare
        `pytest` wedging about one run in five, parked forever on that lock. `ResultPump.stop()`
        asks instead, and the thread returns within one poll — so there is no window in which it
        dies mid-operation.

        **A stop is a request, not an event** (`T013-R4`), and that was already true of the tool
        this replaces. The first version dropped the session as soon as termination had been
        *issued*, so the next tick found nothing left and announced `idle` while the thread was
        still running and the job was still in flight. So the job is resolved durably here, and
        the session stays until the thread reports itself finished. Nothing releases it early,
        and if it never finishes this manager never claims to be idle, which is the honest answer.
        """
        if not session.abandoned:
            session.abandoned = True
            self._on_violation(
                session.job_id,
                "the result pump did not stop after its worker was killed and its stream ended; "
                "the thread was terminated",
            )
            session.pump.stop()
            # Before anything can announce completion: leave no job in flight.
            self._on_session_ended(session.job_id)
        self._release(session)

    # --- slots: everything below runs on the GUI thread ---------------------------------

    def _on_probed(self, message: Probed) -> None:
        self._claim_outcome(message)

    def _on_progress(self, message: Progress) -> None:
        """Forward progress, moving the job first when this message says it has moved on.

        **Both paths go through the job's chain** (`T016-R3`). The version this replaces forwarded
        a non-moving message the instant it arrived, which read as harmless — it persists nothing.
        It was not: the *first* message of a stage queues the transition, and the second one then
        read the queued value back, concluded the job was already where it belonged, and emitted
        while the row on disk still said `PROBING`. An observer that reads the repository when it
        is told about progress therefore saw a state one transition behind the story it was being
        told, which is the ordering `T-013` was approved for.
        """
        session = self._sessions.get(message.job_id)
        target = (
            _STAGE_STATUS.get(message.stage)
            if session is not None and session.outcome is None
            else None
        )
        if target is None:
            self._effect(message.job_id, lambda: self.progress.emit(message))
            return

        def moved(current: Job) -> Job | None:
            if current.status not in _PIPELINE or target not in _PIPELINE:
                return None
            if _PIPELINE.index(current.status) >= _PIPELINE.index(target):
                # Already there, or past it. Returning `None` rather than advancing is what keeps
                # a late message for an earlier stage from asking the pipeline to walk backwards,
                # which `_advance` refuses by raising — out of a Qt slot, from a timer's thread of
                # control, for an event that is merely out of date.
                return None
            return replace(
                self._advance(current, target),
                bytes_done=message.downloaded_bytes or current.bytes_done,
                bytes_total=message.total_bytes or current.bytes_total,
            )

        # The report of a moving message waits for the move to be durable; a message that moves
        # nothing is still forwarded, because bytes really did arrive and progress is not a claim
        # about persisted state.
        self._persist(
            message.job_id,
            moved,
            then=lambda: self.progress.emit(message),
            otherwise=lambda _: self.progress.emit(message),
        )

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
            self._persist(job_id, lambda current: self._settled(current, self._cancelled, reason))
            return

        if session.violations:
            self._fail_loudly(job_id, session)
            return

        outcome = session.outcome
        if outcome is None:
            self._fail_loudly(job_id, session)
        elif isinstance(outcome, Succeeded):
            # `job_succeeded` waits for `COMPLETED` to be on disk (`T016-R3`): it used to arrive
            # while the row still said `RUNNING`.
            self._persist(
                job_id,
                lambda current: self._settled(
                    current,
                    lambda job: replace(
                        self._advance(job, JobStatus.COMPLETED),
                        output_path=outcome.output_path,
                        bytes_total=outcome.total_bytes or job.bytes_total,
                        finished_at=_now(),
                    ),
                ),
                then=lambda: self.job_succeeded.emit(job_id, outcome.output_path),
            )
        elif isinstance(outcome, Probed):
            self._persist(
                job_id,
                lambda current: self._settled(
                    current,
                    lambda job: replace(
                        self._advance(job, JobStatus.READY), title=outcome.media.title
                    ),
                ),
                then=lambda: self.media_probed.emit(job_id, outcome.media),
            )
        elif outcome.kind is ErrorKind.CANCELLED:
            # Not a failure: the user asked for it, and `CANCELLED` is terminal, so presenting
            # it as `FAILED` would offer a retry for something nobody wants retried.
            self._persist(
                job_id, lambda current: self._settled(current, self._cancelled, outcome.message)
            )
        else:
            self._persist(
                job_id,
                lambda current: self._settled(
                    current,
                    lambda job: replace(
                        job.with_failure(outcome.kind, outcome.message), finished_at=_now()
                    ),
                ),
                then=lambda: self.job_failed.emit(job_id, outcome.kind, outcome.message),
            )

    def _settled(self, job: Job, build: Callable[..., Job], *arguments: Any) -> Job | None:
        """`build(job, *arguments)`, unless the job has already reached a terminal state.

        Every terminal transition in this file goes through here (`T016-R3`). They are computed
        when their turn in the chain comes, and by then something ahead of them may already have
        finished the job — a cancellation that won a race with the outcome, most concretely. The
        state machine would refuse that with `IllegalTransitionError` raised out of a Qt slot; a
        job that is already finished is not an error, it is the answer.
        """
        if is_terminal(job.status):
            return None
        return build(job, *arguments)

    def _fail_loudly(self, job_id: str, session: _Session) -> None:
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
        self._persist(
            job_id,
            lambda current: self._settled(
                current,
                lambda job: replace(
                    job.with_failure(ErrorKind.WORKER_CRASH, message), finished_at=_now()
                ),
            ),
            then=lambda: self.job_failed.emit(job_id, ErrorKind.WORKER_CRASH, message),
        )

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

    # --- per-job sequencing -------------------------------------------------------------

    def _enqueue(self, job_id: str, step: Callable[[], None]) -> None:
        """Put `step` at the back of this job's chain and run the chain if it is not running."""
        chain = self._chains.setdefault(job_id, _Chain())
        chain.steps.append(step)
        self._run_next(job_id)

    def _run_next(self, job_id: str) -> None:
        chain = self._chains.get(job_id)
        if chain is None or chain.running:
            return
        if not chain.steps:
            del self._chains[job_id]
            return
        step = chain.steps.popleft()
        chain.running = True
        try:
            step()
        except BaseException:
            # A step that raised has still finished, and a chain left marked as running is a job
            # nothing can ever write again. The exception is re-raised rather than swallowed:
            # this is the manager's own bug, and `T013-R3` is a standing reminder of what happens
            # when a failure is quietly absorbed by cleanup.
            chain.running = False
            self._run_next(job_id)
            raise

    def _step_finished(self, job_id: str) -> None:
        chain = self._chains.get(job_id)
        if chain is None:
            return
        chain.running = False
        self._run_next(job_id)

    def _effect(self, job_id: str, run: Callable[[], None]) -> None:
        """Do something for `job_id` — but not before its outstanding writes have settled.

        The fast path matters: progress messages arrive several times a second per job, and one
        that changes no state is not worth a deque round trip when nothing is in flight.
        """
        if job_id not in self._chains:
            run()
            return

        def step() -> None:
            run()
            self._step_finished(job_id)

        self._enqueue(job_id, step)

    def _persist(
        self,
        job_id: str,
        revise: Callable[[Job], Job | None],
        *,
        then: Callable[[], None] | None = None,
        otherwise: Callable[[str], None] | None = None,
    ) -> None:
        """Persist, **then** signal (`T-013` acceptance criterion). **Waits for neither.**

        The order is the whole guarantee: a crash between the two leaves the database ahead of
        the UI, which recovery corrects at the next startup. The other order leaves the UI
        showing a state that was never stored, and nothing ever corrects that.

        **The waiting is what changed, not the order** (`ARC-005`). This used to call a
        synchronous `JobRepository.update()` from the GUI thread — a start, a cancel or a stage
        change blocking for a measured 5.017 s under a held writer lock and then raising an
        uncaught `OperationalError`.

        **`revise` is a function of the job, not a job** (`T016-R3`). Asynchronous writes mean two
        transitions for one job can be asked for before the first has landed, so a transition
        computed at the moment it was *asked for* is computed against a state that may still
        turn out not to have happened. It is therefore computed when its turn comes, from the job
        as it stands then, and returning `None` says the transition no longer applies — a
        cancelled job whose progress message is still queued behind it, say. That is a normal
        outcome rather than an error, and it runs `otherwise` with its reason.

        A failed write is surfaced rather than swallowed, and **the success-side effect does not
        run**. It is deliberately not turned into a job failure: the download itself may be
        running perfectly, and the honest report is that the queue's record of it is behind.
        Recovery re-queues an interrupted job at the next startup (`NFR-003`).
        """

        def step() -> None:
            current = self._require(job_id)
            revised = revise(current)
            if revised is None:
                reason = f"{job_id} is {current.status.value}; the transition no longer applies"
                if otherwise is not None:
                    otherwise(reason)
                self._step_finished(job_id)
                return
            self._repository.update(
                revised, lambda error: self._settle(revised, error, then, otherwise)
            )

        self._enqueue(job_id, step)

    def _settle(
        self,
        job: Job,
        error: str | None,
        then: Callable[[], None] | None,
        otherwise: Callable[[str], None] | None,
    ) -> None:
        """Announce a durable transition and run what follows it — or run neither.

        **`then` is the whole of `T016-R3`.** Announcing from the callback while leaving the
        *other* effects on the synchronous path preserved nothing: a worker was spawned and a
        pump started while the row still said `QUEUED`, `job_succeeded` arrived while it still
        said `RUNNING`, and startup cleanup ran before `FAILED` was durable. The old synchronous
        write sequenced every following effect for free; this is that sequencing, made explicit.

        The chain is released **last**, after the effects, so anything they queue for this job
        runs behind them rather than interleaved with them.
        """
        if error is not None:
            logging.getLogger(f"{APP_SLUG}.manager").error(
                "could not persist %s as %s: %s", job.id, job.status.value, error
            )
            if otherwise is not None:
                otherwise(error)
            self.persistence_failed.emit(job.id, error)
            self._step_finished(job.id)
            return
        self.job_changed.emit(job.id, job.status.value)
        if then is not None:
            then()
        self._step_finished(job.id)


def _now() -> datetime:
    """Timezone-aware local time, matching what `persistence` stores (`T-014`)."""
    return datetime.now().astimezone()
