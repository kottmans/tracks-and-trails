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
from uuid import uuid4

from PySide6.QtCore import QObject, QTimer, Signal

from tracks_and_trails.core import logging as app_logging
from tracks_and_trails.core import output_template
from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus, can_transition, is_terminal
from tracks_and_trails.core.models import DownloadRequest, Job, MediaInfo, Preset
from tracks_and_trails.core.output_template import OutputPreview
from tracks_and_trails.core.paths import APP_SLUG, UnsafePathError, contained_output_path
from tracks_and_trails.downloader import process_tree, worker
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

    #: `(job_id, status)` for a **staging** job, which is not queue work (`T118-R1`).
    #:
    #: Separate from `job_changed` because everything listening to that one treats what it hears as
    #: a row in the queue. Composition watches the first watchable transition it sees and shows its
    #: progress; the queue model looks the id up in the repository. A staged job is in neither, so
    #: announcing it on the same channel made the window latch its progress view onto a transient
    #: id and sit there — the download completed and the view still said "ready".
    staged_changed = Signal(str, str)

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

    #: `running` — the queue started taking work, or stopped (`UX-001`, `UX-006`, `T-181`).
    #:
    #: Emitted rather than polled because the gate is **queue-level**: there is no job whose
    #: `job_changed` would carry it. A control that read this on a timer would be inventing a
    #: signal this class is better placed to send.
    #:
    #: **Says `running`, not `paused`, and the inversion is the point** (`UX-006`). A queue that
    #: has never been started is not paused — nobody paused it — and a control wired to a signal
    #: named for the wrong state has to invert it somewhere, which is a place to get it backwards.
    queue_running = Signal(bool)

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
    #: rebuild from what is left.
    #:
    #: *(This said "**History is untouched**, so this announces a smaller queue and never a smaller
    #: record of what was obtained". There is no History and no record: `T-169` withdrew `REQ-020`,
    #: `T-170` removed the tab and the private ledger behind it, and migration `0009` removed the
    #: table from upgraded databases. **Clearing finished rows now removes the only trace they
    #: leave**, which is a stronger statement than the one it replaces and the reason `REQ-016`'s
    #: confirmation matters — `T-186`.)*
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
        # **Before any worker exists** (`T-258`). This is the outer half of containment: the
        # worker's own job is installed at the far end of its bootstrap, and a parent that dies
        # before then leaves a child with nothing of ours in it. Here rather than in the
        # application's entry point because *this* is the object that spawns, so a process that
        # creates workers is contained whether it is the GUI, a test driver or a script.
        # Idempotent, and a documented no-op on POSIX, where the bootstrap pipe already closes
        # that window — measured, see `process_tree.contain_this_application`.
        if not process_tree.contain_this_application():
            # Logged rather than raised, matching the worker's own containment failure: an
            # application that cannot make this guarantee still runs downloads, and the cost of
            # silence would be an orphan nobody could explain afterwards.
            logging.getLogger(f"{APP_SLUG}.manager").warning(
                "this application is not contained, so a worker killed before it is prepared "
                "could outlive it: %s",
                process_tree.application_containment_error,
            )
        self._repository = repository
        #: Jobs whose partial is to be thrown away once their process is gone, and the directory
        #: it lives in (`T113-R3`). **The directory is captured when the stop is asked for**, while
        #: the row certainly still exists — `remove()` deletes it, and reading it back afterwards
        #: is how a cleanup comes to have nothing to clean.
        #:
        #: **Acted on in `_release`, not here and not in the worker.** The worker cannot tell a
        #: user's Cancel from an orderly shutdown, and is not reached at all when the parent
        #: escalates to `terminate()`; and `remove()` deleting the directory before stopping the
        #: process let that process recreate it. After the tree is reaped is the only moment a
        #: cleanup cannot be undone by what it is cleaning up after.
        self._discard_partial_when_done: dict[str, Path] = {}
        #: Jobs being stopped by shutdown rather than by the user (`T113-R2`).
        #:
        #: **An interruption is not a cancellation**, and the difference is what `REQ-017` turns
        #: on. A cancelled job is terminal and its partial is unwanted; an interrupted one is work
        #: the user still wants, so its row is left in flight for `recover_interrupted()` to find
        #: at the next launch and its bytes are kept for the retry to continue from.
        self._interrupting: set[str] = set()
        self._entry_point = entry_point
        self._cooperative_seconds = cooperative_seconds
        self._terminate_seconds = terminate_seconds
        self._reap_seconds = reap_seconds
        self._user_ytdlp_directory = user_ytdlp_directory
        self._ffmpeg_override = ffmpeg_override
        #: The cookies file handed to every child (`REQ-026`, `T-197`). Held here rather than on a
        #: job for `DAT-003`'s reason: a cookie path this application supplies must not reach the
        #: model, and therefore cannot reach the database.
        self._cookie_file: Path | None = None
        #: Jobs that exist only in memory, for the add dialog's staging probes (`T118-R1`).
        #:
        #: **`UX-003` says nothing is persisted until Add**, and `T118-R1` is what happens when it
        #: is anyway: `compose()` admits every durable `QUEUED` or `READY` row at startup, so a
        #: crash after a probe succeeded left a row the next launch downloaded although the user
        #: never pressed Add. A staged job is never written, never recovered, and cannot be
        #: admitted for download — it exists so the session machinery has an id to work in, and
        #: it is dropped when the dialog is done with it.
        self._staged: dict[str, Job] = {}
        #: Staged ids asked to go whose session has not ended yet (`T118-R1`).
        #:
        #: The record cannot be dropped when `unstage` is called: cancelling runs a chain of steps
        #: that each ask `_require` for the job, and a staged job removed early is in neither the
        #: staging table nor the store — so the chain raises `KeyError` out of a Qt slot. It is
        #: dropped when the session is released, which is the same rule the durable path uses for
        #: deleting a removed row.
        self._unstaging: set[str] = set()
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
        #: What to restart, for a job whose start is deferred — parked behind the gate, a slot,
        #: a reorder barrier, or a retry's backoff (`T083-R1`). Absent means `DOWNLOAD`, which
        #: is what every deferred start was silently assumed to be until a retried **probe**
        #: came back as a download and began writing media nobody had confirmed.
        self._intended_kind: dict[str, SessionKind] = {}
        #: What a previous run left queued, waiting for the user to start the queue before it is
        #: admitted at all (`T-215`). **Not `_waiting`**, and the difference is the point: a job
        #: in `_waiting` has been admitted and runs the moment its lane allows, which for a probe
        #: is immediately — the stopped-queue gate exempts probes so the add dialog can read what
        #: the user pastes. These have not been admitted, so nothing reads them until Start.
        self._held_for_start: list[tuple[str, SessionKind]] = []
        #: Whether the queue is running (`UX-001`, `UX-006`, `T-181`). **Not a job status** — that
        #: is the whole decision. The gate governs what this manager *starts*; it never changes a
        #: job, which is why `T-080` could delete `JobStatus.PAUSED` outright.
        #:
        #: **`False` at construction, and that is `UX-006`.** A queue does not run until the user
        #: starts it, so restoring a queue at launch starts nothing — the behaviour change with the
        #: widest reach and the least visible symptom, which is why `T-181` asserts it on the pool
        #: rather than on a window. It was `_paused = False` until 2026-08-07, i.e. running.
        self._running = False
        #: Jobs asked to be removed whose session has not ended yet (`T-080`). Removal of a running
        #: job is a cancel followed by a delete, and the delete cannot happen until the process is
        #: gone — a row deleted out from under a live session leaves `_require` raising on the next
        #: message it sends.
        self._remove_when_done: set[str] = set()
        #: Reorders queued and not yet settled (`T081-R1`). **A count, not a flag** — two can be in
        #: flight, and a boolean cleared by the first callback reopens the admission window while
        #: the second is still running.
        self._reorders_in_flight = 0
        #: Why no worker may start, while something is changing the tree they import from
        #: (`T198-R3`). `None` means nothing is held.
        #:
        #: **A hold, not a check.** The first correction asked the manager a question at the moment
        #: the button was pressed and then let an install run for seconds against a live queue, so
        #: a Start, an admission, a tick or an **automatic retry** could spawn a worker inside the
        #: window. Held state is the only shape that covers an interval rather than an instant.
        #:
        #: A string rather than a flag because a refusal is a sentence somebody reads, and because
        #: a holder that cannot say who it is cannot be diagnosed from a log.
        self._starts_held_for: str | None = None
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

    # --- the queue-level run gate (`UX-001`, `UX-006`) -----------------------------------

    @property
    def is_running(self) -> bool:
        """Whether the queue is running. **A property of the queue, never of a job** (`UX-001`).

        `False` until somebody calls `start_queue()`, including at launch (`UX-006`).
        """
        return self._running

    def stop_queue(self) -> None:
        """Stop starting work. **In-flight sessions finish; nothing new begins** (`UX-001`).

        This is `set_concurrency(0)` in spirit and deliberately not in fact: the limit stays what
        the user chose, so starting again restores it without having to remember it. What this
        changes is whether `_fill_free_slots` is willing to spend a slot at all.

        **Nothing is asked to stop, and no job's status changes.** `UX-001` chose draining because
        every alternative buys a half-written file plus a rule about its lifetime, in a phase where
        `REQ-017`'s resume does not exist — so there is no partial file to have a rule about. That
        is also why `T-080` removed `JobStatus.PAUSED`: a stopped queue has running jobs and
        waiting jobs, and no job in a stopped state.

        A direct `start()` — the add-URL dialog's probe — is **not** governed by this. The gate is
        about the queue draining, and a probe the user just asked for by typing a URL is not queue
        work waiting for a slot. Silently refusing it would make the dialog hang on "Probing …"
        with nothing to say why — and under `UX-006` it would hang that way on a *fresh launch*,
        which is now the ordinary case rather than an unusual one.

        Idempotent, and refused during shutdown: a queue that is already ending is not a queue to
        stop, and stopping it would be a second reason nothing starts, with only one of them ever
        cleared.

        *(Was `pause()`. `T-181` renamed the pair when `UX-006` made stopped the state a window
        opens in: a queue nobody has started has not been paused by anyone.)*
        """
        if not self._running or self._shutting_down:
            return
        self._running = False
        self.queue_running.emit(False)

    def start_queue(self) -> None:
        """Start taking work, filling every free slot **now** (`UX-001`, `UX-006`).

        Immediately rather than on the next tick, for `set_concurrency`'s reason: a tick is up to
        `poll_interval_ms` away, which is invisible to a test that spins the event loop and
        perfectly visible to somebody who just pressed Start.

        **Named `start_queue` rather than `start`** because `start(job_id)` is this class's
        per-job entry point and has been since Phase 1. Two methods called `start` differing by
        arity is how a queue-level verb gets called on a job by mistake.
        """
        if self._running or self._shutting_down:
            return
        self._running = True
        self.queue_running.emit(True)
        # **What the last run left is admitted here, and nowhere earlier** (`T-215`). Between
        # setting the gate open and filling slots, so these rows take their turn in the same fill
        # as everything else rather than waiting for a tick. Emptied by `_admit_held_for_start`,
        # so a stop/start cycle does not re-admit what is already running.
        self._admit_held_for_start()
        self._fill_free_slots()

    # --- the exclusion held while yt-dlp's tree changes (`T198-R3`) ----------------------

    @property
    def starts_are_held(self) -> bool:
        """Whether a tree-changing operation currently forbids every worker start."""
        return self._starts_held_for is not None

    def hold_worker_starts(self, reason: str) -> bool:
        """Take the tree quiet, and keep it quiet until `release_worker_starts()` (`T198-R3`).

        **The caller of this is whatever is about to replace or delete the yt-dlp package tree a
        worker imports from.** On POSIX that replacement succeeds by design, so a worker that has
        already imported `yt_dlp` resolves its *later* lazy imports — yt-dlp loads extractors on
        demand — from whatever now sits at that path. That is a mixed-version import, and a revert
        makes it a missing one. Platform rename behaviour is not a gate; this is.

        `True` means two things, and both of them are required for the operation to be safe:

        1. **Nothing is active now.** `active_job_ids()` is empty — no session, no reservation, no
           job waiting for a slot, and no automatic retry counting down.
        2. **Nothing will become active** until the hold is released. Every path that spawns a
           worker parks instead: `start()`, `admit()`, `_start_when_free`, the tick's fill, and a
           retry whose backoff expires mid-operation.

        `False` means the caller must not touch the tree. **It is a refusal, not a wait**: the
        operation belongs to a button somebody pressed, and blocking the GUI thread until a queue
        drains is the freeze `NFR-001` forbids.

        **Not re-entrant.** A second holder would release the first one's exclusion when it
        finished, which is exactly the interval this exists to protect.

        Read every time rather than answered from a cached predicate: a queue that was idle when
        the settings screen opened is not a queue that is idle when the button is pressed.
        """
        if self._starts_held_for is not None or self.active_job_ids():
            return False
        self._starts_held_for = reason
        return True

    def release_worker_starts(self) -> None:
        """Let workers start again, and start whatever the hold parked (`T198-R3`).

        **Called on success *and* on failure**, which is why the service that takes the hold
        releases it from the one place both outcomes reach. An install that raises and leaves the
        queue permanently unable to start is a worse defect than the one the hold prevents.

        Filling here rather than waiting for a tick, for `start_queue`'s reason: a tick is up to
        `poll_interval_ms` away, and a user who pressed Start during an update should not watch
        their queue sit still afterwards. `_fill_free_slots` re-applies the stopped-queue gate and
        the reorder barrier, so releasing this hold releases *only* this hold.

        Idempotent: releasing a hold nobody took is not an error, and a caller that has already
        been told its operation failed should not have to remember whether it got as far as
        holding.
        """
        if self._starts_held_for is None:
            return
        self._starts_held_for = None
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

        **What survives is the file, and only the file** (`T-186`). `UX-001`: remove takes the job
        out of the queue, and nothing this application deletes from disk goes by this route.

        *(This ended "`T-085`'s history keeps a completed job's record even after its queue row is
        gone". It does not — `T-169` withdrew `REQ-020`, `T-170` removed the ledger and migration
        `0009` removed the table. Removing a job now leaves the downloaded file and nothing else,
        which is the same promise made without the second half.)*

        **The one thing it does delete is this job's own partial** (`T-113`, `REQ-017`). Since
        resume landed, a failed or killed attempt deliberately *keeps* its `.part` file so the next
        attempt can continue from it — and removing the job is the user saying there will be no
        next attempt. Nothing of theirs is in that directory: it was created by this job, for this
        job, and holds only bytes this job downloaded. Leaving it would put an invisible partial in
        their download folder with no row left to explain it.

        **Discarded once the process is gone, never before it** (`T113-R3`). This used to delete
        the directory as the removal was *asked for*, with the worker still running — and a worker
        that had not noticed the cancel yet simply recreated it, leaving an invisible partial and
        no row to explain it. The intent is recorded now and acted on in `_release`, which is the
        same reason the row itself is deleted there.

        *(This said "a partially written file from a cancelled download is the user's to delete",
        then said the opposite when `T046-R1` made every session discard its staging directory. It
        is now the sentence above: kept on failure and on an orderly shutdown, discarded on cancel
        and on remove.)*
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
        # **No session, so nothing can recreate it** — the deferral `_release` exists for does not
        # apply, and a job removed before it ever ran still has a directory if an earlier attempt
        # failed and kept one.
        self._discard_partial(job_id)
        self._discard_partial_when_done.pop(job_id, None)
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

    def _output_directory_of(self, job_id: str) -> Path | None:
        """Where this job writes, or `None` for an id this manager cannot answer for.

        Staged first: a staging probe lives in memory and never reaches the repository
        (`T118-R1`), and `cancel` is called for those too. `None` is ordinary — `cancel` and
        `remove` are reached from routes that cannot know whether the id is still known.
        """
        staged = self._staged.get(job_id)
        job = staged if staged is not None else self._repository.get(job_id)
        return None if job is None else Path(job.request.output_directory)

    def _discard_partial(self, job_id: str) -> None:
        """Throw away the staging directory a job's interrupted attempts left (`T-113`).

        **Read before the row goes**, because the output directory lives on the request and the
        request lives on the row. Unknown ids and jobs that never ran are ordinary: `remove` is
        called from routes that cannot know which, and a staging directory that was never created
        is nothing to delete.

        **Synchronous, and small enough to be.** `ARC-005` puts durable *queue* writes on their own
        thread because a contended SQLite commit measured seconds (`T016-R3`). This is an `rmtree`
        of one directory holding at most a handful of this job's own files, with no lock and no
        fsync; putting it behind the writer would mean inventing a second kind of work for a thread
        whose whole contract is the queue.
        """
        directory = self._output_directory_of(job_id)
        if directory is None:
            return
        worker.discard_staging_for(directory, job_id)

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
        """Every job this manager is holding: running, reserved, waiting, **or retrying**.

        Sorted so the answer does not depend on which of the collections an id happens to be in — a
        caller that saw a job appear, vanish, and reappear as its start became a session would be
        watching bookkeeping rather than the job (`T016-R3`). A set first, so an id that is briefly
        in two collections is reported once.

        Waiting jobs count because this manager has **accepted** them (`T078-R1`). They are the
        same commitment a reservation is, one step earlier: nobody else will start them, they are
        why `is_idle` is false, and a caller asking what this manager is holding is asking a
        question the waiting list is part of the answer to. Leaving them out made the method
        contradict its own first sentence.

        **A job counting down to an automatic retry counts for the same reason** (`T198-R3`).
        `is_idle` has always included `_retry_at` — it is work this manager will begin, on a
        deadline it set itself — and this method did not, so the two disagreed about the same
        state. That disagreement was load-bearing rather than untidy: the caller that asks "is
        anything going to start a child" is the one about to replace the package tree those
        children import from, and a queue whose only remaining work was a backoff answered "no".

        **This is not the occupancy count.** A waiting or retrying job holds no slot, so capacity
        and the diagnostics about capacity use `_occupant_ids()` instead.
        """
        return tuple(
            sorted(
                set(self._sessions) | set(self._reserved) | set(self._waiting) | set(self._retry_at)
            )
        )

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

        **A stopped queue admits and starts nothing** (`UX-001`, `UX-006`): `_start_when_free`
        parks it, and `start_queue()` drains. Admission is not a start; it is a claim on the next
        free slot.

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

    def set_cookie_file(self, path: Path | None) -> None:
        """Point later worker sessions at a cookies file, or at none (`REQ-026`, `T-197`).

        `set_ffmpeg_override`'s shape, and for the same reason: composition owns the setting, this
        owns what runs. **The value children receive**, so a change reaches the next session rather
        than the next launch.

        **This is why the cookie path is late-bound**, which `DAT-003`'s 2026-08-10 amendment rules
        deliberate: the path may not live on `DownloadRequest`, so a queued job cannot carry it and
        authenticates with whatever is set when its worker starts.
        """
        self._cookie_file = path

    def set_ffmpeg_override(self, path: Path | None) -> None:
        """Point later worker sessions at a different ffmpeg (`REQ-024`, `T199-R2`).

        **The value children receive, not a copy of it.** `_ffmpeg_override` is captured at
        construction and passed to every child from `_begin_reserved`; nothing could change it, so
        a user who set an ffmpeg location mid-session got a UI that followed the new answer while
        every worker still received the old one — the dialog offering exactly what the worker would
        then refuse. `set_concurrency`'s shape: composition owns the setting, this owns what runs.

        **Sessions already started keep the value they were given.** A running child has its own
        process and its own arguments, and reaching into one would be a different and much larger
        promise; the next session is the first that can honour the change.
        """
        self._ffmpeg_override = path

    def admit_when_started(self, job_id: str, kind: SessionKind = SessionKind.DOWNLOAD) -> None:
        """Admit `job_id` **the first time the queue is started**, and not before (`T-215`).

        For work this manager inherited rather than work someone asked for: the rows a previous
        run left queued, which composition hands over at launch (`T-115`). `admit()` is wrong for
        them, and the difference is not the gate — it is that a `QUEUED` row is admitted as a
        *probe*, and the gate exempts probes so the add dialog can read what the user pastes
        while the queue sits stopped, which `UX-006` says it does at every launch.

        **So an inherited row was read the instant the window opened**, with nobody watching, and
        a launch with no usable network failed every one of them — `REQ-018` then retried the
        network error and failed them again, turning a queue the user had committed into a wall
        of `Failed` rows to retry by hand. Observed live, offscreen, in under a second.

        **Deferred here rather than by widening the gate**, which was tried first and is wrong:
        the gate cannot tell an inherited probe from the one the add dialog runs when the user
        adds a playlist, and holding *those* leaves freshly queued entries bare until Start —
        the report `T-143` exists to have fixed. Startup is the only moment at which nobody has
        asked for anything, so a caller who knows it is startup is the one that can say so.

        Held rather than admitted means the manager reports nothing for these rows — they are not
        `active_job_ids()`, not `_waiting`, and `is_idle` stays true. That is the honest answer:
        an inherited row is not work in flight until the user asks for it.
        """
        self._held_for_start.append((job_id, kind))

    def _admit_held_for_start(self) -> None:
        """Hand every held row to `admit`, once. Called from `start_queue` alone."""
        held, self._held_for_start = self._held_for_start, []
        for job_id, kind in held:
            self.admit(job_id, kind)

    def stage(self, request: DownloadRequest) -> str:
        """Read `request.url` **without creating a queue job** (`T118-R1`, `UX-003`).

        Returns the id the result will arrive under. `media_probed` and `job_failed` report it
        exactly as they do for a queued job, so a caller listens to one pair of signals whether
        the job is staged or durable.

        **Nothing here reaches the store.** `UX-003`'s rule is that a job enters the queue only
        once it has been read, and the first implementation of this dialog persisted a `QUEUED`
        row in order to *do* the reading — which `compose()` then admitted on the next launch, so
        a crash mid-paste downloaded a URL nobody had committed to. A staged job is an id and a
        request, held here, and `unstage` is the whole of its cleanup.

        Admitted rather than started, so a paste of twenty queues behind the probe lane instead of
        being refused (`T-116`).
        """
        staged = Job(
            id=str(uuid4()),
            url=request.url,
            request=request,
            status=JobStatus.QUEUED,
            created_at=_now(),
        )
        self._staged[staged.id] = staged
        self.admit(staged.id, SessionKind.PROBE)
        return staged.id

    def unstage(self, job_id: str) -> None:
        """Forget a staged job, stopping its session if one is running (`T118-R1`).

        **Idempotent, and safe for an id that was never staged**, because the dialog calls this
        from close, from edit and from remove and none of them can know which. A durable job is
        left strictly alone: it belongs to the queue, and `cancel`/`remove` are its verbs.

        No `CANCELLED` row is written and no row is deleted — there is nothing to write or delete,
        which is the point of the ruling. What the queue never held, it never has to be told about.
        """
        if job_id not in self._staged:
            return
        self._discard_waiting(job_id)
        self._retry_at.pop(job_id, None)
        if job_id in self._sessions or job_id in self._reserved:
            # **The record outlives the cancel.** Cooperative first, escalating on the manager's
            # own timer; the staged job stays readable until its session is released, because the
            # steps that cancel it each ask `_require` for it on the way past.
            self._unstaging.add(job_id)
            self.cancel(job_id)
            return
        self._staged.pop(job_id, None)

    def is_staged(self, job_id: str) -> bool:
        """Whether `job_id` is a staging probe rather than a queue job."""
        return job_id in self._staged

    def preview_output_path(self, request: DownloadRequest, media: MediaInfo) -> OutputPreview:
        """Where `request` would write `media`, for `REQ-011`'s live preview (`T-112`).

        **Here because `ARC-002` puts every yt-dlp access behind this class**, and rendering an
        output template is one: `ui/` may not reach `ytdlp_adapter` and must not learn yt-dlp's
        template syntax. The dialog asks the manager, which is the same route a probe takes.

        **Synchronous, and it is the one yt-dlp call that may be** (`NFR-001`, `ARC-005`). Every
        other one is a network extraction of unbounded length and goes to a worker process. This is
        a string substitution against a projection already in memory — measured at 0.07 ms once the
        renderer exists — so a process boundary would cost four orders of magnitude more than the
        work, and a preview that arrived a second after the keystroke would not be a live one.

        Three answers, and the caller has to distinguish them (`REQ-011` as amended):

        - **refused** — the template is unusable and no path is shown, because showing the last
          good one beside an error is how a user comes to believe a broken template works;
        - **provisional** — the path is right and the extension is yt-dlp's to choose later;
        - **exact** — the request itself decides the container.

        Never raises. A preview that threw would take the dialog down over a half-typed template,
        which is the ordinary state of a field somebody is typing into.
        """
        from tracks_and_trails.downloader import ytdlp_adapter as adapter

        template = request.output_template
        if not template.strip():
            return OutputPreview(refusal=output_template.EMPTY_REFUSAL)
        syntax = adapter.template_syntax_error(template)
        refusal = (
            output_template.syntax_refusal(syntax)
            if syntax is not None
            else output_template.unsupported_refusal(template)
        )
        if refusal is not None:
            return OutputPreview(refusal=refusal)

        # **`T-046`'s own two functions do the rest**, rather than a second answer to *"which
        # container will this land in"* written here. `postprocessed_name` reads yt-dlp's `ACODECS`
        # table and `preview_is_provisional` classifies the request; restating either would get
        # `aac` and `alac` both landing in `m4a` wrong, which is `T046-R4` exactly. So `%(ext)s`
        # renders as a placeholder and is replaced wherever the request decides the container —
        # and where it does not, the answer is labelled rather than guessed.
        try:
            rendered = adapter.render_output_template(
                template,
                output_template.template_values(media, output_template.UNDECIDED_EXTENSION),
            )
            target = contained_output_path(Path(request.output_directory), rendered)
            path = worker.previewed_path(target, request)
        except UnsafePathError as unsafe:
            return OutputPreview(refusal=str(unsafe))
        except (ValueError, TypeError, KeyError, OSError) as failure:
            # yt-dlp raises whatever its conversion syntax raises, and this runs on a string the
            # user is in the middle of typing. Reported in the editor rather than escaping into
            # the event loop — the whole point of `P-23` is that the refusal lands beside the field.
            return OutputPreview(refusal=f"This template could not be rendered: {failure}")
        provisional = (
            output_template.PROVISIONAL_NOTE if worker.preview_is_provisional(request) else None
        )
        return OutputPreview(path=str(path), provisional=provisional)

    def requires_ffmpeg(self, preset: Preset) -> bool:
        """Whether `preset`'s post-processing needs ffmpeg (`REQ-024`, `T-111`).

        **Here for `preview_output_path`'s reason**: `ARC-002` puts every yt-dlp access behind this
        class, and the preset manager has to say `REQ-024`'s fact while a preset is being written —
        which is the only moment the user can do anything about it. `ui/` may not ask yt-dlp
        itself, so the question travels through here.

        **One answer, not a second one.** `adapter.requires_ffmpeg` derives it from yt-dlp's class
        hierarchy — every ffmpeg-backed processor subclasses `FFmpegPostProcessor` — precisely so it
        cannot drift as processors are added upstream. A predicate reading the preset's own fields
        would be the hardcoded list that docstring records as having already missed processors once,
        and it would pass every test written today.

        **The URL and directory are placeholders, and the answer does not depend on either.** A
        preset carries neither, and `DownloadRequest` refuses both empty; `build_postprocessors`
        reads only
        the post-processing fields, so any valid pair yields the same answer — asserted by
        `test_the_answer_does_not_depend_on_the_placeholder`. `.invalid` is reserved by RFC 2606 for
        exactly this and is the stand-in `_freeze_probe` already uses. No request is built to be
        downloaded and nothing here touches the network.

        Synchronous, and one of the two yt-dlp calls that may be (`NFR-001`, `ARC-005`): it inspects
        a postprocessor list already in memory rather than extracting anything.
        """
        from tracks_and_trails.core import presets as preset_registry
        from tracks_and_trails.downloader import ytdlp_adapter as adapter

        request = preset_registry.to_request(
            preset, url="https://example.invalid/preset", output_directory="."
        )
        return adapter.requires_ffmpeg(request)

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
        if kind is SessionKind.DOWNLOAD and job_id in self._staged:
            # **A staged job is not queue work** (`T118-R1`, `UX-003`). It has no row, no
            # `queue_position` and no recovery, so downloading it would produce a file for
            # something the user never added. Persisting it is Add's job, and Add creates a
            # different, durable id.
            raise ValueError(
                f"{job_id!r} is a staging probe and cannot be downloaded; persist it first"
            )
        if self._holds(job_id):
            # **One session per job, whichever lane it is in** (`T116-R1`). Raised rather than
            # queued because `start()`'s caller asked for a session *now* on a specific job, and a
            # job that already has one means their model of it is wrong. `admit()` parks instead.
            held = self._kind_of(job_id)
            raise RuntimeError(
                f"{job_id!r} already has a {held.value if held else 'pending'} session; "
                "one job holds one session at a time, whichever lane it is in"
            )
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

        # **A stopped queue admits a probe and parks a download** (`T080-R1`, `UX-001`, `UX-006`).
        #
        # **This guard and `_start_when_free`'s are belt and braces, and `T-181` measured that.**
        # Removing either one alone changes no observable behaviour: a retry released by
        # `_start_when_free` still meets this one through `_start_or_report`, and a parked start
        # here would meet that one on the tick. Only removing both lets a stopped queue run. That
        # is worth knowing before anyone "simplifies" one of them away on the grounds that a test
        # still passes without it.
        #
        # The gate guards used to sit only on `_fill_free_slots` and `_start_when_free`, so this
        # public entry point walked straight past them. That is not a hypothetical hole: the
        # add-URL dialog calls `start(job_id)` after a probe resolves, and its default `kind` is
        # `DOWNLOAD` — so pressing Add while the queue was paused started a download at once.
        # **The test that was supposed to cover this protected the defect**: it described a probe
        # and called `start("job-1")`, taking the same default, so it asserted that a paused queue
        # starts a *download* and called that the probe exemption.
        #
        # Parked rather than refused, because a refusal has nowhere to put the user's intent. The
        # job is already durably `QUEUED`; adding it to the waiting list means `start_queue()`
        # starts it, which is what somebody who queued work while stopped meant to happen.
        #
        # **Under `UX-006` this is the path, not the edge.** The queue is stopped until the user
        # presses Start, so every ordinary Add lands here and parks.
        # **Every DOWNLOAD admission goes through the same two rules** (`T080-R1`, `T081-R1`).
        #
        # The first correction put the pause guard here and the reorder barrier only on
        # `_fill_free_slots` and `_start_when_free` — so the public path honoured one and walked
        # past the other. The add-dialog seam uses exactly this entry point, so starting a job by
        # hand while a reorder was in flight admitted it against the positions the reorder was
        # replacing: both writes then succeeded and the durable order named a different job first.
        #
        # Parked rather than refused, for the gate's reason: the job is already durably `QUEUED`,
        # so the waiting list is where the intent belongs until the queue can honour it.
        # `start_queue()` and `_settle_reorder` both fill from durable positions afterwards.
        #
        # **The PROBE exemption is explicit and applies to both rules.** A metadata probe is not
        # queue work waiting for a slot — it neither depends on `queue_position` nor changes it —
        # and refusing it silently hangs the add dialog on "Probing ...".
        #
        # **The hold is the third rule, and it exempts nothing** (`T198-R3`). The stopped-queue
        # gate lets a probe through because reading a URL moves no bytes; the hold is not about
        # bytes. A probe session is a spawned child that imports `yt_dlp` from the very tree the
        # holder is replacing, so a probe started here is precisely the mixed-version import the
        # hold exists to prevent. Parked rather than refused, for the gate's reason: the intent is
        # good, only the moment is wrong, and `release_worker_starts()` fills from the same list.
        if self._starts_held_for is not None or (
            kind is SessionKind.DOWNLOAD and (not self._running or self._reorders_in_flight)
        ):
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
                    # `T-197`: a settings value, not a job field. It travels as a session
                    # argument exactly as the ffmpeg override does, which is the one route
                    # `DAT-003` authorises besides `settings.toml` itself.
                    "cookie_file": self._cookie_file,
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
        if job_id in self._unstaging and job_id not in self._sessions:
            # A withdrawn reservation never becomes a session, so nothing else will drop this.
            self._unstaging.discard(job_id)
            self._staged.pop(job_id, None)

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
        """The user asks `job_id` to stop, and it does (`REQ-015`).

        **A cancellation, which is terminal and discards the partial** (`UX-008`). Shutdown stops
        work too and means something different by it — see `_stop`.
        """
        self._stop(job_id, interrupting=False)

    def _stop(self, job_id: str, *, interrupting: bool) -> None:
        """Stop `job_id`, and record **why**, because the two answers differ (`T113-R2`).

        | Asked by | The row becomes | The partial |
        |---|---|---|
        | The user (`cancel`, `remove`) | `CANCELLED`, terminal | discarded once the process ends |
        | Shutdown | left in flight for `recover_interrupted()` | **kept**, for the resume |

        The mechanics of stopping are identical and are below; only the intent is recorded here.
        An orderly restart that discarded the partial and wrote a terminal `CANCELLED` left the
        user with neither bytes to continue from nor a row offering to try again — `REQ-017`
        promises resumption *across restarts*, and closing the window is how a restart usually
        begins.

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
        # **The user's intent outranks shutdown's, in both directions.** Cancelling a download and
        # then closing the window is an ordinary sequence, and shutdown cancels every occupant on
        # the way out — so without this the interruption would overwrite the cancellation the user
        # had already made, and a job they threw away would come back offering to resume. The
        # reverse cannot happen today (the window is gone by then) and is written the same way, so
        # the rule is *the user decides* rather than *whichever ran last*.
        if interrupting:
            if job_id not in self._discard_partial_when_done:
                self._interrupting.add(job_id)
        else:
            self._interrupting.discard(job_id)
            # Read now, while the row is certainly still there. `remove()` deletes it as soon as
            # the session ends, and a cleanup that looked the directory up afterwards would find
            # nothing and silently leave the bytes behind.
            directory = self._output_directory_of(job_id)
            if directory is not None:
                self._discard_partial_when_done[job_id] = directory

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
            if not self._known(job_id):
                # **An id this manager can no longer answer for is a no-op, not a crash**
                # (`T-118`). The comment above already names this hazard for `_waiting` and
                # `_discard_waiting` handles it there — but `shutdown()` cancels every *occupant*,
                # and a reservation or a released session can outlive its record by the same
                # routes: a staged job dropped as it is abandoned, a durable row deleted by
                # `T-081`'s clear-finished. `_require` answers such an id with `KeyError`, raised
                # out of a Qt slot from teardown.
                #
                # Observed twice on the self-hosted desktop runner, in teardown, where the test it
                # hung off still reported as passed. Cancelling what the queue has no record of
                # asks it to stop something it is not doing.
                #
                # **The reservation goes too, for `_discard_waiting`'s reason.** `is_idle` counts
                # reservations, and one that can never be answered for can never be spawned or
                # abandoned either — leaving it would hold the shutdown door open for a job that
                # does not exist. `_spawn` already treats a missing reservation as nothing to do.
                self._reserved.pop(job_id, None)
                return
            # Queued behind the starting transition when there is one, so `CANCELLED` is written
            # after the `PROBING` it supersedes rather than racing it (`_Chain`).
            self._persist(job_id, self._cancellation_of)
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

    def _holds(self, job_id: str) -> bool:
        """Whether this manager already owns a session or a reservation for `job_id` (`T116-R1`).

        **Identity, not capacity.** The two lanes `T-116` created are about how much work may run
        at once; this is about the same *job* being in both at the same time. `_spawn` assigns
        `self._sessions[job_id]` unconditionally, so a download admitted for a job whose probe
        process is still alive replaces the only object that owns and reaps that process — the
        manager loses the queue, the pump, the job log and the tree.

        The window is real and small: `media_probed` is emitted when the probe's *stream* ends,
        which is before `_release` has established that its process is gone. A dialog that admits
        the download from that signal — which is exactly what `UX-003`'s flow does — lands inside
        it. Hosted Windows saw three worker processes against a download limit of two.
        """
        return job_id in self._sessions or job_id in self._reserved

    def _gate_blocks(self, kind: SessionKind) -> bool:
        """Whether a stopped queue stops a session of `kind` from starting (`UX-001`, `T080-R1`).

        **The gate stops downloads, not reading.** `start()` has encoded that since `T080-R1` — "a
        paused queue admits a probe and parks a download" — and admission did not, which was
        invisible while probing was a button. `UX-003` made it visible immediately: the add dialog
        probes through `admit`, so a stopped queue left every pasted URL unread and the dialog with
        nothing it could ever offer to queue. Reading a URL moves no bytes and writes no file; it
        is not the work this gate exists to stop.

        **`UX-006` made that exemption load-bearing rather than considerate.** The queue is stopped
        at every launch, so a gate that blocked probes would leave a first-run window unable to
        read anything the user pasted — the failure would be the ordinary case, not the unusual
        one. It also exempts a retried *probe*, for the same reason and with the same consequence:
        `T-181`'s retry test starts from `READY` so the retry under test is a download.
        """
        return not self._running and kind is not SessionKind.PROBE

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

        Called from the tick, from `set_concurrency`, **and from `start_queue`** — which is what
        makes a raised limit, or a queue that has just been started, take effect at once rather
        than on whichever tick happens next. `T-078`'s criterion says "without waiting for a tick
        that happens to fire", and sharing this is how all three paths keep the same promise.

        **A stopped queue starts no download** (`UX-001`, `UX-006`). The guard is applied through
        `_gate_blocks` rather than as an early return, because the gate has never stopped a
        *probe* — `start()` has said so since `T080-R1` and this path did not, which `UX-003`
        turned from a latent inconsistency into a dialog that could read nothing while the queue
        was stopped. Keeping the rule in one predicate is what stops the tick, `set_concurrency`
        and `start_queue` being three chances to get it wrong.

        **A full download lane no longer stops a waiting probe** (`T-116`). The loop used to end
        at the first job it could not start, which was correct with one budget and starves the
        other lane with two: a probe sitting behind three running downloads would wait for a
        download to finish, which is the delay `UX-003` exists to remove. It now takes the next
        job *that can start*, and ends when no waiting job can.

        **Nothing is filled while a tree change holds the starts** (`T198-R3`). This is the path
        the tick, `set_concurrency` and `start_queue` share, so one guard here covers all three —
        and `release_worker_starts()` calls it, which is what makes the parked work run the moment
        the update ends rather than on whichever tick happens next.
        """
        if self._shutting_down or self._reorders_in_flight or self._starts_held_for is not None:
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

        def may_start(job_id: str) -> bool:
            kind = self._wants(job_id)
            if self._holds(job_id):
                # Its own earlier session has not been released yet (`T116-R1`). `_release` fills
                # again once it has, so this is a wait rather than a refusal.
                return False
            return self._has_capacity(kind) and not self._gate_blocks(kind)

        startable = [job_id for job_id in self._waiting if may_start(job_id)]
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

        **A stopped queue always parks it**, even with the pool empty (`UX-001`, `UX-006`). This
        is the path a retry takes — manual through `retry()`, automatic through
        `_perform_due_retries` — so a `NETWORK` failure does not restart itself while the user has
        the queue stopped, which is precisely the work the gate exists to stop.

        **`start()` carries the same guard, and both are needed to change behaviour.** `T-181`
        mutated each in turn and the suite stayed green either way; only removing both let a
        stopped queue run a retry. Neither is redundant — they cover different entry points — but
        neither is individually load-bearing, and a test cannot prove one of them alone.

        **A held tree parks it too, and here that covers the retry** (`T198-R3`). This is the path
        `_perform_due_retries` takes when a backoff expires, which is the one start an update
        cannot see coming: nobody pressed anything, and the deadline was set before the update
        began. Parking it keeps the job accepted — it is still in `active_job_ids()` — and
        `release_worker_starts()` runs it when the tree is stable again.

        **The hold's two guards behave exactly like the gate's, and that was measured rather than
        assumed.** Removing this one alone changes nothing observable: the start falls through to
        `_start_or_report`, meets `start()`'s hold guard, and is parked there instead. Removing
        `start()`'s alone is caught. **Only removing both lets a worker spawn into an update** —
        so this line is defence in depth at a second entry point, not the load-bearing one, and a
        test cannot prove it by itself. Said here because the same sentence about the gate above
        is what stopped somebody deleting *that* pair on the grounds that the suite stayed green.
        """
        if self._shutting_down:
            return
        if (
            self._starts_held_for is not None
            or self._gate_blocks(kind)
            or self._reorders_in_flight
            or self._holds(job_id)
            or not self._has_capacity(kind)
        ):
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
            # **Interrupted, not cancelled** (`T113-R2`). Closing the window is how a restart
            # usually begins, and `REQ-017` promises resumption across one — so the partial is
            # kept and the row is left for `recover_interrupted()` rather than being written
            # terminal here.
            self._stop(job_id, interrupting=True)
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
        if session.job_id in self._unstaging:
            # Its cancellation has run its course; the staging record can go (`T118-R1`).
            self._unstaging.discard(session.job_id)
            self._staged.pop(session.job_id, None)
        # **This job may have work parked behind its own session** (`T116-R1`). A download admitted
        # while its probe was still being released waits on `_waiting`; nothing else would start it
        # until the next tick, and a lane freed here should not cost a job 50 ms of nothing.
        self._fill_free_slots()
        # **After the tree is reaped, which is the whole of `T113-R3`** (`UX-008`). A user's Cancel
        # or Remove ends the partial's life; an orderly shutdown does not. Doing it here rather
        # than in the worker covers the escalated paths the worker never reaches — `terminate()`
        # and `kill()` run no handler — and doing it *before* `_delete_row` is what stops a removal
        # taking away the only row that explained the bytes it left.
        self._interrupting.discard(session.job_id)
        directory = self._discard_partial_when_done.pop(session.job_id, None)
        if directory is not None:
            worker.discard_staging_for(directory, session.job_id)
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

    def _probe_settled(self, job_id: str, media: object) -> None:
        """Announce a finished probe, and carry a **durable** job on into its download (`ARC-009`).

        `admit()` schedules one session; it has never chained. That was complete while the only
        probe in the system was a staging probe, whose whole point is to stop and wait for the
        user. `T-137` then created playlist entries as durable `QUEUED` rows — honestly, because a
        flat entry is named and not extracted — and admitted them straight to `DOWNLOAD`, so every
        entry of a playlist downloaded without ever being probed. `UX-003` says a queued job is a
        probed one, and `T137-R2` is that promise being broken for the majority of rows a real
        playlist produces.

        **Staged rows are excluded, and that is the whole discriminator.** A staging probe exists
        so the add dialog can show the user what they pasted *before* anything is committed;
        continuing it into a download would start the very thing the dialog is asking about.
        `is_staged()` already distinguishes them and is checked at claim time, before `_release`
        clears it.

        **The gate is honoured for free** (`T080-R1`, `UX-001`). The probe half runs while stopped
        because probes are exempt; this admission is an ordinary `DOWNLOAD`, so `_start_when_free`
        parks it and `start_queue()` drains it. A stopped queue therefore probes a playlist's
        entries and starts none of them, which is exactly what the gate is for.

        **A failed probe never reaches here.** `Failed` is a different outcome branch, so an entry
        whose extraction fails is reported per entry and is not carried into a download of
        something that could not be resolved.
        """
        self.media_probed.emit(job_id, media)
        if not self.is_staged(job_id):
            self.admit(job_id)

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
                #
                # **Except for a size this row does not have yet** (`T-118`). Persisting only on a
                # stage move was complete while every download began at `QUEUED` and was moved to
                # `RUNNING` by its first downloading message, which carried the total with it.
                # `UX-003` probes first, so a download starts from `READY` and `start()` has
                # already moved it — no message moves anything, and `bytes_total` stayed `NULL`
                # for the life of the job. The queue then showed an unknown size for every
                # download, and `T-014`'s stored total was a column nothing ever wrote.
                #
                # Bounded deliberately: this fires **once** per job, when a total first becomes
                # known. Writing on every progress message would put a row write behind every
                # frame of a progress bar.
                if current.bytes_total is None and message.total_bytes:
                    return replace(current, bytes_total=message.total_bytes)
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
            # **Unless nobody asked for it** (`T113-R2`). Shutdown stops every occupant through
            # this same path, and a worker that never reaches its cooperative handler — killed on
            # the escalation, which is the ordinary case for one stuck in a socket read — is
            # finalised *here* rather than by an outcome message. Writing `CANCELLED` for it threw
            # the job away on the user's behalf: a terminal row is not recovered at the next
            # launch, so an application closed mid-download reopened with nothing offering to
            # continue. Left in flight instead, which is exactly what a `SIGKILL` already leaves
            # and what `recover_interrupted()` reads.
            #
            # Routed through `_persist` returning `UNCHANGED` rather than simply returning: this
            # runs from the tick and the stream's end, not from inside a chain step, so releasing
            # the chain by hand would mark somebody else's running step as finished.
            if job_id in self._interrupting:
                self._persist(job_id, lambda _current: UNCHANGED)
                return
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
                # **The announcement stays in `then`**, so it fires only after the write commits:
                # there is no instant where the user is told it succeeded and the queue disagrees
                # (`T050-R2`, asserted by
                # `test_a_success_is_announced_only_after_the_row_says_completed`).
                #
                # *(This passed `write=self._repository.complete`, a separate path that existed to
                # put the job row and its history row in one transaction (`T050-R1`). With the
                # record withdrawn it wrote the same single row as `update` through three
                # duplicated layers, so `T-175` collapsed it and this uses the default.)*
                then=lambda: self.job_succeeded.emit(job_id, outcome.output_path),
            )
        elif isinstance(outcome, Probed):
            self._persist(
                job_id,
                lambda current: self._settled(
                    current,
                    # **One write carries every field the probe resolved** (`T-117`). The title and
                    # the thumbnail URL arrive in the same `Probed` message and land in the same
                    # revision, so there is no instant where a row has been told what it is called
                    # but not what it looks like — and no second write that could fail on its own.
                    #
                    # **`uploader` and `duration_seconds` are here because this is the *other* place
                    # a probe result lands** (`T-143`, `T124-R4`, `UX-005` §3). `add_dialog`'s
                    # `_durable_job` carries the whole set across for a pasted URL and says in as
                    # many words that *"adding the next one is a schema change and not a second
                    # omission"* — and this path, which is the one every **playlist entry** takes,
                    # was the second omission. The observable cost was the maintainer's report that
                    # a playlist's rows stay bare: an entry probed, acquired a title and a picture,
                    # and still showed no uploader and no duration, while a pasted URL beside it
                    # showed both. A row's anatomy must not depend on how it got into the queue.
                    lambda job: replace(
                        self._advance(job, JobStatus.READY),
                        title=outcome.media.title,
                        thumbnail_url=outcome.media.thumbnail_url,
                        uploader=outcome.media.uploader,
                        duration_seconds=outcome.media.duration_seconds,
                        # **`T-113`.** A job admitted as a probe — a playlist entry, or a row
                        # recovered from a previous run — learns here whether it is live, which is
                        # the one thing `REQ-017` lets a row say about resumability in advance.
                        is_live=outcome.media.is_live,
                    ),
                ),
                then=lambda: self._probe_settled(job_id, outcome.media),
            )
        elif outcome.kind is ErrorKind.CANCELLED:
            # Not a failure: the user asked for it, and `CANCELLED` is terminal, so presenting
            # it as `FAILED` would offer a retry for something nobody wants retried.
            #
            # **Unless nobody asked for it** (`T113-R2`). Shutdown stops the same sessions through
            # the same worker path, and writing `CANCELLED` for one of those threw the job away on
            # the user's behalf: a terminal row is not recovered at the next launch, so an
            # application closed mid-download reopened with no partial and nothing offering to
            # continue. Left in flight instead, which is what `recover_interrupted()` reads —
            # the same route a `SIGKILL` already takes, and honest, because the download *was*
            # interrupted.
            interrupted = job_id in self._interrupting
            self._persist(
                job_id,
                lambda current: (
                    UNCHANGED
                    if interrupted
                    else self._settled(current, self._cancelled, outcome.message)
                ),
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

    def _cancellation_of(self, job: Job) -> Job | None:
        """`job` cancelled, or `None` if this queue cannot legally cancel it (`T-118`).

        **The guard asks the state machine rather than asking whether the job is terminal.** Those
        are different questions and the difference is a crash: `FAILED` is *not* terminal here —
        retry exists — so `is_terminal` said no, the cancellation was computed, and
        `Job.with_status` refused `FAILED -> CANCELLED` with `IllegalTransitionError` raised out
        of a Qt slot.

        `cancel()`'s own comment has recorded that hazard since `T010-R3` and reasoned nothing
        could reach it, because cancelling is for in-flight work and a failed job has none. That
        held until `unstage()` existed: a staging probe that *fails* still owns its session until
        the process is reaped, so abandoning it in that window cancels a `FAILED` job.

        Declining is the whole fix, and it is the same answer the terminal check already gave for
        the cases it did cover: there is nothing to stop, so there is nothing to write.
        """
        if not can_transition(job.status, JobStatus.CANCELLED):
            return None
        return self._cancelled(job)

    def _cancelled(self, job: Job, message: str | None = None) -> Job:
        """`CANCELLED`, with the reason recorded but not classified as a failure."""
        return replace(
            job.with_status(JobStatus.CANCELLED),
            error_kind=ErrorKind.CANCELLED,
            error_message=message or "Cancelled at your request.",
            finished_at=_now(),
        )

    def _known(self, job_id: str) -> bool:
        """Whether this manager can still answer for `job_id` at all, staged or durable.

        `_require`'s question without its exception, for the one caller that has to ask rather than
        assume. Deliberately not a `try/except KeyError` around `_require`: that exception is the
        contract for a lookup that *should* succeed, and swallowing it at a call site would hide
        the next real instance.
        """
        return job_id in self._staged or self._repository.get(job_id) is not None

    def _require(self, job_id: str) -> Job:
        """The job `job_id` names, staged or durable. Staged first — it is never in the store."""
        staged = self._staged.get(job_id)
        if staged is not None:
            return staged
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

        **`write` overrides which persistence operation is used.** It defaults to
        `JobStore.update`; `requeue_at_end` is the one caller that needs something else, because
        it allocates a tail position inside its own transaction (`T-080`). It is a parameter
        rather than a second method because everything else about the step — computing the
        revision when its turn comes, settling, chain release, failure handling — is identical,
        and duplicating that is how two writes once drifted into two transactions.

        *(The completion branch also passed one, `JobStore.complete`, which wrote a job row and a
        history row together (`T050-R1`). `REQ-020` was withdrawn and it became the same single
        write as the default, so `T-175` removed it. The ordering rule it is often confused with
        — announce only after the write settles — lives in `then`, not in `write`, and is
        unaffected.)*

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
            if revised.id in self._staged:
                # **A staged job has nowhere to be written** (`T118-R1`). Its transitions are real
                # — a probe still moves `QUEUED → PROBING → READY` and the session machinery reads
                # that — but they live in memory and die with the dialog. Routed through the same
                # `_settle` so ordering, signals and chain release are identical; what differs is
                # only that the store is not asked.
                self._staged[revised.id] = revised
                self._settle(revised, None, then, otherwise)
                return
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
        if job.id in self._staged:
            self.staged_changed.emit(job.id, job.status.value)
        else:
            self.job_changed.emit(job.id, job.status.value)
        if then is not None:
            then()
        self._step_finished(job.id)


def _now() -> datetime:
    """Timezone-aware local time, matching what `persistence` stores (`T-014`)."""
    return datetime.now().astimezone()
