"""Process entry point.

Nothing here may be reordered casually -- see the freeze_support() note below.
"""

import multiprocessing
import sys

# MUST be the first executable statement, and MUST precede any Qt import (REL-001,
# ARCHITECTURE.md §3, verified by T-020). Released builds are frozen, where sys.executable
# is the application binary rather than a Python interpreter. Without this call, a spawned
# worker re-executes the whole application -- another window, spawning its own children.
#
# In a frozen child process this call never returns: it runs the worker and exits. That is
# also why it precedes the Qt import, which keeps ARC-002's "workers inherit no Qt" true.
# It is a harmless no-op when running from source, so it is unconditional. Do not remove.
# TEMPORARY T-029 NEGATIVE PROOF: freeze_support() removed on purpose.
# multiprocessing.freeze_support()


def main() -> int:
    """Run the application. Returns the process exit code."""
    # Records one line per top-level application start when TT_PROBE_LOG is set, and does
    # nothing otherwise. This is T-020's evidence that a spawned child ran the worker rather
    # than relaunching the whole application; it must stay here, in the path every top-level
    # start reaches, because a relaunched child inherits multiprocessing's argv rather than
    # ours and so never reaches --spawn-probe. Imports no Qt.
    from tracks_and_trails._freeze_probe import record_app_start

    record_app_start()

    # Imported lazily so that merely importing this module does not pull in Qt.
    from tracks_and_trails.app import run

    return run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
