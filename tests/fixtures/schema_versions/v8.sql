-- A database as version 8 actually writes it, frozen 2026-08-06 while v8 was current.
-- T014-R4: the migration test must migrate historical BYTES, not rows that the current
-- model and serializer produced. Never regenerate this from current code -- that would
-- restore exactly the defect it exists to catch. A future version writes its own file.
--
-- v8 is where `history` stopped being a product and became the completion ledger (`T-169`,
-- `T-170`, `DAT-006`). It adds `normalised_url` -- the key `REQ-022` looks up -- and an index on
-- it. It drops nothing: SQLite implements a column drop as a table rewrite, which `DAT-006` §5
-- refuses on a table holding a user's own record of their own downloads.
--
-- The rows are chosen so that a later migration has every state v8 can produce:
--
--   * `h8-ledger`   -- what v8 writes now. The three ledger fields carry values and every
--     presentation column is NULL, because they stopped being written rather than being removed.
--     A migration that "tidied" this row by dropping those columns would be doing the rewrite
--     `DAT-006` §5 refused.
--   * `h8-upgraded` -- a v7-era row after `0008`'s backfill: the old presentation fields are still
--     populated, and `normalised_url` was computed from `url` by the Python step in `db.migrate`.
--     This is the upgrade data `T-114` needs, and the reason the backfill exists at all.
--   * `h8-unkeyed`  -- a URL the normaliser refused. `core/urls.normalise_url` returns `None`
--     rather than inventing a key, so the row keeps NULL and simply never matches. Frozen because
--     it is the one row a later migration could "fix" by guessing, and guessing here means warning
--     a user about the wrong download.
--   * `h8-repeat`   -- an identity downloaded twice. `DAT-006` §4 keeps one row per identity and
--     updates its completion time, so this row's `completed_at` is the later one; there is no
--     second row for the same key, and a migration must not create one.
--
-- Note that `h8-ledger` and `h8-repeat` differ in host case and fragment from URLs a user might
-- paste, which is the whole of the normalisation `DAT-006` §2 allows: scheme and host lower-cased,
-- fragment dropped, query untouched because the identity of a video lives there.
--
-- The jobs table is seeded unchanged from v7's shape, so a migration touching earlier versions'
-- columns while adding v8's still has both to preserve.

CREATE TABLE history (
    id           TEXT PRIMARY KEY NOT NULL,
    url          TEXT NOT NULL,
    title        TEXT,
    output_path  TEXT,
    format_used  TEXT,
    bytes_total  INTEGER,
    completed_at TEXT NOT NULL, thumbnail_url TEXT, playlist_id TEXT, playlist_index INTEGER, playlist_title TEXT, format_choice TEXT, normalised_url TEXT,

    CHECK (bytes_total IS NULL OR bytes_total >= 0)
);
INSERT INTO "history" VALUES('h8-ledger','https://Example.invalid/watch?v=abc123#t=30',NULL,NULL,NULL,NULL,'2026-08-06T02:00:00+00:00',NULL,NULL,NULL,NULL,NULL,'https://example.invalid/watch?v=abc123');
INSERT INTO "history" VALUES('h8-upgraded','https://example.invalid/v7-one','Track one','/downloads/Trail Sounds/Track one.mp3','251',5242880,'2026-08-05T21:00:00+00:00','https://img.invalid/one.jpg','pl-7',0,'Trail Sounds','{"audio_codec": "mp3", "audio_quality": "192", "embed_subtitles": false, "format_selector": "bestaudio/best", "media_kind": "audio", "output_template": "%(title)s.%(ext)s", "post_processors": [], "subtitle_languages": []}','https://example.invalid/v7-one');
INSERT INTO "history" VALUES('h8-unkeyed','not a url at all',NULL,NULL,NULL,NULL,'2026-08-06T02:01:00+00:00',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "history" VALUES('h8-repeat','https://example.invalid/watch?v=repeat',NULL,NULL,NULL,NULL,'2026-08-06T02:30:00+00:00',NULL,NULL,NULL,NULL,NULL,'https://example.invalid/watch?v=repeat');
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
INSERT INTO "jobs" VALUES('v8-entry','https://example.invalid/v8-era','queued','{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_subtitles": false, "format_selector": "bestaudio/best", "media_kind": "video", "output_directory": "/downloads/Trail Sounds", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "subtitle_languages": [], "url": "https://example.invalid/v8-era"}','Track one',NULL,0,NULL,NULL,NULL,0,NULL,'2026-08-06T02:00:00+00:00',NULL,NULL,'https://img.invalid/one.jpg',NULL,NULL,'pl-8',0,'Trail Sounds');
INSERT INTO "jobs" VALUES('v8-solo','https://example.invalid/v8-solo','queued','{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_subtitles": false, "format_selector": "bestaudio/best", "media_kind": "video", "output_directory": "/downloads/Trail Sounds", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "subtitle_languages": [], "url": "https://example.invalid/v8-solo"}',NULL,NULL,0,NULL,NULL,NULL,0,NULL,'2026-08-06T02:00:00+00:00',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
CREATE UNIQUE INDEX jobs_queue_position ON jobs (queue_position)
    WHERE queue_position IS NOT NULL;
CREATE INDEX jobs_status ON jobs (status);
CREATE INDEX history_completed_at ON history (completed_at);
CREATE INDEX history_normalised_url ON history (normalised_url);

PRAGMA user_version = 8;
