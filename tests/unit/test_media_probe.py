"""What ffprobe is asked about a section, and what its answers mean (`T252-R1`).

**Driven with a stand-in for ffprobe**, so the arguments and the readings are pinned exactly; the
real ffprobe against real media is `tests/integration/test_download_sections.py`.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from collections.abc import Mapping, Sequence
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any

import pytest
import yt_dlp
from yt_dlp.utils import networking

from tracks_and_trails.core.sections import NOT_THROUGH_THE_PROXY, NOT_WITH_THIS_FFPROBE
from tracks_and_trails.downloader.media_probe import (
    HELP_TIMEOUT_SECONDS,
    LINK_PROTOCOLS,
    LOCAL_TIMEOUT_SECONDS,
    ONE_FILE_DEMUXERS,
    PROTOCOL_OPTIONS,
    REMOTE_TIMEOUT_SECONDS,
    Route,
    RouteRefusedError,
    RouteTo,
    defined_options,
    defines_every,
    ffprobe_beside,
    holds_media,
    proxy_table,
    remote_length,
    route_for,
    run_with,
)

FFPROBE = Path("/opt/ffmpeg/ffprobe")

#: No proxy, no address to connect from, yt-dlp's own timeout.
DIRECT = Route(proxy="", source_address=None, timeout=20.0)


def _every_link(route: Route) -> RouteTo:
    """One route for every link, its headers sent as they are."""
    return lambda _url, headers: (route, dict(headers))


ALWAYS_DIRECT = _every_link(DIRECT)

#: Every option a route can pass, as a build that defines them all lists them (`T368-R5`).
EVERY: frozenset[str] = frozenset().union(*PROTOCOL_OPTIONS.values())


def _every() -> frozenset[str]:
    return EVERY


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

    assert (
        remote_length(info, FFPROBE, run, SimpleCookie, route=ALWAYS_DIRECT, defined=_every) == 6.0
    )

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

    assert remote_length(info, FFPROBE, run, route=ALWAYS_DIRECT, defined=_every) == 6.02
    assert [arguments[-1] for arguments, _ in run.runs] == [
        "https://media.example/video.mp4",
        "https://media.example/audio.m4a",
    ]
    assert all("-headers" not in arguments for arguments, _ in run.runs), "no headers to send"


@pytest.mark.parametrize("answer", [(0, "N/A\n"), (0, ""), (0, "0"), (0, "inf"), (1, "6.0")])
def test_no_length_is_read_where_ffprobe_gives_none(answer: tuple[int, str]) -> None:
    link = {"url": "https://media.example/clip.mp4", "protocol": "https"}

    assert (
        remote_length(link, FFPROBE, Answers(answer), route=ALWAYS_DIRECT, defined=_every) is None
    )


def test_only_a_web_link_is_asked() -> None:
    run = Answers()

    rtmp = {"url": "rtmp://media.example/live"}
    assert remote_length(rtmp, FFPROBE, run, route=ALWAYS_DIRECT, defined=_every) is None
    assert remote_length({}, FFPROBE, run, route=ALWAYS_DIRECT, defined=_every) is None
    assert run.runs == []


@pytest.mark.parametrize("protocol", ["m3u8_native", "m3u8", "http_dash_segments", None])
def test_only_a_format_fetched_as_one_file_is_asked(protocol: str | None) -> None:
    """**`T252-R5`**: ffmpeg fetches a manifest's pieces without the address to connect from or a
    certificate check, whatever it is given, so a manifest's length is not read; nor is a format
    that does not say how yt-dlp fetches it."""
    run = Answers((0, "6.0"))
    info = {"url": "https://media.example/master.m3u8", "protocol": protocol}

    assert remote_length(info, FFPROBE, run, route=ALWAYS_DIRECT, defined=_every) is None
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
        {"url": "https://media.example/clip.mp4", "protocol": "https"},
        FFPROBE,
        run,
        route=_every_link(route),
        defined=_every,
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


def test_a_redirect_is_refused_only_where_the_route_could_change() -> None:
    """`-max_redirects 0` where yt-dlp could reach the next link another way (`route_for`)."""
    assert "-max_redirects" not in DIRECT.arguments()
    held = Route(proxy="", source_address=None, timeout=20.0, follows_redirects=False)
    assert _option(held.arguments(), "-max_redirects") == "0"


#: Several environments, each as `urllib.request.getproxies` reads it on this platform.
ENVIRONMENTS = [
    {},
    {"http_proxy": "http://sys:8080"},
    {"https_proxy": "http://sys:8080"},
    {"http_proxy": "http://a:1", "https_proxy": "http://b:1"},
    {"all_proxy": "socks5://sys:1080", "no_proxy": "media.example"},
    {"http_proxy": "http://sys:8080", "no_proxy": "127.0.0.1,.example"},
]


@pytest.mark.parametrize("proxy", [None, "", "http://request:3128"])
@pytest.mark.parametrize("environment", ENVIRONMENTS, ids=lambda e: ",".join(e) or "none")
def test_the_table_is_yt_dlp_s_own(
    monkeypatch: pytest.MonkeyPatch, environment: dict[str, str], proxy: str | None
) -> None:
    """Held to `YoutubeDL.proxies` at the pin, given what the adapter gives it: a request's proxy
    only when it is not empty (`build_options`)."""
    for name in ("http_proxy", "https_proxy", "all_proxy", "no_proxy"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.upper(), raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    params: dict[str, Any] = {"quiet": True}
    if proxy:
        params["proxy"] = proxy

    with yt_dlp.YoutubeDL(params) as ydl:
        expected = ydl.proxies

    assert proxy_table(proxy, urllib.request.getproxies()) == expected


def _route(
    url: str,
    proxies: Mapping[str, str],
    headers: Mapping[str, str] | None = None,
) -> tuple[Route, Mapping[str, str]] | str:
    return route_for(url, headers or {}, proxies, networking, "0.0.0.0", 20.0)  # noqa: S104


@pytest.mark.parametrize(
    ("url", "proxies", "proxy", "follows"),
    [
        # The request's own, for every link, so a redirect keeps it.
        ("https://m.example/c", {"all": "http://request:3128"}, "http://request:3128", True),
        # **`T368-R4`**: written as ffmpeg reads it, which compares `http://` exactly.
        ("http://m.example/c", {"all": "HTTP://request:3128"}, "http://request:3128", True),
        (
            "http://m.example/c",
            {"all": "Http://u:p@request:3128/x"},
            "http://u:p@request:3128/x",
            True,
        ),
        # None at all, and one for both kinds of link.
        ("https://m.example/c", {}, "", True),
        ("http://m.example/c", {"http": "http://s:1", "https": "http://s:1"}, "http://s:1", True),
        # yt-dlp's `__noproxy__`, and a proxy written without its scheme.
        ("http://m.example/c", {"all": "__noproxy__"}, "", True),
        ("http://m.example/c", {"all": "s:8080"}, "http://s:8080", True),
        # **The review's second case**: `https` only leaves an `http://` link direct.
        ("http://m.example/c", {"https": "http://s:1"}, "", False),
        ("https://m.example/c", {"https": "http://s:1"}, "http://s:1", False),
        # Two proxies: each link its own.
        ("http://m.example/c", {"http": "http://a:1", "https": "http://b:1"}, "http://a:1", False),
        ("https://m.example/c", {"http": "http://a:1", "https": "http://b:1"}, "http://b:1", False),
        # **The review's first case**: the exceptions name the host, so it is reached directly.
        ("http://127.0.0.1:8/c", {"all": "http://s:1", "no": "127.0.0.1"}, "", False),
        ("http://m.example/c", {"all": "http://s:1", "no": ".example"}, "", False),
        ("http://m.other/c", {"all": "http://s:1", "no": ".example"}, "http://s:1", False),
        # Exceptions with no proxy to make them to: every link is direct (`T368-R5`).
        ("http://127.0.0.1:8/c", {"no": "127.0.0.1"}, "", True),
        ("https://m.other/c", {"no": ".example", "all": "__noproxy__"}, "", True),
        # Exceptions that happen to name the host each kind of link is tried with.
        ("http://m.other/c", {"all": "http://s:1", "no": ".invalid"}, "http://s:1", False),
    ],
    ids=[
        "request",
        "scheme case",
        "scheme case, the rest kept",
        "none",
        "one for both",
        "noproxy",
        "no scheme",
        "https only, http link",
        "https only, https link",
        "two, http link",
        "two, https link",
        "exempt address",
        "exempt domain",
        "not exempt",
        "exceptions, no proxy",
        "exceptions, no proxy at all",
        "exceptions naming the tried host",
    ],
)
def test_each_link_is_read_by_yt_dlp_s_route_to_it(
    url: str, proxies: dict[str, str], proxy: str, follows: bool
) -> None:
    routed = _route(url, proxies)

    assert not isinstance(routed, str)
    route, _ = routed
    assert route == Route(
        proxy=proxy,
        source_address="0.0.0.0",  # noqa: S104 - IPv4 only, as `-4` binds
        timeout=20.0,
        follows_redirects=follows,
    )


def test_a_header_naming_a_proxy_is_the_route_and_is_not_sent() -> None:
    """`Ytdl-Request-Proxy`, which `--add-headers` can set, stands for every proxy and every
    exception, and goes nowhere; yt-dlp's other instruction is read as yt-dlp reads it."""
    routed = _route(
        "http://127.0.0.1:8/c",
        {"all": "http://s:1", "no": "127.0.0.1"},
        {"ytdl-request-proxy": "http://named:3128", "Youtubedl-No-Compression": "1", "X-A": "b"},
    )

    assert not isinstance(routed, str)
    route, sent = routed
    assert (route.proxy, route.follows_redirects) == ("http://named:3128", True)
    assert dict(sent) == {"X-A": "b", "Accept-Encoding": "identity"}


