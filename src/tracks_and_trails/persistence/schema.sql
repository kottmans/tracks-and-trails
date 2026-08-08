-- schema.sql — a SNAPSHOT of the schema the migrations build (`T-014`).
--
-- **Not applied to create a database.** `persistence/migrations/` does that, and this file
-- is what a test compares the result against. That comparison is the acceptance criterion
-- "a schema change without a migration fails the suite", and it fails in both directions:
-- edit a migration without regenerating this, or edit this without a migration, and the
-- suite goes red.
--
-- Generated, never hand-written. `tests/unit/test_persistence.py` documents the command.

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

CREATE UNIQUE INDEX jobs_queue_position ON jobs (queue_position)
    WHERE queue_position IS NOT NULL;

CREATE INDEX jobs_status ON jobs (status);
