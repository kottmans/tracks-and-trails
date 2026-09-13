"""Checks only a **windowed** release build needs, run by CI's `frozen windows` job (`T-319`).

    python packaging/windowed_checks.py probes  dist-release/tracks-and-trails
    python packaging/windowed_checks.py console dist-release/tracks-and-trails --expect none
    python packaging/windowed_checks.py console dist/tracks-and-trails --expect console

**Why this exists.** The release build is `console=False`, and the smoke build CI already probes is
not. So everything the smoke build proves through its `stdout` has to be proved again for the build
that ships, **through the report file** `_freeze_probe.say` writes to `TT_PROBE_REPORT` — and the
windowed build's own console output is deliberately thrown away, so a probe that stopped writing
the file fails here instead of passing on text nobody would ever see.

**`console` asks the question a user's double-click asks**: does a console window appear? Both
builds are started with `CREATE_NEW_CONSOLE`, which gives a console-subsystem program a window of
its own and is ignored by a GUI-subsystem one. The evidence is a `conhost.exe` in the process's
tree, or a `ConsoleWindowClass` window owned by any process in it. **`--expect console` against the
smoke build is the positive control**: a check that could not see a console there proves nothing
when it sees none in the release build.

Deliberately not a pytest test, for `frozen_smoke.py`'s reason: it runs against a build artifact
that only exists after a packaging step, and CI needs it to fail the job on its own.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil

BINARY = "tracks-and-trails.exe"

#: Every probe the windowed build must pass, and the line its report file must carry when it does.
#: The line is required as well as the exit code, so a probe that exits 0 without writing its
#: report — the defect this file exists to catch — is a failure rather than a pass.
PROBES: tuple[tuple[str, str], ...] = (
    ("--spawn-probe", "OK: spawned a child from this build"),
    ("--ytdlp-probe", "OK: the frozen artifact carries a usable yt-dlp"),
    ("--database-probe", "database        ok"),
    ("--ytdlp-update-probe", "OK: install, resolve in a child, and revert"),
    ("--ffmpeg-probe", "ffmpeg          ok"),
)

PROBE_TIMEOUT_SECONDS = 300
#: How long a launched build is watched for a console before the answer is taken as final.
CONSOLE_WATCH_SECONDS = 15.0


def judge_probe(exit_code: int, report: str | None, marker: str) -> str | None:
    """Why a probe run failed, or `None` when it passed. Pure, so each failure mode is tested.

    A missing report and a report without the marker are **separate** answers: the first is the
    file-write being lost, the second is the probe reporting something other than success.
    """
    if report is None:
        return "wrote no report file, so a windowed build's result reached nobody"
    if exit_code != 0:
        last = report.strip().splitlines()[-1] if report.strip() else "(empty report)"
        return f"exited {exit_code}: {last}"
    if marker not in report:
        return f"exited 0 but its report does not say {marker!r}"
    return None


def run_probes(artifact: Path) -> int:
    binary = artifact / BINARY
    failures = 0
    with tempfile.TemporaryDirectory(prefix="tt-windowed-probes-") as scratch:
        for flag, marker in PROBES:
            report_path = Path(scratch) / f"{flag.strip('-')}.txt"
            environment = {**os.environ, "TT_PROBE_REPORT": str(report_path)}
            completed = subprocess.run(  # noqa: S603 - a fixed flag against the artifact under test
                [str(binary), flag],
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=PROBE_TIMEOUT_SECONDS,
                check=False,
            )
            report = report_path.read_text("utf-8") if report_path.is_file() else None
            problem = judge_probe(completed.returncode, report, marker)
            print(f"{'FAIL' if problem else 'ok  '}  {flag}{': ' + problem if problem else ''}")
            if report:
                for line in report.strip().splitlines():
                    print(f"        {line}")
            failures += problem is not None
    print(f"windowed probes: {len(PROBES) - failures} of {len(PROBES)} passed through their report")
    return 1 if failures else 0


def console_evidence(root: psutil.Process) -> list[str]:
    """What in `root`'s process tree shows a console: a `conhost.exe`, or a console window."""
    try:
        tree = [root, *root.children(recursive=True)]
    except psutil.NoSuchProcess:
        return []
    evidence = [
        f"{child.name()} (pid {child.pid})"
        for child in tree[1:]
        if _name_of(child).lower() == "conhost.exe"
    ]
    pids = {process.pid for process in tree}
    evidence.extend(
        f"a ConsoleWindowClass window owned by pid {pid}" for pid in _console_window_owners(pids)
    )
    return evidence


def _name_of(process: psutil.Process) -> str:
    try:
        return process.name()
    except psutil.Error:
        return ""


def _console_window_owners(pids: set[int]) -> list[int]:
    """The pids among `pids` that own a top-level `ConsoleWindowClass` window. Windows only."""
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    owners: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def visit(hwnd: int, _: int) -> bool:
        name = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, name, 64)
        if name.value == "ConsoleWindowClass":
            owner = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value in pids:
                owners.append(owner.value)
        return True

    user32.EnumWindows(callback_type(visit), 0)
    return owners


def check_console(artifact: Path, expect: str) -> int:
    if sys.platform != "win32":
        print("console check: Windows only")
        return 2
    binary = artifact / BINARY
    launched = subprocess.Popen(  # noqa: S603 - the artifact under test, no arguments
        [str(binary)],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    root = psutil.Process(launched.pid)
    evidence: list[str] = []
    deadline = time.monotonic() + CONSOLE_WATCH_SECONDS
    try:
        while time.monotonic() < deadline and launched.poll() is None:
            evidence = console_evidence(root)
            if evidence:
                break
            time.sleep(0.25)
        exited_early = launched.poll()
    finally:
        _stop_tree(root)

    print(f"artifact  {binary}")
    seen = "; ".join(evidence) if evidence else f"none seen in {CONSOLE_WATCH_SECONDS:.0f} s"
    print(f"console   {seen}")
    if exited_early is not None and not evidence:
        print(f"FAIL: the build exited ({exited_early}) before it was watched; this proves nothing")
        return 1
    if expect == "console" and not evidence:
        print("FAIL: the positive control showed no console, so the check cannot see one")
        return 1
    if expect == "none" and evidence:
        print("FAIL: the windowed build opened a console window")
        return 1
    print(f"ok: {'a console, as the smoke build should' if evidence else 'no console window'}")
    return 0


def _stop_tree(root: psutil.Process) -> None:
    try:
        processes = [*root.children(recursive=True), root]
    except psutil.NoSuchProcess:
        return
    for process in processes:
        try:
            process.kill()
        except psutil.Error:
            continue
    psutil.wait_procs(processes, timeout=10)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    probes = commands.add_parser("probes")
    probes.add_argument("artifact", type=Path)
    console = commands.add_parser("console")
    console.add_argument("artifact", type=Path)
    console.add_argument("--expect", choices=("none", "console"), required=True)
    arguments = parser.parse_args(argv)
    if arguments.command == "probes":
        return run_probes(arguments.artifact)
    return check_console(arguments.artifact, arguments.expect)


if __name__ == "__main__":
    raise SystemExit(main())
