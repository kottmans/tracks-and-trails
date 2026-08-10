"""The Settings screen (`REQ-023`, `T-146`).

Driven through the screen's own controls by object name, never by calling the handler behind
them: what `T-146` promises is that a *user* can change where downloads go and what the window
looks like, and a test that called `_remember` would prove the method exists.

The directory picker is injected (`SettingsDialog.choose_directory`) because a native modal
cannot be driven headlessly — the same seam, and the same reasoning, as the manager's
`entry_point`. What that gives up is `QFileDialog` itself, which is Qt's; what it keeps is every
line of this application's own behaviour on both answers, chosen and cancelled.
"""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QRadioButton, QSpinBox

from tracks_and_trails.core import settings as core_settings
from tracks_and_trails.ui.settings_dialog import (
    DEFAULT_DIRECTORY_NOTE,
    SETTINGS_STILL_TO_COME,
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

    `REQ-023` names eight settings and this screen builds five of them since `T-197`. A settings
    screen showing only what it implements reads as complete, so the remaining absences are stated
    where the user is looking — and each of them is owned by a filed task.
    """
    screen, _ = screens()
    remaining = control(screen, QLabel, "settingsRemaining")

    assert remaining.text() == SETTINGS_STILL_TO_COME
    # `T-199` built the ffmpeg location, so it left this list — which is this test working, not a
    # weakening of it: the sentence must shrink as the screen grows, or it becomes the stale
    # coverage claim the criterion exists to prevent.
    for built, by in (("ffmpeg", "T-199"), ("cookie", "T-197")):
        assert built not in SETTINGS_STILL_TO_COME.lower(), (
            f"the screen still says {built} is to come, but {by} built it"
        )
    for absent in ("default preset", "output template", "network"):
        assert absent in SETTINGS_STILL_TO_COME.lower(), (
            f"{absent!r} is not built and the screen does not say so: {SETTINGS_STILL_TO_COME!r}"
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
    assert control(screen, QLabel, "downloadDirectoryValue").text() == str(chosen_folder)
    assert control(screen, QLabel, "downloadDirectoryNote").text() == "", (
        "a chosen folder is still described as the default one"
    )


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
    assert control(screen, QLabel, "downloadDirectoryValue").text() == str(started)


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
    assert control(default_screen, QLabel, "downloadDirectoryNote").text() == DEFAULT_DIRECTORY_NOTE

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

    assert control(screen, QLabel, "downloadDirectoryValue").text() == str(platform_folder)
    assert control(screen, QLabel, "downloadDirectoryNote").text() == DEFAULT_DIRECTORY_NOTE
    assert not control(screen, QPushButton, "useDefaultDownloadDirectory").isEnabled()


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


def test_the_concurrency_control_mirrors_the_toolbars_without_echoing_it(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**Two controls, one value** (`REQ-013`, `T-146`'s recorded choice).

    The screen's spinner and the toolbar's edit the same setting, so each has to be able to show
    what the other did — and showing must not report. A `setValue` that emitted `valueChanged`
    would call composition, which would call back here, which is a loop rather than a sync.
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
        f"following the toolbar reported back to composition: {reported}. Two controls that echo "
        "each other turn one user change into a round trip"
    )
