"""The yt-dlp adapter: projection, classification, and options (`T-012`).

Everything here runs against the **recorded fixture**, never the network (`ai/TESTING.md` §2,
§5). The fixture is a contract: changing a key the projection reads must fail a test, which is
the only reason recording it is worth the maintenance.

`ai/TESTING.md` §13 applies throughout — expectations are transcribed from `ARCHITECTURE.md`
§5 and §7, never read back out of the adapter.
"""

import contextlib
import json
import logging
from pathlib import Path
from typing import Any, Final, cast

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
from tracks_and_trails.core.logging import redact
from tracks_and_trails.core.models import (
    AudioCodec,
    DownloadRequest,
    FormatInfo,
    MediaInfo,
    MediaKind,
)
from tracks_and_trails.core.paths import APP_SLUG
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


def _nothing_answers(_url: str) -> bool:
    """A reachability probe that never answers, so no test reaches the network (`T-161`).

    **Returning `False` is the honest default for a test, not a convenience.** `_entry_thumbnail`
    falls back to the best guess when nothing answers, so every assertion written before `T-161`
    keeps its meaning: they are about the *ordering*, and ordering is what the fallback preserves.
    A probe that answered `True` would silently make them about the first candidate instead.
    """
    return False


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
    baseline = adapter.project_media(info, reachable=_nothing_answers)
    del info[key]
    assert adapter.project_media(info, reachable=_nothing_answers) != baseline


def test_probe_projects_every_declared_field() -> None:
    """Field by field, against values read from the fixture rather than hardcoded.

    Hardcoding `"Big Buck Bunny"` would pass if the projection returned a constant; comparing
    against the fixture's own values proves the data made the journey.
    """
    info = load_fixture()
    media = adapter.project_media(info, reachable=_nothing_answers)

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
    media = adapter.project_media(info, reachable=_nothing_answers)

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
    # `original_url` carries the same value
    assert adapter.project_media(info, reachable=_nothing_answers).url == expected

    info["original_url"] = ""
    info["url"] = "https://fallback.example/x"
    assert (
        adapter.project_media(info, reachable=_nothing_answers).url == "https://fallback.example/x"
    )


def test_a_missing_title_falls_back_to_the_url_not_to_a_placeholder() -> None:
    """`MediaInfo` requires a displayable title; inventing "Untitled" would be worse."""
    info = load_fixture()
    info["title"] = ""
    assert adapter.project_media(info, reachable=_nothing_answers).title == info["webpage_url"]


def test_yt_dlp_none_codecs_become_none_not_the_string() -> None:
    """`'none'` is yt-dlp's way of saying a stream is absent, not a codec called "none"."""
    projected = adapter.project_format({"format_id": "1", "ext": "m4a", "vcodec": "none"})
    assert projected.video_codec is None
    assert projected.is_audio_only is False or projected.audio_codec is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"vcodec": "avc1.640028"}, True),
        ({"vcodec": "none"}, False),
        ({}, None),
        ({"vcodec": None}, None),
        ({"vcodec": ""}, None),
        # `yt-dlp -F` prints `unknown` for archive.org's derivatives, and the raw field carries the
        # same word. Reading it as a codec name would say *"this format has video"* about every one
        # of them, which is the `T107-R1` divergence arriving in a different field.
        ({"vcodec": "unknown"}, None),
        ({"vcodec": "UNKNOWN"}, None),
    ],
)
def test_the_projection_keeps_an_absent_stream_apart_from_an_unknown_one(
    raw: dict[str, object], expected: bool | None
) -> None:
    """`T-108`: three states out of one yt-dlp field (`REQ-008`, `NFR-008`).

    `_as_optional_codec` collapses `'none'` and *missing* into `None`, which is correct for a codec
    *name* and unusable for *"is there a video stream here"* — the question `REQ-008` must answer
    before it can route a format into a video or an audio slot. The adapter is the only place the
    difference is still visible, so it is the only place it can be recorded.
    """
    projected = adapter.project_format({"format_id": "1", "ext": "mp4", **raw})
    assert projected.has_video is expected


def test_the_two_streams_are_classified_independently() -> None:
    """media.ccc.de reports `vcodec: none` beside a named `acodec` — a real recorded shape.

    Asserted as a pair rather than one field at a time, because the failure this guards against is
    one answer leaking into the other: an audio-only format must come out *audio-only*, not
    *unknown*, and the same item's video recordings — which name a `vcodec` and no `acodec` at all
    — must come out **unknown** rather than video-only.
    """
    audio = adapter.project_format(
        {"format_id": "eng-mp3", "ext": "mp3", "vcodec": "none", "acodec": "mp3"}
    )
    assert (audio.has_video, audio.has_audio) == (False, True)
    assert audio.is_audio_only and not audio.is_video_only

    video = adapter.project_format({"format_id": "eng-h264-hd", "ext": "mp4", "vcodec": "h264"})
    assert (video.has_video, video.has_audio) == (True, None)
    assert not video.is_video_only, "silence about audio was read as an absent audio stream"


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
    assert (
        len(adapter.project_media(info, reachable=_nothing_answers).formats)
        == len(info["formats"]) - 1
    )


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


