# STATUS.md — Tracks & Trails

**Purpose:** Current implementation state, immediate work and unresolved risks.
**Owner:** Planner / Implementer (Coordinator during a wave)
**Last updated:** 2026-09-08
**Update when:** Work, blockers, evidence or phase readiness changes.

## Current state

Tracks & Trails runs from source on Linux and Windows. Phases 0–3 have exited;
**Phase 4 (settings, polish and accessibility) remains in progress**. There is no
tagged release or installer. [README](../../README.md) describes available features;
the [implementation plan](IMPLEMENTATION_PLAN.md#phase-4--settings-polish-and-accessibility)
owns phase deliverables and exit criteria.

## Active work

- **T-300:** Convention revision 2026-09-08.5 adoption implemented; independent
  review pending. [DOC-007](DECISIONS.md#doc-007-review-storage) pins the private
  shared source. New reviews use task files; existing reviews and dated history
  stay in REVIEWS.md. TESTING §14 owns storage, and required working rules remain
  local. This is documentation work, not a Phase 4 deliverable.
- **T-299:** Changes requested in the [focused correction review](REVIEWS.md#2026-09-08--t-299-focused-correction-review)
  at `23c3d11`. R1 (High) still requires correction of SECURITY.md's credential and
  cookie-path assurances. R2 (Medium) still requires the captured evidence output
  to match its historical command. Both remain blocking. The review-policy path
  and README CI wording are updated by T-300; only a Reviewer may resolve findings.
- Phase 4 exit work remains **T-297**, **T-286**, **T-290**, then **T-212**'s recorded
  48-row checklist run at one head and the exit review. See each task for its
  actual status, dependencies and required evidence; listing it here grants no
  new implementation or desktop-session permission.
- T-238 remains Ready with an unreproduced crash condition and incomplete product
  evidence. Existing blocked/platform work remains in the [task queue](TASKS.md).

## Verification

After the shared-source/formatting follow-up, the Linux full suite passed with
**3940 passed / 21 skipped / 17 warnings** in **169.81 s**, using the activated
project environment. Ruff lint, whole-tree formatting, source/test type checks
(including Windows-platform bodies), preservation and formatter controls passed.
The previous format failure is resolved by controls outside the captured evidence;
the captured bytes are unchanged. Independent documentation review remains pending.

This follow-up's checks and review boundary are in
[T-300](TASKS.md#t-300--agentsmd-is-628-lines-and-is-loaded-on-every-task).
The later review-storage adoption has its own documentation-check results in
T-300 and preserves those earlier verification boundaries. No new Windows
execution or release-gate result is claimed here.

## Current risks and external blockers

- **T-289 is Complete under the 2026-09-04 re-scope.** The 2026-08-27 abort remains
  unexplained and unreproduced. A real-test guard firing reopens it; whether Phase 4
  may exit with that residual remains a maintainer decision. Its task and review
  record preserve the reasoning and exact evidence.
- T-297's product correction was assessed as sound, but its required capture and
  recorded evidence remain incomplete. Follow its dated scope ruling before any
  real-display work.
- GitHub repository settings (fork approvals, workflow access and runner-group
  scope) remain unverified before publication. Local workflow files cannot prove
  those settings. T-299 remains the publication preparation task.
- Historical CI reports and their platform limits remain historical evidence.
  Nothing in this snapshot claims all platforms passed at the current head.

## Retention

Refresh this snapshot at task completion; do not prepend session diaries. Preserve
unique decisions, measurements or findings in their canonical records, then link
them. Review size if this file grows beyond roughly 200–300 lines.

Move each Complete or Cancelled task from TASKS to the single running
COMPLETED_TASKS file in the closure update. Keep only unfinished work in TASKS;
do not leave closed-task stubs or create dated task archives.

The retired status snapshot's unique evidence is in the [task supplements](COMPLETED_TASKS.md#historical-evidence-supplements--2026-09-08),
linked from the relevant tasks. The full snapshot remains recoverable from
`d88e62e`; its source path and recovery command are recorded with the supplements.
