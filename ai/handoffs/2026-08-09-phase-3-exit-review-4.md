# Phase 3 exit review — `P3EXIT-R3` correction, 2026-08-09

**From:** Implementer
**To:** Reviewer (Codex)
**What is asked:** **nothing yet.** `P3EXIT-R3` is corrected and this document records it. **A fourth
pass is not authorized**, and this is not a request for one — see *The budget* below.
**Supersedes:** `ai/handoffs/2026-08-09-phase-3-exit-review-3.md` as the current statement.
**Prior review:** *2026-08-09 — Phase 3 exit authorized third pass.* **Verdict Blocked.**
`P3EXIT-R1` **Resolved**, `P3EXIT-R2` **Remains Resolved**, `P3EXIT-R3` **Open — Medium, blocking.**

---

## The budget, first, because it governs what happens next

`AGENTS.md` §10 caps the ordinary budget at one comprehensive review plus one focused correction
re-review. **That was spent, and the maintainer authorized a third pass explicitly.** Your record
closes with the consequence: *"another focused pass on a Medium blocker requires a new maintainer
authorization under `AGENTS.md` §10."*

**No such authorization has been given.** The maintainer's standing instruction was *"if it comes up
with any findings, please implement them and send them back"* — which authorizes **the correction**,
which is what this document is. **It does not authorize a fourth review pass**, and I am not
treating it as though it did. This sits and waits.

## §1 · `P3EXIT-R3` — corrected, and there was a second one you did not name

**You named `IMPLEMENTATION_PLAN.md:634-637`** — the residual paragraph saying `T-189`'s workflow
*"has never executed on a runner"*, contradicting `STATUS.md`, the submission, and the CI run you
independently verified.

**Corrected**, using the same run, head and bounded claim already in `STATUS.md`: run
`31295392039` at `9fe22fb`, all five jobs success, `TRACKSANDTRAILS_REQUIRE_FFMPEG=1` not turning
the required merge cases into failures, therefore criterion 2's Windows evidence is a real pass
rather than a skip inside a green job. The unexecuted state is kept as history in the same
parenthesis and named as `P3EXIT-R3`, per your direction that it be preserved as history rather than
as the plan's current answer.

**And then I swept, and found a second instance in the same file.**

> `IMPLEMENTATION_PLAN.md:598` — the Phase 3 deliverables table, `T-189`'s row:
> **"Residual: the workflow edit has never executed on a runner"**

**Your finding cited only the paragraph.** The table row says the same false thing, four lines above
the deliverable count that `P3EXIT-R1` was about, and it would have survived a correction that
fixed exactly what was reported. It is corrected the same way.

**This is `T186-R1`'s lesson applied to my own correction**: that finding needed three passes because
the first two searched for a *name* while the false claim was about *count*. Here, the reported
instance was prose and the unreported one was a table cell. **I searched three ways** — the wording
(*"never executed"*, *"has not executed"*, *"not yet executed"*), the **old run id** `31233348009` as
the other way to assert the same thing, and the word *residual* near `T-189` — and the table row was
found by the first, not by reading around the line you cited.

**What the sweep left alone, deliberately.** `STATUS.md:34` quotes *"`T-189`'s own gate has never
executed on a runner"* as what the exit review **recorded**, immediately before stating that it has
now executed. `IMPLEMENTATION_PLAN.md:643` says what the paragraph **used to** say. Both are past
tense about a superseded state; neither is a current claim. Every other hit in `ai/` is `T-087`'s
Windows lock branch or the opt-in network tests — different subjects.

## §2 · The defect class, since this is the fourth time it has been the finding

**Every finding in this exit review has been a document outliving the thing that changed it.**
`P3EXIT-R1` was records describing a phase that had moved on. `P3EXIT-R2` was gate figures from a
run that predated the last commit. `P3EXIT-R3` is a residual closed everywhere except the file that
is the exit record.

**The specific failure here is worth naming precisely.** When CI went green I updated `STATUS.md`
and wrote the submission, and I did not ask *which other file asserts this*. `IMPLEMENTATION_PLAN.md`
was edited twice more that same day — for Phase 4's decomposition and its new GUI criterion — and the
false paragraph was not touched either time, because I was editing a different section. **Proximity
is not what makes a claim stale.**

## §3 · What has not changed

- **No verdict is claimed for criterion 6**, and none is requested.
- **`T-192`, `T-193` and `T-194`** remain `## In Review`, unreviewed, outside this exit.
- **Windows runtime is verified only by CI** (`OPS-003`); **real sites are unverified**
  (`ai/TESTING.md` §5).
- **`ai/REVIEWS.md` carries no edit of mine.** Your third-pass record is committed at `4091640`,
  on its own, before the correction that answers it.

## Checks, with their actual results

**Run at `ccdbd0f`**, Linux, `PYTHONDONTWRITEBYTECODE=1`.

| Check | Result |
|---|---|
| `git diff --check` | clean (exit 0) |
| `ruff check` | All checks passed |
| `ruff format --check` | **224** files already formatted |
| `mypy` (src + tests) | Success: no issues found in 125 source files |
| `mypy --platform win32` | Success: no issues found in 125 source files |
| `pytest tests/unit/test_task_placement.py` | 14 passed |
| `QT_QPA_PLATFORM=offscreen pytest` | **not re-run — see below** |
| CI at `9fe22fb`, run `31295392039` | all five jobs success |

**The format count moved 223 → 224, and the reason is arithmetic rather than a change to any file
you have seen.** `ruff format` counts markdown as well as Python here: **142 tracked `.py` + 82
tracked `.md` = 224**. The third-pass handoff added exactly one markdown file. This matches your own
reconciliation — *"the 223-file format count is reproduced when the later third-pass handoff file is
excluded"* — and it will rise by one again with this document. **I am stating the arithmetic because
an unexplained count that moved is what `P3EXIT-R2` was made of.**

**The full suite was not re-run**, on the construction you accepted and verified yourself:
`git diff a5f65c9..HEAD -- src tests` is **empty**. The suite's green result at `a5f65c9` —
**2807 passed, 17 skipped, 2 deselected, 4 warnings in 380.29 s** — describes this tree's `src/` and
`tests/` exactly. **Every commit since `a5f65c9` is markdown.** If you want it repeated at the exact
head regardless, say so; it is about 6.5 minutes and I do not expect the number to move.

**On the head these figures describe.** Measured at `ccdbd0f`; this document is committed after it,
and no `src/` or `tests/` file differs between the two.
