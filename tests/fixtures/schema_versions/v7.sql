-- A database as version 7 actually wrote it, frozen 2026-08-05 while v7 was current.
-- T014-R4: the migration test must migrate historical BYTES, not rows that the current
-- model and serializer produced. Never regenerate this from current code -- that would
-- restore exactly the defect it exists to catch. A future version writes its own file.
--
-- v7 added `history.format_choice` (`T-159`), so a completed download can be named in the words
-- the rest of the window uses instead of yt-dlp's format id. The column holds a `FormatChoice`
-- and never a `DownloadRequest`: `T159-R1` found the first version storing the whole request,
-- which carries a cookie path `REQ-026` forbids History to hold. Every state a later migration
-- would have to preserve is seeded:
--
--   * `h7-converted` -- a record carrying its choice, which is what v7 exists for. The stored
--     `format_used` is `251` -- yt-dlp's id for YouTube's Opus stream, and the value the
--     maintainer reported as useless to a regular user.
--   * `h7-merged`    -- `399+140`, two ids joined by yt-dlp's own selector syntax, also with a
--     choice. The worse half of the same defect.
--   * `h7-legacy`    -- the nulls a row written before v7 leaves behind: an id and no choice.
--     A migration could lose the column's absence without this, and those rows are every history
--     row in a database that predates v7.
--
-- **No row here carries a credential**, and that is part of what the fixture freezes: a later
-- migration that widened this column would have to widen these literals to match, which is a
-- change a reader can see.
--
-- The jobs table is seeded too, with a playlist member and a directly pasted row, so a migration
-- touching earlier versions' columns while adding v7's still has both to preserve.

CREATE TABLE history (
    id           TEXT PRIMARY KEY NOT NULL,
    url          TEXT NOT NULL,
    title        TEXT,
    output_path  TEXT,
    format_used  TEXT,
    bytes_total  INTEGER,
    completed_at TEXT NOT NULL, thumbnail_url TEXT, playlist_id TEXT, playlist_index INTEGER, playlist_title TEXT, format_choice TEXT,

    CHECK (bytes_total IS NULL OR bytes_total >= 0)
);
INSERT INTO "history" VALUES('h7-converted','https://example.invalid/v7-one','Track one','/downloads/Trail Sounds/Track one.mp3','251',5242880,'2026-08-05T21:00:00+00:00','https://img.invalid/one.jpg','pl-7',0,'Trail Sounds','{"audio_codec": "mp3", "audio_quality": "192", "embed_subtitles": false, "format_selector": "bestaudio/best", "media_kind": "audio", "output_template": "%(title)s.%(ext)s", "post_processors": [], "subtitle_languages": []}');
INSERT INTO "history" VALUES('h7-merged','https://example.invalid/v7-two','A merged download','/downloads/A merged download.mp4','399+140',15728640,'2026-08-05T21:01:00+00:00',NULL,NULL,NULL,NULL,'{"audio_codec": "best", "audio_quality": null, "embed_subtitles": false, "format_selector": "bestvideo+bestaudio/best", "media_kind": "video", "output_template": "%(title)s.%(ext)s", "post_processors": [], "subtitle_languages": []}');
INSERT INTO "history" VALUES('h7-legacy','https://example.invalid/v7-old','Recorded before v7',NULL,'137+140',NULL,'2026-08-05T21:02:00+00:00',NULL,NULL,NULL,NULL,NULL);
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
INSERT INTO "jobs" VALUES('v7-entry','https://example.invalid/v7-era','queued','{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_subtitles": false, "format_selector": "bestaudio/best", "media_kind": "video", "output_directory": "/downloads/Trail Sounds", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "subtitle_languages": [], "url": "https://example.invalid/v7-era"}','Track one',NULL,0,NULL,NULL,NULL,0,NULL,'2026-08-05T21:00:00+00:00',NULL,NULL,'https://img.invalid/one.jpg',NULL,NULL,'pl-7',0,'Trail Sounds');
INSERT INTO "jobs" VALUES('v7-solo','https://example.invalid/v7-solo','queued','{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_subtitles": false, "format_selector": "bestaudio/best", "media_kind": "video", "output_directory": "/downloads/Trail Sounds", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "subtitle_languages": [], "url": "https://example.invalid/v7-era"}',NULL,NULL,0,NULL,NULL,NULL,0,NULL,'2026-08-05T21:00:00+00:00',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
CREATE UNIQUE INDEX jobs_queue_position ON jobs (queue_position)
    WHERE queue_position IS NOT NULL;
CREATE INDEX jobs_status ON jobs (status);
CREATE INDEX history_completed_at ON history (completed_at);

PRAGMA user_version = 7;
