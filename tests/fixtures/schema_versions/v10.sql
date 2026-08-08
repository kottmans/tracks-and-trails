-- A database as version 10 actually writes it, frozen 2026-08-08 while v10 was current.
-- T014-R4: the migration test must migrate historical BYTES, not rows that the current
-- model and serializer produced. Never regenerate this from current code -- that would
-- restore exactly the defect it exists to catch. A future version writes its own file.
--
-- **v10 is the version that knows whether a job is live**, and that column is the whole content
-- of this fixture. `0010` added it so a queue row could satisfy `REQ-017`'s second half -- *state
-- clearly when resumption is not possible* -- which until now had nothing to state it from.
--
-- **What a later migration must be able to prove against this file.** `is_live` is `NOT NULL
-- DEFAULT 0`, unlike every other column `0002`..`0004` added, so a migration that assumes the
-- job table's added columns are all nullable meets its counter-example here. The two rows are the
-- two values: one live and one not. A migration rewriting the table -- which SQLite makes people
-- do for a constraint change -- has to carry the NOT NULL and the default across, and dropping
-- either fails against this.
--
-- The rows come from `JobRepository.append` rather than being typed by hand, so the request blob
-- is the one this version's serializer actually produces -- including `T-109`'s five typed
-- post-processing fields, which is what a v10-era blob contains and a hand-written one would not.

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
    finished_at    TEXT, thumbnail_url TEXT, uploader TEXT, duration_seconds REAL, playlist_id TEXT, playlist_index INTEGER, playlist_title TEXT, is_live INTEGER NOT NULL DEFAULT 0,
    -- The queue is ordered by this and it must survive a restart (`REQ-012`). Rows with a NULL
    -- position are not queued; the partial index keeps uniqueness without forbidding that.
    CHECK (bytes_done >= 0),
    CHECK (bytes_total IS NULL OR bytes_total >= 0),
    CHECK (attempts >= 0),
    CHECK (queue_position IS NULL OR queue_position >= 0)
);
INSERT INTO "jobs" VALUES('v10-live','https://example.invalid/v10-live','queued','{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_chapters": false, "embed_metadata": false, "embed_subtitles": false, "embed_thumbnail": false, "format_selector": "bestaudio/best", "media_kind": "video", "output_directory": "/downloads/Trail Sounds", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "recode_container": null, "remux_container": null, "subtitle_languages": [], "url": "https://example.invalid/v10-live"}','A live set',NULL,0,NULL,NULL,NULL,0,0,'2026-08-08T15:00:00+00:00',NULL,NULL,'https://img.invalid/live.jpg',NULL,NULL,NULL,NULL,NULL,1);
INSERT INTO "jobs" VALUES('v10-solo','https://example.invalid/v10-solo','queued','{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_chapters": false, "embed_metadata": false, "embed_subtitles": false, "embed_thumbnail": false, "format_selector": "bestaudio/best", "media_kind": "video", "output_directory": "/downloads/Trail Sounds", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "recode_container": null, "remux_container": null, "subtitle_languages": [], "url": "https://example.invalid/v10-solo"}',NULL,NULL,0,NULL,NULL,NULL,0,1,'2026-08-08T15:00:00+00:00',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0);
CREATE UNIQUE INDEX jobs_queue_position ON jobs (queue_position)
    WHERE queue_position IS NOT NULL;
CREATE INDEX jobs_status ON jobs (status);

PRAGMA user_version = 10;
