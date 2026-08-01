"""The provenance boundary, and the bound on a job's log (`T-084`, `DAT-003`, `REQ-026`).

`DAT-003` as amended by `T-049` makes the boundary **who put the value there**, not what it looks
like. `T-084`'s criterion says so in as many words and says why: *"A gate that only proves the
first would pass an implementation that scrubs everything, which is the failure `DAT-003` records
twice"*. So both directions are asserted here, one test each, and neither is a corollary of the
other.
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
    THIRD_PARTY_FIELD,
    YtdlpLog,
    forget_the_secrets,
    job_log_path,
    open_job_log,
    redact,
    remember_a_secret,
    third_party_logger,
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

    third_party_logger("ytdlp").error("ERROR: rejected the token %s", SUPPLIED_SECRET)
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

    YtdlpLog(third_party_logger("ytdlp")).debug(f"[generic] Extracting URL: {requested}")

    text = written(tmp_path, job_log)
    assert password not in text
    assert token not in text
    assert "https://example.invalid/video" in text


def test_a_cookie_path_yt_dlp_emitted_is_still_there_character_for_character(
    tmp_path: Path, job_log: logging.Handler
) -> None:
    """**Direction two** — and the reason the criterion insists on it.

    `NFR-006` requires a third party's prose intact, and two implementations that scrubbed it by
    shape are on record failing: three credential escapes between them, and one Critical regression
    that turned a user's output directory into a relative path. A log that scrubs everything looks
    safe and is unusable.
    """
    third_party_logger("ytdlp").error("ERROR: unable to open cookie database %s", COOKIE_PATH)

    text = written(tmp_path, job_log)
    assert COOKIE_PATH in text, (
        "the cookie path yt-dlp itself named was scrubbed; that is the 'scrubs everything' "
        "implementation DAT-003 records two failed attempts at"
    )


def test_the_same_path_in_this_application_s_own_line_is_redacted(
    tmp_path: Path, job_log: logging.Handler
) -> None:
    """**The two directions meet on one value**, which is what makes this provenance and not shape.

    The identical string is kept in one line and removed from the other. A rule reading the text
    could not produce both results, so this fails for any shape-based implementation regardless of
    how good its patterns are.
    """
    third_party_logger("ytdlp").error("ERROR: unable to open %s", COOKIE_PATH)
    logging.getLogger("tracksandtrails.worker").info("passing %s to the extractor", COOKIE_PATH)

    text = written(tmp_path, job_log)
    assert text.count(COOKIE_PATH) == 1
    assert "<redacted>" in text


def test_redact_alone_makes_the_same_distinction() -> None:
    """The function under both flags, so the boundary is not only observable through a handler."""
    remember_a_secret(SUPPLIED_SECRET)

    assert redact(COOKIE_PATH, third_party=True) == COOKIE_PATH
    assert redact(COOKIE_PATH) == "<redacted>"
    assert SUPPLIED_SECRET not in redact(f"token {SUPPLIED_SECRET}", third_party=True)


def test_a_record_is_marked_only_by_the_third_party_logger() -> None:
    """The mark is the whole mechanism, so what sets it is asserted rather than assumed."""
    records: list[logging.LogRecord] = []

    class Spy(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    root = logging.getLogger("tracksandtrails")
    spy = Spy()
    root.addHandler(spy)
    try:
        third_party_logger("ytdlp").info("theirs")
        logging.getLogger("tracksandtrails.worker").info("ours")
    finally:
        root.removeHandler(spy)

    marks = [getattr(record, THIRD_PARTY_FIELD, False) for record in records]
    assert marks == [True, False]


def test_asking_twice_does_not_mark_a_record_twice() -> None:
    """`logging` caches loggers by name, so a second `addFilter` would stack."""
    first = third_party_logger("ytdlp")
    second = third_party_logger("ytdlp")

    assert first is second
    assert len(first.filters) == 1


# --- the bound --------------------------------------------------------------------------------


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
        YtdlpLog(third_party_logger("ytdlp")).info("[download]  53.7% of 12.00MiB at %(speed)s")
        handler.flush()
        text = job_log_path("job-1", tmp_path).read_text(encoding="utf-8")
    finally:
        root.removeHandler(handler)
        handler.close()

    assert "53.7% of 12.00MiB at %(speed)s" in text
