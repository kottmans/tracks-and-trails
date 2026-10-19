"""Download tuning: the connection's settings and which part is downloaded (`T-252`).

Ruled 2026-10-19 (`ARC-010` and `UX-015` amended): fragment retries, extractor retries, the socket
timeout and concurrent fragments are Settings, beside the retry count; download sections and
live-from-start are preset fields; several sections write one file each, named by the stem and a
section suffix and claimed as one family. The real downloads are
`tests/integration/test_download_sections.py`; these hold the values on their way there.
"""

from __future__ import annotations

import math
from dataclasses import fields, replace
from pathlib import Path
from typing import Any, Final

import pytest
from yt_dlp import parse_options
from yt_dlp.networking.common import DEFAULT_TIMEOUT
from yt_dlp.postprocessor import FFmpegPostProcessor

from tracks_and_trails.core import presets
from tracks_and_trails.core import settings as app_settings
from tracks_and_trails.core.models import (
    MOST_CONCURRENT_FRAGMENTS,
    DownloadRequest,
    MediaKind,
    NetworkOptions,
    Preset,
)
from tracks_and_trails.core.paths import UnsafePathError
from tracks_and_trails.downloader import worker
from tracks_and_trails.downloader.worker import claim_outputs, previewed_path
from tracks_and_trails.downloader.ytdlp_adapter import (
    NumberedSections,
    build_options,
    connection_defaults,
    ffmpeg_for_its_downloader,
    numbered_sections,
    requires_ffmpeg,
)

#: A chosen value for each of `T-252`'s connection settings, none of them its default.
CONNECTION: Final[dict[str, Any]] = {
    "fragment_retries": 3,
    "extractor_retries": 5,
    "socket_timeout": 7.5,
    "concurrent_fragments": 4,
}
#: The same, spelled as yt-dlp's command line spells it.
CONNECTION_ARGV: Final = (
    "--fragment-retries",
    "3",
    "--extractor-retries",
    "5",
    "--socket-timeout",
    "7.5",
    "-N",
    "4",
)
#: The keys those set, by the request field that sets them.
CONNECTION_KEYS: Final = {
    "fragment_retries": "fragment_retries",
    "extractor_retries": "extractor_retries",
    "socket_timeout": "socket_timeout",
    "concurrent_fragments": "concurrent_fragment_downloads",
}
STAGING: Final = "/home/someone/Videos/.staging/Clip.mp4"


def a_request(**fields_: Any) -> DownloadRequest:
    required: dict[str, Any] = {
        "url": "https://example.invalid/clip",
        "output_directory": "/home/someone/Videos",
        "format_selector": "best",
        "output_template": "%(title)s.%(ext)s",
    }
    return DownloadRequest(**{**required, **fields_})


def test_the_samples_name_every_connection_setting() -> None:
    added = {item.name for item in fields(NetworkOptions)} - {
        "proxy",
        "rate_limit_bytes",
        "retries",
    }
    assert added == set(CONNECTION) == set(CONNECTION_KEYS)


# --- the value -------------------------------------------------------------------------------


@pytest.mark.parametrize("owner", [NetworkOptions, a_request])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fragment_retries", -1),
        ("fragment_retries", True),
        ("extractor_retries", "3"),
        ("socket_timeout", 0),
        ("socket_timeout", -2.0),
        ("socket_timeout", math.inf),
        ("socket_timeout", math.nan),
        ("socket_timeout", True),
        ("socket_timeout", "20"),
        ("concurrent_fragments", 0),
        ("concurrent_fragments", MOST_CONCURRENT_FRAGMENTS + 1),
        ("concurrent_fragments", True),
    ],
)
def test_a_value_the_downloader_cannot_use_is_refused(owner: Any, field: str, value: Any) -> None:
    with pytest.raises((TypeError, ValueError)):
        owner(**{field: value})


def test_zero_retries_and_the_ceiling_of_pieces_are_answers() -> None:
    options = NetworkOptions(
        fragment_retries=0, extractor_retries=0, concurrent_fragments=MOST_CONCURRENT_FRAGMENTS
    )
    assert options.fragment_retries == 0 and options.extractor_retries == 0


@pytest.mark.parametrize("owner", [Preset, DownloadRequest])
@pytest.mark.parametrize("sections", [("*abc",), ("(intro",), ("*2:00-1:00",), ("",)])
def test_a_section_yt_dlp_would_refuse_is_refused_by_the_model(
    owner: type[Any], sections: tuple[str, ...]
) -> None:
    """A hand-edited preset is set aside when it is read, rather than failing its job."""
    required: dict[str, Any] = (
        {"name": "p", "media_kind": MediaKind.VIDEO, "format_selector": "best"}
        if owner is Preset
        else {
            "url": "https://example.invalid/x",
            "output_directory": "/d",
            "format_selector": "best",
            "output_template": "%(title)s.%(ext)s",
        }
    )
    with pytest.raises(ValueError, match="download_sections"):
        owner(**required, download_sections=sections)


