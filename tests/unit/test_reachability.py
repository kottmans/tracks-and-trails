"""Where connections are made from, and the wait before each file (`T-253`).

Ruled 2026-10-19 (`ARC-010` amended, second): one choice in *Settings*, *Network* of Automatic, IPv4
only, IPv6 only or *From this address*, which absorbs `--source-address`; the wait keeps yt-dlp's
meaning, per file, beside the speed limit; a sleeping job shows a *Waiting* stage. The real sessions
are `tests/integration/test_reachability.py`; these hold the values on their way there.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Final

import pytest
from yt_dlp import YoutubeDL, parse_options
from yt_dlp.downloader import common as downloader_common
from yt_dlp.downloader.common import FileDownloader

from tracks_and_trails.core import settings as app_settings
from tracks_and_trails.core.logging import YtdlpLog
from tracks_and_trails.core.models import (
    IPV4_ONLY,
    IPV6_ONLY,
    MOST_WAIT_SECONDS,
    DownloadRequest,
    NetworkOptions,
    canonical_address,
)
from tracks_and_trails.downloader import worker
from tracks_and_trails.downloader.extra_options import HAS_A_CONTROL, admit
from tracks_and_trails.downloader.protocol import Progress, Stage
from tracks_and_trails.downloader.ytdlp_adapter import build_options, is_waiting_line

STAGING: Final = "/home/someone/Videos/.staging/Clip.mp4"
#: Every spelling yt-dlp's parser has for the five options, refused through the options field.
SPELLINGS: Final = (
    ("-4",),
    ("--force-ipv4",),
    ("-6",),
    ("--force-ipv6",),
    ("--source-address", "192.0.2.7"),
    ("--sleep-interval", "3"),
    ("--min-sleep-interval", "3"),
    ("--max-sleep-interval", "9"),
)


def a_request(**fields: Any) -> DownloadRequest:
    return DownloadRequest(
        url="https://example.invalid/clip",
        output_directory="/home/someone/Videos",
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        **fields,
    )


# --- the value -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "held"),
    [
        ("192.0.2.7", "192.0.2.7"),
        ("  192.0.2.7 ", "192.0.2.7"),
        ("0:0::0", IPV6_ONLY),
        ("2001:DB8:0:0::20", "2001:db8::20"),
        ("0.0.0.0", IPV4_ONLY),  # noqa: S104 - the spelling `-4` binds to
        ("example.com", None),
        ("192.0.2.300", None),
        ("192.0.2", None),
        ("", None),
    ],
)
def test_an_address_is_held_the_shortest_way_and_a_name_is_none(
    text: str, held: str | None
) -> None:
    """**An address, never a host name**: yt-dlp picks the family by whether the text holds a colon,
    so a name would be bound as IPv4 whatever it resolved to."""
    assert canonical_address(text) == held


@pytest.mark.parametrize("owner", [NetworkOptions, a_request])
@pytest.mark.parametrize(
    "fields",
    [
        {"source_address": "example.com"},
        {"source_address": "0:0::0"},
        {"source_address": " 192.0.2.7"},
        {"source_address": ""},
        {"source_address": 7},
        # Zero alone is no wait, which `None` says (`T253-R1`); beside a longest it is held.
        {"sleep_interval": 0},
        {"sleep_interval": 0.0, "max_sleep_interval": None},
        {"sleep_interval": -1.0},
        {"sleep_interval": -1.0, "max_sleep_interval": 5.0},
        # `T253-R2`: within the tolerance of zero tenths, alone or beside a longest, either field.
        {"sleep_interval": 1e-9},
        {"sleep_interval": 1e-8, "max_sleep_interval": 5.0},
        {"sleep_interval": 0.0, "max_sleep_interval": 1e-9},
        {"sleep_interval": 0.0, "max_sleep_interval": 0},
        {"sleep_interval": math.inf},
        {"sleep_interval": math.nan},
        {"sleep_interval": 10**400},
        {"sleep_interval": MOST_WAIT_SECONDS + 0.1},
        {"sleep_interval": 2.55},
        {"sleep_interval": True},
        {"sleep_interval": "3"},
        # yt-dlp's command line's rules, which its library does not apply.
        {"max_sleep_interval": 5.0},
        {"sleep_interval": 5.0, "max_sleep_interval": 4.9},
        {"sleep_interval": 5.0, "max_sleep_interval": 0.05},
    ],
)
def test_a_value_yt_dlp_s_command_line_would_refuse_is_refused(
    owner: Any, fields: dict[str, Any]
) -> None:
    with pytest.raises((TypeError, ValueError)):
        owner(**fields)


@pytest.mark.parametrize(
    "fields",
    [
        {"source_address": IPV4_ONLY},
        {"source_address": IPV6_ONLY},
        {"source_address": "2001:db8::20"},
        {"sleep_interval": 0.1},
        {"sleep_interval": float(MOST_WAIT_SECONDS)},
        {"sleep_interval": 3, "max_sleep_interval": 3},
        {"sleep_interval": 3.0, "max_sleep_interval": 9.5},
        # `T253-R1`: a random wait from nothing up to the longest.
        {"sleep_interval": 0, "max_sleep_interval": 5.0},
        {"sleep_interval": 0.0, "max_sleep_interval": 0.1},
    ],
)
def test_each_answer_the_screen_can_give_is_held(fields: dict[str, Any]) -> None:
    assert a_request(**fields) == a_request(**fields)
    assert NetworkOptions(**fields) == NetworkOptions(**fields)


# --- the file --------------------------------------------------------------------------------


def _saved_and_loaded(tmp_path: Path, options: NetworkOptions) -> app_settings.SettingsFile:
    target = tmp_path / "settings.toml"
    held = app_settings.with_network_options(app_settings.Settings(), options)
    assert app_settings.save(held, target) is None
    return app_settings.load(target)


@pytest.mark.parametrize(
    "options",
    [
        NetworkOptions(source_address=IPV4_ONLY),
        NetworkOptions(source_address=IPV6_ONLY),
        NetworkOptions(source_address="2001:db8::20", sleep_interval=2.5),
        NetworkOptions(sleep_interval=2.5, max_sleep_interval=30.0),
        NetworkOptions(sleep_interval=0.0, max_sleep_interval=5.0),
    ],
)
def test_the_choices_are_saved_and_read_back(tmp_path: Path, options: NetworkOptions) -> None:
    read = _saved_and_loaded(tmp_path, options)

    assert read.settings.network == options
    assert read.problem is None


def test_nobody_choosing_writes_none_of_them(tmp_path: Path) -> None:
    _saved_and_loaded(tmp_path, NetworkOptions())

    written = (tmp_path / "settings.toml").read_text(encoding="utf-8")
    assert not any(
        f"{key} =" in written for key in ("source_address", "sleep_interval", "max_sleep_interval")
    )


@pytest.mark.parametrize(
    ("lines", "expected", "reported"),
    [
        ('source_address = "0:0::0"', NetworkOptions(source_address=IPV6_ONLY), False),
        ('source_address = "example.com"', NetworkOptions(), True),
        ("source_address = 4", NetworkOptions(), True),
        ("sleep_interval = 3", NetworkOptions(sleep_interval=3.0), False),
        ("sleep_interval = 0", NetworkOptions(), True),
        ("sleep_interval = -2", NetworkOptions(), True),
        ('sleep_interval = "3"', NetworkOptions(), True),
        ("sleep_interval = 9000", NetworkOptions(sleep_interval=3600.0), True),
        ("sleep_interval = 2.55", NetworkOptions(sleep_interval=2.5), True),
        # Rounded to the nearest tenth, which for the shortest may be none at all (`T253-R1`).
        ("sleep_interval = 0.04", NetworkOptions(), True),
        ("sleep_interval = 0.06", NetworkOptions(sleep_interval=0.1), True),
        ("sleep_interval = 1e-9", NetworkOptions(), True),
        (
            "sleep_interval = 1e-8\nmax_sleep_interval = 5",
            NetworkOptions(sleep_interval=0.0, max_sleep_interval=5.0),
            True,
        ),
        (
            "sleep_interval = 0\nmax_sleep_interval = 1e-9",
            NetworkOptions(sleep_interval=0.0, max_sleep_interval=0.1),
            True,
        ),
        (f"sleep_interval = {10**400}", NetworkOptions(sleep_interval=3600.0), True),
        # The pair is held to yt-dlp's command line's rules after each key is read.
        ("max_sleep_interval = 9", NetworkOptions(), True),
        (
            "sleep_interval = 0\nmax_sleep_interval = 9",
            NetworkOptions(sleep_interval=0.0, max_sleep_interval=9.0),
            False,
        ),
        ("sleep_interval = 5\nmax_sleep_interval = 4", NetworkOptions(sleep_interval=5.0), True),
        (
            "sleep_interval = 5\nmax_sleep_interval = 5",
            NetworkOptions(sleep_interval=5.0, max_sleep_interval=5.0),
            False,
        ),
        (
            "sleep_interval = 5\nmax_sleep_interval = 9000",
            NetworkOptions(sleep_interval=5.0, max_sleep_interval=3600.0),
            True,
        ),
        # One bad key costs only itself.
        (
            'source_address = "nowhere"\nsleep_interval = 2\nretries = 4',
            NetworkOptions(retries=4, sleep_interval=2.0),
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


# --- what yt-dlp is handed -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("argv", "fields"),
    [
        (["-4"], {"source_address": IPV4_ONLY}),
        (["-6"], {"source_address": IPV6_ONLY}),
        (["--source-address", "192.0.2.7"], {"source_address": "192.0.2.7"}),
        (["--sleep-interval", "3"], {"sleep_interval": 3.0}),
        (["--min-sleep-interval", "3"], {"sleep_interval": 3.0}),
        (
            ["--sleep-interval", "3", "--max-sleep-interval", "9.5"],
            {"sleep_interval": 3.0, "max_sleep_interval": 9.5},
        ),
        (
            ["--sleep-interval", "0", "--max-sleep-interval", "5"],
            {"sleep_interval": 0.0, "max_sleep_interval": 5.0},
        ),
    ],
)
def test_each_choice_sets_the_keys_yt_dlp_s_own_options_set(
    argv: list[str], fields: dict[str, Any]
) -> None:
    """**The mapping held to yt-dlp's parser**, so a choice means what its option means, the longest
    wait included where none was chosen."""
    parsed = parse_options(argv).ydl_opts
    downloaded = build_options(a_request(**fields), STAGING)

    for key in ("source_address", "sleep_interval", "max_sleep_interval"):
        assert downloaded.get(key) == parsed[key], key


def test_where_each_key_acts() -> None:
    """The address on both passes, since the probe connects too; the wait on the download only,
    since yt-dlp waits in its file downloader, which a probe never starts."""
    request = a_request(source_address=IPV6_ONLY, sleep_interval=2.0, max_sleep_interval=4.0)

    probed = build_options(request, request.output_template, probe_only=True)
    downloaded = build_options(request, STAGING)

    assert probed["source_address"] == downloaded["source_address"] == IPV6_ONLY
    assert not {"sleep_interval", "max_sleep_interval"} & set(probed)
    assert (downloaded["sleep_interval"], downloaded["max_sleep_interval"]) == (2.0, 4.0)


def test_nobody_choosing_sends_none_of_the_keys() -> None:
    request = a_request()

    for options in (
        build_options(request, request.output_template, probe_only=True),
        build_options(request, STAGING),
    ):
        assert not {"source_address", "sleep_interval", "max_sleep_interval"} & set(options)


@pytest.mark.parametrize("argv", SPELLINGS, ids=lambda argv: argv[0])
def test_the_options_field_refuses_every_spelling_for_its_control(argv: tuple[str, ...]) -> None:
    """**No two spellings can disagree any more** (ruled 2026-10-19, second, question 1): `-4`,
    `-6` and a typed `--source-address` all wrote one key, the last typed winning."""
    admission = admit(" ".join(argv))

    assert [(refusal.option, refusal.reason) for refusal in admission.refusals] == [
        (argv[0], HAS_A_CONTROL)
    ]


# --- the wait, as the row sees it ------------------------------------------------------------


SLEEP_KEYS: Final = ("sleep_interval", "max_sleep_interval")


class _Lines:
    """A logger keeping what yt-dlp writes, as `YtdlpLog` is handed it."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def debug(self, message: str) -> None:
        self.seen.append(message)

    info = warning = error = debug


