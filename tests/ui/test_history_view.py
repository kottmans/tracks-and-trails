"""The history view (`T-100`, `REQ-020`, `REQ-021`).

One test per acceptance criterion, plus the two the task names as mutation-checked. The view is
read-only over a table `T-085` already gates, so what is tested here is what reaches the *screen* —
every criterion asserts a rendered string rather than the record behind it.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QEvent, QItemSelectionModel, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from tests.qt_lifecycle import drain
from tracks_and_trails.persistence import db
from tracks_and_trails.persistence.repositories import HistoryEntry, HistoryRepository
from tracks_and_trails.ui.history_view import (
    COLUMN_HEADERS,
    COMPLETED_COLUMN,
    COMPLETED_FORMAT,
    EMPTY_TEXT,
    FORMAT_COLUMN,
    PATH_COLUMN,
    RAW_FORMAT_PREFIX,
    SIZE_COLUMN,
    TITLE_COLUMN,
    URL_COLUMN,
    HistoryView,
    build_history_view,
)
from tracks_and_trails.ui.job_detail import UNKNOWN_TEXT, format_bytes
from tracks_and_trails.ui.row_delegate import (
    DEPTH_ROLE,
    DETAIL_ROLE,
    EXPANDED_ROLE,
    HEADLINE_ROLE,
    JOB_ID_ROLE,
    PROGRESS_ROLE,
    SEGMENTS_ROLE,
    SELECTOR_ROLE,
    STATE_CHIP_ROLE,
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


def test_history_installs_the_hover_route_its_delegate_requires(qapp: QApplication) -> None:
    """Reviewer regression for `T-134`: History uses the shared painted verb controls too."""
    view = view_over([an_entry()])

    assert view.table.viewport().hasMouseTracking(), (
        "History never installed RowDelegate.watch_hover(); its painted Open and Show-in-folder "
        "buttons cannot receive pointer-move events unless a mouse button is already held"
    )


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


# --- a finished playlist is one row (`T-145`, `UX-005` amended 2026-08-05) --------------------


def a_member(
    entry_id: str,
    *,
    index: int,
    playlist_id: str = "pl-1",
    title: str = "Trail Sounds",
    **overrides: object,
) -> HistoryEntry:
    """A record that belongs to a playlist. The three columns travel together or not at all."""
    return an_entry(
        entry_id,
        playlist_id=playlist_id,
        playlist_index=index,
        playlist_title=title,
        **overrides,
    )


def test_a_finished_playlist_is_one_row_that_opens(qapp: QApplication) -> None:
    """The first criterion, and the report: sixteen tracks landed here as sixteen unrelated rows.

    Asserted by **row count and roles**, not by pixels: the claim is about what the list holds, and
    a pixel comparison would pass with three rows drawn identically. `UX-005` §3 makes this the
    queue's anatomy, so the roles asserted are the ones a queue header answers.
    """
    view = view_over(
        [
            a_member("m-1", index=0),
            a_member("m-2", index=1),
            a_member("m-3", index=2),
            an_entry("solo"),
        ]
    )
    model = view.model

    assert model.rowCount() == 2, (
        f"a three-entry playlist and one ordinary download show {model.rowCount()} rows; closed, "
        "the playlist must be one of them"
    )
    header = model.index(0, 0)
    assert model.data(header, HEADLINE_ROLE) == "Trail Sounds"
    assert model.data(header, JOB_ID_ROLE) == "pl-1"
    assert model.data(header, EXPANDED_ROLE) is False

    model.toggle_group("pl-1")

    assert model.rowCount() == 5, (
        f"opening the playlist showed {model.rowCount()} rows; it must be the header, its three "
        "entries and the unrelated download"
    )
    assert model.data(model.index(0, 0), EXPANDED_ROLE) is True
    assert model.data(model.index(1, 0), DEPTH_ROLE) == 1, (
        "an entry is not nested under its group, so it reads as an unrelated row"
    )
    assert model.data(model.index(4, 0), DEPTH_ROLE) == 0, (
        "the unrelated download was indented as though it belonged to the playlist"
    )


def test_a_history_group_counts_its_members_and_never_measures(qapp: QApplication) -> None:
    """Decision 1 of the amendment: the chip is `3 items`.

    The 2026-08-04 amendment excluded History from the **state** chip — a `Done` on every row is
    noise. A count is not a state, which is why this is a different chip rather than a reversal:
    the ordinary rows beside it still carry none.
    """
    view = view_over([a_member("m-1", index=0), a_member("m-2", index=1), an_entry("solo")])
    model = view.model

    chip = model.data(model.index(0, 0), STATE_CHIP_ROLE)
    assert chip == "2 items", f"the group's chip reads {chip!r} rather than a count of its members"
    assert "%" not in str(chip)

    assert model.data(model.index(1, 0), STATE_CHIP_ROLE) is None, (
        "an ordinary history row grew a chip, which the 2026-08-04 amendment excluded because "
        "every history row is finished and a chip saying so on all of them is noise"
    )


def test_a_history_group_draws_no_segmented_bar(qapp: QApplication) -> None:
    """Decision 2: every member succeeded, so row 9b's bar would be N identical blocks.

    Asserted as the role answering nothing rather than as an empty list — the delegate draws a bar
    for any sequence it is given, and `[]` would be a bar of no blocks rather than no bar.
    """
    view = view_over([a_member("m-1", index=0), a_member("m-2", index=1)])
    model = view.model

    assert model.data(model.index(0, 0), SEGMENTS_ROLE) is None, (
        "a history group answers the segmented bar, which UX-005's amendment refuses: every "
        "member is finished, so the bar is furniture rather than information"
    )


def test_a_partly_failed_playlist_counts_what_history_holds(qapp: QApplication) -> None:
    """Decision 3: `2 items`, never `2 of 3`.

    A sixteen-item playlist with failures reaches History as fewer records — only completed
    downloads arrive (`DAT-005`). The denominator is refused twice over: it describes downloads
    History does not hold, and `DAT-005` makes records removable, so a stored original count is
    wrong about *both* numbers after the first removal. Here the third entry never arrived, and
    nothing on the header may claim it did.
    """
    view = view_over([a_member("m-1", index=0), a_member("m-3", index=2)])
    model = view.model
    header = model.index(0, 0)

    assert model.data(header, STATE_CHIP_ROLE) == "2 items"
    spoken = str(model.data(header, Qt.ItemDataRole.AccessibleTextRole))
    assert "of 3" not in spoken and "of 2" not in spoken, (
        f"the header speaks {spoken!r}, which claims a denominator History cannot describe — the "
        "entries that failed are not records and were never counted"
    )


def test_a_group_opens_in_the_playlists_order_not_the_order_they_finished(
    qapp: QApplication,
) -> None:
    """`playlist_index` is what `0006` carried across, and this is what for.

    History is newest-completed-first and a playlist is not read that way. Track 03 finishing
    first — a smaller file, or a retry — must not put it above track 01 inside the group.
    """
    view = view_over(
        [
            a_member("third", index=2, completed_at=datetime(2026, 7, 30, 16, 0, tzinfo=UTC)),
            a_member("first", index=0, completed_at=datetime(2026, 7, 30, 15, 0, tzinfo=UTC)),
            a_member("second", index=1, completed_at=datetime(2026, 7, 30, 14, 0, tzinfo=UTC)),
        ]
    )
    model = view.model
    model.toggle_group("pl-1")

    opened = tuple(model.entry_id_at(row) for row in range(1, model.rowCount()))
    assert opened == ("first", "second", "third"), (
        f"the playlist opened as {opened}; it must read in the order the site reported, not the "
        "order the downloads happened to finish"
    )


def test_a_record_written_before_the_migration_renders_ungrouped(qapp: QApplication) -> None:
    """The criterion, and the one thing this task refuses to do.

    Every record in a database that predates `0006` has no membership. They render as they always
    did — and **no membership is invented** for them from their titles or their paths, which would
    present a guess as a record.
    """
    older = [
        an_entry("old-1", title="Trail Sounds — 01", output_path="/downloads/Trail Sounds/01.mp3"),
        an_entry("old-2", title="Trail Sounds — 02", output_path="/downloads/Trail Sounds/02.mp3"),
    ]
    view = view_over(older)
    model = view.model

    assert model.rowCount() == 2, (
        "two records sharing a folder and a title prefix were grouped, which is membership "
        "inferred rather than recorded"
    )
    for row in range(2):
        assert model.data(model.index(row, 0), EXPANDED_ROLE) is None, (
            "a record with no membership drew a disclosure triangle"
        )
        assert model.data(model.index(row, 0), DEPTH_ROLE) == 0


def test_a_playlist_that_left_one_record_is_not_a_group(qapp: QApplication) -> None:
    """A heading over a single row is a heading over nothing (`ui/grouping.flatten`, rule 3).

    Reachable in History for a reason the queue does not have: a sixteen-item playlist where
    fifteen failed leaves exactly one record, and `DAT-005` removal can leave one behind too.
    """
    view = view_over([a_member("only", index=0), an_entry("solo")])
    model = view.model

    assert model.rowCount() == 2
    assert model.data(model.index(0, 0), EXPANDED_ROLE) is None
    assert model.entry_id_at(0) == "only", (
        "the lone survivor of a playlist is drawn under a header, so a user must open a group to "
        "reach a single download"
    )


def test_a_header_is_not_a_record_and_never_answers_as_one(qapp: QApplication) -> None:
    """`T140-R1`'s defect, in the tab that had not grown groups yet.

    `entry_ids()` is every record and a row number counts drawn lines; the two diverge the moment a
    playlist is collapsed. Indexing the first with the second resolves a visible row to a hidden
    member, and every file action then targets a record the user cannot see.
    """
    view = view_over([a_member("m-1", index=0), a_member("m-2", index=1), an_entry("solo")])
    model = view.model

    assert model.entry_ids() == ("m-1", "m-2", "solo"), "the durable order is the repository's"
    assert model.entry_id_at(0) is None, "the group header answered as though it were a record"
    assert model.entry_id_at(1) == "solo", (
        f"row 1 resolved to {model.entry_id_at(1)!r}; with the playlist closed the second drawn "
        "row is the unrelated download, and naming a hidden member points every file verb at a "
        "record the user cannot see"
    )
    assert view.verbs_of("pl-1") == (Verb.REVEAL, Verb.REMOVE), (
        f"the header offers {view.verbs_of('pl-1')}; a terminal group's list is derived for it "
        "(T-142) rather than borrowed from the row beneath it"
    )


def test_selecting_a_playlist_selects_the_downloads_it_stands_for(qapp: QApplication) -> None:
    """Removing a group removes its **members** — the criterion, and where it actually lives.

    A header has no id in `history` and nothing to delete, so a removal that took row ids would
    delete nothing while telling the user it had. Answering with the members is what lets
    `DAT-005` §1's existing selection-scoped route remove a playlist, and what makes the
    confirmation count downloads rather than lines.
    """
    view = view_over([a_member("m-1", index=0), a_member("m-2", index=1), an_entry("solo")])
    view.table.selectionModel().select(
        view.model.index(0, 0), QItemSelectionModel.SelectionFlag.Select
    )

    assert view.selected_entry_ids() == ("m-1", "m-2"), (
        f"selecting the playlist selected {view.selected_entry_ids()}; the confirmation counts "
        "what it is about to remove, so a header that stands for two downloads must name two"
    )

    # And with the unrelated download selected beside it, `DAT-005` §1's "the whole selection"
    # covers the playlist's members rather than a header id nothing can delete.
    view.table.selectionModel().select(
        view.model.index(1, 0), QItemSelectionModel.SelectionFlag.Select
    )
    removed: list[list[str]] = []
    view.removal_requested.connect(removed.append)
    view.trigger_verb("solo", Verb.REMOVE)

    assert removed == [["m-1", "m-2", "solo"]], (
        f"removal reported {removed}; a selection holding a playlist and an unrelated download "
        "must remove all three records, not the header's id"
    )


def test_a_playlist_and_one_of_its_members_count_as_the_downloads_once(
    qapp: QApplication,
) -> None:
    """One gesture, two paths to the same id (`DAT-005` §4).

    Selecting a header and then ctrl-clicking one of its open entries is ordinary. A count that
    said 3 for two downloads would be exactly the decoration a count naming itself exists to
    prevent.
    """
    view = view_over([a_member("m-1", index=0), a_member("m-2", index=1)])
    view.model.toggle_group("pl-1")
    for row in (0, 1):
        view.table.selectionModel().select(
            view.model.index(row, 0), QItemSelectionModel.SelectionFlag.Select
        )

    assert view.selected_entry_ids() == ("m-1", "m-2")


def test_a_group_never_claims_a_size_it_cannot_add_up(qapp: QApplication) -> None:
    """`bytes_total` is nullable and means "the download reported none".

    Summing the members that have one produces a number that is confidently too small with nothing
    on the row to say so — a group of three missing one size reads as a correct total for two.
    """
    view = view_over(
        [
            a_member("m-1", index=0, bytes_total=1_048_576),
            a_member("m-2", index=1, bytes_total=None),
        ]
    )
    detail = str(view.model.data(view.model.index(0, 0), DETAIL_ROLE))

    assert detail.startswith(UNKNOWN_TEXT), (
        f"the group's detail line reads {detail!r}, which states a total that is missing one "
        "member's size and looks exactly like a correct one"
    )


def test_a_groups_folder_is_the_one_its_entries_share(qapp: QApplication) -> None:
    """`UX-005` row 10, and the case where it stops being true.

    A playlist's entries share a folder, which is what makes one line meaningful on the header —
    but a user who changed the download folder mid-playlist has records that disagree, and the
    header says so rather than picking the first member's answer.
    """
    together = view_over(
        [
            a_member("m-1", index=0, output_path="/downloads/Trail Sounds/01.mp3"),
            a_member("m-2", index=1, output_path="/downloads/Trail Sounds/02.mp3"),
        ]
    )
    assert together.model.data(together.model.index(0, 0), SELECTOR_ROLE) == (
        "/downloads/Trail Sounds"
    )

    apart = view_over(
        [
            a_member("m-1", index=0, output_path="/downloads/Trail Sounds/01.mp3"),
            a_member("m-2", index=1, output_path="/elsewhere/02.mp3"),
        ]
    )
    assert apart.model.data(apart.model.index(0, 0), SELECTOR_ROLE) == UNKNOWN_TEXT, (
        "the header claimed one folder for entries written to two"
    )


def test_a_hidden_member_is_reached_by_opening_its_playlist(qapp: QApplication) -> None:
    """`T-086`'s route, which a closed group would otherwise break silently.

    `select()` is how a named record is reached before *Open* or *Show in folder* acts on it. A
    member of a closed playlist has no row for that to land on, so the verb would do nothing for
    exactly the downloads a playlist contributed.
    """
    view = view_over([a_member("m-1", index=0), a_member("m-2", index=1)])

    assert view.select("m-2") is True
    assert view.selected_entry_id() == "m-2", (
        "selecting a record inside a closed playlist selected nothing, so its file verbs act on "
        "no record at all"
    )
    assert view.select("never-recorded") is False


def test_a_playlist_opens_and_closes_from_the_keyboard(qapp: QApplication) -> None:
    """`NFR-005`: a group only a pointer can open is `T140-R5`'s defect, one tab over."""
    view = view_over([a_member("m-1", index=0), a_member("m-2", index=1)])
    view.table.setCurrentIndex(view.model.index(0, 0))

    def press(key: Qt.Key) -> None:
        view.eventFilter(
            view.table, QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
        )

    press(Qt.Key.Key_Right)
    assert view.model.rowCount() == 3, "Right did not open the focused playlist"
    press(Qt.Key.Key_Right)
    assert view.model.rowCount() == 3, "a second Right closed the group it had just opened"
    press(Qt.Key.Key_Left)
    assert view.model.rowCount() == 1, "Left did not close the focused playlist"


