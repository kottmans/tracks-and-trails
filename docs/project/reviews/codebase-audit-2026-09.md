# September 2026 codebase audit

**Purpose:** Independent disposition of the maintainer-requested dead-code, complexity,
duplication and performance audit across production code and tools.
**Owner:** Reviewer
**Update when:** Audit evidence, finding disposition or the assigned follow-up changes.

## 2026-09-27 — Independent audit at the interface-stage head

**Reviewer:** Codex, independent of the implementer.
**Scope:** `src/`, `tools/`, and the test consumers of candidate dead/test-only APIs.
**Head:** `a7310d10aa8cb071f2cee6641b1113057967cd76`, clean when the review started.
**Round:** Initial audit, requested separately from T-184's focused correction review.
**Platforms verified:** Linux; Qt offscreen, synthetic queues, temporary files.
**Verdict:** **Changes requested.** T-351 remains the established High correctness finding;
T-352 owns the already-ruled retirement. The remaining actionable work is grouped into the
requested cleanup task T-353 and performance task T-354. This is not approval of T-184,
release readiness, or a general assertion that the entire codebase is defect-free.

### Method and scope limits

The implementer's September 24 sweep was treated as leads. Independently parsed all **69
production and 36 tool Python files** with AST, indexed name/attribute uses across `src`,
`tests`, `tools` and `packaging`, and ran the optional Ruff `ARG`, `PERF`, `FURB` and `C901`
rules as search instruments. They reported 58 diagnostics: 28 complexity, 19 unused-argument,
7 modernization and 4 performance diagnostics. These are not configured lint failures or
findings by themselves. Qt callbacks, logging filters, test-observation properties and exports
need caller analysis rather than deletion on the basis of a count.

Inspected the handoff's candidate symbols and hot paths, with additional reads through
`format_table`, `playlist_picker`, `options_dialog`, `preset_manager`, database migration and
store code, paths/templates/settings, result pumping, pool shutdown and updater replacement.
Reviewed test callers and their fixture/reset patterns. This was targeted code reading plus
repository-wide searches, not line-by-line proof of every function or a whole-suite profiler.
The performance counts below are independent measurements, not the handoff's timings.

### Findings

“Blocks approval” concerns the affected behavior/follow-up, not whether this audit may be
recorded. None of these adjacent findings is added to T-184's correction budget.

| ID | Severity | Blocks approval | Finding and evidence | Disposition/status |
|---|---|---|---|---|
| AUD26-R1 | High | Yes | Queue notifications and accessible format text mix `_rows` and `_visible` indices. Independently reproduced a three-member playlist before `solo`: collapsed, the emitted index was invalid; expanded, it named row 3 instead of visible row 4. Both spoken rows omitted the format. | **Open; existing T-351.** Its scope/criteria already cover the four affected callers. No duplicate task. |
| AUD26-R2 | Medium | No | Parent-owned Settings dialogs survive closing. Five open/reject cycles followed by posted-deletion/event processing and collection left **5 SettingsDialog objects and 475 child widgets** under the parent. The production factory clears its Python reference on `finished` but schedules no Qt deletion. Options/preset/add/format creation sites have related lifetime patterns; their full workflows need their own checks. | **Open; T-353.** Correct ownership after result consumption and verify repeated production open/close paths. Do not apply delete-on-close blindly to callers that read the dialog after `exec()`. |
| AUD26-R3 | Low | No | `main_window.save_geometry` truncates the live file before writing. A temporary-file fault injection that writes ten characters then raises `OSError` returned normally with the old geometry replaced by `'# Window p'`. | **Open; T-353.** Use an atomic replacement and test preservation on failed write. Consequence is loss of recoverable window placement, not loss of presets or downloaded media; do not reuse T109-R9's consequence unqualified. |
| AUD26-R4 | Medium | No | One `SELECTOR_ROLE` read per expanded playlist member invokes `_effective_format_text` **n(n+1)** times because each child recomputes the whole group. Counts at 25/50/100/200 members: **650/2,550/10,100/40,200**; elapsed **5.8/22.3/86.7/343.9 ms**. | **Open; T-354.** Compute reusable group facts with explicit invalidation for membership, request and status changes. These are model-role timings over all members, not measured viewport paint timings or a desktop benchmark. |
| AUD26-R5 | Medium | No | `_next_startable` reads the store once for every startable waiting job via `_waiting_order`. A 500-job synthetic waiting set produced **500 get calls** for one decision. `_fill_free_slots` repeats selection as slots fill. When the store has no pending revision, each call reads/deserializes SQLite. | **Open; T-354.** Bound repeated scheduling reads without weakening lane capacity, queue order, retry ordering, holds or durability. This probe measured call count with a fake store, not database latency. |
| AUD26-R6 | Medium | No | `redact('/a b' * n)` spends superlinear time in the cookie-path matcher despite containing no sensitive value. Independent 2,000/4,000/8,000-character inputs took **68.8/208.8/549.0 ms** with no registered secrets. This matcher runs at every formatter sink, including GUI-originated logging. | **Open; T-354.** Keep the privacy cases and bound adverse long-line cost. Synthetic worst-case evidence does not establish ordinary traceback latency or exploit traffic. |
| AUD26-R7 | Low | No | Dead members and obsolete test-only wrappers remain, and some tests describe a helper as the production decision when it is not. In particular, `test_reordering_changes_the_order_the_pool_starts_jobs_in` only asks `_next_waiting`; production uses `_next_startable`. | **Open; T-353.** Use the inventory below; migrate behavioral assertions to actual consumers before removing wrappers. Keep deliberate observation seams. |
| AUD26-R8 | Low | No | Repeated hot-path work is visible directly: staging `data()` resolves a preset before checking the role; group headers build segments even for simple identity/title roles; every queue change repolishes the gate label; thumbnail arrival invalidates whole models. | **Open; T-354.** Measure and reduce these bounded paths after the main playlist/scheduling work. Do not claim the handoff's 46/59-call paint counts or 235 µs polish timing as independently verified. |
| AUD26-R9 | Low | No | Small duplicated code and stale guidance have concrete cleanup opportunities: duplicate store pending-write settlement, codec sort branches, obsolete `custom_preset()` guidance, and test-only APIs retained by tests that can use current production routes. | **Open; T-353.** Preserve behavior and historical evidence. The inventory below distinguishes these from abstractions with no demonstrated payoff. |
| AUD26-R10 | Note | No | The redaction-order defect identified during the earlier sweep is corrected in the T-184 range and exercised by its seed test. Expanded hatch path redaction is a different, still-open defect. | No duplicate correction: follow **T184-R6** in the T-184 review. |

