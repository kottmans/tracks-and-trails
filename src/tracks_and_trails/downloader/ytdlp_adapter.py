"""Builds yt-dlp options from a DownloadRequest and projects info dicts into core models.

Together with `worker.py` this confines yt-dlp churn to two modules (`NFR-008`). Nothing else
in the codebase may `import yt_dlp` (`ARCHITECTURE.md` §6, enforced by `T-005`'s layering test).

Pure translation: no process handling, no I/O, no network. Everything here is a function from
yt-dlp's vocabulary to this project's, or back. That is what makes it testable against recorded
fixtures rather than against a live site (`ai/TESTING.md` §5, §6).

## Classification maps exception *types*, not message text

`core.errors.classify()` already records why: extractor prose changes without notice, and a
wrong guess is worse than no guess because `DRM_PROTECTED` and `NETWORK` carry retry policy.
So the mapping below is a type table, ordered most-specific-first because
`UnsupportedError` and `GeoRestrictedError` are both `ExtractorError` subclasses.

**DRM is detected structurally, not from prose.** yt-dlp sets `_has_drm` on the info dict and
`has_drm` on individual formats. That is a real contract, so `SEC-001`'s "never work around
DRM" rests on a field rather than on matching the words "DRM protected" in a message that may
be translated or reworded upstream.

Some taxonomy kinds have no yt-dlp exception type at all — see `UNMAPPED_KINDS`. They are
listed explicitly rather than quietly absent, so a reader can tell "not applicable" from
"forgotten".
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from yt_dlp.networking.exceptions import HTTPError, TransportError
from yt_dlp.utils import (
    ContentTooShortError,
    DownloadCancelled,
    DownloadError,
    ExtractorError,
    GeoRestrictedError,
    PostProcessingError,
    ThrottledDownload,
    UnsupportedError,
)

from tracks_and_trails.core.errors import ErrorKind, FailureDetail
from tracks_and_trails.core.models import DownloadRequest, FormatInfo, MediaInfo, MediaKind


class UnsupportedPostProcessorError(ValueError):
    """A requested post-processor does not exist in the pinned yt-dlp.

    Its own type so it can be classified deliberately (`FFMPEG_ERROR`) rather than falling into
    the `EXTRACTOR_ERROR` catch-all, which would blame the site for a configuration mistake.
    """


#: yt-dlp exception type to taxonomy kind, **most specific first**.
#:
#: Order is load-bearing: `UnsupportedError` and `GeoRestrictedError` subclass `ExtractorError`,
#: so a table walked in the wrong order would classify every one of them as `EXTRACTOR_ERROR`
#: and lose the distinction that decides what the user is told.
_EXCEPTION_MAPPING: Final[tuple[tuple[type[BaseException], ErrorKind], ...]] = (
    (UnsupportedPostProcessorError, ErrorKind.FFMPEG_ERROR),
    (DownloadCancelled, ErrorKind.CANCELLED),
    (UnsupportedError, ErrorKind.UNSUPPORTED_URL),
    (GeoRestrictedError, ErrorKind.GEO_RESTRICTED),
    (PostProcessingError, ErrorKind.FFMPEG_ERROR),
    (ContentTooShortError, ErrorKind.NETWORK),
    (ThrottledDownload, ErrorKind.NETWORK),
    # yt-dlp's own transport layer (`T012-R3`). These do **not** subclass `OSError` or
    # `ConnectionError`, so the two built-ins below never caught them and every transport
    # failure fell through to `EXTRACTOR_ERROR` — which is not auto-retryable, so `REQ-018`'s
    # retry-on-transient behaviour was silently dead. Covers `ProxyError`, `SSLError`,
    # `CertificateVerifyError` and `IncompleteRead`, which are all `TransportError` subclasses.
    (TransportError, ErrorKind.NETWORK),
    (ExtractorError, ErrorKind.EXTRACTOR_ERROR),
    (ConnectionError, ErrorKind.NETWORK),
    (TimeoutError, ErrorKind.NETWORK),
    (OSError, ErrorKind.DISK),
)

#: HTTP statuses whose consequence is "this may work if tried again".
#:
#: `HTTPError` is a `RequestError` but **not** a `TransportError`, and mapping the whole class to
#: `NETWORK` would auto-retry a 404 forever while mapping it all to `EXTRACTOR_ERROR` would
#: refuse to retry a 503. The status is the only structured evidence of which one it is, so it
#: is what decides (`T012-R3`).
_RETRYABLE_STATUSES: Final[frozenset[int]] = frozenset({408, 429, 500, 502, 503, 504})

#: Taxonomy kinds with no yt-dlp exception type, and why. Listed so their absence reads as a
#: decision rather than an oversight — the acceptance criterion is that every kind yt-dlp *can*
#: raise is mapped, not that every kind appears here.
UNMAPPED_KINDS: Final[Mapping[ErrorKind, str]] = {
    ErrorKind.DRM_PROTECTED: (
        "detected structurally from `_has_drm` before extraction is attempted, not raised"
    ),
    ErrorKind.FFMPEG_MISSING: (
        "detected up front by downloader.environment (T-035); yt-dlp only reports it as prose"
    ),
    ErrorKind.AUTH_REQUIRED: (
        "no auth exception type exists; HTTP 401 is mapped structurally from HTTPError.status, "
        "but a login wall served as a normal page still arrives as ExtractorError and guessing "
        "from message text is exactly what classify() refuses to do"
    ),
    ErrorKind.WORKER_CRASH: (
        "produced by the parent observing a child's exit code (T-013); a worker cannot raise it"
    ),
}


def unwrap(error: BaseException) -> BaseException:
    """Return the underlying cause of a `DownloadError`, or `error` itself.

    yt-dlp wraps most failures in `DownloadError`, keeping the original in `exc_info`. Without
    unwrapping, every failure would classify identically and the taxonomy would be decorative.
    """
    if isinstance(error, DownloadError):
        info = getattr(error, "exc_info", None)
        if info and len(info) >= 2 and isinstance(info[1], BaseException):
            return info[1]
    return error


def extractor_message(error: BaseException) -> str:
    """The extractor's own words, without yt-dlp's bug-report boilerplate.

    `ExtractorError` decorates unexpected failures: `str(e)` for "Private video. Sign in..."
    appends *"please report this issue on https://github.com/yt-dlp/yt-dlp/issues..."*. Passing
    that to the user tells them to file a bug about a private video — which is not a bug, and
    not what `NFR-006` means by surfacing the extractor's message.

    `orig_msg` is the undecorated text and is preferred wherever yt-dlp provides it. Everything
    else falls back to `str()`, which is already clean for expected conditions.
    """
    cause = unwrap(error)
    for candidate in (cause, error):
        original = getattr(candidate, "orig_msg", None)
        if isinstance(original, str) and original.strip():
            return original
    return str(error) or repr(error)


def classify_exception(error: BaseException) -> FailureDetail:
    """Map a yt-dlp failure onto the taxonomy, keeping the extractor's message **verbatim**.

    The classification comes from the unwrapped type, because that is where the structure is;
    the message comes from `extractor_message()` (`NFR-006`, `REQ-005`).

    An unmapped exception becomes `EXTRACTOR_ERROR` rather than crashing the worker: a worker
    that dies while classifying turns a failed job into a lost one.
    """
    cause = unwrap(error)
    message = extractor_message(error)

    # Before the type table: `HTTPError`'s consequence lives in its status, not its class.
    if isinstance(cause, HTTPError):
        return FailureDetail(kind=_http_status_kind(cause.status), message=message)

    for exception_type, kind in _EXCEPTION_MAPPING:
        if isinstance(cause, exception_type):
            return FailureDetail(kind=kind, message=message)
    return FailureDetail(kind=ErrorKind.EXTRACTOR_ERROR, message=message)


def _http_status_kind(status: int) -> ErrorKind:
    """Classify an HTTP failure by what it means for the user, not by its class.

    `401` is the one status that unambiguously means "credentials required"; **`403` is
    deliberately not mapped to `AUTH_REQUIRED`**, because sites return it for expired signed
    URLs and regional blocks far more often than for a missing login, and telling a user to
    sign in when signing in cannot help is worse than saying nothing. Its verbatim message
    still reaches them.
    """
    if status in _RETRYABLE_STATUSES:
        return ErrorKind.NETWORK
    if status == 401:
        return ErrorKind.AUTH_REQUIRED
    return ErrorKind.EXTRACTOR_ERROR


def has_drm(info: Mapping[str, Any]) -> bool:
    """Whether yt-dlp reports this item as DRM-protected (`REQ-EXCL-001`, `SEC-001`).

    Reads `_has_drm`, which `YoutubeDL` sets, and falls back to the per-format `has_drm` flags.
    Both are structured fields. **No message text is consulted**, and no attempt is made to
    find a non-DRM route — this project does not work around DRM and offering to retry would
    imply it might.
    """
    if info.get("_has_drm"):
        return True
    formats = info.get("formats") or ()
    return bool(formats) and all(entry.get("has_drm") for entry in formats)


def project_format(entry: Mapping[str, Any]) -> FormatInfo:
    """Project one yt-dlp format dict into a declared `FormatInfo`.

    Declared fields only (`ARCHITECTURE.md` §5). `filesize_approx` is accepted as a fallback for
    `filesize` because yt-dlp supplies one or the other depending on the extractor, and a
    missing size shows the user "unknown" rather than a wrong number.
    """
    filesize = entry.get("filesize")
    if filesize is None:
        filesize = entry.get("filesize_approx")
    return FormatInfo(
        format_id=str(entry.get("format_id") or ""),
        extension=str(entry.get("ext") or ""),
        height=_as_optional_int(entry.get("height")),
        width=_as_optional_int(entry.get("width")),
        filesize=_as_optional_int(filesize),
        video_codec=_as_optional_codec(entry.get("vcodec")),
        audio_codec=_as_optional_codec(entry.get("acodec")),
        note=_as_optional_str(entry.get("format_note")),
    )


def project_media(info: Mapping[str, Any]) -> MediaInfo:
    """Project a yt-dlp `info_dict` into a declared `MediaInfo`.

    **This is the boundary `ARC-002` exists to protect.** Past this point the raw dict does not
    travel: `downloader/protocol.py` refuses to carry one, and `core/models.py` refuses to hold
    a list of them.

    A missing title becomes the URL rather than an empty string, because `MediaInfo` requires a
    displayable title and inventing "Untitled" would be worse than showing what the user pasted.
    """
    url = str(info.get("webpage_url") or info.get("original_url") or info.get("url") or "")
    title = str(info.get("title") or "").strip() or url
    formats = tuple(
        project_format(entry) for entry in (info.get("formats") or ()) if entry.get("format_id")
    )
    return MediaInfo(
        url=url,
        title=title,
        formats=formats,
        duration_seconds=_as_optional_float(info.get("duration")),
        uploader=_as_optional_str(info.get("uploader")),
        thumbnail_url=_as_optional_str(info.get("thumbnail")),
        is_live=bool(info.get("is_live")),
    )


def build_options(
    request: DownloadRequest,
    output_template: str,
    *,
    probe_only: bool = False,
    progress_hooks: Sequence[Any] = (),
    postprocessor_hooks: Sequence[Any] = (),
    ffmpeg_location: Path | None = None,
) -> dict[str, Any]:
    """Build the yt-dlp options dict for one session.

    `output_template` is passed in already joined to the target directory by `worker.py`, which
    is also what runs the result through `T-034`'s containment check. Rendering uses yt-dlp's
    own template mechanism (`ARCHITECTURE.md` §9) — this module never interpolates a title into
    a path itself.

    Deliberately quiet and non-interactive: a worker has no console and no user. `noprogress`
    is set because progress reaches the GUI through `progress_hooks`, not stdout.
    """
    options: dict[str, Any] = {
        "outtmpl": output_template,
        "format": request.format_selector,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        # No console, no user, no prompts. An interactive prompt in a worker is a hang.
        "no_color": True,
        "consoletitle": False,
        "progress_hooks": list(progress_hooks),
        "postprocessor_hooks": list(postprocessor_hooks),
    }

    # Connection settings apply to **both** phases (`T012-R5`). A download probes first, and
    # these used to be added only after the `probe_only` early return — so a URL that needed
    # the configured proxy or cookies failed during the probe, before the download that would
    # have used them was ever attempted. The user had set the option correctly and it was not
    # applied to the request that needed it.
    if request.proxy:
        options["proxy"] = request.proxy
    if request.rate_limit_bytes:
        options["ratelimit"] = request.rate_limit_bytes
    if request.cookies_from_browser:
        options["cookiesfrombrowser"] = (request.cookies_from_browser,)
    if ffmpeg_location is not None:
        # `OPS-001`: the worker resolves ffmpeg and gates on it, but yt-dlp does its own lookup
        # and would silently use a different binary — or none — without being told.
        options["ffmpeg_location"] = str(ffmpeg_location)

    if probe_only:
        options["skip_download"] = True
        return options

    if request.subtitle_languages:
        options["writesubtitles"] = True
        options["subtitleslangs"] = list(request.subtitle_languages)

    options["postprocessors"] = build_postprocessors(request)
    return options


def requires_ffmpeg(request: DownloadRequest) -> bool:
    """Whether this request's post-processing needs ffmpeg (`REQ-024`, `T012-R5`).

    Derived from the **class hierarchy** rather than a list of names: yt-dlp marks every
    ffmpeg-backed processor by subclassing `FFmpegPostProcessor`, so asking that question
    cannot drift as processors are added upstream. A hardcoded list would silently stop
    covering the next one, which is how the early gate came to miss requested processors in
    the first place.

    Read by `worker._ffmpeg_gap` so the user is told **before** the download, not after the
    bytes are already spent — the entire point of `REQ-024`.
    """
    from yt_dlp.postprocessor import get_postprocessor
    from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor

    for spec in build_postprocessors(request):
        try:
            processor = get_postprocessor(str(spec["key"]))
        except KeyError, AttributeError:  # pragma: no cover - build_postprocessors validates
            return True
        if issubclass(processor, FFmpegPostProcessor):
            return True
    return False


def build_postprocessors(request: DownloadRequest) -> list[dict[str, Any]]:
    """Translate the request's post-processing intent into what `YoutubeDL` actually consumes.

    **`extractaudio` and `embedsubtitles` are argument-parser flags, not library options**
    (`T012-R5`). Constructing `YoutubeDL({"extractaudio": True})` builds an empty postprocessor
    list: the key is accepted, ignored, and produces no audio extraction at all. Every audio
    preset would have silently delivered the original container instead of the requested one.
    The library reads `postprocessors`, a list of dicts keyed by `key`.

    Names from `DownloadRequest.post_processors` are validated against yt-dlp's own registry
    rather than trusted or filtered against a hardcoded list. An unknown name **raises** instead
    of being dropped: silently discarding a requested post-processor is the same class of defect
    as the two above, and the whole point of this correction.
    """
    from yt_dlp.postprocessor import get_postprocessor

    specs: list[dict[str, Any]] = []
    if request.media_kind is MediaKind.AUDIO:
        # `preferredcodec` is what makes the MP3 preset differ from best/original (`T012-R5`).
        # Omitting it leaves yt-dlp's default of "best", which *keeps* the source codec — so
        # both `REQ-006` audio presets produced the same file and the MP3 one never converted.
        audio: dict[str, Any] = {
            "key": "FFmpegExtractAudio",
            "preferredcodec": request.audio_codec.value,
        }
        if request.audio_quality is not None:
            audio["preferredquality"] = request.audio_quality
        specs.append(audio)
    if request.subtitle_languages and request.embed_subtitles:
        specs.append({"key": "FFmpegEmbedSubtitle"})
    specs.extend({"key": name} for name in request.post_processors)

    resolved: list[dict[str, Any]] = []
    seen: set[str] = set()
    for spec in specs:
        key = str(spec["key"])
        if key in seen:
            continue
        try:
            get_postprocessor(key)
        except (KeyError, AttributeError) as error:
            raise UnsupportedPostProcessorError(
                f"unknown post-processor {key!r}: yt-dlp has no such post-processor"
            ) from error
        seen.add(key)
        resolved.append(spec)
    return resolved


def _as_optional_int(value: object) -> int | None:
    """yt-dlp reports numbers as int, float, str, or `'none'` depending on the extractor."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 else None
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _as_optional_float(value: object) -> float | None:
    if value is None or isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if value >= 0 else None


def _as_optional_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _as_optional_codec(value: object) -> str | None:
    """`'none'` is yt-dlp's way of saying a stream is absent — not a codec called "none"."""
    codec = _as_optional_str(value)
    return None if codec in (None, "none") else codec
