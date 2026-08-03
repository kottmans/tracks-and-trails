"""One drawn row, for both the staging list and the queue (`T-118`, `T-119`, `REQ-002`).

Two surfaces show the same thing — a thumbnail, what the item is, and where it has got to — and
before this they drew it twice. The add dialog put a `QWidget` on every row; the queue laid out a
grid of six text columns. This module draws it once, and that single fact is what closes three
findings at the same time rather than one at a time:

- **`T118-R7`** — the row widget collided with the item delegate, so a 54 px thumbnail was clipped
  into a 25 px row. There is no row widget now, and `ROW_HEIGHT` is derived from the thumbnail it
  has to contain rather than left to whatever the default metrics produce.
- **`T118-R9`** — the per-row controls sat outside the declared focus order and landed after
  *Close*. An editor a delegate opens belongs to the row, is reached through the row, and cannot
  land anywhere in the tab order because it is not in it: `EDIT_KEY` is the declared route, and it
  is stated here rather than inherited from a Qt default nobody wrote down.
- **`T118-R10`** — a paste of 150 cost 0.722 s on hosted Windows because it built 150 widgets. A
  delegate builds **one editor, for the row being edited**, and paints the rest. What used to grow
  with the paste is now flat in it.

## Roles, not columns

The delegate reads its row through named roles rather than through column indices, so the two
models feeding it need not agree on a column layout — the staging list has one column of rows, the
queue has one column of jobs, and each answers the same questions. A role a model does not answer
is simply absent from the drawing; nothing is required except `HEADLINE_ROLE`.

**Every field is text, and every state is a word** (`NFR-005`). The painted progress bar is
decoration over `DETAIL_ROLE`, which already says the same thing in words — this is the rule that
colour never carries meaning alone, applied to the one graphical element here. It is also not a
`QProgressBar`: `queue_view.py` rejected a widget per row and that reasoning is untouched, because
a painted rectangle is not a widget and costs nothing per row.
"""

from typing import Any, Final, cast

from PySide6.QtCore import (
    QAbstractItemModel,
    QEvent,
    QModelIndex,
    QRect,
    QSize,
    Qt,
)
from PySide6.QtCore import QPersistentModelIndex as _PersistentIndex
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QApplication,
    QComboBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionComboBox,
    QStyleOptionViewItem,
    QWidget,
)

from tracks_and_trails.ui.thumbnails import THUMBNAIL_SIZE, ThumbnailStore

#: The headline: a title once something has read one, else the URL the user pasted. Never empty —
#: a row nobody can identify is worse than a long URL.
HEADLINE_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 1

#: The second line: uploader, duration and kind for a staged row; size, speed and ETA for a
#: running one. In words, always.
DETAIL_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 2

#: Where the row has got to, in words (`NFR-005`): "Reading", "Downloading video", "Couldn't read".
STATE_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 3

#: The picture to draw, as a URL. The delegate asks the store for it while painting and never
#: fetches anything itself — see `thumbnails.ThumbnailStore.pixmap`.
THUMBNAIL_URL_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 4

#: The hue of the derived tile drawn until a picture arrives (`staging.placeholder_hue`).
HUE_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 5

#: Completion as a fraction from 0 to 1, or `None` when there is nothing honest to draw. `None` is
#: not zero: an unknown total is not "0%", which is a confident lie `Job.progress` already refuses.
PROGRESS_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 6

#: The third line: what this row will be downloaded as, **spelled out** (`T118-R8`, `REQ-009`).
#:
#: Its own role rather than part of `DETAIL_ROLE` because it is the one line that has to survive
#: eliding intact — a truncated format selector is a format selector the user cannot copy, and
#: `REQ-009`'s promise is that they can learn the syntax from it.
SELECTOR_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 9

#: The row's own choice, as a preset name, or `None` for "follows the batch" (`UX-004`).
PRESET_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 7

#: The names the row's editor offers, in order. A model that answers `None` gets no editor at all,
#: which is how the queue uses this delegate without acquiring a control it has no use for.
PRESET_CHOICES_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 8

#: What the editor's first entry says (`UX-004`). Named rather than blank: a row that follows the
#: batch has made a choice — the same one as everything else — and a blank reads as no format at
#: all rather than as the one below it (`T118-R4`).
INHERITED_TEXT: Final = "Same as all"

#: The editor's object name. Shared by every row deliberately: they are one control reused, and a
#: test asserting the keyboard surface counts them rather than naming twenty of them.
ROW_PRESET_NAME: Final = "rowPresetChoice"

