# Phase 3 exit review — third pass, 2026-08-09

**From:** Implementer
**To:** Reviewer (Codex)
**What is asked:** the **third focused pass** on `P3EXIT-R1`, and with it exit criterion 6.
**Supersedes:** `ai/handoffs/2026-08-08-phase-3-exit-review-2.md`, kept as submitted.
**Prior review:** *2026-08-08 — P3EXIT correction re-review.* **Verdict Blocked.** `P3EXIT-R2`
**Resolved**; `P3EXIT-R1` **Open — partially corrected**, on its count/scope half alone.

---

## The authorization, because this pass does not exist without it

`AGENTS.md` §10 caps the budget at one comprehensive review plus one focused correction re-review,
and your record says it directly: *"`AGENTS.md` §10 requires the maintainer to authorize a third
focused pass, accept…"*. **The maintainer authorized it on 2026-08-09**, in those words:
*"authorize the 3rd pass, write the handoff and run the tests at the submitted head."*

It is recorded in `ai/STATUS.md` as well as here. **`ai/REVIEWS.md` carries no edit of mine** — it
is the Reviewer's file under `AGENTS.md` §4, and the previous two submissions kept that line.

## §1 · `P3EXIT-R1` — the taxonomy, and the sentence I did **not** rewrite

**You offered two taxonomies and required one be applied consistently. I took the first**, which
your direction worded as *"eleven deliverables, of which nine are additive and two subtractive"*.

**The records carry it as one phrase, verbatim in both:**

> **Phase 3 has eleven deliverables: nine additive and two subtractive.**

`ai/IMPLEMENTATION_PLAN.md` §Phase 3 and `ai/STATUS.md`'s current snapshot. *(The wording differs
from your sentence only in punctuation — `: nine additive` rather than `, of which nine are
additive`. I am stating that rather than claiming "the same words", because "close enough" is the
habit this finding is about.)*

**"REQ-bearing" is gone**, and your refutation of it was correct — `T-169` bears `REQ-020` and
`REQ-021`, `T-170` bears `REQ-020` and `DAT-006`, so it could never have carried the distinction. It
appears nowhere in the records now.

**One thing your correction direction named is deliberately unchanged, and you should check whether
I was entitled to leave it.** The direction said to rewrite the *"Two Phase 3 deliverables"*
sentence — **but that instruction was attached to the second taxonomy**, the one that moves
`T-169`/`T-170` outside the Deliverables set. **Under the taxonomy I took, that sentence is true as
written**: they *are* deliverables, and they are the two subtractive ones. Rewriting it would have
made the record disagree with the count above it.

**If you read the instruction as unconditional, this is a miss and I will take it as one.** I am
naming it rather than hoping the difference goes unnoticed, because the pattern this finding is
about is a record that says two things at once.

## §2 · The candidate head has moved, and that is the thing to attack first

**24 commits since `2049980`.** Two of them touch product code:

| Commit | What | Status |
|---|---|---|
| `eff93ab` | `T-194` — reordering a row no longer scrolls the queue to the top | `## In Review`, **no verdict** |
| `9fe22fb` | `T-193` — the playlist panel sizes to its entries, capped at eight | `## In Review`, **no verdict** |

`4 files changed, 222 insertions(+), 2 deletions(-)` across `ui/playlist_picker.py`,
`ui/queue_view.py` and their two test modules. **Every one of the other 22 commits is under `ai/`** —
Phase 4 decomposition, `UX-009`, and records. No `docs/` file changed.

**My claim is that this does not widen the pass**, on the same argument the last submission made for
`T-192` and which you accepted: `T-193` and `T-194` are **Phase 4 polish, maintainer-found, in
`## In Review`, and not claimed as part of this exit.** They carry their own reviews.

**The counter-argument is real and I am not hiding it.** `P3EXIT-R2` existed *because* a Phase 4
task's test made a required exit gate red. Two more Phase 4 tasks now sit in the tree these gates
run against. **The gates below were re-run with them in**, which is the only way that claim is worth
anything.

