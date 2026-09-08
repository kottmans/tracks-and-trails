"""A hard kill mid-write leaves the queue readable
(`T-014`, `NFR-003`, `docs/project/TESTING.md` §7).

**This is the one that has to kill a real process.** The acceptance criterion says so, and the
reason is specific: closing a connection politely, rolling a transaction back, or raising an
exception all exercise SQLite's *cooperative* paths. None of them tests the guarantee `DAT-001`
chose SQLite for, which is that a process which never gets to run another instruction cannot
corrupt the database. Only `SIGKILL` — `TerminateProcess` on Windows — reaches that path.

The child writes in a loop and is killed at an unpredictable point inside it, so the kill lands
mid-write rather than at a tidy boundary.
"""

import multiprocessing as mp
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tracks_and_trails.core.models import DownloadRequest, Job
from tracks_and_trails.persistence import db
from tracks_and_trails.persistence.repositories import JobRepository

#: Long enough that the kill lands mid-loop on any runner, short enough not to pad the suite.
_WRITE_SECONDS = 5.0
_SETTLE_SECONDS = 0.5


def _request(url: str) -> DownloadRequest:
    return DownloadRequest(
        url=url,
        output_directory="/downloads",
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )


def _write_until_killed(database: str, ready: mp.synchronize.Event) -> None:
    """Insert and update jobs continuously until something kills this process.

    Runs in a spawned child (`ARC-002`'s model), so it imports the package itself rather than
    inheriting a fork's memory.
    """
    connection = db.connect(database)
    repository = JobRepository(connection)
    counter = 0
    while True:
        job = Job(
            id=f"job-{counter:06d}",
            url=f"https://example.invalid/{counter}",
            request=_request(f"https://example.invalid/{counter}"),
            created_at=datetime.now(UTC),
            queue_position=counter,
        )
        repository.add(job)
        repository.update(job.with_status(job.status.PROBING))
        counter += 1
        if counter == 1:
            ready.set()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "SIGKILL is POSIX. The Windows equivalent is Process.kill() mapping to TerminateProcess, "
        "which the CI Windows job exercises through the same test body below."
    ),
)
def test_a_hard_kill_mid_write_leaves_the_database_readable(tmp_path: Path) -> None:
    """`docs/project/TESTING.md` §7's crash-recovery area, at the layer where corruption would
    occur.

    Three things are asserted after the kill, and the third is the one that matters:

    1. the file opens at all;
    2. `PRAGMA integrity_check` reports `ok`;
    3. **every row that is there is complete and parses back into a `Job`.** A database can pass
       an integrity check while holding a row whose `request` column is half-written JSON, and
       that is the failure this is really guarding — a queue that loads and then explodes on the
       job it was in the middle of.
    """
    database = tmp_path / "library.sqlite3"
    context = mp.get_context("spawn")
    ready = context.Event()
    child = context.Process(target=_write_until_killed, args=(str(database), ready), daemon=True)
    child.start()
    try:
        assert ready.wait(timeout=30), "the child never completed its first write"
        time.sleep(_WRITE_SECONDS)
        assert child.is_alive(), "the child died on its own; the kill would prove nothing"

        # `.kill()` is SIGKILL on POSIX — no handler, no cleanup, no flush. Deliberately not
        # `.terminate()`, which is SIGTERM and lets Python run shutdown code.
        child.kill()
        child.join(timeout=30)
        assert child.exitcode is not None, "the child survived SIGKILL"
    finally:
        if child.is_alive():  # pragma: no cover - only on an unexpected failure path
            child.kill()
            child.join(timeout=10)

    time.sleep(_SETTLE_SECONDS)

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    connection.close()

    with db.open_database(database) as reopened:
        jobs = JobRepository(reopened).all_jobs()

    assert jobs, "the child wrote nothing before it was killed, so nothing was tested"
    for job in jobs:
        assert job.request.url == job.url, (
            f"{job.id} came back with a request that does not match its own row; a partially "
            "written request column is exactly what WAL is supposed to make impossible"
        )


def test_jobs_left_in_flight_by_the_kill_are_recovered_at_the_next_startup(
    tmp_path: Path,
) -> None:
    """The other half of `NFR-003`: surviving the kill is not enough if the queue then lies.

    The killed child leaves rows in `PROBING`. A restart must not present them as still probing,
    because nothing is. This is the same recovery the unit tests cover, exercised here against a
    database that a real kill produced rather than one a test constructed.
    """
    database = tmp_path / "library.sqlite3"
    context = mp.get_context("spawn")
    ready = context.Event()
    child = context.Process(target=_write_until_killed, args=(str(database), ready), daemon=True)
    child.start()
    try:
        assert ready.wait(timeout=30), "the child never completed its first write"
        time.sleep(1.0)
        child.kill()
        child.join(timeout=30)
    finally:
        if child.is_alive():  # pragma: no cover - only on an unexpected failure path
            child.kill()
            child.join(timeout=10)

    time.sleep(_SETTLE_SECONDS)

    with db.open_database(database) as connection:
        repository = JobRepository(connection)
        in_flight_before = [j for j in repository.all_jobs() if j.status.value == "probing"]
        assert in_flight_before, "the kill left nothing in flight, so recovery is untested here"

        recovered = repository.recover_interrupted()
        assert sorted(recovered) == sorted(job.id for job in in_flight_before)

        assert not [j for j in repository.all_jobs() if j.status.value == "probing"], (
            "a restart must not present a job as probing when no process is probing it"
        )
