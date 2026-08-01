"""The history view (`T-100`, `REQ-020`, `REQ-021`).

One test per acceptance criterion, plus the two the task names as mutation-checked. The view is
read-only over a table `T-085` already gates, so what is tested here is what reaches the *screen* —
every criterion asserts a rendered string rather than the record behind it.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from tracks_and_trails.persistence import db
from tracks_and_trails.persistence.repositories import HistoryEntry, HistoryRepository
from tracks_and_trails.ui.history_view import (
    COLUMN_HEADERS,
    COMPLETED_COLUMN,
    EMPTY_TEXT,
    FORMAT_COLUMN,
    PATH_COLUMN,
    SIZE_COLUMN,
    TITLE_COLUMN,
    URL_COLUMN,
    HistoryView,
    build_history_view,
)
from tracks_and_trails.ui.job_detail import UNKNOWN_TEXT


class FakeHistory:
    """A `HistoryReader` over a list, in the order the repository would return them.

    The real ordering is asserted separately against `HistoryRepository` itself — this one hands
    back exactly what it is given, so a view that re-sorted would be visible here rather than
    hidden behind a repository that had already sorted correctly.
    """

    def __init__(self, entries: list[HistoryEntry] | None = None) -> None:
        self.entries = list(entries or [])

    def all_entries(self) -> list[HistoryEntry]:
        return list(self.entries)


def an_entry(entry_id: str = "job-1", **overrides: object) -> HistoryEntry:
    """A fully populated record. Overrides let a test empty exactly the field it is about."""
    base: dict[str, object] = {
        "id": entry_id,
        "url": "https://example.invalid/watch?v=abc123",
        "title": "A clip about trails",
        "output_path": "/home/sean/Downloads/A clip about trails.mp4",
        "format_used": "137+140",
        "bytes_total": 15_728_640,
        "completed_at": datetime(2026, 7, 30, 14, 5, tzinfo=UTC),
    }
    return HistoryEntry(**(base | overrides))  # type: ignore[arg-type]


def view_over(entries: list[HistoryEntry]) -> HistoryView:
    return build_history_view(FakeHistory(entries))


def test_every_field_req_020_names_is_on_screen(qapp: QApplication) -> None:
    """The first criterion, asserted against a row whose fields are **all** populated.

    A column that is never rendered would otherwise hide behind a `None` somewhere and look like an
    honestly empty cell. `REQ-020` names six things; six things are checked by value.
    """
    entry = an_entry()
    view = view_over([entry])
    model = view.model

    assert model.text_at(entry.id, TITLE_COLUMN) == "A clip about trails"
    assert model.text_at(entry.id, URL_COLUMN) == "https://example.invalid/watch?v=abc123"
    assert model.text_at(entry.id, PATH_COLUMN) == "/home/sean/Downloads/A clip about trails.mp4"
    assert model.text_at(entry.id, FORMAT_COLUMN) == "137+140"
    assert model.text_at(entry.id, SIZE_COLUMN) == "15.0 MB"
    assert model.text_at(entry.id, COMPLETED_COLUMN) == "2026-07-30 14:05"

    # And the headers name them, because a value in an unlabelled column is not "on screen".
    assert COLUMN_HEADERS == ("Title", "Source URL", "Saved to", "Format", "Size", "Completed")


def test_a_completed_download_is_listed_after_its_job_row_is_gone(
    qapp: QApplication, tmp_path: Path
) -> None:
    """**The whole point of the view** (`P2PLAN-R8`), driven through the real repositories.

    `UX-001` says remove never deletes a file and `T-081` delivers clear-completed; together, with
    no history view, the user clears their queue and the application can no longer say where any of
    it went. `history` carries no foreign key to `jobs` — `T-085` gates that structurally — and this
    asserts the user-visible consequence of it.
    """
    from dataclasses import replace

    from tracks_and_trails.core.job_state import JobStatus
    from tracks_and_trails.core.models import DownloadRequest, Job
    from tracks_and_trails.persistence.repositories import JobRepository, complete_job

    connection = db.connect(tmp_path / "library.sqlite3")
    jobs = JobRepository(connection)
    history = HistoryRepository(connection)

    request = DownloadRequest(
        url="https://example.invalid/clip",
        output_directory=str(tmp_path),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )
    jobs.append([Job(id="job-1", url=request.url, request=request)])
    stored = jobs.get("job-1")
    assert stored is not None
    complete_job(
        connection,
        replace(stored, status=JobStatus.COMPLETED, output_path=str(tmp_path / "clip.mp4")),
        an_entry("job-1", output_path=str(tmp_path / "clip.mp4")),
    )

    view = build_history_view(history)
    assert view.model.entry_ids() == ("job-1",)

    # The queue forgets. `clear_completed` is `T-081`'s, and it deletes job rows only.
    assert jobs.clear_completed() == ["job-1"]
    assert jobs.get("job-1") is None
    view.refresh()

    assert view.model.entry_ids() == ("job-1",), (
        "clearing the queue took the history record with it, so the user has files on disk and "
        "nothing that says where they went — which is the hole this view exists to close"
    )
    assert view.model.text_at("job-1", PATH_COLUMN) == str(tmp_path / "clip.mp4")


def test_the_order_is_newest_first(qapp: QApplication, tmp_path: Path) -> None:
    """Against the **real** repository, because the order is `all_entries()`'s to decide.

    A view that re-sorted, or that relied on insertion order, would disagree with the data silently.
    Inserted deliberately out of order so arrival and completion time differ.
    """
    connection = db.connect(tmp_path / "library.sqlite3")
    history = HistoryRepository(connection)
    for entry_id, when in (
        ("middle", datetime(2026, 7, 20, 9, 0, tzinfo=UTC)),
        ("newest", datetime(2026, 7, 30, 9, 0, tzinfo=UTC)),
        ("oldest", datetime(2026, 7, 10, 9, 0, tzinfo=UTC)),
    ):
        history.record(an_entry(entry_id, completed_at=when))

    view = build_history_view(history)

    assert view.model.entry_ids() == ("newest", "middle", "oldest"), (
        f"shown {view.model.entry_ids()}; the newest download is the one a user is looking for"
    )


def test_an_empty_history_says_so_rather_than_showing_a_blank_table(qapp: QApplication) -> None:
    """A user who has downloaded nothing and a view that failed to load look identical otherwise."""
    view = view_over([])

    assert view.shows_empty_notice
    assert view.empty_text() == EMPTY_TEXT
    assert not view.table.isVisible(), "an empty table is shown beside the notice"
    # `T-060`'s rule: a hidden widget must not be in the keyboard order.
    assert view.focus_chain() == []


def test_a_populated_history_shows_the_table_and_not_the_notice(qapp: QApplication) -> None:
    """The other half, and it is a separate test because they fail for different reasons."""
    view = view_over([an_entry()])

    assert not view.shows_empty_notice
    assert view.focus_chain() == [view.table]


def test_a_null_field_renders_as_absence_not_as_the_word_none(qapp: QApplication) -> None:
    """`title`, `output_path`, `format_used` and `bytes_total` are all nullable by design.

    `str(None)` reaching a cell is the defect class `_str_or_none` exists to prevent one layer
    down — and `format_used` is the one that matters most, because `None` there means *yt-dlp
    reported no format*, and printing "None" in a column headed Format states something false.
    """
    entry = an_entry(title=None, output_path=None, format_used=None, bytes_total=None)
    model = view_over([entry]).model

    for column in (TITLE_COLUMN, PATH_COLUMN, FORMAT_COLUMN, SIZE_COLUMN):
        rendered = model.text_at(entry.id, column)
        assert rendered == UNKNOWN_TEXT, f"column {column} rendered {rendered!r}"
        assert "None" not in str(rendered)


def test_the_url_is_never_absent(qapp: QApplication) -> None:
    """`HistoryEntry` refuses a record without one, so the view need not have a story for it.

    Asserted rather than assumed: if that constructor guard were relaxed, this column would start
    rendering an empty string and the record would be unusable for the retry `REQ-020` exists for.
    """
    with pytest.raises(ValueError, match="source URL"):
        an_entry(url="")


def test_the_table_and_its_columns_carry_accessible_names(qapp: QApplication) -> None:
    """`NFR-005`, following `ui/job_detail.py`'s pattern.

    The per-cell accessible text names its column: a bare value read out of a six-column table
    tells a screen-reader user nothing about which field they are hearing.
    """
    entry = an_entry()
    view = view_over([entry])

    assert view.objectName() == "historyView"
    assert view.table.objectName() == "historyTable"
    assert view.table.accessibleName() == "Download history"
    assert view.table.accessibleDescription()

    index = view.model.index(0, FORMAT_COLUMN)
    spoken = view.model.data(index, Qt.ItemDataRole.AccessibleTextRole)
    assert spoken == "Format: 137+140", f"a screen reader hears {spoken!r}"


def test_a_long_url_and_path_carry_their_whole_value_as_a_tooltip(qapp: QApplication) -> None:
    """Both are routinely wider than their column, and a truncated path cannot be acted on."""
    entry = an_entry()
    view = view_over([entry])

    for column, expected in (
        (URL_COLUMN, entry.url),
        (PATH_COLUMN, entry.output_path),
    ):
        index = view.model.index(0, column)
        assert view.model.data(index, Qt.ItemDataRole.ToolTipRole) == expected


def test_refresh_picks_up_a_download_that_finished_after_the_view_was_built(
    qapp: QApplication,
) -> None:
    """The view has no live subscription, so `refresh()` is the whole mechanism.

    Composition calls it on `job_succeeded` and `queue_cleared`, which are the only two moments the
    set of records can differ.
    """
    reader = FakeHistory([])
    view = build_history_view(reader)
    assert view.shows_empty_notice

    reader.entries.append(an_entry("job-2"))
    view.refresh()

    assert view.model.entry_ids() == ("job-2",)
    assert not view.shows_empty_notice, "the notice outlived the empty history it describes"