def test_the_tab_count_counts_downloads_rather_than_lines(qapp: QApplication) -> None:
    """`QueueModel.download_count`'s ruling, one tab over: count the work, not the lines.

    A count reading `rowCount()` moves when a user opens a group, without History having changed.
    """
    view = view_over([a_member("m-1", index=0), a_member("m-2", index=1), an_entry("solo")])

    assert view.model.download_count() == 3
    view.model.toggle_group("pl-1")
    assert view.model.download_count() == 3, (
        "opening a playlist changed how many downloads History says it holds"
    )


def test_both_tabs_draw_a_playlist_with_the_same_anatomy(
    qapp: QApplication, tmp_path: Path
) -> None:
    """The criterion that the two tabs are asserted **together**, not each alone (`UX-005` §3).

    `T-145`'s real design work was the shared-code question: `QueueModel` held the grouping, and
    duplicating it here means the two tabs drift in exactly the way §3 exists to prevent. What is
    shared is `ui/grouping.flatten` — the flattening and the expansion — and what is not is the
    data, because the queue groups `Job`s and this groups records.

    So the assertion is over both models at once. Each half asserted in its own file would pass
    while the two disagreed, which is the whole failure mode.
    """
    from tests.ui.test_queue_view import FakeQueue, make_job
    from tracks_and_trails.downloader.manager import DownloadManager
    from tracks_and_trails.ui.queue_view import QueueModel

    queue = FakeQueue()
    for index in range(3):
        queue.add(
            make_job(
                f"m-{index}",
                tmp_path,
                queue_position=index,
                playlist_id="pl-1",
                playlist_index=index,
                playlist_title="Trail Sounds",
            )
        )
    queue.add(make_job("solo", tmp_path, queue_position=9))
    manager = DownloadManager(queue)
    # Held in a name, not reached through `.model`: the view owns the model, and letting it fall
    # out of scope takes the C++ object with it.
    history = view_over(
        [
            a_member("m-0", index=0),
            a_member("m-1", index=1),
            a_member("m-2", index=2),
            an_entry("solo"),
        ]
    )
    try:
        # `Any`, because the point is that two *unrelated* models answer the same roles: their
        # only common base is `QAbstractTableModel`, which knows nothing about groups.
        tabs: dict[str, Any] = {
            "queue": QueueModel(jobs=queue, manager=manager),
            "history": history.model,
        }

        for name, model in tabs.items():
            header = model.index(0, 0)
            assert model.rowCount() == 2, f"{name}: a closed playlist is not one row"
            assert model.data(header, HEADLINE_ROLE) == "Trail Sounds", f"{name}: header title"
            assert model.data(header, JOB_ID_ROLE) == "pl-1", f"{name}: header id"
            assert model.data(header, EXPANDED_ROLE) is False, f"{name}: closed"
            assert model.data(model.index(1, 0), EXPANDED_ROLE) is None, (
                f"{name}: an ordinary row drew a disclosure triangle"
            )

            model.toggle_group("pl-1")
            assert model.rowCount() == 5, f"{name}: opening did not reveal three entries"
            assert model.data(model.index(0, 0), EXPANDED_ROLE) is True, f"{name}: open"
            assert model.data(model.index(1, 0), DEPTH_ROLE) == 1, f"{name}: entry not nested"
            assert model.data(model.index(4, 0), DEPTH_ROLE) == 0, f"{name}: unrelated row nested"
    finally:
        manager.shutdown()
        drain(qapp, [manager])


