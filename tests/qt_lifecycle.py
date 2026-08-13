"""Dropping a Qt object safely, and catching the moment a suite does not (`T-128`).

**Not in `tests/conftest.py`.** That file is deliberately Qt-free so `tests/unit/` keeps running
headless and without Qt (`ai/TESTING.md` §1), and a root conftest is imported before every suite.
This module is imported only by the conftests that already have Qt.

## What went wrong, and why it took a soak to find

An unattended soak died twice in 39 full-suite runs with `SIGSEGV`, both times at the same place:

```
QCoreApplication::notifyInternal2(QObject*, QEvent*)   <- fault
QTimerInfoList::activateTimers()
QEventDispatcherGlib::processEvents(...)
```

The core dumps (kept by `systemd-coredump`, read with `gdb`) name the instruction —
`mov 0x8(%rdi),%rax` then `mov 0x58(%rax),%rbx`, which is `receiver->d_ptr->threadData` — and show
the receiver's memory already recycled: its vtable slot held `0x00005567c4c40522`, not even
8-aligned, and its `d_ptr` slot held noise. **A timer fired into a QObject that had been freed.**

That can happen two ways, and both start the same:

1. the object is destroyed on a thread that does not own the timer, so Qt refuses to unregister it
   (`QObject::~QObject: Timers cannot be stopped from another thread`) and the entry survives; or
2. the object is destroyed *during* `activateTimers()` — by Python's cycle collector, which runs
   on whichever thread happens to allocate — so the timer is unregistered correctly but the
   iteration already holds the pointer.

**The precondition is the same for both, and it is the thing worth forbidding: a QObject with a
running timer became garbage.** Which of the two then kills the process is a detail of timing that
this module does not need to distinguish, and neither does the fix.

## How a teardown got there

`DownloadManager.is_idle` answers a question about *work* — no sessions, no reservations, nothing
waiting or retrying. It says nothing about the manager's own poll timer, which `_tick` stops on a
later tick. So `is_idle` goes true up to one poll interval before the timer stops, and five
teardowns polled it and then dropped the manager inside that window.

**The application is not on this path**: `app.py` waits for the `idle` *signal*, which is emitted
only after `_timer.stop()`. Nothing in `src/` reads `is_idle` at all. This is a harness defect, and
`has_settled` is the question the harness should have been asking.

## The second lifetime hazard: a widget tree collected at a moment nobody chose (`T-238`)

An `-n auto` unit/UI worker died with `SIGSEGV` inside a test that creates no view at all:

```
_Py_HandlePending
  → Shiboken::BindingManager::runDeletionInMainThread
    → QAbstractItemView::~QAbstractItemView
      → QObject::disconnectImpl        ← faults here
```

**`_Py_HandlePending` is the whole story.** Shiboken queues a C++ deletion when the wrapper's last
reference is dropped somewhere it cannot delete directly, and that queue is drained at an arbitrary
bytecode boundary — so the destructor runs inside *whichever test happens to be executing*, which
is why xdist blamed a test whose file imports no view class in 2600 lines.

**Two measurements decided the shape of the guard below**, over the whole `tests/ui` suite:

| Predicate at teardown | Tests tripping it |
|---|---|
| a view created by this test is still alive | **802 of 839** |
| …and it has no parent | **0** |
| …and its wrapper is otherwise unreferenced | **0** |

So the obvious rule — *no view outlives its test* — is not a lifetime rule at all: it would fail
96% of a correct suite, because a view parented into a widget tree is **owned** and dies with its
owner. What no correct test produces is a view that is alive with **no owner**, which is the shape
of a tree whose root has already gone.

That leaves the real hazard as *when* the owner is collected, and the answer is to stop leaving it
to chance: `settle_deferred_deletions()` collects and drains **at the test boundary, on the main
thread**, so a deletion cannot carry into a later test's bytecode; `assert_no_orphaned_views()`
then fails the test that left an ownerless view behind.

**What this does not claim.** It does not reproduce the segfault — 60 runs did not — and it does
not prove the crash was a harness defect rather than a product one. It removes the carry-over the
retained stack shows, and it names a leak at its cause instead of at its consequence
(`ai/TESTING.md` §13).
"""

from __future__ import annotations

import gc
import time
from collections.abc import Callable, Iterable
from typing import Any, Final, Protocol

