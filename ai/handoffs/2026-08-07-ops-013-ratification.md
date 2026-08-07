# Ratification handoff — `T-107`'s criterion, recorded as `OPS-013`

**From:** Claude Code (Implementer / Planner)
**To:** Codex (Reviewer)
**Follows:** *2026-08-07 — `T-107` High-correction continuation* (`ai/REVIEWS.md`) — `T-107`
**Blocked pending maintainer ratification**, `T-187` **Approved**
**Base:** `09c57c3`, unchanged. **No source, test or fixture is touched by this handoff.**
**Branch:** `main`. Serial mode, no wave.

---

## The ratification you asked for

**The maintainer ratified the exact wording, on 2026-08-07.** It is recorded as **`OPS-013`** in
`ai/DECISIONS.md`, Accepted, with the maintainer named:

> Every column `REQ-003` names is present, and populated from a recorded fixture by value **where
> the source reports it**; `fps` may remain covered by the derived fixture until `T-185` finds an
> acceptable source.

So `T107-R1` is **Resolved at `09c57c3`**, and `T-107` is approved with no further source
correction. `T-107` has moved to `## Complete` with status **Approved at `09c57c3`**, and
`## In Review` is now empty.

**You were right to refuse to take it.** The correction recorded the amendment as the maintainer's
on the strength of your *offer* of a wording, and the handoff called it yours; neither document is
where a ruling belongs. It is worth being precise about what went wrong, because it is not quite
"the wrong name was written down": the maintainer *had* chosen this in conversation, so the decision
existed — but it existed **only in a task entry, a commit message and a `STATUS.md` paragraph**,
which are exactly the three places a reviewer cannot verify authority from. An accepted
`DECISIONS.md` entry is the only artifact that survives the conversation that produced it. That is
now the substance of `OPS-013`'s rationale rather than a footnote to it.

## `OPS-013` is deliberately wider than `T-107`

Phase 3 has five exit criteria left, and three of them are the same shape. The general rule the
entry states:

> A recorded-evidence requirement binds a column only where an acceptable source reports it.
> Covering the remainder synthetically is permitted **only** when the fixture declares it synthetic
> and an open task owns the gap. Absent either, the criterion binds as written.

Both conditions hold here — `derived_format_columns.json` carries `what_is_synthetic`, and `T-185`
is open — and the entry says plainly that absent either one the original wording stands. **Please
push back if that generalisation is broader than the ratification supports.** It was written to stop
the next task settling the same question in a commit, but it is a rule you will be reviewing
against, and it was not part of what the maintainer was asked to ratify.

`OPS-013` also records the alternatives, including the one that was *considered and not taken*:
time-boxing `T-185` to Phase 3's exit. It was declined because a deadline does not produce a source,
and closing `T-185` as *"none exists"* is already an outcome the phase can exit on.

## `T107-R8` — confirmed, and smaller than it looks

Verified independently before recording it. `_fixture.extractor` is the literal `"archive.org"` at
[`tests/fixtures/capture.py:361`], so **all four recorded fixtures carry it** and only
`wikimedia_caminandes.json` is false. `info_dict` carries no `extractor` in any fixture.

The useful detail for whoever takes it: **`extractor` is hand-written provenance, not captured.**
It is in `ALLOWED_FIXTURE_FIELDS` alongside `content_licence` and `why_this_source`, and `SEC-002`
keeps it out of `info_dict` because the projection never reads it. So the truthful value can be
declared on the `Source` next to its url and licence — **no re-capture, no network, no `src/`
change**. Your second requirement, gating a further extractor so another non-archive source cannot
silently inherit the same literal, is what makes it worth doing properly rather than editing one
string.

**It is not started.** `T-185` owns it, `T-185` is `## Proposed`, and nothing in this handoff
touches `tests/`.

## `ec1308b` — mine, on instruction, and outside your boundary

To close the loop on the unexpected state change you recorded: **that commit is mine.** The
maintainer asked for the Phase 3 roadmap to be updated and I committed and pushed it while your
review was running. It is `ai/roadmap-phase-3.html` plus task bookkeeping — **no `src/`, no
`tests/`, no `pyproject.toml`** — so excluding it from `fb3d274..09c57c3` was correct. It should not
sit in the record as unattributed concurrent work, which is why it is named in `STATUS.md`.

The board has since been updated again for this ratification, in the commit carrying this handoff.

## What changed in this commit

Prose only. `git diff --stat` reaches no source, test or fixture.

| File | Change |
|---|---|
| `ai/DECISIONS.md` | **`OPS-013` added**, Accepted 2026-08-07 |
| `ai/TASKS.md` | `T-107` → `## Complete`, **Approved at `09c57c3`**; its criterion cites `OPS-013`; `## In Review` emptied with a note; `T-185` cites `OPS-013` and names the "none exists" outcome |
| `ai/STATUS.md` | New dated section for the approval; the older paragraph corrected — it had called the amendment a maintainer amendment before it was one, and now says so |
| `ai/evidence/2026-08-07-format-table-vs-yt-dlp-f.md` | Cites `OPS-013` instead of an unattributed "the maintainer", and records that the first version overstated it |
| `ai/roadmap-phase-3.html` | Two of nine deliverables approved, nothing in review, 49 entries closed, exit criterion 1 met and read against `OPS-013` |
| `ai/handoffs/` | This file |

**The earlier handoffs are left as written.** `2026-08-07-corrections-t181-t107.md` still attributes
the amendment as it did on the day, and `09c57c3`'s commit message still says "amended by the
maintainer". Both are published history under `AGENTS.md` §7, and this handoff is the correction
that supersedes them rather than a rewrite that hides them.

## Checks

| Check | Result |
|---|---|
| `tests/unit/test_task_placement.py` | **14 passed** — `T-107` sits under a heading matching its status |
| Closed-entry table vs `ai/TASKS.md` | **49 = 49**, parsed and compared id by id; no duplicates, no ranges miscounted |
| Source, tests, fixtures | **Untouched.** This is a prose commit |

## What I did not do

- **Ratify anything myself.** The finding was about authority; confirming it on the maintainer's
  behalf would have repeated it one level up. The wording came back from them explicitly.
- **Start `T107-R8`.** It is `T-185`'s, and `T-185` is Proposed.
- **Close `T-185`.** The fps search stays open, and now has the fixture-provenance fix in front of
  it.
- **Rewrite the earlier handoff or the commit message**, per §7.
