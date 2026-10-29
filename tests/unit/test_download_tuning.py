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
from yt_dlp.utils import networking

from tracks_and_trails.core import presets
from tracks_and_trails.core import settings as app_settings
from tracks_and_trails.core.models import (
    MOST_CONCURRENT_FRAGMENTS,
    MOST_SOCKET_TIMEOUT_SECONDS,
    DownloadRequest,
    MediaKind,
    NetworkOptions,
    Preset,
    is_held_timeout,
)
from tracks_and_trails.core.paths import UnsafePathError
from tracks_and_trails.core.sections import NO_LENGTH
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
        # `T-253`'s, held in `tests/unit/test_reachability.py`.
        "source_address",
        "sleep_interval",
        "max_sleep_interval",
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
        # `T252-R2`: too large for a `float`, which raised `OverflowError` rather than refusing.
        ("socket_timeout", 10**400),
        ("socket_timeout", MOST_SOCKET_TIMEOUT_SECONDS + 1),
        # `T252-R3`: finer than the tenths the screen shows, which it showed as another number.
        ("socket_timeout", 0.04),
        ("socket_timeout", 7.55),
        # Second round: within the tolerance of zero tenths, which the floor had stopped checking.
        ("socket_timeout", 1e-9),
        ("socket_timeout", 1e-8),
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


@pytest.mark.parametrize(
    ("seconds", "held"),
    [
        (0.1, True),
        (0.1 - 1e-8, True),
        (0.30000000000000004, True),
        (600, True),
        (1e-9, False),
        (1e-8, False),
        (1e-7, False),
        (0.05, False),
        (0.1 - 1e-5, False),
        (600 + 1e-9, False),
    ],
)
def test_the_tolerance_is_around_a_tenth_never_around_none(seconds: float, held: bool) -> None:
    """`T252-R3`, second round: a value within the tolerance of zero tenths is no timeout."""
    assert is_held_timeout(seconds) is held


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
        ("socket_timeout = 0.04", NetworkOptions(socket_timeout=0.1), True),
        ("socket_timeout = 7.55", NetworkOptions(socket_timeout=7.5), True),
        ("socket_timeout = 0.3", NetworkOptions(socket_timeout=0.3), False),
        ("socket_timeout = 1e-9", NetworkOptions(socket_timeout=0.1), True),
        ("socket_timeout = 1e-8", NetworkOptions(socket_timeout=0.1), True),
        # `T252-R2`: an integer too large for a `float`, beside a valid key it must not take.
        (
            f"fragment_retries = 4\nsocket_timeout = {10**400}",
            NetworkOptions(fragment_retries=4, socket_timeout=600.0),
            True,
        ),
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


def test_a_length_read_from_the_link_is_given_to_yt_dlp_only_where_the_item_has_none() -> None:
    """`T252-R1`: yt-dlp places a range counted from the end by the item's `duration`, and a direct
    link has none, so `*-2-inf` came back as the whole item. The worker reads the length and the
    sections write it in, where the site gave none and only there."""
    without: dict[str, Any] = {"id": "x"}
    yielded = list(numbered_sections(("*-2-inf",), length=6.0)(without, None))
    assert yielded[0]["start_time"] == 4
    assert without["duration"] == 6.0

    given: dict[str, Any] = {"id": "x", "duration": 10}
    yielded = list(numbered_sections(("*-2-inf",), length=6.0)(given, None))
    assert yielded[0]["start_time"] == 8, "the site's own length was overwritten"

    untouched: dict[str, Any] = {"id": "x"}
    list(numbered_sections(("*-2-inf",))(untouched, None))
    assert "duration" not in untouched


def test_a_length_does_not_change_what_the_sections_equal() -> None:
    """Their equality is yt-dlp's, held to `parse_options`; the length is the worker's addition."""
    assert numbered_sections(("*1-2",), length=6.0) == numbered_sections(("*1-2",))


class _Probe:
    """Stands in for ffprobe reading a link's length."""

    def __init__(self, answer: str | None) -> None:
        self.answer = answer
        self.asked = 0
        self.arguments: list[str] = []

    def __call__(self, arguments: Any, timeout: float) -> tuple[int, str]:
        self.asked += 1
        self.arguments = list(arguments)
        return (0, self.answer) if self.answer is not None else (1, "")


_LINK: Final = {"url": "https://media.example/clip.mp4", "protocol": "https"}


def _placed(
    sections: tuple[str, ...],
    info: dict[str, Any],
    probe: _Probe,
    *,
    routes: Any = networking,
    **fields_: Any,
) -> float | None:
    request = replace(a_request(**fields_), download_sections=sections)
    return worker._place_the_sections(
        request, info, Path("/ff/ffprobe"), probe, None, float(DEFAULT_TIMEOUT), routes
    )


