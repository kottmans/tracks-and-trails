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
- **`P4EXIT-R2`'s evidence exists.** CI run
  [`34653977245`](https://github.com/kottmans/tracks-and-trails/actions/runs/34653977245) at
  **`59598de`** is green on every job — `windows desktop` and `frozen windows` **natively on
  `STARBASE`**, alongside `linux`, `frozen linux` and the coverage reporter. The Windows desktop
  suite is **37 passed in 92.28 s** and the full Windows suite **4,152 passed / 36 skipped in
  36:22**. `59598de` is a later head than `2ea1aa6` carrying every correction, which is what `R2`'s
  route asks for. **Phase 4's exit now waits on the reviewer verifying that and signing off**, not
  on more work.

  **Recorded with it, because it is a finding rather than a detail:** the `windows desktop` job used
  **97% of its 40-minute bound** (38.9 min), and the job's own `T-259` warning fires at 85%. It has
  now reported 98%, 98% and 97% on three consecutive heads. **Nothing is wrong today and the next
  test added tips it into timeouts** — a bound crossed by growth, which wants a re-measurement
  rather than a bigger number.

- **The exit review was Blocked on `P4EXIT-R2` alone** as of the authorized fourth focused pass at
  `2ea1aa6` ([record](reviews/phase-4-exit.md)). `R1`, `R3` and `R4` are **Resolved**.
  **What remained was not a review**: `R2` asked for native Windows execution at the corrected tree,
  and no pass could supply it — the run above did. The maintainer authorized the third and fourth passes on 2026-09-11,
  which `TESTING` §14 requires once only blocking Medium findings remain. Their states differ and
  the difference matters:
  - **`P4EXIT-R1` — Resolved 2026-09-11** at `2ea1aa6`, by the fourth pass. The common audit's
    inventory omitted the queue's
    `FormatDialog` entirely and swept the staging *bodies* where `T-312` made the application show
    *pages*; the Windows UIA sweep covered three roles and never opened Settings or the add dialog.
    The inventory is nine surfaces, not five, and the Windows sweep covers the editing roles with
    both dialogs queried. **The reviewer's own mutation now fails two tests where it previously
    left all 103 passing** — the published-name and keyboard-route checks. *(This said four, which
    was wrong: removing a control's focusability also removes it from the rendered-focus sweep, so
    that sweep is not an oracle for the removed keyboard route. Two, measured independently by the
    reviewer in two separate passes and reproduced here.)*

    **The widened audit immediately found a real defect, which is the point of widening it.** The
    collapse triangle at the top of every row panel — since `T-312` the return control above the
    body of a panel that fills the dialog, and the first thing Tab reaches on it — changed **zero
    pixels on focus in both palettes**. Its rule
    said `border: none`, which out-specifies the `*:focus` catch-all, so a keyboard user landing
    there saw nothing at all. It now reserves a transparent edge for focus to recolour, which is
    `T-303`'s fix one control over, and it is enumerated in `BORDERED_CONTROLS` so the rendered
    per-control sweep covers it. Restoring the reviewed state fails the sweep in both palettes.

    **The re-review verified that and returned three more requirements, corrected 2026-09-11.**
    The Windows tests were taking a bare `MainWindow` with no composition, so `open_settings()`
    answered `None` and `open_add_dialog()` raised — all three failed *before* UI Automation was
    ever called. They take `composed` now, the same fixture `every_surface` and fourteen other
    Linux cases drive. **Measured the way the reviewer measured it**: replaying the committed
    bodies on Linux with only the UIA provider replaced reaches the query **16 times**, against
    the **zero** recorded at the previous head. A fourth test sweeps all thirteen surfaces of the
    shared inventory — Options, `PresetManager`, the queue's `FormatDialog` and the three editing
    panels had no Windows query at all, and a comment pointed at the Linux audit in place of one.
    Its floor is derived rather than listed: a surface with a Tab-reachable widget in Qt must
    publish at least one operable control.

    **The purpose-versus-value check is now provable on this platform.** It compared a combo's
    name against every `ListItem` in the tree, required none to exist, and tied none to a
    particular combo — so a tree holding one combo named `Best video available` and no list item
    passed it. The pure contract moved to `tests/ui/uia_contract.py`, out from behind a
    Windows-only module skip, and `tests/ui/test_uia_contract.py` holds **19 counterexamples**:
    the reviewer's exact tree, a reconstruction of the superseded expression showing it accepted
    that tree, the missing-name case, and a value-as-name case per control. The floor is the
    values the live widgets are displaying, asserted non-empty.

    **Replaying the sweep against Qt's own tree found two more things**, which is again the point
    of widening it:

    - **The template editor's clear button reaches the accessibility tree unnamed.** Measured:
      `EditableText 'File name template'` with one child, `Button ''`. `setClearButtonEnabled`
      adds a control and Qt names none of it. The Linux audit had *excused* it as platform
      furniture on the premise that Qt names what it builds, which is what the measurement
      refutes, and no other check could see it — `focusable()` walks the Tab chain and the button
      is `NoFocus`. Named at its source, its keyboard route declared through the mechanism
      `T200-R2` built for exactly this, and the exclusion tightened so the next one fails.
    - **The published-tree sweep excluded Windows' furniture and not Qt's.** Four unnamed combo
      dropdown lists across Settings and the add dialog, plus the toolbar's `»` overflow — all
      Qt's, all of which would have failed the new sweep. Excluded now by parentage and by
      `AutomationId`, sharing one `PLATFORM_FURNITURE` list with the Linux audit rather than a
      second copy of it.

    **What is still not established is unchanged**: none of the Windows assertions has executed.
    That is `R2`.

    **The third pass verified all of that and found one thing more, corrected 2026-09-11.** The
    furniture filter compared the *whole* `AutomationId` against bare Qt object names, and Qt does
    not publish bare object names: its Windows provider builds the property through
    `QAccessibleBridgeUtils::accessibleId`, which returns a declared `QAccessible::Identifier` or
    else a **dot-separated path through the accessible ancestors**. This application's overflow
    button is `QApplication.mainWindow.queueToolBar.qt_toolbar_ext_button`, so the exclusion never
    fired and the sweep failed on Qt's own control. The predicate now compares the identifier's
    **last segment** — split, never a suffix test, which would excuse
    `…myqt_toolbar_ext_button`. Measured both ways on the surface harness: the superseded
    comparison reaches `read_tree` **4 times** and fails at the first surface; the correction
    reaches it **16** and passes. All three allowlist entries are now exercised as qualified
    identifiers, the declared-identifier shape is covered, and five lookalikes are proven rejected.
    The comments claiming the two platforms spell the identifier alike are corrected — they do
    not.

    **`P4EXIT-R4` is Resolved** as of the third pass.

    **The fourth pass resolved `R1` at `2ea1aa6`.** It reproduced the 4-versus-16 query result,
    reconstructed the superseded whole-identifier comparison as a plugin (**2 failed / 24 passed**),
    and went further than this correction did: three isolated probes broke qualification for each
    allowlisted name **individually**, each failing the all-entries check on that exact name — so
    the claim that the suite covers all three is established rather than argued, even though only
    the overflow path was measured in the application. It records one bound, which is the same one
    this correction recorded: **a declared accessible identifier containing dots is
    indistinguishable from a generated ancestor path by this string alone.** A source search finds
    no application use of explicit accessible identifiers, and the thirteen-surface harness carries
    no nonempty Identifier and no dotted object name, so there is no current case needing a
    different discriminator. No change is requested; introducing such a name would mean revisiting
    the matcher.
  - **`P4EXIT-R4` — Resolved 2026-09-11** by the third pass. The theme comment, the
    `BORDERED_CONTROLS` reason and
    the entry above called the collapse triangle the *only* pointer route out of a panel.
    `RowPanel` gives `Done` the same `closed(True)` (`ui/add_dialog.py:784`, `:805`). All three
    now describe it as the return control at the top of the panel — measured first in every
    panel's focus chain — without claiming exclusivity.
  - **`P4EXIT-R2` — not a queue, a machine.** `WINDOWS_RUNNER` pins `windows desktop` and
    `frozen windows` to `STARBASE`, and the API reports that runner **offline**; both jobs are
    queued behind it at `55d7488`, re-checked 2026-09-11 against the runner API rather than
    inferred from the job state. `OPS-012` records that a self-hosted job with no matching
    online runner queues up to 24 hours before GitHub discards it. **Bringing `STARBASE` online is
    the only route**: `windows-desktop` carries the literal `[self-hosted, windows, desktop]` at
    `.github/workflows/ci.yml:535`, so unsetting `WINDOWS_RUNNER` does not move it. *(This
    previously offered that unset as a fallback to hosted, which is wrong for the native job and is
    corrected here.)* A fresh run is needed either way — `R1`'s correction changes the test tree
    the evidence must cover.
  - **`P4EXIT-R3` — taken 2026-09-11.** The maintainer accepted the residual: Phase 4 may exit
    with `T-289`'s unexplained abort, bounded by the unchanged reopening condition. Recorded in
    that task's closed record and in the risk section below. **The crash is still not explained**,
    and the acceptance says so.
- **Phase 5 is planned, and its four gating rulings are taken.** Twelve tasks (`T-317`–`T-328`)
  plus `T-106` tie every Phase 5 deliverable and exit criterion to an owner; see the task map in
  [IMPLEMENTATION_PLAN §Phase 5](IMPLEMENTATION_PLAN.md#phase-5--distribution).

  **The maintainer ruled on all four on 2026-09-11**, so nothing in Phase 5 is waiting on a
  decision: [`REL-003`](DECISIONS.md#rel-003--semver-and-the-first-release-is-010) SemVer with a
  first release of `0.1.0`; [`REL-004`](DECISIONS.md#rel-004--the-linux-artifact-ships-as-an-appimage)
  AppImage for Linux; [`REL-005`](DECISIONS.md#rel-005--the-first-windows-installer-ships-unsigned)
  `0.1.0` ships unsigned, with a certificate as the `1.0` condition; and
  [`REL-006`](DECISIONS.md#rel-006--a-clean-machine-is-a-disposable-vm-the-maintainer-owns)
  disposable VMs the maintainer owns as the clean-machine evidence. `T-106` is **In Review** —
  `REL-004` meets every criterion it had. `T-317`, `T-318` and `T-320` keep the documentation and
  harness work their rulings did not do, and stay `Proposed` because the phase has not opened.

  **What still gates the phase is Phase 4's exit, not a decision.**

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
