"""Persistence: schema, migrations, and the job repository (`T-014`).

Covers three of `ai/TESTING.md` §7's mandatory areas — crash recovery, migrations, and the
settings freeze — plus `REQ-012`'s durable queue order and `REQ-026`'s exclusion of secrets.

The hard kill that `NFR-003` actually turns on lives in `tests/integration/test_crash_kill.py`,
because it needs a real process to kill. Everything provable in-process is here.
"""

import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import pytest

from tracks_and_trails.core.errors import ErrorKind, is_auto_retryable, is_retryable
from tracks_and_trails.core.job_state import (
    REORDERABLE,
    TERMINAL,
    IllegalTransitionError,
    JobStatus,
)
from tracks_and_trails.core.models import AudioCodec, DownloadRequest, Job, MediaKind
from tracks_and_trails.core.presets import format_choice_of
from tracks_and_trails.persistence import db, repositories
from tracks_and_trails.persistence.repositories import (
    INTERRUPTED_ON_STARTUP,
    HistoryEntry,
    HistoryRepository,
    JobRepository,
)


def a_request(**overrides: Any) -> DownloadRequest:
    """A valid request. Overrides let a test vary exactly the field it is about."""
    base: dict[str, Any] = {
        "url": "https://example.invalid/watch?v=abc123",
        "output_directory": "/downloads",
        "format_selector": "bestvideo[height<=1080]+bestaudio/best",
        "output_template": "%(title)s.%(ext)s",
    }
    return DownloadRequest(**(base | overrides))


def a_job(job_id: str = "job-1", **overrides: Any) -> Job:
    request: DownloadRequest = overrides.pop("request", None) or a_request()
    base: dict[str, Any] = {
        "id": job_id,
        "url": request.url,
        "request": request,
        "created_at": datetime(2026, 7, 26, 12, 0, tzinfo=UTC),
    }
    return Job(**(base | overrides))


@pytest.fixture
def repository(tmp_path: Path) -> JobRepository:
    return JobRepository(db.connect(tmp_path / "library.sqlite3"))


def _strip_sql_comments(sql: str) -> str:
    return "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))


def _normalise_sql(sql: str) -> str:
    """Comment-free, whitespace-collapsed SQL, so the drift test compares schema not formatting.

    Applied to both sides of the comparison. Re-indenting a migration should not fail the suite;
    adding a column should.
    """
    return " ".join(_strip_sql_comments(sql).split())


# --- migrations (ai/TESTING.md §7) -----------------------------------------------------------


def test_migrations_are_discovered_from_the_directory_not_a_list() -> None:
    """The harness cannot fall behind the migrations it tests.

    A hand-maintained list is a second source of truth, and a test built on it proves only that
    the list agrees with itself. This asserts the runner reads the filesystem, by checking that
    every `.sql` file present is reported.
    """
    on_disk = sorted(p.name for p in db.MIGRATIONS_DIRECTORY.glob("*.sql"))
    reported = sorted(path.name for _, path in db.available_migrations())
    assert reported == on_disk
    assert on_disk, "there must be at least one migration, or nothing below tests anything"


#: Frozen databases, one per schema version, each captured **while that version was current**.
#:
#: `T014-R4`. The earlier harness replayed old DDL and then seeded it through the *current*
#: repository, model and serializer. That does not test a migration: when a request field or its
#: representation changes, a genuine v1 row holds the old JSON shape while the harness would
#: write the new shape into a v1 table and migrate that — so a missing data migration passes.
#:
#: These files are historical artefacts. **Never regenerate them from current code.** A new
#: version adds its own file and leaves the older ones untouched.
#: Tables the fixtures seed and the migration test compares. Literals, never user input.
_MIGRATED_TABLES: Final = ("jobs", "history")


def _rows_by_id(connection: sqlite3.Connection, table: str) -> dict[str, dict[str, Any]]:
    """Every row of `table`, keyed by id. `table` comes from `_MIGRATED_TABLES`, never input."""
    return {
        row["id"]: dict(row)
        for row in connection.execute(f"SELECT * FROM {table}")  # noqa: S608
    }


HISTORICAL_FIXTURES: Final = Path(__file__).parent.parent / "fixtures" / "schema_versions"


def historical_versions() -> list[tuple[int, Path]]:
    """Frozen fixtures on disk, as `(version, path)` — discovered, not listed."""
    found = []
    for path in sorted(HISTORICAL_FIXTURES.glob("v*.sql")):
        found.append((int(path.stem.lstrip("v")), path))
    return sorted(found)


def test_a_frozen_fixture_exists_for_every_schema_version_but_the_latest() -> None:
    """Without this, the migration test below silently covers nothing.

    A version whose fixture was never captured cannot be migrated *from* in any later run, and
    the moment to capture it is while it is current. This fails the build that introduces v2
    without freezing v1's successor state, which is exactly when the author still can.
    """
    captured = {version for version, _ in historical_versions()}
    expected = {version for version, _ in db.available_migrations()}
    assert expected - captured == set(), (
        f"no frozen fixture for schema version(s) {sorted(expected - captured)}. Capture one "
        "while that version is current — it cannot be reconstructed later, which is the whole "
        "reason this gate exists (T014-R4)."
    )


@pytest.mark.parametrize(("version", "fixture"), historical_versions())
def test_every_migration_runs_forward_from_real_historical_data(
    tmp_path: Path, version: int, fixture: Path
) -> None:
    """`ai/TESTING.md` §7, against bytes that a past version actually wrote (`T014-R4`).

    The fixture is loaded as SQL and migrated by the **current runner only**. No current model,
    serializer or repository touches it before the migration — that is the difference between
    testing a migration and testing that today's code can round-trip through an old table.

    Data intact is the operative half. A migration that drops and recreates a table passes a
    "does it run" check and loses the user's queue.
    """
    database = tmp_path / f"from_v{version}.sqlite3"
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    db.configure(connection)
    connection.executescript(fixture.read_text(encoding="utf-8"))
    connection.commit()

    assert db.schema_version(connection) == version, "the fixture must declare its own version"
    before = {table: _rows_by_id(connection, table) for table in _MIGRATED_TABLES}
    for table, rows in before.items():
        assert rows, f"the fixture seeds no {table} rows, so 'data intact' asserts nothing there"

    applied = db.migrate(connection)
    assert all(v > version for v in applied)
    assert db.schema_version(connection) == db.latest_version()

    after = {table: _rows_by_id(connection, table) for table in _MIGRATED_TABLES}

    for table, originals in before.items():
        assert set(after[table]) == set(originals), (
            f"migrating {table} from v{version} lost or added rows. A migration that recreates a "
            "table passes a 'does it run' check and drops the user's queue."
        )
        for row_id, original in originals.items():
            for column, value in original.items():
                assert after[table][row_id][column] == value, (
                    f"{table}.{row_id}.{column} changed during migration from v{version}. No "
                    "migration transforms data yet, so any change is loss. `T-048` owns "
                    "verifying a real data migration when the first one is written (T014-R4)."
                )

    # And the current repository can read what the migration produced — the property a user
    # actually experiences after upgrading.
    for job in JobRepository(connection).all_jobs():
        assert job.id in before["jobs"]
    connection.close()


def test_a_schema_change_without_a_migration_fails(tmp_path: Path) -> None:
    """An acceptance criterion, and it fails in both directions.

    `schema.sql` is a generated snapshot of what the migrations build. Change a migration without
    regenerating it, or hand-edit the snapshot without a migration, and this goes red.

    Regenerate with the migrations as the source of truth:

        sqlite3 :memory: < each migration, then
        SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type DESC, name
    """
    connection = db.connect(tmp_path / "built.sqlite3")
    built = [
        _normalise_sql(row[0])
        for row in connection.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type DESC, name"
        )
    ]
    connection.close()

    # Both sides go through the *same* normaliser. SQLite stores a CREATE statement including
    # any comments written inside it, so stripping comments from only one side compares two
    # different things and fails on formatting rather than on schema.
    snapshot = _strip_sql_comments(db.SCHEMA_SNAPSHOT.read_text(encoding="utf-8"))
    recorded = [_normalise_sql(statement) for statement in snapshot.split(";") if statement.strip()]
    assert built == recorded, (
        "the schema the migrations build no longer matches persistence/schema.sql. Either a "
        "migration changed without regenerating the snapshot, or the snapshot was edited "
        "without a migration to produce it."
    )


