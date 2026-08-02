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
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import DownloadRequest, Job
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.downloader.protocol import SessionKind
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
    """A store holding at most one job, satisfying every protocol the widgets here need.

    These tests are about **focus**, not about jobs: no session is ever started and no row is
    ever written. A real store would add a writer thread and a database to a file whose subject
    is which control Windows hands the caret to next.

    It can return a *failed* job because the progress view hides its Retry control unless the
    failure is retryable (`T-017`), and a chain missing a control is a chain this file would
    walk without noticing (`T040-R1`).
    """

    def __init__(self, status: JobStatus | None = None, kind: ErrorKind | None = None) -> None:
        self._status = status
        self._kind = kind

    def get(self, job_id: str) -> Job | None:
        if self._status is None:
            return None
        job = Job(
            id=job_id,
            url="https://focus.invalid/x",
            request=DownloadRequest(
                url="https://focus.invalid/x",
                output_directory=".",
                format_selector="best",
                output_template="%(title)s.%(ext)s",
            ),
            created_at=datetime.now(UTC),
        )
        return replace(
            job.with_status(JobStatus.PROBING).with_status(JobStatus.READY),
            status=self._status,
            error_kind=self._kind,
            error_message="something went wrong",
        )

    def all_jobs(self) -> list[Job]:
        return []

    def update(self, job: Job, done: object = None) -> None:
        if callable(done):
            done(None)

    def complete(self, job: Job, format_used: object = None, done: object = None) -> None:
        """Present only to satisfy `JobStore` (`T050-R1`). No session is started in this file.

        Found by `mypy --platform win32` rather than by the host gate, because this module is
        Windows-only — the case `AGENTS.md` §8's "a host-only check is not the whole gate" names.
        """
        if callable(done):
            done(None)

    def submit(self, jobs: object, done: object = None) -> None:
        if callable(done):
            done(None)

    def requeue_at_end(self, job: Any, done: Any) -> None:
        """Part of `JobStore` since `T-080`. Unused here; present so the fake satisfies it."""
        raise NotImplementedError

    def remove(self, job_id: str, done: Any) -> None:
        """Part of `JobStore` since `T-080`. Unused here; present so the fake satisfies it."""
        raise NotImplementedError

    def reorder(self, job_ids: Any, done: Any) -> None:
        """Part of `JobStore` since `T-081`. Unused here; present so the fake satisfies it."""
        raise NotImplementedError

    def clear_completed(self, done: Any) -> None:
        """Part of `JobStore` since `T-081`. Unused here; present so the fake satisfies it."""
        raise NotImplementedError


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
#:
#: **This is the order, not the reachable set** (`T040-R1`). Tab skips a control that is disabled
#: or hidden, and this dialog disables three of them until there is a URL to act on, so the chain
#: a user actually walks is this list filtered by what the current state offers.
EXPECTED_DIALOG_ORDER = (
    "urlInput",
    "retryFailedButton",
    "stagingList",
    "statusMessage",
    "presetChoice",
    "audioBitrateChoice",
    "selectorValue",
    "addButton",
    "closeButton",
)

#: What each dialog state makes available, written by hand from what the dialog is *for* rather
#: than read back from `_refresh_actions` (`ai/TESTING.md` §13).
#:
#: **All three of the dialog's states, including the one with a probe running** (`T060-R1`). The
#: first version stopped at the two a bare fixture could reach and recorded the third as a
#: deliberate gap — but `cancelProbeButton` is enabled in that state and in no other, so leaving
#: it out meant the only control that stops a running probe was reachable by no assertion here. A
#: gate that skips the one state a control lives in does not gate that control.
#:
#: The third element says whether the state is reached by starting a probe; `dialog_factory`
#: creates it without a worker (see `_ProbeThatNeverAnswers`).
DIALOG_STATES = (
    (
        "nothing typed",
        "",
        False,
        None,
        # Nothing has been read, so there is nothing to add and nothing to retry.
        frozenset(EXPECTED_DIALOG_ORDER) - {"retryFailedButton", "addButton", "audioBitrateChoice"},
    ),
    (
        "a URL typed and not yet read",
        "https://focus.invalid/clip",
        False,
        None,
        # **Add stays out** (`UX-003`). Typing a URL does not make it addable; being read does.
        # This row was "Probe and Add become available" until `T-118`, which is the whole change.
        frozenset(EXPECTED_DIALOG_ORDER) - {"retryFailedButton", "addButton", "audioBitrateChoice"},
    ),
    (
        "a read in flight",
        "https://focus.invalid/clip",
        True,
        None,
        # Still nothing to add: a row that is being read has not been read. Retry stays out
        # because nothing has failed — it appears only when there is a failure to act on, which
        # keeps the control's meaning exact rather than "press me and see".
        frozenset(EXPECTED_DIALOG_ORDER) - {"retryFailedButton", "addButton", "audioBitrateChoice"},
    ),
    (
        "an audio preset chosen",
        "https://focus.invalid/clip",
        False,
        "Audio only (MP3)",
        # `T-076`: the bitrate applies only to a preset that converts audio, so this is the one
        # state that offers it. Without this row the control would be declared and unreachable in
        # every state the suite walks — a chain asserted over a control no test can ever visit,
        # which is the shape `T060-R1` was.
        frozenset(EXPECTED_DIALOG_ORDER) - {"retryFailedButton", "addButton"},
    ),
)

