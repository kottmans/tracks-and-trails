"""The Windows release build and its installer, cross-referenced (`T-319`, `T-322`).

**Neither can be *run* here.** An Inno Setup script is not executable on Linux and the release
spec's Windows branch is guarded by `sys.platform`, so `T-322` records in terms that *"nothing
here is verified"*. That is a real bound and this file does not pretend to close it — what it
closes is the other half, the one a Windows machine would not catch either: **every one of these
files repeats something declared elsewhere, and nothing fails when a copy drifts.**

The installer names the executable the spec builds. The spec puts ffmpeg where `bundled_ffmpeg`
looks for it. The fetch script pins a build whose family `LIC-001` constrains. Each of those is
two declarations that have to agree, which is the same class `test_appdir_metadata.py` covers for
the Linux AppDir.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

import pytest

REPOSITORY: Final = Path(__file__).resolve().parents[2]
SPEC: Final = REPOSITORY / "packaging" / "tracks-and-trails.spec"
INSTALLER: Final = REPOSITORY / "packaging" / "tracks-and-trails.iss"
FETCH: Final = REPOSITORY / "packaging" / "fetch_ffmpeg.py"


def fetch_module() -> ModuleType:
    """By path, as the other `packaging/` tools are loaded: it is not a package."""
    specification = importlib.util.spec_from_file_location("fetch_ffmpeg", FETCH)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


fetch = fetch_module()


def defined(name: str) -> str:
    """One `#define` from the installer script."""
    match = re.search(rf'^#define {name} "([^"]*)"$', INSTALLER.read_text(encoding="utf-8"), re.M)
    assert match is not None, f"the installer no longer defines {name}"
    return match.group(1)


def spec_text() -> str:
    return SPEC.read_text(encoding="utf-8")


# --- T-319: which ffmpeg, and why every part of the name matters -------------------------------


def test_the_ffmpeg_build_is_an_lgpl_shared_one() -> None:
    """`LIC-001` decides this, not convenience.

    A **GPL** ffmpeg may not be bundled with an MIT application at all — `gyan.dev`'s builds are
    GPL and are the easy thing to reach for. A **static** build is not *replaceable*, which the
    same requirement demands in the same sentence it demands dynamic linking for Qt.
    """
    assert "lgpl" in fetch.FFMPEG_ARCHIVE, "the pinned archive is not an LGPL build"
    assert "shared" in fetch.FFMPEG_ARCHIVE, (
        "the pinned archive is not a shared build, so ffmpeg would not be replaceable (LIC-001)"
    )
    assert "gpl-shared" not in fetch.FFMPEG_ARCHIVE.replace("lgpl-shared", ""), (
        "a GPL build cannot ship with an MIT application"
    )
    assert "gyan" not in fetch.FFMPEG_URL.lower(), "gyan.dev's builds are GPL (OPS-001, LIC-001)"
    assert "BtbN/FFmpeg-Builds" in fetch.FFMPEG_URL


def test_the_ffmpeg_pin_is_a_moment_rather_than_a_rolling_tag() -> None:
    """`latest` returns a different binary tomorrow, and a release has to be rebuildable."""
    assert fetch.FFMPEG_RELEASE.startswith("autobuild-"), fetch.FFMPEG_RELEASE
    assert fetch.FFMPEG_RELEASE not in {"latest", "autobuild-latest"}
    assert "latest" not in fetch.FFMPEG_ARCHIVE, (
        f"{fetch.FFMPEG_ARCHIVE} names a rolling build; the same URL will serve different bytes"
    )
    assert re.fullmatch(r"[0-9a-f]{64}", fetch.FFMPEG_SHA256), "the digest is not a SHA-256"
    # The URL must be built from the pinned pieces, not a literal that can drift away from them.
    assert fetch.FFMPEG_RELEASE in fetch.FFMPEG_URL
    assert fetch.FFMPEG_ARCHIVE in fetch.FFMPEG_URL


def test_ffprobe_is_fetched_and_ffplay_is_not() -> None:
    """**`ffprobe` is not optional and `ffplay` is 18 MB of dead weight.**

    yt-dlp's `FFmpegExtractAudioPP.run` calls `get_audio_codec`, which runs ffprobe on the
    downloaded file — so `REQ-010`'s audio extraction needs it. Nothing in this application
    launches a media player.
    """
    assert "ffprobe.exe" in fetch.WANTED_EXECUTABLES
    assert "ffmpeg.exe" in fetch.WANTED_EXECUTABLES
    assert "ffplay.exe" not in fetch.WANTED_EXECUTABLES


def test_the_licence_the_fetch_checks_is_the_one_the_gate_requires() -> None:
    """Two files naming the same obligation: `fetch_ffmpeg` keeps it honest, the gate keeps it
    present. If they named different paths, each would pass while the artifact shipped neither."""
    gates = (REPOSITORY / "packaging" / "artifact_gates.py").read_text(encoding="utf-8")
    required = re.search(r'^FFMPEG_LICENCE = "([^"]+)"$', gates, re.M)
    assert required is not None, "artifact_gates no longer names an ffmpeg licence file"
    assert fetch.LICENCE.name == required.group(1)
    assert fetch.LICENCE.is_file(), f"{fetch.LICENCE} is missing; LIC-001 requires it to ship"
    assert fetch.LICENCE.stat().st_size > 0


def test_the_licence_check_ignores_line_endings() -> None:
    """**The defect the first Windows run found.** `core.autocrlf=true` is the Windows default
    and `STARBASE` has it set, so the committed licence is checked out with CRLF while the
    archive's copy has LF. A byte-exact comparison failed at 7,816 bytes against 7,651 — exactly
    one extra byte per line — and would have failed on every Windows release build.

    The negative half is the point: a licence whose *content* differs is still rejected, so this
    tolerates the checkout's line endings and nothing else.
    """
    body = b"GNU LESSER GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n"
    assert fetch.same_licence(body.replace(b"\n", b"\r\n"), body)
    assert fetch.same_licence(body, body)
    assert not fetch.same_licence(body, b"GNU GENERAL PUBLIC LICENSE\nVersion 3\n"), (
        "a different licence must still be refused"
    )
    assert not fetch.same_licence(body, body + b"and one more clause\n")


def test_the_vendored_binaries_are_not_committed() -> None:
    """155 MB of third-party binary, reproducible from a pinned digest.

    The one half of `T-319`'s open question that was never in doubt.
    """
    ignored = (REPOSITORY / ".gitignore").read_text(encoding="utf-8")
    assert "packaging/vendor/" in ignored, "the fetched ffmpeg is not gitignored"


# --- T-319: the spec puts it where the application looks --------------------------------------


def test_the_spec_bundles_ffmpeg_beside_the_executable() -> None:
    """`bundled_ffmpeg()` reads `Path(sys.executable).parent / "ffmpeg.exe"`.

    So the spec has to place it there and not under `_internal/`, which is where `datas` would
    have put it. `binaries` with a destination of `"."` is the declaration that makes those two
    agree by construction.
    """
    text = spec_text()
    assert "ffmpeg_binaries" in text, "the spec no longer bundles ffmpeg"
    assert "binaries=ffmpeg_binaries" in text, "the ffmpeg list is built and then not passed"
    assert re.search(r'\(str\(path\), "\."\)', text), (
        'ffmpeg must land beside the executable ("."), which is where bundled_ffmpeg looks'
    )


def test_the_spec_refuses_to_build_a_release_without_ffmpeg() -> None:
    """A release that silently shipped without ffmpeg would lose audio extraction at runtime,
    on a user's machine, with no sign of it at build time."""
    text = spec_text()
    assert "raise SystemExit" in text, "a missing ffmpeg no longer stops the build"
    assert "fetch_ffmpeg.py" in text, "the failure does not name the fix"