def test_the_preset_s_part_reaches_the_request() -> None:
    preset = replace(
        presets.BEST_VIDEO, name="Part", download_sections=("intro",), live_from_start=True
    )

    request = presets.to_request(preset, url="https://example.invalid/x", output_directory="/d")

    assert request.download_sections == ("intro",)
    assert request.live_from_start is True


def test_sections_need_ffmpeg_in_both_answers() -> None:
    """The offer's answer and the worker's agree: a section is ffmpeg's download."""
    preset = replace(presets.BEST_VIDEO, name="Part", download_sections=("*1-2",))
    request = presets.to_request(preset, url="https://example.invalid/x", output_directory="/d")

    assert presets.needs_ffmpeg(preset)
    assert requires_ffmpeg(request)
    assert not requires_ffmpeg(replace(request, download_sections=()))


# --- the file --------------------------------------------------------------------------------


def _saved_and_loaded(tmp_path: Path, settings: app_settings.Settings) -> app_settings.SettingsFile:
    target = tmp_path / "settings.toml"
    assert app_settings.save(settings, target) is None
    return app_settings.load(target)


def test_the_connection_settings_are_saved_and_read_back(tmp_path: Path) -> None:
    options = NetworkOptions(retries=2, **CONNECTION)

    read = _saved_and_loaded(
        tmp_path, app_settings.with_network_options(app_settings.Settings(), options)
    )

    assert read.settings.network == options
    assert read.problem is None


def test_nobody_choosing_writes_none_of_them(tmp_path: Path) -> None:
    _saved_and_loaded(tmp_path, app_settings.Settings())

    written = (tmp_path / "settings.toml").read_text(encoding="utf-8")
    assert not any(f"{key} =" in written for key in CONNECTION)


@pytest.mark.parametrize(
    ("lines", "expected", "reported"),
    [
        ("fragment_retries = 1000", NetworkOptions(fragment_retries=100), True),
        ('extractor_retries = "5"', NetworkOptions(), True),
        ("socket_timeout = 30", NetworkOptions(socket_timeout=30.0), False),
        ("socket_timeout = 0", NetworkOptions(), True),
        ("socket_timeout = 9000", NetworkOptions(socket_timeout=600.0), True),
        ('socket_timeout = "20"', NetworkOptions(), True),
        ("concurrent_fragments = 16", NetworkOptions(concurrent_fragments=8), True),
        ("concurrent_fragments = 0", NetworkOptions(), True),
        # One bad key costs only itself.
        (
            "concurrent_fragments = true\nfragment_retries = 4",
            NetworkOptions(fragment_retries=4),
            True,
        ),
    ],
)
def test_a_hand_edited_value_is_read_key_by_key_and_never_raises(
    tmp_path: Path, lines: str, expected: NetworkOptions, reported: bool
) -> None:
    target = tmp_path / "settings.toml"
    target.write_text(f"[network]\n{lines}\n", encoding="utf-8")

    read = app_settings.load(target)

    assert read.settings.network == expected
    assert (read.problem is not None) is reported, read.problem


def test_a_preset_s_sections_are_saved_and_read_back(tmp_path: Path) -> None:
    """A chapter pattern is user text, backslashes and quotes included."""
    preset = replace(
        presets.BEST_VIDEO,
        name="Parts",
        built_in=False,
        download_sections=(r'^Intro\b "cold"', "*1:00-2:00,3:00-inf"),
        live_from_start=True,
    )

    read = _saved_and_loaded(tmp_path, app_settings.add_preset(app_settings.Settings(), preset))

    assert read.settings.presets == (preset,)


# --- what yt-dlp is handed -------------------------------------------------------------------


def test_each_setting_sets_the_key_yt_dlp_s_own_option_sets() -> None:
    """**The mapping held to yt-dlp's parser**, so a setting means what its option means."""
    parsed = parse_options(list(CONNECTION_ARGV)).ydl_opts
    request = a_request(**CONNECTION)

    for passes in (
        build_options(request, request.output_template, probe_only=True),
        build_options(request, STAGING),
    ):
        for field, key in CONNECTION_KEYS.items():
            assert passes[key] == parsed[key], field


