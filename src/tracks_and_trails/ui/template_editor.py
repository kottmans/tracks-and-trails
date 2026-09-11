"""The output template editor and its live path preview (`REQ-011`, `T-112`).

`docs/UX_SPEC.md` §9.1 is the surface, and `UX-007` ruled its two open questions on 2026-08-07:

- **`P-22`** — the preview is a **focusable read-only field**, a second stop in the tab order. The
  spec proposed an unfocusable live region and was ruled against on its own argument: *a user who
  cannot `Tab` to the preview cannot review it at their own pace*, and a live region announces on
  the writer's schedule rather than the reader's. It costs one tab stop.
- **`P-23`** — an invalid template is refused **at edit time, with the reason**, rather than at
  download time. That is better feedback and it costs a validation path that runs on every
  keystroke, which is the trade the ruling accepted.
- **`P-9`** — the editor **lists the fields it supports beside the input**, rather than linking to
  yt-dlp's documentation, because the set this application supports is not yt-dlp's whole set.

## This widget renders nothing

It holds a string and displays an `OutputPreview`. Everything about *where a template writes* comes
from `DownloadManager.preview_output_path`, which is the one route `ARC-002` leaves open: `ui/` may
not import yt-dlp, and a `%(field)s` substituter written here would be a second implementation of
someone else's syntax — the `T-059` shape, with the two answers side by side on screen.

## Why a refused template shows no path at all

`OutputPreview` sets `path` or `refusal`, never both. Leaving the last good path on screen beside an
error is how a user comes to believe a broken template works, and it is the same mistake as a
control that looks like a choice and converts nothing (`T-075`).
"""

from typing import Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractButton,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core.output_template import SUPPORTED_FIELDS, OutputPreview
from tracks_and_trails.ui.keyboard import route_is_elsewhere

#: What the input is labelled. Product vocabulary rather than yt-dlp's: a user is naming a file,
#: not configuring an `outtmpl`.
TEMPLATE_LABEL: Final = "File name template"

#: What Qt's own clear button is announced as (`P4EXIT-R1`).
#:
#: **`setClearButtonEnabled(True)` adds a control to the accessibility tree and gives it no name.**
#: Measured, not inferred: `QAccessible` publishes `EditableText 'File name template'` with one
#: child, `Button ''`. Narrator and Orca both read that tree, so a user tabbing or touching past
#: the field met a button announced as nothing at all — `NFR-005`'s exact failure, contributed by
#: the toolkit rather than by this file.
#:
#: **The audit could not have seen it.** `tests/ui/conftest.py`'s `focusable()` walks controls
#: Tab can land on, and the clear button is `NoFocus` — reachable by pointer and by a screen
#: reader's own navigation, and invisible to a sweep keyed on the keyboard. The gate that catches
#: the next one is `test_every_published_control_has_a_name`, which walks the published tree
#: instead of the focus chain.
CLEAR_LABEL: Final = f"Clear the {TEMPLATE_LABEL.lower()}"

#: What the preview is labelled when the path is exact.
PREVIEW_LABEL: Final = "Where it will be saved"

#: What the preview is labelled when the container is still yt-dlp's to choose (`REQ-011`, amended
#: 2026-08-01). **The label changes, not a footnote beside it**: the difference between a promise
#: and an intention belongs in the name of the thing, where somebody skimming will read it.
PROVISIONAL_LABEL: Final = "Where it is intended to be saved"

#: What the fields list is introduced by (`P-9`).
FIELDS_LABEL: Final = "Fields you can use"

#: A subdirectory is the other half of `REQ-011`'s *path and filename control*, and it is not
#: discoverable from a list of fields. Said once, beside them.
SUBDIRECTORY_HINT: Final = (
    "A / makes a subfolder inside your download folder. A template cannot leave it."
)


def fields_text() -> str:
    """The supported fields and what each one is, on one line each (`P-9`).

    Built from `SUPPORTED_FIELDS` rather than written out here: the list a user reads and the set
    the validator enforces are the same fact, and two copies of it is how an editor comes to offer
    a field that is refused the moment it is used.
    """
    return "\n".join(f"%({field.name})s — {field.describes}" for field in SUPPORTED_FIELDS)


