"""`docs/YTDLP_OPTION_AUDIT.md` against the two things that can contradict it (`T-183`).

The audit classifies every documented yt-dlp option into exactly one class, and its whole value
rests on two claims that a document cannot keep true by itself:

- **the inventory is yt-dlp's**, not a list somebody transcribed, and
- **the application-owned class is `build_options`'**, not a list somebody remembered.

`T-183`'s second acceptance criterion asks for exactly this test, and `ARC-010`'s own history is
why: its §4 names `paths` as an application-owned key, and `build_options` has never set it. A
list written from memory drifts from the code silently, and the refusal list `T-184` builds on
top of it inherits the drift.

**Every expectation here is re-derived, never transcribed.** The option inventory comes from
`create_parser()`, the emitted keys come from calling `build_options` over every branch, and the
only hand-written thing is the audit itself — which is the artefact under test.
"""

import dataclasses
import re
from optparse import SUPPRESS_HELP
from pathlib import Path
from typing import Any, Final

import pytest
import yt_dlp.version
from yt_dlp.options import create_parser

from tracks_and_trails.core.models import AudioCodec, DownloadRequest, MediaKind
from tracks_and_trails.downloader.ytdlp_adapter import build_options

YTDLP_VERSION: Final = yt_dlp.version.__version__

AUDIT = Path(__file__).resolve().parents[2] / "docs" / "YTDLP_OPTION_AUDIT.md"

#: Classes whose options the escape hatch must refuse (`ARC-010` §4, `SEC-003`).
REFUSED: Final = frozenset({"app:sets", "app:contained", "app:plumbing", "excluded"})
#: Classes that may legitimately name a key `build_options` sets.
MAY_SET: Final = frozenset({"app:sets", "typed"})
KNOWN_CLASSES: Final = REFUSED | MAY_SET | {"hatch", "unruled"}


# --- what yt-dlp actually has ------------------------------------------------------------------


def _options() -> list[dict[str, Any]]:
    parser = create_parser()
    return [
        {
            "strings": tuple(opt._short_opts) + tuple(opt._long_opts),
            "dest": opt.dest,
            "documented": opt.help is not SUPPRESS_HELP and opt.help is not None,
        }
        for group in parser.option_groups
        for opt in group.option_list
    ]


ALL_OPTIONS: Final = _options()
DOCUMENTED: Final = [o for o in ALL_OPTIONS if o["documented"]]
SUPPRESSED: Final = [o for o in ALL_OPTIONS if not o["documented"]]


# --- what `build_options` actually sets --------------------------------------------------------

_BASE: Final = {
    "url": "https://example.invalid/watch?v=x",
    "output_directory": str(Path.home() / "downloads"),
    "format_selector": "bv*+ba/b",
    "output_template": "%(title)s.%(ext)s",
}
#: One value per `DownloadRequest` field that can turn a branch on inside `build_options`.
_FIELD_ON: Final = {
    "media_kind": MediaKind.AUDIO,
    "audio_codec": AudioCodec.MP3,
    "audio_quality": "192",
    "post_processors": ("FFmpegThumbnailsConvertor",),
    "subtitle_languages": ("en",),
    "embed_subtitles": True,
    "embed_thumbnail": True,
    "embed_metadata": True,
    "embed_chapters": True,
    "remux_container": "mkv",
    "recode_container": None,  # `DownloadRequest` refuses this alongside `remux_container`
    "proxy": "http://127.0.0.1:8080",
    "rate_limit_bytes": 1024,
    "retries": 0,
    "cookies_from_browser": "firefox",
}
_KEYWORD_ON: Final = {
    "probe_only": True,
    "ffmpeg_location": Path("/usr/bin/ffmpeg"),
    "cookie_file": Path.home() / "cookies.txt",
    "overwrites": True,
    "logger": object(),
}


