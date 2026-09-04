"""`T-038`: redaction at the handler, proven through real handlers writing real files.

Every assertion below reads what was **emitted**. A test that called `redact()` directly would
prove the function works and say nothing about the property the task is actually about — that a
call site cannot leak by forgetting to use it (`ai/TESTING.md` §13, `ARCHITECTURE.md` §8).
"""

from __future__ import annotations

import errno
import logging
import logging.handlers
import multiprocessing as mp
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tracks_and_trails.core import logging as app_logging
from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.core.paths import APP_SLUG

#: One recognisable string per leak shape. Each appears in exactly one test input, so a failure
#: names which route let it out. Not credentials — invented markers, shaped like the real thing
#: so the patterns under test see what they would see in the field.
TOKEN = "sk-live-7c6c-must-not-appear"  # noqa: S105 - a marker, not a secret
COOKIE_VALUE = "SID=7c6c-secret-session"


@pytest.fixture(autouse=True)
def a_clean_logging_tree() -> object:
    """Logging is global state; leaving handlers behind breaks the next test, not this one."""
    yield
    app_logging.forget_the_secrets()
    tree = logging.getLogger("tracksandtrails")
    for handler in list(tree.handlers):
        tree.removeHandler(handler)
        handler.close()


def emitted(tmp_path: Path, emit: Callable[[logging.Logger], None]) -> str:
    """Run `emit` against a configured application log and return what reached the file."""
    path = app_logging.configure_logging(directory=tmp_path, level=logging.DEBUG)
    emit(logging.getLogger("tracksandtrails.test"))
    for handler in logging.getLogger("tracksandtrails").handlers:
        handler.flush()
    return path.read_text(encoding="utf-8")


# --- the four routes a message can take (T-038 acceptance criteria) ---------------------------


def test_a_token_in_a_percent_style_argument_is_redacted(tmp_path: Path) -> None:
    written = emitted(
        tmp_path,
        lambda log: log.info("probing %s", f"https://example.invalid/v?token={TOKEN}"),
    )

    assert TOKEN not in written, "a %-style argument was formatted after redaction, not before"
    assert "https://example.invalid/v" in written, "the address itself must survive"


def test_a_token_in_a_caller_formatted_string_is_redacted(tmp_path: Path) -> None:
    """The commonest real call site, and the one a call-site helper would not cover."""
    written = emitted(
        tmp_path,
        lambda log: log.info(f"probing https://example.invalid/v?token={TOKEN}"),
    )

    assert TOKEN not in written


def test_a_token_in_an_extra_field_is_redacted(tmp_path: Path) -> None:
    """`extra=` reaches the output only through a format string; when it does, it is redacted."""
    handler = logging.handlers.MemoryHandler(10)
    handler.setFormatter(app_logging.RedactingFormatter("%(message)s | %(url)s"))
    record = logging.LogRecord(
        name="tracksandtrails.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="probing",
        args=(),
        exc_info=None,
    )
    record.url = f"https://example.invalid/v?token={TOKEN}"

    assert TOKEN not in handler.format(record)


def test_a_url_inside_an_exception_traceback_is_redacted(tmp_path: Path) -> None:
    """`exc_info` is rendered by the formatter, so it goes through the same one rewrite."""

    def emit(log: logging.Logger) -> None:
        try:
            raise RuntimeError(f"refused https://example.invalid/v?token={TOKEN}")
        except RuntimeError:
            log.exception("the probe failed")

    written = emitted(tmp_path, emit)

    assert "the probe failed" in written
    assert "RuntimeError" in written, "the traceback must still be there"
    assert TOKEN not in written


def test_a_careless_call_site_logging_a_whole_request_still_leaks_nothing(tmp_path: Path) -> None:
    """The criterion that distinguishes handler-level redaction from the call-site kind.

    Nobody writes `log.info("starting %s", redact(request))`. They write this, and the repr
    carries the URL with whatever is in its query string.
    """
    request = DownloadRequest(
        url=f"https://example.invalid/v?token={TOKEN}",
        output_directory=str(tmp_path),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        proxy="http://proxy.invalid:8080",
    )

    written = emitted(tmp_path, lambda log: log.info("starting %s", request))

    assert TOKEN not in written
    assert "example.invalid" in written, "the log must still say what it was working on"


# --- what redaction covers --------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        f"Cookie: {COOKIE_VALUE}",
        f"set-cookie: {COOKIE_VALUE}; Path=/",
        f"sending Cookie: {COOKIE_VALUE}",
    ],
)
def test_cookie_material_never_reaches_the_file(tmp_path: Path, line: str) -> None:
    written = emitted(tmp_path, lambda log: log.info(line))

    assert COOKIE_VALUE not in written


@pytest.mark.parametrize(
    "path",
    [
        "/home/someone/.config/cookies.txt",
        r"C:\Users\Someone\cookies.sqlite",
        "/tmp/yt-dlp-cookiefile-7c6c",  # noqa: S108 - a string under test, nothing is written
    ],
)
def test_a_cookie_file_path_never_reaches_the_file(tmp_path: Path, path: str) -> None:
    written = emitted(tmp_path, lambda log: log.info("loading cookies from %s", path))

    assert path not in written
    assert app_logging.REDACTED in written


def test_url_userinfo_is_removed(tmp_path: Path) -> None:
    """A proxy credential's shape, even though `DownloadRequest` cannot hold one (`T-014`)."""
    written = emitted(tmp_path, lambda log: log.info("via http://user:hunter2@proxy.invalid:8080"))

    assert "hunter2" not in written
    assert "proxy.invalid:8080" in written


def test_a_registered_literal_is_redacted_wherever_it_appears(tmp_path: Path) -> None:
    """The bounded escape hatch: an exact value the application knows, not a pattern."""
    app_logging.remember_a_secret(TOKEN)

    written = emitted(tmp_path, lambda log: log.info("the value was %s, plainly", TOKEN))

    assert TOKEN not in written


