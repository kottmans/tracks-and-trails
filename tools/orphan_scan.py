"""Find spawned workers that outlived the application that created them (`T-258`).

**What this is for.** `T-258`'s fix makes the orphan preventable; this makes an existing one
*visible*. The distinction is the criterion: `OPS-003` means nobody logs in to `STARBASE`, and the
five orphans that prompted the task were found by accident, eleven and twelve days after the run
that spawned them, while somebody was diagnosing why the machine had stopped accepting CI jobs.
Prevention that regresses is silent; this is what would have said so on day one.

**Usage** — a script, and it needs no repository checkout beyond `psutil`:

    .venv/bin/python tools/orphan_scan.py            # report, exit 1 if any were found
    .venv/bin/python tools/orphan_scan.py --kill     # report and reap them

The non-zero exit on a find is what lets a CI step fail the machine rather than the build's
subject, and `--kill` is the manual reap that was performed by hand the first time.

## What counts as one, and why it is not "a python process with no parent"

A spawned worker is identifiable from its command line alone: `multiprocessing` starts one by
running `spawn_main` with `--multiprocessing-fork` appended, which is how the five were recognised.
Two further conditions keep this from reporting healthy processes:

- **Its parent must be gone.** A live worker under a live application is not an orphan, and
  "gone" is not "`ppid == 1`" — see `_parent_is_gone`, where that first rule is recorded along
  with the measurement that killed it.
- **It must be old enough to have missed its bootstrap.** A worker spawned microseconds ago has a
  parent that has not finished `start()`. `MINIMUM_AGE_SECONDS` is deliberately generous: this
  reports on a machine, not in a hot loop, and the orphans it is for were eleven days old.

**This does not identify *whose* worker it is.** Any `multiprocessing` program on the machine
produces the same command line, so a find is a prompt to look rather than a proof of ours. Said
here because the first version claimed otherwise, and `ai/TESTING.md`'s rule about instruments that
report confidently about nothing applies to this one too.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass

import psutil

#: How old a spawned worker must be before its missing parent means anything.
#:
#: Sized for the question rather than for a test: a worker whose parent is mid-`start()` is normal
#: and momentary, and the orphans this exists for were measured in days.
MINIMUM_AGE_SECONDS = 60.0

#: The two markers `multiprocessing.spawn` puts on every spawned child's command line.
_SPAWN_MARKERS = ("spawn_main", "--multiprocessing-fork")


@dataclass(frozen=True)
class Orphan:
    """One spawned worker whose parent is gone, with what a person needs to judge it."""

    pid: int
    age_seconds: float
    parent_pid: int
    threads: int
    rss_bytes: int

    def describe(self) -> str:
        days, hours = divmod(self.age_seconds / 3600, 24)
        # `threads` is reported because it is what identified the window the five died in:
        # `_exit_when_the_parent_does()` starts a second one, so a worker showing 1 never
        # reached it.
        return (
            f"pid {self.pid:>7}  age {int(days)}d{int(hours):02d}h  "
            f"dead parent {self.parent_pid:>7}  threads {self.threads}  "
            f"rss {self.rss_bytes / 1e6:.0f} MB"
        )


def _parent_is_gone(process: psutil.Process, parent_pid: int) -> bool:
    """Whether `parent_pid` names no live process that could have spawned this worker.

    **Not "the parent pid is 1".** That was the first rule here and it was wrong on the machine
    it was written on: a POSIX orphan is reparented to the nearest *subreaper*, which on a
    systemd user session is `systemd` at some ordinary pid, not `init` at 1. Measured — the
    known-positive in `tests/unit/test_orphan_scan.py` reparented to pid 2105 — and the rule
    would have reported "none found" on precisely the case this exists to find.

    So the question asked is what the child's own existence implies about its parent: a
    `spawn_main` child is created by **a Python interpreter**, so a parent that is not one
    cannot be the parent that spawned it, whatever the kernel now records. Three ways for it to
    be gone, and the third is that rule:

    - the pid does not resolve at all (Windows, where nothing reparents);
    - it resolves to a process *younger* than the child, which no real parent can be — the
      pid-reuse guard;
    - it resolves to something that is not a Python process — POSIX, reparented.

    Fails toward **not** reporting when the parent cannot be inspected, because a find is a
    prompt for a person to look and a false one spends that attention for nothing.
    """
    if parent_pid <= 1:  # init itself, or no parent recorded at all
        return True
    try:
        parent = psutil.Process(parent_pid)
        if parent.create_time() > process.create_time():
            return True
        return "python" not in parent.name().lower()
    except psutil.NoSuchProcess:
        return True
    except psutil.AccessDenied:
        # A parent we cannot inspect is a parent that exists. Reporting it would be a guess.
        return False


def find_orphans(minimum_age_seconds: float = MINIMUM_AGE_SECONDS) -> list[Orphan]:
    """Every spawned worker here whose parent is gone and which is old enough to count."""
    now = time.time()
    found: list[Orphan] = []
    for process in psutil.process_iter(["pid", "ppid", "cmdline", "create_time"]):
        try:
            command = " ".join(process.info["cmdline"] or ())
            if not all(marker in command for marker in _SPAWN_MARKERS):
                continue
            age = now - process.info["create_time"]
            if age < minimum_age_seconds:
                continue
            parent_pid = process.info["ppid"]
            if not _parent_is_gone(process, parent_pid):
                continue
            found.append(
                Orphan(
                    pid=process.info["pid"],
                    age_seconds=age,
                    parent_pid=parent_pid,
                    threads=process.num_threads(),
                    rss_bytes=process.memory_info().rss,
                )
            )
        except psutil.NoSuchProcess, psutil.AccessDenied:
            # It exited while being read, or is not ours to inspect. Either way, not a report.
            continue
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--kill", action="store_true", help="reap what was found, rather than only reporting it"
    )
    parser.add_argument(
        "--minimum-age-seconds",
        type=float,
        default=MINIMUM_AGE_SECONDS,
        help=f"how old a worker must be to count (default {MINIMUM_AGE_SECONDS:g})",
    )
    arguments = parser.parse_args(argv)

    orphans = find_orphans(arguments.minimum_age_seconds)
    if not orphans:
        print("no orphaned workers found")
        return 0

    print(f"{len(orphans)} orphaned worker(s) — spawned, parent gone, still running:")
    for orphan in orphans:
        print(f"  {orphan.describe()}")
        if arguments.kill:
            try:
                psutil.Process(orphan.pid).kill()
                print(f"    killed {orphan.pid}")
            except psutil.Error as error:
                print(f"    could not kill {orphan.pid}: {error}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
