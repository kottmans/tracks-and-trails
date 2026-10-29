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
    YOUTUBE_CLIENTS,
    YOUTUBE_LANGUAGES,
    as_text,
    as_ytdlp,
    extractor_args_need_ffmpeg,
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

    assert set(secret_values(structure)) == {
        "web.gvs+TOKENVALUE",
        "0123abcd",
        # Second round: lower-cased as yt-dlp reads it. `TOKENVALUE` is no `base64`, so yt-dlp
        # prints it only in the whole value.
        "web.gvs+tokenvalue",
    }


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
    assert edited.problem is not None
    # `T255-R1`: an argument no extractor reads can be a token typed in the wrong place.
    assert "names an argument youtube does not read" in edited.problem.reason
    assert "nosucharg" not in edited.problem.reason


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


# --- T255-R1: a refusal quotes nothing it was handed ------------------------------------------

#: A made-up token, typed where a value, a key or an argument goes.
TOKEN: Final = "t255secrettokenvalue"  # noqa: S105 - made up, and what the tests look for


@pytest.mark.parametrize(
    "value",
    [
        TOKEN,
        [("youtube", "po_token", (TOKEN,))],
        ((TOKEN,),),
        (("youtube", "po_token", (TOKEN,), "a fourth cell"),),
        (("youtube", "po_token", [TOKEN]),),
        ((TOKEN, "po_token", ("x",)),),
        (("youtube", TOKEN, ("x",)),),
        (("youtube", "po_token", (f"web.gvs+{TOKEN};x",)),),
        (("youtube", "po_token", (f"web.gvs+{TOKEN}\u2028x",)),),
        (("youtube", "po_token", (f" {TOKEN}",)),),
        (("youtube", "po_token", (TOKEN,)), ("youtube", "lang", ("fr",))),
    ],
    ids=[
        "text",
        "list",
        "one cell",
        "four cells",
        "values a list",
        "key",
        "argument",
        "semicolon",
        "line separator",
        "edge space",
        "out of order",
    ],
)
def test_no_refusal_quotes_a_value_or_a_name_nothing_reads(value: object) -> None:
    """**The review's case**: a refusal travels into the settings file's report, logged at startup
    before anything registers the value, and quoted the item or the value whole."""
    problem = extractor_args_problem(value)

    assert problem is not None
    assert TOKEN not in problem


@pytest.mark.parametrize(
    "row",
    [
        f'["youtube", "po_token", ["web.gvs+{TOKEN};x"]]',
        f'["youtube", "po_token", ["{TOKEN}"], "extra"]',
        f'["{TOKEN}", "po_token", ["x"]]',
        f'["youtube", "{TOKEN}", ["x"]]',
        f'"{TOKEN}"',
    ],
    ids=["value", "four cells", "key", "argument", "bare text"],
)
def test_a_preset_set_aside_at_startup_is_reported_without_its_token(
    tmp_path: Path, row: str
) -> None:
    """The real reader, on the file the review hand-edited: the preset is set aside and said so,
    and its report, which composition logs, holds nothing of what was typed."""
    from dataclasses import replace

    from tracks_and_trails.core import presets
    from tracks_and_trails.core import settings as app_settings

    preset = replace(presets.BEST_VIDEO, name="Args", built_in=False, extractor_args=ARGUMENTS)
    target = tmp_path / "settings.toml"
    assert (
        app_settings.save(app_settings.add_preset(app_settings.Settings(), preset), target) is None
    )
    text = target.read_text(encoding="utf-8")
    written = re.search(r"extractor_args = \[.*\]\n", text)
    assert written is not None, text
    target.write_text(text.replace(written.group(0), f"extractor_args = [{row}]\n"), "utf-8")

    read = app_settings.load(target)

    assert read.settings.presets == ()
    assert read.problem is not None and "Args" in read.problem.reason
    assert TOKEN not in read.problem.reason


# --- T255-R2: what is held is what the editor reads back ---------------------------------------


