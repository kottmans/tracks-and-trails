# Review request — everything awaiting a verdict as of 2026-08-01

You are the Reviewer (`AGENTS.md` §3). All of this is my own work; none of it is signed off.

**Repository:** `/mnt/storage/software_projects/tracks-and-trails/tracks-and-trails`, branch `main`
**Complete unreviewed span:** `da49a51..05e5312` — twelve commits, one task each, all pushed.
`da49a51` is `T-079`'s approved head.
**Platforms:** Linux only. **No CI job has executed a step since 2026-07-30 04:08 UTC** — hosted
jobs fail before step one and the self-hosted Windows job is starved. `STATUS.md` has the
measurement. Nothing here has CI evidence and none is claimed.

**Evidence:** `ruff check`, `ruff format --check`, `mypy src` and `mypy --platform win32 src` all
clean. Full Linux suite **1726 passed / 11 skipped / 2 deselected**.

## Ten tasks, in three groups

### Group A — focused correction re-review (you have seen these once)

| Task | Correction boundary |
|---|---|
| `T-080` | `3fed547..910f3cb` |
| `T-081` | `3fed547..910f3cb` |

Your initial review of 2026-07-31 requested changes on six findings, four High. **All six are
closed**, each with a mutation. Details are in the two task entries under `## In Review`.

- **`T080-R1`** — pause now gates a direct `DOWNLOAD` start and **parks** it rather than refusing:
  the job is already durably `QUEUED`, so resume starts what the user queued while paused. Probes
  are still admitted, and the pair is now explicit.
- **`T080-R2` / `T081-R2`** — `job_removed`, `queue_reordered` and `queue_cleared` are connected to
  `QueueModel` through one slot, and disconnected in `detach()`.
- **`T081-R1`** — an in-flight reorder is an **admission barrier** on `_fill_free_slots` and
  `_start_when_free`. Released on refusal as well as success. **A counter, not a flag.** All three
  cases you named are asserted, including two in flight.
- **`T081-R3`** — `_announce_selection` emits the empty string on deselection, and the model reset
  that removal and clearing now cause is connected to it too.
- **`T080-R3`** — `ARCHITECTURE.md` §5 redrawn without `PAUSED`. The same pass corrected
  "(attempts incremented)" beside the retry edge: only *automatic* retry spends one (`UX-002`).

### Group B — never reviewed, delivered 2026-07-31

| Task | Commit | What |
|---|---|---|
| `T-046` | `2ebff0d` | Atomic output-path reservation (`O_CREAT \| O_EXCL`); 9 mutations |
| `T-053` | `19f6015` | Two live spawned workers proved not to cross-write logs; 4 mutations |
| `T-083` | `733209d` + `fd0737a` | Bounded `NETWORK` retry; **its bound and backoff are no longer provisional** — `UX-002` ratifies 3 attempts at 2s/4s/8s |

These were handed over before the `T-080`/`T-081` review and have no review record.

### Group C — never reviewed, delivered overnight 2026-08-01

| Task | Commit | What |
|---|---|---|
| `T-102` | `2a7556e` | A `settings.toml` that exists and cannot be used reports, instead of reverting silently (`ARC-008`). `load()`'s return type changed |
| `T-087` | `6ee9351` | Single-instance guard — **Phase 2 exit criterion 4**. Atomic kernel lock per `ARC-006`'s amendment |
| `T-099` | `dd9c238` | Boundary-gate failures name the rule actually broken |
| `T-101` | `dd9c238` | The retry ETA reset is gated independently of the speed |
| `T-092` | `dd9c238` | Crash-dump capture **prepared, not done** — 3 of 5 criteria need `STARBASE` |
| `T-103` | `8fd7492` | `cancel()` drops a waiting job; `T-081`'s sweep removed |

`88846ab` (Phase 3 decomposition) and `05e5312` (status and this handoff) are documents only.

## Where I would look first

