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
from dataclasses import fields, replace
from datetime import datetime
from typing import Any, Final
from urllib.parse import urlsplit, urlunsplit

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


#: What the database stores in `error_message`, keyed by kind (`T014-R1`, `REQ-026`).
#:
#: **Project-authored text, never the extractor's.** A free-text diagnostic is an unbounded sink:
#: it can carry a credential, a cookie path, a personal path, anything. Two attempts to scrub such
#: prose with a recognizer both failed — the second also corrupted legitimate values — because a
#: heuristic applied to arbitrary text can neither exclude every secret nor leave the text intact.
#:
#: So no external string reaches this column at all. That is a *structural* guarantee rather than
#: a filter: the only values that can be written are the ones below.
#:
#: `NFR-006`'s verbatim preservation is not lost, it is relocated. `ARCHITECTURE.md` §5 already
#: puts the extractor's own output in the per-job log, and `REQ-019` is the view that shows it.
#: The database records *what* failed; the log records what the extractor said (`T-038`).
_STORED_MESSAGES: Final[dict[ErrorKind, str]] = {
    ErrorKind.UNSUPPORTED_URL: "No extractor matched this URL. See the job log.",
    ErrorKind.EXTRACTOR_ERROR: "The site or extractor reported a problem. See the job log.",
    ErrorKind.AUTH_REQUIRED: "This content requires signing in. See the job log.",
    ErrorKind.GEO_RESTRICTED: "This content is not available in your region. See the job log.",
    ErrorKind.DRM_PROTECTED: "This content is DRM protected and cannot be downloaded.",
    ErrorKind.NETWORK: "A network problem interrupted this download. See the job log.",
    ErrorKind.FFMPEG_MISSING: "ffmpeg is required for this download and was not found.",
    ErrorKind.FFMPEG_ERROR: "ffmpeg reported a problem. See the job log.",
    ErrorKind.DISK: "Writing the file failed. See the job log.",
    ErrorKind.WORKER_CRASH: "The download process stopped unexpectedly. See the job log.",
    ErrorKind.INTERRUPTED: _INTERRUPTED_MESSAGE,
    ErrorKind.CANCELLED: "Cancelled.",
}


def proxy_without_credentials(proxy: str | None) -> str | None:
    """Return `proxy` with any userinfo removed, parsed rather than pattern-matched.

    `T014-R1`. A proxy is a URL, so its credentials are removed by *parsing* it — not by scanning
    for something credential-shaped. `urlsplit` only populates `netloc` when a scheme is present,
    and `DownloadRequest.proxy` accepts any non-empty string, so a scheme-less value is re-parsed
    behind a placeholder scheme and the placeholder dropped again. That is what makes this exact
    for every form the model accepts, including single-label, Unicode and IPv6 hosts, which a
    recognizer over prose kept missing.
    """
    if proxy is None:
        return None
    parts = urlsplit(proxy)
    scheme_less = not parts.scheme or not parts.netloc
    if scheme_less:
        parts = urlsplit(f"placeholder://{proxy}")
    if "@" not in parts.netloc:
        return proxy
    _, _, host = parts.netloc.rpartition("@")
    rebuilt = urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))
    return rebuilt.removeprefix("placeholder://") if scheme_less else rebuilt


def _serialize_request(request: DownloadRequest) -> str:
    """Serialize a request to JSON. **Functional values are never rewritten** (`T014-R1`).

    `output_directory`, `output_template`, `format_selector` and `url` are what the download
    does; altering one changes where a file lands or what is fetched. An earlier version ran a
    secret-recogniser over every string and turned the output directory `/downloads/cookie-videos`
    into `[redacted]` — a relative path, so a retry would have written outside the directory the
    user chose. Only `proxy` is transformed, and only by parsing it.
    """
    safe = replace(request, proxy=proxy_without_credentials(request.proxy))
    return json.dumps({name: getattr(safe, name) for name in _REQUEST_FIELDS}, sort_keys=True)


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
    """Every column's value. **Nothing here is rewritten by a heuristic** (`T014-R1`).

    Two rules, both structural:

    - `error_message` is never the caller's string. It is looked up from `_STORED_MESSAGES` by
      kind, so no external text can reach the column — the extractor's own words go to the job
      log (`ARCHITECTURE.md` §5, `REQ-019`), which is where `NFR-006` is actually satisfied.
    - Every other value is stored exactly as given. `url`, `output_directory`, `output_template`
      and `format_selector` are functional: rewriting one changes where the file lands.
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
        "error_message": _STORED_MESSAGES[job.error_kind] if job.error_kind is not None else None,
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