def test_a_short_registered_value_is_ignored(tmp_path: Path) -> None:
    """Over-redaction is a failure too: a two-character "secret" eats ordinary prose."""
    app_logging.remember_a_secret("ok")

    written = emitted(tmp_path, lambda log: log.info("the token was ok, and the download is ok"))

    assert "the token was ok" in written


def test_a_bare_separator_does_not_redact_every_slash_in_the_log(tmp_path: Path) -> None:
    """**`T197-R7`.** The separator exemption could take the whole log with it.

    A previous round waived the byte floor for any value containing `/` or `\\`, reasoning that
    such a string is not a bare word and cannot collide with prose. The counter-example is one
    character long: `[cookies] file = "/"` is a syntactically valid setting. It is refused as a
    directory — **after** `remember_a_secret` has already been handed `/`, at which point every
    slash in every later line is replaced and paths, URLs and ordinary prose stop being readable.

    Two things are asserted, because either alone is satisfiable by the wrong fix: the slash must
    still be *there*, and the line must still be *whole*.
    """
    app_logging.remember_a_secret("/")

    written = emitted(
        tmp_path, lambda log: log.info("read /home/alice/file and audio/video from the source")
    )

    assert "audio/video" in written, f"a stored bare separator ate the log:\n{written}"
    assert "/home/alice/file" in written
    assert app_logging.REDACTED not in written, (
        f"something was redacted that is not a secret:\n{written}"
    )


@pytest.mark.parametrize("root", ["/", "//", "\\", "C:\\", "///"])
def test_a_value_that_is_only_separators_names_no_secret(root: str) -> None:
    """A filesystem root is not a credential, and refusing it is not a length judgement.

    The byte floor happens to reject most of these, which is why the guard is separate: `///` is
    three bytes and `C:\\` is three, but a four-separator value would clear the floor and still be
    a root. What makes them unregisterable is that they name nothing, not that they are short.
    """
    app_logging.forget_the_secrets()
    app_logging.remember_a_secret(root)

    assert app_logging.redact(f"reading {root} now") == f"reading {root} now"


def test_a_short_relative_path_is_still_covered_by_its_absolute_form(tmp_path: Path) -> None:
    """What the separator exemption was added for, and what actually covers it (`T197-R7`).

    The exemption existed so a short *relative* cookie path could be registered directly. It was
    never load-bearing: `core/settings.py` registers the **absolute** spelling, which clears the
    floor on its own — so the protection the exemption was standing in for was already there, and
    removing it costs nothing. That is asserted here at the same layer rather than taken on trust.
    """
    app_logging.forget_the_secrets()
    short = "密"
    absolute = str((tmp_path / short).absolute())
    app_logging.remember_a_secret(absolute)

    written = emitted(tmp_path, lambda log: log.info("reading %s for this download", absolute))

    assert absolute not in written, f"the absolute form of a short path leaked:\n{written}"
    assert "for this download" in written, "the line was scrubbed rather than the path"


@pytest.mark.parametrize(
    ("line", "marker"),
    [
        (r"loading C:\Users\A Person\cookies.txt", "A Person"),
        ("loading cookies.txt from the working directory", "cookies.txt"),
        ("cookiefile=/tmp/yt-dlp-cookies-7c6c", "yt-dlp-cookies-7c6c"),
        ("refused https://[bad/v?token=review-url-token-7c6c", "review-url-token-7c6c"),
        ("via user:review-proxy-pass-7c6c@proxy.invalid:8080", "review-proxy-pass-7c6c"),
    ],
)
def test_the_shapes_that_got_past_the_first_version(tmp_path: Path, line: str, marker: str) -> None:
    """`T038-R1`: five false negatives found at the sink, each written through a real handler.

    Every one of these is a shape the first version's rules could not see rather than a shape it
    decided to allow — a path component with a space in it, a filename with no directory, a URL
    malformed enough to break the parser (which then returned it *unchanged*, so being harder to
    parse made a string safer), and a proxy credential written the ordinary way, without a
    scheme for the URL rule to anchor on.
    """
    written = emitted(tmp_path, lambda log: log.info(line))

    assert marker not in written, f"{marker!r} reached the log file: {written.strip()!r}"


@pytest.mark.parametrize(
    "line",
    [
        "loading cookies from the browser profile",
        "the cookie jar was empty",
        "selected format=best height=1080",
    ],
)
def test_ordinary_prose_survives_the_cookie_rules(tmp_path: Path, line: str) -> None:
    """The other direction, and it is not decoration (`T014-R6`).

    Closing the "bare filename" hole by matching any token containing "cookie" also matches the
    **word**, and "loading <redacted> from the browser profile" is a log nobody can use. The
    extension requirement is what separates a filename from a noun, and this is what holds it
    there.
    """
    written = emitted(tmp_path, lambda log: log.info(line))

    assert line in written, (
        f"redaction ate ordinary prose: {written.strip()!r}. Over-redaction is a failure too — a "
        "log that cannot describe what happened has lost its only purpose."
    )


def test_a_bare_name_equals_value_is_not_chased(tmp_path: Path) -> None:
    """The limit of this design, asserted so nobody discovers it in a review instead.

    `SID=abc` with no header around it is indistinguishable from `height=1080`, `format=best` or
    any other ordinary diagnostic. A pattern wide enough to catch it redacts most of every log
    line, and this project has four `T-018` rounds on record about where recognisers end.

    It is also outside what `REQ-026` binds: cookie *contents* are never a supplied value here —
    `DownloadRequest` carries a browser name, and yt-dlp reads the jar itself, so this
    application never holds one. If that ever changes, the value is known at the moment it is
    held, and `remember_a_secret()` redacts it exactly rather than by guessing.
    """
    written = emitted(tmp_path, lambda log: log.info("selected format=best height=1080"))

    assert "format=best height=1080" in written, (
        "ordinary key=value diagnostics must survive; redacting them would make the log useless"
    )


