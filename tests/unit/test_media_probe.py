"""What ffprobe is asked about a section, and what its answers mean (`T252-R1`).

**Driven with a stand-in for ffprobe**, so the arguments and the readings are pinned exactly; the
real ffprobe against real media is `tests/integration/test_download_sections.py`.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any

import pytest

from tracks_and_trails.core.sections import NOT_THROUGH_SEVERAL_PROXIES, NOT_THROUGH_THE_PROXY
from tracks_and_trails.downloader.media_probe import (
    LINK_PROTOCOLS,
    LOCAL_TIMEOUT_SECONDS,
    ONE_FILE_DEMUXERS,
    REMOTE_TIMEOUT_SECONDS,
    Route,
    ffprobe_beside,
    holds_media,
    remote_length,
    route_for,
    run_with,
)

FFPROBE = Path("/opt/ffmpeg/ffprobe")

#: No proxy, no address to connect from, yt-dlp's own timeout.
DIRECT = Route(proxy="", source_address=None, timeout=20.0)


class Answers:
    """Stands in for ffprobe: each run is recorded and answered from a list."""

    def __init__(self, *answers: tuple[int, str]) -> None:
        self.answers = list(answers)
        self.runs: list[tuple[list[str], float]] = []

    def __call__(self, arguments: Sequence[str], timeout: float) -> tuple[int, str]:
        self.runs.append((list(arguments), timeout))
        return self.answers.pop(0) if self.answers else (1, "")


def _read(streams: list[str], duration: str | None) -> str:
    container: dict[str, Any] = {} if duration is None else {"duration": duration}
    return json.dumps({"streams": [{"codec_type": kind} for kind in streams], "format": container})


# --- a section on disk -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "holds"),
    [
        ((0, _read(["video", "audio"], "2.019")), True),
        ((0, _read(["audio"], "2.0")), True),
        # A container that reports no length is not held to one.
        ((0, _read(["video"], None)), True),
        # The 262-byte cut: a valid MP4 with no streams.
        ((0, _read([], None)), False),
        ((0, _read(["subtitle", "data"], "2.0")), False),
        ((0, _read(["video"], "0.000000")), False),
        ((0, _read(["video"], "N/A")), False),
        ((1, ""), False),
        ((0, "not json"), False),
        ((0, "[]"), False),
    ],
)
def test_a_section_holds_media_only_with_a_picture_or_a_sound(
    answer: tuple[int, str], holds: bool
) -> None:
    run = Answers(answer)
    section = Path("/staging/Clip (section 1).mp4")

    assert holds_media(section, FFPROBE, run) is holds
    arguments, timeout = run.runs[0]
    assert arguments[0] == str(FFPROBE) and arguments[-1] == str(section)
    assert timeout == LOCAL_TIMEOUT_SECONDS


# --- a link's length -------------------------------------------------------------------------


def test_the_length_is_read_from_the_chosen_link_with_its_headers_and_cookies() -> None:
    """The request's own headers, and its cookies as a `Cookie` header: yt-dlp keeps them in a
    format's `cookies` field as `Set-Cookie` text, attributes and all."""
    run = Answers((0, "6.000000\n"))
    info = {
        "url": "https://media.example/clip.mp4",
        "protocol": "https",
        "http_headers": {"User-Agent": "UA", "Referer": "https://page.example/"},
        "cookies": "session=abc; Domain=.example; Path=/; Secure; theme=dark; Path=/",
    }

    assert remote_length(info, FFPROBE, run, SimpleCookie, route=DIRECT) == 6.0

    ((arguments, timeout),) = run.runs
    assert timeout == REMOTE_TIMEOUT_SECONDS
    assert arguments[-1] == "https://media.example/clip.mp4"
    headers = arguments[arguments.index("-headers") + 1]
    assert headers.split("\r\n")[:-1] == [
        "User-Agent: UA",
        "Referer: https://page.example/",
        "Cookie: session=abc; theme=dark",
    ]


