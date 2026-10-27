"""A section's length is read from its link by the request's route, or not at all (`T252-R5`).

**Real ffprobe, through the worker's own placement**, against servers on loopback, the exception
`docs/project/TESTING.md` grants the localhost suites. Measured on 2026-10-27 by the review and
again here: ffprobe left to itself read the length directly while the request named a proxy, and
from any address while it named one to connect from (`T253-R3`), and checked no certificate.

**The origin tells a direct read from one through the proxy** because the proxy here connects out
from `127.0.0.3`; an address to connect from is told the same way, by `127.0.0.2`. Each case has
a control showing the instrument sees what the read is checked against.
"""

from __future__ import annotations

import functools
import http.client
import shutil
import socket
import ssl
import subprocess
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar, Final
from urllib.parse import urlsplit

import pytest
import yt_dlp
from yt_dlp.cookies import LenientSimpleCookie
from yt_dlp.networking.exceptions import TransportError
from yt_dlp.utils import Popen

from tests.capabilities import resolve_ffmpeg
from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.core.sections import NO_LENGTH, NOT_THROUGH_THE_PROXY
from tracks_and_trails.downloader import worker
from tracks_and_trails.downloader.media_probe import run_with

#: Where the proxy connects out from, so the origin can tell it from a direct connection.
PROXY_SIDE: Final = "127.0.0.3"

#: An address to connect from, other than the one a connection would otherwise come from.
BOUND: Final = "127.0.0.2"


def _can_bind(address: str) -> bool:
    with socket.socket() as probe:
        try:
            probe.bind((address, 0))
        except OSError:
            return False
    return True


needs_loopback_addresses = pytest.mark.skipif(
    not (_can_bind(PROXY_SIDE) and _can_bind(BOUND)),
    reason=f"this machine cannot bind {PROXY_SIDE} and {BOUND}, which tell the routes apart",
)


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A six-second clip, its index first, and the same clip as HLS pieces."""
    ffmpeg, _ = resolve_ffmpeg()
    directory = tmp_path_factory.mktemp("site")
    subprocess.run(
        [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=25:duration=6",
         "-c:v", "libx264", "-preset", "ultrafast", "-movflags", "+faststart",
         str(directory / "clip.mp4")],
        check=True,
    )  # fmt: skip
    subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(directory / "clip.mp4"), "-c", "copy", "-f", "hls",
         "-hls_time", "1", "-hls_list_size", "0", str(directory / "clip.m3u8")],
        check=True,
    )  # fmt: skip
    return directory


class _Origin(SimpleHTTPRequestHandler):
    """Serves the clip, keeping the address of every connection that asked for it."""

    callers: ClassVar[list[str]]

    # `http.server`'s own name, hence the camelCase.
    def do_GET(self) -> None:
        type(self).callers.append(self.client_address[0])
        super().do_GET()

    def log_message(self, *_: Any) -> None:
        """Silence the handler's stderr logging; a test is not a web server."""


