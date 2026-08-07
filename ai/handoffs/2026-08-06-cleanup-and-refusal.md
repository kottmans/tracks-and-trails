# Review handoff — the cleanup, and a refusal nobody saw, 2026-08-06

**From:** Claude Code (Implementer)
**To:** Codex (Reviewer)
**Follows:** *2026-08-06 — Focused re-review of `T169-R5`/`T169-R6`* (`ai/REVIEWS.md`), **Approved**
**Review base:** `e70d615` — that review's approved head
**Review head:** `b92ec62`. **Five commits, pushed.** Working tree clean.
**Branch:** `main`. Serial mode, no wave.

**Two tasks, both small, and each one turned up something that was not.** `T-175` found a
persistence rule enforced nowhere; `T-158` found the same defect in my own first tests that it was
filed to fix in the product. Those two findings are what this range is actually about — the
deletions are the easy part.

| Commit | |
|---|---|
| `6d22746` | your re-review record, committed unmodified |
| `dc7d301` | your non-actionable note: what leaving `secure_delete` set actually costs |
| `7857b92` | the Phase 3 chart, redrawn |
| `60f4f28` | **`T-175`** — the machinery the withdrawal left with no caller |
| `b92ec62` | **`T-158`** — a refused *Open*, said where the user is looking |

**22 files, +550 / −620.**

---

## First, your non-actionable note, taken

You were right that *"the cost of leaving it on is bounded to nothing"* overstated it. A pragma is
connection state and outlives its transaction, so every delete on that connection for the rest of
the session overwrites its freed pages — real work on a queue whose rows a user may be removing.
What bounds it is that `migrate` runs a script only for a version above the database's own: one
connection, one session. The comment now says that and calls it a bounded cost accepted knowingly.

**Worth naming as a pattern, since you caught the last three.** That migration's prose asserted a
limit I had reasoned about rather than measured, three times — *not a secure erase*, *delete the
database file*, *bounded to nothing*. All three were wrong or incomplete. I have tried to keep this
range's claims measured rather than argued; the two headline findings below are both cases where
measuring contradicted what the code's own comments said.

## `T-175` — the cleanup, and the rule it found unenforced

Four items from your `T170-R4`. Three were dead. **The fourth was the one your finding flagged as
load-bearing, and checking it was worth more than the cleanup.**

| Item | Disposition |
|---|---|
| `history_group_verbs` | **Deleted**, with its two tests and its `__all__` entry |
| `store._now` | **Deleted**, with `store.py`'s `datetime` import, which existed for nothing else |
| `Succeeded.format_used` | **Removed** across the worker boundary |
| the completion seam | **Collapsed**, but only after writing the test that was missing |

### The hole

`T-175` allowed the seam to collapse **only** if `T050-R2`'s persistence-first ordering stayed
covered by a test that fails when the ordering inverts. I checked that before touching anything.

**It did not.** Emitting `job_succeeded` *before* the completion write settled left the entire suite
green. `test_a_real_download_completes_and_every_transition_is_persisted_first` asserts that
ordering for every `job_changed` and that assertion is real — but the success signal is a separate
emission on a separate path, and its own assertion only compared the payload. **So the rule stated
in three docstrings, and the entire reason the seam existed, was enforced nowhere for the signal a
user's "it finished" actually rides on.** A crash in that gap is the UI saying a download completed
while the queue, on restart, says it never did.

`test_a_success_is_announced_only_after_the_row_says_completed` closes it. Driven by a scripted
child rather than a real download, so the coverage does not depend on binding a loopback server —
which you hit in your own sandbox last round. Mutation-proven both ways.

**The gap existed independently of this task and would have outlived it.** Collapsing the seam is
merely what made someone look, and I would rather you treat the new test as the deliverable here
than the deletions.

### The collapse itself

Pure duplication once checked: `_Worker.revise` and `_Worker.complete` had identical bodies, as did
the facade and store methods above them. Removed — `PersistentJobStore.complete`,
`QueueWriter.complete`, `_Worker.complete`, the `_complete` signal and its connection,
`JobStore.complete`, and ten test doubles' implementations. `_persist`'s `write` parameter **stays**:
`requeue_at_end` still needs it, and the prose that said the completion branch used it is corrected
rather than deleted.

### `Succeeded.format_used`, decided rather than assumed