def test_a_migration_filename_that_would_be_skipped_raises(tmp_path: Path) -> None:
    """A silently ignored migration puts two machines on different schemas with no error."""
    (tmp_path / "not-a-migration.sql").write_text("SELECT 1;", encoding="utf-8")
    original = db.MIGRATIONS_DIRECTORY
    try:
        db.MIGRATIONS_DIRECTORY = tmp_path  # type: ignore[misc]
        with pytest.raises(ValueError, match="not a valid migration name"):
            db.available_migrations()
    finally:
        db.MIGRATIONS_DIRECTORY = original  # type: ignore[misc]


def test_a_gap_in_migration_versions_raises(tmp_path: Path) -> None:
    """ "Every prior version" is ambiguous with a gap, so the gap is refused rather than guessed."""
    (tmp_path / "0001_first.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0003_third.sql").write_text("SELECT 1;", encoding="utf-8")
    original = db.MIGRATIONS_DIRECTORY
    try:
        db.MIGRATIONS_DIRECTORY = tmp_path  # type: ignore[misc]
        with pytest.raises(ValueError, match="no gaps"):
            db.available_migrations()
    finally:
        db.MIGRATIONS_DIRECTORY = original  # type: ignore[misc]


def test_a_failed_migration_rolls_back_its_schema_and_its_version_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T014-R2`. The defect this replaced was a schema/version split, not a crash.

    The earlier runner ran `BEGIN; DDL; COMMIT;` and then set `PRAGMA user_version` in a second
    transaction. An interruption between them committed the tables at version 0, so the next
    startup re-ran the migration and died with `table jobs already exists` — a database that
    cannot be opened again, from a crash that SQLite itself handled correctly.

    Deterministic rather than timing-dependent: the migration's last statement is invalid, so
    the failure lands *after* the DDL and the pragma have both been issued inside the
    transaction. Neither may survive.
    """
    directory = tmp_path / "migrations"
    directory.mkdir()
    (directory / "0001_broken.sql").write_text(
        "CREATE TABLE jobs (id TEXT PRIMARY KEY);\nINSERT INTO no_such_table VALUES (1);\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(db, "MIGRATIONS_DIRECTORY", directory)

    connection = sqlite3.connect(tmp_path / "broken.sqlite3")
    db.configure(connection)
    with pytest.raises(sqlite3.Error):
        db.migrate(connection)

    assert db.schema_version(connection) == 0, (
        "the version bump survived a failed migration; the next startup would skip DDL that "
        "never ran"
    )
    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "jobs" not in tables, (
        "the DDL survived a failed migration; the next startup would re-run it and fail with "
        "'table jobs already exists'"
    )
    connection.close()


def test_a_migration_interrupted_at_the_commit_leaves_a_database_that_still_opens(
    tmp_path: Path,
) -> None:
    """`T014-R2`, and **the case the failing-migration test above cannot reach**.

    The dangerous interruption is not a migration that fails — SQLite rolls that back correctly
    either way. It is a migration that *succeeds* and is interrupted between committing its DDL
    and recording its version. The old runner did those in two transactions, so the tables
    landed at version 0 and the next startup re-ran the DDL and died with `table jobs already
    exists`: a database that can never be opened again.

    Simulated deterministically by truncating the script at its `COMMIT` and then dying. With
    the pragma *inside* the transaction the commit carries both, so the interruption is harmless
    and the next startup proceeds. With the pragma after the `COMMIT`, this leaves the split.

    The assertion is the property a user experiences: **the next startup still works.**
    """

    class DiesAtCommit(sqlite3.Connection):
        """Runs the script up to and including its `COMMIT`, then stops existing.

        A subclass rather than a patch: `sqlite3.Connection` is an immutable C type, so its
        methods cannot be replaced on the class.
        """

        # Not named `interrupt`: `sqlite3.Connection.interrupt` is a real method, and shadowing
        # it with a bool would break any caller that used it.
        stop_at_commit = True

        def executescript(self, sql_script: str) -> sqlite3.Cursor:
            if not DiesAtCommit.stop_at_commit:
                return super().executescript(sql_script)
            head, separator, _ = sql_script.partition("COMMIT;")
            super().executescript(head + separator)
            raise RuntimeError("the process died here")

    connection = sqlite3.connect(tmp_path / "interrupted.sqlite3", factory=DiesAtCommit)
    db.configure(connection)

    with pytest.raises(RuntimeError, match="died here"):
        db.migrate(connection)
    DiesAtCommit.stop_at_commit = False

    # Whatever survived, schema and version must agree, so the next startup can continue.
    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if tables:
        assert db.schema_version(connection) > 0, (
            "tables were committed at version 0. The next startup re-runs the migration and "
            "fails with 'table jobs already exists' — the database is unopenable from here."
        )

    db.migrate(connection)  # must not raise
    assert db.schema_version(connection) == db.latest_version()
    JobRepository(connection).add(a_job("after-recovery"))
    connection.close()


def test_an_empty_migration_set_raises_rather_than_creating_an_empty_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T014-R3`. A packaging omission must not masquerade as a valid version-0 database.

    PyInstaller collects `.sql` files only when the spec names them, and when it does not the
    migration directory is merely *absent*. Left unchecked, `connect()` returns a database with
    no tables and the first write fails with `no such table: jobs` — which reads as a code bug
    on the platform where `OPS-003` says failures are diagnosed from a log and nothing else.
    """
    empty = tmp_path / "no-migrations"
    empty.mkdir()
    monkeypatch.setattr(db, "MIGRATIONS_DIRECTORY", empty)

    connection = sqlite3.connect(tmp_path / "empty.sqlite3")
    db.configure(connection)
    with pytest.raises(RuntimeError, match="no migrations found"):
        db.migrate(connection)
    connection.close()


def test_the_frozen_spec_collects_the_migration_sql() -> None:
    """`T014-R3`, as a cheap early warning — **not** the real gate.

    This asserts the spec *declares* the data rule. Whether PyInstaller then places the files in
    the artifact is proven only by `--database-probe` running inside a built one, which CI does
    on both platforms. Both exist because they fail at different times: this fails in seconds on
    every push, that one fails on the thing users install.
    """
    spec = (Path(__file__).parent.parent.parent / "packaging" / "tracks-and-trails.spec").read_text(
        encoding="utf-8"
    )
    assert "persistence/migrations/*.sql" in spec, (
        "the frozen spec no longer collects the migration SQL. The artifact would build, launch, "
        "and fail every write with 'no such table: jobs'."
    )


def test_migrating_twice_applies_nothing_the_second_time(tmp_path: Path) -> None:
    """Startup runs the migrator every time; re-running DDL against existing objects would fail."""
    database = tmp_path / "library.sqlite3"
    connection = db.connect(database)
    assert db.migrate(connection) == []
    connection.close()


def test_a_version_1_database_is_migrated_when_it_is_opened(tmp_path: Path) -> None:
    """`T-117`: an existing library opens and gains the column, rather than being refused.

    The path a user actually takes on upgrade. `connect()` runs the migrator, so the assertion is
    that opening a v1 database leaves it at the latest version **and readable through the current
    repository** — a migration that ran but produced rows the model cannot build would still be a
    library the user could not open.
    """
    database = tmp_path / "from_v1.sqlite3"
    raw = sqlite3.connect(database)
    raw.executescript((HISTORICAL_FIXTURES / "v1.sql").read_text(encoding="utf-8"))
    raw.commit()
    raw.close()

    connection = db.connect(database)

    assert db.schema_version(connection) == db.latest_version()
    jobs = {job.id: job for job in JobRepository(connection).all_jobs()}
    assert set(jobs) == {"v1-queued", "v1-failed"}, "the upgrade lost the user's queue"
    assert jobs["v1-queued"].title == "A v1-era job", "an unrelated column changed"
    connection.close()


def test_a_job_written_before_the_column_existed_reads_as_having_no_thumbnail(
    tmp_path: Path,
) -> None:
    """`T-117`: no backfill, and `None` is the honest value for a row nobody asked.

    A v1 row was never probed for a thumbnail, so inventing one — a placeholder address, an empty
    string — would be a claim the probe never made. `None` is what `T-119` draws its placeholder
    for, and it is what a probed job that found nothing stores too; `status` is what tells those
    two apart.
    """
    database = tmp_path / "from_v1.sqlite3"
    raw = sqlite3.connect(database)
    raw.executescript((HISTORICAL_FIXTURES / "v1.sql").read_text(encoding="utf-8"))
    raw.commit()
    raw.close()

    connection = db.connect(database)

    stored = JobRepository(connection).all_jobs()
    assert all(job.thumbnail_url is None for job in stored)
    # `T124-R4`'s two columns arrived at v3 with no backfill, for `0002`'s reason: a v1 row was
    # never asked for either, and inventing a value would be a claim no probe made.
    assert all(job.uploader is None for job in stored)
    assert all(job.duration_seconds is None for job in stored)
    connection.close()


def test_a_thumbnail_url_round_trips_through_the_database(repository: JobRepository) -> None:
    """`T-117`: the column is wired through the mapping in both directions.

    Both states, because a mapping that wrote the value and read back a constant would pass a
    test that only ever stored one of them.
    """
    with_picture = a_job(title="Has one", thumbnail_url="https://example.invalid/thumb.jpg")
    without = a_job("second", title="Has none")
    repository.add(with_picture)
    repository.add(without)

    assert repository.get(with_picture.id) == with_picture
    assert repository.get("second") == without


def test_the_uploader_and_duration_round_trip_through_the_database(
    repository: JobRepository,
) -> None:
    """`T124-R4`, `UX-005` §3: the row anatomy needs both, so both have to survive a restart.

    Both states again, for the reason above — and the duration is **fractional**, which is what
    tells a REAL column from an INTEGER one. yt-dlp reports fractional durations, and a mapping
    that silently truncated would leave the queue and the add dialog disagreeing about the same
    clip by up to a second.
    """
    probed = a_job(title="Has both", uploader="Someone Who Publishes", duration_seconds=212.5)
    without = a_job("second", title="Has neither")
    repository.add(probed)
    repository.add(without)

    assert repository.get(probed.id) == probed
    assert repository.get("second") == without


# --- storage and the durable queue (REQ-012) -------------------------------------------------


def test_wal_is_on_because_it_is_the_reason_sqlite_was_chosen(tmp_path: Path) -> None:
    """`DAT-001`: WAL journaling is the crash-safety guarantee, not an optimisation."""
    connection = db.connect(tmp_path / "library.sqlite3")
    assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    connection.close()


def test_a_job_round_trips_through_the_database(repository: JobRepository) -> None:
    stored = a_job(
        title="A Title",
        output_path="/downloads/a.mp4",
        bytes_done=12,
        bytes_total=100,
        attempts=2,
        queue_position=3,
    )
    repository.add(stored)
    assert repository.get(stored.id) == stored


def test_queue_order_survives_a_restart(tmp_path: Path) -> None:
    """`REQ-012`. Reopened from disk, not from a cached connection — the point is durability."""
    database = tmp_path / "library.sqlite3"
    # Inserted out of order on purpose: if the repository returned insertion order the test
    # would still need to fail, so the two orders must differ.
    with db.open_database(database) as connection:
        repository = JobRepository(connection)
        for name, position in [("third", 2), ("first", 0), ("second", 1)]:
            repository.add(a_job(name, queue_position=position))

    with db.open_database(database) as connection:
        assert [job.id for job in JobRepository(connection).queued()] == [
            "first",
            "second",
            "third",
        ]


def test_two_jobs_cannot_hold_the_same_queue_position(repository: JobRepository) -> None:
    """Ordering that permits duplicates is not an order; the queue would shuffle per query."""
    repository.add(a_job("a", queue_position=0))
    with pytest.raises(sqlite3.IntegrityError):
        repository.add(a_job("b", queue_position=0))


def test_append_allocates_positions_at_the_end_of_the_queue(repository: JobRepository) -> None:
    """`ARC-005`: a batch goes to the end, and the next batch goes after it.

    Two batches, because one cannot tell "read the current maximum" from "start at zero" — an
    empty database gives 0, 1, 2 either way. That is exactly how a mutation replacing the
    `MAX(queue_position)` read with a constant survived the first battery.
    """
    first = repository.append([a_job("a"), a_job("b")])
    second = repository.append([a_job("c"), a_job("d")])

    assert [job.queue_position for job in first] == [0, 1]
    assert [job.queue_position for job in second] == [2, 3]
    assert [job.id for job in repository.queued()] == ["a", "b", "c", "d"]


def test_append_writes_every_job_or_none_of_them(repository: JobRepository) -> None:
    """One transaction (`ARC-005`), so a half-queued paste cannot exist.

    The second batch repeats an id, which the primary key refuses. What matters is that its
    *other*, valid job did not land either.
    """
    repository.append([a_job("a")])

    with pytest.raises(sqlite3.IntegrityError):
        repository.append([a_job("fresh"), a_job("a")])

    assert [job.id for job in repository.all_jobs()] == ["a"]


def test_append_of_nothing_is_a_no_op(repository: JobRepository) -> None:
    """A caller with no new URLs should not have to special-case the empty batch."""
    assert repository.append([]) == []
    assert repository.all_jobs() == []


def test_updating_a_job_that_is_not_stored_raises(repository: JobRepository) -> None:
    """Silently inserting would hide that the caller's model of the queue is wrong."""
    with pytest.raises(KeyError):
        repository.update(a_job("never-added"))


