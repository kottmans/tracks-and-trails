"""Kill a worker and everything it spawned, as one unit (`T-019`, `REQ-015`, `NFR-003`).

## The defect this exists to fix

`DownloadManager` cancelled by signalling, terminating and killing **the worker process**. yt-dlp
spawns `ffmpeg` as a child *of the worker*, and killing a parent does not touch its children on
either platform. Probed on 2026-07-27 against a real spawned worker with one grandchild: after
`Process.kill()` the grandchild was still running, reparented to `init`. A merge cancelled
mid-flight kept writing to the user's disk with nothing left that could stop it.

## Why containment happens in the child

The parent cannot reliably enumerate a tree it is racing: between listing the descendants and
signalling them, the worker can spawn another one, and the one it listed can exit and have its
pid reused. Both platforms offer the same answer — make the descendants **a set the kernel
tracks**, established once by the child before any of them exist:

| | The child does | The parent then |
|---|---|---|
| POSIX | `os.setsid()`, leading a new group | `killpg(pid, …)` — the group id *is* the pid |
| Windows | joins a Job object, `KILL_ON_JOB_CLOSE` | `TerminateProcess`; the handle does the rest |

The Windows half needs nothing from the parent at all: when the worker dies, its handles close,
the job's last handle goes with them, and the kernel terminates whatever is left in the job. That
asymmetry is the point — each platform's own mechanism, rather than a portable-looking loop that
is wrong on both.

`CREATE_NEW_PROCESS_GROUP` is **not** what this needs and is a common substitute for it: it
affects Ctrl-C delivery, not descendant lifetime.

## A group id, not a pid — and why the difference is the whole interface

This module signals **groups the caller already identified**, and `group_of()` is the only place
a pid becomes one. That split was learned the hard way: the first version looked the group up at
signalling time, which works while the worker is alive and fails silently the moment it is not.
`os.getpgid` needs the process to exist, and `Process.is_alive()` *reaps the zombie as a side
effect of asking* — so by the time a dead session was released there was no pid left to look up,
`getpgid` raised, and the descendants it had left behind were never touched. The tests agreed,
because a grandchild whose parent has died is reparented to `init` and stops being a descendant
of ours at all.

So the manager records the group while the worker is alive and signals that id afterwards. A
process group keeps its id reserved for as long as it still has members, which is precisely the
case where there is anything to reap.

## The rule that keeps this from killing the application

`killpg` takes a group, and the wrong group id here is the parent's own. Two rules, opposite in
shape because their callers mean opposite things:

- **From the parent** (`group_of`, `_signal_group`): a group equal to ours is refused. It means
  the worker never contained itself, and signalling it would `SIGKILL` the application. The
  caller falls back to signalling the single process — fail-safe rather than fail-closed,
  deliberately, because the failure mode of the alternative is killing the GUI.
- **From inside the worker** (`kill_this_group`): our group *is* the set to kill, so the check is
  that we **lead** it. A worker that never contained itself shares the application's group, and
  the same call would do the same damage from the other end.
"""

from __future__ import annotations

import os
import signal
import sys
from typing import Final

__all__ = [
    "GROUPS_ARE_SUPPORTED",
    "contain_this_process",
    "group_of",
    "kill_group",
    "kill_this_group",
    "terminate_group",
]

#: Whether the parent can signal a worker's descendants as a group.
#:
#: POSIX only. On Windows the same guarantee is delivered by the child's Job object rather than
#: by the parent, so there is nothing for the parent to do beyond killing the worker itself.
GROUPS_ARE_SUPPORTED: Final = sys.platform != "win32"

#: Why the last `contain_this_process()` failed, or `None`. A worker that cannot be contained
#: still runs its download — failing the job for this would be a failure the user cannot act on —
#: so the reason has to be recorded somewhere rather than lost. `prepare_this_worker()` logs it
#: once the log handler exists, which is the only moment it can be both known and reportable.
containment_error: str | None = None


def terminate_group(group: int) -> None:
    """Ask a worker's group to stop (`SIGTERM`)."""
    _signal_group(group, signal.SIGTERM)


def kill_group(group: int) -> None:
    """Stop a worker's group, unconditionally (`SIGKILL`)."""
    _signal_group(group, _HARD_SIGNAL)


# --- the two platform halves ----------------------------------------------------------------
#
# Split at module level rather than branched inside each function, so that **each half is
# type-checked by the run that owns it**: `mypy src` checks the POSIX branch and
# `mypy --platform win32 src` checks the Windows one. A `hasattr()` guard reads as portable and
# checks neither, which is how the first version of this module ended up with `os.getpgid` calls
# that could not exist under one platform and `ctypes.WinDLL` calls that could not exist under
# the other.

