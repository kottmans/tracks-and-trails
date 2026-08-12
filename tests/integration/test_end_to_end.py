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
from urllib.parse import quote

import psutil
import pytest
from PySide6.QtWidgets import QApplication

from tracks_and_trails import app as application
from tracks_and_trails.core import settings as core_settings
from tracks_and_trails.core.errors import ErrorKind, is_retryable
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import DownloadRequest, Job
from tracks_and_trails.core.presets import BUILT_IN_PRESETS
from tracks_and_trails.downloader import worker
from tracks_and_trails.downloader.protocol import Progress, Stage
from tracks_and_trails.persistence import db
from tracks_and_trails.persistence.repositories import JobRepository
from tracks_and_trails.ui.format_selection import FormatKind, kind_of
from tracks_and_trails.ui.row_delegate import CHOOSE_FORMATS_TEXT

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


def kill_only_the_application(application_pid: int) -> None:
    """Kill **exactly one process** — the application — and nothing beneath it (`P2EXIT-R1`).

    This is the opposite of `kill_the_application`, and the difference is the whole point. That
    helper reaps the *tree*, because the tests that use it are about a database being safely
    reopened. A test about **orphans** cannot use it: if the kill reaches the workers, the workers
    dying proves the kill worked, not that anything in the product did. A reviewer's mutation
    deleting `_exit_when_the_parent_does()` from `worker.prepare_this_worker()` left the N-worker
    phase gate green in 9.52 s for precisely that reason.

    Killing one pid leaves each worker to notice on its own, which is the mechanism `T-072`
    identified and `ARC-002` requires: `multiprocessing.parent_process().join()` returns when the
    parent's sentinel closes, and the worker then kills its own group.

    **No platform split, deliberately** — unlike everything else in this file. `Process.kill()` is
    `SIGKILL` to one pid on POSIX and `TerminateProcess` on one handle on Windows; neither reaches
    a child. The launcher is left alive on purpose: it is the application's *parent*, not the
    workers', so killing it would prove nothing extra and would confuse what died of what.

    Nothing unwinds and no handler runs, on either platform, which is what makes this a crash
    rather than a shutdown.
    """
    psutil.Process(application_pid).kill()


def reap_the_captured_tree(
    process: subprocess.Popen[str], doomed: list[psutil.Process]
) -> list[psutil.Process]:
    """Clean up after a test that killed only part of a tree, from a set captured beforehand.

    `reap_application` walks from the application's pid, which is the right thing when the
    application is still there — and finds nothing once it is not, because its children have been
    reparented. A test that kills the application *on purpose* and then asks what survived has to
    hand over the walk it took while the tree was intact.

    **Returns survivors rather than asserting on them.** This runs in a `finally`, so raising here
    would replace the failure the test actually found with a teardown error about its consequence.
    That is also why it stays a *return*: `T127-R1` asks for every survivor to be reported without
    displacing an earlier behavioral failure, and a list the caller asserts on last does both.

    **Only the ordinary races are tolerated** (`T127-R1`). This caught every `psutil.Error` while
    killing and `TimeoutExpired` while waiting, and returned only what `wait_procs` reported — so
    a refused kill (`AccessDenied`) and a stuck direct child were both swallowed, and
    `assert not leaked` passed over a genuine leak. A process that has already exited is a real
    race and is nothing; a process this test may not kill, or one that will not go, is a leak the
    next test would be blamed for.
    """
    refused: list[psutil.Process] = []
    for victim in doomed:
        try:
            victim.kill()
        except psutil.NoSuchProcess, ProcessLookupError:
            continue  # it beat us to it; the wait below is the real check
        except psutil.Error:
            # `AccessDenied`, or anything else that means the kill did not happen. Not "already
            # gone" — recorded, and confirmed against `is_running` below rather than assumed.
            refused.append(victim)

    # **Our own direct child is excluded from the wait**, for `kill_the_application`'s reason: it
    # is a zombie until reaped, and reaping it here would steal the exit status `process.wait()`
    # is about to collect.
    others = [victim for victim in doomed if victim.pid != process.pid]
    alive: list[psutil.Process] = psutil.wait_procs(others, timeout=30)[1]
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        # **The one survivor the wait above structurally cannot report.** It is excluded from
        # `wait_procs` so its exit status survives, which also means a child that never dies left
        # no trace at all — suppressed, and the launcher went on holding whatever it holds.
        with contextlib.suppress(psutil.Error):
            alive.append(psutil.Process(process.pid))

    survivors = {victim.pid: victim for victim in (*alive, *refused) if victim.is_running()}
    return list(survivors.values())


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


