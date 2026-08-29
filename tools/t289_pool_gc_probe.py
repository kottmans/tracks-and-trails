"""Does CPython's collector destroy a `QWidget` on a pool thread? (`T-289` criterion 4.)

**The question, and why it needs an instrument.** `T-289` is a `double free or corruption (!prev)`
abort recorded in `ai/evidence/2026-08-27-T212-ytdlp-update-double-free.md`. Its established half is
that `gc_collect_main` ran on a `QThreadPool` thread and took `~QWidget` down with it, five
`deleteChildren` levels deep, on a thread Qt does not permit widget destruction on. The crash is
intermittent by nature — the collector runs wherever an allocation threshold happens to trip — so
waiting for it is not a method. **This arranges the precondition deliberately and reports which
thread performed the destruction.**

`T-238`'s probe is the model, and its lesson is the reason this one is written the way it is: a
`weakref.finalize` callback runs on whichever thread dropped the last reference, so the deciding
thread is directly observable rather than inferred.

**Why a reference cycle rather than a plain `del`.** A widget released by an ordinary decref is
destroyed on the thread doing the releasing, which proves nothing about the collector. `T-273`
established that this application's windows are held by callables Qt objects close over, across
edges `gc` cannot traverse — so the tree that can only go via `gc` is the realistic shape, and it is
the one the dump implicates. The cycle here is the smallest thing with that property.

**This does not attempt to reproduce the double free**, and that is deliberate. Corrupting the heap
proves nothing the precondition does not, and an instrument that aborts its own process cannot
report. If the abort happens anyway, the exit status says so and that is a stronger finding than the
one this was built to look for.

    QT_QPA_PLATFORM=offscreen .venv/bin/python tools/t289_pool_gc_probe.py

Exit status is 0 when the probe ran, whatever it found — the finding is the report (`T-291`'s
lesson, one file over).
"""

from __future__ import annotations

import gc
import json
import sys
import threading
import weakref
from typing import Any

from PySide6.QtCore import QCoreApplication, QRunnable, Qt, QThreadPool, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

#: Filled by the finaliser, from whichever thread performed the last **Python** decref.
FINALISED_ON: list[str] = []

#: Filled from `QObject::destroyed`, which is emitted inside `~QObject` — so a `DirectConnection`
#: handler runs on whichever thread is executing the **C++** destructor.
#:
#: **These are two different questions and the first version of this probe conflated them.** It
#: reported the finalisation thread and called it destruction, which is wrong in the way that
#: matters: `shiboken` can hand the C++ deletion to the main thread through
#: `BindingManager::runDeletionInMainThread`, and measured here it does exactly that. A probe that
#: reads only the decref thread cannot tell a marshalled deletion from an unmarshalled one, and
#: `T-289` is entirely about which of those happened.
DESTROYED_ON: list[str] = []


class _Cycle:
    """A container that holds a widget tree and itself, so only `gc` can release it."""

    def __init__(self, widget: QWidget) -> None:
        self.widget = widget
        self.myself = self


def _build_a_collectable_tree() -> None:
    """A parented tree whose only Python reference is inside a cycle.

    Shaped after the dump: a `QLabel` with `setBuddy`, because the GUI-thread stack was inside
    `QLabel::setBuddy` clearing itself as its buddy was destroyed, and nested children, because the
    pool-thread stack was five `deleteChildren` levels down.
    """
    root = QWidget()
    layout = QVBoxLayout(root)
    inner = QWidget(root)
    deeper = QWidget(inner)
    layout.addWidget(inner)

    field = QLabel("value", deeper)
    label = QLabel("&Name", deeper)
    label.setBuddy(field)

    weakref.finalize(root, lambda: FINALISED_ON.append(threading.current_thread().name))
    # `DirectConnection` so the handler runs on the destroying thread rather than being queued to
    # the receiver's. Queued would answer a different question and always say "main".
    root.destroyed.connect(
        lambda *_: DESTROYED_ON.append(threading.current_thread().name),
        Qt.ConnectionType.DirectConnection,
    )
    _Cycle(root)  # the only reference, and it refers to itself


