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

## Why the child's containment is not enough on its own (`T-258`)

Everything above happens **inside the worker**, and a spawned worker runs no code of ours until
`multiprocessing` has fed it its bootstrap payload. Between the process existing and that payload
arriving there is a window in which the child has no watchdog, no group, no job, and no way to
learn that its parent is gone.

That window is not theoretical. Five workers were found alive on `STARBASE` eleven and twelve days
after the run that spawned them, each with the `spawn_main` command line and — the finding —
**one thread**, so none had reached `_exit_when_the_parent_does()`.

The two platforms close it differently, and only one of them closes it for free:

- **POSIX closes it by construction.** The payload arrives over a pipe whose only write end is
  held by the parent, so a parent that dies breaks it and the child raises `EOFError` out of
  `spawn_main`. Measured, not assumed: a child stopped in this window dies within **0.02 s**
  of its parent being `SIGKILL`ed — the resolution of the poll, not a latency — in 8 of 8 runs.
  `test_killing_the_parent_before_the_worker_is_prepared_leaves_nothing` is that measurement, kept.
- **Windows is why `contain_this_application()` exists**, below. Its pipe *should* break the same
  way — the parent holds the sole write handle there too — and five orphans say it did not. **Why
  is not established** (`T258-R6`): `threads=1` bounds the block to before the watchdog, which
  leaves the payload read or `contain_this_process()` itself, and no Windows run has looked. The
  guarantee is therefore taken from the kernel rather than from a diagnosis, so that it holds
  whichever of the two it turns out to be.

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
from typing import Any, Final

__all__ = [
    "GROUPS_ARE_SUPPORTED",
    "ContainmentUnavailableError",
    "contain_this_application",
    "contain_this_process",
    "group_of",
    "kill_group",
    "kill_this_group",
    "start_contained",
    "terminate_group",
]


class ContainmentUnavailableError(RuntimeError):
    """Raised instead of spawning a process the application could not guarantee it can reap.

    **Fail closed, and `T019-R3` is why** (`T258-R1`). The first version of `T-258` logged this
    and carried on, which is the same reasoning `T019-R3` rejected one level down: `T-019`'s
    criterion — no surviving descendant, on any path — has no exception clause, and a spawn that
    proceeds without outer containment is precisely the path the orphans took. The branch is not
    hypothetical; `T-019`'s first Windows Job implementation failed quietly at this same API
    boundary, returning `False` while every test passed.

    A refusal is visible and recoverable. A worker nobody can reap is neither.
    """


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

#: Why the last `contain_this_application()` failed, or `None`.
#:
#: Kept apart from `containment_error` deliberately: they are different failures, reported by
#: different processes, and a single variable would let the worker's reason overwrite the
#: application's in the one process that can still act on either.
application_containment_error: str | None = None


