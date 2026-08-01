"""The single-instance guard (`T-087`, `A-004`, `ARC-006`).

**Real processes, not threads.** The property under test is that the *kernel* refuses a second
exclusive lock, and threads in one interpreter share a file table — a threaded version of these
tests would pass against a mechanism with no cross-process guarantee at all. `ai/TESTING.md` §7's
rule for the crash tests, applied to the same class of claim.

The two cases that matter are the ones `ARC-006`'s amendment names:

- **Racing starts.** The withdrawn `QLocalServer`-as-lock design passes a sequential test — launch
  A, then launch B, and B's connect succeeds — and fails this one, because Qt documents two local
  servers listening on one Windows pipe name simultaneously.
- **A stale lock left by a killed process**, tested *by killing a process*. The recovery has to work
  against the failure it was chosen for, so no test here deletes a lock file by hand.
"""

import os
import signal
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from tracks_and_trails.core.instance_lock import (
    AlreadyRunningError,
    InstanceLock,
    lock_path_for,
)

#: How long a spawned holder waits before exiting on its own, if nothing kills it first. Long
#: enough that no test races it; every test that needs it gone kills it explicitly.
HOLDER_LIFETIME_SECONDS = 30

#: How long to wait for a spawned process to report through its stdout. Generous, because a cold
#: interpreter start on a loaded machine is not a failure of anything under test.
REPORT_TIMEOUT_SECONDS = 30.0


def _holder_source(database: Path) -> str:
    """A program that takes the lock, says so, and holds it until killed."""
    return textwrap.dedent(f"""
        import sys, time
        from pathlib import Path
        from tracks_and_trails.core.instance_lock import InstanceLock, AlreadyRunningError

        lock = InstanceLock(Path({str(database)!r}))
        try:
            lock.acquire()
        except AlreadyRunningError:
            print("REFUSED", flush=True)
            sys.exit(1)
        print("HELD", flush=True)
        time.sleep({HOLDER_LIFETIME_SECONDS})
    """)


def _spawn(source: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-c", source],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src")},
    )


def _first_line(process: subprocess.Popen[str], timeout: float = REPORT_TIMEOUT_SECONDS) -> str:
    """The child's first stdout line, or a failure naming what it said on stderr instead."""
    deadline = time.monotonic() + timeout
    assert process.stdout is not None
    while time.monotonic() < deadline:
        line = process.stdout.readline()
        if line:
            return line.strip()
        if process.poll() is not None:
            break
    stderr = process.stderr.read() if process.stderr is not None else ""
    raise AssertionError(f"the child never reported; exit={process.poll()} stderr={stderr!r}")


@pytest.fixture
def reap() -> Callable[[subprocess.Popen[str]], None]:
    """Kill and collect a spawned holder, so no test leaks one into the next."""
    spawned: list[subprocess.Popen[str]] = []

    def track(process: subprocess.Popen[str]) -> None:
        spawned.append(process)

    yield track

    for process in spawned:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)


def test_one_process_takes_the_lock_and_a_second_is_refused(
    tmp_path: Path, reap: Callable[[subprocess.Popen[str]], None]
) -> None:
    """The base case, across a real process boundary."""
    database = tmp_path / "queue.db"
    holder = _spawn(_holder_source(database))
    reap(holder)
    assert _first_line(holder) == "HELD"

    with pytest.raises(AlreadyRunningError):
        InstanceLock(database).acquire()


def test_two_launches_racing_do_not_both_win(
    tmp_path: Path, reap: Callable[[subprocess.Popen[str]], None]
) -> None:
    """`P2PLAN-R5`: **the case the withdrawn design passes sequentially and fails.**

    Both processes are started before either is asked what happened, so neither can have observed
    the other's lock at the moment it tried. Under *connect-then-listen* both would fail to connect
    — neither is listening yet — and both would then become servers.

    The assertion is on the pair: exactly one `HELD` and exactly one `REFUSED`. Asserting only that
    *someone* won would pass against a mechanism that lets both win.
    """
    database = tmp_path / "queue.db"
    source = _holder_source(database)

    first = _spawn(source)
    second = _spawn(source)
    reap(first)
    reap(second)

    outcomes = sorted([_first_line(first), _first_line(second)])

    assert outcomes == ["HELD", "REFUSED"], (
        f"outcomes {outcomes}; two simultaneous launches must not both take the database. Both "
        "HELD is the two-writer state ARC-005's single writer cannot protect against, because it "
        "serialises writes within one process only"
    )


