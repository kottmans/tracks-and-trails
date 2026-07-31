"""Every job at once: the queue table (`T-079`, `REQ-014`, `REQ-016`).

Phase 1 could show **one** job, because the pool ran one. `T-078` made the pool N, and a window
that shows the newest of three running downloads is a window that hides two of them.

## What N changes, and what it does not

`T-017`'s two rules transfer unchanged, and both matter more here:

- **Repaints are coalesced on a timer**, not driven per message. With one job that was an
  optimisation; with N it is what keeps `NFR-001`'s ~100 ms budget true, because yt-dlp's hook
  fires several times a second *per running job* and the rates add.
- **Rendering rules are pure functions**, shared with `job_detail.py` rather than restated here.
  `describe_bar` and `totals_for_ending` are imported, not reimplemented. A table has more paths
  into the same question, not fewer, and `T-059` was one widget answering it two ways.

## One timer for the table, not one per row

The coalescing budget belongs to the **repaint**, and a repaint draws the whole viewport. N
timers at 100 ms each is N times the wakeups for one screen's worth of drawing, and it makes the
stated rate a per-row promise that says nothing about what the user sees. So messages accumulate
in `_pending` keyed by job, and one tick drains all of them and emits one `dataChanged` span.

`renders` counts **ticks that drew**, not messages absorbed, for the reason `T017-R1` gives: the
first version of that test counted messages and stayed at zero while a second route redrew on
every status change.

## Progress is text, and the bar stays in the detail view

`REQ-014` asks for percent, size, speed, ETA and stage — all text. `REQ-011`'s progress *bar* is
`job_detail.py`'s, and it stays there. A `QProgressBar` per row would put N live widgets inside a
scroll area to render a number six characters already carry, and "repaint cost is bounded with N
rows" is one of this task's criteria rather than an aspiration.

The accessible description is still `describe_bar`'s, so the words a screen reader hears in the
table are produced by the same function that produces them beside the bar (`NFR-005`).

## Ordering is `queue_position`, and this does not decide it

The manager drains waiting work in `queue_position` order (`T-078`), because it is allocated
inside the insert transaction and survives a restart. The table shows that same order for the
same reason: two surfaces disagreeing about "next" is worse than either order alone. A job with
no position sorts last on its id, which is what the scheduler does with one.

**Reordering is `T-081`**, and it will change `queue_position` rather than this sort.
"""

from collections.abc import Callable
from contextlib import suppress
from typing import Any, Final, Protocol

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, QTimer, Signal
from PySide6.QtCore import QPersistentModelIndex as _PersistentIndex
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import Job
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.downloader.protocol import Progress
from tracks_and_trails.ui.job_detail import (
    REPAINT_INTERVAL_MS,
    STAGE_TEXT,
    STATUS_TEXT,
    UNKNOWN_TEXT,
    describe_bar,
    format_bytes,
    format_eta,
    format_speed,
    percent_of,
    totals_for_ending,
)

#: The columns, in order, with the header each shows. `REQ-014` names five things a user must be
#: able to see per job; the sixth is which job it is. Transcribed from the requirement rather than
#: generated from a field list, so a renamed attribute cannot quietly change what is on screen
#: (`ai/TESTING.md` §13).
COLUMN_HEADERS: Final = ("Job", "Status", "Progress", "Size", "Speed", "ETA")

JOB_COLUMN: Final = 0
STATUS_COLUMN: Final = 1
PROGRESS_COLUMN: Final = 2
SIZE_COLUMN: Final = 3
SPEED_COLUMN: Final = 4
ETA_COLUMN: Final = 5

#: Shown in the progress column when there is no total to be a fraction of. `REQ-011`'s
#: indeterminate state, in a cell with no room for an animation; `0%` would be a confident lie of
#: the kind `Job.progress` already refuses to tell, and the accessible text says so in words.
INDETERMINATE_TEXT: Final = "—"

#: What an empty queue says. A blank table and a table that failed to load look identical, and
#: `REQ-012`'s promise that a queued job is visible is a claim about the empty case too.
EMPTY_TEXT: Final = "Nothing queued. Use File > Add URLs... to add a download."

