"""What ffmpeg is given for each input of a download yt-dlp hands it (`T-368`).

The inputs as the guard rewrites them, with yt-dlp's own route functions; the real ffmpeg against
real servers is `tests/integration/test_ffmpeg_route.py`.
"""

from __future__ import annotations

import hashlib
import inspect
import subprocess
import sys
from typing import Any

import pytest
import yt_dlp
from yt_dlp.downloader import external
from yt_dlp.downloader.external import FFmpegFD
from yt_dlp.utils import networking

from tracks_and_trails.downloader import ffmpeg_route
from tracks_and_trails.downloader.ffmpeg_route import (
    NOT_ONE_WEB_FILE,
    NOT_THROUGH_THE_PROXY,
    NOT_WITH_THIS_FFMPEG,
    PLAIN_LINK_PROTOCOLS,
    _routed,
    for_the_session,
    on_the_route,
)
from tracks_and_trails.downloader.media_probe import PROTOCOL_OPTIONS, RouteRefusedError

#: `FFmpegFD._call_downloader` at the pin, as a digest of its text. **The guard leans on how it
#: reads its inputs**: `requested_formats` or the item, each input's `downloader_options` before
#: its `-i`, its `http_headers`, and the module's `Popen`. A release that changes the method fails
#: here, and the guard is read again against it before the digest moves.
CALL_DOWNLOADER_AT_THE_PIN = "fe869157381445943253ec0aba3bfb8170cb20009021362fb0da689124647bf4"

#: A direct route, IPv4 only, with yt-dlp's own timeout.
DIRECT: dict[str, str] = {}

#: Every option a route can pass, as a build that defines them all lists them (`T368-R5`).
EVERY: frozenset[str] = frozenset().union(*PROTOCOL_OPTIONS.values())

#: A proxy, and exceptions to it: a redirect could change the route, so none is followed.
EXCEPTED: dict[str, str] = {"http": "http://s:1", "https": "http://s:1", "no": "elsewhere.example"}


def _arguments(item: dict[str, Any]) -> list[str]:
    return list(item["downloader_options"]["ffmpeg_args"])


def _held(
    item: dict[str, Any], proxies: dict[str, str] | None = None, defined: frozenset[str] = EVERY
) -> dict[str, Any]:
    return _routed(item, networking, proxies or DIRECT, "0.0.0.0", 20.0, lambda: defined)  # noqa: S104


class _Found:
    """Stands in for yt-dlp's `FFmpegPostProcessor` finding ffmpeg, or finding none."""

    available = True
    executable: str | None = "/opt/ffmpeg/ffmpeg"

    def __init__(self, downloader: Any = None) -> None:
        self.downloader = downloader


