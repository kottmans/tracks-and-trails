# Criterion 8 — the 40-row run, 2026-08-05

**Purpose:** Evidence for Phase 2's eighth exit criterion, on the candidate head.
**Required by:** `P2EXIT-R10`, and closing `P2EXIT-R12`.
**Supersedes nothing.** The first run (`2026-08-05-criterion-8-checklist-run.md`, eleven findings)
and the second (`2026-08-05-criterion-8-second-run.md`, 39 of 41) stand as what they observed.

---

## The record

```
Head:      376407f..165b6e4   (see the note below)
Platform:  kirk, Fedora
Date:      2026-08-05
Result:    PASS — 40 of 40 rows. No row failed, and no row was recorded
           as passing over a known defect.
Runner:    the maintainer
```

**On the head.** `376407f` is the last commit that changed anything under `src/` or `tests/`;
everything after it is records. Checkable rather than asserted:

```
$ git diff --stat 376407f..165b6e4 -- src/ tests/
(no output — no source or test file differs)
```

So a run anywhere in that range is a run on one build of the application. Stated as a range for
`P2EXIT-R8`'s reason: evidence about a head that moved is evidence about nothing, and a range a
reader can verify beats a single sha chosen for tidiness.

## What is different about this run, and why the count changed

**40 rows, not 41.** Row 2.7 was removed on 2026-08-05 by the reviewer's disposition in `T161-R1`.
It had been authored *after* the closed list to describe `T-160`, a Phase 3 defect — so it could
never pass while that defect lived, and keeping it made a Phase 3 task into a Phase 2 exit gate.
**The behaviour it asked for was not weakened**: it moved to `T-160`'s acceptance evidence. `T-160`
remains open, remains Phase 3, and is not required for exit.

**Row 3.15 is the one this run existed for.** `T-161` — every playlist drawing a blank parent
picture — was fixed and had never been *observed* fixed. `P2EXIT-R12`'s point was precisely that a
fix is not an observation, and that the unit regression proved an address was selected rather than
a picture shown. **This run is the observation.**

**Rows 3.6 and §5 ran for the second time.** 3.6 caught a real defect on its first outing (a
completed playlist drawing blank blocks, `T-140`'s colour fix reading `palette.highlight()` on a
widget whose palette carries the selection tint) and passes here against the correction at
`6bae7ec`.

## The limits, stated as part of the result rather than after it

`P2EXIT-R12` reset this criterion for stating a verdict over the top of its own evidence. The
limits are therefore inside the claim:

- **One platform, and it is a ruling rather than a gap.** Fedora, on `kirk`. CI runs the suite on
  Windows and `windows desktop` is green on the candidate; what is unevidenced is **a person
  looking at the window** there. **The maintainer ruled this acceptable on 2026-08-05** — *"I'm
  okay with criterion 8 resting on one platform (linux) for now."* Written as a ruling because a
  reader cannot otherwise tell a limit that was **chosen** from one that was merely **hit**, and
  the residual is real: `T-134`'s hover defect and `T-149`'s missing `:checked` state are the kind
  of thing only a person at the window catches.
- **One runner, who is also the person who accepted the mockups.** `AGENTS.md` §3 locates the
  independent judgement in the exit review, not here. This is the maintainer checking that the
  built window matches what they accepted.
- **Four known defects were present during the run** — `T-163`, `T-164`, `T-166`, `T-167`, all
  Phase 3, all listed in the checklist's *known open* section so they are not re-filed. **"Pass"
  means every row passed, not that nothing is wrong with the window.**
- **A pass is not a proof of absence.** The first run found eleven defects against 2153 green
  tests; the checklist covers what `T-132`–`T-141` accepted, and nothing else.