@pytest.mark.parametrize(
    ("url", "proxies"),
    [
        ("https://m.example/c", {"all": "socks5://proxy.example:1080"}),
        ("https://m.example/c", {"all": "socks5h://proxy.example:1080"}),
        ("https://m.example/c", {"all": "https://proxy.example:443"}),
        ("http://m.example/c", {"http": "socks4://sys:1080", "https": "http://s:1"}),
    ],
    ids=["socks5", "socks5h", "https", "this link's only"],
)
def test_a_proxy_ffmpeg_would_go_around_is_refused(url: str, proxies: dict[str, str]) -> None:
    """**Measured 2026-10-27**: handed a SOCKS or `https://` proxy, ffmpeg connected directly."""
    assert _route(url, proxies) == NOT_THROUGH_THE_PROXY


def test_a_link_another_proxy_serves_is_still_read() -> None:
    """Refusing one link's route does not stop another's: the audio is asked when the video's
    proxy is one ffmpeg would go around."""
    run = Answers((0, "6.0"))
    info = {
        "requested_formats": [
            {"url": "https://m.example/video.mp4", "protocol": "https"},
            {"url": "http://m.example/audio.m4a", "protocol": "http"},
        ]
    }

    def route(url: str, headers: Mapping[str, str]) -> tuple[Route, Mapping[str, str]] | str:
        return route_for(url, headers, {"https": "socks5://s:1"}, networking, None, 20.0)

    assert remote_length(info, FFPROBE, run, route=route, defined=_every) == 6.0
    assert [arguments[-1] for arguments, _ in run.runs] == ["http://m.example/audio.m4a"]


