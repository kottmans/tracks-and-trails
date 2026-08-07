# STATUS.md — Tracks & Trails

**Purpose:** Concise snapshot of where the project stands right now.
**Authority:** Canonical for current project state.
**Owner:** Planner / Implementer
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-08-07
**Last verified against repository:** 2026-08-06 **for the Phase 3 block below** — its task states,
verdicts and commit SHAs were checked against `ai/TASKS.md` and `git log`. The Phase 1 and Phase 2
narrative from `## Next` onward was last swept 2026-08-04 and is kept for its reasoning, not as a
statement of what is true now.
**Update when:** A meaningful work session ends, a phase changes, a blocker appears or clears, or the next task changes.
**Does not contain:** Task detail (`TASKS.md`), review history (`REVIEWS.md`), decision rationale (`DECISIONS.md`).

---

**Current phase:** **Phase 3 — Format and content depth.** **Phase 2 exited 2026-08-05** (commit
`38504b3`); Phase 1 exited 2026-07-29 and Phase 0 on 2026-07-26. All three Phase 2 planning gates
were clear — `P2PLAN-R2` at `f858da9`, `P2PLAN-R1` and `P2PLAN-R3` at `8306378`.

## 2026-08-07: two maintainer rulings, and a phase that did not exist

**Planning only — no source changed, and nothing below is implemented.** Both rulings came from the
maintainer on 2026-08-07 and are recorded as decisions with tasks against them.

- **`UX-006` — the queue is stopped until it is started.** Adding a URL enqueues it and starts
  nothing; the user reviews the batch and presses `Start`; a started queue keeps running until
  `Stop`. The queue is **stopped at every launch**, so restoring a queue no longer resumes
  downloading on its own. `UX-001`'s drain is kept exactly as it was — this changes the default, not
  the semantics, which is why it needs no new mechanism: `T-080` built the gate and `T080-R1`
  already made it park a download and admit a probe. **`T-181`** implements it, in Phase 3. The
  amendment reaches `REQ-015`, `REQUIREMENTS.md` §11 criterion 1, and `docs/UX_SPEC.md` §2, §2.1.
- **`ARC-010` — option coverage is typed fields plus one validated escape hatch.** `REQ-030` sets
  the target as *capability* parity, not flag count: no download reachable from the yt-dlp command
  line may be unreachable from the GUI, while the options that *are* the command line stay the
  application's own plumbing. `REQ-031` adds the escape hatch — additional yt-dlp options, parsed
  and validated against containment, redaction and an application-owned refusal list, never passed
  through. **It answers `P-12` from above** (typed, the model widens) and narrows `P-18`.

**`Phase 4.5 — Option coverage` is new**, between Phase 4 and Distribution, and Distribution is
deliberately **not** renumbered: "Phase 5" names it in five documents and every review record that
cites it. Three tasks are filed against it and **it is not decomposed** — `T-183` is the audit that
turns yt-dlp's option list into the rest of the phase, so no size estimate for it exists yet.

**`T-182` blocks part of that phase and is the maintainer's, not an implementer's.** Six option
families point in the opposite direction from a written constraint: site credentials against
`REQ-EXCL-003`, `--impersonate` against `REQ-EXCL-005`, `--xff` against `REQ-EXCL-002`, `--exec`
against containment, `--download-archive` against the record-keeping the project withdrew on
2026-08-06 — and **SponsorBlock against `NFR-007`**, because those options query a third-party API
and this application promises no outbound traffic beyond downloads and update checks. Capability
parity does not silently buy any of them.

## 2026-08-07: three verdicts, and the shape the two rejections share

Codex reviewed every outstanding boundary on 2026-08-07 (`ai/REVIEWS.md`). One approval, two
*Changes requested*, all corrected the same day and awaiting re-review.

- **`T-179` — Approved with follow-ups at `1e0d0d5`.** Recorded above.
- **`T-168` — Changes requested at `3859190`, then Approved** on the correction. The implementation
  was accepted as correct throughout; the finding was against the **test**. The reviewer reproduced
  both mutants independently and got the same splits — 3 failed / 3 passed globally, 2 failed / 4
  passed for the count-specific form.
- **`T-105` — Changes requested at `a688a4e`, then Blocked, then Approved.** `T105-R3` (High)
  Resolved on the first re-review; `T105-R1` (High) and `T105-R2` (Medium) on the second;
  `T105-R4` (Medium) on a third, maintainer-authorized pass. **`T105-R4` survived its own
  correction** and is the entry worth reading below. The ordinary pass budget was spent with only
  that blocking Medium left, so §10 put the task in **Blocked** and the maintainer **authorized one
  focused pass** on 2026-08-07 for a single sentence.

**Every outstanding review boundary is now closed**, and `## In Review` is empty for the first time
since 2026-08-03. Four tasks were decided on 2026-08-07 — `T-179`, `T-168` and `T-105` approved,
`T105-R4` through three correction rounds — and the open work is `T-180` (carrying `T179-R3`),
`T-176`, and the four tasks the roadmap change filed.

**The two rejections are the same defect at two altitudes, and it is worth naming.** In both, the
artifact under review was corrected and *the thing an implementer would actually act on* was not.
`T-105` corrected `docs/UX_SPEC.md` and left `T-111` instructing an implementer to build the preset
store the finding forbids, `T-108` stating the **rejected** reading as `T-061`'s rule, and
`T-112`/`T-114` carrying unratified `[P]` proposals as acceptance criteria. `T-168` fixed
`_bar_reserve` correctly and left a regression that fixed the entry count at sixteen while its own
criterion said *any* count — so the gate would have stayed green for the rejected mechanism at
every other count.

**A `[P]` mark protects only the document it is in.** That is `T105-R4`'s lesson stated generally:
the spec can be scrupulous about what is unratified and it changes nothing if the task entry an
implementer opens states the proposal as a requirement. The corrections put the requirement in the
criterion and the choice in the question, in both files.

**And then `T105-R4` was committed a second time, inside its own correction.** The first batch
fixed `T-112`'s acceptance criterion and left its **context field**, three lines above, still
calling `P-23` *"this task's own report-as-you-type criterion"*. The proposal was removed from
where it would be built and left in the field an implementer reads first. A sibling audit ran
across four *other* task entries in that same batch and not across the two fields of the entry
being edited — which is the shape worth keeping: *the audit was aimed outward at the class and
missed the instance under the hand*.

**`T168-R1`'s correction produced a fact worth keeping:** of the counts now swept, **24 and 37 kill
the mutants and 9 does not** — nine's merge step is 17 px and no verb is that narrow, so just above
the threshold the rejected reserve is harmless. A parameterized test whose parameters have not been
mutation-checked one at a time can look broader than it is.

## The direction that changed on 2026-08-06: nothing records what has been downloaded

**Maintainer direction: Tracks & Trails is a lightweight downloader, not a media-library tracker.**
`REQ-020` promised the opposite product and Phase 2 built it — records, a view, groups, removal.
**It is withdrawn**, and so is the private ledger that briefly replaced it.

- **What there is:** the queue, and nothing behind it. A completed download is visible on its row
  until the user clears it; after that the application knows nothing about it. There is no list, no
  ledger, no `history` table — migration `0009` dropped it.
- **What goes:** the History tab, the tab widget, history rows, groups, thumbnails and row verbs;
  `HistoryRepository`, `HistoryEntry` and `core/urls.py`; and the Settings shell that existed only
  to hold *Clear download records*, which has nothing left to clear. `T-146` builds the real
  Settings screen when there is a setting to put in it.
- **Duplicates are handled without storage.** `REQ-022` is scoped to the live queue and asks for a
  **confirmation, not a refusal** — a URL already queued is worth mentioning, and adding it anyway
  is one action. `T-114` owns it and stores nothing. Beyond the queue there is no warning at all: a
  repeat lands as `name (1)`, which is what most downloaders do.
- **What is unchanged:** a record is not a file. `DAT-005`'s boundary holds, and *Open* and *Show
  in folder* still work on a completed queue row until it is cleared (`REQ-021`).
- **The Phase 2 records stay true.** `T-085`, `T-100`, `T-144` and `T-145` remain Complete and
  approved. The plan's Phase 2 rows are annotated as removed rather than rewritten — a file that
  erased them would be claiming the project never built what it is now removing.

**The arc took one day and reversed twice**, which is worth keeping because the ledger's cost only
became visible in review: `T-169` narrowed History to a private ledger, `T-170` built it, two review
rounds returned five blocking findings — **two High, and not one of them about the duplicate warning
being wrong; every one about keeping the data** — and the maintainer withdrew the ledger rather than
correct it. `T169-R3` then found that withdrawing it had not removed the rows an upgraded database
already held, so the maintainer ruled to purge those too (`DAT-006`'s legacy-data note). Work
implemented against the two superseded rulings was discarded uncommitted.

**Phase 3 work completed since the exit:** `T-167`, `T-164`, `T-163`, `T-166`, `T-160` (the row
layout range, approved at `fd15ade`/`4799136`), `T-150` and `T-156`; then the withdrawal work above
— `T-169` and `T-170`, with `T-172`, `T-173` and `T-174` **cancelled as moot** once the surface they
proposed to rename or delete was gone — and `T-175` and `T-158`.

**`T-175` and `T-158` are approved with follow-ups at `b92ec62`** (2026-08-06, base `e70d615`). The
dead completion machinery is gone and a refused *Open* is now said at the row, in the status bar and
to assistive technology. One **Low, non-blocking** finding is open: `T175-R1`, the current-tense
source and test prose that still describes the withdrawn History view or ledger as live. It is owned
by the Implementer and targeted at **`T-176`**, which is filed under `## Proposed — Phase 3`.

**`T-168` and `T-105` were reviewed on 2026-08-07 and both came back *Changes requested*.** They
had sat as *complete, awaiting review*; **both are now Approved and Complete** — see the 2026-08-07
review block below. Neither is covered by the `b92ec62` approval, whose base is `e70d615`.

**`T-177`, `T-178` and `T-179` are complete; `T-179` took three mechanisms and a maintainer
disposition to get there.** All three were filed
2026-08-06 from an efficiency audit (Codex, which changed no files) and implemented the same day on
maintainer instruction. Two review rounds followed. `T177-R1` and `T178-R1` are **Resolved**, and
the maintainer split those two tasks out of the blocked batch — neither carries an approval verdict
of its own, and both entries say so. All three are behavior-preserving:

- **`T-177`** — both startup scans deserialized every stored job to select a status `jobs_status`
  has indexed since the first migration. `JobRepository.with_statuses` selects in SQL and keeps
  `all_jobs()`' order. Measured on this host, the pair went from 93.3 ms to 0.65 ms at 2000 queued
  rows, and from 4.6 ms to 0.63 ms at 100 — the cost is now flat in queue size because it is
  proportional to the rows wanted. `queued_job_ids()` went with it; `waiting_jobs()` carries its
  reasoning.
- **`T-178`** — the `FormatChoice` serializers migration `0009` orphaned. `T-175` removed the
  runtime half of the same withdrawal and missed these because a serializer for a departed table
  does not look like a queue path.
- **`T-179`** — the thumbnail cache is swept when the live URL set changes rather than on every
  model reset, so a pure reorder no longer schedules a scan that can only conclude everything is
  still wanted. **Rejected twice.** The first gate remembered only the membership and stranded a
  picture published after its removal sweep (`T179-R1`); the second compared the cache directory's
  mtime, which is lossy on FAT, is not promised to update continuously on Windows, and — `T179-R2`,
  **High** — was read with a `Path.stat()` on the GUI thread that a probe measured holding a
  reorder for 0.152 s. The third mechanism asks the filesystem nothing: it counts publications in
  process, keyed by cache directory so it spans both stores over one root. **Approved with
  follow-ups at `1e0d0d5`** on 2026-08-07, after the maintainer accepted `T179-R1`'s cross-process
  limitation rather than correcting it: a process-local count cannot see another permitted instance
  writing the shared cache, and **both collision directions are `T-180`'s** — including the older,
  worse half, that unconditional sweeps already delete a peer instance's thumbnails. One Low,
  `T179-R3`, is open against `T-180`.

**Four claims written into this work were wrong, and none of them was caught by reading it** —
which is the same lesson `ai/TESTING.md` §13 already carries, arriving four more times in one day.
Two were found by my own mutation runs: `T-177` guarded the empty-status case because `IN ()` "is
not valid SQL", which is true of standard SQL and not of SQLite; and `T-179`'s comment explained
why its marker starts at `None` rather than an empty set, with no test holding it.

**The other two the review found, and the shape is worth keeping.** `T179-R1` is the one that
matters: the first gate suppressed the scan that would have collected a picture written after its
job's removal sweep, and **my docstring described that as an accepted cost rather than treating it
as the defect it was**. Writing down a regression is not the same as deciding it is acceptable, and
a well-argued note beside it makes the regression harder to see, not easier. `T178-R1` is the same
failure in one sentence: a replacement comment that said `_serialize_request` "writes a request
rather than a credential", reversing the very boundary `T159-R1` drew, beside persistence code that
handles cookies.

The audit's fifth observation, `MainWindow.job_reader`, is deliberately untouched: it belongs to
the deferred `JobProgressView` seam.

## The 2026-08-04 review, and where its findings stand

**`T-127` and `DAT-005` are approved.** `T-122` and the `UX-005` batch (`T-124`, `T-125`, `T-126`)
came back **Changes requested** — one Critical, five High, two Medium, one Low. The details live
in each task entry; this is a pointer rather than a second copy of them.

**The re-review found the correction's own Critical, and it is the entry worth reading.**
`T126-R3`: fixing `T126-R1` by committing the open editor on every reset made a *lifecycle* commit
look exactly like a click, so once a retarget landed the redisplayed value was reported as a fresh
choice — `refresh → commit → retarget(UNCHANGED) → then() inline → refresh`, to `RecursionError`.
**My own regression could not see it**, because its fake `retarget` never updated the reader it
was standing in for, so the reopened editor never held the durable value. That is the recurring
shape in this project stated precisely: *a fake that does not model the write cannot exercise the
ordering the write creates*, and the test said "durable" while proving nothing of the sort.
Corrected, and both the reviewer's regression and a new composed one over the real manager now
fail when the guard is removed.

**A third pass then found `T126-R4`, and it is the same lesson at the level of a widget.**
`RowDelegate` is shared between the staging list and the queue, and it prepended *"Same as all"*
unconditionally — meaningful in a paste, which has a group format, and inert on a queue row, which
has only its own request. The queue drew a control entry its own model refuses. What made the fix
more than a deletion is that `PRESET_ROLE`'s `None` **means two different things** on those two
surfaces — *follows the batch* on one, *no built-in describes this* on the other — so removing the
entry naively would have made a custom-selector row open its control reading the first built-in.
The role is now surface-declared and the row speaks whenever the control cannot.

**Twelve findings were corrected in this round.** *(Their state is `ai/REVIEWS.md`'s, not this
line's — it read "awaiting re-review" for days after they had been reviewed. A count restated
here is a second copy that only ever drifts, which is the `COORD-R5` family this file keeps
feeding. What follows is the reasoning the round produced, which does not expire.)*

- **`T126-R1` was the Critical**, and it is the class this project keeps finding: `T118-R14` gave
  the add dialog a commit-before-reset lifecycle for its shared row editor, and the queue was given
  the same delegate **without it**. A reorder, a removal or a clear while someone was choosing a
  format discarded that choice in silence and let the download run as the format they had replaced.
  The committed tests called `model.setData()` directly, so no route the user takes was covered.
- **Five High findings were all the same shape**: an accepted decision implemented on the surface
  and not underneath it. The declared `⋯` keyboard route existed as drawing and not as a route,
  History's `⋯` did nothing at all, the tab counts followed only the paths composition drives, a
  started download said nothing about its format, and `UX-005`'s *rejected* selection toolbar was
  still on screen beside the row verbs that replaced it.
- **`T124-R4` cost a schema migration.** `UX-005` §3's row anatomy names uploader and duration;
  `Job` never carried either, and `T-124`'s own task text had narrowed the decision to `REQ-014`'s
  older field list to fit. A task cannot narrow an accepted decision, so the data was carried
  instead: migration `0003`, and `v3.sql` frozen for `T014-R4`'s gate.
- **`P2EXIT-R8`** was two documents citing hosted run `30712201443` for exit criterion 5 — a run
  that predates `T-127` and exercised the gate the same review proved passes with the watchdog
  removed. `IMPLEMENTATION_PLAN.md` and `T-127` now cite the corrected gate's Linux and Windows
  executions at `8d1b01c`.

**Phase 2 stays blocked**, and at the time of writing on two things rather than on the
corrections: the re-review of this batch, and `T-128`'s diagnosis. *(Both are since closed —
`T-128` is diagnosed in the very next paragraph, which is the conflict `P2EXIT-R14` names. Nothing blocks
Phase 2 now: criterion 8 was met on the maintainer's evidence at the 40-row run, and criterion 6
was signed off on 2026-08-05. **The phase is exited.**)*

