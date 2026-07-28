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
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from tracks_and_trails.core.models import Job
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.ui.add_dialog import AddUrlDialog
from tracks_and_trails.ui.job_detail import build_progress_view
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


class _EmptyStore:
    """A store with nothing in it, satisfying every protocol the widgets here need.

    These tests are about **focus**, not about jobs: no session is ever started and no row is
    ever written. A real store would add a writer thread and a database to a file whose subject
    is which control Windows hands the caret to next.
    """

    def get(self, job_id: str) -> Job | None:
        return None

    def all_jobs(self) -> list[Job]:
        return []

    def update(self, job: Job, done: object = None) -> None:
        if callable(done):
            done(None)

    def submit(self, jobs: object, done: object = None) -> None:
        if callable(done):
            done(None)


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
#
# `T026-R1`: constructing a `MainWindow` inside pytest is **not** the exit criterion. The
# criterion is that *the application* launches from a clean checkout, and the application is
# `app.run` — argument handling, `QApplication` construction, window creation and a real event
# loop, in a fresh interpreter. A widget built under a pytest-owned `QApplication` skips all
# of it.
#
# `tests/ui/test_app_launch.py` already drives that path, but hard-codes
# `QT_QPA_PLATFORM=offscreen`, so it proves the startup path and not the desktop. The
# subprocess test below is the missing intersection: real startup path *and* real plugin, with
# the launched process reporting Win32 evidence about itself.

#: Runs the real entry point under the inherited platform plugin and quits from the GUI thread.
#:
#: The quit is scheduled from `showEvent` through a zero-delay timer, matching the harness in
#: `test_app_launch.py` and for the same reason (`T028-R1`): polling `QApplication.instance()`
#: from a foreign thread relies on something Qt never documented as safe.
#:
#: The Win32 assertions run **inside the launched application**, which is the point — they
#: describe the process a user would actually start, not a widget a test constructed.
LAUNCH_ON_REAL_DESKTOP = """
import ctypes
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import tracks_and_trails.ui.main_window as main_window


class ProveThenQuit(main_window.MainWindow):
    def showEvent(self, event):
        super().showEvent(event)
        print("WINDOW-SHOWN", flush=True)
        # Probing here reported VISIBLE False on the first CI run: showEvent runs *during*
        # show(), before Windows has mapped the window. A zero-delay timer cannot fire until
        # the event loop is running, by which point the window really is on screen.
        QTimer.singleShot(0, self._probe_then_quit)

    def _probe_then_quit(self):
        app = QApplication.instance()
        print("PLATFORM", app.platformName(), flush=True)

        hwnd = int(self.winId())
        user32 = ctypes.windll.user32
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)

        print("HWND", hwnd, flush=True)
        print("IS-WINDOW", bool(user32.IsWindow(hwnd)), flush=True)
        print("VISIBLE", bool(user32.IsWindowVisible(hwnd)), flush=True)
        print("TITLE", buffer.value, flush=True)

        print("QUIT-REQUESTED", flush=True)
        app.quit()


main_window.MainWindow = ProveThenQuit

from tracks_and_trails.app import run

sys.exit(run(["tracks-and-trails"]))
"""


