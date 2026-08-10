"""The Settings screen (`REQ-023`, built by `T-146`).

**Three of `REQ-023`'s eight settings, and the screen says which.** The requirement names default
download directory, default preset, concurrency limit, output template, ffmpeg location, network
options, cookie source and theme. This screen holds the download directory, the theme and the
concurrency limit; the other five have their own owners (`T-195`, `T-196`, `T-197`, `T-199`), and
`SETTINGS_STILL_TO_COME` is shown on the screen itself so it never claims coverage it does not
have — `T-146`'s own criterion, and the failure mode a settings screen has by default.

*(A module of this name existed until 2026-08-06 holding one control, `Clear download records`. It
went with `REQ-020`. Nothing of it survives here but the shape of the menu route, which was worth
reading before writing this: `T169-R4` recorded that the shell was gone so a later implementer
would not go looking for it.)*

## Changes apply as they are made, and the button says `Close`

The same idiom as the toolbar's concurrency control, which has applied-and-saved on every change
since `T-078`. An `OK`/`Cancel` pair would be the other honest shape, and it is the wrong one
here: two of these three settings are already visible elsewhere in the window — the concurrency
spinner in the toolbar, the theme in every pixel — so a change that waited for `OK` would have to
either not preview (and make the theme unpickable without guessing) or preview and then be
revertible, which is a transaction this screen has no way to roll back.

## The directory picker is injected

`choose_directory` defaults to `QFileDialog.getExistingDirectory` and is a parameter because a
native modal cannot be driven headlessly (`ai/TESTING.md`), and a screen whose one route to its
main setting is untestable is a screen whose main setting is untested. The same seam, and the same
reasoning, as the manager's `entry_point`.
"""

from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core.settings import (
    CONCURRENCY_MAXIMUM,
    CONCURRENCY_MINIMUM,
    THEME_NAMES,
)

__all__ = [
    "DEFAULT_DIRECTORY_NOTE",
    "FFMPEG_ON_PATH_NOTE",
    "SETTINGS_STILL_TO_COME",
    "THEME_LABELS",
    "SettingsDialog",
]

#: What each theme is called on screen. The stored names are lower-case identifiers; these are the
#: words a user reads, and keeping them apart is what lets the file stay stable if the wording
#: changes.
THEME_LABELS: Final = {"light": "Light", "dark": "Dark"}

#: Shown under the folder when no folder has been chosen. **It names the actual path**, because
#: "the default" is not an answer to *where did my file go*.
DEFAULT_DIRECTORY_NOTE: Final = "Your usual downloads folder"

#: Shown where the path would be when none is set. Names the mechanism, because *"not set"* does
#: not tell a user what the application is doing instead.
FFMPEG_ON_PATH_NOTE: Final = "Looked for on PATH"

#: The screen's own statement of what it does not yet cover (`T-146`).
#:
#: **`REQ-023` names eight settings and this screen has three.** A settings screen that shows only
#: what it implements reads as complete, and the five absences are each owned by a filed task —
#: so the honest thing is to say so where the user is looking rather than only in a document they
#: will not read.
SETTINGS_STILL_TO_COME: Final = (
    "Still to come: default preset, output template, network options, and cookie source."
)


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
        ffmpeg_location: Path | None = None,
        ffmpeg_summary: str = "",
        on_ffmpeg_location_chosen: Callable[[Path | None], None] | None = None,
        choose_file: Callable[[Path | None], Path | None] | None = None,
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
        self._ffmpeg_location = ffmpeg_location
        self._ffmpeg_summary = ffmpeg_summary
        self._on_ffmpeg_location_chosen = on_ffmpeg_location_chosen
        self._choose_file = choose_file or self._ask_for_a_file

        self.setObjectName("settingsDialog")
        self.setWindowTitle("Settings")

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_downloads_section())
        layout.addWidget(self._build_ffmpeg_section())
        layout.addWidget(self._build_appearance_section())
        layout.addWidget(self._build_queue_section())

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
        # **The range is the settings layer's**, read from it rather than restated — the same rule
        # the toolbar's spinner follows, and the reason `REQ-013`'s bounds live in `core/`.
        self._concurrency.setRange(CONCURRENCY_MINIMUM, CONCURRENCY_MAXIMUM)
        self._concurrency.setValue(self._initial_concurrency)
        self._concurrency.valueChanged.connect(self._on_concurrency_chosen)
        row.addWidget(self._concurrency)
        row.addStretch(1)
        layout.addLayout(row)

        explanation = QLabel(
            "Each download is a separate process, so a higher number is not always faster. "
            "This is the same setting as the toolbar's.",
            box,
        )
        explanation.setObjectName("settingsConcurrencyNote")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        return box

    def show_concurrency(self, limit: int) -> None:
        """Follow a change made on the toolbar, without echoing it back (`T-146`).

        The two controls edit one value (`REQ-013`), so each has to be able to show what the other
        did — and a naive `setValue` here would emit `valueChanged`, call composition again, and
        make every change a round trip. Blocked for exactly the assignment.
        """
        blocked = self._concurrency.blockSignals(True)
        try:
            self._concurrency.setValue(limit)
        finally:
            self._concurrency.blockSignals(blocked)
