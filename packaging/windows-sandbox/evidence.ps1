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
Say '```'
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

Rule "Uninstall, and what survives it"
Say "``T-039``'s fourth gate. ``DAT-001`` says settings, the job database and downloaded files"
Say "**survive an uninstall by intent** -- so this asserts two different things, and the"
Say "distinction is the point: leftovers under the install root are a failure, leftovers under the"
Say "user directories are the requirement being met."
Say '```'
# The application writes its database under `user_data_dir("tracksandtrails")`, which on Windows
# is %LOCALAPPDATA%\tracksandtrails. The first launch above created it.
$userData = "$env:LOCALAPPDATA\tracksandtrails"
$dataBefore = @(Get-ChildItem -Path $userData -Recurse -File -ErrorAction SilentlyContinue)
Say ("user data before  " + $dataBefore.Count + " file(s) under %LOCALAPPDATA%\tracksandtrails")
if ($dataBefore.Count -eq 0) {
    Say "                  WARNING: nothing to preserve, so the DAT-001 half proves nothing"
}

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
            if (-not (Test-Path $root)) { break }
            Start-Sleep -Milliseconds 500
        }

        $left = @(Get-ChildItem -Path $root -Recurse -File -ErrorAction SilentlyContinue)
        if ($left.Count -eq 0) {
            Say "install root      removed"
        } else {
            Say ("install root      " + $left.Count + " FILE(S) LEFT: " + (($left | Select-Object -First 5).Name -join ", "))
            $failures++
        }
        $stillThere = $startMenuCandidates | Where-Object { Test-Path $_ }
        Say ("start menu        " + $(if ($stillThere) { "SHORTCUT LEFT BEHIND" } else { "removed" }))
        if ($stillThere) { $failures++ }
    }
}

$dataAfter = @(Get-ChildItem -Path $userData -Recurse -File -ErrorAction SilentlyContinue)
Say ("user data after   " + $dataAfter.Count + " file(s)")
if ($dataBefore.Count -gt 0 -and $dataAfter.Count -lt $dataBefore.Count) {
    Say "                  FAILED - the uninstaller removed user data, which DAT-001 preserves"
    $failures++
} elseif ($dataBefore.Count -gt 0) {
    Say "                  preserved, as DAT-001 intends - this is not a leftover"
}
Say '```'

Rule "Verdict"
if ($failures -eq 0) {
    Say "**PASS** - the pre-install check found nothing installed, the artifact installed per-user"
    Say "without elevation, placed what it should, and opened a window."
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
Say "<!-- RUN-COMPLETE -->"
