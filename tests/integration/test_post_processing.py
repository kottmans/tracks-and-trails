"""`REQ-010`'s seven options, inspected as files (`T-109`).

## Why every assertion here is on the output rather than on the request

`T-077` is the reason this module exists in the shape it does. Phase 1 shipped five download
options and **four of them had never produced a file** — each was wired into the request, each was
asserted as a key in an options dictionary, and none of them did anything. `T012-R5` is the same
finding one layer down: `extractaudio` is an argument-parser flag, so `YoutubeDL({"extractaudio":
True})` builds an empty postprocessor list, accepts the key, and converts nothing.

So a test here is only worth writing if it fails when the option stops working. That means real
yt-dlp, real ffmpeg, a real file, and `ffprobe` on what came out.

## What is real, and what is not

Everything except the network. The media is built by ffmpeg at test time and served from
localhost — `docs/project/TESTING.md` §6's recorded exception, the same one `test_end_to_end.py`
runs under — so no fixture can go stale and nothing leaves the machine.

**Chapters are the one option asserted through the postprocessor rather than through a download,
and the limit is stated rather than hidden.** `FFmpegMetadata` writes `info['chapters']`, and no
extractor reachable without a network publishes any: yt-dlp's generic extractor reads a page and
an HLS playlist, and neither carries chapter marks. The test therefore hands yt-dlp's own
postprocessor the spec `build_postprocessors` produces, with chapters in the info dict, and probes
the file it writes. What that does not cover is an extractor supplying chapters in the first
place; what it does cover is that this application's request turns into a file with chapters in
it, which is the half `T-109` owns.
"""

import functools
import json
import subprocess
import threading
from collections.abc import Callable, Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from typing import Any, Final

import pytest

from tests.integration.test_end_to_end import build_hls, build_media, streams_in
from tracks_and_trails.core.models import AudioCodec, DownloadRequest, MediaKind
from tracks_and_trails.downloader import worker as worker_module
from tracks_and_trails.downloader.environment import FfmpegReport
from tracks_and_trails.downloader.protocol import Failed, SessionKind, Succeeded
from tracks_and_trails.downloader.ytdlp_adapter import build_postprocessors

#: What the source is, before anything is asked of it: h264 video and AAC audio in an MP4.
SOURCE_VIDEO_CODEC: Final = "h264"
SOURCE_AUDIO_CODEC: Final = "aac"

#: What the page calls itself, and what `embed_metadata` therefore has to write into the file.
#:
#: **Matched as a prefix**, because yt-dlp's generic extractor appends an index when a page offers
#: more than one media candidate — the title it reports is `A Test Clip (1)`. Asserting the exact
#: string would be asserting the extractor's disambiguation rule, which is not this task's to fix
#: in place; asserting the prefix is the claim that matters, that the *page's own* title reached
#: the file rather than a filename or nothing.
PAGE_TITLE: Final = "A Test Clip"

#: A page advertising the presentation, its title and its cover — what a real site looks like.
#:
#: **The URLs are absolute and therefore written once the port is known.** yt-dlp resolves a
#: relative `og:image` against nothing and reports `cover.jpg` as the thumbnail address, which
#: cannot be fetched — measured while building this fixture, not assumed.
WATCH_PAGE: Final = """<!doctype html>
<html><head>
<meta property="og:title" content="A Test Clip">
<meta property="og:image" content="{base}/cover.jpg">
</head><body>
<video controls><source src="{base}/master.m3u8" type="application/x-mpegURL"></video>
</body></html>
"""


@pytest.fixture
def presentation(ffmpeg: tuple[str, str], tmp_path: Path) -> Path:
    """The served directory: an HLS presentation with two subtitle languages and a cover.

    Built **outside** the output directory the downloads write into, so a test asserting what sits
    beside its download is not reading the fixture's own source file. That is not hypothetical —
    it is what the first run of this module reported.
    """
    root = tmp_path / "site"
    root.mkdir()
    build_media(ffmpeg[0], root / "source.mp4")
    build_hls(ffmpeg[0], root / "source.mp4", root)
    (root / "source.mp4").unlink()
    return root


