"""Reviewer regressions for the Qt-lifecycle test harness (`T-128`)."""

from collections.abc import Callable
from typing import Any

import pytest

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