**`T-128` is diagnosed, and it was the harness** (2026-08-04). A fixture teardown dropped a
`QObject` that still owned a running `QTimer`; the dispatcher followed the pointer into freed
memory. Both soak cores were still on the machine and `gdb` shows the receiver already recycled —
a use-after-free, not corruption, which is why both runs died at the same test count. The failing
test is **#97**, `test_a_ready_job_starts_a_download_at_running`, named from the traceback's
fixture-teardown frame rather than inferred from the dot count. **Five teardowns had the same
shape** and all now use `tests/qt_lifecycle.drain`, which waits for the poll timer as well as the
work. A reproduction of the mechanism runs in **under a second** against a 6-minute soak at 5%.

**No production code is implicated**: nothing in `src/` reads `is_idle`, and `app.py` waits for the
`idle` *signal*, emitted only after `_timer.stop()`. **Which of two mechanisms killed the soak is
recorded as unresolved** — three full runs produced zero cross-thread warnings, so the likelier one
is the cycle collector freeing the object during `activateTimers()`, which emits nothing. The
correction does not depend on the answer; both start with a live timer on an object about to become
garbage.

**Ruled 2026-08-04: the `T-128` prerequisite is satisfied, and a measurement replaces it.** The two
crashes were not recurrences of `T-074`'s fault, so the premise `OPS-007` was originally made on is
intact rather than broken. **That soak is done and clean** (2026-08-05): **60 of 60, no test failures and no process deaths**, run on `Spock` against `ef21e34`, giving P = 0.042 against the 2-in-39 baseline. The corrected teardown holds, and **criterion 6's measurement half is met**; the other half — the independent exit review — was requested 2026-08-05 in `ai/handoffs/2026-08-05-phase-2-exit-review.md` and **signed the phase off at `8de5a72`**. `ai/REVIEWS.md` holds every verdict, and **no tally is kept here** — a count beside the record is a second copy of it, and it drifts the moment another verdict lands. It read *"three times"* against five.

*(The paragraph below is kept as written, because it is the reasoning the measurement was chosen by.)* **Phase 2's exit then waited on a clean 60-run Linux soak** against the
corrected teardown — sized against the measured 2-in-39 baseline, where an unchanged rate gives a
clean sixty a probability of 0.042. `tools/soak.sh` is the instrument.

*(The recommendation this ruling adopted first said "confirm on Windows that the corrected teardown
ends `T-074`'s recurrences". That is not measurable: `OPS-007` records **361 attempts, zero
events** on Windows, so there are no recurrences there to end, and more green runs would only
re-accumulate the evidence that produced the decision. The confirmation is on Linux, where there is
a baseline to compare against; Windows is a passive watch whose value is **asymmetric** — a
recurrence would rule the harness fix out as `T-074`'s cause, while continued silence adds
nothing.)*

**`OPS-007` is amended, and `T-128` gated the exit** (`P2EXIT-R9`, maintainer ruling
2026-08-04). `OPS-007` accepted `T-074`'s unreproduced access violation as residual risk because
**361 attempts produced no event**, and said in as many words that a recurrence reopens it. `T-128`
records **2 Linux `SIGSEGV`s in 39 serial full-suite runs**, both at the same completed-test
position with a live `ResultPump`. The ruling: **`T-128` must diagnose before Phase 2 exits.** Not
because the risk got worse, but because the acceptance rested on *reproduction being exhausted* and
argued it on `STARBASE` time — and a fault reproducing at roughly 1 in 20 on Linux is reachable in
an afternoon on a machine Windows verification does not depend on. The reasoning is in `OPS-007`'s
2026-08-04 amendment. **`T-074` is unchanged**: still open at Medium, still not established as the
same fault.

**Thirteen of thirteen Phase 2 deliverables are approved**, `T-115` included — approved at
`f6dd691` on 2026-08-02, though this line said otherwise until 2026-08-03. **Exit criterion 6 is met**, 2026-08-05.
It asks for *"reviewed and signed off"*, and what it needed was the **independent phase exit
review** that Phase 0 and Phase 1 each required (`AGENTS.md` §3) — not a deliverable review. That
review was requested on 2026-08-05, returned six verdicts (`P2EXIT-R11`–`R15`, `T161-R1`), and
**signed Phase 2 off at `8de5a72`**. *(This read "not met" until then.)*

**Criterion 8 was added on 2026-08-04: the window must catch up with the features behind it.**
The maintainer ruled it after running the application and producing ten tasks in one afternoon,
`T-132` through `T-141`. **Met on the maintainer's evidence**, 2026-08-05 — reset on 2026-08-04 by `P2EXIT-R10` and
again by `P2EXIT-R12`, both times for a verdict stated over its own evidence, so it is offered to
the exit review rather than asserted past it. What it waited on was *evidence* rather than work,
and three runs supplied it: eleven defects found, then 39 of 41, then **40 of 40** on `kirk`
(`ai/evidence/2026-08-05-criterion-8-third-run.md`), with CI green on the candidate and the
one-platform residual a recorded maintainer ruling. `T-140` was reopened for the accepted criteria it
did not build (`T140-R5`); **all three are built** as of 2026-08-05, and the task is
**Complete** — group verbs, removal that names
its own count, and a keyboard-reachable disclosure — with **`Pause all` deferred to `REQ-017`** by
that day's amendment to `UX-005`, since holding one group has no mechanism once `T-080` deleted
`JobStatus.PAUSED`. **The built-window checklist was run on 2026-08-05 at `f2ec6b7`, and found eleven defects** —
`T-149` through `T-159`, none of them reported by any gate, against a suite of 2153 tests that
was green throughout. `ai/evidence/2026-08-05-criterion-8-checklist-run.md` records it. Seven
are inside criterion 8 and four are Phase 3, **ruled 2026-08-05** — and **all seven are now
Complete**, `T-157` against a `UX-005` amendment recorded before it was built. **Rows 3.6 and §5 have since been run** on `kirk` — 3.6 caught a
completed playlist drawing blank blocks, fixed at `6bae7ec`. That run recorded **39 of 41** — the historical result, kept as
observed: **row 2.7** failed (`T-160`) and **row 3.15** failed (`T-161`). **Both are now
dispositioned.** `T-161` is corrected; row 2.7 is removed from the checklist by `T161-R1`, its
property moved to `T-160` unweakened. **That re-run has since happened and passed** — 40 of 40 on `kirk`,
`ai/evidence/2026-08-05-criterion-8-third-run.md`, with CI green on the candidate and the
one-platform residual a recorded maintainer ruling. The ruling's line was: a defect where accepted work
is *unreachable or drawn wrong* contradicts what the criterion asserts, while one asking for
something *new* does not. The closed list stays closed — `T-149`, `T-151`, `T-152`, `T-153`,
`T-154`, `T-155` and `T-157` are **findings against** `T-132`–`T-141`, not additions to it.

**Every finding of the review round is resolved.** The implementation findings — `T140-R6`, `T137-R2`, `T137-R3`
and `T140-R5` — closed at `083fbe4`; `P2EXIT-R10`, the record finding, closed at `431bb47`, and
`T-140` moved to **Complete** on that approval. **The criterion waited on evidence rather than work**, and
that evidence now exists: the built application run against a **written checklist** derived from
`T-132`–`T-141` and the adopted mockups **on the exact candidate head**, plus Windows and Fedora
evidence on that same candidate. Three runs — eleven defects, then 39 of 41, then **40 of 40** on
`kirk` (`ai/evidence/2026-08-05-criterion-8-third-run.md`) — and CI green on the candidate.
**Met on the maintainer's evidence; the exit review judges whether it carries the criterion.** `P2EXIT-R10` requires the checklist because
automated checks are not sufficient evidence for a criterion about what the window looks like, and
that automation does not replace it. *(The measurement `UX-005` said could reopen the playlist shape did come back clear —
150 entries across ten open playlists cost 0.002 s to open and 0.022 s to paint a viewport, against
a 0.5 s budget. The shape stands, and so now does its implementation.)*

*Read the distinction below rather than around it.* This is an **amendment to the criteria**, made
deliberately and recorded in `IMPLEMENTATION_PLAN.md`, which stays canonical. It is not the mistake
`COORD-R13` corrected — that was a Phase 3 task being *described* as what a criterion waited on,
with no ruling behind it. The list is also **closed as of 2026-08-04**: without an edge, "the UI is
caught up" could never be met, because the next sitting at the window would find a tenth task.

**`T-118`/`T-119` precedes that exit review only because the maintainer sequenced it there**
(2026-08-03). It is a Phase 3 task against no Phase 2 deliverable, so it is not a criterion and
cannot become one. `IMPLEMENTATION_PLAN.md` is canonical for the exit state; this paragraph follows
its distinction rather than restating it loosely.

*(`COORD-R13`: this read *"criterion 6 … is met for Phase 2's own tasks; the UI rework's `T-118` is
what is still open"*, which promoted a sequencing decision into an exit criterion and made the phase
look one task from exiting when the sign-off it actually needs had not been requested.)*

- **Approved:** `T-078`, `T-079`, `T-080`, `T-081`, `T-046`, `T-083`, `T-085`, `T-087`, `T-102`,
  plus the supporting `T-053`, `T-099`, `T-101`, `T-103`.
- **Approved 2026-08-01:** `T-100`, `T-082` (first pass, no follow-up), then `T-084` and `T-086`
  on re-review after their Critical and High were corrected.
- **Approved 2026-08-02:** `T-088` at `9e133a6`, the phase's own proof, once `T088-R4` and
  `T087-R6` were corrected and the suite passed on hosted Windows and Ubuntu.
- **Approved 2026-08-03:** `T-116` at `253bbce`, after `T116-R1`. `T117-R1` closed.
- **Approved with follow-ups at `53b07ec`:** `T-118`, carrying `T-119` — 2026-08-03, after four
  rounds of changes requested and four corrections. Exact-head run `30859578131` supplied the
  Windows evidence the last gate needed: `STARBASE` passed the full suite, and hosted
  `windows-latest` passed every `T-118` correction test. Two non-blocking follow-ups carry
  forward — **`T118-R17`/`T-122`**, the paste-scaling ratio oracle that rejects a transient host
  pause, before the Phase 2 exit review; and `COORD-R21`, this file's own current-truth prose,
  corrected here.
- **Approved 2026-08-02:** `T-115`, after `T115-R1` (High) — the probed row was retargeted while
  every later queue position was admitted ahead of it, so with a pool of one the second URL
  started and the head of the queue waited. Add now takes one admission decision after the
  retarget settles, probed id first.
- **Reopened and corrected:** `T-087`'s killed-holder test (`T087-R6`). The guard is unchanged and
  its approval stands; the test was killing a launcher shim and leaving the real holder alive.
- **`T-092` and `T-074` are unblocked and still open.** `STARBASE` came back online 2026-08-03
  after being unreachable since `OPS-005`'s amendment. Neither gates the phase.

**The UI rework has started.** `UX-003` is accepted — nothing enters the queue unprobed — and
`T-116` through `T-120` are filed. `T-116`, `T-117` and `T-120` are **approved**; `T-118` is the
one still in review:

- **`T-116`** — probes and downloads now draw on separate lanes, so pasting URLs no longer takes
  the slots a running transfer is using. It came first because `UX-003` makes probing mandatory,
  and mandatory probing through one budget would have stalled downloads in flight every time
  somebody pressed Add.
- **`T-117`** — `jobs.thumbnail_url`, and **the first migration after the initial schema**. The
  runner had never applied a second script to a database with rows in it; it does now, and
  `T014-R4`'s frozen-fixture gate refused the build until v2's own bytes were captured.
- **`T-118`** — the add dialog is a staging list. Pasting resolves every line and Add commits what
  resolved; the Probe button is gone. `ui/staging.py` holds the state machine, Qt-free.
- **`T-120`** — the brand palette, applied. `ui/theme.py` was one line and nothing imported it, so
  the application had been showing whatever Qt's default style chose since Phase 0.

**`T-119`'s hold is discharged, and the task is subsumed.** It was held on 2026-08-02 until
`T-118` had a verdict; that verdict arrived 2026-08-03, and the maintainer then merged the two.
`T-119` is filed **Cancelled — subsumed into `T-118`**, with its scope, acceptance criteria and
risk carried into that entry verbatim rather than summarised.
*(`COORD-R14`: the hold stood here immediately above the merge decision, so this document said both
"deliberately not started" and "corrected as one task" about the same work.)*

