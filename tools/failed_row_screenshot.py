"""Render the queue's failed rows to PNG, through the real model and delegate (`T201-R3`).

**Why this exists.** `T201-R3` was a layout ruling, and the round that raised it could only render
what was built and what one rejected option would cost — `ai/evidence/README.md` records that
option B and option C *"are not rendered"*. Option C is built now, so the thing the maintainer
ruled on is a thing anyone can look at, and this is how they look at it.

**A tool rather than a test**, on `tools/settings_screenshots.py`'s precedent and for its reason:
`ai/evidence/` keeps one dated capture of one head, and a committed generator is what gets the
*current* rows back. The programmatic gates for the same four cases live in
`tests/ui/test_queue_view.py`; nothing here verifies anything.

**Offscreen, so it says nothing about a real display.** `T-221` is this project's record of a
transient no offscreen grab can see.

    python tools/failed_row_screenshot.py ai/evidence 2026-08-14-T201-next-step-option-c

Writes `<prefix>.png` and prints, per row, the height the delegate gave it and whether it carries
an action line — the measurement the ruling turns on, which is that only the rows with something
to say pay for one.
"""

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QRect, Signal
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication, QStyleOptionViewItem

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import DownloadRequest, Job
from tracks_and_trails.downloader.manager import AUTOMATIC_RETRY_LIMIT
from tracks_and_trails.ui import theme as ui_theme
from tracks_and_trails.ui.queue_view import JOB_COLUMN, QueueModel
from tracks_and_trails.ui.row_delegate import ACTION_ROLE, RowDelegate

#: The width `T201-R3`'s own measurement was taken at, so the picture and the finding agree.
WIDTH = 1180

#: The four cases the correction boundary names, each with a real yt-dlp sentence behind it.
#:
#: They are the four states the ruling has to hold at once: a failure with an honest step, one with
#: none, the network failure whose step changes when the automatic attempts run out, and the long
#: diagnostic whose own remedy is what option A would have elided.
CASES: list[tuple[str, ErrorKind, str, int]] = [
    (
        "Ridgeline in 4K — actionable",
        ErrorKind.FFMPEG_MISSING,
        "ERROR: You have requested merging of multiple formats but ffmpeg is not "
        "installed; pass its location with --ffmpeg-location",
        0,
    ),
    (
        "Live from the summit — nothing to suggest",
        ErrorKind.DRM_PROTECTED,
        "ERROR: This video is DRM protected",
        0,
    ),
    (
        "Trail notes, part two — retrying",
        ErrorKind.NETWORK,
        "ERROR: unable to download video data: <urlopen error timed out>",
        0,
    ),
    (
        "Trail notes, part two — retries spent",
        ErrorKind.NETWORK,
        "ERROR: unable to download video data: <urlopen error timed out>",
        AUTOMATIC_RETRY_LIMIT,
    ),
]


class Rows:
    """The `QueueReader` the model reads, holding the four jobs and nothing else."""

    def __init__(self, jobs: list[Job]) -> None:
        self._jobs = jobs

    def all_jobs(self) -> list[Job]:
        return list(self._jobs)

    def get(self, job_id: str) -> Job | None:
        return next((job for job in self._jobs if job.id == job_id), None)


class Stopped(QObject):
    """A stopped manager: the signals `QueueModel` connects to, and nothing behind them.

    The real `DownloadManager` would spawn a pool and open a database for a picture of four rows
    that will never move. What the model needs of one is these six signals and `is_running`, and a
    stopped queue is the state a failed row is looked at in anyway.
    """

    progress = Signal(object)
    job_changed = Signal(str, str)
    job_removed = Signal(str)
    queue_reordered = Signal()
    queue_cleared = Signal()
    queue_running = Signal(bool)

    is_running = False


def a_job(index: int, title: str, kind: ErrorKind, message: str, attempts: int) -> Job:
    return Job(
        id=f"job-{index}",
        url="https://example.invalid/watch",
        request=DownloadRequest(
            url="https://example.invalid/watch",
            output_directory="/tmp",  # noqa: S108 - never written; nothing here downloads
            format_selector="bestvideo+bestaudio/best",
            output_template="%(title)s.%(ext)s",
        ),
        created_at=datetime.now(UTC),
        queue_position=index,
        title=title,
        uploader="Summit Films",
        duration_seconds=252,
        status=JobStatus.FAILED,
        error_kind=kind,
        error_message=message,
        attempts=attempts,
    )


def main() -> int:
    directory = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    prefix = sys.argv[2] if len(sys.argv) > 2 else "failed-rows"
    directory.mkdir(parents=True, exist_ok=True)

    app = QApplication([])
    ui_theme.apply(app, ui_theme.THEMES["light"])
    jobs = [a_job(index, *case) for index, case in enumerate(CASES)]
    model = QueueModel(jobs=Rows(jobs), manager=Stopped())
    model.refresh()
    delegate = RowDelegate()

    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, WIDTH, 0)
    option.palette = app.palette()
    heights = [
        delegate.sizeHint(option, model.index(row, JOB_COLUMN)).height()
        for row in range(model.rowCount())
    ]

    image = QImage(WIDTH, sum(heights), QImage.Format.Format_ARGB32)
    image.fill(app.palette().base().color())
    painter = QPainter(image)
    try:
        top = 0
        for row, height in enumerate(heights):
            index = model.index(row, JOB_COLUMN)
            option.rect = QRect(0, top, WIDTH, height)
            delegate.paint(painter, option, index)
            action = model.data(index, ACTION_ROLE)
            print(f"row {row}  {height}px  action={action!r}")
            top += height
    finally:
        painter.end()

    target = directory / f"{prefix}.png"
    image.save(str(target))
    print(f"{target}  {WIDTH}x{sum(heights)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
