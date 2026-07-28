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

# Refuse to start on top of a run still in flight. Its redirect holds job.out open, so this
# one's output would be lost and its result unreadable (`WIN-R2`).
if ssh -o BatchMode=yes "$HOST" 'if exist C:\dev\interactive\job.running (echo busy)' 2>/dev/null | grep -q busy; then
    echo "run-on-starbase: a run is already in flight on $HOST; wait for it or clear job.running" >&2
    exit 126
fi

printf '@echo off\r\n%s\r\n' "$1" > "$WORK/job.cmd"
scp -q -o BatchMode=yes "$WORK/job.cmd" "$HOST:C:/dev/interactive/job.cmd"
ssh -o BatchMode=yes "$HOST" 'del C:\dev\interactive\job.done C:\dev\interactive\job.out 2>nul & schtasks /run /tn ttjob >nul & echo started' >/dev/null

# `WIN-R2`: this used to `break` out of the wait and fall through to printing the output, so a
# timeout exited 0 — a hung command was indistinguishable from a successful one. It now exits
# non-zero, and so does a command that failed on the far side.
deadline=$(( $(date +%s) + TIMEOUT ))
timed_out=0
until ssh -o BatchMode=yes "$HOST" 'if exist C:\dev\interactive\job.done (echo yes) else (echo no)' 2>/dev/null | grep -q yes; do
    if [ "$(date +%s)" -gt "$deadline" ]; then
        echo "run-on-starbase: TIMED OUT after ${TIMEOUT}s; partial output follows" >&2
        timed_out=1
        break
    fi
    sleep 5
done

output=$(ssh -o BatchMode=yes "$HOST" 'type C:\dev\interactive\job.out' 2>/dev/null | sed 's/\r$//')
printf '%s\n' "$output"

if [ "$timed_out" -eq 1 ]; then
    exit 124
fi

# `run.cmd` appends EXITCODE=<n> as its last line. Propagating it is what makes this wrapper
# usable in a conditional at all: without it every remote failure looked like a success, which
# is the same defect class as a mutation driver that treats any non-zero exit as a kill.
code=$(printf '%s\n' "$output" | sed -n 's/^EXITCODE=\([0-9][0-9]*\)$/\1/p' | tail -1)
if [ -z "$code" ]; then
    echo "run-on-starbase: no EXITCODE line; the remote command did not report a result" >&2
    exit 125
fi
exit "$code"
