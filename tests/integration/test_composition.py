"""The assembled application (`T-036`).

**Nothing here builds a component.** Every test calls `app.compose()` and then drives what it
returns, because this task exists for the failure that no component test can see: every Phase 1
piece passing while the application still opens an empty window. A test that constructed a
manager and a store and wired them itself would be asserting on its own wiring.

The database is real, the writer thread is real, the worker is a real spawned process
(`ai/TESTING.md` §6). What varies is only which program the child runs.

## Wait on the UI, never on the store

`T-013`'s ordering is *persist, then signal*, and `ARC-005` made the persisting happen on another
thread. So the writer commits a row and **then** posts a signal to the GUI thread, and in between
`store.get()` answers the new state while every widget still shows the old one. That gap is the
guarantee working, not a race.

Three tests in this file were written against the store first and each of them observed the gap:
one read `COMPLETED` from disk and asserted on a view that had not been told, another decided a
probe had failed before the manager announced it. A test about the assembled *application* waits
on what the application shows. `store.get()` is for asserting agreement afterwards.

`is_idle` has the mirror-image trap: it is true before a session starts as well as after one ends,
so spinning on it returns instantly and proves nothing.
"""

import sqlite3
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QMetaMethod, QObject
from PySide6.QtWidgets import QApplication

from tracks_and_trails import app as application
from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.downloader.protocol import (
    Failed,
    Probed,
    Progress,
    SessionKind,
    Stage,
    Succeeded,
    WorkerFinished,
)
from tracks_and_trails.persistence import db
from tracks_and_trails.persistence.repositories import JobRepository
from tracks_and_trails.ui.queue_view import PROGRESS_COLUMN, SIZE_COLUMN

# --- children the composed application spawns -------------------------------------------------


def child_probing_then_waiting(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **kwargs: Any
) -> None:
    """A probe that answers, then a download that runs until it is cancelled.

    One function for both session kinds because the composed application chooses the kind, not
    the test — which is the point of driving the assembled thing.
    """
    from tracks_and_trails.core.models import MediaInfo

    if kind is SessionKind.PROBE:
        queue.put(
            Probed(
                job_id=job_id,
                media=MediaInfo(
                    url=request.url,
                    title="A video that exists",
                    uploader="Somebody",
                    duration_seconds=12,
                ),
            )
        )
        queue.put(WorkerFinished(job_id=job_id, exit_code=0))
        return

    cancel = kwargs.get("cancel")
    sent = 0
    while cancel is None or not cancel.is_set():
        sent += 1024
        queue.put(
            Progress(
                job_id=job_id,
                stage=Stage.DOWNLOADING_VIDEO,
                downloaded_bytes=sent,
                total_bytes=1024 * 100,
            )
        )
        time.sleep(0.02)
    queue.put(Failed(job_id=job_id, kind=ErrorKind.CANCELLED, message="Stopped on request."))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))


def child_probing_then_succeeding(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    from tracks_and_trails.core.models import MediaInfo

    if kind is SessionKind.PROBE:
        queue.put(
            Probed(
                job_id=job_id,
                media=MediaInfo(
                    url=request.url,
                    title="A video that exists",
                ),
            )
        )
        queue.put(WorkerFinished(job_id=job_id, exit_code=0))
        return

    output = Path(request.output_directory) / "A video that exists.mp4"
    output.write_bytes(b"x" * 2048)
    queue.put(
        Progress(
            job_id=job_id, stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=1024, total_bytes=2048
        )
    )
    queue.put(Succeeded(job_id=job_id, output_path=str(output), total_bytes=2048))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))


def child_failing_to_extract(
    kind: SessionKind, job_id: str, _request: DownloadRequest, queue: Any, **_: Any
) -> None:
    queue.put(
        Failed(
            job_id=job_id,
            kind=ErrorKind.NETWORK,
            message="ERROR: Unable to download webpage: <urlopen error timed out>",
        )
    )
    queue.put(WorkerFinished(job_id=job_id, exit_code=1))


# --- fixtures ---------------------------------------------------------------------------------


@pytest.fixture
def composed(
    qapp: QApplication, tmp_path: Path, spin: Callable[..., bool]
) -> Iterator[Callable[..., application.Composition]]:
    """Build composed applications and take each one down through its own shutdown lifecycle.

    Teardown drives the real thing rather than closing handles behind its back: a test that left
    a worker running would have it attributed to whichever test ran next, and one that closed the
    connection itself would prove nothing about the order `T-036` exists to establish.
    """
    built: list[application.Composition] = []

    def build(**overrides: Any) -> application.Composition:
        overrides.setdefault("database", tmp_path / "queue.db")
        overrides.setdefault("output_directory", tmp_path / "downloads")
        overrides.setdefault("geometry_file", tmp_path / "window.toml")
        # Same reason as `geometry_file`: without it these tests read and write the real
        # `user_config_dir`, which `ai/TESTING.md` §5 forbids (`T-078`).
        overrides.setdefault("settings_file", tmp_path / "settings.toml")
        composition = application.compose(qapp, **overrides)
        built.append(composition)
        return composition

    yield build

    for composition in built:
        composition.shutdown.begin()
    for composition in built:
        assert spin(lambda c=composition: c.shutdown.finished, timeout=60), (
            "a composed application never finished shutting down"
        )