def test_the_spec_does_not_fetch_anything_itself() -> None:
    """`OPS-012` §3: a self-hosted runner must not provision itself as a side effect of a build.

    So the spec reads what is on disk. The download is a separate, deliberate act — which is also
    what makes it reviewable.
    """
    text = spec_text()
    assert "urlopen" not in text and "urllib" not in text, "the spec now downloads during a build"
    assert "subprocess" not in text, "the spec now shells out during a build"


def test_ffmpeg_is_bundled_on_windows_only() -> None:
    """`OPS-001`: bundled on Windows, a system dependency on Linux — which is also why `REL-004`
    chose AppImage over a sandboxed format."""
    text = spec_text()
    branch = text[text.index("ffmpeg_binaries: list") : text.index("a = Analysis")]
    assert 'sys.platform == "win32"' in branch
    assert "RELEASE_BUILD" in branch, "the smoke build would bundle 155 MB it does not need"


# --- T-322: the installer names what the spec builds ------------------------------------------


def test_the_installer_launches_the_executable_the_spec_builds() -> None:
    """Two declarations of one filename. Nothing fails when they stop matching — the installer
    builds, installs, and leaves a shortcut to a file that is not there."""
    match = re.search(r'name="([^"]+)"', spec_text())
    assert match is not None, "the spec no longer declares an executable name"
    assert defined("AppExe") == f"{match.group(1)}.exe"


