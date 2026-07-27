"""The yt-dlp adapter: projection, classification, and options (`T-012`).

Everything here runs against the **recorded fixture**, never the network (`ai/TESTING.md` §2,
§5). The fixture is a contract: changing a key the projection reads must fail a test, which is
the only reason recording it is worth the maintenance.

`ai/TESTING.md` §13 applies throughout — expectations are transcribed from `ARCHITECTURE.md`
§5 and §7, never read back out of the adapter.
"""

import json
from pathlib import Path
from typing import Any, cast

import pytest
from yt_dlp.networking.exceptions import (
    CertificateVerifyError,
    IncompleteRead,
    ProxyError,
    SSLError,
    TransportError,
)
from yt_dlp.utils import (
    ContentTooShortError,
    DownloadCancelled,
    DownloadError,
    ExtractorError,
    GeoRestrictedError,
    PostProcessingError,
    UnsupportedError,
)

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.models import (
    AudioCodec,
    DownloadRequest,
    FormatInfo,
    MediaInfo,
    MediaKind,
)
from tracks_and_trails.downloader import ytdlp_adapter as adapter

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "infodicts"


def load_fixture(name: str = "archive_org_big_buck_bunny") -> dict[str, Any]:
    payload = json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return dict(payload["info_dict"])


def request_for(**overrides: Any) -> DownloadRequest:
    base: dict[str, Any] = {
        "url": "https://archive.org/details/BigBuckBunny_124",
        "output_directory": "/downloads",
        "format_selector": "bestvideo+bestaudio/best",
        "output_template": "%(title)s.%(ext)s",
    }
    return DownloadRequest(**{**base, **overrides})


def _http_error(status: int) -> Any:
    """A real `HTTPError`, built the way yt-dlp builds one.

    `HTTPError.__init__` reads `status` and `reason` off a `Response`, so a hand-set attribute
    would test a shape yt-dlp never produces.
    """
    import io

    from yt_dlp.networking import Response
    from yt_dlp.networking.exceptions import HTTPError

    response = Response(fp=io.BytesIO(b""), url="https://example.com/x", headers={}, status=status)
    return HTTPError(response)


# --- the fixture is a contract, not a sample -------------------------------------------------


def test_the_fixture_records_its_provenance() -> None:
    """`ai/TESTING.md` §5: each fixture records the yt-dlp version and capture date.

    Without them a failing projection cannot be told from an upstream change, which is most of
    what the fixture is for.
    """
    payload = json.loads(
        (FIXTURE_DIR / "archive_org_big_buck_bunny.json").read_text(encoding="utf-8")
    )
    meta = payload["_fixture"]
    assert meta["yt_dlp_version"]
    assert meta["captured"]
    assert meta["source_url"]
    assert "allowlist" in meta["policy"], "the fixture must say what rule produced it"


def test_the_fixture_carries_no_credential_material() -> None:
    """`NFR-007`, and `T018-R1`'s structural answer: the keys are **absent**, not redacted.

    They used to be present with a marker, which meant something still had to recognise them.
    A fixture now carries only fields this adapter reads, and it reads no field that can hold a
    credential — so `cookies` and `http_headers` are simply not there. `tests/unit/test_fixtures.py`
    owns the general rule; this pins the one fixture `T-012` reads directly.
    """
    blob = (FIXTURE_DIR / "archive_org_big_buck_bunny.json").read_text(encoding="utf-8")
    info = load_fixture()
    assert "cookies" not in info
    assert all("cookies" not in entry and "http_headers" not in entry for entry in info["formats"])
    assert "Bearer " not in blob


@pytest.mark.parametrize("key", ["title", "duration", "uploader", "formats", "thumbnail"])
def test_removing_a_projected_key_changes_the_projection(key: str) -> None:
    """The contract property: a fixture that loses a projected key must not project the same.

    This is what makes the fixture worth recording. Without it the file is a sample that
    happens to parse.
    """
    info = load_fixture()
    baseline = adapter.project_media(info)
    del info[key]
    assert adapter.project_media(info) != baseline


