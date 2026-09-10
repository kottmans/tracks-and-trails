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

- **Five UI and settings defects found in the built window on 2026-09-09 are Complete**:
  `T-303` (a focused check box shifted its own text), `T-305` (*Unknown* where the table meant
  *none*), `T-306` (codec names, chosen rows, a demoted identifier column), `T-309` (a warning that
  claimed a read failure that had not happened), and `T-307`, **Cancelled** — a defect that did not
  exist, filed on a check that contradicted the specification it tested against.
- **`T-308` is the one still In Review.** Its three `T308-R1` clauses are observed on both
  platforms — synthetically on X11, and by the maintainer on Wayland — and `T308-R3`, a High
  regression in the correction's own probe, is corrected.

- **T-300 is Complete**, approved at `5eecad9` on 2026-09-08 by independent review and
  moved to [COMPLETED_TASKS](COMPLETED_TASKS.md). Its two Low findings were corrected
  during the completion sync and closed by maintainer ruling without a further review
  pass. [DOC-007](DECISIONS.md#doc-007-review-migration) pins the shared source, which
  **stays private** — its links in DECISIONS.md are now labelled as provenance rather
  than navigation. Existing review history lives in task/shared-scope files; REVIEWS.md
  is the index. Documentation work, not a Phase 4 deliverable.
- **T-299 is Complete**, approved at `7a45fc5` on 2026-09-08 after four review rounds;
  `R1`, `R2`, `R7` and `R8` are resolved and its record has moved to
  [COMPLETED_TASKS](COMPLETED_TASKS.md). **Publication itself is not done, and was never
  this task's to do.** **The repository was made public on 2026-09-08**, after the 18-commit
  push that first put this work on `origin/main`. The settings the task listed are set and
  verified: private vulnerability reporting enabled, Dependabot alerts enabled, fork-PR
  approval at `all_external_contributors`, Actions restricted to GitHub-owned actions, zero
  secrets configured, and the default workflow token read-only.
- Phase 4 exit work remains **T-297**, **T-286**, **T-290**, then **T-212**'s recorded
  48-row checklist run at one head and the exit review. See each task for its
  actual status, dependencies and required evidence; listing it here grants no
  new implementation or desktop-session permission.
- T-238 remains Ready with an unreproduced crash condition and incomplete product
  evidence. Existing blocked/platform work remains in the [task queue](TASKS.md).

- **No automatic orphan detection runs on either platform**, since 2026-09-08. `STARBASE orphans`
  was removed 2026-09-03; `Linux orphans` stopped when Linux CI moved to hosted runners, whose
  VMs do not outlive a run. `T-302` owns designing detection that survives that;
  `tools/orphan_scan.py` runs by hand meanwhile. Process lifecycle is the first item in
  TESTING §14's standing risk focus, so this is recorded as an open gap rather than a tidy-up.
- **Four UI tests fail one point above the default font** (`T-301`), found while repairing the two
  that `ubuntu-latest` broke. Contained test debt; reproduce with `tools/bigger_font_plugin.py`.

## Verification

After the shared-source/formatting follow-up, the Linux full suite passed with
**3940 passed / 21 skipped / 17 warnings** in **169.81 s**, using the activated
project environment. Ruff lint, whole-tree formatting, source/test type checks
(including Windows-platform bodies), preservation and formatter controls passed.
The previous format failure is resolved by controls outside the captured evidence;
the captured bytes are unchanged. Independent documentation review remains pending.

This follow-up's checks and review boundary are in
[T-300](COMPLETED_TASKS.md#t-300--agentsmd-is-628-lines-and-is-loaded-on-every-task).
The later review-storage adoption and historical migration have their own
documentation-check results in T-300. They preserve those earlier verification boundaries. No new Windows
execution or release-gate result is claimed here.

## Current risks and external blockers

- **T-289 is Complete under the 2026-09-04 re-scope.** The 2026-08-27 abort remains
  unexplained and unreproduced. A real-test guard firing reopens it; whether Phase 4
  may exit with that residual remains a maintainer decision. Its task and review
  record preserve the reasoning and exact evidence.
- T-297's product correction was assessed as sound, but its required capture and
  recorded evidence remain incomplete. Follow its dated scope ruling before any
  real-display work.
- GitHub repository settings were verified through the API at publication and are
  listed under T-299 above. Local workflow files still cannot prove them, so that
  remains a read-and-check step rather than anything a test covers. **Runner-group
  scope is not among them** — groups are an organisation feature and these are
  repository-level runners.
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
