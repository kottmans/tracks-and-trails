"""The diagnostics view (`T-084`, `REQ-019`).

`REQ-019` asks for the diagnostic output *copyable for a bug report*, so the criteria asserted here
are that what is on screen matches the file character for character, that copying yields the whole
of it, and that a job with no log says so instead of showing an empty box.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from tracks_and_trails.core.logging import JOB_LOG_DIRECTORY
from tracks_and_trails.ui.log_view import (
    EMPTY_TEXT,
    MAX_DISPLAY_BYTES,
    LogView,
    read_job_log,
)

COOKIE_PATH = "/home/sean/.mozilla/firefox/ab12.default-release/cookies.sqlite"


def write_log(directory: Path, job_id: str, body: str) -> Path:
    path = directory / JOB_LOG_DIRECTORY / f"{job_id}.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_the_view_shows_the_file_character_for_character(
    qapp: QApplication, tmp_path: Path
) -> None:
    """**The whole contract** (`NFR-006`, `DAT-003`).

    The body includes a cookie path yt-dlp emitted, because that is precisely the text a view that
    "helpfully" re-redacted would remove — and the copied text would then disagree with the file a
    maintainer asked the user to attach.
    """
    body = (
        "2026-08-01 12:00:00,000 INFO     tracksandtrails.ytdlp [generic] Extracting URL\n"
        f"2026-08-01 12:00:01,000 ERROR    tracksandtrails.ytdlp ERROR: cannot read {COOKIE_PATH}\n"
    )
    write_log(tmp_path, "job-1", body)

    view = LogView("job-1", directory=tmp_path)

    assert view.text() == body
    assert COOKIE_PATH in view.text()


def test_copying_yields_the_whole_log(qapp: QApplication, tmp_path: Path) -> None:
    """A copy that quietly took the selection, or one line, is a bug report with the cause cut."""
    body = "".join(f"line {index}\n" for index in range(200))
    write_log(tmp_path, "job-1", body)
    view = LogView("job-1", directory=tmp_path)

    copied = view.copy_to_clipboard()

    assert copied == body
    assert "line 0" in copied
    assert "line 199" in copied


def test_a_job_with_no_log_says_so_and_offers_nothing_to_copy(
    qapp: QApplication, tmp_path: Path
) -> None:
    """A job that has not started has nothing to say. An empty box and a failed read look alike."""
    view = LogView("never-ran", directory=tmp_path)

    assert view.text() == EMPTY_TEXT
    assert not view.has_log()
    assert not view.copy_button.isEnabled(), (
        "the placeholder sentence would have been copied into somebody's bug report"
    )
    assert view.focus_chain() == [view.text_widget]


def test_a_populated_log_puts_the_copy_button_in_the_keyboard_order(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`NFR-005`, `T-060`'s per-state rule: the two states are asserted separately."""
    write_log(tmp_path, "job-1", "something happened\n")
    view = LogView("job-1", directory=tmp_path)

    assert view.copy_button.isEnabled()
    assert view.focus_chain() == [view.text_widget, view.copy_button]


def test_the_text_is_selectable_from_the_keyboard(qapp: QApplication, tmp_path: Path) -> None:
    """Read-only, **not disabled**. A disabled text edit cannot be focused, so its contents cannot
    be selected without a mouse — and copyable that needs a mouse is not copyable (`NFR-005`)."""
    write_log(tmp_path, "job-1", "something happened\n")
    view = LogView("job-1", directory=tmp_path)

    assert view.text_widget.isReadOnly()
    assert view.text_widget.isEnabled()


def test_a_log_larger_than_the_display_cap_keeps_its_tail(
    qapp: QApplication, tmp_path: Path
) -> None:
    """The **end**, not the beginning: a log is read to find out how something finished."""
    body = "".join(f"line {index:06d} {'x' * 100}\n" for index in range(20000))
    assert len(body.encode()) > MAX_DISPLAY_BYTES
    write_log(tmp_path, "job-1", body)

    shown = read_job_log("job-1", tmp_path)

    assert "line 019999" in shown
    assert "line 000000" not in shown
    assert len(shown.encode()) <= MAX_DISPLAY_BYTES + 200
    assert shown.startswith("…"), "truncation happened without saying so"


def test_a_truncated_log_never_opens_mid_line(qapp: QApplication, tmp_path: Path) -> None:
    """A view opening halfway through a line reads as corruption rather than as truncation."""
    body = "".join(f"line {index:06d} {'x' * 100}\n" for index in range(20000))
    write_log(tmp_path, "job-1", body)

    shown = read_job_log("job-1", tmp_path)
    first_real_line = shown.splitlines()[1]

    assert first_real_line.startswith("line "), f"opened mid-line: {first_real_line[:40]!r}"


def test_undecodable_bytes_do_not_lose_the_lines_around_them(
    qapp: QApplication, tmp_path: Path
) -> None:
    """Rotation can cut a multi-byte character in half. Refusing to decode would throw away the
    diagnostic in order to protect the display of it."""
    path = tmp_path / JOB_LOG_DIRECTORY / "job-1.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"before\n\xff\xfe broken\nafter\n")

    shown = read_job_log("job-1", tmp_path)

    assert "before" in shown
    assert "after" in shown


def test_an_unreadable_log_is_absent_rather_than_an_exception(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`read_job_log` never raises: a permission change is not something the user can act on from
    a Qt slot, and an exception there is printed and swallowed."""
    path = write_log(tmp_path, "job-1", "text\n")
    path.chmod(0o000)
    try:
        assert read_job_log("job-1", tmp_path) in ("", "text\n")  # root can still read it
    finally:
        path.chmod(0o644)


def test_refresh_picks_up_lines_written_after_the_view_was_built(
    qapp: QApplication, tmp_path: Path
) -> None:
    """The file grows while a job runs, which is why expanding the box re-reads it."""
    write_log(tmp_path, "job-1", "first\n")
    view = LogView("job-1", directory=tmp_path)
    assert "second" not in view.text()

    write_log(tmp_path, "job-1", "first\nsecond\n")
    view.refresh()

    assert "second" in view.text()
    assert view.copy_button.isEnabled()
