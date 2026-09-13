#!/usr/bin/env bash
# Take `T-318`/`T-039`'s Windows clean-machine evidence in Windows Sandbox on STARBASE, and fail
# unless it passed.
#
# **The failure contract** (`T039-R1`). `packaging/windows-sandbox/evidence.ps1` runs inside Sandbox
# as a logon command, where nothing observes its exit code, and writes a Markdown report whose last
# lines are `<!-- VERDICT: PASS|FAIL n -->` and `<!-- RUN-COMPLETE -->`. This script is what turns
# that into a result: it exits 0 only for a completed report whose verdict is PASS.
#
# Usage: tools/windows/sandbox_evidence.sh <report destination> [installer path on STARBASE]
#
# The installer defaults to the one `packaging/tracks-and-trails.iss` writes into `dist\`. It is
# copied into the share **under its own name**, and the harness installs whichever `*-setup.exe`
# it finds there, so any other installer in the share is removed first.
#
# **Refuses to run while any Sandbox is open**, because Windows allows one at a time and the
# maintainer's interactive session would otherwise be the one that got closed.
set -euo pipefail
HOST=${STARBASE_HOST:?set STARBASE_HOST to user@host for the Windows verification machine}
REPORT=${1:?give a local path for the report}
INSTALLER=${2:-'C:\dev\tracks-and-trails\dist\Tracks-and-Trails-0.1.0.dev0-setup.exe'}
SHARE='C:\dev\sandbox-share'
TIMEOUT=${SANDBOX_TIMEOUT:-1800}
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)

if ssh -o BatchMode=yes "$HOST" 'tasklist /FI "IMAGENAME eq WindowsSandbox.exe"' | grep -qi WindowsSandbox.exe; then
    echo "sandbox_evidence: a Windows Sandbox is already open on $HOST; close it first" >&2
    exit 3
fi

for file in evidence.ps1 clean-machine.wsb interactive.wsb; do
    scp -q -o BatchMode=yes "$ROOT/packaging/windows-sandbox/$file" "$HOST:C:/dev/sandbox-share/$file"
done
STARBASE_TIMEOUT=600 "$HERE/run-on-starbase.sh" "del /q $SHARE\\*-setup.exe $SHARE\\windows-clean-machine.md $SHARE\\install.log 2>nul & copy /Y \"$INSTALLER\" $SHARE\\ >nul && certutil -hashfile \"$INSTALLER\" SHA256 | findstr /v : && start \"\" $SHARE\\clean-machine.wsb && echo launched"

deadline=$(( $(date +%s) + TIMEOUT ))
until ssh -o BatchMode=yes "$HOST" "findstr /C:\"RUN-COMPLETE\" $SHARE\\windows-clean-machine.md" 2>/dev/null | grep -q RUN-COMPLETE; do
    if [ "$(date +%s)" -ge "$deadline" ]; then
        echo "sandbox_evidence: no completed report after ${TIMEOUT}s" >&2
        exit 2
    fi
    sleep 15
done

scp -q -o BatchMode=yes "$HOST:C:/dev/sandbox-share/windows-clean-machine.md" "$REPORT"
# Close the Sandbox this script opened, so the share is unlocked for whoever is next.
ssh -o BatchMode=yes "$HOST" 'taskkill /F /IM WindowsSandboxClient.exe >nul 2>&1 & taskkill /F /IM WindowsSandbox.exe >nul 2>&1 & echo closed' >/dev/null || true

verdict=$(grep -o '<!-- VERDICT: [^>]*-->' "$REPORT" | tail -1 || true)
echo "report: $REPORT"
echo "verdict: ${verdict:-none}"
case "$verdict" in
    '<!-- VERDICT: PASS -->') exit 0 ;;
    *) exit 1 ;;
esac
