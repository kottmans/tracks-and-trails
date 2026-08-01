"""What was obtained, after the queue has forgotten it (`T-100`, `REQ-020`, `REQ-021`).

## Why this exists at all

`P2PLAN-R8` found the history view had no owner in any phase: Phase 2's deliverables named the
records, Phase 3 is format depth, Phase 4 is settings, and `T-050` pointed at a "Phase 3"
deliverable that has never existed.

**Phase 2's own features combine into a hole without it.** `UX-001` says remove never deletes a
file; `T-081` delivers clear-completed. Together, in a Phase 2 with no history view, the user clears
their completed jobs, every file is still on disk, and **the application can no longer say where any
of it went**. That is this phase losing information the user needs, not a polish gap.

`REQ-021` — *open a completed file, or reveal it, from the **history and queue views*** —
presupposes this view and is a Phase 2 deliverable, which settles where it belongs.

## `HistoryEntry` is imported for typing only

`ARCHITECTURE.md` §3 has `ui/` depend on the *shape* of a repository rather than on `persistence`,
which is why `HistoryReader` is a protocol. The entry type is still needed to say what that protocol
returns, so it is imported under `TYPE_CHECKING`: the annotation is complete and **no runtime edge
from `ui/` to `persistence/` is created**. `app.py` supplies the concrete repository, as it does for
every other reader.

## Read-only, and deliberately so

Nothing here removes a record. `REQ-020` is a record of what was obtained, and pruning it is not in
any phase. `T-086` adds open-and-reveal *onto* this view; that is the only thing meant to grow here.

## No live signals, unlike the queue

`QueueModel` coalesces a stream of progress on a timer because a running job changes several times a
second. A history row is written once, by the completion transaction (`T050-R1`), and never changes
again — so this reads on construction and on an explicit `refresh()`, and has no timer, no
subscription and nothing to detach. Composition refreshes it when a job completes and when the queue
is cleared, which are the only two moments the set of rows can differ.
"""

from typing import TYPE_CHECKING, Any, Final, Protocol

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt
from PySide6.QtCore import QPersistentModelIndex as _PersistentIndex
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.ui.job_detail import UNKNOWN_TEXT, format_bytes

if TYPE_CHECKING:
    from tracks_and_trails.persistence.repositories import HistoryEntry

#: The columns, in order. **Transcribed from `REQ-020` rather than generated from `HistoryEntry`'s
#: fields**, for the reason `COLUMN_HEADERS` gives one module over: the requirement names six things
#: a user must be able to see, and deriving the list from the dataclass would let a renamed or
#: dropped attribute quietly change what is on screen (`ai/TESTING.md` §13).
COLUMN_HEADERS: Final = ("Title", "Source URL", "Saved to", "Format", "Size", "Completed")

TITLE_COLUMN: Final = 0
URL_COLUMN: Final = 1
PATH_COLUMN: Final = 2
FORMAT_COLUMN: Final = 3
SIZE_COLUMN: Final = 4
COMPLETED_COLUMN: Final = 5

#: What an empty history says. A user who has downloaded nothing and a view that failed to load look
#: identical without it — the same reason the queue has one.
EMPTY_TEXT: Final = "Nothing downloaded yet. Completed downloads are listed here."

#: How a completion time is written. Seconds are dropped: this is a record of what happened, not a
#: measurement, and a column of times to the second is harder to scan for no gain.
COMPLETED_FORMAT: Final = "%Y-%m-%d %H:%M"

_ROOT: Final = QModelIndex()


class HistoryReader(Protocol):
    """The one read this view needs, named as a protocol (`ARCHITECTURE.md` §3).

    `ui/` depends on the shape of a repository rather than on `persistence`, exactly as `JobReader`
    and `QueueReader` do. `HistoryRepository` satisfies it; so does a list in a test.
    """

    def all_entries(self) -> list[HistoryEntry]: ...


def _text_or_absent(value: str | None) -> str:
    """A nullable string as itself, or `UNKNOWN_TEXT`.

    **`str(None)` reaching a cell is the defect this exists to prevent.** `title`, `output_path` and
    `format_used` are all nullable by design (`T-085`) — `format_used` specifically means "yt-dlp
    reported none", and printing `None` in a column headed *Format* tells the user a lie about a
    field that is honestly empty.
    """
    return value if value else UNKNOWN_TEXT


