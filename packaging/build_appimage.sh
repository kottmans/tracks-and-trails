#!/usr/bin/env bash
# Build the Linux release artifact (`T-321`, format chosen by `REL-004`).
#
# **Run inside the container, not on the development machine.** `REL-004` requires building
# against the oldest glibc the README claims, and the reason is a silent failure: the artifact
# builds, runs on the build host, and dies on the user's machine with `GLIBC_x.yz not found`.
# Measured 2026-09-11 — the development machine is **glibc 2.43** and Ubuntu 24.04 LTS is 2.39, so
# an AppImage built here would fail on every current LTS while passing every test run here.
#
#   podman run --rm -v "$PWD":/src:ro,Z -v "$PWD/dist":/out:Z \
#       docker.io/library/python:3.14-slim-bookworm /src/packaging/build_appimage.sh
#
# `python:3.14-slim-bookworm` is **glibc 2.36** and carries Python 3.14 already. It is older than
# the Ubuntu LTS `T-321` proposed (2.39) and so covers more machines, and there is no 3.14 image
# on an older Debian — `bullseye` has none. **The floor that buys is Debian 12 / Ubuntu 24.04 and
# newer; Ubuntu 22.04 is glibc 2.35 and is out of reach.** The README claims what this builds on,
# never more.
set -euo pipefail

SOURCE=${SOURCE:-/src}
WORK=${WORK:-/tmp/build}
OUT=${OUT:-/out}
ID=io.github.kottmans.TracksAndTrails

echo "==> glibc on this build host"
ldd --version | head -1

echo "==> copying the source out of the read-only mount"
rm -rf "$WORK"
mkdir -p "$WORK"
cp -a "$SOURCE"/. "$WORK"/
cd "$WORK"
rm -rf .venv .git dist build

# **`binutils` is not optional.** PyInstaller reads each shared library's dependencies with
# `objdump`, and the slim image has no toolchain at all — it fails at the freeze step with a
# message that names the package, which is the one kind of missing dependency that explains itself.
# `file` is wanted by `appimagetool`'s own checks.
#
# **Qt's own runtime libraries are not optional either, and that one does *not* explain itself.**
# PyInstaller's PySide6 hook spawns a child process to ask Qt where its plugins live. Without
# these, that child cannot import `QtCore`, the hook logs
# `failed to obtain Qt library info` as a **warning**, and the build continues — producing an
# artifact with **no platform plugins at all**. It runs, prints `--version`, and passes every
# probe, because none of those creates a `QApplication`. The first thing that does dies with
# *"no Qt platform plugin could be initialized"*. Measured 2026-09-11 on a real desktop.
#
# They are needed twice over: once so the hook can read Qt's layout, and again so these `.so`
# files are bundled rather than resolved from whatever the user's distribution happens to ship.
echo "==> installing the build toolchain and Qt's runtime dependencies"
apt-get -qq update >/dev/null
apt-get -qq install -y --no-install-recommends \
    binutils file \
    libglib2.0-0 libfontconfig1 libfreetype6 libdbus-1-3 \
    libx11-6 libxext6 libxrender1 libxkbcommon0 libxkbcommon-x11-0 \
    libxcb1 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
    libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-sync1 \
    libxcb-xfixes0 libxcb-xinerama0 libxcb-xkb1 \
    libegl1 libgl1 libbrotli1 libkrb5-3 libgssapi-krb5-2 >/dev/null

echo "==> installing the project and PyInstaller"
python3 -m pip install -q --upgrade pip --root-user-action=ignore
python3 -m pip install -q -e . pyinstaller --root-user-action=ignore

echo "==> freezing"
pyinstaller --noconfirm --clean packaging/tracks-and-trails.spec

echo "==> assembling the AppDir"
APPDIR="$WORK/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/metainfo" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a dist/tracks-and-trails/. "$APPDIR/usr/bin/"
install -m 755 packaging/appdir/AppRun "$APPDIR/AppRun"
install -m 644 "packaging/appdir/$ID.desktop" "$APPDIR/$ID.desktop"
install -m 644 "packaging/appdir/$ID.desktop" "$APPDIR/usr/share/applications/$ID.desktop"
install -m 644 "packaging/appdir/$ID.metainfo.xml" "$APPDIR/usr/share/metainfo/$ID.metainfo.xml"
# **The icon sits at the AppDir root as well as in the theme**, because that is where the AppImage
# runtime and most launchers look for it; `Icon=` names it without an extension.
install -m 644 src/tracks_and_trails/resources/icons/icon-256.png "$APPDIR/$ID.png"
install -m 644 src/tracks_and_trails/resources/icons/icon-256.png \
        "$APPDIR/usr/share/icons/hicolor/256x256/apps/$ID.png"

# **The check that would have caught this on the first build** (`T-321`, 2026-09-11). The hook
# degrades to a warning when it cannot read Qt's layout, and an artifact with no platform plugin
# passes `--version` and every probe. Nothing else in this project asks whether a window can open.
echo "==> asserting the Qt platform plugins came across"
PLATFORMS=$(find "$APPDIR/usr/bin" -type d -name platforms | head -1)
if [ -z "$PLATFORMS" ] || [ -z "$(ls -A "$PLATFORMS" 2>/dev/null)" ]; then
    echo "FAIL: no Qt platform plugins in the bundle. PyInstaller's PySide6 hook could not read" >&2
    echo "      Qt's library info — check the apt-get list above against Qt's dependencies." >&2
    exit 1
fi
echo "    $(ls "$PLATFORMS" | tr '\n' ' ')"

echo "==> the release gates, over the AppDir's payload"
python3 packaging/artifact_gates.py "$APPDIR/usr/bin"

VERSION=$(python3 -c "import sys; sys.path.insert(0,'src'); import tracks_and_trails as t; print(t.__version__)")
echo "==> version: $VERSION"

if [ -x /usr/local/bin/appimagetool ]; then
    echo "==> packing the AppImage"
    ARCH=x86_64 /usr/local/bin/appimagetool --appimage-extract-and-run \
        "$APPDIR" "$OUT/Tracks_and_Trails-$VERSION-x86_64.AppImage"
else
    echo "==> appimagetool absent; leaving the AppDir for packing"
    rm -rf "$OUT/AppDir"
    cp -a "$APPDIR" "$OUT/AppDir"
fi
echo "==> done"
