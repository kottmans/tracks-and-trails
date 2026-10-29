"""ffmpeg's own downloads keep to yt-dlp's route, or do not start (`T-368`, `T252-R7`).

**The pinned `FFmpegFD`, driven directly with the real ffmpeg**, against servers on loopback, the
exception `docs/project/TESTING.md` grants the localhost suites; one case goes through the real
worker, to show the guard is where the download is. Measured on 2026-10-27 and again on
2026-10-29, before this task: told to connect from `127.0.0.2`, the cut connected from
`127.0.0.1`; given a proxy and a `no_proxy` naming the site, it went around the proxy; it sent a
`Ytdl-Request-Proxy` header on to the site; it read a certificate nobody signed.

**Each case has its control**: the same download by the pin's `FFmpegFD` without the guard, which
shows the instrument sees the difference the guard makes.
"""

from __future__ import annotations

import contextlib
import functools
import itertools
import ssl
import subprocess
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from queue import Queue
from typing import Any
from urllib.parse import urlsplit

import pytest
import yt_dlp
from yt_dlp.downloader import external
from yt_dlp.downloader.external import FFmpegFD
from yt_dlp.utils import DownloadError, networking

from tests.capabilities import resolve_ffmpeg
from tests.integration.loopback import (
    BOUND,
    PROXY_SIDE,
    SERVER_CONTEXT,
    Origin,
    Proxy,
    Redirect,
    clear_ambient_proxies,
    make_certificate,
    make_site,
    needs_loopback_addresses,
    origin_on,
    proxy_on,
    redirect_on,
    serve,
)
from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.downloader import worker
from tracks_and_trails.downloader.ffmpeg_route import (
    NOT_ONE_WEB_FILE,
    NOT_THROUGH_THE_PROXY,
    on_the_route,
)
from tracks_and_trails.downloader.media_probe import RouteRefusedError, proxy_table
from tracks_and_trails.downloader.protocol import Failed, SessionKind, Succeeded

# --- the length read's servers (`loopback.py`): one route, read and then fetched -------------


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_site(tmp_path_factory)


@pytest.fixture
def origin(site: Path) -> Iterator[tuple[str, type[Origin]]]:
    yield from origin_on(site, "127.0.0.1")


@pytest.fixture
def redirect(site: Path) -> Iterator[tuple[str, type[Redirect], type[Origin]]]:
    yield from redirect_on(site)


@pytest.fixture
def proxy() -> Iterator[tuple[str, type[Proxy]]]:
    yield from proxy_on()


