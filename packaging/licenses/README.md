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
| `ffmpeg-LGPL.txt` | ffmpeg | LGPL | **not yet present** — see below | — | — |

## Why the GPLv3 text is here for an LGPL dependency

The LGPL-3.0 is not a standalone licence. Its own line 9 reads *"This version of the GNU Lesser
General Public License incorporates the terms and conditions of version 3 of the GNU General
Public License, supplemented by the additional permissions listed below."* Shipping the LGPL text
alone would distribute an incomplete licence.

## Why yt-dlp's text comes from the wheel rather than upstream

It is the text of **the version actually bundled**. `OPS-002` pins a yt-dlp baseline, and the
licence that has to ship is the pinned one's, not whatever `master` carries today.

## ffmpeg is outstanding, and deliberately so

`OPS-001` bundles ffmpeg on **Windows only**; on Linux it is a system dependency and no ffmpeg
licence is distributed. `T-319` has not yet chosen the Windows binary, and `REL-005`/`LIC-001`
constrain that choice: an **LGPL** build — `BtbN`'s `*-lgpl-shared`, never `gyan.dev`'s GPL builds.
The licence text is added with the binary, and its build, version and source recorded in this
table.

**The gate requires it only where ffmpeg is bundled**, so a Linux artifact is not failed for
lacking a licence for something it does not ship.
