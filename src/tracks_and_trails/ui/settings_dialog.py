"""The Settings screen (`REQ-023`, built by `T-146`).

**Seven of `REQ-023`'s eight settings, and the screen says which.** The requirement names default
download directory, default preset, concurrency limit, output template, ffmpeg location, network
options, cookie source and theme. This screen holds all but **network options**, which is `T-196`'s
— the download directory, theme and concurrency limit from `T-146`, the ffmpeg location from
`T-199`, the cookie source from `T-197`, and the default preset and output template from `T-195`.
`SETTINGS_STILL_TO_COME` is shown on the screen itself so it never claims coverage it does not
have — `T-146`'s own criterion, and the failure mode a settings screen has by default.

*(A module of this name existed until 2026-08-06 holding one control, `Clear download records`. It
went with `REQ-020`. Nothing of it survives here but the shape of the menu route, which was worth
reading before writing this: `T169-R4` recorded that the shell was gone so a later implementer
would not go looking for it.)*

## Changes apply as they are made, and the button says `Close`

Every control here applies and saves as it is changed — the idiom `T-078` established for the
concurrency limit, and the one this screen inherited when `UX-013` made it that limit's only home
(`T-234`). An `OK`/`Cancel` pair would be the other honest shape, and it is the wrong one here:
several of these settings are already visible elsewhere — the theme in every pixel, the default
preset in the preset manager and on the next row a user pastes — so a change that waited for `OK`
would have to either not preview (and make the theme unpickable without guessing) or preview and
then be revertible, which is a transaction this screen has no way to roll back.

*(This paragraph named the toolbar's concurrency spinner twice: as the idiom's origin and as an
example of a setting visible elsewhere. `UX-013` removed that spinner. The idiom's origin is still
`T-078` — the behaviour outlived the widget that first had it — and the concurrency limit is no
longer an example of the second thing, because this screen is where it is seen.)*

## The directory picker is injected

`choose_directory` defaults to `QFileDialog.getExistingDirectory` and is a parameter because a
native modal cannot be driven headlessly (`ai/TESTING.md`), and a screen whose one route to its
main setting is untestable is a screen whose main setting is untested. The same seam, and the same
reasoning, as the manager's `entry_point`.
"""

from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core.models import BROWSER_NAMES
from tracks_and_trails.core.output_template import unsupported_refusal
from tracks_and_trails.core.settings import (
    CONCURRENCY_MAXIMUM,
    CONCURRENCY_MINIMUM,
    THEME_NAMES,
)

__all__ = [
    "COOKIES_EXPLANATION",
    "DEFAULT_DIRECTORY_NOTE",
    "FFMPEG_ON_PATH_NOTE",
    "NO_COOKIES_NOTE",
    "SETTINGS_STILL_TO_COME",
    "STEP_BUTTON_PROPERTY",
    "STEP_DOWN_LABEL",
    "STEP_UP_LABEL",
    "THEME_LABELS",
    "YTDLP_NOTE_NAME",
    "YTDLP_REVERT_LABEL",
    "YTDLP_REVERT_NAME",
    "YTDLP_UPDATE_NAME",
    "YTDLP_VERSION_NAME",
    "YTDLP_VERSION_UNKNOWN",
    "YTDLP_WORKING_LABEL",
    "SettingsDialog",
]

#: What each theme is called on screen. The stored names are lower-case identifiers; these are the
#: words a user reads, and keeping them apart is what lets the file stay stable if the wording
#: changes.
THEME_LABELS: Final = {"light": "Light", "dark": "Dark"}

#: Object names, so tests and composition reach a control without walking the layout (`T-195`).
DEFAULT_PRESET_NAME: Final = "settingsDefaultPreset"
OUTPUT_TEMPLATE_NAME: Final = "settingsOutputTemplate"
OUTPUT_TEMPLATE_NOTE_NAME: Final = "settingsOutputTemplateNote"

#: Shown under the folder when no folder has been chosen. **It names the actual path**, because
#: "the default" is not an answer to *where did my file go*.
DEFAULT_DIRECTORY_NOTE: Final = "Your usual downloads folder"

#: What the cookies section says it is for, and what it is not for.
#:
#: **`REQ-EXCL-002` is quoted in spirit because a user should read it here.** This exists so
#: someone reaches content they already have an account for; it is not a way past a paywall, and
#: the sentence says so where the control is rather than only in a requirements file.
COOKIES_EXPLANATION: Final = (
    "Use cookies from a file to download things you are signed in to. This does not unlock "
    "anything your account cannot already reach.\n"
    "A cookies file applies to downloads already in the queue as well as new ones."
)

#: Shown where the path would be when none is set.
NO_COOKIES_NOTE: Final = "No cookies file - downloads are not signed in"

#: Shown where the path would be when none is set. Names the mechanism, because *"not set"* does
#: not tell a user what the application is doing instead.
FFMPEG_ON_PATH_NOTE: Final = "Looked for on PATH"

#: What the concurrency control's step buttons read (`UX-005` row 11, `T-141`, `T-236`).
#:
#: A true minus sign rather than a hyphen: at this size a hyphen reads as a dash in a sentence,
#: and the pair has to look like a pair.
#:
#: **These lived in `main_window.py` until `T-234`**, which deleted them with the toolbar's
#: spinner. `UX-005` row 11 rules on *the concurrency control*, not on the toolbar, so they come
#: back with the control rather than staying where the control used to be.
STEP_DOWN_LABEL: Final = "\u2212"
STEP_UP_LABEL: Final = "+"

