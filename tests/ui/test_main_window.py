"""Shell window behavior (`T-007`).

Covers the acceptance criteria that can be asserted rather than looked at: the window
constructs and closes offscreen, carries the icon and title, exposes both menu actions, and
round-trips its geometry. Whether the icon *looks* right in a real Windows taskbar is not
automatable and stays an `OPS-003` known gap.
"""

from pathlib import Path

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QMessageBox

from tracks_and_trails import __version__
from tracks_and_trails.ui.main_window import (
    APP_NAME,
    APP_SLUG,
    DEFAULT_SIZE,
    MainWindow,
    app_icon,
    geometry_path,
    load_geometry,
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
