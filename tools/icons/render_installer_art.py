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
- **Large** — the left panel of the finished page. The application's light window colour
  (`ui/theme.py`), a shade off the white page, so it reads as a deliberate panel.

**Light only.** The masters are the pack's *Brand-OnLight* cut: dark green and gold that disappear
on a dark panel. The installer uses the light modern style, so that is the right pairing.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_icons import ROOT, load_master

OUT = ROOT / "packaging" / "installer-art"

#: `WizardSmallImageFile` sizes Inno Setup documents for 100%, 150%, 200% and 250%.
SMALL_SIZES = ((55, 55), (83, 80), (110, 106), (138, 140))

#: `WizardImageFile` sizes for the same scales.
LARGE_SIZES = ((164, 314), (246, 459), (328, 604), (410, 797))

#: The inner-page header is the window colour, which is white in the light modern style.
SMALL_GROUND = QColor("#FFFFFF")

#: `ui/theme.py` LIGHT `window` — a deliberate panel beside a white page, not a stock grey.
LARGE_GROUND = QColor("#F5F7F4")

#: How much of the large panel's width the logo takes, and where its centre sits vertically.
#: Slightly above the middle, because the optical centre of a tall panel is above its measured one.
LARGE_LOGO_WIDTH = 0.92
LARGE_LOGO_CENTRE = 0.42


def compose(width: int, height: int, ground: QColor, side: float, centre_y: float) -> QImage:
    """An opaque image of `ground` with the logo as a `side` square centred at `centre_y`."""
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
    for width, height in SMALL_SIZES:
        side = float(min(width, height))
        image = compose(width, height, SMALL_GROUND, side, height / 2)
        path = OUT / f"wizard-small-{width}x{height}.png"
        if not image.save(str(path), "PNG"):
            raise SystemExit(f"could not write {path}")
        written.append(path)
    for width, height in LARGE_SIZES:
        image = compose(
            width, height, LARGE_GROUND, width * LARGE_LOGO_WIDTH, height * LARGE_LOGO_CENTRE
        )
        path = OUT / f"wizard-large-{width}x{height}.png"
        if not image.save(str(path), "PNG"):
            raise SystemExit(f"could not write {path}")
        written.append(path)
    for path in written:
        print(f"{path.relative_to(ROOT)}  {path.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
