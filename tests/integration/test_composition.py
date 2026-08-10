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

import json
import shutil
import sqlite3
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Final

import pytest
from PySide6.QtCore import QMetaMethod, QObject
from PySide6.QtWidgets import QApplication, QMessageBox

from tracks_and_trails import app as application
from tracks_and_trails.core import presets
from tracks_and_trails.core import settings as core_settings
from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import DownloadRequest, Job, MediaInfo
from tracks_and_trails.core.paths import thumbnail_cache_path
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
from tracks_and_trails.ui import theme as ui_theme
from tracks_and_trails.ui.queue_view import PROGRESS_COLUMN, SIZE_COLUMN
from tracks_and_trails.ui.row_delegate import PRESET_ROLE
from tracks_and_trails.ui.row_verbs import Verb
from tracks_and_trails.ui.staging import RowState

# --- children the composed application spawns -------------------------------------------------


def child_probing_then_waiting(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **kwargs: Any
) -> None:
    """A probe that answers, then a download that runs until it is cancelled.

    One function for both session kinds because the composed application chooses the kind, not
    the test — which is the point of driving the assembled thing.
    """

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


def child_probing_then_failing(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Read the URL fine, then fail the download with a retryable error.

    **The only shape that produces a retryable queue job** under `UX-003`: a URL that will not
    read never becomes a job at all, so a failed *probe* leaves nothing for the queue's retry to
    act on. Failure has to happen after Add, which is where `REQ-018`'s retry has always lived.
    """
    if kind is SessionKind.PROBE:
        queue.put(
            Probed(job_id=job_id, media=MediaInfo(url=request.url, title="A video that exists"))
        )
        queue.put(WorkerFinished(job_id=job_id, exit_code=0))
        return
    queue.put(Failed(job_id=job_id, kind=ErrorKind.NETWORK, message="the connection dropped"))
    queue.put(WorkerFinished(job_id=job_id, exit_code=1))


def child_probing_then_succeeding(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:

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


def shown_status(composition: application.Composition, job_id: str) -> JobStatus | None:
    """What the queue **row** says about `job_id`.

    `UX-005` removed the detail pane, so the row is the application's answer now. Still the row
    and not `composition.store`, for the reason the pane was watched before it: `T-013`'s ordering
    means the writer thread commits and *then* signals the GUI thread, so a store-based wait can
    pass in the gap before anything on screen has changed.
    """
    view = composition.window.queue_view
    if view is None:
        return None
    job = view.model.job_for(job_id)
    return job.status if job is not None else None


def test_a_queued_playlist_entry_left_on_disk_is_probed_after_restart(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """`T137-R2` at the startup seam, not only the add-dialog callback.

    The durable write and the callback that admits its probe are separate operations.  If the
    application exits between them, a flat playlist entry remains `QUEUED` and unprobed on disk.
    Startup must preserve `ARC-009` rather than admitting that row directly as a download.
    """
    database = tmp_path / "queued-playlist.sqlite3"
    connection = db.connect(database)
    repository = JobRepository(connection)
    request = DownloadRequest(
        url="https://example.invalid/playlist-entry",
        output_directory=str(tmp_path / "downloads"),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )
    repository.append(
        [
            Job(
                id="entry-1",
                url=request.url,
                request=request,
                playlist_id="playlist-1",
                playlist_index=1,
                playlist_title="Trail Sounds",
                queue_position=0,
            )
        ]
    )
    connection.close()

    composition = composed(
        database=database,
        entry_point=child_probing_then_waiting,
    )
    # **The queue is stopped until it is started** (`UX-006`, `T-181`), so a composed test that
    # expects bytes to move has to press Start exactly as a user does. Called on the manager
    # rather than through the toolbar because the seam under test here is not the control.
    #
    # `ARC-009`'s probe-before-download is what this test is about, and Start is now what buys
    # **both** halves: since `T-215` composition holds the previous run's rows until the queue is
    # started, so this entry is read and *then* downloaded on the far side of this call. *(This
    # comment said the probe ran either way, the gate being blind to it. Running it either way is
    # what turned an offline launch into a wall of failures.)*
    composition.manager.start_queue()

    assert spin(lambda: shown_status(composition, "entry-1") is JobStatus.RUNNING, timeout=60), (
        "the playlist entry left queued on disk never reached its download"
    )
    stored = composition.store.get("entry-1")
    assert stored is not None
    assert stored.title == "A video that exists", (
        "startup downloaded a flat playlist entry without first probing it; the live add-dialog "
        "path honours ARC-009, but the durable restart path still admits QUEUED as DOWNLOAD"
    )


def test_an_offline_launch_leaves_the_durable_queue_held(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """**`T-215`.** A bad network moment at launch must not rewrite the queue into failures.

    **Observed live before it was filed**: launched with unreachable URLs, every durably-`QUEUED`
    row became `Failed` within a second — queue stopped, user touching nothing. Startup admitted
    those rows as probe sessions; the stopped-queue gate exempted *every* probe; a failed probe
    fails the job. `REQ-018` then retried the network error and failed it again. The user's
    standing queue is data they committed, and this rewrote it into work they must retry row by
    row.

    The proof is in three parts, because a bare "nothing happened yet" assertion would pass on a
    slow runner for entirely the wrong reason:

    1. **The mechanism, and no clock is involved in it** — `compose()` admitted synchronously, so
       the moment it returns the row is either started or not started at all. The manager must be
       holding **nothing**: `active_job_ids()` empty, which covers running, reserved *and*
       waiting. Asked that way deliberately — the first draft of this test asked `_sessions`
       alone and **passed on the unfixed tree**, because the startup probe was still a
       reservation at that instant. A reservation is a start whose transition has not landed
       yet, which is started, not held.
    2. **What the user sees** — the row still reads `QUEUED`, which `UX-006` shows as `Held`.
    3. **A positive control** — pressing Start reaches `FAILED` carrying the extractor's own text.
       Deferral is not suppression (`T-215`'s own criterion), and a test that could not observe
       the failure at all would be no evidence that it had been deferred.
    """
    database = tmp_path / "offline-launch.sqlite3"
    connection = db.connect(database)
    repository = JobRepository(connection)
    request = DownloadRequest(
        url="https://example.invalid/queued-last-session",
        output_directory=str(tmp_path / "downloads"),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )
    repository.append([Job(id="held-1", url=request.url, request=request, queue_position=0)])
    connection.close()

    # The offline shape: every session kind fails with the timeout a launch on a train produces.
    composition = composed(database=database, entry_point=child_failing_to_extract)
    manager = composition.manager

    assert not manager.active_job_ids(), (
        f"the manager took on {manager.active_job_ids()} at launch with the queue stopped: the "
        "startup probe ran unattended, which is the network moment T-215 is about"
    )
    assert spin(lambda: shown_status(composition, "held-1") is not None, timeout=30), (
        "the queue view never showed the row a previous run left behind"
    )
    assert shown_status(composition, "held-1") is JobStatus.QUEUED, (
        f"the held row reads {shown_status(composition, 'held-1')}, not Held (UX-006)"
    )
    stored = composition.store.get("held-1")
    assert stored is not None and stored.error_message is None, (
        "a row that has never been checked is carrying a failure message, so it claims knowledge "
        "it does not have"
    )

    # **The positive control.** Start is what the user presses; the probe runs then, fails then,
    # and says why — the same failure, moved to the moment it was actually attempted.
    manager.start_queue()
    assert spin(lambda: shown_status(composition, "held-1") is JobStatus.FAILED, timeout=60), (
        "the deferred row never failed once the queue was started, so the fix suppressed the "
        "failure rather than deferring it"
    )
    failed = composition.store.get("held-1")
    assert failed is not None and failed.error_message is not None
    assert "urlopen error" in failed.error_message, (
        f"the extractor's own message did not survive the deferral: {failed.error_message!r}"
    )


def test_a_held_row_still_probes_and_downloads_once_the_queue_starts(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """**`T-215`'s other half**: deferring must not strand a row that can never start.

    The risk the deferral creates is an unprobed row nobody probes — held at launch, and then
    still held after Start because the drain carried it as a download, or not at all. So this
    drives the same seam with a child that answers: held while stopped, and once started it is
    **probed and then downloaded**, with the title from the probe proving `ARC-009`'s order
    survived the parking.
    """
    database = tmp_path / "held-then-started.sqlite3"
    connection = db.connect(database)
    repository = JobRepository(connection)
    request = DownloadRequest(
        url="https://example.invalid/held-then-started",
        output_directory=str(tmp_path / "downloads"),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )
    repository.append([Job(id="wake-1", url=request.url, request=request, queue_position=0)])
    connection.close()

    composition = composed(database=database, entry_point=child_probing_then_waiting)
    manager = composition.manager

    assert not manager.active_job_ids(), (
        "the row did not wait for Start, so what follows proves nothing about waking it"
    )

    manager.start_queue()
    assert spin(lambda: shown_status(composition, "wake-1") is JobStatus.RUNNING, timeout=60), (
        "a row held at launch never reached its download after Start: the deferral stranded it"
    )
    stored = composition.store.get("wake-1")
    assert stored is not None and stored.title == "A video that exists", (
        "the held row was downloaded without being probed first; the deferral must park the "
        "probe, not replace it with a download (ARC-009)"
    )


def test_a_stopped_queue_still_reads_a_url_the_user_pastes(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """**The exemption `T-215` narrowed down to, guarded.** Staging is attended reading.

    `_gate_blocks` stops the queue's own rows and exempts a *staged* probe, and `UX-006` makes
    that exemption load-bearing rather than considerate: the queue is stopped at **every** launch,
    so a gate over staged probes leaves a first-run window unable to read anything pasted into it.

    **Nothing tested it.** Every add-dialog test builds its manager through a fixture that calls
    `start_queue()`, so the whole suite runs with the queue *running* and the launch state — which
    is the only state a first paste ever happens in — was covered nowhere. Measured, not assumed:
    with `_gate_blocks` mutated to gate staged probes too, `tests/ui/test_add_dialog.py` passed
    142 tests. This is the test that fails.

    Driven at the manager, which is the seam the rule lives on; the dialog's own use of it is
    `tests/ui/test_add_dialog.py`'s subject.
    """
    composition = composed(entry_point=child_probing_then_waiting)
    manager = composition.manager
    assert not manager.is_running, (
        "the composed queue is running at launch, so this cannot prove what a stopped one reads"
    )

    read: list[str] = []
    manager.media_probed.connect(lambda job_id, _media: read.append(job_id))
    staged = manager.stage(
        DownloadRequest(
            url="https://example.invalid/just-pasted",
            output_directory=str(tmp_path / "downloads"),
            format_selector="best",
            output_template="%(title)s.%(ext)s",
        )
    )

    assert spin(lambda: staged in read, timeout=60), (
        "a URL pasted into a first-run window was never read: the pause gate caught a staged "
        "probe, and the add dialog can only ever offer what it has read (UX-003)"
    )


def test_a_chosen_download_folder_survives_a_restart_and_is_where_a_job_goes(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """**`T-146`'s criterion, asserted against a real job** rather than against the stored value.

    *"A chosen directory survives a restart and is what a new job actually uses"* — and the second
    half is the one that fails quietly. `T-075` is the shape it fails in: a control that changes
    what is stored and not what runs. So this composes an application whose settings file already
    names a folder — which is what a restart *is*, the file being the only thing that crosses one
    — and then reads the folder off a job the composed application built for itself.

    Not passed as `output_directory=`: that argument is how the tests redirect downloads away from
    a real home directory, and it outranks the stored setting deliberately. A test that passed it
    would be asserting on its own argument.
    """
    chosen = tmp_path / "Trail recordings"
    chosen.mkdir()
    settings_file = tmp_path / "settings.toml"
    assert (
        core_settings.save(
            core_settings.with_download_directory(core_settings.Settings(), chosen), settings_file
        )
        is None
    )

    composition = composed(
        settings_file=settings_file, output_directory=None, entry_point=child_probing_then_waiting
    )

    assert composition.output_directory == chosen, (
        f"the composed application downloads into {composition.output_directory}, not the folder "
        "the settings file names"
    )
    dialog = composition.window.open_add_dialog()
    assert dialog is not None
    try:
        type_urls(dialog, "https://composed.invalid/where-does-this-go")
        dialog.resolve()
        assert spin(lambda: bool(dialog.rows) and dialog.rows[0].committable, timeout=60), (
            f"the URL never resolved: {dialog.status_text()}"
        )
        # Through the dialog's own single request builder (`T-075`, `UX-004`) — the one every
        # committed job goes through, rather than a second construction this test invented.
        built = dialog._request_for(dialog.rows[0])
        assert Path(built.output_directory) == chosen, (
            f"a job this application built writes to {built.output_directory}, not the chosen "
            f"folder {chosen}. The setting is stored and does not run — T-075's shape"
        )
    finally:
        dialog.close()
        QApplication.processEvents()


def test_a_setting_that_could_not_be_saved_says_so(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """**`T146-R2`.** A change that cannot be persisted must not look like one that was.

    `save()` has returned its failure rather than raising since `T109-R9`, and `T-146`'s three
    settings callbacks dropped it — so on a full disk or a read-only profile directory the user
    got a setting that visibly took effect and was gone at the next launch. *"A chosen directory
    survives a restart"* is the criterion, and a silent write failure is exactly where it does not.

    **Driven through a real control on the composed application**: the toolbar spinner, whose
    handler is composition's own `choose_concurrency`. All three callbacks route through the same
    `remember` helper, so this exercises the shared mechanism rather than one caller's copy of it —
    and concurrency is the one of the three with no global side effect, so it can be driven without
    restyling the `QApplication` every other test in this session shares.

    The write is made to fail by putting a **file where the settings file's parent folder should
    be**, after composition has read it: `save()`'s first act is to `mkdir` that parent, and a
    `mkdir` blocked by a file raises on every platform. *(This used a directory in the target's own
    place and relied on `os.replace` refusing it — true, but Windows behaviour I cannot run here,
    which is the class of claim `T146-R3` was. `mkdir` against a file is bedrock on both.)* No
    permission bits either, so it runs as root as well.
    """
    settings_file = tmp_path / "config" / "settings.toml"
    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)
    spinner = composition.window.concurrency_control
    assert spinner is not None, "the composed window has no concurrency control to drive"

    # After composition has read it, so startup is ordinary and only the *write* fails.
    shutil.rmtree(settings_file.parent, ignore_errors=True)
    settings_file.parent.write_text("a file where the folder should be", encoding="utf-8")

    spinner.setValue(spinner.value() + 1)
    QApplication.processEvents()

    assert composition.manager.concurrency == spinner.value(), (
        "the change did not apply, so this proves nothing about reporting a failed save"
    )
    said = composition.window.statusBar().currentMessage()
    assert "could not be saved" in said, (
        f"the status bar says {said!r}. A setting that applied but could not be written is one "
        "the user will lose at the next launch without ever being told"
    )


def test_the_theme_the_file_names_is_the_one_composition_reports(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """`REQ-023`, `T-146`: the stored palette reaches the running application through `run()`.

    **`compose()` carries the name rather than applying it**, and that is deliberate: restyling
    the `QApplication` here would restyle the one every other test in this session shares, which
    is the rule the `theme.apply` comment in `run()` states. So the assertion is that composition
    *reports* what the file said, and `tests/unit/test_theme.py` owns what `apply` then does with
    it.
    """
    settings_file = tmp_path / "settings.toml"
    assert (
        core_settings.save(
            core_settings.with_theme(core_settings.Settings(), "dark"), settings_file
        )
        is None
    )

    composition = composed(settings_file=settings_file)

    assert composition.theme == "dark", (
        f"the settings file asks for dark and composition reports {composition.theme!r}"
    )
    assert composition.theme in ui_theme.THEMES, "composition reported a theme with no palette"


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
    # `UX-003`: both lines are read before either can be queued, so this waits on the rows before
    # committing. The previous version pasted and added in one breath, which was the whole defect
    # `T-118` is about — a URL entering the queue nobody had looked at.
    dialog.resolve()
    assert spin(
        lambda: len(dialog.rows) == 2 and all(row.committable for row in dialog.rows), timeout=60
    ), "the pasted URLs never resolved"
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
    # **The queue is stopped until it is started** (`UX-006`, `T-181`), so a composed test that
    # expects bytes to move has to press Start exactly as a user does. Called on the manager
    # rather than through the toolbar because the seam under test here is not the control.
    composition.manager.start_queue()
    dialog = composition.window.open_add_dialog()
    type_urls(dialog, "https://composed.invalid/movie")
    dialog.resolve()

    assert spin(lambda: bool(dialog.rows) and dialog.rows[0].state is RowState.READY, timeout=60), (
        "the URL never resolved"
    )
    media = dialog.rows[0].media
    assert isinstance(media, MediaInfo) and media.title == "A video that exists"
    # **Nothing is in the queue yet, and that is the corrected behaviour** (`T118-R1`, `UX-005`).
    # Reading a URL is a staging probe with no queue row. The window used to latch its detail pane
    # onto the transient probe id and sit on it — the download completed and the pane still said
    # "ready", because the id it watched was never the one that ran. With no pane, the equivalent
    # claim is that the *queue* has nothing in it, which is the surface a user would be misled by.
    queue = composition.window.queue_view
    assert queue is not None and queue.model.job_ids() == (), (
        f"the queue is showing {queue.model.job_ids() if queue else '?'} for a URL nobody has "
        "added yet"
    )

    # The probe's *session* outlives its result: the manager releases it on a later tick. Adding
    # before then is refused by the pool of one, which the dialog reports rather than raises.
    assert spin(lambda: composition.manager.is_idle, timeout=60), "the probe session never ended"
    dialog.add_to_queue()
    assert "did not start" not in dialog.status_text(), dialog.status_text()
    # **Waited for, not read straight after `add_to_queue()`.** Adding goes through the writer
    # thread, so the ids arrive on a later turn of the event loop; indexing immediately raises
    # `IndexError` from a line that looks like bookkeeping.
    assert spin(lambda: bool(dialog.queued_job_ids), timeout=60), (
        f"nothing was ever queued: {dialog.status_text()}"
    )
    job_id = dialog.queued_job_ids[0]
    assert spin(lambda: shown_status(composition, job_id) is not None, timeout=60), (
        "the window never showed the job the manager was working on"
    )
    # **Waited on the view, not on the store**, and the difference is `T-013`'s ordering rather
    # than a detail. The writer thread commits the row and *then* signals the GUI thread, so
    # `store.get()` answers `COMPLETED` from disk while `job_changed` is still queued. The
    # database leading the UI is exactly the guarantee; a test that polled the store would be
    # asserting on the window in the gap between the two, and this one did.
    assert spin(lambda: shown_status(composition, job_id) is JobStatus.COMPLETED, timeout=60), (
        f"the download never completed; the row says {shown_status(composition, job_id)}"
    )

    job = composition.store.get(job_id)
    assert job is not None and job.output_path is not None
    assert Path(job.output_path).exists(), "the file the queue claims to have downloaded is absent"

    # **The finished row is still in the Queue tab** (`UX-005` §8), which is what makes that tab
    # answer "did it work", and it offers the two file verbs rather than a Cancel. The forbidden
    # half is `tests/ui/test_row_verbs.py`'s; this is the assembled application agreeing with it.
    queue = composition.window.queue_view
    assert queue is not None
    assert job_id in queue.model.job_ids(), (
        "a completed download left the Queue tab before anyone cleared finished jobs"
    )
    assert set(queue.verbs_of(job_id)) == {Verb.OPEN, Verb.REVEAL}, (
        f"a finished row offers {[v.value for v in queue.verbs_of(job_id)]}"
    )


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

    # **One, and it is named** (`UX-005`, `T-124`). It was two: composition also connected
    # `on_job_changed` to claim the detail pane for the first watchable transition (`T-079`). The
    # pane is gone, so that listener is gone with it, and the queue table's model — which keeps
    # the rows current — is the only one left.
    #
    # **The number is written down rather than counted**, which is the whole point: this test
    # exists to fail when a listener appears that nobody meant, and a count derived from the
    # application would agree with the application by construction (`ai/TESTING.md` §13). It has
    # gone one → two → one, and each move was a decision recorded here.
    assert connection_count(manager, "job_changed") == 1, (
        "job_changed should have exactly the queue model's listener now that the detail pane is "
        "gone; a second is how one queued job becomes two of everything downstream"
    )
    # The queue model is the only thing listening to progress. It was zero before `T-079` and
    # briefly shared the signal with a detail view; a table that draws progress is the consumer
    # `T-017`'s repaint budget is about.
    assert connection_count(manager, "progress") == 1, (
        "the queue model should be the only progress listener"
    )
    for name in ("job_removed", "queue_reordered"):
        assert connection_count(manager, name) == 1, (
            f"{name} should have exactly the queue UI listener that reflects the durable change"
        )
    # **Two, and both are named** (`T181-R1`). The run control follows the gate so the toolbar
    # cannot disagree with the queue, and the queue model follows it so a waiting row can read
    # `Held` — two consumers of one fact, answering different questions. A third would mean
    # something else had started deciding what the gate means.
    assert connection_count(manager, "queue_running") == 2, (
        "queue_running should have the run control and the queue model, and nothing else"
    )
    # **One, and it is named.** The queue model rebuilds its rows. This was **two** until `T-170`:
    # the History view re-read as well, because clear-finished was the moment history stopped
    # agreeing with the queue and became the only record of what had been downloaded. That view was
    # removed, and then the ledger behind it was withdrawn outright (`REQ-020`, 2026-08-06), so
    # there is nothing left to re-read — one listener is the whole answer (`T-176`).
    assert connection_count(manager, "queue_cleared") == 1, (
        "queue_cleared should have exactly the queue model's listener"
    )
    # **Nothing at all**, and now for a simpler reason than when this was written. A completion
    # used to write a ledger row in the same transaction (`T050-R1`) that no surface showed; the
    # row and the ledger are both gone, so a completion writes only the job (`T-176`).
    assert connection_count(manager, "job_succeeded") == 0, (
        "job_succeeded gained a listener; a completion updates the job the queue is already "
        "watching, and nothing else records it (REQ-020 withdrawn)"
    )

    dialog = composition.window.open_add_dialog()
    # The dialog adds its own four. Named individually rather than counted in bulk, so a signal
    # gaining a second listener is reported as itself. `job_changed` is **two** here — the queue
    # model's and the dialog's — where it was three before `UX-005` removed the detail pane's.
    for name, expected in (
        ("media_probed", 1),
        ("job_failed", 1),
        ("persistence_failed", 1),
        ("start_rejected", 1),
        ("job_changed", 2),
    ):
        assert connection_count(manager, name) == expected, (
            f"{name} has {connection_count(manager, name)} connections, expected {expected}"
        )
    dialog.close()


# **Three tests about the detail pane were removed here** (`UX-005`, `T-124`).
#
# `test_replacing_the_watched_job_leaves_no_second_listener`,
# `test_watching_the_same_job_twice_does_not_rebuild_the_view` and
# `test_a_second_job_starting_does_not_take_the_detail_pane_from_the_first` all drove
# `window.watch()`, which no longer exists: the row carries progress and state, and selecting one
# opens nothing.
#
# **The first of those was the only test of `JobProgressView.detach` anywhere**, and `UX-005`
# defers what becomes of that widget rather than deciding it — so its guarantee moved to
# `tests/ui/test_job_detail.py::test_a_detached_view_stops_answering_the_manager` *before* this
# deletion, and was mutation-checked there. Deleting it here without that would have turned a
# deferral into a silent deletion.

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
    # **The queue is stopped until it is started** (`UX-006`, `T-181`), so a composed test that
    # expects bytes to move has to press Start exactly as a user does. Called on the manager
    # rather than through the toolbar because the seam under test here is not the control.
    composition.manager.start_queue()
    dialog = composition.window.open_add_dialog()
    type_urls(dialog, "https://composed.invalid/long")
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows) and dialog.rows[0].state is RowState.READY, timeout=60)
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
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows) and dialog.rows[0].state is RowState.READY, timeout=60)
    assert spin(lambda: composition.manager.is_idle, timeout=60), "the probe never finished"

    assert not composition.shutdown.finished, "an ordinary idle closed the writer"

    # **Asserted by writing, not by asking whether the thread is alive.** `close()` is
    # asynchronous, so `is_running` can still be true for a moment after an early close — a check
    # that samples it proves nothing, and a mutation closing the writer on every idle survived
    # exactly that check. What must still be true is that persistence *works*.
    second = composition.window.open_add_dialog()
    type_urls(second, "https://composed.invalid/after-idle")
    # `UX-003`: reading the URL is itself a write, so this waits for the row to resolve before
    # committing. That the row resolved at all is the persistence this test is about.
    second.resolve()
    assert spin(lambda: bool(second.rows) and second.rows[0].committable, timeout=60), (
        "the URL never resolved, so nothing could be queued for reasons other than the writer"
    )
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
    composition = composed(entry_point=child_probing_then_failing)
    # **The queue is stopped until it is started** (`UX-006`, `T-181`), so a composed test that
    # expects bytes to move has to press Start exactly as a user does. Called on the manager
    # rather than through the toolbar because the seam under test here is not the control.
    composition.manager.start_queue()
    dialog = composition.window.open_add_dialog()
    type_urls(dialog, "https://composed.invalid/gone")
    # **The URL reads, and the *download* fails** (`UX-003`, `T118-R1`). This used to fail the
    # probe, which no longer produces anything to retry: an unreadable URL never becomes a queue
    # job. `REQ-018`'s retry has always been about a job that failed downloading.
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows) and dialog.rows[0].committable, timeout=60), (
        "the URL never resolved, so it could never be added"
    )
    dialog.add_to_queue()

    # Waited on the view, per the module docstring: the row is `FAILED` on disk before the
    # manager announces it, and a retry control that exists only after the announcement cannot
    # be asserted on before it. Waiting on `is_idle` here would be worse still — it is true
    # before the download starts.
    # **Waited for, not read straight after `add_to_queue()`.** Adding goes through the writer
    # thread, so the ids arrive on a later turn of the event loop; indexing immediately raises
    # `IndexError` from a line that looks like bookkeeping.
    assert spin(lambda: bool(dialog.queued_job_ids), timeout=60), (
        f"nothing was ever queued: {dialog.status_text()}"
    )
    failed_id = dialog.queued_job_ids[0]
    assert spin(lambda: shown_status(composition, failed_id) is JobStatus.FAILED, timeout=60), (
        "the download never failed, so there is nothing to retry"
    )

    view = composition.window.queue_view
    assert view is not None
    assert Verb.RETRY in view.verbs_of(failed_id), (
        f"a network failure is retryable and the row does not offer it: "
        f"{[v.value for v in view.verbs_of(failed_id)]}"
    )
    failed = composition.store.get(failed_id)
    assert failed is not None and failed.status is JobStatus.FAILED
    transitions: list[str] = []
    composition.manager.job_changed.connect(lambda job_id, status: transitions.append(status))

    # **Through the row's own verb**, which is the route a user has since `UX-005`. Emitting the
    # signal directly would assert on composition's wiring while skipping the thing that reaches
    # it, and `T-124`'s whole risk is a second route that quietly does something else.
    view.trigger_verb(failed_id, Verb.RETRY)

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

    # The row stops showing the old failure, because the manager announced the transition. When
    # composition wrote it through the store instead, nothing did.
    assert spin(lambda: shown_status(composition, failed_id) is not JobStatus.FAILED, timeout=60), (
        "the queue row still shows the failure this retry replaced"
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
    assert app_settings.load(settings_file).settings.concurrency == 5, (
        "the choice never reached disk"
    )

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
    # **The queue is stopped until it is started** (`UX-006`, `T-181`), so a composed test that
    # expects bytes to move has to press Start exactly as a user does. Called on the manager
    # rather than through the toolbar because the seam under test here is not the control.
    composition.manager.start_queue()
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
    assert app_settings.load(settings_file).settings.concurrency == 1, (
        "the decrease never reached disk"
    )

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


#: `NFR-001`'s interaction budget, in seconds. One pass of the event loop longer than this is a
#: visible stall to somebody holding the mouse button down.
BUDGET: Final = 0.1

#: How long the latency above is sampled for, once three downloads are confirmed running.
#:
#: Long enough that every worker delivers many updates inside it — at ~50 a second each, this is
#: over a hundred per job — and short enough that the gate does not dominate the suite. It is not
#: a deadline: nothing is waited *for* here, the loop simply measures for this long.
SAMPLE_WINDOW: Final = 2.0

#: The file `child_streaming_until_released` watches for. Written by the test when it has finished
#: measuring, so the workers stop only after the sampling window closes.
RELEASE_MARKER: Final = "release-the-workers"

#: The three jobs `queue_three` writes. Named once because several tests assert over exactly this
#: set, and a gate that iterated a *subset* would report full concurrency having watched two.
THREE_JOBS: Final = ("job-1", "job-2", "job-3")


def statuses_of(composition: application.Composition) -> dict[str, str | None]:
    """What the store says about each of `THREE_JOBS`, for a failure message.

    A gate that says "three jobs never ran at once" and stops there sends the next reader to the
    manager; one that says two were `completed` and one `queued` sends them to the pool limit.
    """
    return {
        job_id: job.status.value if (job := composition.store.get(job_id)) is not None else None
        for job_id in THREE_JOBS
    }


def child_streaming_until_released(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """A download that streams progress **until the test says stop** (`P2EXIT-R2`).

    `child_streaming_its_own_size` sends two messages and exits, which is right for a routing
    test and wrong for a measurement: three workers that each live a third of a second may barely
    overlap, so a gate that wants to sample *while three downloads run* has no state to sample.
    This one holds the state open, so the sampling window is chosen by the test rather than by
    how fast three interpreters happen to start.

    The release signal is a file rather than an `Event` because the entry point is spawned: a file
    under the job's own output directory needs nothing shared across the process boundary.

    Sizes still differ per job (`child_streaming_its_own_size`'s reason): three identical streams
    are what a table routing every message into one row looks like from outside.
    """
    if kind is SessionKind.PROBE:
        from tracks_and_trails.core.models import MediaInfo

        queue.put(Probed(job_id=job_id, media=MediaInfo(url=request.url, title=f"Video {job_id}")))
        queue.put(WorkerFinished(job_id=job_id, exit_code=0))
        return

    total = 1024 * int(job_id.rsplit("-", 1)[1])
    release = Path(request.output_directory) / RELEASE_MARKER
    sent = 0
    while not release.exists():
        sent += 1
        queue.put(
            Progress(
                job_id=job_id,
                stage=Stage.DOWNLOADING_VIDEO,
                downloaded_bytes=min(total, sent * 64),
                total_bytes=total,
            )
        )
        # ~50 updates a second per worker, so three of them put a real, sustained load through
        # the same queue and table the criterion is about. Slower than this and the gate measures
        # an idle event loop with occasional work in it.
        time.sleep(0.02)

    output = Path(request.output_directory) / f"{job_id}.mp4"
    output.write_bytes(b"x" * total)
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


def test_the_composed_run_control_changes_the_real_manager(
    composed: Callable[..., application.Composition],
) -> None:
    """`T-080`, `T-181`: prove the toolbar-to-manager seam instead of either component alone."""
    composition = composed()
    action = composition.window.run_action
    assert action is not None

    # **Both start stopped, and that is asserted rather than assumed** (`UX-006`). The window's
    # control and the manager's gate are two defaults that must agree; composition does no initial
    # sync, so if either flips the other is silently wrong from the first frame.
    stopped = composition.manager.is_running
    assert not stopped, "the composed manager was running before anybody pressed Start"
    assert not action.isChecked(), "the control claimed a running queue on a stopped one"

    # Read into locals: mypy narrows a property across asserts, so asserting the opposite
    # afterwards types the rest of the test as unreachable and stops it being a gate. The same
    # idiom `job_detail`'s `view.failure` uses.
    action.trigger()
    running = composition.manager.is_running
    assert running
    assert action.isChecked()
    assert action.text() == "&Stop queue", (
        "a running queue's control still offers Start, so its label names the state it is in "
        "rather than what pressing it does"
    )

    action.trigger()
    again = composition.manager.is_running
    assert not again
    assert not action.isChecked()
    assert action.text() == "&Start queue"


def test_the_composed_move_control_updates_the_store_and_the_table(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """`T-081`: the row's verb, composition, manager, writer, and queue view form one reorder path.

    Driven through the **row** since `T124-R3` removed the toolbar's *Move up*: `UX-005` §4 chose
    row verbs rather than a toolbar acting on a selection, because with two tabs that toolbar has
    to guess which list it means. Everything below the verb is the path this test is about and is
    unchanged — `trigger_verb` is the route a click takes.
    """
    composition = composed()
    queue_three(composition, spin, tmp_path / "downloads")
    table = composition.window.queue_view
    assert table is not None
    table.refresh()
    assert Verb.MOVE_UP in table.verbs_of("job-2"), (
        "the row offers no Move up, so this test would prove nothing about the reorder path"
    )

    table.trigger_verb("job-2", Verb.MOVE_UP)

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
    """`T-080`: a durable removal must disappear from the assembled queue view.

    Through the row's own *Remove* since `T124-R3` — see the reorder test above for why the
    toolbar action it used to drive is gone.
    """
    composition = composed()
    queue_three(composition, spin, tmp_path / "downloads")
    table = composition.window.queue_view
    assert table is not None
    table.refresh()
    assert Verb.REMOVE in table.verbs_of("job-2") or Verb.CANCEL in table.verbs_of("job-2"), (
        f"a queued row offers {table.verbs_of('job-2')}, none of which removes it"
    )

    table.trigger_verb("job-2", Verb.REMOVE)

    assert spin(lambda: composition.store.get("job-2") is None, timeout=60), (
        "the composed Remove action never reached the durable queue"
    )
    # **Wait on the UI too** — this file's own rule, which this test broke. The store answering
    # `None` and the view being told are two moments, and asserting the second immediately after
    # the first is the gap the module docstring is about. It passed until `T-115` gave startup
    # admission more event traffic to get through, and then failed only in a full run.
    assert spin(lambda: "job-2" not in table.model.job_ids(), timeout=60), (
        f"the row was deleted but the composed queue table still shows it: {table.model.job_ids()}"
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
    # Wait on the UI, for the reason above and in this file's module docstring.
    assert spin(lambda: "job-2" not in table.model.job_ids(), timeout=60), (
        f"the finished row was cleared but the composed queue table still shows it: "
        f"{table.model.job_ids()}"
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
    # **The queue is stopped until it is started** (`UX-006`, `T-181`), so a composed test that
    # expects bytes to move has to press Start exactly as a user does. Called on the manager
    # rather than through the toolbar because the seam under test here is not the control.
    composition.manager.start_queue()
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
    record_property: Callable[[str, object], None],
) -> None:
    """The other half of the criterion: **interactive throughout**, measured (`NFR-001`).

    "The UI stays responsive" is not testable; "no pass of the event loop takes longer than
    `NFR-001`'s ~100 ms budget while three workers stream progress into a six-column table" is.

    This is the measurement `T-017`'s single-job budget test cannot make, because the cost that
    matters here is three streams arriving at once rather than one.

    ## The measurement needs a positive control (`P2EXIT-R2`)

    An earlier version recorded only the worst `processEvents()` pass and asserted only the
    latency. A reviewer's mutation deleting all three `manager.start()` calls **passed in 60.24
    s**: an idle event loop is very fast, so the gate was satisfied by the absence of the thing it
    was named for. Three separate controls now stand between that and a pass:

    - **`active_job_ids` immediately after the starts** catches a start that never happened, and
      catches it *synchronously*: `start()` reserves the job before the writer thread runs, so the
      deleted-starts mutation now fails in milliseconds instead of after a minute.
    - **Every job seen `RUNNING` at one moment** catches three workers that took turns rather than
      overlapping.
    - **Every job advancing its own update count inside the sampling window** catches a
      measurement taken while the queue was quiet.

    The workers are held open by `child_streaming_until_released` rather than allowed to finish,
    so the window is chosen here instead of by three interpreters' start-up times — and then
    released, because a criterion about three downloads running has to end with three downloads
    that ran.
    """
    downloads = tmp_path / "downloads"
    composition = composed(entry_point=child_streaming_until_released)
    # **The queue is stopped until it is started** (`UX-006`, `T-181`), so a composed test that
    # expects bytes to move has to press Start exactly as a user does. Called on the manager
    # rather than through the toolbar because the seam under test here is not the control.
    composition.manager.start_queue()
    queue_three(composition, spin, downloads)

    # Recorded before the starts, and per job: `Progress` carries the count the table draws, and
    # the store's row does not, so the stream itself is the only place to see three of them.
    seen: dict[str, int] = dict.fromkeys(THREE_JOBS, 0)
    composition.manager.progress.connect(
        lambda message: seen.__setitem__(message.job_id, seen.get(message.job_id, 0) + 1)
    )

    for job_id in THREE_JOBS:
        composition.manager.start(job_id)
    held = composition.manager.active_job_ids()
    assert set(held) == set(THREE_JOBS), (
        f"the manager is holding {held} rather than the three jobs just started, so nothing "
        "below measures an application with three downloads in it"
    )

    assert spin(
        lambda: all(
            (job := composition.store.get(job_id)) is not None and job.status is JobStatus.RUNNING
            for job_id in THREE_JOBS
        ),
        timeout=120,
    ), (
        "three jobs never ran at the same moment, so there was no concurrency to measure: "
        f"{statuses_of(composition)}"
    )

    try:
        before = dict(seen)
        worst = 0.0
        passes = 0
        window = time.monotonic() + SAMPLE_WINDOW
        while time.monotonic() < window:
            started = time.perf_counter()
            qapp.processEvents()
            worst = max(worst, time.perf_counter() - started)
            passes += 1
            time.sleep(0.001)

        advanced = {job_id: seen[job_id] - before[job_id] for job_id in THREE_JOBS}
    finally:
        # Released even if an assertion above fired: three workers spinning on a file that never
        # arrives would outlive the test.
        (downloads / RELEASE_MARKER).write_text("stop", encoding="utf-8")

    assert all(advanced.values()), (
        f"the {SAMPLE_WINDOW} s of latency measured above was not taken while three downloads "
        f"were streaming — updates received per job during it: {advanced}"
    )
    assert passes, "the event loop was never sampled"
    # **The number, not just the verdict.** A pass says the margin was positive and nothing else;
    # three runs of this in the junit XML say whether it is shrinking. `cold_start_seconds` and
    # the network download record theirs for the same reason.
    record_property("worst_event_loop_pass_ms", round(worst * 1000, 1))
    record_property("progress_updates_delivered", sum(advanced.values()))
    assert worst < BUDGET, (
        f"one pass of the event loop took {worst * 1000:.1f} ms while three downloads were "
        f"running, against NFR-001's ~{BUDGET * 1000:.0f} ms interaction budget "
        f"({passes} passes sampled, {sum(advanced.values())} updates delivered)"
    )

    # And they finish, because a criterion about downloads running is not met by downloads that
    # only started.
    assert spin(
        lambda: all(
            (job := composition.store.get(job_id)) is not None and job.status is JobStatus.COMPLETED
            for job_id in THREE_JOBS
        ),
        timeout=120,
    ), f"the workers were released and the jobs never completed: {statuses_of(composition)}"


# --- T-102 / ARC-008: the corrupt-settings report, through the assembled application -------


def test_a_corrupt_settings_file_is_reported_through_the_composed_application(
    qapp: QApplication,
    tmp_path: Path,
    composed: Callable[..., application.Composition],
) -> None:
    """`ARC-008`, `T-102`: the seam between `load()` and the window is the half that can be wired
    wrong while both ends pass their own tests.

    `core` cannot show a dialog and composition has no window when it reads the file, so the
    diagnostic has to travel as data and be presented after the window exists. Nothing below the
    composed application is stubbed: a real malformed file on disk, the real `compose()`, and the
    real dialog it opens.
    """
    from tracks_and_trails.core import settings as app_settings

    settings_file = tmp_path / "settings.toml"
    settings_file.write_text("[queue]\nconcurrency = = 3\n", encoding="utf-8")

    composition = composed(settings_file=settings_file)

    dialog = composition.window.findChild(QMessageBox, "settingsProblemDialog")
    assert dialog is not None, (
        "a corrupt settings file started the application silently; ARC-008 requires the user be "
        "told that defaults are in force, and the seam between load() and the window is where "
        "that gets lost"
    )
    try:
        assert str(settings_file) in dialog.text()
        assert "default settings are in use" in dialog.text()
        # The fallback itself is unchanged: the application runs on defaults rather than refusing.
        assert composition.manager.concurrency == app_settings.CONCURRENCY_DEFAULT
    finally:
        dialog.close()


def test_an_ordinary_settings_file_opens_no_dialog(
    qapp: QApplication,
    tmp_path: Path,
    composed: Callable[..., application.Composition],
) -> None:
    """The silent half, and the one an over-eager implementation breaks.

    A first run has no file at all, and a good file has nothing to report. Either opening a warning
    box would make the report worthless — a dialog that appears every launch is one nobody reads.
    """
    absent = tmp_path / "never-written.toml"
    composition = composed(settings_file=absent)
    assert composition.window.findChild(QMessageBox, "settingsProblemDialog") is None, (
        "a first run opened a settings warning"
    )

    good = tmp_path / "good.toml"
    good.write_text("[queue]\nconcurrency = 4\n", encoding="utf-8")
    # A **different database**, because the first composition still holds the single-instance lock
    # on the default one (`T-087`, `A-004`). Two instances against different databases harm nothing
    # and must both start, which is one of that task's criteria — this is it, incidentally.
    second = composed(settings_file=good, database=tmp_path / "second.db")
    assert second.window.findChild(QMessageBox, "settingsProblemDialog") is None, (
        "a perfectly good settings file opened a warning"
    )
    assert second.manager.concurrency == 4


def test_a_second_composition_against_one_database_is_refused(
    qapp: QApplication,
    tmp_path: Path,
    composed: Callable[..., application.Composition],
) -> None:
    """`T-087`, `A-004`: the guard is taken by `compose()`, before anything opens the database.

    Through the real composition rather than the lock alone, because the ordering is the part that
    can be wired wrong: recovery rewrites rows on the line after `db.connect`, so a guard taken
    afterwards would let a second launch rewrite a live instance's in-flight jobs before refusing.
    """
    from tracks_and_trails.core.instance_lock import AlreadyRunningError

    database = tmp_path / "shared.db"
    first = composed(database=database)
    assert first.instance.is_held

    with pytest.raises(AlreadyRunningError, match="already using"):
        composed(database=database)


def test_the_lock_is_released_only_after_the_database_is_closed(
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
    composed: Callable[..., application.Composition],
) -> None:
    """Ownership outlives the last write, so the next launch never opens a half-closed database."""
    database = tmp_path / "shared.db"
    composition = composed(database=database)
    # Locals both sides of the shutdown, for the reason above: narrowing from the first assert
    # otherwise makes the second one — and everything after it — unreachable to mypy.
    held = composition.instance.is_held
    assert held

    composition.shutdown.begin()
    assert spin(lambda: composition.shutdown.finished, timeout=30), "shutdown never completed"

    released = composition.instance.is_held
    assert not released, (
        "the lock outlived the shutdown lifecycle, so a relaunch would be refused by a process "
        "that has finished with the database"
    )
    # And the next launch really can start.
    composed(database=database)


def test_interrupted_jobs_are_recovered_and_offered_by_the_composed_application(
    tmp_path: Path,
    qapp: QApplication,
    composed: Callable[..., application.Composition],
) -> None:
    """`T-082` end to end: **the seam, which is where an offer gets lost.**

    `recover_interrupted` returned its ids all along and composition threw them away, so the
    recovery was correct and invisible. Nothing below `compose()` is stubbed here — a real
    database carrying a row left `RUNNING`, the real recovery, and the real dialog.
    """
    from tracks_and_trails.core.job_state import JobStatus
    from tracks_and_trails.core.models import DownloadRequest, Job
    from tracks_and_trails.persistence import db
    from tracks_and_trails.persistence.repositories import JobRepository

    database = tmp_path / "library.sqlite3"
    request = DownloadRequest(
        url="https://example.invalid/clip",
        output_directory=str(tmp_path),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )
    seeded = JobRepository(db.connect(database))
    seeded.append([Job(id=f"job-{n}", url=request.url, request=request) for n in range(3)])
    for index in range(3):
        for status in (JobStatus.PROBING, JobStatus.READY, JobStatus.RUNNING):
            stored = seeded.get(f"job-{index}")
            assert stored is not None
            seeded.update(stored.with_status(status))
    seeded._connection.close()

    composition = composed(database=database)

    dialog = composition.window.findChild(QMessageBox, "interruptedJobsDialog")
    assert dialog is not None, (
        "three jobs were left running by an unclean exit and the application started as though "
        "nothing had happened; the recovery is silent by design and the offer is what REQ-012 "
        "asks for"
    )
    assert "3 downloads were interrupted" in dialog.text()

    # And nothing restarted on its own, which is the other half of the criterion.
    for index in range(3):
        job = JobRepository(db.connect(database)).get(f"job-{index}")
        assert job is not None
        assert job.status is JobStatus.FAILED
    dialog.close()


def test_choosing_a_format_on_a_queued_row_changes_the_durable_request(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """`UX-005` §6 / `T-126`, asserted on **the stored request** rather than on the label.

    That distinction is `T118-R6`: the add dialog once updated the displayed selector and nothing
    else, so it showed one format and queued another — `AGENTS.md` §10's `Critical` row,
    downloading something other than what the user chose, silently. A row control that changed only
    what the row says would be the same defect in a new place, and a test reading the row back
    would agree with it.

    So this drives the model the way an editor does, then reads the job out of the **store**.
    """
    composition = composed(entry_point=child_probing_then_waiting)
    queue_three(composition, spin, tmp_path / "downloads")
    # **Refreshed explicitly**, because `queue_three` writes through the store rather than through
    # the add dialog — and adding is the one queue change nothing announces, which is why the
    # dialog's `finished` signal calls this in the real application.
    composition.window.refresh_queue()
    view = composition.window.queue_view
    assert view is not None
    assert spin(lambda: "job-1" in view.model.job_ids(), timeout=60), "the row never appeared"

    before = composition.store.get("job-1")
    assert before is not None
    chosen = presets.by_name("Audio only (original)")
    assert before.request.format_selector != chosen.format_selector, (
        "the row already has the format this test is about to choose, so it would pass without "
        "anything changing"
    )

    row = view.model.row_of("job-1")
    assert row is not None
    assert view.model.setData(view.model.index(row, 0), chosen.name, PRESET_ROLE)

    assert spin(
        lambda: (
            (job := composition.store.get("job-1")) is not None
            and job.request.format_selector == chosen.format_selector
            and job.request.output_template == chosen.output_template
        ),
        timeout=60,
    ), (
        "the format chosen on the row never reached the stored request: "
        f"{stored.request if (stored := composition.store.get('job-1')) is not None else None}"
    )

    # And the row agrees with what is stored, which is the other half of `T118-R6` — the two
    # disagreeing is the defect, and either one alone is half the claim.
    assert spin(
        lambda: view.model.data(view.model.index(row, 0), PRESET_ROLE) == chosen.name, timeout=60
    ), "the stored request changed and the row still reports the old format"


# --- T-180: the partition, through the wiring composition actually builds ------------------


def test_two_databases_get_two_thumbnail_caches_through_composition(
    composed: Callable[..., application.Composition],
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
) -> None:
    """**`T180-R2`.** The partition asserted at the seam that derives it, not at the helper.

    The first version of this proof derived two roots itself, wrote both files by hand and built
    **one** store. That shows `cache_root_for` separates roots handed to it — and it stays green if
    `compose` stops deriving a root from the database, or if `MainWindow` stops passing one to the
    store it builds. The production seam was outside the gate, which is the finding.

    So this builds **two whole applications** over two databases and reads the store each one's own
    queue view actually holds. Nothing here names `cache_root_for`: if the wiring is cut anywhere
    between the database path and the widget that sweeps, the two roots collapse into one and the
    sweep reaches the other instance's picture — which is `ARC-006`'s permitted second instance
    losing its cache, and the whole of `T-180`.
    """
    cache = tmp_path / "cache"
    first = composed(database=tmp_path / "one.sqlite3", cache_directory=cache)
    second = composed(database=tmp_path / "two.sqlite3", cache_directory=cache)

    assert first.cache_root != second.cache_root, (
        "composition handed two databases one cache root; every sweep now reaches the other's files"
    )

    ours = first.window.queue_view
    theirs = second.window.queue_view
    assert ours is not None and theirs is not None

    # Written through each store's *own* resolved path, so a store built with the wrong root puts
    # its file in the wrong place and the assertions below fail rather than silently pass.
    unnamed = "https://pics.invalid/ours-and-unnamed.jpg"
    live = "https://pics.invalid/theirs-and-live.jpg"
    for url, composition in ((unnamed, first), (live, second)):
        path = thumbnail_cache_path(url, composition.cache_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"a picture")

    # One instance sweeps, naming nothing: everything in *its* directory is collectable and
    # nothing in anyone else's is reachable.
    ours.thumbnails.sweep(())

    assert spin(lambda: not thumbnail_cache_path(unnamed, first.cache_root).exists(), timeout=60), (
        "the sweeping instance did not collect its own unnamed picture, so this proves nothing"
    )
    assert thumbnail_cache_path(live, second.cache_root).exists(), (
        "one instance's sweep deleted another database's live picture — T-180's defect, reached "
        "through the composition that builds the wiring rather than through the helper"
    )


def test_the_window_hands_the_partitioned_root_to_both_of_its_stores(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """`T180-R2`'s other half: the queue's store and the add dialog's must share one root.

    `cache_generation` is keyed by directory precisely so a picture the add dialog publishes is one
    the queue's sweep can still see (`T118-R16`). Two roots would put that count back out of reach —
    and a window that partitioned only the queue's store would pass the test above while leaving the
    dialog writing into the shared location this task exists to empty.
    """
    composition = composed(database=tmp_path / "one.sqlite3", cache_directory=tmp_path / "cache")
    view = composition.window.queue_view
    assert view is not None

    dialog = composition.window.open_add_dialog()
    try:
        assert view.thumbnails.cache_root == composition.cache_root, (
            "the queue's store did not get the partitioned root"
        )
        assert dialog.thumbnails.cache_root == composition.cache_root, (
            "the add dialog's store did not get the partitioned root, so a picture it publishes "
            "lands outside the directory the queue's sweep accounts for"
        )
    finally:
        dialog.deleteLater()


def test_a_stored_ffmpeg_location_is_what_the_application_resolves(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**`T-199`'s criterion, through a real resolution rather than the stored value.**

    *"The screen sets an ffmpeg location, it persists, and the resolution path prefers it over
    `PATH`"* — and the second half is the one that fails quietly. So this composes against a
    settings file that already names an ffmpeg, with a `PATH` that also has one, and asserts on
    what `find_ffmpeg` actually returned: the stored file, not the one `PATH` would have found.

    The stand-in is a real executable file rather than a mocked flag, because `find_ffmpeg`
    applies the platform's own executable-discovery rules and a mock would assert nothing about
    them.
    """
    chosen = tmp_path / "somewhere-else" / "ffmpeg"
    chosen.parent.mkdir()
    chosen.write_text("#!/bin/sh\n", encoding="utf-8")
    chosen.chmod(0o755)
    settings_file = tmp_path / "settings.toml"
    assert (
        core_settings.save(
            core_settings.with_ffmpeg_location(core_settings.Settings(), chosen), settings_file
        )
        is None
    )

    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)

    assert composition.ffmpeg.path == chosen, (
        f"the application resolved {composition.ffmpeg.path}, not the location the settings file "
        "names — the setting is stored and does not run"
    )
    assert composition.ffmpeg.available
    # `T-192`'s gate line, and `T-199`'s criterion that it reflects an *overridden* ffmpeg.
    assert "ffmpeg found" in composition.ffmpeg.summary()


def test_an_unusable_stored_ffmpeg_location_still_starts_the_application(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """`ARC-008`: report and fall back, and **the application still starts** (`REQ-024`).

    A missing ffmpeg is a loss of features, never a failure to run — so the assertion is that
    composition completed at all, and that what it reports names the features rather than a path
    the user cannot act on.
    """
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(
        f"[ffmpeg]\nlocation = {json.dumps(str(tmp_path / 'gone' / 'ffmpeg'))}\n",
        encoding="utf-8",
    )

    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)

    assert composition.window is not None, "an unusable ffmpeg location stopped the application"
    read = core_settings.load(settings_file)
    assert read.settings.ffmpeg_location is None
    assert read.problem is not None and "does not exist" in read.problem.reason