def test_probe_projects_every_declared_field() -> None:
    """Field by field, against values read from the fixture rather than hardcoded.

    Hardcoding `"Big Buck Bunny"` would pass if the projection returned a constant; comparing
    against the fixture's own values proves the data made the journey.
    """
    info = load_fixture()
    media = adapter.project_media(info)

    assert isinstance(media, MediaInfo)
    assert media.title == info["title"]
    assert media.url == info["webpage_url"]
    assert media.uploader == info["uploader"]
    assert media.duration_seconds == pytest.approx(float(info["duration"]))
    assert media.thumbnail_url == info["thumbnail"]
    assert media.is_live is False
    assert len(media.formats) == len(info["formats"])


def test_projected_formats_carry_their_declared_fields() -> None:
    info = load_fixture()
    media = adapter.project_media(info)

    for projected, raw in zip(media.formats, info["formats"], strict=True):
        assert isinstance(projected, FormatInfo)
        assert projected.format_id == str(raw["format_id"])
        assert projected.extension == str(raw["ext"])


def test_the_projection_is_a_declared_type_all_the_way_down() -> None:
    """`ARC-002`: no raw dict survives the boundary, at any depth.

    `core/models.py` enforces this too (`T-041`), but asserting it here pins the *adapter's*
    obligation rather than relying on the layer beneath catching a mistake.
    """
    media = adapter.project_media(load_fixture())
    assert isinstance(media.formats, tuple)
    assert all(isinstance(f, FormatInfo) for f in media.formats)
    assert not any(isinstance(f, dict) for f in media.formats)


def test_the_url_falls_back_through_yt_dlps_aliases() -> None:
    """`webpage_url` is not in the removal sweep above because it has deliberate fallbacks.

    Asserted here instead, so the fallback chain is a tested decision rather than the reason a
    contract test quietly passed.
    """
    info = load_fixture()
    expected = info["webpage_url"]
    del info["webpage_url"]
    assert adapter.project_media(info).url == expected  # original_url carries the same value

    info["original_url"] = ""
    info["url"] = "https://fallback.example/x"
    assert adapter.project_media(info).url == "https://fallback.example/x"


def test_a_missing_title_falls_back_to_the_url_not_to_a_placeholder() -> None:
    """`MediaInfo` requires a displayable title; inventing "Untitled" would be worse."""
    info = load_fixture()
    info["title"] = ""
    assert adapter.project_media(info).title == info["webpage_url"]


def test_yt_dlp_none_codecs_become_none_not_the_string() -> None:
    """`'none'` is yt-dlp's way of saying a stream is absent, not a codec called "none"."""
    projected = adapter.project_format({"format_id": "1", "ext": "m4a", "vcodec": "none"})
    assert projected.video_codec is None
    assert projected.is_audio_only is False or projected.audio_codec is None


def test_a_size_known_only_approximately_is_still_reported() -> None:
    """yt-dlp supplies `filesize` **or** `filesize_approx`, never reliably both.

    YouTube's DASH formats — the ones this project exists to download — routinely carry only
    `filesize_approx`. Reading `filesize` alone shows "unknown" for a size yt-dlp actually
    knows, so the user picking a format has no size to compare against on exactly the site
    that matters most.

    Written because a mutation deleting the fallback survived the whole suite: the archive.org
    fixture happens to populate `filesize` on every format, so nothing exercised the other
    branch. The expectation here comes from yt-dlp's field contract, not from the fixture.
    """
    approx_only = adapter.project_format(
        {"format_id": "137", "ext": "mp4", "filesize_approx": 4_194_304}
    )
    assert approx_only.filesize == 4_194_304

    # An exact size must win over the estimate rather than being overwritten by it.
    both = adapter.project_format(
        {"format_id": "137", "ext": "mp4", "filesize": 1000, "filesize_approx": 9999}
    )
    assert both.filesize == 1000

    neither = adapter.project_format({"format_id": "137", "ext": "mp4"})
    assert neither.filesize is None, "an unknown size must stay unknown, not become 0"


