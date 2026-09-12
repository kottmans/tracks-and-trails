"""The shell that builds and evidences the Linux artifact (`T-321`, `T-318`).

These scripts produce the thing a user installs, and their failure modes are **silent**: a build
that packs nothing and prints `done`, a clean-machine run that reports a pass because its probe
never ran. Both happened. Neither is a format a validator owns, so what is asserted here is the
same class as `test_appdir_metadata.py` — the cross-references and the invariants nothing else
would notice losing.

**Not a shell parser.** These read the scripts as text and assert properties a reviewer would
check by eye and then stop checking.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Final

import pytest

REPOSITORY: Final = Path(__file__).resolve().parents[2]
BUILD: Final = REPOSITORY / "packaging" / "build_appimage.sh"
EVIDENCE: Final = REPOSITORY / "tools" / "clean_machine_evidence.sh"
WRAPPER: Final = REPOSITORY / "tools" / "clean_machine_linux.sh"


def recorded_mode(relative: str) -> str:
    """The mode **git** records, not the filesystem's.

    `test_appdir_metadata.py` learned this the hard way: NTFS carries no POSIX execute bit, so
    `st_mode & 0o111` passes on Linux and cannot pass on a Windows checkout. The bit that reaches
    a user is the one the release build checks out, and that comes from the index.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-s", "--", relative],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )
    if listed.returncode != 0 or not listed.stdout.strip():
        pytest.skip("not a git checkout, so the recorded mode cannot be read")
    return listed.stdout.split()[0]


@pytest.mark.parametrize(
    "script",
    [
        "packaging/build_appimage.sh",
        "tools/clean_machine_evidence.sh",
        "tools/clean_machine_linux.sh",
    ],
)
def test_every_build_script_is_executable_in_the_index(script: str) -> None:
    """A script the documentation invokes by path has to be runnable by that path."""
    mode = recorded_mode(script)
    assert mode == "100755", f"git records {script} as {mode}, not an executable 100755"


@pytest.mark.parametrize("script", [BUILD, EVIDENCE, WRAPPER], ids=lambda path: path.name)
def test_every_build_script_parses(script: Path) -> None:
    """`bash -n`. A syntax error in these is found by a release, not by a test run."""
    checked = subprocess.run(
        ["bash", "-n", str(script)], capture_output=True, text=True, check=False
    )
    assert checked.returncode == 0, checked.stderr


# --- T321-R2: the documented command has to be the whole recipe -------------------------------


def test_appimagetool_is_pinned_by_version_and_verified_by_digest() -> None:
    """`T321-R2`: the build depended on a binary somebody had installed by hand.

    The script packed only `if [ -x /usr/local/bin/appimagetool ]`, and nothing put it there — so
    the documented `podman run` produced an AppDir while the task reported an AppImage. It fetches
    the tool now, which makes **how** it fetches it part of the artifact's provenance: an unpinned
    `continuous` download would make each build depend on whatever was published that morning.
    """
    text = BUILD.read_text(encoding="utf-8")

    version = re.search(r"^APPIMAGETOOL_VERSION=(\S+)$", text, re.M)
    assert version is not None, "the appimagetool version is not pinned in a variable"
    assert re.fullmatch(r"\d+\.\d+(\.\d+)?", version.group(1)), (
        f"{version.group(1)!r} is not a release version. 'continuous' or 'latest' would make "
        f"this build depend on whatever was published that morning"
    )

    digest = re.search(r"^APPIMAGETOOL_SHA256=([0-9a-f]{64})$", text, re.M)
    assert digest is not None, (
        "no SHA-256 for appimagetool. A build tool fetched over the network without a digest is "
        "a supply-chain hole in the one script whose output gets signed and shipped"
    )

    assert "sha256sum -c" in text, "the digest is declared and never checked"
    # The download must name the pinned variable, not a literal that drifts away from it.
    assert "$APPIMAGETOOL_VERSION/appimagetool" in text, (
        "the download URL does not use the pinned version variable, so the two can disagree"
    )


def test_the_build_cannot_succeed_without_packing() -> None:
    """The `else` branch that let a run produce an AppDir and print `done` is gone.

    That branch is why `T321-R2` survived a review: the build's own output said it had finished,
    and it had, for a value of finished that ships nothing.
    """
    text = BUILD.read_text(encoding="utf-8")
    assert "appimagetool absent" not in text, "the skip-packing branch is back"
    assert "leaving the AppDir for packing" not in text, "the skip-packing branch is back"


def test_the_build_asserts_the_platform_plugins_came_across() -> None:
    """The defect that shipped an artifact which could not open a window.

    PyInstaller's PySide6 hook logs `failed to obtain Qt library info` as a **warning** and
    carries on, producing a bundle with no platform plugins. It passes every probe, because none
    of them creates a `QApplication`.
    """
    text = BUILD.read_text(encoding="utf-8")
    assert "no Qt platform plugins in the bundle" in text, (
        "the build no longer checks that Qt's platform plugins were bundled"
    )


# --- T-318: a harness that cannot report a negative is not a harness --------------------------


def test_the_pre_install_check_can_fail_the_run() -> None:
    """`T-318`'s first criterion, and the reason it is first.

    Evidence taken on a machine that turns out to have had Python on it is not evidence. A
    pre-install check that only *prints* would let that through, so it has to count faults and
    the script has to exit on them.
    """
    text = EVIDENCE.read_text(encoding="utf-8")
    assert "PRESENT" in text, "the pre-install check no longer reports a tool it found"
    assert re.search(r"failures=\$\(\(failures \+ 1\)\)", text), (
        "nothing increments a failure count, so a PRESENT line cannot fail the run"
    )
    assert re.search(r'^exit "\$failures"$', text, re.M), (
        "the script does not exit on its failure count, so its verdict is decorative"
    )


@pytest.mark.parametrize("tool", ["python3", "pip3", "gcc", "ffmpeg", "qmake6", "yt-dlp"])
def test_the_pre_install_check_looks_for_the_tools_that_would_invalidate_it(tool: str) -> None:
    """`REQ-029` says no Python and no development toolchain; `OPS-001` bundles ffmpeg on
    Windows, so a clean machine with ffmpeg on `PATH` cannot tell bundled from borrowed."""
    assert tool in EVIDENCE.read_text(encoding="utf-8"), (
        f"the pre-install check does not probe for {tool}"
    )


def test_the_evidence_run_includes_a_real_download_and_a_real_launch() -> None:
    """`T321-R1`: the clean-machine evidence was a launch, four probes and the gates — and no
    real download, which is the one thing a clean machine is uniquely able to disprove.

    `--version` is checked for separately because it is **not** a launch test: it returns before
    a `QApplication` exists, which is how a build with no platform plugins passed everything.
    """
    text = EVIDENCE.read_text(encoding="utf-8")
    for flag in ("--spawn-probe", "--ytdlp-probe", "--database-probe", "--download-probe"):
        assert flag in text, f"the evidence run does not exercise {flag}"
    assert "QT_QPA_PLATFORM=offscreen" in text, "nothing in the run starts a real QApplication"


def test_the_clean_machine_is_not_the_machine_that_built_it() -> None:
    """The AppImage is built on Debian 12 so it reaches as far back as possible; testing it there
    would prove nothing about either end. The wrapper runs it on the oldest LTS the README
    claims."""
    wrapper = WRAPPER.read_text(encoding="utf-8")
    build = BUILD.read_text(encoding="utf-8")
    assert "ubuntu:24.04" in wrapper
    assert "bookworm" in build
    assert "bookworm" not in wrapper, "the clean machine is now the build image"
