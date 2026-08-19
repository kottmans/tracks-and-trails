"""`tools/job_duration_report.py` and the workflow wiring that makes it mean something (`T-259`).

**Two halves, and each is useless without the other.** The script can be correct while the step
passes it the wrong bound, and the step can be wired perfectly while the script never warns. So
this file drives the calculation directly *and* reads `ci.yml` to pin the two numbers that must
agree — the `--bound-minutes` the step passes and the `timeout-minutes` the job actually carries.

**Why a bound argument at all, rather than reading `timeout-minutes` at run time?** GitHub does not
publish it to the step, and inferring it would mean parsing the workflow from inside the workflow.
The number is duplicated, so the duplication is what gets tested — which is the same shape as
`T-096`'s placement gate: a fact stated twice, with a test that fails when the copies disagree.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Final

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "tools" / "job_duration_report.py"


def load() -> ModuleType:
    """Load the tool by path, the way `test_commit_message_check.py` loads its own.

    `tools/` is not a package and is not in `mypy`'s `files`, so a plain import is both an
    unresolvable module and a source of `Any`. This is the pattern the project already uses.
    """
    specification = importlib.util.spec_from_file_location("job_duration_report", TOOL)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


reporter = load()
WARNING: Final[str] = reporter.WARNING
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

#: What the step must invoke. The path, not the bare filename — the bare name also matches
#: this test file, which the step's own comment cites.
SCRIPT = "tools/job_duration_report.py"

#: The bound the job carries. Every case below is expressed against it rather than against a
#: literal, so a future raise changes one line here and the cases keep meaning what they say.
BOUND = 40.0
STARTED = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


def lines_of(started_at: str, now: datetime, bound: float, warn_at: float) -> list[str]:
    """`report` called directly, with the module's `Any` pinned to what it actually returns."""
    lines: list[str] = reporter.report(started_at, now, bound, warn_at)
    return lines


def lines_after(minutes: float, *, bound: float = BOUND, warn_at: float = 85.0) -> list[str]:
    """What the reporter prints for a job that has been running `minutes`."""
    lines: list[str] = reporter.report(
        STARTED.isoformat(), STARTED + timedelta(minutes=minutes), bound, warn_at
    )
    return lines


def warning_in(lines: list[str]) -> str | None:
    return next((line for line in lines if WARNING in line), None)


#: The threshold the workflow runs at. **Not a second copy of the policy** — the workflow passes
#: no `--warn-at-percent`, so `main`'s `argparse` default *is* the production value, and
#: `test_the_step_leaves_the_threshold_at_its_default` is what keeps that true. This constant is
#: only what the cases below are derived from, and `test_the_default_threshold_is_the_one_the_job
#: _runs_at` is what compares it to the code (`T-267`).
DECLARED_THRESHOLD = 85.0


def main_lines(minutes: float, capsys: pytest.CaptureFixture[str], *extra: str) -> list[str]:
    """The reporter driven through `main`, which is the entry point the workflow invokes.

    `T259-R2` is why this exists at all: every calculation case in this file passes `warn_at`
    to `report()` itself, so a mutation of `main`'s default from 85 to 90 left all twelve green.
    Those tests prove the arithmetic; only this one goes through the argument the workflow does
    not pass.
    """
    argv = [
        "--started-at",
        STARTED.isoformat(),
        "--bound-minutes",
        f"{BOUND:g}",
        "--now",
        (STARTED + timedelta(minutes=minutes)).isoformat(),
        *extra,
    ]
    exit_code: int = reporter.main(argv)
    assert exit_code == 0, f"the reporter exited {exit_code}; it must never fail the job"
    return capsys.readouterr().out.splitlines()


def test_a_healthy_run_reports_its_margin_and_says_nothing_else() -> None:
    """The 2026-08-17 measurement — 32 minutes against 40 — must print numbers and not warn.

    This is the case the threshold was chosen around. If it warns, the warning is noise from the
    first run and stops being read, which is the failure mode a bound with no headroom already has
    (`T118-R10`).
    """
    lines = lines_after(32)

    assert warning_in(lines) is None, f"the healthy run warned: {warning_in(lines)}"
    assert "Elapsed:   32.0 min" in lines
    assert "Remaining: 8.0 min" in lines
    assert "Used:      80% of the bound" in lines


