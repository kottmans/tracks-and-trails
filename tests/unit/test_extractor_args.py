"""Extractor arguments: the grammar, the allowlist, the forbidden pairs and the value (`T-255`).

Ruled 2026-10-19, all four as recommended: six pairs forbidden (`SEC-003` amended); a pair known
only when the pinned yt-dlp's source reads it (`ARC-010` amended, fourth); values stored as typed
and registered for redaction except a fixed vocabulary's (`DAT-003` amended); one
`KEY:ARG=VALUE;…` per line, shown back merged and normalized (`UX-015` amended, third). The real
reading of an argument is `tests/integration/test_extractor_args.py`.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any, Final

import pytest
from yt_dlp import parse_options

from tracks_and_trails.core.extractor_arg_table import EXTRACTOR_ARGS, READ_FROM
from tracks_and_trails.core.extractor_args import (
    FIXED_VOCABULARY,
    FORBIDDEN,
    NO_ARGUMENT,
    UNKNOWN_KEY,
    as_text,
    as_ytdlp,
    extractor_args_problem,
    pair_problem,
    parsed,
    secret_values,
)

ROOT: Final = Path(__file__).resolve().parents[2]


def _generator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "ytdlp_extractor_args", ROOT / "tools" / "ytdlp_extractor_args.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- the allowlist ---------------------------------------------------------------------------


def test_the_allowlist_is_what_the_pinned_source_reads_today() -> None:
    """**Drift-tested like the option table** (ruling 2): regenerated from the pin and compared."""
    generator = _generator()

    assert generator.rendered() == generator.TARGET.read_text(encoding="utf-8")


def test_every_read_resolves_and_none_is_answered_by_hand_without_need() -> None:
    """A read the generator cannot resolve stops it, so a new one is classified, not missed."""
    generator = _generator()
    pairs, unresolved = generator.read_pairs()

    assert unresolved == []
    assert {key: frozenset(arguments) for key, arguments in pairs.items()} == EXTRACTOR_ARGS


def test_the_allowlist_was_read_from_the_pinned_release() -> None:
    import yt_dlp

    assert yt_dlp.version.__version__ == READ_FROM


@pytest.mark.parametrize(
    ("key", "argument"),
    [
        # The mapping's examples, read and not extractor keys, and the token-carrying ones.
        ("twitch", "client_id"),
        ("jiosaavn", "bitrate"),
        ("wrestleuniverse", "device_id"),
        ("youtube-ejs", "jitless"),
        ("youtubepot-webpo", "bind_to_visitor_id"),
        ("youtube", "po_token"),
        ("youtube", "visitor_data"),
        ("generic", "hls_key"),
        ("tiktok", "device_id"),
        ("youtubetab", "skip"),
        # Read only through a class's own table, answered in the generator.
        ("hotstar", "vcodec"),
        ("tiktok", "app_version"),
        ("youtube", "comment_sort"),
    ],
)
def test_pairs_the_mapping_read_are_known(key: str, argument: str) -> None:
    assert argument in EXTRACTOR_ARGS[key]


def test_every_forbidden_pair_is_one_yt_dlp_reads() -> None:
    """A forbidden pair yt-dlp stopped reading would be refused as unknown instead, silently
    losing the ruling's reason; this fails then, so the ruling is looked at again."""
    for key, argument in FORBIDDEN:
        assert argument in EXTRACTOR_ARGS.get(key, frozenset()), (key, argument)


def test_every_fixed_vocabulary_is_a_pair_yt_dlp_reads_and_none_carries_a_token() -> None:
    for key, argument in FIXED_VOCABULARY:
        assert argument in EXTRACTOR_ARGS.get(key, frozenset()), (key, argument)
    for token in (
        ("youtube", "po_token"),
        ("youtube", "visitor_data"),
        ("youtube", "data_sync_id"),
        ("generic", "hls_key"),
        ("tiktok", "device_id"),
        ("twitch", "client_id"),
        ("streaks", "api_key"),
    ):
        assert token not in FIXED_VOCABULARY


# --- the grammar -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "youtube:player_client=web,ios",
        "YouTube:Player-Client=web",
        "youtube:player_client=web;player_skip=js,configs",
        "youtube:lang= fr ",
        r"generic:key_query=a\,b,c",
        "youtube:player_skip",
        "youtube:player_params=a=b",
        "youtube-ejs:jitless=true",
    ],
)
def test_one_line_reads_as_yt_dlp_s_parser_reads_it(line: str) -> None:
    """**The grammar held to yt-dlp's own**, one `--extractor-args` per line."""
    structure, problems = parsed(line)

    assert problems == []
    assert (
        as_ytdlp(structure) == parse_options(["--extractor-args", line]).ydl_opts["extractor_args"]
    )