#: Space around the row's contents.
PADDING: Final = 6

#: The gap between the thumbnail and the text.
GAP: Final = 10

#: How many lines the wrapped literal selector may occupy on the row (`T118-R8`, `T118-R15`).
#:
#: **The row shows as much of the selector as fits in these lines; the complete, copyable value
#: lives below the list.** That split is the contract, and it is narrower than the one this
#: constant used to claim. Two lines holds the longest built-in at the default 9 pt font — and
#: `T118-R15` measured the same string needing three lines at 12 to 15 pt and five at 18 pt, so a
#: promise that the row never clips was true only of the font the tests happened to use.
#:
#: Sizing the row from the wrapped height instead would make row height depend on content, and
#: uniform rows are what let a long list compute its visible range arithmetically rather than
#: measuring every row — the property `T118-R10` turns on. So the row stays uniform and
#: `add_dialog`'s `selectorValue` label, which wraps freely and is selectable, is the surface that
#: carries the whole value at any font.
SELECTOR_LINES: Final = 2

#: How many lines of text a row draws: headline, detail and state, then the selector's own lines.
TEXT_LINES: Final = 2 + SELECTOR_LINES

#: **The row is at least as tall as the thumbnail it contains** (`T118-R7`). Derived rather than
#: chosen, so changing `THUMBNAIL_SIZE` cannot leave a 54 px picture in a 25 px row again.
#:
#: A floor rather than the final answer: `sizeHint` takes the larger of this and the height
#: `TEXT_LINES` actually need in the view's font, because a user running a large font would
#: otherwise get three lines clipped into a box sized for a picture — the same defect as `R7`,
#: arrived at from the other side.
ROW_HEIGHT: Final = THUMBNAIL_SIZE[1] + 2 * PADDING

#: How wide the row's editor is drawn. Wide enough for the longest preset name plus its arrow.
EDITOR_WIDTH: Final = 190

#: The height of the painted progress bar.
BAR_HEIGHT: Final = 4

#: How tall the row's format control is drawn. A combo box's own height, near enough, and bounded
#: by the row so a large font cannot push it outside its own row.
CONTROL_HEIGHT: Final = 26

#: **The declared keyboard route to a row's editor** (`T118-R9`).
#:
#: Stated here rather than left to `QAbstractItemView`'s default, because "the row controls are
#: outside the declared focus order" was the finding, and a route that exists only as a Qt default
#: is a route nobody declared. The view sets `EditKeyPressed`, which is this key.
EDIT_KEY: Final = Qt.Key.Key_F2

#: What that route is called on screen and to a screen reader. One sentence, in one place, so the
#: dialog's help text and the delegate's accessible description cannot drift apart.
EDIT_HINT: Final = "Press F2 to choose a format for this row."