# --- a History playlist's own verbs (`T-142`) --------------------------------------------------


def test_a_history_group_offers_what_a_terminal_group_can_support(qapp: QApplication) -> None:
    """The list, transcribed from `UX-005` and `DAT-005` rather than copied from the queue.

    Every member of a History group is terminal by definition — `DAT-005` admits only completed
    downloads — so `Cancel all` has nothing to stop and `Retry failed` has no job to retry.
    Offering either would draw a button with nothing behind it, which is `T-016`'s failure and what
    `UX-005` §5 forbids. `Open` is out because there is no one file to open.
    """
    view = view_over([a_member("m-1", index=0), a_member("m-2", index=1)])

    assert view.verbs_of("pl-1") == (Verb.REVEAL, Verb.REMOVE)
    for absent in (Verb.CANCEL_ALL, Verb.RETRY_FAILED, Verb.OPEN, Verb.RETRY, Verb.CANCEL):
        assert absent not in view.verbs_of("pl-1"), (
            f"a terminal history group offers {absent}, which nothing on this tab can perform"
        )


def test_a_group_of_records_with_no_file_does_not_offer_to_show_one(qapp: QApplication) -> None:
    """`output_path` is nullable, and a group with no path has no folder to point at.

    `FileActions` would refuse the reveal for a reason the user cannot act on, so the verb is
    absent rather than offered-and-declined — `T081-R3`'s rule. *Remove* survives, so the header is
    never left with nothing.
    """
    view = view_over(
        [
            a_member("m-1", index=0, output_path=None),
            a_member("m-2", index=1, output_path=None),
        ]
    )

    assert view.verbs_of("pl-1") == (Verb.REMOVE,)


