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

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

if TYPE_CHECKING:
    from collections.abc import Callable


#: How often a sealed pool re-asks whether it has really emptied. Short enough that shutdown does
#: not visibly wait on the poll, long enough not to spin: the thing being waited for is a thread
#: leaving `run`, which takes microseconds once the work is done.
_CONFIRM_EVERY_MS: Final = 10


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
            # Emitted from a pool thread, and **from inside `run`** — which is the reason the
            # count alone cannot end the barrier (`T289-R21`, second pass). At this line the
            # thread is still executing this method and `activeThreadCount()` still reports it, so
            # a `drained` emitted on the strength of the count fires while a pool thread is still
            # live: a probe measured exactly that. This is a *hint* that the pool may now be
            # empty; `_confirm` asks the pool itself whether it is.
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
        self._drained_reported = False
        #: Re-asks the pool whether it is really empty. Started by `seal()`, stopped once it is.
        #: **A poll and not only a signal**, because the completion signal is emitted from inside
        #: the task's own `run` and therefore always arrives while that thread is still live.
        self._confirming = QTimer(self)
        self._confirming.setInterval(_CONFIRM_EVERY_MS)
        self._confirming.timeout.connect(self._confirm)
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

    def is_empty(self) -> bool:
        """Whether the pool has no runnable left, **asked of the pool** rather than of the count.

        `waitForDone(0)` returns immediately with the pool's own answer. The count is checked too,
        so a task that was started and whose completion has not been delivered yet cannot be
        mistaken for an empty pool.

        **`activeThreadCount()` was checked here as well and is not any more**: `waitForDone(0)` is
        already false whenever it is non-zero, so no mutation of it could fail a test — the same
        unfalsifiable-term problem `T289-R20` ruled on. One condition that decides beats two where
        only one can be wrong.
        """
        return not self._outstanding and bool(self._pool.waitForDone(0))

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
        self._confirm()
        if not self._drained_reported:
            self._confirming.start()

    def wait_bounded(self, milliseconds: int) -> bool:
        """Block for at most `milliseconds` and say whether the pool emptied.

        **Only for `aboutToQuit`.** The asynchronous barrier cannot complete there: `drained`
        arrives through a queued connection and nothing is left to deliver it. `stop_for_exit`
        already makes this argument for the writer — the process is leaving, and there is no
        interaction to block — and the alternative is Qt aborting on a running thread.

        **The answer is a diagnostic, not a permission.** `False` means the pool overran the
        threshold; it does not mean the caller may stop waiting, and `stop_for_exit` calls
        `wait_until_empty` after reporting it (`T289-R21`, third pass).
        """
        emptied = bool(self._pool.waitForDone(milliseconds))
        if emptied:
            self._settle()
        return emptied

    def wait_until_empty(self) -> None:
        """Block until the pool really has nothing running, however long that takes.

        **The only honest end to the no-event-loop path** (`T289-R21`, third pass). The bounded
        wait was allowed to expire and `_leave()` was called anyway, which is the measured
        `active=1` teardown this whole task exists to remove: truthful bookkeeping and a warning
        describe the race, they do not sequence it. Returning is what permits Qt to destroy the
        widget tree, so returning is the thing that may not happen early.

        **It is not an unbounded wait added on top of a bounded one.** Qt already waits here — a
        `QThreadPool` destroyed with runnables in flight blocks in its destructor, or aborts — so
        the choice was never *wait* versus *don't*; it was *wait at a point where the widgets are
        still standing* versus *wait in the middle of tearing them down*. An absolute exit deadline
        would need the work to sit behind a boundary that can genuinely be killed, which is a
        design change and not something this call can decide.

        `waitForDone(-1)` has no deadline. The count is reconciled from the pool afterwards for the
        reason `wait_bounded` gives: the completions are still in flight on a queued connection
        that nothing is left to deliver.
        """
        self._pool.waitForDone(-1)
        self._settle()

    def _settle(self) -> None:
        """Bring the gate's own state into line with a pool a wait has just emptied.

        **The count is reconciled from the pool itself, because the signals cannot arrive.**
        `outstanding` is decremented through a queued connection, and the paths that wait are the
        ones with no event loop left to deliver one — so every completion that happened during the
        wait is still in flight and the gate would go on reporting work that has finished. The pool
        has just said it has none, and it is the authority.

        **And the confirmation poll is stopped here** (`T-128`). `seal()` starts a `QTimer` owned by
        this object and only `_confirm` stops it, which is reached through the event loop; a gate
        waited to empty and then dropped would leave a live timer on an object destroyed by
        whichever thread collects it. That is the orphaned-timer fault the UI suite fails on, and
        it cost an overnight soak to attribute the last time. `drained` is deliberately **not**
        emitted from here: a blocking wait is not the asynchronous barrier, and a later completion
        can still reach `_confirm` through `one_finished` if an event loop does come back.
        """
        self._outstanding = 0
        self._confirming.stop()

    def _task_finished(self) -> None:
        self._outstanding = max(self._outstanding - 1, 0)
        self._confirm()

    def _confirm(self) -> None:
        """Emit `drained` once — and only once the pool itself says it has nothing running."""
        if self._drained_reported or not self._sealed or not self.is_empty():
            return
        self._drained_reported = True
        self._confirming.stop()
        self.drained.emit()


def when_all_drained(pools: tuple[SealedPool, ...], then: Callable[[], None]) -> None:
    """Call `then` once every pool has drained, or immediately if they already have.

    The barrier `T289-R21` asks for. It is a function rather than a class because it holds no state
    a caller needs to see: each pool's `drained` is connected once, and the predicate is re-asked on
    every arrival.

    **The predicate is the pool's own `is_empty()`, not a second one written here** (`T289-R21`,
    third pass). The first version asked `sealed and not outstanding`, which is strictly weaker
    than what `drained` itself waits for: a runnable started on the underlying pool is one the gate
    never counted, so `outstanding` reads zero while the pool is plainly busy. A reviewer probe
    built exactly that and this barrier released the quit at `active=1` — while the gate's own
    `drained` correctly withheld. Two predicates for one question is one predicate too many, and
    the authoritative one is the one that asks the pool.
    """

    def check() -> None:
        if all(pool.sealed and pool.is_empty() for pool in pools):
            then()

    for pool in pools:
        pool.drained.connect(check)
    check()