#: The dynamic property the sheet styles the step buttons against (`T-141`).
#:
#: **A role, not a name.** `theme.py` styles by class so a widget nobody remembered still gets
#: themed, and an object-name selector fails silently when it stops matching — the button just goes
#: back to looking like text.
STEP_BUTTON_PROPERTY: Final = "stepButton"

#: Object names for the yt-dlp section, so tests and composition reach a control without walking
#: the layout (`T-198`).
YTDLP_VERSION_NAME: Final = "ytdlpVersion"
YTDLP_NOTE_NAME: Final = "ytdlpNote"
YTDLP_UPDATE_NAME: Final = "ytdlpUpdate"
YTDLP_REVERT_NAME: Final = "ytdlpRevert"

#: Shown before a child has answered. **Not a version and not a guess** (`REQ-025`): the number
#: comes from a worker's import, which takes a moment, and inventing a placeholder that looks like
#: a version is how a screen ends up reporting one nobody read.
YTDLP_VERSION_UNKNOWN: Final = "Checking…"

#: What the revert button says. Names the destination rather than the gesture: *Revert* asks the
#: user to remember what they reverted to, and the bundled baseline is the thing they get.
YTDLP_REVERT_LABEL: Final = "Use the bundled version"

#: What the update button says while an operation is running, so the screen's own state says why
#: nothing is responding rather than leaving a dead-looking button (`NFR-006`'s spirit).
YTDLP_WORKING_LABEL: Final = "Working…"

#: The screen's own statement of what it does not yet cover (`T-146`).
#:
#: **`REQ-023` names eight settings and this screen has seven.** A settings screen that shows only
#: what it implements reads as complete, and the one absence is owned by a filed task (`T-196`) —
#: so the honest thing is to say so where the user is looking rather than only in a document they
#: will not read.
SETTINGS_STILL_TO_COME: Final = "Still to come: network options."


