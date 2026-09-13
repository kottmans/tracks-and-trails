# Windows clean-machine evidence — Sandbox, 2026-09-13

**Captured by** `tools/windows/sandbox_evidence.sh`, which ran `packaging/windows-sandbox/evidence.ps1`
inside Windows Sandbox on `STARBASE` and exited 0 on the verdict below. **Retained for `T318-R1`,
`T322-R1` and `T039-R1`.**

**Artifact:** `Tracks-and-Trails-0.1.0.dev0-setup.exe`, sha256
`5c5c3ec375adb2edd40b637a938e7a9ab736520cd6a61d6d3184dac80fcbc489`, compiled on `STARBASE` from a
release build (`TT_RELEASE_BUILD=1`) of the tree at `a3fd2db` plus the then-uncommitted installer
and harness corrections committed as `c3abd5c` and `1e9abd5`. **`src/` and the spec are identical
between `a3fd2db` and `1e9abd5`**, so this is the product those commits describe. It is a
development build, not a release candidate; `T-326`'s candidate evidence is still owed.

**Negative controls from the same release build**, each an installer with one deliberate defect,
run through the same runner — the lines that decided their verdicts:

*The recursive uninstall rule restored* (sha256 `91bd51cb…`), runner exit 1:

```
user file         pre-existing sentinel DELETED by the uninstaller - T322-R1
user file         user-saved file DELETED by the uninstaller - T322-R1
<!-- VERDICT: FAIL 2 -->
```

*A stray payload in Documents, and an uninstall rule deleting the user data* (sha256 `f94a5f36…`),
runner exit 1:

```
outside       1 WRITTEN OUTSIDE the install root and Start Menu: C:\Users\WDAGUtilityAccount\Documents\stray-payload\tracks-and-trails.exe
                  FAILED - 4 removed or changed by the uninstaller, which DAT-001 preserves: library.sqlite3, library.sqlite3-wal, library.sqlite3-shm
<!-- VERDICT: FAIL 2 -->
```

---

**The passing run's report, as captured:**

# Clean-machine evidence - Windows - Sandbox

Taken by `packaging/windows-sandbox/evidence.ps1` inside Windows Sandbox, which is clean on
every launch by construction (`REL-006`). Nothing below was installed by this script except
the artifact itself.

## Machine

```
date      2026-09-13 06:04:19Z
windows   Microsoft Windows 10 Enterprise
build     19041
host      Windows Sandbox on STARBASE
artifact  Tracks-and-Trails-0.1.0.dev0-setup.exe
size      92013635 bytes
sha256    5c5c3ec375adb2edd40b637a938e7a9ab736520cd6a61d6d3184dac80fcbc489
```

## Pre-install check

What must **not** be here. `REQ-029` and `REL-001` ask whether the artifact runs where
nothing is installed, so this is the half about the machine rather than the build.

**`ffmpeg` matters most.** `OPS-001` bundles it on Windows, so a machine that already had
one could not tell a bundled copy from a borrowed one.
```
absent   python
absent   python3
absent   py
absent   pip
absent   ffmpeg
absent   ffprobe
absent   yt-dlp
absent   cl
absent   gcc
absent   qmake6
absent   git
system Qt 6: none
```

## Install

Per-user, silent, no elevation (`NFR-004`, `T-322`). An elevation prompt here is a
finding, not a detail.

**Into a directory that already holds a file** (`T322-R1`). The uninstaller once deleted its
whole directory recursively; a sentinel placed there *before* installing has to survive the
uninstall byte-for-byte, which an empty default directory could never test.
```
sentinel      312b5a480d343ece... in the install directory
exit code     0
elapsed       20.5s
installed to  C:\Users\WDAGUtilityAccount\AppData\Local\Programs\Tracks & Trails
```

## What it placed

```
files         228
licenses/     present
ffmpeg.exe    present
start menu    %APPDATA%\Microsoft\Windows\Start Menu\Programs\Tracks & Trails\Tracks & Trails.lnk
desktop icon  absent, as the default asks
logged        227 destination(s) in the installer's own log
outside       none
```

## First launch

`--version` is not a launch test: it returns before a `QApplication` exists. This starts
the real application and waits for a window handle.
```
window        appeared after ~7.5s
title         Tracks & Trails
orphans       none
```

## A real download, over TLS, from a site whose root this machine does not hold

`REL-007`, amended from `T-327`. Python's `ssl` on Windows trusts only the roots already in
the store, and Windows fetches a missing one on demand for its own verifier alone -- so in this
Sandbox **every YouTube download failed** with `CERTIFICATE_VERIFY_FAILED`. The probe runs the
same `run_session` a worker runs.

**The root is checked first**, because a machine that already holds it would pass this whether
or not the fix is in the artifact.
```
GTS Root R1 in store  absent - this run can tell a fixed build from a broken one
probe exit            0
url             https://www.youtube.com/watch?v=jNQXAC9IVRw
format          bv*+ba/b
yt-dlp          2026.08.19 from bundled baseline
downloaded      Me at the zoo.webm, 474478 bytes in 4.6s
download        ok

preset probe exit     0
url             https://www.youtube.com/watch?v=aqz-KE-bpKQ
format          bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]
yt-dlp          2026.08.19 from bundled baseline
downloaded      Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film.mp4, 134886020 bytes in 12.6s
download        ok
```

## Uninstall, and what survives it

`T-039`'s fourth gate. `DAT-001` says settings, the job database and downloaded files
**survive an uninstall by intent** -- so this asserts separate things, and the distinction is
the point: a file the installer logged and left behind is a failure; the user's data, a file
the user saved into the install directory, and one that was there before, must all survive
byte-for-byte (`T322-R1`).
```
user data before  5 file(s) under %LOCALAPPDATA%\tracksandtrails
uninstall exit    0
installed files   all 226 removed
user file         pre-existing sentinel kept, unchanged
user file         user-saved file kept, unchanged
start menu        removed
user data after   5 file(s)
                  every file present and byte-identical, as DAT-001 intends
```

## Verdict

**PASS** - the pre-install check found nothing installed, the artifact installed per-user
without elevation, placed what it should, opened a window, and downloaded over TLS.

**Not covered here, and it is `OPS-004`'s:** whether the installer *feels* normal. A script
cannot answer that, which is why `T-318`'s Windows half keeps a human step.

**`T-039`'s four gates are the four sections above** - silent install, placement, launch,
and uninstall with user data preserved. Each fails this run rather than being reported and
passed over, which is the acceptance criterion it was written with.

<!-- VERDICT: PASS -->
<!-- RUN-COMPLETE -->
