"""Does the row underneath an open panel get painted while the panel is not covering it?

**`T-297`'s hypothesis, made falsifiable.** The report is *"when changing the window size while the
naming information is up, the thumbnail cuts in and out very rapidly"*. `RowDelegate.paint` draws
the thumbnail on every row it is asked to draw, expanded or not, and its own comment says an opened
row *"is covered by its panel"* — so the delegate never checks. If a resize ever paints the row at a
rectangle the panel does not cover, the thumbnail is what shows in the gap, and that is the flicker.

**Not collected by the suite**, and the filename is what does it: `python_files` is pytest's default
`test_*.py`. `tools/t297_resize_session.sh` names this file directly, which is the shape
`_leaks_a_view.py` established for the same reason.

**The fixtures are imported rather than rebuilt.** A copy of `dialogs` here would be a copy of the
thing under test's setup, which is the mistake `T-096` and `T214-R1` both name; these are the same
objects `tests/ui/test_add_dialog.py` uses.

## Two ways this instrument can lie, and what is done about each

- **A silently blind patch.** `RowDelegate.paint` is a C++ virtual, and PySide binds the Python
  override **when the instance is created** — replacing the class attribute afterwards intercepts
  nothing and reports a clean zero. The first version of this did exactly that and reported *"0
  paints"* for a dialog that was plainly painting. The patch is applied before anything is built,
  and the run reports its own total so a zero cannot be mistaken for an answer.
- **An under-sampling platform.** Offscreen coalesces paints: ~90 resize steps produced **7**. That
  is why this is run under a compositor, where a drag paints per frame, and why the paint total is
  reported next to the exposure count rather than only the exposures.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from tests.ui.test_add_dialog import (
    _open_the_template_editor,
    _staged_playlist,
    dialogs,
    managers,
    sink,
    store,
    thumbnails,
)
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.ui.add_dialog import AddUrlDialog

__all__ = ["dialogs", "managers", "sink", "store", "thumbnails"]

#: Heights the window is walked through, down and back up. Six-pixel steps rather than a few big
#: jumps: a drag is continuous, and the question is what happens *between* two settled states.
_HEIGHTS = [*range(760, 430, -6), *range(430, 760, 6)]


def test_the_open_row_is_never_painted_uncovered(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Walk the window through a resize with a panel open and record every paint of that row."""
    from tracks_and_trails.ui.row_delegate import RowDelegate

    every: list[int] = []
    exposed: list[dict[str, int]] = []
    watching: dict[str, Any] = {}
    real_paint = RowDelegate.paint

    def watched(self: Any, painter: Any, option: Any, index: Any) -> None:
        every.append(index.row())
        panel = watching.get("panel")
        if panel is not None and index.row() == watching.get("target"):
            covered = panel.geometry()
            if not covered.contains(option.rect):
                exposed.append(
                    {
                        "row_y": option.rect.y(),
                        "row_h": option.rect.height(),
                        "panel_y": covered.y(),
                        "panel_h": covered.height(),
                        "window_h": watching["window"].height(),
                    }
                )
        real_paint(self, painter, option, index)

    # Before anything is constructed; see the module docstring.
    monkeypatch.setattr(RowDelegate, "paint", watched)

    dialog, row = _staged_playlist(dialogs, managers, spin)
    dialog.resize(900, 760)
    dialog.show()
    qapp.processEvents()
    panel = _open_the_template_editor(dialog, 0)
    qapp.processEvents()
    watching.update(panel=panel, target=dialog.rows.index(row), window=dialog)

    from PySide6.QtCore import QEvent, QObject

    resizes: list[tuple[int, int]] = []
    collapses: list[list[str]] = []

    class _PanelWatch(QObject):
        def eventFilter(self, obj: Any, event: Any) -> bool:  # noqa: N802
            if event.type() == QEvent.Type.Resize:
                resizes.append((event.oldSize().height(), event.size().height()))
                if event.size().height() == 26 and len(collapses) < 3:
                    import traceback

                    collapses.append(
                        "".join(traceback.format_stack(limit=8)[:-1]).strip().splitlines()
                    )
            return False

    panel_watch = _PanelWatch()
    panel.installEventFilter(panel_watch)

    before = len(every)
    settled: list[tuple[int, int, int]] = []
    for height in _HEIGHTS:
        dialog.resize(900, height)
        qapp.processEvents()
        # What the panel looks like once this step has been fully delivered. If it is right here
        # and wrong at paint time, the defect is the deferral; if it is wrong here too, the
        # restore itself is not landing.
        index = dialog._index_of(row)
        settled.append((height, panel.geometry().height(), dialog._list.visualRect(index).height()))

    # **A capture of the measured state, reconstructed deliberately and labelled as such.** The
    # nested compositor renders to its own framebuffer and there is no screencast portal here, and
    # `grab()` re-renders a widget rather than reading the frame that was shown — so a "screenshot"
    # taken during the drag would be a picture of a repaired panel, not of the defect. Instead the
    # panel is put back into the exact geometry the trace above recorded (26 px) and the viewport is
    # rendered, which shows what the row underneath contributes to a frame in that state.
    capture = os.environ.get("T297_CAPTURE")
    if capture:
        # **Recording stops first.** The reconstruction below collapses the panel deliberately, and
        # counting that would put the instrument's own action in the measurement — which it did,
        # for one collapse and two paints, until this line existed.
        watching["panel"] = None
        index = dialog._index_of(row)
        full = dialog._list.visualRect(index)
        panel.setGeometry(full.x(), full.y(), full.width(), 26)
        qapp.processEvents()
        dialog._list.viewport().grab().save(capture)

    report = Path(os.environ.get("T297_REPORT", "")) if os.environ.get("T297_REPORT") else None
    lines = [
        f"platform            : {QApplication.platformName()}",
        f"resize steps        : {len(_HEIGHTS)}",
        f"delegate paints     : {len(every)} (before the resize: {before})",
        f"paints of the row   : {sum(1 for r in every if r == watching['target'])}",
        f"EXPOSED paints      : {len(exposed)}",
        f"panel resize events : {len(resizes)}",
        "who collapses it (Python stack at the first collapse):",
        *[f"    {line.strip()}" for line in (collapses[0] if collapses else ["<none captured>"])],
        "  first twenty (old h -> new h): "
        + " ".join(f"{old_h}->{new_h}" for old_h, new_h in resizes[:20]),
        f"  resizes TO the 26 px minimum: {sum(1 for _o, n in resizes if n == 26)}",
        "settled after each step (window h, panel h, row h):",
        "  " + "  ".join(f"{w}:{p}/{r}" for w, p, r in settled[:10]),
        f"  steps where the settled panel matched the row: "
        f"{sum(1 for _w, p, r in settled if p == r)}/{len(settled)}",
    ]
    for record in exposed[:12]:
        lines.append(
            f"  window h={record['window_h']:4}  row y={record['row_y']:5} h={record['row_h']:5}"
            f"   panel y={record['panel_y']:5} h={record['panel_h']:5}"
        )
    lines.append(
        "VERDICT: "
        + (
            f"REPRODUCED — {len(exposed)} paints of the open row were not covered by its panel"
            if exposed
            else "NOT REPRODUCED — every paint of the open row was covered by its panel"
        )
    )
    text = "\n".join(lines)
    print("\n--- T-297 resize probe ---\n" + text)
    if report is not None:
        report.write_text(text + "\n", encoding="utf-8")

    assert len(every) > before, (
        "the delegate was never called during the resize, so this run measured nothing. That is "
        "the blind-patch failure the module docstring describes, not a clean result"
    )
