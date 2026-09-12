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
echo "==> installing the build toolchain the slim image lacks"
apt-get -qq update >/dev/null
apt-get -qq install -y --no-install-recommends binutils file >/dev/null

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
