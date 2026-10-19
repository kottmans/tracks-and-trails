"""The options field's shaping and compatibility values, held where they act (`T-363`).

Two findings of 2026-10-14, ruled the next day. **A file name's shaping acted on the download's
whole path**: `--trim-filenames` and `--windows-filenames` reach the download pass, which is handed
the contained absolute path as a literal, and yt-dlp reshaped its folders. And **`--compat-options`
was admitted as a whole** though one of its values switches yt-dlp's unsafe-extension check off for
the entire process, one rewrites a file's name the application owns, and two reach keys that
controls are planned for.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any, Final

import pytest
from yt_dlp import YoutubeDL, parse_options
from yt_dlp.utils import FormatSorter
from yt_dlp.utils._utils import _UnsafeExtensionError

from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.downloader import worker, ytdlp_adapter
from tracks_and_trails.downloader.extra_options import (
    COMPAT_REFUSALS,
    admit,
    ffmpeg_refusals,
    options_for,
    resolved_compat_values,
)
from tracks_and_trails.downloader.option_table import COMPAT_ALIASES, COMPAT_VALUES, OPTION_KEYS
from tracks_and_trails.downloader.worker import as_literal_template
from tracks_and_trails.downloader.ytdlp_adapter import (
    RENDER_ONLY_KEYS,
    build_options,
    hatch_options,
    hatch_requires_ffmpeg,
    options_needing_ffmpeg,
    process_state_kept,
)

TOOL: Final = Path(__file__).resolve().parents[2] / "tools" / "ytdlp_option_table.py"

#: A download folder like a user's, and the staging folder the worker makes inside it.
CHOSEN: Final = Path("/home/someone/Videos")
STAGING: Final = CHOSEN / ".tracks-and-trails-staging-0123456789abcdef0123456789abcdef0123"
TITLE: Final = "Vol. 2 of the set"


def a_request(text: str, directory: Path = CHOSEN) -> DownloadRequest:
    admission, argv = options_for(text)
    assert admission.usable, admission.refusals
    return DownloadRequest(
        url="https://example.invalid/clip",
        output_directory=str(directory),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        extra_options=text,
        extra_option_argv=argv,
    )


@pytest.fixture
def unchanged_process() -> Iterator[None]:
    """Fail a test that leaves yt-dlp's process-wide state changed, and put it back either way."""
    kept = (FormatSorter.default, _UnsafeExtensionError._enabled)
    yield
    changed = (FormatSorter.default, _UnsafeExtensionError._enabled) != kept
    FormatSorter.default, _UnsafeExtensionError._enabled = kept
    assert not changed, "yt-dlp's process-wide state was left changed"


# --- shaping acts on the name, not on the path it became ---------------------------------------


@pytest.mark.parametrize(
    "text", ["--trim-filenames 15", "--trim-file-names 30", "--windows-filenames"]
)
def test_shaping_reaches_the_render_and_never_the_download(text: str) -> None:
    request = a_request(text)

    rendered = build_options(request, request.output_template, probe_only=True)
    downloaded = build_options(request, as_literal_template(STAGING / f"{TITLE}.mp4"))

    assert RENDER_ONLY_KEYS & set(rendered), "the name is no longer shaped where it is rendered"
    assert not RENDER_ONLY_KEYS & set(downloaded)


@pytest.mark.parametrize(
    ("text", "chosen"),
    [
        # Measured at `8b0aad6`: `/home/someone/Vide. 2 of the set.mp4`, beside the folder.
        pytest.param("--trim-filenames 15", CHOSEN, id="trim above the folder"),
        # Measured: inside the folder but outside staging, past `T-046`'s reservation.
        pytest.param("--trim-filenames 50", CHOSEN, id="trim into the staging name"),
        # Measured: the folder renamed `Talks# 2026`, which does not exist.
        pytest.param("--windows-filenames", Path("/home/someone/Talks: 2026"), id="windows names"),
    ],
)
def test_yt_dlp_writes_the_download_where_it_was_contained(text: str, chosen: Path) -> None:
    """**The breach, through yt-dlp's own naming.** The worker hands the download pass the
    contained path as a literal; whatever yt-dlp makes of it is where the bytes go."""
    staging = chosen / STAGING.name
    contained = staging / f"{TITLE}.mp4"
    request = a_request(text, chosen)

    with YoutubeDL(
        {**build_options(request, as_literal_template(contained)), "quiet": True}
    ) as ydl:
        written = ydl.prepare_filename({"id": "clip", "title": TITLE, "ext": "mp4"})

    assert Path(written) == contained


