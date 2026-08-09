# AGENTS.md — Tracks & Trails

**Purpose:** Define how AI agents must behave in this repository.
**Authority:** Canonical for agent behavior, roles, file ownership, and required validation.
**Owner:** Claude Code (Documentation Maintainer role).
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-27
**Last reviewed:** 2026-07-27
**Update when:** Agent responsibilities, roles, ownership, validation gates, or repository-wide rules change.
**Does not contain:** Product requirements, architecture detail, current progress, review history.

---

## 1. What this project is

Tracks & Trails is a cross-platform (Linux + Windows) desktop GUI front-end for
[yt-dlp](https://github.com/yt-dlp/yt-dlp). It is a general-purpose downloader —
video and audio are equal first-class citizens. Python + PySide6 (Qt 6).

## 2. Read before working

1. **This file.**
2. The exact active task entry in `ai/TASKS.md`.
3. The snapshot in `ai/STATUS.md`.
4. **Only** the requirement IDs, decision IDs, architecture sections, source paths,
   and tests that your task entry links to.

Do **not** read the whole repository for a narrow task. Long documents are indexed by
stable ID (`REQ-###`, `ARC-###`, `T-###`) — retrieve by ID or heading, not front-to-back.
A broad audit, migration, or release review may justify wider reading; ordinary work does not.

§9 (parallel work) applies only if the maintainer has told you that you are in a wave. Ordinary
work is serial; skip it.

## 3. Roles

Capability roles are authoritative; the tool assignment below is the current convention
and may change without changing the roles.

| Tool | Capability roles |
|---|---|
| Claude Code | Planner, Implementer, Documentation Maintainer, Release Manager, Coordinator / Integrator |
| Codex | Reviewer |

Review is a **distinct pass by a different agent**. An implementer does not sign off on
its own change in `ai/REVIEWS.md`.

**Coordinator / Integrator** exists only while a parallel wave is open (§9). Exactly one
agent or the maintainer holds it, and it does not implement a worker's task while also
reviewing it.

## 4. File ownership

| Role | May update | Must not update without explicit instruction |
|---|---|---|
| Planner | `AGENTS.md`, `ai/REQUIREMENTS.md`, `ai/ARCHITECTURE.md`, `ai/DECISIONS.md`, `ai/IMPLEMENTATION_PLAN.md`, `ai/TASKS.md`, `ai/STATUS.md` | source, tests, `pyproject.toml`, build config |
| Implementer | `src/**`, `tests/**`, `pyproject.toml`, build config, `ai/TASKS.md`, `ai/STATUS.md`, `ai/TESTING.md` (to add a check the change introduces) | `ai/REQUIREMENTS.md`, `ai/ARCHITECTURE.md`, `ai/DECISIONS.md`, `ai/IMPLEMENTATION_PLAN.md` |
| Reviewer | `ai/REVIEWS.md` (or the assigned `ai/reviews/T-0NN.md`), `ai/TESTING.md`, test files, `ai/TASKS.md` (approved follow-ups only) | reviewed source code, unless asked to fix findings |
| Release Manager | version sources, `CHANGELOG.md`, release metadata, `ai/STATUS.md` | product scope, during release prep |
| Documentation Maintainer | `README.md`, `ai/PROMPTS.md`, cross-links, formatting | product or architecture *meaning* |
| Coordinator / Integrator (wave only) | `ai/TASKS.md`, `ai/STATUS.md`, the `ai/REVIEWS.md` index and integration result, branches/worktrees the maintainer authorized | a reviewer's substantive findings; worker source outside conflict resolution |

**In a parallel wave the assigned exclusive write set overrides this table** (§9). A worker
writes only its own paths, proposes `ai/TASKS.md` / `ai/STATUS.md` changes instead of applying
them, and never edits another worker's surfaces or the reviewer's findings.

## 5. Authority order

When sources conflict, in order:

1. The user's direct current instruction.
2. `ai/REQUIREMENTS.md`
3. Accepted entries in `ai/DECISIONS.md`
4. `ai/ARCHITECTURE.md`
5. `ai/IMPLEMENTATION_PLAN.md`
6. `ai/TASKS.md`
7. `ai/STATUS.md`
8. Existing code
9. Generated documents
10. `ai/PROMPTS.md` (never authoritative)

**Code shows what happens; requirements state what should happen.** Do not silently treat
existing behavior as correct when it contradicts an approved requirement — report the
conflict and let it be resolved deliberately.

**Safety exception.** The user's instruction governs *direction and scope*. It does not
silently override: secret handling, destructive operations without confirmation, the
legal-scope exclusions in `REQ-EXCL` (`ai/REQUIREMENTS.md` §8), or a documented
non-negotiable invariant. If an instruction appears to require that, say so and ask.

## 6. Current truth vs. historical record

- **Current truth** (rewrite to reflect reality): `REQUIREMENTS.md`, `ARCHITECTURE.md`,
  `IMPLEMENTATION_PLAN.md`, `TASKS.md`, `STATUS.md`, `TESTING.md`
- **Historical record** (append; never silently rewrite): `DECISIONS.md`, `REVIEWS.md`,
  `CHANGELOG.md`, anything under `ai/archive/`
- **Convenience** (non-authoritative): `PROMPTS.md`, generated reports, AI summaries
- **Transient** (delete when spent): `ai/handoffs/`

### Handoffs are messages, not records

**A handoff is one agent talking to another.** It asks for a review, or carries a correction back.
**Once its verdict is recorded in `ai/REVIEWS.md`, it has done its job and is deleted.** Git history
keeps every one, retrievable by path, so nothing is lost by removing it from the working tree.

**Durable records cite commits, never handoffs.** A commit SHA identifies a tree that still exists;
a handoff filename identifies a message that is supposed to stop existing. If a record needs a fact
that appeared in a handoff — what was claimed, what a Planner recommended, what a submission got
wrong — **it states the fact.** Writing *"see `ai/handoffs/…`"* means the record has not recorded
the thing.

**This was a real defect, found 2026-08-09.** Sixty-four handoffs had accumulated in nine days, and
nine were cited from durable records. **Not one citation carried content** — every one was
provenance a SHA already supplied, a bare pointer, or a description of a past event. One cited a
handoff in order to say it was *not* part of the reviewed boundary. A durable record that delegates
its content to a file scheduled for deletion is a document whose truth lives somewhere it does not
control, which is the same failure as a stale current-truth claim.

**Historical records keep their references, and that is not an exception to the rule.** This section
binds **current-truth** files, which are rewritten to reflect reality. `REVIEWS.md` and
`DECISIONS.md` are append-only above, and *"a review was requested in `ai/handoffs/X`"* stays true
after `X` is deleted — it is a statement about the past, not a live pointer. **Rewriting them to
remove a reference would be the larger error.** So a deleted handoff may leave a name behind in
history; what it must not leave behind is a current-truth file that cannot answer its own question.

### The roadmap is a published artifact, never a repository file

**The maintainer keeps one roadmap, as a published artifact, for their own reference.** It is
**never committed** — no `roadmap*.html`, no `roadmap*.md`, nothing under `ai/` or `docs/`. Two
were removed from this repository on 2026-08-08 for that reason.

**It is derived, not authoritative.** `ai/IMPLEMENTATION_PLAN.md` §Phase *N* and `ai/TASKS.md`
§`## Proposed — Phase N` remain canonical; the roadmap is a rendering of them. **Where they
disagree, they are right and it is stale.** Nothing in the repository may cite it, for the reason
handoffs may not be cited: it is not a home.

**Update it — the same artifact, keeping its URL — when:**

- a phase exits or begins,
- a task's disposition changes in a way the phase's shape depends on (approved, blocked, re-phased,
  or newly filed),
- a ruling opens or closes.

**One artifact, updated in place.** Not one per phase: a bookmark that keeps working is the point,
and a graveyard of superseded roadmaps is the thing this rule replaces.

**What it contains**, in this order:

1. **A dependency graph** of the phase's tasks — real edges, not a decorative sequence. Label an
   edge where the *reason* for the dependency is not obvious from the two node names.
2. **The stages**, expanded: each task's one-line substance and the trap in it.
3. **Every plan deliverable mapped to an owning task**, and **every exit criterion mapped** too. A
   deliverable with no owner is the thing this section exists to surface.
4. **Which entries are *not* plan deliverables** — carried-in polish and defects. They must not be
   counted as satisfying one.
5. **Open rulings**, listed separately, each named as the maintainer's to take.

**Diagram legibility is part of the deliverable.** Mermaid in a rendered artifact does not honour
HTML in labels — `<br/>` and `<b>` are stripped, so `T-200<br/>Accessibility` renders as
`T-200Accessibility`. **Use single-line plain-text labels with a visible separator.** Mermaid also
scales an SVG down to its container by default, which shrinks text as the graph grows; set
`useMaxWidth: false` and let the container scroll.

## 7. Hard rules

**Scope**
- Implement the active task only. No unrelated cleanup, no future-phase work, no
  opportunistic refactors. If you find an adjacent problem, file a task; don't fix it inline.
- Do not change approved architecture or product scope. Propose; wait for approval.

**Dependencies**
- Adding, removing, or major-version-bumping a runtime dependency requires an accepted
  `ai/DECISIONS.md` entry. Dev-only tooling deps do not.
- Runtime dependency licenses must stay compatible with the project license (see `LIC-001`).
  PySide6 must remain **dynamically linked** (LGPL condition) — never statically bundle Qt.

**Layering** (enforced by test, see `ai/TESTING.md`)
- `src/tracks_and_trails/core/**` and `src/tracks_and_trails/downloader/worker.py`
  **must not import Qt** (`PySide6`, `shiboken6`). They run in headless child processes
  and must be testable without a display.
- `src/tracks_and_trails/ui/**` must not call yt-dlp directly. All yt-dlp access goes
  through the download manager (`ARC-002`).

**Git**
- This is an individual/personal project. The designated integration branch is `main`, and
  **serial work mode is the default**: one checkout, one writer, commits straight to `main`.
- Do **not** create or switch branches merely because a task, phase, development cycle,
  agent session, or review starts. Commits and exact base/head SHAs on `main` are sufficient
  review boundaries.
- A branch requires explicit maintainer instruction and a concrete need: an open parallel wave
  (§9), a risky experiment, a long-running release/hotfix/backport, an external contribution,
  or repository protection that prevents direct work on `main`.
- If a task begins on a non-`main` branch, do not switch, merge, rebase, or delete it without
  explicit instruction; report the branch in the handoff.
- Do **not** commit or push unless explicitly instructed.
- **One commit per task.** When a commit is instructed, each task gets its own — never one
  commit spanning several tasks, and never a session-sized batch. A commit whose message has
  to enumerate three unrelated tasks is one that cannot be reverted, reviewed, or bisected
  against any of them.
  - This holds even when the tasks were built in one sitting and share a working tree, which
    is the usual case in serial mode. Stage that task's files and commit before starting the
    next one.
  - **Coordination files are the exception that proves it.** `ai/TASKS.md`, `ai/STATUS.md`
    and `ai/IMPLEMENTATION_PLAN.md` accumulate interleaved edits from every task in flight, so
    a hunk-level split is often not clean. Put each task's own entry with that task where it
    separates; where it does not, say so in the commit message rather than silently batching.
  - If several tasks are already finished and uncommitted when the instruction arrives, split
    them retroactively — one commit each, in the order they were done.
- Do **not** name AI tools as commit authors or co-authors. No `Co-Authored-By:` trailers
  for AI tools, no "generated with" footers. Commit history names the human maintainer only.
- Never force-push, rewrite published history, or delete branches without confirmation.
- Never commit secrets, cookie files, browser profiles, or downloaded media.

**Uncertainty**
- Preserve uncertainty. Do not turn a guess into project truth. If a fact is unverified,
  label it unverified in the document that records it.
- Do not fabricate test results, version numbers, or verification dates.

## 8. Validation

`ai/TESTING.md` is authoritative. Default scope:

| Change | Required before "complete" |
|---|---|
| Docs only (`ai/`, `README.md`, comments) | none |
| Source change | `ruff check` + `ruff format --check` + `mypy src` + the tests relevant to the change |
| Change touching a platform-guarded module | the above **plus `mypy --platform win32`** — see below |
| Anything toward a tagged release or distributed build | the full suite + the release gate, regardless of size |

Never report a check as passing without having run it. Paste or summarize the real result.

**Run the checks, read each result, and only then commit.** Do not chain validation and
`git commit` into one shell command: the commit runs regardless of what the checks said, and
the failure is on screen while the push happens. This is not hypothetical — it shipped a
`mypy` failure and, separately, a commit missing its coordination-file updates.

**A host-only check is not the whole gate.** `mypy` is configured for the host platform, so on
Linux the bodies of Windows-guarded modules are proved unreachable and never analysed at all.
`mypy --platform win32` analyses them; `ai/TESTING.md` records which modules need it and why.
The same asymmetry applies to tests: a test that passes on Linux may encode a Linux assumption
(temp-path length, `PATHEXT`, `appauthor`), and only the Windows job can tell you.

## 9. Parallel work (opt-in)

**Skip this section unless the maintainer has told you that you are in a parallel wave.** It
describes an option, not an expectation: most work on this project is serial (§7), nothing here
requires a wave, and no task is worse for having been done one at a time.

A **parallel wave** is several agents implementing different tasks at the same time. Only the
maintainer opens one, per wave. An agent does not start one, create its branches, split a task
into workers, or propose a wave in place of doing the task in front of it. Two tasks merely
*being* independent is not a reason to run them concurrently — a wave adds base selection,
write-set assignment, serial integration, and combined verification, and that overhead only pays
off when the tasks are substantial as well as independent.

**A task may join a wave only if all of these hold.** Otherwise sequence it, or land the
shared piece first as its own task:

1. Its dependencies are already integrated at the wave's common base.
2. Its acceptance criteria can be checked without another worker's unfinished code.
3. Its write set does not overlap another active worker's.
4. The interfaces it depends on already exist — no two workers inventing the same seam.
5. `pyproject.toml`, migration sequence numbers, generated assets, and other single-owner
   surfaces are assigned to one worker or deferred to integration.
6. Its runtime resources are isolated (see below).

**Setup — coordinator.** Pick one stable `main` commit as the common base, assign a wave ID
`PW-###`, and per task: branch `task/T-0NN-slug`, its own worktree, exclusive write set,
read-only shared surfaces, runtime allocation, review-record path, integration order. Record
those as fields on the `ai/TASKS.md` entry. Do **not** record worktree paths there — they are
machine-specific; the branch and starting commit are the durable identifiers. Start a wave at
two or three workers, not more.

**One branch, one worktree, one writer.**

```bash
BASE="$(git rev-parse main)"
git worktree add -b task/T-042-<slug> ../tracks-and-trails-T-042 "$BASE"
```

Branches alone are not enough: two agents in one checkout share an index and working tree, and
switching a branch or editing the same file destroys the other's uncommitted work. That has
already happened here — a reviewer fell back to `git archive` mid-review because unrelated work
had entered the shared tree. The primary checkout stays on `main` for coordination.

**One worker per machine.** Separate worktrees are not enough either: **do not run concurrent
workers on one host**, even with disjoint write sets. A wave gets its parallelism by putting one
workstream on each machine, each with its own clone. Three reasons specific to this repository:

- **The integration tests that spawn and kill real worker processes contend** — the files are
  listed under *Runtime isolation* below. Two of those suites on one machine produce intermittent
  failures that look like defects in the code under test.
- **`.venv` is an editable install pointing at the primary checkout's `src`**, so a second worktree
  silently tests the *other* agent's code unless every command overrides `PYTHONPATH`. One worker
  per machine removes the trap rather than relying on remembering it.
- **A machine running a measurement is fully committed.** The `T-128` soak (`tools/soak.sh`) runs
  the whole suite sixty times and measures timing; any second workload invalidates it. So does a CI
  job — **a machine registered as a self-hosted runner is not idle**, and its runner service must be
  stopped for the duration or the contention recorded.

**Record which machine produced a measurement** in `ai/STATUS.md` or the evidence artifact:
reproducing a timing-dependent result requires knowing the host, and a baseline taken on one
machine does not transfer to another. Host names do not belong in a task entry's durable fields,
for the same reason worktree paths do not.

**Runtime isolation, specific to this repository.**

- `.venv` holds an **editable** install pointing at the primary checkout's `src`, so a second
  worktree silently tests the *other* agent's code. Override it:
  `PYTHONPATH=$PWD/src /path/to/primary/.venv/bin/python -m pytest` (and the same for `mypy`),
  then verify once with
  `python -c "import tracks_and_trails; print(tracks_and_trails.__file__)"`.
- **The integration tests that spawn and kill real worker processes** contend with each other:
  run them in one worktree at a time. They live in `tests/integration/` — `test_manager.py`,
  `test_crash_kill.py`, `test_single_instance.py`, `test_phase_2_exit.py`, `test_composition.py`
  and `test_worker.py`.
  *(This said "`-m process_tree` tests", and **no test carries that marker**: it was retired when
  `T-019` made cancellation reap the whole process group. So the instruction selected nothing and
  could not be followed. Naming the files is worse than a marker and better than a marker that
  does not exist; `T-123` owns identifying them properly, because parallelising the suite needs
  exactly that list.)*
- Qt tests need `QT_QPA_PLATFORM=offscreen`. Every worker's tests must use their own temp,
  database, and config paths — never a shared per-user application directory.

**Write sets are permissions, not predictions.** Needing an unassigned file — a shared module,
`pyproject.toml`, a migration, a generated asset — is a coordination event. Stop that part of
the change and report the scope expansion; do not edit it quietly.

**Shared coordination files are frozen for workers.** During a wave the coordinator is the only
writer of `ai/TASKS.md`, `ai/STATUS.md`, and the wave-level parts of `ai/REVIEWS.md`. Workers
propose those updates in the end-of-task report (§11).

**Review records are partitioned during a wave.** The assigned reviewer writes
`ai/reviews/T-0NN.md` directly, on the task branch, and `ai/REVIEWS.md` links to it as the
index rather than duplicating findings. Serial work continues to use the monolithic
`ai/REVIEWS.md`. Everything in §10 — severities, blocking rules, verdicts, the pass budget —
applies unchanged in either mode.

**Approval freezes one exact head.** Approval reads `Approved at <sha>` and covers that
implementation head only. A later commit may advance the branch if its diff is review-only
(the review record, review metadata). Any change to source, tests, build files, dependencies,
generated artifacts, or evidence creates a new implementation head and needs focused re-review
of the changed part before integration.

**Integration is serial.** The coordinator merges approved branches one at a time in dependency
order, resolves conflicts centrally, and runs the relevant checks after each step. A conflict
resolution that changes behavior is new implementation: keep it as a distinct diff and have it
reviewed, rather than burying it in a merge. Workers never merge or rebase a moving `main` into
themselves — that silently moves the review boundary.

**Verify the combined tree, not just the branches.** After the wave, run what `ai/TESTING.md`
§3 requires for the *union* of the layers touched. Branch-local green does not prove the merged
result works.

**Clean up last.** Remove worktrees and delete branches only after the integrated commit and
its evidence are secure, and never for a branch holding unique unintegrated work.

## 10. Review convergence

The review budget is **one initial comprehensive review plus one focused correction
re-review**. This cap applies when the remaining findings are **Medium or lower**. It does not
stop correction of **Critical or High** defects.

- An unresolved Critical or High finding remains in the current review until it is corrected and
  independently verified. Additional focused passes for those severities do not require
  maintainer authorization, even after the ordinary budget is exhausted.
- If the budget is exhausted and only blocking Medium-or-lower findings remain, stop the
  automatic agent-to-agent loop and ask the maintainer to choose: authorize another focused
  pass, accept the documented risk, change scope, or carry the work into a named follow-up task.
  A third pass for those findings requires explicit maintainer authorization.
- Non-blocking findings become follow-up work with an owner and target task; they do not consume
  another pass or keep the original task in review.

Every extra pass stays focused on unresolved blockers and the correction diff; it is not a new
broad audit. A finding that revisits settled ground needs new evidence, not a second opinion.
If High/Critical corrections repeatedly reproduce the same defect class or create fresh serious
defects, ask the maintainer to split the work or revisit the design, but do not approve the task
while the serious defect remains.

Every finding records both **severity** and **Blocks approval: Yes | No**.

Severity is anchored to **consequence if shipped**, not to how hard the fix looks — a one-line
fix for a data-loss defect is still Critical:

| Severity | Means |
|---|---|
| **Critical** | Shipping it causes harm the user cannot undo: data loss or corruption, a breached security or privacy boundary, exposed credentials or cookies, a defeated safety constraint, a licence violation. Also silent wrong results in what this product exists to do — downloading the wrong thing, or writing outside the directory the user chose. |
| **High** | Core or user-visible functionality the task exists to deliver is broken; a stated requirement or acceptance criterion is unmet; a documented architecture invariant is violated; or a user hits a defect with no workaround. |
| **Medium** | A correctness or robustness gap with a narrow trigger or a workaround — including a gate that does not actually gate what it claims to. |
| **Low** | Quality, clarity, maintainability; test strength where the behavior under test is correct. |
| **Note** | An observation. No action implied. |

- **A Critical finding always blocks. There is no "normally."** It is fixed before approval,
  however late it surfaces and however inconvenient the timing. It may **not** be closed as
  *Accepted Risk* or *Won't Fix* by an agent — only the maintainer can choose to ship known
  harm, and that belongs in `ai/DECISIONS.md` with its reasoning, not in a review table. Where
  it touches a safety constraint, §5's safety exception applies: report the conflict and ask,
  rather than complying silently.
- High findings block, especially when functionality is broken. Downgrading one needs a stated
  reason and explicit maintainer approval recorded with the finding.
- Medium findings block when they violate an acceptance criterion, required check, approved
  architecture invariant, security boundary, data-integrity rule, or observable correctness.
  After the ordinary pass budget, an unresolved blocking Medium finding produces **Blocked**
  pending the maintainer choice above; it does not authorize another pass by itself.
- Low and Note findings normally do not block.
- Mechanical documentation, status, cleanup, and test-hardening findings do not block unless
  they materially misstate safety, behavior, release readiness, or a required gate.

Use these verdicts:

| Verdict | Meaning |
|---|---|
| **Approved** | No open blocking findings remain. |
| **Approved with follow-ups** | No blocking findings remain; non-blocking findings have an owner and target task. |
| **Changes requested** | At least one blocking finding can be corrected in the current task. |
| **Blocked** | Approval requires a maintainer decision, external dependency, or scope change. |

The initial review should inspect the complete bounded change and report the full finding set
it can reasonably establish. Do not intentionally stop at the first defect and leave the
remaining changed surfaces for later rounds.

A focused re-review verifies the original blocking findings and checks the correction diff for
regressions; it is not a new unbounded audit. A new Critical or High defect, failed acceptance
criterion with High consequences, High correction regression, or direct continuation of a
Critical/High blocker continues through another focused correction and verification pass.
Medium-or-lower discoveries follow the pass budget above. Other new, pre-existing, adjacent,
Low, or non-blocking Medium findings become follow-up work and do not reopen the reviewed task.

Before returning a correction batch, the Implementer must:

- map every blocking finding to its code and test evidence;
- reproduce the defect with a failing test or deterministic probe when practical;
- mutation-check or otherwise demonstrate that weakening the correction makes the evidence
  fail;
- audit sibling fields, variants, and call paths when the finding represents a defect class;
  and
- address all in-scope blocking findings in one batch.

Only the Reviewer marks a finding **Resolved** after independent verification. The Implementer
records it as corrected and awaiting re-review. An Open non-blocking finding gets a `TASKS.md`
owner/target and does not keep the original task in `In Review`.

## 11. End-of-task report

Every task ends with:

1. Summary of what changed
2. Files modified
3. Checks run **and their actual results**
4. Assumptions made
5. Remaining risks / known-unverified areas
6. Blockers and follow-up work
7. Whether it is ready for review, and the **review base and head** (commit SHAs, or a
   clearly bounded uncommitted diff)
8. Which coordination files were updated

A worker in a parallel wave (§9) adds, and reports rather than applies:

9. Its wave ID, branch, and exact base/head
10. Runtime resources it used, and any still needing isolation
11. Write-set expansions it needed — granted or requested
12. **Proposed** `ai/TASKS.md` / `ai/STATUS.md` updates, for the coordinator to apply

## 12. Where things go

| Fact | Canonical home |
|---|---|
| What the product must do | `ai/REQUIREMENTS.md` |
| How the system is designed | `ai/ARCHITECTURE.md` |
| Why a durable choice was made | `ai/DECISIONS.md` |
| Phase order and exit criteria | `ai/IMPLEMENTATION_PLAN.md` |
| Concrete actionable work | `ai/TASKS.md` |
| Where the project stands now | `ai/STATUS.md` |
| Review findings and evidence | `ai/REVIEWS.md`; in a parallel wave, `ai/reviews/T-0NN.md` with `ai/REVIEWS.md` as the index |
| Test policy and commands | `ai/TESTING.md` |
| A review request or correction being sent | `ai/handoffs/` — **transient, deleted once its verdict is in `ai/REVIEWS.md`** (§6) |
| A visual roadmap of the current phase | **A published artifact, never a repository file** (§6). Derived from the plan and `TASKS.md`, which stay canonical |

Do not copy a fact into a second authoritative-looking place. Link to the canonical home.
**Never link to `ai/handoffs/`** — it is not a home, it is an outbox.

Create a `ai/DECISIONS.md` entry only for durable choices and real trade-offs — not as a
completion note for routine work. Routine fixes belong in `ai/TASKS.md` and `CHANGELOG.md`.

## 13. Commit messages

A commit message is read twice: once as a one-line subject while scanning history, and once in
full while investigating something that broke. The two readings want different things, and the
format below serves each separately rather than compromising between them.

### Shape

```
<subject, imperative, ≤50 chars, no trailing period>
<blank>
<why-paragraph: 1–3 sentences of reasoning that is not recoverable from the diff>
<blank>
- <one discrete change, wrapped at 72>
- <another>
<blank>
Task: T-0NN
```

### Subject — the only line most tools show

- **≤50 characters.** Hard cap 60. This is not stylistic: VSCode's Source Control pane, GitHub's
  commit list and `git log --oneline` in a split terminal all clip around 50, which is why
  history has looked "cut off" despite nothing being truncated in git itself.
- **Imperative mood** — "Add", "Close", "Record", "Fix". It completes the sentence *"Applied,
  this commit will…"*.
- **No trailing period.** No task ID, no `(T-0NN)` suffix, no `feat:`/`fix:` prefix.
- Say what changed in the product's own vocabulary, not the file's. "Bound stored geometry to
  Qt's maximum" beats "Update paths.py".

### Why-paragraph — the part that only you know

One to three sentences on **why**, or what the change means, or what it cost. The diff already
records what changed; it cannot record that a previous fix was itself wrong, or that a test was
passing vacuously, or that a design was chosen over a specific alternative. That is the content
worth keeping.

Skip it only when the subject is genuinely self-explanatory — a typo fix, a status-file pointer
update. A body that merely restates the subject in longer words is worse than no body.

### Bullets — one per discrete change

Bullets, not paragraphs, once there is more than one thing to report. Wrap at 72 columns so the
message stays readable under `git log`'s four-space indent.

**Budget: about 150 words, and at most ~8 bullets.** Past that, the commit is doing too much and
should have been split, or the detail belongs in `ai/TASKS.md` where it is indexed and editable.
A commit message is an immutable record, so it is the worst place to put anything that will need
revising.

### Trailers

Machine-readable, last, after a blank line:

| Trailer | Use |
|---|---|
| `Task:` | `T-0NN`, or `T-027..T-032` for a range. Omit only for work no task covers. |
| `Refs:` | Decision or requirement IDs the commit turns on — `ARC-002`, `REQ-011`. |
| `Review:` | Finding IDs closed by this commit — `T034-R5`, `T035-R3`. |

Look-ups stay easy: `git log --grep='Task:.*T-034'`.

**No AI tools as authors or co-authors** — §7 already governs this, and it applies to trailers
specifically. No `Co-Authored-By:` for an AI tool, no "generated with" footer. The commit history
names the human maintainer only.

### Worked example

Rewriting this repository's longest message (516 words, 8 unstructured paragraphs):

```
Close the Phase 0 exit review findings

Eight findings plus the four that survived the first re-review. The
theme running through them: stored window geometry was treated as
trusted input when it is not, and the first fix was itself incomplete
in a way its own test concealed.

- Bound coordinates to Qt's QWIDGETSIZE_MAX. Validating the four
  numbers individually missed that QRect derives right() as
  x + width - 1, so at y = 2**31 - 1 the bottom edge wrapped negative
  and off-screen recovery never fired.
- Reject bools, inf and nan in load_geometry, whose contract is that
  it never raises.
- Run T-020's frozen negative proof on Windows, not Linux alone.
- Schedule quit from showEvent so the harness never touches Qt from a
  foreign thread.

Task: T-027..T-032
Review: T027-R1..T032-R4
```

Same facts, a third of the words, and a reader looking for one finding can find it.

### Mechanics

`.gitmessage` at the repository root is the template; `git config commit.template .gitmessage`
activates it per clone (it is not set automatically by cloning).

Write the message in an editor or a file, not as a chain of `-m` flags — `-m` encourages
single-line messages and makes wrapping accidental.
