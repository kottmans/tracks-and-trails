"""A kept info JSON never carries the session's cookies or request headers (`T-249`).

`DAT-003`, amended 2026-10-11. Measured that day: through the options field, `--write-info-json`
with a cookies file kept a file whose every format held the cookie's value, and whose formats held
an `Authorization` header typed through `--add-headers`. Each case here runs the real worker
session and the real yt-dlp against a server on `127.0.0.1`, the exception `docs/project/TESTING.md`
grants the other localhost suites, and reads the file that is actually kept.

Three routes to the file: the download that succeeds; the one that fails after the info JSON is
written, whose staging is kept for its resume (`T-113`); and a yt-dlp that does not run the
`before_dl` hook, which the worker's own pass before claiming still covers.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from typing import Any, Final

import pytest

from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.downloader import worker as worker_module
from tracks_and_trails.downloader import ytdlp_adapter
from tracks_and_trails.downloader.extra_options import options_for
from tracks_and_trails.downloader.protocol import Failed, SessionKind, Succeeded

BODY: Final = b"\0" * 4000
COOKIE: Final = "T249_COOKIE_VALUE"
HEADER: Final = "T249_HEADER_VALUE"


def _server(fail_after: int | None) -> type[BaseHTTPRequestHandler]:
    """A direct link to a clip, failing every request after the first `fail_after`, if given."""
    served = {"count": 0}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        # `http.server`'s own name, hence the camelCase.
        def do_GET(self) -> None:
            served["count"] += 1
            if fail_after is not None and served["count"] > fail_after:
                self.send_response(500)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(BODY)))
            self.end_headers()
            self.wfile.write(BODY)

        def log_message(self, *_: Any) -> None:
            """Silence the handler's stderr logging; a test is not a web server."""

    return Handler


@pytest.fixture
def serve() -> Iterator[Any]:
    servers: list[ThreadingHTTPServer] = []

    def start(fail_after: int | None = None) -> str:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _server(fail_after))
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_address[1]}/clip.mp4"

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def _session(url: str, tmp_path: Path, **fields: Any) -> tuple[list[Any], Path]:
    """One real download keeping its info JSON, signed in with a cookies file and a typed header."""
    cookies = tmp_path / "cookies.txt"
    cookies.write_text(
        f"# Netscape HTTP Cookie File\n127.0.0.1\tFALSE\t/\tFALSE\t0\tsession\t{COOKIE}\n",
        encoding="utf-8",
    )
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    text = f'--add-headers "Authorization: Bearer {HEADER}"'
    admission, argv = options_for(text)
    assert admission.usable, admission.refusals
    request = DownloadRequest(
        url=url,
        output_directory=str(downloads),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        write_info_json=True,
        extra_options=text,
        extra_option_argv=argv,
        **fields,
    )
    queue: Queue[Any] = Queue()
    worker_module.run_session(SessionKind.DOWNLOAD, "job-1", request, queue, cookie_file=cookies)
    messages: list[Any] = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return messages, downloads


def _info_files(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.info.json"))


def test_the_kept_info_json_carries_no_cookie_and_no_header(serve: Any, tmp_path: Path) -> None:
    """The measurement of 2026-10-11, as a test: both were in the file kept beside the clip."""
    messages, downloads = _session(serve(), tmp_path)

    assert [m for m in messages if isinstance(m, Succeeded)], messages
    [kept] = _info_files(downloads)
    text = kept.read_text(encoding="utf-8")
    assert COOKIE not in text and HEADER not in text, "a secret reached the kept info JSON"
    assert '"id"' in text, "the stripping threw away the file rather than its secrets"


def test_a_download_that_fails_keeps_a_staging_info_json_already_stripped(
    serve: Any, tmp_path: Path
) -> None:
    """The info JSON is written before the download; a failed attempt keeps staging for its resume,
    and with it the file. The `before_dl` hook strips it at once, so what stays behind is clean."""
    # A download session reads the item twice, to probe and to extract, before it fetches it.
    messages, downloads = _session(serve(fail_after=2), tmp_path, retries=0)

    assert [m for m in messages if isinstance(m, Failed)], messages
    staged = _info_files(worker_module.staging_directory(downloads, "job-1"))
    assert staged, "the info JSON was not written before the download failed"
    for path in staged:
        text = path.read_text(encoding="utf-8")
        assert COOKIE not in text and HEADER not in text, f"a secret stayed in {path.name}"


def test_without_the_hook_the_file_is_still_stripped_before_it_is_kept(
    serve: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A yt-dlp that never runs the hook, stood in for by one that does nothing: the worker's pass
    before claiming is what keeps the secrets out of the download folder then."""
    from yt_dlp.postprocessor.common import PostProcessor

    class DoesNothing(PostProcessor):  # type: ignore[misc]
        def run(self, information: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
            return [], information

    monkeypatch.setattr(ytdlp_adapter, "info_json_stripper", DoesNothing)

    messages, downloads = _session(serve(), tmp_path)

    assert [m for m in messages if isinstance(m, Succeeded)], messages
    [kept] = _info_files(downloads)
    text = kept.read_text(encoding="utf-8")
    assert COOKIE not in text and HEADER not in text
