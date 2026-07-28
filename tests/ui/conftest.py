"""Qt tests run without a display.

`TESTING.md` §10 and `T-006` both require the UI suite to pass headless on Linux and Windows
CI runners. Setting the platform here rather than relying on the caller's environment means a
plain `pytest` reproduces what CI does.
"""

import os
import time
from collections.abc import Callable

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Imported after the platform is pinned above, so nothing can load a Qt plugin before the
# offscreen choice is in the environment.
from PySide6.QtCore import QCoreApplication


@pytest.fixture
def spin(qapp: QCoreApplication) -> Callable[..., bool]:
    """Deliver queued signals until a condition holds, or the timeout expires.

    The same helper `tests/integration/conftest.py` provides, and for the same reason: a probe
    result reaches a widget as a queued signal from `ResultPump`'s thread, so a test that slept
    without processing events would observe nothing however long it waited.
    """

    def wait_for(condition: Callable[[], bool], timeout: float = 30.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            qapp.processEvents()
            if condition():
                return True
            time.sleep(0.005)
        qapp.processEvents()
        return condition()

    return wait_for
