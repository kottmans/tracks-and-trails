"""`T-019`: the two rules that decide whether a signal is safe to send.

These are unit tests because the property they check is one that **cannot be reached when
everything works**. The parent's guard only fires when a worker failed to contain itself, and
`kill_this_group`'s only when a worker was never the leader of its group — so an integration test
against healthy workers exercises neither, and a mutation removing either one survives the whole
process-tree suite while leaving the application one bad call away from killing itself.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tracks_and_trails.downloader import process_tree

REPO_ROOT = Path(__file__).resolve().parents[2]

#: A process that leads a group of its own, and says so once it does.
LEADS_ITS_OWN_GROUP = "import os, time\nos.setsid()\nprint('up', flush=True)\ntime.sleep(30)\n"

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="process groups are the POSIX mechanism; Windows uses a Job"
)


def test_our_own_group_is_never_reported_as_signallable() -> None:
    """The rule the GUI's life depends on.

    `os.getpgid` on a worker that never called `setsid()` returns the group *this* process is in.
    Signalling that would `SIGKILL` the application, the manager, and everything else in it — so
    a group equal to our own is reported as no group at all, and the caller falls back to the
    single process.
    """
    assert process_tree.group_of(os.getpid()) is None, (
        "this process's own group was reported as signallable; killing it would take the "
        "application with the worker"
    )


def test_a_process_that_leads_its_own_group_is_reported() -> None:
    """The other half: containment worked, so the group is the worker's and is safe to signal."""
    child = subprocess.Popen(
        [sys.executable, "-c", LEADS_ITS_OWN_GROUP],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None
        child.stdout.readline()

        group = process_tree.group_of(child.pid)

        assert group == child.pid, (
            f"a process that called setsid() reported group {group}, not its own pid. The group "
            "id is what the manager signals; a wrong one signals the wrong tree."
        )
    finally:
        child.kill()
        child.wait(timeout=30)


def test_a_process_that_does_not_lead_its_group_refuses_to_kill_it() -> None:
    """`kill_this_group()` checks that it leads the group before killing it.

    The mirror of the rule above, for the caller that means *its own* group. Without the check, a
    worker whose containment failed would kill the application's group from inside the watchdog —
    the opposite of the guard's intent, reached by the same mistake.

    **Two processes deep, deliberately.** The first version called the function on the test
    process and skipped when pytest happened to lead its own group — which it does here, so the
    test proved nothing where it mattered most. Instead: a child calls `setsid()` to lead a group
    of its own, and *its* child — a member but not the leader, which is the state under test —
    makes the call. If the guard is missing, the grandchild kills that group and takes its parent
    with it, so no output comes back and this fails. Either way the group destroyed is never ours.
    """
    inner = (
        "import os\n"
        "from tracks_and_trails.downloader import process_tree\n"
        "assert os.getpgrp() != os.getpid(), 'the probe must not lead its group'\n"
        "process_tree.kill_this_group()\n"
        "print('survived', flush=True)\n"
    )
    outer = (
        "import os, subprocess, sys\n"
        "os.setsid()\n"
        f"probe = {inner!r}\n"
        "result = subprocess.run(\n"
        "    [sys.executable, '-c', probe], capture_output=True, text=True\n"
        ")\n"
        "print(result.stdout.strip(), flush=True)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", outer],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.stdout.strip() == "survived", (
        "a process that does not lead its group killed it anyway. In a worker whose containment "
        f"failed, that group is the application's. stdout={result.stdout!r} "
        f"stderr={result.stderr[-400:]!r}"
    )


def test_killing_a_group_refuses_the_callers_own() -> None:
    """The second place the rule is enforced, and the one that still matters later.

    `group_of` refuses our own group at *lookup* time — but the manager stores the id and signals
    it minutes later, when the process it came from is gone. A check that only ran at lookup
    would be a check that stopped running exactly when the value got old, so `_signal_group`
    repeats it. Nothing else exercises that repetition: with `group_of` working, the id handed
    over is never ours.

    Run in a child that leads its own session, so the group destroyed if the guard is missing is
    that child's and never this test runner's.
    """
    probe = (
        "import os\n"
        "os.setsid()\n"
        "from tracks_and_trails.downloader import process_tree\n"
        "process_tree.kill_group(os.getpgrp())\n"
        "print('survived', flush=True)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.stdout.strip() == "survived", (
        "kill_group signalled the caller's own group. The manager hands this function an id it "
        f"stored earlier; when that id is ours, signalling it kills the application. "
        f"stderr={result.stderr[-300:]!r}"
    )


def test_containment_reports_whether_it_worked() -> None:
    """A worker reports rather than raises, and the caller can tell (`contain_this_process`).

    Run in a child, because succeeding here would put the *test process* in a new session and
    detach it from pytest's own group — which is exactly the kind of thing this module does.
    """
    probe = (
        "from tracks_and_trails.downloader import process_tree\n"
        "import os\n"
        "worked = process_tree.contain_this_process()\n"
        "print(worked, os.getpgrp() == os.getpid())\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "True True", (
        f"containment reported {result.stdout.strip()!r}; the two halves must agree — a worker "
        "that says it was contained and is not leads the parent to signal the wrong group"
    )