## §3 · One thing changed outside the finding, and it strengthens criterion 2

**`T-189`'s workflow has now executed on a runner, and it passed.** The last submission's §3 recorded
this as the live external residual: *"`T-189`'s own gate has still never executed on a runner… the
first CI run at this head is the requirement's first genuine exercise, and it has not happened."*

**It has now happened.** CI run **`31295392039`** at `9fe22fb`, all five jobs green:
`linux`, `frozen linux`, `frozen windows`, `STARBASE coverage`, `windows desktop`.

`TRACKSANDTRAILS_REQUIRE_FFMPEG=1` did **not** turn the required merge cases into failures on
`windows desktop`. That is the point of the gate: ffmpeg was present on `STARBASE`, so **criterion
2's Windows evidence is a real pass rather than a skip inside a green job.** The residual is closed
by execution rather than by argument.

**The 36 unpushed commits the last submission reported are also gone.** Everything is on
`origin/main`; `git log @{u}..HEAD` is empty.

## §4 · What is not claimed

- **No verdict is claimed for criterion 6.** Criteria 1–5 you have already substantiated; nothing in
  this diff touches their evidence.
- **`T-192`, `T-193` and `T-194` have no verdicts** and are not part of this exit.
- **Windows runtime is verified only by CI** (`OPS-003`). Unchanged.
- **Real sites are unverified** — every fixture is recorded or derived, `ai/TESTING.md` §5.
- **`T-203` and `T-204` are Phase 4.** The maintainer briefly ruled `T-203` into Phase 3 on
  2026-08-09 and **reversed it the same day**; Phase 3 exits on its existing six criteria. Phase 4
  gained a GUI checklist criterion instead. Recorded because a scope change and its reversal on one
  day is exactly the kind of thing a later reader mis-reconstructs.

## Checks, with their actual results

**Run at `a5f65c9`**, Linux, `__pycache__` cleared and `PYTHONDONTWRITEBYTECODE=1`.

| Check | Result |
|---|---|
| `git diff --check` | clean (exit 0) |
| `ruff check` | All checks passed |
| `ruff format --check` | 223 files already formatted |
| `mypy` (src + tests) | Success: no issues found in 125 source files |
| `mypy --platform win32` | Success: no issues found in 125 source files |
| `pytest tests/unit/test_task_placement.py` | 14 passed |
| `QT_QPA_PLATFORM=offscreen pytest` | **NOT REPORTED — see below** |
| CI at `9fe22fb`, run `31295392039` | **all five jobs success** |

### The full suite is not reported here, and that is deliberate

**It was still running when the maintainer asked for this handoff**, and I am not writing a number I
do not have. **That is the entire content of `P3EXIT-R2`** — figures reported from a run that had not
finished proving them — so an absent result is stated as absent rather than filled from the last
known-good run.

**What stands in for it, and what does not.** CI run `31295392039` ran the suite to green on five
jobs at `9fe22fb`, which is **two commits before** this candidate. Everything between `9fe22fb` and
`a5f65c9` is under `ai/` — **no `src/` or `tests/` file differs across that range** — so the CI
result is strong evidence and is *not* a local re-run at the candidate head. **Treat this row as
open.** If you want it closed before ruling, say so and I will supply it.

**On the head these figures describe.** They were measured at `a5f65c9`, and this document is
committed after it. **No file under `src/` or `tests/` differs between `a5f65c9` and the candidate
head** — the only change is this file. That is the same construction `ai/evidence/`'s criterion-8
third run used to report a range, and it is stated rather than left for you to verify.

**This is the claim `P3EXIT-R2` caught me making falsely**, when I wrote figures from a run that
predated my last commit. Every number above was taken after the last code-bearing commit on this
branch, from a cleared bytecode cache, with `T-193` and `T-194` in the tree.
