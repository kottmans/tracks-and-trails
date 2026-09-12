#!/usr/bin/env bash
# The clean-machine evidence run (`T-318`), taken **on** the machine that has nothing.
#
# `REL-006` chose disposable VMs the maintainer owns. The maintainer then narrowed that on
# 2026-09-11 — *"I don't really want to use VMs for testing the packages. I'd rather just test the
# app image on my own machine and test the windows installer on starbase"* — so the Linux clean
# machine is a throwaway container and the Windows half is `STARBASE`, by hand, against
# `docs/project/evidence/TEMPLATE-windows.md`.
#
# Run it through `tools/clean_machine_linux.sh`, which supplies the container. Run directly, it
# assumes it is already standing on something disposable.
#
#   tools/clean_machine_linux.sh dist/Tracks_and_Trails-0.1.0.dev0-x86_64.AppImage
#
# **The pre-install check is the first thing and it can fail the run** (`T-318`'s first acceptance
# criterion): evidence taken on a machine that turns out to have had Python on it is not evidence,
# and finding that out afterwards is too late. Its output is retained in full rather than reduced
# to a verdict, because *"no Python"* is a claim and `command -v python3` is the fact.
set -uo pipefail

ARTIFACT=${1:?usage: clean_machine_evidence.sh <artifact>}
RUN_AS=${RUN_AS:-$ARTIFACT}
failures=0

rule() { printf '\n## %s\n\n' "$1"; }

rule "Machine"
echo '```'
echo "date          $(date -u '+%Y-%m-%d %H:%M:%SZ')"
echo "artifact      $(basename "$ARTIFACT")"
echo "size          $(stat -c %s "$ARTIFACT" 2>/dev/null || echo unknown) bytes"
echo "sha256        $(sha256sum "$ARTIFACT" 2>/dev/null | cut -d' ' -f1)"
echo "kernel        $(uname -srm)"
echo "distribution  $(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME")"
echo "glibc         $(ldd --version 2>/dev/null | head -1)"
echo '```'

rule "Pre-install check"
cat <<'WHY'
What must **not** be here. `REQ-029` and `REL-001` ask whether the artifact runs where nothing is
installed, so this is the half of the question that is about the machine rather than the build.
A `PRESENT` line below invalidates everything after it.
WHY
echo '```'
for tool in python3 python pip3 pip gcc cc g++ make qmake6 qmake ffmpeg ffprobe yt-dlp; do
    if location=$(command -v "$tool" 2>/dev/null); then
        echo "PRESENT  $tool -> $location"
        failures=$((failures + 1))
    else
        echo "absent   $tool"
    fi
done
qt_count=$(ldconfig -p 2>/dev/null | grep -ci "libQt6" || true)
echo "system Qt 6 libraries: $qt_count"
[ "$qt_count" -eq 0 ] || failures=$((failures + 1))
echo '```'

cat <<'WHY'

**Two things are deliberately installed, and neither is Python, Qt or a toolchain.**

- `libgl1` / `libegl1` — an AppImage must not ship the graphics stack, because it has to match
  the user's driver. A bare container has none at all, which no real desktop lacks.
- `ca-certificates` — the system trust store. **The artifact carries no CA bundle of its own**,
  measured: without this package every HTTPS request fails with `CERTIFICATE_VERIFY_FAILED`
  (`T321-R1`). Every desktop distribution ships it, so this is a boundary of the model rather
  than a defect, and it is recorded here rather than quietly satisfied.
WHY

rule "The artifact"

probe() {
    local label=$1 flag=$2 seconds=${3:-300}
    printf '### %s\n\n```\n' "$label"
    # `timeout` so a hung probe is a reported failure rather than a run that never ends.
    timeout "$seconds" $RUN_AS "$flag" 2>&1 | tail -12
    local code=${PIPESTATUS[0]}
    printf '\nexit %s\n```\n\n' "$code"
    [ "$code" -eq 0 ] || failures=$((failures + 1))
}

probe "Version" --version 60
probe "Process model (T-020)" --spawn-probe 180
probe "Bundled yt-dlp (T-033)" --ytdlp-probe 180
probe "Database (T-014)" --database-probe 180
probe "In-app update path (T-198)" --ytdlp-update-probe 300
probe "One real download (TESTING §8 item 8)" --download-probe 900

rule "A window, on a machine with no Qt"
cat <<'WHY'
`--version` is **not** a launch test: it returns before a `QApplication` exists, which is how a
build with no platform plugins at all passed every check here on 2026-09-11. This starts the real
application offscreen and gives it time to fail.
WHY
echo '```'
QT_QPA_PLATFORM=offscreen timeout 25 $RUN_AS >/tmp/launch.log 2>&1 &
launcher=$!
sleep 20
if kill -0 "$launcher" 2>/dev/null; then
    echo "still running after 20s — a QApplication came up and stayed up"
    kill "$launcher" 2>/dev/null
    wait "$launcher" 2>/dev/null
else
    echo "FAIL: the application exited on its own before 20s"
    failures=$((failures + 1))
fi
echo "--- anything it wrote ---"
grep -iE "qt\.|error|fatal|abort|plugin|traceback" /tmp/launch.log | head -10 || echo "(nothing)"
echo '```'

rule "Verdict"
if [ "$failures" -eq 0 ]; then
    echo "**PASS** — the pre-install check found nothing installed, and every probe above exited 0."
else
    echo "**FAIL** — $failures check(s) did not pass. The detail is above; nothing here is a summary."
fi
exit "$failures"