1. **`T-087`'s Windows branch has never executed.** `msvcrt.locking` is `# pragma: no cover` on
   Linux and type-checked only. This is precisely the half `ARC-006`'s withdrawn design got wrong,
   so it is the half most worth doubting. `A-004` stays unverified and the task says so.
2. **The admission barrier's coverage** (`T081-R1`). I gated `_fill_free_slots` and
   `_start_when_free`. **If there is a third path from waiting to running, the barrier has a hole
   and none of my tests would show it.**
3. **`T-103` removed `T-081`'s sweep**, on the argument that `remove()` and `clear_completed()` are
   the only paths that delete a waiting job's row and both now discard the id first. If there is a
   third path, the sweep should not have gone.
4. **`T-102` changed `load()`'s return type** from `Settings` to `SettingsFile`. Every caller and
   test was updated; a missed one would be a silent attribute access on the wrong type.
5. **`ARC-008`'s silent rows.** A report that fires on a first run is worthless, so the rows that
   stay silent matter more than the ones that report. I assert all of them, but the *judgement* is
   worth a second opinion — particularly clamping, which I left silent and named as a reopening
   condition.
6. **`T-092` is prepared, not done.** Please check I have not overstated the two criteria I claim
   met. Registry keys are not the evidence; a dump naming a faulting module is.

## Two things about my own testing that you should weigh

**Two of your six findings landed on tests of mine that were passing for the wrong reason**, and a
third of that class turned up while I was correcting them:

- `test_pause_does_not_refuse_a_probe...` described a probe and called `start()` with its `DOWNLOAD`
  default, so it asserted the defect. You caught it. **Your corrected version was still weak** — it
  read `active_job_ids()`, which by design counts jobs merely *waiting* (`T078-R1`), so a wrongly
  parked probe would still have appeared in it. Found by an over-application mutation that
  **survived** the first battery. It asserts occupancy now.
- A `T081-R3` test called `action.trigger()` on a disabled `QAction`, which Qt makes a no-op, so the
  handler's own guard was never reached. Also found by a surviving mutation.

**And one mutation survived because the code was unreachable rather than the test weak.** A first
draft of `T-103` added a `_retry_at` pop to `cancel()`. Writing the test raised
`IllegalTransitionError`: a job awaiting a retry is `FAILED`, and `FAILED` allows only `QUEUED`
(`T010-R3`). The line could never run. Removed, with `remove()` covering the reachable path.

**I would rather you assume more of this class exists than that these were the last.**

## What is not verified

- **Windows, entirely.** Nothing here is platform-specific except `T-087`'s lock, which is.
- **The `app.py` seam for the toolbar controls** — injected handlers on one side, direct manager
  calls on the other. `T-102` and `T-087` *are* asserted through `compose()`; the queue toolbar is
  covered by `mypy` and the composed regressions you added.
- **Concurrent removal and completion of the same job.**
- **A read-only config directory** (`T-102`) and a full disk (`T-087`'s lock file) — `acquire`
  would raise `OSError` rather than `AlreadyRunningError`, and `run()` does not catch that.

## Process notes

- **`3fed547` is not purely mine.** It contains your correction to
  `test_pause_does_not_refuse_a_probe...`, which was in the working tree when I staged; I did not
  notice until afterwards. `AGENTS.md` §4 permits a Reviewer to update test files, so nothing
  improper happened — the commit boundary is simply muddier than it looks.
- **Handoffs are in the repository now.** Your last review recorded that the two files the
  maintainer named "were not present in the checkout" — they were in a scratchpad. `ai/handoffs/`
  fixes that.
- **All of this was written under standing maintainer authorisation to work unattended overnight**,
  including committing and pushing per task. Group C rests on Group A being sound; if a correction
  is wrong, the tasks built on top of it inherit that.

## Still Ready, untouched

`T-082`, `T-084`, `T-100` — three Phase 2 deliverables I did not reach. `T-084`'s approval waits on
`T-053`.
