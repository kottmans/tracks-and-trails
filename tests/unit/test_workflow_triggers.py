"""No workflow may carry a fork-triggerable event, and this is the half that fails closed (`T-264`).

`T-262` removed the `pull_request:` trigger from three workflows because **every runner this
project uses is self-hosted**. On a public repository GitHub runs a fork's pull request with the
fork's own code, and `pytest` executes whatever Python that fork ships — so the trigger is
arbitrary code execution on the maintainer's Fedora desktop and on `STARBASE`, on the maintainer's
own network. Removing it closed the path.

**Nothing kept it closed.** `T262-R3` is that finding: the control lived in prose and in review
attention, and the next person to add a workflow — or to restore one from an older copy — reopens
it silently against a green board. `tests/unit/test_commit_message_check.py` pins the *dormant
concurrency expression* in `commit-messages.yml`, which mentions `pull_request` and is deliberately
unreachable; it says nothing about triggers, so adding `pull_request:` back leaves it green.

## Why this reads the `on:` block rather than grepping the file

Grepping for `pull_request` fails in both directions here. It fires on
`commit-messages.yml`'s retained concurrency expression, which is documented dormant restoration
scaffolding and must stay; and it fires on every comment in this repository that explains *why*
the trigger is gone — of which there are many, because each removal carries its reason in the file.
A gate that cries wolf on its own documentation gets deleted. So the scan isolates the trigger
block and reads only that.

## What is forbidden, and what this does not claim

`pull_request` and `pull_request_target`, which is the rule `T-264` states. `pull_request_target`
matters more than it looks: it runs the *base* repository's workflow with a read-write token, and
is the one people reach for when they want fork PRs to work.

**The wider set `T-262`'s manual audit covered — `workflow_run`, `issue_comment`,
`repository_dispatch` — is checked separately below and is beyond `T-264`'s stated criteria.** It
is split out rather than folded in so the reviewer can rule on the widening instead of finding it
already applied.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

#: The rule `T-264` states. Both put fork-authored code on a runner; the second also hands it a
#: read-write token, because it runs the base repository's definition.
FORBIDDEN = ("pull_request", "pull_request_target")

#: Fork-reachable events `T-262`'s manual audit also checked. **Not part of `T-264`'s criteria** —
#: see the module docstring. `issue_comment` fires on pull-request comments from anyone who can
#: comment; `workflow_run` chains off a workflow that may itself have been fork-triggered;
#: `repository_dispatch` needs a token today but is a trigger nobody reviews twice.
ALSO_AUDITED = ("workflow_run", "issue_comment", "repository_dispatch")


def strip_comments(line: str) -> str:
    """`line` without a trailing `#` comment.

    Naive about `#` inside quotes, and that is safe here: this only ever runs over a trigger block,
    where the values are event names, globs and cron strings. A `#` inside one of those would be a
    stranger thing than this gate mishandling it.
    """
    return line.split("#", 1)[0] if "#" in line else line


def trigger_block(text: str) -> list[str]:
    """The lines of the `on:` block, comments removed, or `[]` if the file declares no triggers.

    YAML 1.1 reads a bare `on` as the boolean `true`, so a workflow may legitimately spell the key
    `"on":` or `True:`. All three are accepted rather than assumed away — a scan that silently
    skipped a file spelled differently would report the clean answer for a file it never read.
    """
    lines = text.splitlines()
    start = next(
        (
            i
            for i, line in enumerate(lines)
            if re.match(r"""^(on|["']on["']|true|True)\s*:""", line)
        ),
        None,
    )
    if start is None:
        return []

    block = [strip_comments(lines[start])]
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # A non-indented line ends the block: the next top-level key.
        if not line[:1].isspace():
            break
        block.append(strip_comments(line))
    return block


def forbidden_triggers_in(text: str, forbidden: tuple[str, ...] = FORBIDDEN) -> list[str]:
    """Every forbidden event `text`'s trigger block declares.

    Matches the mapping form (`  pull_request:`) and the inline form
    (`on: [push, pull_request]`), which are the two `T-264` names. Word boundaries keep
    `pull_request` from matching inside `pull_request_target`, so a file carrying the second is
    reported as the second rather than as both.
    """
    block = "\n".join(trigger_block(text))
    return [event for event in forbidden if re.search(rf"(?<![\w-]){event}(?![\w-])", block)]


