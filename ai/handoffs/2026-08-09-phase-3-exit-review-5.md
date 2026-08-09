# Phase 3 exit — `P3EXIT-R4` correction, 2026-08-09

**From:** Implementer
**To:** Reviewer (Codex)
**What is asked:** the focused re-review of `P3EXIT-R4`, under the maintainer's standing grant.
**Prior review:** *2026-08-09 — Phase 3 post-approval coordination review.* **Changes requested on
exit coordination.** Approval at `ccdbd0f` not reopened.
**Scope:** `ai/STATUS.md` and `ai/TASKS.md` only. **No source, no evidence, no Phase 4 task.**

---

## The finding, and that it was mine to make and mine to miss

**`P3EXIT-R4` is in the commit that recorded the exit.** `6114f51` changed `STATUS.md`'s top
snapshot to Phase 4 and left, four screens below it, a live table saying `P3EXIT-R3` was
*"Corrected, unverified"* and a sentence saying criterion 6 was the only criterion unmet. `TASKS.md`
still said Phase 3 was current in three places.

**This is the fourth consecutive finding of the same class**, and the first three were: records
describing a phase that had moved on, gate figures from a superseded run, and a residual closed
everywhere except the exit record. **This one is a phase exit recorded in a file that still said the
exit had not happened.**

## What was corrected

| Place | Was | Now |
|---|---|---|
| `STATUS.md` findings table | `P3EXIT-R3` *"Corrected, unverified"* | **Resolved** at the fourth pass, with `P3EXIT-R4` added as open |
| `STATUS.md` submission line | *"Criterion 6 is the only criterion still unmet"* | **Criterion 6 is met**, approved at `ccdbd0f` |
| `TASKS.md` header | dated 2026-08-08, *"Phase 3's exit review is the only thing outstanding"*, `## In Review` holds `T-192` alone | dated 2026-08-09, Phase 3 exited, **Phase 4 current**, three tasks in review |
| `TASKS.md` *Start here* | *"the current phase is Phase 3"* | **Phase 4, nothing started** |
| `TASKS.md` `## In Review` preface | *"Empty."* | names `T-192`, `T-193`, `T-194` as Phase 4 polish awaiting verdicts |

## The sweep, and the one instance it found beyond your finding

Three searches: **current-phase claims**, **"only thing outstanding" / "criterion 6 unmet"
phrasings**, and **`## In Review` described as empty**.

**One survivor, and it is a judgement call rather than a clear defect.** `ai/TASKS.md`'s `T-188`
entry, in `## Complete`, read *"…leaving the phase exit review as the only thing outstanding."* It is
**dated to its own approval and sits in `## Complete`**, so it is arguably the *"genuinely dated
historical narrative"* your direction says to preserve — but the participle reads as present tense.

**I anchored it rather than rewrote it**: *"which left the phase exit review as the only thing
outstanding **as of that date**"*, plus a parenthesis naming the approval. **The historical fact of
what `T-188`'s approval closed is intact.** If you think a `## Complete` entry needed no edit at
all, say so and I will revert that hunk — I would rather be told I over-corrected than leave a
sentence that reads as current.

**Everything else the sweep surfaced is inside explicitly dated `## YYYY-MM-DD` blocks** in
`STATUS.md`'s older narrative, which that file's own header scopes as *"kept for its reasoning, not
as a statement of what is true now."* Untouched.

## What is not claimed and not touched

- **The approval at `ccdbd0f` stands and is not reopened.** Nothing here asks you to revisit it.
- **No `src/` or `tests/` file has changed since `a5f65c9`** — still zero, verified.
- **`T-192`, `T-193`, `T-194`** remain unreviewed Phase 4 work with no verdict.
- **`ai/REVIEWS.md` carries no edit of mine.** Your coordination record is committed at `ed43469`,
  alone, before this correction.

## Checks, with their actual results

Run at `4aea3dc`, Linux, `PYTHONDONTWRITEBYTECODE=1`.

| Check | Result |
|---|---|
| `git diff --check` | clean (exit 0) |
| `ruff check` | All checks passed |
| `ruff format --check` | **225** files already formatted |
| `pytest tests/unit/test_task_placement.py` | 14 passed |
| `git diff a5f65c9..HEAD -- src tests` | **empty** |

**225 continues the arithmetic**: 142 tracked `.py` + 83 tracked `.md`. It was 224 at `ccdbd0f`;
`ai/handoffs/2026-08-09-phase-3-exit-review-4.md` added one, and this file will add another.

**mypy and the full suite were not re-run.** Both were clean at `a5f65c9` — 125 files on both
platforms, **2807 passed, 17 skipped, 2 deselected** — and **no `src/` or `tests/` file has changed
since.** Every commit after it is markdown. This is the construction you verified and accepted at
the third and fourth passes; say so if you want it repeated regardless.
