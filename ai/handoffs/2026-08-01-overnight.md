# Review request — the overnight batch of 2026-08-01

You are the Reviewer (`AGENTS.md` §3). Everything below is my own work; none of it is signed off.

**Committed in the repository this time**, rather than in a scratchpad. The last review recorded
that *"the two handoff files named by the maintainer were not present in the checkout"* — they were
outside the repo. That is fixed.

**Repository:** `/mnt/storage/software_projects/tracks-and-trails/tracks-and-trails`, branch `main`
**Range:** `733209d..88846ab` — eight commits, each one task, all pushed
**Platforms:** Linux only. No CI job has executed a step since 2026-07-30; see `STATUS.md`.
**Evidence:** `ruff check`, `ruff format --check`, `mypy src`, `mypy --platform win32 src` all
clean. Full suite **1726 passed / 11 skipped / 2 deselected**.

## The commits, and what each is

| Commit | Task | What |
|---|---|---|
| `3fed547` | `T-080`, `T-081` | The implementation **you already reviewed** — committed after the fact so the correction has a boundary |
| `910f3cb` | `T-080`, `T-081` | **Your six findings, closed** |
| `fd0737a` | `T-083` | `UX-002` ratifies the retry policy; the provisional marking comes off |
| `2a7556e` | `T-102` | A corrupt `settings.toml` reports instead of reverting silently (`ARC-008`) |
| `6ee9351` | `T-087` | The single-instance guard — Phase 2 exit criterion 4 |
| `dd9c238` | `T-099`, `T-101`, `T-092` | Two carried follow-ups; crash-dump capture prepared |
| `8fd7492` | `T-103` | `cancel()` drops a waiting job; `T-081`'s sweep removed |
| `88846ab` | `T-107`–`T-114` | Phase 3 decomposition (documents only) |

**One boundary is muddy and I would rather say so.** `3fed547` also contains your correction to
`test_pause_does_not_refuse_a_probe_the_user_just_asked_for` — it was in the working tree when I
staged, and I did not notice until afterwards. `AGENTS.md` §4 permits a Reviewer to update test
files, so nothing improper happened; the commit simply is not purely mine.

## Your six findings

All closed at `910f3cb`; every one has a mutation. Details in the two task entries.

- **`T080-R1`** — pause now gates a direct `DOWNLOAD` start and **parks** it (the job is already
  durably `QUEUED`, so resume starts what the user queued). Probes still admitted.
- **`T080-R2` / `T081-R2`** — `job_removed`, `queue_reordered` and `queue_cleared` are connected to
  the queue model through one slot, and disconnected in `detach()`.
- **`T081-R1`** — an in-flight reorder is an **admission barrier**, released on refusal too, and a
  **counter** rather than a flag. All three cases you named are asserted.
- **`T081-R3`** — deselection emits the empty string; model resets are connected to it too.
- **`T080-R3`** — `ARCHITECTURE.md` §5 redrawn without `PAUSED`. I also corrected
  "(attempts incremented)" beside the retry edge: only *automatic* retry spends one.

**Two of your findings landed on tests of mine that were passing for the wrong reason**, and a third
of that class turned up in the correction battery. I would rather you assume more of them exist than
that these were the last.

## Where I would look first

1. **`T-087`'s Windows branch has never executed.** `msvcrt.locking` is `# pragma: no cover` on
   Linux and type-checked only. This is precisely the half `ARC-006`'s withdrawn design got wrong.
   `A-004` stays unverified and the task says so.
2. **The admission barrier's coverage.** I gated `_fill_free_slots` and `_start_when_free`. If there
   is a third path from waiting to running, the barrier has a hole and my tests would not show it.
3. **`T-103` removed `T-081`'s sweep** on the argument that `remove()` and `clear_completed()` are
   the only paths that delete a waiting job's row, and both now discard first. If there is a third,
   the sweep should not have gone.
4. **`T-102` changed `load()`'s return type.** Every caller and test was updated; a missed one would
   be a silent `.settings` on something that is no longer a `Settings`.
5. **`ARC-008`'s silent rows.** A report that fires on a first run is worthless. I assert all of
   them, but the judgement about *which* rows stay silent is worth a second opinion — particularly
   clamping, which I left silent and named as a reopening condition.
6. **`T-092` is prepared, not done.** Three of five criteria are unmet and need `STARBASE`. Please
   check I have not overstated the two I claim.

## What is not verified

- **Windows, entirely.** Nothing here is platform-specific except `T-087`'s lock, which is.
- **The `app.py` seam** for the toolbar controls: injected handlers on one side, direct manager
  calls on the other. `T-102` and `T-087` *are* asserted through `compose()`.
- **Concurrent removal and completion of the same job.**
- **A read-only config directory** for `T-102`, and a full disk for `T-087`'s lock file.

## Still Ready, untouched

`T-082`, `T-084`, `T-100` — the three Phase 2 deliverables I did not reach. `T-084`'s approval still
waits on `T-053`.
