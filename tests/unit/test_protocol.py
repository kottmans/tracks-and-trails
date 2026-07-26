"""The IPC message contract (`T-011`).

A gap here shows up as a **hang**, not an exception — the parent blocks on a queue read that
never ends, or attributes a message to the wrong job. So these tests are about completeness as
much as correctness, and about **rejection** as much as acceptance.

The first round of this file tested only the happy paths. `T011-R2` showed what that missed:
replacing the representative `Probed.media` with a raw dict and omitting `Progress.stage` left
all 48 tests passing. Every constructor now has negative tests, and the samples themselves are
asserted to be valid rather than assumed.
"""

import pickle
import typing
from typing import Any

import pytest

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.models import FormatInfo, MediaInfo
from tracks_and_trails.downloader.protocol import (
    MESSAGE_TYPES,
    OUTCOME_TYPES,
    Failed,
    Probed,
    Progress,
    ProtocolViolationError,
    ResolutionReport,
    SessionKind,
    Stage,
    Succeeded,
    WorkerFinished,
    is_message,
    is_outcome,
    legal_outcomes,
    stage_of,
    validate_sequence,
)

#: `REQ-014`'s list — "probing, downloading video, downloading audio, merging,
#: post-processing" — transcribed by hand as the identifiers this protocol uses.
#:
#: Independent of `Stage` on purpose: deriving it from the enum would make the test agree with
#: the code by construction, which is the `T010-R1` mistake.
REQ_014_STAGES = {
    "probing",
    "downloading_video",
    "downloading_audio",
    "merging",
    "post_processing",
}


def media() -> MediaInfo:
    return MediaInfo(
        url="https://example.com/watch?v=abc",
        title="Example",
        formats=(FormatInfo(format_id="137", extension="mp4", height=1080),),
    )


def one_of_each() -> dict[type, Any]:
    """An instance of every declared message type, keyed by type."""
    return {
        Probed: Probed(job_id="j", media=media()),
        Progress: Progress(job_id="j", stage=Stage.MERGING),
        Succeeded: Succeeded(job_id="j", output_path="/downloads/clip.mp4", total_bytes=10),
        Failed: Failed(job_id="j", kind=ErrorKind.NETWORK, message="timed out"),
        ResolutionReport: ResolutionReport(
            job_id="j",
            ytdlp_version="2026.07.04",
            ytdlp_source="bundled baseline",
            rejected=("user-managed copy: ImportError: deliberately broken",),
        ),
        WorkerFinished: WorkerFinished(job_id="j", exit_code=0),
    }


# --- completeness ---------------------------------------------------------------------------


def test_every_declared_type_is_exercised() -> None:
    """An unexercised message type is one whose validation is entirely unverified."""
    assert set(one_of_each()) == set(MESSAGE_TYPES)


def test_the_samples_are_valid_contract_instances() -> None:
    """`T011-R2`: the samples are the fixture everything else parametrises over.

    A degenerate sample — a raw dict where a projection belongs — would leave every test below
    passing while proving nothing, which is exactly what the reviewer's mutation demonstrated.
    Payload types are therefore asserted, not assumed.
    """
    samples = one_of_each()
    assert isinstance(samples[Probed].media, MediaInfo)
    assert isinstance(samples[Progress].stage, Stage)
    assert isinstance(samples[Failed].kind, ErrorKind)
    assert samples[ResolutionReport].ytdlp_version
    assert samples[ResolutionReport].ytdlp_source
    assert samples[Succeeded].output_path
    assert samples[Failed].message
    for message in samples.values():
        assert is_message(message)


# --- picklability: the ARC-002 precondition -------------------------------------------------


@pytest.mark.parametrize("message_type", MESSAGE_TYPES, ids=lambda t: t.__name__)
def test_every_message_round_trips_through_pickle(message_type: type) -> None:
    original = one_of_each()[message_type]
    assert pickle.loads(pickle.dumps(original)) == original


