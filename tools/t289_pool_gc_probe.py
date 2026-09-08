"""Does CPython's collector destroy a `QWidget` on a pool thread? (`T-289` criterion 4.)

**The question, and why it needs an instrument.** `T-289` is a `double free or corruption (!prev)`
abort recorded in `docs/project/evidence/2026-08-27-T212-ytdlp-update-double-free.md`. Its
established half is that `gc_collect_main` ran on a `QThreadPool` thread and took `~QWidget` down
with it, five `deleteChildren` levels deep, on a thread Qt does not permit widget destruction on.
The crash is intermittent by nature — the collector runs wherever an allocation threshold happens to
trip — so waiting for it is not a method. **This arranges the precondition deliberately and reports
which thread performed the destruction.**

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

    QT_QPA_PLATFORM=offscreen .venv/bin/python tools/t289_pool_gc_probe.py [flags]

Exit status is 0 when the probe ran, whatever it found — the finding is the report (`T-291`'s
lesson, one file over). **Unless the release aborts the process, which is itself an observation**;
every event is printed and flushed as it happens, so a crash costs the crash rather than the run.

## Two variables, added 2026-08-30, and why

The first version measured a **never-shown synthetic** tree and found shiboken **marshalling**: the
decref happened on `Dummy-1`, the destructor on `MainThread`, and the crash's precondition was not
reproduced. `T-238`'s criterion-4 run then found the missing variable by accident. Releasing a
**shown** widget on the *main* thread ran `~QDialog` → `hide_helper()` → the platform plugin and
**aborted** — a destructor that does far more work than an unshown one, because it has a platform
window to take down.

So the two things that differ between this probe's null result and the dump are now flags:

- **`--shown`** realises the tree before collecting. One variable, isolated: does shiboken still
  marshal when the widget has a window to close?
- **`--real-screens`** builds the application's own screens through `tests/ui/surfaces.py` — the
  same five `tests/ui/conftest.py` audits — instead of the synthetic tree. Product shapes, with the
  signal and closure graph a bare `QWidget` does not have.

**Neither flag changes what is measured**, only what is measured *on*: the finalisation thread and
the destruction thread, from the same two callbacks.
"""

from __future__ import annotations

import gc
import json
import sys
import threading
import weakref
from pathlib import Path
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


def _watch(root: QWidget) -> None:
    """Record both threads, and print each event as it arrives.

    **Printed from inside the handlers, flushed** (2026-08-30): releasing a shown widget has been
    seen to abort the process, and a finding held in a list until the end is a finding lost when
    that happens.
    """

    def finalised() -> None:
        name = threading.current_thread().name
        FINALISED_ON.append(name)
        print(f"    · last Python reference dropped on {name!r}", flush=True)

    def destroyed(*_args: object) -> None:
        name = threading.current_thread().name
        DESTROYED_ON.append(name)
        print(f"    · C++ ~QObject ran on {name!r}", flush=True)

    weakref.finalize(root, finalised)
    # `DirectConnection` so the handler runs on the destroying thread rather than being queued to
    # the receiver's. Queued would answer a different question and always say "main".
    root.destroyed.connect(destroyed, Qt.ConnectionType.DirectConnection)


def _build_the_real_screens(shown: bool) -> None:
    """The application's own screens, held only by a cycle (`T-238`'s inventory, reused).

    `tests/ui/surfaces.py` is the one list of these, read by `tests/ui/conftest.py`'s accessibility
    sweep and by `T-238`'s criterion-4 probe. Built parentless there, which is exactly the ownership
    this needs: Python owns the C++ objects, so the collector releasing a wrapper is what destroys
    the widget.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tests.ui.surfaces import screens_below_the_add_dialog

    for _label, widget in screens_below_the_add_dialog():
        if shown:
            widget.show()
        _watch(widget)
        _Cycle(widget)
    QCoreApplication.processEvents()


class _DerivedWidget(QWidget):
    """A trivial Python subclass of `QWidget`, and the point is that it *is* one.

    **The `--subclass` variable** (2026-08-30). `--real-screens` reproduced the off-GUI destructor
    where the synthetic tree marshalled, and the screens differ from that tree in several ways at
    once: they are the product's classes, they carry signal connections and closures, and every one
    of them is **defined in Python**. This isolates the last of those — nothing here has behaviour,
    a connection or a closure; it is a `QWidget` whose type happens to live in Python.
    """


def _build_a_collectable_tree(shown: bool = False, derived: bool = False) -> None:
    """A parented tree whose only Python reference is inside a cycle.

    Shaped after the dump: a `QLabel` with `setBuddy`, because the GUI-thread stack was inside
    `QLabel::setBuddy` clearing itself as its buddy was destroyed, and nested children, because the
    pool-thread stack was five `deleteChildren` levels down.
    """
    root = _DerivedWidget() if derived else QWidget()
    layout = QVBoxLayout(root)
    inner = QWidget(root)
    deeper = QWidget(inner)
    layout.addWidget(inner)

    field = QLabel("value", deeper)
    label = QLabel("&Name", deeper)
    label.setBuddy(field)

    if shown:
        # **A widget with a platform window destroys far more than one without**, which is the
        # variable `T-238`'s run turned up: `~QWidget` then runs `hide_helper()` into the platform
        # plugin. Realised here rather than assumed, and drained so the show completes.
        root.show()
        QCoreApplication.processEvents()

    _watch(root)
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
    # one means anything — `docs/project/TESTING.md`'s rule about instruments that report
    # confidently.
    control = "--on-the-gui-thread" in sys.argv
    shown = "--shown" in sys.argv
    real = "--real-screens" in sys.argv
    derived = "--subclass" in sys.argv

    application = QApplication([sys.argv[0]])
    gui_thread = threading.current_thread().name

    subject = (
        f"the application's own screens, {'shown' if shown else 'never shown'}"
        if real
        else (
            f"a synthetic parented tree rooted in "
            f"{'a Python subclass' if derived else 'a plain QWidget'}, "
            f"{'shown' if shown else 'never shown'}"
        )
    )
    where = "the GUI thread (control)" if control else "a pool thread"
    print(f"T-289 criterion 4 — collecting {subject}\n                    on {where}\n", flush=True)

    if real:
        _build_the_real_screens(shown)
    else:
        _build_a_collectable_tree(shown, derived)
    gc.disable()  # so the collection that matters is the one on the pool thread, not an earlier one
    print("  releasing now — if this is the last line, the release aborted the process", flush=True)

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
        "subject": subject,
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
