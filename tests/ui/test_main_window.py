"""Shell window behavior (`T-007`).

Covers the acceptance criteria that can be asserted rather than looked at: the window
constructs and closes offscreen, carries the icon and title, exposes both menu actions, and
round-trips its geometry. Whether the icon *looks* right in a real Windows taskbar is not
automatable and stays an `OPS-003` known gap.
"""

from pathlib import Path

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QMessageBox

from tracks_and_trails import __version__
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import DownloadRequest, Job
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.ui.main_window import (
    _MAX_COORD,
    APP_NAME,
    APP_SLUG,
    DEFAULT_SIZE,
    MainWindow,
    app_icon,
    geometry_path,
    load_geometry,
    moved_onto_a_screen,
    save_geometry,
)


@pytest.fixture
def window(qapp: QApplication, tmp_path: Path) -> MainWindow:
    """A window whose geometry file is redirected into `tmp_path`.

    Never touches the real config directory: a test that writes to `user_config_dir` would
    move the developer's actual window on their next launch.
    """
    return MainWindow(geometry_file=tmp_path / "window.toml")


def test_window_constructs_and_closes_offscreen(window: MainWindow) -> None:
    """The `pytest-qt` criterion: construct and close with no display."""
    window.show()
    assert window.isVisible()
    assert window.close()
    assert not window.isVisible()


def test_window_has_the_application_title_and_icon(window: MainWindow) -> None:
    assert window.windowTitle() == APP_NAME
    assert not window.windowIcon().isNull()
    assert sorted(s.width() for s in window.windowIcon().availableSizes()) == [
        16,
        24,
        32,
        48,
        64,
        128,
        256,
    ]


def test_menu_bar_exposes_quit_and_about(window: MainWindow) -> None:
    titles = {menu.title() for menu in window.menuBar().findChildren(QMenu)}
    assert {"&File", "&Help"} <= titles

    names = {action.objectName() for action in window.findChildren(QAction)}
    assert {"actionQuit", "actionAbout"} <= names


def test_every_action_carries_an_accessibility_label(window: MainWindow) -> None:
    """`NFR-005` requires screen-reader labels on all controls, not just visible text."""
    actions = {action.objectName(): action for action in window.findChildren(QAction)}
    for name in ("actionQuit", "actionAbout"):
        assert actions[name].text(), f"{name} has no visible text"
        assert actions[name].statusTip(), f"{name} has no status tip for assistive technology"


def test_about_box_shows_the_icon_and_version(window: MainWindow) -> None:
    about = window.show_about()
    try:
        assert isinstance(about, QMessageBox)
        assert __version__ in about.text()
        assert APP_NAME in about.text()
        assert not about.iconPixmap().isNull(), "the About box must show the app icon (T-007)"
    finally:
        about.close()


def test_default_size_is_used_when_nothing_is_stored(qapp: QApplication, tmp_path: Path) -> None:
    window = MainWindow(geometry_file=tmp_path / "absent.toml")
    assert window.size() == DEFAULT_SIZE


def test_geometry_round_trips_across_restarts(qapp: QApplication, tmp_path: Path) -> None:
    """The acceptance criterion: geometry persists across restarts."""
    path = tmp_path / "window.toml"
    first = MainWindow(geometry_file=path)
    first.setGeometry(120, 80, 1024, 720)
    first.close()
    assert path.is_file(), "closing the window must write its geometry"

    second = MainWindow(geometry_file=path)
    assert second.geometry().width() == 1024
    assert second.geometry().height() == 720
    assert second.geometry().x() == 120
    assert second.geometry().y() == 80


@pytest.mark.parametrize(
    "content",
    [
        "",
        "not toml at all {{{",
        "[window]\n",
        "[window]\nx = 1\ny = 2\n",
        '[window]\nx = "left"\ny = 0\nwidth = 10\nheight = 10\n',
        "[window]\nx = 0\ny = 0\nwidth = 0\nheight = 500\n",
        "[window]\nx = 0\ny = 0\nwidth = -900\nheight = 500\n",
        "window = 5\n",
    ],
    ids=[
        "empty",
        "malformed",
        "no-keys",
        "missing-keys",
        "wrong-type",
        "zero-width",
        "negative-width",
        "wrong-shape",
    ],
)
def test_unusable_geometry_falls_back_instead_of_crashing(
    qapp: QApplication, tmp_path: Path, content: str
) -> None:
    """A damaged config file must not stop the application starting."""
    path = tmp_path / "window.toml"
    path.write_text(content, encoding="utf-8")
    assert load_geometry(path) is None
    assert MainWindow(geometry_file=path).size() == DEFAULT_SIZE


