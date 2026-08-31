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

import logging
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
from PySide6.QtCore import QObject, QRunnable, Signal

from tracks_and_trails import app as application
from tracks_and_trails.app import OrderlyShutdown, compose
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

    # `is_empty` and not the count: the count reaches zero from inside the task's own `run`, and
    # the barrier deliberately does not believe it until the pool agrees (`T289-R21`).
    assert _pump(qapp, pool.is_empty), "the pool never emptied"
    assert app.quits == 0, "quit was called before the writer had finished"
    assert not shutdown.finished

    writer.wait_for_close()
    assert _pump(qapp, lambda: app.quits == 1), "the writer's completion did not release the quit"
    assert shutdown.finished


def test_the_barrier_does_not_believe_the_count_over_the_pool(
    qapp: QApplication, release: threading.Event
) -> None:
    """The exact state the review's probe measured: count zero, pool still running.

    `_Counted` reports completion from **inside** the task's own `run`, so the count reaches zero
    while that thread is still executing and `activeThreadCount()` still reports it. A barrier that
    believed the count would release the process there — which is the configuration this task
    exists to prevent, produced by the fix for it.

    The state is built directly rather than raced for: a task started on the underlying pool is one
    the gate never counted, so `outstanding` is zero throughout while the pool is plainly busy.
    """
    gate = thumbnails.pool()
    blocker = _Blocking(release)
    gate.pool.start(blocker)
    assert blocker.started.wait(timeout=10)
    assert gate.outstanding == 0, "the gate should not have counted a task started behind it"

    drains: list[int] = []
    gate.drained.connect(lambda: drains.append(1))
    gate.seal()

    assert not gate.is_empty(), "a busy pool called itself empty"
    assert _pump(qapp, lambda: False, deadline_ms=200) is False  # let the confirmation poll run
    assert drains == [], "drained fired while a pool thread was still running"

    release.set()
    assert _pump(qapp, lambda: drains == [1]), "drained never fired after the thread finished"
    assert gate.is_empty()


def test_a_sweep_already_running_stops_when_the_pools_are_sealed(
    qapp: QApplication, tmp_path: Path
) -> None:
    """Cancellation has to reach work that is **already running**, not only work still queued.

    The first version checked only at the task's entry, which a running sweep is already past. This
    runs the real `_SweepTask` over a directory of cache files with the pool already sealed, and
    the loop's own check is the only thing that can stop it.
    """
    directory = tmp_path / "thumbnails"
    directory.mkdir()
    for index in range(50):
        (directory / f"{index:02d}.jpg").write_bytes(b"x")

    gate = thumbnails.pool()
    gate.seal()

    sink = thumbnails._Sink()
    thumbnails._SweepTask(sink, directory, set()).run()

    survivors = list(directory.iterdir())
    assert len(survivors) == 50, f"a sealed sweep deleted {50 - len(survivors)} files anyway"


def test_a_decode_does_not_publish_a_picture_after_the_seal(
    qapp: QApplication, tmp_path: Path
) -> None:
    """The decode's own checkpoint: decoding is uninterruptible, publishing is a choice.

    A cache the process is leaving is not worth writing into, and the write is the part that
    touches the disk. Run with the pool sealed, the task must decode and then decline.
    """
    from PySide6.QtGui import QImage

    # Encoded through a file rather than a `QBuffer`: `QBuffer(QByteArray())` keeps a pointer to a
    # temporary that Python frees immediately, and saving into it segfaulted this test.
    picture = QImage(4, 4, QImage.Format.Format_RGB32)
    picture.fill(0x336699)
    source = tmp_path / "source.png"
    assert picture.save(str(source))  # format inferred from the .png suffix
    data = source.read_bytes()

    destination = tmp_path / "cache" / "picture.jpg"
    gate = thumbnails.pool()
    gate.seal()

    sink = thumbnails._Sink()
    thumbnails._DecodeAndStore(sink, "https://example.invalid/x.jpg", data, destination).run()

    assert not destination.exists(), "a sealed decode published into the cache anyway"


