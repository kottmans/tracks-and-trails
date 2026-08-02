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
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from functools import partial
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

#: Sort key for a waiting job with no `queue_position` — it goes last (`T-078`).
#:
#: A literal rather than `math.inf` so the key stays `tuple[int, str]` and mypy can check it.
_UNPLACED: Final = 1 << 62

#: **Ratified by `UX-002`** (maintainer, 2026-08-01). `T-083`'s scope said the bound and the backoff
#: "need stating in `DECISIONS.md`, not choosing in code", and they now are: the decision holds the
#: reasoning, the rejected alternative, and the condition that reopens it. These values are no
#: longer provisional.
#:
#: Seconds to wait before each automatic attempt, indexed by how many have already been spent.
#: Doubling, so a site that is briefly unreachable is retried quickly and one that is down is not
#: hammered.
RETRY_BACKOFF_SECONDS: Final = (2.0, 4.0, 8.0)

#: How many automatic attempts follow the first. **Derived, not declared**: a bound and a table of
#: delays written separately are two constants that can disagree, and the one that would notice is
#: an `IndexError` inside a Qt slot. Three, because the failure this exists for is a transient
#: network one and a fourth try is evidence the problem is not transient.
AUTOMATIC_RETRY_LIMIT: Final = len(RETRY_BACKOFF_SECONDS)

#: How many probe sessions may run at once, independently of `REQ-013`'s download limit
#: (`T-116`, `UX-003`).
#:
#: **Four, and the number is a judgement about latency rather than about throughput.** A probe is
#: one metadata round trip; what a user waits for is the *last* line of their paste resolving, so
#: more lanes shorten that wait roughly linearly. Against that: every lane is a spawned
#: interpreter (`ARC-002`), so the cost is real and paid up front on a machine that may already be
#: downloading. Four resolves a twenty-line paste in five rounds while leaving the download pool
#: untouched.
DEFAULT_PROBE_CONCURRENCY: Final = 4

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


class _Unchanged:
    """What a revision returns when the job already holds what was asked for (`T075-R1`).

    Three outcomes, not two. A revision can produce a new `Job`, decline entirely (`None`), or
    find that nothing needs writing — and that third one has to be distinguishable, because it
    still has a *successor*: the caller wants its `then` to run.

    It exists because the first version of `retarget` decided this **outside** the chain, by
    reading the store and comparing before enqueuing anything. `PersistentJobStore.get()` answers
    with the newest revision this process has *queued*, durable or not, so that comparison could
    match against a write still in flight — and if that write then failed, the download started
    against the request the database actually held. Deciding it here means deciding it against the
    job as it stands when its turn comes, which is the same guarantee every other transition gets.
    """

    __slots__ = ()


