"""Sortable format table for a probed URL (`REQ-003`, `T-107`).

`REQ-003`: *show the available formats for a probed URL in a sortable table (format ID, extension,
resolution, fps, codecs, bitrate, filesize/estimate, notes).* `docs/UX_SPEC.md` §4 is the surface.

Three rules shape everything here, and each exists because of a specific defect:

- **The table reads a `FormatInfo`, never a raw `info_dict` key.** `NFR-008` confines yt-dlp's
  churn to the adapter, and a widget indexing `entry["vcodec"]` puts that churn straight into
  `ui/`. `test_no_ui_module_reads_a_raw_info_dict_key` asserts it statically, the way `T-097`
  asserts the settings boundary rather than trusting a convention.
- **Sorting is over the projection, never the display string** (`UX-005`'s `T-075` lesson). `1080p`
  must sort above `720p` above `144p`, and `~12.4 MB` must sort as a number. The model answers
  `SORT_ROLE` with the underlying value and the view sorts on that role, so there is exactly one
  place the ordering can be wrong.
- **A missing field renders `UNKNOWN_TEXT`**, never an empty cell and never `None`. yt-dlp
  genuinely omits these — a live stream has no filesize, an audio-only format has no height — so
  the absence is information rather than an error, and the window already has a word for it.
  **Rendering the placeholder is frequently the *correct* answer rather than a gap**: archive.org
  reports no codec, bitrate or fps for its derivatives, and `yt-dlp -F` prints nothing for them
  either, so agreeing means showing nothing too.

**Selection is deliberately absent.** `T-107` builds the table; `T-108` (`REQ-008`) is what makes a
chosen format mean something, and `docs/UX_SPEC.md` §4 keeps *download from the table* out
entirely (`P-14`). What this module offers is a current row, a keyboard that moves it, and a signal
saying which format it names — the seam `T-108` consumes.
"""

from collections.abc import Sequence
from typing import Final

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QRect,
    Qt,
    Signal,
)
from PySide6.QtCore import (
    QPersistentModelIndex as _PersistentIndex,
)
from PySide6.QtGui import QFocusEvent, QKeyEvent, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyle,
    QStyleOptionFocusRect,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core.models import FormatInfo
from tracks_and_trails.ui.job_detail import UNKNOWN_TEXT, format_bytes

#: The columns `REQ-003` names, in the order it names them.
#:
#: **A tuple of headers rather than an enum of indices**, because the header text and the column
#: order are the same fact and two declarations of one fact drift. `COLUMN_COUNT` is derived.
COLUMN_HEADERS: Final = (
    "Format",
    "Ext",
    "Resolution",
    "FPS",
    "Video codec",
    "Audio codec",
    "Bitrate",
    "Size",
    "Notes",
)

FORMAT_COLUMN: Final = 0
EXT_COLUMN: Final = 1
RESOLUTION_COLUMN: Final = 2
FPS_COLUMN: Final = 3
VIDEO_CODEC_COLUMN: Final = 4
AUDIO_CODEC_COLUMN: Final = 5
BITRATE_COLUMN: Final = 6
SIZE_COLUMN: Final = 7
NOTES_COLUMN: Final = 8

COLUMN_COUNT: Final = len(COLUMN_HEADERS)

#: The role the view sorts on: the **projected value**, not the rendered string (`T-075`).
#:
#: A `UserRole` rather than `DisplayRole` is the whole mechanism. Qt's default sort compares what
#: `DisplayRole` returns, which is text — so `1080p` sorts below `144p` and `9.9 MB` above
#: `10.1 MB`, both of which look like the table is broken rather than like it is sorting.
SORT_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 1

#: `FormatInfo` for the current row, answered on the row's first column.
FORMAT_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 2

#: Marks a size yt-dlp estimated rather than was told (`T107-R7`, `REQ-003`'s "filesize/estimate").
#:
#: The same `~` `docs/UX_SPEC.md` §4 uses in its own example. One character, in front, so the
#: column still reads as a column of sizes.
ESTIMATE_PREFIX: Final = "~"

