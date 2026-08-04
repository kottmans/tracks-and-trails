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

#: Runs the real entry point and quits from the GUI thread, with no watcher thread at all.
#:
#: The previous version polled `QApplication.instance()` from a foreign thread. Qt documents
#: `quit()` and `QMetaObject::invokeMethod(..., QueuedConnection)` as thread-safe; it does not
#: document `instance()` as safe to call while the application object is being constructed on
#: another thread, so the harness was relying on something Qt never promised (`T028-R1`).
#:
#: Instead, `MainWindow` is subclassed so that `showEvent` — which Qt calls on the GUI thread,
#: during `show()` — schedules the quit through a zero-delay timer. `app.py` imports
#: `MainWindow` inside `run`, so replacing the module attribute first is enough to have the
#: real entry point construct this subclass.
#:
#: The ordering proof survives and is now directly observable rather than argued: `show()`
#: runs before `exec()`, a zero-delay timer cannot fire until the event loop is running, and
#: both markers are printed in order for the test to assert on.
LAUNCH_AND_QUIT = """
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import tracks_and_trails.ui.main_window as main_window


class QuitOnceShown(main_window.MainWindow):
    def showEvent(self, event):
        super().showEvent(event)
        print("WINDOW-SHOWN", flush=True)
        QTimer.singleShot(0, self._request_quit)

    def _request_quit(self):
        print("QUIT-REQUESTED", flush=True)
        app = QApplication.instance()
        if app is None:
            print("FAIL: no QApplication when the quit fired", file=sys.stderr, flush=True)
            raise SystemExit(3)
        app.quit()


main_window.MainWindow = QuitOnceShown

from tracks_and_trails.app import run

sys.exit(run(["tracks-and-trails"]))
"""


def run_headless(source: str, tmp_home: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        # Redirect platformdirs so a test never writes to the real directories and never reads a
        # window position, a queue or a log the user has of their own.
        #
        # **All three roots, not just config** (`T-131`). This set `XDG_CONFIG_HOME` alone, and the
        # application uses three: `user_config_dir` for `settings.toml` and `window.toml`,
        # `user_data_dir` for **the queue database** and the user-managed yt-dlp copy, and
        # `user_cache_dir` for the application log and the thumbnail cache. So a launch test
        # opened the developer's real database, took the real single-instance lock (`T-087`), and
        # wrote their real log. With the application open the lock is held and the launch hangs
        # until this timeout — which is how it was found, and it would fail the same way on any
        # machine where somebody had the app running.
        #
        # Windows needs its own mechanism: platformdirs resolves folders through
        # SHGetKnownFolderPath via ctypes, so setting APPDATA does nothing there. Its
        # documented escape hatch is WIN_PD_OVERRIDE_*. Setting only the POSIX variable is
        # why this test passed on Linux and failed on the Windows runner — and, as it turns out,
        # the Windows overrides were the *complete* pair while the POSIX side was one of three.
        "XDG_CONFIG_HOME": tmp_home,
        "XDG_DATA_HOME": tmp_home,
        "XDG_CACHE_HOME": tmp_home,
        "WIN_PD_OVERRIDE_APPDATA": tmp_home,
        "WIN_PD_OVERRIDE_LOCAL_APPDATA": tmp_home,
    }
    try:
        return subprocess.run(
            [sys.executable, "-c", source],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as expired:
        # A silent timeout is indistinguishable from CI flakiness. Say what actually happened.
        raise AssertionError(
            "the application never exited within 120s. It either never showed a window or "
            f"never processed the queued quit.\nstdout: {expired.stdout!r}\n"
            f"stderr: {expired.stderr!r}"
        ) from expired


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
    # Asserted, not assumed: a quit that never fired would otherwise surface as an opaque
    # subprocess timeout, which reads like infrastructure flakiness rather than a defect.
    assert "WINDOW-SHOWN" in result.stdout, "the window never reached showEvent"
    assert "QUIT-REQUESTED" in result.stdout, "the window appeared but the quit never fired"
    assert result.stdout.index("WINDOW-SHOWN") < result.stdout.index("QUIT-REQUESTED"), (
        "the quit was processed before the window was shown, so show() did not precede exec()"
    )
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
