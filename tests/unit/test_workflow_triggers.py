"""No workflow may carry a pull-request trigger, and this is the half that fails closed (`T-264`).

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

## Why this parses the YAML instead of reading the text

**The first version read the trigger block as text, and `T264-R2` broke it twice with valid GitHub
Actions YAML.** An anchor defined elsewhere and aliased into the trigger list —
`name: &fork_event pull_request` with `on: [push, *fork_event]` — resolves to a pull-request
trigger that a text scan never sees, because the word does not appear in the block. And
`on: {push: {branches: ["feature#1"]}, pull_request: null}` was truncated at the `#` inside a
quoted string, dropping the forbidden event from the scanned text. Both are **accepting-direction**
bypasses: the gate said clean about a workflow GitHub would run on a fork's code.

Refusing anchors outright was not available: `ci.yml`'s own `on:` block defines `&prose`, so a rule
against them would reject the repository it protects. A gate that decides a security policy has to
read the value GitHub executes, which means the parser GitHub's syntax is defined against. PyYAML
is a declared dev dependency for exactly this, and it is imported plainly — never through
`importorskip`, which would turn this into a test that skips on the machine that most needs it.

## What is forbidden

`pull_request` and `pull_request_target`, which is the rule `T-264` states and the whole of it.

`pull_request_target` is forbidden for a different reason than `pull_request`, and `T264-R3`
corrected this file for overstating it: it runs the **base branch's** workflow definition — trusted
code — with a read-write token and access to secrets. It does not execute fork code by default. The
danger is the transition, where a workflow under it checks out or runs the pull request's head; the
combination of privilege and proximity to untrusted content is why it stays out of a repository
whose runners are somebody's desktops.

**Nothing wider is enforced here.** An earlier version also banned `workflow_run`, `issue_comment`
and `repository_dispatch`. `T264-R3` removed it: their risk depends on what the workflow does with
untrusted content rather than on the trigger existing, and enforcing them under this task's name
made a policy nobody had authorized redden the required suite. A blanket event allowlist needs its
own task and its own event-specific reasoning.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The directory scanned. Rebound by `temporary_workflows` so the discovery tests can build a whole
#: directory under `tmp_path` — see `T264-R1`, and `workflow_files` for why they must not use the
#: real one.
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

#: The rule `T-264` states. See the module docstring for why the second is here and what it is not.
FORBIDDEN = ("pull_request", "pull_request_target")

#: The `on` key, in the spellings YAML 1.1 produces. A bare `on` is the boolean `True` — every
#: workflow in this repository lands here — and a quoted one stays a string.
TRIGGER_KEYS = (True, "on", "On", "ON")


class UnreadableWorkflowError(Exception):
    """The trigger block could not be resolved, which the gate must treat as a failure.

    **Fail closed.** A workflow this cannot parse is one whose triggers are unknown, and an unknown
    trigger set is exactly the state the gate exists to prevent being green.
    """


def declared_events(text: str) -> frozenset[str]:
    """Every event the workflow triggers on, as GitHub resolves it.

    Accepts the three shapes the schema allows — `on: push`, `on: [push, ...]` and
    `on: {push: ...}` — and raises rather than guessing at anything else. Aliases and quoted `#`
    are the parser's problem now, which is the point of `T264-R2`.
    """
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise UnreadableWorkflowError(f"YAML did not parse: {error}") from error

    if not isinstance(document, dict):
        raise UnreadableWorkflowError(
            f"the workflow is not a mapping, but {type(document).__name__}"
        )

    key = next((k for k in TRIGGER_KEYS if k in document), None)
    if key is None:
        raise UnreadableWorkflowError("no `on:` key; GitHub would reject this workflow")

    triggers = document[key]
    if isinstance(triggers, str):
        return frozenset({triggers})
    if isinstance(triggers, list):
        return frozenset(str(event) for event in triggers)
    if isinstance(triggers, dict):
        return frozenset(str(event) for event in triggers)
    raise UnreadableWorkflowError(f"`on:` is a {type(triggers).__name__}, which this cannot read")


def forbidden_triggers_in(text: str) -> list[str]:
    """Which of `FORBIDDEN` the workflow declares, in a stable order."""
    declared = declared_events(text)
    return [event for event in FORBIDDEN if event in declared]


def workflow_files() -> list[Path]:
    """Every workflow in `WORKFLOWS`, found by extension rather than by name.

    `T-264`'s fourth criterion: a new unsafe workflow must fail without anybody remembering to add
    it to a list here. The discovery tests exercise **this function**, with no file list supplied,
    against a directory built under `tmp_path`.
    """
    return sorted(p for p in WORKFLOWS.iterdir() if p.suffix in {".yml", ".yaml"})


@contextmanager
def temporary_workflows(root: Path, files: dict[str, str]) -> Iterator[Path]:
    """Point the scanner at a directory of `files` built under `tmp_path`.

    **The first version wrote probes into the real `.github/workflows/`, and `T264-R1` is what that
    cost.** `ai/TESTING.md` says tests write nowhere outside `tmp_path`, and CI runs
    `pytest -n auto`: one worker listed a probe another worker had already deleted, and the file
    failed 1 of 18 in the mode meant to carry it. Worse than the flake, the shared directory let one
    worker's deliberately unsafe probe be seen by another worker's live gate — a security test that
    can fail because of its own fixtures teaches people to re-run it.
    """
    root.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (root / name).write_text(body, encoding="utf-8")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(f"{__name__}.WORKFLOWS", root)
        yield root


SAFE = "on:\n  push:\n\njobs:\n  x:\n    runs-on: ubuntu-latest\n"

#: `T264-R2`'s first probe, reproduced. The forbidden word never appears inside the trigger block.
ALIASED = (
    "name: &fork_event pull_request\n"
    "on: [push, *fork_event]\n"
    "\njobs:\n  x:\n    runs-on: [self-hosted]\n"
)

#: `T264-R2`'s second probe. A text scan truncates at the `#` and never reaches `pull_request`.
QUOTED_HASH = 'on: {push: {branches: ["feature#1"]}, pull_request: null}\n\njobs: {}\n'


# --- the live gate ---------------------------------------------------------------------------


def test_no_workflow_carries_a_pull_request_trigger() -> None:
    """The control itself. `T-262` closed this path; this is what keeps it closed."""
    offenders = {}
    for path in workflow_files():
        try:
            found = forbidden_triggers_in(path.read_text(encoding="utf-8"))
        except UnreadableWorkflowError as error:
            offenders[path.name] = [f"unreadable: {error}"]
        else:
            if found:
                offenders[path.name] = found

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
    empty directory listing, it is worth less than the person was. Resolving every trigger set is
    part of the claim: a file the parser could not read is not a file that was checked.
    """
    found = workflow_files()

    assert len(found) >= 4, f"only {len(found)} workflow files found: {[p.name for p in found]}"
    assert {"ci.yml", "commit-messages.yml", "prose.yml", "t074-repeat.yml"} <= {
        p.name for p in found
    }
    for path in found:
        assert declared_events(path.read_text(encoding="utf-8")), f"{path.name} resolved no events"


