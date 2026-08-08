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
import os
import shutil
from collections.abc import Mapping
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
#: The application requires ffmpeg for any preset that converts or merges, so on a developer's
#: machine this is a local gap rather than a product one. Naming the tool matters: without it these
#: fail somewhere inside yt-dlp's postprocessor with a message about a missing executable, which
#: reads as a broken checkout.
#:
#: **Which runners install it and which merely require it** (`T-189`). This used to say "CI installs
#: it (T-062)" flatly, and that stopped being true when the Windows gate moved to a self-hosted
#: machine:
#:
#: | Runner | ffmpeg |
#: |---|---|
#: | Hosted Linux (`check`) | **installed** by the workflow, `apt-get` |
#: | Hosted Windows (`check`) | **installed** by the workflow, `choco` |
#: | Self-hosted Windows (`windows-desktop`) | **required, not installed** — recorded only |
#:
#: `OPS-005` is why the last row cannot simply install: the maintainer's own machine is the runner,
#: and a test run does not get to mutate software on it.
NO_FFMPEG = (
    "this machine has no ffmpeg/ffprobe on PATH. The conversion tests need it to build their "
    "source media and to inspect what came out — see T-077. Install ffmpeg, or accept that "
    "preset conversion is unverified here."
)

#: Set by the CI jobs that own `T-108`'s cross-platform merge proof, so a missing tool **fails**
#: rather than skipping (`T-189`).
#:
#: **The defect this closes is a green run that proved nothing.**
#: `test_a_chosen_video_and_audio_pair_produce_one_merged_file` is exit criterion 2's evidence on
#: both platforms, and it takes the ordinary `ffmpeg` fixture below — which skips. The self-hosted
#: Windows runner *records* ffmpeg rather than installing it, so the day that machine loses the
#: tool, the required proof becomes a `SKIPPED` line inside a passing job and the criterion is
#: silently unevidenced. Nothing would have gone red.
#:
#: **An opt-in variable rather than a hostname or a `CI` check.** `CI` is set on every runner
#: including ones that legitimately have no ffmpeg, and detecting the self-hosted machine by name
#: would put the runner's identity in the test suite. The workflow states which jobs carry the
#: proof; this reads that statement.
#:
#: **It does not install anything.** `T-189`'s scope is explicit that a test run must not provision
#: software on `STARBASE` — the gate fails with the missing capability and the maintainer restores
#: it deliberately.
REQUIRE_FFMPEG_VAR = "TRACKSANDTRAILS_REQUIRE_FFMPEG"

#: Why a *required* run refuses, as opposed to why a developer's run skips. Names the variable, so
#: whoever meets this can tell a provisioning failure from a test that should not have been asked.
FFMPEG_REQUIRED_BUT_MISSING = (
    "ffmpeg/ffprobe are absent and this run requires them: {var} is set, which the CI jobs "
    "carrying T-108's cross-platform merge proof do. This is a provisioning failure on the "
    "runner, not a test defect — the required end-to-end case must not become a green skip "
    "(T-189). Restore ffmpeg on the runner; nothing here installs it (OPS-005)."
)


def ffmpeg_is_required(environment: Mapping[str, str] | None = None) -> bool:
    """Whether a missing ffmpeg must fail this run rather than skip it.

    Reads the environment at call time rather than at import, so a test can set the variable and
    observe the change — which is what makes `T-189`'s "a deterministic probe makes the gate fail"
    criterion assertable rather than a claim about CI nobody can run locally.

    Any non-empty value that is not a recognised negative counts as set: a workflow writing `1`,
    `true` or `yes` all mean the same thing, and a variable someone exported as `0` to turn this
    *off* should not silently turn it on.
    """
    source = os.environ if environment is None else environment
    value = source.get(REQUIRE_FFMPEG_VAR, "").strip().lower()
    return value not in ("", "0", "false", "no", "off")


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


def resolve_ffmpeg() -> tuple[str, str]:
    """`(ffmpeg, ffprobe)`, or raise the outcome this run has earned. **Skip or fail** (`T-189`).

    The helpful local skip is deliberately kept: a developer without ffmpeg gets an actionable
    reason and a suite that still runs, which is what `T-070` built this module for. What changes is
    that the CI jobs carrying `T-108`'s cross-platform merge proof set `REQUIRE_FFMPEG_VAR`, and
    there an absent tool is a **failure** — because the alternative is a required end-to-end case
    quietly becoming `SKIPPED` inside a green job, leaving exit criterion 2 evidenced by nothing.

    **A function rather than only a fixture body, so the decision can be probed.** `T-189`'s fourth
    criterion asks for a deterministic probe that hides a tool and makes the gate fail; a fixture
    can only be exercised by the tests that request it, and every one of those runs where ffmpeg is
    *present*. `tests/unit/test_capabilities.py` calls this with `PATH` emptied instead, which asks
    `shutil.which` the same question the runner will.

    `pytrace=False` on the failure: the traceback would point into this module, and the reader needs
    to be looking at the runner rather than at the suite.
    """
    tools = ffmpeg_tools()
    if tools is None:
        if ffmpeg_is_required():
            pytest.fail(FFMPEG_REQUIRED_BUT_MISSING.format(var=REQUIRE_FFMPEG_VAR), pytrace=False)
        pytest.skip(NO_FFMPEG)
    return tools


@pytest.fixture
def ffmpeg() -> tuple[str, str]:
    """`(ffmpeg, ffprobe)` paths. See `resolve_ffmpeg` for which runs skip and which fail."""
    return resolve_ffmpeg()
