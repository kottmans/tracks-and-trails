"""Which thread drops the last Python reference to each `QWidget` (`T-238` criterion 4).

**What this is for.** `T-238`'s criterion 4 asks whether the `gw7` segfault is product behaviour or
harness behaviour, and that question has stayed open because it *cannot be inferred from a green
suite*. This measures the fault's one precondition instead of waiting for the fault.

**The precondition.** `docs/project/evidence/T238-SEGFAULT-gw7.txt` shows
`~QAbstractItemView` reached from `Shiboken::BindingManager::runDeletionInMainThread` under
`_Py_HandlePending`. Shiboken only queues a deletion for the main thread when the wrapper's last
Python reference was dropped **somewhere else** — so the crash requires a `QWidget` whose refcount
reaches zero off the main thread. A `weakref.finalize` callback runs on whichever thread performed
that final decref, so the precondition is directly observable.

**Usage** — it is a pytest plugin, not a script:

    T238_PROBE_OUT=/tmp/report.txt PYTHONPATH=tools QT_QPA_PLATFORM=offscreen \
        .venv/bin/python -m pytest tests/ui -q -p t238_widget_thread_probe

`docs/project/evidence/README.md`'s rule puts this here rather than the measurement there:
re-running produces the report again, so the instrument is what is worth keeping and the number
belongs in `T-238`.

## Two defects this instrument had first, and how they were found

Both are the shape `docs/project/TESTING.md` warns about — an instrument that reports confidently
about nothing — and neither was visible in its output.

1. **Patching `QWidget.__init__` caught nothing.** Shiboken gives every class its own `__init__`
   slot, so the base-class patch never ran for a `QListView`. The first version reported **zero
   off-thread finalisations over the whole UI suite**, which reads exactly like a clean result.
   Found by running it against a widget dropped on a deliberate worker thread — it saw nothing.
2. **Patching a class that inherits `__init__` nests a wrapper per hierarchy level.** A subclass
   captures the *already patched* parent as its `original`, so a `QListView` five levels below
   `QWidget` was counted five times and ran five callbacks. Found because the instrumented run took
   more than three times the bare suite's 307 s.

**So the self-test below runs first, every time.** A probe that cannot see a known positive is not
evidence of absence, and this one twice looked clean while measuring nothing.
"""

from __future__ import annotations

import contextlib
import os
import threading
import weakref
from collections import Counter
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QWidget

_BY_THREAD: Counter[str] = Counter()
_OFF_THREAD: Counter[str] = Counter()
_patched: set[int] = set()
_constructed = 0
_self_test_saw_the_worker = False


def _note(kind: str) -> None:
    """Runs on whichever thread performed the final decref — the whole measurement."""
    name = threading.current_thread().name
    _BY_THREAD[name] += 1
    if name != "MainThread":
        _OFF_THREAD[f"{kind} dropped on {name}"] += 1


def _patch(cls: type) -> None:
    if id(cls) in _patched:
        return
    _patched.add(id(cls))
    # Only a class that defines its own `__init__`: see defect 2 in the module docstring.
    if "__init__" not in cls.__dict__:
        return
    original = cls.__init__

    def patched(self: Any, *args: Any, **kwargs: Any) -> None:
        global _constructed
        original(self, *args, **kwargs)
        _constructed += 1
        with contextlib.suppress(TypeError):  # not weak-referenceable
            weakref.finalize(self, _note, type(self).__name__)

    with contextlib.suppress(TypeError, AttributeError):  # immutable extension type
        cls.__init__ = patched  # type: ignore[method-assign]


def _walk(cls: type = QWidget) -> None:
    """Patch every `QWidget` subclass known *so far*; classes are imported lazily."""
    _patch(cls)
    for subclass in cls.__subclasses__():
        _walk(subclass)


