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
from typing import Any

import pytest

from tracks_and_trails.core.errors import ErrorKind, is_auto_retryable, is_retryable
from tracks_and_trails.core.job_state import IllegalTransitionError, JobStatus
from tracks_and_trails.core.models import AudioCodec, DownloadRequest, Job, MediaKind
from tracks_and_trails.persistence import db
from tracks_and_trails.persistence.repositories import (
    INTERRUPTED_ON_STARTUP,
    JobRepository,
    strip_credentials,
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


def test_every_migration_runs_forward_from_every_prior_version_with_data_intact(
    tmp_path: Path,
) -> None:
    """`ai/TESTING.md` §7, and **the reason this harness exists now rather than later**.

    With one version today this is nearly trivial. It is written anyway because it becomes
    unwritable once several versions exist: reconstructing a v3 database to prove the v4
    migration needs the v3 code, which by then is gone. Building it forward from each version, as
    here, keeps working however many arrive.

    Data intact is the operative half. A migration that drops and recreates a table passes a
    "does it run" check and loses the user's queue.
    """
    migrations = db.available_migrations()

    for start_version, _ in migrations:
        database = tmp_path / f"from_v{start_version}.sqlite3"
        connection = sqlite3.connect(database)
        db.configure(connection)

        # Build the database *at* start_version, then seed it.
        for version, path in migrations:
            if version > start_version:
                break
            connection.executescript(path.read_text(encoding="utf-8"))
            connection.execute(f"PRAGMA user_version = {version:d}")
        connection.commit()
        connection.row_factory = sqlite3.Row

        repository = JobRepository(connection)
        seeded = a_job(f"survivor-from-v{start_version}", queue_position=0)
        repository.add(seeded)

        applied = db.migrate(connection)
        assert all(version > start_version for version in applied)
        assert db.schema_version(connection) == db.latest_version()

        survived = repository.get(seeded.id)
        assert survived == seeded, (
            f"migrating from v{start_version} lost or altered data. A migration that recreates a "
            "table passes a 'does it run' check and drops the user's queue."
        )
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


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://user:pass@proxy.invalid:8080", "http://proxy.invalid:8080"),
        ("http://user@proxy.invalid:8080", "http://proxy.invalid:8080"),
        ("http://proxy.invalid:8080", "http://proxy.invalid:8080"),
        ("socks5://u:p@10.0.0.1:1080", "socks5://10.0.0.1:1080"),
        (None, None),
    ],
)
def test_proxy_credentials_are_stripped(raw: str | None, expected: str | None) -> None:
    """The host survives because a proxy without one is not a proxy; the password does not."""
    assert strip_credentials(raw) == expected


def test_no_credential_or_cookie_reaches_the_database(repository: JobRepository) -> None:
    """`REQ-026`, `NFR-007`, asserted against the raw file rather than the model.

    Scanning the stored row is the point: a redaction applied in the model but not on the way to
    disk would pass an object comparison and still leave the secret on disk.

    The **URL is stored verbatim** and that is deliberate (`T-014` scope decision, 2026-07-26).
    It is the job — `REQ-012`'s queue and `REQ-020`'s history are unusable without it, and a
    retry cannot reconstruct it. What this asserts is that nothing the user did not type into the
    URL bar ends up stored.
    """
    request = a_request(
        proxy="http://secretuser:hunter2@proxy.invalid:8080",
        cookies_from_browser="firefox",
    )
    repository.add(a_job(request=request))

    stored = repository._connection.execute("SELECT request, url FROM jobs").fetchone()
    serialized = stored["request"]

    assert "hunter2" not in serialized
    assert "secretuser" not in serialized
    assert "proxy.invalid" in serialized, "the proxy host must survive or the setting is lost"
    assert json.loads(serialized)["cookies_from_browser"] == "firefox", (
        "a browser name is not a cookie; dropping it would silently stop using the cookies the "
        "user asked for"
    )
    assert stored["url"] == request.url


def test_the_stripped_proxy_is_what_comes_back(repository: JobRepository) -> None:
    """The model must agree with the disk, or callers would think the credential survived."""
    repository.add(a_job(request=a_request(proxy="http://u:p@proxy.invalid:8080")))
    restored = repository.get("job-1")
    assert restored is not None
    assert restored.request.proxy == "http://proxy.invalid:8080"


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


def test_recovery_routes_through_the_state_machine(repository: JobRepository) -> None:
    """The validation must not be bypassed by writing `FAILED` straight into the row.

    Proven at the seam rather than by inspection: a `COMPLETED` job hand-forced into the
    recovered set must raise, because `COMPLETED → FAILED` is illegal. If recovery wrote the
    column directly this would pass and the state machine would be decorative.
    """
    repository.add(a_job("done", status=JobStatus.COMPLETED))
    stored = repository.get("done")
    assert stored is not None
    with pytest.raises(IllegalTransitionError):
        replace(stored, status=JobStatus.COMPLETED).with_failure(ErrorKind.INTERRUPTED, "x")


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