#: The invalid index, meaning "the root" in Qt's model API. A value rather than state, so one
#: instance serves every default argument — and constructing it costs nothing and needs no
#: `QApplication`, since `QModelIndex` is not a `QObject`.
_ROOT: Final = QModelIndex()

#: `queue_position` is optional on `Job`; a row without one sorts last rather than raising or
#: sorting as zero. The same literal and the same reasoning as `manager._UNPLACED`, which is the
#: scheduler's half of this ordering — see the module docstring.
_UNPLACED: Final = 1 << 62


class QueueReader(Protocol):
    """The one read this table needs, named as a protocol (`ARCHITECTURE.md` §3).

    `ui/` depends on the shape of a repository rather than on `persistence`, exactly as
    `JobReader` does for the single-job view. `PersistentJobStore` satisfies it; so does a list
    in a test.
    """

    def all_jobs(self) -> list[Job]: ...


class _Row:
    """One job's durable row, plus whatever a live worker has said since.

    The two are kept apart on purpose. `manager.py` does not persist progress per message — "an
    unbounded write rate for a fact that is worthless after a crash" — so while a job runs the
    durable row lags and the message is closer; once it ends, the row is the one that knows.
    `totals_for_ending` is that rule, and this class holds its two inputs rather than deciding
    between them itself.
    """

    __slots__ = ("displayed", "job", "totals")

    def __init__(self, job: Job) -> None:
        self.job = job
        #: The newest message that has been *drawn* for this job, or `None` if none ever was.
        self.displayed: Progress | None = None
        #: The byte pair the cells were last written from. Meaningful only with `displayed`.
        self.totals: tuple[int | None, int | None] = (None, None)

    @property
    def is_terminal(self) -> bool:
        return self.job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)

    def ending_totals(self) -> tuple[int | None, int | None]:
        """This row's size, through the shared rule rather than a second opinion (`T-059`)."""
        return totals_for_ending(
            self.job.status,
            self.job,
            last_shown=self.totals if self.displayed is not None else None,
        )


def _order(job: Job) -> tuple[int, str]:
    """`queue_position` first, id to break ties. See the module docstring."""
    position = job.queue_position
    return (position if position is not None else _UNPLACED, job.id)


