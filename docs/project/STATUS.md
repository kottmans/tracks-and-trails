# STATUS.md — Tracks & Trails

**Purpose:** Current implementation state, immediate work and unresolved risks.
**Owner:** Planner / Implementer (Coordinator during a wave)
**Last updated:** 2026-09-10
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
- **Every task from the 2026-09-09/10 built-window sessions is Complete.** `T-308`, `T-310`,
  `T-312`, `T-314` closed 2026-09-10; `T-313`, `T-315`, `T-311`, `T-297`, `T-316`, `T-286` and
  `T-290` closed 2026-09-11, each approved by independent review and moved to
  [COMPLETED_TASKS](COMPLETED_TASKS.md). **Nothing is In Review.** `T-297` closed under a recorded
  amendment — which build the maintainer observed is not established, and its record says so.
- **Phase 4's exit review is Blocked at `6b1fcf1`** on three findings
  ([record](reviews/phase-4-exit.md)). Their states differ and the difference matters:
  - **`P4EXIT-R1` — corrected 2026-09-11.** The common audit's inventory omitted the queue's
    `FormatDialog` entirely and swept the staging *bodies* where `T-312` made the application show
    *pages*; the Windows UIA sweep covered three roles and never opened Settings or the add dialog.
    The inventory is nine surfaces, not five, and the Windows sweep covers the editing roles with
    both dialogs queried. **The reviewer's own mutation now fails four tests where it previously
    left all 103 passing.**

    **The widened audit immediately found a real defect, which is the point of widening it.** The
    collapse triangle at the top of every row panel — since `T-312` the *only* pointer route out
    of a panel that fills the dialog — changed **zero pixels on focus in both palettes**. Its rule
    said `border: none`, which out-specifies the `*:focus` catch-all, so a keyboard user landing
    there saw nothing at all. It now reserves a transparent edge for focus to recolour, which is
    `T-303`'s fix one control over, and it is enumerated in `BORDERED_CONTROLS` so the rendered
    per-control sweep covers it. Restoring the reviewed state fails the sweep in both palettes.
  - **`P4EXIT-R2` — not a queue, a machine.** `WINDOWS_RUNNER` pins `windows desktop` and
    `frozen windows` to `STARBASE`, and the API reports that runner **offline**; both jobs on
    `bca24bd` are queued behind it. `OPS-012` records that a self-hosted job with no matching
    online runner queues up to 24 hours before GitHub discards it. Bringing `STARBASE` online
    drains them; unsetting `WINDOWS_RUNNER` routes to hosted, which `OPS-010` says is why it was
    set. **Either way a fresh run is needed** — `R1`'s correction changes the test tree the
    evidence must cover.
  - **`P4EXIT-R3` — taken 2026-09-11.** The maintainer accepted the residual: Phase 4 may exit
    with `T-289`'s unexplained abort, bounded by the unchanged reopening condition. Recorded in
    that task's closed record and in the risk section below. **The crash is still not explained**,
    and the acceptance says so.
- **Phase 5 is planned.** Twelve tasks (`T-317`–`T-328`) plus a sharpened `T-106` tie every
  Phase 5 deliverable and exit criterion to an owner; see the task map in
  [IMPLEMENTATION_PLAN §Phase 5](IMPLEMENTATION_PLAN.md#phase-5--distribution). Three are
  maintainer rulings that gate the start: the Linux format, installer signing, and how a clean
  machine is evidenced.

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
- **Phase 4 exit work remains `T-297`, `T-286` and `T-290`, then the exit review.**
  `T-212`'s recorded checklist run **left this list on 2026-09-10** — the maintainer ran it
  informally, ruled that sufficient for closure, and moved the recorded run to Phase 5, where it
  happens against the artifact that ships. See each task for its actual status, dependencies and
  required evidence; listing it here grants no new implementation or desktop-session permission.

  **`T-297` is no longer Blocked.** The maintainer watched the pre-fix tree on their own display on
  2026-09-10 rather than capturing it, and reported no flicker. That **amends** criterion 1 rather
  than passing it — there is no capture, and which of the two open windows was observed could not
  be established — so the task carries the weaker claim and is In Review for the reviewer's
  disposition.

  **`T-286` was built on 2026-09-10** and is In Review: the container note now names the case
  recoding is for, not only what it costs.

  **`T-290` is Complete**, approved 2026-09-11 after one correction round. **Phase 4's exit work is
  the exit review, and nothing else** — every deliverable and every built-window finding is closed.

  **`T-238` is Complete**, closed 2026-09-11 on the maintainer's explicit no-action decision
  (`TESTING.md` §14). The crash was never reproduced; the guard is the outcome, criterion 4 is met
  as re-scoped, and a firing would reopen it. The Ready queue now holds no High.

- **The order after Phase 4 changed on 2026-09-10.** Phase 5 (distribution) runs next and
  **Phase 4.5 (option coverage) follows the first release** as a rolled-out update, by maintainer
  ruling: *"we really need to get this deployed."* Two consequences are recorded rather than
  assumed:

  - **`REQ-030`'s parity claim is unmet at release and must not be made.** Nothing user-facing may
    say this application reaches everything yt-dlp does until Phase 4.5 lands. `REQ-031`'s escape
    hatch (`T-184`) is what makes the gap survivable and is the first thing to schedule there.
  - **`T-106` is now on the critical path.** The `REL-` decision naming the Linux packaging format
    does not exist and must be accepted before the first build, because AppImage, Flatpak and
    system packages differ in how the application finds `ffmpeg` and where it may write.

  Phase 5 also needs **a real Windows desktop** for its manual verification session — the one item
  that cannot be satisfied from the current development environment, to be arranged before the
  phase starts rather than at its end. The Windows-only tasks `T-074`, `T-092`, `T-068` and `T-056`
  were reassigned there in the same ruling; none of them gated Phase 4.
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

- **T-289 is Complete under the 2026-09-04 re-scope, and Phase 4 may exit over it**
  — the reserved decision was taken by the maintainer on 2026-09-11 (`P4EXIT-R3`):
  **bounded acceptance**, on the implemented pool/ownership guards rather than on an
  explanation. **The 2026-08-27 abort remains unexplained and unreproduced**, and this
  record does not claim otherwise. A real-test guard firing reopens it and the
  acceptance lapses with it. Its task and review record preserve the reasoning and
  exact evidence.
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
