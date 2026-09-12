# Clean-machine evidence — Windows — `<version>`

> Copy to `windows-<version>.md`, fill every box, and **paste real output**. A table saying a
> thing passed is a claim about evidence; the output is the evidence (`T329-R3`).

**Why this half is by hand.** `REL-006` chose disposable VMs; the maintainer narrowed that on
2026-09-11 to *"test the app image on my own machine and test the windows installer on
starbase"*. The Linux half is therefore a container and scripted
(`tools/clean_machine_linux.sh`); this half is a person at `STARBASE` with Windows Sandbox,
which is clean on every launch by design.

**Windows Sandbox and not `STARBASE` itself.** `STARBASE` has Python, a toolchain and a
developer's yt-dlp on it — it is where the installer is *driven from*, not the clean machine.
Sandbox gives a fresh Windows on every launch and discards it on close.

## Machine

```
date          <UTC>
artifact      <installer filename>
size          <bytes>
sha256        <digest, from the same file that was installed>
windows       <winver output>
host          STARBASE / Windows Sandbox
```

## Pre-install check

Run **before** the installer, in the Sandbox, and paste the whole thing. A `PRESENT` line
invalidates everything below it.

```powershell
foreach ($t in 'python','python3','py','pip','ffmpeg','ffprobe','yt-dlp','cl','gcc','qmake6') {
    $found = Get-Command $t -ErrorAction SilentlyContinue
    if ($found) { "PRESENT  $t -> $($found.Source)" } else { "absent   $t" }
}
"Qt 6 DLLs on the system: " + @(Get-ChildItem -Path C:\ -Filter 'Qt6Core.dll' -Recurse -ErrorAction SilentlyContinue).Count
```

```
<paste>
```

**ffmpeg must be absent and stay absent.** `OPS-001` bundles it on Windows, so a Sandbox with
ffmpeg on `PATH` cannot tell a bundled copy from a borrowed one — which is the whole question.

## Install

```
<paste the installer run: the elevation prompt or its absence, the install location, any
SmartScreen click-through (REL-005), and where the shortcuts landed>
```

`T-322` installs per-user with no admin prompt. **An elevation prompt here is a finding**, not a
detail.

## First launch

```
<paste: does the window appear, in how long, and does anything appear behind it>
```

## One real download

The same file the Linux half and `tests/network/test_real_download.py` use, so a difference is
the artifact rather than the site:

`https://archive.org/download/BigBuckBunny_124/Content/big_buck_bunny_720p_surround.mp4`

```
<paste: the queue row reaching COMPLETED, the output path, and the file's size on disk>
```

**Driven through the window, not through `--download-probe`.** The probe is how the *Linux*
half gets this without a display; here there is a desktop, so the GUI path is exercised and this
is `TESTING` §8 item 8 in full — including *cancel another*, which the probe cannot do.

## Cancel another

```
<paste: a second download started and cancelled, and that no yt-dlp or ffmpeg process survives —
Get-Process yt-dlp,ffmpeg -ErrorAction SilentlyContinue after the cancel>
```

## Exit

```
<paste: the application closes, and nothing is left running>
```

## Verdict

**<PASS / FAIL>** — <one line. If FAIL, what failed and which task carries it.>
