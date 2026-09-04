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
import os
import socket
import subprocess
import sys
import sysconfig
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


class _Vanished:
    """A parent that exists when `psutil.Process` resolves it and is gone by the time it is read.

    The race `T279-R2` names, made deterministic: the scanner holds a `Process` handle, the real
    process exits, and the first attribute read raises `NoSuchProcess`. Nothing here sleeps or
    depends on scheduling.
    """

    def __init__(self, pid: int) -> None:
        self.pid = pid

    def exe(self) -> str:
        raise psutil.NoSuchProcess(self.pid)

    def cmdline(self) -> list[str]:
        raise psutil.NoSuchProcess(self.pid)

    def create_time(self) -> float:
        return 0.0


class _Named:
    """A live parent whose *name* lacks `python` while its executable is one — the `T-279` shape."""

    def __init__(self, exe: str, argv0: str | None = None) -> None:
        self._exe, self._argv0 = exe, argv0 or exe

    def exe(self) -> str:
        return self._exe

    def cmdline(self) -> list[str]:
        return [self._argv0]

    def create_time(self) -> float:
        return 0.0


def _a_pid_that_is_gone() -> int:
    """A pid that resolved a moment ago and does not now."""
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait(timeout=30)
    return dead.pid


def test_a_parent_that_vanishes_while_being_read_is_gone(a_real_orphan: psutil.Process) -> None:
    """`T279-R2`: *not inspectable* and *not there* are opposite answers.

    `T-279` moved the interpreter question from `name()` to `exe()`, and its first version caught
    `NoSuchProcess` in the helpers that ask. That turned **the parent exited while we were reading
    it** — a real orphan, in exactly the race this scanner watches for — into *uninspectable,
    therefore alive*, and the scan silently returned one fewer find.

    Two halves, because the exception can arrive from either place: resolving the pid at all, and
    reading an attribute off a handle that resolved. **Both must answer "gone".**
    """
    assert orphan_scan._parent_is_gone(a_real_orphan, _a_pid_that_is_gone()) is True, (
        "a parent pid that no longer resolves was not reported as gone"
    )

    with pytest.raises(psutil.NoSuchProcess):
        orphan_scan._looks_like_an_interpreter(_Vanished(_a_pid_that_is_gone()))

    # **Each helper, independently.** Asserting only through `_looks_like_an_interpreter` lets one
    # helper swallow `NoSuchProcess` while the other still raises, and the test stays green on a
    # half-made regression: measured, re-adding the catch to `_executable_of` alone leaves all
    # tests passing. That is benign only because `_argv0_of` happens to be asked second, which is
    # an ordering nobody promised.
    for helper in (orphan_scan._executable_of, orphan_scan._argv0_of):
        with pytest.raises(psutil.NoSuchProcess):
            helper(_Vanished(_a_pid_that_is_gone()))


@pytest.mark.parametrize(
    ("exe", "expected"),
    [
        ("/usr/bin/python3.14", True),
        ("/usr/bin/python3.14.exe", True),
        (r"C:\Program Files\Python\python.exe", True),
        ("/home/x/.venv/bin/tracks-and-trails", False),
        (r"C:\app\tracks-and-trails.exe", False),
    ],
)
def test_the_interpreter_question_is_asked_of_the_executable(exe: str, expected: bool) -> None:
    """`T279-R1`: the predicate itself, on both platforms' path shapes.

    **The process-tree regression below is POSIX-only and cannot be made otherwise here.** Windows
    `Popen` goes through `CreateProcess`, which will not run a shebang file, and an installed
    console script there is a native `.exe` launcher that starts a Python child and waits — a
    different tree from the one that test builds. **This exercises the decision rather than the
    tree**, so the Windows job runs it too and the path handling is covered on the platform whose
    separator and extension differ.
    """
    assert orphan_scan._looks_like_an_interpreter(_Named(exe)) is expected


