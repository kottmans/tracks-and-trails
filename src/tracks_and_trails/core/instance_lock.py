"""Exclusive ownership of one database, held by exactly one process (`ARC-006`, `A-004`, `T-087`).

`A-004` assumes no concurrent instances against the same database. `ARC-005` puts every write on one
writer thread **within a process**; two processes have two writer threads and no shared lock
discipline, so the assumption is load-bearing for data integrity rather than tidiness.

## Why this is not `QLocalServer`

`ARC-006` originally made the guard *connect to a local server; if that fails, become the server*.
Its amendment of 2026-07-29 withdrew that, on Qt's own documentation: on Windows **two local servers
can listen on the same pipe name simultaneously**. Two launches racing at startup both fail their
initial connect — neither is listening yet — and both then succeed at `listen()`. The result is the
two-writer state the guard exists to prevent, and no amount of connect-first ordering makes creating
a server atomic.

**The defect is invisible to a sequential test.** Launch A, then launch B, and B's connect succeeds,
so the broken mechanism looks correct. Racing starts are the case, which is why one is asserted.

## What replaces it

An atomic, kernel-backed exclusive lock on a file derived from the resolved database path:

- **POSIX** — `fcntl.flock(LOCK_EX | LOCK_NB)`.
- **Windows** — an **exclusive-access open**: `CreateFileW` with `dwShareMode = 0`, so a second
  opener fails with `ERROR_SHARING_VIOLATION`.

*(The Windows half was first written as `msvcrt.locking(LK_NBLCK)`, a one-byte range lock.
`T087-R1`: that may be a defensible primitive, but **`ARC-006`'s amendment names an exclusive-access
open**, and substituting a different mechanism in the one branch nothing can execute here is not
the implementer's call to make silently. It is now the primitive the decision chose.)*

Both are released **by the kernel when the holder dies**, which is the property a PID file cannot
offer and the reason `ARC-006` rejected PID files in the first place. A stale lock file left by a
killed process is therefore not stale in the way that matters: the file remains, the lock does not,
and the next launch takes it. Nothing has to detect or clean up a corpse.

`QLocalServer` remains `ARC-006`'s *attach channel* and is started only by whoever wins here. It is
never the thing that decides who owns the database.

## The lock file is beside the database, and named from it

`A-004` is about the database, not the application: two instances against *different* databases harm
nothing and must not block each other. The lock file is the resolved database path with `.lock`
appended, so the identity is the path itself rather than a hash of it — nothing to collide, nothing
to derive, and a human looking at the directory can see what it belongs to.

**Resolved, so two spellings of one path are one lock.** `Path.resolve()` collapses `..`, symlinks
and a relative launch directory; without it, `./queue.db` and `/home/me/queue.db` would take two
different locks on one database, which is the whole failure this module exists to prevent.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import TracebackType
from typing import Final

#: Appended to the resolved database path. A sibling rather than a file in a temp directory: it
#: belongs to that database, and a lock somewhere else is one a user cannot connect to the thing it
#: guards when they go looking.
LOCK_SUFFIX: Final = ".lock"


def lock_path_for(database: Path) -> Path:
    """The lock file guarding `database`. **Resolved**, so two spellings are one lock.

    `strict=False` because the database may not exist yet on a first run, and the lock is taken
    before anything opens it — the point is to resolve the *path*, not to require the file.
    """
    return database.resolve(strict=False).with_suffix(database.suffix + LOCK_SUFFIX)


class AlreadyRunningError(Exception):
    """Another process holds this database. Raised by `InstanceLock.acquire`.

    An exception rather than a boolean for the reason `IllegalTransitionError` gives: the caller
    that ignores this proceeds to open a database somebody else is writing, and that is the one
    outcome this module exists to make impossible.
    """

    def __init__(self, database: Path) -> None:
        self.database = database
        super().__init__(
            f"another Tracks & Trails instance is already using {database}. "
            "Close it, or start this one against a different database."
        )


class InstanceLock:
    """An exclusive, kernel-backed claim on one database path.

    Use it as a context manager, or call `acquire()` and `release()`. Acquiring twice from the same
    process is an error rather than a no-op: it would mean composition ran twice, which is a defect
    worth surfacing rather than absorbing.

    **The handle is held open for the process's life.** That is not an oversight to tidy up — the
    lock exists only while the descriptor does, and closing it is exactly how ownership is given up.
    """

    def __init__(self, database: Path) -> None:
        self.database = database
        self.path = lock_path_for(database)
        self._handle: int | None = None

    @property
    def is_held(self) -> bool:
        return self._handle is not None

    def acquire(self) -> None:
        """Take the lock, or raise `AlreadyRunningError`. **Never blocks.**

        Non-blocking on both platforms deliberately: a launch that waited would look like a hang,
        and the answer to "somebody else has it" is to say so, not to queue behind them.

        A first run works with no lock file present: both platforms create it if it is absent.
        **Creating it is not the claim** — the exclusive access is — which is why two racing
        launches can both reach the file and only one can hold it.
        """
        if self._handle is not None:
            raise RuntimeError(f"this process already holds the lock on {self.database}")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = _open_exclusive(self.path)
        except OSError as error:
            raise AlreadyRunningError(self.database) from error

        self._handle = handle
        # Written after the lock is won, so the contents can never describe a process that lost the
        # race. Diagnostic only: **nothing reads this to decide ownership**, because a pid in a file
        # is exactly the unreliable signal `ARC-006` rejected. It is here so somebody looking at a
        # stuck machine can find the process without guessing.
        try:
            os.truncate(handle, 0)
            os.write(handle, f"{os.getpid()}\n".encode())
        except OSError:
            # A lock we hold on a file we cannot write is still a lock, and the write is a comment.
            pass

    def release(self) -> None:
        """Give up the lock. Safe to call more than once, and safe to call having never acquired.

        The lock **file is left behind**, deliberately. Removing it races: another launch may have
        opened that same path and be about to lock it, and unlinking underneath them would hand a
        lock on an orphaned inode to a process that thinks it owns the database. The kernel releases
        the lock when the descriptor closes, so an abandoned file is inert — which is the same
        reason a killed process leaves nothing to clean up.
        """
        handle, self._handle = self._handle, None
        if handle is not None:
            os.close(handle)

    def __enter__(self) -> InstanceLock:
        self.acquire()
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()


if sys.platform == "win32":  # pragma: no cover - exercised on STARBASE, not on Linux

    def _open_exclusive(path: Path) -> int:
        """Open `path` for exclusive access, per `ARC-006`'s amendment.

        `CreateFileW` with **`dwShareMode = 0`**: while this handle is open, no other process may
        open the file at all, and a second launch fails with `ERROR_SHARING_VIOLATION`. That is the
        atomic claim the amendment specifies — the kernel decides, and it releases the handle when
        the holder dies, which is the property a PID file cannot offer.

        `OPEN_ALWAYS` creates the file if it is absent and opens it if not, so a first run works
        with no lock file present. Creation is **not** the claim; the share mode is.

        Returned as a C runtime file descriptor so the rest of this module — `os.write`,
        `os.truncate`, `os.close` — is one implementation across both platforms.
        """
        import ctypes
        import msvcrt
        from ctypes import wintypes

        generic_read_write = 0x80000000 | 0x40000000
        no_sharing = 0
        open_always = 4
        file_attribute_normal = 0x80
        invalid_handle = -1

        create_file = ctypes.windll.kernel32.CreateFileW
        create_file.restype = wintypes.HANDLE
        handle = create_file(
            str(path),
            generic_read_write,
            no_sharing,
            None,
            open_always,
            file_attribute_normal,
            None,
        )
        if handle == invalid_handle or handle is None:
            # Raises `OSError` carrying the Windows error code — `ERROR_SHARING_VIOLATION` when
            # another instance holds it, which is what `acquire` converts to `AlreadyRunningError`.
            raise ctypes.WinError(ctypes.get_last_error())
        return msvcrt.open_osfhandle(handle, os.O_RDWR)

else:

    def _open_exclusive(path: Path) -> int:
        """Open `path`, then take `flock(LOCK_EX | LOCK_NB)` on it.

        POSIX has no exclusive-*open* — `O_EXCL` is about creation, not access — so the two steps
        are separate here where Windows fuses them into one. The guarantee is the same: an atomic,
        kernel-held claim released when the process dies.

        `flock` rather than `fcntl.lockf`: POSIX record locks are released when *any* descriptor
        for the file is closed in the process, which makes them unsafe in a program that may open
        the same path elsewhere. `flock` is tied to the open file description, so the lock lives
        exactly as long as this handle.
        """
        import fcntl

        handle = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(handle)
            raise
        return handle
