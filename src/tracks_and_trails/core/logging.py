"""Application and per-job logging, with redaction at the handler (`T-038`, `REQ-026`).

## Why the redaction is a formatter and not a helper

`ARCHITECTURE.md` §8 says redaction happens **at the handler level rather than at each call
site**, and that phrasing is the whole design. A `redact()` that call sites must remember to wrap
their arguments in is a rule enforced by memory: it works until somebody logs
`f"starting {request}"`, which is the most natural line anyone will ever write here, and the
`DownloadRequest` repr carries the URL.

So every handler this module installs formats through `RedactingFormatter`, which redacts the
**finished string**. That is the one point every route converges on — `%`-style args, a
caller's f-string, an exception traceback, a `repr` of an object nobody thought about — so there
is no fourth route to forget. A test asserts that every handler on our loggers has it.

## What is redacted, and the principle behind the list

`REQ-026` binds "credentials and cookie paths **that this application supplies**". That set is
deliberately small, and two thirds of it is already unrepresentable rather than filtered:
`DownloadRequest` refuses a proxy carrying userinfo (`T-014`) and carries a browser *name* rather
than a cookie path. What is left is what this module handles:

- **Every URL loses its query, userinfo and fragment.** Not "token-like parameters" — *all* of
  them. Deciding which parameter names look like secrets is the recogniser problem that cost
  `T-018` four review rounds; `X-Amz-Signature` was outside every list that had been thought of.
  Nothing in a log needs a query string, so the allowlist is empty and the question closes.
- **Cookie material by shape**: a `Cookie:`/`Set-Cookie:` header value, and a path naming a
  cookie file. These arrive in third-party diagnostics rather than from us, and `DAT-003` keeps
  them verbatim *in the database*; it says explicitly that logs are different, because logs are
  written by this application.
- **Values registered at runtime** (`remember_a_secret`). The escape hatch that is not a guess:
  when the application does hold a sensitive literal, it can name it and have that exact string
  redacted wherever it appears. Bounded, exact, and no pattern involved.

**A bare `NAME=value` is not chased**, and that is a decision rather than an omission. It is
indistinguishable from `height=1080`, and a pattern wide enough to catch it would redact most of
every line — the failure mode of over-redaction is a log nobody can read, which `T014-R6` already
demonstrated once. Cookie *contents* are also outside what `REQ-026` binds: this application
never holds one, because `DownloadRequest` carries a browser name and yt-dlp reads the jar
itself. If that ever changes, the value is known at the moment it is held, and
`remember_a_secret()` takes it exactly.

**Output paths are deliberately not touched.** `T014-R6` turned a user's output directory into a
relative path while scrubbing prose, which was independently Critical — a log that cannot say
where the file went has broken the thing logs exist for.
"""

from __future__ import annotations

import logging
import logging.handlers
import re
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlsplit, urlunsplit

from platformdirs import user_cache_dir

from tracks_and_trails.core.paths import sanitize_component
from tracks_and_trails.downloader.environment import APP_SLUG

__all__ = [
    "REDACTED",
    "RedactingFormatter",
    "application_log_path",
    "configure_logging",
    "job_log_path",
    "open_job_log",
    "redact",
    "remember_a_secret",
    "stop_listening_for_worker_logs",
    "worker_log_queue",
    "worker_logging_handler",
]

REDACTED: Final = "<redacted>"

#: The application log's filename inside `user_cache_dir` (`ARCHITECTURE.md` §8, `NFR-004`).
LOG_FILENAME: Final = "tracks-and-trails.log"

#: Per-job logs live beside it, one directory down, one file per job.
JOB_LOG_DIRECTORY: Final = "jobs"

#: One line, and the fields a person reading it after the fact actually needs.
LOG_FORMAT: Final = "%(asctime)s %(levelname)-8s %(name)s %(message)s"

#: A URL with an authority. Matched loosely on purpose: this is the *finder*, and everything it
#: finds is then parsed properly and rebuilt without its query, userinfo or fragment.
_URL: Final = re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s\"'<>]+")

