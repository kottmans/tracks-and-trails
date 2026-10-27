"""Where connections are made from, and the wait before a file, through the real worker (`T-253`).

**Real worker sessions on `127.0.0.1`**, the exception `docs/project/TESTING.md` grants the
localhost suites. Ruled 2026-10-19 (`ARC-010` amended, second): one address choice in Settings,
yt-dlp's own wait per file, and a *Waiting* stage read from yt-dlp's `Sleeping N seconds` line,
**held to that line here**: yt-dlp says it is waiting nowhere else, so a wording it changes would
leave the row reading *Downloading* through the wait, and these are what notice.
"""

from __future__ import annotations

import functools
import subprocess
import threading
from collections.abc import Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from typing import Any

import pytest

from tests.capabilities import resolve_ffmpeg
from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.models import IPV4_ONLY, IPV6_ONLY, DownloadRequest
from tracks_and_trails.downloader import worker as worker_module
from tracks_and_trails.downloader.protocol import (
    Failed,
    Progress,
    SessionKind,
    Stage,
    Succeeded,
)


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One second of picture, served as a plain file."""
    ffmpeg, _ = resolve_ffmpeg()
    directory = tmp_path_factory.mktemp("site")
    subprocess.run(
        [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=25:duration=1",
         "-c:v", "libx264", "-preset", "ultrafast", "-movflags", "+faststart",
         str(directory / "clip.mp4")],
        check=True,
    )  # fmt: skip
    return directory


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_: Any) -> None:
        """Silence the handler's stderr logging; a test is not a web server."""


@pytest.fixture
def served(site: Path) -> Iterator[str]:
    """The site on an IPv4 loopback server, shut down afterwards."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(site)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/clip.mp4"
    server.shutdown()
    thread.join(timeout=5)


def _outcome(url: str, folder: Path, **fields: Any) -> tuple[Any, list[Any]]:
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
    return next((m for m in messages if isinstance(m, Succeeded | Failed)), None), messages


def _stages(messages: list[Any]) -> list[Stage]:
    return [message.stage for message in messages if isinstance(message, Progress)]


def test_a_wait_before_the_file_is_shown_as_waiting_until_the_download_starts(
    served: str, tmp_path: Path
) -> None:
    """**The ruling's question 3, against yt-dlp's real line.** One file, so one wait, and it is
    reported before the file's first progress, which then puts the stage back."""
    outcome, messages = _outcome(served, tmp_path, sleep_interval=0.2)

    assert isinstance(outcome, Succeeded), messages
    stages = _stages(messages)
    assert stages.count(Stage.WAITING) == 1, stages
    waited = stages.index(Stage.WAITING)
    assert Stage.DOWNLOADING_VIDEO not in stages[:waited], stages
    assert Stage.DOWNLOADING_VIDEO in stages[waited:], stages


def test_no_wait_is_shown_where_none_was_chosen(served: str, tmp_path: Path) -> None:
    outcome, messages = _outcome(served, tmp_path)

    assert isinstance(outcome, Succeeded), messages
    assert Stage.WAITING not in _stages(messages)


def test_ipv4_only_reaches_an_ipv4_server(served: str, tmp_path: Path) -> None:
    outcome, messages = _outcome(served, tmp_path, source_address=IPV4_ONLY)

    assert isinstance(outcome, Succeeded), messages


def test_ipv6_only_reaches_nothing_at_an_ipv4_server_and_fails_as_the_network(
    served: str, tmp_path: Path
) -> None:
    """**The choice reaches yt-dlp's traffic**: the server has only an IPv4 address, so a session
    held to IPv6 has nowhere to connect, on any machine, whatever its own routes. It fails as the
    network failure it is, which the queue then retries (mapped 2026-10-14, unchanged)."""
    outcome, messages = _outcome(served, tmp_path, source_address=IPV6_ONLY)

    assert isinstance(outcome, Failed), messages
    assert outcome.kind is ErrorKind.NETWORK, outcome
    assert not any(tmp_path.iterdir())
