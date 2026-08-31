"""The shutdown gate both `QThreadPool`s sit behind (`T-289`, `T289-R21`).

**Why this exists.** `T-289`'s teardown reading found that neither pool — `ytdlp_service`'s nor
`ui/thumbnails`' — was joined by anything. `OrderlyShutdown` waits for the worker *process* and the
writer *thread*, which are neither of these, so `app.quit()` could be called with a pool thread
still running Python. The process then tears down: Qt destroys the widget tree on the GUI thread
while that pool thread's next allocation can trigger a collection which runs `~QWidget` **there**.
That is the configuration the core dump shows, and nothing sequenced the two.

**What a gate is for.** Three things a bare `QThreadPool` cannot do:

1. **Seal.** After shutdown begins, new work is refused rather than queued. A pool that keeps
   accepting tasks has no last task.
2. **Cancel, cooperatively.** A `QRunnable` cannot be interrupted, so tasks ask `cancelled` at the
   points where stopping is safe and return early. Nothing is killed; work declines to continue.
3. **Say when it is empty, asynchronously.** `drained` is emitted when the last task finishes —
   from a callback, not from a wait. `T013-R2`'s rule is that a lifecycle step does not block the
   GUI thread, and this is the same rule: `seal()` returns immediately.

**Counting is the gate's job, not the task's.** Every runnable is wrapped, so a task that raises,
returns early, or forgets to report still decrements exactly once. The count is adjusted through a
signal emitted **from the pool thread** and delivered to this object's thread, which is where
`drained` is emitted from and where every reader of `outstanding` lives.

**Placement, which the layering rules decide rather than taste.** Both pools need it, and
`ARCHITECTURE.md` §4 allows `ui/` to import `downloader/` but not the reverse, while `core/` may not
import Qt at all. `downloader/` is therefore the only layer both users can legally share, and one
description of this rule in a slightly odd place beats two descriptions in tidy ones.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

if TYPE_CHECKING:
    from collections.abc import Callable


class _Counted(QRunnable):
    """One task, wrapped so the gate learns it finished however it ends.

    **`finally`, because the interesting endings are the ones nobody wrote code for.** A task that
    raises on a pool thread has nowhere to report; if the count were the task's own responsibility,
    that ending would leave the gate waiting for a task that is gone, and shutdown would hang on a
    barrier that can never complete.
    """

    def __init__(self, gate: SealedPool, inner: QRunnable) -> None:
        super().__init__()
        self._gate = gate
        self._inner = inner

    def run(self) -> None:
        try:
            self._inner.run()
        finally:
            # Emitted from a pool thread. The connection is queued because the gate lives on the
            # GUI thread, so the count is only ever touched there.
            self._gate.one_finished.emit()


class SealedPool(QObject):
    """A `QThreadPool` that can be closed for business and say when it has emptied."""

    #: The last task has finished after a `seal()`. Emitted once per seal, on this object's thread.
    drained = Signal()

    #: Internal: a task finished. Public only because Qt needs the signal on the class.
    one_finished = Signal()

    def __init__(self, threads: int, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # **Not a child of anything that gets deleted on the GUI thread** (`T118-R13`): a child
        # `QThreadPool` is destroyed with its parent, and its destructor waits for its runnables on
        # whichever thread does the deleting.
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(threads)
        self._outstanding = 0
        self._sealed = False
        self._cancelled = False
        self.one_finished.connect(self._task_finished)

    @property
    def sealed(self) -> bool:
        """Whether new work is being refused."""
        return self._sealed

    @property
    def cancelled(self) -> bool:
        """What a running task asks to decide whether to stop early."""
        return self._cancelled

    @property
    def outstanding(self) -> int:
        """Tasks started and not yet finished."""
        return self._outstanding

    @property
    def pool(self) -> QThreadPool:
        """The pool itself, for a test that needs to block the thing really in use (`T118-R13`)."""
        return self._pool

    def start(self, task: QRunnable) -> bool:
        """Run `task`, unless this pool is sealed. **The answer is whether it was started.**

        A caller that ignores the answer schedules nothing and reports nothing, which is why this
        returns a value rather than silently dropping the work.
        """
        if self._sealed:
            return False
        self._outstanding += 1
        self._pool.start(_Counted(self, task))
        return True

    def seal(self, *, cancel: bool = True) -> None:
        """Refuse new work, ask running work to stop, and report when the last one has.

        **Returns immediately**, and emits `drained` from a callback — or now, if there is nothing
        to wait for. Calling it twice is harmless and emits nothing the second time.
        """
        if self._sealed:
            return
        self._sealed = True
        if cancel:
            self._cancelled = True
        if not self._outstanding:
            self.drained.emit()

    def wait_bounded(self, milliseconds: int) -> bool:
        """Block for at most `milliseconds`, for the exit path that has no event loop left.

        **Only for `aboutToQuit`.** The asynchronous barrier cannot complete there: `drained`
        arrives through a queued connection and nothing is left to deliver it. `stop_for_exit`
        already makes this argument for the writer — the process is leaving, and there is no
        interaction to block — and the alternative is Qt aborting on a running thread.
        """
        emptied = bool(self._pool.waitForDone(milliseconds))
        if emptied:
            # **The count is reconciled from the pool itself, because the signals cannot arrive.**
            # `outstanding` is decremented through a queued connection, and on this path there is
            # no event loop left to deliver one — so every completion that happened during the wait
            # is still in flight and the gate would go on reporting work that has finished. The
            # pool has just said it has none, and it is the authority.
            self._outstanding = 0
        return emptied

    def _task_finished(self) -> None:
        self._outstanding = max(self._outstanding - 1, 0)
        if self._sealed and not self._outstanding:
            self.drained.emit()


def when_all_drained(pools: tuple[SealedPool, ...], then: Callable[[], None]) -> None:
    """Call `then` once every pool has drained, or immediately if they already have.

    The barrier `T289-R21` asks for. It is a function rather than a class because it holds no state
    a caller needs to see: each pool's `drained` is connected once, and the predicate is re-asked on
    every arrival.
    """

    def check() -> None:
        if all(pool.sealed and not pool.outstanding for pool in pools):
            then()

    for pool in pools:
        pool.drained.connect(check)
    check()
