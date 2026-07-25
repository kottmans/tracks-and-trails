"""Asserts the T-003 icon assets actually load through Qt (`T003-R3`).

`tests/unit/test_resources.py` checks the files on disk. This checks the thing the application
will really do: hand the paths to `QIcon` and get usable pixmaps back. A file can have a valid
header and still be unloadable by Qt's image plugins, and the `.ico` frame set Qt reports is
not necessarily the one the file declares.

`T-006` runs these same assertions on Windows, which is the only place they can be confirmed
there (`OPS-003`).
"""

from pathlib import Path

import pytest
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

import tracks_and_trails
from tests.unit.test_resources import ICO_SIZES, PNG_SIZES

ICONS = Path(tracks_and_trails.__file__).parent / "resources" / "icons"

ALL_ASSETS = ["icon.png", "icon.ico", *(f"icon-{s}.png" for s in PNG_SIZES)]


@pytest.mark.parametrize("name", ALL_ASSETS)
def test_asset_loads_through_qicon(qapp: QApplication, name: str) -> None:
    """Every delivered asset must produce a non-null QIcon with a usable pixmap."""
    icon = QIcon(str(ICONS / name))
    assert not icon.isNull(), f"{name} did not load through QIcon"
    assert icon.availableSizes(), f"{name} loaded but exposes no sizes"


def test_ico_exposes_every_frame_to_qt(qapp: QApplication) -> None:
    """Qt must see the whole frame set, not only the first frame in the file.

    This is the assertion that matters for the Windows taskbar and title bar: Qt picks the
    frame, so what Qt reports is what the user gets.
    """
    icon = QIcon(str(ICONS / "icon.ico"))
    reported = sorted(size.width() for size in icon.availableSizes())
    assert reported == sorted(ICO_SIZES)
    assert all(size.width() == size.height() for size in icon.availableSizes())


def test_smallest_icon_renders_actual_content(qapp: QApplication) -> None:
    """The 16 px icon must not be blank.

    `T003-R2` settled that 16 px is legible only narrowly, and `T-021` may replace it with a
    simplified glyph. Neither should be able to land an empty or fully transparent asset, so
    assert the weakest property that still catches that: opaque pixels exist.
    """
    pixmap = QIcon(str(ICONS / "icon-16.png")).pixmap(16, 16)
    assert not pixmap.isNull()
    image = pixmap.toImage()
    opaque = sum(
        image.pixelColor(x, y).alpha() > 0
        for x in range(image.width())
        for y in range(image.height())
    )
    assert opaque > 0, "the 16 px icon is fully transparent"
