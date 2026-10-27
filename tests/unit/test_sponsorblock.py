"""SponsorBlock, opt-in per preset (`T-254`).

Ruled 2026-10-19 (`ARC-010` amended, third; `UX-015` amended, second): each category is left, marked
as a chapter or cut out, held as two tuples sharing nothing; while anything is marked, *Chapters*
is on and one metadata step writes both; the lookup carries none of the download's headers, going
through a session holding only the network settings, by a subclass overriding one private yt-dlp
method; and nothing is sent while it is off (`NFR-007`, as amended). The file the chain writes is
`tests/integration/test_sponsorblock.py`.
"""

from __future__ import annotations

import contextlib
import functools
import inspect
import json
import textwrap
import threading
from collections.abc import Iterator
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar, Final

import pytest
import yt_dlp
from yt_dlp import YoutubeDL, parse_options
from yt_dlp.postprocessor.common import PostProcessor
from yt_dlp.postprocessor.sponsorblock import SponsorBlockPP

from tracks_and_trails.core import presets
from tracks_and_trails.core import settings as app_settings
from tracks_and_trails.core.models import (
    SPONSORBLOCK_CATEGORIES,
    SPONSORBLOCK_UNCUTTABLE,
    DownloadRequest,
    MediaKind,
    Preset,
)
from tracks_and_trails.downloader import ytdlp_adapter as adapter
from tracks_and_trails.downloader.extra_options import HAS_A_CONTROL, admit
from tracks_and_trails.persistence import repositories
from tracks_and_trails.ui.format_text import SPONSORBLOCK_WORDS

STAGING: Final = "/home/someone/Videos/.staging/Clip.mp4"
#: A YouTube item as the after-filter step sees it, which is where yt-dlp runs the lookup.
ITEM: Final = {"extractor_key": "Youtube", "id": "abcdefghijk", "duration": 6.0}
#: A header typed with `--add-headers`, the credential the mapping caught on loopback.
TYPED_HEADER: Final = ("Authorization", "Bearer typed-token")


def a_request(**fields: Any) -> DownloadRequest:
    return DownloadRequest(
        url="https://www.youtube.com/watch?v=abcdefghijk",
        output_directory="/home/someone/Videos",
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        **fields,
    )


def a_preset(**fields: Any) -> Preset:
    return Preset(name="P", media_kind=MediaKind.VIDEO, format_selector="best", **fields)


# --- the categories --------------------------------------------------------------------------


def test_the_categories_are_yt_dlp_s_own_in_its_order() -> None:
    """**Validated against yt-dlp's own lists** (`T-254`'s criterion), at the pin: `core/` holds a
    transcription, since it may not import yt-dlp."""
    assert tuple(SponsorBlockPP.CATEGORIES) == SPONSORBLOCK_CATEGORIES
    assert tuple(SponsorBlockPP.NON_SKIPPABLE_CATEGORIES) == SPONSORBLOCK_UNCUTTABLE


def test_every_category_has_words() -> None:
    assert tuple(SPONSORBLOCK_WORDS) == SPONSORBLOCK_CATEGORIES
    for words in SPONSORBLOCK_WORDS.values():
        assert "\u2014" not in words and "\u2013" not in words


# --- the value -------------------------------------------------------------------------------


@pytest.mark.parametrize("owner", [a_request, a_preset])
@pytest.mark.parametrize(
    "fields",
    [
        {"sponsorblock_remove": ("nonsense",)},
        {"sponsorblock_remove": ("sponsor", "sponsor")},
        {"sponsorblock_remove": ("chapter",)},
        {"sponsorblock_remove": ("poi_highlight",)},
        {"sponsorblock_remove": "sponsor"},
        {"sponsorblock_mark": ("sponsor",), "embed_chapters": False},
        {
            "sponsorblock_mark": ("sponsor",),
            "sponsorblock_remove": ("sponsor",),
            "embed_chapters": True,
        },
        {"sponsorblock_mark": ("all",), "embed_chapters": True},
    ],
)
def test_what_yt_dlp_would_refuse_or_silently_resolve_is_refused(
    owner: Any, fields: dict[str, Any]
) -> None:
    """A category marked and cut, which yt-dlp resolves by cutting, is one or the other here;
    a mark without chapters would be fetched and never written."""
    with pytest.raises((TypeError, ValueError)):
        owner(**fields)