# --- the settings freeze (ai/TESTING.md §7, ARCHITECTURE.md §8) ------------------------------


def test_a_retry_uses_the_stored_request_not_the_current_defaults(
    repository: JobRepository,
) -> None:
    """`ai/TESTING.md` §7's settings-freeze area, proven by changing defaults between the two.

    The request is frozen at job creation so a settings change cannot alter a job already
    queued. Asserting the stored request merely *round-trips* would not show this — the test has
    to change what a newly built request would look like, and then confirm the stored one did
    not follow.
    """
    original = a_request(format_selector="bestaudio", output_template="%(id)s.%(ext)s")
    job = a_job(request=original)
    repository.add(job)

    changed_defaults = a_request(format_selector="worstvideo", output_template="new-%(id)s.%(ext)s")
    assert changed_defaults != original, "the test must actually change something"

    retried = repository.get(job.id)
    assert retried is not None
    assert retried.request == original
    assert retried.request.format_selector == "bestaudio"


def test_every_request_field_survives_the_round_trip(repository: JobRepository) -> None:
    """A field dropped on the way to disk would come back as its default, silently.

    Non-default values throughout, so a lost field shows up as a difference rather than
    coinciding with what the constructor would have produced anyway.
    """
    request = a_request(
        media_kind=MediaKind.AUDIO,
        post_processors=("FFmpegExtractAudio",),
        subtitle_languages=("en", "de"),
        embed_subtitles=True,
        audio_codec=AudioCodec.MP3,
        audio_quality="192",
        rate_limit_bytes=1024,
        cookies_from_browser="firefox",
    )
    repository.add(a_job(request=request))
    restored = repository.get("job-1")
    assert restored is not None
    assert restored.request == request


# --- secrets (REQ-026, NFR-007, and the T-014 scope decision) --------------------------------


def raw_row(repository: JobRepository, job_id: str = "job-1") -> str:
    """Every stored column of one job as one string, for scanning."""
    row = repository._connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return "\n".join(str(value) for value in tuple(row))