class HistoryModel(QAbstractTableModel):
    """Every completed download, newest first."""

    def __init__(self, *, history: HistoryReader, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._history = history
        self._entries: list[HistoryEntry] = []
        self.refresh()

    # --- the promises tests read -----------------------------------------------------------

    def entry_ids(self) -> tuple[str, ...]:
        """The rows, in the order they are shown."""
        return tuple(entry.id for entry in self._entries)

    def text_at(self, entry_id: str, column: int) -> str | None:
        """What one cell says, by entry rather than by row index.

        By id for `QueueModel.text_at`'s reason: a test that indexed by row would silently follow a
        reordering rather than noticing it, and the order is one of this view's own criteria.
        """
        for row, entry in enumerate(self._entries):
            if entry.id == entry_id:
                return self._text(self._entries[row], column)
        return None

    # --- Qt's model interface ---------------------------------------------------------------

    def rowCount(self, parent: QModelIndex | _PersistentIndex = _ROOT) -> int:
        return 0 if parent.isValid() else len(self._entries)

    def columnCount(self, parent: QModelIndex | _PersistentIndex = _ROOT) -> int:
        return 0 if parent.isValid() else len(COLUMN_HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        return COLUMN_HEADERS[section]

    def data(
        self,
        index: QModelIndex | _PersistentIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._entries):
            return None
        entry = self._entries[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._text(entry, index.column())
        if role == Qt.ItemDataRole.AccessibleTextRole:
            # `NFR-005`: a screen reader reads the cell, and a bare value with no column name is
            # not usable in a six-column table.
            return f"{COLUMN_HEADERS[index.column()]}: {self._text(entry, index.column())}"
        if role == Qt.ItemDataRole.ToolTipRole and index.column() in (URL_COLUMN, PATH_COLUMN):
            # Both are routinely wider than their column. The tooltip is the whole value, which is
            # also what somebody copying a path into a bug report needs.
            return self._text(entry, index.column())
        return None

    def _text(self, entry: HistoryEntry, column: int) -> str:
        """One cell, from the record rather than from anything live.

        Ordered by column constant rather than by a lookup table, so a new column is a compile-time
        shaped change here and in `COLUMN_HEADERS` together.
        """
        if column == TITLE_COLUMN:
            return _text_or_absent(entry.title)
        if column == URL_COLUMN:
            # Never absent: `HistoryEntry.__post_init__` refuses a record without it, because
            # `REQ-020` names it and a retry cannot reconstruct it.
            return entry.url
        if column == PATH_COLUMN:
            return _text_or_absent(entry.output_path)
        if column == FORMAT_COLUMN:
            return _text_or_absent(entry.format_used)
        if column == SIZE_COLUMN:
            # The same function the queue and the detail view use, so one download is described
            # identically wherever it appears.
            return format_bytes(entry.bytes_total)
        if column == COMPLETED_COLUMN:
            return entry.completed_at.strftime(COMPLETED_FORMAT)
        return ""

    def path_for(self, entry_id: str) -> str | None:
        """Where the file was written, or `None`. **Not `text_at(PATH_COLUMN)`** (`T-086`).

        That renders `UNKNOWN_TEXT` for a record with no path, which is right on screen and would
        be catastrophic as a filename — `open_file` would be handed the em-dash placeholder and
        refuse it for the wrong reason, reporting that a file named "—" is missing.
        """
        for entry in self._entries:
            if entry.id == entry_id:
                return entry.output_path
        return None

    def refresh(self) -> None:
        """Re-read every entry.

        A full reset rather than a diff: history changes when a download completes — rarely, and
        never in a burst — and there is no live state on a row to preserve across the rebuild, which
        is the one thing `QueueModel.refresh` has to be careful about.

        **The order is the repository's**, not this view's. `all_entries()` sorts by
        `completed_at DESC, id`; re-sorting here would be a second opinion about "newest" that could
        drift from the one the data has.
        """
        self.beginResetModel()
        self._entries = list(self._history.all_entries())
        self.endResetModel()


class HistoryView(QWidget):
    """The table, plus the notice that stands in for it when there is nothing to show."""

    def __init__(self, *, history: HistoryReader, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("historyView")
        self._model = HistoryModel(history=history, parent=self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._empty = QLabel(EMPTY_TEXT, self)
        self._empty.setObjectName("historyEmptyNotice")
        self._empty.setAccessibleName("History is empty")
        self._empty.setTextFormat(Qt.TextFormat.PlainText)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty)

        self._table = QTableView(self)
        self._table.setObjectName("historyTable")
        self._table.setAccessibleName("Download history")
        self._table.setAccessibleDescription(
            "Completed downloads, most recent first. Files are not removed from disk by anything "
            "in this list."
        )
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        # Read-only, and not merely unedited: `REQ-020` is a record of what happened, and an
        # editable view would also put a text cursor into the keyboard order.
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            TITLE_COLUMN, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._table)

        self._model.modelReset.connect(self._show_the_right_thing)
        self._show_the_right_thing()

    @property
    def model(self) -> HistoryModel:
        return self._model

    @property
    def table(self) -> QTableView:
        return self._table

    @property
    def shows_empty_notice(self) -> bool:
        return not self._empty.isHidden()

    def empty_text(self) -> str:
        return self._empty.text()

    def refresh(self) -> None:
        self._model.refresh()

    def selected_entry_id(self) -> str | None:
        """Which record is selected, or `None`. **`T-086` is what this exists for.**"""
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        return self._model.entry_ids()[rows[0].row()]

    def selected_path(self) -> str | None:
        """The selected record's file, or `None`. **`T-086`'s one question of this view.**"""
        entry_id = self.selected_entry_id()
        return None if entry_id is None else self._model.path_for(entry_id)

    def focus_chain(self) -> list[QWidget]:
        """The keyboard order, per state (`NFR-005`, `T-060`'s rule).

        The table is not in the chain when it is hidden: naming a widget the user cannot see is
        exactly what `T-060` found the queue doing.
        """
        return [self._table] if self._model.rowCount() else []

    def _show_the_right_thing(self) -> None:
        """The table when there are rows, the notice when there are none. Never both."""
        has_rows = self._model.rowCount() > 0
        self._table.setVisible(has_rows)
        self._empty.setVisible(not has_rows)


def build_history_view(history: HistoryReader) -> HistoryView:
    """Construct the view. A named function for `build_queue_view`'s reason.

    There is nothing to wire yet — `T-086` adds open-and-reveal, and this is where that wiring
    decision will live rather than being buried in composition.
    """
    return HistoryView(history=history)
