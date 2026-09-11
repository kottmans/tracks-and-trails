# Phase 4 exit review

**Purpose:** Independent assessment of Phase 4 deliverables and exit evidence.
**Owner:** Reviewer
**Update when:** Phase exit is reviewed or an exit finding receives a disposition.

## 2026-09-11 — Initial phase exit review

**Reviewer:** Codex, independent of the implementations and completion records.
**Phase boundary:** Phase 3 approval at
`ccdbd0feb0621b1af3cc06d8e4088e499e915616` through reviewed head
`6b1fcf1deb476c0761afbb3767e1d0b2039ed0fb` on `main`.
**Scope:** The current Phase 4 criteria, their amendments, deliverable evidence,
accessibility and privacy gates, update/revert behavior, platform evidence and
explicit residual risks. Individual task approvals retain their original scope
and revision; this review assesses what they establish together at phase exit.

**Verdict: Blocked. Phase 4 is not signed off.** Three blocking Medium
findings remain: incomplete all-control accessibility evidence, missing Windows
execution for the candidate, and the explicitly reserved T-289 exit decision.
No new product failure was established. The accessibility finding concerns a
required gate's coverage, with a surviving mutation demonstrating the gap.

### Findings

| ID | Severity | Blocks approval | Evidence and required disposition | Status / route |
|---|---|---|---|---|
| P4EXIT-R1 | Medium | Yes — exit criteria 1–3 coverage, especially criterion 2 | The amended criterion requires correct control names and roles automated on both platforms, with Windows reading UI Automation. `tests/ui/test_windows_accessibility.py` queries the main window, its menus and About only; the Settings menu test opens the menu, not SettingsDialog. Its general name sweep at lines 349–372 only considers menu items, buttons and check boxes. Settings, Add URLs and the editing surfaces are never queried through UIA, and their edit/combo/spin/table controls are outside that role sweep. Separately, `every_surface` at `tests/ui/conftest.py:442` and `tests/ui/surfaces.py` omit the new queue FormatDialog and instantiate bare editors instead of the expanded staging pages. In the isolated reviewed tree, removing FormatDialog's Cancel name and keyboard focus leaves all 103 accessibility/colour tests passing, with zero FormatDialog constructions. A direct name check detects the same mutation. | **Open — Implementer, one phase-exit correction batch.** Include the actual dialog/page surfaces and relevant enabled states in the common audit; extend Windows UIA checks to the required controls and roles, with purpose names distinct from selected values where applicable. Demonstrate that an omitted/unnamed control fails and execute the Windows checks. If the maintainer intends narrower coverage, amend the phase criterion explicitly and preserve the surrendered coverage. Passing the current suite cannot establish this criterion. |
| P4EXIT-R2 | Medium | Yes — required Windows evidence | TESTING §10 requires Windows evidence before review and binds phase evidence to a head containing the code being claimed. Run `34606129352` at `c2561037d45c2e1b005db4ad18ebe470fc86e6b6` has successful Linux and frozen-Linux jobs, but `windows desktop` and `frozen windows` are queued. The candidate's source/tests/build inputs are unchanged from that head. The last successful Windows run is `34406323122` at `2181ee13b559dd582a0df6ef662524310200a638`; 27 source/test files changed after it, including the format table, staging pages, queue editing and Settings. | **Open — existing CI/platform verification.** Obtain the required Windows results for the final corrected executable/test tree and record its exact head. A later review-only commit may reuse that evidence after a tree comparison. A Windows-platform mypy pass and the earlier Windows success do not cover these changes. R1's coverage correction must also be included before treating the result as full accessibility evidence. |
| P4EXIT-R3 | Medium | Yes — explicit maintainer decision outstanding | T-289's closed record at reviewed-head `COMPLETED_TASKS.md:13754–13771` says the 2026-08-27 abort remains unexplained and explicitly reserves whether Phase 4 may exit over it to the maintainer. STATUS's risk section repeats that reservation. The 2026-09-04 ruling re-scoped the task's ownership evidence; it did not record the separately reserved phase-exit acceptance. T-238's later no-action closure concerns T-238. | **Open — maintainer disposition, recorded by the task/status owner.** Decide whether Phase 4 may exit with T-289's unexplained abort, the implemented pool/ownership guards, and reopening on a real guard firing. Record that bounded acceptance or the additional work required. This review neither reopens the approved pool correction nor infers that the crash recurred. Task closure alone does not take the reserved decision. |