class QueueModel(QAbstractTableModel):
    """Every job, one row each, coalescing a stream of progress into a bounded repaint rate."""

    def __init__(
        self,
        *,
        jobs: QueueReader,
        manager: DownloadManager,
        parent: QObject | None = None,
        repaint_interval_ms: int = REPAINT_INTERVAL_MS,
    ) -> None:
        super().__init__(parent)
        self._jobs = jobs
        self._manager = manager
        self._rows: list[_Row] = []
        self._index_of: dict[str, int] = {}
        #: Newest undrawn message per job. One entry per job, not a queue of them: an intermediate
        #: byte count nobody drew is not information anyone lost.
        self._pending: dict[str, Progress] = {}
        self._renders = 0

        self._repaint = QTimer(self)
        self._repaint.setInterval(repaint_interval_ms)
        self._repaint.timeout.connect(self._draw_pending)

        self._manager.progress.connect(self._on_progress)
        self._manager.job_changed.connect(self._on_job_changed)
        self.refresh()

    # --- the promises tests read -----------------------------------------------------------

    @property
    def renders(self) -> int:
        """How many ticks have redrawn cells (`T017-R1`'s counting rule, one surface over).

        Ticks, not messages and not rows: `REPAINT_INTERVAL_MS` is a promise about how often the
        table changes under the user's eyes, and a per-row count would grow with the pool while
        the screen was redrawn exactly as often.
        """
        return self._renders

    @property
    def pending_job_ids(self) -> tuple[str, ...]:
        """Jobs with a message that has arrived and not been drawn. Sorted, for a stable test."""
        return tuple(sorted(self._pending))

    def job_ids(self) -> tuple[str, ...]:
        """The rows, in the order they are shown."""
        return tuple(row.job.id for row in self._rows)

    def row_of(self, job_id: str) -> int | None:
        return self._index_of.get(job_id)

    def displayed_progress(self, job_id: str) -> Progress | None:
        index = self._index_of.get(job_id)
        return None if index is None else self._rows[index].displayed

    def text_at(self, job_id: str, column: int) -> str | None:
        """What one cell says, by job rather than by row index.

        For tests and for the shell: a row index is a fact about the sort, and asserting through
        one would silently pass if two jobs swapped places.
        """
        index = self._index_of.get(job_id)
        return None if index is None else self._text(self._rows[index], column)

    def accessible_text_at(self, job_id: str, column: int) -> str | None:
        index = self._index_of.get(job_id)
        return None if index is None else self._accessible_text(self._rows[index], column)

    # --- Qt's model interface ---------------------------------------------------------------

    # Qt's override names, hence the camelCase: these are not project naming choices. The default
    # parent is the module-level `_ROOT` rather than a fresh `QModelIndex()` per call, which ruff
    # rejects in a default (B008) — an invalid index is a value, not state, so one will do.
    def rowCount(self, parent: QModelIndex | _PersistentIndex = _ROOT) -> int:
        # A table model has no children under a valid index; saying so is what stops a tree view
        # from asking for rows beneath every cell.
        return 0 if parent.isValid() else len(self._rows)

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
        return COLUMN_HEADERS[section] if 0 <= section < len(COLUMN_HEADERS) else None

    def data(
        self, index: QModelIndex | _PersistentIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return self._text(row, index.column())
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return self._accessible_text(row, index.column())
        return None

    # --- what each cell says -----------------------------------------------------------------

    def _text(self, row: _Row, column: int) -> str:
        """One cell, in words. **Every column is text**; nothing is signalled by colour alone."""
        job = row.job
        if column == JOB_COLUMN:
            # The extractor's title when a probe found one, else the URL the user pasted. Never
            # empty: a row nobody can identify is worse than a long URL.
            return job.title or job.url
        if column == STATUS_COLUMN:
            return self._status_text(row)

        done, total = self._totals(row)
        if column == PROGRESS_COLUMN:
            if job.status is JobStatus.COMPLETED:
                return "100%"
            if row.is_terminal or not total:
                # A stopped job has no percentage worth stating, and an unknown total is not zero
                # percent. The accessible text carries the distinction in words.
                return INDETERMINATE_TEXT
            return f"{percent_of(done, total)}%"
        if column == SIZE_COLUMN:
            if done is None and total is None:
                return UNKNOWN_TEXT
            return f"{format_bytes(done)} of {format_bytes(total)}"

        # Speed and ETA describe work in flight. A finished job has neither, and a stale
        # "2.1 MB/s" beside a cancelled download is the same class of lie as a stale byte count.
        if row.is_terminal or row.displayed is None:
            return UNKNOWN_TEXT
        if column == SPEED_COLUMN:
            return format_speed(row.displayed.speed_bytes_per_second)
        return format_eta(row.displayed.eta_seconds)

    def _status_text(self, row: _Row) -> str:
        """The stage a worker reported, or the status when no worker is reporting one.

        Same precedence as the detail view (`T017-R3`): while a job runs, "Downloading video" is
        better information than "Downloading". At an ending the status wins outright, because
        nothing a worker said before the end can still be true afterwards.
        """
        if row.is_terminal or row.displayed is None:
            return STATUS_TEXT[row.job.status]
        return STAGE_TEXT.get(row.displayed.stage, STATUS_TEXT[row.job.status])

    def _totals(self, row: _Row) -> tuple[int | None, int | None]:
        if row.is_terminal:
            return row.ending_totals()
        if row.displayed is not None:
            return row.totals
        # Nothing drawn for a job that has not ended: the durable row is all there is, and it is
        # what a restart shows before the first message arrives.
        return (row.job.bytes_done, row.job.bytes_total)

    def _accessible_text(self, row: _Row, column: int) -> str:
        """What a screen reader hears. **Produced by the same function as the bar's words.**

        `NFR-005` is not satisfied by a cell that reads out `47%` without saying what it is 47%
        of, and the contradiction `T017-R2` found — sighted and screen-reader users told different
        things about one download — is avoided by there being one function rather than an
        agreement between two.
        """
        if column != PROGRESS_COLUMN:
            return f"{COLUMN_HEADERS[column]}: {self._text(row, column)}"
        done, total = self._totals(row)
        return describe_bar(done, total, finished=row.job.status is JobStatus.COMPLETED)

    # --- keeping up with the queue -----------------------------------------------------------

    def refresh(self) -> None:
        """Re-read every job and rebuild the rows, keeping what has been drawn for each.

        A full reset rather than a diff. The set of jobs changes when a user adds or removes
        one — rarely, and never in a burst — while the thing that changes constantly is progress,
        which does not come through here at all. Diffing this would optimise the cheap path and
        add a second place for the ordering to be decided.

        **What survives the rebuild is `displayed`**, because it is the only thing the durable row
        cannot reconstruct: it is what this table has actually shown, and `totals_for_ending`
        turns on whether it exists.
        """
        drawn = {row.job.id: row for row in self._rows}
        self.beginResetModel()
        self._rows = []
        for job in sorted(self._jobs.all_jobs(), key=_order):
            row = _Row(job)
            previous = drawn.get(job.id)
            if previous is not None:
                row.displayed = previous.displayed
                row.totals = previous.totals
            self._rows.append(row)
        self._index_of = {row.job.id: index for index, row in enumerate(self._rows)}
        self._pending = {
            job_id: message for job_id, message in self._pending.items() if job_id in self._index_of
        }
        self.endResetModel()

    def _on_progress(self, message: object) -> None:
        """Record the newest message per job. **Drawing is the timer's job.**

        Filtered by whether this table holds the job: a message for a row that is not here is not
        a message to draw, and keeping it would let `_pending` grow without bound behind a job
        that has been removed.
        """
        if not isinstance(message, Progress) or message.job_id not in self._index_of:
            return
        self._pending[message.job_id] = message
        if not self._repaint.isActive():
            self._repaint.start()

    def _on_job_changed(self, job_id: str, status: str) -> None:
        """A state change is the newer fact and is shown at once — but it is not progress.

        **It does not flush pending progress** (`T017-R1`): that would be a second, unrated route
        into drawing, and with N jobs running there are N streams of status changes to ride in on.
        Only the row that changed is rewritten, and only from the durable row.

        At an ending the pending message is **dropped** rather than deferred. Nothing a worker
        said before the end can still be true afterwards, and drawing it a tick later would
        overwrite the ending with the download that is no longer happening.
        """
        index = self._index_of.get(job_id)
        if index is None:
            # A job this table has not seen — the add dialog's first write lands before any
            # refresh. Rebuild rather than ignore it, or the row would appear only at the next
            # unrelated change.
            self.refresh()
            return
        job = self._durable(job_id)
        if job is not None:
            self._rows[index].job = job
        if self._rows[index].is_terminal:
            self._pending.pop(job_id, None)
        self._emit_row_changed(index)

    def _durable(self, job_id: str) -> Job | None:
        for job in self._jobs.all_jobs():
            if job.id == job_id:
                return job
        return None

    def _draw_pending(self) -> None:
        """One tick: draw every job holding something undrawn, then stop if nothing is left."""
        pending, self._pending = self._pending, {}
        if not pending:
            # A quiet interval: stop rather than tick forever behind a finished queue.
            self._repaint.stop()
            return
        self._renders += 1
        touched: list[int] = []
        for job_id, message in pending.items():
            index = self._index_of.get(job_id)
            if index is None:
                continue
            row = self._rows[index]
            row.displayed = message
            row.totals = (message.downloaded_bytes, message.total_bytes)
            touched.append(index)
        if touched:
            # One span rather than one signal per row: the view repaints the intersection of the
            # span with its viewport either way, and N signals is N times the work to say it.
            self.dataChanged.emit(
                self.index(min(touched), 0),
                self.index(max(touched), len(COLUMN_HEADERS) - 1),
            )

    def _emit_row_changed(self, index: int) -> None:
        self.dataChanged.emit(self.index(index, 0), self.index(index, len(COLUMN_HEADERS) - 1))

    def detach(self) -> None:
        """Stop listening to the manager, and stop the timer.

        Same reason `JobProgressView.detach` exists (`T-036`): Qt drops connections when the
        receiver dies, but `deleteLater` is asynchronous, and a model still answering `progress`
        after it was replaced is a second listener rather than a leak.

        Safe to call more than once: disconnecting something already disconnected raises, and
        being asked twice to stop listening is not an error worth propagating.
        """
        for signal, slot in (
            (self._manager.progress, self._on_progress),
            (self._manager.job_changed, self._on_job_changed),
        ):
            with suppress(RuntimeError):
                signal.disconnect(slot)
        self._repaint.stop()


class QueueView(QWidget):
    """The queue table and its empty state (`REQ-012`, `REQ-014`)."""

    #: `(job_id)` — the user selected a row. What the shell does with that is the shell's
    #: business; this widget reports and never reaches for the detail view itself.
    job_selected = Signal(str)

    def __init__(
        self,
        *,
        jobs: QueueReader,
        manager: DownloadManager,
        parent: QWidget | None = None,
        repaint_interval_ms: int = REPAINT_INTERVAL_MS,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("queueView")
        self._model = QueueModel(
            jobs=jobs, manager=manager, parent=self, repaint_interval_ms=repaint_interval_ms
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._empty = QLabel(EMPTY_TEXT, self)
        self._empty.setObjectName("queueEmptyNotice")
        self._empty.setAccessibleName("Queue is empty")
        self._empty.setTextFormat(Qt.TextFormat.PlainText)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty)

        self._table = QTableView(self)
        self._table.setObjectName("queueTable")
        self._table.setAccessibleName("Download queue")
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        # Rows are not editable and never will be: `T-081`'s reorder moves a row, it does not type
        # into one. An editable view also puts a text cursor into the keyboard order, which
        # `focus_chain` would then be wrong about.
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            JOB_COLUMN, QHeaderView.ResizeMode.Stretch
        )
        self._table.selectionModel().selectionChanged.connect(self._announce_selection)
        layout.addWidget(self._table)

        self._model.modelReset.connect(self._show_the_right_thing)
        self._show_the_right_thing()

    @property
    def model(self) -> QueueModel:
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

    def detach(self) -> None:
        self._model.detach()

    def selected_job_id(self) -> str | None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        return self._model.job_ids()[rows[0].row()]

    def select(self, job_id: str) -> bool:
        """Select `job_id`'s row. `False` when this table does not hold it."""
        index = self._model.row_of(job_id)
        if index is None:
            return False
        self._table.selectRow(index)
        return True

    def focus_chain(self) -> list[QWidget]:
        """Every keyboard-focusable control, in its intended order (`NFR-005`, `T-060`).

        **Declared per state, not once.** The empty notice is a label and takes no focus, so an
        empty queue offers nothing to tab to — and a chain claiming the table was focusable while
        it was hidden would describe a widget the user cannot reach. `T-060` established that the
        order is asserted per state rather than in general; the two states here are "has rows" and
        "does not".
        """
        return [self._table] if self._model.rowCount() else []

    def _show_the_right_thing(self) -> None:
        """The table when there are rows, the notice when there are none. Never both."""
        has_rows = self._model.rowCount() > 0
        self._table.setVisible(has_rows)
        self._empty.setVisible(not has_rows)

    def _announce_selection(self, *_: object) -> None:
        job_id = self.selected_job_id()
        if job_id is not None:
            self.job_selected.emit(job_id)


def build_queue_view(
    jobs: QueueReader,
    manager: DownloadManager,
    on_selected: Callable[[str], None] | None = None,
) -> QueueView:
    """Construct the table and connect its selection to whatever composition supplies.

    A named function for the same reason `build_progress_view` is one: "what happens when a user
    picks a row" is the wiring decision this widget deliberately does not make, and burying it in
    composition is how it comes to be forgotten.
    """
    view = QueueView(jobs=jobs, manager=manager)
    if on_selected is not None:
        view.job_selected.connect(on_selected)
    return view
