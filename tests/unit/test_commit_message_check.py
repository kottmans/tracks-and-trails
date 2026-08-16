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
import json
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


# --- which commits an event brought (T240-R1, second round) ------------------------------------
#
# **The range used to be chosen by twenty lines of `bash` inside the workflow**, where nothing
# could reach it — and the finding is that the choice was wrong in two ways. These drive
# `select_range` with the payload shapes GitHub actually sends, against real repositories, because
# both defects are about which commits are handed to the parser at all.

#: A commit that is not in any of these repositories, standing in for `github.event.before` after a
#: force-push: the remote no longer has it and a full-depth clone will not have fetched it.
GONE: Final = "b" * 40
ZERO: Final = "0" * 40


def push_payload(
    *, before: str, after: str, ref: str = "refs/heads/main", default: str = "main"
) -> dict[str, object]:
    """A `push` payload, with the four fields the selection reads."""
    return {
        "before": before,
        "after": after,
        "ref": ref,
        "repository": {"default_branch": default},
    }


def test_a_pull_request_reads_the_branch_rather_than_the_merge_github_built(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**`T240-R1`'s first bypass, in the shape that survived the first correction.**

    `--no-merges` was kept for pull requests, on the grounds that GitHub synthesises a merge of the
    branch into its base that nobody authored and nobody can amend. But `--no-merges` cannot say
    *that one merge*: it skips every merge in the range, and a branch that merged `main` back into
    itself carries an authored one whose message is as checkable as any other. The check's own test
    demonstrated it — a malformed real merge passing under the option.

    The synthetic merge is excluded by **not asking about it**. A pull request is read as
    `base.sha..head.sha`, and the head is the branch tip: GitHub's merge sits above it and is
    simply not in the range.
    """
    monkeypatch.chdir(repository)
    run_git(repository, "checkout", "-q", "-b", "side")
    commit(repository, GOOD_MESSAGE, name="side.txt")
    run_git(repository, "checkout", "-q", "main")
    commit(repository, GOOD_MESSAGE, name="main.txt")
    moved_base = run_git(repository, "rev-parse", "HEAD")
    run_git(repository, "checkout", "-q", "side")
    # The merge a person makes to catch their branch up, and can amend.
    run_git(repository, "merge", "--no-ff", "--no-verify", "-m", BAD_TRAILER, "main")
    head = run_git(repository, "rev-parse", "HEAD")
    # The merge GitHub builds on top and hands over as `github.sha`. Its message is nobody's.
    run_git(repository, "checkout", "-q", "main")
    run_git(repository, "merge", "--no-ff", "--no-verify", "-m", "Merge pull request #1", "side")
    synthetic = run_git(repository, "rev-parse", "HEAD")

    selection = check.select_range(
        "pull_request",
        {"pull_request": {"base": {"sha": moved_base}, "head": {"sha": head}}},
    )

    assert selection.revisions == f"{moved_base}..{head}", (
        f"a pull request is read as base..head and this is {selection.revisions!r} — reading "
        "github.sha instead is what put a commit nobody can amend inside the range"
    )
    read = check.commits_in(selection.revisions)
    assert synthetic not in read, "GitHub's synthetic merge is in the range and cannot be fixed"
    assert head in read, "the branch tip is not in the range, so the merge in it goes unread"
    assert check.check_range(selection.revisions) == 1, (
        "an authored merge carrying an AI authorship trailer passed a pull-request range — this "
        "is exactly what `--no-merges` was letting through"
    )


def test_a_force_push_reads_the_commits_the_payload_lists(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**`T240-R1`, third round.** The commits below the tip were never unknowable.

    The second round fell back to the tip alone here and recorded the rest as undeterminable —
    which was a claim about GitHub, not about git, and GitHub disagrees: a `push` payload carries a
    `commits` array describing what the push brought. The reviewer's probe is this test: a
    malformed commit **below** a clean tip, force-pushed to `main`, where checking the tip exits 0
    and reads past the defect.
    """
    monkeypatch.chdir(repository)
    bad = commit(repository, BAD_TRAILER, name="one.txt")
    middle = commit(repository, GOOD_MESSAGE, name="two.txt")
    head = commit(repository, GOOD_MESSAGE, name="three.txt")
    run_git(repository, "update-ref", "refs/remotes/origin/main", head)

    payload = push_payload(before=GONE, after=head)
    payload["commits"] = [{"id": bad, "distinct": True}, {"id": middle}, {"id": head}]
    selection = check.select_range("push", payload)

    assert check.check_range(f"{head}~1..{head}") == 0, (
        "the tip is clean — which is why reading it alone was the hole this closes"
    )
    assert selection.commits == (bad, middle, head), (
        f"the payload lists three commits and the selection took {selection.commits}"
    )
    assert selection.revisions is None, "a range was formed where the point is that none exists"
    assert check.check_commits(selection.commits, "probe") == 1, (
        "a malformed commit below a clean tip passed a force-push to the default branch"
    )


def test_a_commit_the_payload_lists_and_the_clone_lacks_fails_the_run(
    repository: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """**`T240-R1`, fourth instance.** Known-incomplete coverage is a failure, not a footnote.

    A commit that cannot be read cannot be judged — `git log` on a missing object raises, so an
    unreadable SHA would take the whole gate down with it. The third round dropped those, counted
    them **in the note**, and then exited 0 if the survivors were clean: the run *printed* "1 of
    them not in this clone" and *returned* success, which is the original "did not inspect
    everything it claimed" defect one level outward.

    **Every readable commit here is clean**, so the non-zero exit can only come from the shortfall
    itself — a test with a bad survivor would prove nothing about this rule.
    """
    monkeypatch.chdir(repository)
    first = commit(repository, GOOD_MESSAGE, name="one.txt")
    head = commit(repository, GOOD_MESSAGE, name="two.txt")
    run_git(repository, "update-ref", "refs/remotes/origin/main", head)

    payload = push_payload(before=GONE, after=head)
    payload["commits"] = [{"id": first}, {"id": "c" * 40}, {"id": head}]
    selection = check.select_range("push", payload)

    assert selection.commits == (first, head)
    assert "1 of them not in this clone" in selection.note, selection.note
    assert selection.incomplete, "the selection does not know it is incomplete"

    event = tmp_path / "event.json"
    event.write_text(json.dumps(payload), encoding="utf-8")
    assert check.main(["--event", str(event), "--event-name", "push"]) == 1, (
        "every readable commit is clean and the run still reported success over one it could "
        "not read"
    )


def test_a_commit_already_pushed_elsewhere_is_not_re_read(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`distinct: false` is GitHub saying *this one arrived on another branch*.

    Re-reading it is how a gate starts failing for commits nobody in this push wrote — and this
    repository has **278** commits predating the `Task:` requirement for it to find.
    """
    monkeypatch.chdir(repository)
    old = commit(repository, BAD_TRAILER, name="one.txt")
    head = commit(repository, GOOD_MESSAGE, name="two.txt")
    run_git(repository, "update-ref", "refs/remotes/origin/main", head)

    payload = push_payload(before=GONE, after=head)
    payload["commits"] = [{"id": old, "distinct": False}, {"id": head, "distinct": True}]
    selection = check.select_range("push", payload)

    assert selection.commits == (head,)
    assert check.check_commits(selection.commits, "probe") == 0


def test_a_truncated_payload_fails_rather_than_claiming_the_push(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GitHub caps `commits` at 2048, and a gate that read 2048 of 3000 must not report success.

    The fourth round is the second half of that sentence: the cap used to be a phrase in the note,
    and the run exited 0 around it. GitHub documents an API route for the commits beyond the cap;
    the checker is stdlib-only and tokenless by design, so the honest alternative to retrieval is
    `Selection.incomplete` — asserted here as the field `main` fails on, not as prose.

    Driven at the cap rather than with 2048 real commits: what is being asserted is the shortfall,
    and building three thousand commits to produce it would test `git commit`.
    """
    monkeypatch.chdir(repository)
    head = commit(repository, GOOD_MESSAGE, name="one.txt")
    run_git(repository, "update-ref", "refs/remotes/origin/main", head)

    payload = push_payload(before=GONE, after=head)
    payload["commits"] = [{"id": head}] * check.MAX_PAYLOAD_COMMITS
    selection = check.select_range("push", payload)

    assert f"caps that array at {check.MAX_PAYLOAD_COMMITS}" in selection.note, selection.note
    assert selection.incomplete and "cap" in selection.incomplete, (
        f"a payload at the cap does not mark itself incomplete: {selection.incomplete!r}"
    )


def test_a_complete_payload_with_clean_commits_still_passes(
    repository: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The control for the shortfall rule: complete coverage of clean commits exits 0.

    Without this, everything above could pass by failing every payload route — and it pins the
    boundary that matters: **excluding a `distinct: false` commit is a decision about scope, not a
    gap in coverage**, so it must not trip the incompleteness failure.
    """
    monkeypatch.chdir(repository)
    root = run_git(repository, "rev-parse", "HEAD")
    first = commit(repository, GOOD_MESSAGE, name="one.txt")
    head = commit(repository, GOOD_MESSAGE, name="two.txt")
    run_git(repository, "update-ref", "refs/remotes/origin/main", head)

    payload = push_payload(before=GONE, after=head)
    payload["commits"] = [{"id": root, "distinct": False}, {"id": first}, {"id": head}]
    selection = check.select_range("push", payload)

    assert selection.commits == (first, head)
    assert selection.incomplete is None, (
        f"a fully readable payload marked itself incomplete: {selection.incomplete!r}"
    )
    event = tmp_path / "event.json"
    event.write_text(json.dumps(payload), encoding="utf-8")
    assert check.main(["--event", str(event), "--event-name", "push"]) == 0


def test_a_pull_request_with_an_unresolvable_base_fails_rather_than_passing_its_tip(
    repository: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The same class, one caller over: a tip reading offered as coverage of a whole pull request.

    The fallback for a base this clone cannot resolve read the head commit alone and exited by
    what it found there — for an event whose entire meaning is *the commits between base and
    head*. The head is clean here, so the failure can only be the shortfall.
    """
    monkeypatch.chdir(repository)
    commit(repository, GOOD_MESSAGE, name="one.txt")
    head = commit(repository, GOOD_MESSAGE, name="two.txt")

    payload = {"pull_request": {"base": {"sha": GONE}, "head": {"sha": head}}}
    selection = check.select_range("pull_request", payload)
    assert selection.incomplete, "an unresolvable base did not mark the selection incomplete"

    event = tmp_path / "event.json"
    event.write_text(json.dumps(payload), encoding="utf-8")
    assert check.main(["--event", str(event), "--event-name", "pull_request"]) == 1


def test_a_pull_request_with_an_unresolvable_head_fails_rather_than_reading_nothing(
    repository: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A head this clone cannot resolve used to exit 0 having read nothing at all.

    That is this finding's original shape from round one — an empty reading reported as a pass —
    surviving in the one branch nothing had asked about.
    """
    monkeypatch.chdir(repository)
    base = run_git(repository, "rev-parse", "HEAD")

    payload = {"pull_request": {"base": {"sha": base}, "head": {"sha": GONE}}}
    selection = check.select_range("pull_request", payload)
    assert selection.incomplete, "an unresolvable head did not mark the selection incomplete"

    event = tmp_path / "event.json"
    event.write_text(json.dumps(payload), encoding="utf-8")
    assert check.main(["--event", str(event), "--event-name", "pull_request"]) == 1


def test_a_push_with_no_comparable_default_still_reads_the_payload(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The no-default fallback read the tip alone while the event listed what the push brought.

    A first push to an empty repository is the case: `origin/<default>` does not resolve, and the
    old last resort was the tip commit — with a malformed commit **below** a clean tip sailing
    through, exactly the force-push shape one caller over. The payload route works here too.
    """
    monkeypatch.chdir(repository)
    bad = commit(repository, BAD_TRAILER, name="one.txt")
    head = commit(repository, GOOD_MESSAGE, name="two.txt")
    # No origin/<default> ref exists in this fixture, so the default-branch route cannot fire.

    payload = push_payload(before=ZERO, after=head)
    payload["commits"] = [{"id": bad}, {"id": head}]
    selection = check.select_range("push", payload)

    assert selection.commits == (bad, head), (
        "with no default branch to compare against, the payload's commits went unread"
    )
    assert selection.incomplete is None
    assert check.check_commits(selection.commits, "probe") == 1, (
        "a malformed commit below a clean tip passed a push this clone cannot range"
    )


# --- the workflow's own lifecycle (T240-R2) -----------------------------------------------------


WORKFLOW: Final = TOOL.parents[1] / ".github" / "workflows" / "commit-messages.yml"


def test_a_later_push_cannot_cancel_the_run_holding_the_bad_commit() -> None:
    """**`T240-R2`.** The workflow could cancel the only run that had seen a malformed commit.

    `concurrency` grouped by ref with `cancel-in-progress: true`: push A is still being checked
    when push B lands on the same ref, B cancels A, and B's own `before..after` starts at A's head
    — so A's commits are read by nothing, ever. The reviewer probed it on a real repository:
    rc=1 for A's range, rc=0 for B's, and A's run cancelled.

    **Transcribed as text, the way the Windows menu gate pins its expectations**: this is the
    statement of what the wiring must be, not a copy of whatever it currently is, so restoring
    blanket cancellation fails here rather than waiting for two pushes to race on the runner.

    **The first version of this pin was itself the second instance.** It pinned `github.sha` and
    argued the SHA "never collides" — and a push SHA is not a unique run identifier: different ref
    updates can end at the same commit, and GitHub replaces a **pending** run in a full group even
    with `cancel-in-progress: false`, so a pin can enforce a defect as firmly as it enforces a fix.
    `github.run_id` is documented unique per run. Pull requests keep ref-grouped cancellation
    because a synchronize run's `base..head` covers every commit its cancelled predecessor would
    have read — the property the push side lacked.
    """
    # Comments stripped first, for the reason the colour sweep records: the explanation beside
    # the wiring quotes the defective pair, and a sweep that reads comments matches its own
    # explanation. The first run of this test did exactly that.
    text = "\n".join(
        line
        for line in WORKFLOW.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )
    assert (
        "group: commit-messages-${{ github.event_name == 'pull_request' && github.ref "
        "|| github.run_id }}" in text
    ), "push runs no longer get a collision-free concurrency group"
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in text, (
        "cancellation is no longer scoped to pull requests"
    )
    assert "cancel-in-progress: true" not in text, (
        "blanket cancellation is back, so a later push can cancel the only run that saw a bad "
        "commit"
    )
    assert "github.sha" not in text, (
        "a push SHA is back in the wiring, and a push SHA is not a unique run identifier: "
        "different ref updates can end at the same commit and collide in one group, where GitHub "
        "replaces a pending run even with cancel-in-progress: false — the reviewer's probe was "
        "three same-SHA ranges scoring 0, 1, 0 with only the middle holding the bad commit"
    )


def test_a_push_of_only_excluded_commits_reads_nothing_and_says_so(
    repository: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """**`T240-R1`, fifth instance, second half.** Exclusion cuts both ways.

    When every entry is `distinct: false`, the old branch checked the tip anyway — and the tip is
    one of the commits the exclusion policy had just ruled out of scope. Nothing new arrived, so
    nothing is read: a fact like a branch deletion, not a shortfall, and distinct from *no usable
    payload evidence*, where the tip genuinely is all there is.
    """
    monkeypatch.chdir(repository)
    head = commit(repository, BAD_TRAILER, name="one.txt")
    run_git(repository, "update-ref", "refs/remotes/origin/main", head)

    payload = push_payload(before=GONE, after=head)
    payload["commits"] = [{"id": head, "distinct": False}]
    selection = check.select_range("push", payload)

    assert selection.revisions is None and selection.commits == (), (
        "everything this push carried is excluded by policy, and something was selected anyway — "
        "re-reading the tip contradicts the exclusion that keeps these unjudged"
    )
    assert selection.incomplete is None, "a deliberate exclusion is scope, not a shortfall"
    event = tmp_path / "event.json"
    event.write_text(json.dumps(payload), encoding="utf-8")
    assert check.main(["--event", str(event), "--event-name", "push"]) == 0


def test_the_cap_shortfall_survives_a_payload_of_only_excluded_commits(
    repository: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """**`T240-R1`, fifth instance — the reviewer's exact probe.**

    2,048 `distinct: false` entries: the cap shortfall was computed, and the empty-wanted return
    dropped it — `Selection(commits=(), incomplete=None)`, exit 0, with the tip read against the
    exclusion policy. The cap is a shortfall **regardless of what the visible entries are**: at
    the cap, the array says nothing about what else the push brought, and the commits beyond it
    are exactly as unread as a commit the clone lacks.
    """
    monkeypatch.chdir(repository)
    head = commit(repository, GOOD_MESSAGE, name="one.txt")
    run_git(repository, "update-ref", "refs/remotes/origin/main", head)

    payload = push_payload(before=GONE, after=head)
    payload["commits"] = [{"id": "e" * 40, "distinct": False}] * check.MAX_PAYLOAD_COMMITS
    selection = check.select_range("push", payload)

    assert selection.incomplete and "cap" in selection.incomplete, (
        f"2,048 excluded entries dropped the cap shortfall: {selection.incomplete!r}"
    )
    event = tmp_path / "event.json"
    event.write_text(json.dumps(payload), encoding="utf-8")
    assert check.main(["--event", str(event), "--event-name", "push"]) == 1, (
        "the run exited 0 at the cap because every visible entry happened to be excluded"
    )


def test_a_force_push_to_the_default_branch_does_not_check_nothing(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**`T240-R1`'s second bypass, in the shape the first correction created.**

    The fallback for an unusable `before` was `origin/<default>..<tip>` — everything the tip adds
    over the default branch. That is right for a new branch and **empty by construction for the
    default branch itself**, where `origin/main` *is* the commit that was just pushed. A force-push
    to `main` therefore selected a range of nothing, and a range of nothing exits 0 having read
    nothing, which is the whole of this finding one level down.

    The tip is checked instead, and the note says which case it is. The tip is not everything that
    arrived — after a rewrite nothing can know that — but it is not nothing.
    """
    monkeypatch.chdir(repository)
    commit(repository, BAD_TRAILER, name="rewritten.txt")
    head = run_git(repository, "rev-parse", "HEAD")
    run_git(repository, "update-ref", "refs/remotes/origin/main", head)

    selection = check.select_range("push", push_payload(before=GONE, after=head))

    assert selection.revisions is not None, "a force-push to main selected nothing to read"
    assert check.commits_in(selection.revisions), (
        f"{selection.revisions!r} resolves to no commits at all, so the check would exit 0 having "
        "read nothing — the silent pass this finding is about"
    )
    assert check.check_range(selection.revisions) == 1, (
        "the rewritten tip carries an AI authorship trailer and the gate passed it"
    )
    assert "force-push" in selection.note or "tip" in selection.note, (
        f"the log line does not say the range is a fallback: {selection.note!r}"
    )


def test_a_new_branch_checks_everything_it_adds_to_the_default(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The case the fallback is *for*, with the bad commit deliberately below the tip.

    A new branch has no `before`, and checking `$head~1..$head` — the first version — read one
    commit of however many were pushed.
    """
    monkeypatch.chdir(repository)
    base = run_git(repository, "rev-parse", "HEAD")
    run_git(repository, "update-ref", "refs/remotes/origin/main", base)
    run_git(repository, "checkout", "-q", "-b", "side")
    commit(repository, BAD_TRAILER, name="one.txt")
    commit(repository, GOOD_MESSAGE, name="two.txt")
    commit(repository, GOOD_MESSAGE, name="three.txt")
    head = run_git(repository, "rev-parse", "HEAD")

    selection = check.select_range(
        "push", push_payload(before=ZERO, after=head, ref="refs/heads/side")
    )

    assert selection.revisions == f"origin/main..{head}"
    assert len(check.commits_in(selection.revisions)) == 3, (
        "the new branch's three commits are not all in the range that claims to be what arrived"
    )
    assert check.check_range(selection.revisions) == 1, (
        "a bad commit below the tip of a new branch went unread"
    )


def test_a_re_pushed_tag_that_adds_nothing_still_reads_a_commit(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other way the determinable range comes out empty, and the reason it is counted.

    A force-push to the default branch is caught by asking which ref was pushed. A **tag** pushed
    at a commit that is already on `main` is not: the ref is `refs/tags/...`, so the fallback
    computes `origin/main..<tag>` in good faith and gets nothing. Both were named as cases the
    fallback covers, and both resolved to a range of no commits — which exits 0 having read
    nothing. Counting the range before trusting it is what makes the second case behave like the
    first.
    """
    monkeypatch.chdir(repository)
    commit(repository, BAD_TRAILER, name="tagged.txt")
    head = run_git(repository, "rev-parse", "HEAD")
    run_git(repository, "update-ref", "refs/remotes/origin/main", head)
    run_git(repository, "tag", "v1.0")

    selection = check.select_range(
        "push", push_payload(before=ZERO, after=head, ref="refs/tags/v1.0")
    )

    assert check.commits_in(selection.revisions or ""), (
        f"{selection.revisions!r} resolves to no commits, so the gate reads nothing and passes"
    )
    assert check.check_range(selection.revisions or "") == 1


def test_an_ordinary_push_takes_before_to_after(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The common case, and the control for the two fallbacks above."""
    monkeypatch.chdir(repository)
    before = run_git(repository, "rev-parse", "HEAD")
    commit(repository, GOOD_MESSAGE, name="one.txt")
    commit(repository, BAD_TRAILER, name="two.txt")
    after = run_git(repository, "rev-parse", "HEAD")

    selection = check.select_range("push", push_payload(before=before, after=after))

    assert selection.revisions == f"{before}..{after}"
    assert check.check_range(selection.revisions) == 1


def test_a_deleted_branch_brought_nothing_and_says_so(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deleting a branch is a push whose `after` is all zeros. Nothing arrived; nothing is read.

    **This is the one empty result that is honest**, and it is a different value from *"a range
    that resolved to nothing"* precisely so the two cannot be confused: `revisions is None` says
    the event brought no commits, where an empty range says the question was asked badly.
    """
    monkeypatch.chdir(repository)
    head = run_git(repository, "rev-parse", "HEAD")

    selection = check.select_range("push", push_payload(before=head, after=ZERO))

    assert selection.revisions is None
    assert "deleted" in selection.note


def test_the_first_commit_in_a_repository_can_still_be_read(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A root commit has no parent, so `HEAD~1..HEAD` raises rather than resolving to it.

    The last-resort range names the commit itself, which `rev-list` reads as *this and its
    ancestors* — of which there are none.
    """
    monkeypatch.chdir(repository)
    root = run_git(repository, "rev-parse", "HEAD")

    selection = check.select_range("push", push_payload(before=ZERO, after=root, default=""))

    assert selection.revisions == root
    assert check.commits_in(selection.revisions) == [root]


def test_the_event_form_runs_the_selection_it_documents(
    repository: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """End to end, as the workflow invokes it: a payload file in, an exit code out.

    The workflow passes `$GITHUB_EVENT_PATH` and `$GITHUB_EVENT_NAME` and nothing else. If the two
    arguments and the payload keys did not line up, every test above would still pass and the gate
    would fail on the runner — which is the failure mode the `bash` version had no way to catch.
    """
    monkeypatch.chdir(repository)
    before = run_git(repository, "rev-parse", "HEAD")
    commit(repository, BAD_TRAILER, name="one.txt")
    after = run_git(repository, "rev-parse", "HEAD")
    payload = tmp_path / "event.json"
    payload.write_text(json.dumps(push_payload(before=before, after=after)), encoding="utf-8")

    assert check.main(["--event", str(payload), "--event-name", "push"]) == 1

    payload.write_text(json.dumps(push_payload(before=after, after=ZERO)), encoding="utf-8")
    assert check.main(["--event", str(payload), "--event-name", "push"]) == 0
