# Phase 5 second-batch review

**Purpose:** Shared validation and navigation for the bounded Phase 5 review.
**Owner:** Reviewer
**Update when:** This batch's shared evidence or review routing changes.

## 2026-09-13 — Independent review

**Reviewer:** Codex, independent of the implementer.
**Base:** `2e2507b5cfe4e262fcfda9b954dbbf68c390636c`.
**Head:** `8e67f6ff5b5804a8da907c56aeecac8e9fa5a0a7`.
**Boundary:** All 50 commits in this range, including the task-record corrections.
**Verdict:** Changes requested. This is not a Phase 5 exit or release approval.

The review used the committed requirements, amended decisions, architecture,
task criteria, earlier findings, source, tests and retained reports. Existing
corrections received focused review; new behavior received an initial pass.
Task-specific findings and authoritative dispositions live in these records:

| Scope | Record and outcome |
|---|---|
| Version/rollback corrections; unsigned-release documentation | [T-320 / T-317](T-320.md): Approved with a nonblocking wording correction routed to completion sync |
| Linux artifact corrections | [T-321](T-321.md): Approved within the recorded artifact/evidence limits |
| Artifact gates | [T-323](T-323.md): Blocked; Linux linkage corrected, Windows linkage and binary cookie-path coverage remain open |
| Earlier Windows focus evidence | [T-329](T-329.md): Approved after inspecting the supplied original output |
| Decision-index repair | [DOC-008](DOC-008.md): Approved; R1 resolved |
| Clean-machine harness, installer gates, certificate correction | [T-318 / T-039](T-318.md): Changes requested; later Windows download report and scope disposition remain needed |
| Installer | [T-322](T-322.md): Changes requested; recursive deletion can destroy user-owned files |
| Release workflow and partial Windows release build | [T-324 / T-319](T-324.md): Changes requested; wrong upload path and missing ffmpeg probe; T-319's declared open checks remain |
| Startup and REL-008 | [T-325](T-325.md): Changes requested; cold gate averages warm launches, physical evidence incomplete |
| Windows CI parallelism | [T-330](T-330.md): Approved; three green runs verified |
| yt-dlp version table / OPS-002 amendment | [T-333](T-333.md): Blocked only on its installed-Windows acceptance observation |
| Queue drain / UX-006 amendment | [T-334](T-334.md): Changes requested; unfinished durable probes are omitted from remaining work |
| Partial release gates, baseline bump and remaining manual session | [T-326 / T-332 / T-327](T-326.md): Blocked on the stated candidate checks and mandatory coverage gap |

T-106's prior decision approval is unchanged; no further decision change was
submitted for that task. The six session defects were inspected at their fixing
commits, including the certificate and baseline changes routed above.

### Shared checks actually run

Local platform: Fedora/Linux, Python **3.14.7**, PySide6 **6.11.1**, yt-dlp
**2026.8.19**, truststore **0.10.4**. Source stayed at the reviewed head throughout.

| Check | Actual result |
|---|---|
| Ruff lint | Passed |
| Ruff whole-tree format check | Passed, 397 files already formatted before review-document additions |
| Bare mypy | Passed, 180 source/test files |
| Bare mypy with `--platform win32` | Passed, 180 source/test files; not Windows runtime evidence |
| `pytest -n 4 tests/unit tests/ui` | **3,894 passed, 21 skipped, 3 failed**, 99.74 s. Two failures were the unactivated shell resolving tool commands outside the venv; the third was the sandbox refusing the test's loopback socket. |
| Environment-corrected failed-test selection | **6 passed in 0.78 s**: all toolchain tests plus the adapter's local HTTP test, with the venv on PATH and loopback access allowed. This clears all three failures above. |
| `pytest tests/integration` with loopback access | **461 passed**, 6 warnings, 415.38 s; includes the delayed-retry and TLS worker tests |
| Unique default tests across those runs | **4,358 passed, 21 skipped after environment reruns**; this is a combined result, not an invented single clean invocation |
| Archived head with only version changed to `0.1.0` | **19 passed in 0.42 s**, checker and skeleton including real CLI |
| Real-library deletion with corrected Linux gate | Clean control passes; removing the actual Widgets library is rejected with three specific complaints |
| Windows-layout gate counterexample | Invalid `.pyd`/`.dll` contents accepted; recorded in T323-R1 |
| Binary cookie-path/header counterexamples | Cookie path accepted, cookie header rejected; recorded in T323-R2 |
| Cold-gate counterexample | `[6, 1, 1, 1, 1]` seconds with a 5-second bound exits 0; recorded in T325-R1 |
| Durable-probe/finished-download race | Reproduced with real spawned workers; prior drain behavior completes both jobs; recorded in T334-R1 |
| Dependency licence comparison | Committed yt-dlp and truststore texts match the installed pinned versions, 1,211 and 1,086 bytes respectively |

Local logs and temporary reproduction scripts are under
`/tmp/tt-phase5-review/`. Findings retain their substantive sequences/results in
the canonical records so those paths are not required for future review.

