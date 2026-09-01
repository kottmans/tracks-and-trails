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

import hashlib
import io
import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, cast

import pytest
from PySide6.QtCore import QObject, QRunnable, Signal

from tracks_and_trails import app as application
from tracks_and_trails.app import OrderlyShutdown, compose
from tracks_and_trails.downloader import ytdlp_service, ytdlp_update
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


class _HoldsBriefly(QRunnable):
    """A task that occupies its pool for a fixed span **measured from when it starts running**.

    `T118-R10`'s rule, applied to a control rather than to a product bound: a test that arms a
    `threading.Timer` before scheduling its tasks measures its headroom against the runner's setup
    speed, and on a loaded machine the release can land before the thing it was meant to outlast.
    Holding from `run()` puts the whole margin between the task starting and the test's next three
    statements, which is the interval the test actually controls.
    """

    def __init__(self, seconds: float) -> None:
        super().__init__()
        self.started = threading.Event()
        self._seconds = seconds

    def run(self) -> None:
        self.started.set()
        threading.Event().wait(timeout=self._seconds)


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


def test_the_barrier_asks_the_pool_and_not_a_second_predicate_of_its_own(
    qapp: QApplication, release: threading.Event
) -> None:
    """`when_all_drained` must consume the same authoritative predicate the gate itself waits for.

    The first version asked `sealed and not outstanding`, which is strictly weaker than the gate's
    `is_empty()`: a runnable started on the underlying pool is one the gate never counted, so
    `outstanding` reads zero while the pool is plainly busy. A reviewer probe built exactly that
    state and the barrier released the quit in it — `active=1`, connection closed — while the
    gate's own `drained` correctly withheld. Two predicates for one question is one too many.
    """
    gate = thumbnails.pool()
    blocker = _Blocking(release)
    gate.pool.start(blocker)
    assert blocker.started.wait(timeout=10)
    assert gate.outstanding == 0, "the gate should not have counted a task started behind it"

    shutdown, app, _manager, writer = _shutdown((gate,))
    shutdown.begin()
    writer.wait_for_close()  # the database side is finished; the pool is not

    assert app.quits == 0, "the barrier released the quit over a busy pool it had not counted"
    assert not shutdown.finished

    release.set()
    assert _pump(qapp, lambda: app.quits == 1), "the quit never came after the pool emptied"
    assert shutdown.finished


