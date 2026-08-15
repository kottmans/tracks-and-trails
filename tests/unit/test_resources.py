"""Guards the icon assets delivered by T-003 against silent loss or corruption.

The assets are static files that no other test touches, so nothing in the suite would notice
if one were deleted, truncated, or regenerated at the wrong size (`T003-R3`). These checks read
the file headers directly rather than decoding the images: the project has no image library at
runtime, and header parsing is enough to catch every failure mode that matters here.

Qt-level loadability is asserted separately in `tests/ui/test_resources.py`, which needs a
`QGuiApplication`.
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
    """`icon.png` is the 1024x1024 master the 32 px and larger assets derive from."""
    assert read_png_size(ICONS / "icon.png") == (1024, 1024)


def test_small_glyph_master_is_present_and_full_size() -> None:
    """`icon-small.png` is the reduced glyph `T-021` renders 16 px and 24 px from.

    Full size for the same reason `icon.png` is: every derived asset is a downscale, and a master
    that has itself been shrunk cannot be told from one that has not once it is written out.

    It is **derived** from `icon.png` by `tools/icons/render_small_glyph.py` rather than drawn, so
    that the reduced mark cannot drift into a different mark — which is `T-021`'s second acceptance
    criterion and the one a file check can help with.
    """
    assert read_png_size(ICONS / "icon-small.png") == (1024, 1024)


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