def workflow_files() -> list[Path]:
    """Every workflow, found by extension rather than by name.

    `T-264`'s fourth criterion: a new unsafe workflow must fail without anybody remembering to add
    it to a list here.
    """
    return sorted(p for p in WORKFLOWS.iterdir() if p.suffix in {".yml", ".yaml"})


@contextmanager
def temporary_workflow(name: str, body: str) -> Iterator[Path]:
    """A real file in the real directory, removed afterwards.

    Written to `.github/workflows/` rather than to `tmp_path` on purpose: what is under test is
    that the scan *discovers* files, and a fixture handing it a path proves only that it can read
    one it was given. `T-260` is four rounds of precedent for a gate that passed because the test
    arranged the thing the gate was supposed to find.
    """
    path = WORKFLOWS / name
    assert not path.exists(), f"{name} already exists; this test would overwrite it"
    path.write_text(body, encoding="utf-8")
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


# --- the live gate ---------------------------------------------------------------------------


def test_no_workflow_carries_a_pull_request_trigger() -> None:
    """The control itself. `T-262` closed this path; this is what keeps it closed."""
    offenders = {
        path.name: found
        for path in workflow_files()
        if (found := forbidden_triggers_in(path.read_text(encoding="utf-8")))
    }

    assert not offenders, (
        f"these workflows would run fork-authored code on self-hosted runners: {offenders}. "
        "T-262 removed every pull-request trigger because each one is arbitrary code execution "
        "on the maintainer's machines. Restoring one needs its jobs gated on "
        "`github.event.pull_request.head.repo.full_name == github.repository`, and needs this "
        "policy and its mutations changed in the same reviewed commit."
    )


def test_the_scan_actually_read_the_workflows() -> None:
    """A scan of nothing passes. That is the failure mode this file exists to avoid twice over.

    `T-262`'s audit was a person looking; if this replacement can return a clean answer from an
    empty directory listing, it is worth less than the person was.
    """
    found = workflow_files()

    assert len(found) >= 4, f"only {len(found)} workflow files found: {[p.name for p in found]}"
    assert {"ci.yml", "commit-messages.yml", "prose.yml", "t074-repeat.yml"} <= {
        p.name for p in found
    }
    assert all(trigger_block(p.read_text(encoding="utf-8")) for p in found), (
        "a workflow declared no triggers this scan could find, so it was checked vacuously"
    )


# --- the detector, case by case --------------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "body", "expected"),
    [
        ("mapping form", "on:\n  push:\n  pull_request:\n\njobs: {}\n", ["pull_request"]),
        ("inline form", "on: [push, pull_request]\n\njobs: {}\n", ["pull_request"]),
        (
            "inline form, spaced",
            "on: [ push , pull_request ]\n\njobs: {}\n",
            ["pull_request"],
        ),
        (
            "pull_request_target",
            "on:\n  pull_request_target:\n\njobs: {}\n",
            ["pull_request_target"],
        ),
        (
            "with filters underneath",
            'on:\n  pull_request:\n    branches: ["main"]\n\njobs: {}\n',
            ["pull_request"],
        ),
        (
            "quoted key, because YAML reads bare `on` as true",
            '"on":\n  pull_request:\n\njobs: {}\n',
            ["pull_request"],
        ),
        ("safe: push only", "on:\n  push:\n\njobs: {}\n", []),
        (
            "safe: dispatch and schedule",
            'on:\n  workflow_dispatch:\n  schedule:\n    - cron: "0 6 * * *"\n\njobs: {}\n',
            [],
        ),
        (
            "safe: a comment inside the block mentioning the event",
            "on:\n  # No pull_request: fork code on self-hosted runners (T-262).\n  push:\n\n"
            "jobs: {}\n",
            [],
        ),
        (
            "safe: a trailing comment mentioning the event",
            "on:\n  push:  # deliberately not pull_request, see T-262\n\njobs: {}\n",
            [],
        ),
        (
            "safe: the event named outside the trigger block",
            "on:\n  push:\n\nconcurrency:\n"
            "  cancel-in-progress: ${{ github.event_name == 'pull_request' }}\n\njobs: {}\n",
            [],
        ),
    ],
)
def test_the_detector_reads_the_trigger_block_and_only_that(
    case: str, body: str, expected: list[str]
) -> None:
    """Eleven cases: six that must be caught, five that must not.

    The five safe ones are the reason this is a parser and not a grep. Three of them are shapes
    this repository actually contains — a comment explaining the absent trigger, a trailing comment
    beside a live one, and `commit-messages.yml`'s dormant concurrency expression.
    """
    assert forbidden_triggers_in(body) == expected, case