def test_a_run_near_the_bound_warns_while_it_is_still_green() -> None:
    """34 minutes of 40 is 85%, and the point of the warning is that the run still passed.

    A run this long does not fail. It is the one before the failure, which is the only run where
    the information is still actionable.
    """
    lines = lines_after(34)
    warning = warning_in(lines)

    assert warning is not None, "85% of the bound produced no warning"
    assert "85%" in warning
    assert "Remaining: 6.0 min" in lines


def test_the_threshold_sits_clear_of_the_healthy_run_rather_than_on_it() -> None:
    """The gap between quiet and warning is real minutes, not a rounding accident.

    `T118-R10` is a bound that flaps on how fast the runner feels that morning. A threshold set at
    the measured margin would reproduce that defect inside the fix for it, so this asserts the two
    are separated — and by enough that ordinary run-to-run variance cannot cross it.
    """
    quiet = max(m for m in range(1, 41) if warning_in(lines_after(m)) is None)
    assert quiet == 33, f"the last quiet minute is {quiet}, not 33"
    assert quiet - 32 >= 1, "the healthy 32-minute run has no slack before the warning"


def test_a_run_that_passed_the_bound_reports_a_negative_margin() -> None:
    """`if: always()` means this can run after the timeout killed the suite.

    Reporting `Remaining: -2.0 min` is the honest answer and reads as what happened. Clamping it
    at zero would make a timeout look like a photo finish.
    """
    lines = lines_after(42)

    assert "Remaining: -2.0 min" in lines
    assert warning_in(lines) is not None


def test_an_unreadable_stamp_warns_instead_of_reporting_a_wrong_number() -> None:
    """The stamp comes from a PowerShell step that has failed before, so this path is real.

    The failure mode to avoid is a plausible number derived from a stamp nobody could read. Saying
    *"unknown"* is worth more than saying *"0.0 min"*, and saying nothing at all is worth least —
    a silent reporter looks exactly like one that was never wired up.
    """
    lines = lines_of("not a timestamp", STARTED, BOUND, 85.0)
    warning = warning_in(lines)

    assert warning is not None
    assert "not a timestamp" in warning
    assert not any(line.startswith("Elapsed:") for line in lines)


def test_a_clock_that_moved_backwards_says_so() -> None:
    """A stamp in the future is a clock change, not a job that ran for negative minutes."""
    lines = lines_of((STARTED + timedelta(minutes=5)).isoformat(), STARTED, BOUND, 85.0)
    warning = warning_in(lines)

    assert warning is not None
    assert "future" in warning


def test_the_powershell_round_trip_format_is_what_it_parses() -> None:
    """`[datetime]::UtcNow.ToString('o')` writes seven fractional digits and a `Z`.

    This is the exact string the *Stamp the job start time* step produces. Parsing it is the whole
    contract between the two steps, and it is the half a local test can hold.
    """
    lines = lines_of("2026-08-17T12:00:00.1234567Z", STARTED + timedelta(minutes=10), BOUND, 85.0)

    assert warning_in(lines) is None
    assert "Elapsed:   10.0 min" in lines


def test_it_never_exits_non_zero(tmp_path: Path) -> None:
    """A reporter that fails the gate turns *slow* into *broken*.

    Both the ordinary path and the unreadable-stamp path have to exit 0: `T-259` asks for the creep
    to be visible on a green run, and a step that reddens the board on a slow-but-passing suite
    would make the next raise a fix for the reporter rather than for the bound.
    """
    for stamp in (STARTED.isoformat(), "rubbish"):
        code: int = reporter.main(
            [
                "--started-at",
                stamp,
                "--bound-minutes",
                str(BOUND),
                "--now",
                (STARTED + timedelta(minutes=39)).isoformat(),
                "--report",
                str(tmp_path / "job-duration.txt"),
            ]
        )
        assert code == 0, f"exited {code} for {stamp!r}"

    assert (tmp_path / "job-duration.txt").read_text(encoding="utf-8").strip()


