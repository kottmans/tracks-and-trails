"""What a queue row offers, and only what its state permits (`UX-005` §4 and §5, `T-124`).

**The rule is `T081-R3`'s, moved from the toolbar to the row.** Nothing is drawn disabled and
nothing is drawn that would be refused: a greyed *Retry* on a running download tells the user the
application considered retrying and declined, which is a different and wronger statement than not
offering it. A row offers what it permits and says nothing about the rest.

## Why this is a table and not a chain of `if`s

`ai/TESTING.md` §13's rule is that a test must transcribe its expectation from the specification
rather than ask production what to expect. That only works if the specification is *transcribable*
— so the mapping lives in one literal, `UX-005`'s four rows are visible in it side by side, and
the test writes the same four rows out by hand. Two hand-maintained lists is exactly what §13
warns against for *derived* sets; here the whole point is that they are independent copies of an
external authority, and the test fails when they diverge.

## Three states `UX-005` does not name

Its table has *Running*, *Queued*, *Failed* and *Done*. The pipeline has eight statuses, so
`PROBING`, `POST_PROCESSING` and `CANCELLED` are decided here by the entry's own principle rather
than invented: the first two are states in which a worker holds the job, which is what *Running*
means for this purpose, and a cancelled job has no file to open and nothing to retry, so the only
honest verb left is the one that removes the row. **This is a reading of `UX-005`, not part of
it** — worth an amendment to that entry rather than leaving the reading only here.
"""

from enum import StrEnum
from typing import Final

from tracks_and_trails.core.job_state import JobStatus

__all__ = ["LABELS", "MORE_LABEL", "Verb", "verbs_for"]


class Verb(StrEnum):
    """A thing a row can offer. The value is stable and is what a signal carries."""

    CANCEL = "cancel"
    MOVE_UP = "move_up"
    MOVE_DOWN = "move_down"
    RETRY = "retry"
    REMOVE = "remove"
    OPEN = "open"
    REVEAL = "reveal"


#: What each verb says on the row. Short because they share a line with the format control and
#: `NFR-006` wants the extractor's message to keep the full width above it.
LABELS: Final[dict[Verb, str]] = {
    Verb.CANCEL: "Cancel",
    Verb.MOVE_UP: "↑",
    Verb.MOVE_DOWN: "↓",
    Verb.RETRY: "Retry",
    Verb.REMOVE: "Remove",
    Verb.OPEN: "Open",
    Verb.REVEAL: "Show in folder",
}

#: The overflow, and **the declared keyboard route** (`UX-005` §4, `NFR-005`). Drawn on every row
#: whatever its state, so reaching a row's verbs without a pointer is one key rather than a
#: different key per state — and so the row never has an empty right end that reads as "no
#: actions here" when it means "none that fit".
MORE_LABEL: Final = "⋯"

#: `UX-005` §4, transcribed. The order is the order they are drawn, left to right.
_BY_STATUS: Final[dict[JobStatus, tuple[Verb, ...]]] = {
    # Queued — the row has never started, so it can be moved and abandoned.
    JobStatus.QUEUED: (Verb.MOVE_UP, Verb.MOVE_DOWN, Verb.CANCEL),
    JobStatus.READY: (Verb.MOVE_UP, Verb.MOVE_DOWN, Verb.CANCEL),
    # Running — a worker holds it. `UX-005` §7: there is no per-job pause, so `Cancel` is the
    # only thing that can be said about a download in flight.
    JobStatus.PROBING: (Verb.CANCEL,),
    JobStatus.RUNNING: (Verb.CANCEL,),
    JobStatus.POST_PROCESSING: (Verb.CANCEL,),
    # Failed — `REQ-018`'s edge. Whether the *retry* is honest depends on the error kind as well
    # as the status; `verbs_for` takes that as an argument rather than guessing.
    JobStatus.FAILED: (Verb.RETRY, Verb.REMOVE),
    # Done — `REQ-021`'s two file actions, and `UX-005` §8 keeps the row in the Queue tab until
    # *Clear finished*, so this is where a user answers "did it work".
    JobStatus.COMPLETED: (Verb.OPEN, Verb.REVEAL),
    # Cancelled — no file, nothing to retry. Not in `UX-005`'s table; see the module docstring.
    JobStatus.CANCELLED: (Verb.REMOVE,),
}


def verbs_for(status: JobStatus, *, retryable: bool = True) -> tuple[Verb, ...]:
    """The verbs a row in `status` offers, in the order they are drawn.

    **`retryable` is not a style choice.** `core/errors.py` decides whether a failure can be tried
    again, and `job_detail` already asks it rather than assuming — offering the button implies a
    workaround exists, and a *Retry* that re-runs an unretryable failure spends a worker to
    produce the same error. A failed row that cannot be retried still offers *Remove*, so it is
    never left with nothing.

    Every status is in the table, so an unmapped one is a programming error rather than a row with
    no verbs — a silent empty tuple is how a whole state loses its actions without a test noticing.
    """
    offered = _BY_STATUS[status]
    if not retryable:
        return tuple(verb for verb in offered if verb is not Verb.RETRY)
    return offered
