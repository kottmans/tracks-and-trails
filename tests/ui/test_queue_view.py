"""The queue table (`T-079`, `REQ-014`, `REQ-016`).

Driven by **real `T-011` messages** wherever the claim is about what a user sees during a
download: crafted children send stages over a real queue, through a real `ResultPump`, into a real
`DownloadManager`, with a real pool of three. The phase's first exit criterion is *three
concurrent downloads showing independent progress*, and a test that handed three `Progress`
objects to a model would prove the model can hold three rows — which is not that criterion.

Constructed messages are used in exactly two places, both about **rate** rather than content: a
real worker cannot be asked to emit hundreds of messages inside one repaint interval on demand.
Each says so where it appears, matching `tests/ui/test_job_detail.py`'s convention.
"""

import time
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from tests.qt_lifecycle import drain
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import DownloadRequest, Job
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.downloader.protocol import (
    Progress,
    SessionKind,
    Stage,
    Succeeded,
    WorkerFinished,
)
from tracks_and_trails.ui.job_detail import UNKNOWN_TEXT, describe_bar
from tracks_and_trails.ui.queue_view import (
    COLUMN_HEADERS,
    EMPTY_TEXT,
    ETA_COLUMN,
    INDETERMINATE_TEXT,
    JOB_COLUMN,
    PROGRESS_COLUMN,
    SIZE_COLUMN,
    SPEED_COLUMN,
    STATUS_COLUMN,
    QueueView,
)
from tracks_and_trails.ui.row_delegate import (
    DETAIL_ROLE,
    HEADLINE_ROLE,
    HUE_ROLE,
    PROGRESS_ROLE,
    STATE_ROLE,
    THUMBNAIL_URL_ROLE,
)

# --- a queue the table can read ---------------------------------------------------------------


class FakeQueue:
    """An in-memory `JobStore` and `QueueReader` at once.

    `all_jobs` returns them in **insertion order, not sorted**, on purpose: sorting here would
    make every ordering assertion in this file a test of this fake.
    """

    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        #: Counted because `T079-R2` is about *which* read happens, not about what it returns.
        #: `ARCHITECTURE.md` §3 permits a synchronous GUI read only when it is an indexed
        #: single-row lookup, and a count is the only way to assert that from outside.
        self.enumerations = 0
        self.lookups = 0
        #: Seconds `all_jobs` sleeps. The real cost is `SELECT *` plus deserialising every stored
        #: job, which grows with queue history; a sleep is that cost made deterministic.
        self.enumeration_delay = 0.0

    def add(self, job: Job) -> None:
        self.jobs[job.id] = job

    def get(self, job_id: str) -> Job | None:
        self.lookups += 1
        return self.jobs.get(job_id)

    def all_jobs(self) -> list[Job]:
        self.enumerations += 1
        if self.enumeration_delay:
            time.sleep(self.enumeration_delay)
        return list(self.jobs.values())

    def update(self, job: Job, done: Callable[[str | None], None] | None = None) -> None:
        self.jobs[job.id] = job
        if done is not None:
            done(None)

    def complete(
        self, job: Job, _format_used: str | None, done: Callable[[str | None], None]
    ) -> None:
        self.update(job, done)

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
        url=f"https://example.invalid/{job_id}",
        request=DownloadRequest(
            url=f"https://example.invalid/{job_id}",
            output_directory=str(directory),
            format_selector="best",
            output_template="%(title)s.%(ext)s",
        ),
        created_at=datetime.now(UTC),
        queue_position=0,
    )
    return replace(job, **overrides) if overrides else job


