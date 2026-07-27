# PyInstaller spec for the T-020 frozen smoke test.
#
# Deliberately minimal. This is NOT the release build: no installer, no ffmpeg, no icon
# resources beyond what the package already carries, no signing, no size work — all Phase 5.
# It exists to answer one question in CI, from Phase 0: does spawning a child process from a
# frozen binary work, or does it relaunch the application (REL-001, ARCHITECTURE.md §12)?
#
# One-dir, matching REL-001's Windows target. One-file would extract to a temp directory on
# every launch and change the very sys.executable semantics under test.

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

# T-033. Without this the artifact builds, launches, and fails every URL.
#
# OPS-002 says every release bundles a pinned yt-dlp baseline. PyInstaller's analysis follows
# *static* imports, and yt-dlp reaches its extractors through `lazy_extractors` — 972 of its
# 1046 modules are extractors resolved by name at runtime. Static analysis therefore collects
# the yt-dlp core and misses essentially every site.
#
# The resulting failure is the dangerous kind: `import yt_dlp` succeeds, the window opens, and
# every download reports "unsupported URL" — which reads exactly like ordinary site breakage,
# so it would be diagnosed as a yt-dlp problem rather than a packaging one.
ytdlp_hiddenimports = collect_submodules("yt_dlp")
datas += collect_data_files("yt_dlp")

a = Analysis(
    ["../src/tracks_and_trails/__main__.py"],
    pathex=["../src"],
    binaries=[],
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
