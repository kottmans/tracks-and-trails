"""Open and Show-in-folder, attached to a table (`T-086`, `REQ-021`).

`test_reveal.py` holds the argv and refusal criteria, which need no Qt. This file holds the half
that does: **that the actions are on both tables `REQ-021` names**, that they act on the row the
user selected, and that a refusal reaches the user rather than the console.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication

from tests.ui.test_queue_view import FakeQueue
from tests.ui.test_reveal import RecordingSpawner
from tracks_and_trails.core.models import DownloadRequest, Job
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.persistence.repositories import HistoryEntry
from tracks_and_trails.ui.file_actions import OPEN_TEXT, REVEAL_TEXT, FileActions
from tracks_and_trails.ui.history_view import build_history_view
from tracks_and_trails.ui.queue_view import QueueView


class FakeHistory:
    def __init__(self, entries: list[HistoryEntry]) -> None:
        self._entries = entries

    def all_entries(self) -> list[HistoryEntry]:
        return list(self._entries)


def an_entry(entry_id: str = "job-1", output_path: str | None = None) -> HistoryEntry:
    return HistoryEntry(
        id=entry_id,
        url="https://example.invalid/clip",
        title="A clip",
        output_path=output_path,
        format_used="137+140",
        bytes_total=1024,
        completed_at=datetime(2026, 7, 30, 14, 5, tzinfo=UTC),
    )


@pytest.fixture
def downloads(tmp_path: Path) -> Path:
    directory = tmp_path / "Downloads"
    directory.mkdir()
    return directory


class Attached:
    """A history view with `FileActions` on it, plus everything a test needs to inspect."""

    def __init__(self, *, entries: list[HistoryEntry], downloads: Path) -> None:
        self.view = build_history_view(FakeHistory(entries))
        self.spawner = RecordingSpawner()
        self.reported: list[str] = []
        self.actions = FileActions(
            table=self.view.table,
            selected_path=self.view.selected_path,
            output_directory=lambda: downloads,
            report=self.reported.append,
            run=self.spawner,
        )

    def select_row(self, row: int) -> None:
        self.view.table.selectRow(row)


def test_the_actions_are_offered_only_once_a_row_with_a_path_is_selected(
    qapp: QApplication, downloads: Path
) -> None:
    """Enabled state follows the selection, and a record with no path offers nothing.

    A record can have `output_path` `NULL` — `T-085` made every one of those columns nullable —
    and offering Open for it would produce a refusal about a file named after the placeholder.
    """
    written = downloads / "clip.mp4"
    written.write_bytes(b"")
    attached = Attached(
        entries=[an_entry("with-path", str(written)), an_entry("no-path", None)],
        downloads=downloads,
    )

    assert not attached.actions.open_action.isEnabled(), "offered with nothing selected"

    attached.select_row(0)
    assert attached.actions.open_action.isEnabled()
    assert attached.actions.reveal_action.isEnabled()

    attached.select_row(1)
    assert not attached.actions.open_action.isEnabled(), "offered for a record with no path"
    assert not attached.actions.reveal_action.isEnabled()


def test_triggering_open_acts_on_the_selected_row(qapp: QApplication, downloads: Path) -> None:
    """**Through `trigger()`, not by calling the handler** — a disabled action's `trigger` is a
    no-op, so this fails if the enabled state and the selection ever disagree."""
    first = downloads / "first.mp4"
    second = downloads / "second.mp4"
    for path in (first, second):
        path.write_bytes(b"")
    attached = Attached(
        entries=[an_entry("a", str(first)), an_entry("b", str(second))], downloads=downloads
    )

    attached.select_row(1)
    attached.actions.open_action.trigger()

    assert attached.reported == []
    assert attached.spawner.argv == ["xdg-open", str(second)], (
        f"opened {attached.spawner.argv}, which is not the row the user selected"
    )


def test_reveal_asks_the_file_manager_to_show_the_file_rather_than_opening_it(
    qapp: QApplication, downloads: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**Show in folder must not be Open wired twice.**

    The two actions differ only in which function they call, so a copy-paste that pointed both at
    `open_file` would leave every other test in this file passing while the menu item silently
    played the video instead of showing where it is. A mutation doing exactly that survived until
    this test existed.

    `dbus_available` is pinned false so the expected argv is the machine-independent fallback —
    the folder, not the file, which is what makes the two distinguishable here.
    """
    monkeypatch.setattr("tracks_and_trails.ui.reveal.dbus_available", lambda: False)
    written = downloads / "clip.mp4"
    written.write_bytes(b"")
    attached = Attached(entries=[an_entry("a", str(written))], downloads=downloads)
    attached.select_row(0)

    attached.actions.reveal_action.trigger()

    assert attached.spawner.argv == ["xdg-open", str(downloads)], (
        "Show in folder did not reveal — this is the argv Open would build if both actions were "
        "wired to the same call"
    )


