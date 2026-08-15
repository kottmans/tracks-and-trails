"""The commit-message gate `T-240` built, against the two defects it exists to stop.

**Both were real commits.** `12dff92` reached `origin/main` carrying an AI authorship trailer and
`T-065` closed it by *preserving* the exception rather than rewriting published history, leaving a
standing criterion: *"no later commit carries an AI authorship trailer."* Thirteen days later
`fb41895` carried the identical trailer **and** omitted `Task:`. A sentence in a closed task is not
a mechanism, and the tooling that writes these messages appends the trailer by default — so the
failure recurs by construction rather than by carelessness.

The module is loaded from `tools/` by path. It is developer tooling rather than product code, so it
does not belong under `src/`, and `tools/` is not a package.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

import pytest

TOOL = Path(__file__).resolve().parents[2] / "tools" / "commit_message_check.py"


def load() -> ModuleType:
    specification = importlib.util.spec_from_file_location("commit_message_check", TOOL)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


check = load()


GOOD = """Bound stored geometry to Qt's maximum

Validating the four numbers individually missed that QRect derives
right() as x + width - 1.

- Reject bools, inf and nan in load_geometry.

Task: T-027
"""


def rules(message: str) -> list[str]:
    return [fault.rule for fault in check.check_message(message)]


def test_a_conforming_message_passes() -> None:
    """The baseline, without which every assertion below could pass by rejecting everything."""
    assert check.check_message(GOOD) == []


# --- §7: no AI tool named as an author ---------------------------------------------------------


@pytest.mark.parametrize(
    "trailer",
    [
        "Co-Authored-By: Claude <noreply@anthropic.com>",
        "Co-authored-by: Claude Opus 5 <noreply@anthropic.com>",
        "Co-Authored-By: GitHub Copilot <copilot@github.com>",
        "Co-Authored-By: Cursor Agent <agent@cursor.sh>",
        "Signed-off-by: OpenAI Codex <codex@openai.com>",
    ],
)
def test_an_ai_authorship_trailer_is_rejected(trailer: str) -> None:
    """`fb41895`'s defect, and `12dff92`'s before it.

    The first of these is the exact line both commits carried, and the one the tooling appends
    unless it is stopped.
    """
    assert "§7" in rules(GOOD.replace("Task: T-027", f"{trailer}\nTask: T-027"))


@pytest.mark.parametrize(
    "footer",
    [
        "🤖 Generated with Claude Code",
        "Generated with an AI assistant",
        "Co-authored with GPT-5",
    ],
)
def test_a_generated_with_footer_is_rejected(footer: str) -> None:
    """§7 names this shape beside the trailer, and it is not a trailer — so it is matched anywhere.

    A footer sits below the trailer block as often as inside it, and a check that only read the
    last paragraph would miss the ones that do.
    """
    assert "§7" in rules(GOOD + f"\n{footer}\n")


def test_a_human_co_author_is_not_rejected() -> None:
    """The rule is about **AI tools**, not about co-authorship.

    Worth its own test because the cheap implementation of §7 is *"reject `Co-Authored-By:`"*, and
    that would reject a human contributor — a worse failure than the one being prevented, and one
    that would arrive without warning on the first outside contribution.
    """
    trailer = "Co-Authored-By: Ada Lovelace <ada@example.com>"
    message = GOOD.replace("Task: T-027", f"{trailer}\nTask: T-027")
    assert check.check_message(message) == []


def test_a_trailer_quoted_inside_a_bullet_is_not_a_trailer() -> None:
    """**The rule is what the commit *carries*, not what it mentions**, and the line shape says so.

    A trailer starts its line. `- Reject a Co-Authored-By: ... line` is prose about one, and the
    commit that introduced this gate is the obvious example — a check that could not describe
    itself would be reworded around rather than fixed.

    The failure being prevented has a precise shape: tooling appending `Co-Authored-By:` as a real
    trailer, which is what `12dff92` and `fb41895` both carried. Leading whitespace is allowed for,
    since that is the only variation in how it gets appended.
    """
    message = GOOD.replace(
        "- Reject bools",
        "- Reject a Co-Authored-By: Claude <noreply@anthropic.com> line\n- Reject bools",
    )
    assert check.check_message(message) == []


def test_a_generated_with_footer_is_matched_anywhere_and_that_is_deliberate() -> None:
    """The asymmetry with the test above, stated rather than left to be discovered.

    A *"generated with"* footer has no line shape to anchor to — it is a sentence, and §7 names it
    only by its content. So it is matched anywhere, and a commit that wants to *discuss* one has to
    do so without writing the phrase. That is a real cost, accepted because the alternative is a
    pattern loose enough to be satisfied by accident.
    """
    message = GOOD.replace("- Reject bools", "- Explain the generated with footer\n- Reject bools")
    assert "§7" in rules(message)


# --- §13: a Task: trailer, or an explained exemption -------------------------------------------


def test_a_missing_task_trailer_is_rejected() -> None:
    """`fb41895`'s second defect, which `T-065`'s entry names together with the first."""
    assert "§13" in rules(GOOD.replace("\nTask: T-027\n", "\n"))


@pytest.mark.parametrize("value", ["T-027", "T-027..T-032", "T-027, T-031", "T-027..T-032, T-040"])
def test_the_task_forms_13_gives_are_accepted(value: str) -> None:
    assert check.check_message(GOOD.replace("Task: T-027", f"Task: {value}")) == []


@pytest.mark.parametrize(
    "value", ["none - repository setup, no task covers it", "none — a typo fix"]
)
def test_an_explained_exemption_is_accepted(value: str) -> None:
    """§13's *"omit only for work no task covers"* has to survive, and `T-240` requires it to.

    **Spelled as a `Task:` value rather than as a second trailer**, so one grep finds the covered
    commits and the deliberate exceptions alike — and so that omitting the trailer entirely is
    never how this is said.
    """
    assert check.check_message(GOOD.replace("Task: T-027", f"Task: {value}")) == []


@pytest.mark.parametrize("value", ["none", "none  ", "nothing", "n/a", "TBD", "T27", "T-27"])
def test_an_unexplained_or_malformed_exemption_is_rejected(value: str) -> None:
    """A bare `none` is indexed but unexplained, which is the state `T-065`'s criterion was in."""
    assert "§13" in rules(GOOD.replace("Task: T-027", f"Task: {value}"))