def test_a_format_without_an_id_is_dropped_rather_than_projected_empty() -> None:
    """`FormatInfo` requires a format_id — it is how a format is selected."""
    info = load_fixture()
    info["formats"] = [*info["formats"], {"ext": "mp4"}]
    assert len(adapter.project_media(info).formats) == len(info["formats"]) - 1


# --- classification (ARCHITECTURE.md §7) -----------------------------------------------------

#: Transcribed from `ARCHITECTURE.md` §7, **not** imported from the adapter (`ai/TESTING.md`
#: §13). Asking the module which kinds it maps and then checking it maps them proves nothing.
SECTION_7_KINDS = {
    "UNSUPPORTED_URL",
    "EXTRACTOR_ERROR",
    "AUTH_REQUIRED",
    "GEO_RESTRICTED",
    "DRM_PROTECTED",
    "NETWORK",
    "FFMPEG_MISSING",
    "FFMPEG_ERROR",
    "DISK",
    "WORKER_CRASH",
    # Added to §7 on 2026-07-26 by `T-014` with maintainer approval, for §5's crash recovery.
    # Unmappable here by construction: nothing raises it, because the process that would have
    # is the one that died.
    "INTERRUPTED",
    "CANCELLED",
}


def test_every_taxonomy_kind_is_either_mapped_or_explicitly_unmapped() -> None:
    """The acceptance criterion, in both directions.

    A kind that is neither mapped nor listed as unmappable has been forgotten — which is the
    failure this test exists to catch, since a forgotten kind simply never gets produced.
    """
    assert {k.name for k in ErrorKind} == SECTION_7_KINDS

    mapped = {kind for _, kind in adapter._EXCEPTION_MAPPING}
    accounted = mapped | set(adapter.UNMAPPED_KINDS)
    missing = set(ErrorKind) - accounted
    assert not missing, f"{sorted(k.name for k in missing)} is neither mapped nor explained"


def test_every_unmapped_kind_states_why() -> None:
    """An empty reason would make `UNMAPPED_KINDS` a way to silence this test."""
    for kind, reason in adapter.UNMAPPED_KINDS.items():
        assert reason.strip(), f"{kind.name} is listed as unmapped with no reason"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (UnsupportedError("https://example.com/x"), ErrorKind.UNSUPPORTED_URL),
        (GeoRestrictedError("blocked in your country"), ErrorKind.GEO_RESTRICTED),
        (ExtractorError("Video unavailable"), ErrorKind.EXTRACTOR_ERROR),
        (PostProcessingError("ffmpeg exited 1"), ErrorKind.FFMPEG_ERROR),
        (ContentTooShortError(10, 20), ErrorKind.NETWORK),
        (DownloadCancelled("user cancelled"), ErrorKind.CANCELLED),
        (ConnectionResetError("reset by peer"), ErrorKind.NETWORK),
        (TimeoutError("timed out"), ErrorKind.NETWORK),
        (OSError(28, "No space left on device"), ErrorKind.DISK),
        # yt-dlp's own transport hierarchy (`T012-R3`). None of these subclass OSError or
        # ConnectionError, which is exactly why they used to fall through to EXTRACTOR_ERROR.
        (TransportError("connection dropped"), ErrorKind.NETWORK),
        (ProxyError("proxy refused"), ErrorKind.NETWORK),
        (SSLError("handshake failed"), ErrorKind.NETWORK),
        (CertificateVerifyError("self-signed certificate"), ErrorKind.NETWORK),
        (IncompleteRead(partial=5), ErrorKind.NETWORK),
    ],
)
def test_exception_types_map_to_their_taxonomy_kind(
    error: BaseException, expected: ErrorKind
) -> None:
    assert adapter.classify_exception(error).kind is expected


