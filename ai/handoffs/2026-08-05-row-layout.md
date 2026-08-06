# Review handoff — `T-167`, `T-164`, `T-163`, `T-166`, `T-160`, 2026-08-05

**From:** Claude Code (Implementer)
**To:** Codex (Reviewer)
**Review base:** `38504b3` — "Phase 2 exits"
**Review head:** `fd15ade`. **Six commits, three files. Not pushed** — the maintainer asked for
commits without a push, so the range is local to this checkout.
**Branch:** `main`. Serial mode, no wave.

| Commit | Task |
|---|---|
| `dc43b04` | `T-167` — decide the bar's shape from the row |
| `4a3f8b3` | `T-164` — merge a narrow bar to eight blocks |
| `b9fc1d7` | `T-163` — reserve the bar's share of the last line |
| `c2816e9` | `T-166` — stop the verbs narrowing the line above them |
| `7ebf798` | `T-160` — narrow the control instead of clamping it |
| `fd15ade` | whitespace restore, see *Two things I got wrong* below |

Files: `src/tracks_and_trails/ui/row_delegate.py`, `tests/ui/test_row_delegate.py`,
`ai/TASKS.md`. `ai/REVIEWS.md`, `ai/STATUS.md`, `ai/DECISIONS.md` and `UX-005` are untouched.

---

## Read this first: five findings, one defect

The maintainer submitted these as one piece of work on the reasoning that they are five pairs
colliding on one line, and that fixing them separately is how `T-155` and `T-160` both happened.
That reading is correct, and it is worth stating precisely because it is what the commits are
organised around:

> **The row's last line was being divided by leftovers instead of by a rule.**

The verbs were laid out against whatever space remained and everything else took what was left.
Each finding is one consequence:

| Finding | Which pair, and what it lost |
|---|---|
| `T-167` | the bar's *rendering* read the leftover, which is not monotonic in the window |
| `T-164` | nothing said what a bar too narrow for one-block-per-entry should draw |
| `T-163` | the bar's *width* was the leftover, so the verbs took theirs first |
| `T-166` | the format line's width was also clipped to the verbs — see below, its premise was wrong |
| `T-160` | the control clamped onto the tile because nothing bounded it on the left |

The order was `T-167` first, because a layout that oscillates cannot be asserted at all.

---

## `T-166`'s premise was wrong, and the fix is smaller than the task asked for

**This is the one thing in the range I would most like checked independently.**

`T-166` was filed as the verbs and the format line sharing a line, with acceptance criteria asking
that the verbs "drop into `⋯` before overlapping it" and that "the format line keeps at least a
stated minimum before any verb is drawn beside it — named in source, per `T118-R8`'s rule that the
*number* is the decision".

**They do not share a line.** In `_paint_text`, the selector is drawn at `area.top() + 2 * line`
with a height of `selector_lines * line`, and `selector_lines` is already reduced to 1 whenever any
verb was drawn. The verbs are laid out at `area.top() + (TEXT_LINES - 1) * line`, which is
`3 * line`. There is a whole line between them, and the height calculation is what put it there.

The defect was that the selector's **width** was *also* stopped at `verbs_left`:

```python
max((body.right() if verbs_left is None else verbs_left) - area.left(), 0)
```

So the same width was spent twice, and as the window narrowed the buttons advanced leftward across
a line they do not occupy. Measured on a group header before the fix, against
`Download as: Best video available`, which is 190 px at the default font:

| Window | Width the format line was given | What it draws |
|---|---|---|
| 500 px | 13 px | `…` |
| 560 px | 73 px | `Download` — 57 px, and the next word does not fit |

Which is the report, exactly: *"`Download as: Best video` becomes `Download`"*.

**So the criterion asking for a stated minimum has no number, because no verb is ever beside it.**
I did not invent one to satisfy the wording. The property the criterion was protecting is asserted
directly instead: `test_the_verbs_do_not_narrow_the_format_line_above_them` crops the format line's
band out of the painted row and requires the same row **with and without verbs** to draw it
identically at every swept width. That cannot pass by both being equally truncated — the row
without verbs is not narrowed by anything.

`T118-R8` is untouched and still governs: the selector is the half that cannot give. `T-163` is
where the verbs give way to the thing they *do* share a line with.

If you read the geometry differently, this is the finding to raise, and the fix would be larger
rather than different.

---

## What each change is, and where its number comes from

Every threshold in the range descends from one constant, which is stated rather than tuned:

```python
MIN_BLOCK_WIDTH: Final = 16  # above the 12 px the maintainer measured as "noise"
SEGMENT_GAP: Final = 1
MERGED_BLOCKS: Final = 8
MIN_FRACTION_BAR: Final = 4 * MIN_BLOCK_WIDTH  # a quarter is the coarsest reading of a bar
MIN_CONTROL_WIDTH: Final = 64
MIN_TEXT_WIDTH: Final = 120
```

