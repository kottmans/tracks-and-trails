"""The single-job progress view (`T-017`, `REQ-014`, `REQ-015`, `REQ-018`).

Driven by **real `T-011` messages** wherever the claim is about what a user sees during a
download: a crafted child sends the stages over a real queue, through a real `ResultPump`, into a
real `DownloadManager`. A simulated sequence of `Progress` objects handed straight to the widget
would prove that the widget can render a list, which is not the acceptance criterion.

The two places a constructed message is used instead are stated where they appear, and both are
about *rate* rather than about content: a real worker cannot be asked to emit two hundred
messages inside one repaint interval on demand.
"""

import time
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import pytest
from PySide6.QtCore import QMetaMethod, QObject, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QPushButton, QWidget

from tests.qt_lifecycle import drain
from tracks_and_trails.core.errors import ErrorKind, is_retryable
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import DownloadRequest, Job
from tracks_and_trails.downloader.manager import CANCEL_BUDGET_SECONDS, DownloadManager
from tracks_and_trails.downloader.protocol import (
    Failed,
    Progress,
    SessionKind,
    Stage,
    Succeeded,
    WorkerFinished,
)
from tracks_and_trails.ui.job_detail import (
    CANCELLED_TEXT,
    STAGE_TEXT,
    UNKNOWN_TEXT,
    JobProgressView,
    build_progress_view,
    format_bytes,
    format_speed,
)

# --- a store the view can read ---------------------------------------------------------------


class FakeStore:
    """An in-memory `JobStore` and `JobReader` at once, and a log of every write in order."""

    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.writes: list[tuple[str, JobStatus]] = []

    def add(self, job: Job) -> None:
        self.jobs[job.id] = job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def update(self, job: Job, done: Callable[[str | None], None] | None = None) -> None:
        self.jobs[job.id] = job
        self.writes.append((job.id, job.status))
        if done is not None:
            done(None)

    def statuses(self, job_id: str) -> list[JobStatus]:
        return [status for stored_id, status in self.writes if stored_id == job_id]

    def requeue_at_end(self, job: Any, done: Any) -> None:
        """Part of `JobStore` since `T-080`. Unused here; present so the fake satisfies it."""
        raise NotImplementedError

    def remove(self, job_id: str, done: Any) -> None:
        """Part of `JobStore` since `T-080`. Unused here; present so the fake satisfies it."""
        raise NotImplementedError

    def reorder(self, job_ids: Any, done: Any) -> None:
        """Part of `JobStore` since `T-081`. Unused here; present so the fake satisfies it."""
        raise NotImplementedError

    def clear_completed(self, done: Any) -> None:
        """Part of `JobStore` since `T-081`. Unused here; present so the fake satisfies it."""
        raise NotImplementedError


def make_job(job_id: str, directory: Path, **overrides: Any) -> Job:
    job = Job(
        id=job_id,
        url="https://example.invalid/watch",
        request=DownloadRequest(
            url="https://example.invalid/watch",
            output_directory=str(directory),
            format_selector="best",
            output_template="%(title)s.%(ext)s",
        ),
        created_at=datetime.now(UTC),
        queue_position=0,
    )
    return replace(job, **overrides) if overrides else job


# --- children that send real messages ---------------------------------------------------------


