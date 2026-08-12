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
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QToolBar,
)

from tracks_and_trails import __version__
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import DownloadRequest, Job
from tracks_and_trails.core.paths import APP_SLUG
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.ui import theme
from tracks_and_trails.ui.main_window import (
    _MAX_COORD,
    ACTIONABLE_STATUS_PROPERTY,
    APP_NAME,
    DEFAULT_SIZE,
    MainWindow,
    app_icon,
    geometry_path,
    load_geometry,
    moved_onto_a_screen,
    save_geometry,
)
from tracks_and_trails.ui.row_verbs import Verb


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


def test_menu_bar_exposes_quit_about_and_settings(window: MainWindow) -> None:
    titles = {menu.title() for menu in window.menuBar().findChildren(QMenu)}
    assert {"&File", "&Help", "&Settings"} <= titles

    names = {action.objectName() for action in window.findChildren(QAction)}
    assert {"actionQuit", "actionAbout", "actionSettings"} <= names


def test_the_settings_item_is_disabled_on_a_window_that_cannot_write_settings(
    window: MainWindow,
) -> None:
    """`REQ-023`, `T-146`: the menu route exists, and does nothing it cannot do.

    Every setting the screen edits is written by composition (`ARC-007`), so a window built
    without those callbacks — this fixture's, and most of `tests/ui/` — offers the item disabled
    rather than a screen whose controls are inert. `open_settings` refuses for the same reason,
    which is the second half rather than a trust in the first.
    """
    action = window.settings_action
    assert action is not None, "the Settings menu item is missing entirely"
    assert not action.isEnabled(), (
        "a window with no settings writers offers an enabled Settings item, so the screen behind "
        "it would open with controls that change nothing"
    )
    assert window.open_settings() is None


def test_the_settings_item_opens_the_screen_when_composition_wired_it(
    qapp: QApplication, tmp_path: Path
) -> None:
    """The route a user takes: the menu item, not the method behind it (`REQ-023`, `T-146`)."""
    window = MainWindow(
        tmp_path / "window.toml",
        output_directory=tmp_path / "downloads",
        theme="light",
        on_directory_chosen=lambda _directory: None,
        on_theme_chosen=lambda _name: None,
    )
    try:
        action = window.settings_action
        assert action is not None and action.isEnabled()

        action.trigger()
        qapp.processEvents()

        screens = window.findChildren(QDialog, "settingsDialog")
        assert len(screens) == 1, f"{len(screens)} settings screens opened from one menu item"
    finally:
        window.close()
        qapp.processEvents()


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


# --- T-080/T-181: the queue's run toggle and the selected job's remove action ---------------


def test_the_queue_actions_exist_only_with_the_control_bar(qapp: QApplication) -> None:
    """`T-007`'s bare window still opens, and offers neither action.

    The all-or-nothing rule the add-URL action follows: a window holding half of what an action
    needs could only offer one that fails. A window built with no `concurrency` has no toolbar, so
    it has no queue actions either — and `T-007`'s tests construct exactly that window.
    """
    bare = MainWindow()
    assert bare.run_action is None
    assert bare.clear_completed_action is None

    equipped = MainWindow(concurrency=3)
    assert equipped.run_action is not None
    assert equipped.clear_completed_action is not None


