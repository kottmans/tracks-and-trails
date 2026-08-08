"""The playlist entry picker (`REQ-004`, `T-110`, `docs/UX_SPEC.md` §7).

**The entries come from a recorded probe, not from hand-built objects.** `REQ-004` is about the
entries *a playlist probe produces*, and a test that constructs its own `PlaylistEntry` list
answers a different question — the same reasoning `tests/ui/test_format_table.py` opens with.
`archive_org_art_of_war_playlist` is a real flat extraction of seven items with real titles and
durations, which is what `T-137` recorded it for.

The selection rules themselves are asserted without Qt in `tests/unit/test_playlist_selection.py`.
What is here is the **widget**: that the entries reach the table, that the checkboxes and the
tri-state header say what the selection says, and that every key `docs/UX_SPEC.md` §7 declares
actually does what it is declared to do without a pointer having been used first (`T-152`).
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from tracks_and_trails.core.models import MediaInfo, PlaylistEntry
from tracks_and_trails.downloader import ytdlp_adapter as adapter
from tracks_and_trails.ui.playlist_picker import (
    DURATION_COLUMN,
    INDEX_COLUMN,
    TITLE_COLUMN,
    PlaylistPicker,
)
from tracks_and_trails.ui.playlist_selection import PlaylistSelection

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
INFODICTS: Final = REPO_ROOT / "tests" / "fixtures" / "infodicts"

PLAYLIST: Final = "archive_org_art_of_war_playlist"


def recorded_entries() -> tuple[PlaylistEntry, ...]:
    """The seven entries a real flat extraction produced, through the real adapter."""
    payload = json.loads((INFODICTS / f"{PLAYLIST}.json").read_text(encoding="utf-8"))
    media = adapter.project_media(payload["info_dict"])
    assert isinstance(media, MediaInfo)
    assert media.entries, f"{PLAYLIST} records no entries to choose between"
    return media.entries


@pytest.fixture
def entries() -> tuple[PlaylistEntry, ...]:
    return recorded_entries()


@pytest.fixture
def picker(entries: tuple[PlaylistEntry, ...], qapp: QApplication) -> Iterator[PlaylistPicker]:
    widget = PlaylistPicker(entries)
    yield widget
    widget.deleteLater()
    qapp.processEvents()


def checked_rows(picker: PlaylistPicker) -> list[int]:
    """Which rows the **model** says are checked, read the way Qt reads them.

    Through `CheckStateRole` rather than through `picker.selection`, deliberately: the selection
    value is asserted directly in the unit tests, and what is unproven here is that Qt is told the
    same thing. `T-109` found a control that held the right value and answered the wrong one.
    """
    model = picker.model
    return [
        row
        for row in range(model.rowCount())
        if model.data(model.index(row, INDEX_COLUMN), Qt.ItemDataRole.CheckStateRole)
        is Qt.CheckState.Checked
    ]


def cell(picker: PlaylistPicker, row: int, column: int) -> str:
    return str(picker.model.data(picker.model.index(row, column), Qt.ItemDataRole.DisplayRole))


def walk_to(picker: PlaylistPicker, row: int) -> None:
    """Move the current row by pressing `↓`, which is how a user gets there.

    Not `setCurrentIndex`: Qt anchors a `Shift`+`↓` extension on the position the selection was
    last *set* from, so a run seeded programmatically extends from wherever that position happens
    to be — row 0 in a table that has never been laid out. A test built on that anchor asserts
    something no keyboard can produce, and it changes answer depending on whether the widget was
    shown, which is how the first version of these two tests passed alone and failed in the file.
    """
    assert picker.table.currentIndex().row() == 0, "the picker did not open on its first row"
    for _ in range(row):
        QTest.keyClick(picker.table, Qt.Key.Key_Down)
    assert picker.table.currentIndex().row() == row


# --- what the picker shows ---------------------------------------------------------------------


def test_the_picker_lists_every_entry_with_enough_to_choose_by(
    picker: PlaylistPicker, entries: tuple[PlaylistEntry, ...]
) -> None:
    """`T-110`'s first criterion: *title, duration, index*, from the probe.

    Asserted by value against the recording rather than against a shape, because "lists its
    entries" is a claim about the entries and not about the row count.
    """
    assert picker.model.rowCount() == len(entries) == 7

    assert cell(picker, 0, INDEX_COLUMN) == "1", "the index is not the position a user reads"
    assert cell(picker, 0, TITLE_COLUMN) == entries[0].title
    assert cell(picker, 0, DURATION_COLUMN) == "8:27", (
        "the duration is not the one the extraction recorded, formatted the way the rest of the "
        "window formats one"
    )
    assert [cell(picker, row, TITLE_COLUMN) for row in range(7)] == [e.title for e in entries]


def test_an_entry_with_no_duration_says_so_rather_than_showing_zero(qapp: QApplication) -> None:
    """`format_duration`'s rule, reached through this table: `None` is unknown, not zero."""
    widget = PlaylistPicker((PlaylistEntry(url="https://example.invalid/x", title="No duration"),))
    try:
        assert cell(widget, 0, DURATION_COLUMN) == "Unknown"
    finally:
        widget.deleteLater()
        qapp.processEvents()


