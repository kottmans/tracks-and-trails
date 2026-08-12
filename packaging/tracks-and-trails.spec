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

# T-033. OPS-002 says every release bundles a pinned yt-dlp baseline.
#
# **These two lines are here for different reasons, and only one of them is load-bearing today.**
# The distinction was established by mutation (T-033, 2026-08-11): each line was removed in turn
# and the artifact rebuilt and probed.
#
# `collect_submodules` — **redundant for the current pin, kept as insurance for the next one**
# (REL-002). This comment used to say yt-dlp reaches its extractors through `lazy_extractors`,
# that 972 of its 1046 modules are resolved by name at runtime, and that static analysis
# therefore "collects the core and misses essentially every site". **The mutation disproved that
# for this pin**: `_extractors.py` carries **928 static `from .` imports**, so PyInstaller's
# module graph follows them unaided and the artifact built without this line still resolved
# extractors. It stays because the pin moves and that structure is yt-dlp's to change — a future
# baseline that goes back to name-only resolution would break the artifact silently, and this
# line is cheaper than finding out from a user. **Removing it today would not fail a gate**,
# which is exactly why the reason has to be written down rather than inferred from its presence.
#
# `collect_data_files` — **load-bearing, and its mutant survived for the worst possible reason.**
# Removing it deletes all three YouTube solver assets the baseline ships (`yt.solver.core.js`,
# `yt.solver.deno.lib.js`, `yt.solver.bun.lib.js`, under
# `yt_dlp/extractor/youtube/jsc/_builtin/vendor/`) — verified as three in the baseline artifact
# and **zero** in the mutant. **The frozen probe still reported OK**, because it instantiates
# `YoutubeIE` and checks a URL predicate and never touches them. So that survival measures a
# blind spot in the gate, not a dead line.
#
# The failure either would produce is the dangerous kind: `import yt_dlp` succeeds, the window
# opens, and downloads fail in a way that reads as ordinary site breakage rather than as a
# packaging fault.
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
