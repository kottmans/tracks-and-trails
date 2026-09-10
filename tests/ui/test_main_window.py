"""Shell window behavior (`T-007`).

Covers the acceptance criteria that can be asserted rather than looked at: the window
constructs and closes offscreen, carries the icon and title, exposes both menu actions, and
round-trips its geometry. Whether the icon *looks* right in a real Windows taskbar is not
automatable and stays an `OPS-003` known gap.
"""

from dataclasses import dataclass, field, replace
from pathlib import Path

import pytest
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QAction, QFont, QGuiApplication, QKeySequence, QTextLayout, QTextOption
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QToolBar,
    QWidget,
)

from tracks_and_trails import __version__
from tracks_and_trails.core import presets
from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import DownloadRequest, FormatInfo, Job, MediaInfo
from tracks_and_trails.core.paths import APP_SLUG
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.ui import main_window, theme
from tracks_and_trails.ui.format_dialog import FormatDialog
from tracks_and_trails.ui.main_window import (
    _MAX_COORD,
    ACTIONABLE_STATUS_PROPERTY,
    ADD_URLS_SHORTCUT_FALLBACK,
    APP_NAME,
    CLEAR_FINISHED_SHORTCUT,
    COULD_NOT_READ,
    DEFAULT_SIZE,
    NO_FORMATS,
    QUIT_SHORTCUT_FALLBACK,
    RUN_SHORTCUT,
    STARTED_MEANWHILE,
    TOOLBAR_SPACER_PROPERTY,
    YTDLP_DISPLAY_NAME,
    MainWindow,
    app_icon,
    geometry_path,
    is_a_usable_accelerator,
    load_geometry,
    moved_onto_a_screen,
    resolve_add_urls_shortcut,
    resolve_quit_shortcut,
    save_geometry,
)
from tracks_and_trails.ui.options_dialog import OptionsDialog
from tracks_and_trails.ui.row_delegate import CHOOSE_FORMATS_TEXT, OPTIONS_TEXT
from tracks_and_trails.ui.row_verbs import LABELS, Verb


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


def file_menu(window: MainWindow) -> tuple[list[str], list[QAction], list[QAction]]:
    """The `File` menu's item texts and its actions, with the menu kept alive.

    **The `QAction` wrappers are what keep the `QMenu` wrapper alive**, which is why they are
    returned rather than discarded: releasing them mid-test raises *"Internal C++ object (QMenu)
    already deleted"*. `tests/ui/test_windows_accessibility.py` records the same trap, and this
    helper hit it on its first run.
    """
    held = window.menuBar().actions()
    menu = next(
        menu
        for action in held
        if isinstance(menu := action.menu(), QMenu) and menu.title() == "&File"
    )
    items = menu.actions()
    return [action.text().replace("&", "") for action in items], items, held


def test_the_queue_verbs_are_on_the_file_menu_as_the_same_actions(qapp: QApplication) -> None:
    """**`T-246`.** A shortcut is a route; a menu item is somewhere to land.

    `T-200` gave `Start` and `Clear finished` their shortcuts, which makes them operable without a
    pointer — and leaves a screen-reader user nothing to hear, because `T-234` forbids a focusable
    widget on that toolbar and the drawn buttons take `NoFocus`. The menu item is the announcement
    the shortcut cannot make.

    **The same `QAction`, not a copy** — `T-130`'s rule, which `Add URLs...` has followed since it
    was written. Asserted with `is`, because two actions with equal text would satisfy anything
    weaker and would then drift apart the first time one of them was relabelled.
    """
    window = MainWindow(concurrency=3, control_bar=True)
    toolbar = window.findChild(QToolBar, "queueToolBar")
    assert toolbar is not None, "the queue toolbar is gone, so this proves nothing"
    run, clear = window.run_action, window.clear_completed_action
    assert run is not None and clear is not None

    names, on_the_menu, _held = file_menu(window)
    assert names == ["Add URLs...", "Start", "Clear finished", "", "Quit"], names

    on_the_bar = toolbar.actions()
    for verb, label in ((run, "Start"), (clear, "Clear finished")):
        assert any(action is verb for action in on_the_bar), f"{label} left the toolbar"
        assert any(action is verb for action in on_the_menu), (
            f"File → {label} is a different object from the toolbar's action, so the two can "
            "drift apart the first time either is relabelled or disabled"
        )

    assert run.shortcut().toString() == RUN_SHORTCUT
    assert clear.shortcut().toString() == CLEAR_FINISHED_SHORTCUT


# --- `Quit`'s accelerator survives a platform that does not name one (`T-270`) -----------------
#
# The gap was found on Windows and cannot be *reproduced* there from here, so these drive the
# resolver directly with the sequence Qt hands back rather than waiting for a runner. The Windows
# desktop suite keeps asserting the built window on the real platform; that is the observation,
# and this is the gate that fails on any machine when the fallback stops working.


