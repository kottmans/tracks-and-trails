# The Windows clean-machine evidence run (`T-318`), executed INSIDE Windows Sandbox.
#
# `REL-006` chose a disposable machine the maintainer owns; the maintainer narrowed that to
# Windows Sandbox on `STARBASE`. Sandbox is clean on every launch by construction and discarded on
# close, which is the property the decision was made for.
#
# **Driven by `clean-machine.wsb`'s LogonCommand, not by hand.** `T-318` originally made this half
# a template a human filled in, because the Linux half's probes have no Windows equivalent. Most
# of it turned out to be scriptable after all: Sandbox runs a logon command and a mapped folder
# carries the result back. What stays human is the `OPS-004` judgement -- whether the installer
# *feels* normal -- which no script can answer.
#
# Writes everything to the mapped folder. Nothing here is retained on the sandbox, which ceases to
# exist when the window closes.

$ErrorActionPreference = "Continue"
$share = "C:\Users\WDAGUtilityAccount\Desktop\share"
$report = Join-Path $share "windows-clean-machine.md"
$failures = 0

function Say($text) { Add-Content -Path $report -Value $text -Encoding utf8 }
function Rule($title) { Say ""; Say "## $title"; Say "" }

Set-Content -Path $report -Value "# Clean-machine evidence - Windows - Sandbox" -Encoding utf8
Say ""
Say "Taken by ``packaging/windows-sandbox/evidence.ps1`` inside Windows Sandbox, which is clean on"
Say "every launch by construction (``REL-006``). Nothing below was installed by this script except"
Say "the artifact itself."

