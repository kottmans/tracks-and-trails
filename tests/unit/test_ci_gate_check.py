"""TEMPORARY — verifies the CI gate can actually fail (T-006 acceptance criterion).

Deleted once both failure modes are confirmed red. Do not keep this file.
"""


def test_deliberate_failure_should_turn_ci_red() -> None:
    assert 1 == 2, "deliberate failure: CI must report this as red"
