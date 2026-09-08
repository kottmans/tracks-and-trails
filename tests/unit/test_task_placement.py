"""Task placement and IDs agree across the active and closed records (`T-096`, `T-300`).

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

TASKS = Path(__file__).resolve().parents[2] / "docs" / "project" / "TASKS.md"
COMPLETED_TASKS = TASKS.with_name("COMPLETED_TASKS.md")
TASK_DOCUMENTS = (TASKS, COMPLETED_TASKS)
CLOSED_STATUSES = frozenset({"Complete", "Cancelled"})

#: The vocabulary `docs/project/TASKS.md` declares in its own header. Longest first, so `In Review`
#: is matched before any shorter term could claim its prefix.
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
    "Cancelled": frozenset({"Cancelled"}),
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


def record_lines(document: Path) -> list[tuple[int, str]]:
    """Markdown outside fenced examples/captured history, with physical line numbers."""
    lines = []
    fence = ""
    for number, line in enumerate(document.read_text(encoding="utf-8").split("\n"), start=1):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if marker:
            if not fence:
                fence = marker[1]
            elif (
                marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip()
            ):
                fence = ""
            continue
        if not fence:
            lines.append((number, line))
    assert not fence, f"{document.name} has an unclosed code fence that could hide task records"
    return lines


def live_entries(document: Path = TASKS) -> list[tuple[str, str, str]]:
    """`(task id, section, status line)` for every `### T-NNN` entry in the file.

    The status line is the **first** `**Status:**` under the heading. A second one inside an entry
    is caught by `test_each_entry_states_its_status_once` rather than silently ignored here.
    """
    section = ""
    task: str | None = None
    entries: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for _, line in record_lines(document):
        if line.startswith("## "):
            section = line[3:].strip()
            task = None
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
    """Guards every assertion below against a parser that silently matched nothing.

    **All three parsers, not just the first** (`T-261`). `heading_occurrences()` is the only one
    that can report a duplicate, and it is also the only one whose failure mode is an empty list
    that satisfies a uniqueness assertion perfectly. A gate that proves *"no ID appears twice"*
    over nothing at all is the exact shape `T-096` exists for.
    """
    # The active queue may legitimately become empty; this project's retained history may not.
    assert sum(len(live_entries(path)) for path in TASK_DOCUMENTS) > 50
    for document in TASK_DOCUMENTS:
        headings = status_line_counts(document)
        occurrences = heading_occurrences(document)
        broad = [line for _, line in record_lines(document) if re.match(r"^### T-\d+\b", line)]
        assert len(occurrences) == len(broad), f"{document.name}: malformed task heading"
        assert len(occurrences) >= len(headings), (
            f"{document.name}: {len(occurrences)} headings against {len(headings)} unique IDs; "
            "the occurrence scan cannot see fewer than the collapsing one"
        )


@pytest.mark.parametrize("document", TASK_DOCUMENTS, ids=lambda path: path.name)
def test_every_section_is_mapped(document: Path) -> None:
    """An unknown section would exempt every task inside it, which is this file's failure mode."""
    unmapped = {section for _, section, _ in live_entries(document) if allowed_for(section) is None}
    assert not unmapped, (
        f"{sorted(unmapped)} contain tasks but have no entry in SECTION_ALLOWS. Add the section "
        "deliberately — leaving it out silently exempts everything in it."
    )


@pytest.mark.parametrize("document", TASK_DOCUMENTS, ids=lambda path: path.name)
def test_every_entry_states_a_status_from_the_vocabulary(document: Path) -> None:
    """**No entry is skipped for being unparsable** — that is an acceptance criterion, not a detail.

    A status this cannot read is a status a reader cannot rely on either, and skipping it would
    reproduce the hole in a new place.
    """
    unreadable = [
        (task, line.strip()[:70])
        for task, _, line in live_entries(document)
        if operative_status(line) is None
    ]
    assert not unreadable, (
        "these entries do not open with a status from TASKS.md's declared vocabulary "
        f"{sorted(VOCABULARY)}: {unreadable}"
    )


@pytest.mark.parametrize("document", TASK_DOCUMENTS, ids=lambda path: path.name)
def test_every_entry_sits_under_the_section_its_status_names(document: Path) -> None:
    """`COORD-R5` … `COORD-R10`, mechanically. The whole point of this file."""
    wrong = []
    for task, section, line in live_entries(document):
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