#: The invalid parent every flat model is asked about, as a module-level singleton.
#:
#: A fresh `QModelIndex()` in a default argument is `B008`, and `queue_view` already solved it this
#: way — the same constant for the same reason, rather than a second spelling of it.
_ROOT: Final = QModelIndex()


def describe_resolution(entry: FormatInfo) -> str:
    """`1920x1080`, or `1080p` when only the height is known, or `UNKNOWN_TEXT`.

    Both spellings are yt-dlp's own: it reports `width` and `height` for most formats and height
    alone for some. Rendering `1080p` for a format that also knows its width would throw away a
    fact the projection carries.

    **It reads the height and nothing else, and dropping the audio-only case was the correction**
    (`T107-R1`). This used to render *audio only* whenever `FormatInfo.is_audio_only` was true —
    but that property is `video_codec is None and audio_codec is not None`, and
    `_as_optional_codec` maps both *missing* and yt-dlp's explicit `'none'` to `None`. So a format
    whose video codec is merely **unknown** was reported as having no video at all. `yt-dlp -F`
    prints `unknown` for exactly those, and the recorded-capture comparison caught the divergence.

    Saying *audio only* needs the projection to keep yt-dlp's `'none'` apart from a missing key,
    which is a widening this task did not need. Until then the table declines to assert what it
    does not know.
    """
    if entry.height is None:
        return UNKNOWN_TEXT
    if entry.width is None:
        return f"{entry.height}p"
    return f"{entry.width}x{entry.height}"


def describe_fps(fps: float | None) -> str:
    """`30`, or `29.97`, or `UNKNOWN_TEXT`.

    **Rounded for display only**, and only where rounding loses nothing: 30.0 reads as `30` and
    29.97 keeps its fraction, because 29.97 and 30 are different framerates and a table that
    showed both as `30` would be hiding the distinction a user opened it to see.
    """
    if fps is None:
        return UNKNOWN_TEXT
    return f"{fps:g}"


def describe_bitrate(kbps: float | None) -> str:
    """`1234 kbps`, or `UNKNOWN_TEXT`. Whole kbps: the fraction is below what anyone reads."""
    if kbps is None:
        return UNKNOWN_TEXT
    return f"{kbps:.0f} kbps"


def describe_size(entry: FormatInfo) -> str:
    """`44.8 MB`, or `~44.8 MB` for an estimate, or `UNKNOWN_TEXT` (`T107-R7`).

    Deliberately the same `format_bytes` the job detail uses. Two independently written byte
    formatters drift, and a user reading a size in the table and the same size on a row should not
    have to notice which is which — `format_eta`'s reasoning, one field over.

    **The tilde is the whole point of the column being named "filesize or estimate".** yt-dlp
    supplies `filesize` or `filesize_approx` depending on the extractor, and rendering both the
    same way showed a guess as a measurement. Sorting is unaffected: it is on bytes, and an
    estimate is as sortable as an exact size.
    """
    rendered = format_bytes(entry.filesize)
    if entry.filesize_is_estimate and rendered != UNKNOWN_TEXT:
        return f"{ESTIMATE_PREFIX}{rendered}"
    return rendered


def describe_codec(codec: str | None) -> str:
    return codec if codec else UNKNOWN_TEXT


