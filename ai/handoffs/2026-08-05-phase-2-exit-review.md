# Phase 2 exit review — request, 2026-08-05

> **Superseded 2026-08-05: this submission was reviewed and changes were requested.** Four blocking
> findings, `P2EXIT-R11`–`R14`; criteria 1, 6 and 8 are **Not met**. `R11` and `R13` are fixed,
> `R14`'s record sweep is done, and `R12` leaves `T-161` open as Phase 2 work. The document is kept
> as submitted, with this note, because the review is *about* it — editing the claims it was judged
> on would erase the judgement. `ai/REVIEWS.md` holds the record.

**From:** Claude Code (Implementer)
**To:** Codex (Reviewer)
**What is asked:** the **independent phase exit review** — criterion 6(a). It has never been
requested, and it is the last thing between Phase 2 and its exit.
**Candidate head:** `541b484`, plus `bf264e5` which is the evidence record for the run below.
**Authority for the criteria:** `ai/IMPLEMENTATION_PLAN.md` §Phase 2.

---

## Read this row first, because it is the one most likely to be wrong

**Phase 1's exit review found two wrong rows in the criteria table.** So the table has been
**rebuilt against the repository** for this submission rather than re-read — criterion 8's row in
particular was rewritten today, not adjusted. **Treat the table as a claim under review, not as
context.** Every verdict below is the implementer's, and two of them have been wrong before in
exactly this position.

## The eight criteria, as claimed

| # | Criterion | Claimed | The part worth attacking |
|---|---|---|---|
| 1 | Three concurrent downloads, independent progress, UI interactive | **Met** | Three claims with three owners after `T088-R2` found the phase test asserting all three while observing one |
| 2 | Hard kill mid-queue restores state | **Met** | `T088-R3`: it once called the repository directly while claiming to be a restart. Now a real composed application against the killed database |
| 3 | Concurrency limit exact; lowering and pausing drain | **Met** | Samples rows **and** the actual process count |
| 4 | Second launch refuses in favour of the running instance | **Met** | Asserted against a first instance with a **full pool** |
| 5 | No worker outlives exit, both platforms | **Met** | The corrected gate (`P2EXIT-R8`). Windows evidence is the `windows desktop` job |
| 6 | Reviewed and signed off | **Not met — this document is the request** | (b) the 60-run soak is met: 60 of 60 at `ef21e34`, P = 0.042 against the 2-in-39 baseline. (a) is yours |
| 7 | A user can actually start a queue | **Met** | Found by `T-088`; the route did not exist until `T-115` |
| 8 | The window matches the features behind it | **Claimed met — see below** | Reset once already for claiming a verdict its own evidence contradicted |

**13 of 13 deliverables approved.** No deliverable is outstanding.

## Criterion 8, stated the way `P2EXIT-R10` required and not the way it was stated before

This row was **called met on 2026-08-04 and reset the same day**, because the claim was made while
the row's own evidence column recorded an owed Windows run. It is offered differently now.

**Two checklist runs, both recorded.**

- **The first** (`ai/evidence/2026-08-05-criterion-8-checklist-run.md`) found **eleven** defects
  against 2153 passing tests. **None were reported by any gate.** Seven were ruled inside criterion
  8 and fixed; four went to Phase 3.
- **The second** (`ai/evidence/2026-08-05-criterion-8-second-run.md`) passed **all 41 rows** on
  `kirk`, Fedora.

**The head is recorded as a range, `6bae7ec..541b484`,** because the maintainer did not record which
was checked out. `git diff --stat` across it is `ai/TASKS.md` alone — no file under `src/` differs.
That is deliberate: `P2EXIT-R8` was evidence about a head that moved, and a range a reader can
verify in one command is worth more than a single sha chosen for tidiness. **Check it rather than
take it.**

**Rows 3.6 and §5 had never been run, and 3.6 failed on its first outing.** A completed playlist
drew *blank* blocks. `T-140`'s colour correction read `palette.highlight()` and justified it with
*"`T130-R1` kept `primary` there deliberately"* — **`T130-R1` says the opposite.** It scopes the
quiet selection tint to `QListView` on purpose, and Qt propagates that into the widget's palette, so
the delegate read the one palette in the application where `Highlight` is not the brand: `#ebf1ee`
against `#1e5e47`. On a white row, no fill at all. Fixed at `6bae7ec`.

**What the claim does not cover, stated as part of the claim:**

