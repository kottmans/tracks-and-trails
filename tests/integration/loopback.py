"""Servers on loopback that tell one route from another, for ffprobe and ffmpeg alike.

Shared by `test_length_route.py` (`T252-R5`), the length read, and `test_ffmpeg_route.py`
(`T-368`), the download: one route, read and then fetched. **The origin tells a direct connection
from one through the proxy** because the proxy connects out from `PROXY_SIDE`; an address to
connect from is told the same way, by `BOUND`. Each module wraps these in fixtures of its own.
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
from yt_dlp.utils import Popen

from tests.capabilities import resolve_ffmpeg
from tracks_and_trails.downloader.media_probe import defined_options, run_with

#: The standard library's own context class, for the server side. On Windows the application
#: replaces `ssl.SSLContext` with `truststore`'s for the whole process, and that one checks the
#: peer even when wrapping a listening socket, which has none (`T252-R8`). Taken when this module
#: is imported, before any test has run a session.
SERVER_CONTEXT: Final = ssl.SSLContext

#: Where the proxy connects out from, so the origin can tell it from a direct connection.
PROXY_SIDE: Final = "127.0.0.3"

#: An address to connect from, other than the one a connection would otherwise come from.
BOUND: Final = "127.0.0.2"

#: A host the system's exceptions do not name, which a redirect sends the read on to.
ELSEWHERE: Final = "127.0.0.5"


def can_bind(address: str) -> bool:
    with socket.socket() as probe:
        try:
            probe.bind((address, 0))
        except OSError:
            return False
    return True


needs_loopback_addresses = pytest.mark.skipif(
    not all(can_bind(address) for address in (PROXY_SIDE, BOUND, ELSEWHERE)),
    reason=f"this machine cannot bind {PROXY_SIDE}, {BOUND} and {ELSEWHERE}, which tell the routes "
    "apart",
)


@functools.cache
def defined_by(binary: str) -> frozenset[str]:
    """Which of the route's options the build at `binary` defines, asked as the application asks
    it (`T368-R5`). A case needing one it lacks expects the refusal the application gives instead,
    which is what this build does; `test_length_route` holds the list to what the build accepts."""
    return defined_options(binary, run_with(Popen))


def make_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
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


class Origin(SimpleHTTPRequestHandler):
    """Serves the clip, keeping the address of every connection that asked for it and the names
    of the headers each sent, lower-cased."""

    callers: ClassVar[list[str]]
    heard: ClassVar[list[set[str]]]

    # `http.server`'s own name, hence the camelCase.
    def do_GET(self) -> None:
        type(self).callers.append(self.client_address[0])
        type(self).heard.append({name.lower() for name in self.headers})
        super().do_GET()

    def log_message(self, *_: Any) -> None:
        """Silence the handler's stderr logging; a test is not a web server."""


def serve(handler: type, address: str = "127.0.0.1") -> Iterator[ThreadingHTTPServer]:
    server = ThreadingHTTPServer((address, 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def origin_on(site: Path, address: str) -> Iterator[tuple[str, type[Origin]]]:
    handler: type[Origin] = type("Origin", (Origin,), {"callers": [], "heard": []})
    for server in serve(functools.partial(handler, directory=str(site)), address):  # type: ignore[arg-type]
        yield f"http://{address}:{server.server_address[1]}/clip.mp4", handler


class Redirect(BaseHTTPRequestHandler):
    """Sends every request on to `to`, keeping the address of each connection."""

    to: ClassVar[str]
    callers: ClassVar[list[str]]

    def do_GET(self) -> None:
        type(self).callers.append(self.client_address[0])
        self.send_response(302)
        self.send_header("Location", type(self).to)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_: Any) -> None:
        """Silence the handler's stderr logging; a test is not a web server."""


def redirect_on(site: Path) -> Iterator[tuple[str, type[Redirect], type[Origin]]]:
    """A link on `127.0.0.1` that sends the read on to the clip on `ELSEWHERE`."""
    for target, served in origin_on(site, ELSEWHERE):
        handler = type("Redirect", (Redirect,), {"callers": [], "to": target})
        for server in serve(handler):
            yield f"http://127.0.0.1:{server.server_address[1]}/clip.mp4", handler, served


class Proxy(BaseHTTPRequestHandler):
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


def proxy_on() -> Iterator[tuple[str, type[Proxy]]]:
    """The proxy on `127.0.0.1`, with its own record of what it was asked."""
    handler = type("Proxy", (Proxy,), {"asked": []})
    for server in serve(handler):
        yield f"http://127.0.0.1:{server.server_address[1]}", handler


def clear_ambient_proxies(monkeypatch: pytest.MonkeyPatch) -> None:
    """The route is the request's: a proxy in the suite's own environment must not decide it."""
    for name in ("http_proxy", "https_proxy", "all_proxy", "no_proxy"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.upper(), raising=False)


def make_certificate(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
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