Review-document validation also passed: Ruff lint and formatting (406 files),
all 166 local Markdown file targets checked in the changed records, and
`git diff --check`. Each of the five appended historical review files retains its
entire original byte sequence as a prefix. The review-migration verifier passed
for 381 entries in 105 files, retaining 2,403,546 historical bytes.

### CI and the formerly skipped drop-down test

Independently retrieved [CI run 34738178076](https://github.com/kottmans/tracks-and-trails/actions/runs/34738178076)
for implementation `0b3703aaaff45eb91a63de77183a9efe6fdeb26f`.
The two later task-record commits do not change code or tests.

The run was **cancelled**, not green. Linux, frozen Linux and frozen Windows
completed successfully. The Windows desktop job was cancelled during its serial
integration slice. Its uploaded `evidence-windows-desktop` artifact retains:

```text
tests/ui/test_windows_desktop.py::test_the_chosen_entry_of_an_open_drop_down_is_drawn_on_its_fill[light] PASSED
tests/ui/test_windows_desktop.py::test_the_chosen_entry_of_an_open_drop_down_is_drawn_on_its_fill[dark] PASSED
39 passed, 4379 deselected in 98.25s (0:01:38)
```

The JUnit records contain both named cases with no skips or failures. The same
artifact's offscreen unit/UI slice has **3,876 passed, 40 skipped**. Environment
evidence identifies STARBASE, Windows Python 3.14.6, PySide6/Qt 6.11.2, and yt-dlp
2026.8.19. The desktop cases assert the appropriate popup style rather than
silently skipping it. This closes the specific selection/execution uncertainty,
without turning the cancelled full job into a pass.

The status-bar frame, menu-bar highlight and summary-punctuation corrections
have passing relevant tests; no additional defect was established in those
changes. The prior Windows mutation claims are not recast as fresh reviewer
executions. [T-330](T-330.md) retains the separately verified three-run timings.

### Coordination findings

| ID | Severity | Blocks approval | Finding and evidence | Disposition/status |
|---|---|---|---|---|
| P5B2-R1 | Low | No | STATUS still says no tasks are In Review and presents Phase 4/Phase 5 snapshots contradicted by the active task queue. Several task bodies mix obsolete proposed/open statements with later completion claims. The recent four-task cleanup is useful but does not refresh the current snapshot. | **Open — batch owner's ordinary completion sync.** Preserve dated evidence and rewrite current status/navigation. No new task or review pass. |
| P5B2-R2 | Low | No | `docs/project/roadmap-phase-5.html` is newly tracked although AGENTS §6 says the roadmap is an external artifact and never a repository file. No applicable amendment was located in this review boundary. | **Open — documentation completion sync.** Record any overriding maintainer direction or move publication to the agreed external home, preserving the authored work. No deletion was performed by the reviewer. |

The reviewer changed only review records and their index. Product source, tests,
TASKS, COMPLETED_TASKS and STATUS remain with their owners. No follow-up tasks,
branches, tags, installer runs, workflow dispatches or releases were created.
Nothing was pushed. The work can return to the implementer for the in-scope
corrections; the Critical uninstall finding must be independently verified before
distribution. T-323 alone has exhausted its ordinary Medium-only review budget,
so a further focused pass there requires the maintainer's explicit §14 choice.

## 2026-09-13 — Correction review through acdc570

**Reviewer:** Codex, independent of the implementer.
**Base:** `8e67f6ff5b5804a8da907c56aeecac8e9fa5a0a7`.
**Head:** `acdc57071026fac0dfb15743fe24651cb1fcf013`.
**Boundary:** The 22-commit correction batch, the supplied new T-319/T-331/T-332
completion evidence, and the previous findings it answers. This is a focused
correction review, not another broad audit of settled work.
**Verdict:** Changes requested on T-331; T-323 and the remaining physical/scope
items remain Blocked. The installer data-loss and queue-stopping defects are resolved.

The maintainer explicitly authorized the additional T-323 pass. The requested
`git pull --rebase` dropped local `f2a4b58` as already applied on main as
`7825888`; review then used the clean `acdc570` tree. No implementation edits were
made by this reviewer. The final two commits after CI head `40b1dd8` change only
TASKS and STATUS.

### Dispositions

| Scope | Correction outcome |
|---|---|
| [T-322](T-322.md) | Critical T322-R1 **Resolved**, with fixed/negative Sandbox evidence. Workflow-built installer, SmartScreen and T-039 dependencies still prevent completion; align the remaining empty-directory wording in normal completion sync. |
| [T-334](T-334.md) | T334-R1 **Resolved; Approved**. The original real-worker ordering now completes both jobs and stops exactly once. |
| [T-324 / T-319](T-324.md) | Upload and ffmpeg findings **Resolved**. T-319 **Approved** after the new Windows release-build, report and console evidence. T-324 still awaits its tagged draft run. |
| [T-318 / T-039](T-318.md) | Missing retained transfer and harness failure-contract findings **Resolved**. T-318 **Approved**; T-039 still requires the maintainer's candidate-vs-push decision. |
| [T-325](T-325.md) | Cold-gate defect **Resolved**; measurement finding remains **Open / Blocked**. Withdrawal of unsupported compliance claims is verified; it does not supply cold measurements. |
| [T-323](T-323.md) | Windows dependency finding **Resolved**. Binary scan still misses paths across its printable-run boundary and extensionless store paths; **Blocked** after the authorized pass. |
| [T-326 / T-332](T-326.md) | Settings-freeze and original routing findings **Resolved**. T-332 **Approved** on its baseline-bump evidence. T-326 still awaits its candidate and manual operations; correct the residual real-download routing in completion sync. |
| [T-331](T-331.md) | Initial review: **Changes requested**. Broken or incomplete pytest runs can still receive a successful mutation-kill verdict. |
| [T-320 / T-317](T-320.md) | T320-R3 **Resolved**; earlier approval unchanged. |
| T-327 / [T-333](T-333.md) | No new manual observation supplied; the draft stays a draft. The remaining session items and installed version-table observation are not completed by the automated download or CI. |

**P5B2-R1 — Resolved (Low):** STATUS now describes Phase 5 and routes its open
work; normal completion sync will update this review's dispositions. Older
verification paragraphs retain their identified historical boundaries.
**P5B2-R2 — Resolved (Low):** the roadmap was removed from tracking, ignore rules
were added, and the preserved `../roadmap-phase-5.html` exists beside the checkout.
No roadmap content was deleted by this reviewer.

The platformdirs licence addition was inspected: the committed text matches the
local installed 4.11.0 distribution's 1,089-byte licence. The new dependency-tree
check passes and requires a shipped licence entry for each current runtime Python
distribution. That check concerns the current resolved Python dependency graph,
not every possible third-party component or future optional extra.

### Independent validation

Environment: Linux, Python 3.14.7, PySide6 6.11.1, yt-dlp 2026.8.19. The editable
installation resolves to this checkout, not the implementer's separate worktree.

| Check | Actual result |
|---|---|
| Ruff lint and whole-tree format | Passed before review edits: 409 files formatted |
| Bare mypy; bare mypy with `--platform win32` | Both passed, 181 source/test files |
| Offscreen unit/UI suite, four workers | **3,919 passed, 21 skipped, 17 warnings**, 98.87 s |
| Serial integration suite | **464 passed, 6 warnings**, 425.45 s |
| Combined default coverage | **4,383 passed, 21 skipped**, with no failing default test; these are the two runs above |
| Original durable-probe reproduction | Queue remains started while probing, then both rows complete and `[True, False]` is emitted |
| Windowed report transport, real subprocess loop with temporary executable | Five reports written: 5/5, exit 0. Same markers only on discarded stdout: 0/5, exit 1 |
| Binary cookie-path checks | Original case rejected; 600-byte printable-prefix and extensionless cases accepted incorrectly; see T323-R2 |
| Whole mutation-driver counterexamples | Normal control passes; error-only and missing-summary mutations incorrectly yield KILLED/exit 0; interrupted baseline still permits later kill labels |
| Real pytest fixture-error control | Exit 1, **1 error**, no test assertion executed; corroborates the driver's error-only counterexample |
| Fixed Sandbox report comparison | Committed captured body matches the original full report after BOM/line-ending normalization; original negative reports inspected |

Logs and temporary reproduction scripts are under
`/tmp/tt-phase5-corrections-review/`. The records retain the substantive sequences
and results. Default suites ran with the venv on PATH and permitted loopback
sockets; no user media, installer, live updater or remote workflow was invoked.

### Independently verified CI and canary

[CI run 34742480032](https://github.com/kottmans/tracks-and-trails/actions/runs/34742480032)
is **success** at `40b1dd883de5cc114ba54d3f34df9587b95b4187`. Linux, Windows desktop,
both frozen jobs and STARBASE coverage succeeded. The intentionally disabled
Linux orphan job was skipped. The Windows release evidence records:

```text
windowed probes: 5 of 5 passed through their report
smoke: conhost.exe and a ConsoleWindowClass window observed
release: none seen in 15 s; ok: no console window
```

[Canary run 34743729647](https://github.com/kottmans/tracks-and-trails/actions/runs/34743729647)
is **success** at the same head. It resolved yt-dlp **2026.8.19** and reports
**4,350 passed, 42 skipped, 14 deselected**, 23 warnings, 1,102.99 s. This supersedes
the earlier “not dispatched” limitation for T-332. T-326 still requires evidence
for its eventual candidate; neither run is a tagged release run.

The supplied Windows mutation rerun has **ten rows: three baselines and seven
mutation cases**, not ten mutations. Its table is retained in T-331; the earlier
full report was also inspected. Actual assertion failures in those runs remain
useful evidence despite the driver's separately reproduced classification gap.

No task/status closure, tag, reboot, Windows manual-session completion, release
approval or push was performed. Review records and their index are the only
repository changes made by this pass.

Final review-document checks passed: Ruff lint and formatting (410 files),
`git diff --check`, and all 181 local Markdown file targets in the changed
records. The nine appended review files preserve their entire pre-review byte
sequences as prefixes. The migration verifier also passed: 381 original entries,
105 files and all 2,403,546 historical bytes preserved.
