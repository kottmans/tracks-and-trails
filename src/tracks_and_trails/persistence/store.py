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

from PySide6.QtCore import QObject

from tracks_and_trails.core.models import Job
from tracks_and_trails.persistence.repositories import JobRepository
from tracks_and_trails.persistence.writer import QueueWriter


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

        **A completion comes through here too**, as of 2026-08-06. There was a separate
        `complete()` beside this one, because `T050-R1` needed a job row and its history row in a
        single transaction. `REQ-020` withdrew the record, leaving `complete` writing the same one
        row as `update` through three duplicated layers, and `T-175` collapsed it. `T050-R2`'s
        rule that nothing is announced before the write settles is unchanged and is the caller's
        to keep, which `test_a_success_is_announced_only_after_the_row_says_completed` now checks.

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

    def requeue_at_end(self, job: Job, done: Callable[[str | None], None]) -> None:
        """Persist a manual retry at the tail of the queue. **Returns immediately** (`T-080`).

        Identical in-flight bookkeeping to `update`, and that is the point: the revision is
        recorded here so a `get()` between now and the callback answers `QUEUED` rather than
        `FAILED`, and forgotten the moment it settles either way (`T016-R1`).

        **The recorded revision carries the job's *old* `queue_position`**, because the new one is
        allocated on the writer thread and is not known here. That is deliberate and narrow: what
        the manager reads back before the write lands is the status, which decides whether the
        retry still applies. Position only matters to `_next_waiting`, which runs when a slot opens
        — after the write has settled and `get()` answers from the database. Recording a *guessed*
        tail position would be worse than recording a stale one, because it would be wrong in a way
        the database never corrects.
        """
        queued = self._pending.setdefault(job.id, [])
        queued.append(job)

        def settle(error: str | None) -> None:
            remaining = self._pending.get(job.id)
            if remaining is not None:
                for index, candidate in enumerate(remaining):
                    if candidate is job:
                        del remaining[index]
                        break
                if not remaining:
                    del self._pending[job.id]
            done(error)

        self._writer.requeue_at_end(job, settle)

    def remove(self, job_id: str, done: Callable[[str | None], None]) -> None:
        """Delete the job's row. **Returns immediately** (`UX-001`, `T-080`).

        **Nothing is recorded in memory**, unlike `update`, and the asymmetry is deliberate. The
        in-flight record exists to answer "what is true now" for a job that still exists; there is
        no `Job` value that means "removed", and inventing one — a sentinel in `_pending`, a
        tombstone — would put a second kind of thing in a dictionary whose whole contract is that
        it holds newest revisions.

        The consequence is stated rather than hidden: between this call and its callback, `get()`
        and `all_jobs()` still answer with the row, because the row is still there. The manager
        announces `job_removed` from the callback, so the view is told when it is durable — which
        is `T-013`'s persist-then-announce rule, not an exception to it.
        """
        self._writer.remove(job_id, done)

    def reorder(self, job_ids: Sequence[str], done: Callable[[str | None], None]) -> None:
        """Rearrange the queue into `job_ids`' order. **Returns immediately** (`REQ-016`, `T-081`).

        **Nothing is recorded in memory**, for `remove`'s reason one step further: `_pending` holds
        newest *revisions of a job*, and a reordering is a fact about several jobs' relationship to
        each other. There is no single-job value that expresses it, so between this call and its
        callback `get()` answers with the positions on disk — the ones that are still true, because
        the write has not landed.

        The consequence for the caller is stated rather than hidden: the queue view refreshes when
        the manager announces the reordering from this callback, which is `T-013`'s
        persist-then-announce rule rather than an exception to it.
        """
        self._writer.reorder(job_ids, done)

    def clear_completed(self, done: Callable[[str | None], None]) -> None:
        """Delete every finished job's row. **Returns immediately** (`REQ-016`, `T-081`).

        **History is not touched**, which is `JobRepository.clear_completed`'s guarantee and the
        reason `T-100`'s view can still answer "where did my file go" afterwards.
        """
        self._writer.clear_completed(done)

    def submit(self, jobs: Sequence[Job], done: Callable[[str | None], None]) -> None:
        """Append `jobs` in one transaction. **Returns immediately** (`ARC-005`).

        Nothing is recorded in memory, unlike `update`: these rows do not exist yet, and showing
        them as stored before they are would be the opposite of `REQ-012`'s promise. Once the
        write lands they are rows, and `get` reads them from the database like any other.
        """
        self._writer.submit(jobs, done)
