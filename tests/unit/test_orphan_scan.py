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
import socket
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


#: An age no live process can reach, so a clean scan is arranged rather than asked of the
#: machine — `test_the_exit_code_is_clean_when_nothing_is_found` explains why that matters.
_FAR_FUTURE_AGE = 10**9


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


#: The Linux side of the same question (`T-272`). Expressed as the *selector* rather than a label
#: list, because `LINUX_RUNNER` is what decides the machine and the job is gated on it being set.
LINUX_RUNNER_SELECTOR = "vars.LINUX_RUNNER"


def the_scanning_job() -> dict[str, object]:
    """The Windows one, by name.

    **This used to assert that exactly one job in the file ran the scanner**, on the reasoning that
    two scans could disagree about the same machine. `T-272` is why it no longer does, and the
    reasoning did not survive contact with it: two scans of *different machines* do not disagree,
    they cover. What the old assertion actually enforced was the gap — the scanner ran on one of
    the two platforms this project supports, and the test that would have caught that was the one
    written to forbid a second job.
    """
    return by_platform()["starbase-orphans"]


def by_platform() -> dict[str, dict[str, object]]:
    """Every scanning job, checked to be exactly the two platforms and no duplicates."""
    jobs = scanning_jobs()
    assert sorted(jobs) == ["linux-orphans", "starbase-orphans"], (
        f"the jobs invoking {SCRIPT} are {sorted(jobs)}, expected one per platform. Two scans of "
        "the same machine would disagree about it and nobody would know which to believe; one "
        "scan of one machine is the T-272 gap"
    )
    return jobs


def the_scanning_step(job: dict[str, object]) -> dict[str, object]:
    steps = job["steps"]
    assert isinstance(steps, list)
    running: list[dict[str, object]] = [
        step for step in steps if isinstance(step, dict) and SCRIPT in str(step.get("run", ""))
    ]
    assert len(running) == 1, f"{len(running)} steps in one job run {SCRIPT}"
    return running[0]


def test_every_verdict_names_the_machine_it_came_from(
    capsys: pytest.CaptureFixture[str], a_real_orphan: psutil.Process
) -> None:
    """`T272-R5`: a scan's subject is one host, so a verdict without a host is not a result.

    **`LINUX_RUNNER` is a label two machines answer**, so the job lands on whichever is free. A
    bare *"no orphaned workers found"* is a true statement about an unnamed box that reads as a
    clean bill of health for the platform — and the run history is what that cost: one find on
    `Spock`, then five greens from `kirk`, which the record read as the specimen having cleared.

    **Both branches, because the green one is the branch that misleads.** A find that does not
    say where is merely unhelpful; a *pass* that does not say where is the one that gets believed.
    """
    assert orphan_scan.main(["--minimum-age-seconds", "0"]) == 1
    found = capsys.readouterr().out
    assert socket.gethostname() in found.splitlines()[0], (
        f"the find does not name the machine it came from: {found.splitlines()[0]!r}"
    )

    assert orphan_scan.main(["--minimum-age-seconds", str(_FAR_FUTURE_AGE)]) == 0
    clean = capsys.readouterr().out
    assert socket.gethostname() in clean, (
        f"a clean scan does not name the machine it came from: {clean!r} — which is the line that "
        "gets read as 'Linux is clean' when it means 'one of two boxes was clean'"
    )


def test_a_pipeline_cannot_swallow_the_alarm() -> None:
    """`T-272`: the find-fails-the-job promise depends on `pipefail`, and nothing asserted it.

    **The scanning step pipes into `tee`**, and a pipeline's status is its last command's. The
    alarm therefore survives only because `ci.yml` sets `defaults.run.shell: bash`, which GitHub
    maps to `bash --noprofile --norc -eo pipefail`. **Remove that one line and a find leaves the
    job green** — while `test_a_find_fails_the_job` keeps passing, because it looks for `|| true`,
    `exit 0` and `continue-on-error` and none of those is what would have broken it.

    That is this file's own docstring — *"the way this silently stops working"* — one level below
    where it was being checked.
    """
    parsed = workflow()
    for job_id, job in by_platform().items():
        command = str(the_scanning_step(job)["run"])
        if "|" not in command:
            continue
        defaults = parsed.get("defaults") or {}
        assert isinstance(defaults, dict)
        run_defaults = defaults.get("run") or {}
        assert isinstance(run_defaults, dict)
        shell = str(run_defaults.get("shell", ""))
        assert shell == "bash", (
            f"{job_id} pipes the scanner's output ({command.strip()!r}) while the workflow's "
            f"default shell is {shell!r}. A pipeline reports its last command's status, so the "
            "scanner's non-zero is discarded and a find leaves the job green. `shell: bash` is "
            "what supplies `pipefail`; either keep it or stop piping."
        )


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


