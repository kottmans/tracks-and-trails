"""A name shaped through the options field lands in the chosen folder (`T-363`, `T-034`).

**Real worker sessions on `127.0.0.1`**, the exception `docs/project/TESTING.md` grants the
reservation tests. At `8b0aad6` these sessions wrote outside the chosen folder: yt-dlp applied the
options field's `--trim-filenames` and `--windows-filenames` to the whole staging path it was
handed, so a trim cut into the folders above it and Windows names renamed a folder called
`Talks: 2026`. The claim's source check then failed the job, after the file and any new folder
existed, and nothing removed them. The shaping now acts where the name is rendered, and these
assert the only place anything is written is the chosen folder.
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
from tracks_and_trails.downloader.extra_options import options_for
from tracks_and_trails.downloader.protocol import Failed, SessionKind, Succeeded

#: A minimal MP4. It does not have to play: what is measured is where it is written.
MEDIA: Final = bytes.fromhex("00000018667479706d703432") + b"\0" * 2048
TITLE: Final = "Vol. 2 of the set"


def _handler(host: str) -> type[BaseHTTPRequestHandler]:
    page = (
        f'<html><head><meta property="og:video" content="http://{host}/clip.mp4">'
        f'<meta property="og:video:type" content="video/mp4">'
        f'<meta property="og:title" content="{TITLE}">'
        f"</head><body>x</body></html>"
    ).encode()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        # `http.server`'s own name, hence the camelCase.
        def do_GET(self) -> None:
            body, kind = (MEDIA, "video/mp4") if self.path.endswith(".mp4") else (page, "text/html")
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_: Any) -> None:
            """Silence the handler's stderr logging; a test is not a web server."""

    return Handler


@pytest.fixture
def watch_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler("x"))
    host = f"127.0.0.1:{server.server_address[1]}"
    server.RequestHandlerClass = _handler(host)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}/watch"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _everything_under(root: Path) -> set[Path]:
    return set(root.rglob("*"))


def _download(url: str, chosen: Path, text: str) -> tuple[Any, list[Any]]:
    admission, argv = options_for(text)
    assert admission.usable, admission.refusals
    request = DownloadRequest(
        url=url,
        output_directory=str(chosen),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        extra_options=text,
        extra_option_argv=argv,
    )
    queue: Queue[Any] = Queue()
    worker_module.run_session(SessionKind.DOWNLOAD, "job-1", request, queue)
    messages: list[Any] = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return next((m for m in messages if isinstance(m, Succeeded | Failed)), None), messages


@pytest.mark.parametrize(
    ("folder", "text"),
    [
        # A trim shorter than the folder's own path: at `8b0aad6` the file landed above it.
        pytest.param("plain", "--trim-filenames {short}", id="trim above the folder"),
        # A trim reaching just past the folder, into the staging folder's name.
        pytest.param("plain", "--trim-filenames {into_staging}", id="trim into staging"),
        pytest.param("Talks: 2026", "--windows-filenames", id="windows names"),
        pytest.param("Talks: 2026", "--trim-filenames 12 --windows-filenames", id="both"),
    ],
)
def test_a_shaped_name_lands_in_the_chosen_folder_and_nowhere_else(
    watch_url: str, tmp_path: Path, folder: str, text: str
) -> None:
    chosen = tmp_path / "downloads" / folder
    chosen.mkdir(parents=True)
    text = text.format(short=len(str(chosen)) - 5, into_staging=len(str(chosen)) + 12)
    before = _everything_under(tmp_path)

    outcome, messages = _download(watch_url, chosen, text)

    assert isinstance(outcome, Succeeded), f"the download did not succeed: {messages}"
    written = Path(outcome.output_path)
    assert written.parent == chosen, f"the download landed at {written}"
    new = _everything_under(tmp_path) - before
    assert new == {written}, f"something was written besides the download: {sorted(new)}"