### Cleanup inventory and exclusions

**No production consumer found, with whole-repository references checked:**
`FailureDetail.auto_retryable`, `CONVERTING_AUDIO_CODECS`,
`JobRepository.next_queue_position`, `PANEL_VIEWPORT_MARGIN`, `QueueModel.download_count`,
`EDIT_KEY` (the key itself is Qt's standard edit trigger), `PlaylistSelection.toggle/is_empty`,
`SettingsDialog.show_default_preset/show_output_template/show_cookie_browser`,
`SettingsDialog._update_checks`, `MainWindow._job_reader` (only a composition test reads the
stored attribute), `process_tree.GROUPS_ARE_SUPPORTED` (export only), `SessionValidator.outcome/finished`,
`Staging.overrides/in_flight`, `ThumbnailStore.limit`, and `OptionsDialog._buttons`.
Verify consumer identity immediately before removing an overloaded name such as `in_flight`:
`Row.in_flight` is live. The new `_ok_button` does not read `_buttons`.

**Test-only behavior wrappers needing test migration first:**
`DownloadManager._next_waiting`, `worker.reserve_output_path/resumable_partial/preview_path`,
`environment.describe_candidates`, `job_state.allowed_from`,
`presets.custom_preset/post_processing_of`, `errors.classify`, `FailureDetail.context_map/retryable`,
`FormatSelection.with_mode`, `PlaylistSelection.none_of/chosen/set`, `Staging.duplicates/staged_job_ids`,
`LogView.has_log`, and `AddUrlDialog.edit_row`. Preserve useful assertions on the rule through
its actual production caller. Do not delete coverage merely because its old entry point is unused.
`set` has an internal caller in the unused `toggle` wrapper; this is a dead subgraph, not zero
textual references. `has_log` also reads bounded log content to answer an existence question,
but deleting the unused accessor is preferable to optimizing it.

**Mechanical simplifications in T-353:** replace the one-view `_row_counts` dictionary only if its
behavior remains explicit; remove unused project-owned arguments in `row_delegate._paint_segments`,
its forwarding `_paint_text`, `_paint_verbs`, and `reveal.open_command`; remove the unused
`flatten(order=...)` route after confirming its callers; update live `custom_preset()` guidance to
the existing selector-edit route. Shared tiny codec/size formatting and the store's identical
pending-write settlement are suitable only with preserved error/order tests. Removing the unused
`next_queue_position` entry does not justify a transaction-boundary refactor of the two live SQL
allocations. Cookie-path registration duplicates are safe to simplify while preserving every
spelling registered at the current boundary.

**Existing owner T-352:** `JobProgressView`, its builder and view-only tests/tools. Move live helpers
before retirement as that task already requires. Do not delete `job_detail.py` wholesale while
queue/delegate/format surfaces still import it.

**Keep, with no change requested:** Qt virtual methods and signature-required arguments;
logging `Filter.filter` implementations; lifecycle observation properties such as `is_idle`,
`outstanding`, `starts_are_held`, `gave_up_on_the_log`, `begun`, `is_held` and `pending_in`;
widget-exposing test seams; `forget_the_secrets`; theme rule tables/contrast calculation;
`db.SCHEMA_SNAPSHOT`, `protocol.validate_sequence`, and `UNMAPPED_KINDS`. These make actual
state or contracts observable, despite lacking production callers.

`YtdlpService.reverted`, manager `resolution_reported` and `protocol_violation` have no application
subscriber at this head, but the latter two are tested observation channels for real lifecycle
behavior, and `reverted` forwards a worker result through the service. No removal is requested
merely because the composed window currently uses another notification. This is a Note about
intentional seams, not an Accepted Risk closure of a defect.

No consolidation is requested solely for `app.compose`'s complexity score of 50, the six typed
writer operations/signals, pool singleton similarity, model field validation, or two HTTPS fetchers.
They have different ownership/signature/lifetime contracts. `_on_progress`'s chain also deliberately
orders signals after persistence; bypassing it because most messages do not write would recreate a
recorded ordering defect. Likewise, Settings' screen-room calculation has a no-screen fallback
that `bounded_to_screen` does not, so they are not interchangeable one-line implementations.
A redesign of these surfaces needs evidence and a bounded design, not an automatic cleanup mandate.

### Performance and tools disposition

T-354 also measures the stopped queue's timer wakeups, duplicate output-preview work and per-keystroke
settings saves, repeated worker option construction, and the `clear_completed` SELECT/DELETE
predicate. Their source paths are confirmed; workload cost and safe replacement are not yet measured.
Use measured impact to choose changes. Preserve immediate-settings semantics and transaction
boundaries. The explicit format-row and scheduling counts above make this task worth scheduling
without treating every micro-optimization lead as a promised implementation.

The theme applications at startup serve default-before-compose and configured-after-compose
states. No change is requested without startup evidence. `format_duration`'s lazy UI wrappers
avoid import cycles and already share a renderer; moving that seam is not urgent duplication
removal. `UNKNOWN_TEXT` duplication may be folded into T-352's existing helper move if it adds no
behavioral scope, not into another task.

All 36 tool scripts parsed. They include historical reproduction and Windows mutation adapters;
references and apparent duplication do not justify deleting captured evidence. The progress-view
mutation tools follow T-352. `t308_warning_stacking_probe` calls real `compose`/`present` with fresh
settings whose updater preference defaults on, so it can start the automatic release check.
This was established by call-path inspection, not by making a GitHub request. T-353 should make
that diagnostic's update-service dependency explicit/controlled while retaining the production
presentation path and isolated profile.

The search for test files registering `remember_a_secret`, `remember_a_path` or
`remember_the_hatch` without any local `forget_the_secrets` found **none** at this head. Relevant
hatch/log tests have reset fixtures or `finally` cleanup. This is bounded static evidence, not proof
of isolation across every possible exception. No global-fixture rewrite is requested on the
unconfirmed lead. The known uncontrolled staged probe stays in T-350; fixture consolidation must
not distract from its actual competing callbacks.

### Checks and readiness

Independent instruments reproduced the queue mapping defect, retained dialogs, geometry write
failure, playlist recomputation, scheduling reads and long-line redaction cost. Instruments were
under `/tmp` and are described above so the record does not depend on an ignored handoff. The first
scheduler instrument used an incorrect `_poll` cleanup attribute after printing its measurements;
it was corrected to the actual `_timer`, rerun, and exited successfully. No worker was started.

The configured Ruff/type checks and required unit/integration run for the reviewed implementation
are recorded in [T-184's same-head review](T-184.md#2026-09-27--correction-rounds-and-first-interface-review).
They do not make the independent counterexamples disappear. No complete UI suite, Windows runtime,
desktop, or external-network measurement was performed for this audit.

Documentation validation passed: **30 task-placement tests**, affected review links/anchors,
Ruff lint/format and `git diff --check`. Removing only the two new task records reconstructs the
previous TASKS file exactly. The historical migration verifier also passed all **381 entries**.

T-353 and T-354 are the two maintainer-requested follow-ups, entered as Proposed Phase 4.5 debt;
their order does not override the existing phase plan. Their status is not Complete and no source
fix is claimed. T-351/T-352 retain their existing scope. T-184's push hold is unchanged. This audit
commit changes its canonical record, the review index and the two task definitions only; it does
not rewrite STATUS, historical findings, source, tests or transient handoffs.
