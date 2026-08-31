"""What a long operation asks before it goes on, and what it raises when the answer is no.

**Here rather than beside either caller, and deliberately Qt-free.** `ytdlp_update` and
`ytdlp_resolution` both need checkpoints (`T289-R21`), neither imports the other, and
`_freeze_probe.py` pulls the resolver into a process that must inherit no Qt (`ARC-002`). So the
shared vocabulary cannot live in `pools.py`, which is where the *gate* lives and which imports
`PySide6`.

**A callable rather than a gate reference**, so nothing under `downloader/` outside the service
learns what a `SealedPool` is: `YtdlpService` passes a function that asks the pool, and these
modules only ever ask a question.
"""

from __future__ import annotations

from collections.abc import Callable

#: Asked at each point where stopping leaves nothing half-done. `True` means stop.
Cancelled = Callable[[], bool]


class OperationCancelledError(Exception):
    """A long operation stopped at a checkpoint because it was asked to.

    **The `Error` suffix is the repository's naming rule (ruff `N818`) rather than a claim.** This
    is not a failure — nothing went wrong and nothing is broken — it is an operation declining to
    continue into a process that is leaving.

    **Not an `UpdateError` and not a `ResolutionUnavailableError`.** Those two say an operation
    *failed*; this says it was *stopped*, and the caller reports it in the one sentence shutdown
    has for the user — the same one an operation refused before it started already gets.

    **Not derived from `OSError`**, which is load-bearing: the download and the extraction both sit
    inside `except OSError` blocks that translate transport trouble into a user-facing sentence,
    and a cancellation has to pass through those rather than be reported as a failed network call.
    """


def not_cancelled() -> bool:
    """The default: nothing is asking this operation to stop."""
    return False


def stop_if_cancelled(cancelled: Cancelled) -> None:
    """Raise `OperationCancelledError` if the answer is yes.

    One line at a call site, so a checkpoint reads as a checkpoint rather than as three lines of
    control flow that a later edit can quietly rearrange.
    """
    if cancelled():
        raise OperationCancelledError("The application is closing.")
