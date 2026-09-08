# TASKS.md — Tracks & Trails

**Purpose:** Current work queue and stable navigation to completed tasks.
**Owner:** Planner (priorities); Implementer (current task/status); Reviewer (review disposition)
**Last updated:** 2026-09-08
**Update when:** Work starts, changes scope/status, completes or is cancelled.

Statuses: Proposed · Ready · In Progress · Blocked · In Review · Complete · Cancelled.
IDs are never reused. Current phase and blockers are in [STATUS](STATUS.md).
Read [In Review](#in-review), [Ready](#ready) or the applicable Proposed section;
completed entries retain their original heading/status and link to archived detail.
`T-260` remains in full because a capability test consumes its evidence text.

At completion, the task/status owner removes duplicate narrative, preserves unique
facts, and archives closed detail only when it obstructs active work. Archived
records retain their evidence and attribution; open findings keep an explicit route.
The [previous queue preface and closed records](archive/TASKS-completed-2026-09-08.md)
are historical, not a second work queue.

## In Review

### T-300 — `AGENTS.md` is 628 lines and is loaded on every task

**Status:** In Review — revision 2026-09-08.2 adopted; independent review pending.
**Owner:** Documentation Maintainer (Codex for this implementation, by direct request)
**Priority:** Current maintainer request
**Phase:** Phase 4 (documentation system; not a plan deliverable)
**Depends on:** No implementation dependency. T-299 remains In Review with its own blockers.
**Relevant context:** DOC-007; AGENTS §§1–13; TESTING §§3/14.
**Affected surfaces:** AGENTS, README, DEVELOPMENT, project coordination documents and archives.
**Risk:** Medium — preserving evidence, task consumers and references during reorganization.
**Required checks:** Ruff; full suite; task-placement and documentation-consumer checks;
mechanical section/record/link preservation checks.

#### Scope amendment — 2026-09-08

The maintainer requested adoption of the revised standards across this project.
This expands T-300 to reader routes, retention, decision navigation, proportional
metadata and factual prose. The former dependency on T-299 completion is removed
for this documentation work: no section renumbering or product correction is needed.
T-299's privacy and transcript findings remain its responsibility and remain open.
The original brief is retained in the [task archive](archive/TASKS-completed-2026-09-08.md#original-t-300-brief).

The maintainer subsequently requested relocation of unique status evidence and
removal of the status archive. The [dated evidence supplements](archive/TASKS-completed-2026-09-08.md#historical-evidence-supplements--2026-09-08)
retain the observations and limitations alongside the task records. This explicitly
retires the one-time STATUS snapshot; the pre-existing task and review records
remain intact. DOC-007 records this retention amendment. No external standard changes.

#### Acceptance criteria

- Adopt DOC-007 without applying the web profile to this desktop product.
- Preserve numbered AGENTS sections, safety/permission boundaries and the accepted role mapping.
- Keep one review file; route live policy to TESTING and templates to PROMPTS.
- Preserve dated reviews/decisions and archived records byte-for-byte.
- Keep the status concise, open tasks unchanged in scope, and completed-task anchors reachable.
- Retain documentation inputs consumed by tests and validate the changed navigation.
- Use neutral factual new prose and honest metadata without rewriting historical provenance.

#### Validation and limits

Results are recorded in `docs/project/evidence/2026-09-08-T300-documentation-adoption.md`.
Overall review base: `f465688`; original adoption: `d88e62e`. The status-retention
follow-up is the commit carrying this amendment, based on `d88e62e`.
Both await independent review.
No application, test, dependency or CI behavior changes. No independent approval,
Windows runtime validation, publication or push is claimed by this implementation.

### T-299 — Adopt the neutral coordination layout and the public-ready baseline

**Status:** In Review — corrections returned 2026-09-08 for focused re-review. Reviewed at
`cca7db2..1d43c21`: **Changes requested**, one High and one Medium, both corrected below. The
convention was revised to **2026-09-08.1** and the maintainer decided this repository becomes
public; `DOC-006` records the adoption and its four deviations.

**Owner:** Documentation Maintainer, with the Implementer for the path-dependent code
**Priority:** High — it gates making the repository public, and it is the kind of change that gets
worse the longer it is split across commits
**Phase:** Phase 4 (documentation system; **not** a plan deliverable)
**Depends on:** nothing
**Relevant context:** `DOC-001` (the adoption this amends), `DOC-006` (this one), `AGENTS.md` §3
and §6, `docs/project/TESTING.md` §4
**Affected surfaces:** all of `docs/project/`, `README.md`, `SECURITY.md`, `AGENTS.md`,
`.github/workflows/`, `pyproject.toml`, `.gitignore`, `.gitattributes`, `.gitmessage`,
`tools/windows/run-on-starbase.sh`, and every test and source file naming a coordination document
**Risk:** Medium — 1473 path references across 127 files, and a rename that silently misses one
leaves a broken link nothing fails on
**Required checks:** `ruff check .` · `ruff format --check .` · `mypy src tests` · the full suite

#### Scope

One bounded migration, as the convention's retrofit section asks:

- `ai/` → `docs/project/`, by `git mv`, with every path reference updated.
- `SECURITY.md` added at the root; the application handles cookie material and proxy credentials,
  runs on a network, and is intended for distribution.
- `README.md` rewritten product-first. It said *"pre-alpha, planning only. No code exists yet"*
  beside 58 source modules and a working application.
- `Owner:` metadata made capability roles in the three documents that named a tool.
- `tools/windows/run-on-starbase.sh` no longer carries an account and a LAN address as its default;
  it takes `STARBASE_HOST` and refuses to run without it.

#### Acceptance criteria

- ~~No tracked file refers to a coordination document by an `ai/` path, and no reference is left
  dangling. Bare `ai/` mentions inside historical prose are deliberately retained.~~
  **Amended 2026-09-08 by `T299-R2`.** The original criterion is what produced the finding: it
  treated *every* `ai/FILE.md` as a link. The residual criterion is that **current-truth documents
  name the current location, and historical records keep the paths they were written with** — in
  `REVIEWS.md` and the decision entries a path is often a fact (a command that ran, a review's
  write set, a `FILE.md:NNN` citation, a handoff filename), and rewriting it changes the record.
- `pyproject.toml`'s `docs/project/evidence/*` per-file ignore reaches the evidence scripts it is
  written for, rather than silently matching nothing.
- The four Python path joins that named `"ai"` as a segment — which no string rewrite could see —
  are found and corrected. They were in `test_task_placement.py`, `test_option_audit.py` (two) and
  `test_capability_guards.py`.
- The four gates pass: `ruff check .` (which covers the whole tree, not `src tests`),
  `ruff format --check .`, `mypy src tests`, and the full suite.
- `DOC-006` records the convention revision, the profile, the delivery target, and every
  deliberate deviation.

#### What the migration cost, and what it did not

**The longer paths broke the line-length gate, and that is the whole of the mechanical damage.**
`ai/TASKS.md` → `docs/project/TASKS.md` adds ten characters, which pushed **105** lines past 100
columns. 96 were prose in comments and docstrings and were re-wrapped; **9 were code** — string
literals and docstring summaries — and were split by hand.

**A first re-wrap attempt was reverted, and the reason is worth keeping.** It selected paragraphs
by indentation and comment prefix, which is not the same question as *is this line prose*. It
wrapped inside string literals in eight files and left them unparseable. The replacement asks
`tokenize` instead: a line is eligible only when it is a `COMMENT` token, or lies strictly between
the first and last row of a multi-line `STRING`. Quote lines are never touched, so a wrap can no
longer land inside a literal.

**Content was verified preserved, not assumed.** Every file was compared against its `HEAD`
version under a normalization that applies the path rewrite and collapses whitespace and comment
markers. 291 files matched exactly; the 5 that did not are the 5 with deliberate wording changes.
Re-wrapping moves text between lines, so a diff cannot answer this and a review reading 1473
changed references will not either.

#### Correction round, 2026-09-08

**`T299-R1` — High, false privacy guarantees in `SECURITY.md` and `README.md`. Corrected.**

The review's probes were reproduced before anything was written. `redact()` and a real
`JobRepository` write, at this head:

| Probe | Result |
|---|---|
| `redact("wrote /home/sean/Videos/holiday.mp4")` | **unchanged** — the document claimed home-carrying paths were redacted |
| `redact("loading cookies from /home/sean/session.txt")` | **unchanged** — recognized only when the name looks like a cookie store |
| `redact("... https://example.invalid/watch?v=abc123&list=PL9")` | query stripped — the document claimed URLs were logged verbatim |
| `error_message` = `"download failed: /home/…/cookies.txt"` | **stored verbatim in the raw row** |

**The repository's own record already said so.** `T014-R1` states that `error_message` is an
unrestricted database sink and that *"T-038 redacts logs; it cannot redact a separate database
write."* I cited that review in `SECURITY.md` as evidence the boundary was sound, and then wrote a
guarantee it contradicts. The failure was writing a security claim from the design's intent rather
than from a probe, in a document whose whole purpose is to be believed.

What is written now is the measured behavior: what is refused at construction (structural), what
the log's pattern set catches, and the two sinks that are **not** redaction sinks and are
deliberate. `remember_a_secret()` is unchanged — no production caller registers anything.

**`T299-R2` — Medium, historical evidence rewritten. Corrected.**

`REVIEWS.md` (513 references) and `DECISIONS.md` (48) were restored from `cca7db2` to the paths
they were written with, and a navigation note at the top of each says where the documents live now.
Four recorded facts in `TASKS.md` and `STATUS.md` were restored individually — a
`git checkout -- ai/TASKS.md` that was actually run, a `git diff --stat` describing which file a
past range touched, and two provenance notes naming where a past reading came from. Live
navigation in the current-truth documents keeps the new paths.

`DOC-006` deviation 2 is rewritten to the rule this establishes, and says plainly that the original
version was convenient and untested.

**Non-blocking, corrected:** the machine-address claim in `SECURITY.md` (it asserted an absence
while two RFC1918 addresses remain in review entries — now stated); the `README.md` timing and
verification claims (a desktop-specific wall-clock figure removed; "verified on Windows" narrowed
to what CI runs, since this head has no Windows run); and the last current-policy `ai/` reference,
in `docs/project/TESTING.md`'s documentation-only row.

**Unchanged by this round:** the suite, lint, formatting and types all still pass, and no source
behavior was touched. Windows remains unverified at this head.

#### Correction round 2, 2026-09-08 — after reading the recorded review

The first correction round was written from a summary of the verdict. Reading the full record in
`docs/project/REVIEWS.md` found four things the summary did not carry:

- **`T299-R4` was only half done.** The timing claim was removed, but *"every push, full suite on
  both"* remained in two places, and it contradicts `ci.yml`'s `paths-ignore`: documentation-only
  pushes are deliberately excluded (`OPS-011`). Both are now qualified by the real triggers. The
  displayed suite command is `-n auto` now, matching how the figure was actually measured.
- **`T299-R1` asked for `DAT-003`'s amendments, not its superseded scope table**, and the first
  correction did not use them. `DAT-003` is titled *"a stored diagnostic is verbatim; cookie paths
  inside one are accepted"* — so a cookie path in a diagnostic is a **recorded, reasoned decision**,
  not the caller-discipline gap the first correction described. `SECURITY.md` now states it that
  way, and says why the alternative was rejected twice. A probe also confirmed the review's point
  that **userinfo**, not only a query string, survives in the stored URL; the table says so.
- **A claim in the submission handoff was false.** It said every `src/` hunk is inside a comment or
  a docstring. `persistence/db.py` updates a path inside a runtime `ValueError` message. The edit is
  intentional and the string is a diagnostic, so behavior is unaffected — but the claim was an
  overstatement I had not checked, and the review's AST comparison is what caught it.
- **The fixture change was unrequested scope and is reverted.** The review assessed
  `tests/unit/test_workflow_triggers.py`'s synthetic `ai/**` YAML and ruled it not a finding, since
  it never reads a repository path. Changing it anyway put an unreviewed edit into a correction
  batch.

#### Process failure in this round: the recorded review was destroyed and restored

**While correcting `T299-R2` I overwrote `docs/project/REVIEWS.md` with its version from `cca7db2`,
deleting the review record committed at `66184fd` — 133 lines holding `T299-R1` through `T299-R5`.**
The deletion was then committed at `e43f58f`.

**How it happened.** I checked that `git status` was clean and read that as *nothing to lose*. It
was clean because the review had already been **committed**, on top of the head I was working from.
A whole-file restore from an older commit discards every later change to that file, committed or
not, and I used one on the single append-only file the reviewer owns.

**What made it recoverable** is that the record was committed, so `66184fd` still holds it. It was
restored by re-appending the 132-line block that follows `1d43c21`'s line count, then verifying the
result is byte-identical to `66184fd`'s copy. Had the reviewer left it uncommitted, it would have
been gone.

**The rule this earns:** a whole-file restore from an older commit is not a way to revert an edit —
revert the edit. `AGENTS.md` §6 already makes `REVIEWS.md` append-only and reviewer-owned, and a
blind overwrite is precisely what that ownership forbids.

#### Out of scope

- **`AGENTS.md`'s length.** 628 lines against the convention's ~200–300 review trigger. Filed as
  `T-300`; see `DOC-006` deviation 1 for why it is not done here.
- **Any rewriting of history.** Eighteen commit subjects name the reviewer. `AGENTS.md` §6 and the
  convention both forbid cosmetic rewriting of the development record, and the coordination
  documents cite several hundred short SHAs that a rewrite would invalidate.
- **Partitioning `REVIEWS.md`.** Recommended for parallel work; this project is serial.
- **`CHANGELOG.md` and `docs/RELEASE.md`.** They become required at the first tagged release,
  under Phase 5.

#### Not known: whether the public repository settings match the workflow controls

The trigger set is enforced in-repository by `tests/unit/test_workflow_triggers.py`. The
**repository settings** that sit behind it — fork pull-request approval, who may run workflows,
runner-group scope — are GitHub state, not files, and no test here can see them. They are the
maintainer's to set before the repository is made public, and this task does not claim them done.


## Ready

### T-238 — An xdist UI worker segfaults while entering a thumbnail-store lifetime test

**Status:** **Ready — the guard is Approved at `9e5feae`, and criterion 4 is sharper rather than
met.** The second of its two named steps ran on 2026-08-30, in three arms. **No widget the
application's own routes opened takes the collector's route**; the 95 that survive product shutdown
are `T-273`'s documented baseline and go when its owner step is applied. **The collector-runs-a-Qt-
destructor route is now reproducible on demand** — and doing it aborts the process — but only for
widgets the test helper owns parentless, and on the main thread, so it is **not this task's crash**.
See *Criterion 4, 2026-08-30* and *2026-08-31* below. **The real-session probe has now run on
both pools** — the update route 60 times isolated and once on a real display, the staged-row
thumbnail pipeline once on a real display — and **both were `INCONCLUSIVE`**: the collector never
handled a widget on any of those threads. What criterion 4 still lacks is a product-owned widget
reaching the collector, not another session.

**30 *additional* contended runs, 2026-08-20: zero crashes. The cumulative record is 90 runs, 50 of
them contended.** 40 idle, **12 under 20 busy loops**, **8 beside an `-n auto` integration batch**
— all three rows already in the conditions table below — plus these 30.

*(**The first version of this section said load "had never been tried" and put the total at 70.
Both were wrong, and the entry itself said so** — `T238-R4`. Rows two and three of its own
conditions table are 20 loaded runs, and the paragraph beneath them records that saturation
**refuted** the recommendation to try load. **I acted on the recommendation and not on the
refutation two paragraphs below it**, which is this project's most-documented failure shape: the
sentence most likely to be stale is the one that says what to do next. Nothing was measured wrongly;
the campaign was described as pulling an untried lever when it was adding a fourth condition to
three.)*

**What the design adds over the prior 20, which is the only reason to keep the runs.** The earlier
loaded rows used 20 busy loops (CPU pressure without allocator or GIL contention) and a single
`-n auto` integration batch that **finishes and leaves the target running unopposed**. This ran
**three** `pytest tests/integration -n 4` batches **continuously**, restarting each as it ended, so
every measured run was contended **end to end by real Python allocation and Qt teardown** rather
than by spinning arithmetic. Load achieved on 20 cores: **median 21.4, max 23.9, min 14.2**. Every
run: `3276 passed, 18 skipped`. **It does not reproduce the fault either**, which is the fourth
condition to say so.

**The instrument was proved before the zero was believed.** `T238-R1`'s inverted-order reproduction
was re-run first: swapping the two calls in `tests/ui/conftest.py` still kills the helper subprocess
with **`assert -11 == 0`**, deterministically, on this machine today. **The first attempt at that
control printed a clean 91-passed** — because the reproduction lives in the helper subprocess, not
in an ordinary UI file — which is exactly the blind-probe failure the control exists to catch.
`systemd-coredump` was also confirmed capturing that SIGSEGV, so the dump path was live.
**Independent of the log grep, `coredumpctl` reports no dump of any kind** across the campaign.

*(**The first campaign design was wrong and was discarded after two runs.** It started one competing
batch per iteration and waited for it, so the 39-second target finished and then ran **unopposed**
for the rest of the iteration — a load experiment measuring an idle machine. Recorded because a
negative result from that design would have looked identical to this one.)*

**So repetition is spent at 90 runs across four conditions**, and **criterion 4 is unchanged** —
product-versus-harness is still unestablished. **What it needs is not the guard firing**, and the
first version of this section said it was (`T238-R4`): the 2026-08-16 measurement moved criterion 4
on, and its two named next steps stand — **run the probe against a real session on a display**,
which `tests/integration` cannot answer because a `QCoreApplication` process has no widgets for the
probe's own control, and **establish whether any `QWidget` here participates in a reference cycle**.
A guard firing on a real test would still be evidence; it is not the plan.

**The second of those was attempted on 2026-08-20 and the run refused** (`T238-R5`) — the surfaces
were still retained at the end, so the collector never classified them and its zero says nothing
about cycles either way. **The step is not done and the criterion is not answered**; what the
attempt did produce is `T-273` and a written list of what a run that answered it would have to do.
See *The second step, attempted 2026-08-20* below. *(This paragraph said the two steps "stand", full
stop, for two commits after one of them had been tried — a summary going stale against evidence
lower in the same entry, which is `T238-R4`'s finding recurring in the paragraph `T238-R4`
corrected.)* `T238-R1`, `T238-R2` and `T238-R3` are all **Resolved**. What is delivered is a
harness guard, not a diagnosis: **product-versus-harness is still unestablished**, and this entry
sits under `## Ready` rather than `## Complete` for exactly that reason.

**The review reproduced a segfault, and that is the first one anybody has reproduced here.** Not
the original crash — this investigation has never reproduced that in 60 runs — but its
*mechanism*: swapping the fixture's two calls so the orphan scan runs **before** the drain kills
the helper subprocess with **SIGSEGV (-11), deterministically**. Enumerating live widgets while
deletions are still queued walks a list Qt is about to change. **The order of those two lines is
therefore load-bearing**, which nothing in my own evidence had established, and both the conftest
and `tests/qt_lifecycle.py` now say so where somebody would otherwise tidy them.

**Also verified independently:** all four mutations failed **only** their intended outer
regression, and both guard regressions passed across **20 invocations, 40 tests**.

#### The criterion-6 ruling — maintainer, 2026-08-13 (`T238-R2`, Resolved)

**Criterion 6 is replaced, deliberately and on the record.** It asked that repeated `-n auto` runs
*"materially exceed the pre-fix sample"*, and the pre-fix sample is **60 clean runs**: a larger
clean sample cannot distinguish *the guard worked* from *the crash was always this rare*, which
the reviewer states as plainly as this entry does. **In its place stands `T238-R1`'s evidence** —
each half of the guard fails its own regression under mutation, and neither can be deleted while
the suite stays green.

*(Recorded as a replacement rather than a waiver, which is `T198-R5`'s lesson in a different
costume: a criterion that quietly stops being met is a gate that has been moved without anybody
saying so.)*

#### The criterion-4 ruling — maintainer, 2026-08-13 (`T238-R2`, Resolved)

**`T-238` stays open, and the guard stays in.** Product-versus-harness is not established and
cannot be inferred from a green suite. If the guard ever fires on a real test, that *is* the
evidence criterion 4 asks for and the task closes on it; until then the entry stays open rather
than being closed on the deliverable it happened to produce.

#### What was built — 2026-08-13

**Measurement chose the predicate, and the obvious one was wrong.** *"After every test, assert no
`QAbstractItemView` is awaiting deferred deletion"* is what the entry proposed, and the closest
thing to it that can be observed — *no view created by this test is still alive* — **fails 802 of
839 `tests/ui` tests**. That is not a leak rate: a view parented into a widget tree is **owned**,
and dies with its owner. Two narrower predicates over the same suite return **zero**: a view alive
with *no parent*, and a view alive whose wrapper is otherwise unreferenced. **So what no correct
test produces is an ownerless view**, and that is what `assert_no_orphaned_views` forbids.

**The hazard the stack actually shows is *when*, not *what*.** `_Py_HandlePending` means the
deletion ran at an arbitrary bytecode boundary — inside whatever test was executing, which is why
xdist blamed a file that constructs no view in 2600 lines. So the guard has two halves, and only
one is an assertion:

- **`settle_deferred_deletions(app)`** — `gc.collect()` then
  `sendPostedEvents(None, DeferredDelete)`, at every `tests/ui` test boundary, on the main thread.
  **Measured: 431 of 839 tests had objects awaiting collection or deletion at that point, totalling
  15 457 widgets, 1 001 of them views.** Those destructions were previously running inside later
  tests. **It fixes no *pre-existing* failing assertion** — the suite was green with and without
  it — which is why `T238-R1` was right that it needed evidence of its own, and now has it below.
- **`assert_no_orphaned_views(app)`** — fails the test that leaves a view with no parent, naming
  it. `tests/ui/_leaks_a_view.py` leaks one deliberately and
  `test_a_test_that_leaks_a_view_is_the_test_that_fails` runs it in a subprocess and requires both
  a non-zero exit *and* the orphan message, so a guard reduced to a no-op cannot pass it.

#### `T238-R1` (Medium) — Resolved. The drain had no evidence of its own. It has now.

**The finding is right and it is the one I would have missed.** The leaked-view regression proves
the *assertion* and nothing else: it still fails with `settle_deferred_deletions` reduced to a
no-op, and stashing the whole conftest conflates the two halves. Neither shape the drain exists
for is visible to a parentless-view check — the reviewer's own probe makes the point, a cyclic
parentless view being collected *during* the drain and a parented one dying with its root.

**`tests/ui/_carries_a_deletion.py` is an ordered pair, and the order is the assertion.** The
first test leaves two carry-overs that the orphan check cannot see — a widget tree held only by a
reference cycle, and a `deleteLater()` posted on a **still-parented** view from a fixture
finalizer, after pytest-qt's own drain. The second asserts, **before spinning anything**, that
neither is alive; spinning first would deliver the deletion itself and pass against a conftest
that does nothing.

**Mutated statement by statement, against the regressions rather than against the bad tests:**

| Removed | Which regression fails |
|---|---|
| the whole `settle_deferred_deletions(qapp)` call | `test_a_pending_deletion_does_not_reach_the_next_test` |
| `gc.collect()` alone | the same one |
| `sendPostedEvents(None, DeferredDelete)` alone | the same one |
| `assert_no_orphaned_views(qapp)` alone | `test_a_test_that_leaks_a_view_is_the_test_that_fails` |

**Each half now fails exactly one regression and the other half's stays green**, which is what
makes either one deletable-with-a-test-failing rather than deletable-in-silence. *(The first
version of this measurement ran the deliberately-bad node ids directly and reported the orphan
mutation as "survived" — the bad test **passing** is precisely what its outer regression detects,
so the mutation has to be aimed at the regression, not at the bait.)*

**Cost, measured rather than estimated: `tests/ui` goes from 106.65 s to 121.50 s**, +14.9 s or
**+13.9%**, almost all of it `gc.collect()` per test. Paid deliberately: the alternative is a
native crash attributed to the wrong test, which cost this entry sixty runs and two days.

**Deliberately not extended to `tests/integration`, and that is a decision with a measurement
under it rather than a boundary drawn by hand.** The same predicate was run over that suite:
**0 of 430 tests would trip it**, and the whole suite passes with the drain applied at every
boundary, costing 268.34 s → 281.79 s (**+5%**). So extending it is available and safe whenever
somebody wants it. It is not done here because the crash was in the parallel unit/UI command and
the ruling authorised that guard; widening the blast radius of a change on the same day it is
built is how a small correction becomes a large one.

#### The guard ruling — maintainer, 2026-08-13

**Build it.** The entry conditioned the guard on product-versus-harness being established and then
could not establish it: 60 runs did not reproduce the crash, so repetition is spent at worse than
1-in-60. **The guard is itself the instrument that would establish it** — it fails at the test that
leaks the view, by name, on an ordinary run, instead of waiting for a segfault to land somewhere
else. `docs/project/TESTING.md` §13 already states the principle: the useful signal is the one at the cause.

*(This is a ruling about the *order* of the criteria, not a waiver of any of them. The guard is the
fourth criterion's harness-only branch, taken before the branch condition is proved, because
proving the condition is what it is for.)*

**Status of the original filing** — corrected 2026-08-12 from the retained run log. One of nine observed
`-n auto` unit/UI runs ended when worker `gw7` segfaulted; eight sibling runs passed. **This was
not an assertion failure, and one event in nine runs is a sample, not a measured rate.** Forty
further repeated runs were started to reproduce and characterise it; their result is not yet
recorded here.
**Owner:** Implementer
**Priority:** High — this is a native process crash in the supported parallel test command, not a
timing assertion, and its Qt/PySide lifetime stack belongs to the evidence class that made T-074
and T-128 high-value investigations. One observation does not yet establish product reachability.
**Phase:** Phase 4 — maintenance. **Not a plan deliverable.**
**Depends on:** nothing
**Relevant context:** `T118-R13`, `T-074`, `T-128`, `T-123`,
`tests/ui/test_row_delegate.py::test_deleting_a_closed_store_neither_waits_nor_is_emitted_through`,
`ui/thumbnails.py` (`ThumbnailStore.close`, `_Sink`, the shared `QThreadPool`)
**Affected surfaces:** unknown until the faulting object's lifetime is identified. The active test,
Qt test fixtures/teardown, and `ui/thumbnails.py` are candidates, not conclusions
**Risk:** High to gate integrity and potentially Medium to the product — a worker process is lost;
whether supported application behavior can reach the same native fault is unverified

#### What the retained run actually says

xdist reported:

```
[gw7] node down: Not properly terminated
worker 'gw7' crashed while running
  'tests/ui/test_row_delegate.py::test_deleting_a_closed_store_neither_waits_nor_is_emitted_through'
```

Immediately before that, Python's fault handler reported **`Fatal Python error: Segmentation
fault`**. The current Python frame was inside `occupy_pool()` at `store.pool.start(_Blocker(gate))`,
before the test reached any of its three assertions. The C stack passes through
`QObject::disconnectImpl`, `QAbstractItemView` destruction, and Shiboken's
`BindingManager::runDeletionInMainThread`.

That stack makes Qt/PySide object lifetime and deferred destruction a concrete lead. It does **not**
identify the faulting object, establish that the thumbnail store caused the crash, distinguish an
object left by an earlier test from one created here, or prove identity with T-074/T-128. A native
Qt crash is the shared finding class; a shared cause remains to be demonstrated.

#### The 40 runs, and what the retained stack narrows it to — 2026-08-12

**40 of 40 `-n auto` unit/UI runs passed. Zero crashes, zero failures.** On an otherwise idle
machine, against one observation in nine.

**That is a result, not a null.** The original run happened while the machine was also running
other pytest batches — the same contamination that made `T-228`'s *"one in three"* wrong. **The
one-in-nine figure is not a rate**, and this entry's Status already says so; 40 idle runs now say
it from the other side. Whatever this is, **idle repetition of the supported command does not reach
it**, so the next attempt should reproduce under deliberate host load, as `T-228`'s did.

**The raw stack is retained** at `docs/project/evidence/T238-SEGFAULT-gw7.txt` — `docs/project/evidence/README.md`'s
test is *"could I get it back"*, and 40 runs say no. Trimmed to the crash; the warnings summary is
not evidence.

**What the C stack narrows, read rather than skimmed:**

```
_Py_HandlePending
  → Shiboken::BindingManager::runDeletionInMainThread
    → QAbstractItemView::~QAbstractItemView
      → QObject::disconnectImpl        ← faults here
```

Two things follow, and only two:

- **The faulting object is a `QAbstractItemView`.** `tests/ui/test_row_delegate.py` imports
  `QApplication` and `QStyleOptionViewItem` from `QtWidgets` and **nothing else** — no view class —
  and constructs no view anywhere in its 2600 lines. `ThumbnailStore` is a `QObject`, not a view.
  **So the destroyed object was not created by the test xdist named**, which is exactly the
  attribution trap this entry warned about: *"while running"* names the active node.
- **It ran at `_Py_HandlePending`** — a deferred deletion executing at an arbitrary bytecode
  boundary, here inside `occupy_pool`'s `store.pool.start(...)`. That is why the Python frame points
  at this test while the destructor belongs to something else.

**What it does not establish**, and must not be written as though it did: which object, which test
created it, whether `thumbnails.py` is implicated at all, or identity with `T-074`/`T-128`. A
`QAbstractItemView` destructor under Shiboken deferred deletion is the same *class* of stack as
`T-128`'s — a QObject destroyed at a moment nobody chose — and `T-128` was a **harness** defect. That
is a lead, not a conclusion, and the third criterion below forbids treating resemblance as cause.

**The search is therefore narrower than the entry assumed**: not "what is wrong with this test", but
**which earlier test in the same worker leaves a view whose deletion is still pending**. The
`qt_lifecycle` orphan-timer guard (`T-128`, `tests/integration/conftest.py`) is the existing shape
of an answer — a per-test check that fails at the cause rather than at the crash — and `tests/ui`
has no equivalent for *views*.

#### Reproduction is not a viable strategy at this rate — 60 runs, 2026-08-12

| Conditions | Runs | Crashes |
|---|---:|---:|
| `-n auto` unit/UI, idle machine | 40 | **0** |
| `-n auto` unit/UI, host saturated (20 busy loops on 20 cores) | 12 | **0** |
| `-n auto` unit/UI **while an `-n auto` integration batch runs beside it** | 8 | **0** |

**Sixty runs, no reproduction — including the third row, which is the closest reconstruction of the
original conditions available.** The observation happened while other pytest batches were running,
so that shape was tried deliberately rather than as an afterthought.

**The second row also refutes a recommendation this entry made two paragraphs earlier.** Having
watched saturation reproduce `T-228` at 3-in-5, I wrote that the next attempt should reproduce under
deliberate host load. It does not. Different defect, different lever — the same mistake as comparing
this to `T-228` in the first place, made a second time in a smaller way.

**So repetition is the wrong instrument here.** At worse than 1-in-60 the cost of catching it again
is unbounded, and the retained stack already says more than another crash would: the object is a
view, and the test it was blamed on never makes one.

**What is worth building instead, proposed rather than done:** a `tests/ui` guard in the shape of
`qt_lifecycle.fail_on_orphaned_timers()` — *after every test, assert no `QAbstractItemView` is
awaiting deferred deletion* — which fails **at the test that leaked the view**, by name, on the
first ordinary run, instead of waiting for a segfault to land somewhere else. That would satisfy the
fourth criterion's *"a guard that fails before a worker dies"*, and `docs/project/TESTING.md` §13 already
states the principle: the useful signal is the one at the cause.

**Not built here**, because the fourth criterion is conditioned on product-versus-harness being
established and it is not. This is the Implementer proposing the next step, not taking it.

#### Scope

Reproduce and diagnose the **worker SIGSEGV** under the supported parallel unit/UI command. Capture
the test order and teardown state around the crash, because xdist's *"while running"* attribution
names the active node, not necessarily the object whose deferred deletion faulted.

Do not fold it into T-228: that task concerns `multiprocessing.Queue` delivery in spawned
integration workers. No assertion timed out here, so changing the interaction budget or pool-drain
deadline is not a candidate correction. Preserve the three existing contracts: deletion does not
block the GUI thread, the pool can drain, and late work does not emit through a deleted `QObject`.

#### Acceptance criteria

- Reproduction evidence records the process signal/exit, Python and native stacks, explicit xdist
  worker count, and the tests immediately preceding the active node; raw failing logs are retained
- Serial, isolated, module-order, and explicit xdist-count runs distinguish a defect in this test
  from deferred destruction or contamination left by another test
- The faulting object and lifetime edge are identified before claiming identity with T-074 or
  T-128; stack resemblance alone is not a cause
- **Re-scoped 2026-09-04** — see `T-289`'s *Ruled 2026-09-04*, which governs both. Product versus
  test-harness is established **by enumerating where the precondition is written**, not by catching
  the fault: 91 parentless product-widget constructions in the harness against 4 in the product, and
  77 against 2 for the item-view-capable subset. The guard stays in, and a firing is still the
  evidence that would reopen this. *(The original wording follows; it is superseded, not deleted.)*
- Product behavior versus test-harness behavior is established. A product-reachable fault gets a
  deterministic regression; a harness-only fault gets a guard that fails before a worker dies
- The original responsiveness, pool-drain, and no-emission-through-deleted-object assertions stay
  intact; no timeout is raised to make the crash disappear
- Repeated `pytest -n auto tests/unit tests/ui` runs after the correction materially exceed the
  pre-fix sample without another worker loss

#### Where each criterion stands — 2026-08-13

| # | Criterion | State |
|---|---|---|
| 1 | Reproduction evidence, raw logs retained | **Met for the one observation** — `docs/project/evidence/T238-SEGFAULT-gw7.txt`. **Not reproduced since**, in 60 runs |
| 2 | Serial/isolated/module-order runs distinguish this test from contamination | **Met, and it is what redirected the search.** The named test's file constructs no view; the faulting object came from elsewhere in the worker |
| 3 | The faulting object and lifetime edge identified before claiming identity with `T-074`/`T-128` | **Half met.** The *class* is identified — a `QAbstractItemView` destroyed under Shiboken's cross-thread deletion queue — and the specific object is **not**. No identity with either task is claimed |
| 4 | Product versus harness established; harness-only gets a guard that fails before a worker dies | **Still open — and no longer open with nothing behind it.** The mechanism is identified and is **product-reachable in principle**; see the 2026-08-16 measurement below. The guard remains delivered, and if it ever fires on a real test that is still evidence |
| 5 | The three original assertions stay intact; no timeout raised | **Met** — `test_deleting_a_closed_store_neither_waits_nor_is_emitted_through` is untouched, and `INTERACTION_BUDGET_SECONDS` is unchanged |
| 6 | ~~Repeated `-n auto` runs materially exceed the pre-fix sample~~ → **each half of the guard is mutation-checked independently** | **Replaced by maintainer ruling, 2026-08-13; met as replaced and verified at review.** Four mutations, four failures, each in **only** its intended outer regression — see `T238-R1` |

#### Criterion 4, 2026-08-16: the mechanism, measured and then found to be the wrong question

**The approach.** Criterion 4 has stayed open because it *cannot be inferred from a green suite*.
So this measures the fault's **one precondition** instead of waiting for the fault: the retained
stack shows `~QAbstractItemView` under `Shiboken::BindingManager::runDeletionInMainThread`, and
Shiboken only queues a deletion for the main thread when the wrapper's last Python reference was
dropped **somewhere else**. A `weakref.finalize` callback runs on whichever thread performed that
decref, so the precondition is directly observable. `tools/t238_widget_thread_probe.py`.

**The measurement, over a full serial `tests/ui` run:**

| | |
|---|---|
| `QWidget` classes instrumented | 92 |
| widgets constructed | 14 697 |
| finalisations observed | 8 853 |
| **finalised off the main thread** | **0** |

**The instrument's own positive control passed first, and it had to.** Two earlier versions
reported *zero off-thread finalisations over the whole suite* while measuring nothing at all —
first because Shiboken gives every class its own `__init__` slot, so patching `QWidget` caught no
real widget; then because patching a subclass that *inherits* `__init__` nests a wrapper per
hierarchy level. **Neither was visible in the output**, and "no widget was finalised off the main
thread" is exactly what a blind probe prints. The probe now drops a widget on a named worker
thread and refuses to report unless it sees it. `docs/project/TESTING.md` carries this as a rule.

**Then a survey of what the product's threads hold, which is where it got interesting.** Every
thread mechanism the product has was read: `ResultPump` (a `QThread` holding a queue, a job id, an
`Event` and a dict of `Signal`s), `ytdlp_service._Task` on the shared pool (a `_Sink` `QObject` and
a bound method of a `QObject`), `thumbnails._ReadFromDisk` / `_DecodeAndStore` / `_SweepTask` (a
`_Sink`, `str`, `Path`, `bytes`, `set[str]`), and the persistence writer's `QThread` (a `_Worker`
`QObject` and a callable). **Not one holds a `QWidget`.**

**And that is not sufficient, which is the finding.** Python's cyclic collector runs on whichever
thread crosses the allocation threshold, so **a widget reachable only from a reference cycle is
decref'd wherever `gc` happens to run — with no thread ever holding a reference to it.**
Demonstrated, in twelve lines, by `demonstrate_the_gc_route()` in the probe:

```
$ QT_QPA_PLATFORM=offscreen .venv/bin/python tools/t238_widget_thread_probe.py
the widget's last reference was dropped on: t238-gc-demo-worker
```

**So "who holds a reference" is the wrong question for this criterion. The question is who runs
`gc`** — timing rather than ownership. Both of the product's pools allocate (`QImage` decodes,
most obviously), so **the precondition is product-reachable in principle**, and the harness-only
reading cannot be assumed.

**What this establishes and what it does not.** It identifies the mechanism and shows it is
available to the product; it does **not** show the product reaches it in a real session, and it
does not reproduce the crash. It also explains the shape of the evidence better than anything
before it: a fault needing `gc` to fire on a pool thread at the moment a widget-bearing cycle is
garbage is one that appears once on a loaded machine and never again in 60 clean runs.

**What criterion 4 needed next as of 2026-08-16**, and it was no longer "wait for the guard to
fire". **Both items have since been answered in part; see *Criterion 4, 2026-08-31* for what is
owed now** (`T289-R15`, third pass — this read as a live request for a session that has since been
driven, which is the same defect dated one section further down):

- **Run the probe against a real session, not the suite** — `tests/integration` cannot answer it
  (a `QCoreApplication` process has no widgets at all, so the probe's own control would fail), so
  this needs the application driven on a display with the thumbnail pool actually working.
  **Run on 2026-08-31, on both pools and on a real display, and inconclusive both times**
- **Establish whether any `QWidget` in this application participates in a reference cycle.** If
  none does, the `gc` route is closed and the harness reading is back; if one does, criterion 4's
  *product-reachable* branch is the live one and it wants a deterministic regression, not a guard.
  **The 2026-08-30 arms bear on this without answering it as put**: no widget the application's own
  routes opened was parked while its Qt widget was still alive, which is the consequence this
  bullet cares about — *participates in a cycle* is a stronger predicate than `DEBUG_SAVEALL`
  parking establishes, as that section says of itself

#### The second step, attempted 2026-08-20: the run refused, and criterion 4 is unanswered

**`tools/t238_widget_cycle_probe.py`, offscreen on `kirk`.** It composes the application, opens the
three surfaces the window's own routes open — `open_add_dialog()`, `open_settings()`,
`show_about()` — tears it down through `composition.shutdown.begin()`, and then reads which
`QWidget`s **the cyclic collector freed**, with `gc.DEBUG_SAVEALL` armed so the collector's own
verdict is legible.

**The predicate is "freed by the collector", not "in a cycle", and the difference is the whole
measurement.** A widget held *by* a cycle is not itself in one — its own component has size one —
and it is still freed by `gc` rather than by refcount, and still decref'd on whatever thread
collected. Cycle *membership* would have answered a neighbouring question and missed exactly the
shape `demonstrate_the_gc_route()` demonstrates.

| Measured | Result |
|---|---|
| `QWidget`s live with every route open | **159** |
| `QWidget`s live after the application's own shutdown | **159** |
| `QWidget`s freed by the cyclic collector | **0** |
| **Other** objects freed by the collector in the same window | **30** |
| Exit code | **3 — refused** |

*(**That last row read "0 objects" for one commit and was wrong.** It was quoted from a scratch
diagnostic that was holding the objects it was counting — `gc.get_referrers` returned the very
lists I had put them in — rather than from the probe. The probe reports it now, which is the only
place it can be read from honestly. The correction **strengthens** the result rather than softening
it: the collector was **not** idle during the measurement, so *no widget was collected* is a fact
about widgets and not about the collector having nothing to do.)*

**The probe refused, and the first version of this section then answered anyway** (`T238-R5`). It
said the `gc` route was closed through these surfaces, that the trees were *"not garbage"*, and that
criterion 4's harness branch was selected. **All three are withdrawn.** The run exits **3** and says
its own zero is not a result about cycles; a section that quotes the refusal and then draws the
conclusion the refusal forbids is the same document giving two answers, which is the shape this
project keeps finding.

**Four reasons the counts do not reach that conclusion**, and each is a thing a future run would
have to fix rather than a caveat to note:

1. **Retention is not the absence of cycles.** A still-reachable graph is not classified by the
   collector at all, so it may contain any number of them. *"Not garbage"* described what the
   collector was prevented from deciding.
2. **Equal aggregates do not establish identity.** 159 before and 159 after does not say they are
   the same 159 widgets, and `0 widgets among the parked garbage` is a count, not a statement about
   which widgets those were.
3. **The forced `gc.collect()` after the result is not recorded.** It runs in the helper's `finally`,
   after the result is read and after `DEBUG_SAVEALL` is lowered, so whatever it frees is invisible.
4. **Five product-reachable screens are not covered.** The format table, template editor, playlist
   picker, options dialog and preset manager are reached from a staged row. Criterion 4 asks about
   **any** application widget.

**Criterion 4 stays open**, and what would close it is now specific: a measurement that **releases
or otherwise controls the retention root**, **tracks the identities** of the widgets it decides
about, **observes the collector after that release**, and **covers the whole application-widget
scope**.

**The refusal is the instrument working, and it is why an earlier number was thrown away.** The
very first run printed `0 freed` and nothing else, and that reads exactly like a clean result; *nothing was freed by the collector* and *nothing was freed at all* produce the same zero
and are opposite answers. The before/after widget counts are now part of the instrument, and it
**exits 3 rather than reporting** when the surfaces are still standing. Its **self-test runs in both
directions first** — it must *see* a widget reachable only from a cycle and must *not* name one
freed by refcount — because the sibling probe shipped two defects that made it report confidently
about nothing, **one of them a clean-looking zero** across the whole UI suite. *(That probe's
docstring calls both defects "clean"; only the first was. The second over-counted a widget five
times and was caught by a run taking three times as long, not by reading its output — a distinction
worth keeping, since it is the difference between an instrument that lies quietly and one that lies
loudly.)*

**What this does not establish.** *Why* the tree is retained is not identified here: the window's
Python referrers are its own bound methods and closure cells, and an attempt to attribute those to
C++ signal connections was **contaminated by the diagnostic's own lists** and is withdrawn rather
than reported. **The five uncovered screens were also called a deliberate scope and are not one**
(`T238-R5`): avoiding a second inventory of screens is a real constraint (`T200-R3`), but it does
not make those screens unreachable, and calling an omission a choice is how a bound stops being
read as a bound.

**`T-238` stays `Ready`.** This narrows the question and does not close it, and the entry is not
moving to `Complete` on a measurement that argues the opposite of the deliverable it already has.

#### Criterion 4, 2026-08-30: the collector's route is reproduced, and it is not this crash

`docs/project/evidence/2026-08-30-T238-criterion-4-widget-collection.md`. Three arms, each deterministic.
Census in all three: **364** widgets — 159 opened by the application's own routes, 205 constructed
by `tests/ui/surfaces.py`, the same inventory `tests/ui/conftest.py` audits (imported rather than
restated, because two lists of them would drift).

| Arm | Constructed screens | Window | Parked | **Live when parked** | Survivors | Outcome |
|---|---|---|---:|---:|---:|---|
| **A** | closed + `deleteLater` | product shutdown alone | 17 | **0** | 95 | no live destruction |
| **B** | **dropped for the collector** | product shutdown alone | 24 | **24** | 122 | **release → SIGSEGV** |
| **C** | closed + `deleteLater` | **+ `T-273`'s owner step** | 67 | **0** | **0** | no live destruction |

**The first version of this section was wrong and is withdrawn** (`T238-R7`). It reported arm A's
17 as *"widgets freed by the cyclic collector"* and called them the crash's precondition. **All
seventeen were already-dead wrappers**: the probe had `deleteLater`'d and flushed `DeferredDelete`
first, so Qt destroyed the C++ widgets and the collector parked the Python halves. Clearing a dead
wrapper runs no destructor and reaches no deletion path. The reviewer's replay — `shiboken6.isValid`
read while `gc.garbage` was still populated — is what separated the number from the claim, and the
probe now reads validity there itself. *"They are in cycles"* was also stronger than the predicate:
`DEBUG_SAVEALL` parks what a collection frees, and an object can be there because its only referents
were cyclic.

**No widget the application's own routes opened was parked while its Qt widget was still alive.**
That is the invariant across all three arms — **not** the same arithmetic in each, which is what
this said and was wrong (`T238-R9`). The arms do not release the same widgets:

| Route-opened widgets, 159 | parked | by refcount | still alive |
|---|---:|---:|---:|
| Arms A and B — window left to product shutdown | 0 | 64 | 95 |
| Arm C — `T-273`'s owner step applied | **50** | **109** | 0 |

Arm C parks 50 of them, and **all 50 are already-destroyed wrappers**: the owner's `deleteLater`
ran their destructors before the collector saw them. The claim survives the correction; the number
64 belongs to two arms of the three. The probe now prints the split per origin, because a record
quoting one arm's arithmetic for all three is quoting a number no run produced.

**Arm B reproduces the mechanism on demand, and demonstrating it aborts the process.** With Python
owning the C++ objects and only the collector freeing them, 24 wrappers park **with their widgets
still alive**, and the release dies: `gc_collect_main` → `_Py_Dealloc` → shiboken → `~QDialog` →
`hide_helper()` → the offscreen plugin → `QCursor::pos` → **SIGSEGV, 3 of 3 runs**. The upper half
is `T-238`'s retained stack and `T-289`'s dump — **the cyclic collector running a Qt widget
destructor**. **It is `T-289`'s stack exactly** — that dump's pool thread runs
`_Py_HandlePending` → `gc_collect_main` → `_Py_Dealloc` → shiboken → `QWidget::~QWidget`, the same
frames in the same order. **Its relation to `T-238`'s own crash is analogous rather than
identical** (`T238-R10`): the retained stack here is `~QAbstractItemView` under
`runDeletionInMainThread`, Shiboken's **queued cross-thread** path, which arm B never enters. Both
are the collector running a Qt destructor; only one of them is this task's. **Arm B is not this
task's crash** — main thread, offscreen plugin, helper-owned widgets — and it is the first time the
route has been made to happen on demand.

**Those widgets are the helper's, and that bound is the whole reason arm B is not the answer.**
`tests/ui/surfaces.py` builds the five **parentless**, so Python owns C++ objects the product would
have parented. In the product they have a parent, and dropping a wrapper then destroys nothing.

**The 95 survivors are `T-273`'s documented baseline** (`T238-R8`), and the previous section's
*"a tree that task was meant to have released"* is withdrawn with its incomplete-or-second-instance
speculation. `T-273` ruled that `shutdown.begin()` does **not** own the window's lifetime — the
`composed` fixture does, with `window.deleteLater()` and a **receiver-scoped** `DeferredDelete`
flush. **Arm C applies that step and every censused widget goes: 0 survivors.** Arms A and B omit
it, which is why the tree stands there.

**Two method corrections, either of which changes the answer.** `processEvents()` does not run a
`deleteLater()` — Qt delivers `DeferredDelete` only from an event loop. And automatic collection is
**off** for the measured phase: a widget freed by a generational collection during teardown would
be gone before `DEBUG_SAVEALL` was armed and would be filed under *freed by refcount*, which is the
exact event being measured. The run is therefore not natural teardown timing, deliberately.

**The instrument refuses rather than reporting when it cannot see.** Three controls run first: a
widget reachable only from a cycle is parked by its own tag **and valid at that moment**; a
refcount-freed widget is not named; and a parentless `QListView` outliving the self-test makes the
probe refuse — because the first version censused its own positive control and reported it as a
product finding. **Three instruments in this family have now reported confidently about nothing.**

**What criterion 4 needed as of this section, and how much of it has since been run**: the
real-session probe — the application on a display with the thumbnail pool working — and a widget the
*product* owns from Python reaching the collector. Arm B shows what happens when one does; nothing
in these three arms shows the product holding one. **The probe half ran on 2026-08-31 — both pools,
on a real display — and the widget half did not happen there either.** This paragraph asked for a
session that has since been driven, and said so two lines above the section recording it
(`T289-R15`, second pass); it is kept as the statement of what was owed *then*, and the section
below is what is owed now.

#### Criterion 4, 2026-09-03: counted rather than sampled — **and the first count was wrong**

**Corrected 2026-09-03 after `T238-R11`.** The first version of this section reported *"89
parentless, 30 item-view sites, none in the product"* and drew an asymmetry from it. **Two of those
three numbers were wrong and the third was a category error**, so the numbers are restated below and
the conclusion is not.

**Why count at all.** Six probes asked *"is a product widget reaching the collector right now?"* — 60
isolated sessions, two real-display runs, a forced collection at two sampled moments, the thumbnail
pipeline on its own pool threads — and every one answered no. That question has the regress
`T-289`'s audit named: another null sample cannot separate *there is none* from *we sampled the
wrong instant*. A widget can only be Python-owned if it is left without a Qt parent, so the sites
where this is even possible are finite and countable.

**Three predicates, and merging them is what went wrong.** *Parentless at construction*, *still
Python-owned afterwards*, and *able to destroy an item-view descendant* are different questions.
`tools/t289_ownership_audit.py` now reports the first and third separately and does not claim the
second at all.

| | constructions | parentless at the call site | of those, classes that **can** own an item view |
|---|---:|---:|---:|
| `src/tracks_and_trails` | 162 | 4 | **2** — `MainWindow`, `QueueView` |
| `tests/` | 92 | **91** | **77** |

**What was wrong, itemised, because the corrections are the useful part:**

- **`parent=None` was counted as a parent.** `is_parented` returned true for any `parent=` keyword
  without looking at its value, so four real sites were hidden. 89 → **91**. Fixed for the keyword
  and the signature-mapped positional form, with a self-test arm for each, both verified by mutation.
- **The item-view set was chosen by eye and was incomplete — twice.** It named four classes;
  `PresetManager` and `OptionsDialog` each own a `QListWidget` directly, and ownership is
  **transitive** — a `MainWindow` reaches a `QListView` through its queue. Rebuilt structurally, it
  was **still** wrong: seeding only from *constructions* missed a product class that **is** an item
  view. `EntryTable(QTableView)` constructs nothing and owns nothing, and six `PlaylistPicker` sites
  reach an item view through it. 71 → **77** (`T238-R11`, second round). The seeding now includes
  classes transitively derived from an item view, and the self-test pins both routes.
- **"None in the product" was false.** `src` has **2** parentless sites whose class can own an item
  view, and `build_queue_view()` is reached — `main_window.py` adopts it with `setCentralWidget`
  two statements later. That adoption is exactly the *second* predicate, which this tool does not
  measure, and stating "none" merged it with the first.

**`can own` is not `does own here`, and the tool now says so in its own output.** `MainWindow` builds
its queue only when equipped, so 71 is an **upper bound** on harness sites that could run
`~QAbstractItemView` — not a count of the ones that would. Deciding a given site needs the
construction's arguments, which an AST reading does not have.

*(The count has been corrected twice under review — 89 → 91 for `parent=None`, 71 → 77 for a class
that is an item view rather than owning one. Both errors ran in the direction of the conclusion this
section was drawing, which is the reason it is written up as an argument that has been wrong rather
than as a finding.)*

**What this establishes.** A real asymmetry in where the *precondition* is written — 91 parentless
product-widget constructions in the harness against 4 in the product, and **77** against 2 for the
item-view-capable subset. Nothing more. It does **not** identify the faulting object (criterion 3),
it does not establish what remains Python-owned after construction in either tree, and it is a
static reading blind to widgets Qt itself constructs.

**It does not move criterion 4 and is not offered as doing so.** The maintainer's 2026-08-13 ruling
sets the bar at the guard firing on a real test. This is an argument, it has now been wrong once,
and the corrected version is recorded so the next reader inherits the numbers rather than the claim.

#### Criterion 4, 2026-08-31: both halves of the real-session step have run, and neither answers it

**The update-route half** is `T-289`'s driven measurement — 60 isolated sessions at `179f73e`,
recorded in that entry under *The driven measurement* — plus the reviewer's own run of the same
route on a **real display** at `948f837`. Both answer in the direction the three arms above did:
**no widget the product owns reached the collector**, on the very pool thread the crash dump names.

**The thumbnail half ran too, and it is the one this criterion asked for.** In the review of
2026-08-31 a driver composed the real application with the spawned-fixture worker, staged the
recorded Archive.org row through the add dialog's own debounce, and let the delegate start the real
`ThumbnailStore` pipeline; the public JPEG was fetched into a disposable cache and published as a
pixmap. `_ReadFromDisk`, `_DecodeAndStore` and `_SweepTask` each ran on their own pool thread.
**647 widgets watched, 12 collections — every one of them on the GUI thread, none on any thumbnail
task thread**, 0 destructions off the GUI thread, 0 near misses. `INCONCLUSIVE`.

*(**Superseded by the re-scope of 2026-09-04** — see `T-289`'s *Ruled 2026-09-04*, which governs
both criteria. What follows was true when written.)*

**Criterion 4 stays open, and the reason has moved.** It is no longer *"nobody has run it on a real
session with the pool working"* — that has now been run. What is missing is the thing the criterion
is actually about: **a widget the product owns from Python reaching the collector**. The pool did
its work and the collector never fired on those threads at all, so there was again nothing for it to
get wrong. **Forcing a collection there was deliberately not done**: on a live desktop that converts
the measurement into the hazard it is measuring, which is a choice for the maintainer and not a
thing to slip into a probe.

---

---

---

## Proposed — Phase 0

## Proposed — Phase 1

## Proposed — Phase 2

### T-121 — The phase-exit clip server aborts connections on hosted Windows

**Status:** **Proposed — narrowed 2026-08-03, and still open.** Two of its three parts are struck
off: the misleading assertion and the missing `ConnectionAbortedError`. What remains is the part
nothing here can reproduce — **why the loopback connection aborts under load on hosted Windows.**
Filed rather than fixed inline (`AGENTS.md` §7): it is not `T-118`'s.

**It is now latent for two independent reasons, and only one of them is about the defect.** It did
not recur in run `30859578131` — which is not the same as resolved (`COORD-R21`) — **and the
configuration it appeared in is no longer exercised at all.** It only ever failed on hosted
`windows-latest`, and that job does not run while `WINDOWS_RUNNER` points at `STARBASE`
(`docs/project/TESTING.md` §10). *Not running the job that found a defect is not evidence about the defect*,
and in six weeks the silence will read as resolution unless this paragraph is here.

The current red on `main` belongs to nothing: `T-122`'s ratio oracle is corrected.
*(This read "it is the only thing red on `main`" until 2026-08-03, which stopped being true the
moment `T-118`'s own scaling gate failed and this test passed.)*
**Owner:** Implementer
**Priority:** Medium — a gate that fails for its own fixture's reasons is a gate that will be
dismissed, which is `T118-R10`'s lesson in a different costume
**Phase:** Phase 2 (its gate), though the defect is in test infrastructure
**Relevant context:** `tests/integration/test_phase_2_exit.py`, its `media_url` fixture,
`tests/network/conftest.py`
**Affected surfaces:** `tests/**`
**Risk:** Low to fix, and it is *not* a production defect

**`test_every_queued_job_eventually_starts_as_slots_free` failed on hosted `windows-latest` while
passing on `STARBASE`.** The assertion reads:

```
0 of 5 jobs were still QUEUED after Add with nothing else done
Final: {'af90cb': 'completed', '660db5': 'completed', '83cc82': 'failed',
        'bdd939': 'completed', '7cbf8e': 'completed'}
```

**Read the numbers before the message.** Zero jobs were still `QUEUED`, so the behaviour the test
exists to prove — that a queue drains with no user action after Add — *held*. Four of five
completed. The fifth **failed**, and the captured stderr says why:

```
ConnectionAbortedError: [WinError 10053] An established connection was aborted
by the software in your host machine
```

That is the test's own `ThreadingHTTPServer` losing a connection to its own client, twice, on the
loopback interface. The predicate demands all five `COMPLETED`, so one aborted download reddens a
test whose subject is admission.

**The message is now misleading, which is the part worth fixing.** It reports the `QUEUED` count
and concludes "nothing admits durable queued intent" — a sentence that is false whenever the count
it prints is zero. A reader who trusts the prose over the dict diagnoses the scheduler.

#### Scope

- Make the fixture server survive an aborted client connection rather than propagating it.
- Distinguish the two failures in the message: *jobs did not start* is the defect this gate exists
  for; *a job started and its download failed* is a different sentence and should say so.
- Neither reproduces on Linux, and it is hosted-Windows-only so far — `STARBASE` ran the same test
  in the same run and passed. Codex separately reported 16 localhost-server tests denied outright
  by its sandbox, so this fixture is fragile in more than one constrained environment.

#### Out of scope

- The download path itself. Nothing here suggests a production defect: the worker did what a
  worker does when a server drops the connection.

#### Corrected 2026-08-03 — the two parts that could be fixed without reproducing it

**The assertion named the wrong defect.** It printed the `QUEUED` count and then concluded
"nothing admits durable queued intent" *whatever that count was*, so a run where every job started
and one download failed reported "0 of 5 still QUEUED" and blamed admission — the one part that was
working. It now branches: a stalled queue says so, and a queue that drained with a failed download
says **that**, and points at the clip server.

**`ConnectionAbortedError` was missing from the handler.** `media_handler` already caught
`BrokenPipeError` and `ConnectionResetError` with the comment *"the expected end of a killed
download: the worker went away mid-stream"* — and `ConnectionAbortedError` is that same condition
on Windows. Its absence is why the abort escaped to `socketserver`, which printed a traceback for a
state two lines of the fixture already called expected. Added in **both** copies: the shared
`media_handler` in `test_end_to_end.py` that `test_phase_2_exit.py` imports, and `test_manager.py`'s
own.

**Neither makes the download succeed**, and neither is claimed to. Swallowing the abort stops the
noise; the connection still died mid-stream and that is what failed the job. Both changes are
improvements a reader can verify without Windows, which is exactly why they were worth doing
separately from the part that needs it.

---

### T-106 — Decide the Linux packaging format before Phase 5

**Status:** Proposed — **filed 2026-08-01**, from the Phase 5 roadmap review. `IMPLEMENTATION_PLAN.md`
requires this decision *before the first build* and it does not exist.
**Owner:** Architect / maintainer decision
**Priority:** Medium — nothing is blocked until Phase 5, and the answer shapes work well before then
**Phase:** Phase 5 prerequisite
**Depends on:** nothing
**Relevant context:** `REL-001` (ship frozen artifacts, no Python on the user's machine),
`IMPLEMENTATION_PLAN.md` §Phase 5, `LIC-001`, `NFR-009` (Qt stays dynamically linked), `OPS-001`
**Affected surfaces:** `docs/project/DECISIONS.md`, and later `packaging/`
**Risk:** Medium — taken late, it constrains a build that has already been written

#### Scope

§Phase 5's trigger reads: *"A `REL-` decision recording the Linux packaging format must be accepted
before the first build."* The only `REL-` entry is `REL-001`, which decides that artifacts are
frozen and self-contained and says nothing about **format**. The deliverable list says only
"Linux: packaging per the `REL-` decision" — pointing at an entry that does not exist.

**Why it is worth taking early rather than at Phase 5.** The candidates differ in ways that reach
back into the build: AppImage wants everything in one tree and is closest to what PyInstaller
already produces; Flatpak has its own runtime and sandbox, which changes how the application finds
`ffmpeg` and where it may write (`NFR-004`, `REQ-024`); a `.deb`/`.rpm` pair means system packaging
per distribution and a dependency story rather than a bundle. `NFR-009` constrains all of them —
Qt must stay dynamically linked (`LIC-001`'s LGPL condition).

#### Acceptance criteria

- A `REL-` entry naming the format, with the rejected alternatives and **why**, in the house style
- States how the choice interacts with `REQ-024`'s ffmpeg detection and `NFR-004`'s directories,
  since that is where a sandboxed format differs most from a bundle
- States what it means for `NFR-009`, and how that is checked in the release gate
- Names its reopening condition

#### Out of scope

- Building anything. This is the decision; Phase 5 owns the packaging work
- Windows, which `OPS-001` already settles

---

### T-104 — Hand a second launch's URL to the running instance

**Status:** Proposed — **filed 2026-08-01 by `T-087`**, which built the ownership half of `ARC-006`
and deliberately not the attach half.
**Owner:** Implementer
**Priority:** Low — `T-087` satisfies exit criterion 4 and `A-004` by refusing; this is the nicer
half of "attaches **or** refuses"
**Phase:** Phase 2
**Depends on:** `T-087`
**Relevant context:** **`ARC-006`** and its 2026-07-29 amendment, `A-004`, `REQ-001`
**Affected surfaces:** `app.py`, a new channel module
**Risk:** Low — the ownership guard already prevents the harm; this only improves the outcome

#### Scope

`ARC-006` keeps `QLocalServer`/`QLocalSocket` as an **attach channel**, and is explicit that this is
what makes *attach* possible rather than only *refuse*: "a second launch can hand its URL to the
running instance and raise its window. A lock file can only say no."

`T-087` built the ownership lock and stopped there, because the criterion it owns is satisfied by
refusing. Today a user who double-clicks the application a second time — or opens a link with it
while it is running — gets a message box naming the running instance and nothing happens to the URL.

**The channel is started by whoever wins the lock, and never decides who owns the database.** That
separation is the whole point of the amendment and must survive this task: the loser connects to the
channel and hands over; it does not attempt to become a server.

#### Acceptance criteria

- A second launch with a URL passes it to the running instance, which enqueues it, and the second
  process exits reporting that it did so
- The running instance's window is raised and focused
- **A second launch with no URL still raises the window** rather than doing nothing visible
- The channel is started **after** the lock is won, asserted — a channel started first would
  reintroduce the design `P2PLAN-R5` withdrew
- A second launch when the channel is unreachable — the owner is alive but wedged — still refuses
  rather than hanging, within a stated timeout
- Verified on both platforms. **`OPS-005` amended 2026-08-01:** hosted Windows carries the Windows
  gate while `STARBASE` is unreachable, so `check (windows-latest)` satisfies this and the desktop
  slice stays with `STARBASE` for first release
  *(This read "`STARBASE` included" without qualification, which after the amendment demanded a
  machine nobody could reach for a criterion hosted Windows had already met — `T087-R4`.)*: the named-pipe and Unix-socket halves are
  different system calls

#### Out of scope

- Anything that makes the channel decide ownership (`ARC-006` amendment)
- Multi-user or networked access (`A-004`)

---

### T-048 — Verify the first real data migration when one is written

**Status:** Proposed — **not schedulable yet.** No migration transforms data.
*(Premise re-checked 2026-08-06 after `T169-R5`. Still true, and narrower than it was: `0009`
**destroys** data rather than transforming it. That is a different problem with a different answer
— it needs a test proving the rows are gone, which it has, not an allowance for values that
legitimately changed, which is what this task is for. What did move is the strict per-column rule
below: it now covers `jobs` only, because `history` no longer exists to compare.)*
**Owner:** Implementer, when the first data migration is authored
**Priority:** Medium at that point; nothing to do before
**Phase:** unassigned
**Depends on:** the first migration that changes stored values
**Relevant context:** `T014-R4`; `docs/project/TESTING.md` §7 (Migrations)
**Affected surfaces:** `tests/unit/test_persistence.py`

#### Scope

`T-014`'s migration test asserts strict per-column equality **for the tables in
`_MIGRATED_TABLES`**, which since 2026-08-06 means `jobs` alone. That is correct while every
migration either leaves a table's values alone or removes the table outright, and any unasked-for
change is loss. It will be **wrong** the day a migration legitimately transforms values.

**A destructive migration is not the case this task covers**, and `0009` is the reason to say so:
it removes rows on an explicit ruling and proves it with its own regression. This task is about the
opposite situation — values that change and are still correct — where equality has no way to tell a
good transformation from a corrupt one.

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

## Proposed — Phase 3

### T-190 — `docs/UX_SPEC.md` §6 still says its screen is unspecified

**Status:** Proposed — filed by `T-109`, 2026-08-07.
**Owner:** Planner / Documentation Maintainer
**Priority:** Low — no runtime behaviour depends on it; the defect is a current-truth document
stating a solved problem in the present tense, which is `T185-R1` exactly.
**Phase:** Phase 3 cleanup
**Depends on:** `T-109`'s verdict, so the correction describes what was approved rather than what
was submitted.

#### Scope

`docs/UX_SPEC.md` §6 carries a `[T]` clause reading *"This clause stays because `T-109`'s screen has
not been specified against the ruling yet"*, and a `P-16` paragraph asking whether `T-109` and
`T-111` share a screen as though it were open. `UX-007` ruled `P-16`, and the screen now exists:
`ui/options_dialog.py`, reached as `Options…` on the row's format control.

`AGENTS.md` §4 does not put `docs/UX_SPEC.md` in the Implementer's write set, which is why `T-109`
filed this rather than editing it.

#### Acceptance criteria

- §6's open questions read as ruled and built, in the past tense, with the built surface named.
- The `Save as preset…` clause describes the control **as built by `T-109`** (`T109-R5`), rather
  than saying it arrives with `T-111`. `T-111` still owns the other four operations.
- Nothing else in §6 changes: the ruled clauses are the contract the implementation was built
  against.

---

### T-191 — A queued row shows no size until it downloads

**Status:** Proposed — **filed 2026-08-08 by the `T143-R1` amendment**, which deferred pre-download
size here rather than declining it. A criterion cannot be narrowed into nowhere, so this is where it
went.
**Owner:** Implementer
**Priority:** Low — no defect, and no user has reported it. `UX-005` §3 does not promise a size
before a download starts, which is why `T-143` was amended rather than expanded
**Phase:** Phase 4 — polish, and it is a schema change, so it does not belong in a phase that is
exiting
**Depends on:** nothing
**Relevant context:** `T-143`, `T143-R1`, `UX-005` §3, `DAT-001`, `core/models.py` (`Job`,
`FormatInfo.filesize`, `FormatInfo.filesize_is_estimate`), `persistence/` migrations
**Affected surfaces:** `core/models.py`, `persistence/`, `ui/queue_view.py`, a migration
**Risk:** Low in mechanism, **Medium in honesty.** A size shown before a download is a *prediction*,
and `FormatInfo.filesize_is_estimate` exists because yt-dlp's own number is sometimes
`filesize_approx`. A row that states an estimate as a fact is the class of confident lie
`Job.progress` already refuses to tell

#### What is wrong

Nothing, today — and that is why this is Low. **No row of any kind shows a size before it runs.**
A pasted URL and a playlist entry are equally bare, so there is no inconsistency for a user to
notice; there is a field the application could show and does not.

`T-143`'s first acceptance criterion asked for it and could not have delivered it: a size lives
per-format in `FormatInfo.filesize`, and `Job` carries only `bytes_total`, which a *download*
reports. `T143-R1` found the criterion unmet, the maintainer amended it to the `UX-005` §3 anatomy,
and the deferred half is this entry.

#### Scope

Decide whether a queued row shows a predicted size, and if so store it. That means a field on `Job`
populated from the chosen format, a migration for it, and a decision on what the row says when the
number is `filesize_approx` rather than `filesize`.

**The estimate question is the real work.** Storing a number is a morning; deciding what a row says
when the number is a guess is the part that needs a ruling, because `REQ-003` already names the
column *"filesize/estimate"* and `T107-R7` made the two distinguishable for exactly this reason.

#### Acceptance criteria

- A queued row shows the size of the format it will actually download, before it downloads
- An estimated size is **shown as an estimate**, distinguishable from a size the site stated
- A format with no size at all leaves the row saying nothing rather than zero
- The stored size survives a restart, and a re-probe that changes the chosen format updates it
- Changing the format on a row changes the size it shows

#### Out of scope

- Predicting a size for a format the user has not chosen. The row shows what it will download

---

## Proposed — Phase 4

### T-212 — The recorded checklist run: the built window against the agreed flow

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t212-validation).

**Carries one row by maintainer direction, 2026-08-13:** the **deferred panel mount**. `T-221` was
closed on a real-display observation — the maintainer did not see the one-turn transient — and the
maintainer directed that it be re-checked by hand in this pass rather than left as an open task.
One observation on one machine is evidence about that machine; this run is where a second is taken
deliberately, in front of the whole built window, and **recorded** in `docs/project/evidence/`. Both panel
kinds, since `T-209`'s audit found both spend that turn at 190×26.

**Status:** Proposed — filed 2026-08-09, owning the exit criterion the maintainer added the same
day; **the checklist half is written**, 2026-08-16, at `docs/PHASE_4_CHECKLIST.md` — before the
run, which is this task's first acceptance criterion. **Forty-eight** rows across seven sections
— counted; forty-seven when written, after the entry first said forty-one from an estimate, and
`6.1a` added 2026-08-28 with `T-292` — derived from
`docs/UX_SPEC.md` §2/§3/§8/§11/§12 and the accepted criteria of every surface Phase 4
added or reshaped, in `docs/CRITERION_8_CHECKLIST.md`'s shape and under its guards: rows say what
a user should see, task ids are back-references, and a failed row becomes a task entry rather than
an inline repair. The maintainer-directed panel-mount row is **5.6**, covering both panel kinds.
**What remains is the run itself** — a real display and a person looking at it — recorded in
`docs/project/evidence/` at a named head. A **run sheet** is published for the sitting, generated *from* this
file so the two cannot drift: it marks each row pass / fail / not run, keeps the marks per head,
and emits the `docs/project/evidence/` markdown to paste back. The criterion had no owner in the map above, which is exactly the
failure that map exists to surface.
**Owner:** Implementer
**Priority:** High — it is a phase exit criterion, and the phase cannot exit without the evidence
**Phase:** Phase 4 — **last.** The plan's own criterion text says why: a run taken before the
phase's surfaces land checks an application that is about to change.
**Depends on:** `T-146`, `T-195`–`T-202`, and the add-dialog chain — `T-203`, `T-204`'s
corrections (`T-207`, `T-209`, `T-210`, `T-211`) and whatever `T-208`'s investigation changes.
**Relevant context:** `IMPLEMENTATION_PLAN.md` §Phase 4 exit criteria; Phase 2's criterion 8 —
`docs/project/evidence/2026-08-05-criterion-8-checklist-run.md` and its two successor runs; `P2EXIT-R10`,
`P2EXIT-R12`; `docs/UX_SPEC.md`
**Affected surfaces:** `docs/project/evidence/` (the recorded run) and new task entries for what it finds
**Risk:** Medium — not that the run is hard, but that it is treated as a formality. Phase 2's
first run found **eleven defects against 2153 passing tests, none reported by any gate**, and
needed two further runs to reach 40 of 40

#### Scope

The criterion reads: *"The built window matches the flow that was agreed — evidenced by a recorded
checklist run against the running application, in `docs/project/evidence/`, the way Phase 2's criterion 8 was
evidenced."* This task writes the checklist, runs it against the running application, records the
run, and files what it finds. The checklist derives from `docs/UX_SPEC.md` — the agreed flow — plus
the accepted criteria of the surfaces this phase adds: the settings screen and its panes, the
reshaped add-dialog row, and the phase's queue and error-presentation changes.

**A walked-through session is not evidence.** `P2EXIT-R12` was a checklist claiming a pass over its
own recorded failures, and `P2EXIT-R10` was the same row claimed met and reset twice. The recorded
run is the deliverable; the pass is only what it hopefully shows.

#### Acceptance criteria

- **The checklist is written before the run**, derived from `docs/UX_SPEC.md` and the phase's
  accepted task criteria, and covers every surface Phase 4 added or reshaped
- **The run is recorded in `docs/project/evidence/`**, item by item, pass or fail, at a named commit — the
  format Phase 2's criterion-8 runs established
- **A failed item becomes its own task entry**, filed rather than repaired inline and re-claimed
  within the same run
- **A re-run after corrections repeats the whole checklist**, not only the failed rows — Phase 2
  needed three runs, and each was complete
- **The evidence names the commit and states that every depended-on task above was integrated at
  it** — a run over a tree still missing one of them is the "about to change" application the plan
  warns against

#### Out of scope

- **Fixing what the run finds.** Each finding is its own filed task with its own review
- **The Windows half.** `OPS-003`: there is no Windows machine, so the run is Linux; the
  pre-release Windows session inherits the same checklist, and the gap is named the way the plan's
  screen-reader split names its Narrator gap

### T-286 — The container section says what recode costs and never what it is for

**Status:** Proposed — **filed 2026-08-27 during `T-212`'s run**, from the maintainer's question:
*"Does re-encoding provide any tangible benefits over remuxing the files? Seems like the option is
pointless."* **It is not pointless, and the fact that the dialog left that question open is the
defect** — the note beside the radios states the cost of recoding and never the case that buys it.
**The option stays**; this task changes what the dialog says about it.
**Owner:** Implementer
**Priority:** Medium — a control whose purpose has to be reasoned out from first principles is one
users either avoid or misuse, and both cost a whole re-encode to discover
**Phase:** Phase 4 (polish; **not** a plan deliverable)
**Depends on:** nothing. `T-285` narrows *which containers* are offered; this changes *what the
section says* about the two verbs, and neither blocks the other
**Relevant context:** `ui/options_dialog.py:402`–`:431` — the three radios and the note;
`REQ-010`; `T-109`; `core/presets.py`, where the mp4 preset's selector already answers the common
case without any conversion at all
**Affected surfaces:** `ui/options_dialog.py`, `tests/ui/test_options_dialog.py`
**Risk:** Low

#### What is wrong

The note reads, in full:

> Remuxing keeps the streams and is quick; recoding re-encodes them and is not.

Both halves are true and the sentence describes only cost. A user reading it learns that one
option is slower and nothing about when the slower one is the right answer — which is why the
question this task was filed from is the reasonable conclusion to draw from the dialog as it
stands.

**Measured with ffmpeg 2026-08-27**, a one-second `vp9 + opus` webm and a one-second `h264 + aac`
mp4, plus a ten-second 640×480 clip for the cost:

| Operation | Result |
|---|---|
| **Remux** webm (vp9/opus) → mp4 | **Succeeds — and the output still contains `vp9 opus`** |
| **Remux** mp4 (h264/aac) → webm | **Fails**: *"Only VP8 or VP9 or AV1 video and Vorbis or Opus audio … are supported for WebM"* |
| **Recode** webm (vp9/opus) → mp4 | **Succeeds, producing `h264 aac`** |
| Cost | remux **0.11 s**, recode **4.86 s** — and the recode's output was **larger** than its source, 221 KB against 158 KB |

**Remux changes the wrapper; recode is the only thing that changes the codecs.** That is recode's
entire benefit and it is a real one: a source published as VP9 or AV1 only — which YouTube
increasingly does above 1080p — has no route to a file that plays on hardware speaking h264/aac
except through a re-encode.

**And it is narrower than it looks in this application**, which the note should not overstate
either: the mp4 preset already selects `bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]`, so
the common case is answered by *choosing* an h264 stream rather than by making one. Recode earns
its place only where no such stream exists.

#### Acceptance criteria

- **The section names the case recoding is for**, in the same register as the rest of the dialog —
  a user's words, not codec names, and one line rather than a paragraph
- **It does not oversell it**: the note must not read as advice to recode, given that format
  selection answers the ordinary case without one
- **The cost stays stated.** The present sentence is not wrong and the slowness is what stops a
  casual click; this adds the missing half rather than replacing the sentence
- **The wording is asserted by a test**, the way the dialog's other fixed strings are, so it cannot
  drift back into cost-only

#### An open question this raises, and does not answer

**A remux to `mp4` that leaves VP9 inside is a success that did not do what the user meant.** The
first row of the table is exactly the trap the maintainer's question was circling: the mux
succeeds, the extension changes, and the file still will not play where it was converted to play.
Whether the application should say anything about that is a real decision and **not part of this
task** — warning about it means the container section starts reasoning about codecs it does not
currently touch, and the honest alternative is that this is correct ffmpeg behaviour a
general-purpose tool need not editorialise. **Filed here so the observation is not lost with the
conversation; it needs a ruling before it needs a task.**

#### Out of scope

- **Removing recode.** It is the only route to a playable file from an AV1-only or VP9-only source
- **Which containers are offered** (`T-285`)
- **Choosing codecs**, or any control over the recode's encoder settings — `REQ-010` does not offer
  them and this task does not add them

### T-290 — Offer the yt-dlp update as recovery, not as a setting

**Status:** Proposed — **filed 2026-08-27 to build `OPS-002`'s amendment of the same day**, which
the maintainer ruled during `T-212`'s run: the override stays, and stops being a standing choice.
**Owner:** Implementer
**Priority:** Medium — nothing is broken today; what changes is which version the population runs,
and that compounds quietly in the other direction
**Phase:** Phase 4 (polish; **not** a plan deliverable). It is a presentation change to a screen
this phase built, and the maintainer may prefer it after the exit — that placement is theirs
**Depends on:** nothing. `T-289` crashes in this screen's update path and is a different defect;
neither blocks the other, but both touch `show_ytdlp`
**Relevant context:** `OPS-002` and its 2026-08-27 amendment; `ui/settings_dialog.py:1387` and
`show_ytdlp`/`show_ytdlp_problem`/`show_ytdlp_busy`; `REQ-025`; `NFR-007` — the update performs an
outbound download and must stay explicit, never automatic and never silent
**Affected surfaces:** `ui/settings_dialog.py`, wherever a download failure is presented, and
their tests
**Risk:** Medium — the honest version of this needs a route from a *failure* to the update, and a
failure surface that starts giving advice is how a row's anatomy grows a second voice (`T-243`)

#### What changes, and what does not

**Unchanged:** the pinned baseline, the user-managed copy resolved ahead of it, the version shown
in the UI, and revert as one action. The mechanism is not what was ruled on.

**Changed:** the update is currently `Update to the latest version` — a button of equal weight
beside `Use the bundled version`, in a Settings section that reads like every other setting. That
presentation invites a population onto versions this project has never tested. The amendment makes
it the way out of a site that has broken.

#### Acceptance criteria

- **The Settings screen no longer presents updating as a routine choice.** What it becomes —
  reworded, de-emphasised, moved behind a disclosure, or left in place with different words — is
  the implementer's proposal and the maintainer's ruling. **It must not disappear**: `OPS-002`
  requires the resolved version to be visible and revert to be one action, and both are still true
  after this
- **There is a route from a failed download to the update**, worded as what it is: sites change,
  and a newer yt-dlp may fix this one. This is the half that makes the reframing honest rather than
  merely quieter
- **That route does not turn the failure surface into an advice column.** `T-201`'s error anatomy
  and `T-243`'s one-voice rule both apply: a failure states what happened, why, and one next step —
  and a class with no honest next step still gets none
- **The offer appears only where it could be true.** A refusal that has nothing to do with the
  extractor — an unwritable folder, a full disk — must not suggest updating yt-dlp. `UX-005` §5
- **`NFR-007` is untouched**: still explicit, still never automatic, still never silent
- **The wording is asserted by tests**, the way the screen's other fixed strings are

#### Out of scope

- **Removing the override.** Explicitly rejected in the amendment; `OPS-002`'s *"pin only"*
  alternative stands refused, and more firmly while no release pipeline exists
- **Automatic or background update checks.** `NFR-007`
- **The crash in this path** (`T-289`)
- **Whether the application itself should self-update**, which `REL-001` leaves open and which the
  amendment names as the condition for reopening `OPS-002`

## Proposed — Phase 4.5

### T-184 — The escape hatch: additional yt-dlp options, parsed and bounded

**Status:** Proposed — filed 2026-08-07 with the phase. **Unblocked 2026-08-21**: `SEC-005` ruled
`--legacy-server-connect`, the one disposition this waited on (`T183-R3`, the sixteenth option the
audit surfaced), and **`unruled` is now 0** — every documented option has a class, which is the
condition a final refusal list needs. The three `SEC-003` corrections `T-256` also carried were
non-blocking and were ruled the same day; two of them **add** to this list. `T-183` delivered the
classification and `SEC-004` ruled the original fifteen forbidden, so the refusal list is the
audit's `app:sets` + `app:contained` + `app:plumbing` + **`app:policy`** + `excluded` classes —
**92 documented options**, up from 89 by `--legacy-server-connect`, `--netrc-cmd` and
`--client-certificate-password`. **Nothing in this phase starts before Phase 4 exits**, so this is
unblocked rather than startable.

**`Depends on:` is satisfied rather than removed.** `T-256` is still In Review; what it owed this
task is taken, and a reviewer disposing `T-256` differently would reach this line.

**The refusal list is 92 and this entry gave two numbers** (`T256-R2`). Its `Depends on:` line still
carried the pre-ruling **89**, so an implementer could read both the three newly refused options and
the old list that omits them — from the same entry. **92 is the live figure**, and 89 survives below
only inside the struck dependency, as what it was.

*(**This entry said "both blockers are cleared", "nothing outstanding" and "79 documented options",
and required a destination-keyed refusal, after `T183-R1`…`R5` had changed all four.** The
re-review found it: correcting the audit and leaving the task that consumes it is how an
implementer follows a specification the audit no longer holds — and it would have refused a safe
normalized value as though it were the `SEC-003` bypass.)*
**Owner:** Implementer
**Priority:** High within the phase — it is what makes `REQ-030` true before the typed fields exist
**Phase:** Phase 4.5
**Depends on:** ~~**`T-256`** — **one** unruled option, `--legacy-server-connect`~~ — **satisfied
2026-08-21 by `SEC-005`**. *(This said "sixteen unruled options and three `SEC-003` corrections"; fifteen were ruled by `SEC-004` and the three corrections are explicitly non-blocking — `T183-F1`.)* `T-183` delivered the classification, `SEC-004` ruled the original fifteen and `SEC-005` the sixteenth, with `SEC-003`'s amendment withdrawing two permissions; the refusal list is **92 documented options** across five refused classes, in `docs/YTDLP_OPTION_AUDIT.md`. *(This line said **89** while the status above said 92, so one entry gave both the pre-ruling and post-ruling list to whoever builds it — `T256-R2`.)* *(It also waited on `T-182`, which ruled on 2026-08-07: the refusal list starts with `-u`, `-p`, `--video-password`, `--impersonate`, `--xff`, `--exec` and `--exec-before-download` — `SEC-003`.)*

> **Four of `T-183`'s findings land here, and the first changes the design.**
>
>
> - **Finding 4 — the refusal list keys on the normalized value `parse_options` produces**, not on
>   the option string and **not on the `dest`**. Three suppressed spellings — `--geo-bypass`,
>   `--geo-bypass-country`, `--geo-bypass-ip-block` — reach the value `SEC-003` forbids under the
>   name `--xff`, so a list of strings enforces `REQ-EXCL-002` against one spelling in four. **But
>   `--no-geo-bypass` shares that same `dest` and normalizes to the value that *disables* the
>   bypass**, so keying on `dest` refuses a safe input. Run the candidate through `parse_options`
>   and refuse on what comes out. The refusal still names the string the user typed, because that
>   is where it is stated.
>
>   *(This bullet required destination-keying until `T183-R1`'s re-review. It was the audit's
>   original conclusion and it was wrong in the direction that looks safe.)*
> - **Finding 4, second half — decide the whole parser, not the documented part.** 36 suppressed
>   options have a `dest` no documented option has, so keying on `dest` does not reach them either.
>   Two are the forbidden family outright (`--exec-before-download`, `--no-exec-before-download`).
> - **Finding 6 — `--write-thumbnail` shares `writethumbnail` with the application.** It is the one
>   place a typed control has to share a key rather than own it; `T-249` owns the tri-state and the
>   merge rule is this task's.
> - **Finding 7 — five hatch options touch `T-046`'s reservation, unmeasured.** `--continue`,
>   `--no-continue`, `--part`, `--no-part` and `--post-overwrites` all change how yt-dlp treats a
>   file already at the target path, and the download session leaves a zero-byte reservation there.
**Relevant context:** `REQ-031`, `ARC-010`, `REQ-009` (the pattern), `T-034` (path containment),
`DAT-003` and `DAT-004` (redaction, and whose text this is), `ARCHITECTURE.md` §8 (a request is
frozen at job-creation time), `ARC-002` (it crosses a process boundary and must pickle),
`core/models.DownloadRequest`, `downloader/ytdlp_adapter.build_options`
**Affected surfaces:** `core/models.py`, `core/presets.py`, `downloader/ytdlp_adapter.py`,
`persistence/` (the request gains a field, so a migration), the preset/options UI, and their tests
**Risk:** **High.** It is a new route to two boundaries whose breach is Critical-band: writing
outside the chosen directory, and a secret in a log

#### Scope

An *Additional yt-dlp options* field, per preset and overridable per job, taking command-line
syntax, **parsed into a validated structure at job-creation time** and merged into `build_options`
under a stated precedence.

- **Parsed, not passed through.** The stored field is declared, typed, frozen and picklable like
  every other member of `DownloadRequest`; an unparsed string handed to yt-dlp is not acceptable
  even as an intermediate step
- **Containment.** Options that redirect where files land go through `T-034`'s check, not beside it
- **Redaction.** Values are this application's text under `DAT-004` and are redacted as such
- **Refusal.** An application-owned or excluded option is refused **where the user typed it, with
  the reason** — never accepted and dropped
- **Precedence.** A typed field wins over the hatch for the same user-owned key, because it is the
  one with a visible control; an application-owned key is never overridable at all

#### Acceptance criteria

- A valid option typed into the field reaches yt-dlp, proved by the option dictionary the worker
  receives rather than by the download succeeding
- **The same intent expressed as a typed field and as a hatch option produces the same option
  dictionary** — the assertion that keeps two routes from meaning two things
- An option that would write outside the output directory is **refused or contained**, with a test
  that fails when the containment call is removed
- **No hatch value appears unredacted in any log**, under the existing redaction test extended over
  the parsed values — including the case where the option name is innocuous and the value is not
- An application-owned option and an excluded option are each refused at edit time with a stated
  reason, and a test asserts they never reach `build_options`
- A malformed field fails **at edit time**, not after the bytes are spent — the same rule
  `audio_quality` already follows and for the same reason
- The migration adding the field round-trips an existing queue, and an old row without it loads
- `requires_ffmpeg` still answers correctly for a post-processor the hatch installed
- Both mypy platforms, `ruff`, the model, adapter, persistence and UI tests are clean
- **The refusal list is keyed on the value `parse_options` produces**, and a test asserts that
  `--geo-bypass` is refused for the same reason `--xff` is **while `--no-geo-bypass` is not refused
  as a bypass** — it fails if the list is rebuilt on option strings *or* on destinations (Finding 4,
  as corrected by `T183-R1`)
- **All five refused classes are enforced**, `app:policy` included. It is 10 rows the application
  owns by behaviour rather than by setting a key, and a refusal list built from the other four
  omits every one of them
- **`--break-on-existing` and `--break-per-input` are measured, not assumed inert.** At the pin
  `_match_entry` can raise on the current item and this worker calls `extract_info` directly rather
  than through `YoutubeDL.download`, so the option can turn the current job into a failure. Keep
  them hatch-reachable only if that effect is visible to the user
- **Every option the parser accepts is dispositioned, suppressed ones included.** A test walks
  `create_parser()` and fails on an option that is neither refused, nor typed, nor hatch-reachable
  — the documented 250 are not the parser's whole surface
- **`--continue`, `--no-continue`, `--part`, `--no-part` and `--post-overwrites` are measured
  against `T-046`'s reservation**, not reasoned about: a test shows what each does to a job whose
  target path already holds the zero-byte exclusive-create file (Finding 7)
- **The `writethumbnail` merge is stated and tested** — the application sets it to embed and delete,
  `T-249`'s control sets it to keep, and one of them has to win by a written rule (Finding 6)

#### Out of scope

- Typed fields for individual options — those are `T-183`'s tasks
- yt-dlp **configuration files** as an input route. A config file is a second, invisible source of
  options and would defeat every check above; if it is ever wanted it needs its own decision
- Per-entry hatch options within a playlist — `T-110` owns per-entry anything

---

*(**The nine typed-field tasks, `T-247` … `T-255`**, filed 2026-08-16 by `T-183`, which is where
the option lists come from: `docs/YTDLP_OPTION_AUDIT.md`. **44 options over nine tasks** — the
typed class minus the 21 that already have a `DownloadRequest` field. Counted, and
`tests/unit/test_option_audit.py` asserts the partition, so a task that quietly grows or drops an
option fails a gate.)*

**The following is true of all nine.** Each still states its own `**Status:**`, because `T-096`'s
gate reads that line per entry and a shared one would exempt nine tasks from the check that six
review rounds exist to enforce:

- **Owner:** Implementer · **Phase:** Phase 4.5, filed 2026-08-16
- **Depends on:** `T-183` approved. **Not on `T-184`** — a typed field is a declared member of
  `DownloadRequest` and needs nothing from the hatch. Nine independent tasks, in any order
- **Relevant context:** `ARC-010` §1, `REQ-030`, `docs/YTDLP_OPTION_AUDIT.md`,
  `core/models.DownloadRequest`, `core/presets.py`, `downloader/ytdlp_adapter.build_options`
- **Affected surfaces:** `core/models.py`, `downloader/ytdlp_adapter.py`, `persistence/` (each new
  field is a migration), the preset and options UI, and their tests
- **Acceptance criteria, common to all nine.** Each option below becomes a declared, typed,
  validated, frozen and picklable member of `DownloadRequest` (`ARC-002`, `ARCHITECTURE.md` §8);
  **the value is proved to arrive by asserting on the option dictionary the worker receives**, not
  by the download succeeding — `T-012` produced five defects that were values computed correctly
  and then not acted on, and `T012-R5` two more where yt-dlp accepted a key and ignored it; a
  malformed value fails **at edit time**; the migration round-trips an existing queue and an old
  row without the field loads; every control is keyboard-reachable and screen-reader-labelled
  (`NFR-005`); `ruff`, both mypy platforms and the touched suites are clean
- **Risk:** Medium for all nine — breadth rather than depth, and `NFR-008`'s churn lands on each

### T-247 — Video selection: which items, how big, how old

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Priority:** High among the nine — playlist item selection is the most-asked-for of the 44
**Options (7):** `-I/--playlist-items`, `--min-filesize`, `--max-filesize`, `--date`,
`--datebefore`, `--dateafter`, `--max-downloads`
**Specific criteria:** `-I`'s range grammar is parsed and refused at edit time, not handed to
yt-dlp as a string; the three date options accept yt-dlp's own relative forms (`today-2weeks`) or
refuse them with the reason; `--max-downloads` interacts with the queue's own counting and the
interaction is asserted rather than assumed.

### T-248 — Filename shaping and the modification time

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (7):** `--restrict-filenames`, `--no-restrict-filenames`, `--windows-filenames`,
`--no-windows-filenames`, `--trim-filenames`, `--mtime`, `--no-mtime`
**Specific criteria:** **`T-034`'s containment check runs after these, not before.** All three
filename options change what yt-dlp writes, and `--trim-filenames` can shorten a name into a
collision; the containment and collision tests are extended over each, and a test fails when the
check is removed. `--windows-filenames` is asserted on **both** platforms — its whole purpose is a
platform difference, and a Linux-only assertion proves nothing about it.

### T-249 — The sidecar writers: description, info JSON and thumbnail files

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (7):** `--write-description`, `--no-write-description`, `--write-info-json`,
`--no-write-info-json`, `--write-thumbnail`, `--no-write-thumbnail`, `--write-all-thumbnails`
**Specific criteria:** every file these write lands inside the chosen directory, through `T-034`
rather than beside it. **`--write-thumbnail` shares `writethumbnail` with the application**
(`T-183` Finding 6): `build_options` sets it to embed and then delete, this control sets it to
keep, and the resolution is one written rule with a test — the control is tri-state (off, one,
all). **`--write-info-json` writes a file yt-dlp's own help calls personal information**, so
`DAT-003`'s redaction question is asked of it before it ships, not after.

### T-250 — Format depth: sorting, checking and the merge container

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (4):** `-S/--format-sort`, `--check-formats`, `--no-check-formats`,
`--merge-output-format`
**Specific criteria:** `--format-sort`'s field grammar is validated against yt-dlp's own accepted
fields rather than passed through; `--check-formats` costs a request per format and the format
table's probe budget is stated (`T-161`'s per-entry lesson); `--merge-output-format` and
`remux_container` are two ways to name a container and the precedence between them is written down.

### T-251 — Subtitle depth: automatic captions, format and conversion

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (4):** `--write-auto-subs`, `--no-write-auto-subs`, `--sub-format`, `--convert-subs`
**Specific criteria:** `--convert-subs` installs an ffmpeg post-processor, so `requires_ffmpeg`
answers true for it and the user is told **before** the bytes are spent (`REQ-024`); automatic
captions and real subtitles are distinguishable in the UI, because "no subtitles" and "no *human*
subtitles" are different answers.

### T-252 — Download tuning and the retry policy the settings screen shows

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (7):** `-N/--concurrent-fragments`, `--fragment-retries`, `--extractor-retries`,
`--socket-timeout`, `--download-sections`, `--live-from-start`, `--no-live-from-start`
**Specific criteria:** **the three retry knobs this task owns are presented as one policy**, not
three integers — and the entry no longer calls them *the whole* retry policy, because
`--file-access-retries` and `--retry-sleep` stay in the hatch (`T183-R4`'s wording point) —
`--retries` already exists and `ytdlp_adapter` carries a comment deferring `--fragment-retries`
here by name, so this task is where the difference between them stops needing a comment to explain.
`--download-sections` takes a time-range grammar that is parsed and refused at edit time.
`-N` interacts with the pool's own concurrency (`ARC-007`, `CONCURRENCY_MAXIMUM = 16`) and the
interaction is measured rather than assumed.

### T-253 — Network reachability: address family and politeness delays

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (4):** `-4/--force-ipv4`, `-6/--force-ipv6`, `--sleep-interval`, `--max-sleep-interval`
**Specific criteria:** `-4` and `-6` share yt-dlp's `source_address` and are mutually exclusive —
`DownloadRequest` makes that unrepresentable rather than validating it; `--max-sleep-interval` is
refused without `--sleep-interval`, which is yt-dlp's own rule, and it is refused at edit time.

### T-254 — SponsorBlock, opt-in per preset

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (3):** `--sponsorblock-mark`, `--sponsorblock-remove`, `--no-sponsorblock`
**Specific criteria:** **off by default, and the control says what enabling it sends.** `SEC-003`
permitted this and `NFR-007` was amended to name SponsorBlock as a third permitted destination
*conditional on the user enabling it*; a test asserts no SponsorBlock request leaves the process
while the option is off. The category lists are validated against yt-dlp's own. `--sponsorblock-api`
is **excluded** — `SEC-003` declined a configurable endpoint — and this task does not reopen it.

### T-255 — Per-extractor arguments

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Priority:** Lowest among the nine — one option, and the most expert-facing of the 44
**Options (1):** `--extractor-args`
**Specific criteria:** the `IE_KEY:ARGS` grammar is parsed into a validated structure, never stored
as the string the user typed; an unknown extractor key is refused **with the reason** rather than
accepted and ignored, which is `T012-R5`'s defect exactly; values are redacted under `DAT-004` like
any other text this application supplies, because an extractor argument can carry a token.

---


## Blocked

### T-074 — The Windows suite segfaults intermittently while the result pump is delivering

**Status:** **Blocked — on `T-092`, 2026-08-20. Still undiagnosed, still not blocking Phase 1**
(`OPS-007`, maintainer risk decision 2026-07-29). Downgraded **High → Medium**.

**The dependency was always there; the entry just never said it.** This task's own text already
concluded that only a **recurrence carrying a dump** can supply criterion 2 — *a stack is not a
cause* — and arming `STARBASE` to capture that dump **is** `T-092`. Meanwhile `Depends on:` read
*"nothing"* and the entry sat under `## Ready`, which asserts somebody can pick it up and make
progress. **Nobody can.** Repetition is spent at **466 attempts** — this entry's 361 plus the 105
full-suite Windows runs counted on 2026-08-20, which are more of the same shape rather than a new
one — and the one plan that remained — accumulating clean Windows runs — was measured on 2026-08-20 and
**cannot discriminate**, because the pre-fix sample is equally clean.

**What this changes is the board, not the risk.** The residual `OPS-007` accepted is unchanged and
still accepted; the four criteria are still deliberately not rewritten; and **the detection is in
the code rather than in this entry** — a recurrence turns the `windows desktop` job red whether or
not anybody is holding this task open. What moves is the honest label: this is waiting on a
machine being armed, which is `T-092`, which is waiting on a person.

*(Filed as a correction rather than a re-triage: nothing about the defect changed on 2026-08-20.
What changed is that the last avenue this entry proposed was tried and recorded as insufficient,
which left `Ready` claiming work that does not exist.)* The faulting object of the access violation is
unknown, product-versus-harness is unresolved, and the crash has never been reproduced: the
recorded **0 in 36** deliberate full-suite runs, plus **0/15 at `35fc7ec`** (run `30478557533`,
post-`T-090`) — **51 full-suite runs** in total, with 60 clean runs of the crashing test and 250
clean in-process iterations beside them. **361 attempts, zero events**, across three shapes and two
heads.

**`T-128` is diagnosed as of 2026-08-04, and it was a *harness* defect** — a fixture teardown
dropping a `QObject` that still owned a running `QTimer`, so the dispatcher followed a pointer into
freed memory. Two core dumps and a sub-second reproduction establish it; `src/` is not implicated,
because nothing there reads `is_idle` and the application holds one manager for the life of the
process.

**The free-evidence strategy below was tried on 2026-08-20 and it does not work. The runs were
gathered; what they cannot do is discriminate.** Measured rather than assumed: **105 completed
full-suite Windows runs** on `STARBASE` between 2026-08-04 and 2026-08-20, **zero native crashes**.
Method, so it can be re-run: every `CI` run since the `T-128` teardown fix at `bd4dde8`, taking the
`windows desktop` job's **`Full suite` step conclusion** rather than the job's — 92 `success` plus
**13 `failure`**, and the 13 count because each one **ran to completion with an ordinary pytest
tally**, which a process death cannot produce. 22 `cancelled` and 14 `skipped` are excluded because
the suite did not finish; the 14 are `T-270`'s window, where the step never ran. **Four of the 145
runs are accounted for separately and were not in the first telling of this** (`T074-R5`): they have
no `windows desktop` job at all — `31080589319`, `31120246285`, `31956224066` cancelled, and
`32042191296` failed before it. 92 + 13 + 22 + 14 + 4 = **145**, and none of the four is a completed
run, so the 105 is unchanged.

**Why that settles nothing, and it is this task's own arithmetic that says so.** The pre-fix sample
was **0 events in 51 full-suite runs**. The post-fix sample is **0 events in 105**. *"If the crash
stops recurring"* cannot be observed as a change, **because it had already stopped recurring before
the fix landed** — there is no measured pre-fix rate to beat, so the comparison is undefined.

**What the 105 buys is a dated zero and nothing more, and the first version of this paragraph
claimed more** (`T074-R5`). It gave a rule-of-three **2.9% per-run ceiling**, which assumes
exchangeable trials sharing one underlying probability. **These runs do not share one.** They span
sixteen days and many heads: between `bd4dde8` and `06745fa` the manager and test-lifecycle
surfaces alone move by **2 886 insertions and 622 deletions**. **`T074-R1` had already ruled exactly
this** — samples from materially different heads are not one population, and it required exact-head
observations rather than a rate. *A rate quoted over a changing tree is the same error as a rate
quoted from four observations on different heads*, which is the sentence this entry has carried
since `T074-R1` and which I re-made from the other direction.

**The observation and the non-discrimination argument both stand**; only the ceiling is withdrawn.
Neither `OPS-007`'s accepted residual nor the Blocked-on-`T-092` disposition ever rested on it.

**This is `T238-R2`'s ruling arriving at a second task, and neither entry saw it coming.** That
finding replaced `T-238`'s criterion 6 because *"a larger clean sample cannot distinguish **the
guard worked** from **the crash was always this rare**"*. **The sentence transfers verbatim**: swap
*guard* for *corrected teardown* and it is the paragraph below. Two tasks proposed the same
instrument against the same class of defect, and one of them had already had it ruled out.

**So what would actually move this is `T-092`, and nothing cheaper.** Clean runs cannot supply
criterion 2; only a **recurrence with a dump** can, which is what `T-092` arms `STARBASE` to
capture. Until then the honest position is unchanged: the residual is accepted under `OPS-007`, and
**the accumulating-runs plan is recorded as tried and insufficient rather than left open as
available**.

*(The paragraph below proposed that plan and is kept, because it is what was tried. It was
reasonable when written — what it missed is that its own Status paragraph already recorded the
pre-fix sample as clean, which is the fact that makes it unable to discriminate.)*

**That is a lead here, and it is the strongest one this task has ever had.** The Windows crash
recorded above happened in
`test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget` — **the same file and the
same `manager` fixture** whose teardown `T-128` found at fault, with the same `ResultPump` thread
alive in the traceback. The corrected teardown is now on both platforms.

**It is still not established as the same defect, and the bar has not moved.** Windows produced an
access violation and `T-128` a SIGSEGV; this task's faulting object was never determined, so there
is still nothing to compare against; and *a stack is not a cause* — this task's own words, which
apply to the resemblance as much as to the stack. What can be done now is cheap and was not before:
**`STARBASE` runs the full suite on every push (`OPS-010`), so repeated green Windows runs against
the corrected teardown are evidence that costs nothing extra to gather.** If the crash stops
recurring there over a meaningful number of runs, that is the first positive evidence this task has
had; if it recurs, the harness fix is ruled out as its cause and that is worth just as much.

*(This block read "A candidate reproduction exists … `T-128` owns finding out". `T-128` has now
found out, and what it found does not implicate the product.)*

**The four acceptance criteria below stay unmet, deliberately not rewritten.** All four presuppose
a deliberate reproduction, which is the one thing no instrument has produced, so `OPS-007` accepts
the residual rather than redefining the bar. `T-092` arms `STARBASE` to capture a crash dump so a
recurrence supplies criterion 2 — *a stack is not a cause* — instead of another anecdote.

*(This read "Ready — still undiagnosed and still blocking Phase 1" until `OPS-007`. Before that it
read "In Review — diagnosed and fixed", which `T074-R4` found unsupported; what was fixed is
`T-090`, and `T-090` is **not** established as this crash's cause — the pre-fix sample was equally
clean, so a clean post-fix run carries no causal weight.)*

**A separate defect was found on the way and is `T-090`.** The `T-038` log listener could be left
reading a queue that something else had closed — a real race on the same thread the crash
traceback names, now fixed with tests. **That is not this task.** Calling it "diagnosed and fixed"
claimed a causal link to the historical access violation that no evidence supports, which is what
`T074-R4` reports. This task's acceptance criteria remain unmet.

*(Superseded, and worth keeping: this block read "diagnosed and fixed" on 2026-07-29. Finding a
real defect near a crash is not the same as finding the crash's cause, and the wording did not
keep them apart.)*
`0/12 at ea53c71` (run `30429327464`). That is evidence against the original 25% anecdote and is
**not** a rate: the four original observations came from materially different heads, so they are
not one population, and a single event gives no bound worth quoting (`T074-R1`). The faulting
object is unknown, product-pump versus harness is unresolved, and there is no correction mutation.
**Phase 1's Windows criterion stays unverified.** *(This block claimed "1 in 16, not 1 in 4"; that
promoted samples from changed heads into a stable rate.)*
**Owner:** Implementer
**Priority:** **Medium** — downgraded from High by `OPS-007`. It is still an access violation in a
module under `src/`, in the suite `OPS-005` and `T-073` made Phase 1's only Windows gate; what
changed is that 361 attempts produced no reproduction, so there is no work left that repetition can
do. It returns to High the moment it recurs
**Phase:** Phase 1
**Depends on:** **`T-092`** — which is itself Blocked on somebody at `STARBASE`. The Windows
runner exists; what does not exist is a configured crash dump, and without one a recurrence
produces another anecdote rather than criterion 2
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

#### The ordering hypothesis, tested — 2026-07-29

The earlier attempts ran the crashing test alone and its module. The Windows failure happened
inside a **full-suite** run, and `T-069`'s precedent is that suite ordering was the entire story,
so that was the remaining Linux hypothesis. Six deliberate full-suite runs:

| Attempt | Result |
|---|---|
| Crashing test alone, 40 iterations | 40 passed |
| `test_manager.py` entire, 5 runs | 5 × 71 passed |
| **Full suite, 6 runs** | **6 × 1401 passed, every exit code 0** |

**Linux is now exhausted as a route to this defect**, at least by repetition. Three shapes of
attempt, none of which reproduced it. That is not proof of a Windows-only fault — it is the
absence of a Linux reproduction after looking in the three places worth looking.

**So the measurement has to happen on the machine that shows it.** `.github/workflows/t074-repeat.yml`
runs the suite N times on `STARBASE` and reports a rate. Three things about it are deliberate:

- **Manual dispatch, in its own workflow.** `ci.yml` is a gate and runs on every push; this is an
  instrument. Folding it in would mean paying its cost on every push or making a gate
  conditional.
- **It does not stop on the first crash.** A rate needs every iteration attempted; stopping early
  turns it back into an anecdote.
- **It separates crashes from failures by exit code.** `pytest` exits 1 for a failing assertion.
  A crash takes the interpreter with it, so the code is a signal or an access violation — and
  `T-074` is not a failing assertion. Counting them together would let an ordinary red test
  inflate the crash rate.

"About one in four" came from four ordinary CI runs, where the denominator was however many times
the gate happened to run. This makes the denominator a choice, which is what the acceptance
criteria ask for.

#### The instrument ran — 2026-07-29, run `30429327464`

Twelve full-suite iterations on `STARBASE`, every one attempted:

| Iterations | Crashes | Failures |
|---|---|---|
| **12** | **0** | 0 — `1395 passed, 20 skipped, 32 deselected` each time, 209-217 s |

**"About one in four" was a denominator of four**, and this batch is not a replacement for it.
`0/12 at ea53c71` says the crash is not reliably reproducible at that head. It does **not**
establish a rate (`T074-R1`): the four earlier runs and these twelve are not one controlled
population — the manager and the full-suite composition changed materially between them, including
new integration tests — and after a single event an aggregate point estimate is not a bound. A
clean run is unremarkable under a 25% failure probability and under a 6% one alike.

The crash is real. It happened with a traceback naming `[ResultPump]` and `multiprocessing`'s
`_monitor`, on a documentation-only commit whose code was byte-identical to a passing run.

**It stays a Phase 1 blocker, and the reason is where it landed.** The only observed native crash
is in ordinary `ResultPump` delivery — the exact `ARC-002` path Phase 1 exists to prove — so the
uncertainty cannot be resolved in favour of product safety by counting clean runs. Downgrading it
or accepting the risk is the maintainer's explicit decision to record, not an inference this task
may draw.

**Still unknown: the cause.** Nothing here narrows it. A larger batch is running to either bound
the rate further or catch one with fresh diagnostics; the workflow keeps every iteration's output,
so a crash caught there arrives with its traceback rather than as a count.

*(Superseded: this section previously read "Not yet run. The job is authored and pushed;
executing it needs `STARBASE` and is the next step on this task." It has now run.)*

#### Diagnostic session, 2026-07-29 — narrowed, not diagnosed

**Both threads named in the crash are ours.** The traceback listed `[ResultPump]` and
`Thread-50 (_monitor)`, and `_monitor` was read as `multiprocessing`'s. It is not: `multiprocessing`
declares no such function, and `_monitor` is
`core/logging.py`'s `_ToWhicheverHandlersWeHaveNow._monitor` — the `T-038` log listener's thread
body. So the crash happened with the result pump and the **logging listener** both live, which
points somewhere the earlier notes did not.

**A mechanism worth testing, stated as a hypothesis.** `_monitor()`'s `finally` closes the worker
log queue — a `multiprocessing.Queue` — and `stop_listening_for_worker_logs()` **waits for
nothing**, deliberately (`T038-R2`, and it is right to: the GUI thread must not block on a slow
handler). So the close runs on the listener thread while parent threads may still be logging into
that queue and a spawned writer may still hold the other end. Closing a multiprocessing queue
under a concurrent user is the kind of thing that faults natively instead of raising, which is the
shape this crash took. The crashing test is also the one that **kills** a worker rather than
asking it to stop, so a writer dying mid-record is in scope there and almost nowhere else.

**Nothing here demonstrates that.** It is a mechanism that fits, and the file it implicates has a
recorded reason for the behaviour. It is written down so the next attempt starts from a candidate
rather than from the whole suite.

**What was attempted, and what it cost:**

| Attempt | Result |
|---|---|
| Repeat batch, 24 full-suite iterations on `STARBASE` | **0 crashes** (run `30454206697`) |
| Both batches together, recent heads | **0 in 36** |
| Repeat batch, 15 full-suite iterations at `35fc7ec`, **post-`T-090`** | **0 crashes, 0 failures** (run `30478557533`) |
| The crashing test alone, 60 iterations on Windows | **60 passed, 0 failed, 0 crashed** |
| A direct stress of the logging-teardown race | **unusable — it hung on Linux before its first iteration** |

The last row is the honest one. The harness drives a parent thread logging continuously while a
spawned writer is killed and the listener is torn down; it never reached a print, so it deadlocked
in its own setup rather than measuring anything. A failed instrument is not a negative result, and
it is recorded as neither.

**Classification is unchanged: product versus harness is still unresolved**, and `T-074` remains a
High Phase 1 blocker. What has changed is where to look — logging teardown alongside the pump,
rather than the pump alone.

#### What the diagnostic session produced — 2026-07-29

It found a **different** defect, now filed as `T-090`: the log listener could be left reading a
queue something else had closed. The evidence for that moved there with it.

**What it did not produce is anything about this crash.** The access violation has never been
reproduced — 0 in 36 full-suite runs, 60 clean runs of the crashing test alone, 250 clean
in-process iterations — so its faulting object is still unknown and it is still unclassified
between product and harness. `T074-R4`: a real race on the same thread is a candidate, not a
cause, and the crash's absence cannot distinguish them when it was already absent every time.

**What is genuinely narrowed** is that `_monitor` in the traceback is the `T-038` log listener
rather than anything in `multiprocessing`, so the next attempt has two of our own threads to
account for rather than one.

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

### T-092 — Arm `STARBASE` so the next access violation leaves a cause, not a stack

**Status:** **Blocked — prepared 2026-08-01, on *somebody at* `STARBASE`.**

**Re-triaged 2026-08-04: still blocked, but it may no longer be the only route.** This task exists
because the faulting object of `T-074`'s access violation is unknown and a Windows crash dump was
the only way to get one. `T-128` records something in the same subsystem crashing on **Linux** at
roughly 2 in 39 — where a core dump needs `ulimit -c` and a pattern, not a person at a machine and
consent to write dumps on it. **That does not unblock this**, which is specifically about Windows,
and the two crashes are not established as one defect. It does mean the *cause* may become
obtainable without this task, which is worth knowing before anyone spends a trip to the desktop on
it.

Re-triaged 2026-08-03:
the machine came back that day and now runs every Windows job, so "blocked on `STARBASE`" no longer
says what it means. The three remaining criteria need a person to arm dumps, crash a process on
purpose and open the result — none of which a CI job does. **Availability was never the blocker.** The reviewer classified it
so on 2026-08-01: the safe correction is accepted (`T092-R1`) and the scope amendment is taken
(`T092-R2`), and **nothing further can be done from here.** Three criteria need somebody at the
machine.
*(This read "Ready — prepared 2026-08-01, and NOT complete", which put a task nobody could pick up
in the list of tasks to pick up.)* The maintainer's consent was given
2026-08-01 and the whole configurable half is committed: `tools/windows/crash-dumps.ps1` arms and
disarms it, `docs/WINDOWS_VERIFICATION.md` records the procedure and its disk cost, and both
`STARBASE` jobs collect a dump when one exists. **Three of the five acceptance criteria are
unmet and cannot be met from here** — they require running the script on `STARBASE`, crashing a
process on purpose, and opening the dump. See "Prepared, and what remains" below.
*(This read "Ready — the instrument `OPS-007` leans on".)*
**Owner:** Implementer
**Priority:** Medium — it buys nothing today and is the whole diagnostic plan if `T-074` recurs
**Phase:** Phase 1 origin; it is an instrument, not a deliverable, and gates no exit
**Depends on:** `STARBASE`, which exists. Needs the maintainer's consent to write dumps on a
machine they use
**Relevant context:** `OPS-007`, `T-074`, `T-073`, `docs/WINDOWS_VERIFICATION.md`
**Affected surfaces:** `docs/WINDOWS_VERIFICATION.md`, `.github/workflows/ci.yml` and
`t074-repeat.yml` (a metadata report, never a dump artifact), `STARBASE` machine configuration
**Risk:** Low to the product — it touches no source. The real risk is on the machine: dumps are
written unattended and a full-memory dump of a Python process with Qt loaded is not small

#### Scope

`T-074`'s second acceptance criterion is that **the faulting thread and the object it touched are
identified — a stack is not a cause.** `faulthandler` cannot supply that: it printed
`[ResultPump]` and `Thread-50 (_monitor)` and named neither the faulting module nor the address.
A minidump does.

So: configure Windows Error Reporting local dumps on `STARBASE` for the interpreter that runs the
suite, and have the `t074-repeat.yml` and `windows desktop` jobs **report** any dump written during
that run — name, size and timestamp into `reports/crashdumps.txt` — leaving the dump on the machine
for deliberate retrieval. Then a recurrence, in CI or in an ordinary run, produces something a
debugger can read instead of another anecdote.

*(**Superseded, and the wording matters because this is the live instruction.** This said "upload any
dump they find as an artifact", which `T092-R1` found unsafe on three counts: WER is keyed by
executable *file name* so the folder collects any `python.exe` under that account, nothing filtered
stale dumps so the deliberate proof dump would be re-uploaded on every later run and announced as a
recurrence, and a full memory dump can carry an unrelated program's heap into a CI artifact. The
metadata-only scope is the maintainer's decision of 2026-08-01 — `T092-R2`, which stayed open once
because the criterion was corrected and this sentence was not.)*

**Consent first, and this is not a formality.** `STARBASE` is the maintainer's own desktop.
`OPS-005` and `T-073` both carry the rule that a workflow must never provision it, and
`docs/WINDOWS_VERIFICATION.md` records what installing Python there already cost. Dump capture is
machine configuration and belongs in that document as a manual, reversible step — not in a
workflow.

#### Acceptance criteria

- A **deliberately crashed** Python process on `STARBASE` leaves a dump at a known path — proven by
  causing an access violation on purpose, not by trusting the registry keys
- That dump, opened, names a faulting module and address. If it cannot, this task has failed at the
  thing it exists for and says so rather than reporting the keys as success
- Dump size and retention are bounded and stated; the disk cost on a real machine is named
- **The jobs report a dump's existence and never upload it** — name, size and timestamp into
  `reports/crashdumps.txt`, with the dump left on `STARBASE` for deliberate retrieval. Both the
  "a dump was written" and "no dump" paths stay green: a missing dump is the normal case and must
  not redden the gate
  *(**Scope amended 2026-08-01, maintainer decision** — `T092-R2`. This read "upload a dump when
  one exists". WER is keyed by executable *file name*, so the folder collects any `python.exe`
  under that account and a full memory dump can carry an unrelated program's heap into a CI
  artifact; the old wording could not be met without reintroducing `T092-R1`. The narrower
  alternative — copy the interpreter to a distinct name and key WER to that — is recorded in
  `docs/WINDOWS_VERIFICATION.md` rather than taken, because it changes how the suite is
  launched.)*
- `docs/WINDOWS_VERIFICATION.md` records the configuration, how to undo it, and the disk cost

#### Out of scope

- Diagnosing `T-074` — this task cannot, and pretending otherwise is what `T074-R4` caught
- Any change to `src/`
- Dump capture on Linux, or on hosted runners, which are discarded anyway
- Making `T-074`'s recurrence more likely; this is passive capture, not a stress test

#### Prepared, and what remains, 2026-08-01

**Done, and committed:**

- `tools/windows/crash-dumps.ps1` — arms WER local dumps for `python.exe` under `HKCU` (no
  elevation, scoped to one executable rather than the whole machine), and `-Remove` undoes it.
- `docs/WINDOWS_VERIFICATION.md` — why, how to arm it, **how to prove it**, the disk cost, and how
  to undo it.
- `ci.yml`'s `windows desktop` job and `t074-repeat.yml` each stamp their start time and write
  `reports/crashdumps.txt` naming any dump written **during that run** — and upload no dump at all.
  `if: always()` and `continue-on-error: true`, because **no dump is the normal case and must not
  redden the gate**.
  *(This described copying the dump into `reports/`, which is what `T092-R1` found unsafe. The
  scope amendment above is the maintainer's, taken 2026-08-01.)*
- Full dumps (`DumpType 2`) rather than mini, stated with the cost: ~300–600 MB each for a Python
  process with Qt loaded, five kept, so up to ~3 GB. A mini dump routinely lacks the heap the
  faulting address points into, which is the entire question `T-074` is asking.

**Unmet, and honestly so** — each needs the machine:

| Criterion | State |
|---|---|
| A deliberately crashed process leaves a dump at a known path | **Unmet.** Nobody has run the script or the crash |
| The dump names a faulting module and address | **Unmet**, and it is the one that decides whether this task succeeded at all |
| Dump size and retention bounded and stated | **Met** — in `docs/WINDOWS_VERIFICATION.md` |
| The jobs **report** a dump and never upload one | **Half met.** The steps exist and both YAML files parse; no CI job has executed a step since 2026-07-30, so neither branch has run |
| `docs/WINDOWS_VERIFICATION.md` records config, undo and cost | **Met** |

**Why this is filed as prepared rather than done.** `T074-R4` caught this task's predecessor
reporting registry keys as evidence. The keys are not the evidence; a dump that names a faulting
module is. Until somebody runs the two commands in the document on `STARBASE`, the correct status
is that the instrument is *ready to arm* and has never fired.


#### Correction, 2026-08-01 — `T092-R1`

**The prepared upload was unsafe before it had ever run.** Three problems, all real:

- **WER is keyed by the executable's file name**, so `python.exe` collects *any* Python process
  under that account, not this project. There is no narrower WER key. A dump in the folder is
  therefore not by itself evidence of `T-074`, and the report now says exactly that.
- **Nothing cleared or time-filtered the folder**, so the deliberate proof dump — or a months-old
  one — would be re-uploaded on every later run and announced as a recurrence that never happened.
  Both jobs now stamp their start time and report only what was written after it.
- **A full memory dump can carry an unrelated process's heap**, and a CI artifact is a copy of it
  somewhere else. **Nothing is uploaded now.** The jobs write `reports/crashdumps.txt` with the
  dump's name, size and timestamp and leave the dump on `STARBASE` for deliberate retrieval.

`docs/WINDOWS_VERIFICATION.md` gains the provenance and disclosure reasoning beside the disk cost,
which is what it was missing. The narrower alternative — copy the interpreter to a distinct file
name and key WER to that — is recorded rather than done, because it changes how the suite is
launched.

**Three acceptance criteria remain unmet and still need the machine.** Nothing here changes that.

---

### T-068 — Qt writes a font warning to stderr on a real Windows machine

**Status:** **Blocked — on the runner question, which just got harder**, 2026-07-28; re-triaged
2026-08-03 and **again 2026-08-04, unchanged and verified**. `OPS-010` restored the Windows suite
to every push, which sounds like it would help and does not: it restored the **`STARBASE` desktop**
job, while `check`'s hosted Windows leg stays dropped. `vars.WINDOWS_RUNNER` is set, so hosted
Windows still does not run at all. The cost of answering this is now explicit — unsetting that
variable for one run spends hosted Windows minutes at a 2x multiplier, against a nearly exhausted
quota. The frozen half is now obtainable: `frozen windows` runs on `STARBASE`. The other half
asks *why the hosted runners never showed the fault*, and hosted Windows **no longer runs at all**
while `WINDOWS_RUNNER` points at the desktop (`docs/project/TESTING.md` §10). Answering it now needs that
variable unset deliberately for a run. A consequence of the gate rebuild, recorded rather than
discovered later. The
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
the shape `docs/project/TESTING.md` §13 exists to catch, which is why this was not allowlisted into
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

**Status:** **Blocked — on a reproduction, not on a machine**, 2026-07-28 at `9c92c32`.

**Re-triaged 2026-08-04, and a candidate reproduction was checked and rejected.** The overnight
`-n auto` run failed exactly this task's subject —
`test_the_survival_check_can_tell_a_live_process_from_a_dead_one`, `still_running`'s own test — on
Linux, which looked like the reproduction this task has waited for since July. **It is not.** The
assertion was *"a running process was reported dead"*: `still_running([alive.pid])` returned `[]`
for a live process. This task is the **opposite** symptom — a *reaped* process reported **alive**.
Same helper, inverted direction, and a false negative under parallel load is a different defect
from a false positive on Windows.

Recorded rather than left for somebody else to find and re-check. What it does say is that
`still_running` has a second failure mode nobody had seen, which `T-123` carries.

Re-triaged 2026-08-03: `STARBASE`'s return does **not** help. This task already had its Windows
evidence and that is the finding — reverting the fix passes 20/20 there, so the defect does not
reproduce on the machine we have. More runs of the same machine cannot close it. The reviewer
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
**Relevant context:** `T-019`, `docs/project/TESTING.md` §7 (Cancellation, Worker crash)
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
fail is the shape `docs/project/TESTING.md` §13 exists to catch. A false *alive* fails loudly, as here; the
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

### T-039 — Verify Windows installer behavior on the runner

**Status:** **Blocked — until Phase 5 produces an installer.** Proposed work with nothing to do
until then; the installer it would verify does not exist yet
**Owner:** Implementer
**Priority:** Medium now, High once Phase 5 starts — it must land before the first public release
**Phase:** Phase 5
**Depends on:** the Phase 5 installer, `T-026` (establishes the real-plugin Windows job)
**Relevant context:** `OPS-004`, `REL-001`, `docs/project/TESTING.md` §9, `REQUIREMENTS.md` §3
**Affected surfaces:** `.github/workflows/ci.yml`, `docs/project/TESTING.md` §9, `REQUIREMENTS.md` §3
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
- `docs/project/TESTING.md` §9's manual list drops installer placement and removal, and
  `REQUIREMENTS.md` §3 narrows to match — **only once this job is landed and green**
- The added CI time is recorded against `T-006`'s budget

#### Out of scope

- Whether the installer *feels* normal — `OPS-004`'s subjective residue, still human, still
  blocks first release
- Upgrade-over-existing-install and downgrade paths — real, but a separate task once the
  versioning story exists
- Any non-Windows packaging

---

### T-297 — A thumbnail flickers while the window is resized with a panel open, and the cause is unknown

**Status:** **Blocked on `T297-R1` and `T297-R2`, both High — the product fix is sound and the
*record* of how it was reached is not** (reviewed at `d44700c`). Corrections landed 2026-09-03; two
of the three findings need the maintainer rather than more work.

- **`T297-R1` — no real-display capture.** The reproduction was taken on a nested
  `kwin_wayland --virtual`, and its PNG is a labelled reconstruction rather than a captured frame.
  The criterion asks for a real display and a capture. **Needs either a pre-fix run on the live
  session or an explicit amendment** naming what is surrendered. Not mine to take, and not something
  to run unattended on the maintainer's desktop.
#### Ruled 2026-09-04: the exception is granted, and the capture is being taken

**`T297-R2` — exception granted.** The maintainer accepted that criterion 2 was missed and that the
sequence cannot be created retroactively. What stands in its place is the dated correction in
`docs/project/evidence/2026-09-01-T297-panel-collapses-during-resize.md`, which says the cause section is
superseded, names the real writer, and records that the `T-296` relation was backwards. **The
commits are not rewritten.** This finding no longer blocks Complete.

**`T297-R1` — being answered rather than amended.** The maintainer chose to run the pre-fix tree on
a real display and keep an actual capture, over amending the criterion.
`tools/t297_prefix_capture.sh` puts that tree on the display from a `git worktree` at `331845d`,
with `PYTHONPATH` overridden so the editable install cannot serve the fixed code instead. **Until
that capture exists this task stays Blocked**, and a run that does *not* reproduce is a result to
record rather than a reason to try again.

- **`T297-R2` — the pre-fix record names the wrong cause.** `331845d` says the cause is
  `_on_list_resized`'s deferred relayout and that it is *not* `T-296`'s; both are wrong, and the
  real cause first appears in the commit that changes source. **The evidence file now carries a
  dated correction** saying so and recording that the criterion was missed. Moving this to Complete
  needs the maintainer's explicit exception; the commits are not rewritten.
- **`T297-R3` — corrected.** The probe froze only part of itself before the reconstruction, so the
  post-fix counts included the instrument's own forced 26 px. Every counter is frozen now and a
  control asserts none moved — **it caught a real drift on the first run** (38 → 40 paints) rather
  than passing. Both trees were re-measured rather than corrected by subtraction.

**The fix itself was not in doubt in the review and is unchanged.** **It was not the deferral the
entry hypothesised.** `QAbstractItemView` keeps `setIndexWidget` widgets in **the same map as item
editors**, so every `updateGeometries()` pass handed the open row's panel to
`RowDelegate.updateEditorGeometry` — which applied `_control_of`, the row's *format-combo* slot, to
it. A 354 px panel became **26 px**. A resize calls `updateGeometries()` once per step, so the panel
collapsed and was restored once per step, and the view painted the row inside each gap: `paint`
draws the thumbnail on every row it is given, because an open one is supposed to be covered.

**Measured under a compositor before anything was changed**, which is this task's first criterion —
`docs/project/evidence/2026-09-01-T297-panel-collapses-during-resize.md`, with a capture. 110 resize steps:
**107 collapses to 26 px, 107 paints of the row its panel did not cover**, and 109 of 110 steps
nevertheless *settling* correctly, which is why the first reading — which sampled after each step —
saw nothing. After the fix, re-measured 2026-09-03 with the corrected probe: **0 exposed paints, 110/110
settled**, and the panel's own resize events fell from **214 to 8, with 0 collapses to 26 px**. *(This
read "214 to 9" and one collapse; that ninth event and that collapse were the instrument's own
reconstruction — `T297-R3`. The pre-fix figures re-measured identically: 107 exposed, 214 resizes,
107 collapses, 109 of 110 settling.)*

**The fix is the guard its two siblings already have.** `setEditorData` and `setModelData` both
begin `if not isinstance(editor, QComboBox)`; `updateEditorGeometry` did not. Anything that is not
this delegate's editor now goes to `super()`, which sizes an editor to `option.rect` — exactly right
for an index widget spanning the row.

**This is what `T-296` was working around, and that is worth stating rather than leaving to be
rediscovered.** `T-296` reordered `_mount_panel` so `scrollTo` — which calls `updateGeometries()` —
could not undo the geometry `setGeometry` had just set. The reorder is still correct and still
tested; the reason a scroll destroyed the geometry was this method, one layer down. **`T-296` is not
reopened**: it is Complete, approved, and its own regression still passes.

*(Filed 2026-08-28 by `T-212`'s checklist run, deliberately without a cause.* The maintainer's
report: *"when changing the window size while the naming information is up, the thumbnail cuts in
and out very rapidly. That shouldn't happen."*)
**Owner:** Implementer
**Priority:** Low — it is visual noise during a drag, and it is the least understood thing the run
found
**Phase:** Phase 4 (polish; **not** a plan deliverable)
**Depends on:** nothing
**Relevant context:** `ui/add_dialog.py` `panel_height_for`, which reads the **viewport's** height,
so every resize step changes the row's size hint; `_mount_panel`'s note that `setIndexWidget`
defers geometry to `updateEditorGeometries`, which runs on paint; `T-296`
**Affected surfaces:** `ui/row_delegate.py` (`updateEditorGeometry`), `tests/ui/test_row_delegate.py`;
the instrument is `tests/ui/_t297_resize_probe.py` and `tools/t297_resize_session.sh`
**Risk:** Low

#### What was measured, and what it does not show

**It did not reproduce offscreen.** Across eight resize steps with the template panel open:

```
thumbnail loads : 0        # nothing re-fetches
cancels         : 0
```

and the panel's geometry matched the row's `visualRect` at **every** step, from 762 px down to
430 px and back up. So it is neither the thumbnail being reloaded nor the panel losing coverage in
any way a headless process can see.

**The plausible mechanism is unproven and is recorded as a hypothesis, not a finding.**
`panel_height_for` reads `self._list.viewport().height()`, so every resize step changes the row's
size hint; the panel's re-placement is deferred to paint; and the delegate underneath — which draws
the thumbnail — is what shows in any gap. That is consistent with `T-108`'s comments and with
`T-296`, and it is not evidence.

#### Acceptance criteria

- **It is reproduced on a real display first**, with a capture, and the reproduction is recorded in
  `docs/project/evidence/` before anything is changed. An offscreen process does not do a continuous resize
  and its style is not necessarily the session's
- **The cause is named before the fix**, and if the cause turns out to be `T-296`'s, this task is
  closed against that one rather than fixed twice
- **If it proves to be Qt or compositor behaviour** this application can only work around, that is
  recorded as the finding and the workaround is a separate decision

#### Out of scope

- Guessing. `T-296` is filed with a measured cause; this one is not, and the two should not be
  merged on the strength of sitting near each other


---

## Complete

### T-287 — Minimizing the main window leaves its dialogs on screen

**Status:** **Complete — Approved at `ac1c12e` on 2026-08-31.** The window takes its dialogs down
when it goes off screen and brings them back when it returns. **Hidden, never closed**, so a
half-typed paste, a preset mid-edit and a format table's selection all survive; modality is a
property and is untouched, asserted rather than assumed. **Nine mutations, all killed.**

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-287--minimizing-the-main-window-leaves-its-dialogs-on-screen).

### T-284 — *Same as all* names the relation and drops the value the spec asks for

**Status:** **Complete — Approved at `f0b9c80` on 2026-08-30**, after three findings and their
corrections. The control names the preset the row would follow; the editor's `None` entry names it
too, with *— following the batch* appended. `INHERITED_TEXT`'s *"Same as all"* is gone from both sites and from the codebase.
**Nine mutations, all killed.** `T284-R4`'s cleanup — qualifying the style-dependent label-field
figures, retiring the stale *"~165 px"* wording, and exempting the deliberate elision case from
`RENDER_WIDTH`'s comment — is folded in here; the reviewer required no re-review for it.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-284--same-as-all-names-the-relation-and-drops-the-value-the-spec-asks-for).

### T-298 — Frozen probes must not read a runner's user-managed yt-dlp

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t298-runner-profile).

**Status:** **Complete — Approved at `a93a53b` on 2026-08-29**, with external evidence current
through `53b4d02`. The `frozen` job gives itself a per-run profile through all five variables
`platformdirs` consults, on both matrix legs; the probes run inside it and it is removed on
`always()`. **No `src/` change** — `OPS-002` is untouched.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-298--frozen-probes-must-not-read-a-runners-user-managed-yt-dlp).

### T-291 — A canary that runs the suite against the yt-dlp we have not pinned yet

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t291-verdict).

**Status:** **Complete — Approved at `0332a68` on 2026-08-29.** Three findings corrected, and
`T291-R4` resolved by dispatched run `33231851897`.
`.github/workflows/ytdlp-canary.yml`: weekly plus `workflow_dispatch`, `LINUX_RUNNER`, its own
concurrency group, no `push:` trigger, and it writes nothing back to the repository.
`docs/project/TESTING.md` §8 gained step **10a**, which is where it blocks a bump without ever blocking a
push.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-291--a-canary-that-runs-the-suite-against-the-yt-dlp-we-have-not-pinned-yet).

### T-288 — The scroll bar is the one control the theme never dressed

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t212-validation).

**Status:** **Complete — Approved at `0332a68` on 2026-08-29.** The rendered check `T288-R1`
required was taken 2026-08-28 and found no defect. The bar is drawn by the sheet
in both orientations: a rounded handle in `border` with a 2 px margin, hover and pressed states,
the stepper arrows removed by declaration, and the groove transparent. **Four mutations, all
killed** — including putting the handle back on `surface`, which **survived a first version of the
test** that measured `contrast_ratio(theme.border, theme.window)` from the palette instead of
reading what the sheet draws. Measuring an ingredient the rule is free to stop using is the same
mistake `T-283` made three hours earlier.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-288--the-scroll-bar-is-the-one-control-the-theme-never-dressed).

### T-292 — The download folder can be chosen but not typed, and its caption says nothing worth a line

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t212-validation).

**Status:** **Complete — Approved at `0332a68` on 2026-08-29.** Three findings corrected, and
the relative-path rule is ruled rather than proposed. The folder is a `QLineEdit`
committing on `editingFinished`; a path that is missing, is a file, or cannot be written to is
refused beside the field and the field goes back to the folder in force. The caption and its blank
line are gone. **Six mutations, all killed.**

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-292--the-download-folder-can-be-chosen-but-not-typed-and-its-caption-says-nothing-worth-a-line).

### T-293 — A queued row offers *Remove*, so one playlist entry can go without the playlist

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t212-validation).

**Status:** **Complete — Approved at `0332a68` on 2026-08-29.** A queued row offers
`↑ ↓ Cancel Remove`; one entry's `Remove` goes down the single-job route and the group route is not
taken. **Four mutations, all killed.**

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-293--a-queued-row-offers-remove-so-one-playlist-entry-can-go-without-the-playlist).

### T-285 — The Options dialog offers audio-only containers to a download that keeps its video

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t212-validation).

**Status:** **Complete — Approved at `0332a68` on 2026-08-29.** No implementation finding was
ever raised; it waited on the shared exact-head Windows run, which `T212-R3` resolved at
`75cd183`. A video preset is offered the
seven video containers; an audio preset keeps all eighteen, as ruled. **Six mutations, all killed**,
including restoring the symmetry, restoring the whole list, reclassifying `gif`, and dropping the
guard that keeps a container the preset already carries.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-285--the-options-dialog-offers-audio-only-containers-to-a-download-that-keeps-its-video).

### T-283 — The row's painted *Download as* control insets its text 5 px less than the editor

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t212-validation).

**Status:** **Complete — Approved at `0332a68` on 2026-08-29.** No implementation finding was
ever raised; it waited on the shared exact-head Windows run, which `T212-R3` resolved at
`75cd183`. The painted label now starts
at **x = 7** where it started at 2, matching the editor exactly. Gates green: `ruff check .`,
`ruff format --check .`, `mypy src`, 2,377 tests. **Four mutations, all killed** — including the
one that matters, stopping `_paint_control` from calling the new helper, which **survived a first
version of the test** that measured the helper's arithmetic instead of the paint. That is `T-244`'s
shape and it is why the regression now reads pixels.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-283--the-rows-painted-download-as-control-insets-its-text-5-px-less-than-the-editor).

### T-281 — Unavailable playlist entries are carried into the queue as rows that cannot download

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t212-validation).

**Status:** **Complete — Approved at `0332a68` on 2026-08-29.**
Every discarded input position is recorded now, with the reason it went, and the denominator is the
number of entries the playlist offered.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-281--unavailable-playlist-entries-are-carried-into-the-queue-as-rows-that-cannot-download).

### T-273 — Every composed window outlives its own shutdown, and `tests/ui` accumulates them

**Status:** **Complete — Approved at `b6db88d` on 2026-08-27.** Two rounds. Round one returned
**Blocked** at `806f2e5` on `T273-R1`, which no local run could close; `T273-R2` and `T273-R3` were
corrected inside this task, and **no finding became a follow-up task**.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-273--every-composed-window-outlives-its-own-shutdown-and-testsui-accumulates-them).

### T-279 — The orphan scanner calls a live parent dead when it was launched by a console script

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t279-mutation).

**Status:** **Complete — Approved at `a0085b5`**, 2026-08-26. **All six findings are closed and
no follow-up task exists.** `T279-R1`–`R4` Resolved; `T279-R5` and `T279-R6` were handled in this
completion synchronization under `DOC-005`, which routes a minor actionable finding into the
current task's completion pass rather than into the queue. **`T-280` was created and removed by
the reviewer; nothing here re-creates it.**

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-279--the-orphan-scanner-calls-a-live-parent-dead-when-it-was-launched-by-a-console-script).

### T-272 — The orphan scanner runs only on Windows, and a Linux box has had two orphans for days

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t272-first-dispatch).

**Status:** **Complete — Approved at `12fda3a`**, 2026-08-26, review commit `de0724c`. **All nine
findings are closed.** `T272-R1`–`R4` were resolved before this round; `T272-R5` resolved on the
scope amendment; `T272-R6` after four passes; `T272-R7`, `R8` and `R9` on the second. The reviewer
reproduced the 115-hit `kirk` enumeration independently and confirmed no false current attribution
remains.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-272--the-orphan-scanner-runs-only-on-windows-and-a-linux-box-has-had-two-orphans-for-days).

### T-277 — Move the split to 32 px, so the Icon cut reaches the slot the desktop draws

**Status:** **Complete — Approved with follow-up at `4f3ca78`**, 2026-08-25, review commit
`a85b8bb`. `T277-R1` was Low and non-blocking, assigned to the Implementer for completion
synchronization with no further pass, and is **Resolved below**. **The reviewer accepted the
Linux-derived 32 px boundary as the cross-platform default**, with Windows shell frame selection
recorded as honestly unverified and the softer 32 px artwork explicitly priced in by the
maintainer.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-277--move-the-split-to-32-px-so-the-icon-cut-reaches-the-slot-the-desktop-draws).

### T-276 — Ship the pack's Icon cut at 48 px and above

**Status:** **Complete — Approved at `dcd06a0`**, 2026-08-25, review commit `09e1ecb`. **No
findings.** The reviewer independently regenerated the assets byte-for-byte, confirmed the boundary
mutations fail exactly the cases they should, and confirmed that reintroducing the Standard cut
fails all nine affected cases. Windows is verified: run `32891329714` ran **45 UI and 13 unit
resource tests** on Windows, the same set as Linux.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-276--ship-the-packs-icon-cut-at-48-px-and-above).

### T-278 — Shorten the About labels, enlarge its icon, and stop Qt eating the ampersand

**Status:** **Complete — Approved with follow-up at `107236e`**, 2026-08-25. `T278-R1` and
`T278-R2` are **Resolved**; `T278-R3` was Low and non-blocking, assigned to the Implementer for
completion synchronization with no further pass, and is **Resolved below**. The reviewer accepted
the `U+2011` copy-and-search cost for this one descriptive About string.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-278--shorten-the-about-labels-enlarge-its-icon-and-stop-qt-eating-the-ampersand).

### T-275 — Ship 32 px from a cut that keeps the trees and drops the sound-wave arcs

**Status:** **Cancelled — refused by the maintainer ruling of 2026-08-25**, four days after
filing and one day after `T-274` closed. **A second ruling the same evening granted the band this
entry asked for** — the Icon cut at 32 px — and `T-277` ships it. This stays `Cancelled` because
what it proposed was **three** bands, keeping the Standard cut above 48, and that is still refused:
`T-277` is two bands split at 32. **The disposition is unchanged and the reason for it is now
half wrong**, which is recorded here rather than by rewriting the entry. **Nothing here was found to be wrong.** Every measurement
below stands and `T-276` was built against them; what the ruling rejected is the *band*, and it
did so on evidence that did not exist when this was filed.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-275--ship-32-px-from-a-cut-that-keeps-the-trees-and-drops-the-sound-wave-arcs).

### T-274 — Replace every icon asset with the revamped logo pack, and render them from vector

**Status:** **Complete — Approved with follow-ups at `60dbbcf`**, 2026-08-21. `T274-R1` and
`T274-R2` are Resolved; `T274-R3` was non-blocking, assigned to the Implementer for completion
synchronization with no further pass, and is Resolved below. Instructed by the maintainer the same
day and built that night. The
maintainer revamped the logo and icons outside this repository and directed that they replace what
is in use. **This is not a redesign proposal and contains no judgement about the artwork**; what is
open for review is the pipeline it arrives through and the two checks that had to be rewritten
because the new artwork does not have the property the old ones measured.
**Owner:** Implementer — built 2026-08-21, awaiting a verdict
**Priority:** High, as a direct maintainer instruction. Nothing else was blocked on it
**Phase:** Phase 4 maintenance
**Depends on:** nothing. It **retires** `T-021`'s derivation and `T-071`'s trim-and-fill
**Relevant context:** `tools/icons/render_icons.py`, `tools/icons/masters/`,
`src/tracks_and_trails/resources/icons/`, `tests/unit/test_resources.py`,
`tests/ui/test_resources.py`, `T-003`, `T-021`, `T-071`, `T003-R2`, `ARCHITECTURE.md` §8
**Affected surfaces:** every icon asset, the script that renders them, and their two test modules.
**No source module changed** — `main_window.app_icon()` loads `icon.ico` and is untouched
**Risk:** Low, and it is concentrated in the tests rather than the assets. A wrong asset is visible;
a check that no longer discriminates is not, and one of the two here had stopped

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-274--replace-every-icon-asset-with-the-revamped-logo-pack-and-render-them-from-vector).

### T-256 — Rule the fifteen options no decision covers

**Status:** **Complete — Approved with follow-ups at `ed7e25a`**, 2026-08-21, on the record-only
pass the maintainer authorized that day. All four rulings are taken: `SEC-004` (2026-08-16) forbade
the fifteen; `SEC-005` and `SEC-003`'s amendment (2026-08-21) closed the rest.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-256--rule-the-fifteen-options-no-decision-covers).

### T-267 — Pin the warning threshold the Windows workflow actually uses

**Status:** **Complete — Approved with follow-ups at `0eece42`**, 2026-08-21. **`T267-R1` is
Resolved**; `T267-R2` (Low, non-blocking) is **done at completion**, which is where it was targeted.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-267--pin-the-warning-threshold-the-windows-workflow-actually-uses).

### T-258 — A spawned worker that dies before it is prepared is orphaned forever on Windows

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t258-scan-observations).

**Status:** **Complete — Approved at `3947858`**, 2026-08-21, on the record-only focused pass the
maintainer authorized on 2026-08-19. **`T258-R10` is Resolved**; `T-268` remains separate and
unaffected, and gates nothing in the centre column.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-258--a-spawned-worker-that-dies-before-it-is-prepared-is-orphaned-forever-on-windows).

### T-270 — Quit has no keyboard shortcut on Windows, and the whole Windows gate is red behind it

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t270-version-runs).

**Status:** **Complete — Approved at `c047767`**, 2026-08-20, **no implementation findings**,
across one initial review and one focused evidence re-review. **`T270-R1` is Resolved by run
`32319665394`**: `windows desktop` green end to end in 34m47s, `test_the_quit_shortcut_is_bound`
PASSED on the platform that produced the empty sequence. The reviewer confirmed the implementation
boundary did not move between the two reviews — `06745fa`'s only difference from `c047767` is
`docs/project/REVIEWS.md`.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-270--quit-has-no-keyboard-shortcut-on-windows-and-the-whole-windows-gate-is-red-behind-it).

### T-269 — Make the formatter and type-checker versions reproducible

**Status:** **Complete — Approved at `166ce39`**, 2026-08-20, **no new findings**. **`T269-R1`,
`T269-R2` and `T266-R2` are all Resolved** — the last of those is the follow-up `T-266` filed that
became this task. Run `32319665394` on
`06745fa`, `windows desktop` green end to end: the `--- gates ---` block reports **`ruff 0.16.3`**
and **`mypy 2.3.1`**, bare on `PATH`, on `STARBASE`. **The mechanism this task reasoned about is
now observed** — the persistent virtualenv's `sha256sum pyproject.toml` cache key re-keyed and the
runner installed the pinned versions rather than keeping older satisfied floors. That was the last
half of `T269-R1`'s correction that had never executed on Windows. Corrected 2026-08-19 for
`T269-R1`; awaiting a focused evidence re-review, not a correction.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-269--make-the-formatter-and-type-checker-versions-reproducible).

### T-265 — Make the CI runner inventory describe every job exactly

**Status:** **Complete — Approved at `d7a2d0f`**, 2026-08-19, **no findings**, on one review
round; `T262-R4` is Resolved. The reviewer confirmed all ten rows against the four workflow files
and ruled that **the missing executable inventory gate stays outside this task** — its affected
surface is the inventory itself, not a new parser coupling policy prose to four workflow schemas,
and a Planner may file that separately. *Where each platform runs* is now *Where each job runs*,
and it lists all ten.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-265--make-the-ci-runner-inventory-describe-every-job-exactly).

### T-263 — Close the residual gaps around the outer-containment spawn seam

**Status:** **Complete — Approved at `3b847d8`**, 2026-08-19, **no findings**, on one review
round. `T258-R7`, `T258-R8` and `T258-R9` are all Resolved, and the reviewer ruled that **no
fresh Windows run is required**: nothing changed here sits inside a platform guard — the AST gate
reads source, both probes force the shared containment seam to refuse before an OS child exists,
and the only production change is exception translation at that boundary. All four scope items are
done, and each is mutation-checked rather than asserted to work.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-263--close-the-residual-gaps-around-the-outer-containment-spawn-seam).

### T-261 — Make task placement reject duplicate task IDs

**Status:** **Complete — Approved at `ca2f278`**, 2026-08-19, **no findings**, on one review
round. `COORD-R23` is Resolved. **Built as a third parse rather than a flag on either existing
one**: `heading_occurrences()` returns every `### T-NNN` heading in file order as a **list** of
`(id, line, section)`, and nothing in it deduplicates. `live_entries()` keeps a `seen` set
and `status_line_counts()` keys a dictionary by task id, so both discard the second copy before
any assertion sees it — a parser asked to both collapse and not collapse is one refactor from
doing neither.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-261--make-task-placement-reject-duplicate-task-ids).

### T-266 — `T-258`'s negative control fails on Windows: the child is reaped with the Job suppressed

**Status:** **Complete — Approved with follow-ups at `0c6a2b8`**, 2026-08-18, on one review
round; the verdict is recorded at `fcf463f`. **All four acceptance criteria are met.** Decided on
run `32172384737`, and candidate 1 holds; the corrected records and control then ran green on
`STARBASE` in run `32200375666` — 3684 passed, 30 skipped, 35 deselected, **no failures**, with
both `test_killing_the_parent_before_the_worker_is_prepared_leaves_nothing` and the renamed
`test_a_child_stopped_in_the_window_dies_with_no_outer_job_to_reap_it` passing. The `windows
desktop` job had been red since 2026-08-15 and is not any more.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-266--t-258s-negative-control-fails-on-windows-the-child-is-reaped-with-the-job-suppressed).

### T-264 — Make the no-untrusted-PR workflow policy executable

**Status:** **Complete — Approved at `609d614`**, 2026-08-18, after two review rounds and a
Blocked pass for the dependency gate. `T264-R1` through `R4` are Resolved. Corrected after
`cc17ff0` returned Changes requested with three blocking findings, **all three of which the first
version got wrong in the accepting direction**. T-262 removes every pull-request trigger; this task makes that control fail closed
when a workflow is edited or added later. `tests/unit/test_workflow_triggers.py` now **parses** each
workflow with PyYAML and reads the trigger set GitHub would resolve. **25 tests**, passing serially
and under `pytest -n auto`.
**Owner:** Implementer
**Priority:** Low while the trigger is absent; the consequence of regression is the Critical
self-hosted-runner exposure T-262 records
**Phase:** CI security maintenance; blocks no current T-262 correction
**Depends on:** T-262's trigger removal at `1387e57`
**Relevant context:** `T262-R3`, `.github/workflows/*.yml`, GitHub's public-fork/self-hosted-runner
warning, `AGENTS.md` §7
**Affected surfaces:** a unit/static workflow-policy test; workflow files only if the gate exposes
another trigger
**Risk:** Low — a repository-local assertion over four workflow files

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-264--make-the-no-untrusted-pr-workflow-policy-executable).

### T-259 — The Windows job's timeout had four minutes of headroom, and the suite grew into it

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t259-runtime).

**Status:** **Complete — Approved with follow-ups at `322a533`**, 2026-08-17, after two review
rounds. `T259-R1` is Resolved; `T259-R2` is non-blocking and owned by `T-267`. Corrected after
`T259-R1` returned Changes requested for the two acceptance criteria the raise did not cover. The bound went 30 → 40 on 2026-08-16 and the run
at `31985410889` confirmed the sizing; **the half that makes the next creep visible is now built**:
`tools/job_duration_report.py` prints elapsed, the bound, the remaining margin and the percentage
used, and emits a `::warning::` at 85% — 34 minutes of 40, two minutes clear of the healthy
32-minute measurement and six minutes of notice before the bound. The `windows desktop` job calls
it under `if: always()`, so the run most worth measuring is not the one that skips the report.
**Verified on Windows rather than inferred**, which is what `T259-R1` asked for: run
`32091868834` at head `848ce34` printed `Elapsed: 32.3 min / Bound: 40 min / Remaining: 7.7 min /
Used: 81%` and stayed quiet, 81% being under the 85% mark. That run's only failure is `T-258`'s
negative control (`T-266`) and belongs to neither this task nor its step.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-259--the-windows-jobs-timeout-had-four-minutes-of-headroom-and-the-suite-grew-into-it).

### T-257 — The Windows job has been red since 2026-08-15, and the failure is the guard, not the product

**Status:** **Complete — Approved at `ffa29c1`** on 2026-08-17, **no findings**, in the
T-257/T-259 Windows-chain review (`476b745`). Fixed 2026-08-16 and green on Windows 2026-08-17 in
run `31985410889` at head `7e376e7`, where the named test passed inside a suite of 3597 passed, 30
skipped, 35 deselected. The reviewer also mutation-checked both local branches — an emptied Linux
sweep produced the intended "inspected nothing" failure, and forcing `sys.platform = "win32"` on
the same data produced the Windows branch rejecting the seven Unix fall-through matches — so both
probes passed by seeing a failure. Found by the Phase 4 records sweep, not by anybody reading CI.
**All acceptance criteria met.**
**Owner:** Implementer
**Priority:** **High.** It is the gate that evidences Phase 4 exit criterion 2's *"automated on
**both** platforms"*, and while it is red that criterion has one platform
**Phase:** Phase 4
**Depends on:** nothing
**Relevant context:** `T200-R7` (whose rule this is), `tests/ui/test_accessibility.py`,
`tests/ui/test_windows_accessibility.py`, CI run `31906562503`, `IMPLEMENTATION_PLAN.md` §Phase 4
exit criterion 2 as amended 2026-08-15
**Affected surfaces:** `tests/ui/test_accessibility.py`. **No source — the product is not at
fault**
**Risk:** Low to fix. The risk it exposed is that **a red Windows job went unread for a day**

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-257--the-windows-job-has-been-red-since-2026-08-15-and-the-failure-is-the-guard-not-the-product).

### T-262 — Every CI job runs on the maintainer's own machines, and fork pull requests could too

**Status:** **Complete — Approved with follow-ups at `8ee106b`**, 2026-08-17, after **three
review rounds**: the ordinary review, one ordinary correction re-review, and one
maintainer-authorized focused pass under `AGENTS.md` §10. `T262-R1` and `T262-R2` are **Resolved**;
`T262-R3` is owned by `T-264` and `T262-R4` by `T-265`. Built on the maintainer's direct instruction
while preparing to make the repository public.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-262--every-ci-job-runs-on-the-maintainers-own-machines-and-fork-pull-requests-could-too).

### T-260 — Five symlink tests bypass the guard `T-070` built, and fail bare on Windows

**Status:** **Complete — Approved with follow-ups at `a2389e7`**, 2026-08-17, after **six review
rounds**: one ordinary review, one ordinary re-review, and **four maintainer-authorized passes**
under `AGENTS.md` §10 — three corrections and one design replacement. `T260-R1` through `T260-R4`
are Resolved; the only follow-up, `T260-R4`'s stale counts, is closed here and **pinned by a test**
so it cannot drift again.

**Accepted as out of scope, on the reviewer's ruling:** `__new__` forgery, `ln -s` via a subprocess,
and **assignment aliasing** (`mk = os.symlink`) — following bindings is dataflow analysis, which is
the road four rounds established this gate should not walk.

*(Previous status, and the round it describes.)* Redesigned 2026-08-17 under a maintainer-authorized fifth pass. After
four review rounds, raw symlink creation is now **banned outright** everywhere in `tests/` except
`tests/capabilities.py`; the `symlinks` fixture returns a **`SymlinkCapability`** object and all
nine sites create through its `.create()`. The gate that enforces this needs no pytest semantics at
all, which is the point.

> **Why the design was replaced rather than patched a fifth time.** Rounds one through four were
> one defect wearing four coats: the gate statically approximated pytest's collection and
> fixture-resolution semantics, and every approximation had a hole the reviewer found — test bodies
> only, then a parameter merely *named* `symlinks` (`plant(tmp_path, None)`), then uncollected
> modules and home-grown `fixture` decorators, then **nested `test_` functions pytest never
> collects and `@hookimpl` counting because it came from pytest**. Both round-four survivors were
> reproduced here before anything was decided. `AGENTS.md` §10 names this moment — corrections
> repeatedly reproducing the same defect class — and its answer, *revisit the design*, is what the
> maintainer chose on 2026-08-17, the reviewer having proposed no further automatic round. The
> capability-token design is the alternative the reviewer named in the second-round ruling.
>
> **A sixth pass was authorized the same day**, for the fifth review's finding: ordinary import
> aliases bypassed both flat rules — `from os import symlink as make_link` renamed the local
> binding a call-site ban keyed on, and `SymlinkCapability as Cap` did the same to the constructor
> — and the exemption compared **basenames**, silently exempting every nested file named
> `capabilities.py`. All three were reproduced before fixing. Now the *import itself* of a raw
> name is banned under any alias (no test file has a sanctioned reason to hold one), an aliased
> import of the capability class is banned outright (annotations need no rename), and the
> exemption is the exact path `tests/capabilities.py`. The floor also pins the exempt file to
> **exactly two** raw sites — the probe and `SymlinkCapability.create` — so a third site cannot
> ride the exemption.
>
> **A claim from the second pass is withdrawn, not reinterpreted:** *"a helper that takes the
> fixture as a parameter can only be called by something that has it."* False — `symlinks` returned
> `None`, so any caller could fake it. Under the token design that forgery fails loudly on every
> platform (`AttributeError`), which is now a tested property rather than an argument.

Filed 2026-08-16 from a real Windows failure, run `31966531162`
**Owner:** Implementer
**Priority:** Medium. It costs a red Windows job and five unreadable errors whenever the privilege
is absent, which is the ordinary state of a Windows machine
**Phase:** Phase 4 maintenance. Gates nothing in the centre column
**Depends on:** nothing
**Relevant context:** `T-070` (Complete, approved 2026-07-28 — it built the guard),
`tests/capabilities.py` (`can_create_symlinks`, the `symlinks` fixture), `tests/conftest.py`,
`tests/integration/test_worker.py`, `tests/unit/test_paths.py`, `docs/project/TESTING.md` §12
**Affected surfaces:** `tests/integration/test_worker.py`, and wherever the enforcing check lands.
**No source**
**Risk:** Low. The risk of the obvious fix is the opposite one — adding the fixture to five tests
and calling it done, which is what leaves the sixth to be written next month

#### What happened

`SeCreateSymbolicLinkPrivilege` was absent on `STARBASE` and **five tests failed with a bare
`OSError: [WinError 1314] A required privilege is not held by the client`** instead of skipping
with the message that names the privilege.

**`T-070`'s guard is not broken — it is simply not requested.** Of the nine tests that create a
symlink, four take the `symlinks` fixture and **skipped correctly on the same run**; five do not
and failed. Derived rather than eyeballed:

| File | Guarded | Unguarded |
|---|---|---|
| `tests/unit/test_paths.py` | 3 | 0 |
| `tests/integration/test_worker.py` | 1 | **5** |

The five: `test_a_sidecar_that_is_a_symlink_out_of_staging_is_refused`,
`test_a_symlink_at_the_staging_name_fails_the_session_before_anything_is_written`,
`test_a_symlinked_staging_name_reports_no_partial_to_resume_from`,
`test_a_symlink_pointing_somewhere_else_inside_the_download_folder_is_refused`,
`test_a_symlink_planted_during_the_mkdir_is_still_caught`.

**This is `T-070`'s own defect, re-instanced by tests written after it.** That task fixed four named
tests and added a fixture; nothing makes a *later* symlink test use it. Fixing these five and
stopping would be the same trade again — the list is not the property.

*(The privilege went missing because the runner was restarted from a non-elevated session while
`STARBASE` was being recovered on 2026-08-16. That is the trigger and **not** the defect: a Windows
machine without Developer Mode or elevation is the ordinary case, and `T-070` exists because the
suite must say so rather than erroring.)*

#### Acceptance criteria

- **A check enforces the property, not the list**: a test that creates a symlink and does not
  request the capability **fails a gate**, wherever it is written. A nine-line `ast` walk over
  `tests/` finds all nine of today's cases, so the mechanism is not the hard part
- **It is proved by adding an unguarded symlink test and watching the gate fail**, then removing it
  — the mutation, not the assertion
- **The five gain the guard**, and on a machine without the privilege they **skip with
  `NO_SYMLINKS`** rather than raising
- **Coverage is not quietly reduced.** These five assert containment — `T-034`'s boundary — so a
  skip on Windows is a real gap and must be visible as a skip count, never as a pass
- The gate sits with the project's other static checks over its own tree (`test_layering.py`,
  `test_task_placement.py`) rather than becoming a runtime `except OSError`, which would convert
  every future privilege failure into a silent pass

#### How each criterion was met — 2026-08-17, after the redesign

*(Three earlier versions of this table described the approximation-based gates the review rounds
rejected; per `T260-R2` they are replaced rather than accumulated. The review history is in
`docs/project/REVIEWS.md`, five records from 75ed6bf's base onward.)*

| # | Criterion | Evidence |
|---|---|---|
| 1 | A check enforces the property, not the list | Two flat rules over **every** `*.py` under `tests/`: **no raw `symlink_to`/`symlink` call outside `tests/capabilities.py`**, in any context whatsoever; and **`SymlinkCapability` constructed nowhere else**. No collection semantics, no fixture semantics, no ancestry analysis — nothing left to approximate |
| 2 | Proved by adding unguarded sites and watching the gate fail | **Both round-four survivors reproduced as real files and flagged by name** — the nested `test_` function and the `@hookimpl` fixture — plus a forged `SymlinkCapability()` construction. **Eighteen** parametrized raw spellings must be flagged, one per defeated context — including a genuine `@pytest.fixture` creating raw, and the fifth review's aliased raw import both called and uncalled; four sanctioned shapes must not be |
| 3 | The tests skip rather than raise where the machine cannot | Forced `can_create_symlinks` to `False`: **9 skipped, 0 failed** across both files, each skip naming the privilege and the Developer Mode setting. A sanctioned-route probe also ran end to end on a capable machine: fixture → capability → `.create()` → a real link |
| 4 | Coverage is not quietly reduced | The floor now counts `symlinks.create(...)` sites (≥ 9) and requires the probe file to still contain raw creation, so a rename of `Path.symlink_to` breaks the ban and the probe together rather than silently unlinking them |
| 5 | Static, not a runtime `except OSError` | Unchanged in intent, smaller in practice: the static check is ~90 lines with no pytest model. **The propagation question became a runtime property instead** — `plant(path, None)` now fails loudly on every platform, asserted by `test_forging_the_capability_with_none_fails_loudly_on_every_platform` |

**The enforced boundary, stated honestly** (the fourth review's ruling): this prevents accidents —
the two raw Python spellings and the constructor call. It does not defend against `__new__` forgery
or shelling out to `ln -s`; no test does either, and one that started to would be visible in review.

#### Out of scope

- Restoring the privilege on `STARBASE`. That is machine configuration, done separately — and if it
  is restored first, **this defect stops being visible while still being present**, which is the
  reason it is filed with its evidence rather than left to the next red run

---


### T-183 — The option audit: classify every group, and decompose the phase

**Status:** **Complete — Approved with follow-ups at `1d0caf6`**, 2026-08-17, after **three
review rounds**. All five findings Resolved; the three exact mutations the reviewer built now fail
at the intended assertions. Three Low follow-ups are assigned away rather than left here:
**`T183-F1`** and **`T183-F2`** to `T-256`, **`T183-F3`** to `T-252`.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-183--the-option-audit-classify-every-group-and-decompose-the-phase).

### T-240 — Nothing enforces the commit-message rules, and one of them has now been broken twice

**Status:** **Complete — Approved at `c559b93` on 2026-08-15**, no findings, after **six
review rounds** under the maintainer's standing grant (*"a pass until this is completed"*,
Phase 3's pass-4 precedent). `T240-R1` is Resolved in its **fifth** instance — the branch matrix
preserves incomplete evidence, and capped excluded payloads fail without re-reading the excluded
tip — and `T240-R2` in its **second**: pushes group by `github.run_id`, which GitHub guarantees
unique per workflow run, so pending-run replacement can no longer discard another push's evidence.
The reviewer verified independently — 52 focused tests, the placement gate, Ruff and format, host
and Win32 `mypy`, direct `mypy` over the tool, the commit gate and `git diff --check`, on a clean
worktree — and confirmed the `mapped()` narrowing changes no payload semantics. **The first real
runner execution remains operational confirmation, not a blocker**, the ruling standing since the
fourth round; the pending push is where it happens.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-240--nothing-enforces-the-commit-message-rules-and-one-of-them-has-now-been-broken-twice).

### T-246 — `Start` and `Clear finished` are on no menu, so nothing announces them

**Status:** **Complete — Approved at `217792a` on 2026-08-15**, no findings. The reviewer
independently confirmed the same `QAction` instances on both surfaces, the insertion point, the
shared action state, the toolbar order and the no-control-bar behaviour; measured **`TabFocus` on a
synthetic toolbar button against `NoFocus` on all four composed ones**, which validates the `T-202`
record correction this commit carried; and reproduced both mutations. **93 focused tests**, with
Ruff, formatting, host and Win32 `mypy`, the diff and the commit gate clean.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-246--start-and-clear-finished-are-on-no-menu-so-nothing-announces-them).

### T-200 — The accessibility pass: keyboard, focus order, and names a screen reader can use

**Status:** **Complete — Approved at `274ed9e` on 2026-08-15**, no findings, after four
correction rounds. The verdict covers the implementation through `d2828d1` **plus the
content-preserving inventory move in `a087753`**, which the reviewer verified as **AST-identical**
across all six moved definitions — the move happened under `T-202` after this task's last commit,
and was disclosed rather than left to be found. `T200-R1`–`R7` are all Resolved; `T-245`, filed
from the surviving mutation, is **withdrawn** — it was a failed acceptance criterion, not a
follow-up.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-200--the-accessibility-pass-keyboard-focus-order-and-names-a-screen-reader-can-use).

### T-243 — An interrupted row says the same thing twice, in two voices

**Status:** **Complete — Approved at `083e5e3` on 2026-08-15**, no findings, and **verified
unchanged through `274ed9e`**. The first review confirmed fork 1 as the right presentation boundary
and returned **Changes requested** with `T243-R1` (Medium): making the message optional widened the
failure API past the one class this task owns. That finding is Resolved. Not a plan deliverable —
it carries no exit criterion.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-243--an-interrupted-row-says-the-same-thing-twice-in-two-voices).

### T-202 — Nothing is said by colour alone

**Status:** **Complete — Approved at `a8775bf` on 2026-08-15**, no findings, after four rounds.
`T202-R1` (High) was returned three times: *focus* conveyed by colour alone and exempted by name;
then fixed for the three controls the finding named and left everywhere else; then an inventory
parsed out of the style sheet, blind to a `QListView` that Qt frames and `theme.py` never mentions.
The fourth pass raised **`T202-R2`** (Medium) against the tests themselves, and the maintainer
authorized a focused pass for it. Both findings are closed.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-202--nothing-is-said-by-colour-alone).

### T-021 — Simplified small-size icon glyph

**Status:** **Complete — Approved on 2026-08-15**, no findings. The reviewer independently
regenerated the small master, the eight PNGs and the seven-frame `.ico` and got byte-identical
output, measured the 16 px render at **66 opaque pixels, 20 gold** against the floor of 16, and
**made the side-by-side judgement the first criterion asks for**: at both sizes and on both grounds
the reduced glyph removes the landscape mass that competed with the note, the stem and head read
more clearly, the gold sweep stays visible, and it is recognizably the same mark. The 32 px control
is identical between rows, so the small-master split has not leaked upward.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-021--simplified-small-size-icon-glyph).

### T-245 — Qt publishes a combo box's value where its name should be

**Status:** **Cancelled — 2026-08-15, superseded by `T200-R7`.** Filed the same day from `T-200`'s
mutation battery, on the reading that the survivor was a pre-existing gate weakness needing a fork
this task did not own. **The reviewer overturned that reading**, and was right to: it is a failed
acceptance criterion of `T-200`, not a follow-up, so it was corrected inside `T-200` rather than
carried.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-245--qt-publishes-a-combo-boxs-value-where-its-name-should-be).

### T-244 — Expanded playlist entries offer verbs the delegate never draws

**Status:** **Complete — Approved at `510923d` on 2026-08-14.** Filed by the `T-201`
second-correction re-review; the defect reproduces at the review base and is not caused by
`T201-R3`, so it was carried rather than reopening that task. Round one returned **Changes
requested** with `T244-R1` (the phantom bar reserve, which I had wrongly measured as unobservable)
and `T244-R2` (a stale `docs/project/STATUS.md` claim). Both are **Resolved** — `T244-R2` outlived its first
correction and took a **third, documentation-only pass** the maintainer authorized, `AGENTS.md`
§10's ordinary budget having been exhausted with it still open. **Seven mutations, none surviving** —
and three of the seven survived a first version of the tests, including the one `T244-R1` had to
find for me.
**Owner:** Implementer
**Priority:** Medium — an expanded entry loses its own Retry and Remove controls, but the playlist
header still offers Retry failed and group removal as workarounds
**Phase:** Phase 4 (polish; **not** a plan deliverable)
**Depends on:** nothing
**Relevant context:** `UX-005` rows 4 and 9, `T-140`, `ui/row_delegate.py` `_verb_rects`,
`ui/queue_view.py` `VERBS_ROLE`
**Affected surfaces:** `ui/row_delegate.py`, `tests/ui/test_row_delegate.py`, composed queue tests
**Risk:** Medium — the parent and child row anatomies use different line counts, and fixing one
without driving paint and hit-testing together can restore a control at the wrong coordinates

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-244--expanded-playlist-entries-offer-verbs-the-delegate-never-draws).

### T-201 — The error-surface pass: twelve classes, and the two with nothing to suggest

**Status:** **Complete — Approved at `da9e0a7` on 2026-08-14**, after a second correction. Round
one returned **Changes requested** with `T201-R1` (Medium), `T201-R2` (Medium) and `T201-R3`
(**High**). The first focused re-review resolved `R1` and **reopened `R2`**: the corrected wording
was not reachable through the widget's live event path. `R3` stayed open pending a ruling only the
maintainer could take. **The maintainer ratified option C on 2026-08-14** — recorded as an
amendment to `UX-005`, which is where a row-anatomy ruling lives. The second focused re-review
**resolved both**, with **nine mutations** across them; `T201-R4` was found beside them and is
**pre-existing and non-blocking**, filed as `T-244`.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-201--the-error-surface-pass-twelve-classes-and-the-two-with-nothing-to-suggest).

### T-242 — The Settings screen is taller than the screen, and clips its own explanations

**Status:** **Complete — Approved at `68cd1c6` on 2026-08-14.** Round one returned **Changes
requested** with `T242-R1` and `T242-R2`, **both Resolved**. The sizing now reads the display the dialog is *on*
rather than the primary one — the reviewer found the code contradicting its own call-site comment,
and the multi-monitor case it misses is exactly the 1366 × 768 working area this task's criterion
names. The screenshots are attached rather than claimed. **Ten mutations across both rounds, none
surviving**; the two new ones are the display choice and its fallback.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-242--the-settings-screen-is-taller-than-the-screen-and-clips-its-own-explanations).

### T-227 — Nothing gates the documents that say what is built

**Status:** **Complete — Approved at `cd52ed5` on 2026-08-14.** Round one returned **Changes
requested** with one finding, `T227-R1`, **Resolved**: the `UX_SPEC` count marker sat at the start of a line it
shared with prose, which begins a **CommonMark raw-HTML block** — so the paragraph above it ended
early and the rest of that line rendered its backticks and asterisks literally. **A marker that
damages the sentence it exists to protect is worse than no marker**, and the regex gates could not
see it because they read the file as text and never asked where the comment sat. It is inline now,
and a **structural guard** rejects any marker that begins a line it shares with prose — a rule
rather than a rendered check, so the gate stays free of a Markdown runtime.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-227--nothing-gates-the-documents-that-say-what-is-built).

### T-241 — A row that has moved no bytes still states a byte count

**Status:** **Complete — Approved at `d7c9b7b` on 2026-08-14**, built in the same authorized
overnight run as `T-242` and `T-227`. The sub-question the criteria required answering is answered below — **in this entry,
which is where `T241-R1` found it was not**: the section had been written into `T-201`'s entry,
attributing this task's behaviour to the task that deliberately stopped short of it. The rule also
turned out to have a second half that a *passing* test found. Six mutations, none surviving.
**Owner:** Implementer
**Priority:** Low — one line of furniture on a row the user themselves stopped. Nothing is
misreported about a download that ran; the lie is about one that did not
**Phase:** Phase 4 (polish; **not** a plan deliverable)
**Depends on:** nothing. `T-201` built the branch this would sit beside
**Relevant context:** `ui/queue_view.py` `_detail` and `_failure_detail`, `T-201`'s criterion 4,
`T-216` (the same trade for a finished row), `ARCHITECTURE.md` §7 (cancelling is not failing)
**Affected surfaces:** `ui/queue_view.py`, `tests/ui/test_queue_view.py`
**Risk:** Low

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-241--a-row-that-has-moved-no-bytes-still-states-a-byte-count).

### T-196 — Network options: rate limit, proxy, and a retry policy that does not exist yet

**Status:** **Complete — Approved at `c70f61a` on 2026-08-13.** All five findings are **Resolved**:
`T196-R1` through `T196-R4` in the correction at `c09badd`, each independently mutation-verified by
the Reviewer, and **`T196-R5` in a documentation-only correction the maintainer authorised** as the
extra focused pass `AGENTS.md` §10 requires. No follow-up is required by the review.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-196--network-options-rate-limit-proxy-and-a-retry-policy-that-does-not-exist-yet).

### T-198 — Report the yt-dlp version, update it in place, and be able to go back

**Status:** **Complete — approved at `7b20c60`, 2026-08-13.** All six acceptance criteria are met
and **`T198-R1` through `T198-R6` are all Resolved**, over four review passes. The approval rests
on CI run `31726615968`, green on all five jobs, in which **both frozen artifacts** printed
`2026.07.04` baseline → `9000.1.1` resolved from a user-managed copy in a spawned child →
`2026.07.04` baseline after revert. No follow-up is required by the review.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-198--report-the-yt-dlp-version-update-it-in-place-and-be-able-to-go-back).

### T-208 — Reproduce the multi-row missing-disclosure report

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t203-checks).

**Status:** **Complete — closed by maintainer ruling 2026-08-13 on the bounded, verified
correction.** `T208-R1` had narrowed to one choice, and the maintainer took *close* rather than
*probe further*: the original gesture is unrecoverable, so further probing has **no oracle to match
against** — it could only produce a different reproduction and call it the same report. The reviewer
independently removed the re-anchor and reproduced the collapse control at y=−63, so what the fix
addresses is established; what cannot be established is that it was the same thing the user saw, and
no amount of probing changes that.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-208--reproduce-the-multi-row-missing-disclosure-report).

### T-221 — Decide whether the deferred panel mount visibly flashes

**Status:** **Complete — observed 2026-08-13. No visible flash.** The maintainer ran both panel
openings on a real display and **did not see the one-turn mount transient**, which is what this
entry existed to find out. `T209-R1` is closed by the observation.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-221--decide-whether-the-deferred-panel-mount-visibly-flashes).

### T-219 — The dialog footer speaks the naming rule, not the selector

**Status:** **Cancelled — ruled 2026-08-13. The refusal is the outcome.** The maintainer chose
*refuse and close* from the three shapes this entry recorded.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-219--the-dialog-footer-speaks-the-naming-rule-not-the-selector).

### T-228 — A retry deadline stops firing under parallel load

**Status:** **Cancelled — ruled a harness artefact 2026-08-13.** The maintainer closed it on the
reachability measurement: **680 sessions** — concurrency 1 and 16, idle and saturated, plus 20
independent managers — lost **no message**, so it is not reachable at supported product concurrency
by anything measured. It needs the integration suite itself, at high worker count, on a saturated
host.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-228--a-retry-deadline-stops-firing-under-parallel-load).

### T-230 — A spawned child still gets the developer's real directories

**Status:** **Complete — Approved 2026-08-12.** Spawned children inherit the per-test config, data,
and cache roots; the full integration measurement leaves zero files in the sentinel roots.
**Owner:** Implementer
**Priority:** Medium — it is the remaining half of a rule `docs/project/TESTING.md` §5 states without
qualification, and the half that is left is the one no in-process fixture can reach
**Phase:** Phase 4 — maintenance. **Not a plan deliverable.**
**Depends on:** nothing. `T123-R2`'s fixture is the in-process half and is built
**Relevant context:** `tests/user_directories.py`, `tests/conftest.py`, `docs/project/TESTING.md` §5,
`tests/ui/test_app_launch.py` (the one place that already does this correctly), `T123-R2`
**Affected surfaces:** `tests/integration/**`, possibly a shared spawn helper
**Risk:** Low — the tests pass today; what is wrong is where their children write

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-230--a-spawned-child-still-gets-the-developers-real-directories).

### T-220 — The toolbar and the run control: build and spec disagree

**Status:** **Complete — Approved 2026-08-12.** The requested reading confirms that build and
`docs/UX_SPEC.md` §2.1 agree; neither side needs amendment.
**Both halves were ruled 2026-08-12.** The maintainer chose option A, the grouped bar, from
rendered mockups after `UX-013` removed the concurrency control — *"lets go with option A given
those mockups"* — and chose `Start` / `Stop` for the label.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-220--the-toolbar-and-the-run-control-build-and-spec-disagree).

### T-229 — Prove theme isolation beyond the original T-225 leak

**Status:** **Complete — Approved 2026-08-12.** Both previously unproved restoration fields now
have an ordered between-test regression, and both named behaviors run under the shipped theme.
**Owner:** Implementer
**Priority:** Low — the original order defect is fixed and mutation-proved; this is evidence for
the two restored theme fields that did not cause today's failures, plus product-state coverage for
two assertions that currently run only on a bare application
**Phase:** Phase 4 — test hardening. **Not a plan deliverable.**
**Depends on:** `T-225`
**Relevant context:** `tests/ui/conftest.py::_undressed_afterwards`,
`tests/ui/test_add_dialog.py::test_an_open_playlist_shows_entries_and_a_way_back`,
`tests/ui/test_add_dialog.py::test_the_menu_key_reaches_the_current_rows_menu`,
`ui/row_delegate.py`'s use of `theme.applied()`
**Affected surfaces:** `tests/ui/`
**Risk:** Low — the fixture restores the complete known state correctly; the gap is that only its
style-sheet half and the undressed widget state are asserted today

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-229--prove-theme-isolation-beyond-the-original-t-225-leak).

### T-239 — A thumbnail-sweep regression fails on the runner and nowhere else

**Status:** **Complete — Approved 2026-08-12.** The test now waits for the publication counter the
product gate reads; the original `T179-R1` regression remains live. `T239-R1` is a Low,
non-blocking STATUS wording correction.
**Owner:** Implementer
**Priority:** Medium — it reddened the `linux` job, which is a gate; but the test guards a real
`T179-R1` race and a wrong "fix" here would retire that guard rather than the flake
**Phase:** Phase 4 — maintenance. **Not a plan deliverable.**
**Depends on:** nothing
**Relevant context:** `T-179`, `T179-R1`, `T-238` (a different intermittent native crash, not a
runner-red/local-green event), `T-228`, `T118-R10` (timed gates with no headroom),
`tests/ui/test_queue_view.py::test_a_picture_written_after_its_removal_sweep_is_still_collected`
**Affected surfaces:** `tests/ui/test_queue_view.py`. The product sweep gate was investigated and
left unchanged because it behaves as designed
**Risk:** Medium — the assertion is `T179-R1`'s own regression, and `T-179`'s carried criterion is
that a disk entry is removed when no job names it

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-239--a-thumbnail-sweep-regression-fails-on-the-runner-and-nowhere-else).

### T-234 — The concurrency control leaves the toolbar

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t234-local-checks).

**Status:** **Complete — Approved 2026-08-12 after two focused correction passes.** `T234-R1`,
`T234-R2`, and `T234-R3` are Resolved. T-235's literal exact-set assertions now gate the remaining
Windows-accessibility criterion, and run `31642823390` is green on all five jobs.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-234--the-concurrency-control-leaves-the-toolbar).

### T-237 — The spec recopies `REL-002` and then blurs its two collection results

**Status:** **Complete — Approved 2026-08-12.** `T237-R1` is Resolved: the comment now separates
what each mutant did to the artifact from whether the current gate detected it, with no executable
spec change.
**Owner:** Implementer
**Priority:** Low — comments only; the build operations and gates are correct
**Phase:** Phase 4 — maintenance. **Not a plan deliverable.**
**Depends on:** nothing
**Relevant context:** `T-233`, `T233-R1`, `REL-002`, `packaging/tracks-and-trails.spec`
**Affected surfaces:** comments only in `packaging/tracks-and-trails.spec`
**Risk:** Low

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-237--the-spec-recopies-rel-002-and-then-blurs-its-two-collection-results).

### T-235 — The Windows accessibility sweep has never seen the toolbar

**Status:** **Complete — Approved 2026-08-12.** `T235-R1` is Resolved: the expected names are
literal exact sets, the tree is refreshed for the running state, and run `31642823390` passed the
dedicated Windows accessibility slice.
**Owner:** Implementer
**Priority:** Medium — `NFR-005` is a requirement, and the surface this misses is the three
controls a user reaches for first. Not High only because no defect is known: the buttons may well
announce correctly, and nobody has looked
**Phase:** Phase 4 — maintenance. **Not a plan deliverable.**
**Depends on:** nothing. `T-234` settled what is on the toolbar
**Relevant context:** `tests/ui/test_windows_accessibility.py`, `NFR-005`, `T-026`/`T026-R2` (why
the menus are queried through their own handles), `T-234`'s criteria, `OPS-012` (`WINDOWS_RUNNER`)
**Affected surfaces:** `tests/ui/test_windows_accessibility.py`
**Risk:** Low to change, **unknown to run** — this is the point of the task

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-235--the-windows-accessibility-sweep-has-never-seen-the-toolbar).

### T-236 — The limit's only control has the affordance `T-141` ruled unreadable

**Status:** **Complete — Approved 2026-08-12.** `T234-R2` is Resolved. The accepted labelled
stepper is restored on the Settings screen, including readable styling, range gates, accessible
names, one keyboard stop, and no native arrows.
**Owner:** Implementer
**Priority:** Medium — `NFR-005`, and it is now the *only* control for the setting. Not High
because the control is still operable by typing and by `Up`/`Down`; what is unreadable is the
affordance that says it can be stepped
**Phase:** Phase 4 — polish. **Not a plan deliverable.**
**Depends on:** nothing. `T-234` has landed
**Relevant context:** `T-141` (the finding and its measurements), `T-133` (the same control,
twice), `UX-005` row 11, `UX-013`, `T-234`, `ui/settings_dialog.py`, `ui/theme.py`'s deliberate
omission of `QSpinBox`
**Affected surfaces:** `ui/settings_dialog.py`, possibly `ui/theme.py`
**Risk:** Low — an additive control on one screen

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-236--the-limits-only-control-has-the-affordance-t-141-ruled-unreadable).

### T-233 — T-033's packaging comments still give the pre-REL-002 reason

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t234-local-checks).

**Status:** **Complete — Approved with follow-up `T-237`, 2026-08-12.** `T033-R7` is Resolved:
the two submitted explanations are current and no executable statement changed. `T233-R1` is Low
and does not reopen the correction.
**Owner:** Implementer
**Priority:** Low
**Phase:** Phase 5 residue; gates no phase or task
**Depends on:** nothing
**Relevant context:** `T-033`, `T033-R7`, `REL-002`, `packaging/tracks-and-trails.spec`,
`tests/integration/test_freeze_probe.py`
**Affected surfaces:** comments/docstrings only in the spec and frozen-probe integration test
**Risk:** Low — collection and its executable gates are correct; the explanation gives a reason
the mutation disproved

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-233--t-033s-packaging-comments-still-give-the-pre-rel-002-reason).

### T-033 — Bundle the pinned yt-dlp baseline into the frozen artifact

**Status:** **Complete — Approved with follow-up `T-233`, 2026-08-12.** `T033-R5` remains
Resolved and the second maintainer-authorized records pass resolves `T033-R6`. All six acceptance
criteria are met. `T033-R7` is Low, comment-only cleanup outside the submitted records surfaces.
**No source, test, workflow or dependency change is part of either pass.**

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-033--bundle-the-pinned-yt-dlp-baseline-into-the-frozen-artifact).

### T-232 — T-066's process-tree test still says CI skips the virtualenv

**Status:** **Complete — Approved 2026-08-12.** `T066-R3` is Resolved; the correction is comment
only and preserves the install-shape-independent assertion.
**Owner:** Implementer
**Priority:** Low
**Phase:** Phase 1 residue; gates no phase or task
**Depends on:** nothing
**Relevant context:** `T-066`, `T066-R3`, `.github/workflows/ci.yml`,
`tests/integration/test_manager.py::test_the_detector_sees_a_grandchild_and_not_just_a_worker`
**Affected surfaces:** `tests/integration/test_manager.py` comment only
**Risk:** Low — the assertion is correct; the explanation names CI's retired install shape

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-232--t-066s-process-tree-test-still-says-ci-skips-the-virtualenv).

### T-066 — CI installs the project differently from how the documentation says to

**Status:** **Complete — Approved with follow-up `T-232`, 2026-08-12.** All four
acceptance criteria are met at the evidence level accepted by `OPS-005`; `T066-R1` is Resolved
through `T-072`, and `T066-R2` is Resolved. `T066-R3` is a non-blocking stale test comment.
Its stated blocker was that
"both `frozen` jobs are hosted and have not started since the quota ran out". Neither half holds:
`frozen windows` is pinned to `STARBASE` (`OPS-010`) and `frozen linux` follows `LINUX_RUNNER`,
which is set (`OPS-012`), so **neither is hosted** — and both run on every ordinary push, 31 s and
5m26s in run `31607180926`. *(This said `frozen ubuntu-latest` runs "on a hosted runner", which
`OPS-012` retired on 2026-08-05; the runs it cited, `30861672178` and `30865054119`, are from
before that ruling and are kept as the evidence of the day they were taken.)*
*(This read "Blocked — on frozen-artifact evidence only, and no longer a Phase 1 exit dependency"
(`OPS-005` as amended 2026-07-29) until that re-triage.)* **The process-tree half is discharged:** `T-072`
added a *Process trees under the venv* step to the self-hosted `windows desktop` job, and run
`30414186949` executed the `T-019` cases under the venv shape for the first time anywhere — 72
passed, 3 skipped, the grandchild case among the passes. `T066-R1`'s survivor assertions ran there
too.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-066--ci-installs-the-project-differently-from-how-the-documentation-says-to).

### T-223 — The row's menu: drop the editor alias, name the removal

**Status:** **Complete — Approved 2026-08-12 after the `T223-R1` focused re-review.** Built the
same day in an authorized unattended run; filed 2026-08-10 from `UX-012`, the maintainer's ruling
on three live-use reports.
**Owner:** Implementer
**Priority:** Medium — the alias actively confuses on a playlist row, and Remove's label
understates what it removes
**Phase:** Phase 4 — polish, not a plan deliverable
**Depends on:** `T-203` (Complete — the menu this edits is its build). **Same-file coordination:**
`T-213`/`T-218`/`T-219` also touch `add_dialog.py`; serial order among the four is the
implementer's to pick, one task per commit as always.
**Relevant context:** `UX-012` (the ruling, with the maintainer's words), `UX-011` (the shape this
does not change), `docs/UX_SPEC.md` §3's `UX-012` clause, `T118-R9` (why the alias existed),
`ui/add_dialog.py` `row_menu`/`edit_row`, `tests/ui/test_add_dialog.py` (the menu-content and
two-door tests, and `choose_in_editor`'s sentinel reroute — which drives `Choose specific
formats…`, a different entry that stays)
**Affected surfaces:** `ui/add_dialog.py`, `tests/ui/test_add_dialog.py`
**Risk:** Low

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-223--the-rows-menu-drop-the-editor-alias-name-the-removal).

### T-226 — Preset Manager keeps the startup ffmpeg warning after a live change

**Status:** **Complete — Approved 2026-08-12.** Built in an authorized unattended run; filed 2026-08-11
from the focused `T195-R5` sibling audit; verified in the
same composition closure, outside that finding's Settings/Add catalogue boundary.
**Owner:** Implementer
**Priority:** Medium — the trigger is narrow and restart is a workaround, but the screen states a
capability answer that is no longer true
**Phase:** Phase 4 — maintenance. **Not a plan deliverable.**
**Depends on:** `T-199`
**Relevant context:** `REQ-024`, `app.py` (`manage_presets`, `choose_ffmpeg_location`),
`ui/preset_manager.py` (`NO_FFMPEG_REASON`), `T195-R5`
**Affected surfaces:** `app.py`, composition tests
**Risk:** Low — one live value passed to one modal screen

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-226--preset-manager-keeps-the-startup-ffmpeg-warning-after-a-live-change).

### T-218 — The add dialog's empty state: one instruction, inside the list

**Status:** **Complete — Approved 2026-08-12 with follow-up `T-231`.** Built in an authorized unattended run; filed 2026-08-09 from
the maintainer-approved UI review.
**Owner:** Implementer
**Priority:** Low
**Phase:** Phase 4 — polish, not a plan deliverable
**Depends on:** nothing now — the add-dialog chain is approved and `T-213` has landed
**Relevant context:** `ui/add_dialog.py` (the paste box placeholder, the "Paste one URL per line."
label, the staging list), `UX-003` (nothing enters the queue unprobed — the fact the hint can
teach), `T-060`/`T016-R4` (the focus chain is declared and stable), the `T-203` chain's narrowing
contract
**Affected surfaces:** `ui/add_dialog.py`, `tests/ui/test_add_dialog.py`
**Risk:** Low

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-218--the-add-dialogs-empty-state-one-instruction-inside-the-list).

### T-213 — Remove the dead code a full-tree audit verified

**Status:** **Complete — Approved 2026-08-12.** Built in an authorized unattended run; filed 2026-08-09 from a
maintainer-requested audit of the whole tree.
**Owner:** Implementer
**Priority:** Low — nothing misbehaves; every item is weight with no function
**Phase:** Phase 4 — maintenance. **Not a plan deliverable.**
**Depends on:** the In Review add-dialog chain (`T-203`, `T-204`'s corrections) receiving verdicts
first — two of the items live in files that chain is still changing, and deleting under an open
review moves the review boundary.
**Relevant context:** `ruff check --select F401,F811,F841` is already clean; these are the items
reference-analysis finds and lint cannot. Each was verified to have exactly one occurrence in the
tree — its definition — including string references, the PyInstaller spec's `hiddenimports`, and
`pyproject.toml` entry points
**Affected surfaces:** `ui/add_dialog.py`, `core/output_template.py`,
`tests/ui/test_add_dialog.py`, `ui/widgets/`, `ui/row_delegate.py`
**Risk:** Low — the residual risk is a string-referenced usage the greps missed, which the suite
covers

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-213--remove-the-dead-code-a-full-tree-audit-verified).

### T-231 — Two records still describe the paint implementation `T-218` rejected

**Status:** **Complete — corrected 2026-08-12**, in the same batch as the `T-033`/`T-223` findings.
*(Filed by the Reviewer as `T218-R1`, Low and non-blocking. **The Reviewer's own filing of this
entry was destroyed by the Implementer** — `git checkout -- ai/TASKS.md`, undoing an unrelated
over-deletion, discarded their uncommitted work. This entry is rewritten from `T218-R1`'s text in
`docs/project/REVIEWS.md`; if it differs from what they wrote, theirs was the original.)*
**Owner:** Implementer
**Priority:** Low — behaviour and assertions are correct; what is wrong is that two records point a
future maintainer at an implementation this task's own evidence rejected
**Phase:** Phase 4 — maintenance. **Not a plan deliverable.**
**Depends on:** nothing
**Relevant context:** `T-218`, `T218-R1`, `ui/add_dialog.py`, `tests/ui/test_add_dialog.py`
**Affected surfaces:** comments and one docstring; **no code change**
**Risk:** None

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-231--two-records-still-describe-the-paint-implementation-t-218-rejected).

### T-225 — Two UI test files pass apart and fail together

**Status:** **Complete — Approved with follow-ups 2026-08-12** at the bounded T-123 final-review
manifest recorded in `docs/project/REVIEWS.md`. No blocking T-225 defect was found; its two Low evidence gaps
are carried by `T-229`. Awaiting the required per-task commit split and coordination move to
Complete.
**Owner:** Implementer
**Priority:** Medium — the suite is currently green by an accident of alphabetical collection, and
the accident is one file rename away from ending
**Phase:** Phase 4 — maintenance. **Not a plan deliverable.**
**Depends on:** nothing
**Relevant context:** `tests/ui/test_row_delegate.py`, `tests/ui/test_add_dialog.py`
(`test_an_open_playlist_shows_entries_and_a_way_back`,
`test_the_menu_key_reaches_the_current_rows_menu`), `tests/ui/conftest.py` (the `qapp` fixture —
one `QApplication` for the session, which is the only correct way to run Qt under pytest and also
the reason state can travel between files), `docs/project/TESTING.md`
**Affected surfaces:** `tests/ui/` — test-side unless the reproduction finds otherwise
**Risk:** Low, with one caveat: if the shared state turns out to be in `ui/` rather than in the
tests, the fix is a source change and this entry's scope grows

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-225--two-ui-test-files-pass-apart-and-fail-together).

### T-123 — Evaluate running the suite in parallel

**Status:** **Complete — Approved with follow-ups 2026-08-12.** `T123-R1` and `T123-R2` are
Resolved at the bounded final-review manifest in `docs/project/REVIEWS.md`. The adopted unit/UI slice is
parallel and isolated; integration stays serial behind `T-228`; spawned integration children still
using real per-user directories are filed as `T-230`. Awaiting the required per-task commit split
and coordination move to Complete.
Originally adopted in half on maintainer instruction (*"do T-225 and T-123"*), after CI run
`31553176677` was cancelled at the 15-minute cap inside the `Tests` step
with every other gate green. **`tests/unit` and `tests/ui` take `-n auto`; `tests/integration`
stays serial**, and the reason is evidence rather than caution: two of the hazards this entry
predicted are real, one is fixed here and the other is filed as `T-228`. What was built is at the
end of this entry.
*(Was: **Ready — measured 2026-08-04, and the answer is yes.** `-n auto` runs the
suite in **58 s** against **~400 s** serial — a **7x** reduction — with one hazard identified by
name rather than guessed at. The measurement is below; the adoption has not been done.)*
*(This read "Proposed — for evaluation, not yet a commitment", 2026-08-03. Filed rather than
attempted: the payoff is large and the hazards are specific, and deciding which applies is the
work. That was the right call — the evaluation found the hazard on its second run.)*
**Owner:** Implementer
**Priority:** Medium — the suite is the largest single cost in every gate and in local development
**Phase:** Phase 2 test infrastructure
**Relevant context:** `T-122`, `NFR-001`, `AGENTS.md` §9, run `30861672178`
**Affected surfaces:** `pyproject.toml`, `tests/**`, possibly `.github/workflows/ci.yml`
**Risk:** Medium — the failure mode is *intermittent* tests, which is worse than slow ones

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-123--evaluate-running-the-suite-in-parallel).

### T-195 — The `REQ-023` settings `T-146` defers: default preset and output template

**Status:** **Complete — Approved at `7cd2002` on 2026-08-11.** All seven focused findings are
resolved. The real-file end-to-end proof now completes the composed application's orderly shutdown
and independently exits zero; Windows-native execution remains for CI after this held stack is
pushed, not a blocker to the Linux-reviewed implementation.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-195--the-req-023-settings-t-146-defers-default-preset-and-output-template).

### T-295 — A row's other verbs are dead while one panel is open on it

**Status:** **Complete — Approved at `a406a66` on 2026-08-31** (`T-295`, reviewed at `9fa789b`).
The guard asks which *panel* is open rather than which row, in one place both routes share. **A
second instance was found and fixed in the same pass**: `toggle_playlist` keyed on the row too, so
`→` on a row holding a format panel closed that panel instead of opening the playlist — the toggle
answering for a panel it is not the toggle of. Nine pairs are asserted and the three diagonal ones
are the idempotence the guard was written for: deleting the guard passes the six swaps and fails
those three. Verified against the original guard — 6 swaps and the disclosure fail, the 3 no-ops
pass.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-295--a-rows-other-verbs-are-dead-while-one-panel-is-open-on-it).

### T-294 — The add dialog's status line is an empty tab stop that draws a full-width focus ring

**Status:** **Complete — Approved at `4d0e65b` on 2026-08-31** (`T-294`, reviewed at `9fa789b`).
Focus policy follows the text: copy-ability exists exactly when there is something to copy, the
widget never hides, and it never leaves `focus_chain()` — so the layout does not move and the chain
stays a single declaration made once at construction. The ring is untouched (`T202-R1`) and
`T-218`'s empty summary is untouched.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-294--the-add-dialogs-status-line-is-an-empty-tab-stop-that-draws-a-full-width-focus-ring).

### T-296 — A panel opened in a short list mounts at its 26 px minimum and crushes its contents

**Status:** **Complete — Approved at `8c31d66` on 2026-08-31** (`T296-R1` resolved; reviewed at
`9fa789b` and `96fa0eb`). Two halves, and only the first was a code defect.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-296--a-panel-opened-in-a-short-list-mounts-at-its-26-px-minimum-and-crushes-its-contents).

### T-268 — The reproduced parent-death path does not explain the five orphans

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t258-scan-observations).

**Status:** **Complete — closed 2026-09-04 against `docs/RUNNER_ORPHANS.md`, with the cause
unidentified and recorded as such.** Seven `multiprocessing` spawn children outlived their parents
on `STARBASE` between 2026-08-04 and 2026-08-17 and never exited. **What they are blocked on was
narrowed to one question and then deliberately left unanswered**: they are past their payload read,
have one thread, and every one reports `WrAlertByThreadId` — an in-process synchronisation
primitive — so the remaining question is *which lock*, and answering it needed a live stack from a
machine `OPS-003` says nobody logs into.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-268--the-reproduced-parent-death-path-does-not-explain-the-five-orphans).

### T-282 — A debug level for the application log, reachable without editing code

**Status:** **Complete — Approved at `841e6fc` on 2026-09-04** (`T282-R1`…`R4` and `COORD-R27`
resolved; reviewed at `02b48fa` and `270fc7b`). `--log-level=LEVEL`, matched as the exact token or
the exact `--log-level=` prefix, with `INFO` still the default and an unknown value refused rather
than defaulted. **The mechanism was ruled rather than assumed** — see below.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-282--a-debug-level-for-the-application-log-reachable-without-editing-code).

### T-271 — `Add URLs...` relies on the same unguarded standard key `T-270` was filed for

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t271-ci-upload).

**Status:** **Complete — Approved at `7ca8e63` on 2026-09-04**, with **no implementation
finding** (reviewed at `02b48fa`; `COORD-R27` resolved in `T-282`'s correction at `841e6fc`).
**The post-push Windows execution the approval required is recorded** — see *What is known*.
**One seam, not a second bespoke helper**, which is the second criterion:
`resolve_standard_shortcut(key, fallback)` guards every standard key this project binds, and
`resolve_quit_shortcut` — `T-270`'s entry point, and its tests — now calls into it rather than
owning the logic.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-271--add-urls-relies-on-the-same-unguarded-standard-key-t-270-was-filed-for).

### T-289 — A pool thread's garbage collection destroys widgets while the GUI thread frees them

**Status:** **Complete — Approved at `194316c` on 2026-08-31**, the pool-drain round, after the
measurement round at `c29e299` the same day (`T289-R14`, `R15`, `R16`; `T289-R21`, `R22`, `R24`
resolved, after `R2`…`R5` on 2026-08-30). **`T289-R23`'s remaining half and `T289-R25` were
non-blocking Low and were closed in this entry's completion sync** — see the third-pass section.
**Criterion 2 is met under the re-scope of 2026-09-04**, and the task closes on that wording.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-289--a-pool-threads-garbage-collection-destroys-widgets-while-the-gui-thread-frees-them).

## Complete

### T-197 — Cookie source, and the redaction gate that has to prove it

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t214-correction-checks).

**Status:** **Complete — approved 2026-08-11 at `6a6ce27`.** `T197-R1` and `T197-R7` are
Resolved; `T197-R2` … `T197-R6` remain Resolved.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-197--cookie-source-and-the-redaction-gate-that-has-to-prove-it).

### T-222 — The options dialog clips the container note

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t214-correction-checks).

**Status:** **Complete — approved 2026-08-11 at `4d03937`.** The maintainer-authorised extra
pass resolves T222-R1 and T222-R2.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-222--the-options-dialog-clips-the-container-note).

### T-214 — The layering test proves less than the tree actually promises

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t214-correction-checks).

**Status:** **Complete — approved 2026-08-11 at `28012ad`.**

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-214--the-layering-test-proves-less-than-the-tree-actually-promises).

### T-217 — Placeholder thumbnails read as intentional, not broken

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t214-correction-checks).

**Status:** **Complete — approved 2026-08-11 at `28012ad`.**

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-217--placeholder-thumbnails-read-as-intentional-not-broken).

### T-224 — Draw the ⋮ zone as a button

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t214-correction-checks).

**Status:** **Complete — approved 2026-08-11 at `28012ad`.**

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-224--draw-the--zone-as-a-button).

### T-216 — The finished row: the chip owns the state, the bar retires

**Status:** **Complete — approved 2026-08-11 at `d3f7b50`.**

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-216--the-finished-row-the-chip-owns-the-state-the-bar-retires).

### T-199 — ffmpeg: say which features are gone, and let the user point at one

**Status:** **Complete — approved 2026-08-10 at `245676f`.** All four findings closed; `T199-R1`,
`T199-R2` and `T199-R4` at `c4668e8`, and `T199-R3` at `245676f` after two correction passes.
Built the same day on maintainer instruction, immediately after `T-146` unblocked it.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-199--ffmpeg-say-which-features-are-gone-and-let-the-user-point-at-one).

### T-146 — A Settings menu, and the screen behind it

**Status:** **Complete — approved at `0adf9e3` on 2026-08-10, with one post-approval correction
at the head below.** **`T146-R4` — found by CI on the pushed head, not by review** (see the
findings list): four of this task's own tests hand-wrote TOML with an interpolated path, so on
Windows the unescaped backslashes made `tomllib` reject the whole file and each test asserted a
branch it never reached. **Test-only; no production defect** — `save()` escapes correctly through
`_toml_string`, and the save/load round-trip test passed on Windows. It is `T146-R3`'s defect
class a third time, which is recorded rather than smoothed over. `T146-R1` and `T146-R2`
resolved at `8940353`; `T146-R3` resolved at `2a9d9e1` in the maintainer-authorized pass.
Built the same day on maintainer instruction (*"Do T-215 and then T-146"*);
**the first plan deliverable of Phase 4 to be built.** Filed against `REQ-023`, which
already names every setting asked for.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-146--a-settings-menu-and-the-screen-behind-it).

### T-215 — An offline launch keeps a held queue held

**Status:** **Complete — approved at `b9caa40` on 2026-08-10**, on maintainer instruction (*"Do
T-215 and then T-146"*). **Observed live, not inferred**: the review launched the composed
application offscreen with unreachable URLs, and every durably-queued row became `Failed` within a second — queue
stopped, user touching nothing.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-215--an-offline-launch-keeps-a-held-queue-held).

### T-203 — The row's controls: one preset picker, and the one verb that is genuinely per-item

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t203-checks).

**Status:** **Complete — approved 2026-08-10 at `fe1d246`.** All four findings are Resolved.
The pointer door and row-bound menu are correct, and the correction batch answers the last two:
`_show_row_menu` falls back to
`currentIndex()` when the keyboard-reason position names no row and anchors the popup on the
resolved row, with a shown `CustomContextMenu` dispatch regression that failed on the
uncorrected tree; and the live Phase 4 contracts — the phase preface, `T-200`, `T-218` — plus
one test docstring now state `UX-011`'s option *E*. The hold on the rebuild was lifted by the
maintainer the same night — *"Please do T-203, T208 and T209 overnight"* — which is the
instruction this build acts under. What was built, in one paragraph:
**the three verbs are `QAction`s in the row's own menu** under a *Just this item* heading, above
the Read-again/Choose-a-format/Remove entries the menu already held; the menu opens from a
**painted `⋮` zone carved from the trailing edge of the row's format control**
(`_menu_zone_of`, one definition for paint and hit test) and from the context hook that already
existed — right-click, and since the `T203-R3` correction the Menu key and Shift+F10 through the
current-index fallback — **through one builder**, `row_menu`, so the doors cannot drift; **the bar is removed whole** — label,
three buttons, and `T203-R1`'s
announcement machinery — with `focus_chain()` narrowed and its hand-transcribed test order
updated. **Four mutations fail their own regressions**: the zone anchored at the wrong edge, the
zone hit-test removed, the menu retargeted to the current row, and the `⋮` door unwired.
**One deliberate mechanism change rode along**: `_show_row_menu` now `popup`s the menu instead
of `exec`-ing it — an exec'd nested event loop cannot be returned from headlessly (and PySide's
compiled `exec` resists patching), so the doors would have been undrivable end to end; the menu
is deleted on close, one widget per opening.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-203--the-rows-controls-one-preset-picker-and-the-one-verb-that-is-genuinely-per-item).

### T-209 — Keep an open row panel laid out after a value refresh

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t203-checks).

**Status:** **Complete — Approved with follow-up 2026-08-10 at `5652bf1`.** The correction
itself — `relayout_panel`'s deferred restore — shipped with `T204-R4`; this task ran the criteria
that had not been run: the real `manager.job_changed` signal after a real `Space`, panel/index
identity and geometry, a usable close route, and the changed selection surviving it. The format
panel now has the same value-refresh proof. Codex independently disabled `relayout_panel` and all
three value-refresh regressions failed. `T209-R1` is non-blocking and owned by `T-221`: a
real-display disposition of the one-turn minimum-size state during every open.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-209--keep-an-open-row-panel-laid-out-after-a-value-refresh).

### T-210 — An opened row can be taller than the list, putting its own Done button out of reach

**Status:** **Complete — Approved 2026-08-10 at `de98190`.** `T210-R1` is Resolved under the maintainer's recorded sub-600px scope ruling. The exact-head archive passed 2822 tests; the 600px bound and the below-bound readable floor each kill their opposing mutation.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-210--an-opened-row-can-be-taller-than-the-list-putting-its-own-done-button-out-of-reach).

### T-204 — A row that stops being committable keeps its panel and loses the way to close it

**Status:** **Complete — Approved with follow-ups 2026-08-09 at `9813f19`.** `T204-R1`,
`T204-R4` and `T204-R2` are all **Resolved**; the third focused pass verified the close route
through the panel's own *Done*, the restored panel geometry, and the swept coordination copies.
The two follow-ups have since advanced without reopening this approval: `T204-R3`/`T-208`
reproduced and fixed one route and is Blocked on the maintainer's report disposition; `T-209` is
Approved with the non-blocking real-display follow-up `T-221`.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-204--a-row-that-stops-being-committable-keeps-its-panel-and-loses-the-way-to-close-it).

### T-207 — Reproduce T-204 through a reachable transition

**Status:** **Complete — Approved with follow-up 2026-08-09 at `9813f19`.** The reproduction drives a transition production can reach and closes through a real control. `T207-R1` is a **Low, non-blocking** current-truth follow-up, corrected in this entry's sibling text below.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-207--reproduce-t-204-through-a-reachable-transition).

### T-211 — Destroying an editor trusted the row it was billed to, and crashed

**Status:** **Complete — Approved 2026-08-09 at `9813f19`.** Identity-based teardown clears the exact editor being destroyed whatever the row numbering has done, and the regression reaches the former crash site after the deferred delete. The old row-number comparison is the mutation the evidence fails on.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-211--destroying-an-editor-trusted-the-row-it-was-billed-to-and-crashed).

### T-192 — The stopped-queue message hides at the right, against the ffmpeg summary

**Status:** **Complete — Approved 2026-08-09 at `027dc7c`.** Found by the maintainer
2026-08-08 and fixed the same day. The reviewer ran a **negative probe**: a property-only
change does not restyle, and the explicit repolish moves the weight 600 → 400 — the failure
a test asserting the property rather than the rendered result would have missed.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-192--the-stopped-queue-message-hides-at-the-right-against-the-ffmpeg-summary).

### T-193 — The playlist picker shows two entries at a time, and can stick open showing none

**Status:** **Complete — the sizing half Approved 2026-08-09 at `a6fbf67`**, after
`T193-R1`. **The stuck-open half is `T-204`'s**, and the reviewer ruled the split legitimate:
*"sizing and the stuck-open panel are independent mechanisms with distinct correction
contracts."* **Acceptance criteria 3 and 4 below are `T-204`'s** and are not claimed here.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-193--the-playlist-picker-shows-two-entries-at-a-time-and-can-stick-open-showing-none).

### T-194 — Reordering a row scrolls the queue back to the top

**Status:** **Complete — Approved 2026-08-09 at `a6fbf67`**, after `T194-R1`. Found by the
maintainer 2026-08-08 and fixed the same day.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-194--reordering-a-row-scrolls-the-queue-back-to-the-top).

### T-205 — Include the playlist header in its pre-mount height

**Status:** **Complete — Approved 2026-08-09 at `a6fbf67`.** `EntryTable.sizeHint` now asks
`header.isHidden()` rather than `header.isVisible()`, so the header's height is counted while
the picker is still unmounted — which is when `AddUrlDialog.panel_height_for` asks for it.
**The first correction's test was also wrong** and a mutation caught it: it re-measured the
hint *after* `show()`, where `isVisible()` is already true and both versions agree. The test
now captures the hint unmounted, mounts at that height, and asserts the scroll range.
**Owner:** Implementer
**Priority:** Medium — the sizing change still leaves every at-or-below-cap playlist scrolling,
which is the interaction the task exists to remove
**Phase:** Phase 4 — focused correction to T-193
**Depends on:** nothing
**Relevant context:** `T-193`, `T193-R1`, `ui/playlist_picker.py` (`EntryTable.sizeHint`),
`tests/ui/test_playlist_picker.py`
**Affected surfaces:** `ui/playlist_picker.py`, `tests/ui/test_playlist_picker.py`
**Risk:** Low — one height term and its mounted-widget proof; the seam is timing-sensitive because
the dialog asks for the hint before the panel is visible

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-205--include-the-playlist-header-in-its-pre-mount-height).

### T-206 — Reopen a queue editor without selecting its row

**Status:** **Complete — Approved 2026-08-09 at `a6fbf67`.** `_reopen_editor` now positions the editor
through `selectionModel().setCurrentIndex(index, NoUpdate)` instead of the view's own
`setCurrentIndex`, which selects. Selection is `_restore_current_row`'s to decide; both
handlers run on `modelReset` and the last writer was winning. Two regressions cover it —
an unselected row stays unselected, and a selected one stays selected.
**Owner:** Implementer
**Priority:** Medium — a reset with an editor open creates a selection the user never made and
therefore exposes selection-scoped row actions
**Phase:** Phase 4 — focused correction to T-194
**Depends on:** nothing
**Relevant context:** `T-194`, `T194-R1`, `T126-R1`, `T-086`, `ui/queue_view.py`
(`_restore_current_row`, `_reopen_editor`), `tests/ui/test_queue_view.py`
**Affected surfaces:** `ui/queue_view.py`, `tests/ui/test_queue_view.py`
**Risk:** Low — current-index and selection restoration share a reset path, so the selected and
unselected cases must be proved together

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-206--reopen-a-queue-editor-without-selecting-its-row).

### T-188 — A recorded source with a separate video and audio stream

**Status:** **Complete — Approved 2026-08-08 at `3ce0b8b`.** `T188-R1` is **Resolved** with no open
findings, after three correction passes. **This closes the last of the six loose items the
maintainer ruled into Phase 3**, which left the phase exit review as the only thing outstanding
**as of that date**. *(That review was approved at `ccdbd0f` on 2026-08-09 and Phase 3 has exited;
the clause is kept because it records what this task's approval closed.)*
*(Was: Blocked on `T188-R1` (High) — the recorded fixture was added *beside* the synthetic evidence
rather than **adopted**, leaving criteria 3 and 4 unmet.)*

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-188--a-recorded-source-with-a-separate-video-and-audio-stream).

### T-186 — Finish the withdrawn-History prose sweep

**Status:** **Complete — Approved 2026-08-08 at `7dd5d8d`.** `T186-R1` (High) is **Resolved** after
**three passes**, and the third is the one that worked because it changed *method* rather than
effort. *(Was: Proposed — filed from non-blocking `T176-R1`, 2026-08-07.)* `T-176` corrected a
useful first set; this finished the semantic audit.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-186--finish-the-withdrawn-history-prose-sweep).

### T-189 — Make the required ffmpeg CI cases fail instead of skip

**Status:** **Complete — Approved 2026-08-08 at `365182c`.** `T189-R1` (High) — the environment
recording step's comment still denied the gate added two steps below it — is **Resolved**, and no
open finding remains. *(Was: Proposed — filed 2026-08-07 by the `T-108` correction re-review,
`T108-R3`.)* The Windows evidence was real and green throughout; this keeps a later missing tool
from turning that required gate into a silent skip.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-189--make-the-required-ffmpeg-ci-cases-fail-instead-of-skip).

### T-171 — Decide whether files carry provenance

**Status:** **Complete — decided 2026-08-08, and the decision is *no*.** `DAT-008` is accepted: the
application writes no provenance of its own into any output file or sidecar. **No implementation
task follows and no dormant UI is added**, which is what this task's seventh criterion asks of a
rejection.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-171--decide-whether-files-carry-provenance).

### T-143 — A playlist's entries are never probed, so their rows stay bare

**Status:** **Complete — Approved 2026-08-08.** Reviewed at `bf30d82` and **Blocked** on `T143-R1`
(High): the first acceptance criterion required pre-download *size*, which no row of any kind
carries. **The maintainer amended the criterion** to the `UX-005` §3 row anatomy and deferred
pre-download size to `T-191`; **no source changed for that amendment**, and the focused
documentation re-review **resolved `T143-R1`**. The code itself drew no finding at any point.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-143--a-playlists-entries-are-never-probed-so-their-rows-stay-bare).

### T-180 — Two permitted instances share one thumbnail cache and sweep each other's pictures

**Status:** **Complete — Approved 2026-08-08.** Reviewed at `bf30d82` and **Blocked** on two
findings, both corrected and **Resolved** on re-review: `T180-R1` (High) — the boundary and the
adoption policy were implemented without the accepted decision this entry itself required first,
now **`DAT-007`, accepted 2026-08-08**; `T180-R2` (Medium) — the principal test bypassed production
composition, now asserted through two composed applications and mutation-checked at three seam
points. *(Was: Proposed — **filed out of `T179-R1`'s maintainer disposition, 2026-08-07.** The
finding was about a gate that cannot see another process; the defect underneath it is that the two
processes are allowed to collide in this directory at all.)*

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-180--two-permitted-instances-share-one-thumbnail-cache-and-sweep-each-others-pictures).

### T-111 — User presets: create, edit, duplicate, delete, set default

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t111-checks).

**Status:** **Complete — Approved 2026-08-08.** Reviewed by Codex at `bf30d82` (*Changes
requested*, three findings), corrected the same day, and **approved on re-review**: `T111-R1`,
`T111-R2` and `T111-R3` are all **Resolved** and no open finding remains. **The ninth and last
Phase 3 deliverable.**

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-111--user-presets-create-edit-duplicate-delete-set-default).

### T-113 — Resume a partial download across a restart

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t113-timing).

**Status:** **Complete — Approved at `476cf60`** (2026-08-08). Three findings over two rounds, all
resolved. `T113-R1` was **Critical** and took two corrections: the first made every traversal
spelling in a job id unrepresentable, and a **symlink already at the resulting name** was still
accepted by the worker's `mkdir(exist_ok=True)` — a guard at one end of the directory's lifetime is
not a guard. The reviewer verified the hard-kill and orderly-close resumes end to end, each with a
ranged continuation and byte-exact output.
**Owner:** Implementer
**Priority:** Medium — and the highest *uncertainty* in the phase
**Phase:** Phase 3
**Depends on:** Phase 2 exit
**Relevant context:** `docs/UX_SPEC.md` §9.2 (**`P-10` is ruled 2026-08-07 by `UX-007`, and the
ruling is that *this task decides it*** — whether per-job pause returns, whether `JobStatus.PAUSED`
comes back, and whether a playlist header gets `Pause all` (`T140-R5`). It depends on what resume
actually costs per site and format, which is what this task exists to find out, and **the answer
must be recorded as a decision either way**. `P-24` is ruled outright: a non-resumable job **says so
on its row** and offers *start again* as its own verb. The older note follows — **`P-10` reopens
`UX-001`'s per-job pause** — the
last criterion below is that same question, and answering one answers both), `REQ-017`, `UX-001` (this is its named reopening condition) **as amended by
`UX-006`** — the queue-level gate is now *stopped until started*, which changes the default this
task reopens against and changes nothing about per-job pause, `T-080`
(removed `JobStatus.PAUSED`), `ARCHITECTURE.md` §5, `NFR-003`
**Affected surfaces:** `core/job_state.py`, `downloader/`, `persistence/`
**Risk:** **High** — it is the one Phase 3 item whose feasibility depends on the site and format

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-113--resume-a-partial-download-across-a-restart).

### T-109 — Post-processing: audio, container, thumbnail, metadata, chapters, subtitles

**Status:** **Complete — Approved at `ddd1f59`** (2026-08-08). Ten findings over three rounds, all
resolved: `T109-R1`..`R7` from the review of `4cb549d`, and `T109-R8`..`R10` which the first
correction diff introduced. `T109-R8` was **Critical** — `claim_outputs` decided a reported source
belonged to the staging directory with a lexical test, so `staging/../Clip.de.vtt` moved a
user-owned file into the download's output family.
**Owner:** Implementer
**Priority:** High — the largest single item in the phase
**Phase:** Phase 3
**Depends on:** `T-105`; `T-108` for the ffmpeg-presence rule it shares. Both approved.
**Relevant context:** `docs/UX_SPEC.md` §6 (**ruled 2026-08-07 by `UX-007`**: this **shares one
screen** with `T-111`, reached as a per-download *Options…* and from the preset manager (`P-16`,
`P-3`), a one-off never becomes a preset silently (`P-4`), and subtitle languages are a multi-select
**populated from the probe's own languages** — which makes the list's source this task's to build
(`P-17`). The out-of-scope line below is engineering scope, not a UI ruling.
**`P-12` is ruled** as of 2026-08-07 — `ARC-010` says the five undedicated options get **typed
fields** and the model widens, so this task no longer waits on it and no longer chooses), `REQ-010`,
`REQ-024`, `T-077` (four of five download options had never produced a file), `T-076`, `T-089`,
`downloader/ytdlp_adapter.py`
**Affected surfaces:** `core/models.py`, `core/presets.py`, `downloader/ytdlp_adapter.py`,
`downloader/worker.py`, `persistence/repositories.py`, `ui/options_dialog.py` (new),
`ui/format_text.py`, `ui/row_delegate.py`, `ui/add_dialog.py`, `tests/fixtures/capture.py`
**Risk:** **High** — seven independent options, each of which can be wired to produce no effect

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-109--post-processing-audio-container-thumbnail-metadata-chapters-subtitles).

### T-110 — Playlists: probe the entries, choose which to enqueue

**Status:** **Complete — Approved at `3a53d66`** (2026-08-08). No findings. The reviewer
confirmed the picker is the shared `RowPanel` mechanism, that only checked entries are
submitted in one batch with their original playlist positions, and that a single item is
still one job.
**Owner:** Implementer
**Priority:** High — it changes what a *job* is, which reaches `core/`
**Phase:** Phase 3
**Depends on:** `T-105`
**Relevant context:** `docs/UX_SPEC.md` §7 (**ruled 2026-08-07 by `UX-007`**: the picker is the
**staging row, opened** (`P-19`, the same mechanism `P-1` gives the format table), entries carry
**checkboxes** with a tri-state group header (`P-5`), and filtering stays refused (`P-25`)), `REQ-004`, `REQ-002`, `core/models.py`, `ui/add_dialog.py`,
`persistence/repositories.py` (`append` allocates positions in one transaction), `T-078`
**Affected surfaces:** `core/models.py`, `downloader/ytdlp_adapter.py`, `ui/add_dialog.py`,
`persistence/`
**Risk:** **High** — today one URL is one job; a playlist is one probe producing N

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-110--playlists-probe-the-entries-choose-which-to-enqueue).

### T-112 — The output template editor, with a live path preview

**Status:** **Complete — Approved at `3d6f9bc`** (2026-08-08). No findings. The reviewer
confirmed the parent and the worker end template rendering at the same `contained_output_path`
and share the worker's postprocessed-name and collision path, and matched a real local download
against the preview through a subdirectory, Windows-illegal title characters and MP3
conversion — which is **Phase 3's exit criterion for this deliverable**.
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 3
**Depends on:** `T-105`
**Relevant context:** `docs/UX_SPEC.md` §9.1 (preview and write are one function; **`P-22`, the
preview's focus and announcement policy, is **ruled 2026-08-07** by `UX-007`: a **focusable
read-only field**, a second stop in the tab order, ruled against this file's own proposal of an
unfocusable live region — a user who cannot `Tab` to the preview cannot review it at their own pace.
**`P-23` is ruled with it: a containment failure is shown at edit time, with the reason.** `P-9` too
— the editor **lists its supported fields inline** beside the input. *(This read "`P-23` is this
task's own report-as-you-type
criterion", which is the unratified timing stated as task truth three lines above the criterion that
says it is unruled — `T105-R4`, second correction.)*), `REQ-011`, `DAT-002`, `core/paths.py` (`sanitize_component`, and `T-046`'s
atomic reservation), `T-034`, `T-045`, `T-067` (long paths), `NFR-004`
**Affected surfaces:** `core/paths.py`, `ui/`
**Risk:** Medium — the preview must be the same function the download uses, or it lies

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-112--the-output-template-editor-with-a-live-path-preview).

### T-114 — Confirm before queueing a URL the queue already holds

**Status:** **Complete — Approved at `4786417`** (2026-08-08). No findings. The reviewer
confirmed the comparison is exact and Qt-free, that the queue supplies URLs from its in-memory
model, and that staging duplicates performs no write and the commit adds no persistence
surface.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-114--confirm-before-queueing-a-url-the-queue-already-holds).

### T-185 — Re-capture the fixtures so the format columns rest on a real report

**Status:** **Complete — Approved at `870d56f`** (2026-08-07). Both halves landed: `T107-R8`'s
false provenance is corrected and gated, `T185-R2`'s false policy sentence is derived from the
allowlist rather than written beside it, and **a source that reports `fps` was found** — so the
column `OPS-013` was ratified to excuse rests on a recording after all.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-185--re-capture-the-fixtures-so-the-format-columns-rest-on-a-real-report).

### T-108 — Choose a video and an audio stream, and merge them

**Status:** **Complete — Approved with follow-up `T-189` at `870d56f`** (2026-08-07). The table
is mounted, both selection modes work, both ffmpeg facts are separately asserted, and **a chosen
pair produces a real merged file on both platforms** — Windows run `31233348009` recorded ffmpeg
8.1.2 and the merge test **passed rather than skipped**. `T108-R3` is the non-blocking follow-up:
that test *skips* without ffmpeg while the Windows job only records it, so a later missing install
could leave CI green with the required proof silently absent. `T-189` owns it.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-108--choose-a-video-and-an-audio-stream-and-merge-them).

### T-107 — The format table: every stream a probe found

**Status:** **Complete — Approved at `09c57c3`** (2026-08-07). Five of the seven findings resolved
on the first correction; `T107-R3` on the second; `T107-R1` was technically satisfied at `09c57c3`
but blocked on authority alone — the Reviewer had *offered* the criterion amendment and correctly
refused to treat its own offer as the ruling. **The maintainer ratified it as `OPS-013`**, and
`T107-R1` resolves. `T107-R8` is a non-blocking follow-up owned by `T-185`. *Was blocked on Phase
2's exit and on `T-105`'s `docs/UX_SPEC.md`; both cleared, and `UX-007` ruled its surface.*

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-107--the-format-table-every-stream-a-probe-found).

### T-181 — The queue is stopped until the user starts it

**Status:** **Complete — Approved with follow-ups at `fb3d274`** (2026-08-07). Filed against
`REQ-015` as amended by the maintainer decision `UX-006`, and implemented the same day.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-181--the-queue-is-stopped-until-the-user-starts-it).

### T-187 — Remove the superseded no-Held source contract

**Status:** **Complete — 2026-08-07, awaiting review.** Taken inside `T-107`'s correction round
rather than left standing: it is one comment, and a superseded rationale sitting in `main_window.py`
while the spec above it says the opposite is exactly the drift `T105-R4` was about. Filed from
non-blocking `T181-R2`; `T181-R1` corrected the
row and `docs/UX_SPEC.md`, but `MainWindow.__init__` still teaches the opposite in a present-tense
comment: that the stopped state exists only at queue level and the Held row was not built.
**Owner:** Implementer
**Priority:** Low — runtime behavior is correct; the residue can mislead the next change to the
queue-state presentation
**Phase:** Phase 3 cleanup
**Depends on:** nothing
**Relevant context:** `UX-006` item 3, `T181-R1`, `T124-R4`, `docs/UX_SPEC.md` §2 item 7 and §2.1
**Affected surfaces:** the queue-gate explanation in `src/tracks_and_trails/ui/main_window.py` and
a narrow sibling prose search. **No production logic or historical record**
**Risk:** Low — preserve the distinction between one queue-level gate and its two presentations

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-187--remove-the-superseded-no-held-source-contract).

### T-182 — Rule on the option families `REQ-EXCL` and `NFR-007` touch

**Status:** **Complete — ruled 2026-08-07, recorded as `SEC-003`.** Filed the same day with
`ARC-010`, which explicitly did not decide it. The deliverable was a decision, and it exists:
`--netrc` and client certificates are permitted while `-u`/`-p`/`--video-password` are not;
`--impersonate` and `--xff` are forbidden; `--geo-verification-proxy` is permitted; `--exec` is
forbidden **and `ARC-010` §3 is corrected** because it claimed containment reaches a shell command;
`--download-archive` is permitted as a user-named file with no default path; SponsorBlock is
permitted opt-in with `NFR-007` amended to name the destination.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-182--rule-on-the-option-families-req-excl-and-nfr-007-touch).

### T-176 — Put the withdrawn History prose in the past tense

**Status:** **Complete — 2026-08-07, awaiting review.** Filed by the Reviewer on 2026-08-06 for
`T175-R1`: `T-175` removed the four runtime contracts it owned, but did not finish the current-tense
source/test prose portion of `T170-R4` that it explicitly inherited.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-176--put-the-withdrawn-history-prose-in-the-past-tense).

### T-105 — Write `docs/UX_SPEC.md` before Phase 3 starts

**Status:** **Complete — Approved 2026-08-07** in the bounded working tree. All four findings are
Resolved: `T105-R3` at `a688a4e`, `T105-R1` and `T105-R2` on the second re-review, `T105-R4` on the
maintainer-authorized final pass.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-105--write-docsux_specmd-before-phase-3-starts).

### T-168 — A group's `Remove` comes back as the window gets smaller

**Status:** **Complete — Approved 2026-08-07.** `T168-R1` is **Resolved**: the reviewer reproduced
both mutants independently in a temporary tree and got the same 3/3 and 2/4 splits recorded below.
Changes requested at `3859190` first; the implementation was accepted as correct then, and the
finding was that its required *any entry count* gate was not implemented — the sweep fixed the
segment count at sixteen. The sweep is now parameterized over `RESERVE_COUNTS` — 5, 8, 9, 16, 24 and 37, both sides
of `MERGED_BLOCKS` and four different merge thresholds — keeps the per-pixel downward sweep and the
non-vacuity assertion, and adds a per-count assertion that the sweep actually spanned that count's
threshold. **Mutation-checked both ways** (below).
*(This read "Complete — 2026-08-06, awaiting review".)*
Found by the maintainer, 2026-08-06,
narrowing the window on a sixteen-entry playlist. **Direction 1 was taken**: the bar asks for its
*widest* rendering rather than the one this width chose, so the space left for the verbs is
`max(0, width - segment_span(entries) - VERB_GAP)` — continuous and non-decreasing, with no width
at which narrowing the row gives a verb back. The bar loses nothing: it is drawn into whatever the
verbs leave and still picks its block count from `_bar_line`, so a merged bar spends the freed
width on eight wider blocks. Swept every pixel from 300 to 1200; the mutation restoring the old
reserve fails at the threshold.
**Owner:** Implementer
**Priority:** Medium — nothing is unreachable (`⋯` holds the verb throughout), but a control that
returns when you take space away teaches the user that the row is arbitrary
**Phase:** Phase 3
**Depends on:** nothing. It is `T-163`, `T-164` and `T-167` meeting
**Relevant context:** `T-167` (the bar changing shape twice, the same property one field over),
`T-163` (the bar's share of the last line), `T-164` (the eight-block merge), `T-135` (`⋯` holds what
was dropped), `UX-005` §4, `ui/row_delegate.py` (`_bar_reserve`, `_bar_line`, `_verb_rects`)
**Affected surfaces:** `ui/row_delegate.py`, `tests/ui/test_row_delegate.py`
**Risk:** Low to fix, Medium to fix *without* reopening what `T-163` and `T-164` each decided

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-168--a-groups-remove-comes-back-as-the-window-gets-smaller).

### T-179 — Every model reset scans the thumbnail cache, including a pure reorder

**Status:** **Complete — Approved with follow-ups at `1e0d0d5`** (2026-08-07, base `e159c9a`).
`T179-R2` is Resolved at `5f469da`. `T179-R1` is **dispositioned rather than fixed**: the maintainer
accepted the cross-process limitation on 2026-08-07 and both collision directions are filed as
`T-180` — see **Maintainer disposition** below. One new **Low** finding, `T179-R3`, is open and
**targeted at `T-180`**: `cache_generation()` compresses "until this one's own membership changes"
to "one sweep's delay", and sweeps are event-driven rather than periodic, so the elapsed time can be
the rest of the process lifetime. It does not reopen this task.
*(This read "In Review — the corrected rationale awaits the reviewer", then before that "corrected
twice, third mechanism, awaiting re-review 2026-08-06".)*
**Three rejections, and all were the reviewer's.** `T179-R1` survived two corrections and
`T179-R2` — **High** — was introduced *by* the first. The Medium pass budget is exhausted and
**the maintainer authorised another pass on 2026-08-06**; the High needed no authorization.
Correction round 2 is at the bottom of this entry, on a base of checkpoint `961cada`, which is the
rejected state committed deliberately so this correction has a boundary of its own.
**Owner:** Implementer
**Priority:** Low
**Phase:** Phase 3 cleanup
**Depends on:** nothing
**Relevant context:** `T-119` (the criterion this must not break), `T118-R13`, `NFR-004`,
`ARC-005`, `NFR-001`
**Affected surfaces:** `ui/queue_view.py`, its tests
**Risk:** **Medium.** `T-119`'s criterion is that a picture goes with its job and survives while any
other job names it. A gate that skips too much turns that into a cache that never shrinks

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-179--every-model-reset-scans-the-thumbnail-cache-including-a-pure-reorder).

### T-177 — Startup reads the whole queue to find the few rows it wants

**Status:** **Complete — `T177-R1` Resolved by the Reviewer 2026-08-06, at checkpoint `961cada`.**
Filed from an efficiency audit (Codex) and authorised by the maintainer in the same instruction.
Behavior-preserving, and measured before and after rather than argued. **One acceptance criterion
was written on a false premise and is corrected in place below** — `IN ()` is valid SQLite — which
the mutation check found rather than a reading.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-177--startup-reads-the-whole-queue-to-find-the-few-rows-it-wants).

### T-178 — Delete the `FormatChoice` serializers migration 0009 orphaned

**Status:** **Complete — `T178-R1` Resolved by the Reviewer 2026-08-06, at checkpoint `961cada`.**
Filed from the same audit and authorised with it. The three names and the `FormatChoice` import are
gone; `fields` and the request pair stay. The deletion was accepted in the first pass; **the
replacement comment was not**, and `T178-R1` is the correction.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-178--delete-the-formatchoice-serializers-migration-0009-orphaned).

### T-173 — One `_now()`, not one per module that needs the same clock

**Status:** **Cancelled 2026-08-06 — the premise was wrong** (`T169-R5`). It proposed centralising a
clock that two modules defined identically. **There are not two clocks in use.** `manager._now` has
seven callers; `persistence/store._now` has none, and has had none since the withdrawal removed the
completion write that used it.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-173--one-_now-not-one-per-module-that-needs-the-same-clock).

### T-158 — A refused Open is reported where nobody is looking

**Status:** **Complete — approved with follow-ups at `b92ec62`, 2026-08-06**, with no finding of its
own. A refusal is now said three times: at the row, in the status
bar, and to assistive technology. **Nothing was broken and nothing was rewritten** — the sentence
`reveal.Refusal` already carried is delivered to two more places.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-158--a-refused-open-is-reported-where-nobody-is-looking).

### T-175 — Remove the machinery the withdrawal left with no caller

**Status:** **Complete — approved with follow-ups at `b92ec62`, 2026-08-06.** All four items
resolved. **The fourth found a hole in the suite**, which is the part worth reading. The one
follow-up is `T175-R1`, **Low and Open** — the prose half of `T170-R4` that this task inherited and
did not finish; owner Implementer, target `T-176`.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-175--remove-the-machinery-the-withdrawal-left-with-no-caller).

### T-174 — Say "ledger" where the code still says "history"

**Status:** **Cancelled 2026-08-06 — moot.** It proposed renaming `HistoryRepository`,
`HistoryEntry`, `store.clear_history` and `writer.clear_history` to say *ledger*. **Every one of
those identifiers has been deleted**, and there is no ledger for the survivors to be named after:
`REQ-020` is withdrawn and migration `0009` dropped the table this task promised not to rename.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-174--say-ledger-where-the-code-still-says-history).

### T-172 — Delete the ledger's removal API, which nothing calls

**Status:** **Cancelled — 2026-08-06, moot.** It proposed deleting the ledger's unreachable removal
API. `REQ-020` was withdrawn the same day and the whole ledger went with it, including everything
this task named. Kept as the record that the dead code was found before the feature was.
**Owner:** Implementer
**Priority:** Low
**Phase:** Phase 3
**Depends on:** `T-170`, complete
**Relevant context:** `DAT-005`, `DAT-006`, `T-125`, `T-144`, `persistence/repositories.py`
(`HistoryRepository`), `persistence/store.py`, `persistence/writer.py`
**Affected surfaces:** `persistence/`, `tests/unit/test_persistence.py`
**Risk:** Low — it is deletion, and the gate is that the suite still passes without the tests that
only exercised the deleted code

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-172--delete-the-ledgers-removal-api-which-nothing-calls).

### T-170 — Replace the History tab with a small ledger

**Status:** **Complete — 2026-08-06.** The History view, its tab and the tab widget are gone and
the window is the Queue. **What this task built beyond that no longer exists**, and the title above
names a ledger there is no longer any of:

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-170--replace-the-history-tab-with-a-small-ledger).

### T-169 — Make completion history an internal ledger

**Status:** **Complete — 2026-08-06, and half of what it decided was superseded the same day.**

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-169--make-completion-history-an-internal-ledger).

### T-156 — The MP3 preset does not say which bitrate it means

**Status:** **Complete — 2026-08-06, the disclosure half only**, which is what this entry's own
recommendation asked for: *"disclose first, and decide the control with `T-111`"*. Every surface
now reads `Audio only (MP3), 192 kbps`, rendered by `format_text.format_name` from the choice's own
`audio_quality`. **The control half is not done and is not claimed** — see below. *(Was: Proposed —
**found by the maintainer, 2026-08-05**, reading the queue row's format dropdown. **New scope:
Phase 3**, and not a criterion 8 defect — nothing in `T-132`–`T-141` or the mockups covers what a
preset's name discloses.)*

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-156--the-mp3-preset-does-not-say-which-bitrate-it-means).

### T-150 — The add dialog opens narrower than the rows it holds

**Status:** **Complete — 2026-08-06.** The staging list asks for the width the row anatomy needs,
derived from the delegate's own metrics, and the dialog's layout turns that into its opening size:
**302 px before, 670 px after**. Measured at the old size, the viewport was 254 px and
`_control_rect` had already narrowed the format control to `MIN_CONTROL_WIDTH` — the dialog opened
with the control at the narrowest it is *allowed* to be. **A size hint, not a minimum**, so
narrowing still works and `T-135`'s overflow and `T-160`'s narrowing control stay reachable rather
than being fenced off. *(Was: Proposed — **found by the maintainer, 2026-08-05**, running the built
application. **New scope, so Phase 3 by the closed-list rule** — nothing in `T-132`–`T-141` or
either adopted mockup specifies this dialog's size.)*

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-150--the-add-dialog-opens-narrower-than-the-rows-it-holds).

### T-159 — History reports the format as a yt-dlp id

**Status:** **Complete — approved at `cc94371`, 2026-08-05**, after one correction round, on criteria
**narrowed by maintainer ruling** (2026-08-05, `T159-R2`): the conversion/bitrate criterion is
moved to `T-156`, which owns the control half it depends on.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-159--history-reports-the-format-as-a-yt-dlp-id).

### T-144 — History can only be cleared one record at a time

**Status:** **Complete — approved at `cc94371`, 2026-08-05**, after one correction round. `DAT-005` §1 is
**reopened and amended by maintainer ruling** (2026-08-05), which `T144-R1` required: the entry
outranks this task and named its own reopening condition, but that made an amendment eligible for
a decision rather than self-accepting. The implementation is unchanged — the reviewer found it
conditionally sound — and what changed is that the decision it rests on now exists.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-144--history-can-only-be-cleared-one-record-at-a-time).

### T-142 — A History playlist has no verbs of its own

**Status:** **Complete — approved at `cc94371`, 2026-08-05**, after one correction round. `T142-R1` is
corrected: the header offered *Show in folder* while its own line said the members shared no
folder, then routed to whichever came first. The offer and the route now ask one function, so the
row cannot contradict itself, and the check is repeated when the verb is routed.
**Owner:** Implementer
**Priority:** Medium — the two tabs draw the same row anatomy and answer different verbs on it
**Phase:** Phase 3
**Depends on:** `T-145`, which has to decide what a history group *is* before anything can act on
one. `T-140` (done) is the queue-side precedent to follow rather than reinvent
**Relevant context:** `UX-005` §3 and row 9, `DAT-005` §4, `T-140`'s `group_verbs`, `T-145`,
`ui/history_view.py`, `ui/row_verbs.py`
**Affected surfaces:** `ui/history_view.py`, `ui/row_verbs.py`, `ui/main_window.py`
**Risk:** Medium — the verbs differ from the queue's, and assuming they do not is the trap

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-142--a-history-playlist-has-no-verbs-of-its-own).

### T-145 — History lists a playlist's tracks individually instead of grouping them

**Status:** **Complete — approved at `cc94371`, 2026-08-05**, after one correction round. `UX-005`'s
three decisions are **ratified by the maintainer** (2026-08-05), which `T145-R1` required and
which the first submission wrongly claimed: the chip is a count, there is no segmented bar, and a
partly-failed playlist counts the members present. Two review findings are corrected —
`T145-R2`, a hidden member's thumbnail reaching the row after a closed playlist, which is the
two-index-space defect this task claimed to have audited; and `T145-R3`, a header that drew its
format and folder but did not speak them.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-145--history-lists-a-playlists-tracks-individually-instead-of-grouping-them).

### T-167 — The playlist bar changes shape twice as the window narrows

**Status:** **Complete — 2026-08-05.** The rendering is decided from the row's own text line, whose
width differs from the window's by fixed furniture only, rather than from the space the verbs left
over. Swept one pixel at a time across 380-1200 px: five reversals before, one transition after.
`UX-005` row 9b-i stands unamended. *(Was: Proposed — **found by the maintainer, 2026-08-05**. The
question it carried is **answered**: asked directly whether a narrow bar should become
fewer-but-bigger blocks or one plain bar, the maintainer chose **fewer, bigger blocks**, and this
task is only about *when* the change happens and that it happens once.)*
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 3
**Depends on:** `T-164`, which decides *what* the narrow rendering is. This decides *when*, and
that the answer must be stable
**Relevant context:** `UX-005` rows 9b and 9b-i, `T-155`, `T-135`, `ui/row_delegate.py`
(`_paint_segments`, `_verb_rects`)
**Affected surfaces:** `ui/row_delegate.py`, possibly `UX-005`
**Risk:** Low to fix, Medium if it reopens 9b-i

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-167--the-playlist-bar-changes-shape-twice-as-the-window-narrows).

### T-164 — A sixteen-block bar is unreadable in a narrow window

**Status:** **Complete — 2026-08-05.** Below the threshold the sixteen entries fold into
`MERGED_BLOCKS`, each taking the worst state it covers; above it nothing changed. The gap no
longer varies, so the deliberate merge cannot be mistaken for `T-155`'s accidental one. *(Ruled
2026-08-05: the maintainer chose **merge to a fixed block count, each block taking the worst state
inside it**, recorded as `UX-005` row 9b-i. Their first suggestion — one solid *done of total* bar
— was put to them with what it costs and **rejected**: it moves the failure out of the drawing and
into the text, which is the shape 9b was adopted against.)*
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 3
**Depends on:** nothing — the `UX-005` amendment it was waiting for is made. `T-163` is adjacent — that one is about the bar having *room*,
this is about what to draw once it does
**Relevant context:** `UX-005` row 9b, `T-140`, `T-155`, `ui/row_delegate.py` (`_paint_segments`)
**Affected surfaces:** `ui/row_delegate.py`, `UX-005`
**Risk:** Medium — the obvious fix removes the thing row 9b exists for

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-164--a-sixteen-block-bar-is-unreadable-in-a-narrow-window).

### T-163 — The verbs hold their ground until the progress bar has none

**Status:** **Complete — 2026-08-05.** The bar's share of the last line is taken out before the
verbs are laid out, so a verb drops into `⋯` rather than shaving the bar. The floor is derived from
`MIN_BLOCK_WIDTH` — `segment_span` for a playlist, a quarter of that per quarter-reading for a
fraction. **One stated exception:** on a line too narrow for the merged bar *and* the `⋯`, the
button wins and the bar goes under its minimum, because a row that kept its bar and dropped the
button would leave the pointer no route to its verbs at all. *(Was: Proposed — **found by the
maintainer, 2026-08-05**, narrowing the window.)*
**Owner:** Implementer
**Priority:** Medium — the bar is the row's only answer to *how far along is this*
**Phase:** Phase 3
**Depends on:** nothing. Related to `T-160`, which is the control colliding on the same line
**Relevant context:** `T-135`, `UX-005` §4, `T126-R2`, `ui/row_delegate.py` (`_verb_rects`,
`_paint_verbs`, `_paint_progress`)
**Affected surfaces:** `ui/row_delegate.py`
**Risk:** Low

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-163--the-verbs-hold-their-ground-until-the-progress-bar-has-none).

### T-166 — The group's verbs erase the line above them

**Status:** **Complete — 2026-08-05.** **The premise this was filed on turned out to be wrong in a
way that made the fix smaller, not larger.** The verbs and the format line do not share a line: the
verbs are drawn on the last line and `_paint_text` already gives it to them by dropping the
selector to one line above. It then *also* stopped the selector's width at the leftmost button — a
line below — so the same width was spent twice and the buttons advanced across a line they do not
occupy. The format line now runs the full body width whatever the verbs are doing.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-166--the-groups-verbs-erase-the-line-above-them).

### T-160 — The format control is drawn over the thumbnail on a narrow row

**Status:** **Complete — 2026-08-05.** The control narrows rather than clamping: it keeps
`MIN_TEXT_WIDTH` for the row's text, then narrows to `MIN_CONTROL_WIDTH`, and never crosses the
tile at any body width. **The promise chosen is stated: it shrinks, it is never withheld** —
withholding would leave no route to the format at all, since `EDIT_KEY` opens the editor in this
same rectangle. The paint, the click, the hover and the editor's geometry now resolve the body and
the tile through one place; they had disagreed about the indent, which cost nothing while every
rectangle was measured from the row's right edge and would have cost the first one measured from
its left. *(Was: Proposed — **found by the maintainer, 2026-08-05**, at the add dialog's default
size, and **confirmed on the queue row** the same day at a narrow window. `_control_rect` is
shared, so this is one defect on both surfaces rather than two.)*
**Phase 3**, and the sibling of `T-150`: that one is about the size the dialog *opens* at, this is
about what any row does at any narrow width, including one a user chooses.
**Owner:** Implementer
**Priority:** Medium-High — it is visible at the size the dialog opens at today, so every user sees
it before they see anything else
**Phase:** Phase 3
**Depends on:** nothing. Fixing `T-150` hides it at the default size without fixing it
**Relevant context:** `T-136`, `T118-R8`, `T118-R12`, `UX-004` §1, `ui/row_delegate.py`
(`_control_rect`, `_paint_tile`, `EDITOR_WIDTH`)
**Affected surfaces:** `ui/row_delegate.py`
**Risk:** Low

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-160--the-format-control-is-drawn-over-the-thumbnail-on-a-narrow-row).

### T-161 — The best thumbnail yt-dlp offers is sometimes one that does not exist

**Status:** **Complete — 2026-08-05.** The candidates are walked best-first and the first that answers is taken, in the worker process where network calls already live. **The maintainer chose *try candidates until one loads*** over a likelier-looking guess or an amendment to what `T-153` promises. They were told it would cost a schema change, because `thumbnail_url` is a persisted column in two tables — **it did not**: asking at probe time, where one address is chosen once, delivers the same guarantee without the candidate list ever needing to survive persistence. Reported rather than quietly banked, since the cost was part of what they were deciding on.
**Owner:** Implementer
**Priority:** Medium-High — every playlist on the site the project exists for draws a placeholder
**Phase:** **Phase 2**, reclassified by `P2EXIT-R12` as `T-153`'s unfinished half
**Depends on:** nothing
**Relevant context:** `T-153`, `T-137`, `T-119`, `UX-003`, `downloader/ytdlp_adapter.py`
(`_entry_thumbnail`), `ui/thumbnails.py` (`ThumbnailStore`)
**Affected surfaces:** `downloader/ytdlp_adapter.py`, `core/models.py` and `ui/thumbnails.py` if a
fallback needs more than one candidate carried
**Risk:** Medium — the honest fix changes what a `MediaInfo` carries

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-161--the-best-thumbnail-yt-dlp-offers-is-sometimes-one-that-does-not-exist).

### T-162 — A probed entry keeps saying "Probing" after its probe has finished

**Status:** **Complete — 2026-08-05.** A drawn stage now wins only when it could still be happening in the current status, from a table keyed by status. **Reclassified Phase 2 by `P2EXIT-R11`**, and the reviewer's reasoning is worth keeping: the closed-list rule governs which task owns a defect found by running the window, and cannot defer a failure of an *independent* Phase 2 criterion. This broke criterion 1's accurate-per-job-progress promise and `REQ-014`'s current-stage promise, so filing it as Phase 3 while calling criterion 1 met was a claim stated over the top of evidence already written down.
pasting a playlist. **Introduced by `ARC-009`**, which is mine: it created the state this exposes.
**Owner:** Implementer
**Priority:** **High** — every entry of every playlist misreports itself, and the row contradicts
its own chip while doing it
**Phase:** **Phase 2**, reclassified by `P2EXIT-R11`: a stale stage defeats criterion 1
**Depends on:** nothing
**Relevant context:** `ARC-009`, `T017-R3`, `UX-003`, `ui/queue_view.py` (`_status_text`,
`_Row.displayed`)
**Affected surfaces:** `ui/queue_view.py`
**Risk:** Low

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-162--a-probed-entry-keeps-saying-probing-after-its-probe-has-finished).

### T-165 — A cancelled playlist reports itself as failed, and draws a full bar

**Status:** **Complete — 2026-08-05.** Cancelled is its own `SegmentState`, the mapping is a
table over every status, and the three endings are three hues in both themes. **Fixed rather than
ruled on**: the header saying `16 failed` about downloads the user cancelled is a group summary
stating something untrue, and leaving that filed for a later phase to preserve a filing rule would
have been the rule outliving its purpose.
**Owner:** Implementer
**Priority:** Medium — the words are wrong, which is worse than the colour being unclear
**Phase:** Phase 2, alongside the criterion 8 findings
**Depends on:** nothing. `T-164` is adjacent — that one is the bar at narrow widths, this is what
the bar and the line say at any width
**Relevant context:** `UX-005` rows 9a-9b, `NFR-005`, `T-140` and its colour correction, `T130-R1`,
`ui/queue_view.py` (`_group_segments`, `DETAIL_ROLE`), `ui/row_delegate.py` (`SegmentState`)
**Affected surfaces:** `ui/queue_view.py`, `ui/row_delegate.py`
**Risk:** Low to fix, Medium to rule — a fifth `SegmentState` touches the accessible text too

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-165--a-cancelled-playlist-reports-itself-as-failed-and-draws-a-full-bar).

### T-152 — The declared keyboard route needs a mouse click before it works

**Status:** **Complete — 2026-08-05**, in two rounds. Round one gave both views a current row;
round two gave the visible view the **keyboard**, which is what `Shift+F10` is actually delivered
to. Measured before and after: `QSpinBox concurrencyChoice` → `QListView queueTable`.
**First round, complete:** both views take a current row on reset and at construction, through the
selection model with `NoUpdate` so it is current without being selected.
**Owner:** Implementer
**Priority:** **High** — `NFR-005` is a non-functional requirement, and this is the route it names
**Phase:** **Phase 2 — inside criterion 8**, by the maintainer's ruling of 2026-08-05. Accepted work that the built window does not deliver, which is what criterion 8 asserts
**Depends on:** nothing
**Relevant context:** `NFR-005`, `UX-005` §4, `T124-R1`, `T-135`, `ui/queue_view.py`
(`_row_menu_asked_for`), `ui/history_view.py`, `tests/ui/test_row_verb_wiring.py`
**Affected surfaces:** `ui/queue_view.py`, `ui/history_view.py`
**Risk:** Low

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-152--the-declared-keyboard-route-needs-a-mouse-click-before-it-works).

### T-149 — A paused queue looks exactly like a running one

**Status:** **Complete — 2026-08-05.** The style sheet declares `:checked`, so a paused queue is visibly paused. The border thickens as well as darkening, per `NFR-005`.
**Owner:** Implementer
**Priority:** **High** — `UX-001` makes pause the only queue-wide control there is, and a control
that cannot be read is one a user presses twice
**Phase:** **Phase 2 — inside criterion 8**, by the maintainer's ruling of 2026-08-05. Accepted work that the built window does not deliver, which is what criterion 8 asserts
regression that work introduced. The ruling is the maintainer's
**Depends on:** nothing
**Relevant context:** `UX-001`, `T-129`, `T-132`, `NFR-005`, `ui/theme.py` (the `QToolBar
QToolButton` rules), `ui/main_window.py` (`_pause_action`)
**Affected surfaces:** `ui/theme.py`, possibly `ui/main_window.py`
**Risk:** Low to fix, and the diagnosis is already done

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-149--a-paused-queue-looks-exactly-like-a-running-one).

### T-151 — The queue scrolls sideways, so a row's verbs are off screen and `⋯` never appears

**Status:** **Complete — 2026-08-05.** Both lists keep a row inside the viewport. Stated as a constraint rather than a diagnosis: `offscreen` never reproduced the scrollbar, so the mechanism is not asserted.
**Recommended as a finding against `T-135` rather than new scope — see below.**
**Owner:** Implementer
**Priority:** **High** — it makes two of criterion 8's own tasks unreachable in the shipped window
**Phase:** **Phase 2 — inside criterion 8**, by the maintainer's ruling of 2026-08-05. Accepted work that the built window does not deliver, which is what criterion 8 asserts
closed list held strictly
**Depends on:** nothing
**Relevant context:** `T-134`, `T-135`, `UX-005` §4, `NFR-005`, `ui/queue_view.py` (`data`,
`DisplayRole`), `ui/row_delegate.py` (`sizeHint`, `_verb_rects`), `ui/history_view.py`
**Affected surfaces:** `ui/queue_view.py`, `ui/history_view.py`, possibly `ui/row_delegate.py`
**Risk:** Low to fix; the diagnosis is done and the failure is entirely visible

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-151--the-queue-scrolls-sideways-so-a-rows-verbs-are-off-screen-and--never-appears).

### T-153 — A playlist's own picture is never read, only its entries'

**Status:** **Complete — 2026-08-05.** A playlist reads its own picture through `_entry_thumbnail`, the helper its entries already use.
**Owner:** Implementer
**Priority:** Medium — cosmetic in the queue, but it is the first thing a user sees after pasting
**Phase:** **Phase 2 — inside criterion 8**, by the maintainer's ruling of 2026-08-05. Accepted work that the built window does not deliver, which is what criterion 8 asserts
**Depends on:** nothing
**Relevant context:** `T-137` and its 2026-08-04 correction, `UX-003`, `REQ-002`,
`downloader/ytdlp_adapter.py` (`_media_from`, `_entry_thumbnail`)
**Affected surfaces:** `downloader/ytdlp_adapter.py`
**Risk:** Low — the helper it needs already exists and is already tested

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-153--a-playlists-own-picture-is-never-read-only-its-entries).

### T-154 — A child row's picture is drawn at full size and covers its own text

**Status:** **Complete — 2026-08-05.** A picture is fitted to its slot before centring. Its regression does not kill the mutant at a device pixel ratio of 1, and says so.
**Recommended as a finding against `T-140`** (`UX-005` row 9c).
**Owner:** Implementer
**Priority:** **High** — it makes an opened playlist's entries hard to read, which is the shape's
whole purpose
**Phase:** **Phase 2 — inside criterion 8**, by the maintainer's ruling of 2026-08-05. Accepted work that the built window does not deliver, which is what criterion 8 asserts
**Depends on:** nothing
**Relevant context:** `UX-005` row 9c, `T-140`, `T-119`, `ui/row_delegate.py` (`_paint_tile`),
`ui/thumbnails.py` (`ThumbnailStore`)
**Affected surfaces:** `ui/row_delegate.py`, possibly `ui/thumbnails.py`
**Risk:** Low

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-154--a-child-rows-picture-is-drawn-at-full-size-and-covers-its-own-text).

### T-155 — The playlist bar's blocks merge at most widths

**Status:** **Complete — 2026-08-05.** Each block's right edge comes from the next block's left, so cumulative rounding cannot merge them. Swept across six widths.
**Owner:** Implementer
**Priority:** Medium — the bar is the group's only per-entry progress, and merged blocks under-report
**Phase:** **Phase 2 — inside criterion 8**, by the maintainer's ruling of 2026-08-05. Accepted work that the built window does not deliver, which is what criterion 8 asserts
**Depends on:** nothing
**Relevant context:** `UX-005` row 9b, `T-140`, `ui/row_delegate.py` (`_paint_segments`)
**Affected surfaces:** `ui/row_delegate.py`
**Risk:** Low

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-155--the-playlist-bars-blocks-merge-at-most-widths).

### T-157 — A part-done playlist that is retargeted can no longer say what anything is

**Status:** **Complete — 2026-08-05.** A child states its format when it differs; the group's control reads `Mixed — N formats`. Built against `UX-005`'s amendment, recorded first.
**Owner:** Implementer
**Priority:** **High** — the download is correct; what the window says about it is not, and
`REQ-009` is about exactly that
**Phase:** **Phase 2 — inside criterion 8**, by the maintainer's ruling of 2026-08-05. Accepted work that the built window does not deliver, which is what criterion 8 asserts
**Depends on:** nothing
**Relevant context:** `UX-005` rows 9c and 13, `T140-R3`, `REQ-009`, `Job.RETARGETABLE`,
`ui/queue_view.py` (`_group_data`), `ui/row_delegate.py` (`CHILD_TEXT_LINES`)
**Affected surfaces:** `ui/queue_view.py`, `ui/row_delegate.py`, possibly `UX-005`
**Risk:** Medium — the fix is presentational, but which presentation is a `UX-005` question

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-157--a-part-done-playlist-that-is-retargeted-can-no-longer-say-what-anything-is).

### T-140 — The queue draws a playlist as a row that opens

**Status:** **Complete — approved at `431bb47`, 2026-08-05**, with a **second colour correction
on 2026-08-05** recorded below. Reopened by `T140-R5` for three accepted criteria it had not built;
all three landed, and `Pause all` is deferred to `REQ-017` by that day's amendment to `UX-005`.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-140--the-queue-draws-a-playlist-as-a-row-that-opens).

### T-148 — The soak does not record which tree it exercised

**Status:** **Complete — 2026-08-05.** Found while recording the first clean 60-run soak.
**Owner:** Implementer
**Priority:** Medium — it is the evidence for a phase-exit gate
**Phase:** Phase 3
**Depends on:** nothing
**Relevant context:** `OPS-007`, `T-128`, `docs/project/TESTING.md` §7, `tools/soak.sh`
**Affected surfaces:** `tools/soak.sh`
**Risk:** Low

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-148--the-soak-does-not-record-which-tree-it-exercised).

### T-147 — The primary action's hover ring reads as a smudge

**Status:** **Complete — 2026-08-05.** Reported by the maintainer while running the window.
**Owner:** Implementer
**Priority:** Low — presentation, on the application's most-used control
**Phase:** Phase 3
**Depends on:** nothing
**Relevant context:** `UX-005` row 6, `T130-R1`, `ui/theme.py`
**Affected surfaces:** `ui/theme.py`
**Risk:** Low

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-147--the-primary-actions-hover-ring-reads-as-a-smudge).

### T-141 — The concurrency control steps with buttons, not native arrows

**Status:** **Complete — 2026-08-04.** `−` and `+` are labelled buttons; the spin box draws no
arrows of its own.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-141--the-concurrency-control-steps-with-buttons-not-native-arrows).

### T-139 — The bitrate control stays live when bitrate does not apply

**Status:** **Complete — 2026-08-04, and the premise was wrong.** Measurement moved the finding.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-139--the-bitrate-control-stays-live-when-bitrate-does-not-apply).

### T-136 — The staged row's format line runs underneath its format control

**Status:** **Complete — 2026-08-04.** The control moved; the selector kept its width.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-136--the-staged-rows-format-line-runs-underneath-its-format-control).

### T-138 — History rows lose the thumbnail the queue row had

**Status:** **Complete — 2026-08-04.** A finished download keeps the picture it had in the queue.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-138--history-rows-lose-the-thumbnail-the-queue-row-had).

### T-137 — A playlist downloads one item, silently, and reports nothing about it

**Status:** **Complete — 2026-08-04.** A playlist now enumerates, every entry becomes a queue job,
and they land together in a folder named for the playlist.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-137--a-playlist-downloads-one-item-silently-and-reports-nothing-about-it).

### T-132 — The toolbar is not the mockup's toolbar: no primary button, no alignment

**Status:** **Complete — 2026-08-04, committed at `7311180`.** Adopted as `UX-005` rows 6 and 7, then corrected the same day after the maintainer saw the toolbar's tint stop at the buttons.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-132--the-toolbar-is-not-the-mockups-toolbar-no-primary-button-no-alignment).

### T-133 — The concurrency spin box has no arrows

**Status:** **Complete — 2026-08-04, committed at `7311180`.** Corrected once: the first fix drew blocks, not arrows.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-133--the-concurrency-spin-box-has-no-arrows).

### T-134 — The row's verb buttons do not respond to the pointer

**Status:** **Complete — 2026-08-04, committed at `7311180`.**

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-134--the-rows-verb-buttons-do-not-respond-to-the-pointer).

### T-135 — The row's overflow menu repeats the buttons already on the row

**Status:** **Complete — 2026-08-04, committed at `7311180`.** Adopted as `UX-005` row 8.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-135--the-rows-overflow-menu-repeats-the-buttons-already-on-the-row).

### T-130 — The shipped window diverges from the mockup that was chosen

**Status:** **Complete — corrected 2026-08-04, awaiting re-review.** Three findings, all closed.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-130--the-shipped-window-diverges-from-the-mockup-that-was-chosen).

### T-131 — The launch test used the developer's real database, log and instance lock

**Status:** **Complete — corrected 2026-08-04, awaiting review.** Found while validating `T-129`:
two launch tests failed, and the cause was neither the change under test nor the machine.
**Owner:** Implementer
**Priority:** **High** — it is a test-isolation defect that makes the suite red for a reason
unrelated to whatever is being validated, and it writes to the developer's own files
**Phase:** Phase 2 test infrastructure
**Relevant context:** `T-087` (the single-instance lock), `NFR-004`, `docs/project/TESTING.md` §4,
`ARCHITECTURE.md` §5
**Affected surfaces:** `tests/ui/test_app_launch.py`
**Risk:** None to the product — no `src/` change

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-131--the-launch-test-used-the-developers-real-database-log-and-instance-lock).

### T-129 — The style sheet took the native style's metrics and states away

**Status:** **Complete — corrected 2026-08-04, awaiting review.** Found by opening the
application, not by any gate. Three rules added, three mutations killed.
**Owner:** Implementer
**Priority:** **High** — the add-URL dialog's group titles were unreadable, and every button and
menu item in the application was inert under the pointer. `NFR-005` is about being able to tell
what a control will do.
**Phase:** Phase 3 (`UX-005` follow-on), taken immediately because it is a defect rather than work
**Relevant context:** `T-120` (applied the palette), `UX-005`, `NFR-005`, `docs/project/TESTING.md` §13
**Affected surfaces:** `ui/theme.py`, `tests/ui/test_theme_metrics.py`
**Risk:** Low — additive style-sheet rules; no product logic changes

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-129--the-style-sheet-took-the-native-styles-metrics-and-states-away).

### T-128 — The result-pump segfault reproduces on **Linux**, at ~5% of full-suite runs

**Status:** **Complete — corrected twice on 2026-08-04, awaiting re-review.**
**`T128-R1` (Medium, blocking) — the detector was blind, and it was my bug.** Qt keeps exactly one
message handler; both Qt conftests install one, so in a full run the second replaced the first. But
`fail_on_orphaned_timers` gave **each call its own recorder** and `assert_no_orphaned_timers` read
`_orphaned[0]` — so the live handler wrote to a list nothing inspected, and the detector could not
produce the failure it exists to produce. *Corrected:* one flat module-level recorder, written by
whichever handler Qt currently holds and read by every assertion. Not made idempotent, deliberately:
a flag would have to survive `pytest-qt` replacing and restoring the handler around every test call,
and a shared recorder makes the question moot. Mutation: restoring the per-call recorders fails
the reviewer's regression.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-128--the-result-pump-segfault-reproduces-on-linux-at-5-of-full-suite-runs).

### T-125 — Remove downloads from the history

**Status:** **Complete — corrected 2026-08-04, awaiting re-review.** `DAT-005` is **Approved**; the review
found one High in the implementation and it is fixed.
**`T125-R1` (High).** `HistoryRepository.remove()` executed its `DELETE` with no transaction and no
commit. Every test read back through the *same* connection, which sees its own uncommitted work, so
the deletion looked durable and was not — the reviewer's probe reported `removed 1`,
`same_connection_has_row False`, `other_connection_has_row True`, `after_writer_close_has_row
True`. The running application has exactly that shape: the writer thread deletes on its own
connection (`ARC-005`) and `HistoryView` reads through the one `compose()` opened, so the user was
told a record was gone, the tab still showed it, and closing the application rolled the delete
back. Now committed with `with self._connection`, like every other write here (`NFR-003`), and
tested across the real writer/read boundary **and after the writer closes and the file is
reopened** — the three observations the probe made. Mutation: removing the `with` leaves the
same-connection read passing and fails the other two.
*(This read "Complete — 2026-08-04, awaiting review", then "Ready — `DAT-005` is Accepted, so the
blocker is gone".)*
*(This read "Proposed — needs a decision before it needs a button", 2026-08-03. Found by using the
application: there is no way to clear history at any layer.)*
**Owner:** Implementer
**Priority:** Medium — a record the user cannot remove is a privacy question as much as a feature
**Phase:** Phase 3
**Depends on:** **`DAT-005`, now Accepted.** `T-124` is not a dependency — the control's placement
is in `UX-005`, but what removal *means* was not, and that is what `DAT-005` settles: selected
entries only, no file ever touched, irreversible with a counted confirmation, `REQ-020` amended.
**Relevant context:** `REQ-020`, `REQ-021`, `REQ-026`, `DAT-001`, `UX-005`, `HistoryRepository`
**Affected surfaces:** `docs/project/DECISIONS.md`, `docs/project/REQUIREMENTS.md`, `persistence/repositories.py`,
`ui/`
**Risk:** **Medium** — the obvious implementation deletes the wrong thing

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-125--remove-downloads-from-the-history).

### T-126 — Change a queued job's format from the queue row

**Status:** **Complete — corrected three times on 2026-08-04, awaiting re-review.** The control appears
exactly on `Job.RETARGETABLE` rows, the choice goes through `manager.retarget()`, and the durable request is
what the test reads back. Two findings, one of them the batch's only Critical.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-126--change-a-queued-jobs-format-from-the-queue-row).

### T-124 — The main window becomes two tabs over one list (`UX-005`)

**Status:** **Complete — corrected 2026-08-04, awaiting re-review.** The tab widget, the removal of the
detail pane, every verb `UX-005` §4 names and `HistoryView` as a `row_delegate` list are
implemented, wired and mutation-checked. The review found four High findings; all four are fixed.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-124--the-main-window-becomes-two-tabs-over-one-list-ux-005).

### T-127 — The two phase-proof gates that pass without their subject (`P2EXIT-R1`, `P2EXIT-R2`)

**Status:** **Complete — Approved with follow-up, 2026-08-04** (Codex, over `47299aa`). Both gates
fail when their subject is removed, verified with the reviewer's own two mutations plus two more,
and re-verified independently by the reviewer: removing the watchdog leaves **3/3 workers alive**,
removing the three starts fails in **0.54 s**.
**Windows evidence has landed.** `8d1b01c` is green on all five jobs including `windows desktop`,
and it contains source head `47299aa` — so the corrected `R1` route has run on Linux and Windows,
which is the third acceptance criterion.
*(This said "**Windows evidence is pending**" after that run was green — `P2EXIT-R8`. It also read
"Proposed — blocking the Phase 2 exit" before the exit review's cold reconstruction found the two
gates, each with a mutation.)*
**Open follow-up:** `T127-R1` (Medium, non-blocking) — corrected 2026-08-04, see below.
**Owner:** Implementer
**Priority:** **High** — these are the named evidence for exit criteria 1 and 5, and neither
establishes its criterion
**Phase:** Phase 2
**Relevant context:** `T-088`, `P2EXIT-R1`, `P2EXIT-R2`, `docs/project/TESTING.md` §13, exit criteria 1 and 5
**Affected surfaces:** `tests/integration/test_phase_2_exit.py`,
`tests/integration/test_end_to_end.py` (the kill and reap helpers both gates share),
`tests/integration/test_composition.py`
**Risk:** Low to the product — **nothing here suggests a defect in the application.** Both are
tests that cannot fail for the reason they name.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-127--the-two-phase-proof-gates-that-pass-without-their-subject-p2exit-r1-p2exit-r2).

### T-122 — Replace the flaky paste-scaling ratio gate

**Status:** **Complete — corrected 2026-08-04, awaiting re-review.** The one-sample ratio is gone; the
decision is a pure function over interleaved repeated samples, and the function is what the
deterministic test exercises. The 500-row absolute budget and the structural control count are
untouched. `P2EXIT-R3` is **Resolved**; two findings from the 2026-08-04 review are fixed.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-122--replace-the-flaky-paste-scaling-ratio-gate).

### T-118 — The add dialog becomes a staging list

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t118-third-flap).

**Status:** **Complete — Approved with follow-ups at `53b07ec`**, 2026-08-03, after four rounds of
changes requested and four corrections. Exact-head run `30859578131` supplied the Windows evidence
the last gate needed: `STARBASE` passed the full suite and hosted `windows-latest` passed every
`T-118` correction test. **Two follow-ups carry forward, neither blocking:** `T118-R17` — the
paste-scaling ratio oracle rejects a transient host pause, owned by **`T-122`** before the Phase 2
exit review — and `COORD-R21`, the current-truth prose corrected in this commit.
*(This read "In Review — four rounds … Blocked only on exact-head Windows verification" until the
verdict, and "three rounds" before that.)*
**Resolved by the reviewer:** `T118-R1`…`R3`, `R6`, `R7`, `R8`, `R9`, `R10`, `R11`, `R12`,
`COORD-R18`, and the `e300b04` teardown fixes. `UX-004` closed `R5`. **Resolved in the third round:** `T118-R13`, `R15`, `R16`.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-118--the-add-dialog-becomes-a-staging-list).

### T-120 — The brand palette, applied

**Status:** **Complete — Approved at `44091a1`**, 2026-08-02. The canonical swatches have one
source, both themes are independently defined and applied through the palette plus inherited
selectors, and text and control contrast are measured exhaustively rather than asserted. The
reviewer added the missing all-`JobStatus` textual-name assertion and it passes.
*(**This entry did not exist until 2026-08-03** — `COORD-R15`. The task was filed, built, reviewed
and approved while this file, the canonical task ledger, never held a row for it. Three documents
described its outcome and the one that is authoritative for tasks did not.)*
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 3
**Depends on:** nothing
**Relevant context:** `UX-004`, `NFR-005` (contrast), `ui/theme.py`
**Affected surfaces:** `ui/theme.py`, and every widget that inherits from it
**Risk:** Low mechanically, and the residue is not mechanical

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-120--the-brand-palette-applied).

### T-119 — The queue row: thumbnail, title and progress in one delegate

**Status:** **Cancelled — subsumed into `T-118`**, 2026-08-03. Not abandoned: the maintainer ruled
that the delegate and `T-118`'s row anatomy are one piece of work, so `T-118` now carries this
task's scope, acceptance criteria and risks. Filed here rather than deleted because `T-118`,
`ARCHITECTURE.md` and this file's own history all reference the id.
*(This read "Proposed — UI rework decomposition, 2026-08-02".)*
**Owner:** Implementer
**Superseded by:** `T-118`
**Phase:** Phase 3

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-119--the-queue-row-thumbnail-title-and-progress-in-one-delegate).

### T-115 — Nothing drains the queue: jobs beyond the limit never start

**Status:** **Complete — Approved at `f6dd691`**, 2026-08-02, after `T115-R1` and `T115-R2`
were corrected; `COORD-R12` closed with them. Add admits a saved batch as one ordered decision
after every retarget settles, startup admits durable waiting intent after recovery, and the
Add-only and restart routes drain with no priming loop.
*(This read "In Review — `T115-R1` corrected 2026-08-02" until 2026-08-03, one review round
after the approval: `COORD-R15`.)* Review had returned **changes
requested**: the probed row was retargeted while every *later* queue position was admitted ahead
of it, so with a pool of one the second URL started and the head of the queue waited. Add now
takes **one admission decision** after the retarget settles, probed id first. Three further
mutations run on the correction; all three killed.
*(This read "In Review — complete 2026-08-01. Five mutations run; all five killed.")* The strict
`xfail` that carried this reported **`XPASS(strict)`** the moment the first fix landed — the gate
firing exactly as promised — and was then inverted.
*(This read "Proposed — found by `T-088` on 2026-08-01, by measurement".)*
**Owner:** Implementer
**Priority:** **High** — `REQ-012` is "a queue", and a queue that never starts is a list
**Phase:** Phase 2
**Depends on:** nothing. `T-078`'s pool is what would be driven; it is already approved
**Relevant context:** `REQ-012`, `REQ-001`, `T-078`, `T-016`, `UX-001`, `ARC-004`
**Affected surfaces:** `downloader/manager.py` or `app.py` — see *Where it belongs*
**Risk:** Low to fix, High to leave. The phase cannot honestly exit with it open

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-115--nothing-drains-the-queue-jobs-beyond-the-limit-never-start).

### T-117 — Persist the thumbnail URL so a queued row can show one

**Status:** **Complete — Approved at `af9bfa1`**, 2026-08-02, with `T117-R1` resolved at
`5351be7` — `ARCHITECTURE.md`'s canonical Job entity now names `thumbnail_url`. The
implementation approval was never contingent on it.
*(This read "In Review — complete 2026-08-02" until 2026-08-03, three review rounds after the
verdict: `COORD-R15`.)* Six mutations run; all six killed, two of them
against the migration itself. The frozen-fixture gate `T014-R4` left behind did its job: adding a
schema version fails the build until that version's bytes are captured, which is the only moment
they can be.
*(This read "Proposed — UI rework decomposition, 2026-08-02".)*
**Owner:** Implementer
**Priority:** Medium — small, and `T-118` and `T-119` both need it
**Phase:** Phase 3
**Depends on:** nothing
**Relevant context:** `REQ-002`, `DAT-001`, `core/models.py:314` (`MediaInfo.thumbnail_url`),
`persistence/migrations/`, `persistence/repositories.py`
**Affected surfaces:** `core/models.py`, `persistence/` (schema, migration, repository)
**Risk:** **Medium, and not for its size** — this is the **first migration after the initial
schema**. The machinery has never run a second one against a database with rows in it

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-117--persist-the-thumbnail-url-so-a-queued-row-can-show-one).

### T-116 — A metadata lane: probing stops competing with downloads

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t083-retry-race).

**Status:** **Complete — Approved at `253bbce`**, 2026-08-03, after `T116-R1` was corrected.
One job cannot occupy both lanes: direct start refuses, admission parks, the fill loop skips a held
id, and release re-decides immediately — while different jobs still use the two lanes concurrently.
*(This read "In Review — complete 2026-08-02.")* Six mutations run; all six killed. One of them
found a test of mine passing for the wrong reason: it admitted a probe while the manager was
running, which starts it directly and never reaches the fill loop the test's own name is about.
*(This read "Proposed — UI rework decomposition, 2026-08-02".)* Precedes `T-118`, which is
unusable without it.
**Owner:** Implementer
**Priority:** **High** — `UX-003` makes probing mandatory, and mandatory probing through the
download pool stalls downloads that are already running
**Phase:** Phase 3
**Depends on:** nothing. `T-078`'s pool is what changes; it is approved
**Relevant context:** `UX-003`, `REQ-013`, `NFR-001`, `ARC-002`, `T-078`, `T-115`,
`downloader/manager.py` (`_has_capacity`, `SessionKind`)
**Affected surfaces:** `downloader/manager.py`, `core/settings.py`
**Risk:** Medium — it changes the admission rule the phase's own proof measures

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-116--a-metadata-lane-probing-stops-competing-with-downloads).

### T-088 — Prove the phase: three at once, killed mid-queue, nothing left behind

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t084-platform-checks).

**Status:** **Complete — Approved at `9e133a6`**, 2026-08-02, after `T088-R4` and `T087-R6`
were corrected. Five criteria proved against a real composed application in another interpreter;
the corrected suite passed on hosted Windows and Ubuntu. **It found a High defect that no feature
task would have surfaced — `T-115`, the queue does not drain** — and the evidence table carries a
seventh row for it.
*(This read "In Review — complete 2026-08-01. Four mutations run, all four killed.")*
*(This read "Proposed — the Phase 2 analogue of `T-037`".)*
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 2
**Depends on:** `T-078`…`T-087`
**Relevant context:** `T-037`, `T-019`, `T-073`, `NFR-001`, `docs/project/TESTING.md` §13
**Affected surfaces:** `tests/integration/`
**Risk:** High to omit — it is the phase's exit criteria in executable form

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-088--prove-the-phase-three-at-once-killed-mid-queue-nothing-left-behind).

### T-086 — Open a completed file, or reveal it in the file manager

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t084-platform-checks).

**Status:** **Complete — implemented at `233c5fd`, approved at `2a41c5f`**, 2026-08-01, after `T086-R1` (High) was corrected. Windows Open no longer
runs the file manager; it takes the associated-application route the platform documents.
*(This read "In Review — complete 2026-08-01. Sixteen mutations run; all sixteen killed.")* Two
survived the first pass: one was a defective mutation, and one was a **real gap** — nothing asserted
that Show-in-folder built the *reveal* argv rather than the open one, so both actions wired to
`open_file` passed every test in the file. `test_reveal_asks_the_file_manager_to_show_the_file_...`
closes it. **This is the last Phase 2 feature deliverable**; only `T-088` remains.
*(This read "Proposed", held by `T-100`, which landed at `c242dd3`.)*
**Owner:** Implementer
**Priority:** Low
**Phase:** Phase 2
**Depends on:** **`T-100`** for the history half — the view this acts on, which `P2PLAN-R8`
found had no owner; `T-085` for the records beneath it. The queue half needs only `T-079`
**Relevant context:** `REQ-021`, `T-034`, `SEC-001`, `OPS-004`
**Affected surfaces:** `ui/`, a small platform seam
**Risk:** Medium despite being small — it hands a path to the operating system

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-086--open-a-completed-file-or-reveal-it-in-the-file-manager).

### T-084 — Per-job log capture and a log view

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t084-platform-checks).

**Status:** **Complete — implemented at `75f1c32`, approved at `2a41c5f`**, 2026-08-01, after `T084-R1` (Critical) and
`T084-R2` (High) were corrected.
Fourteen further mutations across the corrections; all fourteen killed. **The contradictory
acceptance criterion was amended by maintainer ruling on 2026-08-01 — `DAT-003` wins — and every
criterion is now met.**
*(This read "In Review — complete 2026-08-01. Nineteen mutations run; all nineteen killed.")*
Three survived the first pass and **two of the three were my tests' fault, not defective mutations**
— see *What the mutation battery found* below. `T-053`'s concurrent evidence, which this task's
last criterion requires before approval, was approved at `05e5312` earlier today.
*(This read "Ready — released 2026-07-30 by `T-078`'s approval at `0f9986f`. Reconciled against
`DAT-003` on 2026-07-31".)*
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 2
**Depends on:** `T-078`. **`T-053` is not a prerequisite — it is required for approval**, which is
the ordering `P2PLAN-R4` asked to be made explicit; the criteria below say so
**Relevant context:** `REQ-019`, `REQ-026`, **`DAT-003`** (the verbatim boundary, amended
2026-07-30 by `T-049`), `T-038`, `NFR-006`, `T-053`
**Affected surfaces:** `downloader/worker.py`, `logging`, `ui/`
**Risk:** Medium — redaction has to hold per job, under concurrency

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-084--per-job-log-capture-and-a-log-view).

### T-082 — Interrupted jobs are offered for retry at startup

**Status:** **Complete — Approved at `b1b7cd6`**, 2026-08-01, without follow-up. The review credits
it with recovering interrupted rows in one transaction, offering exactly those ids before ordinary
interaction, a safe default of *Not now*, and a Retry all that reuses the per-job retry path.
*(This read "In Review — complete 2026-08-01".)* Eight mutations run; all eight killed. Two
survived the first pass and **one of them found a claim the code had not earned** — see below.
*(This read "Ready — released 2026-07-30 by `T-078`'s approval at `0f9986f`".)*
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 2
**Depends on:** `T-078`
**Relevant context:** `REQ-012`, `T-037`, `T-014`
**Affected surfaces:** `app.py`, `persistence/`, `ui/`
**Risk:** Low — the recovery exists; the offer does not

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-082--interrupted-jobs-are-offered-for-retry-at-startup).

### T-100 — The history view: what was obtained, after the queue has forgotten it

**Status:** **Complete — Approved at `c242dd3`**, 2026-08-01, without follow-up. The review credits
it with a read-only, newest-first projection covering every `REQ-020` field including null output
paths, refreshing only after the committed success signal, and staying separate from clear-completed
persistence.
*(This read "In Review — complete 2026-08-01".)* Seven mutations run; all seven killed, including
the two this task names. **It releases `T-086`**, the last Phase 2 deliverable that had not started.
*(This read "Ready — nothing blocks it; `T-085` wrote the table it reads".)*

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-100--the-history-view-what-was-obtained-after-the-queue-has-forgotten-it).

### T-087 — Single-instance guard

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t046-ci-correction).

**Status:** **Complete — Approved at `ea9d752`**, 2026-08-01. **A test defect was corrected the same
day under `T087-R6`; the guard itself is unchanged and its approval stands.**

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-087--single-instance-guard).

### T-046 — Output path collision policy against the filesystem

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t046-ci-correction).

**Status:** **Complete — Approved at `9c5745a`**, 2026-08-01. All seven findings are **Resolved**:
`T046-R1` (Critical), `R2`, `R3`, `R4`, `R5`, plus the coordination `R6` and the evidence overclaim
`R7`. `T046-R1` was **Critical and real data loss**: the reservation covered the pre-postprocessor name, so an MP3 conversion wrote
over a file the user already had. Corrected below. Reservation is atomic (`O_CREAT | O_EXCL`),
because `ARC-002` makes the racing writers separate processes and a check-then-create between
them is the hole itself. Nine mutations run; all nine killed.
*(This read "Ready 2026-07-30. `T-034`, `T-045` and `T-013` are all Complete, and `T-078` makes
collisions reachable concurrently rather than one job at a time".)*
**Owner:** Implementer
**Priority:** Medium — **raise to High before first release.** Until this lands, two downloads
whose titles sanitize to the same component contend for one path
**Phase:** Phase 2
**Depends on:** `T-034`, `T-045`, and the download manager (`T-013`)
**Relevant context:** `DAT-002`; `ARCHITECTURE.md` §8; `REQ-011`
**Affected surfaces:** the download manager's path selection; `core/paths.py` remains pure
**Risk:** Medium — the failure mode is one download overwriting another's output

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-046--output-path-collision-policy-against-the-filesystem).

### T-081 — Reorder pending jobs, and clear completed ones

**Status:** **Complete — Approved at `eb1bd70`**, 2026-08-01. All four findings are **Resolved**.
Reorder settlement preserves the admitted set and uses the new durable positions only to order it;
dormant recovered rows stay dormant.
*(Its history is worth keeping: `T081-R1` — the barrier missing from the public `start()` — stayed
open through the first correction, and `T081-R4` was a defect that correction *introduced*, by
inventing an admission rule to satisfy a reviewer assertion that was later withdrawn.)*
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 2
**Depends on:** `T-078`, `T-079`
**Relevant context:** `REQ-016`, `ARC-005`, `persistence/repositories.py`
**Affected surfaces:** `persistence/`, `ui/`
**Risk:** Low to medium — reordering is a write pattern the writer thread has not seen

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-081--reorder-pending-jobs-and-clear-completed-ones).

### T-083 — Bounded retry with backoff, for network failures only

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t083-retry-race).

**Status:** **Complete — Approved at `97f96c0`**, 2026-08-01, and the approval stands. `T083-R1`
is **Resolved** on the immediate, deferred/full-pool, PROBE and DOWNLOAD paths. It held only
`job_id -> deadline`, so the tick had nothing to say *what* to restart and `start`'s default turned
a failed metadata **probe** into a `DOWNLOAD` — a transient preview failure began writing media
nobody had confirmed.
**Carrying one open, non-blocking finding: `T083-R2`** (2026-08-03) — a test-only headroom defect,
recorded below. The production retry path is not implicated.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-083--bounded-retry-with-backoff-for-network-failures-only).

### T-102 — A settings file that cannot be read says so, instead of reverting in silence

**Status:** **Complete — Approved at `97f96c0`**, 2026-08-01. `T102-R1` is **Resolved**: both
non-UTF-8 shapes return defaults plus a precise problem. It had escaped as `UnicodeDecodeError` and aborted composition, breaking both `ARC-008` and the
never-raises contract. Filed 2026-07-31 by `ARC-008`, which decided the
question `T-078` deferred and `TASKS.md` carried as the last open one. **Eight mutations run; all
eight killed.**
*(This read "Ready — filed 2026-07-31 by `ARC-008` … Nothing blocks it".)*
**Owner:** Implementer
**Priority:** Medium — the failure it addresses is silent, which is why it has waited; nobody is
blocked on it
**Phase:** Phase 2
**Depends on:** `T-078` (Complete — it wrote `core/settings.py` and the main-window control)
**Relevant context:** **`ARC-008`** (the decision, its exact reporting boundary, and the two edges
deliberately left silent), `ARC-007`, `DAT-001`, `AGENTS.md` §7 layering, `core/settings.py`,
`app.py`'s composition, `ui/main_window.py`
**Affected surfaces:** `core/settings.py`, `app.py`, `ui/`
**Risk:** Low — the fallback behaviour does not change; what changes is that it is announced

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-102--a-settings-file-that-cannot-be-read-says-so-instead-of-reverting-in-silence).

### T-053 — Prove concurrent per-job log isolation

**Status:** **Complete — Approved at `05e5312`**, 2026-08-01. Two real spawned workers, both
live before either emits, interleaved through the production log queue. Four mutations run; all
four killed. The review credits it with establishing overlapping live workers, deliberate
interleaving, per-job isolation, shared-log delivery and rejection of unstamped records.
**`T-084` cannot be approved without this**, recorded there as a criterion on 2026-07-31
(`P2PLAN-R4`).
*(This read "Ready — the pool now permits two live sessions (`T-078`, approved 2026-07-30 at
`0f9986f`)".)*
**Owner:** Implementer
**Priority:** Low — Phase 1's structural routing is correct; concurrency is the missing proof.
*Low is about this task's own risk, not its urgency:* it now gates another task's approval
**Phase:** Phase 2
**Depends on:** `T-038` and **`T-078`**, which is the task that implemented `REQ-013` — named now
that it exists, rather than described
**Relevant context:** `T038-R2`; `ARCHITECTURE.md` §8; `REQ-013`, `REQ-019`;
`docs/project/REVIEWS.md` (2026-07-27 T-019/T-038 focused correction re-review)
**Affected surfaces:** `tests/integration/test_worker_logging.py`
**Risk:** Low until concurrency exists; High if the pool ships without the proof
**Review base:** the Phase 2 concurrency implementation head

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-053--prove-concurrent-per-job-log-isolation).

### T-099 — Make the manager-boundary gate say which boundary failed

**Status:** **Complete — Approved at `05e5312`**, 2026-08-01. The reviewer added a gate on the
real failing assertion rather than only the explanation helper. Each prohibition is keyed to the
decision behind it, and a failure reports one line per rule actually broken. A fourth test asserts every
live prohibition has an explanation, so a rule added without one reads as unexplained rather than
silently inheriting the first one listed.
*(This read "Proposed".)*
**Owner:** Implementer
**Priority:** Low — enforcement is correct; the failure points at the wrong rule
**Phase:** Phase 2 test infrastructure; blocks nothing
**Depends on:** none
**Relevant context:** `T097-R2`, `T-097`, `ARC-007`, `T-013`
**Affected surfaces:** `tests/unit/test_manager_boundaries.py`
**Risk:** Low — a future settings violation is caught, but its diagnostic sends the maintainer to
the repository-injection rule instead of ARC-007

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-099--make-the-manager-boundary-gate-say-which-boundary-failed).

### T-101 — Gate the detail view's retry ETA reset independently

**Status:** **Complete — Approved at `05e5312`**, 2026-08-01. `T079-R3` is closed. The scenario
proves a non-default ETA was
drawn before asserting the reset — without which the assertion passes on a label that was never
written — and asserts `etaValue` separately from `speedValue`. Its own criterion is met: deleting
only `_eta.setText(UNKNOWN_TEXT)` makes the unmodified test fail, verified.
*(This read "Proposed".)*
**Owner:** Implementer
**Priority:** Low — the production reset is correct; one sibling label is not independently gated
**Phase:** Phase 2 test infrastructure; blocks nothing
**Depends on:** none
**Relevant context:** `T079-R3`, `T079-R1`, `T-079`, `docs/project/TESTING.md` §13
**Affected surfaces:** `tests/ui/test_job_detail.py`
**Risk:** Low — a future one-line regression can leave an obsolete ETA on a re-queued detail view

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-101--gate-the-detail-views-retry-eta-reset-independently).

### T-103 — Cancelling a waiting job leaves its id on the pool's waiting list

**Status:** **Complete — Approved at `05e5312`**, 2026-08-01. Found by `T-081` on 2026-07-31 and filed rather
than fixed inline (`AGENTS.md` §7); taken now on the maintainer's explicit instruction, knowing it
edits `cancel()` inside a diff already with the reviewer. **`T-081`'s sweep is removed**, per this
task's own fourth criterion. Three mutations run; all three killed.
*(This read "Proposed — found by `T-081` on 2026-07-31 …".)*
**Owner:** Implementer
**Priority:** Low — no observed user-visible failure. It is filed because the *reason* it is
harmless changed, not because it started misbehaving
**Phase:** Phase 2
**Depends on:** nothing. `T-078` created the waiting list; `T-080` and `T-081` both walk past this
**Relevant context:** `downloader/manager.py` — `cancel`, `_discard_waiting`, `_fill_free_slots`,
`_start_or_report`; `T-078`; `T036-R1`
**Affected surfaces:** `downloader/manager.py`
**Risk:** Low

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-103--cancelling-a-waiting-job-leaves-its-id-on-the-pools-waiting-list).

### T-080 — Queue-level pause and resume; per-job cancel, retry and remove

**Status:** **Complete — Approved at `05e5312`**, 2026-08-01. `T080-R1`, `T080-R2` and `T080-R3`
are all **Resolved**. Approved independently of `T-081`: the surviving barrier hole violated
reordered DOWNLOAD admission, not pause semantics. Released by `T-079`'s approval at `da49a51`;
rewritten from `UX-001` on 2026-07-30 (`P2PLAN-R1`). **Both maintainer calls were taken 2026-07-31**
and are recorded in place below: the unreachable `PAUSED` edges are **removed**, and `P2PLAN-R7`'s
manual-retry ordering is **confirmed** — as a maintainer decision, not as something `P2PLAN-R1`
settled. **Fourteen mutations run; all fourteen killed**, nine against the queue and persistence
layers and five against the controls. One of the fourteen **survived its first run** and the test
was wrong, not the code — see the mutation table.
*(This read "Proposed — … **Not released by `T-078`:** it waits on `T-079` as well", then "Ready …
two maintainer calls are still open", then "Ready and startable".)*
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 2
**Depends on:** `T-078`, `T-079`
**Relevant context:** **`UX-001`** (the canonical pause and remove semantics, with rationale and
reopening condition), `REQ-015` **as amended**, `T-051`, `core/job_state.py`, `T036-R1`
**Affected surfaces:** `downloader/manager.py`, `ui/`, possibly `core/job_state.py` (the `PAUSED`
edges — see below)
**Risk:** Medium — every one of these is a state transition plus an effect, which is `T036-R1`

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-080--queue-level-pause-and-resume-per-job-cancel-retry-and-remove).

### T-079 — The queue view: many jobs, each with its own progress

**Status:** **Complete — Approved at `da49a51`**, 2026-07-31. Changes were requested at `cb008da`
on two blocking Medium findings; the focused correction re-review of `cb008da..da49a51` records
both **Resolved** and carries `T079-R3` (Low) as non-blocking, owned by `T-101`. `ui/queue_view.py`
stops being a stub: a `QAbstractTableModel` over every job, a `QTableView` above the detail pane in
a splitter, and one coalescing timer for the whole table. **Twenty mutations across two rounds; all
twenty killed.** **This releases `T-080` and `T-081`**, which waited on this task and not on the
pool.
*(This read "Ready — released 2026-07-30 by `T-078`'s approval at `0f9986f`", then "In Review —
complete 2026-07-31", then "In Review — corrected 2026-07-31, awaiting re-review" — the last of
those was still standing after the re-review had recorded **Approved**. The verdict was written to
`docs/project/REVIEWS.md` in `19f6015`, one commit after `da49a51` last rewrote this line, so the two never
met. `T-096` cannot see this class: the status and the section agreed with each other and both
disagreed with `REVIEWS.md`, which is `COORD-R11` across files rather than within one.)*
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 2
**Depends on:** `T-078`
**Relevant context:** `REQ-015`, `NFR-001`, `T-017`, `T-059`, `T040-R1`
**Affected surfaces:** `ui/`, `main_window.py`
**Risk:** Medium — the repaint discipline that made one job cheap is what N jobs will test

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-079--the-queue-view-many-jobs-each-with-its-own-progress).

### T-078 — A real worker pool, bounded and configurable

**Status:** **Complete — Approved at `0f9986f`**, 2026-07-30. `T078-R1` and `T078-R2` are
**Resolved**, and every original mutation is now killed. Three parts across four commits:
`ARC-007`'s settings layer (`256b411`, `faf374f`), the pool (`a642482`), the main-window control
(`1ef59f1`), and the correction (`0f9986f`). **This releases the subtree** — `T-079`, `T-082`,
`T-083`, `T-084`, `T-053` and `T-046` are Ready; `T-080` and `T-081` descend from it but wait on
`T-079` as well.
*(This read "Ready, promoted 2026-07-30", then "In Progress — the pool is generalised and gated",
then "In Review — complete 2026-07-30", then "In Review — corrected, awaiting re-review".)*

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-078--a-real-worker-pool-bounded-and-configurable).

### T-089 — Gate the MP3 bitrate control's complete UI contract

**Status:** **Complete — Approved at `128be39`**, 2026-07-30. The mutation fails exactly the
intended FLAC test. All four criteria met; the FLAC preset had to be injected, because no built-in is
a *converting non-MP3* one — which is why the gap existed.
**Owner:** Implementer
**Priority:** Low
**Phase:** Phase 1 follow-up; does not block T-076 approval
**Depends on:** `T-076`
**Relevant context:** `T076-R1`, `T076-R2`, `REQ-009`, `REQ-010`
**Affected surfaces:** `tests/ui/test_add_dialog.py`
**Risk:** Low — the behavior is correct; the missing evidence would let adjacent UI paths drift

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-089--gate-the-mp3-bitrate-controls-complete-ui-contract).

### T-047 — Decide whether the environment ownership gate's blind spots are worth closing

**Status:** **Complete — Approved at `321c672`**, 2026-07-30; `T047-R1` Resolved. The decision is
`OPS-008`. `T047-R1` was right
that a durable "no" belongs in `docs/project/DECISIONS.md` rather than only in this task and `docs/project/TESTING.md`:
a decision recorded in a mutable task is exactly what `AGENTS.md` §12 puts in `DECISIONS.md`, and
`P2PLAN-R2` made the same finding about Phase 2's three decisions a day earlier. **`OPS-008`** now
holds the decision, the measurement it rests on, its alternatives and its reopening conditions.
Nothing in `src/` or `tests/` changed, as the second acceptance criterion requires. `T-098` owns what
the measurement exposed.
*(This read "the decision is recorded below" — below being this task — until `T047-R1`.)*
**Owner:** Planner, then Implementer if the answer is yes
**Priority:** **Low, and deliberately so.** The question is whether to spend anything here at
all; the honest default answer is no
**Phase:** unassigned
**Depends on:** `T-044`
**Relevant context:** `T044-R1` and its six review rounds in `docs/project/REVIEWS.md`; `docs/project/TESTING.md`
("What the environment ownership gate actually promises"); `ARCHITECTURE.md` §6
**Affected surfaces:** `tests/unit/test_environment.py` only
**Risk:** Low — no production code is involved, and none ever was

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-047--decide-whether-the-environment-ownership-gates-blind-spots-are-worth-closing).

### T-097 — Gate ARC-007's settings-injection boundary

**Status:** **Complete — Approved at `34addcb`**, 2026-07-30; `T097-R1` Resolved. `T097-R2` — the
combined boundary diagnostic still names the persistence rule when it reports a settings offender —
is carried to **`T-099`** and blocks nothing. Two defects were corrected, both real:

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-097--gate-arc-007s-settings-injection-boundary).

### T-085 — History of completed downloads

**Status:** **Complete — Approved at `36bfba6`**, 2026-07-30. The projection/live split was
accepted; `P2PLAN-R8` was carried and blocks `T-086` readiness rather than this. All three
acceptance criteria are met. **One thing is deliberately not delivered and is not this task's to decide:** the Scope below
says "the record *and the view over it*", and the view has no owner anywhere — see
**`REQ-020`'s view is unowned** below.
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 2
**Depends on:** `T-050`
**Relevant context:** `REQ-020`, `T-014`, `T-050`, `DAT-001`
**Affected surfaces:** `persistence/`, `ui/`
**Risk:** Low to medium — it is the first table whose rows outlive the queue

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-085--history-of-completed-downloads).

### T-049 — Tighten DAT-003 before cookie-file support

**Status:** **Complete — Approved at `0027299`**, 2026-07-30. Appending an explicit amendment was
confirmed correct under §6. `DAT-003` now states its boundary as **provenance** and withdraws three
overstatements, two of which were measured false rather than merely unprovable. See
**Evidence, 2026-07-30**.
**Owner:** Planner
**Priority:** Medium before cookie-file support or first release
**Phase:** Phase 4. *(It is filed under `## Proposed — Phase 2` with the other Phase 1 carry-overs,
which the section note explains — the grouping is by where they were filed, not by phase.)*
**Depends on:** none
**Relevant context:** `DAT-003`, `REQ-026`, `T014-R1`, `T-038`
**Affected surfaces:** `docs/project/DECISIONS.md`, `docs/project/REQUIREMENTS.md`, `docs/project/TASKS.md`

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-049--tighten-dat-003-before-cookie-file-support).

### T-091 — Distinguish a closed log queue from a broken one

**Status:** **Complete — Approved at `25f7879`**, 2026-07-30, no follow-up. Two rounds. The first
narrowed the `OSError` arm and left the other two wide — the same defect one type over — and
delivered two of four acceptance criteria while reading as complete. `T091-R1` and `T091-R2` are
Resolved. See **Corrections, 2026-07-30**.
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 1 follow-up; does not block T-090 approval
**Depends on:** `T-090`
**Relevant context:** `T090-R1`, `T090-R2`, `T074-R3`, `T038-R2`
**Affected surfaces:** `core/logging.py`, `tests/unit/test_logging.py`
**Risk:** Medium — a rare queue transport fault can stop logging silently; one named regression
also no longer proves the ordering it describes

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-091--distinguish-a-closed-log-queue-from-a-broken-one).

### T-096 — Make task status and section placement mechanically agree

**Status:** **Complete — Approved at `25f7879`**, 2026-07-30, no follow-up. `T096-R1` is Resolved.
The first pass had the same hole it was written to close: a task with **no** status line was
invisible to all twelve tests, because every one walked entries that *had* a status, so deleting one
left the suite green. `status_line_counts()` walks the **headings** now, and a third test asserts
both parses see the same set. Six mutations killed.
**Owner:** Implementer
**Priority:** Low — current truth is reconciled; this prevents the seventh recurrence
**Phase:** Documentation infrastructure; blocks no product task or phase
**Depends on:** none
**Relevant context:** `COORD-R5` through `COORD-R10`; `AGENTS.md` §6; `docs/project/TASKS.md` status
vocabulary
**Affected surfaces:** a documentation-invariant test and, only as needed to make the invariant
explicit, `docs/project/TASKS.md`
**Risk:** Low to product behavior, persistent to coordination: six review rounds have found a task
whose status and containing section disagree

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-096--make-task-status-and-section-placement-mechanically-agree).

### T-098 — Guard the premise T-047's decision rests on

**Status:** **Complete — Approved at `5ab8f49`**, 2026-07-30, no follow-up. The reviewer accepted
the inverted module-scope check as load-bearing rather than a restatement of the three named
constructs. `tests/unit/test_environment_shape.py` parses `downloader/environment.py` for the
constructs the blind spots require, plus that positive check. Four mutations killed.
**Owner:** Implementer
**Priority:** Low — it protects a decision rather than a behaviour
**Phase:** unassigned, like `T-047`. Blocks nothing
**Depends on:** none
**Relevant context:** `T-047` (the decision and its measurement), `T044-R1` and its six rounds,
`docs/project/TESTING.md` ("What the environment ownership gate actually promises")
**Affected surfaces:** `tests/unit/test_environment.py` only
**Risk:** Low — no production code is involved

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-098--guard-the-premise-t-047s-decision-rests-on).

### T-050 — Write the history table

**Status:** **Complete — Approved at `6d14e78`**, 2026-07-30, with non-blocking follow-up
`T-096`. All four findings are Resolved. It took two correction rounds and the production code was
only wrong in the first: `f858da9` made completion one transaction and survived independent fault
injection, then `T093-R1` rejected the **gate** for being unable to fail. The literal
production-only split mutation now fails the unchanged atomicity test, which is the criterion.
*(This read "Changes requested — T093-R1" until that gate was rewritten.)*
*(This read "In Review — implemented" and claimed the row "is written from the manager through an
injected sink" — which was the defect. `T050-R1` found that the sink wrote in a **second**
transaction. Before that this read "Proposed — Ready now".)*

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-050--write-the-history-table).

### T-093 — Make completion and history one crash-atomic write

**Status:** **Complete — Approved at `6d14e78`**, 2026-07-30. `T093-R1` is Resolved: the literal
production-only split mutation fails the unchanged atomicity test. `T-096` carries the structural
follow-up — a documentation-invariant test, so the class stops depending on someone noticing.
The production fix was already right;
the *gate* was not, and that is what this correction replaces. The hard-exit test exited from the
settlement callback — after every statement in `complete_job` had run — so a split transaction
passed it and the mutation criterion was unmet. **The gate now injects the exit between the two
statements** (`repositories._write_history` becomes `os._exit`), and a bare split fails it with no
help from the mutation: `COMPLETED` with `history=None`, the state `T050-R1` reported. The
after-callback case is kept beside it, relabelled as the positive durability check it always was.
`T050-R2` and `T050-R3` remain Resolved. See **`T093-R1` — the gate that could not fail** below.
**Owner:** Implementer
**Priority:** **Critical** — a hard exit can leave a completed job with its required history row
silently and irrecoverably absent
**Phase:** Phase 2; blocks T-050 approval
**Depends on:** T-050 implementation head `f4384b0`
**Relevant context:** `REQ-012`, `REQ-020`, `ARC-005`, `T050-R1`, `T050-R2`, `T050-R3`
**Affected surfaces:** `downloader/manager.py`, `persistence/store.py`,
`persistence/repositories.py`, `persistence/writer.py`, composition and tests
**Risk:** Critical — this is durable-record loss in the exact unexpected-termination case the
SQLite design exists to survive

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-093--make-completion-and-history-one-crash-atomic-write).

### T-095 — Reconcile the post-exit and T-050 review queue

**Status:** **Complete — Approved at `6d14e78`**, 2026-07-30. `COORD-R10` is Resolved, and
`T-096` now owns making status and section agree mechanically rather than by inspection.
`COORD-R9`'s three named
contradictions are Resolved. `COORD-R10` then found the same class inside this task's own
correction, which is the part worth keeping: `T-093`, `T-094` and `T-095` each said In Review while
sitting physically under `## Ready`, and neither readiness summary named them. Now filed where their
statuses say — `T-093` and `T-095` In Review, approved `T-094` Complete — and both `TASKS.md`'s
start-here list and `STATUS.md`'s current-phase block account for all three.
**Owner:** Planner / Coordinator
**Priority:** Low
**Phase:** Phase 2 coordination
**Depends on:** the T-050 / P2PLAN-R2 review disposition
**Relevant context:** `COORD-R9`, the 2026-07-29 Phase 1 exit review
**Affected surfaces:** `docs/project/STATUS.md`, `docs/project/TASKS.md`
**Risk:** Low — current-truth navigation is contradictory, but product behavior is unaffected

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-095--reconcile-the-post-exit-and-t-050-review-queue).

### T-094 — Give ARC-006 an atomic Windows ownership primitive

**Status:** **Complete — Approved at `f858da9`**, 2026-07-29. `P2PLAN-R5` is Resolved.
`ARC-006` carries an amendment withdrawing `QLocalServer` as the ownership primitive and replacing
it with an atomic kernel lock — `flock(LOCK_EX | LOCK_NB)` on POSIX, exclusive-access open on
Windows — keeping `QLocalServer` only as the attach channel. The header's "Discharges `A-004`" is
corrected to "Addresses"; `A-004` stays unverified until `T-087` lands. `T-087` gained a
**simultaneous-start** acceptance criterion, which is the case the withdrawn design passes
sequentially and fails. COORD-R10 owns moving this entry out of `## Ready` with the rest of the
correction queue.
**Owner:** Planner
**Priority:** **High** — the chosen guard permits the two-writer state it exists to prevent
**Phase:** Phase 2 planning; blocks `P2PLAN-R2` approval and T-087 readiness
**Depends on:** none
**Relevant context:** `ARC-006`, `A-004`, `ARC-005`, `T-087`, `P2PLAN-R5`
**Affected surfaces:** `docs/project/DECISIONS.md`, `docs/project/TASKS.md`
**Risk:** High — two processes can concurrently write the same queue database

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-094--give-arc-006-an-atomic-windows-ownership-primitive).

### T-090 — The log listener could be left reading a queue something else had closed

**Status:** **Complete — Approved with non-blocking follow-up `T-091`**, 2026-07-29 at `35fc7ec`.
Split out of `T-074` at `T074-R4`'s direction: it is a real defect found while investigating that
crash, and it is **not** that crash. The reviewer treated the split as giving this task its **own
initial comprehensive review budget**, since its acceptance criteria had never had an initial
review — while holding the inherited `T074-R2` and `T074-R3` to the High rule regardless. All
three inherited findings are independently **Resolved**; `T090-R1` (Medium) and `T090-R2` (Low)
are carried to `T-091` and block nothing.
**Owner:** Implementer
**Priority:** **High** — an unhandled fault in a daemon thread during interpreter teardown, and
silently lost log records
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `T-038`, `T038-R2`, `T-074`, `ARC-002`
**Affected surfaces:** `core/logging.py`, `tests/unit/test_logging.py`
**Risk:** Medium — it costs log records, and its failure mode is a thread exception with no
traceback, which reads as unexplainable

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-090--the-log-listener-could-be-left-reading-a-queue-something-else-had-closed).

### T-072 — Carry the three unresolved findings the last-pass direction stopped

**Status:** **Complete — Approved**, 2026-07-29. All five carries are discharged; `WIN-R1` was
verified on `STARBASE` against a deliberately broadened rule, and the reviewer accepted that the
precondition would have stopped the procedure had the broad state not really been created. See
**`WIN-R1` verified** below. *(This read "In Review — all five carries discharged" until the
approval was filed here; `COORD-R8`.)*

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-072--carry-the-three-unresolved-findings-the-last-pass-direction-stopped).

### T-073 — Run the full Windows gate on the machine that can run it

**Status:** **Complete — Approved**, 2026-07-29 at `c41e2ef`. `T073-R1`, the documentation
follow-up, was independently **Resolved** at `9802a6a`, and no later evidence reopens it.
*(This read "In Review — approved with a documentation follow-up" after both the approval and the
resolution had landed; `COORD-R8`.)*
The reviewer accepted the job shape: the real `windows` plugin for the 28-test desktop slice,
`offscreen` for the Qt baseline and the default suite, no provisioning of the self-hosted machine,
ffmpeg recorded, and 30 minutes allowed. All fourteen functional steps passed. `T073-R1` is the
open follow-up — two evidence statements in this task were wrong, corrected below.
**Owner:** Implementer
**Priority:** **High** — it is what makes Phase 1's seventh exit criterion attemptable again
**Phase:** Phase 1
**Depends on:** `OPS-005`; the self-hosted runner established 2026-07-28
**Relevant context:** `OPS-005`, `T-066`, `T-062`, `docs/project/TESTING.md` §12, `IMPLEMENTATION_PLAN.md`
Phase 1 exit criteria
**Affected surfaces:** `.github/workflows/ci.yml`, `docs/project/TESTING.md`
**Risk:** Medium — it puts the project's whole Windows gate on one machine

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-073--run-the-full-windows-gate-on-the-machine-that-can-run-it).

### T-075 — Probing freezes the preset, so the download ignores what the user chose

**Status:** **Complete — Approved**, 2026-07-29. The original defect is fixed, and so is
`T075-R1` — the review found the fix's own shortcut could start a download against a revision that
never landed. See **Evidence** and **`T075-R1`**.
**Owner:** Implementer
**Priority:** **Critical** — the application downloaded something other than what the user
selected, silently, while displaying the correct selector
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `REQ-009`, `REQ-012`, `T-016`, `T-051`, `ARC-004`, `ARC-005`, `T036-R1`
**Affected surfaces:** `ui/add_dialog.py`, `downloader/manager.py`, `core/models.py`,
`tests/ui/test_add_dialog.py`
**Risk:** Was High to leave — it is the product's central promise, and nothing failed loudly

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-075--probing-freezes-the-preset-so-the-download-ignores-what-the-user-chose).

### T-076 — Choose the MP3 bitrate, rather than taking the preset's 192

**Status:** **Complete — Approved with follow-up `T-089`**, 2026-07-29. A bitrate control beside
the preset — 320/256/192/160/128 kbps, defaulting to 192, offered **for MP3 specifically**.
`T076-R1` corrected the first version, which gated on "converts audio": every codec but the
original. See **Evidence**.
**Owner:** Implementer
**Priority:** Medium — `REQ-010` capability, pulled forward from Phase 3 at maintainer request
**Phase:** Phase 1 (pulled forward; `REQ-010` is a Phase 3 deliverable)
**Depends on:** `T-075`, which had to land first — a control added while the preset was frozen at
probe time would have inherited the freeze and read as doing nothing
**Relevant context:** `REQ-009`, `REQ-010`, `T015-R1`, `T-060`, `NFR-005`
**Affected surfaces:** `core/presets.py`, `ui/add_dialog.py`, `tests/ui/test_add_dialog.py`,
`tests/ui/test_windows_desktop.py`
**Risk:** Low — the model already carried `audio_quality`; this is a control, not new plumbing

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-076--choose-the-mp3-bitrate-rather-than-taking-the-presets-192).

### T-077 — Four of the five download options have never produced a file

**Status:** **Complete — Approved**, 2026-07-29. **All five presets execute.** The first version
covered three and recorded the other two as structural limits of network-free testing; `T077-R1`
established they were limits of the *direct-file* fixture, and an HLS fixture removes both. See
**Evidence** and **`T077-R1`**.
**Owner:** Implementer
**Priority:** **High** — these are the application's user-visible choices, and the only one ever
executed end to end is the one the tests happen to pin
**Phase:** Phase 1
**Depends on:** nothing. `T-075` is fixed, so a preset chosen in the dialog now reaches the request
**Relevant context:** `T-037`, `T-061`, `T-062`, `T-015`, `T-012`, `REQ-010`, `docs/project/TESTING.md` §13
**Affected surfaces:** `tests/integration/test_end_to_end.py`, `tests/capabilities.py`
**Risk:** Medium — the postprocessor path is unit-tested, so this is about whether it *works*,
not whether it is wired

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-077--four-of-the-five-download-options-have-never-produced-a-file).

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

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-064--repair-stale-developer-tool-launchers).

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
**Relevant context:** `T026-R3`, `OPS-004`, `NFR-005`, `docs/project/TESTING.md` §9 and §12
**Affected surfaces:** `tests/ui/test_windows_desktop.py`, `docs/project/TESTING.md` §12
**Risk:** Medium — the gap is easy to forget precisely because deferring it was correct

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-040--extend-the-windows-desktop-gate-to-widget-focus-order).

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
**Relevant context:** `T040-R1`; `T-040`; `T026-R3`; `NFR-005`; `docs/project/TESTING.md` §12 and §13
**Affected surfaces:** `tests/ui/test_windows_desktop.py`, `docs/project/TESTING.md` §12
**Risk:** Low to write, Medium to leave — a focus test that cannot reach a control it asserts on
is a red build for a wrong reason, and a green one would be worse

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-060--focus-chains-are-per-state-and-the-windows-mutations-still-owe-evidence).

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
**Affected surfaces:** `tests/unit/test_paths.py`, possibly `core/paths.py`, `docs/project/TESTING.md` §12
**Risk:** Medium — the failure mode is a download that cannot be written

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-067--path-behaviour-is-gated-only-with-long-paths-enabled-which-is-not-the-default).

### T-069 — An end-to-end recovery test is intermittent on Windows

**Status:** **Complete — approved**, 2026-07-28 at `8938478`. It was `T066-R1`: the Windows crash
test killed one process level, orphaning the worker, and the orphan is what broke the restart.
Fixed by reaping the tree; the failure rate went from **4 of 5 to 0 of 5**, reverting the fix
restores the rate, and five clean file-level runs followed. The helper-strengthening residue
belongs to `T-066`'s evidence contract and is carried to `T-072`.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-069--an-end-to-end-recovery-test-is-intermittent-on-windows).

### T-070 — The suite silently requires Windows privileges it never states

**Status:** **Complete — approved**, 2026-07-28 at `1e9694c`. No findings. The capability is
attempted in the test's own temporary directory, the skip tells a Windows developer which
privilege or setting is missing, and the four original tests are unchanged wherever the capability
exists. See **Evidence**.
**Owner:** Implementer
**Priority:** Medium — four tests failed on an ordinary desktop for a reason no message named
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `T-067`, `T-066`, `docs/WINDOWS_VERIFICATION.md`, `docs/project/TESTING.md` §12
**Affected surfaces:** `tests/capabilities.py`, `tests/conftest.py`, `tests/unit/test_paths.py`,
`tests/integration/test_worker.py`
**Risk:** Low to fix, Medium to leave — it reads as a broken checkout

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-070--the-suite-silently-requires-windows-privileges-it-never-states).

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

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-065--resolve-the-forbidden-ai-authorship-trailer).

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

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-071--the-icon-reads-as-undersized-beside-other-taskbar-icons).

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

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-061--the-ffmpeg-gate-reads-the-selector-not-the-format-that-was-chosen).

### T-063 — The virtualenv cannot run the application it installed

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t001-environment).

**Status:** **Complete — approved with follow-up**, 2026-07-28 at `11e1203`. `T063-R1` is carried
to `T-064`: 39 dependency-owned launchers still name the parent checkout's interpreter, so the
documented bare `mypy` and `pytest` fail, while module invocations work. Both entry points work without `PYTHONPATH`, and
the full suite passes without it. The procedure and the symptom are in `docs/DEVELOPMENT.md`. See
**Evidence**.
**Owner:** Implementer
**Priority:** Low — it blocks no gate, and it is the first thing a new checkout hits
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `ENV-R1`; `docs/project/STATUS.md`'s Environment baseline, "Repository path —
**Unsettled**"; `T-001` (the toolchain this is supposed to be)
**Affected surfaces:** `.venv/` is not tracked, so this is a documented procedure plus whatever
`docs/DEVELOPMENT.md` needs; possibly `docs/project/STATUS.md`'s Environment baseline row
**Risk:** Low to fix, and it is a standing tax on every session that does not know the workaround

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-063--the-virtualenv-cannot-run-the-application-it-installed).

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

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-016--add-url-dialog-with-probe-results).

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
**Relevant context:** `SEC-001`, `REQ-EXCL-001`, `NFR-008`, `docs/project/TESTING.md` §5 (fixtures and the
recorded-failure canaries) and §7 (DRM)
**Affected surfaces:** `downloader/ytdlp_adapter.py`, `tests/unit/test_ytdlp_adapter.py`, and the
canary test wherever the recorded-failure canaries live
**Risk:** Medium — it is the input to a non-negotiable product boundary

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-057--bind-drm-detection-to-yt-dlps-actual-contract).

### T-013 — Download manager and result pump

**Status:** **Complete — approved with follow-ups**, 2026-07-27. `T013-R1`, `T013-R2`, `T013-R3`
and `T013-R4` are all verified resolved; `T013-R3` took three passes and was closed by
**restructuring** the startup transaction rather than patching a third sibling of it, which is
the option the maintainer chose when authorizing the pass (`AGENTS.md` §9). `T013-R5` stays
non-blocking test hardening owned by `T-052`.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-013--download-manager-and-result-pump).

### T-015 — Built-in presets and selector translation

**Status:** **Complete — approved**, 2026-07-27. `T015-R1` and `T015-R2` are both verified
resolved; `T015-R2` was the High regression the first correction introduced, and closing it meant
removing the widened fallback rather than widening it once more.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-015--built-in-presets-and-selector-translation).

### T-018 — Recorded `info_dict` fixtures and projection tests

**Status:** **Complete — closed as Approved**, 2026-07-27 on the fifth correction.
`T018-R2` is verified resolved, closing `T012-R6`. `T018-R1` (Critical) survived three recogniser
corrections; the fourth made the allowlist the control, which the reviewer verified works. The
fifth removed the *secondary* record that came with it — `SEC-002` is **amended**: a schema
fingerprint copies mapping keys verbatim, and a mapping key is captured data. The reviewer
confirmed no privacy-boundary escape remains.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-018--recorded-info_dict-fixtures-and-projection-tests).

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

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-038--logging-with-handler-level-redaction).

### T-055 — Decide how the application writes to SQLite without blocking the GUI thread

**Status:** **Complete** — decided and recorded 2026-07-27 as `ARC-005`.
**Owner:** Planner
**Priority:** High — blocked `T-016`'s `T016-R3`
**Phase:** Phase 1
**Depends on:** `T-014`
**Relevant context:** `NFR-001`; `ARCHITECTURE.md` §3 and §8; `DAT-001`; `T016-R3`
**Affected surfaces:** `docs/project/DECISIONS.md`, `docs/project/ARCHITECTURE.md`; implementation is `T-016`'s
**Risk:** Medium — deciding persistence threading inside a widget would set application-wide
policy from the narrowest possible place
**Blocks:** `T-016`

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-055--decide-how-the-application-writes-to-sqlite-without-blocking-the-gui-thread).

### T-054 — File the approved Phase 1 tasks under `## Complete`

**Status:** **Complete — approved with follow-ups**, 2026-07-28 at `9c92c32`. Thirteen entries
moved, not three. `T054-R1` (Low, non-blocking) is corrected here: the permutation evidence now
names what it excluded, and the blank line at EOF is gone.
**Owner:** Planner
**Priority:** Low
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `AGENTS.md` §6 (`TASKS.md` is current truth), `docs/project/REVIEWS.md`
**Affected surfaces:** `docs/project/TASKS.md`
**Risk:** Low — no source or behavior changes

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-054--file-the-approved-phase-1-tasks-under--complete).

### T-051 — Define the READY-to-download lifecycle

**Status:** **Complete** — decided and recorded 2026-07-27 as `ARC-004`. No source changed.
**Owner:** Planner
**Priority:** High — blocks `T-016`'s probe-then-queue flow
**Phase:** Phase 1
**Depends on:** `T-013`
**Relevant context:** `ARCHITECTURE.md` §5; `REQ-002`, `REQ-015`; `T-016`
**Affected surfaces:** `docs/project/ARCHITECTURE.md`, `docs/project/DECISIONS.md` if the choice is durable,
`docs/project/TASKS.md` (`T-013`/`T-016` correction or implementation scope)
**Risk:** Medium — inventing an edge in the manager would make the executable state machine
and the approved architecture disagree
**Review base:** the corrected `T-013` head
**Blocks:** `T-016`

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-051--define-the-ready-to-download-lifecycle).

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
**Relevant context:** `docs/project/TESTING.md` §7 (Cancellation, Worker crash), `REQ-015`, `REQ-028`,
`NFR-003`, `OPS-003`, `OPS-004`
**Affected surfaces:** `downloader/manager.py` (**production**, see below),
`downloader/worker.py`, `tests/integration/`, `.github/workflows/ci.yml`
**Risk:** **High** — a download that keeps running and keeps writing after the user cancelled
it, on a path no current test can see
**Review base:** the `T-013` merge commit

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-019--kill-the-process-tree-and-prove-it-on-windows).

### T-014 — Persistence: schema, migrations, and the job repository

**Status:** **Complete — approved with follow-ups**, 2026-07-26 at `db14cc2`. Four review
rounds; `T014-R1` (Critical), `R2`, `R3`, `R4`, `R5` and `R7` all resolved, `R6` retracted by the
reviewer. Follow-ups: `T-048` (verify the first real data migration) and `T-049` (tighten
`DAT-003`'s explanatory guarantees before cookie-file support).

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-014--persistence-schema-migrations-and-the-job-repository).

### T-044 — Close the non-blocking T-035 review follow-ups

**Status:** **Complete — Approved with follow-ups**, 2026-07-26. The maintainer directed T-044
forward after the claims-only re-review: its deliberately narrow runtime promise is accepted,
the three pinned blind spots are owned by `T-047`, and no further T-044 review loop is
authorized. **No production code changed at any point across six rounds.**

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-044--close-the-non-blocking-t-035-review-follow-ups).

### T-045 — Defused reserved names can collide with a legal neighbour

**Status:** **Complete — approved with follow-ups**, 2026-07-26. `T045-R1`, `T045-R2` and
`T045-R3` all resolved and independently verified; none blocks. Four rounds, one accepted
decision (`DAT-002`), and **no production change at any point** — the digest implementation
merged as `c0f4881` stands untouched. The follow-up is `T-046`, which owns filesystem-aware
uniqueness and whose before-first-release assumption is recorded in both `DAT-002` and the task.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-045--defused-reserved-names-can-collide-with-a-legal-neighbour).

### T-012 — yt-dlp in a spawned worker

**Status:** **Complete** — Approved with follow-ups, 2026-07-26. Two review rounds; all five
blocking findings (`T012-R1`..`T012-R5`) independently verified resolved. `T012-R6` is a
non-blocking follow-up owned by `T-018`.
**What landed.** `downloader/ytdlp_adapter.py` (pure translation: exception classification,
`info_dict` projection, option building) and `downloader/worker.py` (spawn-safe entry, `OPS-002`
resolution, one outcome message then `WorkerFinished` in a `finally`). No raw `info_dict`
crosses the process boundary; `tests/unit/test_layering.py` still passes, so §6 holds.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-012--yt-dlp-in-a-spawned-worker).

### T-034 — Filename safety and output-path containment

**Status:** **Complete — approved with follow-ups**, 2026-07-26 at `313198d`.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-034--filename-safety-and-output-path-containment).

### T-035 — Resolve the yt-dlp and ffmpeg environment

**Status:** **Complete — approved with follow-ups**, 2026-07-26. Both functional blockers
(`T035-R1`, `T035-R2`) resolved and independently verified; the remaining Low findings are owned
by `T-044` and do not keep this task in review.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-035--resolve-the-yt-dlp-and-ffmpeg-environment).

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

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-042--make-the-model-audit-enforce-nullability-and-boolean-rejection).

### T-043 — Protect `protocol.py`'s remaining boolean guards

**Status:** **Complete — approved** 2026-07-26, mutation-verified independently.
**Owner:** Implementer
**Priority:** Low — production behavior is correct; the guards are simply untested
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `T041-R6`, `T042`, `T011-R2`
**Affected surfaces:** `tests/unit/test_protocol.py`
**Risk:** Low to fix; the risk it addresses is a **silent regression**

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-043--protect-protocolpys-remaining-boolean-guards).

### T-041 — Validate nested payloads in `core/models.py`

**Status:** **Complete — approved** at `0268e13`, 2026-07-26. All five findings independently
verified resolved; `T011-R8` functionally closed. CI run `30216176642` was verified green at that
exact head by the reviewer.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-041--validate-nested-payloads-in-coremodelspy).

### T-011 — IPC message contract

**Status:** **Complete** — every finding resolved, 2026-07-26.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-011--ipc-message-contract).

### T-010 — Domain models, job state machine, and error taxonomy

**Status:** **Complete — approved** on final re-review, 2026-07-26 (`docs/project/REVIEWS.md`). All four
findings resolved and verified by the reviewer. Unblocks `T-011`, `T-014`, `T-015`, `T-034`.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-010--domain-models-job-state-machine-and-error-taxonomy).

### T-026 — Verify Windows behavior against the runner's real desktop

**Status:** **Complete — third-round re-review waived by the maintainer**, 2026-07-26.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-026--verify-windows-behavior-against-the-runners-real-desktop).

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

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-027--reject-unsafe-stored-window-geometry).

### T-028 — Remove undocumented cross-thread Qt access from the launch test

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged via PR #7. `T005`-era findings and `P0-R2` … `P0-R5` were reviewer-verified; the corrections to `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **accepted by the maintainer without a final re-review**. Recorded rather than implied: those four are maintainer-accepted, not reviewer-verified.
**Owner:** Reviewer / Implementer
**Priority:** Medium
**Phase:** Phase 0 review correction
**Depends on:** `T-007`
**Relevant context:** Phase 0 finding `P0-R2`, `docs/project/REVIEWS.md` standing Qt-threading risk
**Affected surfaces:** `tests/ui/test_app_launch.py`
**Risk:** Low — this is test reliability, but it guards the phase's real startup path

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-028--remove-undocumented-cross-thread-qt-access-from-the-launch-test).

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

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-029--complete-the-frozen-probe-negative-and-evidence-gates).

### T-030 — Ratify the two Phase 0 architecture additions

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged via PR #7. `T005`-era findings and `P0-R2` … `P0-R5` were reviewer-verified; the corrections to `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **accepted by the maintainer without a final re-review**. Recorded rather than implied: those four are maintainer-accepted, not reviewer-verified.
**Owner:** Planner
**Priority:** Medium
**Phase:** Phase 0 review correction
**Depends on:** `T-007`, `T-020`
**Relevant context:** Phase 0 finding `P0-R6`, `ARCHITECTURE.md` §4 and §5
**Affected surfaces:** `docs/project/ARCHITECTURE.md`
**Risk:** Low — the implementations are reasonable; the canonical ownership map is incomplete

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-030--ratify-the-two-phase-0-architecture-additions).

### T-031 — Correct OPS-004 before deciding it

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged via PR #7. `T005`-era findings and `P0-R2` … `P0-R5` were reviewer-verified; the corrections to `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **accepted by the maintainer without a final re-review**. Recorded rather than implied: those four are maintainer-accepted, not reviewer-verified.
**Owner:** Planner / Maintainer + Reviewer (`docs/project/TESTING.md`)
**Priority:** High
**Phase:** Phase 0 review correction
**Depends on:** none
**Relevant context:** Phase 0 finding `P0-R7`, `OPS-003`, proposed `OPS-004`, `T-026`
**Affected surfaces:** `docs/project/DECISIONS.md`, `docs/project/TASKS.md` (`T-026`), `docs/project/TESTING.md`
**Risk:** Medium — an omitted verification category could disappear when the manual gate shrinks

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-031--correct-ops-004-before-deciding-it).

### T-032 — Reconcile Phase 0 current-truth documents

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged via PR #7. `T005`-era findings and `P0-R2` … `P0-R5` were reviewer-verified; the corrections to `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **accepted by the maintainer without a final re-review**. Recorded rather than implied: those four are maintainer-accepted, not reviewer-verified.
**Owner:** Planner + Reviewer (`docs/project/TESTING.md`)
**Priority:** Medium
**Phase:** Phase 0 review correction
**Depends on:** `T-027` through `T-031`
**Relevant context:** Phase 0 finding `P0-R8`, `AGENTS.md` §6
**Affected surfaces:** `docs/project/STATUS.md`, `docs/project/TASKS.md`, `docs/project/TESTING.md`
**Risk:** Low — stale navigation and exact counts misstate what is implemented and reviewed

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-032--reconcile-phase-0-current-truth-documents).

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

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-007--application-shell-window).

### T-020 — Frozen-build smoke test in CI

**Status:** Complete
**Completed:** 2026-07-25 — merged to `main` as part of `564aad0`; **no independent review**, pending the Phase 0 exit review
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 0
**Depends on:** `T-006`, `T-007`
**Relevant context:** `REL-001`, `REQ-029`, `ARC-002`, `ARCHITECTURE.md` §3 and §12, `docs/project/TESTING.md` §8
**Affected surfaces:** `__main__.py`, PyInstaller spec, CI workflow
**Risk:** **High** — the failure this guards against does not exist until the app is frozen, and
it is a recursive application launch, not a subtle misbehavior

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-020--frozen-build-smoke-test-in-ci).

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

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-025--phase-0-exit-preparation).

### T-005 — Layering enforcement test

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged as `d1f45e5` via PR #2
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 0
**Depends on:** `T-001`
**Relevant context:** `ARCHITECTURE.md` §4, `AGENTS.md` §7 (Layering), `docs/project/TESTING.md` §7
**Affected surfaces:** `tests/unit/test_layering.py`
**Risk:** Low — but its absence lets the central architectural rule erode invisibly

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-005--layering-enforcement-test).

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
**Relevant context:** `docs/project/REVIEWS.md` findings `T005-R1` through `T005-R3`;
`ARCHITECTURE.md` §4 and §6
**Affected surfaces:** `tests/unit/test_layering.py`, `docs/project/STATUS.md`
**Risk:** **High** — a green layering guard can be weakened around its sampled fixtures

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-024--close-t-005-review-findings).

### T-006 — CI on Linux and Windows

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged as `c8a72b8` via PR #1; CI green on `main`
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 0
**Depends on:** `T-001`
**Relevant context:** `docs/project/TESTING.md` §10, `REQUIREMENTS.md` §3, `C-003`, **`OPS-003`**
**Affected surfaces:** CI workflow config
**Risk:** **High** — per `OPS-003` this is the *only* Windows environment that exists. Anything
it does not check is genuinely unverified on Windows, not merely unautomated.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-006--ci-on-linux-and-windows).

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
**Relevant context:** `docs/project/REVIEWS.md` findings `T006-R1`, `T006-R2`; `OPS-003`
**Affected surfaces:** `.github/workflows/ci.yml`, `docs/project/TESTING.md`, `docs/project/TASKS.md`, `docs/project/STATUS.md`
**Risk:** Low — evidence completeness and current-truth accuracy

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-023--close-t-006-review-findings).

### T-022 — Close T-003 review findings

**Status:** Complete
**Completed:** 2026-07-25 — focused re-review approved; `T003-R1`, `T003-R2`, `T003-R3` all
Resolved, no new findings
**Owner:** Planner (documentation correction) + Implementer (resource test)
**Priority:** High
**Phase:** Phase 0
**Depends on:** `T-003`
**Relevant context:** `docs/project/REVIEWS.md` findings `T003-R1` through `T003-R3`
**Affected surfaces:** `docs/project/ARCHITECTURE.md` §8, the `T-003` completion note, resource tests
**Risk:** Low — documentation accuracy and regression coverage for a fixed asset set

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-022--close-t-003-review-findings).

### T-003 — Add the application icon asset

**Status:** Complete
**Completed:** 2026-07-25
**Owner:** Implementer (source asset supplied by Sean Kottman)
**Phase:** Phase 0
**Relevant context:** `T-007`, `ARCHITECTURE.md` §8

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-003--add-the-application-icon-asset).

### T-001 — Establish the project skeleton and toolchain

Historical evidence relocated 2026-09-08:
[Additional historical evidence](archive/TASKS-completed-2026-09-08.md#t001-environment).

**Status:** Complete
**Completed:** 2026-07-25
**Owner:** Implementer
**Phase:** Phase 0
**Relevant context:** `ARCHITECTURE.md` §4, `docs/project/TESTING.md` §4, `DOC-002`

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-001--establish-the-project-skeleton-and-toolchain).

### T-002 — Confirm the Python baseline against PySide6 wheel availability

**Status:** Complete — Linux at completion; Windows discharged by `T-006` on 2026-07-25
**Completed:** 2026-07-25
**Owner:** Implementer
**Phase:** Phase 0
**Relevant context:** `ARC-001`, `REL-001`

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-002--confirm-the-python-baseline-against-pyside6-wheel-availability).

### T-004 — Decide and record the project license

**Status:** Complete
**Completed:** 2026-07-25
**Owner:** Sean Kottman (maintainer decision)
**Phase:** Phase 0
**Relevant context:** `LIC-001`, `NFR-009`, `C-004`

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-004--decide-and-record-the-project-license).

### T-058 — Recount the DRM coverage record

**Status:** **Complete — approved**, 2026-07-28 at `b3e156c`. `T058-R1` is Resolved on the second
correction: `docs/project/TESTING.md` §12 is the sole numeric full-set coverage statement in the
current-truth documents. The finding continued once because the first correction cleaned
`docs/project/STATUS.md` and left two statements inside the file it had just declared the single home —
the search used to verify the claim matched only the phrasing it had removed. See **Evidence**.
**Owner:** Documentation Maintainer, with the Implementer for the mutation evidence
**Priority:** Medium — the exit review reads this record, and today it is wrong
**Phase:** Phase 1
**Depends on:** nothing. `T-057` and `T-017`'s DRM criterion are what the corrected record must
**name**, not what it must wait for
**Relevant context:** `docs/project/TESTING.md` §7, §12, §13; `docs/project/STATUS.md`; the `T-044`/`T-045` lesson
**Affected surfaces:** `docs/project/TESTING.md`, `docs/project/STATUS.md`
**Risk:** Low as a diff, Medium as a claim — this record is what the exit review trusts

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-058--recount-the-drm-coverage-record).

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
`NFR-003`; `docs/project/TESTING.md` §7 (Crash recovery)
**Affected surfaces:** `tests/integration/`
**Risk:** **High** — it is the evidence for the phase
**Review base:** the `T-036` merge commit

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-037--end-to-end-download-and-restart-proof).

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
**Relevant context:** `T017-R4`; `docs/project/REVIEWS.md` (fifth `T-017` re-review); `NFR-005`
**Affected surfaces:** `src/tracks_and_trails/ui/job_detail.py`, `tests/ui/test_job_detail.py`
**Risk:** Low to fix, Medium to leave — a screen reader and the visible byte line disagree

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-059--a-view-opened-onto-a-finished-job-renders-it-from-the-wrong-source).

### T-052 — Make the T-013 correction tests kill their claimed mutations

**Status:** **Complete — approved**, 2026-07-28 at `7d67e77`. `T013-R5` is Resolved. Both named
mutations are killed, and the route-before-validation one on **each** of the three routes the
criteria list. Half of this task turned out to be already done — see **Evidence**.
**Owner:** Implementer
**Priority:** Low
**Phase:** Phase 1
**Depends on:** `T-013`
**Relevant context:** `T013-R5`; `docs/project/TESTING.md` §13
**Affected surfaces:** `tests/integration/test_manager.py`
**Risk:** Low — production behavior is correct; the negative gate is weaker than its evidence
record claims

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-052--make-the-t-013-correction-tests-kill-their-claimed-mutations).

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

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-036--application-composition-and-wiring).

### T-017 — Single-job progress view with cancel

**Status:** **Complete — closed 2026-07-28 at maintainer instruction.** All five findings are
Resolved: `T017-R1`, `R2`, `R3` and `R5` across four correction batches in this task, and
**`T017-R4` by the Reviewer when approving `T-059` at `52f0aed`**, which is where it had been
carried.

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-017--single-job-progress-view-with-cancel).

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
**Relevant context:** `T-037`; `docs/project/TESTING.md` §6; the CI failure at `48dc6a0`
**Affected surfaces:** `.github/workflows/ci.yml`, `tests/integration/test_end_to_end.py`,
`tests/integration/test_composition.py`, `tests/ui/test_job_detail.py`
**Risk:** **High** — these tests *are* the phase's evidence, and they have never passed on CI

[Archived scope and completion evidence](archive/TASKS-completed-2026-09-08.md#t-062--the-end-to-end-tests-need-an-environment-ci-does-not-have-and-say-nothing-when-they-fail).
