"""The proof Phase 1 exists for (`T-037`).

Two of the phase's exit criteria had no owner until this: *a real URL downloads to disk with
accurate live progress and correct final bytes*, and *job state survives an application restart
mid-download*. `T-012` proved probing, `T-019` proved cancellation and crashes, `T-036` proved the
graph is assembled — nobody had proved a download **completing**.

## What is real here, and what is not

Everything except the site. `compose()` builds the application, the worker is a real spawned
process running **real yt-dlp**, the extractor is yt-dlp's generic one, the HTTP downloader is
yt-dlp's own, and the file lands on a real filesystem. What is faked is the server: a local
`http.server` serving `video/mp4` from `127.0.0.1`, which is the exception `ai/TESTING.md` §6
records for exactly this — the acceptance criterion is about bytes actually moving, and a faked
adapter cannot move any.

Nothing leaves the machine, so these are not `-m network` tests. The one test that does reach a
real site lives in `tests/network/` and is excluded by default.

## The restart is a kill, not a close

`SIGKILL` to a separate interpreter, mid-download. A clean shutdown would prove that orderly
teardown works, which `T-036` already covers; `NFR-003` is about the other case, and recovery
that has only ever been driven by a graceful exit is recovery nobody has tested.
"""

import contextlib
import functools
import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Final

import psutil
import pytest
from PySide6.QtWidgets import QApplication

from tracks_and_trails import app as application
from tracks_and_trails.core.errors import ErrorKind, is_retryable
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import DownloadRequest, Job
from tracks_and_trails.core.presets import BUILT_IN_PRESETS
from tracks_and_trails.downloader.protocol import Progress, Stage
from tracks_and_trails.persistence import db
from tracks_and_trails.persistence.repositories import JobRepository

REPO_ROOT = Path(__file__).parents[2]


# **Split at module level, not branched inside a function** — `downloader/process_tree.py`'s own
# idiom, and for its reason: each half is then type-checked by the run that owns it, `mypy` for
# POSIX and `mypy --platform win32` for Windows. A branch *inside* a function leaves the other
# side unreachable to whichever run is looking, which is how the first version of this file
# reached `os.killpg` on a platform that has never had it.
#
# `mypy --platform win32` is what caught that: `os.killpg`, `os.getpgid` and `signal.SIGKILL` are
# all POSIX-only, and this test would have failed on the `windows-latest` job with an
# `AttributeError` rather than a finding (`AGENTS.md` §8 — a host-only check is not the whole
# gate).

if sys.platform == "win32":

    def isolate_the_application() -> dict[str, Any]:
        """`Popen` arguments that put the application in its own process group."""
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}

    def kill_the_application(process: subprocess.Popen[str], doomed: list[psutil.Process]) -> None:
        """Kill every captured process, without letting any of it unwind.

        `T066-R1`. This was `process.kill()` alone, on the reasoning that `ARC-002`'s worker runs
        a parent watchdog and `T-019`'s Job object reaps the worker's descendants. Measured on
        Windows 10, the reasoning does not survive contact:

        | Process | After `process.kill()` |
        |---|---|
        | the pid `Popen` returned | dead |
        | its child | dead |
        | **its grandchild** | **alive** |

        The kill reaches exactly one level. Under a virtualenv that is worse than it sounds,
        because the venv's `python.exe` is a launcher: the pid `Popen` returns is the launcher, its
        child is the application, and **the worker is the grandchild that survives**. So a test
        whose whole subject is an application dying mid-download was leaving the download running
        — the orphan `T-019` exists to prevent, created by the test that asserts recovery from it.

        The POSIX branch has always killed the whole process group. This is that, for a platform
        with no process groups.

        Still a crash, not a shutdown — `Process.kill` is `TerminateProcess`, so nothing unwinds
        and no handler runs, which is what the test needs.

        **The set is captured by the caller, not derived here** (`T072-R1`). An earlier correction
        walked the tree from `process.pid` and asserted `len(doomed) > 1`, which reads like a
        check and is not one: under the venv shape the launcher and the interpreter already make
        that two, so the *worker* could be missing and the assertion still passed. A deterministic
        mutation reducing the walk to direct children proved it — `len(doomed) == 2`, the helper
        returned successfully, and the omitted worker went on downloading. Identity has to come
        from the application's own reported pid, which is why `capture_the_doomed_tree` does the
        walking and this function only kills what it was handed.
        """
        refused: list[str] = []
        for victim in doomed:
            try:
                victim.kill()
            except psutil.NoSuchProcess:
                continue  # raced with the tree tearing itself down; that is a kill, not a miss
            except psutil.Error as error:
                refused.append(f"pid {victim.pid}: {error!r}")

        _, alive = psutil.wait_procs(doomed, timeout=30)
        assert not alive, (
            f"{len(alive)} process(es) survived the kill and still own the database this test is "
            f"about to reopen: {sorted(survivor.pid for survivor in alive)}. "
            f"Kills refused: {refused or 'none'}."
        )

