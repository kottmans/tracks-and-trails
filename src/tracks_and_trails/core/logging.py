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

import atexit
import contextlib
import errno
import itertools
import logging
import logging.handlers
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, NamedTuple
from urllib.parse import urlsplit, urlunsplit

from platformdirs import user_cache_dir

from tracks_and_trails.core.paths import sanitize_component
from tracks_and_trails.downloader.environment import APP_SLUG

__all__ = [
    "MAX_JOB_LOG_BYTES",
    "REDACTED",
    "RedactingFormatter",
    "YtdlpLog",
    "application_log_path",
    "close_job_log_when_drained",
    "configure_logging",
    "job_log_path",
    "open_job_log",
    "redact",
    "remember_a_secret",
    "stop_listening_for_worker_logs",
    "wait_for_the_log_listener_to_stop",
    "worker_log_queue",
    "worker_logging_handler",
    "ytdlp_logger",
]

REDACTED: Final = "<redacted>"

#: The application log's filename inside `user_cache_dir` (`ARCHITECTURE.md` §8, `NFR-004`).
LOG_FILENAME: Final = "tracks-and-trails.log"

#: Per-job logs live beside it, one directory down, one file per job.
JOB_LOG_DIRECTORY: Final = "jobs"

#: One line, and the fields a person reading it after the fact actually needs.
LOG_FORMAT: Final = "%(asctime)s %(levelname)-8s %(name)s %(message)s"

#: **The stated bound on one job's log** (`T-084`). Two files of 2 MiB, so a job's diagnostics can
#: never exceed **4 MiB** however long it runs or however loudly yt-dlp complains.
#:
#: Bounded by rotation rather than by refusing to write: `REQ-019` wants the output for a bug
#: report, and the *end* of a long log is where the failure is. A cap that stopped writing would
#: keep the least useful half. One backup rather than none so a rotation mid-failure does not throw
#: away the lines immediately before it.
MAX_JOB_LOG_BYTES: Final = 2 * 1024 * 1024
JOB_LOG_BACKUPS: Final = 1

#: **There is deliberately no provenance flag here** (`T084-R1`).
#:
#: `T-084` shipped one and it was a **Critical** regression. `DAT-003`'s `T-049` amendment has a
#: section headed *"`T-038` is unchanged and origin-agnostic"* saying in as many words: *every log
#: this application emits is redacted, whatever the provenance of the text inside it*. I read the
#: amendment's provenance **table** — which is about the *database* — and applied it to logs, when
#: the next section says storage and emission are different sinks with different rules.
#:
#: What made it Critical rather than merely wrong: the scheme kept exact `remember_a_secret()`
#: values for third-party records and dropped the pattern rules. **No production caller registers
#: anything**, so that tier is empty, and a yt-dlp line echoing the source URL wrote its userinfo
#: password and signed query to the job log verbatim — onto a surface with a Copy button.

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

    **Origin-agnostic, and that is `DAT-003`'s accepted rule rather than a choice made here.**
    Every line is treated identically whoever wrote the text inside it. `T-084` briefly made this
    provenance-aware and that was `T084-R1`, a Critical — see the note where the provenance flag
    used to be, above `remember_a_secret`.

    The `NFR-006` tension is real: a diagnostic can lose a cookie path it named. That is **the
    maintainer's to resolve**, not this function's, and `T-084`'s record says so.
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


def ytdlp_logger() -> logging.Logger:
    """The logger yt-dlp's output travels on. **A name, and nothing else.**

    Under `APP_SLUG` so it reaches the same handlers as everything else, and separately named so a
    reader can tell yt-dlp's lines from ours. It carries **no filter and no mark**: redaction is
    origin-agnostic (`DAT-003`), so nothing downstream needs to know who wrote a line.
    """
    return logging.getLogger(f"{APP_SLUG}.ytdlp")