#: Deterministic bytes for the resume fixture, so the finished file can be compared exactly.
#:
#: A repeating 256-byte ramp rather than `media_handler`'s zeros: a resumed download that wrote the
#: right *number* of bytes in the wrong *order* is the failure this test exists to catch, and a
#: file of zeros cannot tell the two apart.
RESUMABLE_BYTES: Final = bytes(range(256)) * (CLIP_BYTES // 256)


def resumable_media_handler(
    log: list[tuple[str, int]], chunk_delay: float
) -> type[BaseHTTPRequestHandler]:
    """Serves `RESUMABLE_BYTES` and **honours `Range`**, recording every request (`T-113`).

    `media_handler` advertises `Accept-Ranges` and then ignores the header, always answering `200`
    from byte zero — which is a perfectly realistic server and the *wrong* one for this test: yt-dlp
    sees a `200` where it asked for a `206`, discards its partial and starts again, so a resume
    could never be observed. This one answers `206` with a `Content-Range`, which is what makes the
    resume visible rather than assumed.

    `log` is appended to from the server's own threads and read by the test process afterwards.
    Appending to a list is atomic under the GIL and nothing reads it while a request is in flight,
    so no lock is needed for what it is used for — counting.
    """

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            """Silence `http.server`'s stderr logging; a test is not a web server."""

        def _offset(self) -> int:
            header = self.headers.get("Range") or ""
            if not header.startswith("bytes="):
                return 0
            start, _, _ = header.removeprefix("bytes=").partition("-")
            return int(start) if start.isdigit() else 0

        def do_HEAD(self) -> None:
            log.append(("HEAD", 0))
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(RESUMABLE_BYTES)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()

        def do_GET(self) -> None:
            offset = self._offset()
            log.append(("GET", offset))
            body = RESUMABLE_BYTES[offset:]
            self.send_response(206 if offset else 200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Accept-Ranges", "bytes")
            if offset:
                self.send_header(
                    "Content-Range",
                    f"bytes {offset}-{len(RESUMABLE_BYTES) - 1}/{len(RESUMABLE_BYTES)}",
                )
            self.end_headers()
            try:
                for start in range(0, len(body), 32 * 1024):
                    self.wfile.write(body[start : start + 32 * 1024])
                    time.sleep(chunk_delay)
            except BrokenPipeError, ConnectionResetError, ConnectionAbortedError:
                # The expected end of a killed download — see `media_handler` for why
                # `ConnectionAbortedError` is named (`T-121`).
                pass

    return Handler


@pytest.fixture
def resumable_media_url() -> Iterator[Callable[..., tuple[str, list[tuple[str, int]]]]]:
    """A localhost URL that honours `Range`, and the request log it writes."""
    servers: list[ThreadingHTTPServer] = []

    def serve(chunk_delay: float = 0.0) -> tuple[str, list[tuple[str, int]]]:
        log: list[tuple[str, int]] = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), resumable_media_handler(log, chunk_delay))
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_address[1]}/clip.mp4", log

    yield serve

    for server in servers:
        server.shutdown()
        server.server_close()


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


def shown_status(composition: application.Composition, job_id: str) -> JobStatus | None:
    """What the queue **row** says about `job_id` — the application's answer, not the database's.

    `UX-005` removed the detail pane, so the row is now the only place the application reports a
    job's state and it is what these tests observe. Reading `composition.store` instead would be
    asserting on the *database*, and `T-013`'s ordering guarantee is precisely that the database
    leads the UI: the writer thread commits and *then* signals the GUI thread, so a store-based
    wait can pass in the gap before the row is redrawn. The row is the later of the two, which is
    what makes it the honest thing to wait on.
    """
    view = composition.window.queue_view
    if view is None:
        return None
    job = view.model.job_for(job_id)
    return job.status if job is not None else None


