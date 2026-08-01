# Review handoff — the last five Phase 2 deliverables, and what proving the phase found

You are the Reviewer (`AGENTS.md` §3). This is my own work; none of it is signed off.

**Repository:** `/mnt/storage/software_projects/tracks-and-trails/tracks-and-trails`, branch `main`
**Awaiting a verdict:** `T-100`, `T-086`, `T-084`, `T-082`, `T-088`. Nothing else is in review.

With these, **every Phase 2 deliverable is written.** `T-088` — the phase's proof — is included, and
**it found a High defect that no feature task would have surfaced.** Read §0 first.

| Commit | Task | What it is |
|---|---|---|
| `c242dd3` | `T-100` | The history view (`REQ-020`) |
| `46c1709` | `T-086` | Open a completed file, or reveal it (`REQ-021`) |
| *(this batch)* | `T-084` | Per-job diagnostics and the log view (`REQ-019`) |
| *(this batch)* | `T-082` | Interrupted jobs offered for retry (`REQ-012`) |
| *(this batch)* | `T-088` | Phase 2's exit criteria in executable form |

`T-046` and `T-087` are filed **Complete** at `eb6f690`, which closed `T046-R6`, `T087-R4`,
`T046-R7` and `T087-R5` from your fourth review. That review is recorded and committed.

## Evidence

`ruff`, `ruff format`, and **all four** `mypy` gates (`src` and full tree, both platforms) clean.
Full Linux suite green. **Forty-seven mutations across the four new tasks;
all forty-seven killed**, every source file verified byte-identical afterwards.

Windows carries no new surface here — none of these touch the platform seam except `T-086`, whose
Windows argv is asserted **from Linux** by design (§3).

## 0. `T-088` found that nothing drains the queue — `T-115`

**Start here.** Measured against a real composed application, concurrency 3, five URLs added through
the real dialog:

```
  0.5s  probing  running  probing  queued  queued   (4 child processes)
  8.0s  completed completed completed queued queued (1)
  9.5s  completed completed completed queued queued (1)
```

Three ran concurrently and completed. **The other two stayed `queued` with an empty pool.**

The pool is fine; nothing drives it. `_fill_free_slots` drains an **in-memory** list that only the
internal path populates; the public `start()` **raises** when full rather than parking; nothing
scans the database for `QUEUED` rows; and `add_to_queue` starts only the **probed** job, with Probe
a manual button covering the first URL alone. So a user who pastes five URLs and presses Add gets
**zero** downloads, or one if they probed.

`add_dialog.py` already has a comment reading *"leaving it durably `QUEUED`, where whatever runs the
queue next would download the URL"*. There is no such thing.

Filed as **`T-115`** with three placement options stated and none chosen — where the fix belongs is
a design decision and `T-088` is not the place to make it. Recorded as a **strict `xfail`**, so
**fixing it fails the build** until the test is inverted rather than leaving this file describing a
defect as behaviour.

**What I want checked:** that criterion 1 is now marked honestly. `T-079`'s acceptance criterion is
satisfied and correct — three concurrent downloads do show independent accurate progress. The
evidence table says *mechanism met, no user route*, and I would rather be told that is too harsh
than have it read as met.

## The four things I would look at next

### 1. `T-084`: yt-dlp's diagnostics were never being captured at all

`REQ-019` has said "the actual yt-dlp diagnostic output for that job" since Phase 0. `T-038` built
per-job log files, `T-053` proved they stay isolated under a saturated pool — and `build_options`
set **no `logger`**, so yt-dlp's output went to a console a worker does not have. The per-job log
existed, was correct, and contained this application's own lines only.

Two things I measured rather than assumed, both of which changed the design:

- **`logger` overrides `quiet` and `no_warnings`.** Read in yt-dlp 2026.07.04: `to_screen` calls
  `logger.debug(...)` and **returns before consulting `quiet`**; `report_warning` consults `logger`
  before `no_warnings`. Both flags stay because they are right when no logger is passed, but they
  now read as doing something they do not. **Worth disagreeing with.**