def test_the_toolbar_holds_nothing_that_acts_on_a_selection(qapp: QApplication) -> None:
    """`UX-005` chose row verbs **"rather than a toolbar acting on a selection"** (`T124-R3`).

    The row route was added and the rejected one was left in place, so *Remove*, *Move up* and
    *Move down* were still on the toolbar, still enabled from the queue's selection, and still
    live while the History tab was in front — the exact ambiguity the decision exists to remove.

    Asserted **by object name over the real toolbar**, not by the absence of a property: a property
    can be deleted while the action goes on being built and added, which leaves the defect and
    passes the test. Every surviving action is then required to be enabled with nothing selected,
    which is what "acts on a whole list" means operationally.

    *(This list said the toolbar's verbs act on the **queue**. `T-144` added `Clear history`, and
    `DAT-005`'s 2026-08-05 amendment rewrote the rule to the principle underneath it: nothing here
    acts on a selection, and every verb names the list it empties. The tab a verb belongs to was
    never what made it unambiguous — `Clear finished` was not ambiguous while History was in front
    either. The property this test guards is unchanged; only the sentence describing it moved.)*
    """
    window = _window_over([_job("a", 0), _job("b", 1)], on_remove_requested=lambda _: None)
    bar = window.findChild(QToolBar, "queueToolBar")
    assert bar is not None

    names = {action.objectName() for action in bar.actions() if action.objectName()}
    assert names == {
        "actionAddUrls",
        "runQueueAction",
        "clearCompletedAction",
    }, (
        f"the toolbar holds {sorted(names)}; UX-005 §4 leaves it queue-wide Start/Stop and "
        "Clear-finished, its 2026-08-04 amendment adds Add URLs as the primary action, DAT-005's "
        "2026-08-05 amendment adds Clear history, and every per-row verb belongs on the row"
    )
    for name in names:
        assert "selected" not in name.lower(), f"{name} names a selection rather than a list"

    # **Selection is the property under test, not enablement in general.** `actionAddUrls` is
    # legitimately disabled here — `T-016` disables it when composition supplied no job sink or
    # output directory, which `_window_over` does not — and that has nothing to do with which row
    # is selected. So the claim is asserted as *unchanged by* selection, which is what `UX-005`
    # rejected a selection-driven toolbar over (`T124-R3`).
    assert window.queue_view is not None
    before = {a.objectName(): a.isEnabled() for a in bar.actions() if a.objectName()}
    window.queue_view.select("a")
    with_selection = {a.objectName(): a.isEnabled() for a in bar.actions() if a.objectName()}
    window.queue_view.table.clearSelection()
    without = {a.objectName(): a.isEnabled() for a in bar.actions() if a.objectName()}

    assert before == with_selection == without, (
        f"a toolbar action changed with the selection: {before} -> {with_selection} -> {without}. "
        "UX-005 chose row verbs over a toolbar acting on a selection: with the two tabs it then "
        "had, such a toolbar would have had to guess which list it meant"
    )


def test_the_run_toggle_reports_once_and_says_which_way(qapp: QApplication) -> None:
    """The toggle reports the state it moved to, and reports it exactly once per change.

    `toggled` rather than `triggered`: a checkable action fires `triggered` on every activation
    including the ones that do not change the state, and a queue asked to stop twice would be a
    manager call the second press did not earn.
    """
    reported: list[bool] = []
    window = MainWindow(concurrency=3, on_run_changed=reported.append)
    action = window.run_action
    assert action is not None

    action.setChecked(True)
    assert reported == [True]

    action.setChecked(False)
    assert reported == [True, False]

    # Setting it to what it already is changes nothing, so it says nothing.
    action.setChecked(False)
    assert reported == [True, False], "an unchanged toggle reported a change"


def test_showing_the_run_state_does_not_report_it_back(qapp: QApplication) -> None:
    """`T-080`: the manager telling the control must not become the control telling the manager.

    Composition connects `DownloadManager.queue_running` to `show_queue_running`, so without
    blocking signals the round trip is control → manager → control → manager. The assertion is on
    the handler never firing, which is the half a `setChecked` that merely *looks* right would
    fail.
    """
    reported: list[bool] = []
    window = MainWindow(concurrency=3, on_run_changed=reported.append)
    action = window.run_action
    assert action is not None

    window.show_queue_running(True)

    assert action.isChecked(), "the control did not follow the queue"
    assert reported == [], (
        "reflecting the queue's state called back into the queue; that round trip is how a toggle "
        "ends up fighting itself"
    )

    window.show_queue_running(False)
    assert not action.isChecked()
    assert reported == []


def test_the_window_opens_with_the_queue_stopped_and_says_so(qapp: QApplication) -> None:
    """`UX-006`, `T-181`: the window's own default, and the words that go with it.

    **Two defaults have to agree and composition does not sync them**: `DownloadManager` is
    constructed stopped and this control is constructed unchecked. `test_the_composed_run_control_
    changes_the_real_manager` asserts the pair; this asserts the window's half on its own, so a
    failure says which side moved.
    """
    window = MainWindow(concurrency=3)
    action = window.run_action
    assert action is not None

    assert not action.isChecked(), "the window opened claiming a running queue"
    assert action.text() == "&Start", (
        f"the control reads {action.text()!r} on a stopped queue; its label names what pressing "
        "it does, and a window where nothing has ever run must not offer Stop"
    )

    state = window.findChild(QLabel, "queueGateState")
    assert state is not None, "the window has no permanent statement of whether the queue runs"
    assert "stopped" in state.text().lower(), state.text()
    assert "start" in state.text().lower(), (
        f"the status bar says {state.text()!r}, which names the state without naming the remedy; "
        "a user looking at a full queue and no activity needs to be told what to press"
    )