def test_a_length_the_site_gives_is_used_and_the_link_is_not_asked() -> None:
    probe = _Probe("999")

    assert _placed(("*1-3",), {**_LINK, "duration": 6}, probe) is None
    with pytest.raises(worker.NothingDownloadedError) as cancelled:
        _placed(("*1-3", "*99-100"), {**_LINK, "duration": 6}, probe)

    assert cancelled.value.reason == (
        "Nothing was downloaded: *99-100 starts after the end of this item, which is 6 seconds "
        "long."
    )
    assert probe.asked == 0


def test_where_the_site_gives_none_the_link_s_length_is_read_and_returned() -> None:
    probe = _Probe("6.000000")

    assert _placed(("*-2-inf",), dict(_LINK), probe) == 6.0
    with pytest.raises(worker.NothingDownloadedError, match=r"\*99-100 starts after"):
        _placed(("*99-100",), dict(_LINK), probe)
    assert probe.asked == 2


@pytest.mark.parametrize(
    "duration",
    [None, 0, -5, math.inf, math.nan, 10**400, True, "6"],
    ids=["none", "zero", "negative", "inf", "nan", "too large", "bool", "text"],
)
def test_a_length_the_site_cannot_give_is_read_from_the_link(duration: Any) -> None:
    """Including an integer too large for a `float`, `T252-R2`'s class on what a site reports."""
    probe = _Probe("6.0")

    assert _placed(("*1-3",), {**_LINK, "duration": duration}, probe) == 6.0
    assert probe.asked == 1


def test_with_no_length_from_the_site_or_the_link_the_item_is_cancelled() -> None:
    with pytest.raises(worker.NothingDownloadedError) as cancelled:
        _placed(("*1-3",), dict(_LINK), _Probe(None))

    assert cancelled.value.reason == NO_LENGTH


# --- T252-R1, second round: a section empty once placed ---------------------------------------


@pytest.mark.parametrize(
    ("sections", "named"),
    [
        (("*0--100",), "*0--100 ends at or before its start"),
        (("*0--6",), "*0--6 ends at or before its start"),
        (("*0-2", "*0--6"), "*0--6 ends at or before its start"),
        (("*3--4",), "*3--4 ends at or before its start"),
        (("*-1--2",), "*-1--2 ends at or before its start"),
        (("*0--6", "*4--4"), "*0--6 and *4--4 end at or before their start"),
    ],
    ids=["past the start", "to zero", "beside one inside", "reversed", "both from the end", "two"],
)
def test_a_range_empty_once_placed_cancels_the_item(sections: tuple[str, ...], named: str) -> None:
    """**The review's counterexamples**: yt-dlp resolves `*0--100` and `*0--6` on six seconds to
    zero and zero, and downloads that as no section at all, the whole item, reported as the part."""
    with pytest.raises(worker.NothingDownloadedError) as cancelled:
        _placed(sections, {**_LINK, "duration": 6}, _Probe(None))

    assert cancelled.value.reason == (
        f"Nothing was downloaded: {named} in this item, which is 6 seconds long."
    )
    assert "*0-2 " not in cancelled.value.reason, "a section inside the item was named"


@pytest.mark.parametrize("sections", [("*0--2",), ("*-2-inf",), ("*5-9",), ("*0-inf",)])
def test_a_range_with_something_in_it_is_placed(sections: tuple[str, ...]) -> None:
    assert _placed(sections, {**_LINK, "duration": 6}, _Probe(None)) is None


@pytest.mark.parametrize(
    ("start", "end", "empty"),
    [(3, 3, True), (3, 2, True), (3, None, False), (None, 4, False), (2, 9, False)],
)
def test_the_address_s_range_is_placed_too(start: int | None, end: int | None, empty: bool) -> None:
    info = {**_LINK, "duration": 6, "start_time": start, "end_time": end}

    if not empty:
        assert _placed(("*from-url",), info, _Probe(None)) is None
        return
    with pytest.raises(worker.NothingDownloadedError, match=r"\*from-url ends at or before"):
        _placed(("*from-url",), info, _Probe(None))


def test_a_pattern_matching_a_chapter_of_no_length_cancels_the_item() -> None:
    """yt-dlp ends a chapter where the next starts, so two starting at zero make the first zero to
    zero, which it downloads as the whole item. A chapter pattern needs no length to be checked."""
    chapters = [
        {"title": "Intro", "start_time": 0, "end_time": 0},
        {"title": "Main", "start_time": 0, "end_time": 6},
    ]
    probe = _Probe(None)

    with pytest.raises(worker.NothingDownloadedError) as cancelled:
        _placed(("Intro",), {**_LINK, "chapters": chapters}, probe)

    assert cancelled.value.reason == (
        "Nothing was downloaded: Intro matches a chapter of this item that has no length."
    )
    assert _placed(("Main",), {**_LINK, "chapters": chapters}, probe) is None
    assert _placed(("Ma",), {**_LINK, "chapters": chapters}, probe) is None, "searched, not matched"
    assert probe.asked == 0