class YtdlpLog:
    """yt-dlp's `logger` option, bridged onto this application's logging (`T-084`, `REQ-019`).

    **Setting `logger` is what makes yt-dlp's output reachable at all.** Measured against yt-dlp
    2026.07.04: `to_screen` calls `logger.debug(...)` **and returns before the `quiet` check**, and
    `report_warning` checks `logger` before `no_warnings`. So the `quiet=True` and
    `no_warnings=True` this application has always passed do not suppress anything once a logger is
    present — they only ever governed writes to a console a worker does not have.

    **`verbose` is deliberately not enabled**, and that is a security decision rather than a volume
    one. Measured: verbose makes yt-dlp dump `params:` and `Proxy map:`, which contain the proxy
    URL and `cookiesfrombrowser` — **values this application supplies**, which is the one row of
    `DAT-003`'s provenance table that must never reach a log. The version banner a bug report wants
    is written by `session_header()` instead, where this application chooses every field.

    ## Levels

    yt-dlp's `debug` carries its ordinary screen output — "Extracting URL", "Downloading webpage" —
    which is the substance of `REQ-019` rather than debug detail, so it is logged at `INFO`. Only
    lines yt-dlp itself prefixes `[debug]` (verbose-only, and therefore unreachable today) go to
    `DEBUG`. Logging the lot at `DEBUG` would have been the quiet failure here: the worker's
    handler sits at `INFO`, so the job log would have been created, been empty, and looked fine.
    """

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def debug(self, message: str) -> None:
        if message.startswith("[debug] "):
            self._logger.debug("%s", message)
        else:
            self._logger.info("%s", message)

    def info(self, message: str) -> None:
        self._logger.info("%s", message)

    def warning(self, message: str) -> None:
        self._logger.warning("%s", message)

    def error(self, message: str) -> None:
        self._logger.error("%s", message)


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


def _file_handler(
    path: Path, level: int, *, max_bytes: int = 0, backups: int = 0
) -> logging.Handler:
    """One file, redacted, and optionally bounded.

    `max_bytes=0` is stdlib's "never rotate" and is what the application log uses — `NFR-004` puts
    it under `user_cache_dir` where the OS may reclaim it, and it is one file for the whole
    application rather than one per job. Per-job logs pass the bound; see `MAX_JOB_LOG_BYTES`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        path, encoding="utf-8", maxBytes=max_bytes, backupCount=backups
    )
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
    hands it back through `close_job_log_when_drained()`.

    **A handler still draining onto this same file is taken back, not replaced.** A job probed
    and then downloaded — the ordinary `T-016` flow — reopens its log while the previous
    session's marker may still be in the queue. Closing that handler here and opening a new one
    looks equivalent and is not: the caller cannot attach the replacement in the same breath, and
    a stamped record dispatched in between belongs to a job whose file nothing is holding open.
    It is not written anywhere and there is no later chance to write it, which is the loss this
    whole finding is about. Handing the same open handler back has no such window — and no second
    handler on one file to write every line twice, which was the reason the first version closed
    it.

    A pending drain onto a **different** file is left alone. It has no conflict with this one and
    closes when its own marker arrives.
    """
    path = job_log_path(job_id, directory)
    still_draining = _take_the_drain_back(job_id, path)
    if still_draining is not None:
        return still_draining
    handler = _file_handler(path, level, max_bytes=MAX_JOB_LOG_BYTES, backups=JOB_LOG_BACKUPS)
    handler.addFilter(_OnlyThisJob(job_id))
    return handler


#: The record attribute carrying a drain marker's token (`T038-R2`).
#:
#: A marker is an ordinary `LogRecord` put on the worker queue by the **parent**, and its whole
#: content is this token. It reaches no handler: the listener recognises it and stops there.
_DRAIN_FIELD: Final = "tracks_and_trails_drain"


class _Drain(NamedTuple):
    """One per-job handler, the job it belongs to, and the queue its marker was put on.

    The queue is held because a listener that is stopping closes the handlers waiting on **its**
    queue and no others. Without it, a listener shutting down would close a per-job handler that
    a newer queue and listener had just taken responsibility for — the log failing silently
    again, one lifecycle further out.
    """

    job_id: str
    handler: logging.Handler
    queue: Any


#: Per-job handlers waiting for their marker to come back out of the queue, and the lock over
#: them — the only state in this module touched from both the GUI thread and the listener thread.
_drains: dict[int, _Drain] = {}
_drain_lock: Final = threading.Lock()
_drain_tokens: Final = itertools.count()


