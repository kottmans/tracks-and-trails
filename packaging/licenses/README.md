# Third-party licence texts shipped with the artifact

**Purpose:** The exact upstream texts `LIC-001` requires every distributed artifact to carry, with
their provenance, so a later reader can verify each one rather than trust it.
**Owner:** Implementer
**Status:** Active
**Last updated:** 2026-09-11 — created with `T-323`.

`packaging/artifact_gates.py` checks these are present in every build. **The check is the point:**
a licence obligation that depends on somebody remembering to copy a file is one that eventually
ships unmet.

| File | Component | Licence | Source | Retrieved | Bytes |
|---|---|---|---|---|---|
| `Qt-LGPLv3.txt` | Qt, via PySide6 6.11.1 | LGPL-3.0 | <https://www.gnu.org/licenses/lgpl-3.0.txt> | 2026-09-11 | 7,652 |
| `Qt-GPLv3.txt` | Qt, via PySide6 6.11.1 | GPL-3.0 | <https://www.gnu.org/licenses/gpl-3.0.txt> | 2026-09-11 | 35,149 |
| `yt-dlp-Unlicense.txt` | yt-dlp 2026.7.4 | Unlicense | the installed wheel's own `dist-info/licenses/LICENSE` | 2026-09-11 | 1,211 |
| `NOTICE.txt` | — | — | written here | 2026-09-11 | — |
| `ffmpeg-LGPL.txt` | ffmpeg 9.0.1-29-gad500d59cb, `win64-lgpl-shared` | LGPL-3.0-or-later | the archive's own `LICENSE.txt` (see below) | 2026-09-12 | 7,651 |

## Why the GPLv3 text is here for an LGPL dependency

The LGPL-3.0 is not a standalone licence. Its own line 9 reads *"This version of the GNU Lesser
General Public License incorporates the terms and conditions of version 3 of the GNU General
Public License, supplemented by the additional permissions listed below."* Shipping the LGPL text
alone would distribute an incomplete licence.

## Why yt-dlp's text comes from the wheel rather than upstream

It is the text of **the version actually bundled**. `OPS-002` pins a yt-dlp baseline, and the
licence that has to ship is the pinned one's, not whatever `master` carries today.

## Which ffmpeg, and how its licence was obtained

`OPS-001` bundles ffmpeg on **Windows only**; on Linux it is a system dependency and no ffmpeg
licence is distributed. **The gate requires it only where ffmpeg is bundled**, so a Linux artifact
is not failed for lacking a licence for something it does not ship.

The build is pinned in `packaging/fetch_ffmpeg.py`:

    https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-09-12-13-12/
        ffmpeg-n9.0.1-29-gad500d59cb-win64-lgpl-shared-9.0.zip
    sha256  609245cc0a906c1423f2cdb96e27925302d375fe8024dcbc4b3f6aaf757a43ff

**Every part of that name is load-bearing.** `lgpl` because `LIC-001` forbids bundling a GPL
ffmpeg with an MIT application — `gyan.dev`'s builds are GPL and may **not** be used. `shared`
because the same requirement says the libraries must stay *replaceable*, which a static build is
not. An `autobuild-*` tag rather than `latest`, because `latest` is rolling and a release artifact
has to be rebuildable.

**Verified rather than assumed** (2026-09-12): the configure line embedded in `ffmpeg.exe` carries
`--enable-version3` and **no** `--enable-gpl` and **no** `--enable-nonfree`, and `avutil-61.dll`
self-reports `libavutil license: LGPL version 3 or later`.

**The text here is the archive's own `LICENSE.txt`, byte-for-byte**, which is the same principle
as yt-dlp's above: the licence that ships is the bundled build's, not whatever upstream carries
today. `fetch_ffmpeg.py` compares the two on every run and **refuses** if they differ, so the pin
cannot move without the licence moving with it.

It is LGPL **3**, not 2.1, because of `--enable-version3` — so `Qt-GPLv3.txt` above covers its
incorporated GPL terms too. It is *not* byte-identical to `Qt-LGPLv3.txt` (7,651 against 7,652
bytes), and both are shipped rather than deduplicated: each names the component it came with.