def test_each_category_is_left_marked_or_cut() -> None:
    marked = (*SPONSORBLOCK_UNCUTTABLE, "intro")
    cut = tuple(c for c in SPONSORBLOCK_CATEGORIES if c not in marked)

    request = a_request(sponsorblock_mark=marked, sponsorblock_remove=cut, embed_chapters=True)

    assert set(request.sponsorblock_mark) | set(request.sponsorblock_remove) == set(
        SPONSORBLOCK_CATEGORIES
    )


def test_the_preset_s_choices_reach_the_request_and_name_it() -> None:
    preset = replace(
        presets.BEST_VIDEO,
        name="Skipping",
        embed_chapters=True,
        sponsorblock_mark=("intro",),
        sponsorblock_remove=("sponsor", "selfpromo"),
    )

    request = presets.to_request(preset, url="https://example.invalid/x", output_directory="/d")

    assert request.sponsorblock_mark == ("intro",)
    assert request.sponsorblock_remove == ("sponsor", "selfpromo")
    assert presets.needs_ffmpeg(preset)
    assert adapter.requires_ffmpeg(request)


def test_a_cut_alone_needs_ffmpeg_and_leaving_everything_does_not() -> None:
    """A cut rewrites the file, which is ffmpeg's; the preset beneath needs none of its own."""
    assert not presets.needs_ffmpeg(presets.BEST_VIDEO)

    assert presets.needs_ffmpeg(replace(presets.BEST_VIDEO, sponsorblock_remove=("sponsor",)))


def test_a_preset_is_saved_and_read_back(tmp_path: Path) -> None:
    preset = replace(
        presets.BEST_VIDEO,
        name="Skipping",
        built_in=False,
        embed_chapters=True,
        sponsorblock_mark=("poi_highlight", "chapter"),
        sponsorblock_remove=("sponsor",),
    )
    target = tmp_path / "settings.toml"

    assert (
        app_settings.save(app_settings.add_preset(app_settings.Settings(), preset), target) is None
    )
    read = app_settings.load(target)

    assert read.settings.presets == (preset,)
    assert read.problem is None


def test_a_queued_request_is_stored_and_read_back() -> None:
    request = a_request(
        embed_chapters=True, sponsorblock_mark=("intro",), sponsorblock_remove=("sponsor",)
    )

    stored = repositories._serialize_request(request)

    assert repositories._deserialize_request(stored) == request


@pytest.mark.parametrize(
    "spelling",
    ["--sponsorblock-mark sponsor", "--sponsorblock-remove sponsor", "--no-sponsorblock"],
)
def test_the_options_field_refuses_each_spelling_for_its_control(spelling: str) -> None:
    refusals = admit(spelling).refusals

    assert [(refusal.option, refusal.reason) for refusal in refusals] == [
        (spelling.split()[0], HAS_A_CONTROL)
    ]


# --- the chain -------------------------------------------------------------------------------


def _keys(options: dict[str, Any]) -> list[str]:
    return [str(spec["key"]) for spec in options.get("postprocessors", [])]


def test_one_metadata_step_writes_the_marks_beside_the_metadata() -> None:
    """**Ruling 2**: one `FFmpegMetadata`, after the chapter step, carrying both."""
    options = adapter.build_options(
        a_request(sponsorblock_mark=("intro",), embed_chapters=True, embed_metadata=True), STAGING
    )

    metadata = [spec for spec in options["postprocessors"] if spec["key"] == "FFmpegMetadata"]
    assert len(metadata) == 1
    assert metadata[0]["add_chapters"] is True and metadata[0]["add_metadata"] is True
    keys = _keys(options)
    assert keys.index("ModifyChapters") < keys.index("FFmpegMetadata")


def test_the_chapter_step_cuts_what_yt_dlp_s_own_options_cut() -> None:
    parsed = parse_options(
        ["--sponsorblock-mark", "intro", "--sponsorblock-remove", "sponsor,selfpromo"]
    ).ydl_opts
    theirs = next(s for s in parsed["postprocessors"] if s["key"] == "ModifyChapters")
    options = adapter.build_options(
        a_request(
            sponsorblock_mark=("intro",),
            sponsorblock_remove=("sponsor", "selfpromo"),
            embed_chapters=True,
        ),
        STAGING,
    )

    ours = next(s for s in options["postprocessors"] if s["key"] == "ModifyChapters")
    assert set(ours["remove_sponsor_segments"]) == set(theirs["remove_sponsor_segments"])
    assert bool(ours["force_keyframes"]) == bool(theirs["force_keyframes"])


