"""`tools/orphan_scan.py` — the detection half of `T-258`.

**The known positive runs first, and it is the point of this file.** `T-238`'s widget probe
reported a clean zero twice while measuring nothing, and `ai/TESTING.md` names that shape
directly: an instrument that reports confidently about nothing is worse than no instrument,
because its silence is read as an answer. This scanner's whole output on a healthy machine is
"none found", so nothing else it says means anything until it has been shown one.

It earned that caution immediately. The first rule here was *the parent pid is 1*, and the
known-positive below reparented to `systemd` at pid 2105 instead — so the scanner reported
"no orphaned workers found" against a live, deliberately-made orphan.
"""

from __future__ import annotations

import contextlib
import importlib.util
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import psutil
import pytest

#: Loaded by path, as `tests/unit/test_commit_message_check.py` loads its own tool: this is
#: developer tooling rather than product code, so it does not belong under `src/`, and `tools/`
#: is not a package.
TOOL = Path(__file__).resolve().parents[2] / "tools" / "orphan_scan.py"


def load() -> ModuleType:
    specification = importlib.util.spec_from_file_location("orphan_scan", TOOL)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


orphan_scan = load()

#: A process that looks exactly like a spawned worker to anything reading command lines.
#:
#: The markers are in a comment rather than a real `multiprocessing` bootstrap because what is
#: under test is the *recognition and parent* rules, and a real spawned child cannot be made to
#: outlive its parent on POSIX — which is `T-258`'s whole finding and is measured in
#: `test_killing_the_parent_before_the_worker_is_prepared_leaves_nothing`.
_LOOKS_LIKE_A_WORKER = "import time\ntime.sleep(120)  # spawn_main --multiprocessing-fork\n"


@pytest.fixture
def a_real_orphan() -> Iterator[psutil.Process]:
    """A live process with a worker's command line whose parent has exited."""
    launcher = (
        "import subprocess, sys\n"
        f"child = subprocess.Popen([sys.executable, '-c', {_LOOKS_LIKE_A_WORKER!r}])\n"
        "print(child.pid, flush=True)\n"
    )
    intermediate = subprocess.Popen(
        [sys.executable, "-c", launcher], stdout=subprocess.PIPE, text=True
    )
    assert intermediate.stdout is not None
    orphan = psutil.Process(int(intermediate.stdout.readline().strip()))
    intermediate.wait(timeout=30)
    if sys.platform != "win32":
        # POSIX reparents on the intermediate's exit rather than on its last write, and the
        # scanner cannot see an orphan until it has. **Windows does not reparent at all** — the
        # parent pid simply stops resolving — so waiting for the ppid to change there would spin
        # for the whole deadline on every test that uses this fixture and then proceed anyway.
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and orphan.ppid() == intermediate.pid:
            time.sleep(0.05)
    try:
        yield orphan
    finally:
        with contextlib.suppress(psutil.NoSuchProcess):
            orphan.kill()


def test_the_scanner_sees_a_known_orphan(a_real_orphan: psutil.Process) -> None:
    """Before "none found" can mean anything, one must be found."""
    found = orphan_scan.find_orphans(minimum_age_seconds=0)

    assert a_real_orphan.pid in {orphan.pid for orphan in found}, (
        f"the scanner did not see a deliberately orphaned worker at pid {a_real_orphan.pid}, "
        f"reparented to pid {a_real_orphan.ppid()}. Everything else this tool reports is a "
        "silence that would read the same way."
    )


def test_a_worker_whose_parent_is_alive_is_not_reported() -> None:
    """The other half: a healthy worker under a live application is not a find.

    Without this the scanner could pass the test above by reporting every `spawn_main` process
    on the machine, which on a CI runner mid-suite is all of them.
    """
    child = subprocess.Popen([sys.executable, "-c", _LOOKS_LIKE_A_WORKER])
    try:
        time.sleep(0.2)
        found = orphan_scan.find_orphans(minimum_age_seconds=0)
        assert child.pid not in {orphan.pid for orphan in found}, (
            "a worker whose parent is this very process was reported as an orphan"
        )
    finally:
        child.kill()
        child.wait(timeout=30)


def test_a_young_orphan_is_not_reported(a_real_orphan: psutil.Process) -> None:
    """The age guard, against the same orphan the first test finds.

    A worker whose parent is still inside `Process.start()` is momentarily parentless-looking,
    and reporting it would make the tool cry wolf on every spawn. Asserted against a process
    that *is* an orphan, so this cannot pass by the scanner simply finding nothing.
    """
    found = orphan_scan.find_orphans(minimum_age_seconds=3600)

    assert a_real_orphan.pid not in {orphan.pid for orphan in found}, (
        "a seconds-old process was reported under a one-hour minimum age"
    )


def test_the_exit_code_reports_a_find(a_real_orphan: psutil.Process) -> None:
    """Non-zero on a find is what lets a scheduled run fail the machine rather than a build."""
    assert orphan_scan.main(["--minimum-age-seconds", "0"]) == 1


def test_the_exit_code_is_clean_when_nothing_is_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half of the exit-code contract, and it must not ask the machine.

    The obvious way to write this is to raise the minimum age until nothing qualifies and assert
    `0`. That asserts **the machine has no old orphans**, which on the one machine this tool is
    for — `STARBASE`, where five sat for twelve days — is exactly the thing that might be false.
    It would then fail as a true positive dressed as a broken test, in a suite where the finding
    would be read as noise.
    """
    monkeypatch.setattr(orphan_scan, "find_orphans", lambda *_, **__: [])

    assert orphan_scan.main([]) == 0