**`T-118` and `T-119` will be corrected as one task**, not two. Maintainer decision, 2026-08-03:
the reviewer's own disposition asks for *one rendered row, one declared keyboard route, one
effective request*, and `T-119`'s delegate answers `T118-R7`, `T118-R9` and `T118-R10` together
because it draws one reusable editor instead of a widget per row. `T118-R6` and `T118-R8` are then
the request and its display done correctly inside a row the task owns. Patching five findings
against the widget-per-row approach would be fixing what the review already said to replace.

## Two red gates that were on `main`, diagnosed and corrected 2026-08-03

Neither was in `T-116` or `T-118`. **Both corrections were reviewed and approved** at `6c38d5f` —
`T-083`'s implementation and prior approval are unchanged, and `T-116` retains its approval, the
review having independently ruled out its barrier as the cause. **`T-118` is the only thing still
red.** *(True when written. `T-118` was approved with follow-ups at `53b07ec`, and CI is green on the Phase 2 exit candidate: run `31051896815`, all five jobs.)*
*(`COORD-R17`: this read "neither correction has been reviewed", which was true when written and
had stopped being true by the review recorded at this same head.)*

**`test_the_attempt_count_is_bounded_and_the_last_error_survives` was racing a spawn, not catching
a defect.** It failed on the `windows desktop` job in runs `30822454998` and `30823595744` —
deterministically, both times `assert <JobStatus.PROBING> is <JobStatus.FAILED>` with `attempts=3`
and the `NETWORK` message already stored. `attempts` is incremented by the retry that *starts* an
attempt, so `attempts >= AUTOMATIC_RETRY_LIMIT` is true a whole session before that session
reports; the test then allowed a fixed **1.0 s** for it to finish. A session costs ~0.25 s on the
maintainer's Linux box and **~1.07 s on `STARBASE`** — derived from the failing row itself, whose
`created_at` and final `started_at` are 3.543 s apart across three completed attempts. It waits for
the count *and* the settled `FAILED` now, and holds past a backoff derived from the one in force
rather than a literal.

**`T-116`'s barrier was ruled out.** `entering()` recomputes `_ENTRY_STATUS.get(current.status)`
when the write runs and `FAILED` is not a key, so nothing can write `PROBING` after a terminal
state; the observed `FAILED → QUEUED` gap is the 50 ms backoff, not a wait for `_release`. The
`PROBING` row was the last attempt still in flight. **The first completed full-suite run on the
real desktop is what exposed it** — the prior desktop run never reached that step.

**`OPS-009`'s implementation broke the frozen Windows job in three places.** The ruling stands; the
workflow did not honour it. Moving the leg to `STARBASE` left `actions/setup-python@v7` in the job,
which on a machine somebody uses runs the real installer — it deleted the tool-cache interpreter
and failed the reinstall (`30823595744`). **The desktop job's own comment records this exact
incident from the first time it happened.** The leg now checks the machine's Python, as that job
does. `OPS-009` also replaced `matrix.os` and left three references to it: the two frozen artifacts
collapsed into one `frozen-evidence-` and the size report recorded an empty platform.

**Both corrections verified on the runner that found them — and the run as a whole was still red.**
Run `30826638984` at `6c38d5f` concluded **failure**. Stated narrowly, which is the only honest
form: **the corrected `T-083` test passed** on the **self-hosted** `windows desktop` job, whose full
suite ended **1929 passed, 21 skipped, 32 deselected and two teardown errors — job failed**; and
**`frozen windows` passed** in 5m18s, the first frozen build `STARBASE` has ever completed, both
prior attempts having died in `setup-python` before reaching PyInstaller.
*(`COORD-R16`: this read "1929 passed, 0 failed", which is true of the test calls and makes a failed
job look green. The teardown errors were disclosed two paragraphs later; the number was not wrong,
the framing was.)*

**`T-118` is no longer what is red.** All three original causes are addressed and verified on both
Windows runners. **What is red on `main` now is `T-122`'s ratio oracle** (`COORD-R21`): in
exact-head run `30859578131` the single hosted-Windows failure was `T-118`'s own paste-scaling
gate, which rejects a transient host pause rather than a real regression. The product passed on
both Windows runners.

**The Blocked section was re-read on 2026-08-03**, and the re-read corrected the guess that
prompted it: only `T-066` was genuinely unblocked. `T-092` needs a person at the machine rather
than the machine; `T-056` already had its `STARBASE` evidence, which *is* its finding; `T-033`
waits on a maintainer decision and `T-039` on a Phase 5 installer. `T-068` got harder, because
hosted Windows no longer runs at all.

**`T-121` did not recur in that run — which is not the same as resolved.** It stays Proposed: the
phase-exit fixture's localhost clip server aborted a loopback connection in run `30853680183`
(`ConnectionAbortedError`, `WinError 10053`), failing one of five downloads and reddening a test
about admission while it reported zero jobs left queued. `STARBASE` passed it both times. Nothing
fixed the fixture; the second run simply did not trip it.

*(The three `T-118` causes, kept because the history is the argument:)*

- **`T118-R10` flapped a third time.** `windows-latest` measured **0.520 s** for 150 URLs against
  the test's own 0.5 s allowance. Three hosted measurements of one unchanged path read 0.722 s
  (red), pass, 0.520 s (red) — the bound was marginal, and every red run of it cost a Windows job.
  **Replaced 2026-08-03** by three assertions rather than one: an absolute budget at 500 URLs with
  a 24x margin, a runner-invariant scaling ratio, and a structural count of the per-row controls.
  The third is the one that matters — a mutation restoring a widget per row passed *both* timing
  tests, because an unshown view lays nothing out. **One Windows measurement at the new absolute
  bound is owed and has not been taken** — and it should be taken on `STARBASE` rather than on a
  hosted runner, because hosted Actions minutes are nearly exhausted (maintainer, 2026-08-03).
  `ci.yml` already routes the Windows `check` job through `vars.WINDOWS_RUNNER`, so that is a
  repository variable rather than a workflow change. `STARBASE` is a different machine from the one
  the flapping was observed on; the substitution is deliberate and is named as one in `TASKS.md`.
- **Two teardown errors in the staging seam**, both `shutdown() → cancel()` reaching a staged job
  in a state `cancel` cannot express: `KeyError: no job with id …` (seen twice) and
  `IllegalTransitionError: cannot move a job from failed to cancelled`. Neither reproduces on
  Linux and both are teardown-only, so the tests they hang off still reported as passed.
  **Both are fixed** — `cancel()` treats an id the manager cannot answer for as a no-op, and
  `_cancellation_of` asks the state machine rather than `is_terminal`, which is the distinction
  that made `FAILED → CANCELLED` reachable. Landed at `e300b04`, before this correction batch;
  neither has yet been re-observed on `STARBASE`.

## What `T-118` found in code it did not write

Six, and only two by reading the diff. Listed because the pattern matters more than the fixes:

1. **`T-115` came back as `READY`.** A job is probed before it is queued, so a previous run leaves
   `READY` rows and startup admitted `QUEUED` only — it would have drained nothing. **The phase
   proof caught it.**
2. **A paused queue refused to read URLs.** `start()` has admitted a probe since `T080-R1`;
   `admit()` never had the rule. **The phase proof caught it by hanging.**
3. **`done()` disposed of the wrong set** — "never committable" excludes a `READY` row nobody
   committed, which is the case that looks like success and leaves a download the user never added.
4. **`bytes_total` was never persisted for a pre-probed download.** It is written only by a message
   that *moves* a stage, and a `READY` job is moved to `RUNNING` by `start()` before any progress
   arrives. Every download would have shown an unknown size.
5. **A Windows-only focus-chain table still encoded the old rule.** Invisible on Linux; **caught by
   `mypy --platform win32`**, which type-checks tests.
6. **Admitted rows claimed to be reading.** A paste of five hundred showed five hundred rows saying
   "Reading" when four were. Found by a mutation, fixed with a `WAITING` state.

## **`T-115` is fixed — the queue drains, and the gate fired to say so**

`DownloadManager.admit(job_id)` is the public counterpart to `start()`: `start()` raises at
saturation because its caller wanted a session *now*; `admit()` expresses durable intent, so five
URLs into a pool of three no longer makes the caller choose which two to drop. The parking
primitive already existed — `_start_when_free` — and had no public door.

Two callers cover both halves: the **add dialog** admits every job it persisted rather than only
the probed one, and **`compose()`** admits every durable `QUEUED` row at startup, which is what a
dialog-only fix would have missed since `_waiting` dies with the process.

**`T115-R1` (High) corrected the dialog's half on 2026-08-02.** The first version admitted the
fresh rows immediately and left the probed row until its retarget had settled, so a later
`queue_position` could take a slot the head of the queue was still waiting for — with a pool of
one, probing the first URL and adding it alongside a second started the *second*. Add now takes
**one admission decision**, after the retarget, probed id first; a refused retarget still admits
the rest of the paste rather than stranding it. Insertion order is the durable order, because
`queue_position` is allocated `MAX + 1` at insert and the probed job was submitted first.

**The `QUEUED` list is read after recovery**, so nothing that was in flight is admitted. Starting
those unattended was `T081-R4`, and this ordering is the only thing preventing it.

**The strict `xfail` reported `XPASS(strict)` on the first run after the fix** — reddening the build
exactly as promised — and was then inverted. Two tests were added for what the Add route cannot
reach: a queue left by a previous run, and a paused queue that admits and still starts nothing.

Chasing a surviving mutation found that `test_a_hard_kill_mid_queue_restores_every_job_state_at_the_next_start`
had **become racy**: it asserted never-started rows stay `QUEUED`, which startup now legitimately
changes. It was passing on timing. It asserts what recovery actually promises instead — those rows
are not moved to `FAILED`.

## **`T088-R4`: my correction for the Windows failure introduced a way to fake a repair**

The `disk I/O error` on `windows-latest` had a real cause — `db.connect()` runs `migrate()`, so my
polling "reader" was opening a **migrating** connection against a database the application was
writing. The read-only fix was right. What I then did with the failure was not: on persistent error
the helper returned `{}`, and **`all([])` is `True`**.

One missed read would have reported every job terminal, turned `T-115`'s strict `xfail` into an
`XPASS`, and **announced a repair that had not happened** — the exact failure the strict marker
exists to prevent. Completeness is now checked before any `all`, and `settled([])` is explicitly
`False` rather than vacuously true.

The same round found four teardowns that killed only `Popen` — three having discarded the reported
application pid entirely. Under a Windows virtualenv `Popen` is the *launcher*, so those could leave
a composed application and its workers running after the test passed. One `reap_application` helper
now reaps the captured tree everywhere.

**`T087-R6` is the same mistake in an approved task.** `test_a_killed_holder_leaves_a_lock_the_next_launch_can_take`
failed twice on `windows-latest` and I had twice called it flaky. It is not: `_spawn` runs
`sys.executable`, the shim gets killed, the real holder keeps the lock, and the next acquire is
refused by a process the test believed it had killed. **Calling it flaky was the error** — I had the
evidence to look and did not.

## **The review found a Critical in `T-084`, and it was a decision I misread**

`T084-R1`. I made log redaction provenance-aware on the reading that `DAT-003`'s `T-049` amendment
moved the boundary to *who put the value there*. **It does — about the database.** The section
directly beneath that table is headed *"`T-038` is unchanged and origin-agnostic"* and says every
log this application emits is redacted whatever the provenance of the text inside it, because
storage and emission are different sinks. I read the table and not the section under it, then wrote
`DAT-004` arguing for the change — a `Proposed` entry cannot supersede an `Accepted` one, and
proposing it from inside a task was not a route I should have taken. `DAT-004` is **withdrawn**.

**Why it was Critical rather than merely wrong:** the scheme had two tiers, and the first —
exact `remember_a_secret()` values — is **empty in the running application**, because no production
caller registers anything. So "provenance-aware" collapsed to *no redaction at all* for every line
yt-dlp emits, and a diagnostic echoing the source URL wrote its userinfo password and signed query
to the job log verbatim — onto the surface `T-084` had just given a Copy button.

**Ruled 2026-08-01: `DAT-003` wins.** `T-084`'s criterion asking that a yt-dlp-emitted cookie path
survive character for character could not hold alongside the accepted decision, so **the criterion
was amended** — a criterion that contradicts an accepted decision is the thing that is wrong. The
cost is recorded: a user will not see a cookie path yt-dlp named in a job log. `NFR-006`'s promise
is kept at the other sink, where `DAT-003` puts it — the database stores the extractor's message
verbatim — and the amended criterion asserts the two sinks against each other on one value.

**Four other findings, all corrected:** `T084-R2` (Copy took the capped rendering, not the file),
`T086-R1` (Windows Open ran `explorer`, which is the file manager, not the associated-application
route Windows documents — an argv test can never catch that), and `T088-R1`/`R2`/`R3` (the `T-115`
case was an unconditional xfail that could never detect its own repair; two tests claimed to observe
progress and a restart that they did not). Eleven mutations across the corrections, all killed.

## **The correction for `T088-R3` did not compile, and chasing that found worse**

The reviewer caught it: the restart helper's embedded settings string had unescaped newlines, so the
child died with a `SyntaxError` before `compose()` ran. **I had not re-run the phase tests after
writing it** — the last run predated the change.

Checking the sibling launcher for the same mistake found the more serious one. It wrote a literal
backslash-n into `settings.toml`, which is invalid TOML, so `compose()` fell back to defaults —
and the default concurrency is **3**, the very number the test thought it had configured. **The
"concurrency limit respected exactly" test had never tested a configured limit.** It now configures
`2`, which the default cannot produce.

Both are the same class as the 38 Windows failures: a test that passes for a reason other than the
one it names. `ai/TESTING.md` §13 exists for this and I keep re-finding it from the inside.

## **A fifth boundary lapse: `git add -A tests/` swept in the reviewer's regressions**

`ff16034` committed the two intentionally-failing reviewer regressions along with my own fix. They
were meant to fail until the implementation caught up, and committing them made the tree red for a
reason the commit message did not mention. **Five times this session** a commit has carried
something outside its own boundary, and the cause has been the same each time.

## **CI caught 38 Windows failures I pushed unrun — all in my own new tests**

*(Corrected in two passes: 37 at `5ea6656`, and the last one — `test_a_missing_launcher_says_which_one`, which hardcoded `xdg-open` where Windows produces `explorer` — after run `30713509567` isolated it. `ubuntu-latest` was green in that run; `windows-latest` failed on that single test.)*

