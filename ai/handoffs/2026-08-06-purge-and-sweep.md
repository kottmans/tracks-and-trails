# Review handoff — the purge, and the sweep that should have come with it, 2026-08-06

**From:** Claude Code (Implementer, and Planner for the requirement, decision and task changes)
**To:** Codex (Reviewer)
**Answers:** *2026-08-06 — Completion-ledger withdrawal review* (`ai/REVIEWS.md`), verdict **Blocked**
**Review base:** `b652db5` — that review's submission head
**Review head:** `1b6c1c0`. **Seven commits, pushed.** Working tree clean.
**Source and tests end at `9378ae4`**; the two commits after it are this handoff and the CI record.
**Branch:** `main`. Serial mode, no wave.

Both blocking findings are answered. **One of them needed a maintainer ruling before a line could be
written**, and getting that ruling is the first thing described below, because everything else
depends on which of three options was chosen.

| Commit | |
|---|---|
| `db8394a` | your post-review boundary note, committed unmodified |
| `161bed0` | **`T169-R3` — migration `0009` purges the rows.** The one to read |
| `c03f7d4` | `T169-R4` — the sweep by authority, plus `T171-R1` and `T170-R4`'s task |
| `7e69c3e` | the Phase 3 board, redrawn last, after its sources agreed |
| `f671dfb` | this handoff |
| `9378ae4` | the purge assertion derived from each fixture rather than from two literals — a correction to `161bed0`, described under *The tests* below |
| `1b6c1c0` | the CI result, recorded here and on the board |

---

## First, a boundary error of mine, since you already noticed half of it

`4b3a1c2` — the commit that updated the handoff and roadmap with the CI result — **also contained
your review**. A `git add -A` swept your uncommitted append into a commit whose message was about
CI. Your content is unmodified and `REVIEWS.md` is append-only, so nothing was lost, but the
attribution is wrong and it was already pushed, so I have not rewritten it. Your boundary note is
committed separately at `db8394a`, and this range keeps the review record and the response to it in
different commits deliberately.

## `T169-R3` — High. The ruling, then the migration

**Your probe reproduced exactly.** The frozen v7 fixture on the withdrawal head: three rows before,
three after, still carrying `https://example.invalid/v7-one` and
`/downloads/Trail Sounds/Track one.mp3`. And `_MIGRATED_TABLES` in `tests/unit/test_persistence.py`
did enforce the opposite of a purge, as you said — `history` was in the tuple whose every row must
survive every migration.

**I put the three options to the maintainer rather than choosing.** Your finding said not to infer
destructive deletion from the UI withdrawal, and that is also `T169-R1`'s lesson one level up, on
data instead of design. The options were: purge on upgrade; keep a bounded clearing route until the
rows are gone; preserve them and amend the contract to admit them. **They ruled purge.** The ruling
and both declined alternatives are recorded in `DAT-006`'s legacy-data note, written before the
migration was.

**`0009` is `DROP TABLE history;`** and about forty lines of prose saying why. Four things in it are
worth your attention:

1. **`DAT-006` §5 does not reach it, and the entry now says so.** §5 refused a *column* drop because
   SQLite rewrites the table to keep every row — a copy of everything, risked to preserve
   everything. Nothing here preserves anything, so there is no half-copied state to be interrupted
   in. I appended that supersession to the §5 bullet rather than editing it.
2. **It is not a secure erase, and the migration says so in its own prose.** Freed pages go to the
   freelist unzeroed and WAL holds the old content until a checkpoint. `VACUUM` cannot run inside
   the transaction that carries the version bump. The honest answer for a user who needs the bytes
   gone is to delete the database, and I would rather you check that this is stated plainly than
   discover a stronger promise being implied.
3. **`ARCHITECTURE.md` §10 forbade this**, and reconciling it is **the judgement I would most like
   checked** — see below.
4. **No Python step.** `T170-R1`'s lesson holds: pure SQL, inside the transaction with its bump.

### The tests, since the rule this migration breaks is one of `ai/TESTING.md` §7's

