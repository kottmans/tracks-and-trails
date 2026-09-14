-- A database as version 12 actually writes it, frozen 2026-09-13 while v12 was current.
-- T014-R4: the migration test must migrate historical BYTES, not rows that the current
-- model and serializer produced. Never regenerate this from current code -- that would
-- restore exactly the defect it exists to catch. A future version writes its own file.
--
-- **v12 is the version that knows a job's site id, channel and site** (`0012`, `UX-014`): the
-- *ID*, *Channel* and *Site* naming fields preview a queued download from them. One row holds all
-- three and a date; the other holds none, which is every row a site says nothing about.
--
-- The rows come from `JobRepository.append` rather than being typed by hand, so the request blob
-- is the one this version's serializer actually produces. The id is `capture.py`'s placeholder.

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
    finished_at    TEXT, thumbnail_url TEXT, uploader TEXT, duration_seconds REAL, playlist_id TEXT, playlist_index INTEGER, playlist_title TEXT, is_live INTEGER NOT NULL DEFAULT 0, upload_date TEXT, media_id TEXT, channel TEXT, site TEXT,

    -- The queue is ordered by this and it must survive a restart (`REQ-012`). Rows with a NULL
    -- position are not queued; the partial index keeps uniqueness without forbidding that.
    CHECK (bytes_done >= 0),
    CHECK (bytes_total IS NULL OR bytes_total >= 0),
    CHECK (attempts >= 0),
    CHECK (queue_position IS NULL OR queue_position >= 0)
);
INSERT INTO "jobs" VALUES('v12-identified','https://example.invalid/v12-identified','queued','{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_chapters": false, "embed_metadata": false, "embed_subtitles": false, "embed_thumbnail": false, "format_selector": "best", "media_kind": "video", "output_directory": "/downloads", "output_template": "%(channel)s/%(id)s %(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "recode_container": null, "remux_container": null, "retries": null, "subtitle_languages": [], "url": "https://example.invalid/v12-identified"}','A clip',NULL,0,NULL,NULL,NULL,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,'20260913','fixture-id','A channel','Youtube');
INSERT INTO "jobs" VALUES('v12-anonymous','https://example.invalid/v12-anonymous','queued','{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_chapters": false, "embed_metadata": false, "embed_subtitles": false, "embed_thumbnail": false, "format_selector": "best", "media_kind": "video", "output_directory": "/downloads", "output_template": "%(channel)s/%(id)s %(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "recode_container": null, "remux_container": null, "retries": null, "subtitle_languages": [], "url": "https://example.invalid/v12-anonymous"}','A clip',NULL,0,NULL,NULL,NULL,0,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL);
CREATE UNIQUE INDEX jobs_queue_position ON jobs (queue_position)
    WHERE queue_position IS NOT NULL;
CREATE INDEX jobs_status ON jobs (status);

PRAGMA user_version = 12;
