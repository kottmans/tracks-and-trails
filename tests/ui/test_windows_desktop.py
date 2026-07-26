"""Windows verification against the runner's real desktop (`T-026`, `OPS-004`).

`OPS-003` assumed a CI runner has no desktop session and wrote off rendering, focus and
assistive technology as human-only. `OPS-004` (accepted 2026-07-26) replaced that with a
measurement: `windows-latest` reports the real `windows` platform plugin, a 1024x768 display,
and a native `HWND` whose title the Win32 API reads back.

Everything here therefore runs **without** `QT_QPA_PLATFORM=offscreen`. That is the whole
point: the rest of the UI suite proves the window constructs headless, and this file proves it
reaches an actual Windows desktop.

**Why these fail rather than skip.** A silent skip on the one job that exists to run them
would leave the job green while proving nothing — the exact "retire a gate and replace it with
theatre" failure `T-026` warns about. So the module skips only when it is not on Windows at
all. Once on Windows, a wrong environment is an error, not a reason to opt out.

Screenshots are written to `reports/screenshots/` and uploaded by CI. Per `T031-R2` they are
**retained evidence, not a gate**: they exist for a human to look at, and no assertion here
depends on their content. Every claim that turns the build red is a separate objective check.
"""

import ctypes
import os
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu

from tracks_and_trails.ui.main_window import APP_NAME, MainWindow

pytestmark = pytest.mark.windows_desktop

if sys.platform != "win32":
    pytest.skip(
        "T-026 verifies behavior on a real Windows desktop; nothing here is meaningful "
        "elsewhere. The Linux equivalent is the ordinary offscreen UI suite.",
        allow_module_level=True,
    )


#: Written next to the other CI evidence, so one artifact download carries the whole run.
SCREENSHOT_DIR = Path("reports/screenshots")


def _screenshot(widget: object, name: str) -> Path:
    """Capture `widget` as it is actually composited by Windows, and return the path.

    `QScreen.grabWindow(hwnd)` is deliberate: `QWidget.grab()` re-renders the widget through
    Qt's own paint path, which would produce an image even under the offscreen plugin and so
    could not distinguish a real desktop from a headless one. Grabbing by window handle asks
    the windowing system for what it is showing.
    """
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"{name}.png"
    screen = QGuiApplication.primaryScreen()
    assert screen is not None, "a real desktop must expose a primary screen"
    pixmap = screen.grabWindow(widget.winId())  # type: ignore[attr-defined]
    assert pixmap.save(str(path)), f"could not write {path}"
    return path


def _window_text(hwnd: int) -> str:
    """Read a window's title through the Win32 API, not through Qt.

    Asking Qt what it set the title to would be circular. `GetWindowTextW` is Windows itself
    reporting what it has registered for that handle, which is what makes it evidence that the
    window exists as far as the operating system is concerned.
    """
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


@pytest.fixture
def shown_window(qapp: QApplication, tmp_path: Path) -> MainWindow:
    """A real, visible, activated window with its geometry redirected into `tmp_path`."""
    window = MainWindow(geometry_file=tmp_path / "window.toml")
    window.show()
    window.raise_()
    window.activateWindow()
    QApplication.processEvents()
    return window


# --- the environment itself is the first assertion ----------------------------------------


def test_the_real_windows_platform_plugin_is_active(qapp: QApplication) -> None:
    """Guards every other test in this file.

    If `QT_QPA_PLATFORM=offscreen` leaked into this job, every assertion below would still
    pass while testing nothing — a window that Windows never sees has no title, no focus and
    no accessibility tree worth asserting. This turns that into a loud failure.
    """
    platform = QGuiApplication.platformName()
    assert platform == "windows", (
        f"expected the real 'windows' platform plugin, got {platform!r}. "
        f"QT_QPA_PLATFORM={os.environ.get('QT_QPA_PLATFORM')!r}. "
        "T-026 is meaningless offscreen (OPS-004)."
    )


def test_a_real_screen_is_available(qapp: QApplication) -> None:
    """`OPS-004`'s spike recorded a 1024x768 HyperV monitor. Assert the shape, not the size.

    Pinning the exact resolution would break the day the runner image changes, which is a
    maintenance cost with no safety benefit. What matters is that a screen with usable area
    exists at all, because that is what `OPS-003` assumed was absent.
    """
    screens = QGuiApplication.screens()
    assert screens, "no screen: this is the state OPS-003 assumed and OPS-004 disproved"
    available = screens[0].availableGeometry()
    assert available.width() > 0 and available.height() > 0


# --- the Phase 0 exit criterion -----------------------------------------------------------


def test_the_window_launches_on_a_real_windows_desktop(shown_window: MainWindow) -> None:
    """Phase 0's remaining exit criterion, asserted rather than assumed.

    "The window launches on Linux **and** Windows from a clean checkout" — the clean checkout
    is the runner, and this is the launch. Four independent facts, because any one of them
    alone has a plausible false pass: Qt believing it is visible says nothing about Windows
    agreeing, and a handle that exists says nothing about it being shown.
    """
    hwnd = int(shown_window.winId())
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]

    assert hwnd, "the window has no native handle"
    assert user32.IsWindow(hwnd), f"Windows does not recognise {hwnd} as a window"
    assert user32.IsWindowVisible(hwnd), "Windows reports the window as not visible"
    assert _window_text(hwnd) == APP_NAME, (
        f"Windows reports the title as {_window_text(hwnd)!r}, not {APP_NAME!r}"
    )


