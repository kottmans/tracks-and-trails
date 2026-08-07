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
from typing import Any, Final

import pytest
from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtGui import QFontMetrics, QImage, QKeyEvent, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QStyleOptionViewItem

from tests.qt_lifecycle import drain
from tests.ui.test_row_delegate import REPAINT_BUDGET_SECONDS, VIEWPORT_ROWS
from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import DownloadRequest, Job
from tracks_and_trails.core.paths import thumbnail_cache_path
from tracks_and_trails.core.presets import AUDIO_MP3, BEST_VIDEO, MP3_QUALITY, to_request
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
    DEPTH_ROLE,
    DETAIL_ROLE,
    EXPANDED_ROLE,
    HEADLINE_ROLE,
    HUE_ROLE,
    PRESET_CHOICES_ROLE,
    PRESET_PLACEHOLDER_ROLE,
    PRESET_ROLE,
    PROGRESS_ROLE,
    SEGMENTS_ROLE,
    SELECTOR_ROLE,
    STATE_CHIP_ROLE,
    STATE_ROLE,
    THUMBNAIL_URL_ROLE,
    VERBS_ROLE,
    RowDelegate,
    SegmentState,
)
from tracks_and_trails.ui.row_verbs import LABELS, Verb

#: What every surface must call a default MP3 download (`T-156`).
#:
#: **The wording is transcribed here and the two values are read from the catalogue**
#: (`ai/TESTING.md` §13). Writing `"Audio only (MP3), 192 kbps"` outright would restate the preset
#: name and the bitrate that production already declares, and the test would then pass while the
#: catalogue said something else; asking `format_name` for the answer would be asking production
#: what to expect. This states the *rule* — the name, a comma, the bitrate, `kbps` — and takes the
#: facts from `presets.py`.
MP3_TEXT: Final = f"{AUDIO_MP3.name}, {MP3_QUALITY} kbps"


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
    queue.put(Succeeded(job_id=job_id, output_path=output))
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


