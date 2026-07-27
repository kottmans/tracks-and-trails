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

**No runtime version negotiation** — no version field, no handshake, no compatibility ranges.
Both ends ship in the same artifact and are always the same build; updating yt-dlp in place
(`OPS-002`) changes the *engine*, not this contract.

`ARC-002` calls the protocol "a versioned internal contract"; `ARC-003` (accepted 2026-07-26,
from `T011-R5`) settles that this means version-*controlled* — one module, declared types,
changed only alongside its tests — rather than version-*negotiated*. That decision names its own
expiry: **if parent and child ever become separately deployable** (a standalone worker binary, an
external helper, a plugin model), skew becomes reachable and the question re-opens. Anyone
proposing such a change should read `ARC-003` before touching this module.
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
class ResolutionReport(_Message):
    """Which yt-dlp this session actually used, and what it rejected to get there (`T012-R1`).

    `REQ-025` requires the resolved version to be reported, and `ARCHITECTURE.md` §6 requires a
    rejected override to be **reported, never silently ignored**. Both facts were computed
    correctly inside the worker and then reached the parent only when a session happened to
    fail — a successful probe emitted `Progress`, `Probed` and the sentinel and nothing else. A
    guarantee the parent cannot observe is not a guarantee, and "the fallback says so" was true
    only of the worker's own local variable.

    Its own message rather than fields on `Probed`/`Succeeded`: it describes the *environment*,
    not the job's result, it is identical for both outcome types, and a session that fails
    after resolving should carry it too.

    **Not an outcome.** It reports what the worker is running, not what the job achieved, so it
    must never satisfy the "exactly one outcome" rule.

    Carries labels, never filesystem paths (`NFR-007`): `source` is a description such as
    "bundled baseline", and `rejected` reasons have the candidate directory replaced before
    they are attached.
    """

    ytdlp_version: str
    ytdlp_source: str
    rejected: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        for name in ("ytdlp_version", "ytdlp_source"):
            value: Any = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise TypeError(
                    f"ResolutionReport.{name} must be a non-empty string, not {value!r}. "
                    "An empty one would report a resolution that never happened."
                )
        # Bound through `Any` deliberately, matching `Failed.message` above: these values arrive
        # unpickled from another process, so the annotation is a claim about the sender rather
        # than a guarantee about the bytes. Static narrowing would delete the check that matters.
        rejected: Any = self.rejected
        if not isinstance(rejected, tuple) or not all(isinstance(entry, str) for entry in rejected):
            raise TypeError(
                f"ResolutionReport.rejected must be a tuple of strings, not {rejected!r}"
            )


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
    ResolutionReport,
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

Message = Probed | Progress | ResolutionReport | Succeeded | Failed | WorkerFinished


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


