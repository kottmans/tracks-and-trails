"""`packaging/windowed_checks.py`'s judgement, which is the part that can be wrong on any platform.

The console check and the probe runs need a Windows release build and run in CI; what they decide
from what they see is pure, and each way of being wrong is asserted here.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

TOOL = Path(__file__).resolve().parents[2] / "packaging" / "windowed_checks.py"


@pytest.fixture(scope="module")
def checks() -> ModuleType:
    pytest.importorskip("psutil")
    specification = importlib.util.spec_from_file_location("windowed_checks", TOOL)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules["windowed_checks"] = module
    specification.loader.exec_module(module)
    return module


def test_a_probe_that_wrote_no_report_fails_even_when_it_exits_zero(checks: ModuleType) -> None:
    """**The defect the file exists for**: a windowed build's `stdout` goes nowhere."""
    problem = checks.judge_probe(0, None, "database        ok")
    assert problem is not None and "no report" in problem


def test_a_report_without_the_success_line_fails(checks: ModuleType) -> None:
    assert checks.judge_probe(0, "database        (something else)\n", "database        ok")


def test_a_failing_exit_is_reported_with_the_probes_last_words(checks: ModuleType) -> None:
    problem = checks.judge_probe(1, "bundle x\nFAIL: no ffmpeg\n", "ffmpeg          ok")
    assert problem == "exited 1: FAIL: no ffmpeg"


def test_a_passing_probe_passes(checks: ModuleType) -> None:
    assert checks.judge_probe(0, "database        ok\n", "database        ok") is None


def test_every_probe_marker_is_a_line_the_probe_actually_says(checks: ModuleType) -> None:
    """The markers are copied from `_freeze_probe`; a reworded success line must fail here first."""
    source = (
        Path(__file__).resolve().parents[2] / "src/tracks_and_trails/_freeze_probe.py"
    ).read_text("utf-8")
    for flag, marker in checks.PROBES:
        assert marker in source, f"{flag}'s marker {marker!r} is not in _freeze_probe.py"