def test_entry_verbs_are_unchanged_by_the_level_above_them(qapp: QApplication) -> None:
    """The criterion: this adds a level, it does not move one.

    A record inside a playlist is still a record — `REQ-021`'s two file actions and `DAT-005`'s
    removal — and a group's shorter list must not have leaked down onto its members.
    """
    view = view_over([a_member("m-1", index=0), a_member("m-2", index=1), an_entry("solo")])
    view.model.toggle_group("pl-1")

    assert view.verbs_of("m-1") == (Verb.OPEN, Verb.REVEAL, Verb.REMOVE)
    assert view.verbs_of("solo") == (Verb.OPEN, Verb.REVEAL, Verb.REMOVE)


def test_removing_a_playlist_names_its_members_and_nothing_beside_them(
    qapp: QApplication,
) -> None:
    """A verb on the header does not touch records outside the group.

    Asserted with an unrelated record beside it, and with **nothing selected**: a header that
    resolved through the selection alone would report an empty removal, and one that reported its
    own id would name something `history` has no row for.
    """
    view = view_over([a_member("m-1", index=0), a_member("m-2", index=1), an_entry("solo")])
    removed: list[list[str]] = []
    view.removal_requested.connect(removed.append)

    view.trigger_verb("pl-1", Verb.REMOVE)

    assert removed == [["m-1", "m-2"]], (
        f"the header's Remove reported {removed}; it must name the two records it stands for and "
        "leave the unrelated download alone"
    )


