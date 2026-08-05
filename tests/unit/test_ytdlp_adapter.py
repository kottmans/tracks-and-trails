"""The yt-dlp adapter: projection, classification, and options (`T-012`).

Everything here runs against the **recorded fixture**, never the network (`ai/TESTING.md` §2,
§5). The fixture is a contract: changing a key the projection reads must fail a test, which is
the only reason recording it is worth the maintenance.

`ai/TESTING.md` §13 applies throughout — expectations are transcribed from `ARCHITECTURE.md`
§5 and §7, never read back out of the adapter.
"""

import contextlib
import json
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

    media = adapter.project_media(info)

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

    media = adapter.project_media(info)

    assert len(media.entries) == 1, f"an unreadable entry became a job: {media.entries}"
    assert media.entry_count == 3, (
        "the count shrank to what could be read, so the playlist reports itself smaller than the "
        "site says it is"
    )


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

    media = adapter.project_media(info)

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

    entries = adapter.project_media(info).entries

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

    assert adapter.project_media(flat).thumbnail_url == "https://img.invalid/list-large.jpg", (
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
