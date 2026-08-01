"""One job's diagnostics, on screen and copyable (`T-084`, `REQ-019`).

## What this shows, and why it is worth a surface of its own

`REQ-019` asks for *the yt-dlp diagnostic output for that job, copyable for a bug report*. The
error message on the detail pane is one sentence — `NFR-006` makes sure it is the extractor's own
sentence — but a bug report needs the lines **before** the failure, which is what the job log has
and nothing else in this application does.

## Read from the file, not from a signal

The log is written by the parent's logging handler as records arrive (`T-038`), and this reads the
file that handler is writing. That is deliberate: a second in-memory copy fed by a signal would
diverge from what the user actually copies, and it is the file a maintainer will ask them to
attach. **The file is the artefact; this is a window onto it.**

Reading is capped — see `MAX_DISPLAY_BYTES`. `MAX_JOB_LOG_BYTES` bounds the file, so this is not
the safety net; it is about not stalling the GUI thread on a multi-megabyte read.

## Verbatim within the provenance boundary

What is on screen is what is in the file, character for character. The redaction happened when the
line was written and it happened by **provenance**, not by shape (`DAT-003` as amended by `T-049`):
values this application supplied are gone; prose yt-dlp emitted is intact. Nothing here filters
further, because a view that re-redacted would make the copied text disagree with the file.

**One thing for a maintainer to rule on.** `DAT-003` says the decision reopens if the database or
its diagnostics stop being local and user-owned — and names *"a bug report attaching it"* as one of
the triggers. This view exists to make exactly that easy. The boundary is implemented as `DAT-003`
specifies and this note is the flag, not a unilateral change: see `T-084`'s record.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core.logging import job_log_path

#: How much of the file is rendered. The file is already bounded by `MAX_JOB_LOG_BYTES`; this is
#: about the **GUI thread**, which must not block on a read (`ARC-005`'s posture, applied to a
#: file instead of to SQLite).
#:
#: The **tail** is read, not the head: a log is read to find out how something ended.
MAX_DISPLAY_BYTES: Final = 512 * 1024

#: Shown when the job has no log file. Not an error — a job that has not started yet has nothing
#: to say, and so does one whose log the OS reclaimed from `user_cache_dir` (`NFR-004`).
EMPTY_TEXT: Final = "No diagnostics recorded for this download yet."

TRUNCATION_NOTICE: Final = (
    "… earlier lines are in the log file itself; the most recent {kib} KiB are shown here.\n"
)


def read_job_log(job_id: str, directory: Path | None = None) -> str:
    """The tail of `job_id`'s log, or `""` if it has none. **Never raises.**

    A missing file is the ordinary case, and every other `OSError` — a permission change, a
    reclaimed cache directory — is one the user cannot act on from here and must not lose a window
    over.

    Decoded with `errors="replace"`: a log truncated mid-character by rotation, or one carrying
    bytes from a locale this process does not share, still shows every line around the damage.
    Refusing to decode would throw away the diagnostic to protect the display of it.
    """
    path = job_log_path(job_id, directory)
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > MAX_DISPLAY_BYTES:
                handle.seek(size - MAX_DISPLAY_BYTES)
                body = handle.read().decode("utf-8", errors="replace")
                notice = TRUNCATION_NOTICE.format(kib=MAX_DISPLAY_BYTES // 1024)
                # Dropped up to the first newline, so the view never opens mid-line — which reads
                # as corruption rather than as truncation.
                _, _, remainder = body.partition("\n")
                return notice + remainder
            return handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


class LogView(QWidget):
    """A read-only view of one job's log, with a button that copies all of it."""

    def __init__(
        self,
        job_id: str,
        *,
        directory: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("logView")
        self.setAccessibleName("Diagnostics")
        self._job_id = job_id
        self._directory = directory

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._text = QPlainTextEdit(self)
        self._text.setObjectName("logText")
        self._text.setReadOnly(True)
        # Read-only but **not** disabled: a disabled text edit cannot be focused, so its contents
        # cannot be selected with the keyboard — and "copyable" that requires a mouse is not
        # copyable under `NFR-005`.
        self._text.setAccessibleName("Download diagnostics")
        self._text.setAccessibleDescription(
            "The diagnostic output recorded for this download, for including in a bug report."
        )
        # Fixed-pitch, because yt-dlp's output is column-aligned and proportional type destroys it.
        self._text.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self._text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._text)

        controls = QHBoxLayout()
        self._copy = QPushButton("&Copy diagnostics", self)
        self._copy.setObjectName("copyLogButton")
        self._copy.setAccessibleName("Copy diagnostics")
        self._copy.setToolTip(
            "Copy everything shown here to the clipboard, ready to paste into a bug report."
        )
        self._copy.clicked.connect(self.copy_to_clipboard)
        controls.addWidget(self._copy)

        self._status = QLabel("", self)
        self._status.setObjectName("logStatus")
        self._status.setAccessibleName("Copy result")
        controls.addWidget(self._status)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.refresh()

    @property
    def job_id(self) -> str:
        return self._job_id

    @property
    def text_widget(self) -> QPlainTextEdit:
        return self._text

    @property
    def copy_button(self) -> QPushButton:
        return self._copy

    def text(self) -> str:
        """What is on screen, which is what `copy_to_clipboard` puts on the clipboard."""
        return self._text.toPlainText()

    def has_log(self) -> bool:
        return bool(read_job_log(self._job_id, self._directory))

    def focus_chain(self) -> list[QWidget]:
        """The keyboard order for this view (`NFR-005`, `T-060`'s per-state rule).

        The copy button is dropped when there is nothing to copy — it is disabled then, and a
        disabled control in the tab order is a stop that does nothing.
        """
        return [self._text, self._copy] if self._copy.isEnabled() else [self._text]

    def refresh(self) -> None:
        """Re-read the file.

        The scroll position is not preserved. A log grows at the end and is read to find out how
        something finished, so this follows the tail — restoring an old position would leave a user
        watching a stale part of a file that is still being written.
        """
        body = read_job_log(self._job_id, self._directory)
        self._text.setPlainText(body or EMPTY_TEXT)
        self._text.moveCursor(self._text.textCursor().MoveOperation.End)
        # Nothing to copy is a disabled button rather than a button that copies a placeholder
        # sentence into somebody's bug report.
        self._copy.setEnabled(bool(body))
        self._status.setText("")

    def copy_to_clipboard(self) -> str:
        """Put the whole log on the clipboard and say so. Returns what was copied.

        Returned as well as copied because a test asserting only the clipboard would depend on a
        clipboard existing, which is not true of every CI image; and confirming in the label
        matters because a copy that silently does nothing is indistinguishable from one that
        worked (`NFR-006`'s posture, at the smallest possible scale).
        """
        body = self.text()
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(body)
        self._status.setText(f"Copied {len(body.splitlines())} lines.")
        return body


def build_log_view(job_id: str, directory: Path | None = None) -> LogView:
    """Construct the view. A named function for `build_queue_view`'s reason."""
    return LogView(job_id, directory=directory)
