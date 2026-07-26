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

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Self

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus, apply


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
        if not self.format_id:
            raise ValueError("FormatInfo requires a format_id; it is how a format is selected")

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
        if not self.url:
            raise ValueError("MediaInfo requires the url it describes")
        if not self.title:
            raise ValueError(
                "MediaInfo requires a title; when the extractor supplies none, the caller "
                "substitutes something displayable rather than storing an empty string"
            )


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
        if not self.url:
            raise ValueError("DownloadRequest requires a url")
        if not self.output_directory:
            raise ValueError("DownloadRequest requires an output directory")
        if not self.format_selector:
            raise ValueError(
                "DownloadRequest requires a format selector; an empty one silently means "
                "yt-dlp's default, which is not the same as the preset the user chose"
            )
        if not self.output_template:
            raise ValueError("DownloadRequest requires an output template")


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
        if not self.name:
            raise ValueError("Preset requires a name; it is what the user selects it by")
        if not self.format_selector:
            raise ValueError("Preset requires a format selector")


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
        if not self.id:
            raise ValueError("Job requires an id")
        if not self.url:
            raise ValueError("Job requires a url")
        if self.bytes_done < 0:
            raise ValueError("Job.bytes_done cannot be negative")
        if self.bytes_total is not None and self.bytes_total < 0:
            raise ValueError("Job.bytes_total cannot be negative")
        if self.attempts < 0:
            raise ValueError("Job.attempts cannot be negative")

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