class _CollectOnThePool(QRunnable):
    """`gc.collect()` where the dump found it: on a pool thread, in this task's Python."""

    def __init__(self) -> None:
        super().__init__()
        self.thread_name = ""
        self.collected = 0

    def run(self) -> None:
        self.thread_name = threading.current_thread().name
        self.collected = gc.collect()


def main() -> int:
    # **`--on-the-gui-thread` is the control, and it is not optional decoration.** A probe that
    # only ever reports the pool thread looks exactly like a probe that hard-codes it. Running the
    # identical collection on the GUI thread has to produce the *other* answer before the first
    # one means anything — `ai/TESTING.md`'s rule about instruments that report confidently.
    control = "--on-the-gui-thread" in sys.argv

    application = QApplication([sys.argv[0]])
    gui_thread = threading.current_thread().name

    _build_a_collectable_tree()
    gc.disable()  # so the collection that matters is the one on the pool thread, not an earlier one

    task = _CollectOnThePool()
    task.setAutoDelete(False)
    if control:
        task.run()
    else:
        pool = QThreadPool()
        pool.setMaxThreadCount(1)
        pool.start(task)

    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.start(5000)
    while deadline.isActive() and not FINALISED_ON:
        QCoreApplication.processEvents()
    if not control:
        pool.waitForDone(5000)
    # **Drain after the collection**, because a marshalled deletion is queued to the main thread
    # and only runs when the main thread gets to it. Looking before this is how a queued deletion
    # reads as "never destroyed".
    for _ in range(50):
        QCoreApplication.processEvents()
    gc.enable()

    finalised = FINALISED_ON[0] if FINALISED_ON else None
    destroyed = DESTROYED_ON[0] if DESTROYED_ON else None
    report: dict[str, Any] = {
        "mode": "control: collected on the GUI thread" if control else "collected on a pool thread",
        "gui_thread": gui_thread,
        "pool_thread": task.thread_name,
        "objects_collected": task.collected,
        "python_finalised_on": finalised,
        "cpp_destructor_ran_on": destroyed,
        "decref_off_the_gui_thread": bool(finalised) and finalised != gui_thread,
        "destroyed_off_the_gui_thread": bool(destroyed) and destroyed != gui_thread,
    }
    print(json.dumps(report, indent=2))

    if finalised is None:
        print("\nINCONCLUSIVE: the tree was never finalised, so nothing was measured.")
    elif destroyed is None:
        print(
            "\nINCONCLUSIVE: the last Python reference went, but no C++ destructor was observed. "
            "A queued deletion the main thread never reached looks exactly like this."
        )
    elif report["destroyed_off_the_gui_thread"]:
        print(
            f"\nREPRODUCED: the C++ destructor ran on {destroyed!r}, which is not the GUI thread "
            f"({gui_thread!r}). That is T-289's established precondition."
        )
    elif not report["decref_off_the_gui_thread"]:
        # **Neither of these is the marshalling conclusion, and that was the defect.** Both events
        # happened on the GUI thread, so nothing crossed a thread and nothing was marshalled;
        # printing the pool mode's sentence here reported a mechanism the run cannot see
        # (`T289-R1`). Which of the two it is depends on where the collection was *supposed* to
        # run, so the mode decides rather than the numbers.
        if control:
            print(
                f"\nCONTROL AS EXPECTED: the collection ran on the GUI thread ({gui_thread!r}), "
                f"and both the last Python reference and the C++ destructor went there too "
                f"({finalised!r} / {destroyed!r}). Nothing was marshalled and nothing needed to "
                f"be. This is the answer the pool mode must NOT give, and it is what makes that "
                f"mode's split evidence about the pool thread rather than about the instrument."
            )
        else:
            print(
                f"\nINCONCLUSIVE: the collection was supposed to run on a pool thread, but the "
                f"last Python reference went on {finalised!r}, which is the GUI thread. This run "
                f"measured the control's situation, so it says nothing about the pool's."
            )
    else:
        print(
            f"\nNOT REPRODUCED — and this is the finding, not a null result. The last Python "
            f"reference was dropped on {finalised!r}, but the C++ destructor ran on {destroyed!r}: "
            f"shiboken marshalled the deletion to the GUI thread. An off-GUI decref is therefore "
            f"NOT sufficient to destroy a widget off the GUI thread, and a probe that reads only "
            f"the decref thread cannot tell these apart."
        )

    application.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