def test_the_installer_will_not_invent_a_version() -> None:
    """`REL-003` fixes the version in `__init__.py`. A default here would be a second opinion."""
    text = INSTALLER.read_text(encoding="utf-8")
    assert "#ifndef AppVersion" in text and "#error" in text, (
        "the installer no longer refuses to compile without /DAppVersion="
    )
    assert not re.search(r"^#define AppVersion ", text, re.M), (
        "the installer defines its own AppVersion, which can disagree with __init__.py"
    )


def test_the_installer_asks_for_no_administrator() -> None:
    """`NFR-004`: the application writes nothing beside itself, so a per-machine install would add
    an admin prompt on top of the SmartScreen warning `REL-005` already accepts. Two warnings
    before a first launch is how an install gets abandoned."""
    text = INSTALLER.read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in text
    assert "{autopf}" in text, "the install location is not the per-user one"


def test_the_desktop_shortcut_is_opt_in() -> None:
    """Scope named this default explicitly: the Start Menu entry always, the desktop icon only if
    asked for."""
    text = INSTALLER.read_text(encoding="utf-8")
    desktop = next(line for line in text.splitlines() if line.startswith('Name: "desktopicon"'))
    assert "Flags: unchecked" in desktop, "the desktop shortcut is pre-ticked"
    assert "{group}\\{#AppName}" in text, "there is no Start Menu shortcut"


def test_the_installer_ships_the_whole_one_dir_tree() -> None:
    """Including `licenses\\`, which `LIC-001` requires in *every distributed artifact* — and an
    installer that copied only the executable would satisfy no test but the user's."""
    text = INSTALLER.read_text(encoding="utf-8")
    assert 'Source: "{#SourceDir}\\*"' in text
    assert "recursesubdirs" in text, "subdirectories are not copied, so _internal/ is left behind"


def test_signing_is_a_line_to_edit_rather_than_a_line_to_write() -> None:
    """`REL-005` ships `0.1.0` unsigned with a certificate as the `1.0` condition. The difference
    between those two states should be uncommenting, not authoring."""
    text = INSTALLER.read_text(encoding="utf-8")
    assert "SignTool" in text, (
        "there is no signing line to uncomment when REL-005's condition is met"
    )
    signing = [line for line in text.splitlines() if "SignTool" in line and "=" in line]
    assert signing and all(line.lstrip().startswith(";") for line in signing), (
        "SignTool is active, but REL-005 ships 0.1.0 unsigned"
    )


@pytest.mark.parametrize("declaration", ["AppName", "AppExe", "AppPublisher", "AppUrl"])
def test_every_installer_define_is_non_empty(declaration: str) -> None:
    """The floor. An empty `#define` compiles and produces an installer with a blank name."""
    assert defined(declaration).strip()