def test_every_transport_subclass_upstream_ships_is_network() -> None:
    """Class-level, so a *new* upstream transport type cannot reintroduce the defect.

    `T012-R3` was not "two types were missing" — it was that yt-dlp's transport hierarchy does
    not subclass `OSError` or `ConnectionError`, so the whole family fell through to
    `EXTRACTOR_ERROR` and lost auto-retry. Enumerating the five known names would leave the next
    subclass upstream adds equally unmapped, so this walks the pinned hierarchy instead.
    """
    import inspect

    from yt_dlp.networking import exceptions as upstream

    subclasses = cast(
        "list[type[BaseException]]",
        [
            obj
            for obj in vars(upstream).values()
            if inspect.isclass(obj) and issubclass(obj, upstream.TransportError)
        ],
    )
    assert len(subclasses) >= 4, "the hierarchy moved; this test is no longer reading it"

    for cls in subclasses:
        detail = adapter.classify_exception(cls("transport failure"))
        assert detail.kind is ErrorKind.NETWORK, f"{cls.__name__} is not classified as NETWORK"


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (408, ErrorKind.NETWORK),
        (429, ErrorKind.NETWORK),
        (500, ErrorKind.NETWORK),
        (503, ErrorKind.NETWORK),
        (401, ErrorKind.AUTH_REQUIRED),
        (403, ErrorKind.EXTRACTOR_ERROR),
        (404, ErrorKind.EXTRACTOR_ERROR),
    ],
)
def test_http_failures_classify_by_status_not_by_class(status: int, expected: ErrorKind) -> None:
    """`HTTPError` is one class covering outcomes with opposite retry consequences.

    Mapping the class wholesale would either auto-retry a 404 forever or refuse to retry a 503.
    `403` is deliberately **not** `AUTH_REQUIRED`: sites return it for expired signed URLs and
    regional blocks far more often than for a missing login, and telling a user to sign in when
    that cannot help is worse than saying nothing.

    Expectations are transcribed from HTTP semantics, not from `_RETRYABLE_STATUSES`
    (`ai/TESTING.md` §13).
    """
    detail = adapter.classify_exception(_http_error(status))
    assert detail.kind is expected


def test_a_retryable_http_status_is_actually_auto_retried() -> None:
    """The classification only matters because of what the retry policy does with it."""
    from tracks_and_trails.core.errors import is_auto_retryable

    assert is_auto_retryable(adapter.classify_exception(_http_error(503)).kind)
    assert not is_auto_retryable(adapter.classify_exception(_http_error(404)).kind)


def test_a_wrapped_transport_error_still_classifies_as_network() -> None:
    """yt-dlp wraps most failures in `DownloadError`; unwrapping must reach the transport type."""
    wrapped = DownloadError("download failed")
    wrapped.exc_info = (ProxyError, ProxyError("proxy refused"), None)
    assert adapter.classify_exception(wrapped).kind is ErrorKind.NETWORK


def test_subclass_ordering_is_not_swallowed_by_the_base_class() -> None:
    """`UnsupportedError` and `GeoRestrictedError` are both `ExtractorError` subclasses.

    A table walked in the wrong order classifies every one of them as `EXTRACTOR_ERROR` and
    loses the distinction that decides what the user is told. This is the ordering test.
    """
    assert adapter.classify_exception(UnsupportedError("x")).kind is ErrorKind.UNSUPPORTED_URL
    assert adapter.classify_exception(GeoRestrictedError("x")).kind is ErrorKind.GEO_RESTRICTED
    assert adapter.classify_exception(ExtractorError("x")).kind is ErrorKind.EXTRACTOR_ERROR


def test_a_wrapped_error_classifies_by_its_cause() -> None:
    """yt-dlp wraps most failures in `DownloadError`; without unwrapping, all look alike."""
    try:
        raise GeoRestrictedError("not available in your country")
    except GeoRestrictedError as inner:
        import sys

        wrapped = DownloadError("ERROR: not available in your country", sys.exc_info())
        assert adapter.unwrap(wrapped) is inner
        assert adapter.classify_exception(wrapped).kind is ErrorKind.GEO_RESTRICTED


def test_the_extractor_message_survives_verbatim() -> None:
    """`REQ-005`, `NFR-006` — by string equality, not by substring.

    yt-dlp appends *"please report this issue on GitHub..."* to unexpected `ExtractorError`s.
    Passing that on would tell a user to file a bug about a private video. `orig_msg` is the
    extractor's own text and is what reaches them.
    """
    text = "Private video. Sign in if you've been granted access"
    assert adapter.classify_exception(ExtractorError(text)).message == text


