"""The parent/child IPC contract.

Every object crossing the process boundary is a picklable dataclass declared here.
Raw yt-dlp info dicts are never sent; they are projected first (`ARC-002`).

`ARCHITECTURE.md` §3 makes that projection rule load-bearing rather than stylistic: an
`info_dict`'s shape belongs to yt-dlp and changes without notice (`NFR-008`). If it crossed the
boundary, every layer that touched it would silently depend on yt-dlp's internals, and an
upstream rename would surface as a `KeyError` in the GUI rather than a failing adapter test.
`ytdlp_adapter.py` projects into `core.models`; only those declared types travel.

## Sessions, outcomes, and the sentinel

A worker runs exactly one **session** — a probe or a download — and a session produces exactly
one **outcome** followed by the sentinel:

```
probe     : Progress(PROBING)*   then  Probed | Failed        then WorkerFinished
download  : Progress(...)*       then  Succeeded | Failed     then WorkerFinished
```

This structure is the contract, not a convention, and `validate_sequence()` is its executable
form. `T011-R1` found why it has to be: an earlier version had only "terminal" success and
failure, so a **successful probe produced no outcome at all** — `Probed` then `WorkerFinished`,
neither counted. A receiver that treats "exited 0 with no outcome" as `WORKER_CRASH` (`T-013`,
`REQ-028`) would then have misclassified every successful probe, or special-cased a rule this
module never expressed.

So `Probed` is an outcome, and which outcomes are legal depends on the session kind.
`WorkerFinished` remains **not** an outcome: job result and stream completion are different
facts, and folding them together would make a worker that crashed after reporting success
indistinguishable from one that shut down cleanly.

## What this module enforces, and what it does not

Constructors validate **payload shape**: declared types, no raw dicts, real enum members,
immutable context. `validate_sequence()` validates a **whole session** and is what `T-013`
enforces on receipt — including terminal-once, which no constructor can check because nothing
in a dataclass knows what was sent before it.

**No runtime version negotiation.** Both ends ship in the same artifact and are always the same
build; updating yt-dlp in place (`OPS-002`) changes the *engine*, not this contract. `ARC-002`
calls the protocol "a versioned internal contract", which reads as version-*controlled* rather
than version-*negotiated* — but that is the accepted decision's wording and this module does not
get to reinterpret it (`T011-R5`). The narrow claim here is only that there is no handshake.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final, TypeGuard

from tracks_and_trails.core.errors import ErrorKind, normalise_context
from tracks_and_trails.core.models import MediaInfo


class Stage(StrEnum):
    """The pipeline stages `REQ-014` requires progress to name."""

    PROBING = "probing"
    DOWNLOADING_VIDEO = "downloading_video"
    DOWNLOADING_AUDIO = "downloading_audio"
    MERGING = "merging"
    POST_PROCESSING = "post_processing"


class SessionKind(StrEnum):
    """What a worker was started to do. Determines which outcomes are legal."""

    PROBE = "probe"
    DOWNLOAD = "download"


def _require_optional_count(owner: str, name: str, value: object) -> None:
    """Reject anything that is not a non-negative `int` or `None`.

    `bool` is excluded explicitly: it is an `int` subclass, so `isinstance(True, int)` passes
    and `True` would be stored as a byte count of 1.
    """
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{owner}.{name} must be an int or None, not {type(value).__name__}")
    if value < 0:
        raise ValueError(f"{owner}.{name} cannot be negative")


def _require_optional_rate(owner: str, name: str, value: object) -> None:
    """Reject anything that is not a non-negative real number or `None`.

    Separate from `_require_optional_count` because a transfer rate is legitimately
    fractional, while a byte count is not.
    """
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{owner}.{name} must be a number or None, not {type(value).__name__}")
    if value < 0:
        raise ValueError(f"{owner}.{name} cannot be negative")


class ProtocolViolationError(Exception):
    """A message sequence that this contract forbids.

    Raised by `validate_sequence()`. Distinct from `ValueError` — which a *constructor* raises
    for a malformed single message — because the receiver handles the two differently: a bad
    message is discarded, a bad sequence means the worker cannot be trusted at all.
    """


# All messages are keyword-only (`T011-R3`). Two reasons, and the second is the important one:
# inheritance no longer forces defaults onto required fields, so signatures stop advertising
# `media: MediaInfo | None = None` for something the constructor rejects as None; and a
# positional call site cannot silently shift meaning when a field is added.
@dataclass(frozen=True, slots=True, kw_only=True)
class _Message:
    """Fields every message shares.

    Frozen: a message is a value that has already been sent. `multiprocessing.Queue` may
    serialize on its feeder thread *after* `put()` returns, so a mutable message could be
    changed between those two moments and alter what the parent receives — the hazard
    `T010-R2` found in `FailureDetail.context`.
    """

    job_id: str

    def __post_init__(self) -> None:
        identifier: Any = self.job_id
        if not isinstance(identifier, str) or not identifier:
            raise ValueError(
                f"{type(self).__name__} requires a non-empty string job_id: the result queue "
                "is shared across workers, so an unattributable message cannot be routed"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class Probed(_Message):
    """A probe succeeded. The **outcome** of a probe session.

    Carries the projection, never the `info_dict` — and that is enforced, not merely intended
    (`T011-R2`). A dict here previously constructed, validated and pickled happily, which is
    precisely the `ARC-002` violation this module exists to prevent.
    """

    media: MediaInfo

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.media, MediaInfo):
            raise TypeError(
                f"Probed.media must be a MediaInfo projection, not {type(self.media).__name__}. "
                "A raw yt-dlp info_dict must never cross the process boundary (ARC-002)."
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class Progress(_Message):
    """A progress update (`REQ-014`). Never an outcome.

    `stage` is **required** (`T011-R3`): it previously defaulted to `PROBING`, so forgetting it
    produced a valid message that confidently misreported which stage the job was in.

    The quantities stay optional because yt-dlp genuinely omits them — a live stream has no
    total, and speed and ETA are absent until enough data has moved. Modelling them as required
    would mean inventing numbers the UI would display as fact.
    """

    stage: Stage
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed_bytes_per_second: float | None = None
    eta_seconds: int | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.stage, Stage):
            raise TypeError(f"Progress.stage must be a Stage, not {type(self.stage).__name__}")
        for name in ("downloaded_bytes", "total_bytes", "eta_seconds"):
            _require_optional_count("Progress", name, getattr(self, name))
        # `T011-R2`, second round: this field was the one the first correction missed. It
        # accepted a mutable dict, which pickled, passed `is_message()` and stayed mutable
        # after construction — the same feeder-thread hazard, on a field nobody had listed.
        _require_optional_rate("Progress", "speed_bytes_per_second", self.speed_bytes_per_second)

    @property
    def fraction(self) -> float | None:
        """Completion in [0, 1], or `None` when the total is unknown.

        `None` rather than `0.0`, matching `Job.progress`: a live stream and a stalled download
        are different states, and a confident zero misreports both.
        """
        if not self.total_bytes or self.downloaded_bytes is None:
            return None
        return min(self.downloaded_bytes / self.total_bytes, 1.0)


@dataclass(frozen=True, slots=True, kw_only=True)
class Succeeded(_Message):
    """The outcome of a download session that produced a file."""

    output_path: str
    total_bytes: int | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        path: Any = self.output_path
        if not isinstance(path, str) or not path:
            raise ValueError(
                "Succeeded requires the output path; a success that cannot say what it wrote "
                "is indistinguishable from a failure to the user"
            )
        # `T011-R2`, second round: the other field the first correction missed.
        _require_optional_count("Succeeded", "total_bytes", self.total_bytes)


@dataclass(frozen=True, slots=True, kw_only=True)
class Failed(_Message):
    """The outcome of a session that failed, classified, with the original text intact.

    Both halves are required (`NFR-006`, `REQ-005`). A classification without the message
    throws away the only actionable information the user had; a message without a
    classification leaves the parent unable to decide retry policy (`REQ-018`).

    Mirrors `Job.error_kind` / `Job.error_message` so `T-014`'s persistence is a direct
    mapping. `context` is normalised by the **same** helper `FailureDetail` uses, rather than a
    near-copy — duplicating the shape without duplicating the guarantees is what `T011-R2`
    caught.
    """

    kind: ErrorKind
    message: str
    context: tuple[tuple[str, str], ...] = field(default=())

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.kind, ErrorKind):
            raise TypeError(
                f"Failed.kind must be an ErrorKind, not {type(self.kind).__name__}; "
                "retry policy is decided from it (REQ-018)"
            )
        text: Any = self.message
        if not isinstance(text, str) or not text:
            raise ValueError(
                "Failed requires the original message verbatim (NFR-006); a classification "
                "alone discards what the extractor actually said"
            )
        object.__setattr__(self, "context", normalise_context(self.context))


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkerFinished(_Message):
    """The sentinel. **The last thing a worker puts on the queue, always.**

    Sent after the outcome and after any cleanup, so the parent's blocking `Queue.get()` has a
    definite end rather than relying on a timeout or on tearing down a thread mid-read
    (`ARCHITECTURE.md` §3).

    Not an outcome: it reports that the stream ended, not what the job achieved.
    """

    exit_code: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise TypeError(f"WorkerFinished.exit_code must be an int, not {self.exit_code!r}")


#: Every declared message type. The validator and the tests both derive from this, so adding a
#: type without exercising it fails the suite rather than silently going untested.
MESSAGE_TYPES: Final[tuple[type[_Message], ...]] = (
    Probed,
    Progress,
    Succeeded,
    Failed,
    WorkerFinished,
)

#: Messages that report what a *job* achieved. `WorkerFinished` is deliberately absent.
OUTCOME_TYPES: Final[tuple[type[_Message], ...]] = (Probed, Succeeded, Failed)

#: Which outcomes each session kind may legally produce (`T011-R1`).
_LEGAL_OUTCOMES: Final[dict[SessionKind, tuple[type[_Message], ...]]] = {
    SessionKind.PROBE: (Probed, Failed),
    SessionKind.DOWNLOAD: (Succeeded, Failed),
}

Message = Probed | Progress | Succeeded | Failed | WorkerFinished


def is_message(candidate: object) -> TypeGuard[Message]:
    """Whether `candidate` is a declared protocol message.

    **Exact type match, not `isinstance`** (`T011-R2`). "Declared" is the invariant, and a
    subclass is not declared: it can add fields, override validation, and carry anything at
    all across the boundary while satisfying an `isinstance` check.

    Lives here rather than at either seam so both ends share one definition of valid. A bare
    `dict` is the case it exists for — it pickles happily and would otherwise be discovered as
    an `AttributeError` in the GUI thread.
    """
    return type(candidate) in MESSAGE_TYPES


def is_outcome(message: object) -> bool:
    """Whether `message` reports what the job achieved.

    A session produces **exactly one**. Enforcing that is the receiver's job (`T-013`), because
    no constructor can know what was already sent; this predicate is what the receiver enforces
    it *with*, so the rule tracks the protocol rather than a hardcoded list.
    """
    return type(message) in OUTCOME_TYPES


def legal_outcomes(kind: SessionKind) -> tuple[type[_Message], ...]:
    """The outcome types `kind` may produce. A probe cannot succeed at downloading."""
    return _LEGAL_OUTCOMES[kind]


def stage_of(message: object) -> Stage | None:
    """The stage a message reports, or `None` if it reports none."""
    return message.stage if isinstance(message, Progress) else None


def validate_sequence(kind: SessionKind, messages: Sequence[object]) -> None:
    """Raise `ProtocolViolationError` unless `messages` is a legal `kind` session.

    The executable form of the contract at the top of this module, and what `T-013` enforces on
    receipt. Checked here rather than left to prose because every rule below is a way for the
    system to hang or lie rather than raise:

    - an unattributed or mixed-job stream cannot be routed;
    - a missing outcome is indistinguishable from a crash (`REQ-028`);
    - a second outcome would drive a second state transition for one job;
    - an outcome the session kind cannot produce means the worker is not doing what was asked;
    - a missing or non-final sentinel leaves `ResultPump` blocked on `Queue.get()` forever.
    """
    if not messages:
        raise ProtocolViolationError("a session must send at least an outcome and the sentinel")

    for item in messages:
        if not is_message(item):
            raise ProtocolViolationError(f"undeclared object on the queue: {item!r}")

    declared = [m for m in messages if isinstance(m, _Message)]
    job_ids = {m.job_id for m in declared}
    if len(job_ids) > 1:
        raise ProtocolViolationError(f"one session must carry one job id; saw {sorted(job_ids)}")

    sentinels = [i for i, m in enumerate(declared) if isinstance(m, WorkerFinished)]
    if not sentinels:
        raise ProtocolViolationError(
            "no WorkerFinished: the receiver blocks on Queue.get() and would never stop"
        )
    if len(sentinels) > 1:
        raise ProtocolViolationError(f"{len(sentinels)} sentinels; exactly one ends the stream")
    if sentinels[0] != len(declared) - 1:
        raise ProtocolViolationError(
            f"WorkerFinished is at position {sentinels[0]} of {len(declared)}; "
            "it must be the last message"
        )

    outcomes = [m for m in declared if is_outcome(m)]
    if not outcomes:
        raise ProtocolViolationError(
            f"a {kind.value} session produced no outcome; a receiver cannot tell that from a "
            "crashed worker (REQ-028)"
        )
    if len(outcomes) > 1:
        raise ProtocolViolationError(
            f"{len(outcomes)} outcomes for one job: {[type(m).__name__ for m in outcomes]}; "
            "a session has exactly one"
        )

    outcome = outcomes[0]
    if type(outcome) not in legal_outcomes(kind):
        allowed = ", ".join(t.__name__ for t in legal_outcomes(kind))
        raise ProtocolViolationError(
            f"a {kind.value} session cannot produce {type(outcome).__name__}; allowed: {allowed}"
        )

    outcome_at = declared.index(outcome)
    later = [type(m).__name__ for m in declared[outcome_at + 1 : -1]]
    if later:
        raise ProtocolViolationError(f"messages after the outcome: {later}")

    # `T011-R7`: the module documents the probe grammar as `Progress(PROBING)*`, and claims
    # this function is its executable form — but a probe reporting `MERGING` validated. A probe
    # extracts metadata; it cannot download, merge or post-process, so any other stage is a
    # misreport of `REQ-014` state rather than an unusual-but-legal pipeline.
    #
    # Deliberately *not* generalised to download-stage ordering. Real yt-dlp pipelines skip and
    # repeat stages — a format needing no merge never reports `MERGING` — so ordering there is
    # the adapter's business (`T-012`) and the end-to-end gate's (`T-037`), not this contract's.
    if kind is SessionKind.PROBE:
        wrong = sorted(
            {
                m.stage.value
                for m in declared
                if isinstance(m, Progress) and m.stage is not Stage.PROBING
            }
        )
        if wrong:
            raise ProtocolViolationError(
                f"a probe session reported stage(s) {wrong}; a probe only extracts metadata, "
                f"so {Stage.PROBING.value!r} is its only legal progress stage"
            )
