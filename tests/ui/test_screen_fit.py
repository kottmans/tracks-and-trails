"""Dialogs open inside the screen's working area, title bar included (`ui/screen_fit.py`).

Reported from a Windows laptop at 125%: *Add URLs* and *Preferences* opened with their title bars
above the screen. The Windows measurement is in the module docstring; these are the offscreen
halves of it. The offscreen platform draws no frame, so the frame and client rectangles coincide
here, and `fitted_geometry` is tested with a frame of its own for that part.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QRect, QSize, Qt
from PySide6.QtWidgets import QApplication, QDialog, QPlainTextEdit, QVBoxLayout, QWidget

from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.ui import add_dialog as add_dialog_module
from tracks_and_trails.ui.add_dialog import AddUrlDialog
from tracks_and_trails.ui.screen_fit import (
    WINDOW_CHROME,
    DialogsOnScreen,
    fitted_geometry,
    keep_dialogs_on_screen,
)

#: A Windows-sized frame: 8-pixel borders and a 31-pixel title bar.
LEFT, TOP, RIGHT, BOTTOM = 8, 31, 8, 8
SCREEN = QRect(0, 0, 1536, 912)


def _frame_around(client: QRect) -> QRect:
    return QRect(
        client.x() - LEFT,
        client.y() - TOP,
        client.width() + LEFT + RIGHT,
        client.height() + TOP + BOTTOM,
    )


def _frame_inside(client: QRect) -> bool:
    frame = _frame_around(client)
    return SCREEN.contains(frame.topLeft()) and SCREEN.contains(frame.bottomRight())


def test_a_dialog_placed_above_the_screen_is_moved_down_to_show_its_title_bar() -> None:
    """The report itself: the frame began above the top, so the title bar could not be reached."""
    client = QRect(400, -200, 650, 788)

    fitted = fitted_geometry(client, _frame_around(client), SCREEN)

    assert fitted is not None
    assert fitted.size() == client.size(), "a dialog that fits in height was resized"
    assert _frame_around(fitted).top() == SCREEN.top()
    assert _frame_inside(fitted)


def test_a_dialog_taller_than_the_working_area_is_shrunk_to_fit_with_its_frame() -> None:
    """Shrunk so the **frame** fits, not the client: the title bar is height too."""
    client = QRect(300, 60, 650, 1400)

    fitted = fitted_geometry(client, _frame_around(client), SCREEN)

    assert fitted is not None
    assert fitted.height() == SCREEN.height() - TOP - BOTTOM
    assert _frame_inside(fitted)


@pytest.mark.parametrize(
    "client",
    [QRect(1200, 100, 650, 400), QRect(-300, 100, 650, 400), QRect(300, 800, 650, 400)],
    ids=["past-right", "past-left", "past-bottom"],
)
def test_a_dialog_past_any_other_edge_is_moved_back_inside(client: QRect) -> None:
    fitted = fitted_geometry(client, _frame_around(client), SCREEN)

    assert fitted is not None
    assert fitted.size() == client.size()
    assert _frame_inside(fitted)


def test_a_dialog_that_already_fits_is_left_exactly_where_it_is() -> None:
    """Never moved for the sake of it: a user who placed a dialog keeps it where they put it."""
    client = QRect(300, 100, 650, 400)

    assert fitted_geometry(client, _frame_around(client), SCREEN) is None


def test_the_top_edge_wins_when_the_frame_cannot_fit_at_all() -> None:
    """A working area shorter than the frame alone: the title bar is what stays on screen."""
    tiny = QRect(0, 0, 800, 20)
    client = QRect(100, 300, 400, 300)

    fitted = fitted_geometry(client, _frame_around(client), tiny)

    assert fitted is not None
    assert _frame_around(fitted).top() == tiny.top()


@pytest.fixture
def keeper(qapp: QApplication) -> Iterator[QWidget]:
    """An owner with the rule installed, destroyed afterwards so the rule leaves with it."""
    owner = QWidget()
    keep_dialogs_on_screen(qapp, owner)
    yield owner
    owner.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _tall_dialog() -> QDialog:
    dialog = QDialog()
    layout = QVBoxLayout(dialog)
    text = QPlainTextEdit(dialog)
    text.setMinimumHeight(40)
    layout.addWidget(text)
    return dialog


def _inside_its_screen(dialog: QWidget) -> bool:
    available = dialog.screen().availableGeometry()
    frame = dialog.frameGeometry()
    return available.contains(frame.topLeft()) and available.contains(frame.bottomRight())


def test_a_dialog_shown_outside_the_screen_is_fitted_when_shown(
    keeper: QWidget, spin: Callable[..., bool]
) -> None:
    """The installed rule, through a real show: placed above and taller than the screen."""
    dialog = _tall_dialog()
    available = dialog.screen().availableGeometry()
    dialog.setGeometry(40, -400, 500, available.height() + 600)
    try:
        dialog.show()
        assert spin(lambda: _inside_its_screen(dialog), timeout=2), dialog.frameGeometry()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_a_dialog_that_grows_after_it_is_shown_is_fitted_again(
    keeper: QWidget, spin: Callable[..., bool]
) -> None:
    """*Add URLs* grew after it was shown, on Windows; a fit on show alone was not enough."""
    dialog = _tall_dialog()
    try:
        dialog.setGeometry(40, 40, 400, 300)
        dialog.show()
        assert spin(lambda: dialog.isVisible())
        dialog.resize(400, dialog.screen().availableGeometry().height() * 2)
        assert spin(lambda: _inside_its_screen(dialog), timeout=2), dialog.frameGeometry()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_the_rule_leaves_with_its_owner(qapp: QApplication) -> None:
    """Owned by the main window, so a shared application does not keep it after that window.

    **Asserted on this rule's own object**, not by showing a dialog and watching it stay put: other
    windows alive in the same process keep rules of their own, and the `yt-dlp` canary, which runs
    the whole suite in one process, found the behavioural version failing for that reason. Qt drops
    a destroyed object from the application's filters, so a destroyed rule is a removed one.
    """
    import shiboken6

    owner = QWidget()
    keeper = keep_dialogs_on_screen(qapp, owner)
    assert shiboken6.isValid(keeper)
    owner.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert not shiboken6.isValid(keeper), "the rule outlived the window that owned it"


def test_two_rules_on_one_dialog_do_not_spend_each_others_passes(
    qapp: QApplication, spin: Callable[..., bool]
) -> None:
    """The canary's failure, reproduced on purpose: a second window's rule is installed too, and a
    dialog that grows after showing is still fitted."""
    owners = [QWidget(), QWidget()]
    for owner in owners:
        keep_dialogs_on_screen(qapp, owner)
    dialog = _tall_dialog()
    try:
        dialog.setGeometry(40, 40, 400, 300)
        dialog.show()
        assert spin(lambda: dialog.isVisible())
        spin(lambda: False, timeout=0.2)
        dialog.resize(400, dialog.screen().availableGeometry().height() * 2)
        assert spin(lambda: _inside_its_screen(dialog), timeout=2), dialog.frameGeometry()
    finally:
        dialog.close()
        dialog.deleteLater()
        for owner in owners:
            owner.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_installing_twice_for_one_owner_installs_one_rule(qapp: QApplication) -> None:
    owner = QWidget()
    try:
        assert keep_dialogs_on_screen(qapp, owner) is keep_dialogs_on_screen(qapp, owner)
        assert len(owner.findChildren(DialogsOnScreen)) == 1
    finally:
        owner.deleteLater()
        QApplication.processEvents()


@pytest.fixture
def add_dialog(qapp: QApplication, tmp_path: Path) -> Iterator[Callable[[], AddUrlDialog]]:
    """Builds `AddUrlDialog`s the way `test_add_dialog.py` does, and shuts everything down."""
    from tests.qt_lifecycle import drain
    from tests.ui.test_add_dialog import FakeSink, FakeStore

    built: list[tuple[AddUrlDialog, DownloadManager]] = []

    def build() -> AddUrlDialog:
        store = FakeStore()
        manager = DownloadManager(store)
        dialog = AddUrlDialog(
            manager=manager,
            jobs=FakeSink(store),
            output_directory=tmp_path / "downloads",
            cache_root=tmp_path / "cache",
        )
        built.append((dialog, manager))
        return dialog

    yield build
    for dialog, manager in built:
        dialog.close()
        dialog.deleteLater()
        manager.shutdown()
    drain(qapp, [manager for _, manager in built])


def test_add_urls_asks_for_no_more_than_the_screen_and_opens_at_that(
    add_dialog: Callable[[], AddUrlDialog], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dialog's own half (`add_dialog.AddUrlDialog.sizeHint`).

    Its list asks for `WANTED_ROWS` rows; with enough of them the layout wants more than any
    screen, which is what a laptop's working area is at the real row count. Both the hint and the
    size it opens at stay inside the working area less `WINDOW_CHROME`.
    """
    monkeypatch.setattr(add_dialog_module, "WANTED_ROWS", 40)
    dialog = add_dialog()
    room = dialog.screen().availableGeometry().size()
    bound = QSize(room.width() - WINDOW_CHROME, room.height() - WINDOW_CHROME)

    assert dialog.sizeHint().height() <= bound.height()
    assert dialog.sizeHint().width() <= bound.width()
    assert dialog.height() <= bound.height(), "it opens taller than the screen allows"
    # **It has a size of its own before it is shown.** Offscreen Qt does not grow an unresized
    # window after placing it, so this is asserted by the attribute `resize` sets; the growth it
    # prevents was measured on Windows (see `AddUrlDialog.__init__`).
    assert dialog.testAttribute(Qt.WidgetAttribute.WA_Resized)
