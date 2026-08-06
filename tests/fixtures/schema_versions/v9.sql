-- A database as version 9 actually writes it, frozen 2026-08-06 while v9 was current.
-- T014-R4: the migration test must migrate historical BYTES, not rows that the current
-- model and serializer produced. Never regenerate this from current code -- that would
-- restore exactly the defect it exists to catch. A future version writes its own file.
--
-- **v9 is the version with no `history` table**, and that absence is the whole content of this
-- fixture. `0009` dropped the table on the maintainer's legacy-data ruling (`T169-R3`,
-- `DAT-006`'s legacy-data note): `REQ-020` says the application keeps no record of what has been
-- downloaded, and until v9 an upgraded database kept one that nothing could reach.
--
-- **What a later migration must be able to prove against this file.** The other eight fixtures
-- carry `history` rows, so they exercise the purge. This one is the other side: a database that
-- never had the table when it was migrated forward. A tenth migration written to touch `history`
-- -- to re-add it, or to clean up after it -- has to cope with both, and this is the case where
-- the table simply is not there. `DROP TABLE history` in a future migration would fail here, and
-- the harness would say so.
--
-- The rows are the two shapes v9 writes, taken from `JobRepository.append` rather than typed by
-- hand: one queued job carrying playlist membership, a title and a thumbnail, and one carrying
-- none of them. Both are `queued` at positions 0 and 1, which is `REQ-012`'s durable order.
-- Nothing here is completed, because a completed download in v9 leaves a job row and nothing else
-- -- there is no second row for a migration to preserve, which is the point of the version.

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
INSERT INTO "jobs" VALUES('v9-entry','https://example.invalid/v9-era','queued','{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_subtitles": false, "format_selector": "bestaudio/best", "media_kind": "video", "output_directory": "/downloads/Trail Sounds", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "subtitle_languages": [], "url": "https://example.invalid/v9-era"}','Track one',NULL,0,NULL,NULL,NULL,0,0,'2026-08-06T15:00:00+00:00',NULL,NULL,'https://img.invalid/one.jpg',NULL,NULL,'pl-9',0,'Trail Sounds');
INSERT INTO "jobs" VALUES('v9-solo','https://example.invalid/v9-solo','queued','{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_subtitles": false, "format_selector": "bestaudio/best", "media_kind": "video", "output_directory": "/downloads/Trail Sounds", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "subtitle_languages": [], "url": "https://example.invalid/v9-solo"}',NULL,NULL,0,NULL,NULL,NULL,0,1,'2026-08-06T15:00:00+00:00',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
CREATE UNIQUE INDEX jobs_queue_position ON jobs (queue_position)
    WHERE queue_position IS NOT NULL;
CREATE INDEX jobs_status ON jobs (status);

PRAGMA user_version = 9;