@pytest.mark.parametrize(
    ("name", "verb"),
    [
        pytest.param("actionQuit", "Quit", id="Quit (T-270)"),
        pytest.param("actionAddUrls", "Add URLs…", id="Add URLs (T-271)"),
    ],
)
def test_the_menu_action_carries_a_usable_shortcut(
    window: MainWindow, name: str, verb: str
) -> None:
    """Both standard-key actions must be reachable from a keyboard, on every platform.

    **`isEmpty()` is not the assertion, and that is the whole of `T-271`'s first criterion.** The
    headless themes answer `StandardKey.Quit` with a bare `Qt.Key_Exit` — non-empty, stringifies to
    `"Exit"`, and untypeable as an accelerator — so the previous version of this passed on the
    pre-fix code and left the defect to the resolver tests alone. Asking whether the sequence is
    *usable* makes this bite offscreen too.

    **Both actions, in the suite both platforms run**, which is the third criterion: `T-271` was
    filed because nothing had ever asserted `Add URLs…`'s accelerator on any platform, so the gap
    was in the evidence rather than known to be in the behaviour.
    """
    actions = {action.objectName(): action for action in window.findChildren(QAction)}
    sequence = actions[name].shortcut()

    assert is_a_usable_accelerator(sequence), (
        f"{verb} answers {sequence.toString()!r}, which is not something a keyboard can type. A "
        "bare hardware key like Qt.Key_Exit is non-empty and unusable, which is the case "
        "isEmpty() misses"
    )


def test_a_bare_hardware_key_is_not_a_usable_accelerator(qapp: QApplication) -> None:
    """The discriminator `T-271` turns on, driven with the exact sequence that motivated it.

    `Qt.Key_Exit` is what the headless themes answer for `StandardKey.Quit`: non-empty, so an
    `isEmpty()` guard binds it, and carrying no modifier, so no keyboard produces it. An accelerator
    without a modifier would also swallow a plain keystroke from the rest of the window.

    Measured offscreen at PySide6 6.11.1 — `Quit` → `"Exit"`, `Preferences` → `"Settings"`, both
    `NoModifier`; `New` → `Ctrl+N`, `Open` → `Ctrl+O`, both with `Control`.
    """
    assert not is_a_usable_accelerator(QKeySequence(Qt.Key.Key_Exit))
    assert not is_a_usable_accelerator(QKeySequence()), "the empty sequence is still unusable"
    assert is_a_usable_accelerator(QKeySequence("Ctrl+N")), "a real accelerator was refused"


def test_the_add_urls_shortcut_falls_back_when_the_platform_names_nothing_usable(
    qapp: QApplication,
) -> None:
    """`T-271`, the half no runner is needed for: both unusable answers drive the fallback.

    Filed as a gap in evidence rather than an observed defect — `New` resolves to `Ctrl+N` on all
    four Linux plugins measured and has never been asserted on Windows. This does not claim Windows
    answers badly; it removes the class of failure `T-270` measured one line over.
    """
    assert resolve_add_urls_shortcut(QKeySequence()).toString() == ADD_URLS_SHORTCUT_FALLBACK
    exit_key = QKeySequence(Qt.Key.Key_Exit)
    assert resolve_add_urls_shortcut(exit_key).toString() == ADD_URLS_SHORTCUT_FALLBACK


@pytest.mark.parametrize(
    ("name", "seam"),
    [
        pytest.param("actionQuit", "resolve_quit_shortcut", id="Quit"),
        pytest.param("actionAddUrls", "resolve_add_urls_shortcut", id="Add URLs"),
    ],
)
def test_the_action_is_bound_through_the_seam_and_not_to_the_raw_standard_key(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, name: str, seam: str
) -> None:
    """The wiring, which every other test here passes without (`T-271`, `T289-R20`'s rule).

    **Offscreen cannot tell guarded from unguarded for `Add URLs…`**, because the headless theme
    answers `StandardKey.New` with a perfectly usable `Ctrl+N`. Reverting the binding to
    `setShortcut(QKeySequence.StandardKey.New)` leaves every assertion above green on Linux — the
    guard only does anything on a platform that answers badly, and none that has been measured
    does. A term no mutation can falsify is not a gate, which is what `T289-R20` ruled.

    So this asserts the seam is *used*: the resolver is replaced with one answering a sequence Qt
    would never pick, and the built action has to carry it. That fails the moment either action goes
    back to binding the standard key directly, on any platform.
    """
    sentinel = QKeySequence("Ctrl+Alt+Shift+F11")
    monkeypatch.setattr(main_window, seam, lambda *_args: sentinel)

    built = MainWindow(concurrency=1)
    try:
        actions = {action.objectName(): action for action in built.findChildren(QAction)}
        assert actions[name].shortcut().toString() == sentinel.toString(), (
            f"{name} does not go through {seam}(), so nothing decides what happens when the "
            "platform answers something unusable"
        )
    finally:
        built.close()
        built.deleteLater()


def test_the_add_urls_shortcut_keeps_what_the_platform_answers(qapp: QApplication) -> None:
    """A fallback, not a replacement — the same half `T-270`'s pair asserts for `Quit`.

    Binding `ADD_URLS_SHORTCUT_FALLBACK` unconditionally would leave the test above green while
    discarding every theme's opinion, including the `Ctrl+N` the measured plugins already answer.
    """
    theirs = QKeySequence("Ctrl+Shift+F8")
    assert resolve_add_urls_shortcut(theirs).toString() == "Ctrl+Shift+F8"


def test_the_quit_shortcut_falls_back_when_the_platform_names_none() -> None:
    """The Windows condition, driven on any platform: an empty standard key must not survive.

    This is the failure from run `32268124069` reproduced without a runner. Deleting the
    `isEmpty()` branch returns the empty sequence and fails here.
    """
    assert resolve_quit_shortcut(QKeySequence()).toString() == QUIT_SHORTCUT_FALLBACK