#: The progress view's controls, in order, and what each ending makes available.
#:
#: A terminal job cannot be cancelled and a running one has nothing to retry (`T-017`), so no
#: state offers all three — which is exactly what `T040-R1` caught this file asserting.
EXPECTED_VIEW_ORDER = ("errorMessage", "cancelJobButton", "retryJobButton")
VIEW_STATES = (
    (
        "failed, retryable",
        JobStatus.FAILED,
        ErrorKind.NETWORK,
        frozenset({"errorMessage", "retryJobButton"}),
    ),
    ("running", JobStatus.RUNNING, None, frozenset({"cancelJobButton"})),
)


def _reachable(widget: QWidget, declared: tuple[str, ...], available: frozenset[str]) -> list[str]:
    """The chain a keyboard actually walks: the declared order, minus what this state withholds."""
    _ = widget
    return [name for name in declared if name in available]


def _focusable(widget: QWidget) -> list[str]:
    """Every child of `widget` that a keyboard can reach **now** — enabled, visible, focusable.

    `focusPolicy() != NoFocus` alone is not that question (`T040-R1`): a *disabled* widget keeps
    its focus policy and Tab skips it, so a structural check counted three controls the walk could
    never visit and the two lists agreed with each other while disagreeing with the keyboard.
    """
    return [
        child.objectName()
        for child in widget.findChildren(QWidget)
        if child.objectName()
        and child.focusPolicy() != Qt.FocusPolicy.NoFocus
        and child.isEnabled()
        and not child.isHidden()
    ]


def _walk_focus_chain(window: QWidget, steps: int, *, backwards: bool = False) -> list[str]:
    """Press Tab (or Shift+Backtab) `steps` times and record what holds focus after each.

    `QTest.keyClick` on a shown, activated window goes through Qt's real focus machinery on this
    platform rather than through `setFocus()` — which is the difference this file exists for.
    """
    key = Qt.Key.Key_Backtab if backwards else Qt.Key.Key_Tab
    modifier = Qt.KeyboardModifier.ShiftModifier if backwards else Qt.KeyboardModifier.NoModifier
    seen: list[str] = []
    for _ in range(steps):
        QTest.keyClick(window, key, modifier)
        QApplication.processEvents()
        focused = QApplication.focusWidget()
        seen.append(focused.objectName() if focused is not None else "")
    return seen


def _rotated_to(visited: list[str], expected: list[str]) -> list[str]:
    """Line `visited` up with `expected`'s first entry, since focus starts wherever Qt put it."""
    if expected and expected[0] in visited:
        start = visited.index(expected[0])
        return visited[start:] + visited[:start]
    return visited


class _ProbeThatNeverAnswers(DownloadManager):
    """A real manager whose `start` accepts the session and then does nothing (`T060-R1`).

    The dialog treats a returning `start()` as a probe in flight: `_on_probe_saved` sets
    `started`, `probing_job_id` becomes non-`None`, and `_refresh_actions` swaps Probe and Add out
    for Cancel. That is the whole state this file needs, and none of it depends on a worker
    existing.

    **Deliberately not `entry_point=child_never_returning`**, which is how `tests/ui/`
    `test_add_dialog.py` holds a probe open. That spawns a real process, and a file whose subject
    is which control the caret reaches next should not also be a process-lifetime test — a worker
    left alive by a failed assertion here would be attributed to whichever test ran next.

    A subclass rather than a stand-in object so the dialog still connects to the real signals: a
    fake with five hand-declared `Signal`s could drift from the manager's own and the connection
    would still succeed.
    """

    def __init__(self, store: _EmptyStore) -> None:
        super().__init__(store)
        self.started: list[tuple[str, SessionKind]] = []

    def start(self, job_id: str, kind: SessionKind = SessionKind.DOWNLOAD) -> None:
        self.started.append((job_id, kind))