def connection_count(sender: QObject, signal_name: str) -> int:
    """How many slots are connected to `signal_name` on `sender`.

    Asked of Qt rather than of our own bookkeeping (`ai/TESTING.md` §13): a count this code kept
    would agree with this code. `receivers()` wants the `SIGNAL()`-encoded signature, which the
    meta-object supplies.
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
    raise LookupError(f"{sender} has no signal named {signal_name!r}")


def type_urls(dialog: Any, text: str) -> None:
    dialog._urls.setPlainText(text)


# --- 1. the assembled path (`REQ-001`, `REQ-012`) ---------------------------------------------


def test_pasting_a_url_into_the_assembled_application_reaches_the_database(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """`T-036`'s first acceptance criterion, and the failure the task was filed for.

    Every component of this path had passing tests while `app.py` built a window with no manager,
    no job store and no output directory — so File → Add URLs… was disabled and none of it was
    reachable. This drives the *composed* application: open the real dialog from the real window,
    type, add, and read the row back out of SQLite through a connection the application does not
    own.
    """
    composition = composed(entry_point=child_probing_then_waiting)
    assert composition.window.can_add_urls, (
        "the window was built without everything the dialog needs; that is the defect T-036 "
        "exists to prevent"
    )

    dialog = composition.window.open_add_dialog()
    type_urls(dialog, "https://composed.invalid/one\nhttps://composed.invalid/two")
    dialog.add_to_queue()
    assert spin(lambda: len(dialog.queued_job_ids) == 2, timeout=30), "the paste never persisted"

    # Read through a *different* connection: the point is that the rows are on disk, not that the
    # application remembers writing them.
    reader = sqlite3.connect(tmp_path / "queue.db")
    try:
        urls = [row[0] for row in reader.execute("SELECT url FROM jobs ORDER BY queue_position")]
    finally:
        reader.close()
    assert urls == ["https://composed.invalid/one", "https://composed.invalid/two"]


def test_the_composed_application_downloads_a_file_and_shows_it_finished(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """Probe, queue, download, complete — through the assembled graph and nothing else.

    The progress view appears because the manager moved the job, not because a test built one:
    `T-036` connects `job_changed` to the window, and that connection is what makes the engine
    visible to a person at all.
    """
    composition = composed(entry_point=child_probing_then_succeeding)
    dialog = composition.window.open_add_dialog()
    type_urls(dialog, "https://composed.invalid/movie")
    dialog.probe()

    assert spin(lambda: dialog.media is not None, timeout=60), "the probe never reported"
    assert dialog.media is not None and dialog.media.title == "A video that exists"
    assert composition.window.watched_job_id is not None, (
        "the window never showed the job the manager was working on"
    )

    # The probe's *session* outlives its result: the manager releases it on a later tick. Adding
    # before then is refused by the pool of one, which the dialog reports rather than raises.
    assert spin(lambda: composition.manager.is_idle, timeout=60), "the probe session never ended"
    dialog.add_to_queue()
    assert "did not start" not in dialog.status_text(), dialog.status_text()
    # **Waited on the view, not on the store**, and the difference is `T-013`'s ordering rather
    # than a detail. The writer thread commits the row and *then* signals the GUI thread, so
    # `store.get()` answers `COMPLETED` from disk while `job_changed` is still queued. The
    # database leading the UI is exactly the guarantee; a test that polled the store would be
    # asserting on the window in the gap between the two, and this one did.
    view = composition.window.progress_view
    assert view is not None
    assert spin(lambda: view.status is JobStatus.COMPLETED, timeout=60), (
        f"the download never completed; the view says {view.status.value}"
    )

    job_id = dialog.queued_job_ids[0]
    job = composition.store.get(job_id)
    assert job is not None and job.output_path is not None
    assert Path(job.output_path).exists(), "the file the queue claims to have downloaded is absent"

    assert view.job_id == job_id
    assert not view.can_cancel, "a finished job still offers to be cancelled"


# --- 2. the wiring itself ---------------------------------------------------------------------


def test_the_manager_holds_the_store_composition_built(
    composed: Callable[..., application.Composition],
) -> None:
    """Asserted by identity, so a second store cannot quietly service a second queue.

    `T-036`'s criterion is that *no component is constructed twice*. Two stores over one database
    would each hold their own in-flight revisions, and `ARC-005`'s ordering guarantee is a
    property of there being one writer — not of there being one writer per object.
    """
    composition = composed()

    assert composition.manager._repository is composition.store
    assert composition.window._manager is composition.manager
    assert composition.window._jobs is composition.store
    assert composition.window._job_reader is composition.store


def test_every_manager_signal_the_ui_needs_has_exactly_one_connection(
    composed: Callable[..., application.Composition],
) -> None:
    """A signal connected twice is how one queued job becomes two of everything downstream.

    Counted through Qt's own `receivers()`, not through bookkeeping this code keeps, because
    bookkeeping this code keeps would agree with this code (`ai/TESTING.md` §13).
    """
    composition = composed()
    manager = composition.manager

    # **Two, and each is named.** Composition connects `on_job_changed` to claim the detail pane;
    # the queue table's model connects its own to keep rows current (`T-079`). The number went
    # from one to two when the table arrived, and it is written here rather than counted so that
    # a *third* — the shape this test exists for — is still a failure.
    assert connection_count(manager, "job_changed") == 2, (
        "job_changed should have exactly composition's listener and the queue model's; a third "
        "is how one queued job becomes two of everything downstream"
    )
    # The queue model is the only thing listening to progress until a detail view is built. It
    # was zero before `T-079`, which is why this line is new: a table that draws progress is a
    # second consumer of the stream that `T-017`'s repaint budget is about.
    assert connection_count(manager, "progress") == 1, (
        "the queue model should be the only progress listener before any detail view exists"
    )
    for name in ("queue_paused", "job_removed", "queue_reordered", "queue_cleared"):
        assert connection_count(manager, name) == 1, (
            f"{name} should have exactly the queue UI listener that reflects the durable change"
        )

    dialog = composition.window.open_add_dialog()
    # The dialog adds its own four. Named individually rather than counted in bulk, so a signal
    # gaining a second listener is reported as itself.
    for name, expected in (
        ("media_probed", 1),
        ("job_failed", 1),
        ("persistence_failed", 1),
        ("start_rejected", 1),
        ("job_changed", 3),
    ):
        assert connection_count(manager, name) == expected, (
            f"{name} has {connection_count(manager, name)} connections, expected {expected}"
        )
    dialog.close()


def test_replacing_the_watched_job_leaves_no_second_listener(
    composed: Callable[..., application.Composition],
) -> None:
    """`deleteLater` is asynchronous, so a replaced view answers signals until it dies.

    With a pool of one that is not a leak; it is a second listener, and a second listener is
    exactly what the criterion above forbids. `JobProgressView.detach` is what makes replacement
    deterministic rather than dependent on how many event-loop turns happen to pass.
    """
    composition = composed()
    manager = composition.manager
    before = connection_count(manager, "progress")

    composition.window.watch("job-a")
    with_one = connection_count(manager, "progress")
    assert with_one == before + 1

    composition.window.watch("job-b")
    assert connection_count(manager, "progress") == with_one, (
        "the replaced view is still listening; two views would render one job twice"
    )
    assert composition.window.watched_job_id == "job-b"


def test_watching_the_same_job_twice_does_not_rebuild_the_view(
    composed: Callable[..., application.Composition],
) -> None:
    """`job_changed` fires per transition, and a job passes through several."""
    composition = composed()

    first = composition.window.watch("job-a")
    assert composition.window.watch("job-a") is first, (
        "each transition of one job rebuilt its view, discarding what it was showing"
    )


# --- 3. the environment (`REQ-024`) -----------------------------------------------------------


def test_startup_states_what_this_installation_cannot_do(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """`REQ-024`: report the ffmpeg state and name what will not work without it.

    Driven with an override that does not exist, because that is the case with something to say.
    A missing ffmpeg disables features; it does not stop the application, and the window has to
    say so where a user will see it rather than in a log they will not read.
    """
    composition = composed(ffmpeg_override=tmp_path / "no-such-ffmpeg")

    assert not composition.ffmpeg.available
    summary = composition.window.environment_text()
    assert "ffmpeg was not found" in summary, f"the window says {summary!r}"
    assert "Unavailable:" in summary, (
        "the report named no features, so a user learns that something is wrong and not what"
    )


def test_a_usable_ffmpeg_is_reported_as_usable_and_reaches_the_manager(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """The path is *passed on*, not merely found — the defect class this project met five times.

    `ai/STATUS.md` records it: the resolved yt-dlp version never left the worker, ffmpeg was
    located and never passed to the library. Locating it here and dropping it would look correct
    and produce no error.
    """
    # **What "executable" means is the platform's answer, not a mode bit** (`T-062`). This wrote
    # a `#!/bin/sh` script and `chmod 0755`; Windows decides by `PATHEXT`, so `shutil.which`
    # correctly returned `None` and this test failed there and only there. `find_ffmpeg` uses
    # `shutil.which` precisely so the platform's own rule applies (`T035-R2`) — the test has to
    # honour the same rule it is exercising.
    if sys.platform == "win32":
        fake = tmp_path / "ffmpeg.bat"
        fake.write_text("@echo off\r\nexit /b 0\r\n")
    else:
        fake = tmp_path / "ffmpeg"
        fake.write_text("#!/bin/sh\nexit 0\n")
        fake.chmod(0o755)
    composition = composed(ffmpeg_override=fake)

    assert composition.ffmpeg.available
    assert "all post-processing features are available" in composition.window.environment_text()
    assert composition.manager._ffmpeg_override == composition.ffmpeg.path, (
        "ffmpeg was located and then not handed to the manager, so no worker would ever see it"
    )


# --- 4. shutdown (`T013-R2`, `T038-R2`, `ARC-005`) --------------------------------------------


def test_closing_the_window_with_a_download_running_stops_everything_in_order(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """The whole of `T-036`'s shutdown criterion, driven from the window's own close.

    Order matters and each step is asynchronous: the manager stops the worker and reaps its tree,
    the writer then finishes the transitions the manager queued on its way down, and only then is
    the database closed. Quitting earlier leaves an orphaned process or loses a row.
    """
    composition = composed(entry_point=child_probing_then_waiting)
    dialog = composition.window.open_add_dialog()
    type_urls(dialog, "https://composed.invalid/long")
    dialog.probe()
    assert spin(lambda: dialog.media is not None, timeout=60)
    assert spin(lambda: composition.manager.is_idle, timeout=60), "the probe session never ended"
    dialog.add_to_queue()
    assert spin(lambda: composition.manager.active_job_ids() != (), timeout=60), (
        "no download was running, so this proves nothing about closing with one"
    )
    job_id = composition.manager.active_job_ids()[0]

    # Qt's default is to quit the instant the last window closes, which is step zero of the wrong
    # order: the worker is still alive and the database still open. Asserted structurally because
    # its absence has no in-process consequence — the process would simply be gone, and a test
    # cannot observe its own exit.
    assert composition.app.quitOnLastWindowClosed() is False, (
        "Qt will quit when the window closes, before the worker is stopped or the database "
        "is closed"
    )

    composition.window.close()

    assert composition.shutdown.begun, "closing the window did not begin the shutdown lifecycle"
    assert spin(lambda: composition.shutdown.finished, timeout=60), "shutdown never finished"
    assert composition.manager.is_idle
    assert not composition.writer.is_running, "the writer thread outlived the shutdown"

    # The database is closed, and closed *after* the writes: a fresh reader sees the cancellation.
    with pytest.raises(sqlite3.ProgrammingError):
        composition.connection.execute("SELECT 1")
    reader = db.connect(tmp_path / "queue.db")
    try:
        stored = JobRepository(reader).get(job_id)
    finally:
        reader.close()
    assert stored is not None
    assert stored.status is JobStatus.CANCELLED, (
        f"the job was left {stored.status.value} on disk; closing the window cancels what is "
        "running, and the writer finishes before the connection closes"
    )


def test_shutdown_is_idempotent_and_does_not_quit_on_an_ordinary_idle(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
) -> None:
    """`idle` is emitted whenever the last session is released, not only while shutting down.

    Closing the writer on an ordinary idle would end persistence while the application was still
    running — the queue would keep working and nothing would ever reach disk again.
    """
    composition = composed(entry_point=child_probing_then_succeeding)
    dialog = composition.window.open_add_dialog()
    type_urls(dialog, "https://composed.invalid/short")
    dialog.probe()
    assert spin(lambda: dialog.media is not None, timeout=60)
    assert spin(lambda: composition.manager.is_idle, timeout=60), "the probe never finished"

    assert not composition.shutdown.finished, "an ordinary idle closed the writer"

    # **Asserted by writing, not by asking whether the thread is alive.** `close()` is
    # asynchronous, so `is_running` can still be true for a moment after an early close — a check
    # that samples it proves nothing, and a mutation closing the writer on every idle survived
    # exactly that check. What must still be true is that persistence *works*.
    second = composition.window.open_add_dialog()
    type_urls(second, "https://composed.invalid/after-idle")
    second.add_to_queue()
    assert spin(lambda: len(second.queued_job_ids) == 1, timeout=60), (
        "nothing could be queued after an ordinary idle; the writer was closed while the "
        "application was still running"
    )
    second.close()

    composition.shutdown.begin()
    composition.shutdown.begin()
    assert spin(lambda: composition.shutdown.finished, timeout=60)


# --- 5. cold start (`NFR-002`) ----------------------------------------------------------------


def test_cold_start_with_the_whole_graph_fits_the_budget(
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
    record_property: Callable[[str, object], None],
) -> None:
    """`NFR-002`: three seconds, measured with everything constructed.

    `T-007` measured an empty window at 0.178 s and said so; this measures the graph that window
    now hangs off — a migrated database, a writer thread, a manager, and the window itself.
    Recorded as a property rather than asserted alone, so the number is in the run's output when
    it starts drifting toward the budget rather than only when it crosses it.
    """
    started = time.perf_counter()
    composition = application.compose(
        qapp,
        database=tmp_path / "cold.db",
        output_directory=tmp_path / "downloads",
        geometry_file=tmp_path / "window.toml",
    )
    composition.window.show()
    qapp.processEvents()
    elapsed = time.perf_counter() - started

    record_property("cold_start_seconds", round(elapsed, 3))
    try:
        assert elapsed < 3.0, (
            f"cold start took {elapsed:.3f}s against NFR-002's 3s budget, with the full graph "
            "constructed"
        )
    finally:
        composition.window.close()
        assert spin(lambda: composition.shutdown.finished, timeout=60)


# --- 6. retry is composition's, and it is a write ---------------------------------------------


def test_retrying_a_failed_job_re_queues_it_and_starts_it_again(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
) -> None:
    """The seam `T-017` left open: the widget reports `retry_requested`, this performs it.

    `ui/` holds no writer (`ARCHITECTURE.md` §3), so a retry that the view performed itself would
    be the layering violation `T-005` fails the suite for. What it costs is that nothing retried
    anything until composition existed — which is exactly the shape of gap `T-036` was filed for.
    """
    composition = composed(entry_point=child_failing_to_extract)
    dialog = composition.window.open_add_dialog()
    type_urls(dialog, "https://composed.invalid/gone")
    dialog.probe()

    # Waited on the view, per the module docstring: the row is `FAILED` on disk before the
    # manager announces it, and a retry control that exists only after the announcement cannot
    # be asserted on before it. Waiting on `is_idle` here would be worse still — it is true
    # before the probe starts.
    assert spin(
        lambda: (
            composition.window.progress_view is not None
            and composition.window.progress_view.status is JobStatus.FAILED
        ),
        timeout=60,
    ), "the probe never failed, so there is nothing to retry"

    view = composition.window.progress_view
    assert view is not None
    failed_id = view.job_id
    assert view.can_retry, (
        f"a network failure is retryable and the control is absent: failure={view.failure}"
    )
    failed = composition.store.get(failed_id)
    assert failed is not None and failed.status is JobStatus.FAILED
    transitions: list[str] = []
    composition.manager.job_changed.connect(lambda job_id, status: transitions.append(status))

    view.retry_requested.emit(failed_id)

    # **A retry that leaves an inert queued row is not a retry** (`T036-R1`). The previous version
    # of this test asserted only that the job left `FAILED`, and a comment here argued that
    # starting was not part of the promise. The reviewer measured what that argument costs: the
    # failed session had not been released yet, the pool of one refused the start, the refusal was
    # swallowed, and five seconds later nothing had happened — a queued row nobody was running, a
    # view still showing the old failure, and a Retry button that did nothing the second time.
    assert spin(lambda: "queued" in transitions, timeout=60), (
        f"the re-queue was never announced, so no widget could learn about it: {transitions}"
    )
    assert spin(lambda: any(s in transitions for s in ("probing", "running")), timeout=60), (
        f"the retry re-queued the job and never started it: {transitions}"
    )

    # The view stops showing the old failure, because the manager announced the transition. When
    # composition wrote it through the store instead, nothing did.
    assert spin(lambda: view.status is not JobStatus.FAILED, timeout=60), (
        "the progress view still shows the failure this retry replaced"
    )


# --- T-078: the limit changes through the control a person can reach ------------------------


def test_the_limit_changes_through_the_control_and_survives_a_restart(
    composed: Callable[..., application.Composition], tmp_path: Path
) -> None:
    """`T-078`, `ARC-007`: **driven through the widget, never the constructor.**

    The criterion exists because a pool whose limit is only a constructor argument satisfies every
    behavioural test and misses `REQ-013` entirely — that is what `P2PLAN-R3` reported. So this
    reaches the real `QSpinBox` by object name and sets a value, exactly as a person would, and
    asserts two separate things: the **running pool** changed, and the change is on **disk**.

    "Survives a restart" is asserted by composing a second application against the same settings
    file rather than by trusting `save()`. A second graph reading the value back is the only form
    of that claim which cannot pass against a write that never happened.
    """
    from tracks_and_trails.core import settings as app_settings

    settings_file = tmp_path / "settings.toml"
    first = composed(settings_file=settings_file)

    box = first.window.concurrency_control
    assert box is not None, "composition did not give the window a concurrency control"
    assert box.value() == app_settings.CONCURRENCY_DEFAULT
    assert first.manager.concurrency == app_settings.CONCURRENCY_DEFAULT

    box.setValue(5)

    assert first.manager.concurrency == 5, (
        "the running pool did not change. A control that edits a file and not the pool is T-075's "
        "shape one setting over: the stored value and the running behaviour disagree"
    )
    assert app_settings.load(settings_file).concurrency == 5, "the choice never reached disk"

    second = composed(
        database=tmp_path / "second.db",
        geometry_file=tmp_path / "second-window.toml",
        settings_file=settings_file,
    )
    assert second.manager.concurrency == 5, "a restart did not pick the chosen limit back up"
    assert second.window.concurrency_control is not None
    assert second.window.concurrency_control.value() == 5, (
        "the control came back showing a different number from the pool it governs"
    )


def test_the_control_offers_exactly_the_range_the_settings_layer_allows(
    composed: Callable[..., application.Composition], tmp_path: Path
) -> None:
    """The widget's range is read from `core/settings.py`, not restated beside it.

    A spinbox with its own numbers would be a second opinion about `REQ-013`'s minimum and
    `ARC-007`'s ceiling. It bounds the *widget*; the bound that matters is on the value, which is
    why `settings.toml` is clamped independently and a hand-edited `0` still becomes 1.
    """
    from tracks_and_trails.core import settings as app_settings

    composition = composed(settings_file=tmp_path / "settings.toml")
    box = composition.window.concurrency_control
    assert box is not None
    assert box.minimum() == app_settings.CONCURRENCY_MINIMUM
    assert box.maximum() == app_settings.CONCURRENCY_MAXIMUM


def test_lowering_the_limit_through_the_control_holds_new_work_without_stopping_old(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """`T078-R2`: lowering was **written down and not enforced**, and nothing could see it.

    Two mutations survived the committed suite, and they are the same gap from either end:

    - Composition applying increases but only *saving* decreases passed the entire 14-test file,
      because the one real-control test moves 3 → 5 and never down.
    - The scheduler starting waiting work while the live count was above the lowered limit passed
      every pool test, because the drain test has nothing waiting for it to wrongly start.

    So this lowers a **saturated** pool through the real `QSpinBox` with a fourth job accepted
    behind it, and asserts the three things that distinguish an enforced limit from a recorded
    one: the running work survives, the waiting work stays waiting while the pool is over the new
    limit, and it starts once the pool is under it.

    Jobs are submitted to the real store and started through the real manager rather than typed
    into the add dialog four times — the path under test is control → pool, and
    `test_the_limit_changes_through_the_control_and_survives_a_restart` already drives the
    control end-to-end. `_start_when_free` is reached directly because it is the only admission
    path into the waiting list: `start()` at saturation raises instead of queueing.
    """
    from datetime import UTC, datetime

    from tracks_and_trails.core import settings as app_settings
    from tracks_and_trails.core.models import Job

    settings_file = tmp_path / "settings.toml"
    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)
    manager = composition.manager
    assert manager.concurrency == 3, "this test needs the default limit to be the saturated one"

    saved: list[str | None] = []
    composition.store.submit(
        [
            Job(
                id=job_id,
                url=f"https://composed.invalid/{job_id}",
                request=DownloadRequest(
                    url=f"https://composed.invalid/{job_id}",
                    output_directory=str(tmp_path / "downloads"),
                    format_selector="best",
                    output_template="%(title)s.%(ext)s",
                ),
                created_at=datetime.now(UTC),
            )
            for job_id in ("job-1", "job-2", "job-3", "job-4")
        ],
        saved.append,
    )
    assert spin(lambda: bool(saved), timeout=60), "the queue rows were never written"
    assert saved == [None], f"submitting the queue failed: {saved}"

    for job_id in ("job-1", "job-2", "job-3"):
        manager.start(job_id)
    manager._start_when_free("job-4")
    assert spin(lambda: len(manager._occupant_ids()) == 3, timeout=60), (
        f"the pool never saturated: occupants {manager._occupant_ids()}"
    )
    assert manager._waiting == ["job-4"]

    box = composition.window.concurrency_control
    assert box is not None
    box.setValue(1)

    assert manager.concurrency == 1, (
        "the running pool kept the old limit. A handler that applies increases and merely stores "
        "decreases leaves the file saying 1 and the pool running 3 — T-075's shape, one setting "
        "over, and invisible to any test that only ever raises the limit"
    )
    assert app_settings.load(settings_file).concurrency == 1, "the decrease never reached disk"

    # The tick fills free slots too, so give it several before deciding nothing started.
    spin(lambda: False, timeout=0.5)
    assert manager._occupant_ids() == ("job-1", "job-2", "job-3"), (
        "lowering the limit through the control stopped work already in flight; UX-001 chose "
        "draining, and REQ-017's resume does not exist to make a partial file recoverable"
    )
    assert manager._waiting == ["job-4"], (
        "the waiting job started while three were live and the limit was 1. Lowering governs "
        "what starts next; a pool that fills slots it does not have has no limit at all"
    )

    for job_id in ("job-1", "job-2", "job-3"):
        manager.cancel(job_id)

    assert spin(lambda: manager._occupant_ids() == ("job-4",), timeout=60), (
        "the waiting job never became eligible once the pool drained below the new limit: "
        f"occupants {manager._occupant_ids()}, waiting {manager._waiting}"
    )


# --- T-079: the queue table in the assembled application --------------------------------------


def child_streaming_its_own_size(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """A download that reports a size derived from its job id, then finishes.

    Per-job sizes because three identical rows are what the defect looks like: a table routing
    every message into one row passes any check that merely counts rows or waits for progress.
    The manager writes the worker's total at the terminal transition, so the *worker* has to be
    the thing that differs — seeding the rows would be overwritten.
    """
    if kind is SessionKind.PROBE:
        from tracks_and_trails.core.models import MediaInfo

        queue.put(Probed(job_id=job_id, media=MediaInfo(url=request.url, title=f"Video {job_id}")))
        queue.put(WorkerFinished(job_id=job_id, exit_code=0))
        return

    total = 1024 * int(job_id.rsplit("-", 1)[1])
    output = Path(request.output_directory) / f"{job_id}.mp4"
    output.write_bytes(b"x" * total)
    for fraction in (0.5, 1.0):
        queue.put(
            Progress(
                job_id=job_id,
                stage=Stage.DOWNLOADING_VIDEO,
                downloaded_bytes=int(total * fraction),
                total_bytes=total,
            )
        )
        # Longer than one `REPAINT_INTERVAL_MS`, so each job is drawn at least once before it
        # ends. Faster than that and the terminal state drops the pending message undrawn, which
        # would make the live assertion below a measurement of the timer rather than the routing.
        time.sleep(0.15)
    queue.put(Succeeded(job_id=job_id, output_path=str(output), total_bytes=total))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))


def queue_three(
    composition: application.Composition, spin: Callable[..., bool], where: Path
) -> None:
    """Put three real rows in the composed application's own database."""
    from datetime import UTC, datetime

    from tracks_and_trails.core.models import Job

    saved: list[str | None] = []
    composition.store.submit(
        [
            Job(
                id=job_id,
                url=f"https://composed.invalid/{job_id}",
                request=DownloadRequest(
                    url=f"https://composed.invalid/{job_id}",
                    output_directory=str(where),
                    format_selector="best",
                    output_template="%(title)s.%(ext)s",
                ),
                created_at=datetime.now(UTC),
            )
            for job_id in ("job-1", "job-2", "job-3")
        ],
        saved.append,
    )
    assert spin(lambda: bool(saved), timeout=60), "the queue rows were never written"
    assert saved == [None], f"submitting the queue failed: {saved}"


