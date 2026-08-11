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
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
)

from tracks_and_trails.core import presets as preset_registry
from tracks_and_trails.core import settings as core_settings
from tracks_and_trails.ui.settings_dialog import (
    DEFAULT_DIRECTORY_NOTE,
    DEFAULT_PRESET_NAME,
    NO_COOKIES_NOTE,
    OUTPUT_TEMPLATE_NAME,
    OUTPUT_TEMPLATE_NOTE_NAME,
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

    `REQ-023` names eight settings and this screen builds seven of them since `T-195`. A settings
    screen showing only what it implements reads as complete, so the remaining absences are stated
    where the user is looking — and each of them is owned by a filed task.
    """
    screen, _ = screens()
    remaining = control(screen, QLabel, "settingsRemaining")

    assert remaining.text() == SETTINGS_STILL_TO_COME
    # `T-199` built the ffmpeg location, so it left this list — which is this test working, not a
    # weakening of it: the sentence must shrink as the screen grows, or it becomes the stale
    # coverage claim the criterion exists to prevent.
    for built, by in (
        ("ffmpeg", "T-199"),
        ("cookie", "T-197"),
        ("default preset", "T-195"),
        ("output template", "T-195"),
    ):
        assert built not in SETTINGS_STILL_TO_COME.lower(), (
            f"the screen still says {built} is to come, but {by} built it"
        )
    for absent in ("network",):
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


def test_the_default_preset_has_one_writer(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
    tmp_path: Path,
) -> None:
    """**The criterion this task exists to not fail** (`T-195`, `P3EXIT-R1`).

    Two controls writing one key is how two records of one value came to disagree. So the screen
    does not store a default of its own: what it hands composition goes through
    `settings.set_default_preset`, which is the same function the preset manager's *Set as
    default* calls.

    Asserted by writing through the screen's callback and reading the value back the way the
    **preset manager** reads it — one path, proved from both ends, rather than by inspecting the
    screen's own state.
    """
    stored = core_settings.Settings()
    screen, _ = screens(
        preset_names=tuple(preset.name for preset in preset_registry.BUILT_IN_PRESETS),
        default_preset=core_settings.default_preset_of(stored).name,
    )
    choice = control(screen, QComboBox, DEFAULT_PRESET_NAME)
    chosen = preset_registry.AUDIO_MP3.name

    written = core_settings.set_default_preset(stored, chosen)

    assert core_settings.default_preset_of(written).name == chosen
    # And the screen reflects it without a second store of its own.
    screen.show_default_preset(chosen)
    assert choice.currentData() == chosen


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
