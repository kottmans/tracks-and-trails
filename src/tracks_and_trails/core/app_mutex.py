"""A named mutex that tells the Windows installer and uninstaller the application is running.

**Why** (`T322-R3`). Choosing *Also remove my settings and download queue* while the application
was open could leave its database in use, or let it write its settings again after the removal,
while the uninstaller reported success. Inno Setup's `AppMutex` is its documented way to know an
application is running: the application holds a named mutex, and the installer and uninstaller
check for it before they touch anything, asking the user to close the application first.

**Beside the instance lock, not instead of it.** `core/instance_lock.py` decides who owns the
database (`ARC-006`), and nothing outside this process can ask it that without racing it. This
mutex answers a different question for a different program, and holding both costs one handle.

**The handle is not inherited** by `ARC-002`'s workers: `CreateMutexW` without security attributes
makes a non-inheritable handle, so the mutex exists exactly as long as the application process.
It is never closed deliberately; the kernel closes it when the process ends, however it ends.

`packaging/tracks-and-trails.iss` names the same string in `AppMutex=`, and
`tests/unit/test_windows_packaging.py` pins the two together.
"""

import sys
from typing import Final

#: The name both sides use. Session-local: a per-user install only needs this user's session.
APP_MUTEX_NAME: Final = "TracksAndTrails.Running"

#: The handle, held for the life of the process.
_held: int | None = None


def hold_running_mutex() -> bool:
    """Create the mutex on Windows and hold it. `True` when this process now holds a handle to it.

    Idempotent. Elsewhere it does nothing and answers `False`: only the Windows installer looks.
    A failure to create it is not fatal: the application still runs, and the uninstaller's own
    check of each deletion still stops it from claiming a removal that did not happen.
    """
    global _held
    if _held is None:
        _held = _create_mutex()
    return _held is not None


if sys.platform == "win32":  # pragma: no cover - exercised on STARBASE, not on Linux

    def _create_mutex() -> int | None:
        import ctypes
        from ctypes import wintypes

        # A private binding with its prototype in full, for `instance_lock`'s reasons.
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        create_mutex.restype = wintypes.HANDLE
        handle = create_mutex(None, False, APP_MUTEX_NAME)
        return int(handle) if handle else None

else:

    def _create_mutex() -> int | None:
        return None
