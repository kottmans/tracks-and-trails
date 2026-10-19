"""A download retries, and never finishes with a piece missing (`T-364`).

Measured at `8b0aad6` with the worker's `run_session` against a local 12-second HLS stream: one 503
on one fragment ended the job `Succeeded` with 250 of 300 video frames, and a 403 did the same with
retries set to 3. yt-dlp the library reads an absent `retries` or `fragment_retries` as zero, where
its command line sends ten, and skips a fragment it could not fetch. The stream here is built by
ffmpeg at test time and served from `127.0.0.1`, the exception `docs/project/TESTING.md` grants
the other localhost suites; a scripted server fails chosen requests, and ffprobe counts the frames
of the file that is kept.
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
from tests.integration.test_end_to_end import build_media
from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.downloader import worker as worker_module
from tracks_and_trails.downloader.extra_options import options_for
from tracks_and_trails.downloader.protocol import Failed, SessionKind, Succeeded

#: Twelve one-second fragments at 25 frames a second.
FRAMES: Final = 300
FAILING: Final = "/v0_3.ts"
FOREVER: Final = 10**9


@pytest.fixture(scope="module")
def stream(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The served directory: a 12-second HLS stream in one-second fragments, and a plain clip."""
    ffmpeg, _ = resolve_ffmpeg()
    directory = tmp_path_factory.mktemp("stream")
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size=160x120:rate=25:duration={FRAMES // 25}",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-g",
            "25",
            "-f",
            "hls",
            "-hls_time",
            "1",
            "-hls_playlist_type",
            "vod",
            "-hls_segment_filename",
            str(directory / "v0_%d.ts"),
            str(directory / "v0.m3u8"),
        ],
        check=True,
        capture_output=True,
    )
    build_media(ffmpeg, directory / "clip.mp4")
    return directory


class Script:
    """Which requests fail, how, and every path that was asked for."""

    def __init__(self) -> None:
        self.failing: dict[str, tuple[int, int, int]] = {}
        self.asked: Counter[str] = Counter()

    def fail(self, path: str, status: int, times: int = FOREVER, after: int = 0) -> None:
        """Answer `status` to `path` `times` times, once the first `after` requests succeeded."""
        self.failing[path] = (status, times, after)

    def heal(self) -> None:
        self.failing.clear()


@pytest.fixture
def serve(stream: Path) -> Iterator[Callable[[Script], str]]:
    servers: list[ThreadingHTTPServer] = []

    def start(script: Script) -> str:
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *arguments: Any, **keywords: Any) -> None:
                super().__init__(*arguments, directory=str(stream), **keywords)

            # `http.server`'s own name, hence the camelCase.
            def do_GET(self) -> None:
                script.asked[self.path] += 1
                rule = script.failing.get(self.path)
                if rule is not None:
                    status, times, after = rule
                    if after < script.asked[self.path] <= after + times:
                        self.send_response(status)
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                super().do_GET()

            def log_message(self, *_: Any) -> None:
                """Silence the handler's stderr logging; a test is not a web server."""

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_address[1]}"

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def _download(url: str, directory: Path, options: str = "") -> Succeeded | Failed:
    """One real download session of `url` into `directory`, as job `job-1`."""
    admission, argv = options_for(options)
    assert admission.usable, admission.refusals
    request = DownloadRequest(
        url=url,
        output_directory=str(directory),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        extra_options=options,
        extra_option_argv=argv,
    )
    queue: Queue[Any] = Queue()
    worker_module.run_session(SessionKind.DOWNLOAD, "job-1", request, queue)
    outcomes = []
    while not queue.empty():
        message = queue.get_nowait()
        if isinstance(message, Succeeded | Failed):
            outcomes.append(message)
    [outcome] = outcomes
    return outcome


def _frames(path: str) -> int:
    _, ffprobe = resolve_ffmpeg()
    probed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "json",
            path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return int(json.loads(probed.stdout)["streams"][0]["nb_read_frames"])


