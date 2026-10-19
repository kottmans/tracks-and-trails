"""A shaped name lands in the chosen folder, as its preview says (`T-363`, `T-248`, `T-034`).

**Real worker sessions on `127.0.0.1`**, the exception `docs/project/TESTING.md` grants the
reservation tests. At `8b0aad6` these sessions wrote outside the chosen folder: yt-dlp applied the
options field's `--trim-filenames` and `--windows-filenames` to the whole staging path it was
handed, so a trim cut into the folders above it and Windows names renamed a folder called
`Talks: 2026`. The claim's source check then failed the job, after the file and any new folder
existed, and nothing removed them. The shaping now acts where the name is rendered, and these
assert the only place anything is written is the chosen folder.

**Since `T-248` (2026-10-19) the shaping is a setting**, frozen into the
request, and the options field refuses all seven spellings: five for their controls and the Windows
pair as `app:policy`. So the sessions shape through the request's fields, and the task's criteria
are held here too: `T-034`'s containment runs after the shaping, so a name the shaping makes
reserved is renamed, two names shaped alike are numbered (`T-046`), and the file date follows
`Last-Modified`.
"""

from __future__ import annotations

import html
import threading
from collections.abc import Callable, Iterator
from email.utils import formatdate
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from typing import Any, Final

import pytest
from PySide6.QtCore import QCoreApplication

from tests.integration.test_manager import FakeRepository
from tracks_and_trails.core.models import DownloadRequest, MediaInfo
from tracks_and_trails.downloader import worker as worker_module
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.downloader.protocol import Failed, SessionKind, Succeeded

#: A minimal MP4. It does not have to play: what is measured is where it is written.
MEDIA: Final = bytes.fromhex("00000018667479706d703432") + b"\0" * 2048
TITLE: Final = "Vol. 2 of the set"
#: A date long before any test runs, so a file dated by the server cannot be dated by the clock.
LAST_MODIFIED: Final = 1445412480


def _handler(host: str, title: str) -> type[BaseHTTPRequestHandler]:
    page = (
        f'<html><head><meta property="og:video" content="http://{host}/clip.mp4">'
        f'<meta property="og:video:type" content="video/mp4">'
        f'<meta property="og:title" content="{html.escape(title)}">'
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
            self.send_header("Last-Modified", formatdate(LAST_MODIFIED, usegmt=True))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_: Any) -> None:
            """Silence the handler's stderr logging; a test is not a web server."""

    return Handler


@pytest.fixture
def serve() -> Iterator[Callable[[str], str]]:
    """A page for a title, each on its own server, all shut down afterwards."""
    servers: list[tuple[ThreadingHTTPServer, threading.Thread]] = []

    def start(title: str) -> str:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _handler("x", title))
        host = f"127.0.0.1:{server.server_address[1]}"
        server.RequestHandlerClass = _handler(host, title)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        return f"http://{host}/watch"

    yield start
    for server, thread in servers:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture
def watch_url(serve: Callable[[str], str]) -> str:
    return serve(TITLE)


def _everything_under(root: Path) -> set[Path]:
    return set(root.rglob("*"))


def _request(url: str, chosen: Path, **fields: Any) -> DownloadRequest:
    return DownloadRequest(
        url=url,
        output_directory=str(chosen),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        **fields,
    )


def _download(request: DownloadRequest) -> tuple[Any, list[Any]]:
    queue: Queue[Any] = Queue()
    worker_module.run_session(SessionKind.DOWNLOAD, "job-1", request, queue)
    messages: list[Any] = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return next((m for m in messages if isinstance(m, Succeeded | Failed)), None), messages


def _written(request: DownloadRequest) -> Path:
    outcome, messages = _download(request)
    assert isinstance(outcome, Succeeded), f"the download did not succeed: {messages}"
    return Path(outcome.output_path)


@pytest.mark.parametrize(
    ("folder", "fields"),
    [
        # A trim shorter than the folder's own path: at `8b0aad6` the file landed above it.
        pytest.param("plain", {"trim_filenames": "short"}, id="trim above the folder"),
        # A trim reaching just past the folder, into the staging folder's name.
        pytest.param("plain", {"trim_filenames": "into_staging"}, id="trim into staging"),
        # The restriction stays on the download pass, where the folder is literal text.
        pytest.param("Talks: 2026", {"restrict_filenames": True}, id="plain names"),
        pytest.param("Talks: 2026", {"trim_filenames": 12, "restrict_filenames": True}, id="both"),
    ],
)
def test_a_shaped_name_lands_in_the_chosen_folder_and_nowhere_else(
    watch_url: str, tmp_path: Path, folder: str, fields: dict[str, Any]
) -> None:
    chosen = tmp_path / "downloads" / folder
    chosen.mkdir(parents=True)
    lengths = {"short": len(str(chosen)) - 5, "into_staging": len(str(chosen)) + 12}
    fields = {key: lengths.get(value, value) for key, value in fields.items()}
    before = _everything_under(tmp_path)

    written = _written(_request(watch_url, chosen, **fields))

    assert written.parent == chosen, f"the download landed at {written}"
    new = _everything_under(tmp_path) - before
    assert new == {written}, f"something was written besides the download: {sorted(new)}"


