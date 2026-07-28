"""Qt and the `spin` helper for the opt-in network suite.

The same shape as `tests/integration/conftest.py` and for the same reasons: `pytest-qt`'s `qapp`
is borrowed rather than a second application object being made, and a test that slept without
processing events would observe nothing however long it waited.

Duplicated rather than shared because these three directories are collected independently and a
`conftest.py` does not reach sideways. The alternative — hoisting it to `tests/conftest.py` —
would put a Qt import in front of the unit suite, which runs headless and Qt-free on purpose
(`ai/TESTING.md` §1).
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
    """Deliver queued signals until a condition holds, or the timeout expires."""

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
