"""Does any `QWidget` this application builds get freed by the cyclic collector? (`T-238` crit. 4)

**What this answers.** `T-238`'s criterion 4 has two named next steps and this is the second:
*establish whether any `QWidget` in this application participates in a reference cycle.* The
`t238_widget_thread_probe` sibling established that the segfault's precondition needs **no thread
to hold a widget at all** — Python's cyclic collector runs on whichever thread crosses the
allocation threshold, so a widget freed by `gc` is decref'd wherever `gc` happens to run. That made
ownership the wrong question and left this one: does the product ever put a widget on that route?

**So the predicate is "freed by the cyclic collector", not "in a cycle".** They are not the same
and the difference decides the answer. A widget held *by* a cycle is not itself in one — its own
strongly-connected component has size one — yet it is still freed by `gc` rather than by refcount,
and it is still decref'd on whatever thread collected. Measuring cycle *membership* would answer a
neighbouring question and miss exactly the shape `demonstrate_the_gc_route()` demonstrates. What is
measured here is the thing the mechanism needs: **the collector, not the refcount, was what freed
it.**

**How.** `gc.DEBUG_SAVEALL` parks everything the collector frees in `gc.garbage` instead of
releasing it, so the collector's own verdict is readable. The application is composed, driven
through **its own routes**, and then torn down through the lifecycle it owns; whatever `QWidget`
turns up in `gc.garbage` after that was freed by the collector.

**Scope: the surfaces the application opens, which is a choice and not an omission.**
`open_add_dialog()`, `open_settings()` and `show_about()` are routes a user takes. The five screens
`tests/ui/conftest.py` additionally *constructs* — the format table, template editor, playlist
picker, options dialog and preset manager — are built there so an accessibility sweep can walk a
realised widget; they are reached in the product from a staged row. **This probe deliberately does
not restate that list.** `T200-R3` was reopened twice on two inventories of screens drifting apart,
and a second copy here would be a third. What this measures is what `compose()` builds and what the
window's own routes open.

**Usage** — a script, not a plugin:

    QT_QPA_PLATFORM=offscreen .venv/bin/python tools/t238_widget_cycle_probe.py

`ai/evidence/README.md`'s rule keeps the instrument here and the number in `T-238`: re-running
produces the report again.

## The self-test runs first and runs in both directions

Its sibling probe shipped two defects that each made it report confidently about nothing. **One of
them was a clean-looking zero** — no off-thread finalisation over the whole UI suite, because the
patch it relied on never ran; the other counted a single widget five times. *(Its own docstring
calls both "clean", which is true of the first and generous to the second — the over-count was found
by a run taking three times as long, not by reading the output.)* A "no widget takes the gc route"
answer here is worth nothing unless the same run shows the probe (1) *sees* a widget that is on that
route and (2) does *not* flag one that is not. One direction alone leaves "reports everything" and
"reports nothing" indistinguishable from a correct instrument.
"""

from __future__ import annotations

import gc
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from PySide6.QtWidgets import QApplication, QListView, QWidget


def _widgets_the_collector_freed(collect: Any) -> tuple[list[str], int]:
    """Run `collect()` with `DEBUG_SAVEALL` armed and name every `QWidget` the collector freed.

    Returns the widget names **and the total object count**, because "no widget was collected" and
    "nothing was collected" are different findings and only the second says the collector had
    nothing to do. Quoting the total from anywhere but this function is how it gets quoted from a
    diagnostic that was holding the objects it was counting.

    `gc.garbage` is cleared and the debug flag lowered before returning, so the caller is left with
    an ordinary interpreter. Only `type(...).__name__` is read off the parked objects: their C++
    halves may already be gone, and asking a dead wrapper anything else is how a probe turns a
    measurement into a crash.
    """
    gc.collect()
    gc.set_debug(gc.DEBUG_SAVEALL)
    try:
        collect()
        found = [type(obj).__name__ for obj in gc.garbage if isinstance(obj, QWidget)]
        total = len(gc.garbage)
    finally:
        gc.garbage.clear()
        gc.set_debug(0)
        gc.collect()
    return found, total


def _self_test() -> tuple[bool, bool, list[str]]:
    """Both directions, in this process, before the measurement is believed.

    Positive: a widget reachable **only** from a reference cycle. Nothing holds it directly, so no
    refcount reaching zero can free it and the collector must be what does — this is the route
    `demonstrate_the_gc_route()` showed is reachable, built here so the probe has to see it.

    Negative: a widget held by an ordinary local reference that is then dropped. Its refcount
    reaches zero at the `del`, the collector never touches it, and a probe that names it anyway is
    reporting the wrong thing about every result underneath.
    """
    notes: list[str] = []

    class _Node:
        """Two of these referring to each other is the cycle; the widget hangs off one."""

    def build_a_cycle_holding_a_widget() -> None:
        first, second = _Node(), _Node()
        first.other, second.other = second, first  # type: ignore[attr-defined]
        first.view = QListView()  # type: ignore[attr-defined]

    saw_the_positive = (
        "QListView"
        in _widgets_the_collector_freed(lambda: (build_a_cycle_holding_a_widget(), gc.collect()))[0]
    )
    notes.append(
        "positive: a widget reachable only from a cycle was "
        + ("seen" if saw_the_positive else "MISSED — this probe cannot see its own subject")
    )

    def build_and_drop_an_uncycled_widget() -> None:
        view = QListView()
        del view

    flagged_the_negative = (
        "QListView"
        in _widgets_the_collector_freed(
            lambda: (build_and_drop_an_uncycled_widget(), gc.collect())
        )[0]
    )
    notes.append(
        "negative: a widget freed by refcount was "
        + ("correctly not named" if not flagged_the_negative else "NAMED — this probe over-reports")
    )
    return saw_the_positive, not flagged_the_negative, notes


