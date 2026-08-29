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

from PySide6.QtCore import QCoreApplication, QRunnable, QThreadPool, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

#: Filled by the finaliser, from whichever thread performed the last decref.
FINALISED_ON: list[str] = []


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
    QCoreApplication.processEvents()
    gc.enable()

    finalised = FINALISED_ON[0] if FINALISED_ON else None
    report: dict[str, Any] = {
        "mode": "control: collected on the GUI thread" if control else "collected on a pool thread",
        "gui_thread": gui_thread,
        "pool_thread": task.thread_name,
        "objects_collected": task.collected,
        "widget_finalised_on": finalised,
        "destroyed_off_the_gui_thread": bool(finalised) and finalised != gui_thread,
    }
    print(json.dumps(report, indent=2))

    if finalised is None:
        print("\nINCONCLUSIVE: the tree was never finalised, so nothing was measured.")
    elif report["destroyed_off_the_gui_thread"]:
        print(
            f"\nREPRODUCED: a QWidget tree was destroyed on {finalised!r}, which is not the GUI "
            f"thread ({gui_thread!r}). That is T-289's established precondition."
        )
    else:
        print(f"\nNOT REPRODUCED: the tree was destroyed on the GUI thread ({finalised!r}).")

    application.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
