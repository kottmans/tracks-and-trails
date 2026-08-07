# Review handoff — three verdicts taken, and a roadmap the maintainer added, 2026-08-07

**From:** Claude Code (Implementer, and Planner for the second half)
**To:** Codex (Reviewer)
**Follows:** the three **2026-08-07** records in `ai/REVIEWS.md` — `T-105` at `a688a4e`
(*Changes requested*), `T-168` at `3859190` (*Changes requested*), `T-179` at `1e0d0d5`
(*Approved with follow-ups*)
**Review base:** `1e0d0d5` — the head all three records were written against
**Review head:** **uncommitted working tree.** Nothing has been committed or pushed; the maintainer
has not asked for a commit.
**Branch:** `main`. Serial mode, no wave.

**This handoff covers two things that arrived in one session and must be reviewed as two.**

1. **The finding corrections** — `T105-R1`, `T105-R2`, `T105-R4`, `T168-R1`, and `T179-R3` placed
   on its follow-up. One test file changed; everything else is coordination documents.
2. **A roadmap change the maintainer directed** on 2026-08-07, before your records arrived: the
   queue is stopped until started (`UX-006`), and option coverage becomes a phase (`ARC-010`,
   `REQ-030`, `REQ-031`). **No source. Nothing implemented.**

They are separable and I have kept them separable: **the only overlap is `docs/UX_SPEC.md`**, which
the roadmap work amended while `T-105` was mid-cycle. That overlap is real and §"What to look at
first" below is where it is.

---

## 1 · The corrections

### `T105-R1` (High) — the settled preset store, in the documents an implementer opens

Your finding is exact: the spec was right and the two current-truth documents were not.

- **`ai/TASKS.md` `T-111`.** *Affected surfaces* said "`core/settings.py` **or a new store**" — the
  "or" is gone. The Scope paragraph that said where presets live "is a decision this task must take
  or raise", and argued for a sibling file, is replaced by the settled boundary: **TOML in the
  existing `settings.toml`**, per `DAT-001` and `ARCHITECTURE.md` §5, no new store, no migration
  owed. The superseded wording is preserved in place, as this project does everywhere.
- **`ai/IMPLEMENTATION_PLAN.md`**, Phase 3 deliverables. The `T-111` row's risk read "where it
  lives needs a decision"; it now states the decision and notes that it predates the row.

### `T105-R2` (Medium) — `T-061` stated the way it actually failed

`T-108` carried the rejected reading in **three** places, not the one your finding cites: the
context line, the Scope paragraph, and an acceptance criterion asking for a pair "a selector-only
check would wrongly approve".

The Scope now separates the two questions the way `docs/UX_SPEC.md` §5 does — the table's explicit
pair states a merge and parses no selector; the worker's gate is definitive and reads
`requested_formats`, consulting the selector only when resolution supplied no answer — and states
`T-061`'s measured direction plainly: `bestvideo+bestaudio/best` against a source offering one
progressive format resolved through `/best` to no merge, and the selector-reading gate **refused
it anyway**.

The criteria now assert **both directions**, which is the part I want you to check hardest:

- with ffmpeg absent, an explicitly chosen video + audio pair is refused before the download starts;
- with ffmpeg absent, a `+` selector that **resolved to a single progressive format is not
  refused**.

A selector-only check passes the first and fails the second. That is the property the old single
criterion could not express, and it is why I wrote two rather than reversing one.

### `T105-R4` (Medium) — a proposal is not an acceptance criterion

- **`T-112`**: "An invalid template is reported as the user types" was `P-23` as a requirement. The
  criterion is now that an invalid template never reaches a download, with the *timing* named as
  unruled and the task barred from being started against either.
- **`T-114`**: your finding names the context field. **The same choice was also an acceptance
  criterion** — "in the row's own state rather than a modal" — which is the half that would have
  been built. Both are corrected: the requirement is that the user is told in time to act; which
  surface tells them is `P-26`.

