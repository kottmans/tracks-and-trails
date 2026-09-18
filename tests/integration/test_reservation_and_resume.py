"""What the resume options do to `T-046`'s reservation, measured (`T-184`, audit Finding 7).

The download session reserves the output path with `O_CREAT | O_EXCL` before yt-dlp runs, so a
**zero-byte file sits exactly where the download is about to land**. `build_options` passes
`overwrites=True` for that reason, and its own comment says why: *"yt-dlp treats a file at the
target as an already-completed download and writes nothing; the zero-byte reservation is that
file."*

The escape hatch (`T-184`) lets a user name options that change how yt-dlp treats a file already at
the target, and its acceptance criteria say to **measure** the five the audit's Finding 7 names
rather than reason about them. This is that measurement, and it carries two halves:

- **Finding 7's five are harmless.** `--continue`, `--no-continue`, `--part`, `--no-part` and
  `--post-overwrites` each leave a complete download, because `overwrites=True` decides the
  question before they get to it. So they can stay hatch-reachable.
- **Two other options are not, and this is why the audit refuses them.** `-w/--no-overwrites` and
  `--no-force-overwrites` clear `overwrites`, and then the download reports success and leaves the
  **zero-byte reservation in place** — an empty file, no error, nothing for the user to see until
  they open it. The audit classifies all three `overwrites` spellings `app:sets` with the reason
  *"T-046's reservation owns it"*; this is that reason as a measurement rather than a claim.

**`http.server` on `127.0.0.1`** is the same exception `docs/project/TESTING.md` grants
`test_end_to_end.py`: a real download over a real socket, no network.
"""

from __future__ import annotations

import contextlib
import io
import os
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Final

import pytest
from yt_dlp import YoutubeDL

from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.downloader.ytdlp_adapter import build_options

#: Small enough to be quick, large enough that "nothing was written" is unmistakable.
BODY: bytes = b"\x00" * 64_000


def _handler() -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        # `http.server`'s own name, hence the camelCase.
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(BODY)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(BODY)

        def log_message(self, *_: Any) -> None:
            """Silence the handler's stderr logging; a test is not a web server."""

    return Handler


@pytest.fixture
def media_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/clip.mp4"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _download_onto_a_reservation(
    url: str, directory: Path, extra: dict[str, Any]
) -> tuple[str, int | None]:
    """Reserve the target the way the session does, then download with `extra` merged in.

    Returns the outcome and the size the target ends at, which is the whole question: a complete
    file, or the reservation still sitting there at zero bytes.
    """
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "clip.mp4"
    # `T-046`'s primitive, spelled out rather than imported: the private helper is the worker's,
    # and what this test needs is the *state* it leaves behind.
    os.close(os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644))
    assert target.stat().st_size == 0

    request = DownloadRequest(
        url=url,
        output_directory=str(directory),
        format_selector="best",
        output_template="clip.%(ext)s",
    )
    options = build_options(request, request.output_template, overwrites=True)
    options |= {"quiet": True, "no_warnings": True, "noprogress": True, "retries": 0}
    options["outtmpl"] = str(directory / "clip.%(ext)s")
    options |= extra

    outcome = "downloaded"
    try:
        # yt-dlp writes progress to the real streams even when quiet; this keeps a test's output
        # to what the test says.
        with (
            contextlib.redirect_stderr(io.StringIO()),
            contextlib.redirect_stdout(io.StringIO()),
            YoutubeDL(options) as ydl,
        ):
            ydl.extract_info(url, download=True)
    except BaseException as error:  # every failure shape is the measurement here
        outcome = type(error).__name__

    return outcome, target.stat().st_size if target.exists() else None


#: Finding 7's five, by the option-dictionary key each one sets.
HARMLESS: Final = {
    "--continue": {"continuedl": True},
    "--no-continue": {"continuedl": False},
    "--part": {"nopart": False},
    "--no-part": {"nopart": True},
    "--post-overwrites": {"post_overwrites": True},
}


def test_the_reservation_is_overwritten_when_the_application_asks(
    media_url: str, tmp_path: Path
) -> None:
    """The baseline this rests on: `overwrites=True` turns the reservation into a real download."""
    outcome, size = _download_onto_a_reservation(media_url, tmp_path / "base", {})

    assert outcome == "downloaded"
    assert size == len(BODY), "the application's own options left the reservation in place"


@pytest.mark.parametrize(("option", "extra"), HARMLESS.items(), ids=list(HARMLESS))
def test_finding_sevens_five_leave_a_complete_download(
    media_url: str, tmp_path: Path, option: str, extra: dict[str, Any]
) -> None:
    """Finding 7, answered: each of the five is harmless against the reservation.

    They change how yt-dlp treats a file already at the target, and `overwrites=True` decides that
    question before they reach it. Measured rather than reasoned about, which is what `T-184`'s
    criterion asks for, and the answer is what lets them stay hatch-reachable.
    """
    outcome, size = _download_onto_a_reservation(media_url, tmp_path / "case", extra)

    assert outcome == "downloaded", f"{option} turned the download into {outcome}"
    assert size == len(BODY), f"{option} left {size} bytes where a complete file should be"


#: The three `overwrites` spellings the audit classifies `app:sets`, with the two that clear it.
UNDOES_THE_PROTECTION: Final = {
    "-w/--no-overwrites": {"overwrites": False},
    "--no-force-overwrites": {"overwrites": None},
}


@pytest.mark.parametrize(
    ("option", "extra"), UNDOES_THE_PROTECTION.items(), ids=list(UNDOES_THE_PROTECTION)
)
def test_clearing_overwrites_leaves_an_empty_file_and_calls_it_a_download(
    media_url: str, tmp_path: Path, option: str, extra: dict[str, Any]
) -> None:
    """Why `overwrites` is refused, as a measurement instead of a sentence.

    The audit classifies every `overwrites` spelling `app:sets`, reason: *"T-046's reservation owns
    it"*. This is what happens when that is not enforced — **the download reports success and the
    file is empty**, which the user finds out by opening it.

    It is written as a characterisation test on purpose. If a later yt-dlp stops behaving this way,
    this fails, and the refusal's stated reason gets looked at again rather than inherited.
    """
    outcome, size = _download_onto_a_reservation(media_url, tmp_path / "unsafe", extra)

    assert outcome == "downloaded", f"{option} failed loudly, which would be the better outcome"
    assert size == 0, (
        f"{option} left {size} bytes. If this is no longer empty, yt-dlp's treatment of a file at "
        "the target has changed and the audit's app:sets reason for `overwrites` needs re-reading"
    )