def test_an_output_path_is_left_alone(tmp_path: Path) -> None:
    """`T014-R6`: scrubbing prose destroyed a user's output directory, which was Critical.

    A log that cannot say where the file went has broken the one thing it is for.
    """
    destination = str(tmp_path / "Videos" / "A Clip.mp4")

    written = emitted(tmp_path, lambda log: log.info("wrote %s", destination))

    assert destination in written


# --- where the files go, and who formats them -------------------------------------------------


def test_every_handler_on_our_tree_redacts(tmp_path: Path) -> None:
    """The property the whole design rests on, asserted rather than assumed.

    A handler added without `RedactingFormatter` is a hole in exactly the guarantee
    `ARCHITECTURE.md` §8 makes, and it would be invisible — the other handlers would keep
    passing their own tests.
    """
    app_logging.configure_logging(directory=tmp_path, stream=sys.stderr)
    handler = app_logging.open_job_log("job-1", directory=tmp_path)
    tree = logging.getLogger("tracksandtrails")
    tree.addHandler(handler)

    assert tree.handlers, "the tree has no handlers, so this test proves nothing"
    for installed in tree.handlers:
        assert isinstance(installed.formatter, app_logging.RedactingFormatter), (
            f"{installed!r} formats without redaction"
        )


def test_the_logs_live_under_platformdirs_and_not_beside_the_application() -> None:
    """`NFR-004`. The repository must never be a log destination."""
    application = app_logging.application_log_path()
    job = app_logging.job_log_path("job-1")
    repository = Path(__file__).resolve().parents[2]

    assert not application.is_relative_to(repository), application
    assert not job.is_relative_to(repository), job
    assert job.parent.parent == application.parent, "a job log belongs beside the application log"
    assert "tracksandtrails" in str(application).lower()


def test_a_job_log_holds_that_job_and_is_redacted(tmp_path: Path) -> None:
    """A per-job handler takes its own job's records, redacts them, and refuses the rest.

    Both halves matter (`T038-R2`). The first version of this test attached the handler and
    logged straight into it, which passed while the handler had no filter at all — so it proved
    the file could be written, not that it held one job's output. Records arrive stamped by the
    worker that produced them; an unstamped one belongs to no job and is refused rather than
    shared, because a per-job log whose contents depend on what else was running is worse than
    none.
    """
    handler = app_logging.open_job_log("job-1", directory=tmp_path)
    log = logging.getLogger("tracksandtrails.job")
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    try:
        log.info(
            f"probing https://example.invalid/v?token={TOKEN}",
            extra={app_logging.JOB_FIELD: "job-1"},
        )
        log.info("this line belongs to nobody")
        log.info("this line is another job's", extra={app_logging.JOB_FIELD: "job-2"})
        handler.flush()
    finally:
        log.removeHandler(handler)
        handler.close()

    written = app_logging.job_log_path("job-1", tmp_path).read_text(encoding="utf-8")

    assert "probing" in written
    assert TOKEN not in written
    assert "belongs to nobody" not in written, (
        "an unstamped record reached a job log; it belongs to no job and must not be shared"
    )
    assert "another job's" not in written, "another job's record reached this job's log"


def test_a_generated_log_is_scanned_for_a_known_token(tmp_path: Path) -> None:
    """The acceptance criterion in its own words: generate a log, then hunt the token in it.

    Deliberately separate from the per-route tests. Those assert one shape each; this one takes
    the file as a whole and looks for the value **in any form**, including the percent-encoded
    and uppercased spellings a rewrite could produce.

    The cookie value appears here behind its header, which is the shape it has in a real
    diagnostic. A bare `NAME=value` with nothing around it is not redacted and deliberately is
    not chased — see `test_a_bare_name_equals_value_is_not_chased`.
    """

    def emit(log: logging.Logger) -> None:
        log.info("probe %s", f"https://example.invalid/v?auth={TOKEN}")
        log.warning(f"retrying https://example.invalid/v?auth={TOKEN}#frag={TOKEN}")
        log.error("cookie jar at /home/someone/cookies.txt sent Cookie: %s", COOKIE_VALUE)

    written = emitted(tmp_path, emit)

    for form in (TOKEN, TOKEN.upper(), TOKEN.replace("-", "%2D"), COOKIE_VALUE):
        assert form not in written, f"{form!r} reached the log file"


# --- the worker half --------------------------------------------------------------------------


def test_a_worker_sends_records_to_the_parent_and_the_parent_redacts(tmp_path: Path) -> None:
    """`T-038`: worker logs reach the parent's log, and are rendered by the parent's handlers.

    Records travel unformatted, so redaction happens once, in the process that owns the file.
    A worker cannot emit an unredacted line even in principle — it does not do the formatting.
    """
    queue: Any = mp.get_context("spawn").Queue()
    app_logging.worker_logging_handler(queue)
    logging.getLogger("tracksandtrails.worker").info(
        "probing %s", f"https://example.invalid/v?token={TOKEN}"
    )

    record = queue.get(timeout=10)

    path = app_logging.configure_logging(directory=tmp_path)
    listener = logging.handlers.QueueListener(
        mp.get_context("spawn").Queue(), *logging.getLogger("tracksandtrails").handlers
    )
    listener.handle(record)
    for handler in logging.getLogger("tracksandtrails").handlers:
        handler.flush()
    written = path.read_text(encoding="utf-8")

    assert "probing" in written, "the worker's line never reached the parent's log"
    assert TOKEN not in written