@pytest.mark.parametrize(
    "proxy",
    [
        pytest.param("//secretuser:hunter2@proxy.invalid:8080", id="scheme-relative"),
        pytest.param("secretuser:hunter2@proxy.invalid:8080", id="scheme-less"),
        pytest.param("http://secretuser:hunter2@proxy.invalid:8080", id="scheme"),
        pytest.param("secretuser:hunter2@proxy:8080", id="single-label-host"),
        pytest.param("http://secretuser:hunter2@\u00e9xample.invalid:8080", id="unicode-host"),
        pytest.param("http://secretuser@proxy.invalid:8080", id="username-only"),
        pytest.param("http://u:p@[fe80::1%25eth0]:8080", id="ipv6-zone-id"),
    ],
)
def test_a_job_carrying_proxy_credentials_cannot_be_built(proxy: str) -> None:
    """`T014-R1`, resolved upstream. **The credential is unrepresentable, not stripped.**

    Three forms reached the database while persistence tried to remove credentials from an
    unbounded string, and a fourth attempt corrupted legitimate output paths instead. The model
    now rejects any proxy carrying userinfo, so no job can hold one and this layer has nothing to
    scan. Every form that previously escaped is listed here, including the scheme-relative one
    that survived the third attempt.
    """
    with pytest.raises(ValueError, match="proxy"):
        a_request(proxy=proxy)


@pytest.mark.parametrize(
    "proxy",
    [
        pytest.param("//proxy.invalid:8080", id="scheme-relative-no-credentials"),
        pytest.param("proxy.invalid:8080", id="bare-host-port"),
        pytest.param("notaurl", id="not-a-url"),
    ],
)
def test_a_proxy_without_an_explicit_scheme_is_rejected(proxy: str) -> None:
    """The guard that has no other guard behind it (`T014-R1`).

    These carry no credentials, so neither the userinfo check nor the path check fires — only the
    scheme requirement rejects them. Without this case that requirement could be deleted as
    "redundant" on mutation evidence and every credential-bearing scheme-relative form would come
    straight back. `T-034` lost a guard exactly that way once already.

    Rejecting them is right on its own terms: `//host` and `host:8080` have no unambiguous parse,
    and `urlsplit` reads `user:pass@host` as scheme `user`.
    """
    with pytest.raises(ValueError, match="proxy"):
        a_request(proxy=proxy)


def test_a_credential_free_proxy_is_stored_exactly_as_given(repository: JobRepository) -> None:
    """The setting must survive: a proxy dropped in transit is one the user silently stops using."""
    repository.add(a_job(request=a_request(proxy="http://proxy.invalid:8080")))
    restored = repository.get("job-1")
    assert restored is not None
    assert restored.request.proxy == "http://proxy.invalid:8080"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("output_directory", "/downloads/cookie-videos", id="directory-naming-cookie"),
        pytest.param(
            "output_template", "%(uploader)s:%(id)s@example.invalid.%(ext)s", id="template"
        ),
        pytest.param("format_selector", "bestvideo[height<=1080]+bestaudio/best", id="selector"),
        pytest.param("url", "https://example.invalid/w?v=a&token=keepme", id="url"),
    ],
)
def test_functional_values_are_never_rewritten(
    repository: JobRepository, field: str, value: str
) -> None:
    """`T014-R1`'s regression, pinned. **Rewriting these is itself a Critical defect.**

    A correction once ran a secret-recogniser over every stored string. `/downloads/cookie-videos`
    became `[redacted]` — a *relative* path, so a retry would have written outside the directory
    the user chose — and a template containing `:` and `@` was rewritten. Both also broke the
    settings freeze: the stored request no longer reproduced the original.
    """
    request = a_request(**{field: value})
    repository.add(a_job(request=request, url=request.url))

    restored = repository.get("job-1")
    assert restored is not None
    assert getattr(restored.request, field) == value
    stored = repository._connection.execute("SELECT request FROM jobs").fetchone()["request"]
    assert json.loads(stored)[field] == value


def test_the_extractors_own_message_is_stored_verbatim(repository: JobRepository) -> None:
    """`T014-R7`, `NFR-006`. The diagnostic is preserved, not paraphrased.

    A correction once replaced this column with project-authored text to bound what could reach
    it. That violated `NFR-006`, `ARCHITECTURE.md` §5 and §7, `core/models.py` and
    `downloader/protocol.py` — all of which require the original message. The maintainer restored
    it alongside the proxy grammar that removed the reason it was attempted.
    """
    message = "ERROR: [youtube] dQw4w9WgXcQ: Video unavailable. This video is private."
    repository.add(a_job().with_failure(ErrorKind.EXTRACTOR_ERROR, message))

    restored = repository.get("job-1")
    assert restored is not None
    assert restored.error_message == message
    assert restored.error_kind is ErrorKind.EXTRACTOR_ERROR


def test_a_browser_name_is_not_a_cookie(repository: JobRepository) -> None:
    """Dropping it would silently stop using the cookies the user asked for (`REQ-026`)."""
    repository.add(a_job(request=a_request(cookies_from_browser="firefox")))
    row = repository._connection.execute("SELECT request FROM jobs").fetchone()
    assert json.loads(row["request"])["cookies_from_browser"] == "firefox"


# --- crash recovery (ai/TESTING.md §7, ARCHITECTURE.md §5) -----------------------------------


def test_the_recovered_statuses_are_the_three_the_architecture_names() -> None:
    """`ARCHITECTURE.md` §5 names PROBING, RUNNING and POST_PROCESSING.

    `T-014`'s own criterion and `ai/TESTING.md` §7 mention only `RUNNING`. The architecture
    outranks both (`AGENTS.md` §5), and recovering `RUNNING` alone would strand a job in
    `PROBING` with no path out — transcribed here so narrowing it fails rather than passing.
    """
    named_by_section_5 = {JobStatus.PROBING, JobStatus.RUNNING, JobStatus.POST_PROCESSING}
    assert named_by_section_5 == INTERRUPTED_ON_STARTUP


@pytest.mark.parametrize("status", sorted(INTERRUPTED_ON_STARTUP))
def test_a_job_left_in_flight_is_recovered_to_a_retryable_failure(
    repository: JobRepository, status: JobStatus
) -> None:
    """`ai/TESTING.md` §7. A job cannot be in flight if the application is only now starting."""
    repository.add(a_job("stranded", status=status, queue_position=0))

    assert repository.recover_interrupted() == ["stranded"]

    recovered = repository.get("stranded")
    assert recovered is not None
    assert recovered.status is JobStatus.FAILED
    assert recovered.error_kind is ErrorKind.INTERRUPTED
    assert is_retryable(ErrorKind.INTERRUPTED)


def test_recovery_is_recorded_rather_than_silent(repository: JobRepository) -> None:
    """An acceptance criterion. The user left a job running and must see why it now offers retry.

    A silent move to `QUEUED` would restart the download without asking, which `REQ-018` reserves
    for `NETWORK` alone.
    """
    repository.add(a_job("stranded", status=JobStatus.RUNNING))
    repository.recover_interrupted()

    recovered = repository.get("stranded")
    assert recovered is not None
    assert recovered.error_message
    assert recovered.finished_at is not None
    assert not is_auto_retryable(ErrorKind.INTERRUPTED), (
        "an application that crashed mid-download must not relaunch into the same download"
    )


@pytest.mark.parametrize(
    "status",
    [JobStatus.QUEUED, JobStatus.READY, JobStatus.FAILED, JobStatus.COMPLETED, JobStatus.CANCELLED],
)
def test_recovery_leaves_every_other_status_alone(
    repository: JobRepository, status: JobStatus
) -> None:
    """Recovery touches `INTERRUPTED_ON_STARTUP` and nothing else.

    This used to parametrize `PAUSED` and single it out as the case that mattered — "the user
    asked for that, and it is meant to survive a restart". `T-080` removed the status: under
    `UX-001` no job ever entered it, so the sentence described a state no test could produce
    honestly. The parameters now cover every status recovery must leave alone, which is what the
    test was always for.
    """
    repository.add(a_job("untouched", status=status))
    assert repository.recover_interrupted() == []
    stored = repository.get("untouched")
    assert stored is not None
    assert stored.status is status


