"""`tools/windows/mutations/run_mutations.py`'s verdicts — what the table is allowed to call a kill.

The driver runs on a Windows desktop; the judgement of one pytest run is pure, and `T331-R1` found
it wrong in ways a Windows run would only show by accident. Each counterexample from that review is
here.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

DRIVER = (
    Path(__file__).resolve().parents[2] / "tools" / "windows" / "mutations" / "run_mutations.py"
)


@pytest.fixture(scope="module")
def driver() -> ModuleType:
    """Imported, which runs nothing: the checks and the cases are behind `main()` now."""
    specification = importlib.util.spec_from_file_location("run_mutations", DRIVER)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("expectation", "code", "summary", "broken", "expected"),
    [
        # The Windows run's real kills: assertion failures, with teardown errors cascading after.
        ("fail", 1, "8 failed, 31 passed, 4404 deselected, 11 errors in 83.06s", False, "KILLED"),
        # `T331-R1`: exit 1 with errors only is not a caught mutation.
        ("fail", 1, "39 passed, 4 errors in 80.0s", False, "NO RESULT (errors only)"),
        # `T331-R1`: exit 1 with no result line is not a caught mutation.
        ("fail", 1, "NO SUMMARY LINE — last output was: ....", False, "NO RESULT (no summary)"),
        ("fail", 0, "39 passed, 4404 deselected in 81.13s", False, "SURVIVED (unexpected)"),
        ("survives", 0, "39 passed in 80.0s", False, "SURVIVED (expected)"),
        ("survives", 1, "1 failed, 38 passed in 82.0s", False, "KILLED (unexpected)"),
        ("fail", 4, "ERROR: usage", False, "NO RESULT (exit 4)"),
        ("fail", 1, "2 failed, 37 passed", True, "NO RESULT (baseline broken)"),
        ("pass", 0, "39 passed, 4404 deselected in 84.84s", False, "OK"),
        ("pass", 1, "1 failed, 38 passed", False, "BROKEN BASELINE"),
        # `T331-R1`: a baseline exiting 2 to 5 was never marked broken.
        ("pass", 2, "(interrupted)", False, "NO RESULT (exit 2)"),
        ("pass", 5, "no tests ran in 0.01s", False, "NO RESULT (exit 5)"),
        ("pass", 0, "39 passed, 1 error in 80.0s", False, "BROKEN BASELINE"),
    ],
)
def test_a_verdict_follows_the_evidence_not_the_exit_code(
    driver: ModuleType, expectation: str, code: int, summary: str, broken: bool, expected: str
) -> None:
    assert driver.verdict(expectation, code, summary, broken) == expected


def test_any_baseline_that_is_not_ok_breaks_its_selection(driver: ModuleType) -> None:
    """The loop marks a selection broken for every non-OK baseline, exit 2 to 5 included."""
    source = DRIVER.read_text(encoding="utf-8")
    assert 'if expectation == "pass" and word != "OK":' in source
