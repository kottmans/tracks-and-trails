"""Files the escape hatch asks to keep survive the worker's cleanup (`T-184`, `T184-R11`).

The reviewer found a real download writing a thumbnail and an info file and then **deleting both**,
while the job reported success with only the media. `_discard_staging` removes whatever
`claim_outputs` did not claim, and the claim read `requested_subtitles` and nothing else.

**Measured rather than reasoned about** (evidence: `2026-09-22-T184-retained-sidecars.md`). The
obvious fix does not work: `YoutubeDL.process_info` records `info_dict["infojson_filename"]` and
folds written thumbnails into `__files_to_move`, and neither survives into what `extract_info`
hands back. `thumbnails[*]["filepath"]` does, which is why the thumbnail is read from the result
and the other two are derived from the options.

**`http.server` on `127.0.0.1`** is the same exception `docs/project/TESTING.md` grants the
reservation tests: a real yt-dlp, a real download, no network.
"""

from __future__ import annotations

import contextlib
import io
import shutil
import subprocess
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from yt_dlp import YoutubeDL

from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.core.paths import UnsafePathError
from tracks_and_trails.downloader import ytdlp_adapter as adapter
from tracks_and_trails.downloader.worker import claim_outputs, retained_sidecars

#: A minimal MP4 and JPEG. Neither has to be playable: yt-dlp writes what it is served, and what
#: this measures is which files survive, not what is in them.
MEDIA = bytes.fromhex("00000018667479706d703432") + b"\0" * 2048
PICTURE = bytes.fromhex("ffd8ffe000104a46494600010100000100010000") + b"\0" * 512 + b"\xff\xd9"


def _handler(host: str) -> type[BaseHTTPRequestHandler]:
    page = (
        f'<html><head><meta property="og:video" content="http://{host}/clip.mp4">'
        f'<meta property="og:video:type" content="video/mp4">'
        f'<meta property="og:image" content="http://{host}/cover.jpg">'
        f'<meta property="og:title" content="Probe clip"></head><body>x</body></html>'
    ).encode()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        # `http.server`'s own name, hence the camelCase.
        def do_GET(self) -> None:
            body, kind = page, "text/html"
            if self.path.endswith(".mp4"):
                body, kind = MEDIA, "video/mp4"
            elif self.path.endswith(".jpg"):
                body, kind = PICTURE, "image/jpeg"
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_: Any) -> None:
            """Silence the handler's stderr logging; a test is not a web server."""

    return Handler


def _media_handler(body: bytes) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
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


def _download(url: str, staging: Path, text: str, argv: tuple[str, ...]) -> Any:
    """One real download into `staging`, through this application's own options."""
    request = DownloadRequest(
        url=url,
        output_directory=str(staging),
        format_selector="best",
        output_template="clip.%(ext)s",
        extra_options=text,
        extra_option_argv=argv,
    )
    options = adapter.build_options(request, str(staging / "clip.%(ext)s"))
    with (
        contextlib.redirect_stderr(io.StringIO()),
        contextlib.redirect_stdout(io.StringIO()),
        YoutubeDL(options) as ydl,
    ):
        result = ydl.extract_info(url, download=True) or {}
    return request, options, result


def test_a_thumbnail_and_an_info_file_the_user_asked_for_are_kept(
    watch_url: str, tmp_path: Path
) -> None:
    """The finding, end to end: both were written and both were then thrown away."""
    staging = tmp_path / "staging"
    staging.mkdir()
    downloads = tmp_path / "downloads"
    downloads.mkdir()

    _request, options, result = _download(
        watch_url,
        staging,
        "--write-thumbnail --write-info-json",
        ("--write-thumbnail", "--write-info-json"),
    )
    assert sorted(p.name for p in staging.iterdir()) == ["clip.info.json", "clip.jpg", "clip.mp4"]

    written, kept = claim_outputs(
        result,
        staging=staging,
        stem="clip",
        target=downloads / "clip.mp4",
        produced=staging / "clip.mp4",
        writing_subtitles=False,
        retained=retained_sidecars(options, staging, "clip"),
    )

    landed = sorted(p.name for p in downloads.iterdir())
    assert written.name == "clip.mp4"
    assert landed == ["clip.info.json", "clip.jpg", "clip.mp4"], (
        f"a file the user asked to keep did not land beside the media: {landed}"
    )
    assert {path.name for path in kept} == {"clip.info.json", "clip.jpg"}