class RowDelegate(QStyledItemDelegate):
    """Draws a rich row, and opens **one** editor for the row being edited.

    The store is optional: a surface with no thumbnails to draw passes none and gets the derived
    tile for every row, which is exactly what an unresolved staging row wants anyway.
    """

    def __init__(
        self,
        *,
        thumbnails: ThumbnailStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._thumbnails = thumbnails
        #: The row whose live editor is open, or `None`. At most one at a time — that is the whole
        #: of `T118-R10`'s correction, and `_paint_control` reads it to avoid drawing the
        #: affordance underneath the real control.
        self._editing_row: int | None = None
        #: The live editor itself, so it can be committed and closed **before** a model reset
        #: invalidates its index (`T118-R14`).
        self._editor: QWidget | None = None

    # --- size and drawing -----------------------------------------------------------------

    # Qt's override names, hence the camelCase: these are not project naming choices.
    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | _PersistentIndex
    ) -> QSize:
        """A fixed height, which is what makes a long list cheap to lay out.

        Uniform rows let the view compute the visible range arithmetically instead of measuring
        every row — the same reason `setUniformItemSizes` existed on the list this replaces, kept
        rather than lost in the move to a delegate. It is uniform because it does not consult
        `index`: every row is the same height whatever it holds.
        """
        text = TEXT_LINES * option.fontMetrics.height() + 2 * PADDING
        return QSize(option.rect.width(), max(ROW_HEIGHT, text))

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | _PersistentIndex,
    ) -> None:
        """Draw the whole row: tile or picture, headline, detail, state, and progress.

        **The only place a thumbnail is ever asked for.** `ThumbnailStore.pixmap` starts a fetch on
        a miss, so a row the view never paints never causes a request — which is `T-119`'s
        criterion satisfied by where the call sits rather than by a rule someone maintains.
        """
        style_option = QStyleOptionViewItem(option)
        self.initStyleOption(style_option, index)
        # The text is drawn by hand below, so Qt must not also draw it underneath.
        style_option.text = ""

        # Qt's stubs type `widget` as a `QWidget`, while a style option built outside a view really
        # does carry `None` — the same mismatch `add_dialog._row_preset_control` documents. `cast`
        # states the real contract here rather than suppressing the check at the branch.
        widget = cast("QWidget | None", style_option.widget)
        if widget is not None:
            widget.style().drawControl(
                QStyle.ControlElement.CE_ItemViewItem, style_option, painter, widget
            )

        painter.save()
        painter.setClipRect(option.rect)

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        palette = option.palette
        primary = palette.highlightedText().color() if selected else palette.text().color()
        muted = QColor(primary)
        muted.setAlpha(170)

        body = option.rect.adjusted(PADDING, PADDING, -PADDING, -PADDING)
        self._paint_tile(painter, body, index)

        text_left = body.left() + THUMBNAIL_SIZE[0] + GAP
        text_area = QRect(text_left, body.top(), max(body.right() - text_left, 0), body.height())

        # **The control is drawn on every row that has one** (`UX-004` §1, `T118-R12`). Reserving
        # the slot and painting nothing in it was the defect: an empty 190 px gap is not a visible
        # control, and it left the override discoverable only by knowing it was there.
        #
        # Drawn rather than instantiated, which is `UX-004`'s own sequencing note ("C") — the live
        # `QComboBox` still exists only for the row being edited, so the widget-per-row cost that
        # `T118-R10` measured does not come back. What the user sees is identical either way,
        # because both are drawn by the same style.
        if self._editable(index):
            text_area.setWidth(max(text_area.width() - EDITOR_WIDTH - GAP, 0))
            if not self._is_being_edited(index):
                # Suppressed only under the live editor, which occupies the same rectangle —
                # otherwise the painted affordance shows through the real control's edges.
                self._paint_control(painter, body, option, index)

        self._paint_text(painter, text_area, body, index, primary, muted)
        painter.restore()

    def _control_rect(self, body: QRect) -> QRect:
        """Where the row's format control sits. One definition, so the painted affordance, the
        live editor and the click target cannot disagree about where it is."""
        height = min(CONTROL_HEIGHT, body.height())
        return QRect(
            max(body.right() - EDITOR_WIDTH, body.left()),
            body.top() + (body.height() - height) // 2,
            min(EDITOR_WIDTH, body.width()),
            height,
        )

    def _is_being_edited(self, index: QModelIndex | _PersistentIndex) -> bool:
        """Whether the live editor is currently open on this row.

        Tracked here rather than asked of the view, because the delegate is what creates and
        destroys the editor and so is the only thing that cannot be wrong about it.
        """
        return self._editing_row == index.row()

    def _paint_control(
        self,
        painter: QPainter,
        body: QRect,
        option: QStyleOptionViewItem,
        index: QModelIndex | _PersistentIndex,
    ) -> None:
        """Draw the row's **Download as** control, through the real style (`UX-004`, `T118-R12`).

        `QStyleOptionComboBox` and `CC_ComboBox` rather than a hand-drawn rectangle: a control the
        user is expected to recognise has to be the platform's combo box, not something that
        resembles one on the machine it was drawn on. It also themes itself, which a rectangle
        would have to be told how to do twice.
        """
        chosen = index.data(PRESET_ROLE)
        label = chosen if isinstance(chosen, str) else INHERITED_TEXT

        box = QStyleOptionComboBox()
        box.rect = self._control_rect(body)
        box.palette = option.palette
        box.currentText = label
        box.state = QStyle.StateFlag.State_Enabled
        if option.state & QStyle.StateFlag.State_MouseOver:
            box.state |= QStyle.StateFlag.State_MouseOver

        widget = cast("QWidget | None", option.widget)
        style = widget.style() if widget is not None else QApplication.style()
        style.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, box, painter, widget)
        # The label is a separate element: `CC_ComboBox` draws the frame and the arrow, and
        # `CE_ComboBoxLabel` draws the text inside whatever room they left.
        style.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, box, painter, widget)

    def _paint_tile(
        self, painter: QPainter, body: QRect, index: QModelIndex | _PersistentIndex
    ) -> None:
        """The picture if there is one, the derived tile until then (`UX-003`).

        **Never an empty box.** A column of empty wells reads as a broken application, and it reads
        worse the more rows there are — which is the case this design exists for.
        """
        width, height = THUMBNAIL_SIZE
        tile = QRect(body.left(), body.top(), width, height)

        pixmap: QPixmap | None = None
        if self._thumbnails is not None:
            url = index.data(THUMBNAIL_URL_ROLE)
            pixmap = self._thumbnails.pixmap(url if isinstance(url, str) else None)

        if pixmap is not None and not pixmap.isNull():
            # Centred inside the fixed box: the picture keeps its aspect ratio, so a square
            # thumbnail does not stretch to 16:9 and a wide one does not overflow the row.
            target = QRect(tile)
            target.setSize(pixmap.size())
            target.moveCenter(tile.center())
            painter.drawPixmap(target, pixmap)
            return

        hue = index.data(HUE_ROLE)
        hue = hue if isinstance(hue, int) else 0
        painter.fillRect(tile, QColor.fromHsv(hue, 90, 110))
        painter.setPen(QColor.fromHsv(hue, 60, 190))
        painter.drawRect(tile.adjusted(0, 0, -1, -1))

    def _paint_text(
        self,
        painter: QPainter,
        area: QRect,
        body: QRect,
        index: QModelIndex | _PersistentIndex,
        primary: QColor,
        muted: QColor,
    ) -> None:
        if area.width() <= 0:
            return
        metrics = painter.fontMetrics()
        line = metrics.height()

        headline = _text(index, HEADLINE_ROLE)
        painter.setPen(primary)
        painter.drawText(
            QRect(area.left(), area.top(), area.width(), line),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            metrics.elidedText(headline, Qt.TextElideMode.ElideRight, area.width()),
        )

        state = _text(index, STATE_ROLE)
        detail = _text(index, DETAIL_ROLE)
        second = " — ".join(part for part in (detail, state) if part)
        painter.setPen(muted)
        painter.drawText(
            QRect(area.left(), area.top() + line, area.width(), line),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            metrics.elidedText(second, Qt.TextElideMode.ElideRight, area.width()),
        )

        selector = _text(index, SELECTOR_ROLE)
        if selector:
            # **Not elided, and not narrowed by the control's slot** (`T118-R8`, `REQ-009`).
            #
            # This line was passed through `ElideRight` at the width left over beside the editor
            # slot — 382 px at the tests' own render width — against a built-in selector that
            # measures up to 962 px. The literal selector, which is the entire point of the line,
            # was cut off every time; the tests asserted the model's string and so never saw it.
            #
            # So it wraps instead of eliding, and it runs the **full** body width: the control sits
            # beside the first two lines, and nothing needs the third line's right-hand end.
            # `SELECTOR_LINES` of room, which holds every built-in at the default font and is
            # explicitly *not* a promise at larger ones — see that constant, and `T118-R15`.
            painter.drawText(
                QRect(
                    area.left(),
                    area.top() + 2 * line,
                    max(body.right() - area.left(), 0),
                    SELECTOR_LINES * line,
                ),
                int(
                    Qt.AlignmentFlag.AlignLeft
                    | Qt.AlignmentFlag.AlignTop
                    | Qt.TextFlag.TextWordWrap
                ),
                selector,
            )

        fraction = index.data(PROGRESS_ROLE)
        if selector or not isinstance(fraction, float | int) or isinstance(fraction, bool):
            # The third line belongs to whichever of the two the surface actually has. No model
            # answers both — the staging list has a format to spell out and no progress; the queue
            # has progress and no per-row format — and the bar is the one that yields, because
            # `DETAIL_ROLE` already carries the same number in words (`NFR-005`).
            return
        bar = QRect(area.left(), area.top() + 2 * line + 2, area.width(), BAR_HEIGHT)
        if bar.bottom() > area.bottom():
            return
        track = QColor(muted)
        track.setAlpha(60)
        painter.fillRect(bar, track)
        done = QRect(bar)
        done.setWidth(int(bar.width() * min(max(float(fraction), 0.0), 1.0)))
        painter.fillRect(done, muted)

    # --- the one editor -------------------------------------------------------------------

    def _editable(self, index: QModelIndex | _PersistentIndex) -> bool:
        choices = index.data(PRESET_CHOICES_ROLE)
        return bool(choices)

    def editorEvent(
        self,
        event: Any,
        model: QAbstractItemModel,
        option: QStyleOptionViewItem,
        index: QModelIndex | _PersistentIndex,
    ) -> bool:
        """Open the row's editor when the user clicks the control that is drawn on it.

        **The direct interaction, which is what makes the painted affordance a control** rather
        than a picture of one (`T118-R12`). `SelectedClicked` alone required the row to be selected
        first, so a click on an unselected row's control selected the row and did nothing visible —
        the user had to click the same place twice and had no way to know that.

        Returns `False` for everything else, so the view keeps its ordinary selection behaviour.
        """
        if not isinstance(event, QMouseEvent) or event.type() != QEvent.Type.MouseButtonRelease:
            return False
        if event.button() != Qt.MouseButton.LeftButton or not self._editable(index):
            return False
        body = option.rect.adjusted(PADDING, PADDING, -PADDING, -PADDING)
        if not self._control_rect(body).contains(event.position().toPoint()):
            return False
        view = cast("QAbstractItemView | None", self.parent())
        if view is None:
            return False
        view.setCurrentIndex(index)
        view.edit(index)
        return True

    def createEditor(
        self,
        parent: QWidget,
        option: QStyleOptionViewItem,
        index: QModelIndex | _PersistentIndex,
    ) -> QWidget:
        """**One** combo box, for the row currently being edited (`T118-R10`).

        Qt creates this when a row enters edit mode and destroys it when the row leaves, so the
        cost is one control regardless of how many rows exist. The design this replaces built one
        per row up front, which is the whole of the 0.722 s.
        """
        self._editing_row = index.row()
        choice = QComboBox(parent)
        self._editor = choice
        choice.setObjectName(ROW_PRESET_NAME)
        choice.setAccessibleName("Download format for this URL")
        choice.setAccessibleDescription(
            "Choose a format for this URL alone. The first entry follows the format chosen for "
            "the whole paste."
        )
        choice.addItem(INHERITED_TEXT, None)
        for name in index.data(PRESET_CHOICES_ROLE) or ():
            choice.addItem(str(name), str(name))
        return choice

    def destroyEditor(self, editor: QWidget, index: QModelIndex | _PersistentIndex) -> None:
        """Forget the open row. Every close route reaches here, which is why it is the one hook."""
        if self._editing_row == index.row():
            self._editing_row = None
            self._editor = None
        super().destroyEditor(editor, index)

    def commit_and_close_editor(self) -> bool:
        """Commit the open editor and close it. `True` if there was one (`T118-R14`).

        **Called before a model reset, never after.** A reset invalidates the editor's model index,
        after which Qt disowns the widget: `commitData` then reports *"called with an editor that
        does not belong to this view"*, `setData` is never reached, and the user's chosen format is
        discarded silently while the orphaned combo box stays on screen. The window for that is not
        teardown — it is any sibling row finishing its probe while someone is choosing a format.
        """
        view = cast("QAbstractItemView | None", self.parent())
        editor = self._editor
        if view is None or editor is None:
            return False
        self._editor = None
        self._editing_row = None
        view.commitData(editor)
        view.closeEditor(editor, QAbstractItemDelegate.EndEditHint.NoHint)
        return True

    def setEditorData(self, editor: QWidget, index: QModelIndex | _PersistentIndex) -> None:
        if not isinstance(editor, QComboBox):
            return
        current = index.data(PRESET_ROLE)
        wanted = editor.findData(current if isinstance(current, str) else None)
        editor.setCurrentIndex(max(wanted, 0))

    def setModelData(
        self,
        editor: QWidget,
        model: QAbstractItemModel,
        index: QModelIndex | _PersistentIndex,
    ) -> None:
        if not isinstance(editor, QComboBox):
            return
        model.setData(index, editor.currentData(), PRESET_ROLE)

    def updateEditorGeometry(
        self,
        editor: QWidget,
        option: QStyleOptionViewItem,
        index: QModelIndex | _PersistentIndex,
    ) -> None:
        """Put the editor in the slot `paint` already reserved for it, on the row it belongs to."""
        body = option.rect.adjusted(PADDING, PADDING, -PADDING, -PADDING)
        # **The same rectangle the affordance was painted in** (`T118-R12`). One definition, so the
        # control does not move at the moment the user clicks it.
        editor.setGeometry(self._control_rect(body))


def _text(index: QModelIndex | _PersistentIndex, role: int) -> str:
    """One role as a string. A model that does not answer a role contributes nothing to the row."""
    value: Any = index.data(role)
    return value if isinstance(value, str) else ""
