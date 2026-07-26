"""Runs the frozen artifact and asserts the `ARC-002` process model survived freezing (`T-020`).

Invoked by CI after the PyInstaller build, and runnable by hand:

    python packaging/frozen_smoke.py dist/tracks-and-trails

Answers one question — does spawning a child from a frozen binary work, or does it relaunch
the application? — and answers it with evidence rather than an exit code alone. On failure it
prints the probe log, whose `argv` column names the exact mechanism: a relaunched child shows
`--multiprocessing-fork`, which is multiprocessing's internal invocation being executed as the
whole application because `freeze_support()` did not intercept it.

Deliberately not a pytest test. It runs against a build artifact that only exists after a
packaging step, on a machine that may have no checkout on `sys.path`, and CI needs it to fail
the job on its own.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

BINARY_STEM = "tracks-and-trails"
PROBE_TIMEOUT = 300


def binary_path(dist_dir: Path) -> Path:
    name = BINARY_STEM + (".exe" if os.name == "nt" else "")
    candidate = dist_dir / name
    if not candidate.is_file():
        raise SystemExit(f"no frozen binary at {candidate}")
    return candidate


def running_instances(binary: Path) -> list[int]:
    """PIDs of any live process running this binary — the orphan check.

    Matches on the executable path rather than the process name: a relaunched child carries
    the same name as its parent, and on Windows the name alone would also match an unrelated
    installed copy.
    """
    target = str(binary.resolve()).casefold()
    found = []
    for process in psutil.process_iter(["pid", "exe"]):
        try:
            exe = process.info["exe"]
            if exe and str(Path(exe).resolve()).casefold() == target:
                found.append(process.info["pid"])
        except psutil.NoSuchProcess, psutil.AccessDenied, OSError:
            continue
    return found


def run(
    binary: Path, args: list[str], probe_log: Path | None = None
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if probe_log is not None:
        env["TT_PROBE_LOG"] = str(probe_log)
    # S603: the "untrusted input" is a path this script located inside the build output and
    # a fixed argument list. No shell, no user data. Running the artifact is the entire point.
    return subprocess.run(  # noqa: S603
        [str(binary), *args],
        capture_output=True,
        text=True,
        timeout=PROBE_TIMEOUT,
        check=False,
        env=env,
    )


def fail(message: str, result: subprocess.CompletedProcess[str] | None = None) -> None:
    print(f"\nFAIL: {message}", file=sys.stderr)
    if result is not None:
        print(f"--- stdout ---\n{result.stdout}", file=sys.stderr)
        print(f"--- stderr ---\n{result.stderr}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} <dist-dir>")
    dist_dir = Path(sys.argv[1])
    binary = binary_path(dist_dir)
    probe_log = dist_dir.parent / "frozen-probe.log"
    probe_log.unlink(missing_ok=True)

    size_mb = sum(f.stat().st_size for f in dist_dir.rglob("*") if f.is_file()) / 1e6
    print(f"artifact   {dist_dir}  ({size_mb:.0f} MB)")

    before = running_instances(binary)
    if before:
        fail(f"the binary was already running before the smoke test: {before}")

    started = time.monotonic()
    version = run(binary, ["--version"])
    if version.returncode != 0:
        fail("the frozen binary could not report its version", version)
    print(f"--version  {version.stdout.strip()}  ({time.monotonic() - started:.1f}s)")

    started = time.monotonic()
    probe = run(binary, ["--spawn-probe"], probe_log=probe_log)
    elapsed = time.monotonic() - started
    print(f"--spawn-probe exited {probe.returncode} in {elapsed:.1f}s")
    print(probe.stdout)

    starts = probe_log.read_text(encoding="utf-8").splitlines() if probe_log.is_file() else []
    print(f"top-level application starts recorded: {len(starts)}")
    for line in starts:
        print(f"  {line}")

    if probe.returncode != 0:
        fail("the spawn probe failed inside the frozen build", probe)

    # Asserted rather than merely printed (`T029-R2`). Without this the smoke test would pass
    # against a source run, which proves nothing about freezing — the entire point of T-020.
    if "frozen           True" not in probe.stdout:
        fail("the parent process does not report sys.frozen; this is not a frozen build", probe)
    if "child frozen     True" not in probe.stdout:
        fail("the spawned child does not report sys.frozen", probe)

    # The criterion, asserted rather than eyeballed. More than one start means the spawned
    # child re-executed the application instead of running the worker function.
    if len(starts) != 1:
        fail(
            f"expected exactly 1 top-level application start, got {len(starts)}. "
            "A line with --multiprocessing-fork in its argv means freeze_support() did not "
            "intercept the child (REL-001, ARCHITECTURE.md §3)",
            probe,
        )

    # Give a leaked child a moment to show itself before declaring the process tree clean.
    time.sleep(2)
    orphans = running_instances(binary)
    if orphans:
        fail(f"processes survived the run: {orphans}")

    print("\nOK: frozen build launches, spawns a worker, exchanges one message, exits 0,")
    print("    runs exactly one top-level application process, and leaves no orphan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
