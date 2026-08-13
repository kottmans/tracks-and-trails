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
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QToolButton,
)

from tracks_and_trails.core import presets as preset_registry
from tracks_and_trails.core import settings as core_settings
from tracks_and_trails.core.models import NetworkOptions
from tracks_and_trails.ui import theme
from tracks_and_trails.ui.preset_manager import (
    DEFAULT_MARK,
    PRESET_LIST_NAME,
    SET_DEFAULT_NAME,
    PresetManager,
)
from tracks_and_trails.ui.settings_dialog import (
    DEFAULT_DIRECTORY_NOTE,
    DEFAULT_PRESET_NAME,
    DEFAULT_RETRIES_LABEL,
    NO_COOKIES_NOTE,
    NO_RATE_LIMIT_LABEL,
    OUTPUT_TEMPLATE_NAME,
    OUTPUT_TEMPLATE_NOTE_NAME,
    PROXY_NAME,
    PROXY_NOTE_NAME,
    RATE_LIMIT_NAME,
    RATE_LIMIT_STEP_BYTES,
    RETRIES_NAME,
    SETTINGS_STILL_TO_COME,
    STEP_DOWN_LABEL,
    STEP_UP_LABEL,
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


def test_typing_a_proxy_stores_it(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    chosen: list[NetworkOptions] = []
    screen, _ = screens(on_network_chosen=chosen.append)

    control(screen, QLineEdit, PROXY_NAME).setText("http://proxy.invalid:3128")

    assert chosen and chosen[-1].proxy == "http://proxy.invalid:3128"
    assert control(screen, QLabel, PROXY_NOTE_NAME).text() == ""


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

    control(screen, QLineEdit, PROXY_NAME).setText("http://me:hunter2@proxy.invalid:8080")

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

    control(screen, QLineEdit, PROXY_NAME).setText("")

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

    control(screen, QLineEdit, PROXY_NAME).setText("http://proxy.invalid:8080")
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