def test_the_scan_runs_on_both_platforms_this_project_supports() -> None:
    """`T-272`: the scanner is not Windows-specific and was scheduled as though it were.

    `tools/orphan_scan.py` is `psutil` with no per-platform path, and it found two orphaned
    workers on `kirk` unmodified. Detection that exists and is pointed at one of two platforms is
    the same shape as detection that does not exist, for the platform it does not watch.
    """
    linux = by_platform()["linux-orphans"]

    assert LINUX_RUNNER_SELECTOR in str(linux.get("runs-on")), (
        f"the Linux scan runs on {linux.get('runs-on')!r}, which does not resolve through "
        f"{LINUX_RUNNER_SELECTOR}. The maintainer's machine is where a Linux orphan can survive "
        "four days; a hosted image is destroyed after every job"
    )
    assert LINUX_RUNNER_SELECTOR in str(linux.get("if", "")), (
        f"the Linux scan's condition is {linux.get('if')!r}, which does not require "
        f"{LINUX_RUNNER_SELECTOR} to be set. Unset, the job falls back to a hosted image and "
        "reports a clean scan of a machine that cannot hold the condition — a green check about "
        "nothing, which is what T-272 was filed for the absence of"
    )


def test_neither_scan_can_reap_what_it_finds() -> None:
    """`T258-R4`, now that there are two of them: reporting is the whole contract.

    The `--kill` this tool once had was that round's Critical finding — it cannot prove a match is
    ours. A second job is a second place for it to come back, so this asks both.
    """
    for job_id, job in by_platform().items():
        command = str(the_scanning_step(job)["run"])
        assert "--kill" not in command, (
            f"{job_id} passes --kill, which enumerates and then signals. T258-R4 made reaping a "
            "person's decision with the report in front of them"
        )


def test_a_find_fails_the_job() -> None:
    """The non-zero exit is the alarm, and swallowing it is the way this silently stops working."""
    for job_id, job in by_platform().items():
        _assert_the_exit_code_survives(job_id, job)


def _assert_the_exit_code_survives(job_id: str, job: dict[str, object]) -> None:
    step = the_scanning_step(job)

    assert not step.get("continue-on-error"), (
        f"{job_id}'s scanning step is continue-on-error, so a find leaves the job green and the "
        "report sits unread — which is the condition T258-R5 named, with a step in front of it"
    )
    assert not job.get("continue-on-error"), f"{job_id} is continue-on-error"
    command = str(step["run"])
    for swallow in ("|| true", "exit 0", "continue-on-error"):
        assert swallow not in command, (
            f"{job_id}'s command contains {swallow!r}, which discards the exit code the whole "
            "tool is built around"
        )


def test_the_scan_still_runs_when_the_suite_did_not_pass() -> None:
    """A failed or cancelled suite is a *more* likely leaker, not a less likely one."""
    for job_id, job in by_platform().items():
        condition = str(job.get("if", ""))

        assert "always()" in condition, (
            f"{job_id}'s condition is {condition!r}, which does not contain `always()`. It "
            "`needs` a suite job, so without it a red suite skips the scan — and the run that "
            "crashed mid-spawn is the one most likely to have left something behind"
        )


def test_a_machine_condition_cannot_fail_somebody_s_commit() -> None:
    """The scan answers about the machine, so it must not sit in the path of a push.

    An orphan leaked days ago is not evidence about the commit being pushed now, and failing that
    push would teach everyone to ignore the signal. It also keeps the one `STARBASE` slot free:
    the suite job is what a change is waiting on.
    """
    for job_id, job in by_platform().items():
        condition = str(job.get("if", ""))

        assert "schedule" in condition, (
            f"{job_id}'s condition is {condition!r}, which does not restrict it to the "
            "nightly. Accumulation is measured in days; a per-push scan buys a day of latency "
            "and pays for it by attributing an old leak to an unrelated commit"
        )
        assert "github.event_name == 'push'" not in condition and " push" not in condition, (
            f"{job_id}'s condition is {condition!r}, which reaches push runs"
        )