def test_the_picker_opens_with_everything_chosen(picker: PlaylistPicker) -> None:
    """The default the dialog depends on: an unopened picker enqueues the whole playlist."""
    assert checked_rows(picker) == list(range(7))
    assert picker.group_control.checkState() is Qt.CheckState.Checked
    assert picker.summary_text() == "7 entries · all chosen"


def test_the_picker_opens_on_a_current_row(picker: PlaylistPicker) -> None:
    """`T-152`: a declared keyboard route that needs a click first is not a route.

    `Space` toggles *the current entry*, so there has to be a current entry before anything has
    been clicked or the first key press does nothing.
    """
    assert picker.table.currentIndex().isValid(), "the table opened with no current row"
    assert picker.table.currentIndex().row() == 0


# --- REQ-004's two named operations, from the keyboard ------------------------------------------


def test_space_toggles_the_current_entry(picker: PlaylistPicker) -> None:
    """`docs/UX_SPEC.md` §7's own keyboard row, pressed rather than called.

    `QTest.keyClick` on the table is the user's gesture; calling the model's method would prove
    the method works and say nothing about whether the key reaches it.
    """
    picker.table.setCurrentIndex(picker.model.index(3, INDEX_COLUMN))

    QTest.keyClick(picker.table, Qt.Key.Key_Space)

    assert 3 not in checked_rows(picker), "Space did not uncheck the current entry"
    assert len(checked_rows(picker)) == 6

    QTest.keyClick(picker.table, Qt.Key.Key_Space)

    assert checked_rows(picker) == list(range(7)), "Space did not put it back"


def test_ctrl_a_chooses_every_entry_rather_than_only_highlighting_them(
    picker: PlaylistPicker,
) -> None:
    """`REQ-004`'s **select-all** is about what gets enqueued, not about what is highlighted.

    Qt's own `Ctrl`+`A` selects rows and changes no check state, which would satisfy the key in
    the spec's table and none of the requirement behind it.
    """
    picker.model.clear_selection()
    assert checked_rows(picker) == []

    QTest.keyClick(picker.table, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)

    assert checked_rows(picker) == list(range(7))
    assert picker.group_control.checkState() is Qt.CheckState.Checked


