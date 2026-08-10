"""Built-in presets and the translation into a request (`T-015`, `REQ-006`, `REQ-009`).

Two rules from `ai/TESTING.md` §13 shape this file, and both are here because the project has
already been burned by their absence:

- **The expectation is transcribed from `REQ-006`, not read back out of the module.** A test
  that lists the preset names it expects and compares them with the names the module ships is
  two views of one hand-maintained set — the `T041-R2` shape, which passed while a whole model
  went uncovered. So the requirement is transcribed as *capabilities* below, and each is
  matched against what a preset actually produces.
- **What a preset computes must be shown to arrive.** Five of `T-012`'s defects were values
  computed correctly and then not acted on, including this exact one: an audio codec chosen and
  never requested. So the last section asserts through `ytdlp_adapter`, on the far side of the
  boundary, rather than on the request this module builds.
"""

from dataclasses import fields, replace
from typing import Any, Final

import pytest

from tracks_and_trails.core import presets
from tracks_and_trails.core.models import AudioCodec, DownloadRequest, MediaKind, Preset

URL = "https://example.com/watch?v=abc"
DIRECTORY = "/downloads"


def request_for(preset: Preset, **overrides: Any) -> DownloadRequest:
    return presets.to_request(preset, url=URL, output_directory=DIRECTORY, **overrides)


# --- REQ-006, transcribed --------------------------------------------------------------------
#
# "Provide named presets covering the common cases, at minimum: best video ≤1080p (MP4), best
# video available, audio only (MP3), audio only (best/original), and video with embedded
# subtitles."
#
# Each entry below is that sentence turned into a question about the *request* a preset
# produces. Nothing here reads `presets.BUILT_IN_PRESETS` to decide what to expect.


def _is_video(request: DownloadRequest) -> bool:
    return request.media_kind is MediaKind.VIDEO


def _capped_at_1080_mp4(request: DownloadRequest) -> bool:
    selector = request.format_selector
    return _is_video(request) and "height<=1080" in selector and "ext=mp4" in selector


def _best_video_available(request: DownloadRequest) -> bool:
    selector = request.format_selector
    return _is_video(request) and "height<=" not in selector and not request.embed_subtitles


def _audio_as_mp3(request: DownloadRequest) -> bool:
    return request.media_kind is MediaKind.AUDIO and request.audio_codec is AudioCodec.MP3


def _audio_untouched(request: DownloadRequest) -> bool:
    return request.media_kind is MediaKind.AUDIO and request.audio_codec is AudioCodec.ORIGINAL


def _video_with_embedded_subtitles(request: DownloadRequest) -> bool:
    return _is_video(request) and request.embed_subtitles and bool(request.subtitle_languages)


REQ_006_CASES = {
    "best video up to 1080p (MP4)": _capped_at_1080_mp4,
    "best video available": _best_video_available,
    "audio only (MP3)": _audio_as_mp3,
    "audio only (best/original)": _audio_untouched,
    "video with embedded subtitles": _video_with_embedded_subtitles,
}


@pytest.mark.parametrize("case", sorted(REQ_006_CASES))
def test_every_case_req_006_names_has_exactly_one_preset(case: str) -> None:
    """`REQ-006`'s five cases, each satisfied by exactly one built-in.

    "Exactly one", not "at least one": two presets answering the same case means the user is
    choosing between things that do the same thing, and the second is almost certainly a
    half-finished edit of the first.
    """
    matches = [
        preset for preset in presets.BUILT_IN_PRESETS if REQ_006_CASES[case](request_for(preset))
    ]
    assert len(matches) == 1, (
        f"{case!r} is answered by {[p.name for p in matches]}; REQ-006 requires exactly one"
    )


def test_no_built_in_preset_is_unaccounted_for() -> None:
    """The other direction, so this stays an equality rather than a subset (`ai/TESTING.md` §13).

    A subset check stays green when a preset is added that nothing describes — and an
    undescribed preset is one whose behaviour no test has an opinion about.
    """
    unmatched = [
        preset.name
        for preset in presets.BUILT_IN_PRESETS
        if not any(matches(request_for(preset)) for matches in REQ_006_CASES.values())
    ]
    assert not unmatched, (
        f"{unmatched} answer no case in REQ-006. Either the requirement grew and this file "
        "did not, or the preset does something nobody specified."
    )