@pytest.fixture
def output(tmp_path: Path) -> Path:
    """Where downloads land: its own directory, so its contents are only ever the download's."""
    directory = tmp_path / "downloads"
    directory.mkdir()
    return directory


@pytest.fixture
def serving(presentation: Path) -> Iterator[Callable[[str], str]]:
    """Serve the presentation on localhost and answer with the URL for one of its entry points."""
    servers: list[ThreadingHTTPServer] = []

    def serve(entry: str) -> str:
        handler = functools.partial(SimpleHTTPRequestHandler, directory=str(presentation))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        servers.append(server)
        base = f"http://127.0.0.1:{server.server_address[1]}"
        (presentation / "watch.html").write_text(WATCH_PAGE.format(base=base), encoding="utf-8")
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"{base}/{entry}"

    yield serve

    for server in servers:
        server.shutdown()
        server.server_close()


@pytest.fixture
def playlist_url(serving: Callable[[str], str]) -> Callable[[], str]:
    """The HLS master playlist — video, audio and two subtitle languages, and no thumbnail."""
    return lambda: serving("master.m3u8")


@pytest.fixture
def page_url(serving: Callable[[str], str]) -> Callable[[], str]:
    """The page that advertises the presentation, its title and its cover.

    `playlist_url` hands yt-dlp a playlist, which carries no thumbnail and no title worth
    embedding — so `REQ-010`'s *embed thumbnail* and *embed metadata* could be asserted as a
    request and never as a file. A page is what a real extractor is given, and yt-dlp's generic
    extractor reads `og:title` and `og:image` off it and finds the `<source>` beneath.
    """
    return lambda: serving("watch.html")


def request_for(url: str, directory: Path, **options: Any) -> DownloadRequest:
    """A download of `url` into `directory`, with `options` on top of a plain video request."""
    return DownloadRequest(
        url=url,
        output_directory=str(directory),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        media_kind=MediaKind.VIDEO,
        **options,
    )


def download(request: DownloadRequest) -> Path:
    """Run one real download session and return the file it produced.

    Through `run_session` rather than through the window: the criterion is about what reaches the
    disk, and the dialog's own wiring is asserted in `tests/ui/test_options_dialog.py`. Everything
    below this call is the real thing — the same worker the application spawns, the same adapter,
    the same yt-dlp and the same ffmpeg.
    """
    queue: Queue[Any] = Queue()
    worker_module.run_session(SessionKind.DOWNLOAD, "job-1", request, queue)
    messages: list[Any] = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    failure = next((m for m in messages if isinstance(m, Failed)), None)
    assert failure is None, f"the download failed: {failure.kind} — {failure.message}"
    succeeded = next(m for m in messages if isinstance(m, Succeeded))
    written = Path(succeeded.output_path)
    assert written.is_file(), f"the session reported {written} and no such file exists"
    return written