def _emitted_keys() -> frozenset[str]:
    """Every key `build_options` can emit, by exercising it rather than by reading it.

    Each branch is turned on alone and then all together, which is what makes this a derivation:
    a new `if` in `build_options` that sets a new key shows up here without anyone editing a list.
    """
    fields = {f.name for f in dataclasses.fields(DownloadRequest)}
    unexercised = fields - set(_FIELD_ON) - set(_BASE)
    assert not unexercised, (
        f"{sorted(unexercised)} are DownloadRequest fields no case here turns on, so this "
        f"derivation cannot see the keys they set. Add them to _FIELD_ON."
    )

    on = {name: value for name, value in _FIELD_ON.items() if value is not None}
    cases = [({}, {})]
    cases += [({name: value}, {}) for name, value in on.items()]
    cases += [({}, {name: value}) for name, value in _KEYWORD_ON.items()]
    cases.append((on, dict(_KEYWORD_ON)))
    cases.append((on, {k: v for k, v in _KEYWORD_ON.items() if k != "probe_only"}))

    keys: set[str] = set()
    for overrides, keywords in cases:
        request = DownloadRequest(**_BASE, **overrides)
        keys |= set(build_options(request, _BASE["output_template"], **keywords))
    return frozenset(keys)


EMITTED: Final = _emitted_keys()


# --- the audit, parsed -------------------------------------------------------------------------

_ROW = re.compile(r"^\|((?:\s*`[^`]+`)+)\s*\|\s*`([a-z:]+)`\s*\|\s*(.+?)\s*\|$")


def _rows() -> list[tuple[tuple[str, ...], str, str]]:
    """The classification tables only — the findings above them have tables of their own."""
    text = AUDIT.read_text(encoding="utf-8")
    _, _, tables = text.partition("\n## The tables\n")
    assert tables, "the audit has no '## The tables' section to parse"
    parsed = []
    for line in tables.splitlines():
        match = _ROW.match(line.strip())
        if match:
            strings = tuple(re.findall(r"`([^`]+)`", match.group(1)))
            parsed.append((strings, match.group(2), match.group(3)))
    return parsed


ROWS: Final = _rows()


# --- the audit is about a named version --------------------------------------------------------


def test_the_audit_names_the_yt_dlp_version_it_was_taken_against() -> None:
    """`T-183`: an audit of an unnamed version cannot be re-run when upstream moves.

    This fails when the pin in `pyproject.toml` moves, which is the point — a bump is exactly
    when the classification has to be looked at again, and `NFR-008` owns that.
    """
    recorded = re.search(r"\*\*yt-dlp version:\*\* \*\*([0-9.]+)\*\*", AUDIT.read_text("utf-8"))
    assert recorded, "the audit does not state the yt-dlp version it was taken against"
    assert recorded.group(1) == YTDLP_VERSION, (
        f"the audit was taken against yt-dlp {recorded.group(1)} and {YTDLP_VERSION} is "
        f"installed. Re-run it (T-183) rather than editing the version line."
    )


# --- every documented option, exactly once -----------------------------------------------------


def test_every_documented_option_is_classified_exactly_once() -> None:
    classified: dict[str, int] = {}
    for strings, _, _ in ROWS:
        for string in strings:
            classified[string] = classified.get(string, 0) + 1

    documented = {s for option in DOCUMENTED for s in option["strings"]}
    twice = sorted(s for s, n in classified.items() if n > 1)
    assert not twice, f"classified in more than one row: {twice}"
    assert not documented - set(classified), (
        f"documented by yt-dlp and absent from the audit: {sorted(documented - set(classified))}"
    )
    assert not set(classified) - documented, (
        f"classified by the audit and not documented by yt-dlp: "
        f"{sorted(set(classified) - documented)}"
    )


def test_the_audit_states_the_row_count_it_has() -> None:
    """`T-212`'s row count said forty-one from an estimate and was forty-seven when counted."""
    stated = re.search(r"\*\*Rows:\*\* \*\*(\d+)\*\*", AUDIT.read_text("utf-8"))
    assert stated and int(stated.group(1)) == len(ROWS) == len(DOCUMENTED)