def test_a_value_ending_in_a_backslash_keeps_the_next_one_apart() -> None:
    r"""**The review's case**: `x=\` beside `y=2` was shown back as `x=\,y=2`, which reads as one
    value, `x=,y=2`, so accepting and reopening the editor changed the arguments."""
    structure, problems = parsed("generic:key_query=x=\\ ,y=2")

    assert problems == [] and structure == (("generic", "key_query", ("x=\\", "y=2")),)
    assert parsed(as_text(structure)) == (structure, [])
    assert extractor_args_problem(structure) is None
    line = as_text(structure)
    assert line == "generic:key_query=x=\\ ,y=2"
    assert parse_options(["--extractor-args", line]).ydl_opts["extractor_args"] == {
        "generic": {"key_query": ["x=\\", "y=2"]}
    }
    # Only a value with another after it is parted: the last is shown as it is.
    assert as_text((("generic", "key_query", ("y=2", "x=\\")),)) == "generic:key_query=y=2,x=\\"


def test_any_value_the_model_holds_reads_back_the_same_here_and_to_yt_dlp() -> None:
    """Values made of the grammar's own characters, a thousand of them, seeded: whatever the model
    holds, the editor's text reads back to it, and yt-dlp's parser reads the same values."""
    import random

    chosen = random.Random(255)  # noqa: S311 - test data, not a secret
    held = 0
    for _ in range(1000):
        values = tuple(
            "".join(chosen.choice("ab=\\, ") for _ in range(chosen.randint(0, 6)))
            for _ in range(chosen.randint(1, 3))
        )
        structure = (("generic", "key_query", values),)
        if extractor_args_problem(structure) is not None:
            continue
        held += 1
        line = as_text(structure)
        assert parsed(line) == (structure, []), line
        read = parse_options(["--extractor-args", line]).ydl_opts["extractor_args"]
        assert read == {"generic": {"key_query": list(values)}}, line
    assert held > 300, "too few held to say anything"


#: Every character `str.splitlines` breaks a line at, which the editor's reading uses.
LINE_BREAKS: Final = frozenset(
    chr(point) for point in range(0x110000) if len(f"a{chr(point)}b".splitlines()) == 2
)


def test_the_line_breaks_are_the_ones_the_review_named_and_more() -> None:
    assert {"\u2028", "\u0085", "\v"} <= LINE_BREAKS
    assert len(LINE_BREAKS) == 10


@pytest.mark.parametrize("brake", sorted(LINE_BREAKS))
@pytest.mark.parametrize("owner", ["request", "preset"])
def test_a_value_holding_any_line_break_is_refused_by_both_owners(brake: str, owner: str) -> None:
    """The editor reads one line per key, broken where `str.splitlines` breaks, so a value holding
    U+2028, U+0085 or a vertical tab was held and could not be shown back."""
    arguments = (("youtube", "lang", (f"f{brake}r",)),)

    with pytest.raises(ValueError, match="cannot show back"):
        (_request if owner == "request" else _preset)(extractor_args=arguments)


# --- T255-R3: a value is readable only from its argument's own vocabulary ----------------------

#: The pinned release's documentation, which carries the README, and its extractor arguments.
_DOCUMENTED: Final = Path(parse_options.__code__.co_filename).parent.parent.joinpath(
    next(
        path.name
        for path in Path(parse_options.__code__.co_filename).parent.parent.iterdir()
        if path.name.startswith("yt_dlp-") and path.name.endswith(".dist-info")
    ),
    "METADATA",
)


def _documented_line(key: str, argument: str) -> str:
    """The pinned documentation's line for `key:argument`, under the key's own heading."""
    text = _DOCUMENTED.read_text(encoding="utf-8")
    section = text.split("# EXTRACTOR ARGUMENTS", 1)[1]
    heading = re.search(rf"^#### (?:[^\n]*\b|){re.escape(key)}\b[^\n]*$", section, re.M)
    assert heading is not None, key
    body = section[heading.end() :].split("\n#### ", 1)[0]
    found = re.search(rf"^\* `{re.escape(argument)}`:.*$", body, re.M)
    assert found is not None, (key, argument)
    return found.group(0)