def test_the_part_sets_what_yt_dlp_s_own_options_set() -> None:
    sections = ("intro", "*1:00-2:00,3:00-inf", "*from-url")
    argv = [part for section in sections for part in ("--download-sections", section)]
    parsed = parse_options([*argv, "--live-from-start"]).ydl_opts
    request = a_request(download_sections=sections, live_from_start=True)

    downloaded = build_options(request, STAGING)

    assert downloaded["download_ranges"] == parsed["download_ranges"]
    assert downloaded["download_ranges"].from_info is parsed["download_ranges"].from_info
    assert downloaded["live_from_start"] is parsed["live_from_start"]


def test_where_each_key_acts() -> None:
    """The connection and *from the start* on both passes; the sections on the download only."""
    request = a_request(**CONNECTION, download_sections=("*1-2",), live_from_start=True)

    probed = build_options(request, request.output_template, probe_only=True)
    downloaded = build_options(request, STAGING)

    for options in (probed, downloaded):
        assert set(CONNECTION_KEYS.values()) <= set(options)
        assert options["live_from_start"] is True
    assert "download_ranges" not in probed
    assert isinstance(downloaded["download_ranges"], NumberedSections)


def test_nobody_choosing_sends_the_downloader_s_own() -> None:
    """A piece's retries are the command line's ten (`T-364`); the other three are left out, and
    the library reads each absent key as the command line does."""
    request = a_request()

    for options in (
        build_options(request, request.output_template, probe_only=True),
        build_options(request, STAGING),
    ):
        assert options["fragment_retries"] == parse_options([]).ydl_opts["fragment_retries"]
        assert not {"extractor_retries", "socket_timeout", "concurrent_fragment_downloads"} & set(
            options
        )
        assert "live_from_start" not in options and "download_ranges" not in options


def test_the_screen_s_numbers_are_the_downloader_s() -> None:
    command_line = parse_options([]).ydl_opts

    assert dict(connection_defaults()) == {
        "fragment_retries": command_line["fragment_retries"],
        "extractor_retries": command_line["extractor_retries"],
        "socket_timeout": float(DEFAULT_TIMEOUT),
        "concurrent_fragments": command_line["concurrent_fragment_downloads"],
    }


def test_every_section_is_numbered_in_yt_dlp_s_order() -> None:
    """yt-dlp numbers only a chapter; two ranges would otherwise share one name."""
    info = {
        "id": "x",
        "duration": 100,
        "chapters": [
            {"title": "Intro", "start_time": 0, "end_time": 10},
            {"title": "Talk", "start_time": 10, "end_time": 90},
            {"title": "Outro", "start_time": 90, "end_time": 100},
        ],
    }

    yielded = list(numbered_sections(("Intro|Outro", "*20-30", "*-5-inf"))(info, None))

    assert [section["index"] for section in yielded] == [1, 2, 3, 4]
    assert [section.get("title") for section in yielded] == ["Intro", "Outro", None, None]
    assert yielded[3]["start_time"] == 95


@pytest.mark.parametrize(
    ("sections", "named"),
    [
        (("*1-2", "*3-4"), "/v/.staging/Clip (section %(section_number)s).mp4"),
        (("intro",), "/v/.staging/Clip (section %(section_number)s).mp4"),
        (("*1-2",), "/v/.staging/Clip.mp4"),
    ],
)
def test_the_media_is_numbered_only_where_several_files_can_be_written(
    sections: tuple[str, ...], named: str
) -> None:
    downloaded = build_options(a_request(download_sections=sections), "/v/.staging/Clip.mp4")

    assert downloaded["outtmpl"]["default"] == named


def test_the_sidecars_keep_the_base_name_and_the_chapters_their_own() -> None:
    literal = "/v/.staging/100%% Clip.mp4"
    downloaded = build_options(a_request(download_sections=("*1-2", "*3-4")), literal)
    templates = downloaded["outtmpl"]

    assert templates["default"] == "/v/.staging/100%% Clip (section %(section_number)s).mp4"
    for kind in ("subtitle", "thumbnail", "description", "infojson", "annotation", "link"):
        assert templates[kind] == literal, kind
    assert templates["chapter"].startswith("/v/.staging/100%% Clip.")
    assert not any(kind.startswith("pl_") for kind in templates)


# --- the family ------------------------------------------------------------------------------


def _staged(staging: Path, *names: str) -> list[Path]:
    staging.mkdir(parents=True, exist_ok=True)
    paths = [staging / name for name in names]
    for path in paths:
        path.write_bytes(path.name.encode())
    return paths


