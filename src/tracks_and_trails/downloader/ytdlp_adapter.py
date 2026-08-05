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
from tracks_and_trails.core.models import (
    DownloadRequest,
    FormatInfo,
    MediaInfo,
    MediaKind,
    PlaylistEntry,
)


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
    ErrorKind.INTERRUPTED: (
        "produced by startup recovery when a persisted job is found in flight (T-014); nothing "
        "raises it, because the process that would have has already died"
    ),
}


#: Every `_type` yt-dlp declares for a result holding more than one video (`T018-R2`).
#:
#: Transcribed from `InfoExtractor`'s own documentation — *"`_type` `playlist` indicates multiple
#: videos"* and *"`_type` `multi_video` indicates that there are multiple videos that form a
#: single show"* — rather than derived from yt-dlp's code, so an upstream addition shows up as a
#: fixture disagreeing with this list instead of as a playlist silently reported as one item.
#: `YoutubeDL.process_ie_result()` dispatches both through its playlist processor.
MULTI_ITEM_TYPES: Final[frozenset[str]] = frozenset({"playlist", "multi_video"})


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


#: The one per-format value of `has_drm` that does **not** mean DRM (`T-057`).
#:
#: yt-dlp uses three states, not two: `True`, absent, and `'maybe'` — the last for a format it
#: suspects but has not established. It deliberately keeps those downloadable
#: (`YoutubeDL.py:2933` at the pin) and excludes them from `_has_drm`. Python disagrees by
#: default, because a non-empty string is truthy, which is how this adapter came to read a set of
#: `'maybe'` formats as protected and refuse an item yt-dlp would have downloaded.
UNDECIDED_DRM: Final = "maybe"


def format_has_drm(entry: Mapping[str, Any]) -> bool:
    """Whether one format is DRM-protected, by yt-dlp's own three-state rule."""
    flag = entry.get("has_drm")
    return bool(flag) and flag != UNDECIDED_DRM


