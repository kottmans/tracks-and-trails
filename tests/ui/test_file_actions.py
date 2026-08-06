"""Open and Show-in-folder, attached to a table (`T-086`, `REQ-021`).

`test_reveal.py` holds the argv and refusal criteria, which need no Qt. This file holds the half
that does: **that the actions are on both tables `REQ-021` names**, that they act on the row the
user selected, and that a refusal reaches the user rather than the console.
"""

from __future__ import annotations

import sys
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
from tracks_and_trails.ui.queue_view import QueueView
from tracks_and_trails.ui.reveal import open_command, reveal_command


class PathList:
    """A list of rows carrying paths, and nothing else `FileActions` asks of a host.

    **`FileActions` is a component, and this is what it actually needs**: an item view to attach
    to, and a callable saying which path is selected. These tests used to host it on the History
    view, which was convenient rather than meaningful — and when `T-170` deleted that view the
    tests for `T-086`'s containment nearly went with it. Hosting them on the queue instead would
    only move the coupling to the next surface that might be removed.
    """

    def __init__(self, entries: list[HistoryEntry]) -> None:
        from PySide6.QtCore import QStringListModel
        from PySide6.QtWidgets import QListView

        self._paths = [entry.output_path for entry in entries]
        self.model = QStringListModel([entry.id for entry in entries])
        self.table = QListView()
        self.table.setModel(self.model)

    def selected_path(self) -> str | None:
        index = self.table.currentIndex()
        return self._paths[index.row()] if index.isValid() else None


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
    """A host with `FileActions` on it, plus everything a test needs to inspect."""

    def __init__(
        self, *, entries: list[HistoryEntry], downloads: Path, platform: str = sys.platform
    ) -> None:
        self.view = PathList(entries)
        self.spawner = RecordingSpawner()
        #: Windows Open takes no argv (`T086-R1`), so the route has its own recorder. Without it
        #: the Windows CI job would launch a real media player on a build agent.
        self.started: list[Path] = []
        self.reported: list[str] = []
        self.actions = FileActions(
            table=self.view.table,
            selected_path=self.view.selected_path,
            output_directory=lambda: downloads,
            report=self.reported.append,
            run=self.spawner,
            start=self.started.append,
            platform=platform,
        )
        self.platform = platform

    def assert_opened(self, path: Path) -> None:
        """That `path` was opened, **by whichever route this platform actually uses**.

        Not one assertion with a platform branch inside it: the two routes are different enough
        that asserting the wrong one is how `T086-R1` stayed hidden. On Windows an argv would mean
        the associated-application API was bypassed; on Linux a start call would mean the reverse.
        """
        if self.platform == "win32":
            assert self.started == [path]
            assert self.spawner.calls == [], "Windows Open built an argv"
        else:
            assert self.spawner.argv == open_command(path)
            assert self.started == [], "the Windows start route ran on a POSIX platform"

    def select_row(self, row: int) -> None:
        """Select by index rather than by row.

        `selectRow` is a `QTableView` method and the host is a `QListView` — one column, so
        "select the row" is "make its index current".
        """
        self.view.table.setCurrentIndex(self.view.model.index(row, 0))


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
    # Through the platform-aware helper: on Windows this route uses the starter and builds no argv,
    # so a bare spawner assertion fails there for a reason that has nothing to do with selection.
    attached.assert_opened(second)


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

    assert attached.spawner.argv == reveal_command(written), (
        "Show in folder did not reveal — this is the argv Open would build if both actions were "
        "wired to the same call"
    )
    assert attached.spawner.argv != open_command(written), (
        "reveal and open built the same argv, so one of them is wired to the other"
    )


def test_reveal_and_open_do_different_things(
    qapp: QApplication, downloads: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stated as a difference, so neither action can drift onto the other's implementation.

    Pinned to Linux: on Windows Open takes the starter and builds no argv, so only one spawner call
    would exist and comparing two would fail for a reason unrelated to the difference under test.
    """
    monkeypatch.setattr("tracks_and_trails.ui.reveal.dbus_available", lambda: False)
    written = downloads / "clip.mp4"
    written.write_bytes(b"")
    attached = Attached(
        entries=[an_entry("a", str(written))], downloads=downloads, platform="linux"
    )
    attached.select_row(0)

    attached.actions.open_selected()
    attached.actions.reveal_selected()

    opened, revealed = (call[0] for call in attached.spawner.calls)
    assert opened == open_command(written)
    assert revealed == reveal_command(written)
    assert opened != revealed, "the two actions build the same command"


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
    view = PathList([an_entry("a", str(written))])
    reported: list[str] = []
    spawner = RecordingSpawner()
    actions = FileActions(
        table=view.table,
        selected_path=view.selected_path,
        output_directory=lambda: current,
        report=reported.append,
        run=spawner,
        # Pinned: this test is about the boundary being re-read, and it asserts a POSIX argv. Left
        # unpinned it takes the Windows start route on the Windows job and launches for real.
        platform="linux",
    )
    view.table.setCurrentIndex(view.model.index(0, 0))

    refusal = actions.open_selected()
    assert refusal is not None, "opened a file outside the folder in force"
    assert "outside the download folder" in refusal.reason

    current = new

    assert actions.open_selected() is None, "the boundary was captured rather than re-read"
    assert spawner.argv == open_command(written)


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
    attached.assert_opened(written)


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
            platform="linux",
        )

        assert view.select("running")
        assert not actions.open_action.isEnabled(), "offered for a job with nothing written yet"

        assert view.select("done")
        assert actions.open_action.isEnabled()
        actions.open_action.trigger()
        assert spawner.argv == open_command(written)
    finally:
        view.detach()
        manager.shutdown()


def test_a_row_with_no_written_file_answers_absent_rather_than_a_placeholder(
    qapp: QApplication, downloads: Path
) -> None:
    """A view's `selected_path` must answer `None`, never the text its column renders.

    **This was History's test and it moved to the queue with the question** (`T-170`). There, the
    hazard was `path_for` being written as `text_at(PATH_COLUMN)`, which renders an em-dash for a
    null path — handing that to `open_file` reports that a file named "—" is missing, which is a
    true sentence about the wrong thing. The queue draws a path too, and can answer the same way.
    """
    request = DownloadRequest(
        url="https://example.invalid/clip",
        output_directory=str(downloads),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )
    queue = FakeQueue()
    queue.add(Job(id="running", url=request.url, request=request))
    manager = DownloadManager(queue)
    view = QueueView(jobs=queue, manager=manager)
    try:
        assert view.select("running")
        assert view.selected_path() is None, (
            f"the view answered {view.selected_path()!r} for a job with no written file; anything "
            "but None becomes a refusal naming a file that was never asked for"
        )
    finally:
        view.detach()
        manager.shutdown()


def test_the_windows_open_route_is_reached_through_the_actions(
    qapp: QApplication, downloads: Path
) -> None:
    """**The seam, pinned to Windows and asserted from Linux** (`T086-R1`).

    `FileActions` has to hand `open_file` a starter as well as a spawner, and on any POSIX machine
    forgetting the starter changes nothing observable — the Windows branch is never taken. A
    mutation dropping it survived every test in this file until the platform could be pinned here.
    """
    written = downloads / "clip.mp4"
    written.write_bytes(b"")
    attached = Attached(
        entries=[an_entry("a", str(written))], downloads=downloads, platform="win32"
    )
    attached.select_row(0)

    attached.actions.open_action.trigger()

    assert attached.started == [written], "the Windows Open route was not reached"
    assert attached.spawner.calls == [], "Windows Open built an argv"
