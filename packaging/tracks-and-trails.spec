# PyInstaller spec for the T-020 frozen smoke test.
#
# Deliberately minimal. This is NOT the release build: no installer, no ffmpeg, no icon
# resources beyond what the package already carries, no signing, no size work — all Phase 5.
# It exists to answer one question in CI, from Phase 0: does spawning a child process from a
# frozen binary work, or does it relaunch the application (REL-001, ARCHITECTURE.md §12)?
#
# One-dir, matching REL-001's Windows target. One-file would extract to a temp directory on
# every launch and change the very sys.executable semantics under test.

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