def close_job_log_when_drained(job_id: str, handler: logging.Handler) -> None:
    """Detach and close `handler`, but **not before** the records already queued have reached it.

    The defect this exists for (`T038-R2`): result messages and log records travel on two
    different queues, so a worker's last line can still be in the log queue when its
    `WorkerFinished` has already been read off the result queue and the session released. Closing
    the per-job handler at that moment sends that line to the application log alone, and the
    per-job file — the one a user is pointed at — ends up empty. A two-second listener delay
    reproduced it every time.

    **The ordering is established rather than waited for.** The parent puts a marker record on
    the log queue; everything the worker wrote is already ahead of it, because the worker's
    process has exited and a `multiprocessing.Queue` flushes its feeder before it goes. When the
    listener reaches the marker it has, by construction, already handed every one of those
    records to this handler — so the close happens there, on the listener thread, and nothing on
    the GUI thread waits for it (`T013-R2`).

    Fails closed in both directions: with no listener running, or with a queue that will not take
    the marker, the handler is closed immediately rather than left attached forever.
    """
    queue = _worker_queue
    if queue is None:
        _detach_and_close(handler)
        return
    with _drain_lock:
        token = next(_drain_tokens)
        _drains[token] = _Drain(job_id, handler, queue)
    marker = logging.LogRecord(
        name=APP_SLUG,
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="(a per-job log drain marker; if you are reading this, it escaped the listener)",
        args=None,
        exc_info=None,
    )
    setattr(marker, _DRAIN_FIELD, token)
    try:
        queue.put_nowait(marker)
    except Exception:
        _finish_the_drain(token)


def _finish_the_drain(token: int) -> None:
    """Close the handler this marker was carrying, if nothing has closed it already."""
    with _drain_lock:
        drain = _drains.pop(token, None)
    if drain is not None:
        _detach_and_close(drain.handler)


def _take_the_drain_back(job_id: str, path: Path) -> logging.Handler | None:
    """Stop waiting for this job's marker and return its handler, still attached and still open.

    Popping under the lock is what makes this safe: whoever pops owns the handler, so the
    listener cannot close the one being handed back here, and a marker arriving afterwards finds
    nothing under its token and does nothing.
    """
    # Both sides resolved the same way, rather than one of them compared against whatever
    # `FileHandler` stored. Same file under two spellings is the case this has to get right.
    wanted = path.resolve()
    with _drain_lock:
        for token, drain in _drains.items():
            written = getattr(drain.handler, "baseFilename", None)
            if drain.job_id == job_id and written is not None and Path(written).resolve() == wanted:
                del _drains[token]
                return drain.handler
    return None


def _close_the_drains(chosen: Callable[[_Drain], bool]) -> None:
    """Take the matching handlers out of the waiting set and close them, once each.

    The pop happens under the lock and the close outside it, so the GUI thread and the listener
    thread can both call this without either holding the lock across file I/O.
    """
    with _drain_lock:
        tokens = [token for token, drain in _drains.items() if chosen(drain)]
        closing = [_drains.pop(token) for token in tokens]
    for drain in closing:
        _detach_and_close(drain.handler)


def _detach_and_close(handler: logging.Handler) -> None:
    """Take a handler off the application's logger and close it. Whoever gets here first wins.

    Both threads reach this, but only through a pop under `_drain_lock`, so exactly one of them
    reaches it per handler. `logging` locks the rest: `Handler.close()` and `Handler.handle()`
    take the same handler lock, so this cannot close a file the listener is mid-write on.
    """
    logging.getLogger(APP_SLUG).removeHandler(handler)
    with contextlib.suppress(Exception):
        handler.close()


#: The one queue workers send records on, and the listener draining it. Process-wide rather
#: than per-manager: a queue and a thread for every `DownloadManager` would mean one per test in
#: the integration suite, and the lifetime of a log sink is the lifetime of the process, not of
#: whichever object happened to want one first.
_worker_queue: Any = None
_listener: _ToWhicheverHandlersWeHaveNow | None = None


#: The handle-is-gone codes a queue read can legitimately end on (`T090-R1`).
#:
#: `EBADF` is the POSIX answer; `ERROR_INVALID_HANDLE` is Windows', and the captured traceback that
#: started `T-090` shows it as `[WinError 6] The handle is invalid` out of an overlapped `ReadFile`.
#: Nothing else is a closure: an `EIO` from the same read is a transport fault, and treating it as
#: end-of-stream is what `T090-R1` reported.
_CLOSED_HANDLE_ERRNOS: Final = frozenset({errno.EBADF})
_INVALID_HANDLE_WINERROR: Final = 6

