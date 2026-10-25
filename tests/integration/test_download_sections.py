"""Which part is downloaded, and how many pieces at once, through the real worker (`T-252`).

**Real worker sessions on `127.0.0.1`**, the exception `docs/project/TESTING.md` grants the
localhost suites, against media ffmpeg builds at test time: a six-second clip with its index first,
so ffmpeg can cut it from a server without ranges, and the same picture as an HLS presentation of
one-second pieces. Measured on 2026-10-14, before this task: two sections typed in the options field
wrote one file, the second overwriting the first while the job succeeded; and a section aborted
whenever ffmpeg was found anywhere but `PATH`.

**`T252-R1`'s reproductions, kept** (rulings of 2026-10-25, `ARC-010` amended). The server here
cannot seek, and neither link says how long it is, which is where yt-dlp went wrong: a clip with
its index at the end, and the same clip as MKV, cut to a file with no streams, reported written;
and `*99-100` and `*-2-inf` each came back as the whole six seconds.
"""

from __future__ import annotations

import functools
import subprocess
import threading
import time
from collections.abc import Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from typing import Any, ClassVar, Final

import pytest
from yt_dlp.postprocessor import FFmpegPostProcessor

from tests.capabilities import SymlinkCapability, resolve_ffmpeg
from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.core.sections import NO_LENGTH
from tracks_and_trails.downloader import worker as worker_module
from tracks_and_trails.downloader.protocol import Failed, SessionKind, Succeeded

#: How long each piece of the stream takes to serve, so pieces fetched together overlap.
PIECE_DELAY: Final = 0.3

PAGE: Final = (
    '<html><head><meta property="og:video" content="/clip.mp4">'
    '<meta property="og:video:type" content="video/mp4">'
    '<meta property="og:title" content="Clip"></head><body>x</body></html>'
)

#: A page naming a video that is not there, so nothing can read how long it is.
GONE: Final = PAGE.replace("/clip.mp4", "/gone.mp4")


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The clip, its page, and the same picture as one-second HLS pieces."""
    ffmpeg, _ = resolve_ffmpeg()
    directory = tmp_path_factory.mktemp("site")
    picture = ["-f", "lavfi", "-i", "testsrc=size=160x120:rate=25:duration=6"]
    sound = ["-f", "lavfi", "-i", "sine=frequency=440:duration=6"]
    subprocess.run(
        [ffmpeg, "-v", "error", *picture, *sound, "-c:v", "libx264", "-preset", "ultrafast",
         "-c:a", "aac", "-shortest", "-movflags", "+faststart", str(directory / "clip.mp4")],
        check=True,
    )  # fmt: skip
    subprocess.run(
        [ffmpeg, "-v", "error", *picture, "-c:v", "libx264", "-preset", "ultrafast", "-g", "25",
         "-f", "hls", "-hls_time", "1", "-hls_list_size", "0", str(directory / "video.m3u8")],
        check=True,
    )  # fmt: skip
    # The two that cut to nothing from a server that cannot seek: ffmpeg's own MP4, index last,
    # and MKV, whose cues are at the end (measured 2026-10-25, 262 and 765 bytes, no streams).
    for name in ("late.mp4", "clip.mkv"):
        subprocess.run(
            [ffmpeg, "-v", "error", *picture, *sound, "-c:v", "libx264", "-preset", "ultrafast",
             "-c:a", "aac", "-shortest", str(directory / name)],
            check=True,
        )  # fmt: skip
    (directory / "watch").write_text(PAGE, encoding="utf-8")
    (directory / "gone").write_text(GONE, encoding="utf-8")
    return directory


class _Site(SimpleHTTPRequestHandler):
    """Serves the site, counting how many pieces of the stream are being fetched at once."""

    lock: ClassVar[threading.Lock]
    active: ClassVar[int]
    peak: ClassVar[int]

    # `http.server`'s own name, hence the camelCase.
    def do_GET(self) -> None:
        piece = self.path.endswith(".ts")
        if piece:
            with self.lock:
                type(self).active += 1
                type(self).peak = max(self.peak, self.active)
            time.sleep(PIECE_DELAY)
        try:
            super().do_GET()
        finally:
            if piece:
                with self.lock:
                    type(self).active -= 1

    def log_message(self, *_: Any) -> None:
        """Silence the handler's stderr logging; a test is not a web server."""


@pytest.fixture
def served(site: Path) -> Iterator[tuple[str, type[_Site]]]:
    """The site on its own server, with its own counter, shut down afterwards."""
    handler = type("Counted", (_Site,), {"lock": threading.Lock(), "active": 0, "peak": 0})
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(handler, directory=str(site)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}", handler
    server.shutdown()
    thread.join(timeout=5)


def _request(url: str, folder: Path, **fields: Any) -> DownloadRequest:
    return DownloadRequest(
        url=url,
        output_directory=str(folder),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        **fields,
    )


