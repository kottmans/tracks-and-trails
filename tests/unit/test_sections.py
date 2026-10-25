"""The download sections' grammar, held to yt-dlp's own (`T-252`).

`core/sections.py` transcribes `parse_chapters` and `parse_duration` because `core/` may not import
yt-dlp and the check runs in the GUI process as the user types. A transcription is a second copy,
so these bind it to the pin: every spelling here, and a few hundred generated ones, is accepted by
the transcription exactly when `parse_options` accepts it, and means the same seconds.
"""

from __future__ import annotations

import math
import random
import re
from typing import Final

import pytest
from yt_dlp import parse_options
from yt_dlp.utils import parse_duration as yt_dlp_duration

from tracks_and_trails.core.sections import (
    FROM_URL,
    parse_duration,
    parsed_ranges,
    section_problem,
    sectioned_stem,
    sections_from_text,
    sections_problem,
    unsectioned_name,
    writes_several,
)

#: Durations in every form `parse_duration` knows, and some it does not.
DURATIONS: Final = (
    "10",
    "1:30",
    "01:02:03",
    "1:02:03:04",
    "1:30.5",
    "1:30:5",
    "1:2",
    "1:60",
    "61",
    "90s",
    "1h2m3s",
    "1h 2m",
    "1 hour",
    "2 hours",
    "1.5 hours",
    "90 minutes",
    "90 min.",
    "90 mins",
    "PT1H2M",
    "P1DT2H",
    "P",
    "3Z",
    "1d",
    "2 days 3 hours",
    "1y2m3w4d",
    "1.2.3 hours",
    "abc",
    "",
    " 5 ",
    "inf",
    "1:30:",
    ":30",
    "1.5",
    "5.",
)

#: Sections in each of the three forms, well and badly made.
SECTIONS: Final = (
    "*10-20",
    "*1:00-2:00",
    "*1:00-2:00,3:00-inf",
    "*1:00-2:00, 3:00 - 4:00",
    "*-30-inf",
    "*-30--10",
    "*0--10",
    "*0--inf",
    "*10-",
    "*-20",
    "*-",
    "*",
    "*,",
    "*abc-def",
    "*1h-2h",
    "*1:00-infinite",
    "* 1:00 - 2:00 ",
    "*1.2.3 hours-5",
    "*10-20,",
    "*90 minutes-2 hours",
    FROM_URL,
    "intro",
    "^Intro$",
    "(intro",
    "a{4294967296}",
    "[abc",
    "outro|credits",
)

#: Ranges yt-dlp accepts that end where or before they start: refused here, and only these. A
#: tuple, so every worker collects the same cases in the same order.
BACKWARDS: Final = ("*1:00-1:00", "*2:00-1:00", "*20-10")


def _yt_dlp_reads(section: str) -> tuple[bool, list[tuple[float, float]] | None]:
    """Whether `parse_options` accepts `section`, and the ranges it reads from it."""
    try:
        ranges = parse_options(["--download-sections", section]).ydl_opts["download_ranges"]
    except BaseException:
        return False, None
    return True, [tuple(span) for span in ranges.ranges]


@pytest.mark.parametrize("text", DURATIONS)
def test_a_duration_means_what_it_means_to_yt_dlp(text: str) -> None:
    try:
        theirs = yt_dlp_duration(text)
    except ValueError:
        theirs = None
    assert parse_duration(text) == theirs


def test_generated_durations_mean_what_they_mean_to_yt_dlp() -> None:
    """A few thousand strings over the grammar's own alphabet, seeded so a failure repeats."""
    pick = random.Random(252)  # noqa: S311 - a seeded fuzz, so a failure repeats
    alphabet = "0123456789:.hmsdPTZ ,"
    for _ in range(3000):
        text = "".join(pick.choice(alphabet) for _ in range(pick.randint(1, 9)))
        try:
            theirs = yt_dlp_duration(text)
        except ValueError:
            theirs = None
        assert parse_duration(text) == theirs, text


@pytest.mark.parametrize("section", [*SECTIONS, *BACKWARDS])
def test_a_section_is_refused_exactly_when_yt_dlp_refuses_it(section: str) -> None:
    accepted, theirs = _yt_dlp_reads(section)
    problem = section_problem(section)

    if section in BACKWARDS:
        assert accepted, "sanity: yt-dlp takes a backwards range"
        assert problem is not None and "ends before it starts" in problem
        return
    assert (problem is None) is accepted, problem
    if accepted and section.startswith("*") and section != FROM_URL:
        assert parsed_ranges(section) == theirs


