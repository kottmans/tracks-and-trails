"""`tools/orphan_scan.py` — the detection half of `T-258`.

**The known positive runs first, and it is the point of this file.** `T-238`'s widget probe
reported a clean zero twice while measuring nothing, and `ai/TESTING.md` names that shape
directly: an instrument that reports confidently about nothing is worse than no instrument,
because its silence is read as an answer. This scanner's whole output on a healthy machine is
"none found", so nothing else it says means anything until it has been shown one.

It earned that caution immediately. The first rule here was *the parent pid is 1*, and the
known-positive below reparented to `systemd` at pid 2105 instead — so the scanner reported
"no orphaned workers found" against a live, deliberately-made orphan.
"""

from __future__ import annotations

import contextlib
import importlib.util
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import psutil
import pytest

#: Loaded by path, as `tests/unit/test_commit_message_check.py` loads its own tool: this is
#: developer tooling rather than product code, so it does not belong under `src/`, and `tools/`
#: is not a package.
TOOL = Path(__file__).resolve().parents[2] / "tools" / "orphan_scan.py"


def load() -> ModuleType:
    specification = importlib.util.spec_from_file_location("orphan_scan", TOOL)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


orphan_scan = load()

#: A process that looks exactly like a spawned worker to anything reading command lines.
#:
#: The markers are in a comment rather than a real `multiprocessing` bootstrap because what is
#: under test is the *recognition and parent* rules, and a real spawned child cannot be made to
#: outlive its parent on POSIX — which is `T-258`'s whole finding and is measured in
#: `test_killing_the_parent_before_the_worker_is_prepared_leaves_nothing`.
_LOOKS_LIKE_A_WORKER = "import time\ntime.sleep(120)  # spawn_main --multiprocessing-fork\n"


@pytest.fixture
def a_real_orphan() -> Iterator[psutil.Process]:
    """A live process with a worker's command line whose parent has exited."""
    launcher = (
        "import subprocess, sys\n"
        f"child = subprocess.Popen([sys.executable, '-c', {_LOOKS_LIKE_A_WORKER!r}])\n"
        "print(child.pid, flush=True)\n"
    )
    intermediate = subprocess.Popen(
        [sys.executable, "-c", launcher], stdout=subprocess.PIPE, text=True
    )
    assert intermediate.stdout is not None
    orphan = psutil.Process(int(intermediate.stdout.readline().strip()))
    intermediate.wait(timeout=30)
    if sys.platform != "win32":
        # POSIX reparents on the intermediate's exit rather than on its last write, and the
        # scanner cannot see an orphan until it has. **Windows does not reparent at all** — the
        # parent pid simply stops resolving — so waiting for the ppid to change there would spin
        # for the whole deadline on every test that uses this fixture and then proceed anyway.
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and orphan.ppid() == intermediate.pid:
            time.sleep(0.05)
    try:
        yield orphan
    finally:
        with contextlib.suppress(psutil.NoSuchProcess):
            orphan.kill()


def test_the_scanner_sees_a_known_orphan(a_real_orphan: psutil.Process) -> None:
    """Before "none found" can mean anything, one must be found."""
    found = orphan_scan.find_orphans(minimum_age_seconds=0)

    assert a_real_orphan.pid in {orphan.pid for orphan in found}, (
        f"the scanner did not see a deliberately orphaned worker at pid {a_real_orphan.pid}, "
        f"reparented to pid {a_real_orphan.ppid()}. Everything else this tool reports is a "
        "silence that would read the same way."
    )


def test_a_worker_whose_parent_is_alive_is_not_reported() -> None:
    """The other half: a healthy worker under a live application is not a find.

    Without this the scanner could pass the test above by reporting every `spawn_main` process
    on the machine, which on a CI runner mid-suite is all of them.
    """
    child = subprocess.Popen([sys.executable, "-c", _LOOKS_LIKE_A_WORKER])
    try:
        time.sleep(0.2)
        found = orphan_scan.find_orphans(minimum_age_seconds=0)
        assert child.pid not in {orphan.pid for orphan in found}, (
            "a worker whose parent is this very process was reported as an orphan"
        )
    finally:
        child.kill()
        child.wait(timeout=30)


def test_a_young_orphan_is_not_reported(a_real_orphan: psutil.Process) -> None:
    """The age guard, against the same orphan the first test finds.

    A worker whose parent is still inside `Process.start()` is momentarily parentless-looking,
    and reporting it would make the tool cry wolf on every spawn. Asserted against a process
    that *is* an orphan, so this cannot pass by the scanner simply finding nothing.
    """
    found = orphan_scan.find_orphans(minimum_age_seconds=3600)

    assert a_real_orphan.pid not in {orphan.pid for orphan in found}, (
        "a seconds-old process was reported under a one-hour minimum age"
    )


def test_the_exit_code_reports_a_find(a_real_orphan: psutil.Process) -> None:
    """Non-zero on a find is what lets a scheduled run fail the machine rather than a build."""
    assert orphan_scan.main(["--minimum-age-seconds", "0"]) == 1


