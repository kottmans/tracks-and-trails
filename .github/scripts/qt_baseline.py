"""Verifies the Qt baseline on a CI runner — the Windows half of T-002.

T-002 confirmed on Linux that PySide6 installs, imports, and constructs a live
`QApplication` + `QWidget` offscreen on Python 3.14. Per `OPS-003` the maintainer has no
Windows machine, so the Windows half of that claim can only ever be confirmed here.

This is deliberately not a pytest test. It answers "does the Qt stack work at all on this
runner", which is the question you ask *before* trusting a test suite that imports Qt: if this
fails, every UI test failure downstream is the same failure reported less clearly. Running it
as its own step also puts the versions and the resolved platform plugin in the CI log and the
uploaded artifact, where a Windows-only problem can be diagnosed without a Windows machine.

Exits non-zero on any failure, which fails the step and the job.
"""

import sys


def main() -> int:
    import PySide6
    import shiboken6
    from PySide6.QtCore import QLibraryInfo, qVersion
    from PySide6.QtWidgets import QApplication, QWidget

    print(f"python     {sys.version.split()[0]} ({sys.platform})")
    print(f"PySide6    {PySide6.__version__}")
    print(f"shiboken6  {shiboken6.__version__}")
    print(f"Qt         runtime {qVersion()}, built against {QLibraryInfo.version().toString()}")

    app = QApplication([])
    platform = app.platformName()
    print(f"platform   {platform}")

    widget = QWidget()
    widget.setWindowTitle("Tracks & Trails CI baseline")
    widget.resize(320, 240)
    widget.show()
    app.processEvents()

    visible = widget.isVisible()
    size = widget.size()
    print(f"widget     visible={visible} size={size.width()}x{size.height()}")

    widget.close()
    app.quit()

    # Assert rather than merely report: a step that prints a problem and exits zero is a step
    # that will be skimmed past.
    if platform != "offscreen":
        print(f"FAIL: expected the offscreen platform plugin, got {platform!r}", file=sys.stderr)
        return 1
    if not visible:
        print("FAIL: the widget did not become visible", file=sys.stderr)
        return 1

    print("OK: Qt baseline verified on this runner")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
