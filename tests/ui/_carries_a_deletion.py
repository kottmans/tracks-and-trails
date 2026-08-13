"""Two tests, in order, that prove the *drain* half of `T-238`'s guard (`T238-R1`).

**Why this exists rather than one more leaked view.** `_leaks_a_view.py` proves
`assert_no_orphaned_views`, and only that: the review measured that it still fails with
`settle_deferred_deletions` reduced to a no-op, so the drain — the half that keeps an unreachable
tree or a queued `DeferredDelete` from executing inside a later test — had no evidence of its own.

**The drain is two statements and this file mutation-checks them separately.** Neither case below
is visible to the orphan assertion, which is the point: one is a widget tree whose root is
unreachable but whose view is *parented*, and the other is a deletion that has been *posted* and
not delivered. Both survive their own test's teardown if the matching statement is missing, and
the second test is what sees them.

| Left behind by the first test | Survives without |
|---|---|
| a tree held only by a reference cycle | `gc.collect()` |
| a `deleteLater()` on a still-parented view | `sendPostedEvents(DeferredDelete)` |

Both are seen by the second test, which asserts before it spins anything.

**Not collected by the suite** — `python_files` is `test_*.py` and this is not — and the order is
the assertion, so `test_suite_isolation.py` runs both node ids in one subprocess. Running them
apart, or in the other order, proves nothing.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication, QListView, QWidget

#: The name of the tree whose only reference is a cycle. `gc.collect()` is what frees it; a
#: refcount never will, because each half of the cycle keeps the other alive.
CYCLE_ROOT = "t238-cycle-root"

#: The name of the view whose deletion has been *posted*. Its parent stays referenced and alive,
#: so nothing else will take it down — only the delivery of `DeferredDelete` does.
PENDING_VIEW = "t238-pending-view"

#: The parent, kept alive on purpose. A parent collected here would delete the child itself and
#: the second test would pass for the wrong reason — the failure mode this file exists to avoid.
_KEPT: list[QWidget] = []


class _Cyclic(QWidget):
    """A widget tree that refers to itself, so only the cycle collector can free it.

    Qt parenting alone would not do it: the root is parentless, so its lifetime is the Python
    wrapper's, and the wrapper is immortal while it is part of a cycle.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName(CYCLE_ROOT)
        self.view = QListView(self)
        # The cycle: the child's Python attribute points back at the root that owns it.
        self.view.root = self  # type: ignore[attr-defined]


@pytest.fixture
def _post_a_deletion_after_the_test() -> Iterator[None]:
    """Post the deletion in a **finalizer**, after the test body and after pytest-qt's own drain.

    Deleting inside the body would let any event processing the test happens to do deliver it,
    which would prove nothing about the conftest's boundary. A finalizer runs at the same place a
    real teardown leak would: after the test, before the next one.
    """
    yield
    parent = QWidget()
    view = QListView(parent)
    view.setObjectName(PENDING_VIEW)
    _KEPT.append(parent)
    view.deleteLater()


def test_leaves_a_deletion_pending(
    qapp: QApplication, _post_a_deletion_after_the_test: None
) -> None:
    """Leave both carry-overs behind and assert nothing. The next test is the assertion."""
    _KEPT.append(_Cyclic())
    _KEPT.pop()  # the cycle is now the only thing holding it


def test_the_boundary_left_nothing_behind(qapp: QApplication) -> None:
    """Neither carry-over may still be alive when this test starts.

    **Asserted at the top of the body, before anything spins an event loop**, because a
    `processEvents()` here would deliver the pending deletion itself and the test would pass
    against a conftest that does nothing.
    """
    alive = {widget.objectName() for widget in QApplication.allWidgets()}

    assert CYCLE_ROOT not in alive, (
        f"a widget tree held only by a reference cycle survived the previous test's boundary. "
        f"Without gc.collect() there it is freed at whatever allocation trips the collector next "
        f"— inside this test, or another one. See tests/qt_lifecycle.py ({CYCLE_ROOT})."
    )
    assert PENDING_VIEW not in alive, (
        f"a view whose deleteLater() was posted in the previous test is still alive. Without "
        f"sendPostedEvents(DeferredDelete) at the boundary, Qt delivers it inside whichever test "
        f"next spins an event loop — which is T-238's stack. See tests/qt_lifecycle.py "
        f"({PENDING_VIEW})."
    )
