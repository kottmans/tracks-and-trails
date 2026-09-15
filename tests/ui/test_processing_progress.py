"""What a queue row shows while its file is processed (`T-344`).

Reported by the maintainer: a long video took a long time to convert, and nothing said the
application was still working. Before this the row showed a full bar (the download's bytes, all
in), `Processing`, and nothing that moved.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QStyleOptionViewItem

from tests.ui.test_queue_view import FakeQueue, make_job, managers, queue, views  # noqa: F401
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.downloader.protocol import Progress, Stage
from tracks_and_trails.ui import row_delegate as row_delegate_module
from tracks_and_trails.ui.job_detail import format_bytes
from tracks_and_trails.ui.queue_view import (
    INDETERMINATE_TEXT,
    PROGRESS_COLUMN,
    SIZE_COLUMN,
    STATUS_COLUMN,
    QueueView,
)
from tracks_and_trails.ui.row_delegate import (
    BUSY_ROLE,
    PROGRESS_ROLE,
    STATE_CHIP_ROLE,
    STATE_ROLE,
    RowDelegate,
)


def _processing(
    queue: FakeQueue,  # noqa: F811
    managers: Callable[..., DownloadManager],  # noqa: F811
    views: Callable[..., QueueView],  # noqa: F811
    tmp_path: Path,
    *steps: Progress,
) -> QueueView:
    """A job that downloaded 1000 of 1000 bytes and is now processing, with `steps` drawn."""
    queue.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    view = views(jobs=queue, manager=managers(), repaint_interval_ms=10_000)
    view.model._on_progress(
        Progress(
            job_id="job-1", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=1000, total_bytes=1000
        )
    )
    view.model._draw_pending()
    queue.update(replace(queue.jobs["job-1"], status=JobStatus.POST_PROCESSING))
    view.model._on_job_changed("job-1", JobStatus.POST_PROCESSING.value)
    for step in steps:
        view.model._on_progress(step)
        view.model._draw_pending()
    return view


def _data(view: QueueView, role: int) -> object:
    return view.model.data(view.model.index(0, 0), role)


def test_a_step_with_a_position_shows_its_own_percentage_not_the_downloads(
    queue: FakeQueue,  # noqa: F811
    managers: Callable[..., DownloadManager],  # noqa: F811
    views: Callable[..., QueueView],  # noqa: F811
    tmp_path: Path,
) -> None:
    view = _processing(
        queue,
        managers,
        views,
        tmp_path,
        Progress(
            job_id="job-1",
            stage=Stage.POST_PROCESSING,
            step="ExtractAudio",
            step_fraction=0.42,
        ),
    )

    assert _data(view, PROGRESS_ROLE) == pytest.approx(0.42)
    assert _data(view, BUSY_ROLE) is False
    assert _data(view, STATE_CHIP_ROLE) == "Converting 42%", (
        "the chip does not say what the percentage is of (T-345)"
    )
    assert view.model.text_at("job-1", PROGRESS_COLUMN) == "42%"
    status = view.model.text_at("job-1", STATUS_COLUMN)
    assert status is not None and status.startswith("Converting to audio")
    accessible = view.model.data(
        view.model.index(0, PROGRESS_COLUMN), Qt.ItemDataRole.AccessibleTextRole
    )
    assert "Converting to audio" in accessible and "42 percent" in accessible
    size = view.model.text_at("job-1", SIZE_COLUMN)
    assert size == f"{format_bytes(1000)} of {format_bytes(1000)}", (
        f"the step's message, which counts no bytes, erased the downloaded size: {size!r}"
    )


def test_a_step_without_a_position_is_a_moving_bar_with_its_name_and_time_so_far(
    queue: FakeQueue,  # noqa: F811
    managers: Callable[..., DownloadManager],  # noqa: F811
    views: Callable[..., QueueView],  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**The report itself.** No full bar from the finished download; a bar that moves instead,
    the step in words, and the minutes it has taken, so a long conversion looks like work."""
    clock = [1000.0]
    monkeypatch.setattr(
        "tracks_and_trails.ui.queue_view.time", SimpleNamespace(monotonic=lambda: clock[0])
    )
    view = _processing(
        queue,
        managers,
        views,
        tmp_path,
        Progress(job_id="job-1", stage=Stage.POST_PROCESSING, step="VideoConvertor"),
    )

    assert _data(view, PROGRESS_ROLE) is None, "the finished download's full bar is still drawn"
    assert _data(view, BUSY_ROLE) is True
    assert _data(view, STATE_CHIP_ROLE) == "Converting"
    assert view.model.text_at("job-1", PROGRESS_COLUMN) == INDETERMINATE_TEXT
    assert view.model.text_at("job-1", STATUS_COLUMN) == "Converting the video · 0:00"

    clock[0] += 65
    assert _data(view, STATE_ROLE) == "Converting the video · 1:05"
    accessible = view.model.data(
        view.model.index(0, PROGRESS_COLUMN), Qt.ItemDataRole.AccessibleTextRole
    )
    assert "cannot be measured" in accessible
    assert view.model._busy.isActive(), "nothing will redraw the moving bar or the time"


