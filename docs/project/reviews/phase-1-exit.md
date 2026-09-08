# phase-1-exit — Review record

**Purpose:** Dated review evidence and disposition history for this task or shared scope.
**Owner:** Assigned Reviewer · **Update when:** This scope is reviewed or rechecked.
**Covered tasks:** T-033, T-074

[Review index](../REVIEWS.md) · [Review policy](../TESTING.md#14-review-policy)

Moved from `85422bc0b086de9b18d2f809abb4d6bcebb180e4:docs/project/REVIEWS.md` on 2026-09-08.
The entries below retain their exact original bytes and relative order. Historical
path spellings, line citations and references to “above” describe that source;
the [migration manifest](../evidence/2026-09-08-review-migration.json) records the
original order and byte ranges. Shared entries are stored once; covered tasks
link to this same record. Navigation grants no approval or new review provenance.

## Recorded rounds

- [2026-07-29 — T-074 diagnostic and Phase 1 evidence-table review](#migrated-review-0087)
- [2026-07-29 — Phase 1 evidence-table focused correction re-review](#migrated-review-0088)
- [2026-07-29 — Final authorized Phase 1 evidence-table correction review](#migrated-review-0089)
- [2026-07-29 — Phase 1 exit review](#migrated-review-0097)

<a id="migrated-review-0087"></a>
<!-- review-migration:0087:start -->

## 2026-07-29 — T-074 diagnostic and Phase 1 evidence-table review

**Reviewer:** Codex (Reviewer)
**Base:** `9802a6a`  **Head:** `13138e3`
**Scope:** The T-074 Linux diagnostic and QThread-lifetime rule-out, the new Phase 1 exit-criteria
evidence table, and the T-033 blocker correction
**Boundary classification:** Documentation and review record only; no production source, tests,
workflow, or build configuration
**Verdict by work item:** T-074 diagnostic **Accepted as narrowing, not diagnosis**; Phase 1
evidence table **Changes requested**; T-033 blocker correction **Accepted with a non-blocking
current-truth follow-up**
**Overall verdict:** **Changes requested** on `P1EXIT-R1`. Phase 1 remains not exited, as the table
already says.

The boundary contains two commits. `c76ec43` records the preceding no-new-findings review;
`13138e3` adds the diagnostic, evidence table, and T-033 correction. `HEAD` and `origin/main` both
resolved to `13138e3`, and the tree was clean before this review record was appended.

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `P1EXIT-R1` | **Medium** | **Yes — Phase 1's headless exit criterion** | The new table treats “Worker code runs with no display attached” as met by the static layering test and by running Qt with `QT_QPA_PLATFORM=offscreen`. Neither detaches a display from the worker. The purpose-built `test_the_worker_runs_in_a_real_spawned_process_with_no_display` does not do so either: `_spawn_target` is started with an ordinary `multiprocessing.Process` and inherits the parent environment unchanged. On this review host that test passed while `DISPLAY=:0` and `WAYLAND_DISPLAY=wayland-0` were both present. A separate reviewer run with both variables removed also passed, showing the behavior works, but the lasting gate does not create or assert the condition named by the phase criterion. | Make the spawned child run with the platform's display variables deliberately absent and assert that absence from inside the child before exercising the real worker session. On Linux, remove at least `DISPLAY` and `WAYLAND_DISPLAY`; preserve a cross-platform formulation for Windows. Mutation-check the gate with a worker-side display dependency, then cite that integration test in the table. Until then mark this criterion not met rather than substituting Qt's offscreen plugin. | **Open** |
| `P1EXIT-R2` | **Low** | **No** | The unsupported-URL row cites `test_the_extractor_message_survives_verbatim` and calls it evidence from recorded `info_dict` fixtures. That test constructs a generic `ExtractorError` for a private-video message and uses no fixture; it proves neither `UnsupportedError` classification nor the unsupported-URL UI/storage path. The relevant evidence already exists and passed: `test_subclass_ordering_is_not_swallowed_by_the_base_class` proves `UnsupportedError -> UNSUPPORTED_URL`, while `test_an_unsupported_url_shows_the_extractors_message_character_for_character` and `test_a_failed_probe_leaves_the_job_failed_and_recorded` drive a real manager/process boundary with `errors/unsupported_url.json`. The row's conclusion that this is thinner than a live yt-dlp failure remains correct. | Point the row at those classification and UI/storage tests, call the fixture a recorded **error** fixture rather than an `info_dict`, and retain the honest limitation: the child replays the recorded failure instead of obtaining it from live yt-dlp. | **Open, non-blocking — evidence-table correction** |
| `T033-R3` | **Low** | **No** | Correcting “PyInstaller is absent” to version 6.21.0 is right, and the required Windows frozen-job result remains externally blocked. The current T-033 task still says the repository cannot locally produce the collection-removal negative run, Linux frozen result, or size delta. That no longer follows: PyInstaller 6.21.0 is installed, the workflow publishes the exact local build/probe/size commands, and this review history already records a successful local PyInstaller 6.21 Linux artifact build for `T014-R3`. What cannot be produced on this host is the Windows result; what the acceptance criterion additionally demands is both named CI jobs green. | Keep T-033 Blocked, but distinguish the external Windows/exact-CI requirement from the Linux build, collection-removal mutation, and Linux size comparison that can now be gathered locally. Correct the stale “cannot produce locally” sentence in `ai/TASKS.md`. | **Open, non-blocking — T-033/current-truth follow-up** |

### T-074 judgment

The Linux result is accepted at its stated weight. The reviewer repeated the crash-site test in
forty separate pytest invocations with forty passes and ran the whole manager module once with
all 71 tests passing. This corroborates simple-repetition failure on Linux without clearing
suite-wide ordering or Windows.

The ownership rule-out is also useful. The manager fixture retains every `DownloadManager`,
drives `shutdown()` to `is_idle`, and `_release()` refuses to remove the `_Session` while its
`ResultPump` is running. The start-failure path briefly pops the session but `_unwind()` restores
any started pump to `_sessions` until it finishes. That rules out the straightforward
`session_ended -> _release -> last pump reference dropped inside run()` chain. It does not identify
the faulting object or make the intermittent access violation less open, and the task correctly
continues to say so.

### Independent verification

| Check | Result |
|---|---|
| Boundary identity | `HEAD == origin/main == 13138e3`; clean tree before the review append |
| `git diff --check 9802a6a..13138e3` | Passed |
| Focused evidence tests | **6 passed**: the cited generic-message test, the actual unsupported classification/UI/storage tests, the spawned-worker test, and the T-074 crash-site test |
| T-074 crash-site repetition | **40 separate invocations passed**, no non-zero exit |
| `tests/integration/test_manager.py` | **71 passed** in 35.70 s with localhost sockets enabled |
| First sandboxed manager-module attempt | **61 passed, 10 failed** solely at `ThreadingHTTPServer` construction with sandbox `PermissionError`; rerun above with localhost access |
| Spawned worker with `DISPLAY` and `WAYLAND_DISPLAY` removed | **1 passed** |
| Normal spawned-worker environment | Test passed while `DISPLAY=:0` and `WAYLAND_DISPLAY=wayland-0` were present, proving the current test does not enforce its name |
| Local PyInstaller | **6.21.0** |

### Final disposition

T-074 remains **Ready / undiagnosed**. Its new negative evidence and narrow lifecycle rule-out are
accepted; no source correction is implied by this review.

The Phase 1 evidence table is not ready for sign-off because the headless row currently maps a
required condition to gates that never create that condition. The unsupported-URL behavior is
already covered, but its row names the wrong test and fixture class. T-033 remains Blocked for its
external Windows and exact-CI evidence; its local-evidence wording gets a non-blocking
current-truth follow-up.

<!-- review-migration:0087:end -->

<a id="migrated-review-0088"></a>
<!-- review-migration:0088:start -->

## 2026-07-29 — Phase 1 evidence-table focused correction re-review

**Reviewer:** Codex (Reviewer)
**Base:** `13138e3`  **Head:** `f852bed`
**Scope:** Corrections for `P1EXIT-R1`, `P1EXIT-R2`, and `T033-R3`
**Boundary classification:** Integration-test addition and documentation/evidence; no production
source, workflow, dependency, or build-configuration change
**Verdict by finding:** `P1EXIT-R1` **Partially corrected, still open**; `P1EXIT-R2` **Still
open, non-blocking**; `T033-R3` **Partially corrected, still open and non-blocking**
**Overall verdict:** **Changes requested** on `P1EXIT-R1`. The ordinary initial-plus-focused
review budget is exhausted with a blocking Medium remaining.

The correction is the single commit `f852bed`. `HEAD` and `origin/main` both resolved to it, and
the tree was clean before this review record was appended.

### Finding dispositions

| ID | Severity | Blocks approval | Focused evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `P1EXIT-R1` | **Medium** | **Yes — Phase 1's headless exit criterion** | The environment half is genuinely corrected. `test_the_worker_really_runs_with_no_display_attached` launches a fresh interpreter with `DISPLAY` and `WAYLAND_DISPLAY` absent and asserts their absence inside that child. Removing `env=environment` failed independently and named both inherited values. The workload half remains split away from that condition: the scrubbed child calls only the private `_import_ytdlp()` helper and checks that it returned. It never calls `run_session`, emits or validates a protocol sequence, or completes worker work. The separate `test_the_worker_runs_in_a_real_spawned_process_with_no_display` does those things, but still starts an ordinary `multiprocessing.Process` under the inherited desktop environment and still calls that child “headless.” A display dependency introduced after yt-dlp resolution can therefore leave the claimed headless gate green. | Put the scrub and the worker session in the same observation. For example, remove the display variables before starting the existing real spawned-process test, assert their absence inside `_spawn_target`, then run and validate its real `run_session`/queue path. Mutation-check both halves: restoring the inherited environment and introducing a worker-path display dependency must each fail. Rename or correct the old test/docstring so it no longer independently claims an inherited-display child is headless. | **Still open** |
| `P1EXIT-R2` | **Low** | **No** | The row no longer mislabels an inline exception as a fixture, and `test_a_failure_reaches_the_parent_classified_and_verbatim` does exercise `run_session`, queue carriage, protocol validation, and exact message equality. It raises `GeoRestrictedError`, however, and asserts `GEO_RESTRICTED`. It never constructs `UnsupportedError` or observes `UNSUPPORTED_URL`, so it is still not evidence for the row “An unsupported URL produces a failed job.” `test_yt_dlps_bug_report_boilerplate_does_not_reach_the_user` likewise uses generic `ExtractorError`. The replacement therefore repeats the original mapping defect with a different unrelated error class. | Either inject `UnsupportedError("Unsupported URL: ...")` through the same `run_session` path and assert `UNSUPPORTED_URL` plus exact text, or cite the existing `UnsupportedError -> UNSUPPORTED_URL` classification and unsupported-URL UI/storage tests together. Retain the honest statement that no live unsupported URL is sent through yt-dlp. | **Still open, non-blocking** |
| `T033-R3` | **Low** | **No** | The local Linux positive evidence is real. The retained artifact occupies **194260 KiB** by the workflow's `du -sk` measure; an independent `--ytdlp-probe` reported version `2026.07.04` against pin `2026.7.4`, 1,751 extractors, and `youtube` from `yt_dlp.extractor.youtube`; `frozen_smoke.py` completed in about three seconds with one top-level start and no orphan. Two current-truth problems remain. First, `ai/TASKS.md:1325-1328` calls the collection-removal mutation “genuinely external,” although the same local PyInstaller build can remove line 37 of the spec and run the negative probe; T-033 is not “Blocked on Windows only” while that local acceptance proof remains undone. Second, lines 1345-1348 still say the local run is source-mode and both frozen platforms are pending, and `ai/STATUS.md:521-525` repeats the same superseded state. | Run and revert the collection-removal mutation locally, or accurately leave that local evidence pending. Then make TASKS and STATUS agree on one state: Linux frozen positive complete, Linux collection negative complete or pending, Windows frozen external. Only the Windows half is an external blocker. | **Partially resolved, still open and non-blocking** |

### Independent verification

| Check | Result |
|---|---|
| Boundary identity | `HEAD == origin/main == f852bed`; clean tree before the review append |
| `git diff --check 13138e3..f852bed` | Passed |
| New and related evidence tests | **7 passed** |
| `tests/integration/test_worker.py` | **55 passed** in 4.29 s |
| Headless positive control | Removing `env=environment` **failed** as intended, naming `DISPLAY=:0` and `WAYLAND_DISPLAY=wayland-0`; mutation restored |
| `ruff check tests/integration/test_worker.py` | Passed |
| `ruff format --check tests/integration/test_worker.py` | Passed; one file already formatted |
| Bare `mypy` | Passed: **78 source files** |
| Bare `mypy --platform win32` | Passed: **78 source files** |
| Retained Linux artifact size | **194260 KiB** via `du -sk dist/tracks-and-trails` |
| Retained artifact `--ytdlp-probe` | Passed: bundled baseline `2026.07.04`, pin `2026.7.4`, 1,751 extractors, `youtube` resolved |
| Retained artifact `frozen_smoke.py` | Passed in about 3 s: child spawned, message exchanged, child reaped, one top-level start, no orphan |

### Final disposition

The correction establishes a real display-free child and a non-vacuous environment guard, but it
does not yet establish a **worker session** under that condition. `P1EXIT-R1` therefore remains a
blocking Medium finding and the Phase 1 headless criterion is not ready for sign-off.

`P1EXIT-R2` and `T033-R3` remain non-blocking corrections: the former still cites a geo-restriction
test for unsupported-URL behavior; the latter has real Linux positive frozen evidence but still
misclassifies its local negative proof as external and retains contradictory source-only text.

Under `AGENTS.md` §10, the ordinary review budget is now exhausted with a blocking Medium finding.
Another focused correction pass requires the maintainer to authorize it, accept the documented
risk, change scope, or carry it into a named follow-up.

<!-- review-migration:0088:end -->

<a id="migrated-review-0089"></a>
<!-- review-migration:0089:start -->

## 2026-07-29 — Final authorized Phase 1 evidence-table correction review

**Reviewer:** Codex (Reviewer)
**Authorization:** The maintainer explicitly authorized one final pass
**Base:** `f852bed`  **Head:** `6e23d43`
**Scope:** Final corrections for `P1EXIT-R1`, `P1EXIT-R2`, and `T033-R3`, including the newly
measured T-033 collection-removal survivors
**Boundary classification:** Integration-test correction and documentation/evidence; no production
source or final build-configuration change
**Verdict by finding:** `P1EXIT-R1` **Resolved**; `P1EXIT-R2` **Resolved**; `T033-R3` **Local
evidence resolved, current-truth correction still incomplete**
**Overall verdict:** The Phase 1 evidence-table corrections are **Approved**. T-033 is **Blocked**
on `T033-R4`, a maintainer decision about its invalidated acceptance criterion, and the already
known external Windows build.

The boundary contains two commits: `c49ef96` records the preceding review, and `6e23d43` contains
the corrections and new T-033 evidence. `HEAD` and `origin/main` both resolved to `6e23d43`, and
the tree was clean before this review record was appended.

### Finding dispositions

| ID | Severity | Blocks approval | Final evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `P1EXIT-R1` | **Medium** | **Yes — resolved** | The display condition and worker workload are now one observation. The parent removes `DISPLAY` and `WAYLAND_DISPLAY` before `spawn`; `_spawn_target` checks their absence inside that child; the same child executes `run_session`; and the parent validates the real protocol sequence and `Probed` outcome. Independently removing the scrub failed with the child's inherited-display assertion and both values. Independently adding a post-guard `os.environ["DISPLAY"]` dependency failed with `KeyError: 'DISPLAY'` from the work process. | None. | **Resolved** |
| `P1EXIT-R2` | **Low** | **No** | `test_an_unsupported_url_fails_the_job_with_the_extractors_own_message` now raises the correct `UnsupportedError` through `run_session`, validates the sequence, and asserts both `UNSUPPORTED_URL` and the exact generated message. An independent mutation removing the `UnsupportedError` mapping failed with the observed kind `EXTRACTOR_ERROR`, while preserving the message, exactly isolating the subclass-ordering gate. The table accurately retains the limitation that yt-dlp URL recognition itself is injected rather than live. | None. | **Resolved** |
| `T033-R3` | **Low** | **No — superseded by the substantive T033-R4 blocker** | The requested local evidence was produced: baseline and both collection-removal builds completed, their distinct sizes prove the mutations applied, and both negative probes survived. The task now records that result and marks the acceptance criterion unachievable as written. Current-truth cleanup is incomplete: the T-033 status still says “Blocked on Windows only” while a maintainer acceptance decision is also owed; its Scope still states the now-disproved static-analysis premise; and `ai/STATUS.md:530-537,562-572` still says the collection negative remains to run and that hosted jobs are the only constraint. | Rewrite TASKS and STATUS around the finding below: Linux positive and negative builds complete; submodule collection redundant for this pin; package data remains load-bearing but ungated; Windows external; acceptance-criterion decision required. | **Evidence resolved; documentation follow-up remains** |
| `T033-R4` | **High** | **Yes — T-033** | The conclusion “neither collection line is necessary” does not follow from the surviving probes. The independent `collect_submodules -> []` build also passed, and the pinned `_extractors.py` really does contain 928 static relative imports, so the explicit submodule collection is redundant for this pin. The data mutation is different: removing `collect_data_files("yt_dlp")` produced a passing probe **while deleting all three yt-dlp YouTube solver assets present in the baseline artifact**: `yt.solver.core.js`, `yt.solver.deno.lib.js`, and `yt.solver.bun.lib.js`. yt-dlp loads these with `importlib.resources` through `vendor.load_script`; `EJSBaseJCP._builtin_source` uses `yt.solver.core.js`, and the Deno/Bun providers use the other two. The current probe only instantiates `YoutubeIE` and checks its URL predicate, so it never touches this runtime data. The mutation survival therefore proves the frozen gate is blind to package-data loss, not that the data line is dead. The causal record is also incomplete: PyInstaller processed a package-supplied `yt_dlp/__pyinstaller/hook-yt_dlp.py` through the `pyinstaller40` entry point, contrary to the claim that no yt-dlp hook exists. That hook does not collect these three assets, so it does not rescue the data mutant. | Keep `collect_data_files("yt_dlp")`. Extend the frozen probe to load at least the shipped built-in core solver through yt-dlp's real `vendor.load_script` path and verify its expected hash; then removing the data collection must fail. Decide separately whether `collect_submodules` stays as explicit future-pin insurance or is removed as redundant for the current pin. Replace the impossible blanket negative criterion with those two distinct decisions, and re-evaluate them whenever the yt-dlp pin changes. | **Open — T-033 Blocked pending maintainer decision and correction** |

### Independent verification

| Check | Result |
|---|---|
| Boundary identity | `HEAD == origin/main == 6e23d43`; clean tree before the review append |
| `git diff --check f852bed..6e23d43` | Passed |
| Corrected Phase 1 tests | **2 passed** |
| Full `tests/integration/test_worker.py` | **56 passed** in 4.47 s |
| Headless scrub mutation | **Killed**: child exited 1 and named inherited `DISPLAY=:0`, `WAYLAND_DISPLAY=wayland-0` |
| Headless workload mutation | **Killed**: child exited 1 with `KeyError: 'DISPLAY'` after the headless guard |
| Unsupported mapping mutation | **Killed**: expected `UNSUPPORTED_URL`, observed `EXTRACTOR_ERROR` |
| `ruff check` / `ruff format --check` on changed test | Passed; one file already formatted |
| Bare `mypy` | Passed: **78 source files** |
| Bare `mypy --platform win32` | Passed: **78 source files** |
| Maintainer-reported full suite | **1401 passed** |
| Baseline retained artifact | **194260 KiB**; yt-dlp probe and frozen spawn/reap smoke passed |
| Independent submodule-removal build | **192164 KiB**; probe still passed with 1,751 extractors and concrete `YoutubeIE` |
| Independent data-removal build | **194076 KiB**; probe still passed, but all three baseline `yt.solver*.js` assets were absent |
| Pinned extractor graph | `_extractors.py` contains **928** static `from .` imports |
| PyInstaller hook discovery | Processed `yt_dlp/__pyinstaller/hook-yt_dlp.py`; package entry point is `pyinstaller40: hook-dirs = yt_dlp.__pyinstaller:get_hook_dirs` |

Both temporary spec mutations were reverted. The independent artifacts and the unsupported-error
pytest plugin remain under `/tmp`; no build or production file in the repository was changed.

### Final disposition

`P1EXIT-R1` and `P1EXIT-R2` are **Resolved**. The Phase 1 evidence table now maps both criteria to
tests that exercise the claimed condition, and this final authorized pass introduces no new Phase
1 blocker.

T-033 is **Blocked**, not Approved and not “Windows only.” Its Linux artifact contains a usable
extractor and its collection-removal results are now known, but those results split the two spec
lines: submodule collection is redundant for the pin; data collection ships runtime YouTube
solver assets the probe cannot see. The maintainer must revise the impossible acceptance criterion
and decide the submodule line's defense-in-depth policy; the data line should remain and gain a
resource-aware frozen gate. Windows evidence remains externally pending.

Per the maintainer's instruction, this is the last review pass. No further automatic correction
review will be initiated.

<!-- review-migration:0089:end -->

<a id="migrated-review-0097"></a>
<!-- review-migration:0097:start -->

## 2026-07-29 — Phase 1 exit review

**Reviewer:** Codex (Reviewer)
**Subject:** The eight Phase 1 exit criteria and their evidence table in
`ai/IMPLEMENTATION_PLAN.md`
**Phase span inspected for context:** `7b7860d..e2e60e9`; previously approved implementation
boundaries were not re-reviewed
**Verdict:** **Approved — Phase 1 exits with the `OPS-005` and `OPS-007` residuals explicit**

This review challenged the two decisions that removed the last blockers rather than treating
them as fixes. Neither decision closes its underlying task. `T-066` remains Blocked on
frozen-artifact evidence deferred to Phase 5, and `T-074` remains open at Medium with an
unexplained access violation and all four diagnostic criteria unmet.

### Finding

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `P1EXIT-R3` | **Low** | **No — corrected in the reviewed table** | `IMPLEMENTATION_PLAN.md:146` cited only `test_an_unsupported_url_fails_the_job_with_the_extractors_own_message`. That worker-level test proves the typed `Failed` protocol outcome and exact text, but it neither creates a durable `Job` nor shows text in the UI, so by itself it did not prove the criterion's “failed job showing” claim. `tests/ui/test_add_dialog.py:1448` proves character-for-character display and `:1469` proves the queued job is stored `FAILED` with the same kind and message. Both passed in the full gate. | Cite all three observations and keep the existing `_extract`-seam limit explicit. | **Resolved in this review** |

No blocking finding remains.

### Decision challenge: `OPS-007`

The access violation is a real, unresolved event in a production-path module, and accepting it
weakens the confidence conveyed by “verified on Windows.” It is nevertheless an acceptable
phase residual on the record available:

- The event was loud—an interpreter crash and red gate—not a silent wrong download or path-safety
  failure. Product-versus-harness remains unknown and is stated that way.
- The evidence does not imply that `T-090` fixed it. The pre-`T-090` population was already clean,
  and both the decision and the updated table say so.
- The attempt arithmetic is internally consistent: `12 + 24 + 15 = 51` deliberate full-suite
  runs, and `51 + 60 + 250 = 361` total attempts. The earlier 373 count would double-count the
  12-run batch already included in the 36-run pre-fix population.
- The High-to-Medium downgrade satisfies `AGENTS.md` §10. `OPS-007` is an explicit maintainer
  approval; it states the reasons—reproduction routes exhausted, further repetition costly, loud
  failure mode—and records the downgrade against `T-074`. This exit review records that
  disposition with the finding rather than inferring it from a clean run.
- `T-092` makes recurrence diagnostic by capturing a dump, and `OPS-007` reopens on any recurrence
  or on a user-reachable defect traced to `result_pump.py`.

This is risk acceptance, not proof that the event cannot recur.

### Decision challenge: amended `OPS-005`

Deferring `T-066`'s remaining frozen evidence to Phase 5 is sound for this phase:

- Phase 1's deliverables and eight exit criteria contain no frozen-build, installer, virtualenv,
  or packaging condition.
- Phase 0 owns and has exited on the frozen `spawn` smoke through `T-020`. The plan's additional
  frozen-build risk-register row also assigns that mitigation to Phase 0.
- Phase 5 owns the actual Windows PyInstaller distribution, and `T-033` owns inclusion and
  validation of the yt-dlp baseline there.

The concession is material: a different frozen process-tree shape could mean `T-019`'s source or
virtualenv reaping evidence does not describe the shipped application. The decision names that
assumption and places its measurement beside the artifact that creates the shape. Holding the
vertical-slice exit for a Phase 5 artifact would invert the plan's sequencing.

The earlier review sentence saying the frozen blocker remained predates this explicit amendment.
It is superseded history, not an unresolved contradiction.

### Exit-criterion verification

| Criterion | Reviewer result |
|---|---|
| Real download, progress, final bytes | Met. Real yt-dlp downloaded from a loopback HTTP server; the evidence test asserts file, reported, stored, and served byte counts agree |
| Cancel under 2 seconds, no orphan | Met. Real-byte cancellation, stubborn-worker escalation, and both descendant-reaping cases passed |
| Killed worker becomes `WORKER_CRASH`; app survives | Met. Exit-code mapping, zero-without-outcome, and restart-after-crash tests passed |
| State survives restart mid-download | Met. Separate-interpreter hard kill leaves a confirmed `RUNNING` row which the next application start recovers |
| Unsupported URL becomes a failed job with exact message | Met after `P1EXIT-R3`'s citation correction; the `_extract` injection limit remains explicit |
| Worker runs with no display | Met. One spawned-child observation asserts the variables absent and runs real `run_session`; both display mutations were independently killed |
| Linux and Windows verified | Met with residual. Linux passed below; approved `T-073` evidence records the full `STARBASE` gate, with `T-074` dispositioned by `OPS-007` |
| Reviewed and signed off | Met by this review |

### Independent verification

| Check | Result |
|---|---|
| Working-tree isolation | Clean at `e2e60e9` before reviewer-owned documentation edits; no concurrent work observed |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; **106 files** already formatted |
| `mypy src` | Passed; **35 source files** |
| Configured `mypy` | Passed; **78 files** |
| Configured `mypy --platform win32` | Passed; **78 files** |
| Thirteen named criterion tests | **13 passed, 125 deselected** in 10.36 s |
| Full default suite | **1430 passed, 11 skipped, 2 deselected** in 124.41 s |
| Headless inherited-display mutation | Killed: the spawned child observed `DISPLAY` and `WAYLAND_DISPLAY` and failed |
| Headless workload-display mutation | Killed: adding a display lookup to `run_session` prevented the required protocol sequence |
| Unsupported-error mapping mutation | Killed: removing the `UnsupportedError` mapping produced `EXTRACTOR_ERROR` instead of `UNSUPPORTED_URL` |
| Windows run arithmetic and workflow | Run IDs, populations, totals, and `windows desktop` gate shape agree across `T-073`, `T-074`, `OPS-007`, and the workflows |

The first concurrent mypy attempt shared one incremental cache across native and Windows-platform
processes and produced two spurious `ctypes.windll` errors. After moving that cache aside, the
documented commands passed sequentially; a no-incremental Windows-platform run passed as a control.
This was a review-harness collision, not a project finding.

The private GitHub run contents were not independently downloadable with the credentials available
in this environment. This review therefore relies on the already-approved committed `T-073`
external evidence for the Windows execution, while independently checking its workflow shape and
the arithmetic carried into `OPS-007`.

### Residuals carried out of the phase

- `T-074`: one unexplained Windows access violation in or adjacent to `ARC-002` result delivery;
  accepted by `OPS-007`, open at Medium, with `T-092` as the recurrence trap.
- `T-066`: frozen-artifact process-tree evidence remains unobtainable while hosted quota is
  exhausted; accepted by amended `OPS-005` and measured with `T-033` in Phase 5.
- Linux verification is a maintainer-machine run under `OPS-006`; it does not detect a dependency
  newly introduced on a system library already present on that desktop.
- yt-dlp's own unsupported-URL recognition is not exercised by the criterion test; the typed error
  is injected at the adapter `_extract` seam.

### Final disposition

All eight Phase 1 criteria are met at the level the accepted decisions define. The two unresolved
items are documented residuals with owners and reopening conditions, not hidden green claims.

**Phase 1 exits on 2026-07-29.**

<!-- review-migration:0097:end -->
