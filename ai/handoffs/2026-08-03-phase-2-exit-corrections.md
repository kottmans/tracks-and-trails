# Phase 2 exit — corrections to all five findings

You are the Reviewer (`AGENTS.md` §3). This is the **re-review** of the Phase 2 exit. Your own
verdict at `5eb2611` was *changes requested — Phase 2 has not exited*, on five findings. All five
are answered.

**Repository:** `/mnt/storage/software_projects/tracks-and-trails/tracks-and-trails`, branch `main`

---

## Read this first

Two of your findings were tests that pass with their subject removed. **I corrected both and then
mutated the corrections**, which found a third defect you did not name and which mattered more than
it looks. It is in `P2EXIT-R1` below. If you read one thing here, read that.

The honest summary of this round: your two mutations were the entry point, not the finding. The
finding was that *both* gates had a second, independent way of not firing, and in one case the
correction only worked because I also changed a timeout I had no reason to suspect.

---

## `P2EXIT-R1` — criterion 5, the N-worker orphan gate

**Corrected.** `test_no_worker_outlives_a_hard_kill_with_a_full_pool` now kills exactly one
process.

- `kill_only_the_application()` (`tests/integration/test_end_to_end.py`) calls
  `psutil.Process(pid).kill()` — `SIGKILL` to one pid on POSIX, `TerminateProcess` on one handle on
  Windows. **No platform split**, unlike everything else in that file, because neither form reaches
  a child. The venv launcher is deliberately left alive: it is the application's parent, not the
  workers'.
- Cleanup moved to `reap_the_captured_tree()` in a `finally`, working from a tree captured *before*
  the kill. It **returns** survivors instead of asserting on them, so a teardown problem cannot
  replace the finding — and the test asserts on that return value after the behavioural assertion.

**I checked first that the watchdog is the only mechanism**, because a redundant guard would have
made the corrected gate untestable in a way that looks identical to a working one.
`process_tree.contain_this_process()` is called from `worker.prepare_this_worker()` and nowhere
else, so there is no parent-side Job object reaping workers on Windows; and the harness's
`start_new_session` group is never signalled. The watchdog is load-bearing and alone.

| Mutation | Before | After |
|---|---|---|
| `_exit_when_the_parent_does()` deleted from `prepare_this_worker()` | 1 passed in 9.52 s | **1 failed in 7.76 s** — "3 of 3 worker(s) outlived the application" |
| unmutated | 1 passed | 1 passed in **2.75 s** |

### The finding you did not name, and should check

The old gate waited **60 seconds** for the workers to die. `CLIP_BYTES` at `chunk_delay=0.5` is
about **eight seconds** of paced download. So an orphaned worker simply *finished its download and
exited* inside the window, and `wait_procs` reported it as correctly reaped.

Measured: with the watchdog still removed and the grace period restored to 60 s, **the corrected
gate passes in 11.71 s.** Everything else about the correction is intact. So `ORPHAN_GRACE = 5.0`
is doing as much work as `kill_only_the_application` is, and the timeout was an independent second
reason this gate could not fire.

`test_end_to_end` had already written this reasoning down, for the single-worker case, in a comment
that says a generous timeout "would let a missed worker finish the clip and be reported as
correctly reaped". The phase gate did not inherit it. **Worth asking where else in this suite a
negative claim is bounded by a timeout longer than its subject's own lifetime** — I have not swept
for it and that is a gap in this correction rather than a claim that none exists.

---

## `P2EXIT-R2` — criterion 1, the responsiveness gate

**Corrected**, with the three controls your recommendation asked for.

| Control | Catches | Speed |
|---|---|---|
| `manager.active_job_ids()` immediately after the three starts | a start that never happened | **synchronous** — `start()` reserves before the writer thread runs |
| all three `RUNNING` at one moment | workers that took turns rather than overlapping | at the spin |
| each job advancing its own update count **inside** the sampling window | a measurement taken while the queue was quiet | at the window's end |

The first is what makes it fail *promptly*, which you asked for specifically.
`child_streaming_until_released` holds the workers open on a marker file so the window is chosen by
the test rather than by three interpreters' start-up times; they are released in a `finally`, and
all three must then reach `COMPLETED`.

| Mutation | Before | After |
|---|---|---|
| all three `manager.start()` calls deleted | 1 passed in 60.24 s | **1 failed in 0.54 s** |
| worker reverted to `child_streaming_its_own_size` | — | **1 failed in 3.29 s**, updates per job during the window `{'job-1': 0, 'job-2': 0, 'job-3': 2}` |
| unmutated | 1 passed | 1 passed in **3.31 s** |

**That second row is the more interesting one.** It says the old test's own workers barely
overlapped — two of the three had finished before any sampling began. The gate was not merely
missing a control; for most of its sixty seconds it was measuring an idle event loop, which is
exactly why an idle event loop satisfied it.

The measurement is now recorded rather than only judged, following `cold_start_seconds`:
`worst_event_loop_pass_ms` **1.4** against the 100 ms budget, over **296** progress updates in a
2 s window. Both land in the junit XML in `reports/`.

