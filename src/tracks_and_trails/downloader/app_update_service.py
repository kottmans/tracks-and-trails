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
from typing import Final

from PySide6.QtCore import QObject, QRunnable, Signal

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


__all__ = ["AppRelease", "AppReleaseError", "AppUpdateService", "pool"]
