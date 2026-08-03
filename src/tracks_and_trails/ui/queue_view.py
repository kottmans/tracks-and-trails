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

*(`T-119` gives the delegate a **painted** bar. That does not reopen this: what was rejected is a
widget per row, and a rectangle drawn during `paint` is not one. `DETAIL_ROLE` still carries the
same number in words, so nothing is signalled by the bar alone — `NFR-005`.)*

The accessible description is still `describe_bar`'s, so the words a screen reader hears in the
table are produced by the same function that produces them beside the bar (`NFR-005`).

## One rich row, drawn by the shared delegate — and still six fields

`T-119`: thumbnail, title, progress and state in **one row rather than a grid of columns**, drawn
by `ui/row_delegate.py` so the queue and the add dialog cannot drift apart.

**The columns did not go away; they stopped being the layout.** `COLUMN_HEADERS` is `REQ-014`
transcribed by hand, and `_text` still answers each field separately — that is what
`accessible_text_at` reads, what a screen reader hears per field, and what pins the requirement.
What changed is that the *view* is a `QListView` asking column 0 for the delegate's roles, which
compose those same answers into one row. Deleting the per-field vocabulary to achieve the rich row
would have thrown away `REQ-014`'s transcription to change a widget.

## Ordering is `queue_position`, and this does not decide it

The manager drains waiting work in `queue_position` order (`T-078`), because it is allocated
inside the insert transaction and survives a restart. The table shows that same order for the
same reason: two surfaces disagreeing about "next" is worse than either order alone. A job with
no position sorts last on its id, which is what the scheduler does with one.

