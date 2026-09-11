"""The AppDir's metadata says the same thing as the build that fills it (`T-321`).

`REL-004` chose AppImage, and an AppDir is three small files plus a tree: `AppRun`, a `.desktop`
entry and an AppStream `metainfo.xml`. **Every one of them repeats something declared elsewhere** —
the binary's name from the PyInstaller spec, the licence from `pyproject.toml`, the component id
from the desktop file's own name — and nothing fails when a copy stops matching. The artifact
still builds. It launches on the build host. The launcher shows a filename instead of a name, or
the desktop entry points at a binary that is not there, and the first person to find out is a user.

**What this does not do is validate the formats.** `desktop-file-validate` and `appstreamcli
validate` do that, they are run in `T-321`'s documented build, and they are not reimplemented here:
a hand-rolled parser asserting a spec it half understands is worse than the tool that owns it.
This file asserts only the cross-references those tools cannot know about.
"""

from __future__ import annotations

import re
import subprocess
import tomllib
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Final

import pytest

REPOSITORY: Final = Path(__file__).resolve().parents[2]
APPDIR: Final = REPOSITORY / "packaging" / "appdir"

#: The reverse-DNS id the desktop entry, the metainfo and the icon all have to agree on.
COMPONENT_ID: Final = "io.github.kottmans.TracksAndTrails"

DESKTOP_FILE: Final = APPDIR / f"{COMPONENT_ID}.desktop"
METAINFO_FILE: Final = APPDIR / f"{COMPONENT_ID}.metainfo.xml"
APPRUN: Final = APPDIR / "AppRun"
SPEC: Final = REPOSITORY / "packaging" / "tracks-and-trails.spec"


def desktop_entries() -> dict[str, str]:
    """The `[Desktop Entry]` group as a mapping. Enough for a cross-reference, not a parser."""
    entries: dict[str, str] = {}
    for line in DESKTOP_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("[") or not line.strip() or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        entries[key.strip()] = value.strip()
    return entries


def binary_name() -> str:
    """What the PyInstaller spec names the executable — the one declaration of it."""
    match = re.search(r'name="([^"]+)"', SPEC.read_text(encoding="utf-8"))
    assert match is not None, "the spec no longer declares an executable name"
    return match.group(1)


def test_the_three_appdir_files_exist() -> None:
    """The floor. Every assertion below is vacuous against a missing file."""
    assert DESKTOP_FILE.is_file()
    assert METAINFO_FILE.is_file()
    assert APPRUN.is_file()


def test_apprun_is_executable_in_the_index() -> None:
    """An AppDir whose `AppRun` is not executable does not start, and nothing else notices.

    **Asked of git, not of the filesystem**, and that is the whole of this test's history. The
    first version read `Path.stat().st_mode & 0o111`, which passes on Linux and **cannot** pass on
    Windows: NTFS carries no POSIX execute bit, so a Windows checkout reports `0o100666` for a
    file git has recorded as `100755`. It failed the Windows job while passing every local run.

    Git's index is also the more faithful question. The bit that reaches a user is the one the
    release build checks out, and that comes from the index whatever platform the build ran on.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-s", "--", "packaging/appdir/AppRun"],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )
    if listed.returncode != 0 or not listed.stdout.strip():
        pytest.skip("not a git checkout, so the recorded mode cannot be read")
    mode = listed.stdout.split()[0]
    assert mode == "100755", f"git records AppRun as {mode}, not an executable 100755"


def test_the_desktop_entry_launches_the_binary_the_spec_builds() -> None:
    """`Exec` and the PyInstaller `name=` are the same string, declared twice.

    Rename the executable in the spec and the desktop entry still points at the old one: the
    AppImage builds, installs, and its launcher entry does nothing at all.
    """
    executable = desktop_entries()["Exec"].split()[0]
    assert executable == binary_name(), (
        f"the desktop entry launches {executable!r} and the spec builds {binary_name()!r}"
    )


def test_apprun_execs_the_same_binary() -> None:
    """The third copy of that name, and the one that actually runs."""
    assert f"/usr/bin/{binary_name()}" in APPRUN.read_text(encoding="utf-8")


def test_apprun_extends_the_path_rather_than_replacing_it() -> None:
    """**`OPS-001` makes ffmpeg a system dependency on Linux**, and `REQ-024` finds it on `PATH`.

    An `AppRun` that set `PATH` instead of prepending to it would hide the host's ffmpeg, breaking
    merged formats on every machine that has it installed — which is the exact failure `REL-004`
    rejected Flatpak for. It would also pass every other check here.
    """
    text = APPRUN.read_text(encoding="utf-8")
    assert re.search(r'export PATH="\$\{HERE\}/usr/bin:\$\{PATH\}"', text), (
        "AppRun must prepend to PATH, keeping the host's ffmpeg reachable"
    )


def test_the_icon_name_resolves_to_an_icon_the_package_ships() -> None:
    """The launcher shows a generic placeholder when it does not, and nothing errors.

    The AppDir's icon is copied from the package at build time, so what this checks is that a
    source icon exists to copy — the sizes `T-274` and `T-277` produced.
    """
    assert desktop_entries()["Icon"] == COMPONENT_ID
    icons = REPOSITORY / "src" / "tracks_and_trails" / "resources" / "icons"
    assert (icons / "icon-256.png").is_file(), f"no source icon to install as {COMPONENT_ID}.png"


def test_the_metainfo_agrees_with_the_desktop_entry_and_the_project() -> None:
    """AppStream's id, launchable and licence, each of which is declared somewhere else too.

    A `launchable` that does not name the installed desktop file is the failure that makes a
    software centre list the application and then refuse to start it.
    """
    # `S314` is about untrusted input. This file is `packaging/appdir/`'s own, tracked in this
    # repository and read from a path this module builds — there is no untrusted document here.
    component = ElementTree.parse(METAINFO_FILE).getroot()  # noqa: S314
    assert component.findtext("id") == COMPONENT_ID
    assert component.findtext("launchable") == DESKTOP_FILE.name
    assert component.findtext("provides/binary") == binary_name()

    declared = tomllib.loads((REPOSITORY / "pyproject.toml").read_text(encoding="utf-8"))
    assert component.findtext("project_license") == declared["project"]["license"], (
        "the AppStream licence and pyproject disagree"
    )