def test_the_registry_is_not_empty() -> None:
    """Guards against every parametrised check above passing over nothing."""
    assert len(presets.BUILT_IN_PRESETS) >= len(REQ_006_CASES)


# --- REQ-009: one selector, and it is the one that runs --------------------------------------


@pytest.mark.parametrize("preset", presets.BUILT_IN_PRESETS, ids=lambda p: p.name)
def test_the_visible_selector_is_the_selector_that_downloads(preset: Preset) -> None:
    """`REQ-009`: the effective selector is visible, and *effective* is the load-bearing word.

    The failure this prevents is a preset that displays one string and downloads with another —
    which is not a hypothetical, but the natural result of adding a friendly label beside the
    real selector and letting the two drift.
    """
    assert presets.effective_selector(preset) == request_for(preset).format_selector


def test_a_raw_user_selector_survives_untouched() -> None:
    """`REQ-009`'s escape hatch, with a string the project cannot possibly understand.

    Deliberately nonsense: the criterion is that a user selector is not validated *for content*,
    and a well-formed one would pass whether or not anything was inspecting it. yt-dlp is the
    judge of whether this resolves, and its answer is not this module's business.
    """
    nonsense = "wobble[height<=frobnicate]+???/best{{"
    preset = presets.custom_preset(nonsense)

    assert preset.format_selector == nonsense
    assert presets.effective_selector(preset) == nonsense
    assert request_for(preset).format_selector == nonsense
    assert preset.built_in is False, "a user's own selector must not claim to ship with the app"


@pytest.mark.parametrize("empty", ["", None, 0])
def test_an_empty_or_non_string_selector_is_refused(empty: object) -> None:
    """The structural boundary `T-015` names, enforced where the value is constructed.

    `core/presets.py` deliberately does not re-check this: `Preset` makes it unrepresentable, so
    a second check could never be reached by a test. The behaviour the criterion asks for is
    asserted here instead — including through `custom_preset`, the one path a user's own string
    takes.
    """
    with pytest.raises((TypeError, ValueError)):
        presets.custom_preset(empty)  # type: ignore[arg-type]


@pytest.mark.parametrize("quality", ["0", "9", "128", "192", "320"])
def test_a_preset_may_carry_any_quality_yt_dlp_accepts(quality: str) -> None:
    """yt-dlp's `preferredquality` is a VBR level 0-9 **or** a kbps bitrate, sharing one field.

    Transcribed from that contract rather than from the validator: the two vocabularies are why
    the value is a string at all, and an `int` would make `0` (best VBR) mean 0 kbps.
    """
    built = Preset(
        name="Audio",
        media_kind=MediaKind.AUDIO,
        format_selector="bestaudio",
        output_template="%(title)s.%(ext)s",
        audio_codec=AudioCodec.MP3,
        audio_quality=quality,
    )
    assert built.audio_quality == quality


@pytest.mark.parametrize("quality", ["V0", "192k", "best", "-1", "1.5", "high"])
def test_a_preset_with_an_unusable_audio_quality_is_refused(quality: str) -> None:
    """Refused when the preset is built, not when the download finishes.

    yt-dlp rejects an unusable `preferredquality` at post-processing time — *after* the whole
    file has been fetched. A preset is chosen long before that, so the typo has to be caught
    here or the user pays for the download twice.
    """
    with pytest.raises(ValueError, match="audio_quality"):
        Preset(
            name="Audio",
            media_kind=MediaKind.AUDIO,
            format_selector="bestaudio",
            output_template="%(title)s.%(ext)s",
            audio_codec=AudioCodec.MP3,
            audio_quality=quality,
        )