else:

    def isolate_the_application() -> dict[str, Any]:
        """`Popen` arguments that put the application in its own process group."""
        return {"start_new_session": True}

    def kill_the_application(process: subprocess.Popen[str], doomed: list[psutil.Process]) -> None:
        """Kill the application **and the worker it spawned**, without letting either unwind.

        The whole group at once: killing only the parent would leave the worker downloading into
        a database nobody owns (`T-019`).

        `doomed` is then checked rather than used to kill, because the signal already reached the
        group. **Our own direct child is deliberately excluded from the wait**: it is a zombie
        until someone reaps it, and reaping it here would steal the exit status the caller's
        `process.wait()` is about to collect. That exact mistake is recorded above — the first
        version of `still_running` hit it from the other direction.
        """
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)

        others = [victim for victim in doomed if victim.pid != process.pid]
        _, alive = psutil.wait_procs(others, timeout=30)
        assert not alive, (
            f"{len(alive)} process(es) survived SIGKILL to the group and still own the database "
            f"this test is about to reopen: {sorted(survivor.pid for survivor in alive)}."
        )


#: `multiprocessing`'s bookkeeping child, which is not a worker and must never be counted as one.
#: `tests/integration/test_manager.py` excludes it from `worker_processes()` for the same reason,
#: and names the same string.
RESOURCE_TRACKER_MARKER: Final = "multiprocessing.resource_tracker"


def the_workers_that_must_die(application_pid: int) -> list[psutil.Process]:
    """The **worker** set, obtained independently of whatever will do the killing.

    `T072-R1`, third round. Two faults preceded this, and both were assertions that looked like
    checks:

    1. The first asserted against `doomed` — the same list the kill was handed — so a fault that
       dropped the worker from that list dropped it from the assertion too.
    2. The second separated the lists but returned *every descendant*, which on `multiprocessing`
       means the resource tracker as well as the worker. The tracker outlives the worker, so the
       positive control failed on the tracker while calling it a worker, and a reviewer's mutation
       that killed the application and tracker but deliberately spared the real worker **passed in
       1.38 s**.

    So the exclusion below is the whole point of this function rather than a detail: the tracker is
    infrastructure, it is long-lived, and counting it means the check can be satisfied by something
    that was never doing any work. Everything else is kept — an `ffmpeg` grandchild is not a worker
    either, but it *is* a process that would go on writing to the disk, which is the property these
    tests are actually about (`T-019`).
    """
    application = psutil.Process(application_pid)
    workers: list[psutil.Process] = []
    for child in application.children(recursive=True):
        try:
            if RESOURCE_TRACKER_MARKER in " ".join(child.cmdline()):
                continue
            if child.status() == psutil.STATUS_ZOMBIE:
                continue
            workers.append(child)
        except psutil.NoSuchProcess, psutil.AccessDenied:  # it exited mid-question
            continue

    assert workers, (
        f"the application (pid {application_pid}) has no worker while its job says RUNNING — "
        f"only {[child.pid for child in application.children(recursive=True)]}, which after "
        f"excluding the resource tracker leaves nothing. The worker is what makes this kill "
        f"meaningful; without one, killing proves nothing about orphans."
    )
    return workers


def capture_the_doomed_tree(
    process: subprocess.Popen[str], application_pid: int
) -> list[psutil.Process]:
    """Every process the kill is asked to reach, captured while the tree is still intact.

    Built from the application's own reported pid rather than inferred from a count under the
    launcher, and built *now*: once the parent is gone its children are reparented and a walk
    finds nothing.

    **This list is not evidence of its own completeness.** `the_workers_that_must_die()` is what
    holds the project to killing the worker; this is only what the kill is handed.
    """
    application = psutil.Process(application_pid)
    doomed = [*application.children(recursive=True), application]
    if process.pid != application_pid:
        # The venv launcher, which is our direct child and the application's parent. Absent on
        # POSIX, where `sys.executable` is the interpreter itself.
        with contextlib.suppress(psutil.NoSuchProcess):
            doomed.append(psutil.Process(process.pid))
    return doomed


#: Big enough that the download is still running when the test kills it, small enough that the
#: success case finishes quickly. Paced by the handler rather than by its size, so neither
#: property depends on how fast the machine is.
CLIP_BYTES = 512 * 1024


def media_handler(total_bytes: int, chunk_delay: float) -> type[BaseHTTPRequestHandler]:
    """Serves `total_bytes` of `video/mp4`, paced by `chunk_delay`.

    A declared `Content-Type` and `Content-Length` are all yt-dlp's generic extractor needs to
    treat a URL as a direct media file, so this exercises the real extractor, real format
    selection and the real downloader. The same shape `T-013` established.
    """

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            """Silence `http.server`'s stderr logging; a test is not a web server."""

        def _send_headers(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(total_bytes))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()

        def do_HEAD(self) -> None:
            self._send_headers()

        def do_GET(self) -> None:
            self._send_headers()
            sent = 0
            chunk = b"\0" * (32 * 1024)
            try:
                while sent < total_bytes:
                    self.wfile.write(chunk[: min(len(chunk), total_bytes - sent)])
                    sent += len(chunk)
                    time.sleep(chunk_delay)
            except BrokenPipeError, ConnectionResetError, ConnectionAbortedError:
                # The expected end of a killed download: the worker went away mid-stream.
                #
                # **`ConnectionAbortedError` is the Windows spelling of exactly that** (`T-121`),
                # and it was missing — so on Windows the abort escaped this handler entirely and
                # `socketserver` printed a traceback for a condition two lines of this file
                # already call expected. `WinError 10053`, seen in run `30853680183`.
                pass

    return Handler


