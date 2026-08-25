"""Render every icon asset from the vendored SVG masters (`T-274`, re-cut by `T-276`).

Run from the repository root, in the project's virtualenv:

    .venv/bin/python tools/icons/render_icons.py

Writes `icon.png`, `icon-small.png`, `icon-{16,24,32,48,64,128,256,512}.png` and `icon.ico`
into `src/tracks_and_trails/resources/icons/`. **Every file in that directory is output.**
Nothing there is a source any more.

## The masters are vector, and they are the designer's own artboards

`masters/` holds three of the logo pack's square app-icon artboards, copied byte-for-byte from
**Logo Asset Package v1.1** — `05_AppIcons/SVG/<cut>/Brand-OnLight.svg`:

| master | pack cut | role |
|---|---|---|
| `icon.svg` | **Icon** | rendered at 32 px and above, and at `MASTER_SIZE` |
| `icon-small.svg` | **Small** | rendered at 16 and 24 px |
| `icon-standard.svg` | **Standard** | **not rendered** — see below |

`masters/PACK-README.txt` is the pack's own documentation and is the provenance for everything
this module asserts about them.

This replaced a pipeline that owned two 1024 px PNG masters and *derived* the small one from the
big one by masking pixels (`T-003`, `T-021`, `T-071`). All of that is gone:

- **No trim.** The old master carried a band of alpha-1..8 pixels that a naive crop baked in as
  margin. A vector artboard has no halo, and its bounds are the frame the designer drew.
- **No `FILL` rescale.** The artboards carry a margin rule of their own, and the ink fills
  **86.13%** of the frame height in *all three* cuts — measured here, and the pack states 86%.
  That is what makes the cuts sit at matching weight in the same cell, and rescaling each to its
  own bounds is exactly what would break it. `T-071` raised the mark from ~0.66 of the cell to
  0.92 because it read undersized in a taskbar; 0.8613 keeps that fix and hands the margin back
  to the artwork.
- **No derivation of any cut.** The pack authors all three. The Icon cut is the Standard artwork
  with only the two sound-wave arcs removed and the artboard re-centred around what is left —
  which is why it is a *delivered* artboard rather than two deleted paths: dropping the arcs
  from the Standard master leaves the mark **62 px off-centre in a 1024 px render** (`T-275`),
  and re-centring it in the repository would be a design judgement made in a script. The pack
  did it in the artboard instead — `viewBox` x moves from `7.1` to `-30.65` — and the delivered
  Icon cut measures equal left and right margins at every size this module renders.

## Rasterized at the target size, not downscaled to it

Each asset is rendered from the vector at its own size. Supersampling was measured and rejected:
rendering at 4x and smooth-scaling down moves the 16 px gold-pixel count by 2 and every other
size by 0 or 1, so it buys nothing and adds a step that could soften an edge.

## The split at 32 px, and why it is not the pack's 48

`SMALL_SIZES` is `{16, 24}`: the Small cut draws the two smallest sizes and the Icon cut draws
everything from 32 up.

**The pack puts its floor at 48 and this repository deliberately sits one step below it.** The
pack's reasoning is about legibility in the abstract — below 48 px the third tree and the mountain
notch stop resolving, and the Icon cut keeps both, so it inherits the Standard cut's floor rather
than earning a lower one. That reasoning is sound and is not disputed here. What overrides it is a
measurement the pack could not make: **which frame each slot on the target desktop actually
draws.**

Measured on a KDE 6 / Wayland session (KWin 6.7.3, 46 px panel, scale 1) with the running
application, by locating the mark in a screenshot and reading its ink bounds:

| slot | ink bounds | frame it resolves to |
|---|---|---|
| window titlebar | 14x18 px | **16 or 24** |
| panel task manager | 21x27 px | **32** |

So 32 is exactly the frame the taskbar draws, and 16/24 are what the titlebar draws. Splitting
there — rather than at 48 — is what puts the fuller mark in the panel while leaving the titlebar
the clean note-and-trail cut. **A split at 48 leaves both of these slots on the Small cut**, which
is what they showed until `T-277` and is the defect that task was filed for. It does **not** mean
the Icon cut was invisible: consumers that ask for 48 or more — the task switcher, and the About
dialog — were getting it from `T-276` onward (`T277-R1`). The maintainer ruled it on 2026-08-25
after seeing both cuts at 32 px side by side.

**This is the third position this boundary has held, and each move had a different cause.**
`T-274` put 32 on the full mark's side because that mark's *arcs* broke first at that size.
`T-276` moved it back down because the Icon cut has no arcs, so the trees and mountain decide it
and they fail lower. `T-277` moved it up again because legibility is not the only constraint:
legibility at a size is worth nothing if no slot a user looks at draws that size. **`T-275` asked
for this band on 2026-08-24, was refused on 2026-08-25, and is granted by the ruling the same
day** — the entry
records all three states rather than being rewritten.

*(The trees at 32 px are soft, and that was measured rather than missed: they read as texture more
than as three conifers, which `T-275` recorded and this module repeats so the next reader knows
the cost was priced in. `ai/evidence/` carries the side-by-side and the on-screen before/after.)*

## The Standard cut is vendored and never rendered

`icon-standard.svg` produces no asset. It is here because the suite's claim about the shipped
assets is *"the arcs are gone"*, and a predicate that looks for arcs is worth nothing until it
has been shown one — the Icon and Small cuts both lack them, so nothing else in the repository
can make `has_detached_arcs` return `True`. `tests/ui/test_resources.py` renders this master
purely as that known positive. Deleting it does not change a shipped byte; it silently converts
an enforced boundary into an assumed one, which is `T274-R1` and `T274-R3` both.
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

#: Sizes drawn from the Small cut rather than the Icon cut — see the module docstring.
SMALL_SIZES = frozenset({16, 24})

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
    icon_cut = load_master("icon.svg")
    small_cut = load_master("icon-small.svg")

    masters = {"icon.png": icon_cut, "icon-small.png": small_cut}
    for name, renderer in masters.items():
        image = render(renderer, MASTER_SIZE)
        print(f"{name}: ink spans {ink_height_fraction(image):.4f} of the frame height")
        (ICONS / name).write_bytes(encode_png(image))

    rendered = {
        size: render(small_cut if size in SMALL_SIZES else icon_cut, size)
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
