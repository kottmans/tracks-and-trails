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
| `2026-08-14-T201-next-step-{today,option-a}.png` | **What a ruling is being asked about.** `T201-R3` needs the maintainer to choose where a failure's next step lives, and the cost of one option is only visible as a picture: with the step added, the ffmpeg row's extractor message elides from `--ffmpeg-location` to `--ff…`. Regenerating them needs the rejected option patched back in, which is not something to leave in the tree. |
| `2026-08-14-T242-settings-{light,dark}.png` | **A picture of one head, which is the part that cannot come back.** `tools/settings_screenshots.py` regenerates the *current* Settings screen in one command — so the script is what this directory's rule asks for, and it is committed. What re-running cannot produce is what the screen looked like at `T-242`'s reviewed head, which is what its fourth acceptance criterion asks to be inspectable (`T242-R2`). **The tension is real and this is the resolution**: the generator lives in `tools/`, and only the dated capture lives here. |

**Do not add CI output here.** `reports/` artifacts are uploaded by the workflow and retained for
30 days (`ai/TESTING.md` §10); if one matters beyond that, quote the part that matters into the
task rather than copying the archive.