def test_a_finished_probe_does_not_outlive_the_ready_status(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """Phase 2 criterion 1: a row's visible state must be accurate."""
    queue.add(make_job("job-1", tmp_path, status=JobStatus.PROBING))
    view = views(jobs=queue, manager=managers())
    view.model._on_progress(Progress(job_id="job-1", stage=Stage.PROBING))
    view.model._draw_pending()

    queue.update(replace(queue.jobs["job-1"], status=JobStatus.READY))
    view.model._on_job_changed("job-1", JobStatus.READY.value)
    index = view.model.index(0, 0)

    assert view.model.data(index, STATE_ROLE) == "Ready to download"
    assert view.model.data(index, STATE_CHIP_ROLE) == "Ready", (
        "the row's state and chip contradict one another after its probe finishes"
    )


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


@pytest.mark.parametrize(
    ("status", "expected_chip"),
    [
        (JobStatus.RUNNING, "62%"),
        (JobStatus.COMPLETED, "Done"),
        (JobStatus.FAILED, "Failed"),
        (JobStatus.QUEUED, "Queued"),
    ],
)
def test_the_state_chip_reads_progress_only_while_a_job_is_actually_running(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    status: JobStatus,
    expected_chip: str,
) -> None:
    """`T130-R3`: `UX-005`'s chip vocabulary is `Done`, `Queued`, `62%`, `Failed`.

    **Every row here carries the same bytes**, and that is the whole design of the case. The chip
    used to be derived from the fraction alone, and `_fraction` answers exactly 1.0 for a completed
    job — so completion rendered as `100%` on every finished row in the queue. Holding the bytes
    still and moving only the status is what separates "how far along the bytes are" from "whether
    the work is still happening", which is the distinction the defect collapsed.

    `Done` is asserted as a literal rather than through `CHIP_TEXT`, because the word is the
    ruling: read from the map, this would keep passing if the map were changed to `Completed`.
    """
    queue.add(make_job("job-1", tmp_path, status=status, bytes_done=620, bytes_total=1000))
    manager = managers()
    view = views(jobs=queue, manager=manager)

    chip = view.model.data(view.model.index(0, 0), STATE_CHIP_ROLE)
    assert chip == expected_chip, (
        f"a {status.name} row chips {chip!r} rather than {expected_chip!r}; UX-005 gives the chip "
        "its own compact vocabulary, and a percentage is a running-progress shape only"
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


# --- T-140: a playlist as a row that opens ----------------------------------------------------


def _playlist_jobs(tmp_path: Path, count: int, *, playlist_id: str = "pl-1") -> list[Job]:
    """`count` entries of one playlist, in the playlist's own order."""
    return [
        make_job(
            f"entry-{index}",
            tmp_path,
            status=JobStatus.COMPLETED if index == 0 else JobStatus.QUEUED,
            queue_position=index,
            playlist_id=playlist_id,
            playlist_index=index,
            playlist_title="Trail Sounds",
        )
        for index in range(count)
    ]


def test_a_playlist_is_one_row_until_it_is_opened(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """`UX-005` row 9: closed, a playlist costs exactly one row.

    That is the whole reason the shape was chosen over sixteen loose rows — a sixteen-item paste
    has to survive beside ordinary downloads. Asserted by **row count**, not by pixels: the claim
    is about what the table holds, and a pixel comparison would pass with sixteen rows drawn
    identically.
    """
    for job in _playlist_jobs(tmp_path, 4):
        queue.add(job)
    queue.add(make_job("solo", tmp_path, status=JobStatus.QUEUED, queue_position=9))
    view = views(jobs=queue, manager=managers())

    assert view.model.rowCount() == 2, (
        f"a four-entry playlist and one ordinary download show {view.model.rowCount()} rows; "
        "closed, the playlist must be one of them"
    )

    header = view.model.index(0, 0)
    assert view.model.data(header, EXPANDED_ROLE) is False
    view.model.toggle_group("pl-1")

    assert view.model.rowCount() == 6, (
        f"opening the playlist showed {view.model.rowCount()} rows; it must be the header, its "
        "four entries and the unrelated download"
    )
    assert view.model.data(view.model.index(0, 0), EXPANDED_ROLE) is True
    assert view.model.data(view.model.index(1, 0), DEPTH_ROLE) == 1, (
        "an entry is not nested under its group, so it reads as an unrelated row"
    )


def test_a_groups_chip_counts_and_never_measures(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """`UX-005` row 9a: `4 of 16`, not a percentage.

    The entries' byte totals arrive one at a time, so a fraction across them has a denominator
    that grows while it runs and a bar that goes *backwards*. Every entry here carries **the same
    bytes** and only the statuses differ, so a chip reading a percentage would be visibly wrong.
    """
    for job in _playlist_jobs(tmp_path, 4):
        queue.add(job)
    view = views(jobs=queue, manager=managers())

    chip = view.model.data(view.model.index(0, 0), STATE_CHIP_ROLE)

    assert chip == "1 of 4", f"the group's chip reads {chip!r} rather than a count of its members"
    assert "%" not in str(chip), (
        "the group's chip measures rather than counts, which UX-005 row 9a refuses because the "
        "denominator grows while the download runs"
    )


def test_a_closed_playlist_says_which_format_its_entries_inherit(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """Reviewer regression for `UX-005` row 9c and the adopted playlist mock.

    The short children deliberately drop their format line because the group is meant to carry
    the common value.  If the header answers no selector either, closing the group removes the
    effective download format from every visible row.
    """
    for job in _playlist_jobs(tmp_path, 3):
        queue.add(job)
    view = views(jobs=queue, manager=managers())

    shown = view.model.data(view.model.index(0, 0), SELECTOR_ROLE)

    assert isinstance(shown, str) and shown, (
        "the closed playlist says no format while every hidden child drops its own format line; "
        "the adopted mock puts 'Download as' on the group precisely because children inherit it"
    )


def test_a_closed_playlist_names_its_common_builtin_rather_than_its_selector(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """`T140-R3`: the group displays the preset name that its editor offers.

    A nonempty selector is not sufficient evidence.  Built-ins are offered and selected by name,
    and the ordinary row's `_effective_format_text()` deliberately shows that name instead of
    exposing yt-dlp syntax.  The playlist header must describe the same request the same way.
    """
    for job in _playlist_jobs(tmp_path, 3):
        queue.add(
            replace(
                job,
                request=to_request(
                    BEST_VIDEO,
                    url=job.url,
                    output_directory=str(tmp_path),
                ),
            )
        )
    view = views(jobs=queue, manager=managers())

    shown = view.model.data(view.model.index(0, JOB_COLUMN), SELECTOR_ROLE)

    assert shown == f"Download as: {BEST_VIDEO.name}", (
        f"the playlist names its common built-in as {shown!r}; the format editor offers "
        f"{BEST_VIDEO.name!r}, not that preset's raw yt-dlp selector"
    )


def test_a_playlists_one_format_can_be_changed_on_the_group_that_owns_it(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """Reviewer regression for `UX-005` row 13's group-retargeting half.

    Removing every child editor establishes only that children cannot diverge in the UI.  The
    ruling also moves the one format control to the group; a read-only header leaves no route to
    change the playlist format at all.
    """
    for job in _playlist_jobs(tmp_path, 3):
        queue.add(job)
    view = views(jobs=queue, manager=managers())
    header = view.model.index(0, JOB_COLUMN)

    choices = view.model.data(header, PRESET_CHOICES_ROLE)

    assert choices, (
        "the group displays its format but offers no editor; UX-005 row 13 says retargeting "
        "moves to the group rather than disappearing with the per-entry controls"
    )
    assert view.model.flags(header) & Qt.ItemFlag.ItemIsEditable


def test_choosing_on_the_group_retargets_every_member_that_can_still_move(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """`UX-005` row 13's *effect*, which the control's presence does not establish.

    The reviewer regression above proves a playlist offers an editor and that the header is
    editable.  Both would still hold if choosing did nothing at all — and `T140-R3` asked for
    retargeting to *honour group inheritance*, which is a claim about what happens to the members.

    `_playlist_jobs` makes the first entry `COMPLETED` and the rest `QUEUED`, so the exclusion is
    exercised rather than assumed: a finished track cannot be un-downloaded by changing a dropdown.
    """
    for job in _playlist_jobs(tmp_path, 3):
        queue.add(job)
    view = views(jobs=queue, manager=managers())
    header = view.model.index(0, JOB_COLUMN)

    chosen: list[tuple[str, str]] = []
    view.model.preset_chosen.connect(lambda job_id, name: chosen.append((job_id, name)))

    choices = view.model.data(header, PRESET_CHOICES_ROLE)
    target = next(name for name in choices if name != view.model.data(header, PRESET_ROLE))

    assert view.model.setData(header, target, PRESET_ROLE) is True

    assert [job_id for job_id, _ in chosen] == ["entry-1", "entry-2"], (
        f"the group retargeted {[j for j, _ in chosen]}; UX-005 row 13 moves every member that "
        "can still take a format, and entry-0 is COMPLETED so it cannot"
    )
    assert {name for _, name in chosen} == {target}, (
        "one choice on the group must reach the members as that same choice"
    )


def test_re_choosing_the_group_s_current_preset_emits_nothing(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """The same-value half of `setData`'s group guard (`T126-R3` at the group level).

    Previously disclosed as untestable, because `FakeQueue` does not apply a retarget — so with
    members built from `make_job`'s default request, every name is a real change and the guard
    could never be reached.  Building them from a **built-in preset** removes that: the group's
    current value is then a name the editor also offers, so re-selecting it is genuinely the
    no-op the guard exists for.

    It matters because a lifecycle commit re-sends the displayed value.  If that counted as a
    choice, the reset it causes would re-enter `setData` — which is exactly what `T126-R3` cost a
    round.
    """
    for job in _playlist_jobs(tmp_path, 3):
        queue.add(
            replace(
                job,
                request=to_request(BEST_VIDEO, url=job.url, output_directory=str(tmp_path)),
            )
        )
    view = views(jobs=queue, manager=managers())
    header = view.model.index(0, JOB_COLUMN)

    chosen: list[str] = []
    view.model.preset_chosen.connect(lambda job_id, _name: chosen.append(job_id))

    assert view.model.data(header, PRESET_ROLE) == BEST_VIDEO.name

    assert view.model.setData(header, BEST_VIDEO.name, PRESET_ROLE) is False
    assert chosen == [], "re-choosing the group's current preset emitted a retarget"

    # And the guard is not simply refusing everything: a different preset still moves the members
    # that can take it. Without this the test would pass against a `setData` that always returns
    # `False`, which is the shape of guard that silently disables a control.
    other = next(
        name for name in view.model.data(header, PRESET_CHOICES_ROLE) if name != BEST_VIDEO.name
    )
    assert view.model.setData(header, other, PRESET_ROLE) is True
    assert chosen == ["entry-1", "entry-2"]


def test_a_finished_playlist_refuses_a_group_retarget(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """The `not movable` half of `setData`'s group guard, which the header no longer offers.

    `PRESET_CHOICES_ROLE` already returns `None` once no member is retargetable, so the control is
    gone — but a model that answers a write it should refuse is one reset away from re-entering
    itself (`T126-R3`), and the delegate is not the only caller.

    The **same-value** half of that guard is deliberately not asserted here: `FakeQueue` does not
    apply a retarget, so the members keep their original request and re-sending a name is a genuine
    second change. Testing it against this fixture would measure the fixture, which is the shape
    `T126-R3` was.
    """
    for index in range(3):
        queue.add(
            make_job(
                f"entry-{index}",
                tmp_path,
                status=JobStatus.COMPLETED,
                queue_position=index,
                playlist_id="pl-1",
                playlist_index=index,
                playlist_title="Trail Sounds",
            )
        )
    view = views(jobs=queue, manager=managers())
    header = view.model.index(0, JOB_COLUMN)

    chosen: list[str] = []
    view.model.preset_chosen.connect(lambda job_id, _name: chosen.append(job_id))

    assert view.model.data(header, PRESET_CHOICES_ROLE) is None
    assert not view.model.flags(header) & Qt.ItemFlag.ItemIsEditable
    assert view.model.setData(header, "Audio only (MP3)", PRESET_ROLE) is False
    assert chosen == [], "a playlist with nothing left to move still emitted a retarget"


def test_a_groups_segments_come_from_its_members(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """`UX-005` row 9b, including the failure the bar exists to show.

    Under one continuous bar a playlist that quietly skipped a track looks exactly like one that
    got everything, so a **failed** entry must be its own segment rather than folded into "not
    done yet".
    """
    jobs = _playlist_jobs(tmp_path, 3)
    queue.add(jobs[0])
    queue.add(
        make_job(
            "entry-1",
            tmp_path,
            status=JobStatus.FAILED,
            queue_position=1,
            playlist_id="pl-1",
            playlist_index=1,
            playlist_title="Trail Sounds",
        )
    )
    queue.add(jobs[2])
    view = views(jobs=queue, manager=managers())

    segments = view.model.data(view.model.index(0, 0), SEGMENTS_ROLE)

    assert segments == [SegmentState.DONE, SegmentState.FAILED, SegmentState.WAITING], (
        f"the group's segments are {segments}; each block is one member's own state"
    )


def test_a_cancelled_playlist_is_not_described_as_a_failed_one(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """`T-165`. **Cancelled is not a kind of failure, and the header said it was.**

    One enum feeds the drawing and the words, so folding `CANCELLED` in beside `FAILED` made the
    group report `3 items · 3 failed` about downloads the user stopped on purpose — sending
    somebody to look for an error that does not exist.

    Asserted on the **words**, because that is the surface the claim is made on. The block state
    is checked beside it so the two cannot drift apart.
    """
    queue.add(
        make_job(
            "entry-0",
            tmp_path,
            status=JobStatus.CANCELLED,
            queue_position=0,
            playlist_id="pl-1",
            playlist_index=0,
            playlist_title="Trail Sounds",
        )
    )
    queue.add(
        make_job(
            "entry-1",
            tmp_path,
            status=JobStatus.FAILED,
            queue_position=1,
            playlist_id="pl-1",
            playlist_index=1,
            playlist_title="Trail Sounds",
        )
    )
    view = views(jobs=queue, manager=managers())
    header = view.model.index(0, 0)

    detail = view.model.data(header, DETAIL_ROLE)
    segments = view.model.data(header, SEGMENTS_ROLE)

    assert "cancelled" in detail, (
        f"the header says {detail!r}; one entry was cancelled and the line must say so"
    )
    assert "2 failed" not in detail, (
        f"the header says {detail!r}; only one entry failed, and calling the cancelled one a "
        "failure reports an error that never happened"
    )
    assert segments == [SegmentState.CANCELLED, SegmentState.FAILED], (
        f"the blocks are {segments}; cancelled and failed are different endings"
    )


def test_every_status_has_a_block_state(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """`T-165`, and `row_verbs`' rule about tables.

    The mapping used to end in an `else` that swept every unnamed status into *waiting*, which is
    where `CANCELLED` hid: it was never decided, only defaulted. Transcribed here from
    `JobStatus` rather than read back from the table, so adding a status without deciding what its
    block says fails this rather than quietly drawing it as *waiting*.
    """
    for index, status in enumerate(JobStatus):
        queue.add(
            make_job(
                f"entry-{index}",
                tmp_path,
                status=status,
                queue_position=index,
                playlist_id="pl-1",
                playlist_index=index,
                playlist_title="Trail Sounds",
            )
        )
    view = views(jobs=queue, manager=managers())

    segments = view.model.data(view.model.index(0, 0), SEGMENTS_ROLE)

    assert len(segments) == len(list(JobStatus)), (
        f"{len(segments)} blocks for {len(list(JobStatus))} statuses — every status must map"
    )
    assert all(isinstance(each, SegmentState) for each in segments), segments


def test_an_open_playlist_stays_open_across_a_refresh(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """Expansion is held **by id**, for `T126-R1`'s reason.

    A refresh rebuilds every row and a row number stops naming the same thing; a user who opened a
    playlist expects it to still be open when a download in it finishes. Progress causes refreshes
    constantly, so holding this by position would close the group under the user's hands.
    """
    for job in _playlist_jobs(tmp_path, 3):
        queue.add(job)
    view = views(jobs=queue, manager=managers())
    view.model.toggle_group("pl-1")
    assert view.model.rowCount() == 4

    queue.add(make_job("later", tmp_path, status=JobStatus.QUEUED, queue_position=7))
    view.model.refresh()

    assert view.model.data(view.model.index(0, 0), EXPANDED_ROLE) is True, (
        "the playlist closed itself when the queue changed"
    )
    assert view.model.rowCount() == 5


def test_a_hidden_entry_reports_no_row_of_its_own(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """A job inside a closed playlist has a model row and no line on screen.

    `None` is the honest answer: a caller building a `QModelIndex` from a hidden job would select
    whatever happened to sit at that number, which is `T118-R14`'s defect in a new place.
    """
    for job in _playlist_jobs(tmp_path, 3):
        queue.add(job)
    view = views(jobs=queue, manager=managers())

    assert view.model.row_of("entry-1") is None, (
        "a job hidden inside a closed playlist reports a row number, which addresses whatever is "
        "drawn there instead"
    )
    assert view.model.job_for("entry-1") is not None, (
        "the hidden job vanished from the model as well, so nothing could reopen it"
    )

    view.model.toggle_group("pl-1")
    assert view.model.row_of("entry-1") == 2


def test_selection_after_a_closed_playlist_names_the_row_that_is_visible(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """Reviewer regression for `T-140`: visible and durable row numbers are different.

    A closed playlist occupies one visible line while retaining all of its jobs underneath. The
    ordinary row after it must therefore resolve through the visible model role, not by applying
    its visible row number to the underlying job list.
    """
    for job in _playlist_jobs(tmp_path, 3):
        queue.add(job)
    queue.add(make_job("solo", tmp_path, queue_position=9))
    view = views(jobs=queue, manager=managers())

    assert view.model.rowCount() == 2, "the playlist is not collapsed, so the index spaces agree"
    view.table.setCurrentIndex(view.model.index(1, JOB_COLUMN))

    assert view.selected_job_id() == "solo", (
        "selecting the visible ordinary row resolved to a hidden playlist member; file and "
        "selection actions would target a job other than the one the user selected"
    )


def test_an_open_playlists_members_stay_beneath_its_header_after_reordering(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """Reviewer regression for `T-140`: moving a child must not tear its group in two."""
    first, second = _playlist_jobs(tmp_path, 2)
    queue.add(first)
    queue.add(make_job("solo", tmp_path, queue_position=1))
    queue.add(replace(second, queue_position=2))
    view = views(jobs=queue, manager=managers())

    view.model.toggle_group("pl-1")
    visible = [
        (
            view.model.data(view.model.index(row, 0), HEADLINE_ROLE),
            view.model.data(view.model.index(row, 0), DEPTH_ROLE),
        )
        for row in range(view.model.rowCount())
    ]

    assert visible[0][0] == "Trail Sounds"
    assert [depth for _, depth in visible[1:3]] == [1, 1], (
        f"the playlist's children are split by another download: {visible!r}; opening one row "
        "must reveal one contiguous set beneath it"
    )


def test_a_paste_of_150_with_every_group_open_stays_within_the_repaint_budget(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """**`T-140`'s own acceptance criterion, and `UX-005` says a bad number reopens the shape.**

    `setUniformItemSizes` came off for row 9c: an entry is two lines against its group's four, so
    the promise every row is the same height is false the moment a group is open. That promise is
    what lets a `QListView` compute its visible range arithmetically instead of measuring every
    row, and `T118-R10` is the record of what per-row cost buys when it goes wrong — a paste of
    150 cost 0.722 s on hosted Windows and a delegate fixed it.

    So this measures the case the ruling was made against: **150 entries across ten playlists,
    every one open**, laid out and painted. The budget is `REPAINT_BUDGET_SECONDS`' reasoning —
    generous by design, distinguishing "cost is proportional to the model" from "cost is
    proportional to the screen" and nothing finer, because sizing to the fastest machine is what
    made `T118-R10`'s gate flap between two runs of unchanged code.
    """
    for group in range(10):
        for index in range(15):
            queue.add(
                make_job(
                    f"g{group}-e{index}",
                    tmp_path,
                    status=JobStatus.QUEUED,
                    queue_position=group * 15 + index,
                    playlist_id=f"pl-{group}",
                    playlist_index=index,
                    playlist_title=f"Playlist {group}",
                )
            )
    view = views(jobs=queue, manager=managers())

    started = time.perf_counter()
    for group in range(10):
        view.model.toggle_group(f"pl-{group}")
    opened = time.perf_counter() - started

    assert view.model.rowCount() == 160, (
        f"ten open playlists of fifteen show {view.model.rowCount()} rows, not 160"
    )

    # **`sizeHint` per row is exactly what the dropped promise costs**, so that is what is
    # measured. An earlier version timed `repaint()` on an offscreen widget and reported 0.000s —
    # a number that cannot fail, from a call that may not have painted at all.
    delegate = view.table.itemDelegate()
    assert isinstance(delegate, RowDelegate)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 900, 90)
    option.font = view.table.font()
    option.fontMetrics = QFontMetrics(option.font)

    started = time.perf_counter()
    heights = [
        delegate.sizeHint(option, view.model.index(row, 0)).height()
        for row in range(view.model.rowCount())
    ]
    measured = time.perf_counter() - started

    image = QImage(900, 90 * VIEWPORT_ROWS, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    started = time.perf_counter()
    try:
        for slot in range(VIEWPORT_ROWS):
            option.rect = QRect(0, slot * 90, 900, 90)
            delegate.paint(painter, option, view.model.index(slot, 0))
    finally:
        painter.end()
    painted = time.perf_counter() - started

    print(
        f"\npaste of 150, all groups open — open {opened:.3f}s, "
        f"size {len(heights)} rows {measured:.3f}s, paint {VIEWPORT_ROWS} rows {painted:.3f}s"
    )
    assert len(set(heights)) > 1, (
        "every row measured the same height, so this is not exercising the non-uniform case the "
        "budget is about"
    )
    assert opened < REPAINT_BUDGET_SECONDS, (
        f"opening ten playlists of a 150-entry queue took {opened:.3f}s, over the "
        f"{REPAINT_BUDGET_SECONDS}s budget; the flattening is proportional to the model"
    )
    assert measured < REPAINT_BUDGET_SECONDS, (
        f"measuring {len(heights)} rows took {measured:.3f}s, over the "
        f"{REPAINT_BUDGET_SECONDS}s budget. This is the cost setUniformItemSizes was buying, and "
        "UX-005 row 9 says a bad number here justifies reopening the shape"
    )
    assert painted < REPAINT_BUDGET_SECONDS, (
        f"painting {VIEWPORT_ROWS} rows of a 160-row table took {painted:.3f}s, over the "
        f"{REPAINT_BUDGET_SECONDS}s budget"
    )


def test_a_playlist_opens_and_closes_from_the_keyboard(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """`T-140`'s accepted keyboard criterion, which `T140-R5` found accepted and unbuilt.

    The only disclosure route in source was a left-button release inside the twisty's rectangle.
    A keyboard user could reach the header, hear it announced as a playlist, and have no way to
    see inside it — `NFR-005`'s parity failing on the one row that hides other rows.

    Directional, not a toggle: `Right` on an already open group must leave it open. A toggle makes
    the outcome depend on state the user cannot see, and a screen-reader user is exactly who
    cannot.
    """
    for job in _playlist_jobs(tmp_path, 3):
        queue.add(job)
    view = views(jobs=queue, manager=managers())
    header = view.model.index(0, JOB_COLUMN)
    view._list.setCurrentIndex(header)

    assert view.model.data(header, EXPANDED_ROLE) is False
    assert view.model.rowCount() == 1, "a closed playlist is one row"

    QTest.keyClick(view._list, Qt.Key.Key_Right)
    assert view.model.data(view.model.index(0, JOB_COLUMN), EXPANDED_ROLE) is True
    assert view.model.rowCount() == 4, "opening a three-entry playlist shows its header and three"

    QTest.keyClick(view._list, Qt.Key.Key_Right)
    assert view.model.data(view.model.index(0, JOB_COLUMN), EXPANDED_ROLE) is True, (
        "Right closed an already open playlist; the keys are directional, not a toggle"
    )

    QTest.keyClick(view._list, Qt.Key.Key_Left)
    assert view.model.data(view.model.index(0, JOB_COLUMN), EXPANDED_ROLE) is False
    assert view.model.rowCount() == 1


def test_the_disclosure_keys_leave_an_ordinary_row_alone(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """The filter must not swallow `Left`/`Right` for a row that has nothing to disclose.

    `EXPANDED_ROLE` answers `None` off a group, and that is the whole guard. Asserted because a
    filter that consumed these keys everywhere would take them away from the list for ever, and
    nothing else would notice until something wanted them.
    """
    queue.add(make_job("solo", tmp_path, queue_position=0))
    view = views(jobs=queue, manager=managers())
    row = view.model.index(0, JOB_COLUMN)
    view._list.setCurrentIndex(row)

    assert view.model.data(row, EXPANDED_ROLE) is None
    assert (
        view.eventFilter(
            view._list,
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier),
        )
        is False
    )


def test_a_playlist_header_offers_the_mockups_verbs(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """`T-140`'s verb criterion, transcribed from `UX-005` row 9 rather than from the code.

    `Retry failed` **only when something failed** is the half stated as a criterion, so it is
    asserted in both directions. `Open` is absent by design: the entries share one folder and
    there is no single file to open.
    """
    jobs = _playlist_jobs(tmp_path, 3)
    for job in jobs:
        queue.add(job)
    view = views(jobs=queue, manager=managers())
    header = view.model.index(0, JOB_COLUMN)

    offered = view.model.data(header, VERBS_ROLE)
    assert Verb.CANCEL_ALL in offered, "a playlist with queued entries offers Cancel all"
    assert Verb.RETRY_FAILED not in offered, (
        f"offered {offered}; nothing failed, and a Retry failed that is usually a lie teaches the "
        "user to ignore it"
    )
    assert Verb.REVEAL in offered, "the first entry is COMPLETED, so there is a folder to show"
    assert Verb.OPEN not in offered, "row 9 gives a group no Open: there is no one file"
    assert Verb.REMOVE in offered

    assert LABELS[Verb.CANCEL_ALL] == "Cancel all"
    assert LABELS[Verb.REVEAL] == "Show in folder"


def test_a_group_offers_retry_failed_once_an_entry_fails(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """The other direction of the same criterion, with one member failed."""
    jobs = _playlist_jobs(tmp_path, 3)
    queue.add(jobs[0])
    queue.add(replace(jobs[1], status=JobStatus.FAILED))
    queue.add(jobs[2])
    view = views(jobs=queue, manager=managers())

    offered = view.model.data(view.model.index(0, JOB_COLUMN), VERBS_ROLE)
    assert Verb.RETRY_FAILED in offered


def test_a_group_never_offers_retry_for_drm(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """The group route must preserve the taxonomy's non-retryable safety boundary.

    Ordinary failed rows ask `is_retryable()` before offering Retry.  A playlist header is not a
    route around `REQ-EXCL-001`: DRM-protected members offer no retry and cannot be sent down the
    retry signal by a stale group action.
    """
    for job in _playlist_jobs(tmp_path, 2):
        queue.add(
            replace(
                job,
                status=JobStatus.FAILED,
                error_kind=ErrorKind.DRM_PROTECTED,
                error_message="This content is DRM protected.",
            )
        )
    view = views(jobs=queue, manager=managers())
    header = view.model.index(0, JOB_COLUMN)

    offered = view.model.data(header, VERBS_ROLE)
    assert Verb.RETRY_FAILED not in offered, (
        f"the DRM-only playlist offers {offered}; the ordinary row suppresses Retry because "
        "the product has no DRM workaround"
    )


def test_a_stale_group_action_never_routes_retry_for_drm(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """Hiding a group verb is not authority for its route to cross the DRM boundary."""
    for job in _playlist_jobs(tmp_path, 2):
        queue.add(
            replace(
                job,
                status=JobStatus.FAILED,
                error_kind=ErrorKind.DRM_PROTECTED,
                error_message="This content is DRM protected.",
            )
        )
    view = views(jobs=queue, manager=managers())
    retried: list[str] = []
    view.retry_requested.connect(retried.append)

    view._on_verb("pl-1", Verb.RETRY_FAILED)

    assert retried == [], f"the group retry route bypassed the DRM boundary for {retried}"


def test_group_retry_keeps_eligible_failures_beside_drm(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """The Critical guard filters members; it does not disable a mixed group's valid retry."""
    jobs = _playlist_jobs(tmp_path, 3)
    queue.add(
        replace(
            jobs[0],
            status=JobStatus.FAILED,
            error_kind=ErrorKind.DRM_PROTECTED,
            error_message="This content is DRM protected.",
        )
    )
    queue.add(
        replace(
            jobs[1],
            status=JobStatus.FAILED,
            error_kind=ErrorKind.NETWORK,
            error_message="The connection ended.",
        )
    )
    queue.add(jobs[2])
    view = views(jobs=queue, manager=managers())
    header = view.model.index(0, JOB_COLUMN)

    assert Verb.RETRY_FAILED in view.model.data(header, VERBS_ROLE)

    retried: list[str] = []
    view.retry_requested.connect(retried.append)
    view._on_verb("pl-1", Verb.RETRY_FAILED)

    assert retried == ["entry-1"], (
        f"mixed group retried {retried}; the NETWORK failure is eligible and DRM is permanent"
    )


def test_a_group_verb_acts_on_the_members_it_applies_to(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """`Retry failed` retries the failed ones and nothing else.

    The filtering is the behaviour: retrying all three would be a different and destructive
    reading of the same click, and a test that only counted signals would agree with both.
    """
    jobs = _playlist_jobs(tmp_path, 3)
    queue.add(jobs[0])
    queue.add(replace(jobs[1], status=JobStatus.FAILED))
    queue.add(jobs[2])
    view = views(jobs=queue, manager=managers())

    retried: list[str] = []
    view.retry_requested.connect(retried.append)
    view._on_verb("pl-1", Verb.RETRY_FAILED)

    assert retried == ["entry-1"], (
        f"retried {retried}; Retry failed must reach the failed members and only those"
    )


def test_removing_a_group_reports_every_member_for_one_confirmation(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """`DAT-005` §4: the shell is told the whole group so the question can name its count."""
    for job in _playlist_jobs(tmp_path, 3):
        queue.add(job)
    view = views(jobs=queue, manager=managers())

    asked: list[tuple[str, object]] = []
    view.group_remove_requested.connect(lambda pl, ids: asked.append((pl, ids)))
    view._on_verb("pl-1", Verb.REMOVE)

    assert asked == [("pl-1", ["entry-0", "entry-1", "entry-2"])]


def test_an_ordinary_rows_remove_is_not_routed_as_a_group(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """`Remove` and `Show in folder` are offered by ordinary rows too.

    Routing a group verb by the *verb* was tried and is wrong: it sends every row's Remove down
    the group path. The model deciding whether the id names a group is what makes the two id
    spaces separable, and this is the regression that says so.
    """
    queue.add(make_job("solo", tmp_path, queue_position=0, status=JobStatus.FAILED))
    view = views(jobs=queue, manager=managers())

    removed: list[str] = []
    grouped: list[str] = []
    view.remove_requested.connect(removed.append)
    view.group_remove_requested.connect(lambda pl, _ids: grouped.append(pl))
    view._on_verb("solo", Verb.REMOVE)

    assert removed == ["solo"], "an ordinary row's Remove must stay on the single-job route"
    assert grouped == []


def test_a_retargeted_playlist_says_which_entries_got_which_format(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """`T-157` / `UX-005` amended 2026-08-05: divergence must be reportable, not merely honest.

    **Retargeting a part-done playlist splits its formats by design.** `T140-R3` moves every member
    that can still move, and a finished track cannot — so four completed entries keep the old
    format while twelve queued ones take the new. Before this the header said *mixed across 2
    formats*, its control drew blank, and no child said anything, so sixteen rows carried two
    formats and nothing named which was which.
    """
    jobs = _playlist_jobs(tmp_path, 3)
    queue.add(
        replace(
            jobs[0],
            status=JobStatus.COMPLETED,
            request=to_request(BEST_VIDEO, url=jobs[0].url, output_directory=str(tmp_path)),
        )
    )
    for job in jobs[1:]:
        queue.add(
            replace(job, request=to_request(AUDIO_MP3, url=job.url, output_directory=str(tmp_path)))
        )
    view = views(jobs=queue, manager=managers())
    view.model.toggle_group("pl-1")

    header = view.model.index(0, JOB_COLUMN)
    assert view.model.data(header, PRESET_ROLE) is None, (
        "the members disagree, so there is no one value"
    )
    assert view.model.data(header, PRESET_PLACEHOLDER_ROLE) == "Mixed — 2 formats", (
        f"the header's control says {view.model.data(header, PRESET_PLACEHOLDER_ROLE)!r}; a blank "
        "control reads as unset rather than as they differ"
    )

    entries = [
        view.model.data(view.model.index(row, JOB_COLUMN), SELECTOR_ROLE) for row in (1, 2, 3)
    ]
    assert entries[0] == f"Download as: {BEST_VIDEO.name}", (
        f"the completed entry says {entries[0]!r}; it kept the old format and must say so, or "
        "nothing in the window names which row got which"
    )
    assert entries[1] == entries[2] == f"Download as: {MP3_TEXT}"


def test_a_uniform_playlists_entries_stay_silent(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
) -> None:
    """The other half of the amendment, and the one that keeps row 9c's economy.

    Every playlist is uniform until somebody retargets a part-done one, so this is the common case:
    an entry that agrees with its group spends no line saying so, and the header carries the format
    exactly as row 9c intended.
    """
    for job in _playlist_jobs(tmp_path, 3):
        queue.add(
            replace(job, request=to_request(AUDIO_MP3, url=job.url, output_directory=str(tmp_path)))
        )
    view = views(jobs=queue, manager=managers())
    view.model.toggle_group("pl-1")

    header = view.model.index(0, JOB_COLUMN)
    assert view.model.data(header, PRESET_PLACEHOLDER_ROLE) is None, (
        "a playlist whose members agree offered a Mixed placeholder"
    )
    assert view.model.data(header, SELECTOR_ROLE) == f"Download as: {MP3_TEXT}"

    for row in (1, 2, 3):
        assert view.model.data(view.model.index(row, JOB_COLUMN), SELECTOR_ROLE) == "", (
            "an entry that agrees with its group spent a line saying so, which is the economy "
            "row 9c bought"
        )


# --- T-179: the cache is swept when membership changes, not on every reset ---------------------


def _thumbed(job_id: str, directory: Path, url: str, position: int) -> Job:
    return make_job(job_id, directory, thumbnail_url=url, queue_position=position)


def test_a_reorder_that_changes_no_membership_does_not_sweep_the_cache(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`T-179`. A reorder resets the model and cannot change which URLs are named.

    **The first reset still sweeps**, and that is asserted here rather than in its own test,
    because the two halves are the same rule: sweep when the set is not what was last swept, and
    `None` is not the empty set. A gate that skipped the first sweep would leave a queue restored
    from disk holding pictures no live job wants.

    **The real sweep is wrapped rather than replaced** (`T179-R1`). A stub that only records the
    call never lets the store finish, and the gate deliberately promotes its recorded state from
    `swept` — so a stub would leave every reorder looking like the first one and the test would
    assert nothing about the gate at all. It counts calls *and* lets the work happen.
    """
    first = "https://pics.invalid/a.jpg"
    second = "https://pics.invalid/b.jpg"
    root = tmp_path / "cache"
    thumbnail_cache_path(first, root).parent.mkdir(parents=True, exist_ok=True)
    queue.add(_thumbed("job-a", tmp_path, first, 0))
    queue.add(_thumbed("job-b", tmp_path, second, 1))
    manager = managers()
    view = views(jobs=queue, manager=manager, cache_root=root)

    swept: list[frozenset[str]] = []
    real = view._thumbnails.sweep

    def recording(live: Any) -> None:
        live = frozenset(live)
        swept.append(live)
        real(live)

    monkeypatch.setattr(view._thumbnails, "sweep", recording)

    manager.queue_reordered.emit(("job-b", "job-a"))
    assert swept == [frozenset({first, second})], (
        "the first reset after construction did not sweep; nothing has been swept yet, so a "
        "queue restored from disk would keep every picture it no longer names"
    )
    assert spin_until(qapp, lambda: not view._thumbnails.outstanding), "the first sweep never ran"

    manager.queue_reordered.emit(("job-a", "job-b"))
    manager.queue_reordered.emit(("job-b", "job-a"))

    assert swept == [frozenset({first, second})], (
        f"a reorder scheduled {len(swept)} cache scans; a reorder cannot change the live URL set, "
        "so every one after the first can only conclude that everything is still wanted"
    )


def test_removing_the_last_job_naming_a_picture_still_deletes_it(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`T-119`'s criterion through the view, which is the wiring `T-179` changed.

    The existing proof of this calls `ThumbnailStore.sweep` directly, so it would have passed
    unchanged had the gate skipped every sweep. Both halves are asserted in one arrangement, for
    the reason the original gives: a URL nothing names any more goes, and a URL a surviving job
    still names stays.
    """
    kept = "https://pics.invalid/kept.jpg"
    gone = "https://pics.invalid/gone.jpg"
    root = tmp_path / "cache"
    for url in (kept, gone):
        path = thumbnail_cache_path(url, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"a picture")

    queue.add(_thumbed("job-keeps", tmp_path, kept, 0))
    queue.add(_thumbed("job-shares", tmp_path, kept, 1))
    queue.add(_thumbed("job-goes", tmp_path, gone, 2))
    manager = managers()
    view = views(jobs=queue, manager=manager, cache_root=root)
    assert view.model.rowCount() == 3

    del queue.jobs["job-shares"]
    manager.job_removed.emit("job-shares")
    assert spin_until(qapp, lambda: not view._thumbnails.outstanding)
    assert thumbnail_cache_path(kept, root).exists(), (
        "the picture went when the first of two jobs naming it was removed; T-119 keeps a file "
        "while any remaining job names it"
    )

    del queue.jobs["job-goes"]
    manager.job_removed.emit("job-goes")
    assert spin_until(qapp, lambda: not thumbnail_cache_path(gone, root).exists()), (
        "the last job naming a picture was removed and the file survived"
    )
    assert thumbnail_cache_path(kept, root).exists(), "a picture a live job still names was deleted"


def test_a_first_queue_that_names_no_pictures_still_sweeps_once(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """Why `_swept_for` starts at `None` and not at the empty set (`T-179`).

    **This was a claim in a comment before it was a test.** The mutation that replaced `None` with
    `frozenset()` survived the other two gate tests, because in both of them the queue names at
    least one picture and so differs from empty either way. The case that separates them is the
    one below: a queue naming no pictures at all, over a cache directory that still holds files
    from a previous run. Starting at the empty set calls that "already swept" and the stale files
    stay for the life of the process.
    """
    root = tmp_path / "cache"
    stale = thumbnail_cache_path("https://pics.invalid/from-a-previous-run.jpg", root)
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_bytes(b"a picture no live job names")

    queue.add(make_job("job-a", tmp_path, queue_position=0))
    manager = managers()
    view = views(jobs=queue, manager=manager, cache_root=root)
    assert view.model.rowCount() == 1

    manager.queue_reordered.emit(("job-a",))

    assert spin_until(qapp, lambda: not stale.exists()), (
        "the first sweep was skipped because the queue named no pictures, so a cache left by a "
        "previous run is never collected"
    )


def test_a_picture_written_after_its_removal_sweep_is_still_collected(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """`T179-R1`. The reviewer's probe, as a regression.

    A decode already in flight publishes its file **after** the removal sweep has enumerated the
    directory. That sweep cannot see it. The first version of this gate remembered only the live
    set, so every later reset was suppressed and the file stayed for the life of the process —
    where the base implementation swept again on the next reorder and collected it.

    The write is made directly rather than through the store on purpose: this must hold for a file
    the view has no signal for, which is not hypothetical — the add dialog runs a second store over
    the same cache root (`T118-R16`), and nothing this view is connected to fires for it.

    So the gate also remembers what the cache directory looked like when the sweep **finished**,
    and a pure reorder over a changed directory sweeps rather than skipping.
    """
    kept = "https://pics.invalid/kept.jpg"
    gone = "https://pics.invalid/gone.jpg"
    root = tmp_path / "cache"
    kept_path = thumbnail_cache_path(kept, root)
    kept_path.parent.mkdir(parents=True, exist_ok=True)
    kept_path.write_bytes(b"a picture")

    queue.add(_thumbed("job-keeps", tmp_path, kept, 0))
    queue.add(_thumbed("job-goes", tmp_path, gone, 1))
    manager = managers()
    view = views(jobs=queue, manager=manager, cache_root=root)

    del queue.jobs["job-goes"]
    manager.job_removed.emit("job-goes")
    assert spin_until(qapp, lambda: not view._thumbnails.outstanding), (
        "the removal sweep never finished, so the race this is about was never set up"
    )

    # The late decode lands: its job is already gone, and the sweep that would have caught it has
    # been and finished.
    late = thumbnail_cache_path(gone, root)
    late.write_bytes(b"decoded after the sweep")

    manager.queue_reordered.emit(("job-keeps",))

    assert spin_until(qapp, lambda: not late.exists()), (
        "a picture written after its job's removal sweep survived a later reorder; unchanged "
        "membership suppressed every subsequent scan, which is T179-R1"
    )
    assert kept_path.exists(), "a picture a live job still names was deleted"


def test_clearing_the_queue_sweeps_every_picture_it_held(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """The sibling path `T179-R1` asked to be audited explicitly.

    `queue_cleared` resets the model like the other two, and it is the case where the live set goes
    to empty. A gate keyed on membership handles it by construction — which is exactly why it is
    worth a test rather than an argument.
    """
    root = tmp_path / "cache"
    urls = ["https://pics.invalid/one.jpg", "https://pics.invalid/two.jpg"]
    for index, url in enumerate(urls):
        path = thumbnail_cache_path(url, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"a picture")
        queue.add(_thumbed(f"job-{index}", tmp_path, url, index))

    manager = managers()
    view = views(jobs=queue, manager=manager, cache_root=root)
    assert view.model.rowCount() == 2

    queue.jobs.clear()
    manager.queue_cleared.emit()

    assert spin_until(
        qapp, lambda: not any(thumbnail_cache_path(url, root).exists() for url in urls)
    ), "clearing the queue left its pictures on disk"


def test_a_sweep_that_deleted_something_does_not_make_the_next_reorder_sweep(
    queue: FakeQueue,
    managers: Callable[..., DownloadManager],
    views: Callable[..., QueueView],
    tmp_path: Path,
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Why the gate records what a sweep **finished** with, not what it was asked for (`T179-R1`).

    A sweep changes the very directory the gate fingerprints — deleting a file is a change. Record
    the fingerprint when the sweep is *requested* and it is already stale by the time the sweep
    ends, so the next reorder sees a changed directory and scans again for nothing. That is the
    redundant scan this task exists to remove, reintroduced one step later.

    It is a performance property rather than a correctness one, which is exactly why it needed its
    own test: the mutation that records on request survived every other test here, because none of
    them had a sweep that actually deleted anything.
    """
    kept = "https://pics.invalid/kept.jpg"
    gone = "https://pics.invalid/gone.jpg"
    root = tmp_path / "cache"
    for url in (kept, gone):
        path = thumbnail_cache_path(url, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"a picture")

    queue.add(_thumbed("job-keeps", tmp_path, kept, 0))
    queue.add(_thumbed("job-goes", tmp_path, gone, 1))
    manager = managers()
    view = views(jobs=queue, manager=manager, cache_root=root)

    del queue.jobs["job-goes"]
    manager.job_removed.emit("job-goes")
    assert spin_until(qapp, lambda: not thumbnail_cache_path(gone, root).exists()), (
        "the removal sweep did not delete the orphan, so it changed nothing and this test would "
        "prove nothing"
    )
    assert spin_until(qapp, lambda: not view._thumbnails.outstanding)

    swept: list[frozenset[str]] = []
    real = view._thumbnails.sweep

    def recording(live: Any) -> None:
        live = frozenset(live)
        swept.append(live)
        real(live)

    monkeypatch.setattr(view._thumbnails, "sweep", recording)
    manager.queue_reordered.emit(("job-keeps",))

    assert swept == [], (
        f"a reorder after a sweep that deleted a file scheduled {len(swept)} more scans; the "
        "recorded fingerprint was taken before the sweep changed the directory it fingerprints"
    )
