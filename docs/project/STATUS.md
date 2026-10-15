# STATUS.md — Tracks & Trails

**Purpose:** Current implementation state, immediate work and unresolved risks.
**Owner:** Planner / Implementer (Coordinator during a wave)
**Last updated:** 2026-10-15
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
- **Phase 4.5 (option coverage) is under way, in the order ruled on 2026-09-17** ([the
  stages](IMPLEMENTATION_PLAN.md#order-2026-09-17)) **and amended on 2026-10-11** ([the
  amendment](IMPLEMENTATION_PLAN.md#amended-2026-10-11-no-011-and-t-351-first)): `T-343` and `T-347`
  are done and ship in `0.2.0`, with no `0.1.1`; the escape hatch `T-184` is done; then `T-351`, the
  nine typed-field tasks `T-247`…`T-255`, the rest of the `0.1.0` debt, and **`0.2.0`** (`T-358`).
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
- **`T-184` is Complete**, approved 2026-10-10 at `83749d7`
  ([record](reviews/T-184.md#2026-10-10--eighth-round-focused-verification)) after eight correction
  rounds; its entry is in
  [COMPLETED_TASKS](COMPLETED_TASKS.md#t-184--the-escape-hatch-additional-yt-dlp-options-parsed-and-bounded).
  The last two rulings, both 2026-10-10: a long option is typed in full (`ARC-010` amended), and the
  validation boundary was revised within the task, so a pattern `re.compile` cannot build is refused
  rather than raised. **The push hold is released**: `main` was pushed with `d18bcb8`, and CI run
  [`38088244998`](https://github.com/kottmans/tracks-and-trails/actions/runs/38088244998) passed
  every job on both platforms. Release readiness and the `0.2.0` acceptance walk are not approved by
  it, and `T-048` stays its own task.
- **Four rulings taken 2026-10-11, all as recommended.** No `0.1.1` (`T-349` Cancelled); `T-351`
  runs before `T-247`, as a High defect `0.1.0` shipped; verified build archives are kept beside
  each release (`OPS-001` amended, carried by `T-360`); and the two deliverables that had no owner
  are filed: the README's `REQ-030` statement within `T-358`, the `0.2.0` release, and promotion as
  `T-359`. **`T-351` and `T-360` were built and approved the same day**, and `T-355`, `T-356` and
  `T-357` closed on their CI evidence; all five are in [COMPLETED_TASKS](COMPLETED_TASKS.md). **Four
  more rulings the same day designed `T-247`** (`ARC-010` and `UX-015` amended): `-I` and *at most
  N* act when a playlist is expanded, a preset keeps a date as typed while each job freezes it, and
  one *Which items* group holds all seven controls. Mapping it found the hatch admitting, then
  dropping, long spellings of options that already have a control. **`T-361`, the fix, was approved
  the same day** and is in COMPLETED_TASKS. `T-247` came back with four blockers,
  `T247-R1`…`R4`. Its first correction resolved `R2` and `R3` and passed native Windows CI on
  `STARBASE`; `R1` and `R4` stayed open as Critical, and the maintainer chose on 2026-10-12 to
  revise the selection boundary within the task. **The second correction was approved on
  2026-10-13** at `b7c1dc4`, and `T-247` is in COMPLETED_TASKS; native Windows at that head is
  unverified. **`T-362` was approved on 2026-10-14** at `4fa990b` and is in COMPLETED_TASKS.
  **`T-249` is built and with the Reviewer.** **`T-251` was built the same night, ahead of that
  review and on the implementer's recommended design**, by the maintainer's instruction
  ([the amendment](IMPLEMENTATION_PLAN.md#amended-2026-10-14-t-251-may-be-built-before-t-249s-review-returns));
  its three design questions were ruled as recommended on 2026-10-15 (`ARC-010` and `UX-015`
  amended), so the build stands, and it is with the Reviewer too. Mapping it found the options field able to ask for every automatic caption a
  site lists, about 160 on YouTube, through `--write-auto-subs` and the built-in's `all`, on
  unreleased `main`; closed within the task. The rest of stage 3 was mapped ahead the same
  night, so its rulings can be taken together. `T-247`'s sibling audit found
  queued files numbered among the readable entries rather than by slot, filed as `T-362` by the
  maintainer's ruling, to run right after `T-247`. **`T-249`'s design was ruled the same day**
  (`DAT-003` and `UX-015` amended): mapping it found the options field's `--write-info-json` keeping
  the session's cookies and typed headers in a file beside the media, on unreleased `main`; the file
  is to be kept with them stripped, fixed within `T-249`.
- **The first `T184-R6` correction was inert, found 2026-09-24.** It registered hatch values in
  the worker, but a worker's records are redacted by the parent's handlers, so a real spawn left
  the value in the log. The correction of 2026-09-24 registers them in the parent, covers the
  `--opt=value` spelling, and exempts options whose values cannot be secrets.
- **Three rulings taken 2026-09-26, all as recommended**
  ([T-184](COMPLETED_TASKS.md#t-184--the-escape-hatch-additional-yt-dlp-options-parsed-and-bounded)): that
  exemption is accepted and the criterion narrowed to values that can carry a credential or name a
  file (`ARC-010`); the field is stored verbatim like a URL, in `settings.toml` and the queue
  database (`DAT-003`); and `REQ-031` now says the admitted command line rather than a parsed
  dictionary.
- **A fourth `T-184` correction round, 2026-09-26, was reviewed on 2026-09-27.** It closes a false
  success reachable through `--compat-options`, the same outcome the audit refuses `-i` for, plus a
  merge that read values as options, three unregistered pieces of logged values, and two values
  that failed only at run time.
- **Three more rulings taken 2026-09-27, all as recommended.** An item yt-dlp skips at the user's
  request ends Cancelled with its reason (`UX-005`), where it failed as `DISK`, *The file could
  not be written*. A path option must be absolute (`ARC-010`). And the field is the options
  editor's last group, checked as the user types (`UX-015`), so `T-184`'s interface is specified.
  **All three are built** and were reviewed on 2026-09-27: the first two as a fifth correction
  round, the third as `T-184`'s interface stage.
- **A codebase audit ran on 2026-09-24** and is with the Reviewer for its own record. Two outcomes
  are already filed: `T-351` (with a playlist in the queue, row changes are signalled on the wrong
  row, and a screen reader hears less than the row shows) and `T-352`, which retires
  `JobProgressView` by the maintainer's `UX-005` amendment of the same day.
- **`T-348`'s shape is recommended** (2026-09-18): fetch, verify against the published
  `SHA256SUMS`, hand over. The release publishes no `.zsync`, so delta updating would need a release
  change, and in-place updating waits on signing.
- **There is no `0.1.1`** (maintainer, 2026-10-11). `main` carries `T-184` since 2026-10-10, so a
  fixes-only patch would need a release branch from `v0.1.0`; `T-349` is Cancelled, and its
  preparation moved to `T-358`, the `0.2.0` release. The 2026-09-17 evening amendment had already
  let the patch stop gating the phase ([that
  amendment](IMPLEMENTATION_PLAN.md#amended-the-same-evening-the-patch-no-longer-gates-the-phases-work)).
- **One acceptance walk closes the phase.** `TESTING.md` §8 item 6, waived for `0.1.0`, is
  run once, by the maintainer's ruling: it happens once on the finished `0.2.0` build and closes `T328-R4`
  and the last criterion of `T-340`, `T-342` and `T-344`. `T-339` (Narrator) sits in the same
  sitting, and `T-348` gets a ruling in this phase rather than a build.

## Verification

*Refreshed 2026-10-15, at `3275a36` (code unchanged at `e3b2c8f`), on Linux with the project
`.venv` (yt-dlp 2026.08.19).* The previous snapshot, for `T-184`'s correction rounds, is
recoverable from `e3b2c8f`; how often `T-350`'s race failed each of those runs is kept in
[its entry](TASKS.md#t-350--a-staged-format-fixture-races-a-real-probe-and-loses-its-format-control).

| Check | Result |
|---|---|
| `ruff check .`; `ruff format --check .` | Passed; 480 files (at `bfda7c9`, `T-251`'s gate) |
| `mypy src`; bare `mypy`; `mypy --platform win32` | Passed; 70, 219, 219 (at `bfda7c9`). **Bare and Windows-platform `mypy` failed at `8b0aad6`**, on one `T-249` test, fixed in `bfda7c9` |
| `tests/unit tests/ui` under `-n auto`; `tests/integration` | **5,583 passed**, 21 skipped; **537 passed** (at `bfda7c9`) |
| Full `pytest -q -p no:cacheprovider`, serial | **4 failed, 6,116 passed**, 21 skipped, 2 deselected; 2,216 s |
| Repo root before and after | Unchanged |

**All four failures are `T-350`'s race**, cases of
`test_the_mounted_format_panel_fits_the_dialog_it_asked_for` failing *"row 0 offered no format
control"* with the real worker's DNS error in the log, which is the cause its 2026-10-14
investigation confirmed.

**CI was red at the pushed `8b0aad6`**: run
[`38672888953`](https://github.com/kottmans/tracks-and-trails/actions/runs/38672888953)'s `linux`
job failed at *Types, tests included*, the bare `mypy` error above, and its two Windows jobs are
queued on `STARBASE`, which is offline. The fix, `bfda7c9`, was pushed on 2026-10-15 with
`ea5c787`.

No Windows runtime, external download or release-gate result is claimed here.

## Current risks and external blockers

- **A containment breach on unreleased `main`, found 2026-10-14 while mapping `T-248`.**
  `--trim-filenames` or `--windows-filenames` typed in the options field makes yt-dlp reshape the
  whole staging path, and a download can land outside the chosen folder; the job then fails, and
  the stray file stays. Critical by `TESTING.md` §14's wording; `0.1.0` predates the field. The
  same round found the field able to switch off yt-dlp's unsafe-extension check for the whole
  process, and fragmented downloads ending *Done* with a fragment missing, in `0.1.0` too.
  **Ruled 2026-10-15, as recommended:** both are fixed next, before `T-250` — the breach and the
  `--compat-options` values as [`T-363`](TASKS.md#t-363--the-options-field-can-write-outside-the-chosen-folder-and-switch-off-a-safety-check),
  **built the same day and with the Reviewer**, then the fragments as
  [`T-364`](TASKS.md#t-364--fragmented-downloads-retry-and-never-finish-with-a-piece-missing),
  shipping in `0.2.0`.
- **CI is green again.** Its Linux job failed from 2026-10-08, when PySide6 6.12.0's metapackage
  began requiring `PySide6_WebEngine` and `PySide6_Pdf` and the `LIC-001` gate refused them.
  **`T-355`** caps PySide6 below 6.12, and the push of `d18bcb8` passed every job in run
  [`38088244998`](https://github.com/kottmans/tracks-and-trails/actions/runs/38088244998). `T-355`
  closed on it, approved 2026-10-11
  ([record](COMPLETED_TASKS.md#t-355--pyside6-612-brings-webengine-and-pdf-into-the-bundled-tree)).
  Moving to 6.12 needs its own ruling.
- **The `Commit messages` gate failed on that push**, run
  [`38088245029`](https://github.com/kottmans/tracks-and-trails/actions/runs/38088245029):
  `5314816`, a documentation commit no task covers, has no `Task:` trailer where the gate wants
  `Task: none - <reason>`. It is published, so it is not rewritten; later pushes are checked from
  their own base and do not meet it again. The local `commit-msg` hook that would have stopped it
  was not active in this clone. Grandfathering it as `T-065` did `12dff92` is the maintainer's to
  decide.
- **`STARBASE` was offline from 2026-09-18 to 2026-10-09**, and GitHub had removed its
  registration by the time it returned; it was registered again on 2026-10-09
  ([procedure](../WINDOWS_VERIFICATION.md#offline-for-more-than-14-days-it-must-be-registered-again)).
  Every run in between left `windows desktop` and `frozen windows` queued until cancelled, and
  `STARBASE coverage` reported both as having run, because `STARBASE_AVAILABLE` stayed `true`.
- **Windows evidence is back.** The first run after `STARBASE` returned, at `8857753`
  ([`37929286459`](https://github.com/kottmans/tracks-and-trails/actions/runs/37929286459)), failed
  both Windows jobs: a cp1252 pipe to Ruff, which **`T-356`** fixes, and a pinned ffmpeg BtbN had
  deleted, which **`T-357`** repins to a month-end build kept for two years. At `d18bcb8` both
  passed: `windows desktop` ran the desktop slice and the full suite, integration included, for the
  first Windows integration result since 2026-09-18, and `frozen windows` built the release artifact
  and ran its bundled ffmpeg. Both closed on that evidence, approved 2026-10-11. `release.yml` uses
  the same pin, so `0.2.0` depends on `T-357`.
- **`0.1.0`'s ffmpeg archive is kept beside `v0.1.0`** (`T-360`, 2026-10-11): BtbN deleted it, and
  it is now a release asset at the digest `0.1.0` pinned, so the local copy is no longer the only
  one. The fetcher takes such a copy by the same digest when upstream fails, and each release
  attaches its own (`OPS-001`, amended 2026-10-11). `T-360` is Complete, approved 2026-10-11; a real
  tagged release run waits for `T-358`.
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
