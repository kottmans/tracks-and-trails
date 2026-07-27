"""QThread that drains the multiprocessing result queue and re-emits Qt signals.

The single bridge from worker processes to the GUI thread (`ARCHITECTURE.md` §3, §8), and the
only place in the application where a blocking read happens at all.

## What it is allowed to do

**Emit signals. Nothing else.** It holds no widget, no repository, and no job state;
`ARCHITECTURE.md` §8's threading rule is that Qt objects are touched only on the GUI thread, and
the way this thread keeps that rule is by having nothing to touch. Everything that *reacts* to a
message runs in `DownloadManager`'s slots, on the GUI thread, because a queued signal is
delivered in the receiver's thread.

## One pump per session

The pump reads until the protocol's sentinel and then returns, which is what makes shutdown
deterministic rather than timed (`T-013`): a pump shared across jobs would need a second channel
to be told when to stop, and the obvious implementation of that is a `get(timeout=…)` loop that
either notices late or spins. `WorkerFinished` already means "this stream is over", so the pump
ends exactly when its stream does.

The parent's obligation, held by `DownloadManager`, is that **a sentinel always arrives**: a
worker that dies without sending one has one synthesised on its behalf. Without that, this
thread would sit in `Queue.get()` forever — the hang `validate_sequence()`'s docstring names.

## Violations are reported, never swallowed

Three things can arrive on the queue that are protocol violations rather than ordinary errors,
and each turns into a hang or a lie if ignored:

- an **undeclared object**, which nothing downstream could interpret;
- a **second outcome** for a job, which would drive a second state transition (`T011-R4`);
- an **unreadable queue** — a truncated pickle left by a worker killed mid-write.

Each is emitted on `violation` and ends the stream. `validate_sequence()` then re-checks the
whole session, so a violation visible only in the *shape* of the stream — a missing outcome,
messages after the outcome — is caught too. The two can report one fault twice; that is
deliberate, because suppressing the second would mean deciding which violation matters before
the manager has seen either.
"""

from typing import Any

from PySide6.QtCore import QThread, Signal

from tracks_and_trails.downloader.protocol import (
    MESSAGE_TYPES,
    Failed,
    Probed,
    Progress,
    ProtocolViolationError,
    ResolutionReport,
    SessionKind,
    Succeeded,
    WorkerFinished,
    is_message,
    is_outcome,
    validate_sequence,
)


class ResultPump(QThread):
    """Drains one session's result queue onto Qt signals.

    Constructed and started on the GUI thread; only `run()` executes on this one.
    """

    #: One signal per declared message type. The mapping is checked against `MESSAGE_TYPES` at
    #: construction, so a message type added to the protocol without a route here fails loudly
    #: rather than being dropped on the floor.
    probed = Signal(object)
    progress = Signal(object)
    resolution_reported = Signal(object)
    succeeded = Signal(object)
    failed = Signal(object)
    worker_finished = Signal(object)

    #: `(job_id, reason)` — a stream this contract forbids.
    violation = Signal(str, str)

    #: `(job_id)` — the stream is over and this thread is returning. Emitted on every path,
    #: including a violation, because finalising a job must not depend on the session having
    #: been well-behaved.
    session_ended = Signal(str)

    def __init__(
        self,
        queue: Any,
        job_id: str,
        kind: SessionKind,
        parent: QThread | None = None,
    ) -> None:
        super().__init__(parent)
        self._queue = queue
        self._job_id = job_id
        self._kind = kind
        self._routes: dict[type, Any] = {
            Probed: self.probed,
            Progress: self.progress,
            ResolutionReport: self.resolution_reported,
            Succeeded: self.succeeded,
            Failed: self.failed,
            WorkerFinished: self.worker_finished,
        }
        declared = set(MESSAGE_TYPES)
        routed = set(self._routes)
        if declared != routed:
            raise ValueError(
                "every declared message type needs a signal, and no signal may route a type the "
                "protocol does not declare. "
                f"Unrouted: {sorted(t.__name__ for t in declared - routed)}; "
                f"undeclared: {sorted(t.__name__ for t in routed - declared)}."
            )

    @property
    def job_id(self) -> str:
        return self._job_id

    def run(self) -> None:
        """Read until the sentinel, routing as we go, then validate the whole session.

        Deliberately a blocking `get()` with no timeout: a timeout would be a second, weaker
        definition of "the stream ended", competing with the protocol's own.
        """
        session: list[object] = []
        outcome_seen = False
        try:
            while True:
                try:
                    item = self._queue.get()
                except Exception as error:  # see the module docstring
                    # A worker killed mid-write leaves a truncated pickle behind, and that
                    # surfaces here as anything from `EOFError` to `UnpicklingError`. Whatever
                    # it is, the stream is unreadable and this thread must end rather than
                    # re-enter a `get()` that will fail the same way.
                    self._report(f"the result queue could not be read: {error!r}")
                    break

                session.append(item)

                if not is_message(item):
                    self._report(f"undeclared object on the queue: {item!r}")
                    break

                if is_outcome(item):
                    if outcome_seen:
                        # `T011-R4`: reported, and **not** routed. Suppressing the signal here
                        # is what makes "no second state transition" true by construction,
                        # rather than by every slot remembering to check.
                        self._report(
                            f"a second outcome ({type(item).__name__}) for job "
                            f"{self._job_id!r}; a session has exactly one"
                        )
                        continue
                    outcome_seen = True

                self._routes[type(item)].emit(item)

                if isinstance(item, WorkerFinished):
                    break
        finally:
            try:
                validate_sequence(self._kind, session)
            except ProtocolViolationError as error:
                self._report(str(error))
            self.session_ended.emit(self._job_id)

    def _report(self, reason: str) -> None:
        self.violation.emit(self._job_id, reason)
