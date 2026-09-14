"""A label or tick box inside a group sits on the group's ground (`T-327` session, 2026-09-13).

The sheet's `QWidget` rule gives **every** widget the `window` background, and a group box is
`surface`. So each label, check box and radio button inside one painted a `window` rectangle on the
group's `surface`: a band behind every line of the options dialog, which the maintainer saw in dark
and which is there in light too (`#F5F7F4` on `#FFFFFF`).

Walked over every screen the application shows rather than the dialog it was seen on, and asked of
the rendered pixels: what matters is what is drawn under the text, not which rule says so.
"""

from collections import Counter

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGroupBox,
    QLabel,
    QRadioButton,
    QWidget,
)

from tests.ui.conftest import Surface
from tracks_and_trails.ui import theme

#: The controls that carry no ground of their own. Anything with a fill of its own — a combo, a
#: line edit, a list — is drawn on purpose and is not asked.
GROUNDLESS: tuple[type[QWidget], ...] = (QLabel, QCheckBox, QRadioButton)


@pytest.mark.parametrize("chosen", list(theme.THEMES.values()), ids=lambda t: t.name)
def test_nothing_inside_a_group_paints_a_band_behind_itself(
    qapp: QApplication, every_surface: list[Surface], chosen: theme.Theme
) -> None:
    theme.apply(qapp, chosen)
    qapp.processEvents()
    ground = int(chosen.surface[1:], 16)
    banded: list[str] = []
    asked = 0
    for surface in every_surface:
        for group in surface.widget.findChildren(QGroupBox):
            # A dialog is parented to the window that opened it, so its groups are the dialog's own
            # surface's to ask about, not the main window's as well.
            if group.window() is not surface.widget.window():
                continue
            if not group.isVisibleTo(surface.widget) or group.width() == 0:
                continue
            image = group.grab().toImage()
            for child in group.findChildren(QWidget):
                # A plain `QWidget` is a layout container, and a band the size of a whole row.
                plain = type(child) is QWidget
                if not (plain or isinstance(child, GROUNDLESS)) or not child.isVisibleTo(group):
                    continue
                if child.width() < 4 or child.height() < 4:
                    continue
                corner = child.mapTo(group, child.rect().topLeft())
                colours = Counter(
                    image.pixel(x, y) & 0xFFFFFF
                    for x in range(corner.x(), corner.x() + child.width())
                    for y in range(corner.y(), corner.y() + child.height())
                    if image.rect().contains(x, y)
                )
                if not colours:
                    continue
                asked += 1
                dominant, _count = colours.most_common(1)[0]
                if dominant != ground:
                    banded.append(
                        f"{surface.label}: {type(child).__name__} {child.objectName() or ''!r} "
                        f"sits on #{dominant:06x} inside a {chosen.surface} group"
                    )
    assert asked, "no label or tick box inside any group, so this asserted nothing"
    assert not banded, f"{chosen.name}: " + "; ".join(banded[:8])
