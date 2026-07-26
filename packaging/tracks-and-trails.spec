# PyInstaller spec for the T-020 frozen smoke test.
#
# Deliberately minimal. This is NOT the release build: no installer, no ffmpeg, no icon
# resources beyond what the package already carries, no signing, no size work — all Phase 5.
# It exists to answer one question in CI, from Phase 0: does spawning a child process from a
# frozen binary work, or does it relaunch the application (REL-001, ARCHITECTURE.md §12)?
#
# One-dir, matching REL-001's Windows target. One-file would extract to a temp directory on
# every launch and change the very sys.executable semantics under test.

from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("tracks_and_trails", includes=["resources/icons/*"])

a = Analysis(
    ["../src/tracks_and_trails/__main__.py"],
    pathex=["../src"],
    binaries=[],
    datas=datas,
    hiddenimports=["tracks_and_trails._freeze_probe"],
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
    console=True,  # Phase 5 makes this windowed; the probe needs stdout in CI.
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="tracks-and-trails",
)
