"""Which playlist entries are chosen (`REQ-004`, `T-110`), without a `QApplication`.

`ui/playlist_selection.py` is Qt-free for the reason `ui/staging.py` is: `REQ-004`'s two named
operations — **select-all** and **range selection** — are rules, and a rule asserted through a
table view is asserted through three other things at the same time. What the *widget* does with
these is `tests/ui/test_playlist_picker.py`; what the rules are is here.
"""

import pytest

from tracks_and_trails.core.models import PlaylistEntry
from tracks_and_trails.ui.playlist_selection import (
    GroupCheck,
    PlaylistSelection,
    describe_chosen,
    describe_playlist,
)


def entries(count: int) -> tuple[PlaylistEntry, ...]:
    return tuple(
        PlaylistEntry(url=f"https://example.invalid/{index}", title=f"Track {index}")
        for index in range(count)
    )


def test_a_freshly_probed_playlist_starts_with_everything_chosen() -> None:
    """**The default is the whole playlist**, and it is the default that makes doing nothing safe.

    `REQ-004` is about choosing *which* entries to enqueue. A user who never opens the picker has
    chosen the playlist, so starting empty would silently drop it — a wrong download reached by
    taking no action at all, which is the worst shape this task could have.
    """
    selection = PlaylistSelection.all_of(7)

    assert selection.chosen_count == 7
    assert selection.group_state is GroupCheck.ALL
    assert selection.chosen(entries(7)) == entries(7)


def test_select_all_recovers_everything_after_any_amount_of_unchecking() -> None:
    """`REQ-004`'s *select-all*, from the state a user is most likely to press it in."""
    selection = PlaylistSelection.all_of(5).clear().set(2, True)

    assert selection.select_all().chosen_count == 5
    assert selection.select_all().group_state is GroupCheck.ALL


def test_a_range_is_set_rather_than_inverted() -> None:
    """**One user action sets a run; it does not flip each member of it.**

    A loop of `toggle` over a mixed range comes out with a hole in it — entry 2 was already
    chosen, so inverting would *unchoose* it while the sweep chose its neighbours. That is a range
    selection that leaves the range in two states, which is not what one keystroke should mean.
    """
    selection = PlaylistSelection.none_of(6).set(2, True)

    swept = selection.set_many(range(1, 5), True)

    assert sorted(swept.checked) == [1, 2, 3, 4], (
        "the already-chosen entry inside the range came out unchosen: the range inverted"
    )


def test_unchecking_a_range_leaves_everything_outside_it_alone() -> None:
    selection = PlaylistSelection.all_of(6).set_many(range(1, 4), False)

    assert sorted(selection.checked) == [0, 4, 5]


def test_the_group_header_has_three_states_and_uses_all_of_them() -> None:
    """`P-5`: *a tri-state checkbox reflecting its members.*

    Three assertions rather than two, because *some* is the state a two-valued header would have
    to render as one of the others — and either rendering is a header lying about its members.
    """
    every = PlaylistSelection.all_of(4)

    assert every.group_state is GroupCheck.ALL
    assert every.clear().group_state is GroupCheck.NONE
    assert every.set(0, False).group_state is GroupCheck.SOME


def test_an_empty_playlist_is_not_all_chosen() -> None:
    """A header claiming everything is chosen above nothing is a sentence about nothing."""
    assert PlaylistSelection.all_of(0).group_state is GroupCheck.NONE
    assert describe_playlist(PlaylistSelection.all_of(0)) == "This playlist enumerated no entries."


def test_an_entry_the_playlist_does_not_have_is_refused_rather_than_ignored() -> None:
    """A selection that silently dropped an out-of-range index would enqueue a different set."""
    with pytest.raises(ValueError, match="does not have"):
        PlaylistSelection(count=3, checked=frozenset({0, 5}))


def test_a_selection_applied_to_the_wrong_entries_is_refused() -> None:
    """The positions belong to one extraction, and applying them to another is not a translation.

    A retry can return a playlist of a different length. Filtering seven positions through a tuple
    of five would enqueue items nobody looked at, which is exactly `REQ-004`'s failure mode.
    """
    with pytest.raises(ValueError, match="describes 7 entries and was given 5"):
        PlaylistSelection.all_of(7).chosen(entries(5))


def test_a_shorter_reprobe_starts_the_choice_again_rather_than_keeping_what_fits() -> None:
    """`with_count`: the honest answer to *"these positions no longer describe this playlist"*.

    Keeping whichever indices happen to still be in range would present a choice the user never
    made, over items they have not seen.
    """
    narrowed = PlaylistSelection.all_of(7).set_many((5, 6), False).with_count(3)

    assert narrowed == PlaylistSelection.all_of(3)
    assert PlaylistSelection.all_of(7).set(0, False).with_count(7).chosen_count == 6, (
        "a re-probe of the same length threw the choice away"
    )


def test_the_chosen_entries_keep_the_positions_they_hold_in_the_playlist() -> None:
    """`Job.playlist_index` means *where it sat in it*, and renumbering would make that false.

    A user who queues entries three and eight has queued entries three and eight. Handing the
    queue `0` and `1` would make its own record of the playlist disagree with the playlist.
    """
    every = entries(9)
    picked = PlaylistSelection.none_of(9).set_many((2, 7), True).chosen_with_index(every)

    assert picked == ((2, every[2]), (7, every[7]))


def test_the_chosen_entries_come_back_in_the_playlists_own_order() -> None:
    """A `frozenset` has no order, so the order has to come from the entries (`REQ-016` is later).

    Asserted with the indices supplied out of order, which is the only input that can fail it.
    """
    every = entries(5)
    picked = PlaylistSelection.none_of(5).set_many((4, 1, 3), True).chosen(every)

    assert picked == (every[1], every[3], every[4])


@pytest.mark.parametrize(
    ("selection", "expected"),
    [
        (PlaylistSelection.all_of(7), "all chosen"),
        (PlaylistSelection.none_of(7), "none chosen"),
        (PlaylistSelection.all_of(7).set(0, False), "6 chosen"),
        (PlaylistSelection.all_of(0), "no entries"),
    ],
)
def test_what_is_chosen_is_said_in_words(selection: PlaylistSelection, expected: str) -> None:
    """`NFR-005`: the state is in words, not only in how many boxes are ticked.

    **Never `6 of 7`.** `docs/UX_SPEC.md` §2 bans that shape — *a count is not a state* — and it
    reads as progress rather than as a choice.
    """
    assert describe_chosen(selection) == expected
    assert " of " not in describe_chosen(selection)


def test_the_summary_names_the_size_of_the_playlist_and_what_is_chosen() -> None:
    assert describe_playlist(PlaylistSelection.all_of(7)) == "7 entries · all chosen"
    assert describe_playlist(PlaylistSelection.all_of(1)) == "1 entry · all chosen"
    assert describe_playlist(PlaylistSelection.all_of(4).set(0, False)) == "4 entries · 3 chosen"


def test_a_selection_is_a_value_and_editing_one_does_not_edit_the_other() -> None:
    """Frozen, so the picker's copy and the row's committed copy cannot be the same object.

    `FormatSelection`'s reasoning, and the reason `MediaInfo` carries tuples: a mutable choice
    handed to two owners is a choice one of them can change behind the other's back.
    """
    original = PlaylistSelection.all_of(3)

    changed = original.set(1, False)

    assert original.chosen_count == 3, "the original was edited in place"
    assert changed.chosen_count == 2
    assert original != changed