def test_two_lines_for_one_key_are_merged_where_yt_dlp_keeps_only_the_last() -> None:
    """**The mapped defect** (Medium): a repeated `--extractor-args` for one extractor kept only
    the last, so the first line's argument was accepted and dropped."""
    text = "youtube:player_client=web\nyoutube:lang=fr"
    theirs = parse_options(
        ["--extractor-args", "youtube:player_client=web", "--extractor-args", "youtube:lang=fr"]
    ).ydl_opts["extractor_args"]

    structure, _ = parsed(text)

    assert theirs == {"youtube": {"lang": ["fr"]}}
    assert as_ytdlp(structure) == {"youtube": {"lang": ["fr"], "player_client": ["web"]}}


def test_the_later_line_wins_for_one_argument() -> None:
    structure, _ = parsed("youtube:player_client=web\nyoutube:player_client=ios")

    assert structure == (("youtube", "player_client", ("ios",)),)


@pytest.mark.parametrize(
    "text",
    [
        "youtube:player_client=web,ios;player_skip=js\ntwitch:client_id=abc\nyoutube:lang=fr",
        r"generic:key_query=a\,b,c;variant_query=x=y",
        "youtube:player_skip",
    ],
)
def test_what_is_shown_back_reads_as_the_same_arguments(text: str) -> None:
    """**Shown back merged and normalized** (ruling 4): one line per key, and lossless."""
    structure, problems = parsed(text)

    assert problems == []
    assert parsed(as_text(structure)) == (structure, [])
    assert len(as_text(structure).splitlines()) == len({key for key, _, _ in structure})


@pytest.mark.parametrize(
    ("line", "said"),
    [
        ("nosuchie:anything=1", UNKNOWN_KEY.format(key="nosuchie")),
        ("youtube:nosucharg=1", "youtube has no argument called nosucharg"),
        ("youtube:", NO_ARGUMENT.format(key="youtube")),
        ("player_client=web", "is not KEY:ARGUMENT=VALUE"),
        ("plugin_key:x=1", UNKNOWN_KEY.format(key="plugin_key")),
    ],
)
def test_what_yt_dlp_would_ignore_is_refused_with_the_reason(line: str, said: str) -> None:
    """**`T012-R5` closed for this option**: an unknown key or argument was accepted and ignored
    (mapped: `nosuchie:anything=1`, `youtube:nosucharg=1`); a plugin's key is not on the list."""
    structure, problems = parsed(line)

    assert structure == ()
    assert len(problems) == 1 and said in problems[0], problems


@pytest.mark.parametrize(("key", "argument"), sorted(FORBIDDEN))
def test_each_forbidden_pair_is_refused_with_its_reason(key: str, argument: str) -> None:
    """**Ruling 1** (`SEC-003`, amended): refused where typed, whatever the value, with why."""
    structure, problems = parsed(f"{key}:{argument}=anything")

    assert structure == ()
    assert problems == [FORBIDDEN[key, argument]]
    for reason in FORBIDDEN.values():
        assert "\u2014" not in reason and "\u2013" not in reason


def test_an_unknown_argument_s_reason_offers_none_that_is_forbidden() -> None:
    reason = pair_problem("youtube", "nosuch")

    assert reason is not None
    assert "player_client" in reason and "innertube_host" not in reason


def test_one_bad_line_costs_only_itself() -> None:
    structure, problems = parsed("youtube:player_client=web\nnosuchie:x=1\ntwitch:client_id=a")

    assert len(problems) == 1
    assert {key for key, _, _ in structure} == {"youtube", "twitch"}


# --- the value -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "youtube:player_client=web",
        (("youtube", "player_client", "web"),),
        (("youtube", "player_client", ()),),
        (("youtube", "player_client", (" web",)),),
        (("youtube", "player_client", ("a;b",)),),
        (("youtube", "player_client", ("a\nb",)),),
        (("youtube", "innertube_host", ("h",)),),
        (("nosuchie", "x", ("1",)),),
        (("youtube", "player_client", ("web",)), ("youtube", "lang", ("fr",))),
        (("youtube", "lang", ("fr",)), ("youtube", "lang", ("de",))),
    ],
)
def test_the_model_holds_only_what_the_editor_reads_back(value: object) -> None:
    assert extractor_args_problem(value) is not None


def test_the_model_holds_what_the_grammar_produces() -> None:
    structure, _ = parsed("youtube:lang=fr;player_client=web\ntwitch:client_id=x")

    assert extractor_args_problem(structure) is None
    assert extractor_args_problem(()) is None


def test_values_are_registered_except_a_fixed_vocabulary_s() -> None:
    """**`DAT-003`, amended**: a token is redacted; a client name stays readable."""
    structure, _ = parsed(
        "youtube:player_client=android;po_token=web.gvs+TOKENVALUE\ngeneric:hls_key=0123abcd"
    )

    assert set(secret_values(structure)) == {"web.gvs+TOKENVALUE", "0123abcd"}


