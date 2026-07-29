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

    composition = compose(app)
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
    shutdown: OrderlyShutdown


def compose(
    app: QApplication,
    *,
    database: Path | None = None,
    output_directory: Path | None = None,
    ffmpeg_override: Path | None = None,
    geometry_file: Path | None = None,
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
    from tracks_and_trails.core.job_state import JobStatus
    from tracks_and_trails.downloader import worker
    from tracks_and_trails.downloader.environment import find_ffmpeg
    from tracks_and_trails.downloader.manager import DownloadManager
    from tracks_and_trails.persistence import db
    from tracks_and_trails.persistence.repositories import JobRepository
    from tracks_and_trails.persistence.store import PersistentJobStore
    from tracks_and_trails.persistence.writer import QueueWriter, open_connection_factory
    from tracks_and_trails.ui.main_window import MainWindow

    database_path = database if database is not None else db.database_path()
    downloads = output_directory if output_directory is not None else default_output_directory()
    downloads.mkdir(parents=True, exist_ok=True)

    # **The read connection is opened here and the writer opens its own inside its thread**
    # (`ARC-005`). `check_same_thread` stays on, so the two cannot quietly become one.
    connection = db.connect(database_path)
    # Recovery before anything can read the queue: a row left `RUNNING` by a killed application
    # is not in flight, whatever it says (`T-014`, `NFR-003`).
    JobRepository(connection).recover_interrupted()
    writer = QueueWriter(open_connection_factory(database_path))
    store = PersistentJobStore(connection, writer)

    ffmpeg = find_ffmpeg(ffmpeg_override)
    manager = DownloadManager(
        store,
        # The same object serves both roles, as it already does for `JobStore` and `JobSink`
        # (`T-050`): one queue, one writer thread, one ordering authority. Passing a second
        # persistence owner here would put history writes on a different thread from the job
        # transitions they describe.
        history=store,
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

    window = MainWindow(
        geometry_file,
        manager=manager,
        jobs=store,
        output_directory=downloads,
        job_reader=store,
        retry=retry,
    )
    window.report_environment(ffmpeg.summary())
    logging.getLogger("tracksandtrails.app").info("environment: %s", ffmpeg.summary())

    #: The statuses that mean a worker holds the job, so the window shows its progress. Not
    #: derived from `_STAGE_STATUS` or the pipeline: this is a *presentation* choice about what
    #: is worth watching, and deriving it from the manager's internals would make the two agree
    #: unconditionally (`ai/TESTING.md` §13).
    watchable = (JobStatus.PROBING, JobStatus.READY, JobStatus.RUNNING, JobStatus.POST_PROCESSING)

    def on_job_changed(job_id: str, status: str) -> None:
        if JobStatus(status) in watchable:
            window.watch(job_id)

    manager.job_changed.connect(on_job_changed)

    shutdown = OrderlyShutdown(app, manager, writer, connection)
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
        shutdown=shutdown,
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
    ) -> None:
        self._app = app
        self._manager = manager
        self._writer = writer
        self._connection = connection
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
        if self._app is not None:
            self._app.quit()
