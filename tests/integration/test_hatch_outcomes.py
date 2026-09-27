"""How a job ends when the escape hatch shapes it (`T-184`).

Every case runs the real worker session, the real yt-dlp and, where it converts, the real ffmpeg,
against a server on `127.0.0.1`: the exception `docs/project/TESTING.md` grants the other localhost
suites. What is asserted is the outcome the parent receives, because that is what a row shows.

- **A failed conversion is a failed job, whatever the hatch carries.** `--compat-options` brought
  yt-dlp's command-line default `ignoreerrors: "only_download"` with it. yt-dlp then reported the
  post-processing error and returned normally, and the worker, which reads success from the info
  dict, reported the unconverted file as the finished download. That is the false success the audit
  refuses `-i/--ignore-errors` for (`T183-R2`), reached through an option the audit admits.
- **`--break-on-existing` ends the job `CANCELLED`, carrying yt-dlp's own sentence.** The queue-row
  tests for `T184-R2` start from a stored message; this is where that message comes from, and the
  task's criterion asked for it to be measured rather than assumed.
"""

from __future__ import annotations

import shlex
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from types import ModuleType, SimpleNamespace
from typing import Any, Final, cast

import pytest

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.models import AudioCodec, DownloadRequest, MediaKind
from tracks_and_trails.downloader import worker as worker_module
from tracks_and_trails.downloader import ytdlp_adapter
from tracks_and_trails.downloader.extra_options import options_for, refusal_lines
from tracks_and_trails.downloader.protocol import Failed, SessionKind, Succeeded

#: Not media. yt-dlp downloads it happily and ffmpeg cannot read it, so the MP3 step is what fails.
NOT_MEDIA: Final = b"\x00" * 64_000

#: What yt-dlp's generic extractor records in a download archive for `/clip.mp4` on this server.
ARCHIVED_CLIP: Final = "generic clip\n"


def _handler(body: bytes, kind: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        # `http.server`'s own name, hence the camelCase.
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_: Any) -> None:
            """Silence the handler's stderr logging; a test is not a web server."""

    return Handler


@pytest.fixture
def serve() -> Iterator[Callable[[bytes, str, str], str]]:
    """Serve `body` as `kind` and answer with its URL, ending in `name`."""
    servers: list[ThreadingHTTPServer] = []

    def start(body: bytes, kind: str, name: str) -> str:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(body, kind))
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_address[1]}/{name}"

    yield start

    for server in servers:
        server.shutdown()
        server.server_close()


def _hatch(text: str) -> dict[str, Any]:
    """The request's two hatch fields, as the dialog's one call produces them."""
    admission, argv = options_for(text)
    assert admission.usable, refusal_lines(admission)
    return {"extra_options": text, "extra_option_argv": argv}


def _session(request: DownloadRequest) -> list[Any]:
    """Run one real download session and return everything it sent the parent."""
    queue: Queue[Any] = Queue()
    worker_module.run_session(SessionKind.DOWNLOAD, "job-1", request, queue)
    messages: list[Any] = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return messages


@pytest.mark.parametrize("text", ["", "--compat-options no-live-chat"], ids=["no hatch", "compat"])
def test_a_conversion_that_fails_fails_the_job_whatever_the_hatch_carries(
    ffmpeg: tuple[str, str],
    serve: Callable[[bytes, str, str], str],
    tmp_path: Path,
    text: str,
) -> None:
    """The `no hatch` case is the control: it fails the same way without any option at all."""
    request = DownloadRequest(
        url=serve(NOT_MEDIA, "audio/mp4", "clip.m4a"),
        output_directory=str(tmp_path),
        format_selector="bestaudio/best",
        output_template="%(title)s.%(ext)s",
        media_kind=MediaKind.AUDIO,
        audio_codec=AudioCodec.MP3,
        **_hatch(text),
    )

    messages = _session(request)

    succeeded = [m for m in messages if isinstance(m, Succeeded)]
    assert not succeeded, f"a job whose MP3 conversion failed reported success: {succeeded}"
    failed = next(m for m in messages if isinstance(m, Failed))
    assert failed.kind is ErrorKind.FFMPEG_ERROR, f"{failed.kind}: {failed.message}"


