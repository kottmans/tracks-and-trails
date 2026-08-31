"""Which yt-dlp a child imports, asked without Qt (`REQ-025`, `T-198`, `T198-R2`).

Split out of `ytdlp_service.py` so `_freeze_probe.py` can use it. That module deliberately
imports no Qt — a spawned child must inherit none (`ARC-002`) — and the service beside this one
does, at module scope. **The alternative was a second spawn-and-read implementation inside the
probe**, which would mean the frozen gate proving a copy of the resolver rather than the
resolver, and a second implementation of a rule is the defect this project's reviews keep
finding.

`spawn` for the reason `ARC-002` gives: forking a process that has created a `QApplication` is
unsafe, and one start method everywhere means both platforms exercise the same path.
"""

import multiprocessing
import queue as queue_module
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from tracks_and_trails.downloader import process_tree, worker
from tracks_and_trails.downloader.cancellation import (
    Cancelled,
    OperationCancelledError,
    not_cancelled,
    stop_if_cancelled,
)
from tracks_and_trails.downloader.protocol import ResolutionReport, WorkerFinished

#: How long to wait for a child to import yt-dlp and answer. Generous: `spawn` re-imports the
#: interpreter and yt-dlp is a large package, so a slow machine under load can take seconds. A
#: query that has not answered by now is one the user should be told about rather than waited on.
RESOLUTION_TIMEOUT_SECONDS: Final = 90.0

#: How long one queue read blocks before the loop re-asks whether it should still be waiting.
#: **The reason this is not simply the whole timeout** (`T289-R21`): a single 90-second read cannot
#: notice a cancellation, so a shutdown behind a hung child waited a minute and a half for a
#: process it had already been told to abandon. Short enough that stopping is prompt, long enough
#: that the loop is not a spin — a slice this size costs about ten wake-ups a second.
_POLL_SLICE_SECONDS: Final = 0.1

__all__ = [
    "RESOLUTION_TIMEOUT_SECONDS",
    "OperationCancelledError",
    "Resolution",
    "ResolutionUnavailableError",
    "resolve_in_a_child",
]


class ResolutionUnavailableError(Exception):
    """No child could say which yt-dlp is in use, with a reason fit to show a user."""


@dataclass(frozen=True, slots=True)
class Resolution:
    """Which yt-dlp a worker imported, and where it came from.

    `source` is a label such as `"bundled baseline"` or `"user-managed copy (OPS-002)"`, never a
    path (`NFR-007`) — `environment.YtdlpCandidate` carries the same distinction for the same
    reason.

    `rejected` is why an earlier candidate was not used. `ARCHITECTURE.md` §6 requires a rejected
    override to be **reported, never silently ignored**, and a user who installed a copy that
    does not import needs to be told that rather than left reading a baseline version and
    wondering why their update did nothing.
    """

    version: str
    source: str
    rejected: tuple[str, ...] = ()

    @property
    def is_user_managed(self) -> bool:
        """Whether this came from the user's own copy rather than the shipped baseline.

        Read from the resolved `source` rather than by asking the filesystem whether the
        directory exists: a directory that exists but does not import is **not** what is in use,
        and the button that offers to remove it should say so from the same fact the version
        came from.
        """
        return "user-managed" in self.source


def resolve_in_a_child(
    directory: Path | None = None,
    *,
    entry_point: Callable[..., Any] | None = None,
    timeout: float = RESOLUTION_TIMEOUT_SECONDS,
    cancelled: Cancelled = not_cancelled,
) -> Resolution:
    """Spawn a child, have it import yt-dlp, and return what it reported.

    Blocking, and deliberately not called from the GUI thread — `YtdlpService` is what puts it on
    the pool. Kept separate from that class so the mechanism is testable without a Qt event loop.

    `spawn` for the reason `ARC-002` gives: forking a process that has created a `QApplication`
    is unsafe, and one start method everywhere means both platforms exercise the same path.

    **The wait is sliced so cancellation can land in it** (`T289-R21`). The whole of this function
    is waiting: a spawn, an import of a large package, and a queue read that was allowed to be one
    ninety-second block. `cancelled` is asked before each slice, and a cancellation leaves through
    the same `finally` that terminates and joins the child — the child is already owned here, so
    stopping mid-wait strands nothing that finishing would not have cleaned up too.
    """
    target = worker.spawn_resolution if entry_point is None else entry_point
    context = multiprocessing.get_context("spawn")
    message_queue: Any = context.Queue()
    child = context.Process(
        target=target,
        args=(message_queue,),
        kwargs={"user_ytdlp_directory": directory},
        daemon=True,
    )
    report: ResolutionReport | None = None
    started = False
    try:
        # `T258-R3`: this child is spawned without a `DownloadManager`, and the pre-bootstrap
        # window does not care what the target was going to be — it opens before the target is
        # unpickled. `spawn_resolution`'s "containment is not required" note covers descendants
        # spawned *by* this child; it never covered this child being stranded before it runs.
        #
        # **Translated rather than allowed to escape** (`T258-R9`, `T-263`). A refusal here is a
        # reason the user can act on — it names the boundary that failed — and this function's
        # documented failure is `ResolutionUnavailableError`. Left as itself it reached
        # `YtdlpService`'s broad branch, which reports the exception's *type* and drops the
        # sentence: *"The operation could not be completed (ContainmentUnavailableError)."*
        # Chained with `from`, so the original is still in the traceback for a log to carry.
        try:
            process_tree.start_contained(child)
        except process_tree.ContainmentUnavailableError as error:
            raise ResolutionUnavailableError(str(error)) from error
        started = True
        # **One deadline, many reads.** The overall bound is unchanged — a query that has not
        # answered by `timeout` is still given up on with the same sentence — but it is now
        # measured against the clock rather than against the length of a single blocking read, so
        # a slice that returns nothing costs the loop a fraction of a second and not the lot.
        deadline = time.monotonic() + timeout
        while True:
            stop_if_cancelled(cancelled)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ResolutionUnavailableError(
                    "Checking the yt-dlp version took too long and was stopped."
                )
            try:
                message = message_queue.get(timeout=min(_POLL_SLICE_SECONDS, remaining))
            except queue_module.Empty:
                continue
            if isinstance(message, ResolutionReport):
                report = message
            if isinstance(message, WorkerFinished):
                break
    finally:
        # The child is short-lived and daemonic, but leaving it unjoined would leak a zombie per
        # query on POSIX. `terminate` covers the child that answered and then hung on exit.
        #
        # **Guarded on `started`**: a spawn that fails — an unpicklable target is the way a test
        # reaches this — leaves a `Process` that `join` refuses with *"can only join a started
        # process"*, and that secondary error would replace the real one on its way out.
        if started:
            if child.is_alive():
                child.terminate()
            child.join(timeout=5.0)
        message_queue.close()

    if report is None:
        raise ResolutionUnavailableError(
            "No usable yt-dlp could be loaded. The application cannot download until this is "
            "resolved; reverting to the bundled version is the first thing to try."
        )
    return Resolution(
        version=report.ytdlp_version,
        source=report.ytdlp_source,
        rejected=tuple(report.rejected),
    )