from PySide6.QtCore import QCoreApplication, QEvent, QTimer, qInstallMessageHandler

#: What Qt says when a QObject owning a live timer is destroyed from the wrong thread.
#:
#: It is a warning, and the process usually keeps running — until the orphaned entry fires, which
#: may be a test or two later and looks like an unrelated crash. Treated as fatal here for the
#: reason `ai/TESTING.md` §13 gives about intermittents: the useful signal is the one at the cause,
#: not the one at the consequence.
CROSS_THREAD_TIMER: Final = "Timers cannot be stopped from another thread"


class Settleable(Protocol):
    """A `QObject` that also answers `is_idle` — the manager's shape, structurally.

    `QObject` is the base rather than a second stub method, so `findChildren` comes from Qt's own
    type and this file does not restate a camelCase API it does not own.
    """

    @property
    def is_idle(self) -> bool: ...

    def findChildren(  # noqa: N802
        self, type_: type, /, *args: Any, **kwargs: Any
    ) -> list[Any]: ...


def is_still_polling(owner: Settleable) -> bool:
    """Whether `owner` still has a running timer registered with the event dispatcher.

    **Through `findChildren`, which is public Qt API**, rather than by reaching for a private
    attribute: what matters is not that `DownloadManager` calls its timer `_timer` but that *any*
    live timer parented to this object is an entry the dispatcher will follow back to it.
    """
    return any(timer.isActive() for timer in owner.findChildren(QTimer))


def has_settled(manager: Settleable) -> bool:
    """Idle **and** no longer polling — the question a teardown has to ask before dropping it.

    Two terms, because `is_idle` is about the queue's work and the timer is about the object's own
    lifecycle, and it is the second that decides whether dropping the reference is safe. A manager
    that never started anything satisfies both immediately, which is why this is a predicate rather
    than a wait on the `idle` signal: that signal is only emitted by a tick, and a manager that
    never ran never ticks.
    """
    return manager.is_idle and not is_still_polling(manager)


def drain(
    app: QCoreApplication,
    managers: Iterable[Settleable],
    *,
    timeout: float = 30.0,
    describe: Callable[[], str] = lambda: "",
) -> None:
    """Pump until every manager has settled, then say so or fail saying which had not.

    **Asserted, never merely waited out.** Falling through a deadline and carrying on is how a
    stalled teardown becomes the next test's crash, and the whole of `T-128` is one teardown
    returning while its object was still live to Qt.
    """
    built = list(managers)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not all(has_settled(m) for m in built):
        app.processEvents()
        time.sleep(0.005)

    unsettled = [
        f"idle={m.is_idle} polling={is_still_polling(m)}" for m in built if not has_settled(m)
    ]
    assert not unsettled, (
        f"a manager never finished shutting down after {timeout} s: {unsettled}. "
        "Dropping one while it still has a registered timer leaves the dispatcher holding a "
        "pointer to an object Python is about to free — see tests/qt_lifecycle.py. " + describe()
    )


#: **One recorder, shared by every handler and every assertion** (`T128-R1`).
#:
#: Qt keeps exactly one message handler. Both Qt conftests install one, so in a full run the second
#: installation replaces the first — and the first version of this module gave each call its *own*
#: recorder and had the assertions read `_orphaned[0]`. The live handler therefore wrote to a list
#: nothing inspected, and the detector was blind for the whole suite: it could not produce the
#: failure it exists to produce.
#:
#: Flat, module-level, and written by whichever handler Qt currently holds. `pytest-qt` takes the
#: handler for the duration of each test call and restores the newest project handler before
#: teardown — which is the interval `T-128` is about — so what matters is not *which* of our
#: handlers is installed but that they all report to the same place.
_orphaned: list[str] = []


def fail_on_orphaned_timers() -> None:
    """Make Qt's cross-thread timer warning fail the run, at the cause rather than the crash.

    Called once per Qt conftest. Installing twice is harmless now that every handler reports to the
    one recorder above — which is the correction for `T128-R1`, and is why this does not try to be
    idempotent: a flag would have to survive `pytest-qt` replacing and restoring the handler, and
    the shared recorder makes the question moot.

    **Raising here would not stop the process** — Qt calls the handler from wherever the deletion
    happened, and an exception on a worker thread would be swallowed. So it records, and
    `assert_no_orphaned_timers` is what fails the test.
    """

    def handler(mode: Any, context: Any, message: str) -> None:
        text = str(message)
        if CROSS_THREAD_TIMER in text:
            _orphaned.append(text)
        print(f"Qt: {text}", flush=True)

    qInstallMessageHandler(handler)


