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
import sys
from pathlib import Path
from types import ModuleType

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