def _outcome(request: DownloadRequest, **session: Any) -> tuple[Any, list[Any]]:
    queue: Queue[Any] = Queue()
    worker_module.run_session(SessionKind.DOWNLOAD, "job-1", request, queue, **session)
    messages: list[Any] = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return next((m for m in messages if isinstance(m, Succeeded | Failed)), None), messages


def _written(request: DownloadRequest, **session: Any) -> Path:
    outcome, messages = _outcome(request, **session)
    assert isinstance(outcome, Succeeded), f"the download did not succeed: {messages}"
    return Path(outcome.output_path)


def _seconds(path: Path, ffprobe: str | None = None) -> float:
    """The file's length by ffprobe, found now unless the caller found it before hiding it."""
    ffprobe = ffprobe or resolve_ffmpeg()[1]
    shown = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(shown.stdout.strip())


def test_two_sections_write_two_files_and_the_sidecar_once(
    served: tuple[str, type[_Site]], tmp_path: Path
) -> None:
    """**The ruling's question 4**: one file per section, named by the stem and the section's
    number, the info JSON written once for the item and claimed with them, nothing else left."""
    base, _ = served

    written = _written(
        _request(
            f"{base}/watch", tmp_path, download_sections=("*0-2", "*3-5"), write_info_json=True
        )
    )

    assert written == tmp_path / "Clip (section 1).mp4"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "Clip (section 1).mp4",
        "Clip (section 2).mp4",
        "Clip.info.json",
    ], "a section overwrote another, or staging was left behind"
    for name in ("Clip (section 1).mp4", "Clip (section 2).mp4"):
        assert _seconds(tmp_path / name) == pytest.approx(2, abs=0.3), name


def test_one_section_writes_the_one_file_its_name_says(
    served: tuple[str, type[_Site]], tmp_path: Path
) -> None:
    base, _ = served

    written = _written(_request(f"{base}/watch", tmp_path, download_sections=("*1-3",)))

    assert written == tmp_path / "Clip.mp4"
    assert [path.name for path in tmp_path.iterdir()] == ["Clip.mp4"]
    assert _seconds(written) == pytest.approx(2, abs=0.3)


