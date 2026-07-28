"""POSITIVE CONTROL, not a real mutation.

Makes `still_running` always answer "nothing alive". The test MUST fail on its very first
assertion ("a running process was reported dead"). If this survives, the patching mechanism is
broken and no verdict from the sibling plugins means anything.

This is the check the earlier driver lacked: it could not tell a mutation that survived from a
mutation that was never applied.
"""


def _always_dead(pids):
    return []


def pytest_runtest_setup(item):
    module = getattr(item, "module", None)
    if module is not None and hasattr(module, "still_running"):
        module.still_running = _always_dead
