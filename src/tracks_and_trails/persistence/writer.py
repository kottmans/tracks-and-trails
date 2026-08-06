"""The one thread that writes to the queue, so no widget ever waits on SQLite (`ARC-005`).

`NFR-001` and `ARCHITECTURE.md` §8 are unqualified: the GUI thread is never blocked on disk. The
first widget to persist anything (`T-016`) blocked it anyway, because `JobRepository` is
synchronous and nothing said which thread it belongs on. `T016-R3` measured the result — 0.302 s
of frozen GUI under a contended writer lock, then an `OperationalError` that reached no user.

## Why one writer and not a connection per caller

SQLite permits exactly one writer at a time whatever we do. Serialising in-process therefore
removes self-contention rather than converting it into `SQLITE_BUSY` retries to tune a timeout
against — and it gives `queue_position` a single ordering authority. Two threads racing
`MAX(queue_position) + 1` would hand out the same position, and the queue would disagree with
itself about the order the user typed.

## The connection is opened *in* this thread, never handed to it

`persistence/db.connect()` uses `sqlite3.connect()` with `check_same_thread=True` left on, so a
connection used from the thread that did not create it raises rather than corrupting quietly.
This module keeps that check: it takes a **factory** and calls it on the writer thread the first
time there is something to write. Passing a live connection across the boundary would have meant
turning the check off, which is the one change that would make a real threading bug silent.

## Every queue write comes here, and shutdown is a lifecycle

`T016-R3`: the first version moved only `append` off the GUI thread while the manager's status
updates stayed synchronous, so a start, a cancel or a stage change still blocked — 5.017 s under a
held lock, ending in an uncaught `OperationalError`. `revise()` closes that half. And `close()`
returns immediately, reporting completion through `closed`: the version that called
`QThread.wait()` blocked the GUI thread for 4.921 s, which is the defect `T013-R2` had already
ruled on for the manager.

## Failure is reported, not swallowed

Every submission ends in the caller's callback, on the GUI thread, with either `None` or a
message. There is no path that drops a write silently — the thing `T016-R3` found the previous
design doing with an exception.
"""

import sqlite3
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from PySide6.QtCore import QObject, QThread, Signal, Slot

from tracks_and_trails.core.models import Job
from tracks_and_trails.persistence.repositories import JobRepository


class ConnectionFactory(Protocol):
    """Opens a database connection. Called **on the writer thread**, not before."""

    def __call__(self) -> sqlite3.Connection: ...