def test_a_partially_protected_item_is_treated_as_protected() -> None:
    """Changed by `T-057`, and the change is the point.

    This read `assert not adapter.has_drm(...)`, arguing that one clean format means there is
    something lawful to fetch. The argument is reasonable; the problem is that it described a
    branch which does not run. `_has_drm` — the field the branch above reads, and the one every
    real info dict carries — is computed by yt-dlp as `any`, so production already refused a
    mixed item. The two halves of one function disagreed, and the test asserted the half that
    never answers.

    Aligned on `any`, which is also the answer `SEC-001` wants: this project does not go looking
    for a non-DRM route through an item that has been flagged.
    """
    assert adapter.has_drm({"formats": [{"has_drm": True}, {"has_drm": False}]})


def test_a_format_yt_dlp_is_unsure_about_is_not_treated_as_protected() -> None:
    """`'maybe'` is a third state, and Python's truthiness collapsed it into the wrong one.

    yt-dlp keeps `has_drm='maybe'` formats downloadable and excludes them from `_has_drm`. A
    non-empty string is truthy, so the previous `all(entry.get("has_drm") ...)` read a set of
    them as protected — fail-safe in direction, and therefore never a `SEC-001` breach, but a
    user told an item is DRM-protected when yt-dlp would have downloaded it (`T-057`).
    """
    assert not adapter.has_drm({"formats": [{"has_drm": "maybe"}, {"has_drm": "maybe"}]})
    assert adapter.has_drm({"formats": [{"has_drm": "maybe"}, {"has_drm": True}]})


def test_drm_detection_does_not_read_message_text() -> None:
    """The prose says DRM; the structure does not. Structure wins (`ai/TESTING.md` §13)."""
    assert not adapter.has_drm({"title": "This video is DRM protected", "formats": []})


# --- the upstream contract this boundary rests on (`T-057`, `NFR-008`) ------------------------
#
# `tests/fixtures/errors/` pins the exception *types* this adapter maps, so an upstream rename
# fails a test instead of a download. DRM never got the same treatment, and it is the one
# boundary `SEC-001` calls non-negotiable: `has_drm` reads a single yt-dlp field, and the DRM
# fixture is `derived` by design — capturing a real one means probing a DRM service, which
# `REQ-EXCL-001` puts out of scope — so nothing established that yt-dlp still *writes* it.
#
# On a rename `has_drm` returns `False`, the item is never classified, and the product tries to
# download it: a non-negotiable boundary failing silently. These two tests are the canary.
#
# **They drive yt-dlp's own code and reach no network.** `process_video_result` writes the field
# before it selects anything, and the guard below fails the test if a name is resolved — the
# claim "no packet leaves the machine" is gated rather than asserted in prose.

#: Params that keep format selection from *testing* formats. Without them a `'maybe'` format
#: sends yt-dlp looking for a host, which was measured: two DNS lookups for `.invalid`.
_OFFLINE_PARAMS: Final[dict[str, Any]] = {
    "quiet": True,
    "simulate": True,
    "skip_download": True,
    "format": "all",
    "check_formats": False,
}


def _what_yt_dlp_says(formats: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch) -> Any:
    """Run yt-dlp's own DRM computation over `formats` and return the `_has_drm` it wrote."""
    import socket

    from yt_dlp import YoutubeDL

    # **Recorded as well as refused.** Raising alone does not gate anything: yt-dlp catches
    # whatever a handler raises and re-reports it as `NoSupportingHandlers`, which the suppression
    # below then swallows — so the guard was neutralised by the very thing that makes the call
    # survivable. The attempt is therefore remembered and checked afterwards, outside it.
    attempts: list[tuple[Any, ...]] = []

    def refuse(*args: Any, **kwargs: Any) -> Any:
        attempts.append(args)
        raise AssertionError("the contract check tried to resolve a name")

    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    payload: dict[str, Any] = {
        "id": "x",
        "title": "t",
        "extractor": "test",
        "extractor_key": "Test",
        "webpage_url": "https://example.invalid/x",
        "webpage_url_basename": "x",
        "formats": formats,
    }
    # Mutates `payload` in place, and the write happens before format selection can fail — so an
    # item whose every format is protected still tells us what we came to ask. The outcome of the
    # call is not the subject; the field it wrote on the way is.
    with contextlib.suppress(Exception):
        YoutubeDL(_OFFLINE_PARAMS).process_video_result(payload, download=False)
    assert not attempts, (
        f"the contract check reached for the network: {attempts!r}. It must stay offline — "
        "`REQ-EXCL-001` puts probing a DRM service out of scope, and a unit test that resolves "
        "a name is one that fails on a machine with no DNS."
    )
    return payload.get("_has_drm")