def test_the_run_control_says_its_state_in_words_not_only_by_being_checked(
    qapp: QApplication,
) -> None:
    """`NFR-005`: no information by a visual cue alone, and a checkbox tick is one.

    A screen-reader user hearing only *Start* cannot tell whether the queue is running —
    the verb is the same shape either way. So the state itself is in the tooltip, which is what a
    toolbar button publishes as its accessible description, and in the status bar's own words.
    Both are asserted here rather than one, because a control and a status line that disagree are
    worse than either alone.
    """
    window = MainWindow(concurrency=3)
    action = window.run_action
    state = window.findChild(QLabel, "queueGateState")
    assert action is not None and state is not None

    assert "stopped" in action.toolTip().lower(), action.toolTip()

    window.show_queue_running(True)
    assert action.text() == "&Stop"
    assert "running" in action.toolTip().lower(), (
        f"a running queue's control describes {action.toolTip()!r}; the state a user cannot see "
        "from the tick is the one that has to be said"
    )
    assert "running" in state.text().lower(), state.text()

    window.show_queue_running(False)
    assert action.text() == "&Start"
    assert "stopped" in action.toolTip().lower()
    assert "stopped" in state.text().lower(), (
        "the status bar kept the running wording after the queue stopped; it follows the manager's "
        "signal, not only the click"
    )


def test_the_run_control_is_reachable_by_keyboard(qapp: QApplication) -> None:
    """`NFR-005`: every interactive control is operable by keyboard alone.

    Asserted through the action's own mnemonic rather than by simulating a key press: the toolbar
    button is built by Qt from the action, and `&S` is what makes `Alt`-navigation reach it. A
    control with no mnemonic is reachable only by `Tab` order, which `T-040` already covers for
    the window as a whole — this is the half that names *this* control.
    """
    window = MainWindow(concurrency=3)
    action = window.run_action
    assert action is not None
    assert "&" in action.text(), (
        f"{action.text()!r} carries no mnemonic, so Alt-navigation cannot reach the one control "
        "that decides whether anything downloads"
    )