**Sibling audit, since this is a class rather than two entries.** I checked `T-107`, `T-109`,
`T-110` and `T-113` for the same shape. `T-107` and `T-110` already mark their open questions and
derive their criteria from the requirement — no change. `T-109` and `T-113` had context lines
updated, but for the 2026-08-07 rulings rather than for this finding (`P-12` is now ruled by
`ARC-010`; `UX-001` is amended by `UX-006`). Those two edits belong to part 2 and I have said so in
the entries.

### `T168-R1` (Medium) — the gate now proves what it claims

`ui/row_delegate.py` is **unchanged**. You accepted the formula and the finding was against the
regression, which fixed the count at sixteen while the criterion says *any entry count*.

`test_a_verb_dropped_at_one_width_never_returns_at_a_narrower_one` is parameterized over
`RESERVE_COUNTS = (5, 8, 9, 16, 24, 37)` — both sides of `MERGED_BLOCKS`, four distinct merge
thresholds above it (`segment_span` is `17n − 1`, so 152 px at nine, 271 at sixteen, 407 at
twenty-four, 628 at thirty-seven). It keeps the per-pixel downward sweep and the non-vacuity
assertion, and gains a per-count assertion on which renderings that count's sweep actually
produced: `{MERGED_BLOCKS, entries}` above the threshold, `{entries}` at or below it. A count whose
threshold drifts outside `SWEEP_WIDTHS` now fails loudly instead of passing vacuously — sixty is
excluded for exactly that reason and the constant says so.

`bar_runs_in()` is split out of `bar_runs()` so the sweep asks both questions of the paint it
already does. Repainting to count blocks would double the sweep and measure a *second* paint, and
the delegate records what it dropped on the last one.

**Mutation results, measured, and the honest part first:**

| Mutant | Result |
|---|---|
| `keep = segment_span(segment_blocks(entries, room))` restored everywhere | **fails at 16, 24, 37**; passes at 5, 8, 9 |
| the same restored everywhere **except** sixteen — the count-specific form your finding names | **fails at 24, 37**; passes at 5, 8, 9, 16 |

**Nine kills neither, and I have left it in with the reason written down rather than quietly
swapping it out.** Its step is `segment_span(9) − segment_span(8)` = 17 px and no verb is that
narrow, so just above the threshold the rejected reserve is harmless. **24 and 37 are the counts
that kill the mutants.** I think that is worth a moment of your review: a parameterized test whose
parameters have not been mutation-checked individually can look broader than it is, and this one
would have read as six independent proofs when it is two.

### `T179-R3` (Low) — placed, not fixed

Assigned to `T-180` as an acceptance criterion: whichever way the per-machine/per-database decision
goes, `cache_generation()`'s "one sweep's delay" is rewritten to the precise trigger the task record
already uses — *until this one's own membership changes* — or removed with the risk. `T-179` is
approved at `1e0d0d5` and I have not touched its source, which would have created a new
implementation head for an approved task.

### Task and status moves you left to me

- `T-179` → `## Complete`, **Approved with follow-ups at `1e0d0d5`**, with `T179-R1` recorded as
  *dispositioned rather than fixed* and `T179-R3` noted as open against `T-180`.
- `T-168` and `T-105` → `## In Review`, both **Changes requested … corrected, awaiting
  re-review**. They were sitting in `## Complete` as *awaiting review*; each now carries its
  correction record at the bottom of the entry.
- The `## In Review` section note rewritten — it claimed `T-179` was the one thing awaiting a
  verdict.
- `ai/STATUS.md`: the "two tasks never reviewed" and "third mechanism, awaiting re-review"
  paragraphs corrected, and a block added for the three verdicts.

---

## 2 · The roadmap change (maintainer, 2026-08-07)

**Planning only. No source, no tests, nothing implemented.** Two decisions, both taken by the
maintainer from my recommendation, and both recorded with tasks against them.

**`UX-006` — the queue is stopped until it is started.** Adding a URL enqueues it and starts
nothing; the user reviews the batch and presses `Start`; a started queue keeps running until
`Stop`. **Stopped at every launch**, so restoring a queue no longer resumes downloading on its own.
`UX-001`'s drain is kept **unchanged** — this moves the default, not the semantics, which is why it
needs no new mechanism: `T-080` built the gate and `T080-R1` already made it park a download and
admit a probe. `T-181` implements it, in Phase 3. Reaches `REQ-015`, `REQUIREMENTS.md` §11
criterion 1 (which now contains the `Start` press — without it the criterion is satisfied by a
build that downloads nothing), and `docs/UX_SPEC.md` §2 and §2.1.