def test_yt_dlp_still_writes_the_field_this_boundary_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The canary. Verified against yt-dlp 2026.7.4, the version `pyproject.toml` pins.

    If this fails, `_has_drm` has been renamed or stopped being written, and `has_drm` is
    silently answering `False` for everything. That is not a test failure to route around: it
    means the DRM boundary is open until the adapter is taught the new contract.
    """
    protected = [{"format_id": "a", "url": "https://example.invalid/a", "has_drm": True}]
    assert _what_yt_dlp_says(protected, monkeypatch), (
        "yt-dlp no longer writes _has_drm for a protected format; SEC-001's detection rests on "
        "that field and is now blind. See T-057."
    )


@pytest.mark.parametrize(
    ("case", "flags"),
    [
        ("none", [None, None]),
        ("all protected", [True, True]),
        ("mixed", [True, None]),
        ("all undecided", ["maybe", "maybe"]),
        ("one undecided, one protected", ["maybe", True]),
    ],
)
def test_the_adapter_and_yt_dlp_agree_about_every_shape_of_has_drm(
    case: str, flags: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fallback's rule, compared against the rule itself rather than against a transcription.

    This is what `T-057` exists for. Both divergences it fixed — `'maybe'` counting as DRM, and
    `all` where yt-dlp uses `any` — were invisible to a test that stated the expected answer,
    because the expected answer was written by the same person who wrote the code. Here yt-dlp
    computes the expectation.
    """
    formats: list[dict[str, Any]] = [
        {"format_id": f"f{index}", "url": f"https://example.invalid/f{index}"}
        for index, _ in enumerate(flags)
    ]
    for entry, flag in zip(formats, flags, strict=True):
        if flag is not None:
            entry["has_drm"] = flag

    upstream = bool(_what_yt_dlp_says([dict(entry) for entry in formats], monkeypatch))
    # The fallback branch specifically: no `_has_drm`, so the per-format flags have to answer.
    ours = adapter.has_drm({"formats": formats})
    assert ours is upstream, (
        f"{case}: this adapter says {ours} and yt-dlp says {upstream}; the fallback is computing "
        "a different rule from the field it falls back from"
    )


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
    # **The four-tuple yt-dlp's own `_parse_browser_specification` takes** (`T197-R2`). This was
    # `("firefox",)`, which happens to work for a bare browser name and rejects every profile-
    # bearing specification at the library boundary — the string becomes the browser name.
    assert options["cookiesfrombrowser"] == ("firefox", None, None, None)
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


# --- T-084: the logger, and the flag that must not accompany it -------------------------------


def test_a_logger_is_passed_through_so_yt_dlp_s_diagnostics_are_reachable() -> None:
    """`REQ-019`. Without this yt-dlp writes to a console the worker does not have."""
    sentinel = object()

    options = adapter.build_options(request_for(), "%(title)s.%(ext)s", logger=sentinel)

    assert options["logger"] is sentinel


def test_no_logger_means_no_logger_key() -> None:
    """A probe run by a test has no parent to send records to, and `None` is not a logger."""
    assert "logger" not in adapter.build_options(request_for(), "%(title)s.%(ext)s")


def test_verbose_is_never_enabled() -> None:
    """**A security assertion, not a volume one** (`T-084`, `DAT-003`).

    Measured against yt-dlp 2026.07.04: `verbose` makes it dump `params:` and `Proxy map:`, which
    carry the proxy URL and `cookiesfrombrowser` — **values this application supplies**, the one
    row of `DAT-003`'s provenance table that must never reach a log. The version banner a bug
    report wants is written by `worker._log_the_session_header` instead, where every field is ours.

    Asserted **here** rather than in the end-to-end test, where the equivalent assertion is a guard
    that cannot fire: yt-dlp's verbose lines are prefixed `[debug]`, `YtdlpLog` sends those to
    `DEBUG`, and the worker's handler sits at `INFO`, so they would be dropped for a second and
    unrelated reason. A test that passes for a reason other than the one it names proves nothing
    (`ai/TESTING.md` §13).
    """
    for options in (
        adapter.build_options(request_for(), "%(title)s.%(ext)s"),
        adapter.build_options(request_for(), "%(title)s.%(ext)s", logger=object()),
        adapter.build_options(request_for(), "%(title)s.%(ext)s", probe_only=True, logger=object()),
    ):
        assert not options.get("verbose"), (
            "verbose dumps params and the proxy map — values this application supplied"
        )


# --- T-137: a playlist's entries -------------------------------------------------------------


def test_a_playlist_projects_its_entries_in_order() -> None:
    """`T-137`: the projection used to read `len(entries)` and nothing else.

    Built from a literal info dict rather than a recorded fixture **because no recorded fixture
    can exercise this yet**: `tests/fixtures/capture.py` blanks every entry to `{}` on the stated
    premise that the projection reads only the count, and lifting that premise means recording
    every entry's URL and title — a `SEC-002` question this task did not decide on its own.
    """
    info = {
        "_type": "playlist",
        "title": "Trail Sounds",
        "webpage_url": "https://example.invalid/list",
        "playlist_count": 3,
        "entries": [
            {"url": "https://example.invalid/a", "title": "One", "duration": 61.5},
            {"url": "https://example.invalid/b", "title": "Two"},
            {"webpage_url": "https://example.invalid/c", "title": "Three"},
        ],
    }

    media = adapter.project_media(info, reachable=_nothing_answers)

    assert [entry.title for entry in media.entries] == ["One", "Two", "Three"], (
        "the entries are not projected in the order the playlist gave them, so a queue built "
        "from them would not be in the playlist's order"
    )
    assert media.entries[0].duration_seconds == 61.5
    assert media.entries[2].url == "https://example.invalid/c", (
        "an entry naming itself with `webpage_url` rather than `url` was dropped"
    )


