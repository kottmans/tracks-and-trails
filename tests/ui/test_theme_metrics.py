"""What the style sheet takes away from the native style, and has to give back (`T-129`).

`tests/unit/test_theme.py` asserts the palette as arithmetic and stays Qt-free on purpose. These
claims cannot be arithmetic: they are about what Qt's style *does* with the sheet, and both defects
here were invisible to every existing test and to CI, and were found by opening the application.

**The shape both defects share.** Styling a widget class at all switches that widget from the
platform style to `QStyleSheetStyle`. Anything the platform style was supplying — a layout metric,
a hover rendering — is then supplied by the sheet or not at all. Neither is a colour, so neither
was caught by the contrast arithmetic that `T-120` does assert.

Rendering comparisons rather than a search for rule text: asserting that the sheet *contains*
`:hover` is a list agreeing with a list, which is exactly what `T040-R1` records surviving a
mutation. What a user notices is that the pixels change, so that is what is measured.
"""

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QLabel,
    QMenu,
    QPushButton,
    QStyle,
    QStyleOptionButton,
    QStyleOptionGroupBox,
    QStyleOptionMenuItem,
    QVBoxLayout,
)

from tracks_and_trails.ui import theme


@pytest.fixture
def themed(qapp: QApplication) -> Iterator[QApplication]:
    """The real application style sheet, restored afterwards.

    Restored because a style sheet is application-wide: leaving it on would silently theme every
    later test in the process, and a test that passes because of what a previous one left behind
    is the failure `ai/TESTING.md` §13 is about.
    """
    previous = qapp.styleSheet()
    qapp.setStyleSheet(theme.stylesheet(theme.LIGHT))
    yield qapp
    qapp.setStyleSheet(previous)


def _group_box_rects(box: QGroupBox) -> tuple[QRect, QRect]:
    """Where the style puts this group box's title, and where it puts its contents."""
    option = QStyleOptionGroupBox()
    box.initStyleOption(option)
    style = box.style()
    title = style.subControlRect(
        QStyle.ComplexControl.CC_GroupBox, option, QStyle.SubControl.SC_GroupBoxLabel, box
    )
    contents = style.subControlRect(
        QStyle.ComplexControl.CC_GroupBox, option, QStyle.SubControl.SC_GroupBoxContents, box
    )
    return title, contents


def test_a_themed_group_box_leaves_room_for_its_own_title(themed: QApplication) -> None:
    """**`T-129`'s first defect, and it is a metric rather than a colour.**

    `QGroupBox::title` uses `subcontrol-origin: margin`, which puts the title in the widget's
    margin — and the sheet declared no margin, so there was no band to put it in. Qt drew the title
    at `y = 0`: through the frame's own top border and across the first control inside it. On the
    add-URL dialog that made *"What you pasted"* and *"Download as"* unreadable.

    Measured before the fix: the title's bottom sat **15 px below** the contents' top. Qt's own
    style leaves 5 px of clearance, and the assertion is that clearance exists at all rather than a
    reproduction of Qt's exact number, which is a platform detail this project does not own.
    """
    box = QGroupBox("What you pasted")
    layout = QVBoxLayout(box)
    layout.addWidget(QLabel("a control inside the box"))
    box.resize(320, 120)
    box.show()
    try:
        QApplication.processEvents()
        title, contents = _group_box_rects(box)

        assert title.bottom() < contents.top(), (
            f"the group box title (bottom {title.bottom()}) runs into its contents "
            f"(top {contents.top()}). QGroupBox::title uses subcontrol-origin: margin, so "
            "QGroupBox needs a margin-top big enough to hold it"
        )
    finally:
        box.close()


def test_the_theme_is_what_makes_the_title_fit(qapp: QApplication) -> None:
    """The positive control: without the sheet Qt already got this right.

    Without it, the test above could pass because `QGroupBox` happens to lay out safely for some
    unrelated reason, and would keep passing if the sheet stopped being applied at all. This pins
    the claim to the sheet.
    """
    box = QGroupBox("What you pasted")
    QVBoxLayout(box).addWidget(QLabel("a control inside the box"))
    box.resize(320, 120)
    box.show()
    try:
        QApplication.processEvents()
        title, contents = _group_box_rects(box)
        assert title.bottom() < contents.top(), (
            "Qt's own style collides too, so this file is measuring the wrong thing"
        )
    finally:
        box.close()


