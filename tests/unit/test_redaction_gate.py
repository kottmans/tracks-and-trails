"""**The redaction gate `T-197` exists to deliver, and `IMPLEMENTATION_PLAN.md` §Phase 4 exits on.**

*"Logs carry no cookies, cookie paths, proxy credentials or token-like parameters (`NFR-007`)"* is
a phase exit criterion, and until this file the project had the redaction **and** the criterion but
no single test standing for it. The parts were covered — `tests/unit/test_log_redaction.py` proves
`redact` on strings — and a criterion about the application is not met by a criterion about a
function.

## What this asserts, and the two directions it must hold in

`DAT-003`, as amended by `T-049` and again on 2026-08-10, draws the line at **provenance of the
value**, not at what the value looks like:

- **Values this application supplies** — a cookie file path it holds, a proxy's credentials,
  cookie contents — never reach a log, a stored diagnostic, an `ARC-008` settings report, or a
  crash path.
- **Prose a third party emitted** is stored verbatim in the database (`NFR-006`, `T-014`) and is
  still redacted on its way into a **log**, because `T-038` binds emission in full whatever wrote
  the text. That asymmetry is deliberate and was itself a Critical when it was got wrong
  (`T084-R1`); the two sinks have different rules on purpose.

**Both directions, because one alone passes the wrong implementation.** A gate proving only that
secrets vanish is satisfied by scrubbing everything — the failure `DAT-003` records twice, at the
cost of two recognisers and a corrupted output path. So the verbatim-storage direction is asserted
here too, and it is the one a redaction change will break first.
"""

import logging
from io import StringIO
from pathlib import Path

import pytest

from tracks_and_trails.core import logging as logging_module
from tracks_and_trails.core import settings as app_settings
from tracks_and_trails.core.logging import LOG_FORMAT, RedactingFormatter, redact
from tracks_and_trails.core.models import DownloadRequest, Job

#: One of each thing `NFR-007` and `REQ-026` name, in the shapes they really arrive in.
A_COOKIE_PATH = "/home/sean/.config/tracksandtrails/cookies.txt"
A_BROWSER_JAR = "/home/sean/.mozilla/firefox/ab12cd.default/cookies.sqlite"
A_PROXY_WITH_CREDENTIALS = "http://alice:s3cr3t-p4ss@proxy.example.invalid:8080"
# The secret-detector below is right that this looks like a credential, which is the entire point:
# these are the shapes the gate must remove, written out so a reader can see what is asserted
# rather than a fixture name.
A_TOKEN_URL = "https://example.invalid/watch?v=abc123&token=deadbeefcafe0123&sig=zzz"  # noqa: S105
A_COOKIE_HEADER = "Cookie: SID=AbCdEf0123456789; HSID=secretvalue"
#: The same credential written **without a scheme**, which is a real way a proxy is configured and
#: a separate rule in `redact` (`_BARE_USERINFO`). Covered because it was not: removing that rule
#: left every assertion here green, since the well-formed URL above is handled by the URL rule
#: instead. A gate that exercises one of two rules reports on one of two rules.
A_BARE_PROXY = "bob:hunter2-secret@proxy.example.invalid:3128"

#: The substrings that must never survive into anything this application emits.
SECRETS = (
    "s3cr3t-p4ss",
    "deadbeefcafe0123",
    "AbCdEf0123456789",
    "secretvalue",
    "cookies.txt",
    "cookies.sqlite",
    "hunter2-secret",
)


def emitted(*lines: str) -> str:
    """What the application's own handlers would actually write for `lines`.

    Through `RedactingFormatter` rather than through `redact` directly: the formatter is what is
    installed, it renders first and redacts the rendered line, and a test calling `redact` would
    prove the function works while saying nothing about whether it is on the path.
    """
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(RedactingFormatter(LOG_FORMAT))
    log = logging.getLogger("tracksandtrails.redaction-gate")
    log.handlers = [handler]
    log.propagate = False
    log.setLevel(logging.DEBUG)
    for line in lines:
        log.warning("%s", line)
    return stream.getvalue()


