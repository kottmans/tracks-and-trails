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
from tracks_and_trails.persistence import db, repositories
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


def test_the_recovery_is_recorded_by_its_classification(
    repository: JobRepository, tmp_path: Path
) -> None:
    """`T-014`'s criterion: the recovery is recorded, not silent — and `T-243` moves *where*.

    **This asserted `job.error_message` and that was the defect one layer down.** The criterion is
    that the queue can say why a job the user left running is now offering a retry, and what makes
    that possible is the **classification**: `ui/error_text.py` turns `INTERRUPTED` into *"Tracks &
    Trails closed while this was downloading"*. Asserting that a message was stored pinned the
    duplicate prose in place as though it were the requirement.
    """
    add_in_flight(repository, tmp_path, 1)

    repository.recover_interrupted(now=datetime(2026, 8, 1, 9, 0, tzinfo=UTC))

    job = repository.get("job-0")
    assert job is not None
    assert job.error_kind is ErrorKind.INTERRUPTED
    assert job.finished_at is not None


def test_recovery_records_no_message_because_there_is_none(
    repository: JobRepository, tmp_path: Path
) -> None:
    """`T-243`. `error_message` is the **extractor's** own words (`NFR-006`, `DAT-003`).

    An interrupted job has none — the process died before anything could be recorded, which is the
    entire content of the classification — so recovery writes nothing there. `None` rather than
    `""`: *nothing was recorded* is a different fact from *something empty was*, and the drawn row
    reads this field.

    **The row said the same thing twice before this**: `error_text`'s headline, and then a sentence
    of the project's own prose stored here, ending in a next step on the one line `T201-R3`
    deliberately keeps next steps off.
    """
    add_in_flight(repository, tmp_path, 1)

    repository.recover_interrupted()

    job = repository.get("job-0")
    assert job is not None
    assert job.error_message is None


def test_a_failure_cannot_lose_its_message_by_omission(repository: JobRepository) -> None:
    """`T243-R1`: `None` is legal for `INTERRUPTED`, not for whatever a caller forgot to pass.

    **The default was the defect.** `T-243` needs a job with no extractor message to be
    expressible; it does not need omission to become legal for all twelve classifications. With
    `message` defaulting to `None`, `with_failure(ErrorKind.EXTRACTOR_ERROR)` type-checked and
    produced a `FAILED` job whose diagnostic had silently vanished — indistinguishable from the one
    case where having nothing recorded is the truth.

    Asserted through the signature rather than by calling it, because the whole point is that the
    bad call **no longer type-checks**; `mypy` is what enforces this, and it found the single
    call site that relied on the default when the default was removed.
    """
    import inspect

    parameter = inspect.signature(Job.with_failure).parameters["message"]
    assert parameter.default is inspect.Parameter.empty, (
        "`with_failure`'s message has a default again, so an extractor diagnostic can go missing "
        "by omission and look exactly like an interrupted job that never had one"
    )


def test_a_message_written_by_an_older_build_is_still_rendered(
    repository: JobRepository, tmp_path: Path
) -> None:
    """`T-243`'s third criterion: rows already in the database keep working.

    A build before this change wrote its own sentence into `error_message`, and those rows are on
    disk. They are still carried verbatim, because that is what the field means whatever wrote it —
    **the rejected fork is what would have dropped them.** Recognising the project's own sentence
    and deleting it is a string comparison against a constant that drifts, and the first edit to
    the wording turns it into a silent no-op that leaves the duplication back on screen.
    """
    from tracks_and_trails.ui.error_text import headline_for

    stored = "The application stopped unexpectedly while this job was in progress."
    add_in_flight(repository, tmp_path, 1)
    job = repository.get("job-0")
    assert job is not None
    repository.update(job.with_failure(ErrorKind.INTERRUPTED, stored))

    recovered = repository.get("job-0")
    assert recovered is not None
    assert recovered.error_message == stored
    # And what a row like that draws: the headline, then the stored words, unedited.
    assert headline_for(ErrorKind.INTERRUPTED) != stored


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

    # `message` widened to `str | None` in `T-243` and stayed **required** in `T243-R1`, so this
    # stub takes it the same way: a stub with a default would keep passing if the real signature
    # grew one back, which is the defect the finding is about.
    def refuse_the_third(self: Job, kind: ErrorKind, message: str | None) -> Job:
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


