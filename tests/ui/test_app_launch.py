"""End-to-end launch and shutdown of the real application (`T-007`).

`tests/ui/test_main_window.py` builds a `MainWindow` inside the test process. This exercises
the path a user actually takes: `app.run` constructs the `QApplication`, shows the window and
enters `exec()`, in a fresh interpreter.

Run as a subprocess deliberately. The acceptance criterion is a **zero exit code and no Qt
warnings on stderr**, and neither is observable in-process: pytest-qt has already created a
`QApplication`, so the real startup path never runs, and Qt's warnings go to the process's
stderr rather than anywhere pytest captures by default.
"""

import os
import subprocess
import sys

import pytest

#: Runs the real entry point, then quits the event loop from a watcher thread.
#:
#: The watcher touches exactly two things: `QApplication.instance()`, and
#: `QMetaObject.invokeMethod(..., QueuedConnection)`, which is documented thread-safe. It
#: deliberately does **not** inspect `topLevelWidgets()` or `isVisible()` to decide when to
#: quit — widget state belongs to the GUI thread, and reading it from here is the "Qt object
#: touched off the GUI thread" violation in `ai/REVIEWS.md`'s standing risk list. An earlier
#: version of this harness did exactly that and was intermittently unreliable, which is the
#: symptom that rule exists to prevent.
#:
#: No widget check is needed for correctness: `run` calls `window.show()` before `app.exec()`,
#: so a queued quit cannot be processed until after the window is up.
LAUNCH_AND_QUIT = """
import sys, threading, time
from tracks_and_trails.app import run

def stop():
    from PySide6.QtCore import QMetaObject, Qt
    from PySide6.QtWidgets import QApplication
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        app = QApplication.instance()
        if app is not None:
            QMetaObject.invokeMethod(app, "quit", Qt.ConnectionType.QueuedConnection)
            return
        time.sleep(0.01)
    raise SystemExit("the application never started")

threading.Thread(target=stop, daemon=True).start()
sys.exit(run(["tracks-and-trails"]))
"""


def run_headless(source: str, tmp_home: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        # Redirect platformdirs so a test never writes to the real config directory and never
        # reads a window position the user set by hand.
        #
        # Windows needs its own mechanism: platformdirs resolves folders through
        # SHGetKnownFolderPath via ctypes, so setting APPDATA does nothing there. Its
        # documented escape hatch is WIN_PD_OVERRIDE_*. Setting only the POSIX variable is
        # why this test passed on Linux and failed on the Windows runner.
        "XDG_CONFIG_HOME": tmp_home,
        "WIN_PD_OVERRIDE_APPDATA": tmp_home,
        "WIN_PD_OVERRIDE_LOCAL_APPDATA": tmp_home,
    }
    return subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=env,
    )


#: Emitted by the `offscreen` and `minimal` platform plugins when a window carrying a menu bar
#: is shown — neither implements `propagateSizeHints()`. Verified on 2026-07-25 to be an
#: artifact of those plugins and not of this application: the identical launch under a real
#: Wayland session exits zero with a completely empty stderr, and a bare `QMainWindow` with a
#: menu bar reproduces it under `offscreen` with no project code involved.
#:
#: Allowlisted by exact match, deliberately. Asserting "no *unexpected* stderr" keeps the
#: criterion meaningful; relaxing it to "ignore warnings" would retire the check entirely.
PLUGIN_NOISE = frozenset({"This plugin does not support propagateSizeHints()"})


def unexpected_stderr(stderr: str) -> list[str]:
    return [
        line for line in stderr.splitlines() if line.strip() and line.strip() not in PLUGIN_NOISE
    ]


def test_application_launches_and_exits_cleanly(tmp_path: pytest.TempPathFactory) -> None:
    """Zero exit code and no Qt warnings — the `T-007` criterion, on the real path."""
    result = run_headless(LAUNCH_AND_QUIT, str(tmp_path))
    assert result.returncode == 0, f"exit {result.returncode}\nstderr: {result.stderr}"
    assert unexpected_stderr(result.stderr) == [], (
        f"Qt wrote something unexpected to stderr during a clean run:\n{result.stderr}"
    )


def test_launch_writes_geometry_on_exit(tmp_path: pytest.TempPathFactory) -> None:
    """A real launch/quit cycle must leave a geometry file behind, not just an in-process close."""
    result = run_headless(LAUNCH_AND_QUIT, str(tmp_path))
    assert result.returncode == 0, result.stderr
    written = list(map(str, __import__("pathlib").Path(tmp_path).rglob("window.toml")))
    assert written, "closing the real application must persist window geometry"


def test_unknown_arguments_exit_nonzero_with_usage(tmp_path: pytest.TempPathFactory) -> None:
    result = run_headless(
        "import sys\nfrom tracks_and_trails.app import run\n"
        "sys.exit(run(['tracks-and-trails', '--nonsense']))",
        str(tmp_path),
    )
    assert result.returncode == 2
    assert "usage:" in result.stdout
    assert result.stderr == ""


def test_help_exits_zero_without_a_display(tmp_path: pytest.TempPathFactory) -> None:
    """`--help` must not need Qt: it is the one thing a user runs when the GUI will not start."""
    source = "import sys\nfrom tracks_and_trails.app import run\nsys.exit(run(['t', '--help']))"
    result = subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**os.environ, "QT_QPA_PLATFORM": "definitely-not-a-real-platform-plugin"},
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
