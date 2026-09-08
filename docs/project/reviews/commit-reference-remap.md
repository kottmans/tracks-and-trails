# commit-reference-remap — Review record

**Purpose:** Dated review evidence and disposition history for this task or shared scope.
**Owner:** Assigned Reviewer · **Update when:** This scope is reviewed or rechecked.
**Covered tasks:** T-033

[Review index](../REVIEWS.md) · [Review policy](../TESTING.md#14-review-policy)

Moved from `85422bc0b086de9b18d2f809abb4d6bcebb180e4:docs/project/REVIEWS.md` on 2026-09-08.
The entries below retain their exact original bytes and relative order. Historical
path spellings, line citations and references to “above” describe that source;
the [migration manifest](../evidence/2026-09-08-review-migration.json) records the
original order and byte ranges. Shared entries are stored once; covered tasks
link to this same record. Navigation grants no approval or new review provenance.

## Recorded rounds

- [2026-07-26 — note: commit SHAs in this file were remapped](#migrated-review-0025)

<a id="migrated-review-0025"></a>
<!-- review-migration:0025:start -->

---

## 2026-07-26 — note: commit SHAs in this file were remapped

**This file is a historical record (`AGENTS.md` §6), so this rewrite is recorded rather than
performed silently.** No finding, verdict, evidence line or date has been altered. Only commit
SHAs changed, and only so they keep pointing at the same commits.

All 80 commit messages were rewritten to the `AGENTS.md` §12 convention at the maintainer's
instruction: subjects shortened to ≤50 characters and stripped of task IDs, which moved into
`Task:`/`Refs:`/`Review:` trailers. Rewriting a message changes its SHA and every descendant's,
so the 112 SHA references across `REVIEWS.md`, `TASKS.md` and `STATUS.md` were remapped to the
rewritten commits.

Verified before and after:

- all 80 trees are byte-identical to the originals — **no file content changed**, only messages;
- all 61 commit references in `ai/*.md` resolve in the rewritten history;
- the 26 remaining hex tokens in this file were never commits on `main` — three are blob IDs a
  reviewer cited, the rest are uncommitted working-tree snapshots — and are deliberately
  untouched;
- CI run numbers (`3020867`, `3021095`, `3021516`, `3021617`) are seven-digit decimals that a
  hex pattern also matches; they were excluded explicitly rather than by luck.

The pre-rewrite history is preserved at tag `pre-message-rewrite-backup` and branch
`backup/pre-message-rewrite` (old head `435d780`, new head `a296615`).

**One consequence worth stating plainly:** the passing CI run for the `T-012`/`T-033` boundary
(run `30226122180`) was recorded against `435d780`, which this rewrite orphans. Its evidence
remains valid and is quoted below, but the run no longer corresponds to a reachable commit.
`T-033`'s outstanding CI work will be re-run against the rewritten head.

### The orphaned run's evidence, preserved

Both frozen jobs passed on `435d780`. Quoted here because the run's own artifacts name a commit
that no longer exists:

| Platform | Probe | Artifact |
|---|---|---|
| ubuntu-latest | `2026.07.04`, pin `2026.7.4`, 1751 extractors, `youtube from yt_dlp.extractor.youtube` | 227348 KiB |
| windows-latest | identical | 136020 KiB |

`T033-R2` is therefore confirmed **in the real frozen artifact**, not only in source: the probe
loaded the concrete extractor module rather than the lazy placeholder, on both platforms.

**A defect in that same evidence step, found while reading it.** The step also prints
`yt_dlp files: 3` / `yt_dlp KiB: 24`. That is misleading: PyInstaller packs pure-Python modules
into the PYZ archive, so a filesystem search finds only the few loose data files and reports 24
KiB for a dependency contributing far more. The artifact total is sound; the yt-dlp subtotal is
not, and must not be quoted as the size delta. Filed as part of `T-033`'s remaining CI work.

<!-- review-migration:0025:end -->