#: The single instance. Compared with `is`, so a `Job` can never be mistaken for it.
UNCHANGED: Final = _Unchanged()


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

    **`requeue_at_end` and `remove` are `T-080`'s** (`UX-001`, `P2PLAN-R7`), and both are here
    rather than expressed as an `update` because both need the *database* to decide something the
    manager cannot know:

    - `requeue_at_end` writes the job **and** allocates it a fresh tail `queue_position` in one
      transaction. The tail cannot be computed here — `MAX(queue_position) + 1` is a read of the
      whole queue's ordering, and two callers computing it separately would hand out the same
      position, which a `UNIQUE` index turns into a failed write rather than a silent tie.
    - `remove` deletes the row. It is not a status: `CANCELLED` is a job that stopped and is still
      in the queue, and removal is a job that is no longer in the queue at all. **Neither touches a
      file** (`UX-001`).

    `JobRepository` alone no longer satisfies this: its `update` is synchronous and blocked the
    GUI thread for a measured 5.017 s under contention (`T016-R3`). It is now reached through
    `PersistentJobStore`, which owns that contract.
    """

    def get(self, job_id: str) -> Job | None: ...

    def update(self, job: Job, done: Callable[[str | None], None]) -> None: ...

    def complete(
        self, job: Job, format_used: str | None, done: Callable[[str | None], None]
    ) -> None: ...

    def requeue_at_end(self, job: Job, done: Callable[[str | None], None]) -> None: ...

    def remove(self, job_id: str, done: Callable[[str | None], None]) -> None: ...

    def reorder(self, job_ids: Sequence[str], done: Callable[[str | None], None]) -> None: ...

    def clear_completed(self, done: Callable[[str | None], None]) -> None: ...


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

    #: `paused` — the queue stopped starting work, or started again (`UX-001`, `T-080`).
    #:
    #: Emitted rather than polled because pause is **queue-level**: there is no job whose
    #: `job_changed` would carry it. A control that reads `is_paused` on a timer would be inventing
    #: a signal this class is better placed to send.
    queue_paused = Signal(bool)

    #: `job_id` — the job is no longer in the queue, and its row is gone (`UX-001`, `T-080`).
    #:
    #: Distinct from `job_changed`, which announces a job that still exists in a new state. A view
    #: told a removed job had "changed" would go looking for a row that is not there.
    #:
    #: **This says nothing about the filesystem**, because removal does not touch it. Whatever the
    #: job had already written is still on disk, which is `UX-001`'s rule and not an oversight.
    job_removed = Signal(str)

    #: `tuple[str, ...]` — the queue was rearranged into this order (`REQ-016`, `T-081`).
    #:
    #: Carries the order rather than being a bare "something changed", so a view can apply it
    #: without re-reading the whole queue to discover what moved — `T079-R2`'s rule about
    #: enumerations on the GUI thread applies to the refresh a reordering triggers too.
    queue_reordered = Signal(tuple)

    #: The finished jobs were cleared (`REQ-016`, `T-081`).
    #:
    #: No payload: the ids are of rows that no longer exist, and a view's only useful response is to
    #: rebuild from what is left. **History is untouched**, so this announces a smaller queue and
    #: never a smaller record of what was obtained.
    queue_cleared = Signal()

    def __init__(
        self,
        repository: JobStore,
        *,
        concurrency: int = 1,
        probe_concurrency: int = DEFAULT_PROBE_CONCURRENCY,
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
        #: How many sessions may run at once (`REQ-013`, `T-078`). Injected as a value, never read
        #: from `core/settings.py` — `ARC-007` puts the file behind composition and the UI, and
        #: `tests/unit/test_manager_boundaries.py` enforces that this module cannot reach it.
        #:
        #: Already in range when it arrives: the settings layer clamps to `[1, 16]`, so there is no
        #: second bound here. A caller constructing this object directly is trusted the same way
        #: every other constructor argument is.
        self._limit = max(concurrency, 1)
        #: How many **probe** sessions may run at once (`T-116`, `UX-003`). A separate lane from
        #: the download limit above, because the two are different work and sharing one budget
        #: means adding URLs stalls transfers already in flight.
        #:
        #: Fixed in code rather than exposed as a setting. `REQ-013` is about downloads — it is
        #: what a user throttles to protect their connection — and a second spinbox for something
        #: nobody has asked to tune would be capability without a reason. If it should be
        #: configurable, that is a decision to take rather than a default to leak.
        self._probe_limit = max(probe_concurrency, 1)

        #: Jobs accepted and waiting for a slot, in the order they will be started (`T-078`).
        #:
        #: **A list, where Phase 1 had one slot.** `_pending_retry` held exactly one job because the
        #: pool held exactly one session, and the two were the same assumption written twice. With N
        #: slots a retry can be waiting behind another retry, and a lowered limit can leave several
        #: jobs waiting at once.
        self._waiting: list[str] = []
        #: Jobs whose automatic retry is waiting for its backoff to expire, and when it does
        #: (`T-083`). Held on the tick rather than on a timer per job, for the reason every other
        #: deadline in this class is: one place where the lifetime rules are applied.
        self._retry_at: dict[str, float] = {}
        #: What to restart, for a job whose start is deferred — parked behind pause, a slot,
        #: a reorder barrier, or a retry's backoff (`T083-R1`). Absent means `DOWNLOAD`, which
        #: is what every deferred start was silently assumed to be until a retried **probe**
        #: came back as a download and began writing media nobody had confirmed.
        self._intended_kind: dict[str, SessionKind] = {}
        #: Whether the queue is paused (`UX-001`, `T-080`). **Not a job status** — that is the whole
        #: decision. Pause governs what this manager *starts*; it never changes a job, which is why
        #: `T-080` could delete `JobStatus.PAUSED` outright.
        self._paused = False
        #: Jobs asked to be removed whose session has not ended yet (`T-080`). Removal of a running
        #: job is a cancel followed by a delete, and the delete cannot happen until the process is
        #: gone — a row deleted out from under a live session leaves `_require` raising on the next
        #: message it sends.
        self._remove_when_done: set[str] = set()
        #: Reorders queued and not yet settled (`T081-R1`). **A count, not a flag** — two can be in
        #: flight, and a boolean cleared by the first callback reopens the admission window while
        #: the second is still running.
        self._reorders_in_flight = 0
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
    def concurrency(self) -> int:
        """How many sessions may run at once (`REQ-013`)."""
        return self._limit

    def set_concurrency(self, limit: int) -> None:
        """Change the limit while running. **Lowering drains; raising starts waiting jobs now.**

        `UX-001` chose draining for pause and the same reasoning applies here: a running download is
        work the user asked for, and stopping it buys a half-written file plus a rule about what
        happens to it, in a phase where `REQ-017`'s resume does not exist. So the new limit governs
        **what starts next**, never what is already running — lowering to 1 with three in flight
        leaves three in flight and starts nothing until two have finished.

        Raising fills the free slots **immediately** rather than on the next tick. `T-078`'s
        criterion says "without waiting for a tick that happens to fire", and a tick is up to
        `poll_interval_ms` away — which is invisible in a test that spins the event loop and
        perfectly visible to someone who just moved a spinbox.

        The value arrives already bounded; `core/settings.py` clamps to `[1, 16]` and this module
        never reads that file (`ARC-007`). `max(..., 1)` here is a floor against a direct caller,
        not a second opinion about the requirement.
        """
        self._limit = max(limit, 1)
        if not self._shutting_down:
            self._fill_free_slots()

    # --- queue-level pause (`UX-001`) ---------------------------------------------------

    @property
    def is_paused(self) -> bool:
        """Whether the queue is paused. **A property of the queue, never of a job** (`UX-001`)."""
        return self._paused

    def pause(self) -> None:
        """Stop starting work. **In-flight sessions finish; nothing new begins** (`UX-001`).

        This is `set_concurrency(0)` in spirit and deliberately not in fact: the limit stays what
        the user chose, so resuming restores it without having to remember it. What pause changes
        is whether `_fill_free_slots` is willing to spend a slot at all.

        **Nothing is asked to stop, and no job's status changes.** `UX-001` chose draining because
        every alternative buys a half-written file plus a rule about its lifetime, in a phase where
        `REQ-017`'s resume does not exist — so there is no partial file to have a rule about. That
        is also why `T-080` removed `JobStatus.PAUSED`: a paused queue has running jobs and waiting
        jobs, and no job in a paused state.

        A direct `start()` — the add-URL dialog's probe — is **not** governed by this. Pause is
        about the queue draining, and a probe the user just asked for by typing a URL is not queue
        work waiting for a slot. Silently refusing it would make the dialog hang on "Probing …"
        with nothing to say why.

        Idempotent, and refused during shutdown: a queue that is already ending is not a queue to
        pause, and pausing it would be a second reason nothing starts, with only one of them ever
        cleared.
        """
        if self._paused or self._shutting_down:
            return
        self._paused = True
        self.queue_paused.emit(True)

    def resume(self) -> None:
        """Start taking work again, filling every free slot **now** (`UX-001`).

        Immediately rather than on the next tick, for `set_concurrency`'s reason: a tick is up to
        `poll_interval_ms` away, which is invisible to a test that spins the event loop and
        perfectly visible to somebody who just pressed Resume.
        """
        if not self._paused:
            return
        self._paused = False
        self.queue_paused.emit(False)
        if not self._shutting_down:
            self._fill_free_slots()

    # --- removal (`UX-001`) -------------------------------------------------------------

    def remove(self, job_id: str) -> None:
        """Take `job_id` out of the queue. **Never deletes a file** (`UX-001`, `REQ-015`).

        **Removing a running job cancels it first**, and the row is deleted when the session has
        actually ended rather than when the cancel is asked for. Deleting it immediately would
        leave a live worker whose every message reaches `_require` and finds nothing — the job
        would be gone from the queue and still writing to disk, which is the opposite of what the
        user asked for. The cancel keeps its full escalation and its 2-second budget; removal adds
        the delete behind it.

        A job that is merely waiting for a slot is dropped from the waiting list too, so a removed
        job cannot be started by the tick that fires between the delete being queued and landing.

        **What survives is the file**, deliberately. `UX-001`: remove takes the job out of the
        queue, and nothing this application deletes from disk goes by this route. `T-085`'s history
        keeps a completed job's record even after its queue row is gone.

        *(This added "a partially written file from a cancelled download is the user's to delete".
        That stopped being true with `T046-R1`: the download happens in a staging directory which
        is discarded whatever the outcome, so **a cancelled job leaves no partial at all**. What
        this method promises is unchanged — it deletes nothing — but the sentence described a file
        that no longer exists. `REQ-017` and `T-113` own partial-file lifetime when resume lands.)*
        """
        self._discard_waiting(job_id)
        self._retry_at.pop(job_id, None)

        session = self._sessions.get(job_id)
        if session is not None:
            # Cancel owns the stopping; `_release` owns what happens after it. Recorded before the
            # cancel so a session that ends synchronously inside it still finds the intent.
            self._remove_when_done.add(job_id)
            self.cancel(job_id)
            return

        reservation = self._reserved.get(job_id)
        if reservation is not None and not reservation.withdrawn:
            # A reservation has no process to wait for: withdrawing it is what stops the worker
            # from ever being spawned (`T016-R1`), so there is no session that will reach
            # `_release` and no reason to defer. The delete is enqueued on the same chain as the
            # cancel's write and therefore lands behind it.
            self.cancel(job_id)
        self._delete_row(job_id)

    # --- reordering and clearing (`REQ-016`, `T-081`) -----------------------------------

    def reorder(self, job_ids: Sequence[str]) -> None:
        """Rearrange the pending jobs into `job_ids`' order (`REQ-016`).

        **Through the manager rather than through the store**, which is `T036-R1`'s rule and not a
        formality here: `_next_waiting` reads `queue_position` to decide what starts next, so a
        reordering that composition wrote directly would change the scheduler's mind with nothing
        announcing it, and the table would keep showing the order the user replaced.

        **What is reordered is checked by the repository, not here.** `REORDERABLE` is a fact about
        stored status and the transaction that rewrites the positions is the only place it can be
        read without a race — a check on this side would be reading a status that the write it
        guards may invalidate before it lands.

        A failure is surfaced through `persistence_failed` and the order is unchanged, which is
        what `REQ-016`'s single-transaction criterion buys: there is no half-reordered outcome to
        report.

        **An in-flight reorder is an admission barrier** (`T081-R1`). `ARC-005`'s single writer
        serialises the *writes* and does nothing about the scheduling *read* that precedes one:
        while a reorder is on the writer thread, a tick, `resume()` or `set_concurrency()` can run
        `_next_waiting()` against the positions the reorder is replacing, pick the old head, and
        queue its start. Both writes then succeed — the reorder first, because FIFO — and the queue
        durably says one thing while the job that actually started says another. Ordering the
        transactions differently cannot fix it, because the wrong decision was already made before
        either was queued.

        So nothing is admitted from the waiting list until every outstanding reorder has settled.
        **A counter rather than a flag**: two reorders can be in flight, and a boolean cleared by
        the first callback would reopen the window while the second was still running.
        """
        if not job_ids:
            return
        self._reorders_in_flight += 1
        self._repository.reorder(
            list(job_ids), lambda error: self._settle_reorder(list(job_ids), error)
        )

    def _settle_reorder(self, job_ids: list[str], error: str | None) -> None:
        """Release this reorder's hold on admission, then report what happened.

        The barrier is released on **both** paths. A refused reorder leaves the stored order
        exactly as it was, so there is nothing to wait for and holding the queue shut would turn a
        failed write into a stalled pool.
        """
        self._reorders_in_flight = max(0, self._reorders_in_flight - 1)
        if error is not None:
            logging.getLogger(f"{APP_SLUG}.manager").error("could not reorder the queue: %s", error)
            self.persistence_failed.emit(job_ids[0], error)
        else:
            self.queue_reordered.emit(tuple(job_ids))
        # Whatever the outcome, scheduling was suspended while this was in flight and the durable
        # order is now settled. Filling here is what makes the barrier a delay rather than a drop.
        #
        # **It fills from the intents already admitted, and only those** (`T081-R4`). A correction
        # briefly promoted every reordered row into `_waiting` on the reasoning that ordering some
        # jobs is a statement about what should run — it is not. Startup recovery deliberately
        # leaves `QUEUED` rows dormant (`T-014`, `NFR-003`), so a reorder naming one of them started
        # an unattended download for a job nobody had asked for. Reordering admitted work is not
        # permission to start work that was never admitted.
        #
        # The new positions are used only to *order* the set that was already waiting, which is
        # what `_next_waiting` does with them.
        if not self._shutting_down:
            self._fill_free_slots()

    def clear_completed(self) -> None:
        """Remove every finished job from the queue. **Never deletes a file** (`REQ-016`).

        Completed and cancelled rows go; a failed job stays, because it is still offering a retry.
        `JobRepository.clear_completed` owns that line and this does not restate it.

        **This used to sweep the waiting list afterwards, and no longer does** (`T-103`). The sweep
        existed because `cancel()` left a cancelled job's id on `_waiting`: harmless while the row
        was there — the pool's later `start()` simply refused — and not harmless once clearing
        deleted it, at which point the same path reached `_require` with nothing to find.

        `T-103` fixed that at the cause: `cancel()` now discards the id when the job is cancelled.
        Every path that can delete a waiting job's row — `remove()` and this one — drops it from
        the list first, so a sweep here could no longer fire. Keeping it would be a guard whose
        reason has gone and which no test can distinguish from working, which is
        `ai/TESTING.md` §13's shape.
        """
        self._repository.clear_completed(self._settle_clear)

    def _settle_clear(self, error: str | None) -> None:
        if error is not None:
            logging.getLogger(f"{APP_SLUG}.manager").error(
                "could not clear finished jobs: %s", error
            )
            self.persistence_failed.emit("", error)
            return
        self.queue_cleared.emit()

    def _delete_row(self, job_id: str) -> None:
        """Delete the job's row and announce it, through the same chain every write uses.

        Queued on `_Chain` like any other write, so a removal asked for while a transition is still
        in flight for this job lands *after* it rather than racing it. A delete that overtook a
        pending `CANCELLED` write would be followed by that write recreating nothing — `update`
        raises when the row is gone — and the failure would surface as a persistence error for a
        job the user had already removed.
        """

        def step() -> None:
            self._remove_when_done.discard(job_id)
            self._repository.remove(job_id, lambda error: self._settle_removal(job_id, error))

        self._enqueue(job_id, step)

    def _settle_removal(self, job_id: str, error: str | None) -> None:
        """Announce a durable removal, or report that it did not happen."""
        if error is not None:
            logging.getLogger(f"{APP_SLUG}.manager").error(
                "could not remove %s from the queue: %s", job_id, error
            )
            self.persistence_failed.emit(job_id, error)
            self._step_finished(job_id)
            return
        self.job_removed.emit(job_id)
        self._step_finished(job_id)

    @property
    def is_idle(self) -> bool:
        """Nothing is running **and nothing is about to be** (`T016-R3`).

        A reserved start counts. It used to not, so `idle` could go out while a start's write was
        still on the writer thread — and composition (`T-036`) treats that signal as permission
        to quit, which would have quit into a callback that then spawned a worker.

        So does a job waiting for a slot (`T036-R1`, generalised by `T-078`): it is work this
        manager has accepted and will begin. `shutdown()` drops the whole waiting list, which is
        what stops it from holding the door.
        """
        return (
            not self._sessions and not self._reserved and not self._waiting and not self._retry_at
        )

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
        """Every job this manager is holding: running, reserved, **or waiting for a slot**.

        Sorted so the answer does not depend on which of the three collections an id happens to be
        in — a caller that saw a job appear, vanish, and reappear as its start became a session
        would be watching bookkeeping rather than the job (`T016-R3`). A set first, so an id that
        is briefly in two collections is reported once.

        Waiting jobs count because this manager has **accepted** them (`T078-R1`). They are the
        same commitment a reservation is, one step earlier: nobody else will start them, they are
        why `is_idle` is false, and a caller asking what this manager is holding is asking a
        question the waiting list is part of the answer to. Leaving them out made the method
        contradict its own first sentence.

        **This is not the occupancy count.** A waiting job holds no slot, so capacity and the
        diagnostics about capacity use `_occupant_ids()` instead.
        """
        return tuple(sorted(set(self._sessions) | set(self._reserved) | set(self._waiting)))

    def _occupant_ids(self, kind: SessionKind | None = None) -> tuple[str, ...]:
        """The jobs holding a slot — running sessions and reservations, never waiting jobs.

        Split from `active_job_ids()` by `T078-R1`. The public accounting answers "what is this
        manager holding"; this answers "what is filling the pool", and the two stopped being the
        same question when the waiting list arrived. Using the wrong one would make `start()`'s
        refusal name jobs that are not occupying anything and are, in fact, waiting for exactly
        the slot the caller wanted.

        **`kind` narrows it to one lane** (`T-116`). A refusal names the lane it is about, so a
        caller refused a probe is not handed the ids of three running downloads as the reason.
        `None` keeps the whole-pool answer, which is what shutdown and the diagnostics want.
        """
        occupying = set(self._sessions) | set(self._reserved)
        if kind is None:
            return tuple(sorted(occupying))
        return tuple(
            sorted(job_id for job_id in occupying if self._kind_of(job_id) is kind),
        )

    def _kind_of(self, job_id: str) -> SessionKind | None:
        """What kind of session `job_id` holds a slot with, or `None` if it holds none."""
        session = self._sessions.get(job_id)
        if session is not None:
            return session.kind
        pending = self._reserved.get(job_id)
        return pending.kind if pending is not None else None

    # --- starting -----------------------------------------------------------------------

    def admit(self, job_id: str, kind: SessionKind = SessionKind.DOWNLOAD) -> None:
        """Take responsibility for running `job_id` **when the queue can** (`T-115`, `REQ-012`).

        The public counterpart to `start()`, and the difference is the whole point of `T-115`:
        `start()` **raises** when the pool is full, because its caller asked for a session *now* and
        deserves to be told it cannot have one. `admit()` expresses durable intent instead — run
        this when there is room — so a caller adding five URLs to a pool of three does not have to
        decide which two to drop on the floor.

        Before this existed nothing drained the queue. `_fill_free_slots` drains `_waiting`, which
        is in-memory and was only ever populated by an internal parking path; `start()` refused at
        saturation; and the add dialog started only the job it had probed. So five URLs and a limit
        of three left two `QUEUED` for ever, and five URLs with no probe started nothing at all.

        **Ordering is `queue_position`'s**, through `_next_waiting` — not arrival, and not this
        call. That is what survives a restart and what the queue view already shows.

        **A paused queue admits and starts nothing** (`UX-001`): `_start_when_free` parks it, and
        `resume()` drains. Admission is not a start; it is a claim on the next free slot.

        **A row this manager cannot see is reported, not raised.** `start()` raises for it, and is
        right to: its caller asked for a session on a specific job and a vanished row means their
        model of the queue is wrong. `admit()` is called from Qt slots — the add dialog's save
        callback, and composition's startup loop — where an exception is printed and swallowed, and
        where the row may simply not have landed yet. `start_rejected` is the channel every other
        refusal already uses and the dialog already listens to.

        **`kind` is here because probing needed the same door** (`T-116`, `UX-003`). The only public
        route to a probe was `start(job_id, PROBE)`, which raises when the lane is full — correct
        while probing was a button covering one URL, and useless once pasting twenty URLs probes
        all twenty. A caller pasting a batch is expressing the same durable intent a caller adding
        one is, and should no more have to decide which probes to drop.
        """
        try:
            self._start_when_free(job_id, kind)
        except KeyError as missing:
            self.start_rejected.emit(job_id, f"this job is not in the queue: {missing}")

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
        if not self._has_capacity(kind):
            # **Reservations count against the limit, not just running sessions** (`T016-R3`).
            # `_reserved` holds starts whose transition is still on the writer thread; without
            # counting them the limit would be "N plus however many `start()` calls fit between a
            # write and its completion" — the gap `ARC-005` created, and the reason `T016-R1`
            # measured a missed reservation as a real defect rather than a tidiness one.
            # Occupants, not everything held (`T078-R1`). A caller told "the pool is full at 3"
            # and then handed a list including jobs that are themselves waiting for a slot would
            # be reading a contradiction.
            #
            # **The lane is named** (`T-116`). With two of them, "the pool is full at 3" while
            # three downloads run and a probe was refused would be true of a limit the caller
            # never asked about.
            busy = self._occupant_ids(kind)
            raise RuntimeError(
                f"the {kind.value} lane is full at {self._limit_for(kind)}: {busy}. "
                "Raise the concurrency limit, or wait for a slot"
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

        # **A paused queue admits a probe and parks a download** (`T080-R1`, `UX-001`).
        #
        # The pause guards used to sit only on `_fill_free_slots` and `_start_when_free`, so this
        # public entry point walked straight past them. That is not a hypothetical hole: the
        # add-URL dialog calls `start(job_id)` after a probe resolves, and its default `kind` is
        # `DOWNLOAD` — so pressing Add while the queue was paused started a download immediately.
        # **The test that was supposed to cover this protected the defect**: it described a probe
        # and called `start("job-1")`, taking the same default, so it asserted that a paused queue
        # starts a *download* and called that the probe exemption.
        #
        # Parked rather than refused, because a refusal has nowhere to put the user's intent. The
        # job is already durably `QUEUED`; adding it to the waiting list means resume starts it,
        # which is what somebody who queued work while paused meant to happen.
        # **Every DOWNLOAD admission goes through the same two rules** (`T080-R1`, `T081-R1`).
        #
        # The first correction put the pause guard here and the reorder barrier only on
        # `_fill_free_slots` and `_start_when_free` — so the public path honoured one and walked
        # past the other. The add-dialog seam uses exactly this entry point, so starting a job by
        # hand while a reorder was in flight admitted it against the positions the reorder was
        # replacing: both writes then succeeded and the durable order named a different job first.
        #
        # Parked rather than refused, for pause's reason: the job is already durably `QUEUED`, so
        # the waiting list is where the intent belongs until the queue can honour it. `resume()`
        # and `_settle_reorder` both fill from durable positions afterwards.
        #
        # **The PROBE exemption is explicit and applies to both rules.** A metadata probe is not
        # queue work waiting for a slot — it neither depends on `queue_position` nor changes it —
        # and refusing it silently hangs the add dialog on "Probing ...".
        if kind is SessionKind.DOWNLOAD and (self._paused or self._reorders_in_flight):
            if job_id not in self._waiting:
                self._waiting.append(job_id)
            self._intended_kind[job_id] = kind
            # No reservation to withdraw: this runs before one is taken, which is the point of
            # placing the guard here rather than inside the write's callback.
            self._timer.start()
            return

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

        # **A cancelled job stops waiting for a slot** (`T-103`). This used to be left behind: the
        # id stayed on `_waiting`, the next free slot picked it, and `start()` refused it because a
        # `CANCELLED` job is not startable. Harmless while the row existed — one swallowed refusal
        # — and no longer harmless once `T-081`'s clear-finished deletes that row, at which point
        # the same path reaches `_require` with an id that resolves to nothing.
        #
        # It also costs correctness in its own right: `is_idle` counts waiting jobs, so a queue
        # whose only waiting job had been cancelled held the shutdown door open until a slot
        # happened to free.
        self._discard_waiting(job_id)
        # **No `_retry_at` pop here, and that is deliberate.** A job awaiting an automatic retry is
        # `FAILED`, and `FAILED` allows only `QUEUED` — so cancelling one raises out of the state
        # machine and this line could never run. `T010-R3` settled that on purpose: cancelling stops
        # in-flight work and a failed job has none; **removing** it is the action that applies, and
        # `remove()` does drop the pending retry. A pop here was in the first version of `T-103` and
        # came out when a mutation showed nothing could reach it (`ai/TESTING.md` §13).

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

        def revise(candidate: Job) -> Job | _Unchanged | None:
            if candidate.status not in Job.RETARGETABLE:
                return None
            if candidate.request == request:
                # **Already what was asked for, so no write** — decided here rather than before
                # enqueuing (`T075-R1`). `DownloadRequest` is frozen, so this is a structural
                # comparison; what matters is *when* it happens. Outside the chain it could match
                # a revision still in flight, and a failed write would then leave the download
                # running against the request the database actually held.
                #
                # Skipping the write is still worth doing: it would add a second `READY` revision
                # to every probed job's history for no change, and
                # `test_a_probed_job_downloads_from_ready_without_re_entering_probing` asserts
                # that history as a sequence (`ARC-004`).
                return UNCHANGED
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

        **It re-enters the queue at the back** (`P2PLAN-R7`, confirmed 2026-07-31 by maintainer
        decision). A failed job keeps the `queue_position` it was given when it was added, which is
        *earlier* than everything queued since — so re-queuing it in place would let a job the user
        retried on its second attempt run ahead of jobs that have never run at all.

        **Written as a new position rather than as a scheduling rule, and the difference is
        visible.** `_next_waiting` already sorts automatic retries last using `Job.attempts`, and
        reusing that here does not work: `with_another_attempt` is spent by *automatic* retry only,
        so a manual retry leaves `attempts` at whatever it was and a first manual retry would sort
        as "never run". Renumbering also keeps the table honest — `T-081`'s criterion is that the
        order the pool starts jobs in is the order the table shows, and a scheduling rule the
        `queue_position` column disagrees with is a view that lies about what happens next.

        The tail is allocated inside the write's transaction (`JobStore.requeue_at_end`), not read
        here and passed in: `queue_position` carries a `UNIQUE` index, and two callers computing
        `MAX + 1` separately would collide rather than tie.
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
            write=self._repository.requeue_at_end,
        )

    def _limit_for(self, kind: SessionKind) -> int:
        """The ceiling on `kind`'s lane. **Two lanes, not one budget** (`T-116`)."""
        return self._probe_limit if kind is SessionKind.PROBE else self._limit

    def _occupancy(self, kind: SessionKind) -> int:
        """How much of `kind`'s lane is taken — running sessions and reservations alike."""
        running = sum(1 for session in self._sessions.values() if session.kind is kind)
        reserved = sum(1 for pending in self._reserved.values() if pending.kind is kind)
        return running + reserved

    def _has_capacity(self, kind: SessionKind = SessionKind.DOWNLOAD) -> bool:
        """Whether another session of `kind` may start right now.

        Running sessions **and** reservations both occupy a slot. A reservation is a start whose
        transition has not landed yet, so it has no process — but it will, and counting only
        processes is what let the pool of one become a pool of several between a write and its
        callback (`T016-R3`).

        **The two kinds draw on separate lanes** (`T-116`, `UX-003`). This counted every session
        against `REQ-013`'s single limit, so a probe took a download slot. That was tolerable while
        probing was a button covering one URL; `UX-003` makes probing what happens when a user
        pastes, and under one budget pressing Add would stall the downloads already running —
        measured, with a limit of three and twenty URLs added, as the twentieth being probed only
        after the nineteenth had finished downloading.

        They are different work: a probe is one short metadata round trip, a download is
        bandwidth-bound and long. `REQ-013`'s setting still governs downloads and nothing else.
        """
        return self._occupancy(kind) < self._limit_for(kind)

    def _discard_waiting(self, job_id: str) -> None:
        """Forget `job_id` is waiting, wherever in the list it sits.

        By value rather than by position: a job can be started directly while another is queued
        ahead of it, and `list.remove` on a missing id would raise rather than say "it was not
        waiting", which is an ordinary state here.
        """
        if job_id in self._waiting:
            self._waiting.remove(job_id)
        self._intended_kind.pop(job_id, None)

    def _fill_free_slots(self) -> None:
        """Start waiting jobs while there is room, in the order the queue defines (`T-078`).

        **The order is `queue_position`, not arrival.** `queue_position` is allocated inside the
        insert transaction (`JobRepository.append`), so it is the only ordering that survives a
        restart and the only one two callers cannot disagree about. A job whose row has gone, or
        which has no position, sorts last on its id — deterministic rather than incidental, so a
        test comparing whole lists is comparing something real.

        Called from the tick, from `set_concurrency`, **and from `resume`** — which is what makes a
        raised limit, or an un-paused queue, take effect at once rather than on whichever tick
        happens next. `T-078`'s criterion says "without waiting for a tick that happens to fire",
        and sharing this is how all three paths keep the same promise.

        **A paused queue starts nothing** (`UX-001`, `T-080`). The guard is here rather than at the
        call sites because this is the single place a waiting job becomes a running one; a check
        spread across the tick, `set_concurrency` and `resume` would be three chances to forget it,
        and the tick is the one that fires on its own.

        **A full download lane no longer stops a waiting probe** (`T-116`). The loop used to end
        at the first job it could not start, which was correct with one budget and starves the
        other lane with two: a probe sitting behind three running downloads would wait for a
        download to finish, which is the delay `UX-003` exists to remove. It now takes the next
        job *that can start*, and ends when no waiting job can.
        """
        if self._shutting_down or self._paused or self._reorders_in_flight:
            return
        while True:
            job_id = self._next_startable()
            if job_id is None:
                return
            self._waiting.remove(job_id)
            self._start_or_report(job_id)

    def _next_startable(self) -> str | None:
        """The waiting job that should start next, or `None` if none of them can.

        Ordering is `_next_waiting`'s and unchanged; the filter is what `T-116` adds. A job whose
        lane is full is skipped rather than blocking the ones behind it, so the two lanes drain
        independently while each stays in `queue_position` order within itself.
        """
        startable = [job_id for job_id in self._waiting if self._has_capacity(self._wants(job_id))]
        return min(startable, key=self._waiting_order) if startable else None

    def _wants(self, job_id: str) -> SessionKind:
        """The kind a deferred start recorded for `job_id` (`T083-R1`).

        `DOWNLOAD` when nothing was recorded, which is what every deferred start was silently
        assumed to be until a retried probe came back as a download.
        """
        return self._intended_kind.get(job_id, SessionKind.DOWNLOAD)

    def _waiting_order(self, job_id: str) -> tuple[int, int, str]:
        """The sort key deciding what starts next: has it run, its position, then its id."""
        job = self._repository.get(job_id)
        # **A retry never jumps the queue ahead of jobs that have not run** (`T-083`). A
        # re-queued job keeps its original `queue_position`, which is *earlier* than
        # everything added since — so ordering on position alone would let one job's third
        # attempt run before another job's first. Sorted on "has this run" first, which is
        # data already on the row rather than a renumbering that would have to enumerate the
        # queue to find its tail (`T079-R2`).
        attempted = 1 if job is not None and job.attempts > 0 else 0
        position = job.queue_position if job is not None else None
        # `None` sorts last explicitly rather than relying on a comparison that would raise.
        return (attempted, position if position is not None else _UNPLACED, job_id)

    def _next_waiting(self) -> str:
        """The waiting job with the lowest `queue_position`; ties and absences break on id.

        **Unfiltered, unlike `_next_startable`.** This answers "what is at the head of the queue",
        which is the question the reordering and retry-ordering tests ask of it; whether that job's
        lane happens to have room is a separate one.
        """
        return min(self._waiting, key=self._waiting_order)

    def _start_when_free(self, job_id: str, kind: SessionKind = SessionKind.DOWNLOAD) -> None:
        """Start `job_id` now, or queue it for the first moment a slot opens.

        **A paused queue always parks it**, even with the pool empty (`UX-001`). This is the path a
        retry takes — manual through `retry()`, automatic through `_perform_due_retries` — so
        without the check a `NETWORK` failure would restart itself while the user had the queue
        paused, which is precisely the work pause exists to stop.
        """
        if self._shutting_down:
            return
        if self._paused or self._reorders_in_flight or not self._has_capacity(kind):
            if job_id not in self._waiting:
                self._waiting.append(job_id)
            self._intended_kind[job_id] = kind
            # The tick is what will notice; without this the timer may not be running at all.
            self._timer.start()
            return
        self._discard_waiting(job_id)
        self._start_or_report(job_id, kind)

    def _start_or_report(self, job_id: str, kind: SessionKind | None = None) -> None:
        """Start `job_id`, reporting a refusal rather than swallowing it.

        Reported, not swallowed. `start_rejected` is the asynchronous half of `start()`'s answer and
        the dialog already listens to it; a job that cannot start has exactly the same shape as a
        probe that cannot.

        **`kind` defaults to what the deferred start recorded**, not to `DOWNLOAD` (`T083-R1`).
        `_fill_free_slots` reaches this with no kind of its own, so taking `start`'s default here
        is what turned a parked probe into a download the moment a slot opened.
        """
        if kind is None:
            kind = self._intended_kind.pop(job_id, SessionKind.DOWNLOAD)
        else:
            self._intended_kind.pop(job_id, None)
        try:
            self.start(job_id, kind)
        except (RuntimeError, ValueError) as refusal:
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
        # Work accepted but not started never will be. Dropped rather than carried, so `idle` is
        # not held open by work this manager has just decided not to do (`T036-R1`).
        self._waiting.clear()
        # A retry this manager decided on but has not started never will be (`T-083`), and
        # holding `idle` open for one would stop the application quitting.
        self._retry_at.clear()
        # Reserved starts as well as running sessions (`T016-R3`). A start whose transition is
        # still on the writer thread has no process to cancel yet, and skipping it here is how
        # shutdown used to announce `idle` and then spawn a worker from the callback that
        # arrived afterwards.
        # Occupants (`T078-R1`). Cancelling is for work that has a process or is about to get
        # one; the waiting list was just dropped above and has nothing to stop. Naming that
        # directly rather than relying on the `clear()` above having already emptied it — the
        # cancel loop should not depend on the order of two statements to stay correct.
        for job_id in self._occupant_ids():
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

        self._perform_due_retries(now)
        self._fill_free_slots()

        if self._sessions or self._reserved or self._waiting or self._retry_at:
            # A reservation counts as work in flight (`T016-R3`). Its transition is still on the
            # writer thread, and the callback that settles it is what decides whether a worker
            # appears — so `idle` here would be a promise this manager cannot keep. A job waiting
            # for a slot is the same claim.
            #
            # **So is a retry whose backoff has not expired** (`T-083`), and this is the line that
            # makes the backoff work at all rather than merely be recorded. The tick is the only
            # thing that will notice the deadline, so stopping the timer here strands it: measured
            # with a one-second backoff, where the timer stopped on the tick after the failure and
            # the retry never fired. A 50 ms backoff hid it completely, because the deadline had
            # already passed by the time this line was reached.
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
        if session.job_id in self._remove_when_done:
            # **Here rather than in `remove()`, because here is where the process is actually
            # gone** (`T-080`). Deleting the row when the cancel was *asked for* would leave a live
            # worker whose next message reaches `_require` and finds nothing. By this point the
            # tree is reaped, the pump has returned and the session is dropped, so the delete
            # queues behind the cancel's own terminal write and nothing else will look for the row.
            self._delete_row(session.job_id)

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
            # evidence that the *cooperative* path ran (`REQ-015`). The generic text is for a
            # worker that was killed before it could say anything, where claiming a clean stop
            # would be a guess.
            #
            # *(This said the cooperative path "left partial files in a known state". Since
            # `T046-R1` the download runs in a staging directory that is discarded either way, so
            # there is no partial to be in any state — and the message is now the **only** evidence
            # that the unwind was cooperative rather than forced, which is why the cancel test
            # asserts it instead of a `.part` file.)*
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
                # One transaction for the job row and its history row (`T050-R1`). The
                # announcement stays in `then`, so it fires only after that transaction commits —
                # there is no instant where the user is told it succeeded and the record is missing.
                write=lambda job, done: self._repository.complete(job, outcome.format_used, done),
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
                then=lambda: self._failed_and_maybe_retry(
                    job_id, outcome.kind, outcome.message, session.kind
                ),
            )

    def _failed_and_maybe_retry(
        self, job_id: str, kind: ErrorKind, message: str, session_kind: SessionKind
    ) -> None:
        """Announce the failure, then decide whether this queue will try again (`T-083`).

        **The announcement comes first and is unconditional.** A job that will be retried has
        still failed, and `REQ-018` records failures rather than hiding the ones that turn out to
        be temporary — a view that showed nothing until the last attempt would leave a user
        watching a job do nothing for fourteen seconds.

        **`session_kind` is what failed, and it is what will be retried** (`T083-R1`). Without it
        a transient failure during a *metadata probe* came back as a `DOWNLOAD`, because that is
        `start`'s default — so a preview the user was still deciding about began writing media.
        """
        self.job_failed.emit(job_id, kind, message)
        self._schedule_automatic_retry(job_id, kind, session_kind)

    def _schedule_automatic_retry(
        self, job_id: str, kind: ErrorKind, session_kind: SessionKind = SessionKind.DOWNLOAD
    ) -> None:
        """Queue an automatic attempt if this failure is one worth repeating (`REQ-018`).

        **`NETWORK` only, and the narrowness is the point.** An `UNSUPPORTED_URL` retried on a
        timer is a request the site will refuse identically, forever; `DRM_PROTECTED` is a
        workaround this product exists to refuse (`SEC-001`, `REQ-EXCL-001`). `is_retryable`
        governs whether a *person* may retry, which is a wider question — it says a failure is
        not final, not that repeating it unattended is useful. Deriving one from the other would
        put `WORKER_CRASH` into a loop on its own.
        """
        if kind is not ErrorKind.NETWORK or self._shutting_down:
            return
        job = self._repository.get(job_id)
        if job is None or job.attempts >= AUTOMATIC_RETRY_LIMIT:
            return
        self._retry_at[job_id] = time.monotonic() + RETRY_BACKOFF_SECONDS[job.attempts]
        # **The operation is remembered with the deadline** (`T083-R1`). `_retry_at` used to
        # hold only `job_id -> when`, so the tick had nothing to say *what* to restart and
        # `start`'s default turned every retried probe into a download.
        self._intended_kind[job_id] = session_kind
        # The tick is what will notice; without this the timer may not be running at all.
        self._timer.start()

    def _perform_due_retries(self, now: float) -> None:
        """Re-queue every job whose backoff has expired. Called from the tick."""
        if self._shutting_down:
            return
        for job_id in [job_id for job_id, due in self._retry_at.items() if now >= due]:
            del self._retry_at[job_id]
            self._persist(
                job_id,
                lambda current: (
                    current.with_status(JobStatus.QUEUED).with_another_attempt()
                    if current.status is JobStatus.FAILED
                    else None
                ),
                # `partial` rather than a lambda with a default argument: the latter is a
                # late-binding workaround mypy cannot type, and this loop rebinds `job_id`.
                # The kind is the one that failed (`T083-R1`), read back rather than defaulted.
                then=partial(
                    self._start_when_free,
                    job_id,
                    self._intended_kind.get(job_id, SessionKind.DOWNLOAD),
                ),
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
        revise: Callable[[Job], Job | _Unchanged | None],
        *,
        then: Callable[[], None] | None = None,
        otherwise: Callable[[str], None] | None = None,
        write: Callable[[Job, Callable[[str | None], None]], None] | None = None,
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

        **`write` overrides which persistence operation is used** (`T050-R1`). It defaults to
        `JobStore.update`; the completion branch passes `JobStore.complete`, which writes the job
        row and its history row in one transaction. It is a parameter rather than a second method
        here because everything else about the step — computing the revision when its turn comes,
        settling, chain release, failure handling — is identical, and duplicating that is how the
        two writes drifted into two transactions in the first place.

        A failed write is surfaced rather than swallowed, and **the success-side effect does not
        run**. It is deliberately not turned into a job failure: the download itself may be
        running perfectly, and the honest report is that the queue's record of it is behind.
        Recovery re-queues an interrupted job at the next startup (`NFR-003`).
        """

        def step() -> None:
            current = self._require(job_id)
            revised = revise(current)
            if revised is UNCHANGED:
                # Nothing to write, and a successor to run. The chain is released last, as in
                # `_settle`, so anything `then` queues for this job runs behind it.
                if then is not None:
                    then()
                self._step_finished(job_id)
                return
            if revised is None:
                reason = f"{job_id} is {current.status.value}; the transition no longer applies"
                if otherwise is not None:
                    otherwise(reason)
                self._step_finished(job_id)
                return
            assert isinstance(revised, Job)  # narrowed by the two checks above, for mypy
            persist = write if write is not None else self._repository.update
            persist(revised, lambda error: self._settle(revised, error, then, otherwise))

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
