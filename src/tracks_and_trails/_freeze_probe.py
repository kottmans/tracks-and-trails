"""Frozen-build self-test for the `ARC-002` process model (`T-020`).

**Why this ships in the application rather than living in `tests/`.** The failure it guards
against only exists in a frozen binary. There, `sys.executable` is the application itself, so
`multiprocessing` starting a child re-executes the *app* — and without
`multiprocessing.freeze_support()` running before anything else, that child runs the whole
program again instead of the worker function. The result is a recursive launch, not a subtle
misbehavior. Testing it therefore requires code inside the frozen artifact, spawning a real
child through the real entry point (`REL-001`, `ARCHITECTURE.md` §3 and §12).

**This module belongs to none of `ARCHITECTURE.md` §4's four layers.** It is listed in §4's
structure and described in §12, but as frozen-build diagnostic infrastructure rather than as
product code — which is what the leading underscore marks. It imports no Qt so a spawned child
inherits none (`ARC-002`), and is reachable only via an explicit `--spawn-probe` argument.
`T-012` builds the real worker; this never becomes one.

**How "exactly one top-level application process" is asserted.** `record_app_start` is called
by `main()` in `__main__.py` — the first thing every top-level start reaches — and appends a
line to the file named by `TT_PROBE_LOG`. Exactly one line means the child ran the worker
function; more than one means it relaunched the application.

The marker deliberately lives in `main()` rather than in `run_probe`. An earlier version
recorded it inside the probe, which does not work: a relaunched child inherits multiprocessing's
own argument vector, not the parent's, so it never re-enters `--spawn-probe` and the count stays
at one while the recursion happens anyway. That was found by actually removing
`freeze_support()` and rebuilding, not by reasoning about it.
"""

import multiprocessing
import os
import sys
from multiprocessing.queues import Queue as QueueType
from pathlib import Path
from typing import Any

#: Names the file that records one line per top-level application start. Set by the caller
#: (CI, or a test); when unset the probe still runs but the recursion count is not recorded.
PROBE_LOG_ENV = "TT_PROBE_LOG"

#: The single message the child sends back. Not a real IPC protocol — `T-011` defines that.
PROBE_MESSAGE = "worker-alive"

#: Generous: a cold frozen child on a loaded CI runner starts far slower than a source one.
TIMEOUT_SECONDS = 120


def record_app_start() -> None:
    """Record one top-level application start, if a probe log is configured.

    Called from `main()`. A no-op unless `TT_PROBE_LOG` is set, which it never is in normal
    use — this costs one environment lookup on the startup path and buys the only direct
    evidence that a frozen child did not relaunch the app.
    """
    path = os.environ.get(PROBE_LOG_ENV)
    if not path:
        return
    try:
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(f"app-start pid={os.getpid()} frozen={is_frozen()} argv={sys.argv[1:]}\n")
    except OSError:
        return


def probe_child(queue: QueueType[Any]) -> None:
    """The spawned worker. Module-level so `spawn` can pickle it by reference.

    Sends one message and exits. Deliberately trivial: this task answers whether spawning
    from a frozen binary works at all, not whether any real work does.
    """
    queue.put({"message": PROBE_MESSAGE, "pid": os.getpid(), "frozen": is_frozen()})


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def run_probe() -> int:
    """Spawn one child, exchange one message, and exit. Returns a process exit code."""
    context = multiprocessing.get_context("spawn")
    queue: QueueType[Any] = context.Queue()
    child = context.Process(target=probe_child, args=(queue,), name="tt-freeze-probe")

    child.start()
    try:
        payload = queue.get(timeout=TIMEOUT_SECONDS)
    # Any failure at all is a probe failure; there is no exception here worth re-raising.
    except Exception as exc:
        child.terminate()
        child.join(timeout=TIMEOUT_SECONDS)
        print(f"FAIL: no message from the spawned child: {exc!r}", file=sys.stderr)
        return 1
    finally:
        child.join(timeout=TIMEOUT_SECONDS)

    print(f"frozen           {is_frozen()}")
    print(f"parent pid       {os.getpid()}")
    print(f"child pid        {payload.get('pid')}")
    print(f"child frozen     {payload.get('frozen')}")
    print(f"message          {payload.get('message')}")
    print(f"child exitcode   {child.exitcode}")

    if payload.get("message") != PROBE_MESSAGE:
        print(f"FAIL: unexpected message {payload!r}", file=sys.stderr)
        return 1
    if payload.get("pid") == os.getpid():
        print("FAIL: the worker ran in the parent process; no child was spawned", file=sys.stderr)
        return 1
    if child.is_alive():
        print("FAIL: the child is still alive after join; it would be orphaned", file=sys.stderr)
        return 1
    if child.exitcode != 0:
        print(f"FAIL: child exited {child.exitcode}", file=sys.stderr)
        return 1

    print("OK: spawned a child from this build, exchanged one message, and reaped it")
    return 0