def test_yt_dlps_bug_report_boilerplate_does_not_reach_the_user() -> None:
    """The specific decoration this guards against, named so it cannot regress silently."""
    message = adapter.classify_exception(ExtractorError("Video removed by uploader")).message
    assert "report this issue" not in message
    assert "yt-dlp -U" not in message


def test_an_expected_error_is_already_clean_and_is_unchanged() -> None:
    """`expected=True` means yt-dlp adds nothing; the message must pass through untouched."""
    text = "Video unavailable"
    error = ExtractorError(text, expected=True)
    assert adapter.classify_exception(error).message == text


def test_an_unmapped_exception_classifies_rather_than_crashing() -> None:
    """A worker that dies while classifying turns a failed job into a lost one."""
    detail = adapter.classify_exception(ValueError("something nobody anticipated"))
    assert detail.kind is ErrorKind.EXTRACTOR_ERROR
    assert "something nobody anticipated" in detail.message


# --- DRM (REQ-EXCL-001, SEC-001) --------------------------------------------------------------


def test_drm_is_detected_from_the_structured_flag() -> None:
    """`_has_drm` is a field yt-dlp sets. Matching the words "DRM protected" would break the
    day upstream rewords or translates the message."""
    assert adapter.has_drm({"_has_drm": True})
    assert not adapter.has_drm(load_fixture())


def test_drm_is_detected_when_every_format_is_protected() -> None:
    assert adapter.has_drm({"formats": [{"has_drm": True}, {"has_drm": True}]})


def test_a_partially_protected_item_is_not_treated_as_drm_only() -> None:
    """One clean format means there is something lawful to fetch; failing would be wrong."""
    assert not adapter.has_drm({"formats": [{"has_drm": True}, {"has_drm": False}]})


def test_drm_detection_does_not_read_message_text() -> None:
    """The prose says DRM; the structure does not. Structure wins (`ai/TESTING.md` §13)."""
    assert not adapter.has_drm({"title": "This video is DRM protected", "formats": []})


def test_drm_protected_is_non_retryable_in_the_taxonomy() -> None:
    """`REQ-EXCL-001`: offering a retry would imply a workaround exists. It does not."""
    from tracks_and_trails.core.errors import is_auto_retryable, is_retryable

    assert not is_retryable(ErrorKind.DRM_PROTECTED)
    assert not is_auto_retryable(ErrorKind.DRM_PROTECTED)


# --- options ----------------------------------------------------------------------------------


def test_probe_options_never_download() -> None:
    options = adapter.build_options(request_for(), "%(title)s.%(ext)s", probe_only=True)
    assert options["skip_download"] is True


def test_options_are_quiet_and_non_interactive() -> None:
    """A worker has no console and no user; an interactive prompt there is a hang."""
    options = adapter.build_options(request_for(), "out.%(ext)s")
    assert options["quiet"] is True
    assert options["noprogress"] is True
    assert options["noplaylist"] is True


def test_the_format_selector_and_template_come_from_the_request() -> None:
    options = adapter.build_options(request_for(format_selector="worst"), "given.%(ext)s")
    assert options["format"] == "worst"
    assert options["outtmpl"] == "given.%(ext)s"


def test_network_options_are_only_set_when_asked_for() -> None:
    """An unconditional `proxy: None` is not the same as no proxy to yt-dlp."""
    plain = adapter.build_options(request_for(), "o.%(ext)s")
    assert "proxy" not in plain
    assert "ratelimit" not in plain
    assert "cookiesfrombrowser" not in plain

    configured = adapter.build_options(
        request_for(proxy="socks5://127.0.0.1:9050", rate_limit_bytes=1024), "o.%(ext)s"
    )
    assert configured["proxy"] == "socks5://127.0.0.1:9050"
    assert configured["ratelimit"] == 1024


