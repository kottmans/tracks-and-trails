"""The merge container and the format check, through the real worker and yt-dlp (`T-250`).

A local HLS presentation whose video and audio are separate renditions, so `bv*+ba/b` merges, built
by ffmpeg at test time and served from `127.0.0.1` (`docs/project/TESTING.md`'s exception for the
localhost suites). The merge container decides what the merge writes, and the format check acts on
the download only: reading the URL, which the add dialog does for every paste, costs what it did.
"""

from __future__ import annotations

import json
import subprocess
import threading
from collections import Counter
from collections.abc import Callable, Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from typing import Any, Final

import pytest

from tests.capabilities import resolve_ffmpeg
from tracks_and_trails.core.models import DownloadRequest, FormatCheck
from tracks_and_trails.downloader import worker as worker_module
from tracks_and_trails.downloader.protocol import Failed, Probed, SessionKind, Succeeded

#: A master playlist naming a video-only rendition and an audio-only one, as streaming sites do.
MASTER: Final = (
    "#EXTM3U\n#EXT-X-VERSION:3\n"
    '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud",NAME="English",LANGUAGE="en",DEFAULT=YES,'
    'AUTOSELECT=YES,URI="audio.m3u8"\n'
    '#EXT-X-STREAM-INF:BANDWIDTH=300000,RESOLUTION=160x120,CODECS="avc1.42c00d,mp4a.40.2",'
    'AUDIO="aud"\n'
    "video.m3u8\n"
)


def _hls(ffmpeg: str, source: list[str], name: str, directory: Path) -> None:
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *source,
            "-f",
            "hls",
            "-hls_time",
            "1",
            "-hls_playlist_type",
            "vod",
            "-hls_segment_filename",
            str(directory / f"{name}_%d.ts"),
            str(directory / f"{name}.m3u8"),
        ],
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="module")
def presentation(tmp_path_factory: pytest.TempPathFactory) -> Path:
    ffmpeg, _ = resolve_ffmpeg()
    directory = tmp_path_factory.mktemp("separate")
    video = ["-f", "lavfi", "-i", "testsrc=size=160x120:rate=25:duration=3", "-c:v", "libx264"]
    _hls(ffmpeg, [*video, "-preset", "ultrafast", "-an"], "video", directory)
    audio = ["-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:a", "aac", "-vn"]
    _hls(ffmpeg, audio, "audio", directory)
    (directory / "master.m3u8").write_text(MASTER, encoding="utf-8")
    return directory


@pytest.fixture
def serve(presentation: Path) -> Iterator[Callable[[Counter[str]], str]]:
    servers: list[ThreadingHTTPServer] = []

    def start(asked: Counter[str]) -> str:
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *arguments: Any, **keywords: Any) -> None:
                super().__init__(*arguments, directory=str(presentation), **keywords)

            # `http.server`'s own name, hence the camelCase.
            def do_GET(self) -> None:
                asked[self.path] += 1
                super().do_GET()

            def log_message(self, *_: Any) -> None:
                """Silence the handler's stderr logging; a test is not a web server."""

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_address[1]}/master.m3u8"

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def _session(kind: SessionKind, url: str, directory: Path, **fields: Any) -> Any:
    request = DownloadRequest(
        url=url,
        output_directory=str(directory),
        format_selector="bv*+ba/b",
        output_template="%(title)s.%(ext)s",
        **fields,
    )
    queue: Queue[Any] = Queue()
    worker_module.run_session(kind, "job-1", request, queue)
    outcomes = []
    while not queue.empty():
        message = queue.get_nowait()
        if isinstance(message, Succeeded | Failed | Probed):
            outcomes.append(message)
    [outcome] = outcomes
    return outcome


def _streams(path: str) -> list[str]:
    _, ffprobe = resolve_ffmpeg()
    probed = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "stream=codec_type", "-of", "json", path],
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted(stream["codec_type"] for stream in json.loads(probed.stdout)["streams"])


@pytest.mark.parametrize(
    ("fields", "suffix"),
    [
        ({}, ".mp4"),
        ({"merge_container": "mkv"}, ".mkv"),
        ({"merge_container": "mp4"}, ".mp4"),
        # *Else mkv* at work: yt-dlp gives an HLS audio rendition no codec, so it cannot vouch
        # that the streams fit mp4, and the list falls back to mkv (measured at 2026.08.19).
        ({"merge_container": "mp4/mkv"}, ".mkv"),
        # A remux into a container the merger writes is merged straight into it.
        ({"remux_container": "mkv"}, ".mkv"),
    ],
)
def test_the_merge_writes_the_container_the_written_order_names(
    serve: Callable[[Counter[str]], str], tmp_path: Path, fields: dict[str, Any], suffix: str
) -> None:
    outcome = _session(SessionKind.DOWNLOAD, serve(Counter()), tmp_path, **fields)

    assert isinstance(outcome, Succeeded), outcome
    assert Path(outcome.output_path).suffix == suffix
    assert _streams(outcome.output_path) == ["audio", "video"], "the streams were not merged"


def test_checking_formats_acts_on_the_download_and_never_on_the_read(
    serve: Callable[[Counter[str]], str], tmp_path: Path
) -> None:
    """`T-161`'s per-entry lesson, as `ARC-010` rules it: the read keeps its cost. Checking every
    format tries a fragment of each, so the download asks for more than it would; the probe asks
    for exactly what it always did."""
    asked: dict[FormatCheck, Counter[str]] = {}
    for check in (FormatCheck.DEFAULT, FormatCheck.EVERY):
        read, fetched = Counter[str](), Counter[str]()
        probed = _session(
            SessionKind.PROBE, serve(read), tmp_path / "p" / check, check_formats=check
        )
        done = _session(SessionKind.DOWNLOAD, serve(fetched), tmp_path / check, check_formats=check)
        assert isinstance(probed, Probed) and isinstance(done, Succeeded), (probed, done)
        asked[check] = fetched
        assert sum(read.values()) == sum(
            count for path, count in read.items() if path.endswith(".m3u8")
        ), "a read fetched media"
        if check is FormatCheck.DEFAULT:
            baseline_read = read
        else:
            assert read == baseline_read, "checking formats changed what reading the URL asks for"

    def fragments(counter: Counter[str]) -> int:
        return sum(count for path, count in counter.items() if path.endswith(".ts"))

    assert fragments(asked[FormatCheck.EVERY]) > fragments(asked[FormatCheck.DEFAULT])