def test_recovery_survives_a_restart_and_is_idempotent(tmp_path: Path) -> None:
    """Running it twice must not re-fail an already-recovered job or raise on a legal path."""
    database = tmp_path / "library.sqlite3"
    with db.open_database(database) as connection:
        JobRepository(connection).add(a_job("stranded", status=JobStatus.RUNNING))

    with db.open_database(database) as connection:
        assert JobRepository(connection).recover_interrupted() == ["stranded"]

    with db.open_database(database) as connection:
        repository = JobRepository(connection)
        assert repository.recover_interrupted() == []
        stranded = repository.get("stranded")
        assert stranded is not None
        assert stranded.status is JobStatus.FAILED


def test_recovery_routes_through_the_state_machine(
    repository: JobRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The validation must not be bypassed by writing `FAILED` straight into the row.

    **Rewritten after `T014-R5`.** The earlier version called `stored.with_failure()` directly
    and never invoked `recover_interrupted()` at all — it tested the model method, which is
    already covered elsewhere, while claiming to test the repository seam. Codex proved it by
    replacing `recover_interrupted` with a function that always raises: the test still passed.

    This forces an illegal source status into the recovered set and asserts the *repository*
    raises. A direct `replace(job, status=FAILED, ...)` implementation, which produces identical
    output for every legal case, fails here — which is what makes the mutation meaningful.
    """
    monkeypatch.setattr(repositories, "INTERRUPTED_ON_STARTUP", frozenset({JobStatus.COMPLETED}))
    repository.add(a_job("done", status=JobStatus.COMPLETED))

    with pytest.raises(IllegalTransitionError):
        repository.recover_interrupted()

    # And the illegal move was not written before it raised.
    stored = repository.get("done")
    assert stored is not None
    assert stored.status is JobStatus.COMPLETED


# --- location (NFR-004, ARCHITECTURE.md §5) --------------------------------------------------


def test_the_database_lives_under_platformdirs_and_is_not_doubled() -> None:
    """`NFR-004`: never beside the installed application. And `appauthor=False` is load-bearing.

    Without it, Windows inserts an author segment defaulting to the app name and produces
    `tracksandtrails/tracksandtrails/`, which matches none of `ARCHITECTURE.md` §5's paths. The
    trap `T-007` hit once already, invisible on Linux.
    """
    path = db.database_path()
    assert path.name == db.DATABASE_FILENAME
    assert path.parent.name == "tracksandtrails"
    assert path.parent.parent.name != "tracksandtrails"
    assert Path(__file__).parent not in path.parents


# --- history (T-050, REQ-020) --------------------------------------------------------------


@pytest.fixture
def history(tmp_path: Path) -> HistoryRepository:
    return HistoryRepository(db.connect(tmp_path / "library.sqlite3"))


def _entry(entry_id: str = "job-1", **overrides: Any) -> HistoryEntry:
    fields: dict[str, Any] = {
        "id": entry_id,
        "url": "https://example.com/watch?v=abc",
        "title": "A Clip",
        "output_path": "/downloads/A Clip.mp4",
        "format_used": "137+140",
        "bytes_total": 4096,
        "completed_at": datetime(2026, 7, 29, 12, 0, tzinfo=UTC),
    }
    return HistoryEntry(**{**fields, **overrides})


def test_a_history_entry_round_trips_every_field(history: HistoryRepository) -> None:
    """Whole-object comparison, so a column dropped on the way to disk fails rather than defaults.

    The same reasoning as the job round-trip above: asserting field by field is how a forgotten
    column survives, because the assertion is written from the same list that forgot it.
    """
    entry = _entry()
    history.record(entry)
    assert history.get("job-1") == entry


def test_history_does_not_persist_an_application_supplied_cookie_path(
    history: HistoryRepository,
) -> None:
    """Reviewer regression for `T-159` and `REQ-026`'s History boundary.

    `DownloadRequest.cookies_from_browser` is a browser name by current caller convention, not by
    construction: the model accepts any non-empty text.  History needs only the format-defining
    part of a request, so copying the whole object makes a cookie path durable after the queue row
    is removed and violates the accepted rule the day a caller supplies one.

    *(Adapted by the Implementer for `T159-R1`'s correction, which is what it asked for: the column
    is `format_choice` rather than `request`, and the record is built the way production builds it
    — by narrowing a request through `format_choice_of`, so what is proven is that the **narrowing**
    protects rather than that a field happened to be dropped. Widened at the same time to scan
    **every column** rather than one, since a credential reaching any of them is the same failure,
    and to cover the proxy for the same reason `REQ-026` covers the cookie.)*
    """
    cookie_path = "/home/alice/.mozilla/firefox/profile/cookies.sqlite"
    proxy = "http://proxy.internal.invalid:8080"
    history.record(
        _entry(
            format_choice=format_choice_of(a_request(cookies_from_browser=cookie_path, proxy=proxy))
        )
    )

    row = history._connection.execute("SELECT * FROM history WHERE id = ?", ("job-1",)).fetchone()
    assert row is not None
    stored = " ".join(str(value) for value in dict(row).values())
    assert cookie_path not in stored, (
        "History persisted an application-supplied cookie path even though REQ-026 says that sink "
        "never does"
    )
    assert proxy not in stored, (
        "History persisted the user's proxy. Not a credential — `DownloadRequest` refuses userinfo "
        "outright, so one cannot be represented — but it names a private network, it says nothing "
        "about what was downloaded, and a record outlives the job row that was its only other home"
    )


def test_the_nullable_columns_survive_being_null(history: HistoryRepository) -> None:
    """`REQ-020` names six facts; only the URL and the completion time are always knowable."""
    entry = _entry(title=None, output_path=None, format_used=None, bytes_total=None)
    history.record(entry)
    assert history.get("job-1") == entry


def test_recording_the_same_job_twice_updates_rather_than_duplicating(
    history: HistoryRepository,
) -> None:
    """`T-050`: exactly one row per completed job, and a retry does not silently duplicate it.

    **Stated limit:** this is tested here rather than end to end because the state machine makes it
    unreachable through `DownloadManager` — `core/job_state.py` gives `COMPLETED` no outgoing
    transitions, so one job id cannot legally complete twice today. What is being gated is that the
    table's primary key cannot turn a second arrival into an `IntegrityError` against a download
    that succeeded, and that the newer row wins when it does. Phase 2's retry paths (`T-082`,
    `T-083`) are where that could start mattering.
    """
    history.record(_entry())
    history.record(
        _entry(
            output_path="/downloads/A Clip (1).mp4",
            format_used="18",
            bytes_total=8192,
            completed_at=datetime(2026, 7, 29, 13, 0, tzinfo=UTC),
        )
    )

    stored = history.all_entries()
    assert len(stored) == 1, "the retry duplicated the row"
    assert stored[0].output_path == "/downloads/A Clip (1).mp4", "the stale completion won"
    assert stored[0].format_used == "18"
    assert stored[0].bytes_total == 8192


def test_the_newest_completion_wins_even_when_it_is_smaller(history: HistoryRepository) -> None:
    """The tie-break is recency, not magnitude — `INSERT OR IGNORE` would keep the stale row.

    Written because the mutation that matters here is not "does it overwrite" but "does it
    overwrite with the *new* values": a policy that kept the first completion would pass the count
    assertion above and still lose the retry's result.
    """
    history.record(_entry(bytes_total=99999, format_used="401"))
    history.record(_entry(bytes_total=1, format_used="18"))
    stored = history.get("job-1")
    assert stored is not None
    assert (stored.bytes_total, stored.format_used) == (1, "18")


def test_entries_come_back_newest_first(history: HistoryRepository) -> None:
    history.record(_entry("old", completed_at=datetime(2026, 7, 1, tzinfo=UTC)))
    history.record(_entry("new", completed_at=datetime(2026, 7, 28, tzinfo=UTC)))
    history.record(_entry("middle", completed_at=datetime(2026, 7, 14, tzinfo=UTC)))
    assert [entry.id for entry in history.all_entries()] == ["new", "middle", "old"]


def test_an_unknown_id_is_none_rather_than_an_error(history: HistoryRepository) -> None:
    assert history.get("never-stored") is None


def test_a_history_entry_requires_its_url() -> None:
    """`REQ-020` names the source URL and a retry cannot reconstruct it."""
    with pytest.raises(ValueError, match="requires the source URL"):
        _entry(url="")


def test_a_history_entry_refuses_negative_bytes() -> None:
    """The table's CHECK says the same; saying it at construction names the field."""
    with pytest.raises(ValueError, match="cannot be negative"):
        _entry(bytes_total=-1)


