"""The history view (`T-100`, `REQ-020`, `REQ-021`).

One test per acceptance criterion, plus the two the task names as mutation-checked. The view is
read-only over a table `T-085` already gates, so what is tested here is what reaches the *screen* —
every criterion asserts a rendered string rather than the record behind it.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QApplication

from tracks_and_trails.persistence import db
from tracks_and_trails.persistence.repositories import HistoryEntry, HistoryRepository
from tracks_and_trails.ui.history_view import (
    COLUMN_HEADERS,
    COMPLETED_COLUMN,
    COMPLETED_FORMAT,
    EMPTY_TEXT,
    FORMAT_COLUMN,
    PATH_COLUMN,
    SIZE_COLUMN,
    TITLE_COLUMN,
    URL_COLUMN,
    HistoryView,
    build_history_view,
)
from tracks_and_trails.ui.job_detail import UNKNOWN_TEXT, format_bytes
from tracks_and_trails.ui.row_delegate import (
    DETAIL_ROLE,
    HEADLINE_ROLE,
    PROGRESS_ROLE,
    SELECTOR_ROLE,
    THUMBNAIL_URL_ROLE,
    VERBS_ROLE,
    RowDelegate,
)
from tracks_and_trails.ui.row_verbs import Verb


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


def test_a_row_speaks_every_field_it_shows(qapp: QApplication) -> None:
    """`NFR-005`. **The whole row**, since `UX-005` §3 made this a list rather than six columns.

    It used to name the column — "Format: 137+140" — because a bare value out of six columns says
    nothing about which field is being heard. There is one column now, so the equivalent claim is
    that a screen reader hears every field `REQ-020` names rather than only the one that happens
    to be drawn largest.

    **Asserted field by field**, not as one string: an equality against the whole sentence would
    fail on punctuation and pass on a missing field, which is the wrong way round.
    """
    entry = an_entry()
    view = view_over([entry])

    assert view.objectName() == "historyView"
    assert view.table.objectName() == "historyTable"
    assert view.table.accessibleName() == "Download history"
    assert view.table.accessibleDescription()

    spoken = view.model.data(view.model.index(0, 0), Qt.ItemDataRole.AccessibleTextRole)
    assert isinstance(spoken, str)
    for header in COLUMN_HEADERS:
        assert f"{header}:" in spoken, (
            f"a screen reader hears {spoken!r}, which never says {header!r} — REQ-020 names that "
            "field and a row that does not speak it is unusable without sight"
        )
    assert "137+140" in spoken, f"the values are missing from {spoken!r}"


def test_a_long_url_and_path_carry_their_whole_value_as_a_tooltip(qapp: QApplication) -> None:
    """A truncated path cannot be acted on, and the row draws it on one line (`UX-005` §3).

    The need did not change when the columns did: both values are routinely wider than the space
    they get, and somebody copying a path into a bug report needs all of it. Asserted as
    *containment* rather than equality, because the tooltip now carries both values and the exact
    joining is presentation.
    """
    entry = an_entry()
    view = view_over([entry])

    tip = view.model.data(view.model.index(0, 0), Qt.ItemDataRole.ToolTipRole)
    assert isinstance(tip, str)
    assert entry.url in tip, f"the URL is not in the tooltip: {tip!r}"
    assert entry.output_path is not None
    assert entry.output_path in tip, f"the saved path is not in the tooltip: {tip!r}"


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


# --- UX-005 §3: the same row anatomy, saying different things -------------------------------


def test_a_history_row_is_the_shared_anatomy(qapp: QApplication) -> None:
    """`UX-005` §3: both tabs draw the `T-119` row; history changes what the fields **say**.

    "Where the queue shows progress and speed, history shows the saved path, size and when."
    Asserted through the delegate's own roles, by value, because that is the contract between the
    model and the one renderer both tabs share — a row that looked right while answering the
    wrong roles would draw as a blank row the moment the delegate consulted them.
    """
    entry = an_entry()
    view = view_over([entry])
    index = view.model.index(0, 0)

    assert view.model.data(index, HEADLINE_ROLE) == entry.title, (
        "the row's headline is not the title of what was downloaded"
    )
    detail = view.model.data(index, DETAIL_ROLE)
    assert isinstance(detail, str)
    assert format_bytes(entry.bytes_total) in detail, f"the size is missing from {detail!r}"
    assert entry.completed_at.strftime(COMPLETED_FORMAT) in detail, (
        f"when it finished is missing from {detail!r}"
    )
    assert view.model.data(index, SELECTOR_ROLE) == entry.output_path, (
        "the row does not carry the saved path, which UX-005 §3 names and which is the thing a "
        "person copies into a bug report"
    )
    # **No progress role**, which is the half that says history is not a queue: the delegate draws
    # a progress bar for anything that answers it, and a finished record has no progress to show.
    assert view.model.data(index, PROGRESS_ROLE) is None, (
        "a history row answers PROGRESS_ROLE, so the delegate would draw a progress bar on a "
        "download that finished"
    )


def test_a_history_row_offers_the_two_file_verbs_and_remove(qapp: QApplication) -> None:
    """`REQ-021` and `DAT-005`, and `UX-005` §5 applied to the other tab.

    Open and Show in folder are the two things a user does with a finished download; `DAT-005`
    (2026-08-04) added the third. **Until that decision existed this asserted exactly two**, and
    the reason is worth keeping: `HistoryRepository` said nothing deletes, no requirement covered
    removal, and `UX-005` §9 described the control while refusing to specify it. A button that
    appeared before the decision would *have been* the decision.

    Equality, not containment: a fourth verb on a history row is a surface nobody decided on, and
    this is where that would be caught.
    """
    view = view_over([an_entry()])
    offered = view.model.data(view.model.index(0, 0), VERBS_ROLE)

    assert tuple(offered) == (Verb.OPEN, Verb.REVEAL, Verb.REMOVE), (
        f"a history row offers {[v.value for v in offered]}"
    )


def test_a_history_rows_open_reports_rather_than_opening(qapp: QApplication) -> None:
    """`SEC-001`: containment lives in `FileActions`, so the view reports and the shell acts.

    The same split the queue row makes. A view that resolved its own path would be a second place
    the containment check could be missing, and the check is the only reason opening a file from a
    list of recorded paths is safe at all.
    """
    entry = an_entry()
    view = view_over([entry])
    asked: list[str] = []
    view.open_requested.connect(asked.append)

    view.trigger_verb(entry.id, Verb.OPEN)

    assert asked == [entry.id], "the history row's Open reached nothing"


# --- DAT-005 / T-125: removing records, never files -----------------------------------------


def test_remove_acts_on_the_whole_selection(qapp: QApplication) -> None:
    """`DAT-005` §1: removal is selection-scoped, so the verb carries the selection.

    Sending only the clicked row would make the count in the confirmation a decoration — it would
    always say one — and a user who selected three and confirmed "3 downloads" would lose one.
    """
    entries = [an_entry(entry_id=f"job-{n}") for n in range(3)]
    view = view_over(entries)
    asked: list[list[str]] = []
    view.removal_requested.connect(asked.append)

    assert view.select("job-0")
    view.table.selectionModel().select(
        view.model.index(1, 0), QItemSelectionModel.SelectionFlag.Select
    )

    view.trigger_verb("job-0", Verb.REMOVE)

    assert asked == [["job-0", "job-1"]], f"Remove asked for {asked}"


def test_remove_on_an_unselected_row_means_that_row(qapp: QApplication) -> None:
    """The other half. Clicking Remove on a row outside the selection means *that* row.

    A user who has one row selected and clicks Remove on a different one has not asked to remove
    the selection — reading it as the selection would delete something they never pointed at.
    """
    entries = [an_entry(entry_id=f"job-{n}") for n in range(3)]
    view = view_over(entries)
    asked: list[list[str]] = []
    view.removal_requested.connect(asked.append)
    assert view.select("job-0")

    view.trigger_verb("job-2", Verb.REMOVE)

    assert asked == [["job-2"]], f"Remove asked for {asked}"


def test_a_history_row_keeps_the_picture_its_queue_row_had(qapp: QApplication) -> None:
    """`T-138`, `UX-005` §3: both tabs draw the same row anatomy.

    **Asserted through the role the shared delegate reads**, because that is what decides the
    drawing — and asserted on a record that *has* a picture and one that does not, since `None` is
    what every row written before migration `0005` carries and it must still render.

    The defect was structural rather than a mis-wiring: `HistoryEntry` had no such field and the
    view built its delegate with no thumbnail store, so the same download drew a picture in the
    queue and a derived tile here, one row apart.
    """
    pictured = HistoryEntry(
        id="h-1",
        url="https://example.invalid/one",
        title="A finished download",
        thumbnail_url="https://img.invalid/one.jpg",
        completed_at=datetime(2026, 8, 4, 20, 0, tzinfo=UTC),
    )
    bare = HistoryEntry(
        id="h-2",
        url="https://example.invalid/two",
        completed_at=datetime(2026, 8, 4, 20, 5, tzinfo=UTC),
    )
    view = HistoryView(history=FakeHistory([pictured, bare]))
    model = view.model

    assert model.data(model.index(0, 0), THUMBNAIL_URL_ROLE) == "https://img.invalid/one.jpg", (
        "a history row answers no thumbnail, so it draws the derived tile for a download whose "
        "picture the queue was showing a moment earlier"
    )
    assert model.data(model.index(1, 0), THUMBNAIL_URL_ROLE) is None, (
        "a record written before the column existed invented a picture"
    )


def test_the_history_view_can_fetch_a_picture_at_all(qapp: QApplication) -> None:
    """The role is half of it; a store to answer it is the other half (`T-138`).

    The view built its delegate **without** a `ThumbnailStore`, so even given the URL every row
    would still have drawn the derived tile. A test asserting only the role would have passed
    against exactly the application the maintainer reported.
    """
    view = HistoryView(history=FakeHistory([]))
    delegate = view.table.itemDelegate()

    assert isinstance(delegate, RowDelegate)
    assert delegate._thumbnails is not None, (
        "the history view's delegate has no thumbnail store, so no history row can ever draw a "
        "picture whatever the model answers"
    )
