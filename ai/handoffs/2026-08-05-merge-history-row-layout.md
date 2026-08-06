# Merge review handoff — History × row layout, 2026-08-05

**From:** Claude Code (Implementer)
**To:** Codex (Reviewer)
**Merge commit:** `e48fae5`, **pushed** to `origin/main`
**Merge base:** `38504b3` — *"Phase 2 exits"*, where both streams began
**Parents:** `cba9f3e` (History, approved at `cc94371`) and `d605b73` (row layout, approved)
**Tasks already approved, not re-opened:** `T-145`, `T-142`, `T-144`, `T-159`; `T-160`, `T-163`,
`T-164`, `T-166`, `T-167`

**What this asks of you is narrow.** Both sides are approved on their own; nothing in either is
resubmitted. What has never been reviewed is **the combination** — the conflict resolution, and the
one place the two features touch.

---

## 1. Why a merge and not a rebase

Rebasing my nine commits onto the row-layout stream would have given a linear history and
**invalidated every SHA both review records cite** — including *"Approved at `cc94371`"*, which
would name a commit that no longer exists. `AGENTS.md` makes commits and exact base/head SHAs the
review boundary, so replaying either side destroys the boundary that made the reviews checkable.

The cost is one merge commit. **Both parents are reachable and every reviewed SHA still resolves**,
which you can confirm with `git cat-file -e` on any of them.

---

## 2. The conflicts, and how each was resolved

Only two files conflicted. **No source file was touched by both streams** — the row layout changed
`row_delegate.py` and `test_row_delegate.py`; History changed twenty-six other files and neither of
those.

| File | Conflict | Resolution |
|---|---|---|
| `ai/REVIEWS.md` | Both appended review records; git tangled them on the shared `### Independent verification` headers | Verified **both sides are pure appends** to the base text, then rebuilt as `base + row-layout records + History records`. All four records present and whole |
| `ai/TASKS.md` | Both moved entries into `## Complete` from other sections | Rebuilt **per entry** rather than by hand |

**The `TASKS.md` resolution is the part to check, and it is mechanically verifiable rather than a
judgement.** Parsed base, ours and theirs into 165 entries each, then asserted:

- The two streams changed **disjoint** task sets — mine `T-145 T-142 T-144 T-156 T-159`, theirs
  `T-160 T-163 T-164 T-166 T-167`. No entry was changed by both.
- **Non-entry prose is byte-identical to base on both sides**, so rebuilding from entries loses
  nothing.
- In the merged file, every entry equals the side that changed it, and every entry changed by
  neither equals base. Asserted for all 165, not sampled.

`test_task_placement.py` passes, so every entry still sits under the section its status names.

---

## 3. The one place the two features actually meet

This is the substantive risk and it is not visible in either diff.

`T-163`/`T-167` reserve part of a row's last line for the **progress bar**, and size that reserve
from the row's segments. A History group **has no segments** — `UX-005`'s 2026-08-05 amendment
refuses the segmented bar, because every member of a history group succeeded and sixteen identical
blocks is furniture. So the two features meet in `_bar_reserve`, and **neither suite covered that
pair**: the row-layout tests use queue rows, the History tests predate the new sizing.

**It is sound, and the new code handles it explicitly** — with no segments and no fraction,
`_bar_reserve` returns `0` rather than falling through to a minimum, so the whole line goes to the
verbs and the format.

**Now asserted rather than probed once.** `test_a_history_group_keeps_its_verbs_on_a_narrow_row`
paints a real group header at **631 px** — `T-167`'s own width, where a queue row decided on sixteen
blocks and drew them 15 px wide — and at 400 px, and requires that nothing was dropped into the `⋯`.
Mutating the History group to answer `SEGMENTS_ROLE` like the queue's kills it.

That test is the only source change in this merge commit. **If you would rather a cross-feature
assertion lived in `test_row_delegate.py` instead**, say so — I put it with History because History
is the side that declines the bar.

---

## 4. What I did not do

- **No source was reconciled**, because none needed it. If you think the two streams *should* have
  interacted somewhere they did not — a History row's format control under `7ebf798`'s narrowing, say
  — that is worth naming, and I would rather hear it than assume the empty diff proves it.
- **No `STATUS.md` update.** Phase 3 progress across both streams is a coordination write I have not
  been asked for and did not invent.
- **No Windows runtime run.** Both static gates pass on both platforms; the merge changes no
  platform-guarded module.

---

## Verification

| Check | Result |
|---|---|
| `tests/unit tests/ui tests/integration` | **2262 passed, 11 skipped** on the merge commit |
| `ruff check .` / `ruff format --check .` | All checks passed / 175 files formatted |
| `mypy` / `mypy --platform win32` | Success, 109 source files, both |
| `test_task_placement.py` | **14 passed** — every entry under the section its status names |
| Entry-level merge audit | 165/165 entries match their intended source; prose identical to base |
| CI | Run `31065421037` on `e48fae5`, triggered by the push — **check it before treating this as green** |

**Pushed**, on the maintainer's instruction: `d605b73..e48fae5`. `tests/network` not run, unchanged
from both prior submissions and for the same reason.
