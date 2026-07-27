# TASKS.md — Tracks & Trails

**Purpose:** Track concrete, actionable work.
**Authority:** Canonical for current actionable work and its state.
**Owner:** Planner (creates/prioritizes) · Implementer and Reviewer (update status)
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-27
**Update when:** A task starts, blocks, changes scope, completes, or is cancelled.
**Does not contain:** Phase planning (`IMPLEMENTATION_PLAN.md`), progress narrative (`STATUS.md`).

Statuses: Proposed · Ready · In Progress · Blocked · In Review · Complete · Cancelled.
IDs are never reused. Completed tasks move to `ai/archive/` once they bury the live queue.

**Start here:** three merged correction units remain in review. `T-013` is **Blocked** on
`T013-R3` after its maintainer-authorized extra pass; `T013-R4` is resolved. `T-015` has new
High correction regression `T015-R2`. `T-018` resolved its multi-item projection, but Critical
privacy finding `T018-R1` remains open. See the task-local reviewer results and
`ai/REVIEWS.md`.

`T-012` was approved with follow-ups on 2026-07-26 after two review rounds; `T-014` was approved
2026-07-26 at `db14cc2`. **`T-033` is Blocked**, not complete: its code is verified but approval
needs frozen CI evidence this repository cannot produce locally.

