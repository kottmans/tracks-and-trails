"""A test that deliberately ends with a pool thread still running (`T289-R23`).

**Not collected by the suite**, and the filename is what does it: `python_files` is pytest's
default `test_*.py`, so a directory collection walks past this. `pytest` still collects a file
named directly on the command line, which is how `test_suite_isolation.py` runs it — the same shape
`_leaks_a_view.py` uses, and for the same reason: this one *must* fail.

**What it proves.** The root `conftest.py` replaces the pool singletons around every test, and the
first version dropped whatever the test had created without asking whether it was busy. A
`QThreadPool` released with runnables in flight is destroyed by whichever thread collects it, and
its destructor waits there — or aborts. That segfaulted this suite once, in a test that had nothing
to do with pools, and the test that caused it had to join its own task by hand to work around a
fixture that should have owned this.

**It lives under `tests/ui/` on purpose**, beside the other deliberate violations: what is being
proved is the fixture *as wired*, in the order the two conftests give their autouse fixtures.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QRunnable
from PySide6.QtWidgets import QApplication

from tests import conftest as root_conftest
from tracks_and_trails.ui import thumbnails

#: The real bound is thirty seconds, which is the right patience for a suite and the wrong length
#: for a regression that has to wait it out. Shortened here and nowhere else: what this file
#: asserts is *that* the fixture refuses a busy pool, not how long it is willing to be patient.
root_conftest._POOL_TEARDOWN_WAIT_MS = 300

#: How long the parked task holds its thread. Comfortably past the bound above, so the fixture is
#: guaranteed to see a busy pool — and short enough that the pool empties on its own moments later,
#: so the subprocess exits rather than being held open by `~QThreadPool`.
_HOLD_SECONDS = 2.0


class _Blocking(QRunnable):
    """A task that occupies the pool past the fixture's patience and then finishes on its own."""

    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()

    def run(self) -> None:
        self.started.set()
        threading.Event().wait(timeout=_HOLD_SECONDS)


def test_leaves_a_pool_thread_running(qapp: QApplication) -> None:
    """Start work on the real gate, let it be running, and assert nothing else.

    The assertion this file exists for is made by the root conftest's fixture *after* this returns,
    so there is deliberately nothing to assert here. A test body that also asserted something would
    make a failure ambiguous between the leak and the assertion.
    """
    blocker = _Blocking()
    assert thumbnails.pool().start(blocker)
    assert blocker.started.wait(timeout=10)
