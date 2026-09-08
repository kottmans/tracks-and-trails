"""`REQ-010`'s five typed options, at the boundaries that do not need a download (`T-109`).

The files those options produce are asserted in `tests/integration/test_post_processing.py`, with
real yt-dlp and real ffmpeg. What is here is the part a download cannot show: what the model
refuses, what the translation emits and in what order, and whether the two hand-written lists that
have to agree with yt-dlp still do.
"""

from dataclasses import fields, replace

import pytest

from tracks_and_trails.core import presets as preset_registry
from tracks_and_trails.core.models import (
    AUDIO_ONLY_CONTAINERS,
    CONTAINER_FORMATS,
    AudioCodec,
    DownloadRequest,
    MediaKind,
    Preset,
    containers_for,
)
from tracks_and_trails.downloader.ytdlp_adapter import build_options, build_postprocessors
from tracks_and_trails.ui.format_text import UNADJUSTED, format_name, unadjusted

URL = "https://example.invalid/clip"
DIRECTORY = "downloads"


def request_with(**options: object) -> DownloadRequest:
    return DownloadRequest(
        url=URL,
        output_directory=DIRECTORY,
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        **options,  # type: ignore[arg-type]
    )


# --- what the model will not represent --------------------------------------------------------


@pytest.mark.parametrize("owner", ["DownloadRequest", "Preset"])
@pytest.mark.parametrize("field", ["remux_container", "recode_container"])
def test_a_container_yt_dlp_does_not_accept_is_refused_at_construction(
    owner: str, field: str
) -> None:
    """`REQ-010`, and `audio_quality`'s argument one field over.

    yt-dlp's remuxer raises for an unknown container **after** the download has completed, so a
    typo costs the whole transfer. Refusing at construction is what turns that into a message
    before anything is spent.
    """
    with pytest.raises(ValueError, match=field):
        if owner == "Preset":
            Preset(
                name="p",
                media_kind=MediaKind.VIDEO,
                format_selector="best",
                output_template="%(title)s.%(ext)s",
                **{field: "mp5"},  # type: ignore[arg-type]
            )
        else:
            request_with(**{field: "mp5"})


def test_a_request_cannot_ask_to_remux_and_recode_at_once() -> None:
    """Two intentions for one container, made unrepresentable rather than resolved silently.

    yt-dlp would run both in turn — the remux's output re-encoded immediately — which is the
    recode alone with a wasted pass, and no UI could present it as something a user meant. A
    silent winner is how a control comes to appear to do nothing (`T-075`).
    """
    with pytest.raises(ValueError, match="two different intentions"):
        request_with(remux_container="mkv", recode_container="webm")


def test_every_offered_container_is_one_the_model_accepts() -> None:
    """The list the editor draws from and the list the model allows are the same list.

    Written because they are two statements that must agree: a control offering a container the
    constructor rejects is a control that raises when it is used.
    """
    for container in CONTAINER_FORMATS:
        assert request_with(remux_container=container).remux_container == container


def test_the_container_list_matches_yt_dlp_s_own() -> None:
    """The transcribed list against the derived one (`docs/project/TESTING.md` §13).

    `core/` may not import `yt_dlp`, so `CONTAINER_FORMATS` is a copy — and a copy is only safe
    while something fails when it drifts. A yt-dlp release that adds a container fails here rather
    than quietly refusing one a user could have had.
    """
    from yt_dlp.postprocessor import get_postprocessor

    remuxer = get_postprocessor("FFmpegVideoRemuxer")
    convertor = get_postprocessor("FFmpegVideoConvertor")
    assert tuple(remuxer.SUPPORTED_EXTS) == CONTAINER_FORMATS
    assert tuple(convertor.SUPPORTED_EXTS) == CONTAINER_FORMATS


def test_the_audio_only_containers_are_the_ones_yt_dlp_calls_audio() -> None:
    """`T-285`: the eleven are transcribed in `core/`, and this is the other side of that.

    `core/` may not import `yt_dlp` (`ARCHITECTURE.md` §6), so the split is written by hand there
    and derived here — the same arrangement `CONTAINER_FORMATS` already uses, and the reason a
    yt-dlp release that reclassifies a container fails the suite rather than quietly changing what
    a video download is offered.

    **`gif` is asserted to be in neither**, because that is why it stays with the video containers
    rather than because somebody preferred it there.
    """
    from yt_dlp.utils import MEDIA_EXTENSIONS

    audio = set(MEDIA_EXTENSIONS.audio) | set(MEDIA_EXTENSIONS.common_audio)
    video = set(MEDIA_EXTENSIONS.video) | set(MEDIA_EXTENSIONS.common_video)
    ours = set(CONTAINER_FORMATS)

    assert set(AUDIO_ONLY_CONTAINERS) == ours & audio - video, (
        "the hand-written audio-only list and yt-dlp's own classification disagree"
    )
    assert "gif" not in audio and "gif" not in video, (
        "yt-dlp now classifies gif, so the comment saying it belongs to neither is stale"
    )


