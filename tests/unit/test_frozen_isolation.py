"""The frozen build gate must read its own profile, not the runner account's (`T-298`).

**This is a workflow test, and it exists because the defect was invisible to every other kind.**
`frozen linux` passed on `kirk` and failed on `Spock` at the same code head — run `33231536419` —
because Spock holds the maintainer's real in-app yt-dlp update under their user data directory. The
artifact resolved it ahead of its bundled baseline, which is `OPS-002` working exactly as specified,
and the bundled-baseline probe then failed. Nothing in `src/` was wrong and no test of `src/` could
have found it: the input was the profile the job happened to inherit.

**Why the environment is the whole mechanism here.** The frozen artifact is a *spawned process*, so
`tests/user_directories.py`'s module patching cannot reach it — that half lives in one interpreter.
Only the environment half crosses the process boundary, which is `T-230`'s finding, and it is what
this asserts.

**The names are written out rather than read from `user_directories._CHILD_ENVIRONMENT`, and that
is deliberate.** `test_user_directories.py` records what happened when its own version of this
iterated that dict: deleting the two Windows entries deleted the assertions about them and the
mutant passed. A guard proved against the thing it guards is not a guard. `T-131` is the round
where setting one family passed on Linux and failed on the runner, so both are named here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import pytest
import yaml

CI_WORKFLOW: Final = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"

#: Every variable `platformdirs` consults to place a per-user directory, on either platform.
#: `XDG_*` is read only on POSIX and `WIN_PD_OVERRIDE_*` only on Windows, so a job that sets one
#: family isolates one matrix leg and leaves the other in the real profile.
REQUIRED_VARIABLES: Final = (
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "WIN_PD_OVERRIDE_APPDATA",
    "WIN_PD_OVERRIDE_LOCAL_APPDATA",
)

#: The probes that run the built artifact. Each is a real application launch, so each resolves a
#: user data directory and would find a real user-managed yt-dlp if the job had not moved it.
ARTIFACT_PROBES: Final = ("--ytdlp-probe", "--database-probe")


def frozen_job() -> dict[str, Any]:
    parsed = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict), "ci.yml did not parse as a mapping"
    job = parsed["jobs"]["frozen"]
    assert isinstance(job, dict)
    return job


def profile_step() -> str:
    """The step that exports the profile, by what it does rather than by its name.

    **Exported through `$GITHUB_ENV` rather than declared in a job-level `env:`.** The first
    version of this workflow used `jobs.frozen.env` with `${{ runner.temp }}`, and GitHub rejected
    the entire file at validation: zero jobs, no logs, the run named after its path. The `runner`
    context does not exist at job level, because the runner is not assigned when that block is
    evaluated — and `yaml.safe_load` parses it happily, which is why this test asserts the shape
    that actually ran rather than the one that merely parsed.
    """
    steps = frozen_job()["steps"]
    exporting = [step for step in steps if "GITHUB_ENV" in str(step.get("run", ""))]
    assert exporting, "no step in the frozen job exports anything to GITHUB_ENV"
    return "\n".join(str(step["run"]) for step in exporting)


@pytest.mark.parametrize("variable", REQUIRED_VARIABLES)
def test_the_frozen_job_redirects_every_per_user_directory(variable: str) -> None:
    """Both families, exported once, so both matrix legs are covered by one declaration."""
    exported = profile_step()

    assert f"{variable}=" in exported, (
        f"the frozen job does not export {variable}, so the artifact resolves the runner "
        f"account's own directory on the platform that reads it — which is how run "
        f"33231536419 measured the maintainer's yt-dlp instead of the one it built"
    )


def test_the_profile_is_unique_to_the_run() -> None:
    """A stable path is not isolation on a machine that keeps its temp directory.

    `RUNNER_TEMP` persists between jobs on a self-hosted runner, so a re-run would start from the
    previous attempt's installed copy — and the update probe would then be measuring a state it did
    not create. `run_id` and `run_attempt` are what make the profile fresh.
    """
    exported = profile_step()

    assert "RUNNER_TEMP" in exported, (
        "the profile is not under the runner's temporary directory, so it is either in the "
        "checkout or somewhere the cleanup step does not own"
    )
    for marker in ("github.run_id", "github.run_attempt"):
        assert marker in exported, (
            f"the profile does not vary with {marker}, so a second attempt inherits the first "
            f"one's installed copy and the update probe measures a state it did not create"
        )


def test_no_runner_context_is_used_where_github_will_not_evaluate_it() -> None:
    """`${{ runner.* }}` at job level is a workflow that does not parse, and this is that record.

    Asserted because the failure mode gives no useful signal: the run has no jobs, no logs and is
    named after the file path, and every local YAML check passes.
    """
    job = frozen_job()
    declared = str(job.get("env") or {})

    assert "runner." not in declared, (
        "the frozen job's job-level env uses the runner context, which GitHub does not provide "
        "there — it rejects the whole file at validation and CI stops running entirely"
    )


def test_the_artifact_probes_run_inside_the_job_that_is_isolated() -> None:
    """The declaration is worth nothing if a probe moved to a job that does not carry it.

    Asserted against the probe flags rather than step names, because a step can be renamed and
    still be the thing that launches the artifact.
    """
    steps = frozen_job()["steps"]
    commands = " ".join(str(step.get("run", "")) for step in steps)

    for probe in ARTIFACT_PROBES:
        assert probe in commands, (
            f"{probe} is no longer run by the frozen job. If it moved, the job it moved to needs "
            f"the same profile isolation, and this test is the record that it does"
        )


def test_the_update_probe_still_runs_and_is_not_the_thing_that_was_disabled() -> None:
    """`T-298`'s trap: the baseline probe also goes green if the override route is removed.

    The failing assertion was *"the artifact bundles yt-dlp X but this build pins Y"*, and deleting
    the in-app update probe would silence it just as effectively as isolating the profile — while
    destroying the only evidence that `OPS-002`'s route works inside a frozen build at all
    (`T198-R2`). So the fix is required to keep that probe, not merely to make the first one pass.
    """
    steps = frozen_job()["steps"]
    names = [str(step.get("name", "")) for step in steps]

    assert any("update works inside the frozen artifact" in name for name in names), (
        "the in-app update probe is gone from the frozen job. Isolating the profile must not be "
        "achieved by removing the route that needs a profile (T198-R2, "
        "docs/project/TESTING.md release gate item 10)"
    )


def test_the_profile_is_removed_when_the_job_ends() -> None:
    """A gate that isolates itself by filling a disk has traded one machine problem for another.

    `runner.temp` outlives the job on the self-hosted machines, and each frozen run's profile holds
    a downloaded yt-dlp.
    """
    steps = frozen_job()["steps"]
    cleanup = [step for step in steps if "FROZEN_PROFILE" in str(step.get("run", ""))]
    removing = [step for step in cleanup if "rm -rf" in str(step.get("run", ""))]

    assert removing, "nothing removes the per-run profile, so every run leaves one behind"
    assert any(str(step.get("if", "")).strip() == "always()" for step in removing), (
        "the cleanup is conditional, so a failed run — the one most likely to have left a "
        "half-installed copy — keeps its profile"
    )