#: `user:secret@host` with **no scheme in front of it** (`T038-R1`).
#:
#: `_URL` cannot see this one: it anchors on `://`, so a proxy written the way a proxy is usually
#: written in a diagnostic — `user:pass@proxy.invalid:8080` — walked straight past the rule meant
#: to catch exactly it. Only the userinfo is taken; the host is what makes the line worth having.
_BARE_USERINFO: Final = re.compile(r"(?<![\w:/@.])[\w.\-+%]+:[^\s@/]+@(?=[\w.\-]+)")

#: A cookie header and its value, to the end of the line.
_COOKIE_HEADER: Final = re.compile(r"\b(set-cookie|cookie)\s*:\s*[^\n\r]*", re.IGNORECASE)

#: A cookie store named **with a directory in front of it** (`T038-R1`).
#:
#: Two false negatives closed here. Components could not contain whitespace, so
#: `C:\\Users\\A Person\\cookies.txt` matched only its tail and left the directory — and the
#: person's name — in the line.
_COOKIE_PATH: Final = re.compile(
    r"(?:[A-Za-z]:)?(?:[\\/](?:[^\\/\n\r\"']*[^\\/\s\"'])?)*"
    r"[\\/][^\\/\s\"']*cookies?[^\\/\s\"']*",
    re.IGNORECASE,
)

#: A cookie store named as a **bare filename**, with no directory — the other false negative.
#:
#: An extension is required, and that requirement is the whole rule. Without it this matches the
#: *word*: "loading cookies from the browser profile" becomes "loading <redacted> from the
#: browser profile", and a log that redacts its own prose is the `T014-R6` failure mode wearing
#: a different hat. A relative `cookies.txt` is a path; the noun "cookies" is not.
_COOKIE_FILENAME: Final = re.compile(
    r"\b[^\\/\s\"']*cookies?[^\\/\s\"']*\.[A-Za-z0-9]{1,8}\b",
    re.IGNORECASE,
)

#: Literal strings the application knows are sensitive. Exact matches, never patterns.
_secrets: set[str] = set()


def remember_a_secret(value: str | None) -> None:
    """Redact `value` wherever it later appears in a log line.

    For the case the patterns above cannot cover and should not try to: a literal this
    application is holding and knows is sensitive. Exact-string replacement, so there is nothing
    to be wrong about — the alternative is a rule that guesses, and this project has four review
    rounds on record about how that ends.

    Short values are ignored. A one- or two-character "secret" would redact its way through
    ordinary prose, and the failure mode of over-redaction is a log nobody can read.
    """
    if value and len(value) >= 4:
        _secrets.add(value)


def forget_the_secrets() -> None:
    """Drop every registered literal. For tests, and for a settings change that invalidates them."""
    _secrets.clear()


def redact(text: str) -> str:
    """Remove supplied credentials and cookie material from one finished log line.

    Ordered deliberately: registered literals first, because they are exact and a later rewrite
    could otherwise alter the text they would have matched; then cookie material by shape; then
    every URL, which is the rule with no exceptions in it.
    """
    for secret in _secrets:
        text = text.replace(secret, REDACTED)
    text = _COOKIE_HEADER.sub(lambda match: f"{match.group(1)}: {REDACTED}", text)
    text = _COOKIE_PATH.sub(REDACTED, text)
    text = _COOKIE_FILENAME.sub(REDACTED, text)
    text = _URL.sub(lambda match: _bare_url(match.group(0)), text)
    # After the URL rule, not before: a credential inside a well-formed URL is already gone by
    # now, and this is only for the ones written without a scheme to hang off.
    return _BARE_USERINFO.sub(f"{REDACTED}@", text)


