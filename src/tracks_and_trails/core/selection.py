"""Which items a download keeps: yt-dlp's `-I`, date and size grammars, transcribed (`T-247`).

**Transcribed, and bound by a test to yt-dlp itself.** `core/` may not import yt-dlp
(`ARCHITECTURE.md` §4), and these grammars are needed where a preset is validated and where a
playlist is expanded, neither of which may load it. `tests/unit/test_selection.py` runs yt-dlp's
own `PlaylistEntries`, `date_from_str` and `parse_bytes` over the same inputs and fails on any
difference, which is the `BROWSER_NAMES` arrangement: a copy is acceptable when something checks it.

**Two rulings shape this** (`ARC-010`, amended 2026-10-11). `-I` and *at most N* act when a playlist
is expanded into one job per entry, never per job, so they resolve to positions here. A date stays
as typed in a preset and is frozen into each job when it is queued, so it resolves to `YYYYMMDD`
here, against the day it is asked on.

**Where this differs from yt-dlp, it refuses what yt-dlp would misread or crash on** (`T247-R2`).
yt-dlp reads a range number too long for `int()` as absent, so `1:3:<5000 nines>` means `1:3`
there, and it raises on a date or size too large for its arithmetic. Each is a refusal here, with
a reason, and never an exception: everything that checks a value checks it through these.
"""

from __future__ import annotations

import calendar
import math
import re
from collections.abc import Collection, Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Final

#: `PlaylistEntries.PLAYLIST_ITEMS_RE`, read at 2026.08.19. One item of a comma-separated `-I`: a
#: position, or a range `start:end:step` (`-` also separates start and end), where a negative
#: position counts from the end and the end may be `inf`.
_ITEM: Final = re.compile(
    r"(?P<start>[+-]?\d+)?(?P<range>[:-](?P<end>[+-]?\d+|inf(?:inite)?)?(?::(?P<step>[+-]?\d+))?)?"
)

#: `date_from_str(..., strict=True)`'s pattern, read at 2026.08.19: what `--date`, `--dateafter`
#: and `--datebefore` accept. Only a minus offset, and only whole days, weeks, months or years.
_DATE: Final = re.compile(r"\d{8}|(now|today|yesterday)(-\d+(day|week|month|year)s?)?")

#: How a relative date's offset is read, `datetime_from_str`'s own pattern.
_OFFSET: Final = re.compile(r"(?P<start>.+)-(?P<count>\d+)(?P<unit>day|week|month|year)s?")

#: `parse_bytes`, read at 2026.08.19: `lookup_unit_table` over `''` and `K` to `Y` in powers of
#: 1024, matched strictly against the text upper-cased. What `--min-filesize` and
#: `--max-filesize` accept, so `500M` here is the `500M` yt-dlp's documentation shows.
_SIZE: Final = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>[KMGTPEZY]?)\b")
_SIZE_FACTORS: Final = {unit: 1024**power for power, unit in enumerate(["", *"KMGTPEZY"])}

#: The most entries *at most N* may name (`T247-R3`): the editor's count is a Qt `int`, and no
#: playlist has more entries than that.
MOST_ITEMS: Final = 2**31 - 1

#: The largest size a filter may hold, 8 PiB (`T247-R3`). yt-dlp reads a size through a `float`,
#: and this is the largest at which every whole number of bytes still reads back exactly, so a
#: stored size always survives being shown in yt-dlp's own grammar and read again.
LARGEST_SIZE: Final = 2**53

#: How many characters of a segment a refusal repeats before naming it by position instead.
_SHOWN: Final = 24


class _TooFarBackError(ValueError):
    """A relative date before the first day `datetime.date` holds, or with an unreadable count."""


def items_problem(text: str) -> str | None:
    """Why `text` is refused as `-I`, or `None` when it is taken.

    The wording is this application's; the grammar is yt-dlp's `parse_playlist_items`. **Every
    number must be one `int()` can read** (`T247-R2`): yt-dlp refuses a lone item it cannot read
    and silently drops a range number it cannot read, and the second is refused here too.
    """
    if not text:
        return "Give an item number, or a range such as 1:5."
    for place, segment in enumerate(text.split(","), start=1):
        named = repr(segment) if len(segment) <= _SHOWN else f"item {place}"
        if not segment:
            return "An item between the commas is empty."
        found = _ITEM.fullmatch(segment)
        if found is None:
            return f"{named} is not an item number or a range such as 1:5."
        start, end, step = found.group("start", "end", "step")
        numbers = [number for number in (start, end, step) if number and number[0] != "i"]
        if not all(_readable(number) for number in numbers):
            return f"A number in {named} is too long to read."
        if step is not None and int(step) == 0:
            return f"The step in {named} cannot be zero."
    return None


