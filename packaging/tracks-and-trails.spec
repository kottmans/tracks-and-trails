# PyInstaller spec for the T-020 frozen smoke test.
#
# Deliberately minimal. This is NOT the release build: no installer, no ffmpeg, no icon
# resources beyond what the package already carries, no signing, no size work — all Phase 5.
# It exists to answer one question in CI, from Phase 0: does spawning a child process from a
# frozen binary work, or does it relaunch the application (REL-001, ARCHITECTURE.md §12)?
#
# One-dir, matching REL-001's Windows target. One-file would extract to a temp directory on
# every launch and change the very sys.executable semantics under test.

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("tracks_and_trails", includes=["resources/icons/*"])

# T-014 (T014-R3). Without this the artifact builds, launches, and cannot persist anything.
#
# The migrations are .sql files. PyInstaller follows *imports*, and nothing imports a .sql, so
# they are collected only if asked for by name. The failure mode is the quiet kind again: the
# migration directory is simply absent, so `available_migrations()` returns an empty list, the
# database is created at version 0 with no tables, and the first write fails with `no such
# table: jobs` — which reads as a code bug rather than a packaging one.
#
# `persistence.migrate` now raises on an empty migration set rather than proceeding, so a spec
# that loses this line fails loudly at startup instead of at the first download.
datas += collect_data_files("tracks_and_trails", includes=["persistence/migrations/*.sql"])

# T-323. LIC-001: the licence texts ship with *every distributed artifact*, not only the release.
#
# **The gate found this absent on its first run**, which is the argument for the gate. Qt is
# LGPLv3 and ffmpeg's Windows build is LGPL; distributing either without its text is a breach,
# and an artifact that lacks them still builds, still launches and still passes every other
# check — so nothing was ever going to notice.
#
# `SPECPATH` rather than a relative path: a spec is executed with the *caller's* working
# directory, so `packaging/licenses` resolves against wherever pyinstaller was invoked from and
# silently collects nothing when that is not the repository root.
datas += [(str(Path(SPECPATH) / "licenses"), "licenses")]

# T-033. OPS-002 says every release bundles a pinned yt-dlp baseline.
#
# **These two lines are here for different reasons, and only one of them is load-bearing today.**
# T-033's mutations removed each in turn and rebuilt and probed the artifact; **REL-002 is where
# that reasoning and its measurements live**, and this comment points at it rather than restating
# it, so there is one copy to keep true.
#
# `collect_submodules` — **redundant for the current pin, kept as insurance for the next one**
# (REL-002). The artifact built without it still resolved extractors, and no gate failed. It stays
# because the pin moves and the structure it relies on is yt-dlp's to change.
#
# `collect_data_files` — **load-bearing.** Removing it deletes the YouTube solver assets the
# baseline ships, and **the frozen probe still reported OK**, because the probe never touches them.
# That mutant's survival measures a blind spot in the gate rather than a dead line.
#
# **Neither removal fails a gate, and the two removals are not otherwise alike.** Keeping those
# apart is the point of writing the reasons down:
#
#   - removing `collect_submodules` for *this pin* broke nothing that was measured — the artifact
#     built and still resolved extractors — so no gate fired because there was nothing to fire at;
#   - removing `collect_data_files` **did** break the artifact, deleting the solver assets, and no
#     gate fired anyway because the probe never touches them.
#
# The second is the dangerous kind: `import yt_dlp` succeeds, the window opens, and downloads fail
# in a way that reads as ordinary site breakage rather than as a packaging fault. A future pin
# could put `collect_submodules` in the same position, which is why it stays.
ytdlp_hiddenimports = collect_submodules("yt_dlp")
datas += collect_data_files("yt_dlp")

# **One spec, two modes** (`T-319`). The release build is the same `Analysis` with a different
# console setting, selected by an environment variable rather than by a second spec file: two
# specs are two things to keep true, and `T-233`/`T-237` were both about spec comments drifting
# from the spec beside them.
#
#     TT_RELEASE_BUILD=1 pyinstaller packaging/tracks-and-trails.spec
#
# **`console=False` costs the probes their `stdout`**, which is why `_freeze_probe.say` writes to
# `TT_PROBE_REPORT` as well as printing. CI reads the file for a windowed build and the console
# for the smoke one; the probes themselves do not know which build they are in.
RELEASE_BUILD = os.environ.get("TT_RELEASE_BUILD") == "1"

