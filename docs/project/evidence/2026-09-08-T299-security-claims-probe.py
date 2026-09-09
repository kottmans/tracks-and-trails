"""Probe the claims `SECURITY.md` makes, and the one transcript `T299-R2` found rewritten.

**Security prose has no gate**, which is how `T299-R1` and `T299-R2` both survived a correction
round: the sentences were read, agreed with, and never executed. This script executes them. Every
assertion below is one clause of a document, expressed as something that either happens or does
not — a real `JobRepository` round trip, the real `RedactingFormatter`, and the real `git` command
the evidence file transcribes.

**`--root` exists so the corrections can be weakened without touching the working tree.** Point it
at a copy of the two documents with a claim reverted and the matching assertion fails, which is
`TESTING.md` §14's requirement that a correction's evidence be falsifiable rather than asserted.

Synthetic credentials only. Nothing here reads the user's settings, database or log.
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from tracks_and_trails.core import logging as app_logging  # noqa: E402
from tracks_and_trails.core.models import DownloadRequest, Job  # noqa: E402
from tracks_and_trails.persistence import db  # noqa: E402
from tracks_and_trails.persistence.repositories import JobRepository  # noqa: E402

#: A URL carrying a credential three ways: userinfo, a query token, and a fragment.
URL = "https://alice:hunter2@host.invalid/v?token=SECRETTOKEN#frag"
#: A diagnostic naming a cookie file whose name the shape rules cannot recognize.
DIAGNOSTIC = "ERROR: could not read /home/u/session.txt"
#: The evidence file whose captured transcript a documentation relocation rewrote.
TRANSCRIPT = "docs/project/evidence/2026-08-05-criterion-8-second-run.md"
#: The command that transcript records. Re-running it is the whole point of recording it.
TRANSCRIPT_COMMAND = ("git", "diff", "--stat", "6bae7ec..541b484")

failures: list[str] = []


def check(condition: object, claim: str) -> None:
    """Record one claim's verdict, and keep going — a batch is more useful than a first failure."""
    print(f"{'PASS' if condition else 'FAIL'}  {claim}")
    if not condition:
        failures.append(claim)


def formatted(text: str) -> str:
    """Push one line through the real sink, which is where redaction is enforced."""
    record = logging.LogRecord("t", logging.INFO, "f", 1, "%s", (text,), None)
    return app_logging.RedactingFormatter("%(message)s").format(record)


def check_the_database_table() -> None:
    """The `Database` column of `SECURITY.md`'s table, row by row."""
    try:
        DownloadRequest(
            url="https://h/v",
            output_directory="/o",
            format_selector="best",
            output_template="%(title)s.%(ext)s",
            cookies_from_browser="/home/u/.mozilla/cookies.sqlite",
        )
        check(False, "cookies_from_browser refuses a path, so one cannot enter a stored request")
    except ValueError:
        check(True, "cookies_from_browser refuses a path, so one cannot enter a stored request")

    try:
        DownloadRequest(
            url="https://h/v",
            output_directory="/o",
            format_selector="best",
            output_template="%(title)s.%(ext)s",
            proxy="http://me:hunter2@proxy.invalid:8080",
        )
        check(False, "the proxy field refuses userinfo")
    except ValueError:
        check(True, "the proxy field refuses userinfo")

    request = DownloadRequest(
        url=URL,
        output_directory="/home/u/out",
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )
    check(True, "a URL carrying userinfo is accepted — nothing refuses it, unlike the proxy")

    with (
        tempfile.TemporaryDirectory() as directory,
        db.open_database(pathlib.Path(directory) / "probe.sqlite3") as connection,
    ):
        job = Job(id="j1", url=URL, request=request, error_message=DIAGNOSTIC)
        JobRepository(connection).add(job)
        stored = connection.execute("SELECT url, request, error_message FROM jobs").fetchone()

    check(stored[0] == URL, "jobs.url holds the queued URL verbatim, credential included")
    check(URL in stored[1], "the serialized request holds the same URL a second time")
    check(stored[2] == DIAGNOSTIC, "error_message holds the diagnostic exactly as written")