def test_the_report_file_carries_what_the_log_carried(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The evidence artifact and the log must not be able to disagree.

    `reports/` is uploaded and kept for 30 days; the log scrolls. If the two are written from
    different values, the retained copy is the one that gets cited later and the wrong one.
    """
    destination = tmp_path / "nested" / "job-duration.txt"
    reporter.main(
        [
            "--started-at",
            STARTED.isoformat(),
            "--bound-minutes",
            str(BOUND),
            "--now",
            (STARTED + timedelta(minutes=36)).isoformat(),
            "--report",
            str(destination),
        ]
    )

    printed = capsys.readouterr().out.strip()
    assert destination.read_text(encoding="utf-8").strip() == printed
    assert WARNING in printed


# --- the wiring, which the calculation cannot check for itself -------------------------------
#
# **Read as text, matching `test_commit_message_check.py`.** These three assert about the *wiring* —
# that a step exists, carries `if: always()`, and is passed the same number the job declares — and
# the text is what a person edits when they break it.
#
# *(This comment said PyYAML was not a declared dependency. It is one as of `T264-R2`, which needed
# a real parser to close an alias bypass in a security gate. That does not make these three wrong,
# but it removes the reason they gave: the argument is now suitability, not availability. If a
# future edit wants the parsed value here, PyYAML is available and must be imported plainly —
# never through `importorskip`, which is how a guard comes to be trusted for a check it never
# made, per `tests/ui/test_windows_accessibility.py`.)*


def windows_desktop_job() -> list[str]:
    """The lines of the `windows desktop` job, from its `name:` to the next job at column 2.

    **Comment-only lines are dropped**, and finding that out cost a round: this job's steps are
    documented as heavily as the rest of the repository, and the comment introducing the duration
    step names the very test file reading it. Matching on raw text counted the prose as wiring and
    reported two reporters where there is one. A test that reads a workflow has to read what the
    workflow *does*, not what it says about itself.
    """
    lines = CI_WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "name: windows desktop")
    end = next(
        (i for i in range(start + 1, len(lines)) if re.fullmatch(r"  [a-z][a-z0-9-]*:", lines[i])),
        len(lines),
    )
    return [line for line in lines[start:end] if not line.strip().startswith("#")]


def step_containing(job: list[str], needle: str) -> list[str]:
    """The one step whose body mentions `needle`, from its `- ` marker to the next step's."""
    marker = re.compile(r"^      - (name|uses):")
    starts = [i for i, line in enumerate(job) if marker.match(line)]
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(job)
        if any(needle in line for line in job[start:end]):
            return job[start:end]
    raise AssertionError(f"no step in `windows desktop` mentions {needle!r}")


def test_the_step_exists_and_runs_even_when_the_suite_failed() -> None:
    """Without `if: always()` the step is absent from exactly the runs worth measuring."""
    job = windows_desktop_job()
    step = step_containing(job, SCRIPT)

    assert sum(SCRIPT in line for line in job) == 1, (
        "more than one step reports the duration; two reports can disagree"
    )
    assert any(line.strip() == "if: always()" for line in step), (
        "the duration report is conditional on success, so a slow job that failed — the case "
        "T-259 exists for — would not report its duration"
    )


def test_the_bound_it_is_told_is_the_bound_the_job_carries() -> None:
    """The number is stated twice, so this is the test that stops the copies drifting.

    A step passing `--bound-minutes 30` to a job with `timeout-minutes: 40` would report a margin
    nobody has and warn ten minutes early, and the warning text would still read as authoritative.
    """
    job = windows_desktop_job()
    step = step_containing(job, SCRIPT)

    declared = re.search(r"^    timeout-minutes: (\d+)$", "\n".join(job), re.MULTILINE)
    passed = re.search(r"--bound-minutes\s+(\d+(?:\.\d+)?)", "\n".join(step))

    assert declared is not None, "the job declares no timeout-minutes"
    assert passed is not None, "the step does not pass --bound-minutes"
    assert float(passed.group(1)) == float(declared.group(1)), (
        f"the step reports against {passed.group(1)} minutes while the job is bounded at "
        f"{declared.group(1)}"
    )
    assert float(declared.group(1)) == BOUND, (
        f"the job's bound moved to {declared.group(1)}; the cases in this file are written "
        f"against {BOUND:g} and need re-deriving, which is T-259's fourth acceptance criterion"
    )


def test_the_stamp_the_step_reads_is_the_one_the_job_writes() -> None:
    """`JOB_STARTED_AT` is set into `GITHUB_ENV` by the first step; this reads it back.

    Nothing else in the job establishes that name, so a rename in either place leaves the reporter
    measuring from an empty string — which it reports as unreadable rather than wrong, but the run
    still carries no duration.
    """
    job = windows_desktop_job()
    written = next(i for i, line in enumerate(job) if "JOB_STARTED_AT=" in line)
    read = next(
        i for i, line in enumerate(job) if "$JOB_STARTED_AT" in line and "--started-at" in line
    )

    assert written < read, "the duration report runs before the stamp is written"


def test_the_default_threshold_is_exactly_the_declared_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`T267-R1`: the **exact** value `main` hands `report()` when the workflow passes nothing.

    **Two behaviour points bracket an interval, and an interval is not a value.** The first
    version of this test used 85.0% (must warn) and 84.75% (must not), which together prove only
    that the default lies in `(84.75, 85]`. The reviewer changed the default to **84.9** and all
    fourteen tests passed — a policy drift nobody recorded, sitting green. Tightening the lower
    case would only narrow the interval; it would never close it, because a `>=` comparison can
    always hide a difference smaller than the case below it.

    So this stops sampling behaviour and reads the argument. `report` is replaced with a spy, and
    what `main` passes as `warn_at_percent` is compared to the declared policy value exactly.
    `test_the_default_threshold_still_warns_end_to_end` keeps a real warning path, so this cannot
    pass by pinning a number `report` has stopped honouring.
    """
    passed: list[float] = []
    # Bound before the patch, or the spy calls itself: `main` looks `report` up on the module, and
    # so would `reporter.report` from inside here.
    original = reporter.report

    def spy(started_at: str, now: datetime, bound: float, warn_at: float) -> list[str]:
        passed.append(warn_at)
        lines: list[str] = original(started_at, now, bound, warn_at)
        return lines

    monkeypatch.setattr(reporter, "report", spy)
    exit_code: int = reporter.main(
        [
            "--started-at",
            STARTED.isoformat(),
            "--bound-minutes",
            f"{BOUND:g}",
            "--now",
            (STARTED + timedelta(minutes=1)).isoformat(),
        ]
    )

    assert exit_code == 0
    assert passed == [DECLARED_THRESHOLD], (
        f"`main` passed {passed} to `report` where the declared policy is "
        f"{DECLARED_THRESHOLD:g}. The workflow supplies no --warn-at-percent, so this argument is "
        "the production threshold: T-259 decided 85%, and a different number here is an "
        "unrecorded change to that decision."
    )


def test_the_default_threshold_still_warns_end_to_end(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The behaviour half, kept so the exact-value check above cannot pass over a dead argument.

    A spy proves what `main` *passes*. If `report` ever stopped acting on it — a refactor that
    reads the threshold from somewhere else, or ignores the parameter — the assertion above would
    still hold while the warning stopped working. This drives the real path with no threshold
    argument at all:

    - **34.0 of 40 minutes is 85.0%**, and the comparison is `>=`, so it must warn.
    - **33.9 minutes is 84.75%** and must not, which also keeps the boundary's direction pinned.
    """
    at_the_mark = main_lines(DECLARED_THRESHOLD / 100 * BOUND, capsys)
    just_below = main_lines(33.9, capsys)

    assert warning_in(at_the_mark) is not None, (
        f"a job at exactly {DECLARED_THRESHOLD:g}% of its bound did not warn. `main` passes the "
        "declared threshold — the test above checks that — so `report` has stopped acting on it."
    )
    assert warning_in(just_below) is None, (
        "a job at 84.75% warned, so the warning fires under the mark and spends the signal it "
        "exists to preserve."
    )


def test_the_step_leaves_the_threshold_at_its_default() -> None:
    """The other half: the default is only production configuration while nothing overrides it.

    If the step ever starts passing `--warn-at-percent`, the test above stops describing what CI
    does — it would be pinning a default the workflow no longer uses, which is the same shape of
    silent drift `T-267` was filed to close. This allows the override to exist, and requires it to
    agree.
    """
    step = step_containing(windows_desktop_job(), SCRIPT)
    override = re.search(r"--warn-at-percent\s+(\d+(?:\.\d+)?)", "\n".join(step))

    if override is None:
        return
    assert float(override.group(1)) == DECLARED_THRESHOLD, (
        f"the step now passes --warn-at-percent {override.group(1)}, so the job does not run at "
        f"{DECLARED_THRESHOLD:g}% and the cases above pin a value nothing uses. Change both "
        "together, and record the new threshold's measurement as T-259's entry requires."
    )
