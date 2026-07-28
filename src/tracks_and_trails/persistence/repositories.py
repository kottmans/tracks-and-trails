"""`JobRepository` — the durable queue (`T-014`, `REQ-012`, `REQ-018`, `NFR-003`).

Two properties are the whole point of this module.

**The queue survives an unclean kill.** WAL gives crash-safe commits (`db.configure`); this
layer's contribution is that every write is a single committed statement, so there is no state
in which half a job is stored. `ai/TESTING.md` §7 requires that be proven by killing a real
process, not by closing a connection politely.

**A job's `DownloadRequest` is frozen at creation.** It is stored with the job so a retry after
a settings change reproduces the *original* request rather than current defaults
(`ARCHITECTURE.md` §5, §8) — `ai/TESTING.md` §7's "settings freeze" area.

**What is deliberately not stored** (`REQ-026`, `NFR-007`, and the `T-014` scope decision of
2026-07-26): a proxy's embedded credentials are stripped before the request is serialized. The
job URL is stored verbatim, because it *is* the job — `REQ-012`'s queue and `REQ-020`'s history
are both unusable without it, and a retry cannot reconstruct it. Cookie file paths and contents
never reach this layer at all: `DownloadRequest.cookies_from_browser` carries a browser name
such as `"firefox"`, not a cookie. Log redaction is a different mechanism for a different sink
and belongs to `T-038`.
"""

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import fields, replace
from datetime import datetime
from typing import Any, Final

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import AudioCodec, DownloadRequest, MediaKind
from tracks_and_trails.core.models import Job as JobModel

#: Statuses that cannot still be true at startup (`ARCHITECTURE.md` §5).
#:
#: All three mean "in flight". If the application is only now starting, nothing was running when
#: it did, so a row claiming otherwise was interrupted by an unclean exit. `PAUSED` is absent on
#: purpose: the user asked for that, and it survives a restart intact.
#:
#: `ARCHITECTURE.md` §5 names all three. `T-014`'s acceptance criterion and `ai/TESTING.md` §7
#: mention only `RUNNING`; the architecture outranks both (`AGENTS.md` §5), and recovering only
#: `RUNNING` would leave a job stuck in `PROBING` forever with no path out.
INTERRUPTED_ON_STARTUP: Final = frozenset(
    {JobStatus.PROBING, JobStatus.RUNNING, JobStatus.POST_PROCESSING}
)

_INTERRUPTED_MESSAGE: Final = (
    "The application stopped unexpectedly while this job was in progress. "
    "Nothing is known about why — the process did not survive to record it. Retry to start again."
)

#: Request fields written to the database. Derived from the dataclass rather than typed out, so
#: a new field cannot be silently dropped on the way to disk — the round-trip test compares whole
#: objects, and an unlisted field would fail it rather than persisting as a default.
_REQUEST_FIELDS: Final = tuple(field.name for field in fields(DownloadRequest))

_JOB_COLUMNS: Final = (
    "id",
    "url",
    "status",
    "request",
    "title",
    "output_path",
    "bytes_done",
    "bytes_total",
    "error_kind",
    "error_message",
    "attempts",
    "queue_position",
    "created_at",
    "started_at",
    "finished_at",
)


def _serialize_request(request: DownloadRequest) -> str:
    """Serialize a request to JSON. **Nothing is transformed on the way** (`T014-R1`, `T014-R7`).

    Every field is stored exactly as the caller froze it, which is what `ARCHITECTURE.md` §8's
    settings freeze requires: a retry must reproduce the original request, not an edited copy.

    Credentials are excluded *upstream* rather than here. `DownloadRequest` rejects a proxy
    carrying userinfo at construction, so a job cannot hold one — three separate credential forms
    reached the database while this layer tried to strip them from an unbounded string, and one
    attempt to do so corrupted legitimate output paths instead. Making the value unrepresentable
    is the only version of this bound that does not depend on recognising what a secret looks
    like.
    """
    return json.dumps({name: getattr(request, name) for name in _REQUEST_FIELDS}, sort_keys=True)


