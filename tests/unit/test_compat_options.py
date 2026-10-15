"""The options field's shaping and compatibility values, held where they act (`T-363`).

Two findings of 2026-10-14, ruled the next day. **A file name's shaping acted on the download's
whole path**: `--trim-filenames` and `--windows-filenames` reach the download pass, which is handed
the contained absolute path as a literal, and yt-dlp reshaped its folders. And **`--compat-options`
was admitted as a whole** though one of its values switches yt-dlp's unsafe-extension check off for
the entire process, one rewrites a file's name the application owns, and two reach keys that
controls are planned for.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any, Final

import pytest
from yt_dlp import YoutubeDL, parse_options
from yt_dlp.utils import FormatSorter
from yt_dlp.utils._utils import _UnsafeExtensionError

from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.downloader.extra_options import (
    COMPAT_REFUSALS,
    admit,
    options_for,
    resolved_compat_values,
)
from tracks_and_trails.downloader.option_table import COMPAT_VALUES, OPTION_KEYS
from tracks_and_trails.downloader.worker import as_literal_template
from tracks_and_trails.downloader.ytdlp_adapter import (
    RENDER_ONLY_KEYS,
    build_options,
    hatch_options,
    hatch_requires_ffmpeg,
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
        "--compat-options all,-allow-unsafe-ext,-allow-unsafe-exec-expansion,-filename",
        "--compat-options all --compat-options -allow-unsafe-ext,-allow-unsafe-exec-expansion,"
        "-filename",
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
    """`format-sort` and `mtime-by-default` reach `T-250`'s and `T-248`'s keys, and are admitted
    while neither control exists. Building one must refuse them by regenerating, with no list to
    remember to edit."""
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
    assert COMPAT_VALUES["format-sort"] is None, "a control for the sort was built; update this"
