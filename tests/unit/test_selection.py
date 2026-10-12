"""`core/selection.py` against yt-dlp itself (`T-247`).

The grammars are transcribed because `core/` may not import yt-dlp, and a transcription is only as
good as the check that holds it to the original. Each test here runs yt-dlp's own code over the
same inputs: `PlaylistEntries` for `-I`, `date_from_str(strict=True)` for the dates.
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime
from typing import Final

import pytest

from tracks_and_trails.core.selection import (
    LARGEST_SIZE,
    chosen_positions,
    date_problem,
    item_positions,
    items_problem,
    parsed_size,
    resolved_date,
    size_problem,
    size_text,
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
    # Endpoints well outside a short playlist, in both directions (`T247-R4`).
    "-100:3",
    "100:1:-1",
    "3:-100:-1",
    "-73:9:7",
    "102:1:-5",
)

#: Endpoints that `int()` reads and a `float` cannot hold (`T247-R4`, second round), where yt-dlp
#: stops at once and so can be asked directly: an end at minus infinity going forwards, an end at
#: plus infinity going backwards, a start beyond every slot going forwards. The directions where
#: yt-dlp would walk without end are in `FAR`, against a walkable twin.
BEYOND_A_FLOAT: Final = (
    "1:-" + "9" * 400,
    ":-" + "9" * 400,
    "1:" + "9" * 400,
    "5:" + "9" * 400 + ":-1",
    "9" * 400 + ":",
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


@pytest.mark.parametrize("count", COUNTS)
@pytest.mark.parametrize(
    "text", BEYOND_A_FLOAT, ids=lambda text: text.replace("9" * 400, "<400 nines>")
)
def test_an_endpoint_past_a_float_picks_what_yt_dlp_picks(text: str, count: int) -> None:
    """`T247-R4`, second round: `1:-<400 nines>` is readable, its end is minus infinity as a
    `float`, and the bounded walk raised `OverflowError` taking its ceiling."""
    assert items_problem(text) is None
    assert item_positions(text, count) == yt_dlp_positions(text, count)


#: Endpoints far outside any playlist, each with a twin yt-dlp can afford to walk: congruent with
#: it modulo the step and outside the playlist on the same side, so on a short playlist the two
#: choose the same entries (`T247-R4`).
FAR: Final = (
    ("-10000000:3", "-100:3"),
    ("10000000:1:-1", "100:1:-1"),
    ("3:-10000000:-1", "3:-100:-1"),
    ("-7000073:9:7", "-73:9:7"),
    ("10000002:1:-5", "102:1:-5"),
    ("-1" + "0" * 100 + ":3", "-100:3"),
    ("1" + "0" * 100 + ":1:-1", "100:1:-1"),
    # Past a float in the direction yt-dlp walks forever (`T247-R4`, second round).
    ("-" + "9" * 400 + ":3", "-100:3"),
    ("-1:-" + "9" * 400 + ":-1", "-1:-100:-1"),
    (":-" + "9" * 400 + ":-1", ":-100:-1"),
    ("9" * 400 + "::-1", "100::-1"),
)


@pytest.mark.parametrize("count", COUNTS)
@pytest.mark.parametrize(("far", "near"), FAR)
def test_a_far_endpoint_picks_what_its_near_twin_picks_in_yt_dlp(
    far: str, near: str, count: int
) -> None:
    """**Bounded by the playlist, not by the number typed** (`T247-R4`). yt-dlp walks every index
    between the two ends, which on the GUI thread froze the add dialog for `-1000000000:3`; this
    has to reach the same entries without the walk, so the far text is checked against yt-dlp's
    answer for its walkable twin."""
    started = time.perf_counter()
    positions = item_positions(far, count)
    elapsed = time.perf_counter() - started

    assert positions == yt_dlp_positions(near, count)
    assert elapsed < 0.05, f"{far!r} took {elapsed:.3f} s on a playlist of {count}"


#: A number with more digits than Python will convert, in each place a number can stand.
UNREADABLE: Final = (
    "9" * 5000,
    "9" * 5000 + ":3",
    "1:" + "9" * 5000,
    "1:3:" + "9" * 5000,
)


@pytest.mark.parametrize("text", UNREADABLE, ids=["item", "start", "end", "step"])
def test_a_number_too_long_to_read_is_refused_rather_than_raised(text: str) -> None:
    """`T247-R2`. yt-dlp refuses the lone item; in a range it reads the number as absent, so
    `1:3:<5000 nines>` would mean `1:3` there. Refused here in every place instead, since a
    refusal the user can read beats a step that silently becomes one."""
    from yt_dlp.utils import PlaylistEntries

    assert items_problem(text) is not None
    with pytest.raises(ValueError):
        item_positions(text, 5)
    if ":" not in text:
        with pytest.raises(ValueError):
            list(PlaylistEntries.parse_playlist_items(text))


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
    # Far back and still a day (`T247-R2`'s control): about 1752.
    "today-100000days",
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


#: Relative dates before the first day a calendar can hold, or with a count too long to read.
TOO_FAR_BACK: Final = (
    "today-1000000days",
    "today-200000weeks",
    "today-99999999999months",
    "now-99999999999years",
    "today-" + "9" * 5000 + "days",
)


@pytest.mark.parametrize("text", TOO_FAR_BACK)
def test_a_date_too_far_back_is_refused_rather_than_raised(text: str) -> None:
    """`T247-R2`: `today-1000000days` raised `OverflowError` through the editor's accept and out
    of `settings.load`. yt-dlp cannot read these either; it raises."""
    from yt_dlp.utils import date_from_str

    with pytest.raises((ValueError, OverflowError)):
        date_from_str(text, strict=True)
    assert date_problem(text) == "That is further back than a calendar can name."
    with pytest.raises(ValueError):
        resolved_date(text)


def test_a_relative_date_resolves_against_the_day_it_is_asked_on() -> None:
    """The freezing half of the ruling: a preset keeps `today-2weeks`, a job keeps a day."""
    assert resolved_date("today-2weeks", date(2026, 10, 11)) == "20260927"
    assert resolved_date("today-1month", date(2026, 3, 31)) == "20260228"
    assert resolved_date("20260101", date(2030, 1, 1)) == "20260101"


def test_today_is_utc_s_today_as_yt_dlp_s_is() -> None:
    assert resolved_date("today") == datetime.now(UTC).strftime("%Y%m%d")


#: Sizes in every shape yt-dlp's `parse_bytes` reads, and some it does not (`T247-R3`).
SIZES: Final = (
    "1500",
    "50k",
    "50K",
    "44.6M",
    "2G",
    "2 G",
    "2g",
    "1T",
    "0",
    "0.4",
    "1.5",
    "2.5",
    "1.5k",
    "1 k",
    "1k ",
    "k",
    "1.",
    ".5M",
    "1e3",
    "2GiB",
    "2GB",
    "  2G",
    "-1M",
    "9" * 400 + "Y",
)


@pytest.mark.parametrize("text", SIZES)
def test_a_size_reads_as_yt_dlp_reads_it(text: str) -> None:
    """Bound to `parse_bytes` itself, the reader of `--min-filesize`. Where yt-dlp raises, for a
    number past a `float`, this reads nothing, which the editor refuses."""
    from yt_dlp.utils import parse_bytes

    try:
        theirs = parse_bytes(text)
    except OverflowError:
        theirs = None
    assert parsed_size(text) == theirs


@pytest.mark.parametrize("size", [1, 1023, 1024, 1500, 3 * 1024**3, 2**53 - 1, LARGEST_SIZE])
def test_a_size_is_shown_in_yt_dlp_s_grammar_and_reads_back_exactly(size: int) -> None:
    from yt_dlp.utils import parse_bytes

    shown = size_text(size)

    assert parsed_size(shown) == size
    assert parse_bytes(shown) == size, "yt-dlp reads the shown size differently"


@pytest.mark.parametrize(
    ("text", "refused"),
    [
        ("500M", False),
        ("8P", False),
        ("8.0000001P", True),
        ("0", True),
        ("0.4", True),
        ("2GB", True),
        ("9" * 400 + "Y", True),
    ],
)
def test_a_size_outside_what_a_filter_can_hold_is_refused(text: str, refused: bool) -> None:
    assert (size_problem(text) is not None) is refused, size_problem(text)