def test_a_cookie_path_of_any_name_is_redacted_once_it_is_registered() -> None:
    """**`T197-R1`, a Critical, and the fixture choice that hid it.**

    `redact`'s shape rules recognise a path that *looks* like a cookie jar — `cookies.sqlite`,
    `.../cookies.txt`. A user may point at `~/session.txt`, and the review reproduced exactly that
    surviving the real formatter. **Every fixture in the first version of this gate was named
    `cookies.*`**, so the gate agreed with the rule instead of testing it.

    Guessing harder is the enumeration failure `DAT-003` records twice. **Knowing** is
    `remember_a_secret`, which exists for *"a literal this application is holding and knows is
    sensitive"* — composition registers the path when it takes it.
    """
    innocuous = "/home/alice/session.txt"
    logging_module.forget_the_secrets()
    try:
        assert innocuous in emitted(f"using cookies from {innocuous}"), (
            "this path is already redacted by shape, so it cannot show what registering buys"
        )

        logging_module.remember_a_secret(innocuous)
        written = emitted(f"using cookies from {innocuous}")

        assert innocuous not in written, f"a registered cookie path reached a log line:\n{written}"
        assert "using cookies from" in written, "the line was scrubbed rather than the path"
    finally:
        logging_module.forget_the_secrets()


def test_no_supplied_secret_survives_into_a_log() -> None:
    """The first direction: nothing this application holds reaches a line it writes."""
    written = emitted(
        f"using cookies from {A_COOKIE_PATH}",
        f"proxy configured: {A_PROXY_WITH_CREDENTIALS}",
        f"fetching {A_TOKEN_URL}",
        A_COOKIE_HEADER,
        f"opening {A_BROWSER_JAR}",
        f"proxy without a scheme: {A_BARE_PROXY}",
    )

    for secret in SECRETS:
        assert secret not in written, (
            f"{secret!r} reached a log line. NFR-007 and REQ-026 say it never does:\n{written}"
        )
    # **And the lines still say something**, which is the half a secrets-only assertion misses:
    # `redact` returning `<redacted>` for everything satisfies every line above and destroys the
    # log. Measured — that mutation passed the first version of this test, which is the failure
    # `DAT-003` records twice under a different name.
    for kept in ("using cookies from", "proxy configured", "fetching", "opening"):
        assert kept in written, (
            f"{kept!r} was removed along with the secrets. A log that scrubs everything is the "
            f"implementation DAT-003 records failing twice:\n{written}"
        )
    assert "proxy.example.invalid" in written, (
        "the proxy's host went with its credentials; only the userinfo is a secret"
    )
    assert "proxy without a scheme" in written


def test_a_settings_report_carries_no_secret_either() -> None:
    """**`T-197` names this route specifically**, and `T-146` widened it.

    `ARC-008` reports carry values straight out of the user's settings file — a cookie path, a
    proxy, a download folder — and `SettingsProblem.summary` is composed in `core/` where nothing
    redacts. It is safe because the report reaches the user through a *dialog*, and the same text
    is redacted on its way to a log. Both halves are asserted: the dialog keeps the path, the log
    does not.
    """
    problem = app_settings.SettingsProblem(
        Path("/home/sean/.config/tracksandtrails/settings.toml"),
        f'cookies.file is "{A_COOKIE_PATH}"\nproxy = "{A_PROXY_WITH_CREDENTIALS}"',
    )

    assert A_COOKIE_PATH in problem.summary, (
        "the dialog must name the file the user set; it is their own value, shown to them"
    )
    written = emitted(problem.summary)
    for secret in ("s3cr3t-p4ss", "cookies.txt"):
        assert secret not in written, f"{secret!r} reached a log through the ARC-008 report"
    assert "settings file could not be read" in written, (
        "the report itself was scrubbed away, so the log says a problem happened and not which"
    )


def test_a_crash_path_carries_no_secret() -> None:
    """A traceback is a log line like any other, and is the path nobody remembers to check."""
    try:
        raise RuntimeError(f"failed while reading {A_COOKIE_PATH} via {A_PROXY_WITH_CREDENTIALS}")
    except RuntimeError as error:
        written = emitted(f"unhandled: {error}")

    for secret in ("s3cr3t-p4ss", "cookies.txt"):
        assert secret not in written, f"{secret!r} survived into a crash diagnostic"
    assert "failed while reading" in written, (
        "the crash text was scrubbed with the secrets, leaving a diagnostic that diagnoses nothing"
    )


def test_a_cookie_path_cannot_be_carried_by_a_job_at_all() -> None:
    """**The structural half of `DAT-003`**, asserted rather than assumed (`T-197`).

    Row one of the provenance table is *structural* because the model cannot hold the value: there
    is no cookie-file field on `DownloadRequest`, and `cookies_from_browser` refuses anything that
    is not a browser name. A stored diagnostic and a job row therefore cannot contain a cookie path
    this application supplied — not because something filters it, but because nothing can put it
    there.
    """
    assert not any(
        "cookie" in name and "browser" not in name for name in DownloadRequest.__annotations__
    ), (
        "DownloadRequest gained a cookie field; DAT-003's first row is no longer structural and "
        "the decision must be revisited before this lands"
    )

    # **Both shapes**, because the first version of the validator only checked the component
    # before the colon and `firefox:/home/alice/cookies.sqlite` sailed through it into the job
    # JSON — `T197-R2`, a Critical. A path is refused wherever in the specification it appears.
    for shape in (A_COOKIE_PATH, f"firefox:{A_BROWSER_JAR}", "firefox:~/jar"):
        with pytest.raises(ValueError):
            DownloadRequest(
                url="https://example.invalid/v",
                output_directory=str(Path.home()),
                format_selector="best",
                output_template="%(title)s.%(ext)s",
                cookies_from_browser=shape,
            )