def test_a_probed_message_carries_the_projection_not_a_raw_dict() -> None:
    """`ARCHITECTURE.md` §3: an `info_dict` never crosses the boundary."""
    restored = pickle.loads(pickle.dumps(Probed(job_id="j", media=media()))).media
    assert not isinstance(restored, dict), "a raw info_dict crossed the boundary"
    assert isinstance(restored, MediaInfo)
    assert restored.formats[0].format_id == "137"


# --- rejection: payload types (T011-R2) -----------------------------------------------------


@pytest.mark.parametrize(
    ("label", "payload"),
    [
        ("raw info_dict", {"title": "Example", "formats": []}),
        ("empty dict", {}),
        ("none", None),
        ("string", "Example"),
        ("format info", FormatInfo(format_id="137", extension="mp4")),
    ],
)
def test_probed_rejects_anything_that_is_not_a_projection(label: str, payload: object) -> None:
    """The finding that mattered most: a wrapped raw dict previously constructed, validated and
    pickled happily, defeating `ARC-002`'s projection rule at the one place it is checked."""
    with pytest.raises((TypeError, ValueError)):
        Probed(job_id="j", media=payload)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_stage", ["probing", "merging", 0, None, Stage])
def test_progress_rejects_a_stage_that_is_not_a_stage_member(bad_stage: object) -> None:
    """A string stage passed before. `"probing"` compares equal to `Stage.PROBING` under
    `StrEnum`, so the receiver would mostly work — until something did an identity check."""
    with pytest.raises(TypeError):
        Progress(job_id="j", stage=bad_stage)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_kind", ["network", 0, None, ErrorKind])
def test_failed_rejects_a_kind_that_is_not_an_error_kind(bad_kind: object) -> None:
    """Retry policy is decided from this (`REQ-018`); a string that merely compares equal is
    not a classification."""
    with pytest.raises(TypeError):
        Failed(job_id="j", kind=bad_kind, message="boom")  # type: ignore[arg-type]


@pytest.mark.parametrize("field_name", ["downloaded_bytes", "total_bytes", "eta_seconds"])
def test_progress_rejects_non_integer_quantities(field_name: str) -> None:
    for bad in ("100", 1.5, True):
        with pytest.raises(TypeError):
            Progress(job_id="j", stage=Stage.MERGING, **{field_name: bad})  # type: ignore[arg-type]


@pytest.mark.parametrize("field_name", ["downloaded_bytes", "total_bytes", "eta_seconds"])
def test_progress_rejects_negative_quantities(field_name: str) -> None:
    with pytest.raises(ValueError, match="negative"):
        Progress(job_id="j", stage=Stage.MERGING, **{field_name: -1})


#: Fields that legitimately accept a mapping and normalise it to an immutable form.
#: Everything else must reject one outright.
NORMALISING_FIELDS = {(Failed, "context")}


@pytest.mark.parametrize("message_type", MESSAGE_TYPES, ids=lambda t: t.__name__)
def test_no_field_accepts_and_stores_a_mutable_mapping(message_type: type) -> None:
    """`T011-R2`, second round — the **systematic** version of that finding.

    The first correction validated the fields the review happened to name and left
    `Progress.speed_bytes_per_second` and `Succeeded.total_bytes` accepting a mutable dict:
    they pickled, passed `is_message()`, and stayed mutable after construction. Substituting
    those two left all 100 protocol tests green.

    Listing the newly-found fields would repeat the mistake at a smaller scale. This walks
    **every field of every message type**, so a field added later without validation fails here
    without anyone remembering to extend a list.

    The hazard is the `T010-R2` one: `multiprocessing.Queue` may serialize on its feeder thread
    after `put()` returns, so anything mutable reachable from a message can change what the
    parent receives.
    """
    sample = one_of_each()[message_type]
    valid = {name: getattr(sample, name) for name in sample.__dataclass_fields__}

    for name in sample.__dataclass_fields__:
        kwargs = dict(valid)
        kwargs[name] = {"mutable": "dict"}

        if (message_type, name) in NORMALISING_FIELDS:
            stored = getattr(message_type(**kwargs), name)
            assert not isinstance(stored, dict), f"{message_type.__name__}.{name} stored a dict"
            continue

        with pytest.raises((TypeError, ValueError)):
            message_type(**kwargs)