def _deserialize_request(raw: str) -> DownloadRequest:
    """Rebuild a request from JSON, restoring the tuple and enum types the model requires.

    JSON has no tuples and no enums, so a naive round-trip would hand `DownloadRequest` lists and
    bare strings. Its `__post_init__` would coerce the lists and reject nothing, which is exactly
    the kind of near-miss that passes a shallow test and fails a comparison.
    """
    payload: dict[str, Any] = json.loads(raw)
    payload["post_processors"] = tuple(payload.get("post_processors", ()))
    payload["subtitle_languages"] = tuple(payload.get("subtitle_languages", ()))
    payload["media_kind"] = MediaKind(payload["media_kind"])
    payload["audio_codec"] = AudioCodec(payload["audio_codec"])
    return DownloadRequest(**{name: payload[name] for name in _REQUEST_FIELDS})


def _to_iso(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment is not None else None


def _from_iso(raw: str | None) -> datetime | None:
    return datetime.fromisoformat(raw) if raw is not None else None


def _row_to_job(row: sqlite3.Row) -> JobModel:
    return JobModel(
        id=row["id"],
        url=row["url"],
        request=_deserialize_request(row["request"]),
        status=JobStatus(row["status"]),
        title=row["title"],
        output_path=row["output_path"],
        bytes_done=row["bytes_done"],
        bytes_total=row["bytes_total"],
        error_kind=ErrorKind(row["error_kind"]) if row["error_kind"] is not None else None,
        error_message=row["error_message"],
        attempts=row["attempts"],
        queue_position=row["queue_position"],
        created_at=_from_iso(row["created_at"]),
        started_at=_from_iso(row["started_at"]),
        finished_at=_from_iso(row["finished_at"]),
    )


def _job_to_values(job: JobModel) -> dict[str, Any]:
    """Every column's value, stored exactly as given (`T014-R7`).

    **`error_message` carries the extractor's own words.** An earlier correction replaced it with
    project-authored text to bound what could reach the column; that violated `NFR-006`,
    `ARCHITECTURE.md` §5 and §7, `core/models.py` and `downloader/protocol.py`, all of which
    require the original message to be preserved rather than paraphrased. The maintainer restored
    it on 2026-07-26, together with the proxy grammar that removes the reason it was attempted.
    """
    return {
        "id": job.id,
        "url": job.url,
        "status": job.status.value,
        "request": _serialize_request(job.request),
        "title": job.title,
        "output_path": job.output_path,
        "bytes_done": job.bytes_done,
        "bytes_total": job.bytes_total,
        "error_kind": job.error_kind.value if job.error_kind is not None else None,
        "error_message": job.error_message,
        "attempts": job.attempts,
        "queue_position": job.queue_position,
        "created_at": _to_iso(job.created_at),
        "started_at": _to_iso(job.started_at),
        "finished_at": _to_iso(job.finished_at),
    }


class JobRepository:
    """Durable storage for jobs and their queue order (`REQ-012`).

    Holds a connection rather than opening one per call: SQLite's WAL writer is single, and a
    repository that reconnected per operation would make transaction boundaries impossible to
    reason about at the call site.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def add(self, job: JobModel) -> None:
        """Insert `job`. Raises if its id already exists.

        One statement, one commit. There is no window in which a partially written job is
        visible to another connection or survives a kill (`NFR-003`).
        """
        columns = ", ".join(_JOB_COLUMNS)
        placeholders = ", ".join(f":{name}" for name in _JOB_COLUMNS)
        with self._connection:
            # S608: the interpolated text is `_JOB_COLUMNS`, a module-level tuple of literal
            # identifiers. No value reaches the SQL — every one goes through a named placeholder,
            # which is the actual injection boundary. Spelling the columns out twice by hand
            # would silence the lint and add a second list to forget to update.
            self._connection.execute(
                f"INSERT INTO jobs ({columns}) VALUES ({placeholders})",  # noqa: S608
                _job_to_values(job),
            )

    def append(self, jobs: Sequence[JobModel]) -> list[JobModel]:
        """Insert `jobs` at the end of the queue, in **one** transaction (`ARC-005`).

        Returns them carrying the positions they were given, because the caller cannot know those
        until they are allocated and a caller that guessed would be guessing against every other
        writer.

        **One read and one `executemany`, not one of each per job.** The per-job path this exists
        beside makes a pasted batch cost a round trip and a commit per URL, which `T016-R3` found
        an interaction paying on the GUI thread. Allocating the whole run inside a single
        transaction is also what stops two callers reading the same `MAX(queue_position)` and
        handing out the same position twice — `ARC-005` puts every write on one thread, and this
        is the half of that guarantee the database itself enforces.

        An empty sequence is a no-op that still returns a list, so a caller need not special-case
        "nothing to add".
        """
        if not jobs:
            return []
        columns = ", ".join(_JOB_COLUMNS)
        placeholders = ", ".join(f":{name}" for name in _JOB_COLUMNS)
        with self._connection:
            row = self._connection.execute("SELECT MAX(queue_position) FROM jobs").fetchone()
            start = 0 if row[0] is None else int(row[0]) + 1
            placed = [
                replace(job, queue_position=start + offset) for offset, job in enumerate(jobs)
            ]
            # S608: see `add` — literal identifiers interpolated, every value parameterised.
            self._connection.executemany(
                f"INSERT INTO jobs ({columns}) VALUES ({placeholders})",  # noqa: S608
                [_job_to_values(job) for job in placed],
            )
        return placed

    def update(self, job: JobModel) -> None:
        """Overwrite the stored job with this one. Raises if it is not there.

        Raising rather than inserting: an update to a row that vanished means the caller's model
        of the queue is wrong, and silently recreating it would hide that.
        """
        assignments = ", ".join(f"{name} = :{name}" for name in _JOB_COLUMNS if name != "id")
        with self._connection:
            # S608: see `add` — literal identifiers interpolated, every value parameterised.
            cursor = self._connection.execute(
                f"UPDATE jobs SET {assignments} WHERE id = :id",  # noqa: S608
                _job_to_values(job),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"no job with id {job.id!r} to update")

    def get(self, job_id: str) -> JobModel | None:
        row = self._connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _row_to_job(row) if row is not None else None

    def all_jobs(self) -> list[JobModel]:
        """Every job, queued ones first in queue order, then the rest by creation time.

        `queue_position IS NULL` sorts last explicitly rather than relying on SQLite's NULL
        ordering, which is a detail of the engine and not of this contract.
        """
        rows = self._connection.execute(
            "SELECT * FROM jobs ORDER BY queue_position IS NULL, queue_position, created_at, id"
        ).fetchall()
        return [_row_to_job(row) for row in rows]

    def queued(self) -> list[JobModel]:
        """Jobs holding a queue position, in that order (`REQ-012`)."""
        rows = self._connection.execute(
            "SELECT * FROM jobs WHERE queue_position IS NOT NULL ORDER BY queue_position"
        ).fetchall()
        return [_row_to_job(row) for row in rows]

    def next_queue_position(self) -> int:
        row = self._connection.execute("SELECT MAX(queue_position) FROM jobs").fetchone()
        return 0 if row[0] is None else int(row[0]) + 1

    def recover_interrupted(self, *, now: datetime | None = None) -> list[str]:
        """Move jobs left in flight by an unclean exit to a retryable failure. Returns their ids.

        `ARCHITECTURE.md` §5 and `ai/TESTING.md` §7. A job cannot be probing, running or
        post-processing if the application is only now starting, so a row that says so is
        describing a state that ended when the process died.

        **The recovery is recorded, not silent** (`T-014` acceptance criterion). Each job carries
        `ErrorKind.INTERRUPTED` and a message saying what is and is not known, so the queue shows
        the user why a job they left running is now offering a retry. A silent move to `QUEUED`
        would restart a download without asking, which `REQ-018` reserves for `NETWORK`.

        Transitions go through `Job.with_failure`, so the state machine validates every one. A
        status this method cannot legally move to `FAILED` raises rather than being written.
        """
        finished_at = now if now is not None else datetime.now().astimezone()
        recovered: list[str] = []
        for job in self.all_jobs():
            if job.status not in INTERRUPTED_ON_STARTUP:
                continue
            failed = replace(
                job.with_failure(ErrorKind.INTERRUPTED, _INTERRUPTED_MESSAGE),
                finished_at=finished_at,
            )
            self.update(failed)
            recovered.append(job.id)
        return recovered
