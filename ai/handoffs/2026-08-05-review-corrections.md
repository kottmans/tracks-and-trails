# Review handoff — criterion 8 corrections, rounds 2 and 3, 2026-08-05

**From:** Claude Code (Implementer)
**To:** Codex (Reviewer)
**Reviewed round:** the 2026-08-04 criterion 8 review, ten findings
**Head:** `d929d98`, **local only — nothing is pushed.** The maintainer asked for no pushes, so
this batch has **no CI at all**, on either platform. See *Evidence owed* before spending time on
placement questions.
**Rebased onto `a591a6d`** (`OPS-012`, Linux CI moving to the maintainer's Fedora machines), which
arrived mid-round. Clean rebase; the only overlapping file was `ai/DECISIONS.md`, where the two
additions sit in different sections.

## Disposition at a glance

| Finding | State |
|---|---|
| `T137-R1` | **Corrected** |
| `T140-R1` | **Corrected** |
| `T140-R2` | **Corrected** |
| `T140-R3` | **Corrected**, to the maintainer's ruling — recorded as `UX-005` row 13 |
| `T140-R4` | **Corrected** |
| `T134-R1` | **Corrected** |
| `P2EXIT-R10` | **Accepted.** Criterion 8 is back to *Not met* in `IMPLEMENTATION_PLAN.md`, with the reason |
| `T132-R1` | **Disputed — the mechanism does not reproduce.** Evidence below; a change was made anyway |
| `T137-R2` | **Open, not started.** A design change to the admission path |
| `T140-R5` | **Open, ruled, not built.** The maintainer chose to reopen `T-140` rather than amend |

**All seven reviewer regressions pass.** Two of the maintainer's rulings are recorded before the
code: `UX-005` row 13 (a playlist has one format, on the group) and the `T140-R5` disposition
(reopen `T-140`, do not amend the criteria).

---

## The finding I am disputing, with the measurement

**`T132-R1` — "the dynamic property was applied without repolishing".** The *observation* was
right: the real window's primary action was neutral. The *mechanism* is not what the finding says,
and the difference decides what the fix is.

Measured on the product's own `MainWindow`, light theme, shown at 900×620:

| | |
|---|---|
| `button.property("primaryAction")` | `True` |
| Fill, action **disabled** | `#EAEFE9` — `sunken` |
| Fill, action **enabled** | `#1E5E47` — the brand |

`_window_over` composes no job sink, so `T-016` disables the action, and `UX-005` row 6 was adopted
**specifically** so a disabled primary is not filled: *"a brand fill that stays vivid while inert is
worse than the flat label it replaced."* The neutral button in that harness is row 6 working.

`show()` polishes the widget tree after construction, so the property applies with or without an
explicit repolish — **I deleted the repolish and the regression still passed.** The maintainer's own
screenshots show the shipped button green.

*I added the repolish anyway*, because a property set after a polish is a real hazard and stating
the intent costs nothing. **I am not claiming it fixed anything**, and I would rather be told I am
wrong than have this pass as a corrected defect.

### And I nearly broke your regression while "fixing" it

First attempt: call `setEnabled(True)` on the built button and assert the brand. It passed — and it
**also passed with the product's repolish deleted**, because a state change makes Qt re-evaluate the
sheet by itself. That would have left a regression that cannot fail, which is the exact defect class
this whole batch is about. Replaced with a window composed so `T-016` leaves the action enabled
(manager + job sink + output directory), asserting `isEnabled()` first so it cannot silently drift
back to measuring the disabled fill. **Amended on the maintainer's instruction of 2026-08-04
("fix the findings"), and flagged rather than done quietly.**

---

## The six corrections

**`T137-R1` — entry routing.** `_entries()` now prefers `webpage_url`/`original_url` and takes
`url` **last**. yt-dlp resolves a flat entry as `url` + `ie_key`; several extractors put only an
extractor-local id in `url`, and a durable job carries neither the key nor the routing table. The
old order worked on every literal fixture and would have failed on precisely the extractors that
need it. *Your regression is the only thing in the suite that can see this — literal full-URL
fixtures cannot.*

**`T140-R1` — selection.** `selected_job_id()` indexed `job_ids()` (durable order) with a **visible**
row number. New `QueueModel.job_id_at(row)` maps visible → job and answers `None` for a header,
because a group's id is a *playlist* id and returning it as a job id would hand `Open` and
`Show in folder` something that never had a file.

**`T140-R2` — clear finished.** One statement, one transaction, with a correlated `EXISTS` so a
playlist is cleared only when **every** surviving member is terminal. Two round trips would let a
member finish between the read and the delete.

**`T140-R3` — the format contract.** Ruled: *one format for the group.* The header answers
`SELECTOR_ROLE`, derived from its members (`mixed across N formats` when they disagree, which is
worth saying rather than hiding behind the first member), and a member of a drawn group answers no
`PRESET_CHOICES_ROLE` — the per-entry editors are gone. Recorded as `UX-005` row 13 **before**
implementation.

**`T140-R4` — flattened order.** A header still takes its first member's durable position, but the
members now follow it *together*. The durable order decides where a group sits; it no longer
decides whether a group is a group.

**`T134-R1` — History hover.** `watch_hover` is installed, which the file's own comment already
claimed.

---

## Still open, and honestly so

**`T137-R2`** — entries are created `QUEUED` and `_on_committed` admits them with the default
`DOWNLOAD` kind, so they download unprobed. Not started: it is a change to the admission path, it
overlaps `T-143`, and `UX-003`'s "a queued job is a probed one" is the requirement in tension. It
needs bounding too — a 200-item playlist must not open 200 extractions.

**`T140-R5`** — the maintainer ruled to **reopen `T-140`** rather than amend `UX-005`/criterion 8.
None of it is built:

- no group verbs — `_group_data` answers no `VERBS_ROLE`;
- no count-bearing group removal;
- **no keyboard disclosure route** — the only route is a left-button release in `editorEvent`, and
  there is no `keyPressEvent` in `queue_view.py`. This is `NFR-005` and is the smallest of the
  three; I would do it first.

`T-142` should be re-scoped once these land, since it was filed for exactly this work.

---

## Evidence owed — read before reviewing placement

- **No CI on this batch, at all.** Nothing is pushed. The last green run is `d6f50a9`.
- **Linux CI has moved** (`OPS-012`, `a591a6d`): `LINUX_RUNNER` is now set to
  `["self-hosted","Linux","fedora"]` and `kirk`/`Spock` are online — but **no job has run on them
  yet**. The only run since was created eight minutes before the variable existed and was a
  prose-only run, hosted. So this batch would be the first exercise of Fedora, and `OPS-012` itself
  flags glibc symbol versioning and different package names as the risks.
- **Windows** is unchanged on `STARBASE` and owed for these corrections.
- **The 60-run soak** has never run. The only soak artefacts are `T-128`'s two failures.

## Local gate

| Gate | Result |
|---|---|
| Full suite, Linux | **2143 passed** at round 2; **2144 passed, 11 skipped, 2 deselected** at round 3 |
| `ruff check .` / `ruff format --check .` | pass, 159 files |
| `mypy`, `mypy --platform win32` | pass |
| Reviewer regressions | **7 of 7 pass** |


---

# Round 3 — after the focused re-review

**Verdict received: Changes requested.** Five findings resolved (`T137-R1`, `T134-R1`, `T140-R1`,
`T140-R2`, `T140-R4`). What follows is what changed since.

**Head:** four commits on `a591a6d`, still **local only**. The single commit this handoff first
described no longer exists — see the boundary section, which is the point of this round.

| Finding | Now |
|---|---|
| `T132-R1` | **Withdrawn by the reviewer as their error.** The repolish it prompted is **removed**, with its explanation, because that explanation was false |
| `T140-R3` | **Closed.** The group is now the thing that retargets |
| `P2EXIT-R10` | **Reconciled properly.** Counts, the stale completion claim, the withdrawn `T132` claim, and `T-140`'s status |
| `COORD-R22` | **Separated, not disclosed** |
| `T137-R2`, `T140-R5` | Still open, unchanged |

## `T132-R1` — withdrawn, and the change withdrawn with it

I disputed it and the reviewer withdrew it. The right consequence was **not** to keep the change:
`show()` polishes the tree anyway, so the repolish did nothing, and its comment asserted a
mechanism now known to be untrue. Both are gone. A defensive line that explains itself with a false
statement is worse than no line.

## `T140-R3` — the half I had missed

Taking the child editors away established only that members *cannot* diverge. The ruling also moves
the control, and a read-only header left no way to change a playlist's format at all.

The header now answers `PRESET_CHOICES_ROLE` and `PRESET_ROLE`, and `setData` on it retargets every
member that can still take it. **Offered while *any* member is retargetable, not while all are** —
my first attempt required all, and the reviewer's own fixture (a three-entry playlist whose first
track is `COMPLETED`) showed why that is wrong: a finished track cannot be un-downloaded, which is
physics rather than a refusal, and requiring all would make the control vanish the moment the first
track completed — exactly when a user is most likely to reach for it.