@pytest.fixture
def every_option(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """An ffmpeg that defines every option a route passes, as each binary it is asked about;
    which binaries were asked comes back."""
    asked: list[str] = []

    def defined(binary: str, _run: Any) -> frozenset[str]:
        asked.append(str(binary))
        return EVERY

    monkeypatch.setattr(external, "FFmpegPostProcessor", _Found)
    monkeypatch.setattr(ffmpeg_route, "defined_options", defined)
    return asked


def test_the_method_the_guard_wraps_is_the_pin_s() -> None:
    text = inspect.getsource(FFmpegFD._call_downloader)

    assert hashlib.sha256(text.encode()).hexdigest() == CALL_DOWNLOADER_AT_THE_PIN


def test_one_input_is_given_its_route_after_its_own_options() -> None:
    """After the format's own, so an option of the same name given earlier cannot undo it."""
    item: dict[str, Any] = {
        "url": "https://m.example/c.mp4",
        "protocol": "https",
        "downloader_options": {"ffmpeg_args": ["-tls_verify", "0"], "ffmpeg_args_out": ["-x"]},
    }

    held = _held(item)

    arguments = _arguments(held)
    assert arguments[:2] == ["-tls_verify", "0"]
    assert arguments[arguments.index("-tls_verify", 2) + 1] == "1"
    assert arguments[arguments.index("-local_addr") + 1] == "0.0.0.0"  # noqa: S104
    assert held["downloader_options"]["ffmpeg_args_out"] == ["-x"]
    assert item["downloader_options"]["ffmpeg_args"] == ["-tls_verify", "0"], "yt-dlp's was changed"


def test_each_merged_input_takes_the_item_s_options_where_it_has_none() -> None:
    """As `FFmpegFD` reads them: an input's own `ffmpeg_args`, or else the item's."""
    item = {
        "downloader_options": {"ffmpeg_args": ["-item"]},
        "requested_formats": [
            {"url": "https://m.example/v.mp4", "protocol": "https"},
            {
                "url": "https://m.example/a.m4a",
                "protocol": "https",
                "downloader_options": {"ffmpeg_args": ["-own"]},
            },
        ],
    }

    first, second = _held(item)["requested_formats"]

    assert _arguments(first)[0] == "-item"
    assert _arguments(second)[0] == "-own"
    assert "-tls_verify" in _arguments(first) and "-tls_verify" in _arguments(second)


def test_the_headers_are_the_ones_yt_dlp_sends() -> None:
    item = {
        "url": "http://m.example/c.mp4",
        "protocol": "http",
        "http_headers": {"Ytdl-Request-Proxy": "http://named:1", "X-A": "b"},
    }

    held = _held(item)

    assert held["http_headers"] == {"X-A": "b"}
    assert _arguments(held)[_arguments(held).index("-http_proxy") + 1] == "http://named:1"


@pytest.mark.parametrize(
    "protocol", ["m3u8", "m3u8_native", "http_dash_segments", "rtmp", "ftp", None]
)
def test_an_input_that_is_not_one_web_file_is_refused(protocol: str | None) -> None:
    """**A live stream, Zan's angles, and a section of anything in pieces**: ffmpeg fetches a
    manifest's pieces without the address or the certificate check it was given."""
    item = {
        "requested_formats": [
            {"url": "https://m.example/v.mp4", "protocol": "https"},
            {"url": "https://m.example/a.m3u8", "protocol": protocol},
        ]
    }

    with pytest.raises(RouteRefusedError) as refused:
        _held(item)

    assert refused.value.reason == NOT_ONE_WEB_FILE


def test_a_link_that_is_not_on_the_web_is_refused() -> None:
    with pytest.raises(RouteRefusedError):
        _held({"url": "file:///tmp/c.m3u8", "protocol": "https"})


def test_what_yt_dlp_feeds_ffmpeg_itself_is_left_alone() -> None:
    """The websocket downloader connects and pipes what it receives into ffmpeg's standard
    input, so ffmpeg itself connects to nothing."""
    item = {"url": "-", "protocol": "websocket_frag", "http_headers": {"X": "y"}}

    assert _held(item) == item


@pytest.mark.parametrize("proxy", ["socks5://s:1", "https://s:1"])
def test_a_proxy_ffmpeg_would_go_around_is_refused(proxy: str) -> None:
    with pytest.raises(RouteRefusedError) as refused:
        _held({"url": "https://m.example/c.mp4", "protocol": "https"}, {"all": proxy})

    assert refused.value.reason == NOT_THROUGH_THE_PROXY


def test_the_refusals_are_plain_and_name_no_proxy() -> None:
    for reason in (NOT_ONE_WEB_FILE, NOT_THROUGH_THE_PROXY):
        assert "\u2013" not in reason and "\u2014" not in reason
        assert "@" not in reason


def test_yt_dlp_is_put_back_however_the_block_ends() -> None:
    call, popen = FFmpegFD._call_downloader, external.Popen

    with pytest.raises(KeyError), on_the_route(external, networking, {}, None, 20.0):
        assert FFmpegFD._call_downloader is not call
        raise KeyError

    assert FFmpegFD._call_downloader is call
    assert external.Popen is popen


def test_a_format_test_is_told_ffmpeg_failed_rather_than_stopped() -> None:
    """`--check-formats` catches only yt-dlp's own errors, so a refused format is one ffmpeg
    failed on, and the item goes on to the next format."""
    with yt_dlp.YoutubeDL({"quiet": True, "test": True}) as ydl:
        downloader = FFmpegFD(ydl, ydl.params)
        with on_the_route(external, networking, {}, None, 20.0):
            code = downloader._call_downloader(
                "unused.mp4", {"url": "https://m.example/a.m3u8", "protocol": "m3u8"}
            )

    assert code == 1


def test_a_plain_link_is_given_no_certificate_check_and_may_use_no_tls() -> None:
    """ffmpeg refuses an input option nothing uses, and `http://` opens no TLS; a redirect could
    take it to an `https://` link it would fetch unchecked (measured 2026-10-29, exit 8). With no
    TLS to use, that redirect fails, so one to another `http://` link can be followed, without
    `-max_redirects`, which a build before FFmpeg 8.1 does not define (`T368-R5`)."""
    arguments = _arguments(_held({"url": "http://m.example/c.mp4", "protocol": "http"}))

    assert "-tls_verify" not in arguments
    assert arguments[arguments.index("-protocol_whitelist") + 1] == PLAIN_LINK_PROTOCOLS
    assert "-max_redirects" not in arguments
    assert not {"tls", "https", "httpproxy"} & set(PLAIN_LINK_PROTOCOLS.split(","))


def test_a_plain_link_follows_no_redirect_where_the_route_could_change() -> None:
    item = {"url": "http://m.example/c.mp4", "protocol": "http"}

    arguments = _arguments(_held(item, EXCEPTED))

    assert arguments[arguments.index("-max_redirects") + 1] == "0"


def test_an_https_link_is_checked_and_follows_a_redirect_that_cannot_change_the_route() -> None:
    arguments = _arguments(_held({"url": "https://m.example/c.mp4", "protocol": "https"}))

    assert arguments[arguments.index("-tls_verify") + 1] == "1"
    assert "-max_redirects" not in arguments


@pytest.mark.parametrize("proxy", ["HTTP://u:p@s:1", "Http://s:1/x"])
def test_a_proxy_written_in_capitals_is_handed_on_as_ffmpeg_reads_it(proxy: str) -> None:
    """**`T368-R4`**: ffmpeg takes a proxy only where the text starts `http://`, and otherwise
    connects directly, where yt-dlp goes through it."""
    arguments = _arguments(
        _held({"url": "https://m.example/c.mp4", "protocol": "https"}, {"all": proxy})
    )

    given = arguments[arguments.index("-http_proxy") + 1]
    assert given.startswith("http://") and given[len("http://") :] == proxy.partition("://")[2]


def test_an_input_left_with_no_headers_does_not_take_the_item_s() -> None:
    """**`T368-R1`**: the pin's `FFmpegFD` sends an input's headers, or the item's where those
    are empty, and an input whose only header was `Ytdl-Request-Proxy` is left with none. Each
    input still takes the item's headers where it has none of its own, as yt-dlp sends them."""
    named = "http://named:1"
    item = {
        "http_headers": {"Ytdl-Request-Proxy": named, "User-Agent": "UA"},
        "requested_formats": [
            {"url": "https://m.example/v.mp4", "protocol": "https",
             "http_headers": {"Ytdl-Request-Proxy": named}},
            {"url": "https://m.example/a.m4a", "protocol": "https"},
            {"url": "https://m.example/b.m4a", "protocol": "https", "http_headers": {"X-Own": "1"}},
        ],
    }  # fmt: skip

    held = _held(item)

    # As the pin's `FFmpegFD` chooses each input's headers.
    sent = [
        fmt.get("http_headers") or held.get("http_headers") for fmt in held["requested_formats"]
    ]
    assert sent == [{}, {"User-Agent": "UA"}, {"X-Own": "1"}]
    proxies = [
        _arguments(fmt)[_arguments(fmt).index("-http_proxy") + 1]
        for fmt in held["requested_formats"]
    ]
    assert proxies == [named, named, ""]


@pytest.mark.parametrize(
    ("url", "proxies", "lacking", "refused"),
    [
        # Ubuntu 24.04's 6.1.1 has no `max_redirects`: refused only where a route passes it.
        ("https://m.example/c.mp4", EXCEPTED, "max_redirects", True),
        ("http://m.example/c.mp4", EXCEPTED, "max_redirects", True),
        ("https://m.example/c.mp4", DIRECT, "max_redirects", False),
        ("http://m.example/c.mp4", DIRECT, "max_redirects", False),
        # Debian 12's 5.1.9 has no `local_addr`, which an address to connect from passes.
        ("https://m.example/c.mp4", DIRECT, "local_addr", True),
        # A build without TLS: a plain link is given no certificate check to define.
        ("https://m.example/c.mp4", DIRECT, "tls_verify", True),
        ("http://m.example/c.mp4", DIRECT, "tls_verify", False),
    ],
)
def test_an_input_needing_an_option_the_ffmpeg_in_use_lacks_is_refused(
    url: str, proxies: dict[str, str], lacking: str, refused: bool
) -> None:
    item = {"url": url, "protocol": url.partition(":")[0]}

    if refused:
        with pytest.raises(RouteRefusedError) as raised:
            _held(item, proxies, EVERY - {lacking})
        assert raised.value.reason == NOT_WITH_THIS_FFMPEG
    else:
        assert "-" + lacking not in _arguments(_held(item, proxies, EVERY - {lacking}))


def test_the_ffmpeg_in_use_is_asked_once_a_session_and_only_for_a_link(
    monkeypatch: pytest.MonkeyPatch, every_option: list[str]
) -> None:
    """The binary the pin's method would run, found the way it finds it."""
    monkeypatch.setattr(FFmpegFD, "_call_downloader", lambda *_: 0)
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl, for_the_session(yt_dlp, {}, None, 20.0):
        downloader = FFmpegFD(ydl, ydl.params)
        with pytest.raises(RouteRefusedError):
            downloader._call_downloader(
                "a.mp4", {"url": "https://m.example/a.m3u8", "protocol": "m3u8"}
            )
        assert every_option == []
        for name in ("b.mp4", "c.mp4"):
            downloader._call_downloader(name, {"url": "https://m.example/c", "protocol": "https"})

    assert every_option == ["/opt/ffmpeg/ffmpeg"]


@pytest.mark.usefixtures("every_option")
def test_where_no_ffmpeg_is_found_no_link_is_handed_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing to ask what it defines, so nothing it might not carry is given to it."""
    monkeypatch.setattr(_Found, "available", False)
    monkeypatch.setattr(_Found, "executable", None)
    called: list[None] = []
    monkeypatch.setattr(FFmpegFD, "_call_downloader", lambda *_: called.append(None))

    with (
        yt_dlp.YoutubeDL({"quiet": True}) as ydl,
        for_the_session(yt_dlp, {}, None, 20.0),
        pytest.raises(RouteRefusedError) as refused,
    ):
        FFmpegFD(ydl, ydl.params)._call_downloader(
            "a.mp4", {"url": "https://m.example/c", "protocol": "https"}
        )

    assert refused.value.reason == NOT_WITH_THIS_FFMPEG
    assert called == []


def test_a_copy_without_ffmpeg_s_downloader_is_left_as_it_is() -> None:
    import types

    with for_the_session(types.ModuleType("not_yt_dlp"), {}, None, 20.0):
        pass


def test_a_copy_without_the_route_functions_refuses_every_download_ffmpeg_would_make() -> None:
    """Fail closed: with no way to tell yt-dlp's route, ffmpeg is given no link."""
    with pytest.raises(RouteRefusedError) as refused:
        _routed(
            {"url": "https://m.example/c.mp4", "protocol": "https"}, None, {}, None, 20.0, frozenset
        )

    assert refused.value.reason == NOT_ONE_WEB_FILE


@pytest.mark.usefixtures("every_option")
def test_with_no_timeout_chosen_ffmpeg_waits_as_long_as_yt_dlp_would(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The copy's own `DEFAULT_TIMEOUT`, which the request leaves to it."""
    from yt_dlp.networking.common import DEFAULT_TIMEOUT

    seen: list[dict[str, Any]] = []

    def record(_self: Any, _name: str, info: dict[str, Any]) -> int:
        seen.append(info)
        return 0

    monkeypatch.setattr(FFmpegFD, "_call_downloader", record)
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl, for_the_session(yt_dlp, {}, None, None):
        FFmpegFD(ydl, ydl.params)._call_downloader(
            "unused.mp4", {"url": "https://m.example/c", "protocol": "https"}
        )

    arguments = _arguments(seen[0])
    assert arguments[arguments.index("-timeout") + 1] == str(round(DEFAULT_TIMEOUT * 1_000_000))


@pytest.mark.usefixtures("every_option")
def test_ffmpeg_is_started_without_proxy_variables_and_popen_is_put_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ffmpeg reads `http_proxy` and `no_proxy` itself, so it is started by a `Popen` that leaves
    them out, for that call only."""
    popen = external.Popen
    during: list[Any] = []

    def record(_self: Any, _name: str, _info: dict[str, Any]) -> int:
        during.append(external.Popen)
        return 0

    monkeypatch.setattr(FFmpegFD, "_call_downloader", record)
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl, for_the_session(yt_dlp, {}, None, 20.0):
        FFmpegFD(ydl, ydl.params)._call_downloader(
            "unused.mp4", {"url": "https://m.example/c", "protocol": "https"}
        )
        assert external.Popen is popen, "not put back after the call"

    (started,) = during
    assert started is not popen and issubclass(started, popen)
    shown = "import os; print(sorted(k for k in os.environ if k.lower().endswith('_proxy')))"
    with started([sys.executable, "-c", shown], stdout=subprocess.PIPE, text=True) as child:
        assert child.communicate()[0].strip() == "[]"
