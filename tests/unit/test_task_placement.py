"""`ai/TASKS.md`'s navigation must agree with its own fields (`T-096`).

**Six review rounds found the same defect.** `COORD-R5` through `COORD-R10` each reported a task
whose `**Status:**` line said one thing while the `## ` section containing it said another, and each
was fixed by someone noticing. `COORD-R10` was the sixth, and it landed *inside* the correction
written to remove the fifth.

The seventh was produced by a tool rather than by inattention: a scripted edit replaced everything
between two headings in order to empty a section, and took the `## Ready` heading with it. Five
tasks each saying `Ready` sat under `## In Review` for two commits. Nothing failed.

So this is not a documentation nicety. It is the one mechanically enforceable half of a rule the
project has demonstrated it cannot keep by hand.

**What is enforced:** every live task entry states one operative status drawn from the vocabulary
`TASKS.md` itself declares, and sits under the section that status names. Prose after the status —
qualifiers, dates, review IDs, superseded readings — is free text and deliberately unconstrained.
"""

import re
from pathlib import Path

import pytest

TASKS = Path(__file__).resolve().parents[2] / "ai" / "TASKS.md"

#: The vocabulary `ai/TASKS.md` declares in its own header. Longest first, so `In Review` is matched
#: before any shorter term could claim its prefix.
VOCABULARY = (
    "In Progress",
    "In Review",
    "Cancelled",
    "Proposed",
    "Complete",
    "Blocked",
    "Ready",
)

#: Which operative statuses each section may contain.
#:
#: `## Ready` admits `In Progress` as well: a task being worked on is actionable work, and the file
#: has no separate section for it. Everything else is one-to-one.
#:
#: A section that is **not** listed here fails `test_every_section_is_mapped` rather than being
#: skipped — an unmapped section would silently exempt every task inside it, which is the failure
#: mode this whole file exists to prevent.
SECTION_ALLOWS: dict[str, frozenset[str]] = {
    "In Review": frozenset({"In Review"}),
    "Ready": frozenset({"Ready", "In Progress"}),
    "Blocked": frozenset({"Blocked"}),
    "Complete": frozenset({"Complete", "Cancelled"}),
}

#: `## Proposed — Phase 0`, `## Proposed — Phase 2`, … all admit `Proposed` only.
PROPOSED_PREFIX = "Proposed"


def allowed_for(section: str) -> frozenset[str] | None:
    """The statuses `section` may hold, or `None` if this file does not know the section."""
    if section.startswith(PROPOSED_PREFIX):
        return frozenset({"Proposed"})
    return SECTION_ALLOWS.get(section)


def operative_status(status_line: str) -> str | None:
    """The one vocabulary term `status_line` opens with, or `None` if it opens with none.

    Emphasis and code markers are stripped first, because the file's convention is
    `**Status:** **Complete — Approved at …**` and the asterisks are formatting rather than content.

    Matching a **prefix** rather than an exact field is what lets the existing prose survive
    unchanged: `Blocked on T033-R4 and the external Windows build` and
    `Blocked — until Phase 5 produces an installer` both state `Blocked` and are both legible.
    What it will not accept is a line that opens with something outside the vocabulary — which is
    exactly how `Approved at f858da9 — Complete` slipped past every human reading of this file.
    """
    body = re.sub(r"[*`]", "", status_line[len("**Status:**") :]).strip()
    return next((term for term in VOCABULARY if body.startswith(term)), None)


def live_entries() -> list[tuple[str, str, str]]:
    """`(task id, section, status line)` for every `### T-NNN` entry in the file.

    The status line is the **first** `**Status:**` under the heading. A second one inside an entry
    is caught by `test_each_entry_states_its_status_once` rather than silently ignored here.
    """
    section = ""
    task: str | None = None
    entries: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for line in TASKS.read_text(encoding="utf-8").split("\n"):
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        heading = re.match(r"### (T-\d+) — ", line)
        if heading:
            task = heading.group(1)
            continue
        if task is not None and task not in seen and line.startswith("**Status:**"):
            entries.append((task, section, line))
            seen.add(task)
    return entries


def test_the_file_has_entries_to_check() -> None:
    """Guards every assertion below against a parser that silently matched nothing."""
    entries = live_entries()
    assert len(entries) > 50, f"only {len(entries)} entries parsed; the format probably changed"


def test_every_section_is_mapped() -> None:
    """An unknown section would exempt every task inside it, which is this file's failure mode."""
    unmapped = {section for _, section, _ in live_entries() if allowed_for(section) is None}
    assert not unmapped, (
        f"{sorted(unmapped)} contain tasks but have no entry in SECTION_ALLOWS. Add the section "
        "deliberately — leaving it out silently exempts everything in it."
    )


def test_every_entry_states_a_status_from_the_vocabulary() -> None:
    """**No entry is skipped for being unparsable** — that is an acceptance criterion, not a detail.

    A status this cannot read is a status a reader cannot rely on either, and skipping it would
    reproduce the hole in a new place.
    """
    unreadable = [
        (task, line.strip()[:70])
        for task, _, line in live_entries()
        if operative_status(line) is None
    ]
    assert not unreadable, (
        "these entries do not open with a status from TASKS.md's declared vocabulary "
        f"{sorted(VOCABULARY)}: {unreadable}"
    )


def test_every_entry_sits_under_the_section_its_status_names() -> None:
    """`COORD-R5` … `COORD-R10`, mechanically. The whole point of this file."""
    wrong = []
    for task, section, line in live_entries():
        allowed = allowed_for(section)
        status = operative_status(line)
        if allowed is None or status is None:
            continue  # reported by the two tests above, with better messages
        if status not in allowed:
            wrong.append(f"{task} says {status!r} but sits under '## {section}'")
    assert not wrong, (
        "status and section disagree:\n  "
        + "\n  ".join(wrong)
        + "\nMove the entry, or correct its status — whichever matches the task's real disposition."
    )


def test_each_entry_states_its_status_once() -> None:
    """Two status lines in one entry means two answers, and `T033-R5` found exactly that."""
    section_pattern = re.compile(r"^## ")
    heading = re.compile(r"^### (T-\d+) — ")
    counts: dict[str, int] = {}
    task: str | None = None
    for line in TASKS.read_text(encoding="utf-8").split("\n"):
        if section_pattern.match(line):
            task = None
        found = heading.match(line)
        if found:
            task = found.group(1)
            counts[task] = 0
        elif task is not None and line.startswith("**Status:**"):
            counts[task] += 1
    repeated = {task: n for task, n in counts.items() if n > 1}
    assert not repeated, f"more than one Status line: {repeated}"


@pytest.mark.parametrize("term", VOCABULARY)
def test_the_vocabulary_matches_what_the_file_declares(term: str) -> None:
    """If `TASKS.md`'s own header changes, this file must be updated deliberately, not drift."""
    declared = next(
        line
        for line in TASKS.read_text(encoding="utf-8").split("\n")
        if line.startswith("Statuses:")
    )
    assert term in declared, f"{term!r} is enforced here but no longer declared in TASKS.md"
