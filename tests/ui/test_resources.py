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

ALL_ASSETS = ["icon.png", "icon-small.png", "icon.ico", *(f"icon-{s}.png" for s in PNG_SIZES)]

#: Opaque pixels at 16 px that must be trail gold (`T-021`).
#:
#: **Measured 2026-08-15, and it is the whole point of the reduced glyph.** The full logo
#: downscaled to 16 px puts **13** gold pixels on screen out of 69 opaque; the reduced glyph puts
#: **20** out of 66, because dropping the trees and the mountain gives the trail the room they were
#: taking and `render_small_glyph.TRAIL_GROWTH` keeps it continuous instead of dotted.
#:
#: The floor sits between the two numbers deliberately. A regeneration that stopped using
#: `icon-small.png` — the one failure this can actually catch — lands back on 13 and fails here,
#: while ordinary redrawing of the glyph has room to move.
MINIMUM_GOLD_AT_16 = 16


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


def test_the_reduced_glyph_keeps_its_trail_at_16_px(qapp: QApplication) -> None:
    """`T-021`: the gold trail is one of the two elements the small glyph exists to preserve.

    **This is the only part of `T-021`'s acceptance a test can carry.** Its first criterion is that
    the glyph be *more legible than the current downscale, judged side by side*, and that is a
    human judgement recorded in `ai/evidence/2026-08-15-T021-small-glyph.png`. What is checkable is
    the mechanism behind it: the trail has to occupy enough of a 16 px cell to read as a line
    rather than as three specks.

    Counted from the rendered pixmap rather than the file, because Qt is what picks and scales the
    asset the user sees — the same reason this module exists alongside `tests/unit/test_resources`.
    """
    image = QIcon(str(ICONS / "icon-16.png")).pixmap(16, 16).toImage()
    gold = 0
    for x in range(image.width()):
        for y in range(image.height()):
            colour = image.pixelColor(x, y)
            if colour.alpha() < 128:
                continue
            # Trail gold is `#D9A24C`: high red, mid green, low blue. Compared as a relation
            # rather than against the exact value, since these pixels are antialiased blends of
            # the trail with the green behind it.
            if (
                colour.red() > 150
                and colour.green() > 110
                and colour.blue() < 140
                and colour.red() > colour.blue() + 50
            ):
                gold += 1

    assert gold >= MINIMUM_GOLD_AT_16, (
        f"the 16 px glyph carries {gold} gold pixels, under the {MINIMUM_GOLD_AT_16} floor — the "
        "trail has thinned to the point the full-logo downscale had it, which is what the reduced "
        "glyph exists to fix"
    )
