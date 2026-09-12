"""Fetch the Windows ffmpeg the release artifact bundles (`T-319`), pinned and verified.

`OPS-001` bundles ffmpeg on Windows and treats it as a system dependency on Linux, so this runs
for the Windows build only. `LIC-001` constrains *which* ffmpeg: it must be **dynamically linked
and replaceable**, and its licence text must ship. Both decide the build family before anything
else does — `BtbN`'s `win64-lgpl-shared`, never a static build and never `gyan.dev`'s, which are
GPL and may not be bundled with an MIT application.

    python3 packaging/fetch_ffmpeg.py

**Run once by hand, and callable by a workflow — one mechanism, two callers.** `T-319` left the
acquisition open between *"a build-time download with a recorded URL and checksum"* and *"a copy
placed on `STARBASE` by hand the way Inno Setup is"*, noting that `OPS-012` §3 argues for the
second and the release workflow for the first. This is the shape that satisfies both: the download
is scripted, pinned and digest-verified, so it is reproducible and reviewable; and **it is not
wired into the build**, so a self-hosted runner never provisions itself as a side effect of a
build, which is what `OPS-012` §3 forbids. `packaging/tracks-and-trails.spec` reads what is
already on disk and fails loudly if it is absent.

**Pinned to an `autobuild-*` tag, not `latest`.** `latest` is a rolling tag: the same URL returns
a different binary tomorrow, and a release artifact would then not be rebuildable. The tag below
names one moment.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen

#: One published moment, not a rolling tag.
FFMPEG_RELEASE = "autobuild-2026-09-12-13-12"

#: The **shared LGPL** build. Every part of this name is load-bearing: `lgpl` because `LIC-001`
#: forbids bundling a GPL ffmpeg with this application, and `shared` because the same requirement
#: says the libraries must stay replaceable — a static build is neither.
FFMPEG_ARCHIVE = "ffmpeg-n9.0.1-29-gad500d59cb-win64-lgpl-shared-9.0.zip"

#: Verified before anything is extracted. Measured 2026-09-12 on the archive this pin names.
FFMPEG_SHA256 = "609245cc0a906c1423f2cdb96e27925302d375fe8024dcbc4b3f6aaf757a43ff"

FFMPEG_URL = (
    f"https://github.com/BtbN/FFmpeg-Builds/releases/download/{FFMPEG_RELEASE}/{FFMPEG_ARCHIVE}"
)

#: Where the spec looks. Gitignored: 174 MB of third-party binary does not belong in the history,
#: which is the half of `T-319`'s open question that was never in doubt.
VENDOR = Path(__file__).resolve().parent / "vendor" / "ffmpeg"

#: The licence text committed beside this, which `artifact_gates.py` requires in every build that
#: bundles ffmpeg. Checked against the archive's own copy, so the text we ship cannot drift from
#: the build we ship — the principle `packaging/licenses/README.md` already states for yt-dlp.
LICENCE = Path(__file__).resolve().parent / "licenses" / "ffmpeg-LGPL.txt"

#: What the application actually runs. **`ffprobe.exe` is not optional**: yt-dlp's
#: `FFmpegExtractAudioPP.run` calls `get_audio_codec`, which runs ffprobe on the downloaded file,
#: so `REQ-010`'s audio extraction needs it. **`ffplay.exe` is excluded** — 18 MB of a media
#: player nothing here launches.
WANTED_EXECUTABLES = ("ffmpeg.exe", "ffprobe.exe")


def download(url: str) -> bytes:
    print(f"==> {url}")
    with urlopen(url) as response:  # noqa: S310 - a pinned https URL from this file's constants
        return bytes(response.read())


def main() -> int:
    VENDOR.mkdir(parents=True, exist_ok=True)
    archive = VENDOR / FFMPEG_ARCHIVE

    if archive.is_file() and hashlib.sha256(archive.read_bytes()).hexdigest() == FFMPEG_SHA256:
        print(f"==> already have a verified {FFMPEG_ARCHIVE}")
        payload = archive.read_bytes()
    else:
        payload = download(FFMPEG_URL)
        digest = hashlib.sha256(payload).hexdigest()
        if digest != FFMPEG_SHA256:
            # **Refuse rather than warn.** This binary is about to be signed and shipped under
            # this project's name; a mismatch means the pin and the file disagree, and there is no
            # reading of that which makes extracting it the right move.
            print(
                f"FAIL: {FFMPEG_ARCHIVE} hashes to {digest}, not {FFMPEG_SHA256}.\n"
                f"      Refusing to extract an ffmpeg that is not the one this pin names.",
                file=sys.stderr,
            )
            return 1
        archive.write_bytes(payload)
        print(f"==> verified {digest}")

    with zipfile.ZipFile(archive) as bundle:
        root = Path(bundle.namelist()[0]).parts[0]
        licence_text = bundle.read(f"{root}/LICENSE.txt")

        # **The licence we ship must be the licence of the build we ship.** Checked here rather
        # than trusted, because the gate downstream only asserts the file is present and
        # non-empty — it cannot know which ffmpeg it belongs to.
        if not LICENCE.is_file():
            print(f"FAIL: {LICENCE} is missing; LIC-001 requires it to ship.", file=sys.stderr)
            return 1
        if LICENCE.read_bytes() != licence_text:
            print(
                f"FAIL: {LICENCE.name} is not this build's own LICENSE.txt.\n"
                f"      The pin moved and the licence text did not. Copy it across and record "
                f"the new build in packaging/licenses/README.md.",
                file=sys.stderr,
            )
            return 1

        wanted = [
            name
            for name in bundle.namelist()
            if name.startswith(f"{root}/bin/")
            and (name.endswith(".dll") or Path(name).name in WANTED_EXECUTABLES)
        ]
        for name in wanted:
            target = VENDOR / Path(name).name
            with bundle.open(name) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink)

    missing = [name for name in WANTED_EXECUTABLES if not (VENDOR / name).is_file()]
    if missing:
        print(f"FAIL: the archive carried no {', '.join(missing)}.", file=sys.stderr)
        return 1

    size = sum(path.stat().st_size for path in VENDOR.glob("*") if path.name != FFMPEG_ARCHIVE)
    print(f"==> {len(wanted)} file(s) in {VENDOR}, {size / 1e6:.0f} MB")
    print("==> the spec bundles these when TT_RELEASE_BUILD=1")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through `main`
    raise SystemExit(main())
