"""Asks a child which yt-dlp is in use, and installs or removes the user-managed copy.

`REQ-025` is two promises — *report the version in use* and *let the user change it without
reinstalling* — and this module is the one surface the GUI uses for both. It exists so `ui/`
touches neither `multiprocessing` nor yt-dlp resolution: `ARCHITECTURE.md` §6 permits
`import yt_dlp` in `worker.py` and `ytdlp_adapter.py` alone, and `ARC-002` puts every yt-dlp
interaction behind this package.

## Why the version comes from a spawned child

Because it has to be the version a **worker** imports, not one this process can infer
(`T-198`'s first criterion). The GUI process never imports yt-dlp, so the only honest answer is
the one a child gives after importing it — the same `ResolutionReport` a real session emits, from
the same `_import_ytdlp` a real session calls. `worker.report_resolution` is that child.

A cached number would be wrong the moment an update lands, so the answer is re-asked after every
install and every revert rather than adjusted in place. **Nothing here computes what the version
*should* be** — that is the class of claim this task exists to stop making.

## Why the work is off the GUI thread

Spawning a child and importing yt-dlp costs seconds; downloading a wheel costs more, and both
would freeze the window (`NFR-001`, `ARCHITECTURE.md` §8). Each runs on a shared pool.

**The pool is module-level and the emitting object is parentless**, which is `T118-R13`'s
finding rather than a preference: a `QThreadPool` owned by a widget blocks the GUI thread in
`~QThreadPool` while it waits for its runnables, and a task emitting through its owner raises
`RuntimeError: Signal source has been deleted` when it outlives it. A task holds its own sink
alive; when the screen goes away Qt severs the connections and a late result goes nowhere.
"""

import multiprocessing
import queue as queue_module
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from tracks_and_trails.downloader import worker
from tracks_and_trails.downloader.environment import user_ytdlp_directory
from tracks_and_trails.downloader.protocol import ResolutionReport, WorkerFinished
from tracks_and_trails.downloader.ytdlp_update import (
    Release,
    UpdateError,
    install_latest,
    latest_release,
    revert_to_baseline,
)

#: How long to wait for a child to import yt-dlp and answer. Generous: `spawn` re-imports the
#: interpreter and yt-dlp is a large package, so a slow machine under load can take seconds. A
#: query that has not answered by now is one the user should be told about rather than waited on.
RESOLUTION_TIMEOUT_SECONDS: Final = 90.0

#: One thread. These tasks are seconds-long, network- or process-bound, and there is never a
#: reason to run two at once — the second would be asking the same question or fighting the first
#: for the same directory.
_POOL_THREADS: Final = 1

_SHARED_POOL: QThreadPool | None = None


def _pool() -> QThreadPool:
    """The shared pool for version queries and installs, created once (`T118-R13`)."""
    global _SHARED_POOL
    if _SHARED_POOL is None:
        _SHARED_POOL = QThreadPool()
        _SHARED_POOL.setMaxThreadCount(_POOL_THREADS)
    return _SHARED_POOL


class ResolutionUnavailableError(Exception):
    """No child could say which yt-dlp is in use, with a reason fit to show a user."""


@dataclass(frozen=True, slots=True)
class Resolution:
    """Which yt-dlp a worker imported, and where it came from.

    `source` is a label such as `"bundled baseline"` or `"user-managed copy (OPS-002)"`, never a
    path (`NFR-007`) — `environment.YtdlpCandidate` carries the same distinction for the same
    reason.

    `rejected` is why an earlier candidate was not used. `ARCHITECTURE.md` §6 requires a rejected
    override to be **reported, never silently ignored**, and a user who installed a copy that
    does not import needs to be told that rather than left reading a baseline version and
    wondering why their update did nothing.
    """

    version: str
    source: str
    rejected: tuple[str, ...] = ()

    @property
    def is_user_managed(self) -> bool:
        """Whether this came from the user's own copy rather than the shipped baseline.

        Read from the resolved `source` rather than by asking the filesystem whether the
        directory exists: a directory that exists but does not import is **not** what is in use,
        and the button that offers to remove it should say so from the same fact the version
        came from.
        """
        return "user-managed" in self.source