@pytest.fixture
def media_url() -> Iterator[Callable[..., str]]:
    """Serves a media URL from localhost. Not a network test: nothing leaves the machine."""
    servers: list[ThreadingHTTPServer] = []

    def serve(total_bytes: int = CLIP_BYTES, chunk_delay: float = 0.0) -> str:
        server = ThreadingHTTPServer(("127.0.0.1", 0), media_handler(total_bytes, chunk_delay))
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_address[1]}/clip.mp4"

    yield serve

    for server in servers:
        server.shutdown()
        server.server_close()


#: The preset these tests choose, and why it is not the default one.
#:
#: The dialog opens on "Best video up to 1080p (MP4)", whose selector filters on `height` and
#: `ext`. The local server serves a bare `video/mp4` with no declared height, so yt-dlp's generic
#: extractor produces a format that selector legitimately cannot match — "Requested format is not
#: available" is the *correct* answer to it. Choosing a preset is a thing the dialog exists for
#: (`REQ-006`), so the test does what a user would: it picks one whose selector fits.
#:
#: Recorded rather than worked around silently, because the alternative reading — that a
#: preset is broken — is wrong, and a future reader hitting this deserves the real reason.
END_TO_END_PRESET = "Best video available"


def why(composition: application.Composition, job_id: str) -> str:
    """Everything a failure on a machine nobody can reach needs to say (`T-062`).

    `assert spin(...), "the download never completed"` reports no status, no error and no
    environment, and both `T-037` tests failed on both CI platforms with exactly that. Learning
    that the job had failed `FFMPEG_MISSING` took a downloaded artifact and a local reproduction;
    it should have taken reading the assertion.
    """
    job = composition.store.get(job_id)
    view = composition.window.progress_view
    return (
        f"job={job.status.value if job else 'missing'} "
        f"kind={job.error_kind.value if job and job.error_kind else 'none'} "
        f"view={view.status.value if view else 'none'} "
        f"ffmpeg={'yes' if composition.ffmpeg.available else 'NO — ' + composition.ffmpeg.source} "
        f"error={(job.error_message if job else None) or 'none'}"
    )


def queue_one(
    composition: application.Composition,
    url: str,
    preset: str = END_TO_END_PRESET,
    bitrate: str | None = None,
) -> str:
    """Put one URL in the queue through the dialog the user would use, and return its job id.

    Through the assembled application rather than by writing a row: `REQ-012`'s promise is that
    what a user submits is persisted before anything acts on it, and a test that inserted the row
    itself would be proving the download rather than the queueing.
    """
    dialog = composition.window.open_add_dialog()
    dialog._urls.setPlainText(url)
    names = [dialog._preset_choice.itemText(i) for i in range(dialog._preset_choice.count())]
    assert preset in names, f"no preset named {preset!r}; the dialog offers {names}"
    dialog._preset_choice.setCurrentIndex(names.index(preset))
    if bitrate is not None:
        box = dialog._bitrate_choice
        index = box.findData(bitrate)
        assert index >= 0, f"the dialog offers no {bitrate} kbps entry"
        box.setCurrentIndex(index)
    # **Read before queued** (`UX-003`, `T-118`). Pasting resolves the line; nothing may be
    # queued until it has been, so this waits on the dialog's rows before committing.
    dialog.resolve()
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline and not (
        dialog.rows and all(row.committable for row in dialog.rows)
    ):
        composition.app.processEvents()
        time.sleep(0.005)
    assert dialog.rows and all(row.committable for row in dialog.rows), (
        f"the URL never resolved: {dialog.status_text()}"
    )
    dialog.add_to_queue()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not dialog.queued_job_ids:
        composition.app.processEvents()
        time.sleep(0.005)
    assert dialog.queued_job_ids, f"the paste never persisted: {dialog.status_text()}"
    job_id = dialog.queued_job_ids[0]
    dialog.close()
    # **Add already admitted it** (`T-115`). Callers used to follow this with
    # `manager.start(job_id)`, which was necessary while nothing drained the queue and is now an
    # error: `start()` refuses a job that is already probing, correctly, because `ARC-004` says a
    # session begins at `QUEUED` or `READY`.
    return job_id


# --- real media, so a conversion has something to convert (`T-077`) ---------------------------
#
# `media_handler` above serves half a megabyte of zeros under a `video/mp4` header, which is all
# yt-dlp's generic extractor needs to download it — and exactly nothing for ffmpeg to work with.
# A preset that extracts audio would fail on it, so the presets that convert could never have been
# tested against that fixture.
#
# The source is **generated by ffmpeg at test time** rather than committed. No binary enters the
# repository, no licence question follows it, and the tool is already required for the conversion
# under test, so generating with it costs nothing extra. Two seconds of a 440 Hz tone under a
# 320x240 test pattern: h264 + AAC, about 47 kB.