def test_a_download_that_asked_for_nothing_extra_keeps_nothing_extra(
    watch_url: str, tmp_path: Path
) -> None:
    """The control, and the half `T184-R11` warns against: *"do not simply keep every staging
    intermediate"*. With no hatch, the media lands alone.
    """
    staging = tmp_path / "staging"
    staging.mkdir()
    downloads = tmp_path / "downloads"
    downloads.mkdir()

    _request, options, result = _download(watch_url, staging, "", ())

    written, kept = claim_outputs(
        result,
        staging=staging,
        stem="clip",
        target=downloads / "clip.mp4",
        produced=staging / "clip.mp4",
        writing_subtitles=False,
        retained=retained_sidecars(options, staging, "clip"),
    )

    assert written.name == "clip.mp4"
    assert kept == ()
    assert sorted(p.name for p in downloads.iterdir()) == ["clip.mp4"]


def test_the_family_keeps_one_name_when_the_media_name_is_taken(
    watch_url: str, tmp_path: Path
) -> None:
    """`T109-R4`'s rule, extended to the files the hatch asks for.

    A kept thumbnail that landed as `clip.jpg` beside a media file called `clip (2).mp4` would no
    longer be that download's cover. The whole family moves to one index or none of it does.
    """
    staging = tmp_path / "staging"
    staging.mkdir()
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    (downloads / "clip.mp4").write_bytes(b"taken")

    _request, options, result = _download(
        watch_url, staging, "--write-thumbnail", ("--write-thumbnail",)
    )

    written, kept = claim_outputs(
        result,
        staging=staging,
        stem="clip",
        target=downloads / "clip.mp4",
        produced=staging / "clip.mp4",
        writing_subtitles=False,
        retained=retained_sidecars(options, staging, "clip"),
    )

    assert written.name == "clip (2).mp4"
    assert [path.name for path in kept] == ["clip (2).jpg"], (
        f"the thumbnail came away from the media it belongs to: {[p.name for p in kept]}"
    )


# --- the regression the broadened claim introduced (`T184-R11`) ----------------------------------


def test_an_embedded_thumbnail_is_not_a_missing_subtitle(tmp_path: Path) -> None:
    """**A normal job, with no hatch at all**, and it failed.

    Widening the claim to thumbnails made `claim_outputs` treat every absent sidecar as a missing
    subtitle. A job writing subtitles and embedding a thumbnail then failed as `DISK`, reporting
    that its `.jpg` was a subtitle that never arrived — when the thumbnail's absence is the embed
    having worked. Only a subtitle the user named is required.
    """
    staging = tmp_path / "staging"
    staging.mkdir()
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    (staging / "clip.mp4").write_bytes(b"media")
    (staging / "clip.en.vtt").write_text("subtitle", encoding="utf-8")

    result = {
        "requested_subtitles": {"en": {"filepath": str(staging / "clip.en.vtt")}},
        # Written to be embedded, then deleted by `EmbedThumbnail`, exactly as intended.
        "thumbnails": [{"filepath": str(staging / "clip.jpg")}],
    }

    written, kept = claim_outputs(
        result,
        staging=staging,
        stem="clip",
        target=downloads / "clip.mp4",
        produced=staging / "clip.mp4",
        writing_subtitles=True,
    )

    assert written.name == "clip.mp4"
    assert [path.name for path in kept] == ["clip.en.vtt"]


def test_a_subtitle_that_never_arrived_still_fails_the_job(tmp_path: Path) -> None:
    """The control: `T109-R3`'s rule is not loosened, only narrowed to what it was about."""
    staging = tmp_path / "staging"
    staging.mkdir()
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    (staging / "clip.mp4").write_bytes(b"media")

    result = {"requested_subtitles": {"en": {"filepath": str(staging / "clip.en.vtt")}}}

    with pytest.raises(UnsafePathError, match="subtitle"):
        claim_outputs(
            result,
            staging=staging,
            stem="clip",
            target=downloads / "clip.mp4",
            produced=staging / "clip.mp4",
            writing_subtitles=True,
        )


