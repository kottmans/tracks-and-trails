"""Reviewer regressions for the Qt-lifecycle test harness (`T-128`)."""

import gc
from collections.abc import Callable
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from tests import qt_lifecycle


def test_both_qt_suites_share_the_detector_that_they_assert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both conftests install the detector, but Qt keeps only the latest handler.

    The per-test assertion must therefore inspect the recorder owned by that latest handler.
    Otherwise a full run loads the integration and UI conftests, the second installation replaces
    the first, and every assertion keeps reading the now-detached first recorder.
    """
    handlers: list[Callable[[Any, Any, str], None]] = []
    previous_recorders = list(qt_lifecycle._orphaned)
    monkeypatch.setattr(
        qt_lifecycle,
        "qInstallMessageHandler",
        lambda handler: handlers.append(handler),
    )
    qt_lifecycle._orphaned.clear()
    try:
        qt_lifecycle.fail_on_orphaned_timers()
        qt_lifecycle.fail_on_orphaned_timers()

        handlers[-1](None, None, qt_lifecycle.CROSS_THREAD_TIMER)

        with pytest.raises(AssertionError, match="cross-thread timer removal"):
            qt_lifecycle.assert_no_orphaned_timers()
    finally:
        qt_lifecycle._orphaned[:] = previous_recorders


# --- T-289: the collectable-widget watch, and the two ways `T289-R2` got past it ---------------


def test_the_watch_restores_the_exact_debug_flags_it_found(qapp: QApplication) -> None:
    """`T289-R2`: a process that enters with `33` must leave with `33`, not `1`.

    The reviewed version had two owners for the flag — the watch and the inspection — and between
    them `DEBUG_SAVEALL | DEBUG_STATS` came out as `DEBUG_STATS` alone. A fixture that quietly
    turns off somebody else's diagnostic is worse than one that never touched it, because the
    diagnostic still looks armed.
    """
    previous = gc.get_debug()
    gc.set_debug(gc.DEBUG_SAVEALL | gc.DEBUG_STATS)
    try:
        entered = gc.get_debug()
        with qt_lifecycle.watch_for_collectable_widgets():
            assert gc.get_debug() & gc.DEBUG_SAVEALL, "the watch did not arm the parking"
            qt_lifecycle.widgets_the_collector_would_destroy(qapp)
        assert gc.get_debug() == entered, (
            f"the watch left the debug flags at {gc.get_debug()} having found {entered}"
        )
    finally:
        gc.set_debug(previous)
        gc.garbage.clear()


def test_the_inspection_refuses_to_run_with_the_parking_down(qapp: QApplication) -> None:
    """`T289-R2`: the inspection may not be called outside the watch, and says so.

    **The hole this closes is a gap rather than a call.** The reviewed fixture lowered the parking
    at the end of the test body and inspected afterwards; a collection in between released the
    evidence instead of parking it, and the unmarked violation passed. Making the inspection refuse
    when the flag is down means the gap cannot be reintroduced silently — it fails loudly at the
    first test instead.
    """
    previous = gc.get_debug()
    gc.set_debug(previous & ~gc.DEBUG_SAVEALL)
    try:
        with pytest.raises(AssertionError, match="DEBUG_SAVEALL down"):
            qt_lifecycle.widgets_the_collector_would_destroy(qapp)
    finally:
        gc.set_debug(previous)


def test_the_inspection_clears_what_it_parked(qapp: QApplication) -> None:
    """`T289-R2`: reading the parked list must also empty it, for every test.

    **The exempt node is why.** Skipping the *assertion* used to skip the *clear*, so `T-238`'s
    diagnostic left its widget parked in `gc.garbage` and the control test that asserts the
    boundary cleared it failed on garbage the fixture was holding. Clearing is the boundary's job
    and the verdict is the caller's, which is why they are two calls now.
    """

    class _Leaked(QWidget):
        """Python-defined, so its collection would run the destructor in place."""

    class _Cycle:
        def __init__(self, widget: QWidget) -> None:
            self.widget = widget
            self.myself = self

    with qt_lifecycle.watch_for_collectable_widgets():
        _Cycle(_Leaked())
        dangerous = qt_lifecycle.widgets_the_collector_would_destroy(qapp)
        still_parked = list(gc.garbage)

    # **Cleaned up by collecting for real, which needs the parking down.** This test runs *inside*
    # the fixture's own watch, so every collection here parks instead of freeing and the cycle would
    # be garbage again at teardown — where the boundary guard would fail this test for producing
    # exactly the state it exists to catch. Lowering the flag around one collection releases the
    # widget on this thread, which is the safe thread, and the flag goes straight back.
    parked = gc.get_debug()
    gc.set_debug(parked & ~gc.DEBUG_SAVEALL)
    try:
        gc.collect()
    finally:
        gc.set_debug(parked)

    assert dangerous, "the helper did not see a widget built to be seen"
    assert still_parked == [], (
        f"{len(still_parked)} object(s) were left parked, so the next test inherits them and the "
        "drain cannot release them"
    )