def measure_the_application() -> tuple[list[str], int, int, int]:
    """Compose the application, drive its own routes, tear it down, and read the collector.

    The teardown is `composition.shutdown.begin()` — the route the application takes when a user
    closes the window — rather than dropping references and hoping. Closing the window alone leaves
    the queue writer and the database open, and a probe that leaks its subject measures a different
    application from the one that ships.

    **The widget counts either side are the control, and without them the headline number is not
    readable.** *Nothing was freed by the collector* and *nothing was freed at all* produce the
    same zero, and they are opposite answers: the first says every widget reached refcount zero on
    the thread that dropped it, the second says the surfaces are still standing and the measurement
    never had a subject. Returned rather than asserted, because a leak is a finding about the
    application and not a fault in the probe.
    """
    from tracks_and_trails import app as application
    from tracks_and_trails.downloader.ytdlp_service import YtdlpService

    class _QuietYtdlp(YtdlpService):
        """Answers nothing and spawns nothing — `open_settings()` calls `refresh()` (`T200-R6`)."""

        def __init__(self) -> None:
            super().__init__(directory=Path("/nonexistent-in-probes"))

        def refresh(self) -> None: ...

    app = QApplication.instance()
    assert isinstance(app, QApplication), "main() constructs the QApplication before it gets here"
    counted: dict[str, int] = {}

    with TemporaryDirectory() as raw:
        tmp = Path(raw)

        def compose_open_and_shut() -> None:
            composition = application.compose(
                app,
                database=tmp / "queue.sqlite3",
                output_directory=tmp / "downloads",
                geometry_file=tmp / "window.toml",
                settings_file=tmp / "settings.toml",
                cache_directory=tmp / "cache",
                entry_point=lambda *_a, **_k: None,
                ytdlp_service=_QuietYtdlp(),
            )
            window = composition.window
            window.show()
            app.processEvents()

            # The application's own routes, and nothing constructed beside them — see the module
            # docstring on why the five constructed screens are not restated here.
            window.open_add_dialog()
            app.processEvents()
            settings = window.open_settings()
            assert settings is not None, (
                "composition wired no settings writers, so the Settings screen never opened and "
                "this measurement would silently cover one surface fewer"
            )
            app.processEvents()
            window.show_about()
            app.processEvents()
            counted["before"] = len(QApplication.allWidgets())

            window.close()
            composition.shutdown.begin()
            for _ in range(4000):
                if composition.shutdown.finished:
                    break
                app.processEvents()
            assert composition.shutdown.finished, "composition never finished shutting down"
            app.processEvents()

        freed, collected = _widgets_the_collector_freed(compose_open_and_shut)
        # Read after the helper's final `gc.collect()`, so deferred deletions and the collector
        # have both had their turn and this is the settled count rather than a mid-teardown one.
        app.processEvents()
        counted["after"] = len(QApplication.allWidgets())
        return freed, collected, counted.get("before", -1), counted["after"]


def main() -> int:
    # **Before the self-test, because the self-test builds widgets.** Qt aborts the process on a
    # `QWidget` constructed with no `QApplication`, and the first version of this file did exactly
    # that — it died before printing a line, which is at least a loud failure rather than a quiet
    # zero.
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)

    positive, negative, notes = _self_test()
    print("T-238 criterion 4 — which widgets the cyclic collector frees\n")
    for note in notes:
        print(f"  self-test {note}")
    if not (positive and negative):
        print("\nSELF-TEST FAILED. The measurement below is not evidence of anything.")
        return 2

    freed, collected, before, after = measure_the_application()
    print(f"\n  live QWidgets with every surface open:     {before}")
    print(f"  live QWidgets after shutdown:             {after}")
    print(f"  objects freed by the collector:            {collected}")
    print(f"  QWidget subclasses freed by the collector: {len(freed)}")
    if after >= before:
        print(
            f"\nThe surfaces are still standing — {before} widgets before the teardown and {after} "
            f"after — so no widget was freed by anything, and the {len(freed)} above is not a "
            "result about cycles. The collector was not idle while that happened: it "
            f"freed {collected} other objects in the same window, so this is the teardown "
            "releasing no widget rather than the collector never running."
        )
        return 3
    if freed:
        from collections import Counter

        for name, count in Counter(freed).most_common():
            print(f"    {count:5d}  {name}")
        print(
            "\nAt least one widget this application builds is freed by gc rather than by "
            "refcount, so the gc route is product-reachable and criterion 4's product branch "
            "is the live one."
        )
    else:
        print(
            f"\nNo widget this application builds was freed by the collector, and {before - after} "
            "of them were freed: each reached refcount zero on the thread that dropped it. On "
            "this evidence the gc route is not product-reachable through these surfaces."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