**`ARC-010` — option coverage is typed fields plus one validated escape hatch.** `REQ-030` sets the
target as **capability** parity rather than flag count; `REQ-031` adds *additional yt-dlp options*,
parsed and validated against containment (`T-034`), redaction (`DAT-003`/`DAT-004`) and an
application-owned refusal list, never passed through. **New `Phase 4.5 — Option coverage`**, between
Phase 4 and Distribution; Distribution is deliberately **not** renumbered, because "Phase 5" names
it in five documents and every review record citing it. Three tasks: `T-182` (the `REQ-EXCL`
ruling, the maintainer's), `T-183` (the audit that decomposes the phase), `T-184` (the hatch).

**Two consequences that touch your open findings, so they are not a surprise later:**

- **`ARC-010` rules `P-12`** — the five undedicated post-processing options get typed fields and the
  model widens — and **narrows `P-18`**. Both are marked in `docs/UX_SPEC.md` §6 and §10, and
  `T-109`'s context line no longer says `P-12` must be ruled first.
- **`UX-006` does *not* rule `P-10`.** Per-job pause is untouched and still arrives with `T-113`
  and resume. §10's summary now says so explicitly, because a reader could reasonably assume
  otherwise.

**`T-182` is the one I would flag.** Six option families point opposite a written constraint —
site credentials against `REQ-EXCL-003`, `--impersonate` against `-005`, `--xff` against `-002`,
`--exec` against containment, `--download-archive` against the record-keeping withdrawn on
2026-08-06, and **SponsorBlock against `NFR-007`**, whose outbound-traffic promise those options
would widen. It is filed as a decision task with nothing proposed, and it blocks the parts of Phase
4.5 that touch those families.

---

## What to look at first

**The one place the two halves overlap is `docs/UX_SPEC.md`.** The roadmap work amended §2, §2.1,
§6 and two §10 rows while `T-105` was mid-correction-cycle. Those edits are **`UX-006`/`ARC-010`
transcription, not `T-105` corrections** — none of the three open `T-105` findings is in that file,
and the `T-105` correction batch changes `ai/TASKS.md` and `ai/IMPLEMENTATION_PLAN.md` only. If you
would rather review the `T-105` corrections against an unamended spec, the roadmap edits to that
file are separable and I can lift them out.

Second: **the two-direction `T-108` criteria**. If a selector-only check can pass both, the
correction has not landed and I would rather find that now.

---

## Report

**1 · What changed.** Five findings taken (`T105-R1`, `T105-R2`, `T105-R4`, `T168-R1`, `T179-R3`),
three task entries moved between sections with their statuses corrected, and a maintainer-directed
roadmap change recorded as two decisions, two requirements, one new phase and four new tasks.

**2 · Files modified.**

| File | Why |
|---|---|
| `tests/ui/test_row_delegate.py` | `T168-R1`: `RESERVE_COUNTS`, the parameterized sweep, `bar_runs_in()` |
| `ai/TASKS.md` | `T105-R1/R2/R4` corrections; `T-168`/`T-105`/`T-179` moves, statuses and correction records; `T179-R3` on `T-180`; `T-181`–`T-184` filed; `T-109`/`T-113` context lines |
| `ai/IMPLEMENTATION_PLAN.md` | `T105-R1`'s Phase 3 row; Phase 4.5; `T-181`'s deliverable row; two phase risks |
| `ai/DECISIONS.md` | `UX-006`, `ARC-010`, and the `UX-001` amendment note |
| `ai/REQUIREMENTS.md` | `REQ-015` amended; `REQ-030`/`REQ-031`; §7; §11 criterion 1 |
| `docs/UX_SPEC.md` | `UX-006` and `ARC-010` transcription: §2, §2.1, §6, §10 |
| `ai/STATUS.md` | the three verdicts, the rulings, and two stale paragraphs |

**`src/` is untouched.** The `T168-R1` mutants were applied to `ui/row_delegate.py` and reverted;
`git status` shows it clean.

**3 · Checks run, and their actual results.**

| Check | Result |
|---|---|
| `pytest tests/ui/test_row_delegate.py tests/unit/test_task_placement.py tests/ui/test_queue_view.py` | **150 passed** in 9.68 s (was 145 — the sweep is now six cases) |
| Mutant 1 — old reserve restored everywhere | **3 failed** (16, 24, 37), 3 passed |
| Mutant 2 — old reserve restored except at sixteen | **2 failed** (24, 37), 4 passed |
| `ruff check .` | **All checks passed** |
| `ruff format --check .` | **184 files already formatted** |
| `mypy src` | **Success, 44 source files** |
| `mypy --platform win32 src` | **Success, 44 source files** |

Both mypy runs used `.venv/bin/python -m mypy`; the `.venv/bin/mypy` launcher's shebang is stale,
as you found.

**4 · Assumptions.**

- That the `T-105` correction belongs in the task entries rather than in `docs/UX_SPEC.md` — your
  findings name `ai/TASKS.md` and `ai/IMPLEMENTATION_PLAN.md` line numbers, and the spec is
  correct as it stands.
- That `T179-R3` is discharged by placing it on `T-180` rather than by editing an approved task's
  source.
- That moving `T-168`/`T-105` out of `## Complete` is mine to do, since you left task and status
  moves untouched.

**5 · Remaining risks and known-unverified areas.**

- **Windows is unverified for the test change**, as ever; the sweep is font-metric dependent and
  `RESERVE_COUNTS`' threshold assertions could in principle behave differently there. The
  assertion is on shape rather than on any width's value, which is what should carry it across.
- **Nine kills neither mutant.** Documented, deliberate, and the counts that do the work are 24
  and 37.
- The roadmap half has had **no review at all** — it is decisions and plans, and `T-182`'s ruling
  is outstanding by design.

**6 · Blockers and follow-up work.** `T179-R3` is open against `T-180`. `T-182` blocks part of
Phase 4.5 and needs the maintainer, not an implementer. Nothing blocks this correction batch.

**7 · Ready for review.** Yes, as a **bounded uncommitted diff** against `1e0d0d5`: the eight files
above, with `src/` clean. `git diff --check` passes.

**8 · Coordination files updated.** `ai/TASKS.md`, `ai/STATUS.md`, `ai/IMPLEMENTATION_PLAN.md`,
`ai/REQUIREMENTS.md`, `ai/DECISIONS.md`, `docs/UX_SPEC.md`. **`ai/REVIEWS.md` was not touched** —
your three records are as you wrote them.

---

# Addendum — the authorized pass on `T105-R4`, 2026-08-07

**Follows:** *2026-08-07 — `T-105` / `T-168` correction re-review and `T179-R3` placement*
(`ai/REVIEWS.md`) — **`T-168` Approved, `T-105` Blocked**
**Review base:** unchanged, `1e0d0d5`
**Review head:** still the uncommitted working tree. Nothing committed or pushed.
**Authorization:** the maintainer chose `AGENTS.md` §10's *authorize one more narrowly focused
pass*, on 2026-08-07, for the one sentence below.

## The finding, and why it survived

You were right and the miss is a plain one. `T-112`'s **acceptance criterion** was corrected to say
that an invalid template must never reach a download and that the timing is unruled; its **Relevant
context**, three lines above, still said *"`P-23` is this task's own report-as-you-type criterion"*.

**That is `T105-R4`'s own defect class committed inside `T105-R4`'s correction.** The finding is
about an unratified proposal stated as task truth. I removed it from the criterion — where it
would be *built* — and left it in the field an implementer reads *first*.

The part I want on the record, because it is more useful than the edit: **the first batch did run a
sibling audit, across `T-107`, `T-109`, `T-110` and `T-113`, and it was pointed outward at the
class rather than at the entry under the hand.** `T-114` got both of its occurrences corrected
because your finding named one and I looked for the other; `T-112` got one because your finding
named one and I stopped. An audit of four neighbours is not a substitute for reading the two fields
of the thing being edited.

## What changed

One sentence, in `ai/TASKS.md`, in `T-112`'s **Relevant context**:

> `P-23` — whether a containment failure is refused at edit time or at commit — is unruled with
> `P-22`; one ruling covers both, and until it is taken this task chooses neither.

with the superseded wording preserved in place as a parenthetical, as everywhere else in this file.
**No source, no test, no acceptance criterion, no other entry.**

## Bookkeeping taken with it

- **`T-168` → `## Complete`, Approved 2026-08-07**, `T168-R1` Resolved, noting that you reproduced
  both mutants independently and reached the same 3/3 and 2/4 splits.
- **`T-105` stays `## In Review`**, its status recording the Blocked→authorized sequence, with a
  second correction record in the entry.
- The `## In Review` note and `ai/STATUS.md`'s review block updated: one task awaits a verdict now,
  not two.

## Checks

| Check | Result |
|---|---|
| `pytest tests/unit/test_task_placement.py` | **14 passed** |
| `pytest tests/ui/test_row_delegate.py tests/unit/test_task_placement.py tests/ui/test_queue_view.py` | **150 passed** |
| `ruff check .` / `ruff format --check .` | **pass** / **185 files already formatted** |
| `mypy src` / `mypy --platform win32 src` | **Success, 44 source files** each |
| `git diff --check` | **pass** |
| Task entry count, before and after the `T-168` move | **182 = 182**, same entry set |

Nothing in `src/` or `tests/` changed in this pass; the suites are re-run to prove that rather than
to prove anything new.

*(The formatter's file count moved 184 → 185 between the first batch and this one, and it is not a
stray file in the tree: this ruff configuration counts `ai/` and `docs/` as well as `src/`, `tests/`
and `tools/`, so the handoff you are reading is the 185th. Your own run reported 185 for the same
reason. `git ls-files '*.py'` is 124 and there is no untracked Python anywhere outside `.venv`.)*

## Ready for review

Yes — bounded to the single `T-112` context hunk in `ai/TASKS.md`, plus the `T-168`/`T-105` status
and section bookkeeping above. The `UX-006`/`ARC-010` roadmap work in the same tree is unchanged
since your last boundary and remains excluded.

---

# Close-out — `T-105` Approved, 2026-08-07

**Verdict taken:** *2026-08-07 — `T-105` maintainer-authorized final focused re-review*
(`ai/REVIEWS.md`) — **Approved in the bounded working tree**, `T105-R4` Resolved.

**The bookkeeping the approval implied, now applied:**

- `T-105` → `## Complete`, **Approved 2026-08-07**, all four findings Resolved, with the three
  correction rounds and the Blocked→authorized sequence recorded in its status.
- The `## In Review` note rewritten. **The section is empty**, and the note says so with the three
  tasks that left it and where each went — deliberately, because *"nothing awaits a verdict"* is the
  sentence in this file with the worst track record (`COORD-R11`, `COORD-R15`), and an empty
  section that claims nothing is different from one that claims to be current.
- `ai/STATUS.md` updated: both tasks approved, every outstanding boundary closed, and what is
  actually open now — `T-180` carrying `T179-R3`, `T-176`, and the four roadmap tasks.

**Checks after the move:** task placement **14 passed**; task entry count **182**, and the entry
set is **identical** to the pre-move backup — the three section moves in this session moved entries
without editing or losing one. `git diff --check` **pass**. No source, test, requirement or
decision changed in this step.

**What is left in the tree, and what it needs.** The `UX-006`/`ARC-010` roadmap work — two
decisions, two requirements, `Phase 4.5`, `T-181`–`T-184`, and the `docs/UX_SPEC.md` transcription
— has been excluded from every boundary in this sequence, correctly, and **has therefore had no
review at all**. It is planning rather than implementation, so that may be the right resting place;
if a review is wanted it is its own boundary, not a continuation of these.

**Nothing is committed or pushed**, in line with `AGENTS.md` §7 and the maintainer not having asked
for it.
