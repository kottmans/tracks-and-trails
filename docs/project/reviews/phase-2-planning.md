# phase-2-planning — Review record

**Purpose:** Dated review evidence and disposition history for this task or shared scope.
**Owner:** Assigned Reviewer · **Update when:** This scope is reviewed or rechecked.
**Covered tasks:** T-033, T-072

[Review index](../REVIEWS.md) · [Review policy](../TESTING.md#14-review-policy)

Moved from `85422bc0b086de9b18d2f809abb4d6bcebb180e4:docs/project/REVIEWS.md` on 2026-09-08.
The entries below retain their exact original bytes and relative order. Historical
path spellings, line citations and references to “above” describe that source;
the [migration manifest](../evidence/2026-09-08-review-migration.json) records the
original order and byte ranges. Shared entries are stored once; covered tasks
link to this same record. Navigation grants no approval or new review provenance.

## Recorded rounds

- [2026-07-29 — Previously excluded work review](#migrated-review-0095)
- [2026-07-29 — P2PLAN-R1 / P2PLAN-R3 focused correction re-review](#migrated-review-0101)

<a id="migrated-review-0095"></a>
<!-- review-migration:0095:start -->

## 2026-07-29 — Previously excluded work review

**Reviewer:** Codex (Reviewer)
**Authorization:** The maintainer requested review of every committed boundary that earlier
reviews explicitly excluded
**Boundaries:**

- T-033 record correction: commit `26c1d4e`
- Phase 2 task and decision planning: `71ca6dc..70c96e9`
- Approved-task filing cleanup: `66e96d5..68eb7b6`
- T-072 final WIN-R1 evidence and current coordination: `68eb7b6..b0a6e07`

**Concurrent-work exclusion:** Claude's active, uncommitted T-074 correction in
`core/logging.py` and `test_logging.py` was not read as a finished boundary and is not covered by
this review.

**Verdict by scope:** T-072 **Approved**; T-033's record correction **Accepted with a
non-blocking cleanup**, while T-033 remains Blocked on T033-R4 and Windows evidence; approved-task
filing **correct for T-075 through T-077 but incomplete at the current head**; Phase 2 planning
**Changes requested before any task becomes Ready**

### T-072 final disposition

WIN-R1 supplies the exact evidence the preceding review required. The maintainer first established
the defective existing state—both profile and remote address were `Any`—then ran the real
`ssh-setup.ps1` existing-rule branch. Its own readback reported `Private` and `LocalSubnet`, and
the independent readback reported the same pair. `key already authorised` also exercises the
idempotent append path without replacing the administrator key file.

The evidence is not vacuous: the precondition would have stopped the procedure before the repair
if the broad state had not actually been created. The script path had already been statically
reviewed; runtime execution was the sole remaining condition. WIN-R1 is therefore **Resolved**,
all five T-072 carries are discharged, and **T-072 is Approved**.

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `COORD-R8` | **Medium** | **Yes — Phase 1 exit review** | Current TASKS still gives three incompatible live answers after `b0a6e07`. The start-here bullet calls T-072 **In Progress** and says WIN-R1 remains; T-072's own entry says all five carries are discharged and STATUS calls it complete and in review. T-073 is still filed under In Review with “approved with a documentation follow-up,” although `T073-R1` was independently Resolved at `9802a6a` and the later review explicitly approved T-073. After this review, T-072 is Approved too, so the In Review section should contain only active T-074, not three tasks. The opening “crash, a carry, and frozen-artifact evidence” summary likewise retains a carry that is now closed. These are the exact placement/current-truth failures COORD-R5 through R7 were intended to prevent, and they materially misstate what remains before the exit review. | File T-072 and T-073 under Complete, narrow In Review to T-074, and rewrite the start-here blocker list from the final dispositions. Preserve superseded readings only as explicitly historical text. | **Open** |
| `T033-R5` | **Low** | **No** | Commit `26c1d4e` correctly separates the two collection mutations and records T033-R4 and the Windows build as the blockers. One attached sentence in the status block still says T033-R1 remains open for “the Windows frozen result and the collection-removal negative run,” immediately after saying the Linux negative is complete. The entry also contains the identical `Phase:` field twice. Neither changes T-033's correctly Blocked disposition, but both are current-truth defects in the correction whose purpose was to reconcile that record. | Remove the completed negative run from the remaining T033-R1 evidence and deduplicate the Phase field when T-033 is next edited. | **Open, non-blocking** |
| `P2PLAN-R1` | **Medium** | **Yes — Phase 2 planning** | The accepted REQ-015 amendment makes pause/resume **queue-level** and lets in-flight work drain. The higher-level IMPLEMENTATION_PLAN still requires a queue view with **per-job pause/resume**, while T-080 remains titled “Pause, resume, retry and remove, per job.” Its current Scope quotes the old requirement as though it still governs and says REQ-015 “needs” the amendment already made in the same commit. The task's later acceptance criteria describe queue-level behavior. A Phase 2 implementer therefore receives mutually exclusive instructions from the plan and from different halves of the task. | Amend the Phase 2 deliverable to queue-level pause/resume; retitle and rewrite T-080 from current truth, with per-job cancel/retry/remove separated from queue pause/resume. Move the old requirement wording to explicit history or the decision rationale. | **Open** |
| `P2PLAN-R2` | **Medium** | **Yes — T-087 and durable Phase 2 choices** | Commit `70c96e9` says it records three decisions, but no decision was added to `ai/DECISIONS.md`. QLocalServer keyed from the resolved database path is an architectural, cross-platform choice made over lock files, mutexes, sockets, and `flock`; T-087 itself says it wants a DECISIONS entry first and requires an ID. Queue-draining pause and remove-never-deletes are also durable user-visible trade-offs whose rationale currently lives only in a mutable task. This conflicts with AGENTS §12's canonical home for durable choices and leaves the commit's “recorded” claim false. | Add accepted decision entries for the queue action semantics and the single-instance mechanism, including crash recovery, database-path name derivation, and alternatives. Link their IDs from REQ-015, T-080, and T-087 before those tasks become Ready. | **Open** |
| `P2PLAN-R3` | **Medium** | **Yes — T-078 readiness** | REQ-013 and the Phase 2 deliverable require a **user-configurable** concurrency limit. T-078 calls it the first setting with runtime effect but leaves where it lives as a decision for the implementer, while the full settings dialog is assigned to Phase 4. Its acceptance criteria prove that different N values work but never require a user-accessible, persisted way to select N. The task can therefore pass with only a constructor or test seam and still miss the product requirement at the centre of the phase. | Decide and state the Phase 2 configuration surface and persistence boundary—whether a minimal settings control lands now or a narrower approved mechanism precedes Phase 4—and add an acceptance criterion that changes the limit through that real user-facing path. | **Open** |
| `P2PLAN-R4` | **Low** | **No** | T-084 simultaneously requires per-job logs to be “verbatim” and requires credential/cookie redaction. REQ-026 makes the redaction mandatory, so the literal word “verbatim” cannot govern sensitive substrings. The task also says T-053 is the concurrency proof it rests on without making the ordering explicit. | Say “verbatim except for mandatory handler-level redaction” and make T-053 an explicit prerequisite or an acceptance test owned by T-084. | **Open, non-blocking** |

### Independent verification

| Check | Result |
|---|---|
| Working-tree isolation | Only Claude's two active T-074 source/test files were modified; all reviewed material came from committed objects |
| `git diff --check` on all four reviewed boundaries | Passed |
| Authorship / trailers | Sean Kottman throughout; no AI author or co-author trailer |
| WIN-R1 setup gate | Evidence states and checks `Any / Any` before invoking the repair |
| WIN-R1 repair branch | Real script's existing-rule path reapplies scope and reads rule/address filters separately |
| WIN-R1 result | Maintainer-recorded `Private / LocalSubnet`, with `WIN-R1 PASS` |
| T-033 correction | Correctly preserves T033-R4, data-file load bearing, submodule uncertainty, and external Windows evidence |
| Phase 2 deliverable mapping | T-078 through T-087 map every Phase 2 plan deliverable; T-088 owns all six exit criteria |
| Tests | Not run: every reviewed commit is documentation, planning, or external evidence only |

### Phase transition disposition

The previously excluded work does not hide another unreviewed production implementation.
T-072 is approved, T-073 was already approved, and T-033 gates Phase 5 rather than Phase 1.

Phase 1 still cannot exit today. T-074 remains in active correction and the explicit T-066
frozen-artifact evidence blocker remains. COORD-R8 must then make the current-truth files agree,
after which the Phase 1 exit review can be called.

Phase 2's task coverage is otherwise complete, but P2PLAN-R1 through R3 should be corrected before
the first task is promoted from Proposed to Ready. They do not require production work; they
require one coherent pause contract, durable decision records, and a real user configuration
surface for the concurrency limit.

<!-- review-migration:0095:end -->

<a id="migrated-review-0101"></a>
<!-- review-migration:0101:start -->

## 2026-07-29 — P2PLAN-R1 / P2PLAN-R3 focused correction re-review

**Reviewer:** Codex (Reviewer)
**Base:** `6768f06`  **Head:** `8306378`
**Boundary treatment:** two documentation-only planning commits. P2PLAN-R2 and ARC-006 were
already approved and were not re-reviewed. This pass verifies the P2PLAN-R1 reconciliation against
accepted UX-001 and the P2PLAN-R3 correction against REQ-013, DAT-001 and the existing settings
ownership.
**Verdict:** **Approved with non-blocking follow-ups — all three Phase 2 planning gates are clear**

P2PLAN-R1 and P2PLAN-R3 are Resolved. Together with the prior P2PLAN-R2 approval, the condition
recorded by the initial Phase 2 planning review is now met. T-078 may be promoted from Proposed to
Ready; downstream Phase 2 tasks remain governed by their stated dependencies.

### Finding disposition

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `P2PLAN-R1` | **Medium** | **No — resolved** | IMPLEMENTATION_PLAN now separates queue-level pause/resume from per-job cancel/retry/remove and adds queue draining to the exit criterion. T-080 is retitled, its two granularities are explicit, and its test criterion rejects a single-job pause as proof of the queue contract. The stale pre-amendment reading is marked historical. | None. | **Resolved** |
| `P2PLAN-R3` | **Medium** | **No — resolved** | Accepted ARC-007 gives the setting a durable owner (`core/settings.py` / `settings.toml`), a reachable Phase 2 control in the existing main window, live raise/drain semantics, and an injected manager boundary. T-078 must drive the real control, prove restart persistence, and handle missing, malformed and below-minimum file values at the settings layer. A constructor-only seam cannot pass those criteria. | None. | **Resolved** |
| `P2PLAN-R6` | **Low** | **No — T-078 is not implemented** | ARC-007 says `downloader/manager.py` receives a value and never reads `core/settings.py`, but neither static boundary analyzer enforces that dependency. A synthetic `from tracks_and_trails.core import settings` produced no layering violation and no manager-boundary offender; all 130 existing boundary tests remained green. | Extend the manager-boundary analyzer with an independently mutation-checked prohibition on direct `core.settings` imports in `downloader/manager.py`. | **Open, non-blocking — T-097; required by T-078 approval, not readiness** |
| `P2PLAN-R7` | **Low** | **No — T-080 remains Proposed** | The P2PLAN-R1 correction also adds “manual retry re-enters at the back and does not jump waiting jobs.” UX-001 does not decide retry order, REQ-018 only requires retry, and T-083's existing no-jump criterion is explicitly about automatic retries. The policy is coherent with queue fairness, but it is new task scope rather than reconciliation from UX-001. | Before T-080 starts, either confirm this as the manual-retry consequence of the scheduler T-078 records or remove it; do not describe it as part of P2PLAN-R1's already-made pause decision. | **Open, non-blocking — T-080** |

### Focused challenges

**The PAUSED-edge deferral is accepted.** UX-001 itself assigns T-080 the choice to remove the
unreachable transitions or record why they remain. REQ-017 supplies a concrete Phase 3 reopening
condition, so choosing with the implementation in view is not missing product semantics. T-080
cannot silently ignore the issue: its Scope names the choice and its acceptance criteria require
that no Phase 2 job reaches `PAUSED`.

**ARC-007 closes the user-path hole.** A TOML file alone would have invited the same argument as a
constructor seam. The existing-main-window control is reachable in T-078's own sequence, persists
through the already-assigned settings owner, and applies live. The decision also avoids pulling
Phase 4's eight-setting dialog forward. Missing and malformed files fall back to the REQ-013
default, while invalid values are constrained below the widget, so direct file editing cannot
create a zero-slot pool.

**“Clear” means independently resolved here.** The initial planning review said R1 through R3 must
be corrected before the first promotion, and AGENTS §10 says only the Reviewer marks findings
Resolved. Holding T-078 at Proposed until this verdict was therefore the sound reading. This review
clears that condition; it does not promote every dependent task at once.

**The Phase 2 exit wording remains binding.** IMPLEMENTATION_PLAN now requires both lowering the
limit and pausing the queue to drain. T-080 owns the queue-pause behavior, and T-088's acceptance
criterion still requires one test for every current plan exit criterion. Its explanatory inventory
abbreviates the concurrency bullet to lowering the limit, but cannot narrow the higher-authority
plan; mirror the full wording when T-088 is prepared rather than treating the shorthand as an
exclusion.

### Independent verification

| Check | Result |
|---|---|
| Boundary / working tree | `6768f06..8306378`, two commits; clean before reviewer record edits; `HEAD == origin/main == 8306378` |
| Changed surfaces | DECISIONS, IMPLEMENTATION_PLAN, STATUS and TASKS only; no production or committed test file changed |
| `git diff --check 6768f06..8306378` | Passed |
| Authorship / trailers | Sean Kottman for both commits; no AI author or co-author trailer |
| UX-001 / REQ-015 / plan / T-080 mapping | Queue pause/resume and per-job cancel/retry/remove agree; stale wording is explicitly historical |
| REQ-013 / DAT-001 / architecture / ARC-007 / T-078 mapping | Owner, location, UI surface, live propagation, restart persistence, default and minimum agree |
| Current static-boundary suites | **130 passed in 0.20 s** |
| Direct manager → settings synthetic import | **Not detected**, confirming P2PLAN-R6 and T-097 |
| Full suite, lint and type gates | Not rerun for this documentation-only boundary; implementer reports **1450 passed**, Ruff clean, format clean, and both mypy gates clean at 78 files |

### Final disposition

P2PLAN-R1 and P2PLAN-R3 are **Resolved at `8306378`**. The correction is planning-complete and
T-078 may become Ready. The PAUSED-state choice remains deliberately owned by T-080 rather than
being mistaken for an unresolved planning decision.

P2PLAN-R6 is carried to T-097 as non-blocking pre-implementation test infrastructure.
P2PLAN-R7 is carried to T-080 for explicit confirmation before that dependent task starts. Neither
finding reopens the corrected planning gates or delays T-078 readiness.

<!-- review-migration:0101:end -->