def test_an_unreadable_entry_is_dropped_but_still_counted() -> None:
    """A deleted or private item keeps its slot in yt-dlp's list, as `None`.

    **Dropped from `entries`, kept in `entry_count`.** A job pointing at nothing fails at download
    time with nothing useful to say; a count that shrank would tell the user the playlist was
    smaller than it is. The two fields answer different questions and this is the case that
    separates them.
    """
    info = {
        "_type": "playlist",
        "title": "Partly gone",
        "webpage_url": "https://example.invalid/list",
        "playlist_count": 3,
        "entries": [{"url": "https://example.invalid/a", "title": "One"}, None, {}],
    }

    media = adapter.project_media(info, reachable=_nothing_answers)

    assert len(media.entries) == 1, f"an unreadable entry became a job: {media.entries}"
    assert media.entry_count == 3, (
        "the count shrank to what could be read, so the playlist reports itself smaller than the "
        "site says it is"
    )


def test_a_placeholder_entry_that_still_has_an_address_is_dropped() -> None:
    """`T-281`: the guard tested the address, and a YouTube placeholder still has one.

    **This is the case the old guard passed.** Measured on 2026-08-27 against a real playlist:
    the extractor logged *"2 unavailable videos are hidden"* and the two entries arrived with an
    address composed from the id they still held, and `title` and `duration` `None`. `if not url`
    let them through, `title or url` put the raw address in the title column, and both reached the
    queue to fail there.
    """
    info = {
        "_type": "playlist",
        "title": "Partly gone",
        "webpage_url": "https://example.invalid/list",
        "playlist_count": 3,
        "entries": [
            {"url": "https://example.invalid/a", "title": "One"},
            {"url": "https://example.invalid/watch", "title": None, "duration": None},
            {"url": "https://example.invalid/watch", "title": "   ", "duration": None},
        ],
    }

    media = adapter.project_media(info, reachable=_nothing_answers)

    assert [entry.title for entry in media.entries] == ["One"], (
        "an entry yt-dlp could not name was projected anyway, so its address became its title "
        f"and a job pointing at nothing reached the queue: {media.entries}"
    )
    assert media.entry_count == 3, "the count shrank to what could be read"


def test_the_recorded_playlist_of_unreadable_entries_projects_only_the_readable_ones() -> None:
    """The same case offline, in the shape a real extraction produces (`T-281`).

    The literal above states the rule; this proves it against a fixture with the surrounding
    fields a real capture carries, so the rule is not true only of a dict written to satisfy it.
    """
    info = load_fixture("derived_playlist_with_unavailable_entries")

    media = adapter.project_media(info, reachable=_nothing_answers)

    assert len(media.entries) == 7, (
        f"the two unreadable entries were projected: {[e.title for e in media.entries]}"
    )
    assert media.entry_count == 9, (
        "the count shrank to what could be read, so the group reports itself smaller than the "
        "site says it is"
    )
    assert all(entry.title and not entry.title.startswith("http") for entry in media.entries), (
        "an entry is carrying its own address as its title"
    )