# --- compatibility values, decided one by one -------------------------------------------------


def _parsed_values(texts: list[str]) -> set[str]:
    argv = [word for text in texts for word in ("--compat-options", text)]
    with process_state_kept():
        chosen = parse_options(argv).ydl_opts["compat_opts"]
    # `set_compat_opts` marks a value its other options made unnecessary with a `*`.
    return {value.removeprefix("*") for value in chosen}


@pytest.mark.parametrize(
    "texts",
    [
        ["no-live-chat"],
        ["all"],
        ["youtube-dl"],
        ["youtube-dlc"],
        ["2021"],
        ["2024"],
        ["all,-allow-unsafe-ext"],
        ["-all,format-sort"],
        ["youtube-dl,-filename,multistreams"],
        ["all", "-allow-unsafe-ext,-allow-unsafe-exec-expansion"],
        ["2023", "-2024"],
        [" Format-Sort , NO-LIVE-CHAT "],
    ],
)
def test_the_values_are_resolved_as_yt_dlp_resolves_them(texts: list[str]) -> None:
    """The transcription of yt-dlp's set arithmetic, held to its parser: aliases, `all`, `-`
    removals, case and spaces, and a second option adding to the first."""
    assert set(resolved_compat_values(texts)) == _parsed_values(texts)


def test_a_value_yt_dlp_does_not_know_is_left_to_its_parser() -> None:
    with pytest.raises(ValueError, match="nosuch"):
        resolved_compat_values(["no-live-chat,nosuch"])
    assert not options_for("--compat-options nosuch")[0].usable


@pytest.mark.parametrize(
    ("text", "verdict", "value"),
    [
        ("--compat-options allow-unsafe-ext", "safety", "allow-unsafe-ext"),
        ("--compat-options allow-unsafe-exec-expansion", "safety", "allow-unsafe-exec-expansion"),
        ("--compat-options all", "safety", "allow-unsafe-exec-expansion"),
        ("--compat-options filename", "app", "filename"),
        ("--compat-options youtube-dl", "app", "filename"),
        ("--compat-options no-live-chat --compat-options allow-unsafe-ext", "safety", None),
    ],
)
def test_a_value_that_would_do_harm_or_nothing_is_refused_with_its_reason(
    text: str, verdict: str, value: str | None
) -> None:
    refusals = admit(text).refusals

    assert len(refusals) == 1, refusals
    assert refusals[0].option == "--compat-options"
    if value is not None:
        assert refusals[0].reason == COMPAT_REFUSALS[verdict].format(value=value)
    else:
        assert refusals[0].reason.endswith(COMPAT_REFUSALS[verdict].split("{value}")[1])


@pytest.mark.parametrize(
    "text",
    [
        "--compat-options no-live-chat",
        "--compat-options 2021",
        "--compat-options all,-allow-unsafe-ext,-allow-unsafe-exec-expansion,-filename,"
        "-format-sort",
        "--compat-options all --compat-options -allow-unsafe-ext,-allow-unsafe-exec-expansion,"
        "-filename,-format-sort",
    ],
)
def test_harmless_values_stay_usable(text: str) -> None:
    assert admit(text).usable


def test_every_value_yt_dlp_names_unsafe_is_refused() -> None:
    """The rule by yt-dlp's own naming, so a new `allow-unsafe-*` cannot arrive admitted."""
    unsafe = {value for value in COMPAT_VALUES if value.startswith("allow-unsafe-")}
    assert unsafe and all(COMPAT_VALUES[value] == "safety" for value in unsafe)


def test_an_admitted_value_s_keys_are_carried_rather_than_dropped() -> None:
    """**`multistreams` was admitted and then dropped**: the merge carried only the keys two other
    values differ in. It now carries what each admitted value changes (`REQ-031`)."""
    _, argv = options_for("--compat-options multistreams")

    carried = hatch_options("--compat-options multistreams", argv)

    assert carried["allow_multiple_video_streams"] is True
    assert carried["allow_multiple_audio_streams"] is True
    assert {"allow_multiple_audio_streams", "allow_multiple_video_streams"} <= set(
        OPTION_KEYS["--compat-options"]
    )


