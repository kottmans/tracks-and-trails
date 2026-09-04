# Orphaned worker processes on the CI runners

**Purpose:** What the stuck `python.exe` processes on `STARBASE` were, what was established about
them, and what to do if they appear again.
**Owner:** Implementer.
**Status:** Reference. **This is a machine condition, not an application defect** — no `src/` change
was ever made for it, and none is outstanding.
**`T-268` was closed against this file on 2026-09-04, with the cause unidentified.** The seven
specimens are **released** — the preservation requirement is discharged and they may be reaped
whenever the machine is next attended. `ai/TASKS.md` `T-268` is current truth for the disposition;
if this file and that entry ever disagree, the entry is right.
**Last updated:** 2026-09-03.

---

## The short version

Between 2026-08-04 and 2026-08-17, seven `multiprocessing` spawn children on the Windows runner
outlived the process that created them and never exited. They sit blocked, using no CPU, holding
about 390 MB between them. **The cause was never identified**, and after a month of measurement the
remaining question is narrow — *which* lock, not whether a lock.

**Two decisions, a day apart.** On **2026-09-03** the nightly scan was retired, because it was
permanently red over these seven. On **2026-09-04** the question itself was closed against this
file: the only thing that would have answered *which lock* is a live stack from one of the
specimens, nobody was going to take it, and keeping them cost about 390 MB and a runner that would
eventually stop accepting jobs. **The cause is not identified and now will not be.**

They are not a product fault. Nothing a user runs produces them; they came out of test runs on a
self-hosted runner.

## What they are

Each is a `python.exe` started by `multiprocessing`:

```
python.exe -c "…spawn_main(parent_pid=…, pipe_handle=…)" --multiprocessing-fork
```

| pid | created | parent | age at 2026-09-03 | rss |
|---|---|---|---|---|
| 7028 | 08/04 20:07 | 1052 | 29d | 45 MB |
| 10524 | 08/04 19:43 | 12144 | 29d | 57 MB |
| 2432 | 08/05 12:33 | 9176 | 28d | 45 MB |
| 3408 | 08/05 12:33 | 9176 | 28d | 42 MB |
| 11000 | 08/05 12:33 | 9176 | 28d | 45 MB |
| 3400 | 08/17 13:07 | 1204 | 16d | 79 MB |
| 6924 | 08/17 13:07 | 1204 | 16d | 77 MB |

Note the clustering: three share parent `9176` and were created in the same second, two share `1204`.
Whatever happened, it took a whole batch at once rather than one child at a time.

## What was established

- **They are past their payload read.** Argued from CPython's source as well as from measurement:
  `popen_spawn_win32.Popen.__init__` creates the payload pipe with non-inheritable handles and
  `bInheritHandles=False`, so the parent holds the sole write handle and its death closes the pipe
  **by construction**. No sibling can be holding it open.
- **`threads=1` on every one**, so none reached `prepare_this_worker()`'s watchdog. Together with
  the point above that bounds them to a narrow region: after the payload read, before the watchdog,
  which leaves `contain_this_process()`.
- **Blocked, not spinning** — about 2 seconds of CPU each over twelve days.
- **Blocked on an in-process synchronisation primitive.** Measured 2026-08-29 (read-only run
  `33267794308`): every one reports `KWAIT_REASON 37`, `WrAlertByThreadId` — the wait behind
  `WaitOnAddress`, SRW locks and condition variables. This **refuted** the last standing candidate,
  "something outside the interpreter, a suspended process", which would have reported `WrSuspended`.
- **The signature is reproducible on Windows.** A child stopped *past* the payload read, with the
  outer Job suppressed, survives its parent's death with one thread. Stopped *before* the read it
  dies. With the outer Job present it is reaped.

## What was never established

**Which lock.** That is the whole of the remaining question, and answering it needs a live stack
from one of the blocked threads — an attached debugger or an equivalent live-dump. WER `LocalDumps`
(`T-092`) cannot help: it fires on abnormal *termination*, and these are alive and stuck.

**Two explanations were tried and are wrong**, which is worth knowing so neither is offered again:

- **The pre-bootstrap window.** `T-258` reproduced a window where a child is killed before it
  finishes starting, and closed it. `T-266` then measured that **that window closes itself** on
  Windows — a child stopped there dies with its parent, exit code 1. The fix was built for a window
  that was not the cause. It happens to cover the region they were actually in, and `T-258`'s record
  calls that luck rather than design.
- **A suspended process.** Refuted by the wait-reason measurement above.

## If it happens again

1. **Scan.** `tools/orphan_scan.py` needs only `psutil` and no checkout beyond itself:

   ```
   python tools/orphan_scan.py      # reports; exits 1 if any were found
   ```

   It matches on the `spawn_main … --multiprocessing-fork` command line, a parent that is gone, and
   a minimum age. **It cannot prove a match is ours** — any `multiprocessing` program on the machine
   produces the same command line — so a find is a prompt to look, not a proof.

2. **Do not bulk-kill.** A `--kill` mode existed and was removed as a Critical finding (`T258-R4`):
   the scan stored an integer pid and signalled later from it, so a process that exited in between
   meant killing whatever had been given that pid since. If you terminate anything, revalidate pid,
   creation time, command line and parent first, and terminate only what you explicitly selected.

3. **If you want the cause**, take a live stack before doing anything else — the specimen is the
   evidence, and a debugger that is killed rather than detached takes its debuggee with it.

4. **Reaping is fine now, including the original seven.** The preservation requirement was
   discharged when `T-268` closed on 2026-09-04. Point 2 still applies to *how*: revalidate pid,
   creation time, command line and parent immediately before terminating, and terminate only what
   you explicitly selected.

   *(This said "do not reap the seven" between 2026-09-03 and the closure, while they were still
   `T-268`'s only specimens.)*

## What was removed, and what that costs

The nightly `STARBASE orphans` job was removed on 2026-09-03. It was doing its job correctly — it
found the seven every night and failed, which is what it was built to do — but the seven were being
kept deliberately, so the alarm was permanently red for a known reason and a genuinely new orphan
would have looked identical to it.

**The cost is stated rather than glossed:** there is now no automatic detection on the machine where
these accumulate. `T-258` built that job because *"prevention that regresses is silent"*, and the
first five went unnoticed for twelve days. If the mechanism recurs, nobody will be told; it will be
found the way the first ones were, by somebody noticing the machine misbehaving. That was accepted
on 2026-09-03 on the grounds that one occurrence in a month of watching is rare enough to trade
against a permanently red board.

`Linux orphans` still runs, and `tools/orphan_scan.py` still exists to be run by hand.

## Where the detail lives

- `ai/evidence/2026-08-29-T268-orphan-wait-reasons.md` — the wait-reason measurement, all seven.
- `ai/evidence/2026-08-29-T268-starbase-orphan-wait-reasons.txt` — the raw report.
- `ai/TASKS.md` `T-258` — the five observations and the fix built from the wrong reasoning.
- `ai/TASKS.md` `T-266` — the measurement that showed the reproduced window closes itself.
- `ai/TASKS.md` `T-268` — the diagnosis, its eliminations, and the three-way discrimination.
