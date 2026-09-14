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
from pathlib import Path, PureWindowsPath
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


def test_the_spec_bundles_ffmpeg_where_the_application_looks_for_it() -> None:
    """**This test was wrong, and confidently so** — it is kept as the case it should have been.

    It asserted that a destination of `"."` puts ffmpeg *beside the executable*, "which is where
    `bundled_ffmpeg` looks". Neither half was true of a real build: PyInstaller 6 puts a one-dir
    bundle under `_internal/`, so `"."` is the root of that, and the application was looking one
    level up. A string check agreed with a comment; the build disagreed with both (`T-319`).

    What can honestly be asserted from the spec text is that the binaries are declared and
    passed. **Where they end up is `bundled_ffmpeg`'s question**, and `test_environment.py` now
    covers it against the layout a build actually produces.
    """
    text = spec_text()
    assert "ffmpeg_binaries" in text, "the spec no longer bundles ffmpeg"
    assert "binaries=ffmpeg_binaries" in text, "the ffmpeg list is built and then not passed"
    assert re.search(r'\(str\(path\), "\."\)', text), "the destination is no longer declared"

    # The application must ask the runtime where its bundle is rather than assume a layout.
    resolver = (
        REPOSITORY / "src" / "tracks_and_trails" / "downloader" / "environment.py"
    ).read_text(encoding="utf-8")
    assert "_MEIPASS" in resolver, (
        "bundled_ffmpeg no longer asks sys._MEIPASS where the bundle is, so it is guessing again"
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


def test_the_installer_derives_a_numeric_version_rather_than_taking_one() -> None:
    """**The first compile found this.** `VersionInfoVersion` will not take a PEP 440 string.

    `AppVersion` comes straight from `__init__.py` via `REL-003`, which between releases is
    `0.1.0.dev0` — and Inno rejects it: *"Value of [Setup] section directive VersionInfoVersion
    is invalid"*, compile aborted. Measured on `STARBASE` 2026-09-12.

    **Derived rather than passed in**, so there is still one version input: a second `/D` define
    would be a second opinion, which is what `REL-003` exists to prevent. Verified on the
    compiled installer: `FileVersion 0.1.0.0` beside `ProductVersion 0.1.0.dev0`.
    """
    text = INSTALLER.read_text(encoding="utf-8")
    assert "VersionInfoVersion={#NumericVersion}" in text, (
        "VersionInfoVersion takes AppVersion again, which Inno rejects for a .devN version"
    )
    assert "#define NumericVersion" in text, "nothing derives the numeric version"
    assert 'StringChange(AppVersion, ".dev", ".")' in text, (
        "the derivation no longer maps .devN to a fourth numeric component"
    )
    # A suffix it cannot map must stop the compile rather than be guessed at.
    assert "#error" in text.split("#define NumericVersion")[1].split("[Setup]")[0], (
        "an unmappable version suffix would be stamped into the binary instead of refused"
    )


def test_the_workflow_finds_inno_setup_where_winget_puts_it() -> None:
    """**A path guessed rather than discovered, and it was wrong** (`T-322`).

    The release workflow looked only at `C:\\Program Files (x86)` and would have reported Inno
    Setup missing on a machine that had it: `winget install JRSoftware.InnoSetup` installs
    **per-user**, under `%LOCALAPPDATA%\\Programs\\Inno Setup 6\\`. Same class as the ffmpeg
    destination in `T-319` — a location asserted from a comment rather than from a build.
    """
    workflow = (REPOSITORY / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "LOCALAPPDATA/Programs/Inno Setup 6" in workflow, (
        "the per-user install location winget actually uses is not searched"
    )
    assert "Program Files (x86)/Inno Setup 6" in workflow, (
        "the per-machine location is not searched"
    )
    assert 'echo "ISCC=' in workflow, (
        "the located path is not exported, so the compile step guesses again"
    )


def test_the_installer_asks_for_no_administrator() -> None:
    """`NFR-004`: the application writes nothing beside itself, so a per-machine install would add
    an admin prompt on top of the SmartScreen warning `REL-005` already accepts. Two warnings
    before a first launch is how an install gets abandoned."""
    text = INSTALLER.read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in text
    assert "{autopf}" in text, "the install location is not the per-user one"
    # **No install-mode question either** (maintainer ruling, 2026-09-12). `dialog` asked "for me
    # only / for all users" before anything else, and no automated run could see it: they are all
    # `/VERYSILENT`. `commandline` keeps `/ALLUSERS` for an administrator.
    override = re.search(r"^PrivilegesRequiredOverridesAllowed=(\S+)", text, re.M)
    assert override is not None and override.group(1) == "commandline", (
        "the installer offers an install-mode choice on a double-click again"
    )


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


def uninstall_deletions(text: str) -> list[str]:
    """Every non-comment entry in the installer's `[UninstallDelete]` section, if it has one."""
    entries: list[str] = []
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line.lower()
        elif section == "[uninstalldelete]" and line and not line.startswith(";"):
            entries.append(line)
    return entries


def test_the_uninstaller_deletes_nothing_wholesale_under_the_install_directory() -> None:
    """**`T322-R1`, Critical.** `Type: filesandordirs; Name: "{app}"` deleted the whole directory.

    That is recursive deletion of **everything** there, including files a user saved into it or
    that were there before the installer used it — under a comment saying *only what the installer
    created*. Inno removes what its log installed without any entry, so the rule is: nothing
    recursive, and no wildcard, anywhere under `{app}`. A named, application-owned file would pass.
    """
    offending = [
        entry
        for entry in uninstall_deletions(INSTALLER.read_text(encoding="utf-8"))
        if "{app}" in entry.lower() and ("filesandordirs" in entry.lower() or "*" in entry)
    ]
    assert not offending, f"the uninstaller would delete user files: {offending}"


def test_the_wholesale_deletion_check_sees_the_line_that_was_there() -> None:
    """The positive control: the exact declaration `T322-R1` found must be refused."""
    shipped = '[UninstallDelete]\n; a comment\nType: filesandordirs; Name: "{app}"\n'
    assert uninstall_deletions(shipped) == ['Type: filesandordirs; Name: "{app}"']


def test_the_uninstall_message_promises_nothing_the_application_does_not_keep() -> None:
    """`T320-R3`'s neighbour: there is no download history to keep (`T-186`), so it is not named."""
    message = next(
        line
        for line in INSTALLER.read_text(encoding="utf-8").splitlines()
        if line.startswith("ConfirmUninstall=")
    )
    assert "history" not in message.lower()
    assert "kept" in message


# --- T-322: the uninstaller's question about the application's own data ------------------------

LOCAL_APPDATA: Final = r"C:\Users\someone\AppData\Local"
REMOVAL_CALL: Final = re.compile(r"\b(DeleteFile|DelTree|RemoveDir)\(([^,)]*)")


def code_section(text: str) -> str:
    """The installer's `[Code]` section, which runs last in the file."""
    _, marker, code = text.partition("\n[Code]\n")
    assert marker, "the installer has no [Code] section, so nothing asks about settings"
    return code


def data_removals(code: str) -> list[tuple[str, str]]:
    """Every removal the code makes, as (call, what it names relative to the data folder).

    Only two argument shapes are accepted, `Folder` and `Folder + '\name'`; anything else comes back
    whole, so a path built some other way fails the check rather than slipping past a parser.
    """
    removals: list[tuple[str, str]] = []
    for call, argument in REMOVAL_CALL.findall(code):
        named = re.fullmatch(r"Folder \+ '\\([^'\\*]+)'", argument.strip())
        if argument.strip() == "Folder":
            removals.append((call, ""))
        else:
            removals.append((call, named.group(1) if named else argument.strip()))
    return removals


def is_named_removal(call: str, name: str) -> bool:
    """A named item in the data folder, or `RemoveDir` of the folder, which needs it empty."""
    if not name:
        return call == "RemoveDir"
    return re.fullmatch(r"[A-Za-z0-9_.\-]+", name) is not None


def windows_layout(monkeypatch: pytest.MonkeyPatch) -> dict[str, PureWindowsPath]:
    """Where the application puts each thing on Windows, computed by the application's own code.

    Each module's `platformdirs` import is swapped for the Windows implementation with the known
    folder answered, so a `roaming=True`, a dropped `appauthor=False` or a renamed file moves the
    answer here exactly as it would move it on a user's machine.
    """
    import ntpath
    from types import SimpleNamespace

    import platformdirs.windows as windows

    import tracks_and_trails.core.logging as app_logging
    import tracks_and_trails.core.paths as paths
    import tracks_and_trails.core.settings as settings
    import tracks_and_trails.downloader.environment as environment
    import tracks_and_trails.persistence.db as db
    import tracks_and_trails.ui.main_window as main_window

    monkeypatch.setattr(windows, "os", SimpleNamespace(path=ntpath))
    monkeypatch.setattr(
        windows,
        "get_win_folder",
        lambda const: LOCAL_APPDATA if const == "CSIDL_LOCAL_APPDATA" else r"C:\Roaming",
    )

    def on_windows(kind: str):  # type: ignore[no-untyped-def]
        def resolve(appname=None, appauthor=None, version=None, roaming=False, *_, **__):  # type: ignore[no-untyped-def]
            dirs = windows.Windows(
                appname=appname, appauthor=appauthor, version=version, roaming=roaming
            )
            return getattr(dirs, kind)

        return resolve

    monkeypatch.setattr(settings, "user_config_dir", on_windows("user_config_dir"))
    monkeypatch.setattr(main_window, "user_config_dir", on_windows("user_config_dir"))
    monkeypatch.setattr(db, "user_data_dir", on_windows("user_data_dir"))
    monkeypatch.setattr(environment, "user_data_dir", on_windows("user_data_dir"))
    monkeypatch.setattr(app_logging, "user_cache_dir", on_windows("user_cache_dir"))
    monkeypatch.setattr(paths, "user_cache_dir", on_windows("user_cache_dir"))

    def windows_path(path: Path) -> PureWindowsPath:
        return PureWindowsPath(str(path).replace("/", "\\"))

    return {
        "settings": windows_path(settings.settings_path()),
        "window geometry": windows_path(main_window.geometry_path()),
        "queue database": windows_path(db.database_path()),
        "user yt-dlp": windows_path(environment.user_ytdlp_directory()),
        "application log": windows_path(app_logging.application_log_path()),
        "a job log": windows_path(app_logging.job_log_path("job")),
        "thumbnails and cache": windows_path(paths.cache_directory()),
    }


def test_the_data_question_is_asked_once_and_only_a_ticked_box_removes_anything() -> None:
    """**The maintainer's rulings in `T-327`**: no deleting settings by hand, and one dialog.

    Three properties carry the risk. A silent run never shows the dialog, because `T-039`'s Sandbox
    run uninstalls with `/VERYSILENT` and requires the data to survive byte for byte. Nothing is
    removed except on the explicit switch, and the switch is only added when the box is ticked. And
    the box starts unticked, so pressing Enter out of habit keeps the queue.
    """
    code = code_section(INSTALLER.read_text(encoding="utf-8"))
    initialize = code[code.index("function InitializeUninstall") :]
    initialize = initialize[: initialize.index("\nend;")]
    asking = initialize.index("AskHowToUninstall(")
    assert initialize.index("if UninstallSilent then\n    Exit;") < asking, (
        "a silent uninstall would stop to ask"
    )
    assert "Switches := '/SILENT " in initialize, "the second run would show Inno's box as well"
    assert re.search(
        r"if RemoveData then\s+Switches := Switches \+ ' ' \+ RemoveDataSwitch;", initialize
    ), "the removal switch is added whether or not the box is ticked"
    assert "RemoveBox.Checked := False;" in code, "the box would start ticked"
    step = code[code.index("procedure CurUninstallStepChanged") :]
    assert re.search(r"if HasSwitch\(RemoveDataSwitch\) then\s+RemoveApplicationData;", step), (
        "data is removed without the switch a ticked box adds"
    )
    calls = re.findall(r"(?<!procedure )\bRemoveApplicationData;", code)
    assert len(calls) == 1, "data is removed somewhere nothing asks"


def test_the_data_folder_is_the_one_the_application_writes_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The script names `{localappdata}\tracksandtrails` and the application computes its paths.
    Those are two declarations, so every place the application writes must sit under the one the
    uninstaller cleans, or a "yes" leaves settings behind."""
    code = code_section(INSTALLER.read_text(encoding="utf-8"))
    folder = re.search(r"Result := ExpandConstant\('\{localappdata\}\\([^']+)'\);", code)
    assert folder is not None, "the data folder is no longer {localappdata}\\<name>"
    root = PureWindowsPath(LOCAL_APPDATA, folder.group(1))
    for what, path in windows_layout(monkeypatch).items():
        assert root in path.parents, f"the {what} is written at {path}, outside {root}"


def test_a_yes_removes_everything_the_application_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each place from `windows_layout` must be removed by a named entry: its first component
    below the data folder is deleted, or it is inside a directory that is."""
    code = code_section(INSTALLER.read_text(encoding="utf-8"))
    folder = re.search(r"Result := ExpandConstant\('\{localappdata\}\\([^']+)'\);", code)
    assert folder is not None
    root = PureWindowsPath(LOCAL_APPDATA, folder.group(1))
    removed = {name: call for call, name in data_removals(code) if name}
    for what, path in windows_layout(monkeypatch).items():
        first = path.relative_to(root).parts[0]
        assert first in removed, f"a yes leaves the {what} behind ({first})"
        if len(path.relative_to(root).parts) > 1:
            assert removed[first] == "DelTree", (
                f"the {what} is inside {first}, which is not deleted"
            )
    # The database's WAL companions and the settings scratch file are the application's too
    # (`persistence/db.py` sets WAL; `core/settings.py` writes `settings.toml.writing`).
    database = windows_layout(monkeypatch)["queue database"].name
    for companion in (f"{database}-wal", f"{database}-shm", "settings.toml.writing"):
        assert companion in removed, f"a yes leaves {companion} behind"


def test_a_yes_removes_nothing_it_does_not_name() -> None:
    """**`T322-R1`'s rule, carried from `{app}` to the data folder.** Nothing wholesale: the folder
    itself may only be `RemoveDir`ed, which fails while anything is left in it, so a video someone
    saved there survives. No wildcard, no `{app}`, no path built any other way."""
    code = code_section(INSTALLER.read_text(encoding="utf-8"))
    removals = data_removals(code)
    assert removals, "the removal parser found nothing, so this check would pass blind"
    for call, name in removals:
        assert is_named_removal(call, name), f"{call} of something not named: {name or 'Folder'}"


@pytest.mark.parametrize(
    "shipped",
    [
        "DelTree(Folder, True, True, True);",
        "DelTree(ExpandConstant('{app}'), True, True, True);",
        "DeleteFile(Folder + '\\*.toml');",
    ],
)
def test_the_named_removal_check_refuses_what_it_exists_to_refuse(shipped: str) -> None:
    """The positive controls: a wholesale delete, `{app}`, and a wildcard."""
    [(call, name)] = data_removals(shipped)
    assert not is_named_removal(call, name)


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


def test_the_wizard_artwork_the_installer_names_exists() -> None:
    """**Our logo, not Inno's stock box-and-disc** — and the two declarations agree.

    The maintainer's first real install (2026-09-12) showed the default artwork on every page:
    `SetupIconFile` covers the .exe's icon and nothing else. The images are rendered by
    `tools/icons/render_installer_art.py` and named again in the `.iss`; ISCC fails loudly on a
    missing file, but only on Windows, so a renamed size would otherwise surface at release time.
    """
    text = INSTALLER.read_text(encoding="utf-8")
    art = REPOSITORY / "packaging"
    for directive in ("WizardSmallImageFile", "WizardImageFile"):
        match = re.search(rf"^{directive}=(.+)$", text, re.M)
        assert match is not None, (
            f"the installer no longer sets {directive}, so Inno's default art returns"
        )
        for name in match.group(1).split(","):
            path = art / name.strip().replace("\\", "/")
            assert path.is_file(), f"{directive} names {name.strip()}, which does not exist"


def _png_size(path: Path) -> tuple[int, int]:
    """Width and height from a PNG's IHDR chunk — no imaging library needed."""
    header = path.read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")


def test_the_wizard_artwork_is_the_shape_its_slot_is() -> None:
    """**The installer logo looked fuzzy, and the sizes were why** (`T-322`, 2026-09-12).

    The first cut used Inno Setup's pre-6.6 sizes from memory: several corner images were not
    square, and the panel images were not at the 164:314 aspect Inno keeps. Inno picks the nearest
    image and stretches it to fit, so a wrong shape is a distorted logo and a too-small one is a
    blurred logo. The slot sizes now come from Inno 6.7's own help; this pins the shape.
    """
    text = INSTALLER.read_text(encoding="utf-8")

    def right_shape(directive: str, width: int, height: int) -> bool:
        if directive == "WizardSmallImageFile":
            return width == height
        return abs(width / height - 164 / 314) < 0.01

    for directive in ("WizardSmallImageFile", "WizardImageFile"):
        match = re.search(rf"^{directive}=(.+)$", text, re.M)
        assert match is not None
        sizes = []
        for name in match.group(1).split(","):
            width, height = _png_size(REPOSITORY / "packaging" / name.strip().replace("\\", "/"))
            assert right_shape(directive, width, height), (
                f"{name.strip()} is {width}x{height}, the wrong shape for {directive}"
            )
            sizes.append((width, height))
        # A 100% slot must have an image at least its size, or it is stretched up and blurs.
        smallest = min(sizes)
        floor = (58, 58) if directive == "WizardSmallImageFile" else (202, 386)
        assert smallest[0] >= floor[0] and smallest[1] >= floor[1], (
            f"{directive}'s smallest image is {smallest}, below the {floor} slot at 100% scaling"
        )


def test_the_sandbox_run_downloads_in_the_preset_that_failed() -> None:
    """`T-332`: the clean-machine evidence asks for the 1080p MP4 preset's own selector.

    Written into the PowerShell script as a literal, so this is what keeps the two from drifting —
    a preset edited without the script would leave the Sandbox proving a selector nobody uses.
    """
    from tracks_and_trails.core.presets import BEST_VIDEO_1080P

    script = (
        Path(__file__).parents[2] / "packaging" / "windows-sandbox" / "evidence.ps1"
    ).read_text("utf-8")
    found = re.search(r'^\s*\$presetFormat = "([^"]+)"', script, re.MULTILINE)
    assert found, "evidence.ps1 no longer downloads in a preset"
    assert found.group(1) == BEST_VIDEO_1080P.format_selector
    assert "$env:TT_DOWNLOAD_PROBE_FORMAT = $presetFormat" in script
