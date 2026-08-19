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

from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.downloader import process_tree

REPO_ROOT = Path(__file__).resolve().parents[2]

#: A process that leads a group of its own, and says so once it does.
LEADS_ITS_OWN_GROUP = "import os, time\nos.setsid()\nprint('up', flush=True)\ntime.sleep(30)\n"

#: The group rules are POSIX; the Job object is Windows. Applied per test rather than to the
#: module, because `test_containment_succeeds_on_this_platform` must run on **both** — a
#: module-wide skip is what let a broken Windows Job object reach CI as four confusing
#: integration failures instead of one clear unit failure.
posix_only = pytest.mark.skipif(
    sys.platform == "win32", reason="process groups are the POSIX mechanism; Windows uses a Job"
)


@posix_only
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


@posix_only
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


@posix_only
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


@posix_only
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


def test_containment_succeeds_on_this_platform() -> None:
    """Containment must actually work here, whichever mechanism "here" uses.

    **This is the test the first Windows run needed and did not have.** `contain_this_process()`
    reports failure rather than raising — deliberately, because a worker that cannot be contained
    should still run its download — so a broken Windows Job object was silent, and the only
    symptom was four integration tests reporting that descendants had survived. The cause was
    ctypes returning a 64-bit `HANDLE` through a default `c_int` restype, truncating it.

    Run in a child, because succeeding in-process would put the *test runner* in a new session on
    POSIX, which is exactly the kind of thing this module does.
    """
    probe = (
        "from tracks_and_trails.downloader import process_tree\n"
        "worked = process_tree.contain_this_process()\n"
        "print(worked, process_tree.containment_error)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip().startswith("True"), (
        f"containment failed on {sys.platform}: {result.stdout.strip()}. Nothing spawned by a "
        "worker can be reaped when this fails, and it fails quietly."
    )


def test_application_containment_succeeds_on_this_platform() -> None:
    """`T-258`: the outer half must work here too, and it fails as quietly as the inner one.

    Same shape and same reason as `test_containment_succeeds_on_this_platform`, which exists
    because a broken Windows Job object reported `False` and was noticed only through four
    integration tests failing elsewhere. This half has *no* integration test that would notice:
    its whole job is a window that opens when the application is killed, so nothing routine
    exercises it and a quiet `False` here would be invisible until orphans accumulated.

    Run in a child so that the test runner is not the process being contained.
    """
    probe = (
        "from tracks_and_trails.downloader import process_tree\n"
        "worked = process_tree.contain_this_application()\n"
        "print(worked, process_tree.application_containment_error)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip().startswith("True"), (
        f"application containment failed on {sys.platform}: {result.stdout.strip()}. A worker "
        "killed before it reads its bootstrap payload then has nothing holding it."
    )


def test_containing_the_application_twice_keeps_the_first_job() -> None:
    """Idempotent, because `start_contained()` calls it on every spawn.

    All three spawn sites reach it that way, so it runs once per child rather than once per
    `DownloadManager` — the manager-construction reading this docstring used to give was the
    narrower of the two triggers (`T258-R6`). A second job would be a second handle rather than
    a second guarantee — and on Windows the handle is the thing that must not leak, since
    `KILL_ON_JOB_CLOSE` fires when the *last* one closes. A per-spawn job would leave earlier
    ones open with nothing to close them.

    **This test is only load-bearing on Windows, and says so rather than reading as if it were
    not.** The handle it compares does not exist on POSIX, where containment is a no-op with
    nothing to be idempotent about, so the third value is trivially `True` there and only the
    first two mean anything. Stated because a test that quietly asserts nothing on the platform
    that runs it most is how a guard comes to be trusted for a check it never made.
    """
    probe = (
        "from tracks_and_trails.downloader import process_tree\n"
        "first = process_tree.contain_this_application()\n"
        "held = getattr(process_tree, '_windows_application_job', None)\n"
        "second = process_tree.contain_this_application()\n"
        "print(first, second, held == getattr(process_tree, '_windows_application_job', None))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "True True True", (
        f"containing twice reported {result.stdout.strip()!r}; the second call must keep the "
        "first job rather than create another handle to it"
    )