def test_no_link_read_says_why() -> None:
    run = Answers()
    info = {"url": "https://m.example/clip.mp4", "protocol": "https"}

    def refused(_url: str, _headers: Mapping[str, str]) -> str:
        return NOT_THROUGH_THE_PROXY

    with pytest.raises(RouteRefusedError) as raised:
        remote_length(info, FFPROBE, run, route=refused, defined=_every)

    assert raised.value.reason == NOT_THROUGH_THE_PROXY
    assert run.runs == []


def test_the_route_is_asked_with_each_link_and_its_own_headers() -> None:
    asked: list[tuple[str, dict[str, str]]] = []

    def route(url: str, headers: Mapping[str, str]) -> tuple[Route, Mapping[str, str]]:
        asked.append((url, dict(headers)))
        return DIRECT, {"X-Sent": "yes"}

    run = Answers((1, ""), (0, "6.0"))
    info = {
        "http_headers": {"X-Item": "1"},
        "requested_formats": [
            {"url": "https://m.example/v.mp4", "protocol": "https", "http_headers": {"X-V": "1"}},
            {"url": "https://m.example/a.m4a", "protocol": "https"},
        ],
    }

    assert remote_length(info, FFPROBE, run, route=route, defined=_every) == 6.0
    assert asked == [
        ("https://m.example/v.mp4", {"X-V": "1"}),
        ("https://m.example/a.m4a", {"X-Item": "1"}),
    ]
    assert all(_option(arguments, "-headers") == "X-Sent: yes\r\n" for arguments, _ in run.runs)