class SettingsDialog(QDialog):
    """One screen for the settings `REQ-023` names and this phase has built."""

    def __init__(
        self,
        *,
        download_directory: Path,
        directory_is_default: bool,
        theme: str,
        concurrency: int,
        on_directory_chosen: Callable[[Path | None], None],
        on_theme_chosen: Callable[[str], None],
        on_concurrency_chosen: Callable[[int], None],
        choose_directory: Callable[[Path], Path | None] | None = None,
        cookie_file: Path | None = None,
        cookie_browser: str | None = None,
        on_cookie_file_chosen: Callable[[Path | None], None] | None = None,
        on_cookie_browser_chosen: Callable[[str | None], None] | None = None,
        ffmpeg_location: Path | None = None,
        ffmpeg_summary: str = "",
        on_ffmpeg_location_chosen: Callable[[Path | None], None] | None = None,
        choose_file: Callable[[Path | None], Path | None] | None = None,
        preset_names: Sequence[str] = (),
        default_preset: str = "",
        output_template: str = "",
        shipped_template: str = "",
        on_default_preset_chosen: Callable[[str], None] | None = None,
        on_output_template_chosen: Callable[[str], None] | None = None,
        refuse_template: Callable[[str], str | None] | None = None,
        on_ytdlp_update: Callable[[], None] | None = None,
        on_ytdlp_revert: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_directory_chosen = on_directory_chosen
        self._on_theme_chosen = on_theme_chosen
        self._on_concurrency_chosen = on_concurrency_chosen
        self._choose_directory = choose_directory or self._ask_for_a_directory
        self._directory = download_directory
        self._directory_is_default = directory_is_default
        # Held before the sections are built, because each one reads its own starting value.
        self._theme = theme
        self._initial_concurrency = concurrency
        self._cookie_file = cookie_file
        self._cookie_browser = cookie_browser
        self._on_cookie_file_chosen = on_cookie_file_chosen
        self._on_cookie_browser_chosen = on_cookie_browser_chosen
        self._ffmpeg_location = ffmpeg_location
        self._ffmpeg_summary = ffmpeg_summary
        self._on_ffmpeg_location_chosen = on_ffmpeg_location_chosen
        self._choose_file = choose_file or self._ask_for_a_file
        self._preset_names = tuple(preset_names)
        self._default_preset = default_preset
        self._output_template = output_template
        #: What an empty template resolves to, shown as the field's placeholder so *empty* reads as
        #: a choice with a visible consequence rather than as a blank (`T-195`).
        self._shipped_template = shipped_template
        self._on_default_preset_chosen = on_default_preset_chosen
        #: Why a template cannot be used, or `None` (`T195-R2`).
        #:
        #: **Injected, because the authoritative answer lives behind the manager.** The first build
        #: called `unsupported_refusal` here, which checks *field names only* — so `%(title`, whose
        #: syntax yt-dlp itself rejects, and `../%(title)s.%(ext)s`, which escapes the download
        #: folder, were both accepted and stored. `DownloadManager.preview_output_path` is the
        #: check the per-row editor makes: yt-dlp's own syntax parser, the field names, a real
        #: render, and containment. `ui/` may not reach `ytdlp_adapter` (`ARCHITECTURE.md` §6), so
        #: composition hands the route in rather than this screen learning the syntax.
        #:
        #: `None` falls back to the field-name check, which is what a screen built without a
        #: manager can honestly do — and is why `refuse_template` is what composition always
        #: passes.
        self._refuse_template = refuse_template
        self._on_output_template_chosen = on_output_template_chosen
        self._on_ytdlp_update = on_ytdlp_update
        self._on_ytdlp_revert = on_ytdlp_revert
        #: Whether the yt-dlp in use came from the user's own copy, so reverting means something.
        #: Held here rather than read back off the button — see `show_ytdlp`.
        self._ytdlp_is_user_managed = False

        self.setObjectName("settingsDialog")
        self.setWindowTitle("Settings")

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_downloads_section())
        layout.addWidget(self._build_naming_section())
        layout.addWidget(self._build_cookies_section())
        layout.addWidget(self._build_ffmpeg_section())
        layout.addWidget(self._build_appearance_section())
        layout.addWidget(self._build_queue_section())
        layout.addWidget(self._build_ytdlp_section())

        remaining = QLabel(SETTINGS_STILL_TO_COME, self)
        remaining.setObjectName("settingsRemaining")
        remaining.setTextFormat(Qt.TextFormat.PlainText)
        remaining.setWordWrap(True)
        layout.addWidget(remaining)
        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.setObjectName("settingsButtons")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # --- downloads ----------------------------------------------------------------------

    def _build_downloads_section(self) -> QWidget:
        box = QGroupBox("Downloads", self)
        box.setObjectName("downloadsSection")
        layout = QVBoxLayout(box)

        self._directory_label = QLabel(box)
        self._directory_label.setObjectName("downloadDirectoryValue")
        # `T016-R6`: a label showing text this application did not author is PlainText. A path is
        # exactly that — the user's own folder names, which may contain anything.
        self._directory_label.setTextFormat(Qt.TextFormat.PlainText)
        self._directory_label.setWordWrap(True)
        self._directory_label.setAccessibleName("Download folder")
        layout.addWidget(self._directory_label)

        self._directory_note = QLabel(box)
        self._directory_note.setObjectName("downloadDirectoryNote")
        self._directory_note.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._directory_note)

        row = QHBoxLayout()
        choose = QPushButton("Choose folder...", box)
        choose.setObjectName("chooseDownloadDirectory")
        choose.setAccessibleName("Choose the download folder")
        choose.clicked.connect(self._pick_a_directory)
        row.addWidget(choose)

        self._use_default = QPushButton("Use the default folder", box)
        self._use_default.setObjectName("useDefaultDownloadDirectory")
        self._use_default.setAccessibleName("Use the default download folder")
        self._use_default.clicked.connect(lambda: self._remember(None))
        row.addWidget(self._use_default)
        row.addStretch(1)
        layout.addLayout(row)

        self._show_directory()
        return box

    def _show_directory(self) -> None:
        """Put the folder in force on screen, and say whether it is a choice or the default."""
        self._directory_label.setText(str(self._directory))
        self._directory_note.setText(DEFAULT_DIRECTORY_NOTE if self._directory_is_default else "")
        # Nothing to clear when nothing was chosen. Disabled rather than hidden, so the row does
        # not change shape under the pointer (`T-060`'s rule for the retry button).
        self._use_default.setEnabled(not self._directory_is_default)

    def _ask_for_a_directory(self, start: Path) -> Path | None:
        """The real picker. Replaced in tests, for the reason the module docstring gives."""
        chosen = QFileDialog.getExistingDirectory(self, "Choose the download folder", str(start))
        return Path(chosen) if chosen else None

    def _pick_a_directory(self) -> None:
        chosen = self._choose_directory(self._directory)
        if chosen is None:
            # Cancelled. **Not the same as "use the default"** — that is the other button, and
            # collapsing the two would let a mis-click silently move where files land.
            return
        self._remember(chosen)

    def _remember(self, directory: Path | None) -> None:
        self._on_directory_chosen(directory)
        self._directory_is_default = directory is None
        if directory is not None:
            self._directory = directory
            self._show_directory()

    def show_download_directory(self, directory: Path, *, is_default: bool) -> None:
        """Show the folder composition resolved, after this screen asked for a change.

        Called back rather than assumed, because *"use the default"* is a request whose answer —
        the platform's downloads folder — is composition's to compute and not this screen's to
        guess (`ARC-007`: `ui/` holds no settings writer and no platform paths).
        """
        self._directory = directory
        self._directory_is_default = is_default
        self._show_directory()

    # --- cookies ------------------------------------------------------------------------

    def _build_naming_section(self) -> QWidget:
        """What a new paste starts with, and how its file is named (`REQ-023`, `T-195`)."""
        box = QGroupBox("New downloads", self)
        box.setObjectName("namingSection")
        layout = QVBoxLayout(box)

        preset_label = QLabel("Preset a newly pasted URL starts with", box)
        preset_label.setWordWrap(True)
        layout.addWidget(preset_label)

        self._preset_choice = QComboBox(box)
        self._preset_choice.setObjectName(DEFAULT_PRESET_NAME)
        self._preset_choice.setAccessibleName("Default preset")
        for name in self._preset_names:
            self._preset_choice.addItem(name, name)
        if self._default_preset:
            found = self._preset_choice.findData(self._default_preset)
            if found >= 0:
                self._preset_choice.setCurrentIndex(found)
        # **Disabled with the reason beside it, never drawn dead** (`UX-005` §5, `P-13`). A caller
        # that supplies no names and no writer has nothing to choose between.
        self._preset_choice.setEnabled(
            bool(self._preset_names) and self._on_default_preset_chosen is not None
        )
        self._preset_choice.currentIndexChanged.connect(self._on_preset_index)
        layout.addWidget(self._preset_choice)

        self._preset_note = QLabel(box)
        self._preset_note.setObjectName("defaultPresetNote")
        self._preset_note.setWordWrap(True)
        self._preset_note.setText(
            "" if self._preset_choice.isEnabled() else "No presets are available to choose between."
        )
        layout.addWidget(self._preset_note)

        template_label = QLabel(
            "How downloads are named, when a preset does not say otherwise", box
        )
        template_label.setWordWrap(True)
        layout.addWidget(template_label)

        self._template_field = QLineEdit(box)
        self._template_field.setObjectName(OUTPUT_TEMPLATE_NAME)
        self._template_field.setAccessibleName("Default output template")
        self._template_field.setText(self._output_template)
        self._template_field.setPlaceholderText(self._shipped_template)
        self._template_field.setEnabled(self._on_output_template_chosen is not None)
        # **Checked as it is typed, written only when it is usable** (`P-23`, `T-195`). `T-112`
        # made the same call for the per-row editor: showing the error and storing the value
        # anyway satisfies the visible half of the criterion and queues a broken download.
        self._template_field.textChanged.connect(self._on_template_text)
        layout.addWidget(self._template_field)

        self._template_note = QLabel(box)
        self._template_note.setObjectName(OUTPUT_TEMPLATE_NOTE_NAME)
        # The refusal quotes the template, which is the user's own text (`T016-R6`).
        self._template_note.setTextFormat(Qt.TextFormat.PlainText)
        self._template_note.setWordWrap(True)
        layout.addWidget(self._template_note)

        return box

    def _on_preset_index(self, index: int) -> None:
        if self._on_default_preset_chosen is None or index < 0:
            return
        chosen = self._preset_choice.itemData(index)
        if isinstance(chosen, str) and chosen:
            self._on_default_preset_chosen(chosen)

    def _on_template_text(self, text: str) -> None:
        """Refuse at edit time, with the reason, and do not store what was refused.

        **The same check the per-row editor makes**, reached through
        `core.output_template.unsupported_refusal` — which is what `manager.preview_output_path`
        calls, so the editor and this screen cannot come to disagree about what a usable template
        is. A second implementation of the rule is the defect `ARC-002` reasons about.
        """
        if self._on_output_template_chosen is None:
            return
        refusal = self._refusal_for(text) if text else None
        self._template_note.setText(refusal or "")
        if refusal is None:
            self._on_output_template_chosen(text)

    def _refusal_for(self, template: str) -> str | None:
        """The authoritative refusal where composition supplied one (`T195-R2`)."""
        if self._refuse_template is not None:
            return self._refuse_template(template)
        return unsupported_refusal(template)

    def show_preset_names(self, names: Sequence[str], default: str) -> None:
        """Re-offer the catalogue, keeping the stored default selected (`T195-R5`).

        **An open screen has to follow a live ffmpeg change.** Accepting an ffmpeg location makes
        presets performable that were not a moment ago, and a combo built when the screen opened
        went on offering the smaller list — so the user saw one preset while the add dialog offered
        four, with restart the only way out and nothing saying so.

        Rebuilt wholesale rather than diffed: the list is five entries, and a patch would be a
        second opinion about what the catalogue is.
        """
        self._preset_names = tuple(names)
        blocked = self._preset_choice.blockSignals(True)
        try:
            self._preset_choice.clear()
            for name in self._preset_names:
                self._preset_choice.addItem(name, name)
            found = self._preset_choice.findData(default)
            if found >= 0:
                self._preset_choice.setCurrentIndex(found)
        finally:
            self._preset_choice.blockSignals(blocked)
        self._preset_choice.setEnabled(
            bool(self._preset_names) and self._on_default_preset_chosen is not None
        )
        self._preset_note.setText(
            "" if self._preset_choice.isEnabled() else "No presets are available to choose between."
        )

    def show_default_preset(self, name: str) -> None:
        """Reflect the stored default, so the screen never disagrees with the file."""
        found = self._preset_choice.findData(name)
        if found >= 0 and found != self._preset_choice.currentIndex():
            blocked = self._preset_choice.blockSignals(True)
            self._preset_choice.setCurrentIndex(found)
            self._preset_choice.blockSignals(blocked)

    def show_output_template(self, template: str) -> None:
        """Reflect the stored template, without echoing it back through the writer."""
        if template == self._template_field.text():
            return
        blocked = self._template_field.blockSignals(True)
        self._template_field.setText(template)
        self._template_field.blockSignals(blocked)
        self._template_note.setText("")

    def _build_cookies_section(self) -> QWidget:
        """A cookies file for content the user is already signed in to (`REQ-026`, `T-197`)."""
        box = QGroupBox("Cookies", self)
        box.setObjectName("cookiesSection")
        layout = QVBoxLayout(box)

        explanation = QLabel(COOKIES_EXPLANATION, box)
        explanation.setObjectName("cookiesExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        #: **Three exclusive sources**, because `REQ-026` says *a browser profile **or** a cookies
        #: file*, and two set at once is a credential chosen by accident (`T197-R4`).
        self._cookie_sources: dict[str, QRadioButton] = {}
        for key, label in (
            ("none", "No cookies"),
            ("browser", "From a browser"),
            ("file", "From a cookies file"),
        ):
            button = QRadioButton(label, box)
            button.setObjectName(f"cookieSource{key.capitalize()}")
            button.setAccessibleName(label)
            button.toggled.connect(partial(self._cookie_source_picked, key))
            layout.addWidget(button)
            self._cookie_sources[key] = button

        self._cookie_browser_choice = QComboBox(box)
        self._cookie_browser_choice.setObjectName("cookieBrowserChoice")
        self._cookie_browser_choice.setAccessibleName("Browser to read cookies from")
        for browser in BROWSER_NAMES:
            self._cookie_browser_choice.addItem(browser)
        self._cookie_browser_choice.currentTextChanged.connect(self._cookie_browser_picked)
        layout.addWidget(self._cookie_browser_choice)

        self._cookie_value = QLabel(box)
        self._cookie_value.setObjectName("cookieFileValue")
        # The user's own path (`T016-R6`).
        self._cookie_value.setTextFormat(Qt.TextFormat.PlainText)
        self._cookie_value.setWordWrap(True)
        self._cookie_value.setAccessibleName("Cookies file")
        layout.addWidget(self._cookie_value)

        row = QHBoxLayout()
        choose = QPushButton("Choose cookies file...", box)
        choose.setObjectName("chooseCookieFile")
        choose.setAccessibleName("Choose a cookies file")
        choose.clicked.connect(self._pick_a_cookie_file)
        row.addWidget(choose)

        self._clear_cookies = QPushButton("Use no cookies", box)
        self._clear_cookies.setObjectName("clearCookieFile")
        self._clear_cookies.setAccessibleName("Use no cookies")
        self._clear_cookies.clicked.connect(lambda: self._remember_cookies(None))
        row.addWidget(self._clear_cookies)
        row.addStretch(1)
        layout.addLayout(row)

        self._show_cookie_file()
        return box

    def _show_cookie_file(self) -> None:
        self._cookie_value.setText(
            str(self._cookie_file) if self._cookie_file is not None else NO_COOKIES_NOTE
        )
        self._clear_cookies.setEnabled(self._cookie_file is not None)
        current = (
            "file"
            if self._cookie_file is not None
            else "browser"
            if self._cookie_browser is not None
            else "none"
        )
        for key, button in self._cookie_sources.items():
            blocked = button.blockSignals(True)
            try:
                button.setChecked(key == current)
            finally:
                button.blockSignals(blocked)
        self._cookie_browser_choice.setEnabled(current == "browser")
        self._clear_cookies.setEnabled(self._cookie_file is not None)
        if self._cookie_browser:
            blocked = self._cookie_browser_choice.blockSignals(True)
            try:
                self._cookie_browser_choice.setCurrentText(
                    self._cookie_browser.split(":", 1)[0].split("+", 1)[0]
                )
            finally:
                self._cookie_browser_choice.blockSignals(blocked)

    def _cookie_source_picked(self, key: str, checked: bool) -> None:
        """One source at a time. Choosing *browser* asks for the one the combo shows."""
        if not checked:
            return
        if key == "none":
            self._remember_cookies(None)
        elif key == "browser":
            self._remember_browser(self._cookie_browser_choice.currentText())
        elif key == "file":
            self._pick_a_cookie_file()

    def _cookie_browser_picked(self, browser: str) -> None:
        if self._cookie_sources["browser"].isChecked():
            self._remember_browser(browser)

    def _remember_browser(self, browser: str | None) -> None:
        if self._on_cookie_browser_chosen is not None:
            self._on_cookie_browser_chosen(browser)

    def show_cookie_browser(self, browser: str | None) -> None:
        """Show the browser source composition settled on (`T197-R4`)."""
        self._cookie_browser = browser
        if browser is not None:
            self._cookie_file = None
        self._show_cookie_file()

    def _pick_a_cookie_file(self) -> None:
        chosen = self._choose_file(self._cookie_file)
        if chosen is None:
            # **Cancelled leaves nothing behind, including the radio** (`T197-R4`). Selecting
            # *From a cookies file* moves the button before the dialog opens, so dismissing it left
            # the screen claiming a source that was never set — and *No cookies* still selected
            # underneath in the settings. Redrawn from the state actually in force.
            self._show_cookie_file()
            return
        self._remember_cookies(chosen)

    def _remember_cookies(self, path: Path | None) -> None:
        if self._on_cookie_file_chosen is not None:
            self._on_cookie_file_chosen(path)

    def show_cookie_source(self, file: Path | None, browser: str | None) -> None:
        """Show the source actually in force — **both halves, always** (`T197-R4`).

        `show_cookie_file(None)` used to mean *no file*, which is not the same as *no cookies*: it
        left a previously chosen browser on screen after the user asked for neither. One method
        taking the pair removes the class rather than the instance — there is no way to tell the
        screen half of a change.
        """
        self._cookie_file = file
        self._cookie_browser = browser
        self._show_cookie_file()

    def show_cookie_file(self, path: Path | None) -> None:
        """The file half, kept for callers that only have one (`T-197`)."""
        self.show_cookie_source(path, None if path is not None else self._cookie_browser)

    # --- ffmpeg -------------------------------------------------------------------------

    def _build_ffmpeg_section(self) -> QWidget:
        """Where ffmpeg is, and what this application can do as a result (`REQ-024`, `T-199`)."""
        box = QGroupBox("ffmpeg", self)
        box.setObjectName("ffmpegSection")
        layout = QVBoxLayout(box)

        #: **The summary, not just the path.** `REQ-024` asks the application to report *which
        #: features are unavailable*, and this is the screen a user reaches when they want to fix
        #: that — so it says what is lost here rather than only in the status bar.
        self._ffmpeg_state = QLabel(box)
        self._ffmpeg_state.setObjectName("ffmpegState")
        self._ffmpeg_state.setTextFormat(Qt.TextFormat.PlainText)
        self._ffmpeg_state.setWordWrap(True)
        self._ffmpeg_state.setAccessibleName("ffmpeg status")
        layout.addWidget(self._ffmpeg_state)

        self._ffmpeg_path = QLabel(box)
        self._ffmpeg_path.setObjectName("ffmpegLocationValue")
        # A path the user chose is their own text (`T016-R6`).
        self._ffmpeg_path.setTextFormat(Qt.TextFormat.PlainText)
        self._ffmpeg_path.setWordWrap(True)
        self._ffmpeg_path.setAccessibleName("ffmpeg location")
        layout.addWidget(self._ffmpeg_path)

        row = QHBoxLayout()
        choose = QPushButton("Choose ffmpeg...", box)
        choose.setObjectName("chooseFfmpegLocation")
        choose.setAccessibleName("Choose where ffmpeg is")
        choose.clicked.connect(self._pick_an_ffmpeg)
        row.addWidget(choose)

        self._clear_ffmpeg = QPushButton("Look on PATH", box)
        self._clear_ffmpeg.setObjectName("clearFfmpegLocation")
        self._clear_ffmpeg.setAccessibleName("Look for ffmpeg on PATH")
        self._clear_ffmpeg.clicked.connect(lambda: self._remember_ffmpeg(None))
        row.addWidget(self._clear_ffmpeg)
        row.addStretch(1)
        layout.addLayout(row)

        self._show_ffmpeg()
        return box

    def _show_ffmpeg(self) -> None:
        self._ffmpeg_state.setText(self._ffmpeg_summary)
        self._ffmpeg_path.setText(
            str(self._ffmpeg_location) if self._ffmpeg_location is not None else FFMPEG_ON_PATH_NOTE
        )
        self._clear_ffmpeg.setEnabled(self._ffmpeg_location is not None)

    def _ask_for_a_file(self, start: Path | None) -> Path | None:
        """The real picker. Replaced in tests, for the module docstring's reason."""
        chosen, _ = QFileDialog.getOpenFileName(
            self, "Choose where ffmpeg is", str(start) if start is not None else ""
        )
        return Path(chosen) if chosen else None

    def _pick_an_ffmpeg(self) -> None:
        chosen = self._choose_file(self._ffmpeg_location)
        if chosen is None:
            # Cancelled — not the same as *look on PATH*, which is the other button.
            return
        self._remember_ffmpeg(chosen)

    def _remember_ffmpeg(self, location: Path | None) -> None:
        if self._on_ffmpeg_location_chosen is not None:
            self._on_ffmpeg_location_chosen(location)

    def show_ffmpeg_location(self, location: Path | None, summary: str) -> None:
        """Show what composition resolved: the location, and what it bought (`T-199`).

        Both come back rather than being assumed here, for `show_download_directory`'s reason —
        whether a chosen file is a usable ffmpeg is `find_ffmpeg`'s answer, and `ui/` may not ask
        `downloader/` directly.
        """
        self._ffmpeg_location = location
        self._ffmpeg_summary = summary
        self._show_ffmpeg()

    # --- appearance ---------------------------------------------------------------------

    def _build_appearance_section(self) -> QWidget:
        box = QGroupBox("Appearance", self)
        box.setObjectName("appearanceSection")
        layout = QVBoxLayout(box)

        #: Radio buttons rather than a combo, for two mutually exclusive values: both choices are
        #: visible without opening anything, and a screen reader announces "Light, 1 of 2" instead
        #: of a collapsed control's current value alone (`NFR-005`).
        self._themes: dict[str, QRadioButton] = {}
        for name in THEME_NAMES:
            button = QRadioButton(THEME_LABELS[name], box)
            button.setObjectName(f"theme{THEME_LABELS[name]}")
            button.setAccessibleName(f"{THEME_LABELS[name]} theme")
            button.setChecked(name == self._theme)
            # `partial` rather than a lambda with a default argument: the latter is the
            # late-binding workaround mypy cannot type, and this loop rebinds `name`.
            button.toggled.connect(partial(self._theme_picked, name))
            layout.addWidget(button)
            self._themes[name] = button
        return box

    def _theme_picked(self, name: str, checked: bool) -> None:
        # `toggled` fires for the button being cleared as well as the one being set; only the set
        # one is a choice.
        if not checked or name == self._theme:
            return
        self._theme = name
        self._on_theme_chosen(name)

    # --- queue --------------------------------------------------------------------------

    def _build_queue_section(self) -> QWidget:
        box = QGroupBox("Queue", self)
        box.setObjectName("queueSection")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        label = QLabel("Downloads at once", box)
        label.setObjectName("settingsConcurrencyLabel")
        row.addWidget(label)

        self._concurrency = QSpinBox(box)
        self._concurrency.setObjectName("settingsConcurrencyChoice")
        self._concurrency.setAccessibleName("Downloads at once")
        # **The range is the settings layer's**, read from it rather than restated — the reason
        # `REQ-013`'s bounds live in `core/` rather than in a widget.
        #
        # **This is the only control for the limit since `UX-013`** (`T-234`), which retires the
        # sentence this explanation used to end with — *"This is the same setting as the
        # toolbar's."* There is no toolbar copy to be the same as.
        self._concurrency.setRange(CONCURRENCY_MINIMUM, CONCURRENCY_MAXIMUM)
        self._concurrency.setValue(self._initial_concurrency)
        # **The steps are labelled buttons, not native arrows** (`UX-005` row 11, `T-141`,
        # rebuilt here by `T-236`). The arrows were reported missing twice: first drawn as solid
        # blocks by the CSS border-triangle trick, then drawn correctly as ~10px native wedges in
        # a 23px control and **still unreadable** — measured on the maintainer's own session at
        # the real size, up `4,6,8,10` and down `8,6,4`. The two step labels are **text**, and no
        # style sheet can silently un-draw text, which is the shared cause of `T-129`, `T-133`
        # and `T-139`.
        #
        # **The ruling names the control, not the toolbar** (`T234-R2`). `UX-013` moved where the
        # control lives; it did not amend how it steps. `T-234` removed the buttons with the
        # toolbar and left this spinner at **57x22 with `UpDownArrows`** — materially the 58x23
        # control `T-141` measured — so the accepted design was unbuilt by a relocation that had
        # no authority to unbuild it.
        self._concurrency.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._concurrency.valueChanged.connect(self._on_concurrency_chosen)

        fewer = self._step_button(box, STEP_DOWN_LABEL, "Fewer concurrent downloads")
        more = self._step_button(box, STEP_UP_LABEL, "More concurrent downloads")
        fewer.clicked.connect(self._concurrency.stepDown)
        more.clicked.connect(self._concurrency.stepUp)
        row.addWidget(fewer)
        row.addWidget(self._concurrency)
        row.addWidget(more)
        row.addStretch(1)
        layout.addLayout(row)

        def _limit_the_steps(value: int) -> None:
            """Neither button offers a step the range will not take (`UX-005` §5)."""
            fewer.setEnabled(value > CONCURRENCY_MINIMUM)
            more.setEnabled(value < CONCURRENCY_MAXIMUM)

        self._concurrency.valueChanged.connect(_limit_the_steps)
        _limit_the_steps(self._concurrency.value())

        explanation = QLabel(
            "Each download is a separate process, so a higher number is not always faster.",
            box,
        )
        explanation.setObjectName("settingsConcurrencyNote")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        return box

    def _build_ytdlp_section(self) -> QWidget:
        """The version in use, and the two actions `REQ-025` asks for (`T-198`, `OPS-002`).

        **The version is displayed, never computed here.** It arrives through `show_ytdlp` from a
        child process that imported yt-dlp, because the promise is to report *what is running* —
        and a screen that derives a number from a pin or a folder name reports what ought to be
        running instead. Until that answer arrives the field says so rather than showing a
        plausible placeholder.

        **Both actions are offered together and disabled together.** Updating and reverting are
        the same operation in opposite directions, and while either is in flight neither may
        start: they write the same directory.
        """
        box = QGroupBox("yt-dlp", self)
        box.setObjectName("ytdlpSection")
        layout = QVBoxLayout(box)

        explanation = QLabel(
            "Sites change constantly, and yt-dlp is what keeps up with them. Updating affects "
            "downloads only — Tracks & Trails itself is not changed.",
            box,
        )
        explanation.setObjectName("ytdlpExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        row = QHBoxLayout()
        label = QLabel("Version in use", box)
        label.setObjectName("ytdlpVersionLabel")
        row.addWidget(label)

        self._ytdlp_version = QLabel(YTDLP_VERSION_UNKNOWN, box)
        self._ytdlp_version.setObjectName(YTDLP_VERSION_NAME)
        self._ytdlp_version.setTextFormat(Qt.TextFormat.PlainText)
        # Selectable because the first thing a bug report needs is this number, and retyping a
        # version from a screenshot is how a report ends up describing a different release.
        self._ytdlp_version.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(self._ytdlp_version)
        row.addStretch(1)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        self._ytdlp_update = QPushButton("Update to the latest version", box)
        self._ytdlp_update.setObjectName(YTDLP_UPDATE_NAME)
        self._ytdlp_update.setAccessibleName("Update yt-dlp to the latest version")
        self._ytdlp_update.clicked.connect(self._start_ytdlp_update)
        buttons.addWidget(self._ytdlp_update)

        self._ytdlp_revert = QPushButton(YTDLP_REVERT_LABEL, box)
        self._ytdlp_revert.setObjectName(YTDLP_REVERT_NAME)
        self._ytdlp_revert.setAccessibleName("Go back to the bundled yt-dlp version")
        self._ytdlp_revert.clicked.connect(self._start_ytdlp_revert)
        buttons.addWidget(self._ytdlp_revert)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._ytdlp_note = QLabel("", box)
        self._ytdlp_note.setObjectName(YTDLP_NOTE_NAME)
        self._ytdlp_note.setTextFormat(Qt.TextFormat.PlainText)
        self._ytdlp_note.setWordWrap(True)
        layout.addWidget(self._ytdlp_note)

        # Nothing to revert *to* until a resolution says a user copy is in use, and nothing to
        # update until composition has supplied a route. Both are re-decided by `show_ytdlp`.
        self._ytdlp_update.setEnabled(self._on_ytdlp_update is not None)
        self._ytdlp_revert.setEnabled(False)
        return box

    def _start_ytdlp_update(self) -> None:
        if self._on_ytdlp_update is not None:
            self._on_ytdlp_update()

    def _start_ytdlp_revert(self) -> None:
        if self._on_ytdlp_revert is not None:
            self._on_ytdlp_revert()

    def show_ytdlp(
        self,
        version: str,
        source: str,
        *,
        is_user_managed: bool,
        rejected: Sequence[str] = (),
    ) -> None:
        """Report which yt-dlp a worker imported (`REQ-025`).

        **`is_user_managed` decides whether reverting is offered**, and it comes from the
        resolution rather than from whether the directory exists. A copy that is present but does
        not import is not in use, and offering *"use the bundled version"* as though it were would
        describe the wrong state — while a rejected copy still needs saying, which is what
        `rejected` is for (`ARCHITECTURE.md` §6: reported, never silently ignored).
        """
        self._ytdlp_version.setText(f"{version} — {source}" if source else version)
        # **Held rather than read back off the button.** `show_ytdlp_busy` disables both controls
        # while an operation runs, so asking the widget afterwards whether reverting is available
        # returns *"no"* because it was just switched off — and the button never comes back. The
        # resolution is the fact; the widget is a rendering of it.
        self._ytdlp_is_user_managed = is_user_managed
        self._ytdlp_revert.setEnabled(is_user_managed and self._on_ytdlp_revert is not None)
        self._ytdlp_note.setText(
            "An installed copy could not be used, so the bundled version is running: "
            + "; ".join(rejected)
            if rejected
            else ""
        )

    def show_ytdlp_problem(self, reason: str) -> None:
        """Say why the last update, revert or check did not happen.

        The reason is passed through as written: `ytdlp_update` composes these sentences for a
        user and they carry no path or URL (`NFR-007`), so rewording here would only risk
        replacing an accurate one with a generic one — the failure `NFR-006` names.
        """
        self._ytdlp_note.setText(reason)

    def show_ytdlp_busy(self, busy: bool) -> None:
        """Disable both actions while either is running, and say the screen is not stuck.

        A positional `bool` because this mirrors the service's `busy_changed(bool)` signal, which
        is what composition connects it to.
        """
        self._ytdlp_update.setEnabled(not busy and self._on_ytdlp_update is not None)
        self._ytdlp_revert.setEnabled(
            not busy and self._ytdlp_is_user_managed and self._on_ytdlp_revert is not None
        )
        self._ytdlp_update.setText(YTDLP_WORKING_LABEL if busy else "Update to the latest version")
        if busy:
            self._ytdlp_note.setText("")

    def _step_button(self, parent: QWidget, label: str, announced: str) -> QToolButton:
        """One of the concurrency control's step buttons (`UX-005` row 11, `T-141`, `T-236`).

        **Its accessible name says the direction *and* the setting** (`NFR-005`). "Plus" read on
        its own says nothing about what it increases, and the visible label is a single character
        that a screen reader may or may not pronounce usefully.
        """
        button = QToolButton(parent)
        button.setObjectName(f"settingsConcurrencyStep{'Up' if label == STEP_UP_LABEL else 'Down'}")
        button.setText(label)
        button.setAccessibleName(announced)
        button.setStatusTip(announced)
        button.setProperty(STEP_BUTTON_PROPERTY, True)
        button.setAutoRepeat(True)
        # **Focus stays on the value, not on the steppers.** A user tabbing to this control wants
        # the number, and `NFR-005` asks the keyboard to reach what the pointer reaches — `Up` and
        # `Down` already do, from the spin box itself, so three tab stops for one setting would be
        # the keyboard reaching it three times rather than once.
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    def show_concurrency(self, limit: int) -> None:
        """Show the limit **composition applied**, without echoing it back (`T-146`).

        A naive `setValue` here would emit `valueChanged`, call composition again, and make every
        change a round trip. Blocked for exactly the assignment.

        **What this follows changed with `UX-013`** (`T-234`). It existed because two controls
        edited one value (`REQ-013`) and each had to show what the other did; the toolbar's copy is
        gone, and what remains to follow is composition itself — the number it applies is not
        always the number this control emitted, because `settings.toml` clamps
        (`CONCURRENCY_MINIMUM`/`MAXIMUM`) and the applied value is the one in force. A screen
        showing a number the pool is not running is a screen that will write it back.
        """
        blocked = self._concurrency.blockSignals(True)
        try:
            self._concurrency.setValue(limit)
        finally:
            self._concurrency.blockSignals(blocked)