def test_the_dormant_concurrency_expression_is_left_alone() -> None:
    """Not a synthetic case: this text is in `commit-messages.yml` and `T-262` chose to keep it.

    It is labelled dormant restoration scaffolding, and `test_commit_message_check.py` pins it. A
    gate that failed on it would force a choice between this control and that record — which is
    what a text scan would have done, and the second reason this one parses instead.
    """
    workflow = (WORKFLOWS / "commit-messages.yml").read_text(encoding="utf-8")

    assert "pull_request" in workflow, "the dormant expression is gone; this test is now vacuous"
    assert forbidden_triggers_in(workflow) == []


# --- the detector, case by case ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "body", "expected"),
    [
        ("mapping form", "on:\n  push:\n  pull_request:\n\njobs: {}\n", ["pull_request"]),
        ("inline form", "on: [push, pull_request]\n\njobs: {}\n", ["pull_request"]),
        ("scalar form", "on: pull_request\n\njobs: {}\n", ["pull_request"]),
        (
            "pull_request_target",
            "on:\n  pull_request_target:\n\njobs: {}\n",
            ["pull_request_target"],
        ),
        (
            "both at once, reported in rule order",
            "on:\n  pull_request:\n  pull_request_target:\n\njobs: {}\n",
            ["pull_request", "pull_request_target"],
        ),
        (
            "with filters underneath",
            'on:\n  pull_request:\n    branches: ["main"]\n\njobs: {}\n',
            ["pull_request"],
        ),
        (
            "quoted key, because YAML 1.1 reads bare `on` as true",
            '"on":\n  pull_request:\n\njobs: {}\n',
            ["pull_request"],
        ),
        ("T264-R2: an alias resolving to the event", ALIASED, ["pull_request"]),
        ("T264-R2: a quoted `#` before the event", QUOTED_HASH, ["pull_request"]),
        ("safe: push only", SAFE, []),
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
        (
            "safe: an anchor defined in the block, as ci.yml does",
            'on:\n  push:\n    paths-ignore: &prose\n      - "ai/**"\n  workflow_dispatch:\n\n'
            "jobs: {}\n",
            [],
        ),
    ],
)
def test_the_detector_resolves_what_github_would_run(
    case: str, body: str, expected: list[str]
) -> None:
    """Fifteen cases: nine that must be caught, six that must not.

    The two `T264-R2` rows are the ones that matter most — both were **accepted** by the text
    scanner this replaced, and both are valid YAML that GitHub runs. The last safe row is the shape
    that stops the obvious over-correction: `ci.yml` defines an anchor inside its own trigger block,
    so a rule against anchors would reject the repository it protects.
    """
    assert forbidden_triggers_in(body) == expected, case


