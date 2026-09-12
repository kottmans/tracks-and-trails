"""The release workflow's shape, and the one place CI's trust boundary widens (`T-324`).

**A tag cannot be quietly corrected.** A wrong commit is amended and a wrong release page is
edited; a tag somebody has installed from is a name in the wild. So the properties asserted here
are the ones a first release gets exactly one attempt at — and the one that matters most is the
negative: **nothing in this project publishes.**

`tests/unit/test_workflow_triggers.py` already covers the `pull_request` rule for every workflow
including this one. What is here is what is specific to a workflow that can write to the
repository.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import pytest
import yaml

REPOSITORY: Final = Path(__file__).resolve().parents[2]
WORKFLOW: Final = REPOSITORY / ".github" / "workflows" / "release.yml"


def workflow() -> dict[str, Any]:
    parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict), "release.yml did not parse as a mapping"
    return parsed


def triggers() -> dict[str, Any]:
    """`on:` — which PyYAML resolves to the boolean `True`, because YAML 1.1 says so.

    The trap `test_workflow_triggers.py` documents: a text scan for `on:` is bypassable and a
    naive `parsed["on"]` is simply absent. Both keys are checked so this cannot silently read
    nothing and pass.
    """
    parsed = workflow()
    # `parsed.get(True, ...)` does not type-check: the dict is `dict[str, Any]` and `True` is not
    # a `str`. The key genuinely is the boolean, so the lookup is done in two steps rather than
    # by widening the annotation and losing the rest of the file's checking.
    untyped: dict[Any, Any] = parsed
    declared = untyped.get(True, untyped.get("on"))
    assert isinstance(declared, dict), f"release.yml declares no usable on: block ({declared!r})"
    return declared


def steps(job: str) -> list[dict[str, Any]]:
    return list(workflow()["jobs"][job]["steps"])


def run_text() -> str:
    """Every `run:` in the file, so a claim about what the workflow *does* can be asserted."""
    return "\n".join(
        str(step.get("run", ""))
        for job in workflow()["jobs"].values()
        for step in job.get("steps", [])
    )


# --- the trigger: one, and only one -----------------------------------------------------------


def test_it_runs_on_a_tag_and_on_nothing_else() -> None:
    """A release has exactly one legitimate trigger.

    `workflow_dispatch` would invite a draft built from an untagged tree, and `ci.yml` stays the
    per-push smoke — `T-324`'s criteria say this workflow does not run on push.
    """
    declared = triggers()
    assert set(declared) == {"push"}, f"release.yml has extra triggers: {sorted(declared)}"
    assert declared["push"] == {"tags": ["v*"]}, declared["push"]
    assert "branches" not in declared["push"], "a branch push would build a release"


def test_it_carries_no_pull_request_trigger() -> None:
    """Restated here rather than delegated, because this is the workflow that can write.

    `SECURITY.md` §CI trust boundary: a fork's pull request runs the fork's code, and every runner
    here is a personal machine on a home network.
    """
    declared = triggers()
    assert "pull_request" not in declared
    assert "pull_request_target" not in declared


# --- the permission, and where it is not ------------------------------------------------------


def test_the_default_is_read_only() -> None:
    """`SECURITY.md`: every workflow declares `contents: read` at the top level."""
    assert workflow().get("permissions") == {"contents": "read"}


def test_only_the_draft_job_can_write() -> None:
    """**The one place this project's CI trust boundary widens**, and it widens by one scope for
    one job. A build job with write access could replace a release; it has no reason to."""
    jobs = workflow()["jobs"]
    writers = [
        name
        for name, job in jobs.items()
        if (job.get("permissions") or {}).get("contents") == "write"
    ]
    assert writers == ["draft"], f"these jobs can write to the repository: {writers}"
    for name in ("verify", "build-linux", "build-windows"):
        assert "permissions" not in jobs[name] or jobs[name]["permissions"] == {
            "contents": "read"
        }, f"{name} declares a permission it does not need"


# --- it drafts, and that is all it does -------------------------------------------------------


def test_it_drafts_and_never_publishes() -> None:
    """**The negative that matters.** Publishing is a human click after `T-328`'s review.

    Asserted three ways because one would be easy to lose in an edit: the flag is passed, the
    result is read back, and no publishing verb appears anywhere in the file.
    """
    text = run_text()
    assert "--draft" in text, "the release is not created as a draft"
    assert "isDraft" in text, "nothing reads back whether it actually is a draft"
    for verb in ("gh release edit", "--latest", "release publish"):
        assert verb not in text, f"{verb!r} appears in a workflow that must never publish"


def test_the_draft_assertion_can_fail_the_job() -> None:
    """A read-back that only printed would be decoration."""
    text = run_text()
    assert 'if [ "$state" != "true" ]' in text, "the draft check does not branch"
    assert "Nothing in this project publishes" in text, "the failure does not say why"


# --- the order: nothing is built against a tag that is wrong -----------------------------------


def test_nothing_is_built_before_the_tag_is_verified() -> None:
    """`T-324` step 1 exists so a mismatch costs no builds — and so a tag on an unreviewed
    branch cannot produce artifacts that look exactly like real ones."""
    jobs = workflow()["jobs"]
    for name in ("build-linux", "build-windows"):
        assert jobs[name]["needs"] == "verify" or "verify" in jobs[name]["needs"], (
            f"{name} does not wait for the tag check"
        )
    assert set(jobs["draft"]["needs"]) == {"build-linux", "build-windows"}


@pytest.mark.parametrize(
    "tool",
    ["tools/version_tag_check.py", "tools/changelog_section.py", "packaging/artifact_gates.py"],
)
def test_the_workflow_uses_the_committed_tools_rather_than_inline_shell(tool: str) -> None:
    """`T240-R1`: a decision buried in inline shell is a decision nobody reviews. Each of these
    is a function with a CLI and its own tests."""
    assert tool in run_text(), f"the workflow no longer runs {tool}"


def test_the_verify_job_has_the_history_its_checks_need() -> None:
    """A shallow clone gives `git merge-base --is-ancestor` nothing to look at, and it would
    then fail or pass for reasons unrelated to the tag — `T-331` records a session lost to
    exactly that in `ci.yml`."""
    checkout = next(step for step in steps("verify") if "checkout" in str(step.get("uses", "")))
    assert checkout.get("with", {}).get("fetch-depth") == 0


# --- the release builds are gated, not merely built --------------------------------------------


@pytest.mark.parametrize("job", ["build-linux", "build-windows"])
def test_each_release_build_is_gated_and_probed(job: str) -> None:
    """`T-324` step 3: the gates and probes run against the **release** builds.

    `ci.yml`'s `frozen` job proves the *smoke* build; the release build differs in exactly the
    places that matter — windowed on Windows, ffmpeg bundled, built in a container on Linux.
    """
    text = "\n".join(str(step.get("run", "")) for step in steps(job))
    assert "artifact_gates.py" in text, f"{job} does not gate what it built"
    for probe in ("--spawn-probe", "--ytdlp-probe", "--database-probe", "--ytdlp-update-probe"):
        assert probe in text, f"{job} does not run {probe} on the release build"


def test_the_windows_probes_read_the_report_file_rather_than_stdout() -> None:
    """`console=False` leaves a windowed build with no `stdout`, which is why
    `_freeze_probe.say` writes to `TT_PROBE_REPORT`. Reading the console would read nothing and
    pass — the exact shape of `T-319`'s finding about a build with no platform plugins."""
    probing = next(
        step for step in steps("build-windows") if "--spawn-probe" in str(step.get("run", ""))
    )
    assert (probing.get("env") or {}).get("TT_PROBE_REPORT"), (
        "the Windows probe step does not set TT_PROBE_REPORT, so a windowed build reports nothing"
    )


