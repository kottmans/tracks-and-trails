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

## It reports; it still writes nothing itself

This said *"Read-only, and deliberately so: nothing here removes a record"*, and that stopped being
true at `DAT-005` (2026-08-04), which admits removal of **selected records** and never a file.
`T-125` implements it, and the sentence is corrected here rather than left standing as a comment
that used to be right (`T124-R1` found the drawn `⋯` inert while this paragraph said removal did
not exist at all).

What is unchanged is where the write happens: this view **reports** a removal through
`removal_requested` and composition performs it, exactly as the queue reports its own verbs
(`ARCHITECTURE.md` §7). `T-086`'s open-and-reveal is reported the same way.

## No live signals, unlike the queue

`QueueModel` coalesces a stream of progress on a timer because a running job changes several times a
second. A history row is written once, by the completion transaction (`T050-R1`), and never changes
again — so this reads on construction and on an explicit `refresh()`, and has no timer, no
subscription and nothing to detach. Composition refreshes it when a job completes and when the queue
is cleared, which are the only two moments the set of rows can differ.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Protocol

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QPoint, Qt, Signal
from PySide6.QtCore import QPersistentModelIndex as _PersistentIndex
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListView,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.ui.job_detail import UNKNOWN_TEXT, format_bytes
from tracks_and_trails.ui.row_delegate import (
    DETAIL_ROLE,
    HEADLINE_ROLE,
    HUE_ROLE,
    JOB_ID_ROLE,
    SELECTOR_ROLE,
    STATE_ROLE,
    THUMBNAIL_URL_ROLE,
    VERBS_ROLE,
    RowDelegate,
)
from tracks_and_trails.ui.row_verbs import Verb
from tracks_and_trails.ui.staging import placeholder_hue
from tracks_and_trails.ui.thumbnails import ThumbnailLoader, ThumbnailStore

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

    def download_count(self) -> int:
        """How many records History holds. One per row here — it has no groups (`T-140`)."""
        return len(self._entries)

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
        """**One**, since `UX-005` (`T-124`).

        The six columns are gone from the *view* and survive as what the row says — `_text` and
        `COLUMN_HEADERS` are still the source of every string above, which is what keeps
        `REQ-020`'s fields named in one place. A list draws column 0, so the model offers one.
        """
        return 0 if parent.isValid() else 1

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

        # **The delegate's roles, composed from the very cells `_text` answers** (`UX-005` §3,
        # `T-124`). History changes what the fields *say*, not what they are: where the queue row
        # shows progress and speed, this shows the saved path, the size and when. Each branch is
        # built from `_text` rather than from the record directly, so the row and a screen reader
        # cannot come to disagree — `QueueModel` states the same reasoning for the same reason.
        if role == HEADLINE_ROLE:
            return self._text(entry, TITLE_COLUMN)
        if role == DETAIL_ROLE:
            return " — ".join((self._text(entry, SIZE_COLUMN), self._text(entry, COMPLETED_COLUMN)))
        if role == STATE_ROLE:
            return self._text(entry, FORMAT_COLUMN)
        if role == SELECTOR_ROLE:
            # The saved path, on the row's own last line. `UX-005` §3 names it as one of the three
            # things history says, and it is the one a person copies into a bug report.
            return self._text(entry, PATH_COLUMN)
        if role == THUMBNAIL_URL_ROLE:
            # **History carries its own** (`T-138`, `UX-005` §3). It used to answer nothing, on
            # the recorded premise that "a history record carries no thumbnail URL" — true until
            # migration `0005` gave it one, and the reason the same download drew a picture in the
            # queue and a derived tile here the moment it finished.
            return self._entries[index.row()].thumbnail_url
        if role == HUE_ROLE:
            return placeholder_hue(entry.url)
        if role == JOB_ID_ROLE:
            return entry.id
        if role == VERBS_ROLE:
            # **Not `verbs_for`**, which answers for a `JobStatus`, and a history record has none:
            # it is not a job in a pipeline, it is what happened. `REQ-021` names the two things a
            # user does with a finished download and there is no third — removing one is `T-125`
            # and needs a `DAT-` decision before a button exists for it (`UX-005`).
            # `DAT-005` unblocked the third (2026-08-04). Before it, offering `Remove` would have
            # *been* the decision about what removal means — which is why `UX-005` §9 described the
            # control and refused to specify it.
            return (Verb.OPEN, Verb.REVEAL, Verb.REMOVE)

        if role == Qt.ItemDataRole.DisplayRole:
            return self._text(entry, index.column())
        if role == Qt.ItemDataRole.AccessibleTextRole:
            # **The whole row**, since `UX-005` made this a list (`T-124`). It used to name the
            # column — "Format: 137+140" — because a bare value out of six columns says nothing
            # about which field is being heard. There is one column now, and the equivalent of
            # naming the field is reading every field `REQ-020` names, in one sentence.
            # `QueueModel._whole_row` does the same thing for the same reason.
            return self._whole_row(entry)
        if role == Qt.ItemDataRole.ToolTipRole:
            # **The URL and the path in full**, which is what somebody copying either into a bug
            # report needs. They were per-column tooltips because both are routinely wider than
            # their column; on a row, the path is drawn on the last line and clipped when it is
            # long, so the need is unchanged and the tooltip is where it is met.
            return "\n".join((self._text(entry, URL_COLUMN), self._text(entry, PATH_COLUMN)))
        return None

    def _whole_row(self, entry: HistoryEntry) -> str:
        """Every field `REQ-020` names, in the order the row shows them.

        Built from `_text` and `COLUMN_HEADERS`, so the spoken row and the drawn row are two
        renderings of one set of cells rather than two descriptions that can drift.
        """
        return ", ".join(
            f"{COLUMN_HEADERS[column]}: {self._text(entry, column)}"
            for column in range(len(COLUMN_HEADERS))
        )

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

    def __init__(
        self,
        *,
        history: HistoryReader,
        parent: QWidget | None = None,
        thumbnail_loader: ThumbnailLoader | None = None,
        cache_root: Path | None = None,
    ) -> None:
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

        # **A list behind `RowDelegate`, not a six-column table** (`UX-005` §3, `T-124`). The
        # columns were `T-100`'s and they were right for a table; `UX-005` makes both tabs the
        # same row anatomy, so a user reads one shape rather than two. The fields `REQ-020` names
        # all survive — `_text` still produces every one of them — as *what the row says*.
        self._table = QListView(self)
        self._table.setObjectName("historyTable")
        self._table.setAccessibleName("Download history")
        self._table.setAccessibleDescription(
            "Completed downloads, most recent first. Files are not removed from disk by anything "
            "in this list."
        )
        self._table.setModel(self._model)
        # **Extended, since `DAT-005`**: removal is selection-scoped and its verb names its own
        # count, and a count is decoration if only one row can ever be selected.
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        # Read-only, and not merely unedited: `REQ-020` is a record of what happened, and an
        # editable view would also put a text cursor into the keyboard order.
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setUniformItemSizes(True)
        # **The overflow's keyboard route** (`UX-005` §4, `T124-R1`). Qt raises
        # `customContextMenuRequested` for the Menu key and Shift+F10 as well as for the mouse, so
        # one connection makes `⋯` reachable both ways. `FileActions` is told not to install its
        # own menu on this table, because two menus on one gesture is worse than either.
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._row_menu_asked_for)
        # **A store of its own** (`T-138`). This said "no thumbnail store: a history record
        # carries no thumbnail URL", which migration `0005` made false — and until it did, the
        # same download drew its picture in the queue and a derived tile here, one row apart.
        #
        # Its own rather than the queue's: the two views are built independently and neither owns
        # the other, and the **disk** cache is shared anyway — `thumbnail_cache_path` keys by URL,
        # so a picture fetched for a queue row is already on disk when History asks for it. What
        # is duplicated is an in-memory cache and a thread pool, which is what `T-119` sized per
        # view.
        self._thumbnails = ThumbnailStore(
            loader=thumbnail_loader, cache_root=cache_root, parent=self
        )
        self._delegate = RowDelegate(thumbnails=self._thumbnails, parent=self._table)
        self._table.setItemDelegate(self._delegate)
        self._thumbnails.ready.connect(self._on_thumbnail_ready)
        # **The pointer is watched so the row's verbs can react to it** (`T-134`). Not a
        # default: a viewport's mouse tracking is off, so without this Qt reports the
        # pointer only while a button is held.
        self._delegate.verb_triggered.connect(self._on_verb)
        layout.addWidget(self._table)

        # **The paint-time overflow record does not survive a reset** (`T-135`). A job that
        # left the queue would otherwise keep an entry keyed by its id, and rows that
        # scroll out of view are never repainted to correct it.
        self._model.modelReset.connect(self._delegate.forget_dropped)
        self._model.modelReset.connect(self._show_the_right_thing)
        self._show_the_right_thing()

    #: `(entry_id)` — a row's file verb was activated. Reported rather than performed, because
    #: `FileActions` owns containment (`SEC-001`) and the shell owns `FileActions`.
    open_requested = Signal(str)
    reveal_requested = Signal(str)

    #: `(entry_ids)` — the user asked to remove what they selected (`DAT-005`, `UX-005` §9).
    #: **The whole selection**, not the row the verb was drawn on: `DAT-005` scopes removal to the
    #: selection and makes the verb name its own count, so sending one id would make the count a
    #: decoration.
    removal_requested = Signal(list)

    #: `(entry_id)` — the row's `⋯` was activated, by pointer or by keyboard (`T124-R1`).
    #: The queue's signal of the same name, for the same reason: what belongs in the overflow is a
    #: shell question, and the shell builds one menu for both tabs.
    #: A row asked for its menu: the row's id, and **what the menu should hold** (`T-135`).
    #:
    #: The contents travel with the request because the two routes want different things and only
    #: this widget can tell them apart. The `⋯` button holds what the row could not draw — that is
    #: what it is for, and listing everything there offered the same actions twice on any row wide
    #: enough to show them. The Menu key, Shift+F10 and a right-click hold **everything the state
    #: permits**, because they are not asking about the row's width.
    more_requested = Signal(str, object)

    def _on_verb(self, entry_id: str, verb: object) -> None:
        """Route a history row's verb, or its overflow. An unrouted verb is a programming error.

        Three verbs and the `⋯`, which the delegate reports as `None`. *(This said "only two
        exist" — written when it was true, and still there after `DAT-005` added *Remove*, in the
        method whose missing `None` branch made the `⋯` inert.)*
        """
        if verb is None:
            # **The drawn `⋯` did nothing at all until `T124-R1`.** The delegate emits `None` for
            # the overflow and this method's final branch tested `verb is not None`, so the one
            # control every history row draws was inert — with a pointer as well as without one.
            # `QueueView._on_verb` had the branch; this is the same route, added where it was
            # missing rather than a second one beside it.
            self.more_requested.emit(entry_id, self._delegate.overflowing(entry_id))
            return
        if verb is Verb.OPEN:
            self.open_requested.emit(entry_id)
        elif verb is Verb.REVEAL:
            self.reveal_requested.emit(entry_id)
        elif verb is Verb.REMOVE:
            # **The selection, and the row that was clicked if it is not in it.** A user who
            # clicks Remove on an unselected row means that row; one who has three selected and
            # clicks Remove on one of them means the three (`DAT-005` §1).
            selected = self.selected_entry_ids()
            self.removal_requested.emit(list(selected) if entry_id in selected else [entry_id])
        else:
            raise AssertionError(f"a history row offered {verb!r} and nothing routes it")

    def trigger_verb(self, entry_id: str, verb: Verb) -> None:
        """Activate a verb from the overflow or a key, by the route a click takes."""
        self._on_verb(entry_id, verb)

    def verbs_of(self, entry_id: str) -> tuple[Verb, ...]:
        """What the row for `entry_id` offers, asked of the model the delegate asks (`T124-R1`).

        **Read through the role rather than recomputed**, for `QueueView.verbs_of`'s reason: the
        overflow exists to hold what the row could not fit, so a menu that disagreed with the row
        would be worse than no menu. Empty for a record this view does not hold.
        """
        ids = self._model.entry_ids()
        if entry_id not in ids:
            return ()
        offered = self._model.data(self._model.index(ids.index(entry_id), 0), VERBS_ROLE)
        return tuple(offered or ())

    def _on_thumbnail_ready(self, _url: str) -> None:
        """A picture arrived, so the rows showing it repaint (`T-138`).

        The same shape as `QueueView._on_thumbnail_ready`: the *history* did not change, so this
        repaints rather than refreshing — a reset here would discard the selection a user made
        while a picture was still loading.
        """
        count = self._model.rowCount()
        if count:
            self._model.dataChanged.emit(self._model.index(0, 0), self._model.index(count - 1, 0))

    def _row_menu_asked_for(self, position: QPoint) -> None:
        """The Menu key, Shift+F10 or a right-click asked for a row's overflow (`T124-R1`).

        `QueueView._row_menu_asked_for` is the same method for the same reason, including the
        fall back to the current row when the position names none — which is the keyboard case,
        and which is what makes **history removal keyboard-reachable at all**. Before this the
        only route to *Remove* was a pointer on a control that did nothing.
        """
        at = self._table.indexAt(position)
        index = at if at.isValid() else self._table.currentIndex()
        if not index.isValid():
            return
        entry_id = self._model.data(index, JOB_ID_ROLE)
        if isinstance(entry_id, str) and entry_id:
            # Everything: see `QueueView`'s twin. A keyboard route must not depend on the width.
            self.more_requested.emit(entry_id, self.verbs_of(entry_id))

    @property
    def model(self) -> HistoryModel:
        return self._model

    @property
    def table(self) -> QListView:
        return self._table

    @property
    def shows_empty_notice(self) -> bool:
        return not self._empty.isHidden()

    def empty_text(self) -> str:
        return self._empty.text()

    def refresh(self) -> None:
        self._model.refresh()

    def selected_entry_id(self) -> str | None:
        """Which record is selected, or `None`. **`T-086` is what this exists for.**

        `selectedIndexes` rather than `selectedRows`: a `QListView` has one column, and
        `selectedRows` is a table-shaped question that returns nothing here.
        """
        indexes = self._table.selectionModel().selectedIndexes()
        if not indexes:
            return None
        return self._model.entry_ids()[indexes[0].row()]

    def selected_entry_ids(self) -> tuple[str, ...]:
        """Every selected record, in the order the list shows them.

        `DAT-005` §1 scopes removal to the selection, so this is what the verb acts on and what
        its count counts. Ordered by row rather than by click, because a confirmation naming three
        downloads should list them the way they are on screen.
        """
        ids = self._model.entry_ids()
        rows = sorted(index.row() for index in self._table.selectionModel().selectedIndexes())
        return tuple(ids[row] for row in rows if 0 <= row < len(ids))

    def select(self, entry_id: str) -> bool:
        """Select the row for `entry_id`, so a named verb can act through the selection."""
        ids = self._model.entry_ids()
        if entry_id not in ids:
            return False
        self._table.setCurrentIndex(self._model.index(ids.index(entry_id), 0))
        return True

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


def build_history_view(
    history: HistoryReader,
    *,
    thumbnail_loader: ThumbnailLoader | None = None,
    cache_root: Path | None = None,
) -> HistoryView:
    """Construct the view. A named function for `build_queue_view`'s reason.

    There is nothing to wire yet — `T-086` adds open-and-reveal, and this is where that wiring
    decision will live rather than being buried in composition.
    """
    return HistoryView(history=history, thumbnail_loader=thumbnail_loader, cache_root=cache_root)
