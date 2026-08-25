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

`T-276` moved the sizes at and above 48 px onto the pack's **Icon** cut, which is the Standard
artwork with the two sound-wave arcs removed. **That broke every check in this module that told
one shipped cut from the other**, because all of them read gold and the Icon cut's gold is the
trail alone — indistinguishable from the Small cut's. The cut identity is now a pair: gold says
whether the arcs are there, and `green_coverage` says whether the landscape is.
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

#: The vendored SVG artboards (`T-274`). Two of the three are what the shipped assets are
#: rendered from; `icon-standard.svg` ships nothing and exists only so the control tests can be
#: handed a cut that still has arcs (`T-276`). Reached only by those controls, which need each
#: cut at a size no shipped asset uses it at.
MASTERS = Path(__file__).resolve().parents[2] / "tools" / "icons" / "masters"

ALL_ASSETS = ["icon.png", "icon-small.png", "icon.ico", *(f"icon-{s}.png" for s in PNG_SIZES)]

#: Trail-gold pixels the 16 px asset must carry (`T-274`, replacing `T-021`'s floor of 16).
#:
#: **Measured 2026-08-21 on the Small cut: 9.** The floor sits below it because the count alone
#: cannot tell any two cuts apart — at 16 px the Standard cut carries *11* and the Icon cut *11*,
#: both **more** gold than the Small cut's 9. What separates the cuts is
#: `test_the_small_cut_is_what_ships_at_every_small_size`'s two assertions; this number only has
#: to catch a trail that has thinned to nothing, so it leaves room for redrawing.
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


#: Sizes at or above the pack's 48 px floor: everything the Small cut does not cover.
#:
#: **Derived by subtraction, and that is only safe while there are exactly two bands.** `T-275`
#: proposed a third — the Icon cut at 32 px with the Standard cut kept above — and named this
#: line as the trap: a third band has to be subtracted here too, or these tests run at a size
#: whose asset was built to a different cut. The ruling of 2026-08-25 refused that third band, so
#: two bands is the current shape rather than a shape nobody considered changing.
LARGE_SIZES = tuple(size for size in PNG_SIZES if size not in SMALL_SIZES)

#: How large a second run of gold has to be, against the largest, to count as an arc (`T274-R3`).
#:
#: **A bare "more than one run" does not identify a cut, and 64 px is where that shows.** The
#: Small cut sheds a single antialiasing pixel off its trail there — `[185, 1]` — so it satisfies
#: a `> 1` count. The Icon cut sheds one at 48 px, `[103, 1]`, for the same reason.
#:
#: Measured 2026-08-25, second run as a share of the largest:
#:
#: | size | Standard cut | Icon cut | Small cut |
#: |---|---|---|---|
#: | 48 | 12.75% | **0.97%** | none |
#: | 64 | 11.48% | none | **0.54%** |
#: | 128 | 12.32% | none | none |
#: | 256 | 11.80% | none | none |
#: | 512 | 12.02% | none | none |
#:
#: The arcs hold 11.5 to 12.8% wherever they exist, an order of magnitude above any crumb. 5%
#: sits 2.3x under the tightest real arc and 5.2x over the largest crumb.
ARC_SHARE = 0.05


def has_detached_arcs(image: QImage) -> bool:
    """Whether the image's gold carries a second shape big enough to be a sound-wave arc.

    **This identified the shipped cut until `T-276` and now identifies the one that is gone.**
    The Standard cut's arcs are gold, are never joined to the trail, and are a substantial
    fraction of it; neither shipping cut has them, so every shipped asset must make this
    `False`. Size is what separates an arc from a stray pixel, which is `T274-R3`.
    """
    runs = gold_runs(image)
    return len(runs) > 1 and runs[1] >= ARC_SHARE * runs[0]


def is_forest_green(colour: QColor) -> bool:
    """Whether an opaque rendered pixel belongs to the mark's green mass.

    Mass tone is `#1E5E47` — (30, 94, 71), green-dominant with low red. Compared as a relation
    rather than against the exact value, for the same reason `is_trail_gold` is: these pixels are
    antialiased blends of the mass against the gold trail and the transparent ground.
    """
    if colour.alpha() < 128:
        return False
    return (
        colour.green() > colour.red() + 20
        and colour.green() > colour.blue() + 10
        and colour.red() < 150
    )


def green_coverage(image: QImage) -> float:
    """The share of the *frame* the green mass covers.

    Normalized by frame area rather than by ink, because the frame is the one thing all three
    cuts share exactly: the pack draws each on the same 1244-unit square canvas with the mark at
    86% of the canvas height, which this module measures as 0.8613 in every cut. Two cuts of the
    same artwork on the same canvas therefore differ in green mass by how much landscape they
    carry, and by nothing else.
    """
    green = sum(
        is_forest_green(image.pixelColor(x, y))
        for x in range(image.width())
        for y in range(image.height())
    )
    return green / (image.width() * image.height())