@pytest.mark.parametrize(
    "breaking", ["--break-on-existing", "--break-on-existing --break-per-input"]
)
def test_an_archived_item_under_break_on_existing_ends_cancelled_with_yt_dlp_s_reason(
    serve: Callable[[bytes, str, str], str], tmp_path: Path, breaking: str
) -> None:
    """`_match_entry` raises `ExistingVideoReached` on the current item, and the worker says why.

    `--break-per-input` only narrows where the break applies, and a job has one input, so it
    changes nothing here. Both were measured before either was kept hatch-reachable.
    """
    archive = tmp_path / "archive.txt"
    archive.write_text(ARCHIVED_CLIP, encoding="utf-8")
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    request = DownloadRequest(
        url=serve(b"\0" * 4000, "video/mp4", "clip.mp4"),
        output_directory=str(downloads),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        **_hatch(f"--download-archive {shlex.quote(str(archive))} {breaking}"),
    )

    messages = _session(request)

    failed = next(m for m in messages if isinstance(m, Failed))
    assert failed.kind is ErrorKind.CANCELLED, f"{failed.kind}: {failed.message}"
    assert "--break-on-existing" in failed.message, f"the reason was lost: {failed.message!r}"
    assert not list(downloads.iterdir()), "an item the archive already holds was fetched again"


@pytest.mark.parametrize(
    ("selection", "said"),
    [
        ("--download-archive {archive}", "has already been recorded in the archive"),
        ("--match-filters title=nomatch", "does not pass filter"),
        ("--max-filesize 1k", "larger than max-filesize"),
    ],
    ids=["archive", "filter", "size"],
)
def test_an_item_the_user_s_own_selection_skips_ends_cancelled_with_yt_dlp_s_reason(
    serve: Callable[[bytes, str, str], str], tmp_path: Path, selection: str, said: str
) -> None:
    """`UX-005`, amended 2026-09-27: yt-dlp skipped it because the user asked; not a failure.

    yt-dlp downloads nothing and returns normally. The worker then failed to move a file that does
    not exist and called that `DISK`, *"cannot move the finished download to '…/clip.NA'"*: a user
    who asked to skip what their archive holds was told the file could not be written.
    """
    archive = tmp_path / "archive.txt"
    archive.write_text(ARCHIVED_CLIP, encoding="utf-8")
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    request = DownloadRequest(
        url=serve(b"\0" * 4000, "video/mp4", "clip.mp4"),
        output_directory=str(downloads),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        **_hatch(selection.format(archive=shlex.quote(str(archive)))),
    )

    messages = _session(request)

    failed = next(m for m in messages if isinstance(m, Failed))
    assert failed.kind is ErrorKind.CANCELLED, f"{failed.kind}: {failed.message}"
    assert said in failed.message, f"yt-dlp's reason was not the one shown: {failed.message!r}"
    assert not list(downloads.iterdir()), "the skipped attempt left its staging directory behind"


# --- the seam that decides it, with yt-dlp stood in -----------------------------------------------


def _extract_writing_nothing(tmp_path: Path, said: str, **hatch: Any) -> dict[str, Any]:
    """Run the worker's `_extract` against a yt-dlp that prints `said` and writes nothing."""

    class WritesNothing:
        def __init__(self, options: dict[str, Any]) -> None:
            self._options = options

        def __enter__(self) -> WritesNothing:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def extract_info(self, url: str, download: bool) -> dict[str, Any]:
            self._options["logger"].debug(said)
            return {"id": "clip", "_filename": str(tmp_path / "clip.mp4")}

    # A name nothing can import, so `ffmpeg_progress` steps aside rather than patching it.
    module = ModuleType("t184_stand_in_ytdlp")
    module.YoutubeDL = WritesNothing  # type: ignore[attr-defined]
    reporter = SimpleNamespace(
        progress_hook=lambda _: None,
        postprocessor_hook=lambda _: None,
        ffmpeg_position=lambda _: None,
    )
    request = DownloadRequest(
        url="https://example.invalid/clip",
        output_directory=str(tmp_path),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        **hatch,
    )
    result: dict[str, Any] = worker_module._extract(
        ytdlp_adapter,
        request,
        cast(Any, SimpleNamespace(module=module)),
        cast(Any, reporter),
        probe_only=False,
        output_template=str(tmp_path / "clip.%(ext)s"),
    )
    return result


@pytest.mark.parametrize(
    ("said", "shown"),
    [
        ("[download] clip: A has already been recorded in the archive", "clip: A has already"),
        ("\r[download] File is larger than max-filesize (9 bytes > 1 bytes). Aborting.", "File is"),
    ],
)
def test_a_skip_is_named_in_yt_dlp_s_words_without_its_stage_tag(
    tmp_path: Path, said: str, shown: str
) -> None:
    """The tag names a stage, not a reason, and the size abort arrives with a carriage return."""
    with pytest.raises(worker_module.NothingDownloadedError) as skipped:
        _extract_writing_nothing(tmp_path, said, **_hatch("--continue"))

    assert skipped.value.reason.startswith(shown), skipped.value.reason


def test_a_job_without_the_hatch_that_writes_nothing_is_not_called_a_skip(tmp_path: Path) -> None:
    """No selection option can reach such a job, so nothing written is still a fault, loudly."""
    result = _extract_writing_nothing(tmp_path, "[download] something went quietly wrong")

    assert result["id"] == "clip", "the worker's own failure path no longer saw this result"