def child_walking_every_stage(
    _kind: SessionKind, job_id: str, _request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Every stage `REQ-014` names, then a success. The criterion is that all five are shown.

    Paced deliberately: see the sleep below. A widget that coalesces cannot promise to render a
    stage that was already stale when its turn came, so a test asserting every stage must give
    each one long enough to have a turn.
    """
    for index, stage in enumerate(
        (
            Stage.PROBING,
            Stage.DOWNLOADING_VIDEO,
            Stage.DOWNLOADING_AUDIO,
            Stage.MERGING,
            Stage.POST_PROCESSING,
        )
    ):
        queue.put(
            Progress(
                job_id=job_id,
                stage=stage,
                downloaded_bytes=(index + 1) * 1024,
                total_bytes=5 * 1024,
                speed_bytes_per_second=2048.0,
                eta_seconds=5 - index,
            )
        )
        # **Each stage has to outlive a repaint interval to be seen at all** (`T-062`). This slept
        # 0.02 s, and the test failed on `windows-latest` with "these stages were never displayed:
        # ['Downloading video']" while passing everywhere else. That is not a Windows defect — it
        # is coalescing working: the widget draws the *newest* message, so a stage superseded
        # before the timer fires is never rendered, and Qt's default timer granularity there is
        # ~15 ms against the 1 ms this test asks for.
        #
        # A tenth of a second outlives a repaint interval on both platforms, which is the property
        # that matters: it makes the assertion about the *rendering path* rather than about winning
        # a race with the timer. (This said "a hundred times faster than a human reads" until
        # `T062-R1` — a number nothing here measures.)
        time.sleep(0.15)
    # Post-processing takes a moment in reality, and it has to here too: without it the success
    # arrives in the same instant as the last stage, and "the user never saw post-processing"
    # would be a fact about this child rather than about the widget.
    time.sleep(0.05)
    queue.put(Succeeded(job_id=job_id, output_path="out.mp4", total_bytes=5 * 1024))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))


#: The two failure messages the children below report, kept where the tests can compare against
#: them character for character (`NFR-006`).
NETWORK_MESSAGE: Final = (
    "ERROR: [generic] None: Unable to download webpage: <urlopen error timed out>"
)
DRM_MESSAGE: Final = "This video is DRM protected."


def child_failing_as_network(
    _kind: SessionKind, job_id: str, _request: DownloadRequest, queue: Any, **_: Any
) -> None:
    queue.put(Failed(job_id=job_id, kind=ErrorKind.NETWORK, message=NETWORK_MESSAGE))
    queue.put(WorkerFinished(job_id=job_id, exit_code=1))


def child_failing_as_drm(
    _kind: SessionKind, job_id: str, _request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """A module-level function, not a closure over the kind.

    `ARC-002` spawns rather than forks on every platform, so the entry point is **pickled** to
    reach the child. A nested function is not picklable, and the failure is silent in the worst
    way: the spawn fails, `_abort_start` reports `WORKER_CRASH`, and a test asserting on DRM
    quietly asserts on a start failure instead.
    """
    queue.put(Failed(job_id=job_id, kind=ErrorKind.DRM_PROTECTED, message=DRM_MESSAGE))
    queue.put(WorkerFinished(job_id=job_id, exit_code=1))


def child_downloading_forever(
    _kind: SessionKind, job_id: str, _request: DownloadRequest, queue: Any, **kwargs: Any
) -> None:
    """Reports bytes moving until it is stopped, so a cancel has something real to stop."""
    cancel = kwargs.get("cancel")
    sent = 0
    while cancel is None or not cancel.is_set():
        sent += 1024
        queue.put(
            Progress(
                job_id=job_id, stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=sent, total_bytes=0
            )
        )
        time.sleep(0.02)
    queue.put(Failed(job_id=job_id, kind=ErrorKind.CANCELLED, message="Stopped on request."))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))


# --- fixtures ---------------------------------------------------------------------------------


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def managers(store: FakeStore, qapp: QApplication) -> Iterator[Callable[..., DownloadManager]]:
    built: list[DownloadManager] = []

    def build(**overrides: Any) -> DownloadManager:
        manager = DownloadManager(store, **overrides)
        manager.start_queue()
        built.append(manager)
        return manager

    yield build

    for manager in built:
        manager.shutdown()
    # Waits for the poll timer as well as the work — see `tests/qt_lifecycle.py` and `T-128`.
    drain(qapp, built)


@pytest.fixture
def views(qapp: QApplication) -> Iterator[Callable[..., JobProgressView]]:
    built: list[JobProgressView] = []

    def build(**kwargs: Any) -> JobProgressView:
        view = JobProgressView(**kwargs)
        built.append(view)
        return view

    yield build

    for view in built:
        view.close()
        view.deleteLater()
    qapp.processEvents()


def button(view: JobProgressView, name: str) -> QPushButton:
    found = view.findChild(QPushButton, name)
    assert found is not None, f"no QPushButton named {name!r}"
    return found


# --- 1. every stage `REQ-014` names -----------------------------------------------------------


def test_every_stage_req_014_names_is_shown_from_real_messages(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    spin: Callable[..., bool],
) -> None:
    """The first acceptance criterion, driven end to end.

    A real child sends all five stages over a real queue; the manager routes them; the view
    renders them. What is asserted is the *text a user reads*, collected as it changes, because
    a stage that is computed and never displayed is the defect class this project has now met
    five times (`ai/STATUS.md`).
    """
    job = make_job("job-1", tmp_path)
    store.add(job)
    manager = managers(entry_point=child_walking_every_stage)
    view = views(manager=manager, jobs=store, job_id="job-1", repaint_interval_ms=1)
    seen: list[str] = []

    def sample() -> bool:
        # Sampled from the widget as the event loop turns, which is what a user reads. Sampling
        # inside the `progress` slot instead would read the label one repaint *behind* the
        # message that had just arrived, and report stages as missing that were shown.
        seen.append(view.stage_text())
        return store.statuses("job-1")[-1:] == [JobStatus.COMPLETED]

    manager.start("job-1")
    assert spin(sample, timeout=60), f"the job never completed: {store.statuses('job-1')}"

    shown = set(seen)
    missing = set(STAGE_TEXT.values()) - shown
    assert not missing, f"these stages were never displayed: {sorted(missing)}"


def test_every_stage_the_protocol_can_report_has_words_to_show() -> None:
    """`STAGE_TEXT` is complete, checked against `Stage` itself.

    Completeness is the one thing that may be derived from the enum — the *strings* are still
    transcribed from `REQ-014` by hand, and this asserts only that none is missing. It is here
    because a gap is invisible at runtime: `_show_progress` falls back to the job's status text,
    and for post-processing the two happen to read the same, so dropping the entry changed
    nothing a user or a test could see.
    """
    missing = set(Stage) - set(STAGE_TEXT)
    assert not missing, f"these stages would fall back to a status word: {sorted(missing)}"


# --- 2. the event loop under a burst ----------------------------------------------------------


def test_a_burst_of_progress_is_coalesced_to_the_stated_repaint_rate(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """The measurable half of `NFR-001` for this widget.

    "Does not visibly stutter" is not testable, so the contract is a stated rate: at most one
    repaint per `REPAINT_INTERVAL_MS`, and the repaint shows the **newest** message. A
    per-message repaint — the obvious naive implementation, and the one that degrades exactly
    when a download is fastest — fails this by drawing all two hundred.

    Constructed messages rather than a worker: the claim is about arrival *rate*, and a real
    child cannot be asked to emit two hundred messages inside 100 ms on demand.
    """
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    manager = managers()
    view = views(manager=manager, jobs=store, job_id="job-1", repaint_interval_ms=100)

    for index in range(200):
        view._on_progress(
            Progress(
                job_id="job-1",
                stage=Stage.DOWNLOADING_VIDEO,
                downloaded_bytes=index + 1,
                total_bytes=200,
            )
        )

    drawn = view.displayed_progress
    assert drawn is None, (
        "the widget repainted per message; two hundred repaints is the naive implementation"
    )
    pending = view.pending_progress
    assert pending is not None and pending.downloaded_bytes == 200, (
        "the newest message was not the one held; a burst must coalesce, not drop its tail"
    )

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and view.displayed_progress is None:
        qapp.processEvents()
        time.sleep(0.005)
    displayed = view.displayed_progress
    assert displayed is not None and displayed.downloaded_bytes == 200, (
        "the repaint drew something other than the newest message"
    )
    assert view.pending_progress is None


def test_absorbing_a_burst_stays_inside_the_interaction_budget(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
) -> None:
    """The same claim as a number, because "coalesced" is only useful if arrival is cheap.

    `NFR-001` budgets ~100 ms for an interaction. Two hundred messages arriving is not an
    interaction, but it competes with one, so the whole burst has to cost far less than that.
    """
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    manager = managers()
    view = views(manager=manager, jobs=store, job_id="job-1")
    messages = [
        Progress(
            job_id="job-1", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=index, total_bytes=200
        )
        for index in range(200)
    ]

    started = time.perf_counter()
    for message in messages:
        view._on_progress(message)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.05, (
        f"two hundred progress messages took {elapsed * 1000:.1f} ms to absorb, against "
        "NFR-001's ~100 ms budget for a whole interaction"
    )


def test_a_status_change_does_not_redraw_progress_outside_the_rate_limit(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`T017-R1`: the second route into the progress fields had no rate limit on it.

    The burst test above drives `_on_progress` alone, so it never crossed the path a real
    download takes — where a stage change persists, `job_changed` arrives, and the widget was
    calling `_draw_pending()` from that slot. Three messages interleaved with three status
    changes redrew three times inside one interval, and the rate is the whole promise.

    What must stay immediate is the *state word*: a cancelled job may not go on saying
    "Downloading" until the next tick. That is written by `_refresh`, not by drawing progress.
    """
    store.add(make_job("job-1", tmp_path, status=JobStatus.PROBING))
    manager = managers()
    view = views(manager=manager, jobs=store, job_id="job-1", repaint_interval_ms=100)

    def message(index: int) -> Progress:
        return Progress(
            job_id="job-1", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=index, total_bytes=3
        )

    view._on_progress(message(1))
    view._on_job_changed("job-1", JobStatus.RUNNING.value)
    view._on_progress(message(2))
    view._on_job_changed("job-1", JobStatus.POST_PROCESSING.value)
    view._on_progress(message(3))

    assert view.renders == 0, (
        f"{view.renders} repaints inside one interval; a status change flushed pending progress "
        "past the rate limit"
    )
    assert view.stage_text() == "Post-processing", (
        "before anything has been rendered the state word is all there is, so it has to be "
        "immediate even though the progress behind it waits"
    )

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and view.renders == 0:
        qapp.processEvents()
        time.sleep(0.005)
    assert view.renders == 1, f"the interval produced {view.renders} repaints, not one"
    drawn = view.displayed_progress
    assert drawn is not None and drawn.downloaded_bytes == 3, "the repaint drew a stale message"


def test_only_an_ending_is_immediate_once_progress_is_on_screen(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`T017-R3`: the previous test only covered the state *before* anything had rendered.

    Once a stage has been drawn, a non-terminal status change deliberately leaves it alone —
    "Downloading video" is better information than "Downloading", and the next repaint replaces
    it within one interval. An *ending* is different and is written at once, because a job that
    has stopped must never go on claiming to be running. This states which of the two the widget
    actually promises; the earlier assertion read as though it promised both.
    """
    store.add(make_job("job-1", tmp_path, status=JobStatus.PROBING))
    view = views(manager=managers(), jobs=store, job_id="job-1", repaint_interval_ms=1000)

    view._on_progress(
        Progress(job_id="job-1", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=1, total_bytes=2)
    )
    view._draw_pending()
    assert view.stage_text() == "Downloading video"

    view._on_job_changed("job-1", JobStatus.RUNNING.value)
    assert view.stage_text() == "Downloading video", (
        "a running status overwrote the more specific stage the worker had reported"
    )

    view._on_job_changed("job-1", JobStatus.CANCELLED.value)
    assert view.stage_text() == "Cancelled", (
        "an ending waited for a repaint; a stopped job may not go on claiming to run"
    )


#: Every shape the progress bar's three inputs can take. Small and closed on purpose: this is
#: the space `T017-R2` kept escaping through, three corrections running, because each one gated
#: the case that had just been found (`ai/TESTING.md` §13).
BAR_INPUTS: Final = [
    (done, total, finished)
    for done in (None, 0, 5, 10, 20)
    for total in (None, 0, 10)
    for finished in (False, True)
]


@pytest.mark.parametrize(("done", "total", "finished"), BAR_INPUTS)
def test_the_bar_and_its_description_never_disagree(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    done: int | None,
    total: int | None,
    finished: bool,
) -> None:
    """`T017-R2`, gated over the whole input space rather than over remembered scenarios.

    The assertion is a **relation between what the bar shows and what it says**, derived from the
    widget's own rendered state rather than from a table written beside the code. That matters:
    every previous version of this gate compared the description against a string the same author
    had just written, so it agreed with itself and missed the case next door. Three findings came
    through three different doors — the determinate branch inheriting an indeterminate
    description, `_refresh` writing the bar without one, and completion with an unknown total —
    and all three are one sentence: *a determinate bar must never say progress cannot be
    measured, and an indeterminate one must never claim a figure.*
    """
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    view = views(manager=managers(), jobs=store, job_id="job-1")
    bar = view.findChild(QProgressBar, "progressBar")
    assert bar is not None

    view._draw_bar(done, total, finished=finished)
    described = bar.accessibleDescription()
    indeterminate = (bar.minimum(), bar.maximum()) == (0, 0)

    assert described, f"the bar said nothing at all for {(done, total, finished)}"
    if indeterminate:
        assert "cannot be measured" in described, (
            f"an indeterminate bar has to say so: {described!r}"
        )
        assert "percent" not in described, f"an indeterminate bar claimed a figure: {described!r}"
        assert not finished, "a finished download was drawn as an indeterminate bar"
        return

    assert "cannot be measured" not in described, (
        f"a determinate bar at {bar.value()}% says progress cannot be measured: {described!r}"
    )
    if finished:
        assert bar.value() == 100, "a finished download did not fill its bar"
        assert "Complete" in described, f"a full bar has to say what it means: {described!r}"
        assert "percent" not in described, (
            f"a finished download reported a percentage rather than its size: {described!r}"
        )
        # `T017-R4`: `done` is a progress counter, and a progress counter is not a measurement of
        # a finished file. With no total there is nothing durable saying how big it was.
        if total:
            assert format_bytes(total) in described, (
                f"a finished download knew its size and did not say it: {described!r}"
            )
        else:
            assert described == "Complete", (
                f"a finished download with no recorded total stated a size anyway: {described!r}"
            )
    else:
        assert f"{bar.value()} percent" in described, (
            f"the bar shows {bar.value()}% and says {described!r}"
        )


#: One row per ending, from the rule in `job_detail`'s module docstring. The rule exists because
#: two of the three endings want the opposite source from the third, which is what `T017-R4` came
#: of not writing down.
ENDINGS: Final = [
    (JobStatus.CANCELLED, "what was last shown"),
    (JobStatus.FAILED, "what was last shown"),
    (JobStatus.COMPLETED, "the row's total"),
]


@pytest.mark.parametrize(("ending", "source"), ENDINGS)
def test_each_ending_takes_its_size_from_the_source_the_rule_names(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    qapp: QApplication,
    ending: JobStatus,
    source: str,
) -> None:
    """`T017-R4`. One case per row of the rule, driven through the same interleaving.

    The row is left deliberately behind the display — 1 of 10 stored, 5 of 10 rendered — which is
    the ordinary state of affairs while a job runs, because `manager.py` does not persist progress
    per message. A stopped job then has to pick a source, and the previous correction picked the
    same one for all three endings: cancelling at 50% redrew the bar at the row's stale 10%.
    """
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING, bytes_done=1, bytes_total=10))
    view = views(manager=managers(), jobs=store, job_id="job-1", repaint_interval_ms=1)
    bar = view.findChild(QProgressBar, "progressBar")
    bytes_label = view.findChild(QLabel, "bytesValue")
    assert bar is not None and bytes_label is not None

    view._on_progress(
        Progress(job_id="job-1", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=5, total_bytes=10)
    )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and view.renders == 0:
        qapp.processEvents()
        time.sleep(0.005)
    assert bar.value() == 50 and bytes_label.text() == "5 B of 10 B"

    store.jobs["job-1"] = replace(store.jobs["job-1"], status=ending)
    view._on_job_changed("job-1", ending.value)

    if ending is JobStatus.COMPLETED:
        assert bar.value() == 100
        assert bytes_label.text() == "10 B of 10 B", (
            f"a completed download showed its progress counter, not its size ({source}): "
            f"{bytes_label.text()!r}"
        )
        assert "10 B" in bar.accessibleDescription()
        return

    assert bar.value() == 50, (
        f"{ending.value} rolled the display backward to the row's stale figure "
        f"({bar.value()}%); the rule says {source}, and the row lags on purpose"
    )
    assert bytes_label.text() == "5 B of 10 B", (
        f"{ending.value} replaced what was transferred with what the row happened to hold: "
        f"{bytes_label.text()!r}"
    )


#: Every row of the size rule, as a view is **opened onto** a job in that state — the entry point
#: five `T-017` correction rounds never drove, because every test in that task started from a
#: running view (`T-059`).
REOPENED: Final = [
    ("completed, counter behind its total", JobStatus.COMPLETED, 1, 20, "20 B of 20 B", "20 B"),
    ("completed, no recorded total", JobStatus.COMPLETED, 3, None, UNKNOWN_TEXT, "Complete"),
    ("cancelled partway", JobStatus.CANCELLED, 5, 10, "5 B of 10 B", "50 percent"),
    ("failed partway", JobStatus.FAILED, 5, 10, "5 B of 10 B", "50 percent"),
    ("cancelled before any bytes", JobStatus.CANCELLED, 0, None, "0 B of Unknown", "cannot be"),
]


@pytest.mark.parametrize(
    ("case", "status", "done", "total", "expected_line", "expected_words"), REOPENED
)
def test_a_view_opened_onto_a_finished_job_tells_one_story(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    case: str,
    status: JobStatus,
    done: int,
    total: int | None,
    expected_line: str,
    expected_words: str,
) -> None:
    """`T-059`, carrying `T017-R4`'s open half. **Construction, not transition.**

    `T-017` settled where a stopped job's size comes from and put the rule in one place; `_load`
    then computed its own answer, so the same row gave two results depending on whether anyone had
    been watching it finish. Reopening is not an edge case — it is what happens after every
    restart, and after `T-036` it is how a completed job first appears.

    Driven by constructing the view over a stored row and asserting the byte line and the bar
    agree, which is the contradiction every form of this finding produced.
    """
    store.add(make_job("job-1", tmp_path, status=status, bytes_done=done, bytes_total=total))
    view = views(manager=managers(), jobs=store, job_id="job-1")
    bar = view.findChild(QProgressBar, "progressBar")
    bytes_label = view.findChild(QLabel, "bytesValue")
    assert bar is not None and bytes_label is not None

    assert bytes_label.text() == expected_line, (
        f"{case}: the byte line reads {bytes_label.text()!r}"
    )
    assert expected_words in bar.accessibleDescription(), (
        f"{case}: the bar says {bar.accessibleDescription()!r}"
    )

    # The relation the whole finding is about, restated where construction can break it.
    described = bar.accessibleDescription()
    if status is JobStatus.COMPLETED:
        assert bar.value() == 100
        assert "percent" not in described, (
            f"{case}: a finished download reported a percentage: {described!r}"
        )
        if total:
            assert bytes_label.text() == f"{format_bytes(total)} of {format_bytes(total)}"
    else:
        assert "Complete" not in described, (
            f"{case}: a job that never finished claims to be complete: {described!r}"
        )
    if (bar.minimum(), bar.maximum()) == (0, 0):
        assert "cannot be measured" in described
    else:
        assert "cannot be measured" not in described


def test_a_completed_download_of_unrecorded_size_invents_none(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`T017-R4`: with no durable total, the last progress counter is not a final size.

    It reported "Complete: 3 B downloaded" over a file nobody had measured — a stage transition's
    byte count promoted to a measurement by being the only number to hand.
    """
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING, bytes_done=3))
    view = views(manager=managers(), jobs=store, job_id="job-1", repaint_interval_ms=1)
    bar = view.findChild(QProgressBar, "progressBar")
    bytes_label = view.findChild(QLabel, "bytesValue")
    assert bar is not None and bytes_label is not None

    view._on_progress(Progress(job_id="job-1", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=3))
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and view.renders == 0:
        qapp.processEvents()
        time.sleep(0.005)

    store.jobs["job-1"] = replace(store.jobs["job-1"], status=JobStatus.COMPLETED)
    view._on_job_changed("job-1", JobStatus.COMPLETED.value)

    assert bar.value() == 100
    assert bar.accessibleDescription() == "Complete", (
        f"a size was stated for a download nothing measured: {bar.accessibleDescription()!r}"
    )
    assert bytes_label.text() == UNKNOWN_TEXT, (
        f"the byte line invented a figure too: {bytes_label.text()!r}"
    )