def test_the_word_task_in_the_body_does_not_satisfy_the_rule() -> None:
    """Trailers are *"machine-readable, last, after a blank line"* (§13), so only that block counts.

    Without this the gate passes on any message whose prose happens to mention `Task:`, which is
    most messages describing this file.
    """
    message = "Do a thing\n\nThis relates to Task: T-027 in passing.\n"
    assert "§13" in rules(message)


def test_comment_lines_are_ignored() -> None:
    """`.gitmessage` is a template of `#` comments, and git strips them after the hook runs.

    A hook that read them would see the template's own example trailers and pass every message.
    """
    message = "Do a thing\n\n# Task: T-999\n# Co-Authored-By: Claude <noreply@anthropic.com>\n"
    assert rules(message) == ["§13"]


# --- the reported faults name the line -------------------------------------------------------


def test_a_fault_names_the_offending_line() -> None:
    """`T-240`'s first acceptance criterion: the check **names the offending line**.

    A gate that says only *"this message is wrong"* sends the author back to read the whole of
    §13, and the two rules it actually enforces are a small part of it.
    """
    trailer = "Co-Authored-By: Claude <noreply@anthropic.com>"
    faults = check.check_message(GOOD.replace("Task: T-027", f"{trailer}\nTask: T-027"))
    assert len(faults) == 1
    assert trailer in str(faults[0])
    assert "claude" in str(faults[0])


# --- the range half, over real repositories (T240-R1) ------------------------------------------


GOOD_MESSAGE: Final = (
    "Do a thing\n\nBecause it needed doing and nothing else covers it.\n\nTask: T-240\n"
)
BAD_TRAILER: Final = (
    "Do a thing badly\n\nWith a trailer the tooling appends by default.\n\n"
    "Co-Authored-By: Claude <noreply@anthropic.com>\nTask: T-240\n"
)


