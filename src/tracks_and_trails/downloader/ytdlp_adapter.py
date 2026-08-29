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

import logging
from collections.abc import Callable, Mapping, Sequence
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
    parse_browser_specification,
)
from tracks_and_trails.core.paths import APP_SLUG

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
        subtitle_languages=_subtitle_languages(info),
    )


def _subtitle_languages(info: Mapping[str, Any]) -> tuple[str, ...]:
    """The languages this source publishes subtitles in (`REQ-010`, `P-17`, `T-109`).

    **The keys of yt-dlp's `subtitles` map, and nothing under them.** Each value is a list of
    downloadable variants — url, ext, name — and none of it reaches `MediaInfo`, which needs a
    language list to offer and not a download plan. `writesubtitles` and `subtitleslangs` are how
    a language is asked for; yt-dlp picks the variant.

    **`automatic_captions` is deliberately not merged in.** It is a separate map fetched under a
    separate option (`writeautomaticsub`), which `REQ-010` does not name — so a language offered
    from it would be one this application asks for and never receives, producing a file with no
    subtitles and no error. That is the `T-075` shape: a control that appears to do nothing.

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
    - **The entry's `id`** survives redaction and is what a human would want, but reading it here
      puts `id` into the fixture allowlist by construction: `tests/unit/test_fixtures.py` derives
      that allowlist from this module's AST, and `capture.py` currently strips exactly this value
      out of committed captures, `ALLOWED_QUERY_PARAMETERS` being empty. Committing entry ids is a
      reversal of that, not a consequence of this

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
                duration_seconds=_as_optional_float(item.get("duration")),
                thumbnail_url=_entry_thumbnail(item),
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
    if request.retries is not None:
        # **`is not None`, not truthiness** (`T-196`). `retries=0` is a user asking not to retry
        # inside the attempt, and the two lines above can read a zero as *unset* because a rate
        # limit of zero bytes per second is not a thing anyone means. Here it is: dropped by
        # truthiness, "never retry" would silently become yt-dlp's own default of ten.
        #
        # **This is `--retries`, and it is deliberately not `--fragment-retries`** — measured
        # against yt-dlp 2026.07.04, where `downloader/http.py` reads `retries` and
        # `downloader/fragment.py` reads `fragment_retries`. The maintainer's 2026-08-13 ruling
        # names `--retries`; the rest of yt-dlp's network surface, this one included, belongs to
        # `T-183`'s audit rather than to a setting that would have to explain the difference.
        options["retries"] = request.retries
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

    if request.embed_thumbnail:
        # **`EmbedThumbnail` embeds a file that has to exist first** (`T-109`). yt-dlp's own
        # `get_postprocessors` sets `writethumbnail` when `--embed-thumbnail` is given, and
        # without it the postprocessor runs against a download that has no picture beside it and
        # embeds nothing. That is `T012-R5`'s defect exactly — a key accepted, and silently
        # ineffective — one option along.
        #
        # The picture is **not** kept: `already_have_thumbnail` is left False in the spec below,
        # so yt-dlp deletes it after embedding. `REQ-010` asks to embed a thumbnail, not to write
        # one beside the media, and a stray `.jpg` in the output directory is not what was asked
        # for.
        options["writethumbnail"] = True

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

    ## The order is yt-dlp's own, and it is load-bearing (`T-109`)

    Transcribed from `yt_dlp/__init__.py`'s `get_postprocessors`, which is where the library
    decides what its own command line means. Each step feeds the next, so the sequence is a
    contract rather than a style:

    1. **`FFmpegExtractAudio`** first, because everything after it should act on the audio file
       rather than on the container it came out of.
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
        specs.append({"key": "EmbedThumbnail"})
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


def render_output_template(template: str, values: Mapping[str, Any]) -> str:
    """Render `template` against `values`, through yt-dlp's own mechanism.

    The same call `worker._validated_target` makes — `prepare_filename` with an explicit template —
    so the sanitizing yt-dlp applies on the way out (a colon becoming a fullwidth one, say) happens
    to the preview and the write alike. A separate substituter here would agree with it right up
    until it did not.

    `dict(values)` because yt-dlp adds derived fields to the mapping it is given (`duration_string`,
    `epoch`), and a caller's projection is not this function's to grow.
    """
    return str(_preview_renderer().prepare_filename(dict(values), outtmpl=template))
