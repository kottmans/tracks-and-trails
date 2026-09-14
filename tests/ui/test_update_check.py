"""Help, Check for Updates, the quiet notice, and the preference behind it (`T-338`).

Driven through the production `AppUpdateService` with only its request replaced, so the pool, the
signals and the explicit-versus-automatic bookkeeping are the real ones.
"""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QMenu, QMessageBox, QPushButton

from tracks_and_trails import __version__
from tracks_and_trails.core.app_updates import CHECK_INTERVAL
from tracks_and_trails.downloader.app_release import AppRelease, AppReleaseError
from tracks_and_trails.downloader.app_update_service import (
    RETRY_AFTER_NO_ANSWER,
    AppUpdateService,
    DailyUpdateCheck,
)
from tracks_and_trails.ui.main_window import MainWindow

NEWER = AppRelease(
    version="99.0.0", page="https://github.com/kottmans/tracks-and-trails/releases/tag/v99.0.0"
)
SAME = AppRelease(version=__version__, page="unused")


def opened_box(window: MainWindow) -> QMessageBox:
    """The box a check opened. A function, so mypy does not narrow the property for good."""
    box = window.update_box
    assert box is not None, "no box was opened"
    return box


def answering(release: AppRelease) -> Callable[[], AppRelease]:
    return lambda: release


def failing() -> AppRelease:
    raise AppReleaseError("GitHub could not be reached. Check your connection and try again.")


@pytest.fixture
def opened() -> list[str]:
    return []


@pytest.fixture
def build(
    qapp: QApplication, tmp_path: Path, opened: list[str]
) -> Iterator[Callable[..., MainWindow]]:
    windows: list[MainWindow] = []

    def make(fetch: Callable[[], AppRelease], **overrides: object) -> MainWindow:
        window = MainWindow(
            tmp_path / "window.toml",
            app_updates=AppUpdateService(fetch),
            open_link=opened.append,
            **overrides,  # type: ignore[arg-type]
        )
        windows.append(window)
        return window

    yield make
    for window in windows:
        window.close()
    qapp.processEvents()


def test_the_help_menu_offers_the_check_above_about(build: Callable[..., MainWindow]) -> None:
    window = build(answering(SAME))
    # The `QAction` wrappers are held, or the `QMenu` wrapper is released mid-test (see
    # `test_main_window.file_menu`).
    held = window.menuBar().actions()
    help_menu = next(action.menu() for action in held if action.text() == "&Help")
    assert isinstance(help_menu, QMenu)
    items = help_menu.actions()
    assert [action.text() for action in items] == ["Check for &Updates...", "&About"]
    assert window.updates_action.isEnabled()


def test_the_check_is_disabled_where_nothing_can_answer_it(
    qapp: QApplication, tmp_path: Path
) -> None:
    window = MainWindow(tmp_path / "window.toml")
    try:
        assert not window.updates_action.isEnabled()
        window.check_for_updates()
        assert window.update_box is None
    finally:
        window.close()


def test_asking_when_a_newer_version_is_out_offers_its_page(
    build: Callable[..., MainWindow], spin: Callable[..., bool], opened: list[str]
) -> None:
    window = build(answering(NEWER))
    window.updates_action.trigger()
    assert spin(lambda: window.update_box is not None)
    box = window.update_box
    assert box is not None
    assert box.text() == "Tracks & Trails 99.0.0 is available."
    assert box.informativeText() == f"You have version {__version__}."
    download = next(
        button for button in box.findChildren(QPushButton) if button.text() == "Open Download Page"
    )
    assert box.defaultButton() is download
    download.click()
    assert opened == [NEWER.page]
    assert not window.update_notice.isHidden()
    box.close()


def test_asking_when_this_is_the_newest_says_so(
    build: Callable[..., MainWindow], spin: Callable[..., bool], opened: list[str]
) -> None:
    window = build(answering(SAME))
    window.check_for_updates()
    assert spin(lambda: window.update_box is not None)
    box = window.update_box
    assert box is not None
    assert box.text() == "You have the latest version of Tracks & Trails."
    assert window.update_notice.isHidden()
    assert opened == []
    box.close()


def test_asking_without_a_connection_says_why(
    build: Callable[..., MainWindow], spin: Callable[..., bool]
) -> None:
    window = build(failing)
    window.check_for_updates()
    assert spin(lambda: window.update_box is not None)
    box = window.update_box
    assert box is not None
    assert box.icon() == QMessageBox.Icon.Warning
    assert box.text() == "Couldn't check for updates."
    assert "Check your connection" in box.informativeText()
    box.close()