def check_the_log_table() -> None:
    """The `Log` column, with the positive control that proves the probe sees a redaction."""
    app_logging.forget_the_secrets()
    try:
        line = formatted(f"fetching {URL}")
        check(
            "hunter2" not in line and "SECRETTOKEN" not in line and "frag" not in line,
            f"the log strips userinfo, query and fragment from a URL -> {line}",
        )
        # **The positive control runs before the negative one.** A probe that only ever
        # reports "not redacted" prints the same output when redaction is broken and when
        # the line was never redactable; this proves the instrument sees a real redaction.
        check(
            "<redacted>" in formatted("reading /home/u/cookies.txt"),
            "POSITIVE CONTROL: a shape-recognized cookie path is redacted with no registration",
        )
        check(
            "session.txt" in formatted(f"reading {DIAGNOSTIC}"),
            "an unregistered ordinary-named cookie path survives the shape rules",
        )
        app_logging.remember_a_path("/home/u/session.txt")
        check(
            "session.txt" not in formatted(f"reading {DIAGNOSTIC}"),
            "a configured cookie path is redacted by literal value, however ordinary its name",
        )
    finally:
        app_logging.forget_the_secrets()
    check(
        "/home/u/out/video.mp4" in formatted("wrote /home/u/out/video.mp4"),
        "an output path is not redacted, as the table says",
    )

    # `remember_a_path` hands a separator-free name to `remember_a_secret`, which is why
    # "no production caller registers anything" was false in two places at once.
    app_logging.forget_the_secrets()
    try:
        app_logging.remember_a_path("session.txt")
        check(
            "session.txt" not in formatted("reading session.txt"),
            "remember_a_path delegates a bare name to remember_a_secret, so production registers",
        )
    finally:
        app_logging.forget_the_secrets()


def check_the_documents(root: pathlib.Path) -> None:
    """The prose itself: a corrected sentence stays corrected, and a transcript stays literal."""
    security = (root / "SECURITY.md").read_text(encoding="utf-8")

    check(
        "It should not contain credentials" not in security,
        "SECURITY.md no longer tells a reader the database holds no credentials (T299-R1)",
    )
    check(
        "GitHub's private vulnerability reporting** on this repository" not in security,
        "SECURITY.md no longer offers a reporting route this private repository lacks (T299-R6)",
    )
    check(
        "registered by exact value with `remember_a_path`" in security,
        "SECURITY.md distinguishes a configured cookie path from one it never supplied (T299-R1)",
    )

    tasks = (root / "docs/project/TASKS.md").read_text(encoding="utf-8")
    check(
        "no production caller registers anything" not in tasks,
        "TASKS.md no longer claims production registers no literal (T299-R1)",
    )
    readme = (root / "README.md").read_text(encoding="utf-8")
    check(
        "the URL you queue is stored whole" in readme,
        "README states the queued-URL boundary, not only the diagnostic one (T299-R1)",
    )

    captured = subprocess.run(
        TRANSCRIPT_COMMAND, cwd=REPO, capture_output=True, text=True, check=True
    ).stdout
    transcript = (root / TRANSCRIPT).read_text(encoding="utf-8")
    check(
        all(line in transcript for line in captured.splitlines() if line.strip()),
        f"{TRANSCRIPT} transcribes what {' '.join(TRANSCRIPT_COMMAND)} prints today (T299-R2)",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=REPO,
        help="where to read SECURITY.md and the transcript from; a copy, to weaken a correction",
    )
    arguments = parser.parse_args()

    check_the_database_table()
    check_the_log_table()
    check_the_documents(arguments.root)

    print()
    if failures:
        print(f"{len(failures)} claim(s) failed:")
        for claim in failures:
            print(f"  - {claim}")
        return 1
    print("Every claim held.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
