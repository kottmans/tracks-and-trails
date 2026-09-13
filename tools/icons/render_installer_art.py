"""Render the installer's wizard artwork from the logo masters (`T-322`).

    QT_QPA_PLATFORM=offscreen python tools/icons/render_installer_art.py

**Why this exists.** `packaging/tracks-and-trails.iss` set `SetupIconFile` but never the wizard
images, so every installer page carried Inno Setup's stock box-and-disc artwork beside our name.
The maintainer's verdict on the first real install, 2026-09-12: the logo would look more
professional. It would, and it is also the one screen where a stranger decides whether to trust
an unsigned download (`REL-005`).

**From the SVG masters, not by scaling a PNG.** `render_icons.py` already owns the masters and the
rule for which cut draws at which size; this reuses its loader and rasteriser, so the installer
art cannot drift from the application icon.

**Two images, several sizes each.** Inno picks the closest match to the display's DPI from a
comma-separated list, and an image scaled up by Windows is a blurred logo on the very screen this
is for. The sizes are the ones Inno Setup documents for `WizardStyle=modern` at 100% to 250%.

- **Small** — the top-right corner of every inner page. White, because that is the page header's
  own colour, so the logo sits on the page rather than in a box.
- **Large** — the left panel of the finished page, on warm sand, so it reads as a deliberate
  panel beside the white page.

**Light only.** The masters are the pack's *Brand-OnLight* cut: dark green and gold that disappear
on a dark panel. The installer uses the light modern style, so that is the right pairing.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from PySide6.QtSvg import QSvgRenderer
from render_icons import ROOT, load_master, render

OUT = ROOT / "packaging" / "installer-art"

#: `WizardSmallImageFile` sizes Inno Setup documents for 100%, 150%, 200% and 250%.
SMALL_SIZES = ((55, 55), (83, 80), (110, 106), (138, 140))

#: `WizardImageFile` sizes for the same scales.
LARGE_SIZES = ((164, 314), (246, 459), (328, 604), (410, 797))

#: The inner-page header is the window colour, which is white in the light modern style.
SMALL_GROUND = QColor("#FFFFFF")

#: Warm sand, chosen by the maintainer on 2026-09-12 from four rendered options beside a mock
#: wizard page: pale green, warm sand, brand green and deep evergreen. It picks up the trail's gold
#: and reads as a deliberate panel beside the white page, and it keeps the *Brand-OnLight* logo, so
#: no second master is needed. (The first cut used the app's near-white window colour, which was
#: too faint to read as a background at all.)
LARGE_GROUND = QColor("#F3EBDA")

#: How much of the large panel's width the logo's **ink** takes, and where its centre sits.
#:
#: **Ink, not artboard** — the maintainer asked for the logo bigger, since this panel is one of the
#: few places anyone sees it large. The master's artboard carries the designer's margin: measured,
#: the ink is only 68% of the artboard's width. Sizing the artboard made the logo 63% of the panel;
#: sizing the ink directly lets it take most of the width, with the margin falling outside the
#: panel where it is transparent anyway.
#:
#: Slightly above the middle, because the optical centre of a tall panel is above its measured one.
LARGE_INK_WIDTH = 0.86
LARGE_LOGO_CENTRE = 0.44

#: The corner slot is fixed by Inno, so the gain there is only the margin: ink to 92% of its height.
SMALL_INK_HEIGHT = 0.92


def ink_fraction(renderer: QSvgRenderer) -> tuple[float, float]:
    """The share of the artboard's width and height the logo actually inks.

    Measured from a render rather than hard-coded, so a re-cut master resizes correctly. The ink
    is centred in the pack's artboards, which is what lets `compose` centre the artboard.
    """
    image = render(renderer, 512)
    xs = [x for x in range(512) for y in range(0, 512, 4) if image.pixelColor(x, y).alpha() > 8]
    ys = [y for y in range(512) for x in range(0, 512, 4) if image.pixelColor(x, y).alpha() > 8]
    return (max(xs) - min(xs)) / 512, (max(ys) - min(ys)) / 512


def compose(width: int, height: int, ground: QColor, side: float, centre_y: float) -> QImage:
    """An opaque image of `ground` with the logo's artboard as a `side` square at `centre_y`."""
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(ground)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    target = QRectF((width - side) / 2, centre_y - side / 2, side, side)
    # The master artboard carries the designer's own margin, so it is drawn edge to edge.
    load_master("icon.svg").render(painter, target)
    painter.end()
    return image


def main() -> int:
    QGuiApplication.instance() or QGuiApplication(sys.argv)
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    ink_w, ink_h = ink_fraction(load_master("icon.svg"))
    for width, height in SMALL_SIZES:
        side = height * SMALL_INK_HEIGHT / ink_h
        image = compose(width, height, SMALL_GROUND, side, height / 2)
        path = OUT / f"wizard-small-{width}x{height}.png"
        if not image.save(str(path), "PNG"):
            raise SystemExit(f"could not write {path}")
        written.append(path)
    for width, height in LARGE_SIZES:
        side = width * LARGE_INK_WIDTH / ink_w
        image = compose(width, height, LARGE_GROUND, side, height * LARGE_LOGO_CENTRE)
        path = OUT / f"wizard-large-{width}x{height}.png"
        if not image.save(str(path), "PNG"):
            raise SystemExit(f"could not write {path}")
        written.append(path)
    for path in written:
        print(f"{path.relative_to(ROOT)}  {path.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
