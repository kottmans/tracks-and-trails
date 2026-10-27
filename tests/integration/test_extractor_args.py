"""An extractor argument reaches yt-dlp's extractor through the real worker (`T-255`).

**Real worker sessions on `127.0.0.1`**, the exception `docs/project/TESTING.md` grants the
localhost suites, against an HLS stream ffmpeg builds at test time. The generic extractor reads
`fragment_query` when it is handed a playlist, and adds it to every piece's address, so the server
can see whether the argument arrived: it does with the argument and not without it.
"""

from __future__ import annotations

import functools
import subprocess
import threading
from collections.abc import Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from typing import Any, ClassVar

import pytest

from tests.capabilities import resolve_ffmpeg
from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.downloader import worker as worker_module
from tracks_and_trails.downloader.protocol import Failed, SessionKind, Succeeded


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Two seconds of picture as one-second HLS pieces."""
    ffmpeg, _ = resolve_ffmpeg()
    directory = tmp_path_factory.mktemp("site")
    subprocess.run(
        [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=25:duration=2",
         "-c:v", "libx264", "-preset", "ultrafast", "-g", "25", "-f", "hls", "-hls_time", "1",
         "-hls_list_size", "0", str(directory / "video.m3u8")],
        check=True,
    )  # fmt: skip
    return directory


class _Paths(SimpleHTTPRequestHandler):
    """Serves the site, keeping the address of every piece asked for."""

    asked: ClassVar[list[str]]

    # `http.server`'s own name, hence the camelCase.
    def do_GET(self) -> None:
        if ".ts" in self.path:
            type(self).asked.append(self.path)
        self.path = self.path.split("?", 1)[0]
        super().do_GET()

    def log_message(self, *_: Any) -> None:
        """Silence the handler's stderr logging; a test is not a web server."""


@pytest.fixture
def served(site: Path) -> Iterator[tuple[str, type[_Paths]]]:
    handler = type("Paths", (_Paths,), {"asked": []})
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(handler, directory=str(site)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/video.m3u8", handler
    server.shutdown()
    thread.join(timeout=5)


def _download(url: str, folder: Path, **fields: Any) -> Any:
    request = DownloadRequest(
        url=url,
        output_directory=str(folder),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        **fields,
    )
    queue: Queue[Any] = Queue()
    worker_module.run_session(SessionKind.DOWNLOAD, "job-1", request, queue)
    messages: list[Any] = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return next((m for m in messages if isinstance(m, Succeeded | Failed)), messages)


@pytest.mark.parametrize("given", [True, False], ids=["given", "not-given"])
def test_an_argument_reaches_the_extractor_that_reads_it(
    served: tuple[str, type[_Paths]], tmp_path: Path, given: bool
) -> None:
    url, handler = served
    fields: dict[str, Any] = (
        {"extractor_args": (("generic", "fragment_query", ("token=t255",)),)} if given else {}
    )

    outcome = _download(url, tmp_path, **fields)

    assert isinstance(outcome, Succeeded), outcome
    assert handler.asked, "no piece was fetched"
    assert all(("token=t255" in path) is given for path in handler.asked), handler.asked