def test_the_options_field_s_keyframes_reach_the_chapter_step() -> None:
    argv = admit("--force-keyframes-at-cuts").accepted
    options = adapter.build_options(
        a_request(
            sponsorblock_remove=("sponsor",),
            extra_options="--force-keyframes-at-cuts",
            extra_option_argv=argv,
        ),
        STAGING,
    )

    chapter = next(s for s in options["postprocessors"] if s["key"] == "ModifyChapters")
    assert chapter["force_keyframes"] is True


def test_nothing_of_sponsorblock_is_on_the_probe_or_in_any_options() -> None:
    """**The lookup is never an option**: `look_up_sponsorblock` adds it to the download's session,
    so the probe, which looked up three times per video through the options field, cannot."""
    request = a_request(sponsorblock_remove=("sponsor",))

    probed = adapter.build_options(request, request.output_template, probe_only=True)
    downloaded = adapter.build_options(request, STAGING)

    assert "SponsorBlock" not in _keys(probed) and "ModifyChapters" not in _keys(probed)
    assert "SponsorBlock" not in _keys(downloaded)


# --- the lookup ------------------------------------------------------------------------------


class _Api(BaseHTTPRequestHandler):
    """SponsorBlock's server on loopback: one sponsor segment, and every request's headers kept."""

    seen: ClassVar[list[dict[str, str]]]

    # `http.server`'s own name, hence the camelCase.
    def do_GET(self) -> None:
        type(self).seen.append({key.lower(): value for key, value in self.headers.items()})
        body = json.dumps(
            [
                {
                    "videoID": ITEM["id"],
                    "segments": [
                        {
                            "segment": [1.0, 2.0],
                            "category": "sponsor",
                            "actionType": "skip",
                            "videoDuration": 6.0,
                            "description": "",
                        }
                    ],
                }
            ]
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: Any) -> None:
        """Silence the handler's stderr logging; a test is not a web server."""


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Iterator[type[_Api]]:
    """The fixed endpoint pointed at loopback for one test, and the headers it was sent."""
    handler = type("Api", (_Api,), {"seen": []})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(adapter, "SPONSORBLOCK_API", f"http://127.0.0.1:{server.server_address[1]}")
    yield handler
    server.shutdown()
    thread.join(timeout=5)


def _with_a_typed_header(**fields: Any) -> DownloadRequest:
    text = f'--add-headers "{TYPED_HEADER[0]}:{TYPED_HEADER[1]}"'
    admission = admit(text)
    assert admission.usable, admission.refusals
    return a_request(extra_options=text, extra_option_argv=admission.accepted, **fields)


def test_the_lookup_carries_none_of_the_download_s_headers(api: type[_Api]) -> None:
    """**Ruling 3, the second mapped defect closed**: the header typed for the site stays with
    the site. The lookup still finds the segment."""
    request = _with_a_typed_header(sponsorblock_remove=("sponsor",))
    info = dict(ITEM)

    with YoutubeDL(adapter.build_options(request, STAGING)) as ydl:
        assert ydl.params["http_headers"].get(TYPED_HEADER[0]) == TYPED_HEADER[1]
        adapter.look_up_sponsorblock(ydl, yt_dlp, request)
        info = ydl.run_all_pps("after_filter", info)

    assert len(api.seen) == 1, api.seen
    assert TYPED_HEADER[0].lower() not in api.seen[0], api.seen[0]
    assert [chapter["category"] for chapter in info["sponsorblock_chapters"]] == ["sponsor"]


def test_yt_dlp_s_own_lookup_carries_the_typed_header(api: type[_Api]) -> None:
    """**The instrument, shown a positive**: the stock step, through the download's session."""
    request = _with_a_typed_header(sponsorblock_remove=("sponsor",))

    with YoutubeDL(adapter.build_options(request, STAGING)) as ydl:
        SponsorBlockPP(ydl, categories=["sponsor"], api=adapter.SPONSORBLOCK_API).run(dict(ITEM))

    assert api.seen and api.seen[0].get(TYPED_HEADER[0].lower()) == TYPED_HEADER[1]


