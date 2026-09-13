"""The startup timestamp `NFR-002` is measured with (`T-325`).

**In `core/` because `ui/` calls it** — `test_layering.py` refused the first version, which put
this in the root `_freeze_probe` module and had `ui/main_window.py` import it. A window reaching
into the freeze-probe harness is the sideways dependency `ARCHITECTURE.md` §4 forbids.

**Not a stopwatch**, which is what `T-325` asks for: the application writes a wall clock when its
window reaches the screen, and `tools/startup_time.py` takes the other half before spawning. That
makes the *recording* side a small piece of code with three ways to be quietly wrong — writing
when nobody asked, writing more than once, or failing a launch because a measurement could not be
written — and each is asserted here.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from tracks_and_trails.core import startup


def test_nothing_is_written_when_nobody_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every ordinary launch takes this path, so it must cost one environment read and nothing."""
    monkeypatch.delenv(startup.STARTUP_REPORT_ENV, raising=False)
    startup.record_first_paint()
    assert list(tmp_path.iterdir()) == []


def test_the_timestamp_is_written_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**Once, because exposure fires again on every unminimize.**

    A file with five timestamps in it would not say which was the launch — and the window this
    rides is `T287-R1`'s exposure watch, which by design reports every time the compositor shows
    the surface.
    """
    marker = tmp_path / "first-paint.txt"
    monkeypatch.setenv(startup.STARTUP_REPORT_ENV, str(marker))

    before = time.time()
    startup.record_first_paint()
    after = time.time()

    first = marker.read_text(encoding="utf-8")
    label, _, stamp = first.strip().partition(" ")
    assert label == "first-paint"
    assert before <= float(stamp) <= after, "the timestamp is not this machine's wall clock"

    startup.record_first_paint()
    startup.record_first_paint()
    assert marker.read_text(encoding="utf-8") == first, "a later exposure overwrote the launch"


def test_a_measurement_that_cannot_be_written_does_not_fail_the_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T-319`'s rule for the probe report, followed here: the report is evidence, not the point.

    A directory where a file should be is the cheap way to make the write fail on every platform.
    """
    blocked = tmp_path / "first-paint.txt"
    blocked.mkdir()
    monkeypatch.setenv(startup.STARTUP_REPORT_ENV, str(blocked))
    startup.record_first_paint()  # must not raise


def test_the_window_records_it_through_the_exposure_watch() -> None:
    """**The wiring, asserted where it is easy to lose.**

    `showEvent` is the tempting hook and it is the wrong one: it fires before the window is on
    screen, and on Wayland the widget is never told about exposure at all (`T287-R1`). So the
    recorder rides `_the_window_is_on_screen`, and this fails if someone moves it.
    """
    source = (
        Path(__file__).resolve().parents[2] / "src" / "tracks_and_trails" / "ui" / "main_window.py"
    ).read_text(encoding="utf-8")
    handler = source.split("def _the_window_is_on_screen")[1].split("def _hide_the_dialogs")[0]
    assert "record_first_paint" in handler, (
        "the startup timestamp is no longer taken from the exposure watch, so it is measuring "
        "something other than the window reaching the screen"
    )


def load_startup_tool() -> Any:
    import importlib.util

    tool = Path(__file__).resolve().parents[2] / "tools" / "startup_time.py"
    specification = importlib.util.spec_from_file_location("startup_time_tool", tool)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("durations", "cold", "expected"),
    [
        ([6.0, 1.0, 1.0, 1.0, 1.0], True, 1),
        ([4.0, 9.0, 9.0, 9.0, 9.0], True, 0),
        ([6.0, 1.0, 1.0, 1.0, 1.0], False, 0),
        ([1.0, 6.0, 6.0, 6.0, 1.0], False, 1),
    ],
    ids=["cold-over-warm-under", "cold-under-warm-over", "warm-median-under", "warm-median-over"],
)
def test_the_cold_gate_judges_the_cold_launch_alone(
    monkeypatch: pytest.MonkeyPatch, durations: list[float], cold: bool, expected: int
) -> None:
    """**`T325-R1`.** Under `--cold` only the first launch is cold, so it alone meets the bound.

    The reviewer's counterexample is the first case: a 6-second cold start with four 1-second warm
    ones exited 0 against a 5-second bound, because the median of all five was 1 second. The
    measured durations are substituted; the real argument parsing, loop and verdict run.
    """
    tool = load_startup_tool()
    remaining = iter(durations)
    monkeypatch.setattr(tool, "one_launch", lambda command, environment: (next(remaining), None))
    arguments = ["fake-artifact", "--runs", str(len(durations)), "--bound", "5"]
    assert tool.main([*arguments, "--cold"] if cold else arguments) == expected
