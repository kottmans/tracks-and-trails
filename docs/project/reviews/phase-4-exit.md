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
without a reported failure or warning. The initial sandboxed integration invocation was interrupted before completion
after identifying the localhost socket restriction; it supplies no full-suite
verdict. The completed unit/UI run's warnings are the existing four signal
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

### Coordination and next review

Only this canonical record and its REVIEWS index link are review-owned changes.
Task/status closure and the Phase 5 proposals remain with their owners. No
new bookkeeping task is created, and no publication or release is authorized
by this verdict.

Complete the R1 evidence correction, obtain Windows results for the final
candidate (R2), and record the maintainer's T-289 exit disposition (R3). Return
one focused correction review covering those findings, the correction diff
and any regression it introduces. This is the initial comprehensive phase
review; the ordinary focused correction pass remains available under TESTING §14.

The existing Phase 5 obligations remain: recorded T-212 walkthrough, Orca and
Narrator/pre-release desktop verification, packaging decisions and release
gates. Phase 4.5 option coverage follows the first release under the maintainer's
resequencing; this review grants no yt-dlp capability-parity claim.
