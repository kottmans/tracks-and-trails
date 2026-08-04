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


@pytest.fixture(params=sorted(theme.THEMES), ids=sorted(theme.THEMES))
def chosen(request: pytest.FixtureRequest) -> theme.Theme:
    """Each theme in turn.

    Supplied for `test_lightening_a_row_does_not_make_selected_text_invisible`, which arrived from
    the reviewer without it and so errored at setup rather than running. Parametrized over both
    themes because `T130-R1` measured both — 1.14:1 light and 1.33:1 dark — and a palette claim
    that held in one and not the other would be exactly the half-fix that finding is about.
    """
    return theme.THEMES[request.param]


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


# --- T-130: what the maintainer's 2026-08-04 ruling on UX-005 adopted --------------------------


def test_the_row_tint_is_scoped_to_lists_and_the_editor_keeps_a_visible_selection(
    themed: QApplication,
) -> None:
    """`UX-005`'s 2026-08-04 amendment row 4, and `T130-R1`'s correction to how I applied it.

    The ruling wanted a quiet row: a tint plus an inset bar. **I applied it through
    `QPalette.Highlight`, which is application-wide** — and a row can afford a subtle tint only
    because it also gets the bar. Selected *text* has no second signal, so a selected URL in the
    log view came out at **1.14:1** against its own surface: invisible rather than quiet.

    The correction is scope. The sheet tints `QListView, QTreeView, QTableView` and Qt propagates
    that into those widgets' palettes, so the delegate still reads the tint's pair from
    `option.palette`; the application palette keeps the brand highlight for everything else.

    *(The first version of this test asserted the **global** palette held the tint — it encoded the
    defect, which is why it kept passing while a selected URL was unreadable.)*
    """
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QListView, QPlainTextEdit

    previous = QPalette(themed.palette())
    view: QListView | None = None
    editor: QPlainTextEdit | None = None
    try:
        theme.apply(themed, theme.LIGHT)
        view = QListView()
        editor = QPlainTextEdit()
        view.show()
        editor.show()
        QApplication.processEvents()

        row_fill = view.palette().color(QPalette.ColorRole.Highlight).name()
        row_text = view.palette().color(QPalette.ColorRole.HighlightedText).name()
        assert row_fill == theme.LIGHT.selection.lower(), (
            f"a selected list row fills {row_fill}, not the tint the ruling adopted"
        )
        assert theme.contrast_ratio(row_text, row_fill) >= theme.MINIMUM_CONTRAST, (
            "the delegate reads this pair from option.palette; a selected title must stay legible"
        )

        selection = editor.palette().color(QPalette.ColorRole.Highlight).name()
        base = editor.palette().color(QPalette.ColorRole.Base).name()
        assert theme.contrast_ratio(selection, base) >= theme.MINIMUM_CONTROL_CONTRAST, (
            f"selected text uses {selection} on {base} — the row's tint escaped into the "
            "application palette, where there is no inset bar to carry it"
        )
    finally:
        if view is not None:
            view.close()
        if editor is not None:
            editor.close()
        themed.setPalette(previous)


def test_lightening_a_row_does_not_make_selected_text_invisible(
    qapp: QApplication, chosen: theme.Theme
) -> None:
    """Reviewer regression: the application palette also governs text selection.

    T-130 wants a quiet row tint plus an inset bar. A text editor has no inset bar, so exporting
    that tint through the application-wide ``QPalette.Highlight`` makes a selected URL or log span
    indistinguishable from the editor surface. Drive the real palette on a real copyable widget:
    this is the route a user takes before Copy, not arithmetic about a role nothing consumes.
    """
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QPlainTextEdit

    previous_palette = QPalette(qapp.palette())
    previous_sheet = qapp.styleSheet()
    editor: QPlainTextEdit | None = None
    try:
        theme.apply(qapp, chosen)
        # `app.py` applies the theme before constructing any widget. Building this first would
        # retain Qt's original blue highlight and test an ordering the application never takes.
        editor = QPlainTextEdit()
        editor.setPlainText("https://example.invalid/a-selected-url")
        editor.selectAll()

        selected = editor.palette().color(QPalette.ColorRole.Highlight).name()
        surface = editor.palette().color(QPalette.ColorRole.Base).name()
        ratio = theme.contrast_ratio(selected, surface)

        assert editor.textCursor().hasSelection(), "the probe has no selected text"
        assert ratio >= theme.MINIMUM_CONTROL_CONTRAST, (
            f"{chosen.name}: selected text uses {selected} on {surface}, only {ratio:.2f}:1. "
            "The row has an inset bar to carry its subtle tint; selected text has no second "
            "signal, so the application palette must keep that selection visible"
        )
    finally:
        if editor is not None:
            editor.close()
        qapp.setPalette(previous_palette)
        qapp.setStyleSheet(previous_sheet)