def test_a_video_preset_is_offered_no_container_that_cannot_hold_video() -> None:
    """`T-285`: remux to mp3 errors after the download; recode to mp3 discards the video.

    Both measured with ffmpeg on 2026-08-27 against a one-second `h264 + aac` mp4. The second is
    worse than the first, and neither is something `UX-005` §5 permits offering.
    """
    offered = containers_for(MediaKind.VIDEO)

    wrong = sorted(set(offered) & set(AUDIO_ONLY_CONTAINERS))
    assert not wrong, f"a download that keeps its video is offered {wrong}"
    assert "mp4" in offered and "mkv" in offered, "the video containers went with them"


def test_an_audio_preset_keeps_every_container() -> None:
    """Ruled 2026-08-28: an audio stream in `mp4` or `mkv` is legal and neither route fails on it.

    The symmetry is deliberately not restored — refusing those would refuse combinations that work.
    """
    assert containers_for(MediaKind.AUDIO) == CONTAINER_FORMATS


def test_narrowing_what_is_offered_does_not_narrow_what_is_accepted() -> None:
    """The picker and the validator are different sets, and this is the line between them.

    `CONTAINER_FORMATS` is what `_require_container` refuses against and what the drift test above
    holds equal to yt-dlp's `SUPPORTED_EXTS`. A fix that narrowed it would make a container yt-dlp
    adds unreachable rather than merely unoffered.
    """
    for container in AUDIO_ONLY_CONTAINERS:
        preset = Preset(
            name="v",
            media_kind=MediaKind.VIDEO,
            format_selector="best",
            output_template="%(title)s.%(ext)s",
            remux_container=container,
        )
        assert preset.remux_container == container, (
            f"{container} is no longer accepted by the model, only unoffered by the dialog"
        )


# --- what the translation emits ---------------------------------------------------------------


def test_the_postprocessor_order_is_yt_dlp_s_own() -> None:
    """Each step feeds the next, so the sequence is a contract rather than a style (`T-109`).

    Transcribed from `yt_dlp/__init__.py`'s `get_postprocessors`: extract audio, settle the
    container, embed subtitles, write metadata, embed the thumbnail. Getting it wrong is not a
    crash — it is a picture embedded into the container an extraction then discards, which is the
    combination case `tests/integration/test_post_processing.py` asserts on a real file.
    """
    request = request_with(
        media_kind=MediaKind.AUDIO,
        audio_codec=AudioCodec.MP3,
        recode_container="mkv",
        subtitle_languages=("en",),
        embed_subtitles=True,
        embed_metadata=True,
        embed_chapters=True,
        embed_thumbnail=True,
    )

    assert [spec["key"] for spec in build_postprocessors(request)] == [
        "FFmpegExtractAudio",
        "FFmpegVideoConvertor",
        "FFmpegEmbedSubtitle",
        "FFmpegMetadata",
        "EmbedThumbnail",
    ]


def test_metadata_and_chapters_are_one_spec_that_states_both_flags() -> None:
    """`FFmpegMetadata` defaults both to `True`, so an omitted flag turns an option **on**.

    The consequence is a user's title and source URL written into a file where they asked only to
    keep the chapter marks. Asserted as the spec rather than only as a file so the reason is
    visible where the translation is.
    """
    chapters_only = build_postprocessors(request_with(embed_chapters=True))
    assert chapters_only == [{"key": "FFmpegMetadata", "add_metadata": False, "add_chapters": True}]

    metadata_only = build_postprocessors(request_with(embed_metadata=True))
    assert metadata_only == [{"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": False}]

    assert build_postprocessors(request_with()) == []


def test_embedding_a_thumbnail_asks_for_the_thumbnail_to_be_downloaded() -> None:
    """`EmbedThumbnail` embeds a file that has to exist first (`T012-R5`'s shape).

    yt-dlp's own argument parser sets `writethumbnail` for `--embed-thumbnail`; without it the
    postprocessor runs against a download with no picture beside it and embeds nothing — accepted,
    ineffective, and silent.
    """
    options = build_options(request_with(embed_thumbnail=True), "%(title)s.%(ext)s")
    assert options["writethumbnail"] is True
    assert "writethumbnail" not in build_options(request_with(), "%(title)s.%(ext)s")