def _bare_url(value: str) -> str:
    """A URL with nothing that can carry a credential: no userinfo, no query, no fragment.

    Trailing punctuation is left where it was found. A URL at the end of a sentence picks up the
    full stop, and returning it inside the redacted form would be a small lie about the address.
    """
    trailing = ""
    while value and value[-1] in ".,;:)]}>'\"":
        trailing = value[-1] + trailing
        value = value[:-1]
    try:
        parts = urlsplit(value)
    except ValueError:
        # **Fail closed** (`T038-R1`). This used to return the input unchanged, which meant a URL
        # malformed enough to break the parser — `https://[bad/v?token=…` — kept its query while
        # every well-formed one lost it. A parser failure is the one moment we know least about
        # the string, which is the worst possible moment to decide it is safe.
        return REDACTED
    netloc = parts.netloc.rsplit("@", 1)[-1]
    return urlunsplit(parts._replace(netloc=netloc, query="", fragment="")) + trailing


class RedactingFormatter(logging.Formatter):
    """The only formatter this module installs. Redacts what it has already rendered.

    Subclassing `format` rather than filtering the record is what makes this cover every route:
    by the time `super().format()` returns, the message, its `%`-args, any `extra` field the
    format string names and the exception traceback are all one string, and one rewrite reaches
    all of them.
    """

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def application_log_path(directory: Path | None = None) -> Path:
    """The application log under `platformdirs`, never beside the application (`NFR-004`)."""
    root = directory or Path(user_cache_dir(APP_SLUG, appauthor=False))
    return root / LOG_FILENAME


def job_log_path(job_id: str, directory: Path | None = None) -> Path:
    """One file per job (`ARCHITECTURE.md` §8).

    **The id is sanitised, not trusted** (`T038-R2`). Every id this application generates is a
    UUID, and the first version said so and used it as a filename directly — but `Job.id` is
    typed as any non-empty string, so "every id is a UUID" is a fact about today's callers rather
    than a property of the type. An id containing a separator would otherwise choose its own
    directory, and `core/paths.py` exists precisely so no untrusted text becomes a path
    component.
    """
    root = directory or Path(user_cache_dir(APP_SLUG, appauthor=False))
    return root / JOB_LOG_DIRECTORY / f"{sanitize_component(job_id)}.log"


#: The record attribute carrying which job a line belongs to.
#:
#: Stamped in the worker and read by the per-job handler's filter. Without it every worker's
#: output would land in every open job's file the moment Phase 2 allows two at once — which is
#: not "a per-job log" in any sense a reader would recognise (`T038-R2`).
JOB_FIELD: Final = "tracks_and_trails_job"


class _OnlyThisJob(logging.Filter):
    """Admits records stamped with one job id, and nothing else.

    Records with no stamp are refused rather than shared. The application log already has every
    line; a per-job file whose contents depend on which jobs happened to be open is worse than
    no per-job file, because it looks authoritative.
    """

    def __init__(self, job_id: str) -> None:
        super().__init__()
        self._job_id = job_id

    def filter(self, record: logging.LogRecord) -> bool:
        return getattr(record, JOB_FIELD, None) == self._job_id


class _StampTheJob(logging.Filter):
    """Marks every record from this worker with the job it belongs to. Never filters anything."""

    def __init__(self, job_id: str) -> None:
        super().__init__()
        self._job_id = job_id

    def filter(self, record: logging.LogRecord) -> bool:
        setattr(record, JOB_FIELD, self._job_id)
        return True


def _file_handler(path: Path, level: int) -> logging.Handler:
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(RedactingFormatter(LOG_FORMAT))
    return handler


def configure_logging(
    *, directory: Path | None = None, level: int = logging.INFO, stream: Any = None
) -> Path:
    """Install the application log and return where it went.

    Idempotent: called twice, it replaces its own handlers rather than adding a second copy —
    which is what would otherwise happen in a spawned worker that re-imports the application.
    """
    root = logging.getLogger(APP_SLUG)
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    path = application_log_path(directory)
    root.addHandler(_file_handler(path, level))
    if stream is not None:
        console = logging.StreamHandler(stream)
        console.setLevel(level)
        console.setFormatter(RedactingFormatter(LOG_FORMAT))
        root.addHandler(console)
    # The application's own tree only. Attaching to the root logger would take yt-dlp's and
    # Qt's output too, and this file is a record of what *this* application did.
    root.propagate = False
    return path