def test_the_first_merged_link_that_answers_gives_the_length() -> None:
    run = Answers((1, ""), (0, "6.02"))
    info = {
        "requested_formats": [
            {"url": "https://media.example/video.mp4", "protocol": "https"},
            {"url": "https://media.example/audio.m4a", "protocol": "https"},
        ]
    }

    assert remote_length(info, FFPROBE, run, route=DIRECT) == 6.02
    assert [arguments[-1] for arguments, _ in run.runs] == [
        "https://media.example/video.mp4",
        "https://media.example/audio.m4a",
    ]
    assert all("-headers" not in arguments for arguments, _ in run.runs), "no headers to send"


@pytest.mark.parametrize("answer", [(0, "N/A\n"), (0, ""), (0, "0"), (0, "inf"), (1, "6.0")])
def test_no_length_is_read_where_ffprobe_gives_none(answer: tuple[int, str]) -> None:
    link = {"url": "https://media.example/clip.mp4", "protocol": "https"}

    assert remote_length(link, FFPROBE, Answers(answer), route=DIRECT) is None


def test_only_a_web_link_is_asked() -> None:
    run = Answers()

    assert remote_length({"url": "rtmp://media.example/live"}, FFPROBE, run, route=DIRECT) is None
    assert remote_length({}, FFPROBE, run, route=DIRECT) is None
    assert run.runs == []


@pytest.mark.parametrize("protocol", ["m3u8_native", "m3u8", "http_dash_segments", None])
def test_only_a_format_fetched_as_one_file_is_asked(protocol: str | None) -> None:
    """**`T252-R5`**: ffmpeg fetches a manifest's pieces without the address to connect from or a
    certificate check, whatever it is given, so a manifest's length is not read; nor is a format
    that does not say how yt-dlp fetches it."""
    run = Answers((0, "6.0"))
    info = {"url": "https://media.example/master.m3u8", "protocol": protocol}

    assert remote_length(info, FFPROBE, run, route=DIRECT) is None
    assert run.runs == []


# --- the route a link is read by (`T252-R5`, `T253-R3`) ---------------------------------------


def _option(arguments: list[str], name: str) -> str | None:
    return arguments[arguments.index(name) + 1] if name in arguments else None


def test_the_read_carries_every_part_of_the_route() -> None:
    """Each passed explicitly, before the link: ffmpeg left to itself takes its proxy from the
    environment, connects from anywhere, waits for ever and checks no certificate."""
    run = Answers((0, "6.0"))
    route = Route(proxy="http://proxy.example:3128", source_address="::", timeout=7.5)

    remote_length(
        {"url": "https://media.example/clip.mp4", "protocol": "https"}, FFPROBE, run, route=route
    )

    ((arguments, _),) = run.runs
    assert arguments[-1] == "https://media.example/clip.mp4"
    assert _option(arguments, "-http_proxy") == "http://proxy.example:3128"
    assert _option(arguments, "-local_addr") == "::"
    assert _option(arguments, "-timeout") == "7500000", "microseconds"
    assert _option(arguments, "-tls_verify") == "1"
    assert _option(arguments, "-protocol_whitelist") == LINK_PROTOCOLS
    assert _option(arguments, "-format_whitelist") == ONE_FILE_DEMUXERS


def test_no_proxy_is_passed_as_none_and_no_address_as_nothing() -> None:
    """An empty `-http_proxy` is ffmpeg's *no proxy*, which its environment cannot override."""
    arguments = DIRECT.arguments()

    assert _option(arguments, "-http_proxy") == ""
    assert "-local_addr" not in arguments


@pytest.mark.parametrize(
    ("proxy", "system", "expected"),
    [
        # The request's own proxy, whatever the system says.
        ("http://proxy.example:3128", {"https": "http://other:1"}, "http://proxy.example:3128"),
        ("HTTP://proxy.example:3128", {}, "HTTP://proxy.example:3128"),
        # The system's, as yt-dlp reads it, where the request names none.
        (None, {}, ""),
        (None, {"http": "http://sys:8080", "https": "http://sys:8080"}, "http://sys:8080"),
        (None, {"https": "http://sys:8080"}, "http://sys:8080"),
        (None, {"all": "http://sys:8080", "no": "media.example"}, "http://sys:8080"),
        (None, {"ftp": "http://ftp:21"}, ""),
    ],
    ids=["request", "scheme case", "none", "one for both", "https only", "all", "not a web one"],
)
def test_the_read_takes_the_proxy_yt_dlp_would(
    proxy: str | None, system: dict[str, str], expected: str
) -> None:
    route = route_for(proxy, "0.0.0.0", 20.0, system)  # noqa: S104 - IPv4 only, as `-4` binds

    assert route == Route(proxy=expected, source_address="0.0.0.0", timeout=20.0)  # noqa: S104


