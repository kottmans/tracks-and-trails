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
multiprocessing.freeze_support()


def main() -> int:
    """Run the application. Returns the process exit code."""
    # Imported lazily so that merely importing this module does not pull in Qt.
    from tracks_and_trails.app import run

    return run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