def test_the_bypass_does_not_claim_a_drain_it_did_not_get(
    qapp: QApplication,
    release: threading.Event,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A pool that times out is left recorded as **not** drained, and said out loud.

    There is no third option on this path — refusing to leave hangs the exit, and an unbounded wait
    is the same thing more slowly — so what is left is to keep the state truthful. A version that
    recorded a drain unconditionally quit over a running thread while reporting that none existed.
    """
    monkeypatch.setattr(application, "_POOL_EXIT_WAIT_MS", 50)
    gate = thumbnails.pool()
    blocker = _Blocking(release)
    assert gate.start(blocker)
    assert blocker.started.wait(timeout=10)

    shutdown, app, _manager, _writer = _shutdown((gate,))
    with caplog.at_level(logging.WARNING, logger="tracksandtrails.app"):
        shutdown.stop_for_exit()

    assert shutdown.finished, "the process must still leave; there is nothing else it can do"
    assert app.quits == 1
    assert not shutdown._pools_drained, "a timed-out wait was recorded as a drain"
    assert "still running" in caplog.text, "leaving with work outstanding was not reported"

    # **Released and joined inside the test, not left to a fixture.** This is the one test here
    # that deliberately ends with a pool thread running, and the autouse fixture that replaces the
    # pool singletons would then drop a busy `QThreadPool` — whose destructor waits, or aborts, on
    # whichever thread collects it. That segfaulted the suite once; the task is joined here.
    release.set()
    assert gate.wait_bounded(10_000), "the blocking task never finished"


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


def test_composition_hands_the_shutdown_both_real_pools(qapp: QApplication, tmp_path: Path) -> None:
    """**The wiring, which every test above would pass without** (`T289-R21`).

    Each pool is asserted independently there, but on a pool the *test* fetched. Replacing the
    composed thumbnail pool with the yt-dlp one — so the same pool is waited for twice and the
    thumbnail pool is not waited for at all — left every one of those tests green. The defect this
    task is about is a pool nothing waits on, so what composition actually hands over has to be
    asserted by identity, here.
    """
    composition = compose(
        qapp,
        database=tmp_path / "queue.sqlite3",
        output_directory=tmp_path / "downloads",
        geometry_file=tmp_path / "window.toml",
        settings_file=tmp_path / "settings.toml",
        cache_directory=tmp_path / "cache",
        entry_point=lambda *_args, **_kwargs: None,
    )
    try:
        wired = composition.shutdown._pools
        assert len(wired) == 2, "composition did not hand over two pools"
        assert any(pool is ytdlp_service.pool() for pool in wired), (
            "the yt-dlp pool is not waited for"
        )
        assert any(pool is thumbnails.pool() for pool in wired), (
            "the thumbnail pool is not waited for"
        )
    finally:
        composition.window.close()
        composition.window.deleteLater()


def test_an_update_refused_by_the_seal_gives_the_workers_back(
    qapp: QApplication, tmp_path: Path
) -> None:
    """A refusal must release the hold it was granted (`T289-R21`, the Low correction).

    `_run_holding_the_tree` takes every worker start on the operation's behalf **before** the task
    is submitted, and a sealed pool refuses it after that. Reporting the refusal by emitting
    `failed` directly skips `_on_failed`, which is the one place that gives the workers back — so
    the queue would be left permanently unable to start, by a shutdown that never ran the work.
    """

    class _Exclusion:
        def __init__(self) -> None:
            self.holds = 0
            self.releases = 0

        def hold_worker_starts(self, reason: str) -> bool:
            self.holds += 1
            return True

        def release_worker_starts(self) -> None:
            self.releases += 1

    exclusion = _Exclusion()
    service = ytdlp_service.YtdlpService(
        directory=tmp_path / "ytdlp",
        exclusion=cast("Any", exclusion),
        entry_point=lambda *_args, **_kwargs: None,
    )
    refusals: list[str] = []
    service.failed.connect(refusals.append)

    ytdlp_service.pool().seal()
    service.install_latest_version()

    assert refusals == ["The application is closing."]
    assert exclusion.holds == 1, "the hold was never taken, so this proves nothing"
    assert exclusion.releases == 1, "a refused update kept every worker start held"
    assert not service.busy


def test_a_shutdown_with_no_pools_behaves_as_it_did(qapp: QApplication) -> None:
    """The default is empty, so every caller predating this — and `T-013`'s tests — is intact."""
    shutdown, app, _manager, writer = _shutdown(())
    shutdown.begin()
    writer.wait_for_close()

    assert app.quits == 1
    assert shutdown.finished