def test_a_playlists_remove_says_how_many_downloads_it_takes(qapp: QApplication) -> None:
    """`DAT-005` §4, through the shell's existing question rather than a second wording.

    The confirmation counts **downloads**, which is why the header reports its members: a count
    taken from the row would say 1 for a playlist of two, and a count is decoration if it does not
    count what is about to go.
    """
    from tracks_and_trails.ui.main_window import removal_question

    view = view_over([a_member("m-1", index=0), a_member("m-2", index=1)])
    removed: list[list[str]] = []
    view.removal_requested.connect(removed.append)

    view.trigger_verb("pl-1", Verb.REMOVE)

    assert removal_question(len(removed[0])) == "Remove these 2 downloads from history?"


def test_showing_a_playlists_folder_points_at_a_record_that_has_one(qapp: QApplication) -> None:
    """`UX-005` row 10: the entries share one folder, so revealing any member reveals it.

    **Re-checked when routed, not trusted from the offer** (`T140-R6`). The first member here has
    no path — a completion that recorded none — so a header that revealed `members[0]` would hand
    `FileActions` a record with no file and report a failure the user did not cause.
    """
    view = view_over(
        [
            a_member("m-1", index=0, output_path=None),
            a_member("m-2", index=1, output_path="/downloads/Trail Sounds/02.mp3"),
        ]
    )
    revealed: list[str] = []
    view.reveal_requested.connect(revealed.append)

    view.trigger_verb("pl-1", Verb.REVEAL)

    assert revealed == ["m-2"], (
        f"the header revealed {revealed}; it must point at a record that names a file rather than "
        "at whichever member happens to be first"
    )