Also Ready and independent: `T-038` (log redaction — one of `ai/TESTING.md` §7's two remaining
uncovered mandatory areas, and the one `T-013`'s diagnostics make urgent). `T012-R6` is resolved
by T-018's verified multi-item projection, but T-018 itself remains unapproved on its Critical
privacy gate. `T-050` sits in **Phase 2**, where the plan puts history: nothing writes the
`history` table.

Phase 0 is formally exited (2026-07-26). `T-039` waits for a Phase 5 installer; `T-040` for the
first focusable widgets.

---

## In Review

### T-013 — Download manager and result pump

**Status:** **In Review — Blocked after the maintainer-authorized correction pass,
2026-07-27.** `T013-R4` is resolved; `T013-R3` remains a blocking Medium. The authorized extra
pass is exhausted, so another Medium-or-lower pass requires a new maintainer choice under
`AGENTS.md` §9. `T013-R5` stays non-blocking test hardening owned by `T-052`.

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

**Status:** **In Review — Changes requested 2026-07-27.** `T015-R1` is resolved. New High
correction regression `T015-R2` blocks approval.

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

**Status:** **In Review — Changes requested 2026-07-27.** `T018-R2` is resolved. `T018-R1`
remains an open Critical blocker.

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
**Review base:** the `T-012` merge commit. **Review head:** `0973fee`, merged by `7021a01`
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

## Ready

### T-038 — Logging with handler-level redaction

**Status:** **Ready** — `T-011` complete, 2026-07-26
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

#### Out of scope

- A log viewer in the UI — Phase 3
- Rotation and retention policy — Phase 4
- Crash reporting of any kind; there is none (`NFR-007`)

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

### T-016 — Add-URL dialog with probe results

**Status:** Proposed — Ready once `T-013`, `T-015`, `T-018` and `T-051` merge
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 1
**Depends on:** `T-013`, `T-015`, `T-018` (the playlist/single-item projection this task
displays does not exist until `T-018` adds it — `T012-R6`), `T-051` (the probed `READY` job
cannot currently start a download)
**Relevant context:** `REQ-001`, `REQ-002`, `REQ-005`, `NFR-001`, `NFR-005`, `NFR-006`
**Affected surfaces:** `ui/add_dialog.py`, `ui/main_window.py`, `tests/ui/`
**Risk:** Medium — the first widget that talks to the manager, and the first place a blocking
call would freeze the application
**Review base:** the later of the `T-013` and `T-015` merge commits

#### Scope

Paste or type a URL, probe it, see what it is, choose a preset, and queue it. Probing runs in
a worker process — **never inline** — because probe latency is unbounded and blocking the GUI
thread on it is exactly what `NFR-001` forbids (`ARCHITECTURE.md` §8).

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

#### Out of scope

- The sortable format table and per-format selection — `REQ-003`, `REQ-008`, Phase 3
- Drag-and-drop — `REQ-001` allows it, but it is not needed to prove the slice; Phase 2
- Playlist expansion into individual jobs — Phase 3

---

### T-051 — Define the READY-to-download lifecycle

**Status:** Ready
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

---

### T-052 — Make the T-013 correction tests kill their claimed mutations

**Status:** Proposed — non-blocking follow-up from `T013-R5`
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

---

### T-017 — Single-job progress view with cancel

**Status:** Proposed — Ready once `T-013` and `T-014` merge
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 1
**Depends on:** `T-013`, `T-014`
**Relevant context:** `REQ-014`, `REQ-015`, `REQ-018`, `NFR-001`, `NFR-005`
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
- A cancelled job is presented as cancelled, not as an error (`ARCHITECTURE.md` §7:
  `CANCELLED` is not a failure)
- Accessible names on all controls; no state conveyed by color alone (`NFR-005`)

#### Out of scope

- Multi-job queue view, reordering, bulk actions — Phase 2
- Pause and resume — `REQ-015` includes them, but they need Phase 2's scheduler
- Open-file and reveal-in-file-manager — `REQ-021`, Phase 2

---

### T-036 — Application composition and wiring

**Status:** Proposed — Ready once `T-013` merges
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

---

### T-037 — End-to-end download and restart proof

**Status:** Proposed — Ready once `T-036` merges
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

Two integration tests against the assembled application, with yt-dlp faked at the adapter seam
so they are deterministic and offline:

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

---

### T-019 — Kill the process *tree*, and prove it on Windows

**Status:** Proposed — **rescoped 2026-07-27** (was "Cancellation and worker-crash integration
tests"). Ready once `T-013` is approved.
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

### T-033 — Bundle the pinned yt-dlp baseline into the frozen artifact

**Status:** **Blocked** — code corrections verified 2026-07-26 (`T033-R2` resolved, the
version-against-pin half of `T033-R1` verified). Approval requires evidence this repository
cannot produce locally: the collection-removal negative run, Linux **and** Windows frozen
results, and the recorded artifact-size delta. `T033-R1` stays **Open — externally blocked**;
it is deliberately *not* closed by the commit that lands this work.
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
code and not vacuous. Frozen-artifact evidence on both platforms is pending CI — the local run
is source-mode and deliberately claims nothing about the frozen build.

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



### T-040 — Extend the Windows desktop gate to widget focus order

**Status:** Proposed — blocked until `T-016` or `T-017` adds focusable controls
**Owner:** Implementer
**Priority:** High once unblocked — it completes a `T-026` acceptance criterion that is
currently unmet
**Phase:** Phase 1, landing with the first real widgets
**Depends on:** `T-016` **or** `T-017` (whichever first adds focusable controls), `T-026`
**Relevant context:** `T026-R3`, `OPS-004`, `NFR-005`, `ai/TESTING.md` §9 and §12
**Affected surfaces:** `tests/ui/test_windows_desktop.py`, `ai/TESTING.md` §12
**Risk:** Medium — the gap is easy to forget precisely because deferring it was correct

#### Scope

Filed from `T026-R3`. `T-026` requires "tab order and focus chain are asserted on Windows, and
reordering two widgets fails the test". That criterion is **unmet**, and deferring it was the
right call: the shell window has no focusable controls, so a focus-chain assertion would pass
over zero widgets and gate nothing.

The reviewer's point stands, though — unlike the installer gap, which became `T-039`, this had
no owner. A criterion deferred into a comment is a criterion that quietly disappears. `T-016`
mentions a deliberate tab order but does not require extending the real-plugin Windows suite,
and `T-017` does not mention tab order at all.

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

### T-014 — Persistence: schema, migrations, and the job repository

**Status:** **Complete — approved with follow-ups**, 2026-07-26 at `db14cc2`. Four review
rounds; `T014-R1` (Critical), `R2`, `R3`, `R4`, `R5` and `R7` all resolved, `R6` retracted by the
reviewer. Follow-ups: `T-048` (verify the first real data migration) and `T-049` (tighten
`DAT-003`'s explanatory guarantees before cookie-file support).

Closes three of `ai/TESTING.md` §7's ten mandatory areas — crash recovery, migrations, and the
settings freeze — taking §7 from three to six. **Unblocks `T-013`**, and with it the rest of the
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
capture (public domain, stable) with `cookies`/`http_headers` redacted.

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

Closes `ai/TESTING.md` §7's **Path safety** mandatory area, taking §7 from two of ten to three.
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
  retaining the honest boundary that only one of §7's ten mandatory areas is covered

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
