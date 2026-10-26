"""Builds yt-dlp options from a DownloadRequest and projects info dicts into core models.

Together with `worker.py` this confines yt-dlp churn to two modules (`NFR-008`). Nothing else
in the codebase may `import yt_dlp` (`ARCHITECTURE.md` §6, enforced by `T-005`'s layering test).

Pure translation: no process handling, no I/O, no network. Everything here is a function from
yt-dlp's vocabulary to this project's, or back. That is what makes it testable against recorded
fixtures rather than against a live site (`docs/project/TESTING.md` §5, §6).

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

import codecs
import contextlib
import contextvars
import functools
import importlib
import json
import logging
import os
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from optparse import OptParseError
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

from yt_dlp.networking.exceptions import HTTPError, TransportError
from yt_dlp.utils import (
    OUTTMPL_TYPES,
    ContentTooShortError,
    DateRange,
    DownloadCancelled,
    DownloadError,
    ExtractorError,
    GeoRestrictedError,
    PostProcessingError,
    ThrottledDownload,
    UnsupportedError,
    download_range_func,
)

from tracks_and_trails.core.errors import TRANSIENT_CONTEXT_KEY, ErrorKind, FailureDetail
from tracks_and_trails.core.format_sort import sort_items
from tracks_and_trails.core.models import (
    MERGE_CONTAINERS,
    DownloadRequest,
    FormatCheck,
    FormatInfo,
    KeptThumbnails,
    MediaInfo,
    MediaKind,
    PlaylistEntry,
    parse_browser_specification,
)
from tracks_and_trails.core.paths import APP_SLUG
from tracks_and_trails.core.sections import FROM_URL, parsed_ranges, sectioned_stem, writes_several
from tracks_and_trails.downloader.option_table import OPTION_KEYS, POSTPROCESSOR_ORDER

#: This module's own log name, under the application's tree so `configure_logging`'s redacting
#: handler formats it (`T-038`, `REQ-026`). Named for the module rather than shared with the
#: worker's, so a line about a projection is not read as a line about a download.
_LOG: Final = logging.getLogger(f"{APP_SLUG}.adapter")


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


@contextlib.contextmanager
def ffmpeg_for_its_downloader(ytdlp: Any, location: Path | None) -> Iterator[None]:
    """Tell yt-dlp's ffmpeg **downloader** where ffmpeg is, as its command line does (`T-252`).

    **The option reaches the post-processors and not the downloader's check.** Downloading a
    section is ffmpeg's work, and `process_info` first asks `FFmpegFD.available()`, which builds a
    post-processor with no `YoutubeDL` and so reads only a context variable. yt-dlp's command line
    sets that variable from `--ffmpeg-location`, and its library never does, so with ffmpeg found
    anywhere but `PATH` — the Windows installer's bundled copy, a location set in Settings — every
    section aborted: *"You have requested downloading the video partially, but ffmpeg is not
    installed"*. Measured at 2026.08.19 with `PATH` emptied, and fixed by setting it the same way.

    Reset on exit. A yt-dlp without the variable, or no location, changes nothing.
    """
    postprocessor = getattr(getattr(ytdlp, "postprocessor", None), "FFmpegPostProcessor", None)
    variable = getattr(postprocessor, "_ffmpeg_location", None)
    if location is None or not isinstance(variable, contextvars.ContextVar):
        yield
        return
    token = variable.set(str(location))
    try:
        yield
    finally:
        variable.reset(token)


@contextlib.contextmanager
def retries_given_up(ytdlp: Any) -> Iterator[list[BaseException]]:
    """Collect the error each fatal retry loop gives up on, for as long as this lasts (`T-364`).

    **yt-dlp reports giving up without the error it gave up on.** A downloader's retry loop calls
    `report_retry` once its count is spent, after the `except` that caught the error has ended,
    and `report_error` raises a `DownloadError` whose `exc_info` is empty. So a fragment whose
    server answered 503 eleven times reached `classify_exception` with nothing to classify, and
    failed as `EXTRACTOR_ERROR`, which the queue never retries by itself: the staging that
    `skip_unavailable_fragments=False` keeps for the resume was never resumed. This wraps
    `FileDownloader.report_retry`, every downloader's, to keep the error of each **fatal** give-up;
    a fragment the user chose to skip is not fatal and is not kept.

    Restored on exit, and installed only around a download in a worker process, as
    `ffmpeg_progress` is. A yt-dlp without the method yields an empty list and changes nothing.
    """
    try:
        module = importlib.import_module(f"{ytdlp.__name__}.downloader.common")
    except ImportError:
        yield []
        return
    downloader: Any = getattr(module, "FileDownloader", None)
    original: Any = getattr(downloader, "report_retry", None)
    if not callable(original):
        yield []
        return
    given_up: list[BaseException] = []

    def report_retry(
        self: Any, err: Any, count: int, retries: int, *args: Any, **kwargs: Any
    ) -> Any:
        # yt-dlp's signature at 2026.08.19: `(err, count, retries, frag_index, fatal=True)`.
        fatal = kwargs.get("fatal", args[1] if len(args) > 1 else True)
        if count > retries and fatal and isinstance(err, BaseException):
            given_up.append(err)
        return original(self, err, count, retries, *args, **kwargs)

    downloader.report_retry = report_retry
    try:
        yield given_up
    finally:
        downloader.report_retry = original


def attribute_given_up(error: BaseException, given_up: Sequence[BaseException]) -> None:
    """Give yt-dlp's report of a spent retry count the error it gave up on (`T-364`).

    Only for the report that came without one, which is the shape `retries_given_up` explains; the
    error is put where yt-dlp keeps a cause, so `classify_exception` decides by its status as for
    any other failure. **The words stay yt-dlp's** (`NFR-006`): only the classification gains.
    """
    if given_up and isinstance(error, DownloadError) and unwrap(error) is error:
        cause = given_up[-1]
        # yt-dlp ships no types, so the narrowing above cannot show mypy `exc_info`.
        report: Any = error
        report.exc_info = (type(cause), cause, cause.__traceback__)


def default_retries() -> int:
    """How many times a transfer retries when nobody chose a count: yt-dlp's command line's own.

    What `build_options` sends then (`T-364`), read at the pin, for the Settings screen to show.
    """
    return int(_command_line_defaults()["retries"])


def connection_defaults() -> Mapping[str, float]:
    """What `T-252`'s four settings are when nobody chose, read at the pin, for the Settings screen.

    The command line's own for the two retry counts and the pieces fetched at once, which the
    library reads the same way when the key is absent. The timeout is the networking layer's,
    since the command line leaves it unset. Keyed by `NetworkOptions`' field names.
    """
    from yt_dlp.networking.common import DEFAULT_TIMEOUT

    defaults = _command_line_defaults()
    return MappingProxyType(
        {
            "fragment_retries": int(defaults["fragment_retries"]),
            "extractor_retries": int(defaults["extractor_retries"]),
            "socket_timeout": float(DEFAULT_TIMEOUT),
            "concurrent_fragments": int(defaults["concurrent_fragment_downloads"]),
        }
    )


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
    transient = ((TRANSIENT_CONTEXT_KEY, "yes"),)

    # Before the type table: `HTTPError`'s consequence lives in its status, not its class.
    if isinstance(cause, HTTPError):
        # **A 403 may pass** (maintainer's report, 2026-09-13): YouTube returns one now and then
        # for a read that works a moment later. Still `EXTRACTOR_ERROR` (`_http_status_kind` says
        # why it is not auth), but marked, so a failed read is tried again.
        return FailureDetail(
            kind=_http_status_kind(cause.status),
            message=message,
            context=transient if cause.status == 403 else (),
        )

    for exception_type, kind in _EXCEPTION_MAPPING:
        if isinstance(cause, exception_type):
            # **An extractor that did not expect this may succeed next time.** yt-dlp sets
            # `expected` on the conditions it understands and reports to the user (a private
            # video, a removed one, a sign-in wall) and leaves it unset when extraction itself
            # went wrong.
            unexpected = (
                kind is ErrorKind.EXTRACTOR_ERROR
                and isinstance(cause, ExtractorError)
                and not getattr(cause, "expected", False)
            )
            return FailureDetail(
                kind=kind, message=message, context=transient if unexpected else ()
            )
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

    **`fps` and `tbr` are projected as floats** (`T-107`). yt-dlp reports both fractionally —
    29.97 fps and 1234.56 kbps are ordinary — so `_as_optional_float` is the coercion rather than
    `_as_optional_int`, which would round in the projection where nothing downstream can undo it.
    `REQ-003` names one bitrate column and `tbr` is the total, which is the rate that means
    something for a progressive format and an audio-only one alike; `vbr` and `abr` stay
    unprojected until something asks for them.
    """
    exact = _as_optional_int(entry.get("filesize"))
    size = exact if exact is not None else _as_optional_int(entry.get("filesize_approx"))
    return FormatInfo(
        format_id=str(entry.get("format_id") or ""),
        extension=str(entry.get("ext") or ""),
        # **A zero dimension is an absent one** (`T107-R1`). archive.org reports `height: 0` and
        # `width: 0` for audio items, and `yt-dlp -F` prints `unknown` for exactly those — so
        # projecting the zero produced a table reading `0x0` where yt-dlp reads `unknown`, which
        # the recorded-capture comparison caught. `_as_optional_int` keeps `0` because a zero
        # *count* is meaningful; a zero pixel dimension is not.
        height=_as_dimension(entry.get("height")),
        width=_as_dimension(entry.get("width")),
        filesize=size,
        # `filesize_approx` is a fallback for the number and **not** for its provenance
        # (`T107-R7`). `REQ-003` names the column "filesize/estimate"; collapsing the two showed
        # an estimate as though it had been measured.
        filesize_is_estimate=size is not None and exact is None,
        video_codec=_as_optional_codec(entry.get("vcodec")),
        audio_codec=_as_optional_codec(entry.get("acodec")),
        # **The distinction `_as_optional_codec` throws away, kept beside it** (`REQ-008`,
        # `T-108`). `'none'` is yt-dlp saying the stream is absent and a missing key is yt-dlp
        # saying nothing; both project to `video_codec=None`, which is right for a *codec name* and
        # useless for *"is there a video stream here"*. This is the only place the difference is
        # still visible, so it is the only place it can be recorded — `NFR-008` exactly.
        has_video=_as_stream_presence(entry.get("vcodec")),
        has_audio=_as_stream_presence(entry.get("acodec")),
        note=_as_optional_str(entry.get("format_note")),
        fps=_as_optional_float(entry.get("fps")),
        bitrate_kbps=_as_optional_float(entry.get("tbr")),
    )