def resolve_in_a_child(
    directory: Path | None = None,
    *,
    entry_point: Callable[..., Any] | None = None,
    timeout: float = RESOLUTION_TIMEOUT_SECONDS,
) -> Resolution:
    """Spawn a child, have it import yt-dlp, and return what it reported.

    Blocking, and deliberately not called from the GUI thread — `YtdlpService` is what puts it on
    the pool. Kept separate from that class so the mechanism is testable without a Qt event loop.

    `spawn` for the reason `ARC-002` gives: forking a process that has created a `QApplication`
    is unsafe, and one start method everywhere means both platforms exercise the same path.
    """
    target = worker.spawn_resolution if entry_point is None else entry_point
    context = multiprocessing.get_context("spawn")
    message_queue: Any = context.Queue()
    child = context.Process(
        target=target,
        args=(message_queue,),
        kwargs={"user_ytdlp_directory": directory},
        daemon=True,
    )
    report: ResolutionReport | None = None
    started = False
    try:
        child.start()
        started = True
        while True:
            try:
                message = message_queue.get(timeout=timeout)
            except queue_module.Empty:
                raise ResolutionUnavailableError(
                    "Checking the yt-dlp version took too long and was stopped."
                ) from None
            if isinstance(message, ResolutionReport):
                report = message
            if isinstance(message, WorkerFinished):
                break
    finally:
        # The child is short-lived and daemonic, but leaving it unjoined would leak a zombie per
        # query on POSIX. `terminate` covers the child that answered and then hung on exit.
        #
        # **Guarded on `started`**: a spawn that fails — an unpicklable target is the way a test
        # reaches this — leaves a `Process` that `join` refuses with *"can only join a started
        # process"*, and that secondary error would replace the real one on its way out.
        if started:
            if child.is_alive():
                child.terminate()
            child.join(timeout=5.0)
        message_queue.close()

    if report is None:
        raise ResolutionUnavailableError(
            "No usable yt-dlp could be loaded. The application cannot download until this is "
            "resolved; reverting to the bundled version is the first thing to try."
        )
    return Resolution(
        version=report.ytdlp_version,
        source=report.ytdlp_source,
        rejected=tuple(report.rejected),
    )


class _Sink(QObject):
    """What a running task emits through, owned by the task rather than by the screen.

    Parentless on purpose (`T118-R13`): a task holds one alive for as long as it runs, and a
    result arriving after the settings screen closed is delivered to an object nobody is
    connected to instead of into freed memory.
    """

    resolved = Signal(object)
    installed = Signal(object)
    reverted = Signal(bool)
    failed = Signal(str)


class _Task(QRunnable):
    """One call on the pool, with every failure turned into a sentence for the user.

    **Nothing escapes `run`.** A `QRunnable` that raises does so on a pool thread, where there is
    no handler and the traceback goes to stderr while the screen waits forever for a signal that
    is never emitted.
    """

    def __init__(self, sink: _Sink, work: Callable[[_Sink], None]) -> None:
        super().__init__()
        self._sink = sink
        self._work = work

    def run(self) -> None:
        try:
            self._work(self._sink)
        except (UpdateError, ResolutionUnavailableError) as error:
            self._sink.failed.emit(str(error))
        # Broad on purpose: a pool thread has nowhere else to report, and an unhandled raise
        # here leaves the screen waiting for a signal that never comes.
        except Exception as error:
            self._sink.failed.emit(
                f"The operation could not be completed ({type(error).__name__})."
            )


