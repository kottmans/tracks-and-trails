-- A database as version 3 actually wrote it, frozen 2026-08-04 while v3 was current.
-- T014-R4: the migration test must migrate historical BYTES, not rows that the current
-- model and serializer produced. Never regenerate this from current code -- that would
-- restore exactly the defect it exists to catch. A future version writes its own file.
--
-- v3 added `jobs.uploader` and `jobs.duration_seconds` (`T124-R4`, `UX-005` section 3). Both
-- states of the pair are seeded: a probed row carrying an uploader and a duration, and one that
-- carries neither. A later migration touching either column has to preserve both, and a fixture
-- holding only the populated case would let it lose the other.
--
-- The duration is fractional on purpose. The column is REAL because yt-dlp reports fractional
-- durations, and a migration that quietly narrowed it to INTEGER would pass a "does it run"
-- check while rounding every stored clip.
--
-- Note the shape two more `ALTER TABLE ... ADD COLUMN` statements leave behind: the columns are
-- appended to the stored CREATE statement, after `thumbnail_url` and before the CHECK
-- constraints. That is what v3 looks like on disk, so that is what is frozen here -- not the
-- tidier column order a from-scratch v3 schema would have had.

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
    finished_at    TEXT, thumbnail_url TEXT, uploader TEXT, duration_seconds REAL,

    -- The queue is ordered by this and it must survive a restart (`REQ-012`). Rows with a NULL
    -- position are not queued; the partial index keeps uniqueness without forbidding that.
    CHECK (bytes_done >= 0),
    CHECK (bytes_total IS NULL OR bytes_total >= 0),
    CHECK (attempts >= 0),
    CHECK (queue_position IS NULL OR queue_position >= 0)
);

CREATE INDEX history_completed_at ON history (completed_at);

CREATE UNIQUE INDEX jobs_queue_position ON jobs (queue_position)
    WHERE queue_position IS NOT NULL;

CREATE INDEX jobs_status ON jobs (status);

INSERT INTO jobs VALUES ('v3-probed', 'https://example.invalid/v3-era', 'ready',
    '{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_subtitles": false, "format_selector": "bestvideo+bestaudio/best", "media_kind": "video", "output_directory": "/downloads", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "subtitle_languages": [], "url": "https://example.invalid/v3-era"}',
    'A v3-era job', NULL, 0, NULL, NULL, NULL, 0, 0, '2026-08-04T12:00:00+00:00', NULL, NULL,
    'https://example.invalid/thumb/v3.jpg', 'Someone Who Publishes', 212.5);

-- Probed, and the extractor named neither. NULL here is an answer, not an absence of one: some
-- sites publish no uploader and a live stream has no duration.
INSERT INTO jobs VALUES ('v3-no-media', 'https://example.invalid/v3-era-2', 'failed',
    '{"audio_codec": "best", "audio_quality": null, "cookies_from_browser": null, "embed_subtitles": false, "format_selector": "bestvideo+bestaudio/best", "media_kind": "video", "output_directory": "/downloads", "output_template": "%(title)s.%(ext)s", "post_processors": [], "proxy": null, "rate_limit_bytes": null, "subtitle_languages": [], "url": "https://example.invalid/v3-era"}',
    NULL, NULL, 7, 100, 'network', 'timed out', 2, 1, '2026-08-04T12:05:00+00:00',
    '2026-08-04T12:06:00+00:00', '2026-08-04T12:07:00+00:00', NULL, NULL, NULL);


-- History rows, so a migration touching this table is covered too (`T014-R4`).
INSERT INTO history VALUES ('h-1', 'https://example.invalid/v3-era', 'A finished download',
    '/downloads/a.mp4', 'bestvideo+bestaudio/best', 1048576, '2026-08-04T11:00:00+00:00');
INSERT INTO history VALUES ('h-2', 'https://example.invalid/v3-era-2', NULL,
    NULL, NULL, NULL, '2026-08-04T11:30:00+00:00');

PRAGMA user_version = 3;
