-- A database as version 1 actually wrote it, frozen 2026-07-26 while v1 was current.
-- T014-R4: the migration test must migrate historical BYTES, not rows that the current
-- model and serializer produced. Never regenerate this from current code — that would
-- restore exactly the defect it exists to catch. A future version writes its own file.

-- 0001 — the initial schema (`T-014`, `ARCHITECTURE.md` §5, `DAT-001`).
--
-- Every column here is one of §5's named `Job` fields, plus the `HistoryEntry` table §5
-- requires. Nothing is invented: a column the architecture does not name would be a schema
-- decision made in a migration, which is the worst place to make one.
--
-- `request` holds the serialized `DownloadRequest` (`REQ-018`, `ARCHITECTURE.md` §8). It is
-- persisted *with* the job so a retry after a settings change reproduces the original request
-- rather than current defaults. That is the "settings freeze" area of `ai/TESTING.md` §7.

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
    finished_at    TEXT,

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

-- `HistoryEntry` (`ARCHITECTURE.md` §5, `REQ-020`): a completed job's durable record, retained
-- after the job row is cleared. The table exists from version 1 deliberately — adding it later
-- costs a migration for no reason, and §5 names it as a core entity.
--
-- **Nothing writes this yet.** History is recorded when a job completes, which is the download
-- manager's job (`T-013`); pruning, search and export are Phase 3. Creating the table is in
-- this task's scope because the schema is; populating it is not.
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

CREATE INDEX history_completed_at ON history (completed_at);

INSERT INTO jobs VALUES ('v1-queued', 'https://example.invalid/v1-era', 'queued', '{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_subtitles": false, "format_selector": "bestvideo+bestaudio/best", "media_kind": "video", "output_directory": "/downloads", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "subtitle_languages": [], "url": "https://example.invalid/v1-era"}', 'A v1-era job', NULL, 0, NULL, NULL, NULL, 0, 0, '2026-07-26T12:00:00+00:00', NULL, NULL);
INSERT INTO jobs VALUES ('v1-failed', 'https://example.invalid/v1-era', 'failed', '{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_subtitles": false, "format_selector": "bestvideo+bestaudio/best", "media_kind": "video", "output_directory": "/downloads", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "subtitle_languages": [], "url": "https://example.invalid/v1-era"}', NULL, NULL, 7, 100, 'network', 'timed out', 2, 1, '2026-07-26T12:05:00+00:00', '2026-07-26T12:06:00+00:00', '2026-07-26T12:07:00+00:00');

PRAGMA user_version = 1;