#: Arguments read only for being there, or for not being `false`, whose two words are a flag's:
#: each read at the pin, where the documentation names no value.
_READ_AS_PRESENT: Final = frozenset(
    {
        ("generic", "is_live"),  # `is_live == 'false'`, any other is live
        ("orfon", "prefer_segments_playlist"),  # `if self._configuration_arg(...)`
        ("youtube", "include_duplicate_formats"),  # `if self._configuration_arg(...)`
        ("youtube", "raise_incomplete_data"),  # `bool(self._configuration_arg(...))`
        ("youtubetab", "approximate_date"),  # `if self._configuration_arg(...)`
    }
)

#: The vocabularies whose words come from the class attribute the extractor compares against, each
#: held to it exactly below rather than to the documentation.
_FROM_THE_CODE: Final = frozenset(
    {
        ("afreecatvlive", "cdn"),
        ("youtube", "lang"),
        ("youtube", "player_client"),
        ("youtube", "player_js_variant"),
        ("soundcloud", "formats"),
    }
)


@pytest.mark.parametrize(
    ("key", "argument"),
    sorted(set(FIXED_VOCABULARY) - _FROM_THE_CODE - _READ_AS_PRESENT),
)
def test_each_word_is_one_the_pinned_documentation_gives_the_argument(
    key: str, argument: str
) -> None:
    line = _documented_line(key, argument)
    # Each word as the documentation spells one, in backticks, alone or in a list: `all,all`.
    documented = {word for span in re.findall(r"`([^`]*)`", line) for word in span.split(",")}

    for word in FIXED_VOCABULARY[key, argument].words:
        assert word in documented, (key, argument, word, line)


def test_an_argument_read_as_present_is_left_readable_only_as_a_flag() -> None:
    for pair in _READ_AS_PRESENT:
        assert FIXED_VOCABULARY[pair].words == {"true", "false"}, pair
        assert not FIXED_VOCABULARY[pair].counts, pair


def test_the_vocabularies_taken_from_the_code_are_the_code_s() -> None:
    from yt_dlp.extractor.afreecatv import AfreecaTVLiveIE
    from yt_dlp.extractor.jiosaavn import JioSaavnBaseIE
    from yt_dlp.extractor.nfl import NFLPlusReplayIE
    from yt_dlp.extractor.rokfin import RokfinChannelIE
    from yt_dlp.extractor.sonyliv import SonyLIVSeriesIE
    from yt_dlp.extractor.soundcloud import SoundcloudBaseIE
    from yt_dlp.extractor.vimeo import VimeoBaseInfoExtractor
    from yt_dlp.extractor.youtube._base import INNERTUBE_CLIENTS, YoutubeBaseInfoExtractor
    from yt_dlp.extractor.youtube._video import YoutubeIE

    def words(key: str, argument: str) -> frozenset[str]:
        return FIXED_VOCABULARY[key, argument].words

    clients = {client for client in INNERTUBE_CLIENTS if not client.startswith("_")}
    assert clients == YOUTUBE_CLIENTS
    assert words("youtube", "player_client") == (
        clients | {f"-{client}" for client in clients} | {"default", "all"}
    )
    assert set(YoutubeBaseInfoExtractor._SUPPORTED_LANG_CODES) == YOUTUBE_LANGUAGES
    assert words("youtube", "lang") == YOUTUBE_LANGUAGES
    assert words("youtube", "player_js_variant") == {*YoutubeIE._PLAYER_JS_VARIANT_MAP, "actual"}
    assert words("youtube", "webpage_client") == set(YoutubeIE._WEBPAGE_CLIENTS)
    assert words("afreecatvlive", "cdn") == {
        *AfreecaTVLiveIE._WORKING_CDNS,
        *AfreecaTVLiveIE._BAD_CDNS,
    }
    assert words("jiosaavn", "bitrate") == JioSaavnBaseIE._VALID_BITRATES
    assert words("nflplusreplay", "type") == {*NFLPlusReplayIE._REPLAY_TYPES, "all"}
    assert words("rokfinchannel", "tab") == set(RokfinChannelIE._TABS)
    assert words("sonylivseries", "sort_order") == set(SonyLIVSeriesIE._SORT_ORDERS)
    assert words("vimeo", "client") == set(VimeoBaseInfoExtractor._CLIENT_CONFIGS)
    assert words("soundcloud", "formats") == {"*", "default", *SoundcloudBaseIE._DEFAULT_FORMATS}


