"""The parent/child IPC contract.

Every object crossing the process boundary is a picklable dataclass declared here.
Raw yt-dlp info dicts are never sent; they are projected first (`ARC-002`).

`ARCHITECTURE.md` §3 makes that projection rule load-bearing rather than stylistic: an
`info_dict`'s shape belongs to yt-dlp and changes without notice (`NFR-008`). If it crossed the
boundary, every layer that touched it would silently depend on yt-dlp's internals, and an
upstream rename would surface as a `KeyError` in the GUI rather than a failing adapter test.
`ytdlp_adapter.py` projects into `core.models`; only those declared types travel.

**Three things beyond the payloads are part of this contract, because leaving them to the
receiver is how this design hangs rather than raises:**

- **Every message carries `job_id`.** Workers are one-per-job but the queue is shared, so a
  message without an id cannot be attributed, and "exactly one terminal message per job" cannot
  be checked at all.
- **`WorkerFinished` is a sentinel and the last thing a worker sends.** `ResultPump` does a
  blocking `Queue.get()`; without a sentinel, shutdown depends on a timeout or on killing a
  thread mid-read.
- **Terminal-once is specified here and enforced by the receiver.** Message classes cannot
  prevent a worker sending two terminal messages — nothing in a dataclass constructor knows
  what was sent before it. `is_terminal()` exists so `T-013` can enforce the rule against the
  protocol rather than a hardcoded list that drifts as types are added.

**No protocol versioning, deliberately.** Both ends ship in the same artifact and are always
the same build. Updating yt-dlp in place (`OPS-002`) changes the *engine*, not this contract.
Recorded so nobody later adds negotiation machinery for a skew that cannot occur.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final, TypeGuard

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.models import MediaInfo


class Stage(StrEnum):
    """The pipeline stages `REQ-014` requires progress to name.

    A `StrEnum` for the same reason as `JobStatus`: these cross a process boundary and are
    displayed, so a stable string beats an ordinal.
    """

    PROBING = "probing"
    DOWNLOADING_VIDEO = "downloading_video"
    DOWNLOADING_AUDIO = "downloading_audio"
    MERGING = "merging"
    POST_PROCESSING = "post_processing"


@dataclass(frozen=True, slots=True)
class _Message:
    """Fields every message shares.

    Frozen: a message is a value that has already been sent. `multiprocessing.Queue` may
    serialize on its feeder thread *after* `put()` returns, so a mutable message could be
    changed between those two moments and alter what the parent receives — the same hazard
    `T010-R2` found in `FailureDetail.context`.
    """

    job_id: str

    def __post_init__(self) -> None:
        if not self.job_id:
            raise ValueError(
                f"{type(self).__name__} requires a job_id: the result queue is shared across "
                "workers, so an unattributable message cannot be routed or counted"
            )


@dataclass(frozen=True, slots=True)
class Probed(_Message):
    """A probe succeeded. Carries the projection, never the `info_dict`."""

    media: MediaInfo | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.media is None:
            raise ValueError("Probed requires the MediaInfo it probed")


@dataclass(frozen=True, slots=True)
class Progress(_Message):
    """A progress update (`REQ-014`).

    Every quantity is optional except the stage, because yt-dlp genuinely omits them: a live
    stream has no total, and speed and ETA are absent until enough data has moved. Modelling
    them as required would mean inventing numbers the UI would then display as fact.
    """

    stage: Stage = Stage.PROBING
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed_bytes_per_second: float | None = None
    eta_seconds: int | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.downloaded_bytes is not None and self.downloaded_bytes < 0:
            raise ValueError("downloaded_bytes cannot be negative")
        if self.total_bytes is not None and self.total_bytes < 0:
            raise ValueError("total_bytes cannot be negative")

    @property
    def fraction(self) -> float | None:
        """Completion in [0, 1], or `None` when the total is unknown.

        `None` rather than `0.0`, matching `Job.progress`: a live stream and a stalled download
        are different states, and a confident zero misreports both.
        """
        if not self.total_bytes or self.downloaded_bytes is None:
            return None
        return min(self.downloaded_bytes / self.total_bytes, 1.0)


@dataclass(frozen=True, slots=True)
class Succeeded(_Message):
    """Terminal. The job produced a file."""

    output_path: str = ""
    total_bytes: int | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.output_path:
            raise ValueError(
                "Succeeded requires the output path; a success that cannot say what it wrote "
                "is indistinguishable from a failure to the user"
            )


@dataclass(frozen=True, slots=True)
class Failed(_Message):
    """Terminal. The job failed, classified, with the original text intact.

    Both halves are required (`NFR-006`, `REQ-005`). A classification without the message
    throws away the only actionable information the user had; a message without a
    classification leaves the parent unable to decide retry policy (`REQ-018`).
    """

    kind: ErrorKind | None = None
    message: str = ""
    context: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.kind is None:
            raise ValueError("Failed requires an ErrorKind classification (REQ-018)")
        if not self.message:
            raise ValueError(
                "Failed requires the original message verbatim (NFR-006); a classification "
                "alone discards what the extractor actually said"
            )


@dataclass(frozen=True, slots=True)
class WorkerFinished(_Message):
    """The sentinel. **The last thing a worker puts on the queue, always.**

    Sent after the terminal message, and after any cleanup, so the parent's blocking
    `Queue.get()` has a definite end rather than relying on a timeout or on tearing down a
    thread mid-read (`ARCHITECTURE.md` §3).

    Distinct from `Succeeded`/`Failed` on purpose: the *outcome* and the *end of the stream*
    are different facts. Conflating them would mean a worker that crashed after reporting
    success looked identical to one that shut down cleanly.
    """

    exit_code: int = 0


#: Every declared message type. The validator and the tests both derive from this, so adding a
#: type without exercising it fails the suite rather than silently going untested.
MESSAGE_TYPES: Final[tuple[type[_Message], ...]] = (
    Probed,
    Progress,
    Succeeded,
    Failed,
    WorkerFinished,
)

#: The outcome messages. `WorkerFinished` is **not** terminal: it ends the stream, not the job.
_TERMINAL_TYPES: Final[tuple[type[_Message], ...]] = (Succeeded, Failed)

#: What a caller may legally receive. The alias exists so `T-013`'s signatures read as the
#: protocol rather than as a private base class.
Message = Probed | Progress | Succeeded | Failed | WorkerFinished


def is_terminal(message: object) -> bool:
    """Whether `message` is a job's final outcome.

    A job has **exactly one** terminal message. This function is the definition of "terminal";
    the receiver (`T-013`) enforces the once-only rule by job id, because no constructor can
    know what was already sent.
    """
    return isinstance(message, _TERMINAL_TYPES)


def is_message(candidate: object) -> TypeGuard[Message]:
    """Whether `candidate` is a declared protocol message.

    Lives here rather than at either seam so both ends share one definition of "valid". A bare
    `dict` is the specific thing this rejects: it is what a careless worker would send after a
    refactor, it pickles happily, and it would otherwise be discovered as an `AttributeError`
    in the GUI thread rather than at the boundary.
    """
    return isinstance(candidate, MESSAGE_TYPES)


def stage_of(message: object) -> Stage | None:
    """The stage a message reports, or `None` if it reports none.

    A convenience for the receiver, so `T-013` need not special-case `Progress` to decide
    whether a message carries stage information.
    """
    return message.stage if isinstance(message, Progress) else None
