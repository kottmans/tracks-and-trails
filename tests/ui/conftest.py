"""Qt tests run without a display.

`TESTING.md` §10 and `T-006` both require the UI suite to pass headless on Linux and Windows
CI runners. Setting the platform here rather than relying on the caller's environment means a
plain `pytest` reproduces what CI does.
"""

import os
import time
from collections.abc import Callable, Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Imported after the platform is pinned above, so nothing can load a Qt plugin before the
# offscreen choice is in the environment.
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from tests import qt_lifecycle
from tracks_and_trails.ui import theme


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


# --- `T-238`: a widget tree is collected here, not inside somebody else's test ------------------
#
# An `-n auto` worker died with `SIGSEGV` in `~QAbstractItemView`, reached from
# `_Py_HandlePending` — a deferred deletion running at an arbitrary bytecode boundary — inside a
# test whose file constructs no view at all. Sixty runs did not reproduce it, so the maintainer
# authorised the guard instead: the useful signal is the one at the cause (`ai/TESTING.md` §13).
#
# **Two halves, and only the second is an assertion.** Collecting and draining at the boundary is
# what stops a deletion carrying into a later test; the orphan check is what names a test that
# leaves a view without an owner. `tests/qt_lifecycle.py` records the measurements that chose
# `parentless` as the predicate — 802 of 839 tests leave a view *alive*, and none leaves one
# unparented, so the obvious rule would have failed a correct suite.
#
# **Ordered after the timer check on purpose**: a collection here can run a `QObject`'s destructor,
# and if that object owns a live timer Qt warns, which is `_no_orphaned_timers`' subject rather
# than this one's. Fixtures finalise in reverse order of setup, so this one — declared later —
# runs first and any warning it provokes is still checked.
#
# **The two calls inside this fixture are ordered, and the order is load-bearing — measured, not
# reasoned.** The reviewer swapped them so the assertion ran before the drain, and the helper
# subprocess died with **SIGSEGV (-11), deterministically**. That is the closest thing this
# investigation has to a reproduction: scanning live widgets while deletions are still queued
# walks a list Qt is about to change. Drain first, then look.


@pytest.fixture(autouse=True)
def _no_orphaned_views(qapp: QApplication) -> Iterator[None]:
    yield
    qt_lifecycle.settle_deferred_deletions(qapp)
    qt_lifecycle.assert_no_orphaned_views(qapp)


# --- `T-225`: the application's dressing is global, so dressing it dresses every later test -----
#
# `theme.apply` changes three things on the one `QApplication` the session shares — the style
# sheet, the palette, and the module-level theme `_applied` — and **nothing put them back**. A test
# that dressed the application therefore dressed every test that ran after it in the same process.
#
# **That is what `T-225` was.** `tests/ui/test_row_delegate.py` has one test that applies both
# themes and leaves `LIGHT` on. Two `tests/ui/test_add_dialog.py` tests assert behaviour that only
# holds on an *undressed* application, and both failed when that file ran first:
#
#   - `PlaylistPanel` calls `setAutoFillBackground(True)` for the unstyled case a test window runs
#     in, and Qt's style-sheet polish clears it — so the panel's own `autoFillBackground` assertion
#     is an assertion about a bare application.
#   - A probe point computed as *off every row* stops being off every row once the sheet's metrics
#     make the rows taller, so a keyboard-fallback test silently drove the pointer path instead.
#
# Both files passed alone. The suite was green only because pytest collects `add_dialog` before
# `row_delegate`, which is an accident of the alphabet rather than a property anything asserted.
#
# **Restored around every test rather than fixed in the two tests that failed.** A reset bolted
# onto today's failures leaves the next one to be found by accident; putting the dressing back at
# the boundary every test already has means no test can leak it, including tests not yet written.
# Dressing the application inside a test stays entirely legitimate — thirteen call sites do it on
# purpose — and now costs the tests that follow nothing.
#
# **What the regression proves, and what it does not.** `tests/ui/test_suite_isolation.py` fails
# when this restores nothing. It still **passes** when only the style sheet is put back — measured
# by mutation, not assumed — because the two tests `T-225` filed depend on the sheet alone. The
# palette and `theme._applied` are restored regardless, and not for symmetry: `ui/row_delegate.py`
# reads `theme.applied()` while painting, so a leaked one changes what a later test is shown. They
# are a leak with no test on it rather than a leak that cannot happen, and this paragraph is the
# record that they are unproven — `T180-R2`'s lesson, that a mutation check is worth only what it
# is aimed at.


def _dressing(app: QApplication) -> tuple[str, QPalette, theme.Theme]:
    """Everything `theme.apply` changes, in one value that can be compared and put back.

    Typed `QApplication` rather than the `QCoreApplication` its neighbours take: a style sheet and
    a palette are widget concerns and live on the `QtWidgets` class, which is what `qapp` is.

    The palette is compared by `QPalette.__eq__` rather than by `cacheKey()`: a restored palette
    is *equal* to the saved one but does not get its cache key back, so a key comparison would
    report a leak on every test that dressed and cleaned up correctly.
    """
    return app.styleSheet(), app.palette(), theme.applied()


@pytest.fixture(autouse=True)
def _undressed_afterwards(qapp: QApplication) -> Iterator[None]:
    """Put the application's theme back the way this test found it."""
    sheet, palette, applied = _dressing(qapp)
    yield
    if _dressing(qapp) == (sheet, palette, applied):
        return
    qapp.setStyleSheet(sheet)
    qapp.setPalette(palette)
    # The module global `theme.apply` writes. Restored directly because `theme.apply` is the only
    # thing that sets it and calling that would re-dress the application this is undressing.
    theme._applied = applied