#: Green coverage that separates the two cuts that ship (`T-276`).
#:
#: **This is what tells the Icon cut from the Small cut, and gold cannot do it.** The Icon cut is
#: the Standard artwork with only the sound-wave arcs removed, so its gold *is* the trail alone
#: and falls in one run — exactly like the Small cut's. Every gold property that separated the
#: shipped cuts before `T-276` is blind to this pair. What separates them is the landscape the
#: Small cut drops: three trees and the mountain, all of it green mass.
#:
#: Measured 2026-08-25, over the masters at every size the shipped assets use:
#:
#: | size | Icon cut | Small cut |
#: |---|---|---|
#: | 16 | 0.1953 | 0.1172 |
#: | 24 | 0.1875 | 0.1250 |
#: | 32 | 0.1895 | 0.1172 |
#: | 48 | **0.1832** | 0.1189 |
#: | 64 | 0.1846 | **0.1272** |
#: | 128 | 0.1885 | 0.1241 |
#: | 256 | 0.1852 | 0.1258 |
#: | 512 | 0.1859 | 0.1249 |
#:
#: The two bands never approach each other: the Icon cut's worst size is 0.1832 and the Small
#: cut's worst is 0.1272, a gap of 44%. **0.15 sits 17.9% above the Small cut's worst case and
#: 18.1% below the Icon cut's** — deliberately near the midpoint, because neither direction is
#: the one more likely to drift.
GREEN_FLOOR = 0.15


def rendered_master(name: str, size: int) -> QImage:
    """One of the vendored artboards rasterized at `size`, the way the renderer does it."""
    renderer = QSvgRenderer(str(MASTERS / name))
    assert renderer.isValid(), f"{name} did not load"
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return image


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
    """Below the split, every shipped asset is the Small cut.

    **Two assertions, because after `T-276` one of them stopped being enough.** Connectivity —
    the gold falls in a single unbroken run — is what `T-274` used, and it still rejects the
    Standard cut, whose arcs are a separate gold shape at every size. It does **not** reject the
    Icon cut, which has no arcs either and whose gold is also exactly one run. The green floor is
    what catches that: the Small cut has dropped the trees and the mountain, so it carries a
    third less green mass than the cut drawn above the split.

    **Parameterized over every small size and both sources, which is `T274-R1`.** The first
    version of this asserted 16 px alone while `SMALL_SIZES` claimed three, so a renderer set to
    `{16}` regenerated 24 and 32 — PNGs and `.ico` frames alike — back to the other cut and the
    suite stayed green. A boundary stated in one file and enforced at one of its three sizes is
    not enforced.

    Counted from the rendered pixmap rather than the file, because Qt is what picks and scales
    the asset the user sees — the same reason this module exists alongside
    `tests/unit/test_resources`.
    """
    image = shipped(source, size)
    runs = gold_runs(image)

    assert runs, f"the {size} px {source} carries no trail gold at all"
    assert len(runs) == 1, (
        f"the {size} px {source} puts its gold in {len(runs)} separate runs ({runs}) — the "
        "shipping cuts' gold is the trail alone and is always one run, so this is the Standard "
        "cut, whose arcs are a separate shape at every size"
    )

    coverage = green_coverage(image)
    assert coverage < GREEN_FLOOR, (
        f"the {size} px {source} covers {coverage:.4f} of its frame in green, at or over the "
        f"{GREEN_FLOOR} floor — that is the Icon cut, which carries the trees and the mountain "
        f"and is drawn at {min(LARGE_SIZES)} px and above, not below it"
    )


@pytest.mark.parametrize(("source", "size"), sources_for(LARGE_SIZES))
def test_the_icon_cut_is_what_ships_at_and_above_the_split(
    qapp: QApplication, source: str, size: int
) -> None:
    """And at or above the split it is the Icon cut — both properties, read the other way.

    **This half is not required by `T274-R1` and is here because the hole is symmetric.** With
    only the small sizes asserted, a renderer that moved 48 px — or all of them — onto the Small
    cut would pass every check in this module, and the landscape would quietly leave the icon at
    the sizes that can carry it.

    The second assertion is the one `T-276` is *for*. The whole point of the Icon cut is that the
    sound-wave arcs are gone, and a change that shipped the Standard cut here would put them
    back. Nothing else in the suite would notice: the arcs are two small gold specks, and every
    other property in this module is satisfied by both cuts.
    """
    image = shipped(source, size)

    coverage = green_coverage(image)
    assert coverage >= GREEN_FLOOR, (
        f"the {size} px {source} covers only {coverage:.4f} of its frame in green, under the "
        f"{GREEN_FLOOR} floor — that is the Small cut, which drops the trees and the mountain "
        f"and is drawn below {min(LARGE_SIZES)} px, not at or above it"
    )

    assert not has_detached_arcs(image), (
        f"the {size} px {source} carries a second gold shape big enough to be a sound-wave arc "
        "— that is the Standard cut. The Icon cut is the one that removes the arcs, and it is "
        "what ships here"
    )


