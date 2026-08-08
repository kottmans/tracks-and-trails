-- 0010 — whether a job is a live stream, so a row can say it cannot be resumed (`T-113`).
--
-- `REQ-017` has two halves and the second one — *state clearly when resumption is not possible* —
-- had nothing to state it from. `MediaInfo.is_live` has existed since `T-016` and died with the
-- add dialog, exactly as `thumbnail_url` did before `0002` and `uploader` before `0003`. This is
-- the same omission a third time, and it is worth naming as a pattern: a field the probe learns
-- and the queue needs has to cross, or the queue cannot draw what the dialog could.
--
-- `NOT NULL DEFAULT 0`, unlike `0002` and `0003`, and the difference is deliberate. Those two are
-- *values* a site may or may not supply, so NULL honestly means "nobody said". This is a claim the
-- application makes about a download, and a row written before this ran had no claim made about
-- it — which is `0`, *this is not known to be live*, and is exactly what the UI should act on.
-- A NULL third state would mean the row says nothing, which is what `0` already means here.
--
-- Forward-only, like every migration before it. One `ALTER TABLE ... ADD COLUMN`, which SQLite
-- applies without rewriting the table.

ALTER TABLE jobs ADD COLUMN is_live INTEGER NOT NULL DEFAULT 0;