def test_worker_records_follow_the_handlers_the_application_has_now(tmp_path: Path) -> None:
    """The listener resolves handlers per record, not once when it was built.

    An ordering defect, found by the full suite and invisible to the test that owns this path:
    the listener is created the first time a worker starts, and `configure_logging()` can run
    after that. A listener holding the handler list from construction would then write every
    worker line to handlers nobody reads — a log that fails silently, which is the worst kind.

    Built directly rather than through `worker_log_queue()`, because that one is process-wide:
    a test that stops and replaces it reaches into every other test in the run, which is how
    this file first broke the integration suite.
    """
    import queue as queue_module

    listener = app_logging._ToWhicheverHandlersWeHaveNow(queue_module.Queue())
    path = app_logging.configure_logging(directory=tmp_path, level=logging.DEBUG)

    listener.handle(
        logging.LogRecord(
            name="tracksandtrails.worker",
            level=logging.WARNING,
            pathname=__file__,
            lineno=1,
            msg="probing %s",
            args=(f"https://example.invalid/v?token={TOKEN}",),
            exc_info=None,
        )
    )
    for handler in logging.getLogger("tracksandtrails").handlers:
        handler.flush()
    written = path.read_text(encoding="utf-8")

    assert "probing" in written, (
        "a worker record went to handlers captured before the log was configured, so it reached "
        "nothing"
    )
    assert TOKEN not in written, "the parent rendered the record without redacting it"


# --- handing a per-job log back (T038-R2) ------------------------------------------------------


def a_local_queue(monkeypatch: pytest.MonkeyPatch) -> Any:
    """A queue standing in for the process-wide one, with no thread draining it.

    Driving the listener by hand is what makes these deterministic: "the marker has not been
    reached yet" is a state this test holds open, rather than a race it has to win. The
    process-wide queue is deliberately untouched — a test that stops and replaces it reaches into
    every other test in the run.
    """
    import queue as queue_module

    queue: Any = queue_module.Queue()
    monkeypatch.setattr(app_logging, "_worker_queue", queue)
    return queue


