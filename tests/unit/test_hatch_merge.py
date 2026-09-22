"""What the hatch's admitted options produce for `build_options` (`T-184`, `REQ-031`).

Admission is `tests/unit/test_extra_options.py`. This is the other half: the options a user was
allowed to type, turned into the keys the worker receives.

**The whole file is about `T184-R1`.** A merge derived from diffing the parse against the defaults
loses any explicit value that happens to equal a default, and yt-dlp does not read an absent key
as "the default" everywhere — `fragment_retries` absent becomes **zero** retries. So the merge
carries the destinations each named option touches, at whatever value the parse produced.
"""

from __future__ import annotations

from typing import Any

import pytest

from tracks_and_trails.downloader.extra_options import admit
from tracks_and_trails.downloader.option_table import OPTION_KEYS
from tracks_and_trails.downloader.ytdlp_adapter import (
    UnusableOptionsError,
    hatch_options,
    merge_thumbnail,
)


def hatch_for(text: str) -> dict[str, Any]:
    """What `text` contributes, paired with the argv admission produces from it.

    The two arguments must agree — `hatch_options` refuses them otherwise (`T184-R5`) — so the
    tests below pass the real pairing rather than inventing one.
    """
    return hatch_options(text, admit(text).accepted)


def test_an_explicit_value_equal_to_the_default_is_still_carried() -> None:
    """`T184-R1`, as the one case that makes the whole design necessary.

    `--fragment-retries 10` is what yt-dlp would have done anyway, so the parse produces exactly
    the default dictionary and a diff against it is **empty**. The key would then be absent, and
    `RetryManager(self.params.get('fragment_retries') or 0)` turns absent into zero: the user asks
    for ten retries and gets none. Carrying the destination regardless is the fix.
    """
    carried = hatch_for("--fragment-retries 10")

    assert carried == {"fragment_retries": 10}, (
        "an explicit value equal to the default was dropped, which is the defect T184-R1 names"
    )


def test_a_flag_whose_default_is_already_true_is_carried() -> None:
    """The same trap as a flag: `continuedl` is already true, so `--continue` diffs to nothing."""
    assert hatch_for("--continue") == {"continuedl": True}


def test_the_negation_carries_the_other_value() -> None:
    """And the pair is what makes the destination findable at all."""
    assert hatch_for("--no-continue") == {"continuedl": False}


def test_several_options_each_carry_their_own_destination() -> None:
    carried = hatch_for("--continue --concurrent-fragments 4")

    assert carried == {"continuedl": True, "concurrent_fragment_downloads": 4}


def test_nothing_typed_produces_nothing() -> None:
    """And without a parse: an empty field must not pay for importing yt-dlp's parser."""
    assert hatch_for("") == {}


def test_only_the_destinations_of_the_options_named_are_carried() -> None:
    """**Not everything that differs from the defaults.**

    Handing back the whole diff would let one option carry keys that belong to another, or to the
    parser's own defaults drifting between releases. The result is keyed on what the user actually
    named.
    """
    carried = hatch_for("--concurrent-fragments 4")

    assert set(carried) == set(OPTION_KEYS["--concurrent-fragments"])
    assert "continuedl" not in carried, "a key nobody asked for came along with the answer"


def test_the_equals_form_reaches_the_same_destination() -> None:
    """Admission keeps `--opt=value` as one word, so the merge has to read it as one."""
    assert hatch_for("--fragment-retries=7") == {"fragment_retries": 7}


def test_an_option_the_parser_refuses_stops_the_job_rather_than_running_it() -> None:
    """**Refusing loudly, which is `T184-R8`'s correction.**

    The first version returned `{}` here, so a job whose saved options no longer parse ran
    *without them* and reported success — the user's intent discarded in silence. Raising means
    the job fails with a reason, which is the honest answer when the options cannot be honoured.
    """
    with pytest.raises(UnusableOptionsError):
        hatch_options("--fragment-retries not-a-number", ("--fragment-retries", "not-a-number"))


def test_stored_options_that_the_audit_now_refuses_stop_the_job() -> None:
    """`T184-R5`, the Critical: stored values are re-admitted, never trusted.

    A preset is a file a user can edit and a request is a JSON blob in a database, so tokens can
    arrive that no dialog ever produced. The reviewer wrote `geo_bypass = true` into a preset by
    hand and watched it override the `False` this adapter sets under `SEC-003`.
    """
    with pytest.raises(UnusableOptionsError):
        hatch_options("--geo-bypass", ("--geo-bypass",))


def test_stored_tokens_that_disagree_with_their_text_stop_the_job() -> None:
    """The other half of `T184-R5`: the text a user was shown must be the text that runs."""
    with pytest.raises(UnusableOptionsError):
        hatch_options("--continue", ("--continue", "--fragment-retries", "10"))


def test_no_saved_token_is_repeated_in_the_reason() -> None:
    """`T184-R6`: a hatch token can be a credential, and this message reaches a log."""
    # A synthetic header, not a credential: `S105` flags the shape, and the shape is the point.
    canary = "Authorization: Bearer T184_CANARY"

    with pytest.raises(UnusableOptionsError) as refused:
        hatch_options("--continue", ("--add-headers", canary))

    assert "T184_CANARY" not in str(refused.value), f"a token reached the reason: {refused.value}"


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
