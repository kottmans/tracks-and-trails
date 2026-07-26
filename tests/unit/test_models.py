"""Domain models (`T-010`).

Two things are asserted here, and the second is the one that matters. Picklability alone would
be satisfied by empty dataclasses — the vacuous pass `T-010` explicitly warns against — so
every model's required fields and invariants are pinned as well.
"""

import pickle
from datetime import UTC, datetime

import pytest

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import IllegalTransitionError, JobStatus
from tracks_and_trails.core.models import (
    DownloadRequest,
    FormatInfo,
    Job,
    MediaInfo,
    MediaKind,
    Preset,
)


@pytest.fixture
def request_() -> DownloadRequest:
    return DownloadRequest(
        url="https://example.com/watch?v=abc",
        output_directory="/home/user/Downloads",
        format_selector="bestvideo+bestaudio/best",
        output_template="%(title)s.%(ext)s",
    )


@pytest.fixture
def job(request_: DownloadRequest) -> Job:
    return Job(id="job-1", url=request_.url, request=request_)


# --- picklability: the ARC-002 precondition ------------------------------------------------


def test_every_model_round_trips_through_pickle(job: Job, request_: DownloadRequest) -> None:
    """`ARC-002`: all of these cross a process boundary to the spawned worker.

    Asserted per type so the failure names the offending model rather than reporting that
    "something" in the graph is unpicklable.
    """
    media = MediaInfo(
        url="https://example.com/watch?v=abc",
        title="Example",
        formats=(FormatInfo(format_id="137", extension="mp4", height=1080),),
    )
    preset = Preset(
        name="Best video",
        media_kind=MediaKind.VIDEO,
        format_selector="bestvideo+bestaudio/best",
        output_template="%(title)s.%(ext)s",
    )

    for model in (request_, job, media, media.formats[0], preset, MediaKind.VIDEO):
        assert pickle.loads(pickle.dumps(model)) == model, f"{type(model).__name__} did not survive"


def test_a_job_carrying_a_failure_survives_the_process_boundary(job: Job) -> None:
    """The path that actually matters: a worker reports a failure back to the GUI."""
    failed = job.with_status(JobStatus.PROBING).with_failure(ErrorKind.NETWORK, "timed out")
    assert pickle.loads(pickle.dumps(failed)) == failed


# --- required fields and invariants: not merely picklable ----------------------------------


@pytest.mark.parametrize(
    ("field_name", "value"),
    [("id", ""), ("url", "")],
)
def test_a_job_without_its_required_fields_fails_construction(
    request_: DownloadRequest, field_name: str, value: str
) -> None:
    """An empty id or url is a job that cannot be found or downloaded."""
    kwargs = {"id": "job-1", "url": "https://example.com/x", "request": request_}
    kwargs[field_name] = value
    with pytest.raises(ValueError):
        Job(**kwargs)  # type: ignore[arg-type]


def test_a_job_defaults_to_queued(job: Job) -> None:
    assert job.status is JobStatus.QUEUED
    assert job.attempts == 0
    assert job.bytes_done == 0


def test_negative_counters_are_rejected(request_: DownloadRequest) -> None:
    """Byte counts and attempt counts below zero are corruption, not an edge case.

    Written as three explicit constructions rather than a parametrized `**kwargs` unpack: the
    unpack defeats type checking of the call, which is most of what pins these signatures.
    """
    base = {"id": "j", "url": "https://example.com/x", "request": request_}
    with pytest.raises(ValueError, match="bytes_done"):
        Job(**base, bytes_done=-1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="bytes_total"):
        Job(**base, bytes_total=-1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="attempts"):
        Job(**base, attempts=-1)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "missing",
    ["url", "output_directory", "format_selector", "output_template"],
)
def test_a_download_request_requires_every_field_that_defines_the_download(missing: str) -> None:
    """Each of these silently changes what gets downloaded if left empty.

    An empty format selector is the subtle one: it means yt-dlp's default, which is not the
    preset the user picked.
    """
    kwargs = {
        "url": "https://example.com/x",
        "output_directory": "/downloads",
        "format_selector": "best",
        "output_template": "%(title)s.%(ext)s",
    }
    kwargs[missing] = ""
    with pytest.raises(ValueError):
        DownloadRequest(**kwargs)  # type: ignore[arg-type]


def test_media_info_declares_the_fields_the_architecture_names() -> None:
    """`ARCHITECTURE.md` §5: declared fields only, not a passthrough of yt-dlp's dict."""
    media = MediaInfo(url="https://example.com/x", title="T")
    for name in ("url", "title", "formats", "duration_seconds", "uploader", "thumbnail_url"):
        assert hasattr(media, name), f"MediaInfo is missing {name}"


def test_format_info_declares_the_fields_the_architecture_names() -> None:
    fmt = FormatInfo(format_id="137", extension="mp4")
    for name in ("format_id", "extension", "height", "width", "filesize", "video_codec"):
        assert hasattr(fmt, name), f"FormatInfo is missing {name}"