- **`verbose` must stay off, for a security reason rather than a volume one.** Measured: it makes
  yt-dlp dump `params:` and `Proxy map:`, carrying the proxy URL and `cookiesfrombrowser` — values
  *this application supplies*, `DAT-003`'s first row. The version banner a bug report wants is
  written by `worker._log_the_session_header` instead, where every field is chosen here.

The near-miss worth knowing about: yt-dlp routes ordinary output to `logger.debug`, and the worker's
handler sits at `INFO`. A bridge logging it at `DEBUG` would have produced a job log that is
**created, empty, and entirely plausible**. There is a test named for exactly that.

### 2. `DAT-004` is proposed, and one question in it is yours to rule on, not mine

`T-084`'s criterion requires the boundary asserted **in both directions**, and says why: *"A gate
that only proves the first would pass an implementation that scrubs everything, which is the failure
`DAT-003` records twice."* `T-038` redacted by **shape**, which satisfies the first and fails the
second — a cookie path yt-dlp itself named matched `_COOKIE_PATH` and was removed.

So redaction now asks **who wrote the line**: exact registered secrets are removed from everything,
and the pattern rules apply only to lines this application wrote. Both directions hold **on the same
string**, in one file, which no shape-based rule could produce.

**The part I did not decide.** `DAT-003` says it reopens for *"a bug report attaching it"* — and this
task ships a Copy-diagnostics button whose entire purpose is that. I implemented `DAT-003` as
written and made the copied text the file verbatim. I did **not** invent a second, more-scrubbed
rendering for the clipboard, because that would be writing a specification rather than implementing
one, and `NFR-006` argues against it. The trigger condition is met in fact. **A maintainer ruling is
owed**; the seam is one call — `redact(text, third_party=...)` — and the view is its only caller.

### 3. `T-086`: the platform is a parameter, so Windows is asserted from Linux

`explorer /select,<path>` is one argv element, comma and all; split into two it silently opens the
parent folder **without selecting anything**, which looks close enough to working to survive a
careless manual check on Windows. With `sys.platform` read inline that line could only ever be
checked on Windows. As a parameter of every command builder, the exact Windows argv is asserted by
the ordinary suite on any machine.

`T-086`'s criterion said "verified on `STARBASE`"; it is **narrowed** the same way `T-087`'s was, per
`T087-R4`'s pattern and the `OPS-005` amendment. What is *not* covered is that a real Explorer
selects the file when handed that argv — desktop behaviour, and it stays with the `STARBASE` slice
alongside `T-026` and `T-040`.

Also: `shell=True` is refused by a guard that raises, with a test that fires it, rather than by a
`noqa` nothing checks. `ruff`'s `S603` fires on the one `subprocess` call in the package and I would
rather answer it with an invariant than a comment.

### 4. `T-082`: the recovery was correct and completely invisible

`compose()` called `recover_interrupted()` and **threw the returned ids away**. So a user who lost
twelve downloads to a crash saw twelve failed rows and no acknowledgement that anything had happened.
The offer is a `QMessageBox` following `report_settings_problem`'s precedent, with **`Not now` as
both the default and the escape button** — Enter or Escape at startup must not begin twelve
downloads.

The third criterion was genuinely violated: `recover_interrupted` called `update()` per job, and
`update()` opens its own transaction, so recovering a queue was one commit and one fsync per row on
the path that runs *before the window appears*. Now one transaction, counted with sqlite3's trace
callback rather than asserted about.

**Where I would push back on myself:** accepting the offer is N retries, one per job, through the
same injected `retry` the per-job button uses. That is N writes. I hold that criterion 3 is about
*recovery* — which the user cannot decline and which precedes the window — and that a bulk path in
the manager would be a second definition of "retry" that can drift from the first. If that trade is
wrong it is one call site.

## CI caught 38 Windows failures I pushed unrun

`T-086` and `T-084` reached `main` green on Linux and **red on `windows-latest`** — 38 failures
across `test_reveal.py`, `test_file_actions.py` and `test_log_view.py`, every one a Linux-only
assumption in a *test* rather than a defect in the code. Fixed in a follow-up commit; the causes:

