-- 0008 — the completion ledger's lookup key (`T-170`, `DAT-006`, `REQ-022`).
--
-- **History stops being a product and becomes infrastructure.** `T-169` reconciled the contract:
-- Tracks & Trails is a downloader, not a media-library tracker, so `REQ-020` now keeps the minimum
-- record needed to warn that a URL has been downloaded before. The table keeps its name because
-- renaming it would rewrite it, and rewriting it is the one thing this work must not do.
--
-- **What this adds is a key that can be looked up.** `REQ-022` asks "have I downloaded this
-- before", and answering it from `url` means either an exact string match — which misses the same
-- video pasted with a fragment or a capitalised host — or a scan with normalisation in Python,
-- which is `NFR-001`'s budget spent on every paste. A stored, indexed key is neither.
--
-- **Normalisation is minimal, and `DAT-006` §2 gives the reason.** Lower-case the scheme and host,
-- drop the fragment, and nothing else: the identity of a video lives in the query string on the
-- largest site this serves (`?v=…`), and a rule clever enough to strip tracking parameters per site
-- will one day treat two different downloads as one. A missed duplicate costs a warning that does
-- not appear; a false one warns about the wrong file, and only the second is a lie.
--
-- **The backfill is the upgrade data `T-114` needs.** An installation that has been downloading for
-- months already knows what it has fetched. Computing the key for existing rows is what lets the
-- duplicate warning work on the first run after upgrading, rather than only for downloads made
-- afterwards. It is done in Python by the runner's post-step below, because SQLite has no URL
-- parser and a `lower()`/`instr()` expression that half-parses one is worse than no backfill.
--
-- **Nothing is dropped.** `title`, `output_path`, `format_used`, `bytes_total`, `thumbnail_url`,
-- `playlist_id`, `playlist_index`, `playlist_title` and `format_choice` stop being written and stay
-- where they are (`DAT-006` §5). SQLite implements a column drop as a table rebuild, which is the
-- riskiest possible way to finish a task whose purpose is to *remove* a feature, and the rows those
-- columns belong to are a user's own record of their own downloads.
--
-- Forward-only. One `ALTER TABLE ... ADD COLUMN`, which SQLite applies without rewriting, plus an
-- index. The column is nullable: a row written before this ran has its key computed by the
-- backfill, and a row the backfill could not parse keeps `NULL` and simply never matches, which is
-- the missed-duplicate side of the trade above.

ALTER TABLE history ADD COLUMN normalised_url TEXT;

CREATE INDEX history_normalised_url ON history (normalised_url);
