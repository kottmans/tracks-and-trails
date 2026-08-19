"""Hold an application inside `T-258`'s pre-bootstrap window, and say what contains the child.

`T-258`'s reproduction and its negative control need the identical situation: an application that
has **created** a worker process and has not yet fed it its bootstrap payload, held there while
the harness kills it. This module is that hold.

**It is a module rather than a string spliced into a `-c` driver because of what `T-266` added.**
The measurement below is `ctypes` against `kernel32`, and only the `windows desktop` job ever runs
it — so the one protection available before that run is `ruff` and `mypy --platform win32`, and
neither reaches inside a string literal.

## What it reports, and the question it answered

`T-258`'s negative control failed on `STARBASE`: with the outer Job suppressed, the child was
reaped anyway. `T-266` named two candidates — **something other than the Job closes the window on
Windows**, or **the suppression stopped suppressing** — and one fact told from inside the driver
separates them:

    driver_holds_a_job — whether a job handle is held in this process at the moment the child
                         is created.

`KILL_ON_JOB_CLOSE` reaps a job's members when its **last handle** closes, and the driver's own
handle is the only one whose closing the harness triggers when it kills the driver. So a driver
holding none cannot be the process whose death closes a job, and a child that dies anyway died of
something else.

**Run `32172384737` answered it**: `driver_holds_a_job` came back `false`, and the child died
regardless, exit code 1. The suppression suppresses; the Job is not the reaper. The control
carries the measurement and is now
`test_a_child_stopped_in_the_window_dies_with_no_outer_job_to_reap_it`, and
`test_killing_the_parent_before_the_worker_is_prepared_leaves_nothing` asserts `true` for the
same field with the fix present — which is what says the reading works rather than the reading
being broken in the direction that happened to suit.

`driver_in_any_job` and `child_in_any_job` are recorded beside it because they are the obvious
objection rather than a decoration. On Windows every process the suite spawns inherits `pytest`'s
own job — the tests that construct a `DownloadManager` put that process in one through
`start_contained()`, and job membership is inherited at creation with no way to leave it. Both
read `true`, as expected. Inherited membership did not do the reaping either: `pytest` was still
holding that job's handle and still running, which is why there is a result to read.

The facts are read from the kernel — `IsProcessInJob` — rather than inferred from our own
bookkeeping, for everything except `driver_holds_a_job`, where our bookkeeping *is* the fact in
question.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, NoReturn


def _announce_and_block(pid: int, facts: dict[str, Any]) -> NoReturn:
    """Report the created child's pid and what contains it, then stay in the window forever.

    **One line, carrying the pid as a field**, and the alternative is why it is worth stating: a
    version of this printed the pid and the facts as two lines, and the harness read two. A driver
    that reaches the window and delivers only the first then leaves the harness blocked in
    `readline()` on a process that will never write again and never exit — a CI timeout rather
    than a failed assertion, on a Windows job that `T-259` has already measured at 88% of its
    limit. Found by mutation-checking this very report. One read cannot half-arrive.

    **This never returns**, and that is the whole mechanism. The patched spawn call *is* the
    window: returning from it would let `multiprocessing` carry on and feed the child the payload
    whose absence the window consists of.
    """
    print(json.dumps({"pid": pid, **facts}), flush=True)
    while True:
        time.sleep(3600)


# --- the two platform halves ----------------------------------------------------------------
#
# Split at module level for the reason `downloader/process_tree.py` gives at the same seam: each
# half is then type-checked by the run that owns it — `mypy` this one, `mypy --platform win32`
# the other — where a `hasattr()` guard reads as portable and checks neither.
#
# **The seam is the process-creation call itself**, wrapped so that it returns a live child to
# nobody: the payload is written only after it returns, so blocking there leaves the child created
# and unfed. `prepare_this_worker()` — and therefore the watchdog — runs at the far end of that,
# so a parent that dies here dies with nothing of ours installed in the child. Each platform has
# its own call, because `multiprocessing` creates the process differently and the window is on the
# opposite side of the serialisation:
#
# - **POSIX** serialises the payload *before* the fork and writes it *after* `spawnv_passfds`
#   returns. The resource tracker is spawned through the same call and is not the subject, hence
#   the `--multiprocessing-fork` filter.
# - **Windows** creates the process first and pickles into the pipe afterwards, inside the
#   `with open(wfd, 'wb')` block, so `_winapi.CreateProcess` is the same seam one call later.

if sys.platform == "win32":

    def _what_contains_them(child_handle: int) -> dict[str, Any]:
        """Ask the kernel what job the driver and the child it just created are in."""
        import ctypes
        from ctypes import wintypes

        from tracks_and_trails.downloader import process_tree

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        # Every signature declared, for the reason `_assign_self_to_a_killing_job` records: an
        # undeclared `restype` is assumed `c_int` and truncates a 64-bit `HANDLE` on the way
        # back, which turns a working call into a silently wrong answer.
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.GetCurrentProcess.argtypes = ()
        kernel32.IsProcessInJob.restype = wintypes.BOOL
        kernel32.IsProcessInJob.argtypes = (
            wintypes.HANDLE,
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.BOOL),
        )

        def in_any_job(process: Any) -> bool | str:
            answer = wintypes.BOOL()
            if not kernel32.IsProcessInJob(process, None, ctypes.byref(answer)):
                return f"IsProcessInJob failed, error {ctypes.get_last_error()}"
            return bool(answer.value)

        return {
            "platform": "win32",
            # The fact that separates `T-266`'s two candidates. Read from the module's own
            # handle rather than from the kernel deliberately: the question is not whether some
            # job contains this process — one always does, see below — but whether *this*
            # process holds a handle whose closing could reap anything.
            "driver_holds_a_job": process_tree._windows_application_job is not None,
            "driver_in_any_job": in_any_job(kernel32.GetCurrentProcess()),
            "child_in_any_job": in_any_job(wintypes.HANDLE(child_handle)),
        }

    def stop_inside_the_window() -> None:
        """Stop the next spawned worker's creation at the instant the process exists.

        Patched at `_winapi.CreateProcess` rather than higher up because the window opens
        *between* process creation and the payload write, and this is the only seam between
        them. Non-worker creations are passed straight through: the driver builds a Qt
        application and may resolve yt-dlp in a child of its own, and stopping on the first of
        those would measure the wrong process.
        """
        import _winapi

        real = _winapi.CreateProcess

        def create(
            application_name: str | None, command_line: str | None, *rest: Any
        ) -> tuple[Any, Any, int, int]:
            result = real(application_name, command_line, *rest)
            if "--multiprocessing-fork" not in (command_line or ""):
                return result
            _announce_and_block(result[2], _what_contains_them(int(result[0])))

        _winapi.CreateProcess = create

else:

    def _what_contains_them() -> dict[str, Any]:
        """Nothing to ask: POSIX has no Job objects, and no analogue of one.

        Reported as `None` rather than `False` because the two mean different things — `False`
        would claim a measurement that says the driver holds no job, and here there is nothing
        that could hold one. `contain_this_application()` is a documented no-op on this platform.
        """
        return {
            "platform": "posix",
            "driver_holds_a_job": None,
            "driver_in_any_job": None,
            "child_in_any_job": None,
        }

    def stop_inside_the_window() -> None:
        """The same stop, at POSIX's own seam between `fork`/`exec` and the payload write."""
        import multiprocessing.util

        real = multiprocessing.util.spawnv_passfds

        # `Any`, and not from laziness: typeshed declares this `(path: bytes, args:
        # Sequence[ConvertibleToInt], ...)`, describing what `_posixsubprocess.fork_exec`
        # eventually wants, while its one caller — `popen_spawn_posix._launch` — passes what
        # `multiprocessing.spawn.get_command_line()` returns, which is a `list[str]` beginning
        # with `sys.executable`. A wrapper has to match the values it is actually handed, so the
        # annotation that would satisfy the stub is the one that would be wrong here.
        def spawn(path: Any, args: Any, passfds: Any) -> int:
            pid = real(path, args, passfds)
            if "--multiprocessing-fork" not in args:
                return pid
            _announce_and_block(pid, _what_contains_them())

        multiprocessing.util.spawnv_passfds = spawn