class _Nothing(FileDownloader):  # type: ignore[misc]
    def real_download(self, filename: str, info_dict: dict[str, Any]) -> bool:
        return True


@pytest.mark.parametrize("seconds", [0.1, 3.0, 125.5])
def test_yt_dlp_s_own_line_before_a_wait_is_read_as_one(
    seconds: float, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """**yt-dlp's real downloader writes the line**, so a wording it changes fails here as well as
    in the integration suite. Its sleep is skipped: what is held is the line, not the wait."""
    monkeypatch.setattr(downloader_common.time, "sleep", lambda _seconds: None)
    lines = _Lines()
    with YoutubeDL({"logger": lines, "sleep_interval": seconds}) as ydl:
        _Nothing(ydl, ydl.params).download(str(tmp_path / "clip.mp4"), {"id": "x"})

    assert [line for line in lines.seen if is_waiting_line(line.strip())] != [], lines.seen


def test_a_wait_from_nothing_is_drawn_from_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """**`T253-R1`**: yt-dlp's real downloader, handed what the adapter builds for a wait from zero
    up to five seconds, draws it from zero, where the tenth the model used to substitute drew it
    from a tenth."""
    drawn: list[tuple[float, float]] = []

    def uniform(low: float, high: float) -> float:
        drawn.append((low, high))
        return 0.0

    monkeypatch.setattr(downloader_common.random, "uniform", uniform)
    options = build_options(a_request(sleep_interval=0.0, max_sleep_interval=5.0), STAGING)
    lines = _Lines()
    with YoutubeDL({"logger": lines, **{key: options[key] for key in SLEEP_KEYS}}) as ydl:
        _Nothing(ydl, ydl.params).download(str(tmp_path / "clip.mp4"), {"id": "x"})

    assert drawn == [(0.0, 5.0)]


@pytest.mark.parametrize(
    "line",
    [
        "[download] Destination: Clip.mp4",
        "Sleeping 3.00 seconds ...",
        "[download] Sleeping for a while",
        "[youtube] Sleeping 3.00 seconds ...",
    ],
)
def test_no_other_line_is_read_as_a_wait(line: str) -> None:
    assert not is_waiting_line(line)


def test_a_line_reaches_the_listener_and_a_debug_line_does_not() -> None:
    import logging

    heard: list[str] = []
    log = YtdlpLog(logging.getLogger("tests.reachability"), on_line=heard.append)

    log.debug("[download] Sleeping 3.00 seconds ...")
    log.debug("[debug] params: {}")
    log.warning("\r[download] Something")

    assert heard == ["[download] Sleeping 3.00 seconds ...", "[download] Something"]


class _Messages:
    def __init__(self) -> None:
        self.sent: list[Any] = []

    def put(self, item: Any, /) -> None:
        self.sent.append(item)


def test_the_wait_is_sent_as_its_own_stage_and_the_download_puts_it_back() -> None:
    messages = _Messages()
    reporter = worker._Reporter("job-1", messages)

    reporter.waiting()
    reporter.progress_hook({"status": "downloading", "downloaded_bytes": 1, "info_dict": {}})

    stages = [message.stage for message in messages.sent if isinstance(message, Progress)]
    assert stages == [Stage.WAITING, Stage.DOWNLOADING_VIDEO]