# --- T252-R5 and T253-R3: the link is read by the request's route -----------------------------


def test_the_length_is_read_by_the_request_s_proxy_address_and_timeout() -> None:
    probe = _Probe("6.0")

    _placed(
        ("*1-3",),
        dict(_LINK),
        probe,
        proxy="http://proxy.example:3128",
        source_address="::",
        socket_timeout=7.5,
    )

    arguments = probe.arguments
    assert arguments[arguments.index("-http_proxy") + 1] == "http://proxy.example:3128"
    assert arguments[arguments.index("-local_addr") + 1] == "::"
    assert arguments[arguments.index("-timeout") + 1] == "7500000"


def test_with_nothing_chosen_the_read_waits_as_long_as_yt_dlp_would(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        monkeypatch.delenv(name, raising=False)
    probe = _Probe("6.0")

    _placed(("*1-3",), dict(_LINK), probe)

    arguments = probe.arguments
    assert arguments[arguments.index("-timeout") + 1] == str(DEFAULT_TIMEOUT * 1_000_000)
    assert arguments[arguments.index("-http_proxy") + 1] == ""
    assert "-local_addr" not in arguments


def test_the_system_s_proxy_is_the_one_read_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """yt-dlp's own reading of it, `urllib.request.getproxies`, when the request names none."""
    monkeypatch.setenv("https_proxy", "http://system.example:8080")
    probe = _Probe("6.0")

    _placed(("*1-3",), dict(_LINK), probe)

    assert probe.arguments[probe.arguments.index("-http_proxy") + 1] == "http://system.example:8080"


def test_a_proxy_ffmpeg_would_go_around_cancels_the_item_unread() -> None:
    from tracks_and_trails.core.sections import NOT_THROUGH_THE_PROXY

    probe = _Probe("6.0")

    with pytest.raises(worker.NothingDownloadedError) as cancelled:
        _placed(("*1-3",), dict(_LINK), probe, proxy="socks5://proxy.example:1080")

    assert cancelled.value.reason == NOT_THROUGH_THE_PROXY
    assert probe.asked == 0, "ffprobe was started"
    # The site's own length needs no read, so no route either.
    assert _placed(("*1-3",), {**_LINK, "duration": 6}, probe, proxy="socks5://p:1") is None


def test_without_yt_dlp_s_route_functions_no_link_is_read() -> None:
    """A copy of yt-dlp without `utils.networking` gives no way to tell its route to a link, so
    none is asked and the item is cancelled as one whose length could not be read."""
    probe = _Probe("6.0")

    with pytest.raises(worker.NothingDownloadedError) as cancelled:
        _placed(("*1-3",), dict(_LINK), probe, routes=None)

    assert cancelled.value.reason == NO_LENGTH
    assert probe.asked == 0, "ffprobe was started"


def test_a_section_with_no_media_fails_with_the_staged_info_json_stripped(tmp_path: Path) -> None:
    """Ruling 2's failure is a failed attempt like any other, so the second line behind
    `keep_secrets_out` runs on it too (`T249-R1`), and the cut is left in staging."""
    import json

    from tests.unit.test_kept_beside import WRITTEN
    from tracks_and_trails.downloader import ytdlp_adapter

    info = tmp_path / "Clip.info.json"
    info.write_text(json.dumps(WRITTEN), encoding="utf-8")
    cut = tmp_path / "Clip (section 2).mp4"
    cut.write_bytes(b"\0" * 262)
    answers = iter([(0, '{"streams": [{"codec_type": "video"}]}'), (0, '{"streams": []}')])

    with pytest.raises(worker.SectionWithoutMediaError) as failed:
        worker._require_media(
            (tmp_path / "Clip (section 1).mp4", cut),
            Path("/ff/ffprobe"),
            lambda _arguments, _timeout: next(answers),
            tmp_path,
            ytdlp_adapter,
        )

    assert failed.value.reason.startswith("Clip (section 2).mp4 came back with no picture or sound")
    assert "SECRET" not in info.read_text(encoding="utf-8")
    assert cut.read_bytes() == b"\0" * 262


def test_chapter_patterns_need_no_length() -> None:
    probe = _Probe(None)

    assert _placed(("Intro",), dict(_LINK), probe) is None
    assert probe.asked == 0


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

    location = Path("/opt/ffmpeg/bin/ffmpeg")
    before = FFmpegPostProcessor._ffmpeg_location.get()
    with ffmpeg_for_its_downloader(yt_dlp, location):
        assert FFmpegPostProcessor._ffmpeg_location.get() == str(location)
    assert FFmpegPostProcessor._ffmpeg_location.get() == before

    with ffmpeg_for_its_downloader(yt_dlp, None):
        assert FFmpegPostProcessor._ffmpeg_location.get() == before