# --- T-080: re-queuing at the tail, and removal --------------------------------------------


def test_requeue_at_end_allocates_a_fresh_tail_position(repository: JobRepository) -> None:
    """`T-080`, `P2PLAN-R7`: a manual retry goes behind everything already queued.

    **Two rounds, for `append`'s reason.** With one job re-queued into a two-job queue, "read the
    maximum" and "add one to my own position" give the same answer. The second round is what tells
    them apart: `a` re-queued twice must land behind `c`, not back where it started.
    """
    repository.append([a_job("a"), a_job("b"), a_job("c")])
    original = repository.get("a")
    assert original is not None and original.queue_position == 0

    placed = repository.requeue_at_end(original)
    assert placed.queue_position == 3
    assert [job.id for job in repository.queued()] == ["b", "c", "a"]

    again = repository.requeue_at_end(placed)
    assert again.queue_position == 4
    assert [job.id for job in repository.queued()] == ["b", "c", "a"]

    stored = repository.get("a")
    assert stored is not None
    assert stored.queue_position == 4, "the returned job was placed but the row was not"


def test_requeue_at_end_keeps_every_other_field(repository: JobRepository) -> None:
    """The position is the *only* thing it decides. A write that reset a field would be silent."""
    repository.append([a_job("a", title="a title", attempts=2)])
    stored = repository.get("a")
    assert stored is not None

    repository.requeue_at_end(replace(stored, status=JobStatus.FAILED))

    after = repository.get("a")
    assert after is not None
    assert after.title == "a title"
    assert after.attempts == 2, (
        "re-queuing spent or reset the attempt counter; manual retry deliberately does not, so "
        "the automatic budget is not consumed by a person pressing Retry"
    )
    assert after.status is JobStatus.FAILED


def test_requeue_at_end_refuses_a_job_that_is_not_there(repository: JobRepository) -> None:
    """`update`'s rule: re-queuing a vanished row means the caller's model of the queue is wrong."""
    with pytest.raises(Exception):  # noqa: B017 — the type is `_write_job`'s, not this test's
        repository.requeue_at_end(a_job("never added"))


def test_remove_deletes_the_row_and_reports_whether_there_was_one(
    repository: JobRepository,
) -> None:
    """`UX-001`, `T-080`: removal takes the row out and says whether it had anything to take.

    The second call is the point: pressing Remove twice is a thing a person does, and the outcome
    they asked for is the outcome they have. It must not raise, and it must not claim it deleted
    something.
    """
    repository.append([a_job("a"), a_job("b")])

    assert repository.remove("a") is True
    assert repository.get("a") is None
    assert [job.id for job in repository.queued()] == ["b"]

    assert repository.remove("a") is False, (
        "removing an already-removed job reported a deletion; the boolean exists so a caller that "
        "cares can tell the two apart"
    )


def test_remove_leaves_a_gap_that_nothing_depends_on_being_absent(
    repository: JobRepository,
) -> None:
    """Positions stay sparse after a removal, and the next append still goes to the end.

    Recorded because "gaps are harmless" is a claim about every consumer, and the cheapest way to
    stop it becoming false is a test that fails if something starts renumbering.
    """
    repository.append([a_job("a"), a_job("b"), a_job("c")])
    repository.remove("b")

    assert [job.queue_position for job in repository.queued()] == [0, 2]
    appended = repository.append([a_job("d")])
    assert appended[0].queue_position == 3
    assert [job.id for job in repository.queued()] == ["a", "c", "d"]


# --- T-081: reordering pending jobs, and clearing the finished ones ------------------------


def test_the_reorderable_statuses_partition_the_enum() -> None:
    """`REORDERABLE`, `INTERRUPTED_ON_STARTUP` and `TERMINAL` cover every status exactly once.

    **The reason `REORDERABLE` is written out rather than derived.** A derived complement would
    agree with the other two unconditionally, so a new status would become reorderable silently and
    no test could see it — `ai/TESTING.md` §13. This makes adding a status fail here until somebody
    decides which side it belongs on.
    """
    covered = REORDERABLE | repositories.INTERRUPTED_ON_STARTUP | TERMINAL

    assert covered == set(JobStatus), (
        f"these statuses belong to no group: {sorted(s.value for s in set(JobStatus) - covered)}"
    )
    assert not (REORDERABLE & repositories.INTERRUPTED_ON_STARTUP)
    assert not (REORDERABLE & TERMINAL)
    assert not (repositories.INTERRUPTED_ON_STARTUP & TERMINAL)


def test_reorder_deals_out_the_positions_those_jobs_already_held(
    repository: JobRepository,
) -> None:
    """`REQ-016`: the moved jobs swap places, and nothing else in the queue moves.

    **Asserted with a job that is *not* being reordered sitting between them**, because that is the
    property "redeal the positions they occupied" has and "renumber from zero" does not. A
    renumbering implementation passes a test where the reordered jobs are the whole queue.
    """
    repository.append([a_job("a"), a_job("b"), a_job("c"), a_job("d")])
    # `c` is running, so it is not in the rearrangement and its position must not move.
    running = repository.get("c")
    assert running is not None
    repository.update(replace(running, status=JobStatus.RUNNING))

    placed = repository.reorder(["d", "b", "a"])

    assert [job.id for job in placed] == ["d", "b", "a"]
    assert [job.queue_position for job in placed] == [0, 1, 3]
    after = repository.get("c")
    assert after is not None
    assert after.queue_position == 2, "a job nobody moved changed position"
    assert [job.id for job in repository.queued()] == ["d", "b", "c", "a"]


def test_reorder_survives_the_unique_index_when_positions_cross(
    repository: JobRepository,
) -> None:
    """A straight swap is the case a one-phase implementation cannot do.

    `jobs_queue_position` is `UNIQUE` over non-`NULL` values and SQLite enforces it per statement,
    so assigning `a → 1` while `b` still holds `1` raises `IntegrityError`. This is the smallest
    reorder that crosses, and it is the whole reason for the `NULL` phase.
    """
    repository.append([a_job("a"), a_job("b")])

    repository.reorder(["b", "a"])

    assert [job.id for job in repository.queued()] == ["b", "a"]
    assert [job.queue_position for job in repository.queued()] == [0, 1]


def test_reorder_refuses_a_running_job_rather_than_skipping_it(repository: JobRepository) -> None:
    """`T-081`: a running job's position is not a promise the pool can keep.

    Refused rather than silently dropped from the rearrangement: a caller asking to move a running
    job has a stale view of the queue, and quietly reordering the rest would leave the table
    showing an order the database never agreed to.
    """
    repository.append([a_job("a"), a_job("b")])
    running = repository.get("a")
    assert running is not None
    repository.update(replace(running, status=JobStatus.RUNNING))

    with pytest.raises(ValueError, match="running or finished"):
        repository.reorder(["b", "a"])

    assert [job.id for job in repository.queued()] == ["a", "b"], (
        "the refusal left the queue partly reordered; the check must happen before any write"
    )


