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
