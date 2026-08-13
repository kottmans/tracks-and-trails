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

from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from tracks_and_trails.downloader.environment import user_ytdlp_directory
from tracks_and_trails.downloader.ytdlp_resolution import (
    Resolution,
    ResolutionUnavailableError,
    resolve_in_a_child,
)
from tracks_and_trails.downloader.ytdlp_update import (
    Release,
    UpdateError,
    install_latest,
    latest_release,
    revert_to_baseline,
)

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
        workers_active: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__(parent)
        self._directory = user_ytdlp_directory() if directory is None else directory
        #: Whether any worker could still be importing from the tree this writes (`T198-R3`).
        #:
        #: **Keeping a running worker's code tree stable is a correctness requirement**, and it
        #: cannot be left to platform rename behaviour: on POSIX the rename succeeds by design, so
        #: a worker that has already imported `yt_dlp` resolves its *later* lazy imports — yt-dlp
        #: loads extractors on demand — from whatever now sits at that path. That is a
        #: mixed-version import, and a revert makes it a missing one.
        #:
        #: The first version of this reasoned from `_swap_into_place` failing on Windows when the
        #: directory is held open. That is not a gate: Python does not keep every imported source
        #: file open, and the POSIX path never fails at all.
        #:
        #: Injected rather than read from a manager reference, so this class keeps knowing nothing
        #: about queues; composition supplies `manager.active_job_ids`.
        self._workers_active = workers_active
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

    def _refuse_while_workers_run(self) -> bool:
        """Whether a tree-changing operation must be declined right now (`T198-R3`).

        Reads the predicate every time rather than caching: a queue that was idle when the screen
        opened is not a queue that is idle when the button is pressed.
        """
        if self._workers_active is None or not self._workers_active():
            return False
        self.failed.emit(
            "Downloads are running, and changing yt-dlp underneath them would break them. "
            "Stop the queue and try again."
        )
        return True

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

        if self._refuse_while_workers_run():
            return
        self._run(work)

    def revert(self) -> None:
        """Remove the user-managed copy, then re-ask a child what is now in use."""

        def work(sink: _Sink) -> None:
            removed = revert_to_baseline(self._directory)
            sink.reverted.emit(removed)
            sink.resolved.emit(self._resolve())

        if self._refuse_while_workers_run():
            return
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
