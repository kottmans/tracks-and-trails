"""Application setup and wiring — **the one place the object graph is built** (`T-036`).

Every other module in this application depends on the *shape* of what it is given: the manager
takes a `JobStore`, the dialog takes a `JobSink`, the progress view takes a `JobReader`, and none
of them knows SQLite exists (`ARCHITECTURE.md` §3). Something has to know, once, and this is it.

`A-004` adds the single-instance guard in Phase 2.

## Why this task exists at all

`T-036` was filed after review, because nothing owned it: every Phase 1 component could pass its
own tests while the application still opened an empty window. It remains the one task that can
fail while everything else is green, which is why `compose()` is a function returning the graph
rather than a sequence of statements inside `run()` — a graph nothing can hold is a graph nothing
can assert on.

## Shutdown is a lifecycle, and it has an order

Closing the window is a **request**. What follows it has to happen in sequence, and each step is
asynchronous because none of them may block the GUI thread (`T013-R2`, `ARC-005`):

1. `DownloadManager.shutdown()` — cancels the running job, escalates on its own timer, reaps the
   worker's process tree, and stops the result pump on its sentinel. It reports `idle` when the
   last session is released *and* the worker-log listener has drained (`T038-R2`).
2. `QueueWriter.close()` — only then, because the manager's final transitions are still being
   written when it goes idle. It reports `closed` when its thread has finished them.
3. The read connection is closed and the process quits.

Quitting anywhere earlier is what leaves an orphaned `ffmpeg`, a dropped log record, or a
half-written row. `setQuitOnLastWindowClosed(False)` is what makes the order possible at all:
Qt's default is to quit the moment the window disappears, which is step zero of the wrong
sequence.

Qt is imported inside the functions below, not at module scope. `__main__.py` must stay importable
without pulling in Qt so `multiprocessing.freeze_support()` runs first in a frozen build
(`REL-001`, `ARCHITECTURE.md` §3), and `tests/unit/test_skeleton.py` asserts exactly that. A
module-level Qt import here would break that guarantee from a file that never mentions freezing.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tracks_and_trails import __version__

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

    from tracks_and_trails.core.instance_lock import InstanceLock
    from tracks_and_trails.downloader.environment import FfmpegReport
    from tracks_and_trails.downloader.manager import DownloadManager
    from tracks_and_trails.persistence.store import PersistentJobStore
    from tracks_and_trails.persistence.writer import QueueWriter
    from tracks_and_trails.ui.main_window import MainWindow

USAGE = """\
Tracks & Trails {version} — a desktop GUI for yt-dlp.

usage: tracks-and-trails [--version] [--help] [--spawn-probe] [--ytdlp-probe]

  --version      print the version and exit
  --help, -h     print this message and exit
  --spawn-probe  self-test the process model and exit (T-020)
  --ytdlp-probe  self-test the bundled yt-dlp and exit (T-033)