#: **`multiprocessing`'s own guard raises an `OSError` with no `errno` at all** — measured while
#: narrowing this predicate, and the reason a code-only check was not enough.
#: `multiprocessing.connection.Connection._check_closed` is three lines long and reads
#: `if self._handle is None: raise OSError("handle is closed")`. That is a sentinel, not a system
#: error, so it carries no number to match on.
#:
#: Matching its literal is narrower than the alternatives, which is why it wins: accepting *any*
#: `errno is None` would readmit most of what `T090-R1` asked to be excluded, and this string is
#: CPython's own and has been stable across the versions this project supports.
_CLOSED_SENTINEL_MESSAGE: Final = "handle is closed"


def _is_closed_handle(error: OSError) -> bool:
    """Whether `error` says the queue's handle is gone, rather than that the read failed.

    Three forms, because the read path can end in three ways and only the codes were obvious:

    - `winerror == 6` — Windows' `ERROR_INVALID_HANDLE`, from the overlapped `ReadFile`.
    - `errno == EBADF` — the POSIX equivalent, from the raw descriptor.
    - **`OSError("handle is closed")` with no `errno`** — `multiprocessing`'s own check, which
      fires before either of the above can. This is the form the slow-handler path actually
      produces, measured; a predicate built only from error codes let it through and broke
      `T074-R3`'s regression on the first run.

    `winerror` and `errno` are consulted independently rather than one per platform. Windows raises
    `OSError` carrying `winerror` and CPython also maps it onto an `errno`, so checking both means
    the predicate does not depend on which a given call site populates.
    """
    if getattr(error, "winerror", None) == _INVALID_HANDLE_WINERROR:
        return True
    if error.errno in _CLOSED_HANDLE_ERRNOS:
        return True
    return error.errno is None and str(error) == _CLOSED_SENTINEL_MESSAGE


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

    @property
    def thread(self) -> threading.Thread | None:
        """The listener's own thread, while it still has one. Read before `stop()` drops it."""
        return self._thread

    def handle(self, record: logging.LogRecord) -> None:
        token = getattr(record, _DRAIN_FIELD, None)
        if token is not None:
            # A marker, not a line. Reaching it here is the proof that every record put on the
            # queue before it has already been through the loop below (`T038-R2`).
            _finish_the_drain(token)
            return
        record = self.prepare(record)
        for handler in logging.getLogger(APP_SLUG).handlers:
            if record.levelno >= handler.level:
                handler.handle(record)

    def stop(self) -> None:
        """Ask the thread to finish, and **return without waiting for it** (`T038-R2`).

        The inherited `stop()` joins. That join is on whichever thread called it, which in this
        application is the GUI thread by way of `DownloadManager.shutdown()` — and it lasts as
        long as whatever the listener is currently inside. One queued handler call taking two
        seconds held `shutdown()` for 2.001 s, which is `T013-R2`'s rejected blocking teardown
        again with log I/O in place of a process wait.

        The sentinel still goes on the queue, so the thread still ends; what changes is that
        nobody stands and watches. Its own exit path closes the queue and any handler still
        waiting for a marker, because after the sentinel there is no one left to do either.
        """
        if self._thread is None:
            return
        self._thread = None
        with contextlib.suppress(Exception):
            self.enqueue_sentinel()

    def _queue_is_closed(self) -> bool:
        """Whether the queue this listener reads has been shut.

        **`_closed` is private and there is no public equivalent**, which is worth stating rather
        than hiding: `multiprocessing.queues.Queue` exposes `close()` but nothing that reports
        whether it happened. `getattr` with a default means a queue type that lacks the attribute —
        a `queue.Queue` in a unit test, say — reads as *not closed*, so an unexplained failure
        raises instead of being swallowed. That is the safe direction for `T091-R1`: the defect was
        suppressing too much.
        """
        return bool(getattr(self.queue, "_closed", False))

    def dequeue(self, block: bool) -> Any:
        """Read one record, and treat a closed queue as the end of the stream (`T074-R3`).

        **The exit wait is bounded and therefore cannot be relied on.** It gives the listener five
        seconds; a handler slower than that — measured at 5.1 s — leaves the thread still reading
        when the wait returns and `multiprocessing` finalises the queue underneath it. Then
        `dequeue` raises into an interpreter that is already tearing down, where the exception has
        nowhere to go: `threading.excepthook` is gone and only a header reaches stderr.

        A queue that has been closed is a stream that has ended, so this says so rather than
        raising. That makes the outcome correct whether or not the wait finished in time — the
        ordering fix is what makes it *prompt*, and this is what makes it *safe*.

        **Narrow to the closure forms, and `T090-R1` is why it had to become narrower.** This
        docstring already claimed `OSError` meant "the closed handle (`WinError 6` on Windows,
        `EBADF` elsewhere)" while the code caught *every* `OSError`. A real transport fault — an
        `EIO` out of the receive path — was therefore converted into a normal end of stream: the
        listener exited cleanly, swept its pending drains, and every later record vanished with no
        thread exception to say why. The contract was right and the implementation was wider than
        it.

        `EOFError` is the other end going away, and `ValueError` is a queue closed in *this*
        process — measured: `multiprocessing.Queue.get()` on a closed queue raises
        `ValueError: … is closed`, with no `errno` at all. Both are unambiguous and stay.

        Anything else is a real fault and still raises.
        """
        try:
            return super().dequeue(block)
        except OSError as error:
            if not _is_closed_handle(error):
                raise
            # `_sentinel` is `QueueListener`'s own end-of-stream marker; typeshed does not
            # declare it, which is the same gap `_monitor` has one method down.
            return self._sentinel  # type: ignore[attr-defined]
        except EOFError, ValueError:
            # **Closure is decided by the queue's state, not by the exception** (`T091-R1`).
            # `Queue.get()` deserializes inside the same call that reads, so both of these mean
            # either "the queue is shut" or "the bytes were not a record" — and only the first is
            # an end of stream. Measured: a closed queue raises `ValueError(... is closed)` with
            # `_closed` already `True`, while a truncated payload raises from an **open** queue.
            if not self._queue_is_closed():
                raise
            return self._sentinel  # type: ignore[attr-defined]

    # `_monitor` is the listener thread's body. It is private, and typeshed does not declare it,
    # so the call up to it is the one place in this module that has to say so out loud.
    def _monitor(self) -> None:
        """The listener thread. Everything the unjoined `stop()` no longer does happens here.

        Closing the queue belongs here rather than in `stop()` for the same reason the join is
        gone: this is the moment nothing will read it again. Handlers still waiting for a marker
        on **this** queue are closed too — after the sentinel, no marker on it will ever arrive.
        """
        queue: Any = self.queue
        try:
            super()._monitor()  # type: ignore[misc]
        finally:
            _close_the_drains(lambda drain: drain.queue is queue)
            with contextlib.suppress(Exception):
                queue.close()


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
        # **Registered here, not at import, and the ordering is the whole point** (`T-074`).
        #
        # `atexit` runs handlers last-registered-first. `multiprocessing` registers its own
        # `_exit_function` the first time it is used — which is the line above — and that handler
        # finalises queues and closes their pipes. A handler registered at *import* of this module
        # is therefore registered **earlier** and runs **later**: after multiprocessing has already
        # closed the queue this listener is still reading.
        #
        # Measured on Windows, with the listener asked to stop while a backlog remained:
        #
        #     File "logging/handlers.py", in dequeue -> self.queue.get(block)
        #     File "multiprocessing/connection.py", in _get_more_data
        #       ov, err = _winapi.ReadFile(self._handle, left, overlapped=True)
        #     OSError: [WinError 6] The handle is invalid
        #
        # An overlapped `ReadFile` whose handle is closed underneath it. Registering after the
        # queue exists puts this handler later in the list and therefore *before* multiprocessing's
        # own, so the listener is finished before anything closes what it is reading.
        global _exit_registered
        if not _exit_registered:
            atexit.register(_wait_at_exit)
            _exit_registered = True
    return _worker_queue


