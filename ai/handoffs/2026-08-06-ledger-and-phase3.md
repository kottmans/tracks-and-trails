# Review handoff — `T-150`, `T-156`, `T-169`, `T-170`, and `T-171`'s evidence, 2026-08-06

**From:** Claude Code (Implementer, and Planner for `T-169`)
**To:** Codex (Reviewer)
**Review base:** `7afa295` — "Hand T-168 to review", the last commit before this session
**Review head:** `7f87534`. **Ten commits, pushed.** Working tree clean.
**Branch:** `main`. Serial mode, no wave.

**Whether anything between the row-layout approval and `7afa295` is still outstanding is not mine
to say** — `T-105` and `T-168` were handed over separately and I did not touch them. This range is
the work done after that point.

| Commit | Task | |
|---|---|---|
| `cc5194f` | `T-150` | the add dialog opens at the width its rows need |
| `126c37a` | `T-156` | the MP3 preset says which bitrate it means |
| `cc7ce8a` | — | **the maintainer's planning commit**, not mine — see *One commit is not mine* |
| `4076108` | `T-169` | the product contract, reconciled to a private ledger |
| `2ebb24e` | `T-170` | the ledger: migration, key, queries |
| `ba7239f` | `T-170` | the History surface, removed |
| `a6f7fa7` | `T-171` | evidence only, **no criterion claimed** |
| `094451a` | `T-170` | a placeholder I left in my own surgery |
| `9b47be0` | `T-170` | a criterion I marked Complete without meeting |
| `7f87534` | `T-173` | a code fence that failed the canonical format gate |

**Scale:** 36 files, +2817 / −3960. Two files deleted (`ui/history_view.py`, its test), seven
added. **The deletions are the point of the range**, not a side effect.

---

## Read this first: three things I got wrong

**Front-loaded deliberately.** Two of them I found myself, after committing; the third is a repeat
of a finding you already raised.

### 1. `9b47be0` fixes a criterion I marked Complete without meeting

`T-170`'s *"New completions persist only the fields `T-169` kept"*. I removed the History **view**
and the **refresh**, and left the projection writing all twelve fields — title, path, format, size,
thumbnail address, playlist membership, format choice — on every completion, for a row nobody
draws. `ba7239f` claimed the task complete with that outstanding.

I found it two hours later while sweeping for dead code, which is later than a criterion list
should need. **The narrowing is the largest single change in the range** and is worth reviewing as
though it were its own task: `HistoryEntry` goes from twelve fields to three, and the tests that
asserted the other nine had to be rewritten or deleted rather than adjusted.

### 2. `7f87534` — the canonical format gate, again

`ROWLAYOUT-R1` was exactly this: I ran `ruff format --check src tests`, reported it, and a
**document** failed the repository-wide command. Same shape here — the code fence in `T-173`'s
entry, written after the source gates were green. Every result below is from the exact head with a
clean tree, using the canonical scopes.

### 3. `094451a` — `if True:` left by my own scripted surgery

I removed the History tab with a series of Python scripts. One replaced a `for view in (queue,
history)` loop with `if True:` around the surviving body. It ran correctly and read as though a
condition had been forgotten.

---

## One commit is not mine

`cc7ce8a`, *"Record the lean completion-ledger plan"*, is the maintainer's: it files `T-169`,
`T-170` and `T-171` and rewrites `T-114`, `T-146` and `T-158` to depend on them. It also carries my
`T-156` task entry, which was sitting uncommitted in the working tree when they committed.

**It arrived while I was mid-task**, and the collision is worth recording because it nearly cost
something. I found `ai/TASKS.md` modified underneath me, checked whether my earlier commit had
swept up their work (it had not), and then — wrongly — `git stash`ed the file to get a clean tree.
That pulled a live file out from under whoever was editing it. I restored it within seconds and
verified it byte-identical, but I should not have done it at all.

---

## `T-169` — the contract, and why it is the one to read closely

**This is a Planner change to five accepted entries**, made on the maintainer's direction of
2026-08-06 and on their instruction to do these tasks. It is the highest-consequence commit here.

- **`REQ-020`** is now a private completion ledger: no browseable list, no per-record removal, no
  automatic expiry, one Settings action.
- **`REQ-021`** reaches a file only while its queue row exists, and stops implying the application
  follows files users move.
- **`DAT-001`, `DAT-005`, `UX-005`** carry **appended amendments**, never rewrites — `AGENTS.md` §6
  makes those historical record.
- **`DAT-006` is new** and is what `T-169`'s fourth criterion required: the ledger's identity, its
  three fields, one row per identity, and the migration ruling.

**The judgement I would most like checked** is `DAT-006` §5: obsolete columns **stop being written
rather than being dropped**. SQLite implements a column drop as a table rebuild, on a table holding
a user's own record of their own downloads, at the end of a task whose purpose is to *remove* a
feature. I took the risk asymmetry as decisive. The cost is a table with nine permanently-NULL
columns.

**`DAT-006` §2 is the other one.** Normalisation is scheme and host lower-cased, fragment dropped,
**nothing else** — no query-parameter stripping, because the identity of a video lives in the query
on the largest site this serves. The trade is stated in `core/urls.py`: a missed duplicate costs a
warning that does not appear; a false one warns about the wrong file, and only the second lies.

**Phase 2's deliverables stay Approved** and are annotated as narrowed or removed. A plan that
rewrote them would claim the project never built what it is now removing.

## `T-170` — landed in two commits on purpose

The halves decompose and only one is additive, so `2ebb24e` landed the ledger with the view still
working and `ba7239f` removed the surface. A half-finished single commit here would have been a
window that does not start.

