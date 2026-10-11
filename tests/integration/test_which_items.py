"""How a job ends when its own size and date filters rule its item out (`T-247`).

Each case runs the real worker session and the real yt-dlp against a server on `127.0.0.1`, the
exception `docs/project/TESTING.md` grants the other localhost suites, and asserts the outcome the
parent receives, because that is what a row shows.

`ARC-010`, amended 2026-10-11: the filters act per job, on the download only, and an item they skip
ends *Cancelled* with yt-dlp's reason, as `UX-005`'s 2026-09-27 amendment rules for the hatch. The
date case is real: yt-dlp's generic extractor dates a direct link by its `Last-Modified` header.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from typing import Any, Final

import pytest

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.downloader import worker as worker_module
from tracks_and_trails.downloader.protocol import Failed, Probed, SessionKind, Succeeded

#: Not media, and does not need to be: nothing converts it. Its length is what the sizes test.
BODY: Final = b"\0" * 4000

#: When the server says the clip was last modified, which yt-dlp reads as its upload date.
MODIFIED: Final = "Wed, 01 Jan 2025 00:00:00 GMT"


def _handler() -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        # `http.server`'s own name, hence the camelCase.
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(BODY)))
            self.send_header("Last-Modified", MODIFIED)
            self.end_headers()
            self.wfile.write(BODY)

        def log_message(self, *_: Any) -> None:
            """Silence the handler's stderr logging; a test is not a web server."""

    return Handler


@pytest.fixture
def clip() -> Iterator[str]:
    """A direct link to a 4000-byte clip, last modified on 2025-01-01."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/clip.mp4"
    server.shutdown()
    server.server_close()


def _session(kind: SessionKind, request: DownloadRequest) -> list[Any]:
    """Run one real session and return everything it sent the parent."""
    queue: Queue[Any] = Queue()
    worker_module.run_session(kind, "job-1", request, queue)
    messages: list[Any] = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return messages


def _request(url: str, downloads: Path, **filters: Any) -> DownloadRequest:
    return DownloadRequest(
        url=url,
        output_directory=str(downloads),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        **filters,
    )


@pytest.mark.parametrize(
    ("filters", "said"),
    [
        ({"max_filesize": 1024}, "larger than max-filesize"),
        ({"min_filesize": 10_000}, "smaller than min-filesize"),
        ({"uploaded_after": "20250601"}, "upload date is not in range"),
        ({"uploaded_before": "20241231"}, "upload date is not in range"),
    ],
    ids=["too large", "too small", "too old", "too new"],
)
def test_an_item_a_filter_rules_out_ends_cancelled_with_yt_dlp_s_reason(
    clip: str, tmp_path: Path, filters: dict[str, Any], said: str
) -> None:
    """Not a failure, so neither offered a retry nor shown as a disk fault, and nothing kept."""
    downloads = tmp_path / "downloads"
    downloads.mkdir()

    messages = _session(SessionKind.DOWNLOAD, _request(clip, downloads, **filters))

    assert not [m for m in messages if isinstance(m, Succeeded)]
    failed = next(m for m in messages if isinstance(m, Failed))
    assert failed.kind is ErrorKind.CANCELLED, f"{failed.kind}: {failed.message}"
    assert said in failed.message, f"yt-dlp's reason was not the one shown: {failed.message!r}"
    assert not list(downloads.iterdir()), "the skipped attempt left something behind"


def test_an_item_every_filter_passes_downloads(clip: str, tmp_path: Path) -> None:
    """The control: the same item inside every bound is downloaded whole."""
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    request = _request(
        clip,
        downloads,
        min_filesize=1000,
        max_filesize=10_000,
        uploaded_after="20241231",
        uploaded_before="20250101",
    )

    messages = _session(SessionKind.DOWNLOAD, request)

    succeeded = next((m for m in messages if isinstance(m, Succeeded)), None)
    assert succeeded is not None, [m for m in messages if isinstance(m, Failed)]
    assert Path(succeeded.output_path).read_bytes() == BODY


def test_a_window_whose_days_have_crossed_is_cancelled_with_its_reason(
    clip: str, tmp_path: Path
) -> None:
    """yt-dlp refuses such a `DateRange`; the worker ends the job as a skip before asking it."""
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    request = _request(clip, downloads, uploaded_after="20260101", uploaded_before="20250101")

    messages = _session(SessionKind.DOWNLOAD, request)

    failed = next(m for m in messages if isinstance(m, Failed))
    assert failed.kind is ErrorKind.CANCELLED, f"{failed.kind}: {failed.message}"
    assert failed.message == worker_module.EMPTY_WINDOW.format(after="20260101", before="20250101")
    assert not list(downloads.iterdir())


def test_a_filter_does_not_hide_the_item_from_its_probe(clip: str, tmp_path: Path) -> None:
    """The probe describes the item whatever it is, or the item being chosen would disappear."""
    request = _request(clip, tmp_path, max_filesize=1, uploaded_before="20000101")

    messages = _session(SessionKind.PROBE, request)

    assert [m for m in messages if isinstance(m, Probed)], messages
