"""Which items a download keeps: yt-dlp's `-I` and date grammars, transcribed (`T-247`).

**Transcribed, and bound by a test to yt-dlp itself.** `core/` may not import yt-dlp
(`ARCHITECTURE.md` §4), and these grammars are needed where a preset is validated and where a
playlist is expanded, neither of which may load it. `tests/unit/test_selection.py` runs yt-dlp's
own `PlaylistEntries` and `date_from_str` over the same inputs and fails on any difference, which is
the `BROWSER_NAMES` arrangement: a copy is acceptable when something checks it.

**Two rulings shape this** (`ARC-010`, amended 2026-10-11). `-I` and *at most N* act when a playlist
is expanded into one job per entry, never per job, so they resolve to positions here. A date stays
as typed in a preset and is frozen into each job when it is queued, so it resolves to `YYYYMMDD`
here, against the day it is asked on.
"""

from __future__ import annotations

import calendar
import math
import re
from collections.abc import Iterator
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


def items_problem(text: str) -> str | None:
    """Why yt-dlp would refuse `text` as `-I`, or `None` when it would take it.

    The wording is this application's; the decision is yt-dlp's `parse_playlist_items`.
    """
    if not text:
        return "Give an item number, or a range such as 1:5."
    for segment in text.split(","):
        if not segment:
            return "An item between the commas is empty."
        found = _ITEM.fullmatch(segment)
        if found is None:
            return f"{segment!r} is not an item number or a range such as 1:5."
        step = found.group("step")
        if step is not None and int(step) == 0:
            return f"The step in {segment!r} cannot be zero."
    return None


def item_positions(text: str, count: int) -> tuple[int, ...]:
    """The 1-based positions `-I` picks from a playlist of `count` entries, in yt-dlp's order.

    `PlaylistEntries.__getitem__` over a playlist whose entries are all known, transcribed: a
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
    if first is None:
        index = 0 if stride > 0 else count - 1
    else:
        index = first - 1 if first >= 0 else count + first
    if last is None:
        stop = 0.0 if stride < 0 else math.inf
    else:
        stop = last - 1 if last >= 0 else count + last
    stop += 1 if stride > 0 else -1
    sign = 1 if stride > 0 else -1
    while sign * index < sign * stop:
        if 0 <= index < count:
            yield index + 1
        elif index >= count and stride > 0:
            return
        index += stride


def chosen_positions(items: str | None, at_most: int | None, count: int) -> tuple[int, ...]:
    """The 1-based positions a preset's rule picks from a playlist of `count`, in playlist order.

    `items` absent means every entry. `at_most` keeps the first N of those in playlist order
    (`ARC-010`, amended 2026-10-11), which cannot know which of them a date or size filter will
    skip later. A position `items` names twice is chosen once: a selection is a set of entries.
    """
    picked = sorted(set(item_positions(items, count))) if items else list(range(1, count + 1))
    return tuple(picked[:at_most] if at_most is not None else picked)


def date_problem(text: str) -> str | None:
    """Why yt-dlp would refuse `text` as an upload date, or `None` when it would take it."""
    if _DATE.fullmatch(text) is None:
        return "Give a date as YYYYMMDD, or a form such as today, yesterday or today-2weeks."
    try:
        resolved_date(text)
    except ValueError:
        return "That date does not exist."
    return None


def resolved_date(text: str, today: date | None = None) -> str:
    """`text` as the `YYYYMMDD` yt-dlp would read it on `today`, which defaults to UTC's today.

    **UTC, as yt-dlp's `datetime_from_str` takes it**, so a relative date names the same day here
    as in the worker that will compare an upload date against it. Raises `ValueError` for text
    yt-dlp refuses, and for a date that does not exist.
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
        count = int(offset.group("count"))
        unit = offset.group("unit")
        if unit in ("month", "year"):
            return _months_before(start, count * 12 if unit == "year" else count)
        return start - timedelta(days=count * 7 if unit == "week" else count)
    return datetime.strptime(text, "%Y%m%d").date()


def _months_before(start: date, months: int) -> date:
    """`datetime_add_months` with a negative count, the day clamped to the month's length."""
    month = start.month - months - 1
    year = start.year + month // 12
    month = month % 12 + 1
    if year < 1:
        raise ValueError("before the first year")
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


#: The units a size filter is shown in, largest first. yt-dlp's `parse_bytes` reads `k`, `M` and
#: `G` as powers of 1024, so these are binary units and are named as such.
SIZE_UNITS: Final = (("GiB", 1024**3), ("MiB", 1024**2), ("KiB", 1024), ("bytes", 1))


def in_units(size: int) -> tuple[int, str]:
    """`size` bytes as a whole number of the largest unit that holds it exactly."""
    for unit, factor in SIZE_UNITS[:-1]:
        if size % factor == 0:
            return size // factor, unit
    return size, SIZE_UNITS[-1][0]


def size_words(size: int) -> str:
    """`10 MiB`, `1500 bytes`: a size as the editor would show it."""
    amount, unit = in_units(size)
    return f"{amount} {'byte' if (amount, unit) == (1, 'bytes') else unit}"