# --- the GUI's process is left as it was ------------------------------------------------------


@pytest.mark.usefixtures("unchanged_process")
@pytest.mark.parametrize("text", ["--compat-options prefer-vp9-sort", "--compat-options 2023"])
def test_the_editor_s_check_leaves_the_process_as_it_was(text: str) -> None:
    """`prefer-vp9-sort` is admitted, and parsing it rewrites the default format order for every
    later `YoutubeDL`. The editor's check and the offer's ffmpeg question both parse in the GUI."""
    admission, argv = options_for(text)
    assert admission.usable
    hatch_requires_ffmpeg(text, argv)


@pytest.mark.usefixtures("unchanged_process")
def test_the_unsafe_value_never_reaches_a_parse_in_the_gui() -> None:
    """Refused on its tokens, so the extension check is still on when the editor has answered."""
    admission, _ = options_for("--compat-options all")

    assert not admission.usable
    assert _UnsafeExtensionError._enabled


#: Lines that admit and need ffmpeg for `--split-chapters`, and whose options parsed one at a time
#: change the process: the review's three, through the missing-ffmpeg attribution (`T363-R1`).
WITHOUT_FFMPEG: Final = (
    "--compat-options prefer-vp9-sort --split-chapters",
    "--compat-options allow-unsafe-ext --compat-options -allow-unsafe-ext --split-chapters",
    "--compat-options all --compat-options -allow-unsafe-ext,-allow-unsafe-exec-expansion,"
    "-filename,-format-sort --split-chapters",
)


@pytest.mark.usefixtures("unchanged_process")
@pytest.mark.parametrize("text", WITHOUT_FFMPEG)
def test_naming_what_needs_ffmpeg_leaves_the_process_as_it_was(text: str) -> None:
    """`T363-R1`: the attribution parsed each option alone outside the guard, so an admitted line
    naming `allow-unsafe-ext` and taking it away again switched the GUI's extension check off."""
    admission, argv = options_for(text)
    assert admission.usable, admission.refusals

    refusals = ffmpeg_refusals(text, argv)

    assert [refusal.option for refusal in refusals] == ["--split-chapters"]
    with pytest.raises(_UnsafeExtensionError):
        _UnsafeExtensionError.sanitize_extension("exe")


