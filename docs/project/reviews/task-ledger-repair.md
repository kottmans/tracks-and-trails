# task-ledger-repair — Review record

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

- [2026-08-17 — Duplicate In Review entries repair](#migrated-review-0284)

<a id="migrated-review-0284"></a>
<!-- review-migration:0284:start -->

---

## 2026-08-17 — Duplicate In Review entries repair

**Reviewer:** Codex (Reviewer)
**Task:** none — current-truth repair not covered by a task
**Base:** `8b027cd414fb35af43eca693b49d56a9730c1a4e`
**Head:** `e61152d6741d9c4175a610ef4071561932a6ff5c`
**Platforms verified:** Documentation structure on Linux; no platform behavior changed
**Verdict:** **Approved with follow-ups.** The second copies are removed exactly. The missing
uniqueness invariant is non-blocking follow-up `T-261`; it does not require putting this repair
behind a newly filed task first.

### Findings

| ID | Severity | Blocks approval | Finding | Recommendation | Status |
|---|---|---:|---|---|---|
| **COORD-R23** | **Low** | No | At the base, `T-256`, `T-259` and `T-257` each had two live `### T-NNN` entries under the one `## In Review` heading. `live_entries()` suppresses the later copy with `seen`, while `status_line_counts()` overwrites the earlier dictionary value, so every `T-096` assertion can remain green. This is not a reason to widen T-258 or reject the exact deletion, but it is the second structural edit that the task-board gate did not see. | Assert that live task-entry headings are unique, with a mutation that duplicates one complete valid entry in the same section. | **Open — `T-261`; no re-review of e61152d required** |

### Independent checks

| Check | Result |
|---|---|
| Boundary | One commit and one file: `ai/TASKS.md`; `git show --check e61152d` passed |
| Base structure | One `## In Review` heading, but `T-256`, `T-259` and `T-257` headings each appeared twice before `## Complete` |
| Head structure | One live heading for each of the three task IDs; the first copies are unchanged |
| Task-placement gate | **14 passed** on the repaired head; inspection confirmed both parsers still collapse duplicate IDs |
| Commit-message gate | Both commits in `8b027cd..dbc1e6c` passed; `Task: none - <reason>` is the repository's valid explained exemption, so no task entry or trailer rewrite is required |

### Readiness

The records repair is approved at `e61152d`. It may stay as the separate no-task commit already
submitted. `T-261` owns preventing recurrence and does not hold this repair or T-258.

<!-- review-migration:0284:end -->
