"""Enforce the two commit-message rules `AGENTS.md` §7 and §13 state and nothing checked (`T-240`).

Two rules, and only two:

1. **No AI tool is named as an author or co-author** — no `Co-Authored-By:` for one, no
   *"generated with"* footer. §7. The history names the human maintainer only.
2. **A `Task:` trailer is present**, or the commit says explicitly that no task covers it. §13.

**Everything else in §13 is deliberately out of scope** — the subject's mood, its length, the
72-column wrap, the ~150-word budget. `T-240` says why: those are judgement, and a gate that argues
about prose is a gate people learn to skip. This one only ever fires on facts.

## Two entry points, and they prevent different things

    python3 tools/commit_message_check.py --message-file .git/COMMIT_EDITMSG
    python3 tools/commit_message_check.py --range <base>..<head>
    python3 tools/commit_message_check.py --event "$GITHUB_EVENT_PATH" --event-name "$..."

The **hook** form is what `.githooks/commit-msg` runs. It **prevents** the defect: the commit does
not exist yet, so there is nothing to amend and nothing to preserve. It can be skipped with
`--no-verify` and it does not exist in a fresh clone until the documented setup step installs it.

The **range** form checks exactly what it is given, and is what a person runs by hand.

The **event** form is what CI runs, and it works the range out itself — see `select_range`, which
is where `T240-R1`'s second round moved that decision from twenty lines of unreachable `bash`. It
cannot prevent anything — by then the history exists, which is precisely the state `T-065` had to
preserve rather than fix — so it **reports**. It is the half that cannot be forgotten, and the half
that arrives too late.

Both are wanted, and `T-240`'s entry asks for the difference to be stated rather than blurred.

## Why this exists at all

The rule has been broken twice by the same mechanism. `12dff92` reached `origin/main` and `T-065`
closed it by **preserving** the exception rather than rewriting published history. `fb41895`
carried the identical trailer thirteen days later and also omitted `Task:`; a reviewer caught it
before the push and it cost one amend.

**The standing criterion `T-065` left was not a mechanism.** It was a sentence in a closed task, and
the only thing enforcing it was somebody reading commit metadata. The tooling that writes these
messages appends the trailer by default, so the failure recurs by construction rather than by
carelessness — which is the argument for a gate rather than for more care.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

#: Names that mean *an AI tool wrote this*, matched case-insensitively anywhere in an authorship
#: trailer.
#:
#: **A list, and it will be incomplete.** The alternative — deciding whether an arbitrary name is a
#: person — is not something a gate can do, and one that guessed would eventually reject a human
#: contributor, which is a worse failure than missing a tool nobody here uses. These are the ones
#: whose tooling actually writes this trailer.
AI_AUTHOR_MARKERS = (
    "aider",
    "anthropic",
    "chatgpt",
    "claude",
    "codeium",
    "codex",
    "copilot",
    "cursor",
    "devin",
    "gemini",
    "gpt-",
    "openai",
    "sourcegraph",
    "tabnine",
    "windsurf",
)

#: Footers that credit a tool without using a trailer at all — the *"generated with"* shape §7
#: names alongside `Co-Authored-By:`.
GENERATED_WITH = re.compile(r"(generated\s+with|co-?authored\s+with|written\s+by\s+ai)", re.I)

AUTHOR_TRAILER = re.compile(r"^\s*(co-authored-by|author|signed-off-by)\s*:\s*(?P<who>.+)$", re.I)

#: `T-0NN`, a comma-separated list of them, or a `T-027..T-032` range — the forms §13 gives.
TASK_TRAILER = re.compile(r"^\s*Task:\s*(?P<value>.+?)\s*$")
TASK_VALUE = re.compile(r"^T-\d{3}(\.\.T-\d{3})?(\s*,\s*T-\d{3}(\.\.T-\d{3})?)*$")

#: The escape hatch §13 requires to survive: *"omit only for work no task covers"*.
#:
#: Spelled as a `Task:` value rather than a second trailer name, so that one grep finds both the
#: covered commits and the deliberate exceptions — and so that omitting the trailer entirely is
#: never the way to say this. **A reason is required.** Without one the exemption is indexed but
#: unexplained, which is the state `T-065`'s standing criterion was already in.
NO_TASK = re.compile(r"^none\b\s*[-—:]\s*(?P<reason>\S.*)$", re.I)

#: Commits that predate the gate and are **not** to be judged by it.
#:
#: `12dff92` is published history carrying an AI authorship trailer. `T-065` decided to preserve it
#: rather than rewrite it, `AGENTS.md` §7 forbids force-pushing without confirmation, and `T-240`'s
#: entry puts reopening that decision out of scope. A range check that walked over it would fail
#: every run for a reason nobody is allowed to fix — which is how a gate gets disabled.
GRANDFATHERED = frozenset({"12dff92"})


@dataclass(frozen=True, slots=True)
class Fault:
    """One rule broken, with the line that broke it so the report names it rather than the file."""

    rule: str
    detail: str
    line: str | None = None

    def __str__(self) -> str:
        where = f"\n      {self.line.strip()}" if self.line else ""
        return f"  {self.rule}: {self.detail}{where}"


def trailing_block(message: str) -> list[str]:
    """The message's trailer block — the last run of non-blank lines.

    Trailers are *"machine-readable, last, after a blank line"* (§13). Reading only that block is
    what lets a why-paragraph mention the word `Task:` without satisfying the rule, and lets a
    bullet quote a `Co-Authored-By:` line without breaking it.
    """
    lines = [line for line in message.splitlines() if not line.startswith("#")]
    while lines and not lines[-1].strip():
        lines.pop()
    block: list[str] = []
    for line in reversed(lines):
        if not line.strip():
            break
        block.append(line)
    return list(reversed(block))


def check_message(message: str) -> list[Fault]:
    """Every rule this gate owns, checked against one commit message."""
    faults: list[Fault] = []
    body = [line for line in message.splitlines() if not line.startswith("#")]

    # **The whole message, not the trailer block.** A "generated with" footer is not a trailer and
    # nothing says it will sit in the last paragraph.
    for line in body:
        if GENERATED_WITH.search(line):
            faults.append(Fault("§7", "names a tool as having written this commit", line))

    for line in body:
        match = AUTHOR_TRAILER.match(line)
        if match is None:
            continue
        who = match.group("who").lower()
        named = [marker for marker in AI_AUTHOR_MARKERS if marker in who]
        if named:
            faults.append(Fault("§7", f"names an AI tool as an author ({', '.join(named)})", line))

    trailers = trailing_block(message)
    tasks = [TASK_TRAILER.match(line) for line in trailers]
    found = [match for match in tasks if match is not None]
    if not found:
        faults.append(
            Fault(
                "§13",
                "no Task: trailer. Add `Task: T-0NN`, or `Task: none - <reason>` when no task "
                "covers the work",
            )
        )
    else:
        for match in found:
            value = match.group("value")
            if TASK_VALUE.match(value) or NO_TASK.match(value):
                continue
            faults.append(
                Fault(
                    "§13",
                    "Task: value is neither a task id (`T-0NN`, `T-027..T-032`) nor an "
                    "explained exemption (`none - <reason>`)",
                    match.group(0),
                )
            )
    return faults


def git(*arguments: str) -> str:
    """Run one git command and return its stdout.

    `shell` is left at its default `False`, which is what makes the argument list an argument list
    rather than a string a range could inject into — the same reasoning `ui/reveal.py` records for
    its own `S603`, and the reason the suppression is on this line with a sentence rather than in
    `per-file-ignores` where it would silently cover the next call somebody adds.
    """
    return subprocess.run(  # noqa: S603 - `shell` stays False, so argv is argv
        ["git", *arguments],  # noqa: S607 - the runner's git, as every hook and CI step uses
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def resolves(revision: str) -> bool:
    """Whether `revision` names a commit that exists in this clone.

    `github.event.before` is the shape this exists for: after a force-push it names a commit the
    remote no longer has, and a full-depth clone will not have fetched it either.
    """
    return (
        subprocess.run(  # noqa: S603 - `shell` stays False, as `git()` above records
            ["git", "cat-file", "-e", f"{revision}^{{commit}}"],  # noqa: S607 - the runner's git
            check=False,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )


def commits_in(revision_range: str) -> list[str]:
    """Every commit in `revision_range`, newest first.

    **Merges are included, and `--no-merges` was a real hole** (`T240-R1`). A merge commit's
    message is a commit message: it can carry an AI authorship trailer, and it can omit `Task:`.
    With `--no-merges` on, a push consisting only of a merge returned an empty list and the check
    exited 0 without reading anything — in the half whose entire job is to catch what an
    uninstalled or `--no-verify`-bypassed hook missed.

    **There is no `skip_merges` any more, and that is the second round of the same finding.** It
    was kept for one caller — a pull-request event, where GitHub synthesises a merge of the branch
    into its base and hands that SHA to the workflow — and `--no-merges` cannot express *that one
    merge*: it skips every merge in the range, including the ones a person wrote and can amend. The
    check's own test demonstrated it, passing a malformed real merge under the option. The synthetic
    merge is excluded by **not asking about it**: `select_range` takes the pull request's head
    commit rather than the merge GitHub built on top of it.
    """
    output = git("rev-list", revision_range).strip()
    return output.splitlines() if output else []


def check_range(revision_range: str) -> int:
    """Report on every commit in `revision_range`. Returns the process exit code."""
    failed = 0
    inspected = 0
    for sha in commits_in(revision_range):
        short = git("rev-parse", "--short", sha).strip()
        # Matched by prefix rather than by resolving the grandfathered ids to full SHAs: a CI clone
        # may not contain `12dff92` at all, and `git rev-parse` on a missing object raises.
        if any(sha.startswith(prefix) for prefix in GRANDFATHERED):
            print(f"{short}: skipped, grandfathered by T-065")
            continue
        inspected += 1
        faults = check_message(git("log", "-1", "--format=%B", sha))
        if faults:
            failed += 1
            subject = git("log", "-1", "--format=%s", sha).strip()
            print(f"\n{short} {subject}")
            for fault in faults:
                print(fault)
    # **Say how many were read, always.** A range that resolves to nothing exits 0 either way, and
    # the difference between *"every commit passed"* and *"no commit was looked at"* is the whole
    # of `T240-R1`. Printing the count is what makes a silent empty range visible in the log.
    print(f"{inspected} commit(s) checked in {revision_range}")
    if failed:
        print(f"\n{failed} commit(s) break AGENTS.md §7/§13. See tools/commit_message_check.py.")
    return 1 if failed else 0


#: What `github.event.before` and `github.event.after` say when there was no such commit.
ZERO_SHA: Final = "0" * 40


@dataclass(frozen=True, slots=True)
class Selection:
    """Which commits an event brought, and the sentence explaining how that was decided.

    `revisions` is `None` when the event brought nothing — a branch deletion is the case — which is
    different from *"a range that happens to be empty"* and has to stay different: the second was
    `T240-R1`'s second bypass, and it exited 0 having read nothing.
    """

    revisions: str | None
    note: str


def tip_only(head: str, *, exists: Callable[[str], bool]) -> str:
    """The last resort: the pushed commit and nothing else.

    `head~1..head` is wrong for a repository's first commit, which has no parent — `git rev-parse`
    raises on it — so a root commit is named directly, which `rev-list` reads as *this and its
    ancestors*, and it has none.
    """
    return f"{head}~1..{head}" if exists(f"{head}~1") else head


def select_range(
    event: str,
    payload: Mapping[str, object],
    *,
    exists: Callable[[str], bool] = resolves,
    count: Callable[[str], int] | None = None,
) -> Selection:
    """Work out which commits an event actually brought (`T240-R1`).

    **This used to be twenty lines of `bash` inside the workflow**, where no test could reach it —
    and the finding is specifically that its range selection was wrong in two ways nothing could
    have seen. It is Python now for that reason alone: the shell step passes the event through and
    reads the answer.

    The cases, in the order they are asked:

    - **A pull request** takes `pull_request.head.sha`, *not* `github.sha`. GitHub hands a workflow
      a merge of the branch into its base that nobody authored and nobody can amend, and the first
      correction dealt with that by passing `--no-merges` — which skipped every *authored* merge in
      the branch as well. Asking about the head commit excludes the synthetic merge because it is
      not in the range, and leaves every merge a person wrote where the check can see it.
    - **An ordinary push** takes `before..after`, merges included.
    - **A push whose `before` is unusable** — a new branch, a force-push, a re-pushed tag — takes
      everything the tip adds over the default branch. `origin/<default>..<tip>` is what *"what
      arrived"* means for a branch that did not exist before.
    - **Nothing arrived** on a branch deletion, and that is said rather than checked.

    **And then the range is counted**, because the case above has a hole the previous version fell
    into: force-push *to the default branch*, where `origin/<default>` is the tip that was just
    pushed and the range is empty by construction. An empty range exits 0 having read nothing,
    which is the whole of this finding. When the determinable range turns out to be empty the tip
    is checked instead, and the note says so.

    **Counted rather than reasoned about.** Asking *"was this pushed to the default branch?"*
    catches the force-push and misses the tag re-pushed at a commit already on `main`, which is the
    other way that range comes out empty and was named in the same breath as a case the fallback
    covered. Both guards were written; the second made the first unreachable, and a guard nothing
    can reach is a guard nobody can check. Measuring the range answers both, and answers the next
    one nobody thought of.
    """
    counter = count if count is not None else (lambda revisions: len(commits_in(revisions)))

    if event in {"pull_request", "pull_request_target"}:
        request = payload.get("pull_request") or {}
        base = str((request.get("base") or {}).get("sha") or "")
        head = str((request.get("head") or {}).get("sha") or "")
        if head and exists(head) and base and exists(base):
            return Selection(f"{base}..{head}", f"pull request: {base[:7]}..{head[:7]}")
        if head and exists(head):
            return Selection(
                tip_only(head, exists=exists),
                f"pull request whose base {base[:7] or '(none)'} is not in this clone; "
                "checking the head commit only",
            )
        return Selection(None, "pull request with no head commit in this clone; nothing to read")

    head = str(payload.get("after") or payload.get("head") or "")
    if not head or head == ZERO_SHA:
        return Selection(None, "the branch was deleted; nothing arrived")

    before = str(payload.get("before") or "")
    if before and before != ZERO_SHA and exists(before):
        return Selection(f"{before}..{head}", f"push: {before[:7]}..{head[:7]}")

    default = str(((payload.get("repository") or {}).get("default_branch")) or "")
    if default and exists(f"origin/{default}"):
        candidate = f"origin/{default}..{head}"
        if counter(candidate) > 0:
            return Selection(
                candidate,
                f"no usable before-SHA; checking everything {head[:7]} adds over {default}",
            )
        return Selection(
            tip_only(head, exists=exists),
            f"no usable before-SHA and {head[:7]} adds nothing to {default} — a force-push to the "
            "default branch, or a tag re-pushed at a commit already on it; checking the tip only",
        )

    return Selection(
        tip_only(head, exists=exists),
        "no before-SHA and no default branch to compare against; checking the tip commit only",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--message-file", help="a commit message file, as the commit-msg hook gets")
    source.add_argument("--range", dest="revisions", help="a git range, checked as given")
    source.add_argument(
        "--event",
        help=(
            "a GitHub event payload (`$GITHUB_EVENT_PATH`), from which the range is worked out. "
            "Requires --event-name."
        ),
    )
    parser.add_argument("--event-name", help="`$GITHUB_EVENT_NAME`, beside --event")
    arguments = parser.parse_args(argv)

    if arguments.event:
        if not arguments.event_name:
            parser.error("--event needs --event-name to know which shape the payload is")
        payload = json.loads(Path(arguments.event).read_text(encoding="utf-8"))
        selection = select_range(arguments.event_name, payload)
        print(f"range: {selection.note}")
        if selection.revisions is None:
            return 0
        return check_range(selection.revisions)

    if arguments.revisions:
        return check_range(arguments.revisions)

    faults = check_message(Path(arguments.message_file).read_text(encoding="utf-8"))
    if not faults:
        return 0
    print("This commit message breaks AGENTS.md:")
    for fault in faults:
        print(fault)
    print("\nNothing has been committed. Fix the message and commit again.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
