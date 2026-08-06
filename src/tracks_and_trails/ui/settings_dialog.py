"""The Settings screen (`REQ-023`), which exists so far to hold one data control (`T-170`).

**This is a shell, deliberately.** `T-146` extends it with the settings `REQ-023` names — output
directory, default preset, concurrency, template, ffmpeg location, network options, cookie source,
theme. None of those are here. What is here is the one action that had nowhere else to go once the
History tab was removed: **Clear download records**.

## Why a data control lives in Settings rather than on the toolbar

`Clear history` was a toolbar verb because the toolbar's rule is that every verb on it names the
list it empties (`UX-005` 2.1), and there was a visible list to name. `T-169` removed the list. A
toolbar verb for an invisible ledger would be a button that empties something the user cannot see,
which is the shape `UX-005` §5 objects to — and it would sit beside `Clear finished`, which clears
**queue rows** and is a different action entirely.

Settings is where an application puts *"manage the data I keep about you"*, and that is what this
is.

## The promise the confirmation carries

`DAT-005`'s boundary is the reason this dialog is careful: **a record is not a file**. The
confirmation names the exact count and says outright that downloaded files are not deleted. The
count is in the question because a user reaching this has usually not counted what they have, and
the number is what tells them how much they are about to lose.

**Nothing is asked when there is nothing to clear.** `T-170` requires the empty action to be
disabled or to ask no question; it is disabled, because a dialog that opens only to say "there is
nothing here" is a dialog that taught the user not to read them.
"""

from collections.abc import Callable
from typing import Final, Protocol

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

__all__ = [
    "CLEAR_RECORDS_LABEL",
    "RECORDS_KEEP_FILES",
    "RecordsReader",
    "SettingsDialog",
    "clear_records_question",
]

#: The verb, in one place: the button, its accessible name and the tests all read it from here.
CLEAR_RECORDS_LABEL: Final = "Clear download records"

#: `DAT-005` §3's promise, carried wherever the action is (`T-170`).
#:
#: **It says *records*, not *history*.** The noun is the distinction this promise exists to draw,
#: and `DAT-005`'s 2026-08-06 amendment renamed the action for exactly that reason: with no visible
#: list, *history* names a feature the user can no longer see, while *records* names what is
#: actually emptied.
RECORDS_KEEP_FILES: Final = "Your downloaded files are not deleted."


def clear_records_question(count: int) -> str:
    """The confirmation, naming its own count (`DAT-005` §4, `T-170`).

    Grouped, because `1284` is a number to read and `1,284` is a quantity to feel. Singular is
    written out: "1 records" is the tell that a message was assembled rather than composed.

    *(Adapted from `main_window.clear_question`, which asked the same thing about the visible list.
    The wording moved with the action rather than being rewritten from nothing, so the reasoning
    `T-144` put into it is not lost.)*
    """
    if count == 1:
        return "Clear the one download record?"
    return f"Clear all {count:,} download records?"


class RecordsReader(Protocol):
    """How many completions the ledger holds.

    **A count and nothing else**, which is the whole of what a screen with no list needs. The
    protocol is here rather than `persistence` for `QueueReader`'s reason: the UI states what it
    needs, and the repository happens to satisfy it.
    """

    def count(self) -> int: ...


class SettingsDialog(QDialog):
    """One screen, one section, one control — and room for `T-146`'s settings beside it."""

    def __init__(
        self,
        *,
        records: RecordsReader,
        on_clear_records: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._records = records
        self._on_clear_records = on_clear_records

        self.setObjectName("settingsDialog")
        self.setWindowTitle("Settings")

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_data_section())
        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.setObjectName("settingsButtons")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_data_section(self) -> QWidget:
        box = QGroupBox("Downloads and data", self)
        box.setObjectName("dataSection")
        layout = QVBoxLayout(box)

        explanation = QLabel(
            "Tracks & Trails keeps a private record of what you have downloaded, so it can warn "
            "you before downloading the same URL twice. " + RECORDS_KEEP_FILES,
            box,
        )
        explanation.setObjectName("recordsExplanation")
        # `T016-R6`: every label showing text this application did not author is PlainText. This
        # one it did author, and it is set anyway so the rule has no exceptions to remember.
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self._clear = QPushButton(CLEAR_RECORDS_LABEL, box)
        self._clear.setObjectName("clearRecordsButton")
        self._clear.setAccessibleName(CLEAR_RECORDS_LABEL)
        self._clear.setAccessibleDescription(
            "Empty the private record of completed downloads. " + RECORDS_KEEP_FILES
        )
        self._clear.clicked.connect(self.clear_records_asked_for)
        layout.addWidget(self._clear)

        self.refresh()
        return box

    def refresh(self) -> None:
        """Enable the verb only while it has something to do (`UX-005` §5).

        Nothing is drawn disabled *and offered*; this is the other half of that rule — a control
        that would be refused is not presented as available. It is disabled rather than hidden
        because the section's explanation is still true when the ledger is empty, and a button that
        comes and goes is harder to find than one that greys.
        """
        self._clear.setEnabled(self._records.count() > 0)

    def clear_records_asked_for(self) -> QMessageBox | None:
        """Ask, then clear. Returns the dialog so a test can answer it (`T-144`'s shape).

        Modal and returned rather than `exec()`-ed inline: a test drives the same code path the
        user does instead of a second one written for it, which is how `T-125`'s confirmation is
        asserted.
        """
        count = self._records.count()
        if count <= 0:
            return None

        question = QMessageBox(self)
        question.setObjectName("clearRecordsConfirm")
        question.setIcon(QMessageBox.Icon.Question)
        question.setWindowTitle(CLEAR_RECORDS_LABEL)
        question.setText(clear_records_question(count))
        # **The promise is in the dialog that acts, not only in the section above it** (`DAT-005`
        # §3). Someone who reached a confirmation is deciding right now, and this is the sentence
        # that decides it.
        question.setInformativeText(RECORDS_KEEP_FILES)
        question.setStandardButtons(
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes
        )
        question.setDefaultButton(QMessageBox.StandardButton.Cancel)

        def act(button: object) -> None:
            if question.standardButton(button) == QMessageBox.StandardButton.Yes:  # type: ignore[arg-type]
                self._on_clear_records()

        question.buttonClicked.connect(act)
        question.open()
        return question