def start_contained(process: Any) -> None:
    """Start a product-owned process, or refuse to start it at all (`T-258`, `T258-R1`/`R3`).

    **The one way this application starts a `multiprocessing.Process`**, and it exists because the
    window `T-258` is about opens *before the child's target is unpickled* — so the child cannot
    know what it was going to be, and a fix attached to any one target cannot cover the class.
    `T258-R3` found the manager's spawn contained while `ytdlp_resolution.resolve_in_a_child` and
    `_freeze_probe.run_probe` were not, and the five observed command lines carry no target
    identity, so nothing in the record says the orphans came through the manager at all.

    Containment first, then `start()`, and **the order is the guarantee**: this raises before the
    process exists rather than after, so a failure cannot leave a child that outlives the refusal.

    `tests/unit/test_spawn_sites.py` fails if any file under `src/` calls `.start()` on something
    it built with `Process(...)`, which is what stops a new spawn site reopening the class.
    """
    if not contain_this_application():
        raise ContainmentUnavailableError(
            "This application could not put its child processes under a handle the operating "
            f"system will reap ({application_containment_error}). A worker started now could "
            "outlive it with nothing able to stop it, so it was not started."
        )
    process.start()


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

    #: The Job object **the application** was assigned to (`T-258`), kept alive for the same
    #: reason as `_windows_job` and separate from it because the two are different jobs in
    #: different processes: this one is the outer, created before any worker exists.
    _windows_application_job: int | None = None

    #: `SIGKILL` does not exist on Windows; nothing in the parent half signals there anyway.
    _HARD_SIGNAL: Final = signal.SIGTERM

    def _assign_self_to_a_killing_job() -> tuple[int | None, str]:
        """Create a `KILL_ON_JOB_CLOSE` job, put this process in it, and return its handle.

        Shared by both containment calls because they want the identical object for opposite
        reasons — the worker to take its descendants with it, the application to take *every*
        descendant with it however it dies. Returns `(None, reason)` on failure; the callers
        differ only in where they record the reason.
        """
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        # **Declare every signature.** Without a `restype`, ctypes assumes `c_int` and truncates
        # the returned 64-bit `HANDLE` to 32 bits — so the job is created, the handle is corrupted
        # on the way back, and every later call against it fails. The caller then returns False,
        # nothing is contained, and the only symptom is descendants surviving a cancellation.
        # That is exactly what CI reported on the first Windows run of this code, and it is
        # invisible on Linux by construction.
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
            return None, f"CreateJobObjectW failed, error {ctypes.get_last_error()}"

        limits = _ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = kill_on_close
        if not kernel32.SetInformationJobObject(
            job, extended_limit_information, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            reason = f"SetInformationJobObject failed, error {ctypes.get_last_error()}"
            kernel32.CloseHandle(job)
            return None, reason

        if not kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()):
            reason = f"AssignProcessToJobObject failed, error {ctypes.get_last_error()}"
            kernel32.CloseHandle(job)
            return None, reason

        return int(job), ""

    def contain_this_process() -> bool:
        """Put this process in a fresh Job object that kills its members when it closes.

        Every descendant inherits job membership unless it is created with
        `CREATE_BREAKAWAY_FROM_JOB`, which yt-dlp and ffmpeg do not use. Nested jobs are
        permitted from Windows 8 onward, so this works even when a CI runner, a debugger, or —
        since `T-258` — **this application's own outer job** has already put us in one.
        """
        global _windows_job, containment_error
        job, reason = _assign_self_to_a_killing_job()
        if job is None:
            containment_error = reason
            return False
        # Held for the life of the process. See `_windows_job`.
        _windows_job = job
        return True

    def contain_this_application() -> bool:
        """Put **the application** in a job, so a worker is reaped even before it runs our code.

        `T-258`, and the reason it is not `contain_this_process()` called from somewhere else:
        the job that matters here has to exist **before the worker does**. A worker contains
        itself at the far end of the bootstrap window, and five orphans on `STARBASE` proved
        that a parent dying inside that window leaves a child with nothing installed in it. This
        job is created once, up front, and every descendant inherits membership at creation —
        so there is no window and no per-spawn call that could race one.

        The worker still contains itself. That job nests inside this one and is not redundant:
        it is what lets *one* worker be cancelled without touching its siblings, which killing
        the outer job cannot express.

        **Idempotent**, because `start_contained()` calls it on every spawn. Every child this
        application starts goes through that door — the manager's worker,
        `ytdlp_resolution.resolve_in_a_child` and `_freeze_probe.run_probe` — so this runs once
        per child, not once per `DownloadManager`, and every call after the first has to return
        the job already held rather than make one. A second job would be a second handle to leak
        rather than a second guarantee, and on Windows the handle is the thing that must not
        leak: `KILL_ON_JOB_CLOSE` fires when the *last* one closes.
        """
        global _windows_application_job, application_containment_error
        if _windows_application_job is not None:
            return True
        job, reason = _assign_self_to_a_killing_job()
        if job is None:
            application_containment_error = reason
            return False
        _windows_application_job = job
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

    def contain_this_application() -> bool:
        """Nothing to do: POSIX closes `T-258`'s window with the bootstrap pipe.

        **Measured rather than assumed**, which is the whole reason this is a documented no-op
        and not an oversight. A worker stopped inside the window — created, never fed — dies
        within 0.02 s of its parent being `SIGKILL`ed — 8 of 8 runs, and that figure is the
        poll's own resolution rather than a measured latency — raising `EOFError` out of
        `spawn_main`, because the only write end of its payload pipe was the parent's.
        `test_killing_the_parent_before_the_worker_is_prepared_leaves_nothing` runs on both
        platforms and is where that answer is kept.

        Deliberately **not** `setsid()` here. The application leading its own group would change
        what "our own group" means to every guard in this module — `group_of`, `_signal_group`
        and `kill_this_group` all turn on the comparison — to close a window that is already
        shut.
        """
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