---

## `P2EXIT-R3` — the `T-122` timing gate

**Corrected as you originally recommended, not as `T-122` first implemented it.** The 500-row
absolute budget and the structural control count are the required gates; the relative ratio is
**diagnostic**. Each sample is shut down and reaped inside the loop rather than after the test,
sizes alternate, `superlinear_growth` rejects insufficient or unequal sample sets, and
`SCALING_PAIRS >= 3` is pinned independently of the oracle's own fixtures — which was the specific
hole you found, where changing it to 1 left both tests green.

---

## `P2EXIT-R4` — the CI rewrite

**Maintainer ruling obtained, 2026-08-03. `OPS-010` supersedes `OPS-009`'s runner placement.**

You were right, and the reasoning matters more than the outcome: routing Windows to `STARBASE` and
*removing* the Windows desktop suite from pushes were two changes, and the hosted-minute constraint
authorised only the first. The desktop job runs on the maintainer's own machine and costs nothing.
It was removed for wall-clock and then defended with an argument about money that does not apply to
it.

- **The full Windows desktop suite runs on every push again.** No `[win]` opt-in.
- **The Windows leg of `check` stays dropped** while `WINDOWS_RUNNER` is set — that is the
  duplicate quota actually pays for (identical suite, same machine, four seconds apart).
- **`OPS-010` states what is surrendered**: clean-machine hosted evidence, and the offscreen
  platform plugin on Windows, which now exists in no cell.
- **Windows evidence is asynchronous by decision** — required before review, not a barrier to
  carrying on working. Linux still answers in ~7 minutes.
- **A push can no longer cancel a scheduled run.** `cancel-in-progress` is read from the *arriving*
  run, so the separate concurrency group is the actual fix; `false` for schedules stops two
  nightlies colliding. The nightly's stated purpose is rewritten too: it is no longer standing in
  for missing coverage, it catches what no commit causes.

`ai/TESTING.md` §10 and `ai/IMPLEMENTATION_PLAN.md` follow the ruling.

---

## `P2EXIT-R5` — the current-truth documents

Reconciled. `ai/IMPLEMENTATION_PLAN.md` no longer says criteria 1–5 and 7 are met with only the
exit review outstanding — it records your verdict, which rows failed, and why. `ai/TESTING.md` §10
carries no reconciliation notice because there is nothing left to reconcile.

---

## What else changed that you did not ask for

- **`UX-005`** (`ai/DECISIONS.md`) records the main window layout for the first time. The shipped
  splitter was never ratified: it was decided in a source comment reasoning from `P2PLAN-R8`, which
  is about task ownership and not about placement, and it contradicted a mockup that is lost. Two
  tabs, no detail pane, rows carry everything. `T-124`, `T-125` and `T-126` implement it and are
  sequenced **before** the exit by that decision, so the exit you are re-reviewing does not include
  them.
- **`ai/TESTING.md` §13 is now "the eight"**, with `P2EXIT-R1` and `P2EXIT-R2` added, plus two new
  rules under *What to do instead*: a "did not happen" timeout must be shorter than its subject's
  lifetime, and a budget gate needs a positive control taken inside the measured window.

---

## Evidence at this head

| Gate | Result |
|---|---|
| `ruff check .` / `ruff format --check .` | clean, 144 files |
| `mypy src` / `mypy` / `mypy --platform win32` | clean — 43, 101, 101 files |
| Full suite (Linux) | **1986 passed, 11 skipped, 2 deselected** in 6m48s |
| Task placement | 14 passed |

**On that 6m48s:** the last recorded figure was 4m52s at `5eb2611`, and the two are not comparable
— this run shared the machine with a CI poll, three separate `mypy` invocations and an earlier
integration run. The counts are identical, and the two tests I touched both got *faster* (the
orphan gate 9.52 s → 2.75 s, the responsiveness gate ~60 s → 3.31 s), so nothing here adds time. I
have not re-measured on a quiet machine; if the number matters to you, the CI run on this head is
the clean one.

**Windows evidence.** `OPS-010`'s restoration is proved: run `30873256745` at `529dc05` is green on
every job including `windows desktop`, which is the first push-triggered Windows desktop run since
the removal. **The corrected `R1` gate has not run on Windows yet** — that is this head's push, and
it is the run you asked for.

## What is still not verified

- **`T-121`** — the phase-exit clip server aborting on hosted Windows. Two parts fixed, the abort
  itself unreproduced, and now doubly latent because hosted Windows no longer runs at all.
- **`T-123`** — parallel suite, deliberately not started before an exit review.
- **A real extractor.** Every probe replays a recorded fixture or a localhost server.
- **The dark theme has never been on a screen.** `T-120`'s contrast is arithmetic.
- **`OPS-004`'s subjective half.** Blocks first release, not this phase, and has said so since
  Phase 0.

## If you want the application in front of you

```bash
cd /mnt/storage/software_projects/tracks-and-trails/tracks-and-trails && .venv/bin/python -m tracks_and_trails
```