These are Medium because the established defects are in required evidence and
approval disposition. There is no newly demonstrated inaccessible Windows
control or repeat of the historical crash to justify a product-defect severity.

### Exit criteria reconstructed

Numbering below follows the seven bullets in the
[Phase 4 plan](../IMPLEMENTATION_PLAN.md#phase-4--settings-polish-and-accessibility).

| Criterion | Assessment at the reviewed head |
|---|---|
| 1. Every function reachable by keyboard, end to end on Linux | Existing accessibility, row-route, dialog and composition checks pass in the local scopes below. The common audit's completeness is not established for the new dialog and expanded pages; see R1. Direct checks of the unmodified queue FormatDialog pass for names, roles, named focusable controls and Tab reachability. |
| 2. Correct names and roles automated on both platforms | **Not established — R1 and R2.** The Windows published-tree coverage is narrower than the criterion. Linux source-tree checks pass over their inventory. Orca/Narrator coherence and Linux AT-SPI publication remain explicitly deferred to the pre-release session by the 2026-08-15 amendment. |
| 3. No information conveyed by colour alone | Existing semantic-state, rendered-focus and palette checks pass over the audited controls. The shared inventory omission in R1 also limits the global rendered-focus claim. The staged state-chip review and its regressions provide explicit words for ready/failed rows. |
| 4. Automated log redaction | **Met within the accepted boundaries.** The redaction, log, cookie, proxy, settings and composition gates cover supplied paths, credentials, cookie headers and URL query values. Independent formatter-bypass mutation is detected. DAT-003 preserves third-party diagnostics in the database; logs remain redacted. The accepted unstructured bare `NAME=value` limitation remains as documented in ARCHITECTURE §8. |
| 5. In-app update changes the reported version; revert restores baseline | The local integration check performs installation, three fresh child-process imports and revert. Existing service/UI tests cover the button wiring and report transitions. Historical Windows/frozen evidence and current frozen-Linux CI support the mechanism, with current Windows execution still outstanding under R2. No live PyPI update or user installation was performed for this review. |
| 6. Recorded walkthrough of the built window | **Moved to Phase 5 by the 2026-09-10 maintainer amendment.** T-212 remains the recorded-run obligation before release. The informal observation is accepted only as the narrower evidence the amendment describes; this review does not claim a recorded run happened. |
| 7. Reviewed and signed off | **Not met.** This review is complete; phase approval awaits R1–R3. |

### Deliverable traceability

The closed task records and canonical reviews establish that all eight plan
deliverables were implemented. Their task approval is retained; the phase-wide
evidence limitations above remain separate.

| Deliverable | Implementation / review evidence | Checks inspected and exercised |
|---|---|---|
| Full REQ-023 Settings dialog | T-146 in [T-215](T-215.md), [T-195](T-195.md), and the setting-specific tasks below | Settings writers and persistence, live updates through composition, default preset/template and refusal paths |
| Rate limit, proxy and retries | [T-196](T-196.md) | Settings-to-request/adapter propagation; rejected credentialed proxies; incremental keyboard input cannot persist credentials |
| Cookie source and redaction | [T-197](T-197.md) | Startup/runtime path registration, source clearing, worker handoff and job-storage boundary, formatter and diagnostic redaction |
| yt-dlp display, update and revert | [T-198](T-198.md), [T-290](T-290.md) | Child-import resolution, install/revert, busy/hold/refusal paths, settled recovery label and error-taxonomy guidance |
| ffmpeg detection and override | [T-199](T-199.md) | Stored/runtime overrides, unavailable-feature reporting and preset catalogue filtering |
| Light/dark brand theme | T-120 in [T-100](T-100.md), [T-200/T-202](T-200.md) | Theme persistence, palette and rendered-state/focus checks |
| Keyboard, focus and accessible labels | [T-200](T-200.md) | Current Linux automation passes; R1 identifies scope that these passes do not establish, and R2 bounds Windows execution |
| Error-surface pass | [T-201](T-201.md), [T-244](T-244.md), [T-290](T-290.md) | Taxonomy presentations, preserved extractor messages, one appropriate next step and no invented DRM/geo recovery advice |

T-297's capture/sequence findings were already dispositioned in the
[2026-09-11 review](T-234.md#2026-09-11--t-297-evidence-disposition).
That approval stands under its observation amendment and historical exception;
no new capture or pre-fix reproduction is required by this review. T-286,
T-290, T-313, T-315 and T-316 likewise have independent approvals even though
their task-placement/status synchronization was still pending at the reviewed
commit. Existing Low items keep their routes in their own canonical records.

### Independent verification

Environment: Fedora Linux, kernel `7.1.4-204.fc44.x86_64`, glibc 2.43,
Python 3.14.7, PySide6/Qt 6.11.1, activated project virtual environment,
`QT_QPA_PLATFORM=offscreen`. The package import was checked against this
checkout's `src`. Network tests and native Windows tests are outside the
default selection. Integration was run serially as DEVELOPMENT requires.

| Check | Actual result |
|---|---|
| `ruff check .` | Pass |
| `ruff format --check .` | Pass, 362 files already formatted |
| Bare `mypy` | Pass, 166 files |
| `mypy --platform win32` | Pass, 166 files; type analysis, not Windows runtime |
| `pytest -q -n 4 tests/unit tests/ui` | 3,663 passed, 21 skipped, 1 failed, 17 warnings, 90.13 s. The sole failure was socket creation denied by the sandbox in the localhost thumbnail HEAD-server test. |
| That exact failed test, with local socket creation permitted | 1 passed, 0.60 s. This completes the 3,664 unit/UI cases across the two invocations; the original whole invocation is not relabelled green. |
| `pytest -q tests/integration`, with local sockets/process checks permitted | 454 passed, 397.93 s; process exited zero. |
| FormatDialog direct checks, unmodified | Names, roles, named focusable controls and Tab reachability pass against a shown offscreen dialog containing a format row. |
| FormatDialog omission mutation, archived reviewed tree | 103 accessibility/colour tests pass in 6.25 s; instrument records zero FormatDialog constructions. Direct name check detects the same mutation. |
| RedactingFormatter bypass, archived reviewed tree | Normal redaction control passes; replacing its formatter method with `logging.Formatter.format` is detected by the supplied-secret gate. Only synthetic fixture values are used. |

The two completed suite scopes and the single-test rerun account for **4,118
passed / 21 skipped** across invocations. All 454 integration cases completed
without a reported failure or warning. The initial sandboxed integration
invocation was interrupted before completion after identifying the localhost
socket restriction; it supplies no full-suite verdict. The completed unit/UI
run's warnings are the existing four signal
disconnect warnings and thirteen deprecated QMouseEvent-constructor warnings.
No process death or widget-boundary guard firing was reported in that run.

### Windows and frozen evidence

GitHub job conclusions and the last successful Windows log were read directly:

- [Candidate run 34606129352](https://github.com/kottmans/tracks-and-trails/actions/runs/34606129352),
  at `c256103`: Linux and frozen Linux successful; Windows desktop and frozen
  Windows queued at the review's status checks. The Linux frozen update check
  succeeded. The coverage-reporter job's success is not a Windows result.
- [Last successful run 34406323122](https://github.com/kottmans/tracks-and-trails/actions/runs/34406323122),
  at `2181ee13`: Linux, Windows desktop and both frozen jobs successful.
  Windows log: **33 passed / 4,029 deselected** in the native desktop slice;
  **3,991 passed / 36 skipped / 35 deselected / 23 warnings** in its full suite.
  Eleven of those native cases are the accessibility module's main-window,
  menu, toolbar and About assertions. None opens the Settings dialog.

`git diff c256103..6b1fcf1 -- src tests pyproject.toml .github packaging` is
empty. The later commits are review records. In contrast, the comparison from
`2181ee13` contains 27 changed source/test files, so the older Windows run
cannot be transferred to the candidate as an unchanged-tree result.

### Mutation boundary and shared-checkout changes

The FormatDialog mutation wraps its constructor, clears the Cancel button's
text and accessible name, and gives that button `Qt.NoFocus`. It counts every
FormatDialog construction. Both audit modules run unchanged against the
archived `6b1fcf1` tree, using that tree explicitly on `PYTHONPATH`. The count
is zero and all 103 tests pass. Constructing the mutated dialog separately and
applying the existing all-controls name check fails on `Button '' <QPushButton>`.
This establishes an omitted surface, not a claimed defect in the unmodified
dialog. Expanded FormatPanel/PlaylistPanel/TemplatePanel wrappers are also
absent from the shared inventory; their bare bodies are present.

The checkout was clean when review began. During review, another writer
started task closures, Phase 5 planning and T-290 Low cleanup in TASKS,
COMPLETED_TASKS, STATUS, IMPLEMENTATION_PLAN, `ui/settings_dialog.py` and
`tests/ui/test_settings_dialog.py`. Those edits are outside this verdict and
are not staged by the reviewer. The observed source change is comments only,
verified AST-identical to the reviewed head; the settings-test edit strengthens
the separate appearance guard. The isolated mutation probes use an archive
of the exact reviewed commit and cannot pick up that changed test. No branch
or worktree was created, and no product source was edited by the reviewer.

Before review finalization, the other writer committed that work as
`bca24bd4be79e29ac1d55244a693862abe1005de`, also including the in-progress
review record and index entry. That commit is preserved. The reviewer finishes
the record and index formatting in a separate commit; inclusion of the draft
in the completion commit grants no approval of its source/test or planning
changes. The reviewed implementation boundary remains `6b1fcf1`.

### Coordination and next review

Only this canonical record and its REVIEWS index link are review-owned changes.
Task/status closure and the Phase 5 proposals remain with their owners. No
new bookkeeping task is created, and no publication or release is authorized
by this verdict.

Documentation checks pass: both review/index files pass Ruff formatting, all
136 local link targets in those files resolve, the new index link is exactly
one added table row, and the migration verifier preserves all 381 historical
entries / 2,403,546 bytes. Product source remains AST-identical to the reviewed
head and the integration test files are unchanged despite the concurrent
completion edits.

Complete the R1 evidence correction, obtain Windows results for the final
candidate (R2), and record the maintainer's T-289 exit disposition (R3). Return
one focused correction review covering those findings, the correction diff
and any regression it introduces. This is the initial comprehensive phase
review; the ordinary focused correction pass remains available under TESTING §14.

The existing Phase 5 obligations remain: recorded T-212 walkthrough, Orca and
Narrator/pre-release desktop verification, packaging decisions and release
gates. Phase 4.5 option coverage follows the first release under the maintainer's
resequencing; this review grants no yt-dlp capability-parity claim.

## 2026-09-11 — Focused correction review

**Reviewer:** Codex, independent of the correction implementation.
**Boundary:** `a149b2b8343ffd1af25050f4f309f53d5557602b` →
`67aae4cb80cba5f812feea7591921ae81c9c50e3`, six changed files.
**Verdict: Blocked.** P4EXIT-R3 is Resolved by the confirmed maintainer
disposition. P4EXIT-R1 is partly corrected and remains Open; P4EXIT-R2 remains
Open. There is actionable R1 correction work before the Windows runner returns.

### Finding disposition

| ID | Severity | Blocks approval | Disposition |
|---|---|---|---|
| P4EXIT-R1 | Medium | Yes | **Open, partly corrected.** The added Linux inventory and disclosure focus correction work, with independent mutation evidence below. The new Windows tests cannot open their target dialogs using their fixture; Windows still does not query the editing surfaces; the combo-purpose assertion accepts a value-named combo when no ListItem is published. Relevant populated/enabled states also remain absent from the new local fixtures. Correct these together as continuations of the original coverage finding. |
| P4EXIT-R2 | Medium | Yes | **Open.** Candidate run `34610604275` is at `67aae4c`; Linux and frozen Linux succeed, while Windows desktop and frozen Windows remain queued. STARBASE is offline. Current native Windows execution is absent, and the R1 corrections below will change the test tree again. |
| P4EXIT-R3 | Medium | No | **Resolved by maintainer disposition.** The submission confirms bounded acceptance, and the dated addition to T-289's closed record records it without rewriting the historical reservation. STATUS's risk section agrees: the crash remains unexplained; a real-test guard firing reopens the task and lapses the acceptance. This resolves the decision requirement, without asserting a cause or a reproduced fix. |
| P4EXIT-R4 | Low | No | **Open — wording cleanup in the same correction/completion sync.** New theme comments/registry text and STATUS call the collapse triangle the only pointer route out of a panel. `RowPanel` also supplies a clickable Done button; both emit `closed(True)` (`ui/add_dialog.py:784`, `:805`). Describe the triangle as the top-of-panel return control without claiming exclusivity. No separate task or review pass solely for this item. |

### R1: what is verified

`screens_below_the_add_dialog()` now returns nine entries rather than five;
the common fixture adds its four existing top-level surfaces. FormatDialog
and the three panel wrappers now enter the Linux name, keyboard and rendered
focus checks. Constructing these widgets and supplying synthetic media is a
reasonable bounded way to audit their properties. This review does not require
a live network probe to build that fixture, or reject it merely because it is
constructed. The remaining concerns are which surfaces and states it exercises.

Replaying the initial review's exact FormatDialog mutation—clear Cancel text
and accessible name, then set `Qt.NoFocus`—produces **2 failed / 105 passed**
in 7.12 s, with **12 FormatDialog constructions**. The name and keyboard-route
checks fail. This establishes the corrected coverage. The submission reported
four failures; this pass establishes two for the stated mutation and does not
require a mutation to fail every check. Removing a control's focusability can
also remove it from the rendered-focus sweep, so that sweep is not the oracle
for the removed keyboard route.

The disclosure fix reserves an idle transparent border and adds the control
to BORDERED_CONTROLS, which also generates its specific focus selector. Its
new construction recipe matches the real arrow/auto-raise properties. Restoring
the previous stylesheet and registry together from `a149b2b` makes both
`test_focus_is_visible_on_every_control_the_application_shows` palette cases
fail: each of the three panel collapse controls changes **0 brightness pixels**
against the 43-pixel floor. **2 failed in 1.45 s.** The unmodified correction
passes in the UI run below. This independently verifies the defect and fix.

### R1: remaining correction requirements

1. **Make the Windows fixture capable of opening the screens.** At
   `tests/ui/test_windows_accessibility.py:279`, `window` still constructs
   `MainWindow(geometry_file=..., control_bar=True)` without composition.
   `open_settings()` consequently returns None because it lacks writers,
   output directory and theme; `open_add_dialog()` raises because it lacks
   manager, jobs and output directory. Both new Settings tests fail their
   assertions, and the Add test raises, before `read_tree` is called. Use a
   composed, isolated window with working routes and orderly teardown, or an
   equivalently complete fixture. Supplying desktop availability alone cannot
   make these three tests pass.
2. **Include the remaining Windows surfaces and relevant states.** The new
   UIA tests open Settings and an empty Add dialog only. Options, PresetManager,
   queue FormatDialog and the three editing panels still have no Windows
   published-tree query. The comment at lines 603–609 explicitly substitutes
   the Linux audit for the panels' Windows coverage; the amended criterion
   requires both. The shared fixture also builds PlaylistPanel with
   `entries=()`—independently measured as zero rows—and FormatDialog without a
   completed selection, leaving its accept button disabled. Populate the
   playlist and exercise a completed choice so the claimed item and enabled
   control states are actually represented. Keep construction/routing limits
   explicit; counts of windows alone do not establish the control coverage.
3. **Make the purpose-name assertion discriminate purpose from value.** At
   lines 660–670, `values` is a set of every ListItem name under the dialog,
   with no requirement that any exist and no association with a specific
   combo. A constructed tree containing a combo named `Best video available`
   and no ListItem passes the new test unchanged. Even a nonempty collection
   of unrelated items would not establish that combo's selected value. Bind
   the assertion to each combo's purpose and actual selected value, and prove
   it fails for a missing purpose/value-as-name case. A nonempty combo list
   is not a positive control for the value comparison.

The fixture failures were reproduced on Linux by extracting the committed
fixture and three new test function bodies unchanged into a temporary harness.
Only the platform import boundary and UIA provider were replaced; the real
MainWindow routes ran. The results are **three pre-query failures, zero UIA
calls**. A second harness supplied the constructed Tree counterexample to the
unchanged combo test, after providing a minimal dialog stub. It passed.
These are proofs of platform-independent setup/assertion defects, not claims
that UI Automation executed on Linux. No Windows bridge behavior is inferred.

### R2: runner state and the proposed fallback

The GitHub API reports STARBASE **offline**, `busy=false`, with the matching
self-hosted/Windows/desktop labels. `STARBASE_AVAILABLE=true`, while
`WINDOWS_RUNNER=["self-hosted","windows","desktop"]`. The availability
variable therefore does not currently describe the observed runner state.

[Run 34610604275](https://github.com/kottmans/tracks-and-trails/actions/runs/34610604275)
at the correction head has successful Linux/frozen-Linux jobs and queued
Windows desktop/frozen-Windows jobs. Earlier runs at `bca24bd` and `c256103`
are now cancelled, without supplying the required new Windows result.

**Unsetting WINDOWS_RUNNER does not move the native desktop job.** At
`.github/workflows/ci.yml:535`, that job's `runs-on` is the literal
`[self-hosted, windows, desktop]`; `STARBASE_AVAILABLE` gates its inclusion.
WINDOWS_RUNNER controls the ordinary Windows check/frozen routing. Its removal
would restore those hosted paths, but leave the required native UIA job on the
offline desktop. Correct the proposed fallback in the ordinary R2/status sync.
No runner, workflow or repository variable was changed during this review.

### Reviewer checks and limits

| Check at `67aae4c` | Result |
|---|---|
| `ruff check .` | Pass |
| `ruff format --check .` | Pass, 363 files |
| Bare `mypy`; `mypy --platform win32` | Both pass, 166 files each |
| `pytest -q -n 4 tests/ui tests/unit/test_theme.py tests/unit/test_task_placement.py tests/unit/test_toolchain_versions.py` | **1,343 passed / 3 skipped / 17 warnings**, 71.71 s; normal process exit |
| Initial FormatDialog mutation | **2 failed / 105 passed**, as detailed above |
| Previous disclosure styling and registry | **2 expected failures**, light and dark, as detailed above |
| New Windows setup, extracted unchanged | **Three pre-query failures**; no native UIA execution |
| New combo assertion, constructed counterexample | Passes the wrong name, establishing the guard gap |

The 17 warnings are the existing disconnect/deprecated-event warnings. The
reported **4,122 passed / 21 skipped** full run is the implementer's evidence;
this focused review did not independently repeat it. Integration/core behavior
was not changed by this six-file correction. The broader initial-review
verification retains its original boundary. No native desktop, live download,
frozen installation or new crash diagnosis is claimed here.

### Review convergence

This is the ordinary focused correction pass after the initial comprehensive
review. Only Medium blockers remain. Under [TESTING §14](../TESTING.md#14-review-policy),
another focused verification requires explicit maintainer authorization; this
record does not open an automatic third pass. The concrete remaining R1 work
above can be prepared before the runner returns. The final Windows run must
cover that corrected test tree. R3 is closed and need not be requested again.

Only this canonical review record is appended. Its existing index link remains
valid. Task/status ownership remains unchanged; no follow-up task is invented
for either the continued R1 work or R4's coupled wording cleanup.

Documentation checks pass: Ruff formatting and diff whitespace, the existing
index/policy links, and exact preservation of the previous review as a byte
prefix. The migration verifier again preserves all 381 historical entries /
2,403,546 bytes. Only this review record changed.

## 2026-09-11 — Maintainer authorization for a third focused pass

**Decision, by the maintainer:** a third focused verification pass **is authorized.**

Recorded here by the Implementer; the authorization is the maintainer's and this
entry does not interpret or extend it. [TESTING §14](../TESTING.md#14-review-policy)
requires explicit maintainer authorization for a third pass when the remaining
findings are blocking Medium, which is the state the focused correction review
left: `P4EXIT-R1` Open, `P4EXIT-R2` Open, `P4EXIT-R3` Resolved, `P4EXIT-R4` Open
as coupled wording cleanup.

**What it covers.** The unresolved blockers and the correction diff, at
`55d7488` — the head carrying the corrections to `R1`'s three remaining
requirements and `R4`'s wording. Per §14 an extra pass stays focused on those
and is not a new broad audit.

**What it does not do.** It does not resolve `P4EXIT-R2`. That finding asks for
native Windows execution, which is evidence rather than review: `STARBASE`
reports **offline**, and `windows desktop` and `frozen windows` are queued at
`55d7488`. No review pass can supply that result, and `R2`'s own route requires
the evidence to be taken at the corrected tree or later.
