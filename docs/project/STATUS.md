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

- **The second Phase 5 review returned changes requested** on 2026-09-13
  ([batch record](reviews/phase-5-second-batch.md)). Approved: `T-320`/`T-317`, `T-321`, `T-329`,
  `T-330`, `DOC-008`. **Corrections made the same night, awaiting re-review:** `T322-R1`
  (**Critical** — the uninstaller deleted its whole directory recursively), `T334-R1` (a durable
  probe not counted as queue work), `T324-R1`/`R2` (the release upload path and the ffmpeg probe),
  `T325-R1` (the cold gate averaged warm launches), `T326-R1` (the missing §7 settings-freeze test),
  `T039-R1` (the Sandbox run's failure contract), `T318-R1` (a retained Windows run with real
  downloads), and the documentation findings `T318-R2`, `T320-R3`, `T326-R2`, `P5B2-R1`, `P5B2-R2`.
  **`T322-R1` is verified in Windows Sandbox**: the fixed installer keeps the user's files, and the
  same installer with the old rule deletes them and fails. `T-323`'s two remaining findings are
  corrected too, but a further review pass there needs the maintainer's §14 choice. Each task entry
  has a dated section.
- **Waiting on the maintainer**, and not implementable around:
  - `T039-R2` — whether candidate-only Sandbox gates replace `T-039`'s per-push CI criterion;
  - `T-323` — its two remaining Medium findings have used the ordinary review budget, so a further
    pass needs the maintainer's `TESTING` §14 choice;
  - `T325-R2` — cold starts need reboots: Linux on the reference machine, Windows on `STARBASE`
    with the installed artifact identified;
  - `T-327` items 2–6 — the manual Windows session; `T-333`'s installed-build observation rides it;
  - the first `v*` tag, which `T-324`'s draft run and `T-326`'s candidate items need.
- **In progress without a blocker:** `T-319` (its new CI steps' first run), `T-322` (the
  SmartScreen screenshot, a workflow build), `T-331` (a rerun of the two mutations its 2026-09-13
  Windows run showed were stale), `T-332` (dispatching the canary at 2026.8.19).
- **`T-212`'s recorded checklist run** and the four Windows-only diagnostic tasks (`T-074`,
  `T-092`, `T-068`, `T-056`) are Phase 5 work, each to be given a disposition before the release
  (`T-328`).
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