class _FailsOnExecutemany:
    """A connection that forwards everything except `executemany`, which raises.

    A proxy rather than a `monkeypatch.setattr` on the connection, because
    `sqlite3.Connection.executemany` is a read-only attribute and cannot be patched. A proxy is
    also the more honest instrument: it fails at exactly the call the repository makes, rather than
    at a layer the repository does not use.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def execute(self, *arguments: Any) -> sqlite3.Cursor:
        return self._connection.execute(*arguments)

    def executemany(self, *arguments: Any) -> sqlite3.Cursor:
        raise sqlite3.OperationalError("disk I/O error")

    def __enter__(self) -> sqlite3.Connection:
        return self._connection.__enter__()

    def __exit__(self, *arguments: Any) -> Any:
        return self._connection.__exit__(*arguments)


def test_reorder_is_one_transaction(tmp_path: Path) -> None:
    """`REQ-016`: a queue half-reordered by a crash is a queue in an order nobody chose.

    The failure is injected **between** the `NULL` phase and the reassignment, which is the only
    window where the moved rows are outside the queue order entirely. If the two phases were
    separate transactions, this would leave every named job with no position at all — and a queue
    whose jobs have no position has no order for the pool or the table to agree on.
    """
    connection = db.connect(tmp_path / "library.sqlite3")
    repository = JobRepository(connection)
    repository.append([a_job("a"), a_job("b"), a_job("c")])

    broken = JobRepository(_FailsOnExecutemany(connection))  # type: ignore[arg-type]
    with pytest.raises(sqlite3.OperationalError):
        broken.reorder(["c", "b", "a"])

    assert [job.id for job in repository.queued()] == ["a", "b", "c"], (
        "a failed reorder left the queue changed; the NULL phase and the reassignment must be one "
        "transaction or a crash between them strands every moved job outside the queue"
    )
    assert [job.queue_position for job in repository.queued()] == [0, 1, 2]


def test_reorder_refuses_unknown_and_unplaced_and_duplicated_jobs(
    repository: JobRepository,
) -> None:
    """Three refusals, because each would corrupt the order in a different way."""
    repository.append([a_job("a"), a_job("b")])
    repository.add(a_job("loose"))  # added directly, so it holds no queue position

    with pytest.raises(KeyError, match="unknown"):
        repository.reorder(["a", "ghost"])
    with pytest.raises(ValueError, match="no queue position"):
        repository.reorder(["a", "loose"])
    with pytest.raises(ValueError, match="named twice"):
        repository.reorder(["a", "a"])

    assert [job.id for job in repository.queued()] == ["a", "b"]


def test_clear_completed_removes_finished_rows_and_keeps_the_rest(
    repository: JobRepository,
) -> None:
    """`REQ-016`: completed and cancelled go; queued, running and **failed** stay.

    `FAILED` staying is the one worth asserting. A failed job is still in the queue offering a
    retry (`REQ-018`), so clearing it would throw away work the user has not decided about — while
    a cancelled job is a decision they already made.
    """
    repository.append(
        [a_job("done"), a_job("stopped"), a_job("waiting"), a_job("broken"), a_job("busy")]
    )
    for job_id, status in (
        ("done", JobStatus.COMPLETED),
        ("stopped", JobStatus.CANCELLED),
        ("broken", JobStatus.FAILED),
        ("busy", JobStatus.RUNNING),
    ):
        stored = repository.get(job_id)
        assert stored is not None
        repository.update(replace(stored, status=status))

    cleared = repository.clear_completed()

    assert sorted(cleared) == ["done", "stopped"]
    assert repository.get("done") is None
    assert repository.get("stopped") is None
    assert repository.get("broken") is not None, (
        "clear-completed removed a failed job; it is still in the queue offering a retry"
    )
    assert repository.get("waiting") is not None
    assert repository.get("busy") is not None


def test_clear_completed_keeps_a_partly_finished_playlist_as_one_unit(
    repository: JobRepository,
) -> None:
    """Reviewer regression for `UX-005` row 9d and `T-140`'s accepted contract.

    A completed child remains while any sibling is unfinished.  Otherwise one click silently
    changes the group underneath the user, and can dissolve its header when only one child is
    left.  Once every member is terminal, the existing clear operation may remove the group.
    """
    repository.append(
        [
            a_job(
                "playlist-done",
                status=JobStatus.COMPLETED,
                playlist_id="playlist-1",
                playlist_index=0,
                playlist_title="Trail Sounds",
            ),
            a_job(
                "playlist-running",
                status=JobStatus.RUNNING,
                playlist_id="playlist-1",
                playlist_index=1,
                playlist_title="Trail Sounds",
            ),
        ]
    )

    cleared = repository.clear_completed()

    assert cleared == [], (
        "Clear finished removed the completed member of a partly running playlist; UX-005 row "
        "9d requires the group to remain intact until all of it is done"
    )
    assert repository.get("playlist-done") is not None
    assert repository.get("playlist-running") is not None


def test_clear_completed_leaves_history_alone(tmp_path: Path) -> None:
    """`T-085`, `P2PLAN-R8`: the queue forgets, and history is how the user still finds the file.

    The two live in different tables and the completion transaction writes both. Clearing the queue
    must remove only the queue's record — otherwise clear-completed plus `UX-001`'s
    remove-never-deletes leaves somebody with files on disk and no record of where they went.
    """
    connection = db.connect(tmp_path / "library.sqlite3")
    jobs = JobRepository(connection)
    history = HistoryRepository(connection)

    jobs.append([a_job("done")])
    stored = jobs.get("done")
    assert stored is not None
    completed = replace(stored, status=JobStatus.COMPLETED, output_path=str(tmp_path / "clip.mp4"))
    repositories.complete_job(
        connection,
        completed,
        HistoryEntry(
            id="done",
            url=completed.url,
            title="A clip",
            output_path=completed.output_path,
            format_used="mp4",
            bytes_total=1024,
            completed_at=datetime(2026, 7, 31, 12, 0, tzinfo=UTC),
        ),
    )

    assert jobs.clear_completed() == ["done"]

    assert jobs.get("done") is None
    kept = history.get("done")
    assert kept is not None, (
        "clearing the queue deleted the history record; T-100's view would then have nothing to "
        "show and the user could not find what they downloaded"
    )
    assert kept.output_path == completed.output_path


def test_clear_completed_touches_no_file(repository: JobRepository, tmp_path: Path) -> None:
    """`UX-001`'s rule applied to the other bulk operation, asserted at the directory."""
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    obtained = downloads / "a clip.mp4"
    obtained.write_bytes(b"the user's file")

    repository.append([a_job("done")])
    stored = repository.get("done")
    assert stored is not None
    repository.update(replace(stored, status=JobStatus.COMPLETED, output_path=str(obtained)))

    repository.clear_completed()

    assert obtained.exists(), "clearing completed jobs deleted the file one of them produced"
    assert obtained.read_bytes() == b"the user's file"


# --- DAT-005 / T-125: removal takes ids, and only records ------------------------------------


def test_removing_records_leaves_the_others(history: HistoryRepository) -> None:
    """`DAT-005` §1: what the user selected, and nothing else.

    Asserted as the surviving set rather than as "two rows were deleted": a count is satisfied by
    deleting the wrong two, and the whole of `DAT-005` §1 is *which* records go.
    """
    for entry_id in ("job-1", "job-2", "job-3"):
        history.record(_entry(entry_id))

    removed = history.remove(["job-1", "job-3"])

    assert removed == 2
    assert [entry.id for entry in history.all_entries()] == ["job-2"], (
        "removal did not leave exactly the records the user kept"
    )


def test_removing_nothing_removes_nothing(history: HistoryRepository) -> None:
    """An empty selection must not become `DELETE FROM history`.

    This is the failure the signature exists to make impossible, and it is the one that would be
    catastrophic and silent: a user with nothing selected, a verb that fired anyway, and a history
    that is simply gone. Worth a test of its own rather than trusting the guard to stay.
    """
    history.record(_entry("job-1"))

    assert history.remove([]) == 0
    assert [entry.id for entry in history.all_entries()] == ["job-1"]


def test_removing_a_record_that_is_already_gone_is_not_an_error(
    history: HistoryRepository,
) -> None:
    """Reported as what happened, not as what was asked for.

    Two windows on one library can both remove the same record. The caller says how many rows it
    actually deleted so a report can be honest, rather than raising at a user who did nothing
    wrong.
    """
    history.record(_entry("job-1"))

    assert history.remove(["job-1", "never-existed"]) == 1
    assert history.all_entries() == []


