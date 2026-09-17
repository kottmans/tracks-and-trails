# STATUS.md — Tracks & Trails

**Purpose:** Current implementation state, immediate work and unresolved risks.
**Owner:** Planner / Implementer (Coordinator during a wave)
**Last updated:** 2026-09-17
**Update when:** Work, blockers, evidence or phase readiness changes.

## Current state

**`0.1.0` is published** (2026-09-16), from tag `v0.1.0` at `5b1bf97`: the Linux AppImage and the
Windows installer, with `SHA256SUMS`, on the
[release page](https://github.com/kottmans/tracks-and-trails/releases/tag/v0.1.0). `main` is now
`0.1.1.dev0`. Tracks & Trails also still runs from source on Linux and Windows.

**Phases 0–3 and Phase 5 have exited**; Phase 5's exit is recorded criterion by criterion, one of
them unmet by ruling ([table](IMPLEMENTATION_PLAN.md#phase-5-exit-2026-09-17)). **Phase 4's exit
review was last Blocked only on `T329-R2`'s Windows mutation evidence, which the 2026-09-13 review
resolved**; its sign-off is the reviewer's to record ([record](reviews/phase-4-exit.md)).
[README](../../README.md) describes available features; the
[implementation plan](IMPLEMENTATION_PLAN.md#phase-5--distribution) owns phase deliverables and
exit criteria.

**Order, by maintainer ruling 2026-09-10:** Phase 5 first, **Phase 4.5 (option coverage) after
the first release**. Nothing user-facing may claim parity with yt-dlp until 4.5 lands (`REQ-030`).
**Its own order was ruled 2026-09-17** and is in the
[implementation plan](IMPLEMENTATION_PLAN.md#order-2026-09-17); the phase ends with `0.2.0`.

## Active work

*Refreshed 2026-09-17. The previous snapshot is recoverable from `f67efec`; its facts live in the
task and review records it summarised.*

- **Phase 5 has exited** ([the criterion table](IMPLEMENTATION_PLAN.md#phase-5-exit-2026-09-17)),
  with `T-328` approved with follow-ups and `0.1.0` published. **One exit criterion is unmet by
  ruling:** `REQUIREMENTS.md` §11's acceptance criteria were never walked on the artifacts, on
  either platform; the maintainer waived that on 2026-09-16 and `T328-R4` stays open.
- **Every machine check passed on the published bytes** ([evidence](evidence/2026-09-14-T326-release-candidate-0.1.0.md)):
  CI, both network suites, the Ubuntu and Fedora clean machines, a download on the maintainer's
  Fedora host, Windows Sandbox, and the canary. `T-326` waits on the reviewer's verdict for that
  replacement-candidate evidence.
- **Phase 4.5 (option coverage) is next, and its order was ruled on 2026-09-17**
  ([the stages](IMPLEMENTATION_PLAN.md#order-2026-09-17)): a **`0.1.1` patch** (`T-343`, `T-347`,
  released by `T-349`), then the **escape hatch `T-184` alone**, carrying `T-048`, then the **nine
  typed-field tasks** `T-247`…`T-255`, then the `0.1.0` debt and **`0.2.0`**.
- **The task to pick up is `T-343`** — the Windows taskbar's *Close window* while a dialog is open,
  in the Windows-only shape the maintainer ruled the same day. `T-347` follows it.
- **One acceptance walk closes the phase.** `TESTING.md` §8 item 6 is not run for `0.1.1` either,
  by the maintainer's ruling: it happens once on the finished `0.2.0` build and closes `T328-R4`
  and the last criterion of `T-340`, `T-342` and `T-344`. `T-339` (Narrator) sits in the same
  sitting, and `T-348` gets a ruling in this phase rather than a build.

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
