-- A database as version 4 actually wrote it, frozen 2026-08-04 while v4 was current.
-- T014-R4: the migration test must migrate historical BYTES, not rows that the current
-- model and serializer produced. Never regenerate this from current code -- that would
-- restore exactly the defect it exists to catch. A future version writes its own file.
--
-- v4 added `jobs.playlist_id`, `jobs.playlist_index` and `jobs.playlist_title` (`T-137`,
-- `UX-005` row 9). All three states of the trio are seeded, because a migration touching any of
-- them has to preserve every one:
--
--   * `v4-entry-1` -- a playlist member at index 0, still queued, carrying uploader and duration.
--   * `v4-entry-2` -- a member of the same playlist at index 1, already completed. Two rows share
--     one `playlist_id` on purpose: that is what a group *is*, and a fixture with a single member
--     would let a migration lose the association without failing.
--   * `v4-solo`    -- pasted directly, so all three are NULL. That is the common row, and a
--     migration that backfilled it with something would be inventing a group nobody asked for.
--
-- `playlist_index` starts at 0 and is the position the *site* reported, not the queue position --
-- `queue_position` is a separate column and they diverge the moment a user drags a row.
--
-- Note the shape three more `ALTER TABLE ... ADD COLUMN` statements leave behind: appended to the
-- stored CREATE statement, after `duration_seconds` and before the CHECK constraints. That is
-- what v4 looks like on disk, so that is what is frozen here.

CREATE TABLE history (
    id           TEXT PRIMARY KEY NOT NULL,
    url          TEXT NOT NULL,
    title        TEXT,
    output_path  TEXT,
    format_used  TEXT,
    bytes_total  INTEGER,
    completed_at TEXT NOT NULL,

    CHECK (bytes_total IS NULL OR bytes_total >= 0)
);
CREATE TABLE jobs (
    id             TEXT    PRIMARY KEY NOT NULL,
    url            TEXT    NOT NULL,
    status         TEXT    NOT NULL,
    request        TEXT    NOT NULL,
    title          TEXT,
    output_path    TEXT,
    bytes_done     INTEGER NOT NULL DEFAULT 0,
    bytes_total    INTEGER,
    error_kind     TEXT,
    error_message  TEXT,
    attempts       INTEGER NOT NULL DEFAULT 0,
    queue_position INTEGER,
    created_at     TEXT,
    started_at     TEXT,
    finished_at    TEXT, thumbnail_url TEXT, uploader TEXT, duration_seconds REAL, playlist_id TEXT, playlist_index INTEGER, playlist_title TEXT,

    -- The queue is ordered by this and it must survive a restart (`REQ-012`). Rows with a NULL
    -- position are not queued; the partial index keeps uniqueness without forbidding that.
    CHECK (bytes_done >= 0),
    CHECK (bytes_total IS NULL OR bytes_total >= 0),
    CHECK (attempts >= 0),
    CHECK (queue_position IS NULL OR queue_position >= 0)
);
INSERT INTO "jobs" VALUES('v4-entry-1','https://example.invalid/v4-era','queued','{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_subtitles": false, "format_selector": "bestaudio/best", "media_kind": "video", "output_directory": "/downloads/Trail Sounds", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "subtitle_languages": [], "url": "https://example.invalid/v4-era"}','Track one',NULL,0,NULL,NULL,NULL,0,NULL,'2026-08-04T19:00:00+00:00',NULL,NULL,NULL,'A Label',252.5,'pl-1',0,'Trail Sounds');
INSERT INTO "jobs" VALUES('v4-entry-2','https://example.invalid/v4-era-2','completed','{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_subtitles": false, "format_selector": "bestaudio/best", "media_kind": "video", "output_directory": "/downloads/Trail Sounds", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "subtitle_languages": [], "url": "https://example.invalid/v4-era"}','Track two',NULL,0,NULL,NULL,NULL,0,NULL,'2026-08-04T19:00:00+00:00',NULL,NULL,NULL,NULL,NULL,'pl-1',1,'Trail Sounds');
INSERT INTO "jobs" VALUES('v4-solo','https://example.invalid/v4-solo','queued','{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_subtitles": false, "format_selector": "bestaudio/best", "media_kind": "video", "output_directory": "/downloads/Trail Sounds", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "subtitle_languages": [], "url": "https://example.invalid/v4-era"}',NULL,NULL,0,NULL,NULL,NULL,0,NULL,'2026-08-04T19:00:00+00:00',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
CREATE UNIQUE INDEX jobs_queue_position ON jobs (queue_position)
    WHERE queue_position IS NOT NULL;
CREATE INDEX jobs_status ON jobs (status);
CREATE INDEX history_completed_at ON history (completed_at);

-- Two history rows, because the gate requires every migrated table to be seeded: a fixture that
-- seeds none makes "data intact" assert nothing for that table. One carries a full record and one
-- carries the nulls a cancelled or partially-known download leaves behind.
INSERT INTO history VALUES ('h4-1', 'https://example.invalid/v4-era', 'A finished download',
    '/downloads/Trail Sounds/Track two.mp3', 'bestaudio/best', 5242880,
    '2026-08-04T19:00:00+00:00');
INSERT INTO history VALUES ('h4-2', 'https://example.invalid/v4-solo', NULL,
    NULL, NULL, NULL, '2026-08-04T19:05:00+00:00');

PRAGMA user_version = 4;