def test_the_application_launches_on_a_real_windows_desktop(tmp_path: Path) -> None:
    """**Phase 0's exit criterion**, on the real startup path (`T026-R1`).

    Everything else in this file constructs a widget. This starts the application.

    `platformdirs` is redirected through `WIN_PD_OVERRIDE_*` rather than `APPDATA`: on Windows
    it resolves folders through `SHGetKnownFolderPath` via ctypes, so setting `APPDATA` does
    nothing — the mistake that once made a launch test pass on Linux and fail here.
    """
    environment = {
        **os.environ,
        "QT_QPA_PLATFORM": "windows",
        "WIN_PD_OVERRIDE_APPDATA": str(tmp_path),
        "WIN_PD_OVERRIDE_LOCAL_APPDATA": str(tmp_path),
    }
    try:
        result = subprocess.run(
            [sys.executable, "-c", LAUNCH_ON_REAL_DESKTOP],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired as expired:
        raise AssertionError(
            "the application never exited within 120s on a real desktop. It either never "
            f"showed a window or never processed the queued quit.\nstdout: {expired.stdout!r}"
            f"\nstderr: {expired.stderr!r}"
        ) from expired

    assert result.returncode == 0, f"exit {result.returncode}\nstderr: {result.stderr}"

    reported = dict(
        line.split(" ", 1) for line in result.stdout.splitlines() if " " in line.strip()
    )
    assert reported.get("PLATFORM") == "windows", (
        f"the application ran under {reported.get('PLATFORM')!r}, not the real desktop plugin"
    )
    assert reported.get("IS-WINDOW") == "True", "Windows did not recognise the handle"
    assert reported.get("VISIBLE") == "True", "Windows reports the window as not visible"
    assert reported.get("TITLE") == APP_NAME, (
        f"Windows reports the title as {reported.get('TITLE')!r}"
    )
    assert int(reported.get("HWND", "0")) != 0, "the application window has no native handle"
    assert "WINDOW-SHOWN" in result.stdout, "the window never reached showEvent"
    assert "QUIT-REQUESTED" in result.stdout, "the window appeared but the quit never fired"
    assert result.stderr.strip() == "", (
        f"Qt wrote to stderr during a clean real-desktop run:\n{result.stderr}"
    )


def test_a_window_constructed_in_process_is_seen_by_windows(shown_window: MainWindow) -> None:
    """The narrower, faster check: a widget built here is a real window to the OS.

    Kept alongside the launch test rather than instead of it. It isolates Qt's window creation
    from application startup, so a failure in one does not have to be diagnosed through the
    other — but on its own it is **not** the Phase 0 criterion (`T026-R1`).
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

    Everything happens in **one pass, with `actions` held in a local**. Collecting the menus
    first and asserting over them afterwards fails with "Internal C++ object (QMenu) already
    deleted": the `QAction` wrappers are what keep the menu wrappers alive, so once that list
    is released the collected menus are dead. Two CI runs failed on variations of this before
    the lifetime, rather than the number of `menu()` calls, turned out to be the cause.
    """
    actions = shown_window.menuBar().actions()
    checked = 0

    for action in actions:
        menu = action.menu()
        # isinstance rather than `is not None`: PySide6 types `QAction.menu()` as `QObject`,
        # so a None check alone leaves every `menu.title()` below untyped (`T026-R4`).
        if not isinstance(menu, QMenu):
            continue
        assert "&" in menu.title(), f"menu {menu.title()!r} has no keyboard mnemonic"
        for item in menu.actions():
            if item.isSeparator():
                continue
            assert "&" in item.text(), f"action {item.text()!r} has no keyboard mnemonic"
        checked += 1

    assert checked, "the menu bar exposes no menus"


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


# --- widget focus order under the real plugin (`T-040`, `T026-R3`, `NFR-005`) ----------------
#
# `T-026` required that "tab order and focus chain are asserted on Windows, and reordering two
# widgets fails the test". Deferring it was right at the time: the shell window had no focusable
# controls, so the assertion would have passed over nothing.
#
# `T-016` and `T-017` supplied them — an add-URL dialog with six, a progress view with three —
# and both gate their order **offscreen**. Offscreen proves the order Qt builds; it does not
# prove the order a real Windows desktop delivers, and that is the half this owns.
#
# The lesson carried forward from `T-016`'s own review: the first draft of the offscreen test
# derived its expectation from the dialog's own `focus_chain()`, so it proved only that the list
# equalled itself and the mutation reversing two entries survived. **One side is transcribed by
# hand here** and the other is walked out of Qt (`ai/TESTING.md` §13).


#: The add-URL dialog's controls, in the order a user should meet them, transcribed from what the
#: dialog is *for*: type the URLs, probe them, read the result, choose how to download, then act.
#: Written out rather than read from `focus_chain()` — that is the whole point.
EXPECTED_DIALOG_ORDER = (
    "urlInput",
    "probeButton",
    "cancelProbeButton",
    "titleValue",
    "uploaderValue",
    "durationValue",
    "kindValue",
    "statusMessage",
    "presetChoice",
    "selectorValue",
    "addButton",
    "closeButton",
)


def _focusable(widget: QWidget) -> list[str]:
    """Every focusable child of `widget`, named, as Qt reports them."""
    return [
        child.objectName()
        for child in widget.findChildren(QWidget)
        if child.focusPolicy() != Qt.FocusPolicy.NoFocus and child.objectName()
    ]


def _walk_focus_chain(dialog: QWidget, steps: int) -> list[str]:
    """Press Tab `steps` times and record what holds focus after each, under the real plugin.

    `QTest.keyClick` on a shown, activated window goes through Qt's real focus machinery on this
    platform rather than through `setFocus()` — which is the difference this file exists for.
    """
    seen: list[str] = []
    for _ in range(steps):
        QTest.keyClick(dialog, Qt.Key.Key_Tab)
        QApplication.processEvents()
        focused = QApplication.focusWidget()
        seen.append(focused.objectName() if focused is not None else "")
    return seen


@pytest.fixture
def shown_dialog(shown_window: MainWindow, tmp_path: Path) -> AddUrlDialog:
    """The add-URL dialog, visible and activated on the real desktop.

    Built directly rather than through `MainWindow.open_add_dialog`, because that path needs a
    manager, a job sink and an output directory (`T-036`) and none of them is what this asserts.
    A `DownloadManager` over an empty store is enough to construct the widget, and no session is
    ever started.
    """
    manager = DownloadManager(_EmptyStore())
    dialog = AddUrlDialog(
        manager=manager,
        jobs=_EmptyStore(),
        output_directory=tmp_path / "downloads",
        parent=shown_window,
    )
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    QApplication.processEvents()
    return dialog


def test_every_focusable_control_is_in_the_declared_tab_order(shown_dialog: AddUrlDialog) -> None:
    """A tab order that omits reachable controls is not a tab order (`T016-R4`).

    Compared against the hand-written list above, so a control that becomes focusable without
    being placed fails here rather than landing silently at the end of the chain.
    """
    reachable = set(_focusable(shown_dialog))
    declared = set(EXPECTED_DIALOG_ORDER)
    assert reachable == declared, (
        f"focusable but undeclared: {sorted(reachable - declared)}; "
        f"declared but not focusable: {sorted(declared - reachable)}"
    )


def test_tab_visits_the_declared_order_on_a_real_desktop(shown_dialog: AddUrlDialog) -> None:
    """`T-040`'s first criterion, under the real `windows` platform plugin.

    The offscreen suite asserts the order Qt *builds*; this asserts the order Windows
    *delivers*, by pressing Tab and asking who has focus. Reversing two entries in
    `AddUrlDialog.focus_chain` fails this, which is the mutation `T-026` asked for.
    """
    first = shown_dialog.focusWidget()
    assert first is not None, "nothing had focus when the dialog opened"

    visited = _walk_focus_chain(shown_dialog, len(EXPECTED_DIALOG_ORDER))
    start = visited.index(EXPECTED_DIALOG_ORDER[1]) if EXPECTED_DIALOG_ORDER[1] in visited else 0
    rotated = visited[start:] + visited[:start]
    expected = [*EXPECTED_DIALOG_ORDER[1:], EXPECTED_DIALOG_ORDER[0]]
    assert rotated == expected, (
        f"Tab visited {rotated} on a real desktop; the declared order is {expected}"
    )


def test_the_focus_chain_wraps_in_both_directions(shown_dialog: AddUrlDialog) -> None:
    """`T-040`'s second criterion: forwards and backwards, all the way round.

    A chain that wraps one way and dead-ends the other strands a keyboard user at whichever end
    they reach first, and neither direction is observable offscreen.
    """
    forwards = _walk_focus_chain(shown_dialog, len(EXPECTED_DIALOG_ORDER) * 2)
    assert set(forwards) >= set(EXPECTED_DIALOG_ORDER), (
        f"two full passes forwards missed {sorted(set(EXPECTED_DIALOG_ORDER) - set(forwards))}"
    )

    backwards: list[str] = []
    for _ in range(len(EXPECTED_DIALOG_ORDER) * 2):
        QTest.keyClick(shown_dialog, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
        QApplication.processEvents()
        focused = QApplication.focusWidget()
        backwards.append(focused.objectName() if focused is not None else "")
    assert set(backwards) >= set(EXPECTED_DIALOG_ORDER), (
        f"two full passes backwards missed {sorted(set(EXPECTED_DIALOG_ORDER) - set(backwards))}"
    )


def test_every_control_is_reachable_from_the_initial_focus(shown_dialog: AddUrlDialog) -> None:
    """`T-040`'s third criterion: keyboard alone, from wherever focus starts.

    Reachability is the property a user has; an order that is correct but enters a sub-loop
    leaves controls no amount of tabbing will find.
    """
    visited = set(_walk_focus_chain(shown_dialog, len(EXPECTED_DIALOG_ORDER) * 2))
    unreachable = set(EXPECTED_DIALOG_ORDER) - visited
    assert not unreachable, f"unreachable by keyboard from the initial focus: {sorted(unreachable)}"


def test_the_progress_view_controls_are_reachable_too(
    shown_window: MainWindow, tmp_path: Path
) -> None:
    """`T-017` added three more focusable controls, and they are this task's too.

    `T-040` was filed when the dialog was the only widget with any; the progress view arrived
    afterwards and its order is asserted offscreen for the same reason and with the same gap.
    """
    store = _EmptyStore()
    manager = DownloadManager(store)
    view = build_progress_view(manager, store, "job-1", None)
    shown_window.setCentralWidget(view)
    view.show()
    QApplication.processEvents()

    declared = [widget.objectName() for widget in view.focus_chain()]
    assert declared == ["errorMessage", "cancelJobButton", "retryJobButton"]
    assert set(_focusable(view)) == set(declared), (
        f"focusable: {sorted(set(_focusable(view)))}, declared: {sorted(set(declared))}"
    )
