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

## Failure is reported, not swallowed

Every submission ends in the caller's callback, on the GUI thread, with either `None` or a
message. There is no path that drops a write silently — the thing `T016-R3` found the previous
design doing with an exception.
"""

import sqlite3
from collections.abc import Callable, Sequence
from typing import Any, Final, Protocol

from PySide6.QtCore import QObject, QThread, Signal, Slot

from tracks_and_trails.core.models import Job
from tracks_and_trails.persistence.repositories import JobRepository

#: How long `close()` waits for the thread to finish its current write and exit.
#:
#: A bounded wait rather than none, and it is deliberately not on the interaction path: this runs
#: at shutdown, after the last submission, where the alternative is a thread outliving the
#: application — the same shape of orphan `T-019` spent a whole task removing.
SHUTDOWN_WAIT_MS: Final = 5000


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
        try:
            if self._connection is None:
                self._connection = self._open_connection()
            JobRepository(self._connection).append(jobs)
        except Exception as error:  # see the docstring: nothing may escape into the event loop
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

    def __init__(self, open_connection: ConnectionFactory, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread = QThread()
        self._thread.setObjectName("queue-writer")
        self._worker = _Worker(open_connection)
        self._worker.moveToThread(self._thread)
        self._worker.done.connect(self._on_done)
        self._submit.connect(self._worker.write)
        self._shutdown.connect(self._worker.close)
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
        token = self._next_token
        self._next_token += 1
        self._pending[token] = done
        # `list()` because the sequence crosses a thread boundary: a caller that mutated its own
        # list afterwards would otherwise be editing rows already being written.
        self._submit.emit(token, list(jobs))

    @Slot(int, str)
    def _on_done(self, token: int, error: str) -> None:
        callback = self._pending.pop(token, None)
        if callback is not None:
            callback(error or None)

    def close(self) -> None:
        """Stop the thread, after letting it finish what it has already been given.

        Safe to call more than once. Submissions made after this are refused through their own
        callback rather than silently dropped.
        """
        if self._closed:
            return
        self._closed = True
        # **Emitted, not called.** A direct call would run the slot on this thread and close a
        # connection belonging to another one; emitting queues it behind every write already
        # submitted, and the slot quits the loop once it has run. See `_Worker.close`.
        self._shutdown.emit()
        if not self._thread.wait(SHUTDOWN_WAIT_MS):
            # Nothing left to try that is safe: terminating a thread mid-`sqlite3` call is how
            # `T019-R5` wedged the interpreter. Report and leave it, which at worst leaks one
            # thread at exit rather than corrupting the database.
            self._thread.requestInterruption()

    @property
    def is_running(self) -> bool:
        return self._thread.isRunning()


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
