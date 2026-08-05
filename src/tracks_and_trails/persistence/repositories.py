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
from dataclasses import dataclass, fields, replace
from datetime import datetime
from typing import Any, Final

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import REORDERABLE, TERMINAL, JobStatus
from tracks_and_trails.core.models import AudioCodec, DownloadRequest, MediaKind
from tracks_and_trails.core.models import Job as JobModel

#: Statuses that cannot still be true at startup (`ARCHITECTURE.md` §5).
#:
#: All three mean "in flight". If the application is only now starting, nothing was running when
#: it did, so a row claiming otherwise was interrupted by an unclean exit.
#:
#: *(This used to add "`PAUSED` is absent on purpose: the user asked for that, and it survives a
#: restart intact." `T-080` removed the status — `UX-001`'s pause is a queue-level drain that never
#: changes a job's own status — so the exclusion it explained no longer has anything to exclude.)*
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
    "thumbnail_url",
    "uploader",
    "duration_seconds",
    "playlist_id",
    "playlist_index",
    "playlist_title",
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
        thumbnail_url=row["thumbnail_url"],
        uploader=row["uploader"],
        duration_seconds=row["duration_seconds"],
        playlist_id=row["playlist_id"],
        playlist_index=row["playlist_index"],
        playlist_title=row["playlist_title"],
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
        "thumbnail_url": job.thumbnail_url,
        "uploader": job.uploader,
        "duration_seconds": job.duration_seconds,
        "playlist_id": job.playlist_id,
        "playlist_index": job.playlist_index,
        "playlist_title": job.playlist_title,
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