def test_a_spawn_is_refused_rather_than_left_uncontained() -> None:
    """`T258-R1`: containment that fails must stop the spawn, not warn about it.

    **This is the fail-open branch the first version shipped.** `DownloadManager.__init__` logged
    a warning when `contain_this_application()` returned `False` and constructed a usable manager
    anyway, so a later worker could enter the pre-bootstrap window with nothing holding it — the
    same reasoning `T019-R3` rejected one level down, where a worker that could not contain itself
    was made to refuse the session rather than run it.

    The branch is realistic rather than defensive: `T-019`'s first Windows Job implementation
    returned `False` from this exact API boundary while every test passed, because a truncated
    `HANDLE` made each later call fail.

    **`Process.start()` must not be reached**, which is the assertion — not merely that something
    raised. A refusal that still created the child would be the defect wearing an exception.
    """
    probe = (
        "import multiprocessing\n"
        "from tracks_and_trails.downloader import process_tree\n"
        "process_tree.contain_this_application = lambda: False\n"
        "process_tree.application_containment_error = 'probe: forced failure'\n"
        "started = []\n"
        "class NeverStarts:\n"
        "    def start(self):\n"
        "        started.append(True)\n"
        "raised = ''\n"
        "try:\n"
        "    process_tree.start_contained(NeverStarts())\n"
        "except process_tree.ContainmentUnavailableError as error:\n"
        "    raised = str(error)\n"
        "print(bool(raised), not started, 'probe: forced failure' in raised)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "True True True", (
        f"the refusal did not hold: {result.stdout.strip()!r}. Expected a raise, no `start()`, "
        "and the underlying reason carried into the message a person will read."
    )