def test_a_header_never_routes_a_verb_as_though_it_were_a_record(qapp: QApplication) -> None:
    """A group id names nothing in `history`, and must not escape the view as one.

    `Open` is the case that would: it is not offered on a header — there is no one file — so
    triggering it against one is refused rather than resolved to a member nobody chose.
    """
    view = view_over([a_member("m-1", index=0), a_member("m-2", index=1)])
    opened: list[str] = []
    view.open_requested.connect(opened.append)

    view.trigger_verb("pl-1", Verb.OPEN)

    assert opened == [], f"a group header opened {opened}, choosing one of its files for the user"


def test_a_dissolved_group_routes_nothing(qapp: QApplication) -> None:
    """A group that stopped existing between the paint and the click acts on nothing.

    An ordinary race rather than a programming error, so it is answered with silence rather than
    an exception — `QueueModel.group_jobs` states the same rule for the same reason.
    """
    view = view_over([an_entry("solo")])
    removed: list[list[str]] = []
    view.removal_requested.connect(removed.append)

    view.trigger_verb("pl-gone", Verb.REMOVE)

    assert removed == []


# --- T-159: a history row says what it got, in the window's own vocabulary ---------------------


def test_a_history_row_names_its_format_instead_of_reporting_a_yt_dlp_id(
    qapp: QApplication,
) -> None:
    """The report: *"the (251) here is useless to a regular user."*

    `251` is yt-dlp's format id for YouTube's Opus audio stream, and `format_used` means *what
    yt-dlp reported*. A merged download is worse — `399+140` is two ids joined by yt-dlp's own
    selector syntax — so the field a user reads to answer *what did I get* answered with an
    internal join expression.
    """
    from tracks_and_trails.core.presets import AUDIO_MP3, to_request

    request = to_request(
        AUDIO_MP3, url="https://example.invalid/watch?v=abc123", output_directory="/downloads"
    )
    view = view_over([an_entry("h-1", format_used="251", request=request)])

    shown = view.model.text_at("h-1", FORMAT_COLUMN)
    assert shown == AUDIO_MP3.name, (
        f"the row states its format as {shown!r}; it must use the same words the rest of the "
        "window uses for the same download"
    )
    assert "251" not in shown, "the id survived beside the name rather than being replaced"