# **The Windows version resource** (`T-319`), written here from `__init__.py` rather than kept as
# a file: `[tool.hatch.version]` already reads that module, and a checked-in resource would be a
# third place for the version to disagree with itself.
#
# Written only for a release build, and only on Windows, where the field means anything.
VERSION_FILE = Path(SPECPATH) / "windows-version-info.txt"
if RELEASE_BUILD and sys.platform == "win32":
    sys.path.insert(0, str(Path(SPECPATH).parent / "src"))
    from tracks_and_trails import __version__ as _release_version

    _parts = [int(piece) for piece in _release_version.split(".dev")[0].split(".")] + [0, 0, 0, 0]
    _quad = tuple(_parts[:4])
    VERSION_FILE.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={_quad}, prodvers={_quad}, mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable("040904B0", [
        StringStruct("CompanyName", "Sean Kottman"),
        StringStruct("FileDescription", "Tracks & Trails"),
        StringStruct("FileVersion", "{_release_version}"),
        StringStruct("InternalName", "tracks-and-trails"),
        StringStruct("LegalCopyright", "MIT licensed. Third-party notices in licenses/."),
        StringStruct("OriginalFilename", "tracks-and-trails.exe"),
        StringStruct("ProductName", "Tracks & Trails"),
        StringStruct("ProductVersion", "{_release_version}"),
    ])]),
    VarFileInfo([VarStruct("Translation", [1033, 1200])]),
  ],
)
""",
        encoding="utf-8",
    )

# **ffmpeg, bundled on Windows only** (`OPS-001`, `T-319`). `binaries` rather than `datas`, so
# PyInstaller treats them as libraries and runs its dependency analysis over them.
#
# **A destination of `"."` is the root of `_internal/`, not the directory holding the
# executable**, and that comment used to claim otherwise. PyInstaller 6 moved the one-dir layout
# under `_internal/`; measured on a real Windows build, these land at `_internal\ffmpeg.exe`.
# `downloader.environment.bundled_ffmpeg` asks `sys._MEIPASS` for that directory rather than
# guessing, so the two agree through the runtime's own answer instead of through a pair of
# string literals that were, in fact, different.
#
# **Fetched, never committed.** `packaging/fetch_ffmpeg.py` downloads one pinned `BtbN`
# `win64-lgpl-shared` archive and verifies its SHA-256; 155 MB of third-party binary does not
# belong in the history. **This spec does not run that script**, because `OPS-012` §3 forbids a
# self-hosted runner provisioning itself as a side effect of a build. It reads what is on disk and
# **fails** if it is not there, which is a build that stops rather than a release that silently
# ships without the tool `REQ-010`'s audio extraction needs.
ffmpeg_binaries: list[tuple[str, str]] = []
if RELEASE_BUILD and sys.platform == "win32":
    _vendor = Path(SPECPATH) / "vendor" / "ffmpeg"
    _wanted = sorted(
        [*_vendor.glob("*.exe"), *_vendor.glob("*.dll")], key=lambda path: path.name
    )
    if not any(path.name == "ffmpeg.exe" for path in _wanted):
        raise SystemExit(
            f"no ffmpeg.exe in {_vendor}. OPS-001 bundles ffmpeg on Windows and LIC-001 requires "
            f"an LGPL build; run `python packaging/fetch_ffmpeg.py` first. This spec deliberately "
            f"does not fetch it itself (OPS-012 section 3)."
        )
    # `"."` is the executable's own directory in a one-dir build.
    ffmpeg_binaries = [(str(path), ".") for path in _wanted]

a = Analysis(
    ["../src/tracks_and_trails/__main__.py"],
    pathex=["../src"],
    binaries=ffmpeg_binaries,
    datas=datas,
    hiddenimports=["tracks_and_trails._freeze_probe", *ytdlp_hiddenimports],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="tracks-and-trails",
    debug=False,
    strip=False,
    upx=False,
    # A user must not get a console window behind the application. The smoke build keeps one
    # because `packaging/frozen_smoke.py` and CI read the probes from it.
    console=not RELEASE_BUILD,
    # `icon.ico` is the multi-size icon `T-274` produced; PyInstaller ignores it on Linux, so it
    # is set unconditionally rather than behind another branch.
    icon=str(Path(SPECPATH).parent / "src/tracks_and_trails/resources/icons/icon.ico"),
    # Windows file/product metadata, so the executable's Properties pane is not blank. Generated
    # beside the spec rather than checked in: every field in it comes from `__version__` and
    # `pyproject.toml`, and a checked-in copy is a third place for the version to disagree.
    version=str(VERSION_FILE) if RELEASE_BUILD and VERSION_FILE.exists() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="tracks-and-trails",
)
