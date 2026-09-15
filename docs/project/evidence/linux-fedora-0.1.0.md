
## Machine

```
date          2026-09-14 23:31:21Z
artifact      Tracks_and_Trails-0.1.0-x86_64.AppImage
size          68286968 bytes
sha256        ad859def982df6075433ffc2b56c683f9905f3cc53a399cb0516224a0034330a
kernel        Linux 7.1.13-200.fc44.x86_64 x86_64  (the host's, if this is a container)
distribution  Fedora Linux 44 (Container Image)
glibc         ldd (GNU libc) 2.43
```

## Pre-install check

What must **not** be here. `REQ-029` and `REL-001` ask whether the artifact runs where nothing is
installed, so this is the half of the question that is about the machine rather than the build.
A `PRESENT` line below invalidates everything after it.
```
absent   python3
absent   python
absent   pip3
absent   pip
absent   gcc
absent   cc
absent   g++
absent   make
absent   qmake6
absent   qmake
absent   ffmpeg
absent   ffprobe
absent   yt-dlp
system Qt 6 libraries: 0
```

**Two things are deliberately installed, and neither is Python, Qt or a toolchain.**

- the GL and EGL libraries (`libgl1` / `libegl1`, or `mesa-libGL` / `mesa-libEGL` on Fedora) —
  an AppImage must not ship the graphics stack, because it has to match
  the user's driver. A bare container has none at all, which no real desktop lacks.
- `ca-certificates` — the system trust store. **The artifact carries no CA bundle of its own**,
  measured: without this package every HTTPS request fails with `CERTIFICATE_VERIFY_FAILED`
  (`T321-R1`). Every desktop distribution ships it, so this is a boundary of the model rather
  than a defect, and it is recorded here rather than quietly satisfied.

## The artifact

### Version

```
0.1.0

exit 0
```

### Process model (T-020)

```
frozen           True
parent pid       59
child pid        61
child frozen     True
message          worker-alive
child exitcode   0
OK: spawned a child from this build, exchanged one message, and reaped it

exit 0
```

### Bundled yt-dlp (T-033)

```
ytdlp version   2026.08.19
ytdlp source    bundled baseline
ytdlp pin       2026.8.19
extractors      1751
resolved        youtube from yt_dlp.extractor.youtube
solver          yt.solver.core.js v0.8.0, hash verified
solver extras   2 also present: yt.solver.bun.lib.js, yt.solver.deno.lib.js
OK: the frozen artifact carries a usable yt-dlp with its extractors

exit 0
```

### Database (T-014)

```
migrations      12
schema version  12
database        ok

exit 0
```

### In-app update path (T-198)

```
before install  2026.08.19 — bundled baseline
installed       9000.1.1
after install   9000.1.1 — user-managed copy (OPS-002)
after revert    2026.08.19 — bundled baseline
OK: install, resolve in a child, and revert all work in the frozen artifact

exit 0
```

### One real download (TESTING §8 item 8)

```
url             https://archive.org/download/BigBuckBunny_124/Content/big_buck_bunny_720p_surround.mp4
format          bv*+ba/b
yt-dlp          2026.08.19 from bundled baseline
downloaded      big_buck_bunny_720p_surround.mp4, 61878609 bytes in 6.7s
download        ok

exit 0
```


## A window, on a machine with no Qt

`--version` is **not** a launch test: it returns before a `QApplication` exists, which is how a
build with no platform plugins at all passed every check here on 2026-09-11. This starts the real
application offscreen and gives it time to fail.
```
still running after 20s — a QApplication came up and stayed up
--- anything it wrote ---
Fontconfig error: Cannot load default config file: No such file: (null)
This plugin does not support propagateSizeHints()
```

## Verdict

**PASS** — the pre-install check found nothing installed, and every probe above exited 0.