def test_a_path_yt_dlp_named_is_kept_verbatim_where_it_is_stored() -> None:
    """**The second direction, and the one a redaction change breaks first** (`DAT-003`, `T-014`).

    A gate proving only that secrets vanish is satisfied by an implementation that scrubs
    everything — which is what happened twice, once corrupting a user's output directory into a
    relative path. So this asserts the opposite: a cookie path **yt-dlp** named inside its own
    diagnostic survives into the stored `error_message` character for character, because
    `NFR-006` requires the extractor's words intact and the database is a different sink from a
    log.
    """
    said_by_ytdlp = f"ERROR: Could not read cookies from {A_BROWSER_JAR}: database is locked"
    job = Job(
        id="job-1",
        url="https://example.invalid/v",
        request=DownloadRequest(
            url="https://example.invalid/v",
            output_directory=str(Path.home()),
            format_selector="best",
            output_template="%(title)s.%(ext)s",
        ),
    ).with_failure(
        __import__(
            "tracks_and_trails.core.errors", fromlist=["ErrorKind"]
        ).ErrorKind.EXTRACTOR_ERROR,
        said_by_ytdlp,
    )

    assert job.error_message == said_by_ytdlp, (
        "the extractor's message was altered on its way into the job. NFR-006 requires it "
        "verbatim, and DAT-003 accepts a cookie path inside one at this sink"
    )
    # And the same text, on its way to a *log*, loses the path — the asymmetry that was a
    # Critical when it was made provenance-aware instead (`T084-R1`).
    emitted_line = redact(said_by_ytdlp)
    assert "cookies.sqlite" not in emitted_line, (
        "a cookie path survived into an emitted line. Storage and emission have different rules "
        "and this is the emission one"
    )
    assert "database is locked" in emitted_line, (
        "the extractor's reason was scrubbed along with the path, so the emitted line no longer "
        "says why anything failed — NFR-006's whole complaint about paraphrased errors"
    )


def test_the_worker_hands_cookies_to_the_probe_as_well_as_the_download() -> None:
    """**`T197-R3`.** A URL that needs signing in is *read* before it is downloaded.

    `T012-R5` is the same finding one option to the left: connection settings were added only
    after the probe's early return, so a URL needing the configured proxy failed while being read,
    before the download that would have used it was attempted. The cookies file repeated it —
    passed to the download's `_extract` and to neither probe.

    Driven at the worker's own boundary with stubs for the adapter and the resolved library,
    because what is under test is **which arguments `_extract` forwards**, and a real yt-dlp would
    answer a different question.
    """
    from tracks_and_trails.downloader import worker

    seen: dict[str, object] = {}

    class _Adapter:
        @staticmethod
        def build_options(_request: object, _template: str, **options: object) -> dict[str, object]:
            seen.update(options)
            return {}

    class _Ydl:
        def __init__(self, _options: object) -> None: ...
        def __enter__(self) -> _Ydl:
            return self

        def __exit__(self, *_: object) -> None: ...
        def extract_info(self, *_: object, **__: object) -> dict[str, object]:
            return {}

    class _Resolved:
        module = type("_Module", (), {"YoutubeDL": _Ydl})

    class _Reporter:
        def progress_hook(self, *_: object) -> None: ...
        def postprocessor_hook(self, *_: object) -> None: ...

    request = DownloadRequest(
        url="https://example.invalid/v",
        output_directory=str(Path.home()),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )
    jar = Path("/home/alice/session.txt")

    # Stubs rather than the real collaborators: what is under test is which arguments `_extract`
    # forwards, and a real yt-dlp would answer a different question. The ignore is the price of
    # substituting for two concrete types at a boundary that has no protocol.
    worker._extract(
        _Adapter(),
        request,
        _Resolved(),  # type: ignore[arg-type]
        _Reporter(),  # type: ignore[arg-type]
        probe_only=True,
        cookie_file=jar,
    )  # fmt: skip

    assert seen.get("cookie_file") == jar, (
        f"the probe was built with cookie_file={seen.get('cookie_file')!r}. An authenticated URL "
        "would fail while being read, before the download that would have used cookies"
    )
    assert seen.get("probe_only") is True, "sanity: this is the probe call"
