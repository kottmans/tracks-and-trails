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
deterministic rather than timed (`T-013`). `WorkerFinished` already means "this stream is over",
so the pump ends exactly when its stream does.

## How it is stopped when the stream never ends (`T019-R5`)

`stop()` sets a flag; the read is a short `get(timeout=…)` so the flag is noticed within one
poll, and the thread **returns**. There is no `QThread.terminate()` anywhere in this project any
more, and that is a correctness requirement rather than a style preference.

`terminate()` kills a thread wherever it happens to be — including inside CPython's own
internals, holding one of its locks, which is then never released. The symptom was a bare
`pytest` wedging after 46 manager tests roughly one run in five: the main thread parked forever
on an internal mutex inside `Thread.start()`, with two threads left carrying no Python frame at
all. Twenty-two consecutive clean runs with `terminate()` removed, against that same one-in-five
baseline, is what identified it.

**The timeout is not a second definition of "the stream ended".** That is still the sentinel's
job alone, and a poll that expires simply loops. The timeout exists so a *stopped* thread can
notice it has been stopped — which is the one thing an untimed `get()` makes impossible, and the
reason the first version reached for `terminate()` at all.

The parent's obligation, held by `DownloadManager`, is that **a sentinel always arrives**: a
worker that dies without sending one has one synthesised on its behalf. Without that, this
thread would sit in `Queue.get()` forever — the hang `validate_sequence()`'s docstring names.

## Nothing illegal is ever routed (`T013-R1`)

Every message goes through `protocol.SessionValidator` **before** it is emitted, and a message
the grammar rejects ends the stream instead of reaching a signal. This ordering is the finding:
the first version routed each message and validated the finished session afterwards, so an
illegal one had already been persisted and announced by the time the contract was consulted —
a probe session could report `Succeeded` and leave a durable `COMPLETED` job.

The validator is the protocol's own grammar in incremental form, not a second copy of it, so
what this thread enforces and what `validate_sequence()` enforces cannot drift apart.

One class of fault is not the grammar's and is handled here: an **unreadable queue**, which is
what a worker killed mid-write leaves behind. It is reported the same way and ends the stream
the same way, because a queue that cannot be read cannot be validated either.
"""

import queue as queue_module
import threading
from typing import Any, Final

from PySide6.QtCore import QThread, Signal

from tracks_and_trails.downloader.protocol import (
    MESSAGE_TYPES,
    Failed,
    Probed,
    Progress,
    ProtocolViolationError,
    ResolutionReport,
    SessionKind,
    SessionValidator,
    Succeeded,
    WorkerFinished,
)

#: How long a read waits before looking at the stop flag again.
#:
#: Fifty milliseconds matches `DownloadManager`'s own tick, so a stop is noticed on the same
#: timescale as every other lifetime decision, and an idle pump costs twenty wakeups a second —
#: which is nothing beside the process it is reading from.
POLL_SECONDS: Final = 0.05


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
        #: Set from the GUI thread, read here. A `threading.Event` rather than a bare bool
        #: because the two threads are genuinely concurrent and this is the one piece of state
        #: they share.
        self._stopping = threading.Event()
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

    def stop(self) -> None:
        """Ask this thread to stop reading and return (`T019-R5`).

        A request, and one that is always granted within `POLL_SECONDS` — unlike
        `QThread.terminate()`, which was immediate and left the interpreter holding locks nobody
        would ever release. The caller still has to wait for `isFinished()` rather than assume:
        that a stop has been *asked for* is not that the thread has *stopped*, which is the
        distinction `T013-R4` already drew for the previous mechanism.
        """
        self._stopping.set()

    def run(self) -> None:
        """Validate each message, route it only if it is legal, and stop at the sentinel.

        **Validation happens before routing, and that order is the whole point** (`T013-R1`).
        Routing a message persists job state and tells the GUI about it, so a stream checked only
        after it ended reported its violation *after* the damage — a probe session could return
        `Succeeded` and leave a durable `COMPLETED` job that the contract forbids.

        The read polls rather than blocking outright, so `stop()` can be noticed. That timeout
        is **not** a definition of "the stream ended" — the sentinel remains the only thing that
        means that, and an expired poll simply loops. See the module docstring for why the
        alternative, killing the thread, was worse than it looked.
        """
        validator = SessionValidator(self._kind, self._job_id)
        try:
            while not self._stopping.is_set():
                try:
                    item = self._queue.get(timeout=POLL_SECONDS)
                except queue_module.Empty:
                    # Nothing yet. The only question a timeout answers is whether we were asked
                    # to stop; it says nothing about the stream, so the loop simply goes round.
                    continue
                except Exception as error:  # see the module docstring
                    # A worker killed mid-write leaves a truncated pickle behind, and that
                    # surfaces here as anything from `EOFError` to `UnpicklingError`. Whatever
                    # it is, the stream is unreadable and this thread must end rather than
                    # re-enter a `get()` that will fail the same way.
                    self._report(f"the result queue could not be read: {error!r}")
                    break

                try:
                    validator.accept(item)
                except ProtocolViolationError as error:
                    # Reported, **not** routed, and the stream ends here. `ProtocolViolationError`
                    # says why: a bad message is discarded, but a bad *sequence* means the worker
                    # cannot be trusted at all — so there is nothing to gain by reading on, and
                    # a great deal to lose by acting on what follows.
                    self._report(str(error))
                    break

                self._routes[type(item)].emit(item)

                if isinstance(item, WorkerFinished):
                    break
            else:
                # The loop condition failed, so `stop()` was called. Recorded as a violation for
                # the same reason a synthesised sentinel is: the stream did not end the way the
                # protocol says a stream ends, and a receiver that quietly accepted that could
                # not tell a clean shutdown from an abandoned one.
                self._report("the parent stopped this reader before the stream ended")
        finally:
            try:
                validator.complete()
            except ProtocolViolationError as error:
                self._report(str(error))
            self.session_ended.emit(self._job_id)

    def _report(self, reason: str) -> None:
        self.violation.emit(self._job_id, reason)
