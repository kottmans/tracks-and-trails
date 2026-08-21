"""Render every icon asset from the vendored SVG masters (`T-274`).

Run from the repository root, in the project's virtualenv:

    .venv/bin/python tools/icons/render_icons.py

Writes `icon.png`, `icon-small.png`, `icon-{16,24,32,48,64,128,256,512}.png` and `icon.ico`
into `src/tracks_and_trails/resources/icons/`. **Every file in that directory is output.**
Nothing there is a source any more.

## The masters are vector, and they are the designer's own artboards

`masters/icon.svg` and `masters/icon-small.svg` are the logo pack's square icon artboards,
copied byte-for-byte — `tracks-and-trails-icon.svg` and `tracks-and-trails-small-icon.svg`.
`masters/PACK-README.txt` is the pack's own documentation and is the provenance for everything
this module asserts about them.

This replaced a pipeline that owned two 1024 px PNG masters and *derived* the small one from the
big one by masking pixels (`T-003`, `T-021`, `T-071`). All of that is gone:

- **No trim.** The old master carried a band of alpha-1..8 pixels that a naive crop baked in as
  margin. A vector artboard has no halo, and its bounds are the frame the designer drew.
- **No `FILL` rescale.** The artboards carry an 8% margin rule of their own, and the ink fills
  **86.13%** of the frame height in *both* cuts — measured here, and the pack states 86.2%. That
  is what makes the two cuts sit at matching weight in the same cell, and rescaling each to its
  own bounds is exactly what would break it. `T-071` raised the mark from ~0.66 of the cell to
  0.92 because it read undersized in a taskbar; 0.8613 keeps that fix and hands the margin back
  to the artwork.
- **No derivation of the small cut.** The pack authors it. Two of its three paths are
  byte-identical to the master's, so the two cannot drift into different marks — which is what
  `render_small_glyph.py` existed to guarantee and could only approximate.

## Rasterized at the target size, not downscaled to it

Each asset is rendered from the vector at its own size. Supersampling was measured and rejected:
rendering at 4x and smooth-scaling down moves the 16 px gold-pixel count by 2 and every other
size by 0 or 1, so it buys nothing and adds a step that could soften an edge.

## The split at 32 px

`SMALL_SIZES` is where the full mark stops being drawn and the reduced cut takes over, and the
pack's own measurement of *this* artwork sets it: the sound-wave arcs break into speckle at 32 px
and the mountain has vanished, so 16, 24 and 32 come from `icon-small.svg`. The repository's
previous boundary was 32 too — but as the smallest size that kept the *full* mark, measured on
artwork that no longer exists (`T003-R2`).
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

#: Sizes drawn from the reduced cut rather than the full mark — see the module docstring.
SMALL_SIZES = frozenset({16, 24, 32})

#: The size of the two PNG masters. They are output like everything else now, and they stay
#: because the packaged application ships them and `tests/` uses `icon.png` as a sample image.
MASTER_SIZE = 1024

ROOT = Path(__file__).resolve().parents[2]
MASTERS = Path(__file__).resolve().parent / "masters"
ICONS = ROOT / "src" / "tracks_and_trails" / "resources" / "icons"


def render(renderer: QSvgRenderer, size: int) -> QImage:
    """`renderer`'s artboard rasterized into a transparent `size` square."""
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return image


def encode_png(image: QImage) -> bytes:
    """`image` as PNG bytes, without going through a file."""
    # **Default-constructed, not `QBuffer(QByteArray())`.** That overload takes a reference to a
    # byte array the caller owns, and handing it a temporary leaves the buffer pointing at freed
    # memory — which segfaults on the first write rather than raising.
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise SystemExit("Qt refused to encode a PNG")
    buffer.close()
    return bytes(buffer.data())


def write_ico(frames: dict[int, QImage], path: Path) -> None:
    """Write a PNG-compressed .ico carrying `frames` exactly as rendered.

    Built by hand rather than through an image library's ICO writer so each frame is the one
    this script rendered at that size, not a re-downscale of a single source image.
    """
    sizes = sorted(frames)
    encoded = [encode_png(frames[size]) for size in sizes]

    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = len(header) + 16 * len(sizes)
    directory = b""
    for size, payload in zip(sizes, encoded, strict=True):
        # A dimension of 256 is stored as 0; the format has one byte per side.
        dimension = 0 if size == 256 else size
        directory += struct.pack(
            "<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(payload), offset
        )
        offset += len(payload)

    path.write_bytes(header + directory + b"".join(encoded))


def load_master(name: str) -> QSvgRenderer:
    renderer = QSvgRenderer(str(MASTERS / name))
    if not renderer.isValid():
        raise SystemExit(f"{name} is not a valid SVG")
    frame = renderer.defaultSize()
    if frame.width() != frame.height():
        raise SystemExit(f"{name} is not square: {frame.width()}x{frame.height()}")
    return renderer


def ink_height_fraction(image: QImage) -> float:
    """The share of the frame's height the artwork's visible pixels span.

    Printed rather than asserted, because it is the number the docstring's claim about matching
    weight rests on and the cheapest way to notice a master that was re-exported with a
    different margin.
    """
    rows = [
        y
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).alpha() > 8
    ]
    if not rows:
        raise SystemExit("a master rendered fully transparent")
    return (max(rows) - min(rows) + 1) / image.height()


def main() -> None:
    full = load_master("icon.svg")
    small = load_master("icon-small.svg")

    masters = {"icon.png": full, "icon-small.png": small}
    for name, renderer in masters.items():
        image = render(renderer, MASTER_SIZE)
        print(f"{name}: ink spans {ink_height_fraction(image):.4f} of the frame height")
        (ICONS / name).write_bytes(encode_png(image))

    rendered = {
        size: render(small if size in SMALL_SIZES else full, size)
        for size in sorted({*PNG_SIZES, *ICO_SIZES})
    }

    for size in PNG_SIZES:
        (ICONS / f"icon-{size}.png").write_bytes(encode_png(rendered[size]))
    write_ico({size: rendered[size] for size in ICO_SIZES}, ICONS / "icon.ico")

    print(
        f"wrote 2 masters, {len(PNG_SIZES)} PNGs and an .ico with {len(ICO_SIZES)} frames "
        f"to {ICONS}"
    )


if __name__ == "__main__":
    # Read when the application is constructed, not at import, so it belongs here: this script
    # draws into images and never opens a window, and a headless machine has no display to fail
    # over.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    # **Module level, and it must stay there.** Qt needs a live application object before a
    # `QImage` can be painted, and binding it to a local in `main()` drops the last reference
    # when that frame returns — which destroys the platform integration under the renderers
    # still holding it and takes the process down with a segfault on the way out.
    APPLICATION = QGuiApplication(sys.argv)
    main()