def test_the_composed_pause_control_changes_the_real_manager(
    composed: Callable[..., application.Composition],
) -> None:
    """`T-080`: prove the toolbar-to-manager seam instead of either component in isolation."""
    composition = composed()
    action = composition.window.pause_action
    assert action is not None

    action.trigger()
    assert composition.manager.is_paused
    assert action.isChecked()

    action.trigger()
    assert not composition.manager.is_paused
    assert not action.isChecked()


def test_the_composed_move_control_updates_the_store_and_the_table(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """`T-081`: action, composition, manager, writer, and queue view form one reorder path."""
    composition = composed()
    queue_three(composition, spin, tmp_path / "downloads")
    table = composition.window.queue_view
    action = composition.window.move_up_action
    assert table is not None and action is not None
    table.refresh()
    assert table.select("job-2") and action.isEnabled()

    action.trigger()

    assert spin(
        lambda: (
            tuple(job.id for job in composition.store.all_jobs()) == ("job-2", "job-1", "job-3")
        ),
        timeout=60,
    ), "the composed move action never reached the durable queue"
    assert table.model.job_ids() == ("job-2", "job-1", "job-3"), (
        "the database was reordered but the composed queue table still shows the old order"
    )


def test_the_composed_remove_control_updates_the_store_and_the_table(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """`T-080`: a durable removal must disappear from the assembled queue view."""
    composition = composed()
    queue_three(composition, spin, tmp_path / "downloads")
    table = composition.window.queue_view
    action = composition.window.remove_action
    assert table is not None and action is not None
    table.refresh()
    assert table.select("job-2") and action.isEnabled()

    action.trigger()

    assert spin(lambda: composition.store.get("job-2") is None, timeout=60), (
        "the composed Remove action never reached the durable queue"
    )
    assert "job-2" not in table.model.job_ids(), (
        "the row was deleted but the composed queue table still shows it"
    )


def test_the_composed_clear_control_updates_the_store_and_the_table(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """`T-081`: Clear finished reaches the manager and refreshes the assembled queue view."""
    composition = composed()
    queue_three(composition, spin, tmp_path / "downloads")
    job = composition.store.get("job-2")
    assert job is not None
    settled: list[str | None] = []
    composition.store.update(job.with_status(JobStatus.CANCELLED), settled.append)
    assert spin(lambda: bool(settled), timeout=60)
    assert settled == [None]

    table = composition.window.queue_view
    action = composition.window.clear_completed_action
    assert table is not None and action is not None
    table.refresh()
    assert "job-2" in table.model.job_ids()

    action.trigger()

    assert spin(lambda: composition.store.get("job-2") is None, timeout=60), (
        "the composed Clear finished action never reached the durable queue"
    )
    assert "job-2" not in table.model.job_ids(), (
        "the finished row was cleared but the composed queue table still shows it"
    )


def test_three_concurrent_downloads_each_keep_their_own_row(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """**Phase 2's first exit criterion, through the assembled application** (`T-079`).

    Three real worker processes against the real pool of three, a real database, and the real
    window — the criterion is about what a user sees, and a widget test with a fake store cannot
    make that claim about the application.

    The assertion is that each row ends up describing *its own* job. Three identical rows is what
    a table with one shared progress field looks like, and it passes any check that counts rows.
    """
    composition = composed(entry_point=child_streaming_its_own_size)
    queue_three(composition, spin, tmp_path / "downloads")
    table = composition.window.queue_view
    assert table is not None, "composition did not give the window a queue table"

    for job_id in ("job-1", "job-2", "job-3"):
        composition.manager.start(job_id)

    # **Asserted while they are live.** Measured: a model routing every message into row 0 passes
    # every completion assertion below, because those read the durable row and the durable rows
    # really are per job. What each row has *drawn* is the only place the routing can be seen.
    assert spin(
        lambda: all(
            table.model.displayed_progress(job_id) is not None
            for job_id in ("job-1", "job-2", "job-3")
        ),
        timeout=60,
    ), "a row never drew progress of its own, so messages are not being routed per row"
    for job_id in ("job-1", "job-2", "job-3"):
        drawn = table.model.displayed_progress(job_id)
        assert drawn is not None and drawn.job_id == job_id, (
            f"{job_id}'s row is showing {drawn.job_id if drawn else None}'s message"
        )

    assert spin(
        lambda: all(
            (job := composition.store.get(job_id)) is not None and job.status is JobStatus.COMPLETED
            for job_id in ("job-1", "job-2", "job-3")
        ),
        timeout=60,
    ), "the three downloads did not all finish"
    table.refresh()

    assert table.model.job_ids() == ("job-1", "job-2", "job-3"), (
        f"the table holds {table.model.job_ids()}, not one row per queued job"
    )
    sizes = {
        job_id: table.model.text_at(job_id, SIZE_COLUMN) for job_id in ("job-1", "job-2", "job-3")
    }
    assert len(set(sizes.values())) == 3, (
        f"the three rows report the same size, so they are not independent: {sizes}"
    )
    for job_id in ("job-1", "job-2", "job-3"):
        assert table.model.text_at(job_id, PROGRESS_COLUMN) == "100%"


def test_the_interface_stays_inside_its_budget_while_three_downloads_run(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """The other half of the criterion: **interactive throughout**, measured (`NFR-001`).

    "The UI stays responsive" is not testable; "no pass of the event loop takes longer than
    `NFR-001`'s ~100 ms budget while three workers stream progress into a six-column table" is.

    This is the measurement `T-017`'s single-job budget test cannot make, because the cost that
    matters here is three streams arriving at once rather than one.
    """
    composition = composed(entry_point=child_streaming_its_own_size)
    queue_three(composition, spin, tmp_path / "downloads")
    for job_id in ("job-1", "job-2", "job-3"):
        composition.manager.start(job_id)

    worst = 0.0
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        started = time.perf_counter()
        qapp.processEvents()
        worst = max(worst, time.perf_counter() - started)
        if all(
            (job := composition.store.get(job_id)) is not None and job.status is JobStatus.COMPLETED
            for job_id in ("job-1", "job-2", "job-3")
        ):
            break
        time.sleep(0.001)

    assert worst < 0.1, (
        f"one pass of the event loop took {worst * 1000:.1f} ms while three downloads were "
        "running, against NFR-001's ~100 ms interaction budget"
    )


def test_a_second_job_starting_does_not_take_the_detail_pane_from_the_first(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """`T-079` changed what composition does with `job_changed`, and this is why.

    With a pool of one, following every watchable transition was right: there was one job and the
    pane was the only place to see it. With three running it means they take turns evicting each
    other several times a second, and a user who selected a row loses it to whichever worker last
    changed state.

    So the pane is claimed once and then belongs to the user. The table is what shows all three.
    """
    composition = composed(entry_point=child_probing_then_waiting)
    queue_three(composition, spin, tmp_path / "downloads")

    composition.manager.start("job-1")
    assert spin(lambda: composition.window.watched_job_id == "job-1", timeout=60), (
        "the first job never claimed the empty detail pane"
    )

    # **Wait for the signal that would steal the pane, rather than for a fixed interval.**
    # Measured: with a one-second sleep here, the mutation that removes the guard *survived* —
    # the assertion could run before job-2's transition was delivered, so the test passed by
    # being early rather than by the guard working.
    #
    # This recorder is connected after composition's own handler, so by the time it sees a
    # watchable status for job-2, the handler that would have called `watch` has already run.
    seen: list[tuple[str, str]] = []
    composition.manager.job_changed.connect(lambda job_id, status: seen.append((job_id, status)))
    watchable = ("probing", "ready", "running", "post_processing")
    composition.manager.start("job-2")
    assert spin(
        lambda: any(job_id == "job-2" and status in watchable for job_id, status in seen),
        timeout=60,
    ), f"job-2 never reached a status that would claim the pane: {seen}"

    assert composition.window.watched_job_id == "job-1", (
        "a second job starting took the detail pane from the job already shown there; with a "
        "pool of N that is three workers evicting each other several times a second"
    )
    table = composition.window.queue_view
    assert table is not None
    assert table.select("job-2") and composition.window.watched_job_id == "job-2", (
        "selecting a row is what changes the detail pane, and it did not"
    )