def _self_test() -> None:
    """Drop a widget on a named worker thread and require the probe to see it.

    Raises rather than warns. A silent probe reports a clean suite, and this one has produced that
    false clean twice — so an instrument that fails its own positive control must stop the run.
    """
    global _self_test_saw_the_worker
    import gc

    from PySide6.QtWidgets import QApplication, QListView

    if QApplication.instance() is None:
        # Not yet — the suite builds one lazily at its first test. `pytest_runtest_setup` keeps
        # asking, and `pytest_sessionfinish` fails the report if it never succeeded, so this
        # early return cannot become a silent skip.
        return
    _walk()
    before = _BY_THREAD["t238-probe-selftest"]
    holder = [QListView()]
    thread = threading.Thread(target=holder.clear, name="t238-probe-selftest")
    thread.start()
    thread.join()
    gc.collect()
    _self_test_saw_the_worker = _BY_THREAD["t238-probe-selftest"] > before
    if not _self_test_saw_the_worker:
        raise RuntimeError(
            "t238_widget_thread_probe did not observe a QWidget it dropped on a worker thread. "
            "The instrument is blind, and a report from it would read as a clean suite. Do not "
            "trust any run in which this fires."
        )
    # Do not let the control appear in the measurement it validates.
    _BY_THREAD["t238-probe-selftest"] -= 1
    if not _BY_THREAD["t238-probe-selftest"]:
        del _BY_THREAD["t238-probe-selftest"]
    _OFF_THREAD.pop("QListView dropped on t238-probe-selftest", None)


def pytest_configure(config: Any) -> None:
    _walk()


def pytest_runtest_setup(item: Any) -> None:
    _walk()
    if not _self_test_saw_the_worker:
        # Retried until a `QApplication` exists, then never again.
        _self_test()


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    path = os.environ.get("T238_PROBE_OUT", "t238-probe.txt")
    verdict = (
        "VALID — the probe saw a widget it dropped on a worker thread"
        if _self_test_saw_the_worker
        else "INVALID — the positive control never ran, so a clean result here means nothing"
    )
    lines = [
        "T-238 criterion 4 — which thread drops the last Python reference to a QWidget",
        "",
        f"self-test:                   {verdict}",
        f"QWidget classes patched:     {len(_patched)}",
        f"widgets constructed:         {_constructed}",
        f"finalisations observed:      {sum(_BY_THREAD.values())}",
        "",
        "By thread:",
    ]
    for name, count in _BY_THREAD.most_common():
        marker = "" if name == "MainThread" else "   <-- NOT the main thread"
        lines.append(f"  {count:7d}  {name}{marker}")
    lines.append("")
    if _OFF_THREAD:
        lines.append("Off-main-thread finalisations — the segfault's precondition:")
        for what, count in _OFF_THREAD.most_common(40):
            lines.append(f"  {count:7d}  {what}")
    else:
        lines.append("No QWidget was finalised off the main thread.")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def demonstrate_the_gc_route() -> str:
    """Show that the precondition needs **no thread to hold a widget at all**.

    Run directly: `QT_QPA_PLATFORM=offscreen .venv/bin/python tools/t238_widget_thread_probe.py`

    This is the finding the zero result above pointed at. A survey of what the product's threads
    *hold* — `ResultPump`, the `ytdlp_service` and `thumbnails` pool tasks, the persistence writer
    — finds no `QWidget` anywhere, and that is not sufficient, because **Python's cyclic collector
    runs on whichever thread crosses the allocation threshold**. A widget reachable only from a
    reference cycle is therefore decref'd wherever `gc` happens to run, and both pools allocate.

    So "who holds a reference" is the wrong question for `T-238`'s criterion 4. The question is
    *who runs `gc`*, which is timing rather than ownership — and that is consistent with a fault
    seen once, on a machine that was also running other work, and never again in 60 clean runs.
    """
    import gc

    from PySide6.QtWidgets import QApplication, QListView

    if QApplication.instance() is None:
        QApplication([])
    seen: list[str] = []
    gc.disable()

    class _Node:
        pass

    def build_a_cycle_holding_a_widget() -> None:
        first, second = _Node(), _Node()
        first.other, second.other = second, first  # type: ignore[attr-defined]
        first.view = QListView()  # type: ignore[attr-defined]
        weakref.finalize(first.view, lambda: seen.append(threading.current_thread().name))  # type: ignore[attr-defined]

    build_a_cycle_holding_a_widget()
    worker = threading.Thread(target=gc.collect, name="t238-gc-demo-worker")
    worker.start()
    worker.join()
    gc.enable()
    return seen[0] if seen else "(nothing collected)"


if __name__ == "__main__":
    where = demonstrate_the_gc_route()
    print(f"the widget's last reference was dropped on: {where}")
    print(
        "No thread ever held it. If that name is not MainThread, the segfault's precondition is "
        "reachable by gc timing alone — see T-238 criterion 4."
    )
