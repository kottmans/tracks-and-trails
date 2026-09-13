"""Render the check-box marks the theme draws in its own indicators (`T-327` session, 2026-09-13).

Run from the repository root, in the project's virtualenv:

    QT_QPA_PLATFORM=offscreen .venv/bin/python tools/icons/render_indicators.py

Writes `{tick,dash}-{light,dark}[-disabled].png` and each one's `@2x` into
`src/tracks_and_trails/resources/indicators/`. **Every file in that directory is output.**

## Why there are images at all

Windows draws a check box's indicator as a white square with a dark tick in every theme and every
state, which in dark was a bright block beside every option and looked the same whether the option
could be ticked or not. The maintainer ruled for indicators drawn from the theme. A style sheet can
draw a box, its fill and its border, and a radio button's dot as a radial gradient, but not a tick:
that is what these are, in each theme's ink for a ticked box and for a ticked box that is disabled.

`dash` is the partial state, which the playlist picker's group box shows when some entries are
chosen.

## Colours come from `ui/theme.py`

The mark is `on_primary` on an enabled box, whose fill is `primary`, and `muted` on a disabled one,
whose fill is `rule`. Both pairs are the ones the theme's own contrast tests measure, so a palette
change is a reason to rerun this and nothing here needs editing.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen

from tracks_and_trails.ui import theme

OUT = Path(__file__).resolve().parents[2] / "src" / "tracks_and_trails" / "resources" / "indicators"

#: The indicator's content box in logical pixels, which is `INDICATOR_SIZE` in `ui/theme.py`.
SIZE = theme.INDICATOR_SIZE


def _render(mark: str, ink: str, scale: int) -> QImage:
    side = SIZE * scale
    image = QImage(side, side, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(ink), 2.0 * scale)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        unit = side / 14
        if mark == "tick":
            painter.drawPolyline(
                [
                    QPointF(3.2 * unit, 7.4 * unit),
                    QPointF(5.9 * unit, 10.0 * unit),
                    QPointF(10.9 * unit, 4.2 * unit),
                ]
            )
        else:
            painter.drawLine(QPointF(3.5 * unit, 7 * unit), QPointF(10.5 * unit, 7 * unit))
    finally:
        painter.end()
    return image


def main() -> None:
    _app = QGuiApplication([])
    OUT.mkdir(parents=True, exist_ok=True)
    for chosen in theme.THEMES.values():
        for mark in ("tick", "dash"):
            for suffix, ink in (("", chosen.on_primary), ("-disabled", chosen.muted)):
                stem = f"{mark}-{chosen.name}{suffix}"
                _render(mark, ink, 1).save(str(OUT / f"{stem}.png"))
                _render(mark, ink, 2).save(str(OUT / f"{stem}@2x.png"))
    print(f"wrote {len(list(OUT.iterdir()))} files to {OUT}")


if __name__ == "__main__":
    main()
