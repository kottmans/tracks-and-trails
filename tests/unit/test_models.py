"""Domain models (`T-010`).

Two things are asserted here, and the second is the one that matters. Picklability alone would
be satisfied by empty dataclasses — the vacuous pass `T-010` explicitly warns against — so
every model's required fields and invariants are pinned as well.
"""

import dataclasses
import pickle
import typing
from datetime import UTC, datetime

import pytest

from tracks_and_trails.core import models
from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import IllegalTransitionError, JobStatus
from tracks_and_trails.core.models import (
    BROWSER_NAMES,
    KEYRING_NAMES,
    DownloadRequest,
    FormatInfo,
    Job,
    MediaInfo,
    MediaKind,
    PlaylistEntry,
    Preset,
    parse_browser_specification,
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


def test_a_count_of_entries_is_only_meaningful_on_a_playlist() -> None:
    """`T-018`'s playlist fields, made incapable of describing a contradiction.

    A single item with `entry_count=7` is not a state anything should have to interpret: a UI
    reading it would render "7 items" for one thing, and every reader would have to remember to
    check `is_playlist` first. Making the pair unrepresentable is the same move `T-014` made for
    proxy credentials — cheaper than a rule everyone downstream must keep.
    """
    playlist = MediaInfo(url="https://example.com/p", title="P", is_playlist=True, entry_count=7)
    assert playlist.entry_count == 7

    unknown = MediaInfo(url="https://example.com/p", title="P", is_playlist=True)
    assert unknown.entry_count is None, "an uncounted playlist is unknown, not empty"

    with pytest.raises(ValueError, match="entry_count"):
        MediaInfo(url="https://example.com/x", title="T", entry_count=3)


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
    assert fmt.has_video is None
    assert fmt.has_audio is None


def test_a_stream_is_only_absent_when_something_said_so() -> None:
    """`T-108`: a codec nobody mentioned is unknown, not missing.

    **This is `T107-R1` made unrepresentable rather than merely fixed.** `is_audio_only` read
    `video_codec is None`, and `_as_optional_codec` maps yt-dlp's explicit `'none'` and a missing
    key to the same `None` — so a format whose video codec was merely unknown claimed to have no
    video. The table stopped asserting it; `REQ-008` cannot, because it has to route a format into
    a video or an audio slot.

    Asserted in all three states, because the middle one is the whole point: an audio codec beside
    *silence* about video answers `False` to both questions rather than `True` to one.
    """
    unknown = FormatInfo(format_id="251", extension="webm", audio_codec="opus")
    assert not unknown.is_audio_only, "a format nobody classified claimed to be audio-only"
    assert not unknown.is_video_only

    audio = FormatInfo(
        format_id="251", extension="webm", audio_codec="opus", has_audio=True, has_video=False
    )
    assert audio.is_audio_only
    assert not audio.is_video_only

    video = FormatInfo(
        format_id="137", extension="mp4", video_codec="avc1", has_video=True, has_audio=False
    )
    assert video.is_video_only
    assert not video.is_audio_only


def test_a_format_cannot_name_a_codec_for_a_stream_it_says_it_lacks() -> None:
    """Two fields that would contradict each other are refused at construction (`T-010`'s rule).

    A selection routine handed `has_audio=False, audio_codec="opus"` would have to decide which to
    believe, and whichever it picked would be right half the time. The model refuses the value
    instead, so no caller ever has the choice.
    """
    with pytest.raises(ValueError, match="one of the two is wrong"):
        FormatInfo(format_id="1", extension="mp4", audio_codec="opus", has_audio=False)
    with pytest.raises(ValueError, match="one of the two is wrong"):
        FormatInfo(format_id="1", extension="mp4", video_codec="avc1", has_video=False)


@pytest.mark.parametrize("bad", [0, 1, "true", ""])
def test_a_stream_presence_flag_refuses_anything_that_is_merely_truthy(bad: object) -> None:
    """`has_video=0` must not read as *"no video"* by truthiness (`_require_flag`'s reason)."""
    with pytest.raises(TypeError):
        FormatInfo(format_id="1", extension="mp4", has_video=bad)  # type: ignore[arg-type]


# --- nested payload validation (T-041, from T011-R8) ----------------------------------------


def valid_kwargs(request_: DownloadRequest) -> dict[type, dict[str, object]]:
    """Minimal valid constructor arguments for every model in this module."""
    return {
        FormatInfo: {"format_id": "137", "extension": "mp4"},
        PlaylistEntry: {"url": "https://example.com/e", "title": "E"},
        MediaInfo: {"url": "https://example.com/x", "title": "T"},
        DownloadRequest: {
            "url": "https://example.com/x",
            "output_directory": "/downloads",
            "format_selector": "best",
            "output_template": "%(title)s.%(ext)s",
        },
        Preset: {
            "name": "p",
            "media_kind": MediaKind.VIDEO,
            "format_selector": "best",
            "output_template": "%(title)s.%(ext)s",
        },
        Job: {"id": "j", "url": "https://example.com/x", "request": request_},
    }


def discovered_models() -> set[type]:
    """Every dataclass `core.models` itself defines, found by inspecting the module.

    `T041-R2`: the previous version compared `valid_kwargs()` with a hand-written `MODELS`
    list — two views of the same hand-maintained set, so adding a sixth model to the module
    left all 54 tests green. That is precisely the `T010-R1` vacuity, reproduced inside the
    test written to prevent it.

    This derives the production side independently. Imported classes are excluded by comparing
    `__module__`, so `ErrorKind` and `JobStatus` do not count, and enums are excluded because
    they carry no payload fields to validate.
    """
    return {
        obj
        for obj in vars(models).values()
        if isinstance(obj, type)
        and dataclasses.is_dataclass(obj)
        and obj.__module__ == models.__name__
    }


MODELS = sorted(discovered_models(), key=lambda m: m.__name__)


def test_every_model_the_module_defines_is_covered(request_: DownloadRequest) -> None:
    """Guards the guard, against the module rather than against another list.

    A dataclass added to `core/models.py` without sample kwargs fails here, which is what the
    previous version claimed to do and did not.
    """
    covered = set(valid_kwargs(request_))
    missing = discovered_models() - covered
    assert not missing, (
        f"{sorted(m.__name__ for m in missing)} defined in core.models but absent from "
        "valid_kwargs(), so no audit below touches them"
    )
    assert not covered - discovered_models(), "valid_kwargs() names something the module lost"


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
@pytest.mark.parametrize(
    ("label", "payload"),
    [
        ("raw dict", {"title": "Example", "formats": []}),
        ("list of raw dicts", [{"format_id": "137"}]),
        ("mutable list of strings", ["a"]),
    ],
)
def test_no_field_accepts_raw_or_mutable_payloads(
    request_: DownloadRequest, model: type, label: str, payload: object
) -> None:
    """`T-041`, from `T011-R8` — the **systematic** audit.

    `T011-R8` was reported as one field, `MediaInfo.formats`. Auditing the module found that
    *every* field of *every* model accepted an arbitrary dict or list: the only checks were
    emptiness and negativity, and a non-empty dict passes both. Fixing the reported field alone
    would have repeated the mistake that got `T011-R2` reopened.

    This walks every field of every model, so a field added later without validation fails here
    without anyone remembering to extend a list.

    A field may legitimately **normalise** a sequence — a list of the right element type becomes
    a tuple — but it may never *store* a mutable container, and it may never accept a raw dict
    where a declared model belongs (`ARC-002`).
    """
    fields: dict[str, object] = model.__dataclass_fields__  # type: ignore[attr-defined]
    for name in fields:
        kwargs = dict(valid_kwargs(request_)[model])
        kwargs[name] = payload
        try:
            stored = getattr(model(**kwargs), name)
        except TypeError, ValueError:
            continue
        assert not isinstance(stored, dict | list), (
            f"{model.__name__}.{name} accepted and stored a {type(stored).__name__} "
            f"({label}); a mutable payload reachable from a sent model can change after "
            "put() and before the feeder thread serializes it"
        )


def field_names(model: type) -> list[str]:
    """Declared field names. Centralises the one `__dataclass_fields__` access mypy dislikes."""
    return list(model.__dataclass_fields__)  # type: ignore[attr-defined]


def annotated_types(model: type, name: str) -> set[type]:
    """The concrete types in a field's annotation, unwrapping unions."""
    hint = typing.get_type_hints(model)[name]
    args = typing.get_args(hint) or (hint,)
    return {arg for arg in args if isinstance(arg, type)}


def optional_fields(model: type) -> set[str]:
    """Fields whose annotation admits `None`."""
    return {name for name in field_names(model) if type(None) in annotated_types(model, name)}


def numeric_fields(model: type) -> set[str]:
    """Fields annotated as a number but **not** as a bool.

    `bool` is an `int` subclass, so `True` would otherwise be stored as a count of 1.
    """
    result = set()
    for name in field_names(model):
        types_ = annotated_types(model, name)
        if (int in types_ or float in types_) and bool not in types_:
            result.add(name)
    return result


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_fields_that_cannot_be_none_reject_none(request_: DownloadRequest, model: type) -> None:
    """`T041-R6`. Nullability, derived from each model's own annotations.

    The hostile-payload sweep once carried a `None` case, and it was **vacuous**: its assertion
    is `not isinstance(stored, dict | list)`, and `None` is neither, so any field storing `None`
    passed. `T-041`'s handoff claimed that case covered the class. It did not — protection came
    from two explicitly named fields.

    Reading optionality from the annotations means a new required field is covered without
    anyone editing a list, which is `T041-R2`'s lesson applied before it bites again.
    """
    optional = optional_fields(model)
    required = [n for n in field_names(model) if n not in optional]
    assert required, f"{model.__name__} has no required fields; the sweep would be vacuous"

    for name in required:
        kwargs = dict(valid_kwargs(request_)[model])
        kwargs[name] = None
        with pytest.raises((TypeError, ValueError)):
            model(**kwargs)


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_fields_that_may_be_none_accept_none(request_: DownloadRequest, model: type) -> None:
    """The counterpart, so the rule above cannot be satisfied by rejecting `None` everywhere."""
    for name in optional_fields(model):
        kwargs = dict(valid_kwargs(request_)[model])
        kwargs[name] = None
        assert getattr(model(**kwargs), name) is None


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_numeric_fields_reject_booleans(request_: DownloadRequest, model: type) -> None:
    """`T041-R6`. Nothing tested this: deleting the `bool` guard left all 76 tests green.

    `bool` is an `int` subclass, so `True` would be stored as a byte count of 1 — a wrong number
    that looks like a right one, which is the shape of bug this project treats as serious.

    Driven by the annotations, so a numeric field added later is covered automatically.
    """
    fields = numeric_fields(model)
    if not fields:
        pytest.skip(f"{model.__name__} declares no numeric fields")

    for name in fields:
        kwargs = dict(valid_kwargs(request_)[model])
        kwargs[name] = True
        with pytest.raises(TypeError):
            model(**kwargs)


@pytest.mark.parametrize("field_name", ["bytes_done", "attempts"])
def test_required_job_counters_reject_none(request_: DownloadRequest, field_name: str) -> None:
    """`T041-R1`. Both are `int` with a `0` default, and both accepted `None`.

    That moves an invalid value toward persistence, and `Job.progress` raises rather than
    returning a fraction when a total is present.
    """
    base = {"id": "j", "url": "https://example.com/x", "request": request_}
    with pytest.raises(ValueError, match="cannot be None"):
        Job(**base, **{field_name: None})  # type: ignore[arg-type]


@pytest.mark.parametrize("field_name", ["bytes_total", "queue_position"])
def test_genuinely_optional_job_counters_still_accept_none(
    request_: DownloadRequest, field_name: str
) -> None:
    """The narrowing must not sweep up fields that are legitimately absent."""
    base = {"id": "j", "url": "https://example.com/x", "request": request_}
    assert getattr(Job(**base, **{field_name: None}), field_name) is None  # type: ignore[arg-type]


def test_a_format_info_subclass_cannot_smuggle_fields_into_media_info() -> None:
    """`T041-R3`: `isinstance` let a subclass carry undeclared mutable state.

    A frozen subclass is still frozen, but nothing here validates fields it declares — so a
    mutable dict rides along inside an otherwise valid `MediaInfo`, and mutating the original
    changes an already-constructed graph that may already have been sent.
    """

    @dataclasses.dataclass(frozen=True, slots=True)
    class SneakyFormat(FormatInfo):
        payload: dict[str, str] = dataclasses.field(default_factory=dict)

    smuggled = {"url": "https://cdn.example/secret"}
    sneaky = SneakyFormat(format_id="137", extension="mp4", payload=smuggled)

    assert isinstance(sneaky, FormatInfo), "the premise: it passes an isinstance check"
    with pytest.raises(TypeError):
        MediaInfo(url="https://example.com/x", title="T", formats=(sneaky,))


def test_a_download_request_subclass_cannot_smuggle_fields_into_a_job() -> None:
    """`T041-R3`, the other reachable boundary."""

    @dataclasses.dataclass(frozen=True, slots=True)
    class SneakyRequest(DownloadRequest):
        payload: dict[str, str] = dataclasses.field(default_factory=dict)

    sneaky = SneakyRequest(
        url="https://example.com/x",
        output_directory="/downloads",
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        payload={"cookie": "secret"},
    )
    assert isinstance(sneaky, DownloadRequest)
    with pytest.raises(TypeError):
        Job(id="j", url="https://example.com/x", request=sneaky)


@pytest.mark.parametrize(
    ("model", "field_name"),
    [
        (FormatInfo, "format_id"),
        (MediaInfo, "url"),
        (MediaInfo, "title"),
        (DownloadRequest, "url"),
        (DownloadRequest, "output_directory"),
        (DownloadRequest, "format_selector"),
        (DownloadRequest, "output_template"),
        (Preset, "name"),
        (Preset, "format_selector"),
        (Job, "id"),
        (Job, "url"),
    ],
)
def test_required_text_fields_raise_type_error_for_the_wrong_type(
    request_: DownloadRequest, model: type, field_name: str
) -> None:
    """`T041-R4`: the exception contract, applied consistently.

    `TypeError` for the wrong type, `ValueError` for a validly typed empty string. The bespoke
    truthiness checks these replaced raised `ValueError` for both, so a caller could not tell
    them apart — and only the empty case had tests.
    """
    kwargs = dict(valid_kwargs(request_)[model])
    kwargs[field_name] = 7
    with pytest.raises(TypeError):
        model(**kwargs)

    kwargs[field_name] = ""
    with pytest.raises(ValueError):
        model(**kwargs)


@pytest.mark.parametrize(
    ("model", "field_name"),
    [
        (Job, "title"),
        (Job, "thumbnail_url"),
        (Job, "uploader"),
        (Job, "output_path"),
        (Job, "error_message"),
        (MediaInfo, "thumbnail_url"),
    ],
)
def test_optional_text_fields_accept_none_and_refuse_the_wrong_type(
    request_: DownloadRequest, model: type, field_name: str
) -> None:
    """`T041-R4`'s contract for the fields that are genuinely allowed to be absent.

    `T-117` added `Job.thumbnail_url` and it goes through the same validator as the three optional
    text fields already here, rather than a check of its own. Listed explicitly rather than
    derived from the annotations: a field that acquired `str | None` by accident would be swept
    into a derived list and validated by default, which is the opposite of noticing it.
    """
    kwargs = dict(valid_kwargs(request_)[model])

    kwargs[field_name] = None
    assert getattr(model(**kwargs), field_name) is None

    kwargs[field_name] = 7
    with pytest.raises(TypeError):
        model(**kwargs)


def test_media_info_rejects_raw_yt_dlp_format_dicts() -> None:
    """`T011-R8`'s exact reproduction, kept as a regression test.

    Before `T-041`, this constructed, passed `is_message()` inside a `Probed`, survived pickle
    with the dicts intact, and still mutated afterwards — a CDN URL from raw yt-dlp data
    crossing the process boundary inside a message that validated.
    """
    raw = [{"format_id": "137", "ext": "mp4", "url": "https://cdn.example/secret"}]
    with pytest.raises(TypeError, match="ARC-002"):
        MediaInfo(url="https://example.com/x", title="T", formats=raw)  # type: ignore[arg-type]


def test_a_list_of_the_right_type_is_normalised_to_a_tuple() -> None:
    """Normalising is fine; storing the caller's list is not.

    A frozen dataclass holding a list is only shallowly frozen, so the caller could mutate a
    model that has already been sent (`T010-R2`).
    """
    formats = [FormatInfo(format_id="137", extension="mp4")]
    # A list is deliberately passed: the point is that it is normalised, not stored.
    media = MediaInfo(url="https://example.com/x", title="T", formats=formats)  # type: ignore[arg-type]
    assert isinstance(media.formats, tuple)

    formats.append(FormatInfo(format_id="140", extension="m4a"))
    assert len(media.formats) == 1, "the model tracked the caller's list after construction"


def test_string_fields_do_not_silently_become_character_tuples() -> None:
    """A `str` is a `Sequence`, so `post_processors="abc"` would become `("a", "b", "c")`."""
    with pytest.raises(TypeError):
        DownloadRequest(
            url="https://example.com/x",
            output_directory="/downloads",
            format_selector="best",
            output_template="%(title)s.%(ext)s",
            post_processors="FFmpegExtractAudio",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("label", "kwargs"),
    [
        ("status", {"status": "queued"}),
        ("error_kind", {"error_kind": "network"}),
        ("request", {"request": {"url": "x"}}),
        ("created_at", {"created_at": "2026-07-26"}),
    ],
)
def test_job_rejects_stringly_typed_fields(
    request_: DownloadRequest, label: str, kwargs: dict[str, object]
) -> None:
    """`StrEnum` members compare equal to their values, so a bare string mostly works — until
    something does an identity check, which is the failure `T011-R2` recorded."""
    base = {"id": "j", "url": "https://example.com/x", "request": request_}
    with pytest.raises(TypeError):
        Job(**{**base, **kwargs})  # type: ignore[arg-type]


def test_nested_validation_survives_pickle(request_: DownloadRequest) -> None:
    """A restored model must carry declared types and immutable collections, not raw data."""
    media = MediaInfo(
        url="https://example.com/x",
        title="T",
        formats=[FormatInfo(format_id="137", extension="mp4")],  # type: ignore[arg-type]
    )
    restored = pickle.loads(pickle.dumps(media))
    assert isinstance(restored.formats, tuple)
    assert isinstance(restored.formats[0], FormatInfo)


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


def test_the_browser_and_keyring_names_agree_with_yt_dlp() -> None:
    """**The drift test I said existed and had not written** (`T-197`'s re-review).

    `core/models.py` transcribes yt-dlp's `SUPPORTED_BROWSERS` and `SUPPORTED_KEYRINGS` because
    `core/**` may not import `yt_dlp` (`ARCHITECTURE.md` §6). Two lists of the same names is two
    places to drift — a browser yt-dlp adds would be refused here, and one it drops would be
    accepted here and rejected by the library at download time.

    Asserted in a module that may import both, which is the same device `THEME_NAMES` uses. The
    handoff claimed this existed before it did; that claim is the reason it is written now.
    """
    from yt_dlp.cookies import SUPPORTED_BROWSERS, SUPPORTED_KEYRINGS

    assert set(BROWSER_NAMES) == set(SUPPORTED_BROWSERS), (
        f"this application accepts {sorted(BROWSER_NAMES)} and yt-dlp supports "
        f"{sorted(SUPPORTED_BROWSERS)}"
    )
    assert {name.upper() for name in KEYRING_NAMES} == set(SUPPORTED_KEYRINGS), (
        f"this application accepts {sorted(KEYRING_NAMES)} and yt-dlp supports "
        f"{sorted(SUPPORTED_KEYRINGS)}"
    )


@pytest.mark.parametrize(
    "refused",
    [
        "firefox:$HOME",
        "firefox:${HOME}",
        "firefox:~",
        "firefox:~someone",
        "firefox:%USERPROFILE%",
        "firefox:/home/alice/.mozilla",
        "firefox:C:\\Users\\alice",
        "notabrowser",
        "firefox+nosuchkeyring",
    ],
)
def test_a_profile_that_could_become_a_path_is_refused(refused: str) -> None:
    """**`T197-R2`, both rounds.** A path must not reach the model, however it is spelled.

    The first correction checked the written characters, and `firefox:$HOME` passed it — yt-dlp
    runs a profile through `expand_path` and turned that into `/home/sean`. Expansion is performed
    here now *and* its three syntactic forms are refused outright, because performing it alone
    answers differently on different machines: `~x` expands only where that user exists, and
    `%VAR%` only on Windows. That environment-dependence is the class that has cost this project
    three findings already.
    """
    with pytest.raises(ValueError):
        parse_browser_specification(refused)


@pytest.mark.parametrize(
    "accepted", ["firefox", "firefox:Private", "chrome:Default", "firefox:Profile 1", "brave"]
)
def test_a_real_profile_name_is_still_accepted(accepted: str) -> None:
    """The other direction: a check that refuses everything protects nothing anyone can use."""
    assert parse_browser_specification(accepted)[0] in BROWSER_NAMES
