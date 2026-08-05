# Review handoff — criterion 8, the UI batch, 2026-08-04

**From:** Claude Code (Implementer)
**To:** Codex (Reviewer)
**Review base:** `bd4dde8` — the last head before this batch, green on all five CI jobs
**Review head:** `768937c`, pushed. Fifteen commits, 38 files.
*(This line read `1d87929` when the handoff was written. The maintainer then ran the finished feature and it produced five corrections — **read the correction round at the foot of this file before starting**, and review the head named here rather than the one the first round describes.)*

**Ten tasks, `T-132` through `T-141`.** They are one submission because the maintainer made them
one: on 2026-08-04 they were ruled into Phase 2's exit as **criterion 8**, so they now gate the
phase rather than trailing it. Every one was found by opening the application and using it. None
was found by a gate.

---

## Read this first: how criterion 8 was added

`IMPLEMENTATION_PLAN.md` gained an **eighth exit criterion** by maintainer ruling, and *how* it was
added is part of what you are reviewing.

`COORD-R13` corrected this exact shape once: `STATUS.md` had described `T-118` as what criterion 6
was waiting for, which *"promoted a sequencing decision into an exit criterion"*, and the standing
rule since is that a Phase 3 task **"is not a criterion and cannot become one."**

That rule constrains inference. It does not constrain the maintainer, who may amend the criteria —
and here did. So this is written as an amendment with the ruling named, not as a claim that these
tasks were always criteria. **Check that I got that distinction right in both documents**, because
getting it wrong is a documented failure mode of this project rather than a hypothetical one.

**The list is closed at 2026-08-04.** "The UI is caught up" is unfalsifiable — ten tasks came out
of one afternoon and an eleventh sitting would find an eleventh task — so the criterion names ten
ids and stops. `T-142` is filed *outside* it deliberately. If you think the edge is in the wrong
place, that is a finding worth making.

---

## Decisions taken during the batch

| Record | What was ruled |
|---|---|
| `UX-005` rows 6–7 | The toolbar's primary action is the mockup's filled brand button; the queue verbs sit at the far edge |
| `UX-005` row 8 | The row's `⋯` carries **only what the row could not draw**, and is absent when it drew everything |
| `UX-005` rows 9–9d | A playlist is **one row that opens**: count not percentage, segmented bar, shorter child row, `Clear finished` clears a group as a unit |
| `UX-005` row 10 | Playlist items land in `<download directory>/<playlist title>/`, as a fixed rule |
| `UX-005` row 11 | The concurrency control steps with labelled `−`/`+` buttons, not native arrows |
| `SEC-002` amendment | A recorded fixture may keep four facts per playlist entry: address, title, duration, thumbnail |

**Row 9 was ruled twice.** The first ruling was *one job per entry*; the maintainer then asked for a
third shape, it was mocked up (`docs/mockups/2026-08-04-playlist-rows.html`, published), and that is
what was adopted. The superseded ruling is kept below the table rather than deleted — `UX-005`
exists because an argument with its alternatives removed is not a record of a decision.

---

## The ten, and what to attack in each

### `T-137` — a playlist downloaded one file of sixteen

The highest-severity item here, and a **correctness** defect rather than a cosmetic one:
`build_options` set `noplaylist`, so the download took whichever entry the URL resolved to while
the staged row read *Playlist (16 items)*. The row told the truth and the queue did not.

- `PlaylistEntry` + `MediaInfo.entries`; **`extract_flat: "in_playlist"` on the probe only.**
  Without it a probe extracts every entry in full to answer "what is this URL" — one extraction per
  item. A *download* must not have it or it gets a stub with no formats. Both halves asserted.
- **Migration `0004`** adds `playlist_id`, `playlist_index`, `playlist_title` to `jobs`.
  **No `playlists` table**, and the migration argues it at length: a group has no state of its own.
- The dialog expands a probed playlist into one job per entry, into `sanitize_component(title)`.

**Attack:** entries are `QUEUED`, not `READY` — is that right against `UX-003`, which makes a pasted
URL a probed one? My reasoning is that a flat entry is *named* but not extracted, so `READY` would
claim a probe nobody ran. Also: a playlist that enumerates nothing stays one job, which is the old
behaviour; check that is a defensible floor rather than a silent regression.

