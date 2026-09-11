"""The Settings screen (`REQ-023`, `T-146`).

Driven through the screen's own controls by object name, never by calling the handler behind
them: what `T-146` promises is that a *user* can change where downloads go and what the window
looks like, and a test that called `_remember` would prove the method exists.

The directory picker is injected (`SettingsDialog.choose_directory`) because a native modal
cannot be driven headlessly — the same seam, and the same reasoning, as the manager's
`entry_point`. What that gives up is `QFileDialog` itself, which is Qt's; what it keeps is every
line of this application's own behaviour on both answers, chosen and cancelled.
"""

import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QWidget,
)

from tracks_and_trails.core import presets as preset_registry
from tracks_and_trails.core import settings as core_settings
from tracks_and_trails.core.models import NetworkOptions
from tracks_and_trails.ui import theme
from tracks_and_trails.ui import theme as ui_theme
from tracks_and_trails.ui.preset_manager import (
    DEFAULT_MARK,
    PRESET_LIST_NAME,
    SET_DEFAULT_NAME,
    PresetManager,
)
from tracks_and_trails.ui.settings_dialog import (
    DEFAULT_PRESET_NAME,
    DEFAULT_RETRIES_LABEL,
    DOWNLOAD_DIRECTORY_PROBLEM_NAME,
    NO_COOKIES_NOTE,
    NO_RATE_LIMIT_LABEL,
    OUTPUT_TEMPLATE_NAME,
    OUTPUT_TEMPLATE_NOTE_NAME,
    PROXY_NAME,
    PROXY_NOTE_NAME,
    RATE_LIMIT_NAME,
    RATE_LIMIT_STEP_BYTES,
    RETRIES_NAME,
    SETTINGS_SCROLL_NAME,
    SETTINGS_STILL_TO_COME,
    STEP_DOWN_LABEL,
    STEP_UP_LABEL,
    YTDLP_RECOVERY_NOTE,
    YTDLP_RECOVERY_NOTE_NAME,
    YTDLP_REVERT_NAME,
    YTDLP_UPDATE_LABEL,
    YTDLP_UPDATE_NAME,
    SettingsDialog,
)


@pytest.fixture
def screens(
    qapp: QApplication, tmp_path: Path
) -> Iterator[Callable[..., tuple[SettingsDialog, dict[str, Any]]]]:
    """Build settings screens, and hand back what each one asked composition to do."""
    built: list[SettingsDialog] = []

    def build(**overrides: Any) -> tuple[SettingsDialog, dict[str, Any]]:
        asked: dict[str, Any] = {}
        overrides.setdefault("download_directory", tmp_path / "downloads")
        overrides.setdefault("directory_is_default", True)
        overrides.setdefault("theme", "light")
        overrides.setdefault("concurrency", 3)
        overrides.setdefault("on_directory_chosen", lambda value: asked.update(directory=value))
        overrides.setdefault("on_theme_chosen", lambda value: asked.update(theme=value))
        overrides.setdefault("concurrency_sink", None)
        sink = overrides.pop("concurrency_sink")
        overrides.setdefault(
            "on_concurrency_chosen", sink or (lambda value: asked.update(concurrency=value))
        )
        # Recorded here rather than by each test, so a test never has to close over the `asked`
        # dict it is about to be handed — which reads as a forward reference and `mypy` refuses it.
        # Pass `None` explicitly for a screen that is meant to have nothing behind the control.
        overrides.setdefault(
            "on_default_preset_chosen", lambda value: asked.update(default_preset=value)
        )
        overrides.setdefault(
            "on_output_template_chosen", lambda value: asked.update(template=value)
        )
        screen = SettingsDialog(**overrides)
        built.append(screen)
        return screen, asked

    yield build

    for screen in built:
        screen.close()
    QApplication.processEvents()


def control(screen: SettingsDialog, kind: type, name: str) -> Any:
    """One control by its declared object name, as every other UI test reaches one.

    `findChild` is typed as always finding something, so the assertion below is written against
    the runtime answer rather than the annotation — a missing control must name itself here and
    not surface as an `AttributeError` three lines later.
    """
    found: Any = screen.findChild(kind, name)
    assert found is not None, f"the settings screen has no {kind.__name__} named {name!r}"
    return found


