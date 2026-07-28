"""What the machine running the suite can actually do (`T-070`).

Some tests need a privilege or an OS setting rather than a library. On Linux they are always
available and the question never comes up; on Windows they are not, and the answer differs
between a CI runner and a developer's desktop.

**This exists because the suite was silently assuming them.** Measured 2026-07-28 on a Windows
10 machine that is not a runner: the full suite failed 4 tests when run as an ordinary user and
0 of those 4 when run elevated. The failures were bare `OSError`s from `Path.symlink_to`, which
reads like a broken checkout rather than a machine without a privilege. GitHub's runners are
elevated, so CI could never have reported it.

A skip here is not the "retire a gate and replace it with theatre" failure `T-026` warns about:
these tests still run, and still gate, everywhere the capability exists — including CI. What
changes is that a machine lacking the capability says so instead of failing obscurely.

Kept in `tests/` rather than in a `conftest.py` because the suites are collected independently
and a `conftest.py` does not reach sideways; `tests/network/conftest.py` records the same
constraint from the other direction.
"""

import contextlib
from pathlib import Path

import pytest

#: Why a Windows machine may refuse to create a symlink, in the words a reader needs.
#:
#: Creating one needs `SeCreateSymbolicLinkPrivilege`, which an ordinary account does not hold.
#: Developer Mode grants an unprivileged equivalent; an elevated shell has it outright. CI runs
#: elevated, which is why this never surfaced there.
NO_SYMLINKS = (
    "this machine cannot create symlinks. On Windows that needs Administrator rights or "
    "Developer Mode (Settings > System > For developers), not a code change — see T-070. "
    "The test is unchanged and still gates on Linux and on CI, which runs elevated."
)


def can_create_symlinks(directory: Path) -> bool:
    """Whether a symlink can actually be created in `directory` — attempted, not inferred.

    `os.name`, an elevation check, or a Developer Mode registry read would each be a proxy for
    the real question, and each would be wrong in some configuration. Making one and removing
    it is the question itself.
    """
    probe = directory / "_symlink_capability_probe"
    try:
        probe.symlink_to(directory)
    except OSError, NotImplementedError:
        return False
    # Tidying up is not the question being asked; a link that cannot be removed still proves
    # that one could be created.
    with contextlib.suppress(OSError):
        probe.unlink()
    return True


@pytest.fixture
def symlinks(tmp_path: Path) -> None:
    """Skip with a reason a human can act on when this machine cannot create symlinks."""
    if not can_create_symlinks(tmp_path):
        pytest.skip(NO_SYMLINKS)
