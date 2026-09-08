# T-298 — the frozen gate reading its own profile, proved on the machine that failed

**Taken:** 2026-08-29 on **`Spock`**, the runner whose profile made `frozen linux` red at run
`33231536419` while `kirk` passed at the same code head.

**Why here rather than in CI.** The acceptance criterion asks that the corrected job pass *on Spock,
with the real user-managed copy still in place*. Runner assignment is not something a workflow can
choose, so a CI run proves it only if it happens to land there. Building the artifact on Spock and
running the probes by hand proves the same thing deliberately, and adds the negative control a CI
run cannot give: **the same artifact, the same machine, one variable changed.**

The maintainer's copy — `~/.local/share/tracksandtrails/ytdlp/yt_dlp-2026.8.19.dist-info`, installed
2026-08-27 through the application — was present before, during and after, and is untouched.

## The pair

Artifact built from `packaging/tracks-and-trails.spec`, exactly as the job builds it.

**A — without isolation. The negative control, and today's CI on this machine:**

```text
FAIL: the artifact bundles yt-dlp 2026.08.19, but this build pins 2026.7.4. The frozen baseline
is not the tested one (T-033, OPS-002).
ytdlp version   2026.08.19
ytdlp source    user-managed copy (OPS-002)
ytdlp pin       2026.7.4
exit=1
```

**B — with the five variables the job now sets:**

```text
ytdlp version   2026.07.04
ytdlp source    bundled baseline
ytdlp pin       2026.7.4
extractors      1751
resolved        youtube from yt_dlp.extractor.youtube
exit=0
```

That reproduces the CI failure and removes it by changing nothing but the profile, which is what
establishes the profile as the cause rather than a correlate.

## The override route still works, which is the criterion a lazy fix fails

Deleting the update probe would also turn the baseline probe green. So the same isolated profile was
made to run it:

```text
before install  2026.07.04 — bundled baseline
installed       9000.1.1
after install   9000.1.1 — user-managed copy (OPS-002)
after revert    2026.07.04 — bundled baseline
OK: install, resolve in a child, and revert all work in the frozen artifact
exit=0
```

**`OPS-002`'s preference is intact**: the artifact still resolves a user-managed copy ahead of its
baseline when one exists — it is now one the job installed, in a directory the job owns. Afterwards
the real profile still holds only `yt_dlp-2026.8.19`, and the isolated profile holds nothing,
because revert removed what it installed.

## Confirmed in CI, and the asymmetry in that confirmation

Run **`33264021710`** put `frozen linux` on **`Spock`** — the machine that failed — and it passed:
`bundled baseline`, `2026.07.04`, 1751 extractors. The update probe installed `9000.1.1`, resolved
it as a user-managed copy and reverted. Afterwards the maintainer's `yt_dlp-2026.8.19` was still in
place, so a full frozen job ran on that machine without touching it. `frozen windows` passed on
`STARBASE`.

**The two legs are not equally proved, and the green does not say so.** On Linux the run is
discriminating, because Spock holds a user-managed copy: without isolation the probe fails, with it
the probe passes, same artifact, same machine. **On Windows it is not.** `STARBASE` has no
user-managed copy to be misled by, so `bundled baseline` is the answer with or without the
overrides — the leg would look identical if `WIN_PD_OVERRIDE_*` did nothing at all.

What supports the Windows half is weaker and worth naming as such: the variables are read by
`platformdirs`' own `windows.py`, which builds the name as
`WIN_PD_OVERRIDE_{csidl_name}`; `tests/ui/test_app_launch.py` has relied on the same pair since
`T-131`; and the update probe demonstrably installed into *some* user-managed location and reverted
from it without leaving anything on the machine. None of that is the negative control Linux got.

**What would close it:** a Windows host holding a user-managed copy while the job runs, or a probe
that prints the user-data directory it resolved so the isolated path can be asserted directly. The
second is the cheaper one and is a change to the probe rather than to the product. Neither is done
here, and until one is, the Windows leg rests on the variable names being correct rather than on
having been caught being wrong.

## What is asserted mechanically, and what is not

`tests/unit/test_frozen_isolation.py` pins the wiring: all five variables present, each varying with
`github.run_id` and `github.run_attempt`, the artifact probes still inside the isolated job, the
update probe still present, the profile removed on `always()`, and **no `runner.*` in a job-level
`env:`**. **Six workflow mutations were run against it** — dropping the Windows pair, dropping
`XDG_DATA_HOME`, making the path stable, deleting the update probe, making cleanup conditional, and
declaring the profile at job level with `${{ runner.temp }}` — and each is caught.

**The sixth is not symmetrical with the other five, which is why it is named.** It is this task's
own first implementation (`efa0ce5`) put back: `runner` is not a context GitHub provides at job
level, so the file was rejected at validation and **every job in the repository stopped running** —
zero jobs, no logs, the run named after its path. `yaml.safe_load` accepts it, so only a test that
asserts the *shape that ran* can hold the line; `a93a53b` is the correction and
`test_no_runner_context_is_used_where_github_will_not_evaluate_it` is the regression.

*(**This section said five** for two commits after `a93a53b` added the sixth — `T298-R1`. Re-run at
`f1b36e9`: unmutated baseline `10 passed`, and all six mutants fail the case named for them.)*

**What no test can assert is the runner's own state.** Nothing in the repository can see that Spock
holds a user-managed copy and kirk does not; that is what made the defect invisible until two
identically labelled machines disagreed. The isolation removes the dependency rather than detecting
it, which is why the fix is environmental rather than a check.