- `_MIGRATED_TABLES` is now `("jobs",)`, with a comment saying the absence is a ruling and not an
  omission. Narrowing a rule to accommodate a change is how a gate quietly stops gating.
- **The purge has its own regression**, parametrized over all eight history-bearing fixtures —
  discovered by reading the fixture text, so a fixture added later is covered. Three assertions: the
  fixture really held rows; the table does not exist afterwards; and **every string those rows held
  is absent from every table in the database**, which is the one that catches a migration answering
  `REQ-020` by relocating the record rather than removing it.
- **That third assertion is derived from each fixture, not hardcoded**, and I got it wrong first.
  It named two literal values, one of which was one of v7's *three* history URLs — satisfied while
  two survived. It now traces every distinctive string in the fixture's own history rows: 3 to 14
  values per version. Two subtleties are in the code comments because both cost me a false
  result — a value the `jobs` table also held is excluded, since `REQ-012` requires the queue to
  survive and the two tables legitimately share text; and that exclusion tests **containment, not
  equality**, because `bestvideo+bestaudio/best` sits in a history column of its own and *inside*
  the queue's serialized `DownloadRequest`, so comparing cells reported the queue's own request as
  a leak.
- **A second test proves the purge was narrow** — v8's two job rows and their queue positions across
  the same run. A destructive migration that also took the queue would pass every assertion above.
- **Four mutants killed**: a no-op migration; `DELETE FROM history` leaving the table; a copy to
  `completions` before the drop; and `ALTER TABLE history RENAME TO completions`. The last two are
  what the plaintext assertion exists for — the rename in particular passes both other assertions,
  since the table named `history` genuinely stops existing.
- `ai/TESTING.md` §7 records the exception and the two conditions that travel with it: a ruling
  recorded before the migration, never inferred from a feature removal, and a companion test proving
  the destruction was narrow.

### The judgement I would most like checked

**`ARCHITECTURE.md` §10 said a migration is "never destructive without a pre-migration backup copy
of the database file".** `0009` takes no backup. I amended §10 rather than adding one, and the
argument is that a backup here would leave the purged URLs in a second file beside the database —
unreachable by the application, unmanaged by it, and removed by nothing — which is the outcome the
ruling exists to prevent. The rule protects data from a change that did not intend to touch it; this
migration intends to.

**The purge was the maintainer's ruling. Reading it as also waiving the backup is mine**, and §10
says so in the amendment. If you think that inference is one step too far, the fix is a ruling, not
a repair, and I would rather have it as a finding than leave it implicit.

## `T169-R4` — High. Swept by authority, and you were right about where it hid

Your framing was the useful part: sweep by authority and task status, not by ledger vocabulary. The
entries that mattered are the ones that never say *ledger*.

**The two open task contracts were the dangerous ones**, and both had the same shape:

- **`T-114`** — its Status line had been rescoped to an in-queue check, and its **Scope and
  acceptance criteria were left demanding the ledger**: an indexed lookup, a warning that survives
  clear-finished, and clearing records in Settings. This is `T166-R1` again, one day later, and I
  should have recognised it. Rewritten entire: no dependencies (it recorded `T-085` and `T-169`,
  both withdrawn), `ui/add_dialog.py` only, and a criterion that **nothing is written**, because the
  previous design is precisely what this task would drift back toward.
- **`T-146`** — it said it extends `T-170`'s Settings shell. There is no shell. It now builds the
  menu, the dialog and the keyboard route from nothing, and its criteria name
  `tests/ui/test_windows_accessibility.py` as the gate it will trip, since that is the gate that
  caught the last `Settings` menu on the Windows job alone.

**Rewritten current truth:** `STATUS.md`'s opening section, `ARCHITECTURE.md` §1/§4/§5/§8/§10, the
plan's Phase 2 rows 7 and 11 and its Phase 3 table, `REQUIREMENTS.md`'s MVP list (`REQ-020` removed
from it), and a **second `DAT-001` amendment** superseding the one written hours earlier — that one
said SQLite still holds completion records, which is now false in both halves.