def assert_no_orphaned_timers() -> None:
    """Fail if Qt reported a cross-thread timer removal since the last check, and reset.

    Reset so one orphaned timer fails exactly the test that produced it rather than every test
    after it, which would bury the cause under a page of consequences.
    """
    if not _orphaned:
        return
    reported = list(_orphaned)
    _orphaned.clear()
    raise AssertionError(
        f"Qt refused a cross-thread timer removal {len(reported)} time(s): {reported}. "
        "A QObject owning a live timer was destroyed from a thread that does not own it, so the "
        "dispatcher still holds a pointer to freed memory and will follow it on the next tick. "
        "See tests/qt_lifecycle.py."
    )


# --- `T-238`: a widget tree must not be collected inside somebody else's test -------------------


def settle_deferred_deletions(app: QCoreApplication) -> None:
    """Collect wrappers and run every pending deletion **here**, on the main thread.

    Two steps, and they are not interchangeable:

    1. `gc.collect()` finalises wrappers whose only remaining reference was a cycle. A widget tree
       kept alive by one — a window holding a view that holds a delegate that holds the window — is
       freed at whatever allocation happens to trip the collector otherwise, and that is a bytecode
       boundary in a later test.
    2. `sendPostedEvents(None, DeferredDelete)` runs the deletions `deleteLater()` posted. Qt
       delivers those only from an event loop, and a headless test that never spins one leaves them
       queued for whoever spins one next.

    **Called at the end of every UI test rather than at the end of the session**, because the point
    is the boundary: after this returns, no later test can inherit a deletion of an object it never
    created. `T-238`'s retained stack is exactly that inheritance — a `~QAbstractItemView` running
    at `_Py_HandlePending` inside a test whose file constructs no view.

    **`app` is passed rather than fetched** so this cannot silently do nothing in a process that
    has no application object; every caller is a Qt conftest that already has one.
    """
    gc.collect()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def orphaned_views(app: QCoreApplication) -> list[str]:
    """Every live item view with no parent — a tree whose owner has gone, described for a message.

    **Parentless is the predicate, and it was chosen by measurement rather than by taste.** Over
    `tests/ui`, 802 of 839 tests leave a view alive at teardown and **none** leaves one without a
    parent: a parented view is owned, and dies with its owner. So "alive" describes a correct
    suite and "alive with no owner" describes the shape this exists to catch — a view whose tree
    root was collected while it was not.

    Widgets are asked for through `QApplication.allWidgets()` — public API, and the same source the
    measurement used — rather than by walking `gc.get_objects()`, which would also return wrappers
    for C++ objects that are already gone.
    """
    from PySide6.QtWidgets import QAbstractItemView, QApplication

    if not isinstance(app, QApplication):
        # A `QCoreApplication` process has no widgets at all, which is the honest answer rather
        # than an import-time refusal: `tests/integration` shares this module and has no display.
        return []
    return [
        f"{type(view).__name__}({view.objectName() or 'unnamed'})"
        for view in QApplication.allWidgets()
        if isinstance(view, QAbstractItemView) and view.parent() is None
    ]


def assert_no_orphaned_views(app: QCoreApplication) -> None:
    """Fail the test that left an item view alive with no owner (`T-238`).

    **This is the guard the maintainer authorised, and its own entry says what it is worth**: it
    does not reproduce the segfault and does not prove the fault was the harness's. It fails at the
    test that produced the condition, on an ordinary run, instead of leaving a deletion to execute
    inside an unrelated test — which is the attribution problem the crash arrived with, and
    `ai/TESTING.md` §13's rule about intermittents.
    """
    orphans = orphaned_views(app)
    if not orphans:
        return
    raise AssertionError(
        f"this test left {len(orphans)} item view(s) alive with no parent: {orphans}. "
        "A view whose owner has been collected is destroyed on its own, at whatever bytecode "
        "boundary Python's collector reaches next — which may be inside another test, and is the "
        "shape of T-238's SIGSEGV (~QAbstractItemView under runDeletionInMainThread). Give it a "
        "parent, or delete it before the test ends. See tests/qt_lifecycle.py."
    )