def test_a_custom_selector_is_shown_as_itself_rather_than_as_an_id(qapp: QApplication) -> None:
    """`REQ-009`'s escape hatch, and `format_name`'s fallback rule.

    A request no built-in describes still has to say what it is rather than falling silent. The
    fallback is the **selector** — a request a user can recognise and act on — never the id, which
    is what yt-dlp resolved it to on one site on one day.
    """
    from dataclasses import replace as replace_field

    from tracks_and_trails.core.presets import AUDIO_MP3, to_request

    request = replace_field(
        to_request(
            AUDIO_MP3, url="https://example.invalid/watch?v=abc123", output_directory="/downloads"
        ),
        format_selector="bestaudio[abr>128]",
    )
    view = view_over([an_entry("h-1", format_used="251", request=request)])

    assert view.model.text_at("h-1", FORMAT_COLUMN) == "bestaudio[abr>128]"


def test_a_record_from_before_the_request_column_still_renders_honestly(
    qapp: QApplication,
) -> None:
    """The criterion, and `_text_or_absent`'s existing rule (`T-085`).

    A record written before migration `0007` has no request and nothing to reconstruct one from.
    It keeps saying what yt-dlp reported — an id labelled honestly is better than a name nobody
    wrote down — and a record with no format at all still renders as absence rather than `None`.
    """
    view = view_over(
        [
            an_entry("legacy", format_used="137+140", request=None),
            an_entry("nothing-reported", format_used=None, request=None),
        ]
    )

    assert view.model.text_at("legacy", FORMAT_COLUMN) == "137+140"
    assert view.model.text_at("nothing-reported", FORMAT_COLUMN) == UNKNOWN_TEXT


