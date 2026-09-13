"""Rename one download: a plain name and the path it produces (`UX-014`, 2026-09-13).

**A name, not a template.** The per-item template editor asked a user to write `%(title)s` syntax
to name one file, and the maintainer ruled it out: *"no user is gonna want to do that."* This takes
the words the file should be called, prefilled with what the Settings pattern would produce, and
the surface embedding it writes them literally through `output_template.renamed_template` — a `%`
is a percent sign, the folders stay the setting's and the extension stays yt-dlp's.

**It renders nothing**, for `template_editor`'s reason: the path shown comes from
`DownloadManager.preview_output_path`, handed back through `show_preview`.
"""

from typing import Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QAbstractButton, QLabel, QLineEdit, QVBoxLayout, QWidget

from tracks_and_trails.core.output_template import OutputPreview
from tracks_and_trails.ui.keyboard import route_is_elsewhere
from tracks_and_trails.ui.template_editor import PREVIEW_LABEL, present_preview

#: What the input is labelled.
NAME_LABEL: Final = "File name"

#: What Qt's clear button is announced as — `template_editor.CLEAR_LABEL`'s reason, one field over.
CLEAR_NAME_LABEL: Final = "Clear the file name"

#: Said once under the field: what empty means, and that the extension is not the user's to type.
NAME_HINT: Final = (
    "Leave it empty to use how downloads are named in Settings. The extension is added for you."
)


class RenameEditor(QWidget):
    """A file-name input and what the current name would write."""

    #: `str` — the name changed, by typing. The surface asks for a preview and hands it back.
    name_changed = Signal(str)

    def __init__(self, name: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("renameEditor")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        caption = QLabel(NAME_LABEL, self)
        caption.setObjectName("fileNameCaption")
        layout.addWidget(caption)

        self._input = QLineEdit(name, self)
        self._input.setObjectName("fileNameInput")
        self._input.setAccessibleName(NAME_LABEL)
        self._input.setAccessibleDescription(NAME_HINT)
        self._input.setClearButtonEnabled(True)
        clear_button = self._input.findChild(QAbstractButton)
        if clear_button is not None:
            clear_button.setAccessibleName(CLEAR_NAME_LABEL)
            route_is_elsewhere(clear_button, "Ctrl+A then Delete, in the field itself")
        self._input.textEdited.connect(self.name_changed)
        caption.setBuddy(self._input)
        layout.addWidget(self._input)

        hint = QLabel(NAME_HINT, self)
        hint.setObjectName("fileNameHint")
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(hint)

        self._preview_caption = QLabel(PREVIEW_LABEL, self)
        self._preview_caption.setObjectName("renamePreviewCaption")
        layout.addWidget(self._preview_caption)

        # A focusable read-only field, for `P-22`'s reason: the path can be reviewed and copied.
        self._preview = QLineEdit(self)
        self._preview.setObjectName("renamePathPreview")
        self._preview.setReadOnly(True)
        self._preview.setAccessibleName(PREVIEW_LABEL)
        self._preview_caption.setBuddy(self._preview)
        layout.addWidget(self._preview)

        self._message = QLabel(self)
        self._message.setObjectName("renameMessage")
        self._message.setAccessibleName("Why this name cannot be used")
        self._message.setWordWrap(True)
        # A path is site metadata (`T016-R6`).
        self._message.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._message)
        layout.addStretch(1)

        QWidget.setTabOrder(self._input, self._preview)

    @property
    def name(self) -> str:
        return self._input.text()

    @property
    def input_field(self) -> QLineEdit:
        return self._input

    @property
    def preview_field(self) -> QLineEdit:
        return self._preview

    def preview_text(self) -> str:
        return self._preview.text()

    def message_text(self) -> str:
        return self._message.text()

    def focus_chain(self) -> list[QWidget]:
        """The keyboard order: the name, then the path it produces."""
        return [self._input, self._preview]

    def show_preview(self, preview: OutputPreview) -> None:
        present_preview(preview, self._preview, self._preview_caption, self._message)
