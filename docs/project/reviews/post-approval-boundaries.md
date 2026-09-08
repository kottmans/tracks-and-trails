# post-approval-boundaries — Review record

**Purpose:** Dated review evidence and disposition history for this task or shared scope.
**Owner:** Assigned Reviewer · **Update when:** This scope is reviewed or rechecked.
**Covered tasks:** T-212, T-268, T-289, T-298

[Review index](../REVIEWS.md) · [Review policy](../TESTING.md#14-review-policy)

Moved from `85422bc0b086de9b18d2f809abb4d6bcebb180e4:docs/project/REVIEWS.md` on 2026-09-08.
The entries below retain their exact original bytes and relative order. Historical
path spellings, line citations and references to “above” describe that source;
the [migration manifest](../evidence/2026-09-08-review-migration.json) records the
original order and byte ranges. Shared entries are stored once; covered tasks
link to this same record. Navigation grants no approval or new review provenance.

## Recorded rounds

- [2026-08-29 — Post-approval boundary and T-298 initial review](#migrated-review-0344)
- [2026-08-29 — Post-approval correction focused re-review](#migrated-review-0345)

<a id="migrated-review-0344"></a>
<!-- review-migration:0344:start -->

---

## 2026-08-29 — Post-approval boundary and T-298 initial review

**Reviewer:** Codex (Reviewer)
**Boundary:** `0332a688815b66200dbfbfe2c7967500105972e6..afe116a896416ba5fc374c2354110fef98cf1264`
**T-298 implementation:** `efa0ce5850d94a3dea8398e7a9f7242fc7e01fbd`, corrected at
`a93a53beeb95e7b88d7e471f0d1a3aa98b8db3b4`
**T-298 external-evidence head:** `53b4d028d1e31417a59a6d1602c4418c6ef65a7d`
**Other tasks inspected:** `T-212` completion synchronization, `T-268`, `T-289`
**Verdict:** **T-298 Approved at `a93a53b`.** The first implementation did disable all CI by using
the unavailable `runner` context at job level; the correction moves profile construction into a
runner-assigned step, and two later frozen jobs on the exact machine that exposed the defect prove
the repaired behavior. The Windows leg has weaker negative-control evidence than Linux, but the
variable consumers, exported values and real update/revert execution are sufficient. No T-298
blocker remains.

`T268-R1` is **Resolved** by the requested non-destructive machine-local inspection. `T-268` is not
approved in this record: one of its own current-truth acceptance records still contradicts the new
measurement. `T-289` remains Proposed and unfixed; its claimed reproduction is correctly
withdrawn. None of those dispositions reopens T-298.

### T-298 acceptance and evidence

| Criterion | Review result |
|---|---|
| Fresh profile, both matrix legs | The setup step constructs a run/attempt-specific root beneath `RUNNER_TEMP`, creates data/config/cache/Windows children, and exports all five platform-specific inputs through `GITHUB_ENV` before any artifact launch. Linux and Windows frozen jobs both executed that step successfully. |
| No real profile input | On Spock, the same artifact fails without the override by selecting the maintainer's `2026.08.19` user copy and passes with it by selecting bundled `2026.07.04`. The user's copy remained installed. This is the required discriminating negative control. |
| `OPS-002` preserved | The isolated update probe installs `9000.1.1`, resolves it in a child as a user-managed copy, and reverts to the bundled baseline on both platforms. No `src/` file changed in the review boundary. |
| Deterministic wiring | `tests/unit/test_frozen_isolation.py` names both Windows overrides and all three XDG inputs, requires run/attempt uniqueness, keeps every artifact probe in the isolated job, retains the update probe, rejects job-level `runner.*`, and requires unconditional cleanup. All ten collected cases pass. |
| External confirmation | Run `33264021710` executed both frozen legs successfully at `a93a53b`; its overall cancellation occurred later in `windows desktop` and does not erase the completed frozen results. Run `33264769512` at `53b4d02` is green in every job. Both `frozen linux` jobs ran on Spock; the latter Windows leg ran on STARBASE. |
| Windows evidence asymmetry | STARBASE has no pre-existing user copy, so its green baseline is not the Linux negative control. This is accepted, not hidden: `platformdirs.windows.get_win_folder()` reads the two exact `WIN_PD_OVERRIDE_*` names, the job log shows their common isolated root, and the artifact installs/resolves/reverts through that environment. A future probe may print its resolved data directory, but approval does not depend on that hardening. |

### Finding dispositions and new findings

| ID | Severity | Blocks approval | Finding / disposition | Required action | Status |
|---|---|---:|---|---|---|
| **T212-R5** | Medium | No | T-298 removes the frozen gate's dependency on a self-hosted account's application data without deleting the account's copy or changing `OPS-002`. | None. | **Resolved by T-298** |
| **T268-R1** | Medium | Yes, for T-268 | Run `33267794308` at `14757f1` is the exact read-only inspection the finding requested. Every selected PID was identity-recorded, all seven remained present, no process was modified, and all seven reported `ThreadState=5`, `ThreadWaitReason=37`. Suspended (`5`) is refuted; `37` corresponds to `WrAlertByThreadId`. The inspection cannot name the waited-on object, and records that limit. | None for R1. The original criterion explicitly permits a documented non-identification; a stack may be useful, but is not retroactively required to resolve this finding. | **Resolved** |
| **T268-R2** | Medium | **Yes, for T-268 only; T-298 unaffected** | `src/tracks_and_trails/downloader/process_tree.py:86-93` still says the surviving candidate is outside the interpreter and needs somebody at the machine. The new task/evidence record says that candidate is refuted and the observed wait is an in-process synchronization mechanism. This also leaves T-268's fourth acceptance criterion—keeping `process_tree.py`'s account current—unmet while the header says only a stack remains. | Update the source-side explanatory record to distinguish the measured `WrAlertByThreadId` mechanism class from the still-unknown lock/cause. Do not change containment behavior. | **Open; T-268 already Blocked** |
| **T298-R1** | Low | No | T-298's task and evidence still say **five** mutations after `a93a53b` added the sixth, specifically the job-level `runner.*` regression that records the validation outage. | Correct the count and name the sixth mutation in ordinary T-298 completion synchronization. | **Open, non-blocking** |
| **T212-R6** | Low | No | The completion move succeeded structurally, but current truth did not receive the clean rewrite the prior review requested. `STATUS.md:42` still says nothing is approved, and the T-291/T-288/T-292/T-285/T-283 opening lines retain malformed or stale clauses such as “needs a dispatched run” and “awaiting the focused re-review.” | Remove the five stale task clauses and the contradictory STATUS sentence in the next mechanical coordination sync. No implementation re-review is needed. | **Open, non-blocking** |
| **T268-R3** | Low | No | `tools/soak_a_test.py` advertises `[--jobs 1]` in its usage block, but argparse implements only `--runs` and `--out`; the documented command fails if copied. | Remove the nonexistent option or implement it deliberately. Serial remains the correct default. | **Open, non-blocking; keep with T-268 tooling** |
| **T268-R4** | Low | No | The soak evidence combines 300 Linux and 300 Windows runs to claim a 95% upper bound near 0.5%. The observed flake was Windows-specific and the workflow explicitly treats the platform mechanisms as different populations, so the relevant zero-event sample is Windows's 300 runs, whose rule-of-three bound is about 1%. The conclusion remains the same: an isolated Windows invocation does not reproduce anything near the observed full-suite frequency. | Correct the confidence statement and keep the context-dependent mechanism as a hypothesis. | **Open, non-blocking; evidence wording only** |
| **T289-R1** | Low | No | In `--on-the-gui-thread` mode the probe reports that shiboken “marshalled” deletion to the GUI thread even though both finalization and destruction already occurred there. The pool mode is correct and independently reproduces the submitted `Dummy-1` → `MainThread` split. | Give the GUI control its own conclusion instead of reusing the pool-mode marshalling text. | **Open, non-blocking; T-289 remains Proposed** |

The committed raw STARBASE `.txt` retains Windows CRLF endings, so `git diff --check
0332a68..afe116a` reports all 100 lines as trailing whitespace. The content matches the machine
report and this does not affect a task verdict; normalize it during record cleanup if byte-for-byte
line-ending preservation was not intentional.

### Other boundary judgments

- **T-289's withdrawal is accepted.** Local runs reproduce the corrected instrument exactly:
  pool collection finalizes the Python wrapper on `Dummy-1` while `QObject::destroyed` fires on
  `MainThread`; the GUI control performs both on `MainThread`. That does not reproduce the core
  dump's off-GUI C++ destructor and criterion 4 remains unmet.
- **One adjacent Qt crash is recorded without fitting it to T-289.** The reviewer's first local
  parallel unit/UI run lost an xdist worker in
  `test_a_picture_published_while_the_sweep_runs_is_not_counted_as_swept`. The main thread was in
  `settle_deferred_deletions` → `QObject::~QObject` → shiboken `getOverride`; a Qt pooled thread
  was also live. That run also had three environment-caused failures because the venv was not on
  `PATH` and sandboxed loopback was denied. The exact test then passed alone, and the correctly
  activated full rerun passed **3,378 / 21 skipped**. The crash is real evidence, but this review
  does not claim it is T-289's mechanism; compare it before designing that task's fix.
- **The 600-run soak is useful as a negative result, not a diagnosis.** Zero of 300 isolated
  Windows runs on STARBASE and zero of 300 Linux runs on Spock is strong evidence against the
  isolated test having anything like the observed full-suite frequency. It does not identify what
  keeps the intermediate PID resolvable under suite load. The post-run `tee` failure is correctly
  disclosed and `d0e1d53` repairs the workflow shape, although that corrected diagnostic workflow
  has not itself been dispatched.
- **`tools/t287_minimize_probe.py` is outside the boundary.** It remains untracked and was neither
  read, run, modified nor committed by this review. The disclosed full-desktop-capture concern is
  sufficient reason not to execute it as written.

### Independent verification

| Check | Result |
|---|---|
| Boundary | Eleven commits from `0332a68..afe116a`; `git diff -- src` is empty. The only pre-existing worktree item is the disclosed untracked `tools/t287_minimize_probe.py`. |
| Static | Ruff passed; formatting reports **215 files** in the local tree; bare mypy and `--platform win32` each pass **155 files**. Seven workflow files parse as YAML. |
| Focused tests | T-298 wiring plus task placement: **25 passed**. T-298 alone collects ten cases. |
| Local unit/UI | Correctly activated run: **3,378 passed, 21 skipped**. The preceding malformed-environment run's Qt worker crash is retained above rather than overwritten by the green rerun. |
| T-289 instrument | Pool: 14 objects, Python finalizer `Dummy-1`, C++ destructor `MainThread`. GUI control: both `MainThread`. Both exit 0 and report the distinction. |
| T-298 external | Runs `33264021710` and `33264769512` have successful frozen Linux/Windows jobs; both Linux jobs name Spock. The latter full run is green and includes **3,378 / 21 skipped** unit/UI, **445** integration, and Windows **3,806 / 36 skipped / 35 deselected**. |
| T-268 external | Run `33267794308` is `workflow_dispatch` at `14757f1`, one successful read-only STARBASE job, report uploaded. |

### Readiness

T-298 is **Approved at implementation head `a93a53b`**, with its external evidence current through
`53b4d02`. Move it to Complete and resolve `T212-R5`; fold `T298-R1` into that mechanical sync.

T-268's requested external inspection is complete and `T268-R1` is Resolved. T-268 remains Blocked
on its own stale source-side explanation (`T268-R2`) and any maintainer decision to pursue a stack;
the stack is not required to re-prove R1. T-289 remains Proposed. No new task is warranted for the
Low findings because each belongs to an existing completion or diagnostic pass.

The Reviewer changed only this append-only record. No reviewed source, workflow, task/status file,
evidence artifact, untracked probe, process, push or remote state was changed.

<!-- review-migration:0344:end -->

<a id="migrated-review-0345"></a>
<!-- review-migration:0345:start -->

---

## 2026-08-29 — Post-approval correction focused re-review

**Reviewer:** Codex (Reviewer)
**Correction base:** `f1b36e9cfd4592b60bc8c89cf6cb4bcbae4190b2`
**Correction head:** `d5f1010044ed28d4476c2d26b8cd949e33252d94`
**Commits inspected:** `1b89667`, `0de526c`, `2edbfba`, `d5f1010`
**Verdict:** **Changes requested for T-268 only.** `T298-R1`, `T212-R6`, `T268-R3`,
`T268-R4`, and `T289-R1` are resolved, and the narrowly scoped CRLF policy is accepted. The
T268-R2 correction carries the new measurement into source, but its annotation names the wrong
field and the task's current dependency text still says the completed inspection is outstanding.
That is significant because the source record is T-268's fourth acceptance criterion. T-298
remains Approved/Complete and no other task is reopened.

### Finding dispositions

| ID | Disposition | Verification |
|---|---|---|
| **T298-R1** | **Resolved** | The task and evidence each say six mutations, name the job-level `runner.*` case, and record the baseline plus six-kill rerun. The unchanged focused test is green: **10 passed**. |
| **T212-R6** | **Resolved** | The five completion openings are syntactically complete and name the evidence that closed them. T-291 now records dispatched run `33231851897` and reconciles eleven node IDs to twelve collected tests. The contradictory “nothing is approved” sentence is retained only as an explicitly superseded quotation. |
| **T268-R2** | **Partially corrected; superseded by T268-R5 below** | The source now records `ThreadWaitReason=37`/`WrAlertByThreadId`, distinguishes mechanism class from unknown lock/cause, and says containment behavior is unchanged. Its final annotation nevertheless contradicts the same measurement by naming `ThreadState=5` as the absent suspended value. |
| **T268-R3** | **Resolved** | The usage block no longer advertises `--jobs`; `python tools/soak_a_test.py --help` lists only the implemented `--runs` and `--out` options. Serial execution remains explicit. |
| **T268-R4** | **Resolved** | The evidence uses the Windows-only 300-run population and a rule-of-three bound near 1%; Linux's 300 runs are kept as a separate population. The conclusion is no longer supported by pooled cross-platform arithmetic. |
| **T289-R1** | **Resolved** | The pool run reports `Dummy-1` finalization and `MainThread` destruction with the marshalling conclusion. The GUI control reports both on `MainThread`, explicitly says nothing was marshalled, and exits 0. The separate pool-finalized-on-GUI branch is conservatively INCONCLUSIVE. T-289 remains Proposed and unfixed. |

### Remaining finding

| ID | Severity | Blocks approval | Finding | Required correction | Status |
|---|---|---:|---|---|---|
| **T268-R5** | **Medium** | **Yes, for T-268's record correction only** | The new source annotation says a suspended process is `ThreadState=5` and “not one” specimen reports it (`process_tree.py:115-116`), but the source's own measured sentence says **all seven** report `ThreadState=5` (`:96`). The discriminating property is `ThreadWaitReason`: suspended is reason 5, while the specimens report reason 37. `ai/TASKS.md:13427-13428` repeats the same field error. The task also says at its top that the inspection is satisfied and it is now blocked on a stack (`:13184-13193`), then retains the old machine-local checklist and `Depends on:` claim that nobody has looked at PIDs 3400/6924 (`:13211-13224`, `:13281-13283`) and still lists a suspended process as a live candidate (`:13568-13569`). | Change both explicit `ThreadState=5` annotations to `ThreadWaitReason=5`. Rewrite or annotate the current dependency/checklist/candidate text so it says the read-only inspection is complete and the remaining optional/blocking work is the stack, with its actual owner. Historical reasoning may remain, but its current disposition must not contradict the run. | **Open; narrow record-only correction** |

### CRLF ruling

Keeping the raw STARBASE report byte-for-byte is acceptable. `.gitattributes` applies
`whitespace=-trailing-space` only to direct `ai/evidence/*.txt` artifacts; it does not set `text`
or an EOL conversion. `git check-attr` reports that exact policy for the raw file,
`git ls-files --eol` reports `i/crlf w/crlf`, and `git diff --check f1b36e9..d5f1010` is clean.
This resolves the prior review note without normalizing evidence.

### Independent verification

| Check | Result |
|---|---|
| Boundary/state | Four commits after the review base; their file scopes agree with the task split. No misplaced T-289 body appears in T-290 and no partial T-268 paragraph survives from the disclosed failed staging attempt. The only worktree item is the disclosed untracked `tools/t287_minimize_probe.py`, which was not read, run or modified. |
| Diff/static | `git diff --check`: clean; Ruff: passed; format: **215 files**; `mypy src`: **56 files**; bare mypy and Win32 mypy: **155 files** each. |
| Focused tests | Task placement plus frozen isolation: **25 passed**; frozen isolation alone: **10 passed**. |
| T-289 probe | Pool and GUI-control modes both executed offscreen and exited 0 with the distinct conclusions described above. |
| Soak CLI | `--help` accepts and documents only `--runs` and `--out`; no `--jobs` residue. |
| Commit records | Four correction messages pass `tools/commit_message_check.py --range f1b36e9..HEAD`. |
| Broader gates | The implementer reports **3,378 passed / 21 skipped** unit+UI and **445 passed** integration at this same correction tree. This focused pass did not repeat those full suites because the only `src/` change is explanatory prose; the executable probe and deterministic gates above were rerun directly. |

### Readiness

Five of the six requested finding corrections are complete, and the CRLF decision is approved.
T-298 remains Complete at `a93a53b`; T-289 remains Proposed. T-268 remains Blocked and its focused
record correction is not approved until T268-R5 is fixed. No product behavior change is requested:
this is a field-name and current-truth synchronization correction over the measurement already
obtained.

The Reviewer changed only this append-only record. No reviewed source, task/status file, evidence,
workflow, untracked probe, push or remote state was changed.

<!-- review-migration:0345:end -->
