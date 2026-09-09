# `test_the_scanner_sees_a_known_orphan` — 600 runs, no reproduction

**Taken:** 2026-08-29, soak run `33239854571` at `a7beb50`
**Why:** the test failed on `windows desktop` at `0332a68` and passed at `75cd183`, trees differing
by a workflow comment and a line in `ai/STATUS.md`. One observation is not a rate, and the test is
the one that proves `find_orphans` can see a positive at all — `T-268` turns on what its silence
means.

*(`ai/STATUS.md` is the path in those two trees, and the sentence is a claim about what they
contain — `git cat-file -e 0332a68:ai/STATUS.md` succeeds and `docs/project/STATUS.md` is absent
from both. The file is `docs/project/STATUS.md` on today's tree. A documentation relocation
rewrote the spelling here once, which made a checkable statement about two commits false;
`T299-R2` found it outside a fenced block, where the first class audit did not look.)*

## Result

| Platform | Host | Runs | passed | failed | crashed | seconds (min/mean/max) |
|---|---|---|---|---|---|---|
| Linux | `Spock` | 300 | **300** | 0 | 0 | 0.82 / 0.93 / 1.04 |
| Windows 10 | `STARBASE` | 300 | **300** | 0 | 0 | 2.20 / 2.64 / 7.97 |

**Zero reproductions in 600 runs**, on the same machine and the same platform the failure was seen
on. Every run's log is in the artifact, passes included.

## What that rules out, and what it leaves

**It is not a flake of the test run by itself.** The failure was seen on `windows desktop`, and this
workflow treats the two platforms as different populations on purpose — Windows does not reparent,
POSIX does, and `_parent_is_gone` reaches its verdict by a different route on each. **So the sample
that bears on it is Windows's 300 runs, not the combined 600**: zero events in 300 puts the per-run
failure probability below about **1%** with 95% confidence (rule of three, `3/n`). Linux's 300 clean
runs bound the Linux mechanism to the same 1% and are not evidence about the Windows one.

**The conclusion is unchanged and does not need the larger number.** The observed CI rate — one
failure in three `windows desktop` runs — is two orders of magnitude outside that bound, so the
isolated test and the full-suite test are not the same experiment. **The difference is the context,
not the test.**

*(This read **"600 clean runs put `p` below roughly 0.5%"**, pooling two populations the same
paragraph argues are distinct — `T268-R4`. The pooled figure is not wrong arithmetic; it is the
wrong sample for the claim it supports.)*

The context is the full suite: hundreds of other tests, many of which spawn and reap real
processes, running before this one on a busy machine.

## The mechanism this points at, stated as a hypothesis

`_parent_is_gone` (`tools/orphan_scan.py`) decides orphanhood in three ways: the parent pid does not
resolve, or it resolves to a process *younger* than the child (the pid-reuse guard), or it resolves
to something that is not a Python interpreter.

On Windows the fixture deliberately does **not** wait after `intermediate.wait()`, because
*"Windows does not reparent at all — the parent pid simply stops resolving"*. **If the exited
intermediate's pid still resolves at scan time**, all three tests fail to fire: it is not younger
than its own child, and it is a Python process. `_parent_is_gone` returns `False` and the known
positive is not found — which is exactly the observed failure, whose message reported the parent
still resolving as pid 7752.

**What would make the pid keep resolving longer under a full suite is not established here.**
Handle lifetime on the `Popen` object, garbage-collection timing, and general machine load are all
candidates, and this soak does not separate them. **The pid-reuse guard is not implicated** — a
recycled pid is claimed *after* the child was created, so the younger-than-child rule catches it.

## What would settle it

A probe on Windows that scans immediately after `intermediate.wait()` and records whether
`psutil.Process(intermediate.pid)` still resolves, with and without other load. That is a Windows
run, not a Linux one, and it is not done here.

## The soak's own defect, recorded because it shaped the artifact

Both legs are marked **failed** in GitHub and neither finding is theirs: the workflow piped the tool
into `tee` before creating `reports/`, so `tee` died and `pipefail` failed the step after all 300
runs had completed. The measurements survived in the artifact; the step summary and the
after-the-fact orphan scan were skipped. Fixed in `d0e1d53`. The Linux machine was checked by hand
afterwards and had left **no orphaned workers**.