def test_the_manager_refuses_the_session_rather_than_spawning_uncontained() -> None:
    """The same guarantee at the level the user meets it (`T258-R1`, `T258-R7`, `T-263`).

    `start_contained` raising is only half the contract: the manager has to turn that into a
    **visible failed start** rather than an unhandled exception or a silently dropped job. It does
    it through `_abort_start`, the path every other spawn failure already takes. So three things
    are asserted, not one — **no start, a durable `FAILED` row, and the reason in the message the
    user is shown** — because a refusal that loses the job or loses the reason is a different
    defect wearing the same green tick.

    **The counter patches the class the manager's context actually constructs, and it did not
    before** (`T258-R7`). The first version assigned to `multiprocessing.context.Process.start`;
    the manager's context is a spawn context, whose `.Process` is `SpawnProcess`. Both inherit
    `start` from `BaseProcess` and **neither subclasses the other**, so the patch landed on a
    class the manager never touches and the counter could not observe the call it existed to
    count. Under the fail-open mutation it stayed empty for that reason rather than because
    nothing spawned — a gate that cannot see the class it is patching passes for the wrong
    reason, which is `ai/TESTING.md`'s instrument rule at a patch boundary. `PATCH REACHES
    MANAGER` below closes that: it asserts the patched attribute *is* the one
    `manager._context.Process` resolves, so this cannot silently come apart again.

    **Two things here exist so that the failure is readable, and both were found by mutating.**
    The counter does not call through to the real `start()` — it did at first, and under the
    fail-open mutation the probe spawned a real worker and died with `SIGABRT`. And the probe is
    **not** run with `check=True`: a manager that carries on past the refusal exits non-zero, and
    `check=True` raised `CalledProcessError` before the assertion below could say what happened.
    A test whose failure mode is a stack trace about `subprocess` reports the wrong defect.
    """
    probe = (
        "import os\n"
        "from PySide6.QtCore import QCoreApplication\n"
        "from tracks_and_trails.core.job_state import JobStatus\n"
        "from tracks_and_trails.downloader import process_tree\n"
        "from tests.integration.test_manager import FakeRepository, make_job\n"
        "import multiprocessing.context as mp_context\n"
        "started = []\n"
        "def counted(self):\n"
        "    started.append(True)\n"
        # `SpawnProcess`, not `Process`: see the docstring. The manager builds its worker from a
        # spawn context, and that is the only class whose `start` it can reach.
        "mp_context.SpawnProcess.start = counted\n"
        "process_tree.contain_this_application = lambda: False\n"
        "process_tree.application_containment_error = 'probe: forced failure'\n"
        "from tracks_and_trails.downloader.manager import DownloadManager\n"
        "app = QCoreApplication([])\n"
        "repository = FakeRepository()\n"
        "repository.add(make_job('job-1', 'https://example.invalid/clip', '.'))\n"
        "manager = DownloadManager(repository)\n"
        "reported = []\n"
        "manager.job_failed.connect(lambda job_id, kind, message: reported.append(message))\n"
        # The instrument checking itself: if the manager's context ever stops resolving to the
        # class patched above, say so here rather than reporting a quiet zero.
        "reaches = manager._context.Process.start is counted\n"
        "print('PATCH REACHES MANAGER' if reaches else 'PATCH MISSED THE CLASS', flush=True)\n"
        "manager.start_queue()\n"
        "try:\n"
        "    manager.start('job-1')\n"
        "except Exception:\n"
        "    pass\n"
        "for _ in range(20):\n"
        "    app.processEvents()\n"
        "started_line = 'NO PROCESS STARTED' if not started else 'STARTED %d' % len(started)\n"
        "print(started_line, flush=True)\n"
        "stored = repository.jobs['job-1'].status\n"
        "print('DURABLY FAILED' if stored is JobStatus.FAILED else 'STORED %s' % stored, "
        "flush=True)\n"
        "carried = any('probe: forced failure' in message for message in reported)\n"
        "print('REASON REACHED THE USER' if carried else 'REASON LOST %r' % reported, flush=True)\n"
        # **Exit before Qt tears itself down, and this is load-bearing under the mutation rather
        # than tidiness.** A manager that fails open reaches `pump.start()`, so a real `QThread`
        # is running at interpreter exit; Qt aborts on that — `SIGABRT`, returncode -6 — and an
        # abort discards whatever the probe had already measured. Every line above is flushed and
        # then this leaves immediately, so the mutated run reports *"STARTED 1"* and fails on the
        # defect, instead of reporting an empty stdout and failing on the first assertion that
        # happens to look at it. `T-263`'s first criterion asks for exactly that: observed, not
        # aborted.
        "os._exit(0)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    context = f"stdout: {result.stdout.strip()!r}\nstderr: {result.stderr.strip()[-600:]!r}"

    assert "PATCH REACHES MANAGER" in result.stdout, (
        "the counter was installed on a class the manager does not use, so a zero count below "
        f"would mean nothing. This is `T258-R7` recurring.\n{context}"
    )
    assert "NO PROCESS STARTED" in result.stdout, (
        f"a worker process was started while the application was uncontained.\n{context}"
    )
    assert "DURABLY FAILED" in result.stdout, (
        "the refused job did not end up recorded as failed. A spawn the manager refuses has to "
        f"leave the row terminal, or the job is lost rather than failed.\n{context}"
    )
    assert "REASON REACHED THE USER" in result.stdout, (
        "the containment reason did not reach `job_failed`'s message. The refusal is only "
        f"actionable if what could not be guaranteed is in the sentence a person reads.\n{context}"
    )


@posix_only
def test_containment_leads_a_new_group() -> None:
    """The POSIX half of the same claim: reporting success and *being* a leader must agree."""
    probe = (
        "import os\n"
        "from tracks_and_trails.downloader import process_tree\n"
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
        f"containment reported {result.stdout.strip()!r}; a worker that says it was contained "
        "and is not leads the parent to signal the wrong group"
    )


def test_a_worker_that_cannot_be_contained_refuses_to_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T019-R3`: the session never reaches yt-dlp when containment fails.

    The first version logged a warning and downloaded anyway, reasoning that a worker which
    cannot be contained should still do the user's work. That reasoning does not survive contact
    with the criterion: `T-019` says no descendant survives *any* path, with no exception clause,
    and `REQ-015` promises cancel terminates the underlying work. Downloading anyway means an
    `ffmpeg` nothing in the application can stop, still writing after the user pressed cancel.

    Driven in-process rather than through a spawned child, deliberately: the thing under test is
    a decision made *before* the process boundary matters, and forcing a real containment failure
    on a healthy machine would mean breaking `setsid` for everyone. `ai/TESTING.md` §6 forbids
    mocking the boundary, and this does not — `run_session` is the far side of the decision, and
    the point is that it is never reached.
    """
    from tracks_and_trails.core.errors import ErrorKind
    from tracks_and_trails.downloader import worker
    from tracks_and_trails.downloader.protocol import Failed, SessionKind, WorkerFinished

    monkeypatch.setattr(process_tree, "contain_this_process", lambda: False)
    monkeypatch.setattr(process_tree, "containment_error", "setsid() failed: forced")
    ran: list[str] = []

    def should_never_run(*args: object, **kwargs: object) -> int:
        ran.append("ran")
        return 0

    monkeypatch.setattr(worker, "run_session", should_never_run)

    sent: list[object] = []

    class Sink:
        def put(self, item: object, /) -> None:
            sent.append(item)

    request = DownloadRequest(
        url="https://example.invalid/clip",
        output_directory=str(tmp_path),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )

    with pytest.raises(SystemExit) as exit_info:
        worker.spawn_session(SessionKind.DOWNLOAD, "job-1", request, Sink())

    assert not ran, (
        "the session ran despite containment failing. Whatever it spawns cannot be stopped, "
        "which is the defect T-019 exists to remove."
    )
    assert exit_info.value.code == worker.UNCONTAINED_EXIT_CODE
    assert [type(item) for item in sent] == [Failed, WorkerFinished], (
        f"the refusal must be a legal session — one outcome, then the sentinel. Sent: {sent}"
    )
    failure = sent[0]
    assert isinstance(failure, Failed)
    assert failure.kind is ErrorKind.WORKER_CRASH
    assert "refused before it started" in failure.message
    assert "setsid() failed: forced" in failure.message, (
        "the reason must reach the user; a refusal nobody can diagnose is its own defect"
    )
