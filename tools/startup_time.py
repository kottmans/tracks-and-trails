"""Time a built artifact from launch to interactive window (`T-325`, `NFR-002`).

    python3 tools/startup_time.py dist/Tracks_and_Trails-0.1.0.dev0-x86_64.AppImage --runs 5

**Not a stopwatch**, which `T-325` asks for in terms. The launcher takes wall clock before
spawning; the application writes its own wall clock when the compositor says the window is on
screen (`_freeze_probe.record_first_paint`, riding the exposure watch `T287-R1` installed). The
delta between two clocks on one machine is what a user experiences, and neither end is a human
reacting to a screen.

**Five runs, median reported, every run retained.** `NFR-002` is a single number and an average
hides the run that did not meet it — `T-259`'s rule about bounds applies to the measurement as
much as to the gate.

**Warm and cold are different measurements and this tool does one of them.** It launches
repeatedly on a machine that has already paged the artifact in, which is *warm*. A cold number
needs a reboot — and on Linux additionally `echo 3 > /proc/sys/vm/drop_caches`, which needs root
— so it is the maintainer's to take. This prints which it measured rather than letting a reader
assume.
"""

from __future__ import annotations

import argparse
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

#: How long one launch may take before it is a failure rather than a slow start.
LAUNCH_TIMEOUT = 60.0

#: How often the launcher looks for the timestamp file. Small enough not to be the measurement's
#: resolution: the number being measured is seconds, and the file is written once.
POLL = 0.01


def one_launch(command: list[str], environment: dict[str, str]) -> tuple[float, str]:
    """Launch once and return the seconds to first paint, or a reason it did not happen."""
    with tempfile.TemporaryDirectory(prefix="tt-startup-") as workspace:
        marker = Path(workspace) / "first-paint.txt"
        running = {**environment, "TT_STARTUP_REPORT": str(marker)}
        started = time.time()
        # `S603`: the command is the artifact this tool was pointed at, by a maintainer running
        # it. No shell, and nothing here is assembled from anything a user supplied.
        process = subprocess.Popen(  # noqa: S603
            command, env=running, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        try:
            deadline = started + LAUNCH_TIMEOUT
            while time.time() < deadline:
                if marker.exists():
                    text = marker.read_text(encoding="utf-8").strip()
                    _, _, stamp = text.partition(" ")
                    return float(stamp) - started, ""
                if process.poll() is not None:
                    _, errors = process.communicate()
                    reason = (errors or b"").decode("utf-8", "ignore").strip().splitlines()
                    last = reason[-1] if reason else "(no output)"
                    return 0.0, f"exited {process.returncode}: {last}"
                time.sleep(POLL)
            return 0.0, f"no window after {LAUNCH_TIMEOUT:.0f}s"
        finally:
            # **Taken down between runs**, or the second launch meets the single-instance lock
            # (`A-004`) and exits — which would read as a fast start.
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:  # pragma: no cover - a hung GUI
                process.kill()
                process.wait(timeout=10)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Time an artifact's launch to first paint.")
    parser.add_argument("artifact", help="the built artifact to launch")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--bound", type=float, default=3.0, help="NFR-002's number, in seconds")
    parser.add_argument(
        "--extra", action="append", default=[], help="an extra argument for the artifact"
    )
    parser.add_argument(
        "--cold",
        action="store_true",
        help="label this run cold: the caller has just rebooted, and only the caller can know",
    )
    arguments = parser.parse_args(argv)

    command = [arguments.artifact, *arguments.extra]
    # A per-run profile, so the measurement is not of a machine that already has the user's
    # settings, geometry and database — and so it does not touch them (`TESTING` §5).
    with tempfile.TemporaryDirectory(prefix="tt-startup-profile-") as profile:
        environment = {
            **os.environ,
            "XDG_CONFIG_HOME": f"{profile}/config",
            "XDG_DATA_HOME": f"{profile}/data",
            "XDG_CACHE_HOME": f"{profile}/cache",
            "WIN_PD_OVERRIDE_APPDATA": f"{profile}/appdata",
            "WIN_PD_OVERRIDE_LOCAL_APPDATA": f"{profile}/local",
        }
        print(f"artifact  {arguments.artifact}")
        # **The tool cannot tell cold from warm and must not claim to.** It said *"measuring warm
        # launches"* unconditionally, and then printed that over a run taken seconds after a
        # reboot — which was the cold number `T-325` had been waiting for, mislabelled by its own
        # harness. Only the caller knows what state the machine is in, so the caller says.
        if arguments.cold:
            print("labelled COLD by the caller: first launch after a reboot")
        else:
            print("warm unless --cold was passed; a cold number needs a reboot (T-325)")
        print(f"bound     {arguments.bound}s (NFR-002)")

        timings: list[float] = []
        for run in range(1, arguments.runs + 1):
            seconds, complaint = one_launch(command, environment)
            if complaint:
                print(f"  run {run}  FAILED  {complaint}", file=sys.stderr)
                return 1
            timings.append(seconds)
            print(f"  run {run}  {seconds:.3f}s")

    median = statistics.median(timings)
    kind = "cold" if arguments.cold else "warm"
    print(f"\n{kind} median    {median:.3f}s over {len(timings)} runs")
    print(f"slowest   {max(timings):.3f}s")
    print(f"fastest   {min(timings):.3f}s")
    if median > arguments.bound:
        print(
            f"\nOVER THE BOUND: {median:.3f}s against NFR-002's {arguments.bound}s. That is a "
            f"task, not a re-measure (T-325).",
            file=sys.stderr,
        )
        return 1
    print(f"\nwithin NFR-002's {arguments.bound}s")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through `main`
    raise SystemExit(main())
