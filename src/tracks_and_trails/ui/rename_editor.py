"""Rename one download: a plain name and the path it produces (`UX-014`, 2026-09-13).

**A name, not a template.** The per-item template editor asked a user to write `%(title)s` syntax
to name one file, and the maintainer ruled it out: *"no user is gonna want to do that."* This takes
the words the file should be called, prefilled with what the Settings pattern would produce, and
the surface embedding it writes them literally through `output_template.renamed_template` — a `%`
is a percent sign, the folders stay the setting's and the extension stays yt-dlp's.

**It renders nothing**: the path shown comes from
`DownloadManager.preview_output_path`, handed back through `show_preview`.
"""

from collections.abc import Callable
from typing import Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractButton,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core.output_template import OutputPreview
from tracks_and_trails.ui.keyboard import route_is_elsewhere

#: What the preview is labelled when the path is exact.
PREVIEW_LABEL: Final = "Where it will be saved"

#: What the preview is labelled when the container is still yt-dlp's to choose (`REQ-011`, amended
#: 2026-08-01). **The label changes, not a footnote beside it**: the difference between a promise
#: and an intention belongs in the name of the thing, where somebody skimming will read it.
PROVISIONAL_LABEL: Final = "Where it is intended to be saved"

#: What the input is labelled.
NAME_LABEL: Final = "File name"

#: What Qt's clear button is announced as. Qt adds the button and names nothing (`P4EXIT-R1`).
CLEAR_NAME_LABEL: Final = "Clear the file name"

#: Said once under the field: what empty means, and that the extension is not the user's to type.
NAME_HINT: Final = (
    "Leave it empty to use how downloads are named in Preferences. The extension is added for you."
)


def present_preview(
    preview: OutputPreview, field: QLineEdit, caption: QLabel, message: QLabel
) -> None:
    """Draw one `OutputPreview` into a path field, its caption and its message line.

    **One function for both editors that preview a path** — this one and `RenameEditor` — so a
    refused, an exact and a provisional path are drawn the same way wherever a path is shown.

    The three states are drawn as three, and never mixed: a refusal empties the path field, an
    exact path carries no note, and a provisional one is labelled *intended* in the caption rather
    than annotated underneath — the difference between a promise and an intention is part of what
    the field is, so it belongs in the field's name.
    """
    field.setText(preview.path)
    caption.setText(PROVISIONAL_LABEL if preview.provisional is not None else PREVIEW_LABEL)
    message.setText(preview.refusal or preview.provisional or "")
    # **The state reaches a screen reader too** (`NFR-005`). A caption changing from "will be" to
    # "is intended to be" is a visual difference; the accessible description is where a user who
    # cannot see the caption hears the same distinction.
    if preview.is_refused:
        spoken = f"No path: {preview.refusal}"
    elif preview.provisional is not None:
        spoken = f"{preview.path}. {preview.provisional}"
    else:
        spoken = preview.path
    field.setAccessibleDescription(spoken)
    caption.setAccessibleName(caption.text())


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


class RenameDialog(QDialog):
    """`RenameEditor` in a window of its own, for a queued download (`UX-014`).

    **A dialog here, a panel in Add URLs**, for the reason each surface already opens its other
    per-item commands the way it does: the queue's *Options…* and *Choose specific formats…* are
    windows, and the add dialog's are panels on the row.

    **OK is unavailable while the name would be refused**, as the format dialog's accept is until a
    selection names a download: the reason is on screen beside the field, and pressing OK on it
    could only fail.
    """

    def __init__(
        self,
        title: str,
        name: str,
        preview: Callable[[str], OutputPreview],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("renameDialog")
        self.setWindowTitle(f"Rename {title}")
        self._preview = preview

        layout = QVBoxLayout(self)
        self._editor = RenameEditor(name, self)
        layout.addWidget(self._editor)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._editor.name_changed.connect(self._show)
        self._show(name)
        self.resize(560, self.sizeHint().height())

    @property
    def editor(self) -> RenameEditor:
        return self._editor

    @property
    def name(self) -> str:
        return self._editor.name.strip()

    @property
    def ok_button(self) -> QPushButton:
        button = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert button is not None
        return button

    def _show(self, name: str) -> None:
        answer = self._preview(name)
        self._editor.show_preview(answer)
        self.ok_button.setEnabled(not answer.is_refused)
