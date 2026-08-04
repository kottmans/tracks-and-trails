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
from collections.abc import Callable, Iterator

import pytest
from PySide6.QtCore import QCoreApplication

from tests import qt_lifecycle

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


# --- `T-128`: an orphaned timer fails at its cause, not at the crash it becomes ----------------
#
# Qt warns when a QObject owning a live timer is destroyed from a thread that does not own it, and
# then carries on — the dispatcher keeps a pointer to freed memory and follows it on some later
# tick, which presents as a segfault with no connection to whatever caused it. Two of those cost an
# overnight soak and two core dumps to attribute (`ai/evidence/SOAK-FAILED-13.txt`).
#
# Installed once per session and checked after every test, so the failure names the test that did
# it. `ai/TESTING.md` §13: the useful signal is the one at the cause.
qt_lifecycle.fail_on_orphaned_timers()


@pytest.fixture(autouse=True)
def _no_orphaned_timers() -> Iterator[None]:
    yield
    qt_lifecycle.assert_no_orphaned_timers()