class TemplateEditor(QWidget):
    """A template input, the fields it accepts, and what the current one would write."""

    #: `str` — the template text changed. The surface embedding this asks the manager for a
    #: preview and hands the answer back to `show_preview`.
    template_changed = Signal(str)

    def __init__(self, template: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("templateEditor")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        caption = QLabel(TEMPLATE_LABEL, self)
        caption.setObjectName("templateCaption")
        layout.addWidget(caption)

        self._input = QLineEdit(template, self)
        self._input.setObjectName("outputTemplateInput")
        self._input.setAccessibleName(TEMPLATE_LABEL)
        self._input.setAccessibleDescription(
            "The name each download is saved under. Use a field such as %(title)s to stand for "
            "something the site tells us, and a / to make a subfolder."
        )
        self._input.setClearButtonEnabled(True)
        # **Named here because Qt does not name it** — see `CLEAR_LABEL`. `findChild` rather than
        # a stored reference: the button is `QLineEditIconButton`, a private class Qt creates as a
        # side effect of the line above, so this file can only reach it as the child it is.
        clear_button = self._input.findChild(QAbstractButton)
        if clear_button is not None:
            clear_button.setAccessibleName(CLEAR_LABEL)
            # Qt builds it `NoFocus` and the keyboard needs no button to do this, so the route is
            # declared rather than the control being made focusable — one more Tab stop that
            # duplicates a key every text field already answers is a cost, not a fix.
            route_is_elsewhere(clear_button, "Ctrl+A then Delete, in the field itself")
        # **Every keystroke**, which is what `P-23` costs and what it bought. `textEdited` rather
        # than `textChanged` so setting the text programmatically does not re-enter the surface
        # that set it.
        self._input.textEdited.connect(self.template_changed)
        caption.setBuddy(self._input)
        layout.addWidget(self._input)

        fields = QLabel(f"{FIELDS_LABEL}:\n{fields_text()}\n{SUBDIRECTORY_HINT}", self)
        fields.setObjectName("templateFields")
        fields.setAccessibleName(FIELDS_LABEL)
        fields.setWordWrap(True)
        # The list contains `%(title)s` and a slash and nothing this application did not author,
        # but it is set explicitly for `T016-R6`'s reason: a label's format is decided where the
        # label is made, not remembered later.
        fields.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(fields)

        self._preview_caption = QLabel(PREVIEW_LABEL, self)
        self._preview_caption.setObjectName("outputPreviewCaption")
        layout.addWidget(self._preview_caption)

        # **A read-only field, not a label** (`P-22`). Focusable, so it is a tab stop and can be
        # reviewed at the reader's pace; selectable, so the path can be copied; and read-only, so
        # the one place a path is decided stays the template above it.
        self._preview = QLineEdit(self)
        self._preview.setObjectName("outputPathPreview")
        self._preview.setReadOnly(True)
        self._preview.setAccessibleName(PREVIEW_LABEL)
        self._preview_caption.setBuddy(self._preview)
        layout.addWidget(self._preview)

        self._message = QLabel(self)
        self._message.setObjectName("templateMessage")
        self._message.setAccessibleName("Why this template cannot be used")
        self._message.setWordWrap(True)
        # A refusal can quote a rendered path, which is site metadata (`T016-R6`).
        self._message.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._message)

        QWidget.setTabOrder(self._input, self._preview)

    # --- the seam a surface embedding this uses ------------------------------------------

    @property
    def template(self) -> str:
        return self._input.text()

    def set_template(self, template: str) -> None:
        """Put text in the input **without** claiming the user typed it.

        `textEdited` does not fire for a programmatic change, which is deliberate: the caller that
        sets the text is the caller that will ask for the first preview, and a signal here would
        make it ask twice.
        """
        self._input.setText(template)

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
        """The keyboard order: the template, then the preview (`P-22`)."""
        return [self._input, self._preview]

    def show_preview(self, preview: OutputPreview) -> None:
        """Display one answer from `DownloadManager.preview_output_path`.

        The three states are drawn as three, and never mixed: a refusal empties the path field, an
        exact path carries no note, and a provisional one is labelled *intended* in the caption
        rather than annotated underneath — the difference between a promise and an intention is
        part of what the field is, so it belongs in the field's name.
        """
        self._preview.setText(preview.path)
        self._preview_caption.setText(
            PROVISIONAL_LABEL if preview.provisional is not None else PREVIEW_LABEL
        )
        self._message.setText(preview.refusal or preview.provisional or "")
        # **The state reaches a screen reader too** (`NFR-005`). A caption changing from "will be"
        # to "is intended to be" is a visual difference; the accessible description is where a user
        # who cannot see the caption hears the same distinction.
        if preview.is_refused:
            spoken = f"No path: {preview.refusal}"
        elif preview.provisional is not None:
            spoken = f"{preview.path}. {preview.provisional}"
        else:
            spoken = preview.path
        self._preview.setAccessibleDescription(spoken)
        self._preview_caption.setAccessibleName(self._preview_caption.text())
