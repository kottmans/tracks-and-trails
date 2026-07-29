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
from tracks_and_trails.persistence.repositories import (
    HistoryEntry,
    HistoryRepository,
    JobRepository,
)


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
    def record_history(self, token: int, entry: HistoryEntry) -> None:
        """Store one completed-download record, then report (`T-050`, `REQ-020`).

        Here rather than on the GUI thread for the same reason every other write is: `ARC-005` is
        unqualified, and history is written from `DownloadManager`'s completion callback, which runs
        on the GUI thread. A synchronous insert there would be `T016-R3` again in a new column.

        Ordering with `revise` matters and is free: both are queued to this one receiver, so the
        `COMPLETED` row is written before the history entry that describes it.
        """
        self._perform(token, lambda connection: HistoryRepository(connection).record(entry))

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

    #: Internal: carries a completed-download record to the worker (`T-050`).
    _record_history = Signal(int, object)

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
        self._record_history.connect(self._worker.record_history)
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

    def record_history(self, entry: HistoryEntry, done: Callable[[str | None], None]) -> None:
        """Persist one completed-download record. **Returns immediately** (`T-050`, `ARC-005`).

        Refused through the callback after `close()`, like every other submission: a caller waiting
        to hear whether the record landed must not wait forever because shutdown got there first.

        **A failure here does not undo the download.** The file exists and the job row says
        `COMPLETED`; a missing history entry is a lost record, not a lost download, so the caller
        reports it rather than treating it as the completion failing.
        """
        if self._closed:
            done("the queue writer is shutting down; nothing was saved")
            return
        self._record_history.emit(self._track(done), entry)

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