def test_only_queued_jobs_are_admitted_at_startup(
    repository: JobRepository, tmp_path: Path
) -> None:
    """**`T-115` must not restart what `T-082` recovered** (`T081-R4`).

    Asserted on the filter directly, because through the application it is invisible: the state
    machine refuses `FAILED → PROBING`, so admitting everything produces rejections and no state
    change, and a mutation removing the filter survives every end-to-end test. Relying on that
    refusal is precisely the rule `T081-R4` was filed about.
    """
    from tracks_and_trails.app import waiting_jobs

    request = a_request(tmp_path)
    repository.append(
        [
            Job(id=f"job-{n}", url=request.url, request=request)
            for n in ("queued", "read", "ran", "done")
        ]
    )
    # One left in flight and then recovered, as an unclean exit leaves it.
    for status in (JobStatus.PROBING, JobStatus.READY, JobStatus.RUNNING):
        stored = repository.get("job-ran")
        assert stored is not None
        repository.update(stored.with_status(status))
    repository.recover_interrupted()
    # And one that finished.
    for status in (
        JobStatus.PROBING,
        JobStatus.READY,
        JobStatus.RUNNING,
        JobStatus.POST_PROCESSING,
        JobStatus.COMPLETED,
    ):
        stored = repository.get("job-done")
        assert stored is not None
        repository.update(stored.with_status(status))

    # And one probed but never downloaded, which is what `UX-003` leaves behind on every ordinary
    # exit: a job is read *before* it is queued, so `READY` is the resting state of waiting work.
    stored = repository.get("job-read")
    assert stored is not None
    repository.update(stored.with_status(JobStatus.PROBING).with_status(JobStatus.READY))

    assert [job_id for job_id, _ in waiting_jobs(repository)] == ["job-queued", "job-read"], (
        "startup would admit a job it did not leave waiting — a recovered one restarts unattended, "
        "which is T081-R4 — or would skip a READY one, which is T-115 for every queue UX-003 "
        "leaves behind"
    )


def test_waiting_jobs_deserializes_only_the_rows_it_returns(
    repository: JobRepository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T177-R1`: the other half of the acceptance criterion, which had no gate.

    `T-177` names both startup scans, and the deserialization-count regression covered only
    `recover_interrupted()`. Restoring `waiting_jobs()` to `all_jobs()` plus a Python filter left
    every new test green while putting half the startup cost back — the production code was right
    and the claimed gate did not gate this caller.

    Counted at `_row_to_job`, where the expense is: `_deserialize_request` runs a `json.loads` and
    two enum conversions for every row handed to it. The returned pair is asserted as well, because
    a mutation selecting nothing would deserialize nothing and satisfy a count-only test.
    """
    from tracks_and_trails.app import waiting_jobs

    request = a_request(tmp_path)
    repository.append([Job(id=f"job-{n}", url=request.url, request=request) for n in range(12)])
    # One probed but never downloaded, and the rest finished — so two of twelve are waiting.
    stored = repository.get("job-4")
    assert stored is not None
    repository.update(stored.with_status(JobStatus.PROBING).with_status(JobStatus.READY))
    for n in (1, 2, 3, 5, 6, 7, 8, 9, 10, 11):
        stored = repository.get(f"job-{n}")
        assert stored is not None
        for status in (
            JobStatus.PROBING,
            JobStatus.READY,
            JobStatus.RUNNING,
            JobStatus.POST_PROCESSING,
            JobStatus.COMPLETED,
        ):
            stored = stored.with_status(status)
        repository.update(stored)

    deserialized: list[str] = []
    original = repositories._row_to_job

    def counting(row: sqlite3.Row) -> Job:
        deserialized.append(row["id"])
        return original(row)

    monkeypatch.setattr(repositories, "_row_to_job", counting)
    waiting = waiting_jobs(repository)

    assert waiting == [("job-0", JobStatus.QUEUED), ("job-4", JobStatus.READY)]
    assert sorted(deserialized) == ["job-0", "job-4"], (
        f"waiting_jobs read {len(deserialized)} of 12 rows to return 2; it is enumerating and "
        "filtering in Python again, on the path that runs before the window appears"
    )