@pytest.mark.parametrize("proxy", [" http://s:1", "http:/s:1"])
def test_a_proxy_ffmpeg_would_not_read_as_one_is_refused(proxy: str) -> None:
    """**`T368-R4`**: ffmpeg takes a proxy only where the text starts `http://`, and otherwise
    connects directly; yt-dlp reads a leading space past, so such a proxy is never handed on."""
    assert _route("https://m.example/c", {"all": proxy}) == NOT_THROUGH_THE_PROXY


def test_the_proxy_is_never_named_in_a_refusal() -> None:
    """The system's can carry a password, `http://user:secret@host`."""
    refusal = _route("https://m.example/c", {"all": "socks5://user:secret@sys:1080"})
    assert refusal == NOT_THROUGH_THE_PROXY
    assert "secret" not in refusal and "@" not in refusal


# --- what a build defines (`T368-R5`) ---------------------------------------------------------

#: Each protocol's options as FFmpeg 8.1.3 lists them, trimmed; `-h protocol=…` prints these.
LISTINGS: dict[str, str] = {
    "http": "http AVOptions:\n"
    "  -http_proxy        <string>     ED......... set HTTP proxy to tunnel through\n"
    "  -location          <string>     ED......... The actual location of the data received\n"
    "  -max_redirects     <int>        .D......... Maximum number of redirects (default 8)\n",
    "tcp": "tcp AVOptions:\n"
    "  -local_addr        <string>     ED......... Local address\n"
    "  -timeout           <int>        ED......... set timeout of socket I/O operations\n",
    "tls": "tls AVOptions:\n"
    "  -http_proxy        <string>     .D......... Set proxy to tunnel through\n"
    "  -tls_verify        <boolean>    ED......... Verify the peer certificate (default false)\n",
}


class Listings:
    """Stands in for a build asked for its options, which answers from `listings`."""

    def __init__(self, listings: Mapping[str, str], code: int = 0, failing: str = "") -> None:
        self.listings, self.code, self.failing = listings, code, failing
        self.runs: list[tuple[list[str], float]] = []

    def __call__(self, arguments: Sequence[str], timeout: float) -> tuple[int, str]:
        self.runs.append((list(arguments), timeout))
        protocol = arguments[-1].removeprefix("protocol=")
        if protocol == self.failing:
            return -1, ""
        return self.code, self.listings.get(protocol, f"Unknown protocol '{protocol}'.\n")


def test_a_build_is_asked_for_each_protocol_s_options() -> None:
    run = Listings(LISTINGS)

    assert defined_options(FFPROBE, run) == EVERY
    assert run.runs == [
        ([str(FFPROBE), "-hide_banner", "-h", f"protocol={protocol}"], HELP_TIMEOUT_SECONDS)
        for protocol in ("http", "tcp", "tls")
    ]