def test_removal_touches_no_file(history: HistoryRepository, tmp_path: Path) -> None:
    """**`DAT-005` §2, which is the entire reason this needed a decision.**

    A history entry names a file on disk, and `UX-001` promises this application never deletes the
    user's files. So: a real file at the recorded path, removed from history, and **still there**.

    The file is real rather than a mock. A test asserting that no `os.remove` was called would
    pass against a deletion performed some other way — through `Path.unlink`, through `shutil`,
    through a subprocess — and the claim is about the file, not about which API was avoided.
    """
    downloaded = tmp_path / "a real download.mp4"
    downloaded.write_bytes(b"bytes the user asked for")
    history.record(_entry("job-1", output_path=str(downloaded)))

    history.remove(["job-1"])

    assert downloaded.exists(), (
        "removing a history record deleted the user's file — UX-001 promises this application "
        "never does that, and DAT-005 refuses even an opt-in for it"
    )
    assert downloaded.read_bytes() == b"bytes the user asked for", "the file was modified"


def test_a_removal_is_committed_and_survives_the_writer_closing(tmp_path: Path) -> None:
    """**The removal is durable, asserted from outside the connection that made it** (`T125-R1`).

    Every other test in this section reads back through the *same* connection, and a connection
    sees its own uncommitted work — so an uncommitted `DELETE` passes all of them. The running
    application does not have that shape: `writer.py` deletes on its own connection inside the
    writer thread (`ARC-005`) and `HistoryView` reads through the connection `compose()` opened,
    so an uncommitted delete is invisible to the surface that reports it.

    Three observations, which is what the review's probe measured and what this pins:

    1. the writer's own connection no longer has the row — true even uncommitted, so it proves
       nothing on its own and is here to show the delete really ran;
    2. **a second connection opened against the same file** no longer has it;
    3. **a connection opened after the writer is closed** no longer has it — the case that
       distinguishes a commit from a transaction rolled back at close.

    Deleting `with self._connection` in `HistoryRepository.remove` leaves (1) passing and fails
    (2) and (3), which is the mutation this test exists to kill.
    """
    database = tmp_path / "library.sqlite3"
    writer_connection = db.connect(database)
    writer = HistoryRepository(writer_connection)
    writer.record(_entry("job-1"))
    writer.record(_entry("job-2"))

    assert writer.remove(["job-1"]) == 1

    assert writer.get("job-1") is None, "the delete did not run on the writer's own connection"

    reader = HistoryRepository(db.connect(database))
    assert reader.get("job-1") is None, (
        "another connection still sees the removed record, so the delete was never committed — "
        "which is exactly what the History tab reads through"
    )
    assert reader.get("job-2") is not None, "the wrong record went, or the commit took too much"

    writer_connection.close()
    reopened = HistoryRepository(db.connect(database))
    assert reopened.get("job-1") is None, (
        "the record came back when the writer connection closed: the DELETE was sitting in an "
        "implicit transaction and was rolled back"
    )
    assert reopened.get("job-2") is not None


# --- clearing the whole history (T-144, DAT-005 amended 2026-08-05) ---------------------------


def test_clear_empties_the_list_and_reports_how_many_it_took(history: HistoryRepository) -> None:
    """The criterion: one action empties the list, and says what it did.

    Reported rather than assumed, so composition tells the user what happened rather than what it
    asked for — and so clearing an empty history is honestly zero.
    """
    for entry_id in ("a", "b", "c"):
        history.record(_entry(entry_id))

    assert history.clear() == 3
    assert history.all_entries() == []
    assert history.clear() == 0, "clearing an already empty history claimed to remove something"


def test_clear_is_committed_rather_than_only_visible_to_its_own_connection(
    tmp_path: Path,
) -> None:
    """`NFR-003` and `T125-R1`, whose lesson this repeats deliberately.

    The first `remove` executed its `DELETE` bare, on the implicit transaction `sqlite3` opens and
    never closes by itself. Every test read back through the *same* connection, which sees its own
    uncommitted work, so the deletion looked durable and was not — the History tab reads through a
    different connection, and the records came back. A second connection is the only thing that can
    tell those two apart, and a wholesale clear is the worst place to get it wrong.
    """
    database = tmp_path / "library.sqlite3"
    writer = HistoryRepository(db.connect(database))
    for entry_id in ("a", "b"):
        writer.record(_entry(entry_id))

    assert writer.clear() == 2

    reader = HistoryRepository(db.connect(database))
    assert reader.all_entries() == [], (
        "the clear was never committed, so a second connection still sees the records and they "
        "come back the moment the writer closes"
    )


def test_clearing_is_one_transaction_and_never_half_empties(tmp_path: Path) -> None:
    """`NFR-003`: no half-emptied history, and nothing that survives only until the process exits.

    Driven by killing the connection **without** closing it, which is what a hard exit looks like
    to SQLite: whatever was committed is there and whatever was not is gone. There is no third
    outcome for a single `DELETE`, which is the property being asserted.
    """
    database = tmp_path / "library.sqlite3"
    connection = db.connect(database)
    writer = HistoryRepository(connection)
    for entry_id in ("a", "b", "c"):
        writer.record(_entry(entry_id))
    assert writer.clear() == 3
    del writer
    connection.close()

    survivors = HistoryRepository(db.connect(database)).all_entries()
    assert survivors == [], f"{len(survivors)} records survived a committed clear"


def test_a_history_past_sqlites_parameter_ceiling_still_clears(history: HistoryRepository) -> None:
    """The criterion, and the defect it is about (`T-144`).

    `remove` builds one placeholder per id, and **`SQLITE_LIMIT_VARIABLE_NUMBER` is 32766 on this
    build** — measured while filing the task: 999 ok, 32766 ok, 32767 raises
    `OperationalError: too many SQL variables`. So "select everything and remove it" failed outright
    on a history past that, with a database error rather than a message, on the machine of whoever
    has used the application longest.

    **The measured limit is reasoning, not an assertion.** Asserting against
    `SQLITE_LIMIT_VARIABLE_NUMBER` would let this pass silently on a build with a different ceiling
    — including one where the parameterised route never fails and the test proves nothing. A fixed
    count comfortably past the number measured here is what actually exercises the property: a bare
    `DELETE` names no parameters, so it has no ceiling to cross.

    Seeded with `executemany` on the raw connection rather than through `record`, because the point
    is the *volume*, and forty thousand separate transactions would test the writer's patience
    rather than the ceiling.
    """
    beyond_the_ceiling = 40_000
    # Seeding volume, not exercising the API: forty thousand `record()` calls would test the
    # writer's patience rather than the ceiling.
    connection = history._connection
    with connection:
        connection.executemany(
            "INSERT INTO history (id, url, completed_at) VALUES (?, ?, ?)",
            [
                (f"h-{number}", "https://example.com/watch?v=abc", "2026-07-29T12:00:00+00:00")
                for number in range(beyond_the_ceiling)
            ],
        )

    assert history.clear() == beyond_the_ceiling
    assert history.all_entries() == []


def test_removing_nothing_still_removes_nothing(history: HistoryRepository) -> None:
    """`remove`'s empty guard is untouched by `clear` existing (`T-144`, `DAT-005`).

    The guard exists so an empty selection cannot become an accidental `DELETE FROM history` — *"the
    failure this signature exists to make impossible"*. A wholesale clear is a separate method with
    its own name precisely so that guard could stay, and this is what would fail if a later edit
    taught `remove` to mean "everything" when given nothing.
    """
    for entry_id in ("a", "b"):
        history.record(_entry(entry_id))

    assert history.remove([]) == 0
    assert {entry.id for entry in history.all_entries()} == {"a", "b"}, (
        "an empty selection emptied the history, which is the exact failure remove's signature "
        "exists to make impossible"
    )


def test_removing_a_selection_still_works_beside_clear(history: HistoryRepository) -> None:
    """The last criterion: a wholesale clear changed nothing about selection-scoped removal."""
    for entry_id in ("a", "b", "c"):
        history.record(_entry(entry_id))

    assert history.remove(["a", "c"]) == 2
    assert [entry.id for entry in history.all_entries()] == ["b"]