class FormatTableModel(QAbstractTableModel):
    """Every format a probe found, one row each.

    **A table model over a frozen tuple**, not a live view of anything: a probe's formats are
    fixed once the probe ends, so there is no stream to coalesce and none of `QueueModel`'s
    repaint machinery is needed here.
    """

    def __init__(self, formats: Sequence[FormatInfo] = (), parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._formats: tuple[FormatInfo, ...] = tuple(formats)
        #: The active sort, so a reset can reapply it (`T107-R4`). `None` until something sorts.
        self._sorted_by: tuple[int, Qt.SortOrder] | None = None

    def set_formats(self, formats: Sequence[FormatInfo]) -> None:
        """Replace the whole table, **keeping the active sort** (`T107-R4`).

        A probe answers once, so this is a reset rather than an incremental update. What it must
        not do is install input order underneath a sort indicator that still points at a column:
        the reviewer populated a table after construction and got rows `[720, 1080]` beneath a
        *descending resolution* indicator. That is precisely the defect this module's own docstring
        warns about one paragraph over — an indicator that moves while the rows do not — recreated
        by the setter.
        """
        self.beginResetModel()
        self._formats = tuple(formats)
        if self._sorted_by is not None:
            column, order = self._sorted_by
            self._formats = self._ordered(self._formats, column, order)
        self.endResetModel()

    def formats(self) -> tuple[FormatInfo, ...]:
        return self._formats

    def rowCount(self, parent: QModelIndex | _PersistentIndex = _ROOT) -> int:
        return 0 if parent.isValid() else len(self._formats)

    def columnCount(self, parent: QModelIndex | _PersistentIndex = _ROOT) -> int:
        return 0 if parent.isValid() else COLUMN_COUNT

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> object:
        if orientation is not Qt.Orientation.Horizontal:
            return None
        if role == int(Qt.ItemDataRole.DisplayRole) and 0 <= section < COLUMN_COUNT:
            return COLUMN_HEADERS[section]
        return None

    def data(
        self,
        index: QModelIndex | _PersistentIndex,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> object:
        if not index.isValid() or not 0 <= index.row() < len(self._formats):
            return None
        entry = self._formats[index.row()]
        if role == FORMAT_ROLE:
            return entry
        if role == SORT_ROLE:
            return self._sort_value(entry, index.column())
        if role == int(Qt.ItemDataRole.DisplayRole):
            return self._text(entry, index.column())
        if role == int(Qt.ItemDataRole.AccessibleTextRole):
            # **The column is named as well as the value** (`NFR-005`). A screen reader moving
            # across a row otherwise reads eight bare values with no way to tell which is the
            # bitrate and which the size — the same reason `T-060` made state text carry its own
            # label rather than relying on the header being read once.
            return f"{COLUMN_HEADERS[index.column()]}: {self._text(entry, index.column())}"
        return None

    def _text(self, entry: FormatInfo, column: int) -> str:
        """What the cell reads. **Every branch returns a non-empty string** — see `UNKNOWN_TEXT`."""
        if column == FORMAT_COLUMN:
            return entry.format_id
        if column == EXT_COLUMN:
            return entry.extension
        if column == RESOLUTION_COLUMN:
            return describe_resolution(entry)
        if column == FPS_COLUMN:
            return describe_fps(entry.fps)
        if column == VIDEO_CODEC_COLUMN:
            return describe_codec(entry.video_codec)
        if column == AUDIO_CODEC_COLUMN:
            return describe_codec(entry.audio_codec)
        if column == BITRATE_COLUMN:
            return describe_bitrate(entry.bitrate_kbps)
        if column == SIZE_COLUMN:
            return describe_size(entry)
        if column == NOTES_COLUMN:
            return entry.note or UNKNOWN_TEXT
        return UNKNOWN_TEXT

    def _sort_value(self, entry: FormatInfo, column: int) -> tuple[float, str]:
        """The key the column sorts by — the projection, never the rendered text (`T-075`).

        **Always a `(number, text)` pair, for every column, so the comparison is total.** A column
        that returned a bare `int` for some rows and a `str` for others raises `TypeError` the
        moment `sorted` compares them, and format ids are exactly that column: `137` and
        `hls-1080` both occur. The pair sorts numerically first and settles ties on text, so one
        shape covers both kinds of column and there is no branch that can produce an
        uncomparable pair.

        **A missing value sorts as `-1`**, which puts every unknown at one end of a numeric column
        rather than interleaving them. Text sorts case-insensitively: `AVC1` above `avc1` is an
        ordering a user reads as random.
        """
        if column == FORMAT_COLUMN:
            # Format ids are *mostly* numeric and not reliably so — `137`, but also `hls-1080`.
            # Numeric ids sort numerically (so `9` precedes `137` rather than following it) and
            # named ones sort after all of them, on text.
            if entry.format_id.isdigit():
                return (float(entry.format_id), "")
            return (float("inf"), entry.format_id.casefold())
        if column == EXT_COLUMN:
            return (0.0, entry.extension.casefold())
        if column == RESOLUTION_COLUMN:
            # **Height, not the rendered string.** This is the column `T-075` is about: `1080p`
            # text-sorts below `144p`, and an audio-only row has no height at all.
            return (float(entry.height) if entry.height is not None else -1.0, "")
        if column == FPS_COLUMN:
            return (entry.fps if entry.fps is not None else -1.0, "")
        if column == VIDEO_CODEC_COLUMN:
            return (0.0, (entry.video_codec or "").casefold())
        if column == AUDIO_CODEC_COLUMN:
            return (0.0, (entry.audio_codec or "").casefold())
        if column == BITRATE_COLUMN:
            return (entry.bitrate_kbps if entry.bitrate_kbps is not None else -1.0, "")
        if column == SIZE_COLUMN:
            # **Bytes, not "12.4 MB".** The other half of `T-075`: `9.9 MB` text-sorts above
            # `10.1 MB`, and an estimate and an exact size are both just numbers here.
            return (float(entry.filesize) if entry.filesize is not None else -1.0, "")
        if column == NOTES_COLUMN:
            return (0.0, (entry.note or "").casefold())
        return (0.0, "")

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        """Reorder the rows by `column`, on `_sort_value` (`T-075`).

        **Implemented here rather than left to Qt.** `QTableView.setSortingEnabled(True)` calls
        this method; the default `QAbstractItemModel.sort` does nothing, so a table that merely
        enables sorting shows a sort indicator that moves and rows that do not. That is worse than
        no sorting at all — it looks like it worked.

        A `QSortFilterProxyModel` with `setSortRole` is the other idiom and was not used: it would
        put the ordering behind Qt's `QVariant` comparison of whatever `SORT_ROLE` returns, and the
        keys here are Python tuples. Sorting them in Python is one line and leaves nothing to
        infer about how two variants compare.
        """
        if not 0 <= column < COLUMN_COUNT:
            return
        self.layoutAboutToBeChanged.emit()
        # **Persistent indexes are remapped, which is what keeps a selection on its own row**
        # (`T107-R4`). Qt tracks a current row by index, so a sort that only replaces the tuple
        # leaves the *row number* selected and silently changes which format that is — the
        # reviewer selected `b`, sorted, and `current_format()` answered `a`. Anything holding a
        # `QPersistentModelIndex` — the view's current index among them — follows its row here.
        old_indexes = self.persistentIndexList()
        before = list(self._formats)
        self._formats = self._ordered(self._formats, column, order)
        self._sorted_by = (column, order)
        moved = {id(entry): row for row, entry in enumerate(self._formats)}
        self.changePersistentIndexList(
            old_indexes,
            [
                self.index(moved[id(before[index.row()])], index.column())
                if 0 <= index.row() < len(before)
                else QModelIndex()
                for index in old_indexes
            ],
        )
        self.layoutChanged.emit()

    def _ordered(
        self, formats: tuple[FormatInfo, ...], column: int, order: Qt.SortOrder
    ) -> tuple[FormatInfo, ...]:
        """`formats` in `column` order. One implementation, so `sort` and a reset cannot differ."""
        return tuple(
            sorted(
                formats,
                key=lambda entry: self._sort_value(entry, column),
                reverse=order is Qt.SortOrder.DescendingOrder,
            )
        )


class SortableHeader(QHeaderView):
    """The table's header, with a **current section the keyboard can move** (`T107-R3`).

    `QHeaderView` has no notion of a current section — it is a strip of labels a pointer clicks.
    So an event filter that made a focused header react to `Space` still sorted whatever the
    indicator already pointed at, and there was no way to choose a different column. The reviewer's
    words: *a focused section that the user cannot select is not a keyboard-operable header*.

    A subclass rather than more event filtering, because this needs to **paint** the current
    section as well as track it. `NFR-005` forbids conveying state by colour alone, and a focus
    rectangle a user cannot see is the same defect one sense over.
    """

    #: `column` — the user asked for this column to be sorted.
    sort_requested = Signal(int)

    def __init__(self, orientation: Qt.Orientation, parent: QWidget | None = None) -> None:
        super().__init__(orientation, parent)
        self._current = 0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSectionsClickable(True)

    def current_section(self) -> int:
        return self._current

    def set_current_section(self, section: int) -> None:
        if not 0 <= section < max(self.count(), 1):
            return
        self._current = section
        # **Announced, not only drawn** (`NFR-005`). A screen-reader user moving along the header
        # otherwise hears nothing change, and the sort they trigger lands on a column they were
        # never told they were on.
        self.setAccessibleDescription(f"{COLUMN_HEADERS[section]}, press Space to sort")
        self.updateSection(section)
        self.viewport().update()

    def paintSection(
        self,
        painter: QPainter,
        rect: QRect,
        logicalIndex: int,  # noqa: N803 - Qt's name
    ) -> None:
        super().paintSection(painter, rect, logicalIndex)
        if self.hasFocus() and logicalIndex == self._current:
            option = QStyleOptionFocusRect()
            option.initFrom(self)
            option.rect = rect.adjusted(1, 1, -1, -1)
            option.state |= QStyle.StateFlag.State_KeyboardFocusChange
            self.style().drawPrimitive(
                QStyle.PrimitiveElement.PE_FrameFocusRect, option, painter, self
            )

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Arrive on the column the table is sorted by, which is the one the user last acted on."""
        super().focusInEvent(event)
        indicated = self.sortIndicatorSection()
        self.set_current_section(indicated if 0 <= indicated < self.count() else 0)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """`←` `→` choose a column; `Space` or `Enter` sorts it (`docs/UX_SPEC.md` §4).

        **`Tab` is deliberately not handled**, so it falls through to Qt's focus traversal and
        leaves the header. A widget that swallowed `Tab` would trap a keyboard user on it.
        """
        key = event.key()
        if key == int(Qt.Key.Key_Left):
            self.set_current_section(self._current - 1)
            return
        if key == int(Qt.Key.Key_Right):
            self.set_current_section(self._current + 1)
            return
        if key in (int(Qt.Key.Key_Space), int(Qt.Key.Key_Return), int(Qt.Key.Key_Enter)):
            self.sort_requested.emit(self._current)
            return
        super().keyPressEvent(event)


class FormatTable(QWidget):
    """The table and its keyboard, over a `FormatTableModel` (`docs/UX_SPEC.md` §4).

    **A `QWidget` wrapping a `QTableView` rather than a `QTableView` subclass**, so the surface
    that embeds it — `T-108`'s expanded staging row — composes rather than inherits, and so the
    buttons `UX_SPEC` §4's keyboard path names can join it without this class becoming a dialog.
    """

    #: `FormatInfo` — the current row named a format. **Reported, never acted on** (`T-108` owns
    #: what a choice means, and `P-14` keeps *download from the table* out entirely).
    format_chosen = Signal(object)

    def __init__(self, formats: Sequence[FormatInfo] = (), parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("formatTable")
        self._model = FormatTableModel(formats, self)

        self._table = QTableView(self)
        self._table.setObjectName("formatTableView")
        self._table.setModel(self._model)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAccessibleName("Available formats")
        self._table.verticalHeader().setVisible(False)
        # **Tab must leave the table rather than walk its cells** (`T107-R3`). `QTableView`
        # consumes Tab for cell navigation by default, so the declared route — body, then header —
        # could not exist: Tab moved the current cell and focus never left the view.
        self._table.setTabKeyNavigation(False)
        header = SortableHeader(Qt.Orientation.Horizontal, self._table)
        self._table.setHorizontalHeader(header)
        header.sort_requested.connect(self.sort_by)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        # **Sample a bounded number of rows when sizing a column** (`T107-R6`).
        # `ResizeToContents` asks the model for *every* row of *every* column to decide a width:
        # the repaint gate measured **44,019** model reads to paint fourteen visible rows of a
        # 200-format table. A playlist entry with dozens of formats is the ordinary case, so this
        # is a real cost rather than a synthetic one. Qt exposes the bound for exactly this, and
        # 32 rows is plenty to size a column of format ids and codecs.
        header.setResizeContentsPrecision(32)
        header.setSortIndicatorShown(True)
        # **The header takes focus, which is what makes the declared keyboard route exist**
        # (`T107-R3`, `docs/UX_SPEC.md` §4, `NFR-005`). Qt gives a horizontal header `NoFocus` by
        # default, so `Tab` from the body returned to the same view and `Space` on a header was a
        # route described in the spec and reachable only with a pointer. `T-152` is the same
        # defect one surface over, and its lesson was that a declared route which needs a click
        # first is not a route.
        header.setAccessibleName("Sort formats by column")
        self._header = header

        # **A layout, so the view actually fills the widget** (`T107-R2`). Without one the child
        # keeps whatever geometry it was constructed with: the reviewer resized the wrapper to
        # 320x180 and the `QTableView` stayed 256x192, and the wrapper reported a `-1 x -1` size
        # hint — so any surface embedding this would clip or collapse it.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._table)
        # **The header follows the body in the tab chain**, which is the order `docs/UX_SPEC.md` §4
        # declares: body, then header, then out. Set explicitly rather than left to creation order,
        # because the header is a child of the view and would otherwise come first.
        QWidget.setTabOrder(self._table, self._header)
        # **Opens sorted by resolution, best first**, which is the order somebody opening a format
        # table is looking for. `sortByColumn` drives the model's own `sort` — see it for why the
        # model implements one rather than relying on Qt's default, which silently does nothing.
        self._table.sortByColumn(RESOLUTION_COLUMN, Qt.SortOrder.DescendingOrder)

        self._select_first_row()

    # --- the seam a surface embedding this uses ------------------------------------------

    @property
    def table(self) -> QTableView:
        """The view, for a caller that needs to focus it or read its current row."""
        return self._table

    @property
    def model(self) -> FormatTableModel:
        return self._model

    @property
    def header(self) -> SortableHeader:
        """The header, for a caller that needs to focus it or read its current column."""
        return self._header

    def set_formats(self, formats: Sequence[FormatInfo]) -> None:
        self._model.set_formats(formats)
        self._select_first_row()

    def current_format(self) -> FormatInfo | None:
        """The `FormatInfo` the current row names, or `None` when there is no current row."""
        index = self._table.currentIndex()
        if not index.isValid():
            return None
        carried = self._model.data(index, FORMAT_ROLE)
        return carried if isinstance(carried, FormatInfo) else None

    def choose_current(self) -> None:
        """Emit `format_chosen` for the current row, if there is one."""
        chosen = self.current_format()
        if chosen is not None:
            self.format_chosen.emit(chosen)

    def sort_by(self, column: int) -> None:
        """Sort by `column`, reversing if it is already the sorted one (`docs/UX_SPEC.md` §4).

        The one place the "again reverses" rule lives, so the header click and the key press
        cannot disagree about it.
        """
        if not 0 <= column < COLUMN_COUNT:
            return
        current = self._header.sortIndicatorSection()
        ascending = Qt.SortOrder.AscendingOrder
        descending = Qt.SortOrder.DescendingOrder
        if current == column and self._header.sortIndicatorOrder() is ascending:
            order = descending
        else:
            order = ascending
        self._table.sortByColumn(column, order)

    def _select_first_row(self) -> None:
        """Give the table a current row as soon as it has one (`T-152`, `docs/UX_SPEC.md` §4).

        **A declared keyboard route that needs a click first is not one.** `T-152` is exactly this
        defect one surface over: the row menu resolved `currentIndex()` and nothing ever set one,
        so the keyboard route did nothing until a pointer had been used.
        """
        if self._model.rowCount():
            self._table.setCurrentIndex(self._model.index(0, FORMAT_COLUMN))