@pytest.mark.parametrize("status", [503, 403])
def test_one_failure_on_a_fragment_is_retried_and_every_frame_arrives(
    serve: Callable[[Script], str], tmp_path: Path, status: int
) -> None:
    """The measurement of 2026-10-14: both ended *Done* with a fragment's frames missing."""
    script = Script()
    script.fail(FAILING, status, times=1)

    outcome = _download(serve(script) + "/v0.m3u8", tmp_path)

    assert isinstance(outcome, Succeeded), outcome
    assert _frames(outcome.output_path) == FRAMES
    assert script.asked[FAILING] == 2, "the fragment was not asked for again"


def test_a_fragment_that_never_arrives_fails_and_the_retry_resumes_it(
    serve: Callable[[Script], str], tmp_path: Path
) -> None:
    """No *Done* with a piece missing: the attempt fails as a network failure, which the queue
    retries by itself, and its staging is kept. The next attempt continues where it stopped."""
    script = Script()
    script.fail(FAILING, 503)
    url = serve(script) + "/v0.m3u8"

    failed = _download(url, tmp_path)

    assert isinstance(failed, Failed), failed
    assert failed.kind is ErrorKind.NETWORK, failed
    assert "503" in failed.message, "yt-dlp's own words did not reach the row"
    staged = worker_module.staging_directory(tmp_path, "job-1")
    assert any(path.suffix == ".part" for path in staged.iterdir()), "nothing kept to resume"
    before = Counter({path: script.asked[path] for path in ("/v0_0.ts", "/v0_1.ts", "/v0_2.ts")})

    script.heal()
    resumed = _download(url, tmp_path)

    assert isinstance(resumed, Succeeded), resumed
    assert _frames(resumed.output_path) == FRAMES
    assert all(script.asked[path] == count for path, count in before.items()), (
        "the retry fetched again the fragments the first attempt already had"
    )


def test_a_fragment_that_is_gone_fails_as_a_failure_the_queue_does_not_repeat(
    serve: Callable[[Script], str], tmp_path: Path
) -> None:
    """A 404 after its retries is not a network failure, so nothing retries it on a timer."""
    script = Script()
    script.fail(FAILING, 404)

    outcome = _download(serve(script) + "/v0.m3u8", tmp_path)

    assert isinstance(outcome, Failed), outcome
    assert outcome.kind is ErrorKind.EXTRACTOR_ERROR, outcome
    assert "404" in outcome.message


def test_the_user_s_skip_still_skips(serve: Callable[[Script], str], tmp_path: Path) -> None:
    """`--skip-unavailable-fragments` in the options field is the user's explicit opt-in to a
    partial file, and wins over the application's refusal of one (`ARC-010`, 2026-10-15, third)."""
    script = Script()
    script.fail(FAILING, 503)

    outcome = _download(serve(script) + "/v0.m3u8", tmp_path, "--skip-unavailable-fragments")

    assert isinstance(outcome, Succeeded), outcome
    assert _frames(outcome.output_path) < FRAMES


def test_a_transfer_retries_a_server_failure(
    serve: Callable[[Script], str], tmp_path: Path
) -> None:
    """The progressive half: one 503 on the transfer failed the job as `EXTRACTOR_ERROR`, because
    no count was sent and the library read that as no retries."""
    script = Script()
    # A download session reads the item twice, to probe and to extract, before it fetches it.
    script.fail("/clip.mp4", 503, times=1, after=2)

    outcome = _download(serve(script) + "/clip.mp4", tmp_path)

    assert isinstance(outcome, Succeeded), outcome


def test_a_transfer_the_server_keeps_failing_is_a_network_failure(
    serve: Callable[[Script], str], tmp_path: Path
) -> None:
    script = Script()
    script.fail("/clip.mp4", 503, after=2)

    outcome = _download(serve(script) + "/clip.mp4", tmp_path)

    assert isinstance(outcome, Failed), outcome
    assert outcome.kind is ErrorKind.NETWORK, outcome