def test_shift_arrow_extends_a_range_and_space_sets_the_whole_of_it(
    picker: PlaylistPicker,
) -> None:
    """`REQ-004`'s **range selection**, both halves of it, from the keyboard alone (`NFR-005`).

    `Shift`+`↓` builds the run — Qt's `ExtendedSelection`, which is the platform convention
    `docs/UX_SPEC.md` §7 says it is transcribing — and `Space` sets it. Asserted as *three rows
    changed by one press*, because a `Space` that acted on the current row alone would leave the
    other two and make the declared range key do nothing observable.

    **Driven the way a keyboard user gets there**: `↓` to move, then `Shift`+`↓` to extend. Qt
    anchors a shift-extend on the last position the selection was set from, so seeding the run by
    calling `selectRow` instead of pressing keys tests an anchor no user can produce.
    """
    walk_to(picker, 3)

    for _ in range(2):
        QTest.keyClick(picker.table, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    QTest.keyClick(picker.table, Qt.Key.Key_Space)

    assert checked_rows(picker) == [0, 1, 2, 6], (
        "the swept range 3..5 was not unchosen together; the range key or the toggle acted on one "
        "row"
    )


def test_a_mixed_range_is_chosen_rather_than_inverted(picker: PlaylistPicker) -> None:
    """One keystroke leaves the run in one state — see `PlaylistSelection.set_many`.

    Entry 4 starts unchosen inside a run of chosen ones. A `Space` that looped `toggle` over the
    selection would come out with 3 and 5 unchosen and **4 chosen** — the range left in two states
    by one keystroke. Setting the run leaves all three the same, and *chosen* is the direction,
    because "not every member is chosen" is what makes the press mean *choose these*.
    """
    picker.model.set_checked((4,), False)
    walk_to(picker, 3)
    for _ in range(2):
        QTest.keyClick(picker.table, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)

    QTest.keyClick(picker.table, Qt.Key.Key_Space)

    assert checked_rows(picker) == list(range(7)), (
        "the mixed range 3..5 did not come out uniformly chosen: it inverted"
    )

    QTest.keyClick(picker.table, Qt.Key.Key_Space)

    assert checked_rows(picker) == [0, 1, 2, 6], "the now-uniform range did not unchoose together"


def test_space_with_nothing_selected_acts_on_the_current_row(picker: PlaylistPicker) -> None:
    """Where a keyboard user actually arrives: focus does not select.

    Without the fallback the first `Space` after tabbing into the table would do nothing at all,
    which reads as a dead key rather than as a picker.
    """
    picker.table.clearSelection()
    picker.table.setCurrentIndex(picker.model.index(5, INDEX_COLUMN))

    QTest.keyClick(picker.table, Qt.Key.Key_Space)

    assert 5 not in checked_rows(picker)
    assert len(checked_rows(picker)) == 6


def test_tab_leaves_the_table_rather_than_walking_its_cells() -> None:
    """`T107-R3` one surface over: a view that eats `Tab` traps the keyboard on itself."""
    widget = PlaylistPicker(recorded_entries())
    try:
        assert not widget.table.tabKeyNavigation()
        assert widget.focus_chain() == [widget.group_control, widget.table]
    finally:
        widget.deleteLater()
        QApplication.processEvents()


# --- P-5: the tri-state group header ------------------------------------------------------------


def test_the_group_header_reflects_its_members(picker: PlaylistPicker) -> None:
    """`P-5`, in all three states, read off the widget Qt would draw."""
    assert picker.group_control.checkState() is Qt.CheckState.Checked

    picker.model.set_checked((0,), False)
    assert picker.group_control.checkState() is Qt.CheckState.PartiallyChecked, (
        "a partly chosen playlist drew a header claiming all or none of it"
    )

    picker.model.clear_selection()
    assert picker.group_control.checkState() is Qt.CheckState.Unchecked


def test_clicking_the_group_header_chooses_or_unchooses_every_entry(
    picker: PlaylistPicker,
) -> None:
    """*Add to queue commits only the checked entries*, so the header has to reach all of them."""
    picker.group_control.click()

    assert checked_rows(picker) == [], "the header did not unchoose its members"

    picker.group_control.click()

    assert checked_rows(picker) == list(range(7))


def test_the_partly_filled_header_resolves_to_all_rather_than_cycling_through_it(
    picker: PlaylistPicker,
) -> None:
    """A click on a partial header means *choose everything*, and the next means *nothing*.

    `setTristate` would put "partially checked" into the cycle a click walks, so a user would need
    three presses to get from *some* to *none* and the middle one would mean nothing at all.
    """
    picker.model.set_checked((3,), False)
    assert picker.group_control.checkState() is Qt.CheckState.PartiallyChecked

    picker.group_control.click()
    assert checked_rows(picker) == list(range(7))

    picker.group_control.click()
    assert checked_rows(picker) == []


# --- NFR-005: what a screen reader is told ------------------------------------------------------


def test_every_entry_announces_whether_it_is_chosen(picker: PlaylistPicker) -> None:
    """`NFR-005`: a tick is a colour and a shape, and neither is a sentence.

    Asserted on the **title** column, which is where a screen-reader user reading down the list
    is, and where the check state of a cell in another column would never be announced.
    """
    spoken = picker.model.data(
        picker.model.index(0, TITLE_COLUMN), Qt.ItemDataRole.AccessibleTextRole
    )
    assert "chosen" in spoken and picker.model.entries[0].title in spoken

    picker.model.set_checked((0,), False)
    spoken = picker.model.data(
        picker.model.index(0, TITLE_COLUMN), Qt.ItemDataRole.AccessibleTextRole
    )
    assert "not chosen" in spoken


def test_the_summary_says_what_will_be_added_in_words(picker: PlaylistPicker) -> None:
    picker.model.set_checked((0, 1), False)

    assert picker.summary_text() == "7 entries · 5 chosen"
    assert picker.accessibleDescription() == picker.summary_text()


# --- the seam the dialog consumes ----------------------------------------------------------------


def test_every_change_is_announced_to_whoever_embeds_the_picker(picker: PlaylistPicker) -> None:
    """The dialog writes the choice onto the staging row from this signal.

    Emitted for every route, because a route that changes the selection and stays silent is a
    choice the row never hears about — and Add would then queue what the picker was opened with.
    """
    seen: list[PlaylistSelection] = []
    picker.selection_changed.connect(lambda selection: seen.append(selection))

    QTest.keyClick(picker.table, Qt.Key.Key_Space)
    picker.group_control.click()
    picker.group_control.click()
    QTest.keyClick(picker.table, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)

    # Six, then the partly filled header resolving to all, then none, then select-all. The
    # keyboard and the pointer both reach the dialog through this one signal.
    assert [selection.chosen_count for selection in seen] == [6, 7, 0, 7]


def test_a_click_on_a_checkbox_is_taken_as_a_choice(picker: PlaylistPicker) -> None:
    """**Qt hands `setData` an `int`, not a `Qt.CheckState`** — `T-109`'s defect, one model over.

    An `is Qt.CheckState.Checked` comparison there is always false, and the box would tick on
    screen while the selection never changed: a control that looks like a choice and converts
    nothing.
    """
    index = picker.model.index(2, INDEX_COLUMN)

    assert picker.model.setData(
        index, int(Qt.CheckState.Unchecked.value), Qt.ItemDataRole.CheckStateRole
    )
    assert 2 not in checked_rows(picker)

    assert picker.model.setData(
        index, int(Qt.CheckState.Checked.value), Qt.ItemDataRole.CheckStateRole
    )
    assert 2 in checked_rows(picker)


def test_a_picker_opened_on_an_existing_selection_shows_it(
    entries: tuple[PlaylistEntry, ...], qapp: QApplication
) -> None:
    """Reopening a row must show what was chosen, not start again.

    `P-19` makes the picker a row that opens and closes; a picker that reset every time would
    discard the choice on the first `←`.
    """
    widget = PlaylistPicker(entries, PlaylistSelection.none_of(len(entries)).set_many((1, 4), True))
    try:
        assert checked_rows(widget) == [1, 4]
        assert widget.group_control.checkState() is Qt.CheckState.PartiallyChecked
    finally:
        widget.deleteLater()
        qapp.processEvents()
