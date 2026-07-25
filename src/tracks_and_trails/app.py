"""Application setup and wiring.

Placeholder. T-007 replaces `run` with real QApplication and MainWindow construction;
T-013 adds the multiprocessing start-method setup and the download manager wiring.
Deliberately imports no Qt yet, so that T-001's skeleton runs headless.
"""

from collections.abc import Sequence

from tracks_and_trails import __version__


def run(argv: Sequence[str]) -> int:
    """Start the application and return the process exit code."""
    del argv  # unused until T-007 parses arguments
    print(f"Tracks & Trails {__version__} -- no user interface yet (see ai/TASKS.md: T-007)")
    return 0