@pytest.mark.parametrize(
    ("proxy", "system", "refusal"),
    [
        ("socks5://proxy.example:1080", {}, NOT_THROUGH_THE_PROXY),
        ("socks5h://proxy.example:1080", {}, NOT_THROUGH_THE_PROXY),
        ("https://proxy.example:443", {}, NOT_THROUGH_THE_PROXY),
        (None, {"all": "socks5://sys:1080"}, NOT_THROUGH_THE_PROXY),
        (None, {"http": "sys:8080"}, NOT_THROUGH_THE_PROXY),
        (None, {"http": "http://a:1", "https": "http://b:1"}, NOT_THROUGH_SEVERAL_PROXIES),
    ],
    ids=["socks5", "socks5h", "https", "system socks", "no scheme", "two proxies"],
)
def test_a_proxy_ffmpeg_would_go_around_is_refused(
    proxy: str | None, system: dict[str, str], refusal: str
) -> None:
    """**Measured 2026-10-27**: handed a SOCKS or `https://` proxy, ffmpeg connected directly."""
    assert route_for(proxy, None, 20.0, system) == refusal


def test_the_proxy_is_never_named_in_a_refusal() -> None:
    """The system's can carry a password, `http://user:secret@host`."""
    for refusal in (NOT_THROUGH_THE_PROXY, NOT_THROUGH_SEVERAL_PROXIES):
        assert "secret" not in refusal and "@" not in refusal


# --- which ffprobe, and how it is run ---------------------------------------------------------


def test_the_ffprobe_is_the_one_beside_ffmpeg(tmp_path: Path) -> None:
    # Named as each platform names a program: `shutil.which` finds no bare `ffprobe` on Windows.
    suffix = ".exe" if sys.platform == "win32" else ""
    ffmpeg = tmp_path / f"ffmpeg{suffix}"
    ffmpeg.write_text("#!/bin/sh\n")
    ffmpeg.chmod(0o755)
    assert ffprobe_beside(ffmpeg) is None

    ffprobe = tmp_path / f"ffprobe{suffix}"
    ffprobe.write_text("#!/bin/sh\n")
    ffprobe.chmod(0o755)
    assert ffprobe_beside(ffmpeg) == ffprobe


def test_a_run_that_cannot_start_answers_nothing(tmp_path: Path) -> None:
    run = run_with(None)

    assert run([str(tmp_path / "not-a-program")], 5) == (-1, "")


def test_a_run_goes_through_yt_dlp_s_popen_when_it_has_one() -> None:
    seen: dict[str, Any] = {}

    class Popen:
        @classmethod
        def run(cls, arguments: list[str], **options: Any) -> tuple[str, str, int]:
            seen.update(arguments=arguments, **options)
            return "6.0\n", "an error naming https://media.example/?token=secret", 0

    assert run_with(Popen)(["ffprobe", "x"], 7) == (0, "6.0\n")
    assert seen["arguments"] == ["ffprobe", "x"] and seen["timeout"] == 7 and seen["text"] is True


@pytest.mark.parametrize("through", ["subprocess", "popen"])
def test_ffprobe_inherits_no_proxy_variable(monkeypatch: pytest.MonkeyPatch, through: str) -> None:
    """**`T252-R5`**: ffmpeg reads `http_proxy` and `no_proxy` from its environment, and the route
    is passed as arguments instead. A real child process, so the environment is the one it gets."""
    from yt_dlp.utils import Popen

    for name in ("http_proxy", "HTTPS_PROXY", "no_proxy", "ALL_PROXY"):
        monkeypatch.setenv(name, "http://ambient.example:1")
    monkeypatch.setenv("T252_KEPT", "kept")
    run = run_with(Popen if through == "popen" else None)
    show = (
        "import os; print(sorted(k for k in os.environ if k.lower().endswith('_proxy')), "
        "os.environ.get('T252_KEPT'))"
    )

    code, output = run([sys.executable, "-c", show], 30)

    assert code == 0
    assert output.strip() == "[] kept"