def test_the_dropped_entries_are_logged_with_the_playlist_and_their_positions(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`T-281`: a playlist that comes back short says so somewhere durable.

    **Positions, not ids or URLs, and the reasons are in `_entries`.** A URL loses its query to
    `RedactingFormatter` — which is where a video id lives — and reading the `id` would put it in
    the fixture allowlist that `capture.py` currently strips it out of.

    **The line is asserted through `redact` as well as raw**, because a log line that cannot
    survive redaction is a log line that says nothing in the file it is written to.
    """
    info = load_fixture("derived_playlist_with_unavailable_entries")

    with caplog.at_level(logging.INFO, logger=f"{APP_SLUG}.adapter"):
        adapter.project_media(info, reachable=_nothing_answers)

    lines = [record.getMessage() for record in caplog.records]
    assert len(lines) == 1, f"expected exactly one line about the drop, got {lines}"
    line = lines[0]
    assert "dropped 2 of 9" in line, line
    assert "position 8" in line and "position 9" in line, (
        f"the line does not say which entries went, so it cannot be acted on: {line}"
    )
    assert redact(line) == line, (
        f"the line does not survive redaction, so the log file will not carry what it says: "
        f"{redact(line)!r}"
    )


def test_a_playlist_with_nothing_dropped_says_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A line per probe that reports zero is noise, and noise is what stops a log being read."""
    info = load_fixture("archive_org_art_of_war_playlist")

    with caplog.at_level(logging.INFO, logger=f"{APP_SLUG}.adapter"):
        adapter.project_media(info, reachable=_nothing_answers)

    assert not caplog.records, f"a playlist that lost nothing still logged: {caplog.records}"


def test_a_lazily_paginated_playlist_is_not_consumed_while_probing() -> None:
    """A generator of entries is what a paginated playlist supplies.

    Walking it here would fetch the whole playlist during a probe — the cost `project_media` has
    refused since `T-016`, and `_entry_count` refuses in the same breath for the same reason.
    """
    consumed = False

    def entries() -> object:
        nonlocal consumed
        consumed = True
        yield {"url": "https://example.invalid/a", "title": "One"}

    info = {
        "_type": "playlist",
        "title": "Lazy",
        "webpage_url": "https://example.invalid/list",
        "entries": entries(),
    }

    media = adapter.project_media(info, reachable=_nothing_answers)

    assert not consumed, "probing walked a lazy playlist, fetching every page of it"
    assert media.entries == ()
    assert media.is_playlist, "a playlist that was not enumerated is still a playlist"


def test_a_probe_enumerates_a_playlist_flatly_and_a_download_does_not() -> None:
    """`T-137`: probing a playlist must not cost one full extraction per entry.

    Without `extract_flat`, yt-dlp extracts every entry in full just to answer "what is this URL",
    so a sixteen-item playlist is sixteen extractions before the user has agreed to anything.

    **Both halves, because the option is wrong on a download.** A download needs its item
    extracted properly; given a stub it would have no formats to choose from. A test asserting
    only that the probe sets it would pass with it set on everything.
    """
    request = DownloadRequest(
        url="https://example.invalid/list",
        output_directory="/downloads",
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )

    probe = adapter.build_options(request, "%(title)s.%(ext)s", probe_only=True)
    download = adapter.build_options(request, "%(title)s.%(ext)s")

    assert probe["extract_flat"] == "in_playlist", (
        "a probe extracts every playlist entry in full, so reading a long playlist costs one "
        "extraction per item"
    )
    assert "extract_flat" not in download, (
        "a download was asked for a flat extraction, so it has a stub instead of an item and no "
        "formats to choose from"
    )


def test_a_flat_entry_takes_its_picture_from_the_thumbnails_list() -> None:
    """`T-137`, corrected: every entry of a real playlist drew the derived tile.

    **A flat extraction rarely carries `thumbnail`.** It carries `thumbnails`, a list ordered
    worst-first, and reading only the singular is why a directly pasted URL showed its picture —
    the full extraction a single video gets *does* supply `thumbnail` — while none of a playlist's
    sixteen entries did. The defect looked like "thumbnails are broken" and was "one of the two
    shapes yt-dlp uses was never read".

    Both shapes, and the ordering, because taking the first of the list would prefer the worst.
    """
    info = {
        "_type": "playlist",
        "title": "Trail Sounds",
        "webpage_url": "https://example.invalid/list",
        "entries": [
            {
                "url": "https://example.invalid/a",
                "title": "Listed",
                "thumbnails": [
                    {"url": "https://img.invalid/small.jpg"},
                    {"url": "https://img.invalid/large.jpg"},
                ],
            },
            {
                "url": "https://example.invalid/b",
                "title": "Singular",
                "thumbnail": "https://img.invalid/one.jpg",
            },
            {"url": "https://example.invalid/c", "title": "None at all"},
        ],
    }

    entries = adapter.project_media(info, reachable=_nothing_answers).entries

    assert entries[0].thumbnail_url == "https://img.invalid/large.jpg", (
        "an entry carrying `thumbnails` got no picture, so every row of a playlist draws the "
        "derived tile; and the *last* is the best, since yt-dlp orders them worst-first"
    )
    assert entries[1].thumbnail_url == "https://img.invalid/one.jpg", (
        "the singular shape stopped being read"
    )
    assert entries[2].thumbnail_url is None, "an entry with no picture invented one"


def test_a_flat_entry_keeps_an_address_a_new_extraction_can_open() -> None:
    """Reviewer regression for `T-137`: a flat entry can require its extractor key.

    yt-dlp resolves a playlist entry internally as ``url`` plus ``ie_key``. Some extractors put
    only an id in that first field; it is not a URL that a fresh yt-dlp invocation can route on
    its own. When the processed entry also supplies its public ``webpage_url``, that is the value
    a durable standalone job has to keep. Literal full-URL fixtures cannot expose the distinction.
    """
    media = adapter.project_media(
        {
            "_type": "playlist",
            "title": "Extractor-directed entries",
            "webpage_url": "https://example.invalid/list",
            "entries": [
                {
                    "_type": "url",
                    "url": "abc123",
                    "ie_key": "Youtube",
                    "webpage_url": "https://www.youtube.com/watch?v=abc123",
                    "title": "One",
                }
            ],
        }
    )

    assert media.entries[0].url == "https://www.youtube.com/watch?v=abc123", (
        "the durable job kept yt-dlp's extractor-local value and discarded the public URL; "
        "the later worker no longer has ie_key='Youtube' and cannot route that value"
    )


def test_the_default_probe_really_asks_and_really_skips_a_refusal() -> None:
    """`T161-R1`: the four tests below inject `reachable` and never reach what supplies it.

    **Replacing `_url_answers` with `lambda _: False` left all of them green.** They prove the
    chooser given an oracle; nothing proved the oracle. That is this project's recurring shape
    once more — a test arranging the condition the defect would be about — and it is the third
    instance in this round.

    **A real server on loopback, not the network.** Hermetic and offline: one address answers 404
    and the next answers 200, and the *default* path has to tell them apart. `_url_answers`
    returning a constant fails this in either direction — always-`False` picks the refusal,
    always-`True` picks it too.
    """
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_HEAD(self) -> None:
            self.send_response(404 if self.path == "/best.jpg" else 200)
            self.end_headers()

        def log_message(self, *_args: object) -> None:
            """Silence. The test asserts on the choice, not on a server's console."""

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        answers = f"http://127.0.0.1:{port}/next.jpg"
        flat = {
            "_type": "playlist",
            "id": "pl-1",
            "title": "Trail Sounds",
            "webpage_url": "https://example.invalid/list",
            "thumbnails": [
                {"url": answers},
                {"url": f"http://127.0.0.1:{port}/best.jpg"},
            ],
            "entries": [],
        }

        media = adapter.project_media(flat)

        assert media.thumbnail_url == answers, (
            f"the default probe chose {media.thumbnail_url!r}. The best address answers 404 and "
            "the next answers 200, so a chooser actually asking must take the second — this is "
            "the only test that touches `_url_answers` rather than a substitute for it"
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_a_playlists_entries_are_never_probed() -> None:
    """`T161-R1`: `T-161`'s own criterion is **no probe-time network request per entry**.

    The first correction threaded the probe through `_entries`, so a sixteen-entry playlist made a
    HEAD walk per entry — the very thing this task's rejected-options list already recorded as
    *"correct and unacceptable"*. At four seconds a candidate the worst case grows with
    entries times candidates and can hold an add dialog for minutes with no user workaround.

    Counted rather than timed: a duration assertion would be flaky and would not say *why* it was
    slow.
    """
    asked: list[str] = []
    flat = {
        "_type": "playlist",
        "id": "pl-1",
        "title": "Trail Sounds",
        "webpage_url": "https://example.invalid/list",
        "thumbnails": [
            {"url": "https://img.invalid/parent-small.jpg"},
            {"url": "https://img.invalid/parent-large.jpg"},
        ],
        "entries": [
            {
                "url": f"https://example.invalid/{name}",
                "title": name,
                "thumbnails": [
                    {"url": f"https://img.invalid/{name}-small.jpg"},
                    {"url": f"https://img.invalid/{name}-large.jpg"},
                ],
            }
            for name in ("a", "b", "c")
        ],
    }

    def _record(url: str) -> bool:
        asked.append(url)
        return True

    media = adapter.project_media(flat, reachable=_record)

    assert asked == ["https://img.invalid/parent-large.jpg"], (
        f"projection asked about {asked}; only the playlist's own picture may cost a request, and "
        "three entries turned one probe into four"
    )
    assert [entry.thumbnail_url for entry in media.entries] == [
        "https://img.invalid/a-large.jpg",
        "https://img.invalid/b-large.jpg",
        "https://img.invalid/c-large.jpg",
    ], "an entry still takes its best candidate, exactly as it did before `T-161`"


def test_a_playlist_skips_a_thumbnail_address_that_does_not_answer() -> None:
    """`T-161`, `P2EXIT-R12`: `T-153`'s criterion is that the row **shows** a picture.

    yt-dlp orders thumbnails worst-first and lists addresses it has **not** verified, so taking the
    last selected a `maxresdefault` that 404s — and `T-119`'s give-up-on-failure rule made the
    blank permanent. Measured on the maintainer's playlist: the 180px and 640px addresses answer
    200 with a signature, the 1200px bare path answers 404.

    **The old regression could not have caught this and passed throughout.** It asserted the
    *last* address was selected, which is exactly the behaviour that produced a blank tile —
    `P2EXIT-R12`'s point that proving an address is chosen is not proving a picture appears.

    Asserted through `project_media`, not the private helper, because the seam has to reach the
    boundary a caller actually uses.
    """
    answered = "https://img.invalid/works.jpg"
    flat = {
        "_type": "playlist",
        "id": "pl-1",
        "title": "Trail Sounds",
        "webpage_url": "https://example.invalid/list",
        "thumbnails": [
            {"url": "https://img.invalid/small.jpg"},
            {"url": answered},
            {"url": "https://img.invalid/guessed-maxres.jpg"},
        ],
        "entries": [],
    }

    media = adapter.project_media(flat, reachable=lambda url: url == answered)

    assert media.thumbnail_url == answered, (
        f"the playlist chose {media.thumbnail_url!r}; the best address that answers is "
        f"{answered!r}, and choosing one that does not leaves every playlist drawing a blank tile"
    )


def test_the_best_address_wins_when_more_than_one_answers() -> None:
    """`T-161`: reachability is a filter on the existing order, not a replacement for it.

    A fix that returned the first *answering* candidate in yt-dlp's own worst-first order would
    pass the test above and quietly give every row the 180px thumbnail. The converse has to hold:
    among addresses that answer, the best still wins.
    """
    flat = {
        "_type": "playlist",
        "id": "pl-1",
        "title": "Trail Sounds",
        "webpage_url": "https://example.invalid/list",
        "thumbnails": [
            {"url": "https://img.invalid/small.jpg"},
            {"url": "https://img.invalid/large.jpg"},
        ],
        "entries": [],
    }

    media = adapter.project_media(flat, reachable=lambda _url: True)

    assert media.thumbnail_url == "https://img.invalid/large.jpg", (
        f"every address answered and the playlist chose {media.thumbnail_url!r}; yt-dlp orders "
        "worst-first, so the best is the last"
    )


def test_a_lone_thumbnail_address_is_never_probed() -> None:
    """`T-161`: with nothing to choose between, a request can only make things worse.

    A probe against a single candidate spends a round trip inside a probe the user is waiting on,
    and its only possible effect is turning a picture that might have worked into no picture.
    """

    def _explode(_url: str) -> bool:
        raise AssertionError("a lone candidate was probed; there was nothing to choose between")

    flat = {
        "_type": "playlist",
        "id": "pl-1",
        "title": "Trail Sounds",
        "webpage_url": "https://example.invalid/list",
        "thumbnails": [{"url": "https://img.invalid/only.jpg"}],
        "entries": [],
    }

    assert adapter.project_media(flat, reachable=_explode).thumbnail_url == (
        "https://img.invalid/only.jpg"
    )


def test_nothing_answering_still_yields_the_best_guess() -> None:
    """`T-161`: never worse than what it replaced.

    Offline, or against a site that refuses `HEAD`, every candidate looks unreachable. Returning
    `None` there would take pictures away from users who had them for a rule meant to add some.
    """
    flat = {
        "_type": "playlist",
        "id": "pl-1",
        "title": "Trail Sounds",
        "webpage_url": "https://example.invalid/list",
        "thumbnails": [
            {"url": "https://img.invalid/small.jpg"},
            {"url": "https://img.invalid/large.jpg"},
        ],
        "entries": [],
    }

    media = adapter.project_media(flat, reachable=lambda _url: False)

    assert media.thumbnail_url == "https://img.invalid/large.jpg", (
        f"nothing answered and the playlist chose {media.thumbnail_url!r}; the best guess is still "
        "better than no picture at all"
    )


def test_thumbnail_reachability_is_not_probed_per_playlist_entry() -> None:
    """T-161 explicitly keeps per-entry network requests out of playlist projection."""
    asked: list[str] = []

    def answers(url: str) -> bool:
        asked.append(url)
        return True

    flat = {
        "_type": "playlist",
        "title": "Trail Sounds",
        "webpage_url": "https://example.invalid/list",
        "thumbnails": [
            {"url": "https://img.invalid/list-small.jpg"},
            {"url": "https://img.invalid/list-large.jpg"},
        ],
        "entries": [
            {
                "url": "https://example.invalid/a",
                "title": "A",
                "thumbnails": [
                    {"url": "https://img.invalid/a-small.jpg"},
                    {"url": "https://img.invalid/a-large.jpg"},
                ],
            },
            {
                "url": "https://example.invalid/b",
                "title": "B",
                "thumbnails": [
                    {"url": "https://img.invalid/b-small.jpg"},
                    {"url": "https://img.invalid/b-large.jpg"},
                ],
            },
        ],
    }

    adapter.project_media(flat, reachable=answers)

    assert asked == ["https://img.invalid/list-large.jpg"], (
        f"projecting one playlist made reachability requests for {asked}; T-161 permits choosing "
        "the playlist parent's picture at probe time, but explicitly forbids a network request "
        "per entry because a large playlist would multiply the four-second timeout by its size"
    )


def test_a_playlist_takes_its_own_picture_from_the_thumbnails_list() -> None:
    """`T-153`: the `T-137` correction reached the entries and not the playlist itself.

    **A playlist is probed with `extract_flat`, so its own top level is the flat shape too** — it
    carries `thumbnails` and no singular `thumbnail`. `_media_from` read only the singular, so the
    staged row for a playlist drew the derived tile while every one of its entries drew a picture,
    which looks like a different defect and is the same one a level up.

    The singular still works, because a single video's full extraction supplies it and that route
    must not break to fix this one.
    """
    flat = {
        "_type": "playlist",
        "title": "Trail Sounds",
        "webpage_url": "https://example.invalid/list",
        "thumbnails": [
            {"url": "https://img.invalid/list-small.jpg"},
            {"url": "https://img.invalid/list-large.jpg"},
        ],
        "entries": [{"url": "https://example.invalid/a", "title": "Listed"}],
    }

    assert (
        adapter.project_media(flat, reachable=_nothing_answers).thumbnail_url
        == "https://img.invalid/list-large.jpg"
    ), (
        "the playlist itself got no picture, so its staged row draws the derived tile while its "
        "entries draw theirs — the correction reached the children and not the parent"
    )

    singular = {**flat, "thumbnail": "https://img.invalid/one.jpg"}
    del singular["thumbnails"]
    assert adapter.project_media(singular).thumbnail_url == "https://img.invalid/one.jpg", (
        "the singular shape stopped being read, which is what a single video's full extraction "
        "supplies"
    )

    bare = {k: v for k, v in flat.items() if k != "thumbnails"}
    assert adapter.project_media(bare).thumbnail_url is None, (
        "a playlist with no picture invented one"
    )


@pytest.mark.parametrize("probe_only", [True, False])
def test_both_cookie_sources_reach_yt_dlp(probe_only: bool) -> None:
    """**`REQ-026`'s two sources, both arriving** (`T-197`), and by different routes on purpose.

    The browser name rides on the request, because it is a per-download choice a preset can carry.
    The **file** arrives as a session argument, because `DAT-003` forbids a cookie path this
    application supplies from reaching the model — and therefore the database. Asserted together,
    since the criterion is that *both* reach a real download rather than either one.

    Both phases, because `T012-R5` is the finding that connection settings applied only after the
    probe: a URL needing cookies failed while being read, before the download that would have used
    them was ever attempted.
    """
    options = adapter.build_options(
        request_for(cookies_from_browser="firefox"),
        "o.%(ext)s",
        probe_only=probe_only,
        cookie_file=Path("/home/sean/.config/tracksandtrails/cookies.txt"),
    )

    # **The four-tuple yt-dlp's own `_parse_browser_specification` takes** (`T197-R2`). This was
    # `("firefox",)`, which happens to work for a bare browser name and rejects every profile-
    # bearing specification at the library boundary — the string becomes the browser name.
    assert options["cookiesfrombrowser"] == ("firefox", None, None, None)
    assert options["cookiefile"] == str(Path("/home/sean/.config/tracksandtrails/cookies.txt"))


def test_no_cookie_file_means_no_cookiefile_option() -> None:
    """Absent is absent: yt-dlp is not handed an empty or `None` cookie file to interpret."""
    options = adapter.build_options(request_for(), "o.%(ext)s")

    assert "cookiefile" not in options


# --- network options reaching a real download (T-196) ---------------------------------------


@pytest.mark.parametrize("probe_only", [False, True])
def test_the_network_options_reach_the_options_yt_dlp_is_given(probe_only: bool) -> None:
    """**`T-196`'s first criterion**, asserted through what the adapter builds.

    Not against the stored value: `T-109` and `T195-R1` are both findings where a test asserted
    the *store* and was submitted as proof of the wiring, while the wiring was broken. The keys
    below are yt-dlp's own — `proxy`, `ratelimit` and `retries` — read from its source rather than
    recalled (`downloader/http.py` takes `retries`; `downloader/common.py` takes `ratelimit`).

    **Both phases**, because a proxy is exactly what `T012-R5` was about: connection settings
    applied only after the probe meant a URL needing the proxy failed while being read.
    """
    options = adapter.build_options(
        request_for(proxy="http://proxy.invalid:8080", rate_limit_bytes=524288, retries=2),
        "o.%(ext)s",
        probe_only=probe_only,
    )

    assert options["proxy"] == "http://proxy.invalid:8080"
    assert options["ratelimit"] == 524288
    assert options["retries"] == 2


def test_a_request_that_asks_for_no_retries_gets_none_rather_than_the_default() -> None:
    """**`0` is not falsy here, and truthiness is the bug this asserts against** (`T-196`).

    A `retries=0` dropped by an `if request.retries:` becomes yt-dlp's own default of ten — the
    user asked not to retry and got the opposite, silently. The rate limit above may be read by
    truthiness because zero bytes per second is not a thing anyone means; this may not.
    """
    options = adapter.build_options(request_for(retries=0), "o.%(ext)s")

    assert options["retries"] == 0


def test_a_request_that_says_nothing_about_the_network_leaves_the_keys_out() -> None:
    """Absent is absent: yt-dlp applies its own defaults rather than being handed `None`.

    This is what makes *"the downloader's own"* a real answer on the settings screen instead of a
    number this project would have to copy and keep in step.
    """
    options = adapter.build_options(request_for(), "o.%(ext)s")

    assert "proxy" not in options
    assert "ratelimit" not in options
    assert "retries" not in options


# --- REQ-EXCL-002: the geo exclusion is a default, not a refusal (`T183-R1`) -------------------


def test_geo_bypass_is_turned_off_rather_than_left_to_yt_dlps_default() -> None:
    """`SEC-003` forbids `--xff`, and refusing the option does not enforce the exclusion.

    **The behaviour is on unless it is turned off.** `InfoExtractor` reads
    `get_param('geo_bypass', True)`, so a caller that supplies nothing gets yt-dlp's automatic
    fake-`X-Forwarded-For` retry — which is the mechanism `REQ-EXCL-002` names, arriving with the
    user having typed nothing at all. `T-183`'s audit refused the *option strings* and left the
    default standing; that is the defect `T183-R1` found.

    Asserted for **both** phases: a probe extracts too, and an exclusion that binds only the
    download is not an exclusion.
    """
    for probe_only in (False, True):
        options = adapter.build_options(request_for(), "o.%(ext)s", probe_only=probe_only)
        assert options["geo_bypass"] is False, f"probe_only={probe_only}"


def test_the_geo_value_is_the_one_that_actually_disables_it() -> None:
    """`False`, not `'never'` — the library parameter is a bool and the command line is not.

    yt-dlp's own `__init__.py` converts `--xff never` with
    `opts.geo_bypass = opts.geo_bypass.lower() != 'never'` **before** `YoutubeDL` is constructed,
    so the string never reaches the library. Passing `'never'` here would be truthy and would
    enable exactly what it appears to disable — a fix that reads correct and is not.

    **This reads the application's own options dictionary, not yt-dlp's reader** — the claim that
    it exercised the library was an overstatement the `T-183` re-review caught. What it does catch
    is the two regressions that matter: the key going missing, and the truthy `'never'` spelling.
    Upstream drift is covered instead by the audit's pin check, which fails if the recorded yt-dlp
    version stops matching the installed one (`NFR-008`).
    """
    options = adapter.build_options(request_for(), "o.%(ext)s")

    assert options["geo_bypass"] is not None
    assert not options["geo_bypass"], "a truthy geo_bypass enables the bypass"
    # The value the application supplies must survive `get_param`'s default, which is `True`.
    assert options.get("geo_bypass", True) is False
