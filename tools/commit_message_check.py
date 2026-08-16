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
that arrives too late. **And when it knows it read less than the event brought** — a commit the
payload names and the clone lacks, the 2048-entry payload cap, a pull request base or head this
clone cannot resolve — **it fails rather than reporting coverage it does not have** (fourth round:
incomplete or discarded evidence must never be treated as successful coverage).

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
from collections.abc import Callable, Mapping, Sequence
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


def mapped(value: object) -> Mapping[str, object]:
    """`value` as a mapping, or an empty one.

    Event payloads are parsed JSON, so every nested field arrives typed `object`; reaching into
    `payload["pull_request"]["base"]["sha"]` through that needs either casts or this. Chosen over
    casts because a payload that *lies* — a string where GitHub documents an object — degrades to
    the same honest answer as a missing key, instead of an `AttributeError` inside the gate.
    """
    return value if isinstance(value, Mapping) else {}


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
    return check_commits(commits_in(revision_range), revision_range)


def check_commits(shas: Sequence[str], described_as: str) -> int:
    """Report on each commit in `shas`. Returns the process exit code.

    **Separate from the range that usually produces them** (`T240-R1`, third round), because there
    is one case where no range can be computed and the commits are known anyway: a force-push to
    the default branch, where the push payload's `commits` array is the only surviving description
    of what arrived.
    """
    failed = 0
    inspected = 0
    for sha in shas:
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
    print(f"{inspected} commit(s) checked in {described_as}")
    if failed:
        print(f"\n{failed} commit(s) break AGENTS.md §7/§13. See tools/commit_message_check.py.")
    return 1 if failed else 0


#: What `github.event.before` and `github.event.after` say when there was no such commit.
ZERO_SHA: Final = "0" * 40

#: How many commits a `push` payload's `commits` array carries at most.
#:
#: GitHub's own documented cap. It matters because it is the one thing the payload route cannot
#: promise: at exactly this many, the push may have brought more and the array is all there is.
#: `select_range` says so in its note rather than reporting a clean read of a truncated list.
MAX_PAYLOAD_COMMITS: Final = 2048


@dataclass(frozen=True, slots=True)
class Selection:
    """Which commits an event brought, and the sentence explaining how that was decided.

    Three answers, and they are deliberately different values:

    - `revisions` — a git range, which is the usual and the best answer, because git computes it
      from the history rather than from what an event happened to report.
    - `commits` — explicit SHAs out of the event payload, for the one case where **no range exists
      to compute**: a force-push to the default branch, where `origin/<default>` is already the
      pushed tip. `T240-R1`'s second round called those commits unknowable and fell back to
      reading the tip alone; a push payload carries a `commits` array, so they are not.
    - neither — the event brought nothing at all, which a branch deletion does. Distinct from *a
      range that resolved to nothing*, which is the bypass this whole finding is about.

    **And `incomplete`, which is the fourth round** (`T240-R1`, fourth instance). The third round
    dropped commits the clone lacks, annotated the 2048-entry cap in the note, and then let `main`
    exit 0 if the survivors were clean — *"did not inspect everything it claimed"*, one level
    outward, in the reviewer's words: **incomplete or discarded evidence treated as successful
    coverage**. When a selection *knows* it read less than the event brought, this field says why,
    and `main` fails the run after printing everything that was read. A note is for a reader; an
    exit code is for the gate, and only the second cannot be skimmed past.
    """

    revisions: str | None
    note: str
    commits: tuple[str, ...] = ()
    #: Why this selection covers less than the event brought, or `None` when it covers it all.
    incomplete: str | None = None


def tip_only(head: str, *, exists: Callable[[str], bool]) -> str:
    """The last resort: the pushed commit and nothing else.

    `head~1..head` is wrong for a repository's first commit, which has no parent — `git rev-parse`
    raises on it — so a root commit is named directly, which `rev-list` reads as *this and its
    ancestors*, and it has none.
    """
    return f"{head}~1..{head}" if exists(f"{head}~1") else head


