"""The one persistence owner the GUI process talks to (`ARC-005`, `T016-R3`).

`QueueWriter` moves writes off the GUI thread. This is what the rest of the application holds:
a `JobStore` for `DownloadManager` and a `JobSink` for the add-URL dialog, both backed by that
single writer, so **every** queue write is serialised by one thread in the order it was asked
for — appends and status revisions alike.

## Reads stay synchronous, and still see your own writes

Reads are indexed single-row lookups against a local file and are not what blocked; making them
asynchronous would spread callbacks through every widget to fix a problem only writes have.

But a write that has been *queued* is not yet a row, and `DownloadManager` reads a job back
immediately before advancing it. So this keeps a **write-through view**: `update()` records the
job in memory the instant it is called and `get()` consults that view first. The manager's
read-your-writes assumption therefore holds unchanged, which is what let `ARC-005` land without
restructuring ten call sites of approved `T-013` code.

The view holds only jobs this process has written. Anything else falls through to the database,
so a job created by an earlier run is read normally.

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
        #: Jobs written by this process, newest value first. See the module docstring.
        self._view: dict[str, Job] = {}

    # --- reads --------------------------------------------------------------------------

    def get(self, job_id: str) -> Job | None:
        """The job as this process last left it, falling back to what is stored."""
        cached = self._view.get(job_id)
        if cached is not None:
            return cached
        return self._repository.get(job_id)

    def all_jobs(self) -> list[Job]:
        """Every stored job, with any pending in-memory revision applied.

        Used by the queue view (`T-017`). Reading the database and then overlaying the view is
        what stops a freshly cancelled job from reappearing as `RUNNING` for one refresh.
        """
        return [self._view.get(job.id, job) for job in self._repository.all_jobs()]

    # --- writes -------------------------------------------------------------------------

    def update(self, job: Job, done: Callable[[str | None], None]) -> None:
        """Record `job` and queue the write. **Returns immediately** (`ARC-005`).

        The in-memory record happens first and unconditionally, so a `get()` between here and the
        callback returns the new state rather than the old one. A *failed* write leaves the view
        ahead of the database, which is the honest ordering: recovery corrects a database that
        trails the UI at the next startup (`NFR-003`), and the failure itself is reported.
        """
        self._view[job.id] = job
        self._writer.revise(job, done)

    def submit(self, jobs: Sequence[Job], done: Callable[[str | None], None]) -> None:
        """Append `jobs` in one transaction. **Returns immediately** (`ARC-005`).

        Not recorded in the view before the write lands, unlike `update`: these rows do not exist
        yet, and showing them as stored before they are would be the opposite of `REQ-012`'s
        promise. The dialog waits for the callback before it closes.
        """

        def record(error: str | None) -> None:
            if error is None:
                for job in jobs:
                    self._view.setdefault(job.id, job)
            done(error)

        self._writer.submit(jobs, record)
