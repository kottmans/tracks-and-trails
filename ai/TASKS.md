# TASKS.md — Tracks & Trails

**Purpose:** Track concrete, actionable work.
**Authority:** Canonical for current actionable work and its state.
**Owner:** Planner (creates/prioritizes) · Implementer and Reviewer (update status)
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-28
**Update when:** A task starts, blocks, changes scope, completes, or is cancelled.
**Does not contain:** Phase planning (`IMPLEMENTATION_PLAN.md`), progress narrative (`STATUS.md`).

Statuses: Proposed · Ready · In Progress · Blocked · In Review · Complete · Cancelled.
IDs are never reused. Completed tasks move to `ai/archive/` once they bury the live queue.

**Start here:** **Phase 1's critical path is built and approved**, and the queue is no longer
only paperwork. `T-036` composed the object graph and `T-037` proved a download completes and
survives a `SIGKILL`. **What stands between the phase and its exit review is a crash, a carry, and
frozen-artifact evidence.**

- **`T-074` — the live problem.** The Windows suite exits with an **access violation**, roughly
  one run in four, in the result pump's ordinary message delivery. **High**, filed 2026-07-29, not
  diagnosed. It matters out of proportion to its age because `OPS-005` and `T-073` just made that
  suite Phase 1's only Windows gate, so an intermittent crash devalues every green run of it.
- **`T-072` — In Progress, Changes requested.** `COORD-R5`, `WIN-R3` and `RUNNER-R1` are resolved;
  `T066-R1` and `WIN-R1` are written and **both still open on their evidence** (`T072-R1`,
  `T072-R3`). Also carrying `T072-R2` and this preamble's own `COORD-R6`.
- **`T-073` — In Review**, approved with the `T073-R1` documentation follow-up. The self-hosted
  job now runs the whole Windows gate: 1388 passed, 20 skipped.
- **Blocked on evidence:** `T-066`, narrowed to frozen-artifact evidence alone once its
  process-tree half was discharged. `T-033` and `T-039` are Phase 5.
- **Open, not phase blockers** (`OPS-005`): `T-056` and `T-068`. Both need a GitHub-hosted image,
  neither is a defect a user would meet.
- **Complete:** `T-040`, `T-060`, `T-064`, `T-065`, `T-067`, `T-069`, `T-070`, `T-071`.

**Both halves of exit criterion 7 now have a platform, and it is still unmet.** `OPS-005` made
`STARBASE` the Windows platform; `OPS-006` made the maintainer's own machine the Linux one, rather
than building a runner that would share the development box's environment. `T-074` is why the
criterion cannot yet be called met: a gate that crashes intermittently does not verify reliably.

*(This block said "nothing remains on the path" and listed only a carry, runner evidence and the
exit review, while omitting `T-074` entirely and calling `T-072` and the completed `T-064` Ready.
`COORD-R6` reported it — the same filing class `COORD-R5` was meant to close, recurring in the
task that carries it. Rewritten from current task state rather than patched.)*

**A Windows machine on the maintainer's network — `STARBASE` — supplied what CI could not**
(2026-07-28), and is now a self-hosted runner. Windows 10 22H2, Python 3.14.6 and PySide6 6.11.1
matching the runners. GitHub Actions hosted usage is exhausted (workflow `30392139504` failed
before executing a step, on the billing annotation). STARBASE answered most of what was owed, but
it is **not** a substitute for `windows-latest`: `T-056`'s defect does not reproduce there at all,
20/20, with a positive control proving the mutation applied.

**Every Phase 1 deliverable filed *before* 2026-07-28's CI run is approved** — and that is a
narrower claim than the one this block used to make. Running the tests where they had never run
added tasks, one of which is a defect a user would meet. **Phase 1 is not ready.**

*(This block previously said `T-068` and `T-069` were "not fully closed", listed `T-060` as
Blocked and `T-066`…`T-070` as In Review, and described `T-062`, `T-061` and `T-063` as the
current front. All of that outlived being true: `T-069` is approved, `T-060` is complete, and the
three named tasks are long filed. `COORD-R5` reported the drift; rewritten rather than patched.)*

*(This block read "until `T-060` lands, the `windows desktop` job fails on
`test_the_progress_view_focus_chain_is_walked_on_a_real_desktop`". It landed: run `30388380440`
is green on all five jobs. Kept as a note rather than deleted, because the reasoning stands — a
skip would have left the one job that runs those tests green while proving nothing.)*

*(This block described `T-016` as In Review at `33ebd11`, `T-017` as "the only substantive task
startable right now", and `T-040` as Ready — all true on 2026-07-27 and none of them true a day
later. `COORD-R1` reported it. Rewritten rather than patched, which is the same discipline the
mandatory-area count needed twice.)*

Phase 0 is formally exited (2026-07-26).

---

## In Review
*(Holds `T-073` as of 2026-07-29. It was briefly empty on 2026-07-28 after `COORD-R5`'s refiling,
and this note went on claiming that after `T-073` was filed In Review under `## Ready` —
`COORD-R6`, which is `COORD-R5`'s own failure mode recurring one day later. `COORD-R2` is why this
section carries a note at all rather than sitting blank: an empty section is a claim about
readiness, and the last time it was left unlabelled it outlived being true by one CI run. The
lesson this file keeps relearning is that the claim has to be rewritten when the section changes,
not when someone notices.)*

### T-073 — Run the full Windows gate on the machine that can run it

**Status:** **In Review — approved with a documentation follow-up**, 2026-07-29 at `c41e2ef`.
The reviewer accepted the job shape: the real `windows` plugin for the 28-test desktop slice,
`offscreen` for the Qt baseline and the default suite, no provisioning of the self-hosted machine,
ffmpeg recorded, and 30 minutes allowed. All fourteen functional steps passed. `T073-R1` is the
open follow-up — two evidence statements in this task were wrong, corrected below.
**Owner:** Implementer
**Priority:** **High** — it is what makes Phase 1's seventh exit criterion attemptable again
**Phase:** Phase 1
**Depends on:** `OPS-005`; the self-hosted runner established 2026-07-28
**Relevant context:** `OPS-005`, `T-066`, `T-062`, `ai/TESTING.md` §12, `IMPLEMENTATION_PLAN.md`
Phase 1 exit criteria
**Affected surfaces:** `.github/workflows/ci.yml`, `ai/TESTING.md`
**Risk:** Medium — it puts the project's whole Windows gate on one machine

#### Scope

`OPS-005` made `STARBASE` the platform *verified on Windows* is measured against, and then had to
record that the criterion was still unmet: the self-hosted job ran the 28-test desktop slice and
two integration modules, while `check (windows-latest)` — lint, format, types, the Qt baseline and
the full suite — had not run anywhere since the hosted quota ran out.

Give the self-hosted job the rest of that gate. It already builds a virtualenv on a real Windows
machine, so the marginal cost is steps rather than infrastructure.

**No provisioning.** The one hard rule this job already carries is that a self-hosted runner must
never install software as a side effect of running a test — the first run of it launched the real
Python installer, opened an interactive dialog, and deadlocked against `msiexec` for the full
timeout. So where `check` runs `choco install ffmpeg`, this job **records** ffmpeg instead. That is
affordable because the default suite does not need it: measured on Linux with `ffmpeg` removed from
`PATH`, **1399 passed, 11 skipped, 2 deselected** — the same numbers as with it.

**The job keeps its name.** `windows desktop` is referenced by `ai/TESTING.md`, `ai/REQUIREMENTS.md`
and `IMPLEMENTATION_PLAN.md`, all describing a desktop role that is still true and still its
reason for existing. Renaming would invalidate those and the review record for no gain; the
expanded role is recorded in `ai/TESTING.md` instead.

#### Acceptance criteria

- The self-hosted job runs lint, format, the Qt baseline and the full suite, in addition to what it
  already ran
- The full-suite step runs **offscreen**, and the desktop slice keeps the real `windows` plugin
- Nothing in the job installs software on the machine
- ffmpeg's presence or absence is recorded, and the run states which configuration it measured
- The job's timeout accommodates a full suite, rather than passing by finishing early
- `ai/TESTING.md` records that this job now carries the Windows gate, and what still differs from
  the hosted one

#### Evidence, 2026-07-29

Run **`30415333608`** at `c41e2ef`, job `windows desktop` on `STARBASE`. **All fourteen steps
green**, **6 m 29 s** wall (job `90460498381`).

*(This said 3 m 40 s — `T073-R1`. That was the gap between two log timestamps I happened to grep,
not the job's wall time, which Actions records directly. Corrected rather than left as a number
nobody would re-derive.)*

| Step | Result |
|---|---|
| Types under the Windows platform | Passed |
| Windows desktop suite (real `windows` plugin) | 28 passed |
| Lint | All checks passed |
| Format check | 103 files already formatted |
| Qt baseline | OK: Qt baseline verified on this runner |
| **Full suite** (offscreen) | **1388 passed, 20 skipped, 30 deselected in 208.44 s** |

**The machine has ffmpeg**, which the plan did not assume: `ffmpeg 8.1.2-full_build`, installed by
winget at `…/Gyan.FFmpeg…/bin/ffmpeg`. So this run measured the **with-ffmpeg** configuration, the
same one `check (windows-latest)` measures via `choco`. The no-ffmpeg wording in the environment
step is the branch that did not fire, and the recording is what makes that knowable rather than
assumed.

**Reconciling the counts against Linux**, which is where a difference would otherwise look like a
gap:

| | Linux | Windows |
|---|---|---|
| Passed | 1399 | 1388 |
| Skipped | 11 | 20 |
| Deselected | 2 | 30 |

The deselections explain themselves: Linux deselects the 2 network tests, Windows deselects those
plus the 28 `windows_desktop` tests — which is correct, because step 8 already ran them under the
real plugin. The extra 9 Windows skips are the POSIX-only half of platform-split modules.

**The residual is explained, and it is an identity rather than a discrepancy** (`T073-R1`). Total
collected plus deselected is 1412 on Linux and 1438 on Windows. Linux's JUnit carries two
module-level **"collection skipped"** placeholders, for `tests.ui.test_windows_accessibility` and
`tests.ui.test_windows_desktop`; Windows replaces those two placeholders with the 28 real desktop
cases. `1412 - 2 + 28 = 1438`, exactly the recorded count.

*(This was filed as "two tests unaccounted for … not something to wave through", which was the
right instinct and the wrong conclusion — the answer was in the JUnit output rather than in the
counts. Kept because a reader who re-derives the arithmetic will hit the same 26-against-28 and
deserves the resolution, not the question.)*

#### Out of scope

- Retiring `check (windows-latest)` or the `frozen` jobs. They stay; this makes their absence
  survivable, not permanent
- The Linux half of `check`, which is unaffected
- `T-056` and `T-068`, downgraded by `OPS-005` and not revisited here

---

## Ready

### T-074 — The Windows suite segfaults intermittently while the result pump is delivering

**Status:** **Ready — observed and filed 2026-07-29**, not diagnosed
**Owner:** Implementer
**Priority:** **High** — it is an access violation in a module under `src/`, and it lands in the
suite that `OPS-005` and `T-073` just made Phase 1's only Windows gate
**Phase:** Phase 1
**Depends on:** nothing. It needs the Windows runner, which exists
**Relevant context:** `T-073`, `OPS-005`, `ARC-002`, `src/tracks_and_trails/downloader/result_pump.py`
**Affected surfaces:** unknown — `downloader/result_pump.py` and/or
`tests/integration/test_manager.py`
**Risk:** **High to leave.** An intermittent crash makes every green Windows run mean less than it
appears to

#### Scope

The full suite on `STARBASE` died with exit **139**:

```
tests/integration/test_manager.py::test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget
Windows fatal exception: access violation
Thread 0x00000c88 [ResultPump] (most recent call first):
Thread 0x000024dc [Thread-50 (_monitor)] (most recent call first):
  File "...\tests\integration\test_manager.py", line 1028 in
    test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget
Segmentation fault
```

**It is intermittent, and the evidence for that is unusually clean.** The failing run was
`30416495270` at `454b80e` — a **documentation-only** commit whose code is byte-identical to
`38650dd`, which had passed the same suite minutes earlier.

| Run | Head | Full suite |
|---|---|---|
| `30415333608` | `c41e2ef` | pass |
| `30416156751` | `38650dd` | pass |
| `30416495270` | `454b80e` | **access violation** |
| `30416723791` | `32f9bd2` | pass |

**One in four**, with no code difference between a pass and the failure.

**Line 1028 is before the cancellation**, which narrows this usefully. It is
`assert spin(lambda: bool(recorder.progress), timeout=60)` — the wait for the *first progress
message*, three lines above `download.cancel()`. So the crash is not in the escalation path the
test is named for. It is in ordinary message delivery: `ResultPump` is a `QThread` emitting Qt
signals carrying Python objects from its `run()`, while the main thread sits in `spin()` calling
`app.processEvents()`.

#### What is not known

Everything about the cause. Recorded as a question rather than a hypothesis dressed as one:

- Whether the fault is in **product code** (`result_pump.py`, in `src/`, so `ARC-002`'s pump is a
  candidate) or in the **test harness** (fixture teardown ordering, a receiver outliving or
  predeceasing a queued emission).
- Whether it is specific to `child_ignoring_cancellation`, which is the one worker in the suite
  that deliberately refuses to stop, or reachable by any job.
- Whether it reproduces at all outside `STARBASE`. It has never been seen on Linux across many
  full-suite runs, but Linux has never been where this project's process faults show up.

#### Diagnostic progress, 2026-07-29 — two things narrowed, cause still unknown

**It does not reproduce on Linux.** Two attempts, both clean:

| Attempt | Result |
|---|---|
| The crashing test alone, 40 iterations | **40 passed, 0 non-zero exits** |
| `tests/integration/test_manager.py` entire, 5 runs | **5 × 71 passed**, no crash, no fatal exception |

That is a negative result and is worth exactly what a negative result is worth. It does **not**
clear Linux: `T-069` was ordering-dependent and failed only when one specific test ran first, and
the Windows crash happened inside a full-suite run, not a module run. What it does establish is
that the fault is not reachable by simple repetition of the failing test on this platform, so
whatever it is depends on the platform, on suite-wide ordering, or on both.

**The most obvious cause is already defended against, and this is the more useful half.** The
classic PySide6 access violation of this shape is a `QThread` object being destroyed while its
`run()` is still executing — and `ResultPump` emits `session_ended` from *inside* `run()`, so a
slot that dropped the last reference would do exactly that. It cannot: `_release()` in
`manager.py` refuses to drop a session while its pump is live —

```python
if session.pump_started and not (session.pump_finished or session.pump.isFinished()):
    return
```

— and `_sessions.pop()` is the only thing holding the pump. `_Session` even documents the two
moments as distinct: "the thread emits `session_ended` from inside `run()`." So the first
hypothesis anyone would reach for is not it, which is worth recording so nobody spends the
afternoon re-deriving it.

**Still open.** The crash traceback named two threads — `[ResultPump]` and
`Thread-50 (_monitor)`, which is `multiprocessing`'s — and the fault was at the wait for the first
progress message. Whether it is the pump, the queue read beneath it, the interaction between them,
or the harness remains unanswered. Nothing here should be read as narrowing it to product code.

#### Acceptance criteria

- The failure is **reproduced deliberately**, with a rate, rather than waited for
- The faulting thread and the object it touched are identified — a stack is not a cause
- The fix is proven by a mutation that restores the crash, not only by runs that stop crashing
- If it turns out to be the harness rather than the pump, that is recorded explicitly, because
  the opposite conclusion is the one a reader would assume from the file it crashed in

#### Out of scope

- Retrying, `xfail`, or a rerun plugin. `T-069` established the rule: an intermittent failure gets
  its trigger found, not its symptom hidden. The one time this project reached for a retry the
  reviewer's instruction was explicit — *do not retry or xfail*
- `T-056`, which is a different intermittent on a different platform and is `OPS-005`-downgraded

---

### T-072 — Carry the three unresolved findings the last-pass direction stopped

**Status:** **In Progress — four of the five carries are done, 2026-07-29.** `COORD-R5` is
discharged and `T-040`/`T-060` are filed Complete on it; `WIN-R3` and `RUNNER-R1` are corrected;
the `T-019` process-tree cases run on `STARBASE`. `T066-R1` was **Changes requested** at
`f20a9c8` (`T072-R1`) and is corrected below. **`WIN-R1` is written too**, so all five carries are
addressed — but two things are owed before this can close: the `mut_tree_drop_worker` mutation on
Windows, and a run of `ssh-setup.ps1` against a machine carrying the broad rule. Both are
described with their exact commands below. See **Progress**.

*(This block said "three of the five" and called `T066-R1` unexecuted after its run had already
happened — `T072-R2`, and the same current-truth drift `COORD-R5` is about, in the task that owns
`COORD-R5`. Rewritten rather than patched.)*
**Owner:** Implementer
**Priority:** Medium — it is the only thing standing between `T-040`/`T-060` and closure
**Phase:** Phase 1
**Depends on:** nothing to start. Its `T066-R1` half **needs a Windows runner**; the other two
halves do not
**Relevant context:** `ai/REVIEWS.md` — "STARBASE evidence and T-066 through T-070 review" and
"STARBASE correction focused re-review", both 2026-07-28
**Affected surfaces:** `tests/integration/test_end_to_end.py`, `tests/integration/test_manager.py`,
`tools/windows/ssh-setup.ps1`, `docs/WINDOWS_VERIFICATION.md`, `.github/workflows/`,
`ai/TASKS.md`, `ai/STATUS.md`
**Risk:** Low per item; Medium as a group, because two of the three are gate-vacuity problems

#### Scope

The correction re-review closed under the maintainer's **last-pass direction**: remaining
Medium-or-lower work is carried into a named task rather than starting another correction loop.
This is that task. It exists because the reviewer asked for it by name, and until it did not
exist, `T-040` and `T-060` had nowhere to carry their residue — which is the only reason those
two are not closed.

**Three blocking carries:**

- **`T066-R1` (Medium).** The whole-tree termination fix is accepted and it resolved `T-069`. What
  remains is that `kill_the_application()` suppresses every `psutil` kill error and discards both
  lists returned by `wait_procs`, so it can return and reopen the database with a known survivor.
  The no-survivors probe is reported but is not a lasting assertion. Separately, `T-066`'s own
  criterion covering the `T-019` process-tree cases has never run under the Windows venv — the
  self-hosted job runs `windows_desktop` only.
- **`COORD-R5` (Medium).** The gate statement is corrected: `REQUIREMENTS`, `IMPLEMENTATION_PLAN`,
  `TESTING` and `T-026` now agree Windows tab order is gated. The residual is filing. `## In
  Review` still says it is empty while `T-066`…`T-070` sit In Review under `## Ready`; `T-040` and
  `T-060` sit In Review under `## Blocked`; the `TASKS` preamble still calls `T-060` Blocked; and
  `STATUS` says `T-040`/`T-060` are In Review and then, later in the same file, that `T-069` is
  unfixed and `T-040` is Blocked. These are current-truth files and the stale paragraphs are not
  marked superseded.
- **`WIN-R1` (Medium).** `ssh-setup.ps1` now preserves and deduplicates administrator keys, and a
  newly created firewall rule is correctly Private + LocalSubnet. But its idempotent path looks up
  `sshd-tt` and does nothing when it already exists, so a machine that ran the earlier broad `Any`
  rule stays broad on every later run. A tool documented as safe to re-run does not repair the
  unsafe state it created.

**Two non-blocking carries**, which the re-review asked to travel with this work:

- **`WIN-R3` (Low).** `docs/WINDOWS_VERIFICATION.md` still names `mut_control_always_dead.py` as
  the focus driver's control; the actual control is `mut_control_chain.py`. The named file belongs
  to `T-056`, not to the `T-026` focus harness.
- **`RUNNER-R1` (Low).** The workflow comment and the Windows guide say `timeout-minutes: 15`
  bounds time spent queued while `STARBASE` is offline. It bounds how long a job may **run**; an
  unmatched self-hosted job stays queued for up to **24 hours**. The current text understates this
  single-machine gate's outage window by almost a day.

#### Acceptance criteria

- A surviving process in either `wait_procs` list **fails the test**; the expected descendant set
  is a lasting assertion rather than a reported probe
- `T-019`'s process-tree cases are executed and recorded from the Windows venv, or `T-066`'s
  criterion is rewritten to say what is actually gated and why
- Re-running `ssh-setup.ps1` against a machine carrying the broad `Any` rule leaves it scoped, and
  the script reports the effective profile and remote-address filter it ended with
- One unambiguous current answer, in authority order, about which tasks are In Review, Blocked and
  Complete — including the `## In Review` section's own emptiness claim. (`T-071` was the same
  class of drift and was filed to `## Complete` on 2026-07-28, ahead of this task.)
- Historical statements are preserved as explicitly historical, not deleted
- `WIN-R3` and `RUNNER-R1`'s documentation is corrected to what the code and GitHub actually do

#### Progress, 2026-07-28

| Carry | State |
|---|---|
| `COORD-R5` | **Done.** See below |
| `WIN-R3` | **Done.** The guide now names `mut_control_chain.py`, says it runs first, and records why the `T-056` control does not belong here |
| `RUNNER-R1` | **Done.** `ci.yml` and the guide now say `timeout-minutes` bounds *run* time, and an unmatched self-hosted job queues for up to 24 hours |
| `T066-R1` | **Corrected after `T072-R1`.** One mutation still owed on Windows — see **The `T072-R1` correction** |
| `WIN-R1` | **Written, unverified.** See **The `WIN-R1` correction** |
| `T-019` cases under the venv | **Done.** Run `30414186949`, 72 passed, 3 skipped |
| `T072-R2` | **Resolved.** This status block was the drift it reported |

**`COORD-R5` is discharged.** Every task now sits in the section its verdict says it belongs in:
`T-040`, `T-060`, `T-067`, `T-069`, `T-070` and `T-065` to `## Complete`; `T-066` and `T-068` to
`## Blocked`. The `## In Review` note no longer claims an emptiness it did not have, and names
where each former occupant went. The `TASKS` preamble and `ai/STATUS.md`'s Windows and `T-040`
paragraphs are rewritten from the current head, with every superseded reading kept as an
explicitly historical parenthetical rather than deleted.

**`T066-R1` is written but has not run, and that matters.** `kill_the_application()` now asserts
that the walked tree is deeper than the pid `Popen` returned, and that `wait_procs` reports **no**
survivors before the caller reopens the database; refused kills are collected and reported in the
failure rather than suppressed. `NoSuchProcess` during the kill loop is still tolerated, because
racing with a tree that is already dying is a kill and not a miss.

That code is inside `if sys.platform == "win32"`, so **the Linux suite did not execute one line of
it.** What it has: `mypy --platform win32` passes on it, which is `AGENTS.md` §8's check and is
what caught the previous POSIX-only mistake in this same file. What it does not have: any runtime
evidence at all. It needs the Windows job before it can be called resolved.

**The runner is the answer to that, and it did not need the quota.** `STARBASE` is online and
green — run `30413774102`, job `windows desktop`, **28 passed, 1410 deselected in 12.83s**, while
all four hosted jobs failed at zero steps on the billing annotation. Since that job already builds
a venv on a real Windows machine, it is the only place the required process shape exists. It now
carries a *Process trees under the venv* step running `tests/integration/test_manager.py` and
`tests/integration/test_end_to_end.py` by path.

Pre-flighted on Linux with `ffmpeg` removed from `PATH`, because the desktop job installs none:
**75 passed**. That is what says the step will not turn the one green job red for a missing
dependency rather than for a finding.

#### Evidence, on the runner — 2026-07-29

Run **`30414186949`** at `185ea6d`, job `windows desktop` on `STARBASE`. All ten steps green;
*Process trees under the venv* reports **72 passed, 3 skipped in 79.69s**.

**The caveat above is discharged.** `test_a_job_killed_mid_download_is_recovered_by_the_next_start`
PASSED, and it is the test that calls `kill_the_application()` — so the `T066-R1` assertions
executed on Windows, under a virtualenv, and the tree they walk really was deeper than the pid
`Popen` returned. Had it been one level, the first assertion would have failed rather than the
step passing.

The `T-019` cases ran under the same shape for the first time anywhere:

| Case | Result |
|---|---|
| `test_a_worker_killed_from_outside_does_not_leave_its_grandchild_behind` | **PASSED** — the grandchild case, which is the whole subject |
| `test_cancelling_a_download_kills_what_the_worker_spawned` | **PASSED** |
| `test_a_real_worker_leads_its_own_process_group` | Skipped — POSIX process groups |
| `test_a_descendant_is_asked_to_stop_before_it_is_killed` | Skipped — POSIX signalling |
| `test_the_detector_still_ignores_the_resource_tracker` | Skipped — POSIX only |

The three skips are the POSIX-only half of a file that is deliberately split by platform; nothing
Windows-relevant was skipped. **No hosted minutes were used**, and all four hosted jobs in the
same run failed at zero steps on the billing annotation.

| Check | Result |
|---|---|
| `ruff check .` | All checks passed |
| `ruff format --check .` | 103 files already formatted |
| `mypy` | Success: no issues found in 78 source files |
| `mypy --platform win32` | Success: no issues found in 78 source files |
| `pytest` (full default suite) | **1399 passed, 11 skipped, 2 deselected** |
| `pytest tests/integration/test_end_to_end.py` | 4 passed |

#### The `T072-R1` correction — 2026-07-29

**The assertion was vacuous, and the review proved it rather than argued it.**
`len(doomed) > 1` reads like a check on the walk and is not one: under the venv shape the launcher
and the application interpreter already make that two, so the **worker** could be missing and it
still passed. Codex reduced `children(recursive=True)` to direct children — `len(doomed) == 2`,
the helper returned successfully, and the omitted worker went on downloading. The handoff had
flagged this assertion as the least certain one; the failure mode found is sharper than the one
guessed at.

**Identity now comes from a handshake, not from a count.** `DOWNLOAD_AND_WAIT` prints
`os.getpid()` alongside the job id, so the test knows the application interpreter rather than the
launcher. `capture_the_doomed_tree()` walks from *that* pid while the row still says `RUNNING`,
asserts the application has at least one descendant — the worker, which is the entire reason the
kill means anything — and returns that exact set. `kill_the_application()` no longer walks; it
kills what it was handed and asserts nothing survived.

#### `T072-R1`, third round — the oracle was counting the wrong process

**The second correction separated the lists and then conflated the processes.**
`the_workers_that_must_die()` returned *every* descendant, which under `multiprocessing` means the
**resource tracker** as well as the worker. The tracker outlives the worker, so the positive
control failed on the tracker while calling it a worker — and a reviewer's mutation that killed the
application and the tracker but deliberately spared the real worker **passed in 1.38 s**. The
control had teeth only for "some long-lived descendant".

Three things were wrong, and the third was the one that mattered:

1. **The tracker was in the set.** Excluded now, by the same `multiprocessing.resource_tracker`
   marker `tests/integration/test_manager.py` has always used for the same reason.
2. **`mut_tree_shallow_walk` patched the oracle as well as the capture**, so it shrank the check
   and the checked thing together. It now touches `capture_the_doomed_tree` only.
3. **The clip was too short for the assertion to mean anything.** 512 KiB in 32 KiB chunks at
   0.05 s finished in under a second, so a worker that survived the kill exited *naturally* long
   before any check noticed — the assertion would have passed with no kill at all. The test now
   paces at 0.5 s and waits **5 s**, deliberately shorter than the download still in flight. The
   passing case costs nothing: `wait_procs` returns as soon as everything is gone.

**Measured, on Linux:**

| Plugin | Result | Why |
|---|---|---|
| `mut_control_worker_survives` | **KILLED**, 6.4 s | The kill is disabled, the worker is genuinely still downloading, and the failure names **one** pid — the worker, with the tracker excluded |
| `mut_tree_shallow_walk` | Survives | The capture walks from the application, whose direct children already include the worker. Shallow and recursive differ only if the worker spawned its own child. Unobservable, like `T060-R2`'s reversal |
| `mut_tree_drop_worker` | Survives | `killpg` reaches the whole group whatever was captured |
| Reviewer's spare-the-worker | Survives | **And this is the interesting one — see below** |

**Sparing the worker is unkillable on Linux because the product handles it.** `worker.py`'s
**orphan guard** — `spawn_session()` watches the parent and exits if it disappears — reaps the
worker when the application dies, whether or not anything killed it directly. The two controls
prove it as a pair: with the kill disabled the application lives and the worker is still running at
6 s; with the application killed and the worker deliberately spared, the worker is gone in 1.4 s.
That is `REQ-015`'s orphan guard working, not a hole in the oracle, and it is recorded as the
measured outcome the re-review asked for rather than forced into a kill.

**Which makes the Windows run the whole remaining question.** `T-066` measured the opposite there:
the grandchild **survived** `process.kill()`. Either the orphan guard does not fire on Windows or
it does not fire in time, and that difference is exactly what `mut_tree_drop_worker` is for on
`STARBASE`.

#### `T072-R1`, second round — the assertion was still circular

**The first correction moved the fault rather than fixing it.** It asserted `not alive` against
`doomed` — *the same list the kill was handed* — so a fault that dropped the worker from that list
also dropped it from the assertion, and nothing could fail on any platform. Both checked-in
mutations were built on that misunderstanding: one returned `[]` and proved only that an entirely
empty walk trips a guard nobody doubted, and the other could not be caught even on Windows.

**The check and the thing it checks now come from different sources.**
`the_workers_that_must_die()` is the test's own record of the worker set, taken while the row says
`RUNNING`. `capture_the_doomed_tree()` is what the kill is handed. Nothing downstream can shrink
the first, so a `doomed` missing the worker fails against it.

| Plugin | Linux | Why |
|---|---|---|
| `mut_control_worker_survives` | **KILLED** | The positive control. `kill_the_application` does nothing, the worker outlives it, and the independent set catches it by pid |
| `mut_tree_shallow_walk` | Survives | The capture walks from the *application*, whose direct children already include the worker. Shallow and recursive differ only if the worker has spawned its own child — ffmpeg, on a merge — which a progressive download does not. **Unobservable, like `T060-R2`'s reversal**, not a gap |
| `mut_tree_drop_worker` | Survives | `killpg` reaches the whole group whatever was captured. Structurally ungateable on POSIX |

**The control is why the two survivals are readable.** Two surviving mutations and no kills is
indistinguishable from an assertion that cannot fail — which is the exact shape `T072-R1` found
twice. `mut_control_worker_survives` fails with the surviving pid *and* the list the kill was
handed, so the diagnostic names which of the two possibilities occurred. Same reasoning that puts
`mut_control_chain` first in the focus driver.

**Still owed:** `mut_tree_drop_worker` on Windows. That is where the captured set's completeness
becomes observable, because Windows kills members one at a time.

| Check | Result |
|---|---|
| Baseline, unmutated | 1 passed |
| `tests/integration/test_end_to_end.py` | 4 passed |
| `ruff check .` · `ruff format --check .` | Passed · 105 files already formatted |
| `mypy` · `mypy --platform win32` | Success, 78 source files · Success, 78 source files |
| Full suite | 1399 passed, 11 skipped, 2 deselected |

**On Windows**, run `30416156751` at `38650dd`:
`test_a_job_killed_mid_download_is_recovered_by_the_next_start` **PASSED** inside the full suite —
1388 passed, 20 skipped, 205 s. That exercises the correction end to end on the platform it was
written for: the handshake parsed, `capture_the_doomed_tree` found the worker as a descendant of
the *reported* pid under the venv shape (a walk that had not would have failed the new assertion),
and nothing survived the kill.

**What that run does not establish**, stated because the previous version of this task was
approved on exactly this kind of gap: a green run is not a demonstrated kill. The two mutations
have not executed on Windows. `mut_tree_drop_worker` in particular can only be gated there, and
until it runs, the completeness of the captured set is argued rather than measured.

#### The `WIN-R1` correction — 2026-07-29

The existing-rule branch did nothing and then printed `rule present`, so a machine that had run
the earlier broad `Any` version kept port 22 open on every network profile, on every subsequent
run, while the script reported success. **A tool documented as safe to re-run has to repair the
state it created, not merely decline to make it worse.**

- The branch now reapplies the intended scope with `Set-NetFirewallRule` — `Private` profile,
  `LocalSubnet` remote — instead of skipping.
- The rule is then **read back and reported**: enabled, action, profile, remote address, port.
  The scope lives on two different objects — the profile on the rule, the remote address on an
  associated filter — so a rule that looks correct in `Get-NetFirewallRule` alone can still allow
  the world. Both are printed.
- A mismatch warns and names the rollback: `Remove-NetFirewallRule -Name sshd-tt`, then re-run.

**Unverified, and not verifiable from here.** There is no PowerShell on the Linux development
machine, and the repair path specifically needs a Windows box **already carrying the broad rule** —
a state that has to be created deliberately to test against. What was checked is static: balanced
braces and parentheses, no statements inside string interpolation (the Windows PowerShell 5.1
hazard this file documents), and the CRLF policy `.gitattributes` sets.

The CI runner cannot answer this either, and should not: reconfiguring a machine's firewall from a
workflow is the *provisioning* hazard `T-073` and the job's own comments exist to prevent.

**How to verify on `STARBASE`**, in an elevated session:

```powershell
$ErrorActionPreference = "Stop"

# Broaden the EXISTING rule. Do not try to create it.
Set-NetFirewallRule -Name sshd-tt -Profile Any -RemoteAddress Any

# Assert the defective state really exists, or the run below proves nothing.
$before = Get-NetFirewallRule -Name sshd-tt
$beforeRemote = (Get-NetFirewallAddressFilter -AssociatedNetFirewallRule $before).RemoteAddress
if ($before.Profile.ToString() -ne "Any") { throw "setup failed: profile is not Any" }
if ($beforeRemote -ne "Any") { throw "setup failed: remote address is not Any" }

.\tools\windows\ssh-setup.ps1
```

The script must then report `rule profile : Private` and `rule remote : LocalSubnet`. Before this
correction it would have reported `rule present` and changed nothing.

**`T072-R3` corrected this procedure, and the way it was wrong is the point.** It previously used
`New-NetFirewallRule -Name sshd-tt` to "recreate" the broad rule. On the machine this repair
targets that name **already exists**, so the command fails — and the script then reapplies and
reports an already-scoped rule, producing a green-looking report *without ever exercising
broad-to-scoped repair*. A verification procedure that passes when the thing it verifies never
ran is the same class of fault as the assertion `T072-R1` found. Hence `$ErrorActionPreference`
and the two explicit `throw`s: the setup has to fail loudly rather than quietly leave the machine
in the state that makes the test vacuous.

#### Out of scope

- Another behavioural review of `T-040` or `T-060`. The re-review states they may close as
  Approved-with-follow-up on this carry **without** one
- `T-066`'s external blockers — the four hosted and frozen jobs — which need quota, not work
- `T-056`, which wants `windows-latest`'s image and is not part of this carry
- Any further automatic correction round on the findings above

**Note:** the reviewer's closing instruction is the authority for this task's existence and its
contents. If a carry here disagrees with a task's own status line, `ai/REVIEWS.md` is canonical
for review findings (`AGENTS.md` §12).

---

## Proposed — Phase 0

### T-021 — Simplified small-size icon glyph

**Status:** Proposed
**Owner:** Implementer (needs a design decision from the maintainer first)
**Priority:** Low
**Phase:** Phase 4 (theming) — not a Phase 0 exit condition
**Depends on:** `T-003`
**Relevant context:** `T-003` completion note, `ARCHITECTURE.md` §8
**Affected surfaces:** `src/tracks_and_trails/resources/icons/`
**Risk:** Low — cosmetic only

#### Scope

**This is an enhancement, not a defect fix.** `T-003`'s 16 px asset meets its acceptance
criterion — the note and gold trail stay recognizable (`T003-R2`). What it loses is the
landscape: the trees and mountain collapse into the green mass. That is a property of the
artwork's detail level, not of the scaling method, so no better downscale recovers it.

Draw a reduced glyph for 16 px and 24 px that keeps only the elements that still read at that
size — the note head and stem plus the gold trail sweep — dropping the trees and mountain.
Ship it as a separate size-specific asset so Qt picks it for small requests.

#### Acceptance criteria

- At 16 px and 24 px the glyph is **more legible than the current downscale**, judged
  side by side — not merely legible, which the current asset already is
- The glyph is recognizably the same mark as the full logo, not a different one
- The Windows `.ico` embeds the simplified glyph at 16/24 and the full logo at 32 and above
- The `T-022` resource tests still pass, with their expected frame set updated if it changes

#### Out of scope

- Redesigning the logo itself
- Any change to the brand hex values fixed by `T-003`

**Note:** this is a judgment call about brand appearance, so it needs the maintainer's
agreement on the reduced form before implementation.

---

## Proposed — Phase 1

## Proposed — Phase 2

### T-050 — Write the history table

**Status:** Proposed — Ready now; `T-013` produces the event that fills it
**Owner:** Implementer
**Priority:** Medium — `REQ-020` has no owner without it, and the table already exists empty
**Phase:** **Phase 2** — `IMPLEMENTATION_PLAN.md` lists "History persistence and
completed-download records (`REQ-020`)" among Phase 2's deliverables, and the plan outranks
this file (`AGENTS.md` §5). It was filed under Phase 1 first, because `T-014` had already
created the table and `STATUS.md` said `T-013` would fill it; that was this file drifting
ahead of the plan, not the plan being wrong.
**Depends on:** `T-013`
**Relevant context:** `REQ-020`; `ARCHITECTURE.md` §5 (`HistoryEntry`);
`persistence/schema.sql` (the `history` table `T-014` created)
**Affected surfaces:** `core/models.py` or `persistence/` (wherever `HistoryEntry` lands),
`persistence/repositories.py`, `downloader/manager.py`, `tests/unit/`
**Risk:** Low — an append-only record; nothing depends on it yet
**Review base:** the `T-013` merge commit

#### Scope

**Filed after implementation: nothing owned this.** `STATUS.md` said `T-013` "owns writing the
`history` table `T-014` created but left empty", but `T-013`'s scope, acceptance criteria and
affected surfaces never mentioned it, and `TASKS.md` outranks `STATUS.md` (`AGENTS.md` §5). It
was left undone deliberately rather than guessed at, because two pieces are genuinely missing:

- **There is no `HistoryEntry`.** `core/models.py` says so explicitly and gives the reason — it
  is a durable record rather than live domain state, so it belongs with the schema that stores
  it. No repository exposes the table either.
- **`history.format_used` has no source.** Nothing reports the format yt-dlp actually selected;
  `Succeeded` carries the path and the byte count. Filling the column from the request's
  *format selector* would store a different fact under a truthful-looking name — `bestvideo+
  bestaudio` is not a format that was used. Either the worker projects the chosen format into
  the outcome, or the column is left null and the schema says why.

Decide the first of those, then write a row when a job completes, from the manager, in the same
place the terminal transition is persisted.

#### Acceptance criteria

- A completed download writes exactly one `history` row, and a retry of the same job does not
  silently duplicate it
- `format_used` either carries the format yt-dlp actually used, reported from the worker, or is
  null with the reason recorded — never the selector wearing that name
- A cancelled or failed job writes no history row (`REQ-020` is a record of what was obtained)
- The manager still imports no `persistence` module: history goes through an injected protocol,
  as the job repository does (`T-013`, `ARCHITECTURE.md` §3)

#### Out of scope

- Any history UI — Phase 3 (`REQ-020`'s view)
- Pruning, retention, or export

---

### T-053 — Prove concurrent per-job log isolation

**Status:** Proposed — blocked until the Phase 2 pool permits two live sessions
**Owner:** Implementer
**Priority:** Low — Phase 1's structural routing is correct; concurrency is the missing proof
**Phase:** Phase 2
**Depends on:** `T-038` and the Phase 2 task that implements `REQ-013`
**Relevant context:** `T038-R2`; `ARCHITECTURE.md` §8; `REQ-013`, `REQ-019`;
`ai/REVIEWS.md` (2026-07-27 T-019/T-038 focused correction re-review)
**Affected surfaces:** `tests/integration/test_worker_logging.py`
**Risk:** Low until concurrency exists; High if the pool ships without the proof
**Review base:** the Phase 2 concurrency implementation head

#### Scope

Phase 1 runs one session at a time. `T-038` proves that worker records carry a job-id stamp and
that a per-job handler rejects every other stamp, using two sequential jobs. That establishes
per-job routing, but it cannot establish the concurrent cross-write property while the manager
refuses to keep two sessions open.

When Phase 2 first permits two live sessions, coordinate two real spawned workers so both
per-job handlers are open at the same time. Have both workers emit interleaved, unique markers
through the production log queue and prove that each file contains its own complete stream and
none of the other job's.

This is not the current `T038-R2` ordered-drain correction. `T-038` must already retain a
worker's final emitted records and stop its listener without blocking the GUI thread before this
follow-up becomes relevant.

#### Acceptance criteria

- Two real worker sessions are simultaneously active before either emits its test records
- Their records are deliberately interleaved through the production worker-log queue
- Each per-job log contains every marker its worker emitted and no marker from the other worker
- The application log still contains both streams
- Removing the job-id filter or stamp makes the test fail

#### Out of scope

- Implementing Phase 2 concurrency or its scheduling policy
- Repairing the current single-session ordered-drain and non-blocking-shutdown defect in
  `T038-R2`

---

### T-046 — Output path collision policy against the filesystem

**Status:** Proposed — Phase 2, alongside resume
**Owner:** Implementer
**Priority:** Medium — **raise to High before first release.** Until this lands, two downloads
whose titles sanitize to the same component contend for one path
**Phase:** Phase 2
**Depends on:** `T-034`, `T-045`, and the download manager (`T-013`)
**Relevant context:** `DAT-002`; `ARCHITECTURE.md` §8; `REQ-011`
**Affected surfaces:** the download manager's path selection; `core/paths.py` remains pure
**Risk:** Medium — the failure mode is one download overwriting another's output

#### Scope

**Filed by `DAT-002`, which is where the reasoning lives.** `T-045` established that
`sanitize_component` cannot promise a unique path: it is a pure function of one string, and
"does this collide with something?" is a question about the filesystem. The maintainer kept
idempotence and narrowed the sanitizer's promise to the plausible neighbour class, moving real
uniqueness here.

This task owns the guarantee at the layer that can keep it — the one that knows what is already
on disk and what other jobs are queued. That covers the ordinary case, not only the reserved-name
residue: two different videos whose titles sanitize identically collide today by the same
mechanism, and always have.

**`core/paths.py` stays pure.** The resolution belongs to the caller that has filesystem context;
pushing it into the sanitizer would make it stateful and re-open `DAT-002`.

#### Acceptance criteria

- Two jobs whose sanitized components are equal resolve to distinct output paths
- The resolution is visible in the `REQ-011` preview before the write, not applied silently
  afterwards — a preview that disagrees with the write is the failure `DAT-002` protects against
- An existing file at the target is never silently overwritten
- Concurrent writers cannot both win the same path — asserted against real concurrent jobs
  rather than by inspection, since Phase 2 is where the second worker arrives
- The residual collision `T-045` pins is covered by this policy, so `DAT-002`'s assumption that
  `T-046` lands before first release is discharged

#### Out of scope

- Which names are legal or reserved — settled by `T-034` and `T-045`
- Resume semantics for a partially downloaded file, beyond not colliding with one

---

### T-047 — Decide whether the environment ownership gate's blind spots are worth closing

**Status:** Proposed — **not scheduled.** Carries `T044-R1`'s residue
**Owner:** Planner, then Implementer if the answer is yes
**Priority:** **Low, and deliberately so.** The question is whether to spend anything here at
all; the honest default answer is no
**Phase:** unassigned
**Depends on:** `T-044`
**Relevant context:** `T044-R1` and its six review rounds in `ai/REVIEWS.md`; `ai/TESTING.md`
("What the environment ownership gate actually promises"); `ARCHITECTURE.md` §6
**Affected surfaces:** `tests/unit/test_environment.py` only
**Risk:** Low — no production code is involved, and none ever was

#### Scope

`T-044`'s gate reports any public attribute of `downloader/environment.py` not bound by an
`import` statement, under the configuration the suite runs in. Three gaps are pinned by test and
carried here:

1. **Anything behind a guard false at run time** — OS, architecture, dependency presence,
   feature probe, environment state.
2. **A name imported and then rebound** — `try: from x import Y / except ImportError: Y = ...`,
   the ordinary shape of an optional dependency, where the parse subtracts a name the fallback
   genuinely bound.
3. **Dynamic rebinding of an imported name** — `globals()["Path"] = ...`.

**Read the history before proposing a fix.** `T044-R1` was found six times. Every attempt to
close it by recognising more syntax was defeated by syntax the author had not enumerated, and
three attempts to state its coverage overclaimed and were disproved. That is the strongest
available evidence that the next clever fix will also be wrong, and it is why this task's first
deliverable is a *decision*, not a patch.

The likely correct answer is **no**. Gaps 1 and 3 need a determined author to trigger; gap 2 is
plausible but would announce itself the moment anyone read the module. The gate catches what it
exists to catch — an accidental `get_ytdlp_version()` — and `ARCHITECTURE.md` §6's boundary is
independently guarded by the layering test and by review.

#### Acceptance criteria

- A recorded decision, with reasoning, on whether any gap is worth closing
- If **no**: this task closes, and `ai/TESTING.md`'s statement of the promise stands as the
  durable record. Nothing in the tree changes
- If **yes** for a given gap: the fix must come with evidence it does not reintroduce the
  enumeration failure — specifically, a demonstration against binding syntax the fix does not
  name, since that is how all five previous fixes died

#### Out of scope

- Any production change to `downloader/environment.py`. The gate is a test; the module's
  behavior has never been in question
- Strengthening the layering test, which uses `ast.walk` and is unaffected

---

### T-048 — Verify the first real data migration when one is written

**Status:** Proposed — **not schedulable yet.** No migration transforms data
**Owner:** Implementer, when the first data migration is authored
**Priority:** Medium at that point; nothing to do before
**Phase:** unassigned
**Depends on:** the first migration that changes stored values
**Relevant context:** `T014-R4`; `ai/TESTING.md` §7 (Migrations)
**Affected surfaces:** `tests/unit/test_persistence.py`

#### Scope

`T-014`'s migration test asserts strict per-column equality, which is correct while every
migration is pure DDL and any change is loss. It will be **wrong** the day a migration
legitimately transforms values.

A `TRANSFORMED_BY_MIGRATION` allowance was written and then removed: `T014-R4` established that
an allowance can conceal a corrupt-but-readable migration, and an empty allowance protects
nothing while adding a mechanism nobody has exercised. Designing it against a real migration
beats designing it against an imagined one.

#### Acceptance criteria

- The first data migration ships with a test asserting the transformed values are **correct**,
  not merely different — a readable row holding wrong data is the failure mode `T014-R4` named
- Untransformed columns stay under strict equality
- The v1 fixture remains untouched; a new version freezes its own

#### Out of scope

- Any change to `T-014`'s current strict comparison, which is right until then

---

### T-049 — Tighten DAT-003 before cookie-file support

**Status:** Proposed
**Owner:** Planner
**Priority:** Medium before cookie-file support or first release
**Phase:** Phase 4
**Depends on:** none
**Relevant context:** `DAT-003`, `REQ-026`, `T014-R1`, `T-038`
**Affected surfaces:** `ai/DECISIONS.md`, `ai/REQUIREMENTS.md`, `ai/TASKS.md`

#### Scope

The maintainer accepted DAT-003's controlling trade-off: third-party diagnostic prose is stored
verbatim in the local, user-owned database, even when it names a cookie path. That closes
T014-R1. Its explanatory table is narrower than the decision it records, however:

- a user-supplied source URL may itself contain userinfo and is stored verbatim under the earlier
  URL decision;
- `cookies_from_browser` is passed to yt-dlp as a browser name, but the model currently accepts
  any non-empty string, including a path-shaped one; and
- arbitrary third-party prose cannot support an exhaustive claim that a cookie path is the
  "only residue." The accepted boundary is provenance, not enumeration of what yt-dlp may say.

Rewrite DAT-003's table and linked notes around that actual boundary. Add the missing reopening
condition: REQ-026 already promises cookie-file support, so the decision must be revisited before
the application adds a cookie-file path or any other secret-bearing field to a persisted job.
Keep T-038 origin-agnostic: every emitted log is redacted regardless of whether its text began in
this application or yt-dlp.

#### Acceptance criteria

- DAT-003 makes no exhaustive claim about the contents of arbitrary third-party diagnostics
- User-entered source URLs, model fields supplied by the application, and yt-dlp-emitted prose
  are distinguished explicitly
- Adding cookie-file support or another secret-bearing persisted field is a named reopening
  condition alongside sync, export, cloud backup, and database attachment
- T-038 still requires redaction of the final emitted log regardless of message provenance
- `REQ-026` and T-014's historical criterion link to the same scoped decision without acquiring
  a second competing definition

#### Out of scope

- Reopening T-014 or changing its approved persistence code
- Implementing cookie-file settings or log redaction

---

## Blocked

### T-066 — CI installs the project differently from how the documentation says to

**Status:** **Blocked — on frozen-artifact evidence only**, narrowed 2026-07-29. **The
process-tree half is discharged:** `T-072` added a *Process trees under the venv* step to the
self-hosted `windows desktop` job, and run `30414186949` executed the `T-019` cases under the venv
shape for the first time anywhere — 72 passed, 3 skipped, the grandchild case among the passes.
`T066-R1`'s survivor assertions ran there too. What remains is the frozen-artifact shape: both
`frozen` jobs are hosted and have not started since the quota ran out.

*(This said "on Windows process-tree and frozen evidence" until the runner supplied the first
half.)*
**Owner:** Implementer
**Priority:** **High** — it decides whether `T-019`'s process-tree evidence describes the
environment a developer or a user actually has
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `T-019`, `T-056`, `docs/DEVELOPMENT.md`, `.github/workflows/ci.yml`
**Affected surfaces:** `.github/workflows/ci.yml`, `docs/DEVELOPMENT.md`, possibly
`tests/integration/test_manager.py`
**Risk:** Medium — no product code is wrong; what is wrong is the environment the gate measures

#### Scope

`docs/DEVELOPMENT.md` tells a developer to work in a virtualenv. `ci.yml` installs with
`python -m pip install -e ".[dev]"` straight into the `setup-python` interpreter, with no venv at
any point. **The gate and the documentation describe different environments**, and on Windows the
difference is not cosmetic.

`python -m venv` on Windows does not copy the interpreter into `Scripts\python.exe`; it installs a
launcher that **spawns the real interpreter as a child**. Measured on `STARBASE`, 2026-07-28:

| Install | `Popen(sys.executable)` | interpreter that ran |
|---|---|---|
| venv, as `DEVELOPMENT.md` documents | 10500 | **7356** |
| no venv, as CI installs | 11352 | 11352 |

So under the documented setup every `multiprocessing` spawn sits one level deeper than it does on
CI, because `sys.executable` is a redirector. `test_the_detector_sees_a_grandchild_and_not_just_a_worker`
fails in the venv checkout and passes in the CI-style one, on the same machine and the same
commit — an A/B, not an inference.

**Why this is more than a failing test.** `T-019` exists to prove the application reaps a process
*tree* on Windows, and `T-056` exists because the helper that decides those assertions was
imprecise. Both are verified only against the shallower tree. The deeper tree is the one a
developer following our own instructions produces, and plausibly the one a user of a venv-based
install produces too.

#### Acceptance criteria

- The divergence is resolved rather than documented: either CI installs the way `DEVELOPMENT.md`
  says to, or `DEVELOPMENT.md` stops saying it, and whichever is chosen is justified in writing
- If the venv shape is the one to support, `T-019`'s descendant-reaping assertions are shown to
  hold under it, on Windows, with the extra level present
- Whether the frozen artifact (`T-020`, `T-033`) has the shallow or the deep shape is answered,
  since that is what a user actually runs
- `test_the_detector_sees_a_grandchild_and_not_just_a_worker` states which shape it assumes

#### Evidence, 2026-07-28

**Resolution: CI adopts the virtualenv** (maintainer decision). Every job creates `.venv` and
prepends it to `GITHUB_PATH`, so the commands `ai/TESTING.md` §4 publishes stay identical. On
Windows the path is converted with `cygpath -w`: `shell: bash` there is Git Bash, whose `$PWD` is
an MSYS path the runner itself cannot resolve.

Testing the deeper tree is the superset — reaping that works with an extra generation works
without one — which is why this direction rather than deleting the venv from the docs.

**`test_the_detector_sees_a_grandchild_and_not_just_a_worker` asserted more than it needed.** It
required `ppid() == child.pid`: exactly one hop. That is true only when `sys.executable` starts
the interpreter directly, and in a venv on Windows `Scripts\python.exe` is a launcher that spawns
the real interpreter, so `child.pid` is the launcher and the grandchild sits one level further
down. The test failed with "this test is not about a grandchild at all" while looking at a tree
that was *deeper* than it expected.

It now asserts **at least two generations below the test process**, which is the property the
detector actually has to satisfy, and which holds under both install shapes. Verified passing in
both the venv and the no-venv checkout on Windows, and on Linux.

**My first attempt at that fix was wrong**, and it is worth recording why: I measured generations
from `child.pid` rather than from the test process, so a correct Linux tree (test → child →
grandchild) reported one hop and failed. "Grandchild" is relative to the process doing the
walking, not to the process that was spawned.

**The frozen artifact has neither shape.** Under PyInstaller `sys.executable` is the frozen
executable and `multiprocessing` re-launches it through `freeze_support()`, so there is no
launcher generation and no venv. This is **reasoned, not measured** — building the artifact on
Windows is `T-033`'s ground and no frozen build has been run on `STARBASE`. Recorded as an
assumption rather than a result.

**Partly verified as of 2026-07-28.** The virtualenv step **has now executed on Windows**: job
`90432207805` of run `30405803368` ran `Create the virtualenv` and then the desktop suite under
it, green. That is the self-hosted runner, so it covers the Windows half of the change.

**The four GitHub-hosted jobs have still never run it** — quota is exhausted and every hosted job
fails before its first step. So the Linux half, the `frozen` jobs, and `cygpath -w` on a
*hosted* Windows runner are all unverified. `ai/TESTING.md` §11's "local green is not evidence"
still applies to those.

#### `T066-R1` — the crash tests killed one level, 2026-07-28

The finding: *Windows crash tests kill the venv launcher PID, without proving the application
interpreter was killed.* Measured, with the crash test's own `CREATE_NEW_PROCESS_GROUP` flags:

| Process | After `process.kill()` |
|---|---|
| the pid `Popen` returned (the venv launcher) | dead |
| its child (the application) | dead — the launcher's Job object propagates |
| **its grandchild (the worker)** | **alive** |

So the literal mechanism in the finding is not what happens — the interpreter *is* killed, by the
Job object the venv launcher creates. **The consequence the finding points at is real and worse**:
the kill reaches exactly one level, and under a virtualenv the worker is two levels down. A test
whose entire subject is an application dying mid-download was leaving the download running.

`kill_the_application` now enumerates the tree **before** killing anything — once the parent is
gone its children are reparented and the walk finds nothing — and kills all of it, which is what
the POSIX branch has always done via `killpg`. Still `TerminateProcess`, so nothing unwinds.

| Evidence | Result |
|---|---|
| three-level probe, before | grandchild and one sibling **survive** |
| three-level probe, after, through the real `kill_the_application` | **tree reaped**, no survivors |
| `test_end_to_end.py` ×5, before | **4 failed** |
| `test_end_to_end.py` ×5, after | **5 passed** |

**This is why `T-019`'s sibling tests deserve the same look.** They were written on a machine with
no Windows, from a design argument about Job objects and parent watchdogs that is half right: the
Job object exists and does propagate — one level.

#### Out of scope

- Changing how `multiprocessing` starts workers
- The Qt font failure and the long-path failure seen in the same run (`T-067`, `T-068`)

---

### T-068 — Qt writes a font warning to stderr on a real Windows machine

**Status:** **Blocked — on the disclosed runner and frozen questions**, 2026-07-28. The
environment fix itself was not contested: the warning was the symptom, and the defect is that Qt
had **zero font families** under `offscreen` on that machine, so the whole offscreen UI suite ran
with no fonts. `QT_QPA_FONTDIR` is set before PySide6 is imported, is Windows-only, and honours an
explicit caller value. The task's own acceptance criteria still require the runner difference to
be explained and a Windows frozen artifact to be checked; both need a hosted runner. See
**Evidence**.

**No longer a Phase 1 exit dependency** (`OPS-005`, 2026-07-29). Still open, still Blocked. This
one runs the *other* way from `T-056`: the defect appeared **on** the real machine and the hosted
runners are the ones that look clean, so the fix is already validated where the fault was. What
remains is the diagnostic question of why the runners never showed it — worth answering, not worth
holding a phase for.
**Owner:** Implementer
**Priority:** Medium — an assertion about a *clean* run is failing, and the cause is not understood
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `T-007`, `tests/ui/test_app_launch.py`, `OPS-004`
**Affected surfaces:** `tests/ui/test_app_launch.py`, possibly packaging
**Risk:** Medium — unknown cause; it may be cosmetic, and it may be a deployment gap

#### Scope

`test_application_launches_and_exits_cleanly` asserts the application writes nothing to stderr on
a clean run. On `STARBASE` it writes:

```
QFontDatabase: Cannot find font directory <prefix>/PySide6/lib/fonts.
Note that Qt no longer ships fonts. Deploy some ... or switch to fontconfig.
```

**It fails in both the venv and the CI-style install**, so it is not the virtualenv — an
A/B that also corrects the implementer's first guess, which was that the venv caused it. The
cause is genuinely unknown and this task exists to find it rather than to silence it.

Two reasons not to treat it as noise. It only appears on a machine that is not a CI runner, which
is exactly the population `OPS-004` was written to stop assuming about. And a Qt that cannot find
a font directory under the offscreen platform raises an unanswered question about the **frozen**
artifact, which is what a user runs.

#### Acceptance criteria

- The cause is identified — not "PySide6 does that", but why this machine and not the runner
- Whether the frozen build (`T-020`, `T-033`) shows the same warning is answered on Windows
- If the warning is benign, the test says so deliberately rather than being loosened to pass
- If it is not benign, the fix is in packaging or startup, not in the assertion

#### Evidence, 2026-07-28

**The warning was the symptom. The defect is an empty font database.** Measured under
`QT_QPA_PLATFORM=offscreen` on `STARBASE`, in the interactive desktop session:

```
FAMILIES 0
SAMPLE  []
DEFAULT Sans Serif
```

Zero families. So the **entire offscreen UI suite** runs there against no fonts: every assertion
about a widget's size, about elision, or about anything else derived from font metrics is measured
against nothing — and passes. A suite that agrees with itself while measuring an empty font set is
the shape `ai/TESTING.md` §13 exists to catch, which is why this was not allowlisted into
`PLUGIN_NOISE` alongside `propagateSizeHints`. That allowlist is for artifacts that change no
measurement; this one changes every measurement.

**Not our code.** A bare `QApplication` produces nothing; a bare `QLabel` reproduces it in full,
with no project code involved. Same result in the venv and the no-venv checkout, which also
corrects the first guess recorded against this task — it is not the virtualenv.

**Not the session either.** It reproduces identically in session 2, so it is not an artifact of
running over SSH, which was the other plausible explanation and had to be ruled out because
several other results were.

**Fix:** `tests/conftest.py` sets `QT_QPA_FONTDIR` to `%WINDIR%\Fonts` on Windows, with
`setdefault` so an explicit value wins. Verified: `families()` goes from 0 to a populated list and
`test_application_launches_and_exits_cleanly` passes.

**Open, and it needs a runner:** *why the runners do not show this.* Their offscreen Qt evidently
finds fonts by some route this machine lacks, and until CI runs it is unknown whether
`QT_QPA_FONTDIR` changes anything there. If their database is already populated the variable is
ignored, which is the expected case — expected, not verified.

#### Out of scope

- Weakening the empty-stderr assertion to make the run green; that assertion caught this

---

### T-056 — `still_running` reports a reaped Windows process as alive, intermittently

**Status:** **Blocked — on Windows evidence, not on code**, 2026-07-28 at `9c92c32`. The reviewer
found the implementation correct and could not verify it: the changed branch does not execute on
Linux, so neither the runtime behaviour nor the mutation that proves it can be observed here. The
helper decides by exit status on Windows and the third acceptance criterion is answered in its own
docstring.

**A Windows machine was not enough** (2026-07-28, `STARBASE`, Windows 10 22H2). The corrected
helper passes 3/3. Reverting it to the presence-based form it replaced passes **20/20** — the
defect does not reproduce here at all. A positive control (`still_running` always answering
"nothing alive") **fails** on the test's first assertion, so the patching mechanism is proven and
the survival is a real measurement rather than a mutation that never applied.

So the next step narrows rather than clears: this wants **`windows-latest`'s image**, Windows
Server, not Windows as such. `30323328299` remains the only observation of the defect anywhere.

**No longer a Phase 1 exit dependency** (`OPS-005`, 2026-07-29). Still open, still Blocked, but it
does not gate the phase: `still_running()` is test-only code that never ships, and its documented
sole error direction is a false **alive** — it can redden CI, it cannot make broken reaping look
correct. Windows Server is not a supported platform (`REQUIREMENTS.md`), so a finding seen only
there is a CI-reliability concern rather than a user-facing one.

**What that decision explicitly does not claim.** The mechanism is Windows-*general*: Windows has
no zombie state and a terminated process stays visible while any handle to it is open, which is
identical on Windows 10 and on Server. `STARBASE`'s 20/20 is therefore **absence of a trigger, not
evidence of correctness**. The risk is accepted on the error direction, not on the clean run.
**Owner:** Implementer
**Priority:** Medium — an intermittent failure in the helper every `T-019` assertion rests on
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `T-019`, `ai/TESTING.md` §7 (Cancellation, Worker crash)
**Affected surfaces:** `tests/integration/test_manager.py`
**Risk:** Medium — it decides whether the process-tree suite is telling the truth

#### Scope

`test_the_survival_check_can_tell_a_live_process_from_a_dead_one` failed once on `windows-latest`
in run `30323328299`: `still_running([dead_pid])` returned `[7208]` for a process the test had
already reaped. It passed on the runs either side, so it is **intermittent, not a regression** —
nothing in the `T-016` batch touches `process_tree.py` or that helper.

The likely cause is that `still_running` treats "psutil can still see the pid" as alive, excluding
only `NoSuchProcess` and `STATUS_ZOMBIE`. Windows has no zombie state, and a terminated process
stays visible while a handle to it remains open, so there is a window in which a dead process
reports as running.

**This matters more than a flaky test usually would.** `still_running` is the helper the whole
`T-019` descendant-reaping suite decides on, and its own docstring says a guard nobody watches
fail is the shape `ai/TESTING.md` §13 exists to catch. A false *alive* fails loudly, as here; the
concern is whether the same imprecision can produce a false *dead* and make a reaping assertion
pass without anything having been reaped.

#### Acceptance criteria

- The helper distinguishes a running process from a terminated-but-visible one on Windows, by
  exit status rather than by presence
- The claim is demonstrated on Windows CI, not reasoned about from Linux
- Whether the previous form could report a live process as dead is answered explicitly, and the
  answer is recorded rather than assumed benign

#### Out of scope

- Changing `downloader/process_tree.py`, which is `T-019`-approved and not implicated

#### Evidence, 2026-07-28

**The fix is Windows-only, because the imprecision is.** On POSIX the terminated-but-visible state
*is* the zombie state, so `status()` was already asking the right question. On Windows there is no
zombie and a corpse stays visible while any handle to it is open, so the helper now uses
`wait(timeout=0)` there — `WaitForSingleObject` on psutil's own handle, which neither disturbs
anyone else's handle nor depends on visibility.

**The first attempt used `wait(timeout=0)` on both platforms and broke the suite**, which is worth
keeping: on POSIX that call is `waitpid`, so inspecting a worker *reaped* it and stole the exit
status `multiprocessing` was waiting for. `is_alive()` then never reported the process gone and
the manager never went idle —
`test_cancelling_a_download_kills_what_the_worker_spawned` failed exactly that way. A survival
check that changes what it observes is worse than an imprecise one.

**The third criterion is answered, not assumed benign.** The previous form could **not** report a
live process as dead: it answered "dead" only on `NoSuchProcess` (and `ZombieProcess`, its
subclass) or on a `STATUS_ZOMBIE` a live process never has, and `AccessDenied` was uncaught and so
would have failed loudly. Its one error direction was **false alive**, which fails an assertion in
the open rather than letting a reaping assertion pass over nothing. The answer is recorded in the
helper's docstring, where the next reader of the helper will find it.

**The test now drives the failing shape**: a third process is killed and deliberately *not* waited
on. On Linux that is a zombie, which the old form already handled; on Windows it is exactly run
`30323328299`'s failure.

**Mutations run:** answering by presence alone everywhere — killed. Reporting nothing as alive —
killed. **Disabling the `win32` branch so it falls back to the POSIX question — survived, and
cannot do otherwise here**: the branch is unreachable on Linux by construction. That is
`AGENTS.md` §8's "a host-only check is not the whole gate" in its exact form, and it is why this
task is not claiming to be done.

**Checks:** `ruff check .`, `ruff format --check .`, configured `mypy` and `mypy --platform win32`
(72 files each — the win32 scope is what analyses the new branch at all) all pass. Bare `pytest`
green.

**Blocker:** the Windows demonstration. This machine has no Windows and the branch cannot execute
here, so approval needs the `windows desktop` job to run the corrected helper and the third
mutation against it. Same shape as `T-033`'s blocker: the code is done, the evidence is not
producible locally.

---

### T-033 — Bundle the pinned yt-dlp baseline into the frozen artifact

**Status:** **Blocked on Windows only**, narrowed 2026-07-29 (`T033-R3`). Code corrections were
verified 2026-07-26 (`T033-R2` resolved, the version-against-pin half of `T033-R1` verified).
**The Linux half is no longer externally blocked and has now been produced** — see **Linux
evidence** below. `T033-R1` stays **Open** for the Windows frozen result and the
collection-removal negative run; it is deliberately *not* closed by the commit that lands this
work.

*(This said the evidence was something "this repository cannot produce locally", on the belief
that PyInstaller was absent from the working venv. It is present at 6.21.0 and has been; the
reviewer flagged the claim as stale and the local build proves it. What is genuinely external is
Windows, and the two `frozen` jobs being GitHub-hosted.)*

#### Linux evidence, 2026-07-29 — produced locally

`python -m PyInstaller packaging/tracks-and-trails.spec` on Fedora, Python 3.14.6, PyInstaller
6.21.0. Build exit 0.

| Measure | Result |
|---|---|
| Artifact size | **194 260 KiB** |
| Files matching `*yt_dlp*` | 3 |
| `yt_dlp` bytes on disk | 24 KiB — the package is inside the archive, not loose, which is why the count is small |
| `--ytdlp-probe` | **OK.** version `2026.07.04`, source *bundled baseline*, pin `2026.7.4`, **1751 extractors**, resolved `youtube` from `yt_dlp.extractor.youtube` |
| `packaging/frozen_smoke.py` | **OK** in 3 s — spawned a child, exchanged one message, reaped it, **one** top-level application start (`pid=66180 frozen=True argv=['--spawn-probe']`), no orphan |

That is the version-against-pin assertion, the extractor resolution through the lazy machinery,
the size record, and `T-020`'s spawn proof, all on Linux and none of it waiting on anything.

**Still owed. Only one of the two is external** (`T033-R3`, corrected):

- **The collection-removal negative is *not* external.** The same local build can strip
  `collect_submodules("yt_dlp")` from line 37 of the spec and run the negative probe. Until that
  is done a passing probe cannot distinguish "the collection works" from "the probe cannot fail",
  which is this project's recurring failure shape — and **`T-033` is not "Blocked on Windows
  only" while a local acceptance proof remains undone.** Pending, not blocked.
- **The Windows frozen run is external.** Both `frozen` jobs are GitHub-hosted.

*(This paragraph called the collection-removal mutation "genuinely external" in the same breath as
proving the local build works. It is the second time in two days this task has claimed something
was unproducible locally on the strength of a belief about the environment rather than a check.)*
**What landed.** `collect_submodules("yt_dlp")` + `collect_data_files("yt_dlp")` in
`packaging/tracks-and-trails.spec`; `run_ytdlp_probe()` in `_freeze_probe.py` behind a
`--ytdlp-probe` flag; a CI step in the `frozen` job on both platforms.

**The probe resolves an extractor by name rather than importing yt-dlp.** `import yt_dlp`
succeeds against the core alone — which is exactly what makes this failure look like site
breakage — so the probe goes through the lazy machinery PyInstaller's static analysis cannot
see. Resolution runs through `downloader.worker`, so it exercises the real `OPS-002` path
inside the artifact instead of a parallel one, and stays within `ARCHITECTURE.md` §6.

**Defect found by mutation-checking the probe itself.** `get_info_extractor` *raises* `KeyError`
for an unknown name; it does not return `None`. The `matched is None` branch was therefore dead
code and the failure escaped as a bare traceback. The job still went red, so the gate worked —
but under `OPS-003` a Windows failure is diagnosed from this log and nothing else, and
`KeyError: 'YoutubeIE'` does not say the artifact shipped without its extractors.

**Verified locally:** 1751 extractors, `youtube` resolved, exit 0. Both probe mutations
(threshold above reality; unresolvable name) exit non-zero, so the gate is wired to the exit
code and not vacuous.

*(This paragraph ended "Frozen-artifact evidence on both platforms is pending CI — the local run
is source-mode and deliberately claims nothing about the frozen build." That was true when
written and is not now: **the Linux frozen evidence is complete**, produced against a real
artifact on 2026-07-29 and independently re-verified by the reviewer. See **Linux evidence**
above. Windows remains pending. `T033-R3`.)*

**Owner:** Implementer
**Priority:** High — blocks any usable release, and fails in a way that looks like a site bug
**Phase:** lands with `T-012`; verified by `T-020`'s CI job; gates Phase 5
**Depends on:** `T-012` (the worker is the first thing to import `yt_dlp`)
**Relevant context:** `OPS-002`, `REL-001`, `ARCHITECTURE.md` §6 and §12, `NFR-008`, `C-002`
**Affected surfaces:** `packaging/tracks-and-trails.spec`, `packaging/frozen_smoke.py`,
`.github/workflows/ci.yml`
**Risk:** **High** — the failure mode is silent at build time and total at run time

#### Scope

`OPS-002` says every release bundles a pinned yt-dlp baseline. The frozen artifact currently
contains **none of it**: a search of the built `dist/tracks-and-trails` for `yt_dlp` returns
zero files. That is correct today — nothing imports it, because `worker.py` and
`ytdlp_adapter.py` are still stubs — but it will not self-correct when `T-012` lands.

PyInstaller's analysis follows *static* imports. yt-dlp resolves its extractors dynamically:
1046 package files, **972 of them extractor modules**, reached through `lazy_extractors`
rather than by direct import. Static analysis will therefore collect the yt-dlp core and miss
essentially every extractor.

The resulting failure is the dangerous kind: the artifact **builds and launches normally**,
`import yt_dlp` succeeds, and then every real URL fails to find an extractor — which reads
exactly like the site-breakage `C-002` teaches everyone to expect, so it will be misdiagnosed.

Collect the package explicitly in the spec, and prove it from inside the artifact.

#### Acceptance criteria

- The frozen artifact contains the yt-dlp package, and the bundled version **equals the pin in
  `pyproject.toml`** — asserted, not eyeballed, so a stale build cannot pass
- A probe **inside the frozen artifact** imports `yt_dlp` and resolves a named extractor for a
  stable URL pattern, without network access
- Removing the collection from the spec makes that probe fail — the mutation is exercised once
  and reverted, as `T-020`'s negative proof was
- The `OPS-002` resolution order is honoured: with a directory present at
  `user_data_dir/tracksandtrails/ytdlp/`, the worker reports **that** version; with it absent
  or unimportable, it reports the baseline and says why
- Both the Linux and Windows frozen jobs stay green, and the artifact-size change is recorded

#### Out of scope

- The in-app update action itself (`OPS-002`, Phase 4) — this task bundles the baseline and
  proves the resolution order; downloading and extracting a wheel is separate
- Trimming the bundle. 972 extractor modules is a size cost worth measuring, but excluding
  extractors to save space would re-create this defect deliberately
- Any change to the pin

**Note:** `ai/TESTING.md` §8's release gate re-checks that yt-dlp is still pure Python. This
task is the other half — that the pure-Python package actually *ships*. Purity without
inclusion still yields an application that cannot download anything.

---

### T-039 — Verify Windows installer behavior on the runner

**Status:** Proposed — blocked until Phase 5 produces an installer
**Owner:** Implementer
**Priority:** Medium now, High once Phase 5 starts — it must land before the first public release
**Phase:** Phase 5
**Depends on:** the Phase 5 installer, `T-026` (establishes the real-plugin Windows job)
**Relevant context:** `OPS-004`, `REL-001`, `ai/TESTING.md` §9, `REQUIREMENTS.md` §3
**Affected surfaces:** `.github/workflows/ci.yml`, `ai/TESTING.md` §9, `REQUIREMENTS.md` §3
**Risk:** Medium — same failure mode as `T-026`: a shallow check would retire a
release-blocking manual item without replacing it

#### Scope

Split out of `T-026` when `OPS-004` was accepted on 2026-07-26. `OPS-004` reclassified four
things as automatable on the Windows runner; three of them `T-026` does now, but installer
verification cannot be written before an installer exists, and `T-026` had to stay completable
because it is what closes Phase 0's last exit criterion.

A CI runner is a genuinely clean machine, which is what makes this worth automating at all:
installing onto a box that has never held the application is exactly the case a developer
machine cannot reproduce.

Assert, on `windows-latest`:

1. **Silent install** completes with a success exit code and no interactive prompt.
2. **File and shortcut placement** — the installed tree, the Start Menu entry, and any
   registered association land where the installer claims.
3. **The installed application launches** under the real `windows` platform plugin, reusing
   `T-026`'s harness rather than a second one.
4. **Uninstall and removal** — the uninstaller exits clean and leaves nothing behind except
   what is deliberately preserved (user settings and the job database, per `DAT-001`).

#### Acceptance criteria

- Each of the four is a **gate**, stated as a mutation that turns the suite red: a missing
  shortcut, a file placed outside the install root, a non-zero silent-install exit code, and a
  leftover file after uninstall each fail the job. Screenshots, if any, stay retained evidence
  and fail nothing on their own (`T031-R2`, `P0-R7`)
- Uninstall leaving user data behind is asserted as **intended** behavior, not tolerated as a
  leftover — the test distinguishes the two
- `ai/TESTING.md` §9's manual list drops installer placement and removal, and
  `REQUIREMENTS.md` §3 narrows to match — **only once this job is landed and green**
- The added CI time is recorded against `T-006`'s budget

#### Out of scope

- Whether the installer *feels* normal — `OPS-004`'s subjective residue, still human, still
  blocks first release
- Upgrade-over-existing-install and downgrade paths — real, but a separate task once the
  versioning story exists
- Any non-Windows packaging

---

## Complete

### T-064 — Repair stale developer-tool launchers

**Status:** **Complete — approved**, 2026-07-29 at `f20a9c8`. The reviewer confirmed the repaired
venv's bare `mypy`, `pytest`, application entry point and import-location probe all resolve
through this checkout without `PYTHONPATH`, and that recreating with `venv --clear` addresses the
dependency-owned launchers reinstalling this project alone cannot. The one-sentence `STARBASE`
correction in `docs/DEVELOPMENT.md` was judged acceptable in this repair — reverting it would
knowingly restore a false current statement.
**Owner:** Implementer
**Priority:** Low — the application runs, but the documented bare developer commands do not
**Phase:** Phase 1
**Depends on:** `T-063`
**Relevant context:** `T063-R1`; `docs/DEVELOPMENT.md` setup, Everyday commands, and editable
install repair sections
**Affected surfaces:** `docs/DEVELOPMENT.md`; the local, git-ignored `.venv/`
**Risk:** Low — developer-environment repair only

#### Scope

`T-063` repaired the application console script and editable source path by reinstalling this
project from the current checkout. It did not repair console scripts installed by the development
dependencies: at review time 39 launchers under `.venv/bin/`, including `mypy` and `pytest`, still
named the nonexistent parent-checkout interpreter. Consequently the documented bare `mypy` and
`pytest` commands fail with `bad interpreter`, while `.venv/bin/python -m mypy` and
`.venv/bin/python -m pytest` work.

Make the documented recovery procedure repair the whole development environment, not only this
project's own entry point. Recreating the venv from the current checkout is the simplest known
route; a narrower procedure is acceptable only if it demonstrably rewrites dependency-owned
launchers too.

#### Acceptance criteria

- Following the documented repair from the stale moved-venv state makes both application entry
  points and the documented bare `mypy` and `pytest` commands runnable without `PYTHONPATH`
- The import-location check still resolves `tracks_and_trails` from this checkout
- The same instructions work after `.venv/` is deleted and recreated
- The procedure does not choose between repository paths; it makes the environment agree with the
  checkout in which it is run

#### Evidence, 2026-07-28

**The count was worse than filed.** `T063-R1` measured 39 stale launchers; at repair time it was
**45 of 46**, with `tracks-and-trails` the only healthy one — because `T-063`'s reinstall had
repaired exactly that one and nothing else. That is the trap the documentation now names: the
application starts, so the environment looks fixed, while `mypy` and `pytest` stay broken.

`python3 -m venv --clear .venv` followed by `pip install -e ".[dev,build]"`. The `build` extra was
included because this venv already had PyInstaller 6.21.0 installed and dropping it would have
been a silent regression.

| Check | Result |
|---|---|
| Launchers naming this checkout's interpreter | **46 of 46** (was 1 of 46) |
| `mypy --version` (bare, activated) | 2.3.0 |
| `pytest --version` (bare) | 9.1.1 |
| `ruff --version` (bare) | 0.16.0 |
| `tracks-and-trails --version` (bare) | 0.1.0.dev0 |
| Import location, no `PYTHONPATH` | resolves to this checkout's `src/tracks_and_trails/` |
| `ruff check .` · `ruff format --check .` | Passed · 103 files already formatted |
| `mypy` · `mypy --platform win32` | Success, 78 source files · Success, 78 source files |
| `pytest` (full default suite) | **1399 passed, 11 skipped, 2 deselected** |

Every command in that table was run **bare**, through the activated venv, with no `PYTHONPATH` —
which is the acceptance criterion rather than a convenience.

**Adjacent correction, made inline rather than filed.** `docs/DEVELOPMENT.md`'s Windows section
still said "there is currently no Windows machine available, so Windows is verified through CI
only", while the *same file's* "Verifying on Windows" section described running the suite on
`STARBASE`. One file, two answers; corrected to name `STARBASE` and the self-hosted runner.

#### Out of scope

- Product, packaging, or CI behavior
- Choosing the canonical repository path
- The `build` extra's contents; it was preserved as found, not chosen here

### T-040 — Extend the Windows desktop gate to widget focus order

**Status:** **Complete — approved with follow-up**, 2026-07-28. The behaviour and the manual
mutation evidence are accepted: both `T-026` mutation classes were executed and killed on
`STARBASE`, and the self-hosted desktop job is now a repeatable normal-run gate — job
`90432207805` passed all 28 selected tests under the real Windows plugin. The mutation executions
remain correctly described as **manual**, not automated. `COORD-R5`'s remaining filing and
current-truth cleanup is carried to `T-072`; the re-review states this task may close on that
carry **without another behavioural review**. See **Evidence, on Windows**.
**Owner:** Implementer
**Priority:** High once unblocked — it completes a `T-026` acceptance criterion that is
currently unmet
**Phase:** Phase 1, landing with the first real widgets
**Depends on:** `T-016` **or** `T-017` (whichever first adds focusable controls), `T-026`
**Relevant context:** `T026-R3`, `OPS-004`, `NFR-005`, `ai/TESTING.md` §9 and §12
**Affected surfaces:** `tests/ui/test_windows_desktop.py`, `ai/TESTING.md` §12
**Risk:** Medium — the gap is easy to forget precisely because deferring it was correct

#### Evidence, on Windows — 2026-07-28, `STARBASE`

Run on a Windows 10 22H2 machine on the maintainer's network, over RDP in **session 2** (an
interactive desktop; session 0 would have no window station and every result would be meaningless
rather than merely wrong). Python 3.14.6 MSC v.1944, PySide6 6.11.1 — the same versions the CI
runners report. GitHub Actions was unavailable: workflow `30392139504` failed before executing a
step, on the billing annotation.

**Baseline: 28 passed, 1409 deselected**, under `QT_QPA_PLATFORM=windows`.

| Mutation | Result | Tests failed |
|---|---|---|
| `titleValue`/`uploaderValue` reordered in the dialog's declared chain | **killed** | 6 |
| an undeclared focusable control appears in the dialog | **killed** | 6 |
| an undeclared focusable control appears in the progress view | **killed** | 2 |
| the progress view's delivered order reversed, declaration untouched | **survives, as measured** | 0 |

The counts corroborate rather than merely satisfy: 6 is three dialog states times two dialog
tests, and 2 is the progress view's two states — the mutation reaches exactly the tests it should
and no others.

**Each mutation is a pytest plugin, not a source edit**, so the checkout was never modified and a
failed run could not leave a half-mutated file behind.

**`probeButton`/`cancelProbeButton` is not a usable reorder** and the criterion should not be read
as requiring it: they are never enabled simultaneously, so no keyboard walk distinguishes the two
arrangements. The swap is done on two controls reachable in every state.

**The surviving mutation is the point of its row.** `T060-R2` asked for the progress view's
reversal to be caught; it was measured offscreen as unobservable, and this run confirms that claim
*on the platform it was made about* rather than leaving it an argument made on Linux about
Windows. An unexpected kill would have meant the reasoning was wrong.

**The harness had to be corrected twice, and the first table it produced was false.** Its initial
run reported three clean kills; every mutated run had actually exited on a pytest *usage* error
because the driver built an environment and never passed it to the subprocess, so `-p <plugin>`
named an unknown plugin and no test executed. The driver now counts **only pytest exit code 1** as
a kill and reports any other non-zero code as `NO RESULT`. A result table that cannot distinguish
"the test caught it" from "nothing ran" is the same defect class as a test that passes for the
wrong reason (`ai/TESTING.md` §13), one layer up.

**What this was not, and what changed later the same day.** When first recorded this was a
manual run on one machine rather than a gate — a regression between then and the next CI run
would have been caught by nothing.

**It is a gate again as of 2026-07-28.** `STARBASE` is registered as a **self-hosted runner** for
the `windows desktop` job, started from `run.cmd` in a logged-on, elevated session
(`Runner.Listener.exe`, Session#2). Job `90432207805` of run `30405803368` is **green end to
end** — `28 passed, 1410 deselected in 14.33s` under the real `windows` plugin — so the desktop
suite runs on every push and no longer depends on Actions quota.

Getting there took three corrections, each recorded in `docs/WINDOWS_VERIFICATION.md` because
each is a trap the next person hits:

1. **`actions/setup-python` provisioned the machine.** Free on a hosted runner, which is thrown
   away; this one is not. It launched the real installer, found the existing 3.14.6, opened an
   interactive Modify/Repair dialog nobody could see, and deadlocked against `msiexec` for the
   full timeout — leaving `python.exe` missing from a directory that still had `Lib`. The job now
   installs nothing and asserts the version it needs.
2. **A wedged listener.** Killing the runner's worker out from under it left the scheduled task
   marked running, and `schtasks /run` on a running task is a silent no-op — the runner sat
   `offline busy=true` while jobs reported zero steps for ten minutes. `schtasks /end` first.
3. **`bash` was not on `PATH`.** The workflow uses `shell: bash` throughout and hosted Windows
   runners ship Git Bash; this one had it installed and unreferenced. Caught by the version guard
   added in correction 1, which failed at step 3 rather than letting the suite fail obscurely.

**Still by hand:** the `T-026` mutations run from `tools/windows/mutations/`. Making *those* part
of the job is not done, so the mutation evidence remains a recorded run rather than a gate.

#### Scope

Filed from `T026-R3`. `T-026` requires "tab order and focus chain are asserted on Windows, and
reordering two widgets fails the test". That criterion is **met as of 2026-07-28**, and
deferring it was the right call at the time: the shell window had no focusable controls, so a
focus-chain assertion would have passed over zero widgets and gated nothing.

**`T-016` removed the reason to defer.** The add-URL dialog has six focusable controls, and
`tests/ui/test_add_dialog.py::test_the_tab_order_is_the_declared_one` walks Qt's own focus chain
against a hand-transcribed order — a mutation reversing two entries was run and killed. That test
runs **offscreen**, so it proves the order Qt builds, not the order a real Windows desktop
delivers, which is exactly the half `T-026` asked for and this task still owns.

Worth carrying into the Windows version: the first draft of that offscreen test derived its
expectation from the dialog's own `focus_chain()` and therefore proved only that the list equalled
itself. The mutation survived it. Transcribe one side and derive the other (§13).

Extend the existing `windows_desktop` suite — do not start a second harness — to assert, under
the real `windows` platform plugin:

1. **Tab order** across the new controls matches the intended sequence.
2. **The focus chain wraps**, forwards and backwards (`Tab` and `Shift+Tab`).
3. **Every focusable control is reachable** by keyboard alone from the window's initial focus.

#### Acceptance criteria

- Reordering two widgets in the source **fails** the suite, demonstrated by an actual mutation
  and recorded in the task, not asserted in the abstract
- A control added without being placed in the tab order fails the suite
- The assertions run under the real plugin, not offscreen — offscreen focus behavior does not
  answer the question `NFR-005` asks
- `ai/TESTING.md` §12 drops the "widget tab order is ungated" gap, and `T-026`'s acceptance
  criterion is marked met **only then**

#### Out of scope

- Focus *appearance* — whether the focus ring is visible enough is subjective and stays with
  the pre-release session (`OPS-004`)
- Linux focus order, which the offscreen suite cannot meaningfully assert either

#### Evidence, 2026-07-28

**Four tests, added to the existing `windows_desktop` suite rather than a second harness**, as the
scope requires: every focusable control is in the declared order; Tab visits that order under the
real plugin; the chain wraps forwards *and* backwards; every control is reachable from the initial
focus. A fifth covers the three focusable controls `T-017` added after this task was written — it
was filed when the dialog was the only widget with any.

*(The claim below that CI revealed a Windows-specific order was corrected on 2026-07-28 — see
`T-060`. The failures reproduce offscreen and are about disabled controls.)*

**One side is transcribed by hand and the other walked out of Qt**, which is the lesson carried
from `T-016`'s own review: the first draft of the offscreen test derived its expectation from the
dialog's own `focus_chain()`, so it proved the list equalled itself and the reversing mutation
survived it. `EXPECTED_DIALOG_ORDER` is written out from what the dialog is *for* — type the URLs,
probe them, read the result, choose, act — not read from the source.

**Checked once locally that the transcription and the dialog currently agree**, so the Windows job
fails for the reason it is meant to rather than because the two drifted. That check was run by
hand, not committed as a test: a committed one comparing the two lists would make this one derived
from the other, which is exactly what it exists not to be.

**What cannot be done here, and is therefore not claimed:**

- The tests have **never executed**. The module skips unless `sys.platform == "win32"`, and this
  machine has no Windows and no VM (`ai/STATUS.md`, Environment baseline).
- The acceptance criteria require the reversing mutation and the added-control mutation to be
  **demonstrated**, not argued. Neither can run.
- So `ai/TESTING.md` §12 **keeps** its "widget tab order is ungated on Windows" entry, and
  `T-026`'s acceptance criterion stays **unmet**. The criteria say "only then" and this is what
  "only then" means.

**Checks that could run:** `ruff check .`, `ruff format --check .`, configured `mypy` and
`mypy --platform win32` (76 files each) all pass — the win32 scope is what analyses this module's
body at all, since the host scope proves it unreachable. Bare `pytest`: **1395 passed, 11 skipped,
2 deselected**; the new tests are among the skipped.

#### Correction — `T040-R1`, 2026-07-28, and why it did not close

**`T040-R1` remains open and is carried to `T-060`** at reviewer direction. It is Medium, this
task's pass budget is spent, and `T-040` is blocked on Windows evidence either way (`AGENTS.md`
§10).

**The correction below drives focus, and then asserts a state that cannot exist.** It expects all
three of the progress view's controls to be reachable in one chain; on a failed job `Cancel` is
*disabled*, and on a running one `Retry` and the error text are *hidden*. A probe visited
`retryJobButton → errorMessage → retryJobButton`. The structural half passed because
`focusPolicy() != NoFocus` is true of a disabled widget — a list agreeing with a list, which is
the shape this task was filed to stop being satisfied by. `T-060` carries the per-state chains and
the Windows mutations that still owe evidence.

**A structural check is not a Windows test.** The progress-view test compared `focus_chain()` to a
transcription and checked the same widgets were focusable. Both are true on any platform and
neither touches the `windows` plugin this file exists for — it proved the order Qt was *told*,
which the offscreen suite already covers, while claiming to prove the order Windows *delivers*.

It now drives Tab and Shift+Backtab and asks Qt who holds focus, like the dialog tests beside it.
The stand-in store also returns a **failed, retryable** job, because the view hides its Retry
control otherwise (`T-017`) — a chain two controls long is one this file would have walked without
noticing, which is the same defect one layer down.

**Blocker, unchanged:** the `windows desktop` CI job. Same shape as `T-056` and `T-033`: the code
is done, the evidence is not producible locally — which is also how a test asserting an impossible
state reached a commit. Nothing here has ever run.

---

### T-060 — Focus chains are per state, and the Windows mutations still owe evidence

**Status:** **Complete — approved with follow-up**, 2026-07-28 at `12dff92`. `T060-R1` and
`T060-R2` were independently verified resolved with **no further code correction requested**, and
the mutation evidence that was its last dependency was produced on `STARBASE` the same day
(recorded under `T-040`). **The Windows-divergence claim in this task and in `T-040` was wrong**
and is corrected below: Tab skips disabled and hidden controls, and that reproduces offscreen.
`COORD-R5`'s remaining filing is carried to `T-072`; the re-review states this task may close on
that carry **without another behavioural review**.
**Owner:** Implementer
**Priority:** Medium — it is the difference between a Windows focus gate and a Windows focus
*claim*, and `T-026`'s acceptance criterion cannot be marked met until it is settled
**Phase:** Phase 1
**Depends on:** nothing to write. **Its evidence depends on the `windows desktop` CI job**, which
is also what `T-040` and `T-056` are blocked on
**Relevant context:** `T040-R1`; `T-040`; `T026-R3`; `NFR-005`; `ai/TESTING.md` §12 and §13
**Affected surfaces:** `tests/ui/test_windows_desktop.py`, `ai/TESTING.md` §12
**Risk:** Low to write, Medium to leave — a focus test that cannot reach a control it asserts on
is a red build for a wrong reason, and a green one would be worse

#### Scope

**CI run `30380426474` failed four of `T-040`'s tests, not one.** The progress-view test is the
one `T040-R1` predicted; the other three are the *dialog's*, and they are new information:

| Failing on the real Windows plugin | |
|---|---|
| `test_tab_visits_the_declared_order_on_a_real_desktop` | dialog |
| `test_the_focus_chain_wraps_in_both_directions` | dialog |
| `test_every_control_is_reachable_from_the_initial_focus` | dialog |
| `test_the_progress_view_focus_chain_is_walked_on_a_real_desktop` | `T040-R1` |

**That reading was wrong, and correcting it is the most useful thing in this task.** This entry
said the failures showed "the order Windows delivers is not the order Qt builds offscreen".
They showed nothing of the kind. All four have one cause, and it reproduces offscreen:

**Tab skips a control that is disabled or hidden, and every state of these widgets disables
some.** The dialog disables `probeButton`, `cancelProbeButton` and `addButton` until there is a
URL to act on — which is exactly the three CI reported unreachable — and the progress view
disables `Cancel` on a terminal job and hides `Retry` on a running one. Walking Tab through the
dialog offscreen with no URL typed produces the **identical** sequence `windows-latest` reported,
ending `selectorValue → closeButton → urlInput`.

So `EXPECTED_DIALOG_ORDER` was never the problem: the *order* is right, and what was missing was
that a chain is the declared order **filtered by what the current state offers**. The offscreen
suite had never pressed Tab, so nothing had observed this anywhere — not a platform difference,
an untested behaviour.

`T-040`'s progress-view test expects **three** reachable controls in one chain. That state does
not exist. Measured on 2026-07-28:

| The job is | Tab can reach | Why not the others |
|---|---|---|
| `FAILED`, retryable | `errorMessage`, `retryJobButton` | `cancelJobButton` is **disabled** — a terminal job cannot be cancelled (`T-017`) |
| `RUNNING` | `cancelJobButton` | `errorMessage` and `retryJobButton` are **hidden** — nothing has failed |

An isolated probe visited `retryJobButton → errorMessage → retryJobButton` and could never reach
`cancelJobButton`.

**The structural half of that test agreed with itself, which is how it got written.**
`_focusable()` filters on `focusPolicy() != NoFocus`, and a *disabled* widget keeps its focus
policy — so the set matched while the walk could not. Comparing a declared list against a
computed list is the shape `T016-R4` and `T040-R1` have now each caught once; the walk is the
only part that knows what a keyboard can do.

So the chains have to be asserted **per state**, each with the set that state actually offers.

#### Acceptance criteria

- The failed state and the running state are asserted separately, each against the controls that
  state makes reachable — a disabled or hidden control is not in the expectation for that state
- Reachability is decided by driving Tab and Backtab and asking Qt what has focus, never by
  comparing two lists this repository computes
- A control that becomes reachable in a state without being declared for it fails
- The `T-040` mutations that could not be run — reversing two widgets, and adding a focusable
  control without placing it — are executed on Windows and **recorded**, for the dialog chain as
  well as the view's
- `ai/TESTING.md` §12 drops the "widget tab order is ungated" gap and `T-026`'s acceptance
  criterion is marked met **only when all of the above has run on Windows**

#### Out of scope

- Nothing in the dialog's chain is out of scope any more: CI failed three of its tests too, and
  the same per-state and real-focus reasoning applies to whatever it turns out to want
- Making the progress view offer more controls than a state should; the disabled Cancel and the
  hidden Retry are `T-017`'s behaviour and are correct

#### Evidence, 2026-07-28

**One cause, four failures.** See the correction above: Tab skips disabled and hidden controls,
and both widgets disable some in every state. Not a platform difference.

**Chains are now asserted per state.** The declared order is transcribed once; **availability is
transcribed per state**, by hand, from what the dialog is *for* — "with no URL there is nothing to
probe or add" is a design statement worth asserting, and reading it back from `_refresh_actions`
would make the test agree with the code (`ai/TESTING.md` §13). **Three** dialog states and two
progress view states, each checked for the set it offers, the order Tab walks, and wrapping both
ways. (The third dialog state — a probe in flight — arrived with the correction round below; the
first version left it out.)

**`_focusable` was the structural half of the same mistake.** It filtered on
`focusPolicy() != NoFocus`, which is true of a *disabled* widget — so it counted three controls
the walk could never visit, and the two lists agreed with each other while disagreeing with the
keyboard. It now also requires enabled and not hidden.

**Pre-flighted offscreen, and that is evidence rather than hope.** Because the walk is identical
there, all four states were driven locally before committing: reachable sets, walked order, and
both wrap directions all match what the tests expect. **This is not a substitute for the Windows
job** — the real plugin is the subject — but it is the difference between a test written from a
design and one written from a guess.

#### Correction round, 2026-07-28 — `T060-R1` and `T060-R2`

**`T060-R1` — the probe-in-flight state is now asserted, and the gap it left was real.** The
first version recorded `cancelProbeButton`'s absence as a deliberate gap. Recording a gap is not
the same as being allowed to have one: that control is enabled in exactly one state and disabled
in every other, so excluding that state excluded the only control that stops a running probe from
every assertion in this file. A gate that skips the one state a control lives in does not gate
that control.

The state is reached without a worker. `_ProbeThatNeverAnswers` subclasses `DownloadManager` and
overrides `start` to record the call and return; the dialog's own `_on_probe_saved` then sets
`started`, `probing_job_id` becomes non-`None`, and `_refresh_actions` swaps Probe and Add out for
Cancel. Deliberately **not** `entry_point=child_never_returning`, which is how `test_add_dialog.py`
holds a probe open — that spawns a real process, and a worker left alive by a failed assertion
here would be attributed to whichever test ran next. The factory asserts the state was actually
reached, so a change to `_refresh_actions` cannot silently leave the chain asserted over an idle
dialog.

**`T060-R2` — the set is gone, and the finding's own mutation turns out to be unkillable.** The
walk is now compared as a sequence, anchored on the control focus was placed on rather than
rotated into place, and Backtab is driven for two full laps in both the dialog tests and the
progress-view test. The same weakness was in `test_the_dialog_chain_wraps_in_both_directions`,
which asserted set containment in both directions; it is corrected in the same batch.

**But the reversal `T060-R2` names cannot be caught by any keyboard observation.** No state of the
progress view offers more than two reachable controls, and *a two-element focus cycle has no
observable orientation*: `A → B → A` and `B → A → B` are the same cycle, so from either control,
Tab and Backtab both deliver the other one, from any starting point. Measured, not argued — the
mutation was run and survived, and a four-line model of a 2-cycle shows why it must. This is
recorded as unobservable rather than answered with an assertion that appears to catch it.

Ordering is therefore gated where it is observable — the dialog's three states offer nine to
twelve reachable controls — and the anchored sequence is asserted for the view anyway, because it
costs nothing and begins gating order by itself the day a third control becomes simultaneously
reachable.

**Mutation results, offscreen, 2026-07-28 — 7 of 9 killed, both survivors explained:**

| Mutation | |
|---|---|
| `titleValue`/`uploaderValue` swapped, each of the three dialog states | **killed** ×3 |
| an undeclared focusable control appears in the dialog | **killed** |
| an undeclared focusable control appears in the progress view | **killed** |
| `cancelProbeButton` removed from the chain, probe in flight | **killed** |
| the walk ignores `backwards` and always presses Tab (dialog) | **killed** |
| progress view's delivered order reversed, declaration untouched | **survives — 2-cycle** |
| the walk ignores `backwards` (progress view) | **survives — 2-cycle** |

`probeButton`/`cancelProbeButton` is *not* a usable swap for the first mutation class: they are
never enabled at the same time, so no walk can distinguish the two arrangements. That is the same
2-cycle limitation seen from the other side, and it is why the swap is done on two controls that
are reachable in every state.

**Pre-flight method, so it can be repeated.** `tests/ui/test_windows_desktop.py` skips itself off
Windows, so the pre-flight loads the module's source with *only* the platform guard disabled and
calls the real test functions with hand-built fixture values. Nothing is re-implemented: a
pre-flight that paraphrased the assertions could pass while the file failed. All eight
parametrised cases pass offscreen.

**Still owed, and now blocked on more than a job run:** the two `T-040` mutations must be executed
**on Windows** and recorded, for the dialog chain as well as the view's. Nothing here has run
there. GitHub Actions usage is exhausted as of 2026-07-28 and CI cannot run for several days, so
this evidence is *scheduled*, not merely outstanding. `ai/TESTING.md` §12 keeps its gap and
`T-026`'s criterion stays unmet until it has run.

---

### T-067 — Path behaviour is gated only with long paths enabled, which is not the default

**Status:** **Complete — approved**, 2026-07-28 at `1e9694c`. No findings. The reviewer judged
removing a fixture `mkdir` from a pre-filesystem rejection path correct, and the new test asks the
OS to create a file at the accepted budget, so raising the project constant past what the default
Windows configuration accepts can no longer agree with itself. See **Evidence**.
**Owner:** Implementer
**Priority:** Medium — a real user configuration is untested, and it is the majority one
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `T-046`, `T-045`, `tests/unit/test_paths.py`
**Affected surfaces:** `tests/unit/test_paths.py`, possibly `core/paths.py`, `ai/TESTING.md` §12
**Risk:** Medium — the failure mode is a download that cannot be written

#### Scope

`test_a_directory_leaving_no_room_for_a_filename_raises` fails on `STARBASE` in **both** the venv
and the CI-style checkout, with `FileNotFoundError: [WinError 206]` raised by the test's own
setup while creating the deep directory it needs.

`HKLM\SYSTEM\CurrentControlSet\Control\FileSystem\LongPathsEnabled` is **`0`** there, which is
the Windows default. GitHub's runner images set it to `1`. So the test passes on CI because CI is
configured unusually, and the behaviour this project ships is gated only under a setting most
users do not have.

The test is about what happens when a directory leaves no room for a filename — precisely a
`MAX_PATH` question — so being unable to run it on a default-configured Windows is the sharp end
of the gap rather than an inconvenience.

#### Acceptance criteria

- The test either constructs its fixture in a way that works with long paths disabled, or is
  parameterised over both settings, or is explicitly scoped to one and says which
- The application's own behaviour with `LongPathsEnabled=0` is stated: what a user sees when an
  output path exceeds `MAX_PATH`, and whether `REQ`-level behaviour still holds
- `ai/TESTING.md` §12 records which Windows configurations are gated, rather than implying "Windows"

#### Evidence, 2026-07-28

**The `mkdir` was the only filesystem access in the test**, and the code under test has none on
this branch: `safe_output_path` raises at the length budget several lines before the one call that
resolves anything. So the directory was created only to be named, and creating it is what died
with `WinError 206` when `LongPathsEnabled=0`. Removing it changes no assertion.

**A new test ties the constant to the filesystem rather than to itself.** Every other length test
here compares `safe_output_path`'s output against `MAX_PATH_CHARACTERS`, so all of them would pass
unchanged if that constant were raised past what Windows accepts.
`test_a_path_this_accepts_is_one_the_filesystem_will_actually_take` writes the file.

| Check | Result |
|---|---|
| Both tests, Windows, `LongPathsEnabled=0`, unelevated | **pass** |
| Both tests, Linux | **pass** |

The budget is 240 and Windows' limit is 260, which is why this passes — but that margin was
previously an arithmetic argument nobody had executed on a machine where it mattered.

#### Out of scope

- Enabling long paths on any machine to make the test pass; that hides the finding

---

### T-069 — An end-to-end recovery test is intermittent on Windows

**Status:** **Complete — approved**, 2026-07-28 at `8938478`. It was `T066-R1`: the Windows crash
test killed one process level, orphaning the worker, and the orphan is what broke the restart.
Fixed by reaping the tree; the failure rate went from **4 of 5 to 0 of 5**, reverting the fix
restores the rate, and five clean file-level runs followed. The helper-strengthening residue
belongs to `T-066`'s evidence contract and is carried to `T-072`.

*(Previously: reproduced with a rate and narrowed to one interaction; not fixed. That reading
outlived being true and is kept here as historical.)*
**Owner:** Implementer
**Priority:** Medium — an intermittent test in the suite that proves the restart criterion
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `T-037`, `T-056`, `T-019`
**Affected surfaces:** `tests/integration/test_end_to_end.py`
**Risk:** Medium — it gates a Phase 1 exit criterion

#### Scope

`test_a_job_killed_mid_download_is_recovered_by_the_next_start` failed once on `STARBASE` in the
venv checkout, then passed on re-run and passed in the CI-style checkout. One observation, so the
rate is unknown and the cause is unidentified.

It is filed rather than dismissed because it gates *job state survives an application restart
mid-download*, and because it sits in the same process-reaping neighbourhood as `T-056`, whose
own defect has been seen exactly once. Two single observations in one area is not proof of a
common cause, and it is not nothing either.

#### Acceptance criteria

- The failure is reproduced with a rate, or a bounded search is recorded as not reproducing it
- If it shares a cause with `T-056` or `T-066`, that is stated; if it does not, that is stated
- Any fix is demonstrated by making the fixed behaviour fail when reverted

#### Evidence, 2026-07-28

**It is not intermittent; it is conditional, and the condition is now known.**

| Run shape | Result |
|---|---|
| the test alone | **passes** |
| whole `test_end_to_end.py`, 5 runs | **4 failed, 1 passed** |
| after `test_a_url_becomes_a_file_with_the_bytes_it_reported` | **fails** |
| after `test_a_progressive_download_completes_with_no_ffmpeg_at_all` | **passes** |

So one specific predecessor triggers it, which is a 30-second reproduction for whoever fixes it.

**Where it fails, exactly.** The restart half — the second `compose()`, the one that stands for
the application starting again after the kill:

```
src/tracks_and_trails/app.py:206:  connection = db.connect(database_path)
src/tracks_and_trails/persistence/db.py:171:  connection.execute("PRAGMA journal_mode = WAL")
E   sqlite3.OperationalError: disk I/O error
```

**Why it matters more than a flaky test.** That statement is on the path of Phase 1's *job state
survives an application restart mid-download* criterion, and the two tests use different
`tmp_path` directories — so a shared database file is not the explanation, and the predecessor
does shut its composition down through `OrderlyShutdown`. Whatever is left behind crosses between
two tests that should not be able to affect each other.

#### Resolved, 2026-07-28 — it was the orphaned worker

**Neither of the two candidates I named.** `T066-R1` supplied the answer: `kill_the_application`
killed a single process, so the worker survived the crash the test was simulating, and the
surviving worker is what made the next `compose()` fail.

| | Failure rate over 5 runs of the file |
|---|---|
| before, one-level kill | **4 of 5** |
| after, whole-tree kill | **0 of 5** |

At the prior rate, five clean passes by chance is about 0.03%.

**Recorded rather than smoothed over:** I wrote that whether this was the test's fault or the
product's "is exactly the question", and resolved to measure instead of guess. That was right, and
the answer still came from a reviewer noticing something in a *different* task. A reproduction is
what makes a hypothesis cheap to test; it is not what generates the hypothesis.

#### Out of scope

- Adding a retry to the test; that converts a real intermittency into a hidden one

---

### T-070 — The suite silently requires Windows privileges it never states

**Status:** **Complete — approved**, 2026-07-28 at `1e9694c`. No findings. The capability is
attempted in the test's own temporary directory, the skip tells a Windows developer which
privilege or setting is missing, and the four original tests are unchanged wherever the capability
exists. See **Evidence**.
**Owner:** Implementer
**Priority:** Medium — four tests failed on an ordinary desktop for a reason no message named
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `T-067`, `T-066`, `docs/WINDOWS_VERIFICATION.md`, `ai/TESTING.md` §12
**Affected surfaces:** `tests/capabilities.py`, `tests/conftest.py`, `tests/unit/test_paths.py`,
`tests/integration/test_worker.py`
**Risk:** Low to fix, Medium to leave — it reads as a broken checkout

#### Scope

Four tests create symlinks. On Windows that needs `SeCreateSymbolicLinkPrivilege` — Administrator
rights, or Developer Mode. They failed with a bare `OSError` on a normal desktop session and
passed when the same machine ran them elevated.

**CI could never have reported this**, because GitHub's runners are elevated. It surfaced only
when the suite was first run as an ordinary user, and the failure named a privilege nowhere: it
reads like a broken checkout.

#### Acceptance criteria

- A machine without the capability says so, in words that name the privilege and the fix
- The tests are otherwise unchanged and still gate wherever the capability exists
- The capability is **attempted**, not inferred from `os.name` or an elevation check
- `docs/WINDOWS_VERIFICATION.md` records elevation as one of the axes CI differs on

#### Evidence, 2026-07-28

`tests/capabilities.py` answers the question by making a symlink and removing it. A proxy —
`os.name`, an elevation check, a Developer Mode registry read — would be wrong in some
configuration; the attempt is the question itself.

| Environment | Result |
|---|---|
| Windows, unelevated desktop session | **4 skipped**, each naming the privilege and Developer Mode |
| Windows, elevated | **4 pass**, unchanged |
| Linux | **4 pass**, unchanged |

The skip is not the "retire a gate and replace it with theatre" failure `T-026` warns about: these
tests still gate on Linux and on CI. What changed is that a machine lacking the capability says
which one.

#### Out of scope

- Requiring Developer Mode to develop on Windows; the point is to name the requirement, not impose it
- The other Windows configuration differences (`T-066`, `T-067`, `T-068`)

---

### T-065 — Resolve the forbidden AI authorship trailer

**Status:** **Complete — decided** 2026-07-28. The exception is preserved and published history is
not rewritten. Maintainer decision, on the Implementer's recommendation. The remaining criterion
is standing rather than open: no later commit carries an AI authorship trailer, which the reviewer
confirmed across every commit in the boundary.
**Owner:** Maintainer
**Priority:** Low — repository provenance and process; no product behavior is affected
**Phase:** Phase 1 coordination
**Depends on:** nothing technical
**Relevant context:** `GIT-R1`; `AGENTS.md` §7 and §13
**Affected surfaces:** published commit `12dff92` and `origin/main`
**Risk:** Low if left documented; High to correct because doing so rewrites published `main`

#### Scope

Commit `12dff92` contains `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. That directly
violates the repository's hard rule that commit history names the human maintainer only. The same
message also omits the required `Task: T-060` trailer.

The commit is already on `origin/main`, so correcting its message requires rewriting published
history and force-pushing. `AGENTS.md` independently forbids that without confirmation. Do not
silently choose one rule over the other.

#### Acceptance criteria

- The maintainer explicitly chooses either to preserve the published exception or authorize an
  exact, bounded history rewrite
- If a rewrite is authorized, the replacement commit preserves the reviewed tree, removes the AI
  authorship trailer, adds the task/review trailers, and the force-push target is confirmed before
  execution
- If the exception is preserved, the violation and reason for not rewriting published history
  remain recorded
- Subsequent commits contain no AI authorship or generation trailers

#### Decision, 2026-07-28

**Preserve the published commit; do not rewrite `origin/main`.**

The cause is not in dispute: the Implementer used its own default commit footer instead of this
repository's rule, and `AGENTS.md` §7 is unambiguous. What was weighed is the correction, not the
defect.

**Rewriting costs more than the defect does.** Two records already cite `12dff92` by name — the
focused re-review at `ai/REVIEWS.md` covers the range `11e1203 → 12dff92`, and the roadmap
artifact cites it as the correction's head. A rewrite makes both point at a commit that does not
exist, which trades a findable-by-search defect for two provably wrong citations. This project has
twice found a record that read clean while describing something that was not there; manufacturing
a third deliberately is the worse outcome.

**What the defect actually costs, stated plainly:** `git log --grep='Task:.*T-060'` will not
return `12dff92`. That is the entire practical consequence.

**Mitigated, not hidden.** Commit `61fb8fb` carries `Task: T-060, T-061, T-063` and
`Review: COORD-R4, GIT-R1`, and names `12dff92` in its body, so the trailer search reaches a
commit that points at it. The violation stays visible in the history rather than being tidied
away, which is the same reasoning that keeps superseded claims in these files struck through
rather than deleted.

#### Out of scope

- Any history rewrite; the decision above closes that option unless the maintainer reopens it
- Changing the code or tests reviewed at `12dff92`

---

### T-071 — The icon reads as undersized beside other taskbar icons

**Status:** **Complete — approved**, 2026-07-28 at `3327fd3`, with **no findings**. The
reviewer reproduced every delivered asset byte-for-byte from the authoring script. See
**Review outcome**.
**Owner:** Implementer
**Priority:** Low — cosmetic, but it is the first thing anyone sees of the application
**Phase:** Phase 0 (asset correction to `T-003`)
**Depends on:** `T-003`
**Relevant context:** `T-003`, `T-021`, `tests/unit/test_resources.py`
**Affected surfaces:** `src/tracks_and_trails/resources/icons/` (every derived asset),
`tools/icons/render_icons.py` (new)
**Risk:** Low — no source change; the assets' sizes and frame set are unchanged and still pinned

#### Scope

The maintainer observed the icon looking small in a Linux taskbar beside Steam and Firefox. It
was: measured against the visible mark rather than the file, every derived asset drew the logo
at **~66% of its canvas height**, with almost all of the remaining space as one empty band
below the artwork. At the 32 px a taskbar typically requests, that is a 21 px mark in a 32 px
cell — 66% linear, ~43% by area against a neighbour that fills its cell — sitting high in the
cell rather than centred.

**This is not `T-021`.** That task is about the artwork's *detail* at 16 and 24 px, and stands
unchanged. This is about the *scale and centring* of the same artwork at every size.

The cause is in the master. `icon.png` carries a 194 px band of **alpha-1..8 pixels below the
visible artwork** — invisible at any size, but content to anything that trims on `alpha > 0`.
Its bounds are 496×547 at `alpha > 8` and 498×743 at `alpha > 0`. That 196 px difference is
almost exactly the empty margin every derived asset inherited, so whatever produced them in
`T-003` trimmed at `alpha > 0`. **Unverified** — `T-003` left no generation script, so this is
inference from the numbers, not a reading of what was run.

#### Acceptance criteria

- The mark spans a consistent, near-full fraction of the canvas at every delivered size
- It is centred, rather than flush to one edge with the slack on the other
- `icon.png` is untouched: it is the master, and the only asset not reproducible from another
- The frame sets `T-022` pins are unchanged — 8 PNGs, 7 `.ico` frames, sizes as declared
- Regeneration is repeatable, so this cannot drift back in silence

#### Evidence, 2026-07-28

`tools/icons/render_icons.py` renders all 8 PNGs and the `.ico` from the master: trim at
`alpha > 8`, scale to 92% of the canvas on the longer side, centre. The `.ico` is written by
hand so each frame is the one rendered at that size, not a re-downscale of one source image.

Visible mark as a fraction of canvas height, before and after:

| Size | Before | After |
|---|---|---|
| 16 px | 69% | 94% |
| 32 px | 66% | 91% |
| 48 px | 67% | 92% |
| 64 px | 66% | 92% |
| 256 px | 65% | 92% |

Vertical padding at 32 px went from T1/B9 to T1/B2. The `.ico` frames match their PNGs.

| Check | Result |
|---|---|
| `ruff check .` | All checks passed |
| `ruff format --check .` | 103 files already formatted |
| `mypy` | Success: no issues found in 78 source files |
| `pytest tests/unit tests/ui` | **1241 passed, 11 skipped** |
| `tracks-and-trails` under `QT_QPA_PLATFORM=offscreen` | window up, still running at an 8 s timeout |

**Confirmed on Linux, 2026-07-28.** The maintainer reports the icon reading correctly in the
Linux taskbar — the observation that opened this task, now answered on the surface it was made
on. That is the acceptance criterion the measurements could only stand in for.

**Known-unverified:** the **Windows** taskbar and title bar. No Windows observation was made,
and the `.ico` is what Windows selects from, so the frames that matter there are still judged
only by measurement — the same gap `T-007` records for the icon generally.

**Judgment call, flagged for review:** `tools/icons/render_icons.py` is new, and adding it goes
past the minimum fix. Without it the diff is nine regenerated binaries with no way to check what
produced them, and the drift it corrects had no script to blame. It needs Pillow, which is
**deliberately not added to `[dev]`** — it is a one-off authoring tool, not part of any gate.

#### Review outcome, 2026-07-28

**Approved at `3327fd3`. No findings.** Reviewer: Codex. Base `fd99229`, head `3327fd3`.

| Reviewer check | Result |
|---|---|
| Renderer reproduction with Pillow 12.3.0 | All eight PNGs and `icon.ico` reproduced **byte-for-byte** |
| `.ico` payload audit | Seven valid PNG-compressed frames; every payload exactly matches its standalone PNG |
| Visible bounds | Master crop 496×547 at `alpha > 8`; padding centred within one pixel at every size |
| Master preservation | `icon.png` unchanged across the boundary |
| Focused resource/UI tests | **23 passed** |
| `git diff --check fd99229..3327fd3` | Passed |

**The flagged judgment call was accepted.** The reviewer judged `tools/icons/render_icons.py` a
proportionate part of the correction: it records the threshold and scaling choices that were
previously lost, without adding Pillow to the product or to any development gate.

The known-unverified Windows appearance was judged accurately disclosed, and does not block a
Linux-reported cosmetic correction.


#### Out of scope

- The artwork itself, the brand hex values fixed by `T-003`, and the 1024 px master
- `T-021`'s simplified small-size glyph, which remains Proposed and unaffected
- Adding icon rendering to CI or to any gate

---

### T-061 — The ffmpeg gate reads the selector, not the format that was chosen

**Status:** **Complete — approved**, 2026-07-28 at `11e1203`. The gate asks yt-dlp what it resolved rather
than what was asked for, with the conservative reading kept exactly where nothing was resolved.
Three mutations, three killed. See **Evidence**.
**Owner:** Implementer
**Priority:** Medium — a user without ffmpeg is refused downloads that need none, on four of the
five built-in presets
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `REQ-024`, `OPS-001`; `downloader/worker.py::_ffmpeg_gap`; `T012-R5`;
`T-057`, which is the same defect shape one module over
**Affected surfaces:** `src/tracks_and_trails/downloader/worker.py`,
`tests/integration/test_worker.py`
**Risk:** Medium — it decides whether a download happens at all

#### Scope

```python
needs_merge = "+" in request.format_selector
```

**A string, where a structured fact was already in scope.** `_ffmpeg_gap` receives the probed
`info` and asks the *selector* instead. `bestvideo+bestaudio/best` against a source offering one
progressive format resolves to the `/best` branch — no merge, no ffmpeg — and the gate refuses it
anyway.

Measured on 2026-07-28 against a local `video/mp4`: with ffmpeg absent, the job failed
`FFMPEG_MISSING` before downloading, saying *"ffmpeg is required for this download"* of a file
that needed none. Four of the five built-in presets carry a `+`; the fifth is `Audio only
(original)`. So a user with no ffmpeg has one usable preset, and the one they would reach for
first tells them a download is impossible when it is not.

**The gate being conservative is correct and is not the problem.** Refusing *before* spending
bandwidth is `REQ-024`'s whole point (`T012-R5` widened it to every post-processor for the same
reason). What is wrong is the input: the answer is in `info`, and yt-dlp records a merge by
populating `requested_formats` with more than one entry.

**This is `T-057` again, one module over.** There the adapter matched a truthy string where
yt-dlp keeps a three-state field; here the worker matches a `+` where yt-dlp keeps the resolved
format list. Both read a *rendering* of a decision instead of the decision.

#### Acceptance criteria

- The gate decides from the resolved format — a merge is what yt-dlp says it is, not what a
  selector string looks like
- A progressive single-format download succeeds with ffmpeg absent, driven end to end rather
  than asserted at the function
- A genuine merge still fails **before** downloading, with the same message and kind; the
  conservative direction is preserved where it is correct
- Post-processors that need ffmpeg (`requires_ffmpeg`) still gate independently of the merge
  question — `T012-R5` widened that deliberately and it is not narrowed here
- A mutation restoring `"+" in request.format_selector` fails at least one test

#### Out of scope

- Installing ffmpeg, prompting for it, or bundling it — `OPS-001` settles that
- The `FFMPEG_MISSING` taxonomy entry and its retry policy

#### Evidence, 2026-07-28

**The fact was already in scope.** `requested_formats` is yt-dlp's own record of the decision — a
list of the formats it will merge, absent when one format satisfied the selection — and it is
populated by the same probe this gate already runs. Verified against a local `video/mp4`:
`bestvideo+bestaudio/best` resolves with `requested_formats=None, format_id='mp4'`, while
`bestvideo+bestaudio` with no fallback makes yt-dlp itself refuse.

**`_will_merge` returns three answers, not two.** `True` and `False` when yt-dlp resolved the
selection, and **`None` when it did not** — a playlist, or an extraction that stopped early.
The caller falls back to the selector there. That asymmetry is deliberate and is the whole safety
argument: a wrong *refusal* costs a message, a wrong *proceed* spends the download and then fails
at merge time, which is what `REQ-024` exists to prevent.

**One existing test was passing for the wrong reason.**
`test_a_merge_without_ffmpeg_fails_before_downloading` returned `{"formats": []}`, which resolves
to nothing — so it exercised the *fallback* rather than the merge path and would have passed with
the merge detection removed entirely. It now returns `requested_formats` with two entries, which
is the fact it always meant to state.

**Three tests, one per branch of the answer:** a merging selector that resolved to one format is
not blocked (the defect); a real merge still fails before downloading, same kind and message; an
unresolved extraction still falls back to the selector. Plus the end-to-end criterion — a
progressive download completing with ffmpeg made unavailable through `compose()`, so the test does
not depend on what the machine running it happens to have installed.

**Mutations run, all killed:** the gate reading the selector string again — the defect itself · a
real merge no longer detected · the blind case guessing "no merge".

**Checks:** `ruff check .`, `ruff format --check .`, `mypy src`, configured `mypy` and
`mypy --platform win32` all pass. `tests/integration/test_worker.py`: **54 passed**;
`test_end_to_end.py`: **4 passed**.

---

### T-063 — The virtualenv cannot run the application it installed

**Status:** **Complete — approved with follow-up**, 2026-07-28 at `11e1203`. `T063-R1` is carried
to `T-064`: 39 dependency-owned launchers still name the parent checkout's interpreter, so the
documented bare `mypy` and `pytest` fail, while module invocations work. Both entry points work without `PYTHONPATH`, and
the full suite passes without it. The procedure and the symptom are in `docs/DEVELOPMENT.md`. See
**Evidence**.
**Owner:** Implementer
**Priority:** Low — it blocks no gate, and it is the first thing a new checkout hits
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `ENV-R1`; `ai/STATUS.md`'s Environment baseline, "Repository path —
**Unsettled**"; `T-001` (the toolchain this is supposed to be)
**Affected surfaces:** `.venv/` is not tracked, so this is a documented procedure plus whatever
`docs/DEVELOPMENT.md` needs; possibly `ai/STATUS.md`'s Environment baseline row
**Risk:** Low to fix, and it is a standing tax on every session that does not know the workaround

#### Scope

Found by launching the application (2026-07-28), and reproduced independently by the Reviewer.
**Neither documented way to run this project works:**

```
$ .venv/bin/tracks-and-trails --version
bad interpreter: /mnt/.../tracks-and-trails/.venv/bin/python: No such file or directory

$ .venv/bin/python -m tracks_and_trails --version
No module named tracks_and_trails
```

Two independent faults:

1. **The console script's shebang names an interpreter that does not exist** — a path one
   directory above the real checkout.
2. **The editable install points at the wrong tree.** `_editable_impl_tracks_and_trails.pth`
   contains `/mnt/projects/software_projects/tracks-and-trails/src`, while the checkout is
   `/mnt/projects/software_projects/tracks-and-trails/tracks-and-trails/src`.

`PYTHONPATH=$PWD/src .venv/bin/python -m tracks_and_trails` works and is what every command in
this session used.

**This is `ai/STATUS.md`'s "Repository path — Unsettled" row showing up as a broken install**, and
that row already says the right thing: it should record a machine, not a truth, and it needs a
maintainer answer rather than a third edit. The venv was created from one path and the work
happens at another.

#### Acceptance criteria

- Both `tracks-and-trails` and `python -m tracks_and_trails` run from a fresh checkout without
  `PYTHONPATH`
- The procedure that achieves it is written down where a new session will find it, not just
  performed once
- `ai/STATUS.md`'s Environment baseline says which path the venv belongs to, or says that the
  question is open — it must not imply a working install that is not
- Whatever is decided survives `.venv/` being deleted, since it is git-ignored and does not
  survive a fresh clone (`ai/STATUS.md` records that happening twice already)

#### Out of scope

- Choosing between the two repository paths, which is the maintainer's (`ai/STATUS.md`)
- Packaging or distribution; `REL-001` and Phase 5 own those

#### Evidence, 2026-07-28

**One cause, two symptoms.** An editable install records absolute paths in two places — a `.pth`
naming the source tree and a shebang in each console script naming the interpreter — and neither
follows the venv. This one had been installed from the *parent* directory, so the `.pth` read
`…/tracks-and-trails/src` while the checkout is `…/tracks-and-trails/tracks-and-trails/src`.

**Fixed by re-running the install from the checkout**, which rewrote both:

```
$ .venv/bin/tracks-and-trails --version              → 0.1.0.dev0
$ .venv/bin/python -m tracks_and_trails --version    → 0.1.0.dev0
$ .venv/bin/python -c "import tracks_and_trails; print(tracks_and_trails.__file__)"
  …/tracks-and-trails/tracks-and-trails/src/tracks_and_trails/__init__.py
```

**The whole suite now passes with no `PYTHONPATH` at all**: 1398 passed, 11 skipped, 2 deselected.
Every command in the session before this one carried `PYTHONPATH=$PWD/src`.

**Written down, because the venv is git-ignored and does not survive a clone.**
`docs/DEVELOPMENT.md` gains the two symptoms, the fix, and a three-command check — including
`print(tracks_and_trails.__file__)`, which is the one worth keeping: a venv pointing at the *wrong*
checkout imports someone else's code and passes tests against it, silently. It also says plainly
that `PYTHONPATH=$PWD/src` makes the symptom go away without fixing it.

**The repository-path question is untouched and still the maintainer's.** This did not choose
between the two paths; it made the venv agree with the checkout it lives in. `ai/STATUS.md`'s
Environment baseline now records what was wrong and what fixed it, rather than implying a working
install.

**Nothing tracked by git changed for the fix itself** — `.venv/` is ignored. What is committed is
the documentation that makes the fix reproducible, which is what the acceptance criteria asked
for.

---

### T-016 — Add-URL dialog with probe results

**Status:** **Complete — approved**, 2026-07-28 at `6ce195a`. Critical `T016-R1` and High
`T016-R3` were independently verified resolved on the **fourth** correction batch, which
corrected the lifecycle the third re-review asked for rather than the three places it caught
each finding. `T016-R2` and `T016-R4`…`R8` were resolved earlier and were not reopened.
`T016-R2` is verified resolved. Critical `T016-R1` and High `T016-R3` continue, both narrowed to
what asynchronous persistence stopped guaranteeing rather than to a repeat of the original
defect.
`T016-R4`…`R8` are verified resolved. The three that continue — Critical `T016-R1` and High
`T016-R2`/`R3` — are corrected again, each for a reason the first pass did not reach rather than
a repeat of it.
The initial review returned **Changes requested** with one Critical, two High and three blocking
Medium findings. All six are corrected in one batch, together with both non-blocking Lows.
`T016-R3` needed an architecture decision first: `ARC-005` is accepted, and `T-055` records it.
No finding is marked Resolved here — that is the Reviewer's to do.
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 1
**Depends on:** `T-013`, `T-015`, `T-018` (the playlist/single-item projection this task
displays does not exist until `T-018` adds it — `T012-R6`). **`T-051` is resolved**: `ARC-004`
decides that a probed job downloads from `READY`, and this task implements it
**Relevant context:** `REQ-001`, `REQ-002`, `REQ-005`, `NFR-001`, `NFR-005`, `NFR-006`
**Affected surfaces:** `ui/add_dialog.py`, `ui/main_window.py`, `tests/ui/`, and — for
`ARC-004` — `downloader/manager.py` with `tests/integration/test_manager.py`
**Risk:** Medium — the first widget that talks to the manager, and the first place a blocking
call would freeze the application
**Review base:** `098ba3f` · **head:** `33ebd11`. Five commits span that range and **two are not
this task**: `0b914a5` preserves the Reviewer's own records, and `3b9d937` reflects `T-038`'s
approval into the tracking files. `T-016` is `d9936f4`, `57c7e5c` and `33ebd11`.
**Branch:** none now. `phase1-add-url-dialog` was cut at maintainer instruction because Codex was
reviewing `T-019`/`T-038` on `main` at the time (`AGENTS.md` §7 — isolated concurrent work), then
rebased onto `main`, merged fast-forward and deleted once that review closed.

#### Fourth correction batch — the lifecycle asynchrony needed, 2026-07-28

**Base:** `6ad20f6`. Nine mutations, nine killed, and the full suite re-run.

The third re-review reported both findings in three places each, and the six had one cause:
**a synchronous write sequenced every following effect for free, and an asynchronous one
sequences nothing.** `ARC-005` landed on the claim that a write-through view made the change
invisible to its callers — *"only the announcement moved"*, *"callers unchanged"* — and each
open defect is that equivalence failing somewhere different. So this batch corrects the model
rather than the three sites, and `ARC-005` is amended to say so (`ai/DECISIONS.md`, 2026-07-28).

- **`T016-R1` (Critical), first part — the close that *creates* a withdrawal is refused.**
  `done()` tested `_withdrawing` on the way in and then, four lines later, retired a started
  probe — which populates it — and carried on to `super().done()`. The check now happens after
  the retirement as well, and the dialog **finishes that same close by itself** once the
  cancellation is durable, so the user asks once rather than three times.
- **`T016-R1`, second part — a reserved start is cancellable.** `_reserved` was a set of ids
  held only to keep the pool at one, so `cancel()` wrote `CANCELLED` while the pending `PROBING`
  write's success callback still spawned unconditionally: a durable cancellation and a running
  worker for the URL the user had just taken away. It is now a `_PendingStart` that can be
  withdrawn, `_spawn` re-reads it and re-checks shutdown, and the caller learns through a new
  `start_rejected` signal.
- **`T016-R1`, third part — the store no longer guesses a rollback target.** Keeping the newest
  value and restoring the one it displaced is right for one failed revision and wrong for two:
  the second failure restored the first, which had also failed. `PersistentJobStore` now holds
  the revisions **in flight** and forgets each as it settles, so once nothing is queued the
  database is the only answer. A smaller claim, and one the disk can keep.
- **`T016-R3` (High), first part — a reservation is part of the lifecycle.** `is_idle`,
  `active_job_ids()`, `shutdown()` and the tick's idle gate all account for it now. `idle` is
  composition's permission to quit (`T-036`), so announcing it with a start on the writer thread
  was a promise this manager could not keep.
- **`T016-R3`, second part — per-job ordering of writes and effects.** `_Chain` runs one step at
  a time per job, and a transition is **computed when its turn comes** rather than when it was
  asked for. That closes the measured progress defect — the second message read back the
  `RUNNING` its predecessor had only queued and announced while the row said `PROBING` — and the
  class it belongs to: a step that no longer applies is skipped rather than walking the pipeline
  backwards out of a Qt slot.
- **`T016-R3`, third part — mandatory cleanup is not an announcement.** `_abort_start` passed one
  function as both `then` and `otherwise`, so a failed `FAILED` write still emitted `job_failed`
  and `protocol_violation` to observers that then read `PROBING`. The unwind now runs either way;
  the signals wait for durability, and the failure path logs the violation and emits
  `persistence_failed`.
- **`T016-R3`, fourth part — the dialog hears about a rejected start.** It treated a returning
  `start()` as a running probe and sat at "Probing …" forever when the write failed, offering to
  cancel a worker that did not exist.

**Two committed assertions were changed, and both encoded the defect.**
`test_no_companion_signal_arrives_before_its_transition_is_durable` and
`test_a_second_session_is_refused_while_the_first_is_still_being_stored` asserted
`active_job_ids() == ()` during a reserved start — which is exactly the invisibility `T016-R3`
is about. They now assert the reservation is reported, and the claim they were standing in for —
that no **worker** exists while the row still says `QUEUED` — is asserted directly in
`test_no_worker_exists_while_the_row_still_says_queued`, which was strengthened rather than
relaxed: it now checks the sessions dictionary *and* that the reservation is tracked.

**Mutations run, all killed:** `_spawn` ignoring a withdrawn reservation · `is_idle` ignoring
reservations · the tick's idle gate ignoring them · `shutdown()` cancelling sessions only · a
non-moving progress message forwarded at once · a failed `FAILED` write announcing anyway · the
store's old rollback-to-displaced rule · `done()` checking withdrawals only on the way in · the
dialog not connecting `start_rejected`.

**Checks:** `ruff check .` and `ruff format --check .` pass (86 files). `mypy src` (35 files),
configured `mypy` (71 files) and `mypy --platform win32` (71 files) all pass. Bare `pytest`:
**1292 passed, 11 skipped, 1 deselected in 73.86 s**. The wide mypy scope found two real problems
in the new tests, one of which made mypy stop analysing the rest of a test function — the same
`ai/TESTING.md` §12 scope difference this task recorded last round.

#### Third correction batch — durability now gates the consequences, 2026-07-27

**Base:** `c5dddae`. Seven mutations, seven killed, and the earlier batteries re-run.

- **`T016-R1` (Critical) — a withdrawal is owned until it is durable.** Retiring a probe cancels
  its stored row, but that cancellation is a write, and a write can fail. The reviewer held the
  lock through it: the view said `CANCELLED`, SQLite still said `QUEUED`, and a restart — which
  has no view — brought the replaced URL back as live work while the dialog showed only "The URL
  changed". Two corrections. `PersistentJobStore` **takes its view record back when a write
  fails**, so the view can no longer disagree with the disk about something that did not happen;
  and the dialog tracks each withdrawal until `CANCELLED` is durable, refusing to close or queue
  while one is outstanding, saying which URL is still queued and why, and retrying when Close is
  pressed again. The gate reads the concrete repository and finishes with a **fresh reader**,
  which is the restart the finding is about.
- **`T016-R3` (High) — persistence gates the effects, not just the announcement.** Moving
  `job_changed` into the callback preserved nothing else: the old synchronous write sequenced
  every following effect for free. A worker and its pump were built while the row still said
  `QUEUED`; `_abort_start` emitted `protocol_violation` and `job_failed` and ran cleanup before
  `FAILED` was durable; `job_succeeded` arrived while the row still said `RUNNING`.
  `_save_and_announce` now takes `then` and `otherwise`, and **session construction, startup
  cleanup, `media_probed`, `job_succeeded`, `job_failed` and state-moving `progress` all wait**.
  A failed write runs `otherwise` and never the success-side effect.

**Two consequences worth naming rather than burying.** `start()` **no longer raises for a spawn
failure**: the session is built from a write's completion callback, so there is nobody left to
raise to, and the failure is reported through the signals this manager already had. Five approved
`T-013` tests changed their delivery assertion and kept every other one. And the pool of one now
counts *reserved* starts, because otherwise it would have been "however many `start()` calls fit
between a write and its completion".

**Three of the seven mutations survived first time**, and all three were weak tests of mine rather
than weak code: the companion-signal test produced no companion signal to observe, the
failure-continuation test never checked that the success effect was skipped, and the pool-of-one
test used a synchronous store where the gap cannot exist.

**One defect was found by these tests, in this batch's own code.** Retrying a withdrawal while its
first cancellation was still pending drove `CANCELLED → CANCELLED` and threw
`IllegalTransitionError` out of `QDialog.done()`. `DownloadManager.cancel()` is now a no-op for a
job already terminal — there is nothing to cancel, and raising there is worse than saying so —
and the dialog retries only once a failure has actually been reported.

#### Second correction batch — the three continuations, 2026-07-27

**Base:** `162f286`. Nine mutations, nine killed, and the first batch's nineteen re-run and still
killed.

- **`T016-R1` (Critical) — the window before the row exists.** The first correction bound a
  result to its URL but left the *pending save* unmodelled: between `probe()` and its write
  landing, `started` is false, so nothing could cancel it and its callback simply recorded the
  row. Editing then left the replaced URL durably `QUEUED`, where whatever runs the queue next
  would download what the user took away. A probe retired during its save now has its stored row
  **cancelled** — `QUEUED → CANCELLED` is legal and needs no worker — so the record survives as
  something asked for and withdrawn rather than as pending work nobody wants.
- **`T016-R1` (Critical), second half — occurrences, not membership.** `_Persisted` was keyed by
  URL text, so once a probe had stored one occurrence, `Add` skipped *every* line with that text
  and two identical lines became one job. `split_urls` and `REQ-001` both say two identical lines
  are two requests. It now counts how many occurrences already have a job and creates the
  difference.
- **`T016-R2` (High) — `done()` reads `usable`, not `in_flight`.** A probe mid-save has
  `started is False`, so the first correction let Close through without retiring it, and the
  callback started a worker for a dialog the user had already closed. Four new tests exercise
  reject/close/done against a genuinely deferred save, and prove a later dialog can still probe.
- **`T016-R3` (High) — `ARC-005` covered appends only.** `DownloadManager._save_and_announce()`
  still called a synchronous `JobRepository.update()` from the GUI thread for every start,
  cancel, stage change, success and failure: 5.017 s blocked under a held lock, then an uncaught
  `OperationalError`. `QueueWriter.revise()` and `PersistentJobStore` now put **every** queue
  write on the one thread. `JobStore.update` takes a completion callback, so `T-013`'s
  persist-then-signal ordering is preserved rather than traded away, and a failed write raises
  `persistence_failed` instead of an exception nobody catches. `close()` no longer calls
  `QThread.wait()` — it reports completion through `closed`, the same event-driven shutdown
  `T013-R2` established for the manager, after a contended write held that wait for 4.921 s.

**The store's read contract is what kept this small.** `JobStore.get` is required to reflect a
queued `update` immediately, so all ten `_save_and_announce` call sites in approved `T-013` code
are unchanged; only the announcement moved into a callback.

**Three mutations survived the first run of this batch**, all on `T016-R3`, and each was a real
gap: the integrated test took the writer lock *after* `start()` had already issued its status
write, so nothing was contended; read-your-writes was asserted against a writer fast enough to
pass either way; and no test forced a write failure at all. All three now have a gate that fails
without the fix.

#### First correction batch — all six blocking findings, 2026-07-27

**Base:** `a931736`. Every correction has a test named for it, and every one of those tests was
shown to fail when the correction is weakened (19 of 19 mutations killed).

- **`T016-R1` (Critical) — a probe now belongs to a URL, not just to a job id.** `_Probe` records
  the input line and the generation of the URL box. Changing the first line **retires** that probe
  and cancels its session; a result is refused unless its line is still first. The refusal lives
  in `_on_media_probed`, where the result arrives, rather than resting on the edit handler having
  run first — which is what the defect was. **`Add to queue` is disabled while a probe is
  outstanding**, so the state that stored one line twice is unreachable rather than reconciled.
  `_Persisted` tracks one job per entered line, and a retired probe's URL stops counting as
  stored so it can be queued again.
- **`T016-R2` (High) — `done()` is the choke point.** Escape, the window button, `reject()` and
  `accept()` all reach it, and it cancels an in-flight probe. Three parametrised routes are
  tested, plus the consequence the finding is really about: a later dialog can still probe.
- **`T016-R3` (High) — nothing waits on SQLite.** `ARC-005` (below). The dialog submits and is
  told the answer later; it closes **inside** the success callback, so `REQ-012`'s ordering is
  strengthened rather than kept.
- **`T016-R4` (Medium) — the tab order is complete.** All twelve focusable controls are declared
  and asserted, and the observation no longer filters by declared name: the only exclusion is the
  combo box's popup, which lives in its own top-level window.
- **`T016-R5` (Medium) — the thumbnail reports failure.** `ThumbnailLoader.load` takes `bytes |
  None`; the shipping `QNetworkAccessManager` loader reports both outcomes, and its **failure**
  path is tested against a real local URL that cannot resolve.
- **`T016-R6` (Medium) — foreign text is `PlainText`.** Applied from one list, asserted per label
  and by rendered width against a `<b>VISIBLE</b>` title, because reading `QLabel.text()` back
  returns the input under either format and misses the defect entirely.
- **`T016-R7` (Low)** — the refusal test now takes the *complement* of the two entry points over
  the whole enum, so `PROBING`, `COMPLETED` and `CANCELLED` are covered and a new status joins
  the day it appears. One test compares the transcription against `_ENTRY_STATUS`.
- **`T016-R8` (Low)** — the stale records were corrected in `a931736`, before this batch; the
  "no widget touches any of it yet" contradiction in `STATUS.md` is fixed here.

**Three mutations survived the first battery**, and each exposed a real gap rather than a
mis-aimed probe: the `_on_media_probed` identity check was **unreachable** because the edit
handler deleted the probe record before any late result could be refused by name (fixed by
retiring rather than deleting, which is why `_Probe.superseded` exists); the "a later dialog can
probe" test passed with the fix reverted because the crafted child *died* on an unknown URL and
freed the pool by accident (it now hangs); and the batched position allocation could not be seen
by a single-batch test (a second batch now proves positions continue). All three are killed.

**Two defects were found by the corrections' own tests**, not by review: `QueueWriter.close()`
called the worker's slot directly and closed a SQLite connection from the wrong thread —
`check_same_thread` caught it, which is exactly why `ARC-005` keeps that check on — and
`QWidget.close()` on a never-shown dialog delivers no close event, so that test now shows the
dialog first rather than passing for the wrong reason.

**The `T016-R6` test was vacuous twice, in two different ways, and Windows CI found both.** The
first version compared a font-metrics advance against `sizeHint()`, which is a wrapped-layout
figure and never was a string width; it passed on Linux by luck. The second rendered the same
label under each text format — exact, and one variable — but the Windows runner laid that label
out 84 px wide, so both renderings clipped to identical pixels and the assertion could not fail.
It now sizes the label explicitly and asserts the two grabs are the same size, so a future
clipping change fails loudly rather than quietly restoring the equality.

**Evidence.** `ruff`, `ruff format`, `mypy src` (34 files) and both configured 70-file scopes
pass. Full suite **1267 passed, 11 skipped, 1 deselected**. CI green on all five jobs at
`8bde969` (run `30324097829`): Ubuntu 1267 passed, Windows **1256 passed, 20 skipped**, Windows
desktop 20 passed, both frozen jobs succeeded. Mutation battery: **19 of 19 killed**, including
one mutation per blocking finding.

**One unrelated intermittent was seen and is filed as `T-056`**, not swept up here: a
`windows-latest` run failed `test_the_survival_check_can_tell_a_live_process_from_a_dead_one`,
a `T-019` helper this batch does not touch. It passed on the runs either side.

#### What was built

- **`ui/add_dialog.py`** — the dialog. Probing runs in a worker process and `probe()` returns
  immediately; results arrive on `DownloadManager`'s signals. The thumbnail is the one `REQ-002`
  field the probe's reply does not carry — `MediaInfo` has a *URL* — so it is fetched
  asynchronously through an injected `ThumbnailLoader`, whose shipping implementation is
  `QNetworkAccessManager`. That seam is what lets the suite decode a real image without touching
  the network.
- **`downloader/manager.py`** — `ARC-004` implemented. `start()` now accepts `QUEUED` **or**
  `READY` and moves the job to the status that says a worker holds it, and the docstring that
  said the flow "needs the state machine amended first" is replaced by the ruling. A probe
  session is still refused for a `READY` job: `READY → PROBING` does not exist, and moving a
  probe to `RUNNING` would say a download holds a job that is not downloading.
- **`ui/main_window.py`** — File → Add URLs…, disabled with a status tip naming `T-036` until
  composition supplies a manager, a job store and an output directory. An action that appears to
  work and quietly does nothing is the failure mode this project keeps finding.

#### Two things a reviewer should look at first

- **`started_at` is stamped entering `PROBING` and left alone entering `RUNNING` from `READY`.**
  A download from `READY` continues one attempt rather than beginning a new one, while a retry —
  which re-enters `QUEUED` — still gets a fresh stamp. Both halves have a test.
- **`T-013`'s `test_a_job_that_is_not_queued_cannot_be_started` was replaced, not deleted.** It
  asserted the rule `ARC-004` amended. What stands in its place is a parametrised refusal for
  every status that is *not* an entry point, plus the four new `READY`-entry tests.

#### Evidence

Local at `33ebd11`: `ruff check`, `ruff format --check` (84 files), `mypy src` (33 files), and
bare `mypy` and `mypy --platform win32` (**69** files each) all pass. Full default suite:
**1239 passed, 11 skipped, 1 deselected** in 71 s — `T-038`'s 1195 plus this task's 44.

**CI is green on all five jobs**, run `30320408833`: ubuntu-latest 1239 passed, windows-latest
**1228 passed, 20 skipped, 21 deselected**, windows desktop **20 passed**, both frozen jobs
succeeded. This task has real Windows evidence.

**Twelve weakenings were applied and all twelve were killed** by a committed test — including a
probe that blocks the GUI thread, a paraphrased extractor message, jobs written after the dialog
closes, and a `READY` start that re-enters `PROBING`.

**Three gates reported clean while covering nothing, and each is worth more than the fix.**

- **The tab-order mutation survived the first run.** That test derived its expectation from the
  dialog's own `focus_chain()` — the list `_set_tab_order` feeds to Qt — so reversing two entries
  moved both sides and it proved only that the list equalled itself. Now transcribed by hand with
  Qt's `nextInFocusChain` walked against it (`ai/TESTING.md` §13).
- **The local type gate was the wrong scope, and CI found two real errors.** `mypy src` reads 33
  files; the `windows desktop` job runs the command **unscoped** over 69, including `tests/`.
  Neither error was Windows-specific. One had made mypy narrow a property at an earlier
  `assert ... is not None`, rendering the later `is None` assertion statically impossible — so it
  declared the rest of that test unreachable and **stopped type-checking it**. `ai/TESTING.md` §12
  now records the scope difference, which nothing stated.
- **The Windows UIA menu contract caught the new File-menu item**, correctly, because this task
  added one without declaring it there. The item is spelled `Add URLs...` with ASCII dots: the
  ellipsis returned from UI Automation as a replacement character in the CI log, and that log is
  the only Windows evidence this project has (`ai/TESTING.md` §10).

#### Scope

Paste or type a URL, probe it, see what it is, choose a preset, and queue it. Probing runs in
a worker process — **never inline** — because probe latency is unbounded and blocking the GUI
thread on it is exactly what `NFR-001` forbids (`ARCHITECTURE.md` §8).

**The probe-then-download step is settled** (`ARC-004`, from `T-051`). This task changes
`DownloadManager.start()` to accept a job in `QUEUED` **or** `READY`, choosing the status that
says a worker holds it — `PROBING` from the first, `RUNNING` from the second — and replaces the
docstring note that says the flow "needs the state machine amended first" with a pointer to
`ARC-004`. The download re-extracts rather than re-probing; the recorded title stands.

Show what `REQ-002` names: title, uploader, duration, thumbnail, and whether the URL is a
single item or a playlist. On failure, show the extractor's own message **verbatim**
(`REQ-005`, `NFR-006`) — not a paraphrase, and not a generic "could not fetch".

#### Acceptance criteria

- A probe of a fixture-backed URL populates **every field `REQ-002` names** — title,
  uploader, duration, a thumbnail decoded to a real pixmap rather than a URL, and whether the
  URL is a single item or a playlist — asserted field by field, since "populates the dialog"
  would pass with four of five missing
- The GUI thread is never blocked, and a test asserts the dialog stays responsive while a
  probe is outstanding (`NFR-001`)
- An unsupported URL shows the extractor's message character-for-character, asserted by
  equality against the fixture (`REQ-005`, `NFR-006`)
- A probe that never returns can be cancelled and leaves no worker behind
- Multi-line paste queues each URL as a separate job (`REQ-001`)
- Full keyboard operation: every control reachable and actuable by keyboard, with a
  deliberate tab order asserted, and an accessible name on every control (`NFR-005`)
- No information is conveyed by color alone (`NFR-005`)
- Queuing a job persists it before the dialog closes, so a crash immediately after does not
  lose it (`REQ-012`)
- A probed job in `READY` starts a download through `start()` and moves `READY → RUNNING`
  without passing through `PROBING`, with the persisted status asserted at each step (`ARC-004`)
- A `QUEUED` job still starts at `PROBING`, so the second entry point did not replace the first

#### Out of scope

- The sortable format table and per-format selection — `REQ-003`, `REQ-008`, Phase 3
- Drag-and-drop — `REQ-001` allows it, but it is not needed to prove the slice; Phase 2
- Playlist expansion into individual jobs — Phase 3

---

### T-057 — Bind DRM detection to yt-dlp's actual contract

**Status:** **Complete — approved**, 2026-07-28 at `4a06e92`. The reviewer confirmed the adapter
and the offline canary match yt-dlp 2026.07.04's actual DRM rule. The `_has_drm` write is
reachable offline, so the canary drives yt-dlp's own code rather than reading its source, and the
two divergences are corrected to yt-dlp's rule rather than recorded as deliberate.
**Owner:** Implementer
**Priority:** Medium — the boundary is fail-safe today, but one half of it disagrees with yt-dlp
and nothing would notice an upstream rename
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `SEC-001`, `REQ-EXCL-001`, `NFR-008`, `ai/TESTING.md` §5 (fixtures and the
recorded-failure canaries) and §7 (DRM)
**Affected surfaces:** `downloader/ytdlp_adapter.py`, `tests/unit/test_ytdlp_adapter.py`, and the
canary test wherever the recorded-failure canaries live
**Risk:** Medium — it is the input to a non-negotiable product boundary

#### Scope

Two problems at one seam. Both were found by **reading yt-dlp's own source at the pinned version**
(`yt-dlp==2026.7.4`, `pyproject.toml:34`) rather than by a failing test, which is itself the point.

**1. Nothing verifies that yt-dlp still writes the field.** `adapter.has_drm()` reads `_has_drm`,
and `SEC-001` rests on it. The DRM fixture is `derived` by design — capturing a real one means
probing a DRM service, which `REQ-EXCL-001` puts out of scope — so it proves this code *reads* the
field, not that yt-dlp *writes* it. On an upstream rename `has_drm()` returns `False`, the item is
never classified, and the product tries to download it: a non-negotiable boundary failing
silently. That is exactly the `NFR-008` canary shape `tests/fixtures/errors/` already uses to pin
exception types; DRM never got one. In the pinned version the write is `YoutubeDL.py:2930`, inside
`process_video_result`.

**2. The per-format fallback disagrees with yt-dlp, in both directions.** yt-dlp computes
`any(f.get('has_drm') and f['has_drm'] != 'maybe' for f in formats) or None`. The adapter computes
`bool(formats) and all(entry.get("has_drm") for entry in formats)`. Two divergences, neither
verified against a live extractor:

- **`'maybe'` is truthy in Python.** yt-dlp excludes it deliberately and keeps such formats
  downloadable (`YoutubeDL.py:2933`). The adapter reads a set of `'maybe'` formats as DRM and
  refuses. The direction is fail-safe, so this is not a `SEC-001` breach — but a user is told an
  item is DRM-protected when yt-dlp would have downloaded it.
- **`all` where yt-dlp uses `any`.** A mixed item is DRM to yt-dlp and not-DRM to the fallback.
  It only bites when `_has_drm` is absent, which is the one case the fallback exists for.

Also worth settling rather than inheriting: `_has_drm` is assigned `True` **or `None`**, never
`False`, so its absence does not distinguish "not DRM" from "never processed". Decide whether that
matters on the probe path, or record that it does not.

#### Acceptance criteria

- A test fails if the pinned yt-dlp stops writing `_has_drm`, and it does so by exercising
  yt-dlp's own code path rather than by matching text in its source. Whether that write is
  reachable offline is **unverified** and is the first thing to establish; if it is not, the
  weaker source-level check is acceptable **only** with that reason recorded beside it
- The canary names the yt-dlp version it was verified against, as the recorded-failure canaries do
- The `'maybe'` and `any`/`all` divergences are each either corrected to yt-dlp's rule or recorded
  as a deliberate difference with its reason — not left as an unexamined accident
- A mutation restoring the current fallback rule fails a test
- No test touches a DRM service, a real protected URL, or `allow_unplayable_formats`

#### Out of scope

- The taxonomy and retry policy in `core/errors.py`; `DRM_PROTECTED` stays non-retryable
- The UI half of the boundary — that is the criterion added to `T-017`
- Refreshing any fixture: `ai/TESTING.md` §5 makes that a deliberate act with its own task

#### Evidence, 2026-07-28

**The write is reachable offline, so the weaker source-level check was not needed.**
`YoutubeDL.process_video_result` computes `_has_drm` **before** it selects a format and mutates
the info dict in place, so the canary hands it a synthetic dict, ignores whatever the call goes
on to do, and reads the field back. Measured at zero DNS lookups with `format="all"` and
`check_formats=False`; without those, a `'maybe'` format sends yt-dlp looking for a host.

**Both divergences are corrected rather than recorded.** `format_has_drm` now implements yt-dlp's
three-state rule — `True`, absent, and `'maybe'`, which yt-dlp keeps downloadable — and the item
is protected if **any** format is, matching `_has_drm`. The `any`/`all` choice was not free, and
it is worth the reviewer's attention: a mixed item now reads as DRM, where the fallback used to
say it did not. That is not a new refusal in practice — `_has_drm` is `any`, and it is the branch
every real info dict takes — but it means one committed assertion changed.

**`test_a_partially_protected_item_is_not_treated_as_drm_only` is now
`…_is_treated_as_protected`.** Its old rationale ("one clean format means there is something
lawful to fetch") is a reasonable argument about a branch that never runs: production already
refused mixed items through `_has_drm`, and the test asserted the half of `has_drm` that does not
answer. The two halves of one function disagreed, which is what `T-057` was filed to find.

**The strongest test is the one that does not state its expectation.**
`test_the_adapter_and_yt_dlp_agree_about_every_shape_of_has_drm` runs five format shapes through
yt-dlp *and* through the adapter and compares. Both divergences were invisible to a test that
wrote down the expected answer, because the answer was written by whoever wrote the code.

**Mutations run, all killed:** the fallback restored to `all(entry.get("has_drm"))` · `'maybe'`
counting as DRM again · the canary reading a field yt-dlp does not write · the selection params
dropped so yt-dlp reaches for the network.

**The offline guard had to be corrected before it gated anything.** Raising from a patched
`getaddrinfo` does not fail the test: yt-dlp catches whatever a handler raises and re-reports it
as `NoSupportingHandlers`, which the surrounding `contextlib.suppress` then swallows. The attempt
is now recorded and asserted after the call, and the fourth mutation above proves it fires.

**Checks:** `ruff check .`, `ruff format --check .` (87 files), `mypy src` (35), configured `mypy`
and `mypy --platform win32` (72 each) all pass. Bare `pytest`: **1334 passed, 11 skipped,
1 deselected in 75.05 s**.

**Left open deliberately:** `_has_drm` is written as `True` or `None` and never `False`, so its
absence still does not distinguish "not DRM" from "never processed". It does not matter on any
path this application has — every info dict reaching `has_drm` has been through
`process_video_result` — and inventing a third state here would be this adapter asserting
something yt-dlp does not. Recorded rather than fixed.

---

### T-013 — Download manager and result pump

**Status:** **Complete — approved with follow-ups**, 2026-07-27. `T013-R1`, `T013-R2`, `T013-R3`
and `T013-R4` are all verified resolved; `T013-R3` took three passes and was closed by
**restructuring** the startup transaction rather than patching a third sibling of it, which is
the option the maintainer chose when authorizing the pass (`AGENTS.md` §9). `T013-R5` stays
non-blocking test hardening owned by `T-052`.

**Amended after approval by `T-016`** (`ARC-004`): `start()` now takes a `READY` job as well as a
`QUEUED` one, and `test_a_job_that_is_not_queued_cannot_be_started` — which asserted the older
rule — was replaced rather than deleted. This is the decision `T-051` made, not a defect in the
approved code; see `T-016`.

#### Third correction batch — `T013-R3`, restructured

**The same eight lines had failed review three times, each with a different sibling**: the
cleanup write, then the sentinel write, then a worker left running after its reader failed to
start. Every one had the same cause — the unwind inferred what existed from whichever locals
were in scope. So the shape changed rather than the symptom:

- **The session is created as soon as there is anything to own**, and each start is recorded on
  it the instant it returns. `process_started` and `pump_started` are separate facts because
  they fail separately: the single flag they replace was set only after *both* succeeded, so a
  pump that failed to start left a live worker the unwind could not see.
- **`_abort_start` reads that record instead of guessing.** A started process is killed; a
  started pump is ended with a sentinel, or terminated if the queue refuses one, and the session
  stays under watch until the thread reports itself finished — `T013-R4`'s rule, reused rather
  than re-derived.
- **Persistence comes first and both signals follow it.** `protocol_violation` was still emitted
  before the `FAILED` write, so an observer could read `PROBING` — a state nothing was working
  on any more.

**Mutation-checked: 4 mutations, 4 killed** — dropping the process reap, collapsing the two
start records into one, announcing the violation before persisting, and dropping a started pump
instead of watching it.

**One thing found while validating, worth knowing.** The full suite appeared to hang for ten
minutes. It was not the correction: earlier probes and a timed-out mutation batch had left
orphaned `spawn_main` workers reparented to the session manager, and they interfered with later
runs. That is `T-019`'s subject arriving in the development loop rather than in the product — a
harness that kills its own parent needs the same process-tree cleanup the application does.

#### Reviewer result on `d5034a0`

The reordered startup fixes the cleanup-sentinel failure but does not cover the entire
transaction the original finding named. Once `process.start()` succeeds, a later
`pump.start()` failure leaves a live worker: `session.started` is not set yet, the non-running
pump path closes the queue and drops the session, and nothing terminates or reaps the process.
The startup failure also still emits `protocol_violation` while the durable job is `PROBING`;
the `FAILED` write follows that signal. Both are deterministic reviewer probes under
`T013-R3`.

`T013-R4` is resolved. `_abandon()` finalizes the job and retains the session until the thread
reports finished; removing that finalization fails the direct mechanism test. Full evidence and
the merge verification are in `ai/REVIEWS.md`.

#### Second correction batch — `T013-R3`, `T013-R4` (maintainer-authorized 2026-07-27)

The maintainer authorized one further focused pass under `AGENTS.md` §9. The Implementer
returned both blockers as corrected; focused verification resolved `T013-R4` and kept
`T013-R3` open on the later pump-start and signal-order paths recorded above.

**`T013-R3` — the situation is removed, not merely handled.** The cleanup write could fail
because the thing that broke the session can break its queue too, and then its exception
replaced the original cause and the job stayed `PROBING`. Three changes, in order of how much
they matter:

- **The process now starts before the pump.** The old order existed on the theory that a worker
  failing instantly must not find nobody reading — but a `multiprocessing.Queue` writes into a
  pipe that buffers, so nothing is lost. Starting the pump first was what left a live thread
  blocked in `Queue.get()` after a failed spawn, and that thread has no reliable end: the
  sentinel may be refused, `terminate()` does not interrupt a blocked read, and **closing the
  queue does not wake a reader already inside `get()`** — probed, all three. After the reorder a
  spawn failure has nothing running to unwind.
- **The durable failure is recorded before any cleanup runs**, so nothing done for tidiness can
  pre-empt the record of what happened.
- **Every cleanup step is guarded** and reports rather than raising, including the same sibling
  in `_end_the_stream()`, which the audit found had the identical unprotected write.

**`T013-R4` — terminate is a request, not an event.** `_abandon()` now resolves the job durably
before anything can announce completion, and keeps the session until the thread reports itself
finished. If it never finishes, this manager never claims to be idle, which is the honest
answer; nothing releases early to make the number look better.

**Mutation-checked: 6 mutations, 5 killed — and the two that mattered only died after the tests
were rewritten.** Reinstating cleanup-before-persistence, the pump-first order, and an
`_abandon` that resolves nothing all **survived** the first battery, because the tests asserted
end states that several mechanisms can reach. They are now pinned at the mechanism: a queue that
records what the repository held at the moment it was written to, and `_abandon` driven directly.
**One mutation still survives, stated rather than filed away:** dropping the `isFinished()`
fallback in `_release()` leaves the suite green, because Qt's `finished` signal always arrives in
these tests. The fallback exists for a terminated thread that never delivers it, and no test can
construct that state today — `terminate()` does not act on a thread blocked in a read.

This is the `T013-R5` lesson applied to its own correction: the first battery's numbers were
measuring the tests, not the guards.

#### Focused re-review — `cc79bb8..65303a2`

The incremental protocol grammar and validation-before-routing production order resolve
`T013-R1`; the cancellation carve-out is appropriately limited to a session the user already
asked to stop. The event-driven shutdown entry point resolves `T013-R2`: `shutdown()` returns,
refuses new work, and uses timer-driven escalation without a positive-duration join or
`QThread.wait()`.

Two blocking cleanup edges remain:

- **`T013-R3`:** `_abort_start()` writes its cleanup sentinel before persisting the failed job,
  without protecting that write. A deterministic queue whose cleanup `put()` fails replaced the
  original spawn exception and left the repository at `PROBING`, exactly the cleanup-sentinel
  case the first review required the sibling audit to cover.
- **`T013-R4`:** `_abandon()` calls asynchronous `QThread.terminate()`, then immediately closes
  the queue and removes the session without observing `finished`. The next tick can emit `idle`
  while the pump is not finished, and the active job is left in its in-flight state. Retain the
  session until the thread actually finishes and durably cancel/fail the job before announcing
  idle.

The claimed route-before-validation mutation also survived independently: moving
`_routes[type(item)].emit(item)` immediately before `SessionValidator.accept()` left all five
parameterized illegal-message cases green. The production order is correct, so `T013-R5` is
Low/non-blocking; `T-052` owns assertions over every persisted transient state and every public
message route. The startup test's useful-message assertion is also vacuous because it ends in
`or True`; `T-052` removes that escape.

Exact archived-head validation passed: `ruff check`, `ruff format --check`, `mypy src`,
`mypy --platform win32 src`, focused manager/protocol/boundary tests (**175 passed, 3
skipped**), and the full default suite (**925 passed, 6 skipped, 1 deselected**). Reviewer-only
negative probes failed on both open blockers. Windows remains unverified.

#### Correction batch — `T013-R1`, `T013-R2`, `T013-R3`

**Each blocker was reproduced before it was fixed.** Twelve tests were written against the
committed head and observed failing: five illegal streams, a missing sentinel, a message after
the outcome, a blocking shutdown, a shutdown that accepted new work, and three startup failures.

**`T013-R1` — the grammar now runs before the message does.** The diagnosis was sharper than
the finding: the pump enforced *two* of the grammar's rules on arrival and deferred the rest to
a finalizer that ran after every message had already been routed, persisted and announced. So
the executable receiver was strictly weaker than `validate_sequence()`, the function the
acceptance criterion says it applies.

- `protocol.SessionValidator` is the same grammar in **incremental** form — `accept()` for
  everything decidable on arrival, `complete()` for the two rules that need the end of the
  stream. `validate_sequence()` is now a loop over it, so the whole-stream and per-message forms
  **cannot drift**; writing per-message checks into the pump would have been a second
  hand-maintained statement of one contract, which is the `T010-R1`/`T041-R2` shape.
- The pump validates, then routes, and **ends the stream on any violation** — which is what
  `ProtocolViolationError`'s own docstring already said should happen ("a bad sequence means the
  worker cannot be trusted at all") and what the first implementation did not do.
- The stream is now **bound to the job it was started for**. The old check only rejected a
  stream that *changed* job id; one consistently claiming to be another job passed.
- **A synthesised sentinel is reported as a violation.** The parent knows it manufactured one,
  so no new protocol machinery was needed — three lines.
- **The terminal transition moved to session end.** An outcome legal on arrival can still be
  followed by an illegal stream, and `COMPLETED`/`CANCELLED` are terminal, so a job moved there
  on arrival could not be corrected. Deferring costs one event-loop turn and is what makes the
  ruling below implementable at all.

**Maintainer ruling, 2026-07-27:** a violation **fails the job loudly**, even when a legal
outcome arrived first. The implementer had argued the first legal outcome should stand, on the
grounds that a file already on disk should not be re-downloaded; the maintainer ruled for the
reviewer's reading of "fail loudly". **Cancellation is the one exception** — killing a worker
mid-write routinely truncates its queue, and reporting the user's own cancel as a crash would be
worse than useless. The worker's own cancellation message is kept when it managed to send one,
because that is the evidence the cooperative path ran.

**`T013-R2` — shutdown is a lifecycle, not a call.** The "teardown is not an interaction"
argument was rejected, correctly: `NFR-001` and `ARCHITECTURE.md` §8 are unqualified, and a
blocking loop that pumps events to make progress re-enters the GUI it claims to be closing.
`shutdown()` now refuses new sessions, cancels the running ones, and returns; the same timer
finishes the work and `idle` announces completion. `_force_stop` no longer joins the process or
waits on the pump — it kills, ends the stream, and sets a deadline the tick honours. The
application closes in two steps: ask, then quit when told.

**`T013-R3` — the startup transaction now covers everything after the durable write.** Queue,
event, pump construction, pump start and process start are one `try`; any failure ends the
half-built session, drops it, and leaves the job **persisted as failed before the failure is
announced**. Tested by injecting a resource failure at each of the three construction points.

**Sibling audit** (`AGENTS.md` §9, the finding is a defect class): every other message-handling
path was checked for "acts before it validates". `_on_progress`, `_on_resolution` and
`_on_worker_finished` are all downstream of the same gate, so all three are now covered by it;
`_claim_outcome` keeps its duplicate check as defence in depth for a second route to the slots.

**Mutation-checked: 16 mutations, 16 killed.** Ten for `T013-R1` (including reinstating the
original route-then-validate order, which the new tests catch), three for `T013-R2`, two for
`T013-R3`, and one added afterwards: the shutdown deadline's hard stop **survived** the first
run, because the cancel escalation always finished first. Per `ai/TESTING.md` §13 that defaults
to "a test is missing", and it was — a manager whose cooperative grace is longer than the
shutdown budget now proves the deadline is shutdown's own. Its mutation kills by hanging, which
is the honest consequence of removing a hard stop.

**Checks after the corrections.** `ruff check`, `ruff format --check`, `mypy src`,
`mypy --platform win32 src` clean; **925 passed, 6 skipped, 1 deselected**. `T-011`'s 129
protocol tests pass unchanged against the rewritten `validate_sequence`, which is the evidence
that the grammar was reorganised rather than altered. Still Linux-only.

**What landed.** `downloader/result_pump.py` (a `QThread` doing a blocking read on one session's
queue, routing every declared message type to its own signal and ending on the protocol's
sentinel) and `downloader/manager.py` (`DownloadManager`: one worker per job, a pool of exactly
one, cancellation with cooperative → `terminate()` → `kill()` escalation, persistence of every
transition before the signal announcing it, and `WORKER_CRASH` for a session that reported no
outcome). Persistence is a `JobStore` protocol, injected; `downloader/manager.py` imports
neither `persistence` nor `sqlite3`, and a static test enforces that.

**Three things had to be added to `worker.py`, which the task's affected-surface list did not
name.** Each is a half of a `T-013` criterion that only the child can implement, and each is
recorded here rather than silently absorbed:

- **A cancel signal.** `run_session` takes an optional `CancelSignal`; the progress hooks check
  it *outside* their exception guard and raise yt-dlp's own `DownloadCancelled`, so the download
  unwinds through yt-dlp's cleanup and leaves a `.part` file in a known state. The check has to
  be outside the guard: `DownloadCancelled` is an `Exception`, so inside it, cancellation would
  have been swallowed as a hook failure while the download continued.
- **`spawn_session`.** A process entry point distinct from `run_session`, which exits with the
  session's code — a `Process` target's return value is discarded, and `REQ-028` needs that code.
- **An orphan guard.** `spawn_session` starts a daemon thread on `multiprocessing.parent_process()`
  and `os._exit`s when the parent dies. `daemon=True` alone is implemented by the *parent's* exit
  handling, so a `SIGKILL`ed application leaves the download running. Proven by mutation.

**Deviations and gaps, stated rather than absorbed:**

- **`start()` accepts only a `QUEUED` job.** `ARCHITECTURE.md` §5 has no `READY → PROBING` edge,
  so a job a previous probe left in `READY` cannot be handed to a download session that probes
  again. Phase 1's flow never produces that state; a probe-then-download flow (`T-016`, `T-018`)
  needs the state machine amended first, which is a Planner decision.
  **Amended by `ARC-004` (`T-051`, 2026-07-27), not corrected**: refusing `READY` was right for
  the machine as it stood, and the answer turned out to be a second *entry point* rather than a
  new edge — `start()` will accept `READY` and move the job straight to `RUNNING`, because a
  download's own extraction is not a probe. `T-016` makes that change; this contract is otherwise
  unchanged, and `READY → PROBING` still does not exist.
- **`shutdown()` blocks the GUI thread**, bounded by its timeout. It runs during teardown, when
  the event loop that drives escalation is ending; a non-blocking shutdown would return with
  workers alive and nothing left to reap them. `NFR-001` is about interactions, and there are
  none left. `start()` and `cancel()` are timed against the budget by test.
- **Progress bytes are not persisted per message** — only at transitions and terminal states. A
  write per progress update is an unbounded rate for a fact that is worthless after a crash, and
  recovery re-queues the job anyway (`T-014`).
- **The `history` table is still not written.** `STATUS.md` said this task owned it; the task's
  own scope, acceptance criteria and affected surfaces never mentioned it, and it cannot be done
  honestly yet — there is no `HistoryEntry` model, no `HistoryRepository`, and nothing reports
  the **format actually used**, so `history.format_used` could only be filled with the request's
  *selector*, which is a different fact. Filed as **`T-050`** rather than guessed at.
- **`entry_point` is a constructor parameter** (default `worker.spawn_session`). Not a mock: the
  tests that use it spawn real processes over real queues. It exists because the streams the
  receiving half must survive — two outcomes for one job, a bare dict, an exit reporting nothing
  — are ones a correct worker cannot produce.

**Evidence.** 25 tests in `tests/integration/test_manager.py`, 9 in
`tests/unit/test_manager_boundaries.py`. Cancellation and worker crash are exercised against
**real spawned processes**: `REQ-015`'s two-second budget is measured against a download with
bytes actually moving (a local HTTP server serving throttled `video/mp4` to the real generic
extractor), not against a sleeping worker — the gap `T-002` recorded. `REQ-028` is exercised by
`SIGKILL`ing a worker from outside the manager.

**Mutation-checked (15 mutations, 14 killed).** The orphan guard, the cooperative cancel check,
the escalation, sentinel injection for a dead worker (and again for a spawn that fails before
there is a worker at all), the no-outcome rule (twice: clean exit and `SIGKILL`),
exit-code-beats-message, `is_message()`, `validate_sequence()`, persist-before-signal, and
`shutdown()`'s final force-stop all die when removed. **One survivor, deliberately:**
`_claim_outcome`'s terminal-once check in the manager, which is redundant with `ResultPump`'s
suppression — removing *either* alone leaves the end-to-end test green and removing **both**
fails it, which is what redundancy looks like when it is demonstrated in both directions
(`ai/TESTING.md` §13). The pump's half now has its own test; the manager's stays as the guard
against a second route to those slots.

**Two false readings the mutation run produced first, both recorded because they nearly caused
harm.** The orphan test originally hosted its HTTP server inside the application being killed,
so the orphan died of a connection error and the guard was never involved — the mutation
survived and the test proved nothing. And two size-preserving mutations "survived" because
Python validated the cached `.pyc` by size and whole-second mtime and re-ran unmutated bytecode;
`ai/TESTING.md` §13 now records that trap.

**Checks.** `ruff check`, `ruff format --check`, `mypy src`, `mypy --platform win32 src` all
clean; **913 passed, 6 skipped, 1 deselected**. Windows evidence pending CI — the cancellation
budget, the orphan guard and `TerminateProcess` have only been observed on Linux.

**First review.** `ai/REVIEWS.md` records the full evidence. The correction batch must enforce
the session grammar before forbidden messages mutate durable job state, report a worker's
missing sentinel instead of making the synthetic sentinel indistinguishable from a real one,
replace GUI-thread-blocking shutdown with an event-driven lifecycle, and make every startup
failure leave a durable failed job with no leaked pump/session. Per `AGENTS.md` §9, reproduce
each blocker, audit its sibling paths, and mutation-check the corrections before re-review.

**Owner:** Implementer
**Priority:** High
**Phase:** Phase 1
**Depends on:** `T-012`, `T-014`
**Relevant context:** `ARCHITECTURE.md` §3, §8 (threading); `ARC-002`, `REQ-014`, `REQ-015`,
`REQ-018`, `REQ-028`, `NFR-001`, `NFR-003`; `ai/TESTING.md` §7 (Cancellation, Worker crash)
**Affected surfaces:** `downloader/manager.py`, `downloader/result_pump.py`,
`downloader/worker.py` (cancellation, the spawn entry point and the orphan guard — see above),
`pyproject.toml` (a `psutil` mypy override), `tests/integration/`, `tests/unit/`
**Risk:** **High** — owns process lifetime and the only thread in the application. Both of its
failure modes are silent: an orphaned worker, and a Qt object touched off the GUI thread.
**Current correction head:** `d5034a0`, merged by `7021a01`.
**Review base:** `a296615` (`T-012`, "Run yt-dlp in a spawned worker"). **Review head:**
`0a19daf` ("Add the download manager and result pump"), committed to `main` 2026-07-27 and not
pushed. `git diff a296615..0a19daf` is the review boundary; `T-014`'s persistence work
(`cfb66af`..`655f7f3`) sits between the two and is **already approved** — the changes this task
owns are `src/tracks_and_trails/downloader/{manager,result_pump,worker}.py`, `pyproject.toml`,
`tests/integration/{conftest,test_manager}.py`, `tests/unit/test_manager_boundaries.py` and the
`ai/` updates in `0a19daf`, so `git show 0a19daf` is the tighter and more useful diff.

#### Scope

The GUI-process half of `ARC-002`. A pool of exactly one for Phase 1 — concurrency is Phase 2,
and building the pool for N now would mean designing scheduling policy with no queue to test
it against.

- **`manager.py`** — starts a worker per job, tracks its lifetime, cancels it, reaps it, and
  turns a worker that died without a terminal message into `WORKER_CRASH` with its exit code
  (`REQ-028`).
- **`result_pump.py`** — a `QThread` doing a blocking read on the result queue and re-emitting
  each `T-011` message as a Qt signal. It is the **only** bridge from worker to GUI, and it
  communicates *only* by signal emission (`ARCHITECTURE.md` §8).

`manager.py` is the one `downloader/` module allowed to import Qt, because it emits signals.
`worker.py` still may not.

**Persistence is injected, not imported.** `ARCHITECTURE.md` §3 shows `DownloadManager` owning
a repository, and Phase 1 promises durable transitions — so the dependency on `T-014` stays.
But the manager must not know SQLite exists: it takes a **repository protocol**, is unit-tested
against a fake implementation, and receives the concrete `JobRepository` from `app.py` at
composition time (`T-036`). One integration test exercises the real repository. A widget is the
wrong place to create this boundary; `T-017` consumes durable state, it does not construct the
persistence seam.

Cancellation is the sharp end (`REQ-015`): try the cooperative path first — `DownloadCancelled`
raised from a progress hook, so partial files are left in a known state — then `terminate()`,
then `kill()` on a timeout. The 2-second budget is measured against a **real in-flight
download**, not a sleeping worker; `T-002`'s probe only ever proved the sleeping case and said
so.

#### Acceptance criteria

- Cancel terminates a **real in-flight download** within 2 seconds and leaves no orphan
  process, asserted programmatically rather than by watching a process list
  (`REQ-015`, `ai/TESTING.md` §7)
- `SIGKILL`/`TerminateProcess` of a worker yields `WORKER_CRASH` with the exit code recorded,
  and the application stays responsive (`REQ-028`)
- A worker that exits 0 without sending an **outcome** is also `WORKER_CRASH`, not a silent
  success — the case that looks like nothing went wrong. "Outcome" is `protocol.is_outcome()`,
  which covers `Probed` as well as `Succeeded`/`Failed` (`T011-R1`): a successful probe is a
  complete session, and treating it as outcome-less would fail every probe the application ever
  makes
- **Terminal-once is enforced, not merely assumed** (`T011-R4`). After one outcome for a job id,
  a second `Succeeded`/`Failed`/`Probed` for that id is a protocol violation: it is reported and
  **must not** produce a second state transition or a second signal. Asserted by a test that
  sends two outcomes and observes exactly one transition. `T-011` specifies this rule and
  `protocol.validate_sequence()` expresses it; without this criterion the rule had no owner that
  any test would check
- `protocol.validate_sequence()` is applied to each completed session, and a violation is
  surfaced rather than swallowed — an undeclared object, a missing sentinel, or messages after
  the outcome each fail the job loudly instead of hanging the pump
- No orphan survives application exit, including a job cancelled during shutdown
- The GUI thread is never blocked: an assertion that no manager or pump call performs a
  blocking wait on the GUI thread (`NFR-001`)
- **No Qt object is touched off the GUI thread.** The pump's only interaction with the GUI is
  signal emission; a test asserts messages arrive on the GUI thread, since this is the
  standing risk `ai/REVIEWS.md` names and it produces intermittent failures rather than
  errors
- Every `T-011` message type is routed to a signal; an unhandled type raises rather than being
  dropped
- The manager is constructed with a fake repository in unit tests and never imports
  `persistence` directly — asserted, so the injected boundary cannot quietly collapse
- Every state transition the manager performs is persisted before the corresponding signal is
  emitted, so a crash between the two cannot leave the UI ahead of the database
- **Shutdown is deterministic:** the pump exits on a protocol sentinel rather than on a
  timeout, and a test asserts no thread is left blocked in `Queue.get()` after shutdown
- **The terminal-message/exit race is handled:** a worker that sends a terminal message and
  then exits non-zero is reported by its message, not as `WORKER_CRASH`. A test forces that
  ordering, because the naive implementation checks the exit code first and manufactures a
  crash from a successful download
- Killing the parent does not leave the child running

#### Out of scope

- More than one concurrent job, scheduling, priority, pause/resume — Phase 2
- Retry policy and backoff — Phase 2; this task reports failures, it does not re-run them
- Any widget — `T-016`, `T-017`

---

### T-015 — Built-in presets and selector translation

**Status:** **Complete — approved**, 2026-07-27. `T015-R1` and `T015-R2` are both verified
resolved; `T015-R2` was the High regression the first correction introduced, and closing it meant
removing the widened fallback rather than widening it once more.

#### Reviewer result on `0973fee`

The MP4 constraint and preset-owned override guard resolve `T015-R1`. The replacement final
fallback introduces `T015-R2`: `bestvideo[height<=1080][ext=mp4]` selects a video-only MP4
when the available audio is not M4A. The pinned engine returned one row with `acodec="none"`
from a 720p MP4-video + WebM/Opus-audio set. The committed branch table never isolates that
fallback because its 720p row is pre-muxed and matches the preceding `best[ext=mp4]` branch.
Fix the silent-audio regression and add a branch-distinguishing real-engine test.

#### Correction batch — `T015-R1`

The Implementer closed the two routes in `T015-R1`: a named or displayed choice that was not
the request that ran. Focused verification resolved R1 and found the separate silent-audio
regression `T015-R2` recorded above.

**The preset's name is a promise about the file.** `BEST_VIDEO_1080P`'s last fallback was a bare
`best[height<=1080]` with no container constraint, and fed a site offering only WebM the real
selector engine picked the WebM. Every branch is now constrained to MP4, so a site with no MP4
fails the preset rather than substituting a container nobody chose — and yt-dlp's own message
says so (`REQ-005`). Converting instead would be a post-processing decision (`REQ-010`) and
belongs to a preset whose name says so.

**Overrides may no longer touch a field the preset owns.** `to_request(**overrides)` let a
caller pass `format_selector="worst"` and get exactly that while `effective_selector()` still
displayed the preset's string — which defeats the single thing `REQ-009` promises. The owned set
is **derived from both dataclasses**, so a field added to `Preset` is protected the day it
appears; the sibling audit the finding asked for is the derivation itself rather than a list.
Settings a preset does not own — proxy, rate limit, cookie source — are still accepted.

**The tests now ask yt-dlp, not the string.** The capability check that let this through asked
whether the selector *contained* `ext=mp4`, which stayed true while a later branch permitted
something else. The committed cases use the pinned engine's own `build_format_selector`, and
the WebM-only case selects nothing. They do not isolate the new `bestvideo`-only fallback;
`T015-R2` owns that missing branch observation.

**Mutation-checked: 2 mutations, 2 killed** — restoring the unconstrained fallback, and dropping
the override guard.

**What landed.** `core/presets.py`: the five `REQ-006` presets, `to_request()`,
`effective_selector()`, `by_name()` and `custom_preset()` for `REQ-009`'s raw-selector escape
hatch. No `yt_dlp`, no Qt — it emits selector strings and option *values*, and
`ytdlp_adapter.py` turns those into yt-dlp's dict.

**`Preset` gained four fields**, which the task did not name: `audio_codec`, `audio_quality`,
`subtitle_languages`, `embed_subtitles`. Without them a preset cannot say what "audio only
(MP3)" *means* — `REQ-006`'s two audio presets would differ only in their names, which is
`T012-R5` exactly one layer up, where omitting `preferredcodec` left yt-dlp keeping the source
codec and the MP3 preset converting nothing. Every `Preset` field is now a `DownloadRequest`
field under the same name, and a test derives that correspondence from both dataclasses.

**One deviation, stated.** The criterion asks this module to reject an empty or non-string
selector *for built-ins only*. It does not: `Preset` and `DownloadRequest` already refuse both,
for every preset, so a check here could never be reached by a test — a branch that reads as a
guard while protecting nothing. The behaviour the criterion asks for is asserted where the value
is constructed, including through `custom_preset()`. Making it unrepresentable is the same
resolution `T-014` reached for proxy credentials.

**Evidence.** 86 tests in `tests/unit/test_presets.py`. `REQ-006` is transcribed as five
*capabilities* — questions asked of the request a preset produces — rather than as a list of
names compared with the module's own list, which is the `T041-R2` shape. Each capability must
be answered by **exactly one** preset, and every preset must answer one, so the check is an
equality in both directions. The last section asserts through `ytdlp_adapter`, on the far side
of the boundary: a preset that sets a field the adapter never reads has chosen nothing.

**Mutation-checked (6 of 6 killed).** Dropping `audio_codec` from the translation, returning a
friendly label from `effective_selector`, the MP3 preset losing its codec, `custom_preset`
validating a user's selector, the subtitle preset losing `embed_subtitles`, and `Preset`
dropping its audio-quality check — which **survived** the first run, because the validator was
added and never asserted. Per `ai/TESTING.md` §13 that defaults to "a test is missing", and it
was; the test now kills it.

**First review.** `ai/REVIEWS.md` records the full evidence. The correction must ensure every
branch of the 1080p-MP4 selector can only produce MP4, and must prevent `to_request()` overrides
from replacing preset-owned choices while `effective_selector()` continues to display the
original. Freeze both negative cases through yt-dlp's real selector engine and the complete
preset-to-request API, audit sibling preset-owned fields, and mutation-check the corrections.

**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 1
**Depends on:** `T-010`
**Relevant context:** `REQ-006`, `REQ-008`, `REQ-009`; `ARCHITECTURE.md` §4, §6
**Affected surfaces:** `core/presets.py`, `core/models.py` (`Preset`'s four new fields),
`tests/unit/test_presets.py`
**Risk:** Low — pure translation, fully unit-testable
**Review base:** the `T-010` merge commit. **Review head:** `0973fee`, merged by `7021a01`;
`core/presets.py` and the `Preset` half of `core/models.py`.

#### Scope

The named presets `REQ-006` requires, at minimum: best video ≤1080p (MP4), best video
available, audio only (MP3), audio only (best/original), and video with embedded subtitles.
Plus the translation from a `Preset` to the fields of a `DownloadRequest`.

**This module produces data, not yt-dlp calls.** It emits format selector strings and option
values; `ytdlp_adapter.py` turns those into a yt-dlp options dict. That split is what keeps
`core/` free of `yt_dlp` (`ARCHITECTURE.md` §6) and is enforced by the layering test.

`REQ-009` requires the **effective selector to be visible for every preset**, so a user can
learn the syntax and then write their own. That means the selector string is a first-class
output of translation, not an internal detail.

#### Acceptance criteria

- Every preset named in `REQ-006` exists and translates to a `DownloadRequest`
- Each preset exposes its effective selector string, and the string is what translation
  actually uses — not a separately maintained label that could drift (`REQ-009`)
- A raw user-supplied selector passes through unchanged, including strings the project does
  not understand — the escape hatch is not validated into uselessness (`REQ-009`)
- **The validation boundary is explicit**, because "accept anything unknown" and "reject
  malformed" otherwise contradict each other. Only two structural conditions are rejected, and
  only for **built-in presets**: an empty selector, and one that is not a string. A
  user-supplied selector is never rejected for content — yt-dlp is the judge of whether it
  resolves, and a test asserts a deliberately nonsensical user selector survives untouched
- `core/presets.py` imports no `yt_dlp` and no Qt

#### Out of scope

- Custom user-defined presets and their TOML persistence — Phase 4
- The format table and per-format selection UI — `REQ-003`/`REQ-008`, Phase 3
- Whether a selector actually resolves against a real site — that is yt-dlp's judgment

---

### T-018 — Recorded `info_dict` fixtures and projection tests

**Status:** **Complete — closed as Approved**, 2026-07-27 on the fifth correction.
`T018-R2` is verified resolved, closing `T012-R6`. `T018-R1` (Critical) survived three recogniser
corrections; the fourth made the allowlist the control, which the reviewer verified works. The
fifth removed the *secondary* record that came with it — `SEC-002` is **amended**: a schema
fingerprint copies mapping keys verbatim, and a mapping key is captured data. The reviewer
confirmed no privacy-boundary escape remains.

#### Fifth correction batch — `T018-R1` (Critical, in the authorized design; `SEC-002` amended)

The allowlist held. What failed was the thing standing beside it: `capture.write()` given
`{"unknown_map": {"credential-value-as-key-7c6c": "ignored"}}` wrote that key into `_schema`, and
the key gate, the schema-leaf check and the text scanner all reported the file clean. "Names are
schema, values are data" was the wrong line — nested maps are routinely keyed by data.

- **The fingerprint is deleted, not sanitized.** A name-free version could say only "a mapping of
  nine things, one of them a list": it identifies nothing that changed, churns on every yt-dlp
  release, and remains a second place data can appear. Hashing was rejected because the material
  at risk is low-entropy personal data. `SEC-002` records what this gives up — detecting a rename
  in a field the adapter never reads, which was the fingerprint's only unique job.
- **`write()` derives everything it writes.** It used to accept a caller-supplied `_schema`, so a
  value that had never been through the allowlist reached disk. Nothing outside `_fixture`,
  `info_dict` and `error` is carried now, and those three are rebuilt rather than copied.
- **A playlist entry is a count.** `ytdlp_adapter` reads `len(entries)` and never looks inside
  one, but capture recursed into each entry and kept its consumed fields — the largest body of
  retained data in the set, held for no reader. Entries are placeholders; the playlist fixture
  went from 12 KB to 1.4 KB.
- **The gate refuses both independently.** Removing the writer's ability to emit a `_schema` is
  half the fix; `unexpected_keys()` rejecting a restored one, and rejecting any key inside an
  entry, is the half that survives somebody putting it back or hand-editing a fixture.

**The fixtures were re-applied, not re-captured.** Each committed file was fed back through
`capture.write()` — no network call, no new extraction — so every one is by construction what the
writer produces under the amended policy. The `captured` dates still describe the extractions
they came from, which is what they always meant.

**Mutation-checked: 12 mutations, 12 killed**, including the four the reviewer named as unmutated
last round: a restored `_schema` accepted by `write()`, entry recursion restored, the gate
accepting a `_schema` block, and the gate accepting entry contents.

#### Fourth correction batch — `T018-R1` (Critical, structural; `SEC-002`)

The reviewer declined to return this for a fifth marker list, and was right to: four passes had
each closed the reported spellings and left another the rule was never written to see. The
maintainer authorized the scope change the reviewer recommended; it is recorded as `SEC-002`.

**The recogniser is no longer the control.** `capture.write()` commits values only for the fields
`ytdlp_adapter.py` demonstrably reads, plus the reviewed provenance and error fields
(`CONSUMED_TOP_LEVEL`, `CONSUMED_FORMAT`, `ALLOWED_FIXTURE_FIELDS`, `ALLOWED_ERROR_FIELDS`).
Every other key is **dropped, not redacted** — a dropped key cannot leak what it held, and cannot
become a leak later when yt-dlp adds a field nobody has thought of. The question stops being
"does this look like a secret?", which has no closed answer, and becomes "does the projection
read a field by this name?", which does.

**Upstream churn survives without values.** `schema_fingerprint()` records the discarded data's
key names, container shape and scalar *types*, never a scalar value. `NFR-008`'s canary still
fires on a rename; a fingerprint cannot carry data. The trade is stated in `SEC-002`: a field the
adapter never reads changing *shape* is no longer a test failure, only a fingerprint diff.

**The allowlist is transcribed on one side and derived on the other.** A test walks
`ytdlp_adapter`'s AST and asserts its real reads are a subset of the allowlist, so a field the
adapter starts reading fails the suite until it is listed. Same shape as the preset/request
correspondence test, and for the same reason (`ai/TESTING.md` §13).

**All five fixtures were re-captured**, and `T-012`'s `archive_org_big_buck_bunny` was
force-refreshed rather than left alone this time: its provenance described a policy that no
longer holds. Two of `T-012`'s assertions moved from "the value is `<redacted>`" to "the key is
absent", which is what the policy now promises. The playlist fixture fell from 45 KB to 12 KB.

**Mutation-checked: 10 mutations, 10 killed — after a survivor found a real hole.** The battery
was re-run from a written list rather than reported from memory, and one mutation survived:
removing `clean_scalar`'s user-directory branch left every test green. The key allowlist answers
*may this field carry a value*, not *what is the value* — and `title` or `url` can be a local
path. `test_a_consumed_field_still_loses_a_user_directory` now asserts that at `write()` across
five path shapes, and the mutation dies. The other nine: the allowlist iterating the info dict
instead of itself; the same for format keys; the fingerprint recording values; the fingerprint
flattening container shape; `ALLOWED_QUERY_PARAMETERS` gaining a signed-URL parameter; `redact_url`
keeping userinfo; keeping the fragment; and the provenance and error blocks each bypassing their
allowlist.

#### Reviewer result on `0973fee`

The multi-item projection resolves `T018-R2` and closes `T012-R6`. The privacy gate remains
false-negative in both halves:

- `capture_info()` and `capture_error()` add `source_url` metadata without sanitizing it;
- a Windows profile outside `C:` (for example `D:\Users\Sean`) survives both `redact()` and
  `leaks_in()`; and
- a bearer token in a URL fragment survives both halves.

The current fixtures contain no established live secret, but a future refresh can still write
private material into a file the committed scanner calls clean, so `T018-R1` remains Critical.
Apply sanitization to capture-owned metadata/error fields and make both independent gates
drive/UNC-independent, case-insensitive, and fragment-safe. Full probes are in
`ai/REVIEWS.md`.

#### Correction batch — `T018-R1`, `T018-R2`

**`T018-R1` — attempted fail-closed correction.** The batch fixes the original tuple,
ordinary-query and userinfo cases below. Focused verification found capture-owned metadata,
non-`C:` Windows profiles and URL fragments still bypass both halves, so R1 remains Critical:

- **Every container is walked.** `redact()` recursed through `dict` and `list` only, so one
  tuple anywhere in the graph carried everything beneath it through — and yt-dlp's info dicts
  contain tuples. It now walks every container the JSON encoder can serialise, and asserts on
  Python objects rather than JSON text, because **a tuple cannot be written in JSON**: the
  committed-file scanner is structurally unable to see this class, which is exactly why the
  sanitizer has to fail closed rather than be checked after the fact.
- **Query parameters are an allowlist, and it is empty.** The blocklist enumerated names it had
  thought of, so `X-Amz-Signature`, `X-Amz-Credential` and `X-Amz-Expires` were not missed —
  they were outside the question. Nothing downstream reads a query parameter, so the honest
  default is to keep none. URL userinfo is dropped for the same reason. The committed-file gate
  made the same inversion **independently**, and still shares no constant with the sanitizer.
- **Credential keys match by substring, case-insensitively.** Four exact spellings meant
  `Cookie`, `set-cookie` and `authorization` all walked past.

**A test the corrections added found a third gap immediately.** Putting every leak shape through
the sanitizer and then back through the gate showed the sanitizer never looked at local
filesystem paths, which the gate rejects — so a refresh would have produced a fixture that could
not be committed. `NFR-007` covers those too; the sanitizer now removes them.

**All five fixtures were re-captured under the new policy**, and the derived DRM one regenerated
from the new capture, so no committed fixture claims a redaction policy that no longer holds.
`T-012`'s `archive_org_big_buck_bunny` is deliberately **not** refreshed: refreshing is meant to
be a deliberate act with its own task, and it passes the new gate unchanged.

**`T018-R2` — both of yt-dlp's multi-item types.** `MULTI_ITEM_TYPES` is transcribed from the
extractor documentation (*"`multi_video` indicates that there are multiple videos that form a
single show"*), not derived from yt-dlp's code, so an upstream addition surfaces as a
disagreement rather than as a playlist silently reported as one item. Both project the same
way: `REQ-002` asks one binary question, and inventing a third state it does not name would push
the choice onto every reader. The sibling audit caught `_entry_count` too — `str` and `bytes`
are `Sequence`s, so a malformed `entries` of `"two"` was counted as three characters.

**`T012-R6` is closed.** The projection blocker on `T-016` is resolved; T-018 itself remains in
review on the independent Critical privacy finding.

**Mutation-checked: 9 mutations, 9 killed.** Dict/list-only recursion, exact-match credential
keys, a parameter blocklist in the sanitizer *and* in the gate, userinfo left in place, local
paths left in place, `multi_video` dropped, and `entries` counted by `Sequence` alone.

#### Third correction batch — `T018-R1` (Critical, third pass)

Two false negatives survived the second correction, and both came from a fix made carelessly
in the previous batch:

- **A key named exactly `auth` was written out intact**, by both halves. `auth` had been dropped
  from the marker list because it is a prefix of `author` — a real collision answered the wrong
  way. Keys are now split into words (across delimiters *and* camelCase) and short markers match
  a whole word, so `auth`, `X-Auth` and `authToken` are caught while `author` is not.
- **`\\server\Users\name` survived both patterns**, which required a share component *before*
  `Users`. When the share is itself the profile root there is no such component. Both now accept
  one or more components.

**The gate gained the half it never had.** It only ever read the file as text, and a key is not
visible in text — so it now also walks the parsed object and fails any credential-named key whose
value is not the redaction marker. Its word list is transcribed separately from the sanitizer's,
because the two agreeing is the point and a shared constant would hide it when they stop.

`key` is deliberately in neither list: it is a whole word in `extractor_key`, which yt-dlp puts
on every info dict, so including it redacted real projected data.

**Mutation-checked: 6 mutations, 5 killed.** Three of the first four survivors were missing
tests, and each named the discriminating case the existing ones had missed — `authToken` was
already caught by the `token` substring, so it never exercised the splitter; the UNC shape sat
under a `cookiefile` key, so the key rule caught it before the path rule could. The survivor
that remains removes an *assertion from a test* rather than weakening a guard, and no suite can
detect the deletion of its own coverage.

**All five fixtures were re-captured again**, because their provenance blocks still described the
previous policy.

#### Second correction batch — `T018-R1` (Critical, still open after the first)

The re-review found three more false negatives, all of the same shape: a rule that enumerated
where it should have constrained.

- **The metadata was never sanitized.** `source_url` is captured data — whoever asks for a
  capture supplies it — and it was written into the provenance block raw while the `info_dict`
  beside it was carefully cleaned. `write()` now sanitizes the **whole payload**, so no field can
  be forgotten: sanitizing field by field is precisely the arrangement that forgot one. The
  redaction record became a single sentence, because a metadata key named
  `credential_key_markers` would have been redacted by its own policy.
- **Home directories are not confined to `C:`.** `D:\Users\…`, a redirected profile and a UNC
  share all produced no finding. Both halves now match a *pattern* — any drive letter, either
  slash, UNC shares, case-insensitive — rather than a prefix list.
- **URL fragments are a bearer-token location.** `#access_token=…` is where an OAuth implicit
  flow leaves one, and a check that only knew about `?` called it clean. The sanitizer drops
  fragments; the gate reads them as parameters.

Tests now sit **at `write()`**, the door every capture goes through, rather than only against
`redact()` in isolation. **Mutation-checked: 5 mutations, 5 killed.**

#### Second correction batch — `T015-R2` (High, a regression from the first)

The `T015-R1` correction replaced an unconstrained fallback with `bestvideo[…][ext=mp4]`, which
by definition accepts a **video-only** stream — so the preset produced a mute file. Same cause
as the finding it was fixing: a fallback widened until something matched.

The fallback is **gone** rather than widened again. Two branches remain, and each yields a
watchable MP4: a real MP4/M4A pair to merge, or a pre-muxed MP4. A site with MP4 video and only
non-MP4 audio now fails the preset — merging those would produce an MKV, breaking the container
half of the same promise.

The test that missed it asserted the extension only, and its "720p" row was pre-muxed, so the
branch under test was never reached. Cases now reach **one alternative each**, and assert audio
as well as container. **Mutation-checked: 1 mutation, 1 killed.**

**What landed.**

- **The playlist projection (`T012-R6`).** `MediaInfo` gains `is_playlist` and `entry_count`,
  and `project_media` reads `_type` — yt-dlp's own structured answer — rather than guessing from
  the presence of `entries`. `entry_count` prefers `playlist_count` (what the *site* reported)
  over `len(entries)` (what this extraction happened to materialise), because flat extraction or
  a page limit makes the second smaller and reporting it would understate a playlist silently.
  A count on something that is not a playlist is **unrepresentable**, not merely discouraged.
- **Four new fixtures**, three recorded and one derived: an audio-only item, a real seven-entry
  playlist, and two recorded *failures* — `UnsupportedError` and a real 404 — carrying the
  exception type, where it lives, its verbatim message, and the taxonomy kind
  `ARCHITECTURE.md` §7 says it must become.
- **`tests/fixtures/capture.py`**, so taking or refreshing a fixture is reproducible rather than
  remembered. It sanitizes on the way in, because a committed leak is permanent.

**`build_options` was left alone, and that is a finding.** The task's premise was that
`noplaylist=True` would prevent a probe from ever seeing a playlist. It does not: for a
playlist *URL* the extractor still returns `_type: "playlist"`, and the flag only decides what
happens to a video that merely sits in a playlist's context. Verified against the real
extractor before writing any code, so the probe options are unchanged.

**DRM cannot honestly be recorded.** Capturing a real DRM-protected item means probing a DRM
service, which needs credentials and is what `REQ-EXCL-001` and `SEC-001` put out of scope. The
fixture is therefore **derived** — a real archive.org capture with the two DRM flags set by hand
— and says so in its own metadata, listing which fields are synthetic. Every fixture now
declares `capture_method`, and a test rejects a derived one that does not admit what it is.

**Evidence.** 70 tests in `tests/unit/test_fixtures.py`, plus one model invariant in
`test_models.py`. The sanitization scan reads each file **as text**, because the real leak was
nested three levels down inside a playlist's entries' formats, where a top-level check sees
nothing. The scanner is itself mutation-proofed by a test that feeds it six real leak shapes.
Coverage is asked of the fixtures' *contents*, not their filenames.

**Mutation-checked (6 of 6 killed).** The projection ignoring `_type`; `entry_count` preferring
`len(entries)`; `MediaInfo` accepting a count on a single item; the leak scanner losing the
browser identity; the leak scanner losing Windows paths (which found a real hole first — the
scan reads JSON text, where a Windows path is escaped, so checking only `C:\Users` missed
`C:\\Users`); and `UnsupportedError` falling out of the taxonomy, which the recorded-failure
fixture catches.

**First review.** `ai/REVIEWS.md` records the full evidence. The correction must make capture
sanitization and the independent committed-file scanner fail closed on signed URL credentials
and cookie material across every JSON-serializable container shape, and must project yt-dlp's
declared `multi_video` result as multi-item rather than single-item. Add hostile negative cases,
audit sibling URL credential forms and container shapes, and mutation-check the corrections.

**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 1
**Depends on:** `T-012`
**Relevant context:** `ai/TESTING.md` §5 (fixtures), `NFR-008`, `C-002`, `REQ-026`, `NFR-007`
**Affected surfaces:** `tests/fixtures/infodicts/`, `tests/fixtures/errors/`,
`tests/fixtures/capture.py`, `tests/unit/test_fixtures.py`, `tests/unit/test_models.py`,
`core/models.py`, `downloader/ytdlp_adapter.py`
**Risk:** Medium — a carelessly refreshed fixture hides the upstream breakage the fixture
exists to catch
**Review base:** the `T-012` merge commit. **Review head:** `0973fee`, merged by `7021a01`;
corrections at `73d04c6` (third), `2f85a32` (fourth, structural — `SEC-002`) and the fifth
below (`SEC-002` amended)
**Blocks:** the `T012-R6` projection blocker on `T-016` is resolved; T-018 itself remains in
review on `T018-R1`

#### Scope

Broaden the fixture set `T-012` bootstrapped: several sites, a playlist, an audio-only case,
a DRM-protected case, an unsupported URL, and an extractor error. Each records the yt-dlp
version and capture date (`ai/TESTING.md` §5).

**Also owns the playlist/single-item projection** (`T012-R6`, carried from the `T-012` review).
`REQ-002` requires a probe to say whether the input is a single item or a playlist, and today
no typed value can express it: `MediaInfo` has no such field, `project_media()` cannot preserve
one, and `build_options` sets `noplaylist=True`. `T-016` promises to *display* the distinction,
so it cannot be built until something can carry it.

Assigned here rather than to the `T-012` correction batch because it needs a recorded playlist
fixture to be tested against at all, and this task is where that fixture is captured. **`T-016`
therefore depends on this task**, not merely on `T-012`.

Fixtures are **sanitized**: no cookies, tokens, session or auth query parameters, and no
personal paths (`REQ-026`, `NFR-007`). They are committed, so a leak here is permanent.

#### Acceptance criteria

- Each fixture records the yt-dlp version and capture date alongside it
- A fixture containing a cookie, token, auth query parameter, or a path under `/home` or
  `C:\Users` fails a sanitization check — asserted by a test that scans the fixture directory,
  not by review discipline
- The projection test fails when a projected key changes shape, which is the whole purpose
- When a fixture changes shape the test **names the field that moved**, rather than reporting
  a generic mismatch, so the diff is diagnosable
- Fixture provenance is machine-checked: every fixture has a recorded yt-dlp version and
  capture date, and one lacking either fails. *(Requiring a human to explain why a fixture
  changed is a review convention from `ai/TESTING.md` §5, not an executable criterion — it is
  stated there and deliberately not restated here as if a test enforced it.)
- Fixtures cover at minimum: a normal video, an audio-only case, a playlist, `DRM_PROTECTED`,
  `UNSUPPORTED_URL`, and `EXTRACTOR_ERROR`
- No test in this task touches the network

#### Out of scope

- The `-m network` suite that hits real sites — it exists and stays opt-in
- Automatic fixture refresh; refreshing is deliberately manual

---

### T-038 — Logging with handler-level redaction

**Status:** **Complete — approved**, 2026-07-27 at `098ba3f`. Critical `T038-R1` and High
`T038-R2` are both independently resolved; `T038-R2` took three focused corrections, the last of
which made a same-job reopen return the identical still-attached handler and made `idle` wait
asynchronously for listener completion with a bounded escape (`gave_up_on_the_log`). `T013-R2`,
`T013-R3` and `T013-R4` were re-examined and remain resolved. Known limits the reviewer named and
did not treat as blocking: a single Windows CI run, GUI-thread calls through independently wedged
handlers, and the live-handler-list concurrency proof deferred to `T-053`.
**Owner:** Implementer
**Priority:** High — `NFR-007` is a privacy promise and worker diagnostics are where it leaks
**Phase:** Phase 1
**Depends on:** `T-011`
**Relevant context:** `ARCHITECTURE.md` §8 (Logging); `REQ-026`, `NFR-007`, `NFR-004`
**Affected surfaces:** `core/` logging setup, `downloader/worker.py`, `tests/unit/`
**Risk:** **High** — a leak here is written to disk and survives
**Review base:** the `T-011` merge commit

#### Scope

**Filed after review: nothing owned logging.** `ARCHITECTURE.md` §8 promises an application log
in `user_cache_dir`, per-job logs, and redaction **at the handler level rather than at each
call site** — precisely so a forgotten call site cannot leak. No Phase 1 task owned any of it,
while `T-012` and `T-013` are about to generate the diagnostics most likely to carry a
tokenized URL or a cookie path.

Configure logging for both processes, add per-job log files, and implement the redacting
handler: cookie file paths, cookie contents, proxy credentials, and token-like URL query
parameters (`REQ-026`, `NFR-007`).

Handler-level is the whole design. A redaction helper that call sites must remember to use is
the thing this task exists to avoid.

#### Acceptance criteria

- A log record whose message contains a cookie path, cookie content, proxy credential, or a
  token-like query parameter is redacted **in the emitted output**, asserted by writing through
  a real handler rather than by calling a redaction function directly
- Redaction survives every formatting route: `%`-style args, f-strings pre-formatted by the
  caller, `extra=` fields, and an exception traceback carrying a URL in its message
- A deliberately careless call site — logging a full request object — still produces redacted
  output, which is the property that distinguishes handler-level from call-site redaction
- Worker logs reach the parent's log without the child needing Qt
- Logs are written under `platformdirs`, never beside the application (`NFR-004`)
- A test scans a generated log for a known token and fails if it appears in any form

#### `T038-R1`, `T038-R2` — corrected 2026-07-27, awaiting re-review

`T038-R1` was **resolved** by the focused correction re-review of 2026-07-27 (`ai/REVIEWS.md`).
`T038-R2` stayed open at that pass and is corrected a second time below; it continues under
`AGENTS.md` §9, which does not stop correction of a High defect at the ordinary pass budget.

**`T038-R1` (Critical) — five false negatives, all reproduced first.** Four were shapes the rules
could not see: a path component containing a space, a cookie filename with no directory, a URL
malformed enough to break `urlsplit` — which then returned it **unchanged**, so being harder to
parse made a string safer — and a proxy credential written the ordinary way, with no scheme for
the URL rule to anchor on. All four are closed, and `_bare_url()` now fails closed on a parser
error.

**Closing them nearly broke the log in the other direction.** The first fix matched any token
containing "cookie", which turned "loading cookies from the browser profile" into
"loading `<redacted>` from the browser profile" — the `T014-R6` failure wearing a different hat.
The rule is split in two: a path *with* a directory, and a bare filename that must carry an
extension. An extension is what separates a filename from a noun.
`test_ordinary_prose_survives_the_cookie_rules` holds that boundary, and the mutation removing
the extension requirement is killed by it rather than by a redaction test.

**The fifth shape is the authorized carve-out.** A bare `NAME=value` with nothing around it stays
out of scope, on the maintainer's decision of 2026-07-27, and `ARCHITECTURE.md` §8 now states it
— together with the reconciliation the review asked for: `REQ-026` and `DAT-003` preserve a cookie
path inside a *stored diagnostic* because `NFR-006` requires that message verbatim, while a log
is written by this application rather than quoted by it. The two sinks differ on purpose.

**`T038-R2` (High) — per-job logs are wired, isolated, and closed.** `open_job_log()` had no
production caller at all. `DownloadManager` now opens one per session and closes it on every exit
path including the startup unwind; `shutdown()` stops the process-wide listener. Isolation is
real rather than incidental: the worker stamps each record with its job id and the per-job handler
admits only that job's, so an unstamped record is refused rather than shared — a per-job log whose
contents depend on which other jobs were open is worse than none. `job_log_path()` sanitises the
id through `core/paths.py` instead of asserting that every id is a UUID, which is a fact about
today's callers and not a property of the type.

#### `T038-R2` — second correction, 2026-07-27, awaiting re-review

The routing above held; both **ends of the lifecycle** were wrong, and each had a deterministic
probe against it in the review.

**The close came before the records did.** Results and log records travel on two different
queues, and only the result queue tells the manager a session is over. So `_release()` closed the
per-job handler while a line the worker wrote before its `WorkerFinished` was still in the log
queue: that line reached the application log alone, and the per-job file — the one a user is
pointed at — stayed empty.

The ordering is now **established rather than waited for**. `close_job_log_when_drained()` puts a
marker record on the log queue and hands the handler over; everything the worker wrote is already
ahead of it, because the worker's process has exited and a `multiprocessing.Queue` flushes its
feeder before it goes. When the listener reaches the marker it has, by construction, already given
every one of those records to that handler, so the close happens **there, on the listener thread**,
and nothing on the GUI thread waits for it. It fails closed in every direction that was reachable:
no listener, a queue that refuses the marker, a marker that never comes back, and a second session
opening the same job's file — see the third correction below for what that last one had to become.

**The stop joined the listener on the GUI thread**, which is `T013-R2`'s rejected blocking teardown
restored under a different name — a two-second handler call held `shutdown()` for 2.001 s.
`QueueListener.stop()` is overridden to enqueue the sentinel and return; the thread closes the
queue and sweeps its own leftovers on the way out. Both globals are still dropped together, so the
"both, or neither" rule that this function was already carrying two scars from is untouched.
Waiting is now a separate, named thing (`wait_for_the_log_listener_to_stop`) that says in its own
docstring never to call it from the GUI thread; only test teardown does.

**Evidence.** Two deterministic tests reproduce the reviewer's probes — a gated handler parks the
listener inside `emit`, so "the record was still in flight when the session was released" and "the
handler was still blocked when `shutdown()` returned" are states the test holds open rather than
races it has to win. Four unit tests pin the drain itself. Six mutations, one per moving part, each
killed by the test named for it; the tree hashed identical before and after the battery.

| Check | Result |
|---|---|
| `ruff check` / `ruff format --check` | Passed |
| `mypy` and `mypy --platform win32` | Passed — 68 source files each |
| Focused logging, worker-logging and manager suite | **93 passed** |
| Canonical bare `pytest` | **1192 passed, 11 skipped, 1 deselected** — three consecutive runs, 52–53 s each |
| Mutation battery | **6 of 6 killed**, tree restored to the same hash |
| CI at `b0879d7`, all five jobs green | Ubuntu **1192 passed, 11 skipped, 1 deselected**; Windows **1181 passed, 20 skipped, 21 deselected**; Windows desktop **20 passed, 1202 deselected**; both frozen jobs succeeded |

**Superseded in part.** Both statements above still hold, and the re-review confirmed them —
ordinary marker draining is ordered, and `shutdown()` no longer joins. Two siblings survived at
the edges; see the third correction below. The evidence table here is the one for `b0879d7`.

Windows was not run locally — no Windows-specific code path is involved, but the listener thread
and the queue are platform behaviour, so those CI jobs are the whole of that evidence. The three
consecutive canonical runs were Linux only.

#### `T038-R2` — third correction, 2026-07-27, awaiting re-review

Two siblings at the edges of the second correction, both found by deterministic probe, both
still High: the drain got the ordinary path right and lost records at its two boundaries.

**Reopening a job's log left its file unattended.** `open_job_log()` closed a still-draining
handler so that two would never hold one file. But the caller attaches the replacement in a
*separate* step, and a stamped record dispatched in between belonged to a job whose file nothing
was holding open: written nowhere, with no later chance. The claim recorded above — "nothing is
lost, the new handler admits them into the very same file" — was true only of records dispatched
after the attach, and that qualifier is exactly what a review exists to catch.

The same open handler is now **handed back** rather than replaced, so there is no window and
still only one handler per file. It is handed back only when it writes to the file being asked
for: `open_job_log` takes a `directory`, so same job and same file are different conditions, and
taking one back on the job id alone would misroute the new session into the previous directory.
A pending drain onto a different file is left alone — no conflict, and it closes on its own
marker.

**`idle` was announced while the listener was still working.** `idle` means composition may quit
(`T-036`), the listener runs on a daemon thread, and a record it still holds when the process
exits is not written late but never — the per-job log ends mid-session. During shutdown `idle`
now waits for the listener thread as well as for the sessions, on the tick, never by joining.
Outside shutdown nothing changes: the listener stays up for the next session.

The wait is **bounded by `reap_seconds`**, because a log that can stop the application from
closing is worse than a truncated one. Giving up sets `gave_up_on_the_log` and writes **no log
line**, which is not an oversight: `Handler.handle` takes the handler's lock before calling
`emit`, so a warning on that path blocks on the lock the wedged listener is holding. The first
version did exactly that and a probe measured eleven event-loop turns in five seconds. The
general shape — any GUI-thread `logger` call blocks on a handler that will not return — is
application-wide and older than this task; what is specific here is that this path knows one is
stuck and does not add another.

`stop_listening_for_worker_logs()` now **returns the thread it asked to stop**, and the manager
holds it. Asking the module afterwards would have made a manager that never started a worker
wait on a listener another one was responsible for.

**Evidence.** Nine mutations, each killed by the test named for it, tree hashed identical before
and after. One survived the first battery — dropping the same-file check — and is the reason
`test_a_drain_onto_a_different_file_is_never_taken_back` exists; it was written to kill that
mutation rather than to describe a behaviour already believed.

| Check | Result |
|---|---|
| `ruff check` / `ruff format --check` | Passed |
| `mypy` and `mypy --platform win32` | Passed — 68 source files each |
| Focused logging, worker-logging and manager suite | **96 passed** at `098ba3f` |
| Canonical bare `pytest` | **1195 passed, 11 skipped, 1 deselected** — three consecutive runs, 82 s each |
| Mutation battery | **9 of 9 killed**, tree restored to the same hash |
| CI at `d6f3581`, all five jobs green | Ubuntu **1195 passed, 11 skipped, 1 deselected**; Windows **1184 passed, 20 skipped, 21 deselected**; Windows desktop **20 passed, 1205 deselected**; both frozen jobs succeeded |

*(The focused figure read **95** until 2026-07-27. The reviewer flagged it as a non-blocking
bookkeeping discrepancy against the three-file command this row names, and re-running that
command confirms **96**; `T-016` has since added seven tests to `test_manager.py`, so the same
command now reports 103. The count is corrected rather than the command narrowed.)*

The counts reconcile on both platforms — Ubuntu 1192 → 1195 and Windows 1181 → 1184, each the
three new tests — so all three ran on Windows rather than being skipped. That matters most for
the wedged-listener deadline, which is the one place platform thread timing could differ. Windows
was still not run locally, CI exercised these once, and the three consecutive canonical runs were
Linux only.

The 82 s runs are not a slowdown: the same suite measured **81.40 s** at `dd1dad8` in the same
session, on a machine busy with concurrent work. The 52 s recorded above was a quieter box, and
absolute timings between sessions are not comparable.

#### What landed

**`core/logging.py`, and the redaction is a `Formatter`.** Every handler this module installs
renders through `RedactingFormatter`, which rewrites the **finished string** — so `%`-style args,
a caller's f-string, an `extra` field the format names, and an exception traceback all converge
on one rewrite and there is no fourth route to forget. A test asserts every handler on the
application's logger tree has it, because a handler added without one would be a hole that the
other handlers' passing tests would hide.

**Every URL loses its query, userinfo and fragment** — not "token-like parameters". Deciding
which parameter names look like secrets is the recogniser problem that cost `T-018` four rounds,
and `X-Amz-Signature` was outside every list anyone had thought of. Nothing in a log needs a
query string, so the allowlist is empty and the question closes. Proxy credentials fall out of
the same rule; `DownloadRequest` cannot hold one anyway (`T-014`).

**Two limits, stated rather than discovered.** An **output path is not touched** — `T014-R6`
turned a user's output directory into a relative path while scrubbing prose, which was
independently Critical, and a log that cannot say where the file went has broken its own purpose.
A **bare `NAME=value` is not chased**: it is indistinguishable from `height=1080`, and cookie
*contents* are outside what `REQ-026` binds because this application never holds one — it passes
a browser name and yt-dlp reads the jar. Both have their own tests, so the boundary is asserted
rather than assumed.

**`remember_a_secret()` is the escape hatch that is not a guess.** When the application does hold
a sensitive literal, it registers that exact string. Bounded and exact; no pattern involved.

**Worker records travel unformatted.** The child installs a `QueueHandler` over a plain
`multiprocessing.Queue` — stdlib, Qt-free, which `ARCHITECTURE.md` §3 requires — and the parent's
handlers render them. So a worker cannot emit an unredacted line even in principle: it does not
do the formatting. **Its own queue, not the protocol's**, because a log record on the message
queue is indistinguishable from a worker sending something undeclared, which `SessionValidator`
exists to refuse (`T-011`).

#### Out of scope

- A log viewer in the UI — Phase 3
- Rotation and retention policy — Phase 4
- Crash reporting of any kind; there is none (`NFR-007`)

---

### T-055 — Decide how the application writes to SQLite without blocking the GUI thread

**Status:** **Complete** — decided and recorded 2026-07-27 as `ARC-005`.
**Owner:** Planner
**Priority:** High — blocked `T-016`'s `T016-R3`
**Phase:** Phase 1
**Depends on:** `T-014`
**Relevant context:** `NFR-001`; `ARCHITECTURE.md` §3 and §8; `DAT-001`; `T016-R3`
**Affected surfaces:** `ai/DECISIONS.md`, `ai/ARCHITECTURE.md`; implementation is `T-016`'s
**Risk:** Medium — deciding persistence threading inside a widget would set application-wide
policy from the narrowest possible place
**Blocks:** `T-016`

#### Scope

`T-016`'s review found the first widget to touch persistence doing it synchronously on the GUI
thread, and measured 0.302 s of blocked interaction plus an `OperationalError` that reached no
user. `NFR-001` is unqualified, so the widget was wrong — but *how* the application writes without
blocking was never decided, and `persistence/db.connect()` leaves `check_same_thread=True`, so a
repository built on the GUI thread cannot be used from another one at all.

The same shape as `T-051`: a review found a gap the narrow task could not close without inventing
architecture, so the Planner decides and the implementing task builds it. The maintainer chose
this route on 2026-07-27 over deciding it inside `T-016` or seeking an `NFR-001` carve-out.

#### The decision — `ARC-005`

**Queue writes happen on one dedicated writer thread that owns its own connection**, opened
inside that thread from an injected factory. A batch is one transaction, and the result is
reported back on the GUI thread so a failed write is surfaced rather than swallowed. Full
reasoning, the two rejected alternatives, and what reopens it are in `ai/DECISIONS.md`.

#### Acceptance criteria

- The architecture names which thread writes, and how a caller learns the outcome
- `check_same_thread` stays on, so a wrong-thread use raises rather than corrupting
- Any durable trade-off is recorded in `ai/DECISIONS.md`
- No source code is changed by this Planner task

#### Out of scope

- Making reads asynchronous. Indexed single-row lookups against a local file are not what
  blocked, and every widget would pay for it.
- Constructing and shutting down the writer, which is composition's (`T-036`).

---

### T-054 — File the approved Phase 1 tasks under `## Complete`

**Status:** **Complete — approved with follow-ups**, 2026-07-28 at `9c92c32`. Thirteen entries
moved, not three. `T054-R1` (Low, non-blocking) is corrected here: the permutation evidence now
names what it excluded, and the blank line at EOF is gone.
**Owner:** Planner
**Priority:** Low
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `AGENTS.md` §6 (`TASKS.md` is current truth), `ai/REVIEWS.md`
**Affected surfaces:** `ai/TASKS.md`
**Risk:** Low — no source or behavior changes

#### Scope

`T-013`, `T-015` and `T-018` were approved on 2026-07-27 and their **Status** lines say so, but
their entries still sit under `## In Review`. Move all three to `## Complete`, and check the
section each remaining entry sits in against its own status while doing it.

Filed rather than fixed inline because it is three long entries of pure relocation, and folding
it into `T-016`'s diff would have hidden a widget behind a thousand moved lines (`AGENTS.md` §7).

#### Acceptance criteria

- No entry sits in a section that contradicts its `Status:` line
- The note at the top of `## In Review` explaining the mismatch is removed with the mismatch
- No `Status:` line, finding disposition or evidence record is reworded by the move

#### Out of scope

- Archiving completed entries into `ai/archive/` — that is a separate judgement about when the
  live queue is buried

#### Evidence, 2026-07-28

**Thirteen entries moved, not the three this task was filed for.** The other ten were the same
defect the three were, and checking every entry against its own `Status:` line — which the
acceptance criteria ask for — is what turned them up:

| To | Entries | Was under |
|---|---|---|
| `## Complete` | `T-013`, `T-015`, `T-018` | `## In Review` — the three this task named |
| `## Complete` | `T-038`, `T-055`, `T-058` | `## Ready` |
| `## Complete` | `T-019`, `T-051` | `## Proposed — Phase 1` |
| `## In Review` | `T-017`, `T-056`, `T-057` | `## Ready` and `## Proposed — Phase 1` |
| `## Ready` | `T-040` | `## Blocked` — unblocked on 2026-07-27, never moved *(and Blocked again on 2026-07-28, on its own Windows evidence)* |

`T-054` itself moved to `## Complete` with them.

**Nothing was reworded — but the proof offered for it overclaimed** (`T054-R1`). The *relocation*
was a pure permutation, and that is what the 2327-against-2327 line-multiset comparison actually
measured: it was run against the working tree **before** this entry's own status change, evidence
block, and the removal of the `## In Review` note were written. Compared against `257b7c7`, the
committed diff necessarily also contains those three, so "differs by one separator" was true of a
snapshot and not of the commit. The acceptance criterion still holds — no other task's `Status:`
line, finding disposition, or evidence record differs — but a mechanical claim has to name what it
excluded, or it is doing the same work as "looks fine to me".

**The `## In Review` note is gone with the mismatch it described**, as the criteria require.

**One thing found and deliberately not fixed** (`AGENTS.md` §7 — file it, do not fix it inline):
`## Proposed — Phase 0` now holds a single entry, `T-021`, whose own **Phase** field says Phase 4;
`T-049` is Phase 4 and sits under `## Proposed — Phase 2`. The section headings group by proposal
phase and two entries disagree with theirs. That is a *heading* question rather than a status
contradiction, so it is outside this task's acceptance criteria and is left for the maintainer to
rule on rather than resolved by an implementer's preference.

---

### T-051 — Define the READY-to-download lifecycle

**Status:** **Complete** — decided and recorded 2026-07-27 as `ARC-004`. No source changed.
**Owner:** Planner
**Priority:** High — blocks `T-016`'s probe-then-queue flow
**Phase:** Phase 1
**Depends on:** `T-013`
**Relevant context:** `ARCHITECTURE.md` §5; `REQ-002`, `REQ-015`; `T-016`
**Affected surfaces:** `ai/ARCHITECTURE.md`, `ai/DECISIONS.md` if the choice is durable,
`ai/TASKS.md` (`T-013`/`T-016` correction or implementation scope)
**Risk:** Medium — inventing an edge in the manager would make the executable state machine
and the approved architecture disagree
**Review base:** the corrected `T-013` head
**Blocks:** `T-016`

#### Scope

Resolve the lifecycle gap exposed by the T-013 review ruling. `DownloadManager.start()` is
correct to refuse a `READY` job today because `ARCHITECTURE.md` §5 has no
`READY → PROBING` edge. But `T-016` must first probe a persisted job, leaving it `READY`, and
then queue that selection for download. It cannot honestly reuse that job through the current
manager API, while creating a second job would strand or duplicate the probed record.

Choose and document the intended transition and manager operation before T-016 implements the
widget flow. Plausible designs include starting a download from `READY` without re-probing, or
explicitly allowing a new probe cycle with a justified state edge; the Planner decides rather
than source code silently creating architecture.

#### Acceptance criteria

- The architecture names the legal state path from a successful probe to a download start
- `T-013`'s manager contract and `T-016`'s widget scope name the same operation and starting state
- The chosen design states whether metadata is reused or probed again, including what happens
  when it has become stale
- Any durable architecture trade-off is recorded in `ai/DECISIONS.md`; otherwise the current
  architecture and tasks are aligned without manufacturing a decision entry
- No source code is changed by this Planner task

#### The decision — `ARC-004`

**A download starts from `READY` as well as from `QUEUED`, and never re-enters `PROBING`.** The
two entry points use edges the state machine already has: `QUEUED → PROBING`, and `READY →
RUNNING`. `READY → PROBING` is not added, because a job that has been probed does not become
unprobed, and a download session's own extraction is part of downloading rather than a return to
an earlier state.

Answering this task's criteria one by one:

- **The legal path from a successful probe to a download start** is `PROBING → READY` (the probe
  session's outcome) then `READY → RUNNING` (the download session starting). Recorded in
  `ARCHITECTURE.md` §5 as a table of the two entry points, beside the diagram it reads from.
- **The one operation, named the same in both tasks**, is `DownloadManager.start(job_id,
  kind=SessionKind.DOWNLOAD)` — accepting a job in `QUEUED` **or** `READY`, and setting the
  status that says a worker holds it. `T-013`'s entry and `T-016`'s scope now both say that.
- **Metadata is not reused and not re-probed: it is re-extracted.** `YoutubeDL.download()`
  resolves the URL itself and cannot be handed a previous extraction, so the bytes are never
  fetched against stale data however old the probe is. What can be stale is only what was
  *displayed*, and a download session reports no `Probed` outcome, so the recorded title stands.
- **Staleness that matters surfaces as an ordinary failure** in the extractor's own words
  (`REQ-005`, `NFR-006`) — the chosen format no longer resolving is the observable case. There is
  no freshness timer, no re-probe prompt, and no expiry on `READY`; nothing would read them.
- **The durable trade-off is recorded** in `ai/DECISIONS.md` as `ARC-004`, including the two
  designs considered and what reopens the question (a probe expensive enough to be worth handing
  to the worker, which would be a protocol change).

**Nothing here is implemented by this task.** `T-016` owns the manager change and the docstring
in `DownloadManager.start()` that currently says the flow needs the state machine amended first.

---

### T-019 — Kill the process *tree*, and prove it on Windows

**Status:** **Complete — approved**, 2026-07-27 at `eaa5b50`. `T019-R1` is verified running in
CI, and `T019-R2`, `T019-R3`, `T019-R4` and `T019-R5` are all independently resolved. The
descendant-reaping defect is fixed and the `process_tree` marker is gone with the reason for it.
`T019-R2` is the one worth remembering: pushing bought a Windows defect nothing local could have
found, where `ctypes` had truncated the Job object's handle.
**Owner:** Implementer
**Priority:** **High** — carries a live defect, plus the only Windows evidence Phase 1's exit
criteria can ever have
**Phase:** Phase 1
**Depends on:** `T-013`
**Relevant context:** `ai/TESTING.md` §7 (Cancellation, Worker crash), `REQ-015`, `REQ-028`,
`NFR-003`, `OPS-003`, `OPS-004`
**Affected surfaces:** `downloader/manager.py` (**production**, see below),
`downloader/worker.py`, `tests/integration/`, `.github/workflows/ci.yml`
**Risk:** **High** — a download that keeps running and keeps writing after the user cancelled
it, on a path no current test can see
**Review base:** the `T-013` merge commit

**It also restores the default test run.** `tests/integration/test_manager.py` is behind
`-m process_tree` as of 2026-07-27, because the loose descendants wedge later runs intermittently
— the same suite finishing in 19 seconds twice and then sitting past ten minutes. Two of
`ai/TESTING.md` §7's mandatory areas are out of the default loop until this lands. The marker is
removed by this task, not by a separate cleanup.

#### `T019-R1` — Medium, corrected 2026-07-27, awaiting re-review

**The marker took those 43 tests out of CI as well, while three records said otherwise.**
`addopts` in `pyproject.toml` is global, both check jobs ran bare `pytest`, and no step opted the
marker back in — so Cancellation and Worker crash, two mandatory areas, ran nowhere: not locally,
not on Linux CI, not on Windows CI. `ai/TESTING.md`, the module comment, the implementer record
and the commit message all claimed CI still covered them.

`.github/workflows/ci.yml` now has a **Process-tree suite** step in the `check` job, after the
main test step, on both platforms. It follows the `windows_desktop` pattern: `-m process_tree` is
load-bearing because pytest exits 5 on an empty collection, so a marker typo fails the job rather
than passing it vacuously (`T031-R2`). It carries `timeout-minutes: 10`, because the defect under
test is one that hangs — a wedged job should fail in ten minutes rather than sit for six hours —
and its own junit XML and log in the evidence artifact.

A fresh runner is the right place for these: it is discarded after the job, so an orphan cannot
wedge a later run the way it does locally. Verified locally at `pytest -m process_tree`:
**43 passed, 2 skipped**. The CI step itself cannot be verified from here (`OPS-003`).

Every claim that CI ran them was corrected rather than deleted, in `ai/TESTING.md` §2 and §7 and
in the module comment, each naming the step that now makes it true.

#### What landed

**`downloader/process_tree.py`, and the containment happens in the child.** The parent cannot
reliably enumerate a tree it is racing — between listing the descendants and signalling them the
worker can spawn another, and the one just listed can exit and have its pid reused. Both
platforms offer the same answer instead: make the descendants a set the kernel tracks, once,
before any of them exist. POSIX `os.setsid()` so the worker leads its own process group; a
Windows Job object with `KILL_ON_JOB_CLOSE` so the kernel reaps the members when the worker's
last handle closes. `CREATE_NEW_PROCESS_GROUP` is the common substitute and is not this: it
affects Ctrl-C delivery, not descendant lifetime.

The two halves are **split at module level under `sys.platform`**, so each is type-checked by
the run that owns it — `mypy src` checks the POSIX branch, `mypy --platform win32 src` the
Windows one. The first draft used `hasattr()` guards, which read as portable and check neither.

**The rule that keeps this from killing the application.** `killpg` takes a group, and the wrong
group id here is the parent's own. From the parent, a worker whose group equals ours means
containment failed, and signalling it would take down the GUI — so `_group_of` reports "no group"
and the caller falls back to the single process. From *inside* the worker the same test means the
opposite, which cost a debugging round: the watchdog called `kill_tree(os.getpid())`, the guard
saw the caller's own group, refused, and the grandchild survived. `kill_this_group()` is the
separate function for the caller that means its own group, and it checks that it *leads* that
group first.

**Three paths, all covered.** Cancellation signals the group at both escalation deadlines; a
worker that dies on its own — crash, external kill, ordinary exit — has its group reaped when the
session is released, **before the process is joined**, because the group id is the dead worker's
pid and a pid is reusable the moment the zombie is collected; and the parent-death watchdog kills
the group rather than merely exiting.

**`worker_processes()` was the reason nobody saw this.** It filtered to `spawn_main` in the
command line, so an `ffmpeg` grandchild was invisible to every orphan assertion in the file — the
tests passed while the exact process that survived cancellation was excluded from the question by
construction. It now reports every descendant and excludes only `multiprocessing`'s resource
tracker, which is the exclusion that was always right. Two tests hold it there: one leaks a real
child and a real grandchild and asserts both are seen, the other asserts the tracker still is not.

**`prepare_this_worker()` exists because the `entry_point` seam replaces `spawn_session`
entirely.** A stand-in worker in a test that did not repeat the containment and the watchdog was
subtly unlike every real one — and was: the first parent-kill test watched a stand-in and its
child both survive the application. One function, called by production and by the stand-ins.

**`T019-R1`'s CI step is removed along with the marker**, because the marker is gone: the 43
tests are back in the default run on both platforms, so a separate step would run them twice.

**Mutation-checked.** See the correction record in `ai/REVIEWS.md` for the battery. One result is
worth naming here: removing the escalation's group signalling **survived** the first battery,
because the release-path reaping killed the descendant a moment later anyway. The guard had no
evidence of its own. `test_a_descendant_is_asked_to_stop_before_it_is_killed` now distinguishes
them — a grandchild that handles `SIGTERM` writes a marker when it is *asked* to stop, which is
the difference `REQ-015` actually cares about: `ffmpeg` asked can close its output, `ffmpeg`
killed cannot.

#### `T019-R3`, `T019-R4`, `T019-R5` — corrected 2026-07-27, awaiting re-review

**`T019-R5` — the canonical gate, and the root cause was `QThread.terminate()`.** Reproduced on
the first try: bare `pytest` exit 124 after 46 manager tests. A `SIGABRT` stack dump at the stall
showed the main thread parked on an internal CPython mutex inside `Thread.start()`, and two
threads carrying **no Python frame at all** — a thread killed mid-operation, holding a lock
nothing would release. Two hypotheses were tested and one discarded: the `T-038` log listener was
visibly alive in the dump and turned out to be innocent, since the wedge reproduces with the log
queue removed. Disabling `terminate()` gave **22 consecutive clean runs** against a ~20 % baseline.

`ResultPump` now polls with a `POLL_SECONDS` timeout and returns when asked; `stop()` replaces
both `terminate()` call sites. **There is no `QThread.terminate()` left in the project.** The
module docstring that argued *against* a timed `get()` is corrected rather than deleted: the
timeout is not a second definition of "the stream ended" — the sentinel is still the only thing
that means that — it is the only way a *stopped* thread can notice it was stopped.
`test_a_stopped_pump_actually_stops_rather_than_being_killed` asserts the distinction the review
asked for: not that a stop was requested, but that the thread reports itself finished *and*
emitted `session_ended`, which only a thread that reached its `finally` can do. Verified 13×
across the minimal reproduction and the full bare command.

**`T019-R3` — an uncontained worker refuses to run.** Logging that the guarantee is missing is
not the guarantee. `spawn_session()` now reports a legal failed session — one outcome, then the
sentinel — and exits with `UNCONTAINED_EXIT_CODE` before anything can spawn a descendant. The
message carries the reason, because a refusal nobody can diagnose is its own defect.

**`T019-R4` — the evidence now proves what it claimed.** The detector self-test spawns a **real**
two-level tree and asserts `ppid()` before anything else; its old assertion ended in `or True`
and could not fail. Cancellation asserts the completed output is *absent* as well as the partial
present. Elapsed cancel times go to `record_property`, so they land in the junit XML CI already
uploads and can be seen trending. Stray-descendant cleanup moved into an autouse fixture keyed to
a unique marker, so it runs when an assertion **fails** — which is exactly when a mutation leaks
the deliberately stubborn process, and how 111 of them accumulated.

**A second `or True` was found and removed while fixing the first** — the startup-diagnostic
assertion `T013-R5` filed as `T-052`. Removing it showed the production behaviour was right and
the *assertion* was wrong: it looked for the parametrised component name, which the message never
claimed to carry. It now asserts what `T-052` actually asks for — that the original `OSError`'s
own words survive the unwind rather than being replaced by whatever the cleanup hit. That part of
`T-052` is therefore discharged here; the rest of its scope is untouched.

**Mutation-checked: 14 of 14 killed** across both tasks' corrections.

#### `T019-R2` — the first Windows run, and what it found

**The Job object contained nothing, silently.** Pushed at `989ef46`; CI run `30302798113`
reported the four grandchild tests failing on `windows-latest` and every other job green.

The cause was `ctypes` with no declared `restype`: it assumes `c_int`, so `CreateJobObjectW`'s
64-bit `HANDLE` came back truncated to 32 bits, every later call against it failed,
`contain_this_process()` returned `False`, and nothing was contained. Every signature is now
declared. **Invisible on Linux by construction** — the POSIX half of the module has no handles.

Two things made a one-line bug cost a full CI round, and both are fixed:

- **`contain_this_process()` fails quietly, by design**, because a worker that cannot be
  contained should still run its download. That is right, but the reason was going nowhere:
  `containment_error` now records it and `prepare_this_worker()` logs it once the handler exists.
- **The one test that would have caught it in one line was skipped on Windows.** The module-level
  `skipif` in `tests/unit/test_process_tree.py` covered the *group* tests, which are genuinely
  POSIX — and swept up the containment test with them, so a broken Job object surfaced as four
  confusing integration failures instead. The skip is per-test now, and
  `test_containment_succeeds_on_this_platform` runs on both.

**Verified on the re-run.** CI `30303348265` is green on every job. On `windows-latest`:
`test_containment_succeeds_on_this_platform`, `test_cancelling_a_download_kills_what_the_worker_spawned`,
`test_a_worker_killed_from_outside_does_not_leave_its_grandchild_behind`,
`test_shutdown_leaves_no_descendant_either` and `test_killing_the_parent_takes_the_grandchild_too`
all pass — **1163 passed, 20 skipped** in 64 s. That is the Windows half of this task's whole
premise, and it is the first time a Job object has reaped anything in this project.

**A second finding from the same run, in the checks rather than the code.** CI runs bare
`mypy --platform win32`, which covers `tests/` through `pyproject.toml`'s `files`; locally the
task had been running `mypy --platform win32 src`. Two `os.getpgid` calls in a POSIX-only test
therefore failed a check that had passed everywhere it was run. The test now asks through
`process_tree.group_of`, which is the function the manager uses and is typed on both platforms —
and the local command matches CI's.

#### Why this was rescoped

`T-013` delivered most of what this task was written to prove, and delivered it against
stronger evidence than the task asked for. What it did **not** deliver is now the whole point,
and it is not a test gap — it is a defect.

**What `T-013` already covers, with pointers so the reduction can be checked rather than
trusted** (all in `tests/integration/test_manager.py`):

| This task originally asked for | Where it now lives |
|---|---|
| A fake doing observable work before the cancel | Not a fake at all: `test_cancel_stops_a_real_in_flight_download_within_the_budget` runs **real yt-dlp** against a local `http.server`, cancels only after real progress messages, and asserts the real `.part` file |
| Cancellation within 2 s of genuinely in-flight work | Same test, measured from the `cancel()` call to the last worker process disappearing |
| A worker that ignores cancellation | `test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget` — ignores the event *and* `SIGTERM` |
| `SIGKILL` → `WORKER_CRASH`, app survives | `test_a_killed_worker_becomes_worker_crash_with_its_exit_code`, and `test_the_application_survives_a_worker_crash_and_can_start_another`, which proves survival by *using* the manager afterwards rather than by watching a timer |
| Exit 0 with no outcome → `WORKER_CRASH` | `test_a_worker_that_exits_zero_without_an_outcome_is_a_crash_not_a_success` |
| One terminal outcome per job | `test_a_second_outcome_produces_no_second_transition_and_no_second_signal` |
| Persisted state matches what the UI was told | `test_a_real_download_completes_and_every_transition_is_persisted_first`, asserted at the moment of each signal |
| No orphan outlives the session | `test_shutdown_leaves_no_worker_no_thread_and_no_job_in_flight`, plus the parent-kill test |

Reasserting those here would duplicate them, and a duplicate is worse than nothing: it is a
second place to update and a second place to quietly weaken.

#### Scope

**1. Cancellation must reap the whole process tree — this is a production change.**

`DownloadManager` cancels by signalling, terminating and killing **the worker process**. yt-dlp
spawns `ffmpeg` as a child *of the worker*, and on POSIX killing a parent does not touch its
children. Probed on 2026-07-27 against a spawned worker with one real grandchild: after
`Process.kill()` the grandchild was **still running**, reparented to `init`. `REQ-015` says
cancel must terminate the underlying work and `ai/TESTING.md` §7 says it must leave no orphan
process; a merge cancelled mid-flight currently leaves ffmpeg writing to the user's disk with
nothing left that can stop it.

Fix it where the platforms differ, and say so in the code: a POSIX process **group** (the child
calls `setsid`/`os.setpgrp` at start-up so its descendants share a group that can be signalled
as one) and a Windows **Job object** (`CREATE_NEW_PROCESS_GROUP` alone does not kill
descendants). Both belong to `spawn_session`'s "I am a child" half and the manager's escalation.

**2. The test helper that hides this must be fixed, not worked around.**
`worker_processes()` in `test_manager.py` filters to processes whose command line contains
`spawn_main`, so an `ffmpeg` grandchild is invisible to every existing orphan assertion. It was
written that way to exclude `multiprocessing`'s resource tracker, and the exclusion is right —
but the filter must exclude *that*, not everything that is not a worker.

**3. The orphan detector is permanently self-tested.** A test leaks a real child **and** a real
grandchild, asserts the detector finds both, then reaps them. A detector nobody re-exercises
looks exactly like one that works — the Phase 0 evidence problem, again.

**4. Both platforms, and no skips.** `SIGKILL` and `TerminateProcess` are each exercised on
their own platform, and a skip on either fails the job. `OPS-003` makes CI the only Windows
evidence that exists, and Phase 1 cannot exit without it.

#### Acceptance criteria

- A cancelled download leaves **no surviving descendant**, asserted over the full process tree
  with a deliberately spawned grandchild standing in for `ffmpeg`. Killing the worker while the
  grandchild lives must fail the test
- The same holds for a **killed** worker and for **application exit**: no descendant outlives
  any of the three paths
- `worker_processes()` (or its replacement) is shown to **see** a grandchild — a test leaks one
  and asserts the detector reports it, so the filter cannot be narrowed back into blindness
- Cancellation still completes within 2 seconds with the tree cleanup in place (`REQ-015`)
- A cancelled download leaves **no completed-file rename**: the partial file stays partial, so
  a cancel can never be mistaken for a finished download
- Every cancellation and worker-crash test runs in CI on **Linux and Windows**, unskipped, and
  a skip on either platform fails that job
- Timings are recorded, not merely asserted, so the 2-second budget can be seen trending
- The process-group and Job-object handling is mutation-checked on the platform that owns it

#### Out of scope

- Re-testing what `T-013` already proves — see the table above
- Queue-level behaviour with multiple workers — Phase 2
- Network-dependent tests. The local-server pattern `T-013` introduced (`ai/TESTING.md` §6)
  is available and is not a network test

---

### T-014 — Persistence: schema, migrations, and the job repository

**Status:** **Complete — approved with follow-ups**, 2026-07-26 at `db14cc2`. Four review
rounds; `T014-R1` (Critical), `R2`, `R3`, `R4`, `R5` and `R7` all resolved, `R6` retracted by the
reviewer. Follow-ups: `T-048` (verify the first real data migration) and `T-049` (tighten
`DAT-003`'s explanatory guarantees before cookie-file support).

Closes three of `ai/TESTING.md` §7's mandatory areas — crash recovery, migrations, and the
settings freeze — taking the covered set from three to six. **Unblocks `T-013`**, and with it the rest of the
Phase 1 chain.

**`T014-R1` was the most expensive finding this project has had**, and the lesson is worth more
than the code. Four rounds, three credential escapes, one Critical regression I introduced while
fixing it, and a missing decision record at the end. **All three of my code fixes were in the
wrong layer** — a filter over unbounded input, where the answer was to constrain what the input
could be. The correction that worked changed `core/models.py`, not `persistence/`, and made a
proxy credential *unrepresentable* rather than removable.

The same shape defeated `T-044` (six rounds) and `T-045`. Whoever takes `T-038` should read this
first: log redaction is this problem again, and the instinct to write a recogniser will be wrong
there too.

**Owner:** Implementer
**Priority:** High
**Phase:** Phase 1
**Depends on:** `T-010`
**Relevant context:** `ARCHITECTURE.md` §5 (core entities); `DAT-001`, `REQ-012`, `REQ-018`,
`NFR-003`, `NFR-004`; `ai/TESTING.md` §7 (Crash recovery, Migrations)
**Affected surfaces:** `persistence/schema.sql`, `persistence/migrations/`,
`persistence/db.py`, `persistence/repositories.py`, `tests/unit/`, `tests/integration/`
**Risk:** **High** — the one component whose failure mode is *lost user data*, and the only
one where a bug can persist across restarts
**Review base:** the `T-010` merge commit

#### Scope

SQLite in WAL mode at `user_data_dir/tracksandtrails/library.sqlite3` (`DAT-001`,
`ARCHITECTURE.md` §5). The schema for `Job` and `HistoryEntry` as §5 defines them, a forward-only
migration runner, and `JobRepository`.

Two properties are the entire point:

- **The queue survives an unclean kill** (`REQ-012`, `NFR-003`). WAL is chosen for exactly
  this; the test must actually kill the process, not close the connection politely.
- **Startup recovers jobs stranded in `RUNNING`.** A job cannot be running if the application
  just started, so it is recovered to a retryable state rather than left lying about its own
  status (`ai/TESTING.md` §7).

`DownloadRequest` is persisted *with* the job, so a retry after a settings change reproduces
the original request rather than current defaults (`ARCHITECTURE.md` §5, §8).

#### Acceptance criteria

- A hard kill (`SIGKILL`) mid-write leaves the database readable with no partial row, verified
  by killing a real process rather than simulating it
- Jobs found **in flight** at startup are recovered to a retryable state, and the recovery is
  recorded so it is visible rather than silent.

  **Widened 2026-07-26 to match the architecture.** This said `RUNNING` alone, as does
  `ai/TESTING.md` §7, while `ARCHITECTURE.md` §5 names `PROBING`, `RUNNING` *and*
  `POST_PROCESSING`. The architecture outranks both (`AGENTS.md` §5), and recovering only
  `RUNNING` would strand a job in `PROBING` with no path out. The three statuses are transcribed
  into a test, so narrowing the set fails rather than passing
- **Every migration runs forward from every prior schema version with data intact**, asserted
  by building a database at each historical version and migrating it — not just from the
  latest (`ai/TESTING.md` §7). With one version today, the harness must still exist, because
  it is unwritable later once several versions exist
- A schema change without a migration fails the suite
- A persisted `DownloadRequest` round-trips exactly; a retry uses the stored request, proven
  by changing the defaults between store and retry (`ARCHITECTURE.md` §8)
- Queue order survives a restart (`REQ-012`)
- No **application-supplied** cookie path, cookie content, or proxy credential is ever written to the database (`DAT-003`)
  (`REQ-026`, `NFR-007`) — asserted by scanning the stored row, not the model, since a
  redaction applied in the model but not on the way to disk would pass an object comparison and
  still leave the secret on disk.

  **Narrowed 2026-07-26 by maintainer decision.** This criterion originally also forbade a
  "token-like query parameter", which cannot hold alongside the round-trip criterion above: the
  job URL *is* the request, `REQ-012`'s queue and `REQ-020`'s history are unusable without it,
  and a retry cannot reconstruct it. Stripping token-like parameters would also need a
  heuristic for "token-like" — an enumerate-and-claim-complete gate of exactly the kind that
  cost `T-044` six review rounds. The URL is stored verbatim; what is excluded is everything the
  user did not type into it. `cookies_from_browser` carries a browser name such as `"firefox"`,
  not a cookie, and is kept because dropping it would silently stop using cookies the user asked
  for. Log redaction is a different sink and remains `T-038`'s
- The database lives under `platformdirs`, never beside the installed application (`NFR-004`)

#### Out of scope

- History pruning, search, and export — Phase 3
- Concurrency beyond a single writer — Phase 2 brings the second
- Settings storage, which is TOML and not this store (`DAT-001`)

---

### T-044 — Close the non-blocking T-035 review follow-ups

**Status:** **Complete — Approved with follow-ups**, 2026-07-26. The maintainer directed T-044
forward after the claims-only re-review: its deliberately narrow runtime promise is accepted,
the three pinned blind spots are owned by `T-047`, and no further T-044 review loop is
authorized. **No production code changed at any point across six rounds.**

**`T044-R1` was found six times, and it was two defects wearing one number.**

*Rounds 0–4, the gate missing a binding shape.* Each fix enumerated one layer further out and
was defeated by the next:

| Round | Missed | Because |
|---|---|---|
| 0 | a public function | denylist of forbidden *names* |
| 1 | a public constant | runtime allowlist keyed on `value.__module__`, which constants lack |
| 2 | conditional definition, destructuring | parsed `tree.body` only, simple `Name` targets only |
| 3 | `match` captures | walked statements, never pattern bindings |
| 4 | walrus in a default argument | stopped at the whole `def`, not at its body |

Round 5 retired that class by not parsing for bindings at all: `defined_public_names` reads
`vars(module)` minus the names the parse shows were imported, so the interpreter's own namespace
decides. All eight historical shapes are caught, including the three from round 4 for which no
code was written.

*Rounds 3–6, the docstring claiming more than the gate delivered.* This is the defect that
actually persisted. Three separate claims — a "supported binding model", `T045-R3`'s "exact"
collider set, and "the Windows job covers non-executed exports" — were each asserted without
being established, and each disproved. The last was wrong in an instructive way: the
`[ubuntu-latest, windows-latest]` matrix covers only guards true on Windows and false on Linux.
Guards on architecture, dependency presence, feature probes or environment state are false on
**both** runners, and the probe asserting the claim used a `nonesuch` platform that is false on
both — so it never demonstrated what it was cited for.

**This pass therefore changes claims, not code**, on the reviewer's own recommendation.
`defined_public_names` now states one guarantee — under the configuration the suite runs in, a
public attribute not bound by an `import` statement is reported — and pins three gaps by test
rather than by memory: a guard false at run time, a name imported then rebound by a fallback,
and dynamic rebinding. `ai/TESTING.md` records the same, including the retracted CI claim.
`T-047` carries the decision on whether any gap is worth closing; its likely answer is no.

**`T044-R1` — the gate did not gate what it claimed.** `defined_public_names()` walked
`tree.body` directly and read only simple-`Name` assignment targets, so a public export written
as `if os.name: YTDLP_VERSION = ...` or `YTDLP_VERSION, YTDLP_USABLE = ...` was invisible to it
while being an ordinary module attribute at runtime. Codex demonstrated both survivors.

**Mutation evidence** (round 5's design, unchanged by round 6). All eight survivors from every
round fail the ownership test when planted in the real module — including round four's
walrus-in-a-default, walrus-in-a-decorator and class-base-expression cases, for which *no code
was written*: the interpreter bound them, so the runtime namespace has them. A private name
stays correctly allowed. Dropping the import subtraction fails 5 tests; making the gate return
an empty set fails 17; renaming a reviewed export private fails the reverse check.

**Defect-class audit (`AGENTS.md` §9).** `T044-R1` is a shallow-traversal defect, so every other
AST gate in the repository was checked for it. There is exactly one — the layering analyser in
`tests/unit/test_layering.py` — and it is **not** affected: it uses `ast.walk`, which recurses
into every node, and it already carries a synthetic-violation case for an import nested inside a
function body. No other module parses source.

**`T035-R3`, second round.** The previous fix caught a new *function* but filtered runtime
attributes by `value.__module__` to exclude imports — and a constant has no `__module__`, so
`YTDLP_VERSION = "unreviewed"` was filtered out with them and all 22 tests stayed green. A
denylist of names missed a function; a runtime allowlist missed a constant. That round changed
the check to parse the module's top level; the later `T044-R1` rounds above replaced binding
parsing with the deliberately narrow runtime gate.

Mutation-verified across every shape: a public constant, function, class and annotated constant
each fail 1 test; a private name is correctly allowed; renaming a reviewed export away fails.

**`P1-R1`, second round.** `TASKS.md`'s start-here still pointed at completed `T-041`/`T-034`,
and `STATUS.md` implied `T-038` was the only Ready task. Both now name the canonical set.
**Owner:** Implementer
**Priority:** Low — current production behavior is correct; this closes a future-regression
gap and repairs current-truth navigation
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `T035-R3`, `T035-R4`, `P1-R1`; `AGENTS.md` §9;
`ARCHITECTURE.md` §6
**Affected surfaces:** `tests/unit/test_environment.py`, `ai/TESTING.md`, `ai/TASKS.md`,
`ai/STATUS.md`. **No production code changed at any point across six rounds**
**Risk:** Low
**Review base:** `6c0a773` — the sole parent of head `d01a782` (`T044-R3`). The entry previously
recorded `fb2dab9`, which is seven commits back and would have swept unrelated approved work
into the diff.
**Correction head:** uncommitted; see `ai/REVIEWS.md` for the `T044-R1` correction batch.

#### Scope

Two non-blocking findings were carried rather than keeping `T-035` in review:

1. The replacement for `T035-R3` catches a new module-defined function such as
   `get_ytdlp_version()`, but its purported reviewed-API allowlist filters candidates by
   `value.__module__`. Constants have no `__module__`, so adding
   `YTDLP_VERSION = "unreviewed"` leaves all 22 environment tests green. Make the public API
   explicit and test it independently, including constants.
2. `P1-R1` is only partly corrected. `T-042`/`T-043` moved to Complete, but `TASKS.md` still
   starts implementers at completed `T-041`, and `STATUS.md` says `T-038` is the only Ready
   task while `T-014` and `T-015` are both canonically Ready.

#### Acceptance criteria

- Under the interpreter, platform, and configuration the suite actually runs, adding a public
  function **or constant** not bound by an import statement and not in the independently
  transcribed reviewed API fails the environment test
- The three known gaps are asserted explicitly and owned by `T-047`: a guard false at run time,
  an imported name rebound by a fallback, and dynamic rebinding of an imported name
- The test does not ask production's own list what the expected public API is; if `__all__` is
  introduced, compare it with an independent expectation
- `TASKS.md` and `STATUS.md` agree on which tasks are Ready, In Review, and Complete, and the
  start-here text names current work
- No environment-resolution behavior change

#### Out of scope

- The two blocking T-034 findings from the final focused pass; the maintainer must choose
  another authorized pass, accepted risk, scope change, or carry-forward work for those
- Logging behavior (`T-038`) or any worker implementation (`T-012`)

---

### T-045 — Defused reserved names can collide with a legal neighbour

**Status:** **Complete — approved with follow-ups**, 2026-07-26. `T045-R1`, `T045-R2` and
`T045-R3` all resolved and independently verified; none blocks. Four rounds, one accepted
decision (`DAT-002`), and **no production change at any point** — the digest implementation
merged as `c0f4881` stands untouched. The follow-up is `T-046`, which owns filesystem-aware
uniqueness and whose before-first-release assumption is recorded in both `DAT-002` and the task.

**`T045-R3` — the correction overclaimed.** Having established that the *original* criterion was
unsatisfiable, the fix then asserted an "exact" colliding set that is also untrue. The test
checked six hand-picked candidates and called the result exhaustive, while `defused + " "`,
`defused + "."`, `"CON\t"` and `"C\x00ON"` all collide too — it passed because nothing outside
its own list was ever asked. That is the shape `ai/STATUS.md` records as this project's
recurring test defect: asserting over a curated list and claiming completeness.

Corrected in three places — the test now asserts the fixed point, the plausible-neighbour
distinction, and that the class is demonstrably *wider* than the reserved name alone, with no
enumeration claim; `DAT-002` is amended to say the set is not enumerable and why (normalization
is many-to-one by design); and this entry's criterion below matches. `DAT-002`'s incidental
claim that non-idempotence implies nondeterminism was also wrong and is corrected — the
load-bearing reason is that applying a non-idempotent sanitizer twice changes the path.

**`T045-R1` — the original criterion was unsatisfiable, not unmet.** Codex established that
"defusing cannot produce a path a legal filename also produces" contradicts idempotence, which
this module also promises. For any reserved `x`, let `y = sanitize_component(x)`. `y` is itself
legal input, and idempotence requires `sanitize_component(y) == y`, so `x` and `y` necessarily
map to one path. The digest changes *which* legal name collides — from the plausible `COM1_` to
the 16-hex-digit `CON-1bc43d851d28ada0` — but no stateless idempotent sanitizer can eliminate
the collision entirely.

The maintainer resolved this on 2026-07-26 in favour of keeping idempotence and narrowing the
promise (`DAT-002`). Absolute uniqueness needs to know what is already on disk, which this
function deliberately does not; that guarantee moves to `T-046`, and this task's own out-of-scope
list already deferred it.

Reserved names are now defused with the same digest the truncation differentiator uses, rather
than a bare `_`. `COM1` becomes `COM1-<16 hex>`; a legal file named `COM1_` is untouched, so the
two no longer land on one path.

The digest is taken over the *stem*, so it is stable across calls and processes — a path that
changed between the `REQ-011` preview and the write would make the preview a lie. Idempotent,
because `COM1-<hex>` is not itself reserved and a second pass leaves it alone. Extensions
survive: `CON.mp4` becomes `CON-<hex>.mp4`.

**Mutation-verified:** reverting to the bare `_` suffix fails 5 tests. The pinning test that
recorded the old behavior is replaced by one asserting the names differ, parametrized across
five reserved forms including a superscript.
**Owner:** Implementer
**Priority:** Low — needs a directory containing both names; no data loss, one file would
overwrite or be rejected by the caller
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `T034-R2`, `T034-R4`, `ARCHITECTURE.md` §8
**Affected surfaces:** `src/tracks_and_trails/core/paths.py`, `tests/unit/test_paths.py`
**Risk:** Low
**Review base:** `1c80964` — the sole parent of head `c0f4881` (`T045-R2`). The entry recorded
none, which in this non-contiguous history invites a diff carrying unrelated approved work.

#### Scope

`sanitize_component` defuses a Windows reserved name by appending `_`, so `COM1` becomes
`COM1_` — which is exactly what a file legitimately named `COM1_` also produces. Both land on
one path.

Same class as the `COM0` defect corrected in `T034-R4`'s second round, but narrower and not the
same mistake: `COM0` was never reserved and should never have been touched, whereas `COM1` is
genuinely reserved and *must* be renamed. The collision is a consequence of the renaming
strategy, not of renaming something that did not need it.

Found while writing the `COM0` regression test, and deliberately **not** fixed there: the
maintainer authorized a single exception pass limited to two named corrections, and this is a
third. Pinned by `test_defusing_a_genuinely_reserved_name_still_collides_see_t_045` so the
current behavior cannot change unnoticed.

#### Acceptance criteria

**Narrowed 2026-07-26 per `T045-R1` and `DAT-002`.** The original first criterion — "cannot
produce a path that a legal filename also produces" — is unreachable while `sanitize_component`
stays idempotent, and idempotence is the stronger promise because `T-012` previews a path under
`REQ-011` before writing it. What replaces it is a guarantee this function can actually keep:

- Defusing a reserved name does not collide with **the plausible neighbour class** — the name
  the user would realistically also hold. `COM1` and a legal `COM1_` no longer land on one path
- The residual collision is **named rather than denied**: `sanitize_component(y) == y` where
  `y = sanitize_component("CON")`, so the 16-hex-digit form `CON-1bc43d851d28ada0` is a fixed
  point. A test asserts that identity, and asserts that the colliding class is wider than the
  reserved name alone, so nobody reads the fixed point as an enumeration (`T045-R3`). The
  colliding set is **not** claimed to be enumerable: normalization is many-to-one by design, and
  control-character stripping and trailing dot/space removal each widen the class
- Idempotence survives: sanitizing an already-defused name returns it unchanged
- The pinning test above is replaced by one asserting the names differ
- A mutation reverting to the bare `_` suffix fails the suite

#### Out of scope

- Any change to which names are treated as reserved — `T034-R4` settled that against
  Microsoft's list, in both directions
- Collision policy when the target file already exists — now owned by `T-046` (Phase 2,
  alongside resume). That is where a real uniqueness guarantee belongs, because it is the only
  layer that knows what is already on disk (`DAT-002`)

---

### T-012 — yt-dlp in a spawned worker

**Status:** **Complete** — Approved with follow-ups, 2026-07-26. Two review rounds; all five
blocking findings (`T012-R1`..`T012-R5`) independently verified resolved. `T012-R6` is a
non-blocking follow-up owned by `T-018`.
**What landed.** `downloader/ytdlp_adapter.py` (pure translation: exception classification,
`info_dict` projection, option building) and `downloader/worker.py` (spawn-safe entry, `OPS-002`
resolution, one outcome message then `WorkerFinished` in a `finally`). No raw `info_dict`
crosses the process boundary; `tests/unit/test_layering.py` still passes, so §6 holds.

**Two defects found by the project's own tests rather than by review:**

- The worker reported a yt-dlp *source* it had not used. `import yt_dlp` returns whatever is
  already in `sys.modules` and ignores `sys.path`, so the resolution result was the candidate
  we hoped for rather than the one loaded — making `OPS-002`'s guarantee unfalsifiable. The
  source is now derived from the imported module's `__file__`.
- The first fix for that purged `yt_dlp` from `sys.modules`, which was **worse**: re-importing
  builds *new* exception classes, so `ytdlp_adapter`'s `isinstance` checks against the classes
  it had already bound would all miss and every failure would classify as `EXTRACTOR_ERROR` — a
  silent, total loss of the taxonomy. A classification test caught it. Both the reasoning and
  the rejected approach are recorded in `_origin_of`'s docstring.

**A third defect, found while auditing acceptance criteria for the review handoff.**
`preview_path` (`REQ-011`) had **no test at all** — the criterion "the preview equals the path
actually used" was unmet. The test now takes the preview, runs a real download session, and
reads the path out of the `Succeeded` message, so the two are observed through different
routes rather than by calling the same helper. Its first version was **vacuous on Linux**: the
chosen title used `: " ?`, which yt-dlp's own `prepare_filename` already maps to fullwidth
forms, leaving `T-034` nothing to change — a preview that skipped sanitisation entirely still
matched. A reserved device name (`CON`) diverges on every platform, because yt-dlp does not
handle those and `T-045` defuses them with a digest.

**Correction batch (2026-07-26).** Five blocking findings, all reproduced before being
fixed: successful sessions never told the parent which yt-dlp ran (`T012-R1`); a partially
imported broken override poisoned the baseline fallback (`T012-R2`); yt-dlp's whole transport
hierarchy classified as `EXTRACTOR_ERROR`, silently disabling auto-retry (`T012-R3`); the
rendered template lost its directories and was then re-rendered as a second template, so
containment was checked against a path that was never written (`T012-R4`); and proxy, cookies,
rate limit, ffmpeg location, audio extraction, subtitle embedding and `post_processors` never
reached the library call (`T012-R5`). 18 mutations, 18 killed.

**Evidence.** 42 adapter tests, 17 worker integration tests including a real
`mp.get_context("spawn")` child. The `ai/TESTING.md` §7 taxonomy is transcribed by hand rather
than read from the code under test (§13). Fixture `archive_org_big_buck_bunny.json` is a real
capture with `cookies`/`http_headers` redacted. **The item is CC BY 3.0, not public domain**
(corrected 2026-07-28 by `T037-R2`, which found the same wrong claim in the network fixture): the
Blender Foundation's release poster carries the attribution. Capturing an `info_dict` from it is
fine either way; the correction matters because `LIC-001` makes licence claims load-bearing and a
wrong one repeated in two files is how it becomes something nobody re-checks.

**Mutation-checked (10 of 10 killed, after two survivors became tests).** Mapping order, `orig_msg` preference, `unwrap`, `has_drm`
`all`→`any`, `_has_drm`, the `'none'` codec sentinel, `_origin_of` trusting its candidate — and
`filesize_approx`, which **survived**: the archive.org fixture populates `filesize` on every
format, so nothing exercised the fallback. Per §13 that defaults to "missing test", and it was
one — YouTube's DASH formats commonly carry only `filesize_approx`, so the gap would have shown
"unknown" for sizes yt-dlp knows, on the site that matters most. Test added; mutation now dies.

**Checks.** `ruff check`, `ruff format --check`, `mypy`, `mypy --platform win32` all clean;
**765 passed, 6 skipped**. Windows evidence pending CI.

**Owner:** Implementer
**Priority:** High — this is where `ARC-002` stops being a design
**Phase:** Phase 1
**Depends on:** `T-011`, `T-034` (no file write without a validated path), `T-035` (no
yt-dlp without a candidate list)
**Relevant context:** `ARCHITECTURE.md` §3, §6, §7; `ARC-002`, `OPS-002`, `NFR-008`,
`REQ-002`, `REQ-005`, `REQ-025`, `REQ-028`, `NFR-006`; `ai/TESTING.md` §5 (fixtures)
**Affected surfaces:** `downloader/worker.py`, `downloader/ytdlp_adapter.py`,
`tests/unit/`, `tests/integration/`, `tests/fixtures/infodicts/`
**Risk:** **High** — the first code to run in a spawned process, the only code that may import
`yt_dlp`, and the seam every future upstream change lands on
**Review base:** the last of the `T-011`, `T-034` and `T-035` merge commits — *not* `T-011`
alone, which an earlier draft said while already depending on the other two

#### Scope

Two modules, and they are the **only** two in the project permitted to `import yt_dlp`
(`ARCHITECTURE.md` §6, enforced by `T-005`'s layering test):

1. **`ytdlp_adapter.py`** — builds the yt-dlp options dict from a `DownloadRequest`, projects
   `info_dict` into `MediaInfo`/`FormatInfo`, and maps yt-dlp exceptions onto the `core.errors`
   taxonomy. Pure translation: no process handling, no I/O of its own.
2. **`worker.py`** — the child-process entry point. Import-safe under `spawn` (no side effects
   at import time), resolves yt-dlp per `OPS-002`, runs one probe or one download, converts
   `progress_hooks` and `postprocessor_hooks` into `T-011` messages, and exits.

Neither may import Qt: the worker runs with no display and must inherit no Qt (`ARC-002`).

**This task also owns yt-dlp's import and template rendering**, both moved here from
neighbouring tasks after review:

- **Importing yt-dlp and reporting its version.** `T-035` locates candidates; `worker.py`
  walks them, prepends to `sys.path`, imports, falls back on `ImportError`, and reports which
  candidate won and why any earlier one lost (`OPS-002`, `REQ-025`). Only the importer can
  read the version, and only these two modules may import at all (§6).
- **Output-template rendering and the `REQ-011` preview.** Rendering uses yt-dlp's own
  template mechanism (`ARCHITECTURE.md` §9), so it cannot live in `core/`. The rendered result
  is then passed through `T-034`'s sanitizing and containment check before anything is
  written.

**Fixtures.** `T-018` broadens fixture coverage, but this task cannot be tested without at
least one recorded `info_dict`, so it captures the first ones itself — recording the yt-dlp
version and capture date alongside each, per `ai/TESTING.md` §5. Adapter projection is tested
against recorded fixtures, never against the live network.

**`T-012` stays whole — settled, do not re-open.** Splitting the adapter from the worker was
considered twice and rejected by the maintainer on 2026-07-25. The argument for splitting is
that they fail differently: translation bugs versus process bugs. The argument against, which
won, is that the adapter has no meaningful test surface without a worker to run it in, so a
split would produce one task that cannot be verified and a second that carries all the risk
anyway. Review it as one unit and expect it to be the largest review in the phase.

**`T-033` stays separate, deliberately.** This task makes the worker import `yt_dlp` from
source; `T-033` makes the *frozen artifact* actually contain it. Folding them together would
mean one review covering both a domain seam and a packaging change, and would let a green
source-mode suite imply a working release. `T-012` therefore claims nothing about the frozen
build, and `T-033` becomes Ready the moment this merges.

#### Acceptance criteria

- A probe of a recorded fixture yields a `MediaInfo` with title, uploader, duration and
  format list, asserted field by field
- Every taxonomy kind in `ARCHITECTURE.md` §7 that yt-dlp can raise has a mapping, asserted
  against the §7 table; an unmapped exception classifies as the explicit unknown case rather
  than crashing the worker
- The extractor's own message survives classification verbatim (`REQ-005`, `NFR-006`) —
  asserted by string equality against the fixture, not by substring
- **`DRM_PROTECTED` is classified as non-retryable and no alternative extraction is
  attempted** (`REQ-EXCL-001`, `SEC-001`). Asserted at *this* level as a property of the
  classification and of the adapter's behavior — asserting "is never retried" here would be
  vacuous, because no retry mechanism exists until Phase 2, which is where that assertion
  belongs
- The worker runs headless: a test spawns it with no display and it completes (`ARC-002`)
- The worker module imports cleanly under `spawn` with no side effects — asserted by importing
  it in a fresh interpreter and observing no work performed
- yt-dlp's resolved version is reported through a message (`REQ-025`), read from the imported
  module rather than from a recorded string that could drift
- With a **broken** user copy present — a path that exists holding an unimportable package —
  the worker falls back to the baseline and **says so**; a test asserts both the fallback and
  that it was not silent (`ARCHITECTURE.md` §6)
- A rendered output template is passed through `T-034`'s containment check before use; a
  template that renders outside the target directory is rejected, not written
- The `REQ-011` preview equals the path actually used — asserted by rendering, previewing,
  downloading to a temporary directory, and comparing the real result
- Changing a projected `info_dict` key in a fixture fails the projection test — the fixture is
  a contract, not a sample
- The layering test still passes, and `yt_dlp` appears in exactly these two modules

#### Out of scope

- The process pool, scheduling, and Qt signals — `T-013`. In particular **`WORKER_CRASH`
  cannot be asserted here**: it is produced by the parent observing a child's exit, and there
  is no parent until `T-013`. An earlier draft claimed it as a criterion of this task
- Bundling yt-dlp into the frozen artifact — `T-033`
- Broadening fixture coverage across sites — `T-018`
- Cancellation and crash *integration* tests — `T-019`; this task covers the worker side, and
  the 2-second cancellation criterion is measured there
- The in-app yt-dlp updater — Phase 4; this task only *resolves* what `OPS-002` describes

---

Every Phase 1 task is now planned in full. `T-034` was filed during planning: output-path
rendering and filename safety belonged to no task, despite being a `ai/TESTING.md` §7
mandatory area that `T-012` depends on.

**Four requirements are cited in Phase 1 but only partly discharged here**, and are listed so
raw citation counts are not mistaken for coverage:

| REQ | Cited by | Discharged in Phase 1? |
|---|---|---|
| `REQ-008` (select format IDs from the table) | `T-015` out-of-scope | **No.** The format table is Phase 3. `T-015` only notes the boundary. |
| `REQ-021` (open / reveal a completed file) | `T-017` out-of-scope | **No.** Phase 2. |
| `REQ-025` (report the yt-dlp version, update it in-app) | `T-012`, `T-035` | **Partly.** Reporting the resolved version, yes. Updating it in-app is Phase 4 (`OPS-002`). |
| `REQ-026` (cookies for entitled content) | `T-014`, `T-038` | **Partly.** Only the promise that cookie material never reaches the database or a log. Cookie *input* is Phase 3. |

**Five tasks were filed during planning, not created as new work.** `T-034` (path safety),
`T-035` (environment resolution), `T-036` (application composition), `T-037` (end-to-end
download and restart proof) and `T-038` (logging and redaction) are all `ARCHITECTURE.md` or
`IMPLEMENTATION_PLAN.md` responsibilities that the original ten-row outline did not own. Two
were found while writing dependencies, three by review. Without `T-036` and `T-037` in
particular, every task could pass while the application still opened an empty window and no
download was ever proven to complete.

Dependency order: `T-010`; then `T-011`, `T-014`, `T-015`, `T-034` in parallel; then `T-035`
and `T-038`; then `T-012`; then `T-013`; then `T-016`, `T-017`, `T-018`, `T-019`; then `T-036`;
then `T-037`.

---

### T-034 — Filename safety and output-path containment

**Status:** **Complete — approved with follow-ups**, 2026-07-26 at `313198d`.

Closes `ai/TESTING.md` §7's **Path safety** mandatory area, taking the covered set from two to
three.
Four review rounds and two maintainer-authorized exception passes; the reviewer independently
probed `C:../evil.mp4` and `C:..\evil.mp4` and confirmed both stay contained.

**Follow-up owned elsewhere:** `T-045` is implemented but independently in review, in this same
module. It does not block this task under `AGENTS.md` §9.
**Owner:** Implementer
**Priority:** **High** — a `ai/TESTING.md` §7 mandatory area, and `T-012` cannot write a file
without it
**Phase:** Phase 1
**Depends on:** `T-010`
**Relevant context:** `ARCHITECTURE.md` §8 (Filename safety), §9 (Security boundaries);
`REQ-011`, `NFR-004`; `ai/TESTING.md` §7 (Path safety)
**Affected surfaces:** `core/paths.py`, `tests/unit/`
**Risk:** **High** — the failure mode is writing a file outside the directory the user chose,
driven by a title an attacker controls
**Review base:** the `T-010` merge commit

#### Scope

**Filed during Phase 1 planning: this was assigned to no task.** `ARCHITECTURE.md` §8 requires
every output path to pass through `core/paths.py`, `ai/TESTING.md` §7 lists path safety as
mandatory coverage, and `T-012` writes files — so the slice cannot be built without it, and
nothing in the original outline owned it.

**Corrected after review: this task no longer renders output templates.** The earlier draft
put yt-dlp-compatible template rendering in `core/paths.py`, which cannot work —
`ARCHITECTURE.md` §9 says rendering uses *yt-dlp's own template mechanism*, and `core/` may not
import `yt_dlp` (§6). Reimplementing yt-dlp's template language in `core/` would be a second
implementation of someone else's syntax, guaranteed to drift.

The responsibility splits:

- **`core/paths.py` (this task)** — pure, yt-dlp-free: platform directory resolution, filename
  sanitizing, and the containment check. Given a candidate path and a target directory, it
  answers *is this safe and legal on both platforms*, and returns a sanitized path.
- **`ytdlp_adapter.py` (`T-012`)** — passes the output template to yt-dlp, which renders it,
  then runs the result through this module before it is used. Rendering stays with the only
  code allowed to know yt-dlp's syntax.

Sanitizing enforces the **intersection** of Linux and Windows rules: reserved device names
(`CON`, `NUL`, `LPT1`…), characters illegal on NTFS, trailing dots and spaces, and path-length
limits.

The security property, stated plainly: **a title-derived filename must never escape the
configured output directory.** Titles come from media sites and are attacker-influenced data.
After rendering, `..` and absolute components are rejected, and the result is verified to be
contained within the target directory.

#### Acceptance criteria

- A rendered path is always inside the configured output directory. Asserted against titles
  containing `../`, absolute paths, drive letters, UNC prefixes, NUL bytes, and separators for
  the *other* platform — each must be neutralized, not merely escaped
- Windows-illegal names are sanitized **on both platforms**, not only on Windows
  (`ai/TESTING.md` §7) — a name legal on Linux that becomes illegal when the file syncs to
  Windows is still a defect
- Reserved device names are handled including with extensions (`CON.mp4`), which is the case
  usually missed
- Over-long paths are shortened without losing the extension or colliding with a neighbouring
  file
- Sanitizing is deterministic and idempotent: sanitizing an already-sanitized path returns it
  unchanged, so passing a path through twice cannot corrupt it
- The `REQ-011` live preview is **not** this task's — it needs a rendered template and
  therefore belongs with `T-012`, which owns rendering. This task supplies the sanitizing step
  the preview must pass through, and `T-012` asserts preview-equals-actual
- `core/paths.py` imports no Qt and no `yt_dlp`

#### Out of scope

- **Output-template rendering** — `T-012`, because it uses yt-dlp's own mechanism
- The `REQ-011` live preview — `T-012`, for the same reason
- The settings UI for choosing a template — Phase 4
- Collision policy when the target file already exists — Phase 2 alongside resume
- Any actual file writing; this module computes and validates paths

---

### T-035 — Resolve the yt-dlp and ffmpeg environment

**Status:** **Complete — approved with follow-ups**, 2026-07-26. Both functional blockers
(`T035-R1`, `T035-R2`) resolved and independently verified; the remaining Low findings are owned
by `T-044` and do not keep this task in review.

**`T-012`'s last prerequisite** — with `T-011` approved and `T-034` in its final pass, the
Phase 1 chokepoint is all but unblocked.

**The ownership split is the substance of this task, and it is asserted, not just described.**
`environment.py` locates; `worker.py` imports. A test parses the module's AST and fails if it
imports `yt_dlp` **or `importlib`** — the latter matters because `test_layering.py` looks for an
`import yt_dlp` statement, and `importlib.import_module("yt_dlp")` is not one while violating §6
exactly as much. A second test asserts the module exposes no `version`/`verify`/`is_usable`, so
the split cannot erode back by someone adding a helpful-looking function.

Mutation-checked, eight weakenings; seven fail:

- reordering baseline ahead of the user copy — 2 fail
- filtering out a user copy with no `yt_dlp/` directory — 4 fail
- silently falling back to `PATH` when an override is missing — 2 fail
- a vague "some features are unavailable" summary — 1 fail
- logging the user path instead of the source label — 1 fail
- accepting a *directory* named `ffmpeg` — 1 fail
- adding a `version()` that reaches for `importlib` — 2 fail

**The eighth is invisible on Linux by nature and that is recorded rather than papered over:**
dropping `appauthor=False` changes nothing on Linux — both spellings resolve to
`~/.local/share/tracksandtrails` — while on Windows it inserts an author segment and doubles the
directory. `test_the_default_user_directory_is_not_doubled` is a real gate, but only the Windows
job can fail it. That is what `T-006`'s matrix is for, and the same trap `T-007` hit for
`window.toml`.

**A Windows-only test defect, caught by CI.** `test_ffmpeg_found_on_path_reports_available`
created a fake binary named `ffmpeg`; Windows resolves executables through `PATHEXT`, so
`shutil.which` did not find it and the test failed there while passing on Linux. The production
code was right — the fixture assumed POSIX semantics. Second time this session a test has
carried a Linux assumption into the Windows job.

**Reviewed 2026-07-26 — changes requested; two blocking Medium findings plus one Low, all
corrected:**

- **`T035-R1`** — `ytdlp_candidates()` always returned two entries, contradicting the criterion
  that with no user copy the list is *the baseline alone*. Worse, my test had quietly weakened
  itself to "the only **present** candidate" to match. Absent candidates are no longer listed,
  the `exists` flag is gone, and the test asserts the tuple rather than a filtered projection.
- **`T035-R2`** — an override was accepted on `is_file()` alone, so a mode-0644 file was
  reported available while the summary claimed every feature worked. `shutil.which` now applies
  the platform's own executable semantics, matching what the `PATH` branch already got. **The
  positive fixture itself created a non-executable file**, enshrining the bug.
- **`T035-R3` (Low)** — the ownership test named six forbidden strings, so `get_ytdlp_version()`
  slipped through. Replaced with a reviewed-API allowlist: guessing the names a future author
  picks is unwinnable, and forcing any new export to be justified is the conversation worth having.

All three weakenings now fail: absent candidate 2, non-executable override 1, new export 1.
**Owner:** Implementer
**Priority:** High — `T-012` cannot honour `OPS-002` without it, and `REQ-024` is owned by
nothing else
**Phase:** Phase 1
**Depends on:** `T-011`
**Relevant context:** `ARCHITECTURE.md` §6 (resolution order), §4; `OPS-002`, `OPS-001`,
`REQ-024`, `REQ-025`, `NFR-007`
**Affected surfaces:** `downloader/environment.py`, `tests/unit/`, `tests/integration/`
**Risk:** Medium — a wrong answer here is misattributed to yt-dlp or to the site
**Review base:** the `T-011` merge commit

#### Scope

**Filed during Phase 1 planning: `downloader/environment.py` was claimed by no task, and
`REQ-024` by nothing at all.** `ARCHITECTURE.md` §4 assigns this module "locating yt-dlp and
ffmpeg; version reporting; update", and `ARCHITECTURE.md` §6 puts yt-dlp resolution at *worker
start* — so `T-012` needs it from its first line, and without it the worker would import
whatever yt-dlp happens to be on `sys.path`, which is precisely what `OPS-002` rejects.

Two jobs:

1. **Locate yt-dlp candidates** per `OPS-002` — and *only* locate them. This module returns
   an ordered list of candidate paths: the user-managed copy in
   `user_data_dir/tracksandtrails/ytdlp/` first, then the bundled baseline. It reports what
   exists on disk and answers nothing about whether a candidate works.

   **It must not import yt-dlp**, and the earlier draft of this task required exactly that —
   "fail loudly if the user copy does not import cleanly" and "report the resolved version"
   are both unimplementable without importing it. `ARCHITECTURE.md` §6 permits that import in
   `worker.py` and `ytdlp_adapter.py` alone, and `T-005`'s layering guard enforces it after
   being deliberately mutation-tested. Reaching for `importlib` to slip past the guard would
   be worse than the violation, because it defeats a check the project spent two review
   rounds hardening.

   So the split is: **`environment.py` locates, `worker.py` imports.** `worker.py` walks the
   candidate list, prepends the first entry to `sys.path`, imports, and on `ImportError` falls
   back to the next candidate — reporting which one it used and why any earlier candidate was
   rejected (`ARCHITECTURE.md` §6: fail loudly, never silently ignore an override). The
   version comes from the imported module, so only the importer can report it (`REQ-025`).

   If a third module ever genuinely needs to import yt-dlp, that is an architecture change:
   amend `ARCHITECTURE.md` §6 and the layering rule deliberately, in a reviewed change.
2. **Detect ffmpeg** at startup and report which features are unavailable without it
   (`REQ-024`, `OPS-001`) — rather than failing at merge time, after a download has already
   consumed the user's bandwidth.

Resolution runs in the worker, so this module must not import Qt.

#### Acceptance criteria

- With no user copy present, the candidate list contains the baseline alone
- With a user copy present, it is ordered ahead of the baseline
- A candidate directory that exists but is empty, or contains no `yt_dlp` package, is still
  *listed* — deciding it is unusable requires importing it, which is `worker.py`'s job
- `environment.py` does not import `yt_dlp`, asserted by the layering test **and** by a test
  that the module can be imported with `yt_dlp` absent from `sys.modules` entirely
- **Ownership boundary asserted:** a test confirms `environment.py` exposes no version and no
  usability verdict, so the split cannot erode back into this module by accident
- ffmpeg presence and absence both yield a correct feature report; the absent case names what
  will not work (`REQ-024`)
- Detection never executes a shell (`ARCHITECTURE.md` §9) and never blocks the GUI thread
- No user path, cookie, or credential reaches a log line from this module (`NFR-007`)
- `environment.py` imports no Qt

#### Out of scope

- Downloading and extracting the yt-dlp wheel — Phase 4; this task resolves what is already
  present
- Bundling either dependency into the frozen artifact — `T-033` for yt-dlp, Phase 5 for ffmpeg
- Any UI for showing the version or the ffmpeg state — `T-016`/`T-017` consume the report

---

### T-042 — Make the model audit enforce nullability and boolean rejection

**Status:** **Complete — approved** 2026-07-26, mutation-verified independently.
**Owner:** Implementer
**Priority:** Low — production behavior is already correct; this is test strength, not a defect
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `T041-R6`, `T041-R1`, `T010-R1`
**Affected surfaces:** `tests/unit/test_models.py`
**Risk:** Low to fix. The risk it addresses is a **silent regression**: production could lose
these guards and the suite would stay green.

#### Scope

Two gaps in `tests/unit/test_models.py`, both confirmed by mutation on 2026-07-26:

1. **The `None` case in the hostile-payload sweep is vacuous.** Its assertion is
   `not isinstance(stored, dict | list)`, and `None` is neither — so a field that accepts and
   stores `None` passes. Nullability is actually protected only by
   `test_required_job_counters_reject_none`, which names two fields explicitly.

   **This was overstated in `T-041`'s handoff**, which claimed adding `None` to the sweep covered
   the class. It did not; the reviewer was right to check rather than take the claim.

2. **Nothing tests boolean rejection.** `_require_optional_count()` excludes `bool` because it is
   an `int` subclass and `True` would be stored as a count of 1 — but deleting that check leaves
   all 76 model tests green.

#### Acceptance criteria

- The sweep distinguishes fields that are genuinely optional from those that are not, and a
  required field accepting `None` fails — derived from the model's own annotations rather than a
  hand-listed set of field names, so a new required field is covered without editing a list
  (`T041-R2`'s lesson)
- Deleting the `bool` guard from either count validator fails the suite
- Both mutations are demonstrated and recorded in this task, not asserted in the abstract
- No production change: the behavior is already correct and must stay so

#### Out of scope

- `downloader/protocol.py`'s equivalent sweep. It has the same shape and may have the same gap;
  check it, and if so file separately rather than widening this task

---

### T-043 — Protect `protocol.py`'s remaining boolean guards

**Status:** **Complete — approved** 2026-07-26, mutation-verified independently.
**Owner:** Implementer
**Priority:** Low — production behavior is correct; the guards are simply untested
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `T041-R6`, `T042`, `T011-R2`
**Affected surfaces:** `tests/unit/test_protocol.py`
**Risk:** Low to fix; the risk it addresses is a **silent regression**

#### Scope

`T-042` closed the same class in `core/models.py` and its out-of-scope note required checking
the sibling sweep. `downloader/protocol.py` is in better shape — no required field accepts
`None`, and the count validators' `bool` guards are covered — but two are not:

- `Progress.speed_bytes_per_second` (`_require_optional_rate`)
- `WorkerFinished.exit_code`

Deleting either guard leaves **all 113 protocol tests green**, verified by mutation on
2026-07-26. `bool` is an `int` subclass, so `True` would be stored as a rate of 1 byte/second or
an exit code of 1 — a wrong number that reads as a right one.

Apply the annotation-driven approach `T-042` used rather than adding two more names to a
parametrize list: derive the numeric fields from each message's type hints.

#### Acceptance criteria

- Deleting the `bool` guard from `_require_optional_rate` fails the suite
- Deleting it from `WorkerFinished.exit_code` fails the suite
- The check is derived from the message annotations, so a numeric field added later is covered
  without editing a list
- Both mutations demonstrated and recorded here
- No production change

#### Out of scope

- Nullability in `protocol.py` — already verified sound: no required field accepts `None`
- Any production change to `protocol.py`

---

### T-041 — Validate nested payloads in `core/models.py`

**Status:** **Complete — approved** at `0268e13`, 2026-07-26. All five findings independently
verified resolved; `T011-R8` functionally closed. CI run `30216176642` was verified green at that
exact head by the reviewer.

One non-blocking Low finding, **`T041-R6`, was carried forward to `T-042`**.

**The reported hole was one field; the audit found the whole module.** `T011-R8` named
`MediaInfo.formats`. Enumerating every field of every model showed that **all of them** accepted
an arbitrary dict or list — the only checks were emptiness and negativity, and a non-empty dict
passes both. Fixing the named field alone would have repeated exactly what got `T011-R2`
reopened, so the fix is a validation layer over all five models plus a systematic audit test.

Verified after the change: a raw dict, a list of raw dicts, and a mutable list are now rejected
by **every** field of every model; `T011-R8`'s exact reproduction raises with an `ARC-002`
message; and a caller's list can no longer mutate a constructed model.

**Second pass, 2026-07-26 — five findings corrected:**

- **`T041-R1`** — `bytes_done` and `attempts` are `int` with a `0` default, but I routed them
  through the *optional* validator, so both accepted `None`. A `_require_count` now separates
  required from optional counters, and `None` is in the hostile-payload sweep — its absence is
  why this stayed green.
- **`T041-R2`** — the "guards the guard" test compared `valid_kwargs()` with a hand-written
  `MODELS` list: **two views of one hand-maintained set**, so a sixth model left all 54 tests
  green. That is the `T010-R1` vacuity reproduced inside the test written to prevent it. The
  production side is now discovered by inspecting the module for dataclasses it defines.
- **`T041-R3`** — `_require_model()` and `_as_tuple_of()` used `isinstance`, so a frozen
  subclass carrying an extra mutable dict rode along inside a validated graph. Both now require
  the exact declared type, matching what `T-011` did to `is_message()`.
- **`T041-R4`** — required text fields now route through `_require_text()`: `TypeError` for the
  wrong type, `ValueError` for a validly typed empty string. The explanatory messages survive
  via a `reason` argument.
- **`T041-R5`** — task placement, canonical status, and `STATUS.md`'s premature claim.

**Mutation-checked, each against the finding it closes:** a sixth model fails 5 tests
(previously 0); an unvalidated field on an existing model fails 3; reverting `bytes_done` to the
optional validator fails 1; reverting either boundary to `isinstance` fails 2.

**Note for review:** the field annotations still say `tuple[...]` while the constructors accept
any non-`str` sequence and normalise it. That is deliberate — the annotation describes what is
*stored*, which is what readers depend on — but it is the same signature/runtime divergence
`T011-R3` objected to in `protocol.py`, so it is worth a second opinion rather than my say-so.
**Owner:** Implementer
**Priority:** **High** — it falsifies a guarantee `downloader/protocol.py` currently advertises
**Phase:** Phase 1
**Depends on:** nothing; `core/models.py` exists and is approved (`T-010`)
**Relevant context:** `T011-R8`, `T011-R2`, `T010-R2`; `ARC-002`; `ARCHITECTURE.md` §3 and §5;
`NFR-008`
**Affected surfaces:** `src/tracks_and_trails/core/models.py`, `tests/unit/test_models.py`
**Risk:** Medium to fix, **High to leave** — the failure is silent and the data is
attacker-influenced

#### Scope

`T-011` made `Probed.media` reject anything that is not a `MediaInfo`. It did not check what a
`MediaInfo` *contains*, and `T011-R8` found the hole that leaves:

```python
raw = [{"format_id": "137", "url": "https://cdn.example/secret"}]
msg = Probed(job_id="j", media=MediaInfo(url=..., title="T", formats=raw))
is_message(msg)  # True
msg.media.formats[0]  # {'format_id': '137', 'url': '...'} — a raw yt-dlp dict
raw.append({...})  # and it still mutates after construction
```

Two invariants break at once. Raw yt-dlp data crosses the process boundary inside a message
that validates (`ARC-002`, `NFR-008`), and a mutable list reachable from a sent message can
change after `put()` and before the feeder thread serializes it — the `T010-R2` hazard.

**Fix the class, not the instance.** `T011-R2` had to be reopened precisely because the first
correction validated the fields the review named. Every collection and nested model field in
`core/models.py` needs checking, not just `MediaInfo.formats`:

- `MediaInfo.formats` — a tuple of `FormatInfo`
- `DownloadRequest.post_processors`, `.subtitle_languages` — tuples of `str`
- `Preset.post_processors` — a tuple of `str`
- `Job.request` — a `DownloadRequest`
- `Job.error_kind` — an `ErrorKind` or `None`

Normalising a list to a tuple is acceptable where the element types are right; passing raw
dicts where models belong is not, and must raise.

#### Acceptance criteria

- `MediaInfo(formats=[{...}])` **raises**; a raw yt-dlp format dict cannot reach a `Probed`
- Every collection field is stored as a tuple, whatever sequence type was passed, and mutating
  the original afterwards does not change the model
- A **systematic** test walks every field of every model in `core/models.py` and asserts that a
  raw `dict`, and a `list` of raw dicts, are rejected or normalised — modelled on
  `test_no_field_accepts_and_stores_a_mutable_mapping`, so a field added later is covered
  without anyone extending a list by hand
- Nested validation survives `pickle`: a restored `MediaInfo` carries `FormatInfo` instances
  and immutable collections
- `T011-R8`'s exact reproduction is a regression test
- The layering test still passes: `core/` imports no Qt and no `yt_dlp`

#### Out of scope

- Any change to `downloader/protocol.py` — its own validation is correct; this is the layer
  beneath it
- Projecting an `info_dict` into `MediaInfo` — `T-012` owns the adapter that does it
- Retro-fitting the same audit to `persistence/` — nothing exists there yet (`T-014`)

---

### T-011 — IPC message contract

**Status:** **Complete** — every finding resolved, 2026-07-26.

Three review rounds, all recorded in `ai/REVIEWS.md`. `T011-R1`, `R2`, `R3`, `R4`, `R6` and
`R7` were **reviewer-verified resolved**, each with mutation evidence. `T011-R5` closed when the
maintainer **accepted `ARC-003`**, which settles that `ARC-002`'s "versioned internal contract"
means version-*controlled*, not version-*negotiated* — so this task complies as written.

**On the absence of a fourth Codex pass:** the reviewer's verification stated that `R5` was the
only open item, that it awaited a maintainer decision, and that *"no further Codex re-review is
implied"*. Nothing changed in the implementation between that verification and this status —
only the decision it was waiting on. This is therefore not a waived review in the sense of
`T-007` or `T-026`'s third round; the code at this head is the code Codex verified.

`T011-R8` was carried out of this task into **`T-041`** and is **not** fixed here: a `MediaInfo`
can still hold a mutable list of raw yt-dlp format dicts, so raw upstream data crosses the
boundary inside a message that validates. `T-011`'s own validation is correct; the layer beneath
it is not yet.

- **`T011-R1` (High), corrected.** A successful probe produced *no outcome*: `Probed` then
  `WorkerFinished`, neither counted as terminal. A receiver applying `REQ-028`'s "exited 0 with
  no outcome means the worker crashed" would have failed **every** successful probe. The
  contract now models **sessions**: a probe or a download produces exactly one outcome, `Probed`
  is an outcome, and `validate_sequence()` is the executable form. `WorkerFinished` stays a
  non-outcome, which the reviewer confirmed is right.
- **`T011-R2` (High), corrected.** Constructors validated only the outer class, so
  `Probed(media={...})` carried a raw `info_dict` across the boundary — the exact `ARC-002`
  violation this module exists to prevent — and string stages, string kinds, mutable dict
  contexts and undeclared subclasses all passed. Payloads are now type-checked, `context` is
  normalised by the **same helper** `FailureDetail` uses rather than a near-copy, and
  `is_message()` is an exact type match.
- **`T011-R3` (Medium), corrected.** All messages are `kw_only`, so required payloads have no
  defaults and honest non-optional annotations. `Progress.stage` is required — it defaulted to
  `PROBING`, so omitting it produced a valid message that confidently misreported the stage.
- **`T011-R4` (Medium), corrected** in `T-013`'s acceptance criteria, which now require
  terminal-once to be enforced and tested rather than merely assigned.
- **`T011-R5` (Low), narrowed.** The module now claims only "no runtime negotiation" and records
  that `ARC-002`'s "versioned internal contract" is the accepted decision's wording. **Whether
  `ARC-002` meant version-controlled or an explicit protocol version is a maintainer question,
  raised in `STATUS.md` — not something this task may decide.**
- **`T011-R6` (Low), corrected.** Task placement, status vocabulary, metadata and `STATUS.md`
  reconciled.

**Verified 2026-07-26:** the reviewer confirmed `T011-R2`'s reopened fields and `T011-R7`
**resolved**, with mutation evidence — the dict speed/byte-count substitution fails 33 tests, an
added unvalidated field is caught specifically by the generic audit, and disabling probe-stage
enforcement fails the four intended tests.

**`T-011` is still not approved**, for one reason: `T011-R5` is parked on a maintainer reading
of `ARC-002`. Nothing an Implementer does can close it.

**`T011-R8` (High) was carried out of this task into `T-041`**, not fixed here. `Probed.media`
correctly rejects a non-`MediaInfo`, but a `MediaInfo` can itself hold a mutable list of raw
yt-dlp format dicts — so raw upstream data still crosses the boundary inside a message that
validates. The hole is **live at this head**; `protocol.py`'s guarantee is only as strong as
`core/models.py` beneath it.

**Third pass, 2026-07-26 (`T011-R2` reopened, `T011-R7` new):**

- **`T011-R2`** — the first correction validated the fields the review *named* and left
  `Progress.speed_bytes_per_second` and `Succeeded.total_bytes` accepting a mutable dict; a
  substitution left all 100 tests green. Both are validated now — but the real fix is
  `test_no_field_accepts_and_stores_a_mutable_mapping`, which walks **every field of every
  message type**. Listing two more fields would have repeated the same mistake one size smaller.
- **`T011-R7`** — the module documented the probe grammar as `Progress(PROBING)*` and claimed
  `validate_sequence()` was its executable form, but a probe reporting `MERGING` validated.
  Probe sessions now reject any other stage. Download-stage ordering stays unconstrained, and a
  test asserts that narrowness is deliberate: real yt-dlp pipelines skip and repeat stages.

**Verified against the reviewer's own probes**, not just re-asserted: the sample mutation that
previously left all 48 tests passing now fails **28**, and all five direct runtime probes
(wrapped dict, string stage, string kind, mutable context, undeclared subclass) now raise.
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 1
**Depends on:** `T-010`
**Relevant context:** `ARCHITECTURE.md` §3 (process model), §6 (yt-dlp boundary), §7;
`ARC-002`, `NFR-008`, `REQ-014`, `REQ-028`
**Affected surfaces:** `downloader/protocol.py`, `tests/unit/`
**Risk:** Medium — this is the parent/child contract; a gap here shows up as a hang, not an
exception
**Review base:** the `T-010` merge commit

#### Scope

The typed messages that cross the `multiprocessing.Queue` between the GUI process and a
worker, and nothing else. One module, no behavior beyond construction and validation.

Cover the message kinds the vertical slice needs: a probe result, progress updates carrying
the stages `REQ-014` names (probing, downloading video, downloading audio, merging,
post-processing), a terminal success carrying the final path and byte count, and a terminal
failure carrying a `core.errors` classification plus the verbatim message.

The rule this module exists to enforce: **a raw yt-dlp `info_dict` never crosses the
boundary** (`ARCHITECTURE.md` §3). The dict's shape belongs to yt-dlp and changes without
notice (`NFR-008`); the parent must only ever see declared types projected by
`ytdlp_adapter.py`.

**Shutdown and identity are part of the contract, not details left to `T-013`.** The earlier
draft specified only the message payloads, which leaves three ways to hang or lie:

- **Every message carries a job ID.** Without it the parent cannot attribute a message, and
  "exactly one terminal message per job" is unenforceable.
- **A sentinel terminates the stream.** `ResultPump` does a blocking `Queue.get()`; with no
  sentinel, shutdown depends on a timeout or on killing a thread mid-read. The protocol
  defines the sentinel and the guarantee that it is the last thing sent.
- **Terminal-once is a receiver obligation, stated here.** Message classes alone cannot
  prevent a second terminal message being sent — an earlier draft claimed they could. The
  protocol therefore *specifies* that a job has exactly one terminal outcome and that the
  receiver must enforce it by job ID; `T-013` implements the enforcement.

**No runtime version negotiation.** Both ends ship in the same artifact and are always the same
build, even when the user updates yt-dlp underneath (`OPS-002`) — that changes the *engine*, not
the contract. Recording this so nobody later adds negotiation machinery for a skew that cannot
occur.

**This does not resolve `T011-R5`.** `ARC-002` calls the protocol "a versioned internal
contract". Whether that meant version-*controlled* or an explicit protocol version is a
maintainer reading of an accepted decision, raised in `STATUS.md`. `DECISIONS.md` outranks this
file (`AGENTS.md` §5), so if it meant the latter, this task is non-compliant as written.

#### Acceptance criteria

- Every message type round-trips through `pickle` unchanged
- **Every message carries a job ID**, and constructing one without it fails
- A declared **outcome** predicate identifies exactly the types that report what a job
  achieved, so the receiver's terminal-once rule can be written against the protocol rather
  than a hardcoded list that drifts as types are added (**amended 2026-07-26 per `T011-R1`**:
  this said `is_terminal` and "success and failure types", which excluded `Probed` and left a
  successful probe with no outcome at all)
- **Legal sequences are specified and executable.** Each session kind declares which outcomes
  it may produce, and a validator rejects a missing outcome, a duplicate outcome, an outcome
  illegal for the session, a missing or misplaced sentinel, messages after the outcome, mixed
  job ids, and undeclared objects (`T011-R1`)
- A sentinel type exists, is picklable, and is documented as the last item on the queue
- Progress messages carry every stage named in `REQ-014`, asserted against that list
- A terminal failure carries both a `core.errors` kind **and** the original text; neither is
  optional, and a message with a classification but no text fails construction (`NFR-006`)
- A **validation helper** rejects anything that is not a declared message — including a bare
  `dict` — and it lives here so both ends share one definition of "valid". This task tests the
  helper directly; `T-013` applies it on receipt. The earlier draft promised rejection "at a
  seam" while declaring both seams out of scope, which was unimplementable
- `protocol.py` imports no Qt and no `yt_dlp`, enforced by the layering test
- Every message type is exercised by at least one test; an unexercised type fails the suite

#### Out of scope

- Sending or receiving anything — `T-012` (child side) and `T-013` (parent side). This task
  defines and tests the validator; it does not call it across a real queue
- Enforcing terminal-once — specified here, implemented and tested in `T-013`
- Queue lifetime, draining, and backpressure — `T-013`
- Any type that only Phase 2's queue needs

---

### T-010 — Domain models, job state machine, and error taxonomy

**Status:** **Complete — approved** on final re-review, 2026-07-26 (`ai/REVIEWS.md`). All four
findings resolved and verified by the reviewer. Unblocks `T-011`, `T-014`, `T-015`, `T-034`.

- **`T010-R1` (High), closed.** The exhaustive test asked `can_transition()` which pairs were
  illegal, so it compared the table with itself. The reviewer's `QUEUED → READY` mutation left
  48 tests green. `tests/unit/test_job_state.py` now carries `EXPECTED`, transcribed by hand
  from `ARCHITECTURE.md` §5, and checks production against it. The same mutation now fails 2
  tests. **My own earlier mutation check missed this**: I verified that adding a *status* broke
  the table and never that adding an *edge* did.
- **`T010-R2` (Medium), closed.** `context` is a sorted tuple of pairs with a `context_map`
  read-only view; in-place mutation raises. `MappingProxyType` was the obvious alternative and
  cannot be pickled, which rules it out for an `ARC-002` value.
- **`T010-R3` / `T010-R4` (Low), closed** as Planner amendments to the criteria below, per the
  reviewer's recommendation to keep production unchanged. The `FAILED` exclusion is now an
  explicit `CANCELLABLE` set rather than a silent `continue`.

**Owner:** Implementer
**Priority:** High — every other Phase 1 task imports this
**Phase:** Phase 1
**Depends on:** `T-001`
**Relevant context:** `ARCHITECTURE.md` §4 (layers), §5 (data ownership), §7 (error taxonomy),
§8 (settings propagation); `REQ-005`, `REQ-012`, `REQ-015`, `REQ-018`, `REQ-028`, `NFR-006`,
`REQ-EXCL-001`; `ai/TESTING.md` §7 (State machine)
**Affected surfaces:** `core/models.py`, `core/job_state.py`, `core/errors.py`,
`tests/unit/`
**Risk:** Medium — cheap to write, expensive to change once four other modules import it
**Review base:** `3c4f7a7`

#### Scope

The pure-domain foundation of the vertical slice. No Qt, no yt-dlp, no I/O beyond the standard
library — `core/` is the layer that stays testable headless and gets reused by both the GUI
process and the spawned worker.

Three modules, deliberately together because they are one design and splitting them would
mean three reviews of the same decisions:

1. **`models.py`** — `Job`, `JobStatus`, `MediaInfo`, `FormatInfo`, `Preset`,
   `DownloadRequest`. Plain dataclasses.
2. **`job_state.py`** — the legal-transition table and the single function that applies a
   transition. `ai/TESTING.md` §7 requires that every illegal transition raises; this is where
   that guarantee lives.
3. **`errors.py`** — the `ARCHITECTURE.md` §7 taxonomy as an enum, plus a `classify()` seam.
   The module *defines* the taxonomy and how a classified failure is carried; `T-012` supplies
   the yt-dlp-specific mapping into it, because that is the only place that may import
   `yt_dlp` (§6).

`errors.py` is pulled forward into this task rather than left to `T-012` for two reasons: it
is pure `core/` code, and `T-012` needs to classify from its first line, so writing it there
would put a `core/` design decision inside a task reviewed for its yt-dlp handling.

Two properties are load-bearing and easy to lose:

- **Everything here crosses a process boundary** (`ARC-002`). Every type must be picklable:
  plain dataclasses and enums, no lambdas, no open handles, no `functools.partial`.
- **`DownloadRequest` is frozen at job-creation time** (`ARCHITECTURE.md` §8). A running job
  never observes a mid-flight settings change, which is what makes the worker's behavior
  reproducible from the request alone.

#### Acceptance criteria

- Every model round-trips through `pickle` unchanged, asserted per type — this is what makes
  `T-011`'s IPC possible, and it fails loudly the day someone adds an unpicklable field
- **Each model's required fields and invariants are pinned**, not merely its picklability: a
  `Job` without an id or url fails construction, and its status is always a valid `JobStatus`,
  defaulting to `QUEUED` (**amended 2026-07-26 per `T010-R4`** — the criterion previously
  required construction to fail without an explicit status, which contradicted the implemented
  default; a new job is queued by definition, and no caller needs to distinguish "omitted" from
  "queued"); `MediaInfo` and `FormatInfo` declare
  the fields `ARCHITECTURE.md` §5 names. Empty dataclasses would satisfy a pickle test alone,
  which is exactly the vacuous pass to avoid
- `DownloadRequest` is immutable; attempting to mutate a field raises
- The state machine accepts every transition in the legal table and **raises on every
  transition outside it** — asserted exhaustively over the full `JobStatus × JobStatus`
  product, not over a sampled list, so a newly added status cannot silently acquire
  permissive behavior
- Adding a `JobStatus` member without adding its transitions fails the suite
- `CANCELLED` is reachable from exactly the states with work in flight — `QUEUED`, `PROBING`,
  `READY`, `RUNNING`, `PAUSED`, `POST_PROCESSING` — and no state is reachable *from* a terminal
  state (**amended 2026-07-26 per `T010-R3`**: this read "every non-terminal state", which
  wrongly implies `FAILED`. Cancelling stops active work and a failed job has none; `REQ-015`'s
  "remove" is deletion, not a lifecycle transition. `FAILED → QUEUED` remains its only edge)
- The taxonomy covers exactly the **eleven** kinds in `ARCHITECTURE.md` §7 — asserted against
  that list, so the table and the code cannot drift apart (**corrected 2026-07-26**: §7 has ten
  *rows*, one of which declares two kinds, `FFMPEG_MISSING` and `FFMPEG_ERROR`. The old wording
  counted rows. Collapsing them to match the count would lose a real distinction)
- A classified failure preserves the original message verbatim alongside the classification
  (`NFR-006`); the classification is additive and never replaces the text
- `DRM_PROTECTED` and `CANCELLED` are marked non-retryable, and `NETWORK` is the only kind
  marked auto-retryable (`REQ-018`, `REQ-EXCL-001`)
- The layering test still passes: no Qt, no `yt_dlp` anywhere in `core/`

#### Out of scope

- Any yt-dlp exception mapping — `T-012`, and it is the only place that may import `yt_dlp`
- Persistence of any of these types — `T-014` owns the schema
- Preset *content* and selector translation — `T-015`; this task defines the `Preset` shape
  only
- Retry scheduling and backoff policy — Phase 2, though the retryable flag is defined here

---

### T-026 — Verify Windows behavior against the runner's real desktop

**Status:** **Complete — third-round re-review waived by the maintainer**, 2026-07-26.

Two full independent review passes were performed (`ai/REVIEWS.md`), producing five findings;
all five are corrected. The waiver applies **only to the third round**, which would have
verified the `T026-R2` and `T026-R5` corrections. It is not an unreviewed merge — contrast
`T-007`, which had no independent pass at all.

**What the waiver rests on, stated so it can be re-examined:**

- `T026-R2`'s corrections were verified against the reviewer's **own adversarial trees**, rebuilt
  locally: a main window containing only native furniture, and an About dialog whose only button
  is the title-bar `Close`. Both previously passed; both are now rejected, and a healthy tree
  still passes all four main-window assertions.
- Windows CI is green on the corrections — run `30212152886`, `windows desktop` job, **20
  passed**, all five jobs green.
- **What no one verified independently:** that the corrected assertions fail for the *right*
  reasons against a real UI Automation tree. The adversarial trees are fabricated `Node` graphs,
  not live UIA output, and no missing-control or wrong-role mutation was run against a real
  Windows tree. That is the specific gap the waived round would have closed.

**`T026-R2`, second round.** The contract was still satisfiable by Windows' own furniture: a
name-and-role match cannot tell the application's menu bar from the System menu, nor the About
dialog's Close button from the title bar's. The reviewer proved both with fabricated trees.

Part of the cause was mine and worth recording: the `File`/`Help` equality written in the first
correction round was **deleted by accident** when a scripted block replacement spanned past it,
and the follow-up edit meant to scope it silently matched nothing. Three scripted edits in this
task failed that way; the ones that asserted on their own match did not.

The snapshot now walks the UIA control view and records each node's ancestor roles, so
`application_controls()` excludes the title bar's subtree. The equality is restored and scoped
to it, and the About dialog requires a Close button of its own. Verified locally against the
reviewer's three adversarial trees — all now rejected, and a healthy tree still passes.

**`T026-R5`, second round.** A stray duplicated copy of the `windows desktop` section sat
*before* `TESTING.md`'s document title — introduced by the same class of scripted edit. Removed;
metadata dated; the Windows-environment row in `STATUS.md` corrected; the obsolete ten-kind
paragraph deleted.

**The Phase 0 exit criterion was claimed too early, and is now genuinely met.** The new
subprocess launch test passed on Windows, so the application — not merely a widget — has been
observed starting on a real desktop through its real entry point.

**The original over-claim, kept as the record:** Run `30208677607` was genuinely green and
its `HWND` evidence real, but `T026-R1` is right that it proved a *widget* reaches a real
desktop, not that the *application* launches: every test constructed `MainWindow` inside pytest
and none touched `app.run`. The criterion is **not** met until the new subprocess launch test is
green on Windows.

- **`T026-R1` (High), corrected.** A subprocess test drives the real entry point under the real
  plugin, with the launched process reporting its own `IsWindow` / `IsWindowVisible` /
  `GetWindowTextW` results and a clean-stderr assertion.
- **`T026-R2` (High), corrected.** The accessibility contract is now an equality over names and
  roles. The File menu, Help menu and About dialog are each opened and queried by their own
  window handle, so `Quit`, `About` and the dialog's Close button are covered — none of them
  were reachable from the main window's handle alone.
- **`T026-R3` (Medium), corrected.** Tab order now has a concrete owner: `T-040`.
- **`T026-R4` (Low), corrected.** `mypy --platform win32` runs in the desktop job. It found
  seven real errors on first use, including `QAction.menu()` being typed as `QObject`.
- **`T026-R5` (Low), corrected.** Coordination documents reconciled.

**Incomplete against its own scope, deliberately.** The widget tab-order gate is not here: the
shell window has no focusable controls, so a focus-chain assertion would pass over zero widgets
— the vacuous check this task exists to avoid. It lands with `T-016`/`T-017`. The installer half
became `T-039`. `ai/TESTING.md` §9 and `REQUIREMENTS.md` §3 record both gaps rather than
implying full coverage.

**Three CI rounds were needed, and each failure was real rather than flaky:**
1. `findChildren(QMenu)` also returns an untitled internal `QMenu` Qt creates for the menu bar.
2. UI Automation returned an empty tree and `COMError 0x80040201`. A UIA client inspecting its
   own process must not call from the thread owning the window — Qt builds its accessibility
   bridge in response to `WM_GETOBJECT`, which that thread must handle. Queries now run in an
   MTA worker thread while the main thread pumps events.
3. `QMenu` wrappers died mid-test. The `QAction` list is what keeps them alive, so collecting
   menus in one loop and asserting in a second releases the actions and kills the menus. The
   first fix for this was wrong — it blamed the number of `menu()` calls, not the lifetime.
**Owner:** Implementer
**Priority:** High — this is what closes Phase 0's last exit criterion
**Phase:** Phase 0 follow-up; must land before the first public release
**Depends on:** `T-006`, `T-007`, `OPS-004`
**Relevant context:** `OPS-004`, `OPS-003` (superseded classification), `NFR-005`,
`ai/TESTING.md` §9, `REQUIREMENTS.md` §3
**Affected surfaces:** `.github/workflows/ci.yml`, `tests/ui/`, `ai/TESTING.md`,
`REQUIREMENTS.md` §3
**Risk:** Medium — it converts release-blocking manual work into automation, so a weak
implementation would retire a gate without replacing it

#### Scope

`OPS-003` assumed a CI runner has no desktop and wrote off most Windows verification as
human-only. A spike disproved that: `windows-latest` reports `platformName == 'windows'`,
a 1024×768 display, a native `HWND` whose title the Win32 API reads back, and captures
screenshots with native font rendering.

Move the objective half of Windows verification into CI:

1. **Real-plugin rendering.** Run the UI suite on Windows without `QT_QPA_PLATFORM=offscreen`
   as well as with it, and retain screenshots of each key window as artifacts.
2. **Focus and keyboard.** Assert tab order and focus chain through synthetic key events on a
   real window, not an offscreen one.
3. **Accessibility tree.** Assert every control's name and role as exposed to UI Automation —
   what a screen reader reads (`NFR-005`). Needs a dev-only dependency such as `comtypes`.

The fourth item `OPS-004` reclassified — installer behavior — is **`T-039`**, not this task.
An installer only exists in Phase 5, and this task must be completable now because it is what
closes Phase 0's remaining exit criterion.

#### Acceptance criteria

- The Windows job runs the UI suite under the real `windows` platform plugin and uploads a
  screenshot of every key window. **A screenshot is retained evidence, not a gate**: it is
  uploaded for a human to look at and does not turn the build red on its own. Any claim that
  a broken layout "fails" must be backed by a separate objective assertion — a widget's
  geometry, visibility, or size — not by the image (`T031-R2`).
- Tab order and focus chain are asserted on Windows, and reordering two widgets fails the test
- Every interactive control exposes a non-empty accessible name and a correct role through UI
  Automation; removing a label fails the test
- `ai/TESTING.md` §9's manual Windows list is rewritten to only what remains subjective **plus
  installer behavior**, which stays manual until `T-039` lands; `REQUIREMENTS.md` §3's
  "known-unverified" wording is narrowed to match — **each item moved only once its replacement
  automation has landed and is green**, never on the strength of this task's intent
- Native file dialogs, reveal-in-file-manager and open-file behavior are handled per
  `OPS-004`'s split: the request, path handling and shell verb are asserted; foreground and
  file-association behavior stay on the manual list
- Both the offscreen and real-plugin runs stay green, and the added time is recorded against
  `T-006`'s budget

#### Out of scope

- Pixel-perfect screenshot diffing — retain screenshots as evidence first; baselines are a
  separate decision, and a brittle image gate is worse than none
- The subjective residue in `OPS-004`: whether rendering looks right, whether Narrator sounds
  coherent, installer feel, long-running stability. Those still need a person and still block
  first release
- Installer verification — `T-039`, once Phase 5 produces an installer
- Buying or renting a cloud Windows desktop — complementary, not part of this

**Note:** this is the rare task that *reduces* release-blocking manual work. The risk is doing
it shallowly: a screenshot nobody looks at and an accessibility assertion that passes on an
empty tree would retire a real gate and replace it with theatre.

The criteria are therefore of two kinds, and conflating them is exactly the failure mode
(`P0-R7`). **Gates** — focus order, accessibility names and roles — are each stated as a
mutation that must turn the suite red, and only those may retire a manual item. **Retained
evidence** — the screenshots — is uploaded for a human to look at and fails nothing on its
own; it supports a judgement rather than replacing one.

---

### T-027 — Reject unsafe stored window geometry

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged via PR #7. `T005`-era findings and `P0-R2` … `P0-R5` were reviewer-verified; the corrections to `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **accepted by the maintainer without a final re-review**. Recorded rather than implied: those four are maintainer-accepted, not reviewer-verified.
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 0 review correction
**Depends on:** `T-007`
**Relevant context:** Phase 0 finding `P0-R1`, `NFR-004`
**Affected surfaces:** `ui/main_window.py`, `tests/ui/test_main_window.py`
**Risk:** Medium — one damaged state file can prevent every subsequent application launch

#### Scope

Make window restoration honor its "never raises" contract for every TOML value and keep a
previous monitor layout from restoring the only window entirely off-screen.

#### Acceptance criteria

- TOML `inf`, values outside Qt's signed 32-bit geometry range, booleans, and huge integers
  fall back without an exception or Qt overflow warning
- Stored geometry that intersects no available screen is moved onto an available screen
- The existing round-trip remains green for ordinary negative coordinates and positive sizes
- Each new adversarial case fails against `adb25f8` before the production fix is applied

---

### T-028 — Remove undocumented cross-thread Qt access from the launch test

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged via PR #7. `T005`-era findings and `P0-R2` … `P0-R5` were reviewer-verified; the corrections to `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **accepted by the maintainer without a final re-review**. Recorded rather than implied: those four are maintainer-accepted, not reviewer-verified.
**Owner:** Reviewer / Implementer
**Priority:** Medium
**Phase:** Phase 0 review correction
**Depends on:** `T-007`
**Relevant context:** Phase 0 finding `P0-R2`, `ai/REVIEWS.md` standing Qt-threading risk
**Affected surfaces:** `tests/ui/test_app_launch.py`
**Risk:** Low — this is test reliability, but it guards the phase's real startup path

#### Acceptance criteria

- The watcher uses only Qt APIs documented thread-safe from a foreign thread; it does not
  poll `QApplication.instance()` during construction
- A failed quit request cannot silently turn into a subprocess timeout
- The launch/quit test passes repeatedly on Linux and in the Windows matrix
- The ordering proof still establishes that `window.show()` runs before the queued quit

---

### T-029 — Complete the frozen-probe negative and evidence gates

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged via PR #7. `T005`-era findings and `P0-R2` … `P0-R5` were reviewer-verified; the corrections to `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **accepted by the maintainer without a final re-review**. Recorded rather than implied: those four are maintainer-accepted, not reviewer-verified.
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 0 review correction
**Depends on:** `T-020`
**Relevant context:** Phase 0 findings `P0-R3`, `P0-R4`, `P0-R5`, `REL-001`, `ARC-002`
**Affected surfaces:** `_freeze_probe.py`, `packaging/frozen_smoke.py`, CI workflow
**Risk:** High — the probe guards recursive application launch in the distributed artifact

#### Acceptance criteria

- A temporary Windows CI mutation removes `freeze_support()`, the frozen smoke step goes red,
  and retained evidence records more than one top-level start including multiprocessing argv
- The mutation is reverted and the final Linux and Windows frozen jobs are green
- The smoke gate fails if either the parent or spawned child does not report `frozen=True`
- The raw probe log is uploaded from its actual `dist/frozen-probe.log` location, or the
  redundant raw-log upload claim is removed and `frozen-smoke.txt` is made canonical
- No temporary mutation remains in the final tree


#### Work completed — 2026-07-25

**The Windows negative proof, which had never been run.** `T-020`'s criterion required that
removing `freeze_support()` fails the frozen smoke test *on Windows*; it was only ever
exercised on Linux. Run `30186080950` removed it and pushed:

```
frozen windows-latest = failure
--spawn-probe exited 1 in 120.2s     (the child never sent its message)
top-level application starts recorded: 2
  app-start pid=3344 frozen=True argv=['--spawn-probe']
  app-start pid=1700 frozen=True argv=['--multiprocessing-fork', 'parent_pid=3344', 'pipe_handle=608']
```

That second argv is **Windows-specific** — `parent_pid`/`pipe_handle`, where Linux produced
`tracker_fd`/`pipe_handle` — so this is genuinely the Windows relaunch path and not a Linux
result restated. All four jobs went red, not just the frozen ones. Reverted in the following
commit; run `30186222977` is green on all four, and no mutation remains in the tree.

**`frozen=True` is now asserted, not printed.** The smoke test previously printed the parent's
and child's frozen state and asserted nothing about it, so it would have passed against a
source run — which proves nothing about freezing, the entire point of `T-020`.

**The raw probe log upload was silently broken.** CI requested `frozen-probe.log` at the
repository root; `frozen_smoke.py` writes it beside the artifact at `dist/frozen-probe.log`,
so the upload had been contributing nothing. Corrected, and confirmed by the negative run's
artifact, which now contains the log.

---

### T-030 — Ratify the two Phase 0 architecture additions

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged via PR #7. `T005`-era findings and `P0-R2` … `P0-R5` were reviewer-verified; the corrections to `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **accepted by the maintainer without a final re-review**. Recorded rather than implied: those four are maintainer-accepted, not reviewer-verified.
**Owner:** Planner
**Priority:** Medium
**Phase:** Phase 0 review correction
**Depends on:** `T-007`, `T-020`
**Relevant context:** Phase 0 finding `P0-R6`, `ARCHITECTURE.md` §4 and §5
**Affected surfaces:** `ai/ARCHITECTURE.md`
**Risk:** Low — the implementations are reasonable; the canonical ownership map is incomplete

#### Acceptance criteria

- §5 assigns ephemeral window geometry to the UI and records
  `user_config_dir/tracksandtrails/window.toml`
- §4 or §12 records `_freeze_probe.py` as frozen-build diagnostic infrastructure outside the
  product layers and explains why it must share the real entry point
- The changes ratify current behavior without broadening product scope or creating a routine
  `DECISIONS.md` completion entry

---

### T-031 — Correct OPS-004 before deciding it

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged via PR #7. `T005`-era findings and `P0-R2` … `P0-R5` were reviewer-verified; the corrections to `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **accepted by the maintainer without a final re-review**. Recorded rather than implied: those four are maintainer-accepted, not reviewer-verified.
**Owner:** Planner / Maintainer + Reviewer (`ai/TESTING.md`)
**Priority:** High
**Phase:** Phase 0 review correction
**Depends on:** none
**Relevant context:** Phase 0 finding `P0-R7`, `OPS-003`, proposed `OPS-004`, `T-026`
**Affected surfaces:** `ai/DECISIONS.md`, `ai/TASKS.md` (`T-026`), `ai/TESTING.md`
**Risk:** Medium — an omitted verification category could disappear when the manual gate shrinks

#### Acceptance criteria

- Native file dialogs, reveal-in-file-manager, and open-file behavior are explicitly assigned
  to automation or retained manual verification; they do not disappear between `OPS-003` and
  `OPS-004`
- `T-026` distinguishes a retained screenshot from a red/green layout assertion and does not
  claim that a visible mutation fails the suite unless an objective assertion actually does
- The manual list shrinks only after each replacement automation has landed
- After those corrections, the maintainer accepts or rejects `OPS-004` explicitly

---

### T-032 — Reconcile Phase 0 current-truth documents

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged via PR #7. `T005`-era findings and `P0-R2` … `P0-R5` were reviewer-verified; the corrections to `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **accepted by the maintainer without a final re-review**. Recorded rather than implied: those four are maintainer-accepted, not reviewer-verified.
**Owner:** Planner + Reviewer (`ai/TESTING.md`)
**Priority:** Medium
**Phase:** Phase 0 review correction
**Depends on:** `T-027` through `T-031`
**Relevant context:** Phase 0 finding `P0-R8`, `AGENTS.md` §6
**Affected surfaces:** `ai/STATUS.md`, `ai/TASKS.md`, `ai/TESTING.md`
**Risk:** Low — stale navigation and exact counts misstate what is implemented and reviewed

#### Acceptance criteria

- `STATUS.md` no longer asks to merge completed work, call completed tasks "in review", or
  describe the replaced placeholder `app.run`
- Exact source counts are recomputed rather than copied; at `adb25f8` there are 31 Python
  modules, 26 docstring-only stubs, and 5 modules with code
- `TASKS.md` headings agree with task statuses, and the exit-review next step is current
- `TESTING.md`'s status note acknowledges resource, layering, and shell-window tests while
  retaining the honest boundary that only one of §7's mandatory areas is covered

---

### T-007 — Application shell window

**Status:** Complete
**Completed:** 2026-07-25. **The Codex review was waived by the maintainer**, who authorized
the merge to unblock `T-020`. Recorded rather than implied: unlike `T-003`, `T-006` and
`T-005`, this task received **no independent review at all** — not a waived re-review after
findings, but no first pass. `AGENTS.md` §3 requires review by a different agent; that did not
happen here. The Windows config-directory bug below was caught by CI, not by review, and a
reviewer would plausibly have found more.
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 0
**Depends on:** `T-001`, `T-003`
**Relevant context:** `ARCHITECTURE.md` §4, `NFR-002`, `NFR-005`
**Affected surfaces:** `app.py`, `ui/main_window.py`, `resources/`
**Risk:** Low
**Required checks:** default suite; manual launch on both platforms

#### Scope

A `QApplication` and `MainWindow` that opens with the app icon and title, has a menu bar with
File → Quit and Help → About, restores window geometry, and shuts down cleanly with no
warnings on stderr. No download functionality.

#### Acceptance criteria

- Launches and exits cleanly on Linux and Windows with a zero exit code and no Qt warnings
- App icon appears in the title bar, taskbar, and About dialog on both platforms
- Geometry persists across restarts
- Cold start under 3 seconds on the reference machine (`NFR-002`, measured and recorded)
- A `pytest-qt` test constructs and closes the window offscreen

#### Out of scope

- Queue view, settings, theming (Phase 4), any yt-dlp interaction

#### Implementation record — 2026-07-25

**Delivered:** `ui/main_window.py` (menu bar, About box, geometry), `app.py` (`QApplication`
setup, argument handling, event loop), `tests/ui/test_main_window.py` (17 cases),
`tests/ui/test_app_launch.py` (4 cases, subprocess). Suite 154 passed, 1 deselected.

**Two consequences this task forced that its text did not mention.**

1. **`ARCHITECTURE.md` §5's data-ownership table has no row for window geometry.** §5 assigns
   `settings.toml` to `core/settings.py`, which does not exist and is not this task's to
   build. Geometry is not a user setting — nobody edits it deliberately and losing it costs
   nothing — so it went to its own `user_config_dir/tracksandtrails/window.toml`, consistent
   with `DAT-001` (TOML, `platformdirs`, inspectable) and leaving the real settings layer
   free to arrive without a migration. **Reported, not decided:** §5 needs a row for window
   state, which is a Planner call.
2. **`test_module_entry_point_runs_and_exits_zero` could not survive a real window.** It ran
   `python -m tracks_and_trails` and expected exit 0; with a GUI it blocked until the 60 s
   timeout. `app.py`'s placeholder anticipated this ("unused until `T-007` parses
   arguments"), so `run` now handles `--version` and `--help` **before** constructing a
   `QApplication` — they must work with no display — and the test uses `--version`.

**Acceptance criteria:**

| Criterion | Evidence |
|---|---|
| Launches and exits cleanly, zero exit code, no Qt warnings | Verified under a **real Wayland session**: exit 0, stderr exactly 0 bytes |
| App icon in title bar and About dialog | `QIcon` from `icon.ico`, all seven frames asserted; About box screenshotted |
| Geometry persists across restarts | Round-trip test, plus a subprocess launch/quit confirming the file is written |
| Cold start under 3 s (`NFR-002`), measured and recorded | **median 0.178 s**, min 0.146, max 0.181, 10/10 runs on the reference machine |
| `pytest-qt` test constructs and closes offscreen | `test_window_constructs_and_closes_offscreen` |

**The "no Qt warnings" criterion needed care.** Headless runs emit `This plugin does not
support propagateSizeHints()`. Rather than relax the assertion, this was traced: it comes from
the `offscreen` and `minimal` plugins, reproduces with a bare `QMainWindow` plus a menu bar
and no project code, and does **not** occur under a real platform plugin, where stderr is
empty. It is allowlisted by exact string so the check still fails on anything else.

**A Qt threading defect in the test harness, found and fixed.** The first launch harness
polled `topLevelWidgets()` and `isVisible()` from a watcher thread — the "Qt object touched
off the GUI thread" violation in `ai/REVIEWS.md`'s standing risk list. It was intermittently
unreliable: 2 of 8 runs never saw the window and one took 18 s. The harness now touches only
`QApplication.instance()` and the thread-safe `QMetaObject.invokeMethod(..., QueuedConnection)`,
relying on `run` calling `show()` before `exec()` for ordering. 10/10 clean afterwards. The
instability was the harness, never the application.

**A Windows-only production bug, caught by CI on the first run.** `user_config_dir(APP_SLUG)`
inserts an author segment on Windows, defaulting it to the app name, so the real config path
would have been `%APPDATA%\tracksandtrails\tracksandtrails\` — a doubled directory that does
not match `ARCHITECTURE.md` §5. Invisible on Linux, where the call is identical either way.
Fixed with `appauthor=False` and pinned by `test_config_directory_is_not_doubled`, which
asserts the shape rather than the platform-specific string.

The same CI run also exposed a defect in the test that found it: `run_headless` redirected
platformdirs by setting `XDG_CONFIG_HOME`, `APPDATA` and `LOCALAPPDATA`, but platformdirs
resolves Windows folders through `SHGetKnownFolderPath` via ctypes and ignores `APPDATA`
entirely. The Windows job was therefore writing to the runner's real profile. It now uses
platformdirs' documented `WIN_PD_OVERRIDE_*` variables. **This is precisely the `OPS-003`
case for CI**: neither fault was observable on the development machine.

**Known-unverified.** Whether the icon appears correctly in the **Windows** taskbar and title
bar, and how the About box renders there, are not automatable and remain `OPS-003` gaps —
CI proves the assets load and the window constructs, not that they look right. Cold start was
measured on Linux only; `NFR-002` names the reference Linux machine, so this is complete as
specified, but Windows startup time is unmeasured.


#### Re-review corrections — 2026-07-25

**`P0-R1`, the fix was incomplete and its test enshrined the gap.** Validating each of the
four numbers against int32 was not enough: `QRect` computes `right()` and `bottom()` as
`x + width - 1`, and Qt's `intersects()` normalises internally. At `y = 2**31 - 1`, `bottom()`
wrapped to **-2147483170**, so an off-screen rectangle was reported as touching a screen, the
recovery never fired, and the window was restored where it could never be clicked. At
`x = -2**31` the same thing happened through a different overflow, even with both edges
representable.

`test_int32_boundary_values_are_accepted` asserted precisely those values were acceptable —
and only exercised `load_geometry`, so it could not see damage that happened *after* loading
succeeded. It has been replaced by `test_extreme_coordinates_never_strand_the_window`, which
asserts on the **restored** geometry across six extreme inputs.

Rather than chase which Qt operation overflows where, stored coordinates are now bounded to
`_MAX_COORD` (`2**24 - 1`), matching Qt's own `QWIDGETSIZE_MAX`. No real display arrangement
approaches 16.7 million pixels, and inside that range none of Qt's geometry arithmetic can
wrap. `test_the_largest_usable_coordinate_still_round_trips` guards against the bound being
tightened so far that legitimate multi-monitor offsets are discarded.

**`P0-R6`** — the contradiction was introduced by the previous fix. §4 listed the module while
§12 and its docstring both said it was outside §4. Corrected everywhere to the accurate
statement: it is listed in §4's structure and belongs to none of the four **layers**.

**`P0-R7`** — `T-026`'s closing note claimed every criterion was a failing mutation, while the
criteria themselves had just been corrected to make screenshots evidence-only. The note now
separates **gates** (focus order, accessibility names and roles, installer placement — each a
mutation that must turn the suite red, and only these may retire a manual item) from
**retained evidence** (screenshots, which fail nothing on their own). `OPS-004` remains
formally **Proposed**; accepting it is the maintainer's call and is surfaced in `STATUS.md`.

**`P0-R8`** — eight heading/status mismatches, now zero, verified by a script rather than by
reading. `STATUS.md` said seven findings where there were eight, claimed `main` was the only
branch while PR #7 was open, and still called `T-005` and `T-007` "in review" after both had
merged.

---

### T-020 — Frozen-build smoke test in CI

**Status:** Complete
**Completed:** 2026-07-25 — merged to `main` as part of `564aad0`; **no independent review**, pending the Phase 0 exit review
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 0
**Depends on:** `T-006`, `T-007`
**Relevant context:** `REL-001`, `REQ-029`, `ARC-002`, `ARCHITECTURE.md` §3 and §12, `ai/TESTING.md` §8
**Affected surfaces:** `__main__.py`, PyInstaller spec, CI workflow
**Risk:** **High** — the failure this guards against does not exist until the app is frozen, and
it is a recursive application launch, not a subtle misbehavior

#### Scope

Prove during Phase 0 that the `ARC-002` process model survives freezing, rather than
discovering otherwise at Phase 5 with the whole app built on top of it.

Add `multiprocessing.freeze_support()` as the first statement of `__main__.py`. Add a minimal
PyInstaller build producing a one-dir artifact of the Phase 0 shell window plus a trivial
worker that spawns a child process, exchanges one protocol message, and exits. Run that build
and its launch in CI on Linux and Windows.

This does **not** attempt real packaging — no installer, no ffmpeg bundling, no icons, no
signing. It answers one question: does spawning a child process from a frozen binary work, or
does it relaunch the application?

#### Acceptance criteria

- `multiprocessing.freeze_support()` is the first statement in `__main__.py`, with a comment
  citing `REL-001` so it is not "cleaned up" later
- CI builds a frozen artifact on Linux and Windows
- The frozen artifact launches, spawns a worker, receives one message, and exits zero
- **Exactly one** top-level application process exists during the run — asserted, not
  eyeballed. Removing `freeze_support()` must fail this test on Windows.
- No orphaned process survives exit on either platform
- Build and run complete inside the `T-006` ~10 minute CI budget, or the frozen job runs
  separately and its runtime is recorded

#### Out of scope

- Installers, ffmpeg bundling, icons, signing, size optimization — all Phase 5
- Qt dynamic-linking verification (Phase 5 release gate)
- The `OPS-002` wheel-extraction updater — Phase 4, though it shares this constraint

#### Implementation record — 2026-07-25

**Delivered:** `_freeze_probe.py` (spawn probe and start marker), `packaging/tracks-and-trails.spec`
(minimal one-dir PyInstaller build), `packaging/frozen_smoke.py` (runs the artifact and
asserts), a `--spawn-probe` argument, and a separate `frozen` CI job on both platforms.
`psutil` added as a dev-only dependency for the orphan check (`AGENTS.md` §7: no `DECISIONS`
entry needed).

**`freeze_support()` was already correct.** `T-001` placed it as the first executable statement
of `__main__.py` with a comment citing `REL-001`, ahead of any Qt import. This task verified
that placement rather than making it.

**A separate CI job, not extra steps on `check`.** The build dominates the test suite, and
folding it in would hide that cost inside `T-006`'s ~10 minute budget. The task permits this
provided the runtime is recorded, which the job does explicitly.

**The detection method was wrong on the first attempt, and the negative test is what found
it.** `run_probe` originally wrote the "application started" marker itself, on the reasoning
that a relaunched child would re-enter the same path. It does not: a relaunched child inherits
*multiprocessing's* argument vector, not the parent's, so it never reaches `--spawn-probe`.
Removing `freeze_support()` and rebuilding produced a genuine recursion while the marker count
stayed at 1 — the assertion would have passed through exactly the failure it exists to catch.
The marker now lives in `main()`, which every top-level start reaches.

**Negative test, on Linux.** With `freeze_support()` commented out and the artifact rebuilt,
the probe exits **1** and the log records **three** top-level application starts instead of
one. The `argv` column names the mechanism outright:

```
app-start pid=110766 frozen=True argv=['--spawn-probe']
app-start pid=110768 frozen=True argv=['--multiprocessing-fork', 'tracker_fd=7', 'pipe_handle=9']
app-start pid=110767 frozen=True argv=['-B','-S','-I','-c','from multiprocessing.resource_tracker import main;main(6)']
```

Those second and third lines are multiprocessing's internal invocations being executed as the
whole application. `T-020` predicted this would fail "on Windows"; it fails on **Linux too**,
which is a better outcome than the task assumed — the guard is not Windows-specific.

**Positive result, Linux:** frozen artifact 284 MB, `--version` in 0.1 s, `--spawn-probe`
exits 0 in 0.3 s, exactly one top-level start, both parent and child report `frozen=True`, no
orphan. Build 15 s locally.

**Deliberate deviation, reported.** `_freeze_probe.py` belongs to none of
`ARCHITECTURE.md` §4's four layers (it is listed in §4's structure and described in §12 as
frozen-build infrastructure). It is underscore-prefixed to mark it as infrastructure rather than a layer, imports
no Qt so a spawned child inherits none, and is reachable only through an explicit argument.
The alternative — a separate frozen entry point — would not have tested `__main__.py`'s
ordering, which is the only thing that matters here. `--spawn-probe` is listed in `--help`
rather than hidden.

**Windows is unverified until this runs in CI**, which is the whole point of the job
(`OPS-003`).

---

### T-025 — Phase 0 exit preparation

**Status:** Complete
**Completed:** 2026-07-25 — merged to `main` as part of `564aad0`; **no independent review**, pending the Phase 0 exit review
**Owner:** Implementer + Documentation Maintainer
**Priority:** High
**Phase:** Phase 0
**Depends on:** `T-007`, `T-020`
**Relevant context:** `IMPLEMENTATION_PLAN.md` Phase 0 exit criteria, `OPS-003`
**Affected surfaces:** `docs/DEVELOPMENT.md`
**Risk:** Low

#### Scope

Discharge the Phase 0 exit criteria that are not any single task's responsibility: bring
`docs/DEVELOPMENT.md` back in line with what the code now does, and re-run the clean-checkout
verification the exit criteria require, which has not been done since `T-001` — before the
window existed.

#### Acceptance criteria

- `docs/DEVELOPMENT.md` describes the application as it is, and every command in it is
  verified to work verbatim from a clean checkout
- The four gates pass from a checkout containing only git-tracked files
- The window launches and exits cleanly from that checkout on Linux
- Windows remains explicitly unverified (`OPS-003`), not quietly assumed

#### Out of scope

- The Windows interactive launch, which needs a real Windows session and blocks first release
- The Phase 0 exit review itself, which is Codex's

#### Implementation record — 2026-07-25

**Stale documentation corrected.** `docs/DEVELOPMENT.md` still said "It prints a version
banner and exits 0. There is no window yet — that is `T-007`." `T-007` had shipped, so the one
file the exit criteria name as the thing to follow was describing an application that no
longer existed. It now documents `--version` and the real window, the frozen build (`T-020`),
and `packaging/` and `_freeze_probe.py` in the layout.

**Clean-checkout verification, from 73 git-tracked files only** — no `.venv`, no `.git`, no
caches, no egg-info. Following the document verbatim:

| Step | Result |
|---|---|
| `python3 -m venv .venv`, `pip install -e ".[dev]"` | installed cleanly |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 58 files already formatted |
| `mypy` | Success: no issues in 44 source files |
| `pytest` | 158 passed, 1 deselected |
| `python -m tracks_and_trails --version` | `0.1.0.dev0`, exit 0 |
| `python -m tracks_and_trails` | window opened and exited 0, **stderr 0 bytes**, geometry written at the 960×640 default |
| `pip install -e ".[dev,build]"` + the documented PyInstaller invocation | built |
| `python packaging/frozen_smoke.py dist/tracks-and-trails` | OK: one top-level start, no orphan |

Every command in the document was executed as written rather than read for plausibility.

**Phase 0 exit criteria standing after this:**

| Criterion | Standing |
|---|---|
| Gates pass locally and in CI | **Met** |
| Layering test fails on a deliberate `core/` Qt import | **Met** (`T-005`, five real injections) |
| Window launches from a clean checkout on **Linux** | **Met** — above |
| Window launches from a clean checkout on **Windows** | **NOT met.** Blocked by `OPS-003`; needs a real Windows session. CI proves it constructs offscreen and that the frozen artifact runs, which is not the same claim. |
| Frozen artifact spawns without relaunching, both platforms | **Met** (`T-020`) |
| `LIC-001` Accepted and `LICENSE` exists | **Met** (`T-004`) |

Phase 0 cannot be declared fully exited on the letter of its own criteria until someone
launches the window on Windows. That is the same gap `OPS-003` records and `ai/TESTING.md` §9
lists as blocking first release; it is not newly discovered here, and everything automatable
around it is done.

---

### T-005 — Layering enforcement test

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged as `d1f45e5` via PR #2
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 0
**Depends on:** `T-001`
**Relevant context:** `ARCHITECTURE.md` §4, `AGENTS.md` §7 (Layering), `ai/TESTING.md` §7
**Affected surfaces:** `tests/unit/test_layering.py`
**Risk:** Low — but its absence lets the central architectural rule erode invisibly

#### Scope

Statically analyze the import graph (via `ast`, not by importing) and assert:
`core/**` and `downloader/worker.py` never import `PySide6`/`shiboken6`;
`ui/**` never imports `yt_dlp`; only `downloader/worker.py` and
`downloader/ytdlp_adapter.py` import `yt_dlp` at all.

#### Acceptance criteria

- The test passes on the current tree
- Adding `import PySide6` to any `core/` module fails it, with a message naming the file and
  the rule
- Adding `import yt_dlp` to a `ui/` module fails it
- Uses static analysis — importing modules to check would defeat the purpose and could
  execute side effects

#### Out of scope

- Enforcing anything beyond the two rules in `ARCHITECTURE.md` §4

#### Implementation record — 2026-07-25

**Delivered:** `tests/unit/test_layering.py`, 45 tests. Static `ast` analysis, no imports
executed — importing to inspect `sys.modules` would run module-level code, and a module
importing Qt lazily inside a function would pass while still breaking the frozen worker.

**Four rules, not two.** This task's Scope enumerates four checks while its Out of scope line
says "the two rules in `ARCHITECTURE.md` §4". Read as: implement the enumerated four, and do
not invent a fifth. All four are stated in the linked context — §4's diagram gives the two
headline rules, §4's bullets add "`worker.py` … never Qt", and §6 with `NFR-008` confines
`yt_dlp` to two modules. Flagged rather than silently resolved.

**A documentation imprecision, not a conflict.** §4's structure block calls `worker.py` "the
ONLY module that calls `yt_dlp`", while §6 permits both `worker.py` and `ytdlp_adapter.py` to
import it. These are consistent if "calls" is read as §6's "the only place `YoutubeDL` is
instantiated". The test follows §6, which is explicit. Not worth a task; noted so the next
reader does not have to re-derive it.

**Verification — five real violations injected into the actual tree**, each confirmed to fail
with a message naming both the file and the rule, then reverted with `src/` hashed before and
after to prove restoration:

| Injected | Caught by |
|---|---|
| `import PySide6` in `core/models.py` | core/ must not import Qt |
| `from PySide6.QtCore import QObject` in `core/job_state.py` | core/ must not import Qt |
| `import yt_dlp` in `ui/main_window.py` | both the `ui/` rule and the two-owner rule |
| `import PySide6` in `downloader/worker.py` | worker.py must not import Qt |
| `import yt_dlp` in `persistence/db.py` | only `worker.py` and `ytdlp_adapter.py` may import yt-dlp |

**The guard is itself guarded.** `ai/REVIEWS.md` names layering as an area where "the
enforcement test can be weakened as easily as bypassed" — narrowing a rule's `applies_to` or
dropping a package from `forbidden` leaves the tree passing and nothing else notices. Thirteen
synthetic cases assert the analyzer still catches what it must and still permits what the
architecture allows; a `test_source_tree_is_not_empty` guard catches the glob silently
matching nothing.

**Known limit, stated in the module docstring rather than left implicit:** only `import`
statements are analyzed. `importlib.import_module("PySide6")` and `__import__` are not
detected. Accepted, not overlooked — a dynamic import of Qt is conspicuous in review in a way
a plain one is not.

**Checks:** `ruff check`, `ruff format --check`, `mypy src`, and `pytest` all green.

#### Review corrections — 2026-07-25

**`T005-R1`, High — the analyzer's self-protection was routed around.** The finding is
correct and it is the exact failure the original design claimed to prevent. The synthetic
cases asserted the analyzer's behavior at a handful of *hardcoded paths*, so narrowing the
`core/` predicate to those same paths left all 45 tests green, as did adding
`downloader/environment.py` as a third yt-dlp owner. The guard was checking itself against its
own examples rather than against the architecture.

Fixed by stating the architecture a second time, independently. `architecture_forbids()`
derives what a file may not import straight from its path, sharing no constant or predicate
with `RULES`, and `test_every_module_is_actually_guarded` sweeps **every real module** in the
tree asserting the analyzer would catch every package the architecture forbids there. A
literal `ARCH_YTDLP_OWNERS` is compared against `YTDLP_OWNERS`, so widening the allowlist
fails rather than silently permitting a third importer. Two statements that must agree cannot
be routed around by editing one.

Verified by reproducing the reviewer's two bypasses and two more:

| Weakening | Result |
|---|---|
| Narrow the `core/` predicate to `core/models.py` + `core/paths.py` | **fails** — every other `core/` module reported as an enforcement hole |
| Add `downloader/environment.py` as a third yt-dlp owner | **fails** twice — allowlist mismatch, and `environment.py` unguarded |
| Drop `shiboken6` from `QT` | **fails** — `shiboken6` uncaught across `core/` |
| Make `check()` return `[]` unconditionally | **fails** — 36 of 76 |

**`T005-R2`, Low — the static test imported the package under test.** Correct and
self-contradictory: locating `SRC` via `import tracks_and_trails` executed its `__init__` and
bound the analysis to whichever copy was installed rather than this checkout. `SRC` is now
derived from `Path(__file__)`, so the module imports nothing from the package it analyzes.

**`T005-R3`, Low — stale current truth.** `STATUS.md` still said nothing in `TESTING.md` was
implemented. Rewritten to separate the two claims that had been conflated: no application
*behavior* exists, which remains true and is the warning worth keeping, while the *scaffolding*
that guards it does — CI, asset invariants, and this test.

**Suite:** 103 passed, 1 deselected (was 27 before `T-005`, 72 at first review).

---

### T-024 — Close T-005 review findings

**Status:** Complete
**Completed:** 2026-07-25. **The focused re-review was waived by the maintainer**, who
authorized the merge after two review rounds on `T-005`. Recorded rather than implied: the
acceptance criterion "`T005-R1` through `T005-R3` receive focused re-review" was **not** met
for this second pass. The set-equality fix and the `STATUS.md` module count are therefore
maintainer-accepted, not reviewer-verified.
**Owner:** Implementer (test correction) + Planner (coordination correction)
**Priority:** High
**Phase:** Phase 0
**Depends on:** `T-005`
**Relevant context:** `ai/REVIEWS.md` findings `T005-R1` through `T005-R3`;
`ARCHITECTURE.md` §4 and §6
**Affected surfaces:** `tests/unit/test_layering.py`, `ai/STATUS.md`
**Risk:** **High** — a green layering guard can be weakened around its sampled fixtures

#### Scope

Make the analyzer's self-tests pin the complete architectural rule definitions rather than
sample paths. Keep source discovery static and rooted in the repository without importing the
package under test. Correct the stale blanket statement in `STATUS.md` that nothing in
`TESTING.md` is implemented.

#### Acceptance criteria

- Narrowing the core rule to the currently sampled `core/models.py` and `core/paths.py` makes
  the suite red
- Adding any third existing module to `YTDLP_OWNERS` makes the suite red
- Dropping `shiboken6`, emptying `YTDLP_OWNERS`, or making `check()` return `[]` makes the
  suite red
- Adding an architecture-allowed package such as `typing` to a forbidden set, or widening a
  rule onto a layer where that package is allowed, makes the suite red
- The five real-tree violation probes from `T-005` still fail with the offending file and
  rule in the message, and the source tree is restored byte-for-byte
- The test locates and parses the repository source tree without importing
  `tracks_and_trails`; every Python module under that tree is swept
- `STATUS.md` accurately distinguishes the implemented `T-001` entry-point scaffold,
  implemented test infrastructure, and approved future application behavior
- The default suite and Linux/Windows matrix are green
- `T005-R1` through `T005-R3` receive focused re-review

#### Out of scope

- Detecting dynamic `importlib.import_module()` or `__import__()` calls
- Changing the layer boundaries or adding a fifth rule

#### Work completed — 2026-07-25

**Pass 1** closed the false-negative half of `T005-R1` (an independent
`architecture_forbids()` plus a real-tree sweep), `T005-R2` (source discovery via
`Path(__file__)`, importing nothing), and the blanket half of `T005-R3`.

**Pass 2 — the one-way comparison.** Re-review found the fix proved only that *required*
prohibitions exist, never that no *surplus* ones had been added: putting `typing` into `QT`
left all 76 tests green. Required-only agreement is not agreement.

`test_every_module_is_guarded_no_more_than_the_architecture_requires` now asserts set
**equality** between what `RULES` reject and what `ARCHITECTURE.md` forbids, per module, in
both directions. Surplus prohibitions matter as much as missing ones: a rule that rejects
legitimate code gets loosened or deleted by whoever it blocks, taking the real protection
with it.

**Pass 2 — `T005-R3`.** The claim "not one module in §4's structure has an implementation"
was still false: `__main__.py` and `app.py` carry `T-001`'s entry-point scaffold. Counted
rather than estimated — of 30 modules under `src/`, **27 are docstring-only stubs** and three
hold code (`__init__.py`, `__main__.py`, `app.py`, all `T-001`). `STATUS.md` now says exactly
that.

**Every weakening in `T-024`'s acceptance criteria, probed and reverted:**

| Weakening | Suite |
|---|---|
| Add `typing` to `QT` | 8 failed |
| Add `typing` to `YTDLP` | 28 failed |
| Widen the Qt rule onto `downloader/`, where Qt is allowed | 7 failed |
| Widen the Qt rule onto `ui/`, where Qt is allowed | 10 failed |
| Narrow `core/` to the two sampled files | 10 failed |
| Add a third `YTDLP_OWNERS` entry | 3 failed |
| Empty `YTDLP_OWNERS` | 5 failed |
| Drop `shiboken6` | 17 failed |

The five real-tree violation probes still fail with the file and rule named, and `src/` was
hashed before and after: byte-identical. Suite 133 passed, 1 deselected.

---

### T-006 — CI on Linux and Windows

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged as `c8a72b8` via PR #1; CI green on `main`
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 0
**Depends on:** `T-001`
**Relevant context:** `ai/TESTING.md` §10, `REQUIREMENTS.md` §3, `C-003`, **`OPS-003`**
**Affected surfaces:** CI workflow config
**Risk:** **High** — per `OPS-003` this is the *only* Windows environment that exists. Anything
it does not check is genuinely unverified on Windows, not merely unautomated.

#### Scope

A matrix workflow on Linux and Windows running lint, format check, mypy, and the default
pytest suite on the `T-002` baseline. UI tests run with `QT_QPA_PLATFORM=offscreen`. Network
tests excluded.

This is deliberately **larger than a standard lint-and-test pipeline**. Because there is no
Windows machine (`OPS-003`), CI carries verification load that manual testing would normally
carry, so treat the automatable list in `OPS-003` as this task's real target and extend the
workflow toward it as those features arrive in later phases.

#### Acceptance criteria

- Both platforms run green on push and pull request
- A deliberate lint error and a deliberate test failure each turn CI red (verified once, then reverted)
- UI tests pass headless on both runners
- **Carried from `T-002`:** on the Windows runner, PySide6 installs, `import PySide6` works,
  and a `QApplication` + `QWidget` constructs offscreen on the pinned baseline. `T-002`
  verified this on Linux only; CI is the only place it can be confirmed for Windows
  (`OPS-003`).
- **Carried from `T-003`:** `tests/ui/test_resources.py` passes on the Windows runner — every
  asset non-null through `QIcon`, and `icon.ico` reporting all seven embedded sizes. The test
  exists (added by `T-022`) and passes on Linux; CI is the only place it can be confirmed for
  Windows (`OPS-003`).
- Windows runner artifacts (logs, failure output, screenshots when added) are retained and
  downloadable — with no local Windows machine, CI output is the only debugging evidence
  available for Windows failures
- Total run under ~10 minutes

#### Out of scope

- Release/packaging pipelines (Phase 5), coverage gates, network tests
- The frozen build — that is `T-020`

#### Implementation record — 2026-07-25

**Delivered:** `.github/workflows/ci.yml` and `.github/scripts/qt_baseline.py`; `reports/`
added to `.gitignore`.

The workflow encodes two `OPS-003` consequences rather than leaving them to convention.
`fail-fast: false`, so a Linux failure can never cancel the Windows job — Windows evidence is
the scarce resource. Evidence uploads `if: always()`, so a failed Windows job still yields a
downloadable record of this project's own gates. That artifact is not the whole record:
checkout, `setup-python`, apt, and pip all run before `reports/` exists, and a failure in
those is available only through the Actions job log. `ai/TESTING.md` §10 tabulates which
source covers what. Concurrency cancels superseded runs, since Windows minutes bill at 2×
against a private repository's allowance.

`qt_baseline.py` is deliberately **not** a pytest test. It answers whether the Qt stack works
at all on the runner, which is the question worth asking before trusting a suite that imports
Qt: if it fails, every downstream UI failure is that same failure reported less clearly. It
asserts rather than reports — a wrong platform plugin or an invisible widget exits non-zero.

**Every acceptance criterion, with the run that evidences it.** All runs on `t-006-ci`:

| Criterion | Evidence |
|---|---|
| Both platforms green on push | `30179359072` |
| Both platforms green on pull request | `30179407050` (PR #1) |
| Deliberate lint error turns CI red | `30179263484` — both runners failed at `Lint` |
| Deliberate test failure turns CI red | `30179308976` — both runners failed at `Tests` |
| Both reverted after verification | `30179359072` is the reverted tree, green |
| UI tests pass headless on both | 27 passed on each runner under `QT_QPA_PLATFORM=offscreen` |
| **Carried from `T-002`:** PySide6 + `QApplication` on Windows | Python 3.14.6 (MSC v.1944, AMD64), PySide6 6.11.1, shiboken6 6.11.1, Qt 6.11.1, `QWidget` `visible=True` offscreen |
| **Carried from `T-003`:** `QIcon` reads all seven `.ico` frames on Windows | `test_ico_exposes_every_frame_to_qt` PASSED on `windows-latest` |
| Windows artifacts retained and downloadable | 30-day retention. Corrected after review — see below |
| Total run under ~10 minutes | Linux 37–54 s, Windows 1 m 3 s – 1 m 16 s |

**Both Windows carries are now discharged**, with artifact evidence rather than a green tick.
`T-002` and `T-003` should no longer be read as carrying unverified Windows claims.

**Two defects were caught before CI ever ran**, by executing each step's command locally
first: `QT_VERSION_STR` does not exist in PySide6 (the baseline script would have crashed on
both runners), and the actions were on the deprecated Node 20 runtime — bumped to v7.

**Assumption recorded:** the Linux job installs `libegl1 libgl1 libxkbcommon0 libdbus-1-3
libfontconfig1`. This list was derived from what the offscreen plugin links, not from a
minimality experiment; it may be broader than strictly needed. It is correct, not necessarily
minimal.

#### Review corrections — 2026-07-25

**`T006-R1`, evidence retention.** The artifact retention claim was only ever true for the
steps that happened to be piped. Lint, format, and mypy wrote to the Actions job log and
nothing else, so the artifact from the failed lint run contained `environment.txt` alone —
directly contradicting the claim that these artifacts carry failure output and are the only
Windows debugging material available under `OPS-003`. All four checks now tee into
`reports/`. The Qt baseline and pytest steps additionally gained `2>&1`: both write failure
detail to stderr, which the original pipe silently dropped, so they carried the same defect
in a less visible form.

Re-verified rather than assumed. Run `30180163074` reintroduced the lint error; the
`windows-latest` artifact now contains `lint.txt` with the full `F401` diagnostic, including
the Windows path separator in `tests\unit\test_ci_gate_check.py`, confirming it is the
runner's own output and not a replayed local result. Reverted in `30180215713`, whose passing
artifact carries all seven evidence files.

**`T006-R2`, coordination truth.** The `T-002` and `T-003` completion notes still described
their Windows checks as unverified and carried into `T-006`, while `T-006`'s own record in the
same file said those carries were discharged. `TASKS.md` is current truth (`AGENTS.md` §6), so
both notes now state the discharge and cite the evidence. `T-002`'s "explicitly still
unverified" list was also audited item by item: one item was genuinely resolved by `T-001` and
had never been marked so; the cancellation-timing item remains open and is now labeled as
such rather than sitting in an undifferentiated list.

**Not yet extended toward the rest of `OPS-003`'s automatable list** — orphaned-process
assertions, path-safety checks, artifact-install-and-launch, screenshot capture. Those depend
on behavior that does not exist yet; the task says to extend the workflow as those features
arrive, which is future-phase work rather than a gap in this one.

---

### T-023 — Close T-006 review findings

**Status:** Complete
**Completed:** 2026-07-25 — `T006-R2` closed in the first pass, `T006-R1` across two.
**The focused re-review was waived by the maintainer**, who judged three review rounds
sufficient and authorized the merge. Recorded rather than implied: the acceptance criterion
"`T006-R1` and `T006-R2` receive a focused re-review" was **not** met for the second-pass
documentation correction. That correction is therefore maintainer-accepted, not
reviewer-verified.
**Owner:** Implementer (workflow evidence) + Planner (coordination correction)
**Priority:** High
**Phase:** Phase 0
**Depends on:** `T-006`
**Relevant context:** `ai/REVIEWS.md` findings `T006-R1`, `T006-R2`; `OPS-003`
**Affected surfaces:** `.github/workflows/ci.yml`, `ai/TESTING.md`, `ai/TASKS.md`, `ai/STATUS.md`
**Risk:** Low — evidence completeness and current-truth accuracy

#### Scope

Ensure a failed lint, format, or type-check command leaves its diagnostic in the uploaded
Windows evidence rather than only in the GitHub Actions job log. Make the documentation
distinguish retained artifacts from Actions-owned logs instead of calling the artifact the
only debugging material. Update the completed `T-002` and `T-003` notes to record that their
Windows carries were discharged by `T-006`.

#### Acceptance criteria

- The controllable project gates write stdout and stderr to `reports/` while preserving their
  non-zero exit status; a locally injected lint failure proves both properties
- `if: always()` still uploads the reports on both runners, and the evidence model states
  honestly which early action/setup failures remain available only through Actions job logs
- The `T-002` and `T-003` completion notes no longer say their Windows checks are unverified
  or still carried to `T-006`; they link to the verified `T-006` evidence
- `T-006` and `STATUS.md` reflect the review outcome and subsequent correction state
- The final Linux and Windows matrix remains green
- `T006-R1` and `T006-R2` receive a focused re-review

#### Out of scope

- Re-running the already-proven lint and pytest gate experiments unless needed to validate
  the evidence-capture correction
- Adding behavior-dependent `OPS-003` checks assigned to later phases

#### Work completed — 2026-07-25

**Pass 1 — mechanism.** All four project gates now tee stdout *and* stderr into `reports/`
while preserving exit status. The Qt baseline and pytest steps also gained `2>&1`; both write
failure detail to stderr, so they carried the same defect in a less visible form than the
three steps the finding named. Proven by run `30180163074` (lint failure, both platforms red,
Windows `lint.txt` carrying the native `tests\unit\...` `F401` diagnostic) and reverted in
`30180215713` (green, all seven evidence files per artifact).

**Pass 1 — `T006-R2`.** The `T-002` and `T-003` notes now record their discharge and cite the
`T-006` evidence. `T-002`'s "explicitly still unverified" list was audited item by item rather
than only the flagged entry; a third item had been resolved by `T-001` and never marked.

**Pass 2 — the documentation half of `T006-R1`, missed in pass 1.** Fixing the mechanism while
leaving the description intact meant the docs still called the artifact the only Windows
debugging material. It is not: checkout, `setup-python`, apt, and pip all run before
`reports/` exists, and a failure in any of them is recorded only in the Actions job log.

Corrected in all four places — `.github/workflows/ci.yml` (header and the tee comment),
`ai/TESTING.md` §10, and the `T-006` implementation record. `ai/TESTING.md` §10 now carries a
table stating which source covers what and with what retention, since that is the policy home
and the other three should point at it rather than restate it. `ai/REVIEWS.md` was left
untouched: it is a historical record (`AGENTS.md` §6), and its finding text quoting the old
wording is evidence of what was found, not a claim to be corrected.

**Standing distinction, recorded so it is not re-flattened:** the Actions job log is the
complete record and the only source covering the setup steps; the `reports/` artifact covers
this project's own gates and is the part that can be analyzed offline. Neither replaces the
other, and only the second is ours to control.

---

### T-022 — Close T-003 review findings

**Status:** Complete
**Completed:** 2026-07-25 — focused re-review approved; `T003-R1`, `T003-R2`, `T003-R3` all
Resolved, no new findings
**Owner:** Planner (documentation correction) + Implementer (resource test)
**Priority:** High
**Phase:** Phase 0
**Depends on:** `T-003`
**Relevant context:** `ai/REVIEWS.md` findings `T003-R1` through `T003-R3`
**Affected surfaces:** `ai/ARCHITECTURE.md` §8, the `T-003` completion note, resource tests
**Risk:** Low — documentation accuracy and regression coverage for a fixed asset set

#### Scope

Make the palette evidence reproducible or describe the three hex values honestly as adopted
brand swatches rather than uniquely derived measurements. Correct the `T-003` completion note
so its status agrees with the review's judgment that the 16 px criterion is met narrowly, with
`T-021` retained as an optional visual improvement. Add a default-suite resource test for the
delivered PNG and ICO invariants.

#### Acceptance criteria

- The palette table either links to a deterministic algorithm whose radius-40 output matches
  every published hex and share, or drops the measurement-dependent shares and labels the
  hexes as the canonical swatches selected from the source artwork
- The `T-003` completion note no longer says a completed task left its 16 px acceptance
  criterion unmet; it preserves the marginal visual result and the rationale for `T-021`
- A default-suite test fails when a required PNG is missing or has the wrong dimensions, and
  fails when `icon.ico` is null or does not report 16/24/32/48/64/128/256 through `QIcon`
- The test passes on Linux offscreen; `T-006` runs the same assertion on Windows
- `T003-R1`, `T003-R2`, and `T003-R3` receive a focused re-review

#### Out of scope

- Changing the artwork, choosing new brand colors, implementing `T-021`, or consuming the
  icon in the application shell (`T-007`)

#### Work completed — 2026-07-25

**`T003-R1` — palette evidence.** Took the second option: the shares are gone and the hexes
are labeled adopted canonical swatches in `ARCHITECTURE.md` §8. No deterministic algorithm was
supplied because none exists to supply — the artwork has no flat fills, every colored region
is a cloud spanning roughly ±2 per channel, so the modal color is as unstable as the cluster
center (the gold's two most frequent exact values, `#D8A14C` and `#D8A24C`, are within 1.07%
and 0.94% of opaque pixels of each other). §8 now says so explicitly and forbids re-deriving
the values. **The three hex values are unchanged** — only the claim about them. The source
master's SHA-256 is recorded there as the provenance anchor (`T003-R5`).

**`T003-R2` — task truth.** The review's reading is adopted: the criterion is narrowly met.
The `T-003` note now says so, keeps the marginal 16 px assessment verbatim, and states that
`T-021` blocks nothing. `T-021` was itself reworded — it had inherited the overstated premise
that the trail collapses, and its acceptance criterion "distinguishable from a generic green
square" was already satisfied by the current asset, making it unfalsifiable. It now requires a
side-by-side improvement over the existing downscale.

**`T003-R3` — test coverage.** `tests/unit/test_resources.py` (11 assertions, stdlib only —
PNG `IHDR` and `.ico` directory parsing, since the project has no image library and adding one
for a test is not worth it) and `tests/ui/test_resources.py` (12 assertions through `QIcon`,
using pytest-qt's `qapp`). `tests/ui/conftest.py` sets `QT_QPA_PLATFORM=offscreen` by default
so a plain `pytest` reproduces CI.

Negative-tested rather than assumed — each failure mode was injected, confirmed to fail the
suite, and reverted, with the asset directory hashed before and after to prove restoration:

| Injected failure | Caught by |
|---|---|
| `icon-48.png` deleted | `test_no_unexpected_files_in_the_icon_directory` |
| `icon-32.png` resized to 31×31 | `test_derived_png_exists_at_its_declared_size[32]` |
| `icon.ico` truncated to 200 bytes | `test_ico_exposes_every_frame_to_qt` |
| `icon.ico` rebuilt with only 16/32/48 | `test_ico_declares_every_required_frame` + the Qt test |
| stray `icon-99.png` added | `test_no_unexpected_files_in_the_icon_directory` |

Suite: 27 passed, 1 deselected (was 4 passed). `ruff`, `ruff format --check`, `mypy src` green.

---

### T-003 — Add the application icon asset

**Status:** Complete
**Completed:** 2026-07-25
**Owner:** Implementer (source asset supplied by Sean Kottman)
**Phase:** Phase 0
**Relevant context:** `T-007`, `ARCHITECTURE.md` §8

**Source asset:** `icon.png`, 1024×1024 RGBA, placed by the maintainer. No vector source
exists, so **no SVG was produced** — that half of the scope is not deferred, it is
unavailable. If a vector original surfaces later, regenerating from it would be an
improvement, not a correction.

**Brand swatches, adopted from the asset.** Recorded canonically in `ARCHITECTURE.md` §8:
`#1E5E47` forest green, `#D9A24C` trail gold, `#083122` deep green.

Originally published here as measurements — hexes plus a share of the logo, said to be
"exact", from clustering opaque pixels at a Euclidean radius of 40. `T003-R1` showed that was
wrong: the artwork has no flat fills, so different reasonable clusterings give different
centers and shares. Corrected by `T-022` to adopted canonical swatches with no share claims.
The values themselves did not change; the claim made about them did.

**Framing decision.** The source artwork occupies only ~9% of its canvas: a 498×743 opaque
box inside 1024×1024, padded 260 left / 192 top / 266 right / 89 bottom — horizontally
centered but sitting low. Scaled as-is, a 16 px icon would carry roughly 8×12 px of actual
artwork. On the maintainer's instruction the derived sizes are **trimmed to the content box
and recentered in a square canvas with a 6% margin**, so the derived assets do not reproduce
the source's framing. `icon.png` is kept unmodified as the master.

**Delivered:** `icon-{16,24,32,48,64,128,256,512}.png` and `icon.ico` (embedding
16/24/32/48/64/128/256), all derived by Lanczos downsampling from an 844×844 master.
The directory's `.gitkeep` was removed, its purpose discharged.

**Checks run:**

| Check | Result |
|---|---|
| `.ico` embedded sizes | `[16, 24, 32, 48, 64, 128, 256]` — exceeds the required 16/32/48/256 |
| `QIcon` load, Linux offscreen | all assets non-null; `icon.ico` reports all 7 sizes to Qt |
| Visual inspection, 16–128 px | see below |
| Resource invariant tests | added by `T-022`; 23 assertions, negative-tested against five failure modes |
| `ruff`, `ruff format`, `mypy`, `pytest` | green |

**All acceptance criteria met.** The 16 px criterion — "renders correctly at 16 px without
becoming unreadable mush" — is met **narrowly**. Judged by eye at 8× nearest-neighbour zoom:

- **128/64/48 px** — fully legible; trees, mountain, trail, and note all distinct
- **32 px** — good; the note and trail read clearly, the trees begin to merge
- **24 px** — acceptable; note and gold trail read, the trees are one blob
- **16 px** — **marginal but legible.** The note and gold trail stay recognizable; only the
  landscape detail collapses. It reads as this mark, not as a green blob

The implementer first recorded 16 px as failing the criterion while still marking the task
Complete, which is a contradictory state (`T003-R2`). Independent review judged the criterion
narrowly met and that reading is adopted here. The marginal result stands as recorded — the
cause is the artwork's detail density, not the scaling — and the simplified small-size glyph
remains worth doing as an **optional enhancement, `T-021`**, which does not block this task,
`T-007`, or Phase 0 exit.

**Windows verified 2026-07-25 — carry discharged.** At completion this criterion, "loads via
Qt resources on both platforms", was confirmed on Linux only and carried into `T-006` as the
only place `OPS-003` allows it to be confirmed. `T-006` has since run it:
`test_ico_exposes_every_frame_to_qt` passed on `windows-latest`, so `QIcon` reads all seven
embedded frames there. This note is no longer an open carry.

---

### T-001 — Establish the project skeleton and toolchain

**Status:** Complete
**Completed:** 2026-07-25
**Owner:** Implementer
**Phase:** Phase 0
**Relevant context:** `ARCHITECTURE.md` §4, `ai/TESTING.md` §4, `DOC-002`

**Checks run** (Linux, from a simulated clean checkout containing only git-tracked files):

| Check | Result |
|---|---|
| `ruff check .` | All checks passed |
| `ruff format --check .` | 49 files already formatted |
| `mypy` (strict) | Success: no issues found in 37 source files |
| `pytest` | 4 passed, 1 deselected |
| `pytest -m network` | 1 passed, 4 deselected |
| `python -m tracks_and_trails` | exit 0 |
| `tracks-and-trails` (console script) | exit 0 |

**Acceptance criteria — all met.** The clean-checkout criterion was verified by extracting a
copy with no `.venv`, `.git`, caches, or egg-info, then following `docs/DEVELOPMENT.md`
verbatim; all four checks passed there.

**Delivered:** `pyproject.toml` (hatchling, src layout, `requires-python = ">=3.14"`, console
script, ruff/mypy/pytest/coverage config); the 27-module package skeleton matching
`ARCHITECTURE.md` §4, each module carrying a docstring stating its responsibility; the
four-package `tests/` tree; `docs/DEVELOPMENT.md` (`DOC-002` trigger discharged).

**Two deliberate deviations from "no behavior", both reported rather than made silently:**

1. **`__main__.py` contains `multiprocessing.freeze_support()`.** `ARCHITECTURE.md` §3 requires
   it as the first executable statement ahead of any Qt import. Creating the entry point
   without it would have committed a known-wrong file for `T-020` to discover later. `app.py`
   holds a placeholder `run()` returning 0 so the entry point resolves; `T-007` replaces it.
2. **`tests/unit/test_skeleton.py` and `tests/network/test_marker.py` exist.** A tree with no
   tests makes `pytest` exit 5 (no tests collected), so "pytest passes" would have been
   unverifiable. These test T-001's own acceptance criteria — importability, entry-point exit
   code, layer presence, marker exclusion — plus one guard that importing `__main__` pulls in
   no Qt, which is what makes the `freeze_support()` ordering meaningful.

**One mypy ignore exists**, contrary to a literal reading of the "no ignores" criterion:
`ignore_missing_imports` scoped to `yt_dlp.*`. yt-dlp ships no `py.typed` (verified), so this
is required the moment `T-012` imports it — confirmed with a throwaway probe module, since
nothing imports yt-dlp yet. It is confined to the two modules permitted to touch yt-dlp
(`ARCHITECTURE.md` §6), so the untyped surface stays small. Recorded here rather than passed
off as a clean strict run.

**Follow-ups:** `requires-python = ">=3.14"` is now recorded, closing `T-002`'s last open
item. `pyproject.toml` carries the MIT license metadata, closing `T-004`'s carried item.

---

### T-002 — Confirm the Python baseline against PySide6 wheel availability

**Status:** Complete — Linux at completion; Windows discharged by `T-006` on 2026-07-25
**Completed:** 2026-07-25
**Owner:** Implementer
**Phase:** Phase 0
**Relevant context:** `ARC-001`, `REL-001`

**Outcome: Python 3.14 is fully supported. No fallback interpreter is needed.**

Verified on Fedora 44 / x86-64, 2026-07-25, in a clean `.venv`:

| Component | Version | Note |
|---|---|---|
| Python | 3.14.6 | the machine's only interpreter |
| PySide6 | 6.11.1 | wheel is `cp310-abi3` |
| Qt runtime | 6.11.1 | `QApplication` + `QWidget` + `QTableView` construct and show offscreen |
| shiboken6 | 6.11.1 | |
| yt-dlp | 2026.7.4 | imports and extracts cleanly |
| PyInstaller | 6.21.0 | installs and imports on 3.14 — de-risks `T-020` |

**Key finding — PySide6 ships stable-ABI (`abi3`) wheels.** One `cp310-abi3` wheel serves
every Python ≥3.10, so PySide6 does *not* require a per-version wheel and the Python baseline
is not constrained by PySide6 release cadence. This removes the risk that motivated this task
and makes future interpreter upgrades cheap.

**Baseline recommendation for `T-001`: `requires-python = ">=3.14"`.** Not because older
versions would fail, but because `REL-001` freezes an interpreter into every artifact — users
never supply their own — so there is no value in claiming support for a range we do not test.
Pin to the one version actually verified.

**Bonus: `ARC-002` mechanics validated on Linux** with a throwaway probe (not committed):
spawn worked with a live `QApplication` in the parent; the child imported yt-dlp with no Qt
inherited and returned structured info (title, extractor, 33 formats) over an `mp.Queue` in
1.62 s; `terminate()` on a hung worker returned in 0.001 s with exit code -15, no orphan, and
the parent healthy. The central architectural bet behaves as designed.

**Unverified at completion, and their current standing:**

- **Resolved 2026-07-25.** Everything above was **Linux only**, with the Windows half
  transferred to `T-006` as the only Windows environment available (`OPS-003`). `T-006` has
  since run it: on `windows-latest`, Python 3.14.6 (MSC v.1944, AMD64), PySide6 6.11.1,
  shiboken6 6.11.1, Qt 6.11.1, and a `QWidget` visible offscreen. The Windows baseline is
  confirmed and this is no longer a carry.
- **Still open.** The 2-second cancellation criterion (`REQUIREMENTS.md` §11) was probed
  against a *sleeping* worker, not a real in-flight download. Real cancellation is Phase 1
  (`T-019`).
- **Resolved by `T-001`.** No `pyproject.toml` existed yet, so `requires-python` was a
  recommendation; `T-001` recorded `>=3.14`.

---

### T-004 — Decide and record the project license

**Status:** Complete
**Completed:** 2026-07-25
**Owner:** Sean Kottman (maintainer decision)
**Phase:** Phase 0
**Relevant context:** `LIC-001`, `NFR-009`, `C-004`

**Outcome:** MIT. `LIC-001` moved to Accepted with rationale; `LICENSE` written at the
repository root with the 2026 Sean Kottman copyright line; `README.md` updated.

**Remaining:** the `pyproject.toml` license field is set by `T-001`, since no
`pyproject.toml` exists yet. Shipping third-party license texts (Qt, ffmpeg, yt-dlp) with
the distribution is a Phase 5 release-gate item, not part of this task.
### T-058 — Recount the DRM coverage record

**Status:** **Complete — approved**, 2026-07-28 at `b3e156c`. `T058-R1` is Resolved on the second
correction: `ai/TESTING.md` §12 is the sole numeric full-set coverage statement in the
current-truth documents. The finding continued once because the first correction cleaned
`ai/STATUS.md` and left two statements inside the file it had just declared the single home —
the search used to verify the claim matched only the phrasing it had removed. See **Evidence**.
**Owner:** Documentation Maintainer, with the Implementer for the mutation evidence
**Priority:** Medium — the exit review reads this record, and today it is wrong
**Phase:** Phase 1
**Depends on:** nothing. `T-057` and `T-017`'s DRM criterion are what the corrected record must
**name**, not what it must wait for
**Relevant context:** `ai/TESTING.md` §7, §12, §13; `ai/STATUS.md`; the `T-044`/`T-045` lesson
**Affected surfaces:** `ai/TESTING.md`, `ai/STATUS.md`
**Risk:** Low as a diff, Medium as a claim — this record is what the exit review trusts

#### Scope

`ai/TESTING.md` §12 says "Log redaction (`T-038`) and DRM remain uncovered", and `ai/STATUS.md`
says in three places that DRM is the one uncovered mandatory area with no Phase 1 owner. Log
redaction closed with `T-038`. DRM has had tests since the worker path landed:

- `tests/unit/test_errors.py:56` — non-retryable and non-auto-retryable, asserted across the whole
  taxonomy rather than for one kind
- `tests/unit/test_ytdlp_adapter.py:422` — detection is structural, and prose *claiming* DRM is
  explicitly asserted not to be DRM
- `tests/integration/test_worker.py:351` — the bypass half, by counting extraction calls: a DRM
  item fails after exactly one, because a second would be an attempt to route around the
  protection

The claim was most likely written before `T-012` and `T-013` landed that path, and was never
recomputed. **Recount, do not adjust** — that is the discipline that caught `STATUS.md`'s stale
module counts, and the one that would have caught this.

**Do not replace one completeness claim with another.** The `T-044`/`T-045` lesson in
`ai/TESTING.md` §13 applies directly: the corrected record states what is proven and names its
open edges — the upstream contract (`T-057`) and the UI affordance (`T-017`) — rather than
declaring the area closed.

#### Acceptance criteria

- Every test named above is run, and a mutation is run against each claim it is cited for — at
  minimum: making `DRM_PROTECTED` retryable, and removing the single-extraction assertion. **A
  claim whose mutation survives is not recorded as covered**
- §12's coverage sentence is recomputed from §7's rows rather than edited in place
- `ai/STATUS.md`'s DRM statements agree with each other and with §12 — one number, stated once
- The corrected record names `T-057` and `T-017`'s criterion as the open edges of the boundary
- No mandatory row's *requirement* text is reworded; only the coverage claim about it changes

#### Out of scope

- Adding tests. If the mutation evidence shows a claim is not actually gated, that is a finding to
  file, not a fix to fold into a documentation task
- `T-057`'s code change

#### Second correction — the search was narrower than the claim, 2026-07-28

`T058-R1` continued, and the reason is worth more than the fix. The first correction removed every
restatement from `ai/STATUS.md`, then verified the single-home claim by grepping for `"ten of
ten"` and `"of ten mandatory"` — **the two phrasings it had just removed**. That search cannot
fail, and it reported success while `ai/TESTING.md` §7's own execution note two hundred lines
above the count still read "All ten are back in the default run".

Corrected: §7's note now says "Every mandatory area above", `ai/TESTING.md` §12 is the only place
the count or its denominator appears, and three historical entries (`T-014`, `T-034`, and this
task's own criteria and evidence) keep their numerators and drop the size of the set. The check is
now a pattern over word-form and digit numbers near `mandatory`, `of ten` or `§7` across `ai/`,
`AGENTS.md` and `README.md`, whose *output* is read rather than its exit status.

`ARCHITECTURE.md` §7 — the error taxonomy — also has ten rows, and `T-010`'s entry says so. That
is a different §7 and was deliberately left alone.

#### Evidence, 2026-07-28

**The coverage sentence in `ai/TESTING.md` §12 is recomputed from §7's rows** rather than edited
in place, and §12 is where the number is — this entry does not restate it. The old sentence
— "eight … Log redaction and DRM remain uncovered" — was wrong in both halves by the time anyone
read it: `T-038` closed log redaction, and DRM had been gated since the worker path landed.

**Every claim recorded was mutated first**, and all three mutations were killed:

| Claim | Mutation | Result |
|---|---|---|
| `DRM_PROTECTED` is never retried | drop it from `_NON_RETRYABLE` in `core/errors.py` | killed by `test_drm_protected_is_non_retryable_in_the_taxonomy` and `test_a_drm_failure_offers_no_retry_at_all` |
| No bypass path | delete the DRM check before the download in `worker.py` | killed by `test_a_drm_item_fails_without_attempting_extraction` |
| Detection is structural | let `has_drm` match "drm" in the title | killed by `test_drm_detection_does_not_read_message_text` |

**The corrected record names what it cannot cover** rather than declaring the area closed
(`T-044`/`T-045`, §13): no recorded fixture can exist, because capturing one means probing a DRM
service; and `_has_drm` is written as `True` or `None` and never `False`, so absence is
ambiguous. Both are stated in `ai/TESTING.md` §12 with the reason.

**One number, one home — and this claim was false when it was first written** (`T058-R1`). The
correction recounted §7's rows honestly and then **restated the new number in `ai/STATUS.md`
twice**, in a paragraph one of whose sentences said the file no longer stated it; the
coordination commit `2831973` added a third. The reviewer found all three. A recount that
replaces "nine" with "ten" in every place that had "nine" has not moved anything, and writing
"this file does not repeat the count" beneath a repetition of it is the same defect wearing the
fix's clothes.

`ai/STATUS.md` states neither the coverage count nor its denominator anywhere, and neither does
anywhere else outside `ai/TESTING.md` §12 — including §7's own execution note, this task's
acceptance criteria and evidence, and the historical `T-014` and `T-034` entries, each of which
kept its numerator and dropped the size of the set.

**The first attempt at that claim was checked with the wrong search** (`T058-R1`, second pass).
Grepping for `"ten of ten"` and `"of ten mandatory"` found nothing left in `ai/STATUS.md` and
reported success while §7's note two hundred lines above still said "All ten". A search narrow
enough to match only the phrasing you just removed will always succeed. The check is now a
pattern over **word-form and digit numbers within forty characters of `mandatory`, `of ten`, or
`§7`**, run across `ai/`, `AGENTS.md` and `README.md`, and its output is read rather than its
exit status.

The failure mode this task actually closes is therefore narrower and more useful than it first
recorded: *two files stating one number* is what let "DRM is uncovered" outlive being true by
four tasks, and pointing at a number is not the same act as repeating it.

**No §7 requirement text was reworded.** The DRM row still reads exactly as it did; only the
coverage claim about it changed.
### T-037 — End-to-end download and restart proof

**Status:** **Complete — approved with follow-ups**, 2026-07-28 at `894d794`. Both unowned exit
criteria have tests against the assembled application; five mutations, five killed. Low
`T037-R1` and `T037-R2` are Resolved — the scope text described a faked adapter the implementation
deliberately did not use, and the network fixture called Big Buck Bunny public domain when it is
CC BY 3.0. **`T-036` is now approved too**, so nothing on the critical path is outstanding; Phase 1
waits on Windows evidence and its exit review.
**Owner:** Implementer
**Priority:** **High** — two Phase 1 exit criteria are unowned without it
**Phase:** Phase 1
**Depends on:** `T-036`
**Relevant context:** `IMPLEMENTATION_PLAN.md` Phase 1 exit criteria; `REQ-012`, `REQ-014`,
`NFR-003`; `ai/TESTING.md` §7 (Crash recovery)
**Affected surfaces:** `tests/integration/`
**Risk:** **High** — it is the evidence for the phase
**Review base:** the `T-036` merge commit

#### Scope

**Filed after review: the phase had no proof of success.** `T-012` tests probing and failure,
`T-019` tests cancellation and crashes — nobody proved a download *completing*. Phase 1's first
exit criterion is "a real URL downloads to disk with accurate live progress and correct final
bytes", and its fourth is "job state survives an application restart mid-download". Both were
unowned.

Two integration tests against the assembled application, deterministic and offline. *(This read
"with yt-dlp faked at the adapter seam" when the task was filed, and the implementation
deliberately did not do that — `T037-R1`. A faked adapter cannot move bytes, and the first exit
criterion is about bytes moving, so the tests run **real yt-dlp against a local `http.server`**,
which is the exception `ai/TESTING.md` §6 records for exactly this case. The scope text is
corrected to what was built and why, rather than the implementation being bent back to a sentence
written before the constraint was understood.)*

1. **Success.** A job runs to completion: the file exists at the expected path, its byte count
   matches what was reported, progress advanced monotonically through the `REQ-014` stages, and
   the job's terminal state is success in both the UI and the repository.
2. **Restart.** Kill the application mid-download, restart it, and assert the job is recovered
   to a retryable state, visible in the UI, with its `DownloadRequest` intact — the assembled
   equivalent of the database-level recovery `T-014` proves.

A network-marked variant downloads one real, stable, small URL end to end, so the offline fake
is checked against reality at least once. It stays excluded by default (`ai/TESTING.md` §2).

#### Acceptance criteria

- The completed file exists, and its size equals the total the final progress message reported
  — a mismatch is exactly the bug this criterion is for
- Progress is monotonic and reaches every `REQ-014` stage the job actually used
- Success is recorded identically in the UI and the repository; disagreement fails
- After a mid-download kill and restart, the job is recovered, visible, retryable, and its
  stored `DownloadRequest` is byte-identical to the original (`REQ-012`, `NFR-003`)
- Recovery is proven by killing a real process, not by closing the application cleanly
- The `-m network` variant completes one real download and is **not** part of the default run

#### Out of scope

- Multiple concurrent jobs — Phase 2
- Resume of a partial download — Phase 2

#### Evidence, 2026-07-28

**`tests/integration/test_end_to_end.py`** — three tests, everything real except the site. Real
yt-dlp, its generic extractor, its HTTP downloader, a real spawned worker, a real file. The server
is a local `http.server` on `127.0.0.1`, which is the §6 exception recorded for exactly this: the
criterion is about bytes actually moving and a faked adapter cannot move any.

**The assertion that matters joins the halves.** The file on disk is the size the last progress
message said it would be, *and* the size the queue recorded. The worker knows the bytes and the
manager knows the messages; only the assembled thing knows whether they agree.

**The restart is a `SIGKILL` to another interpreter**, mid-download, with the row confirmed
`RUNNING` first. A clean shutdown would prove teardown works, which `T-036` covers; `NFR-003` is
about the other case. The recovered job comes back `FAILED`/`INTERRUPTED`, retryable, visible in
the UI, with its `DownloadRequest` byte-identical to what was submitted. A third test plants a
`RUNNING` row directly, so the claim is about startup rather than about what the previous test
left behind.

**Two things found on the way, both worth more than the fix:**

- **`mypy --platform win32` caught a test that could not run on Windows.** `os.killpg`,
  `os.getpgid` and `signal.SIGKILL` are POSIX-only, so the `windows-latest` job would have
  reported an `AttributeError` rather than a finding. The halves are now split at module level,
  following `downloader/process_tree.py`'s own idiom — each is then type-checked by the run that
  owns it, where a branch inside a function leaves the other side unreachable to whichever run is
  looking. This is `AGENTS.md` §8's "a host-only check is not the whole gate", found by the gate
  that exists for it.
- **The default preset legitimately cannot download the fake clip.** Its selector filters on
  `height` and `ext`; a bare `video/mp4` declares no height, so "Requested format is not
  available" is the *correct* answer. The tests choose a preset instead, which is what the dialog
  is for (`REQ-006`). Recorded at the constant rather than worked around silently, because the
  other reading — that a preset is broken — is wrong and a future reader deserves the real one.

**Mutations run, all killed:** startup no longer recovering interrupted jobs · a completed job
forgetting its output path · recovery rewriting the request it recovers · an interruption recorded
as a worker crash · the stored byte total drifting from the bytes that moved.

**One mutation deliberately not counted.** Freezing `bytes_done` so the stored counter never
advances survives, and should: the manager persists progress only on a *stage transition*, so with
a single-stage download there is exactly one write and a frozen counter is indistinguishable from
correct behaviour. Gating it would assert a promise the design does not make (`ai/TESTING.md` §13).

**The `-m network` variant is written and has never been executed here.**
`tests/network/test_real_download.py` downloads one real archive.org file through the same path,
so the offline fake is checked against reality once. This machine ran it zero times; the first
real run is whoever runs `pytest -m network`. Stated because "written" and "passing" are different
claims and only the first is true. Its `conftest.py` duplicates the `spin` helper rather than
hoisting it, which would put a Qt import in front of the deliberately Qt-free unit suite.

**Checks:** `ruff check .`, `ruff format --check .` (91 files), `mypy src` (35), configured `mypy`
and `mypy --platform win32` (76 each) all pass. Bare `pytest`: **1395 passed, 11 skipped,
2 deselected**.

---

### T-059 — A view opened onto a finished job renders it from the wrong source

**Status:** **Complete — approved**, 2026-07-28 at `52f0aed`. `T017-R4` is Resolved. The rule
gained one entry point instead of two, and the row construction exposed. Three mutations, three
killed — including `_load` computing its own answer, which was the finding.
**Owner:** Implementer
**Priority:** Medium — it is what a user sees after every restart, which is the ordinary case
rather than an edge one
**Phase:** Phase 1
**Depends on:** nothing. **Lands before or with `T-036`**, which is the first code that will
construct a view over a job it did not watch finish
**Relevant context:** `T017-R4`; `ai/REVIEWS.md` (fifth `T-017` re-review); `NFR-005`
**Affected surfaces:** `src/tracks_and_trails/ui/job_detail.py`, `tests/ui/test_job_detail.py`
**Risk:** Low to fix, Medium to leave — a screen reader and the visible byte line disagree

#### Scope

`T-017` established a rule for where a stopped job's displayed size comes from, and put it in one
place — `_totals_for_ending`. **`_load` does not go through that place.** So the rule holds for a
job that finishes while the view is watching and not for one the view is opened onto:

- an already-`COMPLETED` row of `bytes_done=1, bytes_total=20` shows a full bar described as
  "Complete: 20 B downloaded" beside a byte line reading "1 B of 20 B";
- with no recorded total it shows "Complete" beside "3 B of Unknown".

Both are the same contradiction `T017-R2` and `T017-R4` were about, reached through the one entry
point none of the five correction batches drove. **Every test in `T-017` starts from a running
view**, which is exactly why: a suite that never opens a view onto a finished job cannot see what
opening one does.

Reopening is not an exotic path. It is what happens after every restart, and after `T-036` it is
how any completed job will first appear.

#### Acceptance criteria

- Construction goes through the same rule as a live terminal transition — one place decides,
  reached from both entry points, rather than two places agreeing
- A view opened onto a `COMPLETED` row whose counter lags its total shows one consistent story:
  the bar, the byte line and the accessible description agree
- A view opened onto a `COMPLETED` row with no recorded total states no size it does not have
- A view opened onto a `CANCELLED` or `FAILED` row shows what the row holds, since there is no
  earlier display to preserve — state the answer rather than inheriting it by accident
- The tests drive **construction**, not only transition, for every row of the rule; a mutation
  that makes `_load` bypass the rule fails at least one of them

#### Out of scope

- The rule itself, which `T-017` settled and the reviewer verified for live transitions
- Any other `job_detail.py` behaviour; `T017-R1`, `R2`, `R3` and `R5` are resolved and closed

#### Evidence, 2026-07-28

**`_adopt_totals` is the one entry point**, reached from construction and from a live terminal
transition alike. `_load` used to compute its own answer, which is why one row gave two results
depending on whether anyone had been watching it finish.

**The rule gained a row, because construction exposed a case the rule did not have.** For a
cancelled or failed job it said "whatever was last shown" — correct while watching, and meaningless
for a view that watched none of it, where "what was last shown" is the pair of `None`s the view was
constructed with. A reopened stopped job takes the row, since nothing is closer:

| The job is | The size comes from |
|---|---|
| running | the last rendered progress message |
| `COMPLETED` | the row's `bytes_total` |
| `CANCELLED` / `FAILED`, watched | whatever was last shown |
| `CANCELLED` / `FAILED`, reopened | the row |

That fourth row is stated rather than inherited. The previous code would have reached it by
falling through to an empty display, and a cancelled download would have reported nothing at all
about how far it got — a defect the tests would not have caught either, because they would have
been asserting on the same accident.

**Five parametrised construction cases**, one per row plus the two shapes `T017-R4` reported:
a completed row whose counter lags its total, a completed row with no total, cancelled partway,
failed partway, and cancelled before any bytes moved. Each asserts the byte line and the bar agree,
which is the contradiction every form of this finding produced.

**Mutations run, all killed:** `_load` bypassing the rule — the finding itself · a reopened stopped
job inheriting the empty display · the watched case taking the row too.

**Checks:** `ruff check .`, `ruff format --check .`, `mypy src`, configured `mypy` and
`mypy --platform win32` all pass. Bare `pytest` green.

**Why five `T-017` rounds missed it, recorded because it is about test design rather than this
widget:** every test in that task began with a running view. A suite that never opens a view onto
a finished job cannot observe what opening one does, however many cases it drives afterwards.

---

### T-052 — Make the T-013 correction tests kill their claimed mutations

**Status:** **Complete — approved**, 2026-07-28 at `7d67e77`. `T013-R5` is Resolved. Both named
mutations are killed, and the route-before-validation one on **each** of the three routes the
criteria list. Half of this task turned out to be already done — see **Evidence**.
**Owner:** Implementer
**Priority:** Low
**Phase:** Phase 1
**Depends on:** `T-013`
**Relevant context:** `T013-R5`; `ai/TESTING.md` §13
**Affected surfaces:** `tests/integration/test_manager.py`
**Risk:** Low — production behavior is correct; the negative gate is weaker than its evidence
record claims

#### Scope

Strengthen the T-013 correction evidence at the observations where a route-before-validation
regression is currently invisible. Moving the pump's signal emission immediately before
`SessionValidator.accept()` leaves all five cases in
`test_an_illegal_message_never_reaches_the_job` green: the test excludes only `READY` and
`COMPLETED`, so illegal progress may still persist `RUNNING`; it does not assert that foreign
progress or a duplicate resolution report was withheld from the public signals.

The startup-construction test also ends its useful-error assertion with `or True`, making that
assertion unconditional. Remove the escape and prove the stored diagnostic retains the original
failure rather than a cleanup error.

#### Acceptance criteria

- Reordering validation and routing makes at least one committed test fail for each affected
  route: persisted progress state, public progress, and resolution report
- The tests assert the complete persisted status sequence, not selected terminal states
- The useful startup diagnostic assertion has no unconditional branch and fails if the original
  construction error is discarded
- The route-before-validation and diagnostic-weakening mutations are run and recorded as killed

#### Out of scope

- Changing `SessionValidator` or the production routing order, which are correct at `65303a2`
- The blocking cleanup behavior in `T013-R3` and `T013-R4`

#### Evidence, 2026-07-28

**The `or True` was already gone**, removed by a later `T-013` pass that cited this task. Removing
it had shown the production behaviour was right and the *assertion* was wrong: it looked for a
parametrised component name the message never claimed to carry. What the message must carry — and
does — is the `OSError` that stopped the start rather than whatever the unwind hit afterwards.
Recorded rather than quietly dropped from the scope, because "already fixed" and "not a problem"
are different findings.

**What was still missing was the shape of the assertions, not their subject.**

- `test_an_illegal_message_never_reaches_the_job` excluded `COMPLETED` and `READY` **by name**,
  which left `RUNNING` unexamined — so an illegal *progress* message routed before validation
  persisted a state that never legitimately existed and nothing noticed. It now asserts the
  **complete persisted sequence**.
- It checked `succeeded` and `probed` and not `progress` or `resolution_reported`, so a message
  the validator went on to reject could still have reached a widget first. All four public routes
  are checked now.

**Mutations run, all killed:**

| Mutation | Killed by |
|---|---|
| The pump routes before it validates | `probe-stage` (persisted progress state), `foreign-job-id` (public progress), `two-reports` (resolution report) — one per route, as the criteria ask |
| The stored diagnostic discards the original cause | `test_a_startup_failure_leaves_a_failed_job_rather_than_a_phantom_one`, both parametrisations |
| The failure message replaces the cause with the cleanup's | the same test, both parametrisations |

The first mutation was the point of the task and it now fails on **three** parametrisations rather
than the two it would have before, because the persisted-sequence assertion is what catches the
probe case.

**Checks:** `ruff check .`, `ruff format --check .`, configured `mypy` (76 files) all pass. Bare
`pytest`: **1395 passed, 11 skipped, 2 deselected**. No production code changed.

---
### T-036 — Application composition and wiring

**Status:** **Complete — approved**, 2026-07-28 at `306840b`. High `T036-R1` is Resolved: `retry`
moved into the manager, where the transition and the start both belong. Three mutations, three
killed. The reviewer confirmed the process reading — a High stays in its own review until
corrected and verified (`AGENTS.md` §10) — rather than being carried.
**Owner:** Implementer
**Priority:** **High** — without it every component can pass while the product still opens an
empty window
**Phase:** Phase 1
**Depends on:** `T-013`, `T-014`, `T-015`, `T-016`, `T-017`
**Relevant context:** `ARCHITECTURE.md` §3, §4, §8; `NFR-001`, `NFR-002`, `REQ-024`
**Affected surfaces:** `app.py`, `ui/main_window.py`, `tests/ui/`, `tests/integration/`
**Risk:** **High** — the only task that can fail while every other task is green
**Review base:** the last of its dependencies' merge commits

#### Scope

**Filed after review: nothing owned this.** `app.py`'s own docstring says `T-013` adds the
download manager wiring, but `T-013` neither claims `app.py` nor proves the assembled path. So
every Phase 1 task could pass in isolation while the application still did nothing — which is
the failure the phase exists to prevent.

Compose the object graph in one place: construct the repository, the manager, the result pump
and the window; inject the concrete `JobRepository` into the manager through the protocol seam
`T-013` defines; connect the add-URL dialog and the progress view to manager signals; and
report the ffmpeg state `T-035` supplies at startup (`REQ-024`).

Also own orderly shutdown: closing the window stops the pump on its sentinel, cancels any
running job, reaps its process tree, and closes the database — in that order.

#### Acceptance criteria

- A test drives the **assembled application** — not components — from paste through to a queued
  job, using `T-016`'s dialog and asserting the job reaches the repository
- Wiring is asserted structurally too: the manager holds the concrete repository, and every
  manager signal the UI needs has exactly one connection. A signal connected twice, producing
  duplicate rows, must fail
- Startup reports the ffmpeg state and names what will not work without it (`REQ-024`)
- Closing the window with a job running exits with code 0, leaves no process in the tree, and
  leaves the database consistent
- Cold start stays inside `NFR-002`'s 3-second budget with the full graph constructed, and the
  measurement is recorded — `T-007` measured an empty window
- No component is constructed twice, asserted by identity, so a second manager cannot quietly
  service a second queue

#### Out of scope

- Any new behavior; this task connects what the others built
- The single-instance guard — `A-004`, Phase 2

#### First correction batch — the manager owns a retry, 2026-07-28

**Base:** `6ce26ec`. Three mutations, three killed. **Corrected here rather than carried**: the
reviewer's handoff applied the standing carry direction, but `T036-R1` is **High**, and
`AGENTS.md` §10 says a High "remains in the current review until it is corrected and independently
verified", that further focused passes for it need no authorization, and that downgrading one
needs stated reasons and explicit maintainer approval. Carrying it would be a downgrade in effect.

**`T036-R1` (High, blocking) — reproduced first, and it had two halves.** With the failed probe
session not yet released, pressing Retry produced: the row at `queued`, **no manager transitions
at all**, the view still reading `failed`, and a Retry button that did nothing on a second press.

- **The start was attempted once and the refusal swallowed.** The pool of one refuses while a
  session is being released — a window of a tick or two — and nothing ever tried again. A comment
  in the previous test argued that starting "is not what a retry promises", which was my
  rationalisation of the defect; the reviewer measured what it costs.
- **The re-queue was written behind the manager's back.** Composition called `store.update`
  directly, and the store has no signal — `job_changed` is emitted from the *manager's* write
  callback. So nothing announced `FAILED → QUEUED` and every widget kept showing the failure.

**`DownloadManager.retry()` now owns both.** A retry is a state transition plus a start, and both
are the manager's business; composition routes the widget's `retry_requested` to it exactly as it
would route a cancel, so `ui/` still holds no writer. The transition goes through `_persist`, so
it is announced like every other. If the pool is busy the job waits and starts on the first tick
that finds it free — **not** Phase 2's scheduler: one job, the one the user just asked for, and
what it waits for is a session that has already ended being released. `is_idle` counts it and
`shutdown()` drops it, so it cannot hold the door open.

**Mutations run, all killed:** attempting the start once and swallowing the refusal — the finding
itself · the tick never picking up a waiting retry · the re-queue written without announcing it.

#### Evidence, 2026-07-28

**`app.compose()` builds the graph and returns it.** A `Composition` value rather than locals,
because three of the acceptance criteria — the manager holds the concrete repository, no component
is constructed twice, every manager signal the UI needs has exactly one connection — are claims
about an object graph, and a graph nothing can reach is a graph nothing can check.

**Shutdown is a three-step lifecycle, and the order is the point.** `DownloadManager.shutdown()`
cancels the job and reaps its process tree, reporting `idle` when the last session is released
*and* the worker-log listener has drained (`T038-R2`); only then does `QueueWriter.close()` run,
because the manager's final transitions are still being written when it goes idle; only then is
the read connection closed. `setQuitOnLastWindowClosed(False)` is what makes the order possible —
Qt's default is to quit the moment the window disappears, which is step zero of the wrong sequence.

**Three seams `T-016`, `T-017` and `T-059` left open are now connected:** `start_rejected` reaches
the dialog, `retry_requested` reaches a composition-owned re-queue, and the window shows a
`JobProgressView` for whichever job the manager is working on.

**Two real defects this task found, both invisible to every component test:**

- **A retry raised out of a write callback.** `manager.start()` refuses when the pool of one is
  busy, and composition called it from the writer's `done` — so the refusal escaped into a Qt slot
  instead of reaching whoever pressed the button. `FAILED → QUEUED` is what a retry promises; a
  retry that cannot start now logs it and leaves the job durably queued.
- **A quit that skipped the lifecycle aborted the process.** Qt terminates with `SIGABRT` when a
  running `QThread` is destroyed, so `T-007`'s launch test — which quits from a timer, never
  touching the window — exited **-6** with `QThread: Destroyed while thread 'queue-writer' is
  still running` on stderr. `aboutToQuit` now runs a bounded last-resort stop. It cannot reap a
  worker, because that needs timer ticks and the loop is ending; that limitation is recorded at
  the method rather than left to be discovered.

**Three tests were written against the store and each observed the same gap**, which is worth
more than the fix: `T-013`'s ordering is *persist, then signal*, and `ARC-005` moved the persisting
to another thread — so the writer commits a row and **then** posts to the GUI thread, and in
between `store.get()` answers the new state while every widget still shows the old one. A test of
the assembled application waits on what the application *shows*. The module docstring says so, and
notes `is_idle`'s mirror-image trap: it is true before a session starts as well as after one ends,
so spinning on it returns instantly and proves nothing — which one test did, reporting "nothing
failed" for a probe that had not yet been asked to run.

**Mutations run, all killed:** the window built without a manager — the `T-036` defect itself ·
ffmpeg located and never handed to the manager · a replaced view dropped without detaching · the
database closed before the writer finished · the writer closed on any idle rather than during
shutdown · closing the window not beginning the lifecycle · Qt quitting with the last window ·
the environment found and never reported.

**Two of those survived their first run and both produced better tests.** Closing the writer on
every idle survived a check that sampled `is_running` — `close()` is asynchronous, so the thread
is briefly alive either way; the test now *writes another job* after an ordinary idle, which is
the consequence that matters. And removing `setQuitOnLastWindowClosed(False)` has no in-process
consequence at all — a test cannot observe its own exit — so that one is asserted structurally,
with the reason recorded.

**Cold start:** measured with the whole graph constructed and recorded as a test property
(`cold_start_seconds`), against `NFR-002`'s 3 s. `T-007` measured an empty window at 0.178 s; this
measures the migrated database, the writer thread, the manager and the window together.

**Checks:** `ruff check .`, `ruff format --check .` (88 files), `mypy src` (35), configured `mypy`
and `mypy --platform win32` (73 each) all pass. Bare `pytest`: **1392 passed, 11 skipped,
1 deselected**. The wide mypy scope again found errors the `src` scope cannot see, all in the new
test file.

---
### T-017 — Single-job progress view with cancel

**Status:** **Complete — closed 2026-07-28 at maintainer instruction.** All five findings are
Resolved: `T017-R1`, `R2`, `R3` and `R5` across four correction batches in this task, and
**`T017-R4` by the Reviewer when approving `T-059` at `52f0aed`**, which is where it had been
carried.

**No new verdict was issued and none was needed.** The finding was carried rather than corrected
here, so the review that resolved it is `T-059`'s; `ai/REVIEWS.md` carries it and is not edited
by this closure (`AGENTS.md` §4 — only the Reviewer writes there). What was left was this task's
own **status**, which said Blocked with nothing open against it.

**The delivered implementation spans two commits**, which a reviewer reading a single head should
know: `f100108` is where this task's own corrections end, and `52f0aed` is where `T017-R4`'s fix
landed in `ui/job_detail.py` under `T-059`. Anyone re-reading the widget wants both.

*(This entry read "Blocked at `f100108` — by maintainer direction" from 2026-07-28, which was true
when written and stopped being true the moment `T-059` was approved. The gap was reported as a
next step rather than found later.)*

`ui/job_detail.py` holds the view;
`ui/queue_view.py` stays a docstring-only stub, because a multi-job table is Phase 2 and this
task's scope is one job.
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 1
**Depends on:** `T-013`, `T-014`
**Relevant context:** `REQ-014`, `REQ-015`, `REQ-018`, `NFR-001`, `NFR-005`, `SEC-001` and
`REQ-EXCL-001` (the retry affordance is where the DRM boundary becomes visible — added
2026-07-28, see the criterion below)
**Affected surfaces:** `ui/queue_view.py`, `ui/job_detail.py`, `tests/ui/`
**Risk:** Medium
**Review base:** the later of the `T-013` and `T-014` merge commits

#### Scope

One job, visible: percent, downloaded/total, speed, ETA, and the current stage — probing,
downloading video, downloading audio, merging, post-processing (`REQ-014`). A cancel control
that reaches `T-013`'s cancellation path. A failed job stays visible with its error and a
retry affordance (`REQ-018`); nothing fails silently.

#### Acceptance criteria

- Every stage in `REQ-014` is displayed, driven by real `T-011` messages rather than a
  simulated sequence
- Under a burst of progress messages the **event loop stays responsive by measurement**, not
  by eye: either event-loop latency stays under a stated bound, or updates are coalesced to a
  stated maximum repaint rate and a test asserts the coalescing. "Does not visibly stutter" is
  not testable, and a per-message repaint is the obvious naive implementation — it degrades
  exactly when a download is fastest
- Cancel is actuable by keyboard and produces a cancelled job within the `REQ-015` budget
- A failed job shows the extractor's verbatim message and remains in the view with a retry
  affordance (`REQ-018`, `NFR-006`)
- **The retry affordance is driven by `is_retryable`, not by a per-kind branch in the widget**,
  so a `DRM_PROTECTED` job offers no retry at all — not disabled, not present. `core/errors.py`
  states the reason where the policy lives: offering the button implies a workaround exists, and
  `SEC-001`/`REQ-EXCL-001` say none does. A test asserts the absence, and a mutation replacing
  the predicate with a literal kind comparison fails it. *(Added 2026-07-28. This is the UI half
  of `ai/TESTING.md` §7's DRM row — the engine half is already gated in
  `tests/integration/test_worker.py`, the upstream half is `T-057`, and nothing gated this one
  because the widget did not exist.)*
- A cancelled job is presented as cancelled, not as an error (`ARCHITECTURE.md` §7:
  `CANCELLED` is not a failure)
- Accessible names on all controls; no state conveyed by color alone (`NFR-005`)

#### Out of scope

- Multi-job queue view, reordering, bulk actions — Phase 2
- Pause and resume — `REQ-015` includes them, but they need Phase 2's scheduler
- Open-file and reveal-in-file-manager — `REQ-021`, Phase 2

#### Fourth correction batch — the rule the corrections were guessing at, 2026-07-28

**Base:** `5ee8d36`. Authorized by the maintainer under `AGENTS.md` §10. Four mutations, four
killed, including the reviewer's own.

**`T017-R4` (Medium, blocking) — a regression the previous batch introduced, and the second one
this widget has had from me.** `_adopt_stored_totals` was written for completion and run for
*every* terminal state, so:

- cancelling a job displayed at 50% redrew it at the row's stale 10%;
- a real completed row — `bytes_done=1, bytes_total=20`, which is the ordinary shape, because the
  manager writes the total at the terminal transition and leaves the counter where progress
  stopped — showed a 100% bar reading "Complete: 20 B downloaded" beside "1 B of 20 B";
- completion with no recorded total presented the last stage transition's byte count as the final
  size.

**The cause is that this view has two sources of truth and I had been choosing between them at
each call site.** `manager.py` deliberately does not persist progress per message, so the row lags
while a job runs; the final byte count arrives with `Succeeded` rather than as progress, so the
last message lags once it has finished. Each source is right somewhere and wrong elsewhere, and
two of the three endings want the opposite one from the third.

So the rule is written down — in the module docstring as a table, and in `_totals_for_ending` as
the one place that applies it — rather than remembered:

| The job is | The size comes from |
|---|---|
| running | the last rendered progress message |
| `COMPLETED` | the row's `bytes_total` |
| `CANCELLED` / `FAILED` | whatever was last shown |

`describe_bar` also stops falling back to `done` for a finished size: a progress counter is not a
measurement of a finished file, and with no total "Complete" on its own is the honest answer.

**`T017-R5` (Low, non-blocking)** — the evidence said 35 tests when there were 71. Corrected, and
the count is now stated once with the head it was true at.

**Mutations run, all killed:** the reviewer's own — adopting the row's totals for every terminal
state · a completed download showing its progress counter · the finished description falling back
to the counter · a cancelled job no longer keeping what was shown.

#### Third correction batch — the space, not the cases, 2026-07-28

**Base:** `b3e156c`. Authorized by the maintainer under `AGENTS.md` §10. Four mutations, four
killed — including all three of this finding's historical forms and the reviewer's own.

**`T017-R2` (Medium, blocking) — three recurrences, one cause.** The determinate branch
inheriting an indeterminate description; `_refresh` writing the bar without one; and now
completion with an unknown total, plus a stale byte count. Every correction added a guard for the
case just found and left the next one to whether anyone thought of it, and every test compared the
description against a string the same author had written moments before — so it agreed with itself
and missed the case next door.

Two changes, and neither is another guard:

- **`describe_bar(done, total, finished)` is a pure function**, and the space it covers is small
  and closed: each of `done` and `total` is known or not, and the job is finished or not. A test
  now enumerates the cross-product — thirty cases — rather than sampling it.
- **The gate asserts a relation between what the bar *shows* and what it *says***, read off the
  rendered widget rather than from a table beside the code. All three historical forms collapse
  into one sentence: a determinate bar must never say progress cannot be measured, and an
  indeterminate one must never claim a figure.

**And one real defect the reviewer found underneath the ungated case.** The totals behind a
finished bar came from whatever a repaint last drew, so a row holding 2 KB was described as
"Complete: 1.0 KB downloaded". The final bytes arrive with `Succeeded` rather than as a progress
update, making the last render precisely the wrong source; completion now adopts the durable row's
counts. Reading them there is a `T-016` guarantee rather than an assumption — `job_changed` is
emitted from the write's own callback.

**`T017-R3`** — source and tests were accepted; the first correction record still said "the state
words stay immediate", contradicting the second. Corrected in the record that is wrong, with a
note saying so.

**Mutations run, all killed:** the reviewer's own — describing a finished bar only when the total
is known · a finished bar reporting the last size drawn · the determinate branch inheriting the
indeterminate words · the bar drawn without describing itself.

#### Second correction batch — one owner for the bar, 2026-07-28

**Base:** `e66f34d`. Authorized by the maintainer under `AGENTS.md` §10 after the ordinary budget
was exhausted. Four mutations, four killed.

- **`T017-R2` (Medium, blocking) — corrected structurally, because a patch would have been the
  third instance.** `_show_totals` was fixed and `_refresh` still set the bar to 100% on
  completion through a path of its own, so a completed download showed a full bar described as
  "50 percent of 10 B downloaded". The same contradiction, a different writer.

  Two methods writing one widget's state independently is what produced this defect twice, so
  there are no longer two: `_draw_bar` owns range, value and accessible description together, and
  `_refresh` **asks** for a finished bar rather than setting one. A description is now not
  something a caller can forget to update, because no caller writes the value either.

- **`T017-R3` (Low, non-blocking) — an inaccurate claim, corrected rather than filed.** The
  docstring said state words stay immediate; that was true only before anything had been
  rendered. While a job runs, a status change deliberately leaves the more specific stage the
  worker reported — "Downloading video" beats "Downloading" — and the next repaint replaces it
  within `REPAINT_INTERVAL_MS`. An *ending* is immediate, and that is the case a user must not be
  lied to about. Behaviour unchanged; the claim now matches it, and a new test states which of
  the two the widget actually promises. Corrected here rather than carried as follow-up work
  because it is a sentence in a docstring this batch was already rewriting.

**Mutations run, all killed:** `_refresh` writing the bar itself again — the exact missed sibling
· a finished bar keeping the running description · a running status change overwriting the
reported stage · an ending waiting for the repaint like anything else.

#### First correction batch — the rate limit had a second door, 2026-07-28

**Base:** `9c92c32`. Four mutations, four killed.

- **`T017-R1` (Medium, blocking) — a status change no longer flushes pending progress.**
  `_on_job_changed` called `_draw_pending()`, which is a second route into `_show_progress` with
  no rate limit on it. The reviewer interleaved three progress messages with three status changes
  and measured three repaints inside one 100 ms interval, which is the acceptance criterion the
  whole design exists to meet. An *ending* stays immediate — `_refresh` writes it itself, and a
  cancelled job must not go on saying "Downloading" — but progress waits for the timer.
  *(This read "the state words stay immediate" until 2026-07-28. `T017-R3` established that was
  true only before anything had rendered, and the correction below says so; leaving the older
  sentence standing left one record contradicting the next. Corrected here rather than in the
  newer record, because this is the sentence that is wrong.)*

  **At a terminal state the pending message is dropped**, not deferred. That half is not
  bookkeeping: holding it would have let a tick after the ending replace "Cancelled" with the
  download that is no longer happening. The reviewer's guidance named it and it needed naming.

  **The burst test could not have caught this**, and that is the part worth keeping. It drives
  `_on_progress` directly, so it never crossed the path a real download takes, where a stage
  change persists and `job_changed` comes back. It also counted the wrong thing: it asserted on
  messages absorbed, which stayed at zero while a second route redrew. `renders` is now public
  and counted, because `REPAINT_INTERVAL_MS` is a promise about that number and a promise nothing
  can count is not one.

- **`T017-R2` (Medium, blocking) — the bar always describes the bar it currently is.** The
  indeterminate branch set an accessible description and the determinate branch never cleared it,
  so the moment a total became known the bar showed 50% while telling a screen reader that
  progress could not be measured. Under `NFR-005` that is worse than silence: two users of one
  widget were being told different things. Both branches now write it, and the determinate one
  says what it shows rather than merely stopping the lie. **Gated in both directions** —
  unknown → known and known → unknown — because an unknown total arrives late as often as first.

**Mutations run, all killed:** a status change flushing pending progress again · a terminal state
deferring the message instead of dropping it · the determinate branch not describing itself · the
indeterminate branch not describing itself.

#### Evidence, 2026-07-28

**What was built.** `ui/job_detail.py`: `JobProgressView`, driven by `DownloadManager`'s signals,
with `build_progress_view` as the seam composition uses to supply the retry. The suite is
`tests/ui/test_job_detail.py`, much of it driving a real child process over a real queue; **76
tests as of the fourth correction batch**, which is the batch that last changed the number. Stated
here and nowhere else, and deliberately without a commit SHA — a commit cannot name its own hash,
and the previous attempt at precision was a placeholder that would have been wrong on arrival.
This read "35 tests" for four correction batches after that stopped being true, which is
`T017-R5`.

**Two design decisions worth a reviewer's attention:**

- **Repaints are coalesced at a stated rate**, not measured against a latency bound. `REQ-014`'s
  criterion allows either; a rate is the one this widget can *promise*, and `pending_progress`
  and `displayed_progress` are public so a test can tell "coalesced" from "dropped". The tail of
  a burst is never lost — the newest message is held and drawn by the next tick.
- **The retry is reported, not performed.** Re-queueing a failed job is a write and `ui/` holds
  no writer (`ARCHITECTURE.md` §3), so the widget emits `retry_requested` and `T-036` connects
  it. Cancel is different and does live here: it is a request to a process the manager owns.

**The DRM criterion is met by asking the taxonomy, and the test asserts the rule rather than the
case.** `test_the_retry_affordance_agrees_with_the_taxonomy_for_every_kind` is parametrised over
every `ErrorKind` and compares against `is_retryable` itself, so a kind that becomes
non-retryable in `core/errors.py` is covered here without anyone remembering to come back. The
button is **absent** rather than disabled: a greyed-out Retry still asserts that a retry is the
sort of thing a DRM failure could have, which is the claim `SEC-001` refuses to make.

**Mutations run, all killed:** the retry rule replaced by a literal `DRM_PROTECTED` comparison ·
retry offered for every failure · retry disabled instead of absent · every message repainting ·
a cancellation shown as a failure · a stage dropped from `STAGE_TEXT` · the extractor's message
truncated · the cancel control losing its keyboard focus policy.

**One mutation survived at first and produced a test.** Dropping `Stage.POST_PROCESSING` from
`STAGE_TEXT` changed nothing observable, because `_show_progress` falls back to the job's status
text and for that stage the two strings read the same. A stage with no words of its own was
therefore invisible. `test_every_stage_the_protocol_can_report_has_words_to_show` closes it by
checking completeness against `Stage` — the only thing derived from the enum; the strings are
still transcribed from `REQ-014` by hand (`ai/TESTING.md` §13).

**Checks:** `ruff check .`, `ruff format --check .` (87 files), `mypy src` (35 files), configured
`mypy` and `mypy --platform win32` (72 files each) all pass. Bare `pytest`: **1327 passed,
11 skipped, 1 deselected in 74.95 s**. The wide mypy scope again found real problems the `src`
scope could not see, including one that made mypy stop analysing the rest of a test.

**Known-unverified:** the Windows half. Focus order is asserted offscreen here; the real
platform plugin is `T-040`'s, and this widget adds three focusable controls to what that task
covers.

---
### T-062 — The end-to-end tests need an environment CI does not have, and say nothing when they fail

**Status:** **Complete — approved with follow-ups**, 2026-07-28 at `a78df2f`; the coordination
corrections were approved at `8a0117e`. **Four** problems corrected, the fourth found by the run
that fixed the first three. Verified green on `ubuntu-latest`, `windows-latest` and both frozen
jobs in CI run **`30383367481`**. `T062-R1`'s two remaining wording corrections are applied here,
as the Reviewer assigned: the acceptance criterion below no longer claims more than the fix
delivered, and an invented reading-speed comparison is gone.
**Owner:** Implementer
**Priority:** **High** — Phase 1's first and fourth exit criteria have no passing evidence on any
CI platform, and the exit review consumes exactly that
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `T-037`; `ai/TESTING.md` §6; the CI failure at `48dc6a0`
**Affected surfaces:** `.github/workflows/ci.yml`, `tests/integration/test_end_to_end.py`,
`tests/integration/test_composition.py`, `tests/ui/test_job_detail.py`
**Risk:** **High** — these tests *are* the phase's evidence, and they have never passed on CI

#### Scope

`T-037` was written, reviewed and approved against a machine with ffmpeg on `PATH`. **The runners
have none**, so both of its tests fail on `ubuntu-latest` and `windows-latest`, and have never
passed on either. They pass locally, which is how they reached approval.

Three separate problems, and only the first is about ffmpeg:

1. **The tests assume ffmpeg.** They select `Best video available` — chosen because the default
   preset filters on a height a bare `video/mp4` does not declare — and that selector carries a
   `+`, so `_ffmpeg_gap` refuses before downloading. Reproduced locally by removing ffmpeg from
   `PATH`: identical failures, identical messages.
2. **The failure says nothing.** `assert spin(...), "the download never completed"` reports no
   status, no error message, no job state. On the one test that can only fail somewhere the
   author cannot look, the message has to carry the diagnosis — it took a downloaded artifact and
   a local reproduction to learn the job had failed `FFMPEG_MISSING`.
3. **A Windows-only assumption in `T-036`'s ffmpeg test.** It writes `#!/bin/sh` and `chmod 0755`;
   Windows decides executability by `PATHEXT`, so `shutil.which` correctly returns `None` and
   `test_a_usable_ffmpeg_is_reported_as_usable_and_reaches_the_manager` fails there and only
   there.

#### Acceptance criteria

- Both `T-037` tests pass on `ubuntu-latest` and `windows-latest`, demonstrated by a green run
  rather than by local evidence
- **The assertions that did fail on CI** report the job's status, error kind and stored message,
  so the next failure of *those* is diagnosable from the log alone. *(Narrowed 2026-07-28 by
  `T062-R1`. This read "every assertion in them", which the correction did not deliver and did
  not attempt: `why()` covers the two end-to-end waits that failed. The other assertions in those
  files still report only their own text, and that is unfinished work rather than a met
  criterion — a criterion written wider than the fix is how a gate comes to be believed.)*
- `T-036`'s ffmpeg test uses something the host platform actually treats as executable
- Whatever makes ffmpeg available to CI is recorded with its reason — this project is a front end
  for a tool that shells out to ffmpeg, so a CI environment without it is not a neutral choice
- The environment record uploaded by each job states whether ffmpeg was found; its absence was
  invisible in the evidence artifact and had to be inferred

#### Out of scope

- `T-061`'s over-refusal. These tests would pass with it fixed *or* with ffmpeg installed, and
  the two are independent: one is what the product does for a user, the other is what CI proves

#### Evidence, 2026-07-28

**Diagnosed by reproduction, not by reading.** Removing ffmpeg from `PATH` locally produced the
identical failures on both tests, with the identical messages. The job had failed
`FFMPEG_MISSING` before downloading — `REQ-024` working exactly as designed, against a test that
assumed otherwise.

**1. CI gets ffmpeg**, installed per platform with the reason recorded at the step: this project
is a front end for a tool that shells out to ffmpeg, so a runner without it is not a neutral
environment. Installing it does not paper over `T-061` — that a *user* without ffmpeg is refused
more than they should be is a separate defect with its own gate.

**2. The end-to-end failures now diagnose themselves** — those two assertions specifically, not
the suite at large (`T062-R1`). A `why()` helper in `tests/integration/test_end_to_end.py` reports
the job status, error kind, the view's status, whether ffmpeg was found, and the stored message.
Nothing else gained diagnostics. Verified by running without ffmpeg and reading the assertion:

> `the download never completed — job=failed kind=ffmpeg_missing view=failed ffmpeg=NO — not found
> on PATH error=ffmpeg is required for this download but was not found…`

One line, where before it took a downloaded artifact and a local reproduction to learn the same
thing. The restart test does the equivalent by reading the row its killed interpreter left behind,
since that is the only channel it has.

**3. The fake ffmpeg is executable by the platform's own rule.** A `#!/bin/sh` script with mode
0755 is not executable on Windows, where `PATHEXT` decides — which is why
`test_a_usable_ffmpeg_is_reported_as_usable_and_reaches_the_manager` failed there and only there.
It now writes a `.bat` on Windows. `find_ffmpeg` uses `shutil.which` precisely so the platform's
rule applies (`T035-R2`); the test has to honour the rule it exercises.

**4. The environment record now states whether ffmpeg was found.** Its absence was invisible in
the uploaded artifact and had to be inferred from a failure three files away.

**Checks:** `ruff check .`, `ruff format --check .`, configured `mypy` and `mypy --platform win32`
(76 files each) pass. The composition and end-to-end suites pass with ffmpeg present, and fail
with the new diagnostic when it is removed.

**A fourth problem, found by the run that fixed the first three.** With ffmpeg installed,
`ubuntu-latest` went green and `windows-latest` failed on
`test_every_stage_req_014_names_is_shown_from_real_messages`: *"these stages were never displayed:
['Downloading video']"*.

**That is not a Windows defect — it is `T-017`'s coalescing working, against a test that asserted
more than the design promises.** The widget renders the *newest* message, so a stage superseded
before the repaint timer fires is legitimately never drawn. The child held each stage for 0.02 s
and asked for a 1 ms repaint; Qt's default timer granularity on Windows is ~15 ms. Each stage now
lasts 0.15 s, which is long enough to outlive a repaint interval on both platforms and makes the
assertion about the *rendering path* rather than about winning a race with the timer. *(This
carried a "hundred times faster than anyone reads" comparison until `T062-R1`. Nothing in this
project measures reading speed, and a number invented to sound reassuring is the kind of claim
`AGENTS.md` §7 means by preserving uncertainty.)*

**Two runs, and the second is the one that counts.** `30382752254` proved the first three fixes —
`ubuntu-latest` and both frozen jobs green, `windows-latest` red only on the timing test above.
**`30383367481` at `a78df2f` is the final state**: `ubuntu-latest`, `windows-latest` and both
frozen jobs **green**, and `windows desktop` red on exactly `T-060`'s four known tests
(*4 failed, 21 passed*). Both environment artifacts record ffmpeg present on both platforms.

**The lesson, recorded because it is the whole task:** `T-037` was written, reviewed and
*approved* on a machine with ffmpeg, and had never passed on a runner. Four separate CI failures
in this batch were one sentence — a test asserting something true of the author's machine.

---