`T-086` and `T-084` went to `main` green on Linux and **red on `windows-latest`**, with 38 failures
across `test_reveal.py`, `test_file_actions.py` and `test_log_view.py`. Every one was a Linux-only
assumption in a *test*, not a defect in the code:

- **Hostile filenames were written to disk.** Windows forbids `"`, `|` and a newline in a filename
  outright, so creating the fixture failed on the platform whose argv the test exists to check. The
  command builders are pure functions of the path; nothing needed to be written.
- **`str(path)` compared against `as_uri()`.** A Windows path renders with forward slashes in a
  URI and backslashes otherwise, so the containment check found nothing — and would have reported
  "spread across 0 arguments", describing a defect that was not there.
- **`["xdg-open", …]` hardcoded** in the wiring tests, which now assert against the platform's own
  builder.
- **`chmod(0o000)` was the unreadable-file fixture.** It does not remove read access on Windows and
  does not stop root on Linux — and the assertion was `in ("", "text")`, which passes whether or not
  the guard exists. The error is now injected at the real call site.
- **`write_text` translates `\n` to `\r\n` on Windows**, so a character-for-character assertion
  compared against a file the test did not think it wrote.

**This is the second time this session that something reached `main` without the platform gate
seeing it.** The first was four failing tests pushed unrun; this one was run, on one platform. A
green local suite is not the gate — `AGENTS.md` §8 says so and I read it as satisfied by `ruff`,
`mypy` and `pytest` on the machine in front of me.

**The same run carried a genuinely good result.** All five of `T-088`'s phase-exit tests
**passed on `windows-latest`** (run `30712201443`), and `T-115`'s case reported `XFAIL` there as
designed. So exit criteria 2 and 5 — hard-kill recovery and no worker outliving exit — are
evidenced on both platforms by measurement rather than by assertion. Only the three UI test files
failed there, and those are the Linux-only assumptions above.

**A hazard worth knowing about, which I walked into twice.** `.github/workflows/ci.yml` sets
`cancel-in-progress: true`, so every push supersedes the run before it. Chasing this verdict I
pushed coordination commits while the run I needed was in flight and **cancelled the Windows job
twice** — runs `30713061006` and `30713168373` both read `cancelled`, and in the second
`ubuntu-latest` had already reported success while `windows-latest` was killed mid-run. **A
cancelled job is not evidence either way**, which matters because this project has already
mistaken a non-failure for a failure once.

**Two flakes found while chasing that, both recorded rather than chased:**

- `test_a_killed_holder_leaves_a_lock_the_next_launch_can_take` failed on `windows-latest` in one
  run and passed in the next with nothing changed between them. The `T-074` class of Windows
  intermittency.
- `test_the_composed_remove_control_updates_the_store_and_the_table` failed once in a full
  `tests/integration` run and **passes alone and in its own file** — so it is cross-file state
  leakage, not a defect in the control. It predates this session's work: `test_composition.py`
  passes complete, including the `T-082` test added to it.

## How `T-115` was found — historical, kept because the measurement is the evidence

**This section is a record, not current state.** `T-115` was fixed on 2026-08-01 and corrected for
`T115-R1` on 2026-08-02; see the snapshot above for where it stands. `COORD-R12` is why the
heading says so: this read *"and it blocks the exit"* while the snapshot above said the same task
was fixed, and a reader had no way to tell which was current.

Measured against a real composed application, concurrency 3, five URLs added through the real
dialog: **three ran concurrently and completed; the other two stayed `queued` with an empty pool**
and were still queued when the run ended.

The pool is not the problem — it works. **Nothing drives it.** `_fill_free_slots` drains an
in-memory list that only the internal path populates; the public `start()` raises when full rather
than parking; nothing anywhere scans the database for `QUEUED` rows; and `add_to_queue` starts only
the **probed** job, with Probe a manual button covering the first URL alone. A user who pastes five
URLs and presses Add gets **zero** downloads started, or one if they probed first.

`add_dialog.py` already carries a comment reading *"leaving it durably `QUEUED`, where whatever runs
the queue next would download the URL"*. There is no "whatever runs the queue next", and that
comment is the clearest evidence it was believed to exist.

Recorded as a **strict `xfail`**, so fixing it fails the build until the test is inverted. Phase 2's
exit criterion 1 is now marked *mechanism met, no user route*: `T-079`'s acceptance criterion is
satisfied and correct, and what no feature task asks is whether anything drives the pool.

**`T-084` found that yt-dlp's diagnostics were being discarded entirely.** `build_options` set no
`logger`, so the output `REQ-019` names went to a console a worker does not have; the per-job log
existed and held this application's own lines only. Two measured findings came out of fixing it:
**`logger` overrides `quiet` and `no_warnings`** (yt-dlp returns from `to_screen` before consulting
either), and **`verbose` must stay off** because it dumps `params:` and `Proxy map:` — values this
application supplies, which `DAT-003`'s provenance table says must never reach a log.

**`DAT-004` is withdrawn** (`T084-R1`). It argued that log redaction should follow the provenance
table in `DAT-003`'s `T-049` amendment; that table governs the **database**, and the section beneath
it says emission is origin-agnostic. `DAT-003`'s reopening clause named *"a bug report attaching
it"* as a trigger, and `T-084` ships exactly that button — **the 2026-08-01 ruling settles it**:
emission stays origin-agnostic, so the Copy surface carries nothing the log did not already redact.

**`A-004` is verified and Phase 2 exit criterion 4 is met.** `T-087`'s three required Windows cases
— first acquisition and refusal, **two launches racing**, killed-holder recovery — passed on
`check (windows-latest)` at `ea9d752`. Under `OPS-005`'s 2026-08-01 amendment that is the Windows
gate while `STARBASE` is unreachable.

**Local evidence, stated as what was actually run.** The Windows corrections above were verified by
three separate invocations covering every changed file — `tests/unit` + `tests/ui` (**1584 passed /
11 skipped**), `tests/integration/test_phase_2_exit.py` (**5 passed / 1 xfailed**), and
`tests/integration` without that file (**275 passed**, plus the cross-file flake noted above). **A
single combined run did not complete**: repeated attempts were killed and restarted by the
environment at ~25 s with no CPU used, which is a machine problem rather than a test one — the last
clean combined run, before these corrections, was **1865 passed / 11 skipped / 1 xfailed**. CI is
the gate that matters here and it runs both platforms.

All four `mypy` gates clean
(`ruff`, `ruff format`, `mypy src`, `mypy`, and both under `--platform win32`).