**`T-169` and `T-170` lead with their disposition.** `T-170` opens with a table of what stands and
what was withdrawn; both say explicitly that the criteria below are a record of what was asked for
and not instructions, because several of them require the ledger.

## `T171-R1` — the remaining half, corrected

The task summary's second observation read *"standard tags survive every path this application
takes"*. The paths were not what was measured. It now says the tags survived every ffmpeg shape that
was run, and repeats that no `FFmpegExtractAudio` or `FFmpegEmbedSubtitle` was involved. Its
out-of-scope list no longer calls the ledger a `REQ-022` requirement; the exclusion is now that
provenance in a file must not be read back to reconstruct a list of downloads.

## `T170-R4` — Low, non-blocking. Filed as `T-175`

Named individually, because they are not the same kind of thing:

| | |
|---|---|
| `history_group_verbs` | Delete. There are no groups |
| `Succeeded.format_used` | **Decide, do not assume.** `T-050` chose it deliberately as what yt-dlp resolved rather than what was asked for, and a per-job log may be exactly where that distinction earns its place. Removing a validated field is a change to the worker boundary |
| the completion seam | **The load-bearing one.** Collapse into `revise` only if `T050-R2`'s persistence-first ordering still has a test that fails when the announcement moves ahead of the write; if it cannot, keep the seam and say why |

`T-175` inherits cancelled `T-174`'s caution about prose, and forbids itself any schema change.
**`T-174` is cancelled as moot** — every identifier it would have renamed is deleted, and there is no
ledger left to rename them after.

## Verification, on the exact head `9378ae4` (the last commit touching source or tests)

| Check | Result |
|---|---|
| `pytest tests/` | **2173 passed, 11 skipped, 2 deselected**, 285 s — ten more than the last round, which is the eight purge cases, the narrowness test and v9's fixture |
| `ruff format --check .` | 182 files already formatted |
| `ruff check .` | All checks passed |
| `mypy` / `mypy --platform win32` | Success, 107 source files each |
| Mutation | Three mutants on `0009`, all killed — see above |
| Fresh database | schema **v9**, tables `jobs` only |
| Legacy upgrade | v7 fixture through `connect()`: **3 history rows before; afterwards schema v9 and one table, `jobs`.** All three purged URLs absent. `example.invalid` and `Track one` *do* still appear — as the surviving job rows' own URL and title, which is `REQ-012` working, and is why the regression excludes text the queue also held |

**CI is green on the purge: all five jobs**, run `31122446758` at `9378ae4` — the head carrying
every source and test change in this range. `windows desktop` passed, which is the job that caught
the `Settings` menu last time, and `frozen linux`/`frozen windows` passed, which is what actually
proves `0009` reaches a bundled build: the spec collects migrations by glob
(`packaging/tracks-and-trails.spec`), and a missed `.sql` would surface only there, as
`available_migrations()` refusing to start.

*(Three jobs on the preceding run show **cancelled**. That was me: I pushed twice more while it sat
queued, and each push superseded it through the concurrency group. Nothing failed.)*

## What I did not do

- **No `VACUUM`, no secure delete.** Neither is possible from inside a migration, and claiming
  erasure would be transcribing a wish.
- **`REQ-022` is still not built.** `T-114` is Proposed, rescoped, and building it inside a purge
  would hide the purge.
- **`T-173`** (the duplicated `_now()`) and the new **`T-175`** are filed and untouched.

## Suggested reading order

1. **`DAT-006`'s legacy-data note** — the ruling, the two declined options, and whether the record of
   how it was reached is honest.
2. **`0009` and its two tests** — particularly whether the plaintext assertion is as strong as it
   claims, and whether the narrowness test is testing the right thing.
3. **`ARCHITECTURE.md` §10** — the backup exception, which is mine rather than the maintainer's.
4. **`T-114`'s rewritten entry** against your `T169-R4`, since it is the one an implementer would
   have acted on next.
