"""`T-254`: the *SponsorBlock (YouTube only)* group of the preset editor.

Ruled 2026-10-19 (`UX-015` amended, second; `ARC-010` amended, third): one row per category, each
left, marked as a chapter or cut out; while anything is marked, *Chapters* shows checked and cannot
be cleared; and the control says what turning it on sends (`T-254`'s criterion, `NFR-007`).
Driven through the editor's own buttons by object name.
"""

from collections.abc import Callable, Iterator
from dataclasses import replace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QRadioButton

from tracks_and_trails.core import presets as preset_registry
from tracks_and_trails.core.models import SPONSORBLOCK_CATEGORIES, SPONSORBLOCK_UNCUTTABLE, Preset
from tracks_and_trails.ui.options_dialog import (
    CHAPTERS_HELD_NOTE,
    EMBED_CHAPTERS_NAME,
    SPONSORBLOCK_NOTE,
    SPONSORBLOCK_NOTE_NAME,
    OptionsDialog,
    sponsorblock_name,
)

#: A preset marking one category and cutting two, *Chapters* on as the model requires.
SKIPPING = replace(
    preset_registry.BEST_VIDEO,
    name="Skipping",
    embed_chapters=True,
    sponsorblock_mark=("intro",),
    sponsorblock_remove=("sponsor", "selfpromo"),
)


@pytest.fixture
def editor(qapp: QApplication) -> Iterator[Callable[..., OptionsDialog]]:
    built: list[OptionsDialog] = []

    def build(preset: Preset | None = None, *, ffmpeg_available: bool = True) -> OptionsDialog:
        dialog = OptionsDialog(
            preset or preset_registry.BEST_VIDEO, ffmpeg_available=ffmpeg_available
        )
        built.append(dialog)
        return dialog

    yield build

    for dialog in built:
        dialog.close()
        dialog.deleteLater()
    qapp.processEvents()


def choice(dialog: OptionsDialog, category: str, which: str) -> QRadioButton:
    found = dialog.findChild(QRadioButton, sponsorblock_name(category, which))
    assert found is not None, f"no {which} for {category}"
    return found


def chapters(dialog: OptionsDialog) -> QCheckBox:
    found = dialog.findChild(QCheckBox, EMBED_CHAPTERS_NAME)
    assert found is not None
    return found


def test_every_category_is_left_marked_or_cut_and_two_cannot_be_cut(
    editor: Callable[..., OptionsDialog],
) -> None:
    """Eleven rows, as ruled; a highlight and a chapter title are not stretches to cut."""
    dialog = editor()

    for category in SPONSORBLOCK_CATEGORIES:
        assert choice(dialog, category, "leave").isChecked()
        assert not choice(dialog, category, "mark").isChecked()
        cut = dialog.findChild(QRadioButton, sponsorblock_name(category, "cut"))
        assert (cut is None) is (category in SPONSORBLOCK_UNCUTTABLE), category


def test_a_row_is_one_choice_and_the_rows_are_independent(
    editor: Callable[..., OptionsDialog],
) -> None:
    dialog = editor()

    choice(dialog, "sponsor", "cut").click()
    choice(dialog, "intro", "mark").click()
    choice(dialog, "sponsor", "mark").click()

    assert [choice(dialog, "sponsor", w).isChecked() for w in ("leave", "mark", "cut")] == [
        False,
        True,
        False,
    ]
    assert choice(dialog, "intro", "mark").isChecked()
    result = dialog.result_preset()
    assert result.sponsorblock_mark == ("sponsor", "intro")
    assert result.sponsorblock_remove == ()


def test_the_editor_opens_on_the_preset_s_own_and_gives_it_back(
    editor: Callable[..., OptionsDialog],
) -> None:
    dialog = editor(SKIPPING)

    assert choice(dialog, "intro", "mark").isChecked()
    assert choice(dialog, "sponsor", "cut").isChecked()
    assert choice(dialog, "selfpromo", "cut").isChecked()
    result = dialog.result_preset()
    assert (result.sponsorblock_mark, result.sponsorblock_remove) == (
        ("intro",),
        ("sponsor", "selfpromo"),
    )