def test_the_dormant_concurrency_expression_is_left_alone() -> None:
    """Not a synthetic case: this text is in `commit-messages.yml` and `T-262` chose to keep it.

    It is labelled dormant restoration scaffolding, and `test_commit_message_check.py` pins it. A
    gate that failed on it would force a choice between this control and that record.
    """
    workflow = (WORKFLOWS / "commit-messages.yml").read_text(encoding="utf-8")

    assert "pull_request" in workflow, "the dormant expression is gone; this test is now vacuous"
    assert forbidden_triggers_in(workflow) == []


# --- the discovery half, proved with real files -----------------------------------------------


def test_a_new_unsafe_workflow_is_caught_without_being_listed_here() -> None:
    """`T-264`'s fourth criterion, proved by adding one rather than by asserting the glob.

    The file is created in the real directory, scanned by the same function the live gate calls,
    and removed. If discovery were name-based this would pass silently.
    """
    with temporary_workflow(
        "zz-t264-probe.yml", "on:\n  pull_request:\n\njobs:\n  x:\n    runs-on: ubuntu-latest\n"
    ) as path:
        offenders = {
            p.name: found
            for p in workflow_files()
            if (found := forbidden_triggers_in(p.read_text(encoding="utf-8")))
        }

        assert path.name in offenders, "a new pull-request-triggered workflow was not discovered"
        assert offenders[path.name] == ["pull_request"]

    assert not path.exists(), "the probe workflow outlived its test"


def test_a_new_safe_workflow_does_not_trip_the_gate() -> None:
    """The other direction, without which the gate could pass by rejecting everything.

    **Asserts about the probe, not about the whole directory.** The first version asserted the
    scan found nothing anywhere, so mutating an unrelated real workflow failed this test too — it
    reported "a safe workflow tripped the gate" when no such thing had happened. A control that
    fails for a reason other than the one it names sends the next reader to the wrong file.
    """
    name = "zz-t264-safe-probe.yml"
    with temporary_workflow(
        name,
        "on:\n  workflow_dispatch:\n\njobs:\n  x:\n    runs-on: ubuntu-latest\n",
    ) as path:
        assert path in workflow_files(), "the safe probe was not discovered, so it proves nothing"
        assert forbidden_triggers_in(path.read_text(encoding="utf-8")) == []


def test_a_yaml_suffixed_workflow_is_scanned_too() -> None:
    """GitHub accepts both suffixes; a scan that only globbed `*.yml` would miss half of them."""
    name = "zz-t264-probe.yaml"
    with temporary_workflow(name, "on:\n  pull_request_target:\n\njobs: {}\n"):
        offenders = {
            p.name: found
            for p in workflow_files()
            if (found := forbidden_triggers_in(p.read_text(encoding="utf-8")))
        }

    # Scoped to the probe for the reason the safe-probe test records: an unrelated real violation
    # must fail `test_no_workflow_carries_a_pull_request_trigger`, not this one.
    assert offenders.get(name) == ["pull_request_target"], (
        f"the .yaml probe was not scanned; offenders were {offenders}"
    )


# --- beyond T-264's criteria, split out so it can be ruled on ---------------------------------


def test_the_wider_fork_reachable_set_is_also_absent_today() -> None:
    """`workflow_run`, `issue_comment`, `repository_dispatch` — `T-262`'s audit covered these.

    **This is not `T-264`'s stated rule**, and it is a separate test so that a future task wanting
    one of these fails here, reads this docstring, and makes a deliberate decision — rather than
    finding the wider ban already merged under a narrower task's name.
    """
    offenders = {
        path.name: found
        for path in workflow_files()
        if (found := forbidden_triggers_in(path.read_text(encoding="utf-8"), ALSO_AUDITED))
    }

    assert not offenders, (
        f"{offenders} — fork-reachable beyond T-264's rule. If one of these is wanted, rule on it "
        "and change this test in the same commit."
    )