@pytest.mark.parametrize(
    ("factory", "match"),
    [
        (lambda: MediaInfo(url="", title="T"), "url"),
        (lambda: MediaInfo(url="https://example.com/x", title=""), "title"),
        (lambda: FormatInfo(format_id="", extension="mp4"), "format_id"),
        (
            lambda: Preset(
                name="",
                media_kind=MediaKind.VIDEO,
                format_selector="best",
                output_template="%(title)s.%(ext)s",
            ),
            "name",
        ),
    ],
)
def test_models_reject_empty_required_fields(factory: object, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        factory()  # type: ignore[operator]


def test_optional_probe_fields_stay_optional() -> None:
    """yt-dlp genuinely omits these; requiring them would mean inventing values."""
    fmt = FormatInfo(format_id="251", extension="webm", audio_codec="opus")
    assert fmt.height is None
    assert fmt.filesize is None
    assert fmt.is_audio_only


# --- immutability: the settings-freeze guarantee --------------------------------------------


def test_a_download_request_cannot_be_mutated(request_: DownloadRequest) -> None:
    """`ARCHITECTURE.md` §8: frozen at job-creation time.

    This is what stops a settings change from altering a job already in flight, and what makes
    a retry reproduce the original request rather than today's defaults.
    """
    with pytest.raises(AttributeError):
        request_.format_selector = "worst"  # type: ignore[misc]


def test_every_model_is_frozen(job: Job) -> None:
    """Asserted across the set: one mutable model is enough to lose the guarantee."""
    media = MediaInfo(url="https://example.com/x", title="T")
    preset = Preset(
        name="p",
        media_kind=MediaKind.AUDIO,
        format_selector="bestaudio",
        output_template="%(title)s.%(ext)s",
    )
    for model, attribute in ((job, "status"), (media, "title"), (preset, "name")):
        with pytest.raises(AttributeError):
            setattr(model, attribute, "changed")


def test_collection_fields_are_tuples_not_lists(request_: DownloadRequest) -> None:
    """A frozen dataclass with a mutable field is only shallowly frozen."""
    assert isinstance(request_.post_processors, tuple)
    assert isinstance(request_.subtitle_languages, tuple)
    assert isinstance(MediaInfo(url="https://e.com/x", title="T").formats, tuple)


# --- status changes go through the state machine --------------------------------------------


def test_with_status_applies_a_legal_transition(job: Job) -> None:
    assert job.with_status(JobStatus.PROBING).status is JobStatus.PROBING


def test_with_status_refuses_an_illegal_transition(job: Job) -> None:
    """There is no route to a new status that skips validation."""
    with pytest.raises(IllegalTransitionError):
        job.with_status(JobStatus.COMPLETED)


def test_with_status_returns_a_copy_and_leaves_the_original_alone(job: Job) -> None:
    moved = job.with_status(JobStatus.PROBING)
    assert job.status is JobStatus.QUEUED
    assert moved is not job


def test_with_failure_records_the_kind_and_the_verbatim_message(job: Job) -> None:
    """`NFR-006`: the extractor's own words reach the stored job unchanged."""
    message = "ERROR: [youtube] abc: Private video. Sign in if you've been granted access"
    failed = job.with_status(JobStatus.PROBING).with_failure(ErrorKind.AUTH_REQUIRED, message)

    assert failed.status is JobStatus.FAILED
    assert failed.error_kind is ErrorKind.AUTH_REQUIRED
    assert failed.error_message == message


def test_with_failure_refuses_when_failing_is_not_legal(job: Job) -> None:
    """A completed job cannot retroactively fail."""
    completed = (
        job.with_status(JobStatus.PROBING)
        .with_status(JobStatus.READY)
        .with_status(JobStatus.RUNNING)
        .with_status(JobStatus.POST_PROCESSING)
        .with_status(JobStatus.COMPLETED)
    )
    with pytest.raises(IllegalTransitionError):
        completed.with_failure(ErrorKind.DISK, "too late")


# --- progress ------------------------------------------------------------------------------


def test_progress_is_none_when_the_total_is_unknown(job: Job) -> None:
    """A live stream and a stalled download differ; a confident 0% would lie about both."""
    assert job.progress is None


def test_progress_is_a_fraction_when_the_total_is_known(request_: DownloadRequest) -> None:
    job = Job(id="j", url="https://e.com/x", request=request_, bytes_done=512, bytes_total=1024)
    assert job.progress == pytest.approx(0.5)


def test_progress_never_exceeds_one(request_: DownloadRequest) -> None:
    """yt-dlp's reported total can be an estimate that the actual download overshoots."""
    job = Job(id="j", url="https://e.com/x", request=request_, bytes_done=2048, bytes_total=1024)
    assert job.progress == 1.0


def test_timestamps_are_optional_and_default_to_none(job: Job) -> None:
    """`T-014` sets them; the domain model does not reach for a clock."""
    assert job.created_at is None
    assert job.started_at is None
    assert job.finished_at is None


def test_a_job_carrying_timestamps_still_pickles(request_: DownloadRequest) -> None:
    job = Job(
        id="j",
        url="https://e.com/x",
        request=request_,
        created_at=datetime(2026, 7, 26, 12, 0, tzinfo=UTC),
    )
    assert pickle.loads(pickle.dumps(job)) == job
