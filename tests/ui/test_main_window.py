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
