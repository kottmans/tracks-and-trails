"""Domain models: Job, DownloadRequest, MediaInfo, FormatInfo, Preset.

The pure-domain foundation of the vertical slice (`T-010`). No Qt, no yt-dlp, no I/O beyond
the standard library — `core/` is the layer that stays testable headless and is reused by both
the GUI process and the spawned worker (`ARCHITECTURE.md` §4).

Two properties are load-bearing and easy to lose:

- **Everything here crosses a process boundary** (`ARC-002`). Every type must be picklable:
  plain dataclasses and enums, no lambdas, no open handles, no `functools.partial`. The tests
  assert this per type, so the day someone adds an unpicklable field it fails loudly rather
  than at the first real download.
- **`DownloadRequest` is frozen at job-creation time** (`ARCHITECTURE.md` §8). A running job
  never observes a mid-flight settings change, which is what makes the worker's behavior
  reproducible from the request alone — and what makes a retry repeat the *original* request
  rather than today's defaults (`REQ-018`).

Every model here is frozen. Immutability is not stylistic: these objects are read on the GUI
thread, sent to a worker process, and persisted, and a shared mutable job is how a queue
silently disagrees with its own database.

`HistoryEntry` is named in `ARCHITECTURE.md` §5 but is not defined here. It is a *durable
record* rather than live domain state, so it belongs with the schema that stores it (`T-014`).
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any, Self

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus, apply

# --- field validation -----------------------------------------------------------------------
#
# `T011-R8` found that `MediaInfo(formats=[{...}])` stored a mutable list of raw yt-dlp format
# dicts — so raw upstream data crossed the process boundary inside a `Probed` message that
# validated, and could still be mutated afterwards. `downloader/protocol.py` correctly rejects a
# non-`MediaInfo`; nothing checked what a `MediaInfo` contained.
#
# The audit that followed found the hole was not one field. **Every** field of every model here
# accepted an arbitrary dict or list: the only checks were emptiness and negativity, and a
# non-empty dict passes both. These helpers close the class rather than the instance, which is
# the lesson `T011-R2` had to be reopened to teach.
#
# Deliberately duplicated in miniature from `downloader/protocol.py` rather than shared:
# `T-041`'s scope puts that module out of bounds, and exporting private validators across a
# layer boundary to save ten lines is a worse trade. `normalise_context()` *is* shared, because
# there the risk was two hand-written copies of one subtle normalisation drifting apart.


def _fail(owner: str, name: str, value: object, expected: str) -> None:
    raise TypeError(f"{owner}.{name} must be {expected}, not {type(value).__name__}")


def _require_text(owner: str, name: str, value: object) -> None:
    """A non-empty string."""
    if not isinstance(value, str):
        _fail(owner, name, value, "a string")
    if not value:
        raise ValueError(f"{owner}.{name} cannot be empty")


def _require_optional_text(owner: str, name: str, value: object) -> None:
    if value is not None and not isinstance(value, str):
        _fail(owner, name, value, "a string or None")


def _require_optional_count(owner: str, name: str, value: object) -> None:
    """A non-negative `int` or `None`. `bool` is rejected: it is an `int` subclass."""
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(owner, name, value, "an int or None")
    if value < 0:  # type: ignore[operator]
        raise ValueError(f"{owner}.{name} cannot be negative")


def _require_optional_duration(owner: str, name: str, value: object) -> None:
    """A non-negative real number or `None`. Durations are legitimately fractional."""
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int | float):
        _fail(owner, name, value, "a number or None")
    if value < 0:  # type: ignore[operator]
        raise ValueError(f"{owner}.{name} cannot be negative")


def _require_flag(owner: str, name: str, value: object) -> None:
    """Strictly `bool` — not merely truthy. A non-empty dict is truthy."""
    if not isinstance(value, bool):
        _fail(owner, name, value, "a bool")


def _require_enum[E: Enum](owner: str, name: str, value: object, enum: type[E]) -> None:
    """An actual enum member.

    `StrEnum` members compare equal to their string values, so a bare string mostly works
    until something does an identity check — the failure mode `T011-R2` recorded.
    """
    if not isinstance(value, enum):
        _fail(owner, name, value, f"a {enum.__name__} member")


def _require_optional_enum[E: Enum](owner: str, name: str, value: object, enum: type[E]) -> None:
    if value is not None and not isinstance(value, enum):
        _fail(owner, name, value, f"a {enum.__name__} member or None")


def _require_model[T](owner: str, name: str, value: object, model: type[T]) -> None:
    if not isinstance(value, model):
        _fail(owner, name, value, f"a {model.__name__}")


def _require_optional_datetime(owner: str, name: str, value: object) -> None:
    if value is not None and not isinstance(value, datetime):
        _fail(owner, name, value, "a datetime or None")


def _as_tuple_of[T](owner: str, name: str, value: object, element: type[T]) -> tuple[T, ...]:
    """Return `value` as a tuple, rejecting a non-sequence or a wrong element type.

    Normalising a list to a tuple is deliberate: the element types are what matter, and a
    caller passing a list is not making a mistake. Storing it as a tuple is what stops the
    caller's list from mutating a model that has already been sent (`T010-R2`) — a frozen
    dataclass holding a list is only shallowly frozen.

    A `str` is a `Sequence` and is rejected explicitly, or `"abc"` would silently become
    `("a", "b", "c")`.
    """
    if isinstance(value, str) or not isinstance(value, Sequence):
        _fail(owner, name, value, f"a sequence of {element.__name__}")
    items: tuple[Any, ...] = tuple(value)  # type: ignore[arg-type]
    for index, item in enumerate(items):
        if not isinstance(item, element):
            raise TypeError(
                f"{owner}.{name}[{index}] must be a {element.__name__}, "
                f"not {type(item).__name__}"
                + (
                    " — a raw yt-dlp dict must never reach a domain model (ARC-002)"
                    if isinstance(item, dict)
                    else ""
                )
            )
    return items


class MediaKind(StrEnum):
    """What a preset or request is asking for.

    Video and audio are equal first-class citizens — the project's premise, not a detail
    (`README`, `REQ-002`). Neither is the default the other opts out of.
    """

    VIDEO = "video"
    AUDIO = "audio"


@dataclass(frozen=True, slots=True)
class FormatInfo:
    """One selectable format from a probe — a projection of yt-dlp's format dict.

    Declared fields only (`ARCHITECTURE.md` §5). Carrying the raw dict through the application
    would spread yt-dlp's schema into every layer and defeat `NFR-008`'s containment of
    upstream churn.
    """

    format_id: str
    extension: str

    #: Every field below is optional because yt-dlp genuinely omits them. A live stream has no
    #: filesize, an audio-only format has no height, and a storyboard has no codec. Modelling
    #: them as required would mean inventing values, which the UI would then display.
    height: int | None = None
    width: int | None = None
    filesize: int | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        identifier: Any = self.format_id
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("FormatInfo requires a format_id; it is how a format is selected")
        _require_text("FormatInfo", "extension", self.extension)
        for name in ("height", "width", "filesize"):
            _require_optional_count("FormatInfo", name, getattr(self, name))
        for name in ("video_codec", "audio_codec", "note"):
            _require_optional_text("FormatInfo", name, getattr(self, name))

    @property
    def is_audio_only(self) -> bool:
        return self.video_codec is None and self.audio_codec is not None


@dataclass(frozen=True, slots=True)
class MediaInfo:
    """What a probe learned about a URL — a projection of yt-dlp's `info_dict`.

    Declared fields only, for the same reason as `FormatInfo`. `T-018` pins this against
    recorded fixtures so an upstream schema change fails a test rather than a user's download.
    """

    url: str
    title: str
    formats: tuple[FormatInfo, ...] = ()

    #: A tuple, not a list: this is frozen, and a mutable default would let a caller edit a
    #: probe result that the UI is already displaying.
    duration_seconds: float | None = None
    uploader: str | None = None
    thumbnail_url: str | None = None
    is_live: bool = False

    def __post_init__(self) -> None:
        url: Any = self.url
        if not isinstance(url, str) or not url:
            raise ValueError("MediaInfo requires the url it describes")
        title: Any = self.title
        if not isinstance(title, str) or not title:
            raise ValueError(
                "MediaInfo requires a title; when the extractor supplies none, the caller "
                "substitutes something displayable rather than storing an empty string"
            )
        # `T011-R8`, the finding that opened this task: a list of raw yt-dlp format dicts used
        # to be stored verbatim, so upstream data crossed the process boundary inside an
        # otherwise valid `Probed` message and could still mutate afterwards.
        object.__setattr__(
            self, "formats", _as_tuple_of("MediaInfo", "formats", self.formats, FormatInfo)
        )
        _require_optional_duration("MediaInfo", "duration_seconds", self.duration_seconds)
        _require_optional_text("MediaInfo", "uploader", self.uploader)
        _require_optional_text("MediaInfo", "thumbnail_url", self.thumbnail_url)
        _require_flag("MediaInfo", "is_live", self.is_live)


@dataclass(frozen=True, slots=True)
class DownloadRequest:
    """The resolved intent for one download, frozen at job-creation time.

    `ARCHITECTURE.md` §8: settings are read into this once and never re-read. That is what
    makes a job reproducible from its request alone, and what stops a settings change from
    altering a download already in flight.

    This is the object the worker receives (`ARC-002`), so it must stay picklable and must
    contain no handles, callbacks, or live objects.
    """

    url: str
    output_directory: str
    format_selector: str
    output_template: str
    media_kind: MediaKind = MediaKind.VIDEO

    #: Tuples rather than lists throughout: a frozen dataclass with a mutable field is only
    #: shallowly frozen, and these travel between processes.
    post_processors: tuple[str, ...] = ()
    subtitle_languages: tuple[str, ...] = ()
    embed_subtitles: bool = False

    #: Network options are carried, never logged as-is. `T-038` redacts at the handler level
    #: (`NFR-007`), which is why a proxy URL may safely live in the model.
    proxy: str | None = None
    rate_limit_bytes: int | None = None
    cookies_from_browser: str | None = None

    def __post_init__(self) -> None:
        url: Any = self.url
        if not isinstance(url, str) or not url:
            raise ValueError("DownloadRequest requires a url")
        directory: Any = self.output_directory
        if not isinstance(directory, str) or not directory:
            raise ValueError("DownloadRequest requires an output directory")
        selector: Any = self.format_selector
        if not isinstance(selector, str) or not selector:
            raise ValueError(
                "DownloadRequest requires a format selector; an empty one silently means "
                "yt-dlp's default, which is not the same as the preset the user chose"
            )
        template: Any = self.output_template
        if not isinstance(template, str) or not template:
            raise ValueError("DownloadRequest requires an output template")
        _require_enum("DownloadRequest", "media_kind", self.media_kind, MediaKind)
        for name in ("post_processors", "subtitle_languages"):
            object.__setattr__(
                self, name, _as_tuple_of("DownloadRequest", name, getattr(self, name), str)
            )
        _require_flag("DownloadRequest", "embed_subtitles", self.embed_subtitles)
        _require_optional_text("DownloadRequest", "proxy", self.proxy)
        _require_optional_text("DownloadRequest", "cookies_from_browser", self.cookies_from_browser)
        _require_optional_count("DownloadRequest", "rate_limit_bytes", self.rate_limit_bytes)


@dataclass(frozen=True, slots=True)
class Preset:
    """A named, user-facing bundle that translates to a `DownloadRequest`.

    This task defines the *shape* only. Built-in preset content and the translation into a
    format selector are `T-015` — putting them here would mean deciding yt-dlp selector syntax
    inside a task reviewed for its domain model.
    """

    name: str
    media_kind: MediaKind
    format_selector: str
    output_template: str
    post_processors: tuple[str, ...] = ()

    #: Built-ins ship with the application and may not be edited or deleted; user presets may.
    #: The flag lives on the preset rather than in a separate list so the UI cannot lose track
    #: of which is which.
    built_in: bool = False

    def __post_init__(self) -> None:
        name_value: Any = self.name
        if not isinstance(name_value, str) or not name_value:
            raise ValueError("Preset requires a name; it is what the user selects it by")
        selector: Any = self.format_selector
        if not isinstance(selector, str) or not selector:
            raise ValueError("Preset requires a format selector")
        _require_enum("Preset", "media_kind", self.media_kind, MediaKind)
        _require_text("Preset", "output_template", self.output_template)
        object.__setattr__(
            self,
            "post_processors",
            _as_tuple_of("Preset", "post_processors", self.post_processors, str),
        )
        _require_flag("Preset", "built_in", self.built_in)


@dataclass(frozen=True, slots=True)
class Job:
    """One download, from queued to finished (`ARCHITECTURE.md` §5).

    Frozen, so a status change produces a new `Job` via `with_status` rather than mutating one
    that another layer may be holding. The state machine validates the change; this type just
    carries the result.
    """

    id: str
    url: str
    request: DownloadRequest
    status: JobStatus = JobStatus.QUEUED

    title: str | None = None
    output_path: str | None = None
    bytes_done: int = 0
    bytes_total: int | None = None

    #: Failure is stored as two fields rather than a `FailureDetail`, mirroring the columns in
    #: `ARCHITECTURE.md` §5 so the persistence layer (`T-014`) is a direct mapping. The
    #: verbatim message requirement (`NFR-006`) applies here just as strongly.
    error_kind: ErrorKind | None = None
    error_message: str | None = None

    attempts: int = 0
    queue_position: int | None = None

    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        identifier: Any = self.id
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("Job requires an id")
        job_url: Any = self.url
        if not isinstance(job_url, str) or not job_url:
            raise ValueError("Job requires a url")
        _require_optional_count("Job", "bytes_done", self.bytes_done)
        _require_optional_count("Job", "bytes_total", self.bytes_total)
        _require_optional_count("Job", "attempts", self.attempts)
        _require_model("Job", "request", self.request, DownloadRequest)
        _require_enum("Job", "status", self.status, JobStatus)
        _require_optional_enum("Job", "error_kind", self.error_kind, ErrorKind)
        _require_optional_text("Job", "title", self.title)
        _require_optional_text("Job", "output_path", self.output_path)
        _require_optional_text("Job", "error_message", self.error_message)
        _require_optional_count("Job", "queue_position", self.queue_position)
        for name in ("created_at", "started_at", "finished_at"):
            _require_optional_datetime("Job", name, getattr(self, name))

    def with_status(self, target: JobStatus) -> Self:
        """Return a copy in `target`, raising `IllegalTransitionError` if the move is not legal.

        Routing every status change through here is what makes `ai/TESTING.md` §7's guarantee
        real: there is no way to reach a new status that skips validation, short of building a
        `Job` by hand.
        """
        return replace(self, status=apply(self.status, target))

    def with_failure(self, kind: ErrorKind, message: str) -> Self:
        """Return a copy moved to `FAILED`, carrying the classification and the message.

        The message is stored **verbatim** (`NFR-006`, `REQ-005`). Callers that want a friendly
        summary present one alongside it; they do not substitute it here.
        """
        failed = replace(self, status=apply(self.status, JobStatus.FAILED))
        return replace(failed, error_kind=kind, error_message=message)

    @property
    def progress(self) -> float | None:
        """Fraction complete, or `None` when the total is unknown.

        `None` rather than `0.0`: a live stream and a stalled download are different states,
        and a progress bar that shows a confident zero for an unknown total is lying. The UI
        shows an indeterminate bar for `None` (`REQ-011`).
        """
        if not self.bytes_total:
            return None
        return min(self.bytes_done / self.bytes_total, 1.0)
