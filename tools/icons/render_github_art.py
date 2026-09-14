"""Render the GitHub page artwork from the logo master.

    QT_QPA_PLATFORM=offscreen python tools/icons/render_github_art.py

**Why this exists.** The maintainer asked for the logo on the repository page, 2026-09-14. It
appears in two places, and neither can use the shipped icon as it is:

- **The README header.** The shipped icon is the *Brand-OnLight* colourway: its `#1E5E47` mass
  tone measures 2.5:1 against GitHub's dark ground `#0d1117`, so the trees and note all but
  disappear. So the light theme gets the OnLight cut and the dark theme the OnDark one.
  **Both are cropped to the ink**, because the maintainer found the first header too small: the
  master's square artboard is only 68% ink across, so `width="160"` drew a logo about 110 px
  wide. The crop keeps the pack's minimum clear space, 4% of the artwork width, on every side.
- **The social preview**, the card shown when the repository link is shared. GitHub wants an
  opaque 1280x640 image, uploaded by hand under *Settings → General → Social preview*. There is
  no API for it, so this file is only ever the source of that upload.

**Brand-OnDark by the pack's own values, not a recolour.** `masters/PACK-README.txt` defines
Brand-OnDark as mass tone `#48906C` with the same `#D9A24C` accent, and says every colourway of a
cut shares its geometry exactly. The repository vendors only the OnLight master, so the OnDark cut
is that master with its one mass-tone value substituted — the colourway the pack ships, not a new
colour. That brings the mass tone to 4.9:1 on the dark ground. If the pack's own
`Icon/…Brand-OnDark` SVG is vendored later, render from it instead.

**Not a light tile behind the logo.** That was the first idea, and the pack forbids it: *"Do not
flatten the PNGs onto a background colour"*, and *"Place OnLight artwork on light grounds and
OnDark on dark ones."*

**The preview's text uses the machine's Noto Sans**, so a machine without it renders a fallback
face. Upload the committed PNG, and re-render only when the name or description changes.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_icons import MASTERS, ROOT, encode_png, render
from render_installer_art import LARGE_GROUND, ink_fraction

OUT = ROOT / "docs" / "assets"

#: The pack's Brand colourway values (`masters/PACK-README.txt`, "Colourways and colour values").
BRAND_ON_LIGHT_MASS = "#1E5E47"
BRAND_ON_DARK_MASS = "#48906C"

#: The artboard size the README logos are rasterised at before cropping. At 1024 the cropped ink
#: is about 700 px wide, over three times the README's display width, so high-density screens
#: still get a sharp image.
README_RENDER_SIZE = 1024

#: The pack's minimum clear space: *"at least 4% of the artwork width on all four sides."*
CLEAR_SPACE = 0.04

#: GitHub's recommended social preview size.
PREVIEW_SIZE = (1280, 640)

#: The installer's large-panel sand: already the maintainer's chosen ground for the logo at size,
#: and a light ground, which the OnLight master is drawn for.
PREVIEW_GROUND = LARGE_GROUND

#: How much of the preview's height the logo's ink takes, and the left edge of that ink.
#: GitHub's guidance is a 40 pt border for safe display; both margins clear it at 1280x640.
PREVIEW_INK_HEIGHT = 0.70
PREVIEW_LEFT = 110

NAME = "Tracks & Trails"
TAGLINE = ("A desktop GUI for yt-dlp,", "for Linux and Windows")
NAME_COLOUR = QColor(BRAND_ON_LIGHT_MASS)
TAGLINE_COLOUR = QColor("#3A3A3A")


def master_svg() -> bytes:
    """The Icon-cut master's bytes, checked to carry the OnLight mass tone it is substituted for."""
    data = (MASTERS / "icon.svg").read_bytes()
    if BRAND_ON_LIGHT_MASS.encode() not in data:
        raise SystemExit(
            f"icon.svg no longer carries {BRAND_ON_LIGHT_MASS}; re-check the colourway"
        )
    return data


def renderer_for(data: bytes) -> QSvgRenderer:
    renderer = QSvgRenderer(QByteArray(data))
    if not renderer.isValid():
        raise SystemExit("the logo master did not load as SVG")
    return renderer


def crop_to_ink(image: QImage) -> QImage:
    """`image` cut to its visible pixels plus `CLEAR_SPACE` of the ink's width on each side."""
    inked = [
        (x, y)
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).alpha() > 8
    ]
    if not inked:
        raise SystemExit("the logo rendered fully transparent")
    xs = [x for x, _ in inked]
    ys = [y for _, y in inked]
    margin = round((max(xs) - min(xs) + 1) * CLEAR_SPACE)
    left, top = max(min(xs) - margin, 0), max(min(ys) - margin, 0)
    right = min(max(xs) + margin, image.width() - 1)
    bottom = min(max(ys) + margin, image.height() - 1)
    return image.copy(left, top, right - left + 1, bottom - top + 1)


def readme_logo(mass_tone: str) -> QImage:
    svg = master_svg().replace(BRAND_ON_LIGHT_MASS.encode(), mass_tone.encode())
    return crop_to_ink(render(renderer_for(svg), README_RENDER_SIZE))


def social_preview() -> QImage:
    width, height = PREVIEW_SIZE
    renderer = renderer_for(master_svg())
    ink_w, ink_h = ink_fraction(renderer)
    side = height * PREVIEW_INK_HEIGHT / ink_h
    # The pack's artboards centre the ink, so the ink's left edge sits this far inside the artboard.
    artboard_left = PREVIEW_LEFT - side * (1 - ink_w) / 2
    ink_right = PREVIEW_LEFT + side * ink_w

    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(PREVIEW_GROUND)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    renderer.render(painter, QRectF(artboard_left, (height - side) / 2, side, side))

    name_font = QFont("Noto Sans")
    name_font.setPixelSize(92)
    name_font.setWeight(QFont.Weight.Bold)
    tagline_font = QFont("Noto Sans")
    tagline_font.setPixelSize(44)

    name_metrics = QFontMetricsF(name_font)
    tagline_metrics = QFontMetricsF(tagline_font)
    gap = 28.0
    block = name_metrics.height() + gap + tagline_metrics.lineSpacing() * len(TAGLINE)
    text_left = ink_right + 80
    top = (height - block) / 2

    painter.setFont(name_font)
    painter.setPen(NAME_COLOUR)
    painter.drawText(
        QRectF(text_left, top, width - text_left, name_metrics.height()),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        NAME,
    )
    painter.setFont(tagline_font)
    painter.setPen(TAGLINE_COLOUR)
    y = top + name_metrics.height() + gap
    for line in TAGLINE:
        painter.drawText(
            QRectF(text_left, y, width - text_left, tagline_metrics.lineSpacing()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            line,
        )
        y += tagline_metrics.lineSpacing()
    painter.end()
    return image


def main() -> int:
    QGuiApplication.instance() or QGuiApplication(sys.argv)
    OUT.mkdir(parents=True, exist_ok=True)
    outputs = {
        OUT / "logo-on-light.png": readme_logo(BRAND_ON_LIGHT_MASS),
        OUT / "logo-on-dark.png": readme_logo(BRAND_ON_DARK_MASS),
        OUT / "social-preview-1280x640.png": social_preview(),
    }
    for path, image in outputs.items():
        path.write_bytes(encode_png(image))
        print(f"{path.relative_to(ROOT)}  {path.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
