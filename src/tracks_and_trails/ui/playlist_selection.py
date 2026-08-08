"""Which entries of a probed playlist the user has chosen (`REQ-004`, `T-110`).

**Qt-free on purpose**, for the reason `ui/staging.py` and `ui/format_selection.py` are: the rules
below are what `REQ-004` actually asks for — *select-all and range selection* — and they are worth
asserting without a `QApplication`, an event loop and a table view standing between the assertion
and the rule.

## A value, not a widget's state

`PlaylistSelection` is frozen and every operation returns a new one. The picker holds the current
value and the staging row holds the committed one, and neither can edit the other's copy by
accident — the same reasoning `FormatSelection` was built on, and the same reason `MediaInfo`
carries tuples rather than lists.

## Nothing here is persisted

`UX_SPEC` §7: *"Unchecked entries are **not** queued and not remembered. Nothing is persisted until
Add is pressed (`UX-003`), so there is no state to keep."* This type therefore describes a choice
that lives exactly as long as the add dialog does, which is why it holds indices into one probe's
entry tuple rather than URLs or ids.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Self


class GroupCheck(StrEnum):
    """What the group header's tri-state checkbox says about its members (`P-5`).

    A three-valued answer rather than a `bool` and a flag, because *some* is a state the header
    genuinely has and a two-valued answer would have to render it as one of the other two — which
    is a header claiming every entry is chosen while four of seven are.

    Mapped to `Qt.CheckState` by the widget rather than being one, so this module stays Qt-free.
    """

    ALL = "all"
    SOME = "some"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class PlaylistSelection:
    """The checked entries of one probed playlist, by position.

    **By position, and the positions are the probe's own.** An entry has no stable identity across
    probes — `PlaylistEntry` carries a URL and a title and a flat extraction may report the same
    URL twice — so a selection is only meaningful against the tuple it was made from. `count` is
    kept beside the indices so a mismatch is detectable rather than silently dropping entries off
    the end, which is what a bare set of indices would do.
    """

    count: int
    checked: frozenset[int] = frozenset()

    def __post_init__(self) -> None:
        if self.count < 0:
            raise ValueError(f"a playlist cannot have {self.count} entries")
        stray = sorted(index for index in self.checked if not 0 <= index < self.count)
        if stray:
            raise ValueError(
                f"selection names entries {stray} that a playlist of {self.count} does not have"
            )

    @classmethod
    def all_of(cls, count: int) -> Self:
        """Every entry chosen — **the state a freshly probed playlist starts in**.

        `REQ-004` is about *choosing* which entries to enqueue, and the choice a user who never
        opens the picker has made is *the playlist*. Starting empty would make an unopened picker
        silently drop the whole thing, which is a wrong download reached by doing nothing.
        """
        return cls(count=count, checked=frozenset(range(count)))

    @classmethod
    def none_of(cls, count: int) -> Self:
        return cls(count=count, checked=frozenset())

    def is_checked(self, index: int) -> bool:
        return index in self.checked

    def toggle(self, index: int) -> Self:
        """Flip one entry. An index the playlist does not have is refused, not ignored."""
        return self.set(index, not self.is_checked(index))

    def set(self, index: int, checked: bool) -> Self:
        return self.set_many((index,), checked)

    def set_many(self, indices: Iterable[int], checked: bool) -> Self:
        """Check or uncheck a set of entries in one step — `REQ-004`'s *range selection*.

        One operation rather than a loop of `toggle` because a range is one user action: toggling
        each member of a mixed range would invert it rather than set it, so a range containing one
        already-checked entry would come out with a hole in it.
        """
        wanted = frozenset(indices)
        updated = self.checked | wanted if checked else self.checked - wanted
        return replace(self, checked=updated)

    def select_all(self) -> Self:
        """`REQ-004`'s *select-all*."""
        return replace(self, checked=frozenset(range(self.count)))

    def clear(self) -> Self:
        return replace(self, checked=frozenset())

    @property
    def group_state(self) -> GroupCheck:
        """What the tri-state header reads (`P-5`).

        An empty playlist answers `NONE` rather than `ALL`: a header claiming everything is chosen
        above a list with nothing in it is a sentence about entries that do not exist.
        """
        if not self.checked:
            return GroupCheck.NONE
        return GroupCheck.ALL if len(self.checked) == self.count else GroupCheck.SOME

    @property
    def chosen_count(self) -> int:
        return len(self.checked)

    @property
    def is_empty(self) -> bool:
        """Nothing is chosen, so this playlist would contribute no jobs."""
        return not self.checked

    def chosen_with_index[T](self, entries: Sequence[T]) -> tuple[tuple[int, T], ...]:
        """The checked entries **with the positions they hold in the playlist**, in order.

        The position is carried rather than re-derived because it is what `Job.playlist_index`
        means — *"where it sat in it"* — and a user who queues entries three and eight has queued
        entries three and eight, not entries one and two. Renumbering would make the queue's own
        record of a playlist disagree with the playlist.

        Refuses a sequence this selection was not made against. A selection of seven applied to a
        tuple of five would quietly enqueue a different set of items than the one on screen, which
        is the class of defect `REQ-004` exists to prevent rather than to introduce.
        """
        if len(entries) != self.count:
            raise ValueError(
                f"selection describes {self.count} entries and was given {len(entries)}"
            )
        return tuple((index, entry) for index, entry in enumerate(entries) if index in self.checked)

    def chosen[T](self, entries: Sequence[T]) -> tuple[T, ...]:
        """`entries` filtered to the checked ones, **in the playlist's own order**."""
        return tuple(entry for _index, entry in self.chosen_with_index(entries))

    def with_count(self, count: int) -> Self:
        """This selection re-made against a playlist of `count` entries.

        A fresh probe replaces the entries, and the honest answer for a set of positions that no
        longer describes them is to start again rather than to keep whichever indices happen to
        still be in range.
        """
        return self if count == self.count else type(self).all_of(count)


def describe_chosen(selection: PlaylistSelection) -> str:
    """How much of a playlist is chosen, in words (`NFR-005`).

    **One author for the phrase**, because the staging row's detail line, the picker's summary and
    the accessible description all say it and three copies of a sentence is how they come to
    disagree — `T118-R8` twice over.

    Never `4 of 7`: `UX_SPEC` §2's rule is that a count is not a state, and the shape it bans is
    the one that reads as progress. What is chosen is a choice, and it is said as one.
    """
    if selection.count == 0:
        return "no entries"
    state = selection.group_state
    if state is GroupCheck.ALL:
        return "all chosen"
    if state is GroupCheck.NONE:
        return "none chosen"
    return f"{selection.chosen_count} chosen"


def describe_playlist(selection: PlaylistSelection) -> str:
    """The picker's own summary line: how many entries there are, and how many are chosen."""
    if selection.count == 0:
        return "This playlist enumerated no entries."
    noun = "entry" if selection.count == 1 else "entries"
    return f"{selection.count} {noun} · {describe_chosen(selection)}"
