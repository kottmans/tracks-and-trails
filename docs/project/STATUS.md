# STATUS.md — Tracks & Trails

**Purpose:** Current implementation state, immediate work and unresolved risks.
**Owner:** Planner / Implementer (Coordinator during a wave)
**Last updated:** 2026-09-27
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

*Refreshed 2026-09-18. The previous snapshot is recoverable from `f67efec`; its facts live in the
task and review records it summarised.*

- **Phase 5 has exited** ([the criterion table](IMPLEMENTATION_PLAN.md#phase-5-exit-2026-09-17)),
  with `T-328` approved with follow-ups and `0.1.0` published. **One exit criterion is unmet by
  ruling:** `REQUIREMENTS.md` §11's acceptance criteria were never walked on the artifacts, on
  either platform; the maintainer waived that on 2026-09-16 and `T328-R4` stays open.
- **Every machine check passed on the published bytes** ([evidence](evidence/2026-09-14-T326-release-candidate-0.1.0.md)):
  CI, both network suites, the Ubuntu and Fedora clean machines, a download on the maintainer's
  Fedora host, Windows Sandbox, and the canary. **`T-326` is Complete**, approved 2026-09-17 on
  that replacement-candidate evidence ([record](reviews/T-326.md#2026-09-17--replacement-candidate-evidence-verdict)).
  The approval states the `§11` walk as still waived and unperformed rather than resolving it.
- **Phase 4.5 (option coverage) is next, and its order was ruled on 2026-09-17**
  ([the stages](IMPLEMENTATION_PLAN.md#order-2026-09-17)): a **`0.1.1` patch** (`T-343`, `T-347`,
  released by `T-349`), then the **escape hatch `T-184` alone**, carrying `T-048`, then the **nine
  typed-field tasks** `T-247`…`T-255`, then the `0.1.0` debt and **`0.2.0`**.
- **`T-343` is Complete**, approved 2026-09-17 ([record](reviews/T-343.md)) and **measured on the
  real Windows desktop** (run
  [`35276130787`](https://github.com/kottmans/tracks-and-trails/actions/runs/35276130787), 46
  passed): both forms of the taskbar's close now close the dialog and then the application, with
  the defect asserted in the same run ([evidence](evidence/2026-09-17-T343-taskbar-close.md)).
  `T343-R1`, the Low finding, was closed in ordinary completion: ownership is asked again for each
  dialog the close loop reaches, with the review's two-owner probe kept as a test. It took six
  `windows desktop` runs, and **four defects they found were invisible to every gate on this
  machine** — the worst would have shipped a Windows build whose every message went through a
  raising Python function.
- **Four rulings taken 2026-09-18**, all as recommended: `T-347` raises through KWin, narrowed to
  the case that needs it; `T-184`'s refusal list is **default-deny**; a cancelled row shows its
  reason when that reason is not the application's own sentence (`UX-005` amended); and `T-348` is
  **fetch, verify, hand over** (`REL-009` amended, built in a later phase). Nothing in the phase is
  waiting on a decision now.
- **`T-347` is Complete**, approved 2026-09-19 ([record](reviews/T-347.md)) and **re-measured on
  the KDE Plasma Wayland desktop at `bfc11c1`**
  ([capture](evidence/2026-09-19-T347-production-route.txt)): all four cases establish their
  preconditions and the window comes forward when it is behind **and** when it is minimized. Every
  route was tried before it was ruled ([evidence](evidence/2026-09-18-T347-raising-dolphin.md));
  `ShowItems` leaves the window where it is and **only `KWin.WindowsRunner.Run` raises it**. The
  correct fix is unavailable from this toolkit: `Dolphin.activateWindow` needs an activation token
  and PySide6 exposes no way to get one.
- **It took five review rounds, and two of the findings were regressions in the corrections.**
  `T347-R3` found a window *caption* able to turn Show in folder into a request to **close** a
  window; `T347-R4` found the discovery worker outside the shutdown barrier. Then stricter
  discovery, written to close `T347-R1`, broke the feature on every KDE desktop: `dolphin --daemon`
  owns a bus name like any window, has no main window object, and answers an error to every
  question — so "decline on any reply I cannot read" declined on all of them (`T347-R6`). Its first
  fix over-corrected in turn, reading *unsupported method* as *no window*, which reopened `T347-R1`.
  **The approval does not cover release readiness**, and two follow-ups remain: `T-350`, and the
  human selection walk, which no instrument here can perform — `isItemVisibleInAnyView` says the
  item is in a view, not that it is highlighted.
- **`T-184` is In Progress, with every stage built, the interface included.** The review of
  2026-09-27 resolved `R9`, `R10`, `R11` and `R13` and left `R6` (Critical), `R8`, `R14` and
  `R15` blocking. It invoked TESTING §14, because the redaction and validation corrections keep
  reproducing their defect class. **The maintainer chose to revisit both designs** and correct
  all four in one batch; the design is in the task entry. The push stays held.
- **The first `T184-R6` correction was inert, found 2026-09-24.** It registered hatch values in
  the worker, but a worker's records are redacted by the parent's handlers, so a real spawn left
  the value in the log. The correction of 2026-09-24 registers them in the parent, covers the
  `--opt=value` spelling, and exempts options whose values cannot be secrets.
- **Three rulings taken 2026-09-26, all as recommended**
  ([T-184](TASKS.md#t-184--the-escape-hatch-additional-yt-dlp-options-parsed-and-bounded)): that
  exemption is accepted and the criterion narrowed to values that can carry a credential or name a
  file (`ARC-010`); the field is stored verbatim like a URL, in `settings.toml` and the queue
  database (`DAT-003`); and `REQ-031` now says the admitted command line rather than a parsed
  dictionary.
- **A fourth `T-184` correction round, 2026-09-26, is with the Reviewer.** It closes a false
  success reachable through `--compat-options`, the same outcome the audit refuses `-i` for, plus a
  merge that read values as options, three unregistered pieces of logged values, and two values
  that failed only at run time.
- **Three more rulings taken 2026-09-27, all as recommended.** An item yt-dlp skips at the user's
  request ends Cancelled with its reason (`UX-005`), where it failed as `DISK`, *The file could
  not be written*. A path option must be absolute (`ARC-010`). And the field is the options
  editor's last group, checked as the user types (`UX-015`), so `T-184`'s interface is specified.
  **All three are built** and with the Reviewer: the first two as a fifth correction round, the
  third as `T-184`'s interface stage.
- **A codebase audit ran on 2026-09-24** and is with the Reviewer for its own record. Two outcomes
  are already filed: `T-351` (with a playlist in the queue, row changes are signalled on the wrong
  row, and a screen reader hears less than the row shows) and `T-352`, which retires
  `JobProgressView` by the maintainer's `UX-005` amendment of the same day.
- **`T-348`'s shape is recommended** (2026-09-18): fetch, verify against the published
  `SHA256SUMS`, hand over. The release publishes no `.zsync`, so delta updating would need a release
  change, and in-place updating waits on signing.
- **The `0.1.1` patch no longer gates the phase's work** (maintainer, 2026-09-17 evening: *"even if
  it means skipping the interrim release"*). `T-184` may start before it ships; `T-349` stays filed
  and prepared rather than cancelled
  ([the amendment](IMPLEMENTATION_PLAN.md#amended-the-same-evening-the-patch-no-longer-gates-the-phases-work)).
- **One acceptance walk closes the phase.** `TESTING.md` §8 item 6 is not run for `0.1.1` either,
  by the maintainer's ruling: it happens once on the finished `0.2.0` build and closes `T328-R4`
  and the last criterion of `T-340`, `T-342` and `T-344`. `T-339` (Narrator) sits in the same
  sitting, and `T-348` gets a ruling in this phase rather than a build.

## Verification

*Refreshed 2026-09-27, for `T-184`'s correction rounds and its interface stage, on Linux with the
project `.venv` (Python 3.14.7, yt-dlp 2026.08.19).* The previous section described `T-300`'s
documentation follow-up; its results are kept in
[T-300](COMPLETED_TASKS.md#t-300--agentsmd-is-628-lines-and-is-loaded-on-every-task).

| Check | Third round (`428f65d`) | Fourth round (`78a5f9f`) | Fifth round (`52ace9a`) | Interface stage |
|---|---|---|---|---|
| `ruff check .`; `ruff format --check .` | Passed; 461 files | Passed; 462 | Passed; 462 | Passed; 462 |
| `mypy src`; bare `mypy`; `mypy --platform win32` | Passed; 69, 209, 209 | Passed; 69, 210, 210 | Passed; 69, 210, 210 | Passed; 69, 210, 210 |
| `pytest tests/unit tests/integration` | In the full suite | In the full suite | **3,500 passed**, 19 skipped; 722 s | In the full suite |
| Full `pytest -q -p no:cacheprovider` | **1 failed, 4,948 passed**; 3,091 s | **6 failed, 4,959 passed**; 3,575 s | Not run on that tree alone | **4 failed, 4,987 passed**; 3,421 s |
| Repo root before and after | Unchanged | Unchanged | Unchanged | Unchanged |

Every full run also skipped 22 and deselected 2. **Every failure in them is `T-350`'s race**: cases
of `test_the_mounted_format_panel_fits_the_dialog_it_asked_for`, each failing with *"row 0 offered
no format control"*. The nine cases passed alone after each run. None of these rounds changes the
add dialog or the probe of a request with no hatch.

No Windows runtime, external download or release-gate result is claimed here.

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