`MIN_BLOCK_WIDTH`'s anchor is `T-164`'s own measurement — *"sixteen blocks in a 200 px bar are
twelve pixels each, and at that size the segmentation reads as noise"* — so the floor sits above
twelve rather than at it. That is the weakest derivation in the set and it is the one to push on if
any of them looks arbitrary; the others are arithmetic from it.

**`T-167`.** `_paint_segments` gains `line_width`, and the caller passes `_bar_line(...)` rather
than the bar's own rect. `_bar_line` is the text line less the overflow button — everything
subtracted is fixed for a given row, so it moves one way as the user drags.

**`T-164`.** `segment_blocks` folds to `MERGED_BLOCKS` below the threshold; `_merge` takes each
block's worst state, ordered `FAILED, CANCELLED, WAITING, RUNNING, DONE`. Below the two endings the
order is least-advanced first, so a block cannot claim more progress than the slowest entry under
it. The gap no longer varies at all, which is `UX-005` row 9b-i's constraint that a deliberate
merge must not look like `T-155` returning.

**`T-163`.** `_bar_reserve` takes the bar's minimum out of the line before `_lay_out` places any
button, so a verb drops for crowding the bar as well as for running off the row.

**`T-160`.** `_control_rect` takes a `tile` and never crosses it; `_body_of` and `_control_of` give
the paint, the click, the hover and the editor geometry one answer.

---

## Two decisions I made that the tasks left open

**1. `T-163`: the `⋯` outranks the bar's minimum.** On a line too narrow for the merged bar *and*
the overflow button, the button wins and the bar goes under its stated minimum. A row that kept its
bar and dropped the button would leave the pointer no route to its verbs at all. So the test
asserts the *rule*, not an absolute: a bar under `MIN_BLOCK_WIDTH` is only allowed on a row that has
already dropped every verb it has. Verified across the sweep — no width violates it.

**2. `T-160`: the control shrinks; it is never withheld.** The task explicitly left this open —
*"narrowing the control to what is left, or withholding it as the verbs are withheld. Whichever is
chosen is stated"*. I chose shrinking, because `EDIT_KEY` opens the editor **in this same
rectangle**, so withholding it would remove the only route to the format rather than relocating it,
which is the opposite of what `⋯` does for the verbs. Stated at `MIN_CONTROL_WIDTH`.

---

## Two things I got wrong, disclosed rather than tidied away

**1. Two mutants initially survived. Both were my tests being weak, not the code being right.**

- The `T-164` failure test passed against a fold that took each block's **first** state, because I
  had put the failed entry at index 4 — which is first in its merged block. Moved to index 5, and
  `test_a_merged_block_takes_the_worst_state_it_covers` now checks all sixteen positions directly.
  This is `T126-R3`'s shape again and I would rather you saw it than found it.
- The `T-160` tile clamp was not load-bearing anywhere in the swept range: subtracting
  `MIN_TEXT_WIDTH` happens to hold a 96 px tile clear down to about a 186 px row, which is narrower
  than any width swept. Without `test_the_control_stays_clear_of_the_tile_at_any_body_width`, which
  drives the body to 60 px, the clamp would have been untested code that two unrelated constants
  were standing in for.

**2. The first four commits are individually red on `test_task_placement`.** I ran `tests/ui` for
each and only the full suite at the end, which caught that I had marked entries **Complete** while
leaving them under `## Proposed — Phase 3`. `7ebf798` moves all five into `## Complete`, and the
head is green. The intermediate commits are not. Fixed forward rather than rewritten, because the
history is the review boundary; say if you would rather it were rebased.

`fd15ade` is the tail of that same mistake: the script that moved the entries ran a
newline-collapsing regex over the whole file and took a blank line off `T-119`, `T-123`, `T-152`
and `T-161`. Restored, so the range touches only the five tasks it claims to. **The `ai/TASKS.md`
diff is large (545+/521-) and is almost entirely the five entries being relocated** — the check
worth running is that no other entry's body differs, which is what `fd15ade` restores and what I
verified block-by-block against `38504b3`.

---

## What is asserted, and how

Twelve new tests, all in `tests/ui/test_row_delegate.py`. **Every layout claim is swept across
`SWEEP_WIDTHS = range(300, 1201)` one pixel at a time**, which is `T-155`'s lesson: its blocks
merged at most widths and not at 800, so a test rendering one width drew the defect correctly and
would have passed.

The low end was 380 until `T-160`; below that the control took the whole width beside the tile and
the row had no last line to measure.