class SessionValidator:
    """The contract enforced **as each message arrives**, rather than after the fact.

    This is the form `T-013`'s receiver needs and `validate_sequence()` is a wrapper around
    (`T013-R1`). The distinction is not stylistic: the receiver routes each message onward, and
    routing an illegal one persists job state and tells the GUI about a result that the contract
    forbids. Validating the finished stream afterwards reports the violation *after* the damage,
    which made the executable receiver strictly weaker than the rules written here.

    Every rule below is decidable when the message arrives, given only what came before it. The
    two that are not — a session that never produced an outcome, and one that never ended — live
    in `complete()`, because until the stream stops they are indistinguishable from a stream that
    has not finished yet.

    **One implementation, two entry points.** A per-message checker written separately from
    `validate_sequence()` would be a second hand-maintained statement of one grammar, and this
    project has repeatedly found that two such statements drift apart without anything noticing
    (`T010-R1`, `T041-R2`). So `validate_sequence()` feeds this class and adds nothing of its own.
    """

    def __init__(self, kind: SessionKind, job_id: str | None = None) -> None:
        self._kind = kind
        #: The job this stream is allowed to describe. `None` means "bind to the first message",
        #: which is what a whole-stream check does; the receiver passes the id it asked for, so a
        #: stream consistently claiming to be a *different* job is caught (`T013-R1`). The old
        #: check only rejected a stream that changed its mind halfway.
        self._job_id = job_id
        self._outcome: _Message | None = None
        self._reports = 0
        self._finished = False
        self._seen = 0

    @property
    def outcome(self) -> _Message | None:
        """The one legal outcome, once it has arrived."""
        return self._outcome

    @property
    def finished(self) -> bool:
        """Whether the sentinel has been accepted."""
        return self._finished

    def accept(self, item: object) -> None:
        """Admit one message, or raise `ProtocolViolationError` describing why not."""
        if not is_message(item):
            raise ProtocolViolationError(f"undeclared object on the queue: {item!r}")
        message: _Message = item  # narrowed by `is_message`
        self._seen += 1

        if self._finished:
            raise ProtocolViolationError(
                f"{type(message).__name__} arrived after WorkerFinished; the sentinel is the "
                "last thing a worker sends"
            )

        if self._job_id is None:
            self._job_id = message.job_id
        elif message.job_id != self._job_id:
            raise ProtocolViolationError(
                f"a message for job {message.job_id!r} arrived on job {self._job_id!r}'s "
                "stream; one session carries one job id, and an unattributable message "
                "cannot be routed"
            )

        if isinstance(message, WorkerFinished):
            self._finished = True
            return

        if is_outcome(message):
            # Checked before the general post-outcome rule below, because a *second outcome* is
            # a materially different fault from a stray progress message: it is the one that
            # would drive a second state transition for one job (`T011-R4`), and the receiver's
            # log should say so rather than describing it as late chatter.
            if self._outcome is not None:
                raise ProtocolViolationError(
                    f"a second outcome ({type(message).__name__}) for job {self._job_id!r}; "
                    "a session has exactly one"
                )
            self._accept_outcome(message)
            return

        if self._outcome is not None:
            raise ProtocolViolationError(
                f"messages after the outcome: [{type(message).__name__!r}]"
            )

        if isinstance(message, ResolutionReport):
            # `T012-R1`: one session resolves yt-dlp once, so it reports that once. Two reports
            # would mean either a second resolution or a duplicated message, and the parent
            # would have no way to tell which one describes the run.
            self._reports += 1
            if self._reports > 1:
                raise ProtocolViolationError(
                    f"{self._reports} ResolutionReports for one session; a session resolves "
                    "yt-dlp once"
                )
            return

        if isinstance(message, Progress):
            self._check_stage(message)

    def _accept_outcome(self, message: _Message) -> None:
        if type(message) not in legal_outcomes(self._kind):
            allowed = ", ".join(t.__name__ for t in legal_outcomes(self._kind))
            raise ProtocolViolationError(
                f"a {self._kind.value} session cannot produce {type(message).__name__}; "
                f"allowed: {allowed}"
            )
        self._outcome = message

    def _check_stage(self, message: Progress) -> None:
        """`T011-R7`: a probe extracts metadata, so `PROBING` is its only legal stage.

        Deliberately *not* generalised to download-stage ordering. Real yt-dlp pipelines skip and
        repeat stages — a format needing no merge never reports `MERGING` — so ordering there is
        the adapter's business (`T-012`) and the end-to-end gate's (`T-037`), not this contract's.
        """
        if self._kind is SessionKind.PROBE and message.stage is not Stage.PROBING:
            raise ProtocolViolationError(
                f"a probe session reported stage(s) ['{message.stage.value}']; a probe only "
                f"extracts metadata, so {Stage.PROBING.value!r} is its only legal progress stage"
            )

    def complete(self) -> None:
        """Raise unless the stream that just ended was a complete session.

        The two rules that need the end: a session with no outcome cannot be told from a crashed
        worker (`REQ-028`), and one with no sentinel leaves `ResultPump` blocked on `Queue.get()`
        forever.
        """
        if self._seen == 0:
            raise ProtocolViolationError("a session must send at least an outcome and the sentinel")
        if self._outcome is None:
            raise ProtocolViolationError(
                f"a {self._kind.value} session produced no outcome; a receiver cannot tell that "
                "from a crashed worker (REQ-028)"
            )
        if not self._finished:
            raise ProtocolViolationError(
                "no WorkerFinished: the receiver blocks on Queue.get() and would never stop"
            )


def validate_sequence(kind: SessionKind, messages: Sequence[object]) -> None:
    """Raise `ProtocolViolationError` unless `messages` is a legal `kind` session.

    The whole-stream form of the contract at the top of this module. It is now a loop over
    `SessionValidator`, which is the same grammar applied message by message — the receiver
    needs that form, and two implementations of one contract would drift (`T013-R1`).

    Checked at all rather than left to prose because every rule is a way for the system to hang
    or lie rather than raise:

    - an unattributed or mixed-job stream cannot be routed;
    - a missing outcome is indistinguishable from a crash (`REQ-028`);
    - a second outcome would drive a second state transition for one job;
    - an outcome the session kind cannot produce means the worker is not doing what was asked;
    - a missing or non-final sentinel leaves `ResultPump` blocked on `Queue.get()` forever.
    """
    validator = SessionValidator(kind)
    for item in messages:
        validator.accept(item)
    validator.complete()