def _readable(number: str) -> bool:
    """Whether `int()` reads `number`: Python refuses more digits than its conversion limit."""
    try:
        int(number)
    except ValueError:
        return False
    return True


def item_positions(text: str, count: int) -> tuple[int, ...]:
    """The 1-based positions `-I` picks from a playlist of `count` slots, in yt-dlp's order.

    `PlaylistEntries.__getitem__` over a playlist whose slots are all known, transcribed: a
    position past the end ends a forward range and is passed over by a backward one, and a
    position before the first is skipped. A position may repeat, as yt-dlp would repeat it.
    Raises `ValueError` for text `items_problem` refuses.
    """
    problem = items_problem(text)
    if problem is not None:
        raise ValueError(problem)
    chosen: list[int] = []
    for segment in text.split(","):
        found = _ITEM.fullmatch(segment)
        assert found is not None  # items_problem has accepted every segment
        start, end, step = found.group("start", "end", "step")
        if found.group("range"):
            first = int(start) if start is not None else None
            last = _end(end)
            stride = int(step) if step is not None else 1
        else:
            first = last = int(start)
            stride = 1
        chosen.extend(_walk(first, last, stride, count))
    return tuple(chosen)


def _end(text: str | None) -> float | None:
    if text is None:
        return None
    return math.inf if text.startswith("inf") else float(text)


def _walk(first: int | None, last: float | None, stride: int, count: int) -> Iterator[int]:
    """yt-dlp's index arithmetic, then **only the indices inside the playlist** (`T247-R4`).

    yt-dlp steps through every index between the two ends and skips the ones outside, so
    `-1000000000:3` costs a billion steps for three entries. The same indices are reached here by
    moving each end to the first in-range index on the step's own lattice, so the work is bounded
    by `count` whatever was typed. `range` keeps it exact for integers of any size, and an end is
    compared with a `float` only after `count` has bounded it.

    **An end can be an infinity** (`T247-R4`, second round): `int()` reads `-<400 nines>`, and as a
    `float` it is minus infinity. Each direction therefore stops before any rounding when its end
    is already behind its start, which is also when yt-dlp's own loop never runs.
    """
    if first is None:
        start = 0 if stride > 0 else count - 1
    else:
        start = first - 1 if first >= 0 else count + first
    if last is None:
        stop: float = math.inf if stride > 0 else -1.0
    else:
        stop = (last - 1 if last >= 0 else count + last) + (1 if stride > 0 else -1)
    if stride > 0:
        # Below the first entry, yt-dlp skips; at or past the last, it stops.
        if start < 0:
            start %= stride
        if not stop > start:
            return
        end = count if stop > count else math.ceil(stop)
        for index in range(start, end, stride):
            yield index + 1
        return
    # Backwards: past the last entry yt-dlp skips each index, and below the first nothing remains.
    span = -stride
    if start > count - 1:
        start = count - 1 - (count - 1 - start) % span
    low = max(stop, -1.0)
    if not low < start:
        return
    for index in range(start, math.floor(low), stride):
        yield index + 1


def chosen_positions(
    items: str | None,
    at_most: int | None,
    count: int,
    available: Collection[int] | None = None,
) -> tuple[int, ...]:
    """The 1-based positions a preset's rule picks from a playlist of `count` slots, in order.

    `items` absent means every slot. **`count` and the positions are the extraction's own slots,
    the unavailable ones included** (`T247-R1`): yt-dlp's `-I 2` names the second slot whether
    or not it could be read, and counting only what survived would name the third. `available`
    is the slots that hold an entry; *at most N* then keeps the first N of those the rule chose,
    in playlist order (`ARC-010`, amended 2026-10-11), since an unavailable slot is never a
    download. A position `items` names twice is chosen once: a selection is a set of entries.
    """
    picked = sorted(set(item_positions(items, count))) if items else list(range(1, count + 1))
    if available is not None:
        picked = [position for position in picked if position in available]
    return tuple(picked[:at_most] if at_most is not None else picked)


def date_problem(text: str) -> str | None:
    """Why `text` is refused as an upload date, or `None` when it is taken."""
    if _DATE.fullmatch(text) is None:
        return "Give a date as YYYYMMDD, or a form such as today, yesterday or today-2weeks."
    try:
        resolved_date(text)
    except _TooFarBackError:
        return "That is further back than a calendar can name."
    except ValueError:
        return "That date does not exist."
    return None


