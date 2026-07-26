"""The IPC message contract (`T-011`).

A gap in this contract shows up as a **hang**, not an exception — the parent blocks on a queue
read that never ends, or attributes a message to the wrong job. So the tests here are about
completeness as much as correctness: every declared type is exercised, and the exercise list is
derived from `MESSAGE_TYPES` rather than written out, so adding a type without testing it fails.
"""

import pickle
from typing import Any

import pytest

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.models import FormatInfo, MediaInfo
from tracks_and_trails.downloader.protocol import (
    MESSAGE_TYPES,
    Failed,
    Probed,
    Progress,
    Stage,
    Succeeded,
    WorkerFinished,
    is_message,
    is_terminal,
    stage_of,
)

#: `REQ-014`'s list — "probing, downloading video, downloading audio, merging,
#: post-processing" — transcribed by hand as the identifiers this protocol uses for them.
#:
#: Independent of `Stage` on purpose: deriving it from the enum would make the test agree with
#: the code by construction, which is the `T010-R1` mistake. Written as exact values rather than
#: normalised prose, because normalising ("post-processing" -> "post processing") introduces a
#: string-munging step that can fail for reasons unrelated to the requirement.
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
    """An instance of every declared message type, keyed by type.

    Compared against `MESSAGE_TYPES` so a new type without a sample fails the completeness
    test rather than slipping through untested.
    """
    return {
        Probed: Probed(job_id="j", media=media()),
        Progress: Progress(job_id="j", stage=Stage.MERGING),
        Succeeded: Succeeded(job_id="j", output_path="/downloads/clip.mp4", total_bytes=10),
        Failed: Failed(job_id="j", kind=ErrorKind.NETWORK, message="timed out"),
        WorkerFinished: WorkerFinished(job_id="j", exit_code=0),
    }


# --- completeness ---------------------------------------------------------------------------


def test_every_declared_type_is_exercised() -> None:
    """`T-011`: an unexercised message type fails the suite.

    The contract's risk is omission — a type nobody sends in a test is a type whose pickling,
    validation and terminal classification are all unverified.
    """
    assert set(one_of_each()) == set(MESSAGE_TYPES)


# --- picklability: the ARC-002 precondition -------------------------------------------------


@pytest.mark.parametrize("message_type", MESSAGE_TYPES, ids=lambda t: t.__name__)
def test_every_message_round_trips_through_pickle(message_type: type) -> None:
    """These exist only to cross a process boundary; unpicklable is unusable."""
    original = one_of_each()[message_type]
    assert pickle.loads(pickle.dumps(original)) == original


def test_a_probed_message_carries_the_projection_not_a_raw_dict() -> None:
    """`ARCHITECTURE.md` §3: an `info_dict` never crosses the boundary.

    Asserted on the restored object, because that is what the parent actually gets.
    """
    restored_media = pickle.loads(pickle.dumps(Probed(job_id="j", media=media()))).media

    # Checked before the positive assertion narrows the type: afterwards mypy proves the dict
    # case impossible and the check becomes dead code rather than a runtime guard.
    assert not isinstance(restored_media, dict), "a raw info_dict crossed the boundary"
    assert isinstance(restored_media, MediaInfo)
    assert restored_media.formats[0].format_id == "137"


# --- job identity ---------------------------------------------------------------------------


@pytest.mark.parametrize("message_type", MESSAGE_TYPES, ids=lambda t: t.__name__)
def test_every_message_requires_a_job_id(message_type: type) -> None:
    """The result queue is shared, so an unattributable message cannot be routed or counted."""
    sample = one_of_each()[message_type]
    fields = {name: getattr(sample, name) for name in sample.__dataclass_fields__}
    fields["job_id"] = ""
    with pytest.raises(ValueError, match="job_id"):
        message_type(**fields)


@pytest.mark.parametrize("message_type", MESSAGE_TYPES, ids=lambda t: t.__name__)
def test_every_message_is_immutable(message_type: type) -> None:
    """A message is a value already sent.

    `multiprocessing.Queue` may serialize on its feeder thread after `put()` returns, so a
    mutable message could be altered between those moments and change what the parent receives.
    """
    with pytest.raises(AttributeError):
        one_of_each()[message_type].job_id = "other"


# --- terminal classification ----------------------------------------------------------------


def test_exactly_success_and_failure_are_terminal() -> None:
    """The receiver's terminal-once rule is written against this, not a hardcoded list."""
    terminal = {t for t in MESSAGE_TYPES if is_terminal(one_of_each()[t])}
    assert terminal == {Succeeded, Failed}


