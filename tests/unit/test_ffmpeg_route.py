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

from tracks_and_trails.downloader.ffmpeg_route import (
    NOT_ONE_WEB_FILE,
    NOT_THROUGH_THE_PROXY,
    _routed,
    for_the_session,
    on_the_route,
)
from tracks_and_trails.downloader.media_probe import RouteRefusedError

#: `FFmpegFD._call_downloader` at the pin, as a digest of its text. **The guard leans on how it
#: reads its inputs**: `requested_formats` or the item, each input's `downloader_options` before
#: its `-i`, its `http_headers`, and the module's `Popen`. A release that changes the method fails
#: here, and the guard is read again against it before the digest moves.
CALL_DOWNLOADER_AT_THE_PIN = "fe869157381445943253ec0aba3bfb8170cb20009021362fb0da689124647bf4"

#: A direct route, IPv4 only, with yt-dlp's own timeout.
DIRECT: dict[str, str] = {}


def _arguments(item: dict[str, Any]) -> list[str]:
    return list(item["downloader_options"]["ffmpeg_args"])


def _held(item: dict[str, Any], proxies: dict[str, str] | None = None) -> dict[str, Any]:
    return _routed(item, networking, proxies or DIRECT, "0.0.0.0", 20.0)  # noqa: S104


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


def test_a_plain_link_is_given_no_certificate_check_and_follows_no_redirect() -> None:
    """ffmpeg refuses an input option nothing uses, and `http://` opens no TLS; a redirect could
    take it to an `https://` link it would fetch unchecked (measured 2026-10-29, exit 8)."""
    arguments = _arguments(_held({"url": "http://m.example/c.mp4", "protocol": "http"}))

    assert "-tls_verify" not in arguments
    assert arguments[arguments.index("-max_redirects") + 1] == "0"


def test_an_https_link_is_checked_and_follows_a_redirect_that_cannot_change_the_route() -> None:
    arguments = _arguments(_held({"url": "https://m.example/c.mp4", "protocol": "https"}))

    assert arguments[arguments.index("-tls_verify") + 1] == "1"
    assert "-max_redirects" not in arguments


def test_a_copy_without_ffmpeg_s_downloader_is_left_as_it_is() -> None:
    import types

    with for_the_session(types.ModuleType("not_yt_dlp"), {}, None, 20.0):
        pass


def test_a_copy_without_the_route_functions_refuses_every_download_ffmpeg_would_make() -> None:
    """Fail closed: with no way to tell yt-dlp's route, ffmpeg is given no link."""
    with pytest.raises(RouteRefusedError) as refused:
        _routed({"url": "https://m.example/c.mp4", "protocol": "https"}, None, {}, None, 20.0)

    assert refused.value.reason == NOT_ONE_WEB_FILE


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