def test_a_sweep_that_has_already_begun_stops_when_the_seal_lands(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancellation has to reach work **already running**, and this control has to be able to tell.

    **The earlier version of this test could not** (`T289-R21`, third pass). It sealed the pool and
    *then* called `run()`, so the task was cancelled before its first line — moving the checkpoint
    back to the task's entry would have left every assertion green, and the control therefore said
    nothing about the distinction it was written for.

    So the sweep is started on a thread of its own and blocked **inside its first unlink**; the
    seal lands from the test thread while it is in that call; then it is released. The one file it
    was already deleting goes, and the checkpoint at the top of the next iteration has to stop the
    other forty-nine. Removing exactly one is what proves both halves: the sweep really does
    delete, and it really did stop.
    """
    directory = tmp_path / "thumbnails"
    directory.mkdir()
    for index in range(50):
        (directory / f"{index:02d}.jpg").write_bytes(b"x")

    inside_the_first_unlink = threading.Event()
    sealed = threading.Event()
    real_unlink = Path.unlink

    def blocking_unlink(self: Path, *args: Any, **kwargs: Any) -> None:
        # Only this directory's files, and only the first of them: everything else in the process
        # — the temp-directory fixtures included — must go on deleting normally.
        if self.parent == directory and not inside_the_first_unlink.is_set():
            inside_the_first_unlink.set()
            sealed.wait(timeout=30)
        real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", blocking_unlink)

    gate = thumbnails.pool()
    sweep = thumbnails._SweepTask(thumbnails._Sink(), directory, set())
    sweeping = threading.Thread(target=sweep.run)
    sweeping.start()
    try:
        assert inside_the_first_unlink.wait(timeout=10), "the sweep never reached a file to delete"
        gate.seal()
    finally:
        sealed.set()
        sweeping.join(timeout=30)
    assert not sweeping.is_alive(), "the sweep never finished"

    survivors = sorted(entry.name for entry in directory.iterdir())
    assert len(survivors) == 49, (
        f"the sweep removed {50 - len(survivors)} files. It should have removed exactly the one it "
        "was already inside when the seal landed: fewer means the sweep never deletes anything and "
        "this control proves nothing, more means cancellation did not reach a running sweep."
    )


def test_a_decode_that_has_already_begun_declines_to_publish(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The decode's own checkpoint, asserted from the transition rather than from a sealed start.

    Decoding is one uninterruptible call; publishing is a choice, and a cache the process is
    leaving is not worth writing into. **The control is the shape the sweep's is**: the task is
    started with the pool open, blocked inside the decode, sealed from the test thread while it is
    in there, and released. The first half of this test is the positive — the same task, left
    alone, does publish — because a test that only ever asserts an absence cannot tell a working
    checkpoint from a decode that never wrote anything in the first place.
    """
    from PySide6.QtGui import QImage

    # Encoded through a file rather than a `QBuffer`: `QBuffer(QByteArray())` keeps a pointer to a
    # temporary that Python frees immediately, and saving into it segfaulted this test.
    picture = QImage(4, 4, QImage.Format.Format_RGB32)
    picture.fill(0x336699)
    source = tmp_path / "source.png"
    assert picture.save(str(source))  # format inferred from the .png suffix
    data = source.read_bytes()
    url = "https://example.invalid/x.jpg"

    published = tmp_path / "cache" / "published.jpg"
    thumbnails._DecodeAndStore(thumbnails._Sink(), url, data, published).run()
    assert published.is_file(), "the undisturbed task published nothing, so the control is blind"

    began = threading.Event()
    sealed = threading.Event()

    class _SlowImage:
        """`QImage` seen through the two calls the task makes, with the decode held open."""

        def loadFromData(self, data: bytes) -> bool:  # noqa: N802  (Qt's own spelling)
            began.set()
            sealed.wait(timeout=30)
            return True

        def scaled(self, *args: Any) -> _SlowImage:
            return self

    monkeypatch.setattr(thumbnails, "QImage", _SlowImage)

    destination = tmp_path / "cache" / "picture.jpg"
    gate = thumbnails.pool()
    decoding = threading.Thread(
        target=thumbnails._DecodeAndStore(thumbnails._Sink(), url, data, destination).run
    )
    decoding.start()
    try:
        assert began.wait(timeout=10), "the decode never began"
        gate.seal()
    finally:
        sealed.set()
        decoding.join(timeout=30)
    assert not decoding.is_alive(), "the decode never finished"

    assert not destination.exists(), "a decode sealed while it was running published anyway"


def test_an_update_already_downloading_stops_at_its_next_checkpoint(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The state the review's probe measured — `cancelled=True`, `completed=False`, `active=1`.

    Entry-only cancellation reaches queued work and nothing that is already running, and an update
    is the longest-running thing on either pool. This one is **inside its download** when the seal
    lands: the wheel's second chunk is held until the test has sealed, so the checkpoint between
    chunks is the only thing that can end it.

    **It runs through `YtdlpService`, not through `install_latest` directly**, because the wiring is
    the part a mutation removes silently: an install handed no cancellation at all still downloads,
    still installs, and still passes every test written against the update module. The callable it
    was handed is asserted by identity.
    """
    directory = tmp_path / "ytdlp"
    (directory / "yt_dlp").mkdir(parents=True)
    (directory / "yt_dlp" / "sentinel.txt").write_text("the copy that was already here")

    # Not a real wheel: this download never reaches the extraction, and a zip here would only be a
    # second thing that could be wrong. Big enough to need several chunks.
    payload = b"\0" * (4 * ytdlp_update._CHUNK_BYTES)
    chosen = ytdlp_update.Release(
        version="2026.9.1",
        url="https://files.pythonhosted.org/yt_dlp-2026.9.1-py3-none-any.whl",
        digest=hashlib.sha256(payload).hexdigest(),
        filename="yt_dlp-2026.9.1-py3-none-any.whl",
    )

    downloading = threading.Event()
    sealed = threading.Event()

    class _HeldStream(io.BytesIO):
        """Serves the first chunk, then holds the second until the test has sealed the pool."""

        # `int | None`, matching `BufferedIOBase.read`: narrowing an override's argument
        # is a Liskov violation and `mypy` checks tests too.
        def read(self, size: int | None = -1, /) -> bytes:
            if downloading.is_set():
                sealed.wait(timeout=30)
            downloading.set()
            return super().read(size)

    @contextmanager
    def opener(url: str) -> Iterator[IO[bytes]]:
        yield _HeldStream(payload)

    handed: list[Any] = []
    real_install = ytdlp_update.install_latest

    def install_through_a_fake_index(
        directory: Path,
        open_url: Any = None,
        release: Any = None,
        cancelled: Any = None,
    ) -> Any:
        handed.append(cancelled)
        return real_install(directory, opener, release, cancelled)

    monkeypatch.setattr(ytdlp_service, "latest_release", lambda: chosen)
    monkeypatch.setattr(ytdlp_service, "install_latest", install_through_a_fake_index)

    gate = ytdlp_service.pool()
    service = ytdlp_service.YtdlpService(
        directory=directory, entry_point=lambda *_args, **_kwargs: None
    )
    refusals: list[str] = []
    service.failed.connect(refusals.append)

    service.install_latest_version()
    try:
        assert downloading.wait(timeout=10), "the download never started, so nothing was cancelled"
        gate.seal()
    finally:
        sealed.set()

    assert _pump(qapp, gate.is_empty), "the cancelled update never left the pool"
    assert _pump(qapp, lambda: bool(refusals)), "the cancelled update reported nothing"
    assert refusals == ["The application is closing."]
    assert handed == [ytdlp_service._the_pool_is_closing], (
        "the service ran an install that had no way to ask whether it should stop"
    )
    assert (directory / "yt_dlp" / "sentinel.txt").is_file(), "a stopped update lost the copy"
    assert not list(tmp_path.glob(f".{directory.name}.staging-*")), "the workspace was left behind"
    assert not service.busy


def test_a_wait_that_empties_the_pool_stops_its_confirmation_poll(
    qapp: QApplication, release: threading.Event
) -> None:
    """A gate waited to empty must not be left holding a live timer (`T-128`).

    `seal()` starts a `QTimer` owned by the gate, and only `_confirm` stops it — which is reached
    through the event loop. The paths that *wait* are exactly the ones with no event loop left, so
    a gate waited to empty and then dropped would leave a live timer on an object destroyed by
    whichever thread collects it. Qt warns and then follows a pointer into freed memory on some
    later tick; that fault cost an overnight soak and two core dumps to attribute the last time.

    The poll is asserted **running first**, because a test that only checks it is stopped would
    pass just as well against a seal that never started one.
    """
    from PySide6.QtCore import QTimer

    gate = thumbnails.pool()
    blocker = _Blocking(release)
    assert gate.start(blocker)
    assert blocker.started.wait(timeout=10)

    gate.seal()
    polls = gate.findChildren(QTimer)
    assert len(polls) == 1 and polls[0].isActive(), (
        "sealing a busy pool started no confirmation poll"
    )

    release.set()
    assert gate.wait_bounded(10_000), "the blocking task never finished"

    assert not polls[0].isActive(), (
        "the confirmation poll outlived the wait that emptied the pool, so the gate is a live "
        "timer on an object nothing is going to stop"
    )


def test_the_bypass_reports_an_overrun_and_goes_on_waiting(
    qapp: QApplication,
    release: threading.Event,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The threshold buys a diagnostic. It does not buy permission to tear the widgets down.

    **The previous version of this behaviour was the finding** (`T289-R21`, third pass): expiring
    the bound recorded `_pools_drained = False`, logged, and called `_leave()` anyway — which quit
    and closed the connection with `activeThreadCount() == 1`. Truthful bookkeeping describes the
    race; it does not sequence teardown, and returning from here is exactly what permits Qt to
    destroy the widget tree.

    So the blocker is released well past a 50 ms threshold: the warning must appear, *and* the pool
    must be empty by the time the bypass returns.
    """
    monkeypatch.setattr(application, "_POOL_EXIT_REPORT_AFTER_MS", 50)
    gate = thumbnails.pool()
    # Twenty times the threshold, held from the task's own start, so the overrun is a fact about
    # this run rather than a race between a wall-clock timer and the runner's setup speed.
    blocker = _HoldsBriefly(1.0)
    assert gate.start(blocker)
    assert blocker.started.wait(timeout=10)

    shutdown, app, _manager, _writer = _shutdown((gate,))
    with caplog.at_level(logging.WARNING, logger="tracksandtrails.app"):
        shutdown.stop_for_exit()

    assert "the exit is waiting for it" in caplog.text, "an exit that overran said nothing"
    assert gate.is_empty(), "the bypass returned with a pool task still running"
    assert gate.pool.activeThreadCount() == 0, "a thread outlived the bypass"
    assert shutdown._pools_drained, "the pools were drained; the state should say so"
    assert app.quits == 1
    assert shutdown.finished


def test_the_bypass_waits_for_every_pool_and_not_only_the_first(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pool that overran must not consume the wait the pool behind it needed.

    The aggregation was `all(pool.wait_bounded(...) for pool in self._pools)` — a generator, so the
    first false answer ended the expression and **the second pool was never waited at all**. A
    reviewer probe recorded the calls as `[1, 0]`. Both pools here are held past the threshold and
    released at different moments, and both must be empty when the bypass returns.
    """
    monkeypatch.setattr(application, "_POOL_EXIT_REPORT_AFTER_MS", 50)
    first, second = ytdlp_service.pool(), thumbnails.pool()
    # Each hold runs from its own task's start and both are far past the threshold, so the bypass
    # has to overrun on the first pool and then wait a second time for the one behind it.
    for gate, seconds in ((first, 1.0), (second, 2.0)):
        blocker = _HoldsBriefly(seconds)
        assert gate.start(blocker)
        assert blocker.started.wait(timeout=10)

    assert not first.is_empty() and not second.is_empty(), (
        "both pools finished before the bypass was even called, so this run proves nothing about "
        "the aggregation"
    )
    shutdown, app, _manager, _writer = _shutdown((first, second))
    shutdown.stop_for_exit()

    assert first.is_empty(), "the first pool was left running"
    assert second.is_empty(), "the second pool was never waited for"
    assert app.quits == 1
    assert shutdown.finished


def test_the_about_to_quit_bypass_waits_for_the_pools(
    qapp: QApplication, release: threading.Event
) -> None:
    """The path with no event loop left still may not leave a pool thread running.

    `stop_for_exit` is reached from `aboutToQuit`, where the asynchronous barrier cannot complete:
    `drained` arrives through a queued connection and nothing is left to deliver it. So this path
    waits, and the test asserts the pool is empty by the time it returns.
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


def test_the_service_hands_its_version_query_the_pools_cancellation(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The resolution half of the same wiring, which the update test does not cover.

    `resolve_in_a_child` polls its queue in slices against the cancellation it is handed, and a
    service that hands it none is a version query that goes on waiting up to ninety seconds into a
    shutdown. The seam is a keyword argument, so removing it is a one-token change that leaves
    every test of the resolver itself green — which is why it is asserted here by identity.
    """
    handed: list[Any] = []

    def recording(
        directory: Path, *, entry_point: Any = None, cancelled: Any = None
    ) -> ytdlp_service.Resolution:
        handed.append(cancelled)
        return ytdlp_service.Resolution(version="2026.9.1", source="bundled baseline")

    monkeypatch.setattr(ytdlp_service, "resolve_in_a_child", recording)
    service = ytdlp_service.YtdlpService(directory=tmp_path / "ytdlp")
    reported: list[Any] = []
    service.reported.connect(reported.append)

    service.refresh()

    assert _pump(qapp, lambda: bool(reported)), "the version query never reported"
    assert handed == [ytdlp_service._the_pool_is_closing], (
        "the service ran a version query that had no way to ask whether it should stop"
    )


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