def test_progress_rejects_a_non_numeric_speed() -> None:
    """One of the two fields the first correction missed (`T011-R2`)."""
    bad_speeds: tuple[object, ...] = ({}, "fast", [1])
    for bad in bad_speeds:
        with pytest.raises(TypeError):
            Progress(job_id="j", stage=Stage.MERGING, speed_bytes_per_second=bad)  # type: ignore[arg-type]


def test_progress_accepts_a_fractional_speed_but_not_a_negative_one() -> None:
    """A transfer rate is legitimately fractional, unlike a byte count."""
    assert Progress(job_id="j", stage=Stage.MERGING, speed_bytes_per_second=1.5).fraction is None
    with pytest.raises(ValueError, match="negative"):
        Progress(job_id="j", stage=Stage.MERGING, speed_bytes_per_second=-1.0)


def test_succeeded_rejects_a_non_integer_total() -> None:
    """The other field the first correction missed (`T011-R2`)."""
    bad_totals: tuple[object, ...] = ({}, "10", 1.5, True)
    for bad in bad_totals:
        with pytest.raises(TypeError):
            Succeeded(job_id="j", output_path="/a.mp4", total_bytes=bad)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="negative"):
        Succeeded(job_id="j", output_path="/a.mp4", total_bytes=-1)


# --- annotation-driven scalar guards (T-043, from T041-R6 via T-042) ------------------------


def field_names(message_type: type) -> list[str]:
    """Declared field names. Centralises the one `__dataclass_fields__` access mypy dislikes."""
    return list(message_type.__dataclass_fields__)  # type: ignore[attr-defined]


def annotated_types(message_type: type, name: str) -> set[type]:
    """The concrete types in a field's annotation, unwrapping unions."""
    hint = typing.get_type_hints(message_type)[name]
    args = typing.get_args(hint) or (hint,)
    return {arg for arg in args if isinstance(arg, type)}


def numeric_fields(message_type: type) -> set[str]:
    """Fields annotated as a number but **not** as a bool."""
    result = set()
    for name in field_names(message_type):
        types_ = annotated_types(message_type, name)
        if (int in types_ or float in types_) and bool not in types_:
            result.add(name)
    return result


def optional_fields(message_type: type) -> set[str]:
    return {
        name
        for name in field_names(message_type)
        if type(None) in annotated_types(message_type, name)
    }


def kwargs_for(message_type: type) -> dict[str, Any]:
    sample = one_of_each()[message_type]
    return {name: getattr(sample, name) for name in field_names(message_type)}


@pytest.mark.parametrize("message_type", MESSAGE_TYPES, ids=lambda t: t.__name__)
def test_numeric_fields_reject_booleans(message_type: type) -> None:
    """`T-043`. `bool` is an `int` subclass, so `True` becomes a rate of 1 B/s or exit code 1.

    Found by `T-042`'s out-of-scope check on the sibling sweep in `core/models.py`. The count
    validators' guards were already covered here, but `Progress.speed_bytes_per_second` and
    `WorkerFinished.exit_code` were not: deleting either left all 113 protocol tests green.

    Annotation-driven rather than two more names in a parametrize list, so a numeric field added
    later is covered without anyone editing anything — the `T041-R2` lesson.
    """
    fields = numeric_fields(message_type)
    if not fields:
        pytest.skip(f"{message_type.__name__} declares no numeric fields")

    for name in fields:
        kwargs = kwargs_for(message_type)
        kwargs[name] = True
        with pytest.raises(TypeError):
            message_type(**kwargs)