def test_reveal_and_open_do_different_things(
    qapp: QApplication, downloads: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stated as a difference, so neither action can drift onto the other's implementation."""
    monkeypatch.setattr("tracks_and_trails.ui.reveal.dbus_available", lambda: False)
    written = downloads / "clip.mp4"
    written.write_bytes(b"")
    attached = Attached(entries=[an_entry("a", str(written))], downloads=downloads)
    attached.select_row(0)

    attached.actions.open_selected()
    attached.actions.reveal_selected()

    opened, revealed = (call[0] for call in attached.spawner.calls)
    assert opened != revealed
    assert opened[-1] == str(written)
    assert revealed[-1] == str(downloads)


def test_a_refusal_reaches_the_user_rather_than_the_console(
    qapp: QApplication, downloads: Path
) -> None:
    """`NFR-006` at this surface. The file is recorded and gone, which is the ordinary case."""
    attached = Attached(entries=[an_entry("a", str(downloads / "moved.mp4"))], downloads=downloads)
    attached.select_row(0)

    refusal = attached.actions.open_selected()

    assert refusal is not None
    assert attached.reported == [refusal.reason]
    assert "no longer there" in attached.reported[0]


def test_a_recorded_path_outside_the_download_folder_is_refused_at_the_moment_of_use(
    qapp: QApplication, downloads: Path, tmp_path: Path
) -> None:
    """**The stored path is data, not a permission** (`SEC-001`).

    A `history` row outlives the setting that produced it, and `T-079` lets the user change where
    downloads go. A row written when the folder was elsewhere must not open a file elsewhere now.
    """
    outside = tmp_path / "elsewhere.mp4"
    outside.write_bytes(b"")
    attached = Attached(entries=[an_entry("a", str(outside))], downloads=downloads)
    attached.select_row(0)

    refusal = attached.actions.reveal_selected()

    assert refusal is not None
    assert "outside the download folder" in refusal.reason


def test_the_output_directory_is_read_at_the_moment_of_use(
    qapp: QApplication, tmp_path: Path
) -> None:
    """Captured rather than read, and a folder change would be checked against a stale boundary."""
    old = tmp_path / "old"
    new = tmp_path / "new"
    for directory in (old, new):
        directory.mkdir()
    written = new / "clip.mp4"
    written.write_bytes(b"")

    current = old
    view = build_history_view(FakeHistory([an_entry("a", str(written))]))
    reported: list[str] = []
    spawner = RecordingSpawner()
    actions = FileActions(
        table=view.table,
        selected_path=view.selected_path,
        output_directory=lambda: current,
        report=reported.append,
        run=spawner,
    )
    view.table.selectRow(0)

    refusal = actions.open_selected()
    assert refusal is not None, "opened a file outside the folder in force"
    assert "outside the download folder" in refusal.reason

    current = new

    assert actions.open_selected() is None, "the boundary was captured rather than re-read"
    assert spawner.argv == ["xdg-open", str(written)]


def test_the_context_menu_carries_both_actions(qapp: QApplication, downloads: Path) -> None:
    """`REQ-021`'s two verbs, on the menu the table raises — including from the keyboard.

    `CustomContextMenu` is asserted rather than the key press: Qt routes the Menu key and
    Shift+F10 to `customContextMenuRequested` under that policy, while `DefaultContextMenu` with
    an overridden `contextMenuEvent` would answer the mouse and not the keyboard.
    """
    written = downloads / "clip.mp4"
    written.write_bytes(b"")
    attached = Attached(entries=[an_entry("a", str(written))], downloads=downloads)

    assert attached.view.table.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu

    menu = attached.actions._show_menu(QPoint(0, 0))
    try:
        assert [action.text() for action in menu.actions()] == [OPEN_TEXT, REVEAL_TEXT]
    finally:
        menu.close()


def test_a_double_click_opens(qapp: QApplication, downloads: Path) -> None:
    """What a table of files is expected to do, and it is wired to the same call as the action."""
    written = downloads / "clip.mp4"
    written.write_bytes(b"")
    attached = Attached(entries=[an_entry("a", str(written))], downloads=downloads)
    attached.select_row(0)

    attached.view.table.doubleClicked.emit(attached.view.model.index(0, 0))

    assert attached.reported == []
    assert attached.spawner.argv == ["xdg-open", str(written)]


def test_the_queue_view_offers_the_actions_for_a_finished_job_and_not_a_running_one(
    qapp: QApplication, downloads: Path
) -> None:
    """**`REQ-021` names the queue view too**, so the wiring is asserted there and not only on
    history.

    A job that has not finished has no `output_path` — `T-046` writes into a staging directory and
    the final name does not exist until the download succeeds — so the actions stay disabled for
    it. That is the correct answer rather than a limitation: there is no file yet to open.
    """
    written = downloads / "clip.mp4"
    written.write_bytes(b"")
    request = DownloadRequest(
        url="https://example.invalid/clip",
        output_directory=str(downloads),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )
    queue = FakeQueue()
    queue.add(Job(id="running", url=request.url, request=request))
    queue.add(Job(id="done", url=request.url, request=request, output_path=str(written)))
    manager = DownloadManager(queue)
    view = QueueView(jobs=queue, manager=manager)
    spawner = RecordingSpawner()
    try:
        actions = FileActions(
            table=view.table,
            selected_path=view.selected_path,
            output_directory=lambda: downloads,
            report=lambda message: None,
            run=spawner,
        )

        assert view.select("running")
        assert not actions.open_action.isEnabled(), "offered for a job with nothing written yet"

        assert view.select("done")
        assert actions.open_action.isEnabled()
        actions.open_action.trigger()
        assert spawner.argv == ["xdg-open", str(written)]
    finally:
        view.detach()
        manager.shutdown()


def test_the_history_view_reports_a_missing_path_as_absent_not_as_the_placeholder(
    qapp: QApplication,
) -> None:
    """`path_for` must not be `text_at(PATH_COLUMN)`.

    That renders the em-dash placeholder for a null path, and handing it to `open_file` would
    report that a file named "—" is missing — a true sentence about the wrong thing.
    """
    view = build_history_view(FakeHistory([an_entry("a", None)]))
    view.table.selectRow(0)

    assert view.selected_path() is None
    assert view.model.path_for("a") is None