def heading_occurrences(document: Path = TASKS) -> list[tuple[str, int, str]]:
    """Every `### T-NNN` heading in file order, as `(task id, 1-based line, section)`.

    **A list, and that is the entire point** (`T-261`, from `COORD-R23`). `live_entries()` keeps a
    `seen` set and `status_line_counts()` writes into a dictionary keyed by task id, so both
    *collapse* a second heading for the same task into the first. `e61152d` had to remove a second
    copy of `T-256`, `T-259` and `T-257` from current truth, and **all fourteen checks in this file
    were green the whole time they existed** — each one asked its question of a set that had
    already discarded the evidence.

    So this reports occurrences rather than tasks, and nothing here deduplicates. It is a third
    parse rather than a flag on either existing one, because a parser that must both collapse and
    not collapse is a parser one refactor away from doing neither.
    """
    heading = re.compile(r"^### (T-\d+) — ")
    section = ""
    found: list[tuple[str, int, str]] = []
    for number, line in record_lines(document):
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        match = heading.match(line)
        if match:
            found.append((match.group(1), number, section))
    return found


def status_line_counts(document: Path = TASKS) -> dict[str, int]:
    """How many `**Status:**` lines each `### T-NNN` heading owns.

    Counted from the **headings**, not from the status lines, which is the difference `T096-R1`
    turned on: `live_entries()` can only report entries that have a status, so an entry with none
    is invisible to it. This sees every heading whether or not it states anything.
    """
    heading = re.compile(r"^### (T-\d+) — ")
    counts: dict[str, int] = {}
    task: str | None = None
    for _, line in record_lines(document):
        if line.startswith("## "):
            task = None
        found = heading.match(line)
        if found:
            task = found.group(1)
            counts[task] = 0
        elif task is not None and line.startswith("**Status:**"):
            counts[task] += 1
    return counts


@pytest.mark.parametrize("document", TASK_DOCUMENTS, ids=lambda path: path.name)
def test_every_entry_states_a_status_at_all(document: Path) -> None:
    """**A missing status is invisible to every other test in this file** (`T096-R1`).

    They all walk `live_entries()`, which pairs a heading with the status line under it — so an
    entry with no status line contributes nothing and every assertion passes over it. Deleting one
    left all twelve tests green, which is the same shape as the deleted section heading `T-096` was
    written for: the check ran, found nothing, and reported success.
    """
    missing = sorted(task for task, count in status_line_counts(document).items() if count == 0)
    assert not missing, (
        f"{missing} have no **Status:** line. Every other test here pairs a heading with its "
        "status, so an entry without one is skipped rather than reported."
    )


@pytest.mark.parametrize("document", TASK_DOCUMENTS, ids=lambda path: path.name)
def test_each_entry_states_its_status_once(document: Path) -> None:
    """Two status lines in one entry means two answers, and `T033-R5` found exactly that."""
    repeated = {task: n for task, n in status_line_counts(document).items() if n > 1}
    assert not repeated, f"more than one Status line: {repeated}"


@pytest.mark.parametrize("document", TASK_DOCUMENTS, ids=lambda path: path.name)
def test_every_heading_is_paired_with_an_entry(document: Path) -> None:
    """The two parses agree, so neither can drift into seeing a different set of tasks.

    `live_entries()` walks status lines and `status_line_counts()` walks headings. If they ever
    disagree about which tasks exist, one of them is wrong and every assertion built on it is
    unreliable — this is what says so rather than letting the smaller set quietly win.
    """
    from_status = {task for task, _, _ in live_entries(document)}
    from_headings = set(status_line_counts(document))
    assert from_status == from_headings, (
        f"headings without a parsed entry: {sorted(from_headings - from_status)}; "
        f"entries without a heading: {sorted(from_status - from_headings)}"
    )


@pytest.mark.parametrize("term", VOCABULARY)
def test_the_vocabulary_matches_what_the_file_declares(term: str) -> None:
    """If `TASKS.md`'s own header changes, this file must be updated deliberately, not drift."""
    declared = next(
        line
        for line in TASKS.read_text(encoding="utf-8").split("\n")
        if line.startswith("Statuses:")
    )
    assert term in declared, f"{term!r} is enforced here but no longer declared in TASKS.md"


def test_no_task_id_has_two_entries() -> None:
    """One task, one entry — the invariant every other test in this file assumes (`T-261`).

    **`COORD-R23` is why this is not covered by what was already here.** `e61152d` removed a
    duplicated `T-256`, `T-259` and `T-257`; while the copies were in the file, the placement gate
    was green, because `live_entries()` and `status_line_counts()` both key by task id and the
    second copy landed on top of the first. **The copies were also perfectly well-formed** — same
    section, same valid status line — so no other assertion here had anything to object to.

    A duplicate is not cosmetic. `docs/project/TASKS.md` is current truth, and two entries for one
    task are two answers to *"what is its status"* that can drift apart independently, which is the
    class `AGENTS.md` §6 is written against. This is the only check that can see one.
    """
    positions: dict[str, list[tuple[str, int, str]]] = {}
    for document in TASK_DOCUMENTS:
        for task, line, section in heading_occurrences(document):
            positions.setdefault(task, []).append((document.name, line, section))

    duplicated = {task: where for task, where in positions.items() if len(where) > 1}

    assert not duplicated, (
        "these task ids have more than one `### T-NNN` entry: "
        + "; ".join(
            f"{task} at "
            + ", ".join(f"{path}:{line} under `## {section}`" for path, line, section in where)
            for task, where in sorted(duplicated.items())
        )
        + ".\nKeep one operative entry per task across TASKS.md and COMPLETED_TASKS.md. Keep the "
        "one that is right and delete the other — the rest of this file cannot see the difference, "
        "because both of its other parsers key by task id and collapse the copies."
    )