def test_the_time_so_far_restarts_with_each_step(
    queue: FakeQueue,  # noqa: F811
    managers: Callable[..., DownloadManager],  # noqa: F811
    views: Callable[..., QueueView],  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [1000.0]
    monkeypatch.setattr(
        "tracks_and_trails.ui.queue_view.time", SimpleNamespace(monotonic=lambda: clock[0])
    )
    view = _processing(
        queue,
        managers,
        views,
        tmp_path,
        Progress(job_id="job-1", stage=Stage.MERGING, step="Merger", step_fraction=0.9),
    )
    clock[0] += 30
    view.model._on_progress(
        Progress(job_id="job-1", stage=Stage.MERGING, step="Merger", step_fraction=1.0)
    )
    view.model._draw_pending()
    assert view.model.text_at("job-1", STATUS_COLUMN) == "Joining video and audio · 0:30"

    view.model._on_progress(
        Progress(job_id="job-1", stage=Stage.POST_PROCESSING, step="EmbedThumbnail")
    )
    view.model._draw_pending()
    assert view.model.text_at("job-1", STATUS_COLUMN) == "Adding the thumbnail · 0:00"


def test_a_step_with_no_words_of_its_own_is_shown_as_its_stage(
    queue: FakeQueue,  # noqa: F811
    managers: Callable[..., DownloadManager],  # noqa: F811
    views: Callable[..., QueueView],  # noqa: F811
    tmp_path: Path,
) -> None:
    view = _processing(
        queue,
        managers,
        views,
        tmp_path,
        Progress(job_id="job-1", stage=Stage.POST_PROCESSING, step="SomeFutureStep"),
    )

    status = view.model.text_at("job-1", STATUS_COLUMN)
    assert status is not None and status.startswith("Post-processing")


def test_the_redraw_timer_stops_once_nothing_is_processing(
    queue: FakeQueue,  # noqa: F811
    managers: Callable[..., DownloadManager],  # noqa: F811
    views: Callable[..., QueueView],  # noqa: F811
    tmp_path: Path,
) -> None:
    view = _processing(
        queue,
        managers,
        views,
        tmp_path,
        Progress(job_id="job-1", stage=Stage.POST_PROCESSING, step="ExtractAudio"),
    )
    assert view.model._busy.isActive()

    queue.update(replace(queue.jobs["job-1"], status=JobStatus.COMPLETED))
    view.model._on_job_changed("job-1", JobStatus.COMPLETED.value)
    view.model._tick_busy()

    assert not view.model._busy.isActive(), "the timer kept redrawing a finished queue"
    assert _data(view, BUSY_ROLE) is False


def test_the_moving_bar_is_drawn_and_moves() -> None:
    """The delegate's half: a block on the track, in a different place a moment later."""
    colour = QColor("#224466")

    def frame(now: float) -> QImage:
        image = QImage(200, 4, QImage.Format.Format_ARGB32)
        image.fill(QColor("white"))
        painter = QPainter(image)
        try:
            RowDelegate._paint_busy(painter, image.rect(), colour, now)
        finally:
            painter.end()
        return image

    def solid(image: QImage) -> list[int]:
        return [x for x in range(image.width()) if image.pixelColor(x, 1) == colour]

    first = solid(frame(10.0))
    later = solid(frame(10.0 + row_delegate_module.BUSY_PERIOD / 2))

    assert first, "no block was drawn"
    assert later, "no block was drawn half a period later"
    assert first != later, "the block did not move"
    assert len(first) <= int(200 * row_delegate_module.BUSY_SHARE)


def test_a_busy_row_paints_the_moving_bar_through_the_real_delegate(
    queue: FakeQueue,  # noqa: F811
    managers: Callable[..., DownloadManager],  # noqa: F811
    views: Callable[..., QueueView],  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Routed, not only drawable: the view's own delegate asks `BUSY_ROLE` and calls the paint."""
    view = _processing(
        queue,
        managers,
        views,
        tmp_path,
        Progress(job_id="job-1", stage=Stage.POST_PROCESSING, step="VideoConvertor"),
    )
    calls: list[float] = []
    monkeypatch.setattr(
        RowDelegate, "_paint_busy", staticmethod(lambda _p, _bar, _c, now: calls.append(now))
    )
    delegate = view.table.itemDelegate()
    assert isinstance(delegate, RowDelegate)
    index = view.model.index(0, 0)
    option = QStyleOptionViewItem()
    option.rect = view.table.visualRect(index)
    option.rect.setWidth(max(option.rect.width(), 900))
    option.rect.setHeight(max(option.rect.height(), delegate.sizeHint(option, index).height()))
    image = QImage(option.rect.width() + 10, option.rect.height() + 10, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        delegate.paint(painter, option, index)
    finally:
        painter.end()

    assert calls, "the delegate never drew the moving bar for a busy row"


#: yt-dlp steps that do no ffmpeg work worth naming: they edit fields or run the user's command,
#: and finish in a moment. Stated here so a new step is a decision, not a silent default.
_QUIET_STEPS = frozenset(
    {
        "Exec",
        "ExecAfterDownload",
        "MetadataFromField",
        "MetadataFromTitle",
        "MetadataParser",
        "XAttrMetadata",
    }
)


def test_every_step_yt_dlp_can_report_has_words_or_is_named_as_quiet() -> None:
    """**By the names yt-dlp's hook actually reports** (`PostProcessor.pp_key`).

    The first version keyed the words by class name (`FFmpegExtractAudio`), and the hook reports
    `ExtractAudio`: no step would ever have been named, and only a real download showed it.
    """
    import yt_dlp.postprocessor as postprocessors

    from tracks_and_trails.ui.queue_view import STEP_TEXT

    reported = {
        getattr(postprocessors, name).pp_key()
        for name in dir(postprocessors)
        if name.endswith("PP") and hasattr(getattr(postprocessors, name), "pp_key")
    }

    assert reported, "yt-dlp exposed no post-processors, so this checks nothing"
    unnamed = reported - set(STEP_TEXT) - _QUIET_STEPS
    assert not unnamed, f"steps yt-dlp can report with no words on the row: {sorted(unnamed)}"
    assert not set(STEP_TEXT) - reported, (
        f"words for steps yt-dlp does not report: {sorted(set(STEP_TEXT) - reported)}"
    )


def test_every_step_with_words_has_a_word_for_the_chip() -> None:
    """`T-345`: the chip names what is happening beside its percentage, for every named step."""
    from tracks_and_trails.ui.queue_view import STEP_CHIP_TEXT, STEP_TEXT

    assert set(STEP_CHIP_TEXT) == set(STEP_TEXT)


@pytest.mark.parametrize(
    ("status", "message", "chip"),
    [
        (
            JobStatus.RUNNING,
            Progress(
                job_id="job-1",
                stage=Stage.DOWNLOADING_AUDIO,
                downloaded_bytes=500,
                total_bytes=1000,
            ),
            "Downloading 50%",
        ),
        (
            JobStatus.POST_PROCESSING,
            Progress(job_id="job-1", stage=Stage.MERGING, step="Merger", step_fraction=0.4),
            "Joining 40%",
        ),
        (
            JobStatus.POST_PROCESSING,
            Progress(job_id="job-1", stage=Stage.POST_PROCESSING, step="SomeFutureStep"),
            "Processing",
        ),
    ],
    ids=["downloading", "joining", "unnamed-step"],
)
def test_the_chip_says_what_the_percentage_is_of(
    queue: FakeQueue,  # noqa: F811
    managers: Callable[..., DownloadManager],  # noqa: F811
    views: Callable[..., QueueView],  # noqa: F811
    tmp_path: Path,
    status: JobStatus,
    message: Progress,
    chip: str,
) -> None:
    """Reported by the maintainer (`T-345`): a chip reading `86%` did not say whether that was the
    download or the conversion, and the words on the second line are cut off on a narrow window."""
    queue.add(make_job("job-1", tmp_path, status=status))
    view = views(jobs=queue, manager=managers(), repaint_interval_ms=10_000)
    view.model._on_progress(message)
    view.model._draw_pending()

    assert _data(view, STATE_CHIP_ROLE) == chip
