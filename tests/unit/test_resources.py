"""Guards the icon assets against silent loss or corruption (`T-003`, re-cut by `T-274`).

The assets are static files that no other test touches, so nothing in the suite would notice
if one were deleted, truncated, or regenerated at the wrong size (`T003-R3`). These checks read
the file headers directly rather than decoding the images: the project has no image library at
runtime, and header parsing is enough to catch every failure mode that matters here.

Qt-level loadability is asserted separately in `tests/ui/test_resources.py`, which needs a
`QGuiApplication`.

**`T-274` made every file here an output.** The two 1024 px PNGs used to be hand-delivered
masters — `icon.png` drawn, `icon-small.png` derived from it by masking — and they are now
rasterized from `tools/icons/masters/*.svg` like everything else. What that changes for this
module is only *why* the sizes are pinned, not the pinning: an asset regenerated at the wrong
size is still the failure nothing else would notice.
"""

import struct
from pathlib import Path

import pytest

import tracks_and_trails

ICONS = Path(tracks_and_trails.__file__).parent / "resources" / "icons"

#: Sizes T-003 is required to deliver as standalone PNGs.
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

#: Frames T-003 embeds in the Windows .ico. The 16/32/48/256 subset is the acceptance
#: criterion; the rest were delivered as well and are pinned so a regeneration cannot
#: quietly drop them.
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

#: Sizes rendered from the pack's Small cut rather than its Icon cut (`T-274`, re-cut by
#: `T-276`).
#:
#: Stated here rather than imported from `tools/icons/render_icons.py`, so that the expectation
#: is independent of the script that has to meet it. The pack's own measurement of this artwork
#: sets the boundary, and **what it measures changed at `T-276`**: the cut drawn above the split
#: no longer has sound-wave arcs to break into speckle, so the floor is now the third tree and
#: the mountain notch, which stop resolving below 48 px. The boundary lands on the same three
#: sizes for a different reason, which is why it is written out rather than left implied.
SMALL_SIZES = (16, 24, 32)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def read_png_size(path: Path) -> tuple[int, int]:
    """Return (width, height) from a PNG's IHDR chunk, which is always the first chunk."""
    header = path.read_bytes()[:24]
    if header[:8] != PNG_SIGNATURE:
        raise ValueError(f"{path.name} is not a PNG")
    if header[12:16] != b"IHDR":
        raise ValueError(f"{path.name} does not start with IHDR")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def read_ico_sizes(path: Path) -> list[int]:
    """Return the square frame sizes declared in an .ico directory, ascending.

    A dimension byte of 0 means 256 — the format cannot express 256 in one byte.
    """
    data = path.read_bytes()
    reserved, image_type, count = struct.unpack("<HHH", data[:6])
    if reserved != 0 or image_type != 1:
        raise ValueError(f"{path.name} is not an .ico")
    sizes = []
    for i in range(count):
        entry = data[6 + i * 16 : 22 + i * 16]
        width, height = entry[0] or 256, entry[1] or 256
        if width != height:
            raise ValueError(f"{path.name} frame {i} is not square: {width}x{height}")
        sizes.append(width)
    return sorted(sizes)


def test_source_master_is_present_and_full_size() -> None:
    """`icon.png` is the Icon cut at 1024, the largest raster the package ships."""
    assert read_png_size(ICONS / "icon.png") == (1024, 1024)


def test_small_cut_is_present_and_full_size() -> None:
    """`icon-small.png` is the Small cut at 1024 — the same mark without the landscape.

    Kept at full size even though nothing displays it there: it is the only place the Small cut
    can be *looked at*, and a 1024 px render of it is what makes a changed small cut visible to a
    reviewer instead of arriving as a 16 px diff.
    """
    assert read_png_size(ICONS / "icon-small.png") == (1024, 1024)


def test_the_svg_masters_are_present() -> None:
    """The three vendored artboards (`T-274`, third added by `T-276`).

    They live outside the package — nothing at runtime reads them — so no other check in the
    suite touches them, and losing them would leave a set of rasters with no way back to the
    artwork. That is the same failure mode this module exists for, one level up.

    **`icon-standard.svg` renders no asset and is required anyway.** It is the only cut in the
    repository that still carries the sound-wave arcs, and `tests/ui/test_resources.py` needs it
    as the known positive for `has_detached_arcs` — a predicate every shipped asset must now
    make `False`. Losing it would leave that assertion passing and unfalsifiable, which is the
    quiet failure mode rather than the loud one, so it is named here as well.
    """
    masters = Path(__file__).resolve().parents[2] / "tools" / "icons" / "masters"
    assert (masters / "icon.svg").is_file()
    assert (masters / "icon-small.svg").is_file()
    assert (masters / "icon-standard.svg").is_file()


@pytest.mark.parametrize("size", PNG_SIZES)
def test_derived_png_exists_at_its_declared_size(size: int) -> None:
    path = ICONS / f"icon-{size}.png"
    assert path.is_file(), f"missing derived icon: {path.name}"
    assert read_png_size(path) == (size, size)


def test_ico_declares_every_required_frame() -> None:
    """The .ico must carry the full frame set, not just the ones Windows asks for first."""
    assert read_ico_sizes(ICONS / "icon.ico") == sorted(ICO_SIZES)


def test_no_unexpected_files_in_the_icon_directory() -> None:
    """A stray asset is usually a half-finished regeneration; fail loudly rather than ship it."""
    expected = {"icon.png", "icon-small.png", "icon.ico"} | {f"icon-{s}.png" for s in PNG_SIZES}
    assert {p.name for p in ICONS.iterdir()} == expected
