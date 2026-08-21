"""Asserts the T-003 icon assets actually load through Qt (`T003-R3`).

`tests/unit/test_resources.py` checks the files on disk. This checks the thing the application
will really do: hand the paths to `QIcon` and get usable pixmaps back. A file can have a valid
header and still be unloadable by Qt's image plugins, and the `.ico` frame set Qt reports is
not necessarily the one the file declares.

`T-006` runs these same assertions on Windows, which is the only place they can be confirmed
there (`OPS-003`).

`T-274` replaced the artwork and the pipeline behind it — the assets are now rasterized from the
vendored SVG artboards in `tools/icons/masters/` — and rewrote the trail check below, which had
been measuring a property the new artwork does not have.
"""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

import tracks_and_trails
from tests.unit.test_resources import ICO_SIZES, PNG_SIZES, SMALL_SIZES

ICONS = Path(tracks_and_trails.__file__).parent / "resources" / "icons"

#: The vendored SVG artboards every shipped asset is rendered from (`T-274`). Reached only by
#: the control test, which needs the full mark at a size no shipped asset uses it at.
MASTERS = Path(__file__).resolve().parents[2] / "tools" / "icons" / "masters"

ALL_ASSETS = ["icon.png", "icon-small.png", "icon.ico", *(f"icon-{s}.png" for s in PNG_SIZES)]

#: Trail-gold pixels the 16 px asset must carry (`T-274`, replacing `T-021`'s floor of 16).
#:
#: **Measured 2026-08-21 on the new small cut: 9.** The floor sits below it because the count
#: alone can no longer tell the two cuts apart — the full mark at 16 px carries *11*, more gold
#: than the reduced cut, because its sound-wave arcs are gold too. What separates them is
#: `test_the_small_cut_is_what_ships_at_every_small_size`'s connectivity assertion; this number
#: only has to catch a trail that has thinned to nothing, so it leaves room for redrawing.
#:
#: *(`T-021`'s 16 was the midpoint between a 13-pixel full-logo downscale and a 20-pixel derived
#: glyph whose trail had been deliberately dilated. Both of those artworks are gone.)*
MINIMUM_GOLD_AT_16 = 6


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


def is_trail_gold(colour: QColor) -> bool:
    """Whether an opaque rendered pixel belongs to the gold trail.

    Trail gold is `#D9A24C`: high red, mid green, low blue. Compared as a relation rather than
    against the exact value, since these pixels are antialiased blends of the trail with the
    green behind it.
    """
    if colour.alpha() < 128:
        return False
    return (
        colour.red() > 150
        and colour.green() > 110
        and colour.blue() < 140
        and colour.red() > colour.blue() + 50
    )


def gold_runs(image: QImage) -> list[int]:
    """Sizes of the image's connected runs of trail gold, largest first (8-connectivity)."""
    gold = {
        (x, y)
        for x in range(image.width())
        for y in range(image.height())
        if is_trail_gold(image.pixelColor(x, y))
    }
    seen: set[tuple[int, int]] = set()
    runs = []
    for seed in gold:
        if seed in seen:
            continue
        stack, size = [seed], 0
        seen.add(seed)
        while stack:
            x, y = stack.pop()
            size += 1
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    neighbour = (x + dx, y + dy)
                    if neighbour in gold and neighbour not in seen:
                        seen.add(neighbour)
                        stack.append(neighbour)
        runs.append(size)
    return sorted(runs, reverse=True)


#: Sizes rendered from the full mark: everything the reduced cut does not cover.
FULL_SIZES = tuple(size for size in PNG_SIZES if size not in SMALL_SIZES)


def shipped(source: str, size: int) -> QImage:
    """The asset a caller asking `source` for `size` actually gets, rendered through Qt.

    **Both sources, because both ship and they are picked by different consumers.** The sized
    PNGs are what anything asking for a file by name gets; the `.ico` is what Windows reads for
    the title bar and the taskbar, and Qt chooses the frame. They are byte-identical today —
    `render_icons.write_ico` embeds the same renders — and a check that consulted only one would
    not notice if they stopped being.
    """
    path = ICONS / ("icon.ico" if source == "ico" else f"icon-{size}.png")
    return QIcon(str(path)).pixmap(size, size).toImage()


def sources_for(sizes: tuple[int, ...]) -> list[tuple[str, int]]:
    """`(source, size)` pairs for every way `sizes` ship. The `.ico` stops at its largest frame."""
    return [("png", size) for size in sizes] + [
        ("ico", size) for size in sizes if size in ICO_SIZES
    ]