@pytest.mark.usefixtures("unchanged_process")
def test_an_attribution_that_raises_still_leaves_the_process_as_it_was(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exception path: whatever stops the attribution after a parse, the state is put back."""

    def fails(_specs: object) -> bool:
        raise RuntimeError("after the parse")

    monkeypatch.setattr(ytdlp_adapter, "_performed_by_ffmpeg", fails)
    _, argv = options_for(WITHOUT_FFMPEG[1])

    with pytest.raises(RuntimeError):
        options_needing_ffmpeg(argv)


#: Every function in the two modules allowed to import yt-dlp that hands its parser anything, and
#: why each is safe in the GUI's process. A new one fails here until it is added with its reason.
PARSES: Final = {
    # Reached only through `unparseable`, which guards it.
    "_unparseable": "parse_options",
    # Reached only through `options_needing_ffmpeg`, which guards it (`T363-R1`).
    "_options_needing_ffmpeg": "parse_options",
    # The job's own process, where the effect is the option working; the GUI asks through
    # `hatch_requires_ffmpeg`, which guards it.
    "hatch_options": "parse_options",
    # Parses nothing the user typed.
    "_command_line_defaults": "parse_options",
    # The option parser alone; the process-wide writes happen in `parse_options`.
    "_unreadable_when_it_runs": "parseOpts",
}


def test_every_parse_of_the_user_s_options_is_one_this_file_knows() -> None:
    """`T363-R1` was a third parse no state test reached, so the parses are listed, not sampled."""
    found: dict[str, str] = {}
    for module in (ytdlp_adapter, worker):
        for node in ast.walk(ast.parse(inspect.getsource(module))):
            if not isinstance(node, ast.FunctionDef):
                continue
            for call in ast.walk(node):
                name = getattr(getattr(call, "func", None), "id", None)
                if isinstance(call, ast.Call) and name in {"parse_options", "parseOpts"}:
                    found[node.name] = name

    assert found == PARSES


# --- a value that does nothing here (`T363-R2`) -------------------------------------------------

INERT: Final = sorted(value for value, verdict in COMPAT_VALUES.items() if verdict == "inert")


@pytest.mark.parametrize("value", INERT)
def test_a_value_that_does_nothing_here_is_refused_where_it_is_named(value: str) -> None:
    """`list-formats` was admitted and only chose console table formatting, which this application
    never prints; `REQ-031` refuses an option that would be accepted and dropped."""
    [refusal] = admit(f"--compat-options {value}").refusals

    assert refusal.option == "--compat-options"
    assert refusal.reason == COMPAT_REFUSALS["inert"].format(value=value)


def test_the_values_that_do_nothing_here_are_the_ones_the_audit_names() -> None:
    assert "list-formats" in INERT and "no-live-chat" not in INERT
    assert len(INERT) == 12, "the audit's table changed; check the reasons still hold"


def test_a_bundle_that_brings_nothing_that_acts_is_refused_by_its_own_name() -> None:
    """`2025` expands to nothing at 2026.08.19, and was admitted with an empty hatch."""
    assert COMPAT_ALIASES["2025"] == ()
    [refusal] = admit("--compat-options 2025").refusals

    assert refusal.reason == COMPAT_REFUSALS["inert"].format(value="2025")


@pytest.mark.parametrize(
    "text",
    [
        # Bundles that bring something that acts, beside a passenger that does not.
        "--compat-options 2021",
        "--compat-options 2022",
        "--compat-options 2024",
        # A value named and taken away again: the user's own cancellation.
        "--compat-options list-formats,-list-formats",
        "--compat-options list-formats --compat-options -list-formats",
    ],
)
def test_passengers_and_cancellations_stay_usable(text: str) -> None:
    assert admit(text).usable, admit(text).refusals


@pytest.mark.parametrize(
    "value",
    [
        "embed-metadata",
        "filename-sanitization",
        "manifest-filesize-approx",
        "no-direct-merge",
        "no-live-chat",
        "no-youtube-channel-redirect",
        "no-youtube-unavailable-videos",
        "playlist-match-filter",
    ],
)
def test_a_value_that_acts_only_when_a_job_runs_stays_usable(value: str) -> None:
    """Meaningful values are not refused merely because their parse changes no key."""
    admission, argv = options_for(f"--compat-options {value}")

    assert admission.usable
    assert hatch_options(f"--compat-options {value}", argv) == {"compat_opts": {value}}


def test_the_generator_stops_on_an_admitted_value_the_audit_does_not_classify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """So a value a new yt-dlp brings is classified rather than admitted by default."""
    tool = _tool()
    rulings = tool.compat_rulings()
    assert set(rulings) == {v for v, verdict in COMPAT_VALUES.items() if verdict in (None, "inert")}
    del rulings["no-live-chat"]
    monkeypatch.setattr(tool, "compat_rulings", lambda: rulings)

    with pytest.raises(SystemExit, match="no-live-chat"):
        tool.compat_values()


def test_the_generator_stops_on_an_effect_nothing_could_produce(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A value yt-dlp never reads, whose parse changes no key, cannot be called `effect`."""
    tool = _tool()
    rulings = {**tool.compat_rulings(), "seperate-video-versions": "effect"}
    monkeypatch.setattr(tool, "compat_rulings", lambda: rulings)

    with pytest.raises(SystemExit, match="seperate-video-versions"):
        tool.compat_values()


# --- the evidence each `inert` row stands on ---------------------------------------------------


def test_three_values_are_read_nowhere_in_yt_dlp() -> None:
    tool = _tool()

    unread = {value for value in COMPAT_VALUES if not tool.read_by_yt_dlp(value)}

    assert unread == {
        "no-external-downloader-progress",
        "no-youtube-prefer-utc-upload-date",
        "seperate-video-versions",
    }
    assert all(COMPAT_VALUES[value] == "inert" for value in unread)


def test_the_packages_three_values_need_are_not_installed_with_this_application() -> None:
    """`no-certifi`, `embed-thumbnail-atomicparsley` and `prefer-legacy-http-handler` choose
    between certifi, mutagen or another request handler and what is used without them."""
    from yt_dlp.networking.common import _REQUEST_HANDLERS

    for package in ("certifi", "mutagen", "requests", "curl_cffi"):
        assert importlib.util.find_spec(package) is None, f"{package} is installed; recheck"
    assert list(_REQUEST_HANDLERS) == ["Urllib"]


@pytest.mark.parametrize(
    "option",
    [
        "--embed-subs",  # `no-keep-subs` acts only on its processor
        "--embed-metadata",  # `no-attach-info-json` acts only on its processor
        "--embed-chapters",
        "--playlist-random",  # `playlist-index` acts only after a reordering
        "--lazy-playlist",
        "--ignore-errors",  # `abort-on-error` acts only beside these
        "--abort-on-error",
        "--no-abort-on-error",
        "--list-formats",  # `list-formats` acts only on its table
    ],
)
def test_the_options_an_inert_value_would_act_beside_are_refused(option: str) -> None:
    assert not admit(option).usable


@pytest.mark.parametrize("probe_only", [True, False])
def test_every_pass_names_a_format_and_leaves_errors_to_the_library(probe_only: bool) -> None:
    """`format-spec` changes only the format chosen when none is given; `abort-on-error` sets
    `ignoreerrors` false, which yt-dlp reads as it reads the key absent."""
    request = a_request("--fragment-retries 3")
    options = build_options(request, "%(title)s.%(ext)s", probe_only=probe_only)

    assert options["format"] == "best"
    assert "ignoreerrors" not in options


def test_filename_sanitization_changes_the_name_this_application_renders() -> None:
    """Reachability: the hatch's `compat_opts` reach the pass that renders the name."""
    information = {"id": "a/b..", "title": "x", "ext": "mp4"}
    names = []
    for text in ("--fragment-retries 3", "--compat-options filename-sanitization"):
        options = build_options(a_request(text), "%(id)s.%(ext)s", probe_only=True)
        with YoutubeDL(options) as ydl:
            names.append(ydl.prepare_filename(dict(information)))

    # yt-dlp's own sanitizing puts a big solidus, U+29F8, where the slash was.
    assert names == ["a\u29f8b...mp4", "a_b...mp4"]


def test_embed_metadata_changes_what_this_application_embeds() -> None:
    """Reachability: the application's own metadata processor reads the hatch's `compat_opts`."""
    from yt_dlp.postprocessor.ffmpeg import FFmpegMetadataPP

    information = {"id": "x", "title": "x", "description": "about it", "webpage_url": "https://e"}
    comments = []
    for text in ("--fragment-retries 3", "--compat-options embed-metadata"):
        request = replace(a_request(text), embed_metadata=True)
        with YoutubeDL(build_options(request, "%(title)s.%(ext)s")) as ydl:
            [embedder] = [pp for pp in ydl._pps["post_process"] if isinstance(pp, FFmpegMetadataPP)]
            pairs = embedder._get_metadata_opts(dict(information))
            arguments = [part for pair in pairs for part in pair]
        comments.append([part for part in arguments if part.startswith("comment=")])

    assert comments == [["comment=https://e"], ["comment=about it"]]


# --- the generator's rule, for the day a control is built -------------------------------------


def _tool() -> ModuleType:
    specification = importlib.util.spec_from_file_location("ytdlp_option_table", TOOL)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.mark.usefixtures("unchanged_process")
def test_a_value_reaching_a_built_control_s_key_is_refused_once_that_control_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`format-sort` and `mtime-by-default` reach `T-250`'s and `T-248`'s keys, and each was
    admitted until its control existed. Building one must refuse them by regenerating, with no list
    to remember to edit: `T-250`'s did, on 2026-10-18."""
    tool = _tool()
    built: dict[str, Any] = dict(tool.built_spellings())
    monkeypatch.setattr(
        tool,
        "built_spellings",
        lambda: {**built, "-S": "format_sort", "--format-sort": "format_sort", "--mtime": "mtime"},
    )

    verdicts, _aliases, carried = tool.compat_values()

    assert verdicts["format-sort"] == "control"
    assert verdicts["mtime-by-default"] == "control"
    assert verdicts["no-live-chat"] is None
    assert "format_sort" not in carried
    # `T-250` built the sort's control on 2026-10-18, and regenerating refused the value for it.
    assert COMPAT_VALUES["format-sort"] == "control"