def test_an_argument_whose_words_come_from_the_site_has_no_vocabulary() -> None:
    """SoundCloud's comment sorts are the filters its API offers at run time (`available_filters`),
    so no word of theirs is known in advance."""
    assert ("soundcloud", "comments_sort_by") not in FIXED_VOCABULARY
    assert secret_values((("soundcloud", "comments_sort_by", ("newest",)),)) == ("newest",)


@pytest.mark.parametrize(
    ("line", "registered"),
    [
        # The review's case: the client stays readable, the token beside it does not.
        (f"youtube:player_client=android,{TOKEN}", (TOKEN,)),
        ("youtube:player_client=-web,default", ()),
        # An open pattern: only its own two words and the default formats are known.
        ("soundcloud:formats=default,*,hls_*,http_aac", ("hls_*",)),
        # A count is readable as a number, and only as one.
        ("youtube:max_comments=1000,all,12a", ("12a",)),
        # A count as `int` reads one: fullwidth digits are, a superscript is not.
        ("youtube:max_comments=\uff11\uff12\uff13", ()),
        ("youtube:max_comments=\u00b2", ("\u00b2",)),
        ("niconicochannelplus:max_comments=500", ()),
        ("bilibili:prefer_multi_flv=80,eighty", ("eighty",)),
        # A flag's two words, and nothing else.
        ("zan:split_angles=true", ()),
        (f"zan:split_angles={TOKEN}", (TOKEN,)),
        ("youtube:lang=en-GB", ()),
        ("youtube:lang=en-gb", ("en-gb",)),
    ],
)
def test_a_value_is_left_readable_only_from_its_vocabulary(
    line: str, registered: tuple[str, ...]
) -> None:
    structure, problems = parsed(line)

    assert problems == []
    assert secret_values(structure) == registered


@pytest.mark.parametrize("marker", [TOKEN, "T255_UPPERCASE_MARKER", "t255_MiXeD_Marker"])
def test_yt_dlp_s_own_warning_about_an_unknown_client_is_redacted(
    monkeypatch: pytest.MonkeyPatch, marker: str
) -> None:
    """**The review's case, through the real path**: yt-dlp's YouTube extractor, initialized and
    asked for its clients with the network refused, quotes a client it does not know in a warning.
    Registered as the manager registers it, and read through `YtdlpLog` into the redacting
    formatter, the token is gone and the warning still says what happened. The control: without
    the registration the token is in the line.

    **Second round**: yt-dlp lower-cases the value before it quotes it, so a token typed with
    capitals was printed in a spelling nobody had registered."""
    import io
    import logging
    import socket

    import yt_dlp

    from tracks_and_trails.core import logging as app_logging

    def refuse(*_: Any, **__: Any) -> None:
        raise OSError("no network in a unit test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    structure, _ = parsed(f"youtube:player_client=android,{marker}")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(app_logging.RedactingFormatter(app_logging.LOG_FORMAT))
    log = logging.getLogger("tests.t255.warning")
    log.handlers = [handler]
    log.propagate = False
    log.setLevel(logging.DEBUG)

    def warn_once() -> str:
        stream.seek(0)
        stream.truncate()
        with yt_dlp.YoutubeDL(
            {"logger": app_logging.YtdlpLog(log), "extractor_args": as_ytdlp(structure)}
        ) as ydl:
            extractor = ydl.get_info_extractor("Youtube")
            extractor.initialize()
            assert extractor._get_requested_clients(
                "https://www.youtube.com/watch?v=xxxxxxxxxxx", {}, False
            ) == ["android"]
        return stream.getvalue()

    try:
        app_logging.forget_the_secrets()
        assert marker.lower() in warn_once(), "the control: yt-dlp did not quote the client"
        for value in secret_values(structure):
            app_logging.remember_a_secret(value)
        logged = warn_once()
    finally:
        app_logging.forget_the_secrets()

    assert "Skipping unsupported client" in logged
    assert marker not in logged
    assert marker.lower() not in logged


@pytest.mark.parametrize("line", ["youtube:player_client=ANDROID,Web", "vimeo:client=Web"])
def test_a_known_word_typed_in_capitals_stays_readable(line: str) -> None:
    """yt-dlp reads it lower-cased, so it is the word it names; registering it would hide that
    word from every line, as `android` or `web`."""
    structure, problems = parsed(line)

    assert problems == []
    assert secret_values(structure) == ()


def _case_reads() -> tuple[set[str], set[str], bool]:
    """The arguments the pinned extractors read keeping their case, and those read lower-cased,
    by name, from every `_configuration_arg` call's syntax tree; and whether a call whose
    argument is not written out keeps its case, which would have to be decided by hand."""
    import ast

    import yt_dlp

    kept: set[str] = set()
    lowered: set[str] = set()
    unwritten_kept = False
    for path in Path(yt_dlp.__file__).parent.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "_configuration_arg"
                and node.args
            ):
                continue
            keeps = any(
                word.arg == "casesense"
                and isinstance(word.value, ast.Constant)
                and word.value.value is True
                for word in node.keywords
            )
            name = node.args[0].value if isinstance(node.args[0], ast.Constant) else None
            if isinstance(name, str):
                (kept if keeps else lowered).add(name)
            else:
                unwritten_kept = unwritten_kept or keeps
    return kept, lowered, unwritten_kept