def test_closed_tasks_are_in_the_closed_record_only() -> None:
    wrong = []
    for document in TASK_DOCUMENTS:
        for task, _, line in live_entries(document):
            status = operative_status(line)
            if status is None:
                continue  # vocabulary check supplies the diagnostic
            if (status in CLOSED_STATUSES) != (document == COMPLETED_TASKS):
                wrong.append(f"{task}: {status} in {document.name}")
    assert not wrong, "task in the wrong file: " + "; ".join(wrong)


@pytest.fixture
def task_documents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Small catalogs let controls exercise the actual repository gates."""
    active = tmp_path / "TASKS.md"
    closed = tmp_path / "COMPLETED_TASKS.md"
    active.write_text("## Ready\n\n### T-901 — Pending\n\n**Status:** Ready\n", encoding="utf-8")
    closed.write_text(
        "## Complete\n\n### T-902 — Finished\n\n**Status:** Complete\n", encoding="utf-8"
    )
    monkeypatch.setitem(globals(), "TASKS", active)
    monkeypatch.setitem(globals(), "COMPLETED_TASKS", closed)
    monkeypatch.setitem(globals(), "TASK_DOCUMENTS", (active, closed))
    return active, closed


@pytest.mark.parametrize("status", ["Complete", "Cancelled"])
def test_closing_without_transferring_is_rejected(
    task_documents: tuple[Path, Path], status: str
) -> None:
    active, _ = task_documents
    active.write_text(
        f"## Complete\n\n### T-901 — Pending\n\n**Status:** {status}\n", encoding="utf-8"
    )
    with pytest.raises(AssertionError, match=r"T-901.*TASKS\.md"):
        test_closed_tasks_are_in_the_closed_record_only()


def test_unfinished_work_in_the_closed_record_is_rejected(
    task_documents: tuple[Path, Path],
) -> None:
    _, closed = task_documents
    closed.write_text(
        "## In Review\n\n### T-902 — Finished\n\n**Status:** In Review\n", encoding="utf-8"
    )
    with pytest.raises(AssertionError, match=r"T-902.*COMPLETED_TASKS\.md"):
        test_closed_tasks_are_in_the_closed_record_only()


@pytest.mark.parametrize("other_file", [True, False], ids=["across-files", "within-completed"])
def test_duplicate_closed_records_are_rejected(
    task_documents: tuple[Path, Path], other_file: bool
) -> None:
    active, closed = task_documents
    target = active if other_file else closed
    with target.open("a", encoding="utf-8") as out:
        out.write("\n## Complete\n\n### T-902 — Copy\n\n**Status:** Complete\n")
    with pytest.raises(AssertionError, match="T-902"):
        test_no_task_id_has_two_entries()


def test_a_closed_record_without_status_is_rejected(task_documents: tuple[Path, Path]) -> None:
    _, closed = task_documents
    closed.write_text("## Complete\n\n### T-902 — Finished\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="T-902"):
        test_every_entry_states_a_status_at_all(closed)


def test_quoted_history_does_not_create_an_operative_task(
    task_documents: tuple[Path, Path],
) -> None:
    _, closed = task_documents
    with closed.open("a", encoding="utf-8") as out:
        out.write(
            "\n## Historical context\n\n````text\n### T-901 — Old brief\n**Status:** Ready\n````\n"
        )
        out.write("\n## Cancelled\n\n### T-903 — Withdrawn\n\n**Status:** Cancelled\n")
    assert [task for task, _, _ in live_entries(closed)] == ["T-902", "T-903"]
    assert [task for task, _, _ in heading_occurrences(closed)] == ["T-902", "T-903"]
    assert status_line_counts(closed) == {"T-902": 1, "T-903": 1}
    test_closed_tasks_are_in_the_closed_record_only()
    test_no_task_id_has_two_entries()


def test_an_unclosed_fence_cannot_silently_hide_tasks(task_documents: tuple[Path, Path]) -> None:
    _, closed = task_documents
    closed.write_text("````text\n### T-902 — Finished\n**Status:** Complete\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="unclosed code fence"):
        live_entries(closed)
