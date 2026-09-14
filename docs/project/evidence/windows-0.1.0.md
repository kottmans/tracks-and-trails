# Clean-machine evidence - Windows - Sandbox

Taken by `packaging/windows-sandbox/evidence.ps1` inside Windows Sandbox, which is clean on
every launch by construction (`REL-006`). Nothing below was installed by this script except
the artifact itself.

## Machine

```
date      2026-09-14 19:16:38Z
windows   Microsoft Windows 10 Enterprise
build     19041
host      Windows Sandbox on STARBASE
artifact  Tracks-and-Trails-0.1.0-setup.exe
size      93470565 bytes
sha256    aafc574cacdab3493b1b67ffe271efed5065d8d399b9020e65e5b834b86082f7
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
sentinel      f1a09a5205b0727a... in the install directory
exit code     0
elapsed       20.6s
installed to  C:\Users\WDAGUtilityAccount\AppData\Local\Programs\Tracks & Trails
```

## What it placed

```
files         248
licenses/     present
ffmpeg.exe    present
start menu    %APPDATA%\Microsoft\Windows\Start Menu\Programs\Tracks & Trails\Tracks & Trails.lnk
desktop icon  absent, as the default asks
logged        247 destination(s) in the installer's own log
outside       none
```

## First launch

`--version` is not a launch test: it returns before a `QApplication` exists. This starts
the real application and waits for a window handle.
```
window        appeared after ~2.5s
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
downloaded      Me at the zoo.webm, 474478 bytes in 5.9s
download        ok

preset probe exit     0
url             https://www.youtube.com/watch?v=aqz-KE-bpKQ
format          bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]
yt-dlp          2026.08.19 from bundled baseline
downloaded      Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film.mp4, 134886020 bytes in 12.6s
download        ok
```

## Uninstall, and what survives it

`T-039`'s fourth gate. Settings, the job database and downloaded files **survive a silent
uninstall by intent** (an interactive one asks first, `T-322`) -- so this asserts separate
things, and the distinction is the point: a file the installer logged and left behind is a
failure; the user's data, a file
the user saved into the install directory, and one that was there before, must all survive
byte-for-byte (`T322-R1`).
```
user data before  5 file(s) under %LOCALAPPDATA%\tracksandtrails
uninstall exit    0
installed files   all 246 removed
user file         pre-existing sentinel kept, unchanged
user file         user-saved file kept, unchanged
start menu        removed
user data after   5 file(s)
                  every file present and byte-identical, as DAT-001 intends
```

## Removing settings while something still holds them

`T322-R3` and `T322-R4`, unattended. The dialog itself needs a person; what it leads to does
not. The installer is put back, and then: the uninstall entry Windows runs must be the one silent
run that asks; with the application open, a removal must be refused and remove nothing; with the
queue database held open, the removal must say it was incomplete, and still remove the rest.
```
uninstall entry   "C:\Users\WDAGUtilityAccount\AppData\Local\Programs\Tracks & Trails\unins000.exe" /SILENT /ASK
while running     exit 1; application kept; queue database kept
while locked      exit 0; logged incomplete: True; logged removed: False; settings removed: True; locked database still there: True
  log: 2026-09-14 14:18:09.525   Could not delete C:\Users\WDAGUtilityAccount\AppData\Local\tracksandtrails\library.sqlite3
  log: 2026-09-14 14:18:09.525   Settings and download queue: removal incomplete.
```

## An uninstall run by hand, with the removal switch and Inno's own box

`T322-R5`. `unins000.exe /REMOVEDATA`, run without `/ASK` or a silent flag, shows Inno's
confirmation, which says settings and the download queue are kept. It must keep them. The
confirmation is answered Yes by keystroke, and the final box closed the same way.
```
by hand           confirmed and uninstalled: True; settings kept: True; queue database kept: True; removal logged: False
  log: 2026-09-14 14:18:26.827   Removed all? Yes
  log: 2026-09-14 14:18:26.827   Need to restart Windows? No
  log: 2026-09-14 14:18:26.869   Message box (OK):
  log: Tracks & Trails was successfully removed from your computer.
  log: 2026-09-14 14:18:27.134   User chose OK.
  log: 2026-09-14 14:18:27.134   Log closed.
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