def test_no_value_is_kept_with_a_comma_escape_left_in_it() -> None:
    structure, _ = parsed(r"generic:key_query=a\,b")

    assert structure == (("generic", "key_query", ("a,b",)),)
    assert re.search(r"\\,", as_text(structure))


# --- on its way to yt-dlp --------------------------------------------------------------------

ARGUMENTS: Final = (
    ("twitch", "client_id", ("abcdef0123",)),
    ("youtube", "lang", ("fr",)),
    ("youtube", "player_client", ("web", "ios")),
)


def _request(**fields: Any) -> Any:
    from tracks_and_trails.core.models import DownloadRequest

    return DownloadRequest(
        url="https://www.youtube.com/watch?v=abcdefghijk",
        output_directory="/home/someone/Videos",
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        **fields,
    )


def _preset(**fields: Any) -> Any:
    from tracks_and_trails.core.models import MediaKind, Preset

    return Preset(name="P", media_kind=MediaKind.VIDEO, format_selector="best", **fields)


@pytest.mark.parametrize("owner", [_request, _preset])
def test_both_owners_hold_only_a_checked_structure(owner: Any) -> None:
    owner(extractor_args=ARGUMENTS)
    with pytest.raises(ValueError, match="extractor_args"):
        owner(extractor_args=(("youtube", "innertube_host", ("h",)),))
    with pytest.raises(ValueError, match="extractor_args"):
        owner(extractor_args=(("nosuchie", "x", ("1",)),))


def test_no_value_is_in_the_repr() -> None:
    """**Out of the `repr`** (`DAT-003`, amended), which is the route into a log anyone writes."""
    from tracks_and_trails.core import presets

    request = _request(extractor_args=ARGUMENTS)

    assert "abcdef0123" not in repr(request)
    assert "abcdef0123" not in repr(presets.format_choice_of(request))


def test_both_passes_hand_yt_dlp_the_merged_arguments() -> None:
    """**On both passes**, since an argument changes which formats exist and the user picks from
    what the probe found; merged, so each line reaches yt-dlp."""
    from tracks_and_trails.downloader.ytdlp_adapter import build_options

    request = _request(extractor_args=ARGUMENTS)
    line = "youtube:lang=fr;player_client=web,ios"
    theirs = parse_options(
        ["--extractor-args", line, "--extractor-args", "twitch:client_id=abcdef0123"]
    ).ydl_opts["extractor_args"]

    for options in (
        build_options(request, request.output_template, probe_only=True),
        build_options(request, "/home/someone/Videos/.staging/x.mp4"),
    ):
        assert options["extractor_args"] == theirs


def test_nobody_choosing_sends_no_key() -> None:
    from tracks_and_trails.downloader.ytdlp_adapter import build_options

    request = _request()

    assert "extractor_args" not in build_options(request, request.output_template, probe_only=True)


def test_the_preset_s_arguments_reach_the_request_and_the_name_says_whose() -> None:
    """**The name says which extractors, never the values**, which can be tokens."""
    from dataclasses import replace

    from tracks_and_trails.core import presets
    from tracks_and_trails.ui.format_text import derived_preset_name

    preset = replace(presets.BEST_VIDEO, name="Args", extractor_args=ARGUMENTS)
    request = presets.to_request(preset, url="https://example.invalid/x", output_directory="/d")

    assert request.extractor_args == ARGUMENTS
    name = derived_preset_name(preset)
    assert name == "Best video available · extractor arguments for twitch, youtube"
    assert "abcdef0123" not in name


def test_a_preset_is_saved_and_read_back_and_a_bad_one_set_aside(tmp_path: Path) -> None:
    from dataclasses import replace

    from tracks_and_trails.core import presets
    from tracks_and_trails.core import settings as app_settings

    preset = replace(presets.BEST_VIDEO, name="Args", built_in=False, extractor_args=ARGUMENTS)
    target = tmp_path / "settings.toml"
    assert (
        app_settings.save(app_settings.add_preset(app_settings.Settings(), preset), target) is None
    )

    read = app_settings.load(target)

    assert read.settings.presets == (preset,)
    assert read.problem is None
    text = target.read_text(encoding="utf-8").replace('"lang"', '"nosucharg"')
    target.write_text(text, encoding="utf-8")
    edited = app_settings.load(target)
    assert edited.settings.presets == ()
    assert edited.problem is not None and "nosucharg" in edited.problem.reason


def test_a_queued_request_is_stored_and_read_back() -> None:
    from tracks_and_trails.persistence import repositories

    request = _request(extractor_args=ARGUMENTS)

    assert repositories._deserialize_request(repositories._serialize_request(request)) == request


def test_the_options_field_refuses_the_spelling_for_its_control() -> None:
    from tracks_and_trails.downloader.extra_options import HAS_A_CONTROL, admit

    refusals = admit("--extractor-args youtube:player_client=web").refusals

    assert [(refusal.option, refusal.reason) for refusal in refusals] == [
        ("--extractor-args", HAS_A_CONTROL)
    ]
