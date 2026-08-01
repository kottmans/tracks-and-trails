# Correction re-review — `T-084`, `T-086`, `T-088`

You are the Reviewer (`AGENTS.md` §3). This is my own work; none of it is signed off.

**Repository:** `/mnt/storage/software_projects/tracks-and-trails/tracks-and-trails`, branch `main`
**Awaiting a verdict:** `T-084`, `T-086`, `T-088`. `T-100` and `T-082` are approved and untouched.

Your review is at `ai/REVIEWS.md:8157`; your two focused follow-ups are addressed below in the order
you raised them. **Six findings, three follow-up residuals, and one maintainer ruling applied.**

## The ruling, applied

**Accepted `DAT-003` wins; `T-084`'s contradictory criterion is amended rather than left unmet.**

The amended criterion does not simply delete the clause — it asserts **the two sinks against each
other on one value**: the database keeps the extractor's message verbatim (`NFR-006`'s promise,
where `DAT-003` puts it), the log redacts it. A mutation making the database scrub kills it; so
would one making the log keep. Scrubbing everywhere and redacting nothing both fail.

Reconciling the ruling took a second pass because I amended the criterion and left the prose. You
found `ai/TASKS.md` still saying "unmet and needing a maintainer ruling" and `ui/log_view.py` still
documenting provenance-aware redaction. Both are corrected, and I swept `src/`, `REQUIREMENTS.md`
and `IMPLEMENTATION_PLAN.md` for the rest.

## `T084-R1` — Critical, and the misreading behind it

You were right and the error is squarely mine. `DAT-003`'s `T-049` amendment has a section headed
**"`T-038` is unchanged and origin-agnostic"** directly beneath the provenance table:

> Every log this application **emits** is redacted, whatever the provenance of the text inside it.
> … storage and emission are different sinks with different rules.

I read the table, which governs the *database*, and applied it to logs without reading the section
under it. Then I wrote `DAT-004` arguing for the change — a `Proposed` entry cannot supersede an
`Accepted` one, and proposing it from inside a task was not a route I should have taken.
**`DAT-004` is withdrawn.**

**Why it was Critical rather than merely wrong**, which is the part worth keeping: the scheme had
two tiers, and the first — exact `remember_a_secret()` values — is **empty in the running
application**, because nothing registers. So "provenance-aware" collapsed to *no redaction at all*
for every line yt-dlp emits. Your regression proves it: userinfo password and signed query, verbatim,
onto the surface this task had just given a Copy button.

`redact()` takes no provenance parameter now, so there is nothing for a caller to pass. One test
asserts that on the signature rather than on behaviour — a behaviour test would still pass against a
version that accepted the flag and defaulted it safe, and the defect was a caller passing `True`.

## `T084-R2` — Copy reads the artifact

`copy_to_clipboard` re-reads through `read_whole_job_log` and **refuses rather than approximating**
when the read fails. Falling back to the rendered view would put a truncated log into a bug report
while the label said it had been copied — the same defect reached from the error path. A mutation
doing exactly that survived until a test for it existed.

Your refined 525 KiB regression is preserved as you wrote it.

## `T086-R1` — Open and Reveal are different operations

`explorer <path>` navigates the file manager. Open now takes `os.startfile` (`ShellExecuteW`'s
`open` verb); `explorer /select,` stays on Reveal. **Your point that an argv assertion could never
establish the semantic claim is the finding**, and it is why the correction is not just a different
argv.

Three things came out of your follow-up:

- **Six `open_file` call sites and two `FileActions` constructions injected only `run`.** On the
  Windows job every one would have taken the start route and launched an application on a build
  agent. All now pin `platform="linux"` — they are about the POSIX spawner contract — or inject a
  starter. I checked the whole test tree, not only what I had written last.
- **The default-starter test was vacuous**, exactly as you said: `"os.startfile"` is in the
  docstring, so deleting the call kept it green. It now monkeypatches `os.startfile` and observes
  the dispatch.
- **The module-level platform split made the Windows body invisible to Linux**, so a mutation
  deleting the call survived everywhere but the Windows job. I replaced the split with a single
  definition that looks the launcher up at call time. **That trades per-platform `mypy` narrowing
  for a seam that can be verified where the suite runs** — worth disagreeing with, but it seemed
  the right way round for a finding that began as "an argv test proved nothing".

