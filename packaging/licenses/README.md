# Third-party licence texts shipped with the artifact

**Purpose:** The exact upstream texts `LIC-001` requires every distributed artifact to carry, with
their provenance, so a later reader can verify each one rather than trust it.
**Owner:** Implementer
**Status:** Active
**Last updated:** 2026-10-11 — where the archive is kept, `T-360`; ffmpeg repinned by `T-357`; created with `T-323`.

`packaging/artifact_gates.py` checks these are present in every build. **The check is the point:**
a licence obligation that depends on somebody remembering to copy a file is one that eventually
ships unmet.

| File | Component | Licence | Source | Retrieved | Bytes |
|---|---|---|---|---|---|
| `Qt-LGPLv3.txt` | Qt, via PySide6 6.11.1 | LGPL-3.0 | <https://www.gnu.org/licenses/lgpl-3.0.txt> | 2026-09-11 | 7,652 |
| `Qt-GPLv3.txt` | Qt, via PySide6 6.11.1 | GPL-3.0 | <https://www.gnu.org/licenses/gpl-3.0.txt> | 2026-09-11 | 35,149 |
| `yt-dlp-Unlicense.txt` | yt-dlp 2026.8.19 | Unlicense | the installed wheel's own `dist-info/licenses/LICENSE` — byte-identical to 2026.7.4's, compared at the `T-332` bump | 2026-09-12 | 1,211 |
| `truststore-MIT.txt` | truststore 0.10.4 | MIT | the installed wheel's own `dist-info/licenses/LICENSE` | 2026-09-12 | 1,086 |
| `platformdirs-MIT.txt` | platformdirs 4.11.0 | MIT | the installed wheel's own `dist-info/licenses/LICENSE` — **shipped since Phase 0 with no licence text until 2026-09-12**; `LICENCE_FOR_DISTRIBUTION` is the check that found nothing had asked | 2026-09-12 | 1,089 |
| `NOTICE.txt` | — | — | written here | 2026-09-11 | — |
| `ffmpeg-LGPL.txt` | ffmpeg 9.0.2-17-g2a571b6068, `win64-lgpl-shared` | LGPL-3.0-or-later | the archive's own `LICENSE.txt` (see below) — the same text as 9.0.1-29's, compared at the `T-357` repin | 2026-09-12 | 7,651 |

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

    https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-09-30-13-08/
        ffmpeg-n9.0.2-17-g2a571b6068-win64-lgpl-shared-9.0.zip
    sha256  7157177b8a6cb2174c1650ba8c71b363f2c78cba5330f88c4c02cf5b2b880646

**Every part of that name is load-bearing.** `lgpl` because `LIC-001` forbids bundling a GPL
ffmpeg with an MIT application — `gyan.dev`'s builds are GPL and may **not** be used. `shared`
because the same requirement says the libraries must stay *replaceable*, which a static build is
not. An `autobuild-*` tag rather than `latest`, because `latest` is rolling and a release artifact
has to be rebuildable. **A month's last build rather than a daily** (`T-357`), because BtbN keeps
the last 14 daily builds and each month's last build for two years. The first pin,
`autobuild-2026-09-12-13-12` (ffmpeg 9.0.1-29, which `0.1.0` shipped), was a daily and had been
deleted by 2026-10-09.

**Kept beside each release** (`OPS-001`, amended 2026-10-11, `T-360`). Upstream retention is finite,
so the archive a release bundled is also one of that release's assets, and `fetch_ffmpeg.py` takes
it from there, by the same digest, when BtbN no longer has it. The release workflow attaches it,
and a draft without it fails.

**`0.1.0`'s archive**, 9.0.1-29 above, is an asset of
[`v0.1.0`](https://github.com/kottmans/tracks-and-trails/releases/tag/v0.1.0), attached on 2026-10-11
after BtbN had deleted it. GitHub records it at the digest `0.1.0` pinned, `609245cc…a43ff`.

**Verified rather than assumed**, for 9.0.1-29 on 2026-09-12 and again for 9.0.2-17 on 2026-10-10:
the configure line embedded in `ffmpeg.exe` carries `--enable-version3` and **no**
`--enable-gpl` and **no** `--enable-nonfree`, and `avutil-61.dll` self-reports
`libavutil license: LGPL version 3 or later`. The 2026-10-10 check read both strings from the
extracted binaries without running them.

**The text here is the archive's own `LICENSE.txt`, byte-for-byte**, which is the same principle
as yt-dlp's above: the licence that ships is the bundled build's, not whatever upstream carries
today. `fetch_ffmpeg.py` compares the two on every run and **refuses** if they differ, so the pin
cannot move without the licence moving with it.

It is LGPL **3**, not 2.1, because of `--enable-version3` — so `Qt-GPLv3.txt` above covers its
incorporated GPL terms too. It is *not* byte-identical to `Qt-LGPLv3.txt` (7,651 against 7,652
bytes), and both are shipped rather than deduplicated: each names the component it came with.
