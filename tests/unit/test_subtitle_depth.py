"""Subtitle depth: automatic captions, the format preference and the conversion (`T-251`).

Three typed fields for four of yt-dlp's options, shared by presets and requests, set on the
download only and only where languages are chosen, and held here to yt-dlp's own `parse_options`
of the options they stand for (`ARC-010`, amended 2026-10-15). The refusal of automatic captions
beside `all` comes from a measurement rather than a preference, and the probe case below carries
its shape.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

import pytest
from yt_dlp import parse_options
from yt_dlp.postprocessor.ffmpeg import FFmpegSubtitlesConvertorPP

from tracks_and_trails.core import presets
from tracks_and_trails.core.models import (
    ALL_SUBTITLE_LANGUAGES,
    DownloadRequest,
    Preset,
    SubtitleFormat,
    subtitle_format_problem,
)
from tracks_and_trails.core.settings import Settings, add_preset, load, save
from tracks_and_trails.downloader.ytdlp_adapter import (
    build_options,
    build_postprocessors,
    project_media,
    requires_ffmpeg,
)
from tracks_and_trails.persistence.repositories import _deserialize_request, _serialize_request
from tracks_and_trails.ui.format_text import format_name

URL: Final = "https://example.invalid/clip"
DIRECTORY: Final = "downloads"
TEMPLATE: Final = "%(title)s.%(ext)s"

#: The keys the fields set, and what yt-dlp means when each is absent.
DEPTH_KEYS: Final = {
    "writesubtitles": False,
    "writeautomaticsub": False,
    "subtitleslangs": [],
    "subtitlesformat": "best",
}


def a_request(**fields: Any) -> DownloadRequest:
    return DownloadRequest(
        url=URL,
        output_directory=DIRECTORY,
        format_selector="best",
        output_template=TEMPLATE,
        **fields,
    )


def a_preset(**fields: Any) -> Preset:
    return replace(presets.BEST_VIDEO, name="Subtitled", built_in=False, **fields)


def converter(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [spec for spec in specs if spec.get("key") == "FFmpegSubtitlesConvertor"]


# --- the model and where it is kept -----------------------------------------------------------


def test_the_conversions_are_exactly_the_ones_yt_dlp_s_converter_takes() -> None:
    """A release that adds one is noticed here, rather than missing from the control."""
    assert tuple(member.value for member in SubtitleFormat) == tuple(
        FFmpegSubtitlesConvertorPP.SUPPORTED_EXTS
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("automatic_captions", "yes"),
        ("convert_subtitles", "srt"),
        ("subtitle_format", ""),
        ("subtitle_format", "SRT"),
        ("subtitle_format", "srt/"),
        ("subtitle_format", "srt vtt"),
    ],
)
def test_a_value_of_the_wrong_kind_is_refused(field: str, value: object) -> None:
    """A bare `"srt"` compares equal to the member and fails an identity check (`T011-R2`)."""
    with pytest.raises((TypeError, ValueError), match=field):
        a_preset(**{field: value})
    with pytest.raises((TypeError, ValueError), match=field):
        a_request(**{field: value})


@pytest.mark.parametrize("text", ["srt", "srt/vtt/best", "best", "ass/srt", "json3/vtt"])
def test_a_preference_in_yt_dlp_s_grammar_is_accepted(text: str) -> None:
    assert subtitle_format_problem(text) is None
    assert a_preset(subtitle_format=text).subtitle_format == text


def test_automatic_captions_are_refused_beside_every_language() -> None:
    """**About 160 requests, measured 2026-10-14.** yt-dlp merges the caption map in first, so
    `all` would name every machine translation the site lists. The built-in carrying `all` is the
    preset one checkbox away from it.
    """
    with pytest.raises(ValueError, match="160"):
        replace(presets.VIDEO_WITH_SUBTITLES, automatic_captions=True)
    with pytest.raises(ValueError, match="automatic_captions"):
        a_request(subtitle_languages=(ALL_SUBTITLE_LANGUAGES,), automatic_captions=True)


def test_a_preset_with_subtitle_depth_survives_a_save(tmp_path: Path) -> None:
    target = tmp_path / "settings.toml"
    preset = a_preset(
        subtitle_languages=("en",),
        automatic_captions=True,
        subtitle_format="srt/best",
        convert_subtitles=SubtitleFormat.ASS,
    )

    save(add_preset(Settings(), preset), target)
    read = load(target)

    assert read.problem is None, read.problem
    assert read.settings.presets == (preset,)
    assert read.settings.presets[0].convert_subtitles is SubtitleFormat.ASS


def test_a_request_with_depth_survives_the_queue_and_an_older_row_has_none() -> None:
    """One JSON blob, so no migration (`T-109`'s rule): a row without the keys asks for none."""
    request = a_request(
        subtitle_languages=("de",), automatic_captions=True, convert_subtitles=SubtitleFormat.SRT
    )
    read = _deserialize_request(_serialize_request(request))
    assert read == request
    assert read.convert_subtitles is SubtitleFormat.SRT

    older = _deserialize_request(
        json.dumps(
            {
                "url": URL,
                "output_directory": DIRECTORY,
                "format_selector": "best",
                "output_template": TEMPLATE,
            }
        )
    )
    assert (older.automatic_captions, older.subtitle_format, older.convert_subtitles) == (
        False,
        None,
        None,
    )


def test_a_preset_s_depth_reaches_its_request() -> None:
    preset = a_preset(
        subtitle_languages=("en",),
        automatic_captions=True,
        subtitle_format="vtt",
        convert_subtitles=SubtitleFormat.LRC,
    )
    request = presets.to_request(preset, url=URL, output_directory=DIRECTORY)
    assert (
        request.automatic_captions,
        request.subtitle_format,
        request.convert_subtitles,
    ) == (True, "vtt", SubtitleFormat.LRC)


# --- what the probe offers --------------------------------------------------------------------


def test_the_probe_lists_captions_apart_and_only_for_languages_without_subtitles() -> None:
    """The shape measured 2026-10-14: every subtitle language again in the caption map, plus the
    original track and machine translations. A language with both is offered once, as subtitles.
    """
    info = {
        "id": "clip",
        "title": "Clip",
        "webpage_url": URL,
        "subtitles": {"en": [], "de-DE": []},
        "automatic_captions": {"en": [], "de-DE": [], "en-orig": [], "fr": [], "ab": []},
    }

    media = project_media(info, reachable=lambda _: True)

    assert media.subtitle_languages == ("en", "de-DE")
    assert media.caption_languages == ("en-orig", "fr", "ab")


def test_a_source_with_no_caption_map_lists_none() -> None:
    media = project_media({"id": "c", "title": "C", "webpage_url": URL}, reachable=lambda _: True)
    assert media.caption_languages == ()


# --- reaching yt-dlp --------------------------------------------------------------------------


def test_depth_is_asked_for_on_the_download_and_never_the_probe() -> None:
    request = a_request(
        subtitle_languages=("en",),
        automatic_captions=True,
        subtitle_format="srt/best",
        convert_subtitles=SubtitleFormat.SRT,
    )

    download = build_options(request, TEMPLATE)
    probe = build_options(request, TEMPLATE, probe_only=True)

    assert (download["writeautomaticsub"], download["subtitlesformat"]) == (True, "srt/best")
    assert converter(download["postprocessors"]) == [
        {"key": "FFmpegSubtitlesConvertor", "format": "srt", "when": "before_dl"}
    ]
    assert not {"writeautomaticsub", "subtitlesformat"} & set(probe)


def test_depth_with_no_language_chosen_asks_yt_dlp_for_nothing() -> None:
    """**yt-dlp with no language named takes English**, so a flag alone would fetch a file."""
    request = a_request(
        automatic_captions=True, subtitle_format="srt", convert_subtitles=SubtitleFormat.SRT
    )

    options = build_options(request, TEMPLATE)

    assert not {"writesubtitles", "writeautomaticsub", "subtitlesformat"} & set(options)
    assert converter(options["postprocessors"]) == []
    assert not requires_ffmpeg(request)


#: The same intent twice: the typed fields, and the options a user would type for them.
SAME_INTENT: Final = [
    pytest.param({}, [], id="nothing"),
    pytest.param(
        {"subtitle_languages": ("en",), "automatic_captions": True},
        ["--sub-langs", "en", "--write-subs", "--write-auto-subs"],
        id="captions",
    ),
    pytest.param(
        {"subtitle_languages": ("en", "fr"), "subtitle_format": "srt/vtt/best"},
        ["--sub-langs", "en,fr", "--write-subs", "--sub-format", "srt/vtt/best"],
        id="format",
    ),
    pytest.param(
        {"subtitle_languages": ("de",), "convert_subtitles": SubtitleFormat.SRT},
        ["--sub-langs", "de", "--write-subs", "--convert-subs", "srt"],
        id="conversion",
    ),
    pytest.param(
        {
            "subtitle_languages": ("de",),
            "automatic_captions": True,
            "subtitle_format": "vtt",
            "convert_subtitles": SubtitleFormat.ASS,
        },
        [
            "--sub-langs",
            "de",
            "--write-subs",
            "--write-auto-subs",
            "--sub-format",
            "vtt",
            "--convert-subs",
            "ass",
        ],
        id="all three",
    ),
]


@pytest.mark.parametrize(("typed", "argv"), SAME_INTENT)
def test_the_depth_builds_what_yt_dlp_s_own_command_line_builds(
    typed: dict[str, Any], argv: list[str]
) -> None:
    """**Same intent, same dictionary**, through the preset and `to_request`, key by key, and the
    same converter. Embedding is left out: `--embed-subs` changes `writesubtitles` on yt-dlp's
    command line in a way `test_post_processing_options.py` already holds.
    """
    request = presets.to_request(a_preset(**typed), url=URL, output_directory=DIRECTORY)
    ours = build_options(request, TEMPLATE)
    theirs = parse_options(argv).ydl_opts

    for key, absent in DEPTH_KEYS.items():
        assert ours.get(key, absent) == theirs[key], key
    assert converter(ours["postprocessors"]) == converter(theirs["postprocessors"])


# --- ffmpeg, before a byte moves (`REQ-024`) --------------------------------------------------


@pytest.mark.parametrize("conversion", list(SubtitleFormat))
def test_a_conversion_needs_ffmpeg_and_both_answers_say_so(conversion: SubtitleFormat) -> None:
    """The definitive answer and the GUI's pure one agree (`T199-R1`), and both say yes."""
    preset = a_preset(subtitle_languages=("en",), convert_subtitles=conversion)
    request = presets.to_request(preset, url=URL, output_directory=DIRECTORY)

    assert requires_ffmpeg(request)
    assert presets.needs_ffmpeg(preset)


def test_captions_and_a_format_need_no_ffmpeg() -> None:
    preset = a_preset(subtitle_languages=("en",), automatic_captions=True, subtitle_format="srt")
    request = presets.to_request(preset, url=URL, output_directory=DIRECTORY)

    assert not requires_ffmpeg(request)
    assert not presets.needs_ffmpeg(preset)
    assert build_postprocessors(request) == []


# --- what the row says --------------------------------------------------------------------------


def test_the_name_says_how_the_subtitles_are_taken_and_written() -> None:
    preset = replace(
        presets.VIDEO_WITH_SUBTITLES,
        subtitle_languages=("en",),
        automatic_captions=True,
        subtitle_format="srt/best",
        convert_subtitles=SubtitleFormat.SRT,
    )

    name = format_name(presets.format_choice_of(preset))

    assert "with automatic captions" in name
    assert "subtitles fetched as srt/best" in name
    assert "subtitles converted to SRT" in name


def test_the_built_in_is_still_named_beneath_the_depth() -> None:
    """The depth is set aside to find the built-in, then said, as `T-249`'s kept files are."""
    preset = replace(presets.VIDEO_WITH_SUBTITLES, convert_subtitles=SubtitleFormat.SRT)

    name = format_name(presets.format_choice_of(preset))

    assert name == f"{presets.VIDEO_WITH_SUBTITLES.name} · subtitles converted to SRT"


def test_a_download_that_takes_the_defaults_reads_as_it_did() -> None:
    """Silence by default is what keeps every other row unchanged (`T-109`)."""
    choice = presets.format_choice_of(presets.VIDEO_WITH_SUBTITLES)
    assert format_name(choice) == presets.VIDEO_WITH_SUBTITLES.name