def _console_script(name: str) -> Path:
    """An installed console script by name, with the platform's own suffix and directory."""
    scripts = Path(sysconfig.get_path("scripts"))
    return scripts / (f"{name}.exe" if os.name == "nt" else name)


def _the_process_a_worker_would_call_parent(launcher: psutil.Process) -> psutil.Process:
    """The process a `spawn_main` child of `launcher` would record as its parent.

    **The two platforms differ here and that difference is the whole of `T279-R1`.** A POSIX
    console script is a shebang file, so the interpreter *is* the process that was launched. A
    Windows console script is a **native `.exe` launcher** that starts a Python child and waits —
    the product's code runs in that child, so a worker it spawns records the child, not the
    launcher.
    """
    if os.name != "nt":
        return launcher
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        children = launcher.children()
        if children:
            return children[0]
        time.sleep(0.1)
    raise AssertionError(
        f"the Windows launcher {launcher.pid} started no child within 30s. If console scripts "
        "have stopped being .exe launchers that spawn an interpreter, this test's premise is "
        "gone and T279-R1's reasoning needs re-reading rather than this assertion relaxing"
    )


def test_an_installed_console_script_resolves_to_an_interpreter(tmp_path: Path) -> None:
    """`T279-R1`: the real installed launcher, on whichever platform is running.

    **This runs on Windows**, which the shebang test below cannot. It uses a console script pip
    actually installed — the same machinery that produced the product's own
    `tracks-and-trails` entry point, whose presence is asserted so the shape under test is the
    shape that ships — and asks the scanner's predicate about the process a worker would record
    as its parent.

    `coverage` rather than the product's entry point because that one opens a window; the launcher
    machinery is the same, and it is the machinery under test.
    """
    product = _console_script("tracks-and-trails")
    assert product.exists(), (
        f"{product} is not installed, so this test is not exercising the shape that ships"
    )

    probe = _console_script("coverage")
    if not probe.exists():
        pytest.skip(f"no installed console script to drive at {probe}")

    script = tmp_path / "sleeper.py"
    script.write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
    launcher = subprocess.Popen([str(probe), "run", str(script)])
    try:
        time.sleep(0.8)
        parent = _the_process_a_worker_would_call_parent(psutil.Process(launcher.pid))
        assert orphan_scan._looks_like_an_interpreter(parent), (
            f"the process a worker would record as its parent ({parent.name()!r}, "
            f"exe {parent.exe()!r}) is not recognised as an interpreter, so a live "
            "application's own workers would be reported as orphans"
        )
    finally:
        for child in psutil.Process(launcher.pid).children(recursive=True):
            with contextlib.suppress(psutil.NoSuchProcess):
                child.kill()
        launcher.kill()
        launcher.wait(timeout=30)