#: How long a thumbnail reachability probe waits (`T-161`). Short because it runs inside a
#: probe the user is watching, and a slow answer is worth less than the next candidate.
_THUMBNAIL_PROBE_SECONDS: Final = 4.0


def _thumbnail_candidates(item: Mapping[str, Any]) -> list[str]:
    """Every thumbnail address yt-dlp offered, **best first** (`T-161`).

    Reversed on the way out because yt-dlp orders by *increasing* preference and every caller here
    wants the best one first.
    """
    listed = item.get("thumbnails")
    if isinstance(listed, str | bytes) or not isinstance(listed, Sequence):
        return []
    urls = [
        url
        for candidate in listed
        if isinstance(candidate, Mapping) and (url := _as_optional_str(candidate.get("url")))
    ]
    urls.reverse()
    return urls


def _url_answers(url: str) -> bool:
    """Whether `url` responds to a `HEAD` (`T-161`).

    **Any exception is "no".** A timeout, a refused connection, a redirect loop and a 404 all mean
    the same thing to the caller — this address will not produce a picture — and distinguishing
    them here would only invent failure kinds nothing acts on. `core/errors.py` classifies failures
    a *user* is told about; this one is a private choice between two addresses.

    Short timeout on purpose: this runs inside a probe the user is waiting on, and a slow answer is
    worth less than the next candidate.

    **Reaching the body means success, so there is no status arithmetic here.** This first
    read `200 <= answer.status < 300`, and a mutation to `return True` survived: `urlopen`
    raises `HTTPError` — a subclass of `URLError` — for every 4xx and 5xx, and it follows
    redirects, so a 404 is caught below and the comparison could never see one. It was a
    condition that could not fail, which reads as a check and is not one. Deleted rather than
    left as reassurance.
    """
    import urllib.error
    import urllib.request

    request = urllib.request.Request(url, method="HEAD")  # noqa: S310 — http(s) from yt-dlp
    try:
        with urllib.request.urlopen(request, timeout=_THUMBNAIL_PROBE_SECONDS):  # noqa: S310
            return True
    except urllib.error.URLError, OSError, ValueError:
        return False


def _upload_date(value: object) -> str | None:
    """yt-dlp's `upload_date`, kept only in its documented `YYYYMMDD` shape; anything else is none.

    **Not trusted to be well formed**, for `_as_optional_str`'s reason: an extractor that put a
    timestamp or a free-text date here would otherwise refuse the whole probe at `MediaInfo`.
    """
    text = _as_optional_str(value)
    return text if text is not None and len(text) == 8 and text.isdigit() else None


def project_media(
    info: Mapping[str, Any], *, reachable: Callable[[str], bool] = _url_answers
) -> MediaInfo:
    """Project a yt-dlp `info_dict` into a declared `MediaInfo`.

    **This is the boundary `ARC-002` exists to protect.** Past this point the raw dict does not
    travel: `downloader/protocol.py` refuses to carry one, and `core/models.py` refuses to hold
    a list of them.

    **`reachable` is threaded from here rather than defaulted deeper** (`T-161`). Choosing a
    thumbnail now asks the network whether an address answers, and a default buried in a private
    helper is one a caller cannot replace — so every unit test projecting a two-candidate list
    would make real DNS lookups and pass by happening to fail fast. A seam that stops short of the
    boundary is not a seam.

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
        upload_date=_upload_date(info.get("upload_date")),
        # The *ID*, *Channel* and *Site* naming fields (`UX-014`). `capture.py` commits a
        # placeholder for `id`, not the real one, so reading it does not put video ids in fixtures.
        media_id=_as_optional_str(info.get("id")),
        channel=_as_optional_str(info.get("channel")),
        site=_as_optional_str(info.get("extractor_key")),
        # **Both shapes, through the same helper the entries use** (`T-153`). A playlist is
        # probed with `extract_flat`, so its *top level* is the same flat dict its entries are:
        # `thumbnails`, a list, and no singular `thumbnail`. Reading only the singular here is why
        # a playlist drew the derived tile while every one of its entries drew a picture — the
        # `T-137` correction reached the children and not the parent.
        thumbnail_url=_entry_thumbnail(info, reachable=reachable),
        is_live=bool(info.get("is_live")),
        is_playlist=is_playlist,
        entry_count=_entry_count(info) if is_playlist else None,
        entries=_entries(info) if is_playlist else (),
        slot_count=_slot_count(info) if is_playlist else None,
        subtitle_languages=_subtitle_languages(info),
        caption_languages=_caption_languages(info),
    )


def _subtitle_languages(info: Mapping[str, Any]) -> tuple[str, ...]:
    """The languages this source publishes subtitles in (`REQ-010`, `P-17`, `T-109`).

    **The keys of yt-dlp's `subtitles` map, and nothing under them.** Each value is a list of
    downloadable variants — url, ext, name — and none of it reaches `MediaInfo`, which needs a
    language list to offer and not a download plan. `writesubtitles` and `subtitleslangs` are how
    a language is asked for; yt-dlp picks the variant.

    **`automatic_captions` is deliberately not merged in.** It is a separate map fetched under a
    separate option (`writeautomaticsub`), so a language offered from it here would be one asked
    for and never received unless that option is on, producing a file with no subtitles and no
    error — the `T-075` shape, a control that appears to do nothing. `_caption_languages` reads
    it apart, and the editor offers it behind the option (`T-251`).

    Order is the extractor's own. Sorting would look tidier and would put `ar` above `en` for an
    English source that also publishes Arabic, which is not the order the site thought its
    languages went in.

    A language with an empty variant list is still kept: the extractor said the language exists,
    and yt-dlp is the thing that decides at download time whether it can be fetched.
    """
    subtitles = info.get("subtitles")
    if not isinstance(subtitles, Mapping):
        return ()
    return tuple(str(language) for language in subtitles if str(language))


def _caption_languages(info: Mapping[str, Any]) -> tuple[str, ...]:
    """The languages this source offers only as automatic captions (`T-251`), in its own order.

    **The caption map's keys less the subtitle map's.** yt-dlp takes a language's subtitles over
    its caption whenever both exist and both are asked for (`YoutubeDL.process_subtitles`), so a
    language in both is offered once, as subtitles. Measured 2026-10-14 on a YouTube video with
    five subtitle languages: the caption map held 160 keys — those five again, `en-orig`, and
    machine translations into nearly every other language YouTube has.
    """
    captions = info.get("automatic_captions")
    if not isinstance(captions, Mapping):
        return ()
    subtitled = set(_subtitle_languages(info))
    return tuple(
        str(language) for language in captions if str(language) and str(language) not in subtitled
    )


def _entries(info: Mapping[str, Any]) -> tuple[PlaylistEntry, ...]:
    """The playlist's items, projected flatly and in order (`T-137`).

    **A generator is not consumed.** A lazily paginated playlist supplies one, and walking it here
    would fetch the whole playlist during a probe — the cost `project_media` has always refused.
    `_entry_count` makes the same refusal for the same reason; this is the pair of it.

    An entry yt-dlp could not read is **dropped rather than carried**: a deleted or private video
    keeps its slot in the list, and a job pointing at nothing would fail at download time with
    nothing useful to say. The count still reports the full playlist, so the group knows it is
    short.

    **The marker is the missing title, not a missing address** (`T-281`). This said the same thing
    and tested `url`, which a YouTube placeholder still has — yt-dlp composes `watch?v=<id>` from
    the id it holds even for an item it could read nothing else about. Measured against a real
    playlist on 2026-08-27: the extractor logged *"2 unavailable videos are hidden"* and the two
    entries arrived with `id` and `url` intact and `title`, `duration`, `channel` and `uploader`
    all `None`. The old guard passed them through, `title or url` put the raw address in the title
    column, and both rows reached the queue to fail there — which is the outcome this paragraph
    already claimed to prevent. The address check stays, because an entry with neither is no more
    usable than one without a title.

    **A title of `[Private video]` or `[Deleted video]` is *not* matched**, and that is a decision
    rather than an omission. Those spellings come back from paths that read the item well enough to
    name it, and matching them means recognising user-supplied titles by their text — the
    recogniser problem `T-018` refused for query parameters, for the same reason: a real video may
    be called anything. If such an entry is ever seen reaching the queue, it needs its own evidence
    and its own decision, not a string added here.

    **Every drop is logged, by position and reason rather than by identity**, and the count is out
    of what the playlist offered. `T281-R1` found the first spelling recording only the placeholder
    branch: an item that was not a mapping, or a mapping with no usable address, was discarded in
    silence, and the denominator was the two surviving lists added together rather than the input's
    own length. A mixed four-entry list therefore reported *"dropped 1 of 2"* while three of four
    went. Reasons are three fixed words chosen here, not text read off the entry, so they say why a
    slot went without naming what was in it.

    The line is a smaller one than it first looks like it should be. Two other spellings were tried
    and both are refused by a decision this function does not get to overturn:

    - **The entry's URL** is useless. `RedactingFormatter` strips every URL's query string
      (`T-018`, allowlist empty by design) and a YouTube video id lives in the query — measured,
      `https://www.youtube.com/watch?v=Zg0WtgC80lY` redacts to `https://www.youtube.com/watch`
    - **The entry's `id`** survives redaction and is what a human would want. The projection reads
      it since `UX-014` (the *ID* naming field), and `capture.py` commits a placeholder in its place
      so no real id reaches a fixture — but a log line naming it is still a separate decision,
      not made here

    So the line names the playlist and which positions went. `T-281` records the id as an available
    upgrade if the fixture policy is ever widened deliberately.
    """
    entries = info.get("entries")
    if isinstance(entries, str | bytes) or not isinstance(entries, Sequence):
        return ()
    projected: list[PlaylistEntry] = []
    dropped: list[str] = []
    # **The denominator is what the playlist offered, not what the two lists add up to.**
    # `len(dropped) + len(projected)` was the arithmetic, and it counted only the entries that
    # reached the title guard — so a list of four holding a `None`, an addressless mapping, a
    # titleless address and one good entry projected one and reported "dropped 1 of 2" (`T281-R1`).
    # Counting here rather than with `len(entries)` keeps the number equal to what was actually
    # enumerated, which is the fact the line claims. With every branch below recording its slot the
    # two spellings now agree; this one keeps agreeing if a later branch forgets to.
    offered = 0
    # **`item`, not `entry`.** `tests/unit/test_fixtures.py` derives what this module reads by
    # walking its AST for `<name>.get("key")`, and `entry` is its name for a *format* — so reading
    # a playlist entry through a variable called `entry` reported these keys as ones the adapter
    # reads off a format, which is a different allowlist and a different fixture shape.
    for position, item in enumerate(entries, start=1):
        offered = position
        if not isinstance(item, Mapping):
            # A deleted or private item arrives as `None` in yt-dlp's list. It is a drop like any
            # other and used to leave no trace at all.
            dropped.append(f"position {position} (not an entry)")
            continue
        # **A public URL first, and `url` last** (`T137-R1`). yt-dlp resolves a flat entry
        # internally as the pair `url` + `ie_key`, and a number of extractors put only an
        # extractor-local id in `url` — `abc123`, not an address. A durable job carries neither the
        # key nor yt-dlp's routing table, so a later worker handed that id has nothing to open. The
        # order was the other way round, which worked on every literal fixture and would have
        # failed on the extractors that need it most.
        url = str(item.get("webpage_url") or item.get("original_url") or item.get("url") or "")
        if not url:
            dropped.append(f"position {position} (no address)")
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            # The placeholder case above. `position` counts every item the playlist offered,
            # including the dropped ones, so it is the number the extractor's own "item N of M"
            # lines use rather than an index into what survived.
            dropped.append(f"position {position} (no title)")
            continue
        projected.append(
            PlaylistEntry(
                url=url,
                title=title,
                # The slot, not the place among survivors: `-I` counts slots (`T247-R1`).
                position=position,
                duration_seconds=_as_optional_float(item.get("duration")),
                thumbnail_url=_entry_thumbnail(item),
                media_id=_as_optional_str(item.get("id")),
                channel=_as_optional_str(item.get("channel")),
            )
        )
    if dropped:
        # **The playlist first, so the line has a subject.** A count on its own is unreadable in a
        # log holding several probes.
        _LOG.info(
            "playlist %r: dropped %d of %d entries yt-dlp could not read, at %s",
            str(info.get("title") or "?"),
            len(dropped),
            offered,
            ", ".join(dropped),
        )
    return tuple(projected)


def _slot_count(info: Mapping[str, Any]) -> int | None:
    """How many slots the extraction enumerated, the ones `_entries` drops included (`T247-R1`).

    **The length yt-dlp's `PlaylistEntries` counts a negative `-I` back from**, measured at
    2026.08.19: a `None` slot is still a slot there.

    **`0` and `None` are different answers** (`T247-R1`, second round). An empty list is an
    enumeration that found nothing, and so is a list whose every slot `_entries` drops; `None` is
    no enumeration at all — a generator `_entries` refuses to consume, or no list — which a
    playlist downloads as its own URL (`T-137`). Collapsing the two queued an enumerated, unreadable
    playlist as one job for its whole URL, so the preset's `-I` never applied.
    """
    entries = info.get("entries")
    if isinstance(entries, str | bytes) or not isinstance(entries, Sequence):
        return None
    return len(entries)


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


def _entry_thumbnail(
    item: Mapping[str, Any], *, reachable: Callable[[str], bool] | None = None
) -> str | None:
    """A picture from either shape yt-dlp uses (`T-137`, corrected; `T-153`, widened).

    **Named for entries and used by the playlist too.** The name is kept because that is where the
    shape was found, and the reasoning below is about flat extractions rather than about children:
    a playlist probed with `extract_flat` carries `thumbnails` at its own level as well.

    **A flat extraction rarely carries `thumbnail`.** It carries `thumbnails` — a list, worst
    first — and reading only the singular is why every entry of the maintainer's playlist drew the
    derived tile while a directly pasted URL drew its picture. The full extraction a single video
    gets does supply `thumbnail`, which is why this looked like it worked.

    **The best candidate that actually resolves** (`T-161`, `P2EXIT-R12`). This took the *last*
    entry, because yt-dlp orders thumbnails by increasing preference — and yt-dlp lists addresses
    it has **not** verified. Measured on the maintainer's playlist:

    ```
    180x180    200   .../mqdefault.jpg?sqp=...      signed, resolved
    640x640    200   .../sddefault.jpg?sqp=...      signed, resolved
    1200x1200  404   .../maxresdefault.jpg          bare path, does not exist
    ```

    So *"the last one"* selected an address that 404s, and `T-119`'s give-up-on-failure rule made
    the resulting blank permanent. `T-153`'s accepted criterion is that the row **shows** a
    picture; selecting an address is not that, which is what `P2EXIT-R12` found its regression
    unable to prove.

    **Asking is the only thing that answers it.** No property of the list separates a resolved
    address from a guessed one without encoding one site's habits here — the query signature is
    YouTube's, not the web's. So the candidates are walked best-first and the first that responds
    is taken. **In the worker process, where network calls already live**, rather than in the
    store: the store fetches on paint, so a fallback there would spend the user's scroll on
    retries and would still have nothing durable to hand a restart.

    **`thumbnail` is trusted without asking.** It is yt-dlp's own resolved pick from a full
    extraction and it has always worked; a request to confirm it would be spent on every ordinary
    download to fix a case that only arises for flat playlist extractions.

    A single candidate is returned unasked — there is nothing to choose between, and a probe could
    only turn a picture that might work into no picture at all. If nothing answers, the best guess
    is returned anyway, so this is never worse than what it replaced.

    **`reachable` is `None` by default, and only the playlist *parent* passes one** (`T161-R1`).
    This first defaulted to the live probe and was threaded through `_entries`, so projecting a
    sixteen-entry playlist made a HEAD walk **per entry** — against this task's own criterion
    *"no probe-time network request per entry"*, and against its rejected-options list, which
    already recorded per-entry verification as *"correct and unacceptable"*. At four seconds a
    candidate the worst case grows with entries times candidates and can hold an add dialog for
    minutes with nothing the user can do about it. **An entry's picture is projected exactly as it
    was before `T-161`:** best candidate, no request. `T-153`'s criterion is about the parent, and
    that is the only row this may spend a request on.
    """
    single = _as_optional_str(item.get("thumbnail"))
    if single:
        return single
    candidates = _thumbnail_candidates(item)
    if reachable is None or len(candidates) <= 1:
        return candidates[0] if candidates else None
    for url in candidates:
        if reachable(url):
            return url
    return candidates[0]


def _in_dependency_order(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`specs` in the order yt-dlp's own builder emits them (`T184-R10`).

    The ranks are measured, not written here: `tools/ytdlp_option_table.py` runs yt-dlp over an
    argv that activates every processor this project can produce and reads the order back, so a
    release that reorders them is picked up by regenerating rather than by anyone noticing.

    A key the table does not know keeps its position relative to other unknowns and goes last —
    it can only be one yt-dlp has added since the pin, and `tests/unit/test_ytdlp_adapter.py`
    asserts that nothing this application itself emits is in that position.
    """
    return sorted(
        specs,
        key=lambda spec: POSTPROCESSOR_ORDER.get(str(spec.get("key")), len(POSTPROCESSOR_ORDER)),
    )