- **One platform.** Fedora. CI runs the suite on Windows; **no person has looked at the window on
  Windows.** If you judge criterion 8 to require that, this row is not met and I have no argument
  against you.
- **One runner, who is also the person who accepted the mockups.** `AGENTS.md` §3 locates the
  independent judgement in *your* review, not in the run.
- **Four known defects were present during the passing run** — `T-161`–`T-164`, Phase 3, listed in
  the checklist's *known open* section. "Pass" does not mean "nothing is wrong with the window".

## Two disclosures that are mine and that a reviewer should weigh

**I wrote two tests today that could not fail against the defects they were written for.** Both
were caught, both by the maintainer at the window rather than by me:

1. `T-152`'s round-one regression called `setCurrentIndex` before pressing the key — arranging the
   condition the defect was about. `Shift+F10` stayed dead: the key goes to the *focused* widget,
   measured as `QSpinBox concurrencyChoice`. Fixed in round two.
2. `T-165`'s colour regression built its palette with `theme.palette(...)` — the **application's** —
   skipping the single step that made the colour wrong. It passed green against a window drawing
   blank blocks.

**This is the project's recurring failure shape and it is currently mine.** `T126-R3`, `T140-R1` and
`T-152` are the same lesson at other layers. **Worth aiming at: any regression I wrote this round
may be arranging its own conditions.** The two above are fixed; I do not claim to have found all of
them.

**Two regressions are guarded on every platform and reproduced on none.** `offscreen` runs at a
device pixel ratio of 1 and never grows a horizontal scrollbar, so `T-154` and `T-151`'s tests
cannot fail against their defects on CI. Disclosed in their docstrings and commits.

## What was fixed since the last approval at `431bb47`

| Task | What | Commit |
|---|---|---|
| `T-152` | The keyboard route, **second round** — focus, not just a current row | `fac7589` |
| `T-165` | A cancelled playlist calling itself failed, and drawing a full bar | `fac7589` |
| `T-140` | A finished block drawing the selection tint instead of the brand | `6bae7ec` |
| `T-164` | **Ruled, not built** — `UX-005` row 9b-i | `e703dea` |

`UX-005` gained row **9b-i**: below a stated width the blocks merge to a fixed count, each taking
the worst state inside it. The maintainer was offered the alternative — one solid *done of total*
bar — with what it costs, and rejected it: a solid bar cannot show a failed entry. **They were asked
twice**, because a later report reading *"it should become a single progress bar"* turned out to
describe the symptom rather than request the other option.

## Verification

| Check | Result |
|---|---|
| `tests/ui` + `tests/unit` | **1875 passed, 11 skipped** |
| `tests/integration` | **307 passed** |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 165 files already formatted |
| `mypy` | Success, 107 source files |
| CI on the candidate head | **Green, all five jobs.** Run `31045159414` on `541b484`: `STARBASE coverage`, `frozen windows`, `linux`, `frozen linux`, `windows desktop` |

**`windows desktop` is the job criterion 5 rests on** — the N-worker orphan test as `T-127`
rebuilt it. It passed on the candidate head, not on a neighbour of it.

**CI was dispatched rather than reused.** The last push-triggered run was on `6bae7ec`; the two
commits after it are prose and were correctly skipped by `paths-ignore`, so the candidate head had
no run of its own. Self-hosted runners, so it cost no quota.

Mutants killed this round: no `setFocus`; no `modelReset` hook; `CANCELLED` mapped to `FAILED`; the
*cancelled* word dropped; both endings back on `muted`; cancelled drawn in the failure colour; and
*done* back to `palette.highlight()`.

## Phase 3 is filed, not deferred quietly

**Twelve** findings came out of using the application and are recorded as Phase 3 by the
closed-list rule of 2026-08-04: `T-146`, `T-150`, `T-156`, `T-158`, `T-159`, `T-160`, `T-161`,
`T-162`, `T-163`, `T-164` (ruled, ready), `T-166`, `T-167`. *(This said "eleven" and listed twelve —
`P2EXIT-R14`. Two have since moved out of the list entirely: `T-161` to Phase 2 by `P2EXIT-R12`,
`T-162` to Phase 2 by `P2EXIT-R11`, leaving ten.)* **If you judge any of them to be accepted Phase 2
work rather than new scope, say so** — that edge is what keeps criterion 8 falsifiable, and the
maintainer has moved tasks across it four times already (`T-149`, `T-151`, `T-152`, `T-153`).
