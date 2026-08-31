"""The process may not leave while a pool thread is still running Python (`T-289`, `T289-R21`).

`T-289`'s teardown reading measured both halves of the core dump's configuration: after `run()`
returned, `ytdlp_service`'s pool still had an active thread, and the `MainWindow` was still alive,
still valid and still owned by Python. Qt destroys the widget tree at exit **on the GUI thread**,
and a collection on that pool thread runs `~QWidget` **there**. Nothing sequenced the two.

These tests are about the sequencing, and each one uses a **real pool** — the module-level gate the
application actually schedules on — because the defect was that nothing joined *those*. A fake pool
would prove the barrier can be written, not that it is wired to the thing that runs.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, cast

import pytest
from PySide6.QtCore import QObject, QRunnable, Signal

from tracks_and_trails.app import OrderlyShutdown
from tracks_and_trails.downloader import ytdlp_service
from tracks_and_trails.ui import thumbnails

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

    from tracks_and_trails.downloader.pools import SealedPool

#: Long enough for a pool thread to be scheduled and finish on a loaded runner, short enough that a
#: barrier which never completes fails the test rather than hanging it. `T118-R10`'s bound: a timed
#: gate needs headroom over the thing it waits for, which here is a thread start.
_PATIENCE_MS = 10_000


class _Blocking(QRunnable):
    """A task that occupies its pool until the test lets it go."""

    def __init__(self, release: threading.Event) -> None:
        super().__init__()
        self.started = threading.Event()
        self._release = release

    def run(self) -> None:
        self.started.set()
        self._release.wait(timeout=30)


class _Manager(QObject):
    """`DownloadManager` seen through the two things the shutdown sequence uses."""

    idle = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.asked_to_stop = False

    def shutdown(self) -> None:
        self.asked_to_stop = True


class _Writer(QObject):
    """`QueueWriter` seen the same way."""

    closed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.asked_to_close = False
        self.waited = False

    def close(self) -> None:
        self.asked_to_close = True

    def wait_for_close(self) -> None:
        self.waited = True
        self.closed.emit()


class _Connection:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _App:
    def __init__(self) -> None:
        self.quits = 0

    def quit(self) -> None:
        self.quits += 1


def _pump(app: QApplication, until: Any, deadline_ms: int = _PATIENCE_MS) -> bool:
    """Run the event loop until `until()` is true, or the deadline passes."""
    from PySide6.QtCore import QDeadlineTimer

    deadline = QDeadlineTimer(deadline_ms)
    while not until():
        if deadline.hasExpired():
            return False
        app.processEvents()
    return True


@pytest.fixture
def release() -> Iterator[threading.Event]:
    """An event every blocking task waits on, always set so no test can strand a pool thread."""
    event = threading.Event()
    yield event
    event.set()


def _shutdown(pools: tuple[SealedPool, ...]) -> tuple[OrderlyShutdown, _App, _Manager, _Writer]:
    app, manager, writer, connection = _App(), _Manager(), _Writer(), _Connection()
    # **Cast at the seam, because the fakes are deliberate.** `OrderlyShutdown` is not a `QObject`
    # and connects to signals as a plain callable precisely so it can be built without an
    # application — its own docstring says so — and these stand in for the three collaborators
    # through the handful of calls the sequence makes on them. Widening the production signature to
    # protocols to satisfy a test would be the tail wagging the dog.
    return (
        OrderlyShutdown(
            cast("Any", app),
            cast("Any", manager),
            cast("Any", writer),
            cast("Any", connection),
            None,
            pools=pools,
        ),
        app,
        manager,
        writer,
    )


@pytest.mark.parametrize(
    "which",
    [
        pytest.param(ytdlp_service.pool, id="the yt-dlp pool"),
        pytest.param(thumbnails.pool, id="the thumbnail pool"),
    ],
)
def test_quit_waits_for_each_real_pool(
    qapp: QApplication, release: threading.Event, which: Any
) -> None:
    """**Each pool independently**, because one barrier covering both would hide a missing edge.

    A pool that nothing waits on is the whole defect, so this is asserted for the yt-dlp pool and
    the thumbnail pool separately: wiring only one of them would pass a test that took the two
    together and saw the other's completion.
    """
    pool = which()
    blocker = _Blocking(release)
    assert pool.start(blocker)
    assert blocker.started.wait(timeout=10), "the pool never ran the task"

    shutdown, app, _manager, writer = _shutdown((pool,))
    shutdown.begin()
    writer.wait_for_close()  # the database side is finished; the pool is not

    assert app.quits == 0, "quit was called with a pool task still running"
    assert not shutdown.finished

    release.set()
    assert _pump(qapp, lambda: app.quits == 1), "the barrier never completed after the task ended"
    assert shutdown.finished


def test_the_pools_are_sealed_the_moment_shutdown_begins(qapp: QApplication) -> None:
    """New work is refused rather than queued, or the barrier has no last task to wait for."""
    pool = ytdlp_service.pool()
    shutdown, _app, _manager, _writer = _shutdown((pool,))
    shutdown.begin()

    assert pool.sealed
    assert not pool.start(_Blocking(threading.Event())), "a sealed pool accepted new work"


def test_a_task_still_queued_when_the_seal_lands_declines_to_run(
    qapp: QApplication, release: threading.Event
) -> None:
    """Cooperative cancellation, on the real task the application schedules.

    The yt-dlp pool runs one task at a time, so a second task sits queued behind the blocker and
    starts *after* the seal. It must decline rather than perform an install into a directory the
    process is about to leave.
    """
    pool = ytdlp_service.pool()
    assert pool.start(_Blocking(release))

    performed = threading.Event()
    sink = ytdlp_service._Sink()
    refusals: list[str] = []
    sink.failed.connect(refusals.append)
    assert pool.start(ytdlp_service._Task(sink, lambda _sink: performed.set()))

    shutdown, _app, _manager, _writer = _shutdown((pool,))
    shutdown.begin()
    release.set()

    assert _pump(qapp, lambda: not pool.outstanding), "the pool never emptied"
    assert not performed.is_set(), "a cancelled task did its work anyway"
    assert refusals == ["The application is closing."]


def test_the_pools_draining_first_does_not_quit_before_the_writer(
    qapp: QApplication, release: threading.Event
) -> None:
    """**Whichever finishes last is the one that quits**, so the barrier is symmetric.

    The pools can empty before the database side has. A version that quit as soon as they did
    passed every other test here — the writer's own edge is asserted twice over and this direction
    was not asserted at all — while closing the connection under a writer that was still draining,
    which is the loss `OrderlyShutdown`'s order exists to prevent.
    """
    pool = thumbnails.pool()
    blocker = _Blocking(release)
    assert pool.start(blocker)
    assert blocker.started.wait(timeout=10)

    shutdown, app, _manager, writer = _shutdown((pool,))
    shutdown.begin()
    release.set()

    assert _pump(qapp, lambda: not pool.outstanding), "the pool never emptied"
    assert app.quits == 0, "quit was called before the writer had finished"
    assert not shutdown.finished

    writer.wait_for_close()
    assert app.quits == 1
    assert shutdown.finished


def test_the_about_to_quit_bypass_waits_for_the_pools(
    qapp: QApplication, release: threading.Event
) -> None:
    """The path with no event loop left still may not leave a pool thread running.

    `stop_for_exit` is reached from `aboutToQuit`, where the asynchronous barrier cannot complete:
    `drained` arrives through a queued connection and nothing is left to deliver it. So this path
    waits, bounded, and the test asserts the pool is empty by the time it returns.
    """
    pool = thumbnails.pool()
    blocker = _Blocking(release)
    assert pool.start(blocker)
    assert blocker.started.wait(timeout=10)

    shutdown, app, manager, writer = _shutdown((pool,))
    threading.Timer(0.2, release.set).start()
    shutdown.stop_for_exit()

    assert manager.asked_to_stop
    assert writer.waited
    assert pool.sealed
    assert pool.outstanding == 0, "the bypass returned with a pool task still running"
    assert pool.pool.activeThreadCount() == 0, "a thread outlived the bypass"
    assert app.quits == 1
    assert shutdown.finished


def test_a_shutdown_with_no_pools_behaves_as_it_did(qapp: QApplication) -> None:
    """The default is empty, so every caller predating this — and `T-013`'s tests — is intact."""
    shutdown, app, _manager, writer = _shutdown(())
    shutdown.begin()
    writer.wait_for_close()

    assert app.quits == 1
    assert shutdown.finished