| Test | Claim |
|---|---|
| `..._bar_changes_shape_at_most_once_across_a_drag` | `T-167`: one transition across the sweep |
| `..._narrow_bar_merges_to_a_fixed_count...` | `T-164`: exactly two renderings, merged at the narrow end |
| `..._merge_threshold_is_the_stated_block_minimum` | the boundary, one pixel either side |
| `..._failed_entry_stays_visible_at_every_width` | row 9b's guarantee, swept |
| `..._merged_block_takes_the_worst_state_it_covers` | all sixteen failure positions |
| `..._playlists_blocks_keep_their_width_and_the_verbs_give_way` | `T-163`, segmented |
| `..._downloads_bar_keeps_its_minimum_and_the_verbs_give_way` | `T-163`, fraction |
| `..._overflow_still_holds_exactly_what_the_row_dropped` | `T-135`, re-asserted |
| `..._verbs_do_not_narrow_the_format_line_above_them` | `T-166` |
| `..._format_control_never_covers_the_thumbnail` | `T-160`, three surfaces, geometry |
| `..._control_stays_clear_of_the_tile_at_any_body_width` | `T-160`, below any window |
| `..._thumbnail_is_drawn_the_same_with_a_control_and_without` | `T-160`, from the pixels |

**Anti-vacuity, since three of these exclude widths.** `T-167`'s and `T-164`'s sweeps skip widths
where the row draws no bar, because that is `T-163`'s defect and asserting it there would fail for
the wrong reason. Each carries a guard requiring the excluded widths to be a minority. After
`T-163` the exclusions are empty in practice; the guards remain so they cannot silently become the
whole sweep again.

### Mutation evidence

| Mutant | Result |
|---|---|
| `T-167`: decide the gap from `area.width()` again | **killed** — 5 reversals at 398, 464, 482, 507, 525 |
| `T-164`: fold takes each block's first state | **killed** (2 tests) |
| `T-164`: fold takes each block's commonest state | **killed** (2 tests) |
| `T-164`: never merge | **killed** (2 tests) |
| `T-163`: drop the reserve entirely | **killed** (2 tests) |
| `T-163`: reserve without its `VERB_GAP` | **killed** (2 tests) — this is a real off-by-one I hit |
| `T-163`: no minimum for a fraction bar | **killed** |
| `T-166`: restore the `verbs_left` clip | **killed** |
| `T-160`: restore the old `body.left()` clamp | **killed** (3 tests) |
| `T-160`: control ignores the tile | **killed** (2 parametrisations) |

---

## Verification

| Check | Result |
|---|---|
| `pytest tests/` | **2204 passed, 11 skipped, 2 deselected**, 293 s |
| `pytest tests/ui/test_row_delegate.py` | **52 passed** |
| `ruff check src tests` | All checks passed |
| `ruff format --check src tests` | 107 files already formatted |
| `mypy` (bare) | Success, 107 source files |
| `mypy --platform win32` | Success, 107 source files |

Both `mypy` forms were run because this range edits a test file (`ai/TESTING.md` §12). Run as
`python -m mypy`: the `.venv/bin/mypy` console script on this machine still carries the stale
shebang recorded in the `T140-R3` handoff — unchanged machine state, still unfiled.

**One machine note that affected a measurement.** Two `pytest` runs overlapped at one point on this
host and I killed both and re-ran rather than reading the result, per §9's warning that concurrent
suites here produce failures that look like defects. The numbers above are from a single run on an
otherwise idle `kirk`.

**`T118-R10`'s repaint budget still holds** — `_bar_reserve` is now called once per `_verb_rects`,
which runs on every hover move, and
`test_painting_a_viewport_of_a_large_queue_stays_inside_the_budget` passes unchanged. It is
arithmetic over a list the row already builds, but it is new per-paint work and worth a look.

---

## Not in this range

- **`UX-005` is unamended.** Row 9b-i is implemented as written; nothing here needed a decision
  change, and `T-166`'s wrong premise is a task-entry correction rather than a `UX-005` one.
- **`ai/STATUS.md` is untouched.** Its snapshot predates this work and this is Phase 3; I did not
  want a Phase 3 entry rewriting a file whose current sentence is about Phase 2's exit.
- **`T-150`** (the dialog's opening width) is still open and is not fixed by `T-160`, which is what
  that task entry already says.
- **Checklist row 2.7's property** is inherited by `T-160`'s acceptance criteria and asserted at the
  dialog's default size and narrower, per the ruling of 2026-08-05.

## Suggested reading order

1. `_bar_line`, `_bar_reserve`, `segment_blocks`, `segment_span` — the whole rule is four functions.
2. `_control_rect` and `_body_of` — the one structural change, and why `paint` no longer computes
   its own body.
3. The `T-166` section above, against `_paint_text`'s line arithmetic.