#: A chapter pattern nested deeper than `re`'s parser goes, which raises `RecursionError` rather
#: than `re.error` (`T184-R8`); and one whose repeat count is past `re`'s limit, `OverflowError`.
TOO_DEEP: Final = "(" * 500 + "a" + ")" * 500
TOO_MANY: Final = "a{4294967296}"


@pytest.mark.parametrize(
    ("pattern", "raised"),
    [(TOO_DEEP, RecursionError), (TOO_MANY, OverflowError)],
    ids=["recursion", "overflow"],
)
def test_a_pattern_re_cannot_build_is_refused_rather_than_raised(
    pattern: str, raised: type[BaseException]
) -> None:
    """`T252-R4`: these were the hatch's cases until the sections had a control, and the move kept
    only the repeat count, so `RecursionError` could leave the handler with every test green."""
    with pytest.raises(raised):
        re.compile(pattern)  # the positive control: this pattern is the one that raises

    problem = section_problem(pattern)

    assert problem is not None and "is not a chapter pattern" in problem


def test_generated_ranges_are_read_as_yt_dlp_reads_them() -> None:
    """Generated `*` sections, compared range by range, backwards ones aside."""
    pick = random.Random(19)  # noqa: S311 - a seeded fuzz, so a failure repeats
    alphabet = "0123456789:.-,hmsinf "
    for _ in range(300):
        section = "*" + "".join(pick.choice(alphabet) for _ in range(pick.randint(1, 10)))
        accepted, theirs = _yt_dlp_reads(section)
        problem = section_problem(section)
        if problem is not None and "ends before it starts" in problem:
            assert accepted, section
            continue
        assert (problem is None) is accepted, (section, problem)
        if accepted:
            assert parsed_ranges(section) == theirs, section


def test_infinity_is_read_as_infinity() -> None:
    assert parsed_ranges("*10:00-inf") == [(600, math.inf)]
    assert parsed_ranges("*-30-inf") == [(-30, math.inf)]


def test_the_first_problem_is_said_and_none_when_all_are_usable() -> None:
    assert sections_problem(("intro", "*1-2")) is None
    assert sections_problem(("intro", "*abc", "(x")) == section_problem("*abc")


@pytest.mark.parametrize(
    ("text", "sections"),
    [
        ("intro\n*1:00-2:00\n", ("intro", "*1:00-2:00")),
        ("  intro  \n\n   \n*10-20", ("intro", "*10-20")),
        ("", ()),
    ],
)
def test_one_section_per_line_without_blank_lines(text: str, sections: tuple[str, ...]) -> None:
    assert sections_from_text(text) == sections


@pytest.mark.parametrize(
    ("sections", "several"),
    [
        (("*1:00-2:00",), False),
        ((FROM_URL,), False),
        (("*1:00-2:00,3:00-4:00",), True),
        (("*1:00-2:00", "*3:00-4:00"), True),
        (("*1:00-2:00", FROM_URL), True),
        # A chapter pattern can match any number of chapters.
        (("intro",), True),
        ((), False),
    ],
)
def test_whether_several_files_can_be_written(sections: tuple[str, ...], several: bool) -> None:
    assert writes_several(sections) is several


@pytest.mark.parametrize(
    ("name", "unsectioned"),
    [
        ("Clip (section 2).en.vtt", "Clip.en.vtt"),
        ("Clip (section 12).info.json", "Clip.info.json"),
        ("Clip.en.vtt", "Clip.en.vtt"),
        # Not a section suffix: the number is not a number, or the stem is another file's.
        ("Clip (section x).en.vtt", "Clip (section x).en.vtt"),
        ("Clipper (section 1).mp4", "Clipper (section 1).mp4"),
    ],
)
def test_a_sidecar_recorded_under_a_section_name_is_read_under_the_base(
    name: str, unsectioned: str
) -> None:
    assert unsectioned_name(name, "Clip") == unsectioned


def test_a_section_s_name_is_the_stem_and_its_number() -> None:
    assert sectioned_stem("Clip", 3) == "Clip (section 3)"
    assert unsectioned_name(sectioned_stem("Clip", 3) + ".mp4", "Clip") == "Clip.mp4"
