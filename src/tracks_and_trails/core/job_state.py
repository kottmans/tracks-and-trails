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
    PAUSED = "paused"
    POST_PROCESSING = "post_processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


#: States from which nothing further happens.
#:
#: `FAILED` is deliberately **not** here: `ARCHITECTURE.md` §5 has `FAILED ──retry──▶ QUEUED`,
#: and `REQ-018` requires a failed job to stay in the queue and offer retry. A job that failed
#: is finished with *this attempt*, not with its life.
TERMINAL: Final = frozenset({JobStatus.COMPLETED, JobStatus.CANCELLED})

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
    JobStatus.RUNNING: frozenset(
        {
            JobStatus.POST_PROCESSING,
            JobStatus.PAUSED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        }
    ),
    # Resume returns to RUNNING. It does not go back to READY: the partial download and the
    # already-resolved format belong to this attempt, and re-entering READY would imply
    # re-deciding them (`REQ-015`).
    JobStatus.PAUSED: frozenset({JobStatus.RUNNING, JobStatus.FAILED, JobStatus.CANCELLED}),
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