def test_the_argv_fallback_answers_when_the_executable_cannot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`T279-R5`: the `argv[0]` fallback is load-bearing, so deleting it must fail something.

    A parent whose executable cannot be read but whose command line can is the case the fallback
    exists for — `AccessDenied` on `exe()` is ordinary on a shared machine. Without the fallback
    the predicate falls through to its bias and calls an unreadable parent an interpreter, which
    happens to be the same answer here for the wrong reason; this pins the *route*.
    """

    class _NoExe(_Named):
        def exe(self) -> str:
            raise psutil.AccessDenied(1)

    assert orphan_scan._looks_like_an_interpreter(_NoExe("/usr/bin/python3.14")) is True
    assert orphan_scan._looks_like_an_interpreter(_NoExe("/opt/app/tracks-and-trails")) is False


def test_an_uninspectable_parent_is_treated_as_alive(monkeypatch: pytest.MonkeyPatch) -> None:
    """`T279-R5`: the bias, pinned. Reversing it must fail rather than pass quietly.

    A parent that answers neither question is **treated as an interpreter**, so the enclosing
    predicate says *not gone*. That is deliberate: an uninspectable parent is a parent that
    exists, and reporting it spends a person's attention on a guess. The opposite choice — report
    it — is defensible and is not what this scanner does, so the choice is asserted.
    """

    class _Silent:
        def exe(self) -> str:
            raise psutil.AccessDenied(1)

        def cmdline(self) -> list[str]:
            raise psutil.AccessDenied(1)

    assert orphan_scan._looks_like_an_interpreter(_Silent()) is True


@pytest.mark.skipif(
    os.name == "nt",
    reason=(
        "POSIX-only by construction (T279-R1). This builds the tree with a shebang file, and "
        "Windows `Popen` goes through `CreateProcess`, which will not run one. An installed "
        "console script there is a native .exe launcher that starts a Python child and waits, so "
        "the real Windows tree differs from anything this can build. The platform-neutral half of "
        "this coverage is test_the_interpreter_question_is_asked_of_the_executable."
    ),
)
def test_a_console_script_parent_is_not_mistaken_for_a_dead_one(tmp_path: Path) -> None:
    """`T-279`: a worker under a live entry-point parent is not an orphan.

    **This is the product's own shape.** `pyproject.toml` installs `tracks-and-trails` as a console
    script, and on Linux `psutil.name()` reads `/proc/<pid>/comm`, which the kernel sets from the
    **executed file** — so the running application is named `tracks-and-trai`, truncated to
    fifteen characters, and `pytest` is `pytest`. The predicate asked `name()`, found no `python`
    in it, and concluded the parent was gone. `MINIMUM_AGE_SECONDS` is 60, so a nightly firing
    while somebody used the application would have reported that person's own live workers.

    A shebang script standing in for the entry point spawns a worker-shaped child and stays alive
    holding it. Same mechanism as the real one, no install step.
    """
    script = tmp_path / "tracks-and-trails-like"
    script.write_text(
        f"#!{sys.executable}\n"
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {_LOOKS_LIKE_A_WORKER!r}])\n"
        "time.sleep(120)\n",
        encoding="utf-8",
    )
    script.chmod(0o755)

    parent = subprocess.Popen([str(script)])
    try:
        time.sleep(0.6)
        named = psutil.Process(parent.pid).name()
        assert "python" not in named.lower(), (
            f"this machine names a shebang script's process {named!r}, which contains 'python' — "
            "the arrangement this test depends on does not hold here, so it would pass without "
            "exercising anything"
        )

        children = psutil.Process(parent.pid).children()
        assert children, "the stand-in parent spawned no worker, so there is nothing to misreport"

        reported = {orphan.pid for orphan in orphan_scan.find_orphans(minimum_age_seconds=0)}
        assert not {child.pid for child in children} & reported, (
            f"a worker under the live parent {named!r} was reported as an orphan. Its parent is "
            "running; only its *name* lacks 'python', which is what an entry point does"
        )
    finally:
        for child in psutil.Process(parent.pid).children():
            child.kill()
        parent.kill()
        parent.wait(timeout=30)


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

#: Every workflow, because `ci.yml` is not the universe (`T268-R6`). `flake-soak.yml` already runs
#: the scanner, so a test that assumed one file would have missed a `STARBASE` scan added anywhere
#: else — while claiming, in three records, that automatic detection on that machine stays absent.
WORKFLOWS = CI_WORKFLOW.parent

#: Triggers that fire without anybody asking. `workflow_dispatch` is deliberately not one: running
#: the scanner by hand is the affordance the retirement kept.
AUTOMATIC_TRIGGERS = ("schedule", "push", "pull_request")

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


def by_platform() -> dict[str, dict[str, object]]:
    """Every scanning job. **One, since 2026-09-03** — see `test_the_windows_scan_stays_removed`."""
    jobs = scanning_jobs()
    assert sorted(jobs) == ["linux-orphans"], (
        f"the jobs invoking {SCRIPT} are {sorted(jobs)}, expected only the Linux one. The Windows "
        "job was removed on 2026-09-03 by the maintainer's ruling; `docs/RUNNER_ORPHANS.md` is "
        "why, and re-adding it is a decision rather than a tidy-up"
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
    host = socket.gethostname()

    assert orphan_scan.main(["--minimum-age-seconds", "0"]) == 1
    _assert_the_verdict_carries_the_host(capsys.readouterr().out, "orphaned worker(s)", host)

    assert orphan_scan.main(["--minimum-age-seconds", str(_FAR_FUTURE_AGE)]) == 0
    _assert_the_verdict_carries_the_host(capsys.readouterr().out, "no orphaned workers found", host)


def _assert_the_verdict_carries_the_host(output: str, verdict: str, host: str) -> None:
    """The host must be on the **verdict's own line**, which is `T272-R7`.

    Asserting it appears *somewhere* in the output is satisfied by printing it on a line of its
    own — and a line of its own is exactly what gets dropped when the verdict is quoted, grepped,
    tailed or pasted into a record. The claim this pins is that the two cannot be separated, so
    the test has to require them joined rather than merely both present.
    """
    lines = [line for line in output.splitlines() if verdict in line]
    assert lines, f"no line carries the verdict {verdict!r}: {output!r}"
    for line in lines:
        assert host in line, (
            f"the verdict and the machine are on different lines: {line!r}. Separated, the "
            "verdict travels without the host and reads as a statement about the platform — "
            f"which is what {verdict!r} did before T272-R5"
        )


#: Shells GitHub runs with `pipefail`, so a pipeline reports the *scanner's* status rather than
#: `tee`'s. `bash` is mapped to `bash --noprofile --norc -eo pipefail {0}`; `sh` is not, and
#: neither is an unset shell on Linux, which GitHub runs as plain `bash -e {0}`.
SHELLS_WITH_PIPEFAIL = frozenset({"bash"})


def effective_shell(step: dict[str, object], job: dict[str, object]) -> str:
    """The shell GitHub will actually use for `step`, by its own precedence.

    **Step, then job defaults, then workflow defaults** — and `T272-R8` is what happens when a
    check reads only the last of those: a `shell:` on the step overrides everything above it, so
    a rule that inspects the workflow default alone can be defeated by a line one level closer to
    the command it is supposed to be protecting.
    """
    if "shell" in step:
        return str(step["shell"])
    for scope in (job, workflow()):
        defaults = scope.get("defaults") or {}
        assert isinstance(defaults, dict)
        run_defaults = defaults.get("run") or {}
        assert isinstance(run_defaults, dict)
        if "shell" in run_defaults:
            return str(run_defaults["shell"])
    return ""


def test_a_pipeline_cannot_swallow_the_alarm() -> None:
    """`T-272`: the find-fails-the-job promise depends on `pipefail`, and nothing asserted it.

    **The scanning step pipes into `tee`**, and a pipeline's status is its last command's. The
    alarm therefore survives only on a shell GitHub runs with `pipefail` — `shell: bash`, which it
    maps to `bash --noprofile --norc -eo pipefail`. **Take that away and a find leaves the job
    green** while `test_a_find_fails_the_job` keeps passing, because it looks for `|| true`,
    `exit 0` and `continue-on-error` and none of those is what would have broken it.

    **Resolved through all three levels, which is `T272-R8`.** The first version of this read the
    workflow default only, so adding `shell: sh` *to the step* defeated `pipefail` with all
    fourteen tests still green. This workflow already carries step-level shells — `ci.yml` records
    `dd9c238` adding two `shell: pwsh` steps — so that override is a thing that happens here
    rather than a hypothetical.
    """
    for job_id, job in by_platform().items():
        step = the_scanning_step(job)
        command = str(step["run"])
        if "|" not in command:
            continue
        shell = effective_shell(step, job)
        assert shell in SHELLS_WITH_PIPEFAIL, (
            f"{job_id} pipes the scanner's output ({command.strip()!r}) under "
            f"{shell or 'the runner default'!r}, which does not set `pipefail`. A pipeline "
            "reports its last command's status, so the scanner's non-zero is discarded and a "
            "find leaves the job green. Either use a shell with `pipefail` or stop piping."
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


def automatic_starbase_scans() -> dict[str, str]:
    """Every job in every workflow that runs the scanner on `STARBASE` from an automatic trigger.

    **Machine and trigger, not filename** (`T268-R6`). What the retirement claims is that nothing
    scans that machine *on its own* any more — not that `ci.yml` in particular does not. A job in a
    second workflow would satisfy the old test and falsify all three records.

    `workflow_dispatch`-only workflows are excluded on purpose: `flake-soak.yml` runs the scanner
    that way, and running it by hand is what `docs/RUNNER_ORPHANS.md` tells a reader to do.
    """
    found: dict[str, str] = {}
    for path in sorted(WORKFLOWS.glob("*.yml")):
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(parsed, dict):
            continue
        # `on` is YAML 1.1's boolean true, which is why this looks for both.
        triggers = parsed.get("on") or parsed.get(True) or {}
        names = set(triggers) if isinstance(triggers, dict) else {str(triggers)}
        if not names & set(AUTOMATIC_TRIGGERS):
            continue
        for job_id, job in (parsed.get("jobs") or {}).items():
            if not isinstance(job, dict) or job.get("runs-on") != STARBASE:
                continue
            steps = job.get("steps") or []
            if any(SCRIPT in str(step.get("run", "")) for step in steps):
                found[f"{path.name}::{job_id}"] = str(sorted(names))
    return found


def test_the_windows_scan_stays_removed() -> None:
    """`STARBASE orphans` was removed on 2026-09-03, and the absence is asserted on purpose.

    **It was not failing because it was wrong.** It found the same seven spawned workers every
    night and failed, which is exactly what `T-258` built it to do — *"prevention that regresses is
    silent; this is what would have said so on day one."* Those seven were being kept deliberately
    as `T-268`'s only specimens, so the board was permanently red for a known reason and a
    genuinely new orphan would have looked identical to it.

    **The maintainer ruled** that one occurrence in a month of watching is rare enough to trade
    against that, and that the condition belongs to a runner rather than to the application. The
    cost was accepted with its name on it: there is now no automatic detection on the machine where
    these accumulate.

    **This test exists so that re-adding it is a decision.** Without it the removal is a hole
    somebody closes on a tidy-up, and the reason it was made would have to be rediscovered — which
    is the shape `T-096` and `T214-R1` both name. `docs/RUNNER_ORPHANS.md` is the writeup.
    """
    automatic = automatic_starbase_scans()

    assert not automatic, (
        f"{sorted(automatic)} runs the scanner on {STARBASE!r} from an automatic trigger again. "
        "That job was removed deliberately on 2026-09-03; read docs/RUNNER_ORPHANS.md before "
        "putting it back, and decide what happens to the seven preserved specimens first — while "
        "they are alive it will be red every run for a reason nobody needs telling twice. "
        "Running the scanner by hand is untouched and is what the writeup points at"
    )


def test_the_linux_scan_watches_the_machine_that_can_hold_one() -> None:
    """`T-272`: the scanner is not Windows-specific and was scheduled as though it were.

    `tools/orphan_scan.py` is `psutil` with no per-platform path, and it found two orphaned
    workers on a Linux box unmodified. Detection that exists and is pointed at one of two
    platforms is the same shape as detection that does not exist, for the platform it does not
    watch.

    **Which box is not established** (`T272-R6`). This docstring said `kirk`; those PIDs are on
    `Spock`, and which machine the 2026-08-20 capture was taken on is not recoverable. Nothing
    this test asserts depends on the answer.
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


def test_no_scan_can_reap_what_it_finds() -> None:
    """`T258-R4`: reporting is the whole contract.

    The `--kill` this tool once had was that round's Critical finding — it cannot prove a match is
    ours. Asked of every scanning job there is, so a job added later inherits the rule.
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
