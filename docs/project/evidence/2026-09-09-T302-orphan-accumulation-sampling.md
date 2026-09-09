# Nine suite runs on `Spock` left no orphaned workers — 2026-09-09

**Taken:** 2026-09-09, 07:33:53 to 09:34:39 CDT, on `Spock`.
**Head:** `793059a` at the start; the tree carried one uncommitted file, recorded by the sampler
itself rather than assumed.
**Ran:** `tools/t302_orphan_accumulation_sampler.sh 8`, stopped at two hours by the maintainer's
direction once it was clear the machine was in use.
**Why:** `T-302`. `Linux orphans` scanned a persistent runner nightly until 2026-09-08, when Linux
CI moved to ephemeral hosted VMs and the job stopped. The task's first question is where orphaned
workers accumulate instead, and its working assumption — a developer's own machine — is what this
samples.

**Full log:** `../t302-orphan-sampling-20260909-073353.log`, 748 lines, kept outside the
repository so a long run never appears as a dirty tree.

---

## The known positive ran first, and this record would be worthless without it

```
07:33:53  --- known positive: can the scanner see a deliberate orphan? ---
07:33:54  known positive PASSED — a clean scan below means something
```

`tests/unit/test_orphan_scan.py::test_the_scanner_sees_a_known_orphan` deliberately orphans a
worker and requires `find_orphans` to name it. **A scanner that cannot see one prints the same
clean zero as a machine with none**, and nineteen of those would be evidence of nothing. The
sampler aborts outright if this fails; `2026-08-29-orphan-scan-known-positive-soak.md` is the
precedent it follows.

## The result

| | |
|---|---|
| Rounds | **9**, each a full `tests/integration` + `tests/ui` pass with `-n auto` |
| Suite exits | **9 of 9 were `0`** |
| Scans | **19** — a baseline, then two per round |
| Scans reporting an orphan | **0** |
| Non-zero exits of any kind | **none** |

Each round scanned twice: immediately after the suite, at `--minimum-age-seconds 0`, and again 90
seconds later at the default threshold. **The two are asked separately on purpose** — a worker
still shutting down is not an orphan, and the difference between the scans is where a slow reaper
would show. There was no difference to see.

## The one thing that moved, and what it turned out to be

The sampler records a raw count of Python processes each round, which is deliberately wider than
the scanner's definition:

```
07:37 → 6      08:18 → 6
07:51 → 6      08:32 → 8
08:04 → 6      08:46 → 8   (and 8 for every round after)
```

**Two processes appeared between round 4 and round 5 and never left.** They are not a finding:

```
823784  Wed Sep  9 08:24:48 2026  .venv/bin/python -m tracks_and_trails
823820  Wed Sep  9 08:25:41 2026  .venv/bin/python … (its spawned worker)
```

The maintainer launched the application at **08:24:48** and it spawned a worker at 08:25:41,
between the round-4 and round-5 scans. **The scanner saw both and reported neither**, because
`823820`'s parent was alive — which is `test_a_worker_whose_parent_is_alive_is_not_reported`
holding on a real session rather than on a fixture. It is recorded here because a count that rises
and stays risen is exactly the shape a leak has, and *"it was probably nothing"* is not a reading
of evidence.

## What this establishes

**Nine consecutive runs of the suites that spawn real workers leave nothing behind on this
machine.** That is the heaviest thing routinely run here, and the assumption `T-302` was written
on — that orphans now accumulate on a developer's machine because CI can no longer catch them —
is not supported by two hours of exactly that activity.

**Rounds 5 to 9 ran with a live application present**, which is closer to how the machine is
actually used than an idle sampler would have been. The maintainer redirected the run from eight
hours to two on that basis, and the concurrent session is a property of the evidence rather than
noise in it.

## What this does not establish

- **A test run that exits cleanly is not the path that orphans workers.** Every suite exit here was
  `0`. `T-268` and `T-272`'s specimens came from sessions that ended badly, and a GUI session that
  crashes — as one did on 2026-08-27, recorded in
  `2026-08-27-T212-ytdlp-update-double-free.md` — is a different route entirely. **This says
  nothing about it.**
- **Two hours is not a working week**, and nine rounds is not a distribution. A leak that needs a
  particular interleaving, or that accrues over days, would not appear here.
- **One machine, one platform.** `Spock`, Fedora 44, Wayland. `STARBASE` is not covered, and its
  own scan was removed on 2026-09-03 for a different reason.
- **The scanner's definition bounds all of it.** A process that outlives its parent is what it
  looks for; something leaking that keeps a live parent would pass every scan above, and the raw
  count is the only reason this record can say so.

## Where that leaves `T-302`

The task's first acceptance criterion — establish where orphans actually accumulate — is
**partly answered and by elimination**: not from clean suite runs on this machine. The remaining
candidate is the one this run could not reach, a session that ends badly, and that is where the
next measurement belongs. **No detector is proposed here**, because proposing one against an
unlocated source is how a scan ends up running where orphans are not.