def test_an_automatic_check_that_finds_a_release_only_shows_the_notice(
    build: Callable[..., MainWindow], spin: Callable[..., bool], opened: list[str]
) -> None:
    """No box at launch: somebody opened the application to download something."""
    window = build(answering(NEWER))
    service = window._app_updates
    assert service is not None
    service.check(explicit=False)
    assert spin(lambda: not window.update_notice.isHidden())
    assert window.update_notice.text() == "Version 99.0.0 is available"
    assert window.update_notice.accessibleName() == "Version 99.0.0 is available"
    assert window.update_box is None
    window.update_notice.click()
    box = opened_box(window)
    assert box.text() == "Tracks & Trails 99.0.0 is available."
    assert opened == []
    box.close()


@pytest.mark.parametrize("fetch", [answering(SAME), failing])
def test_an_automatic_check_with_nothing_to_say_says_nothing(
    build: Callable[..., MainWindow],
    spin: Callable[..., bool],
    fetch: Callable[[], AppRelease],
) -> None:
    window = build(fetch)
    service = window._app_updates
    assert service is not None
    service.check(explicit=False)
    assert spin(lambda: not service.busy)
    QApplication.processEvents()
    assert window.update_box is None
    assert window.update_notice.isHidden()


def test_asking_while_an_automatic_check_runs_shows_that_checks_answer(
    build: Callable[..., MainWindow], spin: Callable[..., bool]
) -> None:
    """One request, two audiences: the press marks the request in flight as asked for."""
    calls: list[int] = []

    def counted() -> AppRelease:
        calls.append(1)
        return SAME

    window = build(counted)
    service = window._app_updates
    assert service is not None
    service.check(explicit=False)
    window.check_for_updates()
    assert spin(lambda: window.update_box is not None)
    assert calls == [1]
    box = window.update_box
    assert box is not None
    box.close()


def test_the_preference_is_on_the_screen_and_reaches_its_writer(
    build: Callable[..., MainWindow], qapp: QApplication, tmp_path: Path
) -> None:
    chosen: list[bool] = []
    window = build(
        answering(SAME),
        output_directory=tmp_path / "downloads",
        theme="light",
        on_directory_chosen=lambda _directory: None,
        on_theme_chosen=lambda _name: None,
        check_for_updates=True,
        on_update_checks_chosen=chosen.append,
    )
    screen = window.open_settings()
    assert screen is not None
    choice = screen.findChild(QCheckBox, "checkForUpdates")
    assert choice is not None
    assert choice.isChecked() and choice.isEnabled()
    assert choice.text() == "Check for updates automatically"
    # The maintainer's rule for on-screen text: no en or em dashes.
    assert "\u2014" not in choice.toolTip() and "\u2013" not in choice.toolTip()
    choice.click()
    assert chosen == [False]
    screen.close()
    qapp.processEvents()

    reopened = window.open_settings()
    assert reopened is not None
    again = reopened.findChild(QCheckBox, "checkForUpdates")
    assert again is not None and not again.isChecked(), "reopening forgot the choice"
    reopened.close()


def test_the_preference_is_disabled_without_a_writer(
    build: Callable[..., MainWindow], tmp_path: Path
) -> None:
    window = build(
        answering(SAME),
        output_directory=tmp_path / "downloads",
        theme="light",
        on_directory_chosen=lambda _directory: None,
        on_theme_chosen=lambda _name: None,
    )
    screen = window.open_settings()
    assert isinstance(screen, QDialog)
    choice = screen.findChild(QCheckBox, "checkForUpdates")
    assert choice is not None and not choice.isEnabled()
    screen.close()


# --- T338-R1: the daily schedule, decided when it fires ------------------------------------------


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 14, 9, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def schedule(qapp: QApplication) -> Iterator[Callable[..., tuple[DailyUpdateCheck, list[int]]]]:
    made: list[DailyUpdateCheck] = []

    def make(
        fetch: Callable[[], AppRelease] | None = None,
        *,
        enabled: Callable[[], bool] = lambda: True,
        record: list[datetime | None] | None = None,
        clock: _Clock | None = None,
    ) -> tuple[DailyUpdateCheck, list[int]]:
        requests: list[int] = []
        answer = fetch or answering(SAME)

        def counted() -> AppRelease:
            requests.append(1)
            return answer()

        service = AppUpdateService(counted)
        stamps: list[datetime | None] = record if record is not None else [None]
        timer_clock = clock or _Clock()
        # The composition's recorder, first, as `compose` connects it.
        service.answered.connect(lambda *_: stamps.__setitem__(0, timer_clock()))
        daily = DailyUpdateCheck(
            service, enabled=enabled, last_checked=lambda: stamps[0], now=timer_clock
        )
        made.append(daily)
        return daily, requests

    yield make
    for daily in made:
        daily.stop()


