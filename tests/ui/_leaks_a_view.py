"""A test that deliberately leaks a view, so `T-238`'s guard can be proved to fail (`T-238`).

**Not collected by the suite**, and the filename is what does it: `python_files` is pytest's
default `test_*.py`, so a directory collection walks past this. `pytest` still collects a file
named directly on the command line, which is how `test_suite_isolation.py` runs it — the same shape
`test_theme_restoration.py` uses for `T-229`'s pair, one step further because this one *must* fail.

**It lives under `tests/ui/` on purpose.** The thing being proved is the guard *as wired* —
`tests/ui/conftest.py`'s autouse fixture, `settle_deferred_deletions`, and the orphan check in the
order the conftest puts them. A copy of the fixture next to the leak would prove the function and
not the wiring, which is the mistake `T-096` and `T214-R1` both name in other files.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QListView

#: Somewhere to park the leak so Python's refcount does not free it the moment the test returns.
#:
#: **The hazard is a view that outlives its owner, not one that outlives its test.** A parentless
#: view held here is exactly the state `qt_lifecycle.orphaned_views` looks for: alive, and owned by
#: nothing that will delete it deterministically. Cleared by the guard test after the subprocess
#: exits, which costs nothing — the process is gone.
_KEEP_ALIVE: list[QListView] = []


def test_leaks_a_view(qapp: QApplication) -> None:
    """Create a view with no parent, keep it alive past teardown, and assert nothing else.

    The assertion this file exists for is made by the conftest fixture *after* this returns, so
    there is deliberately nothing to assert here. A test body that also asserted something would
    make a failure ambiguous between the leak and the assertion.
    """
    _KEEP_ALIVE.append(QListView())
