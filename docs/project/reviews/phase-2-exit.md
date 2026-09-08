# phase-2-exit — Review record

**Purpose:** Dated review evidence and disposition history for this task or shared scope.
**Owner:** Assigned Reviewer · **Update when:** This scope is reviewed or rechecked.
**Covered tasks:** Cross-cutting scope; see the dated entries.

[Review index](../REVIEWS.md) · [Review policy](../TESTING.md#14-review-policy)

Moved from `85422bc0b086de9b18d2f809abb4d6bcebb180e4:docs/project/REVIEWS.md` on 2026-09-08.
The entries below retain their exact original bytes and relative order. Historical
path spellings, line citations and references to “above” describe that source;
the [migration manifest](../evidence/2026-09-08-review-migration.json) records the
original order and byte ranges. Shared entries are stored once; covered tasks
link to this same record. Navigation grants no approval or new review provenance.

## Recorded rounds

- [2026-08-03 — Phase 2 exit review](#migrated-review-0126)
- [2026-08-05 — `P2EXIT-R10` records focused re-review](#migrated-review-0142)
- [2026-08-05 — `P2EXIT-R10` final records re-review](#migrated-review-0143)
- [2026-08-05 — Phase 2 exit review, second submission](#migrated-review-0144)
- [2026-08-05 — Phase 2 exit findings focused re-review](#migrated-review-0145)
- [2026-08-05 — P2EXIT-R14 records focused re-review](#migrated-review-0147)
- [2026-08-05 — P2EXIT-R14 criterion-claims re-review](#migrated-review-0148)
- [2026-08-05 — P2EXIT-R14 phase-claims final re-review](#migrated-review-0149)
- [2026-08-05 — Phase 2 exit review, third submission](#migrated-review-0150)
- [2026-08-05 — P2EXIT-R15 focused re-review](#migrated-review-0151)
- [2026-08-05 — P2EXIT-R15 final re-review and Phase 2 sign-off](#migrated-review-0152)

<a id="migrated-review-0126"></a>
<!-- review-migration:0126:start -->

## 2026-08-03 — Phase 2 exit review

**Reviewer:** Codex (Reviewer)
**Approval base:** `dca3bfa`
**Submitted implementation head:** `5eb2611`
**Handoff-only head:** `f8f8638`
**Overall verdict:** **Changes requested — Phase 2 has not exited.** The cold reconstruction finds
criteria 1 and 5 unproved by the tests named for them, the `T-122` correction is not yet a sound
timing gate, and the CI rewrite changes an accepted operations decision without a maintainer
ruling. Criteria 2, 3, 4 and 7 are met. Criterion 6 is not met while the findings below remain.

### Cold criteria reconstruction

| # | Verdict | Independent reading |
|---|---|---|
| 1 | **Not met — `P2EXIT-R2`.** | The real-worker/file and per-row progress evidence is substantive. The only named responsiveness gate, however, also passes when none of its three jobs is started. It therefore does not establish “interactive throughout while three downloads run.” |
| 2 | **Met.** | The phase test hard-kills a real composed application with in-flight and never-started jobs, starts a new composed application against the killed database, distinguishes the recovered states, and observes the recovery offer. |
| 3 | **Met.** | The phase test samples both durable in-flight rows and actual worker processes against a non-default limit over the whole run. Approved lowering and pause tests cover draining without over-admission. |
| 4 | **Met.** | A second real launch refuses while the first owns the guard and a full pool; the Windows acquisition, racing-start and killed-holder cases have prior hosted-Windows evidence. No source governing this behavior changed after that evidence. |
| 5 | **Not met — `P2EXIT-R1`.** | The N-worker phase test kills the same captured process tree whose survivors it later inspects. It passes with the product's parent-death watchdog removed, so it proves the test helper can reap workers, not that application exit leaves none. |
| 6 | **Not met.** | This independent phase review requests changes. All thirteen deliverables do have prior reviewer verdicts, subject to the boundary corrections in `P2EXIT-R5`; deliverable approval alone is not phase sign-off. |
| 7 | **Met.** | The Add-only gate admits every durable job without priming `start()`, drains beyond the pool limit, and is complemented by restart and paused-queue routes. |

### Blocking findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `P2EXIT-R1` | **Medium** | **Yes** | Criterion 5 / orphan-worker gate | `test_no_worker_outlives_a_hard_kill_with_a_full_pool` obtains `workers`, then builds `doomed` from the application's complete tree and passes that tree to `kill_the_application`. On POSIX the helper kills the process group; on Windows it kills every captured process. The later assertion asks whether the same workers are alive. A reviewer mutation deleting `_exit_when_the_parent_does()` from `worker.prepare_this_worker()` left this phase test green: **1 passed in 9.52 s**. The gate therefore survives removal of the mechanism its docstring says it proves and cannot discharge the “no worker outlives application exit” criterion at N=3. | Capture the worker set independently, kill only the actual application process (not its launcher and not its process tree/group), and assert the captured workers exit through their own parent watchdog. Put full-tree cleanup only in `finally`, after the behavioral assertion, so a failed gate still cleans up. Execute this corrected route on Linux and Windows. | **Open; Implementer** |
| `P2EXIT-R2` | **Medium** | **Yes** | Criterion 1 / responsiveness gate | `test_the_interface_stays_inside_its_budget_while_three_downloads_run` records only the worst `processEvents()` duration. It never requires a job to enter an active state, emit progress, or finish; after its 60-second deadline it asserts only the latency. A reviewer mutation deleting all three `manager.start(job_id)` calls still passed: **1 passed in 60.24 s**. An idle GUI therefore satisfies the test whose name and criterion require three concurrent downloads. | Give the measurement a positive control: hold three workers at a barrier, require all three active and independently producing/queued to produce progress before sampling, measure while that state holds, release them, and require all three to settle. It should fail promptly rather than wait 60 seconds when concurrency was never reached. | **Open; Implementer** |
| `P2EXIT-R3` | **Medium** | **Yes** | `T-122` / timing-gate correction | Repeating the ratio did not make its live samples comparable. Every `cost()` creates another manager and dialog backed by `child_never_returning`; the fixture shuts them down only after the test. Warm-up plus three small/large pairs can therefore leave seven managers and up to 28 probe workers alive, and every large sample follows its small sample under monotonically increasing background load. A median cannot remove load introduced systematically by the harness. The sample-count contract is also unguarded: changing `SCALING_PAIRS` from 3 to 1 left both the deterministic oracle test and the live gate green (**2 passed**), because the oracle supplies its own three-element lists. `T-122` was explicitly required before this exit review and remains “awaiting review,” so it is not clean evidence yet. | Prefer the original review recommendation: keep the absolute 500-row budget and structural control count as required gates, and make the relative ratio diagnostic. If the ratio remains required, shut down and reap each sample outside the timed region, alternate which size runs first, reject insufficient or unequal sample sets in `superlinear_growth`, and pin the live sample count independently. | **Open; Implementer** |
| `P2EXIT-R4` | **High** | **Yes** | CI policy / accepted `OPS-009` | Accepted `OPS-009` says the full `windows-latest` suite stays hosted and `WINDOWS_RUNNER` is a fallback that routes it to STARBASE when hosted minutes run out. The new workflow goes further without a later accepted decision: while the variable is set it deletes the Windows matrix leg, and it removes the full Windows desktop suite from ordinary pushes unless the commit says `[win]`. That is a durable coverage-policy change made below the authority of an accepted decision. Its “nightly backstop” is not guaranteed either: global `cancel-in-progress: true` lets an ordinary push cancel the scheduled Windows run, while the replacement push can skip the full Windows suite. | Obtain an explicit maintainer ruling and amend/supersede `OPS-009`, or restore the accepted policy. The ruling should state whether clean hosted-Windows evidence and every-push full Windows coverage are being surrendered, and make the nightly guarantee true (for example, do not let an ordinary push cancel a scheduled full-Windows run). Then align the workflow and canonical testing contract to that ruling. | **Open; Maintainer ruling, then Implementer** |
| `P2EXIT-R5` | **Medium** | **Yes** | Exit record / current truth | The records being signed off still contradict current evidence. `IMPLEMENTATION_PLAN.md` says the Blocked list “wants re-reading” and `STATUS.md` says nobody re-read it, although `5eb2611` records the completed re-triage. `TESTING.md` opens §10 with “Runs on every push and pull request, on Linux and Windows matrix runners,” then says ordinary pushes omit the full Windows suite. The deliverable and criterion tables also call `75f1c32` and `233c5fd` the T-084/T-086 approval heads; the reviewer record approved both only at `2a41c5f`, after later corrections. These are current-truth documents and approval boundaries, not harmless historical wording. | Reconcile the live plan, status and testing contract after the `P2EXIT-R4` ruling. Record T-084 and T-086's reviewer-approved head as `2a41c5f` (implementation commits can be named separately), and remove the already-discharged Blocked-list warning. | **Open; Planner / Documentation Maintainer** |

### Non-blocking findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `P2EXIT-R6` | **Low** | No | `T-121` diagnostic | `describe_drain_failure()` correctly stops blaming admission when no row remains queued, but it then directs every such failure to the clip server. Its input contains only final statuses; it cannot know whether a failed/cancelled download came from the observed `ConnectionAbortedError`, another worker failure, or test teardown. The new wording replaces one unjustified causal claim with a narrower but still unjustified one. | Report only what the statuses establish—admission drained and one or more jobs failed—then direct the reader to captured stderr for the cause. Name the clip-server abort only when the test observed it. | **Open, non-blocking; fold into Proposed `T-121`** |
| `P2EXIT-R7` | **Low** | No | Handoff boundary | The handoff says `origin/main` is `53b07ec`, but the reviewed checkout has `origin/main` at `dca3bfa`; it also labels `5eb2611` as the head while `f8f8638` is the handoff-only head. The implementation boundary remains recoverable and no code is hidden, so this does not affect the substantive findings. | In the correction handoff, report both implementation head and handoff head and resolve the remote immediately before writing the boundary. | **Open, non-blocking process follow-up** |

### Independent verification

| Check | Result |
|---|---|
| Submitted boundary | `dca3bfa..5eb2611` and handoff commit `f8f8638` inspected; working tree was clean before and after reviewer mutation probes. No product source changed in this boundary. |
| Cold phase suite | `tests/integration/test_phase_2_exit.py`: **13 passed in 47.57 s**. Passing the suite does not resolve `P2EXIT-R1` because the watchdog-removal mutation also passed. |
| Supporting criterion surface | Focused progress, composition, lowering, pause, graceful-shutdown, parent-kill and grandchild tests: **13 passed in 14.10 s**. Changed T-083/T-121/T-122/task-placement tests: **18 passed in 3.57 s**. |
| Static gates | `ruff check .` passed; `ruff format --check .`: **144 files**; `mypy --no-incremental src`: **43 files**; bare host and bare `--platform win32` mypy: **101 files each**. |
| Reviewer mutation: criterion 5 | Removed the worker parent-watchdog call. The named N-worker phase test still passed. Mutation reverted; tree verified clean. |
| Reviewer mutation: criterion 1 | Removed every `manager.start()` from the named responsiveness test. The idle 60-second loop still passed. Mutation reverted; tree verified clean. |
| Reviewer mutation: T-122 | Reduced live timing pairs from three to one. The synthetic oracle test and live timing test both passed. Mutation reverted; tree verified clean. |
| Windows evidence | The last full Windows product evidence remains run `30859578131` at `53b07ec`. Production source has not changed since it. An exact-head Windows run now would not repair the platform-neutral gate defects above; the corrected criterion-5 route itself needs exact Linux and Windows execution before exit. |

### Final disposition

Do **not** spend a Windows run on `f8f8638`. First correct `P2EXIT-R1`, `P2EXIT-R2` and
`P2EXIT-R3`, obtain the `P2EXIT-R4` maintainer ruling, and reconcile `P2EXIT-R5`. Then push the
correction head with `[win]` or dispatch the workflow against that exact head. The useful final
evidence is the corrected N-worker parent-watchdog test on both Windows and Linux, the
positive-controlled three-download responsiveness measurement, the selected T-122 policy, and a
workflow whose observed jobs match the newly accepted policy.

No source, submitted test, repository variable, remote ref or CI state was changed by the
reviewer. The three temporary mutations above were reverted and the working tree was clean before
this review record was appended.

<!-- review-migration:0126:end -->

<a id="migrated-review-0142"></a>
<!-- review-migration:0142:start -->

## 2026-08-05 — `P2EXIT-R10` records focused re-review

**Reviewer:** Codex (Reviewer)
**Correction base:** `083fbe4`
**Correction head:** `c920446` (`422c545` carries the preceding review record and mixed-safety
regression; `c920446` is the three-document correction)
**Verdict:** **Changes requested.** The four contradictory surfaces named by the prior pass are
corrected, including a coherent end-to-end T-142 rewrite. `P2EXIT-R10` remains open because the
rewrite drops one of the finding's required criterion-8 gates: an exact-candidate built-window
checklist. `STATUS.md` also replaces its stale implementation claim with an overbroad exact-head
claim that includes this still-open finding.

### Finding status

| ID | Severity | Blocks approval | Re-review result | Status |
|---|---|---:|---|---|
| `P2EXIT-R10` | High | **Yes — Phase 2 exit truth** | The live outstanding-work row no longer says “nine open” or calls built T-140 work outstanding. T-140's introduction now says the work landed. T-142 is genuinely rewritten around a History playlist header, depends on T-145, names History surfaces, derives a distinct terminal-record verb set, and no longer assigns its own subject away. STATUS no longer says the implementation is unfinished. However, the original finding also requires the built application to be run on the exact candidate against a written checklist derived from T-132–T-141 and the adopted mockups, precisely because automated gates missed visible defects. The rewritten outstanding row names exact-head Windows and Fedora evidence but omits that checklist, and no current-truth document carries it. STATUS then says **every finding** from the round and its correction passes was resolved at `083fbe4`; P2EXIT-R10 itself was not, and its record correction is `c920446`. | **Open — the stale scope is repaired; the owed evidence list and exact-head attribution are not** |

### Required correction

Restore the exact-candidate **built-window checklist** to criterion 8's outstanding evidence. It
must cover the closed T-132–T-141 list and adopted mockups; Fedora/Windows automated evidence does
not substitute for it because `P2EXIT-R10` recorded that five visible defects escaped those gates.
The checklist need not be run before this document correction lands: criterion 8 should remain
Not met and say the checklist is owed, then record its result against the candidate when performed.

Qualify STATUS's head claim as the **implementation** findings being resolved at `083fbe4`, and
name `c920446` (plus this re-review when carried) for P2EXIT-R10's record correction. Exact review
boundaries are the subject of these repairs, so “every finding resolved at the source head” is not
an interchangeable shorthand.

### Independent verification

| Check | Result |
|---|---|
| Boundary | `git diff --check 083fbe4..c920446`: **pass**. The range contains the prior review/test carry plus the three current-truth documents corrected at `c920446`. |
| Stale-claim sweep | No remaining `nine open`, `implementation is not finished`, `What remains here`, or equivalent old T-140 group-verb claim outside `ai/REVIEWS.md`. |
| T-142 coherence | Title, status, priority, dependency, relevant context, affected surfaces, Scope, acceptance criteria and Out of scope now consistently describe History-header verbs after T-145. |
| Missing-gate sweep | No current-truth document mentions the required built-window/written checklist for T-132–T-141 or the exact candidate. |
| Placement gate | `tests/unit/test_task_placement.py`: **14 passed**. |
| Carried mixed-safety regression | **1 passed** at `c920446`. |

No new regression was needed for a prose-only finding. This review appends this record only. No
source, test, decision, task state, commit, remote ref or CI state was changed by the reviewer.

<!-- review-migration:0142:end -->

<a id="migrated-review-0143"></a>
<!-- review-migration:0143:start -->

## 2026-08-05 — `P2EXIT-R10` final records re-review

**Reviewer:** Codex (Reviewer)
**Correction base:** `c920446`
**Approved at:** `431bb47` (`814ee93` carries the preceding review record; `431bb47` is the final
plan/status correction)
**Verdict:** **Approved.** `P2EXIT-R10` is resolved. This approves the truth of the criterion-8
records; it does **not** mark criterion 8 or Phase 2 met. The exact-candidate checklist and platform
evidence they now name remain to be performed.

### Finding status

| ID | Severity | Blocks approval | Re-review result | Status |
|---|---|---:|---|---|
| `P2EXIT-R10` | High | No | The outstanding-work row now preserves all three owed steps: run the built application on the exact candidate against a written checklist derived from T-132–T-141 and the adopted mockups; obtain Windows and Fedora evidence on that same candidate; and complete re-review. It explicitly states that automation cannot replace the checklist because visible defects escaped the gates. STATUS carries the same manual obligation and now limits `083fbe4` to the four implementation findings rather than claiming every finding resolved there. Together with `c920446`'s coherent T-140/T-142 rewrites, the current-truth documents no longer call built work outstanding or omit an accepted evidence gate. | **Resolved at `431bb47`** |

### Independent verification

| Check | Result |
|---|---|
| Boundary | `git diff --check c920446..431bb47`: **pass**. `814ee93` changes only the reviewer record; `431bb47` changes only `ai/IMPLEMENTATION_PLAN.md` and `ai/STATUS.md`. |
| Checklist authority | Both plan and status name the built application, a written T-132–T-141/adopted-mockup checklist, and the exact candidate head; both say automated evidence is insufficient. |
| Resolution attribution | STATUS names only `T140-R6`, `T137-R2`, `T137-R3` and `T140-R5` as implementation findings resolved at `083fbe4`, and explicitly excludes P2EXIT-R10 from that claim. |
| Stale/weakening sweep | No current-truth criterion-8 record retains the old “nine open,” unfinished-implementation, or all-findings-at-`083fbe4` claim. The manual checklist is present in both places it is owed. |
| Placement gate | `tests/unit/test_task_placement.py`: **14 passed**. |

No test or source change was needed for this docs-only re-review. This review appends the approval
record only. The next coordination update may mark T-140 Complete at its reviewed head and replace
“awaits re-review” with this approval; criterion 8 remains Not met until its checklist and
exact-head Windows/Fedora evidence pass. No source, test, decision, task state, commit, remote ref
or CI state was changed by the reviewer.

<!-- review-migration:0143:end -->

<a id="migrated-review-0144"></a>
<!-- review-migration:0144:start -->

## 2026-08-05 — Phase 2 exit review, second submission

**Reviewer:** Codex (Reviewer)
**Review base:** `431bb47`
**Implementation head:** `541b484`
**Submission head:** `5ccf2bc` (`bf264e5` adds the second-run evidence and `5ccf2bc` adds the
handoff/current plan claim)
**Verdict:** **Changes requested.** Criteria 1, 6 and 8 are not met. The second checklist record
cannot support its “all 41 rows” result while it also records failures of those rows, and a later
probe-continuation change regressed the accurate per-job progress criterion. The focused T-152
correction also steals focus on unrelated model resets.

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `P2EXIT-R11` | **High** | **Yes — criterion 1 / REQ-014** | Accurate per-job progress | A durable playlist probe reaches `READY` while retaining its last drawn `Stage.PROBING`. `_status_text()` gives any non-terminal row's drawn stage precedence, so the row says **Probing** beside a **Ready** chip indefinitely. The candidate already files this exact behavior as High in `T-162`, and the reviewer regression reproduces it. The criterion-8 closed-list rule cannot defer a failure of the independent Phase 2 criterion that each job show accurate progress, or REQ-014's current-stage promise. | Retire a completed probe's live state, or otherwise make stage precedence conditional on a stage that can still be active in the current status. Prove the probe → ready → download sequence while retaining `Probing` during a live probe and download-stage detail during a live download. | **Open** |
| `P2EXIT-R12` | **High** | **Yes — criterion 8 / accepted T-153 criterion** | Built-window evidence | The second-run artifact reports **“pass, all 41 rows”** while its own known-open section says the candidate fails checklist row 3.15: every playlist on the primary site still draws a blank parent picture because the selected URL returns 404 (`T-161`). T-153 is Phase 2 work whose acceptance criterion is that the staged playlist row **shows** its own picture; its unit regression proves only that an address string is selected and cannot prove that address yields a picture. The same artifact calls row 2.7 passed while T-160 says the format control overlaps the thumbnail at the dialog's default size. Whether T-160 remains Phase 3 does not make a checklist row it directly fails a pass. | Mark criterion 8 Not met. Correct the T-153 continuation (or obtain an explicit amendment to what “shows a picture” means), then rerun the written checklist and record results that distinguish passed rows from accepted later defects. Keep the closed-list ruling, but do not use it to rewrite an observed row failure as a pass. | **Open** |
| `P2EXIT-R13` | **Medium** | **Yes — NFR-005 / T-152 correction** | Keyboard focus | Both queue and History `modelReset` signals call `_give_the_rows_the_keyboard()`, which focuses whichever tab is currently visible without checking which model reset or whether focus is intentionally on a toolbar control. A hidden History refresh therefore takes focus from `concurrencyChoice` and moves it into the queue. The source disclosure limits this cost to the instant a first row arrives, but the connection runs on every structural reset from either model. That makes the keyboard route reachable by interrupting unrelated keyboard work, contrary to T-152's stated “initial focus, not the ability to have it” trade. | Restrict automatic focus placement to initial construction and the empty → first-row transition of the relevant visible view. Preserve deliberate focus elsewhere, and cover a hidden-tab reset plus a repeated nonempty queue refresh. | **Open** |
| `P2EXIT-R14` | **High** | **Yes — Phase 2 exit truth** | Current-truth records | The canonical plan contains incompatible live verdicts: exit row 8 claims criterion 8 met from the second 41-row run, while its outstanding-work row still says the checklist rerun—including rows 3.6 and §5—has never happened. STATUS likewise says criterion 8 is Not met and the rerun is owed, then later describes it as waiting on that same evidence. This is the P2EXIT-R10/COORD-R5 class once more: one current-truth occurrence was updated while the sibling claims were left behind. The handoff also says eleven Phase 3 findings and lists twelve. | Reconcile every live criterion-8 occurrence in plan and status in one sweep after the evidence is corrected. Until the other findings close, state that criteria 1, 6 and 8 are Not met and this review requested changes. Correct the handoff/task count when carrying the review. | **Open** |

### Exit-criterion reconstruction

| Criterion | Review result |
|---|---|
| 1 | **Not met.** `P2EXIT-R11` is a deterministic inaccurate-stage case on the durable playlist route added after the earlier criterion proof. |
| 2 | **Met on the submitted evidence.** The candidate does not change persistence, recovery, composition recovery ordering or the phase restart gate. |
| 3 | **Met on the submitted evidence.** Pool limits, lowering and pause mechanics are outside the candidate's changed source. |
| 4 | **Met on the submitted evidence.** The single-instance implementation and its approved Windows evidence are unchanged. |
| 5 | **Met at the last corrected Linux/Windows evidence head.** No worker/watchdog/process-lifecycle source changed in this submission. The newly dispatched candidate CI was not awaited or used as evidence in this review. |
| 6 | **Not met.** This independent review requests changes, so there is no phase sign-off. The 60-run Linux soak remains accepted as the measurement half. |
| 7 | **Met on the submitted evidence.** The Add/admission/restart routes remain covered; the candidate's `main_window.py` change is focus placement, not admission. |
| 8 | **Not met.** The claimed pass contradicts rows 2.7 and 3.15 and the accepted T-153 property remains false in the built window. |

All thirteen deliverable approval records were found. Those approvals do not override a later
regression of deliverable 2's per-job status/progress surface, which is the same current candidate
criterion 1 asks this review to judge.

### Independent verification

| Check | Result |
|---|---|
| Boundary | `431bb47..541b484` changes five source files and their tests plus current-truth/evidence records. `541b484..5ccf2bc` changes only plan/status/evidence/handoff files. `git diff --check 431bb47..5ccf2bc` reports one submitted whitespace error: an extra blank line at the end of `ai/STATUS.md`. |
| Candidate-range identity | `git diff --stat 6bae7ec..541b484` confirms only `ai/TASKS.md` differs, so the Fedora second run does describe one application build despite its unrecorded exact commit. |
| Reviewer criterion-1 regression | `test_a_finished_probe_does_not_outlive_the_ready_status`: **failed** — actual state `Probing`, expected `Ready to download`; the chip is `Ready`. |
| Reviewer focus regression | `test_a_hidden_history_refresh_does_not_take_focus_from_the_toolbar`: **failed** — refreshing hidden History moves focus off `concurrencyChoice`. |
| Submitted correction neighborhood | **9 passed**: the five T-152 keyboard cases, T-165 cancelled summary and enum coverage, the corrected finished-segment palette case, and T-153's adapter projection case. These prove the submitted local mechanisms but do not reach the two reviewer failures or a thumbnail fetch. |
| Reviewer-test lint / format | `ruff check` on both changed reviewer test files: **pass**. `ruff format --check`: **pass**, 2 files. |
| Submitted broader checks | The handoff reports unit/UI **1875 passed, 11 skipped**, integration **307 passed**, ruff, format and mypy. They were not rerun wholesale; run `31045159414` was intentionally not awaited at the maintainer's direction and has no bearing on the deterministic blockers above. |

This review adds two failing regressions, one each to `tests/ui/test_queue_view.py` and
`tests/ui/test_row_verb_wiring.py`, and appends this record. No submitted source, decision, task
state, commit, remote ref or CI state was changed by the reviewer.

<!-- review-migration:0144:end -->

<a id="migrated-review-0145"></a>
<!-- review-migration:0145:start -->

## 2026-08-05 — Phase 2 exit findings focused re-review

**Reviewer:** Codex (Reviewer)
**Correction base:** `5ccf2bc`
**Correction head:** `e4b2208` (`5de6ddb` carries the preceding review record/regressions and
candidate CI result; `83f3aa2` corrects P2EXIT-R11/R13 and the first record sweep; `e4b2208`
implements T-161)
**Verdict:** **Changes requested.** P2EXIT-R11 and P2EXIT-R13 are resolved. P2EXIT-R12's false
pass record is corrected, but its T-161 continuation contains a new High regression and row 3.15
is deliberately unrun. P2EXIT-R14 remains open because the later T-161 commit advanced one set of
current-truth claims and left the plan, checklist and task fields behind.

### Finding status

| ID | Severity | Blocks approval | Re-review result | Status |
|---|---|---:|---|---|
| `P2EXIT-R11` | High | No | `_status_text()` now accepts a drawn stage only when `_STAGES_STILL_LIVE_IN` says that stage can still be active in the durable status. The reviewer probe now reports `Ready to download` beside the `Ready` chip after PROBING → READY, while existing live-download coverage still reports `Downloading video`. The closed-list misclassification is corrected in current status. | **Resolved** |
| `P2EXIT-R12` | High | **Yes — criterion 8 / T-153** | The historical evidence now honestly records 39 passed and failures at rows 2.7 and 3.15; it does not promote a fix into an observation, and says row 3.15 must be rerun. T-161 adds a parent-thumbnail candidate walk, but `T161-R1` below means that implementation is not approved. Row 2.7 still needs the disposition recorded below. | **Open — evidence corrected; implementation and rerun remain** |
| `P2EXIT-R13` | Medium | No | Focus placement now records row counts per view and runs only on that view's empty → nonempty transition while it is visible. The original hidden-History reviewer regression passes, and the strengthened version also proves refreshing an already-populated queue preserves toolbar focus. First rows still take focus and startup rows still hold it. | **Resolved** |
| `P2EXIT-R14` | High | **Yes — Phase 2 exit truth** | `83f3aa2` correctly reset the 41/41 claim and reconciled plan/status at that head. `e4b2208` then declared T-161 fixed only in later STATUS/evidence/task prose. The plan still says T-161 correction is owed and two rows currently fail; the live checklist still says T-161 and T-162 are present Phase 3 defects; and T-161's own task says it was reclassified Phase 2 while its `Phase:` field remains Phase 3. This is the same sibling-update failure the finding names, reproduced by its correction sequence. | **Open — initial sweep correct, later head drifted again** |

### New correction finding

| ID | Severity | Blocks approval | Finding | Recommendation | Status |
|---|---|---:|---|---|---|
| `T161-R1` | **High** | **Yes — T-161 acceptance / playlist probe usability** | The reachability callback is passed to `_entries()`, so projection performs a HEAD walk for every playlist member carrying multiple thumbnails, not only for the playlist parent's picture T-161 owns. A two-entry reviewer fixture makes three requests: parent, entry A and entry B. The task explicitly requires **“No probe-time network request per entry”** and leaves entry thumbnails out of scope. With a four-second timeout for each candidate, the worst case grows with entries × candidates and can hold a large playlist probe for minutes with no user workaround. The submitted tests also stop one seam short in the other direction: all four inject `reachable`, so replacing the production `_url_answers()` implementation with `False` leaves all four green. They prove the chooser given an oracle, not the default boundary that must supply it. | Apply reachability only to the playlist parent's candidates. Keep entries on their existing best-candidate projection without network I/O. Add a default-boundary test—without injecting `reachable`—that makes the best address refuse and the next answer, so `_url_answers = False` fails; retain the reviewer no-per-entry regression. Then run row 3.15 in the built dialog. | **Open** |

### Row 2.7 disposition

**Remove row 2.7 from the Phase 2 criterion-8 checklist and keep T-160 in Phase 3.** Do not amend
the row to tolerate the overlap, and do not call its historical failure a pass. The row already
states the correct product behavior; its author now establishes that it was added after the closed
list specifically to describe a known Phase 3 defect. Keeping it as a Phase 2 gate silently expands
the closed list, while weakening it to match the defect repeats P2EXIT-R12. Move the property to
T-160/Phase 3's acceptance evidence and preserve the second-run record as the historical 39/41
result it actually was.

Fixing T-160 is valid Phase 3 work and the maintainer may deliberately sequence it before exit. It
is not required by this review unless the maintainer explicitly reclassifies it into Phase 2; the
closed-list rule otherwise decides that boundary exactly as written.

### Independent verification

| Check | Result |
|---|---|
| Boundary | `5ccf2bc..e4b2208` is three commits and twelve files. `git diff --check`: **pass**. |
| Original reviewer probes | P2EXIT-R11 ready-state and P2EXIT-R13 hidden-refresh tests: **pass**. The focus test was extended to an already-populated queue refresh and still passes. |
| Correction neighborhood | **23 passed** across the two original reviewer probes, live-stage/retry behavior, focus first-row/startup behavior, four submitted T-161 cases and the placement gate. |
| Adapter file with reviewer regression | **106 passed, 1 failed**. The sole failure records parent plus both entry reachability calls where the accepted bound permits the parent call only. |
| Production-boundary mutation | Replaced `_url_answers()` with `return False`: the four submitted T-161 tests still report **4 passed**. The source was restored byte-for-byte afterward. |
| Reviewer-test lint / format | `ruff check`: **pass**. `ruff format --check`: **pass**, 2 files. |
| Test-inclusive types | Bare mypy and `mypy --platform win32`: **pass**, 107 files each. |
| Submitted broad gates | Implementer reports unit/UI **1881 passed, 11 skipped**, integration **307 passed**, ruff and mypy clean. Candidate run `31045159414` is recorded green on all five jobs at `541b484`; it predates these source corrections and is not exact-head evidence for `e4b2208`. |

This review adds one failing T-161 regression to `tests/unit/test_ytdlp_adapter.py`, strengthens the
passing P2EXIT-R13 reviewer regression in `tests/ui/test_row_verb_wiring.py`, and appends this
record. The temporary `_url_answers` mutation was fully restored. No submitted source, decision,
task state, commit, remote ref or CI state was changed by the reviewer.

<!-- review-migration:0145:end -->

<a id="migrated-review-0147"></a>
<!-- review-migration:0147:start -->

## 2026-08-05 — P2EXIT-R14 records focused re-review

**Reviewer:** Codex (Reviewer)
**Correction base:** `376407f`
**Correction head:** `8d7c88d`
**Verdict:** **Changes requested.** The submitted correction repairs the named criterion-8
siblings, preserves the historical 39/41 observation, and restores the four-row known-open table.
P2EXIT-R14 remains open because STATUS still contains incompatible live exit verdicts immediately
above the corrected finding table, and both plan and STATUS still say this already-requested exit
review has never been requested.

### Finding status

| ID | Severity | Blocks approval | Re-review result | Status |
|---|---|---:|---|---|
| `P2EXIT-R14` | High | **Yes — Phase 2 exit truth** | The criterion-8 plan row and outstanding-work heading now agree: the earlier run observed 39/41, both failed rows were later dispositioned, and the unperformed 40-row run is why criterion 8 remains Not met. STATUS's main criterion-8 account and finding rows now say the same. The second-run annex no longer asks for a row 2.7 decision, and T-166/T-167 are inside the checklist table. However, STATUS lines 1376–1384 still first claim every criterion except 6(a) met and then call criteria 1, 6 and 8 Not met. Criterion 1 is resolved; criterion 8 remains open. Plan line 424 and STATUS line 90 also still say the independent exit review has never been requested, although this review has been in progress since `5ccf2bc`. | **Open — the criterion-8 repair is correct; the live exit-state sweep is still incomplete** |
| `P2EXIT-R12` | High | **Yes — criterion 8 evidence** | Unchanged by this docs correction. T-161 remains approved, row 2.7 remains outside the closed list without weakening T-160, and no 40-row built-window observation has been submitted. | **Open — run and record the 40 rows** |

### Required correction

Reconcile the two adjacent STATUS verdicts to the current state: criteria 1–5 and 7 are met;
criteria 6 and 8 are Not met. Criterion 6 is not a separate implementation or evidence task: its
independent review is **in progress** and cannot be signed off while P2EXIT-R12/P2EXIT-R14 remain
open. Replace the two “never requested” claims in the plan and STATUS with that fact. If the
candidate-era sentence at STATUS line 1376 is retained as history, put it explicitly in the past
and state that P2EXIT-R12 reset its criterion-8 claim; do not leave “now claimed met” as live prose.

Do not change the second run's 39/41 result. It is a historical observation over the then-current
41 rows, not arithmetic to recompute after row 2.7's later removal. The next run measures the 40
rows that remain.

### Independent verification

| Check | Result |
|---|---|
| Boundary | `git diff --check 376407f..8d7c88d`: **pass**. One commit changes the four plan/status/checklist/evidence documents and carries the preceding review record; no source or test file changes. |
| Named sibling audit | No live “two rows fail,” present-tense row 2.7/3.15 failure, T-161-correction-owed, row-2.7-decision-owed, or R14-fixed claim remains in the four corrected documents. |
| Historical evidence | The second-run result remains **39 of 41** and explicitly says it is not recomputed. Its annex now records T-161 corrected/approved, row 2.7 removed with its property intact in T-160, and future runs covering 40 rows. |
| Checklist rendering | T-163, T-164, T-166 and T-167 now occupy one contiguous Markdown table. |
| Remaining contradiction | STATUS lines 1376–1384 make mutually exclusive current claims; plan line 424 and STATUS line 90 falsely say this review was never requested. |
| Placement gate | `tests/unit/test_task_placement.py`: **14 passed**. |

No source or test correction was needed. The reviewer appends this record only; no submitted
document, task state, commit, remote ref or CI state was changed by the reviewer.

<!-- review-migration:0147:end -->

<a id="migrated-review-0148"></a>
<!-- review-migration:0148:start -->

## 2026-08-05 — P2EXIT-R14 criterion-claims re-review

**Reviewer:** Codex (Reviewer)
**Correction base:** `8d7c88d`
**Correction head:** `9fe5e37`
**Verdict:** **Changes requested.** The three criterion-level claims named by the preceding pass
are corrected, and the new shared verdict is accurate: criteria 1–5 and 7 met; criteria 6 and 8
Not met. P2EXIT-R14 remains open because two older plan summaries still say criterion 6 alone
stands between the project and exit, while STATUS still names the already-completed T-128 diagnosis
as a current blocker. Those are whole-phase siblings of the same verdict, not row-level history.

### Finding status

| ID | Severity | Blocks approval | Re-review result | Status |
|---|---|---:|---|---|
| `P2EXIT-R14` | High | **Yes — Phase 2 exit truth** | STATUS now marks the candidate-era “all except 6(a)” claim superseded and places the current verdict directly below it. Its findings introduction correctly distinguishes the submission-time 1/6/8 result from today's 6/8 result. Plan criterion 6 and STATUS correctly say the review was requested and is in progress. However, plan lines 183–185 still call criterion 6 “the only thing left,” and line 240 says criterion 6 alone stands between the project and exit, despite the same plan's criterion 8 being Not met. STATUS lines 69–70 still say Phase 2 is blocked on T-128's diagnosis immediately before lines 72 and 88 say it is diagnosed and its prerequisite satisfied. | **Open — the requested criterion claims are repaired; the phase-level siblings are not** |
| `P2EXIT-R12` | High | **Yes — criterion 8 evidence** | Unchanged. The current verdict correctly identifies the unperformed 40-row built-window run as criterion 8's remaining evidence. | **Open — run and record the 40 rows** |

### Required correction

Rewrite or explicitly mark superseded the two pre-criterion-8 plan summaries. They may accurately
say that criterion 6 was the only remaining item **at that earlier date**, but cannot state it as
what stands between the current project and exit. Prefer linking them to the canonical exit table
instead of creating another live verdict copy.

Rewrite STATUS's T-128 blocker sentence as historical or remove it. The diagnosis and replacement
60-run measurement are complete; current Phase 2 blockers are criteria 6 and 8, exactly as the
correct current-truth block at lines 1380–1382 now says. The Phase 1 criterion-7 statement at
STATUS line 1113 is correctly scoped to Phase 1 and requires no change.

The repeated correction pattern now spans row claims, criterion claims and phase summaries. A
reliable repair is to leave one live verdict table/block per canonical document and mark earlier
narrative snapshots explicitly historical, rather than continuing to synchronize multiple copies.
This is a record-structure recommendation, not a new product or architecture decision.

### Independent verification

| Check | Result |
|---|---|
| Boundary | `git diff --check 8d7c88d..9fe5e37`: **pass**. One commit changes plan and STATUS and carries the preceding review record; no source, tests, checklist or evidence artifact changed. |
| Requested three claims | **Corrected.** The old candidate verdict is superseded; criterion 1 is met; the exit review is requested and in progress in both canonical records. |
| Canonical current verdict | Plan's exit table and STATUS lines 1380–1382 agree: criteria 1–5 and 7 met; criteria 6 and 8 Not met. |
| Remaining sibling sweep | Plan lines 185 and 240 still say criterion 6 alone remains. STATUS lines 69–70 still name T-128 diagnosis as a current blocker, contradicted by lines 72 and 88. |
| Phase 1 boundary | STATUS line 1113 occurs in Phase 1's historical gate account and refers to that phase's criterion 7; correctly untouched. |
| Placement gate | `tests/unit/test_task_placement.py`: **14 passed**. |

No source or test correction was needed. The reviewer appends this record only; no submitted
document, task state, commit, remote ref or CI state was changed by the reviewer.

<!-- review-migration:0148:end -->

<a id="migrated-review-0149"></a>
<!-- review-migration:0149:start -->

## 2026-08-05 — P2EXIT-R14 phase-claims final re-review

**Reviewer:** Codex (Reviewer)
**Correction base:** `9fe5e37`
**Approved at:** `e94b412`
**Verdict:** **P2EXIT-R14 is resolved.** The phase-level siblings now agree with the canonical exit
table, and earlier claims are explicitly dated or superseded rather than presented as current.
This does **not** approve the Phase 2 exit: P2EXIT-R12 remains open until the 40-row built-window
run supplies criterion-8 evidence, so criterion 6 cannot yet receive sign-off.

### Finding status

| ID | Severity | Blocks approval | Re-review result | Status |
|---|---|---:|---|---|
| `P2EXIT-R14` | High | No | Both plan summaries now account for criterion 8: the live status says it is Not met awaiting the 40-row run, and the 2026-08-03 “criterion 6 alone” statement is explicitly past-tense history. STATUS marks the T-128 blocker statement as true only when written and names its diagnosis complete; its current block identifies criteria 6 and 8. The outstanding-work row now records the exit review requested and in progress, including which findings are resolved. Plan's exit table and STATUS's current verdict agree that criteria 1–5 and 7 are met and 6 and 8 are Not met. | **Resolved at `e94b412`** |
| `P2EXIT-R12` | High | **Yes — criterion 8 evidence** | No new built-window observation is in this docs-only correction. T-161 remains approved and row 2.7 remains correctly outside the live checklist without altering the historical 39/41 result. | **Open — run and record all 40 current rows** |

### Non-blocking observation

The plan and STATUS say this review has “requested changes three times,” while the appended review
history contains five Changes requested verdicts from the second submission through the
criterion-claims pass. That count is not used to establish a criterion and does not misstate phase
readiness, so it does not keep P2EXIT-R14 open. Omitting the count on the next record touch would
avoid creating another synchronized fact; the linked findings already say what matters.

### Remaining exit path

Run the built application on kirk against all 40 current checklist rows on one exact candidate
head, recording passed rows separately from failed rows and observing row 3.15 in particular. If
that evidence passes, obtain fresh exact-head CI/platform evidence and return the resulting head for
P2EXIT-R12 verification and the criterion-6 sign-off. The historical second run remains 39/41.

### Independent verification

| Check | Result |
|---|---|
| Boundary | `git diff --check 9fe5e37..e94b412`: **pass**. One commit changes plan and STATUS and carries the preceding review record; no source, tests, checklist or evidence artifact changed. |
| Phase-level sweep | No live plan/STATUS statement says criterion 6 alone remains or names T-128 diagnosis as a current blocker. The corrected summaries point to criteria 6 and 8. |
| Outstanding-work row | The exit review is recorded as requested 2026-08-05 and in progress; R11, R13 and T161-R1 are correctly named resolved. |
| Canonical verdict | Plan and STATUS agree: criteria 1–5 and 7 met; criterion 6 Not met pending approval; criterion 8 Not met pending the 40-row run. |
| Historical boundaries | The earlier criterion-6-only plan claim and T-128 blocker claim are explicitly past-tense. STATUS's Phase 1 criterion-7 account remains correctly untouched. |
| Placement gate | `tests/unit/test_task_placement.py`: **14 passed**. |

No source or test correction was needed. The reviewer appends this record only; no submitted
document, task state, commit, remote ref or CI state was changed by the reviewer.

<!-- review-migration:0149:end -->

<a id="migrated-review-0150"></a>
<!-- review-migration:0150:start -->

## 2026-08-05 — Phase 2 exit review, third submission

**Reviewer:** Codex (Reviewer)
**Review base:** `e94b412`
**Evidence head:** `165b6e4`
**Submission head:** `b4aae67` (`9aa3a43` records the 40-row run, `229dbbb` submits it, and
`b4aae67` marks the first handoff superseded)
**Verdict:** **Changes requested.** P2EXIT-R12 is resolved and criterion 8 is met on the accepted
maintainer evidence. Criteria 1–5, 7 and 8 are met. Criterion 6 remains Not met because the evidence
commit reproduced P2EXIT-R14's claim-over-sibling shape in current STATUS and one live plan summary:
the same records now both accept the 40-row pass and say it has not happened.

### Finding status

| ID | Severity | Blocks approval | Review result | Status |
|---|---|---:|---|---|
| `P2EXIT-R12` | High | No | The third built-window run records **40 of 40 passed** across the 40 live checklist rows, including the two letter-suffixed rows 2.5a and 3.9a. It explicitly observes row 3.15's playlist parent picture rather than inferring it from T-161's source fix. Row 2.7 remains removed with its property intact in T-160, and the earlier run remains the historical 39/41 result. The evidence states its one-platform and one-runner limits inside the claim. The maintainer's Linux-only visual ruling is accepted; Windows automated coverage remains green but is not misdescribed as a person inspecting the window. | **Resolved on the evidence at `9aa3a43`** |
| `P2EXIT-R14` | High | No | Its reviewed state at `e94b412` remains resolved. The new contradiction below was introduced by the later evidence/current-truth update and does not rewrite that exact-head approval. | **Resolved at `e94b412`** |
| `P2EXIT-R15` | **High** | **Yes — Phase 2 exit truth / criterion 6** | The third-run update advances later plan/STATUS claims to criterion 8 met but leaves earlier live siblings behind. Plan line 185 still says criterion 8 is Not met awaiting the 40-row run. STATUS lines 69–72 name that run as a current blocker; lines 118–120 say the exit review is absent; lines 122–139 call criterion 8 Not met and the rerun owed. Its findings table still calls P2EXIT-R14 open at line 1405, and lines 1414–1425 say row 3.15 is unrun and criterion 8 Not met immediately before lines 1427–1435 record the 40/40 pass. This is the same claim stated over contradicting evidence that R12 caught and the same sibling-update class R14 resolved, recreated by the evidence commit. | **Open** |

### Exit-criterion reconstruction

| Criterion | Review result |
|---|---|
| 1 | **Met.** P2EXIT-R11 is resolved; the durable probe no longer leaves a READY job displaying a live Probing stage, and the accepted concurrency/progress/UI evidence remains unchanged. |
| 2 | **Met.** No persistence, recovery or restart source changed after its accepted hard-kill proof. |
| 3 | **Met.** Pool-limit, lowering and queue-pause mechanics are unchanged from their accepted evidence. |
| 4 | **Met.** The single-instance implementation and its platform evidence are unchanged. |
| 5 | **Met.** The corrected N-worker orphan gate remains accepted. GitHub run `31051896815` independently verifies the candidate build on all five jobs, including `windows desktop`. |
| 6 | **Not met.** The soak half remains met, but this independent exit review requests a current-truth correction for P2EXIT-R15. |
| 7 | **Met.** The Add/admission/restart routes are unchanged from their accepted proof. |
| 8 | **Met on the maintainer's accepted evidence.** The live checklist contains exactly 40 rows; all 40 are recorded passed on kirk, including the requested row 3.15 observation. The maintainer explicitly accepts Linux-only human inspection for this criterion and the evidence preserves the Windows visual residual. |

All thirteen deliverables remain approved. The ten named Phase 3 findings remain outside the closed
criterion-8 list; none contradicts a live checklist row under the recorded dispositions.

### Required correction

Reconcile the post-evidence siblings without changing the evidence:

- In the plan's Phase 2 status summary, replace the still-owed 40-row run with criterion 8 met on
  the evidence offered to review; criterion 6 is the remaining live gate.
- In STATUS's top Phase 2 account, replace the current 40-row blocker and absent-review claims with
  the completed run and review in progress. Update the earlier criterion-8 paragraph through the
  third run instead of leaving it at the second.
- In STATUS's review section, mark P2EXIT-R14 resolved at `e94b412`, remove or supersede the
  “row 3.15 is unrun” verdict, and make the current state only criterion 6 / P2EXIT-R15.

Keep the second run at 39/41, the third at 40/40, and the Linux-only ruling unchanged. No new source,
test, checklist run or CI dispatch is requested. Run `31051896815` is sufficient for this submission:
`165b6e4..b4aae67` changes records only, and `376407f..b4aae67` changes no source, tests,
`pyproject.toml` or workflow configuration.

### Independent verification

| Check | Result |
|---|---|
| Boundary | `git diff --check e94b412..b4aae67`: **pass**. The range changes only plan/status/review/evidence/handoff records. |
| Candidate identity | `git diff 376407f..b4aae67 -- src tests pyproject.toml .github`: **empty**. The checklist and CI describe the same executable/test/build configuration through submission head. |
| Checklist cardinality | **40 live rows**, counted directly: 1.1–1.8, 2.1–2.6 including 2.5a, 3.1–3.18 including 3.9a, 4.1–4.5 and 5.1. |
| P2EXIT-R12 evidence | Third-run artifact: **PASS — 40 of 40**; row 3.15 explicitly named as the observation the run existed to obtain. The evidence retains the historical 39/41 result and does not convert removed row 2.7 into a pass. |
| CI | GitHub Actions run `31051896815`, head `165b6e4f935f0459fed742d2c93978cb3ec16250`: **completed / success**. `STARBASE coverage`, `linux`, `frozen linux`, `windows desktop` and `frozen windows` all succeeded. |
| Current-truth negative audit | Plan line 185 and STATUS lines 72, 118–139, 1405 and 1424–1425 contradict the accepted third-run/current verdict elsewhere in those files. |
| Placement gate | `tests/unit/test_task_placement.py`: **14 passed**. |
| Submitted broader gates | Implementer reports unit/UI **1884 passed, 11 skipped**, integration **307 passed**, ruff, format and mypy clean. The reviewer verified the external CI result rather than rerunning these complete suites locally. |

No new test was needed for this records-only finding. The reviewer appends this record only; no
submitted document, source, test, task state, commit, remote ref or CI state was changed by the
reviewer.

<!-- review-migration:0150:end -->

<a id="migrated-review-0151"></a>
<!-- review-migration:0151:start -->

## 2026-08-05 — P2EXIT-R15 focused re-review

**Reviewer:** Codex (Reviewer)
**Correction base:** `b4aae67`
**Correction head:** `9ff3693`
**Verdict:** **Changes requested.** The plan summary, absent-review claim, main criterion-8 verdict,
P2EXIT-R14 row and row-3.15 sentence are corrected. P2EXIT-R15 remains open because four other live
STATUS siblings still say criterion 8 awaits evidence or remains open while the same document
records it met on the 40/40 run.

### Finding status

| ID | Severity | Blocks approval | Re-review result | Status |
|---|---|---:|---|---|
| `P2EXIT-R15` | High | **Yes — Phase 2 exit truth / criterion 6** | Plan's Phase 2 summary now records criterion 8 met on the third-run evidence and criterion 6 as the only live gate. STATUS correctly says the exit review is in progress, advances its main criterion-8 paragraph through 40/40, marks P2EXIT-R14 resolved, and preserves the old row-3.15 verdict as explicitly superseded history. However, STATUS line 72 still says criterion 8 is a current blocker awaiting the 40-row run; lines 144–145 still say that run plus Windows/Fedora evidence are owed; line 1404 still says “Now: 6 and 8”; and the live heading at line 1421 remains “What criterion 8 still needs.” These are operative claims, not the deliberately quoted historical sentence. | **Open** |

P2EXIT-R12 and P2EXIT-R14 remain resolved. Criterion 8 remains substantively met on the accepted
evidence; no new checklist run, platform evidence, source correction or CI dispatch is required.

### Required correction

Update the four remaining STATUS siblings to the already-canonical state:

- At the T-128 historical paragraph, say the current blocker is criterion 6 alone; criterion 8's
  40-row run is complete.
- In the main criterion-8 account, change the second-run “owes a re-run” sentence into past tense
  and carry it through the third run and Linux-only ruling already stated above and below.
- Change the review introduction's “Now: 6 and 8” to criterion 6 alone.
- Retitle “What criterion 8 still needs” as a historical disposition section, or otherwise state
  that it needs nothing further and the following text explains how the earlier failures closed.

The P2EXIT-R15 table row may remain Open/awaiting re-review until the reviewer resolves it; that is
an accurate process state, not a criterion-8 evidence claim. Preserve the second run at 39/41, the
third at 40/40, and the Linux-only ruling unchanged.

### Independent verification

| Check | Result |
|---|---|
| Boundary | `git diff --check b4aae67..9ff3693`: **pass**. One commit changes plan and STATUS and carries the preceding review record. Checklist and evidence files are byte-unchanged. |
| Accepted corrections | Plan summary: criterion 8 met / criterion 6 only live gate. STATUS: review in progress; main criterion-8 verdict 40/40; P2EXIT-R14 resolved; row 3.15's prior unrun claim explicitly superseded. |
| Negative claim-shape audit | Live hits remain at STATUS lines 72, 144–145, 1404 and 1421. The R15 row is intentionally open pending this review; the Phase 1 and explicitly historical plan hits remain correctly scoped. |
| Placement gate | `tests/unit/test_task_placement.py`: **14 passed**. |

No new test was needed for this records-only correction. The reviewer appends this record only; no
submitted document, source, test, task state, commit, remote ref or CI state was changed by the
reviewer.

<!-- review-migration:0151:end -->

<a id="migrated-review-0152"></a>
<!-- review-migration:0152:start -->

## 2026-08-05 — P2EXIT-R15 final re-review and Phase 2 sign-off

**Reviewer:** Codex (Reviewer)
**Correction base:** `9ff3693`
**Approved at:** `8de5a72`
**Verdict:** **Approved. Phase 2 may exit.** P2EXIT-R15 is resolved, all thirteen deliverables are
approved, and all eight exit criteria are met. The Linux-only human inspection limit for criterion
8 remains an explicit maintainer ruling and accepted residual, not missing evidence silently read
as a pass.

### Finding status

| ID | Severity | Blocks approval | Re-review result | Status |
|---|---|---:|---|---|
| `P2EXIT-R15` | High | No | All four surviving STATUS siblings now agree with the completed 40-row event. The T-128-era paragraph names criterion 6 alone as the then-current blocker and criterion 8 met. The main criterion-8 account carries the second run forward to the 40/40 third run and the recorded platform ruling. The review introduction says “6 alone,” and the disposition heading is past tense. The deliberately retained row-3.15 sentence is explicitly superseded; P2EXIT-R15's Open row correctly awaited this independent resolution. | **Resolved at `8de5a72`** |

P2EXIT-R11 through P2EXIT-R15 and T161-R1 are resolved. P2EXIT-R12's historical evidence remains
39/41 for the second run and 40/40 for the third; row 2.7 remains removed without weakening T-160.

### Final exit reconstruction

| Criterion | Final result |
|---|---|
| 1 | **Met.** Three concurrent jobs, independent accurate progress and an interactive UI; P2EXIT-R11's stale-stage regression is resolved. |
| 2 | **Met.** Hard-kill/restart recovery proof accepted and unchanged. |
| 3 | **Met.** Exact pool limit, clean lowering and queue-level pause behavior accepted and unchanged. |
| 4 | **Met.** Single-instance behavior accepted on both platforms. |
| 5 | **Met.** Corrected N-worker orphan gate accepted; candidate CI is green including `windows desktop`. |
| 6 | **Met by this sign-off.** Thirteen deliverables are approved, the 60-run soak passed, and no blocking review finding remains. |
| 7 | **Met.** The user-visible Add/admission/restart queue route is accepted and unchanged. |
| 8 | **Met.** The maintainer recorded 40/40 live checklist rows passed, including direct observation of row 3.15. Linux-only human inspection is accepted by maintainer ruling; Windows automation is green and the unevidenced Windows visual residual is disclosed. |

### Independent verification

| Check | Result |
|---|---|
| Boundary | `git diff --check 9ff3693..8de5a72`: **pass**. The correction changes STATUS and carries the preceding review record only. |
| Evidence preservation | No checklist or evidence artifact changes in the correction. The second run remains 39/41, the third 40/40, and the Linux-only ruling unchanged. |
| Unfiltered criterion-8 audit | Read all sixteen `criterion 8` occurrences across plan and STATUS. Current claims say met; the remaining non-met/awaiting wording is explicitly dated, quoted, descriptive or attached to P2EXIT-R15's pre-resolution process state. |
| Candidate identity | `git diff 376407f..8de5a72 -- src tests pyproject.toml .github`: **empty**. No later record commit changes the application, tests, build inputs or CI workflow verified for the candidate. |
| CI | GitHub Actions run `31051896815` at `165b6e4`: **success**, all five jobs including `windows desktop`. No further docs-only dispatch is required. |
| Placement gate | `tests/unit/test_task_placement.py`: **14 passed**. |

Known residuals remain visible and non-blocking: no person inspected criterion 8 on Windows; four
known Phase 3 window defects were present during the checklist run; T-151 and T-154's regressions
are guarded on all platforms but reproduce their visual defects on none; and OPS-007's T-074 risk
remains accepted rather than resolved.

This approval covers exact head `8de5a72`. A subsequent review-only commit may carry this record
without changing that boundary. The next coordination update may mark P2EXIT-R15 Resolved,
criterion 6 Met, and Phase 2 exited, then advance current work to Phase 3. No source, test, evidence,
task state, commit, remote ref or CI state was changed by the reviewer.

<!-- review-migration:0152:end -->