def test_the_registry_check_catches_a_broken_entry() -> None:
    """`check_registry` must be able to fail, or importing this module proves nothing."""
    not_built_in = presets.custom_preset("best")
    with pytest.raises(ValueError, match="not built_in"):
        presets.check_registry((not_built_in,))

    duplicate = presets.BUILT_IN_PRESETS[0]
    with pytest.raises(ValueError, match="named"):
        presets.check_registry((duplicate, duplicate))


def test_an_unknown_preset_name_raises_rather_than_substituting_one() -> None:
    """A stored name this build no longer has is a disagreement, not a reason to pick a default."""
    assert presets.by_name(presets.BUILT_IN_PRESETS[0].name) is presets.BUILT_IN_PRESETS[0]
    with pytest.raises(KeyError, match="no built-in preset named"):
        presets.by_name("Best video, but faster")


# --- translation carries everything ----------------------------------------------------------

#: Field names a `Preset` and a `DownloadRequest` share, derived from both dataclasses rather
#: than listed. This is the half that must not be hand-maintained: a preset field added and not
#: translated is invisible to every other test in this file, and the request quietly keeps a
#: default the user did not choose.
SHARED_FIELDS = sorted(
    {field.name for field in fields(Preset)} & {field.name for field in fields(DownloadRequest)}
)


def test_the_two_models_actually_share_fields() -> None:
    """If the intersection ever empties, the test below would pass over nothing."""
    assert "format_selector" in SHARED_FIELDS
    assert len(SHARED_FIELDS) >= 6, SHARED_FIELDS


@pytest.mark.parametrize("preset", presets.BUILT_IN_PRESETS, ids=lambda p: p.name)
@pytest.mark.parametrize("field_name", SHARED_FIELDS)
def test_every_shared_field_reaches_the_request(preset: Preset, field_name: str) -> None:
    """Translation is a copy, and this is what makes that claim checkable.

    Derived from the dataclasses, so adding `Preset.container_format` without adding it to
    `to_request` fails here — rather than at the first download that quietly ignores it.
    """
    request = request_for(preset)
    assert getattr(request, field_name) == getattr(preset, field_name), (
        f"{preset.name!r} sets {field_name}={getattr(preset, field_name)!r}, but the request it "
        f"produced carries {getattr(request, field_name)!r}"
    )


def test_the_url_and_directory_are_the_two_things_a_preset_cannot_know() -> None:
    request = request_for(presets.BEST_VIDEO)
    assert request.url == URL
    assert request.output_directory == DIRECTORY


def test_overrides_apply_last_and_leave_the_preset_alone() -> None:
    """Settings a preset does not fix — a proxy, a rate limit — are the caller's to add.

    The preset must survive being used: it is a module-level constant, so a translation that
    mutated it would change every later download in the process.
    """
    before = presets.AUDIO_MP3
    request = request_for(
        presets.AUDIO_MP3, proxy="http://proxy.example:8080", rate_limit_bytes=1024
    )

    assert request.proxy == "http://proxy.example:8080"
    assert request.rate_limit_bytes == 1024
    assert request.audio_codec is AudioCodec.MP3, "the override erased the preset's own choice"
    assert before == presets.AUDIO_MP3


# --- what the selector actually picks (T015-R1) ----------------------------------------------
#
# Through yt-dlp's own selector engine, because the previous test asked whether the selector
# *string* contained `ext=mp4` — which stayed true while a later fallback branch permitted
# something else. A preset's name is a promise about the file that lands, and only the engine
# that resolves it can say what that file would be.


