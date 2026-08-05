# Criterion 8 — the second checklist run, 2026-08-05

**Purpose:** Evidence for Phase 2's eighth exit criterion, on the candidate head.
**Required by:** `P2EXIT-R10`
**Supersedes nothing.** The first run (`2026-08-05-criterion-8-checklist-run.md`) stands as the
record of eleven findings; this is the run against the code those findings produced.

---

## The record

```
Head:      6bae7ec..541b484   (see the note below — the maintainer did not record which)
Platform:  kirk, Fedora
Date:      2026-08-05
Result:    39 of 41 rows passed. ROWS 2.7 AND 3.15 FAILED — see the correction below
Runner:    the maintainer
```

**On the head, stated precisely rather than rounded.** The maintainer ran the checklist on `kirk`
without recording which of the last three commits was checked out. **It does not change what the
run evidences, and the reason is checkable rather than asserted:**

```
$ git diff --stat 6bae7ec..541b484
 ai/TASKS.md | 114 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 114 insertions(+)
```

`f54b493` and `541b484` are prose. **No file under `src/` differs across that range**, so a run on
any of the three is a run on one build of the application. Written this way because `P2EXIT-R8` was
evidence about a head that moved, and the remedy for that is a range a reader can verify — not a
single sha chosen for tidiness.

## Correction, 2026-08-05 — this record first said "pass, all 41 rows", and that was wrong

**`P2EXIT-R12` found the record contradicting itself**, and it is right. The result line claimed
every row passed while the section below it listed defects that **are** those rows:

| Row | What it asks | Why it did not pass |
|---|---|---|
| 2.7 | The format control must not be drawn over the row's thumbnail at the dialog's default size | `T-160` is exactly that overlap, and it is open |
| 3.15 | The playlist's **own staged row shows a picture** | `T-161`: every playlist draws a blank parent tile, because the chosen address 404s |

**Filing a failure as a Phase 3 task does not convert it into a passed row.** The closed-list rule
decides *which task owns* a defect; it has no authority over what a checklist row observed. Writing
"pass" beside a known failure is the same class of error `P2EXIT-R10` reset this criterion for —
a verdict stated over the top of its own evidence.

**Row 3.15 is worse than a Phase 3 defect.** `T-153` is accepted **Phase 2** work whose criterion
is that the staged playlist row *shows* its picture. Its regression proves an address string is
selected and cannot prove the address yields an image, so the accepted property is still false in
the built window. `T-161` is therefore reclassified as `T-153`'s unfinished half rather than new
scope.

**Rows recorded from here on must distinguish three outcomes** — passed, failed, and failed-with-an-
accepted-owner — because collapsing the last two into the first is what produced this.

## What this run is worth, and what it is not

**41 rows attempted, including the two that had never been run; 39 passed.** Rows 3.6 and §5 were unreachable in the
first run — the first needed a download to fail and the checklist did not say how to arrange one;
the second needed a look at a theme nobody had opened. Both are answered here.

**Row 3.6 found a defect on its first outing**, which is the strongest thing this run has to say.
A completed playlist drew *blank* blocks: `T-140`'s colour correction read `palette.highlight()`,
and a `QListView`'s palette carries the quiet selection tint by `T130-R1`'s deliberate design, so
the delegate read `#ebf1ee` where the application's palette answers `#1e5e47`. On a white row that
is no fill at all. Fixed at `6bae7ec`, and **the row that caught it had existed, unrun, since the
checklist was written.**

**Three more findings came from the same sitting** and are Phase 3 by the closed-list rule:
`T-165` (fixed anyway — a cancelled playlist calling itself failed), `T-166` (the group's verbs
erasing the format line) and `T-167` (the bar changing shape twice as the window is dragged).

## The limits, stated so the exit review does not have to find them

- **One platform.** `kirk`, Fedora. The Windows half of criterion 8 is not evidenced here; CI
  covers the suite on Windows, and the *window* on Windows has not been looked at by a person.
- **One runner, who is also the person who accepted the mockups.** `AGENTS.md` §3 puts the
  independent judgement in the exit review rather than here, so this is a maintainer's check that
  the built window matches what was accepted — not an independent one.
- **Four known defects were present during the run** and are listed in the checklist's *known
  open* section so they are not re-filed: `T-161`, `T-162`, `T-163`, `T-164`. A reader should not
  read "pass" as "nothing is wrong with the window".