def test_a_mark_holds_chapters_on_and_clearing_it_gives_them_back(
    editor: Callable[..., OptionsDialog],
) -> None:
    """**Ruling 2**: checked and held while anything is marked, and the user's own choice after."""
    dialog = editor()
    assert not chapters(dialog).isChecked() and chapters(dialog).isEnabled()

    choice(dialog, "intro", "mark").click()

    assert chapters(dialog).isChecked() and not chapters(dialog).isEnabled()
    assert chapters(dialog).accessibleDescription() == CHAPTERS_HELD_NOTE
    assert dialog.result_preset().embed_chapters is True

    choice(dialog, "intro", "leave").click()

    assert not chapters(dialog).isChecked() and chapters(dialog).isEnabled()
    assert dialog.result_preset().embed_chapters is False


def test_chapters_the_user_turned_on_stay_on_after_the_marks_go(
    editor: Callable[..., OptionsDialog],
) -> None:
    """The hold gives back the user's own choice, made before it, not the preset's."""
    dialog = editor()
    chapters(dialog).click()

    choice(dialog, "intro", "mark").click()
    choice(dialog, "intro", "leave").click()

    assert chapters(dialog).isChecked() and chapters(dialog).isEnabled()


def test_a_cut_alone_does_not_hold_chapters(editor: Callable[..., OptionsDialog]) -> None:
    dialog = editor()

    choice(dialog, "sponsor", "cut").click()

    assert chapters(dialog).isEnabled() and not chapters(dialog).isChecked()


def test_taking_the_marks_and_the_chapters_away_together_is_accepted(
    editor: Callable[..., OptionsDialog],
) -> None:
    """The model refuses a mark without chapters, so the two are set together, never in turn."""
    dialog = editor(SKIPPING)

    choice(dialog, "intro", "leave").click()
    chapters(dialog).click()

    result = dialog.result_preset()
    assert result.sponsorblock_mark == () and result.embed_chapters is False
    assert result.sponsorblock_remove == ("sponsor", "selfpromo")


def test_the_name_says_what_sponsorblock_does(editor: Callable[..., OptionsDialog]) -> None:
    dialog = editor()
    choice(dialog, "sponsor", "cut").click()

    assert dialog.result_preset().name == (
        "Best video available · SponsorBlock cutting out sponsored segments"
    )


def test_the_group_says_what_is_sent_and_to_whom(editor: Callable[..., OptionsDialog]) -> None:
    """**`T-254`'s criterion**: off by default, and the control says what enabling it sends."""
    dialog = editor()
    note = dialog.findChild(QLabel, SPONSORBLOCK_NOTE_NAME)

    assert note is not None and note.text() == SPONSORBLOCK_NOTE
    for words in ("sponsor.ajay.app", "first four characters", "Nothing is sent"):
        assert words in SPONSORBLOCK_NOTE
    assert "\u2014" not in SPONSORBLOCK_NOTE and "\u2013" not in SPONSORBLOCK_NOTE


def test_every_choice_names_its_category_and_takes_the_keyboard(
    editor: Callable[..., OptionsDialog],
) -> None:
    """`NFR-005`: each button says its row and its choice, so a screen reader needs no layout."""
    dialog = editor()

    for category in SPONSORBLOCK_CATEGORIES:
        for which in ("leave", "mark", "cut"):
            button = dialog.findChild(QRadioButton, sponsorblock_name(category, which))
            if button is None:
                continue
            name = button.accessibleName()
            assert ": " in name and button.text().lower() in name, name
            assert button.focusPolicy() & Qt.FocusPolicy.TabFocus, name
    names = {
        choice(dialog, category, "mark").accessibleName().split(":")[0]
        for category in SPONSORBLOCK_CATEGORIES
    }
    assert len(names) == len(SPONSORBLOCK_CATEGORIES)


def test_without_ffmpeg_only_leaving_is_offered_and_the_preset_s_own_is_kept(
    editor: Callable[..., OptionsDialog],
) -> None:
    dialog = editor(SKIPPING, ffmpeg_available=False)

    for category in SPONSORBLOCK_CATEGORIES:
        assert choice(dialog, category, "leave").isEnabled()
        assert not choice(dialog, category, "mark").isEnabled()
    assert dialog.result_preset().sponsorblock_remove == ("sponsor", "selfpromo")
