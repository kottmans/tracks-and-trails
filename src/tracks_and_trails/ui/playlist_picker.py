"""Choose which entries of a probed playlist to enqueue (`REQ-004`, `T-110`).

`REQ-004`: *for a playlist, let the user select which entries to enqueue, including select-all and
range selection, before any download starts.* `docs/UX_SPEC.md` §7 is the surface, and `UX-007`
ruled its three open questions on 2026-08-07:

- **`P-19`** — the picker is the **staging list's own row, opened**, not a separate dialog. It is
  the same mechanism `P-1` gives the format table, so `ui/add_dialog.py` mounts this widget through
  the very machinery that mounts `FormatTable`. Two surfaces, one panel.
- **`P-5`** — each entry carries a **checkbox**, and the group header carries a **tri-state**
  checkbox reflecting its members.
- **`P-25`** — **no filtering by title or duration.** A picker that hides entries can lie about
  what *select all* did, so there is nothing here to hide them with.

## The selection is a value, and it does not live in this widget

`PlaylistSelection` (`ui/playlist_selection.py`) holds the choice and is Qt-free, so `REQ-004`'s
two named operations are asserted directly rather than through a table view. This widget owns a
current value, announces every change, and is the only thing that knows about Qt.

## What `Space` toggles, and why the answer is "everything selected"

`docs/UX_SPEC.md` §7 gives `Shift`+`↑` `↓` to *extend a range* and `Space` to *toggle the current
entry*. Qt's `ExtendedSelection` already implements the first — it is the platform convention the
spec says it is transcribing — so the range that `Shift`+`↑` builds is the view's **selection**,
and the thing `Space` acts on has to be that selection or the range would extend to nothing.

With one row selected the two readings coincide, which is the case the spec's wording describes.
With several, toggling only the current one would make the declared range key do nothing a user
could see — `UX-005` §5's defect, and `T-152`'s: a route that is declared and unreachable.

**A mixed range is set, not inverted.** If every selected entry is checked, `Space` unchecks them
all; otherwise it checks them all. Inverting would leave a range the user just swept containing
both states, which is not what one keystroke should mean.

## `Ctrl`+`A` checks, it does not merely highlight

Qt's `Ctrl`+`A` selects every row. `REQ-004` asks for **select-all** as a thing that decides what
gets enqueued, so here it checks every entry as well — a select-all that only highlights would
satisfy the key and not the requirement.
"""

from collections.abc import Sequence
from typing import Any, Final

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSize, Qt, Signal
from PySide6.QtCore import QPersistentModelIndex as _PersistentIndex
from PySide6.QtGui import QKeyEvent, QWheelEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHeaderView,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core.models import PlaylistEntry
from tracks_and_trails.ui.playlist_selection import (
    GroupCheck,
    PlaylistSelection,
    describe_playlist,
)

#: The columns, in the order `T-110`'s acceptance criterion names the fields it needs to choose by:
#: *"title, duration, index"*. The index leads because it is what orders the playlist and what the
#: queue will show; a tuple rather than an enum of positions, for `format_table`'s reason — the
#: header text and the column order are one fact.
COLUMN_HEADERS: Final = ("#", "Title", "Duration")

INDEX_COLUMN: Final = 0
TITLE_COLUMN: Final = 1
DURATION_COLUMN: Final = 2

COLUMN_COUNT: Final = len(COLUMN_HEADERS)

#: What the tri-state group header reads (`P-5`). Named once because the label and the accessible
#: name are the same sentence.
GROUP_TEXT: Final = "Every entry"

#: How many entries the table shows before it starts scrolling inside itself (`T-193`).
#:
#: **The panel had no height of its own**, so it inherited `QTableView`'s fixed default hint — the
#: same height for a two-entry playlist and a sixteen-entry one. A real sixteen-track album showed
#: **two rows**, with the other fourteen behind the table's own scrollbar *inside* the staging
#: list's, which is two scrollbars in one gesture.
#:
#: Eight is chosen against the dialog rather than picked: the staging list is the shorter half of a
#: window that opens around 700px, and eight rows plus the group control and the header is most of
#: what it can give without the panel becoming the dialog. Below eight nothing scrolls at all,
#: which is the case that matters — most playlists a user pastes are shorter than this.
VISIBLE_ENTRIES: Final = 8