def test_a_rows_remove_names_its_own_job(qapp: QApplication) -> None:
    """Removal is the row's verb now, and it carries the job rather than reading a selection.

    This replaces `test_remove_is_offered_only_when_something_is_selected` (`T124-R3`). That test
    was about the toolbar action's enabled state, which existed because the toolbar had to guess
    what it was acting on. The row cannot guess: it names the job it is drawn on, and the
    assertion is that the named job is the one that reaches composition **while a different row is
    selected**, which is the case a selection-reading implementation gets wrong.
    """
    asked: list[str] = []
    window = _window_over(
        [_job("a", 0), _job("b", 1)],
        on_remove_requested=asked.append,
    )
    assert window.queue_view is not None
    window.queue_view.select("a")

    window.queue_view.trigger_verb("b", Verb.REMOVE)

    assert asked == ["b"], (
        f"asked to remove {asked}; the row's verb names its own job, and `a` was selected"
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
    manager.start_queue()
    return MainWindow(concurrency=1, manager=manager, queue=_FakeQueue(jobs), **handlers)  # type: ignore[arg-type]


class _EmptyJobStore:
    """The narrowest thing `DownloadManager` will accept; nothing here starts a job."""

    def get(self, job_id: str) -> Job | None:
        return None

    def update(self, job: Job, done: object) -> None: ...
    def complete(self, job: Job, done: object) -> None: ...
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

    window.queue_view.trigger_verb("c", Verb.MOVE_UP)

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

    window.queue_view.trigger_verb("c", Verb.MOVE_UP)

    assert asked == [["c", "a"]], (
        f"sent {asked}; the running job must not be named, and `c` moving up past it means `c` "
        "and `a` swap"
    )


def test_a_running_row_offers_only_cancel(qapp: QApplication) -> None:
    """`UX-005` §4's table, read off the row the user is looking at.

    Nothing is drawn that would be refused (§5), so a running job offers neither move — the
    repository would reject it — and no *Remove*: `UX-005` §4 gives a download in flight exactly
    one verb, because §7 removed the per-job pause and cancelling is the only thing left to say
    about it.

    **And the move is refused even when driven anyway** (`T124-R3`), which is the half that
    matters now that the route is a signal rather than a disabled button: `_move_job` asks
    `_is_movable` rather than trusting that a row drew the verb.
    """
    asked: list[list[str]] = []
    window = _window_over(
        [_job("busy", 0, JobStatus.RUNNING), _job("next", 1)],
        on_reorder_requested=asked.append,
    )
    assert window.queue_view is not None

    assert window.queue_view.verbs_of("busy") == (Verb.CANCEL,), (
        f"a running row offered {window.queue_view.verbs_of('busy')}"
    )

    window.queue_view.trigger_verb("busy", Verb.MOVE_DOWN)
    assert asked == [], (
        "a running job was reordered; the row must not be the only thing that decides, because "
        "the model's answer is a moment old and the repository refuses this move"
    )


def test_moving_past_either_end_asks_for_nothing(qapp: QApplication) -> None:
    """The first job cannot move up and the last cannot move down, and neither is an error."""
    asked: list[list[str]] = []
    window = _window_over([_job("a", 0), _job("b", 1)], on_reorder_requested=asked.append)
    assert window.queue_view is not None

    window.queue_view.trigger_verb("a", Verb.MOVE_UP)
    window.queue_view.trigger_verb("b", Verb.MOVE_DOWN)

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


# --- T-082: interrupted jobs are offered, never restarted -------------------------------------


def test_a_clean_start_offers_nothing(window: MainWindow) -> None:
    """No dialog at all when nothing was interrupted, which is every ordinary start."""
    assert window.offer_to_retry_interrupted([]) is None
    assert window.findChild(QMessageBox, "interruptedJobsDialog") is None


def test_the_offer_names_how_many_and_is_refusable(qapp: QApplication, tmp_path: Path) -> None:
    """**Explicit and refusable** (`T-082`'s second criterion).

    `Not now` is the default *and* the escape button: Enter or Escape at startup must not begin
    twelve downloads. Refusing has to be the easier of the two things to do, or the offer is a
    prompt the user learns to dismiss without reading.
    """
    retried: list[str] = []
    window = MainWindow(geometry_file=tmp_path / "window.toml", retry=retried.append)

    box = window.offer_to_retry_interrupted(["a", "b", "c"])

    assert box is not None
    assert "3 downloads were interrupted" in box.text()
    labels = [button.text().replace("&", "") for button in box.buttons()]
    assert labels == ["Retry all", "Not now"]
    default = box.defaultButton()
    assert default.text().replace("&", "") == "Not now"
    assert box.escapeButton() is default

    assert retried == [], "the offer started downloads merely by being shown"
    box.close()


def test_one_interrupted_job_reads_as_one(qapp: QApplication, tmp_path: Path) -> None:
    """The plural is the task, so the singular must not read as a bug."""
    window = MainWindow(geometry_file=tmp_path / "window.toml")

    box = window.offer_to_retry_interrupted(["only"])

    assert box is not None
    assert "1 download was interrupted" in box.text()
    box.close()


def test_accepting_retries_every_recovered_job_through_the_ordinary_route(
    qapp: QApplication, tmp_path: Path
) -> None:
    """Through the injected `retry`, which is the same callable the per-job button uses.

    One route rather than a bulk path in the manager: two routes are two things that can come to
    disagree about what a retry is.
    """
    retried: list[str] = []
    window = MainWindow(geometry_file=tmp_path / "window.toml", retry=retried.append)

    box = window.offer_to_retry_interrupted(["a", "b", "c"])
    assert box is not None
    for button in box.buttons():
        if button.text().replace("&", "") == "Retry all":
            button.click()

    assert retried == ["a", "b", "c"]
    box.close()


def test_declining_retries_nothing(qapp: QApplication, tmp_path: Path) -> None:
    """The half of "refusable" that a test which only clicked Retry would never notice."""
    retried: list[str] = []
    window = MainWindow(geometry_file=tmp_path / "window.toml", retry=retried.append)

    box = window.offer_to_retry_interrupted(["a", "b"])
    assert box is not None
    for button in box.buttons():
        if button.text().replace("&", "") == "Not now":
            button.click()

    assert retried == []
    box.close()


def test_a_window_with_no_retry_route_offers_without_raising(
    qapp: QApplication, tmp_path: Path
) -> None:
    """Composition supplies `retry`; a window built without one is `T-007`'s bare case, and an
    exception out of a button's slot is printed and swallowed rather than handled."""
    window = MainWindow(geometry_file=tmp_path / "window.toml")

    box = window.offer_to_retry_interrupted(["a"])
    assert box is not None
    for button in box.buttons():
        if button.text().replace("&", "") == "Retry all":
            button.click()
    box.close()


# --- T-192: the stopped queue asks for a press, and has to look like it ----------------------


def test_the_queue_state_sits_at_the_left_and_the_summary_at_the_right(
    qapp: QApplication,
) -> None:
    """**`T-192`.** The two status-bar labels must not run together as one sentence.

    Both used `addPermanentWidget`, which packs to the **right** end, so the bar read
    *"Queue stopped — press Start to download  ffmpeg found; all post-processing features are
    available."* — one line in which the half asking the user to act is the tail of the half that
    does not. Asserted on measured positions rather than on which method was called, because the
    defect a reader sees is the distance between them.
    """
    window = MainWindow(concurrency=3)
    window.resize(1000, 600)
    window.show()
    qapp.processEvents()

    bar = window.statusBar()
    gate = window.findChild(QLabel, "queueGateState")
    summary = window.findChild(QLabel, "environmentSummary")
    # `statusBar()` is non-optional in the stubs, so guarding it is a `redundant-expr` error under
    # the test-inclusive gates — only the two `findChild` results can actually be `None`.
    assert gate is not None and summary is not None

    gate_x = gate.mapTo(bar, gate.rect().topLeft()).x()
    summary_x = summary.mapTo(bar, summary.rect().topLeft()).x()

    assert gate_x < bar.width() // 4, (
        f"the queue state starts at x={gate_x} in a {bar.width()}px bar; it belongs at the left "
        "edge, where a reader starts"
    )
    assert summary_x > gate_x + gate.width(), (
        "the environment summary overlaps or precedes the queue state; they read as one sentence"
    )