def _pending(daily: DailyUpdateCheck) -> timedelta | None:
    """A function, so mypy does not narrow the property for the rest of a test."""
    return daily.pending_in


def _fire(daily: DailyUpdateCheck) -> None:
    """What the timer does when it fires, without waiting for it."""
    daily._timer.timeout.emit()


def test_a_launch_inside_the_day_schedules_the_check_for_when_it_is_due(
    schedule: Callable[..., tuple[DailyUpdateCheck, list[int]]], spin: Callable[..., bool]
) -> None:
    clock = _Clock()
    daily, requests = schedule(record=[clock.now - timedelta(hours=20)], clock=clock)
    daily.start()
    _fire(daily)
    assert not spin(lambda: bool(requests), timeout=0.5), "a check inside the day was sent"
    pending = _pending(daily)
    assert pending is not None and timedelta(hours=3, minutes=59) < pending <= timedelta(
        hours=4, seconds=1
    )


def test_an_application_left_open_checks_again_the_next_day(
    schedule: Callable[..., tuple[DailyUpdateCheck, list[int]]], spin: Callable[..., bool]
) -> None:
    clock = _Clock()
    daily, requests = schedule(clock=clock)
    daily.start()
    _fire(daily)
    assert spin(lambda: requests == [1] and not daily._service.busy)
    pending = _pending(daily)
    assert pending is not None and pending > CHECK_INTERVAL - timedelta(minutes=1)

    clock.now += CHECK_INTERVAL
    _fire(daily)
    assert spin(lambda: requests == [1, 1]), "no second check a day later without a relaunch"


def test_an_answer_asked_for_before_the_delay_moves_the_automatic_check(
    schedule: Callable[..., tuple[DailyUpdateCheck, list[int]]], spin: Callable[..., bool]
) -> None:
    daily, requests = schedule()
    daily.start()
    daily._service.check(explicit=True)
    assert spin(lambda: requests == [1] and not daily._service.busy)
    _fire(daily)
    assert requests == [1], "the automatic check asked again straight after a manual answer"
    pending = _pending(daily)
    assert pending is not None and pending > CHECK_INTERVAL - timedelta(minutes=1)


def test_a_check_without_an_answer_is_tried_again_within_the_hour(
    schedule: Callable[..., tuple[DailyUpdateCheck, list[int]]], spin: Callable[..., bool]
) -> None:
    daily, requests = schedule(failing)
    daily.start()
    _fire(daily)
    assert spin(lambda: requests == [1] and not daily._service.busy)
    pending = _pending(daily)
    # A very coarse timer rounds to whole seconds, so a second of slack either way.
    assert pending is not None and pending <= RETRY_AFTER_NO_ANSWER + timedelta(seconds=1)


def test_switching_off_cancels_and_switching_on_reschedules(
    schedule: Callable[..., tuple[DailyUpdateCheck, list[int]]], spin: Callable[..., bool]
) -> None:
    allowed = [True]
    daily, requests = schedule(enabled=lambda: allowed[0])
    daily.start()
    assert _pending(daily) is not None
    allowed[0] = False
    daily.preference_changed(False)
    assert _pending(daily) is None
    _fire(daily)
    # Waited for: the request is made on a pool thread, so an immediate look would see nothing.
    assert not spin(lambda: bool(requests), timeout=0.5), (
        "a timer that fired after switching off still asked"
    )
    allowed[0] = True
    daily.preference_changed(True)
    assert _pending(daily) is not None


def test_a_stopped_schedule_never_fires_again(
    schedule: Callable[..., tuple[DailyUpdateCheck, list[int]]], spin: Callable[..., bool]
) -> None:
    daily, requests = schedule()
    daily.start()
    daily.stop()
    assert _pending(daily) is None
    daily.start()
    _fire(daily)
    assert not spin(lambda: bool(requests), timeout=0.5)
    assert _pending(daily) is None