@pytest.mark.parametrize(("source", "size"), sources_for(SMALL_SIZES))
def test_the_small_cut_is_what_ships_at_every_small_size(
    qapp: QApplication, source: str, size: int
) -> None:
    """`T-274`: below the split, every shipped asset is the reduced cut — one unbroken trail.

    **This is what replaced `T-021`'s pixel count, and the reason is that the count stopped
    discriminating.** The reduced cut used to carry *more* gold than the full mark downscaled,
    because it was derived by masking and its trail was dilated to survive. The pack's small cut
    is not derived — its trail is byte-identical to the master's — so at 16 px it carries **9**
    gold pixels against the full mark's **11**, and any floor that passes the one passes the
    other.

    What separates them is **shape**. The full mark's gold is the trail *and* two sound-wave
    arcs, and at every size those arcs are separate from it: 2 runs at 16 px, 2 at 24, 2 at 32,
    4 at 48, 3 from 64 up. The reduced cut has no arcs, so its gold is exactly **one** run.

    **Parameterized over every small size and both sources, which is `T274-R1`.** The first
    version of this asserted 16 px alone while `SMALL_SIZES` claimed three, so a renderer set to
    `{16}` regenerated 24 and 32 — PNGs and `.ico` frames alike — back to the full mark and the
    suite stayed green. A boundary stated in one file and enforced at one of its three sizes is
    not enforced.

    Counted from the rendered pixmap rather than the file, because Qt is what picks and scales
    the asset the user sees — the same reason this module exists alongside
    `tests/unit/test_resources`.
    """
    runs = gold_runs(shipped(source, size))

    assert runs, f"the {size} px {source} carries no trail gold at all"
    assert len(runs) == 1, (
        f"the {size} px {source} puts its gold in {len(runs)} separate runs ({runs}) — the "
        "reduced cut's gold is the trail alone and is always one run, so this is the full mark, "
        "whose arcs are a separate shape at every size"
    )


@pytest.mark.parametrize(("source", "size"), sources_for(FULL_SIZES))
def test_the_full_mark_is_what_ships_above_the_split(
    qapp: QApplication, source: str, size: int
) -> None:
    """And above the split it is the full mark — the same property, read the other way.

    **This half is not required by `T274-R1` and is here because the hole is symmetric.** With
    only the small sizes asserted, a renderer that moved 48 px — or all of them — onto the
    reduced cut would pass every check in this module, and the landscape would quietly leave the
    icon at the sizes that can carry it. The arcs are what make it checkable: they are gold and
    they are never joined to the trail, so the full mark cannot present as one run.
    """
    runs = gold_runs(shipped(source, size))

    assert len(runs) > 1, (
        f"the {size} px {source} puts its gold in one run — that is the reduced cut, which is "
        f"drawn below {min(FULL_SIZES)} px and not at or above it"
    )


def test_the_16_px_trail_is_thick_enough_to_read(qapp: QApplication) -> None:
    """The smallest asset's trail must be a line rather than a speck.

    Connectivity says the gold is one shape; it does not say the shape is big enough to see, and
    a trail thinned to two pixels would still be one run. This is the floor that catches that,
    and 16 px is the only size where it is in any doubt.
    """
    runs = gold_runs(shipped("png", 16))

    assert runs[0] >= MINIMUM_GOLD_AT_16, (
        f"the 16 px trail is {runs[0]} pixels, under the {MINIMUM_GOLD_AT_16} floor — it has "
        "thinned to the point of vanishing"
    )


@pytest.mark.parametrize("size", SMALL_SIZES)
def test_the_predicate_can_tell_the_two_cuts_apart(qapp: QApplication, size: int) -> None:
    """The control for the two tests above: the full mark **fails** what the small cut passes.

    A one-run assertion is worth nothing if both cuts satisfy it, and this is the only place that
    can be established at the small sizes — every shipped asset there is the reduced cut, so
    nothing else in the suite ever draws the full mark small enough to break. It reaches past the
    shipped assets to `tools/icons/masters/icon.svg` deliberately: the point is to feed the check
    a known positive and watch it fire.
    """
    renderer = QSvgRenderer(str(MASTERS / "icon.svg"))
    assert renderer.isValid(), "the full-mark master did not load"
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()

    assert len(gold_runs(image)) > 1, (
        f"the full mark at {size} px puts its gold in one run — the arcs no longer read as a "
        "separate shape, so the shipped-asset checks above can no longer tell the two cuts apart"
    )