Run with no arguments to open the application window.
"""


def run(argv: Sequence[str]) -> int:
    """Start the application and return the process exit code."""
    args = list(argv[1:])

    # Handled before constructing a QApplication: `--version` must work on a machine with no
    # display, and without paying Qt's startup cost.
    if "--version" in args:
        print(__version__)
        return 0
    if "--help" in args or "-h" in args:
        print(USAGE.format(version=__version__), end="")
        return 0
    # Before Qt, and before anything else that would make this need a display. The frozen
    # build runs exactly this path in CI to prove that spawning a child does not relaunch the
    # application (REL-001, ARCHITECTURE.md §3, T-020).
    if "--spawn-probe" in args:
        from tracks_and_trails._freeze_probe import run_probe

        return run_probe()
    # Before Qt for the same reason as above: a frozen artifact missing its extractors must be
    # diagnosable without a display (T-033).
    if "--ytdlp-probe" in args:
        from tracks_and_trails._freeze_probe import run_ytdlp_probe

        return run_ytdlp_probe()
    # Before Qt for the same reason: a frozen artifact that cannot create its database must
    # be diagnosable without a display (T-014, T014-R3).
    if "--database-probe" in args:
        from tracks_and_trails._freeze_probe import run_database_probe

        return run_database_probe()
    if args:
        print(USAGE.format(version=__version__), end="")
        return 2

    # Before Qt, and before anything that might log: a diagnostic emitted while the application
    # was still starting is exactly the one worth having, and until this runs there is no
    # redacting handler under it (`T-038`, `REQ-026`). Nothing above this point logs, which is
    # why it sits here rather than at the top — `--version` on a machine with no writable cache
    # directory must still print a version.
    from tracks_and_trails.core.logging import configure_logging

    configure_logging()

    from PySide6.QtWidgets import QApplication

    from tracks_and_trails.ui.main_window import APP_NAME, app_icon

    app = QApplication(list(argv))
    # Set before any window exists: platform integration and some desktop environments read
    # these once, when the first window is created.
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_NAME)
    app.setWindowIcon(app_icon())

    from tracks_and_trails.core.instance_lock import AlreadyRunningError

    try:
        composition = compose(app)
    except AlreadyRunningError as refusal:
        # **It says which thing it did** (`ARC-006`): silence is indistinguishable from a hang, and
        # a second launch that exits quietly looks like a broken shortcut. A message box because
        # this is a desktop application launched from an icon, where stderr goes nowhere anybody
        # will see; the same text goes to the log for the case where it was launched from a shell.
        from PySide6.QtWidgets import QMessageBox

        logging.getLogger("tracksandtrails.app").warning("refusing to start: %s", refusal)
        QMessageBox.information(None, APP_NAME, str(refusal))
        # Refusing in favour of the running instance is the outcome `A-004` asks for, not a crash.
        # Non-zero so a script can tell it apart from a normal run that the user closed.
        return 3

    composition.window.show()
    return app.exec()


def default_output_directory() -> Path:
    """Where downloads go until `core/settings.py` lets the user say otherwise.

    The user's own downloads directory, not a subfolder of it: a downloader that invents a
    folder is one the user has to go looking in. `platformdirs` answers this per platform, and
    the test suite redirects it to `tmp_path`, so nothing here writes into a real home directory
    during a run (`ai/TESTING.md` §5).
    """
    from platformdirs import user_downloads_dir

    return Path(user_downloads_dir())


@dataclass(frozen=True)
class Composition:
    """Everything the running application owns, constructed exactly once.

    Held as a value rather than left in local variables so `T-036`'s acceptance criteria can be
    asserted at all: *the manager holds the concrete repository*, *no component is constructed
    twice*, and *every manager signal the UI needs has exactly one connection* are claims about
    an object graph, and a graph nothing can reach is a graph nothing can check.
    """

    app: Any
    window: MainWindow
    manager: DownloadManager
    store: PersistentJobStore
    writer: QueueWriter
    connection: sqlite3.Connection
    ffmpeg: FfmpegReport
    output_directory: Path
    database_path: Path
    settings_path: Path
    shutdown: OrderlyShutdown
    instance: InstanceLock


def compose(
    app: QApplication,
    *,
    database: Path | None = None,
    output_directory: Path | None = None,
    ffmpeg_override: Path | None = None,
    geometry_file: Path | None = None,
    settings_file: Path | None = None,
    entry_point: Callable[..., None] | None = None,
) -> Composition:
    """Build the object graph and wire it up. **Constructs everything; starts nothing.**

    The arguments exist so a test can drive the assembled application against a temporary
    database and a crafted worker (`T-037`), not as configuration — `run()` passes none of them.

    `entry_point` reaches `DownloadManager` unchanged and is not a mocking seam: the tests that
    use it spawn a real process over a real queue (`ai/TESTING.md` §6). It is here because the
    *assembled* application is exactly what `T-036` has to prove, and proving it against a real
    extractor would make the proof depend on a site staying up.
    """
    from tracks_and_trails.core import settings as app_settings
    from tracks_and_trails.core.instance_lock import InstanceLock
    from tracks_and_trails.core.job_state import JobStatus
    from tracks_and_trails.downloader import worker
    from tracks_and_trails.downloader.environment import find_ffmpeg
    from tracks_and_trails.downloader.manager import DownloadManager
    from tracks_and_trails.persistence import db
    from tracks_and_trails.persistence.repositories import HistoryRepository, JobRepository
    from tracks_and_trails.persistence.store import PersistentJobStore
    from tracks_and_trails.persistence.writer import QueueWriter, open_connection_factory
    from tracks_and_trails.ui.main_window import MainWindow

    database_path = database if database is not None else db.database_path()
    downloads = output_directory if output_directory is not None else default_output_directory()
    downloads.mkdir(parents=True, exist_ok=True)

    # **Ownership before anything opens the database** (`A-004`, `ARC-006`, `T-087`). An atomic
    # kernel lock, not `QLocalServer` — Qt documents two local servers listening on one Windows pipe
    # name simultaneously, so *connect-then-listen* admits the two-writer state the guard exists to
    # prevent. Raising `AlreadyRunningError` out of `compose()` is deliberate: there is nothing
    # useful this process can do against a database another process is writing, and `run()` turns it
    # into a message and a non-zero exit rather than a traceback.
    #
    # Taken *before* `db.connect`, because recovery runs on the very next line and would otherwise
    # rewrite rows belonging to a live instance's in-flight jobs.
    instance = InstanceLock(database_path)
    instance.acquire()

    # **The read connection is opened here and the writer opens its own inside its thread**
    # (`ARC-005`). `check_same_thread` stays on, so the two cannot quietly become one.
    connection = db.connect(database_path)
    # Recovery before anything can read the queue: a row left `RUNNING` by a killed application
    # is not in flight, whatever it says (`T-014`, `NFR-003`).
    # The ids are **kept**, not discarded (`T-082`): recovery is silent by design — it happens
    # before the window exists and the user cannot decline it — and the *offer* to restart them is
    # the thing `REQ-012` wants and the thing this list makes possible.
    recovered = JobRepository(connection).recover_interrupted()
    writer = QueueWriter(open_connection_factory(database_path))
    store = PersistentJobStore(connection, writer)

    ffmpeg = find_ffmpeg(ffmpeg_override)
    # `ARC-007`: composition owns `settings.toml`; the manager receives a value. The read happens
    # here so a settings-format change cannot reach `downloader/`, which `T-097` enforces
    # statically.
    # `ARC-008`: the read answers with the settings *and* why they are not the file's, when the
    # file exists and could not be used. The problem is carried to the window rather than logged
    # here — `core/` cannot show a dialog and composition has no window yet.
    settings_read = app_settings.load(settings_file)
    settings = settings_read.settings
    manager = DownloadManager(
        store,
        # History is no longer a second injected sink (`T050-R1`, `T050-R2`): completion is one
        # `JobStore.complete` operation writing both rows in one transaction, so there is no
        # optional collaborator to forget to wire and no partial state to report quietly.
        concurrency=settings.concurrency,
        ffmpeg_override=ffmpeg.path,
        entry_point=entry_point if entry_point is not None else worker.spawn_session,
    )

    def retry(job_id: str) -> None:
        """Hand a retry to the manager, which owns job transitions (`T036-R1`).

        This used to write `FAILED → QUEUED` through the store and then call `manager.start()`
        itself. Both halves were wrong: the store has no signal, so nothing announced the
        transition and the progress view kept showing a failure over a re-queued row; and the
        start was attempted once, while the failed session was still being released, so the pool
        of one refused it and nothing tried again.

        `ui/` still holds no writer (`ARCHITECTURE.md` §3) — the view reports `retry_requested`
        and composition routes it, exactly as it would route a cancel.
        """
        manager.retry(job_id)

    def choose_concurrency(limit: int) -> None:
        """Apply the user's chosen limit and remember it (`REQ-013`, `ARC-007`).

        **Both halves, in this order, and neither is optional.** Applying without saving makes the
        control forget itself at the next launch; saving without applying makes it appear to do
        nothing until a restart, which is the shape `T-075` was — a control that changes what is
        stored and not what runs.

        Bounded on the way in by `with_concurrency`, so a caller that reached here with a value
        outside `REQ-013`'s range stores a usable one. The spinbox's own range already prevents it;
        this is the bound on the *value*, which is where `ARC-007` puts it.
        """
        chosen = app_settings.with_concurrency(settings, limit)
        manager.set_concurrency(chosen.concurrency)
        app_settings.save(chosen, settings_file)

    def choose_pause(paused: bool) -> None:
        """Pause or resume the queue (`UX-001`, `T-080`).

        **Not saved to `settings.toml`, unlike the concurrency limit.** A limit is a preference —
        the user chose 5 and means it next time. A paused queue is a *state*, and restoring it at
        launch would mean starting the application to find it deliberately doing nothing, with the
        reason a session old. `ARC-007`'s file holds settings, and this is not one.
        """
        if paused:
            manager.pause()
        else:
            manager.resume()

    def remove_job(job_id: str) -> None:
        """Route a removal to the manager, which owns it (`T036-R1`, `UX-001`).

        Through the manager rather than the store, for the reason `T036-R1` recorded when a retry
        went the other way: removal of a running job is a cancel *plus* a delete, and only the
        manager knows there is a session to stop. A composition that deleted the row itself would
        leave the worker running and nothing to announce it.
        """
        manager.remove(job_id)

    def reorder_queue(job_ids: list[str]) -> None:
        """Route a reordering to the manager (`REQ-016`, `T-081`).

        Through the manager for `remove_job`'s reason: `_next_waiting` reads `queue_position` to
        decide what starts next, so the object whose scheduling changes is the one that should be
        told.
        """
        manager.reorder(job_ids)

    def clear_finished() -> None:
        """Route a clear-finished to the manager (`REQ-016`, `T-081`)."""
        manager.clear_completed()

    window = MainWindow(
        geometry_file,
        manager=manager,
        jobs=store,
        output_directory=downloads,
        job_reader=store,
        retry=retry,
        concurrency=settings.concurrency,
        on_concurrency_changed=choose_concurrency,
        on_pause_changed=choose_pause,
        on_remove_requested=remove_job,
        on_reorder_requested=reorder_queue,
        on_clear_requested=clear_finished,
        # The same store, through a second protocol: `JobReader` is one job, `QueueReader` is all
        # of them (`T-079`). Two narrow protocols rather than one wide one, so a widget that needs
        # a single row cannot accidentally enumerate the queue.
        queue=store,
        # `T-100`: read-only over the table `T-085` writes. A third narrow protocol rather than
        # widening `QueueReader` — the history view enumerates records and nothing else, and a
        # reader that could also reach jobs would let it.
        history=HistoryRepository(connection),
    )
    # The control follows the queue, not only the other way round: anything that pauses the pool
    # without going through the toolbar still leaves the toggle telling the truth (`T-080`).
    manager.queue_paused.connect(window.show_queue_paused)
    window.report_environment(ffmpeg.summary())
    # `ARC-008`: after the window exists, because that is the earliest a modal can be shown, and
    # before it is interactive, because the reverted setting is what the user would otherwise
    # notice first and have no explanation for.
    if settings_read.problem is not None:
        logging.getLogger("tracksandtrails.app").warning(
            "settings: %s (%s)", settings_read.problem.reason, settings_read.problem.path
        )
        window.report_settings_problem(settings_read.problem)
    # After the settings problem, so a user with both sees the one they cannot act on first and the
    # one they can act on second — an offer buried under a warning gets dismissed with it.
    if recovered:
        logging.getLogger("tracksandtrails.app").info(
            "recovered %d interrupted job(s) on startup", len(recovered)
        )
        window.offer_to_retry_interrupted(recovered)
    logging.getLogger("tracksandtrails.app").info("environment: %s", ffmpeg.summary())

    #: The statuses that mean a worker holds the job, so the window shows its progress. Not
    #: derived from `_STAGE_STATUS` or the pipeline: this is a *presentation* choice about what
    #: is worth watching, and deriving it from the manager's internals would make the two agree
    #: unconditionally (`ai/TESTING.md` §13).
    watchable = (JobStatus.PROBING, JobStatus.READY, JobStatus.RUNNING, JobStatus.POST_PROCESSING)

    def refresh_history_if_the_set_changed(*_: object) -> None:
        """Re-read history when a completion or a clear can have changed which records exist.

        `T-100`'s view has no live subscription because a history row is written once and never
        changes. These are the only two moments the *set* differs: a job completing writes a row in
        the same transaction (`T050-R1`), and clear-finished deletes queue rows while deliberately
        leaving history alone — which is exactly the state the view exists to make visible.
        """
        window.refresh_history()

    manager.job_succeeded.connect(refresh_history_if_the_set_changed)
    manager.queue_cleared.connect(refresh_history_if_the_set_changed)

    def on_job_changed(job_id: str, status: str) -> None:
        """Show a starting job **only when the detail pane is empty** (`T-079`).

        With a pool of one, following every watchable transition was right: there was one job, and
        the pane was the only place to see it. With a pool of N it means three running downloads
        take turns evicting each other from the pane several times a second, and a user who
        selected a row in the queue table loses it to whichever worker last changed state.

        So the pane is claimed once and then belongs to the user: the table shows all N (that is
        what it is for), and selecting a row is what changes the detail. `watched_job_id` is the
        question "is anything shown", asked of the window rather than tracked here.
        """
        if JobStatus(status) in watchable and window.watched_job_id is None:
            window.watch(job_id)

    manager.job_changed.connect(on_job_changed)

    shutdown = OrderlyShutdown(app, manager, writer, connection, instance)
    window.closing.connect(shutdown.begin)
    # **Every quit, not only the one through the window.** Qt aborts the process if a `QThread`
    # is destroyed while running, so a quit that skipped the lifecycle — `QApplication.quit()`
    # from anywhere, a platform session-end — would exit `-6` rather than `0`. See
    # `OrderlyShutdown.stop_for_exit`.
    app.aboutToQuit.connect(shutdown.stop_for_exit)
    # Qt quits when the last window closes, which is step zero of the wrong order. The shutdown
    # lifecycle quits instead, once the worker is gone and the database is closed.
    app.setQuitOnLastWindowClosed(False)

    return Composition(
        app=app,
        window=window,
        manager=manager,
        store=store,
        writer=writer,
        connection=connection,
        ffmpeg=ffmpeg,
        output_directory=downloads,
        database_path=database_path,
        settings_path=settings_file if settings_file is not None else app_settings.settings_path(),
        shutdown=shutdown,
        instance=instance,
    )


class OrderlyShutdown:
    """Closing the window is a request; quitting is what happens when everything has stopped.

    Three steps, in order, each waiting on the previous one's completion **signal** rather than
    on a join (`T013-R2`): the manager stops the worker and its tree, the writer finishes the
    transitions the manager queued on its way down, and only then is the read connection closed
    and the process allowed to exit.

    The order is not cosmetic. Closing the database while the writer thread still holds queued
    revisions loses them; quitting while a worker is alive leaves an orphaned `ffmpeg` on the
    user's disk (`T-019`); and `DownloadManager.idle` deliberately also waits for the worker-log
    listener, because a daemon thread's held records go with the process (`T038-R2`).

    Not a `QObject`: it owns no Qt state and connects to signals as a plain callable, which keeps
    it constructible in a test without an application object.
    """

    def __init__(
        self,
        app: Any,
        manager: DownloadManager,
        writer: QueueWriter,
        connection: sqlite3.Connection,
        instance: InstanceLock | None = None,
    ) -> None:
        self._app = app
        self._manager = manager
        self._writer = writer
        self._connection = connection
        #: Optional, because `T-013`'s tests construct this without one and the ownership guard is
        #: composition's concern rather than the shutdown sequence's. When present it is released
        #: last — see `_writes_are_finished`.
        self._instance = instance
        self._begun = False
        self._finished = False
        manager.idle.connect(self._workers_are_gone)
        writer.closed.connect(self._writes_are_finished)

    @property
    def begun(self) -> bool:
        return self._begun

    @property
    def finished(self) -> bool:
        """Every step has completed and the process may exit."""
        return self._finished

    def begin(self) -> None:
        """Ask the manager to stop. **Returns immediately**; the rest happens on signals."""
        if self._begun:
            return
        self._begun = True
        self._manager.shutdown()

    def _workers_are_gone(self) -> None:
        # `idle` is emitted whenever the last session is released, not only during shutdown, so
        # this has to know whether it was asked for. Closing the writer on an ordinary idle would
        # end persistence while the application was still running.
        if not self._begun or self._finished:
            return
        self._writer.close()

    def stop_for_exit(self) -> None:
        """Last resort for a quit that did not go through the lifecycle. **Bounded, and blocks.**

        Reached from `aboutToQuit`, which Qt emits for every quit — including ones that never
        touched the window. The ordinary path has already finished by then and this does nothing.

        When it has not, the choice is between a bounded wait and `SIGABRT`: Qt aborts the
        process when a running `QThread` is destroyed, which is `exit -6` and a warning on
        stderr instead of a clean exit. `T013-R2`'s rule is that a *lifecycle* is not implemented
        as a wait, and it is not — `begin()` still returns immediately. This is the process
        leaving, where there is no interaction left to block.

        **It cannot reap a worker.** Killing a process tree needs timer ticks and there is no
        event loop left here, so a quit that bypasses the window can still strand a worker. The
        window's own close is the path that does not, which is why it is the one composition
        wires up.
        """
        if self._finished:
            return
        self._manager.shutdown()
        self._writer.close()
        self._writer.wait_for_close()
        self._writes_are_finished()

    def _writes_are_finished(self) -> None:
        if self._finished:
            return
        self._finished = True
        # Last, and only here: every queued revision has been written by now, so nothing is
        # reading or writing this file any more.
        self._connection.close()
        # **After the connection, never before** (`T-087`). The lock says "this process owns this
        # database"; releasing it while a write could still land would let the next launch open a
        # database this one has not finished with. The kernel would release it at exit anyway —
        # doing it here is what makes the ordering true for a process that keeps running, which is
        # every test in `test_composition.py`.
        if self._instance is not None:
            self._instance.release()
        if self._app is not None:
            self._app.quit()
