-- 0011 — when a job's media was published, so a queued download can be named by it (`UX-014`).
--
-- The *Upload date* naming field previews from what the probe learned, and a queued download that is
-- renamed later has only its row to preview from. `MediaInfo.upload_date` would otherwise die with
-- the add dialog, which is `0002`, `0003` and `0010`'s omission a fourth time.
--
-- Nullable, like `uploader`: a site may report no date, and a row written before this ran has none.
-- Forward-only; one `ALTER TABLE ... ADD COLUMN`, which SQLite applies without rewriting the table.

ALTER TABLE jobs ADD COLUMN upload_date TEXT;
