# AGENTS.md — Tracks & Trails

**Purpose:** Repository instructions, roles and write boundaries.
**Owner:** Documentation Maintainer · **Maintainer:** Sean Kottman
**Last updated:** 2026-09-08
**Update when:** Permissions, ownership or repository-wide workflow changes.

This file is self-contained with the canonical documents it links. `DOC-007` adopts
convention revision **2026-09-08.5**, Standard profile, for this desktop application.
The external web profile does not apply. Existing numbered sections remain stable;
the `tt-*` anchors give new references durable names.
The [adoption record](docs/project/DECISIONS.md#doc-007-review-migration) pins the shared
standard's repository and full commit. Routine work uses these local project rules.

<a id="tt-project"></a>

## 1. What this project is

Tracks & Trails is a Linux/Windows desktop GUI for yt-dlp, written in Python and
PySide6. Video and audio are equal first-class uses.

<a id="tt-context"></a>

## 2. Read before working

Read this file, the exact task in `docs/project/TASKS.md` (closed records are in
`docs/project/COMPLETED_TASKS.md`), the current
`docs/project/STATUS.md`, and the requirements, decisions, architecture, source
and tests relevant to that task. Retrieve long records by ID or heading.
Expand reading when the task or evidence requires it; broad audits may need more.
Read §9's extended procedure only for a maintainer-opened parallel wave.
Product users start with README; contributors use `docs/DEVELOPMENT.md`.

<a id="tt-roles"></a>

## 3. Roles

Capability roles are authoritative; the tool assignment below is the current convention
and may change without changing the roles.

| Tool | Capability roles |
|---|---|
| Claude Code | Planner, Implementer, Documentation Maintainer, Release Manager, Coordinator / Integrator |
| Codex | Reviewer |

Review is a **distinct pass by a different agent**. An implementer does not sign off on
its own change in any canonical review record.

**Coordinator / Integrator** exists only while a parallel wave is open (§9). Exactly one
agent or the maintainer holds it, and it does not implement a worker's task while also
reviewing it.

<a id="tt-ownership"></a>

## 4. File ownership

| Role | May update | Must not update without explicit instruction |
|---|---|---|
| Planner | `AGENTS.md`, `docs/project/REQUIREMENTS.md`, `docs/project/ARCHITECTURE.md`, `docs/project/DECISIONS.md`, `docs/project/IMPLEMENTATION_PLAN.md`, `docs/project/TASKS.md`, `docs/project/COMPLETED_TASKS.md`, `docs/project/STATUS.md` | source, tests, `pyproject.toml`, build config |
| Implementer | `src/**`, `tests/**`, `pyproject.toml`, build config, `docs/project/TASKS.md`, `docs/project/COMPLETED_TASKS.md`, `docs/project/STATUS.md`, `docs/project/TESTING.md` (to add a check the change introduces) | `docs/project/REQUIREMENTS.md`, `docs/project/ARCHITECTURE.md`, `docs/project/DECISIONS.md`, `docs/project/IMPLEMENTATION_PLAN.md` |
| Reviewer | the assigned canonical review record and its `docs/project/REVIEWS.md` index link (§10; coordinator owns the index in a wave), `docs/project/TESTING.md`, test files, `docs/project/TASKS.md` (approved follow-ups meeting §10's task threshold only) | reviewed source code, unless asked to fix findings |
| Release Manager | version sources, `CHANGELOG.md`, release metadata, `docs/project/STATUS.md` | product scope, during release prep |
| Documentation Maintainer | `README.md`, `docs/DEVELOPMENT.md`, `docs/project/PROMPTS.md`, current navigation/metadata, retention archives, cross-links, formatting; adopted documentation policy when instructed | product or architecture *meaning*; dated review findings |
| Coordinator / Integrator (wave only) | `docs/project/TASKS.md`, `docs/project/COMPLETED_TASKS.md`, `docs/project/STATUS.md`, the `docs/project/REVIEWS.md` index and assigned integration review record, branches/worktrees the maintainer authorized | a reviewer's substantive findings; worker source outside conflict resolution |

**In a parallel wave the assigned exclusive write set overrides this table** (§9). A worker
writes only its own paths and proposes TASKS, COMPLETED_TASKS and STATUS changes
instead of applying them. It never edits another worker's surfaces or the reviewer's findings.

<a id="tt-authority"></a>

## 5. Authority order

Resolve conflicts in this order: direct current user instruction; requirements;
accepted decisions including applicable amendments; architecture; implementation
plan; tasks; status; existing code; generated documents; prompts.
`docs/project/DECISIONS.md` indexes amendments; it does not replace the current
requirements or design. Code records actual behavior, not approval of that behavior.
Report conflicts rather than treating an implementation as its own justification.

User instructions govern direction and scope, but do not silently override secret
handling, confirmation for destructive operations, `REQ-EXCL` in REQUIREMENTS §8,
or a documented non-negotiable safety invariant. Report such a conflict and ask.

<a id="tt-history"></a>

## 6. Current truth vs. historical record

- Rewrite current requirements, architecture, plan, task queue, status and testing
  policy to reflect approved reality. Current indexes and metadata are editable.
- Preserve dated decisions, reviews, captured commands/output and archive records.
  Append amendments or superseding records; do not silently rewrite their meaning,
  path spellings, reviewer identity or evidence. Label mixed-file boundaries.
- Prompts and generated reports are convenience material, never policy.
- Handoffs are transient messages under ignored `docs/project/handoffs/`, or pasted
  text. Never commit them. Durable records state their facts and cite commits;
  they do not depend on a handoff. Historical mentions remain historical facts.
- The roadmap is one external published artifact, never a repository file or an
  authoritative source. Its owner, update triggers and contents are in
  [DEVELOPMENT](docs/DEVELOPMENT.md#roadmap-maintenance).

Before replacing content from an older revision, inspect intervening changes and
preserve the current content. Prefer a targeted inverse patch. A clean Git status
does not prove that committed work will survive. Mechanically compare protected
records after a move, restore or structural edit.

Keep maintained examples under normal checks. Protect captured historical blocks
with narrowly paired formatter controls outside their content, preserving their
bytes. Verify both preservation and continued checking of maintained examples;
[TESTING §4](docs/project/TESTING.md#captured-evidence-and-formatting) gives the exact controls.

At completion the serial task/status owner, or the wave coordinator, refreshes
the snapshot and removes duplicated session prose after preserving unique facts.
In the same update that marks a task Complete or Cancelled, move its full record
from `docs/project/TASKS.md` to the single running `docs/project/COMPLETED_TASKS.md`.
Keep only unfinished work in TASKS, with one link to the closed records and no
per-task stubs. Append future closures to the same file, without dated batches.
Preserve IDs, headings, evidence, limitations, attribution and follow-up routes;
update current links and task-reading checks. Required review/checks precede
closure; a move grants no approval. Cancelled remains Cancelled.

Both files share task/status ownership; in a wave only the coordinator performs
transfers. Check both when allocating IDs; never reuse an ID or keep two operative
entries for one. If work reopens, return its record to TASKS and preserve the prior
closure as dated history. The placement gate checks both files.

[Review storage](docs/project/TESTING.md#review-records-and-storage) defaults to
one file per reviewed task or shared scope, indexed in REVIEWS. Existing history
has moved to those indexed records; continue each scope there. Ownership and
approval rules apply in every location.

New prose explains behavior, causes, corrections, checks and remaining risk.
Comments explain constraints and invariants, with stable references for history.
Personal tool routing belongs in personal configuration; the accepted operational
mapping in §3 remains here. Preserve actual review provenance and necessary tool
adapters. Do not rewrite dated records to remove tool names or imply human review.

Use metadata proportional to the document. Purpose, owner and update trigger must
be discoverable. `Last updated` means edited; `Last reviewed` means a substantive
review of identified scope; `Last verified` names the checked revision/environment
and result. Formatting alone advances neither review nor verification dates.

<a id="tt-boundaries"></a>

## 7. Hard rules

**Scope:** Implement only the approved task. No adjacent fixes, future-phase work,
opportunistic refactors, or product/architecture changes without approval.
Disposition adjacent findings under §10 instead of automatically creating tasks.

**Dependencies:** Runtime additions, removals or major-version bumps require an
accepted decision. Dev-only dependencies do not. Licenses must remain compatible
(`LIC-001`); PySide6/Qt stays dynamically linked, never statically bundled.

**Layering:** `core/**` and `downloader/worker.py` must not import Qt (`PySide6`,
`shiboken6`). `ui/**` must not call yt-dlp directly; use the manager (`ARC-002`).
`docs/project/TESTING.md` owns the enforcement checks.

**Git:**
- Serial work on `main`, one checkout and one writer, is the default. Do not create
  or switch branches for ordinary tasks or reviews. A branch needs explicit
  maintainer instruction and a concrete isolation/collaboration/release need.
- If already on another branch, report it; do not switch, merge, rebase or delete
  it without instruction. Only the maintainer opens a parallel wave (§9).
- Commit when a task is complete: its required checks have run, their results
  have been read, coordination is updated, and it is ready for review. Never chain
  validation and commit in one shell command. Do not push without instruction.
- One commit per task. Stage only that task's files before starting another.
  Split already-finished tasks retroactively; where shared coordination hunks
  cannot separate cleanly, explain the overlap in the commit message.
- No AI authors/co-authors, `Co-Authored-By` trailers for tools, or generated-with
  footers. Commit identity names the human maintainer, without claiming unaided
  authorship. Actual review execution retains its provenance in the review.
- Never force-push, rewrite published history or delete branches without
  confirmation. Never commit secrets, cookie files, browser profiles or media.

**Uncertainty:** Label unverified claims. Never invent results, versions or dates.

<a id="tt-validation"></a>

## 8. Validation

[TESTING §3](docs/project/TESTING.md#3-required-checks-by-change-type) owns required
checks; §4 gives commands and §8 the release gate. Task-specific gates also apply.
Documentation-only edits need no application suite by default, but verify affected
links, literal evidence and documentation consumers. Source needs Ruff lint and
format checks, `mypy src`, and relevant tests. Platform-guarded changes also need
`mypy --platform win32`; test edits need bare `mypy` and its Windows-platform run.
Core/downloader/persistence changes and releases have broader gates in TESTING.
Read every result before committing and report actual failures as well as passes.
A Linux result does not establish Windows runtime behavior; host-only type checks
can skip Windows-guarded bodies entirely.

<a id="tt-parallel"></a>

## 9. Parallel work (opt-in)

Only the maintainer opens a wave, per wave. Do not delegate a task into workers or
create its branches without that instruction. Ordinary work stays serial.
Follow the complete [parallel procedure](docs/DEVELOPMENT.md#parallel-work-procedure):
common base; independent accepted tasks/interfaces; explicit write sets; one
branch, worktree and writer per task; **one worker per machine**; isolated runtime
resources; coordinator-only shared task/status updates; reviewer-owned records;
approval of an exact implementation head; serial integration and combined checks.
No branch cleanup until integrated work and evidence are secure.

<a id="tt-review"></a>

## 10. Review convergence

[TESTING §14](docs/project/TESTING.md#14-review-policy) is the canonical review
policy: independence, severity, blocking, pass budget, finding disposition and
correction evidence. Read it for review or correction work. Its task-creation
threshold also governs adjacent findings during implementation. Only an
independent Reviewer records resolution or approval; the implementer reports
correction and awaits verification. Canonical review records own dated evidence;
`REVIEWS.md` indexes them. TESTING §14 also owns storage and migration guidance.

<a id="tt-completion"></a>

## 11. End-of-task report

Report: (1) changes, (2) files, (3) checks and actual results, (4) assumptions,
(5) risks/unverified areas, (6) blockers/follow-up, (7) readiness plus exact review
base/head or a bounded uncommitted diff, (8) coordination updates.
Wave workers also report (9) wave/branch/base/head, (10) runtime resources,
(11) write-set expansions, (12) proposed task/status updates for the coordinator.
Apply §6's retention pass and update decision navigation when amendments change.
Read canonical finding rows before preparing a correction batch.

<a id="tt-routing"></a>

## 12. Where things go

| Subject | Canonical home |
|---|---|
| Product intent | `docs/project/REQUIREMENTS.md` |
| Design | `docs/project/ARCHITECTURE.md` |
| Durable choices and amendments | `docs/project/DECISIONS.md` |
| Phases and exit criteria | `docs/project/IMPLEMENTATION_PLAN.md` |
| Work queue | `docs/project/TASKS.md` |
| Completed and cancelled task records | `docs/project/COMPLETED_TASKS.md` |
| Current state | `docs/project/STATUS.md` |
| Review evidence | Canonical record indexed by `docs/project/REVIEWS.md`; storage in TESTING §14 |
| Testing and review policy | `docs/project/TESTING.md` |
| Contributor procedures | `docs/DEVELOPMENT.md` |
| Reusable launch wording | `docs/project/PROMPTS.md` (non-authoritative) |

Link to each canonical home. Decisions record durable choices, not routine
completion. Handoffs and the external roadmap are never canonical homes (§6).

<a id="tt-commits"></a>

## 13. Commit messages

Use an imperative subject of at most 50 characters (hard cap 60), no trailing
period, task-ID suffix or type prefix. Add a short why-paragraph when useful,
then discrete bullets wrapped at 72 columns; target 150 words and at most eight
bullets. Put `Task:`, relevant `Refs:` and `Review:` trailers last. No AI credits (§7).
Follow the [format and example](docs/DEVELOPMENT.md#commit-message-format).
Use `.gitmessage`; activate per clone with `git config commit.template .gitmessage`.
Write multiline messages in an editor or file, not a chain of `-m` arguments.
