"""The one persistence owner the GUI process talks to (`ARC-005`, `T016-R3`).

`QueueWriter` moves writes off the GUI thread. This is what the rest of the application holds:
a `JobStore` for `DownloadManager` and a `JobSink` for the add-URL dialog, both backed by that
single writer, so **every** queue write is serialised by one thread in the order it was asked
for — appends and status revisions alike.

## Reads stay synchronous, and still see your own writes

Reads are indexed single-row lookups against a local file and are not what blocked; making them
asynchronous would spread callbacks through every widget to fix a problem only writes have.

But a write that has been *queued* is not yet a row, and `DownloadManager` reads a job back
immediately before advancing it. So this keeps the revisions that are **still in flight**:
`update()` records the job the instant it is called, `get()` answers with the newest one
outstanding, and the record is dropped the moment the write settles — successfully or not.

That last clause is the correction `T016-R1` forced. What is held is a *queue of pending
writes*, not a cache of the newest value: once nothing is in flight the database is the only
answer, because it is the only thing that knows what actually landed. A cache had to guess a
rollback target when a write failed, and guessed wrong as soon as two failed in a row.

## Persist before announce, through a callback

`T-013`'s rule — persist, *then* signal — is preserved rather than traded away. `update()` takes
a completion callback and the manager emits `job_changed` from it, so the ordering is the same
one the acceptance criterion asked for; only the waiting is gone.
"""

import sqlite3
from collections.abc import Callable, Sequence
from datetime import datetime

from PySide6.QtCore import QObject

from tracks_and_trails.core.models import Job
from tracks_and_trails.persistence.repositories import HistoryEntry, JobRepository
from tracks_and_trails.persistence.writer import QueueWriter


def _now() -> datetime:
    """Timezone-aware, matching what the manager stamps onto `finished_at`."""
    return datetime.now().astimezone()


class PersistentJobStore(QObject):
    """Reads on the GUI thread, writes through `QueueWriter`, and never blocks either.

    Satisfies `downloader.manager.JobStore` and `ui.add_dialog.JobSink` at once, deliberately:
    they are the two halves of one queue, and giving them separate owners is what let the
    manager's writes stay synchronous while the dialog's moved (`T016-R3`).
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        writer: QueueWriter,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._repository = JobRepository(connection)
        self._writer = writer
        #: Per job, the revisions queued and **not yet settled**, oldest first (`T016-R1`).
        #:
        #: A list rather than one value, because revisions overlap: the dialog can withdraw a
        #: job while an earlier transition for it is still on the writer thread. Holding only
        #: the newest, plus the value it displaced, cannot answer "what is true now" once two
        #: of them fail — see `update`.
        self._pending: dict[str, list[Job]] = {}

    # --- reads --------------------------------------------------------------------------

    def get(self, job_id: str) -> Job | None:
        """The newest revision this process has queued, or what the database holds.

        Those are the only two answers, and which one applies is decided by whether a write is
        still outstanding — never by a remembered value. A settled write **is** the database's
        answer, so nothing is cached past the callback that reported it (`T016-R1`).
        """
        queued = self._pending.get(job_id)
        if queued:
            return queued[-1]
        return self._repository.get(job_id)

    def all_jobs(self) -> list[Job]:
        """Every stored job, with any queued revision of it applied.

        Used by the queue view (`T-017`). Reading the database and then overlaying what is still
        in flight is what stops a freshly cancelled job from reappearing as `RUNNING` for one
        refresh.
        """
        return [self._newest(job) for job in self._repository.all_jobs()]

    def _newest(self, stored: Job) -> Job:
        queued = self._pending.get(stored.id)
        return queued[-1] if queued else stored

    # --- writes -------------------------------------------------------------------------

    def update(self, job: Job, done: Callable[[str | None], None]) -> None:
        """Queue `job` as this job's newest revision. **Returns immediately** (`ARC-005`).

        The record happens first and unconditionally, so a `get()` between here and the callback
        returns the new state rather than the old one.

        **A revision is forgotten the moment it settles, whichever way it settled** (`T016-R1`).
        That is the whole model, and it replaces a newest-value cache with a rollback rule:

        - **It succeeded** → the database now holds it, and the database is asked from then on.
        - **It failed** → it never happened, and the answer is whatever is *still* queued behind
          it, falling through to the row on disk when nothing is.

        The version this replaces kept the newest value and, on failure, restored the value it
        had displaced. That is right for one failure and wrong for two: with revisions A then B
        both failing, B's rollback restored **A**, which had also failed — the reviewer measured
        SQLite holding `QUEUED` while this store answered `PROBING`. A rollback target that is
        itself a failed write is not a state anything ever reached. Only the database knows what
        is durable, so only the database is asked once nothing is in flight.
        """
        queued = self._pending.setdefault(job.id, [])
        queued.append(job)

        def settle(error: str | None) -> None:
            # Removed by identity, and from anywhere in the list rather than from the front: the
            # writer completes revisions in order, but a submission made after `close()` is
            # answered immediately, so an earlier one can still be outstanding.
            remaining = self._pending.get(job.id)
            if remaining is not None:
                for index, candidate in enumerate(remaining):
                    if candidate is job:
                        del remaining[index]
                        break
                if not remaining:
                    del self._pending[job.id]
            done(error)

        self._writer.revise(job, settle)

    def record_completion(
        self, job: Job, format_used: str | None, done: Callable[[str | None], None]
    ) -> None:
        """Write `job`'s completed-download record. **Returns immediately** (`T-050`, `REQ-020`).

        **The projection happens here, not in the manager, and that is the point.** `T-050`'s fourth
        acceptance criterion is that `downloader.manager` imports no `persistence` module. So the
        manager hands over a `Job` — a `core` type it already owns — plus the one fact the job does
        not carry, and this layer builds the `HistoryEntry`. Had the manager constructed the entry
        it would have needed to import it, and the criterion would have been lost to convenience.

        **`format_used` is not on `Job` on purpose.** It is a completion fact rather than live queue
        state, so putting it on the model would mean a `jobs` column that only ever matters once,
        after the row stops changing. It arrives from `Succeeded.format_used` instead.

        `completed_at` prefers the job's own `finished_at`, which the manager set in the same
        transition that made the job `COMPLETED`. Falling back to now would silently record the
        moment the *write* happened; the fallback exists only because `finished_at` is nullable in
        the schema, and a history row with no completion time is unusable to `REQ-020`.
        """
        self._writer.record_history(
            HistoryEntry(
                id=job.id,
                url=job.url,
                title=job.title,
                output_path=job.output_path,
                format_used=format_used,
                bytes_total=job.bytes_total,
                completed_at=job.finished_at if job.finished_at is not None else _now(),
            ),
            done,
        )

    def submit(self, jobs: Sequence[Job], done: Callable[[str | None], None]) -> None:
        """Append `jobs` in one transaction. **Returns immediately** (`ARC-005`).

        Nothing is recorded in memory, unlike `update`: these rows do not exist yet, and showing
        them as stored before they are would be the opposite of `REQ-012`'s promise. Once the
        write lands they are rows, and `get` reads them from the database like any other.
        """
        self._writer.submit(jobs, done)
