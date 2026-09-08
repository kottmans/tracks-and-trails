# history-row-layout-integration — Review record

**Purpose:** Dated review evidence and disposition history for this task or shared scope.
**Owner:** Assigned Reviewer · **Update when:** This scope is reviewed or rechecked.
**Covered tasks:** Cross-cutting scope; see the dated entries.

[Review index](../REVIEWS.md) · [Review policy](../TESTING.md#14-review-policy)

Moved from `85422bc0b086de9b18d2f809abb4d6bcebb180e4:docs/project/REVIEWS.md` on 2026-09-08.
The entries below retain their exact original bytes and relative order. Historical
path spellings, line citations and references to “above” describe that source;
the [migration manifest](../evidence/2026-09-08-review-migration.json) records the
original order and byte ranges. Shared entries are stored once; covered tasks
link to this same record. Navigation grants no approval or new review provenance.

## Recorded rounds

- [2026-08-05 — History × row-layout merge review](#migrated-review-0157)

<a id="migrated-review-0157"></a>
<!-- review-migration:0157:start -->

## 2026-08-05 — History × row-layout merge review

**Reviewer:** Codex (Reviewer)
**Merge base:** `38504b3`
**Parents:** `cba9f3e` (History) and `d605b73` (row layout)
**Merge commit:** `e48fae5`
**Submission head:** `4482383` (handoff only)
**Verdict:** **Approved for merge correctness at `4482383`.** The two conflict resolutions preserve
both reviewed streams exactly, the only merge-only executable change is the cross-feature History
paint test, and that test holds the one special interaction between the streams: a History group
with neither segments nor a fraction reserves no progress-bar width. **This is not a claim that CI
is fully green:** exact-head run `31065421037` remains in progress/queued at review time.

### Merge reconstruction

- **`ai/REVIEWS.md` is exact.** Both parents are byte-prefix appends to the merge-base file. The
  merged result is byte-for-byte `base + row-layout append + History append`: 108 and 123 added
  lines respectively, 231 together, with no deletion or rewritten review record.
- **`ai/TASKS.md` is exact.** Parsing all four revisions yields 165 unique task blocks apiece. The
  History parent changes only T-142, T-144, T-145, T-156 and T-159; the row-layout parent changes
  only T-160, T-163, T-164, T-166 and T-167. The sets are disjoint. Every merged block equals the
  sole parent that changed it, every untouched block equals base, and non-entry prose is
  byte-identical in base, both parents and merge. The placement gate passes all 14 assertions.
- **Executable union is exact.** The parents have no overlapping changed path under `src/`,
  `tests/`, `pyproject.toml` or `.github/`. Every non-conflict executable blob in the merge equals
  its reviewed parent. `tests/ui/test_history_view.py` is the sole executable path changed against
  both parents, and its only merge-specific addition is the named interaction test.
- **Merging instead of rebasing is accepted.** Both reviewed histories and the exact SHAs their
  review records cite remain reachable. Replaying a parent would have destroyed those established
  boundaries for no executable benefit.

### Interaction disposition

`RowDelegate._bar_reserve` returns zero when both `SEGMENTS_ROLE` and `PROGRESS_ROLE` are absent.
That is exactly the History-group contract accepted in UX-005: the group has no segmented progress
bar. The real-model test paints the group at 631 px and 400 px and observes no dropped verbs.

The test is **correctly placed in `test_history_view.py`**. Its valuable half is not generic delegate
arithmetic alone; it is that a real History group supplies neither bar role and consequently keeps
its two History verbs. Moving it to the delegate suite would either import the History surface there
or replace the real model half with another role fake, weakening the combination being reviewed.

The submitted mutation (“make History answer segments”) is killed by the explicit role assertion.
The reviewer separately mutated the layout authority in memory—forcing a 240 px reserve whenever
the real `_bar_reserve` answered zero—and the test failed at 400 px with both verbs in overflow.
Thus the overflow assertion independently guards the integration behavior rather than passing only
because the no-segments premise is asserted above it.

No second source interaction is missing from the empty overlap. T-160's body/control geometry is
role-generic and History supplies no editor control; T-166's selector/verb lines are already driven
through the same delegate roles; T-164 and T-167 apply only when segments exist. The absent-bar
branch is the one History-specific value the row-layout stream had not exercised, and it is now
covered.

### Independent verification

| Check | Result |
|---|---|
| Parent/base identity | Both merge parents resolve; `git merge-base cba9f3e d605b73` is exactly `38504b3`. The previously approved `cc94371` and `d605b73` SHAs remain reachable. |
| Conflict reconstruction | REVIEWS append identity: **exact**. TASKS audit: **165/165** entries equal their intended source; changed sets disjoint; non-entry prose exact. |
| Executable merge audit | Parent overlap: **empty**. Non-conflict blob mismatches: **none**. Sole merge-only executable path: `tests/ui/test_history_view.py`. |
| Focused combined tests | History view, row delegate and task placement: **117 passed**. |
| Merge-specific mutation | Forced nonzero reserve on the no-bar branch: **killed** at 400 px; both History verbs moved to overflow. |
| Submitted local gate | Implementer reports unit/UI/integration **2262 passed, 11 skipped**, plus clean ruff, formatting, host mypy and win32 mypy. |
| Live CI check | Run `31065421037` targets exact executable head `e48fae5`. Linux, frozen Linux and STARBASE coverage are **success**; Windows desktop is in its Full suite; frozen Windows remains **queued**. Overall status is **queued**, conclusion unset. |

No finding or source/test correction is required. The merge may be treated as independently
reviewed, but not as CI-green until run `31065421037` reaches a successful conclusion for the two
remaining Windows jobs. The reviewer appended this record only; no source, test, task, commit,
remote ref, workflow run or CI state was changed.

<!-- review-migration:0157:end -->