def test_a_job_log_stays_open_until_its_queued_records_have_come_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T038-R2`: the handler is closed by the marker's arrival, not by the session ending.

    Two queues, and only the result one says the session is over — so a record can still be in
    the log queue when the manager releases the job. Closing the handler at that moment loses the
    line. Here the marker is held in the queue, and the handler must still be attached and open.
    """
    queue = a_local_queue(monkeypatch)
    listener = app_logging._ToWhicheverHandlersWeHaveNow(queue)
    tree = logging.getLogger("tracksandtrails")
    handler = app_logging.open_job_log("job-1", directory=tmp_path)
    tree.addHandler(handler)

    app_logging.close_job_log_when_drained("job-1", handler)

    assert handler in tree.handlers, (
        "the per-job handler was detached before its queued records arrived; anything still in "
        "the log queue would be written to the application log alone"
    )
    late = logging.LogRecord(
        name="tracksandtrails.worker",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="a late line",
        args=None,
        exc_info=None,
    )
    setattr(late, app_logging.JOB_FIELD, "job-1")
    listener.handle(late)
    handler.flush()
    written = app_logging.job_log_path("job-1", tmp_path).read_text(encoding="utf-8")

    listener.handle(queue.get_nowait())

    assert "a late line" in written, (
        f"the record arrived after the session was released and never reached its own log: "
        f"{written!r}"
    )
    assert handler not in tree.handlers, (
        "the marker came through and the handler is still attached; a per-job file handle now "
        "outlives its job for the rest of the process"
    )
    assert handler.stream is None, "the handler was detached but its file was left open"  # type: ignore[attr-defined]


def test_reopening_a_jobs_log_never_leaves_that_file_unattended(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A record dispatched between reopening a job's log and attaching it must still be written.

    The ordinary `T-016` flow releases a session and starts another for the same job at once, so
    the reopen lands while the first handler may still be waiting for its marker. Closing the
    first here and handing back a new one looks equivalent and is not: the caller attaches the
    replacement in a separate step, and a stamped record dispatched in the gap belongs to a job
    whose file nothing is holding open. It is written nowhere, and there is no second chance.

    So the gap is what this test holds open. The listener dispatches a record at exactly the
    moment the manager has a handler in its hand and has not attached it yet.
    """
    queue = a_local_queue(monkeypatch)
    listener = app_logging._ToWhicheverHandlersWeHaveNow(queue)
    tree = logging.getLogger("tracksandtrails")
    first = app_logging.open_job_log("job-1", directory=tmp_path)
    tree.addHandler(first)
    app_logging.close_job_log_when_drained("job-1", first)

    second = app_logging.open_job_log("job-1", directory=tmp_path)
    in_the_gap = logging.LogRecord(
        name="tracksandtrails.worker",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="a line from the session that just ended",
        args=None,
        exc_info=None,
    )
    setattr(in_the_gap, app_logging.JOB_FIELD, "job-1")
    listener.handle(in_the_gap)
    tree.addHandler(second)
    second.flush()
    written = app_logging.job_log_path("job-1", tmp_path).read_text(encoding="utf-8")

    assert "a line from the session that just ended" in written, (
        f"a stamped record dispatched between the reopen and the attach was written nowhere: "
        f"{written!r}"
    )
    assert second is first, (
        "reopening a job's log while its previous handler is still draining should hand the same "
        "open handler back; a replacement cannot be attached without leaving that gap"
    )
    assert [handler for handler in tree.handlers if handler is second] == [second], (
        "one job's file has two handlers on it; every line would be written twice"
    )


def test_a_drain_onto_a_different_file_is_never_taken_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Handing a draining handler back is right only when it writes where the caller asked.

    `open_job_log` takes a `directory`, so "the same job" and "the same file" are not the same
    condition. A handler taken back on the job id alone would send the new session's records to
    the directory the *previous* one was opened with — the log misrouted rather than lost, which
    is harder to notice. The pending drain is left alone instead: different files have no
    conflict, and it closes when its own marker arrives.
    """
    a_local_queue(monkeypatch)
    tree = logging.getLogger("tracksandtrails")
    first = app_logging.open_job_log("job-1", directory=tmp_path / "first")
    tree.addHandler(first)
    app_logging.close_job_log_when_drained("job-1", first)

    second = app_logging.open_job_log("job-1", directory=tmp_path / "second")
    tree.addHandler(second)

    assert second is not first, (
        "a handler still draining onto a different file was handed back for this one; every "
        "record of the new session would be written to the previous session's directory"
    )
    assert Path(second.baseFilename).parent == tmp_path / "second" / "jobs", (  # type: ignore[attr-defined]
        f"the handler does not write where it was asked to: {second.baseFilename}"  # type: ignore[attr-defined]
    )


def test_a_marker_that_will_never_arrive_does_not_hold_a_job_log_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A listener that stops closes what it was going to close. The marker is taken away here.

    Nothing in production is expected to lose one — a marker is always queued ahead of the
    sentinel. That is exactly why the case needs a test: an invariant nobody can reach is also an
    invariant nobody notices breaking, and the cost of being wrong is a file handle attached to
    the application's logger for the rest of the process.
    """
    queue = a_local_queue(monkeypatch)
    listener = app_logging._ToWhicheverHandlersWeHaveNow(queue)
    tree = logging.getLogger("tracksandtrails")
    handler = app_logging.open_job_log("job-1", directory=tmp_path)
    tree.addHandler(handler)
    app_logging.close_job_log_when_drained("job-1", handler)
    queue.get_nowait()

    listener.enqueue_sentinel()
    listener._monitor()

    assert handler not in tree.handlers, (
        "the listener stopped with a per-job handler still waiting for a marker that is no longer "
        "coming, and left it attached"
    )
    assert handler.stream is None  # type: ignore[attr-defined]


def test_a_job_log_is_closed_at_once_when_no_listener_is_running(tmp_path: Path) -> None:
    """With no queue there is no marker to wait for, so waiting would be waiting forever."""
    tree = logging.getLogger("tracksandtrails")
    handler = app_logging.open_job_log("job-1", directory=tmp_path)
    tree.addHandler(handler)

    app_logging.close_job_log_when_drained("job-1", handler)

    assert handler not in tree.handlers
    assert handler.stream is None  # type: ignore[attr-defined]


def test_the_logging_module_needs_no_qt() -> None:
    """`ARCHITECTURE.md` §3: the worker installs logging, and the worker inherits no Qt.

    Asserted in a fresh interpreter, because this one has already imported Qt for other tests
    and `sys.modules` would show it whatever this module does.
    """
    probe = (
        "import sys\n"
        "import tracks_and_trails.core.logging\n"
        "qt = [name for name in sys.modules if name.startswith('PySide6')]\n"
        "print(qt)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "[]", f"importing the logging module pulled in {result.stdout}"


# --- the listener must outlive nothing it is still reading (`T-074`) --------------------------

#: A process that asks the listener to stop while a backlog is still in the pipe, then exits.
#:
#: The shape `T-074` implicates, made deterministic. `stop_listening_for_worker_logs()` does not
#: wait — correctly, since the GUI thread must not block on a slow handler (`T038-R2`) — so at
#: exit the listener can still be inside `queue.get()`, which on Windows is an overlapped
#: `ReadFile` on the queue's pipe. If `multiprocessing`'s own exit handler closes that pipe first,
#: the read is left holding a handle that no longer exists.
EXIT_WITH_A_BACKLOG = """
import logging, sys
from tracks_and_trails.core.logging import stop_listening_for_worker_logs, worker_log_queue

queue = worker_log_queue()
record = logging.LogRecord("t", logging.INFO, "backlog.py", 1, "backlog", None, None)
for _ in range(20000):
    queue.put(record)
stop_listening_for_worker_logs()
sys.exit(0)
"""


def test_the_log_listener_is_not_left_reading_a_closed_queue(tmp_path: Path) -> None:
    """`T-074`: exiting must not pull the queue out from under the listener thread.

    **Measured, both platforms, before the fix:** 6/6 on Linux and 8/8 on Windows ended with

    ```
    File "logging/handlers.py", in dequeue -> self.queue.get(block)
    File "multiprocessing/connection.py", in _get_more_data
      ov, err = _winapi.ReadFile(self._handle, left, overlapped=True)
    OSError: [WinError 6] The handle is invalid
    ```

    The cause is `atexit` ordering, which is why an obvious fix did not work. Handlers run
    last-registered-first; `multiprocessing` registers its own the first time it is used, and that
    one finalises queues. A handler registered at *import* of `core.logging` is registered earlier
    and therefore runs **later** — after the queue it was meant to protect has been closed.
    Registering it where the queue is created puts it after multiprocessing's and so ahead of it.

    Asserted on **stderr of a real process**, because that is the only place the failure appears:
    a daemon thread raising during interpreter finalisation cannot be caught in-process, and by
    then `threading.excepthook` is gone — which is why the first observation of this had a header
    and no traceback.
    """
    result = subprocess.run(
        [sys.executable, "-c", EXIT_WITH_A_BACKLOG],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode == 0, f"exit {result.returncode}\nstderr: {result.stderr}"
    assert "Exception in thread" not in result.stderr, (
        "the listener thread raised while the interpreter was tearing down, which means it was "
        f"still reading a queue something else had closed:\n{result.stderr}"
    )


#: Two listener lifecycles, the first still draining (`T074-R2`).
#:
#: **Asserted on records delivered, not on a thread exception.** The single `_stopping` slot let a
#: second listener displace the first, so the exit wait joined the newest and returned while the
#: older one was still working. With `T074-R3`'s `dequeue` guard in place that no longer *raises* —
#: it ends cleanly — so the only remaining evidence is the records that never got written. A test
#: looking for `Exception in thread` passes against the defect, which is what the first version of
#: this one did.
TWO_LIFECYCLES = """
import logging, sys, time
from tracks_and_trails.core.paths import APP_SLUG
from tracks_and_trails.core.logging import (
    stop_listening_for_worker_logs, worker_log_queue,
)

class SlowFile(logging.Handler):
    def emit(self, record):
        time.sleep(0.05)
        with open(sys.argv[1], "a", encoding="utf-8") as sink:
            sink.write("record\\n")

# The listener resolves handlers from the *app* logger, not root, so a handler installed anywhere
# else is never consulted and the backlog drains instantly.
logging.getLogger(APP_SLUG).addHandler(SlowFile())
logging.getLogger(APP_SLUG).setLevel(logging.INFO)

record = logging.LogRecord(APP_SLUG, logging.INFO, "backlog.py", 1, "backlog", None, None)

first = worker_log_queue()
for _ in range(40):
    first.put(record)
stop_listening_for_worker_logs()

# A second lifecycle, which used to displace the first in the single stopping slot.
second = worker_log_queue()
second.put(record)
stop_listening_for_worker_logs()
sys.exit(0)
"""

#: One lifecycle, enough backlog that ordering decides whether it survives (`T091-R2`).
#:
#: `TWO_LIFECYCLES` proves the *list* remembers more than one stopped listener. It cannot prove the
#: **registration ordering** on its own: with two lifecycles a second `atexit` handler used to
#: collect what the first had skipped, which is precisely why `T074-R2` said a duplicate
#: registration covered for a wrong wait. One lifecycle removes that cover.
ONE_LIFECYCLE = """
import logging, sys, time
from tracks_and_trails.core.paths import APP_SLUG
from tracks_and_trails.core.logging import (
    stop_listening_for_worker_logs, worker_log_queue,
)

class SlowFile(logging.Handler):
    def emit(self, record):
        time.sleep(0.05)
        with open(sys.argv[1], "a", encoding="utf-8") as sink:
            sink.write("record\\n")

# The listener resolves handlers from the *app* logger, not root. A handler on root is never
# consulted, the backlog drains instantly, and the test passes whatever the ordering is.
logging.getLogger(APP_SLUG).addHandler(SlowFile())
logging.getLogger(APP_SLUG).setLevel(logging.INFO)

record = logging.LogRecord(APP_SLUG, logging.INFO, "backlog.py", 1, "backlog", None, None)

only = worker_log_queue()
for _ in range(40):
    only.put(record)
stop_listening_for_worker_logs()
sys.exit(0)
"""

#: A handler slower than the exit wait's own timeout (`T074-R3`).
#:
#: The wait is bounded at five seconds and cannot be otherwise — an unbounded one would turn a
#: tidy exit into a hang. So the listener has to survive being closed under, not merely be waited
#: for.
SLOW_HANDLER = """
import logging, sys, time
from tracks_and_trails.core import logging as tt

class Slow(logging.Handler):
    def emit(self, record):
        time.sleep(5.1)

logging.getLogger(tt.APP_SLUG).addHandler(Slow())
logging.getLogger(tt.APP_SLUG).setLevel(logging.INFO)
queue = tt.worker_log_queue()
record = logging.LogRecord(tt.APP_SLUG, logging.INFO, "slow.py", 1, "slow", None, None)
for _ in range(4):
    queue.put(record)
tt.stop_listening_for_worker_logs()
sys.exit(0)
"""


def run_probe(source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        cwd=Path(__file__).resolve().parents[2],
    )


def test_every_stopped_listener_is_waited_for_not_just_the_newest(tmp_path: Path) -> None:
    """`T074-R2`: a second lifecycle must not make the first one's records disappear.

    The exit wait kept one thread in one slot, so starting a second listener overwrote the first.
    The wait then joined the newest, returned, and the process exited with the older listener
    still draining — the records it had not reached are simply lost.

    **Counted, not inferred from stderr.** `T074-R3`'s guard means an orphaned listener now ends
    cleanly rather than raising, so "no exception" is true whether or not this defect is present.
    The records are the only thing that still tells them apart.
    """
    written = tmp_path / "records.txt"
    result = subprocess.run(
        [sys.executable, "-c", TWO_LIFECYCLES, str(written)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode == 0, f"exit {result.returncode}\nstderr: {result.stderr}"
    delivered = written.read_text(encoding="utf-8").count("record") if written.exists() else 0
    assert delivered == 41, (
        f"{delivered} of 41 records reached the handler. A listener that is stopped and then "
        "forgotten takes whatever it had not written with it"
    )


def test_a_handler_slower_than_the_wait_does_not_leave_a_raising_thread() -> None:
    """`T074-R3`: the bounded wait can expire, so the listener must survive being closed under.

    Five seconds is a deliberate bound — an unbounded wait at exit is a hang. A handler slower
    than it therefore *will* leave the thread reading, and the fix cannot be "wait longer": it is
    that a closed queue means the stream ended, which `dequeue` now says instead of raising.
    """
    result = run_probe(SLOW_HANDLER)
    assert result.returncode == 0, f"exit {result.returncode}\nstderr: {result.stderr}"
    assert "Exception in thread" not in result.stderr, (
        f"the listener raised after the wait gave up on it:\n{result.stderr}"
    )


# --- T-091: only closure ends the stream --------------------------------------------------


def test_the_three_closure_forms_are_recognised() -> None:
    """`T090-R1`: each is a way the queue's handle can be gone, and only these three are.

    Read directly rather than through a live queue, because two of the three cannot be produced on
    this platform: `winerror` is Windows-only, and `EBADF` comes from the raw descriptor path.
    """
    from tracks_and_trails.core.logging import _is_closed_handle

    posix = OSError(errno.EBADF, "Bad file descriptor")
    windows = OSError(22, "The handle is invalid")
    # `setattr` rather than a direct assignment with an ignore comment: `OSError.winerror` exists
    # only on Windows, so mypy needs the ignore on Linux and rejects it as unused under
    # `--platform win32`. There is no single spelling of the assignment that satisfies both gates,
    # and `ai/TESTING.md` §3 requires both. This one needs neither.
    setattr(windows, "winerror", 6)  # noqa: B010
    sentinel = OSError("handle is closed")

    assert _is_closed_handle(posix), "EBADF is the POSIX closure"
    assert _is_closed_handle(windows), "WinError 6 is the Windows closure"
    assert _is_closed_handle(sentinel), (
        "multiprocessing's own guard raises OSError('handle is closed') with no errno; this is the "
        "form the slow-handler path actually produces"
    )


@pytest.mark.parametrize(
    ("name", "error"),
    [
        ("EIO — a real transport fault", OSError(errno.EIO, "Input/output error")),
        ("ENOSPC", OSError(errno.ENOSPC, "No space left on device")),
        ("EPIPE", OSError(errno.EPIPE, "Broken pipe")),
        ("a bare OSError with a different message", OSError("something else went wrong")),
        (
            "an errno-less OSError whose text merely contains the sentinel",
            OSError("the handle is closed now"),
        ),
    ],
)
def test_a_non_closure_oserror_is_not_a_closure(name: str, error: OSError) -> None:
    """`T090-R1`'s finding: every `OSError` became end-of-stream, so a real fault lost records.

    The last case is the interesting one. The sentinel is matched by **equality**, not containment,
    so prose that happens to mention it is still a fault. A substring check would have reopened the
    hole in a smaller doorway.
    """
    from tracks_and_trails.core.logging import _is_closed_handle

    assert not _is_closed_handle(error), f"{name} was treated as a closed queue"


def test_a_non_closure_oserror_propagates_out_of_dequeue() -> None:
    """The predicate is only useful if `dequeue` acts on it — asserted through the real method.

    `T090-R1` did not report a wrong predicate; it reported a `dequeue` that suppressed everything.
    Testing the helper alone would leave that untested.
    """
    from tracks_and_trails.core.logging import _ToWhicheverHandlersWeHaveNow

    class _Failing:
        def get(self, block: bool = True) -> object:
            raise OSError(errno.EIO, "Input/output error")

    listener = _ToWhicheverHandlersWeHaveNow(_Failing())  # type: ignore[arg-type]
    with pytest.raises(OSError, match="Input/output error"):
        listener.dequeue(True)


def test_a_closure_oserror_ends_the_stream_rather_than_raising() -> None:
    """The other half, so the test above cannot pass by `dequeue` simply never suppressing."""
    from tracks_and_trails.core.logging import _ToWhicheverHandlersWeHaveNow

    class _Closed:
        def get(self, block: bool = True) -> object:
            raise OSError("handle is closed")

    listener = _ToWhicheverHandlersWeHaveNow(_Closed())  # type: ignore[arg-type]
    assert listener.dequeue(True) is listener._sentinel  # type: ignore[attr-defined]


def test_one_lifecycle_delivers_every_record_it_was_given() -> None:
    """`T091-R2`: the post-queue registration rule, gated on its own without a second lifecycle.

    **Why this is not covered by the two-lifecycle test.** That one proves `_stopping` remembers
    more than the newest listener. It cannot isolate *when* the exit wait was registered, because a
    second `worker_log_queue()` used to register a second `atexit` handler, and the second pass
    collected what the first had skipped — `T074-R2`'s own finding was that a duplicate
    registration covered for a wrong wait. With one lifecycle there is no second pass to cover.

    The handler is on the **application** logger, not root. The listener resolves handlers from
    `APP_SLUG`, so a slow handler installed on root is never consulted, the backlog drains
    instantly, and the assertion holds no matter what the ordering is. Two of this file's probes
    were vacuous for exactly that reason before `T-090` corrected them.
    """
    with tempfile.TemporaryDirectory() as directory:
        written = Path(directory) / "records.txt"
        result = subprocess.run(
            [sys.executable, "-c", ONE_LIFECYCLE, str(written)],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
            cwd=Path(__file__).resolve().parents[2],
        )
        assert result.returncode == 0, f"exit {result.returncode}\nstderr: {result.stderr}"
        delivered = written.read_text(encoding="utf-8").count("record") if written.exists() else 0

    assert delivered == 40, (
        f"{delivered} of 40 records reached the handler. The exit wait was registered before "
        "multiprocessing's own, so it ran after the queue had already been finalised and the "
        "listener was cut off mid-backlog."
    )


def test_a_non_closure_oserror_from_a_real_queue_still_raises() -> None:
    """`T091-R2`: through a real `multiprocessing.Queue`, not a stand-in with a `get` method.

    The fake-queue test beside this one proves `dequeue` re-raises. It cannot prove the same of the
    **real** read path, which is where `T090-R1`'s `EIO` would arrive: `Queue.get()` acquires a
    lock, reads bytes off a connection and deserializes them, and only the middle step can fail
    this way. Injecting at `_recv_bytes` puts the fault where the real one would be.
    """
    queue: Any = mp.Queue()
    try:
        queue.put(logging.LogRecord(APP_SLUG, logging.INFO, __file__, 1, "x", None, None))
        time.sleep(0.1)  # let the feeder thread hand the bytes to the pipe

        def failing_recv(*_args: object, **_kwargs: object) -> bytes:
            raise OSError(errno.EIO, "Input/output error")

        queue._recv_bytes = failing_recv
        listener = app_logging._ToWhicheverHandlersWeHaveNow(queue)
        with pytest.raises(OSError, match="Input/output error"):
            listener.dequeue(True)
    finally:
        queue.close()
        queue.join_thread()


def test_a_deserialization_fault_on_an_open_queue_still_raises() -> None:
    """`T091-R1`: `EOFError` and `ValueError` are only end-of-stream when the queue is **shut**.

    `Queue.get()` reads and deserializes in one call, so a truncated payload surfaces as the same
    exception types a closed queue does. Suppressing both meant a corrupt record silently ended the
    listener and every later record went with it — the defect one type over from the `OSError` arm.
    """
    for fault in (EOFError("Ran out of input"), ValueError("could not unpickle")):
        queue: Any = mp.Queue()
        try:

            def failing_recv(
                *_args: object, _fault: BaseException = fault, **_kwargs: object
            ) -> bytes:
                raise _fault

            queue._recv_bytes = failing_recv
            listener = app_logging._ToWhicheverHandlersWeHaveNow(queue)
            with pytest.raises(type(fault)):
                listener.dequeue(True)
        finally:
            queue.close()
            queue.join_thread()


def test_the_same_faults_end_the_stream_once_the_queue_is_closed() -> None:
    """The other half, so the test above cannot pass by `dequeue` never suppressing at all."""
    queue: Any = mp.Queue()
    queue.close()
    queue.join_thread()
    listener = app_logging._ToWhicheverHandlersWeHaveNow(queue)

    def closed_recv(*_args: object, **_kwargs: object) -> bytes:
        raise ValueError("queue is closed")

    queue._recv_bytes = closed_recv
    assert listener.dequeue(True) is listener._sentinel  # type: ignore[attr-defined]


# --- T-282: a debug level, reachable without editing code -------------------------------------


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        pytest.param("DEBUG", logging.DEBUG, id="DEBUG"),
        pytest.param("debug", logging.DEBUG, id="lower case, which is what a person types"),
        pytest.param(" Warning ", logging.WARNING, id="surrounding space"),
        pytest.param("CRITICAL", logging.CRITICAL, id="CRITICAL"),
    ],
)
def test_a_level_name_resolves_to_its_level(given: str, expected: int) -> None:
    """`--log-level=debug` is what somebody types, so case and stray space cannot decide it."""
    assert app_logging.level_named(given) == expected


@pytest.mark.parametrize(
    "given",
    [
        pytest.param("chatty", id="not a level"),
        pytest.param("", id="empty"),
        pytest.param("10", id="a number, which this deliberately does not accept"),
        pytest.param("NOTSET", id="a real logging name this application does not offer"),
        pytest.param("getLogger", id="an attribute of the logging module that is not a level"),
    ],
)
def test_an_unknown_level_name_is_refused_rather_than_defaulted(given: str) -> None:
    """**`None`, not a fallback.** Silently running at `INFO` when somebody asked for `DEBUG`
    produces a log missing exactly what they turned it on to see.

    `getLogger` is in here because the resolution is an attribute lookup on the `logging` module:
    without the name check it would answer a function and pass an `isinstance(int)` test never.
    `NOTSET` is a real level name and is still refused, because this application does not offer it
    and a level nothing lists is one nobody can be told about.
    """
    assert app_logging.level_named(given) is None


def test_the_log_says_which_level_it_is_at(tmp_path: Path) -> None:
    """`T-282`: a log whose level is unknown makes an absent line ambiguous.

    *"It did not happen"* and *"it happened and was not recorded"* are different answers, and a
    reader six months later cannot tell them apart without this line.

    **Driven at `WARNING` deliberately.** The first version of the announcement used `root.info`,
    which is filtered out at `WARNING` and above — so the line was missing from exactly the runs
    whose level is least obvious, and this test is what said so. It is emitted at the level in
    force now.
    """
    for level, name in ((logging.DEBUG, "DEBUG"), (logging.WARNING, "WARNING")):
        # A directory each: the handler appends, so a shared one would carry the previous run's
        # announcement into this one and make the once-only assertion below measure the test.
        path = app_logging.configure_logging(directory=tmp_path / name, level=level)
        written = path.read_text(encoding="utf-8")

        assert f"logging at {name}" in written, (
            f"a run at {name} did not say what level it is at: {written!r}"
        )
        assert str(path) in written, "the announcement does not say where the log is"
        assert written.count("logging at ") == 1, "the level was announced more than once"


def test_every_handler_still_redacts_at_debug(tmp_path: Path) -> None:
    """`REQ-026` is a property of the handlers, and raising the volume must not touch it.

    A debug level changes *how much* is written and never *what may be* written. Asserted over
    every handler rather than over the file, because a second handler added later without a
    redactor is the way this regresses.
    """
    app_logging.configure_logging(directory=tmp_path, level=logging.DEBUG, stream=sys.stderr)
    root = logging.getLogger(APP_SLUG)

    assert root.handlers, "no handlers, so this asserts nothing"
    for handler in root.handlers:
        assert isinstance(handler.formatter, app_logging.RedactingFormatter), (
            f"{handler!r} formats through {handler.formatter!r}, which does not redact"
        )


@pytest.mark.parametrize(
    "level",
    [logging.DEBUG, logging.INFO, logging.WARNING],
    ids=["DEBUG", "INFO", "WARNING"],
)
def test_the_level_offered_to_a_worker_is_the_one_this_process_uses(
    tmp_path: Path, level: int
) -> None:
    """`T282-R2`: a worker filters where the application does, not at a hard-coded default.

    **Asserted here and not only through a spawned worker**, because the real-worker control cannot
    see it: at `INFO` the parent's own handlers drop a worker `DEBUG` record anyway, so carrying
    `DEBUG` into *every* worker unconditionally produces an identical application log. It would
    also put every worker `DEBUG` record on the queue on an ordinary run — the volume the default
    exists to avoid — and this is the assertion that notices.
    """
    app_logging.configure_logging(directory=tmp_path / str(level), level=level)

    assert app_logging.worker_log_level() == level
