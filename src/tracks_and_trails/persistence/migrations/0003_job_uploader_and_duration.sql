-- 0003 — who published a job and how long it is (`T124-R4`, `UX-005` §3, `REQ-002`).
--
-- `UX-005` §3 names the row anatomy in both tabs as *thumbnail, title, uploader and duration,
-- progress and state*. `Job` carried the first two and nothing else, so `QueueModel` could not
-- render the rest — and `T-124` answered that by weakening its own task text to `REQ-014`'s
-- older field list, which a task may not do to an accepted decision.
--
-- These are exactly `0002`'s case a second time: `MediaInfo` has carried `uploader` and
-- `duration_seconds` since `T-016`, the add dialog draws both while a URL is staged, and both
-- died with the dialog. `UX-003` makes every queued job a probed one, which is what makes the
-- columns worth having — they will be populated for every row rather than for whichever one the
-- user happened to probe.
--
-- Nullable, no default, no backfill, for `0002`'s reason: a row written before this ran was never
-- asked for either, and inventing a value would be a claim no probe made. NULL is honest for both
-- "not probed" and "the extractor named none" — a live stream has no duration and some sites name
-- no uploader — and `status` is what tells those apart.
--
-- `duration_seconds` is REAL: yt-dlp reports fractional durations, and rounding at the storage
-- layer would make the queue and the add dialog disagree about the same clip by up to a second.
--
-- Forward-only, like `0001` and `0002`. Two `ALTER TABLE ... ADD COLUMN` statements, which SQLite
-- applies without rewriting the table, so this stays cheap on a long queue.

ALTER TABLE jobs ADD COLUMN uploader TEXT;
ALTER TABLE jobs ADD COLUMN duration_seconds REAL;