@pytest.fixture
def dialog_factory(shown_window: MainWindow, tmp_path: Path) -> Callable[..., AddUrlDialog]:
    """Builds the add-URL dialog, visible and activated on the real desktop, with given text.

    Built directly rather than through `MainWindow.open_add_dialog`, because that path needs a
    manager, a job sink and an output directory (`T-036`) and none of them is what this asserts.
    A manager over an empty store is enough, and no worker is ever spawned.

    `probing=True` drives the dialog's own `probe()` and then asserts the state was actually
    reached. Without that check a change to `_refresh_actions` or to the save path could leave the
    dialog idle, and the two focus tests below would go on passing over the wrong state — the
    "gate that reports clean while covering nothing" this file exists to avoid.
    """

    def build(text: str, *, probing: bool = False, preset: str | None = None) -> AddUrlDialog:
        dialog = AddUrlDialog(
            manager=_ProbeThatNeverAnswers(_EmptyStore()),
            jobs=_EmptyStore(),
            output_directory=tmp_path / "downloads",
            parent=shown_window,
        )
        dialog._urls.setPlainText(text)
        if preset is not None:
            names = [
                dialog._preset_choice.itemText(i) for i in range(dialog._preset_choice.count())
            ]
            dialog._preset_choice.setCurrentIndex(names.index(preset))
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        QApplication.processEvents()
        if probing:
            # `T-118`: resolving is what starts a probe now, and it starts one per entered line.
            # The manager here never answers, so the rows stay in flight — which is the state the
            # chain below is asserted over.
            dialog.resolve()
            QApplication.processEvents()
            assert any(row.in_flight for row in dialog.rows), (
                "the dialog was asked to resolve and no row entered the in-flight state, so the "
                "chain below would be asserted over the wrong one. Status: "
                f"{dialog.status_text()!r}"
            )
        return dialog

    return build


@pytest.mark.parametrize(("case", "text", "probing", "preset", "available"), DIALOG_STATES)
def test_the_dialog_chain_offers_exactly_what_its_state_allows(
    dialog_factory: Callable[..., AddUrlDialog],
    case: str,
    text: str,
    probing: bool,
    preset: str | None,
    available: frozenset[str],
) -> None:
    """`T040-R1`: a focus chain is a property of *state*, not of the widget tree.

    The first version of this file asserted one chain for all states and CI failed three of its
    tests, reporting `probeButton`, `cancelProbeButton` and `addButton` unreachable. They were —
    all three are disabled until there is a URL to act on, and Tab skips a disabled control.

    **That was never a Windows behaviour.** The identical walk reproduces offscreen; the offscreen
    suite simply never pressed Tab, so nothing had observed it anywhere.
    """
    dialog = dialog_factory(text, probing=probing, preset=preset)
    expected = _reachable(dialog, EXPECTED_DIALOG_ORDER, available)

    assert sorted(_focusable(dialog)) == sorted(expected), (
        f"{case}: reachable now is {sorted(_focusable(dialog))}, this state should offer "
        f"{sorted(expected)}"
    )

    visited = _walk_focus_chain(dialog, len(expected))
    assert _rotated_to(visited, expected) == expected, (
        f"{case}: Tab visited {visited} on a real desktop; this state's chain is {expected}"
    )


