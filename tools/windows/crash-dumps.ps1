<#
.SYNOPSIS
    Arm or disarm Windows Error Reporting local crash dumps on STARBASE (T-092).

.DESCRIPTION
    `T-074`'s second acceptance criterion is that the faulting thread and the object it touched are
    identified — **a stack is not a cause**. `faulthandler` cannot supply that: on the one recorded
    access violation it printed `[ResultPump]` and `Thread-50 (_monitor)` and named neither the
    faulting module nor the address. A minidump does.

    This configures WER to write a dump when *this project's interpreter* dies abnormally, so a
    recurrence leaves something a debugger can read instead of another anecdote.

    **This is machine configuration, not a workflow step.** `OPS-005` and `T-073` both carry the
    rule that a workflow must never provision STARBASE — it is the maintainer's own desktop. Run
    this by hand, once, having read what it costs below.

.PARAMETER Remove
    Undo the configuration. Leaves any dumps already written; delete those yourself.

.PARAMETER DumpFolder
    Where dumps go. Defaults to %LOCALAPPDATA%\CrashDumps\tracks-and-trails.

.PARAMETER DumpCount
    How many dumps to keep before Windows overwrites the oldest. Default 5.

.NOTES
    **Disk cost, stated.** `DumpType 2` is a *full* memory dump: a Python process with Qt loaded is
    roughly 300-600 MB, so five of them is up to ~3 GB. That is the price of naming the faulting
    object — a mini dump (`DumpType 1`) is a few MB and routinely lacks the heap the faulting
    address points into, which is the whole question here. `DumpCount` is the bound; lower it to 2
    if the disk is tight, and `-Remove` when the investigation is over.

    **Scoped to one executable**, not to every process on the machine. WER's per-application key
    means nothing else on STARBASE starts writing dumps because of this.
#>
[CmdletBinding()]
param(
    [switch]$Remove,
    [string]$DumpFolder = "$env:LOCALAPPDATA\CrashDumps\tracks-and-trails",
    [int]$DumpCount = 5
)

$ErrorActionPreference = 'Stop'

# The interpreter the suite runs under. Keyed by *file name* because that is what WER matches on;
# a venv's python.exe and the base install share it, which is what we want — the suite runs under
# whichever one the runner activated.
$Executable = 'python.exe'
$Key = "HKCU:\Software\Microsoft\Windows\Windows Error Reporting\LocalDumps\$Executable"

if ($Remove) {
    if (Test-Path $Key) {
        Remove-Item -Path $Key -Recurse -Force
        Write-Host "Removed $Key"
    }
    else {
        Write-Host "Nothing to remove: $Key does not exist"
    }
    Write-Host "Dumps already written are left in place. Delete them yourself if you want the disk back."
    return
}

New-Item -Path $DumpFolder -ItemType Directory -Force | Out-Null
New-Item -Path $Key -Force | Out-Null

# `ExpandString` so %LOCALAPPDATA% keeps working if the profile moves.
New-ItemProperty -Path $Key -Name 'DumpFolder' -Value $DumpFolder -PropertyType ExpandString -Force | Out-Null
New-ItemProperty -Path $Key -Name 'DumpCount'  -Value $DumpCount  -PropertyType DWord -Force | Out-Null
# 2 = full dump. See the disk cost note above; 1 (mini) omits the heap the faulting address needs.
New-ItemProperty -Path $Key -Name 'DumpType'   -Value 2           -PropertyType DWord -Force | Out-Null

Write-Host "Armed crash dumps for $Executable"
Write-Host "  folder: $DumpFolder"
Write-Host "  keep:   $DumpCount full dumps (up to roughly 3 GB)"
Write-Host ""
Write-Host "HKCU, so this applies to the current user only and needs no elevation."
Write-Host ""
Write-Host "Prove it before trusting it (T-092's first criterion — the keys are not the evidence):"
Write-Host '  python -c "import ctypes; ctypes.string_at(0)"'
Write-Host "Then check $DumpFolder for a .dmp file. If none appears, this task has failed at the"
Write-Host "thing it exists for and must say so rather than reporting the keys as success."