Your finding asked for a decision, so: **removed**, with its validation, `_str_or_none` which had no
other caller, and seven tests. Kept, its only honest consumer would have been a per-job log — and
`T-084` already captures yt-dlp's own output, so a second channel for the same fact is a feature
wearing a cleanup's clothes. Nothing serialised it: protocol messages cross a multiprocessing queue
as pickled objects and `ARC-003` ships both ends together, so no fixture constrained the removal.
**The distinction it protected is kept in `Succeeded`'s docstring** — an intention and an outcome
are different facts, and one must not wear the other's name.

## `T-158` — a refused *Open*, and a test of mine that proved nothing

The task's diagnosis held up exactly: **nothing was broken.** `_refuse_unless_usable` →
`FileActions._act` → `_report_transiently` worked end to end with a test over the whole path. The
sentence arrived several hundred pixels below the row the maintainer had just clicked, in a status
bar already carrying a permanent ffmpeg line. **The defect was distance, not silence.**

So it is a second and third delivery rather than a louder one, and `Refusal.reason` is reused
unchanged — a second wording would be a second thing to keep true:

- **At the row**, anchored to the acted-on row's rectangle. Not the cursor: `QToolTip.showText`
  follows the pointer by default, which is wrong for the keyboard and overflow-menu routes since
  they arrive with no meaningful mouse position. All three come through `_act`, so the anchor is
  read from the view's current index.
- **In the status bar**, unchanged. It is the record for a user who looked away, and a tooltip that
  has faded leaves nothing behind. Your predecessor's reasoning against a modal for an ordinary case
  is untouched.
- **Announced**, through `QAccessibleAnnouncementEvent`. `NFR-005` is a criterion here and a tooltip
  is placed, not spoken. A fix whose whole point is *where* a message appears is precisely the one
  that leaves a user who cannot see it with nothing, and "too far away for the sighted user" is not
  an argument that the status bar suffices for anyone else.

### The part I would review hardest

**My first tests were the shape this project keeps catching.** They asserted the tooltip's *text*,
and that two different rows each said something. A mutant anchoring every message at the cursor
**passed them** — a test that looks like it checks placement and checks nothing of the sort, which
is `ai/TESTING.md` §13's family exactly, authored by me while writing the fix for a defect about
placement.

`FileActions` now takes a `show_tip` seam, in the idiom of the `run`, `start` and `platform` seams
already in that constructor, so a test records **where** a refusal went and not only what it said.
`row_anchor()` is public for the same reason.

Five mutants, all killed: no row report; the status-bar report dropped in its favour; anchored at
the cursor; the announcement dropped; the announcement carrying its own wording instead of
`Refusal.reason`.

## Verification, on `b92ec62`

| Check | Result |
|---|---|
| `pytest tests/` | **2169 passed**, 11 skipped, 2 deselected |
| `ruff format --check .` | 183 files already formatted |
| `ruff check .` | All checks passed |
| `mypy` / `mypy --platform win32` | Success, 107 source files each |
| Mutation | Four on the completion ordering and the seam; five on `T-158`. All killed |

**Suite arithmetic, since the number moved twice.** 2174 → 2166 under `T-175`: nine tests deleted
with the code they covered, one added for the ordering gap. 2166 → 2169 under `T-158`: three added.

**CI is green: all five jobs at `b92ec62`**, run `31133125505`. **`windows desktop` passed**, which
is the one worth naming: `T-158` calls a Qt accessibility API and that job is the only thing that
sees the published UI Automation tree — it is what caught the `Settings` menu two rounds ago.
`frozen windows` and `frozen linux` passed too, which covers `T-175`'s protocol change reaching a
bundled build.

## What I did not do

- **`T-143` is not in this range**, and was asked for. It is not small: one extraction per playlist
  entry with bounded concurrency, per-entry failure isolation, and probe cancellation when a row is
  removed. More to the point its own final criterion decides **what an entry's status is while its
  probe runs**, and `ARC-004` has no `READY → PROBING` edge — so it amends an accepted state
  machine. That is a ruling, and `T169-R1` is three instances of what happens when an implementer
  supplies one. Left Proposed, with the maintainer told why.
- **No new decision entry.** Nothing here needed one; the `show_tip` seam is a testing seam in an
  established idiom, not a design choice.

## Suggested reading order

1. **`test_a_success_is_announced_only_after_the_row_says_completed`** and the seam collapse it
   permitted — whether the new test really covers what the old one did not.
2. **`FileActions._say_at_the_row` and `row_anchor`**, against the tests: the first version of those
   tests passed a cursor-anchored mutant, and I would like the second version checked by someone
   who did not write it.
3. **`Succeeded`'s docstring**, for whether removing a validated protocol field kept the reasoning
   worth keeping.
