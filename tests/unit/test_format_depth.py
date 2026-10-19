"""Format depth: the sort, the format check and the merge container (`T-250`).

`ARC-010`, amended 2026-10-15, second: the sort is checked field by field against yt-dlp's own
vocabulary (`test_format_sort.py` binds that); the check has four positions and acts on the
download only, so reading a URL keeps its cost; and one written order decides the container —
recode, then remux, then the merge container, then yt-dlp's choice — with a remux into a container
the merger writes merging straight into it. Six spellings are refused through the options field
for their controls, and `--compat-options format-sort` with them.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

import pytest
from yt_dlp import YoutubeDL, parse_options
from yt_dlp.postprocessor.ffmpeg import FFmpegMergerPP

from tracks_and_trails.core import presets
from tracks_and_trails.core.models import (
    MERGE_CONTAINERS,
    DownloadRequest,
    FormatCheck,
    MediaKind,
    Preset,
)
from tracks_and_trails.core.settings import Settings, add_preset, load, save
from tracks_and_trails.downloader import worker
from tracks_and_trails.downloader.extra_options import COMPAT_REFUSALS, admit
from tracks_and_trails.downloader.ytdlp_adapter import build_options, merge_container_for
from tracks_and_trails.persistence.repositories import _deserialize_request, _serialize_request
from tracks_and_trails.ui.format_text import format_name

URL: Final = "https://example.invalid/clip"
DIRECTORY: Final = "downloads"
TEMPLATE: Final = "%(title)s.%(ext)s"


def a_request(**fields: Any) -> DownloadRequest:
    fields.setdefault("format_selector", "bv*+ba/b")
    return DownloadRequest(url=URL, output_directory=DIRECTORY, output_template=TEMPLATE, **fields)


def a_preset(**fields: Any) -> Preset:
    return replace(presets.BEST_VIDEO, name="Mine", built_in=False, **fields)


def test_the_merge_containers_are_yt_dlp_s() -> None:
    assert MERGE_CONTAINERS == FFmpegMergerPP.SUPPORTED_EXTS


# --- each field, held to yt-dlp's own parse ------------------------------------------------------


@pytest.mark.parametrize("probe_only", [False, True])
@pytest.mark.parametrize("text", ["res:1080,vcodec:h264", "+size, br", "res"])
def test_the_sort_is_sent_as_the_command_line_sends_it(text: str, probe_only: bool) -> None:
    """On both passes: the probe chooses a format too, to name the file it will write."""
    ours = build_options(a_request(format_sort=text), TEMPLATE, probe_only=probe_only)

    assert ours["format_sort"] == parse_options(["-S", text]).ydl_opts["format_sort"]


@pytest.mark.parametrize(
    ("check", "argv"),
    [
        (FormatCheck.SELECTED, ["--check-formats"]),
        (FormatCheck.EVERY, ["--check-all-formats"]),
        (FormatCheck.NEVER, ["--no-check-formats"]),
    ],
)
def test_each_check_is_sent_as_its_option_on_the_download_only(
    check: FormatCheck, argv: list[str]
) -> None:
    """**Not on the probe** (`ARC-010`): checking every format took 79 requests over 12.9 s
    against 3 to read one video, and the add dialog reads every URL pasted into it."""
    request = a_request(check_formats=check)

    assert (
        build_options(request, TEMPLATE)["check_formats"]
        == (parse_options(argv).ydl_opts["check_formats"])
    )
    assert "check_formats" not in build_options(request, TEMPLATE, probe_only=True)


def test_leaving_the_check_to_yt_dlp_sends_nothing() -> None:
    assert "check_formats" not in build_options(a_request(), TEMPLATE)


@pytest.mark.parametrize("probe_only", [False, True])
@pytest.mark.parametrize("merge", ["mkv", "mp4/mkv", "webm/mp4/mkv"])
def test_the_merge_container_is_sent_as_the_command_line_sends_it(
    merge: str, probe_only: bool
) -> None:
    ours = build_options(a_request(merge_container=merge), TEMPLATE, probe_only=probe_only)

    assert (
        ours["merge_output_format"]
        == (parse_options(["--merge-output-format", merge]).ydl_opts["merge_output_format"])
    )


# --- the written order ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fields", "merges_into"),
    [
        ({}, None),
        ({"merge_container": "mkv"}, "mkv"),
        # A remux into a container the merger writes merges straight into it, one pass.
        ({"remux_container": "mp4"}, "mp4"),
        ({"remux_container": "mp4", "merge_container": "webm"}, "mp4"),
        # A remux the merger cannot write leaves the merge to the merge container, or yt-dlp.
        ({"remux_container": "gif", "merge_container": "mkv"}, "mkv"),
        ({"remux_container": "gif"}, None),
        # A recode runs after the merge, whatever the merge wrote.
        ({"recode_container": "webm"}, None),
        ({"recode_container": "webm", "merge_container": "mkv"}, "mkv"),
    ],
)
def test_the_container_follows_the_written_order(
    fields: dict[str, Any], merges_into: str | None
) -> None:
    request = a_request(**fields)

    assert merge_container_for(request) == merges_into
    assert build_options(request, TEMPLATE).get("merge_output_format") == merges_into


# --- a real sort changes the format a selector picks ---------------------------------------------

#: Two formats of one item, hand-built and never fetched: choosing is all that is asked.
FORMATS: Final = [
    {"format_id": "small", "url": "https://example.invalid/s", "ext": "mp4", "height": 240,
     "width": 320, "vcodec": "avc1", "acodec": "mp4a", "tbr": 300},
    {"format_id": "large", "url": "https://example.invalid/l", "ext": "mp4", "height": 1080,
     "width": 1920, "vcodec": "avc1", "acodec": "mp4a", "tbr": 3000},
]  # fmt: skip


@pytest.mark.parametrize(("sort", "chosen"), [(None, "large"), ("+res", "small")])
def test_a_sort_moves_the_format_a_preset_s_selector_picks(sort: str | None, chosen: str) -> None:
    """Through real yt-dlp with the application's options: `best` under `+res` is the smallest."""
    options = build_options(a_request(format_selector="best", format_sort=sort), TEMPLATE)
    information = {"id": "x", "title": "x", "extractor": "generic", "webpage_url": URL}
    with YoutubeDL({**options, "simulate": True}) as ydl:
        result = ydl.process_ie_result({**information, "formats": FORMATS}, download=False)

    assert result["format_id"] == chosen