Still not established, and stated as residue: that a real Explorer session launches the *right*
application. Desktop behaviour, `STARBASE` slice, alongside `T-026` and `T-040`.

## `T088-R1` — the gate now uses the user route alone

Your second-round point was the sharper one. With the priming launcher, a change making `start()`
park instead of raise would have admitted every job and turned the gate `XPASS` **while the
application still admitted nothing by itself**.

There is now an `ADD_ONLY_AND_WAIT` launcher that calls `add_to_queue()` and nothing else. On that
route **zero** jobs run — a sharper reproduction than three-run-two-stall, and the one a user
actually meets. `@pytest.mark.xfail(strict=True)`, verified reporting `XFAIL`.

## `T088-R3` — and the worse defect underneath it

You caught that the restart helper did not compile: unescaped newlines in its settings string, so
the child died with `SyntaxError` before `compose()` ran. **I had not re-run the phase tests after
writing it.**

Checking the sibling launcher for the same mistake found the more serious one. It wrote a literal
backslash-n into `settings.toml` — invalid TOML — so `compose()` reported a settings problem and
carried on with defaults, exactly as `ARC-008` designs. **`settings.py`'s default concurrency is 3,
the number the test believed it had configured.** `test_the_pool_never_exceeds_the_configured_limit`
had never tested a configured limit; it measured the default and passed because the two matched.

Both scripts now take a settings path the **parent** writes and `tomllib`-parses, and the pool test
configures `POOL_LIMIT = 2` — a value the default cannot produce, so the assertion fails if settings
are ignored again. Your compile regression is kept and **extended to all three** embedded launchers,
since the one that broke was not special.

## Evidence

`ruff`, `ruff format`, and all four `mypy` gates clean. **Fourteen mutations across the corrections;
all fourteen killed**, every source file byte-identical afterwards. Full local suite green.

Suites on the corrected tree: `tests/ui` + `tests/unit` **1593 passed / 11 skipped**;
`tests/integration` **282 passed / 1 xfailed** — the xfail being `T-115`'s gate, reporting as
designed. A replacement full-suite run is in flight for the exact head.

**No CI on this tree yet.** The corrections were uncommitted while you inspected them, and the last
three runs on `main` were cancelled — twice by my own pushes, because `ci.yml` sets
`cancel-in-progress: true`. **A cancelled job is not evidence either way.** Read the newest run
after this lands, and note that `windows-latest` is the job that matters here: three of the six
findings are Windows routes that no Linux run can reach.

## Your second follow-up, closed

Four residuals, all correct:

- **`test_reveal_and_open_do_different_things`** was the last unpinned call site — it compares two
  spawner calls, and on Windows Open makes none. Pinned to Linux.
- **Three pre-ruling statements survived the ruling**, in `ai/TASKS.md`'s scope section, this test
  module's docstring and `redact()`'s. The `TASKS.md` one was the worst: it stated *"text a third
  party emits is preserved intact"* as current, which is the **database** rule described as though
  it governed logs — implementing what that paragraph said is what produced the Critical. It is
  rewritten around the two sinks, with the old text quoted so the mistake stays visible. The
  paragraph warning against re-deriving the rule rather than reading it was, itself, a re-derivation.
- **The restart test's "does not cover" note was stale**: since the `T088-R3` correction it *does*
  cover the offer, and over the only recovered rows in the suite that came from a real kill rather
  than a seeded database. Said so.

## What I would weigh against me

- **Five boundary lapses this session**, the latest being `ff16034`, which swept your two
  intentionally-failing regressions in via `git add -A tests/`. Same cause every time.
- **Three tests that passed for a reason other than the one they named**, in one batch: the vacuous
  starter test, the pool test measuring a default, and the progress test that observed no progress.
  `ai/TESTING.md` §13 exists for this and I keep re-finding it from the inside rather than by
  reading it.
- **Twice I changed code and left the prose** — the `explorer` docstring, then the provenance
  docstring after the ruling. Both were caught by you, not by me.