def test_a_section_is_cut_with_ffmpeg_found_only_through_its_location(
    served: tuple[str, type[_Site]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Windows installer's bundled ffmpeg, and a location set in Settings, are not on `PATH`.

    yt-dlp's downloader asks a context variable only its command line sets, so before this task
    every such section aborted: *"You have requested downloading the video partially, but ffmpeg
    is not installed"*. Its version cache is emptied too, as a fresh worker's is, or an earlier
    test's lookup on the full `PATH` would answer for this one.
    """
    base, _ = served
    ffmpeg, ffprobe = resolve_ffmpeg()
    monkeypatch.setenv("PATH", str(tmp_path / "no-programs-here"))
    monkeypatch.setattr(FFmpegPostProcessor, "_version_cache", {None: None})
    monkeypatch.setattr(FFmpegPostProcessor, "_features_cache", {})
    folder = tmp_path / "chosen"
    folder.mkdir()

    written = _written(
        _request(f"{base}/watch", folder, download_sections=("*0-2",)),
        ffmpeg_override=Path(ffmpeg),
    )

    assert written == folder / "Clip.mp4"
    assert _seconds(written, ffprobe) == pytest.approx(2, abs=0.3)


def test_sections_without_ffmpeg_are_refused_before_a_byte_moves(
    served: tuple[str, type[_Site]], tmp_path: Path
) -> None:
    """`REQ-024`: the worker's gate counts a section as ffmpeg's work, as the offer does."""
    base, _ = served

    outcome, messages = _outcome(
        _request(f"{base}/watch", tmp_path, download_sections=("*0-2",)),
        ffmpeg_override=tmp_path / "no-ffmpeg-here",
    )

    assert isinstance(outcome, Failed), messages
    assert outcome.kind is ErrorKind.FFMPEG_MISSING
    assert list(tmp_path.iterdir()) == []


def test_a_chapter_pattern_that_matches_nothing_ends_cancelled(
    served: tuple[str, type[_Site]], tmp_path: Path
) -> None:
    """The job's own choice skipped the item, so it ends as a filter's skip does (`UX-005`)."""
    base, _ = served

    outcome, messages = _outcome(_request(f"{base}/watch", tmp_path, download_sections=("Intro",)))

    assert isinstance(outcome, Failed), messages
    assert outcome.kind is ErrorKind.CANCELLED
    assert list(tmp_path.iterdir()) == [], "a cancelled job left something behind"


@pytest.mark.parametrize("pieces", [1, 4])
def test_the_pieces_fetched_at_once_are_the_setting_s(
    served: tuple[str, type[_Site]], tmp_path: Path, pieces: int
) -> None:
    """**Measured, as `T-252`'s criterion asks**: one download fetches exactly this many pieces of
    a stream at once. Each download is its own process, so the pool multiplies it (`ARC-007`);
    the 2026-10-14 mapping measured three jobs at 4 holding 12 requests open."""
    base, handler = served

    written = _written(
        _request(
            f"{base}/video.m3u8",
            tmp_path,
            concurrent_fragments=None if pieces == 1 else pieces,
        )
    )

    assert written.exists()
    assert handler.peak == pieces


# --- T252-R1: each section checked before it is cut and after -------------------------------


@pytest.mark.parametrize("name", ["late.mp4", "clip.mkv"])
def test_a_cut_with_no_picture_or_sound_fails_and_keeps_its_staging(
    served: tuple[str, type[_Site]], tmp_path: Path, name: str
) -> None:
    """**Ruling 2**: from a server that cannot seek, ffmpeg cut these to a file with no streams
    and yt-dlp reported it written, so the job claimed 262 bytes as the part. Now every section is
    read before it is claimed: an ffmpeg failure, the reason in words, nothing claimed, and staging
    kept as on any failed attempt."""
    base, _ = served

    outcome, messages = _outcome(_request(f"{base}/{name}", tmp_path, download_sections=("*1-3",)))

    assert isinstance(outcome, Failed), messages
    assert outcome.kind is ErrorKind.FFMPEG_ERROR
    assert "came back with no picture or sound" in outcome.message
    staging = worker_module.staging_directory(tmp_path, "job-1")
    assert staging.is_dir(), "a failed attempt discarded its staging"
    assert [
        path for path in tmp_path.rglob("*") if path.is_file() and staging not in path.parents
    ] == []


@pytest.mark.parametrize(
    ("sections", "named"),
    [
        (("*99-100",), "*99-100 starts"),
        (("*6-7",), "*6-7 starts"),
        (("*0-2", "*99-100"), "*99-100 starts"),
        (("*99-100", "*120-130"), "*99-100 and *120-130 start"),
    ],
    ids=["past", "at the end", "one of two", "both"],
)
def test_a_section_past_the_end_cancels_the_item_before_it_downloads(
    served: tuple[str, type[_Site]], tmp_path: Path, sections: tuple[str, ...], named: str
) -> None:
    """**Rulings 1 and 3**: the page gives no length, so it is read from the link, six seconds, and
    a range starting at or after it cancels the item, naming each such section and no other. Before
    this, `*99-100` came back as the whole six seconds, reported as the part."""
    base, _ = served

    outcome, messages = _outcome(_request(f"{base}/watch", tmp_path, download_sections=sections))

    assert isinstance(outcome, Failed), messages
    assert outcome.kind is ErrorKind.CANCELLED
    assert f"Nothing was downloaded: {named} after the end of this item" in outcome.message
    assert "6 seconds long" in outcome.message
    assert "*0-2" not in outcome.message, "a section inside the item was named"
    assert list(tmp_path.iterdir()) == [], "a cancelled job left something behind"


def test_a_range_from_the_end_is_cut_by_the_length_read_from_the_link(
    served: tuple[str, type[_Site]], tmp_path: Path
) -> None:
    """yt-dlp places a range counted from the end by the item's length, and this page gives none,
    so `*-2-inf`, the last two seconds, came back as all six. The length read from the link is
    handed to yt-dlp."""
    base, _ = served

    written = _written(_request(f"{base}/watch", tmp_path, download_sections=("*-2-inf",)))

    assert _seconds(written) == pytest.approx(2, abs=0.3)


def test_an_item_whose_length_cannot_be_read_is_cancelled_with_the_reason(
    served: tuple[str, type[_Site]], tmp_path: Path
) -> None:
    """**Ruling 3**: with no length from the site or the link, a range cannot be placed, so the
    item is cancelled rather than cut."""
    base, _ = served

    outcome, messages = _outcome(_request(f"{base}/gone", tmp_path, download_sections=("*1-3",)))

    assert isinstance(outcome, Failed), messages
    assert outcome.kind is ErrorKind.CANCELLED
    assert outcome.message == NO_LENGTH
    assert list(tmp_path.iterdir()) == []


def test_sections_without_ffprobe_beside_ffmpeg_are_refused_before_a_byte_moves(
    served: tuple[str, type[_Site]], tmp_path: Path, symlinks: SymlinkCapability
) -> None:
    """Every section is read with the ffprobe in ffmpeg's own directory, where yt-dlp looks for
    it, so an ffmpeg with none beside it cannot cut one."""
    base, _ = served
    alone = tmp_path / "ffmpeg-alone"
    alone.mkdir()
    symlinks.create(alone / "ffmpeg", Path(resolve_ffmpeg()[0]))
    folder = tmp_path / "chosen"
    folder.mkdir()

    outcome, messages = _outcome(
        _request(f"{base}/watch", folder, download_sections=("*0-2",)),
        ffmpeg_override=alone / "ffmpeg",
    )

    assert isinstance(outcome, Failed), messages
    assert outcome.kind is ErrorKind.FFMPEG_MISSING
    assert outcome.message == worker_module.NO_FFPROBE
    assert list(folder.iterdir()) == []
