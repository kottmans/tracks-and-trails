"""The format table as a window, for a download that is already queued (`T-315`).

**Why this exists beside `FormatPanel` rather than instead of it.** `T-312` made the staging list's
format table a *page* of the add dialog, because the alternative there was a modal opened from a
modal — `UX-007`'s `P-1`. The queue is not a modal, so that objection does not reach it, and the
queue has no page stack to swap: it is one list inside the main window. A dialog is what a window
opens.

**The table itself is shared, and that is the point.** `FormatTable` owns the two lists, the
choosing rules, the merge refusal and the *Chosen* summary; this adds a frame, a way to say yes and
a way to say no. A second table drawn here would be a second opinion about what a format is.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core.models import FormatInfo
from tracks_and_trails.ui.format_selection import FormatSelection
from tracks_and_trails.ui.format_table import FormatTable

#: What the accept button says. **A statement of what pressing it does**, not `OK` — the same
#: reason `RowPanel`'s way out is named for its effect (`NFR-006`).
USE_TEXT = "Use these formats"


class FormatDialog(QDialog):
    """Pick the streams for one queued download (`REQ-003`, `REQ-008`)."""

    def __init__(
        self,
        formats: Sequence[FormatInfo],
        *,
        title: str,
        ffmpeg_available: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("formatDialog")
        self.setWindowTitle("Choose formats")
        self.setModal(True)

        layout = QVBoxLayout(self)

        # **The download this is about, said on the surface that changes it.** A dialog opened
        # from a row loses the row: `T203-R1` is this project's record of a shared surface failing
        # to say which item it meant, and a window has even less context than a bar does.
        self._subject = QLabel(title, self)
        self._subject.setObjectName("formatDialogSubject")
        self._subject.setWordWrap(True)
        # `T016-R6`'s rule: text from an extractor is never drawn as markup.
        self._subject.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._subject)

        self._table = FormatTable(formats, self, ffmpeg_available=ffmpeg_available)
        self._table.selection_changed.connect(self._on_selection)
        layout.addWidget(self._table, 1)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._buttons.setObjectName("formatDialogButtons")
        accept = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        accept.setObjectName("formatDialogUse")
        accept.setText(USE_TEXT)
        # **Nothing is chosen yet, so there is nothing to use** (`UX-005` §5: a control is not
        # offered where it would be refused). Enabled by `_on_selection` the moment the selection
        # names a download — which for a merge means *both* halves, not the first.
        accept.setEnabled(False)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._selection = FormatSelection()

    def _on_selection(self, selection: object) -> None:
        if not isinstance(selection, FormatSelection):
            return
        self._selection = selection
        accept = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        accept.setEnabled(selection.is_complete)

    @property
    def table(self) -> FormatTable:
        """The table itself, so a caller can drive it the way a user does."""
        return self._table

    def selection(self) -> FormatSelection:
        """What is chosen. Incomplete until both halves of a merge are named."""
        return self._selection

    # Qt's override name, hence the camelCase.
    def sizeHint(self) -> QSize:
        """Wide enough for two lists, and no wider than the screen (`T-310`, `T-312`).

        **The table's own hint, asked rather than assumed.** `T-310` measured two lists at roughly
        1100px before a column truncates, and `T310-R2` is the record of what a constant costs
        here: five wrong answers in a row, each a horizontal scrollbar on a table that had asked
        for exactly enough. The screen bound is `_widen_for`'s, for its reason — a window wider
        than the display is one whose buttons cannot be reached.
        """
        wanted = super().sizeHint()
        available = self.screen().availableGeometry()
        return QSize(
            min(wanted.width(), available.width()), min(wanted.height(), available.height())
        )