@pytest.mark.parametrize("message_type", MESSAGE_TYPES, ids=lambda t: t.__name__)
def test_fields_that_cannot_be_none_reject_none(message_type: type) -> None:
    """A regression guard, slightly beyond `T-043` as written — deliberately.

    The task scoped nullability out because the reviewer verified it sound, and it is. But
    "correct and untested" is exactly the condition `T-042` existed to fix, and the helpers
    above make this one extra test rather than a separate effort. Widening by a single test
    with the reason recorded beats filing a third task for it.
    """
    optional = optional_fields(message_type)
    required = [n for n in field_names(message_type) if n not in optional]
    assert required, f"{message_type.__name__} has no required fields; this would be vacuous"

    for name in required:
        kwargs = kwargs_for(message_type)
        kwargs[name] = None
        with pytest.raises((TypeError, ValueError)):
            message_type(**kwargs)


# --- rejection: failure context immutability (T011-R2 / T010-R2) ----------------------------


def test_failed_context_is_normalised_to_an_immutable_tuple() -> None:
    """A dict here previously stayed mutable after construction, reproducing exactly the
    feeder-thread race `T010-R2` fixed in `FailureDetail`."""
    failed = Failed(
        job_id="j",
        kind=ErrorKind.FFMPEG_ERROR,
        message="ffmpeg exited 1",
        context={"exit_code": "1", "codec": "aac"},  # type: ignore[arg-type]
    )
    assert failed.context == (("codec", "aac"), ("exit_code", "1"))
    with pytest.raises(TypeError):
        failed.context[0] = ("exit_code", "0")  # type: ignore[index]


def test_failed_context_rejects_malformed_entries() -> None:
    with pytest.raises(ValueError, match="pairs"):
        Failed(job_id="j", kind=ErrorKind.DISK, message="m", context=(("a", 1),))  # type: ignore[arg-type]


def test_failed_context_order_does_not_affect_equality() -> None:
    first = Failed(job_id="j", kind=ErrorKind.DISK, message="m", context=(("a", "1"), ("b", "2")))
    second = Failed(job_id="j", kind=ErrorKind.DISK, message="m", context=(("b", "2"), ("a", "1")))
    assert first == second


def test_a_restored_failure_context_is_still_immutable() -> None:
    """Unpickling must not produce a mutable twin of an immutable record."""
    restored = pickle.loads(
        pickle.dumps(Failed(job_id="j", kind=ErrorKind.DISK, message="m", context=(("k", "v"),)))
    )
    with pytest.raises(TypeError):
        restored.context[0] = ("k", "other")


# --- job identity and immutability ----------------------------------------------------------


@pytest.mark.parametrize("message_type", MESSAGE_TYPES, ids=lambda t: t.__name__)
def test_every_message_requires_a_job_id(message_type: type) -> None:
    sample = one_of_each()[message_type]
    fields = {name: getattr(sample, name) for name in sample.__dataclass_fields__}
    fields["job_id"] = ""
    with pytest.raises(ValueError, match="job_id"):
        message_type(**fields)


@pytest.mark.parametrize("message_type", MESSAGE_TYPES, ids=lambda t: t.__name__)
def test_every_message_rejects_a_non_string_job_id(message_type: type) -> None:
    sample = one_of_each()[message_type]
    fields = {name: getattr(sample, name) for name in sample.__dataclass_fields__}
    fields["job_id"] = 7
    with pytest.raises(ValueError, match="job_id"):
        message_type(**fields)


@pytest.mark.parametrize("message_type", MESSAGE_TYPES, ids=lambda t: t.__name__)
def test_every_message_is_immutable(message_type: type) -> None:
    with pytest.raises(AttributeError):
        one_of_each()[message_type].job_id = "other"


@pytest.mark.parametrize("message_type", MESSAGE_TYPES, ids=lambda t: t.__name__)
def test_every_message_is_keyword_only(message_type: type) -> None:
    """`T011-R3`: positional construction cannot silently shift meaning when a field is added."""
    with pytest.raises(TypeError):
        message_type("j")


# --- the validator --------------------------------------------------------------------------


