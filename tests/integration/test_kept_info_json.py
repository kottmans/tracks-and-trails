"""A kept info JSON never carries the session's cookies or request headers (`T-249`).

`DAT-003`, amended 2026-10-11. Measured that day: through the options field, `--write-info-json`
with a cookies file kept a file whose every format held the cookie's value, and whose formats held
an `Authorization` header typed through `--add-headers`. Each case here runs the real worker
session and the real yt-dlp against a server on `127.0.0.1`, the exception `docs/project/TESTING.md`
grants the other localhost suites, and reads the file that is actually kept.

**Two lines, each tested alone** (`T249-R1`). `keep_secrets_out` makes yt-dlp write every info
JSON without them, so no file holds them at any moment; the worker strips each info JSON in
staging again, before claiming it and when an attempt fails. The routes: the download that
succeeds; the one that fails after the info JSON is written, whose staging is kept for its resume
(`T-113`); a subtitle conversion that fails before the download, which is how the review kept both
secrets in staging; and `--embed-info-json`, which puts the file inside the media.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from typing import Any, Final

import pytest

from tests.integration.test_end_to_end import build_media
from tracks_and_trails.core.models import DownloadRequest, SubtitleFormat
from tracks_and_trails.downloader import worker as worker_module
from tracks_and_trails.downloader import ytdlp_adapter
from tracks_and_trails.downloader.extra_options import options_for
from tracks_and_trails.downloader.protocol import Failed, SessionKind, Succeeded

BODY: Final = b"\0" * 4000
COOKIE: Final = "T249_COOKIE_VALUE"
HEADER: Final = "T249_HEADER_VALUE"

#: A page offering a clip and an English subtitle, as the review's reproduction served it. The
#: subtitle is TTML that is not XML at all, so converting it fails before the download starts.
SUBTITLED_PAGE: Final = (
    b'<html><head><title>clip</title></head><body><video><source src="/clip.mp4" '
    b'type="video/mp4"><track src="/en.ttml" kind="subtitles" srclang="en"></video></body></html>'
)

Handler = type[BaseHTTPRequestHandler]


def _clip(fail_after: int | None = None) -> Handler:
    """A direct link to a clip, failing every request after the first `fail_after`, if given."""
    served = {"count": 0}

    class Clip(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        # `http.server`'s own name, hence the camelCase.
        def do_GET(self) -> None:
            served["count"] += 1
            if fail_after is not None and served["count"] > fail_after:
                self.send_response(500)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(BODY)))
            self.end_headers()
            self.wfile.write(BODY)

        def log_message(self, *_: Any) -> None:
            """Silence the handler's stderr logging; a test is not a web server."""

    return Clip


def _site(routes: dict[str, tuple[bytes, str]]) -> Handler:
    """Each path in `routes` answered with its body and content type, and anything else a 404."""

    class Site(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:
            body, kind = routes.get(self.path, (b"", "text/plain"))
            self.send_response(200 if body else 404)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_: Any) -> None:
            """Silence the handler's stderr logging; a test is not a web server."""

    return Site


@pytest.fixture
def serve() -> Iterator[Callable[[Handler], str]]:
    """Start a server on `127.0.0.1` with the given handler, and return its address."""
    servers: list[ThreadingHTTPServer] = []

    def start(handler: Handler) -> str:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_address[1]}"

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def _session(url: str, tmp_path: Path, options: str = "", **fields: Any) -> tuple[list[Any], Path]:
    """One real download signed in with a cookies file and a typed header, plus `options`."""
    cookies = tmp_path / "cookies.txt"
    cookies.write_text(
        f"# Netscape HTTP Cookie File\n127.0.0.1\tFALSE\t/\tFALSE\t0\tsession\t{COOKIE}\n",
        encoding="utf-8",
    )
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    text = f'--add-headers "Authorization: Bearer {HEADER}" {options}'.strip()
    admission, argv = options_for(text)
    assert admission.usable, admission.refusals
    request = DownloadRequest(
        url=url,
        output_directory=str(downloads),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        extra_options=text,
        extra_option_argv=argv,
        **{"write_info_json": True, **fields},
    )
    queue: Queue[Any] = Queue()
    worker_module.run_session(SessionKind.DOWNLOAD, "job-1", request, queue, cookie_file=cookies)
    messages: list[Any] = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return messages, downloads