### `T-140` — the queue draws a playlist as a row that opens

Two commits: the drawing (`bc1a3d4`) and the model (`d54db67`).

- The tree is **flattened in the model**; the view stays a `QListView`. A `QTreeView` would have
  replaced the list, the delegate and the geometry `T118-R7`, `T118-R8`, `T118-R12` and `T118-R15`
  were each spent on.
- Expansion is held **by playlist id** (`T126-R1`'s lesson: progress causes constant refreshes).
- A job inside a closed group reports **no row** — a caller building an index from a hidden job
  would address whatever is drawn there.
- **A group of one is dissolved**, so a playlist whose siblings were removed is not a heading over
  one row.

**`setUniformItemSizes` came off**, and `UX-005` says a bad paste-of-150 number justifies reopening
the shape. Measured:

| | |
|---|---|
| Open ten groups of a 150-entry queue | **0.002 s** |
| `sizeHint` over 160 rows | **0.019 s** |
| Paint a viewport | **0.022 s** |
| Budget | 0.500 s |

**Attack:** the budget is `REPAINT_BUDGET_SECONDS`, five times `NFR-001`'s whole-interaction budget,
sized so it distinguishes "cost proportional to the model" from "cost proportional to the screen"
and nothing finer — `T118-R10`'s gate flapped when it was sized to the fastest machine. Is that
still the right instrument now that it is being asked about layout rather than paint?

### `T-138` — History lost the picture the queue row had

Neither half existed: `HistoryEntry` had no field and `history_view.py` built its delegate with
**no thumbnail store**, saying so in a comment. Migration `0005`, `v5.sql` frozen.
**Three assertions**, because there were three ways to keep failing: the model answers the role,
the view has a store, and the picture survives the move.

### `T-136` — the format line ran under the format control

Two deliberate decisions collided and neither was wrong about its own half: `_paint_text` runs the
selector at full body width *because* "the control sits beside the first two lines", while
`_control_rect` centred the control in the whole body. On a four-line row, centred is across line
three. **The control gave, not the selector** — narrowing the selector is `T118-R8`, the finding
where `REQ-009`'s selector was elided into uselessness by that very slot. Asserted at four row
heights, because the overlap is height-dependent.

### `T-132`, `T-133`, `T-134`, `T-135`, `T-139`, `T-141` — the window's smaller lies

Toolbar button and alignment; the spin box's missing arrows; verbs that ignored the pointer; an
overflow that repeated the row; a disabled control that drew **pixel-identically** to a settable
one; and the concurrency stepper.

**`T-129`, `T-133`, `T-139` and `T-141` are one cause seen four times**: styling a widget switches
it to `QStyleSheetStyle`, and whatever the platform used to draw is then drawn by the sheet or not
at all. That is worth a reviewer's opinion as a *pattern* rather than four times as an instance —
if there is a general assertion to be had here, I did not find it.

---

## What I changed that was not mine to change quietly

**Six pre-existing tests were rewritten in place**, not merely repaired. Each is flagged in its own
docstring; they are listed here so none of them reaches you as a surprise:

| Test | Why |
|---|---|
| `test_clicking_a_rows_control_opens_it_without_selecting_first` | aimed at `rect.center().y()`, inside the control only while it was centred in the row (`T-136`) |
| `test_the_overflow_menu_holds_exactly_what_the_row_offers` | now names the **keyboard** route specifically; the `⋯` holds the narrower set (`T-135`) |
| `test_the_overflow_keeps_its_place_as_the_state_changes` | expected an overflow on a wide row, which `UX-005` row 8 removed; the width is now searched for rather than written down |
| `test_a_completion_records_every_field_req_020_names` | pins the projected field set, so `T-138`'s new column belongs in it |
| `test_a_playlist_entry_is_a_count_and_never_a_record` | renamed and rewritten under the same rule — kept if and only if the adapter reads it (`SEC-002`) |
| `test_the_gate_refuses_a_shape_record_and_a_populated_entry` | `title` is allowlisted for an entry now; `uploader` never was, and it is still refused |

Two of my *own* regressions from earlier rounds were also rewritten after they were found to be
measuring the wrong thing — see below.

---

## The thing most worth your scepticism

**Nine assertions in this batch measured a proxy rather than the property.** Most were mine, and
several **passed while the defect was visible on the maintainer's screen**:

1. A hover test drew through `QApplication.style()` with no widget — the *platform* style.
2. A palette test asserted the *global* palette held the row tint. It encoded the defect it was
   written for.
3. The chip's terminal test compared two rows that drew no chip at all; both crops matched because
   nothing was in them.
4. The spin box test asserted arrow-coloured pixels *existed*. A solid block satisfies that, and a
   solid block is what shipped.
5. The toolbar test built a bare `QToolBar`, which paints no gradient, and compared `window`
   against `window`.
6. An indent test compared whole rows and survived deleting the rail its docstring claimed.
7. Its ink probe used `QColor(pixel).alpha()`, which is 255 for every pixel whatever the image held.
8. A cost test timed `repaint()` on an offscreen widget and reported `0.000s`.
9. A stepper test compared a pixel inside a button against the toolbar **at a different height**,
   across a gradient.

They share one shape: **two things are compared that differ for a reason other than the one being
claimed.** `ai/TESTING.md` §13 already forbids a test that passes for the wrong reason; what these
add is that a mutation is the only thing that reliably tells them apart. Every claim in this batch
has a recorded killed mutation, and the last two were caught before shipping rather than after —
but the base rate here is the reason to distrust the rest, and **re-running the mutations yourself
is the cheapest way to check me.**

There is a tenth, of a different kind: I verified `T-133`'s fix with `QT_QPA_PLATFORM=offscreen`
against a bare 90×30 spin box when the maintainer's session is Wayland and the real control is
58×23 in a toolbar. The fix was correct and the verification was not evidence for it.

---

## Checks run, and their actual results

| Gate | Result |
|---|---|
| Full suite, Linux | **2129 passed, 11 skipped, 2 deselected** |
| `ruff check .` / `ruff format --check .` | pass, 158 files |
| `mypy src`, `mypy`, both `--platform win32` | pass |
| Task placement | 14 passed |
| CI | **green on all five jobs at `d54db67`**, `windows desktop` and `frozen windows` included |

**Windows evidence stops at `d54db67`.** `006b152` (the stepper's styling) and `1d87929` (the
roadmap) came after it: `006b152`'s run was **cancelled** when `1d87929` superseded it, and
`1d87929`'s run was still queued when this was written. `006b152` is a **style-sheet change**, so
its Windows leg genuinely matters — treat that as owed rather than as covered.

---

## What this does not claim

- **That the dark theme has been seen.** It still has not. Every dark-theme figure in this batch is
  arithmetic or an offscreen render.
- **That `T-142` is done.** A playlist header has a count, a bar and a disclosure and **no verbs of
  its own**; `UX-005` row 9 names four. Split out deliberately, outside criterion 8.
- **That the playlist failure the maintainer saw is explained.** `noplaylist` explains one file
  instead of sixteen. It does not explain *none*, and that report is recorded as undiagnosed.
- **That a recorded fixture exercises playlist expansion.** Entries are captured now, but no
  existing fixture was re-recorded, so `T-137`'s projection tests are still built from literal info
  dicts.

## Still owed after this review

- **Windows on `1d87929`**, per the note above.
- **The 60-run Linux soak**, which wants a settled head — this batch is why it has not run yet.
- **The independent Phase 2 exit review**, over a table that now has eight criteria.

---

# Correction round — the batch was run, and it produced five more

**Review head is now `6b354f0`**, two commits past the one this handoff was written against.
`a884035` carries the corrections; `6b354f0` is the roadmap. **Do not review `c0710dc`** — the
maintainer ran the finished feature between the handoff and now, and everything below came out of
that sitting.

**The playlist itself was fine.** Sixteen of sixteen, grouped, with the disclosure, the count and
the indented entries. `T-137` and `T-140` did what they claimed. Every correction below is
something the *rest* of the window got wrong around a working feature.

## Six reports, and what each actually was

| Reported as | What it was |
|---|---|
| *Pause queue and Clear finished are no longer buttons* | **Mine, and my own test asserted it** — see below. Making tool buttons transparent fixed a flat patch over the toolbar's gradient and destroyed the buttons |
| *The progress bar didn't update — I'd expect green* | It did. Every segment drew in `muted`, so **sixteen done looked exactly like sixteen waiting**: the bar reported nothing while appearing to report something |
| *The data under each video is cut off* | `UX-005` row 9c says a child row drops the format line. It was **sized** for two lines and the painter still drew three, so the third was clipped |
| *The queue shows 17 for a 16-video playlist* | The tab counted **rows**: 17 open, 2 closed. The number moved when a group was opened, without the queue changing |
| *No thumbnails for any of the playlist* | A flat extraction carries **`thumbnails`, a list — not `thumbnail`**. Reading only the singular is why a pasted URL showed its picture and none of the entries did |
| *A paused queue should still probe* | **It already does** (`T080-R1`, and the manager says so outright). The real gap is that a playlist's entries are **never probed at all** |

## What changed in the record

- **`UX-005` row 12** — the tab's count is of *downloads, not lines*. The first amendment left this
  *proposed* ("count rows as shown"); running it settled it, because the number moved when a user
  opened a group.
- **`T-143` filed** — a playlist's entries are never probed. Two of the reports above are one gap,
  and it is **not** the one it looked like: pause is not the problem, and `UX-003`'s "a queued job
  is a probed one" is the requirement in tension. The task names that tension rather than resolving
  it, because moving the probe after admission is a design choice with a cost.
- **`T-142`** — the playlist header still has no verbs of its own.

Both are **outside criterion 8** on purpose. The list closed on 2026-08-04 so that finding more
work cannot reopen the phase.

## The thing to weigh, and it is about process rather than code

**Criterion 8 was called met and then corrected five times within the hour.** That is the most
reviewable fact in this submission, and it cuts two ways:

- The closed list did its job — none of this reopened the phase, and the follow-ons are filed as
  Phase 3.
- But "met" was claimed on a batch that had five visible defects in it, and **the thing that found
  them was a person opening the window**, for the sixth time in this project's history. If you
  think criterion 8 should not be called met until someone has run the built application against a
  written checklist, that is a finding worth making and I would not argue with it.

## A tenth test, and it is a different kind

The handoff above lists nine assertions that measured a proxy. There is now a tenth, and it does
not belong in that list:

> `test_the_toolbars_own_background_runs_behind_its_buttons` asserted that the toolbar's buttons
> were **indistinguishable from the bar**. It was correct, precise, and mutation-proof — the code
> did exactly what the test said. What it asserted was the wrong choice, and the maintainer
> reported the result as *"no longer buttons"*.

So there are two shapes, and separating them is worth more than the count:

- **Measured a proxy** (eight): two things compared that differ for a reason other than the one
  claimed. **A mutation catches these.**
- **Encoded the defect** (two — the palette test at `T130-R1`, and this): the test faithfully
  asserts a decision that was itself wrong. **No mutation catches these. Only running the
  application does.**

The mockup is the check that would have caught this one: it says `.btn` is
`border: 1px solid var(--b); background: var(--s)`, and I made them transparent without going back
to it. **Worth checking whether anything else in this batch diverges from
`docs/mockups/2026-08-03-main-window-b1.html` in the same way** — that is the highest-value thing
you could do with this submission.

## Checks, restated for the new head

| Gate | Result |
|---|---|
| Full suite, Linux | **2132 passed, 11 skipped, 2 deselected** |
| `ruff check .` / `ruff format --check .` | pass, 158 files |
| `mypy src`, `mypy`, both `--platform win32` | pass |
| Mutations | five more killed for the corrections above |
| CI | green on all five jobs at **`1d87929`**, which contains `006b152` |

**Windows evidence stops at `1d87929`.** `a884035` — which changes the style sheet and the
delegate — and `6b354f0` have none: `a884035`'s run was cancelled when `6b354f0` superseded it.
Treat that as owed.

## Unchanged from the first round

The dark theme still has not been seen; the playlist failure the maintainer originally reported is
still undiagnosed; no recorded fixture exercises playlist expansion; and the six pre-existing tests
rewritten in place are listed above and still want your eyes.
