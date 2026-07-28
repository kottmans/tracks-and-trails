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
    $key = Get-Content $source
    Set-Content -Path $target -Value $key -Encoding ascii
    # sshd REFUSES this file if any account outside Administrators/SYSTEM can write it, and the
    # refusal is silent - it falls back to password auth. These ACLs are load-bearing.
    icacls $target /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F" | Out-Null
    Write-Host "key written to $target"
} else {
    Write-Warning "$source not found."
    Write-Warning "Reconnect RDP with: /drive:linux,/home/sean/starbase-share"
}

Write-Host "== 4. firewall =="
$rule = Get-NetFirewallRule -Name sshd-tt -ErrorAction SilentlyContinue
if ($rule -eq $null) {
    New-NetFirewallRule -Name sshd-tt -DisplayName "OpenSSH Server (Tracks and Trails)" -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 | Out-Null
}
Write-Host "rule present"

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
