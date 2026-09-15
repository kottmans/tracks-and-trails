"""The worker's half of a post-processing step's progress (`T-344`).

`ytdlp_adapter.ffmpeg_progress` reads ffmpeg's position; `_Reporter` turns it, and yt-dlp's
*started* hook, into `Progress` messages the queue row draws.
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.downloader import worker
from tracks_and_trails.downloader.protocol import Progress, Stage


class _Sink:
    def __init__(self) -> None:
        self.messages: list[Any] = []

    def put(self, item: Any, /) -> None:
        self.messages.append(item)


def _started(reporter: worker._Reporter, name: str, duration: object) -> None:
    reporter.postprocessor_hook(
        {"status": "started", "postprocessor": name, "info_dict": {"duration": duration}}
    )


def test_a_started_step_is_announced_by_name() -> None:
    sink = _Sink()
    reporter = worker._Reporter("job-1", sink)

    _started(reporter, "ExtractAudio", 120)

    assert sink.messages == [
        Progress(job_id="job-1", stage=Stage.POST_PROCESSING, step="ExtractAudio")
    ]


def test_ffmpegs_position_is_a_fraction_of_the_medias_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Halfway through a 120-second file is 0.5; and positions are sent at most every
    `STEP_PROGRESS_INTERVAL`, because ffmpeg reports faster than anyone reads."""
    clock = [100.0]
    # The module's own `time`, replaced, rather than `time.monotonic` for the whole process.
    monkeypatch.setattr(
        "tracks_and_trails.downloader.worker.time", SimpleNamespace(monotonic=lambda: clock[0])
    )
    sink = _Sink()
    reporter = worker._Reporter("job-1", sink)
    _started(reporter, "Merger", 120)
    sink.messages.clear()

    reporter.ffmpeg_position(60)
    reporter.ffmpeg_position(61)  # the same instant: throttled
    clock[0] += worker.STEP_PROGRESS_INTERVAL
    reporter.ffmpeg_position(240)  # past the end: bounded

    assert [(m.step, m.step_fraction) for m in sink.messages] == [
        ("Merger", 0.5),
        ("Merger", 1.0),
    ]
    assert all(m.stage is Stage.MERGING for m in sink.messages)


@pytest.mark.parametrize("duration", [None, 0, "unknown"])
def test_without_a_length_the_position_says_the_step_is_running_and_no_more(
    duration: object,
) -> None:
    """No fraction invented: the row shows a moving bar and the time so far instead."""
    sink = _Sink()
    reporter = worker._Reporter("job-1", sink)
    _started(reporter, "VideoConvertor", duration)
    sink.messages.clear()

    reporter.ffmpeg_position(30)

    assert len(sink.messages) == 1
    assert sink.messages[0].step == "VideoConvertor"
    assert sink.messages[0].step_fraction is None


def test_a_cancelled_session_stops_at_ffmpegs_next_position() -> None:
    """Checked outside the hook's guard, as in the other hooks: a conversion that runs for
    minutes stops when asked, and the adapter kills ffmpeg on the way out."""
    cancel = threading.Event()
    reporter = worker._Reporter("job-1", _Sink(), cancel)
    _started(reporter, "ExtractAudio", 120)
    cancel.set()

    with pytest.raises(worker.SessionCancelledError):
        reporter.ffmpeg_position(10)


class _Adapter:
    def __init__(self) -> None:
        self.entered: list[object] = []

    def build_options(self, *_args: object, **_options: object) -> dict[str, object]:
        return {}

    @contextlib.contextmanager
    def ffmpeg_progress(self, module: object, on_position: object) -> Iterator[bool]:
        self.entered.append(on_position)
        yield True


class _Ydl:
    def __init__(self, _options: object) -> None: ...

    def __enter__(self) -> _Ydl:
        return self

    def __exit__(self, *_: object) -> None: ...

    def extract_info(self, *_: object, **__: object) -> dict[str, object]:
        return {}


class _Resolved:
    module = type("_Module", (), {"YoutubeDL": _Ydl, "__name__": "yt_dlp"})


@pytest.mark.parametrize("probe_only", [False, True], ids=["download", "probe"])
def test_positions_are_read_for_a_download_and_never_for_a_probe(probe_only: bool) -> None:
    """A probe runs no step, and stand-in adapters built for probes do not offer the hook."""
    adapter = _Adapter()
    reporter = worker._Reporter("job-1", _Sink())
    request = DownloadRequest(
        url="https://example.invalid/v",
        output_directory=str(Path.home()),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )

    worker._extract(
        adapter,
        request,
        _Resolved(),  # type: ignore[arg-type]
        reporter,
        probe_only=probe_only,
    )

    assert adapter.entered == ([] if probe_only else [reporter.ffmpeg_position])
