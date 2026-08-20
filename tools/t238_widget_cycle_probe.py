"""Does any `QWidget` this application builds get freed by the cyclic collector? (`T-238` crit. 4)

**What this is for, and what it has so far refused to answer.** `T-238`'s criterion 4 has two named
next steps and this addresses the second: *establish whether any `QWidget` in this application
participates in a reference cycle.* **As of 2026-08-20 it has not answered it** — the surfaces stay
retained through teardown, so the run exits 3 rather than reporting; see the limits below before
reading any number this prints. The
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

**Scope, and it is an omission rather than a choice** (`T238-R5`). This covers what `compose()`
builds and what `open_add_dialog()`, `open_settings()` and `show_about()` open. The five screens
`tests/ui/conftest.py` additionally constructs — the format table, template editor, playlist picker,
options dialog and preset manager — **are reachable in the product**, from a staged row, and they
are not covered here. An earlier version of this docstring called that a deliberate scope on the
grounds that restating the list would be a second inventory (`T200-R3`); avoiding a second inventory
is a real constraint but it does not make the uncovered screens unreachable, and criterion 4 asks
about **any** application widget. **Whatever this reports is bounded to the surfaces below.**

**What this run cannot answer, stated here because the exit code alone is easy to skim past.**
When the surfaces are still standing at the end — which is what happens today — this refuses, and
the refusal is not a quiet result:

- **Retention is not the absence of cycles.** A still-reachable object graph may contain any number
  of them; being reachable is what stops the collector classifying it, not the absence of a cycle.
- **Equal aggregate counts do not establish identity.** `159` before and `159` after does not say
  they are the same 159 widgets, and `0` widgets among the parked garbage is a count rather than a
  statement about which widgets those were.
- **The post-callback `gc.collect()` in the `finally` below is not recorded.** It runs after the
  result has been read and after `DEBUG_SAVEALL` is lowered, so whatever it frees is invisible to
  this measurement.

**A run that answered criterion 4** would release or otherwise control the retention root, track
the identities of the widgets it is deciding about, observe what the collector does *after* that
release, and cover the criterion's whole application-widget scope. This does none of those.

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
            f"\nREFUSED. The surfaces are still standing — {before} widgets before the teardown "
            f"and {after} after — so no widget was freed by anything and the {len(freed)} above is "
            "not a result about cycles. It is also not a result about their absence: a retained "
            "graph is not classified by the collector at all, so it may contain any number of "
            f"cycles. The {collected} other objects say the collector ran in this window; they do "
            "not say which objects, and they do not cover the post-result collection in `finally`."
            "\n\nCriterion 4 is unanswered by this run. See the module docstring for what a run "
            "that answered it would have to do."
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
            f"\nNo widget this application builds turned up in the collector's garbage, and "
            f"{before - after} widgets were released. That is evidence about **these** surfaces "
            "and about the widgets this run tracked; it does not close the gc route for the "
            "application, which has screens this probe does not open. Read it with the module "
            "docstring's limits in hand."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
