"""The format sort's transcription, held to yt-dlp in a fresh process (`T-250`).

`ARC-010`, amended 2026-10-15, second: the sort is checked field by field and limit by limit
against a transcription in `core/`, **bound to the pin by a test run in a fresh process**, because
yt-dlp's field table is class state an unknown field writes into. Two bindings: the vocabulary
equals `FormatSorter.settings`; and over a set of sorts, `format_sort_problem` accepts exactly
those yt-dlp would carry out as written — no deprecation line, no field it invents, every limit
read as a limit, and no field named twice.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any, Final

import pytest

from tracks_and_trails.core.format_sort import (
    DEPRECATED_SORT_ALIASES,
    DIGITS,
    NUMBER,
    ORDERED,
    SIZE,
    SORT_ALIASES,
    SORT_FIELDS,
    TEXT,
    format_sort_problem,
    sort_items,
)

#: Reads `FormatSorter.settings` as yt-dlp left it on import, with its own defaults applied.
_VOCABULARY: Final = r"""
import json
from yt_dlp.utils import FormatSorter

out = {}
for name, setting in FormatSorter.settings.items():
    kind = setting.get("type", "field")
    convert = setting.get("convert") or ("order" if kind == "ordered" else "float_string")
    out[name] = {
        "type": kind,
        "convert": convert,
        "field": setting.get("field"),
        "deprecated": bool(setting.get("deprecated")),
        "visible": setting.get("visible", True),
        "regex": bool(setting.get("regex")),
        "order": [item for item in setting.get("order", ()) if item],
    }
print(json.dumps(out))
"""

#: Runs each sort through yt-dlp's own `FormatSorter`, from a clean field table every time, and
#: reports whether yt-dlp would carry it out as written.
_BEHAVIOUR: Final = r"""
import copy, json, sys
from yt_dlp import YoutubeDL
from yt_dlp.utils import FormatSorter

pristine = copy.deepcopy(FormatSorter.settings)
verdicts = {}
for text in json.loads(sys.stdin.read()):
    FormatSorter.settings = copy.deepcopy(pristine)
    items = [item.strip() for item in text.split(",") if item.strip()]
    warned = []
    with YoutubeDL({"quiet": True, "format_sort": items}) as ydl:
        ydl.deprecated_feature = lambda message, *a, **k: warned.append(message)
        try:
            sorter = FormatSorter(ydl, [])
        except Exception as error:
            verdicts[text] = f"raised {type(error).__name__}"
            continue
    invented = set(FormatSorter.settings) - set(pristine)
    order = sorter._order
    fields = []
    for item in items:
        name = item.lstrip("+").split(":")[0].split("~")[0]
        setting = pristine.get(name, {})
        target = setting.get("field", name) if setting.get("type") == "alias" else name
        combined = pristine.get(target, {}).get("type") == "combined"
        parts = pristine[target]["field"] if combined else (target,)
        has_limit = ":" in item or "~" in item
        separator = ":" if ":" in item else "~"
        limit = item.split(separator, 1)[1] if has_limit else None
        pieces = limit.split(":") if (has_limit and len(parts) > 1) else (limit,)
        fields.append((parts, pieces, has_limit))
    named = [part for parts, _, _ in fields for part in parts]
    unread = []
    for parts, pieces, has_limit in fields:
        if not has_limit:
            continue
        if len(pieces) > len(parts):
            unread.append("extra limits")
        for part, piece in zip(parts, pieces):
            got = FormatSorter.settings[part].get("limit")
            if got is None:
                unread.append(part)
            elif (
                FormatSorter.settings[part].get("convert") == "string"
                and pristine[part].get("convert") != "string"
            ):
                unread.append(part)
            elif pristine[part].get("type") == "ordered":
                probe = FormatSorter(ydl, [])
                empty = probe._resolve_field_value(part, "")
                if got == empty and piece.lower() != "":
                    unread.append(part)
    verdicts[text] = {
        "warned": bool(warned),
        "invented": sorted(invented),
        "unread": unread,
        "twice": len(named) != len(set(named)),
    }
