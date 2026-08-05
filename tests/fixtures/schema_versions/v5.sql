-- A database as version 5 actually wrote it, frozen 2026-08-04 while v5 was current.
-- T014-R4: the migration test must migrate historical BYTES, not rows that the current
-- model and serializer produced. Never regenerate this from current code -- that would
-- restore exactly the defect it exists to catch. A future version writes its own file.
--
-- v5 added `history.thumbnail_url` (`T-138`, `UX-005` section 3). Both states are seeded, because
-- a migration touching the column has to preserve each:
--
--   * `h5-pictured` -- a record that carries a picture, alongside every other field populated.
--   * `h5-bare`     -- the nulls a row written before this column existed leaves behind, which is
--     every history row in every database that predates v5. A fixture holding only the populated
--     case would let a migration lose the other without failing.
--
-- The jobs table is seeded too, with a playlist member and a directly pasted row, so a migration
-- touching v4's columns while adding v5's still has both to preserve.

CREATE TABLE history (
    id           TEXT PRIMARY KEY NOT NULL,
    url          TEXT NOT NULL,
    title        TEXT,
    output_path  TEXT,
    format_used  TEXT,
    bytes_total  INTEGER,
    completed_at TEXT NOT NULL, thumbnail_url TEXT,

    CHECK (bytes_total IS NULL OR bytes_total >= 0)
);
INSERT INTO "history" VALUES('h5-pictured','https://example.invalid/v5-era','A finished download','/downloads/Trail Sounds/Track two.mp3','bestaudio/best',5242880,'2026-08-04T20:00:00+00:00','https://img.invalid/two.jpg');
INSERT INTO "history" VALUES('h5-bare','https://example.invalid/v5-solo',NULL,NULL,NULL,NULL,'2026-08-04T20:00:00+00:00',NULL);
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
INSERT INTO "jobs" VALUES('v5-entry','https://example.invalid/v5-era','queued','{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_subtitles": false, "format_selector": "bestaudio/best", "media_kind": "video", "output_directory": "/downloads/Trail Sounds", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "subtitle_languages": [], "url": "https://example.invalid/v5-era"}','Track one',NULL,0,NULL,NULL,NULL,0,NULL,'2026-08-04T20:00:00+00:00',NULL,NULL,'https://img.invalid/one.jpg',NULL,NULL,'pl-5',0,'Trail Sounds');
INSERT INTO "jobs" VALUES('v5-solo','https://example.invalid/v5-solo','queued','{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_subtitles": false, "format_selector": "bestaudio/best", "media_kind": "video", "output_directory": "/downloads/Trail Sounds", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "subtitle_languages": [], "url": "https://example.invalid/v5-era"}',NULL,NULL,0,NULL,NULL,NULL,0,NULL,'2026-08-04T20:00:00+00:00',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
CREATE UNIQUE INDEX jobs_queue_position ON jobs (queue_position)
    WHERE queue_position IS NOT NULL;
CREATE INDEX jobs_status ON jobs (status);
CREATE INDEX history_completed_at ON history (completed_at);

PRAGMA user_version = 5;