# --- chapters, which escaped the download directory entirely (`T184-R13`) -------------------------

CHAPTER_METADATA = """;FFMETADATA1
[CHAPTER]
TIMEBASE=1/1000
START=0
END=2000
title=First
[CHAPTER]
TIMEBASE=1/1000
START=2000
END=4000
title=Second
"""


def _chaptered_media(tmp_path: Path) -> bytes:
    """A four-second clip carrying two chapters, built with the real ffmpeg.

    `--split-chapters` needs chapters to split, and a synthetic mp4 has none — which is why the
    first measurement of this finding found nothing to find.
    """
    metadata = tmp_path / "meta.txt"
    metadata.write_text(CHAPTER_METADATA, encoding="utf-8")
    built = tmp_path / "chaptered.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=4:size=64x64:rate=5",
            "-i",
            str(metadata),
            "-map_metadata",
            "1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(built),
        ],
        check=True,
        capture_output=True,
    )
    return built.read_bytes()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="the chapter split needs real ffmpeg")
def test_split_chapters_writes_inside_the_download_directory(tmp_path: Path) -> None:
    """The Critical: real ffmpeg wrote chapter files **outside** the chosen folder.

    yt-dlp renders the `chapter` template, and that is the one of eleven types it does not derive
    from the main output template — its default is relative, so the files landed against the
    process working directory. It became reachable once `T184-R10` stopped discarding the hatch's
    postprocessors. Contained here **before anything is written**, which is the only order that
    can be right: a check afterwards is a check on files already outside.

    **The postprocessor is driven directly**, as the reviewer drove it, because chapters come from
    the *extractor* and a bare mp4 has none — yt-dlp answers "Chapter information is unavailable"
    and writes nothing at all. What is under test is where the writer puts its output, so the
    writer is given chapters and a real file.
    """
    from yt_dlp.postprocessor.ffmpeg import FFmpegSplitChaptersPP

    staging = tmp_path / "staging"
    staging.mkdir()
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    (staging / "clip.mp4").write_bytes(_chaptered_media(tmp_path))

    request = DownloadRequest(
        url="https://example.invalid/watch",
        output_directory=str(staging),
        format_selector="best",
        output_template="clip.%(ext)s",
        extra_options="--split-chapters",
        extra_option_argv=("--split-chapters",),
    )
    options = adapter.build_options(request, str(staging / "clip.mp4"))
    info = {
        "title": "Clip",
        "id": "x",
        "ext": "mp4",
        "filepath": str(staging / "clip.mp4"),
        "duration": 4,
        "chapters": [
            {"start_time": 0, "end_time": 2, "title": "First"},
            {"start_time": 2, "end_time": 4, "title": "Second"},
        ],
    }

    before = set(Path.cwd().iterdir())
    with (
        contextlib.redirect_stderr(io.StringIO()),
        contextlib.redirect_stdout(io.StringIO()),
        YoutubeDL(options) as ydl,
    ):
        _files, info = FFmpegSplitChaptersPP(ydl).run(info)

    assert set(Path.cwd().iterdir()) == before, "the chapter split wrote into the working directory"
    written = sorted(path.name for path in staging.iterdir() if path.name != "clip.mp4")
    assert written == ["clip.001 First.mp4", "clip.002 Second.mp4"], (
        f"the chapter files are not where the worker put the media: {written}"
    )

    _placed, kept = claim_outputs(
        info,
        staging=staging,
        stem="clip",
        target=downloads / "clip.mp4",
        produced=staging / "clip.mp4",
        writing_subtitles=False,
        retained=retained_sidecars(options, staging, "clip"),
    )

    assert sorted(path.name for path in kept) == ["clip.001 First.mp4", "clip.002 Second.mp4"], (
        f"the chapter files were left for the cleanup to delete: {[p.name for p in kept]}"
    )
