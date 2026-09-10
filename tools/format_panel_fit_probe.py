"""Does the format panel fit the width it asks for? (`T-310`, `T310-R2`.)

**A tool because the answer moves.** `FormatList.sizeHint` is what `AddUrlDialog._widen_for` and
`panel_height_for` both act on, and it was wrong five times while looking right in the source:
Qt's fixed default on each axis, a sum that ignored headers, a sum that ignored the layout's
stretch, a row height that ignored the style sheet's padding, and a second slot whose share was
counted only when a sound list occupied it. Each was found by measuring, and none by reading.

    .venv/bin/python tools/format_panel_fit_probe.py

Reports, for every committed capture, at three font sizes and in both palettes: the width the
widget states, whether either list scrolls at exactly that width, and the same one level up for a
standalone `FormatPanel`. **A non-zero scrollbar maximum is a failure**, and the number is in
scroll units rather than pixels — it says *that* a column is off the edge, not by how much.

**What this tool does not cover, and where that lives instead** (`T310-R9`). It never constructs an
`AddUrlDialog`, so it exercises neither `_mount_panel` nor `_widen_for` — the reviewer disabled the
widening outright and this tool still reported a clean sheet while all nine mounted-fit tests
failed. The mounting boundary is
`tests/ui/test_add_dialog.py::test_the_mounted_format_panel_fits_the_dialog_it_asked_for`, across
three captures and three font sizes with a substituted screen; the standalone axes are
`test_the_stated_width_is_enough_for_both_lists` and `test_the_stated_height_shows_every_row`.
This is the diagnostic you reach for when one of those fails and you want the numbers.

**It carries its own positive control.** A probe that only ever printed zeros would report a clean
sheet whether or not it was looking at anything, which is this project's recorded way of being
wrong (`tools/dialog_width_floor_probe.py` runs a larger font for the same reason). The last
section resizes a widget to two thirds of its stated width and expects the scrollbars it then
finds; if that comes back clean, the probe is not measuring what it claims to.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Final

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from tracks_and_trails.core.models import MediaInfo
from tracks_and_trails.downloader import ytdlp_adapter as adapter
from tracks_and_trails.ui import theme
from tracks_and_trails.ui.add_dialog import FormatPanel, row_summary
from tracks_and_trails.ui.format_table import FormatTable
from tracks_and_trails.ui.staging import Row

FIXTURES: Final = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "infodicts"

#: The captures with formats. Named rather than globbed, so a new fixture is added deliberately.
CAPTURES: Final = ("derived_format_columns", "archive_org_big_buck_bunny", "wikimedia_caminandes")

#: This machine's default, the control `dialog_width_floor_probe.py` uses, and one beyond it.
SIZES: Final = (9, 10, 11)


def formats_of(name: str) -> tuple:  # type: ignore[type-arg]
    payload = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return adapter.project_media(payload["info_dict"]).formats


def overflow(table: FormatTable) -> list[int]:
    """Each list's horizontal scrollbar maximum. All zeros is the only passing answer."""
    return [one.view.horizontalScrollBar().maximum() for one in table.lists()]


def measure(app: QApplication, name: str, points: int) -> tuple[int, list[int], int, list[int]]:
    """The standalone widget and the mounted panel, at `points`."""
    font = QFont(app.font())
    font.setPointSize(points)
    app.setFont(font)
    formats = formats_of(name)

    table = FormatTable(formats)
    table.resize(table.sizeHint())
    table.show()
    app.processEvents()
    standalone = (table.sizeHint().width(), overflow(table))
    table.close()

    # **A standalone panel, and calling this "mounted" was a false claim** (`T310-R9`). It builds a
    # `FormatPanel` directly and resizes it to its own hint: no `AddUrlDialog`, no `_mount_panel`,
    # no `_widen_for`. The reviewer showed what that costs — disabling `_widen_for` entirely leaves
    # this tool reporting the same clean sheet while all nine mounted-fit tests fail. So it
    # measures the panel's own layout, one level up from the bare table, and the widening is
    # covered by `test_the_mounted_format_panel_fits_the_dialog_it_asked_for` instead.
    row = Row(url="https://example.invalid/probe", generation=1)
    row.media = MediaInfo(url="https://example.invalid/probe", title="probe", formats=formats)
    panel = FormatPanel(row, row_summary(row), ffmpeg_available=True)
    panel.resize(panel.sizeHint())
    panel.show()
    app.processEvents()
    mounted = (panel.sizeHint().width(), overflow(panel.table))
    panel.close()
    return (*standalone, *mounted)


def main() -> int:
    app = QApplication([])
    failures = 0
    for palette in ("light", "dark"):
        theme.apply(app, theme.THEMES[palette])
        print(f"\n{palette} palette")
        for name in CAPTURES:
            for points in SIZES:
                width, bars, panel_width, panel_bars = measure(app, name, points)
                bad = any(bars) or any(panel_bars)
                failures += bad
                print(
                    f"  {name:28} {points:>2}pt  widget {width:>5}px bars={bars}"
                    f"   standalone panel {panel_width:>5}px bars={panel_bars}"
                    f"{'   <-- DOES NOT FIT' if bad else ''}"
                )

    theme.apply(app, theme.THEMES["light"])
    font = QFont(app.font())
    font.setPointSize(10)
    app.setFont(font)
    table = FormatTable(formats_of(CAPTURES[0]))
    starved = table.sizeHint().width() * 2 // 3
    table.resize(starved, table.sizeHint().height())
    table.show()
    app.processEvents()
    control = overflow(table)
    table.close()
    print(f"\nPositive control — the same widget at {starved}px: bars={control}")
    if not any(control):
        print("  The control did not scroll, so this probe cannot detect a widget that does.")
        return 2

    print(f"\n{failures} of {len(CAPTURES) * len(SIZES) * 2} measurements did not fit.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