| What | Why it only failed there |
|---|---|
| Hostile filenames written to disk | Windows forbids `"`, `\|` and a newline in a filename — so the fixture for the argv test failed on the platform the argv is *for*. Nothing needed writing; the builders are pure |
| `str(path)` compared against `as_uri()` | A Windows path is forward-slashed in a URI and backslashed otherwise, so containment found nothing — and would have reported "spread across 0 arguments", a defect that is not there |
| `["xdg-open", …]` hardcoded in the wiring tests | They now assert against the platform's own builder |
| `chmod(0o000)` as the unreadable-file fixture | Does not remove read access on Windows, does not stop root on Linux — and the assertion `in ("", "text")` passed whether or not the guard existed. The error is now injected at the real call site |
| `write_text` translating `\n` → `\r\n` | A character-for-character assertion compared against a file the test did not think it wrote |

**Worth weighing against me:** this is the second time this session something reached `main` without
the platform gate seeing it. The first was four failing tests pushed unrun. This one *was* run — on
one platform — which is the more dangerous version, because it felt like compliance with
`AGENTS.md` §8.

*(Also: `test_a_killed_holder_leaves_a_lock_the_next_launch_can_take` failed on `windows-latest` in
one run and passed in the next with nothing changed between them. **Flaky, not a regression** —
recorded rather than chased. It is the `T-074` class.)*

## Three things my own tests got wrong, found by mutation

Not offered as contrition — they are the places a reviewer should look hardest, because a test I had
to fix once is a test I may have fixed shallowly.

1. **`T-086`: nothing asserted that Show-in-folder built the *reveal* argv.** Wiring both actions to
   `open_file` passed every test in the file. A mutation doing exactly that survived until
   `test_reveal_asks_the_file_manager_to_show_the_file_rather_than_opening_it` existed.
2. **`T-084`: the bound test wrote 2.5 MB against a 4 MiB total**, so a file that never rotated
   passed it. It now asserts the *live* file against `MAX_JOB_LOG_BYTES`.
3. **`T-082`: I had written a guard the code did not earn.** An early return for "nothing to
   recover", commented as avoiding a needless fsync. Measured: `with connection` issues **nothing**
   when no statement runs inside it. The guard is gone; the comment now says why there is no guard.

And two claims I withdrew rather than defended:

- A test said passing yt-dlp's text as a `%`-argument prevented it being read as a format string.
  `logging` applies `%` only when a record carries args, so both spellings are identical. The
  docstring says so now and the test asserts what is real.
- The end-to-end test's `verbose` assertion was a **guard that cannot fire** — verbose lines are
  prefixed `[debug]`, go to `DEBUG`, and are dropped at the worker's `INFO` handler for a second
  unrelated reason. It is asserted on the options dict instead.

## A defect in my own work that the full suite caught and a single file did not

`JobProgressView` built its `LogView` with no directory, so it read the **real** `user_cache_dir`.
The diagnostics focus-order test passed alone and failed in the full run, because a `job-1.log`
written by some other test made the copy button live. `log_directory` is now threaded through. It
was never wrong in production — but a widget whose content depends on machine state is untestable,
and I would not have found it from the file I was editing.

## `T-088`: two things the tests had to be careful about

**The rows lead the processes.** `start()` writes `PROBING` through the writer thread and the worker
spawns after, so three rows can claim to be in flight with an empty process tree — measured at
t = 0.0 s. My first version waited on the rows, raced the spawn, and made
`the_workers_that_must_die` fire its own guard. It was correct to fire. Waiting on the **processes**
is the fix; weakening that guard would have been the `T072-R1` mistake a third time.

**A kill during a probe is not a kill during a download.** Both are "mid-queue" and
`INTERRUPTED_ON_STARTUP` covers both, but a kill that always landed while workers were resolving
URLs would never exercise what a user loses — bytes in flight.

## What is still not verified

- **A real Windows desktop session.** The desktop slice does not run on a hosted image.
- **`T-092`'s three machine-dependent criteria**, unchanged — `STARBASE` is offline.
- **That a real file manager selects the file** given `T-086`'s reveal argv, per §3 above.
- **Phase 2 cannot exit.** Criterion 6 needs this review, and criterion 7 needs `T-115`. The
  evidence table in `ai/IMPLEMENTATION_PLAN.md` now states, per row, what its evidence does not
  cover — building Phase 1's table is what exposed two wrong rows (`P1EXIT-R1`, `P1EXIT-R2`).