def test_the_audit_states_the_documented_and_suppressed_split() -> None:
    text = AUDIT.read_text("utf-8")
    assert f"**{len(ALL_OPTIONS)}** options" in text
    assert f"**{len(SUPPRESSED)}** have their help suppressed" in text


def test_every_class_used_is_one_the_audit_defines() -> None:
    used = {cls for _, cls, _ in ROWS}
    assert used <= KNOWN_CLASSES, f"undefined classes in use: {sorted(used - KNOWN_CLASSES)}"


def test_every_row_carries_a_reason() -> None:
    """`T-183`: "nobody asked for it" is a reason; silence is not."""
    silent = [strings for strings, _, note in ROWS if len(note.strip()) < 10]
    assert not silent, f"rows with no reason: {silent}"


# --- the application-owned class is derived, and cannot drift ----------------------------------


def test_no_key_build_options_sets_is_reachable_through_the_hatch() -> None:
    """The invariant the refusal list exists to hold, checked against the code that sets them.

    A key the application sets and the user can also type is a key two sources fight over. The
    audit's answer is that such an option is `app:sets` (refused) or `typed` (a control wins by
    `ARC-010`'s precedence rule) — never `hatch`, which would let the hatch win by silence.
    """
    class_of = {s: cls for strings, cls, _ in ROWS for s in strings}
    escapes = {}
    for option in DOCUMENTED:
        if option["dest"] in EMITTED:
            for string in option["strings"]:
                if class_of[string] not in MAY_SET:
                    escapes[string] = (option["dest"], class_of[string])
    assert not escapes, (
        f"these set a key build_options also sets, and the audit does not refuse them: {escapes}"
    )


def test_every_application_owned_row_names_a_key_build_options_really_sets() -> None:
    """The other direction: a refusal that refuses nothing is a refusal nobody maintains."""
    dest_of = {s: option["dest"] for option in DOCUMENTED for s in option["strings"]}
    stale = {
        strings: dest_of[strings[0]]
        for strings, cls, _ in ROWS
        if cls == "app:sets" and dest_of[strings[0]] not in EMITTED
    }
    assert not stale, f"classified app:sets and build_options never sets the key: {stale}"


def test_the_keys_with_no_command_line_route_are_the_ones_the_audit_names() -> None:
    """Five emitted keys are library parameters; refusing them would refuse nothing."""
    routable = {option["dest"] for option in ALL_OPTIONS}
    assert sorted(EMITTED - routable) == [
        "logger",
        "no_color",
        "postprocessor_hooks",
        "postprocessors",
        "progress_hooks",
    ]


# --- Finding 4: a string-keyed refusal list is routed around ------------------------------------


def test_suppressed_aliases_still_reach_a_refused_key() -> None:
    """Finding 4, kept true rather than kept written.

    `--geo-bypass` sets the same `geo_bypass` that `--xff` does, and `SEC-003` forbids `--xff` by
    name. If upstream ever stops sharing these dests the finding is obsolete and this test says
    so; while it holds, `T-184` cannot key its refusal list on option strings.
    """
    refused_dests = {
        option["dest"]
        for option in DOCUMENTED
        for strings, cls, _ in ROWS
        if cls in REFUSED and option["strings"][0] in strings
    }
    bypassing = {
        s for option in SUPPRESSED if option["dest"] in refused_dests for s in option["strings"]
    }
    assert bypassing == {
        "--all-formats",
        "--geo-bypass",
        "--geo-bypass-country",
        "--geo-bypass-ip-block",
        "--no-geo-bypass",
        "--no-colors",
        "--no-colours",
    }


@pytest.mark.parametrize("option", ["--exec-before-download", "--no-exec-before-download"])
def test_the_forbidden_exec_family_has_a_suppressed_member(option: str) -> None:
    """`SEC-003` names `--exec-before-download`, and the documented surface does not carry it."""
    suppressed = {s for o in SUPPRESSED for s in o["strings"]}
    assert option in suppressed