def has_drm(info: Mapping[str, Any]) -> bool:
    """Whether yt-dlp reports this item as DRM-protected (`REQ-EXCL-001`, `SEC-001`).

    Reads `_has_drm`, which `YoutubeDL` sets, and falls back to the per-format `has_drm` flags.
    Both are structured fields. **No message text is consulted**, and no attempt is made to
    find a non-DRM route — this project does not work around DRM and offering to retry would
    imply it might.

    **The fallback computes yt-dlp's rule, and used to compute a different one** (`T-057`). Its
    two divergences were found by reading `YoutubeDL.process_video_result` rather than by a
    failing test, which is the argument for the canary that now sits beside this in
    `tests/unit/test_ytdlp_adapter.py`:

    - It treated `'maybe'` as DRM, because the string is truthy. That refuses an item yt-dlp
      would download — fail-safe in direction, so never a `SEC-001` breach, but a user told
      something is protected when it is not.
    - It required **every** format to be flagged, where yt-dlp requires **any**. That mattered
      more than it looks: `_has_drm` is `any`, and it is what the primary branch above reads, so
      the two branches of this one function disagreed about a mixed item.

    Aligning on `any` is also the answer to what a mixed item *should* mean here. yt-dlp reports
    it as having DRM and then downloads the unprotected formats; this project does not go looking
    for a non-DRM route, so a flagged item is refused whichever branch answers.
    """
    if info.get("_has_drm"):
        return True
    return any(format_has_drm(entry) for entry in info.get("formats") or ())


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

    **Playlists are projected as playlists** (`REQ-002`, `T012-R6`). `_type` is yt-dlp's own
    structured answer to "is this one thing or many", so the distinction is read from it rather
    than guessed from the presence of `entries` — an extractor may supply an empty `entries` for
    a playlist it could not enumerate, and that is still a playlist.

    **Both of yt-dlp's multi-item types count** (`T018-R2`). Its extractor contract declares
    `"playlist"` *and* `"multi_video"` — the second for parts of one work, such as a film split
    across files — and `playlist_result(multi_video=True)` produces it. Reading only `"playlist"`
    reported a real multi-item result as a single item, which is the distinction `REQ-002`
    exists to make. They are deliberately projected the same: `REQ-002` asks one question, and
    inventing a third state the requirement does not name would push the choice onto every
    reader.

    **The entries are projected flatly** (`T-137`). This used to project none of them, and said
    why: Phase 1 downloaded one item and projecting every entry would make a probe cost one
    extraction per item. Phase 3 needs them, so `probe_options` asks yt-dlp for a *flat* playlist
    — an address and a name per entry, no extraction — and `PlaylistEntry` is deliberately shaped
    to hold exactly that much. The cost the old comment refused to pay is still refused; what
    changed is that yt-dlp can be asked not to charge it.

    **`entries` and `entry_count` remain different facts.** The count is what the site reports;
    this is what this extraction materialised. A paginated playlist can give fewer entries than
    its count, and `_entry_count` already keeps them apart — see its own note.
    """
    url = str(info.get("webpage_url") or info.get("original_url") or info.get("url") or "")
    title = str(info.get("title") or "").strip() or url
    formats = tuple(
        project_format(entry) for entry in (info.get("formats") or ()) if entry.get("format_id")
    )
    is_playlist = info.get("_type") in MULTI_ITEM_TYPES
    return MediaInfo(
        url=url,
        title=title,
        formats=formats,
        duration_seconds=_as_optional_float(info.get("duration")),
        uploader=_as_optional_str(info.get("uploader")),
        thumbnail_url=_as_optional_str(info.get("thumbnail")),
        is_live=bool(info.get("is_live")),
        is_playlist=is_playlist,
        entry_count=_entry_count(info) if is_playlist else None,
        entries=_entries(info) if is_playlist else (),
    )


def _entries(info: Mapping[str, Any]) -> tuple[PlaylistEntry, ...]:
    """The playlist's items, projected flatly and in order (`T-137`).

    **A generator is not consumed.** A lazily paginated playlist supplies one, and walking it here
    would fetch the whole playlist during a probe — the cost `project_media` has always refused.
    `_entry_count` makes the same refusal for the same reason; this is the pair of it.

    An entry with no usable address is **dropped rather than carried**: yt-dlp emits `None`
    placeholders for items it could not read — a deleted or private video keeps its slot in the
    list — and a job pointing at nothing would fail at download time with nothing useful to say.
    The count still reports the full playlist, so the group knows it is short.
    """
    entries = info.get("entries")
    if isinstance(entries, str | bytes) or not isinstance(entries, Sequence):
        return ()
    projected: list[PlaylistEntry] = []
    # **`item`, not `entry`.** `tests/unit/test_fixtures.py` derives what this module reads by
    # walking its AST for `<name>.get("key")`, and `entry` is its name for a *format* — so reading
    # a playlist entry through a variable called `entry` reported these keys as ones the adapter
    # reads off a format, which is a different allowlist and a different fixture shape.
    for item in entries:
        if not isinstance(item, Mapping):
            continue
        # **A public URL first, and `url` last** (`T137-R1`). yt-dlp resolves a flat entry
        # internally as the pair `url` + `ie_key`, and a number of extractors put only an
        # extractor-local id in `url` — `abc123`, not an address. A durable job carries neither the
        # key nor yt-dlp's routing table, so a later worker handed that id has nothing to open. The
        # order was the other way round, which worked on every literal fixture and would have
        # failed on the extractors that need it most.
        url = str(item.get("webpage_url") or item.get("original_url") or item.get("url") or "")
        if not url:
            continue
        title = str(item.get("title") or "").strip() or url
        projected.append(
            PlaylistEntry(
                url=url,
                title=title,
                duration_seconds=_as_optional_float(item.get("duration")),
                thumbnail_url=_entry_thumbnail(item),
            )
        )
    return tuple(projected)


def _entry_count(info: Mapping[str, Any]) -> int | None:
    """How many items a playlist holds, or `None` when the extractor did not say.

    `playlist_count` is preferred over `len(entries)` because they are different facts: the
    count is what the site reports, while `entries` is what this extraction happened to
    materialise — flat extraction, a page limit or a lazy generator can all make the second
    smaller. Reporting the second as the total would understate a playlist and do it silently.
    """
    counted = _as_optional_int(info.get("playlist_count"))
    if counted is not None:
        return counted
    entries = info.get("entries")
    # `str` and `bytes` are `Sequence`s, and a malformed `entries` of either would have been
    # "counted" as its number of characters (`T018-R2`). A generator — which is what a lazily
    # paginated playlist supplies — has no length at all and is not counted rather than being
    # consumed, because consuming it here would fetch the whole playlist during a probe.
    if isinstance(entries, str | bytes) or not isinstance(entries, Sequence):
        return None
    return len(entries)


def _entry_thumbnail(item: Mapping[str, Any]) -> str | None:
    """A flat playlist entry's picture, from either shape yt-dlp uses (`T-137`, corrected).

    **A flat extraction rarely carries `thumbnail`.** It carries `thumbnails` — a list, worst
    first — and reading only the singular is why every entry of the maintainer's playlist drew the
    derived tile while a directly pasted URL drew its picture. The full extraction a single video
    gets does supply `thumbnail`, which is why this looked like it worked.

    The **last** entry of the list, because yt-dlp orders thumbnails by increasing preference; a
    row is 38px wide at most and the store scales, so the better source costs nothing to prefer.
    """
    single = _as_optional_str(item.get("thumbnail"))
    if single:
        return single
    listed = item.get("thumbnails")
    if isinstance(listed, str | bytes) or not isinstance(listed, Sequence):
        return None
    for candidate in reversed(listed):
        if not isinstance(candidate, Mapping):
            continue
        url = _as_optional_str(candidate.get("url"))
        if url:
            return url
    return None


def build_options(
    request: DownloadRequest,
    output_template: str,
    *,
    probe_only: bool = False,
    progress_hooks: Sequence[Any] = (),
    postprocessor_hooks: Sequence[Any] = (),
    ffmpeg_location: Path | None = None,
    overwrites: bool | None = None,
    logger: Any = None,
) -> dict[str, Any]:
    """Build the yt-dlp options dict for one session.

    `output_template` is passed in already joined to the target directory by `worker.py`, which
    is also what runs the result through `T-034`'s containment check. Rendering uses yt-dlp's
    own template mechanism (`ARCHITECTURE.md` §9) — this module never interpolates a title into
    a path itself.

    Deliberately quiet and non-interactive: a worker has no console and no user. `noprogress`
    is set because progress reaches the GUI through `progress_hooks`, not stdout.

    **`logger` changes what `quiet` and `no_warnings` mean** (`T-084`). Measured against yt-dlp
    2026.07.04: `to_screen` calls `logger.debug` and returns *before* consulting `quiet`, and
    `report_warning` consults `logger` before `no_warnings`. Both flags stay because they are
    still correct when no logger is passed — a probe run by a test, for instance — but with one
    present they suppress nothing. `core.logging.YtdlpLog` is what this receives.
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

    if logger is not None:
        # `REQ-019`: without this, yt-dlp's diagnostics go to a console the worker does not have
        # and are lost. `verbose` is deliberately *not* set alongside it — see `YtdlpLog`.
        options["logger"] = logger

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
    if overwrites is not None:
        # `T-046`. Only ever `True`, and only from the download session, which has just claimed
        # this exact path with `O_CREAT | O_EXCL`. yt-dlp treats a file at the target as an
        # already-completed download and writes nothing; the zero-byte reservation is that file.
        # Nothing else can be there, because anything pre-existing failed the exclusive create
        # and moved the reservation to the next candidate.
        options["overwrites"] = overwrites
    if ffmpeg_location is not None:
        # `OPS-001`: the worker resolves ffmpeg and gates on it, but yt-dlp does its own lookup
        # and would silently use a different binary — or none — without being told.
        options["ffmpeg_location"] = str(ffmpeg_location)

    if probe_only:
        options["skip_download"] = True
        # **A playlist is enumerated flatly** (`T-137`). Without this yt-dlp extracts every entry
        # in full to answer "what is this URL", which makes probing a sixteen-item playlist
        # sixteen extractions — the cost `project_media` refused to pay when it declined to
        # project entries at all. `in_playlist` gives each entry an address, a title and a
        # duration and stops there, which is exactly what `PlaylistEntry` is shaped to hold.
        #
        # **Probe only.** A download must extract its item properly; this would leave it with a
        # stub and no formats to choose from.
        options["extract_flat"] = "in_playlist"
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