def stop_listening_for_worker_logs() -> threading.Thread | None:
    """Ask the listener to stop and drop the queue with it. **Waits for nothing** (`T038-R2`).

    **Both, or neither.** Stopping the listener while keeping the queue leaves the next caller of
    `worker_log_queue()` holding a queue nothing drains: workers log into a pipe nobody reads,
    silently. Found twice — once as a hang, and again as an ordering failure after
    `DownloadManager.shutdown()` started calling this, where a later manager's worker output
    vanished entirely. Both globals are therefore dropped here, together, so the next caller
    builds a fresh pair.

    What is *not* done here is waiting: this is reached from `DownloadManager.shutdown()` on the
    GUI thread, and the listener may be inside a slow handler. The thread finishes on its own
    time and closes the queue as it goes — see `_ToWhicheverHandlersWeHaveNow._monitor`. A
    caller that genuinely needs the thread to be gone, which no GUI path does, asks for it
    explicitly through `wait_for_the_log_listener_to_stop()`.

    **Returns the thread it just asked to stop**, or `None` when nothing was running. Callers
    that need to know when the records are safely written hold that thread rather than asking
    this module later: "the listener" is process-wide, and a caller which never started one
    would otherwise find itself waiting on somebody else's.
    """
    global _listener, _worker_queue
    stopping = None
    if _listener is not None:
        stopping = _listener.thread
        if stopping is not None:
            # Pruned as we go, so a long-lived process does not accumulate dead threads.
            _stopping[:] = [thread for thread in _stopping if thread.is_alive()]
            _stopping.append(stopping)
        _listener.stop()
        _listener = None
    _worker_queue = None
    return stopping