def _constructed(options: dict[str, Any]) -> Any:
    """Build a real `YoutubeDL` and return the postprocessors it actually installed.

    `T012-R5` existed because the previous tests asserted that a key was *present in the input
    dict*. `extractaudio` is an argument-parser flag: `YoutubeDL` accepts it, ignores it, and
    installs nothing. Only the constructed object knows what will really run, so that is what
    these assert against (`ai/TESTING.md` §13).
    """
    from yt_dlp import YoutubeDL

    with YoutubeDL({**options, "quiet": True}) as ydl:
        return [type(pp).__name__ for group in ydl._pps.values() for pp in group]


def test_an_audio_request_installs_a_real_extraction_postprocessor() -> None:
    """`REQ-002` treats audio as first-class; a no-op here delivers the video container."""
    options = adapter.build_options(
        request_for(media_kind=MediaKind.AUDIO, format_selector="bestaudio"), "o.%(ext)s"
    )
    assert "FFmpegExtractAudioPP" in _constructed(options)


def _audio_processor(request: Any) -> Any:
    """The real `FFmpegExtractAudioPP` a request installs, or `None`.

    Returns the constructed processor rather than its spec dict: `T012-R5`'s second half was
    that the class being *installed* proves nothing about what it will *deliver*. `mapping` and
    `_preferredquality` are what yt-dlp actually acts on.
    """
    from yt_dlp import YoutubeDL

    options = adapter.build_options(request, "o.%(ext)s")
    with YoutubeDL({**options, "quiet": True}) as ydl:
        for group in ydl._pps.values():
            for processor in group:
                if type(processor).__name__ == "FFmpegExtractAudioPP":
                    return processor
    return None


def test_the_mp3_preset_actually_requests_mp3() -> None:
    """`REQ-006` requires "audio only (MP3)" as a preset distinct from best/original.

    Installing `FFmpegExtractAudioPP` is not enough: with no `preferredcodec` it defaults to
    `best`, which **keeps the source codec**. The MP3 preset therefore delivered whatever the
    site served — an Opus or M4A file named as though the user's choice had been honoured —
    and never converted anything (`T012-R5`).
    """
    processor = _audio_processor(
        request_for(
            media_kind=MediaKind.AUDIO,
            format_selector="bestaudio",
            audio_codec=AudioCodec.MP3,
            audio_quality="192",
        )
    )

    assert processor is not None
    assert processor.mapping == "mp3"
    assert processor._preferredquality == 192


def test_the_original_audio_preset_requests_no_conversion() -> None:
    """The other half of the pair. `ORIGINAL` carries yt-dlp's `best`, meaning "do not convert"."""
    processor = _audio_processor(
        request_for(
            media_kind=MediaKind.AUDIO,
            format_selector="bestaudio",
            audio_codec=AudioCodec.ORIGINAL,
        )
    )

    assert processor is not None
    assert processor.mapping == "best"
    assert processor._preferredquality is None


def test_the_two_audio_presets_are_distinguishable() -> None:
    """Stated as its own case because indistinguishability *was* the defect.

    Two presets `REQ-006` requires to differ produced byte-identical configuration.
    """
    mp3 = _audio_processor(
        request_for(
            media_kind=MediaKind.AUDIO, format_selector="bestaudio", audio_codec=AudioCodec.MP3
        )
    )
    original = _audio_processor(
        request_for(
            media_kind=MediaKind.AUDIO,
            format_selector="bestaudio",
            audio_codec=AudioCodec.ORIGINAL,
        )
    )

    assert mp3 is not None and original is not None
    assert mp3.mapping != original.mapping


@pytest.mark.parametrize("codec", [c for c in AudioCodec if c is not AudioCodec.ORIGINAL])
def test_every_declared_codec_reaches_the_processor(codec: AudioCodec) -> None:
    """Class-level: a codec added to the enum but not translated would be silently ignored."""
    processor = _audio_processor(
        request_for(media_kind=MediaKind.AUDIO, format_selector="bestaudio", audio_codec=codec)
    )

    assert processor is not None
    assert processor.mapping == codec.value


def test_a_video_request_installs_no_audio_extraction() -> None:
    options = adapter.build_options(request_for(media_kind=MediaKind.VIDEO), "o.%(ext)s")
    assert "FFmpegExtractAudioPP" not in _constructed(options)


