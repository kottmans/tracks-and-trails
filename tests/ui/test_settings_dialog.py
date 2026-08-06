"""The Settings screen and its one control (`REQ-023`, `T-170`).

**Most of this file is `T-144`'s clear-history suite, moved with the action it tests.** That task
built a visible, keyboard-reachable route to emptying the list, a confirmation naming its own count,
and a promise that files are kept — and `DAT-005` §4 ruled on the wording. `T-169` took the list
away; none of those four properties went with it, because they are about **emptying records**, which
is still something a user can do.

What changed is the noun. `DAT-005`'s 2026-08-06 amendment renamed the verb to *Clear download
records*, on its own §1 reasoning: *history* named a visible list and now names a feature the user
cannot see, while *records* names what is actually emptied.
"""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from tracks_and_trails.ui.main_window import MainWindow
from tracks_and_trails.ui.settings_dialog import (
    CLEAR_RECORDS_LABEL,
    RECORDS_KEEP_FILES,
    SettingsDialog,
    clear_records_question,
)


class _LedgerOf:
    """A ledger holding `held` records, and nothing else a screen with no list could ask."""

    def __init__(self, held: int) -> None:
        self.held = held

    def count(self) -> int:
        return self.held


@pytest.fixture
def dialogs(qapp: QApplication) -> object:
    """Builds dialogs and destroys them, so no widget outlives the test that made it."""
    built: list[SettingsDialog] = []

    def build(held: int, on_clear: object = None) -> SettingsDialog:
        dialog = SettingsDialog(
            records=_LedgerOf(held),
            on_clear_records=on_clear or (lambda: None),  # type: ignore[arg-type]
        )
        built.append(dialog)
        return dialog

    yield build

    for dialog in built:
        dialog.close()
        dialog.deleteLater()
    qapp.processEvents()


def test_the_question_names_its_count_and_never_says_all_alone() -> None:
    """`DAT-005` §4, and the wording its amendment ruled on.

    That entry refused *Clear all* partly because the phrase *"is the phrasing most likely to be
    read as deleting downloads"* — *all* has no object, so the user supplies one, and the one they
    have in mind is their files. The question names **records**, so there is no gap to fill.

    The count is grouped because this is the number a user has not been keeping: `1,284` is a
    quantity to feel where `1284` is a number to read.
    """
    assert clear_records_question(1) == "Clear the one download record?"
    assert clear_records_question(1284) == "Clear all 1,284 download records?"
    assert "records?" not in clear_records_question(1), (
        "the singular case reads as a plural, which is how a user learns the message is generated"
    )


def test_clearing_is_confirmed_with_its_count_and_the_file_promise(dialogs) -> None:  # type: ignore[no-untyped-def]
    """The criterion: the confirmation names its own count **and** says the files are kept.

    `RECORDS_KEEP_FILES` is one constant so the section's explanation and the confirmation cannot
    come to disagree — and the confirmation is the moment it matters most, because it is the moment
    the records go.
    """
    cleared: list[bool] = []
    dialog = dialogs(3, lambda: cleared.append(True))

    for button, expected in (
        (QMessageBox.StandardButton.Cancel, []),
        (QMessageBox.StandardButton.Yes, [True]),
    ):
        confirm = dialog.clear_records_asked_for()
        assert isinstance(confirm, QMessageBox)
        try:
            assert "3 download records" in confirm.text(), f"the question reads {confirm.text()!r}"
            assert confirm.informativeText() == RECORDS_KEEP_FILES, (
                "clearing does not say the files are safe, which is the one thing a user emptying "
                "their records needs to know"
            )
            assert confirm.defaultButton() == confirm.button(QMessageBox.StandardButton.Cancel), (
                "the default button clears; an irreversible action's default should do nothing"
            )
            confirm.button(button).click()
        finally:
            confirm.close()
        assert cleared == expected, f"{button} produced {cleared}"


def test_clearing_an_empty_ledger_asks_nothing(dialogs) -> None:  # type: ignore[no-untyped-def]
    """`UX-005` §5: nothing is offered that would be refused.

    *Clear 0 download records?* is a question with no answer worth giving, and a confirmation that
    appears for it teaches the user that the dialog is noise. The button is disabled too, which is
    the half a user sees before they click.
    """
    cleared: list[bool] = []
    dialog = dialogs(0, lambda: cleared.append(True))

    button = dialog.findChild(QPushButton, "clearRecordsButton")
    assert button is not None
    assert not button.isEnabled(), "an empty ledger still offers a verb that would do nothing"
    assert dialog.clear_records_asked_for() is None
    assert cleared == []


def test_the_route_is_visible_and_says_what_it_empties(dialogs) -> None:  # type: ignore[no-untyped-def]
    """The criterion `T-144` set: a **visible** route that names what it empties.

    Bulk removal existed before `T-144` and could only be reached by dragging a selection — *a
    route nobody can find is the same as no route*. The route is now a Settings screen, and what
    survives the move is that the verb names its object and the promise travels with it.
    """
    dialog = dialogs(2)
    button = dialog.findChild(QPushButton, "clearRecordsButton")

    assert button is not None, "the screen offers no route to clear the records at all"
    assert button.isEnabled()
    assert button.text() == CLEAR_RECORDS_LABEL
    assert "record" in button.text().lower(), (
        f"the verb reads {button.text()!r}; DAT-005's amendment rules that it names what it "
        "empties, because 'Clear all' has no object and the user supplies one"
    )
    assert "not deleted" in (button.accessibleDescription() or "").lower(), (
        "a screen-reader user is not told that the files are kept, which is the sentence a "
        "hesitating user needs (NFR-005, DAT-005 §3)"
    )


def test_the_window_opens_settings_and_only_when_it_has_a_ledger(
    qapp: QApplication, tmp_path: Path
) -> None:
    """The menu route, and composition's all-or-nothing rule (`T-170`).

    A window given no ledger offers a disabled action and opens nothing — the same shape as the
    add-URL action, which is enabled only when it has all three of its collaborators.
    """
    bare = MainWindow(tmp_path / "geometry.toml")
    try:
        assert bare.settings_action is not None, "the window has no Settings route at all"
        assert not bare.settings_action.isEnabled(), (
            "a window with no ledger offers Settings, whose only control it cannot serve"
        )
        assert bare.open_settings() is None
    finally:
        bare.close()
        bare.deleteLater()

    wired = MainWindow(
        tmp_path / "geometry.toml",
        records=_LedgerOf(4),
        on_clear_records_requested=lambda: None,
    )
    try:
        assert wired.settings_action is not None and wired.settings_action.isEnabled()
        assert "&" in wired.settings_action.text(), (
            "the action has no mnemonic, so the only way to reach it is with a pointer"
        )
        opened = wired.open_settings()
        assert isinstance(opened, SettingsDialog)
        opened.close()
    finally:
        wired.close()
        wired.deleteLater()
    qapp.processEvents()