#: The fewest entries the table will shrink to before the panel stops compressing (`T-209`).
#:
#: **Two, so the table is visibly a list rather than a single row.** Below the cap the panel asks
#: for `VISIBLE_ENTRIES`; in a window too short for that, the entries give way — the summary says
#: which row this is and *Done* is the way out, so neither of those may be what shrinks.
MINIMUM_ENTRIES: Final = 2

#: `Qt.CheckState` for each of `GroupCheck`'s three answers. A mapping rather than a chain of
#: conditionals so the three-valued shape survives contact with Qt's own three-valued type.
_GROUP_STATES: Final = {
    GroupCheck.ALL: Qt.CheckState.Checked,
    GroupCheck.SOME: Qt.CheckState.PartiallyChecked,
    GroupCheck.NONE: Qt.CheckState.Unchecked,
}

_ROOT: Final = QModelIndex()


def _duration_text(seconds: float | None) -> str:
    """`H:MM:SS`, through the dialog's own formatter.

    Imported inside the function because `ui/add_dialog.py` imports this module, and `job_detail`
    and `queue_view` already reach `format_duration` exactly this way — one renderer for a
    duration across every surface, which is the property that matters, and a deferred import is
    what this project already pays for it.
    """
    from tracks_and_trails.ui.add_dialog import format_duration

    return format_duration(seconds)