def pushed_commits(
    payload: Mapping[str, object],
    head: str,
    why: str,
    *,
    exists: Callable[[str], bool],
) -> Selection:
    """What arrived when no range can describe it (`T240-R1`, third round).

    A force-push to the default branch leaves nothing to subtract from: `origin/<default>` **is**
    the commit that was just pushed, so every range that could be formed is empty. The second round
    read the tip alone and recorded the rest as unknowable — which was a claim about GitHub rather
    than about git, and it was wrong. The `push` payload carries a `commits` array describing the
    commits the push brought, and a probe with a malformed commit below a clean tip is exactly the
    shape it exists for: the tip passes, the commit under it does not, and only this route sees it.

    **Only the commits this clone actually has can be read — and the rest fail the run**
    (fourth round). The array describes what GitHub received; a commit missing from the checkout
    cannot have its message read, and the third round dropped those with a note and exited by the
    survivors alone. They are counted into `Selection.incomplete` now, as is the **2048-entry
    cap**: GitHub documents an API route for the commits beyond it, and it is deliberately not
    taken — this checker imports the standard library only and runs without a token, which is what
    lets it run with no setup step — so the honest alternative to retrieval is a failing report.
    **`distinct` is still honoured and is not a shortfall**: GitHub marks a commit already pushed
    elsewhere as `distinct: false`, and re-reading history that arrived on another branch is how a
    gate starts failing for commits nobody in this push wrote. Excluding those is a decision about
    scope, not a gap in coverage — **which cuts both ways** (fifth round): when *every* entry is
    excluded, the tip is not read either, because the tip is one of the commits the policy just
    ruled out of scope, and the fifth-round probe caught this branch doing exactly that.

    **The empty branches are the finding's fifth instance, so they are enumerated rather than
    fallen into.** `described` empty means the event offers no payload evidence at all, and the tip
    is genuinely all there is. `described` non-empty with `wanted` empty means everything the push
    carried was deliberately excluded — nothing new arrived, nothing is read, and that is a fact
    like a branch deletion, not a shortfall. **And `incomplete` survives every one of these
    returns**: the fifth-round probe was 2,048 `distinct: false` entries, where the cap shortfall
    was computed and then dropped by the one return that did not carry it — the run checked a tip
    the policy had excluded and exited 0.

    `why` is the caller's sentence for how it got here, because two callers arrive for different
    reasons: an empty determinable range, and a clone with no default branch to compare against.
    """
    listed = payload.get("commits")
    described = listed if isinstance(listed, list) else []
    wanted = [
        str(entry.get("id") or "")
        for entry in described
        if isinstance(entry, dict) and entry.get("distinct") is not False
    ]
    present = [sha for sha in wanted if sha and exists(sha)]
    missing = len(wanted) - len(present)
    shortfalls = []
    if missing:
        shortfalls.append(f"{missing} commit(s) the payload names are not in this clone")
    if len(described) >= MAX_PAYLOAD_COMMITS:
        shortfalls.append(
            f"the payload's commits array is at GitHub's {MAX_PAYLOAD_COMMITS}-entry cap, so the "
            "push may have brought commits nothing in this event describes"
        )
    incomplete = "; and ".join(shortfalls) if shortfalls else None
    excluded = [
        entry for entry in described if isinstance(entry, dict) and entry.get("distinct") is False
    ]
    if not wanted:
        if excluded:
            return Selection(
                None,
                f"{why}; every commit this push carried is marked distinct: false — each arrived "
                "on another branch already, and the exclusion that keeps them unjudged there "
                "keeps the tip unjudged here too",
                incomplete=incomplete,
            )
        return Selection(
            tip_only(head, exists=exists),
            f"{why}; checking the tip commit only",
            incomplete=incomplete,
        )
    if not present:
        return Selection(
            tip_only(head, exists=exists),
            f"{why}; the payload lists no commit this clone has, so checking the tip only",
            incomplete=incomplete,
        )
    truncated = (
        f", and GitHub caps that array at {MAX_PAYLOAD_COMMITS} so the push may have brought more"
        if len(described) >= MAX_PAYLOAD_COMMITS
        else ""
    )
    absent = f", {missing} of them not in this clone" if missing else ""
    return Selection(
        None,
        f"{why}; reading the {len(present)} commit(s) the payload lists{absent}{truncated}",
        tuple(present),
        incomplete=incomplete,
    )


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

    **And when the range is empty, the payload still knows.** The previous round fell back to the
    tip alone and called the rest unknowable; that was wrong, and stated as fact. A `push` payload
    carries a `commits` array describing the commits the push brought — GitHub sends up to
    **2048** of them — so a force-push to the default branch, where no range can be computed at
    all, is checked commit by commit out of the event itself. `MAX_PAYLOAD_COMMITS` is the one
    case where that is not the whole push, and it says so in the log rather than implying
    coverage it does not have.
    """
    counter = count if count is not None else (lambda revisions: len(commits_in(revisions)))

    if event in {"pull_request", "pull_request_target"}:
        request = mapped(payload.get("pull_request"))
        base = str(mapped(request.get("base")).get("sha") or "")
        head = str(mapped(request.get("head")).get("sha") or "")
        if head and exists(head) and base and exists(base):
            return Selection(f"{base}..{head}", f"pull request: {base[:7]}..{head[:7]}")
        if head and exists(head):
            return Selection(
                tip_only(head, exists=exists),
                f"pull request whose base {base[:7] or '(none)'} is not in this clone; "
                "checking the head commit only",
                incomplete=(
                    f"the pull request names base {base[:7] or '(none)'} and this clone cannot "
                    "resolve it, so everything below the head commit went unread"
                ),
            )
        return Selection(
            None,
            "pull request with no head commit in this clone; nothing can be read",
            incomplete=(
                f"the pull request names head {head[:7] or '(none)'} and this clone cannot "
                "resolve it, so nothing the pull request brings was read"
            ),
        )

    head = str(payload.get("after") or payload.get("head") or "")
    if not head or head == ZERO_SHA:
        return Selection(None, "the branch was deleted; nothing arrived")

    before = str(payload.get("before") or "")
    if before and before != ZERO_SHA and exists(before):
        return Selection(f"{before}..{head}", f"push: {before[:7]}..{head[:7]}")

    default = str(mapped(payload.get("repository")).get("default_branch") or "")
    if default and exists(f"origin/{default}"):
        candidate = f"origin/{default}..{head}"
        if counter(candidate) > 0:
            return Selection(
                candidate,
                f"no usable before-SHA; checking everything {head[:7]} adds over {default}",
            )
        return pushed_commits(
            payload,
            head,
            f"no usable before-SHA and {head[:7]} adds nothing to {default} — a force-push to "
            "the default branch, or a tag re-pushed at a commit already on it",
            exists=exists,
        )

    # No default branch this clone can compare against — a first push to an empty repository is
    # the case. The payload route works here too (fourth round): reading the tip alone while the
    # event lists what the push brought was this finding's class, one caller over.
    return pushed_commits(
        payload,
        head,
        "no usable before-SHA and no default branch this clone can compare against",
        exists=exists,
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
        if selection.commits:
            failed = check_commits(selection.commits, "the commits the push payload listed")
        elif selection.revisions is not None:
            failed = check_range(selection.revisions)
        else:
            failed = 0
        if selection.incomplete:
            # **A known shortfall is a failure, not a footnote** (`T240-R1`, fourth instance).
            # Everything readable was read and reported above; what this cannot do is call that
            # a complete check of the push, and an exit code is the one part of the report the
            # gate itself consumes.
            print(f"\nNOT FULLY CHECKED: {selection.incomplete}.")
            return failed or 1
        return failed

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
