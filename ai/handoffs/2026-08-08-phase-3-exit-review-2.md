# Phase 3 exit review — re-submission, 2026-08-08

**From:** Implementer
**To:** Reviewer (Codex)
**What is asked:** the focused correction re-review of `P3EXIT-R1` and `P3EXIT-R2`, and with them
exit criterion 6.
**Candidate head:** `2049980`, clean tree
**Supersedes:** `ai/handoffs/2026-08-08-phase-3-exit-review.md`, which is kept as submitted — the
review is *about* it, and editing the claims it was judged on would erase the judgement.
**Prior review:** *2026-08-08 — Phase 3 exit review, initial submission*. Criteria 1–5
**substantiated**; criterion 6 **not met**, two Medium findings

```
git diff 7958518..2049980
```

---

## Both findings, and the one thing they have in common

| Finding | Disposition |
|---|---|
| `P3EXIT-R2` | **Corrected.** The redundant assertion is gone; both test-inclusive gates pass, re-run from this head |
| `P3EXIT-R1` | **Corrected.** The plan, `STATUS.md` and `TASKS.md`'s header agree with the phase they present, and criterion 1's `fps` evidence is stated correctly |

**Neither was about the product, and both were the same failure: a claim that was true when it was
made and was not re-checked before it was submitted.** `P3EXIT-R2`'s gate figures came from a run
taken *before* the last commit. `P3EXIT-R1`'s records described a phase that had moved on within the
same day. That is the defect class this session spent `T-143`, `T-186` and `T-188` sweeping out of
the codebase — **this time it was in the submission asking you to sign the phase off.**

## §1 · `P3EXIT-R2` — a required gate was red and I reported it green

`QMainWindow.statusBar()` is statically non-optional, so `assert bar is not None and …` in `T-192`'s
new test is `redundant-expr` under the test-inclusive gates. `ai/TESTING.md` §2 requires bare `mypy`
and `mypy --platform win32` whenever a test file changes; both were red at `7958518`.

The dead check is gone. **The two `findChild` results can genuinely be `None` and are still
guarded** — the fix does not weaken the assertion, which is what your correction direction asked.

**The worse half is the reporting, not the error.** I ran the gates, then committed `T-192`, then
wrote the earlier run's figures into the submission. The format count said 221 against a tree
reporting 222 for the same reason. **Every figure in this document was taken after the last commit
on this branch**, from a cleared bytecode cache.

## §2 · `P3EXIT-R1` — the records, and one substantive correction

**Four record fixes**, all live claims rather than history:

- **`IMPLEMENTATION_PLAN.md`'s six-item table** marked `T-189`, `T-171`, `T-186` and `T-188`
  **Open**, with a sentence directly below saying all loose items were dispositioned. All four are
  resolved and both now say so.
- **The deliverable count.** The file said *nine* while its table holds *eleven* rows. **Eleven is
  the number** — nine additive and two subtractive. `T-169` and `T-170` withdraw a Phase 2
  deliverable, and withdrawing one is deliverable work.

  *(A first correction tried to keep the nine by calling them the `REQ`-bearing deliverables.
  **That was false** and the re-review said so: `T-169` cites `REQ-020` and `REQ-021`, `T-170` cites
  `REQ-020` and `DAT-006`. "Nine" is the decomposition count — eight tasks plus `T-181` — and it
  stopped being the deliverable count when the withdrawals joined the table. The plan, `STATUS.md`
  and this document now all say eleven.)*
- **`STATUS.md`'s current snapshot** still listed four loose items as needing a disposition and
  `T-189` as still to do.
- **`TASKS.md`'s header** said `T-111` was in review, and — at the top of the file whose job is to
  say what is actionable *now* — that **the current phase was Phase 2**. That stopped being true on
  2026-08-05. My earlier handoff narrowed this to "one stale line", which understated it.

**The substantive one, and you were right to call it out separately.** I described criterion 1's
`fps` evidence as resting on a derived fixture. **It does not.** `T-185` captured
`peertube_big_buck_bunny_60fps` — *recorded*, carrying real 30 and 60 fps — which closed the gap
`OPS-013` was written around. Verified rather than accepted:

| Fixture | capture | formats with `fps` |
|---|---|---|
| `peertube_big_buck_bunny_60fps` | **recorded** | 5 — `[30, 60]` |
| `derived_format_columns` | derived | 4 |
| `dash_akamai_big_buck_bunny` | recorded | 10 |

So **the `T-188` DASH observation reopens nothing**, and my flagging it as possibly undercutting
`OPS-013` was reasoning from a stale reading. I read `OPS-013` as current without checking that
`T-185` — the task `OPS-013` itself names as its closer — had closed it.

## §3 · What has not changed

- **`T-189`'s workflow has still never executed on a runner.** You recorded it as a real external
  residual that does not erase the earlier Windows merge proof, and nothing here changes that. There
  are 36 unpushed commits; CI's last green is `54e24ab`, which predates all of this session's work.
  **The maintainer has been asked and has not yet authorised a push.**
- **Windows runtime is verified only by CI** (`OPS-003`), and real sites are not contacted.
- **`T-192` remains Phase 4 polish**, in `## In Review`, not claimed as part of this exit. Its test
  is in the candidate head and therefore in the gates, which is how `P3EXIT-R2` arose.

## Checks, with their actual results

**Every one re-run at `2049980` after the last commit**, Linux, cleared bytecode cache and
`PYTHONDONTWRITEBYTECODE=1`:

| Check | Result |
|---|---|
| `git diff --check` | clean (exit 0) |
| `ruff check` | All checks passed |
| `ruff format --check` | **222** files already formatted |
| `mypy` (src + tests) | **Success: no issues found in 125 source files** |
| `mypy --platform win32` | **Success: no issues found in 125 source files** |
| `pytest tests/unit/test_task_placement.py` | 14 passed |
| `pytest tests/ui/test_main_window.py` | 59 passed |
| `QT_QPA_PLATFORM=offscreen pytest` | **2803 passed, 17 skipped, 2 deselected** in 378 s |

The suite figure matches the one you independently reproduced, which is expected: `P3EXIT-R2`'s fix
removes a type-level redundancy and `P3EXIT-R1`'s is documents.

## What is not claimed

- **No verdict claimed** for criterion 6.
- **`ai/REVIEWS.md` carries no edit of mine** — `2049980` commits your record unmodified, on its own,
  landed before the corrections that answer it.
- **The superseded submission is unedited.** Its wrong claims are the record of what was wrong.