@pytest.mark.parametrize(
    ("left_out", "lacking"),
    [
        # Ubuntu 24.04's 6.1.1: FFmpeg added `max_redirects` in 8.1.
        ("  -max_redirects     <int>        .D......... Maximum number of redirects (default 8)\n",
         "max_redirects"),
        # Debian 12's 5.1.9.
        ("  -local_addr        <string>     ED......... Local address\n", "local_addr"),
    ],
    ids=["6.1.1", "5.1.9"],
)  # fmt: skip
def test_an_option_a_build_does_not_list_is_one_it_lacks(left_out: str, lacking: str) -> None:
    listings = {protocol: text.replace(left_out, "") for protocol, text in LISTINGS.items()}

    assert defined_options(FFPROBE, Listings(listings)) == EVERY - {lacking}


def test_a_build_without_tls_defines_no_certificate_check() -> None:
    """It answers `Unknown protocol 'tls'.`, so an `https://` link is not handed to it."""
    listings = {"http": LISTINGS["http"], "tcp": LISTINGS["tcp"]}

    assert defined_options(FFPROBE, Listings(listings)) == EVERY - {"tls_verify"}


def test_a_build_that_cannot_say_defines_none(tmp_path: Path) -> None:
    assert defined_options(FFPROBE, Listings(LISTINGS, code=1)) == frozenset()
    assert defined_options(tmp_path / "not-a-program", run_with(None)) == frozenset()


@pytest.mark.parametrize("failing", ["http", "tcp", "tls"])
def test_a_build_that_cannot_say_for_one_protocol_defines_none(failing: str) -> None:
    """A listing that did not finish says nothing of the others' being whole either."""
    assert defined_options(FFPROBE, Listings(LISTINGS, failing=failing)) == frozenset()


def test_an_option_named_only_in_another_s_description_is_not_one_it_defines() -> None:
    listings = {
        **LISTINGS,
        "tcp": "tcp AVOptions:\n  -timeout   <int>   ED.. waits, unlike -local_addr here\n",
    }

    assert "local_addr" not in defined_options(FFPROBE, Listings(listings))


@pytest.mark.parametrize(
    ("route", "lacking", "carried"),
    [
        (DIRECT, "max_redirects", True),
        (Route("", None, 20.0, follows_redirects=False), "max_redirects", False),
        (Route("", "::", 20.0), "local_addr", False),
        (DIRECT, "local_addr", True),
        (DIRECT, "tls_verify", False),
        (DIRECT, "timeout", False),
        (DIRECT, "http_proxy", False),
    ],
)
def test_a_route_is_carried_only_where_the_build_defines_each_option_it_passes(
    route: Route, lacking: str, carried: bool
) -> None:
    assert defines_every(route.arguments(), EVERY - {lacking}) is carried


def test_a_link_this_ffprobe_cannot_take_the_route_to_is_never_asked() -> None:
    """Refused before ffprobe is started on it, with the reason, and the build asked once."""
    run = Answers((0, "6.0"))
    asked: list[None] = []
    info = {
        "requested_formats": [
            {"url": "https://m.example/v.mp4", "protocol": "https"},
            {"url": "https://m.example/a.m4a", "protocol": "https"},
        ]
    }

    def defined() -> frozenset[str]:
        asked.append(None)
        return EVERY - {"local_addr"}

    with pytest.raises(RouteRefusedError) as raised:
        remote_length(info, FFPROBE, run, route=_every_link(Route("", "::", 20.0)), defined=defined)

    assert raised.value.reason == NOT_WITH_THIS_FFPROBE
    assert run.runs == []
    assert len(asked) == 1


def test_the_build_is_not_asked_where_no_link_has_a_route() -> None:
    def defined() -> frozenset[str]:
        raise AssertionError("asked")

    info = {"url": "https://m.example/master.m3u8", "protocol": "m3u8"}
    assert remote_length(info, FFPROBE, Answers(), route=ALWAYS_DIRECT, defined=defined) is None


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
