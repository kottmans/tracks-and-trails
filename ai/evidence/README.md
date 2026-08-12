# `ai/evidence/` — artifacts that cannot be regenerated

**This directory is an exception, and it should stay small.** Everything else in `ai/` is prose,
and evidence normally lives *inside* the task or review that reasons about it — `T-074` carries its
361 attempts as a sentence, not as 361 files. That is the right default: a number somebody has read
and thought about is worth more than a directory nobody opens.

**Put a file here only when re-running the thing would not produce it again.** The test that
qualifies is not "was this expensive" but "could I get it back". A slow but deterministic run does
not belong here; its command line does.

What is here now:

| File | Why it cannot be regenerated |
|---|---|
| `SOAK-FAILED-13.txt`, `SOAK-FAILED-19.txt` | The only two observations of `T-128`'s segfault, from 39 full-suite runs. Reproducing one takes hours and may not succeed; these are the stacks the investigation has to work from. |
| `T238-SEGFAULT-gw7.txt` | The only observation of `T-238`'s worker segfault, from a run in which the machine was also busy. 37 further `-n auto` runs on an idle machine have not reproduced it. The Python and C stacks are what the investigation has to work from — same case as the two above. |
| `mutation.json` | 1185 mutants over six modules. Regenerable in principle, but it is the baseline the next mutation run is compared against, and a diff needs both sides. |

**Do not add CI output here.** `reports/` artifacts are uploaded by the workflow and retained for
30 days (`ai/TESTING.md` §10); if one matters beyond that, quote the part that matters into the
task rather than copying the archive.
