# The yt-dlp canary, run by hand before the workflow existed

**Taken:** 2026-08-28, during `T-212`'s run, on the maintainer's Fedora machine.
**Why:** `T-291` adds a scheduled job nobody can execute from here. Running its logic by hand is
the only way to know the design works before it is committed — and it changed the design once,
below.

**Method.** The latest yt-dlp installed to a scratch directory with `pip install --target` and put
ahead on `PYTHONPATH`, so the project's own `.venv` was never modified. That is the same mechanism
`OPS-002` uses in the application, and it is viable for the same reason: yt-dlp is pure Python.

```
pinned    : yt-dlp==2026.7.4
installed : 2026.08.19          # the version the maintainer had updated to in-app
```

## What it found

**Nothing.** The option surface and both container lists are unchanged between the pinned baseline
and 2026.08.19.

```
tests/unit, minus the expected-stale pair:   2291 passed, 18 skipped, 2 deselected
tests/unit/test_option_audit.py + test_post_processing_options.py:   42 passed
```

**So the version already in use on this machine is clean by every gate this project has.** That is
worth recording precisely because it is a negative: it is the first time any of those gates has
been shown a yt-dlp newer than the pin.

## What it changed about the design

**The expected-failure set is two tests, not one.** The task entry named one:

- `test_the_audit_names_the_yt_dlp_version_it_was_taken_against` — fails by design, because a bump
  is when the audit has to be re-taken (`T-183`, `NFR-008`).

Running it turned up the second:

- `test_the_installed_baseline_is_the_pinned_one` — which asserts precisely the thing this job
  deliberately breaks.

A canary that ran both would be red on **every** run, which is the failure mode `T-291`'s entry
spends most of its length on: a job that is always red gets muted, and a muted canary hides the
finding it exists to surface. Both are now deselected from the verdict and reported separately,
from **one** definition in the workflow's `env:` block so the reporting step and the excluding step
cannot drift apart.

**Found by running it rather than by reading it**, which is the whole reason this file exists.

## What this does not establish

- **The workflow itself has never executed.** GitHub Actions cannot be run from here; what was
  verified is the logic it performs, not the YAML that performs it. Its first real run is its own
  evidence.
- **`tests/ui` was not run against 2026.08.19 here** — only `tests/unit`. The workflow runs both;
  this dry run stopped at the suite that reaches yt-dlp directly.
- **A clean canary is not a cleared bump.** `OPS-002` attaches a release gate to changing the pin,
  and `ai/TESTING.md` §8 step 10a is where the two meet.