**Three implementation findings:**

1. **One row per identity is a delete, not a `UNIQUE` index.** The constraint would need a
   migration that first deletes rows a user already has — two completions of one URL from before
   the ledger existed. Collapsing lazily reaches the same state without deleting anybody's records
   to install a constraint.
2. **Two test factories gave every record the same URL.** Under the collapse, a test seeding three
   rows asserted against one. Both now vary the URL with the id.
3. **`test_file_actions.py` was hosted on the History view** — convenient rather than meaningful,
   and `T-086`'s containment tests nearly went with the view. They now run against a two-field row
   they own. Its one History-model test moved to the queue, where the question is still askable.

**What moved rather than died:** `T-144`'s four clear-history properties (visible route, count in
the question, files-are-safe promise, nothing asked when empty) are now
`tests/ui/test_settings_dialog.py`, against *Clear download records*. The format-naming tests are
`tests/ui/test_format_text.py`, beside the rule rather than inside the surface built last.

## `T-156` — two findings changed the shape

1. **The bitrate could not go in the catalogue name.** `with_audio_quality` derives a preset at
   another bitrate with `replace(...)` and **copies the name across**, so a name built from
   `MP3_QUALITY` would have called a 320 kbps download 192 — beside the dialog's own control
   reading 320. The suffix is read from the choice instead.
2. **Naming and identifying had to be separated.** `preset_name_for` feeds `PRESET_ROLE`, which is
   what the row's dropdown shows as selected, and the retarget no-op guard. Relaxing it to match
   MP3 at any bitrate would make a 320 kbps row's control claim the 192 kbps preset — `T126-R4`.
   It stays strict; `_converting_preset_for` describes and only the row uses it. **This fixed a gap
   on the way**: a non-default bitrate previously had no name at all and read `bestaudio/best`.

**Left open deliberately**, on that task's own recommendation: the dropdowns still offer
`preset.name`, so a row reading *Audio only (MP3), 192 kbps* sits beside a control reading
*Audio only (MP3)*. Naming the catalogue entry instead would trade the gap for a contradiction.
`T-111` owns it.

## `T-150` — the number is derived from two things, not one

`minimum_row_width` takes the larger of the anatomy's needs and the selector's. The second is
measured through Qt's own wrapping rather than divided out of the string's width: the 1080p
selector's bare token is 489 px on its own, and that sets the answer. **A hint, not a minimum** —
670 px now, still narrowable to 320, because a floor would fence off the very behaviour `T-135` and
`T-160` built.

## `T-171` — evidence only, and **no criterion is claimed**

Every remaining criterion is a product judgement about writing private download context into a
user's files: opt-in versus opt-out, global versus per-download, the privacy allowlist, what a
container that cannot carry a field should do, and whether the feature is adopted at all.
`AGENTS.md` §5 keeps those with the maintainer.

What the measurement found, from synthetic media — **no network, no download**:

- **Nothing writes provenance today.** No preset configures `FFmpegMetadata`.
- **Standard tags survive every path**, including the MP3 transcode.
- **A custom key is dropped silently by MP4 and M4A**, while surviving MKV and MP3. Two of five
  presets produce exactly those containers, and there is no error at the default log level.

---

## Verification, on the exact head `7f87534`

| Check | Result |
|---|---|
| `ruff format --check .` | **183 files already formatted** — the canonical scope |
| `ruff check .` | All checks passed |
| `pytest tests/` | **2213 passed, 11 skipped, 2 deselected**, 287 s |
| `mypy` | Success, 110 source files |
| `mypy --platform win32` | Success, 110 source files |
| Migration, fresh database | version 8, 0 rows |
| Migration, frozen `v7.sql` | version 8, 3 rows, every key backfilled from its URL |
| Real window, composed | central widget `QueueView`, **0 tab widgets**, Settings menu enabled, dialog opens, clear button disabled on an empty ledger |

**The full suite was rerun after the last source change** and `7f87534` is documents only.

`mypy` run as `python -m mypy` for the usual reason — the stale `.venv/bin/mypy` shebang, unchanged
machine state.

**Mutation evidence:** four on the ledger (query-stripping normalisation, a fallback key, no
identity collapse, collapsing NULL keys) — all killed. Four on `T-156` (no bitrate, bitrate from
the constant, bitrate for any codec, the display rule leaking into identity) — three killed, one
equivalent and disclosed below. Three on `T-150` (a stale literal width, no selector term, a plain
`QListView`) — all killed.

**One equivalent mutant, disclosed:** `_bitrate`'s `AudioCodec.MP3` guard is unreachable — no
non-MP3 choice can acquire a name while carrying a bitrate, so only the `audio_quality` check can
fire. Kept as documentation of the rule, on the `not movable` precedent from the `T140-R3` handoff.

## Not in this range

- **`T-172`, `T-173`, `T-174`** are filed, not done: the dead removal API, the duplicated `_now()`,
  and the history-to-ledger rename. They came out of a simplification sweep the maintainer asked
  for and are deliberately left as reviewable tasks rather than more unattended deletion.
- **`ai/REVIEWS.md`** is untouched by me in this range.
- **The `history` table, its columns and its indexes.** `DAT-006` §5, and `T-174` restates it.

## Suggested reading order

1. **`DAT-006`**, then `REQ-020`/`REQ-021`. Everything else implements them.
2. **`9b47be0`** — the narrowing, and the criterion it closes late.
3. **`core/urls.py` and migration `0008`** — the identity rule and the one backfill.
4. **`ba7239f`'s deletions**, against the "what moved rather than died" list above.
