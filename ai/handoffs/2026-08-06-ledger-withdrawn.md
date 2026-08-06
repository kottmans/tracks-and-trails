# Review handoff — the completion ledger, withdrawn, 2026-08-06

**From:** Claude Code (Implementer, and Planner for the requirement and decision changes)
**To:** Codex (Reviewer)
**Corrects:** the review at `ai/REVIEWS.md`, *2026-08-06 — Completion-ledger and Phase 3 batch review*
**Review base:** `3578fcc` — that review's submission head
**Review head:** `de7cb19`. **Five commits, pushed.** Working tree clean.
**Branch:** `main`. Serial mode, no wave.

**This is not a correction batch.** Four of your five blocking findings are answered by the feature
no longer existing, and the fifth by a ruling that it should not. **What needs reviewing is the
withdrawal**, which is a product decision plus a 2,154-line deletion across the persistence layer —
not a set of repairs to the thing you reviewed.

| Commit | |
|---|---|
| `be76fe9` | the Windows menu-bar equality, taught to see `Settings` |
| `abcfb22` | Phase 3 board redrawn |
| `6c90cf7` | **the withdrawal** — the one to read |
| `fd389f3` | `T171-R1`: the provenance evidence relabelled as a surrogate |
| `de7cb19` | Phase 3 board redrawn again, without the ledger |

**27 files, +483 / −2154.** Three deleted: `core/urls.py`, `ui/settings_dialog.py`, and that
screen's tests.

---

## How the ruling was reached, in order, because the order matters

1. I put two of your findings to the maintainer as questions, because `T169-R1` had just established
   that I could not rule on them myself: **the identity** (digest versus plaintext) and **legacy
   duplicates** (collapse versus preserve). They ruled *digest* and *collapse to the latest,
   chronologically*.
2. **I implemented both, plus `T170-R1` and `T170-R2`**, and reproduced all four of your probes as
   fixed — including the offset-crossing one, where `01:10-06:00` correctly beat `01:50-05:00`.
3. The maintainer then said the whole approach was overcomplicated for a lightweight downloader, and
   asked what I thought. **I agreed**, and said so with the evidence: five findings across two
   rounds, two High, and not one about the warning being wrong — every one about keeping the data.
4. They ruled: **no record at all**. Duplicate detection scoped to the live queue. No file-exists
   warning either — *"most downloaders just download it again with a (n) appended"*.
5. They then added that a queue duplicate should be **allowed and confirmed, not refused**.

**So the two rulings in step 1 were superseded by step 4 before they shipped**, and the work from
step 2 — 282 lines across six files, plus a migration `0009` and a v9 fixture — was **discarded, not
committed**. It is in no commit in this range. I mention it because it is the reason nothing here
looks like the corrections your findings asked for.

## Your findings, and how each stands

| Finding | Disposition |
|---|---|
| `T169-R1` **High** | **Resolved by withdrawal.** `DAT-006` is **Withdrawn**, not ratified. You were right on the authority point and right that it was the third time — `T145-R1`, `T144-R1`, and this. |
| `T169-R2` **High** | **Resolved by withdrawal.** No URL is stored, plaintext or otherwise. Nothing is written to the ledger at all. |
| `T170-R1` **Medium** | **Moot.** No data step, so nothing can be interrupted between a backfill and a version bump. The lesson is preserved in `DAT-006`'s withdrawal note for whoever writes the next transforming migration. |
| `T170-R2` **Medium** | **Moot.** `core/urls.py` is deleted; nothing normalises a URL. |
| `T170-R3` **Medium** | **Moot.** No identities, no rows, no `MAX` over offset-bearing text. |
| `T171-R1` **Medium, non-blocking** | **Corrected** in `fd389f3`, as you asked rather than by removal. |

**`T171-R1` is the only one I actually fixed.** The evidence now says in its purpose line, before
its table, and in the task summary that these are **direct ffmpeg commands standing in for the
application's postprocessor paths** — no `FFmpegExtractAudio`, no `FFmpegEmbedSubtitle`, and a
"merge" that is one muxed file copied to another container. The container findings in §3 hold; the
per-family claim is withdrawn, and `T-171`'s first criterion is explicitly **not** met.

---

## What the withdrawal changed, and the four judgements inside it

### The contract

- **`REQ-020` is withdrawn.** No record of what has been downloaded — not a list, not a private
  ledger behind one.
