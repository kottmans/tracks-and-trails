"""The download sections' grammar, checked where they are typed (`T-252`).

`--download-sections` downloads part of an item, and each section is one of three things: a
**chapter pattern**, a regular expression matched against the item's chapter titles; a **time
range**, `*` and then `start-end`, several of them comma-separated; or **`*from-url`**, the range
the item's own address names. yt-dlp checks the grammar only on its command line, in
`parse_options`, and its library takes whatever it is handed, so `T-252`'s criterion has the
grammar parsed and refused here, where the user types it.

**A transcription, because `core/` may not import yt-dlp** (`ARCHITECTURE.md` §6), and the check
runs in the GUI process as the user types. `parse_chapters` and `parse_duration` are copied from
the pin, regular expressions verbatim, and `tests/unit/test_sections.py` binds both to yt-dlp's own
over every spelling it can think of: a section is accepted here exactly when yt-dlp's command line
accepts it, and a range means the same seconds to both.

**One rule is stricter than yt-dlp's**: a range that ends where or before it starts is refused.
yt-dlp passes it to ffmpeg, which is asked for a negative length and writes nothing usable. It is
checked only where both ends count from the start, because an end counted from the item's end is
not known until the item is.

**Several sections write several files** (`ARC-010`, amended 2026-10-19): one file per section,
named by the stem and a section suffix. Whether a request can write more than one is decided from
the request alone, so the preview and the worker agree before anything is fetched; see
`writes_several`.

**A time range is placed against the item's length before it is cut** (`T252-R1`, `ARC-010`
amended 2026-10-25). yt-dlp asks ffmpeg for whatever the range says, and ffmpeg seeking past the
end of an item wrote the whole item, reported as the part. So a range that starts at or after the
end cancels the item instead, with the words below; see `starting_past`.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from typing import Final

#: yt-dlp's spelling for the range the item's own address names, `?t=` and the like.
FROM_URL: Final = "*from-url"

#: `parse_chapters`' range pattern, verbatim from the pin (2026.08.19, `yt_dlp/__init__.py`).
#: Neither end may contain `-`, which is what lets the separator be one.
_TIMESTAMP_RE: Final = r"""(?x)(?:
            (?P<start_sign>-?)(?P<start>[^-]+)
        )?\s*-\s*(?:
            (?P<end_sign>-?)(?P<end>[^-]+)
        )?"""

#: `parse_duration`'s three forms, verbatim from the pin (`yt_dlp/utils/_utils.py`): clock
#: notation, `1h2m3s` and its ISO 8601 cousin, and a bare `1.5 hours` or `90 minutes`.
_CLOCK: Final = re.compile(
    r"""(?x)
            (?P<before_secs>
                (?:(?:(?P<days>[0-9]+):)?(?P<hours>[0-9]+):)?(?P<mins>[0-9]+):)?
            (?P<secs>(?(before_secs)[0-9]{1,2}|[0-9]+))
            (?P<ms>[.:][0-9]+)?Z?$
        """
)
_UNITS: Final = re.compile(
    r"""(?ix)(?:P?
                (?:
                    [0-9]+\s*y(?:ears?)?,?\s*
                )?
                (?:
                    [0-9]+\s*m(?:onths?)?,?\s*
                )?
                (?:
                    [0-9]+\s*w(?:eeks?)?,?\s*
                )?
                (?:
                    (?P<days>[0-9]+)\s*d(?:ays?)?,?\s*
                )?
                T)?
                (?:
                    (?P<hours>[0-9]+)\s*h(?:(?:ou)?rs?)?,?\s*
                )?
                (?:
                    (?P<mins>[0-9]+)\s*m(?:in(?:ute)?s?)?,?\s*
                )?
                (?:
                    (?P<secs>[0-9]+)(?P<ms>\.[0-9]+)?\s*s(?:ec(?:ond)?s?)?\s*
                )?Z?$"""
)
_WORDS: Final = re.compile(
    r"(?i)(?:(?P<hours>[0-9.]+)\s*(?:hours?)|(?P<mins>[0-9.]+)\s*(?:mins?\.?|minutes?)\s*)Z?$"
)

#: How a range is written, for a refusal to show.
RANGE_EXAMPLE: Final = "*1:30-2:45, or *10:00-inf for the rest"

#: What each file adds to the stem when a request can write several (`ARC-010`, amended
#: 2026-10-19): `Clip (section 1).mp4`, `Clip (section 2).mp4`. **One spelling for three readers**:
#: the adapter's template, the worker's claim, which recognises a sidecar yt-dlp recorded under a
#: section's name, and the preview.
SECTION_SUFFIX: Final = " (section {number})"
_OPENING, _CLOSING = SECTION_SUFFIX.split("{number}")


def sectioned_stem(stem: str, number: int | str) -> str:
    """`stem` with the suffix of section `number`, which may be a template field."""
    return stem + SECTION_SUFFIX.format(number=number)


def unsectioned_name(name: str, stem: str) -> str:
    """`name` without a section suffix after `stem`, or `name` unchanged when it has none.

    `Clip (section 2).en.vtt` becomes `Clip.en.vtt`: the name yt-dlp moves a section's sidecar to
    when the sidecar templates keep the base name, though it records the section's own.
    """
    prefix = stem + _OPENING
    if not name.startswith(prefix):
        return name
    number, closing, rest = name[len(prefix) :].partition(_CLOSING)
    return stem + rest if closing and number.isdigit() else name


def parse_duration(text: str) -> int | float | None:
    """Seconds in `text`, as yt-dlp's `parse_duration` reads them, or `None` if it reads none.

    **Faithful, quirks included**: `"P"` reads as zero and years, months and weeks are matched and
    ignored, because that is what the pin does, and a section that means something different here
    from what it means to yt-dlp is the defect this module exists to prevent.
    """
    text = text.strip()
    if not text:
        return None
    days: str | None
    hours: str | None
    mins: str | None
    secs: str | None
    ms: str | None
    days = hours = mins = secs = ms = None
    if clock := _CLOCK.match(text):
        days, hours, mins, secs, ms = clock.group("days", "hours", "mins", "secs", "ms")
    elif units := _UNITS.match(text):
        days, hours, mins, secs, ms = units.group("days", "hours", "mins", "secs", "ms")
    elif words := _WORDS.match(text):
        hours, mins = words.group("hours", "mins")
    else:
        return None
    if ms:
        ms = ms.replace(":", ".")
    try:
        total = sum(
            float(part or 0) * multiplier
            for part, multiplier in ((days, 86400), (hours, 3600), (mins, 60), (secs, 1), (ms, 1))
        )
    except ValueError:
        # `1.2.3 hours`: yt-dlp's own `float()` raises here, so its command line refuses the
        # section too, with the `ValueError` as its reason.
        return None
    return int(total) if total.is_integer() else total


def _timestamp(text: str) -> float | None:
    """One end of a range: `inf` or `infinite`, or a duration (`parse_chapters`' own reading)."""
    return math.inf if text in ("inf", "infinite") else parse_duration(text)


def parsed_ranges(section: str) -> list[tuple[float, float]] | None:
    """The `(start, end)` seconds of a `*` section, negative counting from the end, or `None`.

    `None` for anything that is not a well-formed time range. The ends are what yt-dlp's
    `download_range_func` receives, so `test_sections.py` compares them with its own.
    """
    if not section.startswith("*") or section == FROM_URL:
        return None
    found: list[tuple[float, float]] = []
    for piece in (part.strip() for part in section[1:].split(",")):
        match = piece != "-" and re.fullmatch(_TIMESTAMP_RE, piece)
        if not match:
            return None
        start = _timestamp(match.group("start") or "0")
        end = _timestamp(match.group("end") or "inf")
        if start is None or end is None:
            return None
        start *= -1 if match.group("start_sign") else 1
        end *= -1 if match.group("end_sign") else 1
        if end == -math.inf:
            return None
        found.append((start, end))
    return found


def section_problem(section: str) -> str | None:
    """Why yt-dlp would refuse `section`, or this module would, in words; `None` if usable."""
    if not section.strip():
        return "A section cannot be empty."
    if section == FROM_URL:
        return None
    if not section.startswith("*"):
        try:
            re.compile(section)
        except (re.error, OverflowError, RecursionError) as error:
            # The last two are what `re` raises for a repeat count past its limit and for nesting
            # too deep for its parser, neither of them `re.error` (`T184-R8`).
            return f"{section!r} is not a chapter pattern: {error}."
        return None
    ranges = parsed_ranges(section)
    if ranges is None:
        return f"{section!r} is not a time range. Write it as {RANGE_EXAMPLE}."
    for start, end in ranges:
        if start >= 0 and end >= 0 and end <= start:
            return f"{section!r} ends before it starts."
    return None


def sections_problem(sections: Iterable[str]) -> str | None:
    """The first section's problem, or `None` when every one is usable."""
    for section in sections:
        if (problem := section_problem(section)) is not None:
            return problem
    return None


def sections_from_text(text: str) -> tuple[str, ...]:
    """The sections typed one per line, each without its surrounding space, blank lines dropped."""
    return tuple(line.strip() for line in text.splitlines() if line.strip())


def writes_several(sections: Iterable[str]) -> bool:
    """Whether these sections can make yt-dlp write more than one file (`T-252`).

    **Decided from the request, so the preview and the worker agree before anything is fetched.**
    A chapter pattern can match any number of chapters, so it counts as several; `*from-url` is
    at most one range; a `*` section is as many as its commas make. One time range writes the
    one file the name says, and anything more is numbered.
    """
    count = 0
    for section in sections:
        if section == FROM_URL:
            count += 1
        elif section.startswith("*"):
            count += len(parsed_ranges(section) or ())
        else:
            return True
    return count > 1


def needs_the_length(sections: Iterable[str]) -> bool:
    """Whether any section is placed by time, so the item's length decides whether it is inside.

    A chapter pattern is matched against the item's own chapters, which are inside it by
    definition, so it needs no length (`T252-R1`).
    """
    return any(section.startswith("*") for section in sections)


def starting_past(
    sections: Iterable[str], length: float, url_start: float | None = None
) -> tuple[str, ...]:
    """Every section asking for a range that starts at or after `length` seconds (`T252-R1`).

    **Only the start decides**: a range that starts inside and runs past the end is cut to the end,
    as yt-dlp cuts it (ruled 2026-10-25). A start counted from the end is inside by construction,
    since yt-dlp takes it from the length and never below zero. `*from-url` starts where the address
    says, `url_start`, which yt-dlp reads as zero when the address names none.
    """
    outside: list[str] = []
    for section in sections:
        if section == FROM_URL:
            starts = [url_start or 0.0]
        elif section.startswith("*"):
            starts = [start for start, _end in parsed_ranges(section) or ()]
        else:
            continue
        if any(start >= 0 and start >= length for start in starts):
            outside.append(section)
    return tuple(outside)


def length_text(seconds: float) -> str:
    """A length as a person reads one: `6 seconds`, `2:05` or `1:02:03`, like the sections."""
    shown = round(seconds, 1)
    if shown < 60:
        return f"{shown:g} second" + ("" if shown == 1 else "s")
    hours, rest = divmod(int(shown), 3600)
    minutes, whole = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{whole:02d}" if hours else f"{minutes}:{whole:02d}"


def past_the_end_reason(outside: Iterable[str], length: float) -> str:
    """Why an item was cancelled for sections past its end, naming each (`T252-R1`)."""
    named = list(outside)
    listed = named[0] if len(named) == 1 else ", ".join(named[:-1]) + " and " + named[-1]
    starts = "starts" if len(named) == 1 else "start"
    return (
        f"Nothing was downloaded: {listed} {starts} after the end of this item, which is "
        f"{length_text(length)} long."
    )


#: Why an item whose length nobody can say was cancelled rather than cut (`T252-R1`, ruling 3).
NO_LENGTH: Final = (
    "Nothing was downloaded: this item does not say how long it is, and its length could not be "
    "read, so part of it cannot be cut. Downloading the whole item may work."
)