@pytest.mark.parametrize("message_type", MESSAGE_TYPES, ids=lambda t: t.__name__)
def test_every_declared_type_is_accepted_by_the_validator(message_type: type) -> None:
    assert is_message(one_of_each()[message_type])


@pytest.mark.parametrize(
    ("label", "candidate"),
    [
        ("bare dict", {"job_id": "j", "stage": "merging"}),
        ("none", None),
        ("string", "Progress"),
        ("tuple", ("j", "merging")),
        ("media info", MediaInfo(url="https://e.com/x", title="T")),
        ("error kind", ErrorKind.NETWORK),
    ],
)
def test_the_validator_rejects_anything_undeclared(label: str, candidate: object) -> None:
    assert not is_message(candidate), f"{label} should not be accepted"


def test_the_validator_rejects_an_undeclared_subclass() -> None:
    """`T011-R2`: "declared" is the invariant, and a subclass is not declared.

    It can add fields, override validation, and carry anything at all across the boundary while
    satisfying an `isinstance` check — which is what the previous implementation used.
    """

    class Sneaky(Progress):
        pass

    sneaky = Sneaky(job_id="j", stage=Stage.MERGING)
    assert isinstance(sneaky, Progress), "the premise: it would pass an isinstance check"
    assert not is_message(sneaky)
    assert not is_outcome(sneaky)


# --- outcomes and sessions (T011-R1) --------------------------------------------------------


def test_exactly_the_three_outcome_types_are_outcomes() -> None:
    """`Probed` is an outcome — a successful probe otherwise reports nothing at all.

    `ResolutionReport` deliberately is **not** one: it says which yt-dlp is running, not what
    the job achieved. Counting it would break the "exactly one outcome" rule on every session
    that reports its resolution, which is every session that gets that far (`T012-R1`).
    """
    outcomes = {t for t in MESSAGE_TYPES if is_outcome(one_of_each()[t])}
    assert outcomes == {Probed, Succeeded, Failed} == set(OUTCOME_TYPES)
    assert not is_outcome(one_of_each()[ResolutionReport])


def test_the_sentinel_is_not_an_outcome() -> None:
    """It ends the *stream*, not the *job*. Conflating them would make a worker that crashed
    after reporting success indistinguishable from a clean shutdown."""
    assert not is_outcome(WorkerFinished(job_id="j"))
    assert is_message(WorkerFinished(job_id="j"))


def test_progress_is_never_an_outcome() -> None:
    assert not is_outcome(Progress(job_id="j", stage=Stage.MERGING))


def test_each_session_kind_declares_its_legal_outcomes() -> None:
    """A probe cannot succeed at downloading, and a download does not end at `Probed`."""
    assert legal_outcomes(SessionKind.PROBE) == (Probed, Failed)
    assert legal_outcomes(SessionKind.DOWNLOAD) == (Succeeded, Failed)


def test_every_session_kind_can_fail() -> None:
    for kind in SessionKind:
        assert Failed in legal_outcomes(kind)


# --- sequence validation --------------------------------------------------------------------


def probe_success() -> list[object]:
    return [
        Progress(job_id="j", stage=Stage.PROBING),
        Probed(job_id="j", media=media()),
        WorkerFinished(job_id="j"),
    ]


def download_success() -> list[object]:
    return [
        Progress(job_id="j", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=1, total_bytes=2),
        Progress(job_id="j", stage=Stage.MERGING),
        Succeeded(job_id="j", output_path="/downloads/clip.mp4"),
        WorkerFinished(job_id="j"),
    ]