def _write_job(connection: sqlite3.Connection, job: JobModel) -> None:
    """The `UPDATE jobs` statement, **without owning a transaction** (`T050-R1`).

    Separated from `JobRepository.update` so that `complete_job` can put this statement and the
    history insert inside **one** commit. A helper that opened its own transaction could not be
    composed, and composing them is the whole point: a completed job whose history row is in a
    second transaction can lose that row to a hard exit in between.
    """
    assignments = ", ".join(f"{name} = :{name}" for name in _JOB_COLUMNS if name != "id")
    # S608: see `JobRepository.add` — literal identifiers interpolated, values parameterised.
    cursor = connection.execute(
        f"UPDATE jobs SET {assignments} WHERE id = :id",  # noqa: S608
        _job_to_values(job),
    )
    if cursor.rowcount == 0:
        raise KeyError(f"no job with id {job.id!r} to update")


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
        with self._connection:
            _write_job(self._connection, job)

    def requeue_at_end(self, job: JobModel) -> JobModel:
        """Write `job` carrying a **freshly allocated tail position**, in one transaction (`T-080`).

        Manual retry's write (`P2PLAN-R7`): a failed job keeps the position it was added with, so
        re-queuing it in place would let a second attempt run ahead of jobs that have never run.

        **The position is allocated here, not by the caller.** `queue_position` carries a `UNIQUE`
        index, so two callers each computing `MAX + 1` outside a transaction would not tie — one of
        them would fail to write. Reading and writing inside the same transaction is the same
        guarantee `append` relies on, for the same reason.

        Returns the job as stored, because the caller cannot know the position it was given and a
        caller that guessed would be guessing against every other writer.

        Raises if the row is not there, exactly as `update` does: re-queuing a job that vanished
        means the caller's model of the queue is wrong, and silently inserting it would hide that.
        """
        with self._connection:
            row = self._connection.execute("SELECT MAX(queue_position) FROM jobs").fetchone()
            placed = replace(job, queue_position=0 if row[0] is None else int(row[0]) + 1)
            _write_job(self._connection, placed)
        return placed

    def remove(self, job_id: str) -> bool:
        """Delete the job's row. Returns whether there was one (`UX-001`, `T-080`).

        **This deletes a database row and nothing else.** No file is touched, by this method or by
        anything it calls — `UX-001` makes that the rule for remove, and the absence of any
        filesystem call here is the whole of its implementation.

        A boolean rather than raising on a missing row, unlike `update`: "remove what is already
        gone" is a state the user can reach by pressing the same button twice, and the outcome they
        asked for is the outcome they have. The return value exists so a caller that *does* care
        can tell the two apart.

        The row's `queue_position` goes with it, which leaves a gap in the sequence. Gaps are
        harmless: every consumer orders by the column and none of them counts on it being dense.
        """
        with self._connection:
            cursor = self._connection.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        return cursor.rowcount > 0

    def reorder(self, job_ids: Sequence[str]) -> list[JobModel]:
        """Rearrange `job_ids` into that order, in **one** transaction (`REQ-016`, `T-081`).

        Returns them carrying their new positions.

        **They are dealt the positions they already collectively occupied**, rather than being
        renumbered from zero. Two consequences, both wanted: a running job keeps its slot, because
        its position is not among the ones being redealt; and jobs the user did not touch do not
        move relative to anything, because no position outside this set changes. Renumbering the
        whole queue would reorder by side effect.

        **Two phases, and the `UNIQUE` index is why.** `jobs_queue_position` is unique over
        non-`NULL` values, and SQLite checks uniqueness per *statement*, not at commit — so
        assigning the new positions directly fails the moment two of them cross, which is what
        reordering is. The rows are set to `NULL` first, which the partial index excludes, and then
        given their new values. Both phases are inside one transaction, so a crash between them
        leaves the queue as it was: `REQ-016`'s criterion is that a queue half-reordered by a crash
        is a queue in an order nobody chose.

        **Only pending jobs** (`REORDERABLE`). A running job's position is not a promise this pool
        can keep — it is already started, and moving it says otherwise. Raises rather than skipping
        silently: a caller asking to move a running job has a stale view, and quietly reordering the
        rest would leave the table showing an order the database never agreed to.

        Raises if an id is unknown, or if a named job holds no position at all — a job outside the
        queue order has no place in a rearrangement of it.
        """
        if not job_ids:
            return []
        if len(set(job_ids)) != len(job_ids):
            raise ValueError("cannot reorder: the same job was named twice")
        with self._connection:
            placeholders = ", ".join("?" for _ in job_ids)
            # S608: `placeholders` is generated `?` marks, never caller text. Every value below is
            # parameterised — same boundary `add` and `append` document.
            rows = self._connection.execute(
                f"SELECT * FROM jobs WHERE id IN ({placeholders})",  # noqa: S608
                tuple(job_ids),
            ).fetchall()
            found = {row["id"]: _row_to_job(row) for row in rows}

            missing = [job_id for job_id in job_ids if job_id not in found]
            if missing:
                raise KeyError(f"cannot reorder unknown jobs: {', '.join(missing)}")
            unplaced = [job_id for job_id in job_ids if found[job_id].queue_position is None]
            if unplaced:
                raise ValueError(
                    f"cannot reorder jobs that hold no queue position: {', '.join(unplaced)}"
                )
            fixed = [job_id for job_id in job_ids if found[job_id].status not in REORDERABLE]
            if fixed:
                raise ValueError(
                    "cannot reorder jobs that are running or finished: "
                    + ", ".join(f"{job_id} is {found[job_id].status.value}" for job_id in fixed)
                )

            positions = sorted(found[job_id].queue_position or 0 for job_id in job_ids)
            # Phase one: out of the unique index entirely. Without this, the first assignment that
            # lands on a position another named row still holds raises `IntegrityError`.
            self._connection.execute(
                f"UPDATE jobs SET queue_position = NULL WHERE id IN ({placeholders})",  # noqa: S608
                tuple(job_ids),
            )
            self._connection.executemany(
                "UPDATE jobs SET queue_position = ? WHERE id = ?",
                list(zip(positions, job_ids, strict=True)),
            )
        return [
            replace(found[job_id], queue_position=position)
            for position, job_id in zip(positions, job_ids, strict=True)
        ]

    def clear_completed(self) -> list[str]:
        """Delete every finished job's row. Returns their ids (`REQ-016`, `T-081`).

        **Finished means `TERMINAL` — completed *or* cancelled — and not `FAILED`.** A failed job is
        still in the queue offering a retry (`REQ-018`), so clearing it would throw away work the
        user has not decided about. A cancelled one is a decision they already made.

        **History is untouched, and that is the answer to "where did my file go".** `T-085` writes a
        `history` row inside the completion transaction, in a different table; clearing the queue
        removes the queue's record and leaves the record of what was obtained. `T-100`'s view is
        how the user finds it afterwards, which is why `P2PLAN-R8` filed that view:
        clear-completed plus `UX-001`'s remove-never-deletes would otherwise leave them unable
        to find their own downloads.

        **No file is touched**, by this method or anything it calls. Same rule and same
        implementation as `remove`: the absence of any filesystem call is the whole of it.

        One statement, one transaction. There is no window where half the finished rows are gone.
        """
        statuses = sorted(status.value for status in TERMINAL)
        placeholders = ", ".join("?" for _ in statuses)
        with self._connection:
            # S608: `placeholders` is generated `?` marks; the status values are parameterised.
            #
            # **A playlist clears as a unit, or not at all** (`UX-005` row 9d, `T140-R2`). This
            # deleted every terminal row independently, so a sixteen-track playlist with three
            # done and thirteen running lost those three from underneath the group the user had
            # opened specifically to watch — the exact thing row 9d was adopted to prevent, and
            # `T-140` claimed as an acceptance criterion without implementing it.
            #
            # `NOT EXISTS` rather than two round trips: the survivors have to be judged inside the
            # same transaction, or a member finishing between the read and the delete would let a
            # group be cleared that was no longer wholly terminal.
            sibling = "EXISTS (SELECT 1 FROM jobs AS sibling WHERE "
            sibling += "sibling.playlist_id = jobs.playlist_id AND sibling.status NOT IN "
            unfinished_member = f"{sibling}({placeholders}))"
            clause = (
                f"status IN ({placeholders}) "
                f"AND (jobs.playlist_id IS NULL OR NOT {unfinished_member})"
            )
            rows = self._connection.execute(
                f"SELECT id FROM jobs WHERE {clause}",  # noqa: S608
                (*statuses, *statuses),
            ).fetchall()
            cleared = [row["id"] for row in rows]
            self._connection.execute(
                f"DELETE FROM jobs WHERE {clause}",  # noqa: S608
                (*statuses, *statuses),
            )
        return cleared

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

        **One transaction for all of them** (`T-082`). This used to call `update()` per job, and
        `update()` opens its own transaction — so recovering a queue of twenty left-running jobs
        was twenty commits, each with its own fsync, on the path that runs *before the window
        appears*. `T-082`'s criterion names this directly: recovering N jobs must not mean N
        unbatched writes. The transitions are still validated one at a time; only the commit is
        shared.

        **Every transition is computed before anything is written.** `with_failure` raises for a
        status it cannot legally move, and doing that inside the transaction would leave some rows
        recovered and some not if it ever fired — an application that half-recovers on startup is
        worse than one that refuses to.
        """
        finished_at = now if now is not None else datetime.now().astimezone()
        pending = [
            replace(
                job.with_failure(ErrorKind.INTERRUPTED, _INTERRUPTED_MESSAGE),
                finished_at=finished_at,
            )
            for job in self.all_jobs()
            if job.status in INTERRUPTED_ON_STARTUP
        ]
        # No early return for the empty case. `with connection` issues **nothing** when no
        # statement runs inside it — measured, and a mutation removing the guard survived because
        # the guard changed no observable behaviour. A branch that saves a commit that was never
        # going to happen is a claim the code does not earn.
        with self._connection:
            for failed in pending:
                _write_job(self._connection, failed)
        return [failed.id for failed in pending]


#: `history`'s columns, in the order the insert names them. Same reasoning as `_JOB_COLUMNS`:
#: derived once, so a column cannot be silently dropped between the insert and the update.
_HISTORY_COLUMNS: Final = (
    "id",
    "url",
    "title",
    "output_path",
    "format_used",
    "bytes_total",
    "thumbnail_url",
    "playlist_id",
    "playlist_index",
    "playlist_title",
    "completed_at",
)


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoryEntry:
    """A completed download's durable record (`REQ-020`, `ARCHITECTURE.md` §5).

    **It lives here rather than in `core/models.py`, and that module says why**: this is a durable
    record, not live domain state, so it belongs with the schema that stores it. Nothing in `core`
    or `downloader` needs the type — the manager hands a `Job` to a sink and this layer does the
    projecting, which is what keeps `downloader.manager` free of a `persistence` import
    (`ARCHITECTURE.md` §3).

    **`id` is the job's id, not a new one.** One completed job is one history row, which is what
    makes a retry an update rather than a duplicate. See `HistoryRepository.record`.

    **`format_used` is nullable and means "not reported".** `REQ-020` asks for the format used, and
    `Succeeded.format_used` supplies the resolved `format_id`. When yt-dlp reports none there is no
    honest value: the request's selector describes an intention rather than an outcome, and writing
    it here would be the defect `T-050` names explicitly.
    """

    id: str
    url: str
    completed_at: datetime
    title: str | None = None
    output_path: str | None = None
    format_used: str | None = None
    bytes_total: int | None = None

    #: Where the site said the picture was (`T-138`, `UX-005` §3).
    #:
    #: **Its own copy, not the job's.** `jobs.thumbnail_url` holds the same address while the job
    #: exists, and removing the job takes it — so a history row reading through to the queue would
    #: lose its picture exactly when History becomes the only place the download is recorded.
    #:
    #: `None` means "recorded before this column existed" or "the extractor named no picture", and
    #: the row draws the derived tile for either. That is what every history row did until this
    #: existed, so the absent case is the old behaviour rather than a degraded one.
    thumbnail_url: str | None = None

    #: Which playlist this download came from, and where it sat in it (`T-145`, `UX-005` amended
    #: 2026-08-05).
    #:
    #: **Its own copy, for `thumbnail_url`'s reason, one field further on.** `0004` put the same
    #: three columns on `jobs`, where they die with the job — `T-081`'s *Clear finished* is enough
    #: to take them — so a playlist that finished would be sixteen unrelated history rows at
    #: exactly the point History became the only record of it.
    #:
    #: `None` for all three means "pasted directly" or "recorded before migration `0006`". Both
    #: render ungrouped, and neither is re-grouped by guessing from titles or paths.
    #:
    #: `playlist_index` is the position **the playlist reported**, not the order the downloads
    #: finished in, so a group opens with track 03 above track 04 however they interleaved.
    playlist_id: str | None = None
    playlist_index: int | None = None
    playlist_title: str | None = None

    def __post_init__(self) -> None:
        membership = (self.playlist_id, self.playlist_index, self.playlist_title)
        if any(part is not None for part in membership) and None in membership:
            # **All three or none**, which is `Job.__post_init__`'s rule and is here for the same
            # reason: a record with an id and no index cannot be ordered within its group, and one
            # with an index and no id belongs to no group at all. Unrepresentable is cheaper than
            # every reader checking the other two first.
            raise ValueError(
                "HistoryEntry carries part of a playlist membership: playlist_id, playlist_index "
                f"and playlist_title must be set together or not at all, got {membership!r}"
            )
        if self.playlist_index is not None and self.playlist_index < 0:
            raise ValueError("HistoryEntry.playlist_index cannot be negative")
        if not self.url:
            raise ValueError(
                "HistoryEntry requires the source URL; `REQ-020` names it and a retry cannot "
                "reconstruct it"
            )
        if self.bytes_total is not None and self.bytes_total < 0:
            # The table's own CHECK says the same thing. Saying it here too means a bad value
            # fails where it was constructed rather than as an opaque IntegrityError one layer on.
            raise ValueError("HistoryEntry.bytes_total cannot be negative")


def _history_to_values(entry: HistoryEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "url": entry.url,
        "title": entry.title,
        "output_path": entry.output_path,
        "format_used": entry.format_used,
        "bytes_total": entry.bytes_total,
        "thumbnail_url": entry.thumbnail_url,
        "playlist_id": entry.playlist_id,
        "playlist_index": entry.playlist_index,
        "playlist_title": entry.playlist_title,
        "completed_at": entry.completed_at.isoformat(),
    }


def _row_to_history(row: sqlite3.Row) -> HistoryEntry:
    return HistoryEntry(
        id=row["id"],
        url=row["url"],
        title=row["title"],
        output_path=row["output_path"],
        format_used=row["format_used"],
        bytes_total=row["bytes_total"],
        thumbnail_url=row["thumbnail_url"],
        playlist_id=row["playlist_id"],
        playlist_index=row["playlist_index"],
        playlist_title=row["playlist_title"],
        completed_at=datetime.fromisoformat(row["completed_at"]),
    )


def _write_history(connection: sqlite3.Connection, entry: HistoryEntry) -> None:
    """The history upsert, **without owning a transaction** (`T050-R1`). See `_write_job`."""
    columns = ", ".join(_HISTORY_COLUMNS)
    placeholders = ", ".join(f":{name}" for name in _HISTORY_COLUMNS)
    assignments = ", ".join(
        f"{name} = excluded.{name}" for name in _HISTORY_COLUMNS if name != "id"
    )
    # S608: see `JobRepository.add` — the interpolated text is `_HISTORY_COLUMNS`, a module-level
    # tuple of literal identifiers, and every value goes through a named placeholder.
    connection.execute(
        f"INSERT INTO history ({columns}) VALUES ({placeholders}) "  # noqa: S608
        f"ON CONFLICT(id) DO UPDATE SET {assignments}",
        _history_to_values(entry),
    )


def complete_job(connection: sqlite3.Connection, job: JobModel, entry: HistoryEntry) -> None:
    """Store the completed job **and** its history record in one transaction (`T050-R1`).

    **This exists because two transactions are not atomic and a crash found the gap.** The first
    version persisted `COMPLETED`, returned to the GUI thread, and only then queued the history
    insert. A deterministic probe held GUI event delivery, waited for the completion to commit, and
    hard-exited the process: the restart observed `job_status='completed', history=None`. Nothing
    backfills history at startup and `format_used` exists nowhere else, so the record was gone for
    good — `REQ-012`'s unexpected-termination promise and `REQ-020`'s durable record both broken by
    a silent, irreversible loss.

    One `with connection:` block means SQLite commits both statements or neither. There is no
    instant at which a job is durably complete without the record of what it obtained.

    Ordered job-first only because `_write_job` raises `KeyError` for a row that is not there, and
    failing before writing history keeps the error about the thing that is actually wrong. Both
    statements are inside the transaction either way, so the order is not what makes it safe.
    """
    with connection:
        _write_job(connection, job)
        _write_history(connection, entry)


class HistoryRepository:
    """The completed-download record (`REQ-020`, `T-050`, `DAT-005`).

    **Append-mostly, and it deletes in exactly one way.** This said "nothing here deletes" until
    `DAT-005` (2026-08-04), and that sentence was load-bearing rather than descriptive — it is why
    `T-125` had to be a decision before it could be a button. What changed is narrow and stated
    there: a user may remove **records they selected**, and **no file is ever touched**.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def record(self, entry: HistoryEntry) -> None:
        """Store `entry`, replacing any row already held for that job.

        **Upsert rather than insert — and the reason is not that a retry can complete twice today.**
        `core/job_state.py` gives `COMPLETED` no outgoing transitions, so the state machine forbids
        a second completion of one job id: `FAILED → QUEUED` is the only retry edge and a completed
        job cannot reach it. This branch is therefore **not reachable through `DownloadManager` as
        it stands**, which is why `T-050` proves it here rather than end to end.

        It is an upsert because the alternative fails badly if it is ever reached. A plain insert
        would raise `IntegrityError` on the writer thread for a download that genuinely succeeded,
        reporting a persistence failure the user did not cause and cannot act on. A duplicated
        `Succeeded`, a replayed completion callback, or a Phase 2 retry path (`T-082`, `T-083`) that
        reaches `COMPLETED` again would each land here.

        And when it is reached, *which* row survives matters. `INSERT OR IGNORE` would keep the
        **stale** completion and silently discard the newer one — the right count with the wrong
        data. The latest completion is the true one, so it wins. That is the "not silently
        duplicate" half of `T-050`'s criterion: one row, deliberately overwritten, rather than a
        second insert swallowed.

        One statement, one commit, matching `JobRepository`'s guarantee: there is no state in which
        half an entry is visible or survives a kill (`NFR-003`).

        **This is not the path a completing download takes** — see `complete_job`, which writes the
        job row and this row in one transaction because two transactions can be separated by a hard
        exit (`T050-R1`).
        """
        with self._connection:
            _write_history(self._connection, entry)

    def get(self, entry_id: str) -> HistoryEntry | None:
        row = self._connection.execute("SELECT * FROM history WHERE id = ?", (entry_id,)).fetchone()
        return _row_to_history(row) if row is not None else None

    def remove(self, entry_ids: Sequence[str]) -> int:
        """Delete the named records, and **only** records (`DAT-005`, `REQ-020`, `T-125`).

        **Nothing on this path touches the filesystem, and that is the guarantee rather than an
        omission.** A history entry names a file on disk, and `UX-001` promises this application
        never deletes the user's files. `DAT-005` §2 refuses even an opt-in for it.

        **Ids, never a predicate.** `DAT-005` scopes removal to what the user selected; a method
        taking a `WHERE` fragment or a cutoff date would move that decision to whichever caller was
        written next, which is exactly how a scoping decision stops being one.

        Returns how many rows were actually deleted, which is not always `len(entry_ids)`: a record
        can already be gone, and the caller reports what happened rather than what was asked for.

        An empty sequence deletes nothing and says so, rather than becoming an accidental
        `DELETE FROM history` — the failure this signature exists to make impossible.

        **The empty-sequence guard cannot be tested away, and that is recorded rather than fixed.**
        Deleting it leaves the suite green, because SQLite accepts `IN ()` as the empty set and
        deletes nothing — measured, not assumed. That is a SQLite *extension*; standard SQL rejects
        the syntax outright. So the guard is redundant against this backend and load-bearing
        against the next one, and it states the intent that an empty selection removes nothing.
        A future reader finding this mutation survives should not conclude the line is dead
        (`ai/TESTING.md` §13: default to "a test is missing", and prove redundancy before acting —
        this is the proof).

        **Committed, like every other write here** (`T125-R1`). The first version executed the
        `DELETE` bare, on the implicit transaction `sqlite3` opens for a DML statement and never
        closes by itself. Every test read back through the *same* connection, which sees its own
        uncommitted work, so the deletion looked durable and was not: a second connection still
        found the row, and closing the writer rolled the delete back. The user was told a record
        was gone, the History tab reads through a different connection, and the record came back.
        `with self._connection` is the same guarantee `record` and `JobRepository` already give —
        `NFR-003`, no half-applied write and nothing that survives only until the process exits.
        """
        if not entry_ids:
            return 0
        placeholders = ", ".join("?" for _ in entry_ids)
        with self._connection:
            cursor = self._connection.execute(
                f"DELETE FROM history WHERE id IN ({placeholders})",  # noqa: S608
                tuple(entry_ids),
            )
            return int(cursor.rowcount)

    def all_entries(self) -> list[HistoryEntry]:
        """Every entry, most recently completed first.

        `id` breaks ties rather than leaving them to insertion order, which SQLite does not
        promise and which a test comparing whole lists would depend on by accident.
        """
        rows = self._connection.execute(
            "SELECT * FROM history ORDER BY completed_at DESC, id"
        ).fetchall()
        return [_row_to_history(row) for row in rows]
