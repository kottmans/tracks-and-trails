#!/usr/bin/env bash
# T-302: does anything orphan workers on a developer's machine, now that CI cannot?
#
# `Linux orphans` scanned a persistent runner nightly and stopped on 2026-09-08 when Linux CI
# moved to ephemeral hosted VMs. T-302 asks where orphans accumulate instead. The working
# assumption is a developer's own machine, and this samples that assumption rather than restating
# it: run the parts of the suite that spawn real workers, scan after each, and record every result
# with the run that preceded it.
#
#   nohup tools/t302_orphan_accumulation_sampler.sh <hours> > /dev/null 2>&1 &
#
# **The known positive runs first, and a failure there stops the whole thing.** A scanner that
# cannot see a deliberately orphaned worker prints the same clean zero as a machine with none, and
# a night of those would be evidence of nothing. `2026-08-29-orphan-scan-known-positive-soak.md`
# is the precedent this follows.
#
# Reads and reports only. It runs the project's own suite and scanner; it kills nothing, writes no
# task or review record, and commits nothing.
set -uo pipefail

HOURS="${1:-8}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="${ROOT}/../t302-orphan-sampling-$(date +%Y%m%d-%H%M%S).log"
cd "$ROOT" || exit 1

say() { printf '%s  %s\n' "$(date -Is)" "$*" >> "$LOG"; }

say "T-302 orphan accumulation sampling, ${HOURS}h, on $(hostname)"
say "repo head: $(git rev-parse --short HEAD)  tree: $(git status --porcelain | wc -l) modified"

say "--- known positive: can the scanner see a deliberate orphan? ---"
if python -m pytest -q tests/unit/test_orphan_scan.py::test_the_scanner_sees_a_known_orphan \
      >> "$LOG" 2>&1; then
  say "known positive PASSED — a clean scan below means something"
else
  say "known positive FAILED — stopping; every scan after this would be an unreadable silence"
  exit 1
fi

say "--- baseline, before any suite run ---"
python tools/orphan_scan.py --minimum-age-seconds 0 >> "$LOG" 2>&1
say "baseline exit: $?"

deadline=$(( $(date +%s) + HOURS * 3600 ))
round=0
while [ "$(date +%s)" -lt "$deadline" ]; do
  round=$(( round + 1 ))
  say "=== round ${round}: the suites that spawn real workers ==="
  # Integration and UI are where a worker process is actually started; unit tests are not.
  timeout 2400 python -m pytest -q tests/integration tests/ui -n auto >> "$LOG" 2>&1
  say "round ${round} suite exit: $?"

  # Immediately, and then after the default age threshold, because a worker still shutting down
  # is not an orphan and the difference between the two scans is the interesting part.
  say "--- scan, immediately after the run (age 0) ---"
  python tools/orphan_scan.py --minimum-age-seconds 0 >> "$LOG" 2>&1
  say "immediate scan exit: $?"
  sleep 90
  say "--- scan, 90s later at the default threshold ---"
  python tools/orphan_scan.py >> "$LOG" 2>&1
  say "settled scan exit: $?"
  say "python processes now: $(pgrep -c -f 'python' || echo 0)"
  sleep 600
done

say "=== sampling finished after ${round} rounds ==="
say "read with: grep -E 'orphan|round|scan exit|known positive' '${LOG}'"
