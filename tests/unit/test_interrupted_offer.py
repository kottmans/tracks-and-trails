"""Interrupted jobs are recovered in one write and *offered*, not restarted (`T-082`, `REQ-012`).

Phase 1 already recovered a job left `RUNNING` by an unclean exit. `T-082` adds two things its
criteria name: **the plural** — a queue of them rather than one — and **the offer**, which must be
explicit and refusable.

The recovery half is tested against a real SQLite connection, because the criterion that is easiest
to satisfy accidentally is the write-count one and a fake repository would not have transactions to
count.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import DownloadRequest, Job
from tracks_and_trails.persistence import db
from tracks_and_trails.persistence.repositories import JobRepository


def a_request(directory: Path) -> DownloadRequest:
    return DownloadRequest(
        url="https://example.invalid/clip",
        output_directory=str(directory),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )


@pytest.fixture
def repository(tmp_path: Path) -> JobRepository:
    return JobRepository(db.connect(tmp_path / "library.sqlite3"))


def add_in_flight(repository: JobRepository, tmp_path: Path, count: int) -> list[str]:
    """`count` jobs left mid-flight, written the way a killed application would have left them.

    Driven through the **real transitions** — `QUEUED → PROBING → READY → RUNNING` — rather than
    writing `RUNNING` straight into the row. `with_status` validates, so a shortcut here would
    either raise or, worse, teach this file a path the state machine does not have.
    """
    request = a_request(tmp_path)
    jobs = [Job(id=f"job-{index}", url=request.url, request=request) for index in range(count)]
    repository.append(jobs)
    for job in jobs:
        for status in (JobStatus.PROBING, JobStatus.READY, JobStatus.RUNNING):
            stored = repository.get(job.id)
            assert stored is not None
            repository.update(stored.with_status(status))
    return [job.id for job in jobs]


def test_every_interrupted_job_is_recovered_not_just_the_first(
    repository: JobRepository, tmp_path: Path
) -> None:
    """**The plural is the task** — one was Phase 1's case (`T-082`'s scope)."""
    ids = add_in_flight(repository, tmp_path, 12)

    recovered = repository.recover_interrupted()

    assert sorted(recovered) == sorted(ids)
    for job_id in ids:
        job = repository.get(job_id)
        assert job is not None
        assert job.status is JobStatus.FAILED
        assert job.error_kind is ErrorKind.INTERRUPTED


def test_recovering_n_jobs_is_one_transaction_not_n(
    repository: JobRepository, tmp_path: Path
) -> None:
    """**The third criterion, counted rather than asserted about.**

    `update()` opens its own transaction, so the loop this replaced was one commit — and one
    fsync — per job, on the path that runs *before the window appears*. Counted through sqlite3's
    trace callback, which sees the real statements, so this cannot pass against an implementation
    that batches in Python and still commits per row.
    """
    add_in_flight(repository, tmp_path, 12)

    statements: list[str] = []
    repository._connection.set_trace_callback(statements.append)
    try:
        repository.recover_interrupted()
    finally:
        repository._connection.set_trace_callback(None)

    commits = [line for line in statements if line.strip().upper().startswith("COMMIT")]
    assert len(commits) == 1, f"twelve jobs took {len(commits)} commits: {statements}"


def test_a_clean_start_opens_no_transaction_at_all(
    repository: JobRepository, tmp_path: Path
) -> None:
    """Every start but the interesting one.

    **Not a claim about an early return** — there is none, deliberately. Measured: `with
    connection` issues nothing when no statement runs inside it, and a mutation removing the guard
    that used to be here survived for exactly that reason. What this asserts is the behaviour that
    is real: a clean start writes nothing.
    """
    request = a_request(tmp_path)
    repository.append([Job(id="job-1", url=request.url, request=request)])

    statements: list[str] = []
    repository._connection.set_trace_callback(statements.append)
    try:
        assert repository.recover_interrupted() == []
    finally:
        repository._connection.set_trace_callback(None)

    assert not [line for line in statements if line.strip().upper().startswith(("BEGIN", "COMMIT"))]


def test_nothing_is_moved_back_to_queued(repository: JobRepository, tmp_path: Path) -> None:
    """**Nothing restarts a download the user did not ask to restart** (`REQ-018`).

    A recovered job that landed in `QUEUED` would be picked up by the pool as soon as the window
    opened — a queue of downloads resuming because the machine crashed, on somebody's metered
    connection. `FAILED` with a retryable kind is what makes the *offer* possible at all.
    """
    ids = add_in_flight(repository, tmp_path, 3)

    repository.recover_interrupted()

    for job_id in ids:
        job = repository.get(job_id)
        assert job is not None
        assert job.status is not JobStatus.QUEUED
        assert job.status is JobStatus.FAILED


def test_a_job_that_was_not_in_flight_is_left_exactly_as_it_was(
    repository: JobRepository, tmp_path: Path
) -> None:
    """Recovery is for rows describing a state that ended when the process died, and no others."""
    request = a_request(tmp_path)
    repository.append([Job(id="queued", url=request.url, request=request)])
    before = repository.get("queued")

    assert repository.recover_interrupted() == []
    assert repository.get("queued") == before


def test_the_recovery_message_says_what_happened(repository: JobRepository, tmp_path: Path) -> None:
    """`T-014`'s criterion: the recovery is recorded, not silent. The queue must be able to say
    why a job the user left running is now offering a retry."""
    add_in_flight(repository, tmp_path, 1)

    repository.recover_interrupted(now=datetime(2026, 8, 1, 9, 0, tzinfo=UTC))

    job = repository.get("job-0")
    assert job is not None
    assert job.error_message
    assert job.finished_at is not None


def test_a_recovered_job_is_retryable(repository: JobRepository, tmp_path: Path) -> None:
    """The offer is only meaningful if the retry it offers is one the state machine permits."""
    from tracks_and_trails.core.errors import is_retryable

    add_in_flight(repository, tmp_path, 1)
    repository.recover_interrupted()

    job = repository.get("job-0")
    assert job is not None
    assert job.error_kind is not None
    assert is_retryable(job.error_kind)


def test_recovery_survives_a_second_start(repository: JobRepository, tmp_path: Path) -> None:
    """Idempotent: a user who declines the offer and restarts must not see rows recovered twice
    into an illegal transition."""
    add_in_flight(repository, tmp_path, 2)

    assert len(repository.recover_interrupted()) == 2
    assert repository.recover_interrupted() == []


def test_a_transition_the_state_machine_refuses_leaves_nothing_half_written(
    repository: JobRepository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**Every transition is computed before anything is written.**

    `with_failure` validates, and validating inside the transaction would leave some rows recovered
    and some not. An application that half-recovers on startup is worse than one that refuses to:
    the user cannot tell which half.
    """
    ids = add_in_flight(repository, tmp_path, 4)
    original = Job.with_failure
    calls = {"n": 0}

    def refuse_the_third(self: Job, kind: ErrorKind, message: str) -> Job:
        calls["n"] += 1
        if calls["n"] == 3:
            raise ValueError("refused")
        return original(self, kind, message)

    monkeypatch.setattr(Job, "with_failure", refuse_the_third)

    with pytest.raises(ValueError, match="refused"):
        repository.recover_interrupted()

    still_running = [
        job_id
        for job_id in ids
        if (job := repository.get(job_id)) and job.status is JobStatus.RUNNING
    ]
    assert len(still_running) == len(ids), (
        f"{len(ids) - len(still_running)} rows were written before the refusal, so the queue is "
        "half recovered and nothing says which half"
    )


def test_the_connection_is_still_usable_after_a_refusal(
    repository: JobRepository, tmp_path: Path
) -> None:
    """A rolled-back transaction must not leave the connection in a state the next read trips on."""
    add_in_flight(repository, tmp_path, 2)
    repository.recover_interrupted()

    assert isinstance(repository._connection, sqlite3.Connection)
    assert len(repository.all_jobs()) == 2
