-- A database as version 6 actually wrote it, frozen 2026-08-05 while v6 was current.
-- T014-R4: the migration test must migrate historical BYTES, not rows that the current
-- model and serializer produced. Never regenerate this from current code -- that would
-- restore exactly the defect it exists to catch. A future version writes its own file.
--
-- v6 added `history.playlist_id`, `playlist_index` and `playlist_title` (`T-145`, `UX-005`
-- amended 2026-08-05). Every state a later migration would have to preserve is seeded:
--
--   * `h6-entry-one`, `h6-entry-two` -- two members of one playlist, carrying the membership
--     v6 introduced, in the playlist's own order rather than completion order.
--   * `h6-solo`     -- a directly pasted download. Fully populated and deliberately NOT a
--     member: the three columns are all-or-nothing, so the ungrouped case has to be here or a
--     migration could lose it while the grouped rows still passed.
--   * `h6-bare`     -- the nulls a row written before v5 and v6 leaves behind, which is every
--     history row in a database that predates them.
--
-- The jobs table is seeded too, with a playlist member and a directly pasted row, so a migration
-- touching v4's columns while adding v6's still has both to preserve.

CREATE TABLE history (
    id           TEXT PRIMARY KEY NOT NULL,
    url          TEXT NOT NULL,
    title        TEXT,
    output_path  TEXT,
    format_used  TEXT,
    bytes_total  INTEGER,
    completed_at TEXT NOT NULL, thumbnail_url TEXT, playlist_id TEXT, playlist_index INTEGER, playlist_title TEXT,

    CHECK (bytes_total IS NULL OR bytes_total >= 0)
);
INSERT INTO "history" VALUES('h6-entry-one','https://example.invalid/v6-one','Track one','/downloads/Trail Sounds/Track one.mp3','bestaudio/best',5242880,'2026-08-05T20:00:00+00:00','https://img.invalid/one.jpg','pl-6',0,'Trail Sounds');
INSERT INTO "history" VALUES('h6-entry-two','https://example.invalid/v6-two','Track two','/downloads/Trail Sounds/Track two.mp3','bestaudio/best',6291456,'2026-08-05T20:01:00+00:00','https://img.invalid/two.jpg','pl-6',1,'Trail Sounds');
INSERT INTO "history" VALUES('h6-solo','https://example.invalid/v6-solo','A pasted download','/downloads/A pasted download.mp4','137+140',15728640,'2026-08-05T20:02:00+00:00','https://img.invalid/solo.jpg',NULL,NULL,NULL);
INSERT INTO "history" VALUES('h6-bare','https://example.invalid/v6-bare',NULL,NULL,NULL,NULL,'2026-08-05T20:03:00+00:00',NULL,NULL,NULL,NULL);
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
INSERT INTO "jobs" VALUES('v6-entry','https://example.invalid/v6-era','queued','{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_subtitles": false, "format_selector": "bestaudio/best", "media_kind": "video", "output_directory": "/downloads/Trail Sounds", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "subtitle_languages": [], "url": "https://example.invalid/v6-era"}','Track one',NULL,0,NULL,NULL,NULL,0,NULL,'2026-08-05T20:00:00+00:00',NULL,NULL,'https://img.invalid/one.jpg',NULL,NULL,'pl-6',0,'Trail Sounds');
INSERT INTO "jobs" VALUES('v6-solo','https://example.invalid/v6-solo','queued','{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_subtitles": false, "format_selector": "bestaudio/best", "media_kind": "video", "output_directory": "/downloads/Trail Sounds", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "subtitle_languages": [], "url": "https://example.invalid/v6-era"}',NULL,NULL,0,NULL,NULL,NULL,0,NULL,'2026-08-05T20:00:00+00:00',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
CREATE UNIQUE INDEX jobs_queue_position ON jobs (queue_position)
    WHERE queue_position IS NOT NULL;
CREATE INDEX jobs_status ON jobs (status);
CREATE INDEX history_completed_at ON history (completed_at);

PRAGMA user_version = 6;
