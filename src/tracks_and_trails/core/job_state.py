"""Job status enum and the state machine.

Illegal transitions raise rather than silently corrupting state: a persisted queue
that lies about its state is worse than a crash (`ARCHITECTURE.md` §5).

The legal table lives here and nowhere else. Every component that changes a job's status —
the download manager, the persistence layer, the UI — goes through `apply()`, so there is one
place to read to know what can happen, and one place a mistake can be made.

`ai/TESTING.md` §7 lists the state machine as mandatory coverage: *every* illegal transition
must raise. The tests assert that over every ordered pair of statuses rather than a sampled
list, so adding a status without adding its transitions fails the suite instead of quietly
acquiring permissive behavior.
"""

from enum import StrEnum
from typing import Final


class JobStatus(StrEnum):
    """Where a job is in its lifecycle (`ARCHITECTURE.md` §5).

    `StrEnum` for the same reason as `ErrorKind`: these are persisted (`T-014`) and cross a
    process boundary (`ARC-002`), where a stable string beats a shifting ordinal.
    """

    QUEUED = "queued"
    PROBING = "probing"
    READY = "ready"
    RUNNING = "running"
    POST_PROCESSING = "post_processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    # `PAUSED` was here until `T-080` (2026-07-31, maintainer decision). It was never reachable:
    # `UX-001` makes pause a queue-level drain, so a paused *queue* has running jobs that finish
    # and waiting jobs that do not start, and no job's own status ever changes. Keeping a status
    # nothing can enter reads as capability without being it. `REQ-017`'s partial-download resume
    # in Phase 3 is the reopening condition, and it can add the status its own semantics need
    # rather than inheriting this one, which was a guess nothing ever exercised.


#: States from which nothing further happens.
#:
#: `FAILED` is deliberately **not** here: `ARCHITECTURE.md` §5 has `FAILED ──retry──▶ QUEUED`,
#: and `REQ-018` requires a failed job to stay in the queue and offer retry. A job that failed
#: is finished with *this attempt*, not with its life.
TERMINAL: Final = frozenset({JobStatus.COMPLETED, JobStatus.CANCELLED})

#: Statuses whose queue position the user may rearrange (`REQ-016`, `T-081`).
#:
#: **The complement of "in flight or finished", written out rather than derived.** Deriving it as
#: `set(JobStatus) - INTERRUPTED_ON_STARTUP - TERMINAL` would make the three agree
#: unconditionally, which `ai/TESTING.md` §13 is about: a new status would silently become
#: reorderable and no test could tell. `test_the_reorderable_statuses_partition_the_enum` asserts
#: the partition instead, so adding a status fails the suite until somebody decides its side.
#:
#: `FAILED` is here because a failed job is still in the queue offering a retry (`TERMINAL`'s own
#: note), and where it sits decides when that retry runs.
REORDERABLE: Final = frozenset({JobStatus.QUEUED, JobStatus.READY, JobStatus.FAILED})

#: Lives here rather than in `persistence/` because it is a fact about a *status*, like `TERMINAL`
#: and `CANCELLABLE` above — and because `ui/` needs it to decide whether to offer the move
#: actions. Reaching into the persistence layer for that would have `ui/` importing a module it
#: has no other business with (`ARCHITECTURE.md` §3).

#: The legal transition table, transcribed from `ARCHITECTURE.md` §5's diagram.
#:
#: Read it as "from this state, these are the only states reachable in one step". Every
#: non-terminal state can reach `CANCELLED`, because `REQ-015` requires cancel to work at any
#: point — a cancel refused because a job is mid-probe is a UI that lies about what its
#: buttons do.
_TRANSITIONS: Final[dict[JobStatus, frozenset[JobStatus]]] = {
    JobStatus.QUEUED: frozenset({JobStatus.PROBING, JobStatus.FAILED, JobStatus.CANCELLED}),
    JobStatus.PROBING: frozenset({JobStatus.READY, JobStatus.FAILED, JobStatus.CANCELLED}),
    JobStatus.READY: frozenset({JobStatus.RUNNING, JobStatus.FAILED, JobStatus.CANCELLED}),
    # `RUNNING → PAUSED` and `PAUSED → RUNNING` were removed by `T-080`. See `JobStatus` for why;
    # the short version is that `UX-001`'s pause never changes a job's status, so both edges were
    # unreachable and the second one's comment ("resume returns to RUNNING, not READY") was
    # reasoning about a transition nothing could take.
    JobStatus.RUNNING: frozenset(
        {
            JobStatus.POST_PROCESSING,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        }
    ),
    JobStatus.POST_PROCESSING: frozenset(
        {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
    ),
    # Retry, and only retry. It re-enters the queue rather than resuming in place, so the
    # attempt counter and the queue position are the caller's to update (`REQ-018`).
    JobStatus.FAILED: frozenset({JobStatus.QUEUED}),
    JobStatus.COMPLETED: frozenset(),
    JobStatus.CANCELLED: frozenset(),
}


class IllegalTransitionError(Exception):
    """Raised when a transition outside `_TRANSITIONS` is attempted.

    An exception rather than a `False` return, on purpose. A boolean invites being ignored at
    the call site, and the failure it reports — a queue whose stored state no longer describes
    reality — is precisely the one that must not be allowed to continue quietly.
    """

    def __init__(self, source: JobStatus, target: JobStatus) -> None:
        self.source = source
        self.target = target
        allowed = sorted(status.value for status in _TRANSITIONS[source])
        detail = ", ".join(allowed) if allowed else "nothing — it is terminal"
        super().__init__(
            f"cannot move a job from {source.value} to {target.value}; "
            f"{source.value} allows: {detail}"
        )


def allowed_from(status: JobStatus) -> frozenset[JobStatus]:
    """Every status reachable from `status` in one step. Empty for a terminal state."""
    return _TRANSITIONS[status]


def can_transition(source: JobStatus, target: JobStatus) -> bool:
    """Whether `source → target` is legal. The predicate behind `apply()`.

    Exposed so the UI can disable an action rather than offer it and catch the exception —
    presenting a button that always raises is not a usable interface.
    """
    return target in _TRANSITIONS[source]


def apply(source: JobStatus, target: JobStatus) -> JobStatus:
    """Return `target` if `source → target` is legal, else raise `IllegalTransitionError`.

    Returns rather than mutates because `Job` is frozen: the caller rebuilds the job with the
    new status (`Job.with_status`), which keeps the state machine free of any knowledge of how
    a job is stored.
    """
    if not can_transition(source, target):
        raise IllegalTransitionError(source, target)
    return target


def is_terminal(status: JobStatus) -> bool:
    """Whether the job is finished for good. See `TERMINAL` for why `FAILED` is not."""
    return status in TERMINAL
