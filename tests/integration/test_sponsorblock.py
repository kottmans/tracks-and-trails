"""SponsorBlock's marks and cuts, asserted on the file the chain writes (`T-254`).

**The chain is the one `build_options` builds, run on a clip ffmpeg makes here**, with the segments
SponsorBlock's lookup would have found placed where yt-dlp's `SponsorBlockPP` places them: the
lookup acts on YouTube alone, so no local page can make one, and `tests/unit/test_sponsorblock.py`
holds the lookup itself. Mapped 2026-10-14 through the options field: *Embed metadata* beside
`--sponsorblock-mark` wrote a file with no metadata, because the option appended a second metadata
step that rewrote the file from its chapters alone; and two chapter passes, the options field's
`--remove-chapters` beside SponsorBlock's, could leave a stale SponsorBlock chapter.
"""

from __future__ import annotations

import contextlib
import functools
import io
import json
import shutil
import subprocess
import threading
from collections.abc import Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from typing import Any, Final

import pytest
from yt_dlp import YoutubeDL
from yt_dlp.postprocessor import get_postprocessor

from tests.capabilities import resolve_ffmpeg
from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.downloader import worker as worker_module
from tracks_and_trails.downloader import ytdlp_adapter as adapter
from tracks_and_trails.downloader.protocol import Failed, SessionKind, Succeeded

#: A sponsor segment from one second to two, as `SponsorBlockPP` hands it on.
SPONSOR: Final = {
    "start_time": 1.0,
    "end_time": 2.0,
    "category": "sponsor",
    "title": "Sponsor",
    "type": "skip",
    "_categories": [("sponsor", 1.0, 2.0, "Sponsor")],
}


@pytest.fixture
def clip(tmp_path: Path) -> Path:
    """Six seconds, inside a staging folder of its own.

    **No chapters in the file**, as a downloaded video has none: a site's chapters arrive in the
    item's information, which `_run_chain` carries, and ffmpeg keeps chapters already in a file
    ahead of the ones the metadata step writes.
    """
    ffmpeg, _ = resolve_ffmpeg()
    staging = tmp_path / "staging"
    staging.mkdir()
    built = staging / "Clip.mp4"
    subprocess.run(
        [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=6:size=64x64:rate=10",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", str(built)],
        check=True,
    )  # fmt: skip
    return built