def run_git(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def commit(repository: Path, message: str, *, name: str = "file.txt") -> str:
    (repository / name).write_text(message[:20], encoding="utf-8")
    run_git(repository, "add", "-A")
    run_git(repository, "commit", "--no-verify", "-m", message)
    return run_git(repository, "rev-parse", "HEAD")


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """A real repository, because the defect being tested is in what `git rev-list` returns.

    `T240-R1` names the absence of these directly: *"There are no unit tests for `commits_in()` or
    `check_range()`, so the 29 passing parser tests cannot see either bypass."* A parser test over a
    string cannot: both bypasses are about which commits are handed to the parser at all.
    """
    root = tmp_path / "repo"
    root.mkdir()
    run_git(root, "init", "-q", "-b", "main")
    run_git(root, "config", "user.email", "test@example.com")
    run_git(root, "config", "user.name", "Test")
    commit(
        root, "Add the first file\n\nThe base every range below is measured from.\n\nTask: T-240\n"
    )
    return root


def test_a_merge_commit_is_checked(repository: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**`T240-R1`'s first bypass.** `commits_in` passed `--no-merges` unconditionally.

    A merge commit's message is a commit message: it can carry an AI authorship trailer and it can
    omit `Task:`. With merges skipped, a push consisting only of a merge returned an empty list and
    the check exited **0 having read nothing** — in the half whose whole job is to catch what an
    uninstalled or bypassed hook missed.
    """
    monkeypatch.chdir(repository)
    base = run_git(repository, "rev-parse", "HEAD")
    run_git(repository, "checkout", "-q", "-b", "side")
    commit(repository, GOOD_MESSAGE, name="side.txt")
    run_git(repository, "checkout", "-q", "main")
    commit(repository, GOOD_MESSAGE, name="main.txt")
    run_git(repository, "merge", "--no-ff", "--no-verify", "-m", BAD_TRAILER, "side")
    head = run_git(repository, "rev-parse", "HEAD")

    assert head in check.commits_in(f"{base}..{head}"), "the merge is not even in the range"
    assert check.check_range(f"{base}..{head}") == 1, (
        "a merge commit carrying an AI authorship trailer passed the range check"
    )
    assert check.check_range(f"{base}..{head}", skip_merges=True) == 0, (
        "`skip_merges` is for the synthetic pull-request merge and must still skip one"
    )


def test_a_merge_only_range_is_not_silently_empty(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shape that returned `[]` and exited 0: a range whose only commit is a merge."""
    monkeypatch.chdir(repository)
    run_git(repository, "checkout", "-q", "-b", "side")
    commit(repository, GOOD_MESSAGE, name="side.txt")
    run_git(repository, "checkout", "-q", "main")
    before = run_git(repository, "rev-parse", "HEAD")
    run_git(repository, "merge", "--no-ff", "--no-verify", "-m", BAD_TRAILER, "side")
    head = run_git(repository, "rev-parse", "HEAD")

    merge_only = [
        sha
        for sha in check.commits_in(f"{before}..{head}")
        if sha != run_git(repository, "rev-parse", "side")
    ]
    assert merge_only, "the merge-only range is empty, which is the bypass itself"
    assert check.check_range(f"{before}..{head}") == 1


def test_a_bad_commit_that_is_not_the_tip_still_fails(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**`T240-R1`'s second bypass**, in the shape a new branch pushes.

    When `before` is unusable the workflow used to check `$head~1..$head` — the tip alone — while
    both it and the task claimed the *pushed range*. Every earlier commit in a new branch went
    unread. This is that range: three commits where the **first** is the bad one.
    """
    monkeypatch.chdir(repository)
    base = run_git(repository, "rev-parse", "HEAD")
    commit(repository, BAD_TRAILER, name="one.txt")
    commit(repository, GOOD_MESSAGE, name="two.txt")
    commit(repository, GOOD_MESSAGE, name="three.txt")
    head = run_git(repository, "rev-parse", "HEAD")

    assert check.check_range(f"{head}~1..{head}") == 0, (
        "the tip alone is clean — which is exactly why checking only the tip was the defect"
    )
    assert check.check_range(f"{base}..{head}") == 1, (
        "a bad commit below the tip passed a range that claims to cover what arrived"
    )


def test_a_clean_range_passes(repository: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The control. Without it every assertion above could pass by rejecting everything."""
    monkeypatch.chdir(repository)
    base = run_git(repository, "rev-parse", "HEAD")
    commit(repository, GOOD_MESSAGE, name="one.txt")
    commit(repository, GOOD_MESSAGE, name="two.txt")
    head = run_git(repository, "rev-parse", "HEAD")

    assert check.commits_in(f"{base}..{head}"), "the range is empty, so this proves nothing"
    assert check.check_range(f"{base}..{head}") == 0