@pytest.fixture(scope="module")
def certificate(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    return make_certificate(tmp_path_factory)


@pytest.fixture(autouse=True)
def no_ambient_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_ambient_proxies(monkeypatch)


def _cut(
    url: str,
    folder: Path,
    *,
    guarded: bool = True,
    proxy: str | None = None,
    source_address: str | None = None,
    params: dict[str, Any] | None = None,
    **info: Any,
) -> Path:
    """Seconds one to three of `url`, by the pin's `FFmpegFD`, kept to the route when `guarded`.

    yt-dlp is given the same settings either way: the request's proxy as `--proxy` gives it, and
    the address to connect from."""
    settings: dict[str, Any] = {"quiet": True, **(params or {})}
    if proxy:
        settings["proxy"] = proxy
    if source_address:
        settings["source_address"] = source_address
    # A name of its own each time: yt-dlp skips a download whose file is already there.
    out = folder / f"cut-{next(_CUTS)}.mp4"
    item: dict[str, Any] = {
        "url": url,
        "protocol": urlsplit(url).scheme,
        "ext": "mp4",
        "section_start": 1,
        "section_end": 3,
        "to_stdout": False,
        **info,
    }
    table = proxy_table(proxy, urllib.request.getproxies())
    with yt_dlp.YoutubeDL(settings) as ydl:
        downloader = FFmpegFD(ydl, ydl.params)
        route = (
            on_the_route(external, networking, table, source_address, 20.0)
            if guarded
            else contextlib.nullcontext()
        )
        with route:
            downloader.download(str(out), item)
    return out


_CUTS = itertools.count()


@functools.cache
def _ffprobe() -> str:
    return resolve_ffmpeg()[1]


def _seconds(path: Path) -> float:
    shown = subprocess.run(
        [
            _ffprobe(),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(shown.stdout.strip())


@needs_loopback_addresses
def test_the_cut_connects_from_the_request_s_address(
    origin: tuple[str, type[Origin]], tmp_path: Path
) -> None:
    """**The review's case, `T252-R7` and `T253-R3`**: yt-dlp told to connect from `127.0.0.2`,
    and the pin's cut connecting from `127.0.0.1`."""
    url, served = origin
    _cut(url, tmp_path, guarded=False, source_address=BOUND)
    assert served.callers == ["127.0.0.1"], "the control: the pin's cut used the address"
    served.callers.clear()

    written = _cut(url, tmp_path, source_address=BOUND)

    assert _seconds(written) == pytest.approx(2, abs=0.3)
    assert served.callers and set(served.callers) == {BOUND}, served.callers


@needs_loopback_addresses
def test_the_cut_goes_through_the_request_s_proxy_whatever_no_proxy_says(
    origin: tuple[str, type[Origin]],
    proxy: tuple[str, type[Proxy]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """yt-dlp takes the request's proxy for every link, `no_proxy` or not; the pin gave ffmpeg the
    environment with `no_proxy` still in it, and ffmpeg reads that itself."""
    url, served = origin
    address, forwarded = proxy
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    _cut(url, tmp_path, guarded=False, proxy=address)
    assert served.callers == ["127.0.0.1"], "the control: the pin's cut kept to the proxy"
    served.callers.clear()

    _cut(url, tmp_path, proxy=address)

    assert forwarded.asked, "the proxy was not asked"
    assert served.callers and set(served.callers) == {PROXY_SIDE}, served.callers


@needs_loopback_addresses
def test_a_link_the_system_exempts_is_cut_directly(
    origin: tuple[str, type[Origin]],
    proxy: tuple[str, type[Proxy]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With `http_proxy` set and `no_proxy` naming the site, yt-dlp reaches it directly."""
    url, served = origin
    address, forwarded = proxy
    monkeypatch.setenv("http_proxy", address)
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        ydl.urlopen(url).read()
    assert served.callers == ["127.0.0.1"] and forwarded.asked == [], "the control was proxied"
    served.callers.clear()

    _cut(url, tmp_path)

    assert forwarded.asked == []
    assert served.callers and set(served.callers) == {"127.0.0.1"}, served.callers


def test_a_proxy_ffmpeg_would_go_around_refuses_the_cut_before_it_starts(
    origin: tuple[str, type[Origin]], tmp_path: Path
) -> None:
    """Handed a SOCKS proxy the pin's cut connected directly; this one never starts."""
    url, served = origin
    _cut(url, tmp_path, guarded=False, proxy="socks5://127.0.0.1:9")
    assert served.callers == ["127.0.0.1"], "the control: the pin's cut did not go direct"
    served.callers.clear()

    with pytest.raises(RouteRefusedError) as refused:
        _cut(url, tmp_path, proxy="socks5://127.0.0.1:9")

    assert refused.value.reason == NOT_THROUGH_THE_PROXY
    assert served.callers == []


def test_a_manifest_is_never_handed_to_ffmpeg(
    origin: tuple[str, type[Origin]], tmp_path: Path
) -> None:
    """ffmpeg fetches a manifest's pieces without the address or the certificate check it was
    given (measured 2026-10-27), so a format that comes in pieces is refused before it starts."""
    url, served = origin
    playlist = url.replace("clip.mp4", "clip.m3u8")
    _cut(playlist, tmp_path, guarded=False, protocol="m3u8")
    assert len(served.callers) > 1, "the control fetched no piece"
    served.callers.clear()

    with pytest.raises(RouteRefusedError) as refused:
        _cut(playlist, tmp_path, protocol="m3u8")

    assert refused.value.reason == NOT_ONE_WEB_FILE
    assert served.callers == []


def test_a_format_test_counts_a_refused_format_as_not_working(
    origin: tuple[str, type[Origin]], tmp_path: Path
) -> None:
    """`--check-formats` downloads a little of each format, catching only yt-dlp's own errors: a
    refused one is reported as not working rather than ending the item, and nothing is asked."""
    url, served = origin
    playlist = url.replace("clip.mp4", "clip.m3u8")

    with pytest.raises(DownloadError):
        _cut(playlist, tmp_path, protocol="m3u8", params={"test": True})

    assert served.callers == []


def test_a_certificate_nobody_signed_stops_the_cut(
    site: Path, certificate: tuple[Path, Path], tmp_path: Path
) -> None:
    """**`SEC-004`**: ffmpeg checks no certificate unless asked. The control, the pin's cut, reads
    this server; the guarded one sends no request. An extractor's own input options come first,
    so one asking for no check cannot undo it."""
    handler: type[Origin] = type("Origin", (Origin,), {"callers": [], "heard": []})
    for server in serve(functools.partial(handler, directory=str(site))):  # type: ignore[arg-type]
        context = SERVER_CONTEXT(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(*certificate)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        url = f"https://127.0.0.1:{server.server_address[1]}/clip.mp4"
        assert _seconds(_cut(url, tmp_path, guarded=False)) == pytest.approx(2, abs=0.3)
        handler.callers.clear()

        with pytest.raises(DownloadError):
            _cut(url, tmp_path, downloader_options={"ffmpeg_args": ["-tls_verify", "0"]})

        assert handler.callers == [], "a request was sent to a server nobody vouched for"


@needs_loopback_addresses
def test_a_proxy_a_header_names_carries_the_cut_and_is_never_sent(
    origin: tuple[str, type[Origin]], proxy: tuple[str, type[Proxy]], tmp_path: Path
) -> None:
    """yt-dlp takes `Ytdl-Request-Proxy` as the proxy and sends it nowhere; the pin's cut sent it
    on to the site, and went directly."""
    url, served = origin
    address, forwarded = proxy
    headers = {"Ytdl-Request-Proxy": address}
    _cut(url, tmp_path, guarded=False, http_headers=headers)
    assert served.callers == ["127.0.0.1"], "the control: the pin's cut took the header's proxy"
    assert any("ytdl-request-proxy" in heard for heard in served.heard), "the control: not sent"
    served.callers.clear()
    served.heard.clear()

    _cut(url, tmp_path, http_headers=headers)

    assert forwarded.asked, "the header's proxy was not asked"
    assert served.callers and set(served.callers) == {PROXY_SIDE}, served.callers
    assert all("ytdl-request-proxy" not in heard for heard in served.heard), "the header was sent"


@needs_loopback_addresses
def test_a_redirect_is_not_followed_where_it_could_change_the_route(
    redirect: tuple[str, type[Redirect], type[Origin]],
    proxy: tuple[str, type[Proxy]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """yt-dlp would reach the first host directly and the second through the proxy; ffmpeg keeps
    one route for both, so it follows no redirect and the cut fails."""
    url, sent_on, served = redirect
    address, forwarded = proxy
    monkeypatch.setenv("http_proxy", address)
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        ydl.urlopen(url).read()
    assert served.callers == [PROXY_SIDE], "the control did not take the proxy to the second"
    sent_on.callers.clear()
    served.callers.clear()
    forwarded.asked.clear()

    with pytest.raises(DownloadError):
        _cut(url, tmp_path)

    assert sent_on.callers and set(sent_on.callers) == {"127.0.0.1"}, sent_on.callers
    assert served.callers == [], "the redirect was followed by a route yt-dlp would not take"
    assert forwarded.asked == []


def _session(url: str, folder: Path, **fields: Any) -> Any:
    """One section, one to three seconds, through the real worker; its outcome."""
    request = DownloadRequest(
        url=url,
        output_directory=str(folder),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        download_sections=("*1-3",),
        **fields,
    )
    queue: Queue[Any] = Queue()
    worker.run_session(SessionKind.DOWNLOAD, "job-1", request, queue)
    messages = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return next((m for m in messages if isinstance(m, Succeeded | Failed)), messages)


@needs_loopback_addresses
def test_the_worker_s_own_section_download_connects_from_the_address(
    origin: tuple[str, type[Origin]], tmp_path: Path
) -> None:
    """**The guard is where the download is**: the review's case through the real worker, its
    probe and its cut both from the address the request names."""
    url, served = origin

    outcome = _session(url, tmp_path, source_address=BOUND)

    assert isinstance(outcome, Succeeded), outcome
    assert _seconds(Path(outcome.output_path)) == pytest.approx(2, abs=0.3)
    assert served.callers and set(served.callers) == {BOUND}, served.callers


def test_a_section_of_an_item_in_pieces_is_cancelled_with_the_reason(
    origin: tuple[str, type[Origin]], tmp_path: Path
) -> None:
    """yt-dlp gives this HLS item's length itself, so nothing is read first: ffmpeg is what would
    fetch its pieces, and the worker ends the item as cancelled, saying why."""
    url, _ = origin

    outcome = _session(url.replace("clip.mp4", "clip.m3u8"), tmp_path)

    assert isinstance(outcome, Failed), outcome
    assert (outcome.kind, outcome.message) == (ErrorKind.CANCELLED, NOT_ONE_WEB_FILE)
    assert list(tmp_path.iterdir()) == []
