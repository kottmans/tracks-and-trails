-- 0004 — which playlist a job came from, and where it sat in it (`T-137`, `UX-005` row 9).
--
-- `UX-005`'s second 2026-08-04 amendment makes a pasted playlist **one queue row that opens into
-- its entries**. The entries are ordinary jobs — that is the whole point of the shape, and why
-- the downloader needs no change for it — so what has to be durable is only which group each one
-- belongs to and in what order.
--
-- **No `playlists` table, deliberately.** A group has no state of its own: row 9a makes its chip a
-- count of its members and row 9b makes its bar their states, so everything a group row shows is
-- derived from the jobs below it. A table would be a second home for a title with nothing else in
-- it, and the group would acquire a lifecycle nothing needs — created before its first entry,
-- deleted after its last, and wrong in between. Three columns here say the same thing and cannot
-- drift from it. The cost is a repeated title per entry, which `REQ-020` already pays for `url`.
--
-- Nullable with no default and no backfill, for `0002` and `0003`'s reason: every row written
-- before this ran was pasted directly, and `NULL` says exactly that. The three are all-or-nothing
-- and `Job.__post_init__` refuses a partial set — a job with an index and no id belongs to no
-- group, and one with an id and no index cannot be ordered within it.
--
-- `playlist_index` is the entry's position **as the playlist reported it**, not its queue
-- position: the queue reorders and `queue_position` already carries that. Ordering entries by
-- what the site said is what keeps track 03 above track 04 after a user drags something.
--
-- Forward-only, like `0001` through `0003`. Three `ALTER TABLE ... ADD COLUMN` statements, which
-- SQLite applies without rewriting the table.

ALTER TABLE jobs ADD COLUMN playlist_id TEXT;
ALTER TABLE jobs ADD COLUMN playlist_index INTEGER;
ALTER TABLE jobs ADD COLUMN playlist_title TEXT;
