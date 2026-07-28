#!/usr/bin/env bash
# Run a command in STARBASE's logged-on desktop session and print its output.
#
# SSH lands in session 0, which has no window station. Qt degrades there without failing:
# the offscreen plugin falls back to a font database that wants a font directory, and the
# real `windows` plugin cannot set DPI awareness. Results collected over SSH are therefore
# not results about the machine.
#
# This writes the command to job.cmd, triggers the pre-registered `ttjob` scheduled task
# (created with /IT, so it inherits the interactive session), waits for the done marker, and
# prints what the command wrote.
#
# Usage: run-on-starbase.sh 'cd C:\dev\tracks-and-trails && .venv\Scripts\python.exe -m pytest -q'
set -euo pipefail

HOST=${STARBASE_HOST:-Admin@192.168.68.65}
TIMEOUT=${STARBASE_TIMEOUT:-1800}
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

printf '@echo off\r\n%s\r\n' "$1" > "$WORK/job.cmd"
scp -q -o BatchMode=yes "$WORK/job.cmd" "$HOST:C:/dev/interactive/job.cmd"
ssh -o BatchMode=yes "$HOST" 'del C:\dev\interactive\job.done C:\dev\interactive\job.out 2>nul & schtasks /run /tn ttjob >nul & echo started' >/dev/null

deadline=$(( $(date +%s) + TIMEOUT ))
until ssh -o BatchMode=yes "$HOST" 'if exist C:\dev\interactive\job.done (echo yes) else (echo no)' 2>/dev/null | grep -q yes; do
    if [ "$(date +%s)" -gt "$deadline" ]; then
        echo "TIMED OUT after ${TIMEOUT}s; partial output follows" >&2
        break
    fi
    sleep 5
done
ssh -o BatchMode=yes "$HOST" 'type C:\dev\interactive\job.out' 2>/dev/null | sed 's/\r$//'
