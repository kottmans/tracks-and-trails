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

## What is on screen is what is in the file

Character for character, and this view filters nothing: re-redacting here would make the copied text
disagree with the file a maintainer asked the user to attach.

**The redaction already happened when the line was written, and it is origin-agnostic** — accepted
`DAT-003`, whose `T-049` amendment says every log this application *emits* is redacted whatever the
provenance of the text inside it. `T-084` briefly made it provenance-aware and that was `T084-R1`, a
Critical: with no production caller registering a secret, the scheme left yt-dlp's lines unredacted
entirely, so a diagnostic echoing the source URL wrote its credentials here. `DAT-004`, which argued
for that reading, is withdrawn.

The cost is real and is `DAT-003`'s choice rather than this module's: a user reading their own log
will not see a cookie path yt-dlp named. `NFR-006`'s promise is kept at the **other** sink — the
database stores the extractor's message verbatim (`T-014`), and `T-084`'s amended criterion asserts
the two sinks against each other so neither drifts into the other.

## Copy reads the file, not this view

`copy_to_clipboard` re-reads the artifact rather than taking what is rendered. The rendering is
capped so the GUI thread never blocks; the clipboard is not, because `REQ-019` promises the file
exactly and the omitted beginning is where the session header lives. That was `T084-R2`.
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


def read_whole_job_log(job_id: str, directory: Path | None = None) -> str | None:
    """**The whole file**, or `None` if it could not be read (`T084-R2`).

    Separate from `read_job_log` because the two callers want different things and conflating them
    lost the thing that mattered. The **view** is capped so the GUI thread never blocks on a large
    read; **Copy** must produce the file, because `REQ-019` says so in as many words — *"What is
    copied is the file exactly"* — and the omitted beginning is where the session header and the
    first extractor decisions live, which is exactly what a bug report is opened about.

    Copying the capped rendering was `T084-R2`. For a log past the cap the clipboard lost its
    beginning, and for a single long line it could contain nothing but the truncation notice.

    **Unbounded is safe here** only because the artifact is bounded: `MAX_JOB_LOG_BYTES` caps the
    live file at 2 MiB. This reads that file, not the rotated backup.

    `None` rather than `""`: the caller must be able to say *could not read* rather than silently
    copying an empty string, which is indistinguishable from a job that logged nothing.
    """
    path = job_log_path(job_id, directory)
    try:
        return path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return None


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

    def status_text(self) -> str:
        """What the label beside Copy last said. **The only report of a refused copy.**"""
        return self._status.text()

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
        """Put **the file** on the clipboard and say so. Returns what was copied.

        **Re-read here rather than taken from the widget** (`T084-R2`). What is on screen is the
        capped tail; what `REQ-019` promises is the file. Taking `self.text()` meant a long log was
        copied without its beginning — the session header and the first extractor decisions — and a
        single very long line could copy nothing but the truncation notice.

        Returned as well as copied because a test asserting only the clipboard would depend on a
        clipboard existing, which is not true of every CI image; and confirming in the label
        matters because a copy that silently does nothing is indistinguishable from one that worked
        (`NFR-006`'s posture, at the smallest possible scale).
        """
        body = read_whole_job_log(self._job_id, self._directory)
        if body is None:
            # **Refused, not approximated.** Copying the rendered tail as a fallback would put a
            # truncated log into a bug report while telling the user it was copied.
            self._status.setText("The log file could not be read, so nothing was copied.")
            return ""
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(body)
        self._status.setText(f"Copied {len(body.splitlines())} lines.")
        return body


def build_log_view(job_id: str, directory: Path | None = None) -> LogView:
    """Construct the view. A named function for `build_queue_view`'s reason."""
    return LogView(job_id, directory=directory)
