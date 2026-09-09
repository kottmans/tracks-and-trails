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
#: A credential in the URL *path*, which is not one of the forms redaction recognizes (`T299-R1`).
PATH_CREDENTIAL_URL = (
    "https://example.invalid/download/SYNTHETIC_PATH_TOKEN?t=SYNTHETIC_QUERY_TOKEN"
)
#: Arbitrary third-party text in a diagnostic. `error_message` has no filter at all (`T299-R1`).
COOKIE_DIAGNOSTIC = "upstream response Cookie: session=SYNTHETIC_COOKIE_VALUE"
BEARER_DIAGNOSTIC = "Authorization: Bearer SYNTHETIC_BEARER_TOKEN"
#: The soak report whose unfenced claim about two past trees the relocation rewrote (`T299-R2`).
SOAK = "docs/project/evidence/2026-08-29-orphan-scan-known-positive-soak.md"
#: The two commits that report describes. Neither contains the relocated spelling.
SOAK_COMMITS = ("0332a68", "75cd183")
#: The evidence file whose captured transcript a documentation relocation rewrote.
TRANSCRIPT = "docs/project/evidence/2026-08-05-criterion-8-second-run.md"
#: The command that transcript records. Re-running it is the whole point of recording it.
TRANSCRIPT_COMMAND = ("git", "diff", "--stat", "6bae7ec..541b484")

failures: list[str] = []


#: Every claim attempted, so the total is counted here rather than by a reader (`T299-R7`).
attempted: list[str] = []


def check(condition: object, claim: str) -> None:
    """Record one claim's verdict, and keep going — a batch is more useful than a first failure."""
    attempted.append(claim)
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

    # `T299-R1`: the sink has no filter, so a cookie *value* is stored as readily as a path.
    with (
        tempfile.TemporaryDirectory() as directory,
        db.open_database(pathlib.Path(directory) / "probe2.sqlite3") as connection,
    ):
        JobRepository(connection).add(
            Job(id="j2", url=URL, request=request, error_message=COOKIE_DIAGNOSTIC)
        )
        kept = connection.execute("SELECT error_message FROM jobs").fetchone()[0]
    check(kept == COOKIE_DIAGNOSTIC, "a cookie VALUE inside a diagnostic is stored verbatim too")


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

    # `T299-R1`: three claims about what redaction does *not* reach. The positive controls
    # above have already shown the instrument reporting a real redaction.
    app_logging.forget_the_secrets()
    line = formatted(f"Extracting URL: {PATH_CREDENTIAL_URL}")
    check(
        "SYNTHETIC_QUERY_TOKEN" not in line,
        "POSITIVE CONTROL: the query token is removed from that same URL",
    )
    check(
        "SYNTHETIC_PATH_TOKEN" in line,
        "a credential in a URL PATH survives the log — redaction recognizes forms, not secrets",
    )
    check(
        "<redacted>" in formatted(COOKIE_DIAGNOSTIC),
        "POSITIVE CONTROL: a Cookie header value IS recognized in the log",
    )
    check(
        "SYNTHETIC_BEARER_TOKEN" in formatted(BEARER_DIAGNOSTIC),
        "an Authorization: Bearer line in a diagnostic survives the log unrecognized",
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
        "what survives is paths" not in security,
        "SECURITY.md no longer concludes that only paths survive into the log (T299-R1)",
    )
    check(
        "Neither artifact stores cookie" not in security,
        "SECURITY.md no longer guarantees that neither artifact holds cookie contents (T299-R1)",
    )
    check(
        "the only people positioned to find a vulnerability" not in security,
        "SECURITY.md no longer claims only collaborators can find a vulnerability (T299-R8)",
    )
    check(
        "depend on the repository's visibility, not on a release" in security,
        "SECURITY.md ties the reporting route to visibility, not a release (T299-R8)",
    )
    check(
        "Registered by literal value and replaced" in security,
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

    soak = (root / SOAK).read_text(encoding="utf-8")
    check(
        "by a workflow comment and a line in `ai/STATUS.md`" in soak,
        f"{SOAK} names the path its two commits actually contain (T299-R2)",
    )
    for revision in SOAK_COMMITS:
        present = subprocess.run(
            ("git", "cat-file", "-e", f"{revision}:ai/STATUS.md"), cwd=REPO, capture_output=True
        )
        absent = subprocess.run(
            ("git", "cat-file", "-e", f"{revision}:docs/project/STATUS.md"),
            cwd=REPO,
            capture_output=True,
        )
        check(
            present.returncode == 0 and absent.returncode != 0,
            f"{revision} contains ai/STATUS.md and not docs/project/STATUS.md",
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

    # **The script counts, not the person writing it up** (`T299-R7`). The correction record
    # said "16 of 16" twice for a probe that ran 18 checks, because the total was counted by
    # hand from an enumeration rather than read off the run.
    print()
    print(f"{len(attempted) - len(failures)} of {len(attempted)} claims held.")
    if failures:
        print(f"{len(failures)} failed:")
        for claim in failures:
            print(f"  - {claim}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