def _chapter_template(output_template: str) -> str:
    """The media's own name, plus the chapter's number and title (`T184-R13`).

    `output_template` is the literal, already-contained path the worker validated, so taking its
    stem keeps every chapter in the same directory by construction rather than by a check.

    **The stem is the file name's, not the path's.** The first version split the whole path on its
    last dot, so `/home/u/my.dir/staging/clip` became `/home/u/my` plus the chapter suffix,
    written beside `my.dir` rather than inside staging. `os.path.split` finds the file name on
    either platform's separator. Only that name is replaced, and every character before it is
    kept exactly as the worker validated it.
    """
    name = os.path.split(output_template)[1]
    stem, dot, _ = name.rpartition(".")
    chapter = f"{stem if dot and stem else name}.%(section_number)03d %(section_title)s.%(ext)s"
    return output_template[: len(output_template) - len(name)] + chapter


class NumberedSections(download_range_func):  # type: ignore[misc]
    """`--download-sections`, with every section numbered in the order yt-dlp yields them (`T-252`).

    **yt-dlp numbers only a chapter**: its `section_number` is the matched chapter's index, and a
    time range has none, so two ranges named by the number would share one name and the second
    would overwrite the first, which is what the options field did with two ranges until this task
    (measured 2026-10-14). Each yielded section is numbered from 1 instead: chapter matches, then
    ranges, then the address's own range, which is yt-dlp's order.

    **Its equality is yt-dlp's own**, which compares the patterns and the ranges, so the typed field
    is held to `parse_options` by comparing the two.

    **It gives yt-dlp the item's length where the site gave none** (`T252-R1`, ruled 2026-10-25).
    yt-dlp resolves a range counted from the end, and clips one that runs past it, by the item's
    `duration`, and a direct link has none: `*-2-inf` on one came back as the whole file. The worker
    reads the length with ffprobe first and sets `length`, which is written into the item here,
    before yt-dlp reads it, and only where the item has none.
    """

    length: float | None = None

    def __call__(self, info_dict: Any, ydl: Any) -> Iterator[dict[str, Any]]:
        if self.length is not None and not info_dict.get("duration"):
            info_dict["duration"] = self.length
        for number, section in enumerate(super().__call__(info_dict, ydl), start=1):
            yield {**section, "index": number} if section else section


def numbered_sections(sections: Sequence[str], length: float | None = None) -> NumberedSections:
    """The `download_ranges` yt-dlp's command line builds from these sections, numbered.

    Parsed by `core/sections.py`'s transcription, which the model already held each section to, so
    a section reaching here is one yt-dlp's command line accepts. `length` is the item's, read by
    the worker where the site gave none; see `NumberedSections`.
    """
    chapters = [re.compile(section) for section in sections if not section.startswith("*")]
    ranges = [
        list(span)
        for section in sections
        if section.startswith("*") and section != FROM_URL
        for span in parsed_ranges(section) or ()
    ]
    numbered = NumberedSections(chapters, ranges, FROM_URL in sections)
    numbered.length = length
    return numbered


def _section_template(output_template: str) -> str:
    """The media's own name with each section's number after the stem (`T-252`).

    `_chapter_template`'s shape: the worker's literal, contained path with only its file name's
    stem extended, so every section lands in the same directory by construction.
    """
    name = os.path.split(output_template)[1]
    stem, dot, extension = name.rpartition(".")
    numbered = (
        f"{sectioned_stem(stem, '%(section_number)s')}.{extension}"
        if dot and stem
        else sectioned_stem(name, "%(section_number)s")
    )
    return output_template[: len(output_template) - len(name)] + numbered


