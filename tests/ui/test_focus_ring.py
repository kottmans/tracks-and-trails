"""The focus ring is drawn for the keyboard, and not for a click (`T-304`, `UX-016`).

The maintainer's ruling of 2026-09-09, option (2). The criterion the ruling named as the case to
check is the handover: **a key pressed after a click shows the ring at once, on the control the
click focused**, and that is asserted on what is drawn, with the focus sweep's own measure
(`tests/ui/test_colour_is_never_alone.py`): a ring is a change in ink of at least
`MINIMUM_FOCUS_RING_SHARE` of one more pixel of edge.

**`T304-R1`: the click's side is asserted on every control there is**, because the style-sheet
rule was the only route the first build covered. The format headers paint their own ring and drew
it on a click; the spin boxes, which the sheet leaves to the platform's style, drew that style's
focus frame. Both were found by sweeping the pointer's side, so the sweep is kept.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tests.ui.conftest import Surface, focusable
from tests.ui.test_colour_is_never_alone import (
    MINIMUM_FOCUS_RING_SHARE,
    SURFACE_COVERAGE_FLOOR,
    THEMES,
    dress,
    one_more_ring,
    rendered,
    surface_alone,
    visible_change,
)
from tests.ui.test_format_table import formats_from
from tracks_and_trails.ui import theme as ui_theme
from tracks_and_trails.ui.focus_ring import FocusRing
from tracks_and_trails.ui.format_table import FormatTable, SortableHeader


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


# --- the click's side, on every route that draws focus (`T304-R1`) ----------------------------


def pointer_turn(qapp: QApplication) -> None:
    """Give the pointer the turn **without clicking any control**: a press sent to a widget of its
    own, which the tracker sees as it sees every event. Clicking each control in a sweep would
    press every button on every screen."""
    elsewhere = QWidget()
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(1, 1),
        QPointF(1, 1),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(elsewhere, press)
    elsewhere.deleteLater()
    qapp.processEvents()


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_a_click_draws_no_ring_on_any_control_and_the_next_key_draws_it(
    every_surface: list[Surface], qapp: QApplication, theme: ui_theme.Theme
) -> None:
    """`UX-016` on every control a keyboard can reach, on every screen there is, both ways round.

    **The key after the click must add a ring**, which a control that drew one on the click cannot
    do: that is how the format headers were found, 430 pixels after the click and not one more
    after the key. **And the click must not draw one**, which the first check alone misses: a spin
    box drew the platform style's one-pixel frame on the click and the sheet's ring on the key, and
    those differ, so it passed the first check while showing a ring on every click.

    **One exemption, proved rather than named**: a dialog's push button that Qt has made the
    default. Qt hands `:default` to whichever button in a dialog has focus, and the sheet fills a
    default button, so the user can see which button Enter presses, whatever moved focus there.
    That fill is not the ring, and the first check still holds such a button to adding the ring on
    the key.
    """
    dress(qapp, theme)
    measured = 0
    default_buttons = 0
    reached: set[str] = set()
    faults: list[str] = []

    for surface in reversed(every_surface):
        surface_alone(every_surface, surface, qapp)
        for widget in focusable(surface.widget):
            if widget.objectName().startswith("qt_") or not widget.isEnabled():
                continue
            holder = QApplication.focusWidget()
            if holder is not None:
                holder.clearFocus()
            qapp.processEvents()
            assert QApplication.focusWidget() is None, "focus stayed put, so idle is not idle"
            idle = rendered(widget)

            pointer_turn(qapp)
            widget.setFocus(Qt.FocusReason.MouseFocusReason)
            qapp.processEvents()
            focused = QApplication.focusWidget()
            assert widget.hasFocus() and focused is not None, f"{widget} took no focus"
            assert focused.property(ui_theme.FOCUS_RING_PROPERTY) is False, "not the pointer's turn"
            clicked = rendered(widget)

            QTest.keyClick(widget, Qt.Key.Key_Shift)
            qapp.processEvents()
            assert focused.property(ui_theme.FOCUS_RING_PROPERTY) is True, "not the keyboard's turn"
            keyed = rendered(widget)

            measured += 1
            reached.add(type(widget).__name__)
            control = f"{type(widget).__name__} {widget.objectName()} on {surface.label}"
            floor = MINIMUM_FOCUS_RING_SHARE * one_more_ring(widget)
            if visible_change(clicked, keyed) < floor:
                faults.append(f"{control}: the key after a click added no ring")
            if visible_change(idle, clicked) >= floor:
                if isinstance(widget, QPushButton) and widget.isDefault():
                    default_buttons += 1
                else:
                    faults.append(f"{control}: a click drew a ring")

    assert not faults, f"in {theme.name}: " + "; ".join(sorted(faults))
    assert measured >= SURFACE_COVERAGE_FLOOR, f"only {measured} controls were reached"
    assert {"SortableHeader", "QSpinBox", "QDoubleSpinBox"} <= reached, (
        f"the two routes this sweep was written for are not on a screen it reached: {reached}"
    )
    assert default_buttons, "no default button was exempted, so that branch is doing nothing"


def _accent_pixels(widget: QWidget, theme: ui_theme.Theme) -> int:
    image = rendered(widget)
    accent = QColor(theme.accent).rgb()
    return sum(
        1
        for y in range(image.height())
        for x in range(image.width())
        if image.pixel(x, y) == accent
    )


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_a_real_click_on_a_format_header_draws_no_ring(
    qapp: QApplication, theme: ui_theme.Theme
) -> None:
    """**`T304-R1`'s reproduction, kept**: a real click on the centre of section 0, through the
    header's viewport, focused the header with `focusRing` false and painted the same 430 accent
    pixels as the key did, because `SortableHeader.paintSection` asked only `hasFocus()`."""
    dress(qapp, theme)
    table = FormatTable(formats_from("derived_format_columns"))
    table.show()
    qapp.processEvents()
    try:
        header = table.header
        assert isinstance(header, SortableHeader)
        middle = QPoint(
            header.sectionViewportPosition(0) + header.sectionSize(0) // 2, header.height() // 2
        )

        QTest.mouseClick(header.viewport(), Qt.MouseButton.LeftButton, pos=middle)
        qapp.processEvents()

        assert header.hasFocus(), "the click did not focus the header, so this proves nothing"
        assert header.property(ui_theme.FOCUS_RING_PROPERTY) is False
        assert _accent_pixels(header, theme) == 0, "a click drew the header's ring"

        QTest.keyClick(header, Qt.Key.Key_Shift)
        qapp.processEvents()

        assert header.hasFocus()
        assert _accent_pixels(header, theme) >= one_more_ring(header), "the key drew no ring"
    finally:
        table.close()
        table.deleteLater()
        qapp.processEvents()


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_a_real_click_on_a_spin_box_draws_no_frame_of_the_platform_s_own(
    qapp: QApplication, theme: ui_theme.Theme
) -> None:
    """The sheet leaves `QSpinBox` to the platform's style (`T-133`), and that style draws its own
    focus frame: with Fusion, one pixel of the palette's highlight, measured at **0.91 to 1.00** of
    a ring on every spin box the application shows. `_KeyboardFocusStyle` withholds it."""
    dress(qapp, theme)
    host = QWidget()
    layout = QVBoxLayout(host)
    elsewhere = QPushButton("elsewhere", host)
    box = QSpinBox(host)
    layout.addWidget(elsewhere)
    layout.addWidget(box)
    host.show()
    qapp.processEvents()
    try:
        elsewhere.setFocus()
        qapp.processEvents()
        idle = rendered(box)
        floor = MINIMUM_FOCUS_RING_SHARE * one_more_ring(box)

        QTest.mouseClick(box, Qt.MouseButton.LeftButton, pos=QPoint(8, box.height() // 2))
        qapp.processEvents()

        assert box.hasFocus(), "the click did not focus the spin box, so this proves nothing"
        clicked = rendered(box)
        assert visible_change(idle, clicked) < floor, "a click drew a focus frame"

        QTest.keyClick(box, Qt.Key.Key_Shift)
        qapp.processEvents()
        assert visible_change(clicked, rendered(box)) >= floor, "the key drew no ring"
    finally:
        host.close()
        host.deleteLater()
        qapp.processEvents()


class _Paints(QObject):
    """Counts the paint events one widget receives."""

    def __init__(self) -> None:
        super().__init__()
        self.count = 0

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt's name
        if event.type() == QEvent.Type.Paint:
            self.count += 1
        return False


def test_the_header_repaints_its_sections_when_the_turn_changes(qapp: QApplication) -> None:
    """A header paints its sections in its **viewport**, a child of its own, so the ring appears and
    goes only if the change of turn repaints that child as well as the header (`T304-R1`).
    `render()` paints from scratch, so this counts what the screen would be sent instead."""
    dress(qapp, ui_theme.LIGHT)
    table = FormatTable(formats_from("derived_format_columns"))
    table.show()
    qapp.processEvents()
    try:
        header = table.header
        paints = _Paints()
        header.viewport().installEventFilter(paints)
        header.setFocus()
        qapp.processEvents()

        for turn in ("pointer", "keyboard"):
            before = paints.count
            if turn == "pointer":
                pointer_turn(qapp)
            else:
                QTest.keyClick(header, Qt.Key.Key_Shift)
            qapp.processEvents()
            assert paints.count > before, f"the {turn}'s turn left the old sections on the screen"
    finally:
        table.close()
        table.deleteLater()
        qapp.processEvents()


def test_drawing_with_the_wrapped_style_leaves_every_scroll_bar_alive(
    every_surface: list[Surface], qapp: QApplication
) -> None:
    """`_KeyboardFocusStyle` asks the tracker whose turn it is and never the widget being drawn:
    asking that widget for its `focusProxy()` from inside a draw call **deleted** a table's scroll
    bar during `render()`, with PySide6 6.11 and the sheet installed. Every scroll bar on every
    screen, drawn on both turns, is still there afterwards."""
    dress(qapp, ui_theme.LIGHT)
    bars = [
        bar
        for surface in every_surface
        for area in surface.widget.window().findChildren(QAbstractScrollArea)
        for bar in (area.horizontalScrollBar(), area.verticalScrollBar())
    ]
    assert bars, "no scroll bar on any screen, so this draws nothing"
    for surface in every_surface:
        surface_alone(every_surface, surface, qapp)
        for widget in focusable(surface.widget)[:1]:
            for keyboard in (False, True):
                widget.setFocus()
                if keyboard:
                    QTest.keyClick(widget, Qt.Key.Key_Shift)
                else:
                    pointer_turn(qapp)
                rendered(surface.widget.window())
                qapp.processEvents()

    lost = 0
    for bar in bars:
        try:
            bar.objectName()
        except RuntimeError:
            lost += 1
    assert not lost, f"{lost} of {len(bars)} scroll bars were deleted by drawing them"