@pytest.mark.parametrize(
    ("kind", "sequence"),
    [
        (SessionKind.PROBE, probe_success()),
        (SessionKind.DOWNLOAD, download_success()),
        (
            SessionKind.PROBE,
            [
                Failed(job_id="j", kind=ErrorKind.UNSUPPORTED_URL, message="no extractor"),
                WorkerFinished(job_id="j", exit_code=1),
            ],
        ),
        (
            SessionKind.DOWNLOAD,
            [
                Failed(job_id="j", kind=ErrorKind.NETWORK, message="timed out"),
                WorkerFinished(job_id="j", exit_code=1),
            ],
        ),
    ],
    ids=["probe-success", "download-success", "probe-failure", "download-failure"],
)
def test_the_four_legal_sessions_validate(kind: SessionKind, sequence: list[object]) -> None:
    """The whole point of `T011-R1`: a successful probe is a *complete* session.

    Under the previous contract this sequence contained zero outcomes, so a receiver applying
    `REQ-028`'s "exited 0 with no outcome means the worker crashed" would have failed every
    successful probe.
    """
    validate_sequence(kind, sequence)


def test_a_successful_probe_has_exactly_one_outcome() -> None:
    assert sum(1 for m in probe_success() if is_outcome(m)) == 1


@pytest.mark.parametrize(
    ("label", "kind", "sequence"),
    [
        ("empty", SessionKind.PROBE, []),
        (
            "no outcome",
            SessionKind.DOWNLOAD,
            [Progress(job_id="j", stage=Stage.MERGING), WorkerFinished(job_id="j")],
        ),
        (
            "two outcomes",
            SessionKind.DOWNLOAD,
            [
                Succeeded(job_id="j", output_path="/a.mp4"),
                Succeeded(job_id="j", output_path="/b.mp4"),
                WorkerFinished(job_id="j"),
            ],
        ),
        (
            "outcome illegal for the session kind",
            SessionKind.PROBE,
            [Succeeded(job_id="j", output_path="/a.mp4"), WorkerFinished(job_id="j")],
        ),
        (
            "probe outcome in a download session",
            SessionKind.DOWNLOAD,
            [Probed(job_id="j", media=media()), WorkerFinished(job_id="j")],
        ),
        ("no sentinel", SessionKind.DOWNLOAD, [Succeeded(job_id="j", output_path="/a.mp4")]),
        (
            "two sentinels",
            SessionKind.DOWNLOAD,
            [
                Succeeded(job_id="j", output_path="/a.mp4"),
                WorkerFinished(job_id="j"),
                WorkerFinished(job_id="j"),
            ],
        ),
        (
            "sentinel not last",
            SessionKind.DOWNLOAD,
            [WorkerFinished(job_id="j"), Succeeded(job_id="j", output_path="/a.mp4")],
        ),
        (
            "progress after the outcome",
            SessionKind.DOWNLOAD,
            [
                Succeeded(job_id="j", output_path="/a.mp4"),
                Progress(job_id="j", stage=Stage.MERGING),
                WorkerFinished(job_id="j"),
            ],
        ),
        (
            "mixed job ids",
            SessionKind.DOWNLOAD,
            [Succeeded(job_id="j", output_path="/a.mp4"), WorkerFinished(job_id="other")],
        ),
        (
            "undeclared object on the queue",
            SessionKind.DOWNLOAD,
            [{"job_id": "j"}, WorkerFinished(job_id="j")],
        ),
    ],
)
def test_illegal_sequences_are_rejected(
    label: str, kind: SessionKind, sequence: list[object]
) -> None:
    """Each of these is a way for the system to hang or lie rather than raise."""
    with pytest.raises(ProtocolViolationError):
        validate_sequence(kind, sequence)


@pytest.mark.parametrize(
    "stage",
    [Stage.DOWNLOADING_VIDEO, Stage.DOWNLOADING_AUDIO, Stage.MERGING, Stage.POST_PROCESSING],
    ids=lambda s: s.value,
)
def test_a_probe_session_may_only_report_the_probing_stage(stage: Stage) -> None:
    """`T011-R7`: the declared grammar is `Progress(PROBING)*`, and now so is the check.

    A probe extracts metadata. It cannot download, merge or post-process, so any other stage
    misreports `REQ-014` state rather than describing an unusual pipeline.
    """
    sequence = [
        Progress(job_id="j", stage=stage),
        Probed(job_id="j", media=media()),
        WorkerFinished(job_id="j"),
    ]
    with pytest.raises(ProtocolViolationError, match="probe session"):
        validate_sequence(SessionKind.PROBE, sequence)


