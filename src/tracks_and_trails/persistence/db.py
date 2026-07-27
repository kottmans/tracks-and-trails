"""Connection setup, WAL mode, and the forward-migration runner (`T-014`, `DAT-001`).

Three things live here and each exists for a stated reason.

**WAL mode** is `DAT-001`'s whole justification for choosing SQLite. The queue takes frequent
transactional row updates during downloads and must not corrupt on a hard kill (`NFR-003`), and
WAL journaling is that guarantee. It is set on every connection rather than assumed, because a
database restored from a backup taken in another mode would otherwise start without it.

**Migrations are discovered from the directory, never listed in code.** `ai/TESTING.md` §7
requires that every migration run forward from every prior version with data intact. A
hand-maintained list is a second source of truth that drifts from the files, and a test built on
it proves only that the list agrees with itself. Globbing means the harness cannot fall behind
the migrations it tests.

**The location comes from `platformdirs`** (`NFR-004`, `ARCHITECTURE.md` §5). Nothing is written
beside the installed application, and `appauthor=False` is not optional: without it Windows
inserts an author segment and produces `tracksandtrails\\tracksandtrails\\`, matching none of
§5's paths. `T-007` hit that trap once already.
"""

import re
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Final

from platformdirs import user_data_dir

from tracks_and_trails.downloader.environment import APP_SLUG

#: Where migrations live. One `.sql` file per version, named `NNNN_description.sql`.
MIGRATIONS_DIRECTORY: Final = Path(__file__).parent / "migrations"

#: A migration filename. The number is the schema version it produces, zero-padded so lexical
#: and numeric order agree — but it is parsed as an `int` regardless, so a mis-padded file sorts
#: correctly rather than silently running out of order.
_MIGRATION_NAME: Final = re.compile(r"^(\d+)_[a-z0-9_]+\.sql$")

#: The schema this build expects, as a snapshot. It is **not** applied to create a database —
#: migrations do that. It exists so that a schema change without a migration fails the suite
#: (`T-014` acceptance criterion), by comparing what the migrations actually build against it.
SCHEMA_SNAPSHOT: Final = Path(__file__).parent / "schema.sql"

DATABASE_FILENAME: Final = "library.sqlite3"


def database_path() -> Path:
    """The database location under `platformdirs` (`ARCHITECTURE.md` §5, `NFR-004`)."""
    return Path(user_data_dir(APP_SLUG, appauthor=False)) / DATABASE_FILENAME


def available_migrations() -> list[tuple[int, Path]]:
    """Every migration on disk, as `(version, path)` ordered by version.

    Derived from the directory rather than a list in code, which is the point: a new `.sql` file
    is picked up by the runner *and* by the tests that prove migrations work, with no third place
    to update and forget.

    A file whose name does not match raises rather than being skipped. A silently ignored
    migration is a schema that differs between two machines with no error on either.
    """
    migrations: list[tuple[int, Path]] = []
    for path in sorted(MIGRATIONS_DIRECTORY.glob("*.sql")):
        match = _MIGRATION_NAME.match(path.name)
        if match is None:
            raise ValueError(
                f"{path.name} is not a valid migration name. Expected NNNN_description.sql; a "
                "file that does not match would be skipped silently, leaving two machines on "
                "different schemas with no error on either."
            )
        migrations.append((int(match.group(1)), path))

    migrations.sort()
    versions = [version for version, _ in migrations]
    if len(set(versions)) != len(versions):
        raise ValueError(f"duplicate migration versions: {versions}")
    if versions and versions != list(range(1, len(versions) + 1)):
        raise ValueError(
            f"migration versions must run 1..N with no gaps; got {versions}. A gap makes "
            "'every prior version' ambiguous, which is exactly what ai/TESTING.md §7 tests."
        )
    return migrations


def latest_version() -> int:
    """The version a fully migrated database should report. Zero when there are none."""
    migrations = available_migrations()
    return migrations[-1][0] if migrations else 0


def schema_version(connection: sqlite3.Connection) -> int:
    """The version this database is at. Zero means empty.

    `PRAGMA user_version` rather than a table: it is atomic with the transaction that sets it,
    costs no schema of its own, and cannot itself need migrating.
    """
    row = connection.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def migrate(connection: sqlite3.Connection) -> list[int]:
    """Apply every pending migration in order, returning the versions applied.

    **Each migration and its version bump commit together.** If they could not, a crash between
    them would leave a database whose schema and recorded version disagree, and the next startup
    would either re-run a migration against objects that already exist or skip one that never
    ran. Both are worse than the crash.

    Forward-only (`T-014` scope). There is no `down`: an unexercised down-migration is a guess
    about undoing a change, and restoring a backup is the honest recovery path.
    """
    applied: list[int] = []
    current = schema_version(connection)
    for version, path in available_migrations():
        if version <= current:
            continue
        # `executescript` issues a COMMIT before running, so the version bump cannot share a
        # transaction with the DDL by wrapping both in one `with`. Set it inside the script's
        # own transaction instead: SQLite's DDL is transactional, and appending the pragma to
        # the script keeps the two atomic.
        connection.executescript(f"BEGIN;\n{path.read_text(encoding='utf-8')}\nCOMMIT;")
        connection.execute(f"PRAGMA user_version = {version:d}")
        connection.commit()
        applied.append(version)
    return applied


def configure(connection: sqlite3.Connection) -> None:
    """Apply the pragmas every connection needs (`DAT-001`, `NFR-003`).

    `synchronous=NORMAL` is the documented-safe pairing with WAL: durable against process death,
    which is what `NFR-003` asks for, without an fsync per commit. It is *not* durable against
    sudden power loss, and that distinction is deliberate — the acceptance criterion is a hard
    kill of the process, which this survives.

    `foreign_keys` is on because SQLite defaults it off per connection, and a constraint only
    sometimes enforced is worse than none.
    """
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA foreign_keys = ON")


def connect(path: Path | str) -> sqlite3.Connection:
    """Open (creating if needed) a configured, migrated database at `path`."""
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    configure(connection)
    migrate(connection)
    return connection


@contextmanager
def open_database(path: Path | str) -> Iterator[sqlite3.Connection]:
    """`connect`, closed on exit. The form callers should prefer."""
    with closing(connect(path)) as connection:
        yield connection