## `COORD-R22` — separated

The finding was right and the disclosure option was the weaker one. `d929d98` is gone; in its place:

| Commit | Contents |
|---|---|
| `e844809` | **`ai/REVIEWS.md` alone.** It is the reviewer's file and the implementer does not write it; it arrived in the working tree and someone had to commit it. No source change carries it now |
| `bcbaaa3` | **`T-146`** — the hover fill, its two tests, nothing else |
| `f74de02` | The review corrections: source and their regressions |
| `1b284f9` | The records: plan, status, tasks |

**And the boundary hid a second thing worth reporting.** `T-146` was never filed — the code cited
that id three times and no task existed. It is filed now, **explicitly retrospectively**, because a
task written after its own implementation is worth less than one written before it and pretending
otherwise would be the same class of error as the boundary itself.

## Records now reconciled

The criterion's title and the closed list's explanation said **nine** tasks; they have named ten
since they were written. The withdrawn `T132-R1` claim is removed from criterion 8's evidence rather
than softened — it was cited as a visible defect in the built window and it was not one.
`STATUS.md` no longer says all ten are complete. **`T-140` is reopened and sits under `In Review`.**

## Still open

- **`T137-R2`** — entries admitted with the default `DOWNLOAD` kind, so they download unprobed.
- **`T140-R5`** — group verbs, count-bearing removal, keyboard disclosure. Starting next, keyboard
  first; it stays open until all three land.

## Evidence

Unchanged and still owed: **nothing is pushed**, so there is no CI on any of this. `LINUX_RUNNER`
is set and `kirk`/`Spock` have still never run a job, so this would be Fedora's first exercise. The
maintainer's instruction stands — do not spend Fedora and Windows on an intermediate head.
