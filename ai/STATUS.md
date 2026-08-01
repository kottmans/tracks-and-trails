# STATUS.md — Tracks & Trails

**Purpose:** Concise snapshot of where the project stands right now.
**Authority:** Canonical for current project state.
**Owner:** Planner / Implementer
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-08-01
**Last verified against repository:** 2026-08-01
**Update when:** A meaningful work session ends, a phase changes, a blocker appears or clears, or the next task changes.
**Does not contain:** Task detail (`TASKS.md`), review history (`REVIEWS.md`), decision rationale (`DECISIONS.md`).

---

**Current phase:** **Phase 2 — Queue and concurrency.** **Phase 1 formally exited 2026-07-29**;
Phase 0 exited 2026-07-26. All three Phase 2 planning gates are clear — `P2PLAN-R2` at `f858da9`,
`P2PLAN-R1` and `P2PLAN-R3` at `8306378`.

**Nothing is a choke point as of 2026-08-01.** `T-078` (the pool) was approved 2026-07-30 and
`T-079` (the queue view) 2026-07-31; nothing has waited on anything since. **Three tasks are Ready
and startable:** `T-082`, `T-084`, `T-100`, plus `T-074` and `T-092`, which block nothing.

**Ten tasks are in review**, eight of them delivered overnight on 2026-08-01 under standing
maintainer authorisation to work unattended: `T-080`, `T-081`, `T-102`, `T-087`, `T-103`, `T-099`,
`T-101`, joining `T-046`, `T-053` and `T-083`. Eight commits, each its own task, all pushed. **Full
Linux suite: 1726 passed / 11 skipped / 2 deselected.**

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

**CI is not running at all, and no document said so until now.** This is measured, not inferred
from a red badge:

- **The last fully green CI push run was 2026-07-28**, at head `11e1203`. **97 commits** have landed
  since.
- **The last CI job to execute a single step was 2026-07-30 04:08 UTC**, run `30513067158` — and
  only one job in it ran: the **self-hosted `windows desktop`** job, 16 steps, **passed**. All four
  GitHub-hosted jobs in that same run *failed in three to four seconds having executed zero steps*.
- **Across the 17 CI push runs since, not one job has executed a step.** The hosted jobs
  (`ubuntu-latest`, `windows-latest`, and both frozen variants) fail instantly with `steps=0`; the
  self-hosted `windows desktop` job is cancelled without starting; the run for `733209d` has been
  **queued 18.6 hours** and has never begun.

**A zero-step three-second job failure is not a test failure**, so the 47 "failure" conclusions in
that window say nothing about the code. The signature — hosted jobs dying before step one while the
self-hosted job is merely starved — points at **GitHub-hosted runner unavailability**, consistent
with the quota exhaustion `OPS-005` was amended over. *That last clause is inference from the run
metadata; nobody has read a billing page, and it is recorded as unverified.* The cancellations are
separately explained by `ci.yml:30-32` (`cancel-in-progress: true`) plus pushes arriving faster than
a queue this deep can drain.

**What it costs, stated rather than absorbed.** The gate the trunk-based workflow leans on — *CI
runs on every push to `main`, and a red run still blocks* — has not run on `T-078` or `T-079`, and
cannot run on any of the ten now in review. Their Linux evidence is the maintainer's own machine
(`OPS-006`): **1726 passed / 11 skipped / 2 deselected**, 2026-08-01, plus `mypy --platform win32`.
**Windows has never run against the pool, and `T-087`'s `msvcrt` branch has never executed at
all** — that is the half `ARC-006`'s withdrawn design got wrong, so it is the half most worth
running. **No task should be reported as gated by CI until a run executes a step.**

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