def test_each_vocabulary_reads_case_as_yt_dlp_does() -> None:
    """**Held to the pin**: an argument read keeping its case is compared as typed, and every
    other lower-cased, so each word of the latter must be lower case to be reachable at all."""
    kept, lowered, unwritten_kept = _case_reads()

    # Hotstar's `res`, `vcodec` and `dr` are read through a variable, lower-cased.
    assert not unwritten_kept, "an argument not written out keeps its case; decide it by hand"
    for (key, name), vocabulary in FIXED_VOCABULARY.items():
        assert name in EXTRACTOR_ARGS[key], f"{key}:{name} is read nowhere"
        assert name not in kept & lowered, f"{name} is read both ways; decide by key"
        assert vocabulary.casesense == (name in kept), f"{key}:{name}"
        if not vocabulary.casesense:
            assert all(word == word.lower() for word in vocabulary.words), f"{key}:{name}"


@pytest.mark.parametrize(
    "token",
    ["QUJDREVGR0hJ", "QUJDREVGR0g%3D", "QUJD*REVG!R0g=", "QUJDREVGR0hJ&pot=1"],
    ids=["as yt-dlp wants it", "quoted", "stray characters", "with a query"],
)
def test_a_po_token_is_registered_as_yt_dlp_cleans_it(token: str) -> None:
    """`_get_config_po_token` unquotes the token, drops what is not `base64` and puts the result
    in a manifest's path; held to the pinned method itself."""
    import yt_dlp
    from yt_dlp.extractor.youtube._base import _PoTokenContext

    value = f"web.gvs+{token}"
    structure, problems = parsed(f"youtube:po_token={value}")
    assert problems == []
    with yt_dlp.YoutubeDL({"quiet": True, "extractor_args": as_ytdlp(structure)}) as ydl:
        cleaned = ydl.get_info_extractor("Youtube")._get_config_po_token("web", _PoTokenContext.GVS)

    assert cleaned is not None
    assert cleaned in secret_values(structure)
    assert value in secret_values(structure)


@pytest.mark.parametrize("value", ["T255DELEGATED||T255SESSION", "T255SESSION||"])
def test_a_data_sync_id_is_registered_in_the_pieces_yt_dlp_reads(value: str) -> None:
    from yt_dlp.extractor.youtube._base import YoutubeBaseInfoExtractor

    structure, _ = parsed(f"youtube:data_sync_id={value}")
    pieces = {piece for piece in YoutubeBaseInfoExtractor._parse_data_sync_id(value) if piece}

    assert pieces
    assert pieces <= set(secret_values(structure))


