# AGENTS.md — Tracks & Trails

**Purpose:** Define how AI agents must behave in this repository.
**Authority:** Canonical for agent behavior, roles, file ownership, and required validation.
**Owner:** Claude Code (Documentation Maintainer role).
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-26
**Last reviewed:** 2026-07-26
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

## 3. Roles

Capability roles are authoritative; the tool assignment below is the current convention
and may change without changing the roles.

| Tool | Capability roles |
|---|---|
| Claude Code | Planner, Implementer, Documentation Maintainer, Release Manager |
| Codex | Reviewer |

Review is a **distinct pass by a different agent**. An implementer does not sign off on
its own change in `ai/REVIEWS.md`.

## 4. File ownership

| Role | May update | Must not update without explicit instruction |
|---|---|---|
| Planner | `AGENTS.md`, `ai/REQUIREMENTS.md`, `ai/ARCHITECTURE.md`, `ai/DECISIONS.md`, `ai/IMPLEMENTATION_PLAN.md`, `ai/TASKS.md`, `ai/STATUS.md` | source, tests, `pyproject.toml`, build config |
| Implementer | `src/**`, `tests/**`, `pyproject.toml`, build config, `ai/TASKS.md`, `ai/STATUS.md`, `ai/TESTING.md` (to add a check the change introduces) | `ai/REQUIREMENTS.md`, `ai/ARCHITECTURE.md`, `ai/DECISIONS.md`, `ai/IMPLEMENTATION_PLAN.md` |
| Reviewer | `ai/REVIEWS.md`, `ai/TESTING.md`, test files, `ai/TASKS.md` (approved follow-ups only) | reviewed source code, unless asked to fix findings |
| Release Manager | version sources, `CHANGELOG.md`, release metadata, `ai/STATUS.md` | product scope, during release prep |
| Documentation Maintainer | `README.md`, `ai/PROMPTS.md`, cross-links, formatting | product or architecture *meaning* |

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
- This is an individual/personal project. Normal development stays on the
  maintainer-designated integration branch, `main`.
- Do **not** create or switch branches merely because a task, phase, development cycle,
  agent session, or review starts. Commits and exact base/head SHAs on `main` are sufficient
  review boundaries.
- A branch requires explicit maintainer instruction and a concrete need: isolated concurrent
  work, a risky experiment, a long-running release/hotfix/backport, an external contribution,
  or repository protection that prevents direct work on `main`.
- If a task begins on a non-`main` branch, do not switch, merge, rebase, or delete it without
  explicit instruction; report the branch in the handoff.
- Do **not** commit or push unless explicitly instructed.
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

## 9. Review convergence

**There is no cap on review passes.** Review continues until the verdict is **Approved** or
**Approved with follow-ups**. A blocking defect found on any round gets fixed in that round —
including one found late, and including one introduced by a correction.

This follows convention rev **2026-07-26.3**, which withdrew the Standard-profile review
budget. The change came from this project's experience: the cap was reached twice in one
session, and on both occasions the passes it would have prevented found real blocking defects —
a digest collision, a regression a correction had itself introduced, and two more that an
implementer verification turned up afterwards. A cap that stops before the defects do is not
buying convergence; it defers the same work to a later task with less context.

Convergence comes from **scope discipline**, not from counting passes:

- A focused re-review verifies the original blocking findings and checks the correction diff for
  regressions. It is not a new unbounded audit.
- Non-blocking findings become follow-up work with an owner and target task; they do not keep
  the reviewed task in review, and they do not reopen it.
- The absence of a cap is not licence to reopen settled ground. A finding that revisits a
  decision already recorded as settled needs new evidence, not a second opinion.

**If rounds stop converging — the same defect class recurring, or corrections generating fresh
blockers — that is a signal to change approach**, not to keep iterating. Say so, and put the
choice to the maintainer: split the task, revisit the design, or accept a documented risk.

Every finding records both **severity** and **Blocks approval: Yes | No**:

- Critical and High findings normally block.
- Medium findings block when they violate an acceptance criterion, required check, approved
  architecture invariant, security boundary, data-integrity rule, or observable correctness.
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
criterion/check, correction regression, or direct continuation showing an original blocker is
not resolved may block. Other new, pre-existing, adjacent, Low, or non-blocking Medium findings
become follow-up work and do not reopen the reviewed task.

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

## 10. End-of-task report

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

## 11. Where things go

| Fact | Canonical home |
|---|---|
| What the product must do | `ai/REQUIREMENTS.md` |
| How the system is designed | `ai/ARCHITECTURE.md` |
| Why a durable choice was made | `ai/DECISIONS.md` |
| Phase order and exit criteria | `ai/IMPLEMENTATION_PLAN.md` |
| Concrete actionable work | `ai/TASKS.md` |
| Where the project stands now | `ai/STATUS.md` |
| Review findings and evidence | `ai/REVIEWS.md` |
| Test policy and commands | `ai/TESTING.md` |

Do not copy a fact into a second authoritative-looking place. Link to the canonical home.

Create a `ai/DECISIONS.md` entry only for durable choices and real trade-offs — not as a
completion note for routine work. Routine fixes belong in `ai/TASKS.md` and `CHANGELOG.md`.

---

*Documentation system: AI-Assisted Project Documentation Convention, Standard profile.
Adopted at rev 2026-07-18.1 (`DOC-001`); §7's individual-project branch policy and §9's
review-convergence policy came from rev 2026-07-26.2, and §9's removal of the review budget
from rev **2026-07-26.3** — a convention change this project's experience prompted. No
deliberate deviations from the convention are in force. The convention document itself lives
outside this repository; this file is self-contained and does not depend on it.*