#: The sidecar templates kept on the base name when sections number the media (`T-252`). The
#: playlist ones are left alone, since a download here is one item, and the chapter template has its
#: own derivation.
_BASE_NAMED: Final = frozenset(
    kind for kind in OUTTMPL_TYPES if kind != "chapter" and not kind.startswith("pl_")
)


def build_options(
    request: DownloadRequest,
    output_template: str,
    *,
    probe_only: bool = False,
    progress_hooks: Sequence[Any] = (),
    postprocessor_hooks: Sequence[Any] = (),
    ffmpeg_location: Path | None = None,
    cookie_file: Path | None = None,
    overwrites: bool | None = None,
    logger: Any = None,
    section_length: float | None = None,
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

    **`section_length` is the item's length as the worker read it from the link** (`T252-R1`),
    set only where the site gave none; the sections hand it to yt-dlp (`NumberedSections`).
    """
    options: dict[str, Any] = {
        # **Every template type, because one of them is not derived from this one** (`T184-R13`).
        # Measured 2026-09-23: of yt-dlp's eleven `OUTTMPL_TYPES`, ten resolve inside the
        # directory this names — `infojson` to `clip.info.json` beside the media, and so on — but
        # **`chapter` has its own default and it is relative**, so it renders
        # `Clip - 001 First [x].mp4` against the process working directory. `--split-chapters` is
        # admitted, and once `T184-R10` stopped discarding the hatch's postprocessors it became
        # reachable: real ffmpeg wrote chapter files outside the chosen download folder.
        #
        # The chapter template is therefore pinned here, **before anything is written** rather
        # than checked afterwards, and it keeps the media's own stem so the files belong to the
        # family `claim_outputs` moves under one index (`T109-R4`).
        "outtmpl": {"default": output_template, "chapter": _chapter_template(output_template)},
        "format": request.format_selector,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        # No console, no user, no prompts. An interactive prompt in a worker is a hang.
        "no_color": True,
        "consoletitle": False,
        # **`REQ-EXCL-002` is a default, not a refusal** (`T183-R1`). `SEC-003` forbids `--xff`,
        # and refusing the *option* leaves the behaviour on: `InfoExtractor` reads
        # `get_param('geo_bypass', True)`, so an application that sets nothing gets yt-dlp's
        # automatic fake-`X-Forwarded-For` retry — the exact mechanism the exclusion names.
        #
        # **It has to be `False`, not `'never'`.** yt-dlp's *command line* carries a string and
        # converts it (`opts.geo_bypass.lower() != 'never'`) before `YoutubeDL` sees it; the
        # library parameter is a bool. `'never'` is truthy and would enable what it looks like it
        # disables. Measured against the 2026.07.04 pin.
        "geo_bypass": False,
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
    # **What yt-dlp's command line retries, when nobody chose a count** (`T-364`, ruled
    # 2026-10-15). The library reads an absent `retries` or `fragment_retries` as **zero**, where
    # the command line sends ten, so a job whose user left the setting alone gave up on the first
    # 503 of a transfer, and every fragment had no retry at all. Read from `parse_options([])`
    # rather than copied, so the number follows the pin; `test_retry_defaults.py` holds it there.
    defaults = _command_line_defaults()
    # **`is not None`, not truthiness** (`T-196`). `retries=0` is a user asking not to retry inside
    # the attempt, and the two lines above can read a zero as *unset* because a rate limit of zero
    # bytes per second is not a thing anyone means. Here it is: dropped by truthiness, "never
    # retry" would silently become the default of ten.
    options["retries"] = request.retries if request.retries is not None else defaults["retries"]
    # **The rest of the retry policy and the connection's tuning** (`T-252`), on both passes like
    # `retries`, since the probe reads the page and fetches over the same connection. A piece's
    # retries fall back to the command line's ten, as `retries` does; the other three are left out
    # while nobody chose, because the library's own reading of an absent key is the command line's
    # (three retries of the page, yt-dlp's 20-second timeout, one piece at a time), read at the pin.
    options["fragment_retries"] = (
        request.fragment_retries
        if request.fragment_retries is not None
        else defaults["fragment_retries"]
    )
    if request.extractor_retries is not None:
        options["extractor_retries"] = request.extractor_retries
    if request.socket_timeout is not None:
        options["socket_timeout"] = request.socket_timeout
    if request.concurrent_fragments is not None:
        options["concurrent_fragment_downloads"] = request.concurrent_fragments
    # **From the start, on both passes** (`T-252`): yt-dlp's live extractors offer different
    # formats for a stream fetched from its beginning, so the probe has to ask the same question.
    if request.live_from_start:
        options["live_from_start"] = True
    # **A fragment still missing after its retries fails the attempt** (`T-364`). The library skips
    # it by default and the job ended *Done* with seconds of the media gone (250 of 300 frames,
    # measured at `8b0aad6`). Failing instead keeps staging, and the job's own retry resumes it.
    # `--skip-unavailable-fragments` in the options field is merged below and wins: the one other
    # key the application and the user share, ruled as `ARC-010` rules `writethumbnail`.
    options["skip_unavailable_fragments"] = False
    # **The sort and the merge container, on both passes** (`T-250`). The probe chooses a format
    # too, to render the name the download will take, and yt-dlp picks a merged format's container
    # when it chooses it; a probe without these would preview a name the download does not write.
    # The check is the download's alone, below.
    if request.format_sort is not None:
        options["format_sort"] = list(sort_items(request.format_sort))
    merge = merge_container_for(request)
    if merge is not None:
        options["merge_output_format"] = merge
    # **The name's shape, on both passes** (`T-248`). The probe pass renders the name
    # `_validated_target` contains, so these act there, before containment. The download pass drops
    # the trim with the other `RENDER_ONLY_KEYS` below and keeps the restriction, which yt-dlp
    # applies to a field's text and never to literal text, so the path it is handed stays as
    # validated while a chapter's title in `_chapter_template` is shaped like the media's.
    options.update(shaping_options(request))
    if request.cookies_from_browser:
        # **The four-tuple yt-dlp parses, not the string the user typed** (`T197-R2`). Its
        # `_parse_browser_specification(browser_name, profile, keyring, container)` refuses an
        # unsupported browser — and `("firefox:Private",)` makes the *whole string* the browser
        # name, so every profile-bearing specification was rejected by the library after passing
        # everything here. Split in `core/`, which owns the grammar and the refusal of a profile
        # that is a path.
        options["cookiesfrombrowser"] = parse_browser_specification(request.cookies_from_browser)
    if cookie_file is not None:
        # **A parameter, not a request field** (`REQ-026`, `T-197`, `DAT-003`). The browser name
        # rides on the request because it is a per-download choice a preset can carry; the *file*
        # is a settings value handed to this session, because a cookie path this application
        # supplies may never reach the model and therefore the database.
        options["cookiefile"] = str(cookie_file)
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

    # **The escape hatch, before the probe branch and therefore on both paths** (`T-184`).
    #
    # A probe that saw different options from the download would list formats the download then
    # could not produce: `--extractor-args youtube:player_client=…` changes which formats exist,
    # and the user picks from what the probe found. So the hatch applies to both, and the
    # application's own probe keys are set below this line, where they still win.
    #
    # **Read from the request, never re-parsed here.** The parse happened where the user typed
    # it, which is what makes a malformed field fail at edit time; the worker receives the result
    # (`REQ-031`). `writethumbnail` is left for `merge_thumbnail` in the download-only tail,
    # because it is the one key the application also sets.
    hatch = hatch_options(request.extra_options, request.extra_option_argv)
    options.update({key: value for key, value in hatch.items() if key != "writethumbnail"})

    if not probe_only:
        # **Shaping acts where the name is rendered, never on the path it became** (`T-363`).
        # `_validated_target` renders the user's template on the probe pass, where these act on
        # the name, and contains the result; the download pass is then handed that path as a
        # literal. yt-dlp applies both to whatever it is handed, so here they reshaped the whole
        # absolute path: a trim of 15 turned `/home/sean/Videos/.tracks-and-trails-staging-…/
        # Vol. 2 of the set.mp4` into `/home/sean/Vide. 2 of the set.mp4`, and Windows names
        # renamed a folder called `Talks: 2026`. Both measured on `8b0aad6`.
        for key in RENDER_ONLY_KEYS:
            options.pop(key, None)

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

    # **Which items, on the download only** (`T-247`, `ARC-010` amended 2026-10-11). yt-dlp applies
    # these where it decides whether to fetch the item, so on the probe they would hide the item
    # the user is choosing a format for. Set after the hatch, so a typed value wins as `ARC-010`'s
    # precedence rule says, although admission already refuses these spellings for their control.
    #
    # **`daterange` is yt-dlp's own `DateRange`**, which is what its command line builds from
    # `--date`, `--dateafter` and `--datebefore`: an absent end is open, as the request's `None`
    # is. The request carries frozen `YYYYMMDD` days, never a relative form, and the worker ends a
    # job whose days have crossed before this is reached, since `DateRange` refuses that pair.
    # **The format check, on the download only** (`T-250`, `ARC-010` amended 2026-10-15, second):
    # checking every format of one YouTube video took 79 requests and 12.9 s against 3 to read it,
    # and the add dialog reads every URL pasted into it.
    if request.check_formats is not FormatCheck.DEFAULT:
        options["check_formats"] = FORMAT_CHECKS[request.check_formats]
    if request.min_filesize is not None:
        options["min_filesize"] = request.min_filesize
    if request.max_filesize is not None:
        options["max_filesize"] = request.max_filesize
    if request.uploaded_after is not None or request.uploaded_before is not None:
        options["daterange"] = DateRange(request.uploaded_after, request.uploaded_before)
    # **The file's date, on the download only** (`T-248`). yt-dlp dates what it writes
    # by the server's `Last-Modified` only when asked, as its command line has since 2025; a merge
    # or a conversion keeps the oldest input's date, so the finished file carries it.
    if request.use_last_modified:
        options["updatetime"] = True
    # **Which part, on the download only** (`T-252`, `ARC-010` amended 2026-10-19). yt-dlp asks for
    # the sections when it processes the item, which a probe never does, and a chapter pattern
    # that matches nothing would otherwise be reported while the user is still choosing a format.
    if request.download_sections:
        options["download_ranges"] = numbered_sections(request.download_sections, section_length)
        if writes_several(request.download_sections):
            # **One file per section, the sidecars once** (ruled 2026-10-19, question 4). The media
            # template gains each section's number, so two sections can no longer share a name;
            # every other template keeps the base name, so the description, the info JSON, the
            # subtitles and the thumbnail are written once for the item rather than per section,
            # and claimed with the sections as one family.
            options["outtmpl"] = {
                **options["outtmpl"],
                **dict.fromkeys(_BASE_NAMED, output_template),
                "default": _section_template(output_template),
            }

    if request.subtitle_languages:
        options["writesubtitles"] = True
        options["subtitleslangs"] = list(request.subtitle_languages)
        # **Subtitle depth, only where languages are chosen** (`T-251`). yt-dlp with no languages
        # named takes English, or the first it finds, so a caption flag or a format preference set
        # alone would fetch a file nobody chose. A chosen language with subtitles keeps them: the
        # caption is used only for one without, which is yt-dlp's own precedence.
        if request.automatic_captions:
            options["writeautomaticsub"] = True
        if request.subtitle_format is not None:
            options["subtitlesformat"] = request.subtitle_format

    if request.embed_thumbnail:
        # **`EmbedThumbnail` embeds a file that has to exist first** (`T-109`). yt-dlp's own
        # `get_postprocessors` sets `writethumbnail` when `--embed-thumbnail` is given, and
        # without it the postprocessor runs against a download that has no picture beside it and
        # embeds nothing. That is `T012-R5`'s defect exactly — a key accepted, and silently
        # ineffective — one option along.
        #
        # The picture is **not** kept unless the user asks: `already_have_thumbnail` follows
        # `keep_thumbnails` in the spec below, so yt-dlp deletes it after embedding otherwise.
        # `REQ-010` asks to embed a thumbnail, not to write one beside the media.
        options["writethumbnail"] = True

    # **Thumbnails kept beside the media** (`T-249`), the user's half of the union `ARC-010`'s
    # 2026-09-20 amendment rules: written when either asks, and kept when the user does.
    # `write_all_thumbnails` is yt-dlp's own key for `--write-all-thumbnails`, which sets the
    # same destination as `--write-thumbnail` on the command line and is read apart from it.
    if request.keep_thumbnails is KeptThumbnails.BEST:
        options["writethumbnail"] = True
    elif request.keep_thumbnails is KeptThumbnails.ALL:
        options["write_all_thumbnails"] = True

    # **The description and the info JSON, on the download only** (`T-249`). yt-dlp writes both
    # when it processes the item, which a probe never does; `retained_sidecars` reads these keys
    # to claim the files, and the worker strips an info JSON before it does (`DAT-003`, amended
    # 2026-10-11).
    if request.write_description:
        options["writedescription"] = True
    if request.write_info_json:
        options["writeinfojson"] = True

    # The one key the application and the user share, settled as `ARC-010`'s 2026-09-20 amendment
    # rules: written when either asks, and the user's request to keep it survives.
    merge_thumbnail(options, hatch)

    # **Composed in yt-dlp's own order** (`T184-R10`). This assignment used to replace whatever
    # the hatch produced, so `--split-chapters` reached this dictionary and was dropped. The first
    # correction appended instead, which was still wrong: `FFmpegMetadata` then ran **before**
    # `ModifyChapters`, so `--remove-chapters` wrote metadata from chapters that were removed
    # straight afterwards and the finished file had none. Grouping by `when` does not settle
    # order *within* a stage, and these two share one.
    options["postprocessors"] = _in_dependency_order(
        [
            *build_postprocessors(request, keep_thumbnail=bool(hatch.get("writethumbnail"))),
            *hatch.get("postprocessors", []),
        ]
    )
    return options


#: Each position of the format check (`T-250`) as yt-dlp's `check_formats` reads it: `selected`,
#: everything, nothing. `DEFAULT` sends no key, which leaves the check to the extractor.
FORMAT_CHECKS: Final[Mapping[FormatCheck, str | bool]] = MappingProxyType(
    {FormatCheck.SELECTED: "selected", FormatCheck.EVERY: True, FormatCheck.NEVER: False}
)


def merge_container_for(request: DownloadRequest) -> str | None:
    """The container a merge writes, by `ARC-010`'s written order (amended 2026-10-15, second).

    **Recode, then remux, then the merge container, then yt-dlp's choice.** A recode or a remux
    runs after the merge and decides the final container, so the merge container is an
    intermediate whenever either is set. **A remux into a container the merger writes merges
    straight into it**, one pass instead of two, as yt-dlp's own `-t mp4` does; a remux into one it
    cannot write, `gif` or an audio container, leaves the merge to the merge container or yt-dlp.
    A request carries a remux or a recode, never both (`_require_one_container_change`), so the
    remux is asked about alone.
    """
    if request.remux_container in MERGE_CONTAINERS:
        return request.remux_container
    return request.merge_container


def shaping_options(request: DownloadRequest) -> dict[str, Any]:
    """The keys that shape `request`'s rendered name (`T-248`).

    **One derivation for the write and the preview**, so `REQ-011`'s example cannot show a name
    the download does not take: `build_options` sends these and the preview's renderer takes them.
    """
    options: dict[str, Any] = {}
    if request.restrict_filenames:
        options["restrictfilenames"] = True
    if request.trim_filenames is not None:
        options["trim_file_name"] = request.trim_filenames
    return options


#: Every key `shaping_options` can send, which the preview sets on each render (`T-248`).
SHAPING_KEYS: Final = frozenset({"restrictfilenames", "trim_file_name"})


#: Keys that shape a file name, which act on the rendered name and never on the download's path
#: (`T-363`). yt-dlp applies them to the whole path it is handed, and the download pass is handed
#: the contained absolute path as a literal, so there they would reshape its folders.
RENDER_ONLY_KEYS: Final = frozenset({"trim_file_name", "windowsfilenames"})


#: What compiling a pattern the user typed raises (`T184-R8`, eighth round).
#:
#: `re.compile` raises `OverflowError` for a repeat count past its limit (`a{4294967296}`) and
#: `RecursionError` for nesting too deep for its parser (500 groups), neither of them `re.error`.
#: yt-dlp catches only `re.error`, so both escaped the parse of `--remove-chapters` and
#: `--download-sections` and every filter check, up through the editor. Each is decided by the
#: text alone, so it is refused like any bad value. **Nothing broader is caught**: any other
#: exception here is a defect and must still raise.
_UNCOMPILABLE: Final = (re.error, OverflowError, RecursionError)

#: What a parse of the user's options raises when yt-dlp will not take them.
_REFUSED_BY_YT_DLP: Final = (SystemExit, OptParseError, *_UNCOMPILABLE)


@contextlib.contextmanager
def process_state_kept() -> Iterator[None]:
    """Put back what parsing the user's options changes for the whole process (`T-363`).

    **Parsing is not free of effects.** yt-dlp's parser rewrites the default format order for the
    compatibility value `prefer-vp9-sort` and switches its unsafe-extension check off for
    `allow-unsafe-ext`, both on classes every later `YoutubeDL` reads. In a job's own process that
    is the option doing its work. In the GUI's, where the editor and the offer ask their questions,
    it would change every check made after it, so these two are put back. Admission refuses
    `allow-unsafe-ext` before anything is parsed when the whole line leaves it chosen, but a line
    that names it and takes it away again is admitted, and a parse of one option alone still sees
    it (`T363-R1`). So **every parse of the user's options in the GUI's process runs inside this**;
    `tests/unit/test_compat_options.py` holds the list of parses to that.
    """
    from yt_dlp.utils import FormatSorter
    from yt_dlp.utils._utils import _UnsafeExtensionError

    kept = (FormatSorter.default, _UnsafeExtensionError._enabled)
    try:
        yield
    finally:
        FormatSorter.default, _UnsafeExtensionError._enabled = kept


def unparseable(argv: Sequence[str], groups: Sequence[Sequence[str]]) -> tuple[bool, str | None]:
    """Whether yt-dlp refuses `argv` as a whole, and which option to point the user at.

    Asked by the editor, in the GUI's process, so whatever the parse changes for the whole process
    is put back (`T-363`). See `_unparseable`.
    """
    with process_state_kept():
        return _unparseable(argv, groups)


def _unparseable(argv: Sequence[str], groups: Sequence[Sequence[str]]) -> tuple[bool, str | None]:
    """Whether yt-dlp refuses `argv` as a whole, and which option to point the user at.

    **The whole ordered command line decides** (`T184-R8`). Asking about each option alone gets
    both directions wrong, and the reviewer measured both: `--dateafter 20260920 --datebefore
    20260901` is fine one at a time and contradictory together, so the seam accepted a field the
    worker would refuse; and `--fragment-retries nope --fragment-retries 7` is fine to the real
    parser, which takes the last value, while one-at-a-time refused it on the first.

    **Attribution is a second question, asked only after the first has been answered.** Once the
    whole line is known to be bad, each option is tried alone to find something to name — and if
    none of them fails alone, the answer is still *refused*, with no option named. A diagnostic
    that could change the verdict would be the same defect wearing a different hat.

    **A line that parses can still hold a value yt-dlp reads only when a job runs**, and that is
    asked next, by `_unreadable_when_it_runs`, naming the option it found.
    """
    from yt_dlp import parse_options

    try:
        parse_options(list(argv))
    except _REFUSED_BY_YT_DLP:
        pass
    else:
        culprit = _unreadable_when_it_runs(argv)
        return culprit is not None, culprit

    for group in groups:
        try:
            parse_options(list(group))
        except _REFUSED_BY_YT_DLP:
            return True, str(group[0]).partition("=")[0]
    return True, None


#: Where `match_str` splits a filter into parts: an `&` not escaped with a backslash. yt-dlp's own
#: expression, read at 2026.08.19; each part keeps its `\&`, which `match_str` unescapes itself.
_FILTER_PARTS: Final = re.compile(r"(?<!\\)&")


class _EveryFieldIsText:
    """An item whose every field is the empty string, so each comparison in a filter is made.

    Text rather than a number on purpose: a string operator on a number raises before the pattern
    is reached, and on text every operator here is defined, so the only error left is the pattern.
    """

    def get(self, key: str, default: object = None) -> str:
        return ""


def _unreadable_when_it_runs(argv: Sequence[str]) -> str | None:
    """The option whose **effective** value yt-dlp takes as text now and cannot read later.

    **The whole-line parse passes these, whatever they say** (`T184-R8`). A match filter is read
    part by part as each item arrives, and an encoding is looked up when output is written, so a
    bad one failed the job rather than the field.

    **What yt-dlp keeps, not each occurrence** (the 2026-09-27 redesign). The first version checked
    every occurrence, so `--encoding nope --encoding utf-8` was refused though yt-dlp takes the
    last one. `parseOpts` is yt-dlp's own parser step, and it answers with what every repeat and
    reset leaves: the last encoding, and each filter list as it stands. Each is then asked yt-dlp's
    own question with no item: `match_str` with every field missing still parses every part, and
    `codecs.lookup` is the lookup `--encoding` gets. Filters are alternatives, and yt-dlp reaches
    them in no fixed order, so every one is checked rather than any.

    **Parsing a part is not compiling its pattern** (`T184-R8`, seventh round). A missing field
    answers before `re.search` is reached, so `title~=[` parsed here and raised `PatternError` on
    the first item with a title. So each part is also evaluated on its own against an item whose
    every field is text: `~=` then compiles its operand, and no part's answer can hide the next
    one's, as `match_str`'s `all()` would.
    """
    from yt_dlp.options import parseOpts
    from yt_dlp.utils import match_str

    _, parsed, _ = parseOpts(list(argv))
    for spelling, filters in (
        ("--match-filters", parsed.match_filter),
        ("--break-match-filters", parsed.breaking_match_filter),
    ):
        for text in filters or ():
            try:
                match_str(text, {}, incomplete=True)
                for part in _FILTER_PARTS.split(text):
                    match_str(part, _EveryFieldIsText())
            except (ValueError, *_UNCOMPILABLE):
                return spelling
    if parsed.encoding is not None:
        try:
            codecs.lookup(parsed.encoding)
        except LookupError:
            return "--encoding"
    return None


class UnusableOptionsError(ValueError):
    """Saved hatch options that may not be used, discovered where they are about to be used.

    Its own type so the worker can tell it from a malformed request: the job is not invalid, its
    **stored options are no longer admissible** — because yt-dlp moved under a queued job, or
    because something other than this application wrote them.

    **No token is ever in the message** (`T184-R6`). A hatch token can be
    `Authorization: Bearer …` and this text reaches a log.
    """


def hatch_options(text: str, argv: Sequence[str]) -> dict[str, Any]:
    """What the admitted options produce, **re-admitting them first** (`T184-R5`).

    **Stored options are not trusted, and that is the whole point.** The first version applied
    whatever pairs the request carried, on the reasoning that the dialog would have parsed them.
    It would not always have: a preset is a TOML file a user can edit, and a request is a JSON
    blob in a database. The reviewer wrote `geo_bypass = true` into a preset by hand and watched
    it override the `False` this adapter sets on purpose (`REQ-EXCL-002`, `SEC-003`), and
    replaced `outtmpl` with a path outside the download directory by the same route.
    "Semantically validated at the boundary where it is used" is the only version of this that
    holds, because that is the only place all the routes meet.

    So three things are established here, every time:

    1. the **text** still admits, against today's audit and today's yt-dlp;
    2. the **argv** is exactly what admitting that text produces, so the tokens cannot have been
       edited away from the text a user was shown;
    3. the parse **succeeds**, so no job runs with options the parser would reject.

    Any of them failing raises `UnusableOptionsError` rather than quietly dropping the options,
    which would run a job that is not the one the user asked for (`T184-R8`).

    **Only the destinations the named options touch, at whatever value the parse produced**
    (`T184-R1`): `--fragment-retries 10` produces exactly the default dictionary, so a diff-derived
    merge omits the key and yt-dlp reads the absent value as **zero** retries.
    """
    if not argv and not text.strip():
        # **Both empty, which is every user who never opens the hatch.** The cheap path stays
        # cheap; what it may not do is skip the comparison below when only the *argv* is empty
        # (`T184-R8`), because stored text with no tokens beside it would then run silently
        # without the options it names.
        return {}

    from tracks_and_trails.downloader.extra_options import admit, grouped

    admission = admit(text)
    if not admission.usable:
        raise UnusableOptionsError(
            f"{len(admission.refusals)} of the options saved with this download are not accepted "
            "any more. Open it and check the extra options field."
        )
    if admission.accepted != tuple(argv):
        raise UnusableOptionsError(
            "the options saved with this download do not match the text they came from, so it is "
            "not clear which of them was meant to run"
        )

    from yt_dlp import parse_options

    try:
        parsed = dict(parse_options(list(argv)).ydl_opts)
    except _REFUSED_BY_YT_DLP as refused:
        raise UnusableOptionsError(
            "yt-dlp will not accept the options saved with this download"
        ) from refused
    if _unreadable_when_it_runs(argv) is not None:
        # The dialog's question, asked again: a stored filter no dialog checked would otherwise
        # start the job and fail on its first item.
        raise UnusableOptionsError("yt-dlp will not accept the options saved with this download")

    # **Options, not tokens, and from an option with several destinations only what it changed.**
    # Both halves were measured on 2026-09-26. Walking every token looked values up as if they
    # were options, so `--output-na-placeholder --fragment-retries` copied `fragment_retries` at
    # its default. And an option that can reach several keys brought all of them at whatever the
    # parse held, which for the keys its value did not touch is the *command line's* default rather
    # than the library's: `--compat-options no-live-chat` carried `ignoreerrors: "only_download"`,
    # and a failed MP3 conversion then came back as a finished `.m4a` — the false success the audit
    # refuses `-i/--ignore-errors` for (`T183-R2`). An option with one destination still carries
    # it whatever its value (`T184-R1`).
    command_line = _command_line_defaults()
    wanted: dict[str, Any] = {}
    for chunk in grouped(argv):
        keys = OPTION_KEYS.get(chunk[0], ())
        for key in keys:
            if key in parsed and (len(keys) == 1 or parsed[key] != command_line.get(key)):
                wanted[key] = parsed[key]
    if "postprocessors" in wanted:
        # **Only the processors the named options asked for.** Every `parse_options` result
        # carries yt-dlp's default `FFmpegConcat` (`only_multi_video`, run per playlist), which is
        # `--concat-playlist`'s default. The audit refuses that option, and the application's own
        # chain never had it. Copying the whole list brought it in with any processor the hatch
        # names, `--convert-thumbnails png` included. `postprocessors` is the one destination that
        # accumulates across options and has a non-empty default, so it is the one filtered.
        defaults = _default_postprocessors()
        wanted["postprocessors"] = [
            spec for spec in wanted["postprocessors"] if spec not in defaults
        ]
    return wanted


@functools.cache
def _command_line_defaults() -> Mapping[str, Any]:
    """What `parse_options` holds when nothing is typed: the command line's defaults.

    **Not the library's.** `YoutubeDL` reads an absent key its own way, and the two disagree:
    `ignoreerrors` is `"only_download"` here and absent, so false, to the library.
    """
    from yt_dlp import parse_options

    return MappingProxyType(dict(parse_options([]).ydl_opts))


@functools.cache
def _default_postprocessors() -> tuple[dict[str, Any], ...]:
    """What `parse_options` puts in `postprocessors` when nothing asks for any (`T184-R10`)."""
    return tuple(_command_line_defaults().get("postprocessors", ()))


#: The keys of an info JSON that carry the session's secrets (`DAT-003`, amended 2026-10-11).
#:
#: **Measured at 2026.08.19, on 2026-10-11.** yt-dlp writes `cookies`, the cookie values its jar
#: holds for a format's address, into every format and at the top level, so `--load-info-json` can
#: replay the download; and `http_headers`, which carry any header typed through `--add-headers`,
#: `Authorization` included. Its *clean* step strips neither. Both are removed wherever they occur,
#: since a field's depth is the extractor's choice.
INFO_JSON_SECRETS: Final = frozenset({"cookies", "http_headers"})


def without_secrets(value: Any) -> Any:
    """`value`, a decoded info JSON, with every `INFO_JSON_SECRETS` key removed at any depth."""
    if isinstance(value, dict):
        return {
            key: without_secrets(item)
            for key, item in value.items()
            if key not in INFO_JSON_SECRETS
        }
    if isinstance(value, list):
        return [without_secrets(item) for item in value]
    return value


def strip_info_json(path: Path) -> None:
    """Rewrite the info JSON at `path` without its cookies or request headers (`T-249`).

    `DAT-003`, amended 2026-10-11: cookie contents never reach a file this application keeps.
    **Replaced, not edited in place**: the stripped text goes to a sibling, which then replaces
    the original atomically, so no reader ever finds half a file. Written as yt-dlp writes it, UTF-8
    without escaping. **An unreadable file raises** rather than being kept as it is: a file this
    cannot read is one it cannot vouch for.
    """
    stripped = without_secrets(json.loads(path.read_text(encoding="utf-8")))
    sibling = path.with_name(f"{path.name}.stripping")
    sibling.write_text(json.dumps(stripped, ensure_ascii=False), encoding="utf-8")
    sibling.replace(path)


def keep_secrets_out(ydl: Any) -> None:
    """Make `ydl` serialize every info JSON without its cookies or request headers (`T249-R1`).

    **Before the file exists, not after it is written.** Every info JSON yt-dlp produces goes
    through the instance's `sanitize_info`, measured at 2026.08.19: the file `--write-info-json`
    keeps (`_write_info_json`, item and playlist alike), and the one `--embed-info-json` attaches
    inside an MKV (`FFmpegMetadataPP`, through its downloader). So no file holds the secrets for any
    moment, and no failure can leave one that does. A `before_dl` hook that stripped the file
    after it was written ran after any processor registered ahead of it: a subtitle conversion
    that failed there kept both secrets in staging for the resume, and the attachment was never
    reached at all. The download itself reads the info dict, never this copy of it.

    An instance attribute, because `sanitize_info` is a static method and only this session's
    `YoutubeDL` is changed. The worker still strips each info JSON in staging itself, for a yt-dlp
    whose writers stop calling it.
    """
    serialize = ydl.sanitize_info

    def sanitize_info(info_dict: Any, remove_private_keys: bool = False) -> Any:
        return without_secrets(serialize(info_dict, remove_private_keys))

    ydl.sanitize_info = sanitize_info


def keep_the_literal_path(ydl: Any, ytdlp: Any, staging: Path) -> None:
    """Make `ydl` write the worker's literal path as it was handed over (`T-365`).

    **yt-dlp changes the path it is given twice before writing to it**, and `as_literal_template`'s
    escaping reaches neither. `_outtmpl_expandpath` expands environment variables in the template,
    so a folder `Notes $HOME` became `Notes /home/…`, outside the chosen folder, and a title
    `Price $HOME` was saved as the variable's last part. And on Windows `get_output_path` puts the
    whole path through `sanitize_path`, which renames a folder Windows allows, ending in U+00A0, to
    end in `#`. Measured in real sessions at 2026.08.19: each wrote outside the folder or under
    another name, and the claim's source check (`T109-R8`) failed the job only after the file
    existed. It is `T-363`'s breach by two more routes.

    **Instance attributes on this session's `YoutubeDL` only**, as `keep_secrets_out` sets its own.
    A template under `staging` is not expanded at all: the probe pass expanded the user's template
    already, and every character after that is a name the worker rendered, contained and showed.
    yt-dlp's Windows pass still runs below `staging`, where a site's chapter title can land; only
    the staging directory's own path, which the worker created and so exists as written, is kept
    out of it. Any other template or path goes to yt-dlp unchanged, and a yt-dlp without these
    methods leaves the claim's check as the only line.
    """
    kept = f"{staging}{os.sep}"
    escaped = kept.replace("%", "%%")
    expand = getattr(ydl, "_outtmpl_expandpath", None)
    output_path = getattr(ydl, "get_output_path", None)
    sanitize_path = getattr(getattr(ytdlp, "utils", None), "sanitize_path", None)

    if expand is not None:

        def _outtmpl_expandpath(outtmpl: str) -> str:
            return outtmpl if outtmpl.startswith(escaped) else str(expand(outtmpl))

        ydl._outtmpl_expandpath = _outtmpl_expandpath

    if output_path is not None and sanitize_path is not None:

        def get_output_path(dir_type: str = "", filename: str | None = None) -> str:
            # `--paths` is refused (`app:contained`), so nothing is joined ahead of the literal.
            if filename and filename.startswith(kept) and not ydl.params.get("paths"):
                below = filename[len(kept) :]
                return kept + str(sanitize_path(below, force=ydl.params.get("windowsfilenames")))
            return str(output_path(dir_type, filename))

        ydl.get_output_path = get_output_path


def merge_thumbnail(options: dict[str, Any], hatch: dict[str, Any]) -> None:
    """Settle `writethumbnail`, the one key the application and the user share (Finding 6).

    **A union, ruled by the maintainer on 2026-09-20 as an `ARC-010` amendment.** `ARC-010` §3
    says the hatch may not override an application-owned key, and this is one: `build_options`
    sets `writethumbnail` whenever `embed_thumbnail` is set, so the picture is written, embedded
    and then deleted. Read literally that refuses `--write-thumbnail` outright.

    The amendment says the two intents are not in conflict. The application writes the thumbnail
    *in order to embed it*; a user asking to keep it changes only the deletion. So the thumbnail
    is written when **either** asks, and the user's request to keep it survives — which is the
    `already_have_thumbnail` half.

    **Since `T-249` the keep is a control**, `keep_thumbnails`, and admission refuses the hatch's
    three thumbnail spellings for it. This union is still the written rule for the key, and the
    control reaches it through `build_options` directly.
    """
    if "writethumbnail" not in hatch:
        return
    options["writethumbnail"] = bool(options.get("writethumbnail")) or bool(hatch["writethumbnail"])


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
    # **The hatch's processors count too** (`T184-R10`). This read the application's own list, so
    # `--split-chapters` and `--convert-thumbnails png` — both ffmpeg work, both admitted —
    # answered "no ffmpeg needed", and the user learned otherwise after the bytes were spent,
    # which is the whole point of `REQ-024` asking before.
    # **A section is ffmpeg's download** (`T-252`): yt-dlp sends any item with a `section_start` to
    # its ffmpeg downloader, or aborts when there is none (`YoutubeDL.process_info`, read at
    # 2026.08.19). A chapter pattern or `*from-url` counts as well, since what it cuts depends on
    # the item. The hatch answered this for `--download-sections` until the control refused it.
    return (
        bool(request.download_sections)
        or _performed_by_ffmpeg(build_postprocessors(request))
        or hatch_requires_ffmpeg(request.extra_options, request.extra_option_argv)
    )


def hatch_requires_ffmpeg(text: str, argv: Sequence[str]) -> bool:
    """Whether the hatch alone asks for work ffmpeg performs, counted as the worker counts it.

    **The one answer the offer and the worker share** (`T184-R14`). `core.presets.needs_ffmpeg`
    reads a preset's fields and cannot see the hatch without yt-dlp, so a preset carrying
    `--split-chapters` was offered with ffmpeg absent and refused by `_ffmpeg_gap` straight after:
    `T199-R1`'s offered-then-refused, through the newest field. `requires_ffmpeg` and
    `extra_options.preset_needs_ffmpeg` both ask here.

    Stored options that no longer admit count as none: the job fails on them with its own reason
    when its dictionary is built, and this answers for the part that is still readable.

    **Downloading counted as well as post-processing** (`T184-R14`, seventh round): this read only
    `postprocessors`, so `--download-sections "*1-2"` was offered with ffmpeg absent and yt-dlp then
    aborted. *(Since `T-252` that spelling is refused here for its control, so nothing the hatch
    admits sets `download_ranges`, and `requires_ffmpeg` reads the request's sections instead.)*
    """
    if not argv and not text.strip():
        return False
    try:
        # Asked by the offer in the GUI's process as well as by the worker (`T-363`).
        with process_state_kept():
            hatch = hatch_options(text, argv)
    except UnusableOptionsError:
        return False
    return _performed_by_ffmpeg(hatch.get("postprocessors", []))


def options_needing_ffmpeg(argv: Sequence[str]) -> tuple[str, ...]:
    """Which admitted options each install work ffmpeg performs, to name them where typed.

    Asked by the editor without ffmpeg, in the GUI's process, so whatever the parses change for the
    whole process is put back (`T363-R1`). **One option at a time is exactly the danger**: a line
    that names `allow-unsafe-ext` and takes it away again is admitted, and parsing its first
    `--compat-options` alone switched the GUI's extension check off. See `_options_needing_ffmpeg`.
    """
    with process_state_kept():
        return _options_needing_ffmpeg(argv)


def _options_needing_ffmpeg(argv: Sequence[str]) -> tuple[str, ...]:
    """Which admitted options each install work ffmpeg performs, to name them where typed.

    Attribution only, asked one option at a time; whether the field needs ffmpeg is
    `hatch_requires_ffmpeg`'s answer for the whole line.
    """
    from yt_dlp import parse_options

    from tracks_and_trails.downloader.extra_options import grouped

    defaults = _default_postprocessors()
    named: dict[str, None] = {}
    for chunk in grouped(argv):
        try:
            parsed = parse_options(list(chunk)).ydl_opts
        except _REFUSED_BY_YT_DLP:
            continue
        specs = parsed.get("postprocessors", [])
        if _performed_by_ffmpeg([spec for spec in specs if spec not in defaults]):
            named[chunk[0]] = None
    return tuple(named)


def _performed_by_ffmpeg(specs: Sequence[Mapping[str, Any]]) -> bool:
    """Whether any of these postprocessors is ffmpeg's, by yt-dlp's own class hierarchy."""
    from yt_dlp.postprocessor import get_postprocessor
    from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor

    for spec in specs:
        try:
            processor = get_postprocessor(str(spec["key"]))
        except KeyError, AttributeError:  # pragma: no cover - build_postprocessors validates
            return True
        if issubclass(processor, FFmpegPostProcessor):
            return True
    return False


def build_postprocessors(
    request: DownloadRequest, *, keep_thumbnail: bool = False
) -> list[dict[str, Any]]:
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

    ## The order is yt-dlp's own, and it is load-bearing (`T-109`)

    Transcribed from `yt_dlp/__init__.py`'s `get_postprocessors`, which is where the library
    decides what its own command line means. Each step feeds the next, so the sequence is a
    contract rather than a style:

    0. **`FFmpegSubtitlesConvertor`** (`T-251`), which runs *before* the download, on the
       subtitles yt-dlp has just written, so whatever follows sees the converted files.
    1. **`FFmpegExtractAudio`** first among the rest, because everything after it should act on
       the audio file rather than on the container it came out of.
    2. **`FFmpegVideoRemuxer`**, then **`FFmpegVideoConvertor`** — the container is settled before
       anything is written into it. `DownloadRequest` refuses to carry both.
    3. **`FFmpegEmbedSubtitle`**, before metadata: yt-dlp's own comment notes the subtitles must
       already be in the container by the time chapters are modified.
    4. **`FFmpegMetadata`** after the container is final, because "containers before conversion
       may not support metadata (3gp, webm, etc.)" — yt-dlp's words, and the reason this is not
       simply appended wherever it reads best.
    5. **`EmbedThumbnail`** last, for the same reason.

    **Metadata and chapters are one postprocessor with two flags, and both flags are always
    stated.** `FFmpegMetadata(add_metadata=True, add_chapters=True)` is the constructor's
    *default*, so a spec naming one and omitting the other does not lose the second — it turns it
    on. A translation emitting one spec per option would therefore embed a user's title, uploader
    and source URL into a file where they had asked only to keep the chapter marks, and the
    deduplication below would hide it by keeping whichever spec came first.

    *(An earlier version of this paragraph said the opposite — that two specs would be
    deduplicated to one and *lose* a flag. A mutation replacing this block with two specs survived
    the whole suite, which is what said so: nothing was lost, something was added. The claim was
    wrong in a way that made the code look more defensive than it was, and
    `test_requested_chapters_are_written_into_the_file` now asserts the real property.)*
    """
    from yt_dlp.postprocessor import get_postprocessor

    specs: list[dict[str, Any]] = []
    if request.subtitle_languages and request.convert_subtitles is not None:
        # **Before the download, as yt-dlp's own command line schedules it** (`T-251`), so the
        # converted file is the one `FFmpegEmbedSubtitle` embeds or the worker claims. It replaces
        # each written subtitle with the converted one, in `requested_subtitles` as on disk.
        specs.append(
            {
                "key": "FFmpegSubtitlesConvertor",
                "format": request.convert_subtitles.value,
                "when": "before_dl",
            }
        )
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
    if request.remux_container is not None:
        specs.append({"key": "FFmpegVideoRemuxer", "preferedformat": request.remux_container})
    if request.recode_container is not None:
        # yt-dlp's spelling, missing `r` and all: `preferedformat` is the constructor's parameter
        # name for both of these, and correcting it here would simply not reach the postprocessor.
        specs.append({"key": "FFmpegVideoConvertor", "preferedformat": request.recode_container})
    if request.subtitle_languages and request.embed_subtitles:
        specs.append({"key": "FFmpegEmbedSubtitle"})
    if request.embed_metadata or request.embed_chapters:
        specs.append(
            {
                "key": "FFmpegMetadata",
                "add_metadata": request.embed_metadata,
                "add_chapters": request.embed_chapters,
            }
        )
    if request.embed_thumbnail:
        # `already_have_thumbnail` tells the postprocessor to **leave the picture behind**
        # (`T184-R11`). Without it the real `EmbedThumbnail` deletes the cover after embedding, so
        # a user who asked to keep it with `--write-thumbnail` watched it vanish from a download
        # that reported success. `ARC-010`'s 2026-09-20 amendment rules the union; this is where
        # the keep half of it actually happens.
        # **Keyed on what the *user* asked for, not on `writethumbnail`.** The application sets
        # that key itself whenever it embeds, purely so there is a picture to embed, so reading it
        # here would keep the file for every embedding job — which `REQ-010` does not ask for and
        # `T-109` deliberately decided against. The keep comes from `keep_thumbnails` (`T-249`)
        # or from the hatch, or it does not come.
        kept = keep_thumbnail or request.keep_thumbnails is not KeptThumbnails.NONE
        specs.append({"key": "EmbedThumbnail", "already_have_thumbnail": kept})
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


def _as_dimension(value: object) -> int | None:
    """A pixel dimension, where **zero means absent** (`T107-R1`).

    Separate from `_as_optional_int` rather than changing it: a zero *count* — bytes, entries,
    attempts — is a real value that must survive, and a zero *dimension* is yt-dlp saying it does
    not know. `yt-dlp -F` prints `unknown` for those, and the table has to agree with it.
    """
    projected = _as_optional_int(value)
    return projected or None


def _as_optional_codec(value: object) -> str | None:
    """`'none'` is yt-dlp's way of saying a stream is absent — not a codec called "none"."""
    codec = _as_optional_str(value)
    return None if codec in (None, "none") else codec


def _as_stream_presence(value: object) -> bool | None:
    """Whether a `vcodec`/`acodec` field says the stream is there, absent, or unknown (`T-108`).

    Three answers from one yt-dlp field, which carries three states:

    - a codec name — the stream is there
    - the literal `'none'` — yt-dlp is stating there is no such stream
    - missing, empty, or the placeholder `'unknown'` — yt-dlp does not know

    **`'unknown'` is grouped with missing rather than with present**, and that is the whole
    distinction `T107-R1` turned on: `yt-dlp -F` prints `unknown` for archive.org's derivatives, and
    reading that as *"a codec named unknown, therefore a stream exists"* would put every one of them
    in the video slot. A placeholder is the absence of an answer, not an answer.
    """
    codec = _as_optional_str(value)
    if codec is None or codec.casefold() == "unknown":
        return None
    return codec != "none"


# --- REQ-011: rendering an output template for the preview (`T-112`) -----------------------------
#
# **The preview renders through yt-dlp, exactly as the download does.** `ARCHITECTURE.md` §6 makes
# this module one of the two allowed to know that syntax, and `docs/UX_SPEC.md` §9.1 requires the
# preview and the write to be one function — so a hand-written `%(field)s` substituter in `ui/`
# would break both rules at once and would be wrong the first time yt-dlp's conversion syntax was
# used. What differs between the two callers is the *info* being rendered, not the renderer: the
# worker has the real extraction, and the dialog has the declared projection `core/output_template`
# builds from `MediaInfo`.
#
# `ARC-002` keeps `ui/` away from here regardless; `DownloadManager.preview_output_path` is the seam
# the dialog actually calls.

#: One `YoutubeDL`, reused for every preview.
#:
#: **Construction is the cost, and it is not small.** Measured at 15.7 ms per instance against
#: yt-dlp 2026.07.04 versus 0.07 ms to render a template on an existing one — so building one per
#: keystroke would spend a fifth of `NFR-001`'s whole interaction budget on setup for a string
#: substitution. It holds no session state that a render can dirty: `prepare_filename` takes both
#: the template and the info dict as arguments, so nothing about one preview reaches the next.
_previewer: Any = None


def _preview_renderer() -> Any:
    global _previewer
    if _previewer is None:
        from yt_dlp import YoutubeDL

        _previewer = YoutubeDL({"quiet": True, "no_warnings": True, "noprogress": True})
    return _previewer


def template_syntax_error(template: str) -> str | None:
    """Why yt-dlp would refuse `template`, or `None` if it would not (`P-23`).

    **yt-dlp's own validator**, so the editor refuses exactly what the download would and nothing
    else. It reports what it can as a returned error and raises `ValueError` for a template it
    cannot even parse — `%(title)` is the ordinary case, a field left mid-conversion while the user
    is still typing — so both are turned into the same answer here.

    Field *names* are not its business and it does not check them: yt-dlp renders an unknown field
    as `NA`. `core.output_template.unsupported_refusal` is the other half.
    """
    try:
        error = _preview_renderer().validate_outtmpl(template)
    except ValueError as refusal:
        return str(refusal)
    return None if error is None else str(error)


def render_output_template(
    template: str, values: Mapping[str, Any], shaping: Mapping[str, Any] = MappingProxyType({})
) -> str:
    """Render `template` against `values`, through yt-dlp's own mechanism.

    The same call `worker._validated_target` makes — `prepare_filename` with an explicit template —
    so the sanitizing yt-dlp applies on the way out (a colon becoming a fullwidth one, say) happens
    to the preview and the write alike. A separate substituter here would agree with it right up
    until it did not.

    `dict(values)` because yt-dlp adds derived fields to the mapping it is given (`duration_string`,
    `epoch`), and a caller's projection is not this function's to grow.

    **`shaping` is `shaping_options` of the request being previewed** (`T-248`). yt-dlp reads both
    keys from its parameters as it renders, so they are set on the shared renderer, **every key on
    every call**, and one preview's shape cannot reach the next.
    """
    renderer = _preview_renderer()
    for key in SHAPING_KEYS:
        renderer.params[key] = shaping.get(key)
    return str(renderer.prepare_filename(dict(values), outtmpl=template))


# --- ffmpeg's position while a post-processing step runs (`T-344`) -----------------------------

#: What yt-dlp's `FFmpegPostProcessor.real_run_ffmpeg` puts on every command it runs for a step,
#: and its other ffmpeg calls (`-version`, `ffprobe`) do not. It is how a step's run is told apart,
#: so those others are left exactly as yt-dlp made them.
_STEP_LOGLEVEL: Final = "repeat+info"

#: Where the progress lines go and how they are asked for. `-progress pipe:1` writes `key=value`
#: lines to standard output, which yt-dlp's call discards; `-nostats` keeps the older, unparseable
#: status line out of the standard error yt-dlp does read, for its error message.
_PROGRESS_ARGUMENTS: Final = ("-progress", "pipe:1", "-nostats")

#: The keys ffmpeg reports its position in. **Both are microseconds**: `out_time_ms` is misnamed in
#: ffmpeg itself, and newer builds add `out_time_us` beside it.
_POSITION_KEYS: Final = ("out_time_us", "out_time_ms")


def is_step_command(command: object) -> bool:
    """Whether `command` is ffmpeg run by yt-dlp for a post-processing step."""
    return isinstance(command, list | tuple) and _STEP_LOGLEVEL in command


def with_progress_arguments(command: Sequence[str]) -> list[str]:
    """`command` with ffmpeg asked to report its position, straight after the executable."""
    return [command[0], *_PROGRESS_ARGUMENTS, *command[1:]]


def position_in(line: str) -> float | None:
    """The position, in seconds, one ffmpeg progress line reports, or `None` if it reports none."""
    key, _, value = line.strip().partition("=")
    if key in _POSITION_KEYS and value.isdigit():
        return int(value) / 1_000_000
    return None


def run_reporting_position(
    popen: Any,
    command: Sequence[str],
    options: dict[str, Any],
    on_position: Callable[[float], None],
) -> tuple[str, str, int]:
    """Run a step's ffmpeg the way `yt_dlp.utils.Popen.run` would, reporting its position.

    **Returns what `Popen.run` returns** — standard output, standard error, the exit code — so
    `real_run_ffmpeg` carries on unchanged: it reads the exit code and standard error, and makes
    its error message from the last line of the latter.

    Standard error is drained on its own thread while standard output is read here, because
    ffmpeg writes both and a full pipe on either would stop it. **If `on_position` raises** — the
    worker's cancellation check does — ffmpeg is killed before the exception goes on, so a
    cancelled conversion leaves no ffmpeg behind.
    """
    import subprocess
    import threading

    arguments = dict(options)
    arguments.pop("timeout", None)
    arguments["stdout"] = subprocess.PIPE
    arguments["stderr"] = subprocess.PIPE
    arguments.setdefault("text", True)
    errors: list[str] = []
    output: list[str] = []
    with popen(with_progress_arguments(command), **arguments) as process:
        drain = threading.Thread(
            target=lambda: errors.append(process.stderr.read()), daemon=True, name="ffmpeg-stderr"
        )
        drain.start()
        try:
            for line in process.stdout:
                output.append(line)
                position = position_in(line)
                if position is not None:
                    on_position(position)
            process.wait()
        except BaseException:
            process.kill()
            process.wait()
            raise
        finally:
            drain.join()
    return "".join(output), "".join(errors), int(process.returncode)


@contextlib.contextmanager
def ffmpeg_progress(ytdlp: Any, on_position: Callable[[float], None]) -> Iterator[bool]:
    """Report ffmpeg's position during yt-dlp's post-processing steps, for as long as this lasts.

    **yt-dlp says only *started* and *finished* for a step** (`T-344`): `real_run_ffmpeg` runs
    ffmpeg through `Popen.run`, which returns when ffmpeg has finished, so a long conversion was
    minutes of nothing. This replaces the `Popen` that yt-dlp's `postprocessor.ffmpeg` module looks
    up, for step commands only (`is_step_command`), with one that asks ffmpeg for `-progress` and
    passes each position to `on_position`.

    **Yields whether it could.** A yt-dlp whose module no longer has a `Popen` with `run` is left
    alone and the row falls back to a moving bar; the canary is what says so when it happens.
    Restored on exit, and it is only ever installed inside a worker process, one session each.
    """
    try:
        module = importlib.import_module(f"{ytdlp.__name__}.postprocessor.ffmpeg")
    except ImportError:
        yield False
        return
    original: Any = getattr(module, "Popen", None)
    if original is None or not callable(getattr(original, "run", None)):
        yield False
        return

    class _ReportingPopen(original):  # type: ignore[misc]
        @classmethod
        def run(cls, *args: Any, **kwargs: Any) -> Any:
            command: Any = args[0] if args else kwargs.get("args")
            if not is_step_command(command) or len(args) > 1:
                return original.run(*args, **kwargs)
            kwargs.pop("args", None)
            return run_reporting_position(original, command, kwargs, on_position)

    setattr(module, "Popen", _ReportingPopen)  # noqa: B010 (the module's type does not name it)
    try:
        yield True
    finally:
        setattr(module, "Popen", original)  # noqa: B010