class _Worker(QObject):
    """Lives on the writer thread and owns the connection it creates there."""

    #: `(token, error)` — `error` is the empty string on success. A plain `str` rather than an
    #: optional because Qt's queued-signal marshalling is happier with concrete types, and the
    #: public surface converts it back to `str | None` at `QueueWriter.finished`.
    done = Signal(int, str)

    def __init__(self, open_connection: ConnectionFactory) -> None:
        super().__init__()
        self._open_connection = open_connection
        self._connection: sqlite3.Connection | None = None

    @Slot(int, object)
    def write(self, token: int, jobs: Sequence[Job]) -> None:
        """Append `jobs` in one transaction, then report. **Never raises into the event loop.**

        A raise here would cross a queued connection and take down the writer thread, leaving
        every later submission unanswered — a caller waiting on a callback that can no longer
        arrive. So every failure becomes a message, including the one that matters most: not
        being able to open the database at all.
        """
        self._perform(token, lambda connection: JobRepository(connection).append(jobs))

    @Slot(int, object)
    def revise(self, token: int, job: Job) -> None:
        """Overwrite one stored job, then report (`T016-R3`).

        The manager's status transitions come through here. They were the half `ARC-005` did not
        cover: `append` moved to this thread while `update` stayed a synchronous call from
        `DownloadManager._save_and_announce()`, so a start, a cancel or a stage change still
        blocked the GUI thread — measured at 5.017 s under a held writer lock, ending in an
        uncaught `OperationalError`. One writer means *every* queue write, not the new ones.
        """
        self._perform(token, lambda connection: JobRepository(connection).update(job))

    @Slot(int, object)
    def requeue_at_end(self, token: int, job: Job) -> None:
        """Write one job with a freshly allocated tail position, then report (`T-080`).

        Here rather than on the GUI thread for every other write's reason, plus one of its own:
        the tail is read and written in the same transaction, and `ARC-005`'s single writer is what
        makes that allocation the only one in flight.
        """
        self._perform(token, lambda connection: JobRepository(connection).requeue_at_end(job))

    @Slot(int, object)
    def reorder(self, token: int, job_ids: Sequence[str]) -> None:
        """Rearrange the queue, then report (`REQ-016`, `T-081`).

        On this thread for `ARC-005`'s reason and one of its own: reordering reads several rows and
        rewrites their positions in one transaction, and the single writer is what stops an append
        allocating a tail position in the middle of it.
        """
        self._perform(token, lambda connection: JobRepository(connection).reorder(job_ids))

    @Slot(int, object)
    def clear_completed(self, token: int, _: object) -> None:
        """Delete every finished job's row, then report (`REQ-016`, `T-081`).

        Takes an ignored payload so it can share `_submit`'s two-argument signal shape rather than
        needing a signal of its own — the token is the part that matters, and a slot with a
        different arity would need one.
        """
        self._perform(token, lambda connection: JobRepository(connection).clear_completed())

    @Slot(int, object)
    def remove(self, token: int, job_id: str) -> None:
        """Delete one job's row, then report (`UX-001`, `T-080`).

        A delete is a queue write like any other, so it belongs on this thread and in this order:
        a removal asked for while a transition for the same job is still in flight must land
        behind it, and the single writer is what guarantees that.
        """
        self._perform(token, lambda connection: JobRepository(connection).remove(job_id))

    @Slot(int, object)
    def complete(self, token: int, job: Job) -> None:
        """Store a completed job. One row, one transaction.

        Here rather than on the GUI thread for the same reason every other write is: `ARC-005` is
        unqualified, and completion is persisted from `DownloadManager`, on the GUI thread.

        *(This carried a `HistoryEntry` beside the job and wrote both in one transaction, because
        `T050-R1` found a hard exit between two separate commits leaving a durably completed job
        with no record of what it obtained. `REQ-020` was withdrawn on 2026-08-06 and there is no
        second row — the pairing this slot existed to guarantee has nothing left to pair.)*
        """
        self._perform(token, lambda connection: JobRepository(connection).update(job))

    def _perform(self, token: int, work: Callable[[sqlite3.Connection], object]) -> None:
        """Run `work` against this thread's connection, reporting through `done` either way.

        Takes the **connection** rather than a `JobRepository`, because more than one repository
        writes here now. Building the repository inside `work` keeps that choice at the call site
        and keeps this method's contract — open once, never raise into the event loop — in one
        place.
        """
        try:
            if self._connection is None:
                self._connection = self._open_connection()
            work(self._connection)
        except Exception as error:  # see `write`: nothing may escape into the event loop
            self.done.emit(token, f"{type(error).__name__}: {error}")
            return
        self.done.emit(token, "")

    @Slot()
    def close(self) -> None:
        """Close the connection **on the thread that opened it**, then stop the event loop.

        Both halves have to happen here rather than in `QueueWriter.close()`. Calling this
        directly from the GUI thread is what the first version did, and `check_same_thread`
        caught it immediately: *"SQLite objects created in a thread can only be used in that same
        thread."* That check is load-bearing precisely because it turns a threading mistake into
        an exception instead of undefined behaviour, which is why `ARC-005` keeps it on.

        Quitting from inside the slot also fixes the ordering. `QThread.quit()` called from
        outside can end the loop before queued writes have been delivered; a queued slot that
        quits last runs *after* everything already posted.
        """
        connection, self._connection = self._connection, None
        if connection is not None:
            connection.close()
        thread = QThread.currentThread()
        if thread is not None:
            thread.quit()