# --- the model, storage and the name --------------------------------------------------------------


@pytest.mark.parametrize(
    ("fields", "says"),
    [
        ({"format_sort": "res:abc"}, "whole number"),
        ({"format_sort": "resolution"}, "Use res"),
        ({"merge_container": "mp3"}, "not a merge container"),
        ({"merge_container": "mp4/"}, "not a merge container"),
    ],
)
def test_a_value_that_would_not_do_what_it_says_is_refused(
    fields: dict[str, Any], says: str
) -> None:
    with pytest.raises(ValueError, match=says):
        a_request(**fields)
    with pytest.raises(ValueError, match=says):
        a_preset(**fields)


def test_a_preset_with_format_depth_survives_a_save(tmp_path: Path) -> None:
    target = tmp_path / "settings.toml"
    preset = a_preset(
        format_sort="res:1080,vcodec:h264",
        check_formats=FormatCheck.NEVER,
        merge_container="mp4/mkv",
    )

    save(add_preset(Settings(), preset), target)
    read = load(target)

    assert read.problem is None, read.problem
    assert read.settings.presets == (preset,)
    assert read.settings.presets[0].check_formats is FormatCheck.NEVER


def test_a_request_with_depth_survives_the_queue_and_an_older_row_has_none() -> None:
    request = a_request(format_sort="+size", check_formats=FormatCheck.EVERY, merge_container="mkv")

    read = _deserialize_request(_serialize_request(request))

    assert read == request and read.check_formats is FormatCheck.EVERY
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
    assert (older.format_sort, older.check_formats, older.merge_container) == (
        None,
        FormatCheck.DEFAULT,
        None,
    )


def test_a_preset_carries_its_depth_into_the_request_and_back() -> None:
    preset = a_preset(format_sort="res", check_formats=FormatCheck.SELECTED, merge_container="webm")

    request = presets.to_request(preset, url=URL, output_directory=DIRECTORY)

    assert (request.format_sort, request.check_formats, request.merge_container) == (
        "res",
        FormatCheck.SELECTED,
        "webm",
    )
    assert presets.preset_of(request, name="Mine") == replace(preset, built_in=False)


@pytest.mark.parametrize(
    ("fields", "clause"),
    [
        ({"format_sort": "res:720"}, " · sorted by res:720"),
        ({"check_formats": FormatCheck.EVERY}, " · checking every format"),
        ({"check_formats": FormatCheck.NEVER}, " · checking no format"),
        ({"merge_container": "mp4/mkv"}, " · merged into mp4, else mkv"),
    ],
)
def test_the_name_says_the_depth_and_still_finds_the_built_in(
    fields: dict[str, Any], clause: str
) -> None:
    """Set aside to find the built-in, as `T-251`'s depth is, so the row still says *Best video*."""
    name = format_name(presets.format_choice_of(a_preset(**fields)))

    assert name == f"{presets.BEST_VIDEO.name}{clause}"


# --- the options field, and the preview -----------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "-S res",
        "--format-sort res",
        "--format-sort-reset",
        "--check-formats",
        "--check-all-formats",
        "--no-check-formats",
        "--merge-output-format mkv",
    ],
)
def test_every_spelling_is_refused_for_its_control(text: str) -> None:
    assert not admit(text).usable


def test_the_compatibility_value_reaching_the_sort_is_refused_for_its_control() -> None:
    [refusal] = admit("--compat-options format-sort").refusals

    assert refusal.reason == COMPAT_REFUSALS["control"].format(value="format-sort")


@pytest.mark.parametrize(
    ("fields", "suffix"),
    [
        ({"merge_container": "mp4"}, ".mp4"),
        ({"merge_container": "mp4/mkv"}, ".undecided"),
        ({"merge_container": "mkv", "remux_container": "mov"}, ".mov"),
        ({"merge_container": "mkv", "format_selector": "best"}, ".undecided"),
        ({"merge_container": "mkv", "media_kind": MediaKind.AUDIO}, ".undecided"),
    ],
)
def test_the_preview_names_a_merge_container_only_where_it_decides(
    fields: dict[str, Any], suffix: str
) -> None:
    """A merge container names the container where the selector merges and nothing comes after.
    A list leaves it to the streams, and a remux decides it instead."""
    request = a_request(**fields)

    assert worker.postprocessed_name(Path("Clip.undecided"), request).suffix == suffix