class YtdlpService(QObject):
    """The GUI's whole view of yt-dlp's version: read it, update it, put it back.

    One operation at a time. The screen disables its buttons while `busy` is true, and this
    refuses anyway — the guard belongs where the state is, not only where the buttons are.
    """

    #: A `Resolution`: which yt-dlp a worker imported.
    reported = Signal(object)
    #: The `Release` that was installed. **Not the version now in use** — that is `reported`,
    #: re-asked from a child immediately afterwards, because an install that lands and then does
    #: not import is exactly the failure this task's fourth criterion is about.
    installed = Signal(object)
    #: Whether there was a user-managed copy to remove.
    reverted = Signal(bool)
    #: Why the last operation did not happen, in the user's terms.
    failed = Signal(str)
    #: Whether an operation is running, so the screen can disable its controls.
    busy_changed = Signal(bool)

    def __init__(
        self,
        directory: Path | None = None,
        parent: QObject | None = None,
        *,
        entry_point: Callable[..., Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self._directory = user_ytdlp_directory() if directory is None else directory
        #: The child a version query runs, injected for the reason `compose`'s is (`T-037`): the
        #: real one imports yt-dlp, so without this seam the pool path — the signals, the busy
        #: state, and the task's own lifetime — has no test that does not take seconds and a real
        #: package. That path is where this class's only defect so far lived.
        self._entry_point = entry_point
        self._busy = False
        #: The task currently on the pool, held so Python does not collect it mid-flight.
        #:
        #: **Found by the composition regression**, as `RuntimeError: Signal source has been
        #: deleted` raised from inside `_Task.run`. `QThreadPool.start` takes ownership of the
        #: C++ runnable, which does not keep the Python object — or the `_Sink` it holds — alive,
        #: so a task whose only reference was the argument to `start()` could be collected while
        #: still running and emit through a deleted object. This is `T118-R13` again: parentless
        #: is right, unreferenced is not.
        self._running: _Task | None = None

    @property
    def directory(self) -> Path:
        """Where a user-managed copy lives (`OPS-002`)."""
        return self._directory

    @property
    def busy(self) -> bool:
        return self._busy

    def refresh(self) -> None:
        """Ask a child which yt-dlp it imports, and emit `reported`."""
        self._run(lambda sink: sink.resolved.emit(self._resolve()))

    def _resolve(self) -> Resolution:
        return resolve_in_a_child(self._directory, entry_point=self._entry_point)

    def install_latest_version(self) -> None:
        """Install the newest yt-dlp wheel, then re-ask a child what is now in use.

        **The re-ask is inside the same task**, so `installed` and `reported` arrive in that
        order and the screen never shows a new version number sourced from the installer's own
        claim. `install_latest` returns what it *wrote*; only a child can say what now *imports*.
        """

        def work(sink: _Sink) -> None:
            release = install_latest(self._directory, release=latest_release())
            sink.installed.emit(release)
            sink.resolved.emit(self._resolve())

        self._run(work)

    def revert(self) -> None:
        """Remove the user-managed copy, then re-ask a child what is now in use."""

        def work(sink: _Sink) -> None:
            removed = revert_to_baseline(self._directory)
            sink.reverted.emit(removed)
            sink.resolved.emit(self._resolve())

        self._run(work)

    def _run(self, work: Callable[[_Sink], None]) -> None:
        if self._busy:
            self.failed.emit("Another yt-dlp operation is still running.")
            return
        sink = _Sink()
        sink.resolved.connect(self._on_resolved)
        sink.installed.connect(self.installed)
        sink.reverted.connect(self.reverted)
        sink.failed.connect(self._on_failed)
        self._set_busy(True)
        task = _Task(sink, work)
        self._running = task
        _pool().start(task)

    def _on_resolved(self, resolution: object) -> None:
        self._running = None
        self._set_busy(False)
        self.reported.emit(resolution)

    def _on_failed(self, reason: str) -> None:
        self._running = None
        self._set_busy(False)
        self.failed.emit(reason)

    def _set_busy(self, busy: bool) -> None:
        if busy != self._busy:
            self._busy = busy
            self.busy_changed.emit(busy)


__all__ = [
    "Release",
    "Resolution",
    "ResolutionUnavailableError",
    "UpdateError",
    "YtdlpService",
    "resolve_in_a_child",
]