class QueueWriter(QObject):
    """Persists jobs off the GUI thread and reports the outcome back on it (`ARC-005`).

    Construct once, at composition time (`T-036`), and `close()` it on the way out.
    """

    #: Internal: carries a submission to the worker across the thread boundary.
    _submit = Signal(int, object)

    #: Internal: asks the worker to close **on its own thread**, after every queued write.
    _shutdown = Signal()

    #: Internal: carries a single-job revision to the worker.
    _revise = Signal(int, object)

    #: Internal: carries a completed job to the worker. It once carried a completion record with
    #: it, so the two landed in one transaction (`T050-R1`); there is no second row now.
    _complete = Signal(int, object)

    #: Internal: carries a manual retry's re-queue to the worker, which allocates its tail
    #: position inside the transaction (`T-080`).
    _requeue = Signal(int, object)

    #: Internal: carries a removal to the worker (`T-080`).
    _remove = Signal(int, object)

    #: Internal: carries a reordering to the worker, which rewrites every position in one
    #: transaction (`T-081`).
    _reorder = Signal(int, object)

    #: Internal: asks the worker to clear every finished job (`T-081`).
    _clear = Signal(int, object)

    #: The writer thread has finished and its connection is closed. **Shutdown is a lifecycle,
    #: not a call** — the same rule `T013-R2` established for the manager, and for the same
    #: reason: `close()` used to `QThread.wait(5000)` on the GUI thread, which a contended write
    #: held for a measured 4.921 s (`T016-R3`). Composition waits for this signal instead.
    closed = Signal()

    def __init__(self, open_connection: ConnectionFactory, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread = QThread()
        self._thread.setObjectName("queue-writer")
        self._worker = _Worker(open_connection)
        self._worker.moveToThread(self._thread)
        self._worker.done.connect(self._on_done)
        self._submit.connect(self._worker.write)
        self._revise.connect(self._worker.revise)
        self._complete.connect(self._worker.complete)
        self._requeue.connect(self._worker.requeue_at_end)
        self._remove.connect(self._worker.remove)
        self._reorder.connect(self._worker.reorder)
        self._clear.connect(self._worker.clear_completed)
        self._shutdown.connect(self._worker.close)
        self._thread.finished.connect(self.closed)
        self._pending: dict[int, Callable[[str | None], None]] = {}
        self._next_token = 0
        self._closed = False
        self._thread.start()

    def submit(self, jobs: Sequence[Job], done: Callable[[str | None], None]) -> None:
        """Persist `jobs` in one transaction. **Returns immediately.**

        `done` is called on the GUI thread with `None` on success or a message on failure. It is
        always called exactly once, including when this writer is already closed — a caller that
        is waiting to close a dialog must not be left waiting because shutdown got there first.
        """
        if self._closed:
            done("the queue writer is shutting down; nothing was saved")
            return
        # `list()` because the sequence crosses a thread boundary: a caller that mutated its own
        # list afterwards would otherwise be editing rows already being written.
        self._submit.emit(self._track(done), list(jobs))

    def revise(self, job: Job, done: Callable[[str | None], None]) -> None:
        """Persist one changed job. **Returns immediately**; `done` fires on the GUI thread.

        The manager's transitions travel this way (`T016-R3`). Ordering with `submit` is
        guaranteed by the single worker thread: a job appended and then revised is written in
        that order, because both are queued to the same receiver.
        """
        if self._closed:
            done("the queue writer is shutting down; nothing was saved")
            return
        token = self._track(done)
        self._revise.emit(token, job)

    def complete(self, job: Job, done: Callable[[str | None], None]) -> None:
        """Persist a completion. **Returns immediately.**

        Refused through the callback after `close()`, like every other submission: a caller waiting
        to hear whether the completion landed must not wait forever because shutdown got there
        first.

        A failure is an ordinary failed transition that `DownloadManager._settle` logs, surfaces,
        and withholds the success announcement for.
        """
        if self._closed:
            done("the queue writer is shutting down; nothing was saved")
            return
        self._complete.emit(self._track(done), job)

    def requeue_at_end(self, job: Job, done: Callable[[str | None], None]) -> None:
        """Persist a manual retry, re-placed at the tail of the queue. **Returns immediately.**

        Refused through the callback after `close()`, like every other submission.
        """
        if self._closed:
            done("the queue writer is shutting down; nothing was saved")
            return
        self._requeue.emit(self._track(done), job)

    def remove(self, job_id: str, done: Callable[[str | None], None]) -> None:
        """Delete one job's row. **Returns immediately**; `done` fires on the GUI thread.

        Refused through the callback after `close()`. A caller waiting to hear whether a removal
        landed must not wait forever because shutdown got there first — and a removal reported as
        failed is one the queue view can leave on screen rather than hiding a row that is still
        there.
        """
        if self._closed:
            done("the queue writer is shutting down; nothing was saved")
            return
        self._remove.emit(self._track(done), job_id)

    def reorder(self, job_ids: Sequence[str], done: Callable[[str | None], None]) -> None:
        """Rearrange the queue into `job_ids`' order. **Returns immediately.**

        `list()` for `submit`'s reason: the sequence crosses a thread boundary, and a caller that
        mutated its own list afterwards would be editing an order already being written.
        """
        if self._closed:
            done("the queue writer is shutting down; nothing was saved")
            return
        self._reorder.emit(self._track(done), list(job_ids))

    def clear_completed(self, done: Callable[[str | None], None]) -> None:
        """Delete every finished job's row. **Returns immediately.**"""
        if self._closed:
            done("the queue writer is shutting down; nothing was saved")
            return
        self._clear.emit(self._track(done), None)

    def _track(self, done: Callable[[str | None], None]) -> int:
        token = self._next_token
        self._next_token += 1
        self._pending[token] = done
        return token

    @Slot(int, str)
    def _on_done(self, token: int, error: str) -> None:
        callback = self._pending.pop(token, None)
        if callback is not None:
            callback(error or None)

    def close(self) -> None:
        """Ask the thread to finish what it has been given, and **return** (`T016-R3`).

        **Nothing here waits.** The first version called `QThread.wait(5000)`, which a contended
        write held on the GUI thread for a measured 4.921 s — the same defect `T013-R2` had
        already ruled on for the manager, reintroduced one layer down. Completion arrives as
        `closed`; composition quits when it does, exactly as it waits for `DownloadManager.idle`.

        Safe to call more than once. Submissions made after this are refused through their own
        callback rather than silently dropped, so nothing is left waiting for an answer.
        """
        if self._closed:
            return
        self._closed = True
        # **Emitted, not called.** A direct call would run the slot on this thread and close a
        # connection belonging to another one; emitting queues it behind every write already
        # submitted, and the slot quits the loop once it has run. See `_Worker.close`.
        self._shutdown.emit()

    @property
    def is_running(self) -> bool:
        return self._thread.isRunning()

    def wait_for_close(self, timeout_ms: int = 5000) -> bool:
        """Block until the writer thread has finished. **Only on the way out of the process.**

        This is the one wait in this class, and it exists because the alternative is worse:
        Qt *aborts the process* when a `QThread` is destroyed while still running, so a quit that
        did not go through the shutdown lifecycle takes the application down with `SIGABRT`
        instead of an exit code. `T-036` measured that as `exit -6` and a `QThread: Destroyed
        while thread 'queue-writer' is still running` on stderr.

        `T013-R2` rejected blocking the GUI thread during teardown, and this does not contradict
        it: that ruling is about a *lifecycle* being implemented as a wait, which is why
        `close()` still returns immediately and reports through `closed`. This runs from
        `aboutToQuit`, when the event loop is ending and there is no interaction left to block —
        and it is bounded, so a wedged writer costs seconds rather than the process.
        """
        return bool(self._thread.wait(timeout_ms))


def open_connection_factory(path: Any) -> ConnectionFactory:
    """A factory that opens (and migrates) the database at `path`, on whichever thread calls it.

    A named function rather than a lambda at the call site, because `ARC-005` turns on *where*
    the connection is created and a lambda buried in composition is easy to hoist into the wrong
    thread by accident.
    """

    def factory() -> sqlite3.Connection:
        from tracks_and_trails.persistence.db import connect

        return connect(path)

    return factory
