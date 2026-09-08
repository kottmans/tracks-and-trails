# session-evidence-2026-08-20 — Review record

**Purpose:** Dated review evidence and disposition history for this task or shared scope.
**Owner:** Assigned Reviewer · **Update when:** This scope is reviewed or rechecked.
**Covered tasks:** T-074, T-238, T-269, T-270, T-272

[Review index](../REVIEWS.md) · [Review policy](../TESTING.md#14-review-policy)

Moved from `85422bc0b086de9b18d2f809abb4d6bcebb180e4:docs/project/REVIEWS.md` on 2026-09-08.
The entries below retain their exact original bytes and relative order. Historical
path spellings, line citations and references to “above” describe that source;
the [migration manifest](../evidence/2026-09-08-review-migration.json) records the
original order and byte ranges. Shared entries are stored once; covered tasks
link to this same record. Navigation grants no approval or new review provenance.

## Recorded rounds

- [2026-08-20 — session coordination and evidence review](#migrated-review-0308)
- [2026-08-20 — session evidence focused correction re-review](#migrated-review-0309)

<a id="migrated-review-0308"></a>
<!-- review-migration:0308:start -->

---

## 2026-08-20 — session coordination and evidence review

**Reviewer:** Codex (Reviewer)
**Tasks:** `T-074`, `T-238`, `T-269`, `T-270`, `T-272`
**Base:** `5b61279da91b62ff70c48572c0b1db19e6ea662b` (`origin/main` at review start)
**Head:** `bf766b3dffce042607c65e2157cdacf20497911f` — five local, unpushed commits
**Verdict:** **Changes requested.** The completion filing for T-269/T-270 and T-074's move from
Ready to Blocked are sound. The new evidence prose is not ready as current truth: T-238 erases an
earlier 20-run loaded campaign, T-272 equates its POSIX resource-tracker pipe with T-268's distinct
Windows spawn-payload pipe, and T-074 gives a common-rate statistical ceiling to runs drawn from
materially different heads. No product, test, workflow or dependency behavior changed in this
range.

### Findings

| ID | Severity | Blocks approval | Finding | Required correction | Status |
|---|---|---:|---|---|---|
| **T074-R5** | **Medium** | **Yes — the current evidence assigns a stable risk bound to a heterogeneous sample** | The claimed **105 completed Full suite steps and zero native crashes are verified**: GitHub exposes 92 successful and 13 failed step conclusions, and all 13 failures end in ordinary pytest tallies rather than a native-process death. The inference does not follow. These runs span many heads; just the manager and test-lifecycle surfaces changed by **2,886 insertions and 622 deletions** between `bd4dde8` and the last source head `06745fa`. `T074-R1` already ruled that materially changed heads are not one controlled population and required exact-head observations rather than a stable rate. The rule-of-three **2.9% per-run ceiling** assumes exchangeable Bernoulli trials with one underlying probability, which this record does not establish. The enumeration also contains four CI runs with no `Full suite` step at all, in addition to the 22 cancelled and 14 skipped step conclusions the entry names. None changes the correct 105 total, but the method does not account for every run as written. | Keep the exact observation `0/105 completed Full suite steps` and the valid T238-R2 nondiscrimination argument. Remove the stable 2.9% rate claim, or label it explicitly as a conditional pooled calculation whose common-rate premise is not established. Account for the four absent-step runs separately. Preserve the OPS-007 risk decision and T-074's Blocked-on-T-092 disposition; neither depends on the invalid ceiling. | **Open** |
| **T238-R4** | **Medium** | **Yes — the current task record contradicts its own retained campaign evidence** | The new opening says deliberate load “had never been tried,” that all previous 40 runs were idle, and that repetition is spent at **70 = 40 idle + 30 contended**. The same entry later records **60** prior clean runs: 40 idle, **12 under 20 busy loops**, and **8 beside an `-n auto` integration batch**; it explicitly says that deliberate saturation refuted the earlier recommendation. If the new 30-run campaign is distinct, the clean total is **90**, including 50 previously/newly contended runs, not 70. The opening also says a real-test guard firing is the only route left, while the later 2026-08-16 ruling says criterion 4 is *no longer* “wait for the guard to fire” and names a real-session probe plus a widget-cycle check. The new 30-run zero may still be useful as an additional, better-controlled campaign, but it neither pulls an untried lever nor replaces the recorded next investigation. | Rewrite the new section as **30 additional contended runs**, state the cumulative conditions/count accurately, and identify what the continuous three-batch design adds over the prior 12+8 loaded runs. Reconcile its criterion-4 sentence with the later real-session/cycle plan. Keep T-238 Ready and criterion 4 open; this finding does not request a disposition change. | **Open** |
| **T272-R1** | **Medium** | **Yes — the causal distinction rests on two different pipes being treated as one mechanism** | T-268 rules out another process retaining the write end of the Windows **spawn payload pipe**: `popen_spawn_win32` creates `pipe_handle` and starts the child with `bInheritHandles=False`. The Linux specimen is held by the separate **resource-tracker pipe**. `popen_spawn_posix._launch()` obtains `resource_tracker.getfd()`, appends that descriptor to the child pass-FD set, and supplies it independently of the payload `pipe_handle`; the spawned worker is therefore expected to retain the tracker's writer. T-272's one-thread, zero-CPU reader is the `resource_tracker`, not the spawned worker T-268 classifies; the spawned worker has two threads and 157 seconds of CPU. The claim that this is “that eliminated” T-268 mechanism, or the five's one-thread shape reproduced outside Windows, is false. The supported conclusions survive: the scanner finds a Linux spawned-worker orphan, Linux scheduling is absent, the worker is past T-258's pre-payload window, and product reachability is unproved. | Distinguish the resource-tracker and spawn-payload channels in both the task and evidence file. Say this is not T-268's cause because it is a different platform channel/process pair, not because T-268 eliminated the same mechanism. Attribute the one-thread/zero-CPU observation to the tracker and the two-thread/157-second observation to the worker; do not present their union as the five's process shape. | **Open** |
| **T272-R2** | **Low** | **No** | `ai/evidence/README.md` calls its table “What is here now” but does not list the new Linux-orphan artifact or why it satisfies the directory's cannot-be-regenerated rule. The artifact itself does satisfy that rule: it captures read-only state from live specimens that will disappear when those processes exit. | Add the file to the inventory with that retention reason. **Owner/target:** Documentation Maintainer, T-272 correction batch. | **Open, non-blocking** |

### Independent verification

| Check | Result |
|---|---|
| Boundary and scope | **Passed.** `main` was clean and five commits ahead of `origin/main`; `5b61279..bf766b3` changes only `ai/TASKS.md`, `ai/STATUS.md`, and one new evidence file. `git diff --check` passes. No `src/`, test, workflow, dependency, or build path changed. |
| Windows Full suite enumeration | **105 completed steps confirmed:** 92 success + 13 failure. All 13 failed-step logs contain an ordinary pytest completion tally and exit 1; none contains an access violation, fatal Python error, segmentation fault, or exit 139. The full 145-run enumeration also contains 22 cancelled conclusions, 14 skipped conclusions, and four runs where the step is absent. |
| T-074 population audit | The 105 observations are useful as a dated zero count and cannot establish that T-128 caused T-074. They are not an exact-head population: `bd4dde8..06745fa` materially changes `manager.py`, `test_manager.py`, the root/UI conftests and `qt_lifecycle.py` across many commits. This independently reproduces the limitation T074-R1 already recorded. |
| T-238 retained record | The pre-existing conditions table explicitly totals 40 idle + 12 busy-loop + 8 concurrent-integration runs and calls saturation tried. The later criterion-4 section explicitly redirects work to a real session and widget-cycle reachability. Both contradict the newly prepended summary. |
| T-272 mechanism | Local Python 3.14 source confirms POSIX passes `tracker_fd` and `pipe_handle` separately, while the Windows source creates and duplicates only the payload pipe described by T-268. The evidence artifact itself identifies PID 432922 as `resource_tracker` and PID 434366 as `spawn_main`. |
| Entry moves | **Passed.** T-269/T-270 retain their approved evidence while moving to Complete, and STATUS now correctly reports five successful jobs plus the skipped orphan job. T-074's move changes its status/dependency without losing its prior entry; Blocked on T-092 is consistent with its still-unmet dump criterion and OPS-007. |
| Repository gates at head | **Passed:** task placement **15 passed**; `ruff check .`; `ruff format --check .` (**203 files**); commit-message checker (**5 commits**). |

### Review judgments

- **The T238-R2 reasoning transfers to T-074.** Zero before and zero after cannot establish that
  the candidate correction caused the absence. T074-R5 rejects only the unsupported common-rate
  ceiling, not the negative result or the reclassification that rests on it.
- **T-074's Ready-to-Blocked move is accepted as a current-truth correction.** It does not reverse
  OPS-007, alter priority, close any criterion, or claim a diagnosis. T-092 is the real external
  dependency its retained criterion already describes.
- **T-238's disposition is untouched.** This review asks for an accurate campaign record and
  preserves the maintainer's decision to leave criterion 4 open with T-238 Ready.
- **The T-272 scheduling task remains well-founded after narrowing.** A Linux worker orphan was
  found by the existing scanner and no Linux job schedules it. The two live specimens remain
  preserved; this review did not inspect, signal or reap them.
- **The T-269/T-270 completion filing is accepted.** It accurately applies the existing approvals
  and corrects the six-green-jobs sentence without reopening either implementation.

### Readiness

The range is **not approved at `bf766b3`**. Correct T074-R5, T238-R4 and T272-R1 together, and fold
the non-blocking T272-R2 inventory row into that documentation batch. One focused correction
re-review is available and should inspect only those four findings and the correction diff; it
must not reopen T-269/T-270, T-074's accepted board move, or T-238's disposition. The Reviewer
changed only this append-only record. No reviewed task/status/evidence file, source, test,
workflow, dependency, live process, push or remote state was changed.

<!-- review-migration:0308:end -->

<a id="migrated-review-0309"></a>
<!-- review-migration:0309:start -->

---

## 2026-08-20 — session evidence focused correction re-review

**Reviewer:** Codex (Reviewer)
**Tasks:** `T-074`, `T-238`, `T-272`
**Initial reviewed head:** `bf766b3dffce042607c65e2157cdacf20497911f`
**Review-record base:** `2835a30c3400cc1db86de463248b8e5672720e18`
**Correction head:** `d50eef9299d4a6036b736ca39f23f14312847387`
**Additional record head:** `d5b95c5e9adb27a3a0d50c8118a2e5d205367152`
**Verdict:** **Changes requested at `d5b95c5`.** The offered correction is approved at
`d50eef9`: T074-R5, T238-R4, T272-R1 and T272-R2 are Resolved. The two later commits were
explicitly outside that offer, so they are treated as a small initial review of a new record
boundary rather than silently folded into the spent focused pass. They introduce one blocking
uncertainty contradiction in T-272 and one non-blocking false gate tally in STATUS.

### Scope ruling

The focused correction boundary is `2835a30..d50eef9`. `f20876a` records a state change that was
not knowable when the initial review was written, and `d5b95c5` brings canonical STATUS across the
same correction round. Reading them is warranted because they change the same T-272 task/evidence
surfaces and copy the corrected claims into current truth; approving only the superseded head would
leave the actual handoff head unreviewed. This additional review does not reopen T-269/T-270,
T-074's accepted board move, T-238's disposition, or any source/test behavior.

### Original-finding disposition

| ID | Severity | Blocks approval | Focused result | Status |
|---|---|---:|---|---|
| **T074-R5** | **Medium** | Yes | The entry accounts separately for the four runs with no Windows-desktop job, reconciles all 145 runs, keeps the verified 0/105 completed-step observation and nondiscrimination argument, and explicitly withdraws the 2.9% pooled ceiling because these changed heads are not one established population. OPS-007 and the Blocked-on-T-092 disposition remain independent of that ceiling. | **Resolved at `36677b8`** |
| **T238-R4** | **Medium** | Yes | The new campaign is 30 **additional** contended runs: 90 total over four conditions, 50 contended. The entry distinguishes continuous real Python/Qt contention from the earlier busy loops and one finite integration batch, and restores the real-session probe plus widget-cycle question as criterion 4's next work. T-238 remains Ready. | **Resolved at `cc8dd89`** |
| **T272-R1** | **Medium** | Yes | The task and evidence file now distinguish the POSIX resource-tracker channel from the Windows spawn-payload channel, assign one thread/0 CPU to the tracker and two threads/157 seconds to the worker, and withdraw both the eliminated-mechanism and reproduced-shape claims. The surviving scheduling observation remains accurately narrow. | **Resolved at `d50eef9`** |
| **T272-R2** | **Low** | No | The evidence inventory names the Linux-orphan artifact and states why the vanished live-process state cannot be regenerated. | **Resolved at `d50eef9`** |

### New findings on the additional record boundary

| ID | Severity | Blocks approval | Finding | Required correction | Status |
|---|---|---:|---|---|---|
| **T272-R3** | **Medium** | **Yes — current truth converts an explicitly unexcluded intervention into a natural-exit fact** | The measurement establishes that both PIDs later disappeared, the host did not reboot, both scans were report-only and nothing **in this session** signalled them. It explicitly says an outside kill or cleanup on the shared machine was neither observed nor excluded. The same T-272 entry then says both processes “ended on their own before anyone inspected or released them”; its opening says they “expired anyway.” The evidence file says the specimen was lost “without anyone deciding to spend it,” the inventory abbreviates the result to “nothing signalled” and “expired anyway,” and STATUS repeats that nobody decided. Those are global causal/intent claims the retained evidence disclaims, and whether an unknown external actor inspected or deliberately released the pair cannot be recovered after the fact. | Across the task, evidence inventory, evidence conclusion and STATUS, state only what was observed: the PIDs are gone, no reboot occurred, and this session did not signal them. Keep external termination, inspection and deliberate release unknown. The preservation criterion can be overtaken because no specimen remains available; it cannot say nobody fulfilled or deliberately ended it. Audit every sibling copy as one defect class. | **Open — additional-record correction** |
| **COORD-R24** | **Low** | No | STATUS reports task placement as **16 passed, 2 skipped** at `f20876a`. `tests/unit/test_task_placement.py` collects and passes **15 tests, with no skips**; `d5b95c5` changes only STATUS, so the board input and test file are identical at both heads. The gate passed, but the recorded exact result is not its result. | Replace the tally with the actual **15 passed**, or name the different command whose result was recorded. **Owner/target:** Documentation Maintainer, the T272-R3 correction batch; no separate re-review required. | **Open, non-blocking** |

### Independent checks

| Check | Result |
|---|---|
| Correction boundary | `2835a30..d50eef9` is documentation only: one task file plus the T-272 evidence artifact and inventory. The three commits remain separated by owning task and answer only the four reviewed findings. |
| T-074 correction | The unsupported ceiling appears only as a withdrawn claim; 92 + 13 + 22 + 14 + 4 reconciles to 145, while the completed population remains 105. The pre/post zero comparison is still explicitly nondiscriminating. |
| T-238 correction | The retained conditions now agree at 40 idle + 12 busy-loop + 8 concurrent-integration + 30 continuously contended = 90, with 50 contended. The later criterion-4 ruling and the new summary name the same two next steps. |
| T-272 correction | Both corrected records name the two channels and two process roles separately. No surviving sentence presents the one-thread tracker and 157-second worker as one shape or calls the tracker channel T-268's eliminated payload mechanism. |
| Later specimen state | PID absence plus a no-reboot observation proves that this Linux pair had finite process lifetimes. It does **not** identify why either process ended or exclude another session's signal, inspection or cleanup. |
| Boundary hygiene | `git diff --check 2835a30..d5b95c5` passed. The five commits change only `ai/TASKS.md`, `ai/STATUS.md` and two files under `ai/evidence/`; no source, test, workflow, dependency or build path changed. |
| Current focused gates | Task placement: **15 passed**. Ruff: passed. Ruff format: **203 files already formatted**. Commit-message checker: **5 commits checked** in `2835a30..d5b95c5`. The full suite was not run and is not required for this documentation-only boundary. |

### Review judgments

- **The “did not persist indefinitely” sentence is sound.** Both PIDs were present and later
  absent without a reboot, so this pair's lifetimes were finite. The sentence confines that fact to
  Linux and expressly says it does not explain the distinct Windows specimens. T272-R3 concerns
  the stronger sibling claims about *why* they ended and whether anybody acted.
- **The shared stale-summary pattern is a fair synthesis, but not the whole of T272-R1.** Each of
  the three blocking corrections did repair a summary contradicted by retained evidence. T272-R1
  additionally required identifying two different platform channels; STATUS preserves that
  technical correction explicitly, so the synthesis does not erase it.
- **The extra boundary receives its own pass budget.** T272-R3 is the initial finding on
  `d50eef9..d5b95c5`, not a new Medium discovery charged to the completed focused pass on the four
  original findings. One focused correction re-review is available for it.

### Readiness

The original evidence correction is **approved at `d50eef9`**. T-074 and T-238 need no further
review from this batch, and T272-R1/R2 are Resolved. The actual handoff head `d5b95c5` is **not
approved**: correct T272-R3 across all copies and fold in COORD-R24's tally. The next pass is focused
only on those two items and their correction diff.

The Reviewer changed only this append-only record. No reviewed task/status/evidence file, source,
test, workflow, dependency, live process, push or remote state was changed.

<!-- review-migration:0309:end -->