*(This block previously said ten tasks were in review and that the Windows branch had never
executed, several paragraphs before a later section said the reverse — `T087-R4`. Every claim in it
was true when written and stopped being true the same day. Rebuilt from `TASKS.md`'s sections and
the CI run rather than edited in place, which is the seventh instance of `COORD-R5`'s class.)*

**`T-080` and `T-081` were reviewed and came back Changes requested — six findings, four High.**
All six are closed at `910f3cb`. The theme is worth keeping: **the persistence primitives were
right and the queue the user looks at never heard about any of it.** Removal, reorder and clear each
reached the database and left the table showing the old world indefinitely, because `job_removed`,
`queue_reordered` and `queue_cleared` had **zero receivers**. The other half was that pause guarded
the scheduler and not the public `start()`, so pressing Add while paused began a download — and
**my own test protected that defect**, describing a probe while calling `start()` with its
`DOWNLOAD` default.

**Two mutations survived their first battery, and both times the test was at fault rather than the
code.** One asserted on a disabled `QAction`, which Qt makes a no-op. One asserted on
`active_job_ids()`, which deliberately counts *waiting* jobs — so a wrongly parked probe still
looked active. That accounting split (`T078-R1`) is easy to read past and has now caught this
project twice in two days.

**`T-103` produced a finding of its own.** A first draft added a `_retry_at` pop to `cancel()`; the
mutation survived, and writing the test showed why — a job awaiting a retry is `FAILED`, and
`FAILED` allows only `QUEUED`, so the line could never run. The mutation survived because the code
was unreachable, not because the test was weak. Removed, with `remove()` covering the reachable
path.

**Decisions taken 2026-08-01:** `UX-002` ratifies the automatic retry policy — three attempts at
2s, 4s and 8s, `NETWORK` only — which was the last thing `T-083` was waiting on. `ARC-008` was
implemented by `T-102`. `ARC-006`'s ownership half is implemented by `T-087`; **`A-004` stays
unverified**, exactly as `ARC-006` requires, because the Windows branch of the lock has never
executed.

**Phase 3 is decomposed** (`T-107`–`T-114`). It had **zero** tasks against seven deliverables, so
any statement of its size — including the one given on 2026-07-31 — came from prose rather than
from work anybody had broken down. Two of the eight are structural rather than additive: `T-110`
changes what a *job* is, and `T-113` reopens `UX-001` and `T-080`'s `PAUSED` removal by design.

**Four scheduled things had no task behind them and now do:** `T-104` (the attach channel `T-087`
deliberately did not build), `T-105` (`docs/UX_SPEC.md`, a Phase 3 trigger), `T-106` (the Linux
packaging `REL-` decision Phase 5 requires and which does not exist), and `T-103` itself.

**CI came back on 2026-08-01, and immediately earned its keep.** The picture has changed twice in
two days and both halves matter:

- **The GitHub-hosted runners work again.** After executing zero steps since 2026-07-30 04:08 UTC,
  `ubuntu-latest`, `windows-latest` and both frozen jobs ran a full 15–18 steps.
- **`STARBASE` is offline.** The runner is registered — `self-hosted, Windows, X64, desktop` — and
  its status is `offline`, so the `windows desktop` job sits queued and is cancelled by the next
  push. Earlier notes here called it "starved"; that was wrong. It is not connected.

**The first working run was red, and everything it caught was mine.** Four failures on both
platforms: the original-audio preview (`T046-R4`), `mergeall` (`T046-R5`) and two Windows handle
details (`T087-R3`). All are corrected at `6171812`.

**How they reached `main` is the part worth keeping.** `049b595` was a `git add -A` that swept in
four reviewer regressions written during the review, and I pushed **without re-running the suite** —
which `AGENTS.md` §8 forbids in as many words. The commit's subject and trailers named Phase 2
coordination; its contents included four deliberately failing tests.

**A gate had also been red for the whole session without anything noticing.** `pyproject.toml`
declares `files = ["src", "tests"]`, so plain `mypy` — what a developer types — covers the test
tree. CI ran `mypy src` only. Plain `mypy` was **green before this session and red by the end of
it**: six `JobStore` fakes had fallen behind a protocol `T-080` and `T-081` extended, and a property
narrowed across asserts had made three tests unreachable. Both are fixed, and CI now runs plain
`mypy` as well — a gate nobody runs is not a gate.

**`OPS-005` was amended and nothing is blocked on a machine any more.** Hosted Windows carries the
Windows gate while `STARBASE` is unreachable — on that entry's own reasoning, which was written when
the positions were reversed. **`T-087`'s Windows branch has executed**: first acquisition, two
launches racing, and killed-holder recovery all passed on `check (windows-latest)`, which are its
three required cases. It needs a review, not a machine. The `windows desktop` job is skipped unless
`STARBASE_AVAILABLE` is set, because an offline self-hosted runner holds a run at `queued` forever
rather than failing.

**`17e7ba5` is green on all four hosted jobs** — the first fully successful run since 2026-07-28.

**Two things still wait for `STARBASE`, and neither gates the phase:** `T-092` (arming crash dumps
is configuration of that machine) and `T-074` (its segfault has only ever been seen there). The
desktop slice and `OPS-004`'s subjective residue also stay with it, and still block first release.

**Overall state:** Phase 0's five exit criteria were each verified rather than asserted, and the
evidence is recorded in `IMPLEMENTATION_PLAN.md` §Phase 0 — including a fresh mutation run
proving the layering test still fails on a deliberate `PySide6` import in `core/`.

`T-010`, `T-011` and `T-026` are complete. `ARC-003` settled the IPC versioning question.

**Phase 1 exited 2026-07-29, with two residuals explicit rather than resolved.** All eight criteria
are met and the exit review is recorded in `ai/REVIEWS.md`. It challenged the two decisions that
removed the last blockers instead of treating them as fixes, and upheld both: `OPS-007` is genuine
risk acceptance and **not** evidence that `T-090` fixed the access violation, the 51/361 arithmetic
checks out, and the High → Medium downgrade satisfies §10. `P1EXIT-R3` was found and resolved in the
same pass — the unsupported-URL row cited only the worker-level test, which proves the typed
outcome but neither creates a durable job nor shows text in the UI; it now cites all three
observations and keeps the `_extract`-seam limit explicit. Criterion 7 is **met with accepted
residual risk**: Linux 1430 passed / 11 skipped / 2 deselected, Windows `T-073` run `30415333608`
1388 passed / 20 skipped.

**Neither underlying task is closed.** `T-074` stays open at Medium with all four diagnostic
criteria unmet; `T-066` stays Blocked with its frozen-process assumption explicit and deferred to
Phase 5 alongside `T-033`. `T-092` owns the crash-dump trap, and a recurrence returns `T-074` to
High.

**Two blockers were dispositioned by decision, not by being fixed, and the difference matters.**
`T-066` by the `OPS-005` amendment; `T-074` by `OPS-007`, which accepts its unreproduced access
violation as residual risk after **361 attempts produced no event** — 51 deliberate full-suite runs
across two heads, 60 runs of the crashing test, 250 in-process iterations. Both tasks stay **open**.
`T-074` keeps its four acceptance criteria recorded **unmet** rather than rewritten, and `T-090` is
explicitly **not** established as the crash's cause: the pre-fix sample was equally clean, so a
clean post-fix run carries no causal weight. `T-092` arms `STARBASE` to capture a crash dump so a
recurrence answers criterion 2 — *a stack is not a cause* — instead of adding another anecdote.
The exit review has since recorded criterion 7 as **met with accepted residual risk**; this file
reports that verdict rather than deferring to it. *(This read "calling criterion 7 met is the exit
review's to record, not this file's" after that review had recorded it — `COORD-R9`.)*

**`T-066` no longer blocks the exit** (`OPS-005` amended 2026-07-29, maintainer decision). Its
remaining frozen-artifact evidence can only be gathered on GitHub-hosted runners and the quota is
out — the unreachable-environment condition `OPS-005` covers, which `OPS-006` states generally as
*a criterion that waits on a payment is not a gate*. The amendment also records why the frozen
shape was never Phase 1's question: **all five** frozen references in `IMPLEMENTATION_PLAN.md`
belong to Phase 0 — its deliverable, its exit criterion, its evidence row, its rationale, and the
Phase-level risk-register row at `:330`, which attributes itself to Phase 0 — while Phase 1's
section names none, and `T-033` owns the Windows frozen build in Phase 5. *(This said "all four",
counted case-sensitively and missing the risk-register row; the conclusion is unchanged, the count
was wrong — `COORD-R9`.)* What that gives up is named there — the frozen process-tree shape stays
reasoned rather than measured, and if the assumption is wrong `T-019`'s reaping evidence may not
describe the shipped application. *(A reviewer disposition of 2026-07-29 called `T-066` a standing Phase 1
blocker; it predates the amendment and stands in `ai/REVIEWS.md` as history.)*

**Two things the phase exits with, named rather than hidden:**

- The **subjective** half of Windows verification (`OPS-004`) — whether rendering *looks* right,
  whether Narrator *sounds* coherent, whether the installer *feels* normal. Unverified, needs a
  person, and blocks **first release**, not this phase. `T-039` (installer) has no automated gate
  yet either. **`T-040` is no longer among them**: its tests ran on a real Windows desktop on
  2026-07-28 and both `T-026` mutation classes were killed there, so tab order is gated on
  Windows. *(This entry said "Ready" on 2026-07-27, "Blocked ... never run" on 2026-07-28, and
  was still saying the latter after the run happened — `COORD-R5`. Four documents disagreed about
  this one fact at once; they are reconciled as of `T066-R1`'s correction batch.)*
- **`T011-R8` is closed.** `T-041` was approved at `0268e13` and the finding is functionally
  resolved. The audit behind it found the hole was not one field but every field of every model
  in `core/models.py`.

## Completed

- Documentation system bootstrapped: `DOC-001`
- Requirements, architecture, phases, and Phase 0 tasks defined
- Foundational decisions accepted: `ARC-001`, `ARC-002`, `DAT-001`, `OPS-001`, `OPS-002`,
  `OPS-003`, `SEC-001`, `REL-001`, `LIC-001`
- **`T-004` complete** — licensed MIT; `LICENSE` written
- **`T-002` complete** — Python 3.14 baseline confirmed (PySide6 ships `abi3` wheels)
- **`T-001` complete** — `pyproject.toml`, 27-module skeleton per `ARCHITECTURE.md` §4,
  `tests/` tree, `docs/DEVELOPMENT.md`. All four checks green from a simulated clean checkout.
- **`T-003` + `T-022` complete and approved** — icon set derived from the maintainer's
  1024×1024 source; brand swatches fixed in `ARCHITECTURE.md` §8; resource invariant tests
  added. Codex requested changes, then approved the corrections on re-review; no open
  findings. Two standing caveats: no SVG exists (no vector source), and 16 px is legible only
  narrowly — `T-021` filed as an optional improvement that blocks nothing
- **First review completed** — the review process in `AGENTS.md` §3 has now been exercised
  end to end (implement → review → correct → focused re-review) and works
- **`T-006` + `T-023` complete** — CI runs on Linux and Windows for every push and pull
  request, squash-merged as `c8a72b8` and green on `main`. Reviewed twice; the final
  documentation correction was maintainer-accepted with the focused re-review waived.
- **`T-005` + `T-024` complete** — layering enforcement test, squash-merged as `d1f45e5`.
  The analyser is guarded against being weakened, verified by eight distinct weakenings. Two
  review rounds; the second re-review was waived by the maintainer.
- **`T-007` complete** — the application shell window, merged as `fa5a3c0`. Opens with the
  icon and title, File → Quit and Help → About, geometry across restarts, clean exit. Cold
  start 0.178 s median against `NFR-002`'s 3 s. **Merged without any independent review** at
  the maintainer's direction — not a waived re-review, no first pass; recorded in its task.
- **`T-020` + `T-025` complete** — frozen-build smoke test and the Phase 0 exit preparation,
  merged as `564aad0`. A frozen artifact spawns a child without relaunching itself on both
  platforms; the clean-checkout verification passes on Linux. The **negative** proof — that
  removing `freeze_support()` breaks it — has now been run on Windows too (`T-029`, run
  `30186080950`).
- **Phase 0 exit review complete, and its eight findings closed** — `T-027` … `T-032`,
  squash-merged as `7b7860d`. `P0-R2` … `P0-R5` were reviewer-verified; the corrections to
  `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **maintainer-accepted without a final
  re-review**, and each task records that.
- **Windows is no longer entirely unverified.** `T-006`'s runners confirmed, with downloadable
  artifact evidence: Python 3.14.6 (MSC v.1944, AMD64), PySide6/shiboken6/Qt 6.11.1, a
  `QWidget` visible offscreen, and the full 27-test suite passing. This discharges the Windows
  carries from `T-002` and `T-003`. The `OPS-003` interactive gaps (screen reader, native
  dialogs, keyboard, theming, installer) remain untouched. They no longer all need a person:
  `OPS-004` splits them into an objective half CI can assert (`T-026`) and a subjective
  residue — whether it *looks* right, whether Narrator *sounds* coherent, installer feel,
  shell foreground behavior, long-running stability — which is what still blocks first release.
- Verified 2026-07-25 that yt-dlp 2026.06.09 is pure Python (1046 `.py`, no compiled
  extensions), which is what makes the `OPS-002` pip-free updater viable
- **`T-045` complete — Approved with follow-ups**, 2026-07-26 after four rounds, with no
  production change at any point. `T-046` owns the filesystem-aware uniqueness guarantee.
- **`T-044` complete — Approved with follow-ups by maintainer direction**, 2026-07-26 after six
  rounds and three scope decisions. The gate now states only its tested runtime promise; three
  known blind spots are pinned and owned by `T-047`. No production code changed in any round.
- **The lesson from T-044 and T-045:** all six defects came from treating an enumerated set as
  exhaustive. The successful corrections were not longer enumerations: T-044 reads the
  interpreter's namespace and states its gaps, while T-045 dropped the completeness claim.
  `ai/TESTING.md` §13 records the general rule.

## In progress

**Session of 2026-07-28 — eleven tasks, split into review sections.** The commits are grouped so
each section is a contiguous range:

| Review | Tasks | Base | Head |
|---|---|---|---|
| 1 | `T-016` fourth correction, `T-017` | `6ad20f6` | `6ce195a` |
| 1a | `T-017` corrections, four batches | `9c92c32` | `f100108` |
| 2 | `T-057`, `T-058` | `6ce195a` | `4a06e92` |
| 3 | `T-056`, `T-054` | `4a06e92` | `9c92c32` |
| 4 | `T-059`, then `T-036` and `T-037` | `5b0ebca` | `894d794` |
| 5 | `T-052`, `T-040` | `894d794` | `1aba441` |
| 6 | `T036-R1` correction, `T037-R1/R2`, `T040-R1` attempt | `6ce26ec` | `306840b` |

**Every Phase 1 deliverable is approved.** `T-036` (at `306840b`) and `T-037` (at `894d794`)
closed the two exit criteria that had no owner, and `T-017` closed on 2026-07-28 with the last of
its findings resolved under `T-059`.

**Then CI ran, and the claim that only evidence remained did not survive it** (`COORD-R2`). The
first real Windows run of this work produced three tasks — `T-062`, `T-061` and a widened
`T-060` — and all three are written. **CI run `30388380440` then passed all five jobs at
`11e1203`**, `windows desktop` included; it is the first run of this project with none red.

*(This paragraph called `T-062` "In Review" for as long as it took to approve it. A narrative
sentence carrying a status is a second place for that status to live, which is the shape
`COORD-R2` and the mandatory-area count each landed on — the operative list below is the one
that is meant to hold it.)*

**What remains is evidence.** `T-061` and `T-063` are **Complete** at `11e1203` (`T-063` carrying
`T-064`), and `T-060`'s two findings were **Resolved** at `12dff92` with no further correction
requested.

**Then a Windows machine appeared that is not a CI runner.** `STARBASE`, on the maintainer's
network — Windows 10 22H2, reached over RDP in an interactive session, Python 3.14.6 and PySide6
6.11.1 matching the runners exactly. It supplied the evidence `T-040` had owed since it was filed:
28 desktop tests passing under the real `windows` plugin, and both `T-026` mutation classes
executed and killed. **`T-040` and `T-060` are Complete, approved with follow-up, and `T-026`'s
last acceptance criterion is met** — with no CI minutes spent. *(This read "now In Review rather
than Blocked" until their approvals landed later the same day; `COORD-R5`.)*

**The `windows desktop` job runs on the maintainer's own machine as of 2026-07-28.** `STARBASE`
is a self-hosted runner, in a logged-on elevated session, and job `90432207805` is green end to
end — `28 passed` under the real `windows` plugin. Self-hosted minutes are not billed, so the one
job that cannot be replaced by reasoning survives the Actions quota being exhausted. It also gave
the `T-066` virtualenv change its first execution anywhere.

**It cost a repair to that machine first.** `actions/setup-python` is free on a hosted runner
because the runner is discarded; this one is a computer somebody uses, and it deadlocked the real
Python installer against `msiexec`, leaving the interpreter half-removed. The job installs nothing
now. `docs/WINDOWS_VERIFICATION.md` carries that and the two follow-on traps.

**`T-056` did not move, and now the reason is sharper.** Its defect does not reproduce on
`STARBASE`: the pre-correction helper passes 20/20, with a positive control proving the mutation
was really applied. A Windows machine was not enough; it wants `windows-latest`'s image.

**The same first run found five things CI structurally cannot see** (`T-066`…`T-070`), all five
implemented on 2026-07-28 and all five since reviewed. STARBASE now runs **1384 passed, 24
skipped, 0 failed** as an ordinary unelevated user, from 8 failures at the start.
`T-067`, `T-069` and `T-070` are **Approved**. `T-066` and `T-068` are **Blocked on evidence**, and
`OPS-005` as amended makes neither a phase blocker: `T-066` owes only the frozen-artifact shape —
its `T-019` process-tree cases **have** since run under the venv shape, in run `30414186949` — and
`T-068` still cannot say why the runners do not show the empty font database.
*(This read "`T-066`'s own `T-019` process-tree cases have never run under the venv shape it exists
to cover" after run `30414186949` had executed exactly those cases, including the grandchild case.
The correction is recorded further down this file and in the task; it had not reached here.)*
`docs/WINDOWS_VERIFICATION.md` records the machine, the harness, and the two traps that make a
Windows run look valid when it is not.

The largest of the five is that `ci.yml` installed with no virtualenv while `docs/DEVELOPMENT.md`
tells developers to use one — and on Windows a venv's `python.exe` spawns the real interpreter as
a child, so every `multiprocessing` spawn sits one level deeper than CI ever tested. That is
exactly the tree shape `T-019`'s reaping evidence is about, and it is why `T-066` is not closed by
a green desktop job. Also: `LongPathsEnabled=0` is the Windows default and fails a path test CI
passes; Qt writes a font warning there and not on a runner; and an end-to-end recovery test was
intermittent, which turned out to be `T066-R1` and is now fixed. **CI is one Windows
configuration, and an unusual one.**

**`T-040` is Complete, approved with follow-up.** STARBASE ran both `T-026` mutation classes and
killed them, and the self-hosted `windows desktop` job is now a repeatable normal-run gate — job
`90432207805`, 28 passed under the real Windows plugin. The mutation executions remain **manual**.
`T-056` is the one that still needs the hosted image: its defect does not reproduce on STARBASE at
all. **GitHub Actions hosted usage is exhausted as of 2026-07-28** — workflow `30392139504` failed
before executing a single step, on GitHub's billing annotation.

**That no longer stops the criterion**, which is the part this paragraph got wrong for a day.
`OPS-005` and `OPS-006` gave both halves a platform that does not depend on the quota, and `T-073`
made the Windows half actually run. What holds criterion 7 now is `T-074`, not billing. The hosted
jobs still gate `T-066`'s frozen artifacts — which, as of the `OPS-005` amendment, gate no phase
exit; that evidence lands with `T-033` in Phase 5.

*(This paragraph said `T-069` was "reproduced and narrowed but not fixed" and that `T-040` still
needed the `windows desktop` job, after both had moved — `COORD-R5`. It then said the criterion
"cannot move until it resets" after two decisions had moved it — `COORD-R6`. Both superseded
readings are named here rather than deleted.)*

**The lesson is about method, not ffmpeg.** `T-037` was written, reviewed and approved on a machine
that had what the runners did not, and had never passed on either. Four CI failures in one batch
were one sentence: a test asserting something true of the author's machine.

**`T040-R1` is closed, and what it caught is worth keeping.** The correction drove keyboard focus
as asked and then asserted a state that cannot exist: on a failed job `Cancel` is disabled and on
a running one `Retry` and the error text are hidden, so no chain offers all three controls. The
structural half passed because `focusPolicy() != NoFocus` is true of a *disabled* widget — a list
agreeing with a list, which is the shape that task exists to stop being satisfied by. It was
carried to `T-060`, resolved there, and the mutations it demanded were finally executed on
STARBASE.

*(This paragraph opened "`T-040` is Blocked with `T040-R1` still open" until 2026-07-28, when the
task was approved with follow-up. `COORD-R5`.)*

**And one of those mutations turns out to be unkillable** (`T060-R2`, measured). No state of the
progress view offers more than two reachable controls, and a two-element focus cycle is its own
reverse — from either control, Tab and Backtab both deliver the other. Reversing those two cannot
be observed by any keyboard walk. Order is gated on the add-URL dialog instead, whose states offer
nine to twelve controls, and where the swap is killed in all three states.

**What the day's work turned on.** `T-016`'s third re-review reported its two open findings in
three places each, and all six had one cause: **a synchronous write sequenced every following
effect for free, and an asynchronous one sequences nothing.** `ARC-005` had landed on the claim
that a write-through view made the change invisible to its callers — *"only the announcement
moved"*, *"callers unchanged"* — and each defect was that equivalence failing somewhere different.
The correction is a per-job lifecycle rather than three patches, and `ARC-005` is **amended** to
say so (2026-07-28): asynchrony is not free at the call site.

**DRM was never the uncovered mandatory area this file claimed.** Reading the tests rather than
the record found three layers already gating it; `T-017` added the fourth (the UI half), `T-057`
canaried the yt-dlp field the whole boundary rests on, and `T-058` recounted `ai/TESTING.md` §7 —
where the count lives, and where this file now sends you rather than restating it. `T-057` found
two real divergences on the way: the adapter read `has_drm='maybe'` as protected, and its fallback
used `all` where `_has_drm` — the branch that actually runs — uses `any`, so the two halves of one
function disagreed about a mixed item.

**`T-036` and `T-037` found two defects nothing else could see.** Composition's retry raised out
of a write callback — the pool of one refuses while something else runs, and the refusal escaped
into a Qt slot instead of reaching whoever pressed the button. And a quit that skipped the
shutdown lifecycle *aborted the process*: Qt terminates with `SIGABRT` when a running `QThread` is
destroyed, so `T-007`'s launch test exited `-6`. Neither is visible to a component test, which is
the argument for `T-036` existing at all.

**Three `T-036` tests were written against the store and each caught the same thing.** `T-013`'s
ordering is *persist, then signal*, and `ARC-005` moved the persisting to another thread — so the
writer commits a row and **then** posts to the GUI thread, and in between `store.get()` answers
the new state while every widget still shows the old one. A test of the assembled application
waits on what the application shows. `is_idle` has the mirror-image trap: it is true before a
session starts as well as after one ends.

**`mypy --platform win32` caught a test that could not run on Windows.** `T-037`'s kill helper
reached for `os.killpg`, which does not exist there, so the `windows-latest` job would have
reported an `AttributeError` rather than a finding. `AGENTS.md` §8's "a host-only check is not the
whole gate", found by the gate that exists for it.

**`T-017` is Complete**, closed 2026-07-28 once `T-059`'s approval resolved `T017-R4` — the
finding that had been carried out of it rather than corrected in a sixth pass. All five findings
are resolved and no new verdict was needed: the review that settled the last one is `T-059`'s.
Its delivered code spans two commits, `f100108` and `52f0aed`, which a reviewer reading a single
head should know. Two of the five rounds were regressions I introduced, and the shape is worth
keeping: the widget draws from two sources — live progress and the durable row — and each
correction chose between them at one more call site. The fifth wrote the rule down; the reviewer
then found the one entry point that still bypasses it, `_load`, which no test in the task reaches
because **every test starts from a running view**. A suite that never opens a view onto a finished
job cannot see what opening one does. `T-059` owns that, and should land before or with `T-036`.

**`T-056` is corrected but not demonstrable here.** The fix is Windows-only, and the mutation that
proves it survives on Linux by construction. That is `AGENTS.md` §8's "a host-only check is not
the whole gate" in its exact form, and it needs the Windows job.

- **`T-016` is Approved**, 2026-07-28 at `6ce195a`. Four correction batches; `T016-R1` and
  `T016-R3` were independently verified resolved on the fourth. The Critical is worth carrying
  forward past approval, because each round restated it rather than repeating it: a probe result
  was first bound to a **job id** and not to the URL on screen, then to a withdrawal nothing
  owned until it was durable, then to a start that could be cancelled after it had been reserved
  and before it existed. Every version had the same consequence — work the user had taken away
  running anyway — and the last two only became reachable when `ARC-005` made writes
  asynchronous. *(This bullet said "Changes requested, first correction batch returned" until
  2026-07-28, three batches after that stopped being true, and sat directly above a description
  of the fourth. `T-054`'s reviewer found it.)*
- **`T-019` and `T-038` are both Approved**, 2026-07-27 — `T-019` at `eaa5b50`, `T-038` at
  `098ba3f` after three focused corrections of High `T038-R2`. That finding was the one that
  "directly regresses High `T013-R2`": the per-job log handler closed when the *result* pump
  finished, without establishing that the *log* listener had drained, and listener shutdown
  blocked the GUI thread for a measured 2.001 s. Both halves are fixed — a same-job reopen returns
  the identical still-attached handler, and `idle` is withheld while the listener thread is alive,
  polled by the existing timer and never joined, with `gave_up_on_the_log` as the bounded escape
  if it wedges past `reap_seconds`. `T013-R2/R3/R4` were re-examined and remain resolved.
  `ai/TESTING.md` §7's coverage was recounted by `T-058` on 2026-07-28, with the DRM row's four
  claims each mutation-checked before being recorded. The count itself lives in §12 and is not
  repeated here.
- **`T-013` closed after three correction passes.** `T013-R1`, `T013-R2` and `T013-R4` were
  verified resolved; `T013-R3` came back twice more with a different sibling each time, so the
  maintainer authorized **restructuring** the startup transaction rather than patching it again:
  the session now records each start as it happens, and the unwind reads that record instead of
  inferring it. `T013-R5` remains non-blocking hardening owned by `T-052`.
- **`T-013` approved with follow-ups and `T-015` approved**, 2026-07-27. `T-018` reached its
  **fifth** correction of the same Critical (`T018-R1`). Three recogniser passes each closed the
  reported spellings and left another the rule had not been written to see; the fourth made an
  allowlist the control (`SEC-002`), and the reviewer verified that it works. The fifth removed
  what stood beside it: the schema fingerprint copied captured mapping **keys** verbatim, so a
  secret used as a key was written to disk while all three gates called the file clean. `SEC-002`
  is amended — the fingerprint is gone, `write()` derives everything it writes, and a playlist
  entry is a count rather than a record. **`T-018` is closed as Approved on that fifth pass.**
- **The lesson, a fourth time in one task:** every one of the five rounds ended the same way —
  something was being kept without a reader for it, and the argument for keeping it was always
  "it's only shape / only names / only the parts we recognise". The allowlist survived review
  because it starts from what is *read*. Anything else in a fixture is a liability with a story.
- **`ai/TESTING.md` §12 holds the mandatory-area coverage count; §7's areas are all in the
  default local run.**
  `T-013` added Cancellation and Worker crash against real spawned processes; both moved behind
  `-m process_tree` in `9010794`, because `T-019`'s live defect left descendants that wedged later
  runs. **`T019-R1` caught that the same marker removed them from CI**, which ran a bare `pytest`
  and inherited the exclusion — so for one day two mandatory areas gated nothing anywhere, while
  three records said CI still covered them. `T-019` removed the marker along with the defect.
  Log redaction closed with `T-038`'s approval. **DRM was never the uncovered area this file
  claimed it was** — three tests already gated it, and the record had simply never been
  recomputed. `T-058` recounted it; `T-017` added the UI half and `T-057` the upstream contract.
  The count is now stated in one place, `ai/TESTING.md` §12, and this bullet points at it.
- **The lesson from `T-044`, `T-045` and `T-014`, now three for three:** each blocking finding
  came from filtering unbounded input instead of constraining what the input could be. `T-044`
  stopped parsing for exports and read the interpreter's namespace; `T-045` dropped a completeness
  claim it could not keep; `T-014` made a proxy credential *unrepresentable* in the model rather
  than strippable in persistence. **`T-038` is this problem again** and should start from that,
  not from a recogniser.

**`T-072` is filed, and it is what `T-040` and `T-060` are waiting for.** The STARBASE correction
re-review closed under the maintainer's last-pass direction: carry the residue into a named task
rather than start another correction loop. That task did not exist, so the two behaviourally
accepted tasks had nowhere to carry to. `T-072` now holds `T066-R1`'s survivor assertion and its
unrun `T-019` process-tree cases, `COORD-R5`'s filing and current-truth cleanup, and `WIN-R1`'s
firewall-rule repair, plus the non-blocking `WIN-R3` and `RUNNER-R1` documentation corrections.
`T-040` and `T-060` may close as Approved-with-follow-up on this carry **without another
behavioural review**. See `T-072`.

**`T072-R1` found the `T066-R1` assertion was vacuous, and it was right** (2026-07-29).
`len(doomed) > 1` looked like a check on the walk but was not one: launcher plus interpreter
already make two under the venv shape, so the worker could be missing and it passed. The reviewer
mutated the walk to direct children and watched the omitted worker keep downloading. The
correction takes identity from a startup handshake — the application prints its own pid — walks
from there, and asserts it has the worker as a descendant before capturing and killing that exact
set. One mutation is killed on Linux; the other survives there **by design**, because `killpg`
kills the group regardless of the captured set, so its gate belongs on Windows and is still owed.
`T-064` is **Approved**.

**The Phase 1 evidence table paid for itself twice, and is now finished** (2026-07-29). Building it
exposed that the *headless* criterion rested on a static import guard and an environment variable
that does not remove a display, and that the *unsupported URL* row cited the wrong error class.
Both took three passes. **`P1EXIT-R1` and `P1EXIT-R2` are Resolved.** The scrub and the worker
session are one observation now — the parent removes `DISPLAY` and `WAYLAND_DISPLAY` before
`spawn`, the child asserts their absence and then runs a real `run_session`, and both halves are
mutation-verified. The unsupported-URL row raises a real `UnsupportedError` through `run_session`
and asserts `UNSUPPORTED_URL` plus the exact message, with the honest limit retained: yt-dlp's own
recognition of such a URL is injected rather than live.

*(This block said **`P1EXIT-R1` remains open and blocking** and `P1EXIT-R2` "is open too" for as
long as it took someone to read it against the review that resolved both. `COORD-R8` named it as
the same current-truth failure as the `TASKS.md` filing drift, one document over.)*

**`T-074` has exhausted Linux and now has an instrument** (2026-07-29). The last untested Linux
hypothesis was suite ordering — the Windows crash happened inside a full-suite run and `T-069` was
ordering-dependent. Six deliberate full-suite runs: **6 × 1401 passed, every exit code 0**. With
the earlier 40 single-test iterations and 5 module runs, that is three shapes of attempt and no
reproduction. Not proof of a Windows-only fault; the absence of a Linux one after looking where it
was worth looking. `.github/workflows/t074-repeat.yml` now runs the suite N times on `STARBASE` and
reports a rate, separating crashes from ordinary test failures by exit code — manual dispatch, in
its own workflow, because `ci.yml` is a gate and this is an instrument. **It has run: `0/12 at
ea53c71`, run `30429327464`.** *(This said "Authored, not yet run" after it had.)*

**`T-074` narrowed on 2026-07-29, without being solved.** It does not reproduce on Linux — 40
iterations of the crashing test and 5 whole-module runs, all clean — which does not clear Linux
(`T-069` was ordering-dependent) but does say the fault is not reachable by repetition here. More
usefully, **the obvious cause is already defended against**: the classic PySide6 fault of this
shape is a `QThread` destroyed while `run()` executes, and `manager.py`'s `_release()` refuses to
drop a session while its pump is live. The first hypothesis anyone would reach for is not it. Also
recorded: the Phase 1 exit criteria now have an evidence table in `IMPLEMENTATION_PLAN.md`, which
they never had, and it shows the *unsupported URL* criterion is thinner than the others — proved
against recorded fixtures rather than a live session.

**The new Windows gate found something on its fourth run** (`T-074`, 2026-07-29). The full suite
died with an **access violation**, exit 139, in
`test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget` — with the `ResultPump`
thread in the traceback and the crash at the wait for the *first progress message*, three lines
before the cancellation the test is named for. The failing commit was **documentation-only** and
byte-identical in code to one that had passed minutes earlier, so it is intermittent. **How
intermittent is not established** (`T074-R1`): a deliberate batch ran `0/12` at a later head, which
argues against the original "one run in four" without replacing it — those four runs and these
twelve are not one population, and one event supports no bound. Cause unknown; whether it is
`result_pump.py` or the test harness is an open question and is written as one. It is High priority because it is an access violation in a
module under `src/`, and because an intermittent crash devalues every green run of the gate
`OPS-005` just made load-bearing.

**All five of `T-072`'s carries are now written** (2026-07-29). `WIN-R1` was the last: the
existing-rule branch of `ssh-setup.ps1` did nothing and printed `rule present`, so a machine
carrying the earlier broad `Any` rule kept port 22 open on every profile forever while the script
reported success. It now reapplies the scope, reads the rule back, and reports the profile and
remote-address filter separately — they live on different objects, so a rule can look right and
still allow the world. **`T-072` is Approved and filed Complete** (2026-07-29): `WIN-R1` was
verified on `STARBASE` against a deliberately broadened rule — `defective state confirmed:
profile=Any remote=Any`, then the repair, then `WIN-R1 PASS`. The reviewer found the evidence
non-vacuous on the ground that the precondition would have stopped the procedure had the broad
state not really been created. *(This previously read "One thing is owed before `T-072` closes.",
then "complete and in review" after the approval had landed — `COORD-R8`.)*

**Superseded reading.** `mut_tree_drop_worker` has run on
Windows: it **survives**, because `worker.spawn_session()`'s `parent-watchdog` exits the worker
when the application dies whether or not its pid was captured — so capture-list completeness is
not the product invariant, and `T072-R1` is Resolved on that basis. What remains is the `WIN-R1`
run of the script against a deliberately broadened rule. Neither is verifiable from the Linux box, and neither
belongs in CI — reconfiguring a machine's firewall from a workflow is the provisioning hazard the
runner exists to avoid.

*(**Historical, 2026-07-28** — superseded by the two paragraphs above it, which record `WIN-R1`
landing and `T072-R1` reopening `T066-R1`. Kept because the sequence is the point: this said four
of five and an unexecuted assertion, and both had moved by the time anyone read it. `T072-R2`
reported it staying here as ordinary prose after the newer state was written above it, which is
the same mistake one layer down.)*

> **Four of `T-072`'s five carries are done, and `T-064` with them** (2026-07-28). `COORD-R5` is
> discharged — every task is filed in the section its verdict names, the `## In Review` note no
> longer claims an emptiness it did not have, and `T-040`/`T-060` are Complete on that carry.
> `WIN-R3` and `RUNNER-R1` are corrected: the focus driver's control is `mut_control_chain.py`, and
> `timeout-minutes` bounds a job's *run* time while an unmatched self-hosted job queues for up to
> **24 hours** — a day-long failure mode that was documented as a fifteen-minute one. `T-064`
> recreated the venv: **45 of 46** launchers had been stale, not the 39 filed, because `T-063` had
> repaired this project's own two artefacts and nothing else. `T066-R1`'s survivor assertions are
> written and type-check under `--platform win32`, but they live in the Windows branch and had not
> executed anywhere.

**Then the runner answered it, and it cost no hosted minutes** (2026-07-29). `STARBASE` is online
and green while every hosted job still fails at zero steps on the billing annotation, so the
`windows desktop` job gained a *Process trees under the venv* step. Run `30414186949`: **72
passed, 3 skipped**, the three skips being the POSIX-only half of a platform-split file. That run
executed the `T-019` process-tree cases under the venv shape **for the first time anywhere** —
including the grandchild case — and it executed `T066-R1`'s survivor assertions with them. `T-066`
is accordingly narrowed to frozen-artifact evidence alone.

*(This said "`WIN-R1` is the last carry left in `T-072`" — true for a few hours, then not:
`T072-R1` reopened `T066-R1` on the same day, twice more. `T072-R2` reported the sentence
outliving its truth. `T-072`'s own **Progress** table is the live answer; this paragraph is
historical.)*

**`T-056` and `T-068` are no longer phase blockers** (`OPS-005`, maintainer decision 2026-07-29).
Both stay open and Blocked; neither gates the exit. `STARBASE` is now the platform the *verified on
Windows* criterion is measured against, and a finding that reproduces only on a GitHub-hosted image
does not hold a phase. `T-056` is test-only code whose sole error direction is a false **alive** —
it can redden CI, not hide a defect — and Windows Server is not a supported platform. `T-068`'s
fault appeared on the real machine and its fix is validated there; only the diagnostic question
about the runners is open. **What the decision does not claim:** `still_running`'s mechanism is
Windows-general, so 20/20 on `STARBASE` is absence of a trigger rather than proof of correctness.
**It also does not satisfy exit criterion 7** — the full Windows `check` suite has still not run
anywhere since the quota ran out, and `STARBASE` could run it.

**`T-073` made `STARBASE` run it** (2026-07-29). The self-hosted job now carries lint, format, the
Qt baseline and the full suite alongside the desktop slice, reusing the venv it already builds and
**recording** ffmpeg rather than installing it, because this job must never provision the machine
it runs on. Run `30415333608`: all fourteen steps green, **1388 passed, 20 skipped, 30 deselected
in 208 s**, with `ffmpeg 8.1.2` present — so it measured the same with-ffmpeg configuration the
hosted job does. The count differences against Linux reconcile exactly: Linux carries two
module-level **"collection skipped"** placeholders, for `tests.ui.test_windows_accessibility` and
`tests.ui.test_windows_desktop`, which Windows replaces with the 28 real desktop cases —
`1412 - 2 + 28 = 1438`.

*(This said two tests were unexplained and flagged for review. They were explained, by
`T073-R1`, from the JUnit output rather than from the counts; the arithmetic alone gives 26
against 28 and no way to resolve it.)*

**The remaining hole in criterion 7 was Linux, not Windows** — `check (ubuntu-latest)` is hosted
and has not started either. Windows became the better-covered of the two platforms, which is a
sentence this file had never been able to write before.

**`OPS-006` closed that hole by deciding it rather than building for it** (2026-07-29). Linux
verification is the maintainer's own machine. A self-hosted runner on the development box would
share its OS install, packages and Qt libraries, so it would add a clean checkout and a recorded
result and nothing else — ceremony priced as infrastructure. Every development platform here is
Linux, so the rot-unnoticed risk that justified `STARBASE` has no Linux equivalent. **What it
gives up is written down:** the hosted job installs `libegl1`, `libgl1`, `libxkbcommon0`,
`libdbus-1-3` and `libfontconfig1`, and a desktop already has them, so a change that adds a
system-library dependency would pass here and fail on a bare install. `T-062` is that same shape
one platform over. A container-based runner is the fix if it ever bites, and the decision reopens
rather than being re-argued.

**Both halves of criterion 7 now have a platform, and it is still not met.** `T-074` is why: the
gate has crashed once, in ordinary `ResultPump` delivery, and the fault is unclassified between
product and harness. A `0/12` batch argues against the original one-in-four reading and does not
clear it — a gate that has crashed once and cannot be explained does not verify a criterion.

**`T-071` — the icon was undersized, and the master says why.** Reported from a taskbar
screenshot and fixed the same day: every derived asset drew the logo at ~66% of its canvas with
the slack as one empty band beneath it, so at 32 px the mark filled ~43% of the cell by area.
The master carries a 194 px band of alpha-1..8 pixels below the artwork — invisible, but content
to a trim on `alpha > 0`. All eight PNGs and the `.ico` are regenerated at 92% fill and centred,
now from a script (`tools/icons/render_icons.py`) so it cannot drift back unrecorded. The master
is untouched and the pinned frame sets are unchanged. **Confirmed by the maintainer in the Linux
taskbar**; Windows is unobserved. **Approved at `3327fd3` with no findings** — the reviewer
reproduced every asset byte-for-byte from the script — and filed Complete. See `T-071`.

## Next

**Written 2026-08-02.** `T-115`'s re-verdict was then the only thing between here and Phase 2's exit. *(Superseded many times over — criterion 8 was added on 2026-08-04 and the phase exited on 2026-08-05 at `38504b3`, "Phase 2 exits". This line named `8de5a72`, which is the last criterion-8 sweep rather than the exit commit.)*
After it: the **UI rework**, `T-116` through `T-120`, filed from mockups the maintainer reviewed
and chose between. It precedes `T-107` deliberately — Phase 3 and 4 add a format table, a stream
chooser, a playlist picker and a preset editor **to the queue that already exists**, so what a row
is gets decided once rather than renegotiated by each feature. `UX-003` is the rule the add flow
now follows: nothing enters the queue unprobed. `T-116` comes first because mandatory probing
through the shared pool would stall downloads already running.

**Everything below this line is Phase 1 narrative** and has not been swept since. It is kept for
the reasoning, not as a statement of what happens next.

`ARC-002`'s ordinary end-to-end path is proven: a spawned child imports yt-dlp, extracts and
reports typed messages back (`T-012`); a job survives a restart and an unclean kill (`T-014`);
and, in a test, a URL becomes a file on disk through `T-013`. T-013 is now approved, so that path
is something to build on, and cancellation now reaps the worker's descendants too (`T-019`).
**`T-016`'s dialog is the one widget that touches it**, and it is in review rather than reachable:
composition is `T-036`, so `app.py` still builds a window with no manager and the menu item stays
disabled. The first *user-visible* download is `T-037`. *(This paragraph said "no widget touches
any of it yet" until 2026-07-27, a few lines before another that described `T-016`'s widget doing
exactly that — the contradiction `T016-R8` reported.)*

1. **`T-018` is approved and closed** (2026-07-27, `T018-R1` and `T019-R1` both Resolved). The
   fifth correction removed the schema fingerprint that could carry captured mapping keys;
   `SEC-002` records the amendment and what it gives up.
2. **`T-019`, `T-038` and `T-051` are all approved and on `main`.** `T-019` fixed the live defect
   — cancelling now reaps the worker's whole process group, and the `process_tree` marker is gone
   with the reason for it. `T-038` puts redaction in a formatter, so no call site can leak by
   forgetting, and its High `T038-R2` took three focused corrections. `T-051` is a decision,
   `ARC-004`. The `phase1-orphans-logging-lifecycle` branch that carried them is merged.
3. **Windows has runtime evidence, and it found a real bug.** `30293051118` first ran the
   process-tree suite on both platforms; `30302798113` then ran `T-019`'s new descendant tests
   there and **failed**, because `ctypes` had truncated the Job object's handle — invisible on
   Linux by construction. `30303348265` is green on every job, with all four grandchild tests
   and the containment check passing on `windows-latest` (1163 passed, 20 skipped). Phase 1's
   "verified on Linux *and* Windows" criterion has moved for the first time since it was written,
   and the move was worth more than the confirmation: pushing bought a defect nothing local
   could have found (`T019-R2`).
4. **`T-016` is merged to `main` at `33ebd11` and in review.** It is the first code that makes
   any of the engine visible to a person: paste URLs, probe one in a worker process, see title,
   uploader, duration, a decoded thumbnail and whether it is a playlist, pick a preset, queue them
   all. It also implements `ARC-004` — `DownloadManager.start()` now takes a `READY` job as well
   as a `QUEUED` one — which amends code `T-013` was approved with, and replaces the `T-013` test
   that asserted the older rule.

   Twelve deliberate weakenings were run against the new tests and all twelve were killed, but
   **three gates reported clean while covering nothing**, and that is the part worth keeping. The
   tab-order test derived its expected order from the same list the dialog hands to Qt, so it
   proved only that the list equalled itself and the mutation survived. The local type gate was
   the wrong *scope* — `mypy src` reads 33 files, the `windows desktop` job reads 69 including
   `tests/` — and CI found two real errors, one of which had silently stopped mypy analysing the
   rest of a test. The Windows UI Automation menu contract then caught a File-menu item this task
   added without declaring it. Each was corrected, and `ai/TESTING.md` §12 now states the scope
   difference that nothing had written down.

5. **`T-017` is implemented** (2026-07-28) and in review, so the critical path to the phase exit
   is now **`T-036` → `T-037`**. `T-036` depends on `T-016` *and* `T-017`, so composition begins
   when both clear review rather than when either does. *(This item used to end "DRM is
   the one uncovered mandatory area and still has no owner". It was neither: see
   `ai/TESTING.md` §12.)*
6. **`T-050`** — **Phase 2**, not Phase 1: the `history` table is still empty, and
   `IMPLEMENTATION_PLAN.md` puts `REQ-020`'s history persistence in Phase 2. This file's claim
   that `T-013` owned it was `STATUS.md` running ahead of both the plan and `T-013`'s own scope;
   the task entry records the two things still missing before it can be written honestly.

**What two review rounds cost, and what they bought.** Eight blocking findings across two
passes, every one real. The pattern worth remembering: **five of them were things that
computed the right answer and then failed to act on it** — the resolved yt-dlp version never
left the worker, the rendered path was validated and then re-rendered, ffmpeg was located and
never passed to the library, an audio codec was chosen and never requested, and the frozen
probe resolved an extractor name without loading the extractor. Each looked correct in the
code and produced no error.

The tests that missed them shared a shape too: they asserted on the *input* to a boundary
rather than on what came out the far side — a key present in an options dict, a local variable
on the worker's side of the queue. `ai/TESTING.md` §13 now has the general form of this.

## Known gaps not yet scheduled

- **`T-035` was missing from the plan.** `downloader/environment.py` was claimed by no task
  and `REQ-024` (ffmpeg detection) by nothing at all, though `ARCHITECTURE.md` §6 puts yt-dlp
  resolution at worker start and `T-012` therefore needs it immediately.
- **`T-034` was missing from the plan.** Filename safety and output-path containment
  (`core/paths.py`) belonged to no task, despite `ARCHITECTURE.md` §8 requiring every output
  path to pass through it and `ai/TESTING.md` §7 listing path safety as mandatory. Found while
  planning Phase 1; now filed and blocking `T-012`.

- **`T-033` — implemented, not closed** (`P1-R2`). The spec collects yt-dlp's submodules and
  data files; the probe resolves an extractor *by name* through the lazy machinery and asserts
  the bundled version against the pin (`T033-R1`). **The Linux half is now complete**, produced
  against a real frozen artifact on 2026-07-29 and independently re-verified by the reviewer:
  194 260 KiB, 1751 extractors, version against pin, frozen smoke green with no orphan. **The
  Linux negative is complete too, and it reopened the task** (`T033-R4`): removing
  `collect_data_files("yt_dlp")` strips all three YouTube solver assets — baseline has three, the
  mutant has zero — and **the probe still passes**, because it only instantiates `YoutubeIE` and
  checks a URL predicate. The frozen gate is therefore blind to package-data loss, which is a live
  regression risk rather than bookkeeping. `collect_submodules` is separately redundant for this
  pin, since `_extractors.py` has 928 static imports. What remains: extend the probe so the data
  removal fails, decide the submodule line, and the **Windows** build, which stays external.

  *(This said "the local probe is source-mode and proves nothing about the artifact", which was
  true when written and stopped being true when the artifact was built. `T033-R3`. An earlier
  version called the task "closed" here while listing it as pending above — the contradiction
  `P1-R2` reported.)*

## Open questions for the maintainer

- *(`ARC-003` was accepted on 2026-07-26, closing `T011-R5`. It narrows `ARC-002`'s "versioned
  internal contract" to version-controlled, and names its own expiry: any packaging in which
  parent and child become separately deployable re-opens the question.)*

- **Confirm the Phase 1 prerequisite amendment.** `IMPLEMENTATION_PLAN.md` said "Phase 0
  complete" while `TASKS.md` treated `T-010` as startable — and the plan outranks `TASKS.md`
  (`AGENTS.md` §5), so `T-010` was formally blocked. The prerequisite now reads "Phase 0's
  **deliverables** complete, merged and reviewed", separating those from the exit criteria,
  one of which needs a Windows machine. The Windows criterion is **not** waived; it still
  blocks Phase 0's formal exit and first release.

*(`OPS-004` was accepted on 2026-07-26 and is no longer open. Its installer half became
`T-039`, blocked until Phase 5 produces an installer.)*

## Blockers

- **`T-033` — blocked on `T033-R4` and the Windows build.** Its corrections are reviewed and
  verified, and the Linux frozen positive and negative are both done. The negative is what blocks
  it: the probe survives the loss of every YouTube solver asset, so it does not gate the data
  collection it exists to justify. A probe extension and a maintainer decision on
  `collect_submodules` are owed before the Windows build matters.

  *(This said "PyInstaller is in the `build` extra and absent from the working venv, so none of it
  can be produced here." **It is present, at 6.21.0** — `T-064` reinstalled the venv with
  `.[dev,build]` deliberately, and it was installed before that too. The reviewer placed the
  sentence at `a2966156`, well before any recent boundary, and asked for it as separate cleanup
  rather than folded into `T-064`. Corrected here; what blocks `T-033` is the hosted frozen jobs,
  not a missing local dependency.)*

*(the `T-003` logo blocker cleared on 2026-07-25 when the maintainer supplied the source
asset)*

## Repository

`github.com/kottmans/tracks-and-trails` — **private** for now, intended to go public later.

Commits are authored as `40611149+kottmans@users.noreply.github.com`, set in **repo-local**
git config so the maintainer's personal address never enters a history that will eventually be
public. This is per-repository, not global: a fresh clone, or a new repo, needs it set again.

To do when it goes public: state that contributions are accepted under MIT (`LIC-001`), and
re-check that no personal paths or local configuration reached the history.

## Environment baseline

Development machine, verified 2026-07-25:

| Item | State |
|---|---|
| Python | 3.14.6 (`/usr/bin/python3`) — the only interpreter; **confirmed sufficient** (`T-002`) |
| `pip` | 26.0.1, installed via `ensurepip --user` into `~/.local` (no sudo, no PEP 668 marker on F44) |
| Project venv | `.venv/` — **repaired 2026-07-28** (`T-063`). It had been installed from a parent directory, so the console script's shebang named a missing interpreter and the editable `.pth` pointed one level above the checkout: neither `tracks-and-trails` nor `python -m tracks_and_trails` worked, and every command used `PYTHONPATH=$PWD/src`. Re-running `pip install -e ".[dev]"` from the checkout fixed both; `docs/DEVELOPMENT.md` carries the symptom and the check. Editable install, PySide6 6.11.1, platformdirs 4.11.0. `comtypes` is a Windows-only dev dependency and is absent here by design |
| Dev tools | ruff 0.16.0, mypy 2.3.0, pytest 9.1.1, pytest-qt 4.5.0, PyInstaller 6.21.0, psutil — no longer packaging-only, the default suite needs it since `T-013` asserts on real processes |
| ffmpeg | present |
| git | branch `main` tracking `origin/main`; CI green on every push and PR (`T-006`) |
| Repository path | **Unsettled, and this row has now been wrong in both directions.** On 2026-07-27 the `T-013` session ran entirely in `/mnt/projects/software_projects/tracks-and-trails`, where `ls`, `readlink -f` (not a symlink) and every check and test agree, while `/mnt/storage` does not exist at all. The previous entry asserted the reverse. Rather than flip the value a third time: the working checkout is wherever the maintainer's shell says it is, and **this row should record a machine, not a truth** — one of the two paths is presumably a mount that is not always present. Needs a maintainer answer, not another edit |
| Windows environment | **CI runners only** — no local Windows machine or VM. The runner is a real desktop, not a bare headless box (`OPS-004`), and the dedicated `windows desktop` job uses it: the other jobs pin `QT_QPA_PLATFORM=offscreen`, that one does not |

## Current risks

| Risk | Impact | Standing |
|---|---|---|
| ~~PySide6 may lack Python 3.14 wheels~~ | — | **Closed** by `T-002`: PySide6 ships `abi3` wheels serving all Python ≥3.10 |
| No Windows machine — CI only | Interactive Windows behavior (screen reader, dialogs, keyboard, theming, installer) is **known-unverified**, not merely untested | Narrowed by `OPS-004`: the runner has a real desktop, so the objective half is automatable and `T-026` owns it. Only the subjective residue needs a person, and that still blocks first public release |
| `ARC-002` process model is unproven | It is the project's central architectural bet | **Mechanics validated on Linux** by a `T-002` probe (spawn under a live `QApplication`, structured progress over `mp.Queue`, instant terminate with no orphan). Phase 1 still proves it under a real download. |
| `ARC-002` may break once frozen — `spawn` from a frozen binary relaunches the app | Recursive launch; invisible until Phase 5 without a guard | `freeze_support()` + `T-020` frozen smoke test in Phase 0 CI |
| yt-dlp upstream churn | Ongoing maintenance cost | Confined to two modules (`NFR-008`); pinned fixtures |

## Notes

**Something downloads now — in a test.** What `T-013` connected is the *engine*: given a job in
the repository, a real spawned worker downloads a real URL to a real file and every transition is
persisted. `T-016` adds the first widget that calls it — the add-URL dialog probes, displays and
queues through `DownloadManager`, and its tests drive that path end to end.

**A user still cannot reach any of it.** `app.py` builds `MainWindow` with no manager, no job
store and no output directory, so File → Add URLs… is **disabled**, saying so in its status tip.
Supplying those three is composition (`T-036`); the first URL a *user* can download is `T-037`.
Treat `ARCHITECTURE.md` as the approved target rather than a description of what a user can do.

Precisely, recounted 2026-07-28 by parsing each module for anything beyond its docstring: of the
**35** modules under `src/`, **11 are still docstring-only stubs** and **24 have code**. Two of
the three changes since the 2026-07-27 count came from `ARC-005` — `persistence/store.py` and
`persistence/writer.py` are new modules, which is why the denominator moved as well as the split
— and the third is `ui/job_detail.py`, `T-017`'s progress view and **the second widget beyond the
shell window**. `ui/queue_view.py` stays a stub deliberately: a multi-job table is Phase 2, and
`T-017`'s scope is one job.

*(Before `T-014` this said 23 stubs and eight coded, recomputed at `697e024`; it had gone stale
across four tasks. The previous count of 31/13/18 was itself two modules stale, missing
`core/logging.py` and `downloader/process_tree.py`, which landed with `T-038` and `T-019`. Each
count is recounted rather than adjusted, which is how that was caught.)*

The `core/` modules remain **domain vocabulary plus pure functions** — what a job, a request and
a failure *are*, the rules for moving between states, and filename safety. `persistence/` is the
first module that keeps something across a restart.

**`TESTING.md` §12 holds the mandatory-area coverage count, and this file does not repeat it —
including the denominator.** Two statements of one number in one file was the defect the last
correction named; two files stating it was the defect that survived that correction, and it is
why "DRM is uncovered" outlived being true by four tasks. `T-058` recounted the rows; `T058-R1`
then found that the correction had *restated* the new number here three times while claiming this
very sentence was true. Pointing at a number and repeating it are not the same act, and only the
first one keeps.

---

## Criterion 8, second run — 2026-08-05

**39 of 41 rows passed, on `kirk`** — the historical result, first recorded as a clean pass and
corrected by `P2EXIT-R12`: **row 2.7** (`T-160`) and **row 3.15** (`T-161`) failed, and writing
*pass* beside a defect already filed is a verdict stated over its own evidence. **Both are since
dispositioned** — `T-161` corrected and approved, row 2.7 removed by `T161-R1` — so the next run
covers 40 rows. The record is
`ai/evidence/2026-08-05-criterion-8-second-run.md`, which states the head as the range
`6bae7ec..541b484` rather than a single sha: the maintainer did not record which was checked out,
and `git diff --stat` across it is `ai/TASKS.md` alone. A range a reader can verify is worth more
than a sha chosen for tidiness — `P2EXIT-R8` was evidence about a head that moved.

**Rows 3.6 and §5 were run for the first time**, and 3.6 immediately failed: a completed playlist
drew blank blocks, because `T-140`'s colour fix read `palette.highlight()` on a widget whose
palette carries the selection tint by `T130-R1`'s design. Fixed at `6bae7ec`. The row that caught
it had existed, unrun, since the checklist was written — which is the argument for running the
rows nobody has run rather than the rows that are easy.

**What the pass does not cover** is stated in the evidence and repeated here because it is what an
exit review needs: one platform (Fedora, not Windows), one runner who is also the person who
accepted the mockups, and four known defects present during the run (`T-161`–`T-164`).

## CI on the exit candidate — 2026-08-05

**Green on `541b484`, all five jobs**, run `31045159414`: `STARBASE coverage`, `frozen windows`,
`linux`, `frozen linux`, `windows desktop`.

**Dispatched rather than reused, and that is the point.** The last push-triggered run was on
`6bae7ec`; the two commits after it are prose and were correctly skipped by `paths-ignore`, so the
candidate head had no run of its own. Citing a neighbour's run and reasoning that the diff is
harmless is `P2EXIT-R8` exactly — the remedy is a run whose head *is* the head. Self-hosted
runners, so it cost no quota.

*(This said **"every Phase 2 exit criterion is now claimed met except 6(a)"**. It was written
before the review answered, and `P2EXIT-R11` then found criterion 1 broken by a change made after
its proof. Superseded — the current verdict is directly below.)*

**Current truth, 2026-08-05.** **All eight exit criteria are met and Phase 2 is exited**, signed
off at `8de5a72`. Criterion 6's review returned six verdicts before approving. Criterion 8's
evidence is the **40-row run**, a pass on
`kirk`, recorded in `ai/evidence/2026-08-05-criterion-8-third-run.md` — offered as *met on the
maintainer's evidence* and **accepted by the review**. This row has been claimed
met twice and reset twice, so its limits sit inside the claim: one platform, one runner who also
accepted the mockups, and four known Phase 3 defects present during the run.

---

## Phase 2 exit review — changes requested, 2026-08-05

**Four blocking findings** (`ai/REVIEWS.md`, 2026-08-05 second submission). At submission,
criteria 1, 6 and 8 were Not met. **`P2EXIT-R11` is since resolved, so criterion 1 is met** — this
line said *"criteria 1, 6 and 8 are Not met"* after that, which is the finding it sits under.
**Now: 6 alone** — `P2EXIT-R12` was answered by the 40-row run and criterion 8 is met.

| Finding | What | State |
|---|---|---|
| `P2EXIT-R11` | High. A finished probe's `Probing` outlived it against a `Ready` chip, so criterion 1's accurate-progress promise failed on the durable playlist route | **Fixed.** Stage precedence is gated by whether the stage can still be live in the current status |
| `P2EXIT-R12` | High. The second-run record said *"pass, all 41 rows"* while listing failures of rows 2.7 and 3.15 | **Answered.** Record corrected, `T-161` fixed and approved, row 2.7 removed by `T161-R1`, and **the 40-row run is a pass** — row 3.15 is observed rather than inferred, which was the finding's whole point |
| `P2EXIT-R13` | Medium. The `T-152` focus correction fired on every model reset from either view, taking the keyboard off toolbar controls | **Fixed.** First rows only, in the visible view |
| `P2EXIT-R14` | High. Plan and status carried incompatible live criterion-8 verdicts | **Resolved at `e94b412`**, after five sweeps. Each earlier one corrected the occurrence it was looking at and left siblings behind — the finding, reproduced by its own corrections |
| `P2EXIT-R15` | High. Passages written before the 40-row run still said criterion 8 awaited it, `P2EXIT-R14` was open, and row 3.15 was unrun | **Resolved at `8de5a72`.** The same shape a sixth time, and the first five were about *stale* claims while this one is about claims that were **true when written** and were overtaken |

**The pattern in three of the four is mine and it is one pattern.** `P2EXIT-R11` and `P2EXIT-R12`
are both a claim stated over the top of contradicting evidence I had already written down —
`T-162` was filed as a known defect while criterion 1 was called met, and the checklist record
listed its own failures underneath a *pass*. `P2EXIT-R14` is the third instance: one occurrence
updated and the siblings left behind. `P2EXIT-R10` and `COORD-R5` are the same class, and this is
the second exit submission it has blocked.

### What criterion 8 needed, and how it was met

**Row 2.7 has been removed from the checklist**, by the reviewer's direction in `T161-R1`. It was
authored on 2026-08-05, after the closed list, to describe `T-160` — so it could never pass while
that defect lived, and keeping it made a Phase 3 task into a Phase 2 exit gate. **Neither of the
two ways out I offered was taken, and both were worse:** amending the row to tolerate the overlap
repeats `P2EXIT-R12`, and requiring `T-160` for exit expands the closed list. The property is
unweakened — it now lives in `T-160`'s acceptance evidence — and the 39/41 record stands as what
was observed rather than being recomputed. Forty rows remain.

*(This said **"row 3.15's defect is fixed and the row is unrun"**, and it was true when written.
The 40-row run of 2026-08-05 observed it: `ai/evidence/2026-08-05-criterion-8-third-run.md`.
Superseded, and kept because it is the sentence `P2EXIT-R12` was answered by.)*

## The 40-row run — 2026-08-05

**Pass, 40 of 40, on `kirk`**, across `376407f..165b6e4`: no file under `src/` or `tests/` differs
across that range, so it is one build. `ai/evidence/2026-08-05-criterion-8-third-run.md`.

**Row 3.15 is why it existed.** `T-161` was fixed and had never been *observed* fixed, and
`P2EXIT-R12`'s point was that a fix is not an observation. The three runs are a sequence rather than
a repetition: eleven defects found, then 39 of 41 with two named failures, then 40 of 40 — and the
count changed because row 2.7 was **removed** by `T161-R1`, not because a failure was rewritten.

**The one-platform limit is a maintainer ruling.** Asked whether criterion 8 could rest on
Fedora alone, the maintainer answered on 2026-08-05: *"I'm okay with criterion 8 resting on one
platform (linux) for now."* Recorded as a ruling rather than left as a gap, because an implementer
who **could not** get Windows evidence and one who was **told it was not required** look identical
in a record that does not say which. CI runs the suite on Windows and `windows desktop` is green on
the candidate; what is deliberately unevidenced is a *person looking at the window* there — and
`T-134`'s hover defect and `T-149`'s missing `:checked` state are exactly the kind of thing only
that catches, so the residual is accepted rather than argued away.

**CI is green on the candidate**: run `31051896815` on `165b6e4`, all five jobs — `STARBASE
coverage`, `linux`, `frozen linux`, `windows desktop`, `frozen windows`.

**Criterion 6 was the last one open, and it was not the implementer's to close. It closed on 2026-08-05 at `8de5a72`.**

**`P2EXIT-R15` is a different failure from the five before it, and the difference is the lesson.**
`P2EXIT-R14` was about claims that had gone *stale* — corrected, then found again one scope out,
five times. `R15` is about claims that were **true when written** and were overtaken by an event:
the 40-row run turned *"criterion 8 awaits the run"* from accurate into false in one moment, across
every passage that said it. **Searching for wrong-looking sentences cannot find these**, because
they were not wrong. The check that works is the opposite direction: after an event changes a
criterion's state, sweep every passage that *mentions that criterion*, whatever it says.

**That rule was written here and then not followed, which is how `R15` survived its own
correction.** The next sweep grepped a *vocabulary of staleness* — `awaits`, `owed`, `Not met` —
and missed `awaiting`, `owes`, `needs`, and one line reading only *"Now: 6 and 8."* Enumerating the
ways a claim can be stale is the same error one level up from enumerating the stale claims: **the
set of wordings is unbounded and the set of mentions is not.** The sweep that finally worked listed
every occurrence of *"criterion 8"* in both records — sixteen of them — with no filter at all, and
read each one.

---

# Phase 2 exited — 2026-08-05

**Signed off at `8de5a72`** by the independent exit review. **All thirteen deliverables approved,
all eight exit criteria met.**

| Evidence | |
|---|---|
| Suites | 1884 passed / 11 skipped, 307 integration; ruff and mypy clean |
| CI | Run `31051896815` on `165b6e4`, all five jobs including `windows desktop` |
| Built window | **40 of 40** checklist rows, `kirk`, Fedora |
| Soak | **60 of 60**, `Spock`, `ef21e34`, P = 0.042 against the 2-in-39 baseline |

**The review returned six verdicts before approving**, and what they caught is worth carrying into
Phase 3 more than the approval is:

- **`P2EXIT-R11`** — criterion 1 **silently broken by a change made after its proof**. A finished
  probe's stage outlived it. It had been filed as a Phase 3 task while the criterion was called
  met; the closed-list rule decides which task *owns* a defect, not whether a criterion holds.
- **`P2EXIT-R12`** — a checklist record reading *"pass, all 41 rows"* while listing failures of two
  of those rows. **A fix is not an observation.**
- **`P2EXIT-R13`** — a correction that seized the keyboard on every model reset, far wider than the
  seam its own source disclosed.
- **`T161-R1`** — an implementation of the option the task had explicitly ruled out, in a task
  whose own acceptance criteria forbade it.
- **`P2EXIT-R14` and `R15`** — records disagreeing with each other, six sweeps between them.

**Not one of the six was a defect a gate could have caught, and four were the same shape: a claim
stated over the top of evidence already written down.** That is the thing to watch in Phase 3, and
it is recorded here rather than in a commit message because it outlives the commit.

**The one-platform residual stands as a maintainer ruling**: criterion 8 rests on Fedora, CI covers
the suite on Windows, and no person has looked at the window there.