def test_tiktok_s_debug_line_of_its_app_info_is_redacted() -> None:
    """TikTok cuts `app_info` at `/` and writes the pieces to a debug line as a `dict`, so each
    piece is printed alone, lower-cased, and as `repr` spells it: the backslash here doubled.
    Through the pinned `_get_next_app_info`, and the control is the line before registering."""
    import yt_dlp

    from tracks_and_trails.core import logging as app_logging

    value = "7351144126450059040/T255_App\\Name/T255.9.9/T2552023401020"
    structure, problems = parsed(f"tiktok:app_info={value}")
    assert problems == []
    with yt_dlp.YoutubeDL({"quiet": True, "extractor_args": as_ytdlp(structure)}) as ydl:
        extractor = ydl.get_info_extractor("TikTok")
        assert extractor._get_next_app_info()
        line = str(extractor._APP_INFO)
    assert "7351144126450059040" in line and "t255_app\\\\name" in line, line

    try:
        app_logging.forget_the_secrets()
        for one in secret_values(structure):
            app_logging.remember_a_secret(one)
        redacted = app_logging.redact(line)
    finally:
        app_logging.forget_the_secrets()

    # `t255_app` stands for its piece in both spellings; the `dict`'s own keys hold `name`.
    for piece in ("7351144126450059040", "t255_app", "t255.9.9", "t2552023401020"):
        assert piece not in redacted.lower(), redacted


# --- T255-R4: an argument that makes the download ffmpeg's -------------------------------------


@pytest.mark.parametrize(
    ("values", "splits"),
    [(("true",), True), (("yes",), True), (("",), True), (("TRUE",), True), (("false",), False),
     (("FALSE",), False), (("false", "true"), False)],
)  # fmt: skip
def test_both_gates_count_zan_s_split_as_ffmpeg_s_as_yt_dlp_reads_it(
    values: tuple[str, ...], splits: bool
) -> None:
    """**The review's case**: upstream's own `_multiangle_formats`, driven with the value, writes
    ffmpeg's crop and `libx264` into each angle exactly when it splits, and the offer and the
    worker both said no ffmpeg was needed. The control is upstream's own answer."""
    from dataclasses import replace

    import yt_dlp
    from yt_dlp.extractor.zan import ZanIE

    from tracks_and_trails.core import presets
    from tracks_and_trails.downloader.ytdlp_adapter import requires_ffmpeg

    arguments = (("zan", "split_angles", values),)
    with yt_dlp.YoutubeDL({"quiet": True, "extractor_args": as_ytdlp(arguments)}) as ydl:
        zan = ZanIE(ydl)
        formats = zan._multiangle_formats(
            [{"format_id": "hls-720", "vcodec": "avc1", "height": 720, "url": "https://z/a.m3u8"}],
            "4_x",
            4,
            0,
        )
    upstream = any("libx264" in str(fmt.get("downloader_options")) for fmt in formats)
    assert upstream is splits, formats

    assert extractor_args_need_ffmpeg(arguments) is splits
    assert presets.needs_ffmpeg(replace(presets.BEST_VIDEO, extractor_args=arguments)) is splits
    assert requires_ffmpeg(_request(extractor_args=arguments)) is splits


def test_no_other_argument_counts_as_ffmpeg_s() -> None:
    from tracks_and_trails.core import presets
    from tracks_and_trails.downloader.ytdlp_adapter import requires_ffmpeg

    assert not extractor_args_need_ffmpeg(ARGUMENTS)
    assert not requires_ffmpeg(_request(extractor_args=ARGUMENTS))
    assert not presets.needs_ffmpeg(presets.BEST_VIDEO)


def test_a_value_ending_in_a_backslash_is_stored_and_read_back(tmp_path: Path) -> None:
    """`T255-R2` in both stores: the settings file and the queue's database."""
    from dataclasses import replace

    from tracks_and_trails.core import presets
    from tracks_and_trails.core import settings as app_settings
    from tracks_and_trails.persistence import repositories

    arguments = (("generic", "key_query", ("x=\\", "y=2")),)
    preset = replace(presets.BEST_VIDEO, name="Args", built_in=False, extractor_args=arguments)
    target = tmp_path / "settings.toml"
    assert (
        app_settings.save(app_settings.add_preset(app_settings.Settings(), preset), target) is None
    )

    read = app_settings.load(target)

    assert read.problem is None and read.settings.presets == (preset,)
    request = _request(extractor_args=arguments)
    assert repositories._deserialize_request(repositories._serialize_request(request)) == request