def tags_of(ffprobe_path: str, path: Path) -> dict[str, str]:
    """The container-level metadata tags `ffprobe` reads off `path`."""
    result = subprocess.run(
        [
            ffprobe_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-show_entries",
            "format_tags",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"ffprobe could not read {path}: {result.stderr}"
    report = json.loads(result.stdout)
    tags = report.get("format", {}).get("tags", {})
    return {str(name): str(value) for name, value in tags.items()}


def chapters_of(ffprobe_path: str, path: Path) -> list[dict[str, Any]]:
    """The chapter marks `ffprobe` reads off `path`."""
    result = subprocess.run(
        [
            ffprobe_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-show_chapters",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"ffprobe could not read {path}: {result.stderr}"
    return list(json.loads(result.stdout).get("chapters", []))


# --- containers: option 2 and option 3 -------------------------------------------------------


def test_a_remux_rewraps_the_streams_without_re_encoding_them(
    output: Path, ffmpeg: tuple[str, str], playlist_url: Callable[[], str]
) -> None:
    """`REQ-010`'s remux: a new container, the **same** streams.

    Both halves are asserted, because either alone passes for the wrong reason. The extension
    alone would pass if yt-dlp had recoded instead — which is a much slower and lossier thing than
    was asked for — and the codecs alone would pass if nothing had happened at all.
    """
    written = download(request_for(playlist_url(), output, remux_container="mkv"))

    assert written.suffix == ".mkv", f"the remux produced {written.name}"
    codecs = {
        stream["codec_type"]: stream["codec_name"] for stream in streams_in(ffmpeg[1], written)
    }
    assert codecs["video"] == SOURCE_VIDEO_CODEC, (
        f"the remuxed file carries {codecs['video']} video, not the source's "
        f"{SOURCE_VIDEO_CODEC}. A remux copies the streams; re-encoding them is a recode"
    )
    assert codecs["audio"] == SOURCE_AUDIO_CODEC, codecs


def test_a_recode_re_encodes_into_a_container_the_source_codec_cannot_enter(
    output: Path, ffmpeg: tuple[str, str], playlist_url: Callable[[], str]
) -> None:
    """`REQ-010`'s recode, told apart from a remux by the container's own rules.

    **WebM cannot hold h264**, so a `.webm` output whose video stream is not h264 is proof that
    the streams were re-encoded rather than copied — a claim that does not depend on which encoder
    this machine's ffmpeg happens to default to.
    """
    written = download(request_for(playlist_url(), output, recode_container="webm"))

    assert written.suffix == ".webm", f"the recode produced {written.name}"
    codecs = {
        stream["codec_type"]: stream["codec_name"] for stream in streams_in(ffmpeg[1], written)
    }
    assert codecs["video"] != SOURCE_VIDEO_CODEC, (
        "the file is .webm and still carries h264, which WebM cannot hold — the container was "
        "renamed rather than converted"
    )


def test_the_previewed_path_is_the_one_a_container_change_writes(
    output: Path, playlist_url: Callable[[], str]
) -> None:
    """`REQ-011`: the preview and the write are one function, through the new fields too.

    `postprocessed_name` predicted the audio extension and said in its own docstring that a remux
    was *"not derivable from the request alone"* — true of a list of postprocessor names, and no
    longer true now the container is a typed field. This asserts the two agree rather than
    trusting that they were changed together.
    """
    request = request_for(playlist_url(), output, remux_container="mkv")
    predicted = worker_module.postprocessed_name(output / "Clip.mp4", request)
    assert predicted.name == "Clip.mkv", predicted

    written = download(request)
    assert written.suffix == predicted.suffix, (
        f"the preview promised {predicted.suffix} and the download wrote {written.suffix}"
    )
    assert not worker_module.preview_is_provisional(request), (
        "a request that names its container knows what it will produce, so the preview must not "
        "be labelled as merely intended"
    )


# --- embedding: options 4, 5 and 6 -----------------------------------------------------------


def test_an_embedded_thumbnail_arrives_as_a_picture_inside_the_file(
    output: Path, ffmpeg: tuple[str, str], page_url: Callable[[], str]
) -> None:
    """`REQ-010`'s embed-thumbnail, as a stream in the output rather than as a flag.

    **The picture is inside the file and not beside it.** `EmbedThumbnail` needs the thumbnail
    downloaded first, which `build_options` arranges with `writethumbnail`; the same option would
    leave a `.jpg` in the output directory if `already_have_thumbnail` were set, and `REQ-010`
    asks to embed one rather than to keep one. Both are asserted, because the option working and
    the directory being clean are different claims.
    """
    written = download(request_for(page_url(), output, embed_thumbnail=True))

    kinds = [stream["codec_type"] for stream in streams_in(ffmpeg[1], written)]
    assert kinds.count("video") == 2, (
        f"the file carries {kinds}. An embedded cover is a second video stream — the source's "
        "picture and the attached one — and one video stream means nothing was embedded"
    )
    beside = sorted(path.name for path in output.iterdir() if path.is_file())
    assert beside == [written.name], f"embedding left {beside} in the output directory"


def test_embedded_metadata_reaches_the_file_and_is_absent_without_the_option(
    output: Path, ffmpeg: tuple[str, str], page_url: Callable[[], str]
) -> None:
    """`REQ-010`'s embed-metadata, with the negative that makes it a gate.

    The same page downloaded twice: once asking for metadata and once not. Asserting only the
    first would pass on a container that happens to carry a title anyway — MP4 writers put one
    there — so the difference between the two runs is the evidence, not the presence of a tag.
    """
    url = page_url()
    with_metadata = download(request_for(url, output / "with", embed_metadata=True))
    without = download(request_for(url, output / "without"))

    tags = tags_of(ffmpeg[1], with_metadata)
    assert tags.get("title", "").startswith(PAGE_TITLE), (
        f"the page's own title did not reach the file: {tags}"
    )
    assert "watch.html" in tags.get("comment", ""), (
        f"the source address did not reach the file: {tags}"
    )
    assert "title" not in tags_of(ffmpeg[1], without), (
        "the file carries a title without the option, so the assertion above proves nothing"
    )


def test_requested_chapters_are_written_into_the_file(
    output: Path, ffmpeg: tuple[str, str], playlist_url: Callable[[], str]
) -> None:
    """`REQ-010`'s embed-chapters, through the spec this application builds (`T-109`).

    **Not a full download, and the module docstring says why**: nothing reachable without a
    network publishes chapters, so a download-shaped test would assert that a file has no chapters
    and would pass with the option removed. What is real here is everything this task owns —
    `build_postprocessors` produces the spec, yt-dlp's own `FFmpegMetadata` consumes it, ffmpeg
    writes the file, and `ffprobe` reads the chapters back out.

    **Chapters alone must not bring metadata with them**, which is the assertion that makes the
    single-spec translation load-bearing rather than tidy. `FFmpegMetadata(add_metadata=True,
    add_chapters=True)` is the constructor's *default*, so a spec that names one flag and omits
    the other silently turns the other one on — and a user who asked to keep chapter marks would
    find their title, uploader and source URL written into the file as well. A translation
    emitting two specs, one per option, has exactly that shape.

    *(This test was written after a mutation survived. The docstring on `build_postprocessors`
    claimed two specs would be deduplicated to one and lose a flag; the deduplication is real and
    the consequence is the opposite — nothing is lost, something is added. The claim has been
    corrected there, and this is the test that would have caught it.)*
    """
    from yt_dlp import YoutubeDL
    from yt_dlp.postprocessor import get_postprocessor

    media = download(request_for(playlist_url(), output))
    chapters = [
        {"start_time": 0.0, "end_time": 1.0, "title": "Opening"},
        {"start_time": 1.0, "end_time": 2.0, "title": "Closing"},
    ]

    def run(request: DownloadRequest, target: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
        target.write_bytes(media.read_bytes())
        specs = [spec for spec in build_postprocessors(request) if spec["key"] == "FFmpegMetadata"]
        with YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            for spec in specs:
                arguments = {name: value for name, value in spec.items() if name != "key"}
                processor = get_postprocessor(str(spec["key"]))(ydl, **arguments)
                processor.run(
                    {
                        "filepath": str(target),
                        "ext": target.suffix.lstrip("."),
                        "chapters": chapters,
                        # A title the metadata option *would* write, so "chapters only" is a
                        # claim with something to be wrong about.
                        "title": PAGE_TITLE,
                    }
                )
        return chapters_of(ffmpeg[1], target), tags_of(ffmpeg[1], target)

    asked, tags = run(
        request_for("https://e.invalid/x", output, embed_chapters=True), output / "a.mp4"
    )
    assert [chapter["tags"]["title"] for chapter in asked] == ["Opening", "Closing"], asked
    assert "title" not in tags, (
        f"asking for chapters also embedded the metadata: {tags}. FFmpegMetadata defaults both "
        "flags to True, so every option this application does not ask for must be said `False` "
        "rather than left out"
    )

    not_asked, _ = run(request_for("https://e.invalid/x", output), output / "b.mp4")
    assert not_asked == [], (
        f"the file has chapters without the option ({not_asked}), so the assertion above is not "
        "evidence that the option did anything"
    )


# --- subtitles: option 7, in both of its directions -------------------------------------------


def test_chosen_subtitle_languages_are_embedded_and_an_absent_one_is_not_invented(
    output: Path, ffmpeg: tuple[str, str], playlist_url: Callable[[], str]
) -> None:
    """`REQ-010`'s language *selection*, asserted as a selection rather than as a fetch.

    The presentation publishes `en` and `de`; the request asks for `de` and `fr`. **One** subtitle
    stream, in German, is the only answer that distinguishes a real selection from all three ways
    of getting this wrong: two streams means the languages were ignored and everything published
    was taken, zero means the language list never reached yt-dlp, and a `fr` stream would mean
    something was invented for a language nobody publishes.

    **Asking for both published languages would prove none of that**, and the first version of
    this test did exactly that. Replacing `subtitleslangs` with a hardcoded `["all"]` left it
    passing — the mutation that made this test worth rewriting.
    """
    written = download(
        request_for(
            playlist_url(),
            output,
            subtitle_languages=("de", "fr"),
            embed_subtitles=True,
        )
    )

    subtitles = [
        stream
        for stream in streams_in(ffmpeg[1], written, language=True)
        if stream["codec_type"] == "subtitle"
    ]
    languages = [stream.get("_language", "") for stream in subtitles]
    # `deu` and `ger` are the same language in two ISO 639-2 registers — the terminological and
    # the bibliographic — and which one appears is the muxer's choice rather than this
    # application's. Both are accepted; what is asserted is that it is German and that there is
    # one of it.
    assert len(subtitles) == 1 and languages[0] in {"deu", "ger"}, (
        f"the file carries {len(subtitles)} subtitle streams {languages}. One German track is "
        "what was asked for: English is published and was not requested, French was requested "
        "and is not published"
    )
    beside = sorted(path.name for path in output.iterdir() if path.is_file())
    assert beside == [written.name], (
        f"embedding left the subtitle files behind as well: {beside}. REQ-010 offers embed *or* "
        "write, and an embed that also writes is both"
    )


def test_written_subtitles_survive_the_staging_directory(
    output: Path, playlist_url: Callable[[], str]
) -> None:
    """**`T046-R3`'s finding, met** (`REQ-010`, `T-109`).

    `_discard_staging` removes the download's private directory wholesale except the single path
    the media file was claimed from. That is correct for every intermediate — and wrong for a
    subtitle the user asked to *keep*, which until now was fetched, written, and deleted with the
    directory. Nothing exposed the combination before `T-109`, which is why it was latent.

    **The same strict subset as the embedding test**, for the same reason: `de` and `fr` against a
    source publishing `en` and `de`, so exactly one file may appear and it has to be the German
    one. Its content is read back, because a test that found *some* file beside the media would
    pass on an empty placeholder.
    """
    written = download(
        request_for(
            playlist_url(),
            output,
            subtitle_languages=("de", "fr"),
            embed_subtitles=False,
        )
    )

    beside = sorted(path.name for path in output.iterdir() if path.is_file())
    subtitles = [name for name in beside if name != written.name]
    assert len(subtitles) == 1, (
        f"the output directory holds {beside}. One requested language is published, so one "
        "subtitle file is the whole of the correct answer"
    )
    kept = output / subtitles[0]
    assert kept.name.startswith(written.stem), (
        f"{kept.name} does not follow the name the media landed under, so it belongs to a file "
        "that is not there"
    )
    assert ".de." in kept.name, kept.name
    assert "hallo untertitel" in kept.read_text(encoding="utf-8"), kept.read_text()


def test_a_staging_directory_is_still_removed_after_its_subtitles_are_kept(
    output: Path, playlist_url: Callable[[], str]
) -> None:
    """Keeping the sidecars must not keep the directory they came out of.

    The claim moves files out of a temporary directory and the cleanup then removes it; a
    correction that kept the files by not cleaning up would pass the test above and leave a
    `.tracks-and-trails-staging-…` directory beside every download.
    """
    download(request_for(playlist_url(), output, subtitle_languages=("en",), embed_subtitles=False))

    leftovers = [path.name for path in output.iterdir() if path.is_dir()]
    assert leftovers == [], f"the staging directory outlived the download: {leftovers}"


# --- options that combine, and the refusal that precedes all of them --------------------------


def test_options_that_combine_produce_one_file_carrying_every_one_of_them(
    output: Path, ffmpeg: tuple[str, str], page_url: Callable[[], str]
) -> None:
    """`T-109`'s combination criterion: an audio extraction **and** an embedded thumbnail and
    metadata is one file that has to have all three.

    Singly each option can pass while the postprocessor chain is ordered wrongly. This is the case
    that catches it: `EmbedThumbnail` and `FFmpegMetadata` run after `FFmpegExtractAudio` in
    yt-dlp's own ordering, so a chain that embedded first would put the picture into the container
    that is then thrown away.
    """
    written = download(
        DownloadRequest(
            url=page_url(),
            output_directory=str(output),
            format_selector="best",
            output_template="%(title)s.%(ext)s",
            media_kind=MediaKind.AUDIO,
            audio_codec=AudioCodec.MP3,
            audio_quality="192",
            embed_thumbnail=True,
            embed_metadata=True,
        )
    )

    assert written.suffix == ".mp3", f"the extraction produced {written.name}"
    streams = streams_in(ffmpeg[1], written)
    kinds = [stream["codec_type"] for stream in streams]
    assert "audio" in kinds and "video" in kinds, (
        f"the MP3 carries {kinds}; the embedded cover is the video stream and it is missing, so "
        "the picture went into the container the extraction discarded"
    )
    audio = next(stream for stream in streams if stream["codec_type"] == "audio")
    assert audio["codec_name"] == "mp3", audio
    assert tags_of(ffmpeg[1], written).get("title", "").startswith(PAGE_TITLE), tags_of(
        ffmpeg[1], written
    )


@pytest.mark.parametrize(
    "options",
    [
        pytest.param({"remux_container": "mkv"}, id="remux"),
        pytest.param({"recode_container": "webm"}, id="recode"),
        pytest.param({"embed_thumbnail": True}, id="thumbnail"),
        pytest.param({"embed_metadata": True}, id="metadata"),
        pytest.param({"embed_chapters": True}, id="chapters"),
        pytest.param(
            {"subtitle_languages": ("en",), "embed_subtitles": True}, id="embed-subtitles"
        ),
    ],
)
def test_every_option_that_needs_ffmpeg_is_refused_before_the_download_starts(
    output: Path, monkeypatch: pytest.MonkeyPatch, options: dict[str, Any]
) -> None:
    """`REQ-024`: the user is told **before** the bytes are spent, for every one of these.

    Parametrized over each option rather than asserted once, because the gate reads the
    postprocessor list and a translation that forgot to add one would leave that option sailing
    through to fail after the download completed — which is precisely what `T012-R5` found the
    old two-flag gate doing.

    No network is involved: the refusal happens after the probe and before the download, so a
    stub probe is enough and a real one would only make the test slower.
    """
    monkeypatch.setattr(
        worker_module,
        "find_ffmpeg",
        lambda **_: FfmpegReport(path=None, source="absent for this test"),
    )
    monkeypatch.setattr(
        worker_module,
        "_extract",
        lambda *_a, **_k: {"title": "Clip", "webpage_url": "https://e.invalid/x", "ext": "mp4"},
    )
    queue: Queue[Any] = Queue()

    worker_module.run_session(
        SessionKind.DOWNLOAD,
        "job-1",
        request_for("https://e.invalid/x", output, **options),
        queue,
    )

    messages: list[Any] = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    failure = next((m for m in messages if isinstance(m, Failed)), None)
    assert failure is not None, f"{options} was allowed to start with no ffmpeg"
    assert failure.kind.name == "FFMPEG_MISSING", failure.kind
    assert not any(isinstance(m, Succeeded) for m in messages)