- **`REQ-021`** unchanged from the last round: a file is reachable while its queue row exists.
- **`REQ-022` is scoped to the live queue**, and says a duplicate is **allowed and confirmed, not
  refused** — the maintainer's step-5 addition, written so it cannot be read as a block.
- **`REQ-012`** stopped claiming a history survives restart.
- **`DAT-006` is Withdrawn**; `DAT-005` and `UX-005`'s same-day amendments are reconciled to
  describe a Settings action that no longer exists.

### Four judgements I made, none of them ruled on explicitly

**1. The Settings menu was removed, not left empty.** It existed to hold `Clear download records`.
An empty settings screen is a control that does nothing, which is `UX-005` §5's own objection, so
the menu, the dialog and its tests are gone and `T-146` rebuilds it. **This is the judgement I would
most like checked** — it undoes something your review accepted, on a premise that changed under it.

**2. `store.complete` lost its `format_used` parameter**, which rippled to the `JobStore` protocol,
the manager's one call site, and five test doubles. It existed only to fill a column of the record.

**3. The writer's two-row transaction became one statement.** `T050-R1`'s reasoning — a hard exit
between two commits left a durably completed job with no record — is preserved in prose at
`writer.complete`, because the requirement it protected has nothing left to be atomic with.

**4. Migration `0008`'s `normalised_url` column stays, unused and never written.** `DAT-006` §5's
argument outlives the entry: a column drop is a table rewrite on a table holding a user's own rows.
The column is dead weight and `T-174` does not touch it either.

### Tests

**Deleted:** the ledger suites, `test_settings_dialog.py`, and the `T-085` completion-projection
tests whose subject was the record.

**Kept, reframed:** the hard-exit durability probe, now asserting the **job row** survives a process
that stops existing. Job-row crash safety is otherwise covered by `tests/integration/test_crash_kill.py`
and 23 references to `recover_interrupted`, which is why I did not keep more of that section.

**`be76fe9` and `6c90cf7` cancel out on one test.** The first taught the Windows menu-bar equality
to expect `Settings`; the second removed the menu and put it back to `File`/`Help`. Both are in this
range, and the docstring now records the six hours in between — because that equality is what caught
the menu on the Windows job after the Linux suite had passed and three commits had been pushed.

### Tasks

`T-114` is rescoped to an in-queue confirmation storing nothing. **`T-172` is cancelled as moot** —
it proposed deleting dead ledger code, and the live ledger went first, which is its own small joke.

---

## Verification, on the exact head `de7cb19`

| Check | Result |
|---|---|
| `pytest tests/` | **2163 passed, 11 skipped, 2 deselected**, 286 s |
| `ruff format --check .` | 181 files already formatted |
| `ruff check .` | All checks passed |
| `mypy` | Success, 107 source files |
| `mypy --platform win32` | Success, 107 source files |
| Composed window | central widget `QueueView`, **0 tab widgets**, menus `File`/`Help`, no `open_settings` |
| Fresh database | schema v8, **`history` table present and empty** — it exists and nothing writes to it |

**CI is green on the withdrawal.** Run `31109522346`, at `6c90cf7`: all five jobs, **including
`windows desktop`** — the job that matters most here, since it is the only thing that sees the menu
bar this range changes twice, and the one that caught the `Settings` menu in the first place. The
three commits after it are documentation, so they ran `Prose` alone (`OPS-011`).

*(This section said the run was still in flight; it landed shortly after the handoff was written and
is corrected here rather than left for a reviewer to re-check.)*

`mypy` run as `python -m mypy`; the stale `.venv/bin/mypy` shebang is unchanged machine state.

## What I did not do

- **No new tests for `REQ-022`.** It is rescoped, not built — `T-114` remains Proposed, and building
  it inside a removal would have hidden the removal.
- **No schema change.** `0008` stands as the last migration.
- **`T-173`** (the duplicated `_now()`) and **`T-174`** (the history-to-ledger naming) are still
  filed and untouched. `T-174` is smaller than it was: most of what it would have renamed is gone.

## Suggested reading order

1. **`REQ-020`, `REQ-022`, and `DAT-006`'s withdrawal note** — the decision, and whether the record
   of it is honest about how it was reached.
2. **`6c90cf7`'s deletions in `persistence/`** — particularly `writer.complete` and
   `store.complete`, where a two-statement transaction became one.
3. **The Settings removal**, against the part of your review that accepted it.
4. **`fd389f3`** — the only place a finding was repaired rather than dissolved.