def test_the_sentinel_is_not_terminal() -> None:
    """`WorkerFinished` ends the *stream*, not the *job*.

    Conflating them would make a worker that crashed after reporting success indistinguishable
    from one that shut down cleanly.
    """
    assert not is_terminal(WorkerFinished(job_id="j"))
    assert is_message(WorkerFinished(job_id="j"))


def test_is_terminal_rejects_things_that_are_not_messages() -> None:
    candidates: tuple[object, ...] = ({}, None, "Succeeded", 0)
    for candidate in candidates:
        assert not is_terminal(candidate)


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
    """The bare dict is the case that matters.

    It is what a careless worker sends after a refactor, it pickles happily, and without this
    it would surface as an `AttributeError` on the GUI thread rather than at the boundary.
    """
    assert not is_message(candidate), f"{label} should not be accepted as a protocol message"


# --- progress -------------------------------------------------------------------------------


def test_progress_covers_every_stage_req_014_names() -> None:
    """Asserted against `REQ-014`'s own list, transcribed independently of `Stage`.

    Deriving the expectation from the enum would make this agree with the code by
    construction — the vacuity `T010-R1` recorded.
    """
    assert {stage.value for stage in Stage} == REQ_014_STAGES


@pytest.mark.parametrize("stage", list(Stage), ids=lambda s: s.value)
def test_a_progress_message_can_carry_each_stage(stage: Stage) -> None:
    assert Progress(job_id="j", stage=stage).stage is stage


def test_progress_quantities_are_optional() -> None:
    """yt-dlp omits them: a live stream has no total, and speed and ETA start absent."""
    progress = Progress(job_id="j", stage=Stage.DOWNLOADING_VIDEO)
    assert progress.total_bytes is None
    assert progress.speed_bytes_per_second is None
    assert progress.eta_seconds is None
    assert progress.fraction is None


def test_progress_fraction_is_none_when_the_total_is_unknown() -> None:
    """Matching `Job.progress`: a confident zero would misreport a live stream."""
    assert Progress(job_id="j", downloaded_bytes=500).fraction is None


def test_progress_fraction_is_computed_and_capped() -> None:
    """yt-dlp's reported total is an estimate the download can overshoot."""
    assert Progress(job_id="j", downloaded_bytes=512, total_bytes=1024).fraction == 0.5
    assert Progress(job_id="j", downloaded_bytes=2048, total_bytes=1024).fraction == 1.0


@pytest.mark.parametrize("field_name", ["downloaded_bytes", "total_bytes"])
def test_negative_byte_counts_are_rejected(field_name: str) -> None:
    with pytest.raises(ValueError, match="negative"):
        Progress(job_id="j", **{field_name: -1})  # type: ignore[arg-type]


def test_stage_of_returns_the_stage_only_for_progress() -> None:
    assert stage_of(Progress(job_id="j", stage=Stage.MERGING)) is Stage.MERGING
    assert stage_of(WorkerFinished(job_id="j")) is None
    assert stage_of({}) is None


# --- terminal payloads ----------------------------------------------------------------------


def test_a_success_must_say_what_it_wrote() -> None:
    """A success that cannot name its file is indistinguishable from a failure to the user."""
    with pytest.raises(ValueError, match="output path"):
        Succeeded(job_id="j", output_path="")


def test_a_failure_requires_both_a_classification_and_the_verbatim_message() -> None:
    """`NFR-006` and `REQ-018`: neither half is optional."""
    with pytest.raises(ValueError, match="ErrorKind"):
        Failed(job_id="j", message="something broke")
    with pytest.raises(ValueError, match="verbatim"):
        Failed(job_id="j", kind=ErrorKind.NETWORK, message="")


def test_a_failure_preserves_the_extractor_message_exactly() -> None:
    """Whitespace and newlines included — tidying an extractor message is altering it."""
    text = "ERROR: [youtube] abc: Video unavailable\n  This video is private.  "
    assert Failed(job_id="j", kind=ErrorKind.EXTRACTOR_ERROR, message=text).message == text


def test_a_probe_result_requires_its_media() -> None:
    with pytest.raises(ValueError, match="MediaInfo"):
        Probed(job_id="j")


def test_failure_context_is_an_immutable_tuple() -> None:
    """Same reasoning as `FailureDetail.context` (`T010-R2`): a dict here would be mutable
    after `put()` and before the feeder thread serialized it."""
    failed = Failed(
        job_id="j",
        kind=ErrorKind.FFMPEG_ERROR,
        message="ffmpeg exited 1",
        context=(("exit_code", "1"),),
    )
    assert isinstance(failed.context, tuple)
    with pytest.raises(TypeError):
        failed.context[0] = ("exit_code", "0")  # type: ignore[index]