def why(composition: application.Composition, job_id: str) -> str:
    """Everything a failure on a machine nobody can reach needs to say (`T-062`).

    `assert spin(...), "the download never completed"` reports no status, no error and no
    environment, and both `T-037` tests failed on both CI platforms with exactly that. Learning
    that the job had failed `FFMPEG_MISSING` took a downloaded artifact and a local reproduction;
    it should have taken reading the assertion.
    """
    job = composition.store.get(job_id)
    shown = shown_status(composition, job_id)
    return (
        f"job={job.status.value if job else 'missing'} "
        f"kind={job.error_kind.value if job and job.error_kind else 'none'} "
        f"row={shown.value if shown else 'none'} "
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
    # **Two languages, not one** (`T-109`). `REQ-010`'s acceptance criterion asks for a language
    # *selection* asserted with more than one, including one the source does not publish — which a
    # single-language presentation cannot exercise: picking "the only one there is" and picking
    # "these two of the three offered" are different behaviours, and the first passes whether or
    # not `subtitleslangs` reaches yt-dlp at all.
    for language, words in (("en", "hello subtitles"), ("de", "hallo untertitel")):
        (directory / f"subs_{language}.vtt").write_text(
            f"WEBVTT\n\n00:00:00.000 --> 00:00:02.000\n{words}\n", encoding="utf-8"
        )
        (directory / f"subs_{language}.m3u8").write_text(
            "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:2\n#EXT-X-PLAYLIST-TYPE:VOD\n"
            f"#EXTINF:2.0,\nsubs_{language}.vtt\n#EXT-X-ENDLIST\n",
            encoding="utf-8",
        )
    (directory / "master.m3u8").write_text(
        "#EXTM3U\n#EXT-X-VERSION:3\n"
        '#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="English",LANGUAGE="en",'
        'DEFAULT=YES,AUTOSELECT=YES,URI="subs_en.m3u8"\n'
        '#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="German",LANGUAGE="de",'
        'DEFAULT=NO,AUTOSELECT=NO,URI="subs_de.m3u8"\n'
        "#EXT-X-STREAM-INF:BANDWIDTH=400000,RESOLUTION=320x240,"
        'CODECS="avc1.42c01e,mp4a.40.2",SUBTITLES="subs"\n'
        "v0.m3u8\n",
        encoding="utf-8",
    )
    build_cover(ffmpeg_path, directory / "cover.jpg")


def build_cover(ffmpeg_path: str, destination: Path) -> None:
    """A one-frame JPEG for the page to advertise as its `og:image` (`REQ-010`, `T-109`).

    `EmbedThumbnail` embeds a picture that has to have been downloaded, and an HLS master playlist
    advertises no thumbnail — so without this the option could only ever be asserted as a request.
    Generated by ffmpeg for `build_media`'s reason: no binary enters the repository, and the tool
    is already required by the conversion under test.
    """
    subprocess.run(
        [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=160x120:d=1",
            "-frames:v",
            "1",
            str(destination),
        ],
        capture_output=True,
        text=True,
        check=True,
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


@pytest.fixture
def named_media_url(ffmpeg: tuple[str, str], tmp_path: Path) -> Iterator[Callable[[str], str]]:
    """A localhost URL serving a real MP4 **under a filename the caller chooses** (`T-112`).

    yt-dlp's generic extractor derives the title from the URL's last path component, so this is how
    a test gets a real extraction whose title contains characters Windows forbids — which is the
    case Phase 3's exit criterion names, and the one where a preview written by a second renderer
    would diverge from the write.
    """
    servers: list[ThreadingHTTPServer] = []
    payload = build_media(ffmpeg[0], tmp_path / "named-source.mp4")

    def serve(filename: str) -> str:
        server = ThreadingHTTPServer(("127.0.0.1", 0), serve_bytes(payload, "video/mp4"))
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_address[1]}/{quote(filename)}"

    yield serve

    for server in servers:
        server.shutdown()
        server.server_close()


def streams_in(ffprobe_path: str, path: Path, *, language: bool = False) -> list[dict[str, str]]:
    """What ffprobe reports for `path`: one dict per stream, plus the format's bitrate.

    `language=True` also asks for each stream's language tag, as `_language` (`T-109`). Off by
    default because it changes what ffprobe is asked for, and every existing caller wants the
    smaller answer; a subtitle selection is the one question that needs to know *which* track
    arrived rather than how many did.
    """
    entries = "stream=codec_type,codec_name:format=bit_rate"
    if language:
        entries = "stream=codec_type,codec_name:stream_tags=language:format=bit_rate"
    result = subprocess.run(
        [
            ffprobe_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-show_entries",
            entries,
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
    # **Read as the nested shape ffprobe actually returns, and flattened into the flat one this
    # helper promises** (`T109-R6`). The raw report was annotated `list[dict[str, str]]` and then
    # indexed for `tags`, which is itself a dict — so mypy resolved the key type to `Never` and
    # every read of it was an error. One conversion, in one direction, at the boundary.
    raw: list[dict[str, Any]] = list(report.get("streams") or [])
    container: dict[str, Any] = report.get("format") or {}
    bit_rate = str(container.get("bit_rate", ""))
    streams: list[dict[str, str]] = []
    for stream in raw:
        # `tags` is flattened out so a caller reads one dict rather than two shapes, and the
        # additions are named with a leading underscore — both are this helper's, not ffprobe's.
        tags: dict[str, Any] = stream.get("tags") or {}
        flattened = {key: str(value) for key, value in stream.items() if key != "tags"}
        flattened["_format_bit_rate"] = bit_rate
        flattened["_language"] = str(tags.get("language", ""))
        streams.append(flattened)
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
    # `UX-006`: a composed application opens with its queue stopped, so this presses Start.
    composition.manager.start_queue()
    try:
        job_id = queue_one(composition, hls_media_url(), preset=preset, bitrate=bitrate)
        assert spin(
            lambda: shown_status(composition, job_id) is JobStatus.COMPLETED,
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


def test_a_default_output_template_names_the_file_that_is_actually_written(
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
    media_url: Callable[..., str],
) -> None:
    """**`REQ-023`, `T-195`: the criterion read literally** (`T195-R4`).

    The criterion says a job whose preset states no template *"writes to the path that template
    renders"*, and every earlier version of this proof stopped short of a file: the composition
    tests persist the request and preview its path, which exercises the render and the containment
    rule but creates nothing on disk.

    This downloads. The template is set in `settings.toml` before the application composes, the
    shipped preset states none and therefore defers to it, and the assertion is that **the file
    exists at the path the template describes** — a folder named for the uploader, which the
    default template does not produce.
    """
    chosen = "%(uploader)s/%(title)s.%(ext)s"
    settings_file = tmp_path / "settings.toml"
    assert (
        core_settings.save(
            core_settings.set_output_template(core_settings.Settings(), chosen), settings_file
        )
        is None
    )

    composition = application.compose(
        qapp,
        database=tmp_path / "queue.db",
        output_directory=tmp_path / "downloads",
        geometry_file=tmp_path / "window.toml",
        settings_file=settings_file,
    )
    # `UX-006`: a composed application opens with its queue stopped, so this presses Start.
    composition.manager.start_queue()
    try:
        job_id = queue_one(composition, media_url())
        assert spin(
            lambda: shown_status(composition, job_id) is JobStatus.COMPLETED, timeout=180
        ), f"the download never completed — {why(composition, job_id)}"

        job = composition.store.get(job_id)
        assert job is not None and job.output_path is not None
        written = Path(job.output_path)

        assert written.exists(), (
            f"the queue recorded {written} and no such file exists, so the template names a path "
            "nothing was written to"
        )
        assert written.parent != tmp_path / "downloads", (
            f"{written} sits directly in the download folder, so the uploader segment the chosen "
            "template asks for was never applied — the shipped default was used instead"
        )
        assert job.request.output_template == chosen, (
            "the job carries a template other than the one Settings stored"
        )
    finally:
        # **The orderly shutdown, not a stopped queue** (`T195-R7`). `stop_queue` stops *scheduling*
        # and leaves the writer thread running, so the process aborted at teardown with
        # `QThread: Destroyed while thread 'queue-writer' is still running` — after the assertions
        # had passed, which is how a green line and an exit code of 134 came from one run. Every
        # neighbouring download test here begins the shutdown and waits for it; this one did not.
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
    # `UX-006`: a composed application opens with its queue stopped, so this presses Start.
    composition.manager.start_queue()
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
    # `UX-006`: a composed application opens with its queue stopped, so this presses Start.
    composition.manager.start_queue()
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
    # `UX-006`: a composed application opens with its queue stopped, so this presses Start.
    composition.manager.start_queue()
    seen: list[Progress] = []
    composition.manager.progress.connect(seen.append)

    try:
        job_id = queue_one(composition, media_url(total_bytes=CLIP_BYTES, chunk_delay=0.0))

        assert spin(
            lambda: shown_status(composition, job_id) is JobStatus.COMPLETED,
            timeout=120,
        ), f"the download never completed — {why(composition, job_id)}"

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
        # Since `UX-005` the UI's answer is the queue row rather than a detail pane.
        assert shown_status(composition, job_id) is JobStatus.COMPLETED
        view = composition.window.queue_view
        assert view is not None and view.model.job_for(job_id) is not None, (
            f"{job_id} completed and the queue has no row for it, so the tab in front of the "
            "user does not answer 'did it work' (UX-005)"
        )
        # *That a finished row offers no Cancel* was `view.can_cancel` and is now a property of
        # the row's verbs, asserted where they are drawn (`T-124`) rather than dropped here.
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
    # `UX-006`: a composed application opens with its queue stopped, so this presses Start.
    composition.manager.start_queue()
    try:
        assert not composition.ffmpeg.available, (
            "ffmpeg was available, so this proves nothing about doing without it"
        )
        job_id = queue_one(composition, media_url(total_bytes=CLIP_BYTES, chunk_delay=0.0))

        assert spin(
            lambda: shown_status(composition, job_id) is JobStatus.COMPLETED,
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
# `UX-006`: a composed application opens stopped, and this script exists to be killed
# mid-download, so it presses Start. Without it the job reaches READY and stays there — which is
# the shape this failed as, and it is the gate working rather than a defect.
composition.manager.start_queue()
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
# No explicit per-job start: Add admits the job now (`T-115`), and starting it again is
# refused. The queue-level Start above is a different thing (`UX-006`).
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
    # `UX-006`: a composed application opens with its queue stopped, so this presses Start.
    composition.manager.start_queue()
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

        # **Visible** (`REQ-018`), in the queue row, which since `UX-005` is where a job reports
        # itself. The other half of `REQ-018` — that the row *offers* the retry its kind allows —
        # has no home until `T-124` draws the row's verbs, and is asserted there rather than
        # dropped. `is_retryable` above is the kind; this is the application saying so.
        assert shown_status(composition, job_id) is JobStatus.FAILED, (
            "a recovered job the queue does not show as failed is a job nobody knows to retry"
        )
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
    # `UX-006`: a composed application opens with its queue stopped, so this presses Start.
    composition.manager.start_queue()
    try:
        recovered = composition.store.get("planted")
        assert recovered is not None
        assert recovered.status is JobStatus.FAILED
        assert recovered.error_kind is ErrorKind.INTERRUPTED
    finally:
        composition.shutdown.begin()
        assert spin(lambda: composition.shutdown.finished, timeout=60)


# --- T-108: a chosen video + audio pair produces one merged file (REQ-008) --------------------
#
# **`T108-R1`.** The criterion is *"a video-only and an audio-only selection produce one merged
# file, on both platforms"*, and the first submission stopped at a `DownloadRequest` carrying
# `137+140`. A request is not a file: everything between the selector and the output — yt-dlp's
# format resolution, two downloads, and the ffmpeg mux — was unexercised, and that span is exactly
# where `T-061` lived.
#
# The presentation below is what makes the criterion reachable without a network: a master playlist
# with a **video-only variant** and a separate `EXT-X-MEDIA:TYPE=AUDIO` group, which yt-dlp reports
# as two formats — one `vcodec: 'none'`, one `acodec: 'none'`. `hls_media_url`'s single variant
# carries both streams and can never need merging.
#
# **It also corrected the routing rule.** The audio group arrives with *no `acodec` at all*, because
# HLS puts the codec list on the variant rather than on the group — so `kind_of`'s first version,
# which required both answers, made the commonest real audio half unpairable. Building this is what
# found that; see `format_selection.kind_of`.


def build_split_hls(ffmpeg_path: str, source: Path, directory: Path) -> None:
    """Render `source` into an HLS presentation whose video and audio are **separate formats**.

    Two renditions rather than one: `-an` drops the audio from the video playlist and `-vn` drops
    the video from the audio one, so neither is playable alone and a merge is genuinely required.

    The master deliberately declares only the **video** codec in `CODECS`. That is what a real
    packager emits — the audio group's codec is not part of the variant's list — and it is why the
    audio format arrives with no `acodec`. Adding one here would make the fixture kinder than
    reality and hide the case `kind_of` had to learn.
    """
    for arguments, playlist, segments in (
        (["-an", "-c:v", "libx264", "-preset", "ultrafast"], "v0.m3u8", "v0_%d.ts"),
        (["-vn", "-c:a", "aac"], "a0.m3u8", "a0_%d.ts"),
    ):
        subprocess.run(
            [
                ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source),
                *arguments,
                "-f",
                "hls",
                "-hls_time",
                "1",
                "-hls_playlist_type",
                "vod",
                "-hls_segment_filename",
                str(directory / segments),
                str(directory / playlist),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    (directory / "master.m3u8").write_text(
        "#EXTM3U\n#EXT-X-VERSION:3\n"
        '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud",NAME="English",DEFAULT=YES,AUTOSELECT=YES,'
        'URI="a0.m3u8"\n'
        "#EXT-X-STREAM-INF:BANDWIDTH=400000,RESOLUTION=320x240,"
        'CODECS="avc1.42c01e",AUDIO="aud"\n'
        "v0.m3u8\n",
        encoding="utf-8",
    )


@pytest.fixture
def split_media_url(ffmpeg: tuple[str, str], tmp_path: Path) -> Iterator[Callable[[], str]]:
    """A localhost HLS presentation whose video and audio are separate formats.

    Nothing leaves the machine.
    """
    servers: list[ThreadingHTTPServer] = []
    root = tmp_path / "split-hls"
    root.mkdir()
    source = tmp_path / "split-source.mp4"
    build_media(ffmpeg[0], source)
    build_split_hls(ffmpeg[0], source, root)

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


def choose_pair_and_queue(composition: application.Composition, url: str) -> str:
    """Paste `url`, open the format table, pick the two halves, and Add — the user's whole route.

    **Through the dialog rather than by building a request**, for `queue_one`'s reason and one
    more: `T-108`'s criterion is about a *selection* producing a merged file, so a test that
    assembled the selector itself would skip the part under review — the row menu's formats
    entry, the panel, the mode, and the routing of each row into its slot.
    """
    dialog = composition.window.open_add_dialog()
    dialog._urls.setPlainText(url)
    # **The batch preset is set before resolving, and it has to be.** A probe runs yt-dlp with the
    # selector the batch currently names, so the default `…[ext=mp4]+…[ext=m4a]` preset makes this
    # presentation fail to resolve at all — *"Requested format is not available"* — before any of
    # `T-108` is reached. The row's own choice replaces this selector entirely once it is made; what
    # this affects is whether the URL can be read in the first place.
    names = [dialog._preset_choice.itemText(i) for i in range(dialog._preset_choice.count())]
    dialog._preset_choice.setCurrentIndex(names.index(END_TO_END_PRESET))
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

    # **`T-203` rerouted this gesture, twice.** The row's combo holds presets only; the verb bar
    # that briefly followed was rejected on sight and `UX-011` ruled option *E*: the three
    # per-row commands are entries in **the row's own menu**. So the route is now *open the row's
    # menu, choose `Choose specific formats…`* — the same route `choose_in_editor` sends the UI
    # suite's sentinel choices down, driven here through the menu's real action.
    actions = [
        action
        for action in dialog.row_menu(dialog.rows[0]).actions()
        if action.text() == CHOOSE_FORMATS_TEXT
    ]
    assert actions, (
        f"the row's menu does not offer the format table for a resolved single item — "
        f"{dialog.status_text()}"
    )
    actions[0].trigger()
    composition.app.processEvents()

    panel = dialog.open_format_panel
    assert panel is not None, "the row did not open into its format table"
    mode = panel.table.mode_control
    assert mode is not None, (
        "the merge mode was not offered for a presentation that has a video-only and an "
        "audio-only format — the routing rule disagrees with what yt-dlp reported"
    )
    mode.setChecked(True)

    formats = panel.table.model.formats()
    kinds = {kind_of(entry_): entry_ for entry_ in formats}
    assert FormatKind.VIDEO_ONLY in kinds and FormatKind.AUDIO_ONLY in kinds, (
        f"yt-dlp reported {[(f.format_id, str(kind_of(f))) for f in formats]}, which is not a pair"
    )
    for kind in (FormatKind.VIDEO_ONLY, FormatKind.AUDIO_ONLY):
        wanted = kinds[kind]
        row = next(index for index in range(len(formats)) if formats[index] is wanted)
        panel.table.table.setCurrentIndex(panel.table.model.index(row, 0))
        panel.table.choose_current()
        composition.app.processEvents()

    assert dialog.open_panel is None, "the pair completed and the panel stayed open"
    dialog.add_to_queue()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not dialog.queued_job_ids:
        composition.app.processEvents()
        time.sleep(0.005)
    assert dialog.queued_job_ids, f"the pair never persisted: {dialog.status_text()}"
    return dialog.queued_job_ids[0]


def test_a_chosen_video_and_audio_pair_produce_one_merged_file(
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
    ffmpeg: tuple[str, str],
    split_media_url: Callable[[], str],
) -> None:
    """**`T-108`'s acceptance criterion**, as a file rather than as a request (`REQ-008`).

    *"A video-only and an audio-only selection produce one merged file."* Everything is real except
    the server: the user's route through the dialog, yt-dlp's own format resolution, two downloads,
    and ffmpeg's mux. The output is inspected with `ffprobe`, so a merge that produced a video-only
    file — which is what selecting one half would do — fails here.

    **Both platforms**: this runs wherever the suite runs, and CI runs the whole suite on Windows
    as well as Linux. Nothing in it is POSIX-only.
    """
    composition = application.compose(
        qapp,
        database=tmp_path / "queue.db",
        output_directory=tmp_path / "downloads",
        geometry_file=tmp_path / "window.toml",
    )
    composition.manager.start_queue()
    try:
        job_id = choose_pair_and_queue(composition, split_media_url())
        assert spin(
            lambda: shown_status(composition, job_id) is JobStatus.COMPLETED,
            timeout=180,
        ), f"the merge never completed — {why(composition, job_id)}"

        job = composition.store.get(job_id)
        assert job is not None and job.output_path is not None
        # **The selector is the two ids joined**, which is what the selection produced — asserted
        # here as well as on the file, because a request that happened to resolve to a progressive
        # format would produce a perfectly good merged-looking file and prove nothing.
        assert "+" in job.request.format_selector, job.request.format_selector

        output = Path(job.output_path)
        assert output.exists(), f"the queue recorded {output} and no such file exists"
        outputs = sorted(p.name for p in output.parent.iterdir() if p.is_file())
        assert len(outputs) == 1, f"a merge left {outputs}, not one file"

        streams = streams_in(ffmpeg[1], output)
        kinds = sorted(stream["codec_type"] for stream in streams)
        assert kinds == ["audio", "video"], (
            f"the merged file carries {kinds}. Two half-streams were chosen and the output must "
            "contain both; one of them means the merge did not happen"
        )
    finally:
        composition.shutdown.begin()
        assert spin(lambda: composition.shutdown.finished, timeout=120)


# --- T-112: the preview is the path (REQ-011, Phase 3's exit criterion) ------------------------


def test_the_previewed_path_is_the_path_the_download_actually_writes(
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
    named_media_url: Callable[[str], str],
) -> None:
    """**Phase 3's exit criterion for `T-112`**, and the only test that can establish it.

    *The preview matches the written path in every tested case, including titles with characters
    illegal on Windows.* Everything smaller — the field set, the containment, the widget — can be
    correct while the two answers still differ, because the thing under test is that they are the
    same two steps run twice rather than two implementations that agree today.

    Three deliberate choices in the setup:

    - **The MP3 preset**, because `REQ-011` as amended promises an *exact* path only where the
      request decides the container. A named audio codec does; a video download does not, and
      asserting equality against one would be asserting the amendment is wrong.
    - **A subfolder in the template**, so `REQ-011`'s *path* control is exercised and not only its
      filename control — the download has to create a directory that the preview named.
    - **A title carrying `:`, `?` and `"`**, which is the exit criterion's own wording. yt-dlp
      replaces them with fullwidth characters of its own during rendering, and `core/paths.py`
      would have replaced them with underscores. A preview that did its own substitution would
      show the underscores and the file would land under the fullwidth ones.

    Read from the **editor**, not from `manager.preview_output_path`: what the criterion is about
    is what the user was shown.
    """
    composition = application.compose(
        qapp,
        database=tmp_path / "queue.db",
        output_directory=tmp_path / "downloads",
        geometry_file=tmp_path / "window.toml",
    )
    # `UX-006`: a composed application opens with its queue stopped, so this presses Start.
    composition.manager.start_queue()
    try:
        url = named_media_url('A: Song? "Live".mp4')
        dialog = composition.window.open_add_dialog()
        names = [dialog._preset_choice.itemText(i) for i in range(dialog._preset_choice.count())]
        dialog._preset_choice.setCurrentIndex(names.index("Audio only (MP3)"))
        dialog._urls.setPlainText(url)
        dialog.resolve()
        assert spin(
            lambda: bool(dialog.rows) and all(row.committable for row in dialog.rows), timeout=60
        ), f"the URL never resolved: {dialog.status_text()}"

        row = dialog.rows[0]
        dialog.open_template_editor(row)
        qapp.processEvents()
        panel = dialog.open_template_panel
        assert panel is not None, "the template editor did not open"
        panel.editor.set_template("music/%(title)s.%(ext)s")
        panel.editor.template_changed.emit("music/%(title)s.%(ext)s")
        qapp.processEvents()

        previewed = panel.editor.preview_text()
        assert previewed, f"no path was previewed: {panel.editor.message_text()}"
        assert panel.editor.message_text() == "", (
            f"an MP3 conversion was presented as uncertain: {panel.editor.message_text()}"
        )
        assert previewed.endswith(".mp3"), previewed
        dialog.close_panel(keep=True)

        dialog.add_to_queue()
        assert spin(lambda: bool(dialog.queued_job_ids), timeout=30), dialog.status_text()
        job_id = dialog.queued_job_ids[0]
        dialog.close()

        assert spin(
            lambda: (
                (stored := composition.store.get(job_id)) is not None
                and stored.status is JobStatus.COMPLETED
            ),
            timeout=180,
        ), f"the download never completed — {why(composition, job_id)}"

        stored = composition.store.get(job_id)
        assert stored is not None and stored.output_path is not None
        written = Path(stored.output_path)

        assert written.exists(), f"the queue recorded {written} and nothing is there"
        assert str(written) == previewed, (
            f"the preview promised {previewed!r} and the download wrote {str(written)!r}"
        )
        assert written.parent == tmp_path / "downloads" / "music", (
            "the subfolder the template asked for was not created where the preview said"
        )
        assert not set(written.name) & set('<>:"/\\|?*'), (
            f"a character illegal on Windows survived into {written.name!r}"
        )
    finally:
        composition.shutdown.begin()
        assert spin(lambda: composition.shutdown.finished, timeout=120)


# --- T-113: a partial download survives a kill and is continued (REQ-017, UX-008) --------------


def test_a_killed_download_resumes_from_its_partial_rather_than_starting_again(
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
    resumable_media_url: Callable[..., tuple[str, list[tuple[str, int]]]],
) -> None:
    """**`T-113`'s first criterion**: *a real restart, verified by killing the process*.

    `ai/TESTING.md` §7's rule, and `NFR-003`'s: a `SIGKILL` to a separate interpreter mid-download,
    with no handlers and nothing flushed. A clean shutdown would prove that orderly teardown keeps
    a file, which is a different and much easier claim — and the whole mechanism here is that
    *nothing runs*: the staging directory survives because no code deleted it.

    **Three assertions, and each one fails on its own.** That the partial survived (the mechanism);
    that the second attempt asked for a **range** rather than the whole file (the resume actually
    happened, rather than a restart that also produced a correct file); and that the finished bytes
    are exactly right (the resume did not corrupt what it continued). The middle one is why the
    server here honours `Range` at all — `media_handler` advertises it and ignores it, under which
    yt-dlp discards the partial and starts over, correctly and invisibly.
    """
    database = tmp_path / "queue.db"
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    # Paced for `test_a_job_killed_mid_download_is_recovered_by_the_next_start`'s reason: the kill
    # has to land with the download genuinely in flight, or there is nothing partial to keep.
    url, requests = resumable_media_url(chunk_delay=0.5)

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

        def partial_size() -> int:
            """How much of this job's `.part` file exists, read from outside the application."""
            partial = worker.resumable_partial(downloads, job_id)
            return 0 if partial is None else partial.stat().st_size

        # Waited on the **file** rather than on the row's status: `RUNNING` is set when the session
        # starts and this test is about bytes on disk, so killing at `RUNNING` could land before
        # yt-dlp had written any and leave nothing to resume from.
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline and partial_size() <= 0:
            time.sleep(0.05)
        killed_at = partial_size()
        assert killed_at > 0, (
            "no partial file existed to kill mid-way through, so this test would prove nothing"
        )

        must_die = the_workers_that_must_die(application_pid)
        doomed = capture_the_doomed_tree(process, application_pid)
        kill_the_application(process, doomed)
        _, survivors = psutil.wait_procs(must_die, timeout=5)
        assert not survivors, (
            f"{len(survivors)} worker process(es) outlived the kill: "
            f"{sorted(p.pid for p in survivors)}"
        )
        process.wait(timeout=30)
    finally:
        if process.poll() is None:  # pragma: no cover - only on an unexpected path
            with contextlib.suppress(psutil.Error):
                for victim in [*psutil.Process(process.pid).children(recursive=True)][::-1]:
                    victim.kill()
            process.kill()
            process.wait(timeout=30)
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()

    survived = worker.resumable_partial(downloads, job_id)
    assert survived is not None and survived.stat().st_size > 0, (
        "the kill took the partial with it, so there is nothing for the next attempt to continue "
        "from — which is what `tempfile.mkdtemp` staging did before T-113"
    )
    before_resume = len(requests)

    composition = application.compose(
        qapp,
        database=database,
        output_directory=downloads,
        geometry_file=tmp_path / "window2.toml",
    )
    # `UX-006`: a composed application opens with its queue stopped, so this presses Start.
    composition.manager.start_queue()
    try:
        recovered = composition.store.get(job_id)
        assert recovered is not None and recovered.status is JobStatus.FAILED
        assert recovered.error_kind is ErrorKind.INTERRUPTED

        # The user's own Retry, which `UX-008` says *is* the resume: there is no separate verb,
        # because the difference is what the download does and not what the application asks for.
        composition.manager.retry(job_id)
        assert spin(
            lambda: (
                (stored := composition.store.get(job_id)) is not None
                and stored.status is JobStatus.COMPLETED
            ),
            timeout=180,
        ), f"the resumed download never completed — {why(composition, job_id)}"

        stored = composition.store.get(job_id)
        assert stored is not None and stored.output_path is not None
        written = Path(stored.output_path)
        assert written.read_bytes() == RESUMABLE_BYTES, (
            "the resumed download produced the wrong bytes — a resume that corrupts what it "
            "continued is worse than one that never happened"
        )

        resumed = requests[before_resume:]
        ranged = [offset for verb, offset in resumed if verb == "GET" and offset > 0]
        assert ranged, (
            f"the second attempt asked for the whole file again: {resumed}. The partial was there "
            "and yt-dlp was pointed somewhere else, which is a restart wearing a resume's clothes."
        )
        assert max(ranged) >= killed_at * 0.5, (
            f"resumed from byte {max(ranged)} having already written {killed_at}; the range asked "
            "for throws most of the partial away"
        )

        assert worker.resumable_partial(downloads, job_id) is None, (
            "the staging directory outlived a download that succeeded"
        )
    finally:
        composition.shutdown.begin()
        assert spin(lambda: composition.shutdown.finished, timeout=120)


def test_an_orderly_close_and_reopen_continues_the_download(
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
    resumable_media_url: Callable[..., tuple[str, list[tuple[str, int]]]],
) -> None:
    """**`T113-R2`**: closing the window is how a restart usually begins.

    The hard-kill proof above establishes that nothing running is what keeps the partial. This is
    the case where something *is* running: `shutdown()` cancels every occupant, and the cooperative
    worker path used to delete the partial while the manager wrote a terminal `CANCELLED` — so an
    application closed mid-download reopened with neither bytes to continue from nor a row offering
    to try again. `REQ-017` promises resumption **across restarts**, and this is the ordinary one.

    Everything the kill test asserts is asserted here too — the partial survived, the second
    attempt asked for a **range**, and the bytes are exact — because the failure mode is that an
    orderly close silently costs the head start a kill would have kept.

    Composed twice in one process rather than across two interpreters. The kill test needs a real
    `SIGKILL` and therefore a real second process; this one is about `shutdown()`, which is code
    that runs, so running it is the point.
    """
    database = tmp_path / "queue.db"
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    url, requests = resumable_media_url(chunk_delay=0.2)

    first = application.compose(
        qapp,
        database=database,
        output_directory=downloads,
        geometry_file=tmp_path / "window.toml",
    )
    # `UX-006`: a composed application opens with its queue stopped, so this presses Start.
    first.manager.start_queue()
    job_id = queue_one(first, url)

    def partial_size() -> int:
        found = worker.resumable_partial(downloads, job_id)
        return 0 if found is None else found.stat().st_size

    assert spin(lambda: partial_size() > 0, timeout=120), (
        "no bytes were ever written, so closing would prove nothing"
    )
    written_before = partial_size()

    # The application's own orderly close, the one the window's `closeEvent` reaches.
    first.shutdown.begin()
    assert spin(lambda: first.shutdown.finished, timeout=120), "the application never shut down"

    survived = worker.resumable_partial(downloads, job_id)
    assert survived is not None and survived.stat().st_size >= written_before, (
        "an orderly close threw away the bytes REQ-017 promises to continue from"
    )
    before_resume = len(requests)

    second = application.compose(
        qapp,
        database=database,
        output_directory=downloads,
        geometry_file=tmp_path / "window2.toml",
    )
    second.manager.start_queue()
    try:
        recovered = second.store.get(job_id)
        assert recovered is not None, "the job did not survive the close"
        assert recovered.status is not JobStatus.CANCELLED, (
            "the close wrote a terminal cancellation, so the next launch offers nothing back"
        )
        assert (
            recovered.status is JobStatus.FAILED and recovered.error_kind is ErrorKind.INTERRUPTED
        )

        second.manager.retry(job_id)
        assert spin(
            lambda: (
                (stored := second.store.get(job_id)) is not None
                and stored.status is JobStatus.COMPLETED
            ),
            timeout=180,
        ), f"the reopened download never completed — {why(second, job_id)}"

        stored = second.store.get(job_id)
        assert stored is not None and stored.output_path is not None
        assert Path(stored.output_path).read_bytes() == RESUMABLE_BYTES

        resumed = requests[before_resume:]
        ranged = [offset for verb, offset in resumed if verb == "GET" and offset > 0]
        assert ranged, (
            f"the reopened application fetched the whole file again: {resumed}. The partial was "
            "there and nothing continued from it."
        )
    finally:
        second.shutdown.begin()
        assert spin(lambda: second.shutdown.finished, timeout=120)
