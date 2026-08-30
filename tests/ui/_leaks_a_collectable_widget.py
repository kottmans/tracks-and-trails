"""A test that leaves a widget the collector would destroy, so `T-289`'s guard can be proved.

**Not collected by the suite**, and the filename is what does it: `python_files` is pytest's
default `test_*.py`, so a directory collection walks past this. `tests/ui/test_suite_isolation.py`
names it on the command line, which pytest still collects — the same shape `_leaks_a_view.py` uses,
for the same reason.

**It lives under `tests/ui/` on purpose.** What is being proved is the guard *as wired*: the
conftest's autouse fixture, the boundary drain, and the collector check in the order the conftest
puts them. A copy of the check beside the leak would prove the function and not the wiring.

**The shape is `T-289`'s precondition exactly** and each part of it is load-bearing:

- **A Python subclass.** Measured 2026-08-30: a plain `QWidget` is marshalled to the GUI thread and
  a subclass is not, so a leak built from `QWidget()` would be caught by nothing and prove nothing.
- **No Qt parent**, so `shiboken6.ownedByPython` is `True` and the wrapper's dealloc is what
  destroys the C++ object.
- **Reachable only through a reference cycle**, so the collector is what frees it rather than a
  refcount reaching zero — which is the difference between "destroyed here" and "destroyed on
  whichever thread the collector happens to run on".
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QWidget


class _Leaked(QWidget):
    """Defined in Python, which is the property that makes the destruction happen in place."""


class _Cycle:
    """Holds the widget and itself, so only the collector can release either."""

    def __init__(self, widget: QWidget) -> None:
        self.widget = widget
        self.myself = self


def test_leaks_a_collectable_widget(qapp: QApplication) -> None:
    """Build the state and assert nothing else.

    The assertion this file exists for is made by the conftest fixture *after* this returns, so
    there is deliberately nothing to assert here: a test body that also asserted something would
    make a failure ambiguous between the leak and the assertion.
    """
    _Cycle(_Leaked())