def _probed(path: Path) -> dict[str, Any]:
    _, ffprobe = resolve_ffmpeg()
    shown = subprocess.run(
        [ffprobe, "-v", "error", "-show_chapters", "-show_format", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    result: dict[str, Any] = json.loads(shown.stdout)
    return result


def _chapter_titles(path: Path) -> list[str]:
    return [c.get("tags", {}).get("title", "") for c in _probed(path).get("chapters", [])]


def _title_tag(path: Path) -> str | None:
    tags = _probed(path).get("format", {}).get("tags", {})
    return next((value for key, value in tags.items() if key.lower() == "title"), None)


def _seconds(path: Path) -> float:
    return float(_probed(path)["format"]["duration"])


def _run_chain(clip: Path, specs: list[dict[str, Any]]) -> Path:
    """Each processor of `specs`, in order, on the clip, as yt-dlp runs its post-processors."""
    info: dict[str, Any] = {
        "id": "x",
        "title": "Clip",
        "ext": "mp4",
        "filepath": str(clip),
        "duration": 6,
        "webpage_url": "https://www.youtube.com/watch?v=x",
        "chapters": [
            {"start_time": 0, "end_time": 3, "title": "First"},
            {"start_time": 3, "end_time": 6, "title": "Second"},
        ],
        "sponsorblock_chapters": [dict(SPONSOR)],
    }
    ffmpeg, _ = resolve_ffmpeg()
    with (
        contextlib.redirect_stderr(io.StringIO()),
        contextlib.redirect_stdout(io.StringIO()),
        YoutubeDL({"quiet": True, "ffmpeg_location": shutil.which(ffmpeg) or ffmpeg}) as ydl,
    ):
        for spec in specs:
            processor = get_postprocessor(str(spec["key"]))
            arguments = {k: v for k, v in spec.items() if k not in {"key", "when"}}
            _files, info = processor(ydl, **arguments).run(info)
    return Path(str(info["filepath"]))


def _chain(clip: Path, **fields: Any) -> list[dict[str, Any]]:
    request = DownloadRequest(
        url="https://www.youtube.com/watch?v=x",
        output_directory=str(clip.parent),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        **fields,
    )
    specs: list[dict[str, Any]] = adapter.build_options(request, str(clip))["postprocessors"]
    return specs


def test_a_mark_is_written_as_a_chapter_and_the_metadata_survives(clip: Path) -> None:
    """**The first mapped defect, closed** (ruling 2): one metadata step carries both."""
    specs = _chain(clip, sponsorblock_mark=("sponsor",), embed_chapters=True, embed_metadata=True)

    assert [spec["key"] for spec in specs].count("FFmpegMetadata") == 1, specs
    written = _run_chain(clip, specs)

    assert _title_tag(written) == "Clip"
    assert any("Sponsor" in title for title in _chapter_titles(written)), _chapter_titles(written)
    assert _seconds(written) == pytest.approx(6, abs=0.3)


def test_a_second_metadata_step_for_the_marks_loses_the_tags_the_first_wrote(clip: Path) -> None:
    """**The instrument, shown a positive**: the options field's route, a chapters-only metadata
    step after the application's own, as yt-dlp's `--sponsorblock-mark` appended it."""
    specs = _chain(clip, sponsorblock_mark=("sponsor",), embed_chapters=True, embed_metadata=True)
    second = {"key": "FFmpegMetadata", "add_chapters": True, "add_metadata": False}

    written = _run_chain(clip, [*specs, second])

    assert _title_tag(written) is None


def test_a_cut_is_removed_from_the_file(clip: Path) -> None:
    written = _run_chain(clip, _chain(clip, sponsorblock_remove=("sponsor",)))

    assert _seconds(written) == pytest.approx(5, abs=0.3)


def test_chapters_removed_through_the_options_field_join_the_one_pass(clip: Path) -> None:
    """**One chapter pass for both**, as yt-dlp's command line builds it (mapped 2026-10-14):
    the options field's `--remove-chapters` beside SponsorBlock's marks and cuts."""
    specs = _chain(
        clip,
        sponsorblock_mark=("intro",),
        sponsorblock_remove=("sponsor",),
        embed_chapters=True,
        extra_options="--remove-chapters Second",
        extra_option_argv=("--remove-chapters", "Second"),
    )

    assert [spec["key"] for spec in specs].count("ModifyChapters") == 1, specs
    written = _run_chain(clip, specs)

    assert _seconds(written) == pytest.approx(2, abs=0.3)
    assert _chapter_titles(written) == ["First"], _chapter_titles(written)


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_: Any) -> None:
        """Silence the handler's stderr logging; a test is not a web server."""


@pytest.fixture
def served(clip: Path) -> Iterator[str]:
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(_Quiet, directory=str(clip.parent))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/{clip.name}"
    server.shutdown()
    thread.join(timeout=5)


def test_a_real_session_with_sponsorblock_on_downloads_an_item_it_cannot_ask_about(
    served: str, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """**The worker's lookup, on a real session**: SponsorBlock knows YouTube alone, so yt-dlp's
    step says so and asks nothing, and the download finishes as it would have without it."""
    folder = tmp_path / "out"
    folder.mkdir()
    request = DownloadRequest(
        url=served,
        output_directory=str(folder),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        sponsorblock_mark=("intro",),
        sponsorblock_remove=("sponsor",),
        embed_chapters=True,
    )
    queue: Queue[Any] = Queue()

    with caplog.at_level("INFO"):
        worker_module.run_session(SessionKind.DOWNLOAD, "job-1", request, queue)

    messages = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    outcome = next((m for m in messages if isinstance(m, Succeeded | Failed)), None)
    assert isinstance(outcome, Succeeded), messages
    assert _seconds(Path(outcome.output_path)) == pytest.approx(6, abs=0.3)
    said = [record.getMessage() for record in caplog.records]
    assert any("SponsorBlock is not supported for Generic" in line for line in said), said