def test_the_lookup_asks_only_for_the_categories_chosen_in_yt_dlp_s_order() -> None:
    added: list[tuple[Any, str]] = []

    class _Session:
        params: ClassVar[dict[str, Any]] = {}

        def add_post_processor(self, processor: Any, when: str) -> None:
            added.append((processor, when))

    request = a_request(
        sponsorblock_mark=("chapter", "intro"),
        sponsorblock_remove=("sponsor",),
        embed_chapters=True,
    )
    adapter.look_up_sponsorblock(_Session(), yt_dlp, request)

    ((processor, when),) = added
    assert when == "after_filter"
    assert isinstance(processor, SponsorBlockPP)
    assert processor._categories == ("sponsor", "intro", "chapter")
    assert processor._API_URL == adapter.SPONSORBLOCK_API == "https://sponsor.ajay.app"


def test_the_lookup_keeps_only_the_network_settings() -> None:
    params = {
        "proxy": "http://127.0.0.1:3128",
        "source_address": "0.0.0.0",  # noqa: S104 - `-4`, which binds to no one address
        "socket_timeout": 7.5,
        "http_headers": {"Authorization": "Bearer x"},
        "cookiefile": "/home/someone/cookies.txt",
        "cookiesfrombrowser": ("firefox",),
        "client_certificate": "/home/someone/me.pem",
    }

    assert adapter.lookup_params(params) == {
        "proxy": "http://127.0.0.1:3128",
        "source_address": "0.0.0.0",  # noqa: S104 - as above
        "socket_timeout": 7.5,
    }


class _RefusedError(Exception):
    """A request the test refuses, where it would have left the process."""


@pytest.mark.parametrize(("mark", "cut"), [((), ()), (("intro",), ()), ((), ("sponsor",))])
def test_no_sponsorblock_request_leaves_while_it_is_off(
    monkeypatch: pytest.MonkeyPatch, mark: tuple[str, ...], cut: tuple[str, ...]
) -> None:
    """**`T-254`'s criterion**, through yt-dlp's own after-filter step with every request refused
    and counted. Off, nothing is asked; on, one request is, which is the instrument's positive."""
    asked: list[str] = []

    def refused(_self: Any, request: Any) -> Any:
        asked.append(str(getattr(request, "url", request)))
        raise _RefusedError(asked[-1])

    monkeypatch.setattr(YoutubeDL, "urlopen", refused)
    request = a_request(sponsorblock_mark=mark, sponsorblock_remove=cut, embed_chapters=bool(mark))

    with YoutubeDL(adapter.build_options(request, STAGING)) as ydl:
        adapter.look_up_sponsorblock(ydl, yt_dlp, request)
        with contextlib.suppress(_RefusedError):
            ydl.run_all_pps("after_filter", dict(ITEM))

    if mark or cut:
        assert len(asked) == 1 and "/api/skipSegments/" in asked[0], asked
    else:
        assert asked == []


#: `PostProcessor._download_json` at the pin, which the lookup's subclass replaces with a copy
#: sending through its own session. **A release that changes it fails here**, so the copy is
#: looked at again rather than drifting from what it replaced.
REPLACED: Final = """\
def _download_json(self, url, *, expected_http_errors=(404,)):
    self.write_debug(f'{self.PP_NAME} query: {url}')
    for retry in RetryManager(self.get_param('extractor_retries', 3), self._retry_download):
        try:
            rsp = self._downloader.urlopen(Request(url))
        except network_exceptions as e:
            if isinstance(e, HTTPError) and e.status in expected_http_errors:
                return None
            retry.error = PostProcessingError(f'Unable to communicate with {self.PP_NAME} API: {e}')
            continue
    return json.loads(rsp.read().decode(rsp.headers.get_param('charset') or 'utf-8'))
"""


def test_the_method_the_lookup_replaces_is_the_one_it_copied() -> None:
    assert textwrap.dedent(inspect.getsource(PostProcessor._download_json)) == REPLACED
    assert "_download_json" in vars(adapter._lookup_class(yt_dlp))


def test_the_lookup_class_is_made_once_per_yt_dlp() -> None:
    assert adapter._lookup_class(yt_dlp) is adapter._lookup_class(yt_dlp)
    assert isinstance(adapter._lookup_class, functools._lru_cache_wrapper)
