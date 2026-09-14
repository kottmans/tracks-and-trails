-- 0012 — a job's site id, channel and site, so a queued download can be named by them (`UX-014`).
--
-- The *ID*, *Channel* and *Site* naming fields preview a queued download that is renamed later from
-- its row, for `0011`'s reason one set of fields over. All nullable: a site may report none of
-- them, and a row written before this ran has none.
--
-- Forward-only; `ALTER TABLE ... ADD COLUMN` three times, which SQLite applies without a rewrite.

ALTER TABLE jobs ADD COLUMN media_id TEXT;
ALTER TABLE jobs ADD COLUMN channel TEXT;
ALTER TABLE jobs ADD COLUMN site TEXT;