#: Every listener thread asked to stop and not yet seen to finish (`T074-R2`).
#:
#: **A list, because a single slot silently forgot the earlier one.** This held only the most
#: recently stopped thread, so a second lifecycle overwrote the first — and the exit wait then
#: joined the newest listener while an older one was still reading a queue that was about to be
#: finalised. A two-lifecycle probe reproduced exactly that.
_stopping: list[threading.Thread] = []

#: Whether the exit wait has been registered. **Once, not once per lifecycle.**
#:
#: `atexit.register` was called from every `worker_log_queue()`, so a process with two lifecycles
#: got two handlers and the second pass happened to collect what the first had skipped. That made
#: the defect `T074-R2` reports invisible to a test — the wait was wrong, and a duplicate
#: registration covered for it. One registration means the list below is the only thing that
#: remembers, which is what makes it testable.
_exit_registered = False


def _wait_at_exit() -> None:
    """Let a stopped listener finish before the interpreter finalises (`T-074`).

    **The thread is a daemon and nothing waited for it.** `logging.handlers.QueueListener` makes
    its `_monitor` thread a daemon, and `stop_listening_for_worker_logs()` deliberately does not
    join it (`T038-R2`) — the GUI thread must not block on a slow handler. Both of those are
    right. What was missing is anywhere that the wait *is* safe.

    Without this, a process could exit with the listener still inside its exit path, closing a
    `multiprocessing.Queue`. Measured on Windows: 250 iterations of the `T-074` shape ended with
    `Exception in thread Thread-250 (_monitor):` and **no traceback** — at finalisation
    `threading.excepthook` is already gone, so only the header is written. Adding an explicit wait
    made it disappear and the listener report a clean finish.

    `atexit` is where that wait belongs: the main thread, after Qt has quit, at a moment when
    blocking costs nobody anything. Bounded, because a hang here would turn a tidy exit into one
    the user has to kill.

    **What this does not claim.** `T-074` is an access violation naming this same thread, and it
    has never been reproduced. This removes a demonstrated race on the path that crash implicates;
    absence of a fault that was already absent 0 times in 36 is not evidence that it is fixed.
    """
    with contextlib.suppress(Exception):
        stop_listening_for_worker_logs()
        wait_for_the_log_listener_to_stop(timeout=5.0)


def wait_for_the_log_listener_to_stop(timeout: float = 5.0) -> bool:
    """Block until the stopped listener's thread has returned.

    **Never call this on the GUI thread**: that wait is the thing `stop_listening_for_worker_logs`
    exists without (`T038-R2`). Returns whether the thread finished within `timeout`, and `True`
    when there was nothing to wait for.
    """
    deadline = time.monotonic() + timeout
    for thread in list(_stopping):
        thread.join(max(0.0, deadline - time.monotonic()))
    still_running = [thread for thread in _stopping if thread.is_alive()]
    _stopping[:] = still_running
    return not still_running


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