@pytest.mark.parametrize("size", SMALL_SIZES)
def test_the_green_floor_rejects_the_icon_cut_below_the_split(
    qapp: QApplication, size: int
) -> None:
    """Control: the cut that must not ship small **fails** what the small assets pass.

    A floor is worth nothing if both cuts sit on the same side of it, and this is the only place
    that can be established below the split — every shipped asset there is the Small cut, so
    nothing else in the suite ever draws the Icon cut small enough to break. It reaches past the
    shipped assets into `tools/icons/masters/` deliberately: the point is to feed the check a
    known positive and watch it fire.
    """
    coverage = green_coverage(rendered_master("icon.svg", size))
    assert coverage >= GREEN_FLOOR, (
        f"the Icon cut at {size} px covers {coverage:.4f} of its frame in green, under the "
        f"{GREEN_FLOOR} floor — so test_the_small_cut_is_what_ships_at_every_small_size would "
        "accept it and cannot tell the two shipping cuts apart there"
    )


@pytest.mark.parametrize("size", LARGE_SIZES)
def test_the_green_floor_rejects_the_small_cut_above_the_split(
    qapp: QApplication, size: int
) -> None:
    """The same control on the other side, and the one `T274-R3` was missing.

    **The complement shipped without a control once, and that is exactly how it escaped.** Its
    small-size sibling had one and this side had none, so a predicate that both cuts satisfied at
    64 px looked identical to one that discriminated. The reviewer found it by regenerating with
    `SMALL_SIZES = {16, 24, 32, 64}` and watching 45 tests pass over a swapped asset.

    So: render the Small cut at every size the complement guards and require that it **fails**
    the property. This is the assertion that fixes the class rather than the instance.
    """
    coverage = green_coverage(rendered_master("icon-small.svg", size))
    assert coverage < GREEN_FLOOR, (
        f"the Small cut at {size} px covers {coverage:.4f} of its frame in green, at or over the "
        f"{GREEN_FLOOR} floor — so test_the_icon_cut_is_what_ships_at_and_above_the_split cannot "
        "tell the two shipping cuts apart there"
    )


@pytest.mark.parametrize("size", LARGE_SIZES)
def test_the_arc_predicate_fires_on_the_cut_that_has_arcs(qapp: QApplication, size: int) -> None:
    """Control: `has_detached_arcs` must return `True` for something.

    **Every cut that ships lacks arcs, so every arc assertion in this module is a negative** —
    and a negative that has never been shown a positive is not a check, it is a sentence. This is
    the only test in the repository that can make the predicate fire, and it is the whole reason
    `icon-standard.svg` is vendored despite producing no asset.

    Delete that master and this test is what fails, loudly, instead of
    `test_the_icon_cut_is_what_ships_at_and_above_the_split` quietly becoming unfalsifiable.
    """
    assert has_detached_arcs(rendered_master("icon-standard.svg", size)), (
        f"the Standard cut at {size} px does not satisfy the arc property, so the arcs no longer "
        "read as a separate gold shape and no shipped-asset check in this module can tell the "
        "Standard cut from the Icon cut"
    )


@pytest.mark.parametrize("size", SMALL_SIZES)
def test_the_gold_run_predicate_fires_on_the_cut_that_has_arcs(
    qapp: QApplication, size: int
) -> None:
    """The same control for the connectivity half of the small-size check.

    `test_the_small_cut_is_what_ships_at_every_small_size` asserts exactly one run of gold, and
    the Standard cut is the only thing that can break it. **This side asserts one run while the
    large side speaks in fractions**, and the difference is measured rather than stylistic: the
    shipped small assets carry exactly one run at 16, 24 and 32, so the stricter form is true and
    a crumb appearing there would be a real change. At 48 px and up both shipping cuts do shed
    one, which is why `ARC_SHARE` exists.
    """
    runs = gold_runs(rendered_master("icon-standard.svg", size))
    assert len(runs) > 1, (
        f"the Standard cut at {size} px puts its gold in one run — the arcs no longer read as a "
        "separate shape, so the connectivity assertion above can no longer reject it"
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