def test_a_probe_asks_for_none_of_it() -> None:
    """Post-processing belongs to a download. A probe that installed it would convert nothing and
    pay for the postprocessor list anyway."""
    options = build_options(
        request_with(embed_thumbnail=True, embed_metadata=True),
        "%(title)s.%(ext)s",
        probe_only=True,
    )
    assert "postprocessors" not in options
    assert "writethumbnail" not in options


# --- the preset round trip ---------------------------------------------------------------------


def test_the_five_options_are_preset_owned_and_carried_into_the_request() -> None:
    """A preset is the subset of a request a named choice fixes, and these are part of it."""
    assert preset_registry.POST_PROCESSING_FIELDS <= preset_registry.PRESET_OWNED_FIELDS

    preset = preset_registry.with_post_processing(
        preset_registry.BEST_VIDEO,
        name="Best video available · remuxed to mkv",
        remux_container="mkv",
        embed_metadata=True,
    )
    request = preset_registry.to_request(preset, url=URL, output_directory=DIRECTORY)

    assert request.remux_container == "mkv"
    assert request.embed_metadata is True
    assert request.embed_chapters is False


def test_a_derived_preset_is_no_longer_built_in() -> None:
    """`REQ-007`: a preset the user adjusted is not one that ships with the application, and the
    flag is what the UI reads to know it may be edited."""
    derived = preset_registry.with_post_processing(
        preset_registry.BEST_VIDEO, name="adjusted", embed_chapters=True
    )
    assert preset_registry.BEST_VIDEO.built_in is True
    assert derived.built_in is False


def test_the_editor_s_round_trip_returns_what_it_was_given() -> None:
    """Open showing what the preset asks for, and hand back the same thing unchanged."""
    preset = preset_registry.with_post_processing(
        preset_registry.BEST_VIDEO, name="adjusted", recode_container="webm", embed_thumbnail=True
    )
    again = preset_registry.with_post_processing(
        preset, name="adjusted", **preset_registry.post_processing_of(preset)
    )
    assert again == preset


# --- what the row says it is --------------------------------------------------------------------


def test_a_preset_with_options_still_names_the_preset_it_started_from() -> None:
    """`T140-R3`'s defect, through a field that did not exist when it was fixed.

    Without the third describing fallback, a row that ticks *embed metadata* on `Best video
    available` matches no built-in and falls through to reading `bestvideo+bestaudio/best` —
    the selector twice over, naming nothing.
    """
    adjusted = preset_registry.with_post_processing(
        preset_registry.BEST_VIDEO,
        name="ignored — the name is what is under test",
        embed_metadata=True,
        remux_container="mkv",
    )
    spoken = format_name(preset_registry.format_choice_of(adjusted))

    assert spoken == "Best video available · remuxed to mkv · embedding metadata", spoken


def test_a_download_with_no_options_reads_exactly_as_it_did_before() -> None:
    """The clause is silent by default, which is what leaves every other surface unchanged."""
    plain = format_name(preset_registry.format_choice_of(preset_registry.BEST_VIDEO))
    assert plain == "Best video available"


def test_a_custom_selector_with_options_still_says_both() -> None:
    """A selector no built-in describes names itself, and the options are still disclosed."""
    custom = preset_registry.custom_preset("137+140", name="137+140")
    adjusted = preset_registry.with_post_processing(
        custom, name="x", embed_thumbnail=True, embed_chapters=True
    )
    assert format_name(preset_registry.format_choice_of(adjusted)) == (
        "137+140 · embedding thumbnail and chapters"
    )


def test_the_written_reset_and_the_derived_one_agree() -> None:
    """Two statements of what *unadjusted* means, one transcribed and one derived (§13).

    `unadjusted()` is written field by field so `mypy` checks each; `UNADJUSTED` is read off
    `Preset`'s own defaults. A field whose default changes fails here rather than leaving the
    reset quietly out of step with the model.
    """
    choice = preset_registry.format_choice_of(
        preset_registry.with_post_processing(
            preset_registry.BEST_VIDEO, name="x", recode_container="webm", embed_metadata=True
        )
    )
    assert unadjusted(choice) == replace(choice, **UNADJUSTED)  # type: ignore[arg-type]
    assert set(UNADJUSTED) == preset_registry.POST_PROCESSING_FIELDS


def test_every_post_processing_field_has_a_default_meaning_not_asked_for() -> None:
    """`POST_PROCESSING_FIELDS` names options a user adds; none may be on by default.

    A preset that silently recoded or embedded would make *"the preset, plus these"* false, and
    `_base_preset_for` — which decides what a row is called — would name the wrong thing.
    """
    defaults = {
        field.name: field.default
        for field in fields(Preset)
        if field.name in preset_registry.POST_PROCESSING_FIELDS
    }
    assert set(defaults) == preset_registry.POST_PROCESSING_FIELDS
    assert all(value in (None, False) for value in defaults.values()), defaults