def selected_rows(selector: str, formats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every format row the pinned yt-dlp would choose for `selector`.

    Rows rather than extensions (`T015-R2`): the previous version returned only the container,
    so a *video-only* selection looked identical to a complete one. What a preset delivers is
    the whole set — its container **and** whether anyone can hear it.
    """
    from yt_dlp import YoutubeDL

    chosen = YoutubeDL({"quiet": True, "no_warnings": True}).build_format_selector(selector)
    picked = list(chosen({"formats": formats, "incomplete_formats": False}))
    # A merge is reported as one entry with `requested_formats`; flatten it so the assertions
    # below see what actually gets downloaded.
    rows: list[dict[str, Any]] = []
    for entry in picked:
        rows.extend(entry.get("requested_formats") or [entry])
    return rows


def has_audio(rows: list[dict[str, Any]]) -> bool:
    return any(row.get("acodec") not in (None, "none") for row in rows)


def format_row(**overrides: Any) -> dict[str, Any]:
    base = {
        "format_id": "f",
        "ext": "mp4",
        "height": 1080,
        "vcodec": "avc1",
        "acodec": "mp4a",
        "url": "https://example.com/f",
    }
    return {**base, **overrides}


#: One format set per selector alternative, each reachable **only** by that alternative
#: (`T015-R2`). The previous table's "720p" row was pre-muxed, so it was selected by the
#: *preceding* branch and the branch under test was never exercised at all.
ALTERNATIVE_CASES = {
    "merge an mp4 video with m4a audio": [
        format_row(format_id="v", acodec="none"),
        format_row(format_id="a", ext="m4a", vcodec="none", acodec="mp4a"),
    ],
    "take a pre-muxed mp4 when no separate audio exists": [format_row(format_id="m")],
}


@pytest.mark.parametrize("case", sorted(ALTERNATIVE_CASES))
def test_every_alternative_delivers_mp4_that_can_be_heard(case: str) -> None:
    """Each branch resolved by the real engine, asserting container **and** audio.

    `T015-R2` was a branch that satisfied the container half of the preset's name and silently
    dropped the sound. Asserting the extension alone is what let it through review-clean.
    """
    rows = selected_rows(
        presets.effective_selector(presets.BEST_VIDEO_1080P), ALTERNATIVE_CASES[case]
    )

    assert rows, f"the {case!r} case selected nothing"
    assert {row["ext"] for row in rows} <= {"mp4", "m4a"}, f"{case!r} delivered {rows}"
    assert has_audio(rows), f"{case!r} produced a video nobody can hear: {rows}"
    assert any(row.get("vcodec") not in (None, "none") for row in rows), f"{case!r} has no video"


@pytest.mark.parametrize(
    ("case", "formats"),
    [
        (
            "webm only",
            [format_row(format_id="w", ext="webm", height=720, vcodec="vp9", acodec="opus")],
        ),
        (
            "mp4 video with only non-mp4 audio",
            [
                format_row(format_id="v", height=720, acodec="none"),
                format_row(format_id="a", ext="webm", vcodec="none", acodec="opus"),
            ],
        ),
        ("mp4 above the height limit", [format_row(format_id="m", height=2160)]),
    ],
)
def test_the_preset_refuses_rather_than_delivering_something_else(
    case: str, formats: list[dict[str, Any]]
) -> None:
    """`T015-R1` and `T015-R2` share one cause: a fallback widened until something matched.

    Selecting nothing is the correct answer for all three. yt-dlp then says no format matched,
    verbatim (`REQ-005`), and the user reaches for "best video available" or their own selector
    — which is a choice they made, rather than a substitution nobody told them about.

    The middle case is `T015-R2`'s: merging that pair would produce an MKV, so honouring the
    "MP4" half of the name means declining, not merging.
    """
    rows = selected_rows(presets.effective_selector(presets.BEST_VIDEO_1080P), formats)

    assert rows == [], f"the {case!r} case delivered {rows}"


# --- overrides cannot contradict what was shown (T015-R1) -------------------------------------


@pytest.mark.parametrize("field_name", sorted(presets.PRESET_OWNED_FIELDS))
def test_a_preset_owned_field_cannot_be_overridden(field_name: str) -> None:
    """`REQ-009`'s promise, enforced against **every** field a preset owns.

    The finding was `format_selector`, where an override produced a request for `worst` while
    `effective_selector()` still displayed the preset's own string. The sibling audit is the
    reason this is parametrized over the fields derived from both dataclasses: `media_kind`,
    the codec and the subtitle settings are each equally capable of making the request stop
    being the preset that was chosen.
    """
    sample: dict[str, Any] = {
        "format_selector": "worst",
        "output_template": "%(id)s.%(ext)s",
        "media_kind": MediaKind.AUDIO,
        "post_processors": ("FFmpegMetadata",),
        "subtitle_languages": ("en",),
        "embed_subtitles": True,
        "audio_codec": AudioCodec.FLAC,
        "audio_quality": "0",
        # `REQ-010`'s other five (`T-109`). Each one changes what the finished file *is*, so an
        # override that reached them would make the request stop being the preset that was
        # displayed exactly as `format_selector` did — a preset called "Best video available"
        # silently recoding to `webm` is the same defect wearing a different field name.
        "remux_container": "mkv",
        "recode_container": "webm",
        "embed_thumbnail": True,
        "embed_metadata": True,
        "embed_chapters": True,
    }
    assert field_name in sample, f"no hostile value written for {field_name}"

    with pytest.raises(presets.PresetOverrideError, match=field_name):
        presets.to_request(
            presets.BEST_VIDEO_1080P,
            url=URL,
            output_directory=DIRECTORY,
            **{field_name: sample[field_name]},
        )


def test_settings_a_preset_does_not_own_are_still_accepted() -> None:
    """The refusal must stay narrow, or it blocks the settings it was never about."""
    request = request_for(
        presets.BEST_VIDEO,
        proxy="http://proxy.example:8080",
        rate_limit_bytes=1024,
        cookies_from_browser="firefox",
    )

    assert request.proxy == "http://proxy.example:8080"
    assert request.rate_limit_bytes == 1024
    assert request.cookies_from_browser == "firefox"
    assert request.format_selector == presets.effective_selector(presets.BEST_VIDEO)


def test_the_owned_field_set_is_derived_and_not_empty() -> None:
    """A guard that protects nothing would let every parametrized case above vanish."""
    assert "format_selector" in presets.PRESET_OWNED_FIELDS
    assert len(presets.PRESET_OWNED_FIELDS) >= 6


def test_the_two_audio_presets_are_actually_different() -> None:
    """`T012-R5`, one layer up: they must differ in what they *ask for*, not only in name.

    Both select `bestaudio`, so a reader comparing selectors alone would conclude they are the
    same preset twice. The codec is the difference, and it is the field that decides whether
    anything is converted at all.
    """
    mp3 = request_for(presets.AUDIO_MP3)
    original = request_for(presets.AUDIO_ORIGINAL)

    assert mp3.audio_codec is not original.audio_codec
    assert mp3 != original


# --- what the presets actually ask yt-dlp for ------------------------------------------------
#
# Through `ytdlp_adapter`, on the far side of the boundary. A preset that sets a field the
# adapter never reads has chosen nothing, and that is not a hypothetical failure mode here: it
# is `T012-R5`, where `extractaudio` was set on every audio request and silently ignored
# because the library reads `postprocessors` instead.


def test_the_mp3_preset_asks_yt_dlp_to_convert_to_mp3() -> None:
    from tracks_and_trails.downloader import ytdlp_adapter as adapter

    specs = adapter.build_postprocessors(request_for(presets.AUDIO_MP3))

    extract = [spec for spec in specs if spec["key"] == "FFmpegExtractAudio"]
    assert extract, "the MP3 preset installs no audio extractor at all"
    assert extract[0]["preferredcodec"] == AudioCodec.MP3.value
    assert extract[0]["preferredquality"] == presets.MP3_QUALITY


def test_the_original_audio_preset_asks_for_no_conversion() -> None:
    """`AudioCodec.ORIGINAL` carries yt-dlp's `best`, which means "keep the source codec"."""
    from tracks_and_trails.downloader import ytdlp_adapter as adapter

    specs = adapter.build_postprocessors(request_for(presets.AUDIO_ORIGINAL))

    extract = [spec for spec in specs if spec["key"] == "FFmpegExtractAudio"]
    assert extract, "the audio preset must still extract the audio stream"
    assert extract[0]["preferredcodec"] == AudioCodec.ORIGINAL.value
    assert "preferredquality" not in extract[0]


def test_the_subtitle_preset_asks_yt_dlp_to_write_and_embed_them() -> None:
    from tracks_and_trails.downloader import ytdlp_adapter as adapter

    request = request_for(presets.VIDEO_WITH_SUBTITLES)
    options = adapter.build_options(request, "%(title)s.%(ext)s")

    assert options["writesubtitles"] is True
    assert options["subtitleslangs"] == list(presets.SUBTITLE_LANGUAGES)
    assert any(spec["key"] == "FFmpegEmbedSubtitle" for spec in options["postprocessors"])


@pytest.mark.parametrize("preset", presets.BUILT_IN_PRESETS, ids=lambda p: p.name)
def test_every_preset_produces_options_yt_dlp_accepts(preset: Preset) -> None:
    """Every built-in's post-processors resolve against the pinned yt-dlp's own registry.

    `build_postprocessors` raises `UnsupportedPostProcessorError` for a name yt-dlp does not
    have, so this fails the day a preset names a processor that was renamed upstream (`NFR-008`)
    — which is the kind of breakage that would otherwise surface as a failed download.
    """
    from tracks_and_trails.downloader import ytdlp_adapter as adapter

    request = request_for(preset)
    options = adapter.build_options(request, "%(title)s.%(ext)s")

    assert options["format"] == presets.effective_selector(preset)
    assert isinstance(options["postprocessors"], list)


@pytest.mark.parametrize("preset", presets.BUILT_IN_PRESETS, ids=lambda p: p.name)
def test_the_selector_reaches_yt_dlp_unedited(preset: Preset) -> None:
    """The whole chain in one assertion: preset → request → the `format` yt-dlp is handed.

    `REQ-009` promises the user that what they are shown is what runs. The promise is only worth
    anything if it holds at the end of the chain, not at the start of it.
    """
    from tracks_and_trails.downloader import ytdlp_adapter as adapter

    shown = presets.effective_selector(preset)
    options = adapter.build_options(request_for(preset), "%(title)s.%(ext)s", probe_only=False)

    assert options["format"] == shown


# --- the MP3 bitrate scale belongs to MP3 (`T-076`, `T076-R1`) --------------------------------


@pytest.mark.parametrize("bitrate", presets.MP3_BITRATES)
def test_every_offered_bitrate_reaches_the_preset(bitrate: str) -> None:
    """Each value the UI offers must be one `with_audio_quality` accepts, and carry through."""
    assert presets.with_audio_quality(presets.AUDIO_MP3, bitrate).audio_quality == bitrate


OTHER_CODECS: Final = tuple(sorted(set(AudioCodec) - {AudioCodec.MP3}, key=lambda c: c.value))


@pytest.mark.parametrize("codec", OTHER_CODECS, ids=lambda c: c.value)
def test_no_other_codec_accepts_mp3s_bitrates(codec: AudioCodec) -> None:
    """`T076-R1`: "converts audio" is not the same question as "is MP3".

    The first version gated on `CONVERTING_AUDIO_CODECS` — every codec but `ORIGINAL`. That set
    contains `FLAC`, `WAV` and `ALAC`, where a constant kbps bitrate is not a worse choice but a
    meaningless one, and `OPUS`, whose useful range is nothing like MP3's.

    Only MP3 is offered today, so a gate on "converting" behaved identically and would have gone
    on doing so until the day a second converting preset appeared — which is exactly when nobody
    would be looking at this.
    """
    candidate = replace(presets.AUDIO_MP3, audio_codec=codec)
    with pytest.raises(ValueError, match="MP3"):
        presets.with_audio_quality(candidate, "320")


def test_a_bitrate_outside_the_offered_set_is_refused() -> None:
    """A number the UI cannot produce is still a number a caller can pass."""
    with pytest.raises(ValueError, match="offered bitrates"):
        presets.with_audio_quality(presets.AUDIO_MP3, "999")


# --- FormatChoice: the narrowing preset naming depends on (T159-R1, REQ-026) -------------------
#
# *(This read "the narrowing History depends on". History was withdrawn by `T-169`/`T-170`, and
# `T159-R1`'s boundary ended with the table rather than moving to the survivor — see the note in
# `persistence/repositories.py`. The narrowing is still a live invariant for the reason below:
# `preset_name_for` cannot tell two presets apart without it. `T-186`.)*


def test_a_format_choice_carries_exactly_the_preset_owned_fields() -> None:
    """**Equality, not containment**, and both directions are a real failure (`T159-R1`).

    A field this *lacks* stops `preset_name_for` distinguishing two presets that differ only in it,
    so a download would be named as something it is not. A field this *gains* is worse: everything
    a `DownloadRequest` holds outside `PRESET_OWNED_FIELDS` is a credential, a network setting or a
    location, and `REQ-026` governs where the first of those may be written. This is the assertion
    that makes "narrowed" a property rather than a claim in a docstring.
    """
    carried = {field.name for field in fields(presets.FormatChoice)}

    assert carried == presets.PRESET_OWNED_FIELDS, (
        f"FormatChoice carries {sorted(carried)} but presets own "
        f"{sorted(presets.PRESET_OWNED_FIELDS)}. Extra fields may be credentials this structure "
        "must never hold; missing ones make two presets indistinguishable"
    )


def test_narrowing_a_request_drops_every_field_that_is_not_about_the_format() -> None:
    """The other half, asserted on a request whose private fields are all populated.

    `cookies_from_browser` is the one `REQ-026` names. `proxy` and `output_directory` are not
    credentials — the model refuses proxy userinfo outright — but they describe the user's network
    and disk rather than the download, and a narrowed choice is compared and stored where the whole
    request is not.

    **This test used to put a cookies *path* in `cookies_from_browser`**, which is precisely the
    gap `DAT-003`'s `T-049` amendment measured and called *"by intent, not by construction"* — the
    field took any non-empty text, so a path travelled through the one field the redaction
    reasoning treats as a name. `T-197` closed it with a validator, and this line is what the
    closing looked like from the inside: the value is now a browser name, because a path is
    refused.
    """
    request = DownloadRequest(
        url="https://example.invalid/watch?v=abc123",
        output_directory="/home/alice/Private Downloads",
        format_selector="bestaudio/best",
        output_template="%(title)s.%(ext)s",
        cookies_from_browser="firefox:Private",
        proxy="http://proxy.internal.invalid:8080",
        rate_limit_bytes=1024,
    )

    narrowed = repr(presets.format_choice_of(request))

    for private in ("alice", "cookies.sqlite", "proxy.internal.invalid", "1024"):
        assert private not in narrowed, (
            f"{private!r} survived the narrowing into {narrowed!r}, which is compared and stored "
            "where the whole request is not"
        )
    assert presets.format_choice_of(request).format_selector == "bestaudio/best", (
        "the narrowing dropped the format itself, which is the one thing it exists to keep"
    )


def test_the_pure_ffmpeg_predicate_agrees_with_the_definitive_one() -> None:
    """**`T199-R1`'s anti-drift binding**, over the whole built-in catalogue.

    `core.presets.needs_ffmpeg` reads a preset's fields; `ytdlp_adapter.requires_ffmpeg` asks
    yt-dlp which postprocessors it would build and whether they subclass `FFmpegPostProcessor`.
    The second is definitive and unavailable to `ui/` — it imports `yt_dlp`, which
    `ARCHITECTURE.md` §6 permits in two modules only. So the offer computes the first, and this
    asserts the two never disagree.

    **Every built-in, compared as a whole** rather than a spot check: `T199-R1` was three presets
    offered with ffmpeg absent that the worker refuses before a byte moves, and a test naming the
    three it happened to know about would not have caught the fourth.
    """
    from tracks_and_trails.downloader.ytdlp_adapter import requires_ffmpeg

    disagreements = []
    for preset in presets.BUILT_IN_PRESETS:
        request = request_for(preset)
        pure = presets.needs_ffmpeg(preset)
        definitive = requires_ffmpeg(request)
        if pure != definitive:
            disagreements.append(f"{preset.name}: pure={pure} definitive={definitive}")

    assert not disagreements, (
        "the predicate the add dialog uses disagrees with the one the worker enforces: "
        + "; ".join(disagreements)
        + ". A preset offered but refused is UX-005 §5's own failure"
    )
