#!/usr/bin/env python3
"""Run one pytest node id N times and report how often it fails, for a suspected flake.

`tools/soak.sh` is this project's instrument for the *whole suite* dying (`T-128`, `OPS-007`).
This is the narrow one: a single node id, run many times, when a test has passed and failed on
**the same tree** and the question is whether that is a flake and at what rate.

It exists because `tests/unit/test_orphan_scan.py::test_the_scanner_sees_a_known_orphan` failed on
the `windows desktop` job at `0332a68` and passed at `75cd183`, whose trees differ by a YAML
comment and a status file. One observation is not a rate, and *"seen once"* is not something a
task entry can be written against.

**Its lessons are `soak.sh`'s, and they are not decoration:**

- **Say which tree it measured** (`T-148`). A soak that reports a number and not a commit does not
  say what the number is about. A dirty tree is recorded as dirty rather than rounded to the SHA.
- **Say which machine.** A timing-dependent result does not transfer between hosts, and this
  project runs three.
- **A crash is not a failure.** `pytest` exiting 139, or dying with a `Fatal Python error`, is a
  different finding from an assertion that did not hold, and collapsing them hides whichever is
  rarer.
- **The instrument reports; it does not judge.** Exit status is 0 whenever the soak *ran*, whatever
  the tests did, because a soak that fails its own job when it finds something cannot be put in a
  workflow that is supposed to report the finding.

    tools/soak_a_test.py <node-id> [--runs N] [--out DIR] [--jobs 1]

Runs are serial by default and deliberately: the test this was written for spawns and reaps real
processes, and `AGENTS.md` §9 lists that family as the one that contends with itself.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Outcome:
    """What one run did."""

    index: int
    returncode: int
    seconds: float
    verdict: str


def _head() -> str:
    """The commit measured, marked dirty when the tree is not the commit (`T-148`)."""
    git = shutil.which("git")
    if git is None:
        return "unknown"
    try:
        sha = subprocess.run(  # noqa: S603
            [git, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(  # noqa: S603
            [git, "status", "--porcelain"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except OSError, subprocess.CalledProcessError:
        return "unknown"
    return f"{sha}+dirty" if dirty else sha


def _verdict(returncode: int, output: str) -> str:
    """`passed`, `failed`, or `crashed` — three answers, because they have three causes.

    A negative return code is a signal, and `Fatal Python error` reaches stdout when the
    interpreter dies without one. pytest's own exit codes are small positives.
    """
    if returncode == 0:
        return "passed"
    if returncode < 0 or returncode >= 128 or "Fatal Python error" in output:
        return "crashed"
    return "failed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("node_id", help="the pytest node id to soak")
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--out", type=Path, default=Path("reports/soak"))
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    header = {
        "node_id": args.node_id,
        "runs": args.runs,
        "head": _head(),
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    for key, value in header.items():
        print(f"soak: {key}: {value}", flush=True)

    outcomes: list[Outcome] = []
    for index in range(1, args.runs + 1):
        began = time.monotonic()
        # S603: the "untrusted input" is the node id the operator typed, and running it is the
        # entire purpose of this tool. `sys.executable` is already an absolute path.
        done = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "pytest", "-q", args.node_id],
            capture_output=True,
            text=True,
        )
        elapsed = time.monotonic() - began
        combined = done.stdout + done.stderr
        verdict = _verdict(done.returncode, combined)
        outcomes.append(Outcome(index, done.returncode, round(elapsed, 2), verdict))
        # **Every run's log is kept, not only the failures.** Comparing a failure against a pass
        # from the same machine and minute is most of diagnosing a flake, and the passes are gone
        # by the time you know you wanted them.
        (args.out / f"run-{index:03d}-{verdict}.txt").write_text(combined, encoding="utf-8")
        print(f"soak: run {index}/{args.runs}: {verdict} ({elapsed:.1f}s)", flush=True)

    counts = {
        v: sum(1 for o in outcomes if o.verdict == v) for v in ("passed", "failed", "crashed")
    }
    summary = {
        **header,
        "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "counts": counts,
        "failure_rate": round((counts["failed"] + counts["crashed"]) / max(args.runs, 1), 4),
        "outcomes": [asdict(o) for o in outcomes],
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(
        f"soak: {counts['passed']} passed, {counts['failed']} failed, "
        f"{counts['crashed']} crashed out of {args.runs}",
        flush=True,
    )
    # **Zero whatever the tests did.** The finding is the report, not the exit status; see the
    # module docstring. A soak that cannot run at all still raises.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
