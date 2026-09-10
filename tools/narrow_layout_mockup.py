"""What a narrow screen could show instead of scrolling sideways (`T-310`, `T310-R2`).

**The conflict this is for.** `REQ-003` names eight fields and `T310-R1` restored the one the split
had dropped, which took the derived capture from about 1100px to **1506px** at the 10pt control
font. `T-310`'s criterion promises no sideways scrolling at 10pt, unqualified. On a 1366px laptop
those two cannot both stand: `Notes` and `ID` fall off the right edge of both lists.

Three answers, rendered at the same width so the cost of each is visible rather than argued:

- **A** — today. Side by side, and it scrolls.
- **C** — the lists stacked when the screen is narrow, side by side when it is not. Every column at
  full width, nothing truncated, nothing scrolling. The cost is vertical: two lists sharing the
  panel's height show fewer rows each, and that is what the render shows.
- **Wide** — the same panel at 1920px, for reference. `C` is a narrow-screen layout only; nothing
  about a roomy screen changes.

    .venv/bin/python tools/narrow_layout_mockup.py             # on the real display
    .venv/bin/python tools/narrow_layout_mockup.py --shots OUT # render each to a PNG

**Built on the real `FormatTable`**, with only its list layout re-hung, so what is being compared
is the product's own columns, sorting and wording rather than a drawing of them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.downloader import ytdlp_adapter as adapter
from tracks_and_trails.ui import theme
from tracks_and_trails.ui.format_table import FormatTable

FIXTURES: Final = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "infodicts"
CAPTURE: Final = "derived_format_columns"

#: A 1366x768 laptop, less the dialog chrome the panel does not receive, and a 1920 desktop.
NARROW: Final = 1366 - 62
WIDE: Final = 1920 - 62

#: What the panel gets of a 768-high window once the dialog's own furniture is out of the way.
PANEL_HEIGHT: Final = 420


def formats() -> tuple:  # type: ignore[type-arg]
    payload = json.loads((FIXTURES / f"{CAPTURE}.json").read_text(encoding="utf-8"))
    return adapter.project_media(payload["info_dict"]).formats


def stack(table: FormatTable) -> None:
    """Re-hang the two lists one above the other.

    **The lists themselves are untouched.** Only the layout holding them changes, which is the
    whole of what `C` proposes: each list then receives the panel's full width, so every column it
    has room for at 1920 it also has room for at 1366.
    """
    outer = table.layout()
    assert outer is not None
    row = next(
        outer.itemAt(index).layout()
        for index in range(outer.count())
        if isinstance(outer.itemAt(index).layout(), QHBoxLayout)
    )
    panels = [row.itemAt(index).widget() for index in reversed(range(row.count()))]
    for panel in panels:
        row.removeWidget(panel)
    column = QVBoxLayout()
    for panel in reversed(panels):
        column.addWidget(panel)
    outer.removeItem(row)
    outer.insertLayout(0, column)


def overflow(table: FormatTable) -> list[int]:
    return [one.view.horizontalScrollBar().maximum() for one in table.lists()]


def page(title: str, width: int, stacked: bool) -> QWidget:
    shell = QWidget()
    shell.resize(width, PANEL_HEIGHT + 60)
    layout = QVBoxLayout(shell)

    caption = QLabel("", shell)
    caption.setWordWrap(True)
    caption.setTextFormat(Qt.TextFormat.RichText)
    layout.addWidget(caption)

    table = FormatTable(formats(), shell)
    if stacked:
        stack(table)
    table.setFixedHeight(PANEL_HEIGHT)
    layout.addWidget(table)
    shell.table = table  # type: ignore[attr-defined]
    shell.caption = caption  # type: ignore[attr-defined]
    shell.title = title  # type: ignore[attr-defined]
    return shell


VARIANTS: Final = (
    ("A · side by side at 1366", NARROW, False),
    ("C · stacked at 1366", NARROW, True),
    ("Wide · side by side at 1920", WIDE, False),
)


def describe(shell: QWidget) -> str:
    table = shell.table  # type: ignore[attr-defined]
    bars = overflow(table)
    rows = [one.view.viewport().height() // max(one.view.rowHeight(0), 1) for one in table.lists()]
    verdict = "scrolls sideways" if any(bars) else "<b>fits</b>"
    return (
        f"<b>{shell.title}</b> — {verdict}. Horizontal maxima {bars}; "  # type: ignore[attr-defined]
        f"about {rows} rows visible per list."
    )


def build(title: str, width: int, stacked: bool) -> QWidget:
    """One page, **shown at its own width**.

    **Not tabs, and the first draft's bug is why.** Three pages in a `QTabWidget` are all sized by
    the tab widget, so each `resize` was discarded and every variant rendered at the same width —
    the run reported *"side by side at 1366 fits"*, which is the opposite of the measured truth and
    would have argued the decision the wrong way. Each page is a top-level widget here, and the
    caption reports what it measured after being shown at that size.
    """
    shell = page(title, width, stacked)
    shell.resize(width, PANEL_HEIGHT + 70)
    shell.show()
    QApplication.processEvents()
    shell.caption.setText(describe(shell))  # type: ignore[attr-defined]
    QApplication.processEvents()
    return shell


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shots", type=Path, help="render each variant to this directory and exit")
    parsed = parser.parse_args(argv)
    if parsed.shots is not None:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication([])
    theme.apply(app, theme.THEMES["light"])
    font = QFont(app.font())
    font.setPointSize(10)
    app.setFont(font)

    shells = [build(title, width, stacked) for title, width, stacked in VARIANTS]
    if parsed.shots is None:
        return app.exec()

    parsed.shots.mkdir(parents=True, exist_ok=True)
    for (title, _width, _stacked), shell in zip(VARIANTS, shells, strict=True):
        target = parsed.shots / f"{title.split(' · ')[0].lower()}.png"
        shell.grab().save(str(target))
        print(f"{target}  {shell.width()}px  {describe(shell)}")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
