"""`core/selection.py` against yt-dlp itself (`T-247`).

The grammars are transcribed because `core/` may not import yt-dlp, and a transcription is only as
good as the check that holds it to the original. Each test here runs yt-dlp's own code over the
same inputs: `PlaylistEntries` for `-I`, `date_from_str(strict=True)` for the dates.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Final

import pytest

from tracks_and_trails.core.selection import (
    chosen_positions,
    date_problem,
    item_positions,
    items_problem,
    resolved_date,
)

#: Item specifications of every shape `PLAYLIST_ITEMS_RE` admits, and some it refuses.
ITEMS: Final = (
    "1",
    "3",
    "0",
    "-1",
    "-2",
    "+2",
    "1:3",
    "1-3",
    "2:",
    ":2",
    ":",
    "-",
    "::2",
    "::-1",
    "-3:",
    ":-2",
    "5:1:-1",
    "1:inf",
    "2:infinite:2",
    "1,3,5",
    "3,1",
    "1,1",
    "1:3,7,-2",
    "10",
    "8:12",
    "-10:",
)
BAD_ITEMS: Final = ("x", "1,,2", ",", "", "1:2:0", "1.5", "1;2", "a:b", "1:3:")
COUNTS: Final = (0, 1, 5, 9)


def yt_dlp_positions(text: str, count: int) -> tuple[int, ...]:
    """What yt-dlp's own `PlaylistEntries` picks from a playlist whose entries are all known."""
    from yt_dlp.utils import PlaylistEntries

    entries = PlaylistEntries(None, {"entries": list(range(count))})
    return tuple(
        position
        for index in PlaylistEntries.parse_playlist_items(text)
        for position, _ in entries[index]
    )


@pytest.mark.parametrize("count", COUNTS)
@pytest.mark.parametrize("text", ITEMS)
def test_the_items_pick_what_yt_dlp_picks(text: str, count: int) -> None:
    assert items_problem(text) is None
    assert item_positions(text, count) == yt_dlp_positions(text, count)


@pytest.mark.parametrize("text", BAD_ITEMS)
def test_items_yt_dlp_refuses_are_refused(text: str) -> None:
    from yt_dlp.utils import PlaylistEntries

    with pytest.raises(ValueError):
        list(PlaylistEntries.parse_playlist_items(text))
    assert items_problem(text) is not None
    with pytest.raises(ValueError):
        item_positions(text, 5)


def test_a_rule_keeps_the_first_n_of_the_chosen_entries_in_playlist_order() -> None:
    """`ARC-010`, amended 2026-10-11: *at most N* is the first N chosen; a repeat is one entry."""
    assert chosen_positions(None, None, 4) == (1, 2, 3, 4)
    assert chosen_positions("3,1,3", None, 5) == (1, 3)
    assert chosen_positions("-3:", 2, 9) == (7, 8)
    assert chosen_positions(None, 2, 9) == (1, 2)
    assert chosen_positions(None, 5, 3) == (1, 2, 3)


#: Dates of every form the strict grammar admits, and some it refuses.
DATES: Final = (
    "20260101",
    "20240229",
    "now",
    "today",
    "yesterday",
    "today-1day",
    "today-2days",
    "today-2weeks",
    "today-1month",
    "now-3months",
    "yesterday-1year",
    "today-13months",
)
BAD_DATES: Final = (
    "2026-01-01",
    "x",
    "today+1day",
    "tomorrow",
    "today-2hours",
    "20261340",
    "20250229",
    "",
    "20260101-1day",
)


@pytest.mark.parametrize("text", DATES)
def test_a_date_resolves_to_the_day_yt_dlp_reads(text: str) -> None:
    """Both read UTC's today; a run spanning UTC midnight could differ, and none here takes long."""
    from yt_dlp.utils import date_from_str

    assert date_problem(text) is None
    assert resolved_date(text) == date_from_str(text, strict=True).strftime("%Y%m%d")


@pytest.mark.parametrize("text", BAD_DATES)
def test_a_date_yt_dlp_refuses_is_refused(text: str) -> None:
    from yt_dlp.utils import date_from_str

    with pytest.raises(ValueError):
        date_from_str(text, strict=True)
    assert date_problem(text) is not None


def test_a_relative_date_resolves_against_the_day_it_is_asked_on() -> None:
    """The freezing half of the ruling: a preset keeps `today-2weeks`, a job keeps a day."""
    assert resolved_date("today-2weeks", date(2026, 10, 11)) == "20260927"
    assert resolved_date("today-1month", date(2026, 3, 31)) == "20260228"
    assert resolved_date("20260101", date(2030, 1, 1)) == "20260101"


def test_today_is_utc_s_today_as_yt_dlp_s_is() -> None:
    assert resolved_date("today") == datetime.now(UTC).strftime("%Y%m%d")