**Reordering is `T-081`**, and it will change `queue_position` rather than this sort.
"""

from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any, Final, Protocol

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, QTimer, Signal
from PySide6.QtCore import QPersistentModelIndex as _PersistentIndex
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListView,
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
from tracks_and_trails.ui.row_delegate import (
    DETAIL_ROLE,
    HEADLINE_ROLE,
    HUE_ROLE,
    PROGRESS_ROLE,
    STATE_ROLE,
    THUMBNAIL_URL_ROLE,
    RowDelegate,
)
from tracks_and_trails.ui.staging import placeholder_hue
from tracks_and_trails.ui.thumbnails import ThumbnailLoader, ThumbnailStore

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
    """The two reads this table needs, named as a protocol (`ARCHITECTURE.md` §3).

    `ui/` depends on the shape of a repository rather than on `persistence`, exactly as
    `JobReader` does for the single-job view. `PersistentJobStore` satisfies both; so does a
    dictionary in a test.

    **The pair is the point** (`T079-R2`). `ARCHITECTURE.md` §3 permits a synchronous GUI read
    only when it is an *indexed single-row lookup*, and this protocol used to offer only
    `all_jobs()` — so the one place that wanted a single job scanned the whole queue for it,
    which is `SELECT *` plus deserialisation of every row inside a Qt slot. `get` is what a
    status change uses; `all_jobs` is for building the table and for an explicit refresh.
    """

    def get(self, job_id: str) -> Job | None: ...

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

    def retire_live_state(self) -> None:
        """Forget what a worker said, because it was a **different attempt** (`T079-R1`).

        A drawn message describes the attempt that produced it. `REQ-018`'s retry edge is
        `FAILED → QUEUED`, and a job in `QUEUED` has no worker: whatever is held here came from
        the attempt that failed. Left in place, a re-queued row went on saying "Downloading
        video" at the old percentage, with the old speed and ETA — and a saturated pool can leave
        that on screen for as long as the retry waits for a slot.

        **The boundary is the status, not `Job.attempts`.** Keying to the attempt counter is the
        obvious answer and it would be a guard that can never fire: nothing in this project ever
        increments `attempts`. It is a schema column with a default that no code writes, so every
        job's attempt number is `0` for life and a comparison against it is always equal.

        Not done on every rebuild: `refresh()` must keep drawn state *within* an attempt, or a
        newly added neighbour would erase the live total of a still-running job and `T017-R4`'s
        ending rule would fall back to the durable row's lagging counter.
        """
        self.displayed = None
        self.totals = (None, None)

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
        # **The three signals that change which rows exist** (`T080-R2`, `T081-R2`). `job_changed`
        # announces a job that still exists in a new state; these announce that the *set* of jobs
        # has changed, which no amount of per-job news can express. Without them the database
        # reached the state the user asked for and the table went on showing the old one
        # indefinitely — a removed job stayed on screen, and reorder and clear appeared to do
        # nothing at all.
        #
        # Each is emitted only after its write is durable, so refreshing here re-reads a queue that
        # really is in the announced state. A failed write emits nothing and the table correctly
        # keeps showing what is still stored.
        self._manager.job_removed.connect(self._on_set_changed)
        self._manager.queue_reordered.connect(self._on_set_changed)
        self._manager.queue_cleared.connect(self._on_set_changed)
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

    def job_for(self, job_id: str) -> Job | None:
        """The job behind a row, as the table currently holds it (`T-081`).

        **An indexed lookup into rows already built**, not a read (`T079-R2`). The window asks this
        to decide whether to offer the move actions, and it must get the same answer the user is
        looking at — a fresh `QueueReader.get` could disagree with the row on screen and offer a
        control for a state the table is not showing.
        """
        index = self._index_of.get(job_id)
        return None if index is None else self._rows[index].job

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

        # **The delegate's roles, composed from the very cells `_text` answers** (`T-119`). Not a
        # second rendering of the same facts: each branch below is the column it names, so a
        # change to a cell reaches the drawn row and the screen reader together.
        if role == HEADLINE_ROLE:
            return self._text(row, JOB_COLUMN)
        if role == STATE_ROLE:
            return self._text(row, STATUS_COLUMN)
        if role == DETAIL_ROLE:
            return self._detail(row)
        if role == HUE_ROLE:
            return placeholder_hue(row.job.url)
        if role == THUMBNAIL_URL_ROLE:
            return row.job.thumbnail_url
        if role == PROGRESS_ROLE:
            return self._fraction(row)

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return self._text(row, index.column())
        if role == Qt.ItemDataRole.AccessibleTextRole:
            if index.column() == JOB_COLUMN:
                # The list draws column 0, so this is what a screen reader hears for the whole
                # row — every field `REQ-014` names, not just the one the column happens to be.
                return self._whole_row(row)
            return self._accessible_text(row, index.column())
        return None

    def _detail(self, row: _Row) -> str:
        """The row's second line: percent, size, speed and ETA, in one sentence.

        Built from the columns rather than beside them, so the rich row and the per-field
        accessible text cannot say different things about one download.
        """
        parts = [
            self._text(row, PROGRESS_COLUMN),
            self._text(row, SIZE_COLUMN),
            self._text(row, SPEED_COLUMN),
            self._text(row, ETA_COLUMN),
        ]
        return " · ".join(part for part in parts if part and part != UNKNOWN_TEXT)

    def _whole_row(self, row: _Row) -> str:
        """Everything a sighted user reads from the drawn row, for a screen reader (`NFR-005`)."""
        spoken = [self._accessible_text(row, column) for column in range(len(COLUMN_HEADERS))]
        return ". ".join(spoken)

    def _fraction(self, row: _Row) -> float | None:
        """Completion from 0 to 1, or `None` when there is nothing honest to draw.

        **`None` is not zero.** An unknown total is not "0%" — the same refusal `_text` makes for
        `INDETERMINATE_TEXT`, so the bar is absent exactly when the percentage is.
        """
        if row.job.status is JobStatus.COMPLETED:
            return 1.0
        if row.is_terminal:
            return None
        done, total = self._totals(row)
        if not total or done is None:
            return None
        return min(max(done / total, 0.0), 1.0)

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

        **`QUEUED` retires the drawn message too** (`T079-R1`): it is `REQ-018`'s retry edge, and
        what was drawn belongs to the attempt that failed. See `_Row.retire_live_state`.
        """
        index = self._index_of.get(job_id)
        if index is None:
            # A job this table has not seen — the add dialog's first write lands before any
            # refresh. Rebuild rather than ignore it, or the row would appear only at the next
            # unrelated change.
            self.refresh()
            return
        # **One indexed lookup, never an enumeration** (`T079-R2`). This used to scan
        # `all_jobs()`, which in the real graph is `SELECT *` plus deserialisation of every stored
        # job, run synchronously inside this slot — `ARCHITECTURE.md` §3 allows a synchronous GUI
        # read only when it is an indexed single-row lookup, and a probe measured one transition
        # spending 150.7 ms here against `NFR-001`'s ~100 ms budget. The cost also grew with queue
        # history, so the queue got slower the longer it was used.
        job = self._jobs.get(job_id)
        row = self._rows[index]
        if job is not None:
            row.job = job
        if row.is_terminal or row.job.status is JobStatus.QUEUED:
            self._pending.pop(job_id, None)
        if row.job.status is JobStatus.QUEUED:
            row.retire_live_state()
        self._emit_row_changed(index)

    def _on_set_changed(self, *_: object) -> None:
        """A job left the queue, or the order changed. Rebuild from what is stored.

        Takes and ignores its arguments so one slot serves all three signals — `job_removed`
        carries an id, `queue_reordered` a tuple, `queue_cleared` nothing. What each of them means
        to this table is identical: the rows it holds are no longer the rows that exist.

        A full `refresh()` rather than a targeted edit, for the reason `refresh` already gives:
        the set of jobs changes rarely and never in a burst, and a second place that decides row
        order is a second place for it to disagree with `queue_position`.
        """
        self.refresh()

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
            (self._manager.job_removed, self._on_set_changed),
            (self._manager.queue_reordered, self._on_set_changed),
            (self._manager.queue_cleared, self._on_set_changed),
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
        thumbnail_loader: ThumbnailLoader | None = None,
        cache_root: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("queueView")
        self._model = QueueModel(
            jobs=jobs, manager=manager, parent=self, repaint_interval_ms=repaint_interval_ms
        )
        self._thumbnails = ThumbnailStore(
            loader=thumbnail_loader, cache_root=cache_root, parent=self
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._empty = QLabel(EMPTY_TEXT, self)
        self._empty.setObjectName("queueEmptyNotice")
        self._empty.setAccessibleName("Queue is empty")
        self._empty.setTextFormat(Qt.TextFormat.PlainText)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty)

        # **One rich row rather than a grid of columns** (`T-119`), drawn by the delegate the add
        # dialog uses. The object name is unchanged: it is what the shell and `T-086`'s file
        # actions attach to, and renaming it would be a second change riding on this one.
        self._list = QListView(self)
        self._list.setObjectName("queueTable")
        self._list.setAccessibleName("Download queue")
        self._list.setModel(self._model)
        self._list.setItemDelegate(RowDelegate(thumbnails=self._thumbnails, parent=self._list))
        self._list.setUniformItemSizes(True)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        # Rows are not editable and never will be: `T-081`'s reorder moves a row, it does not type
        # into one. An editable view also puts a text cursor into the keyboard order, which
        # `focus_chain` would then be wrong about. The delegate offers no editor here anyway —
        # this model answers no `PRESET_CHOICES_ROLE` — but the trigger is stated rather than
        # inherited, because that is the whole lesson of `T118-R9`.
        self._list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._list.selectionModel().selectionChanged.connect(self._announce_selection)
        layout.addWidget(self._list)

        # A picture arriving repaints the rows showing it; nothing about the queue changed.
        self._thumbnails.ready.connect(self._on_thumbnail_ready)
        # **The disk cache is swept with the job** (`T-119`), and only then: a file is kept while
        # any remaining job names the same thumbnail URL, which is what "two jobs for one URL
        # share it" requires. `sweep` takes what is still live rather than what just left.
        self._model.modelReset.connect(self._sweep_thumbnails)

        self._model.modelReset.connect(self._show_the_right_thing)
        # A reset drops the selection, and the per-job actions have to hear about it
        # (`T081-R3`). Removal and clearing both reset the model now, so this is the path a
        # user actually takes to end up with nothing selected — not an edge case.
        self._model.modelReset.connect(self._announce_selection)
        self._show_the_right_thing()

    @property
    def model(self) -> QueueModel:
        return self._model

    @property
    def table(self) -> QListView:
        """The widget the rows are drawn in.

        Still called `table` because that is what the shell and `T-086`'s file actions attach to,
        and what every caller names it. It is a `QListView` now — the rows are one drawn row each
        rather than a grid — but nothing outside this module uses more than `QAbstractItemView`.
        """
        return self._list

    @property
    def thumbnails(self) -> ThumbnailStore:
        return self._thumbnails

    @property
    def shows_empty_notice(self) -> bool:
        return not self._empty.isHidden()

    def empty_text(self) -> str:
        return self._empty.text()

    def refresh(self) -> None:
        self._model.refresh()

    def detach(self) -> None:
        """Stop listening, and let the thumbnail pool drain before this widget goes."""
        self._model.detach()
        self._thumbnails.close()

    def selected_job_id(self) -> str | None:
        selected = self._list.selectionModel().selectedIndexes()
        if not selected:
            return None
        return self._model.job_ids()[selected[0].row()]

    def selected_path(self) -> str | None:
        """The selected job's written file, or `None`. **`T-086`'s one question of this view.**

        `Job.output_path` is set by the completion transaction, so a job still running answers
        `None` and the open actions stay disabled — which is correct: `T-046` writes into a staging
        directory and the final name does not exist until the download succeeds.
        """
        job_id = self.selected_job_id()
        if job_id is None:
            return None
        job = self._model.job_for(job_id)
        return None if job is None else job.output_path

    def select(self, job_id: str) -> bool:
        """Select `job_id`'s row. `False` when this table does not hold it."""
        index = self._model.row_of(job_id)
        if index is None:
            return False
        self._list.setCurrentIndex(self._model.index(index, JOB_COLUMN))
        return True

    def focus_chain(self) -> list[QWidget]:
        """Every keyboard-focusable control, in its intended order (`NFR-005`, `T-060`).

        **Declared per state, not once.** The empty notice is a label and takes no focus, so an
        empty queue offers nothing to tab to — and a chain claiming the table was focusable while
        it was hidden would describe a widget the user cannot reach. `T-060` established that the
        order is asserted per state rather than in general; the two states here are "has rows" and
        "does not".
        """
        return [self._list] if self._model.rowCount() else []

    def _on_thumbnail_ready(self, _url: str) -> None:
        """A picture arrived, so the rows showing it repaint. The queue itself did not change."""
        count = self._model.rowCount()
        if count:
            self._model.dataChanged.emit(
                self._model.index(0, JOB_COLUMN), self._model.index(count - 1, JOB_COLUMN)
            )

    def _sweep_thumbnails(self) -> None:
        """Drop cached pictures no remaining job names (`T-119`, `NFR-004`).

        Driven by the model reset, which is what `job_removed`, `queue_reordered` and
        `queue_cleared` all cause — so a removed job's picture goes with it, and a picture two jobs
        shared survives until the second one goes too.
        """
        live = {
            job.thumbnail_url
            for job in (self._model.job_for(job_id) for job_id in self._model.job_ids())
            if job is not None and job.thumbnail_url
        }
        self._thumbnails.sweep(live)

    def _show_the_right_thing(self) -> None:
        """The table when there are rows, the notice when there are none. Never both."""
        has_rows = self._model.rowCount() > 0
        self._list.setVisible(has_rows)
        self._empty.setVisible(not has_rows)

    def _announce_selection(self, *_: object) -> None:
        """Report the selected job, or **the empty string when nothing is selected** (`T081-R3`).

        Deselection used to emit nothing at all, on the reading that there was no job to announce.
        But this signal is the only thing that updates the per-job actions, so "no job" was exactly
        the news the toolbar needed and never got: clearing the selection — with the keyboard, by
        clicking empty space, or through the model reset a removal now causes — left Remove, Move
        up and Move down enabled with no row to act on. Their handlers then did nothing, which is a
        control that lies about what it does.

        The empty string rather than a separate `selection_cleared` signal: one signal carrying
        "what is selected now" cannot get out of order with itself, where two can arrive in either
        order and leave the actions reflecting the older one.
        """
        job_id = self.selected_job_id()
        self.job_selected.emit(job_id if job_id is not None else "")


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