def _serve(handler: type, address: str = "127.0.0.1") -> Iterator[ThreadingHTTPServer]:
    server = ThreadingHTTPServer((address, 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture
def origin(site: Path) -> Iterator[tuple[str, type[_Origin]]]:
    handler = type("Origin", (_Origin,), {"callers": []})
    for server in _serve(functools.partial(handler, directory=str(site))):  # type: ignore[arg-type]
        yield f"http://127.0.0.1:{server.server_address[1]}/clip.mp4", handler


class _Proxy(BaseHTTPRequestHandler):
    """An HTTP proxy for `http://` links, connecting out from `PROXY_SIDE`, counting requests."""

    asked: ClassVar[list[str]]

    def do_GET(self) -> None:
        type(self).asked.append(self.path)
        target = urlsplit(self.path)
        upstream = http.client.HTTPConnection(
            target.hostname or "", target.port, timeout=10, source_address=(PROXY_SIDE, 0)
        )
        headers = {k: v for k, v in self.headers.items() if k.lower() != "proxy-connection"}
        upstream.request("GET", target.path, headers=headers)
        answer = upstream.getresponse()
        body = answer.read()
        self.send_response(answer.status)
        for name, value in answer.getheaders():
            if name.lower() not in ("connection", "transfer-encoding", "content-length"):
                self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        upstream.close()

    def log_message(self, *_: Any) -> None:
        """Silence the handler's stderr logging; a test is not a web server."""


@pytest.fixture
def proxy() -> Iterator[tuple[str, type[_Proxy]]]:
    handler = type("Proxy", (_Proxy,), {"asked": []})
    for server in _serve(handler):
        yield f"http://127.0.0.1:{server.server_address[1]}", handler


@pytest.fixture(autouse=True)
def no_ambient_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """The route is the request's: a proxy in the suite's own environment must not decide it."""
    for name in ("http_proxy", "https_proxy", "all_proxy", "no_proxy"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.upper(), raising=False)


def _placed(url: str, **fields: Any) -> float | None:
    """`_place_the_sections` on a link that gives no length, with the real ffprobe."""
    request = DownloadRequest(
        url=url,
        output_directory="/unused",
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        download_sections=("*-2-inf",),
        **fields,
    )
    _, ffprobe = resolve_ffmpeg()
    return worker._place_the_sections(
        request,
        {"url": url, "protocol": urlsplit(url).scheme},
        Path(ffprobe),
        run_with(Popen),
        LenientSimpleCookie,
        20.0,
    )


@needs_loopback_addresses
def test_the_length_is_read_through_the_request_s_proxy(
    origin: tuple[str, type[_Origin]], proxy: tuple[str, type[_Proxy]]
) -> None:
    """**The review's case, `T252-R5`**: the same proxy on the request that yt-dlp goes through.
    The read had gone around it, reaching the origin directly with no request to the proxy."""
    url, served = origin
    address, forwarded = proxy
    with yt_dlp.YoutubeDL({"proxy": address, "quiet": True}) as ydl:
        ydl.urlopen(url).read()
    assert forwarded.asked and served.callers == [PROXY_SIDE], "the control did not go through"
    forwarded.asked.clear()
    served.callers.clear()

    assert _placed(url, proxy=address) == pytest.approx(6, abs=0.1)

    assert forwarded.asked, "the proxy was not asked"
    assert set(served.callers) == {PROXY_SIDE}, f"the origin was reached directly: {served.callers}"


def test_a_proxy_ffprobe_would_go_around_is_never_tried(origin: tuple[str, type[_Origin]]) -> None:
    """ffmpeg handed a SOCKS proxy connected directly (measured 2026-10-27), so it is not handed
    one: the item is cancelled and the origin never asked."""
    url, served = origin

    with pytest.raises(worker.NothingDownloadedError) as cancelled:
        _placed(url, proxy="socks5://127.0.0.1:9")

    assert cancelled.value.reason == NOT_THROUGH_THE_PROXY
    assert served.callers == []


@needs_loopback_addresses
def test_the_length_is_read_from_the_request_s_address(origin: tuple[str, type[_Origin]]) -> None:
    """`T253-R3`: connections are made from the address the request names, as yt-dlp's are."""
    url, served = origin
    with yt_dlp.YoutubeDL({"source_address": BOUND, "quiet": True}) as ydl:
        ydl.urlopen(url).read()
    assert served.callers == [BOUND], "the control did not connect from the address"
    served.callers.clear()

    assert _placed(url, source_address=BOUND) == pytest.approx(6, abs=0.1)

    assert served.callers and set(served.callers) == {BOUND}, served.callers


def test_ipv6_only_does_not_reach_an_ipv4_origin(origin: tuple[str, type[_Origin]]) -> None:
    """**The review's case, `T253-R3`**: yt-dlp told to use IPv6 only cannot reach this origin,
    which is IPv4 only, and the read had reached it and returned six seconds."""
    url, served = origin
    with (
        yt_dlp.YoutubeDL({"source_address": "::", "quiet": True}) as ydl,
        pytest.raises(TransportError, match="No remote IPv6 addresses"),
    ):
        ydl.urlopen(url).read()

    with pytest.raises(worker.NothingDownloadedError) as cancelled:
        _placed(url, source_address="::")

    assert cancelled.value.reason == NO_LENGTH
    assert served.callers == []


@pytest.fixture(scope="module")
def certificate(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """A certificate for `127.0.0.1` signed by nobody, made now, since none is kept in the tree."""
    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("no openssl program to make a certificate with")
    directory = tmp_path_factory.mktemp("tls")
    certificate, key = directory / "cert.pem", directory / "key.pem"
    subprocess.run(
        [openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
         "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1",
         "-keyout", str(key), "-out", str(certificate)],
        check=True,
        capture_output=True,
    )  # fmt: skip
    return certificate, key


def test_a_certificate_nobody_signed_is_refused(site: Path, certificate: tuple[Path, Path]) -> None:
    """The read sends the site's cookies, and ffmpeg checks no certificate unless asked, which
    `SEC-004` forbids yt-dlp. The control: ffprobe left to itself reads this server."""
    handler: type[_Origin] = type("Origin", (_Origin,), {"callers": []})
    for server in _serve(functools.partial(handler, directory=str(site))):  # type: ignore[arg-type]
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(*certificate)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        url = f"https://127.0.0.1:{server.server_address[1]}/clip.mp4"
        _, ffprobe = resolve_ffmpeg()
        unchecked = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", url],
            capture_output=True,
            text=True,
            check=False,
        )
        assert float(unchecked.stdout) == pytest.approx(6, abs=0.1), "the control read nothing"
        handler.callers.clear()

        with pytest.raises(worker.NothingDownloadedError) as cancelled:
            _placed(url)

        assert cancelled.value.reason == NO_LENGTH
        assert handler.callers == [], "a request was sent to a server nobody vouched for"


def test_a_manifest_is_not_read_even_as_one_file(origin: tuple[str, type[_Origin]]) -> None:
    """ffmpeg fetches HLS pieces from wherever the playlist says, without the address to connect
    from or a certificate check (measured 2026-10-27), so only a demuxer that reads one file may
    read the length: a playlist served as a plain link is not read past itself. The control:
    ffprobe left to itself reads it and its pieces."""
    url, served = origin
    playlist = url.replace("clip.mp4", "clip.m3u8")
    _, ffprobe = resolve_ffmpeg()
    unchecked = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", playlist],
        capture_output=True,
        text=True,
        check=False,
    )
    assert float(unchecked.stdout) == pytest.approx(6, abs=0.1), "the control read nothing"
    assert len(served.callers) > 1, "the control fetched no piece"
    served.callers.clear()

    with pytest.raises(worker.NothingDownloadedError) as cancelled:
        _placed(playlist)

    assert cancelled.value.reason == NO_LENGTH
    assert len(served.callers) == 1, "a piece was fetched past the playlist"