def test_a_killed_holder_leaves_a_lock_the_next_launch_can_take(
    tmp_path: Path, reap: Callable[[subprocess.Popen[str]], None]
) -> None:
    """`ARC-006`: the stale path is tested **by killing an instance**, not by deleting a file.

    A `SIGKILL`/`TerminateProcess` gives the holder no chance to release anything, which is the
    failure the kernel-backed lock was chosen for: the file stays, the lock does not.

    The lock file is asserted to still exist afterwards, because that is what distinguishes this
    mechanism from one that depends on cleanup. If a future change starts unlinking it, this test
    keeps passing and the assertion below is what says the reason changed.
    """
    database = tmp_path / "queue.db"
    holder = _spawn(_holder_source(database))
    reap(holder)
    assert _first_line(holder) == "HELD"

    holder.kill()
    holder.wait(timeout=10)

    assert lock_path_for(database).exists(), (
        "the killed holder's lock file is gone, so this test no longer exercises the stale-file "
        "path it was written for"
    )

    lock = InstanceLock(database)
    lock.acquire()
    try:
        assert lock.is_held
    finally:
        lock.release()


@pytest.mark.skipif(sys.platform == "win32", reason="SIGTERM is a POSIX signal")
def test_a_holder_terminated_politely_also_releases(
    tmp_path: Path, reap: Callable[[subprocess.Popen[str]], None]
) -> None:
    """The ordinary end of a process, not just the violent one. Both are the kernel's doing."""
    database = tmp_path / "queue.db"
    holder = _spawn(_holder_source(database))
    reap(holder)
    assert _first_line(holder) == "HELD"

    holder.send_signal(signal.SIGTERM)
    holder.wait(timeout=10)

    with InstanceLock(database) as lock:
        assert lock.is_held


def test_two_databases_do_not_block_each_other(tmp_path: Path) -> None:
    """`A-004` is about the database, not the application (`ARC-006`)."""
    with InstanceLock(tmp_path / "one.db"), InstanceLock(tmp_path / "two.db"):
        pass


def test_two_spellings_of_one_path_are_one_lock(tmp_path: Path) -> None:
    """Without `resolve()`, a relative launch directory would take a second lock on one database.

    The failure this prevents is the whole point of the module, and it is invisible unless the two
    spellings are actually tried.
    """
    database = tmp_path / "queue.db"
    indirect = tmp_path / "sub" / ".." / "queue.db"
    (tmp_path / "sub").mkdir()

    assert lock_path_for(indirect) == lock_path_for(database)
    with InstanceLock(database), pytest.raises(AlreadyRunningError):
        InstanceLock(indirect).acquire()


def test_releasing_lets_the_next_acquirer_in(tmp_path: Path) -> None:
    """Ownership is given up by closing the handle, and giving it up must actually work."""
    database = tmp_path / "queue.db"
    first = InstanceLock(database)
    first.acquire()
    first.release()

    second = InstanceLock(database)
    second.acquire()
    try:
        assert second.is_held
    finally:
        second.release()


def test_release_is_safe_to_repeat_and_safe_without_acquiring(tmp_path: Path) -> None:
    """Teardown paths call it more than once; being asked twice is not an error."""
    lock = InstanceLock(tmp_path / "queue.db")
    lock.release()
    lock.acquire()
    lock.release()
    lock.release()
    assert not lock.is_held


def test_acquiring_twice_in_one_process_is_a_defect_not_a_no_op(tmp_path: Path) -> None:
    """It would mean composition ran twice, which is worth surfacing rather than absorbing."""
    lock = InstanceLock(tmp_path / "queue.db")
    lock.acquire()
    try:
        with pytest.raises(RuntimeError, match="already holds"):
            lock.acquire()
    finally:
        lock.release()
