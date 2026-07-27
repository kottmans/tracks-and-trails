"""Qt for tests that have no window.

`DownloadManager` and `ResultPump` need an event loop to deliver queued signals, not a display.
A `QCoreApplication` would be the exact fit and is deliberately **not** used: Qt allows one
application object per process, and the widget tests in `tests/ui/` run in the same process and
need a `QApplication` — one built here first would make every later `QMainWindow` abort with
"cannot create a QWidget without QApplication". So this borrows `pytest-qt`'s `qapp`, which is
the same object the rest of the suite already shares.

The platform default matches `tests/ui/conftest.py` for the same reason it does there: a plain
`pytest` should reproduce what CI runs, and CI pins `QT_QPA_PLATFORM` per job — `setdefault`
leaves that pin alone.
"""

import os
import time
from collections.abc import Callable

import pytest
from PySide6.QtCore import QCoreApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def app(qapp: QCoreApplication) -> QCoreApplication:
    """The process-wide application object, whatever the rest of the suite made it."""
    return qapp


@pytest.fixture
def spin(app: QCoreApplication) -> Callable[..., bool]:
    """Deliver queued signals until a condition holds, or the timeout expires.

    The honest alternative to `sleep`: signals from a pump thread arrive as events, so a test
    that sleeps without processing them observes nothing however long it waits.
    """

    def wait_for(condition: Callable[[], bool], timeout: float = 30.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            app.processEvents()
            if condition():
                return True
            time.sleep(0.005)
        app.processEvents()
        return condition()

    return wait_for
