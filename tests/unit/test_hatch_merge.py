"""What the hatch's admitted options produce for `build_options` (`T-184`, `REQ-031`).

Admission is `tests/unit/test_extra_options.py`. This is the other half: the options a user was
allowed to type, turned into the keys the worker receives.

**The whole file is about `T184-R1`.** A merge derived from diffing the parse against the defaults
loses any explicit value that happens to equal a default, and yt-dlp does not read an absent key
as "the default" everywhere — `fragment_retries` absent becomes **zero** retries. So the merge
carries the destinations each named option touches, at whatever value the parse produced.
"""

from __future__ import annotations

import pytest

from tracks_and_trails.downloader.option_table import OPTION_KEYS
from tracks_and_trails.downloader.ytdlp_adapter import hatch_options, merge_thumbnail


def test_an_explicit_value_equal_to_the_default_is_still_carried() -> None:
    """`T184-R1`, as the one case that makes the whole design necessary.

    `--fragment-retries 10` is what yt-dlp would have done anyway, so the parse produces exactly
    the default dictionary and a diff against it is **empty**. The key would then be absent, and
    `RetryManager(self.params.get('fragment_retries') or 0)` turns absent into zero: the user asks
    for ten retries and gets none. Carrying the destination regardless is the fix.
    """
    carried = hatch_options(["--fragment-retries", "10"])

    assert carried == {"fragment_retries": 10}, (
        "an explicit value equal to the default was dropped, which is the defect T184-R1 names"
    )


def test_a_flag_whose_default_is_already_true_is_carried() -> None:
    """The same trap as a flag: `continuedl` is already true, so `--continue` diffs to nothing."""
    assert hatch_options(["--continue"]) == {"continuedl": True}


def test_the_negation_carries_the_other_value() -> None:
    """And the pair is what makes the destination findable at all."""
    assert hatch_options(["--no-continue"]) == {"continuedl": False}


def test_several_options_each_carry_their_own_destination() -> None:
    carried = hatch_options(["--continue", "--concurrent-fragments", "4"])

    assert carried == {"continuedl": True, "concurrent_fragment_downloads": 4}


def test_nothing_typed_produces_nothing() -> None:
    """And without a parse: an empty field must not pay for importing yt-dlp's parser."""
    assert hatch_options([]) == {}


def test_only_the_destinations_of_the_options_named_are_carried() -> None:
    """**Not everything that differs from the defaults.**

    Handing back the whole diff would let one option carry keys that belong to another, or to the
    parser's own defaults drifting between releases. The result is keyed on what the user actually
    named.
    """
    carried = hatch_options(["--concurrent-fragments", "4"])

    assert set(carried) == set(OPTION_KEYS["--concurrent-fragments"])
    assert "continuedl" not in carried, "a key nobody asked for came along with the answer"


def test_the_equals_form_reaches_the_same_destination() -> None:
    """Admission keeps `--opt=value` as one word, so the merge has to read it as one."""
    assert hatch_options(["--fragment-retries=7"]) == {"fragment_retries": 7}


def test_an_option_the_parser_refuses_adds_nothing_rather_than_raising() -> None:
    """A guard, not a route (`T184-R3`).

    Every option that exits or fails is refused before this runs, so reaching here means admission
    and the parser disagree — which a yt-dlp bump between the pin and the installed release would
    do. The worker is mid-job by then, and an option nobody can parse is not worth a crash.
    """
    assert hatch_options(["--fragment-retries", "not-a-number"]) == {}


# --- the shared key, ruled as a union -----------------------------------------------------------


@pytest.mark.parametrize(
    ("application", "user", "expected"),
    [
        # The application embeds, so it writes the picture; the user says nothing about it.
        ({"writethumbnail": True}, {}, True),
        # The user asks for the picture and the application did not want one.
        ({}, {"writethumbnail": True}, True),
        # Both ask. Still one thumbnail.
        ({"writethumbnail": True}, {"writethumbnail": True}, True),
        # **The user's no does not take away the application's need.** `--no-write-thumbnail`
        # against a job that embeds would otherwise leave `EmbedThumbnail` with nothing to embed,
        # which is `T-109`'s defect: a key accepted and silently ineffective.
        ({"writethumbnail": True}, {"writethumbnail": False}, True),
        # Neither wants it.
        ({}, {"writethumbnail": False}, False),
    ],
)
def test_the_thumbnail_is_written_when_either_side_asks(
    application: dict[str, object], user: dict[str, object], expected: bool
) -> None:
    """The `ARC-010` amendment of 2026-09-20, as its table.

    `ARC-010` §3 says the hatch may not override an application-owned key, and `writethumbnail` is
    one. The amendment says these two intents are not in conflict: the application writes the
    picture *in order to embed it*, and a user asking to keep it changes only the deletion. So the
    picture is written when either asks.
    """
    options = dict(application)

    merge_thumbnail(options, user)

    assert options["writethumbnail"] is expected


def test_a_user_who_says_nothing_leaves_the_key_untouched() -> None:
    """The application's own decision is not rewritten by a hatch that never mentioned it."""
    options: dict[str, object] = {}

    merge_thumbnail(options, {"continuedl": True})

    assert options == {}, "the merge invented a key from a field that did not name it"