def test_a_download_session_may_report_any_stage() -> None:
    """Deliberately *not* generalised (`T011-R7`).

    Real yt-dlp pipelines skip and repeat stages — a format needing no merge never reports
    `MERGING` — so download-stage ordering belongs to the adapter (`T-012`) and the end-to-end
    gate (`T-037`), not to this contract. Asserted so the narrowness is intentional rather than
    an omission.
    """
    validate_sequence(
        SessionKind.DOWNLOAD,
        [
            Progress(job_id="j", stage=Stage.MERGING),
            Progress(job_id="j", stage=Stage.DOWNLOADING_AUDIO),
            Progress(job_id="j", stage=Stage.PROBING),
            Succeeded(job_id="j", output_path="/a.mp4"),
            WorkerFinished(job_id="j"),
        ],
    )


def test_the_violation_message_names_what_was_wrong() -> None:
    """A bare exception would waste the raise; `T-013` surfaces this to a log."""
    with pytest.raises(ProtocolViolationError, match="no outcome"):
        validate_sequence(SessionKind.DOWNLOAD, [WorkerFinished(job_id="j")])


# --- progress -------------------------------------------------------------------------------


def test_progress_covers_every_stage_req_014_names() -> None:
    """Asserted against `REQ-014`'s own list, transcribed independently of `Stage`."""
    assert {stage.value for stage in Stage} == REQ_014_STAGES


@pytest.mark.parametrize("stage", list(Stage), ids=lambda s: s.value)
def test_a_progress_message_can_carry_each_stage(stage: Stage) -> None:
    assert Progress(job_id="j", stage=stage).stage is stage


def test_progress_quantities_are_optional() -> None:
    progress = Progress(job_id="j", stage=Stage.DOWNLOADING_VIDEO)
    assert progress.total_bytes is None
    assert progress.speed_bytes_per_second is None
    assert progress.eta_seconds is None
    assert progress.fraction is None


def test_progress_fraction_is_none_when_the_total_is_unknown() -> None:
    progress = Progress(job_id="j", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=500)
    assert progress.fraction is None


def test_progress_fraction_is_computed_and_capped() -> None:
    """yt-dlp's reported total is an estimate the download can overshoot."""
    half = Progress(
        job_id="j", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=512, total_bytes=1024
    )
    over = Progress(
        job_id="j", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=2048, total_bytes=1024
    )
    assert half.fraction == 0.5
    assert over.fraction == 1.0


def test_stage_of_returns_the_stage_only_for_progress() -> None:
    assert stage_of(Progress(job_id="j", stage=Stage.MERGING)) is Stage.MERGING
    assert stage_of(WorkerFinished(job_id="j")) is None
    assert stage_of({}) is None


# --- outcome payloads -----------------------------------------------------------------------


def test_a_success_must_say_what_it_wrote() -> None:
    with pytest.raises(ValueError, match="output path"):
        Succeeded(job_id="j", output_path="")


def test_a_failure_requires_both_a_classification_and_the_verbatim_message() -> None:
    """`NFR-006` and `REQ-018`: neither half is optional."""
    with pytest.raises(TypeError):
        Failed(job_id="j", message="something broke")  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="verbatim"):
        Failed(job_id="j", kind=ErrorKind.NETWORK, message="")


def test_a_failure_preserves_the_extractor_message_exactly() -> None:
    """Whitespace and newlines included — tidying an extractor message is altering it."""
    text = "ERROR: [youtube] abc: Video unavailable\n  This video is private.  "
    assert Failed(job_id="j", kind=ErrorKind.EXTRACTOR_ERROR, message=text).message == text


def test_a_probe_result_requires_its_media() -> None:
    with pytest.raises(TypeError):
        Probed(job_id="j")  # type: ignore[call-arg]
