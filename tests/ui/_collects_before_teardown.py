"""`T289-R2`'s bypass, as a test that must still fail.

The submitted guard sampled at the boundary, so a test that produced the forbidden state and then
collected it **passed** — the widget was gone before anything looked, and automatic collection
reaches the same result with nobody writing a call. The state existed; a pool thread could have been
what ran it.

**Unmarked, deliberately.** This is not an exemption; it is the same violation as
`_leaks_a_collectable_widget.py` with the evidence destroyed on the way out.

Not collected by the suite — the filename does that — and named on the command line by
`tests/ui/test_suite_isolation.py`.
"""

from __future__ import annotations

import gc

from PySide6.QtWidgets import QApplication, QWidget


class _Leaked(QWidget):
    """Defined in Python, which is what makes the destruction happen in place."""


class _Cycle:
    """Holds the widget and itself, so only the collector can release either."""

    def __init__(self, widget: QWidget) -> None:
        self.widget = widget
        self.myself = self


def test_collects_the_dangerous_cycle_before_teardown(qapp: QApplication) -> None:
    """Create the state, collect it inside the test, and assert nothing.

    `gc.collect()` here is the whole point: it is the ordinary call any test may make, and under the
    submitted guard it erased the finding. With `DEBUG_SAVEALL` armed for the test's lifetime the
    collector parks the widget instead of releasing it, so the boundary still sees it.
    """
    _Cycle(_Leaked())
    gc.collect()