def child_downloading_a_known_size(
    _kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Four progress messages with a known total, then a success.

    A *known* total because the interesting column is a percentage, and a percentage of an unknown
    total is a different state with its own assertions elsewhere in this file.

    **The total is derived from the job id**, so three concurrent workers report three different
    sizes. Seeding different `bytes_total` values on the rows instead does not work and is worth
    stating: the manager writes the worker's total at the terminal transition, so a shared total
    overwrites the seeds and all three rows end up identical — which is indistinguishable from the
    defect the test exists to catch.
    """
    total = 1000 * int(job_id.rsplit("-", 1)[1])
    for fraction in (0.25, 0.5, 0.75, 1.0):
        queue.put(
            Progress(
                job_id=job_id,
                stage=Stage.DOWNLOADING_VIDEO,
                downloaded_bytes=int(total * fraction),
                total_bytes=total,
            )
        )
        time.sleep(0.05)
    output = str(Path(request.output_directory) / f"{job_id}.mp4")
    queue.put(Succeeded(job_id=job_id, output_path=output, format_used="best"))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))


@pytest.fixture
def queue() -> FakeQueue:
    return FakeQueue()


@pytest.fixture
def managers(queue: FakeQueue, qapp: QApplication) -> Iterator[Callable[..., DownloadManager]]:
    built: list[DownloadManager] = []

    def build(**overrides: Any) -> DownloadManager:
        manager = DownloadManager(queue, **overrides)
        built.append(manager)
        return manager

    yield build

    for manager in built:
        manager.shutdown()
    # Waits for the poll timer as well as the work — see `tests/qt_lifecycle.py` and `T-128`.
    drain(qapp, built)


@pytest.fixture
def views(qapp: QApplication, tmp_path: Path) -> Iterator[Callable[..., QueueView]]:
    built: list[QueueView] = []

    def build(**kwargs: Any) -> QueueView:
        # **Never the real cache directory.** The thumbnail store writes under `NFR-004`'s cache
        # root, and a view left on the default would write into the developer's own — then read it
        # back next run, which is a test passing on what a previous run left behind.
        kwargs.setdefault("cache_root", tmp_path / "cache")
        view = QueueView(**kwargs)
        built.append(view)
        return view

    yield build

    for view in built:
        view.detach()
        view.close()
        view.deleteLater()
    qapp.processEvents()


def spin_until(qapp: QApplication, predicate: Callable[[], bool], timeout: float = 30) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        qapp.processEvents()
        time.sleep(0.005)
    return predicate()


# --- 1. three at once, independently ----------------------------------------------------------


def test_three_concurrent_downloads_show_independent_progress(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """The phase's first exit criterion, asserted rather than observed.

    Three real workers, a real pool of three, three rows. **The assertion is that each row ends
    up describing its own job**, which is the thing a single shared progress field cannot do: a
    table that wrote every message into one row would show three identical rows and pass any
    check that merely counted rows or waited for "some" progress.

    The sizes differ per job for exactly that reason — the totals are what tell the rows apart.
    """
    for position, job_id in enumerate(("job-1", "job-2", "job-3")):
        queue.add(make_job(job_id, tmp_path, queue_position=position))
    manager = managers(concurrency=3, entry_point=child_downloading_a_known_size)
    view = views(jobs=queue, manager=manager)

    for job_id in ("job-1", "job-2", "job-3"):
        manager.start(job_id)

    assert spin_until(
        qapp,
        lambda: all(
            queue.jobs[job_id].status is JobStatus.COMPLETED
            for job_id in ("job-1", "job-2", "job-3")
        ),
    ), "the three downloads did not all finish"
    view.refresh()

    for job_id in ("job-1", "job-2", "job-3"):
        assert view.model.text_at(job_id, STATUS_COLUMN) == "Completed", (
            f"{job_id} does not describe itself as finished: "
            f"{view.model.text_at(job_id, STATUS_COLUMN)!r}"
        )
        assert view.model.text_at(job_id, PROGRESS_COLUMN) == "100%"

    sizes = {job_id: view.model.text_at(job_id, SIZE_COLUMN) for job_id in queue.jobs}
    assert len(set(sizes.values())) == 3, (
        f"the three rows report the same size, so they are not independent: {sizes}"
    )


def test_each_row_reports_its_own_job_while_all_three_are_running(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """Independence **during** the download, not only at the end.

    The test above waits for three endings, and an ending is written from the durable row — so a
    model that routed every live message into one row would still pass it. This one asserts while
    the workers are live, on the *drawn* message per job, which is the only place the routing
    can be wrong.

    Constructed messages: interleaving three real workers' output deterministically is a test
    about scheduling, and the claim here is about which row a message lands in.
    """
    for position, job_id in enumerate(("job-1", "job-2", "job-3")):
        queue.add(make_job(job_id, tmp_path, status=JobStatus.RUNNING, queue_position=position))
    manager = managers(concurrency=3)
    view = views(jobs=queue, manager=manager, repaint_interval_ms=10)

    for index, job_id in enumerate(("job-1", "job-2", "job-3"), start=1):
        view.model._on_progress(
            Progress(
                job_id=job_id,
                stage=Stage.DOWNLOADING_VIDEO,
                downloaded_bytes=index * 100,
                total_bytes=1000,
            )
        )

    assert spin_until(qapp, lambda: view.model.displayed_progress("job-3") is not None)

    for index, job_id in enumerate(("job-1", "job-2", "job-3"), start=1):
        drawn = view.model.displayed_progress(job_id)
        assert drawn is not None and drawn.downloaded_bytes == index * 100, (
            f"{job_id} shows {drawn.downloaded_bytes if drawn else None} rather than "
            f"{index * 100}; messages are not being routed per row"
        )
        assert view.model.text_at(job_id, PROGRESS_COLUMN) == f"{index * 10}%"


# --- 2. a row opened onto a job that already ended (`T-059`) -----------------------------------


@pytest.mark.parametrize(
    ("status", "expected_progress"),
    [
        (JobStatus.COMPLETED, "100%"),
        (JobStatus.CANCELLED, INDETERMINATE_TEXT),
        (JobStatus.FAILED, INDETERMINATE_TEXT),
    ],
)
def test_a_row_opened_onto_a_finished_job_renders_its_ending(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    status: JobStatus,
    expected_progress: str,
) -> None:
    """`T-059`, one surface over: nothing watched this job, so the row is all there is.

    This is not an exotic path. It is what every restart shows, and with a queue table it is what
    **every** finished job looks like — the table outlives each download, so most rows in it were
    never watched by anything.

    A model that reported an empty size here would be the emptied-bar defect `T-059` fixed in the
    detail view, and the reason `totals_for_ending` is shared rather than reimplemented.
    """
    queue.add(make_job("job-1", tmp_path, status=status, bytes_done=400, bytes_total=1000))
    manager = managers()
    view = views(jobs=queue, manager=manager)

    assert (
        view.model.text_at("job-1", STATUS_COLUMN)
        == {
            JobStatus.COMPLETED: "Completed",
            JobStatus.CANCELLED: "Cancelled",
            JobStatus.FAILED: "Failed",
        }[status]
    )
    assert view.model.text_at("job-1", PROGRESS_COLUMN) == expected_progress
    size = view.model.text_at("job-1", SIZE_COLUMN)
    assert size is not None and size != UNKNOWN_TEXT, (
        "a row opened onto a finished job reported no size at all; the durable row knows one, "
        "and nothing watched this download so there is nothing closer to prefer (T-059)"
    )


def test_a_completed_row_reports_its_total_and_not_its_lagging_counter(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """`T017-R2`'s rule, reached through the shared function.

    The manager writes `bytes_total` at the terminal transition and leaves `bytes_done` wherever
    progress stopped, so a real completed row routinely holds `bytes_done < bytes_total`. Showing
    the counter is how `Complete: 3 B downloaded` appeared over a file nobody had measured.
    """
    queue.add(
        make_job(
            "job-1", tmp_path, status=JobStatus.COMPLETED, bytes_done=3, bytes_total=5 * 1024 * 1024
        )
    )
    manager = managers()
    view = views(jobs=queue, manager=manager)

    size = view.model.text_at("job-1", SIZE_COLUMN)
    assert size == "5.0 MB of 5.0 MB", (
        f"a completed row reported {size!r}; a completed download is its total, and bytes_done "
        "is a progress counter rather than a measurement of a finished file"
    )


def test_a_stopped_job_shows_neither_a_speed_nor_an_eta(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """A stale `2.1 MB/s` beside a cancelled download is the stale-byte defect in another column.

    Reached by drawing a real speed first and *then* ending the job, because a row that never had
    a speed would show `Unknown` whether or not the rule exists.
    """
    queue.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    manager = managers()
    view = views(jobs=queue, manager=manager, repaint_interval_ms=10)

    view.model._on_progress(
        Progress(
            job_id="job-1",
            stage=Stage.DOWNLOADING_VIDEO,
            downloaded_bytes=500,
            total_bytes=1000,
            speed_bytes_per_second=2_200_000,
            eta_seconds=42,
        )
    )
    assert spin_until(qapp, lambda: view.model.displayed_progress("job-1") is not None)
    assert view.model.text_at("job-1", SPEED_COLUMN) != UNKNOWN_TEXT, "no speed was ever shown"

    queue.update(replace(queue.jobs["job-1"], status=JobStatus.CANCELLED))
    view.model._on_job_changed("job-1", JobStatus.CANCELLED.value)

    assert view.model.text_at("job-1", SPEED_COLUMN) == UNKNOWN_TEXT, (
        "a cancelled download is still reporting the speed it had when it stopped"
    )
    assert view.model.text_at("job-1", ETA_COLUMN) == UNKNOWN_TEXT, (
        "a cancelled download is still reporting an estimated time remaining"
    )


# --- 3. keyboard order, per state (`T-060`) ---------------------------------------------------


def test_the_keyboard_order_is_declared_for_a_queue_with_rows(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """`NFR-005`: the table is reachable, and it is what the chain names."""
    queue.add(make_job("job-1", tmp_path))
    manager = managers()
    view = views(jobs=queue, manager=manager)

    chain = view.focus_chain()
    assert chain == [view.table], f"the keyboard order is {chain}, expected the table alone"
    assert view.table.focusPolicy() != Qt.FocusPolicy.NoFocus, (
        "the table is in the keyboard order and cannot be focused"
    )


def test_an_empty_queue_offers_nothing_to_tab_to(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
) -> None:
    """The second state, which is the point of `T-060`'s "per state".

    A chain that named the table unconditionally would be describing a hidden widget: `Tab` would
    move focus to something the user cannot see. Asserted as an empty list rather than skipped,
    because "no controls" is a keyboard order and not the absence of one.
    """
    manager = managers()
    view = views(jobs=queue, manager=manager)

    assert view.focus_chain() == [], (
        "an empty queue claims a focusable table; the table is hidden behind the empty notice"
    )
    assert view.shows_empty_notice
    assert view.empty_text() == EMPTY_TEXT
    # `isHidden()`, not `isVisible()`: this widget is never shown, so `isVisible()` is False
    # for the table either way and the assertion would hold against a table that was on
    # screen. `isHidden()` asks what this code set, which is the thing under test.
    assert view.table.isHidden()


def test_the_notice_gives_way_to_the_table_when_a_job_arrives(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """Never both, in either direction — and the keyboard order moves with it.

    Both states are read into locals rather than asserted on the property twice: mypy narrows a
    property access across asserts, so the second assertion would be typed as unreachable and the
    gate would stop being a gate.
    """
    manager = managers()
    view = views(jobs=queue, manager=manager)
    empty_at_first = view.shows_empty_notice
    assert empty_at_first and view.focus_chain() == []

    queue.add(make_job("job-1", tmp_path))
    view.refresh()

    empty_after = view.shows_empty_notice
    assert not empty_after, "the empty notice is still showing over a queued job"
    assert not view.table.isHidden()
    assert view.focus_chain() == [view.table]


# --- 4. the repaint rate, measured with N rows ------------------------------------------------


def test_a_burst_across_many_rows_costs_one_repaint(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`NFR-001` with N rows, which is the case `T-017`'s single-job measurement cannot reach.

    Eight jobs, fifty messages each. The rates **add**: a per-message repaint costs four hundred
    here where it cost fifty with one job, which is why "bounded repaint cost" is a criterion of
    this task rather than something inherited.

    The number asserted is `renders` — ticks that drew — because that is what the promise is
    about. A per-row timer would satisfy "at most ten a second *per row*" while redrawing the
    screen eighty times a second, so the count deliberately does not scale with the pool.

    Constructed messages: the claim is about arrival rate, and eight real workers cannot be asked
    to emit four hundred messages inside one interval on demand.
    """
    job_ids = [f"job-{index}" for index in range(8)]
    for position, job_id in enumerate(job_ids):
        queue.add(make_job(job_id, tmp_path, status=JobStatus.RUNNING, queue_position=position))
    manager = managers(concurrency=8)
    view = views(jobs=queue, manager=manager, repaint_interval_ms=100)

    for round_number in range(50):
        for job_id in job_ids:
            view.model._on_progress(
                Progress(
                    job_id=job_id,
                    stage=Stage.DOWNLOADING_VIDEO,
                    downloaded_bytes=round_number + 1,
                    total_bytes=50,
                )
            )

    assert view.model.renders == 0, (
        f"the table repainted {view.model.renders} times while messages were still arriving; "
        "four hundred messages inside one interval is the burst this rate limit exists for"
    )
    assert view.model.pending_job_ids == tuple(sorted(job_ids)), (
        "a burst must coalesce per job, not drop rows"
    )

    assert spin_until(qapp, lambda: view.model.renders > 0)
    assert view.model.renders == 1, (
        f"{view.model.renders} repaints for one interval's worth of messages across eight rows; "
        "the budget belongs to the repaint, not to each row"
    )
    for job_id in job_ids:
        drawn = view.model.displayed_progress(job_id)
        assert drawn is not None and drawn.downloaded_bytes == 50, (
            f"{job_id} kept an intermediate message rather than the newest of its burst"
        )


def test_absorbing_a_burst_across_many_rows_stays_inside_the_budget(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """Coalescing is only useful if *arrival* is cheap, and arrival now happens N times as often.

    `NFR-001` budgets ~100 ms for an interaction. Four hundred messages arriving is not an
    interaction, but it competes with one on the same thread.
    """
    job_ids = [f"job-{index}" for index in range(8)]
    for job_id in job_ids:
        queue.add(make_job(job_id, tmp_path, status=JobStatus.RUNNING))
    manager = managers(concurrency=8)
    view = views(jobs=queue, manager=manager)
    messages = [
        Progress(
            job_id=job_id, stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=index, total_bytes=50
        )
        for index in range(50)
        for job_id in job_ids
    ]

    started = time.perf_counter()
    for message in messages:
        view.model._on_progress(message)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.05, (
        f"four hundred progress messages took {elapsed * 1000:.1f} ms to absorb across eight "
        "rows, against NFR-001's ~100 ms budget for a whole interaction"
    )


def test_a_status_change_does_not_flush_pending_progress(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """`T017-R1`'s finding, and with N jobs there are N streams of status changes to ride in on.

    A status change is drawn at once because it is the newer fact — but drawing *progress* from
    it is a second route into rendering with no rate limit on it.
    """
    queue.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    manager = managers()
    view = views(jobs=queue, manager=manager, repaint_interval_ms=10_000)

    view.model._on_progress(
        Progress(
            job_id="job-1", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=500, total_bytes=1000
        )
    )
    queue.update(replace(queue.jobs["job-1"], status=JobStatus.POST_PROCESSING))
    view.model._on_job_changed("job-1", JobStatus.POST_PROCESSING.value)

    assert view.model.renders == 0, (
        "a status change drew the pending progress message, which is a second unrated route "
        "into rendering (T017-R1)"
    )
    assert view.model.pending_job_ids == ("job-1",)
    assert view.model.text_at("job-1", STATUS_COLUMN) == "Post-processing", (
        "the status change itself was not shown; it is the newer fact and is not rate limited"
    )


def test_an_ending_drops_progress_that_can_no_longer_be_true(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """Deferred would mean drawing the download a tick after it stopped happening."""
    queue.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    manager = managers()
    view = views(jobs=queue, manager=manager, repaint_interval_ms=10_000)

    view.model._on_progress(
        Progress(
            job_id="job-1", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=500, total_bytes=1000
        )
    )
    queue.update(replace(queue.jobs["job-1"], status=JobStatus.CANCELLED))
    view.model._on_job_changed("job-1", JobStatus.CANCELLED.value)

    assert view.model.pending_job_ids == (), (
        "a message from before the ending is still queued to be drawn over it"
    )


# --- 5. ordering, and what a cell says ---------------------------------------------------------


def test_rows_are_ordered_by_queue_position_and_not_by_arrival(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """The same order the scheduler drains in (`T-078`), because two answers to "next" is worse.

    Added in the opposite order to their positions, so a table that kept insertion order — which
    is what `FakeQueue.all_jobs` deliberately returns — fails rather than coincidentally passes.
    """
    for job_id, position in (("job-c", 2), ("job-a", 0), ("job-b", 1)):
        queue.add(make_job(job_id, tmp_path, queue_position=position))
    manager = managers()
    view = views(jobs=queue, manager=manager)

    assert view.model.job_ids() == ("job-a", "job-b", "job-c"), (
        f"rows are in {view.model.job_ids()}, which is the order they were added rather than "
        "the order they will run"
    )


def test_a_job_with_no_queue_position_sorts_last_rather_than_first(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """`queue_position` is optional, and `None` is not zero — the scheduler says the same."""
    queue.add(make_job("job-a", tmp_path, queue_position=5))
    queue.add(make_job("job-z", tmp_path, queue_position=None))

    manager = managers()
    view = views(jobs=queue, manager=manager)

    assert view.model.job_ids() == ("job-a", "job-z"), (
        "a job with no queue position sorted ahead of a placed one, which would make it look "
        "like the next thing to run"
    )


def test_every_column_req_014_names_is_on_screen(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`REQ-014` lists five things per job; the sixth column says which job it is.

    Asserted as *content*, not as headers: a table can carry six headings over empty cells.
    """
    queue.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING, title="A video"))
    manager = managers()
    view = views(jobs=queue, manager=manager, repaint_interval_ms=10)

    view.model._on_progress(
        Progress(
            job_id="job-1",
            stage=Stage.DOWNLOADING_AUDIO,
            downloaded_bytes=512,
            total_bytes=1024,
            speed_bytes_per_second=1024,
            eta_seconds=61,
        )
    )
    assert spin_until(qapp, lambda: view.model.displayed_progress("job-1") is not None)

    assert view.model.text_at("job-1", JOB_COLUMN) == "A video"
    assert view.model.text_at("job-1", STATUS_COLUMN) == "Downloading audio"
    assert view.model.text_at("job-1", PROGRESS_COLUMN) == "50%"
    assert view.model.text_at("job-1", SIZE_COLUMN) == "512 B of 1.0 KB"
    assert view.model.text_at("job-1", SPEED_COLUMN) == "1.0 KB/s"
    assert view.model.text_at("job-1", ETA_COLUMN) == "1:01"
    assert len(COLUMN_HEADERS) == 6


def test_the_drawn_row_carries_every_field_the_columns_do(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`T-119`: one rich row instead of a grid — **and not one field fewer**.

    The rich row is drawn from roles while `REQ-014`'s per-field vocabulary stays. This is what
    stops the two diverging: every column's text must be findable in what the delegate is handed,
    so a field that stops reaching the drawn row fails here rather than quietly disappearing off
    a surface nobody re-reads.

    Asserted **by value** (`T-119`), through the model's roles, rather than off the painted image.
    """
    queue.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING, title="A video"))
    view = views(jobs=queue, manager=managers(), repaint_interval_ms=10)

    view.model._on_progress(
        Progress(
            job_id="job-1",
            stage=Stage.DOWNLOADING_AUDIO,
            downloaded_bytes=512,
            total_bytes=1024,
            speed_bytes_per_second=1024,
            eta_seconds=61,
        )
    )
    assert spin_until(qapp, lambda: view.model.displayed_progress("job-1") is not None)

    index = view.model.index(0, JOB_COLUMN)
    headline = view.model.data(index, HEADLINE_ROLE)
    detail = view.model.data(index, DETAIL_ROLE)
    state = view.model.data(index, STATE_ROLE)

    assert headline == view.model.text_at("job-1", JOB_COLUMN)
    assert state == view.model.text_at("job-1", STATUS_COLUMN)
    for column in (PROGRESS_COLUMN, SIZE_COLUMN, SPEED_COLUMN, ETA_COLUMN):
        cell = view.model.text_at("job-1", column)
        assert cell is not None and cell in detail, (
            f"{COLUMN_HEADERS[column]} reads {cell!r} in the column and is missing from the "
            f"drawn row: {detail!r}"
        )

    # The bar is drawn from the same numbers the percentage is, so it cannot say something else.
    assert view.model.data(index, PROGRESS_ROLE) == pytest.approx(0.5)
    # And `REQ-002`'s picture, for the row that has one.
    assert view.model.data(index, THUMBNAIL_URL_ROLE) is None, "this job was never given one"
    assert isinstance(view.model.data(index, HUE_ROLE), int), (
        "no derived tile for a row with no picture"
    )


def test_the_drawn_row_is_spoken_whole_to_a_screen_reader(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`NFR-005`: everything a sighted user reads from the row is available to a screen reader.

    The list draws column 0, so column 0 is the whole row to anyone listening — announcing only
    "Job: A video" there would hide five fields that are on screen. The per-column announcements
    stay for a caller that asks for one.
    """
    queue.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING, title="A video"))
    view = views(jobs=queue, manager=managers(), repaint_interval_ms=10)

    view.model._on_progress(
        Progress(
            job_id="job-1", stage=Stage.DOWNLOADING_AUDIO, downloaded_bytes=512, total_bytes=1024
        )
    )
    assert spin_until(qapp, lambda: view.model.displayed_progress("job-1") is not None)

    spoken = view.model.data(view.model.index(0, JOB_COLUMN), Qt.ItemDataRole.AccessibleTextRole)

    assert isinstance(spoken, str)
    for column in range(len(COLUMN_HEADERS)):
        announced = view.model.accessible_text_at("job-1", column)
        assert announced is not None and announced in spoken, (
            f"{COLUMN_HEADERS[column]} is drawn but never spoken: {spoken!r}"
        )


def test_a_row_names_the_url_when_no_probe_found_a_title(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """A row nobody can identify is worse than a long URL."""
    queue.add(make_job("job-1", tmp_path, title=None))
    manager = managers()
    view = views(jobs=queue, manager=manager)

    assert view.model.text_at("job-1", JOB_COLUMN) == "https://example.invalid/job-1"


def test_an_unknown_total_is_stated_and_never_rendered_as_zero_percent(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`REQ-011`'s indeterminate state. `0%` would be a confident lie, and a live stream has no
    total at all."""
    queue.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    manager = managers()
    view = views(jobs=queue, manager=manager, repaint_interval_ms=10)

    view.model._on_progress(
        Progress(
            job_id="job-1", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=900, total_bytes=None
        )
    )
    assert spin_until(qapp, lambda: view.model.displayed_progress("job-1") is not None)

    assert view.model.text_at("job-1", PROGRESS_COLUMN) == INDETERMINATE_TEXT, (
        "an unknown total was rendered as a percentage of nothing"
    )
    assert view.model.accessible_text_at("job-1", PROGRESS_COLUMN) == (
        "Total size unknown; progress cannot be measured"
    )
    # **And the drawn bar refuses it too** (`T-119`). The text and the bar are two renderings of
    # one fact, so a bar sitting at zero beside "—" would be the graphical half telling the lie
    # the textual half was written to avoid.
    assert view.model.data(view.model.index(0, JOB_COLUMN), PROGRESS_ROLE) is None, (
        "an unknown total drew a progress bar at zero"
    )


# --- 6. what a screen reader hears (`NFR-005`) -------------------------------------------------


def test_the_progress_column_is_described_by_the_same_function_as_the_bar(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`T017-R2` was sighted and screen-reader users told different things about one download.

    Avoided by there being one function rather than an agreement between two, so this asserts the
    table's accessible text **is** `describe_bar`'s output — not that it resembles it.
    """
    queue.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    manager = managers()
    view = views(jobs=queue, manager=manager, repaint_interval_ms=10)

    view.model._on_progress(
        Progress(
            job_id="job-1", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=470, total_bytes=1000
        )
    )
    assert spin_until(qapp, lambda: view.model.displayed_progress("job-1") is not None)

    assert view.model.accessible_text_at("job-1", PROGRESS_COLUMN) == describe_bar(
        470, 1000, finished=False
    )
    assert view.model.text_at("job-1", PROGRESS_COLUMN) == "47%", (
        "the visible cell and the description are describing different downloads"
    )


def test_a_completed_row_is_described_as_complete_and_not_as_a_percentage(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """The `finished` half of `describe_bar`, which no percentage carries."""
    queue.add(
        make_job("job-1", tmp_path, status=JobStatus.COMPLETED, bytes_done=1, bytes_total=2048)
    )
    manager = managers()
    view = views(jobs=queue, manager=manager)

    assert view.model.accessible_text_at("job-1", PROGRESS_COLUMN) == describe_bar(
        2048, 2048, finished=True
    )


def test_every_other_column_announces_which_column_it_is(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """A cell read out as `Queued` says nothing about what is queued (`NFR-005`)."""
    queue.add(make_job("job-1", tmp_path, title="A video"))
    manager = managers()
    view = views(jobs=queue, manager=manager)

    assert view.model.accessible_text_at("job-1", STATUS_COLUMN) == "Status: Queued"
    assert view.model.accessible_text_at("job-1", JOB_COLUMN) == "Job: A video"


# --- 7. keeping up with a queue that changes ---------------------------------------------------


def test_a_job_this_table_has_not_seen_appears_rather_than_being_ignored(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """A job added after the table was built announces itself by changing state.

    Without this the row would appear only at the next unrelated change — which, in a queue with
    one job in it, is never.
    """
    manager = managers()
    view = views(jobs=queue, manager=manager)
    assert view.model.job_ids() == ()

    queue.add(make_job("job-1", tmp_path, status=JobStatus.PROBING))
    view.model._on_job_changed("job-1", JobStatus.PROBING.value)

    assert view.model.job_ids() == ("job-1",), (
        "a job that started while the table was open never got a row"
    )
    assert not view.shows_empty_notice


def test_a_refresh_keeps_what_each_row_has_already_drawn(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`refresh` rebuilds rows, and `displayed` is the one thing the durable row cannot restore.

    It is also what `totals_for_ending` turns on, so losing it would make a job cancelled at 50%
    redraw at the row's stale count — `T017-R4`, arriving through a rebuild instead of a call
    site.
    """
    queue.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING, bytes_done=10))
    manager = managers()
    view = views(jobs=queue, manager=manager, repaint_interval_ms=10)

    view.model._on_progress(
        Progress(
            job_id="job-1", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=500, total_bytes=1000
        )
    )
    assert spin_until(qapp, lambda: view.model.displayed_progress("job-1") is not None)

    queue.add(make_job("job-2", tmp_path, queue_position=1))
    view.refresh()

    drawn = view.model.displayed_progress("job-1")
    assert drawn is not None and drawn.downloaded_bytes == 500, (
        "a rebuild forgot what the row had drawn, so the next ending would be taken from the "
        "durable row's lagging counter instead (T017-R4)"
    )
    assert view.model.text_at("job-1", PROGRESS_COLUMN) == "50%"


def test_a_message_for_a_job_not_in_the_table_is_not_held(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """Otherwise `_pending` grows without bound behind a job that was removed."""
    queue.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    manager = managers()
    view = views(jobs=queue, manager=manager, repaint_interval_ms=10_000)

    view.model._on_progress(
        Progress(job_id="ghost", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=1, total_bytes=2)
    )

    assert view.model.pending_job_ids == (), (
        "a message for a job with no row was kept, so nothing will ever draw or discard it"
    )


def test_selecting_a_row_reports_which_job_it_is(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """The table reports; the shell decides what to do about it (`ARCHITECTURE.md` §3)."""
    for position, job_id in enumerate(("job-a", "job-b")):
        queue.add(make_job(job_id, tmp_path, queue_position=position))
    manager = managers()
    view = views(jobs=queue, manager=manager)

    seen: list[str] = []
    view.job_selected.connect(seen.append)

    assert view.select("job-b")
    assert seen == ["job-b"], f"selection reported {seen}"
    assert view.selected_job_id() == "job-b"
    assert not view.select("job-missing")


# --- 8. the attempt boundary (`T079-R1`) -------------------------------------------------------


def test_retrying_a_job_retires_the_failed_attempts_live_state(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`T079-R1`: a drawn message describes **the attempt that produced it**.

    `REQ-018`'s retry edge is `FAILED → QUEUED`, and a job in `QUEUED` has no worker — so what was
    drawn belongs to the attempt that failed. Left in place, the re-queued row went on saying
    "Downloading video" at the old percentage, speed and ETA, and a saturated pool can leave that
    on screen for as long as the retry waits for a slot.

    **The durable row is deliberately behind the drawn message** here — 10% stored against 50%
    drawn — because that is the only way to tell "retired the message" from "kept it". A test
    where the two agree passes whether or not the boundary exists. That lag is not contrived:
    `manager.py` does not persist progress per message, so the row lags by design while a job
    runs.
    """
    queue.add(
        make_job("job-1", tmp_path, status=JobStatus.RUNNING, bytes_done=100, bytes_total=1000)
    )
    manager = managers()
    view = views(jobs=queue, manager=manager, repaint_interval_ms=10)

    view.model._on_progress(
        Progress(
            job_id="job-1",
            stage=Stage.DOWNLOADING_VIDEO,
            downloaded_bytes=500,
            total_bytes=1000,
            speed_bytes_per_second=2_200_000,
            eta_seconds=42,
        )
    )
    assert spin_until(qapp, lambda: view.model.displayed_progress("job-1") is not None)
    assert view.model.text_at("job-1", STATUS_COLUMN) == "Downloading video"
    assert view.model.text_at("job-1", PROGRESS_COLUMN) == "50%"

    queue.update(replace(queue.jobs["job-1"], status=JobStatus.FAILED))
    view.model._on_job_changed("job-1", JobStatus.FAILED.value)
    queue.update(replace(queue.jobs["job-1"], status=JobStatus.QUEUED))
    view.model._on_job_changed("job-1", JobStatus.QUEUED.value)

    assert view.model.text_at("job-1", STATUS_COLUMN) == "Queued", (
        "a re-queued job is still describing the stage of the attempt that failed"
    )
    assert view.model.displayed_progress("job-1") is None, (
        "the failed attempt's message is still the row's live message"
    )
    assert view.model.text_at("job-1", PROGRESS_COLUMN) == "10%", (
        "the re-queued row reports the failed attempt's 50% rather than the durable row's 10%"
    )
    assert view.model.text_at("job-1", SIZE_COLUMN) == "100 B of 1000 B", (
        "the re-queued row reports the bytes the failed attempt drew"
    )
    assert view.model.text_at("job-1", SPEED_COLUMN) == UNKNOWN_TEXT, (
        "a queued job has no worker and cannot have a speed"
    )
    assert view.model.text_at("job-1", ETA_COLUMN) == UNKNOWN_TEXT, (
        "a queued job has no worker and cannot have an estimated time remaining"
    )


def test_a_retry_also_drops_a_message_that_was_never_drawn(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """The other half of the boundary: *pending* is previous-attempt state too.

    A message still waiting for its tick when the job failed would otherwise be drawn onto the
    retry, which is the same lie arriving one interval later.
    """
    queue.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    manager = managers()
    view = views(jobs=queue, manager=manager, repaint_interval_ms=10_000)

    view.model._on_progress(
        Progress(
            job_id="job-1", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=500, total_bytes=1000
        )
    )
    # Locals for the same reason as elsewhere in this file: mypy narrows the property across
    # asserts, and the second comparison would be typed as non-overlapping rather than run.
    before = view.model.pending_job_ids
    assert before == ("job-1",)

    queue.update(replace(queue.jobs["job-1"], status=JobStatus.QUEUED))
    view.model._on_job_changed("job-1", JobStatus.QUEUED.value)

    after = view.model.pending_job_ids
    assert after == (), (
        "a message from the failed attempt is still queued to be drawn onto the retry"
    )


def test_a_rebuild_still_keeps_drawn_state_inside_one_attempt(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """The boundary is an *attempt* boundary, not "delete on every rebuild" (`T079-R1`).

    Unconditional deletion would pass the retry test above and break `T017-R4`: a newly added
    neighbour would erase the live total of a still-running job, and its ending would then be
    taken from the durable row's lagging counter. Both halves are needed, so both are asserted.
    """
    queue.add(
        make_job("job-1", tmp_path, status=JobStatus.RUNNING, bytes_done=100, bytes_total=1000)
    )
    manager = managers()
    view = views(jobs=queue, manager=manager, repaint_interval_ms=10)

    view.model._on_progress(
        Progress(
            job_id="job-1", stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=500, total_bytes=1000
        )
    )
    assert spin_until(qapp, lambda: view.model.displayed_progress("job-1") is not None)

    queue.add(make_job("job-2", tmp_path, queue_position=1))
    view.refresh()

    assert view.model.text_at("job-1", PROGRESS_COLUMN) == "50%", (
        "adding a neighbour erased a running job's drawn progress; the attempt did not end"
    )


# --- 9. what a status change is allowed to read (`T079-R2`) ------------------------------------


def test_a_status_change_does_not_enumerate_the_queue(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """`T079-R2`, `ARCHITECTURE.md` §3: a synchronous GUI read must be an indexed single-row one.

    This slot used to find one job by scanning `all_jobs()`, which in the real graph is
    `SELECT *` plus deserialisation of every stored job — so the cost of *every* transition grew
    with queue history, inside the Qt slot.

    Counted rather than timed, because a count is the claim: "does not enumerate" is a statement
    about which read happens, and a fast enumeration is still an enumeration.
    """
    for position, job_id in enumerate(("job-1", "job-2", "job-3")):
        queue.add(make_job(job_id, tmp_path, status=JobStatus.RUNNING, queue_position=position))
    manager = managers()
    view = views(jobs=queue, manager=manager)

    queue.enumerations = 0
    queue.lookups = 0
    queue.update(replace(queue.jobs["job-2"], status=JobStatus.POST_PROCESSING))
    view.model._on_job_changed("job-2", JobStatus.POST_PROCESSING.value)

    assert queue.enumerations == 0, (
        f"a status change enumerated the whole queue {queue.enumerations} time(s); every "
        "transition would then cost one full table read on the GUI thread"
    )
    assert queue.lookups == 1, f"expected exactly one indexed lookup, got {queue.lookups}"
    assert view.model.text_at("job-2", STATUS_COLUMN) == "Post-processing", (
        "the transition was not actually applied, so the counts above prove nothing"
    )


def test_a_status_change_stays_inside_the_budget_when_enumeration_is_slow(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """The same claim as a number (`NFR-001`), with the enumeration made expensive.

    A reviewer's probe measured one transition spending **150.7 ms** in this slot against
    `NFR-001`'s ~100 ms interaction budget, using a reader whose full read was slow. The
    committed tests could not see it because three rows are cheap to enumerate however wrongly
    the read is chosen — which is why this makes the enumeration slow rather than the queue long.
    """
    queue.add(make_job("job-1", tmp_path, status=JobStatus.RUNNING))
    manager = managers()
    view = views(jobs=queue, manager=manager)

    queue.update(replace(queue.jobs["job-1"], status=JobStatus.POST_PROCESSING))
    queue.enumeration_delay = 0.25

    started = time.perf_counter()
    view.model._on_job_changed("job-1", JobStatus.POST_PROCESSING.value)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.1, (
        f"one status change spent {elapsed * 1000:.1f} ms on the GUI thread against NFR-001's "
        "~100 ms budget, because it read the whole queue to find one job"
    )
