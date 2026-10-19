"""The focus ring is drawn for the keyboard, and not for a click (`T-304`, `UX-016`).

The maintainer's ruling of 2026-09-09, option (2). The criterion the ruling named as the case to
check is the handover: **a key pressed after a click shows the ring at once, on the control the
click focused**, and that is asserted on what is drawn, with the focus sweep's own measure
(`tests/ui/test_colour_is_never_alone.py`): a ring is a change in ink of at least
`MINIMUM_FOCUS_RING_SHARE` of one more pixel of edge.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QSpinBox, QVBoxLayout, QWidget

from tests.ui.test_colour_is_never_alone import (
    MINIMUM_FOCUS_RING_SHARE,
    THEMES,
    dress,
    one_more_ring,
    rendered,
    visible_change,
)
from tracks_and_trails.ui import theme as ui_theme
from tracks_and_trails.ui.focus_ring import FocusRing


@pytest.fixture
def stage(qapp: QApplication) -> Iterator[tuple[QWidget, QPushButton, QPushButton]]:
    host = QWidget()
    layout = QVBoxLayout(host)
    elsewhere = QPushButton("elsewhere", host)
    target = QPushButton("target", host)
    layout.addWidget(elsewhere)
    layout.addWidget(target)
    host.resize(260, 140)
    host.show()
    qapp.processEvents()
    yield host, elsewhere, target
    host.close()
    host.deleteLater()
    qapp.processEvents()


def _ring_drawn(idle: object, widget: QWidget) -> bool:
    change = visible_change(idle, rendered(widget))  # type: ignore[arg-type]
    return change >= MINIMUM_FOCUS_RING_SHARE * one_more_ring(widget)


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_a_click_draws_no_ring_and_the_next_key_draws_it_on_the_same_control(
    qapp: QApplication,
    theme: ui_theme.Theme,
    stage: tuple[QWidget, QPushButton, QPushButton],
) -> None:
    """The ruling's case: clicking around draws nothing; reaching for the keyboard shows where
    focus already is, without moving it."""
    dress(qapp, theme)
    _host, elsewhere, target = stage
    elsewhere.setFocus()
    qapp.processEvents()
    idle = rendered(target)

    QTest.mouseClick(target, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert target.hasFocus(), "the click did not focus the button, so this proves nothing"
    assert not _ring_drawn(idle, target), "a click drew the focus ring"

    QTest.keyClick(target, Qt.Key.Key_Shift)
    qapp.processEvents()

    assert target.hasFocus()
    assert _ring_drawn(idle, target), "the key after the click did not show the ring"


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_the_keyboard_draws_the_ring_from_the_start(
    qapp: QApplication,
    theme: ui_theme.Theme,
    stage: tuple[QWidget, QPushButton, QPushButton],
) -> None:
    """Nothing has been clicked in a newly dressed application, so `Tab` shows the ring."""
    dress(qapp, theme)
    _host, elsewhere, target = stage
    elsewhere.setFocus()
    qapp.processEvents()
    idle = rendered(target)

    QTest.keyClick(elsewhere, Qt.Key.Key_Tab)
    qapp.processEvents()

    assert target.hasFocus()
    assert _ring_drawn(idle, target)


def test_a_spin_box_with_a_line_edit_inside_is_told_as_a_whole(qapp: QApplication) -> None:
    """A spin box is a control with a line edit inside it, and the ring is the spin box's: told
    `false` by the click and `true` by the next key, whichever of the two Qt reports as focused."""
    dress(qapp, ui_theme.LIGHT)
    host = QWidget()
    layout = QVBoxLayout(host)
    box = QSpinBox(host)
    layout.addWidget(box)
    host.show()
    qapp.processEvents()

    QTest.mouseClick(box, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert box.hasFocus()
    assert box.property(ui_theme.FOCUS_RING_PROPERTY) is False
    QTest.keyClick(box, Qt.Key.Key_Shift)
    qapp.processEvents()
    assert box.property(ui_theme.FOCUS_RING_PROPERTY) is True
    host.close()


def test_dressing_the_application_installs_one_tracker_on_the_keyboard_s_turn(
    qapp: QApplication,
) -> None:
    """`theme.apply` themes everything, the property's tracker included, and starts it afresh."""
    dress(qapp, ui_theme.LIGHT)
    host = QPushButton("press")
    host.show()
    QTest.mouseClick(host, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    dress(qapp, ui_theme.DARK)

    trackers = qapp.findChildren(FocusRing)
    assert len(trackers) == 1 and trackers[0].keyboard
    host.close()


def test_every_focus_rule_asks_for_the_ring() -> None:
    """A focus rule written without `theme.focused` would draw on a click again."""
    sheet = re.sub(r"/\*.*?\*/", "", ui_theme.stylesheet(ui_theme.LIGHT), flags=re.S)
    selectors = re.findall(r"([^{}]+)\{", sheet)
    parts = [
        part.strip() for selector in selectors for part in selector.split(",") if ":focus" in part
    ]

    assert parts, "the sheet has no focus rules at all"
    missing = [part for part in parts if f'[{ui_theme.FOCUS_RING_PROPERTY}="true"]' not in part]
    assert not missing, missing
