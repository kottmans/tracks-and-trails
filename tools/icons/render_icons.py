"""Render every derived icon asset from the 1024x1024 master (`T-071`).

Run from the repository root, with Pillow available:

    python3 -m pip install --user pillow
    python3 tools/icons/render_icons.py

Writes `icon-{16,24,32,48,64,128,256,512}.png` and `icon.ico` into
`src/tracks_and_trails/resources/icons/`. It never writes `icon.png`, which is the master
`T-003` delivered and the only file here that is not reproducible from something else.

Two details carry the whole point of `T-071`, and a future regeneration that drops either one
puts the undersized icon straight back:

`VISIBLE_ALPHA` — the master carries a 194 px band of alpha-1..8 pixels below the artwork.
They are invisible at any size, but a crop that trims on "alpha > 0" treats them as content
and bakes them in as empty margin. Trimming at a threshold is what removes it.

`FILL` — the mark is scaled to occupy this fraction of the canvas on its longer side. The
assets this script replaced sat at ~0.66, which is why the icon read as undersized in a
taskbar beside icons that fill their cell.
"""

from __future__ import annotations

import struct
from io import BytesIO
from pathlib import Path

from PIL import Image

#: Alpha at or below this is treated as empty when finding the artwork's bounds. The master's
#: invisible halo tops out at 8; the artwork's own antialiased edge runs far above it, so any
#: threshold in roughly 8..64 gives the same crop.
VISIBLE_ALPHA = 8

#: Fraction of the canvas the mark spans on its longer side. Leaves a hair of margin so the
#: artwork does not touch the edge, which reads as clipped.
FILL = 0.92

PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

ICONS = Path(__file__).resolve().parents[2] / "src" / "tracks_and_trails" / "resources" / "icons"


def visible_artwork(master: Image.Image) -> Image.Image:
    """The master cropped to its visible pixels, ignoring the sub-threshold halo."""
    mask = master.getchannel("A").point(lambda value: 255 if value > VISIBLE_ALPHA else 0)
    bounds = mask.getbbox()
    if bounds is None:
        raise SystemExit("the master is fully transparent above the visible-alpha threshold")
    return master.crop(bounds)


def render(art: Image.Image, size: int) -> Image.Image:
    """`art` scaled to FILL of a `size` square canvas and centred on it."""
    width, height = art.size
    scale = (size * FILL) / max(width, height)
    scaled = art.resize(
        (max(1, round(width * scale)), max(1, round(height * scale))), Image.LANCZOS
    )
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(scaled, ((size - scaled.width) // 2, (size - scaled.height) // 2))
    return canvas


def write_ico(frames: dict[int, Image.Image], path: Path) -> None:
    """Write a PNG-compressed .ico carrying `frames` exactly as rendered.

    Built by hand rather than through Pillow's ICO writer so each frame is the one this script
    rendered at that size, not a re-downscale of a single source image.
    """
    sizes = sorted(frames)
    encoded = []
    for size in sizes:
        buffer = BytesIO()
        frames[size].save(buffer, format="PNG", optimize=True)
        encoded.append(buffer.getvalue())

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


def main() -> None:
    master = Image.open(ICONS / "icon.png").convert("RGBA")
    if master.size != (1024, 1024):
        raise SystemExit(f"expected a 1024x1024 master, found {master.size[0]}x{master.size[1]}")

    art = visible_artwork(master)
    print(f"master artwork: {art.width}x{art.height} after trimming at alpha > {VISIBLE_ALPHA}")

    rendered = {size: render(art, size) for size in sorted({*PNG_SIZES, *ICO_SIZES})}

    for size in PNG_SIZES:
        rendered[size].save(ICONS / f"icon-{size}.png", format="PNG", optimize=True)
    write_ico({size: rendered[size] for size in ICO_SIZES}, ICONS / "icon.ico")

    print(f"wrote {len(PNG_SIZES)} PNGs and an .ico with {len(ICO_SIZES)} frames to {ICONS}")


if __name__ == "__main__":
    main()