Rule "Machine"
Say '```'
Say ("date      " + (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ssZ"))
Say ("windows   " + (Get-CimInstance Win32_OperatingSystem).Caption)
Say ("build     " + (Get-CimInstance Win32_OperatingSystem).BuildNumber)
Say ("host      Windows Sandbox on STARBASE")
$setup = Get-ChildItem -Path $share -Filter *-setup.exe | Select-Object -First 1
if ($setup) {
    Say ("artifact  " + $setup.Name)
    Say ("size      " + $setup.Length + " bytes")
    Say ("sha256    " + (Get-FileHash $setup.FullName -Algorithm SHA256).Hash.ToLower())
} else {
    Say "artifact  MISSING - nothing to install"
    $failures++
}
Say '```'

Rule "Pre-install check"
Say "What must **not** be here. ``REQ-029`` and ``REL-001`` ask whether the artifact runs where"
Say "nothing is installed, so this is the half about the machine rather than the build."
Say ""
Say "**``ffmpeg`` matters most.** ``OPS-001`` bundles it on Windows, so a machine that already had"
Say "one could not tell a bundled copy from a borrowed one."
Say '```'
foreach ($tool in @("python","python3","py","pip","ffmpeg","ffprobe","yt-dlp","cl","gcc","qmake6","git")) {
    $found = Get-Command $tool -ErrorAction SilentlyContinue
    if ($found) { Say ("PRESENT  " + $tool + " -> " + $found.Source); $script:failures++ }
    else { Say ("absent   " + $tool) }
}
# **Targeted, not a recursive walk of C:\.** The first version scanned the whole drive and the
# run simply stopped there -- twenty-five minutes with no further output, because
# `Get-ChildItem -Recurse` over a fresh Windows image is not a check, it is a crawl. A system-wide
# Qt would be in one of these or on PATH; nowhere else makes it loadable by an unrelated process.
$qtPlaces = @(
    "$env:WINDIR\System32\Qt6Core.dll",
    "$env:WINDIR\SysWOW64\Qt6Core.dll",
    "$env:PROGRAMFILES\Qt",
    "${env:PROGRAMFILES(X86)}\Qt",
    "$env:LOCALAPPDATA\Qt"
)
$qt = @($qtPlaces | Where-Object { Test-Path $_ })
$onPath = @($env:PATH -split ";" | Where-Object { $_ -and (Test-Path (Join-Path $_ "Qt6Core.dll") -ErrorAction SilentlyContinue) })
Say ("system Qt 6: " + $(if ($qt.Count + $onPath.Count -eq 0) { "none" } else { ($qt + $onPath) -join ", " }))
if ($qt.Count + $onPath.Count -gt 0) { $failures++ }
Say '```'

Rule "Install"
Say "Per-user, silent, no elevation (``NFR-004``, ``T-322``). An elevation prompt here is a"
Say "finding, not a detail."
Say ""
Say "**Into a directory that already holds a file** (``T322-R1``). The uninstaller once deleted its"
Say "whole directory recursively; a sentinel placed there *before* installing has to survive the"
Say "uninstall byte-for-byte, which an empty default directory could never test."
Say '```'
$installRoot = "$env:LOCALAPPDATA\Programs\Tracks & Trails"
function Fingerprint($path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower() }
New-Item -ItemType Directory -Force -Path $installRoot | Out-Null
$sentinel = Join-Path $installRoot "was-here-before-install.txt"
Set-Content -LiteralPath $sentinel -Value ("placed before install " + [guid]::NewGuid()) -Encoding utf8
$sentinelHash = Fingerprint $sentinel
Say ("sentinel      " + $sentinelHash.Substring(0, 16) + "... in the install directory")
if ($setup) {
    $started = Get-Date
    $run = Start-Process -FilePath $setup.FullName `
        -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART","/LOG=C:\Users\WDAGUtilityAccount\Desktop\share\install.log" `
        -Wait -PassThru
    Say ("exit code     " + $run.ExitCode)
    Say ("elapsed       " + [math]::Round(((Get-Date) - $started).TotalSeconds, 1) + "s")
    if ($run.ExitCode -ne 0) { $failures++ }
} else { Say "skipped - no installer" }
$installed = "$env:LOCALAPPDATA\Programs\Tracks & Trails\tracks-and-trails.exe"
$alt = "$env:PROGRAMFILES\Tracks & Trails\tracks-and-trails.exe"
if (Test-Path $installed) { $exe = $installed } elseif (Test-Path $alt) { $exe = $alt } else { $exe = $null }
Say ("installed to  " + $(if ($exe) { Split-Path $exe -Parent } else { "NOT FOUND" }))
if (-not $exe) { $failures++ }
Say '```'

Rule "What it placed"
Say '```'
if ($exe) {
    $root = Split-Path $exe -Parent
    Say ("files         " + @(Get-ChildItem $root -Recurse -File).Count)
    Say ("licenses/     " + $(if (Test-Path (Join-Path $root "_internal\licenses")) { "present" } else { "MISSING - LIC-001" }))
    if (-not (Test-Path (Join-Path $root "_internal\licenses"))) { $failures++ }
    Say ("ffmpeg.exe    " + $(if (Test-Path (Join-Path $root "_internal\ffmpeg.exe")) { "present" } else { "MISSING - OPS-001" }))
    if (-not (Test-Path (Join-Path $root "_internal\ffmpeg.exe"))) { $failures++ }
}
# **`DefaultGroupName` puts it in a folder of that name**, so the shortcut is one level deeper
# than the obvious path. The first version looked directly under `Programs\` and reported
# MISSING for an installer that had placed it correctly -- and then **passed anyway**, because
# nothing incremented the failure count. A check that reports a problem and does not fail is the
# defect this project keeps finding; both halves are fixed.
$startMenuCandidates = @(
    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Tracks & Trails\Tracks & Trails.lnk",
    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Tracks & Trails.lnk"
)
$startMenu = $startMenuCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($startMenu) {
    Say ("start menu    " + $startMenu.Replace($env:APPDATA, "%APPDATA%"))
} else {
    Say "start menu    MISSING - T-322 places one unconditionally"
    $failures++
}
$desktop = "$env:USERPROFILE\Desktop\Tracks & Trails.lnk"
Say ("desktop icon  " + $(if (Test-Path $desktop) { "PRESENT - should be opt-in and unchecked" } else { "absent, as the default asks" }))
if (Test-Path $desktop) { $failures++ }
# **Every destination the installer logged, not a few named files** (`T039-R1`). A payload file
# written anywhere else -- a stray `[Files]` entry to Documents, say -- passed the checks above,
# which only asked whether the expected things were present.
$installLog = "C:\Users\WDAGUtilityAccount\Desktop\share\install.log"
$startMenuRoot = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Tracks & Trails"
$logged = @()
if (Test-Path $installLog) {
    $logged = @(Get-Content -LiteralPath $installLog | ForEach-Object {
        if ($_ -match "Dest filename: (.+)$") { $Matches[1].Trim() }
    })
}
$outside = @($logged | Where-Object {
    -not ($_.StartsWith($installRoot + "\", "OrdinalIgnoreCase") -or $_.StartsWith($startMenuRoot + "\", "OrdinalIgnoreCase"))
})
Say ("logged        " + $logged.Count + " destination(s) in the installer's own log")
if ($logged.Count -eq 0) { Say "              FAILED - no install log to judge placement from"; $failures++ }
if ($outside.Count -gt 0) {
    Say ("outside       " + $outside.Count + " WRITTEN OUTSIDE the install root and Start Menu: " + (($outside | Select-Object -First 3) -join "; "))
    $failures++
} else { Say "outside       none" }
Say '```'

Rule "First launch"
Say "``--version`` is not a launch test: it returns before a ``QApplication`` exists. This starts"
Say "the real application and waits for a window handle."
Say '```'
if ($exe) {
    $app = Start-Process -FilePath $exe -PassThru
    $window = 0
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        $live = Get-Process -Id $app.Id -ErrorAction SilentlyContinue
        if (-not $live) { break }
        if ($live.MainWindowHandle -ne 0) { $window = $live.MainWindowHandle; break }
    }
    if ($window -ne 0) {
        Say ("window        appeared after ~" + [math]::Round($i * 0.5, 1) + "s")
        Say ("title         " + (Get-Process -Id $app.Id).MainWindowTitle)
    } else {
        Say "window        NEVER APPEARED"
        $failures++
    }
    Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    $orphans = @(Get-Process -Name "tracks-and-trails","ffmpeg","ffprobe" -ErrorAction SilentlyContinue)
    Say ("orphans       " + $(if ($orphans.Count -eq 0) { "none" } else { "LEFT RUNNING: " + ($orphans.Name -join ", ") }))
    if ($orphans.Count -ne 0) { $failures++ }
}
Say '```'

Rule "A real download, over TLS, from a site whose root this machine does not hold"
Say "``REL-007``, amended from ``T-327``. Python's ``ssl`` on Windows trusts only the roots already in"
Say "the store, and Windows fetches a missing one on demand for its own verifier alone -- so in this"
Say "Sandbox **every YouTube download failed** with ``CERTIFICATE_VERIFY_FAILED``. The probe runs the"
Say "same ``run_session`` a worker runs."
Say ""
Say "**The root is checked first**, because a machine that already holds it would pass this whether"
Say "or not the fix is in the artifact."
Say '```'
$probeUrl = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
# A longer video for the preset run, because a 19-second clip's streams come in one request and
# `T-332`'s 403 arrived partway into a stream. Blender's *Big Buck Bunny*, 1080p MP4 available.
$presetVideo = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
$rootHeld = @(Get-ChildItem Cert:\LocalMachine\Root, Cert:\CurrentUser\Root -ErrorAction SilentlyContinue | Where-Object Subject -match "GTS Root R1")
Say ("GTS Root R1 in store  " + $(if ($rootHeld.Count -eq 0) { "absent - this run can tell a fixed build from a broken one" } else { "PRESENT - this run cannot show the fix; the result below proves nothing about it" }))
if ($exe) {
    $probeReport = Join-Path $env:TEMP "tt-download-probe.txt"
    Remove-Item $probeReport -ErrorAction SilentlyContinue
    $env:TT_PROBE_REPORT = $probeReport
    # The release build is windowed and has no stdout, so the probe's lines come back through
    # `TT_PROBE_REPORT` (`T-319`).
    $probe = Start-Process -FilePath $exe -ArgumentList ("--download-probe=" + $probeUrl) -Wait -PassThru
    Remove-Item Env:\TT_PROBE_REPORT
    Say ("probe exit            " + $probe.ExitCode)
    if (Test-Path $probeReport) { Get-Content $probeReport | ForEach-Object { Say $_ } }
    else { Say "probe report          MISSING - the probe wrote nothing" }
    if ($probe.ExitCode -ne 0) { $failures++ }

    # **Again in a user's preset** (`T-332`). The probe's own selector asks for separate streams,
    # which the bundled yt-dlp 2026.7.4 could fetch while it 403'd the 1080p MP4 preset's -- so a
    # probe-only run passed the build that failed the maintainer's first real download. This line
    # must stay the preset's own selector; `tests/unit/test_windows_packaging.py` compares them.
    $presetFormat = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]"
    Say ""
    Remove-Item $probeReport -ErrorAction SilentlyContinue
    $env:TT_PROBE_REPORT = $probeReport
    $env:TT_DOWNLOAD_PROBE_FORMAT = $presetFormat
    $preset = Start-Process -FilePath $exe -ArgumentList ("--download-probe=" + $presetVideo) -Wait -PassThru
    Remove-Item Env:\TT_PROBE_REPORT
    Remove-Item Env:\TT_DOWNLOAD_PROBE_FORMAT
    Say ("preset probe exit     " + $preset.ExitCode)
    if (Test-Path $probeReport) { Get-Content $probeReport | ForEach-Object { Say $_ } }
    else { Say "preset probe report   MISSING - the probe wrote nothing" }
    if ($preset.ExitCode -ne 0) { $failures++ }
}
Say '```'

Rule "Uninstall, and what survives it"
Say "``T-039``'s fourth gate. Settings, the job database and downloaded files **survive a silent"
Say "uninstall by intent** (an interactive one asks first, ``T-322``) -- so this asserts separate"
Say "things, and the distinction is the point: a file the installer logged and left behind is a"
Say "failure; the user's data, a file"
Say "the user saved into the install directory, and one that was there before, must all survive"
Say "byte-for-byte (``T322-R1``)."
Say '```'
# The application writes its database under `user_data_dir("tracksandtrails")`, which on Windows
# is %LOCALAPPDATA%\tracksandtrails. The first launch above created it.
#
# **Fingerprinted, not counted** (`T039-R1`). Five files before and five after accepted a database
# replaced or corrupted by the uninstall; each file's content hash is compared instead.
$userData = "$env:LOCALAPPDATA\tracksandtrails"
$dataBefore = @{}
Get-ChildItem -Path $userData -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
    $dataBefore[$_.FullName] = Fingerprint $_.FullName
}
Say ("user data before  " + $dataBefore.Count + " file(s) under %LOCALAPPDATA%\tracksandtrails")
if ($dataBefore.Count -eq 0) {
    # A warning used to go here. Launching and downloading create the database, so an empty
    # directory means the preservation half has nothing to prove -- which is a failed check.
    Say "                  FAILED - nothing to preserve, so the DAT-001 half cannot be judged"
    $failures++
}
# **A file the user saved into the install directory** (`T322-R1`), beside the sentinel that was
# there before installing. Both are the user's, and both must outlive the uninstaller.
$userFile = Join-Path $installRoot "my-saved-video.mp4"
$bytes = New-Object byte[] 65536
(New-Object System.Random).NextBytes($bytes)
[System.IO.File]::WriteAllBytes($userFile, $bytes)
$userFileHash = Fingerprint $userFile
$installedFiles = @($logged | Where-Object { $_.StartsWith($installRoot + "\", "OrdinalIgnoreCase") })

if ($exe) {
    $root = Split-Path $exe -Parent
    $uninstaller = Get-ChildItem -Path $root -Filter "unins*.exe" | Select-Object -First 1
    if (-not $uninstaller) {
        Say "uninstaller       MISSING - nothing to run"
        $failures++
    } else {
        $u = Start-Process -FilePath $uninstaller.FullName `
            -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART" -Wait -PassThru
        Say ("uninstall exit    " + $u.ExitCode)
        if ($u.ExitCode -ne 0) { $failures++ }
        # Inno's uninstaller returns before it has finished removing itself.
        for ($i = 0; $i -lt 60; $i++) {
            if (-not (Test-Path (Join-Path $root "unins000.exe"))) { break }
            Start-Sleep -Milliseconds 500
        }

        # **Leftovers are judged against what the installer said it installed**, not against an
        # empty directory: the user's own files there are meant to stay.
        $installedLeft = @($installedFiles | Where-Object { Test-Path -LiteralPath $_ })
        if ($installedLeft.Count -eq 0) {
            Say ("installed files   all " + $installedFiles.Count + " removed")
        } else {
            Say ("installed files   " + $installedLeft.Count + " LEFT: " + (($installedLeft | Select-Object -First 5 | ForEach-Object { Split-Path $_ -Leaf }) -join ", "))
            $failures++
        }
        foreach ($kept in @(@{ Path = $sentinel; Hash = $sentinelHash; Name = "pre-existing sentinel" },
                            @{ Path = $userFile; Hash = $userFileHash; Name = "user-saved file" })) {
            if (-not (Test-Path -LiteralPath $kept.Path)) {
                Say ("user file         " + $kept.Name + " DELETED by the uninstaller - T322-R1")
                $failures++
            } elseif ((Fingerprint $kept.Path) -ne $kept.Hash) {
                Say ("user file         " + $kept.Name + " CHANGED by the uninstaller")
                $failures++
            } else {
                Say ("user file         " + $kept.Name + " kept, unchanged")
            }
        }
        $strays = @(Get-ChildItem -Path $root -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
            $_.FullName -ne $sentinel -and $_.FullName -ne $userFile
        })
        if ($strays.Count -gt 0) {
            Say ("install root      " + $strays.Count + " OTHER FILE(S) LEFT: " + (($strays | Select-Object -First 5).Name -join ", "))
            $failures++
        }
        $stillThere = $startMenuCandidates | Where-Object { Test-Path $_ }
        Say ("start menu        " + $(if ($stillThere) { "SHORTCUT LEFT BEHIND" } else { "removed" }))
        if ($stillThere) { $failures++ }
    }
}

$changed = @($dataBefore.Keys | Where-Object {
    -not (Test-Path -LiteralPath $_) -or (Fingerprint $_) -ne $dataBefore[$_]
})
Say ("user data after   " + @(Get-ChildItem -Path $userData -Recurse -File -ErrorAction SilentlyContinue).Count + " file(s)")
if ($changed.Count -gt 0) {
    Say ("                  FAILED - " + $changed.Count + " removed or changed by the uninstaller, which DAT-001 preserves: " + (($changed | Select-Object -First 3 | ForEach-Object { Split-Path $_ -Leaf }) -join ", "))
    $failures++
} elseif ($dataBefore.Count -gt 0) {
    Say "                  every file present and byte-identical, as DAT-001 intends"
}
Say '```'

Rule "Removing settings while something still holds them"
Say "``T322-R3`` and ``T322-R4``, unattended. The dialog itself needs a person; what it leads to does"
Say "not. The installer is put back, and then: the uninstall entry Windows runs must be the one silent"
Say "run that asks; with the application open, a removal must be refused and remove nothing; with the"
Say "queue database held open, the removal must say it was incomplete, and still remove the rest."
Say '```'
if ($setup) {
    $re = Start-Process -FilePath $setup.FullName -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART" -Wait -PassThru
    if ($re.ExitCode -ne 0 -or -not (Test-Path $installed)) {
        Say ("reinstall         FAILED, exit " + $re.ExitCode)
        $failures++
    } else {
        $root = Split-Path $installed -Parent
        $un = (Get-ChildItem -Path $root -Filter "unins*.exe" | Select-Object -First 1).FullName
        $entry = Get-ItemProperty -LiteralPath "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{8F3C4A21-6D5E-4B7A-9C12-3E8D5A7B1F40}_is1" -ErrorAction SilentlyContinue
        $command = if ($entry) { [string]$entry.UninstallString } else { "" }
        Say ("uninstall entry   " + $command)
        if (-not $command.EndsWith("/SILENT /ASK")) {
            Say "                  FAILED - Windows would not start the single dialog (T322-R4)"
            $failures++
        }

        # (a) The application is running: Inno's AppMutex check must stop the uninstall.
        $app = Start-Process -FilePath $installed -PassThru
        for ($i = 0; $i -lt 60; $i++) {
            Start-Sleep -Milliseconds 500
            $live = Get-Process -Id $app.Id -ErrorAction SilentlyContinue
            if (-not $live -or $live.MainWindowHandle -ne 0) { break }
        }
        $database = Join-Path $userData "library.sqlite3"
        $runningLog = Join-Path $env:TEMP "uninstall-while-running.log"
        $u1 = Start-Process -FilePath $un -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART","/REMOVEDATA",("/LOG=" + $runningLog) -Wait -PassThru
        Start-Sleep -Seconds 3
        $appKept = Test-Path $installed
        $databaseKept = Test-Path $database
        Say ("while running     exit " + $u1.ExitCode + "; application " + $(if ($appKept) { "kept" } else { "REMOVED" }) + "; queue database " + $(if ($databaseKept) { "kept" } else { "REMOVED" }))
        if (-not $appKept -or -not $databaseKept) {
            Say "                  FAILED - an open application did not stop the removal (T322-R3)"
            $failures++
        }
        Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2

        # (b) Something holds the queue database: the removal must say it is incomplete.
        $settingsFile = Join-Path $userData "settings.toml"
        Set-Content -LiteralPath $settingsFile -Value "[queue]`nconcurrency = 2" -Encoding utf8
        $held = [System.IO.File]::Open($database, 'Open', 'ReadWrite', 'None')
        $lockedLog = Join-Path $env:TEMP "uninstall-while-locked.log"
        try {
            $u2 = Start-Process -FilePath $un -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART","/REMOVEDATA",("/LOG=" + $lockedLog) -Wait -PassThru
            for ($i = 0; $i -lt 60; $i++) {
                if (-not (Test-Path (Join-Path $root "unins000.exe"))) { break }
                Start-Sleep -Milliseconds 500
            }
        } finally {
            $held.Close()
        }
        $incomplete = [bool](Select-String -LiteralPath $lockedLog -SimpleMatch "removal incomplete" -Quiet)
        $claimed = [bool](Select-String -LiteralPath $lockedLog -SimpleMatch "Settings and download queue removed." -Quiet)
        $settingsGone = -not (Test-Path $settingsFile)
        $databaseKept = Test-Path $database
        Say ("while locked      exit " + $u2.ExitCode + "; logged incomplete: " + $incomplete + "; logged removed: " + $claimed + "; settings removed: " + $settingsGone + "; locked database still there: " + $databaseKept)
        if (-not $incomplete -or $claimed -or -not $settingsGone -or -not $databaseKept) {
            Say "                  FAILED - a removal that could not finish was not reported as incomplete (T322-R3)"
            $failures++
        }
        foreach ($line in @(Select-String -LiteralPath $lockedLog -Pattern "Could not delete|removal incomplete|removed\." -ErrorAction SilentlyContinue | Select-Object -First 4)) {
            Say ("  log: " + $line.Line.Trim())
        }
    }
} else { Say "skipped - no installer" }
Say '```'

Rule "An uninstall run by hand, with the removal switch and Inno's own box"
Say "``T322-R5``. ``unins000.exe /REMOVEDATA``, run without ``/ASK`` or a silent flag, shows Inno's"
Say "confirmation, which says settings and the download queue are kept. It must keep them. The"
Say "confirmation is answered Yes by keystroke, and the final box closed the same way."
Say '```'
if ($setup) {
    $re = Start-Process -FilePath $setup.FullName -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART" -Wait -PassThru
    if ($re.ExitCode -ne 0 -or -not (Test-Path $installed)) {
        Say ("reinstall         FAILED, exit " + $re.ExitCode)
        $failures++
    } else {
        $root = Split-Path $installed -Parent
        $un = (Get-ChildItem -Path $root -Filter "unins*.exe" | Select-Object -First 1).FullName
        $settingsFile = Join-Path $userData "settings.toml"
        Set-Content -LiteralPath $settingsFile -Value "[queue]`nconcurrency = 2" -Encoding utf8
        $handLog = Join-Path $env:TEMP "uninstall-by-hand.log"
        $hand = Start-Process -FilePath $un -ArgumentList "/REMOVEDATA",("/LOG=" + $handLog) -PassThru
        $shell = New-Object -ComObject WScript.Shell
        $answered = $false
        $finished = $false
        for ($i = 0; $i -lt 240; $i++) {
            Start-Sleep -Milliseconds 500
            $focused = $shell.AppActivate("Uninstall")
            if (-not $answered) {
                # Yes on the confirmation. Enter would take its default, which is No.
                if ($focused) { $shell.SendKeys("y") }
                if (-not (Test-Path $installed)) { $answered = $true }
            } elseif ($focused) {
                # The final "was removed" box.
                $shell.SendKeys("{ENTER}")
            }
            # **Finished means Inno says so**, not that the application's files are gone: the data
            # step runs after the files, and a check made in between saw nothing either way.
            if ($answered -and (Test-Path $handLog) -and
                [bool](Select-String -LiteralPath $handLog -Pattern "Log closed|Uninstall process exited|exit code" -Quiet) -and
                -not (Test-Path (Join-Path $root "unins000.exe"))) {
                $finished = $true
                Start-Sleep -Seconds 3
                break
            }
        }
        Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "unins*" -or $_.Name -like "_iu*" } | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        $claimed = (Test-Path $handLog) -and [bool](Select-String -LiteralPath $handLog -SimpleMatch "Settings and download queue removed." -Quiet)
        $attempted = (Test-Path $handLog) -and [bool](Select-String -LiteralPath $handLog -SimpleMatch "removal incomplete" -Quiet)
        $settingsKept = Test-Path $settingsFile
        $databaseKept = Test-Path (Join-Path $userData "library.sqlite3")
        Say ("by hand           confirmed and uninstalled: " + $answered + "; settings kept: " + $settingsKept + "; queue database kept: " + $databaseKept + "; removal logged: " + ($claimed -or $attempted))
        foreach ($line in @(Get-Content -LiteralPath $handLog -Tail 6 -ErrorAction SilentlyContinue)) {
            Say ("  log: " + $line.Trim())
        }
        if (-not $answered -or -not $finished) {
            Say ("                  NOT EXERCISED - confirmed: " + $answered + ", finished: " + $finished + "; nothing is shown either way")
            $failures++
        } elseif (-not $settingsKept -or -not $databaseKept -or $claimed -or $attempted) {
            Say "                  FAILED - the box promised to keep them, and they were removed (T322-R5)"
            $failures++
        }
    }
} else { Say "skipped - no installer" }
Say '```'

Rule "Verdict"
if ($failures -eq 0) {
    Say "**PASS** - the pre-install check found nothing installed, the artifact installed per-user"
    Say "without elevation, placed what it should, opened a window, and downloaded over TLS."
} else {
    Say ("**FAIL** - " + $failures + " check(s) did not pass. The detail is above; nothing here is a summary.")
}
Say ""
Say "**Not covered here, and it is ``OPS-004``'s:** whether the installer *feels* normal. A script"
Say "cannot answer that, which is why ``T-318``'s Windows half keeps a human step."
Say ""
Say "**``T-039``'s four gates are the four sections above** - silent install, placement, launch,"
Say "and uninstall with user data preserved. Each fails this run rather than being reported and"
Say "passed over, which is the acceptance criterion it was written with."

Say ""
# **The failure contract** (`T039-R1`). A Markdown verdict is for a person; this line is what
# `tools/windows/sandbox_evidence.sh` reads, and it exits non-zero unless it says PASS. The exit
# code below is for anything that runs this script directly.
Say ("<!-- VERDICT: " + $(if ($failures -eq 0) { "PASS" } else { "FAIL " + $failures }) + " -->")
Say "<!-- RUN-COMPLETE -->"
exit $(if ($failures -eq 0) { 0 } else { 1 })
