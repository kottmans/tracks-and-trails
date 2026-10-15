"""Automatic captions reach the disk only where they were asked for (`T-251`).

**Real yt-dlp, a real file, and a source built by hand.** No extractor reachable without a network
publishes an `automatic_captions` map: the generic extractor reads a page and an HLS playlist, and
neither has one. So the source is an info dict of the shape the probe measured on 2026-10-14 —
the same language in both maps, a caption-only language, and one the source does not have —
whose formats and subtitles are files served from localhost, and yt-dlp's own `process_ie_result`
downloads it under the options `build_options` produced. What this does not cover is an extractor
supplying captions in the first place; what it covers is that this application's request makes
yt-dlp write the right files, which is the half `T-251` owns.
"""

import functools
import threading
from collections.abc import Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Final

import pytest
from yt_dlp import YoutubeDL

from tests.integration.test_end_to_end import build_media
from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.downloader.worker import requested_sidecars
from tracks_and_trails.downloader.ytdlp_adapter import build_options

#: What each served subtitle says, so a file can be traced to the map it came from.
WRITTEN_BY_A_PERSON: Final = "written by a person"
MADE_BY_THE_SITE: Final = "made by the site"


def _vtt(words: str) -> str:
    return f"WEBVTT\n\n00:00:00.000 --> 00:00:02.000\n{words}\n"


@pytest.fixture
def source(ffmpeg: tuple[str, str], tmp_path: Path) -> Iterator[dict[str, Any]]:
    """An info dict for a served clip: German subtitles, captions in German and French."""
    root = tmp_path / "site"
    root.mkdir()
    build_media(ffmpeg[0], root / "clip.mp4")
    (root / "de.vtt").write_text(_vtt(WRITTEN_BY_A_PERSON), encoding="utf-8")
    for language in ("de", "fr"):
        (root / f"{language}-auto.vtt").write_text(_vtt(MADE_BY_THE_SITE), encoding="utf-8")

    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    yield {
        "id": "clip",
        "title": "Clip",
        "extractor": "generic",
        "extractor_key": "Generic",
        "webpage_url": f"{base}/clip.html",
        "formats": [{"format_id": "0", "url": f"{base}/clip.mp4", "ext": "mp4"}],
        "subtitles": {"de": [{"ext": "vtt", "url": f"{base}/de.vtt"}]},
        "automatic_captions": {
            language: [{"ext": "vtt", "url": f"{base}/{language}-auto.vtt"}]
            for language in ("de", "fr")
        },
    }

    server.shutdown()
    server.server_close()


def download(source: dict[str, Any], directory: Path, **fields: Any) -> dict[str, Any]:
    """Download `source` into `directory` under the options a request with `fields` builds."""
    request = DownloadRequest(
        url=source["webpage_url"],
        output_directory=str(directory),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        **fields,
    )
    options = build_options(request, str(directory / "%(title)s.%(ext)s"))
    with YoutubeDL({**options, "quiet": True, "noprogress": True}) as ydl:
        result: dict[str, Any] = ydl.process_ie_result(dict(source), download=True)
    return result


def written(directory: Path) -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in directory.iterdir()
        if path.suffix == ".vtt"
    }


def test_a_caption_is_taken_only_where_the_language_has_no_subtitles(
    source: dict[str, Any], tmp_path: Path
) -> None:
    """German has both, so the person's subtitles; French has only a caption, so the caption.
    yt-dlp's own precedence, which the editor's single list relies on."""
    result = download(source, tmp_path, subtitle_languages=("de", "fr"), automatic_captions=True)

    assert written(tmp_path) == {
        "Clip.de.vtt": _vtt(WRITTEN_BY_A_PERSON),
        "Clip.fr.vtt": _vtt(MADE_BY_THE_SITE),
    }
    required = {s.path.name for s in requested_sidecars(result) if s.required and s.exists}
    assert required == {"Clip.de.vtt", "Clip.fr.vtt"}, (
        "the worker claims subtitles from yt-dlp's record of them, and a caption is not in it"
    )


def test_without_automatic_captions_a_caption_only_language_is_not_written(
    source: dict[str, Any], tmp_path: Path
) -> None:
    """The control is what fetches it: off, French is simply not there, as before `T-251`."""
    download(source, tmp_path, subtitle_languages=("de", "fr"))

    assert written(tmp_path) == {"Clip.de.vtt": _vtt(WRITTEN_BY_A_PERSON)}


def test_automatic_captions_alone_write_nothing(source: dict[str, Any], tmp_path: Path) -> None:
    """**yt-dlp with no language named takes English, or the first it finds**, so the flag alone
    would fetch a caption nobody chose. `build_options` passes it only with languages."""
    download(source, tmp_path, automatic_captions=True)

    assert written(tmp_path) == {}
