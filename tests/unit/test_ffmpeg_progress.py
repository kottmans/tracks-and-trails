"""ffmpeg's position during yt-dlp's post-processing steps (`T-344`).

What `ytdlp_adapter.ffmpeg_progress` and its helpers do.

Reported by the maintainer: a long video took a long time to convert and nothing on screen said the
application was still working. yt-dlp reports only *started* and *finished* for a step, so the
position comes from ffmpeg itself.
"""

from __future__ import annotations

import subprocess
import sys
import time
import types
from pathlib import Path
from typing import Any, ClassVar

import pytest

from tests.capabilities import ffmpeg  # noqa: F401 (the fixture)
from tracks_and_trails.downloader import ytdlp_adapter as adapter

#: A stand-in ffmpeg: progress blocks on standard output, an error on standard error, exit 3.
_FAKE_FFMPEG = r"""
import sys, time
print("frame=10\nout_time_us=1000000\nout_time_ms=1000000\nprogress=continue", flush=True)
print("out_time_us=2500000\nprogress=continue", flush=True)
if "--linger" in sys.argv:
    time.sleep(60)
print("out_time_us=4000000\nprogress=end", flush=True)
sys.stderr.write("Stream mapping\nthe last line of the error\n")
sys.exit(3)
"""


class _RecordingPopen(subprocess.Popen[str]):
    """Records the command it was given, and runs the stand-in ffmpeg instead of it."""

    commands: ClassVar[list[list[str]]] = []
    started: ClassVar[list[subprocess.Popen[str]]] = []

    def __init__(self, args: list[str], **kwargs: Any) -> None:
        type(self).commands.append(list(args))
        extra = ["--linger"] if "--linger" in args else []
        super().__init__([sys.executable, "-c", _FAKE_FFMPEG, *extra], **kwargs)
        type(self).started.append(self)


@pytest.fixture(autouse=True)
def _fresh_recorder() -> None:
    _RecordingPopen.commands = []
    _RecordingPopen.started = []


def test_a_step_command_is_the_one_carrying_yt_dlps_log_level() -> None:
    assert adapter.is_step_command(["ffmpeg", "-y", "-loglevel", "repeat+info", "-i", "in"])
    assert not adapter.is_step_command(["ffmpeg", "-version"])
    assert not adapter.is_step_command(["ffprobe", "-show_streams", "in"])
    assert not adapter.is_step_command("ffmpeg -loglevel repeat+info")


def test_progress_is_asked_for_straight_after_the_executable() -> None:
    command = ["/usr/bin/ffmpeg", "-y", "-loglevel", "repeat+info", "-i", "in.webm", "out.mp3"]

    changed = adapter.with_progress_arguments(command)

    assert changed[0] == "/usr/bin/ffmpeg"
    assert changed[1:4] == ["-progress", "pipe:1", "-nostats"]
    assert changed[4:] == command[1:]


@pytest.mark.parametrize(
    ("line", "seconds"),
    [
        ("out_time_us=2500000\n", 2.5),
        ("out_time_ms=2500000", 2.5),
        ("out_time=00:00:02.500000", None),
        ("out_time_us=N/A", None),
        ("progress=end", None),
        ("", None),
    ],
)
def test_the_position_is_read_in_seconds_from_either_microsecond_key(
    line: str, seconds: float | None
) -> None:
    """`out_time_ms` is microseconds too; ffmpeg misnamed it and kept the name."""
    assert adapter.position_in(line) == seconds


def test_a_reported_run_returns_what_yt_dlp_reads_and_reports_each_position() -> None:
    """The shape `Popen.run` returns, so `real_run_ffmpeg` reads the exit code and the last error
    line exactly as before; and every position, in order."""
    positions: list[float] = []
    command = ["ffmpeg", "-y", "-loglevel", "repeat+info", "-i", "in", "out"]

    stdout, stderr, code = adapter.run_reporting_position(
        _RecordingPopen,
        command,
        {"text": True, "stdin": subprocess.PIPE, "timeout": None},
        positions.append,
    )

    assert positions == [1.0, 1.0, 2.5, 4.0]
    assert code == 3
    assert stderr.strip().splitlines()[-1] == "the last line of the error"
    assert "progress=end" in stdout
    assert _RecordingPopen.commands[0][1:4] == ["-progress", "pipe:1", "-nostats"]


def test_a_position_callback_that_raises_kills_ffmpeg_before_the_exception_goes_on() -> None:
    """The worker's cancellation check raises from the callback; no ffmpeg may be left running."""

    class CancelledError(Exception):
        pass

    def cancel(_seconds: float) -> None:
        raise CancelledError

    command = ["ffmpeg", "-loglevel", "repeat+info", "--linger", "out"]
    started = time.monotonic()
    with pytest.raises(CancelledError):
        adapter.run_reporting_position(_RecordingPopen, command, {"text": True}, cancel)

    assert time.monotonic() - started < 30, "the lingering process was waited for, not killed"
    assert _RecordingPopen.started[0].poll() is not None, "ffmpeg was left running"


def test_a_yt_dlp_without_the_module_is_left_alone() -> None:
    """A future yt-dlp that moves its ffmpeg module: nothing installed, and the row falls back."""
    elsewhere = types.SimpleNamespace(__name__="json")

    with adapter.ffmpeg_progress(elsewhere, lambda _seconds: None) as installed:
        assert installed is False


def test_a_real_conversion_reports_its_position_and_yt_dlp_is_restored(
    ffmpeg: tuple[str, str],  # noqa: F811 (the fixture)
    tmp_path: Path,
) -> None:
    """**yt-dlp's own audio conversion, on a real file, through real ffmpeg.** The positions reach
    the end of the file, the output is written, and only step commands are changed: a `-version`
    call inside the same context reports nothing."""
    import yt_dlp
    import yt_dlp.postprocessor.ffmpeg as ffmpeg_module
    from yt_dlp.postprocessor import FFmpegExtractAudioPP

    executable, _ = ffmpeg
    source = tmp_path / "clip.mp4"
    subprocess.run(
        [
            executable,
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=6",
            "-c:a",
            "aac",
            str(source),
        ],
        check=True,
    )
    original = ffmpeg_module.Popen
    positions: list[float] = []

    with adapter.ffmpeg_progress(yt_dlp, positions.append) as installed:
        assert installed is True
        ffmpeg_module.Popen.run([executable, "-version"], stdout=subprocess.PIPE, text=True)
        assert positions == [], "a command that is not a step reported a position"
        ydl = yt_dlp.YoutubeDL({"quiet": True, "ffmpeg_location": str(Path(executable).parent)})
        step = FFmpegExtractAudioPP(ydl, preferredcodec="mp3")
        _, info = step.run(
            {"filepath": str(source), "ext": "mp4", "duration": 6, "__files_to_move": {}}
        )

    assert Path(info["filepath"]).is_file()
    assert positions, "the conversion reported no position"
    assert positions == sorted(positions)
    assert positions[-1] == pytest.approx(6, abs=0.5)
    assert ffmpeg_module.Popen is original, "yt-dlp's Popen was not put back"