def test_a_completed_row_whose_counter_lags_its_total_says_one_thing(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
) -> None:
    """`T017-R4`: a real completed row routinely holds `bytes_done < bytes_total`.

    `manager.py` writes `bytes_total` at the terminal transition and leaves the counter wherever
    progress stopped, so this is the ordinary shape rather than a corrupt one. The widget showed a
    100% bar reading "Complete: 20 B downloaded" beside a byte line reading "1 B of 20 B" — both
    from the same row, disagreeing.
    """
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING, bytes_done=1, bytes_total=20))
    view = views(manager=managers(), jobs=store, job_id="job-1")
    bar = view.findChild(QProgressBar, "progressBar")
    bytes_label = view.findChild(QLabel, "bytesValue")
    assert bar is not None and bytes_label is not None

    store.jobs["job-1"] = replace(store.jobs["job-1"], status=JobStatus.COMPLETED)
    view._on_job_changed("job-1", JobStatus.COMPLETED.value)

    assert bar.value() == 100
    assert bytes_label.text() == "20 B of 20 B", (
        f"the byte line contradicts a full bar: {bytes_label.text()!r}"
    )
    assert "20 B" in bar.accessibleDescription()


def test_a_finished_download_reports_the_size_its_row_holds_not_the_last_one_drawn(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`T017-R2`: the totals behind a finished bar came from whatever a repaint last drew.

    The final bytes normally arrive with `Succeeded` rather than as a progress update, so the
    last rendered message is precisely the wrong source. A row holding 2 KB was described as
    "Complete: 1.0 KB downloaded" — a stale figure presented as a final one.
    """
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    view = views(manager=managers(), jobs=store, job_id="job-1", repaint_interval_ms=1)
    bar = view.findChild(QProgressBar, "progressBar")
    assert bar is not None

    view._on_progress(
        Progress(
            job_id="job-1", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=1024, total_bytes=1024
        )
    )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and view.renders == 0:
        qapp.processEvents()
        time.sleep(0.005)
    assert "1.0 KB" in bar.accessibleDescription()

    # The download finished larger than the last message said, which is the ordinary case.
    store.jobs["job-1"] = replace(
        store.jobs["job-1"], status=JobStatus.COMPLETED, bytes_done=2048, bytes_total=2048
    )
    view._on_job_changed("job-1", JobStatus.COMPLETED.value)

    described = bar.accessibleDescription()
    assert "2.0 KB" in described, (
        f"the finished bar reported the last size drawn rather than the row's: {described!r}"
    )
    assert "1.0 KB" not in described


def test_a_completed_download_describes_a_full_bar_and_not_the_last_percentage(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`T017-R2` through its sibling path, which the first correction missed.

    `_show_totals` was fixed and `_refresh` still set the bar to 100% by itself, so a completed
    download showed a full bar whose accessible description said "50 percent of 10 B
    downloaded". Same contradiction, different writer — which is why the bar now has exactly one.
    """
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    view = views(manager=managers(), jobs=store, job_id="job-1", repaint_interval_ms=1)
    bar = view.findChild(QProgressBar, "progressBar")
    assert bar is not None

    view._on_progress(
        Progress(job_id="job-1", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=5, total_bytes=10)
    )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and view.renders == 0:
        qapp.processEvents()
        time.sleep(0.005)
    assert bar.value() == 50 and "50" in bar.accessibleDescription()

    view._on_job_changed("job-1", JobStatus.COMPLETED.value)

    assert bar.value() == 100, "the bar did not fill on completion"
    described = bar.accessibleDescription()
    assert "50" not in described, (
        f"the completed bar still describes the last percentage it drew: {described!r}"
    )
    assert "Complete" in described, (
        f"a full bar has to say what it means, not merely stop saying the wrong thing: "
        f"{described!r}"
    )


def test_a_terminal_state_drops_progress_that_can_no_longer_be_true(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`T017-R1`, the other half: deferring a message past the ending would overwrite it.

    Holding pending progress behind the rate limit is right while a job is running and wrong once
    it has stopped — nothing a worker said before the end is still true afterwards, and a tick
    later it would replace "Cancelled" with the download that is not happening.
    """
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    view = views(manager=managers(), jobs=store, job_id="job-1", repaint_interval_ms=10)

    view._on_progress(
        Progress(job_id="job-1", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=5, total_bytes=10)
    )
    view._on_job_changed("job-1", JobStatus.CANCELLED.value)

    assert view.pending_progress is None, "a message that can no longer be true was kept"
    assert view.stage_text() == "Cancelled"

    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    assert view.renders == 0
    assert view.stage_text() == "Cancelled", "a deferred progress message overwrote the ending"


def test_the_bar_never_describes_itself_as_the_bar_it_no_longer_is(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`T017-R2`, gated in **both** directions.

    An unknown total is the ordinary opening state of a download and a known one arrives moments
    later, so the transition is common rather than exotic. The indeterminate branch set an
    accessible description and the determinate branch never cleared it: the bar showed 50 percent
    while telling a screen reader that progress could not be measured. Under `NFR-005` that is
    worse than silence — two users of the same widget were being told different things.
    """
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    view = views(manager=managers(), jobs=store, job_id="job-1", repaint_interval_ms=1)
    bar = view.findChild(QProgressBar, "progressBar")
    assert bar is not None

    def deliver(done: int, total: int | None) -> None:
        view._on_progress(
            Progress(
                job_id="job-1",
                stage=Stage.DOWNLOADING_VIDEO,
                downloaded_bytes=done,
                total_bytes=total,
            )
        )
        renders = view.renders
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and view.renders == renders:
            qapp.processEvents()
            time.sleep(0.005)

    deliver(1024, None)
    assert (bar.minimum(), bar.maximum()) == (0, 0)
    assert "cannot be measured" in bar.accessibleDescription()

    deliver(5, 10)
    assert (bar.minimum(), bar.maximum()) == (0, 100)
    assert bar.value() == 50
    assert "cannot be measured" not in bar.accessibleDescription(), (
        f"the determinate bar still says progress cannot be measured: "
        f"{bar.accessibleDescription()!r}"
    )
    assert "50" in bar.accessibleDescription(), (
        "a determinate bar has to say what it shows, not merely stop lying"
    )

    deliver(2048, None)
    assert (bar.minimum(), bar.maximum()) == (0, 0)
    assert "cannot be measured" in bar.accessibleDescription(), (
        "going back to an unknown total left the old percentage in the description"
    )


# --- 3. cancel (`REQ-015`) --------------------------------------------------------------------


def test_cancel_is_reachable_by_keyboard_and_lands_inside_the_budget(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    qapp: QApplication,
    spin: Callable[..., bool],
) -> None:
    """`REQ-015` and `NFR-005` in one: the control is actuated with the keyboard, not clicked.

    A cancel that only a mouse can reach is not a cancel for a keyboard or screen-reader user,
    and the two-second budget is measured from the key press rather than from the manager call —
    which is what a user experiences.
    """
    store.add(make_job("job-1", tmp_path))
    manager = managers(entry_point=child_downloading_forever, cooperative_seconds=0.2)
    view = views(manager=manager, jobs=store, job_id="job-1")
    view.show()
    qapp.processEvents()

    manager.start("job-1")
    assert spin(lambda: store.statuses("job-1")[-1:] == [JobStatus.RUNNING], timeout=30), (
        f"the download never started: {store.statuses('job-1')}"
    )

    cancel = button(view, "cancelJobButton")
    cancel.setFocus()
    qapp.processEvents()
    assert cancel.hasFocus(), "the cancel control cannot be reached by keyboard"

    started = time.monotonic()
    QTest.keyClick(cancel, Qt.Key.Key_Space)
    assert spin(lambda: view.status is JobStatus.CANCELLED, timeout=30), (
        f"the job never reached cancelled: {store.statuses('job-1')}"
    )
    elapsed = time.monotonic() - started
    assert elapsed < CANCEL_BUDGET_SECONDS, (
        f"cancelling took {elapsed:.2f}s, over REQ-015's {CANCEL_BUDGET_SECONDS}s budget"
    )


def test_a_cancelled_job_is_presented_as_cancelled_and_not_as_an_error(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    spin: Callable[..., bool],
) -> None:
    """`ARCHITECTURE.md` §7: `CANCELLED` is not a failure, so it offers no retry.

    Presenting it as an error would offer to retry something the user asked to stop.
    """
    store.add(make_job("job-1", tmp_path))
    manager = managers(entry_point=child_downloading_forever, cooperative_seconds=0.05)
    view = views(manager=manager, jobs=store, job_id="job-1")

    manager.start("job-1")
    assert spin(lambda: store.statuses("job-1")[-1:] == [JobStatus.RUNNING], timeout=30)
    view.cancel()
    assert spin(lambda: view.status is JobStatus.CANCELLED, timeout=30)

    assert view.stage_text() == "Cancelled"
    assert not view.can_retry, "a cancelled job was offered a retry"
    assert not view.can_cancel, "a cancelled job can still be cancelled"
    assert view.error_text(), "a cancelled job said nothing at all about being cancelled"


def test_a_cancelled_job_with_no_word_from_its_worker_still_says_so(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
) -> None:
    """`NFR-005`: no state conveyed by appearance alone, including the one nobody reported."""
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    manager = managers()
    view = views(manager=manager, jobs=store, job_id="job-1")

    view._on_job_changed("job-1", JobStatus.CANCELLED.value)

    assert view.error_text() == CANCELLED_TEXT
    assert view.stage_text() == "Cancelled"


# --- 4. failure (`REQ-018`, `NFR-006`) --------------------------------------------------------


def test_a_failed_job_stays_visible_with_the_extractors_own_message(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    spin: Callable[..., bool],
) -> None:
    """`REQ-018` and `NFR-006`: the message is the extractor's, character for character."""
    verbatim = NETWORK_MESSAGE
    store.add(make_job("job-1", tmp_path))
    manager = managers(entry_point=child_failing_as_network)
    view = views(manager=manager, jobs=store, job_id="job-1")

    manager.start("job-1")
    assert spin(lambda: view.status is JobStatus.FAILED, timeout=30), (
        f"the job never failed: {store.statuses('job-1')}"
    )

    assert verbatim in view.error_text(), (
        f"the extractor's message was altered: {view.error_text()!r}"
    )
    assert view.failure == (ErrorKind.NETWORK, verbatim)
    assert view.stage_text() == "Failed"
    assert view.can_retry, "a network failure is retryable and must offer it (REQ-018)"


def test_markup_in_an_extractor_message_is_shown_and_not_rendered(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
) -> None:
    """`T016-R6`, one widget along: a message of `<b>gone</b>` is a message, not markup."""
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    manager = managers()
    view = views(manager=manager, jobs=store, job_id="job-1")

    view._on_job_failed("job-1", ErrorKind.EXTRACTOR_ERROR, "<b>VISIBLE</b>")
    view._on_job_changed("job-1", JobStatus.FAILED.value)

    assert "<b>VISIBLE</b>" in view.error_text()


# --- 5. the DRM boundary (`SEC-001`, `REQ-EXCL-001`) ------------------------------------------


def test_a_drm_failure_offers_no_retry_at_all(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    spin: Callable[..., bool],
) -> None:
    """The UI half of `ai/TESTING.md` §7's DRM row (`SEC-001`, `REQ-EXCL-001`).

    `core/errors.py` states the reason where the policy lives: *offering the button implies a
    workaround exists*. It does not, so the control is **absent** rather than disabled — a
    greyed-out Retry still asserts that a retry is the sort of thing this failure could have.

    The engine half is gated in `tests/integration/test_worker.py`; nothing gated this one until
    `T-017`, because the widget did not exist.
    """
    message = DRM_MESSAGE
    store.add(make_job("job-1", tmp_path))
    manager = managers(entry_point=child_failing_as_drm)
    view = views(manager=manager, jobs=store, job_id="job-1")

    manager.start("job-1")
    assert spin(lambda: view.status is JobStatus.FAILED, timeout=30)

    assert view.failure == (ErrorKind.DRM_PROTECTED, message)
    assert message in view.error_text(), "the failure is still reported; only the retry is not"
    assert not view.can_retry, (
        "a DRM failure was offered a retry, which SEC-001 says must not exist"
    )
    assert button(view, "retryJobButton").isHidden(), (
        "the retry control was merely disabled; a disabled button still claims a retry exists"
    )


@pytest.mark.parametrize("kind", list(ErrorKind))
def test_the_retry_affordance_agrees_with_the_taxonomy_for_every_kind(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    kind: ErrorKind,
) -> None:
    """The rule, not the case. Every kind, checked against `is_retryable` itself.

    Written this way on purpose: a widget that listed the non-retryable kinds would have to be
    edited whenever the taxonomy changed, and the edit that gets forgotten is the one that
    matters. `core/errors.py` is the single place the rule lives, and this asserts the widget
    asks it rather than remembering an answer.
    """
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    manager = managers()
    view = views(manager=manager, jobs=store, job_id="job-1")

    view._on_job_failed("job-1", kind, "something happened")
    view._on_job_changed("job-1", JobStatus.FAILED.value)

    assert view.can_retry is is_retryable(kind), (
        f"{kind.value}: the widget offers retry={view.can_retry}, the taxonomy says "
        f"{is_retryable(kind)}"
    )


def test_an_unclassifiable_failure_offers_no_retry_and_still_shows_its_message(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
) -> None:
    """No guess about retry policy. `core/errors.py`: a wrong guess is worse than no guess."""
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    manager = managers()
    view = views(manager=manager, jobs=store, job_id="job-1")

    view._on_job_failed("job-1", "not-a-kind", "the site said no")
    view._on_job_changed("job-1", JobStatus.FAILED.value)

    assert "the site said no" in view.error_text()
    assert not view.can_retry


def test_the_retry_affordance_reports_rather_than_writing(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`ui/` holds no writer, so a retry is reported and composition performs it (`T-036`)."""
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    manager = managers()
    view = views(manager=manager, jobs=store, job_id="job-1")
    asked: list[str] = []
    view.retry_requested.connect(asked.append)

    view._on_job_failed("job-1", ErrorKind.NETWORK, "timed out")
    view._on_job_changed("job-1", JobStatus.FAILED.value)
    retry = button(view, "retryJobButton")
    retry.setFocus()
    QTest.keyClick(retry, Qt.Key.Key_Space)
    qapp.processEvents()

    assert asked == ["job-1"]
    assert store.statuses("job-1") == [], "the widget wrote to the queue; that is composition's"


# --- 6. accessibility and honesty about unknowns ----------------------------------------------


def test_every_control_has_an_accessible_name(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
) -> None:
    """`NFR-005`. Checked over the widgets Qt reports, not over a list this test maintains."""
    store.add(make_job("job-1", tmp_path))
    view = views(manager=managers(), jobs=store, job_id="job-1")

    unnamed = [
        child.objectName()
        for child in view.findChildren(QWidget)
        if child.objectName()
        and not child.accessibleName()
        # The two layout containers carry no information of their own; a screen reader announces
        # what is inside them, and naming a box that is only there to hold a row adds noise.
        and child.objectName() not in {"progressNumbers", "jobActions"}
        # Qt's own internals — the scroll-area viewport and its containers, which every
        # `QAbstractScrollArea` brings with it. They are named by Qt, not by this project, and
        # a screen reader announces the widget that owns them.
        and not child.objectName().startswith("qt_")
    ]
    assert not unnamed, f"these controls have no accessible name: {unnamed}"


def test_the_declared_focus_order_is_the_one_qt_builds(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """Every focusable control is declared, and the expectation is transcribed by hand.

    `T016-R4` and `T-040`: deriving the expected order from `focus_chain()` would prove only
    that the list equals itself, and the mutation that reverses two entries survives such a
    test. So the order below is written out (`ai/TESTING.md` §13).
    """
    store.add(make_job("job-1", tmp_path, status=JobStatus.FAILED, error_kind=ErrorKind.NETWORK))
    # `log_directory` pinned to this test's own tree. Without it the view reads the machine's real
    # cache, and a `job-1.log` left there by any other test makes the copy button live — which is
    # exactly how this test came to pass alone and fail in the full suite.
    view = views(manager=managers(), jobs=store, job_id="job-1", log_directory=tmp_path)
    view.show()
    qapp.processEvents()

    expected = ["errorMessage", "cancelJobButton", "retryJobButton", "diagnosticsBox"]
    assert [widget.objectName() for widget in view.focus_chain()] == expected, (
        "the collapsed state's order changed; the diagnostics box's own indicator is focusable "
        "but what is inside it is not reachable until it is expanded (T-084)"
    )

    # Expanded is a second state and is transcribed separately, for the reason above.
    view.log_box.setChecked(True)
    qapp.processEvents()
    assert [widget.objectName() for widget in view.focus_chain()] == [
        *expected,
        "logText",
    ], "an expanded diagnostics box must put its text in the keyboard order"
    view.log_box.setChecked(False)

    focusable = {
        child.objectName()
        for child in view.findChildren(QWidget)
        if child.focusPolicy() != Qt.FocusPolicy.NoFocus
        and child.objectName()
        and not child.objectName().startswith("qt_")
        # Hidden while the box is collapsed, and `focus_chain` says so; Qt still reports the
        # policy of a widget nobody can reach.
        and child.isVisibleTo(view)
    }
    assert focusable == set(expected), (
        f"a focusable control is missing from the declared order: {focusable ^ set(expected)}"
    )


def test_an_unknown_total_is_shown_as_unknown_and_not_as_zero(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`None` is not zero — the rule `Job.progress` already refuses to break (`REQ-011`)."""
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    view = views(manager=managers(), jobs=store, job_id="job-1", repaint_interval_ms=1)

    view._on_progress(
        Progress(job_id="job-1", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=1024)
    )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and view.displayed_progress is None:
        qapp.processEvents()
        time.sleep(0.005)

    bar = view.findChild(QProgressBar, "progressBar")
    bytes_label = view.findChild(QLabel, "bytesValue")
    assert bar is not None and bytes_label is not None
    assert (bar.minimum(), bar.maximum()) == (0, 0), "an unknown total showed a definite bar"
    assert UNKNOWN_TEXT in bytes_label.text()
    assert bar.accessibleDescription(), "the indeterminate state is signalled only by animation"


@pytest.mark.parametrize(
    ("count", "expected"),
    [(None, UNKNOWN_TEXT), (0, "0 B"), (512, "512 B"), (1536, "1.5 KB"), (1024**3, "1.0 GB")],
)
def test_sizes_are_rendered_the_way_a_file_manager_renders_them(
    count: int | None, expected: str
) -> None:
    assert format_bytes(count) == expected


def test_an_unknown_speed_says_so() -> None:
    assert format_speed(None) == UNKNOWN_TEXT
    assert format_speed(2048.0) == "2.0 KB/s"


def test_composition_can_wire_the_retry_without_the_widget_knowing_how(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`build_progress_view` is the seam `T-036` uses; it exists so it cannot be forgotten."""
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    asked: list[str] = []
    view = build_progress_view(managers(), store, "job-1", asked.append)
    try:
        view._on_job_failed("job-1", ErrorKind.NETWORK, "timed out")
        view._on_job_changed("job-1", JobStatus.FAILED.value)
        button(view, "retryJobButton").click()
        qapp.processEvents()
        assert asked == ["job-1"]
    finally:
        view.close()
        view.deleteLater()
        qapp.processEvents()


def test_the_view_ignores_another_jobs_messages(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
) -> None:
    """A pool of one is Phase 1's rule, not the manager's signal contract (`T-011`, `T012-R?`)."""
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    view = views(manager=managers(), jobs=store, job_id="job-1")

    view._on_progress(Progress(job_id="job-2", stage=Stage.MERGING, downloaded_bytes=5))
    view._on_job_failed("job-2", ErrorKind.NETWORK, "not this job")
    view._on_job_changed("job-2", JobStatus.FAILED.value)

    assert view.pending_progress is None
    assert view.failure is None
    assert view.status is JobStatus.RUNNING


def test_retrying_a_job_retires_the_failed_attempts_live_state(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`T079-R1`, found in the queue table and audited back to here — **this widget had it too.**

    The reviewer asked for the analogous cached-message lifecycle to be audited rather than
    assumed covered by the table's correction. It was not covered: `_refresh` rewrites the stage
    line only when the job is terminal *or* nothing has been drawn, and after a failed attempt
    something had been drawn — so pressing Retry left "Downloading video" over a queued job.

    The durable row is deliberately behind the drawn message (10% stored, 50% drawn), because
    that is the only way to tell "retired it" from "kept it". `manager.py` does not persist
    progress per message, so the row lags by design while a job runs.
    """
    store.add(
        make_job("job-1", tmp_path, status=JobStatus.RUNNING, bytes_done=100, bytes_total=1000)
    )
    manager = managers()
    view = views(manager=manager, jobs=store, job_id="job-1", repaint_interval_ms=10)

    view._on_progress(
        Progress(
            job_id="job-1",
            stage=Stage.DOWNLOADING_VIDEO,
            downloaded_bytes=500,
            total_bytes=1000,
            speed_bytes_per_second=2_200_000,
            eta_seconds=42,
        )
    )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and view.displayed_progress is None:
        qapp.processEvents()
        time.sleep(0.005)
    assert view.stage_text() == STAGE_TEXT[Stage.DOWNLOADING_VIDEO]

    # **Both live labels must hold a non-default value before the reset is asserted** (`T-101`).
    # Without this, `etaValue == UNKNOWN_TEXT` afterwards is satisfied by the label never having
    # been written at all, and the assertion passes against a production line that does nothing.
    drawn_speed = view.findChild(QLabel, "speedValue")
    drawn_eta = view.findChild(QLabel, "etaValue")
    assert drawn_speed is not None and drawn_speed.text() != UNKNOWN_TEXT, (
        "the speed label was never drawn, so retiring it proves nothing"
    )
    assert drawn_eta is not None and drawn_eta.text() != UNKNOWN_TEXT, (
        "the ETA label was never drawn, so retiring it proves nothing"
    )

    view._on_job_failed("job-1", ErrorKind.NETWORK, "ERROR: timed out")
    store.update(replace(store.jobs["job-1"], status=JobStatus.FAILED))
    view._on_job_changed("job-1", JobStatus.FAILED.value)
    # Read into a local: mypy narrows a property across asserts, so asserting on `view.failure`
    # twice would type the second one as unreachable and stop it being a gate.
    recorded = view.failure
    assert recorded is not None, "the failure was never recorded, so retiring it proves nothing"

    store.update(replace(store.jobs["job-1"], status=JobStatus.QUEUED))
    view._on_job_changed("job-1", JobStatus.QUEUED.value)

    assert view.stage_text() == "Queued", (
        f"a re-queued job still says {view.stage_text()!r}, which is the failed attempt's stage"
    )
    assert view.displayed_progress is None, "the failed attempt's message is still displayed"
    retired = view.failure
    assert retired is None, "a queued job is still reporting the error from the attempt that ended"
    bytes_label = view.findChild(QLabel, "bytesValue")
    assert bytes_label is not None
    assert bytes_label.text() == f"{format_bytes(100)} of {format_bytes(1000)}", (
        f"the re-queued view reports {bytes_label.text()!r}, which is the failed attempt's "
        "drawn byte count rather than the durable row's"
    )
    speed_label = view.findChild(QLabel, "speedValue")
    assert speed_label is not None and speed_label.text() == UNKNOWN_TEXT, (
        "a queued job has no worker and cannot have a speed"
    )
    # **Separately asserted, which is the whole of `T-101`** (`T079-R3`). The correction resets both
    # labels and this scenario checked only the speed, so deleting `_eta.setText(UNKNOWN_TEXT)`
    # alone left the complete 82-test file green while a re-queued job showed the failed attempt's
    # ETA. One combined assertion cannot gate two independent production lines.
    eta_label = view.findChild(QLabel, "etaValue")
    assert eta_label is not None and eta_label.text() == UNKNOWN_TEXT, (
        "a queued job is still reporting the failed attempt's ETA — it has no worker, and so "
        "nothing to estimate from"
    )


def test_the_diagnostics_box_is_closed_until_asked_and_re_reads_when_opened(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    views: Callable[..., JobProgressView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`T-084`, `REQ-019`. **Closed by default and re-read on expand.**

    Closed because diagnostics are what a user needs when something went wrong and clutter every
    other time. Re-read on expand rather than on a timer because the file grows while a job runs,
    and a box showing what the log said when the pane was built is worse than one showing nothing —
    it looks current.
    """
    store.add(make_job("job-1", tmp_path, status=JobStatus.FAILED, error_kind=ErrorKind.NETWORK))
    view = views(manager=managers(), jobs=store, job_id="job-1", log_directory=tmp_path)

    assert not view.log_box.isChecked(), "the diagnostics box opened over the progress bar"
    assert not view.log_view.isVisible()

    reads: list[int] = []
    original = view.log_view.refresh

    def counted() -> None:
        reads.append(1)
        original()

    view.log_view.refresh = counted  # type: ignore[method-assign]
    view.log_box.setChecked(True)
    qapp.processEvents()

    assert reads, "expanding the box showed whatever it had read at construction time"


def test_a_detached_view_stops_answering_the_manager(
    store: FakeStore,
    managers: Callable[..., DownloadManager],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`detach()` severs the connections, at the view rather than through a window (`T-124`).

    **Written because the only test of `detach` anywhere was a composition test about the detail
    pane**, and `UX-005` removes that pane. `UX-005` explicitly defers what becomes of
    `JobProgressView` rather than deciding it, so deleting its window route must not delete its
    guarantees with it — that would turn a deferral into a deletion nobody voted for.

    The guarantee is not "it eventually stops". `deleteLater` is asynchronous, so a replaced view
    goes on answering signals for however many event-loop turns it takes to die; `detach` is what
    makes replacement deterministic. Asserted by **counting Qt's own connections** rather than by
    watching for a stale render — a render-based test would pass whenever the timing happened to
    be kind, which is the class of test this file exists to avoid.
    """
    store.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    manager = managers()
    before = _connections_to(manager, "progress")

    view = build_progress_view(manager, store, "job-1", None)
    try:
        assert _connections_to(manager, "progress") == before + 1, (
            "the view was built and never listened to the manager, so this test would pass "
            "against a detach that did nothing"
        )

        view.detach()

        assert _connections_to(manager, "progress") == before, (
            "a detached view is still connected to progress; with the view replaced but not yet "
            "destroyed, one job's messages reach two listeners"
        )
        # **Twice is not an error.** Every close route reaches `detach`, and a disconnect of
        # something already disconnected raises — being asked twice to stop listening is not
        # worth propagating out of a slot.
        view.detach()
        assert _connections_to(manager, "progress") == before
    finally:
        view.close()
        view.deleteLater()
        qapp.processEvents()


def _connections_to(sender: QObject, signal_name: str) -> int:
    """How many slots are connected to `signal_name`, asked of Qt rather than of our own count.

    `ai/TESTING.md` §13: a count this code kept would agree with this code.

    **The `"2"` prefix is not decoration.** `receivers()` takes a `SIGNAL()`-encoded signature, and
    that macro's encoding is the digit 2 in front of the signature the meta-object gives. Without
    it Qt matches nothing and returns 0 — which reads exactly like "no connections" and would have
    made the built-view assertion below fail rather than the detach assertion, so the mistake is
    at least loud. It cost one run here to find.
    """
    meta = sender.metaObject()
    for index in range(meta.methodCount()):
        method = meta.method(index)
        if (
            method.methodType() == QMetaMethod.MethodType.Signal
            and bytes(method.name().data()).decode("ascii") == signal_name
        ):
            signature = bytes(method.methodSignature().data()).decode("ascii")
            return int(sender.receivers("2" + signature))
    raise LookupError(f"{type(sender).__name__} has no signal named {signal_name!r}")
