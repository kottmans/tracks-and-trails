"""Why `AddUrlDialog` refuses to narrow to 320px on some systems, and what sets the floor.

**The failing assertion is `test_the_dialog_can_still_be_made_narrower_than_it_opens`.** It resizes
the dialog to 320px and requires it to land there. On the maintainer's Fedora machines it does; on
GitHub's `ubuntu-latest` image the dialog stops at 331px and the test fails.

**Run it before deciding whether that is a product defect or a test defect**, because the two have
opposite fixes and the wrong one hides the other. It reports the floor, the widget that sets it,
and how both move with the application font — the only input that differs between the two
platforms.

    QT_QPA_PLATFORM=offscreen python tools/dialog_width_floor_probe.py

**It carries its own positive control.** A probe that only ever printed the local floor would say
the same thing whether or not the font is what moves it. Increasing the point size by one
reproduces the CI failure on a machine where the suite passes, which is what makes the diagnosis
checkable rather than argued.

Builds the real `AddUrlDialog` with permissive stubs for the two collaborators it only connects
signals to. It measures layout, so nothing is downloaded, probed or written.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication, QWidget

from tracks_and_trails.ui.add_dialog import AddUrlDialog

#: The width the test demands the dialog reach.
TARGET = 320

#: A line the queue view also measures, kept here so both failures can be read side by side.
REFERENCE_TEXT = "This download needed ffmpeg, which was not found"


class _FakeSignal:
    def connect(self, *args: object, **kwargs: object) -> None: ...
    def disconnect(self, *args: object, **kwargs: object) -> None: ...
    def emit(self, *args: object, **kwargs: object) -> None: ...


class _Permissive:
    """Answers every attribute with a connectable signal.

    The dialog only *connects* to its manager and job sink while it is being built — this probe
    asked, and the set is `job_changed`, `job_failed`, `media_probed`, `persistence_failed`,
    `staged_changed` and `start_rejected`. Stubbing them keeps the measurement about layout
    instead of dragging a real `DownloadManager` and its threads into a width question.
    """

    def __getattr__(self, name: str) -> _FakeSignal:
        return _FakeSignal()


def measure(app: QApplication, label: str, font: QFont | None = None) -> tuple[int, int, bool]:
    """Report the floor for one font, and the widgets that set it."""
    if font is not None:
        app.setFont(font)
    dialog = AddUrlDialog(
        manager=_Permissive(),
        jobs=_Permissive(),
        # Never written to: the dialog only shows this path. Kept off the real download
        # directory so a probe can never touch one.
        output_directory=Path(tempfile.gettempdir()) / "tracks-and-trails-probe",
    )
    dialog.show()
    floor = dialog.minimumSizeHint().width()
    opens_at = dialog.sizeHint().width()
    dialog.resize(TARGET, dialog.height())
    reached = dialog.width()

    active = app.font()
    reference = QFontMetrics(active).horizontalAdvance(REFERENCE_TEXT)
    print(
        f"{label:<26} font={active.family()!r:<17} {active.pointSize()}pt  "
        f"reference={reference:>4}px  opens={opens_at:>4}  floor={floor:>4}  "
        f"resize({TARGET})->{reached:<4} {'PASS' if reached == TARGET else 'FAIL'}"
    )
    widest = sorted(
        (child.minimumSizeHint().width(), type(child).__name__, child.objectName())
        for child in dialog.findChildren(QWidget)
    )[-3:]
    for width, kind, name in reversed(widest):
        print(f"      sets the floor: {width:>4}px  {kind}{' #' + name if name else ''}")
    dialog.deleteLater()
    return floor, opens_at, reached == TARGET


def main() -> int:
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    base = app.font()

    print("This machine, as the suite runs it:")
    floor, opens_at, passed = measure(app, "default")

    print("\nPositive control — the same dialog, one point larger:")
    larger = QFont(base.family())
    larger.setPointSize(base.pointSize() + 1)
    bigger_floor, _, bigger_passed = measure(app, f"{base.pointSize() + 1}pt", larger)

    print(f"\nMargin on this machine: {TARGET - floor}px between the floor and the assertion.")
    print(f"The floor moved {bigger_floor - floor}px for one point of font size.")
    if passed and not bigger_passed:
        print(
            "\nThe control reproduced the CI failure locally, so the font is what differs and the "
            "floor is not a regression."
        )
    elif not passed:
        print("\nThis machine already fails; the floor is below the assertion here too.")
    else:
        print("\nThe control did NOT reproduce it. Do not conclude the font is the cause.")
    print(
        f"The dialog still opens at {opens_at}px and narrows to {floor}px, so the opening width "
        "is not itself the floor — which is the property the failing test exists to protect."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