def test_the_exit_code_is_clean_when_nothing_is_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half of the exit-code contract, and it must not ask the machine.

    The obvious way to write this is to raise the minimum age until nothing qualifies and assert
    `0`. That asserts **the machine has no old orphans**, which on the one machine this tool is
    for — `STARBASE`, where five sat for twelve days — is exactly the thing that might be false.
    It would then fail as a true positive dressed as a broken test, in a suite where the finding
    would be read as noise.
    """
    monkeypatch.setattr(orphan_scan, "find_orphans", lambda *_, **__: [])

    assert orphan_scan.main([]) == 0


# --- the wiring, which is what `T258-R5` was about -------------------------------------------
#
# **A scanner nothing invokes is a script, not a detection path.** The finding was blocking for
# exactly that reason, and everything above this line was already true while it stood: the tool
# worked, its known positive passed, and no run on the machine it exists for had ever executed it.
# So these read `ci.yml` and assert about the *invocation*.
#
# **Parsed with PyYAML rather than matched as text**, which is `T-264`'s precedent at the same
# surface: that gate accepted an anchor aliased into `on:` and an event hidden behind a quoted `#`,
# both valid YAML that GitHub runs, and the fix was to stop reading workflows as prose. Imported
# plainly — never through `importorskip`, which is how a guard comes to be trusted for a check it
# never made.

import yaml  # noqa: E402 — the wiring half of this file, deliberately below the tool tests

CI_WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"

#: The path the step must invoke, not the bare filename — which also matches this test file.
SCRIPT = "tools/orphan_scan.py"

#: Where the orphans are. A hosted runner is destroyed after every job and has no history to
#: accumulate one, so a scan there would be a green check about a machine that cannot have the
#: condition.
STARBASE = ["self-hosted", "windows", "desktop"]


def workflow() -> dict[str, object]:
    parsed = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def scanning_jobs() -> dict[str, dict[str, object]]:
    """Every job with a step that runs the scanner, keyed by job id."""
    found: dict[str, dict[str, object]] = {}
    jobs = workflow()["jobs"]
    assert isinstance(jobs, dict)
    for job_id, job in jobs.items():
        steps = job.get("steps") or []
        if any(SCRIPT in str(step.get("run", "")) for step in steps):
            found[str(job_id)] = job
    return found


def the_scanning_job() -> dict[str, object]:
    jobs = scanning_jobs()
    assert len(jobs) == 1, (
        f"expected exactly one job to invoke {SCRIPT}, found {sorted(jobs)}. Two scans can "
        "disagree about the same machine, and nobody would know which to believe"
    )
    return next(iter(jobs.values()))


def the_scanning_step(job: dict[str, object]) -> dict[str, object]:
    steps = job["steps"]
    assert isinstance(steps, list)
    running: list[dict[str, object]] = [
        step for step in steps if isinstance(step, dict) and SCRIPT in str(step.get("run", ""))
    ]
    assert len(running) == 1, f"{len(running)} steps in one job run {SCRIPT}"
    return running[0]


def test_something_actually_invokes_the_scanner() -> None:
    """`T258-R5`: the whole finding, as one assertion.

    Deleting the step leaves every other test in this file green, because they all drive
    `find_orphans` and `main` directly. That is precisely the state the review found and this
    is the test that would have reported it.
    """
    assert scanning_jobs(), (
        f"no job in ci.yml runs {SCRIPT}. The scanner is then a script somebody could run, "
        "which is what T-258 criterion 5 already had and what T258-R5 refused"
    )


def test_the_scan_runs_on_the_machine_that_accumulates_orphans() -> None:
    """A hosted runner cannot hold a twelve-day-old orphan; only `STARBASE` can."""
    job = the_scanning_job()

    assert job.get("runs-on") == STARBASE, (
        f"the scan runs on {job.get('runs-on')!r} rather than {STARBASE!r}. A fresh hosted "
        "runner has no history, so a clean result there says nothing about the machine where "
        "five orphans sat for twelve days"
    )


def test_a_find_fails_the_job() -> None:
    """The non-zero exit is the alarm, and swallowing it is the way this silently stops working."""
    job = the_scanning_job()
    step = the_scanning_step(job)

    assert not step.get("continue-on-error"), (
        "the scanning step is continue-on-error, so a find leaves the job green and the report "
        "sits unread — which is the condition T258-R5 named, with an extra step in front of it"
    )
    assert not job.get("continue-on-error"), "the scanning job is continue-on-error"
    command = str(step["run"])
    for swallow in ("|| true", "exit 0", "continue-on-error"):
        assert swallow not in command, (
            f"the scan's command contains {swallow!r}, which discards the exit code the whole "
            "tool is built around"
        )


def test_the_scan_still_runs_when_the_suite_did_not_pass() -> None:
    """A failed or cancelled suite is a *more* likely leaker, not a less likely one."""
    job = the_scanning_job()
    condition = str(job.get("if", ""))

    assert "always()" in condition, (
        f"the scanning job's condition is {condition!r}, which does not contain `always()`. It "
        "`needs` the suite job, so without it a red suite skips the scan — and the run that "
        "crashed mid-spawn is the one most likely to have left something behind"
    )


def test_a_machine_condition_cannot_fail_somebody_s_commit() -> None:
    """The scan answers about the machine, so it must not sit in the path of a push.

    An orphan leaked days ago is not evidence about the commit being pushed now, and failing that
    push would teach everyone to ignore the signal. It also keeps the one `STARBASE` slot free:
    the suite job is what a change is waiting on.
    """
    job = the_scanning_job()
    condition = str(job.get("if", ""))

    assert "schedule" in condition, (
        f"the scanning job's condition is {condition!r}, which does not restrict it to the "
        "nightly. Accumulation is measured in days; a per-push scan buys a day of latency and "
        "pays for it by attributing an old leak to an unrelated commit"
    )
    assert "github.event_name == 'push'" not in condition and " push" not in condition, (
        f"the scanning job's condition is {condition!r}, which reaches push runs"
    )