def test_only_the_stopped_state_is_emphasised(qapp: QApplication) -> None:
    """A bar where everything is emphasised emphasises nothing (`T-192`).

    The stopped line is the one asking for a press; the running line reports, like the summary
    beside it. **`NFR-005` is satisfied before this**: both states are already distinct *in words*,
    and the weight is a second channel rather than the carrier.
    """
    # The theme is applied here rather than relied on: `qapp` does not set a stylesheet, and
    # without one the property would be correct while nothing drew differently — which is the half
    # of this that a user actually sees. Restored afterwards so it does not leak into other tests.
    previous = qapp.styleSheet()
    theme.apply(qapp, theme.LIGHT)
    try:
        window = MainWindow(concurrency=3)
        gate = window.findChild(QLabel, "queueGateState")
        assert gate is not None

        assert gate.property(ACTIONABLE_STATUS_PROPERTY) is True, (
            "a stopped queue is not marked actionable, so the sheet cannot emphasise it"
        )
        stopped_weight = gate.font().weight()
        assert stopped_weight > 400, (
            f"the stopped queue draws at weight {stopped_weight}; the sheet rule did not reach it"
        )

        window.show_queue_running(True)
        qapp.processEvents()

        assert gate.property(ACTIONABLE_STATUS_PROPERTY) is False, (
            "the running queue is still marked actionable; the emphasis never turns off"
        )
        assert gate.font().weight() < stopped_weight, (
            f"running weight {gate.font().weight()} is not lighter than stopped {stopped_weight}; "
            "the property changed but nothing repolished the widget, so the rule applied once at "
            "construction and then silently stopped"
        )
    finally:
        qapp.setStyleSheet(previous)