def test_the_launched_window_is_captured_for_review(shown_window: MainWindow) -> None:
    """Retained evidence, not a gate (`T031-R2`).

    The assertions are that a capture happened and is a non-trivial image — enough to catch a
    capture pipeline that silently produces nothing. Whether the window *looks* right is the
    subjective judgement `OPS-004` leaves with a person, and nothing here pretends otherwise.
    """
    path = _screenshot(shown_window, "main-window")
    assert path.is_file()
    assert path.stat().st_size > 1024, f"{path} is too small to be a real capture"


def test_the_about_box_is_captured_for_review(shown_window: MainWindow) -> None:
    """The second key window. Same standing: evidence for a human, not a gate."""
    about = shown_window.show_about()
    try:
        QApplication.processEvents()
        path = _screenshot(about, "about-box")
        assert path.is_file()
    finally:
        about.close()


# --- keyboard reachability ----------------------------------------------------------------
#
# `NFR-005` requires full keyboard navigation. What can be asserted today is menu-bar
# navigation, because the shell window has no other interactive controls yet — Phase 1's
# T-016 and T-017 bring the first ones.
#
# The widget tab-order gate T-026 calls for therefore lands with those widgets, not here.
# Asserting a focus chain over zero focusable widgets would pass unconditionally and prove
# nothing, which is precisely the vacuous check this task exists to avoid. `ai/TESTING.md` §9
# keeps Windows keyboard use on the manual list until that gate is real.


def test_the_menu_bar_is_not_native_and_so_is_keyboard_reachable(
    shown_window: MainWindow,
) -> None:
    """A native menu bar would be drawn by the OS and outside Qt's key handling.

    Windows does not use one, but Qt decides this at runtime and a wrong answer would make
    every keyboard assertion below meaningless rather than failing.
    """
    assert not shown_window.menuBar().isNativeMenuBar()
    assert shown_window.menuBar().isVisible()


def test_alt_f_opens_the_file_menu(shown_window: MainWindow) -> None:
    """Alt+F is the mnemonic declared by `"&File"`, driven through the real key path.

    The keystroke is sent and the result observed. Calling `QMenu.popup()` and then asserting
    the menu is visible would be the vacuous version: it would pass with the mnemonic removed,
    with the menu bar native, and under the offscreen plugin, so it would gate nothing.
    """
    menus = {menu.title(): menu for menu in shown_window.menuBar().findChildren(QMenu)}
    file_menu = menus["&File"]
    assert not file_menu.isVisible(), "the File menu should start closed"

    QTest.keyClick(shown_window, Qt.Key.Key_F, Qt.KeyboardModifier.AltModifier)
    QApplication.processEvents()
    try:
        assert file_menu.isVisible(), (
            "Alt+F did not open the File menu. On a real desktop this is a genuine keyboard "
            "gap (NFR-005), not a test artifact — the mnemonic is declared by '&File'."
        )
    finally:
        file_menu.close()
        QApplication.processEvents()


def test_every_menu_action_is_reachable_by_a_keyboard_mnemonic(shown_window: MainWindow) -> None:
    """Every action a mouse can reach must have a mnemonic, or it is mouse-only (`NFR-005`).

    Asserted over whatever actions exist rather than a fixed list, so an action added later
    without a mnemonic fails here instead of silently becoming unreachable.

    Walks `menuBar().actions()` rather than `findChildren(QMenu)`. On Windows the latter also
    returns an untitled internal `QMenu` that Qt creates for the menu bar itself, which is not
    a menu the user can reach and has no mnemonic to check — the first run of this test failed
    on exactly that.
    """
    menus = [action.menu() for action in shown_window.menuBar().actions() if action.menu()]
    assert menus, "the menu bar exposes no menus"

    for menu in menus:
        assert menu is not None
        assert "&" in menu.title(), f"menu {menu.title()!r} has no keyboard mnemonic"
        for action in menu.actions():
            if action.isSeparator():
                continue
            assert "&" in action.text(), f"action {action.text()!r} has no keyboard mnemonic"


def test_the_quit_shortcut_is_bound(shown_window: MainWindow) -> None:
    """`QKeySequence.StandardKey.Quit` resolves per-platform; assert it produced something.

    On Windows the standard Quit sequence is not the Ctrl+Q it is on Linux, and Qt may resolve
    it to nothing at all. An unbound shortcut is a keyboard gap that no offscreen test sees.
    """
    actions = {action.objectName(): action for action in shown_window.findChildren(QAction)}
    assert not actions["actionQuit"].shortcut().isEmpty(), (
        "Quit has no keyboard shortcut on Windows"
    )


def test_focus_reaches_the_window_when_activated(shown_window: MainWindow) -> None:
    """The window must be able to take focus at all — the precondition for keyboard use.

    On a real desktop this exercises the window manager; offscreen it would be a no-op, which
    is why it lives here rather than in the ordinary UI suite.
    """
    assert shown_window.isActiveWindow(), "the window did not become active on a real desktop"
    assert shown_window.windowHandle() is not None
    assert shown_window.windowHandle().isVisible()


def test_escape_does_not_close_the_main_window(shown_window: MainWindow) -> None:
    """A main window is not a dialog. Escape closing it would lose the user's session."""
    QTest.keyClick(shown_window, Qt.Key.Key_Escape)
    QApplication.processEvents()
    assert shown_window.isVisible(), "Escape closed the main window"