# --- `T-268`: the other side of the payload read --------------------------------------------
#
# **The window above is not the one the five orphans fell through, and this is where they must
# have been instead.** `T-266` measured that a child stopped *before* its payload read dies when
# its parent does, on both platforms, so a survivor cannot have been blocked there. `threads=1`
# already bounds the five to *before* `_exit_when_the_parent_does()`. What is left between those
# two bounds is the region this half stops in: the payload has been read, the target is running,
# and `prepare_this_worker()` has not been called yet.
#
# **Why the read cannot be where they were, from the source rather than from the run.**
# `popen_spawn_win32.Popen.__init__` creates the payload pipe with `_winapi.CreatePipe(None, 0)`
# — `None` for security attributes, so **neither handle is inheritable** — and creates the child
# with `_winapi.CreateProcess(..., None, None, False, ...)`, whose fifth argument is
# `bInheritHandles=False`. The child obtains the *read* end by duplicating it out of the parent
# in `spawn_main`, and nothing duplicates the *write* end anywhere. So the parent holds the sole
# write handle, no sibling can hold a copy, and its death closes the pipe by construction.
# **That rules out `T-268`'s first candidate in its handle-duplication form** — *"a parent that
# exits while some other process holds a duplicate of the write handle"* — as something this code
# cannot produce, rather than as something a run did not happen to show.


def block_past_the_payload_read(marker: str) -> NoReturn:
    """A worker target that reports the five's signature and then stays in it forever.

    **Deliberately does not call `prepare_this_worker()`**, which is the whole point: a real
    worker installs containment and then the watchdog at the far end of this region, and every
    one of the five had **one thread**, so none of them reached it. Running as a target at all
    proves the payload read completed, because `multiprocessing` does not reach a target until
    it has unpickled one.

    Reports its own thread count beside its pid because that is the observation being matched:
    five processes, one thread each, ~2 s of CPU over twelve days. A stop point that produced a
    second thread would not be a candidate for them however well it survived.

    **Reports through a file rather than through `stdout`, and the reason is the same fact this
    module is about.** `popen_spawn_win32` creates the child with `bInheritHandles=False`, so a
    spawned worker on Windows inherits none of the driver's handles and anything it prints goes
    nowhere. The driver above can print because it is an ordinary `subprocess`; this runs in the
    worker, and a marker file is the one channel both platforms give it.
    """
    Path(marker).write_text(
        json.dumps({"pid": os.getpid(), "threads": threading.active_count()}), encoding="utf-8"
    )
    while True:
        time.sleep(3600)