def test_the_id_yt_dlp_reported_is_still_reachable(qapp: QApplication) -> None:
    """`REQ-020` records what happened, and an id is what happened (`T-159`).

    The row names the download in words; somebody debugging one needs `399+140` and cannot get it
    from a preset's name. A tooltip is where the second reader is not charged for the first one's
    question — and it is **labelled**, because a third line reading `399+140` under a URL and a
    path is one more unexplained string rather than a fix for one.
    """
    from tracks_and_trails.core.presets import AUDIO_MP3, to_request

    request = to_request(
        AUDIO_MP3, url="https://example.invalid/watch?v=abc123", output_directory="/downloads"
    )
    view = view_over([an_entry("h-1", format_used="399+140", request=request)])
    tooltip = view.model.data(view.model.index(0, 0), Qt.ItemDataRole.ToolTipRole)

    assert f"{RAW_FORMAT_PREFIX}399+140" in tooltip, (
        f"the tooltip reads {tooltip!r}; REQ-020 records what happened, and naming the download in "
        "words must not be the same as discarding what yt-dlp answered"
    )


def test_the_queue_history_and_add_dialog_name_one_download_the_same_way(
    qapp: QApplication, tmp_path: Path
) -> None:
    """The criterion `T140-R3` required: **asserted together, so a fourth surface cannot drift.**

    This defect has been fixed twice and shipped a third time — the queue's ordinary row
    (`T126-R2`), its playlist header (`T140-R3`), and History (`T-159`) — because each fix was a
    copy of the rule rather than a use of it. One download is built here and every surface that
    describes it is asked at once.

    **They are not required to say identical strings**, and that would be the wrong assertion: the
    add dialog deliberately spells out the literal selector beside the name, because `T118-R8`'s
    promise is that *the effective selector shown stays the one that will run*. What must hold is
    that all three name it with the **same words** and that none of them shows a yt-dlp id.
    """
    from tests.ui.test_queue_view import FakeQueue, make_job
    from tracks_and_trails.core.job_state import JobStatus
    from tracks_and_trails.core.presets import AUDIO_MP3, to_request
    from tracks_and_trails.downloader.manager import DownloadManager
    from tracks_and_trails.ui.add_dialog import describe_preset
    from tracks_and_trails.ui.queue_view import QueueModel
    from tracks_and_trails.ui.row_delegate import SELECTOR_ROLE as QUEUE_SELECTOR
    from tracks_and_trails.ui.staging import Row

    url = "https://example.invalid/watch?v=abc123"
    request = to_request(AUDIO_MP3, url=url, output_directory=str(tmp_path))

    queue = FakeQueue()
    # **Completed**, which is the state a history record corresponds to — and `UX-005` §8 keeps a
    # finished download in the Queue tab until *Clear finished*, so both tabs really do describe
    # this one download at the same moment. While a row is still retargetable the queue puts the
    # name in its *control* instead of on the line (`UX-005` §6), which is a different assertion.
    queue.add(make_job("job-1", tmp_path, request=request, url=url, status=JobStatus.COMPLETED))
    manager = DownloadManager(queue)
    history = view_over([an_entry("job-1", format_used="251", request=request)])
    try:
        model = QueueModel(jobs=queue, manager=manager)
        surfaces = {
            "queue row": model.data(model.index(0, 0), QUEUE_SELECTOR),
            "history row": history.model.text_at("job-1", FORMAT_COLUMN),
            "add dialog": describe_preset(Row(url=url, generation=0), AUDIO_MP3),
        }

        for surface, said in surfaces.items():
            assert said is not None, f"{surface} says nothing about the format"
            assert AUDIO_MP3.name in said, (
                f"{surface} reads {said!r}, which does not name the download the way the other "
                "surfaces do — this is T140-R3's defect on a fourth surface"
            )
            assert "251" not in said, (
                f"{surface} reads {said!r}, which is the yt-dlp id the user was told is useless"
            )
    finally:
        manager.shutdown()
        drain(qapp, [manager])
