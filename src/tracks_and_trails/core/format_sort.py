"""The format sort's grammar, checked field by field and limit by limit (`T-250`).

`-S/--format-sort` takes a comma-separated list of yt-dlp's sort fields, each optionally reversed
with `+` and limited with `:` (at most) or `~` (closest to). **yt-dlp refuses almost nothing about
what a sort means**, measured at 2026.08.19: an unknown field is ignored with a deprecation line
and written into the class's field table; `res:abc` silently sets no limit; `vcodec:nonsense`
silently picks a different format; a field named twice keeps only its first mention. So
`ARC-010`'s 2026-10-15 amendment rules the sort checked here, against a transcription of yt-dlp's
own vocabulary, and refused where it is typed.

**A transcription, because `core/` may not import yt-dlp** (`ARCHITECTURE.md` §6), and it has to be
checkable in the GUI process while the user types. `tests/unit/test_format_sort.py` binds it to
the pin **in a fresh process**: yt-dlp's field table is class state that an unknown field writes
into, so asking it in a process that has already sorted would read what earlier sorts left there.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Final

from tracks_and_trails.core.selection import parsed_size

#: How a field's limit is read, which is yt-dlp's `_resolve_field_value` per conversion:
#: `number` is `float_or_none`; `digits` is the branch that takes only `str.isnumeric` text and
#: otherwise rewrites the field to compare as text; `size` is `parse_bytes`; `ordered` finds the
#: limit in the field's order; `text` takes anything.
NUMBER: Final = "number"
DIGITS: Final = "digits"
SIZE: Final = "size"
ORDERED: Final = "ordered"
TEXT: Final = "text"


@dataclass(frozen=True, slots=True)
class SortField:
    """One field yt-dlp sorts by, as far as checking a limit for it needs."""

    #: How its limit is read; `None` for a field made of others, whose parts are checked instead.
    limit: str | None
    #: The parts of a combined field, which take one limit each, separated by `:`.
    parts: tuple[str, ...] = ()
    #: For an ordered field, the patterns a limit must match (`regex`) or the values it must be.
    order: tuple[str, ...] = ()
    regex: bool = False
    #: For an ordered field, limits a person would write, which its refusal suggests.
    examples: tuple[str, ...] = ()


#: Every field yt-dlp sorts by at 2026.08.19, `FormatSorter.settings` without its aliases.
#: **Its two hidden fields are left out**, `hidden` and `aud_or_vid`: yt-dlp forces them first and
#: marks them not visible, so a user naming one is naming plumbing.
SORT_FIELDS: Final[dict[str, SortField]] = {
    "vcodec": SortField(
        ORDERED,
        order=(
            "av0?1",
            r"vp0?9\.0?2",
            "vp0?9",
            "[hx]265|he?vc?",
            "[hx]264|avc",
            "vp0?8",
            "mp4v|h263",
            "theora",
            "none",
        ),
        regex=True,
        examples=("av01", "vp9", "h265", "h264", "vp8"),
    ),
    "acodec": SortField(
        ORDERED,
        order=(
            "[af]lac",
            "wav|aiff",
            "opus",
            "vorbis|ogg",
            "aac",
            "mp?4a?",
            "mp3",
            "ac-?4",
            "e-?a?c-?3",
            "ac-?3",
            "dts",
            "none",
        ),
        regex=True,
        examples=("flac", "opus", "aac", "mp3"),
    ),
    "hdr": SortField(
        ORDERED,
        order=("dv", "(hdr)?12", r"(hdr)?10\+", "(hdr)?10", "hlg", "sdr"),
        regex=True,
        examples=("dv", "hdr10", "hlg", "sdr"),
    ),
    "proto": SortField(
        ORDERED,
        order=(
            "(ht|f)tps",
            "(ht|f)tp$",
            "m3u8.*",
            ".*dash",
            "websocket_frag",
            "rtmpe?",
            "ws|websocket",
            "f4",
        ),
        regex=True,
        examples=("https", "http", "m3u8", "dash"),
    ),
    "vext": SortField(
        ORDERED, order=("mp4", "mov", "webm", "flv", "none"), examples=("mp4", "webm")
    ),
    "aext": SortField(
        ORDERED,
        order=("m4a", "aac", "mp3", "ogg", "opus", "web[am]", "none"),
        regex=True,
        examples=("m4a", "opus", "webm"),
    ),
    "ie_pref": SortField(DIGITS),
    "hasvid": SortField(DIGITS),
    "hasaud": SortField(DIGITS),
    "lang": SortField(DIGITS),
    "quality": SortField(DIGITS),
    "filesize": SortField(SIZE),
    "fs_approx": SortField(SIZE),
    "id": SortField(TEXT),
    "height": SortField(NUMBER),
    "width": SortField(NUMBER),
    "fps": SortField(NUMBER),
    "channels": SortField(NUMBER),
    "tbr": SortField(NUMBER),
    "vbr": SortField(NUMBER),
    "abr": SortField(NUMBER),
    "asr": SortField(NUMBER),
    "source": SortField(DIGITS),
    "codec": SortField(None, parts=("vcodec", "acodec")),
    "br": SortField(NUMBER),
    "size": SortField(SIZE),
    "ext": SortField(None, parts=("vext", "aext")),
    "res": SortField(DIGITS),
}

#: yt-dlp's other names for a field, which it takes without comment: the format dict's own keys.
SORT_ALIASES: Final[dict[str, str]] = {
    "format_id": "id",
    "preference": "ie_pref",
    "language_preference": "lang",
    "source_preference": "source",
    "protocol": "proto",
    "filesize_approx": "fs_approx",
    "audio_channels": "channels",
}

#: The names yt-dlp still takes with a deprecation line, and the field each stands for. Refused
#: naming the field, so a preset never carries a spelling the next yt-dlp may drop.
DEPRECATED_SORT_ALIASES: Final[dict[str, str]] = {
    "dimension": "res",
    "resolution": "res",
    "extension": "ext",
    "bitrate": "br",
    "total_bitrate": "tbr",
    "video_bitrate": "vbr",
    "audio_bitrate": "abr",
    "framerate": "fps",
    "filesize_estimate": "size",
    "samplerate": "asr",
    "video_ext": "vext",
    "audio_ext": "aext",
    "video_codec": "vcodec",
    "audio_codec": "acodec",
    "video": "hasvid",
    "has_video": "hasvid",
    "audio": "hasaud",
    "has_audio": "hasaud",
    "extractor": "ie_pref",
    "extractor_preference": "ie_pref",
}

#: One item, as yt-dlp's `FormatSorter.regex` reads it once the item is stripped: `+` to reverse,
#: a field, and a limit after `:` or `~`.
_ITEM: Final = re.compile(
    r"(?P<reverse>\+)?(?P<field>[a-zA-Z0-9_]+)(?:(?P<separator>[~:])(?P<limit>.*))?"
)


def sort_items(text: str) -> tuple[str, ...]:
    """The items of a sort, as `-S` splits them: on commas, stripped, empty ones dropped."""
    return tuple(item for item in (part.strip() for part in text.split(",")) if item)


def format_sort_problem(text: str) -> str | None:
    """Why `text` is not a sort this application will send, in words for the editor, or `None`."""
    items = sort_items(text)
    if not items:
        return "Name at least one field to sort by, such as res or vcodec."
    seen: set[str] = set()
    for item in items:
        problem = _item_problem(item, seen)
        if problem is not None:
            return problem
    return None


def _item_problem(item: str, seen: set[str]) -> str | None:
    found = _ITEM.fullmatch(item)
    if found is None:
        return (
            f"{item!r} is not a sort field. Write a field, optionally +field to reverse it, "
            "and :limit or ~limit after it."
        )
    name, limit = found.group("field"), found.group("limit")
    field = _field_named(name)
    if isinstance(field, str):
        return field
    resolved = SORT_ALIASES.get(name, name)
    parts = SORT_FIELDS[resolved].parts or (resolved,)
    if limit is not None:
        problem = _limits_problem(name, resolved, limit)
        if problem is not None:
            return problem
    for part in parts:
        if part in seen:
            return f"{part} is sorted by twice; yt-dlp would use only its first place."
        seen.add(part)
    return None


def _field_named(name: str) -> SortField | str:
    """The field `name` names, or why it names none."""
    if name in DEPRECATED_SORT_ALIASES:
        return f"{name} is an old name yt-dlp is retiring. Use {DEPRECATED_SORT_ALIASES[name]}."
    resolved = SORT_ALIASES.get(name, name)
    if resolved in SORT_FIELDS:
        return SORT_FIELDS[resolved]
    if name.lower() != name and isinstance(_field_named(name.lower()), SortField):
        # yt-dlp takes it only after treating the name as an unknown field, with a deprecation
        # line, and writing it into its field table.
        return f"Write {name} in lower case, {name.lower()}."
    return f"{name} is not a field yt-dlp sorts by."


def _limits_problem(name: str, resolved: str, limit: str) -> str | None:
    field = SORT_FIELDS[resolved]
    if not field.parts:
        return _limit_problem(name, resolved, limit)
    pieces = limit.split(":")
    if len(pieces) > len(field.parts):
        return (
            f"{name} takes at most {len(field.parts)} limits, one for each of "
            f"{' and '.join(field.parts)}."
        )
    for part, piece in zip(field.parts, pieces, strict=False):
        problem = _limit_problem(part, part, piece)
        if problem is not None:
            return problem
    return None


def _limit_problem(name: str, resolved: str, limit: str) -> str | None:
    """Why `limit` would not limit `resolved`, where yt-dlp would read it as no limit or another."""
    if not limit:
        return f"{name} has nothing after its : or ~. Give a limit, or leave both out."
    field = SORT_FIELDS[resolved]
    value = limit.lower()
    if field.limit == TEXT:
        return None
    if field.limit == SIZE:
        if parsed_size(value) is None:
            return f"{name}:{limit} is not a size. Write one such as 500M or 2G."
        return None
    if field.limit == DIGITS:
        if not re.fullmatch(r"[0-9]+", value):
            return f"{name}:{limit} is not a whole number, which is the only limit {name} takes."
        return None
    if field.limit == NUMBER:
        try:
            number = float(value)
        except ValueError:
            number = math.nan
        if math.isnan(number):
            return f"{name}:{limit} is not a number."
        return None
    if field.regex:
        if any(re.match(pattern, value) for pattern in field.order):
            return None
    elif value in field.order:
        return None
    return (
        f"{name}:{limit} names nothing yt-dlp knows for {name}, so it would not limit anything. "
        f"Try {', '.join(field.examples)}."
    )
