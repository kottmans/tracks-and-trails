"""Runs the release check off the GUI thread and reports what it learned (`T-338`).

The same shape as `ytdlp_service`, for its reasons: a module-level pool behind the shutdown gate
(`T118-R13`, `T289-R21`), a parentless sink the running task owns, and nothing escaping `run`.

**Its own pool, not yt-dlp's.** That pool runs one operation at a time and refuses a second, so an
automatic check at launch would have made a press of *Check for updates* in the yt-dlp section
answer "another operation is still running" about something the user never started.

**Explicit and automatic are one request with two audiences.** A press while an automatic check is
already on its way does not start a second request; it marks the one in flight as asked for, so its
answer is shown rather than kept quiet.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Final

from PySide6.QtCore import QObject, QRunnable, Qt, QTimer, Signal

from tracks_and_trails.core.app_updates import CHECK_INTERVAL, check_is_due
from tracks_and_trails.downloader.app_release import AppRelease, AppReleaseError, latest_app_release
from tracks_and_trails.downloader.pools import SealedPool

_POOL_THREADS: Final = 1

_SHARED_POOL: SealedPool | None = None


def pool() -> SealedPool:
    """The shared pool for release checks, created once and sealed at shutdown."""
    global _SHARED_POOL
    if _SHARED_POOL is None:
        _SHARED_POOL = SealedPool(_POOL_THREADS)
    return _SHARED_POOL


class _Sink(QObject):
    """What a running check emits through, owned by the task (`T118-R13`)."""

    answered = Signal(object)
    failed = Signal(str)


class _Task(QRunnable):
    """One check on the pool, with every failure turned into a sentence."""

    def __init__(self, sink: _Sink, fetch: Callable[[], AppRelease]) -> None:
        super().__init__()
        self._sink = sink
        self._fetch = fetch

    def run(self) -> None:
        if pool().cancelled:
            self._sink.failed.emit("The application is closing.")
            return
        try:
            self._sink.answered.emit(self._fetch())
        except AppReleaseError as error:
            self._sink.failed.emit(str(error))
        # Broad for `ytdlp_service._Task`'s reason: a pool thread has nowhere else to report.
        except Exception as error:
            self._sink.failed.emit(f"The check could not be completed ({type(error).__name__}).")


class AppUpdateService(QObject):
    """The GUI's view of whether a newer release exists."""

    #: The newest `AppRelease`, and whether somebody asked for it.
    answered = Signal(object, bool)
    #: Why the check did not answer, and whether somebody asked for it.
    failed = Signal(str, bool)

    def __init__(
        self,
        fetch: Callable[[], AppRelease] = latest_app_release,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        #: The request itself, injected so tests never reach GitHub.
        self._fetch = fetch
        self._running: _Task | None = None
        self._explicit = False

    @property
    def busy(self) -> bool:
        return self._running is not None

    def check(self, *, explicit: bool) -> None:
        """Ask for the newest release. `explicit` when a person asked, so the answer is shown."""
        self._explicit = self._explicit or explicit
        if self._running is not None:
            return
        sink = _Sink()
        sink.answered.connect(self._on_answered)
        sink.failed.connect(self._on_failed)
        task = _Task(sink, self._fetch)
        if not pool().start(task):
            self._on_failed("The application is closing.")
            return
        # Held so Python does not collect the task while it runs (`ytdlp_service._running`).
        self._running = task

    def _finish(self) -> bool:
        explicit = self._explicit
        self._running = None
        self._explicit = False
        return explicit

    def _on_answered(self, release: object) -> None:
        self.answered.emit(release, self._finish())

    def _on_failed(self, reason: str) -> None:
        self.failed.emit(reason, self._finish())


#: How long after the window appears the first automatic check may start. Late enough that it costs
#: nothing a user waits for at launch (`NFR-002`, `NFR-010`).
FIRST_CHECK_DELAY: Final = timedelta(seconds=5)

#: When a check did not answer, how long before trying again while the application stays open.
#: An hour: soon enough that a laptop that came back online is told the same day, rare enough that
#: an offline machine does not knock on GitHub's door all afternoon.
RETRY_AFTER_NO_ANSWER: Final = timedelta(hours=1)


class DailyUpdateCheck(QObject):
    """The automatic check's schedule, for as long as the application runs (`T-338`, `T338-R1`).

    **Decided when it fires, not when it was set.** The first version was one `singleShot` at
    launch that captured the preference: switching it off during the delay still sent the request,
    and an application left open never checked again. This owns one timer. When it fires, it asks
    the preference and the record of the last answer *then*; it checks only when both allow, and
    it always sets the timer for the next moment a check could be due.

    **An answer from anywhere moves the next check**: a press of *Check for Updates* before the
    first delay expires is recorded, so the automatic check finds it not due and waits a day from
    that answer instead of asking again.
    """

    def __init__(
        self,
        service: AppUpdateService,
        *,
        enabled: Callable[[], bool],
        last_checked: Callable[[], datetime | None],
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._enabled = enabled
        self._last_checked = last_checked
        self._now = now
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.TimerType.VeryCoarseTimer)
        self._timer.timeout.connect(self._fire)
        self._stopped = False
        service.answered.connect(self._after_a_check)
        service.failed.connect(self._after_a_check)

    @property
    def pending_in(self) -> timedelta | None:
        """How long until the timer fires, or `None` when nothing is scheduled."""
        if not self._timer.isActive():
            return None
        return timedelta(milliseconds=self._timer.remainingTime())

    def start(self) -> None:
        """Begin: the first chance comes after `FIRST_CHECK_DELAY`."""
        if self._stopped or not self._enabled():
            return
        self._arm(FIRST_CHECK_DELAY)

    def preference_changed(self, enabled: bool) -> None:
        """Switched off cancels what is pending; switched on schedules the next chance."""
        if not enabled:
            self._timer.stop()
        else:
            self.start()

    def stop(self) -> None:
        """For good: the application is going away."""
        self._stopped = True
        self._timer.stop()

    def _fire(self) -> None:
        if self._stopped or pool().sealed or not self._enabled():
            return
        now = self._now()
        previous = self._last_checked()
        if not check_is_due(previous, now):
            assert previous is not None
            self._arm(previous + CHECK_INTERVAL - now)
            return
        # The answer, or the failure, re-arms the timer in `_after_a_check`.
        self._service.check(explicit=False)

    def _after_a_check(self, *_: object) -> None:
        """Set the next chance after any check ends, automatic or asked for."""
        if self._stopped or pool().sealed or not self._enabled():
            return
        now = self._now()
        previous = self._last_checked()
        if previous is not None and not check_is_due(previous, now):
            self._arm(previous + CHECK_INTERVAL - now)
        else:
            self._arm(RETRY_AFTER_NO_ANSWER)

    def _arm(self, wait: timedelta) -> None:
        self._timer.start(max(0, int(wait.total_seconds() * 1000)))


__all__ = [
    "AppRelease",
    "AppReleaseError",
    "AppUpdateService",
    "DailyUpdateCheck",
    "pool",
]