def resolved_date(text: str, today: date | None = None) -> str:
    """`text` as the `YYYYMMDD` yt-dlp would read it on `today`, which defaults to UTC's today.

    **UTC, as yt-dlp's `datetime_from_str` takes it**, so a relative date names the same day here
    as in the worker that will compare an upload date against it. Raises `ValueError` for text
    yt-dlp refuses, for a date that does not exist, and for one before the first year — where
    yt-dlp's own arithmetic raises `OverflowError` or `ValueError` (`T247-R2`).
    """
    if _DATE.fullmatch(text) is None:
        raise ValueError(f"not a date yt-dlp accepts: {text!r}")
    return _resolved(text, today if today is not None else datetime.now(UTC).date()).strftime(
        "%Y%m%d"
    )


def _resolved(text: str, today: date) -> date:
    if text in ("now", "today"):
        return today
    if text == "yesterday":
        return today - timedelta(days=1)
    offset = _OFFSET.fullmatch(text)
    if offset is not None:
        start = _resolved(offset.group("start"), today)
        if not _readable(offset.group("count")):
            raise _TooFarBackError("the count has too many digits to read")
        count = int(offset.group("count"))
        unit = offset.group("unit")
        if unit in ("month", "year"):
            return _months_before(start, count * 12 if unit == "year" else count)
        try:
            return start - timedelta(days=count * 7 if unit == "week" else count)
        except OverflowError as overflow:
            raise _TooFarBackError("before the first year") from overflow
    return datetime.strptime(text, "%Y%m%d").date()


def _months_before(start: date, months: int) -> date:
    """`datetime_add_months` with a negative count, the day clamped to the month's length."""
    month = start.month - months - 1
    year = start.year + month // 12
    month = month % 12 + 1
    if year < 1:
        raise _TooFarBackError("before the first year")
    return start.replace(
        year=year, month=month, day=min(start.day, calendar.monthrange(year, month)[1])
    )


def empty_window(after: str | None, before: str | None) -> bool:
    """Whether a request's frozen upload dates leave no day between them.

    **Possible, and not refused by the model.** A preset may mix a fixed date with a relative one,
    and the two can cross as the days pass, so a window that was open when the preset was saved can
    be shut on the day a job is queued. yt-dlp refuses such a `DateRange` outright; the worker ends
    the job *Cancelled* with this reason instead, as for any item the filters pass over.
    """
    return after is not None and before is not None and after > before


def parsed_size(text: str) -> int | None:
    """The bytes yt-dlp's `parse_bytes` reads `text` as, or `None` where it reads none.

    **`None` too where yt-dlp would raise**: a number too large for a `float` becomes infinity,
    and yt-dlp's `round` of it raises `OverflowError` (`T247-R2`'s class).
    """
    found = _SIZE.fullmatch(text.upper())
    if found is None:
        return None
    scaled = float(found.group("num")) * _SIZE_FACTORS[found.group("unit")]
    return round(scaled) if math.isfinite(scaled) else None


def size_problem(text: str) -> str | None:
    """Why `text` is refused as a size filter, or `None` when it is taken."""
    size = parsed_size(text)
    if size is None:
        return "Give a size such as 500M or 2G. yt-dlp counts K, M and G in 1024s."
    if size < 1:
        return "A size of nothing would let no file through."
    if size > LARGEST_SIZE:
        return "No file is that large. The most a size can be is 8P."
    return None


def size_text(size: int) -> str:
    """`size` bytes in yt-dlp's own grammar, exactly: `2G`, `1500`. `parsed_size` reads it back."""
    for unit in "YZEPTGMK":
        factor = _SIZE_FACTORS[unit]
        if size % factor == 0:
            return f"{size // factor}{unit}"
    return str(size)


#: The units a size is *named* in, largest first, for the descriptions a row and a preset show.
SIZE_UNITS: Final = (("GiB", 1024**3), ("MiB", 1024**2), ("KiB", 1024), ("bytes", 1))


def in_units(size: int) -> tuple[int, str]:
    """`size` bytes as a whole number of the largest unit that holds it exactly."""
    for unit, factor in SIZE_UNITS[:-1]:
        if size % factor == 0:
            return size // factor, unit
    return size, SIZE_UNITS[-1][0]


def size_words(size: int) -> str:
    """`10 MiB`, `1500 bytes`: a size as a description says it."""
    amount, unit = in_units(size)
    return f"{amount} {'byte' if (amount, unit) == (1, 'bytes') else unit}"
