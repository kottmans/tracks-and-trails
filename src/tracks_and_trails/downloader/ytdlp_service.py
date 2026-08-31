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
from typing import Any, Final, Protocol

from PySide6.QtCore import QObject, QRunnable, Signal

from tracks_and_trails.downloader.environment import user_ytdlp_directory
from tracks_and_trails.downloader.pools import SealedPool
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

_SHARED_POOL: SealedPool | None = None


def pool() -> SealedPool:
    """The shared pool for version queries and installs, created once (`T118-R13`).

    **Behind a gate since `T289-R21`**: shutdown seals it, running work is asked to stop, and the
    last task's completion is what lets the process quit. Before that nothing joined it and
    `app.quit()` could be called with a thread of it still running Python.
    """
    global _SHARED_POOL
    if _SHARED_POOL is None:
        _SHARED_POOL = SealedPool(_POOL_THREADS)
    return _SHARED_POOL


class WorkerExclusion(Protocol):
    """Whatever owns the workers, seen through the two calls an update needs (`T198-R3`).

    **A hold with a lifetime, not a question with an answer.** The first correction injected a
    `workers_active()` predicate and asked it once, on the GUI thread, before submitting the real
    work to the pool — so index lookup, download, extraction and the swap all ran with the queue
    live behind them, and a Start, an admission, a tick or an automatic retry could spawn a worker
    into the middle of it. A predicate can only describe an instant; an operation occupies an
    interval, and the interval is what has to be protected.

    Two methods rather than a manager reference, so this module still knows nothing about queues,
    statuses or slots. `DownloadManager` satisfies it structurally and composition passes it
    directly — nothing adapts, so there is no adapter to be wired wrongly.
    """

    def hold_worker_starts(self, reason: str) -> bool:
        """Stop every worker start until released. `False` if work is active and it cannot."""
        ...

    def release_worker_starts(self) -> None:
        """Let workers start again, and start whatever the hold parked."""
        ...


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
        # **Cooperative cancellation** (`T289-R21`). A `QRunnable` cannot be interrupted, so the
        # only safe stop is one it asks for. Before the work starts is the one point where nothing
        # is half-done — an update that has begun extracting must finish or roll back, which is
        # `T-198`'s rule, so it is deliberately not checked again inside.
        if pool().cancelled:
            self._sink.failed.emit("The application is closing.")
            return
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
        exclusion: WorkerExclusion | None = None,
    ) -> None:
        super().__init__(parent)
        self._directory = user_ytdlp_directory() if directory is None else directory
        #: Who to ask for the tree to be left alone, for as long as this is writing it
        #: (`T198-R3`).
        #:
        #: **Keeping a running worker's code tree stable is a correctness requirement**, and it
        #: cannot be left to platform rename behaviour: on POSIX the rename succeeds by design, so
        #: a worker that has already imported `yt_dlp` resolves its *later* lazy imports — yt-dlp
        #: loads extractors on demand — from whatever now sits at that path. That is a
        #: mixed-version import, and a revert makes it a missing one.
        #:
        #: Two corrections landed here before this one, and both were the wrong shape. The first
        #: reasoned from `_swap_into_place` failing on Windows when the directory is held open —
        #: not a gate, because Python does not keep every imported source file open and the POSIX
        #: path never fails at all. The second asked a `workers_active()` predicate once and then
        #: ran for seconds anyway, which protects the press and not the operation.
        #:
        #: `None` means nothing owns any workers — a service constructed on its own — and then
        #: there is no tree anybody else is importing from to protect.
        self._exclusion = exclusion
        #: Whether *this* service currently holds the exclusion, so it is released exactly once
        #: and only by the holder.
        self._holding = False
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

        self._run_holding_the_tree(work, "installing yt-dlp")

    def revert(self) -> None:
        """Remove the user-managed copy, then re-ask a child what is now in use."""

        def work(sink: _Sink) -> None:
            removed = revert_to_baseline(self._directory)
            sink.reverted.emit(removed)
            sink.resolved.emit(self._resolve())

        self._run_holding_the_tree(work, "reverting yt-dlp")

    def _run_holding_the_tree(self, work: Callable[[_Sink], None], reason: str) -> None:
        """Run a tree-changing operation with every worker start held for its whole length.

        **The hold is taken here, before anything is scheduled, and released in `_on_resolved`
        and `_on_failed`** — the two places every outcome arrives at. That ordering is the
        finding: the work runs on a pool thread for seconds while the GUI thread stays live, so
        anything shorter than the whole operation leaves an interval in which a worker can start
        against a tree that is being replaced.

        **Busy is checked before the hold**, so a refused second operation cannot release the
        first one's exclusion. Nothing is taken that this does not go on to release.

        A refusal to hold is reported in the user's terms and leaves nothing busy: the screen must
        not be left disabled for an operation that never started.
        """
        if self._busy:
            self.failed.emit("Another yt-dlp operation is still running.")
            return
        if self._exclusion is not None:
            if not self._exclusion.hold_worker_starts(reason):
                self.failed.emit(
                    "Downloads are running, and changing yt-dlp underneath them would break "
                    "them. Stop the queue and try again."
                )
                return
            self._holding = True
        self._run(work)

    def _release_the_tree(self) -> None:
        """Hand the workers back, once and only if this service is what is holding them."""
        if not self._holding:
            return
        self._holding = False
        if self._exclusion is not None:
            self._exclusion.release_worker_starts()

    def _run(self, work: Callable[[_Sink], None]) -> None:
        if self._busy:
            self.failed.emit("Another yt-dlp operation is still running.")
            return
        sink = _Sink()
        sink.resolved.connect(self._on_resolved)
        sink.installed.connect(self.installed)
        sink.reverted.connect(self.reverted)
        sink.failed.connect(self._on_failed)
        task = _Task(sink, work)
        if not pool().start(task):
            # Sealed: the application is going down and this work will never run. **Reported
            # through `_on_failed`, not by emitting `failed` here** (`T289-R21`): a refusal that
            # emits the signal directly skips the release, and `_run_holding_the_tree` may already
            # be holding every worker start on this operation's behalf. Nothing takes a hold that
            # is not given back.
            self._on_failed("The application is closing.")
            return
        self._set_busy(True)
        self._running = task

    def _on_resolved(self, resolution: object) -> None:
        self._running = None
        # Released before the signal, not after: a slot connected to `reported` runs inside this
        # call, and the queue should already be free by the time the screen has been told the
        # operation ended.
        self._release_the_tree()
        self._set_busy(False)
        self.reported.emit(resolution)

    def _on_failed(self, reason: str) -> None:
        self._running = None
        # **Failure releases too** (`T198-R3`). Every escape from `_Task.run` lands here, so an
        # install that raised — no network, a bad digest, a directory it could not write — gives
        # the workers back rather than leaving the queue permanently unable to start.
        self._release_the_tree()
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
    "WorkerExclusion",
    "YtdlpService",
    "resolve_in_a_child",
]