def build_media(ffmpeg_path: str, destination: Path) -> bytes:
    """Render a small real MP4 with both a video and an audio stream, and return its bytes."""
    result = subprocess.run(
        [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=15:duration=2",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(destination),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"could not build the source media: {result.stderr}"
    return destination.read_bytes()


def build_hls(ffmpeg_path: str, source: Path, directory: Path) -> None:
    """Render `source` into a local HLS presentation, with a subtitle track (`T077-R1`).

    **This is what makes every preset reachable without a network.** A direct `video/mp4` URL
    gives yt-dlp's generic extractor one format with no `height` and no `ext` to filter on, and no
    subtitles — so the 1080p preset's selector legitimately matches nothing and
    `FFmpegEmbedSubtitle` has nothing to embed. The first version of this file recorded both as
    structural limits of network-free testing. They are limits of *that fixture*: a master
    playlist declares `RESOLUTION` and `CODECS`, and an `EXT-X-MEDIA` group declares subtitles,
    so the same extractor reports a format with `height=240, ext=mp4` and `subtitles={'en': …}`.
    """
    subprocess.run(
        [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
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
        capture_output=True,
        text=True,
        check=True,
    )
    (directory / "subs.vtt").write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nhello subtitles\n", encoding="utf-8"
    )
    (directory / "subs.m3u8").write_text(
        "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:2\n#EXT-X-PLAYLIST-TYPE:VOD\n"
        "#EXTINF:2.0,\nsubs.vtt\n#EXT-X-ENDLIST\n",
        encoding="utf-8",
    )
    (directory / "master.m3u8").write_text(
        "#EXTM3U\n#EXT-X-VERSION:3\n"
        '#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="English",LANGUAGE="en",'
        'DEFAULT=YES,AUTOSELECT=YES,URI="subs.m3u8"\n'
        "#EXT-X-STREAM-INF:BANDWIDTH=400000,RESOLUTION=320x240,"
        'CODECS="avc1.42c01e,mp4a.40.2",SUBTITLES="subs"\n'
        "v0.m3u8\n",
        encoding="utf-8",
    )


@pytest.fixture
def hls_media_url(ffmpeg: tuple[str, str], tmp_path: Path) -> Iterator[Callable[[], str]]:
    """A localhost HLS presentation with video, audio and subtitles. Nothing leaves the machine."""
    servers: list[ThreadingHTTPServer] = []
    root = tmp_path / "hls"
    root.mkdir()
    source = tmp_path / "source.mp4"
    build_media(ffmpeg[0], source)
    build_hls(ffmpeg[0], source, root)

    def serve() -> str:
        handler = functools.partial(SimpleHTTPRequestHandler, directory=str(root))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_address[1]}/master.m3u8"

    yield serve

    for server in servers:
        server.shutdown()
        server.server_close()


def serve_bytes(payload: bytes, content_type: str) -> type[BaseHTTPRequestHandler]:
    """Serve exactly `payload`, so the file that arrives is the file that was built."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            """Silence `http.server`'s stderr logging."""

        def _send_headers(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()

        def do_HEAD(self) -> None:
            self._send_headers()

        def do_GET(self) -> None:
            self._send_headers()
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                self.wfile.write(payload)

    return Handler


@pytest.fixture
def real_media_url(ffmpeg: tuple[str, str], tmp_path: Path) -> Iterator[Callable[[], str]]:
    """A localhost URL serving a genuine two-second MP4. Nothing leaves the machine."""
    servers: list[ThreadingHTTPServer] = []
    payload = build_media(ffmpeg[0], tmp_path / "source.mp4")

    def serve() -> str:
        server = ThreadingHTTPServer(("127.0.0.1", 0), serve_bytes(payload, "video/mp4"))
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_address[1]}/clip.mp4"

    yield serve

    for server in servers:
        server.shutdown()
        server.server_close()


def streams_in(ffprobe_path: str, path: Path) -> list[dict[str, str]]:
    """What ffprobe reports for `path`: one dict per stream, plus the format's bitrate."""
    result = subprocess.run(
        [
            ffprobe_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name:format=bit_rate",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"ffprobe could not read {path}: {result.stderr}"
    report = json.loads(result.stdout)
    streams: list[dict[str, str]] = list(report.get("streams", []))
    for stream in streams:
        stream["_format_bit_rate"] = report.get("format", {}).get("bit_rate", "")
    return streams


#: Every built-in preset, and what its output must contain (`T-077`, `T077-R1`).
#:
#: `(preset, bitrate to choose, expected stream kinds, expected audio codec)`.
#:
#: **All five, against the HLS fixture.** The first version covered three and recorded the other
#: two as structural limits of network-free testing. They were limits of the *direct-file* fixture
#: — `T077-R1` — and a master playlist removes both: it declares `RESOLUTION` so the 1080p
#: selector has a `height` and an `ext` to match, and an `EXT-X-MEDIA` subtitle group so
#: `FFmpegEmbedSubtitle` has something to embed.
ALL_PRESETS = (
    ("Best video available", None, {"video", "audio"}, None),
    ("Best video up to 1080p (MP4)", None, {"video", "audio"}, None),
    ("Audio only (MP3)", "320", {"audio"}, "mp3"),
    ("Audio only (original)", None, {"audio"}, "aac"),
    ("Video with embedded subtitles", None, {"video", "audio", "subtitle"}, None),
)


def test_the_preset_table_covers_every_built_in_preset() -> None:
    """`T077-R1`: a hand-maintained list has to be pinned to the thing it claims to cover.

    Two lists were maintained by hand and neither asserted its relationship to
    `BUILT_IN_PRESETS`, so a preset added tomorrow would be covered by nothing and reported by
    nothing. This is the assertion that makes "each built-in preset" a fact rather than an
    intention.
    """
    covered = {name for name, *_ in ALL_PRESETS}
    built_in = {preset.name for preset in BUILT_IN_PRESETS}
    assert covered == built_in, (
        f"the table covers {sorted(covered)} and the registry offers {sorted(built_in)}; "
        "a preset in one and not the other is a download option nothing executes"
    )


@pytest.mark.parametrize(("preset", "bitrate", "kinds", "audio_codec"), ALL_PRESETS)
def test_each_preset_produces_the_file_it_promises(
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
    ffmpeg: tuple[str, str],
    hls_media_url: Callable[[], str],
    preset: str,
    bitrate: str | None,
    kinds: set[str],
    audio_codec: str | None,
) -> None:
    """`T-077`: every download option, inspected as a file rather than as a request.

    Until this existed, one preset had ever produced a file — `END_TO_END_PRESET` — and the other
    four were exercised only as far as the request describing them. `build_postprocessors` is
    asserted down to its `FFmpegExtractAudio` spec and validated against yt-dlp's own registry, so
    a postprocessor correctly *specified* and silently ineffective passed everything.

    The bitrate is asserted at **320**, not the 192 default, for the same reason: a conversion
    that ignored `preferredquality` entirely would pass at 192 by coincidence.
    """
    composition = application.compose(
        qapp,
        database=tmp_path / "queue.db",
        output_directory=tmp_path / "downloads",
        geometry_file=tmp_path / "window.toml",
    )
    try:
        job_id = queue_one(composition, hls_media_url(), preset=preset, bitrate=bitrate)
        assert spin(
            lambda: (
                composition.window.progress_view is not None
                and composition.window.progress_view.status is JobStatus.COMPLETED
            ),
            timeout=180,
        ), f"{preset} never completed — {why(composition, job_id)}"

        job = composition.store.get(job_id)
        assert job is not None and job.output_path is not None
        output = Path(job.output_path)
        assert output.exists(), (
            f"the queue recorded {output} for {preset!r} and no such file exists. A postprocessor "
            "that renames the output leaves the stored path describing something that is gone"
        )

        streams = streams_in(ffmpeg[1], output)
        assert {stream["codec_type"] for stream in streams} == kinds, (
            f"{preset!r} produced {[s['codec_type'] for s in streams]}, expected {sorted(kinds)}"
        )
        if audio_codec is not None:
            audio = next(s for s in streams if s["codec_type"] == "audio")
            assert audio["codec_name"] == audio_codec, (
                f"{preset!r} produced {audio['codec_name']} audio, expected {audio_codec}"
            )
        if bitrate is not None:
            audio = next(s for s in streams if s["codec_type"] == "audio")
            measured = int(audio["_format_bit_rate"] or 0)
            assert abs(measured - int(bitrate) * 1000) < 40_000, (
                f"{preset!r} at {bitrate} kbps produced {measured} bps. A conversion that ignores "
                "preferredquality lands near the preset default instead"
            )
    finally:
        composition.shutdown.begin()
        assert spin(lambda: composition.shutdown.finished, timeout=120)


def test_audio_postprocessing_does_not_overwrite_an_existing_final_path(
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
    hls_media_url: Callable[[], str],
) -> None:
    """T-046 must reserve the file that survives post-processing, not only its input name."""
    from tracks_and_trails.downloader import worker, ytdlp_adapter
    from tracks_and_trails.downloader.environment import ytdlp_candidates

    downloads = tmp_path / "downloads"
    composition = application.compose(
        qapp,
        database=tmp_path / "queue.db",
        output_directory=downloads,
        geometry_file=tmp_path / "window.toml",
    )
    try:
        url = hls_media_url()
        job_id = queue_one(composition, url, preset="Audio only (MP3)")
        job = composition.store.get(job_id)
        assert job is not None

        resolved = worker._import_ytdlp(ytdlp_candidates(None))
        options = ytdlp_adapter.build_options(
            job.request, job.request.output_template, probe_only=True
        )
        with resolved.module.YoutubeDL(options) as ydl:
            info = dict(ydl.extract_info(url, download=False) or {})
        source_target = worker.preview_path(job.request, info, resolved)
        protected = source_target.with_suffix(".mp3")
        protected.parent.mkdir(parents=True, exist_ok=True)
        protected.write_bytes(b"the user's existing mp3")

        assert spin(
            lambda: (
                (stored := composition.store.get(job_id)) is not None
                and stored.status is JobStatus.COMPLETED
            ),
            timeout=180,
        ), f"the MP3 download never completed — {why(composition, job_id)}"

        stored = composition.store.get(job_id)
        assert stored is not None and stored.output_path is not None
        assert protected.read_bytes() == b"the user's existing mp3", (
            "the source-extension reservation did not protect the MP3 produced by the postprocessor"
        )
        assert Path(stored.output_path) != protected
    finally:
        composition.shutdown.begin()
        assert spin(lambda: composition.shutdown.finished, timeout=120)


def test_original_audio_preview_matches_the_real_postprocessor_output(
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
    hls_media_url: Callable[[], str],
) -> None:
    """``original`` keeps the codec, but yt-dlp may still replace its source container.

    The built-in original-audio preset is one of the cases the amended ``REQ-011`` calls exact.
    Drive the real FFmpegExtractAudio postprocessor because a fake that writes the previewed name
    simply assumes the disputed behavior: AAC from this HLS fixture is copied into M4A even though
    the probed download target has another extension.
    """
    from tracks_and_trails.downloader import worker, ytdlp_adapter
    from tracks_and_trails.downloader.environment import ytdlp_candidates

    composition = application.compose(
        qapp,
        database=tmp_path / "queue.db",
        output_directory=tmp_path / "downloads",
        geometry_file=tmp_path / "window.toml",
    )
    try:
        url = hls_media_url()
        job_id = queue_one(composition, url, preset="Audio only (original)")
        job = composition.store.get(job_id)
        assert job is not None

        resolved = worker._import_ytdlp(ytdlp_candidates(None))
        options = ytdlp_adapter.build_options(
            job.request, job.request.output_template, probe_only=True
        )
        with resolved.module.YoutubeDL(options) as ydl:
            info = dict(ydl.extract_info(url, download=False) or {})
        preview = worker.preview_path(job.request, info, resolved)

        assert spin(
            lambda: (
                (stored := composition.store.get(job_id)) is not None
                and stored.status is JobStatus.COMPLETED
            ),
            timeout=180,
        ), f"the original-audio download never completed — {why(composition, job_id)}"

        stored = composition.store.get(job_id)
        assert stored is not None and stored.output_path is not None
        written = Path(stored.output_path)

        # **The real download is kept and the claim it gates is amended** (`T046-R4`). Equality is
        # not achievable here and the failure proved why: `FFmpegExtractAudioPP.run` decides the
        # container from `get_audio_codec(path)` — **ffprobe on the downloaded file** — and skips
        # conversion outright when the *downloaded* extension is already a common audio one.
        # Neither input exists when the preview is drawn, so "Audio only (original)" is labelled
        # provisional rather than predicted, and `REQ-011`'s exactness claim is narrowed to
        # extraction with a **named** codec.
        assert worker.preview_is_provisional(job.request), (
            "the original-audio preset was presented as an exact path; its container is decided "
            "by ffprobe on a file that does not exist yet"
        )
        assert written.stem == preview.stem, (
            f"preview promised the name {preview.stem!r} and the download wrote {written.stem!r}; "
            "provisional is about the container, and the rest of the path is still a promise"
        )
        assert written.parent == preview.parent, "the download landed outside the previewed folder"
    finally:
        composition.shutdown.begin()
        assert spin(lambda: composition.shutdown.finished, timeout=120)


# --- 1. a download that completes (`REQ-012`, `REQ-014`) --------------------------------------


def test_a_url_becomes_a_file_with_the_bytes_it_reported(
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
    media_url: Callable[..., str],
    record_property: Callable[[str, object], None],
) -> None:
    """Phase 1's first exit criterion, end to end through the assembled application.

    Real yt-dlp, a real spawned worker, a real HTTP download, a real file. The assertion that
    matters is the one joining them: **the file on disk is the size the last progress message
    said it would be.** A mismatch there is a download that reported one thing and produced
    another, which is the failure this criterion exists to catch and which no component test can
    see — the worker knows the bytes, the manager knows the messages, and only the assembled
    thing knows whether they agree.
    """
    composition = application.compose(
        qapp,
        database=tmp_path / "queue.db",
        output_directory=tmp_path / "downloads",
        geometry_file=tmp_path / "window.toml",
    )
    seen: list[Progress] = []
    composition.manager.progress.connect(seen.append)

    try:
        job_id = queue_one(composition, media_url(total_bytes=CLIP_BYTES, chunk_delay=0.0))

        view = composition.window.progress_view
        assert spin(
            lambda: (
                composition.window.progress_view is not None
                and composition.window.progress_view.status is JobStatus.COMPLETED
            ),
            timeout=120,
        ), f"the download never completed — {why(composition, job_id)}"
        view = composition.window.progress_view
        assert view is not None

        job = composition.store.get(job_id)
        assert job is not None
        assert job.status is JobStatus.COMPLETED
        assert job.output_path is not None, "a completed job with no file is not a completion"

        output = Path(job.output_path)
        assert output.exists(), f"the queue claims {output} exists and it does not"
        record_property("downloaded_bytes", output.stat().st_size)

        reported = [message.total_bytes for message in seen if message.total_bytes]
        assert reported, "no progress message ever reported a total"
        assert output.stat().st_size == reported[-1], (
            f"the file is {output.stat().st_size} bytes and the last progress message said "
            f"{reported[-1]}; a download that reports one number and writes another is exactly "
            "what this criterion is for"
        )
        assert output.stat().st_size == CLIP_BYTES, "the server served a different clip"
        assert job.bytes_total == output.stat().st_size, (
            f"the queue recorded {job.bytes_total} bytes for a {output.stat().st_size}-byte file. "
            "The criterion names the final progress message, but a stored total nobody checks is "
            "a wrong number the user reads later — a mutation halving it survived until this line"
        )

        # Monotonic, because a bar that goes backwards is a bar nobody can read.
        counted = [message.downloaded_bytes for message in seen if message.downloaded_bytes]
        assert counted == sorted(counted), f"progress went backwards: {counted}"

        stages = {message.stage for message in seen}
        assert Stage.DOWNLOADING_VIDEO in stages, (
            f"the download never reported the stage it spent its time in: {stages}"
        )

        # **The UI and the repository agree.** Disagreement is the defect; either alone is only
        # half the claim (`T-036` found three tests that watched one and asserted on the other).
        assert view.status is JobStatus.COMPLETED
        assert view.job_id == job_id
        assert not view.can_cancel
    finally:
        composition.shutdown.begin()
        assert spin(lambda: composition.shutdown.finished, timeout=60)


def test_a_progressive_download_completes_with_no_ffmpeg_at_all(
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
    media_url: Callable[..., str],
) -> None:
    """`T-061`'s acceptance criterion, driven end to end rather than asserted at the function.

    The same path as the test above, with ffmpeg made unavailable by pointing the override at a
    file that does not exist. The preset is still `Best video available` — `bestvideo+bestaudio/
    best` — and the clip is a single progressive format, so the `/best` branch wins and nothing
    needs merging.

    Before `T-061` this failed `FFMPEG_MISSING` before a byte moved, which is how a user without
    ffmpeg met four of the five presets. Driven through `compose()` rather than by hiding ffmpeg
    from `PATH`, so the test does not depend on what the machine running it happens to have.
    """
    composition = application.compose(
        qapp,
        database=tmp_path / "queue.db",
        output_directory=tmp_path / "downloads",
        geometry_file=tmp_path / "window.toml",
        ffmpeg_override=tmp_path / "no-such-ffmpeg",
    )
    try:
        assert not composition.ffmpeg.available, (
            "ffmpeg was available, so this proves nothing about doing without it"
        )
        job_id = queue_one(composition, media_url(total_bytes=CLIP_BYTES, chunk_delay=0.0))

        assert spin(
            lambda: (
                composition.window.progress_view is not None
                and composition.window.progress_view.status is JobStatus.COMPLETED
            ),
            timeout=120,
        ), "a download needing no merge was refused for want of ffmpeg — " + why(
            composition, job_id
        )

        job = composition.store.get(job_id)
        assert job is not None and job.output_path is not None
        assert Path(job.output_path).stat().st_size == CLIP_BYTES
    finally:
        composition.shutdown.begin()
        assert spin(lambda: composition.shutdown.finished, timeout=60)


# --- 2. surviving a kill (`NFR-003`, `ai/TESTING.md` §7 crash recovery) ------------------------


#: Runs the real application against a given database and URL, starts the download, and waits.
#:
#: A separate interpreter because the test kills it: `SIGKILL` to the test process would take
#: pytest with it, and recovery driven by a clean exit proves the graceful path this task is
#: explicitly not about.
DOWNLOAD_AND_WAIT = """
import os
import sys
from PySide6.QtWidgets import QApplication

from tracks_and_trails import app as application

database, downloads, geometry, url = sys.argv[1:5]
qapp = QApplication([])
composition = application.compose(
    qapp,
    database=__import__("pathlib").Path(database),
    output_directory=__import__("pathlib").Path(downloads),
    geometry_file=__import__("pathlib").Path(geometry),
)
dialog = composition.window.open_add_dialog()
dialog._urls.setPlainText(url)
names = [dialog._preset_choice.itemText(i) for i in range(dialog._preset_choice.count())]
dialog._preset_choice.setCurrentIndex(names.index("Best video available"))
# **Read before queued** (`UX-003`, `T-118`).
dialog.resolve()
while not (dialog.rows and all(row.committable for row in dialog.rows)):
    qapp.processEvents()
dialog.add_to_queue()
while not dialog.queued_job_ids:
    qapp.processEvents()
job_id = dialog.queued_job_ids[0]
dialog.close()
# No explicit start: Add admits the job now (`T-115`), and starting it again is refused.
# `os.getpid()` is this interpreter, which under a Windows venv is *not* the pid Popen returned
# — that one is the launcher. T072-R1: the test needs the application's own identity to walk
# from, because a count beneath the launcher cannot tell a worker-less tree from a healthy one.
print(os.getpid(), job_id, flush=True)
sys.exit(qapp.exec())
"""


def test_a_job_killed_mid_download_is_recovered_by_the_next_start(
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
    media_url: Callable[..., str],
) -> None:
    """Phase 1's fourth exit criterion, proved by killing a real process (`NFR-003`).

    The application is started for real in another interpreter, downloads until the row says
    `RUNNING`, and is then `SIGKILL`ed — no handlers, no teardown, nothing flushed. What must
    survive is not the download but the *record* of it: the next start finds a job claiming to be
    in flight with nothing flying it, and says so.

    `T-014` proves this at the database level. What is new here is that the application's own
    startup does it — `compose()` recovers before anything can read the queue — and that the
    request the user submitted comes back unchanged.
    """
    database = tmp_path / "queue.db"
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    # **Paced so that a worker which survives the kill is still running when we look**
    # (`T072-R1`). At 0.05 s the whole clip took under a second, so a missed worker finished
    # naturally long before any assertion could notice it was missed — the check would have passed
    # with no kill at all. Sixteen chunks at 0.5 s leaves seconds of download in flight at kill
    # time, which is what makes the survivor observable. It costs nothing in the passing case:
    # `wait_procs` returns as soon as everything is gone.
    url = media_url(total_bytes=CLIP_BYTES, chunk_delay=0.5)

    environment = dict(os.environ, PYTHONPATH=str(REPO_ROOT / "src"), QT_QPA_PLATFORM="offscreen")
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            DOWNLOAD_AND_WAIT,
            str(database),
            str(downloads),
            str(tmp_path / "window.toml"),
            url,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
        **isolate_the_application(),
    )
    try:
        assert process.stdout is not None
        handshake = process.stdout.readline().strip()
        assert handshake, "the application never queued anything"
        reported_pid, _, job_id = handshake.partition(" ")
        assert job_id, f"the startup handshake was not '<pid> <job id>': {handshake!r}"
        application_pid = int(reported_pid)

        # Wait for the row to say a worker holds it. Read from a separate connection, because the
        # application that owns the database is the one about to be killed.
        def is_running() -> bool:
            reader = db.connect(database)
            try:
                job = JobRepository(reader).get(job_id)
                return job is not None and job.status is JobStatus.RUNNING
            finally:
                reader.close()

        deadline = time.monotonic() + 120
        while time.monotonic() < deadline and not is_running():
            time.sleep(0.05)
        if not is_running():
            # Same reasoning as `why()`: this runs in another interpreter, so its state is only
            # reachable through the row it left behind and the output it printed (`T-062`).
            reader = db.connect(database)
            try:
                stranded = JobRepository(reader).get(job_id)
            finally:
                reader.close()
            assert stranded is not None, "the job vanished from the database"
            raise AssertionError(
                "the download never reached running, so there is nothing to kill — "
                f"job={stranded.status.value} "
                f"kind={stranded.error_kind.value if stranded.error_kind else 'none'} "
                f"error={stranded.error_message or 'none'}"
            )

        stored_before = None
        reader = db.connect(database)
        try:
            stored_before = JobRepository(reader).get(job_id)
        finally:
            reader.close()
        assert stored_before is not None

        # Two sources, on purpose (`T072-R1`). `must_die` is the test's own record of the worker
        # set, taken while the row still says RUNNING. `doomed` is what the kill is handed. If the
        # capture ever drops the worker, the kill misses it and the assertion below still catches
        # it — which is exactly what a single shared list could not do.
        must_die = the_workers_that_must_die(application_pid)
        doomed = capture_the_doomed_tree(process, application_pid)
        kill_the_application(process, doomed)

        # **Deliberately shorter than the download still in flight.** A generous timeout is wrong
        # here: `wait_procs` returns as soon as everything is gone, so a long one only matters
        # when something survived — and waiting 30 s would let a missed worker finish the clip
        # and be reported as correctly reaped. Five seconds is longer than any real kill needs
        # and shorter than the seconds of paced download remaining.
        _, survivors = psutil.wait_procs(must_die, timeout=5)
        assert not survivors, (
            f"{len(survivors)} worker process(es) outlived the kill and still own the database "
            f"this test is about to reopen: {sorted(p.pid for p in survivors)}. The kill was "
            f"handed {sorted(p.pid for p in doomed)}, so a worker missing from that list is the "
            f"T072-R1 failure and not a flake."
        )
        process.wait(timeout=30)
    finally:
        if process.poll() is None:  # pragma: no cover - only on an unexpected path
            # Best effort, and deliberately not the asserting path: this runs when the test has
            # already failed, and a second assertion here would replace that failure's cause.
            with contextlib.suppress(psutil.Error):
                for victim in [*psutil.Process(process.pid).children(recursive=True)][::-1]:
                    victim.kill()
            process.kill()
            process.wait(timeout=30)
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()

    # Restart: `compose()` recovers before anything can read the queue.
    composition = application.compose(
        qapp,
        database=database,
        output_directory=downloads,
        geometry_file=tmp_path / "window2.toml",
    )
    try:
        recovered = composition.store.get(job_id)
        assert recovered is not None, "the job did not survive the kill at all"
        assert recovered.status is JobStatus.FAILED, (
            f"a job left {recovered.status.value} is a job the queue still thinks is running"
        )
        assert recovered.error_kind is ErrorKind.INTERRUPTED, (
            f"recovered as {recovered.error_kind}; an interruption is not a worker crash — "
            "nobody watched this one end"
        )
        assert is_retryable(recovered.error_kind), "a recovered job the user cannot retry is lost"

        # **The request is unchanged**, field for field. `REQ-012` promises that what was
        # submitted is what is stored, and a recovery that rewrote it would be a different job
        # wearing the same id.
        assert recovered.request == stored_before.request
        assert recovered.url == stored_before.url

        # Visible, and offering the retry its kind allows (`REQ-018`).
        view = composition.window.watch(job_id)
        assert view.status is JobStatus.FAILED
        assert view.can_retry, "a recovered job has to be restartable from the UI"
        assert recovered.error_message, "recovery that says nothing is recovery nobody can act on"
    finally:
        composition.shutdown.begin()
        assert spin(lambda: composition.shutdown.finished, timeout=60)


def test_recovery_is_the_applications_own_and_not_the_tests(
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
) -> None:
    """`compose()` recovers, and does it before anything can read the queue.

    Asserted against a row planted directly in the database, so the claim is about startup rather
    than about whatever the previous test happened to leave behind. A `RUNNING` row on disk is
    always a lie — the process that could have made it true is gone — and the application has to
    treat it as one without being asked.
    """
    database = tmp_path / "queue.db"
    connection = db.connect(database)
    try:
        repository = JobRepository(connection)
        job = Job(
            id="planted",
            url="https://planted.invalid/clip",
            request=DownloadRequest(
                url="https://planted.invalid/clip",
                output_directory=str(tmp_path / "downloads"),
                format_selector="best",
                output_template="%(title)s.%(ext)s",
            ),
            created_at=datetime.now(UTC),
        )
        repository.append([job])
        running = job.with_status(JobStatus.PROBING).with_status(JobStatus.READY)
        repository.update(running.with_status(JobStatus.RUNNING))
    finally:
        connection.close()

    composition = application.compose(
        qapp,
        database=database,
        output_directory=tmp_path / "downloads",
        geometry_file=tmp_path / "window.toml",
    )
    try:
        recovered = composition.store.get("planted")
        assert recovered is not None
        assert recovered.status is JobStatus.FAILED
        assert recovered.error_kind is ErrorKind.INTERRUPTED
    finally:
        composition.shutdown.begin()
        assert spin(lambda: composition.shutdown.finished, timeout=60)
