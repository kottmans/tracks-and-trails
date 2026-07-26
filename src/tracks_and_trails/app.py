"""Application setup and wiring (`T-007`).

Builds the `QApplication`, shows the shell window, and runs the event loop. `T-013` adds the
download manager wiring; `A-004` adds the single-instance guard in Phase 2.

Qt is imported inside `run`, not at module scope. `__main__.py` must stay importable without
pulling in Qt so `multiprocessing.freeze_support()` runs first in a frozen build (`REL-001`,
`ARCHITECTURE.md` §3), and `tests/unit/test_skeleton.py` asserts exactly that. A module-level
Qt import here would break that guarantee from a file that never mentions freezing.
"""

from collections.abc import Sequence

from tracks_and_trails import __version__

USAGE = """\
Tracks & Trails {version} — a desktop GUI for yt-dlp.

usage: tracks-and-trails [--version] [--help] [--spawn-probe]

  --version      print the version and exit
  --help, -h     print this message and exit
  --spawn-probe  self-test the process model and exit (T-020)

Run with no arguments to open the application window.
"""


def run(argv: Sequence[str]) -> int:
    """Start the application and return the process exit code."""
    args = list(argv[1:])

    # Handled before constructing a QApplication: `--version` must work on a machine with no
    # display, and without paying Qt's startup cost.
    if "--version" in args:
        print(__version__)
        return 0
    if "--help" in args or "-h" in args:
        print(USAGE.format(version=__version__), end="")
        return 0
    # Before Qt, and before anything else that would make this need a display. The frozen
    # build runs exactly this path in CI to prove that spawning a child does not relaunch the
    # application (REL-001, ARCHITECTURE.md §3, T-020).
    if "--spawn-probe" in args:
        from tracks_and_trails._freeze_probe import run_probe

        return run_probe()
    if args:
        print(USAGE.format(version=__version__), end="")
        return 2

    from PySide6.QtWidgets import QApplication

    from tracks_and_trails.ui.main_window import APP_NAME, MainWindow, app_icon

    app = QApplication(list(argv))
    # Set before any window exists: platform integration and some desktop environments read
    # these once, when the first window is created.
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_NAME)
    app.setWindowIcon(app_icon())

    window = MainWindow()
    window.show()
    return app.exec()
