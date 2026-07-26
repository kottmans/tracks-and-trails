"""Records the Windows runner's desktop capabilities — the evidence behind `OPS-004`.

`OPS-003` assumed a CI runner has no desktop session and classified rendering, focus and
assistive technology as human-only work blocking the first public release. A spike disproved
the assumption; `OPS-004` accepted the correction. This script is that spike, promoted from a
one-off into something that runs on every push.

It exists separately from the pytest suite for the same reason `qt_baseline.py` does: it
answers "is there a desktop here at all", which is the question you ask *before* trusting a
suite that assumes one. If the runner image ever loses its desktop, the failure surfaces here
as one clear line rather than as a dozen confusing test failures.

Exits non-zero on any failure, which fails the step and the job.
"""

import ctypes
import sys


def main() -> int:
    if sys.platform != "win32":
        print(f"FAIL: this script is Windows-only, got {sys.platform!r}", file=sys.stderr)
        return 1

    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication, QWidget

    app = QApplication([])
    platform = app.platformName()
    print(f"platformName        {platform!r}")

    screens = [(s.name(), s.size().width(), s.size().height()) for s in QGuiApplication.screens()]
    print(f"screens             {screens}")

    widget = QWidget()
    widget.setWindowTitle("Tracks & Trails")
    widget.resize(640, 480)
    widget.show()
    widget.raise_()
    widget.activateWindow()
    app.processEvents()

    hwnd = int(widget.winId())
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    title = buffer.value
    visible = bool(user32.IsWindowVisible(hwnd))

    print(f"native HWND         {hwnd}")
    print(f"GetWindowTextW      {title!r}")
    print(f"IsWindowVisible     {visible}")

    # Prove the capture path works here, so the suite's screenshot failures are its own rather
    # than an environment problem discovered at the wrong moment.
    primary = QGuiApplication.primaryScreen()
    captured = False
    if primary is not None:
        pixmap = primary.grabWindow(widget.winId())
        captured = not pixmap.isNull()
        print(f"screenshot          {'captured' if captured else 'FAILED'} {pixmap.size()}")

    widget.close()
    app.quit()

    # Assert rather than merely report. A step that prints a problem and exits zero is a step
    # that will be skimmed past — and this one exists to catch a silent regression.
    if platform != "windows":
        print(
            f"FAIL: expected the real 'windows' platform plugin, got {platform!r}. "
            "T-026 is meaningless offscreen (OPS-004).",
            file=sys.stderr,
        )
        return 1
    if not screens:
        print("FAIL: no screen — the state OPS-003 assumed and OPS-004 disproved", file=sys.stderr)
        return 1
    if not visible:
        print("FAIL: Windows does not report the window as visible", file=sys.stderr)
        return 1
    if title != "Tracks & Trails":
        print(f"FAIL: Windows reports the title as {title!r}", file=sys.stderr)
        return 1
    if not captured:
        print("FAIL: could not capture the window", file=sys.stderr)
        return 1

    print("OK: this runner provides a real Windows desktop (OPS-004)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