class PlaylistEntryModel(QAbstractTableModel):
    """The entries a probe enumerated, each with a checkbox (`P-5`).

    **The model holds the selection**, because Qt asks it for the check state and would otherwise
    be asking the widget through the model — two owners for one fact. The widget reads it back and
    the panel above reads it from the widget, so there is exactly one copy.
    """

    #: `PlaylistSelection` — what is chosen now, after any change.
    selection_changed = Signal(object)

    def __init__(
        self,
        entries: Sequence[PlaylistEntry] = (),
        selection: PlaylistSelection | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._entries = tuple(entries)
        self._selection = (
            PlaylistSelection.all_of(len(self._entries))
            if selection is None
            else selection.with_count(len(self._entries))
        )

    # Qt's override names, hence the camelCase.
    def rowCount(self, parent: QModelIndex | _PersistentIndex = _ROOT) -> int:
        return 0 if parent.isValid() else len(self._entries)

    def columnCount(self, parent: QModelIndex | _PersistentIndex = _ROOT) -> int:
        return 0 if parent.isValid() else COLUMN_COUNT

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole or orientation is not Qt.Orientation.Horizontal:
            return None
        return COLUMN_HEADERS[section] if 0 <= section < COLUMN_COUNT else None

    def data(
        self, index: QModelIndex | _PersistentIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if not index.isValid():
            return None
        row = index.row()
        if not 0 <= row < len(self._entries):
            return None
        entry = self._entries[row]

        if role == Qt.ItemDataRole.CheckStateRole and index.column() == INDEX_COLUMN:
            checked = self._selection.is_checked(row)
            return Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == INDEX_COLUMN:
                # One-based, because it is the position a user reads off a playlist page.
                return str(row + 1)
            if index.column() == TITLE_COLUMN:
                return entry.title
            if index.column() == DURATION_COLUMN:
                return _duration_text(entry.duration_seconds)
            return None
        if role == Qt.ItemDataRole.AccessibleTextRole:
            # **The whole row in one sentence, including whether it is chosen** (`NFR-005`). A
            # screen reader announces the check state of the cell it is on; a user arrowing down
            # the title column would otherwise hear titles and never hear what they had picked.
            state = "chosen" if self._selection.is_checked(row) else "not chosen"
            return (
                f"{row + 1}. {entry.title}. {_duration_text(entry.duration_seconds)}. {state}. "
                "Press Space to change."
            )
        return None

    def setData(
        self,
        index: QModelIndex | _PersistentIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        """A pointer clicking one checkbox. The keyboard routes come through `set_checked`."""
        if role != Qt.ItemDataRole.CheckStateRole or index.column() != INDEX_COLUMN:
            return False
        if not index.isValid() or not 0 <= index.row() < len(self._entries):
            return False
        # Qt hands back an `int` here rather than the enum it was given, exactly as `T-109` found
        # for `currentData()`: comparing against `Qt.CheckState.Checked` directly is a comparison
        # that is always false, and the control would look like a choice and change nothing.
        self.set_checked((index.row(),), int(value) == int(Qt.CheckState.Checked.value))
        return True

    def flags(self, index: QModelIndex | _PersistentIndex) -> Qt.ItemFlag:
        base = super().flags(index)
        if index.isValid() and index.column() == INDEX_COLUMN:
            return base | Qt.ItemFlag.ItemIsUserCheckable
        return base

    # --- the seam the widget drives -------------------------------------------------------

    @property
    def entries(self) -> tuple[PlaylistEntry, ...]:
        return self._entries

    @property
    def selection(self) -> PlaylistSelection:
        return self._selection

    def set_checked(self, rows: Sequence[int], checked: bool) -> None:
        """Check or uncheck a set of rows in one step (`REQ-004`'s range selection)."""
        self._apply(self._selection.set_many(rows, checked))

    def toggle_rows(self, rows: Sequence[int]) -> None:
        """`Space`: set the whole run rather than invert it — see this module's docstring."""
        if not rows:
            return
        every = all(self._selection.is_checked(row) for row in rows)
        self._apply(self._selection.set_many(rows, not every))

    def select_all(self) -> None:
        self._apply(self._selection.select_all())

    def clear_selection(self) -> None:
        self._apply(self._selection.clear())

    def set_group(self, checked: bool) -> None:
        """The tri-state header, clicked. Partially checked resolves to *all* (`P-5`)."""
        self._apply(self._selection.select_all() if checked else self._selection.clear())

    def _apply(self, selection: PlaylistSelection) -> None:
        if selection == self._selection:
            return
        self._selection = selection
        rows = max(len(self._entries) - 1, 0)
        if self._entries:
            self.dataChanged.emit(
                self.index(0, INDEX_COLUMN),
                self.index(rows, COLUMN_COUNT - 1),
                [Qt.ItemDataRole.CheckStateRole, Qt.ItemDataRole.AccessibleTextRole],
            )
        self.selection_changed.emit(selection)


class EntryTable(QTableView):
    """The entry list, with the keyboard `docs/UX_SPEC.md` §7 declares.

    A subclass rather than an event filter, for `SortableHeader`'s reason: two of these keys have
    to *replace* what Qt does with them, and a filter that let the default through afterwards would
    give `Ctrl`+`A` a highlight and a check that disagree.
    """

    def sizeHint(self) -> QSize:
        """As tall as its rows, up to `VISIBLE_ENTRIES` (`T-193`).

        **Asked of the rows rather than guessed**, for the reason `AddUrlDialog.panel_height_for`
        gives about constants: a fixed number here would be a second opinion about how tall a row
        is, and the first font change would make it the wrong one (`T118-R15`).

        `QTableView`'s inherited hint is a fixed default that ignores the model entirely, which is
        why a sixteen-entry playlist was drawn at the height of a two-entry one. Capped so a
        200-track playlist does not ask for a 6,000px row; the table scrolls inside the cap, and
        below it nothing scrolls at all.
        """
        hint = super().sizeHint()
        # `model()` is non-optional in the stubs, so guarding it is a `redundant-expr` error —
        # the same shape `P3EXIT-R2` caught in `T-192`'s test.
        model = self.model()
        if not model.rowCount():
            return hint
        rows = min(model.rowCount(), VISIBLE_ENTRIES)
        header = self.horizontalHeader()
        # **`isHidden()`, not `isVisible()`** (`T193-R1`). A widget is not *visible* until every
        # ancestor is shown, and this hint is asked **before the picker is mounted** — so
        # `isVisible()` answered "has this been shown yet", omitted the header's height, and left
        # every picker up to eight entries with a scroll range it should not have had. `isHidden()`
        # reports what was *configured*: it is `False` for a header nobody hid, mounted or not, and
        # becomes `True` only if one is hidden deliberately. The vertical header is hidden that way
        # in `_build`; this one never is.
        wanted = (
            (0 if header.isHidden() else header.sizeHint().height())
            + sum(self.rowHeight(row) for row in range(rows))
            + 2 * self.frameWidth()
        )
        return QSize(hint.width(), wanted)

    def minimumSizeHint(self) -> QSize:
        """Small enough that the panel can fit a short window (`T-209`).

        **`sizeHint` is what the table wants; this is what it will accept.** Qt takes the larger of
        a widget's minimum and its parent's remaining space, so a table whose minimum equalled its
        preferred height made the whole panel incompressible — and the panel then overflowed the
        list, taking its own *Done* button below the fold.

        `MINIMUM_ENTRIES` rows, because a picker showing nothing is not worth opening: the entries
        compress, and the summary and *Done* do not.
        """
        hint = super().minimumSizeHint()
        model = self.model()
        rows = min(model.rowCount(), MINIMUM_ENTRIES)
        if not rows:
            return hint
        header = self.horizontalHeader()
        wanted = (
            (0 if header.isHidden() else header.sizeHint().height())
            + sum(self.rowHeight(row) for row in range(rows))
            + 2 * self.frameWidth()
        )
        return QSize(hint.width(), min(hint.height(), wanted) if hint.height() else wanted)

    #: The user asked for the rows named to be toggled together.
    toggle_requested = Signal(object)
    #: The user asked for every entry.
    select_all_requested = Signal()

    # Qt's override name, hence the camelCase.
    # Qt's override name, hence the camelCase.
    def wheelEvent(self, event: QWheelEvent) -> None:
        """The wheel stops at the table's edge instead of grabbing the whole list (`T-210`).

        Qt *ignores* a wheel event a scroll area cannot use, which hands it to the next scroll
        area up — so the moment the entries hit bottom, the outer staging list took over
        mid-gesture and the dialog jumped to its own end. The maintainer's words: *"once the inner
        scroll bar reaches the bottom, it immediately jumps you to the bottom of the other."*

        Consumed at the edges instead: reaching an end simply stops. The outer list is scrolled by
        pointing at it, not through this table — the boundary a nested list needs to feel like a
        thing rather than a hole.

        **A table with no scroll range of its own still passes the wheel along.** A short picker
        consuming wheels it cannot use would be a dead patch between the user and the list.
        """
        if self.verticalScrollBar().maximum() == 0:
            event.ignore()
            return
        super().wheelEvent(event)
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == int(Qt.Key.Key_Space):
            self.toggle_requested.emit(self.checked_rows())
            return
        if key == int(Qt.Key.Key_A) and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Qt's own select-all runs too, so the highlight and the checks agree afterwards.
            self.selectAll()
            self.select_all_requested.emit()
            return
        # `Shift`+`↑` `↓` falls through: `ExtendedSelection` is where the range comes from, and
        # re-implementing it here would be a second answer to a question Qt already answers.
        super().keyPressEvent(event)

    def checked_rows(self) -> tuple[int, ...]:
        """The rows `Space` acts on: everything selected, or the current row alone.

        The fallback matters. `Space` before anything has been selected — which is where a
        keyboard user arrives, because focus does not select — would otherwise act on nothing and
        read as a dead key.
        """
        rows = sorted({index.row() for index in self.selectionModel().selectedIndexes()})
        if rows:
            return tuple(rows)
        current = self.currentIndex()
        return (current.row(),) if current.isValid() else ()


class PlaylistPicker(QWidget):
    """The tri-state header, the entry table and the sentence saying what is chosen (`P-5`).

    **A `QWidget` composing a `QTableView`**, for `FormatTable`'s reason: the surface that embeds
    it is a staging row, and a view subclass could not carry the header checkbox and the summary
    the ruling asks for without becoming a dialog.
    """

    #: `PlaylistSelection` — what is chosen now, after any change.
    selection_changed = Signal(object)

    def __init__(
        self,
        entries: Sequence[PlaylistEntry] = (),
        selection: PlaylistSelection | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("playlistPicker")
        self._model = PlaylistEntryModel(entries, selection, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._group = QCheckBox(GROUP_TEXT, self)
        self._group.setObjectName("playlistGroupCheck")
        self._group.setAccessibleName(GROUP_TEXT)
        self._group.setAccessibleDescription(
            "Choose or unchoose every entry of this playlist. Partly filled means some entries "
            "are chosen."
        )
        # **Tri-state to *display*, two-state to *click*** (`P-5`). `setTristate` would put
        # "partially checked" into the cycle a click walks, so a user would have to press three
        # times to get from *some* to *none* and the middle press would mean nothing. The partial
        # state is written by `_announce` from the members, which is what "reflecting its members"
        # says.
        self._group.clicked.connect(self._on_group_clicked)
        layout.addWidget(self._group)

        self._table = EntryTable(self)
        self._table.setObjectName("playlistEntryTable")
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # **`ExtendedSelection` is `REQ-004`'s range selection** — `Shift`+`↑` `↓` and shift-click
        # both build the run that `Space` then sets.
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setAccessibleName("Playlist entries")
        self._table.verticalHeader().setVisible(False)
        # `T107-R3`: Tab must leave the table rather than walk its cells, or the declared route
        # out of it does not exist.
        self._table.setTabKeyNavigation(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(TITLE_COLUMN, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(INDEX_COLUMN, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(DURATION_COLUMN, QHeaderView.ResizeMode.ResizeToContents)
        # `T107-R6`: `ResizeToContents` reads every row of a column to size it, and a playlist is
        # exactly the unbounded case. Sampling bounds that to what a column actually needs.
        header.setResizeContentsPrecision(32)
        self._table.toggle_requested.connect(self._on_toggle_requested)
        self._table.select_all_requested.connect(self._model.select_all)
        self._model.selection_changed.connect(lambda _selection: self._announce())
        layout.addWidget(self._table)

        self._summary = QLabel(self)
        self._summary.setObjectName("playlistSummary")
        self._summary.setAccessibleName("What this playlist will add")
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)

        QWidget.setTabOrder(self._group, self._table)
        self._select_first_row()
        self._announce()

    # --- the seam a surface embedding this uses ------------------------------------------

    @property
    def table(self) -> EntryTable:
        return self._table

    @property
    def group_control(self) -> QCheckBox:
        return self._group

    @property
    def model(self) -> PlaylistEntryModel:
        return self._model

    @property
    def selection(self) -> PlaylistSelection:
        """What is chosen now. The dialog reads this when it builds the jobs."""
        return self._model.selection

    def summary_text(self) -> str:
        """The sentence the label and the accessible description both carry."""
        return self._summary.text()

    def focus_chain(self) -> list[QWidget]:
        """The keyboard order through the picker, stated rather than left to construction."""
        return [self._group, self._table]

    # --- internals -------------------------------------------------------------------------

    def _on_group_clicked(self, checked: bool) -> None:
        self._model.set_group(checked)

    def _on_toggle_requested(self, rows: object) -> None:
        self._model.toggle_rows(tuple(rows) if isinstance(rows, tuple) else ())

    def _announce(self) -> None:
        """Put the selection where a reader, a screen reader and the header all find it."""
        selection = self.selection
        described = describe_playlist(selection)
        self._summary.setText(described)
        self.setAccessibleDescription(described)
        # Blocked because writing the state back is a *reflection* of the members, not a click:
        # `setCheckState` emits `clicked`'s sibling signals and would re-enter the model.
        self._group.blockSignals(True)
        self._group.setTristate(selection.group_state is GroupCheck.SOME)
        self._group.setCheckState(_GROUP_STATES[selection.group_state])
        self._group.blockSignals(False)
        self.selection_changed.emit(selection)

    def _select_first_row(self) -> None:
        """A current row from the start (`T-152`): a route that needs a click first is not one."""
        if self._model.rowCount():
            self._table.setCurrentIndex(self._model.index(0, INDEX_COLUMN))