def test_the_linux_artifact_is_built_in_the_container_rather_than_on_the_runner() -> None:
    """`REL-004` and `OPS-012`: the runner is glibc 2.43, and an AppImage built there fails on
    every current LTS while passing every test run there. Measured, not argued."""
    text = "\n".join(str(step.get("run", "")) for step in steps("build-linux"))
    # **Not merely present in the text.** A mutation that replaced the command with
    # `true # podman run ...` survived a substring check: the string was still there and the
    # container was not. So the line has to be a command rather than a comment.
    invoking = [
        line
        for line in text.splitlines()
        if "podman run" in line and not line.strip().startswith("#")
    ]
    assert invoking, "podman run appears only in a comment, so nothing builds in the container"
    assert not any(line.strip().startswith(("true", "false", ":")) for line in invoking), (
        f"the container build is stubbed out: {invoking}"
    )
    assert "bookworm" in text, "the container is no longer the oldest-glibc one"


def test_it_refuses_rather_than_installing_inno_setup() -> None:
    """`OPS-012` §3: a self-hosted runner must not provision itself as a side effect of a build.

    A build that installed a compiler would make the machine's state a function of whoever pushed
    a tag.
    """
    text = "\n".join(str(step.get("run", "")) for step in steps("build-windows"))
    assert "ISCC" in text
    assert "OPS-012" in text, "the refusal does not name the rule it enforces"
    for installer in ("choco install", "winget install", "Invoke-WebRequest"):
        assert installer not in text, f"the workflow installs tooling with {installer!r}"


def test_both_artifacts_and_a_checksum_file_are_required() -> None:
    """`T-324` step 4, and the negative: a release missing a platform is a release nobody
    notices is missing a platform."""
    text = "\n".join(str(step.get("run", "")) for step in steps("draft"))
    assert "sha256sum" in text and "SHA256SUMS" in text
    assert "no AppImage" in text and "no installer" in text, (
        "a missing artifact would produce a draft rather than a failure"
    )


def test_a_release_build_is_not_cancellable() -> None:
    """A half-built draft is the one artifact nobody can tell apart from a finished one — and
    `cancel-in-progress` has already cost this project a Windows evidence run twice."""
    concurrency = workflow().get("concurrency")
    assert concurrency is not None, "release.yml has no concurrency group"
    assert concurrency.get("cancel-in-progress") is False, concurrency
