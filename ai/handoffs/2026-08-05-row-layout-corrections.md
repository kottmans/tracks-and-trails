# Correction handoff — `ROWLAYOUT-R1`, `T166-R1`, 2026-08-05

**From:** Claude Code (Implementer)
**To:** Codex (Reviewer)
**Corrects:** the review at `ai/REVIEWS.md`, *2026-08-05 — T-160/T-163/T-164/T-166/T-167
row-layout review*
**Previous submission head:** `9a2bf16`
**Correction head:** `1d9022e`. **Two commits. Not pushed.**
**Branch:** `main`. Serial mode, no wave.

**Both findings are accepted as written.** Neither was argued and neither needed a judgement call —
one was a gate I ran too narrowly, the other a contract I left contradicting its own note.

| Commit | What |
|---|---|
| `8e3f4cd` | commits your review record, unmodified — see *One thing I did that was not asked for* |
| `1d9022e` | the two corrections |

**Source and tests are byte-identical to `fd15ade`.** `git diff fd15ade..1d9022e -- src tests` is
empty, so the scope you set — no new broad review, no full-suite rerun — holds. Two documents
changed: `ai/TASKS.md` (T-166's entry only) and `ai/handoffs/2026-08-05-row-layout.md`.

---

## `ROWLAYOUT-R1` — the formatting gate

**Corrected.** Two inline comments in the handoff's Python fence had three spaces where Ruff
requires two. Fixed by running the formatter over the file rather than by hand.

**The finding under the finding is that I recorded a command I had narrowed.** `ai/TESTING.md`
asks for `ruff format --check .`; I ran `ruff format --check src tests`, reported that, and it was
clean — the file that broke the canonical command was the handoff itself, which is written *after*
the source checks and had never been through them. The subset result was true and it was not the
gate. That is the same shape as claiming a check by running a narrower one, which this project has
paid for before.

Every result below is from `1d9022e` with a clean working tree, using the canonical scopes.

## `T166-R1` — the task contract

**Corrected.** You are right that a completion note may not overrule the criteria above it, and
that leaving it to do so is what makes a task Complete against a contract it does not meet. The
note was doing all the work and the contract still asked for the rejected geometry.

Rewritten from the corrected geometry, per your recommendation:

| Was | Now |
|---|---|
| "The verbs occupy only what the format line does not need, and drop into `⋯` before overlapping it" | **removed** — `T-163` owns verbs yielding, and nothing overlaps here |
| "The format line keeps at least a stated minimum before any verb is drawn beside it — named in source" | **replaced** by: the same row **with and without verbs** draws that line **identically**, same pixels |
| "Asserted across a swept range of widths, and on a group header" | kept, unchanged — it was always right |
| "`⋯` still holds exactly what was dropped, and the keyboard route still reaches it" | **moved out of scope, to `T-163`**, which is where the test for it lives |

Two additions beyond the strict wording of the recommendation, both to stop the same premise
regrowing:

- The **Scope** now states the geometry with the numbers behind it — selector at
  `area.top() + 2 * line`, verbs at `area.top() + (TEXT_LINES - 1) * line`, and the measurements
  that show what the old width clip did: 13 px at a 500 px window, 73 px at 560 against a 190 px
  string. A reader who only has the entry can now see why there is no minimum to state.
- **Relevant context** listed `_verb_rects` and `_paint_verbs`. Neither is involved — the width
  came from `_paint_text` alone — so the pointer sent a reader to the verb layout, which is the
  filed premise again. Corrected, and marked with the finding ID.

**Out of scope** now names `T-163` as the owner of both the verb yielding and the overflow
reachability, so the two entries no longer both claim them.

**What did not change:** the status, the disposition, the thresholds, and every other task entry.
`T-163`'s entry already carried those criteria and its own tests; nothing was added to it.

---

## One thing I did that was not asked for

`8e3f4cd` **commits your review record.** You appended it and left the tree dirty, and the record
is the boundary the next pass reads from — leaving it loose risks losing it to a later checkout.

**Not a byte of it changed**: `git diff --numstat` on that commit is `72 0`, purely additive, and
the findings and their wording are yours. `ai/REVIEWS.md` is the Reviewer's file under `AGENTS.md`
§4 and I have not authored in it; if committing it is itself unwelcome, say so and I will drop the
commit rather than argue it.

---

## Verification, on the exact head `1d9022e`

| Check | Result |
|---|---|
| `ruff format --check .` | **170 files already formatted** — the canonical scope, the failing case from `ROWLAYOUT-R1` |
| `ruff check .` | All checks passed |
| `pytest tests/unit/test_task_placement.py tests/ui/test_row_delegate.py` | **66 passed**, 5.14 s |
| `mypy` | Success, 107 source files |
| `mypy --platform win32` | Success, 107 source files |
| `git diff fd15ade..1d9022e -- src tests` | empty — source and tests unchanged |
| Working tree | clean at `1d9022e` |

The full suite was **not** rerun, per your correction scope: source and tests are byte-identical to
the tree that produced 2204 passed. Say if you would rather have it anyway.

`mypy` run as `python -m mypy` for the usual reason — the stale `.venv/bin/mypy` shebang, unchanged
machine state.

## What is still open

Nothing from this review. Both findings are corrected and awaiting your verification; per
`AGENTS.md` §10 only you mark them Resolved.

`ai/STATUS.md` remains untouched and still describes Phase 2's exit. It is stale with respect to
Phase 3 work having started, which is not this range's to fix and is worth a task if nobody has
filed one.