print(json.dumps(verdicts))
"""

#: Sorts across every field kind, accepted and refused, each run through yt-dlp itself.
SAMPLES: Final = (
    "res:1080,vcodec:h264",
    "res",
    "+size,+br,res,fps",
    "res~720",
    "res:abc",
    "res:720.5",
    "height:720.5",
    "fps:abc",
    "vcodec:nonsense",
    "vcodec:av01",
    "vcodec:vp9.2",
    "vcodec:none",
    "acodec:opus",
    "acodec:xyz",
    "hdr:12",
    "hdr:hdr10",
    "proto:m3u8_native",
    "proto:https",
    "proto:carrier-pigeon",
    "vext:mp4",
    "vext:mkv",
    "aext:webm",
    "codec:h264:aac",
    "codec:h264",
    "codec:h264:aac:x",
    "ext:mp4:m4a",
    "size:500M",
    "size:lots",
    "filesize:1G",
    "quality:2",
    "quality:-1",
    "lang:1",
    "id:137",
    "format_id",
    "protocol:https",
    "resolution:720",
    "framerate",
    "extractor",
    "RES",
    "foo",
    "res,res:720",
    "codec,vcodec",
    "hasvid,hasaud,ie_pref,source",
    "channels:2,asr:44100,tbr:500",
)


def _run(script: str, stdin: str = "") -> Any:
    done = subprocess.run(
        [sys.executable, "-I", "-c", script],
        input=stdin,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(done.stdout)


@pytest.fixture(scope="module")
def vocabulary() -> dict[str, Any]:
    return dict(_run(_VOCABULARY))


def test_the_fields_are_yt_dlp_s_less_its_hidden_ones(vocabulary: dict[str, Any]) -> None:
    fields = {
        name
        for name, setting in vocabulary.items()
        if setting["type"] != "alias" and setting["visible"]
    }

    assert set(SORT_FIELDS) == fields


def test_the_aliases_and_the_retiring_names_are_yt_dlp_s(vocabulary: dict[str, Any]) -> None:
    aliases = {n: s["field"] for n, s in vocabulary.items() if s["type"] == "alias"}

    current = {n: f for n, f in aliases.items() if not vocabulary[n]["deprecated"]}
    retiring = {n: f for n, f in aliases.items() if vocabulary[n]["deprecated"]}

    assert current == SORT_ALIASES
    assert retiring == DEPRECATED_SORT_ALIASES


def test_each_field_reads_its_limit_as_yt_dlp_does(vocabulary: dict[str, Any]) -> None:
    """The conversion decides what a limit is; an ordered field's order is copied whole."""
    kinds = {"float_none": NUMBER, "float": DIGITS, "float_string": DIGITS, "bytes": SIZE}
    for name, field in SORT_FIELDS.items():
        setting = vocabulary[name]
        if setting["type"] == "combined":
            assert field.limit is None and field.parts == tuple(setting["field"]), name
        elif setting["convert"] == "order":
            assert field.limit == ORDERED, name
            assert field.order == tuple(setting["order"]) and field.regex == setting["regex"], name
        elif setting["convert"] == "string":
            assert field.limit == TEXT, name
        else:
            assert field.limit == kinds[setting["convert"]], name


@pytest.fixture(scope="module")
def yt_dlp_verdicts() -> dict[str, Any]:
    examples = [f"{name}:{example}" for name, f in SORT_FIELDS.items() for example in f.examples]
    return dict(_run(_BEHAVIOUR, json.dumps([*SAMPLES, *examples])))


@pytest.mark.parametrize("text", SAMPLES)
def test_a_sort_is_accepted_exactly_when_yt_dlp_would_do_what_it_says(
    text: str, yt_dlp_verdicts: dict[str, Any]
) -> None:
    """**The binding.** yt-dlp carries a sort out as written when it warns of nothing, invents no
    field, reads every limit as one, and finds no field twice."""
    verdict = yt_dlp_verdicts[text]
    as_written = isinstance(verdict, dict) and not (
        verdict["warned"] or verdict["invented"] or verdict["unread"] or verdict["twice"]
    )

    assert (format_sort_problem(text) is None) is as_written, (text, verdict)


def test_every_suggested_limit_is_one_yt_dlp_reads(yt_dlp_verdicts: dict[str, Any]) -> None:
    for name, field in SORT_FIELDS.items():
        for example in field.examples:
            verdict = yt_dlp_verdicts[f"{name}:{example}"]
            assert not verdict["unread"], (name, example)
            assert format_sort_problem(f"{name}:{example}") is None


def test_the_items_are_split_as_the_command_line_splits_them() -> None:
    from yt_dlp import parse_options

    for text in ("res:1080, vcodec:h264", " res ,, +size ", "res"):
        assert list(sort_items(text)) == parse_options(["-S", text]).ydl_opts["format_sort"]


@pytest.mark.parametrize(
    ("text", "says"),
    [
        ("resolution:720", "Use res"),
        ("RES", "lower case"),
        ("vcodec:nonsense", "h264"),
        ("res:abc", "whole number"),
        ("res,res:720", "twice"),
        ("", "at least one"),
        ("hidden", "not a field"),
    ],
)
def test_each_refusal_says_what_to_write_instead(text: str, says: str) -> None:
    problem = format_sort_problem(text)

    assert problem is not None and says in problem, problem
