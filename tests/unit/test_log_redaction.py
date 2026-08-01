"""Log redaction, and the bound on a job's log (`T-084`, `DAT-003`, `REQ-026`).

**Redaction here is origin-agnostic, and this file used to say the opposite.**

`T-084` shipped a provenance-aware scheme on the reading that `DAT-003`'s `T-049` amendment made
the boundary *who put the value there*. That amendment does say so — **about the database**. The
section immediately after it is headed *"`T-038` is unchanged and origin-agnostic"* and says every
log this application emits is redacted whatever the provenance of the text inside it, because
storage and emission are different sinks with different rules.

`T084-R1` filed that as **Critical**, and the reason it was Critical rather than merely wrong is
worth keeping: the scheme kept exact `remember_a_secret()` values for third-party records and
dropped the pattern rules — and **no production caller registers anything**, so that tier was empty.
A yt-dlp line echoing the source URL wrote its userinfo password and signed query to the job log
verbatim, onto a surface with a Copy button.

**`T-084`'s second acceptance criterion is therefore unsatisfiable as written** — it asks that a
cookie path yt-dlp emitted survive character for character, which accepted `DAT-003` forbids at this
sink. That conflict is the maintainer's to resolve and is recorded in the task, not settled here.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from tracks_and_trails.core import logging as app_logging
from tracks_and_trails.core.logging import (
    JOB_LOG_BACKUPS,
    MAX_JOB_LOG_BYTES,
    YtdlpLog,
    forget_the_secrets,
    job_log_path,
    open_job_log,
    redact,
    remember_a_secret,
    ytdlp_logger,
)

#: A path yt-dlp really does name in a diagnostic when a profile cannot be read.
COOKIE_PATH = "/home/sean/.mozilla/firefox/ab12.default-release/cookies.sqlite"

#: A literal this application would be holding and would register. Long enough to clear
#: `remember_a_secret`'s minimum, and shaped like nothing the pattern rules would find.
SUPPLIED_SECRET = "hunter2-supplied-by-this-application"  # noqa: S105 - that is the point


@pytest.fixture(autouse=True)
def _no_leftover_secrets() -> Iterator[None]:
    forget_the_secrets()
    yield
    forget_the_secrets()


@pytest.fixture
def job_log(tmp_path: Path) -> Iterator[logging.Handler]:
    """A per-job handler on a temporary directory, stamping as the worker's queue handler does.

    The stamp is inserted **before** the job filter. Order is not cosmetic: `_OnlyThisJob` refuses
    an unstamped record, so a stamp added after it never runs and the file stays empty — which is
    the shape of failure this whole module is about, a log that exists and says nothing.
    """
    handler = open_job_log("job-1", directory=tmp_path)
    handler.filters.insert(0, app_logging._StampTheJob("job-1"))
    root = logging.getLogger("tracksandtrails")
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    yield handler
    root.removeHandler(handler)
    handler.close()


def written(tmp_path: Path, handler: logging.Handler) -> str:
    handler.flush()
    return job_log_path("job-1", tmp_path).read_text(encoding="utf-8")


# --- the boundary, both directions ------------------------------------------------------------


def test_a_value_this_application_supplied_does_not_reach_the_log(
    tmp_path: Path, job_log: logging.Handler
) -> None:
    """**Direction one** — the guarantee `DAT-003`'s provenance table actually makes.

    Asserted through third-party prose deliberately: a supplied value is removed *wherever it
    appears*, including inside a diagnostic somebody else wrote. An implementation that skipped
    redaction entirely for marked records would pass the other direction and fail here.
    """
    remember_a_secret(SUPPLIED_SECRET)

    ytdlp_logger().error("ERROR: rejected the token %s", SUPPLIED_SECRET)
    logging.getLogger("tracksandtrails.worker").info("using %s", SUPPLIED_SECRET)

    text = written(tmp_path, job_log)
    assert SUPPLIED_SECRET not in text
    assert text.count("<redacted>") == 2, "one of the two routes kept the supplied value"


def test_a_credential_in_the_requested_url_does_not_reach_a_yt_dlp_log(
    tmp_path: Path, job_log: logging.Handler
) -> None:
    """The production route cannot depend on a caller registering the request first.

    `DAT-003`'s accepted T-049 amendment says log emission remains origin-agnostically redacted.
    The source URL is handed to yt-dlp and yt-dlp routinely echoes it through its logger, so both
    userinfo and a signed query are credentials at this sink even though the diagnostic is marked
    third-party prose.
    """
    password = "password-that-must-not-be-logged"  # noqa: S105 - reviewer marker
    token = "signed-query-token-that-must-not-be-logged"  # noqa: S105 - reviewer marker
    requested = f"https://alice:{password}@example.invalid/video?token={token}"

    YtdlpLog(ytdlp_logger()).debug(f"[generic] Extracting URL: {requested}")

    text = written(tmp_path, job_log)
    assert password not in text
    assert token not in text
    assert "https://example.invalid/video" in text


def test_a_cookie_path_is_redacted_even_when_yt_dlp_itself_named_it(
    tmp_path: Path, job_log: logging.Handler
) -> None:
    """**The accepted rule, asserted in the direction the code now takes** (`T084-R1`).

    This test previously asserted the opposite, because `T-084` read the amendment's database table
    as governing logs. It does not: *"Every log this application **emits** is redacted, whatever the
    provenance of the text inside it."*

    **The `NFR-006` cost is real and is recorded rather than hidden.** A user reading this log will
    not see which cookie database yt-dlp could not open. That is a genuine loss of diagnostic value,
    it is what accepted `DAT-003` chooses at this sink, and `T-084`'s criterion asking for the
    opposite needs a maintainer ruling — not an implementation that quietly picks a side.
    """
    ytdlp_logger().error("ERROR: unable to open cookie database %s", COOKIE_PATH)

    text = written(tmp_path, job_log)
    assert COOKIE_PATH not in text
    assert "<redacted>" in text


def test_the_same_value_is_treated_identically_on_both_routes(
    tmp_path: Path, job_log: logging.Handler
) -> None:
    """**Origin-agnostic, stated as an equality rather than as two separate assertions.**

    The identical string goes down yt-dlp's logger and this application's, and neither copy
    survives. A provenance-aware implementation produces two different results here, which is
    precisely how `T084-R1`'s regression would come back.
    """
    ytdlp_logger().error("ERROR: unable to open %s", COOKIE_PATH)
    logging.getLogger("tracksandtrails.worker").info("passing %s to the extractor", COOKIE_PATH)

    text = written(tmp_path, job_log)
    assert COOKIE_PATH not in text
    assert text.count("<redacted>") == 2, "the two routes were redacted differently"


def test_redact_takes_no_provenance_argument() -> None:
    """**The signature is the guarantee** (`T084-R1`).

    A caller cannot ask for a laxer rendering because there is no parameter to ask with. Asserted
    on the signature rather than on behaviour: behaviour tests would still pass against a version
    that accepted the flag and defaulted it to safe, and the defect was a caller passing `True`.
    """
    import inspect

    remember_a_secret(SUPPLIED_SECRET)
    assert redact(COOKIE_PATH) == "<redacted>"
    assert SUPPLIED_SECRET not in redact(f"token {SUPPLIED_SECRET}")
    assert list(inspect.signature(redact).parameters) == ["text"]


def test_a_job_log_is_bounded_and_the_bound_is_stated(
    tmp_path: Path, job_log: logging.Handler
) -> None:
    """`T-084`'s criterion: growth is bounded, **and the bound is stated**.

    Stated as `MAX_JOB_LOG_BYTES * (JOB_LOG_BACKUPS + 1)` = 4 MiB per job. Asserted by writing
    past it rather than by reading the constants back, which would only prove arithmetic.

    The **most recent** lines survive, which is the half that matters: a log is kept for a bug
    report, and the failure is at the end.
    """
    logger = logging.getLogger("tracksandtrails.worker")
    for index in range(6000):
        logger.info("line %d %s", index, "x" * 400)

    job_log.flush()
    directory = job_log_path("job-1", tmp_path).parent
    files = list(directory.glob("job-1.log*"))
    total = sum(path.stat().st_size for path in files)

    assert len(files) <= JOB_LOG_BACKUPS + 1, f"rotation kept {len(files)} files"
    assert total <= MAX_JOB_LOG_BYTES * (JOB_LOG_BACKUPS + 1)
    # **The assertion that catches an unbounded handler.** The two above pass for a single file
    # that never rotates, as long as the test does not happen to write past 4 MiB — a mutation
    # removing the bound survived them. This one is about the live file and fails immediately.
    assert job_log_path("job-1", tmp_path).stat().st_size <= MAX_JOB_LOG_BYTES, (
        "the live log is larger than its own bound, so nothing is rotating it"
    )
    assert "line 5999" in job_log_path("job-1", tmp_path).read_text(encoding="utf-8"), (
        "the newest line was rotated away, so the bound kept the least useful half"
    )


# --- the yt-dlp bridge ------------------------------------------------------------------------


def test_yt_dlp_screen_output_is_logged_at_info_not_debug() -> None:
    """**The quiet failure this would otherwise be.**

    yt-dlp calls `logger.debug` for its ordinary screen output. The worker's handler sits at
    `INFO`, so routing that straight to `DEBUG` would create the job log, leave it empty, and look
    entirely correct — `ai/TESTING.md` §13's "guards that cannot fire" in its other form.
    """
    seen: list[tuple[int, str]] = []

    class Spy(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            seen.append((record.levelno, record.getMessage()))

    logger = logging.getLogger("tracksandtrails.test-bridge")
    spy = Spy()
    logger.addHandler(spy)
    logger.setLevel(logging.DEBUG)
    try:
        bridge = YtdlpLog(logger)
        bridge.debug("[generic] Extracting URL: https://example.invalid/v")
        bridge.debug("[debug] Loaded 1744 extractors")
        bridge.warning("Falling back to generic extractor")
        bridge.error("ERROR: Unable to download webpage")
    finally:
        logger.removeHandler(spy)

    assert [level for level, _ in seen] == [
        logging.INFO,
        logging.DEBUG,
        logging.WARNING,
        logging.ERROR,
    ]


def test_a_percent_sign_in_yt_dlp_s_output_survives_to_the_file(tmp_path: Path) -> None:
    """yt-dlp's output routinely contains `%` — a percentage, or a `%(title)s` template echoed back.

    **This does not test the `"%s", message` spelling.** A mutation to `logger.info(message)`
    survived: `logging` applies `%`-formatting only when a record carries args, so both spellings
    behave identically and the defensive form prevents nothing today. The spelling stays as the
    habit that keeps being right if args are ever added; the claim that it prevents a defect does
    not, because nothing can demonstrate it (`ai/TESTING.md` §13).

    What *is* worth asserting is the whole path: a percent sign reaches the file intact, through
    the formatter and the redaction rules, neither of which may consume it.
    """
    handler = open_job_log("job-1", directory=tmp_path)
    handler.filters.insert(0, app_logging._StampTheJob("job-1"))
    root = logging.getLogger("tracksandtrails")
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        YtdlpLog(ytdlp_logger()).info("[download]  53.7% of 12.00MiB at %(speed)s")
        handler.flush()
        text = job_log_path("job-1", tmp_path).read_text(encoding="utf-8")
    finally:
        root.removeHandler(handler)
        handler.close()

    assert "53.7% of 12.00MiB at %(speed)s" in text


def test_the_database_keeps_verbatim_what_the_log_redacts(tmp_path: Path) -> None:
    """**`DAT-003`'s two sinks, asserted against each other on one value** (`T-084`, amended).

    This is the criterion the maintainer's ruling put in place of the one that contradicted the
    decision. Storage and emission are different sinks with different rules, and the way to keep
    them from drifting into each other is to pin both to a single string:

    - the **database** stores the extractor's message verbatim, which is where `NFR-006`'s promise
      lives and what a retry or a bug report can still read;
    - the **log** redacts it, whoever wrote it.

    An implementation that scrubbed everywhere fails the first half; one that redacted nothing, or
    redacted by provenance, fails the second. Neither could pass this by accident.
    """
    from dataclasses import replace

    from tracks_and_trails.core.errors import ErrorKind
    from tracks_and_trails.core.job_state import JobStatus
    from tracks_and_trails.core.models import DownloadRequest, Job
    from tracks_and_trails.persistence import db
    from tracks_and_trails.persistence.repositories import JobRepository

    diagnostic = f"ERROR: unable to open cookie database {COOKIE_PATH}"

    request = DownloadRequest(
        url="https://example.invalid/clip",
        output_directory=str(tmp_path),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )
    repository = JobRepository(db.connect(tmp_path / "library.sqlite3"))
    repository.append([Job(id="job-9", url=request.url, request=request)])
    stored = repository.get("job-9")
    assert stored is not None
    for status in (JobStatus.PROBING, JobStatus.READY, JobStatus.RUNNING):
        stored = repository.get("job-9")
        assert stored is not None
        repository.update(stored.with_status(status))
    running = repository.get("job-9")
    assert running is not None
    repository.update(replace(running.with_failure(ErrorKind.EXTRACTOR_ERROR, diagnostic)))

    persisted = repository.get("job-9")
    assert persisted is not None
    assert persisted.error_message == diagnostic, (
        "the database paraphrased or scrubbed the extractor's message; NFR-006 keeps its promise "
        "at this sink and DAT-003 says so"
    )

    handler = open_job_log("job-9", directory=tmp_path)
    handler.filters.insert(0, app_logging._StampTheJob("job-9"))
    root = logging.getLogger("tracksandtrails")
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        ytdlp_logger().error("%s", diagnostic)
        handler.flush()
        emitted = job_log_path("job-9", tmp_path).read_text(encoding="utf-8")
    finally:
        root.removeHandler(handler)
        handler.close()

    assert COOKIE_PATH not in emitted, "the log kept a path DAT-003 redacts at this sink"
    assert "<redacted>" in emitted