def test_the_quit_shortcut_keeps_what_the_platform_answers(qapp: QApplication) -> None:
    """A fallback, not a replacement — and this is the half that says so.

    Binding `QUIT_SHORTCUT_FALLBACK` unconditionally would leave the test above green while
    discarding every theme's opinion, including the `Ctrl+Q` that `xcb` and `wayland` already
    answer. Handing in a sequence Qt would never pick keeps this from passing by coincidence.
    """
    theirs = QKeySequence("Ctrl+Shift+F9")
    assert resolve_quit_shortcut(theirs).toString() == "Ctrl+Shift+F9"


def test_the_run_items_label_follows_the_queue_from_the_menu_too(qapp: QApplication) -> None:
    """One object means one label, so the menu cannot describe a state the toolbar has left.

    This is what *the same action* buys that a copy would not: nothing here updates the menu item.
    """
    window = MainWindow(concurrency=3, control_bar=True)
    assert file_menu(window)[0][1] == "Start"

    window.show_queue_running(True)
    assert file_menu(window)[0][1] == "Stop", (
        "the queue is running and File still offers Start — the menu item is not the toolbar's "
        "action, or its label is set in a second place"
    )

    window.show_queue_running(False)
    assert file_menu(window)[0][1] == "Start"


def test_a_window_with_no_control_bar_has_neither_queue_item(qapp: QApplication) -> None:
    """The all-or-nothing rule the two actions already followed, now visible on the menu.

    `_build_queue_actions` owns both, so a window built without a control bar has neither action —
    and must therefore offer neither item, rather than a menu route to a verb that does not exist.
    """
    window = MainWindow()
    assert window.run_action is None and window.clear_completed_action is None
    assert file_menu(window)[0] == ["Add URLs...", "", "Quit"]


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


#: Widths and point sizes the About blurb is laid out at below. The range is deliberately wider
#: than any box Qt actually builds: the property being asserted is that the tool's name cannot be
#: split *at any width*, which is stronger than checking the one width today's dialog happens to
#: pick and does not depend on that width staying the same.
_LAYOUT_WIDTHS = tuple(range(80, 601, 10))
_LAYOUT_POINTS = (9, 12, 15, 18, 19, 22)


def _wrapped_lines(text: str, font: QFont, width: int) -> list[str]:
    """The line boxes Qt's own breaker produces for `text` at `width`.

    `QTextLayout` rather than a rendered widget, because the question is about Qt's line-breaking
    decision and not about any one dialog's geometry — and reading a `QMessageBox`'s informative
    label would mean depending on `qt_msgbox_informativelabel`, the private child name `T278-R1`
    rejected.
    """
    layout = QTextLayout(text, font)
    option = QTextOption()
    option.setWrapMode(QTextOption.WrapMode.WordWrap)
    layout.setTextOption(option)
    layout.beginLayout()
    lines = []
    while True:
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(width)
        lines.append(text[line.textStart() : line.textStart() + line.textLength()])
    layout.endLayout()
    return lines


def _splits_the_name(text: str, name: str) -> bool:
    """Whether laying `text` out ever puts `name`'s two halves on different lines."""
    for point in _LAYOUT_POINTS:
        font = QFont(QApplication.font().family(), point)
        for width in _LAYOUT_WIDTHS:
            lines = _wrapped_lines(text, font, width)
            if not any(name in line for line in lines):
                return True
    return False


def test_the_about_blurb_writes_the_tool_name_unbreakably(window: MainWindow) -> None:
    """`T278-R1`: the About box must not render the tool's name as "yt-" / "dlp".

    **The mechanism is a character, not a layout rule, and this asserts the character is there.**
    `YTDLP_DISPLAY_NAME` uses `U+2011`; an ordinary `U+002D` is a break opportunity to Qt and is
    what produced the defect. A future edit that "fixes the typo" back is invisible on screen —
    the two codepoints are metrically identical — so it has to be caught here.
    """
    about = window.show_about()
    try:
        said = about.informativeText()
        assert YTDLP_DISPLAY_NAME in said, (
            f"the About blurb does not carry the non-breaking spelling: {said!r}"
        )
        assert "yt-dlp" not in said, (
            "the About blurb contains an ordinary hyphen in the tool's name, which Qt will break "
            f"across a line at the box's own width: {said!r}"
        )
    finally:
        about.close()


def test_the_tool_name_survives_every_width_and_font_size(window: MainWindow) -> None:
    """And the property itself, rather than the mechanism that delivers it.

    **`T278-R1` was a rule that held at the measured default and failed at 18 and 19 pt**, so a
    check pinned to one width or one font would have passed the defect it was written for. This
    lays the real blurb out at every width from 80 to 600 px and at six point sizes, and requires
    the name to survive all of them.
    """
    about = window.show_about()
    try:
        blurb = about.informativeText().replace("<br>", " ")
    finally:
        about.close()

    assert not _splits_the_name(blurb, YTDLP_DISPLAY_NAME), (
        "the About blurb splits the tool's name at some width or font size"
    )


