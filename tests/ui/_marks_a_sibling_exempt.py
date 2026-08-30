"""`T289-R4`'s bypass, as a test that must still fail.

The submitted guard asked `get_closest_marker`, which is **inherited**: the exemption `T-238`'s one
diagnostic needs was available to any test, class or module that spelled the marker — and a real
violation in a marked test passed. A bypass for a memory-corruption guard that spreads by
inheritance is one nobody notices spreading.

**The marker here is applied at module level**, which is the widest spelling and the one that would
have suppressed the guard for every test in the file.

Not collected by the suite — the filename does that — and named on the command line by
`tests/ui/test_suite_isolation.py`.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QWidget

pytestmark = pytest.mark.leaves_a_collectable_widget


class _Leaked(QWidget):
    """Defined in Python, which is what makes the destruction happen in place."""


class _Cycle:
    """Holds the widget and itself, so only the collector can release either."""

    def __init__(self, widget: QWidget) -> None:
        self.widget = widget
        self.myself = self


def test_a_marked_sibling_still_may_not_leave_one(qapp: QApplication) -> None:
    """Claim the exemption from a node that is not the one allowed to have it."""
    _Cycle(_Leaked())
