# AGENTS.md — Tracks & Trails

**Purpose:** Define how AI agents must behave in this repository.
**Authority:** Canonical for agent behavior, roles, file ownership, and required validation.
**Owner:** Claude Code (Documentation Maintainer role).
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-25
**Last reviewed:** 2026-07-25
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
| Anything toward a tagged release or distributed build | the full suite + the release gate, regardless of size |

Never report a check as passing without having run it. Paste or summarize the real result.

## 9. End-of-task report

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

## 10. Where things go

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

*Documentation system: AI-Assisted Project Documentation Convention rev 2026-07-18.1,
Standard profile. See `DOC-001` in `ai/DECISIONS.md`. The convention document itself lives
outside this repository; this file is self-contained and does not depend on it.*
