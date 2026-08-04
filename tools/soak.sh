#!/usr/bin/env bash
# Run the full suite N times and report how many died, for `T-128` / `OPS-007`.
#
# This is the instrument that found the segfault (2 in 39, 2026-08-04) and it is the one that has
# to show it gone. `OPS-007`'s 2026-08-04 ruling sets the bar at **60 clean runs**: against the
# measured 5.1% baseline, a clean sixty has probability 0.042 if nothing changed, so it puts the
# "nothing changed" reading below 5%. Thirty-nine only gets to 0.128, which is why the original
# soak's own size is not enough to clear it.
#
# A crash here is a *process* death, not a test failure — `pytest` exits 139 and prints a
# `Fatal Python error`. Both are recorded: a run that fails tests is a different problem from a run
# that dies, and collapsing them would hide whichever is rarer.
#
#   tools/soak.sh 60 [output-directory]
#
# Cores are kept by systemd on this machine, so a death is inspectable afterwards with
# `coredumpctl list` — no `ulimit` change is needed. See `ai/TASKS.md` T-128.

set -uo pipefail

RUNS="${1:-60}"
OUT="${2:-$(mktemp -d -t soak-XXXXXX)}"
mkdir -p "$OUT"

echo "soak: $RUNS runs, logs in $OUT"
echo "soak: started $(date -Is)"

crashed=0
failed=0
passed=0

for i in $(seq 1 "$RUNS"); do
    log="$OUT/run-$(printf '%03d' "$i").log"
    QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q -p no:randomly >"$log" 2>&1
    code=$?
    case "$code" in
        0) passed=$((passed + 1)); verdict="pass" ;;
        1) failed=$((failed + 1));  verdict="TEST FAILURE" ;;
        *) crashed=$((crashed + 1)); verdict="PROCESS DIED (exit $code)" ;;
    esac
    printf 'run %3d/%s: %-26s %s\n' "$i" "$RUNS" "$verdict" "$(tail -1 "$log" | cut -c1-60)"
    # Keep only the interesting logs: sixty green runs of 2000 tests is a lot of disk for nothing.
    [ "$code" -eq 0 ] && rm -f "$log"
done

echo "soak: finished $(date -Is)"
echo "soak: $passed passed, $failed with test failures, $crashed process deaths, out of $RUNS"
if [ "$crashed" -gt 0 ] || [ "$failed" -gt 0 ]; then
    echo "soak: logs for the runs that did not pass are in $OUT"
    exit 1
fi
echo "soak: clean. Against the 2-in-39 baseline, P(this | rate unchanged) is 0.042 at 60 runs."