def test_the_layout_check_can_see_a_name_that_does_split(window: MainWindow) -> None:
    """The control, and without it the test above proves nothing.

    **The submitted fix passed its own acceptance check while breaking at 18 and 19 pt**, because
    nothing ever fed the harness a known positive. So: take the shipped blurb, put the ordinary
    hyphen back, and require that the same sweep **finds** the split. If this stops failing, the
    sweep above has stopped discriminating and its green is meaningless.
    """
    about = window.show_about()
    try:
        blurb = about.informativeText().replace("<br>", " ")
    finally:
        about.close()

    breakable = blurb.replace(YTDLP_DISPLAY_NAME, "yt-dlp")
    assert _splits_the_name(breakable, "yt-dlp"), (
        "an ordinary hyphen no longer splits at any width this sweep tries, so "
        "test_the_tool_name_survives_every_width_and_font_size cannot tell the two spellings apart"
    )


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
    needs could only offer one that fails. A window built with `control_bar=False` has no toolbar,
    so it has no queue actions either — and `T-007`'s tests construct exactly that window.

    **The switch used to be `concurrency`** (`T-234`): one argument meant both *the limit* and
    *build the bar*, which held only while the bar's reason for existing was the spinner. `UX-013`
    moved that spinner to the Settings screen, and a gate still reading `concurrency is not None`
    would have taken *Start* and *Clear finished* down with it. The third assertion is the one
    that would have caught that — a window told the limit but not to build a bar.
    """
    bare = MainWindow()
    assert bare.run_action is None
    assert bare.clear_completed_action is None

    equipped = MainWindow(control_bar=True)
    assert equipped.run_action is not None
    assert equipped.clear_completed_action is not None

    limit_only = MainWindow(concurrency=3)
    assert limit_only.run_action is None, (
        "knowing the limit built a toolbar, so the two are still one switch"
    )


def test_the_window_has_no_concurrency_control_of_its_own(qapp: QApplication) -> None:
    """`UX-013`, `T-234`: `Settings → Settings…` is the only place the limit is set.

    **Asserted by name over the whole window**, not by reading the toolbar's actions. The
    neighbouring test compares `objectName()`s and skips the anonymous ones — a widget action
    holding a spin box has no action name, so a spinner left on the bar would pass it. The
    question here is whether the control exists *at all*, and the only assertion that answers it
    searches every child.

    **A `QSpinBox`, not the object name alone.** Removing the name while leaving the widget would
    satisfy a name search and leave two controls editing one value, which is the state `UX-013`
    ended.
    """
    window = _window_over([_job("a", 0)])
    assert window.findChild(QSpinBox, "concurrencyChoice") is None, (
        "the toolbar still carries the concurrency spinner UX-013 moved to the Settings screen"
    )
    assert not window.findChildren(QSpinBox), (
        "the window holds a spin box of some other name; the limit is the only number it ever "
        "asked a user to type, so a new one is either that control renamed or a change nobody "
        "declared"
    )


def test_the_toolbar_carries_the_three_verbs_and_the_spacer_and_nothing_else(
    qapp: QApplication,
) -> None:
    """`UX_SPEC` §2.1 as `UX-013` amended it: **three verbs and nothing else.**

    Every action on the bar, including the anonymous ones the name-set test filters out. The
    spacer is a widget action with no name of its own, so it is identified by the dynamic property
    `theme.py` styles it against — the same handle the sheet uses, which means a spacer that
    stopped carrying it would fail here *and* stop being styled, rather than silently becoming an
    unaccounted widget.
    """
    window = _window_over([_job("a", 0)])
    bar = window.findChild(QToolBar, "queueToolBar")
    assert bar is not None

    accounted: list[str] = []
    for action in bar.actions():
        if action.objectName():
            accounted.append(action.objectName())
            continue
        widget = bar.widgetForAction(action)
        if widget.property(TOOLBAR_SPACER_PROPERTY):
            accounted.append("<spacer>")
            continue
        accounted.append(f"<unaccounted {type(widget).__name__} {widget!r}>")

    assert accounted == [
        "actionAddUrls",
        "<spacer>",
        "runQueueAction",
        "clearCompletedAction",
    ], (
        f"the toolbar holds {accounted}. UX-013 left it three verbs with the spacer between what "
        "adds work and what acts on work already queued (UX-005 row 7); anything else on it is "
        "either a fourth verb or the concurrency control back"
    )


def test_nothing_on_the_toolbar_can_take_the_keyboard_from_the_rows(qapp: QApplication) -> None:
    """`T-234`'s focus criterion, answered by measurement rather than by reasoning.

    `T203-R3` recorded `Shift+F10` reaching the spin box's own edit menu instead of the row menu,
    because the spinner was the first thing on a freshly opened window that could hold focus.
    **With the spinner gone, no widget on the toolbar can**: `QToolBar` gives its buttons
    `NoFocus`, so the queue's table is the only focusable widget the window chrome has, and
    `_give_the_rows_the_keyboard` puts the keyboard there.

    **So the window needs no declared tab order** — there is nothing to order. That is the
    criterion's second half, and it is a fact about the widgets rather than a preference, which is
    why it is asserted here instead of written into a comment. A control added to the bar that
    *can* take focus fails this and has to answer `T203-R3` again.

    **`NFR-005`'s requirement is a keyboard route, not a place in the tab chain**, and that half of
    this docstring stands. What did not is how the route was supplied.

    *(This read: "The three verbs stay reachable without Tab: each carries a mnemonic (`&Start`),
    and `+ Add URLs` is `File → Add URLs…` as well." **The mnemonic half was false**, measured by
    `T-200` on 2026-08-15: every toolbar button's `shortcut()` is empty. Qt strips the `&` for
    display and registers no accelerator, because a `QAction`'s mnemonic binds in a **menu** — so
    `Start` and `Clear finished`, which are on no menu, had no keyboard route at all while this
    file recorded that they did. They carry `Ctrl+R` and `Ctrl+Shift+C` now. The criterion this
    test asserts is unchanged and was never the problem: it is right that nothing here takes
    focus, and it was the sentence explaining why that was carrying the gap.)*
    """
    window = _window_over([_job("a", 0)])
    bar = window.findChild(QToolBar, "queueToolBar")
    assert bar is not None

    grabby = [
        (type(child).__name__, child.objectName())
        for child in bar.findChildren(QWidget)
        if child.focusPolicy() is not Qt.FocusPolicy.NoFocus
    ]
    assert not grabby, (
        f"{grabby} on the toolbar can hold focus, so a freshly opened window may deliver Shift+F10 "
        "there instead of to the rows — the defect T203-R3 recorded against the spinner"
    )


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
    window = MainWindow(concurrency=3, control_bar=True, on_run_changed=reported.append)
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
    window = MainWindow(concurrency=3, control_bar=True, on_run_changed=reported.append)
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
    window = MainWindow(concurrency=3, control_bar=True)
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
    window = MainWindow(concurrency=3, control_bar=True)
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

    **Asserted on the shortcut, because the mnemonic never was the route** (`T200-R5`).

    *(This read: "Asserted through the action's own mnemonic rather than by simulating a key press:
    the toolbar button is built by Qt from the action, and `&S` is what makes `Alt`-navigation
    reach it." It does not. Measured by `T-200` on 2026-08-15: every toolbar button's `shortcut()`
    is empty, because a `QAction`'s mnemonic binds in a **menu** and this action is on none. Qt
    strips the `&` for display and registers nothing. So this test asserted the presence of an
    ampersand and called it reachability, and the control it names had no keyboard route at all for
    as long as it has existed.)*

    The `&` stays in the text — it is what the button would use if this action ever reached a menu,
    and `T-235` asserts the label — but it is `RUN_SHORTCUT` that makes the claim in this test's
    name true, so that is what is asserted.
    """
    window = MainWindow(concurrency=3, control_bar=True)
    action = window.run_action
    assert action is not None
    assert not action.shortcut().isEmpty(), (
        "the run control carries no shortcut, and its toolbar button takes no focus by T-234's "
        "criterion — so nothing reaches the one control that decides whether anything downloads"
    )
    assert action.shortcut().toString() == RUN_SHORTCUT, (
        f"the run control answers {action.shortcut().toString()!r}, not the {RUN_SHORTCUT} this "
        "project declares; a shortcut nobody documents is one nobody finds"
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
    return MainWindow(
        control_bar=True,
        manager=manager,
        queue=_FakeQueue(jobs),
        **handlers,  # type: ignore[arg-type]
    )


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
    window = MainWindow(concurrency=1, control_bar=True, on_clear_requested=lambda: asked.append(1))
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
    window = MainWindow(concurrency=3, control_bar=True)
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
        window = MainWindow(concurrency=3, control_bar=True)
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


# --- T-287: the window takes its dialogs down with it ------------------------------------------


def test_minimizing_hides_the_dialogs_and_restoring_brings_them_back(composed: MainWindow) -> None:
    """`T-287`, the maintainer's ruling of 2026-08-30.

    **Measured first, on KWin 6.7.3 / Wayland**: a plain `QMainWindow` and a correctly parented
    `QDialog` — `open()` or `exec()` alike — leave the dialog alone on the output when the window
    is minimized through KDE's panel-facing protocol. Compositor behaviour, not our parenting, so
    the ruling was to work around it rather than to fix a bug we do not have.

    **This drives `showMinimized()`, which is the *widget-state* route — Windows and X11.** It is
    not the panel's: KWin's panel minimize delivers no widget state change at all, and this
    docstring claimed the two were the same event until `T287-R1` measured otherwise. The Wayland
    route has its own regression, `test_the_surface_going_off_screen_hides_the_dialogs`, and both
    reach one idempotent decision.
    """
    dialog = composed.open_add_dialog()
    QApplication.processEvents()
    assert dialog.isVisible(), "the add dialog did not open, so this test has no subject"

    composed.showMinimized()
    QApplication.processEvents()

    assert not dialog.isVisible(), (
        "the add dialog stayed up while its window was minimized — the state T-287 was filed for, "
        "where a window-modal dialog outlives the window it is modal to"
    )

    composed.showNormal()
    QApplication.processEvents()

    assert dialog.isVisible(), "the add dialog did not come back with its window"


def test_a_second_state_change_while_minimized_does_not_forget_the_dialog(
    composed: MainWindow,
) -> None:
    """Window state is a set of flags; minimize is not necessarily its only transition.

    Changing another flag while the minimized bit remains set must not replace the restore set
    with the now-hidden (and therefore empty) visible-dialog set.
    """
    dialog = composed.open_add_dialog()
    QApplication.processEvents()

    composed.showMinimized()
    QApplication.processEvents()
    composed.setWindowState(Qt.WindowState.WindowMinimized | Qt.WindowState.WindowMaximized)
    QApplication.processEvents()
    composed.showNormal()
    QApplication.processEvents()

    assert dialog.isVisible(), "a second minimized-state event made the window forget its dialog"


def test_the_window_watches_its_native_surface_once_shown(composed: MainWindow) -> None:
    """`T287-R1`: the Wayland route needs the *native* window, and it only exists after `show()`.

    **The widget hears nothing when KDE's panel minimizes it** — measured on KWin 6.7.3, where
    `org_kde_plasma_window.set_state(MINIMIZED)` leaves `QMainWindow` with no `WindowStateChange`
    and `isMinimized()` false. The `QWindow` is what receives `Expose` with `isExposed()` false. So
    the work-around is only wired at all if the window is watching that object.
    """
    handle = composed.windowHandle()
    assert handle is not None, "the composed window has no native window, so nothing can watch it"
    assert composed._watched_surface is handle, (
        "the window is not watching its own native surface, so a panel-driven minimize reaches "
        "nothing — which is exactly what T287-R1 found"
    )


def test_the_surface_going_off_screen_hides_the_dialogs(composed: MainWindow) -> None:
    """`T287-R1`: the exposure route hides and restores, without any widget state change.

    **Driven through the real event, not through the decision it reaches.** Hiding the widget makes
    the offscreen platform deliver `Expose` with `isExposed()` false on the native window — measured
    — which is the same event KWin delivers on a panel minimize. So this exercises the wiring the
    reported route uses, rather than a substitute for it.

    **What it is still not** is a panel minimize: this hides the widget, and KWin does not. The
    end-to-end proof on a real KWin is a maintainer-run measurement and is recorded in the task as
    outstanding. Saying otherwise is what `T287-R1` was: the previous version asserted
    `showMinimized()` and the reported defect went untouched.
    """
    dialog = composed.open_add_dialog()
    QApplication.processEvents()
    assert dialog.isVisible()

    composed.hide()
    QApplication.processEvents()

    assert not composed.isMinimized(), (
        "the widget reports itself minimized, so this is not measuring the exposure route — the "
        "whole point is that Wayland never sets that state"
    )
    assert not dialog.isVisible(), "the exposure route did not take the dialog down"

    composed.show()
    QApplication.processEvents()
    assert dialog.isVisible(), "the exposure route did not bring the dialog back"


def test_a_modal_dialog_comes_back_modal(composed: MainWindow) -> None:
    """`T-287`'s third criterion: *modality survives the round trip*, asserted rather than observed.

    A dialog that returns without its modality is worse than one that never left — the user gets a
    window that looks interactive and a dialog that is no longer enforcing anything.
    """
    dialog = composed.open_add_dialog()
    QApplication.processEvents()
    before = dialog.windowModality()
    assert before != Qt.WindowModality.NonModal, (
        "the add dialog is not modal at all, so this test cannot prove modality survives"
    )

    composed.showMinimized()
    QApplication.processEvents()
    composed.showNormal()
    QApplication.processEvents()

    assert dialog.windowModality() == before, (
        f"the dialog came back {dialog.windowModality()} having been {before}"
    )
    assert dialog.isModal(), "the dialog came back not modal"


def test_nothing_typed_is_lost_across_a_minimize(composed: MainWindow) -> None:
    """`T-287`'s fourth criterion: *nothing is lost*.

    The dialogs are **hidden**, not closed, and this is what that buys. Closing them would be the
    naive fix the entry's Risk line warns about: it strands whatever the user was part-way through.
    """
    dialog = composed.open_add_dialog()
    QApplication.processEvents()
    box = dialog.findChild(QPlainTextEdit, "urlInput")
    assert box is not None, "the add dialog has no URL input under its declared name"
    box.setPlainText("https://example.invalid/half-typed")

    composed.showMinimized()
    QApplication.processEvents()
    composed.showNormal()
    QApplication.processEvents()

    assert box.toPlainText() == "https://example.invalid/half-typed", (
        "the paste did not survive the minimize, so the dialogs are being closed rather than hidden"
    )


def test_a_dialog_closed_while_minimized_does_not_come_back(composed: MainWindow) -> None:
    """Restoring puts back what was taken down — not what the user has since finished with.

    Reachable: the window is minimized with a dialog up, the dialog is dismissed from the taskbar's
    preview or by a shortcut, and the window is restored. Resurrecting it would be the window
    inventing a screen the user had closed.
    """
    dialog = composed.open_add_dialog()
    QApplication.processEvents()

    composed.showMinimized()
    QApplication.processEvents()
    dialog.close()
    QApplication.processEvents()

    composed.showNormal()
    QApplication.processEvents()

    assert not dialog.isVisible(), "a dialog closed while the window was minimized was re-shown"


def _manager_of(window: MainWindow) -> DownloadManager:
    """The window's manager, as a non-optional handle. Composition always supplies one here."""
    manager = window._manager
    assert manager is not None, "this window was built without a manager"
    return manager


@dataclass
class _Intercepted:
    """What the window tried to do to the queue, captured instead of performed.

    A real `DownloadManager` over `_EmptyJobStore` finds no job to revise, so a retarget would
    succeed silently and prove nothing; and `stage` would admit a real probe session. Both are
    replaced so the test observes the *intent*, which is what these paths are about.
    """

    staged: list[DownloadRequest] = field(default_factory=list)
    unstaged: list[str] = field(default_factory=list)
    written: list[tuple[str, DownloadRequest]] = field(default_factory=list)


def _intercept(window: MainWindow, *, probe_id: str = "probe-1") -> _Intercepted:
    record = _Intercepted()
    manager = _manager_of(window)

    def stage(request: DownloadRequest) -> str:
        record.staged.append(request)
        return f"{probe_id}-{len(record.staged)}" if len(record.staged) > 1 else probe_id

    def unstage(job_id: str) -> None:
        record.unstaged.append(job_id)

    def retarget(
        job_id: str,
        request: DownloadRequest,
        *,
        then: object = None,
        otherwise: object = None,
    ) -> None:
        record.written.append((job_id, request))

    manager.stage = stage  # type: ignore[method-assign]
    manager.unstage = unstage  # type: ignore[method-assign]
    manager.retarget = retarget  # type: ignore[method-assign]
    return record


def _job_with(request: DownloadRequest, job_id: str = "a") -> Job:
    """A queued job carrying `request`, so a test can say what the job was queued *with*."""
    return Job(
        id=job_id,
        url=request.url,
        request=request,
        status=JobStatus.QUEUED,
        queue_position=0,
        title="A clip",
    )


def _formats() -> tuple[FormatInfo, ...]:
    """One video-only stream and one audio-only stream, so a merge can be composed."""
    return (
        FormatInfo(
            "137",
            "mp4",
            height=1080,
            width=1920,
            video_codec="avc1.4d",
            has_video=True,
            has_audio=False,
            bitrate_kbps=4200.0,
        ),
        FormatInfo(
            "140",
            "m4a",
            audio_codec="mp4a.40.2",
            has_video=False,
            has_audio=True,
            bitrate_kbps=128.0,
        ),
    )


def test_the_rows_item_menu_offers_this_downloads_own_commands(qapp: QApplication) -> None:
    """`T-315`: the `⋮` holds what can be done to the **item**, not to its line.

    *"The options from that button seem completely redundant. I think it should give you
    options/choose formats like it does when you do it on the add urls."*

    `T-314` wired the zone to the overflow's slot, so it offered `verbs_of` — the four verbs the
    row already draws as buttons. **The verbs are asserted absent**, not merely the two entries
    present: a menu holding both would still be the redundancy that was reported.
    """
    window = _window_over([_job("a", 0)])
    menu = window._show_item_menu("a")
    assert menu is not None, "the row's ⋮ produced no menu"
    try:
        offered = [action.text() for action in menu.actions() if action.text()]
        assert CHOOSE_FORMATS_TEXT in offered, offered
        assert OPTIONS_TEXT in offered, offered
        verbs = {LABELS[verb] for verb in Verb}
        assert not verbs & set(offered), (
            f"the item menu repeats the row's own buttons: {sorted(verbs & set(offered))}"
        )
    finally:
        menu.close()


def test_a_started_download_is_offered_no_item_menu(qapp: QApplication) -> None:
    """Both entries end in `retarget`, which a started job refuses (`UX-005` §5).

    Offering them anyway would be a menu whose every entry fails — the defect `UX-005` §5 names,
    and the one the `⋮` was reported for in the first place.
    """
    window = _window_over([_job("a", 0, status=JobStatus.RUNNING)])
    assert window._show_item_menu("a") is None, "a running download was offered a way to retarget"


def test_choosing_formats_reads_the_url_again_rather_than_guessing(qapp: QApplication) -> None:
    """`T-315`, **ruled by the maintainer on 2026-09-10**: re-read rather than store.

    A queued `Job` carries its request, title, uploader, duration and thumbnail — **not its format
    list**, which lives in the add dialog's `MediaInfo` and is discarded when that dialog closes.
    So the table has nothing to show until the URL is read again.

    **Staged, not queued** (`UX-003`): `stage` reads a URL without creating a job, which is what
    this is — the job already exists.
    """
    window = _window_over([_job("a", 0)])
    record = _intercept(window)

    window._choose_job_formats("a")

    assert len(record.staged) == 1, "choosing formats did not read the URL again"
    assert record.staged[0].url == "https://example.invalid/clip"
    assert window._reading == {"probe-1": "a"}, window._reading


def test_a_second_press_while_reading_does_not_start_a_second_read(qapp: QApplication) -> None:
    """Two tables over one row would each write, and whichever was answered last would win."""
    window = _window_over([_job("a", 0)])
    record = _intercept(window)

    window._choose_job_formats("a")
    window._choose_job_formats("a")

    assert len(record.staged) == 1, f"{len(record.staged)} reads were started for one row"


def test_the_chosen_formats_compose_over_the_request_the_job_already_has(
    qapp: QApplication,
) -> None:
    """`T-315`: the streams change and **nothing else does** (`T-311`'s rule, one surface over).

    A queued request is whatever the add dialog composed for it — here an embedded thumbnail, a
    subtitle language and a naming pattern, none of which any shipped preset states. Rebuilding
    the request from a bare selector would discard all three, which is `T-313` arriving from a new
    direction; composing over `preset_of(job.request)` keeps them.

    Driven the whole way: the read is started, its result delivered on the manager's own signal,
    and the dialog answered by choosing in the table the way a user does.
    """
    request = replace(
        _job("a", 0).request,
        embed_thumbnail=True,
        subtitle_languages=("en",),
        output_template="%(uploader)s/%(title)s.%(ext)s",
    )
    window = _window_over([_job_with(request)])
    record = _intercept(window)

    window._choose_job_formats("a")
    # **Delivered on the manager's own signal** (`T315-R4`). Calling the slot would prove the slot
    # works and say nothing about whether anything is connected to it — which is the half of
    # `T-315` that a reviewer had to check by hand.
    _manager_of(window).media_probed.emit(
        "probe-1", MediaInfo(url=request.url, title="A clip", formats=_formats())
    )
    qapp.processEvents()

    dialog = window.findChild(FormatDialog)
    assert dialog is not None, "the read finished and no format table opened"
    try:
        for entry in _formats():
            dialog.table.choose(entry)
        dialog.accept()
        qapp.processEvents()
    finally:
        dialog.close()

    assert len(record.written) == 1, f"the chosen formats produced {len(record.written)}"
    job_id, new = record.written[0]
    assert job_id == "a"
    assert new.format_selector == "137+140", new.format_selector
    assert new.embed_thumbnail is True, "the job's own options were discarded"
    assert new.subtitle_languages == ("en",), "the job's subtitle choice was discarded"
    assert new.output_template == "%(uploader)s/%(title)s.%(ext)s", "the naming was discarded"


def test_a_failed_re_read_says_so_and_leaves_the_download_alone(qapp: QApplication) -> None:
    """`NFR-006`: the download the user already has is untouched, so this is not a modal.

    **The message reaches the status bar and no retarget is written.** A failure that silently did
    nothing would leave the user pressing a menu entry that never opens anything.
    """
    window = _window_over([_job("a", 0)])
    record = _intercept(window)

    window._choose_job_formats("a")
    # Through the manager, for `T315-R4`'s reason: the connection is part of the claim.
    _manager_of(window).job_failed.emit("probe-1", ErrorKind.NETWORK, "HTTP Error 403: Forbidden")

    said = window.statusBar().currentMessage()
    assert COULD_NOT_READ in said, said
    assert "403" in said, f"the extractor's own words were not passed on: {said!r}"
    assert record.written == [], "a failed read still rewrote the download"
    assert window._reading == {}, "the failed read is still remembered as in flight"


def test_a_probe_this_window_did_not_start_is_ignored(qapp: QApplication) -> None:
    """`media_probed` and `job_failed` are shared with every other probe in the process.

    The add dialog stages its own on these very signals, so membership of `_reading` — keyed on
    the **probe's** id — is what says a result is this window's to act on.
    """
    window = _window_over([_job("a", 0)])
    record = _intercept(window)

    manager = _manager_of(window)
    manager.media_probed.emit("someone-elses", MediaInfo(url="x", title="x", formats=_formats()))
    qapp.processEvents()
    assert window.findChild(FormatDialog) is None, "a table opened for somebody else's probe"

    # **`job_failed` is the half that carries the real risk**, because it also fires for genuine
    # queue jobs — every failed download in the application arrives here. Reporting one as a
    # failed re-read would put the wrong words in the status bar for something the user *was*
    # told about properly elsewhere.
    manager.job_failed.emit("job-that-really-failed", ErrorKind.NETWORK, "HTTP Error 500")
    assert COULD_NOT_READ not in window.statusBar().currentMessage(), (
        "a download's own failure was reported as a failed re-read"
    )
    assert record.unstaged == [], "a job this window never staged was unstaged"


def test_accepting_the_options_editor_unchanged_changes_nothing(qapp: QApplication) -> None:
    """`T-315`: *Options…* opens on the request the job **actually has**.

    **The strongest form of the claim: open it, accept it, change nothing.** If the editor opened
    on a catalogue preset matched by name — or on a fresh one — then pressing OK would write that
    preset's settings over the job's, and every field below would come back wrong. That is
    `T-313`'s silent discard arriving from a new direction, and `presets.preset_of` is what
    prevents it.

    The request deliberately agrees with no shipped preset: an embedded thumbnail, a subtitle
    language and a naming pattern, none of which any built-in states.
    """
    request = replace(
        _job("a", 0).request,
        embed_thumbnail=True,
        subtitle_languages=("en",),
        output_template="%(uploader)s/%(title)s.%(ext)s",
    )
    window = _window_over([_job_with(request)])
    record = _intercept(window)

    window._edit_job_options("a")
    qapp.processEvents()
    dialog = window.findChild(OptionsDialog)
    assert dialog is not None, "the item menu's Options… opened nothing"
    try:
        dialog.accept()
        qapp.processEvents()
    finally:
        dialog.close()

    assert len(record.written) == 1, f"accepting the options wrote {len(record.written)}"
    _job_id, kept = record.written[0]
    assert presets.format_choice_of(kept) == presets.format_choice_of(request), (
        "accepting the options editor without changing anything changed the download"
    )


def test_a_re_read_that_finds_no_formats_says_so_and_opens_nothing(qapp: QApplication) -> None:
    """`T315-R4`: one of the two endings no committed test exercised.

    A URL that still reads but offers nothing to choose from is an ordinary outcome — a video made
    private, a live stream that ended. Opening an empty table would be `UX-005` §5's defect; saying
    nothing would leave a menu entry that appears to do nothing at all.
    """
    window = _window_over([_job("a", 0)])
    record = _intercept(window)

    window._choose_job_formats("a")
    _manager_of(window).media_probed.emit("probe-1", MediaInfo(url="x", title="x", formats=()))
    qapp.processEvents()

    assert window.findChild(FormatDialog) is None, "an empty format table opened"
    assert NO_FORMATS in window.statusBar().currentMessage()
    assert record.written == [], "a read that found nothing still rewrote the download"
    assert record.unstaged == ["probe-1"], "the probe was left staged"


def test_a_download_that_starts_while_being_read_is_not_retargeted(qapp: QApplication) -> None:
    """`T315-R4`: the other ending, and the one with a real race behind it.

    The re-read takes a second or two, and the queue is running throughout. A job that starts in
    that window is past `Job.RETARGETABLE`, so opening the table would offer a choice `retarget`
    would refuse — and the user would believe the format changed.
    """
    jobs = [_job("a", 0)]
    window = _window_over(jobs)
    record = _intercept(window)

    window._choose_job_formats("a")
    # **The job starts while the URL is being read**, through the list the window reads and the
    # refresh the window itself calls after a write — rather than by reaching into the model, which
    # would be this test arranging the state instead of reaching it.
    jobs[0] = _job("a", 0, status=JobStatus.RUNNING)
    window.refresh_queue()

    _manager_of(window).media_probed.emit(
        "probe-1", MediaInfo(url="x", title="x", formats=_formats())
    )
    qapp.processEvents()

    assert window.findChild(FormatDialog) is None, "a table opened for a download already running"
    assert STARTED_MEANWHILE in window.statusBar().currentMessage()
    assert record.written == [], "a running download was retargeted"
