# STATUS.md — Tracks & Trails

**Purpose:** Current implementation state, immediate work and unresolved risks.
**Owner:** Planner / Implementer (Coordinator during a wave)
**Last updated:** 2026-09-13
**Update when:** Work, blockers, evidence or phase readiness changes.

## Current state

Tracks & Trails runs from source on Linux and Windows, and **Phase 5 (distribution) is under way**:
a Linux AppImage and a Windows release build with an Inno Setup installer are built and evidenced
on clean machines, but **there is no tagged release**. Phases 0–3 have exited. **Phase 4's exit
review was last Blocked only on `T329-R2`'s Windows mutation evidence, which the 2026-09-13 review
resolved**; its sign-off is the reviewer's to record ([record](reviews/phase-4-exit.md)).
[README](../../README.md) describes available features; the
[implementation plan](IMPLEMENTATION_PLAN.md#phase-5--distribution) owns phase deliverables and
exit criteria.

**Order, by maintainer ruling 2026-09-10:** Phase 5 first, **Phase 4.5 (option coverage) after
the first release**. Nothing user-facing may claim parity with yt-dlp until 4.5 lands (`REQ-030`).

## Active work

*Refreshed 2026-09-13. The previous snapshot (2026-09-10) is recoverable from `8e67f6f`; its
facts live in the task and review records it summarised.*

- **The second Phase 5 review is closed** ([batch record](reviews/phase-5-second-batch.md)): every
  finding the implementer could correct was corrected and verified, including the **Critical**
  `T322-R1` (the uninstaller deleted its whole directory). **Completed 2026-09-13 and moved to
  [COMPLETED_TASKS](COMPLETED_TASKS.md):** `T-317`, `T-318`, `T-319`, `T-320`, `T-321`, `T-323`,
  `T-329`, `T-330`, `T-331`, `T-334`, and the `T-106` decision. Three clauses they left are carried by `T-328`: the README's
  install section and changelog at the release commit, and how a user without AppImageLauncher gets
  a working menu entry.
- **Waiting on the maintainer**, and not implementable around:
  - `T039-R2` — whether candidate-only Sandbox gates replace `T-039`'s per-push CI criterion;
  - `T325-R2` — cold starts need reboots, and the criterion asks for five cold and five warm samples
    per platform, with the installed Windows artifact identified;
  - `T-327` items 2–6 — the manual Windows session; `T-333`'s installed-build observation rides it,
    and `T-322`'s SmartScreen screenshot can be taken in the same sitting;
  - the first `v*` tag, which `T-324`'s draft run and `T-326`'s candidate items need.
- **Otherwise open:** `T-332` (baseline bump: every criterion met, awaiting review), `T-322` (the
  SmartScreen screenshot and a workflow build), `T-039` (on `T039-R2`), `T-324`/`T-326` (a tag),
  `T-333` (the installed-build observation), `T-328` (the release).
- **The four Windows-only diagnostic tasks** (`T-074`, `T-092`, `T-068`, `T-056`) are Phase 5 work,
  each to be given a disposition before the release (`T-328`). `T-212`'s checklist run was
  cancelled by the maintainer on 2026-09-13; §8 item 6 moved to `T-328`'s release review.
- **No automatic orphan detection runs on either platform**, since 2026-09-08. `T-302` owns
  designing detection that survives hosted runners; `tools/orphan_scan.py` runs by hand meanwhile.
- **Four UI tests fail one point above the default font** (`T-301`). Contained test debt; reproduce
  with `tools/bigger_font_plugin.py`.

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