@pytest.mark.parametrize(("case", "text", "probing", "preset", "available"), DIALOG_STATES)
def test_the_dialog_chain_wraps_in_both_directions(
    dialog_factory: Callable[..., AddUrlDialog],
    case: str,
    text: str,
    probing: bool,
    preset: str | None,
    available: frozenset[str],
) -> None:
    """`T-040`'s second criterion: forwards and backwards, all the way round.

    A chain that wraps one way and dead-ends the other strands a keyboard user at whichever end
    they reach first, and neither direction is observable without pressing the key.

    **Two full laps, compared as sequences** (`T060-R2`, applied to this file's sibling). This
    asserted set containment, which cannot see order and so could not tell a wrap from a chain
    that visits everything in the wrong sequence. Backtab through a reversed chain is exactly the
    defect a keyboard user meets and a set cannot express.
    """
    dialog = dialog_factory(text, probing=probing, preset=preset)
    expected = _reachable(dialog, EXPECTED_DIALOG_ORDER, available)
    reversed_expected = list(reversed(expected))

    forwards = _walk_focus_chain(dialog, len(expected) * 2)
    assert _rotated_to(forwards, expected) == expected * 2, (
        f"{case}: two laps of Tab visited {forwards}; this state's chain is {expected}"
    )

    backwards = _walk_focus_chain(dialog, len(expected) * 2, backwards=True)
    assert _rotated_to(backwards, reversed_expected) == reversed_expected * 2, (
        f"{case}: two laps of Backtab visited {backwards}; reversed this state's chain is "
        f"{reversed_expected}"
    )


@pytest.mark.parametrize(("case", "status", "kind", "available"), VIEW_STATES)
def test_the_progress_view_chain_offers_exactly_what_its_state_allows(
    shown_window: MainWindow,
    case: str,
    status: JobStatus,
    kind: ErrorKind | None,
    available: frozenset[str],
) -> None:
    """`T040-R1`, the case it was filed for, per state.

    A terminal job cannot be cancelled and a running one has nothing to retry, so the three
    controls never coexist. The version this replaces expected all three at once and a probe
    visited `retryJobButton → errorMessage → retryJobButton`, unable to reach `Cancel` because it
    was disabled.

    ## What this cannot prove, and why it is written this way anyway

    **No state of this view offers more than two reachable controls, and a two-element focus
    cycle has no observable orientation.** `A → B → A` and `B → A → B` are the same cycle: from
    either control, Tab and Backtab both deliver the other one, from any starting point. So
    reversing the failed state's two controls is unkillable *here* — not because the assertion is
    weak, but because the keyboard cannot distinguish the two arrangements. `T060-R2` names that
    reversal as the mutation this should catch; it is recorded as unobservable rather than
    answered with an assertion that appears to catch it.

    Ordering is gated where it is observable: the dialog's states offer nine to twelve reachable
    controls, and swapping two of them fails the dialog chain test above, in all three states.

    The anchored sequence is asserted regardless, because it costs nothing and it starts gating
    order by itself the day a third control becomes simultaneously reachable — which is a change
    nobody would think to add a test for.
    """
    store = _EmptyStore(status=status, kind=kind)
    view = build_progress_view(DownloadManager(store), store, "job-1", None)
    shown_window.setCentralWidget(view)
    view.show()
    shown_window.raise_()
    shown_window.activateWindow()
    QApplication.processEvents()

    declared = [widget.objectName() for widget in view.focus_chain()]
    assert declared == list(EXPECTED_VIEW_ORDER), f"the declared order changed: {declared}"

    expected = _reachable(view, EXPECTED_VIEW_ORDER, available)
    assert sorted(_focusable(view)) == sorted(expected), (
        f"{case}: reachable now is {sorted(_focusable(view))}, this state should offer "
        f"{sorted(expected)}"
    )

    first = view.findChild(QWidget, expected[0])
    assert first is not None
    first.setFocus()
    QApplication.processEvents()

    # **Anchored, not rotated** (`T060-R2`). This collected the walk into a *set*, which proved
    # every control was reached and nothing about the order. Focus is placed deliberately above,
    # so the sequence can be predicted outright rather than lined up after the fact — and an
    # anchored sequence is the strongest statement this walk can make.
    laps = len(expected) * 2
    forwards = _walk_focus_chain(shown_window, laps)
    assert forwards == [expected[step % len(expected)] for step in range(1, laps + 1)], (
        f"{case}: from {expected[0]}, two laps of Tab visited {forwards}; this state's chain is "
        f"{expected}"
    )

    first.setFocus()
    QApplication.processEvents()
    backwards = _walk_focus_chain(shown_window, laps, backwards=True)
    assert backwards == [expected[-step % len(expected)] for step in range(1, laps + 1)], (
        f"{case}: from {expected[0]}, two laps of Backtab visited {backwards}; reversed this "
        f"state's chain is {list(reversed(expected))}"
    )
