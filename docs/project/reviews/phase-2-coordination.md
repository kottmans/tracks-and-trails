# phase-2-coordination — Review record

**Purpose:** Dated review evidence and disposition history for this task or shared scope.
**Owner:** Assigned Reviewer · **Update when:** This scope is reviewed or rechecked.
**Covered tasks:** T-083, T-118, T-119

[Review index](../REVIEWS.md) · [Review policy](../TESTING.md#14-review-policy)

Moved from `85422bc0b086de9b18d2f809abb4d6bcebb180e4:docs/project/REVIEWS.md` on 2026-09-08.
The entries below retain their exact original bytes and relative order. Historical
path spellings, line citations and references to “above” describe that source;
the [migration manifest](../evidence/2026-09-08-review-migration.json) records the
original order and byte ranges. Shared entries are stored once; covered tasks
link to this same record. Navigation grants no approval or new review provenance.

## Recorded rounds

- [2026-08-03 — CI corrections and Phase 2 roadmap review](#migrated-review-0120)
- [2026-08-03 — Coordination corrections focused re-review](#migrated-review-0121)

<a id="migrated-review-0120"></a>
<!-- review-migration:0120:start -->

## 2026-08-03 — CI corrections and Phase 2 roadmap review

**Reviewer:** Codex (Reviewer)
**Review boundary:** `2ec9c45..7202a5d`
**Handoff head inspected:** `71fa992` (handoff only after the reviewed boundary)
**Overall verdict:** **CI corrections approved; changes requested for the coordination record.**
The corrected T-083 test wait and `OPS-009` workflow implementation are sound. The rebuilt
current-truth documents still give incompatible instructions about Phase 2 sign-off and the merged
T-118/T-119 correction, and the task ledger has not actually filed three tasks it says are filed.

### Component verdicts

| Component | Verdict | Reason |
|---|---|---|
| T-083 retry-test correction | **Approved at `6c38d5f`** | The wait now observes the final automatic attempt's durable `FAILED` outcome before testing the bound. The following one-second event-pumping hold is twenty times the installed 50 ms backoff, so the ordinary fourth-attempt mutation is observable after the session releases. The final exact count and manual-retry assertions remain. T-083's production implementation and prior approval are unchanged. |
| `OPS-009` frozen-workflow correction | **Approved at `6c38d5f`** | `runner.environment` is a documented two-valued runner property, both branches executed in run `30826638984`, and the frozen build and smoke passed on both hosted Ubuntu and self-hosted Windows. `matrix.name` now supplies distinct artifact names and non-empty platform evidence. |
| Phase 2 / UI-rework coordination | **Changes requested at `7202a5d`** | The plan's rebuilt table is useful, but STATUS and TASKS contradict its exit state, the maintainer's merged-task decision, and the recorded task approvals. |
| T-118 source | **Not re-reviewed** | This boundary records the known T-118 failures but does not change their source. T118-R6 through T118-R10 remain open under the prior verdict. |

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `COORD-R13` | **Medium** | **Yes — coordination record** | Phase 2 exit truth | `IMPLEMENTATION_PLAN.md:183-191` and criterion 6 at `:329` correctly say the phase has **not** exited: all deliverables are approved, but independent phase sign-off is absent, and T-118/T-119 is only a maintainer sequencing edge. `STATUS.md:19-22` instead says criterion 6 is met and that T-118 is what remains open. That turns a lower-authority sequencing decision into the exit criterion and materially misstates phase readiness. | Make STATUS use the plan's distinction verbatim: 13/13 deliverables approved; criterion 6 pending an independent phase exit review; T-118/T-119 precedes that review only because of the named maintainer sequencing decision. | **Open** |
| `COORD-R14` | **Medium** | **Yes — coordination record** | T-118/T-119 merged scope | The new text says T-118 and T-119 are one task (`TASKS.md:99-107`, `:887-893`), but the executable task instructions still say queue rendering is out of T-118 (`:187-191`) and T-119 depends on T-118 (`:897`), making the combined work depend on itself. T-118 also retains T-105 as a dependency at `:146-147` after accepted UX-004 explicitly removed it as this correction's prerequisite (`DECISIONS.md:2586`); because T-119 still names T-105 too, the merged record does not say whether that original dependency is deliberately retained for the combined work. STATUS compounds the ambiguity by leaving “T-119 is deliberately not started” at `:62-64` immediately before “corrected as one task” at `:66-71`. An implementer cannot tell whether to start, what owns the delegate, or which prerequisite governs it. | Express one actionable work item. Either subsume T-119 into T-118 and move its scope/criteria under that task, or keep two tasks with a non-circular delivery order. Remove the obsolete hold and out-of-scope line, remove T-105 from T-118 as UX-004 requires, and state explicitly whether T-119's original T-105 dependency survives the merge. Preserve T-119's caching/accessibility criteria rather than losing them during the merge. | **Open** |
| `COORD-R15` | **Medium** | **Yes — coordination record** | Canonical task ledger | The In Review note says T-115, T-117 and T-120 are approved and filed under Complete (`TASKS.md:81-85`), but T-115 remains an `In Review` entry at `:241-258`, T-117 remains an `In Review` entry at `:195-205`, and no `### T-120` task entry exists anywhere in the file. `test_task_placement.py` still passes because the stale entries' status text agrees with their stale section; it cannot compare the ledger to review verdicts. This is the same approval/queue drift the roadmap rebuild claims to close and affects the evidence for Phase 2 readiness. | File T-115 and T-117 under Complete with their approved heads and resolved findings, and restore/file T-120 under Complete at `44091a1`. Then rebuild the In Review count from the actual section, not its leading prose. | **Open** |
| `COORD-R16` | **Low** | No | Exact-run evidence wording | STATUS `:103-106` and the handoff evidence table describe the desktop “full suite” as **1929 passed, 0 failed**. Run `30826638984` concluded failure: those 1929 test calls passed, but two teardown errors made the job red. The errors are disclosed later, so this is not hidden evidence, but presenting only the failure count makes a failed full-suite job look green and calls the self-hosted desktop run “hosted” in the handoff. | Report the whole result together: 1929 passed plus two teardown errors, job failed; identify the desktop as self-hosted. State narrowly that the corrected T-083 test passed and the frozen Windows job passed. | **Open, non-blocking** |

### Review judgments requested in the handoff

**The corrected T-083 gate is stronger for the failure actually observed.** The old predicate
returned as soon as attempt three *started*, then gave that worker a fixed second to finish. The new
predicate cannot return until attempt three has persisted `FAILED`; only then does it hold for
twenty patched backoffs and assert the exact attempt count. The fake child sends `Failed` and
`WorkerFinished` in order, and the hold continues pumping events, so a fourth ordinary retry has a
free lane and becomes visible. A hypothetical retry delayed beyond twenty times its configured
backoff is not covered, but neither was it covered by the old finite wait; that is not a weakening
of this gate.

**T-116 did not cause the observed `PROBING` row.** `start()` captures the expected transition and
`entering()` recomputes `_ENTRY_STATUS` from the row at persistence time (`manager.py:1129-1143`).
A row already moved to `FAILED` yields no goal, declines the pending start and cannot be written
back to `PROBING`. The observed attempt count of three with `PROBING` is the final retry already in
flight, exactly the state the old test raced.

**`runner.environment` is the right boundary.** It expresses the property that matters—who owns
the machine—rather than coupling provisioning safety to a matrix display name. GitHub's runner
context documents only `github-hosted` and `self-hosted`; run `30826638984` exercised both values.

### Independent verification

| Check | Result |
|---|---|
| Boundary and tree | `2ec9c45..7202a5d` inspected; `git diff --check` passed. `HEAD == origin/main == 71fa992`; the tree was clean before this review record. |
| Focused local checks | Corrected bounded-retry test plus `tests/unit/test_task_placement.py`: **15 passed in 2.69 s**. |
| Exact Actions run | Run `30826638984`, SHA `6c38d5f91607a0fd7b6dd602aa274b88f22ccfa1`, conclusion **failure** from known T-118 failures. Hosted Ubuntu passed. Hosted Windows finished **1 failed / 1928 passed / 21 skipped / 32 deselected** on T118-R10. The self-hosted desktop reached the corrected T-083 case but ended with two recorded T-118 teardown errors. |
| Frozen branch coverage | `frozen ubuntu-latest`: setup-python success, machine check skipped, build/smoke success. `frozen windows`: setup-python skipped, machine check success, build/smoke success. |
| Runner expression authority | GitHub Actions' official runner-context reference lists `runner.environment` as a string whose possible values are `github-hosted` and `self-hosted`; step-level `if` permits the runner context. |
| Task-ledger gate | `tests/unit/test_task_placement.py`: **14 passed**, but direct ledger inspection shows why it cannot catch COORD-R15: the stale status and stale section agree. |

### Final disposition

The T-083 test-only correction and `OPS-009` workflow correction need no further implementation
pass. T-083 and T-116 retain their prior approvals. The roadmap/coordination batch needs one focused
reconciliation of COORD-R13 through COORD-R15; COORD-R16 is non-blocking evidence cleanup. T-118's
existing source verdict is unchanged, and its two newly observed teardown defects remain part of
that correction rather than this CI/docs review.

No reviewed source, tests or workflow files were edited. This review record is the only reviewer
change; nothing was committed or pushed.

<!-- review-migration:0120:end -->

<a id="migrated-review-0121"></a>
<!-- review-migration:0121:start -->

## 2026-08-03 — Coordination corrections focused re-review

**Reviewer:** Codex (Reviewer)
**Submitted span:** `7202a5d..890fb5d`
**Focused correction boundary:** `71fa992..890fb5d`
**Correction commit:** `890fb5d`
**Overall verdict:** **Approved with follow-up.** COORD-R13 through COORD-R16 are resolved. One
non-blocking current-truth sentence and one Markdown typo remain; neither changes the task queue,
phase gate, or T-118 scope, so T-118 may proceed.

The submitted span contains two commits: `71fa992` adds the prior handoff and `890fb5d` contains the
coordination corrections. The latter is the one-commit re-review boundary.

### Prior-finding resolution

| Finding | Result |
|---|---|
| `COORD-R13` | **Resolved.** STATUS now says 13/13 Phase 2 deliverables are approved while criterion 6 remains unmet pending an independent phase exit review. It names T-118's position before that review as a maintainer sequencing choice, not a phase criterion. This agrees with the higher-authority plan and its criterion-6 row. |
| `COORD-R14` | **Resolved.** T-119 is a `Cancelled — subsumed into T-118` tombstone, not a second actionable task. T-118 removes the queue-rendering exclusion and T-105 dependency, carries T-119's affected surfaces, context, complete acceptance criteria and risk, and has no circular dependency. STATUS and the plan describe the same single item. |
| `COORD-R15` | **Resolved.** T-115, T-117 and restored T-120 each appear exactly once under Complete at their reviewed heads. In Review contains exactly T-118, and the leading count says one. The placement test passes against the corrected ledger. |
| `COORD-R16` | **Resolved.** STATUS and the handoff identify `windows desktop` as self-hosted and report the whole result together: corrected T-083 test passed, 1929 test calls passed, two teardown errors, job failed. The frozen Windows success remains stated separately. |

### New non-blocking follow-up

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Owner / target | Status |
|---|---|---:|---|---|---|---|---|
| `COORD-R17` | **Low** | No | Current-truth prose / Markdown | STATUS `:85-88` still calls the earlier T-083/OPS-009 fixes “two red gates on main” and says neither correction has been reviewed, although the review committed at this same head approves both. `IMPLEMENTATION_PLAN.md:391-393` also attempts to nest backticks in `` `Cancelled — subsumed into `T-118`` ``, producing malformed inline code. Neither changes the now-correct gate or task state. | Say the two gate corrections were approved in the preceding review and leave only T-118 red. Render the tombstone without nested backticks, for example **Cancelled — subsumed into T-118**. | Documentation Maintainer; next coordination/status update before the Phase 2 exit review | **Open, non-blocking** |

### Independent verification

| Check | Result |
|---|---|
| Boundary | `71fa992..890fb5d` inspected; the wider submitted span contains the prior handoff as a separate commit. `git diff --check` passed for both spans. |
| Change isolation | No files under `src/`, `tests/`, `.github/` or `pyproject.toml` changed in the focused correction. T-118 source and its existing verdict are unchanged. |
| Task placement | `tests/unit/test_task_placement.py`: **14 passed in 0.09 s**. |
| Ledger audit | Exactly one heading each for T-115, T-117, T-119 and T-120. T-115/T-117/T-120 are under Complete; T-119 is the subsumed tombstone; T-118 is the only In Review entry. |
| Scope preservation | All seven T-119 acceptance criteria, its cache policy, affected surfaces, accessibility rule, out-of-scope history rendering and risk are carried into T-118. T-105 is explicitly not a dependency of the merged correction. |

### Final disposition

The coordination correction is approved at `890fb5d`; no maintainer waiver is needed. COORD-R17
is a non-blocking documentation follow-up and does not consume another correction pass or prevent
work on T-118. Phase 2 criterion 6 remains pending the independent phase exit review, exactly as
the corrected plan and status say.

No reviewed coordination/source/test files were edited. This review record is the only reviewer
change; nothing was committed or pushed.

<!-- review-migration:0121:end -->