def test_the_screen_says_which_settings_it_does_not_cover(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**`T-146`'s honesty criterion**, on the screen rather than only in a document.

    `REQ-023` names eight settings and this screen builds **all eight** since `T-196`. A settings
    screen showing only what it implements reads as complete, so any absence is stated where the
    user is looking — and there is none left to state.

    **The sentence shrinking to nothing is this test working, not being weakened.** Each task that
    landed one of the eight took its name out (`T-199` the ffmpeg location, `T-197` the cookie
    source, `T-195` two more), and `T-196` took the last. What is asserted now is the pair that
    has to hold together: nothing is named as missing, **and** the label carrying the sentence is
    not built — an empty label is still a line of the dialog and still a stop for a screen reader.
    """
    screen, _ = screens()

    assert SETTINGS_STILL_TO_COME == "", (
        "every REQ-023 setting is built, so the screen has nothing to say is still to come: "
        f"{SETTINGS_STILL_TO_COME!r}"
    )
    assert screen.findChild(QLabel, "settingsRemaining") is None, (
        "the still-to-come label is built with nothing in it, which is a claim about coverage "
        "made in whitespace"
    )
    for built, by in (
        ("ffmpeg", "T-199"),
        ("cookie", "T-197"),
        ("default preset", "T-195"),
        ("output template", "T-195"),
        ("network", "T-196"),
    ):
        assert built not in SETTINGS_STILL_TO_COME.lower(), (
            f"the screen still says {built} is to come, but {by} built it"
        )


def test_choosing_a_folder_reports_it_and_shows_it(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    tmp_path: Path,
) -> None:
    """The download folder: chosen through the button, handed to composition, and displayed."""
    chosen_folder = tmp_path / "Trail recordings"
    chosen_folder.mkdir()
    screen, asked = screens(choose_directory=lambda _start: chosen_folder)

    control(screen, QPushButton, "chooseDownloadDirectory").click()

    assert asked.get("directory") == chosen_folder, (
        f"the screen reported {asked.get('directory')!r} to composition, not the chosen folder"
    )
    assert control(screen, QLineEdit, "downloadDirectoryValue").text() == str(chosen_folder)


def test_cancelling_the_picker_changes_nothing(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    tmp_path: Path,
) -> None:
    """**Cancelled is not "use the default"**, and collapsing the two would move files silently.

    `QFileDialog` answers an empty string when dismissed; the screen must treat that as *no
    request was made*, not as the request its other button makes.
    """
    started = tmp_path / "downloads"
    screen, asked = screens(
        download_directory=started, directory_is_default=True, choose_directory=lambda _s: None
    )

    control(screen, QPushButton, "chooseDownloadDirectory").click()

    assert "directory" not in asked, (
        f"a cancelled picker still asked composition for {asked.get('directory')!r}"
    )
    assert control(screen, QLineEdit, "downloadDirectoryValue").text() == str(started)


def test_the_default_folder_is_offered_only_when_one_was_chosen(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    tmp_path: Path,
) -> None:
    """*Use the default folder* clears the choice, and is disabled when there is none to clear.

    Disabled rather than hidden, so the row does not change shape under the pointer — the rule
    `T-060` applies to the add dialog's retry button, and the reason the chain is stable.
    """
    default_screen, _ = screens(directory_is_default=True)
    assert not control(default_screen, QPushButton, "useDefaultDownloadDirectory").isEnabled(), (
        "the screen offers to clear a choice that was never made"
    )

    chosen_screen, asked = screens(
        download_directory=tmp_path / "chosen", directory_is_default=False
    )
    clear = control(chosen_screen, QPushButton, "useDefaultDownloadDirectory")
    assert clear.isEnabled()
    clear.click()

    assert "directory" in asked and asked["directory"] is None, (
        "clearing the folder must ask composition for the platform default, which is None here — "
        f"it asked for {asked.get('directory')!r}"
    )


def test_the_resolved_default_folder_comes_back_from_composition(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    tmp_path: Path,
) -> None:
    """The screen shows what composition resolved, rather than guessing the platform's answer.

    `ui/` holds no platform paths (`ARC-007`), so *use the default* is a request whose answer
    arrives back through `show_download_directory`.
    """
    screen, _ = screens(download_directory=tmp_path / "chosen", directory_is_default=False)
    platform_folder = tmp_path / "Downloads"

    screen.show_download_directory(platform_folder, is_default=True)

    assert control(screen, QLineEdit, "downloadDirectoryValue").text() == str(platform_folder)
    assert not control(screen, QPushButton, "useDefaultDownloadDirectory").isEnabled()


def test_a_typed_folder_is_taken_when_the_field_is_left(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    tmp_path: Path,
) -> None:
    """`T-292`: the folder was a `QLabel`, so a path on the clipboard could not be pasted."""
    typed = tmp_path / "Sort"
    typed.mkdir()
    screen, asked = screens(download_directory=tmp_path / "downloads")

    field = control(screen, QLineEdit, "downloadDirectoryValue")
    field.setText(str(typed))
    field.editingFinished.emit()

    assert asked.get("directory") == typed, (
        f"the screen reported {asked.get('directory')!r} to composition, not the typed folder"
    )


def test_a_typed_folder_is_not_taken_while_it_is_being_typed(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    tmp_path: Path,
) -> None:
    """A deliberate exception to *"every control applies as it is changed"* (row 6.2).

    Applying per keystroke would set `/h`, then `/ho`, then `/hom` — each a different destination,
    and each one a write. The value commits when the field is left or `Return` is pressed.
    """
    typed = tmp_path / "Sort"
    typed.mkdir()
    screen, asked = screens(download_directory=tmp_path / "downloads")

    control(screen, QLineEdit, "downloadDirectoryValue").setText(str(typed))

    assert "directory" not in asked, (
        f"typing alone reported {asked.get('directory')!r}, so a half-typed path became a setting"
    )


def test_a_folder_that_does_not_exist_is_refused_and_the_field_put_back(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    tmp_path: Path,
) -> None:
    """Ruled 2026-08-28: refused, not created and not offered for creation.

    **The field is restored**, because a screen still showing a path it did not accept is a screen
    lying about where files will land — `T109-R2`'s rule one control over.
    """
    started = tmp_path / "downloads"
    missing = tmp_path / "nowhere" / "at" / "all"
    screen, asked = screens(download_directory=started)

    field = control(screen, QLineEdit, "downloadDirectoryValue")
    field.setText(str(missing))
    field.editingFinished.emit()

    assert "directory" not in asked, (
        f"a folder that does not exist was reported to composition: {asked.get('directory')!r}"
    )
    assert not missing.exists(), "the folder was created; the ruling was that it is refused"
    assert field.text() == str(started), (
        f"the field still shows {field.text()!r}, which is not where downloads will go"
    )
    problem = control(screen, QLabel, DOWNLOAD_DIRECTORY_PROBLEM_NAME).text()
    assert str(missing) in problem and problem, (
        f"the refusal does not name the folder it refused: {problem!r}"
    )


def test_a_file_where_a_folder_belongs_is_refused_in_its_own_words(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    tmp_path: Path,
) -> None:
    """*"is not a folder that exists"* would be a lie about a path that does exist."""
    a_file = tmp_path / "notes.txt"
    a_file.write_text("x")
    screen, asked = screens(download_directory=tmp_path)

    field = control(screen, QLineEdit, "downloadDirectoryValue")
    field.setText(str(a_file))
    field.editingFinished.emit()

    assert "directory" not in asked
    assert "file" in control(screen, QLabel, DOWNLOAD_DIRECTORY_PROBLEM_NAME).text().lower(), (
        "a file was refused as though it were a missing folder"
    )


def test_a_folder_that_cannot_be_written_to_is_refused(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    tmp_path: Path,
) -> None:
    """Checklist 7.1 arranges this at download time; refusing it here is cheaper for the user.

    **POSIX only, and the Windows job is what said so.** `chmod(0o500)` sets the read-only
    attribute, which Windows applies to files and not to directories — so the folder stayed
    writable, `os.access` agreed, and the screen accepted it. That is the test failing to build
    its own precondition, not the screen accepting an unwritable folder: `core/settings.py`
    already records that `os.access` reads the read-only attribute rather than the ACL there.
    `tests/unit/test_settings.py` guards its equivalent the same way, and this is the same skip.

    Skipped as root too, which bypasses the permission bits entirely and would leave this
    asserting that `os.access` agrees with itself.
    """
    # Asked of the attribute rather than of `sys.platform`, which mypy narrows under
    # `--platform win32` until everything after it is unreachable — `test_settings.py`'s note.
    effective_user = getattr(os, "geteuid", None)
    if effective_user is None:
        pytest.skip("POSIX permission bits are not how Windows refuses a write")
    if effective_user() == 0:
        pytest.skip("root ignores the permission bits this asserts on")
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        screen, asked = screens(download_directory=tmp_path)

        field = control(screen, QLineEdit, "downloadDirectoryValue")
        field.setText(str(locked))
        field.editingFinished.emit()

        assert "directory" not in asked, "a folder that cannot be written to became the setting"
        assert control(screen, QLabel, DOWNLOAD_DIRECTORY_PROBLEM_NAME).text()
    finally:
        locked.chmod(0o700)


def test_a_tilde_is_understood_rather_than_refused(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`~/…` is a folder a user can reasonably expect this field to understand.

    Refusing it as *"not a folder that exists"* would be true of the literal text and false about
    what they typed.

    **The home directory is a writable `tmp_path`, not the account's own** (`T292-R3`). Reading the
    real one conflated two claims: that `~` is expanded, and that whatever it expands to happens to
    be writable by the process running the test. Under a sandbox with a read-only `/home/sean` the
    expansion was correct and the product correctly refused the folder, and the test failed for a
    reason that had nothing to do with what it is named after.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    screen, asked = screens(download_directory=tmp_path)

    field = control(screen, QLineEdit, "downloadDirectoryValue")
    field.setText("~")
    field.editingFinished.emit()

    assert asked.get("directory") == home, (
        f"a tilde was not expanded before the check: {asked.get('directory')!r}"
    )


#: The account in the two tests below. Long enough that no host has one, and it is asserted on
#: rather than the whole typed path — see the portable test's docstring for why.
NO_SUCH_ACCOUNT = "tracks_and_trails_user_that_cannot_exist_28493"


def test_a_tilde_naming_no_one_is_refused_and_the_field_put_back(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    tmp_path: Path,
) -> None:
    """`T292-R1`, asserted as the contract rather than as one platform's branch.

    **The first version of this test asserted the POSIX branch and failed the Windows job**, which
    runs the whole suite. `Path("~nosuchuser/x").expanduser()` raises `RuntimeError` on POSIX
    because no `pwd` entry exists, so the screen refuses in the *could not be read* words and
    names the path **as written**. On Windows `ntpath.expanduser` guesses a sibling of
    `%USERPROFILE%` instead, nothing raises, and the guessed path simply is not there — so the
    *missing folder* branch refuses and names the guess. Measured, from run `33228591432`:
    `C:\\Users\\<account>\\downloads is not a folder that exists.`

    That is `T146-R3` exactly, one layer up: `tests/unit/test_settings.py` had this same test,
    made this same mistake, and had it caught in review. **The account name is the portable
    assertion** — verbatim in one message, inside the guessed path in the other — so it is how to
    ask *"does this name what it refused?"* without asserting a platform.

    What must hold either way: nothing reached composition, a refusal is on screen naming the
    account, and the field shows the folder still in force.
    """
    started = tmp_path / "downloads"
    started.mkdir()
    screen, asked = screens(download_directory=started)

    field = control(screen, QLineEdit, "downloadDirectoryValue")
    field.setText(f"~{NO_SUCH_ACCOUNT}/downloads")
    field.editingFinished.emit()

    assert "directory" not in asked, (
        f"a path naming no one reached composition: {asked.get('directory')!r}"
    )
    problem = control(screen, QLabel, DOWNLOAD_DIRECTORY_PROBLEM_NAME).text()
    assert NO_SUCH_ACCOUNT in problem, (
        f"the screen said nothing the user could act on about what they typed: {problem!r}"
    )
    assert field.text() == str(started), (
        f"the field kept the text it refused, so it shows {field.text()!r} and downloads go to "
        f"{started}"
    )


@pytest.mark.skipif(
    os.name != "posix",
    reason=(
        "the RuntimeError branch needs an expansion that cannot resolve a home, which is POSIX's "
        "answer for an unknown ~user; Windows guesses a path instead and reaches the missing-"
        "folder branch, which the portable test above covers"
    ),
)
def test_an_expansion_that_cannot_resolve_a_home_is_refused_rather_than_raised(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    tmp_path: Path,
) -> None:
    """**`T292-R1`'s own branch**, where it can be reached without asserting a guess.

    **Measured through the real slot, not `Path.expanduser` in isolation.**
    `Path("~nosuchuser/downloads").expanduser()` raises
    `RuntimeError("Could not determine home directory.")`, and that call sat above every refusal —
    so the exception left `_directory_typed`, no message was shown at all, and the field kept the
    text that caused it. Removing the guard fails this by **erroring**, which is the shape the
    defect had. The same defect `T146-R1` fixed in the settings loader, one layer up.

    This is the test that carries the mutation evidence; the portable one above carries the
    contract.
    """
    started = tmp_path / "downloads"
    started.mkdir()
    screen, asked = screens(download_directory=started)
    typed = f"~{NO_SUCH_ACCOUNT}/downloads"

    field = control(screen, QLineEdit, "downloadDirectoryValue")
    field.setText(typed)
    field.editingFinished.emit()

    assert "directory" not in asked, (
        f"a path that could not even be expanded reached composition: {asked.get('directory')!r}"
    )
    problem = control(screen, QLabel, DOWNLOAD_DIRECTORY_PROBLEM_NAME).text()
    assert typed in problem, (
        f"the refusal does not name the path as written, which is all there is to name when the "
        f"expansion is what failed: {problem!r}"
    )
    assert "RuntimeError" in problem, (
        f"the refusal does not say what went wrong, so nobody can tell it from a typo: {problem!r}"
    )


def test_a_relative_folder_is_settled_to_one_that_survives_a_restart(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`T292-R2`: `.` is a different folder every time the process starts somewhere else.

    The relative spelling went out to composition unchanged and was persisted that way, so the
    setting named the launch directory rather than a folder. This types the relative form from a
    known working directory and asserts the **absolute** value both leaves the screen and comes
    back onto it — the reopened display, which is what the user checks the setting by.
    """
    here = tmp_path / "sorted"
    here.mkdir()
    monkeypatch.chdir(here)
    screen, asked = screens(download_directory=tmp_path / "downloads")

    field = control(screen, QLineEdit, "downloadDirectoryValue")
    field.setText(".")
    field.editingFinished.emit()

    assert asked.get("directory") == here, (
        f"composition was handed {asked.get('directory')!r}, which is resolved against whatever "
        f"directory the next launch happens to start in"
    )
    assert asked["directory"].is_absolute(), (
        "the stored destination has no root, so it names a different folder on the next launch"
    )
    assert field.text() == str(here), (
        f"the field still shows the relative spelling {field.text()!r}, so reopening Settings "
        f"from another directory would show a path that means somewhere else"
    )


def test_the_refusal_clears_once_the_folder_is_settled(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    tmp_path: Path,
) -> None:
    """A message about a path nobody is proposing any more is noise that outlives its cause."""
    good = tmp_path / "good"
    good.mkdir()
    screen, _ = screens(download_directory=tmp_path)
    field = control(screen, QLineEdit, "downloadDirectoryValue")

    field.setText(str(tmp_path / "missing"))
    field.editingFinished.emit()
    assert control(screen, QLabel, DOWNLOAD_DIRECTORY_PROBLEM_NAME).text()

    field.setText(str(good))
    field.editingFinished.emit()

    assert not control(screen, QLabel, DOWNLOAD_DIRECTORY_PROBLEM_NAME).text(), (
        "the refusal outlived the path it was about"
    )


def test_picking_a_theme_reports_it_once(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """Light and dark, as radio buttons, reported when chosen and not when cleared.

    `toggled` fires for the button being *un*checked as well as the one being checked, so a naive
    handler reports twice per change — once with the old name. Counted here rather than assumed.
    """
    reported: list[str] = []
    screen, _ = screens(theme="light", on_theme_chosen=reported.append)

    assert control(screen, QRadioButton, "themeLight").isChecked(), (
        "the screen opened without showing which theme is in force"
    )
    control(screen, QRadioButton, "themeDark").click()

    assert reported == ["dark"], f"choosing dark reported {reported}"
    assert control(screen, QRadioButton, "themeDark").isChecked()


def test_the_concurrency_control_shows_what_was_applied_without_echoing_it(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**Showing must not report** (`REQ-013`). A `setValue` that emitted `valueChanged` would call
    composition, which would call back here, which is a loop rather than a sync.

    *(This was `..._mirrors_the_toolbars_...`, and it was about `T-146`'s recorded choice to keep
    **two controls, one value**. `UX-013` removed the toolbar's copy and `T-234` carried it out, so
    there is no second control to mirror. The property survives the removal with a different
    reason: what `show_concurrency` follows now is **composition**, whose applied value is not
    always the number this control emitted — `settings.toml` clamps — and a screen that reported
    the applied value back would turn one clamp into a loop.)*
    """
    reported: list[int] = []
    screen, _ = screens(concurrency=3, concurrency_sink=reported.append)
    spinner = control(screen, QSpinBox, "settingsConcurrencyChoice")

    assert spinner.value() == 3
    assert spinner.minimum() == core_settings.CONCURRENCY_MINIMUM
    assert spinner.maximum() == core_settings.CONCURRENCY_MAXIMUM, (
        "the screen's range is its own rather than the settings layer's, so a hand-edited file "
        "and this control would disagree about what is allowed"
    )

    spinner.setValue(5)
    assert reported == [5], f"changing the screen's spinner reported {reported}"

    screen.show_concurrency(2)
    assert spinner.value() == 2
    assert reported == [5], (
        f"showing the applied limit reported it back to composition: {reported}. A control that "
        "echoes what it is told turns one user change into a round trip"
    )


def test_the_concurrency_control_steps_with_labelled_buttons(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """`UX-005` row 11 (`T-141`), rebuilt on this screen by `T-236`.

    The ruling is about **the concurrency control**, not about the toolbar it used to sit on, so
    `UX-013` moving the control moved this with it. `T-234` did not, and left the only control for
    the limit at 57x22 with the native `UpDownArrows` — materially the 58x23 control whose wedges
    `T-141` measured as unreadable at the real size (`T234-R2`).

    **`NoButtons` is asserted as well as the labels.** A control offering both would offer two ways
    to step with one of them the unreadable one this replaced, and that is the mutation which
    otherwise survives.
    """
    screen, _ = screens(concurrency=3)
    box = control(screen, QSpinBox, "settingsConcurrencyChoice")
    fewer = control(screen, QToolButton, "settingsConcurrencyStepDown")
    more = control(screen, QToolButton, "settingsConcurrencyStepUp")

    assert (fewer.text(), more.text()) == (STEP_DOWN_LABEL, STEP_UP_LABEL)
    assert box.buttonSymbols() is QAbstractSpinBox.ButtonSymbols.NoButtons, (
        "the spin box still draws its own arrows, so the control offers two ways to step and one "
        "of them is the unreadable one this replaced"
    )

    started = box.value()
    more.click()
    assert box.value() == started + 1, "the + button does not step the value"
    fewer.click()
    assert box.value() == started, "the minus button does not step the value"

    # **Each announces the direction *and* the setting** (`NFR-005`): "Plus" alone says nothing
    # about what it increases, and the visible label is one character.
    for button in (fewer, more):
        announced = button.accessibleName()
        assert "concurrent downloads" in announced.lower(), (
            f"a step button announces {announced!r}, which does not say what it changes"
        )


def test_a_step_button_is_disabled_at_its_end_of_the_range(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """`UX-005` §5: a control must not offer a choice nothing acts on.

    Both ends, because a test at one would pass with the other button permanently enabled.
    """
    screen, _ = screens(concurrency=3)
    box = control(screen, QSpinBox, "settingsConcurrencyChoice")
    fewer = control(screen, QToolButton, "settingsConcurrencyStepDown")
    more = control(screen, QToolButton, "settingsConcurrencyStepUp")

    box.setValue(core_settings.CONCURRENCY_MINIMUM)
    assert not fewer.isEnabled(), "the minus button offers a step below the minimum"
    assert more.isEnabled(), "the + button is disabled at the minimum, where it can still step"

    box.setValue(core_settings.CONCURRENCY_MAXIMUM)
    assert not more.isEnabled(), "the + button offers a step above the maximum"
    assert fewer.isEnabled(), "the minus button is disabled at the maximum, where it can still step"


def test_the_step_buttons_are_a_matched_pair(
    qapp: QApplication, screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]]
) -> None:
    """`T-141`, corrected: the minus looked boxed and the plus did not.

    Left bare, both were transparent text — and the sheet's global `*:focus` rule then drew an
    accent border on whichever one had focus, so the pair was asymmetric depending on what the
    user had last clicked. **Two controls doing the same thing in opposite directions must not
    differ in whether they look like controls at all.**

    Asserted as *sameness*, which is the property, rather than as a particular size or colour —
    pinning either would pin a styling choice instead.

    **The selector is the thing most likely to break here** (`T-236`). The sheet rule said
    `QToolBar QToolButton[stepButton="true"]` while the control was on a toolbar; on this screen
    that matches nothing, and the failure is silent — the buttons simply go back to looking like
    text, which is the defect this test exists for.
    """
    was_sheet, was_palette = qapp.styleSheet(), qapp.palette()
    try:
        theme.apply(qapp, theme.LIGHT)
        screen, _ = screens(concurrency=3)
        screen.resize(700, 700)
        screen.show()
        qapp.processEvents()
        fewer = control(screen, QToolButton, "settingsConcurrencyStepDown")
        more = control(screen, QToolButton, "settingsConcurrencyStepUp")

        assert fewer.size() == more.size(), (
            f"the step buttons are {fewer.size()} and {more.size()}; a pair that does the same "
            "thing in two directions must be one shape"
        )

        # **The sheet is what paints them, and this is how that is checked.**
        #
        # *A size assertion does not do it, and the first version of this test used one.* Measured
        # against the `QToolBar`-scoped selector: styled the button is 17x25 with a `#748A7E` edge;
        # unstyled it is 21x24 with a `#AFB0AE` one — **Qt falls back to the platform's own tool
        # button frame**, so it is neither invisible nor obviously smaller, and `width > 10` passed
        # against the mutation this test names. That mutation is the whole point of the test.
        #
        # **The colour is read from the theme, not written down here** — `T-141`'s own record warns
        # that pinning a size or a colour pins a styling choice. What is asserted is that the edge
        # is *the theme's border*, which only the sheet can make it.
        for button in (fewer, more):
            image = button.grab().toImage()
            edge = image.pixelColor(0, image.height() // 2)
            assert edge.name().upper() == theme.LIGHT.border.upper(), (
                f"the {button.text()!r} button's edge is {edge.name()}, not the theme's border "
                f"{theme.LIGHT.border}. The sheet is not reaching it — most likely its selector "
                "still scopes these buttons to a QToolBar, which is where they used to live"
            )
        for button in (fewer, more):
            assert button.focusPolicy() is Qt.FocusPolicy.NoFocus, (
                "a step button takes focus, so one setting is three tab stops"
            )
    finally:
        qapp.setStyleSheet(was_sheet)
        qapp.setPalette(was_palette)


# --- T-197: the cookie source -----------------------------------------------------------------


def test_the_cookies_section_says_what_it_is_for_and_what_it_is_not(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**`REQ-EXCL-002`, where the user is standing** (`REQ-026`, `T-197`).

    This exists so someone reaches content they already have an account for. Saying so beside the
    control — rather than only in a requirements file — is what stops it reading as a way past a
    paywall. The other sentence is `DAT-003`'s ruled consequence: the file is late-bound, so a
    change reaches downloads already queued, and a screen that did not say so would be hiding a
    surprise.
    """
    screen, _ = screens()
    explanation = control(screen, QLabel, "cookiesExplanation")

    assert "does not unlock anything your account cannot already reach" in explanation.text()
    assert "already in the queue" in explanation.text(), (
        "the screen does not say the setting applies to queued downloads, which DAT-003 rules it "
        "does — a user changing it would be surprised by what happens next"
    )


def test_choosing_a_cookies_file_reports_it_and_shows_it(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    tmp_path: Path,
) -> None:
    jar = tmp_path / "cookies.txt"
    jar.write_text("", encoding="utf-8")
    chosen: list[Path | None] = []
    screen, _ = screens(on_cookie_file_chosen=chosen.append, choose_file=lambda _start: jar)

    control(screen, QPushButton, "chooseCookieFile").click()

    assert chosen == [jar]
    screen.show_cookie_file(jar)
    assert control(screen, QLabel, "cookieFileValue").text() == str(jar)


def test_using_no_cookies_is_offered_only_when_a_file_is_set(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    tmp_path: Path,
) -> None:
    """Clearing is a request the screen makes once there is something to clear."""
    none_set, _ = screens()
    assert control(none_set, QLabel, "cookieFileValue").text() == NO_COOKIES_NOTE
    assert not control(none_set, QPushButton, "clearCookieFile").isEnabled()

    chosen: list[Path | None] = []
    with_file, _ = screens(
        cookie_file=tmp_path / "cookies.txt", on_cookie_file_chosen=chosen.append
    )
    clear = control(with_file, QPushButton, "clearCookieFile")
    assert clear.isEnabled()
    clear.click()

    assert chosen == [None], f"clearing asked for {chosen}, not 'no cookies'"


def test_a_cancelled_cookies_picker_asks_for_nothing(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """Cancelled is not *use no cookies* — that is the other button, and this one signs you out."""
    chosen: list[Path | None] = []
    screen, _ = screens(on_cookie_file_chosen=chosen.append, choose_file=lambda _start: None)

    control(screen, QPushButton, "chooseCookieFile").click()

    assert chosen == [], "a cancelled picker signed the user out of everything they had"


def test_choosing_no_cookies_clears_a_browser_from_the_screen_too(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**`T197-R4`.** *No file* and *no cookies* are not the same statement.

    Telling the screen only the file half left a previously chosen browser on display after the
    user asked for neither — a screen saying the downloads are signed in when they are not.
    `show_cookie_source` carries both halves, so there is no way to tell it half of a change.
    """
    screen, _ = screens(cookie_browser="firefox")
    assert control(screen, QRadioButton, "cookieSourceBrowser").isChecked()

    screen.show_cookie_source(None, None)

    assert control(screen, QRadioButton, "cookieSourceNone").isChecked(), (
        "the screen still shows a cookie source after the user chose none"
    )
    assert not control(screen, QRadioButton, "cookieSourceBrowser").isChecked()


def test_a_cancelled_file_picker_leaves_the_source_where_it_was(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """Selecting *From a cookies file* moves the radio before the dialog opens (`T197-R4`).

    Dismissing the picker therefore left the screen claiming a source that was never set, while
    the setting underneath was still the browser. The radio is redrawn from what is in force.
    """
    asked: list[object] = []
    screen, _ = screens(
        cookie_browser="firefox",
        choose_file=lambda _start: None,
        on_cookie_file_chosen=asked.append,
    )

    control(screen, QRadioButton, "cookieSourceFile").click()

    assert asked == [], "a cancelled picker asked composition for something"
    assert control(screen, QRadioButton, "cookieSourceBrowser").isChecked(), (
        "the screen claims a cookies file after the picker was dismissed"
    )


# --- T-195: the preset a paste starts with, and how downloads are named ------------------------


def test_the_screen_offers_the_catalogue_and_starts_on_the_stored_default(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**`REQ-023`, `T-195`.** The default preset is what every paste inherits.

    Until now it could only be changed from the preset manager, which is a screen a user reaches
    to *edit presets* — not where they would look to change what a new download starts as.
    """
    screen, asked = screens(
        preset_names=("Best video available", "Audio only (MP3)"),
        default_preset="Audio only (MP3)",
    )

    choice = control(screen, QComboBox, DEFAULT_PRESET_NAME)
    assert [choice.itemData(i) for i in range(choice.count())] == [
        "Best video available",
        "Audio only (MP3)",
    ]
    assert choice.currentData() == "Audio only (MP3)", "the screen opened on something else"

    choice.setCurrentIndex(choice.findData("Best video available"))
    assert asked["default_preset"] == "Best video available"


def test_the_default_set_in_the_preset_manager_is_what_the_settings_screen_shows(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    qapp: QApplication,
) -> None:
    """**The one-writer criterion, crossed at the two surfaces** (`T-195`, `T195-R4`).

    Two controls writing one key is how `P3EXIT-R1`'s two records came to disagree, and the
    criterion names this crossing explicitly. Earlier versions of this test called
    `set_default_preset` themselves and asserted the store — which proves the store and says
    nothing about whether the two screens are wired to it.

    So: press *Set as default* in the **preset manager**, take the settings it saved, and open the
    **settings screen** on them. Both surfaces go through `settings.set_default_preset`; neither
    keeps a copy, and that is what makes this pass.
    """
    saved: list[core_settings.Settings] = []

    def capture(settings: core_settings.Settings) -> str | None:
        """Composition wires `core.settings.save` here; a test keeps what it was handed."""
        saved.append(settings)
        return None

    manager = PresetManager(core_settings.Settings(), save=capture, parent=None)
    try:
        chosen = preset_registry.AUDIO_MP3.name
        rows = manager.findChild(QListWidget, PRESET_LIST_NAME)
        assert rows is not None, "the manager has no preset list"
        for index in range(rows.count()):
            if rows.item(index).data(Qt.ItemDataRole.UserRole) == chosen:
                rows.setCurrentRow(index)
                break
        else:  # pragma: no cover - the catalogue always contains it
            raise AssertionError(f"{chosen} is not in the manager's list")

        button = manager.findChild(QPushButton, SET_DEFAULT_NAME)
        assert button is not None, "the manager offers no Set as default"
        button.click()
    finally:
        manager.close()

    assert saved, "the preset manager saved nothing"
    written = saved[-1]

    screen, _ = screens(
        preset_names=tuple(preset.name for preset in preset_registry.BUILT_IN_PRESETS),
        default_preset=core_settings.default_preset_of(written).name,
    )
    assert control(screen, QComboBox, DEFAULT_PRESET_NAME).currentData() == chosen, (
        "the settings screen opened on a different default than the preset manager just set, so "
        "the two surfaces keep separate records of one value"
    )


def test_the_default_set_on_the_settings_screen_is_what_the_preset_manager_marks(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    qapp: QApplication,
) -> None:
    """The same crossing in the other direction, which is the half a one-way test misses.

    A settings screen that wrote its own key would satisfy the forward direction — the manager's
    value would simply be ignored — and only reading the manager back catches it.
    """
    stored = core_settings.Settings()
    screen, asked = screens(
        preset_names=tuple(preset.name for preset in preset_registry.BUILT_IN_PRESETS),
        default_preset=core_settings.default_preset_of(stored).name,
    )
    choice = control(screen, QComboBox, DEFAULT_PRESET_NAME)
    chosen = preset_registry.AUDIO_MP3.name

    choice.setCurrentIndex(choice.findData(chosen))
    assert asked["default_preset"] == chosen, "the screen's control asked nothing of composition"

    # What composition does with that request, and what the manager then shows.
    manager = PresetManager(
        core_settings.set_default_preset(stored, asked["default_preset"]),
        save=lambda settings: None,
        parent=None,
    )
    try:
        rows = manager.findChild(QListWidget, PRESET_LIST_NAME)
        assert rows is not None
        # Asserted on each row's **name**, not its label: the label also carries a built-in mark,
        # and how it is composed is `T-111`'s subject rather than this test's. `P-7` guarantees
        # exactly one row is marked, so the list is compared whole.
        marked = [
            rows.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(rows.count())
            if DEFAULT_MARK in rows.item(index).text()
        ]
        assert marked == [chosen], (
            f"the preset manager marks {marked} as default after the settings screen chose {chosen}"
        )
    finally:
        manager.close()


def test_an_unusable_template_is_refused_at_edit_time_and_never_written(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**`P-23`'s rule, on this screen** (`T-195`).

    `T-112` made the same call for the per-row editor and recorded why: a screen that shows the
    error and stores the value anyway satisfies the visible half of the criterion and leaves a
    broken template behind for every future download.

    Refused through `core.output_template.unsupported_refusal` — the function
    `manager.preview_output_path` calls, so the editor and this screen cannot come to disagree
    about what a usable template is.
    """
    screen, asked = screens(
        output_template="",
        shipped_template=preset_registry.DEFAULT_OUTPUT_TEMPLATE,
    )
    field = control(screen, QLineEdit, OUTPUT_TEMPLATE_NAME)
    note = control(screen, QLabel, OUTPUT_TEMPLATE_NOTE_NAME)

    field.setText("%(nonsense)s.%(ext)s")

    assert "nonsense" in note.text(), f"no reason was shown: {note.text()!r}"
    assert "template" not in asked, "a refused template was written anyway"

    field.setText("%(uploader)s/%(title)s.%(ext)s")
    assert note.text() == "", "the reason outlived the problem"
    assert asked["template"] == "%(uploader)s/%(title)s.%(ext)s"


def test_the_shipped_template_is_the_placeholder_so_empty_reads_as_a_choice(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """Empty means *use the application default*, which an empty box alone does not say.

    Without the placeholder the field would look unset rather than deliberately deferred, and a
    user could not tell what their downloads would be named.
    """
    screen, _ = screens(
        output_template="",
        shipped_template=preset_registry.DEFAULT_OUTPUT_TEMPLATE,
    )

    field = control(screen, QLineEdit, OUTPUT_TEMPLATE_NAME)
    assert field.text() == ""
    assert field.placeholderText() == preset_registry.DEFAULT_OUTPUT_TEMPLATE


def test_a_screen_with_nothing_behind_a_control_says_so_rather_than_drawing_it_dead(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """`UX-005` §5 and `P-13`: a control that cannot act keeps its reason beside it."""
    screen, _ = screens(on_default_preset_chosen=None, on_output_template_chosen=None)

    assert not control(screen, QComboBox, DEFAULT_PRESET_NAME).isEnabled()
    assert control(screen, QLabel, "defaultPresetNote").text()
    assert not control(screen, QLineEdit, OUTPUT_TEMPLATE_NAME).isEnabled()


# --- network options (T-196) ----------------------------------------------------------------


def test_the_screen_offers_the_three_network_options_it_holds(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """The controls open showing what is in force, in the units a person reads them in.

    The rate limit is stored in bytes because that is what yt-dlp and the model take, and offered
    in KiB/s because that is what somebody means — so the conversion is asserted at the boundary
    where it happens rather than trusted.
    """
    screen, _ = screens(
        network=NetworkOptions(
            proxy="http://proxy.invalid:8080", rate_limit_bytes=512 * 1024, retries=4
        ),
        on_network_chosen=lambda _options: None,
    )

    assert control(screen, QLineEdit, PROXY_NAME).text() == "http://proxy.invalid:8080"
    assert control(screen, QSpinBox, RATE_LIMIT_NAME).value() == 512
    assert control(screen, QSpinBox, RETRIES_NAME).value() == 4


def test_an_unset_network_reads_as_no_limit_and_the_downloaders_own_retries(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**Neither absence is drawn as a bare zero**, which would be a different instruction.

    `0` on the retry box means *never retry inside the attempt*; the screen has to be able to say
    *nobody chose* as well, so the sentinel is below the range and reads as words. The rate limit
    can use zero for *no limit* because zero bytes per second is not a speed anyone means — and
    the words are on screen either way, so there is nothing to misread.
    """
    screen, _ = screens(on_network_chosen=lambda _options: None)

    rate = control(screen, QSpinBox, RATE_LIMIT_NAME)
    retries = control(screen, QSpinBox, RETRIES_NAME)

    assert rate.value() == 0
    assert rate.text() == NO_RATE_LIMIT_LABEL
    assert retries.value() == -1
    assert retries.text() == DEFAULT_RETRIES_LABEL
    assert control(screen, QLineEdit, PROXY_NAME).text() == ""


def type_a_proxy(screen: SettingsDialog, text: str) -> QLineEdit:
    """Type `text` into the proxy field the way a user does, and finish the edit (`T196-R1`).

    **`QTest.keyClicks`, not `setText`.** The finding is about what happens *between* keystrokes:
    every accepted prefix used to be written, so a test that assigned the whole string at once
    could never see it. `editingFinished` is then raised the way Return raises it — the screen
    commits there rather than on `textChanged`.
    """
    field: QLineEdit = control(screen, QLineEdit, PROXY_NAME)
    field.clear()
    QTest.keyClicks(field, text)
    return field


def test_typing_a_proxy_stores_it(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    chosen: list[NetworkOptions] = []
    screen, _ = screens(on_network_chosen=chosen.append)

    field = type_a_proxy(screen, "http://proxy.invalid:3128")
    QTest.keyClick(field, Qt.Key.Key_Return)

    assert chosen and chosen[-1].proxy == "http://proxy.invalid:3128"
    assert control(screen, QLabel, PROXY_NOTE_NAME).text() == ""


@pytest.mark.parametrize(
    ("typed", "label"),
    [
        ("http://alice:hunter2@proxy.invalid:8080", "a word for a password"),
        # **The one a grammar cannot catch** (`T196-R1`). `http://alice:12345` is a legal
        # `host:port`, so the prefix this passes through is indistinguishable from a valid proxy —
        # which is why the correction is *when* the field is committed, not what it accepts.
        ("http://alice:12345@proxy.invalid:8080", "a numeric password"),
    ],
)
def test_no_keystroke_of_a_credentialed_proxy_ever_reaches_the_writer(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    typed: str,
    label: str,
) -> None:
    """**`T196-R1`, Critical.** Typing a credentialed proxy must store nothing at any point.

    The screen wrote on `textChanged`, so typing `http://alice:hunter2@proxy.invalid:8080` handed
    composition `http://alice:hunter2` — a complete username and password — one keystroke before
    the `@` arrived and the value was refused. Composition applies and saves everything handed to
    it, so the credential reached `settings.toml` and would have reached the next queued request.

    Asserted over **every** value handed over, not the last one: the defect is an intermediate.
    """
    chosen: list[NetworkOptions] = []
    screen, _ = screens(on_network_chosen=chosen.append)

    field = type_a_proxy(screen, typed)
    QTest.keyClick(field, Qt.Key.Key_Return)
    screen.done(0)

    assert not [options for options in chosen if options.proxy is not None], (
        f"{label}: these values reached the writer while typing {typed!r}: "
        f"{[options.proxy for options in chosen]}"
    )
    assert control(screen, QLabel, PROXY_NOTE_NAME).text(), "it was refused without saying why"


def test_a_proxy_edit_left_unfinished_is_committed_when_the_screen_closes(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """The other half of `T196-R1`'s correction: not committing must not mean losing.

    `editingFinished` covers Return and focus leaving the field — clicking `Close` included, since
    the button takes focus first. `Esc`, and a window closed while the box still holds focus, do
    not raise it, and an edit silently discarded there is the same surprise as one silently
    stored.
    """
    chosen: list[NetworkOptions] = []
    screen, _ = screens(on_network_chosen=chosen.append)

    type_a_proxy(screen, "http://proxy.invalid:3128")
    assert chosen == [], "the value was committed while it was still being typed"

    screen.done(0)

    assert chosen and chosen[-1].proxy == "http://proxy.invalid:3128"


def test_a_proxy_carrying_a_credential_is_refused_with_the_reason_and_not_stored(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**`T-196`'s second criterion, at the screen.**

    Refused *before* the write, not beside it: this is the one setting on the screen that can
    carry a password, and storing it while showing an error would put the credential in
    `settings.toml` — the failure `T-112` and `T195-R2` both name one setting over, with more at
    stake here than a template that does not render.

    The refusal is `core.models.proxy_refusal`, so the screen cannot come to disagree with the
    model about what a usable proxy is (`T199-R3`).
    """
    chosen: list[NetworkOptions] = []
    screen, _ = screens(on_network_chosen=chosen.append)

    field = type_a_proxy(screen, "http://me:hunter2@proxy.invalid:8080")
    QTest.keyClick(field, Qt.Key.Key_Return)

    assert not [options for options in chosen if options.proxy is not None], (
        f"a proxy carrying a credential was handed to composition: {chosen}"
    )
    assert control(screen, QLabel, PROXY_NOTE_NAME).text(), "it was refused without saying why"


def test_emptying_the_proxy_box_clears_the_setting(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """An empty box is *no proxy* — a value, not a refusal, so no error is shown for it."""
    chosen: list[NetworkOptions] = []
    screen, _ = screens(
        network=NetworkOptions(proxy="http://proxy.invalid:8080"), on_network_chosen=chosen.append
    )

    field = type_a_proxy(screen, "")
    QTest.keyClick(field, Qt.Key.Key_Return)

    assert chosen and chosen[-1].proxy is None
    assert control(screen, QLabel, PROXY_NOTE_NAME).text() == ""


def test_a_speed_limit_is_stored_in_bytes_and_cleared_by_asking_for_none(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    chosen: list[NetworkOptions] = []
    screen, _ = screens(on_network_chosen=chosen.append)
    rate = control(screen, QSpinBox, RATE_LIMIT_NAME)

    rate.setValue(256)
    assert chosen[-1].rate_limit_bytes == 256 * RATE_LIMIT_STEP_BYTES

    rate.setValue(0)
    assert chosen[-1].rate_limit_bytes is None, "'No limit' was stored as a limit of zero"


def test_a_retry_count_of_zero_is_stored_and_the_sentinel_is_not(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """The pair that has to stay distinguishable, driven through the control (`T-196`)."""
    chosen: list[NetworkOptions] = []
    screen, _ = screens(on_network_chosen=chosen.append)
    retries = control(screen, QSpinBox, RETRIES_NAME)

    retries.setValue(0)
    assert chosen[-1].retries == 0, "'never retry' was stored as 'nobody chose'"

    retries.setValue(-1)
    assert chosen[-1].retries is None, "the sentinel was stored as a retry count"


def test_changing_one_network_control_keeps_what_the_others_hold(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**`T195-R1`'s defect, in the shape this screen could have reproduced.**

    Three controls edit one stored value, so each change has to be built from the value in force
    rather than from the one the screen opened with — otherwise setting a proxy and then a retry
    count writes the retry count against the original network options and silently drops the
    proxy. Asserted across two edits, because one cannot show it.
    """
    chosen: list[NetworkOptions] = []
    screen, _ = screens(
        network=NetworkOptions(rate_limit_bytes=1024), on_network_chosen=chosen.append
    )

    field = type_a_proxy(screen, "http://proxy.invalid:8080")
    QTest.keyClick(field, Qt.Key.Key_Return)
    control(screen, QSpinBox, RETRIES_NAME).setValue(2)

    assert chosen[-1] == NetworkOptions(
        proxy="http://proxy.invalid:8080", rate_limit_bytes=1024, retries=2
    )


def test_the_screen_follows_the_options_composition_settled_on(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """`show_concurrency`'s rule: what is displayed is what is in force, not what was emitted.

    `with_network_options` bounds what it is given, so the answer can differ from the request —
    and a screen showing a number that is not in force is a screen that will write it back.
    Shown without echoing, or every change would become a round trip.
    """
    chosen: list[NetworkOptions] = []
    screen, _ = screens(on_network_chosen=chosen.append)

    screen.show_network_options(NetworkOptions(proxy="http://proxy.invalid:9", retries=1))

    assert control(screen, QLineEdit, PROXY_NAME).text() == "http://proxy.invalid:9"
    assert control(screen, QSpinBox, RETRIES_NAME).value() == 1
    assert chosen == [], f"showing the value in force wrote it back: {chosen}"


def test_the_retry_control_says_which_retry_it_governs(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**The ruling's own obligation** (`T-196`, maintainer 2026-08-13).

    *"The label names the scope in the user's terms — retries within a download attempt."* A
    control reading only *Retries* would look like it governs the queue's own retry — which
    `REQ-015`/`REQ-018` already govern, and which `T-201`'s error text tells the user happens by
    itself. That is `T-075`: a control that looks like a choice and changes something else.

    Asserted on the visible label **and** the accessible name, because a screen-reader user gets
    only the second (`NFR-005`).
    """
    screen, _ = screens(on_network_chosen=lambda _options: None)

    visible = control(screen, QLabel, "networkRetriesLabel").text().lower()
    announced = control(screen, QSpinBox, RETRIES_NAME).accessibleName().lower()

    for reading, where in ((visible, "the label"), (announced, "the accessible name")):
        assert "retries" in reading, f"{where} does not say what the control is"
        assert "attempt" in reading, (
            f"{where} says only {reading!r}, which reads as the queue's own retry"
        )
        # **`T196-R5`: "within one attempt" separates two of the three retries, not all three.**
        # `--fragment-retries` is *also* within one attempt and is a different option this control
        # does not set, so a user setting this to zero would still watch fragments retry. The text
        # has to name what is being retried, not only when.
        assert "file transfer" in reading, (
            f"{where} says {reading!r}, which does not distinguish the file transfer's own "
            "retries from the separate count for the pieces of a segmented stream"
        )

    said = control(screen, QLabel, "networkExplanation").text().lower()
    assert "pieces" in said, (
        f"the section does not say that segmented streams retry on a count of their own: {said!r}"
    )


def test_the_network_section_says_when_its_settings_take_effect(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """These bind when a job is queued (`ARCHITECTURE.md` §8) — the opposite of the cookies file.

    A user who sets a speed limit with a full queue and sees nothing change has been told
    nothing; the cookies section states its own (late) binding for the same reason, and the two
    sections genuinely differ, so neither sentence can be dropped as boilerplate.
    """
    screen, _ = screens(on_network_chosen=lambda _options: None)

    said = control(screen, QLabel, "networkExplanation").text().lower()

    assert "already in the queue" in said, f"the binding is not stated: {said!r}"
    assert "each download" in said, "the limit's per-download scope is not stated"


@pytest.mark.parametrize(
    ("stored", "shown"),
    [
        (core_settings.RATE_LIMIT_MINIMUM_BYTES, 1),
        (1500, 1),
        (524288, 512),
    ],
)
def test_a_limit_in_force_is_never_displayed_as_no_limit(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]], stored: int, shown: int
) -> None:
    """**`T196-R3`.** Whatever the settings layer can hold, this control can show as a limit.

    The floor is what makes that true — `500` used to floor to `0` KiB/s and read *No limit* while
    downloads were capped at 500 B/s. `1500` is the residual that remains: it reads as 1 KiB/s,
    which understates the limit rather than denying it, and is not written back.
    """
    screen, _ = screens(
        network=NetworkOptions(rate_limit_bytes=stored), on_network_chosen=lambda _options: None
    )

    rate = control(screen, QSpinBox, RATE_LIMIT_NAME)

    assert rate.value() == shown
    assert rate.text() != NO_RATE_LIMIT_LABEL, (
        f"{stored} bytes per second is in force and the screen says {rate.text()!r}"
    )


def test_an_unrelated_edit_does_not_rewrite_a_rate_limit_the_box_rounds(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """The disclosed residual, bounded: displayed rounding must not become stored rounding.

    A stored `1500` reads as 1 KiB/s. Changing the retry count must hand back `1500`, not the
    `1024` the box happens to be showing — otherwise an unrelated control silently edits a limit
    the user set by hand.
    """
    chosen: list[NetworkOptions] = []
    screen, _ = screens(
        network=NetworkOptions(rate_limit_bytes=1500), on_network_chosen=chosen.append
    )

    control(screen, QSpinBox, RETRIES_NAME).setValue(3)

    assert chosen[-1] == NetworkOptions(rate_limit_bytes=1500, retries=3), (
        f"an unrelated edit rewrote the rate limit: {chosen[-1]}"
    )


def test_return_in_the_proxy_field_finishes_the_edit_and_opens_nothing(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**Found while building `T196-R1`'s evidence, and it made that correction incomplete.**

    A `QPushButton` in a dialog is `autoDefault`, so Return in any field activated the first one —
    *Choose folder…*, which opens a **native modal file picker** that no headless test can
    dismiss. The commit-on-finish correction relies on Return being a natural way to finish an
    edit, so a Return that opens a folder chooser instead is that correction with a hole in it.

    Asserted through the injected picker seam: if the button fired, `choose_directory` ran.
    """
    picked: list[Path] = []
    chosen: list[NetworkOptions] = []

    def refuse_to_pick(start: Path) -> Path | None:
        """Record that the picker was reached, and answer as a cancelled one does.

        A named function rather than a lambda: recording *and* returning needs two statements,
        and `append(...) or None` is an expression `mypy` reads as always-false.
        """
        picked.append(start)
        return None

    screen, _ = screens(choose_directory=refuse_to_pick, on_network_chosen=chosen.append)
    # **Shown, because `autoDefault` is only consulted by a dialog that is up.** A screen built and
    # never shown swallows Return, so this test passed with the correction removed until it did
    # this — the vacuity the injected picker exists to make visible rather than hide.
    screen.show()
    QApplication.processEvents()

    field = type_a_proxy(screen, "http://proxy.invalid:3128")
    QTest.keyClick(field, Qt.Key.Key_Return)

    assert picked == [], "Return in the proxy field opened the folder picker"
    assert chosen and chosen[-1].proxy == "http://proxy.invalid:3128"


# --- the screen fits the screen (T-242) ------------------------------------------------------


def wrapped_labels(screen: SettingsDialog) -> list[QLabel]:
    """Every label on the screen with words in it."""
    return [label for label in screen.findChildren(QLabel) if label.text().strip()]


def short_by(label: QLabel) -> int:
    """How many pixels this label is drawn shorter than the text in it needs, or 0."""
    needs = label.heightForWidth(label.width()) if label.wordWrap() else label.sizeHint().height()
    return max(0, needs - label.height())


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (1366, 700),  # the smallest laptop working area this project has claimed anywhere
        (1024, 620),  # smaller still, to prove the scroll area rather than the slack
        (1180, 900),
    ],
)
def test_no_label_is_drawn_shorter_than_the_words_in_it(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]], width: int, height: int
) -> None:
    """**`T-242`.** The screen asked for 1407 pixels of height and the display has about a thousand.

    What gave way was the wrapped explanatory text — measured before the fix, at the dialog's own
    `sizeHint`: `cookiesExplanation` got **23** pixels of the **51** it needs, `networkExplanation`
    **38** of **85**. So the sentence saying a cookies file *"does not unlock anything your account
    cannot already reach"* was cut in half, and so was the one naming which retry the retry control
    governs — the sentence a whole review round was spent getting right (`T196-R5`).

    **Asserted by measurement, not by eye**: `heightForWidth` against the height each label was
    actually given, at three window sizes. A picture cannot fail a build.
    """
    screen, _ = screens(on_network_chosen=lambda _options: None)
    screen.resize(width, height)
    screen.show()
    QApplication.processEvents()

    clipped = {
        label.objectName() or label.text()[:40]: (label.height(), short_by(label))
        for label in wrapped_labels(screen)
        if short_by(label)
    }

    assert not clipped, (
        f"at {width}x{height} these labels are drawn shorter than their text needs "
        f"(height, short by): {clipped}"
    )


def test_the_sections_scroll_and_the_way_out_does_not(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**The button box is outside the scroll area** (`T-242`), so `Close` is never scrolled off.

    The other half of the same choice: a screen that scrolls its own exit is one a user can lose
    their way out of, and this screen applies every change as it is made — so leaving is the one
    action it must never hide.
    """
    screen, _ = screens(on_network_chosen=lambda _options: None)
    screen.resize(700, 420)  # deliberately far shorter than the sections need
    screen.show()
    QApplication.processEvents()

    scroll = control(screen, QScrollArea, SETTINGS_SCROLL_NAME)
    buttons = control(screen, QDialogButtonBox, "settingsButtons")

    assert scroll.verticalScrollBar().maximum() > 0, (
        "the sections do not scroll at a height far shorter than they need, so either the scroll "
        "area is not doing its job or this test is no longer squeezing anything"
    )
    assert not scroll.isAncestorOf(buttons), (
        "the way out of the screen is inside the scrolling part"
    )
    assert buttons.visibleRegion().boundingRect().height() > 0, "Close is not on screen"

    # **And it scrolls one way only.** A scroll area that keeps its contents at their hint width
    # buys the vertical room back by scrolling sideways — which is this task's clipping moved
    # rather than fixed, because a wrapped label's height is a function of the width it is given.
    # Asserted at a width narrower than the sections ask for, which is where the two differ.
    screen.resize(480, 420)
    QApplication.processEvents()
    sections = control(screen, QWidget, "settingsSections")
    assert sections.width() <= scroll.viewport().width(), (
        f"the sections are {sections.width()}px wide in a {scroll.viewport().width()}px viewport, "
        "so the screen scrolls sideways rather than wrapping"
    )


def test_a_control_below_the_fold_is_scrolled_to_when_it_takes_focus(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**The keyboard route through a scrolling screen, stated because `T-200` inherits it.**

    A scroll area that did not follow focus would leave a keyboard user editing a control they
    cannot see — which is `NFR-005`'s promise broken by the fix for `T-242` rather than by the
    defect it replaced. Asserted on the last control on the screen, which is the one furthest
    below the fold.
    """
    screen, _ = screens(on_network_chosen=lambda _options: None)
    screen.resize(700, 420)
    screen.show()
    QApplication.processEvents()

    scroll = control(screen, QScrollArea, SETTINGS_SCROLL_NAME)
    revert = control(screen, QPushButton, YTDLP_REVERT_NAME)
    assert revert.visibleRegion().boundingRect().height() == 0, (
        "the last control is already on screen at this size, so this test proves nothing"
    )
    assert scroll.verticalScrollBar().value() == 0, "sanity: the screen has not scrolled yet"

    # **Tabbed, not `setFocus`.** The gesture is the assertion here: `setFocus` alone does not
    # scroll, which is how the defect was found — Qt scrolls when the *scroll area* resolves the
    # focus move, and in a dialog the dialog owns the tab chain.
    off_screen = []
    for _ in range(60):
        QTest.keyClick(screen, Qt.Key.Key_Tab)
        QApplication.processEvents()
        # `focusWidget()` is typed as always answering, so the `is not None` guard mypy would
        # otherwise call redundant is left out rather than written and suppressed.
        focused = screen.focusWidget()
        if focused.visibleRegion().boundingRect().height() == 0:
            off_screen.append(focused.objectName() or type(focused).__name__)
        if focused is revert:
            break

    assert not off_screen, (
        f"{len(off_screen)} controls took keyboard focus while off screen — a keyboard user would "
        f"be editing something they cannot see: {sorted(set(off_screen))[:6]}"
    )
    assert scroll.verticalScrollBar().value() > 0, "the view never followed the keyboard at all"


def test_the_screen_opens_no_taller_than_the_display(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """It opens at the height its **contents** want, bounded by the room there is (`T-242`).

    Both halves matter and neither is the dialog's own `sizeHint`: a scroll area asks for very
    little — **463** pixels, measured — so sizing to the hint would open a screen that scrolls
    from the first section, and sizing to the contents alone would open one taller than the
    display, which is what this task was filed about.
    """
    screen, _ = screens(on_network_chosen=lambda _options: None)
    room = QApplication.primaryScreen().availableGeometry().size()

    assert screen.height() <= room.height(), (
        f"the screen opens {screen.height()}px tall on a {room.height()}px display"
    )
    sections = control(screen, QWidget, "settingsSections")
    assert screen.height() > sections.sizeHint().height() // 2, (
        f"it opens at {screen.height()}px against sections wanting "
        f"{sections.sizeHint().height()}px — that is the scroll area's own hint, not the content's"
    )


class _Display:
    """A stand-in for one physical display, with the working area it offers.

    **A stub rather than a second monitor**, because the offscreen platform has exactly one screen
    and this project does not have a two-monitor runner. What is under test is the *choice* — which
    display's room the dialog reads — and that choice is deterministic and worth pinning even
    though the multi-monitor rendering behind it is not verified anywhere (`T242-R1`).
    """

    def __init__(self, width: int, height: int) -> None:
        self._room = QRect(0, 0, width, height)

    def availableGeometry(self) -> QRect:  # noqa: N802 — Qt's own spelling, matched deliberately
        return self._room


def test_the_dialog_is_bounded_by_the_display_it_is_on_not_the_primary_one(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**`T242-R1`.** The dialog is parented to the main window and follows it between displays.

    This asked `QApplication.primaryScreen()` while its own call site claimed *"the screen it is
    on"*. On a two-monitor desk those differ: a main window on a 768-high secondary display would
    open Settings against the 1080-high primary's room — **recreating the off-screen dialog this
    task exists to remove, at exactly the working area the acceptance criterion names.**

    The smaller room is given to the *associated* display deliberately, so a fallback to the
    primary cannot pass this by accident.
    """
    screen, _ = screens(on_network_chosen=lambda _options: None)
    # Dimensions the *primary* display cannot produce, so a fallback cannot satisfy this by
    # accident — which is exactly how the first version of this assertion passed against the
    # mutation it was written to catch: it asked only that the room be *small enough*, and the
    # offscreen primary is smaller still.
    associated = _Display(1366, 700)

    screen.screen = lambda: associated  # type: ignore[method-assign, assignment, return-value]
    room = screen._room_on_screen()

    primary = QApplication.primaryScreen().availableGeometry()
    assert (room.width(), room.height()) == (1366 - 48, 700 - 48), (
        f"the dialog sized itself {room.width()}x{room.height()} against an associated display of "
        f"1366x700 — it is reading the primary display, which offers "
        f"{primary.width()}x{primary.height()}"
    )


def test_the_primary_display_is_the_fallback_when_there_is_no_associated_one(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """A widget never shown has no associated screen, which is every offscreen construction.

    So the fallback is not a headless curiosity — it is the path most of this suite takes, and a
    correction that removed it would leave the dialog sizing itself against nothing.
    """
    screen, _ = screens(on_network_chosen=lambda _options: None)

    screen.screen = lambda: None  # type: ignore[method-assign, assignment, return-value]
    room = screen._room_on_screen()

    primary = QApplication.primaryScreen().availableGeometry().size()
    assert room.height() == primary.height() - 48, (
        f"with no associated display the dialog sized itself to {room.height()}px against a "
        f"{primary.height()}px primary"
    )


def test_a_newer_ytdlp_reads_as_recovery_rather_than_a_setting(
    qapp: QApplication,
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**`T-290`**, building `OPS-002`'s 2026-08-27 amendment.

    *"Update to the latest version"* sat as a peer of *"Use the bundled version"* in a section that
    reads like every other setting — a presentation that invites a population onto versions this
    project has never tested. The mechanism was never what was ruled on; the weight was.

    **Four things, and the last two are what keep the fix honest.**

    - The section says **when**, not only what.
    - The control is quieter than the one beside it — `quietAction`, which `theme.py` renders
      **without a fill and with its text colour unchanged**. *(A first version also muted the text;
      the colour guard refused it, because a pressable control in the disabled colour looks
      unavailable while responding. `T290-R3` is this docstring catching up with that.)*
    - **And "quieter" is measured on pixels, not on a property** (`T290-R2`). The first version
      asserted the property was set and the selector existed, which a sheet restoring the fill
      would pass: two equal buttons with a flag on one. So both buttons are rendered under each
      palette and their fills compared — the demotion has to be *visible*, or it is not one.
    - **It is still a button and still reachable** — `OPS-002` requires the version visible and
      revert one action, and `error_text` sends users here from a failed download, so hiding it
      would dead-end that advice.
    - **The two surfaces agree.** The note and the failure's next step describe the same move;
      `T-243`'s one-voice rule applies across screens as well as within a row.
    """
    # **Both routes wired and both buttons enabled**, or the rendering below compares two
    # disabled controls — the fixture supplies no yt-dlp callbacks by default, and the screen
    # disables a button whose route is `None`. A user-managed resolution is what enables revert.
    dialog, _asked = screens(on_ytdlp_update=lambda: None, on_ytdlp_revert=lambda: None)
    dialog.show_ytdlp("2026.9.1", "user-managed copy (OPS-002)", is_user_managed=True)
    update = dialog.findChild(QPushButton, YTDLP_UPDATE_NAME)
    revert = dialog.findChild(QPushButton, YTDLP_REVERT_NAME)
    note = dialog.findChild(QLabel, YTDLP_RECOVERY_NOTE_NAME)
    assert update is not None and revert is not None
    assert note is not None, "the section does not say when a newer yt-dlp is the right move"

    assert note.text() == YTDLP_RECOVERY_NOTE
    assert "stopped working" in note.text(), "the note does not name the occasion"
    assert update.property("quietAction") is True, (
        "the newer-copy control is still a peer of Use the bundled version"
    )
    # **And the property reaches the sheet.** A dynamic property nothing styles is a no-op that
    # this test would otherwise call a de-emphasis. Asserted in both palettes, per `T130-R1`.
    for palette in ui_theme.THEMES.values():
        assert 'QPushButton[quietAction="true"]' in ui_theme.stylesheet(palette), (
            f"the {palette.name} sheet styles nothing for quietAction, so setting it changes "
            "nothing on screen"
        )
    assert revert.property("quietAction") in (None, False), (
        "reverting was demoted too, so nothing was actually de-emphasised relative to it"
    )
    # **Still a control, not prose.** The failure message points a user at this screen; a note
    # where the button was would leave that advice with nothing to act on. That it *acts* is
    # `test_pressing_update_asks_composition_to_do_it`'s claim, not a tautology's (`T290-R2`).
    assert update.text() == YTDLP_UPDATE_LABEL
    assert update.accessibleName(), "the control lost the name a screen reader announces"

    # **Rendered, under each palette** (`T290-R2`). A centre pixel of each button is its fill:
    # revert keeps the theme's `surface`, and the demoted control must not — the two fills have to
    # differ, or the property is decoration. Read from the theme rather than written down, for
    # `T-141`'s reason: pinning a colour pins a styling choice.
    was_sheet, was_palette = qapp.styleSheet(), qapp.palette()
    try:
        for palette in ui_theme.THEMES.values():
            theme.apply(qapp, palette)
            dialog.show()
            qapp.processEvents()

            def fill_of(button: QPushButton) -> QColor:
                # **Inside the padding, not at the centre.** The centre of a button is where its
                # label is drawn, so sampling it reads a glyph's antialiased edge — measured as
                # `#B9906A` on a button whose fill was plain white. The sheet gives every button a
                # 1 px border and 4 px of padding, so x = 5 on the middle row is fill and only fill.
                image = button.grab().toImage()
                return image.pixelColor(5, image.height() // 2)

            quiet, filled = fill_of(update), fill_of(revert)
            assert filled.name().upper() == palette.surface.upper(), (
                f"[{palette.name}] the revert button's fill is {filled.name()}, not the theme's "
                f"surface {palette.surface}; the sheet is not reaching this screen at all"
            )
            assert quiet.name().upper() != filled.name().upper(), (
                f"[{palette.name}] both buttons are filled {filled.name()}: the demotion is a "
                "property with nothing behind it"
            )
    finally:
        qapp.setStyleSheet(was_sheet)
        qapp.setPalette(was_palette)