def test_saving_to_an_unwritable_location_does_not_raise(
    qapp: QApplication, tmp_path: Path
) -> None:
    """Failing to persist a window position must not turn a clean exit into a crash."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    window = QMainWindow()
    save_geometry(window, blocker / "nested" / "window.toml")


def test_app_icon_loads(qapp: QApplication) -> None:
    assert not app_icon().isNull()


def test_config_directory_is_not_doubled(qapp: QApplication) -> None:
    """`ARCHITECTURE.md` §5 specifies `user_config_dir/tracksandtrails/window.toml`.

    platformdirs inserts an author segment on Windows unless `appauthor=False`, defaulting it
    to the app name and producing `...\\tracksandtrails\\tracksandtrails\\`. That is invisible
    on Linux, so it needs asserting rather than eyeballing on the platform it breaks.
    """
    path = geometry_path()
    assert path.name == "window.toml"
    assert path.parent.name == APP_SLUG
    assert path.parent.parent.name != APP_SLUG, f"config directory is doubled: {path}"


# --- T-027: stored geometry is untrusted input -------------------------------------------
#
# Every case below was confirmed to fail against 2d06153 before the fix: `inf`, the huge
# integer and the int32 overflow all raised OverflowError out of a function documented never
# to raise, TOML booleans were silently accepted as 1/0, and an off-screen rectangle was
# restored verbatim, leaving the window unreachable.


@pytest.mark.parametrize(
    ("case", "content"),
    [
        ("inf-width", "[window]\nx = 0\ny = 0\nwidth = inf\nheight = 480\n"),
        ("nan-x", "[window]\nx = nan\ny = 0\nwidth = 640\nheight = 480\n"),
        ("huge-int", "[window]\nx = 0\ny = 0\nwidth = 99999999999999999999\nheight = 480\n"),
        ("int32-overflow-x", "[window]\nx = 3000000000\ny = 0\nwidth = 640\nheight = 480\n"),
        ("int32-underflow-y", "[window]\nx = 0\ny = -3000000000\nwidth = 640\nheight = 480\n"),
        ("bool-coordinates", "[window]\nx = true\ny = false\nwidth = 640\nheight = 480\n"),
        ("bool-size", "[window]\nx = 0\ny = 0\nwidth = true\nheight = true\n"),
        ("float-size", "[window]\nx = 0\ny = 0\nwidth = 640.5\nheight = 480.5\n"),
        ("string-size", '[window]\nx = 0\ny = 0\nwidth = "640"\nheight = "480"\n'),
        ("unusably-small", "[window]\nx = 0\ny = 0\nwidth = 1\nheight = 1\n"),
    ],
)
def test_hostile_geometry_falls_back_without_raising(
    qapp: QApplication, tmp_path: Path, case: str, content: str
) -> None:
    """`load_geometry` must never raise, and must not hand Qt a value it cannot take."""
    path = tmp_path / "window.toml"
    path.write_text(content, encoding="utf-8")
    assert load_geometry(path) is None, f"{case} should have been rejected"
    assert MainWindow(geometry_file=path).size() == DEFAULT_SIZE


@pytest.mark.parametrize(
    ("case", "x", "y"),
    [
        ("x-at-int32-min", -(2**31), 0),
        ("x-at-int32-max", 2**31 - 1, 0),
        ("y-at-int32-min", 0, -(2**31)),
        ("y-at-int32-max", 0, 2**31 - 1),
        ("both-extreme", -(2**31), 2**31 - 1),
        ("just-past-the-bound", _MAX_COORD + 1, 0),
    ],
)
def test_extreme_coordinates_never_strand_the_window(
    qapp: QApplication, tmp_path: Path, case: str, x: int, y: int
) -> None:
    """Restoration, not just loading — which is what the earlier boundary test missed.

    `P0-R1`: values inside int32 individually still overflow Qt's own rectangle arithmetic.
    At `y = 2**31 - 1`, `QRect.bottom()` wrapped to a large *negative*, `intersects()` reported
    the rectangle as touching a screen, the recovery never fired, and the window was restored
    where it could never be clicked. Asserting on `load_geometry` alone could not see that,
    because the damage happened after loading succeeded.
    """
    path = tmp_path / "window.toml"
    path.write_text(f"[window]\nx = {x}\ny = {y}\nwidth = 640\nheight = 480\n", encoding="utf-8")
    geometry = MainWindow(geometry_file=path).geometry()
    assert any(
        screen.availableGeometry().intersects(geometry) for screen in QGuiApplication.screens()
    ), f"{case} restored to {geometry}, which no screen can show"


def test_the_largest_usable_coordinate_still_round_trips(
    qapp: QApplication, tmp_path: Path
) -> None:
    """The bound must not be so tight that legitimate multi-monitor offsets are discarded."""
    path = tmp_path / "window.toml"
    x = _MAX_COORD - 640
    path.write_text(f"[window]\nx = {x}\ny = 0\nwidth = 640\nheight = 480\n", encoding="utf-8")
    assert load_geometry(path) == {"x": x, "y": 0, "width": 640, "height": 480}


def test_ordinary_negative_coordinates_still_restore(qapp: QApplication, tmp_path: Path) -> None:
    """A window on a monitor left of the primary has negative x. That is normal, not hostile."""
    path = tmp_path / "window.toml"
    path.write_text("[window]\nx = -40\ny = -20\nwidth = 800\nheight = 600\n", encoding="utf-8")
    geometry = MainWindow(geometry_file=path).geometry()
    assert (geometry.x(), geometry.y()) == (-40, -20)
    assert (geometry.width(), geometry.height()) == (800, 600)


def test_geometry_with_no_screen_left_to_show_it_is_recovered(
    qapp: QApplication, tmp_path: Path
) -> None:
    """Unplugging a monitor must not strand the only window where it cannot be clicked."""
    path = tmp_path / "window.toml"
    path.write_text(
        "[window]\nx = 999999\ny = 999999\nwidth = 640\nheight = 480\n", encoding="utf-8"
    )
    geometry = MainWindow(geometry_file=path).geometry()
    assert any(
        screen.availableGeometry().intersects(geometry) for screen in QGuiApplication.screens()
    ), f"restored at {geometry} which no screen can show"


def test_a_rect_already_on_screen_is_left_alone(qapp: QApplication) -> None:
    """The recovery must not move windows that were fine."""
    available = QGuiApplication.primaryScreen().availableGeometry()
    rect = QRect(available.x() + 10, available.y() + 10, 400, 300)
    assert moved_onto_a_screen(rect) == rect


# --- T-080: the queue's pause toggle and the selected job's remove action ------------------


def test_the_queue_actions_exist_only_with_the_control_bar(qapp: QApplication) -> None:
    """`T-007`'s bare window still opens, and offers neither action.

    The all-or-nothing rule the add-URL action follows: a window holding half of what an action
    needs could only offer one that fails. A window built with no `concurrency` has no toolbar, so
    it has no queue actions either — and `T-007`'s tests construct exactly that window.
    """
    bare = MainWindow()
    assert bare.pause_action is None
    assert bare.remove_action is None

    equipped = MainWindow(concurrency=3)
    assert equipped.pause_action is not None
    assert equipped.remove_action is not None


def test_pausing_reports_once_and_says_which_way(qapp: QApplication) -> None:
    """The toggle reports the state it moved to, and reports it exactly once per change.

    `toggled` rather than `triggered`: a checkable action fires `triggered` on every activation
    including the ones that do not change the state, and a queue asked to pause twice would be a
    manager call the second press did not earn.
    """
    reported: list[bool] = []
    window = MainWindow(concurrency=3, on_pause_changed=reported.append)
    action = window.pause_action
    assert action is not None

    action.setChecked(True)
    assert reported == [True]

    action.setChecked(False)
    assert reported == [True, False]

    # Setting it to what it already is changes nothing, so it says nothing.
    action.setChecked(False)
    assert reported == [True, False], "an unchanged toggle reported a change"


def test_showing_the_pause_state_does_not_report_it_back(qapp: QApplication) -> None:
    """`T-080`: the manager telling the control must not become the control telling the manager.

    Composition connects `DownloadManager.queue_paused` to `show_queue_paused`, so without blocking
    signals the round trip is control → manager → control → manager. The assertion is on the
    handler never firing, which is the half a `setChecked` that merely *looks* right would fail.
    """
    reported: list[bool] = []
    window = MainWindow(concurrency=3, on_pause_changed=reported.append)
    action = window.pause_action
    assert action is not None

    window.show_queue_paused(True)

    assert action.isChecked(), "the control did not follow the queue"
    assert reported == [], (
        "reflecting the queue's state called back into the queue; that round trip is how a toggle "
        "ends up fighting itself"
    )

    window.show_queue_paused(False)
    assert not action.isChecked()
    assert reported == []


def test_remove_is_offered_only_when_something_is_selected(qapp: QApplication) -> None:
    """An action that needs a selection starts disabled, and a press with none does nothing.

    Both halves, because they fail differently: the enabled state is what the user sees, and the
    handler's own guard is what a keyboard shortcut would otherwise walk straight past.
    """
    asked: list[str] = []
    window = MainWindow(concurrency=3, on_remove_requested=asked.append)
    action = window.remove_action
    assert action is not None

    assert not action.isEnabled(), "Remove was offered with nothing selected"

    # **Enabled first, deliberately.** `QAction.trigger()` on a disabled action is a no-op, so
    # triggering it while disabled asserts Qt's behaviour and not this window's — the first
    # version of this test did exactly that and survived a mutation removing the handler's own
    # guard. Enabling it reproduces the state the guard exists for: the action's enabled state and
    # the table's selection disagreeing, which is one stale signal or one shortcut away.
    action.setEnabled(True)
    action.trigger()
    assert asked == [], (
        "Remove acted with nothing selected. The enabled state is what the user sees; the "
        "handler's own check is what a keyboard shortcut walks past"
    )


# --- T-081: reordering the queue, and clearing the finished jobs --------------------------


class _FakeQueue:
    """A `QueueReader` over a fixed list of jobs, in the order a table would show them."""

    def __init__(self, jobs: list[Job]) -> None:
        self._jobs = jobs

    def get(self, job_id: str) -> Job | None:
        return next((job for job in self._jobs if job.id == job_id), None)

    def all_jobs(self) -> list[Job]:
        return list(self._jobs)


def _job(job_id: str, position: int, status: JobStatus = JobStatus.QUEUED) -> Job:
    request = DownloadRequest(
        url="https://example.invalid/clip",
        output_directory="/downloads",
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )
    return Job(
        id=job_id,
        url=request.url,
        request=request,
        status=status,
        queue_position=position,
    )


def _window_over(jobs: list[Job], **handlers: object) -> MainWindow:
    manager = DownloadManager(_EmptyJobStore(), concurrency=1)
    return MainWindow(concurrency=1, manager=manager, queue=_FakeQueue(jobs), **handlers)  # type: ignore[arg-type]


class _EmptyJobStore:
    """The narrowest thing `DownloadManager` will accept; nothing here starts a job."""

    def get(self, job_id: str) -> Job | None:
        return None

    def update(self, job: Job, done: object) -> None: ...
    def complete(self, job: Job, format_used: object, done: object) -> None: ...
    def requeue_at_end(self, job: Job, done: object) -> None: ...
    def remove(self, job_id: str, done: object) -> None: ...
    def reorder(self, job_ids: object, done: object) -> None: ...
    def clear_completed(self, done: object) -> None: ...


def test_moving_a_job_sends_the_whole_new_order(qapp: QApplication) -> None:
    """`REQ-016`: the window hands over the order it wants, not "move this one".

    `JobRepository.reorder` redeals the positions the named jobs hold, so the caller that knows
    what the user is looking at supplies the arrangement. A delta would make the repository infer
    it from a position it did not choose.
    """
    asked: list[list[str]] = []
    window = _window_over(
        [_job("a", 0), _job("b", 1), _job("c", 2)],
        on_reorder_requested=asked.append,
    )
    assert window.queue_view is not None
    window.queue_view.select("c")

    assert window.move_up_action is not None
    window.move_up_action.trigger()

    assert asked == [["a", "c", "b"]], (
        f"sent {asked}; moving `c` up swaps it with `b` and leaves `a` where it was"
    )


def test_moving_across_a_running_job_moves_the_pending_pair(qapp: QApplication) -> None:
    """`T-081`: a running job's position is not a promise the pool can keep, so it is not moved.

    **The running job sits between the two pending ones**, which is the arrangement that tells a
    correct implementation from one that swaps with `index ± 1` in the table. The repository
    *refuses* to reorder a running job, so naming it here would turn a legal move into an error the
    user did not cause.
    """
    asked: list[list[str]] = []
    window = _window_over(
        [_job("a", 0), _job("busy", 1, JobStatus.RUNNING), _job("c", 2)],
        on_reorder_requested=asked.append,
    )
    assert window.queue_view is not None
    window.queue_view.select("c")

    assert window.move_up_action is not None
    window.move_up_action.trigger()

    assert asked == [["c", "a"]], (
        f"sent {asked}; the running job must not be named, and `c` moving up past it means `c` "
        "and `a` swap"
    )


def test_the_move_actions_are_not_offered_for_a_running_job(qapp: QApplication) -> None:
    """An action that is offered and then refuses is a UI that lies about what its buttons do.

    Remove stays available — a running job can be removed, which cancels it first (`T-080`). The
    two differ, and asserting both is what stops the enabling rule collapsing into one flag.
    """
    window = _window_over([_job("busy", 0, JobStatus.RUNNING)], on_reorder_requested=lambda _: None)
    assert window.queue_view is not None
    window.queue_view.select("busy")

    assert window.move_up_action is not None
    assert window.move_down_action is not None
    assert window.remove_action is not None
    assert not window.move_up_action.isEnabled(), "a running job was offered a move"
    assert not window.move_down_action.isEnabled()
    assert window.remove_action.isEnabled(), (
        "a running job must still be removable; T-080 cancels it first"
    )


def test_clearing_the_selection_disables_every_per_job_action(qapp: QApplication) -> None:
    """A refresh or explicit deselection must not leave actions offered for no selected row."""
    window = _window_over(
        [_job("a", 0), _job("b", 1)],
        on_remove_requested=lambda _: None,
        on_reorder_requested=lambda _: None,
    )
    assert window.queue_view is not None
    window.queue_view.select("a")

    assert window.remove_action is not None and window.remove_action.isEnabled()
    assert window.move_up_action is not None and window.move_up_action.isEnabled()
    assert window.move_down_action is not None and window.move_down_action.isEnabled()

    window.queue_view.table.clearSelection()

    assert not window.remove_action.isEnabled(), "Remove stayed enabled with no selected row"
    assert not window.move_up_action.isEnabled(), "Move up stayed enabled with no selected row"
    assert not window.move_down_action.isEnabled(), "Move down stayed enabled with no selected row"


def test_moving_past_either_end_asks_for_nothing(qapp: QApplication) -> None:
    """The first job cannot move up and the last cannot move down, and neither is an error."""
    asked: list[list[str]] = []
    window = _window_over([_job("a", 0), _job("b", 1)], on_reorder_requested=asked.append)
    assert window.queue_view is not None

    window.queue_view.select("a")
    assert window.move_up_action is not None
    window.move_up_action.trigger()

    window.queue_view.select("b")
    assert window.move_down_action is not None
    window.move_down_action.trigger()

    assert asked == [], f"sent {asked}; moving past an end must ask for no reordering at all"


def test_clear_finished_is_always_offered_and_asks_once(qapp: QApplication) -> None:
    """Unlike the per-job actions, this needs no selection — it is a queue-level chore."""
    asked: list[int] = []
    window = MainWindow(concurrency=1, on_clear_requested=lambda: asked.append(1))
    action = window.clear_completed_action
    assert action is not None

    assert action.isEnabled(), "clear-finished needs no selection and must not wait for one"
    action.trigger()
    assert asked == [1]