@pytest.mark.parametrize(
    ("title", "fields", "shaped"),
    [
        pytest.param("Café & Crème: live", {"restrict_filenames": True}, True, id="plain names"),
        pytest.param("A long title for a short name", {"trim_filenames": 9}, True, id="trim"),
        # yt-dlp keeps the last two dotted parts out of its count, so this one is not shortened,
        # and the preview has to say so rather than show a trim that does not happen.
        pytest.param(TITLE, {"trim_filenames": 5}, False, id="trim beside a dot"),
        pytest.param(
            "Café & Crème: live",
            {"restrict_filenames": True, "trim_filenames": 6},
            True,
            id="both",
        ),
    ],
)
def test_the_preview_names_the_file_the_download_writes(
    app: QCoreApplication,
    serve: Callable[[str], str],
    tmp_path: Path,
    title: str,
    fields: dict[str, Any],
    shaped: bool,
) -> None:
    """`REQ-011`: the shaping reaches the preview through the same derivation as the write."""
    request = _request(serve(title), tmp_path, **fields)
    preview = DownloadManager(FakeRepository()).preview_output_path(
        request, MediaInfo(url=request.url, title=title)
    )
    assert preview.refusal is None, preview.refusal

    written = _written(request)

    assert str(written).removesuffix(".mp4") == preview.path.removesuffix(".ext")
    assert (written.name != f"{title}.mp4") is shaped


@pytest.mark.parametrize(
    ("title", "fields"),
    [
        # The trim alone makes the reserved name: `CON and more` keeps three characters.
        pytest.param("CON and more", {"trim_filenames": 3}, id="trim"),
        # The restriction alone makes it: `Con!` is a legal name until the mark is dropped.
        pytest.param("Con!", {"restrict_filenames": True}, id="plain names"),
    ],
)
def test_containment_runs_after_the_shaping(
    serve: Callable[[str], str], tmp_path: Path, title: str, fields: dict[str, Any]
) -> None:
    """**The task's first criterion.** A name the shaping makes reserved on Windows is renamed by
    `DAT-002`'s pass, on both platforms, which it could not be if that pass ran first."""
    written = _written(_request(serve(title), tmp_path, **fields))

    assert written.parent == tmp_path
    assert written.stem.upper().startswith("CON")
    assert written.stem.upper() != "CON", f"a reserved name was written: {written.name}"


@pytest.mark.parametrize(
    ("titles", "fields", "name"),
    [
        pytest.param(
            ("Concert, part one", "Concert, part two"),
            {"trim_filenames": 12},
            "Concert, par",
            id="trim",
        ),
        # A title without Latin letters keeps none of them: both become `_`.
        pytest.param(("日本語", "中文"), {"restrict_filenames": True}, "_", id="plain names"),
    ],
)
def test_two_names_shaped_alike_are_numbered(
    serve: Callable[[str], str],
    tmp_path: Path,
    titles: tuple[str, str],
    fields: dict[str, Any],
    name: str,
) -> None:
    """`T-046`'s numbering, after the shaping: the second download keeps the first's file."""
    first = _written(_request(serve(titles[0]), tmp_path, **fields))
    second = _written(_request(serve(titles[1]), tmp_path, **fields))

    assert first == tmp_path / f"{name}.mp4"
    assert second == tmp_path / f"{name} (2).mp4"


@pytest.mark.parametrize("dated", [True, False])
def test_the_file_is_dated_by_last_modified_only_when_asked(
    watch_url: str, tmp_path: Path, dated: bool
) -> None:
    """`--mtime`, as the setting: off, the file is dated when it was written, as yt-dlp's command
    line has dated it since 2025."""
    written = _written(_request(watch_url, tmp_path, use_last_modified=dated))

    stamped = written.stat().st_mtime
    assert (stamped == LAST_MODIFIED) is dated, stamped