if sys.platform == "win32":
    #: The Job object this process was assigned to, kept alive deliberately.
    #:
    #: `KILL_ON_JOB_CLOSE` fires when the **last** handle to the job closes. This process holds
    #: the only one, so the handle must outlive everything: letting it be garbage-collected would
    #: kill the very descendants it exists to reap, immediately and at random.
    _windows_job: int | None = None

    #: `SIGKILL` does not exist on Windows; nothing in the parent half signals there anyway.
    _HARD_SIGNAL: Final = signal.SIGTERM

    def contain_this_process() -> bool:
        """Put this process in a fresh Job object that kills its members when it closes.

        Every descendant inherits job membership unless it is created with
        `CREATE_BREAKAWAY_FROM_JOB`, which yt-dlp and ffmpeg do not use. Nested jobs are
        permitted from Windows 8 onward, so this works even when a CI runner or a debugger has
        already put us in one.
        """
        global _windows_job, containment_error
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        # **Declare every signature.** Without a `restype`, ctypes assumes `c_int` and truncates
        # the returned 64-bit `HANDLE` to 32 bits — so the job is created, the handle is corrupted
        # on the way back, and every later call against it fails. `contain_this_process()` then
        # returns False, nothing is contained, and the only symptom is descendants surviving a
        # cancellation. That is exactly what CI reported on the first Windows run of this code,
        # and it is invisible on Linux by construction.
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.SetInformationJobObject.argtypes = (
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        )
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.GetCurrentProcess.argtypes = ()
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

        class _BasicLimits(ctypes.Structure):
            _fields_ = (
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_void_p),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            )

        class _IoCounters(ctypes.Structure):
            _fields_ = tuple(
                (name, ctypes.c_uint64)
                for name in (
                    "ReadOperationCount",
                    "WriteOperationCount",
                    "OtherOperationCount",
                    "ReadTransferCount",
                    "WriteTransferCount",
                    "OtherTransferCount",
                )
            )

        class _ExtendedLimits(ctypes.Structure):
            _fields_ = (
                ("BasicLimitInformation", _BasicLimits),
                ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            )

        #: `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, the one limit this needs, and
        #: `JobObjectExtendedLimitInformation`, the class it belongs to.
        kill_on_close = 0x2000
        extended_limit_information = 9

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            containment_error = f"CreateJobObjectW failed, error {ctypes.get_last_error()}"
            return False

        limits = _ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = kill_on_close
        if not kernel32.SetInformationJobObject(
            job, extended_limit_information, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            containment_error = f"SetInformationJobObject failed, error {ctypes.get_last_error()}"
            kernel32.CloseHandle(job)
            return False

        if not kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()):
            containment_error = f"AssignProcessToJobObject failed, error {ctypes.get_last_error()}"
            kernel32.CloseHandle(job)
            return False

        # Held for the life of the process. See `_windows_job`.
        _windows_job = int(job)
        return True

    def kill_this_group() -> None:
        """Nothing to do: the Job object reaps the tree when this process's handles close."""
        return

    def group_of(pid: int) -> int | None:
        """No groups on Windows; the Job object is the mechanism and needs no id."""
        return None

    def _signal_group(group: int, sig: int) -> None:
        """Nothing to do: the child's Job object reaps the tree when the worker dies.

        Not an oversight and not a stub — it is the Windows design. `TerminateProcess`, which the
        caller issues either way, closes the worker's handles; the job's last handle goes with
        them; the kernel terminates whatever is left in the job.
        """
        return

else:
    #: The signal that cannot be caught, ignored, or slept through.
    _HARD_SIGNAL: Final = signal.SIGKILL

    def contain_this_process() -> bool:
        """Lead a new process group, so every later descendant is addressable as one unit.

        A failure is reported rather than raised — a worker that cannot be contained should still
        run the download, because the alternative is a job that fails for a reason the user
        cannot act on. The parent's fallback still covers the process itself.
        """
        global containment_error
        try:
            os.setsid()
        except OSError as error:
            # Already a group leader, which a spawned child is not — but a test harness or an
            # embedding may have arranged otherwise, and it is not worth failing a session over.
            containment_error = f"setsid() failed: {error}"
            return False
        return True

    def kill_this_group() -> None:
        """Kill **our own** group: the worker taking its descendants with it.

        The mirror image of `_group_of`'s rule, and it has to be a separate function because the
        two callers mean opposite things by "the same group". From the parent, a worker sharing
        our group means containment failed and signalling would kill the application — so it
        refuses. From inside the worker, our group *is* the set we are trying to kill.

        `T-019` found this the direct way: the watchdog called `kill_tree(os.getpid())`, the
        guard saw a group equal to the caller's own, refused, and the grandchild survived the
        application. The worker died, the test that only looked for workers passed, and `ffmpeg`
        kept writing.

        **Leading the group is the precondition**, checked here rather than assumed: an
        uncontained worker shares the application's group, and this would otherwise kill the very
        thing the guard on the other side exists to protect.
        """
        if os.getpgrp() != os.getpid():
            return
        try:
            os.killpg(os.getpgrp(), _HARD_SIGNAL)
        except ProcessLookupError, PermissionError:
            return

    def _signal_group(group: int, sig: int) -> None:
        """Signal a group the caller already identified, unless it is ours.

        The guard is repeated here rather than trusted to `group_of` because the id arrives from
        a caller that stored it earlier, and the whole point of storing it is that the process it
        came from may be gone by now. A check that only ran at lookup time would be a check that
        stopped running exactly when the value got old.
        """
        if group == os.getpgid(0):
            return
        try:
            os.killpg(group, sig)
        except ProcessLookupError, PermissionError:
            # No members left, or not ours to signal. Both mean there is nothing here to stop.
            return

    def group_of(pid: int) -> int | None:
        """`pid`'s process group, but **only if it is not also ours**.

        The one place a pid becomes a group id, and it must be called while `pid` still exists —
        a caller that needs the answer later stores it. `os.getpgid` on a worker that never called
        `setsid()` returns the group *this* process is in, and signalling that would take down the
        GUI, so an id equal to our own is reported as no group at all.
        """
        try:
            group = os.getpgid(pid)
        except ProcessLookupError, PermissionError:
            return None
        return None if group == os.getpgid(0) else group