def open_job_log(
    job_id: str, *, directory: Path | None = None, level: int = logging.INFO
) -> logging.Handler:
    """A handler writing **one job's** diagnostics to its own file, redacted like everything else.

    Filtered to that job, which is what makes it a per-job log rather than a second copy of the
    application log (`T038-R2`). `DownloadManager` installs it for the life of a session and
    closes it on every exit path; `logging.Handler.close()` is the end of it.
    """
    handler = _file_handler(job_log_path(job_id, directory), level)
    handler.addFilter(_OnlyThisJob(job_id))
    return handler


#: The one queue workers send records on, and the listener draining it. Process-wide rather
#: than per-manager: a queue and a thread for every `DownloadManager` would mean one per test in
#: the integration suite, and the lifetime of a log sink is the lifetime of the process, not of
#: whichever object happened to want one first.
_worker_queue: Any = None
_listener: logging.handlers.QueueListener | None = None


class _ToWhicheverHandlersWeHaveNow(logging.handlers.QueueListener):
    """A listener that resolves the application's handlers per record, not once at construction.

    `QueueListener` normally captures a handler list when it is built. That is wrong here by one
    ordering: the listener is created the first time a worker starts, and `configure_logging()`
    may run afterwards — in a test, or in any process that installs its log after doing some
    work. The listener would then hold handlers nobody writes to any more and every worker line
    would vanish, silently, which is the worst way for a log to fail.

    Found by the full suite rather than by the test that owns this: alone it passed, because
    nothing had started a worker first.
    """

    def handle(self, record: logging.LogRecord) -> None:
        record = self.prepare(record)
        for handler in logging.getLogger(APP_SLUG).handlers:
            if record.levelno >= handler.level:
                handler.handle(record)


def worker_log_queue() -> Any:
    """The queue to hand a worker, with a listener already draining it into our handlers.

    Created on first use, because a `multiprocessing.Queue` costs a pipe and a feeder thread and
    most processes that import this module never spawn a worker at all — `--version` among them.
    """
    global _worker_queue, _listener
    if _worker_queue is None:
        import multiprocessing

        _worker_queue = multiprocessing.get_context("spawn").Queue()
        _listener = _ToWhicheverHandlersWeHaveNow(_worker_queue)
        _listener.start()
    return _worker_queue


def stop_listening_for_worker_logs() -> None:
    """Stop the listener and drop the queue with it. Safe when nothing ever started.

    **Both, or neither.** Stopping the listener while keeping the queue leaves the next caller of
    `worker_log_queue()` holding a queue nothing drains: workers log into a pipe nobody reads,
    silently. Found twice — once as a hang, and again as an ordering failure after
    `DownloadManager.shutdown()` started calling this, where a later manager's worker output
    vanished entirely.
    """
    global _listener, _worker_queue
    if _listener is not None:
        _listener.stop()
        _listener = None
    if _worker_queue is not None:
        _worker_queue.close()
        _worker_queue = None


def worker_logging_handler(
    queue: Any, *, job_id: str | None = None, level: int = logging.INFO
) -> logging.Handler:
    """Install a handler in a **worker process** that sends records to the parent (`T-038`).

    A `QueueHandler` over a plain `multiprocessing.Queue`: stdlib, and Qt-free, which the child
    must be (`ARCHITECTURE.md` §3). The records travel unformatted and are rendered — and
    therefore redacted — by the parent's handlers, so a worker cannot emit an unredacted line
    even in principle.

    **Its own queue, not the protocol's.** Putting log records on the message queue would make
    them indistinguishable from a worker sending something undeclared, which `SessionValidator`
    exists to refuse (`T-011`). Two queues; one contract each.
    """
    worker_root = logging.getLogger(APP_SLUG)
    worker_root.setLevel(level)
    for handler in list(worker_root.handlers):
        worker_root.removeHandler(handler)
        handler.close()
    handler = logging.handlers.QueueHandler(queue)
    handler.setLevel(level)
    if job_id is not None:
        # Stamped here, in the child, because this is the only process that knows which job it
        # is working on. The parent reads it to route the line to that job's file.
        handler.addFilter(_StampTheJob(job_id))
    worker_root.addHandler(handler)
    worker_root.propagate = False
    return handler