def _info_files(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.info.json"))


def _assert_staging_clean(downloads: Path) -> None:
    staged = _info_files(worker_module.staging_directory(downloads, "job-1"))
    assert staged, "the info JSON was not written before the attempt failed"
    for path in staged:
        text = path.read_text(encoding="utf-8")
        assert COOKIE not in text and HEADER not in text, f"a secret stayed in {path.name}"
        assert '"id"' in text, "the stripping threw away the file rather than its secrets"


def _without_the_funnel(monkeypatch: pytest.MonkeyPatch) -> None:
    """A yt-dlp whose writers no longer call `sanitize_info`: only the worker's line is left."""
    monkeypatch.setattr(ytdlp_adapter, "keep_secrets_out", lambda ydl: None)


def _without_the_worker_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only `keep_secrets_out` is left: the worker strips nothing, before claiming or on failing."""
    monkeypatch.setattr(worker_module, "strip_kept_info_json", lambda retained, adapter: None)
    monkeypatch.setattr(worker_module, "strip_staged_info_json", lambda staging, adapter: None)


def test_the_kept_info_json_carries_no_cookie_and_no_header(
    serve: Callable[[Handler], str], tmp_path: Path
) -> None:
    """The measurement of 2026-10-11, as a test: both were in the file kept beside the clip."""
    messages, downloads = _session(serve(_clip()) + "/clip.mp4", tmp_path)

    assert [m for m in messages if isinstance(m, Succeeded)], messages
    [kept] = _info_files(downloads)
    text = kept.read_text(encoding="utf-8")
    assert COOKIE not in text and HEADER not in text, "a secret reached the kept info JSON"
    assert '"id"' in text, "the stripping threw away the file rather than its secrets"


def test_a_download_that_fails_keeps_a_staging_info_json_already_stripped(
    serve: Callable[[Handler], str], tmp_path: Path
) -> None:
    """The info JSON is written before the download; a failed attempt keeps staging for its resume,
    and with it the file, which was never written with the secrets in it."""
    # A download session reads the item twice, to probe and to extract, before it fetches it.
    messages, downloads = _session(serve(_clip(fail_after=2)) + "/clip.mp4", tmp_path, retries=0)

    assert [m for m in messages if isinstance(m, Failed)], messages
    _assert_staging_clean(downloads)


@pytest.mark.parametrize(
    "only",
    [None, "keep_secrets_out", "the worker's line"],
    ids=["both lines", "keep_secrets_out alone", "the worker alone"],
)
def test_a_conversion_that_fails_before_the_download_keeps_no_secret_in_staging(
    ffmpeg: tuple[str, str],
    serve: Callable[[Handler], str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    only: str | None,
) -> None:
    """`T249-R1`, through `T-251`'s typed conversion: it runs before the download, and it failed
    ahead of a `before_dl` hook that would have stripped the file, so both secrets stayed in the
    staging kept for the resume. Neither line alone may let that happen again."""
    if only == "keep_secrets_out":
        _without_the_worker_line(monkeypatch)
    elif only == "the worker's line":
        _without_the_funnel(monkeypatch)
    base = serve(
        _site(
            {
                "/": (SUBTITLED_PAGE, "text/html"),
                "/clip.mp4": (BODY, "video/mp4"),
                "/en.ttml": (b"\0" * 64, "application/ttml+xml"),
            }
        )
    )

    messages, downloads = _session(
        base + "/",
        tmp_path,
        subtitle_languages=("en",),
        convert_subtitles=SubtitleFormat.SRT,
        retries=0,
    )

    [failed] = [m for m in messages if isinstance(m, Failed)]
    assert "not well-formed" in failed.message, "the conversion did not fail where it should"
    _assert_staging_clean(downloads)


def test_without_keep_secrets_out_the_file_is_still_stripped_before_it_is_kept(
    serve: Callable[[Handler], str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The worker's pass before claiming keeps the secrets out of the download folder alone."""
    _without_the_funnel(monkeypatch)

    messages, downloads = _session(serve(_clip()) + "/clip.mp4", tmp_path)

    assert [m for m in messages if isinstance(m, Succeeded)], messages
    [kept] = _info_files(downloads)
    text = kept.read_text(encoding="utf-8")
    assert COOKIE not in text and HEADER not in text


def test_an_info_json_embedded_in_the_file_carries_no_cookie_and_no_header(
    ffmpeg: tuple[str, str], serve: Callable[[Handler], str], tmp_path: Path
) -> None:
    """`--embed-info-json` attaches an info JSON inside an MKV, written by `FFmpegMetadataPP`
    rather than beside the file, so no strip of a kept sidecar can reach it. Found by `T249-R1`'s
    sibling audit: both secrets were in the kept file of a download that succeeded."""
    clip = build_media(ffmpeg[0], tmp_path / "source.mkv")
    base = serve(_site({"/clip.mkv": (clip, "video/x-matroska")}))

    messages, downloads = _session(
        base + "/clip.mkv", tmp_path, "--embed-info-json", write_info_json=False
    )

    [succeeded] = [m for m in messages if isinstance(m, Succeeded)]
    kept = Path(succeeded.output_path).read_bytes()
    assert b'"webpage_url"' in kept, "no info JSON was attached, so this proves nothing"
    assert COOKIE.encode() not in kept and HEADER.encode() not in kept, (
        "a secret reached the info JSON inside the kept file"
    )
    assert not _info_files(downloads), "an info JSON nobody asked to keep was kept beside it"