def _fill(widget: object, option: object, element: QStyle.ControlElement) -> str:
    """The background colour the style paints for this control, as `#rrggbb`.

    **Drawn through the widget**, which is the whole point: a style sheet is applied by
    `QStyleSheetStyle` wrapping the widget's style, so `QApplication.style().drawControl(...)` with
    no widget never consults the sheet at all. The first version of this file did exactly that and
    both mutations survived — it was measuring the *platform* style's hover, which was never the
    thing at fault.

    The label is cleared before drawing so the sampled centre pixel is background rather than a
    glyph, and the assertion is a **colour the theme names** rather than "the two renderings
    differ": the platform style also differs under hover, so mere difference proves nothing about
    whether our sheet is what produced it.
    """
    option.text = ""  # type: ignore[attr-defined]
    image = QImage(160, 34, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    try:
        widget.style().drawControl(element, option, painter, widget)  # type: ignore[attr-defined]
    finally:
        painter.end()
    return QImage.pixelColor(image, 80, 17).name()


def test_a_themed_button_fills_with_the_themes_own_hover_colour(themed: QApplication) -> None:
    """**`T-129`'s second defect.** The sheet declared `:disabled` and nothing else.

    Styling `QPushButton` switches it to style-sheet rendering, and Qt then draws hover exactly
    like the normal state unless the sheet says otherwise — so every button on every row was inert
    under the pointer, including *Open*, *Show in folder* and *Remove* on the history rows.

    Measured, with the rule deleted: the hover fill stays `surface`, identical to normal.
    """
    button = QPushButton()
    button.resize(160, 34)
    button.show()
    try:
        QApplication.processEvents()

        plain = QStyleOptionButton()
        button.initStyleOption(plain)
        plain.state &= ~QStyle.StateFlag.State_MouseOver

        hovered = QStyleOptionButton()
        button.initStyleOption(hovered)
        hovered.state |= QStyle.StateFlag.State_MouseOver

        normal_fill = _fill(button, plain, QStyle.ControlElement.CE_PushButton)
        hover_fill = _fill(button, hovered, QStyle.ControlElement.CE_PushButton)

        assert normal_fill == theme.LIGHT.surface.lower(), (
            f"an idle themed button fills {normal_fill}, not the theme's surface"
        )
        assert hover_fill == theme.LIGHT.sunken.lower(), (
            f"a themed button under the pointer fills {hover_fill}, not the theme's sunken. "
            "Nothing tells the user which control they are about to activate"
        )
    finally:
        button.close()


def test_a_themed_menu_highlights_the_selected_item_in_the_brand_primary(
    themed: QApplication,
) -> None:
    """The same defect on the overflow menu, which `UX-005` §4 makes the keyboard route.

    `QWidget {{ background-color; color }}` is a universal selector, so it catches `QMenu` —
    switching menus to style-sheet rendering with nothing declared for the selected item. Every
    entry then looked the same as the one under the cursor, and on the keyboard route there is no
    cursor to fall back on: the highlight *is* the only indication of what Enter will do.
    """
    menu = QMenu()
    menu.addAction("Show in folder")
    menu.resize(160, 34)
    menu.show()
    try:
        QApplication.processEvents()

        plain = QStyleOptionMenuItem()
        plain.rect = QRect(0, 0, 160, 34)
        plain.state = QStyle.StateFlag.State_Enabled

        selected = QStyleOptionMenuItem()
        selected.rect = QRect(0, 0, 160, 34)
        selected.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Selected

        highlighted = _fill(menu, selected, QStyle.ControlElement.CE_MenuItem)
        idle = _fill(menu, plain, QStyle.ControlElement.CE_MenuItem)

        assert highlighted != idle, (
            "a themed menu draws the selected item exactly like the rest, so neither the pointer "
            "nor the arrow keys show what is about to be activated"
        )
        assert highlighted == theme.LIGHT.primary.lower(), (
            f"the selected menu item fills {highlighted}, not the theme's primary "
            f"({theme.LIGHT.primary.lower()})"
        )
    finally:
        menu.close()