@pytest.mark.parametrize(
    ("case", "body"),
    [
        ("not YAML at all", "on: [push\n  bad: ["),
        ("not a mapping", "- just\n- a list\n"),
        ("no trigger key", "name: x\njobs: {}\n"),
        ("a trigger shape this cannot read", "on: 42\n\njobs: {}\n"),
    ],
)
def test_an_unresolvable_workflow_fails_closed(case: str, body: str) -> None:
    """Unknown triggers are the state the gate exists to prevent being green.

    Returning `[]` for a file nobody could parse is the accepting direction, and `T264-R2` is a
    finding about exactly that: the gate said clean about workflows it had not understood.
    """
    with pytest.raises(UnreadableWorkflowError):
        forbidden_triggers_in(body)


# --- discovery, proved against a directory the scan has never seen -----------------------------


def test_a_new_unsafe_workflow_is_caught_without_being_listed_here(tmp_path: Path) -> None:
    """`T-264`'s fourth criterion: discovery, not a filename list.

    Calls `workflow_files()` with no arguments, against a directory built here. Handing the scanner
    a path would prove only that it can read one it was given.
    """
    with temporary_workflows(
        tmp_path / "workflows",
        {"a-safe.yml": SAFE, "zz-unsafe.yml": "on:\n  pull_request:\n\njobs: {}\n"},
    ):
        offenders = {
            p.name: forbidden_triggers_in(p.read_text(encoding="utf-8")) for p in workflow_files()
        }

    assert offenders == {"a-safe.yml": [], "zz-unsafe.yml": ["pull_request"]}


def test_a_yaml_suffixed_workflow_is_scanned_too(tmp_path: Path) -> None:
    """GitHub accepts both suffixes; a scan that only globbed `*.yml` would miss half of them."""
    with temporary_workflows(
        tmp_path / "workflows",
        {"probe.yaml": "on:\n  pull_request_target:\n\njobs: {}\n", "other.txt": "not a workflow"},
    ):
        scanned = [p.name for p in workflow_files()]
        offenders = {
            p.name: forbidden_triggers_in(p.read_text(encoding="utf-8")) for p in workflow_files()
        }

    assert scanned == ["probe.yaml"], "the `.txt` was scanned, or the `.yaml` was not"
    assert offenders == {"probe.yaml": ["pull_request_target"]}


def test_the_alias_probe_is_caught_through_real_discovery(tmp_path: Path) -> None:
    """`T264-R2`'s probe end to end, not only through the detector.

    The reviewer's version was a real file in the real directory and both gates passed it. This is
    the same workflow, reached the same way — found by `workflow_files()`, read off disk — with the
    checkout left alone.
    """
    with temporary_workflows(tmp_path / "workflows", {"aliased.yml": ALIASED}):
        offenders = {
            p.name: forbidden_triggers_in(p.read_text(encoding="utf-8")) for p in workflow_files()
        }

    assert offenders == {"aliased.yml": ["pull_request"]}