def test_embedding_subtitles_installs_the_embedding_postprocessor() -> None:
    """`embedsubtitles` was the same kind of ignored flag as `extractaudio`."""
    options = adapter.build_options(
        request_for(subtitle_languages=("en",), embed_subtitles=True), "o.%(ext)s"
    )
    installed = _constructed(options)
    assert "FFmpegEmbedSubtitlePP" in installed
    assert options["writesubtitles"] is True
    assert options["subtitleslangs"] == ["en"]


def test_subtitles_without_embedding_are_written_but_not_embedded() -> None:
    options = adapter.build_options(
        request_for(subtitle_languages=("en",), embed_subtitles=False), "o.%(ext)s"
    )
    assert "FFmpegEmbedSubtitlePP" not in _constructed(options)
    assert options["writesubtitles"] is True


def test_requested_post_processors_reach_the_library() -> None:
    """`DownloadRequest.post_processors` was accepted by the model and then ignored entirely."""
    options = adapter.build_options(
        request_for(post_processors=("FFmpegMetadata", "EmbedThumbnail")), "o.%(ext)s"
    )
    installed = _constructed(options)
    assert "FFmpegMetadataPP" in installed
    assert "EmbedThumbnailPP" in installed


def test_an_unknown_post_processor_is_refused_rather_than_dropped() -> None:
    """Silently discarding it is the same defect class as the two above.

    Validated against yt-dlp's own registry, so the check cannot drift from what the pinned
    version actually provides.
    """
    with pytest.raises(adapter.UnsupportedPostProcessorError) as caught:
        adapter.build_options(request_for(post_processors=("NotARealPostProcessor",)), "o.%(ext)s")
    assert "NotARealPostProcessor" in str(caught.value)


def test_an_unknown_post_processor_classifies_as_a_post_processing_failure() -> None:
    """Not `EXTRACTOR_ERROR`: the site is fine, the configuration is not."""
    error = adapter.UnsupportedPostProcessorError("unknown post-processor 'X'")
    assert adapter.classify_exception(error).kind is ErrorKind.FFMPEG_ERROR


def test_the_audio_postprocessor_is_not_installed_twice() -> None:
    """An audio request that also names the processor explicitly must not stack it."""
    options = adapter.build_options(
        request_for(media_kind=MediaKind.AUDIO, post_processors=("FFmpegExtractAudio",)),
        "o.%(ext)s",
    )
    assert _constructed(options).count("FFmpegExtractAudioPP") == 1


@pytest.mark.parametrize("probe_only", [True, False])
def test_connection_settings_apply_to_both_phases(probe_only: bool) -> None:
    """`T012-R5`: a download probes first, and the probe used to get none of these.

    A URL needing the configured proxy or cookies therefore failed during the probe, before the
    download that would have used them was attempted — with the option set correctly all along.
    """
    options = adapter.build_options(
        request_for(
            proxy="socks5://127.0.0.1:9050",
            cookies_from_browser="firefox",
            rate_limit_bytes=1024,
        ),
        "o.%(ext)s",
        probe_only=probe_only,
    )
    assert options["proxy"] == "socks5://127.0.0.1:9050"
    assert options["cookiesfrombrowser"] == ("firefox",)
    assert options["ratelimit"] == 1024


@pytest.mark.parametrize("probe_only", [True, False])
def test_the_resolved_ffmpeg_location_reaches_yt_dlp(probe_only: bool) -> None:
    """`OPS-001`: the worker gates on a specific binary; yt-dlp otherwise does its own lookup."""
    options = adapter.build_options(
        request_for(), "o.%(ext)s", probe_only=probe_only, ffmpeg_location=Path("/opt/ff/ffmpeg")
    )
    assert options["ffmpeg_location"] == str(Path("/opt/ff/ffmpeg"))


def test_hooks_are_passed_through_so_progress_can_be_reported() -> None:
    def hook(_status: dict[str, Any]) -> None:
        return None

    options = adapter.build_options(
        request_for(), "o.%(ext)s", progress_hooks=[hook], postprocessor_hooks=[hook]
    )
    assert options["progress_hooks"] == [hook]
    assert options["postprocessor_hooks"] == [hook]
