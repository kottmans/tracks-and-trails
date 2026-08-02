-- 0002 — where a job's thumbnail lives (`T-117`, `REQ-002`, `UX-003`).
--
-- `MediaInfo` has carried a thumbnail URL since `T-016`, but nothing stored it, so the address
-- died with the dialog that probed for it and a queued row could never show a picture. `UX-003`
-- makes every queued job a probed one, which is what makes a column worth having: it will be
-- populated for every row rather than for whichever one the user happened to probe.
--
-- **The first migration after the initial schema.** `migrate()` has never had a second script to
-- run against a database that already holds rows, so this exercises the path as much as it adds
-- the column. Nullable with no default and no backfill: rows written before this ran were never
-- asked for a thumbnail, and inventing one would be a claim the probe never made. NULL is the
-- honest value for both "not probed" and "the site offered none" — `status` is what distinguishes
-- them, and neither is an error.
--
-- Forward-only, like `0001`. `ALTER TABLE ... ADD COLUMN` is the one shape SQLite has always
-- supported without rewriting the table, so this is cheap on a large queue.

ALTER TABLE jobs ADD COLUMN thumbnail_url TEXT;
