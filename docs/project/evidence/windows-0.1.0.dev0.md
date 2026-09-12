# Clean-machine evidence - Windows - Sandbox

Taken by `packaging/windows-sandbox/evidence.ps1` inside Windows Sandbox, which is clean on
every launch by construction (`REL-006`). Nothing below was installed by this script except
the artifact itself.

## Machine

```
date      2026-09-12 19:36:56Z
windows   Microsoft Windows 10 Enterprise
build     19041
host      Windows Sandbox on STARBASE
artifact  Tracks-and-Trails-0.1.0.dev0-setup.exe
size      91776949 bytes
sha256    7528e12f3547a8b904b9247de745c24502e4d881c2e5a5b9ab9fb9552b56514b
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
```
exit code     0
elapsed       16.6s
installed to  C:\Users\WDAGUtilityAccount\AppData\Local\Programs\Tracks & Trails
```

## What it placed

```
files         225
licenses/     present
ffmpeg.exe    present
start menu    %APPDATA%\Microsoft\Windows\Start Menu\Programs\Tracks & Trails\Tracks & Trails.lnk
desktop icon  absent, as the default asks
```

## First launch

`--version` is not a launch test: it returns before a `QApplication` exists. This starts
the real application and waits for a window handle.
```
window        appeared after ~2s
title         Tracks & Trails
orphans       none
```

## Verdict

**PASS** - the pre-install check found nothing installed, the artifact installed per-user
without elevation, placed what it should, and opened a window.

**Not covered here, and it is `OPS-004`'s:** whether the installer *feels* normal. A script
cannot answer that, which is why `T-318`'s Windows half keeps a human step.

<!-- RUN-COMPLETE -->
