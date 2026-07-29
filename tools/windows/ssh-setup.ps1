# STARBASE - enable OpenSSH Server and authorise the Fedora box's key.
# Run in an ELEVATED PowerShell. Safe to run more than once.
# Written in deliberately plain PowerShell: no statements inside string interpolation,
# which is what broke the previous version on Windows PowerShell 5.1.

Write-Host "== 1. OpenSSH Server =="
$cap = Get-WindowsCapability -Online -Name "OpenSSH.Server*" | Select-Object -First 1
if ($cap -eq $null) {
    Write-Warning "This Windows build offers no OpenSSH.Server capability."
} elseif ($cap.State -eq "Installed") {
    Write-Host "already installed"
} else {
    try {
        Add-WindowsCapability -Online -Name $cap.Name -ErrorAction Stop
        Write-Host "installed"
    } catch {
        Write-Warning "Add-WindowsCapability failed:"
        Write-Warning $_.Exception.Message
        Write-Warning "Usually policy blocking Features on Demand (0x800f0954)."
        Write-Warning "Fallback A: Settings > System > Optional features > Add > OpenSSH Server"
        Write-Warning "Fallback B: winget install --id Microsoft.OpenSSH.Beta -e"
    }
}

Write-Host "== 2. service =="
$svc = Get-Service sshd -ErrorAction SilentlyContinue
if ($svc -eq $null) {
    Write-Warning "sshd does not exist yet - step 1 did not complete."
} else {
    Set-Service -Name sshd -StartupType Automatic
    Start-Service sshd
    Write-Host "sshd started"
}

Write-Host "== 3. authorised key =="
$source = "\\tsclient\linux\id_ed25519.pub"
$sshDir = Join-Path $env:ProgramData "ssh"
$target = Join-Path $sshDir "administrators_authorized_keys"
if (Test-Path $source) {
    if (-not (Test-Path $sshDir)) {
        New-Item -ItemType Directory -Path $sshDir -Force | Out-Null
    }
    $key = (Get-Content $source -Raw).Trim()
    # **Append, never replace** (`WIN-R1`). This wrote the file outright, so running it a second
    # time - or on a machine an administrator already had a key on - silently revoked every other
    # key. Losing your own access to a machine you are configuring remotely is a bad way to find
    # that out.
    $existing = @()
    if (Test-Path $target) {
        $existing = @(Get-Content $target | Where-Object { $_.Trim() -ne "" })
    }
    if ($existing -contains $key) {
        Write-Host "key already authorised"
    } else {
        Set-Content -Path $target -Value (@($existing) + $key) -Encoding ascii
    }
    # sshd REFUSES this file if any account outside Administrators/SYSTEM can write it, and the
    # refusal is silent - it falls back to password auth. These ACLs are load-bearing.
    icacls $target /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F" | Out-Null
    Write-Host "key written to $target"
} else {
    Write-Warning "$source not found."
    Write-Warning "Reconnect RDP with: /drive:linux,/home/sean/starbase-share"
}

Write-Host "== 4. firewall =="
# **Scoped to the local network** (`WIN-R1`). `-Profile` defaults to Any, so the first version
# opened port 22 on public networks too - on a laptop, that is every coffee shop. Private plus
# LocalSubnet matches what this is for: reaching the machine from the same LAN.
$intendedProfile = "Private"
$intendedRemote = "LocalSubnet"

$rule = Get-NetFirewallRule -Name sshd-tt -ErrorAction SilentlyContinue
if ($rule -eq $null) {
    New-NetFirewallRule -Name sshd-tt -DisplayName "OpenSSH Server (Tracks and Trails)" `
        -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 `
        -Profile $intendedProfile -RemoteAddress $intendedRemote | Out-Null
    Write-Host "rule created"
} else {
    # **Reapply the scope, do not just note the rule exists** (`WIN-R1`, second half). This branch
    # used to do nothing at all and then print "rule present" - so a machine that had already run
    # the earlier broad `Any` version kept port 22 open on every network profile, on every
    # subsequent run, while the script reported success. A tool documented as safe to re-run has
    # to be able to repair the state it created, not just decline to make it worse.
    Set-NetFirewallRule -Name sshd-tt -Enabled True -Direction Inbound -Protocol TCP `
        -Action Allow -LocalPort 22 -Profile $intendedProfile -RemoteAddress $intendedRemote
    Write-Host "rule existed - reapplied the intended scope"
}

# Read the rule back and report what is actually in force. The scope lives on two different
# objects - the profile on the rule, the remote address on an associated filter - so a rule that
# looks right in `Get-NetFirewallRule` alone can still allow the world.
$rule = Get-NetFirewallRule -Name sshd-tt -ErrorAction SilentlyContinue
if ($rule -eq $null) {
    Write-Warning "the rule is absent after configuring it - the commands above did not take"
} else {
    $addressFilter = Get-NetFirewallAddressFilter -AssociatedNetFirewallRule $rule
    $portFilter = Get-NetFirewallPortFilter -AssociatedNetFirewallRule $rule
    $effectiveProfile = $rule.Profile.ToString()
    $effectiveRemote = ($addressFilter.RemoteAddress -join ", ")
    $effectivePort = ($portFilter.LocalPort -join ", ")
    $effectiveEnabled = $rule.Enabled.ToString()
    $effectiveAction = $rule.Action.ToString()

    Write-Host "rule enabled : $effectiveEnabled"
    Write-Host "rule action  : $effectiveAction"
    Write-Host "rule profile : $effectiveProfile"
    Write-Host "rule remote  : $effectiveRemote"
    Write-Host "rule port    : $effectivePort"

    if ($effectiveProfile -ne $intendedProfile) {
        Write-Warning "profile is '$effectiveProfile', expected '$intendedProfile'"
        Write-Warning "Remove it and re-run: Remove-NetFirewallRule -Name sshd-tt"
    }
    if ($effectiveRemote -ne $intendedRemote) {
        Write-Warning "remote address is '$effectiveRemote', expected '$intendedRemote'"
        Write-Warning "Remove it and re-run: Remove-NetFirewallRule -Name sshd-tt"
    }
}

$sessionId = (Get-Process -Id $PID).SessionId
$state = "not installed"
$svc2 = Get-Service sshd -ErrorAction SilentlyContinue
if ($svc2 -ne $null) {
    $state = $svc2.Status
}

Write-Host ""
Write-Host "== report =="
Write-Host "user    : $env:USERNAME"
Write-Host "session : $sessionId   (must be non-zero)"
Write-Host "sshd    : $state"
Write-Host "python  :"
python --version
Write-Host "git     :"
git --version
