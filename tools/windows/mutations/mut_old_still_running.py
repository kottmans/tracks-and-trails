"""T-056's mutation: put `still_running` back to the pre-correction, presence-based form.

The corrected helper asks whether a process has *ended* (`wait(timeout=0)`). This is what it
replaced: ask `status()` and call anything that is not a zombie alive. Windows has no zombie
state, so a terminated process with a handle still open answers "running" — which is what
`windows-latest` produced once in run `30323328299`.

Patched on the already-imported test module rather than by editing the file, so the checkout is
never touched.
"""

import psutil


def _presence_based(pids):
    alive = []
    for pid in pids:
        try:
            process = psutil.Process(pid)
            if process.status() != psutil.STATUS_ZOMBIE:
                alive.append(pid)
        except psutil.NoSuchProcess:
            continue
    return alive


def pytest_runtest_setup(item):
    module = getattr(item, "module", None)
    if module is not None and hasattr(module, "still_running"):
        module.still_running = _presence_based
