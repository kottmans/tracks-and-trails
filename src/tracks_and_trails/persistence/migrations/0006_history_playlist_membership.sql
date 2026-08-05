-- 0006 — which playlist a completed download came from (`T-145`, `UX-005` amended 2026-08-05).
--
-- A playlist downloads as one queue row that opens into its entries (`UX-005` row 9) and then
-- became **sixteen unrelated rows in History** — the fact that they arrived together, which the
-- queue took trouble to show, lost at exactly the point History becomes the only record.
--
-- This is `0004`'s three columns again, one table over, and `0005`'s case for the third time: the
-- data was known while the job existed and had nowhere to live afterwards. `0004` put the
-- membership on `jobs`, where it dies with the job — `T-081`'s clear-finished is enough to take it
-- — so a history row has to carry its own, exactly as `0005` reasoned for the thumbnail.
--
-- **No `playlists` table, and no original-count column**, per the same amendment. A group's
-- header is a count of the members present (`14 items`, never `14 of 16`): History holds only
-- completed downloads, so a denominator counts rows it cannot describe, and `DAT-005` makes
-- records removable one at a time — a stored count would be wrong about both numbers after the
-- first removal. A count derived from what is there cannot drift from it, which is `0004`'s
-- reasoning for having no table.
--
-- Nullable with no default and no backfill, for `0002` through `0005`'s reason: a record written
-- before this ran never had a membership written down. It renders **ungrouped**, and is not
-- re-grouped by inferring one from titles or paths — that would present a guess as a record, which
-- is the one thing `REQ-020` cannot do. The three are all-or-nothing and `HistoryEntry.__post_init__`
-- refuses a partial set, mirroring `Job`'s rule.
--
-- `playlist_index` is the entry's position **as the playlist reported it**, carried across from the
-- job unchanged, so a group opens in the playlist's own order rather than in completion order —
-- track 03 stays above track 04 however the downloads interleaved.
--
-- Forward-only, like `0001` through `0005`. Three `ALTER TABLE ... ADD COLUMN` statements, which
-- SQLite applies without rewriting the table.

ALTER TABLE history ADD COLUMN playlist_id TEXT;
ALTER TABLE history ADD COLUMN playlist_index INTEGER;
ALTER TABLE history ADD COLUMN playlist_title TEXT;
