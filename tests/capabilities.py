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
import shutil
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


#: Why a machine may not be able to run the conversion tests, in words that name the fix.
#:
#: CI installs ffmpeg on both platforms (`T-062`), and the application requires it for any preset
#: that converts or merges — so this is a developer-machine gap rather than a product one. Naming
#: the tool matters: without it these fail somewhere inside yt-dlp's postprocessor with a message
#: about a missing executable, which reads as a broken checkout.
NO_FFMPEG = (
    "this machine has no ffmpeg/ffprobe on PATH. The conversion tests need it to build their "
    "source media and to inspect what came out — see T-077. CI installs it (T-062); locally, "
    "install ffmpeg or accept that preset conversion is unverified here."
)


def ffmpeg_tools() -> tuple[str, str] | None:
    """Paths to `ffmpeg` and `ffprobe`, or `None` if either is missing.

    Both, not just `ffmpeg`: the tests convert *and* inspect, and a machine with one and not the
    other would fail at the assertion rather than at the skip.
    """
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        return None
    return ffmpeg, ffprobe


@pytest.fixture
def ffmpeg() -> tuple[str, str]:
    """`(ffmpeg, ffprobe)` paths, skipping with a reason a human can act on."""
    tools = ffmpeg_tools()
    if tools is None:
        pytest.skip(NO_FFMPEG)
    return tools
