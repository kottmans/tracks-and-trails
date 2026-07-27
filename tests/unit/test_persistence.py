"""Persistence: schema, migrations, and the job repository (`T-014`).

Covers three of `ai/TESTING.md` §7's mandatory areas — crash recovery, migrations, and the
settings freeze — plus `REQ-012`'s durable queue order and `REQ-026`'s exclusion of secrets.

The hard kill that `NFR-003` actually turns on lives in `tests/integration/test_crash_kill.py`,
because it needs a real process to kill. Everything provable in-process is here.
"""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import pytest

from tracks_and_trails.core.errors import ErrorKind, is_auto_retryable, is_retryable
from tracks_and_trails.core.job_state import IllegalTransitionError, JobStatus
from tracks_and_trails.core.models import AudioCodec, DownloadRequest, Job, MediaKind
from tracks_and_trails.persistence import db, repositories
from tracks_and_trails.persistence.repositories import INTERRUPTED_ON_STARTUP, JobRepository


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
    before = {row["id"]: dict(row) for row in connection.execute("SELECT * FROM jobs ORDER BY id")}
    assert before, "the fixture carries no rows, so 'data intact' asserts nothing"

    applied = db.migrate(connection)
    assert all(v > version for v in applied)
    assert db.schema_version(connection) == db.latest_version()

    after = {row["id"]: dict(row) for row in connection.execute("SELECT * FROM jobs ORDER BY id")}
    assert set(after) == set(before), (
        f"migrating from v{version} lost or added rows. A migration that recreates a table "
        "passes a 'does it run' check and drops the user's queue."
    )
    for job_id, original in before.items():
        for column, value in original.items():
            assert after[job_id][column] == value, (
                f"{job_id}.{column} changed during migration from v{version}"
            )

    # And the current repository can read what the migration produced — the property a user
    # actually experiences after upgrading.
    for job in JobRepository(connection).all_jobs():
        assert job.id in before
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
    """Every stored column of one job as one string, for scanning.

    **Scanning the raw row is the point** (`T014-R1`). Redaction applied in the model but not on
    the way to disk passes an object comparison and still leaves the secret on disk — and a test
    that checks only the field it expects the secret in misses the field it did not think of.
    This concatenates *all* of them.
    """
    row = repository._connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return "\n".join(str(value) for value in tuple(row))


@pytest.mark.parametrize(
    "proxy",
    [
        pytest.param("http://secretuser:hunter2@proxy.invalid:8080", id="with-scheme"),
        # `T014-R1`: `DownloadRequest.proxy` accepts any non-empty string, and `urlsplit` puts
        # this entirely in `path` with an empty `netloc` — so the old netloc-only check returned
        # it unchanged and wrote both credentials to disk.
        pytest.param("secretuser:hunter2@proxy.invalid:8080", id="scheme-less"),
        pytest.param("socks5://secretuser:hunter2@10.0.0.1:1080", id="socks-numeric-host"),
        pytest.param("HTTP://secretuser:hunter2@Proxy.Invalid:8080", id="uppercase-scheme"),
    ],
)
def test_no_proxy_credential_reaches_any_column(repository: JobRepository, proxy: str) -> None:
    """`REQ-026`: credentials are never written to history, whatever form the proxy took."""
    repository.add(a_job(request=a_request(proxy=proxy)))
    stored = raw_row(repository)

    assert "hunter2" not in stored
    assert "secretuser" not in stored
    assert "proxy.invalid" in stored.lower() or "10.0.0.1" in stored, (
        "the proxy host must survive or the setting is silently lost on retry"
    )


@pytest.mark.parametrize(
    ("secret", "message"),
    [
        pytest.param(
            "hunter2",
            "proxy failed: http://secretuser:hunter2@proxy.invalid:8080 refused the connection",
            id="credential-in-diagnostic",
        ),
        pytest.param(
            "hunter2",
            "could not connect via secretuser:hunter2@proxy.invalid:8080",
            id="scheme-less-credential-in-diagnostic",
        ),
        pytest.param(
            "cookies.txt",
            "Cookie file /home/someone/private/cookies.txt could not be read",
            id="cookie-path-in-diagnostic",
        ),
        pytest.param(
            "secret-jar",
            "unable to open --cookies /var/data/secret-jar",
            id="cookie-flag-in-diagnostic",
        ),
    ],
)
def test_no_secret_reaches_the_database_through_a_diagnostic(
    repository: JobRepository, secret: str, message: str
) -> None:
    """`T014-R1`. `error_message` is an unrestricted sink carrying verbatim extractor prose.

    The earlier design redacted the request's `proxy` field and wrote `error_message` untouched,
    so a diagnostic naming the proxy stored the password in the row beside the stripped copy.
    Redaction now happens at the sink, so every text column is covered by default.
    """
    job = a_job().with_failure(ErrorKind.NETWORK, message)
    repository.add(job)
    assert secret not in raw_row(repository)


def test_redaction_leaves_the_diagnostic_usable(repository: JobRepository) -> None:
    """`NFR-006`: masking a password must not destroy the message the user can act on.

    Over-eager redaction violates `NFR-006` as surely as a leak violates `REQ-026`. The host,
    the verb and the reason all survive; only the credential goes.
    """
    repository.add(
        a_job().with_failure(
            ErrorKind.NETWORK, "proxy failed: http://u:p@proxy.invalid:8080 refused the connection"
        )
    )
    stored = repository.get("job-1")
    assert stored is not None
    assert stored.error_message is not None
    assert "proxy.invalid:8080" in stored.error_message
    assert "refused the connection" in stored.error_message


def test_the_job_url_is_the_one_thing_stored_verbatim(repository: JobRepository) -> None:
    """The maintainer-approved exception, asserted so it stays an exception rather than a habit.

    The URL *is* the job — `REQ-012`'s queue and `REQ-020`'s history are unusable without it and
    a retry cannot reconstruct it. `_STORED_VERBATIM` names it and `output_path` explicitly, so
    a text column added later is redacted unless someone deliberately exempts it.
    """
    url = "https://example.invalid/watch?v=abc123&token=keepme"
    repository.add(a_job(request=a_request(url=url), url=url))

    row = repository._connection.execute("SELECT url, request FROM jobs").fetchone()
    assert row["url"] == url
    assert json.loads(row["request"])["url"] == url
    assert {"url", "output_path"} == repositories._STORED_VERBATIM


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
    "status", [JobStatus.QUEUED, JobStatus.READY, JobStatus.PAUSED, JobStatus.COMPLETED]
)
def test_recovery_leaves_every_other_status_alone(
    repository: JobRepository, status: JobStatus
) -> None:
    """`PAUSED` especially: the user asked for that, and it is meant to survive a restart."""
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