def test_every_section_and_each_sidecar_is_claimed_once_under_the_base_name(
    tmp_path: Path,
) -> None:
    """yt-dlp records the subtitle under the last section's name it wrote before moving it."""
    staging = tmp_path / ".staging"
    first, second, subtitle, info = _staged(
        staging, "Clip (section 1).mp4", "Clip (section 2).mp4", "Clip.en.vtt", "Clip.info.json"
    )
    result = {
        "requested_subtitles": {"en": {"filepath": str(staging / "Clip (section 2).en.vtt")}},
    }

    written, kept = claim_outputs(
        result,
        staging=staging,
        stem="Clip",
        target=tmp_path / "Clip.mp4",
        produced=first,
        writing_subtitles=True,
        retained=(info,),
        sections=(first, second),
    )

    assert written == tmp_path / "Clip (section 1).mp4"
    assert set(kept) == {
        tmp_path / "Clip (section 2).mp4",
        tmp_path / "Clip.en.vtt",
        tmp_path / "Clip.info.json",
    }
    assert (tmp_path / "Clip (section 2).mp4").read_bytes() == b"Clip (section 2).mp4"
    assert not any(path.exists() for path in (first, second, subtitle, info))


def test_a_taken_section_name_moves_the_whole_family(tmp_path: Path) -> None:
    """`T109-R4`'s rule for a sectioned family: one index for every member, never a mixture."""
    (tmp_path / "Clip (section 2).mp4").write_bytes(b"the user's")
    staging = tmp_path / ".staging"
    first, second, info = _staged(
        staging, "Clip (section 1).mp4", "Clip (section 2).mp4", "Clip.info.json"
    )

    written, kept = claim_outputs(
        {},
        staging=staging,
        stem="Clip",
        target=tmp_path / "Clip.mp4",
        produced=first,
        writing_subtitles=False,
        retained=(info,),
        sections=(first, second),
    )

    assert written == tmp_path / "Clip (2) (section 1).mp4"
    assert set(kept) == {tmp_path / "Clip (2) (section 2).mp4", tmp_path / "Clip (2).info.json"}
    assert (tmp_path / "Clip (section 2).mp4").read_bytes() == b"the user's"
    assert not (tmp_path / "Clip (section 1).mp4").exists(), "a reservation was left behind"


def test_a_section_from_outside_staging_is_refused(tmp_path: Path) -> None:
    """`T109-R8`: every reported source is contained before anything moves, sections included."""
    staging = tmp_path / ".staging"
    (first,) = _staged(staging, "Clip (section 1).mp4")
    elsewhere = tmp_path / "Clip (section 2).mp4"
    elsewhere.write_bytes(b"the user's")

    with pytest.raises(UnsafePathError, match="outside"):
        claim_outputs(
            {},
            staging=staging,
            stem="Clip",
            target=tmp_path / "Clip.mp4",
            produced=first,
            writing_subtitles=False,
            sections=(first, elsewhere),
        )
    assert elsewhere.read_bytes() == b"the user's"


def test_the_preview_names_the_first_section_numbered_as_the_claim_numbers(
    tmp_path: Path,
) -> None:
    several = a_request(download_sections=("*1-2", "*3-4"), output_directory=str(tmp_path))
    target = tmp_path / "Clip.mp4"

    assert previewed_path(target, several) == tmp_path / "Clip (section 1).mp4"
    assert previewed_path(target, replace(several, download_sections=("*1-2",))) == target

    (tmp_path / "Clip (section 1).mp4").write_bytes(b"")
    assert previewed_path(target, several) == tmp_path / "Clip (2) (section 1).mp4"


def test_section_files_are_read_in_order_and_only_where_they_exist(tmp_path: Path) -> None:
    first, second = _staged(tmp_path, "Clip (section 1).mp4", "Clip (section 2).mp4")
    result = {
        "requested_downloads": [
            {"filepath": str(first)},
            {"filepath": str(tmp_path / "Clip (section 3).mp4")},
            {"filepath": str(second)},
        ]
    }

    assert worker._section_files(result) == (first, second)


# --- ffmpeg, for the downloader that cuts ----------------------------------------------------


def test_the_downloader_s_ffmpeg_is_set_for_the_session_and_put_back() -> None:
    """yt-dlp's command line sets this from `--ffmpeg-location`; its library never does."""
    import yt_dlp

    before = FFmpegPostProcessor._ffmpeg_location.get()
    with ffmpeg_for_its_downloader(yt_dlp, Path("/opt/ffmpeg/bin/ffmpeg")):
        assert FFmpegPostProcessor._ffmpeg_location.get() == "/opt/ffmpeg/bin/ffmpeg"
    assert FFmpegPostProcessor._ffmpeg_location.get() == before

    with ffmpeg_for_its_downloader(yt_dlp, None):
        assert FFmpegPostProcessor._ffmpeg_location.get() == before
