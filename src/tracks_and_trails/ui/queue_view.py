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

from collections import Counter
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any, Final, Protocol

from PySide6.QtCore import (
    QAbstractTableModel,
    QEvent,
    QModelIndex,
    QObject,
    QPoint,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtCore import QPersistentModelIndex as _PersistentIndex
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListView,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core.errors import is_retryable
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import Job
from tracks_and_trails.core.presets import BUILT_IN_PRESETS, PRESET_OWNED_FIELDS
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
    DEPTH_ROLE,
    DETAIL_ROLE,
    EXPANDED_ROLE,
    HEADLINE_ROLE,
    HUE_ROLE,
    JOB_ID_ROLE,
    PRESET_CHOICES_ROLE,
    PRESET_ROLE,
    PROGRESS_ROLE,
    SEGMENTS_ROLE,
    SELECTOR_ROLE,
    STATE_CHIP_ROLE,
    STATE_ROLE,
    THUMBNAIL_URL_ROLE,
    VERBS_ROLE,
    RowDelegate,
    SegmentState,
)
from tracks_and_trails.ui.row_verbs import Verb, group_verbs, verbs_for
from tracks_and_trails.ui.staging import placeholder_hue
from tracks_and_trails.ui.thumbnails import ThumbnailLoader, ThumbnailStore

#: The columns, in order, with the header each shows. `REQ-014` names five things a user must be
#: able to see per job; the sixth is which job it is. Transcribed from the requirement rather than
#: generated from a field list, so a renamed attribute cannot quietly change what is on screen
#: (`ai/TESTING.md` §13).
COLUMN_HEADERS: Final = ("Job", "Status", "Progress", "Size", "Speed", "ETA")

#: What the **title-line chip** reads for each status (`T-130`, `T130-R3`, `UX-005` 2026-08-04).
#:
#: **Deliberately not `STATUS_TEXT`.** The amendment names the chip's vocabulary — `Done`, `Queued`,
#: `62%`, `Failed` — and a chip is a glance at the end of a title, so it is a word wide, not a
#: sentence: `Ready to download` becomes `Ready`, `Completed` becomes the adopted `Done`. The status
#: column keeps `STATUS_TEXT` and says the longer thing, which is why both spellings can be right.
#:
#: `RUNNING` is absent on purpose — a running row's chip is its percentage, and `_chip` falls back
#: to `STATUS_TEXT` for the case where a running job has no honest fraction yet.
CHIP_TEXT: Final[dict[JobStatus, str]] = {
    JobStatus.QUEUED: "Queued",
    JobStatus.PROBING: "Probing",
    JobStatus.READY: "Ready",
    JobStatus.POST_PROCESSING: "Processing",
    JobStatus.COMPLETED: "Done",
    JobStatus.FAILED: "Failed",
    JobStatus.CANCELLED: "Cancelled",
}

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


class _Group:
    """A playlist's rows, gathered under one header (`T-140`, `UX-005` row 9).

    **Synthesised per refresh, never stored.** A group has no state of its own — its chip is a
    count of its members and its bar is their states — so there is nothing to keep in sync and
    nothing to go stale. `T-137` records the same reasoning from the schema side, which is why
    there is no `playlists` table for this to mirror.
    """

    __slots__ = ("members", "playlist_id", "title")

    def __init__(self, playlist_id: str, title: str) -> None:
        self.playlist_id = playlist_id
        self.title = title
        self.members: list[_Row] = []


#: One line of the table: a playlist's header, or the index of a job row in `_rows` (`T-140`).
#:
#: **The tree is flattened here rather than the view becoming a `QTreeView`.** A tree view would
#: replace the list, the delegate and the geometry `T118-R7`, `T118-R8`, `T118-R12` and `T118-R15`
#: were each spent on. A flat list of these keeps every one of them, and the delegate's
#: `DEPTH_ROLE` is the only thing that has to know nesting exists.
_Visible = _Group | int


def group_members(group: _Group) -> list[_Row]:
    """A group's rows, in the playlist's own order (`T140-R3`)."""
    return list(group.members)


def _order(job: Job) -> tuple[int, str]:
    """`queue_position` first, id to break ties. See the module docstring."""
    position = job.queue_position
    return (position if position is not None else _UNPLACED, job.id)


def _preset_name_for(job: Job) -> str | None:
    """Which built-in preset describes this job's request, if any.

    Matched on **every field a preset owns**, not on the format selector alone: two presets can
    share a selector and differ in the container or the output template, and naming the wrong one
    would tell the user their download is something it is not. `PRESET_OWNED_FIELDS` is derived
    from the two dataclasses, so a field added to `Preset` is compared the day it appears
    (`T015-R1`).

    `None` for a request no built-in describes — a custom selector (`REQ-009`). The row still says
    what it is in words; what it does not do is claim to be one of the choices.
    """
    for preset in BUILT_IN_PRESETS:
        if all(
            getattr(preset, field) == getattr(job.request, field) for field in PRESET_OWNED_FIELDS
        ):
            return preset.name
    return None


#: How a row states the format it is running as, once the control is gone (`UX-005` §6).
#:
#: The same three words the add dialog's row uses, so one download is described the same way in
#: the dialog that queued it and in the queue that runs it.
FORMAT_PREFIX: Final = "Download as: "


def _duration_text(seconds: float | None) -> str:
    """A clip's length, or nothing at all when the probe learned none (`T124-R4`).

    **The same formatter the add dialog and the detail view use** — imported at call time for
    `job_detail.format_eta`'s reason, which is that `add_dialog` imports this module's delegate
    roles and a module-level import would close the cycle. Two independently written clock
    formatters drift, and the queue row is meant to read as the staging row it replaced.

    Empty rather than `UNKNOWN_TEXT` for `None`: this joins a line of optional parts, and an em
    dash between the title and the percentage says less than nothing.
    """
    from tracks_and_trails.ui.add_dialog import format_duration

    return "" if seconds is None else format_duration(seconds)


def _effective_format_text(job: Job) -> str:
    """What this job will be — or is being — downloaded as, in words (`T126-R2`, `REQ-009`).

    **The built-in's name when one describes the request, and the literal selector otherwise.**
    `REQ-009` allows a custom selector and `retarget` is not the only thing that can set one, so a
    row whose request no built-in matches must still say what it is rather than falling silent —
    which is what "including custom selectors" costs if the text is derived from the preset list
    alone. The literal is what a user can read the syntax out of, which is `REQ-009`'s own reason
    for showing it.

    Read from `job.request`, never from the chosen preset: the request is what the worker is
    given, and a rendering derived from anything else is a second opinion about the download in
    flight (`T118-R8` is this mistake in the add dialog).
    """
    name = _preset_name_for(job)
    return f"{FORMAT_PREFIX}{name or job.request.format_selector}"


class QueueModel(QAbstractTableModel):
    """Every job, one row each, coalescing a stream of progress into a bounded repaint rate."""

    #: `(job_id, preset_name)` — a row chose a format. **Reported, never written here**: the
    #: manager owns `retarget()` and is what announces the change (`T036-R1`).
    preset_chosen = Signal(str, str)

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
        #: What the table actually shows: group headers and the job rows not hidden under a
        #: collapsed one (`T-140`).
        self._visible: list[_Visible] = []
        #: Where each id sits in `_visible` — a job id, or a playlist id for a header.
        self._visible_of: dict[str, int] = {}
        #: Which playlists are open, **by id** (`T-140`). By id rather than by row for
        #: `T126-R1`'s reason: a refresh rebuilds every row and a row number stops naming the
        #: same thing, while a user who opened a playlist expects it to stay open.
        self._expanded: set[str] = set()
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

    def _in_a_drawn_group(self, row: _Row) -> bool:
        """Whether this job is a member of a playlist the table is actually drawing as a group."""
        playlist_id = row.job.playlist_id
        return playlist_id is not None and playlist_id in self._visible_of

    def job_id_at(self, row: int) -> str | None:
        """The job a **visible row** is about, or `None` for a group header (`T140-R1`).

        **Two index spaces, and they diverge the moment a playlist is collapsed.** `job_ids()` is
        the durable order — every job, hidden or not — and the view's row numbers count only what
        is drawn. `selected_job_id` indexed the first with the second, so with a three-entry
        playlist closed above an ordinary download, selecting the visible row resolved to a hidden
        member and every file action targeted a job the user could not see.

        `None` for a header is not a gap: a group's id is a *playlist* id, and returning it as a
        job id would hand `Open` and `Show in folder` something that never had a file.
        """
        if not 0 <= row < len(self._visible):
            return None
        entry = self._visible[row]
        if isinstance(entry, _Group):
            return None
        return self._rows[entry].job.id

    def download_count(self) -> int:
        """How many **downloads** the queue holds, which is not how many rows it shows (`T-140`).

        A collapsed playlist of sixteen is one row; expanded it is seventeen, counting its header.
        Neither is the answer to "how much is in the queue", and the tab count was reading
        `rowCount()` — so a sixteen-item playlist beside one download read *(17)* open and *(2)*
        closed, and the number moved when the user opened a group without the queue changing.

        `UX-005` left the tab count *proposed* rather than ruled, and this is the maintainer's
        answer of 2026-08-04: **count the work, not the lines.**
        """
        return len(self._rows)

    def row_of(self, job_id: str) -> int | None:
        """Where `job_id` sits **in the table**, or `None` when nothing shows it.

        A job inside a collapsed playlist has a row in the model and no line on screen, and
        `None` is the honest answer for it — a caller building a `QModelIndex` from a hidden job
        would select whatever happened to be at that number (`T-140`).
        """
        return self._visible_of.get(job_id)

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
        return 0 if parent.isValid() else len(self._visible)

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
        if not index.isValid() or not 0 <= index.row() < len(self._visible):
            return None
        entry = self._visible[index.row()]
        if isinstance(entry, _Group):
            # **A playlist's header answers for itself** (`T-140`). It has no job behind it, so
            # everything below — which reads `row.job` — would be answering about a job that does
            # not exist.
            return self._group_data(entry, role)
        row = self._rows[entry]
        if role == PRESET_CHOICES_ROLE and self._in_a_drawn_group(row):
            # **Entries inherit; they do not each choose** (`UX-005` row 13, `T140-R3`). Offering
            # each child its own editor let members of one playlist end up with different formats,
            # which contradicts the premise the header's single `Download as` rests on.
            return None
        if role == DEPTH_ROLE:
            # **One level, and only under a group that is actually drawn** (`T-140`). A member
            # whose group was dropped for having one entry is an ordinary row, and indenting it
            # would leave it stepped in under nothing.
            playlist_id = row.job.playlist_id
            return 1 if playlist_id is not None and playlist_id in self._visible_of else 0

        # **The delegate's roles, composed from the very cells `_text` answers** (`T-119`). Not a
        # second rendering of the same facts: each branch below is the column it names, so a
        # change to a cell reaches the drawn row and the screen reader together.
        if role == HEADLINE_ROLE:
            return self._text(row, JOB_COLUMN)
        if role == STATE_ROLE:
            return self._text(row, STATUS_COLUMN)
        if role == STATE_CHIP_ROLE:
            # **The queue draws its state as a chip; History does not** (`T-130`, `UX-005`'s
            # 2026-08-04 amendment). A queue is a list of rows in different states and the state is
            # what the eye is hunting for. Every history row is finished, so the same chip there
            # would read *Done* on all of them and be furniture — which is why this is a role the
            # model answers rather than something the shared delegate decides for both.
            return self._chip(row)
        if role == DETAIL_ROLE:
            return self._detail(row)
        if role == HUE_ROLE:
            return placeholder_hue(row.job.url)
        if role == THUMBNAIL_URL_ROLE:
            return row.job.thumbnail_url
        if role == PROGRESS_ROLE:
            return self._fraction(row)
        if role == JOB_ID_ROLE:
            return row.job.id
        if role == PRESET_CHOICES_ROLE:
            # **`Job.RETARGETABLE`, asked of the model rather than restated** (`UX-005` §6,
            # `T-126`). The control appears only while `retarget()` would accept the change; once
            # a worker holds the job the request it is reading is fixed, and a control that
            # accepted a choice the manager would refuse is `UX-005` §5's defect exactly — worse
            # here than elsewhere, because the refusal would be silent and the user would believe
            # the format changed.
            if row.job.status not in Job.RETARGETABLE:
                return None
            return tuple(preset.name for preset in BUILT_IN_PRESETS)
        if role == PRESET_ROLE:
            # What this row's request currently *is*, matched back to a preset by selector. `None`
            # means no built-in describes it — a custom selector, which the row still shows as
            # text on its last line rather than pretending it is one of the choices.
            return _preset_name_for(row.job)
        if role == SELECTOR_ROLE:
            # **What the download is actually running as, once nothing can change it** (`UX-005`
            # §6, `T126-R2`). §6 asks for *a control before start and plain format text
            # afterwards*, and the second half was missing: the control simply vanished when the
            # job left `RETARGETABLE` and nothing took its place, so a running download said
            # nothing at all about its format — on the one surface `UX-005` removed the detail
            # pane from, so there was nowhere else to look.
            #
            # Empty while the control is there **and can say it** — drawing both would put one
            # fact on the row twice, in two places that can disagree.
            #
            # **A custom selector is the case where the control cannot** (`T126-R4`, `REQ-009`).
            # The control offers built-ins, so a request no built-in describes leaves it showing
            # no selection; it used to read `INHERITED_TEXT`, which named a batch the queue does
            # not have. With that gone the row would have said nothing at all about its format
            # while still being retargetable, which is `T126-R2`'s defect arriving from the other
            # side. So the line speaks exactly when the control is silent.
            if row.job.status in Job.RETARGETABLE and _preset_name_for(row.job) is not None:
                return ""
            return _effective_format_text(row.job)
        if role == VERBS_ROLE:
            # **`is_retryable` is asked, not assumed** (`REQ-018`, `UX-005` §5). `job_detail`
            # already asks it before offering its own Retry; the row has to ask the same question
            # or it will offer a workaround that does not exist. A job with no recorded kind is
            # treated as retryable, which is what `job_detail` does and what a failure nobody
            # classified deserves.
            retryable = row.job.error_kind is None or is_retryable(row.job.error_kind)
            return verbs_for(row.job.status, retryable=retryable)

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return self._text(row, index.column())
        if role == Qt.ItemDataRole.AccessibleTextRole:
            if index.column() == JOB_COLUMN:
                # The list draws column 0, so this is what a screen reader hears for the whole
                # row — every field `REQ-014` names, not just the one the column happens to be.
                return self._whole_row(row)
            return self._accessible_text(row, index.column())
        return None

    def setData(
        self,
        index: QModelIndex | _PersistentIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        """Report the chosen preset. **This model does not write** (`T-126`, `ARCHITECTURE.md` §7).

        `retarget()` is the manager's, and it has to be: `T036-R1` cost a review round because
        composition wrote a status change through the store directly, so nothing announced it and
        a view went on showing a state the row no longer held. A request change has the same
        shape, so it takes the same route — this reports, and the shell asks the manager.

        **The row is looked up when the choice is made**, not when the editor was built. That is
        `T118-R14`: an index that outlived the row it named wrote a format chosen for one URL onto
        the next one, and the queue reorders.

        **A choice that changes nothing is not a choice** (`T126-R3`, Critical). `T126-R1` gave
        this view a commit-before-reset lifecycle, and a lifecycle commit arrives here looking
        exactly like a click: `setEditorData` refills the reopened editor from `PRESET_ROLE`, so
        once a retarget has landed the redisplayed value *is* the durable request. Reporting it
        was a closed loop with no exit —

            `refresh` → commit → `preset_chosen` → `retarget(the request it already has)` →
            `revise` answers `UNCHANGED` → `then()` is called **synchronously** by `_persist` →
            `then` is `refresh_queue` → `refresh` …

        — which ends in `RecursionError` inside the Qt event loop. The window for it is not
        exotic: any reorder, removal or clear arriving between a retarget's write and its success
        refresh, which is one queued job finishing while somebody picks a format.

        **The guard is on the value, not on the caller.** Knowing *how* `setData` was reached
        would be state about the call rather than about the download, and it would have to be
        right at every future call site; "the request already says this" is true or false on its
        own. It also fixes the quieter case the loop was hiding — opening the editor, changing
        nothing and closing it used to spend a manager round trip to write what was already there.

        `_preset_name_for` is the same function `PRESET_ROLE` answers with, so this compares the
        editor's redisplayed value against the very thing that produced it — and it compares on
        **every field a preset owns**, not the selector alone, which is what keeps two presets
        sharing a selector distinguishable here (`T015-R1`).
        """
        if role != PRESET_ROLE or not index.isValid():
            return False
        if not 0 <= index.row() < len(self._visible):
            return False
        name = value if isinstance(value, str) else None
        if name is None:
            return False
        entry = self._visible[index.row()]
        if isinstance(entry, _Group):
            # **One choice, applied to every member** (`UX-005` row 13, `T140-R3`). The group owns
            # the format, so retargeting it is retargeting all of them — emitted per job because
            # `preset_chosen` is the route a click already takes and the manager is what decides
            # whether each is still retargetable.
            #
            # `T126-R3`'s guard applies here too: a lifecycle commit that re-selects the value the
            # group already has must emit nothing, or the reset it causes re-enters this method.
            movable = [row for row in group_members(entry) if row.job.status in Job.RETARGETABLE]
            if not movable or all(name == _preset_name_for(row.job) for row in movable):
                return False
            for row in movable:
                self.preset_chosen.emit(row.job.id, name)
            return True
        if not 0 <= entry < len(self._rows):
            return False
        job = self._rows[entry].job
        if name == _preset_name_for(job):
            return False
        self.preset_chosen.emit(job.id, name)
        return True

    def flags(self, index: QModelIndex | _PersistentIndex) -> Qt.ItemFlag:
        """Editable exactly while the row offers choices, so the two cannot disagree."""
        base = super().flags(index)
        if index.isValid() and self.data(index, PRESET_CHOICES_ROLE):
            return base | Qt.ItemFlag.ItemIsEditable
        return base

    def _detail(self, row: _Row) -> str:
        """The row's second line: who and how long, then percent, size, speed and ETA.

        Built from the columns rather than beside them, so the rich row and the per-field
        accessible text cannot say different things about one download.

        **The uploader and the duration lead it** (`UX-005` §3, `T124-R4`), because they are what
        identifies the thing rather than its progress, and because that is the order the add
        dialog's row puts them in — the queue row is meant to read as the same row after the
        dialog closes. Either is omitted when the probe did not learn it; neither is invented,
        and `UNKNOWN_TEXT` is not shown for them for the reason `format_duration` gives — a field
        the extractor never named is quieter as nothing than as an em dash.
        """
        parts = [
            row.job.uploader or "",
            _duration_text(row.job.duration_seconds),
            self._text(row, PROGRESS_COLUMN),
            self._text(row, SIZE_COLUMN),
            self._text(row, SPEED_COLUMN),
            self._text(row, ETA_COLUMN),
        ]
        return " · ".join(part for part in parts if part and part != UNKNOWN_TEXT)

    def _whole_row(self, row: _Row) -> str:
        """Everything a sighted user reads from the drawn row, for a screen reader (`NFR-005`).

        **`COLUMN_HEADERS` is not the whole row any more, and this is where that shows.**
        `REQ-014`'s six columns are still the spine, but the drawn row carries two more things —
        and a field a sighted user reads and a screen-reader user does not is the `T017-R2` split,
        which is one download described differently to two people.

        - **Uploader and duration** (`UX-005` §3, `T124-R4`), named rather than read as bare values
          for the reason `_accessible_text` gives: `47%` without saying what it is 47% of is the
          shape this file already refuses. Absent fields are absent, not spoken as placeholders.
        - **The format line** (`T126-R2`), and it matters more than most: once the control
          disappears this text is the only statement anywhere of what is being downloaded.
          **Read from `SELECTOR_ROLE` rather than recomputed** (`T126-R4`): whether the line is
          there at all now depends on two things — the status *and* whether a built-in describes
          the request — and a second copy of that condition is a second place for it to drift from
          what is drawn, which is the whole of `T017-R2`.
        """
        spoken = [self._accessible_text(row, column) for column in range(len(COLUMN_HEADERS))]
        extra = [
            f"Uploader: {row.job.uploader}" if row.job.uploader else "",
            f"Duration: {duration}"
            if (duration := _duration_text(row.job.duration_seconds))
            else "",
        ]
        spoken[1:1] = [part for part in extra if part]
        index = self._index_of.get(row.job.id)
        drawn_format = "" if index is None else self.data(self.index(index, 0), SELECTOR_ROLE)
        if drawn_format:
            spoken.append(str(drawn_format))
        return ". ".join(spoken)

    def _chip(self, row: _Row) -> str:
        """What the title-line chip reads: a running row's percentage, or its status in a word.

        **Percentage only while the job is actually running** (`T130-R3`). The chip derived itself
        from `_fraction` alone, and `_fraction` returns exactly 1.0 for a completed job — so every
        finished row read `100%` where `UX-005` adopted `Done`. A fraction says how far along the
        bytes are; it does not say whether the work is still happening, and only the status does.

        Rounded from `_fraction`, so the chip and the bar under it are one number seen twice rather
        than two numbers that can disagree.
        """
        if row.job.status is JobStatus.RUNNING:
            fraction = self._fraction(row)
            if fraction is not None:
                return f"{round(fraction * 100)}%"
        return CHIP_TEXT.get(row.job.status, STATUS_TEXT[row.job.status])

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

    def _rebuild_visible(self) -> None:
        """Flatten the rows into what the table shows: headers, and the rows not hidden (`T-140`).

        **Order is the jobs' order, and a group's members are contiguous** (`T140-R4`). A header
        takes the position of its first member, so a queue the user reordered keeps reading the way
        they left it — but the members then follow it *together*, whatever their own positions are.
        Placing each member at its own durable position let an unrelated standalone row land
        between a header and its children, which draws a row as belonging to a playlist it has
        nothing to do with. The durable order still decides where the *group* sits; it no longer
        decides whether the group is a group.

        A group of one is dissolved: a heading over a single row is a heading over nothing.
        """
        groups: dict[str, _Group] = {}
        for row in self._rows:
            playlist_id = row.job.playlist_id
            if playlist_id is None:
                continue
            group = groups.get(playlist_id)
            if group is None:
                group = _Group(playlist_id, row.job.playlist_title or playlist_id)
                groups[playlist_id] = group
            group.members.append(row)
        grouped = {
            playlist_id: group for playlist_id, group in groups.items() if len(group.members) > 1
        }

        index_of = {id(row): number for number, row in enumerate(self._rows)}
        self._visible = []
        emitted: set[str] = set()
        for position, row in enumerate(self._rows):
            playlist_id = row.job.playlist_id
            group = grouped.get(playlist_id) if playlist_id is not None else None
            if group is None or playlist_id is None:
                self._visible.append(position)
                continue
            if playlist_id in emitted:
                # Already drawn, with its siblings, where its header sits.
                continue
            emitted.add(playlist_id)
            self._visible.append(group)
            if playlist_id in self._expanded:
                self._visible.extend(index_of[id(member)] for member in group.members)

        self._visible_of = {}
        for line, entry in enumerate(self._visible):
            key = entry.playlist_id if isinstance(entry, _Group) else self._rows[entry].job.id
            self._visible_of[key] = line

    def group_jobs(self, playlist_id: str) -> list[Job]:
        """Every job in `playlist_id`, in playlist order, or empty when it names no group.

        **Empty rather than raising**, because the caller is a verb router acting on an id the
        view drew a moment ago: a group that was dissolved between the paint and the click is an
        ordinary race, not a programming error. The verbs then act on nothing, which is what a
        group that no longer exists deserves.
        """
        for entry in self._visible:
            if isinstance(entry, _Group) and entry.playlist_id == playlist_id:
                return [row.job for row in group_members(entry)]
        return []

    def toggle_group(self, playlist_id: str) -> None:
        """Open or close a playlist (`T-140`). Called by the delegate's disclosure."""
        if playlist_id in self._expanded:
            self._expanded.discard(playlist_id)
        else:
            self._expanded.add(playlist_id)
        self.beginResetModel()
        self._rebuild_visible()
        self.endResetModel()

    def _group_segments(self, group: _Group) -> list[SegmentState]:
        """One block per entry, from each member's own status (`UX-005` row 9b)."""
        states: list[SegmentState] = []
        for row in group.members:
            status = row.job.status
            if status is JobStatus.COMPLETED:
                states.append(SegmentState.DONE)
            elif status in (JobStatus.RUNNING, JobStatus.POST_PROCESSING):
                states.append(SegmentState.RUNNING)
            elif status in (JobStatus.FAILED, JobStatus.CANCELLED):
                states.append(SegmentState.FAILED)
            else:
                states.append(SegmentState.WAITING)
        return states

    def _group_data(self, group: _Group, role: int) -> Any:
        """What a playlist's header row answers (`T-140`, `UX-005` rows 9a-9c)."""
        segments = self._group_segments(group)
        if role == HEADLINE_ROLE:
            return group.title
        if role == JOB_ID_ROLE:
            return group.playlist_id
        if role == VERBS_ROLE:
            # **Derived from every member, not from one that speaks for them** (`T-140`,
            # `UX-005` row 9). A playlist mid-run holds a completed track, a running one and
            # fourteen queued, so there is no member whose status is the group's.
            return group_verbs(row.job.status for row in group.members)
        if role == EXPANDED_ROLE:
            return group.playlist_id in self._expanded
        if role == SEGMENTS_ROLE:
            return segments
        if role == STATE_CHIP_ROLE:
            # **A count, never a percentage** (`UX-005` row 9a). The entries' totals arrive one
            # at a time, so a fraction across them has a denominator that grows while it runs.
            done = sum(1 for state in segments if state is SegmentState.DONE)
            return f"{done} of {len(segments)}"
        if role == DETAIL_ROLE:
            counted = Counter(segments)
            parts = [f"{len(segments)} items"]
            for state, word in (
                (SegmentState.DONE, "done"),
                (SegmentState.RUNNING, "running"),
                (SegmentState.FAILED, "failed"),
                (SegmentState.WAITING, "queued"),
            ):
                if counted[state]:
                    parts.append(f"{counted[state]} {word}")
            return " · ".join(parts)
        if role == SELECTOR_ROLE:
            # **The group carries the format its entries inherit** (`UX-005` row 13, `T140-R3`).
            # The mock puts `Download as` on the header precisely because the short child rows drop
            # their format line — and this answered nothing, so a *closed* playlist showed its
            # format nowhere at all. Derived from the members rather than stored: they are built
            # from one preset, so agreement is the normal case and disagreement is worth saying
            # out loud rather than hiding behind the first member's answer.
            #
            # **Rendered through `_effective_format_text`, not built beside it** (`T140-R3`, second
            # round). Comparing raw `format_selector` values and printing the winner showed
            # `bestvideo+bestaudio/best` on a header whose own editor offers *Best video available*
            # — the group naming a request in syntax while the control names the same request in
            # words, one row apart. An ordinary row has solved this since `T126-R2`; the group now
            # asks the same function rather than keeping a second opinion.
            #
            # Agreement is judged on the **rendered text** for the same reason. Two members can
            # differ in a preset-owned field while sharing a selector, or share a preset while
            # differing in syntax; what the user is told is one line, so that line is what has to
            # agree before the header claims they match.
            texts = {_effective_format_text(row.job) for row in group.members}
            if len(texts) == 1:
                return texts.pop()
            return f"{FORMAT_PREFIX}mixed across {len(texts)} formats"
        if role == PRESET_CHOICES_ROLE:
            # **Retargeting moves to the group** (`UX-005` row 13, `T140-R3`). Taking the child
            # editors away established only that members cannot diverge; a read-only header then
            # left no route to change a playlist's format at all.
            #
            # Offered while **any** member would still accept it, not while all of them would. A
            # track that has already downloaded cannot be re-downloaded by changing a dropdown —
            # that is the physics of it, not a silent refusal — so a playlist with one finished
            # entry and fifteen queued must still be retargetable. Requiring all of them would
            # make the control vanish the moment the first track completed, which is when a user
            # is most likely to be looking at it.
            if not any(row.job.status in Job.RETARGETABLE for row in group.members):
                return None
            return tuple(preset.name for preset in BUILT_IN_PRESETS)
        if role == PRESET_ROLE:
            # The one preset the members share, or `None` when they do not — which the header's
            # `SELECTOR_ROLE` already says out loud as *mixed across N formats*.
            names = {_preset_name_for(row.job) for row in group.members}
            return names.pop() if len(names) == 1 else None
        if role == HUE_ROLE:
            return placeholder_hue(group.members[0].job.url if group.members else group.title)
        if role == THUMBNAIL_URL_ROLE:
            return next(
                (row.job.thumbnail_url for row in group.members if row.job.thumbnail_url), None
            )
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return f"{group.title}. Playlist, {self._group_data(group, STATE_CHIP_ROLE)}"
        return None

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
        self._rebuild_visible()
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


#: Members worth cancelling. A terminal member is already where cancelling would put it.
_CANCELLABLE: Final = frozenset(
    {
        JobStatus.QUEUED,
        JobStatus.READY,
        JobStatus.PROBING,
        JobStatus.RUNNING,
        JobStatus.POST_PROCESSING,
    }
)


class QueueView(QWidget):
    """The queue table and its empty state (`REQ-012`, `REQ-014`)."""

    #: `(job_id)` — the user selected a row. What the shell does with that is the shell's
    #: business; this widget reports and never reaches for the detail view itself.
    job_selected = Signal(str)

    #: `(job_id)` — a row's **Retry** was activated (`REQ-018`, `UX-005` §4). Reported rather
    #: than performed for `job_detail`'s reason: re-queueing is a *write*, `ui/` holds no writer,
    #: and composition is what performs it. This is the same seam `retry_requested` was, moved
    #: from the detail pane to the row that replaced it.
    retry_requested = Signal(str)

    #: `(job_id)` — a row's **Remove** was activated. A write for the same reason.
    remove_requested = Signal(str)
    #: **A group removal carries its members** (`T-140`, `DAT-005` §4). Separate from
    #: `remove_requested` because the confirmation has to name a count, and a shell receiving one
    #: id at a time cannot say "these 16" — it would ask sixteen times or not at all.
    group_remove_requested = Signal(str, object)

    #: `(job_id, delta)` — a row asked to move, `-1` up and `+1` down. Reordering is durable
    #: (`T-081`), so it is composition's to perform.
    move_requested = Signal(str, int)

    #: `(job_id)` — a row's file verb was activated. `FileActions` owns containment (`SEC-001`)
    #: and the shell owns `FileActions`, so the row asks rather than opening anything itself.
    open_requested = Signal(str)
    reveal_requested = Signal(str)

    #: `(job_id)` — the row's `⋯` was activated, by pointer or by keyboard. The overflow menu is
    #: the shell's, because what belongs in it is a shell question.
    #: A row asked for its menu: the row's id, and **what the menu should hold** (`T-135`).
    #:
    #: The contents travel with the request because the two routes want different things and only
    #: this widget can tell them apart. The `⋯` button holds what the row could not draw — that is
    #: what it is for, and listing everything there offered the same actions twice on any row wide
    #: enough to show them. The Menu key, Shift+F10 and a right-click hold **everything the state
    #: permits**, because they are not asking about the row's width.
    more_requested = Signal(str, object)

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
        #: Held so a row's **Cancel** can reach it. Cancelling is not a write — it asks the
        #: manager to stop a session it already owns — so it is the one verb this widget performs
        #: rather than reports (`ARCHITECTURE.md` §7).
        self._manager = manager
        self._model = QueueModel(
            jobs=jobs, manager=manager, parent=self, repaint_interval_ms=repaint_interval_ms
        )
        #: The job whose editor was open when a reset began, carried across it (`T126-R1`).
        self._reopen_for: str | None = None
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
        self._delegate = RowDelegate(thumbnails=self._thumbnails, parent=self._list)
        self._list.setItemDelegate(self._delegate)
        # **Cancel is performed here; everything else is reported.** The split is `ui/`'s writer
        # rule (`ARCHITECTURE.md` §7): cancelling is asking the manager to stop a session it owns,
        # which this widget already holds, while re-queueing, reordering and removing are writes
        # and belong to composition. `job_detail` drew the same line for the same reason.
        # **The pointer is watched so the row's verbs can react to it** (`T-134`). Not a
        # default: a viewport's mouse tracking is off, so without this Qt reports the
        # pointer only while a button is held.
        self._delegate.watch_hover(self._list)
        # **Opening a playlist is the model's to decide** (`T-140`). The delegate reports the
        # click; which rows exist is not its answer to give.
        self._delegate.disclosure_toggled.connect(self._model.toggle_group)
        # **The disclosure's keyboard route** (`T140-R5`, `NFR-005`). Until this the only way to
        # open a playlist was a left-button release inside the twisty's rectangle, so a keyboard
        # user could reach a group header, hear it announced as a playlist, and have no way to see
        # what was inside it. `T-140`'s own acceptance criteria call expanding and collapsing
        # keyboard reachable; the review found the criterion accepted and unbuilt.
        #
        # `Right`/`Left` rather than `Space` or `Return`: they are what a tree does everywhere, and
        # both are unbound on a flat `QListView`, so nothing is taken away from an ordinary row.
        # Installed on the *list* rather than the viewport because key events go to the focused
        # widget, and the delegate's own filter watches the viewport for pointer events.
        self._list.installEventFilter(self)
        self._delegate.verb_triggered.connect(self._on_verb)
        # **Rows are no longer uniform, and that is spent deliberately** (`T-140`, `UX-005`
        # row 9c). `setUniformItemSizes` lets the view compute the visible range arithmetically
        # instead of measuring every row, and `T118-R10` is the record of what per-row cost buys
        # when it goes wrong — a paste of 150 cost 0.722 s on hosted Windows. A playlist entry is
        # two lines against its group's four, so the promise is already false the moment a group
        # is open; keeping it would mean drawing entries at full height and wasting a third of
        # the list on blank space in exactly the case with least room to waste.
        self._list.setUniformItemSizes(False)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        # **`EDIT_KEY` is the declared keyboard route to the row's format control** (`T118-R9`,
        # `T124-R1`, `UX-005` §6). `EditKeyPressed` *is* `row_delegate.EDIT_KEY`, and it is stated
        # here rather than inherited from a Qt default, which is that finding's whole point.
        #
        # *(This said "rows are not editable and never will be… this model answers no
        # `PRESET_CHOICES_ROLE`". `T-126` gave it one, and the comment stayed — so the queue drew
        # a format control that only a pointer could reach, and `NFR-005`'s keyboard parity was
        # false on the surface that declared it. Corrected here rather than deleted, because the
        # sentence is the record of how the route went missing.)*
        #
        # **No `SelectedClicked`.** The add dialog needs it; here the delegate's own hit test on
        # `_control_rect` is the mouse route, and it is narrower — clicking anywhere on an already
        # selected row would otherwise open a format editor the user did not ask for.
        self._list.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed)
        # **The overflow's keyboard route** (`UX-005` §4, `T124-R1`). `CustomContextMenu` for
        # `FileActions`' reason: Qt raises `customContextMenuRequested` for the Menu key and
        # Shift+F10 as well as for the mouse, so `⋯` is reachable without a pointer through one
        # code path rather than two. The shell builds the menu, because what belongs in it is a
        # shell question — this only says which row was asked about.
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._row_menu_asked_for)
        self._list.selectionModel().selectionChanged.connect(self._announce_selection)
        layout.addWidget(self._list)

        # **The editor is committed before every structural reset and reopened after it**
        # (`T126-R1`, `T118-R14`). `modelAboutToBeReset` is emitted from `beginResetModel()`,
        # which `refresh()` calls *before* it replaces `_rows` — so the open editor's index still
        # resolves to the job the user is choosing a format for. After the reset the row number
        # may name a different job, or no job, which is why the restore is by id.
        self._model.modelAboutToBeReset.connect(self._commit_open_editor)

        # A picture arriving repaints the rows showing it; nothing about the queue changed.
        self._thumbnails.ready.connect(self._on_thumbnail_ready)
        # **The disk cache is swept with the job** (`T-119`), and only then: a file is kept while
        # any remaining job names the same thumbnail URL, which is what "two jobs for one URL
        # share it" requires. `sweep` takes what is still live rather than what just left.
        # **The paint-time overflow record does not survive a reset** (`T-135`). A job that
        # left the queue would otherwise keep an entry keyed by its id, and rows that
        # scroll out of view are never repainted to correct it.
        self._model.modelReset.connect(self._delegate.forget_dropped)
        self._model.modelReset.connect(self._sweep_thumbnails)

        self._model.modelReset.connect(self._show_the_right_thing)
        # A reset drops the selection, and the per-job actions have to hear about it
        # (`T081-R3`). Removal and clearing both reset the model now, so this is the path a
        # user actually takes to end up with nothing selected — not an edge case.
        self._model.modelReset.connect(self._announce_selection)
        # **Last of the reset slots**, so the editor is reopened onto a list that has already been
        # shown or hidden by `_show_the_right_thing`. Reopening onto a hidden view would lay out a
        # control nobody can see and then destroy it at the next reset.
        self._model.modelReset.connect(self._reopen_editor)
        self._show_the_right_thing()

    def _on_verb(self, job_id: str, verb: object) -> None:
        """Route a row's verb, and refuse anything this widget does not recognise.

        **The unknown case raises rather than passing silently.** A verb added to `row_verbs` and
        forgotten here would draw a button that does nothing, which is precisely the failure
        `T-016` records — an action that appears to work and quietly does not. The row only offers
        what `verbs_for` returned, so an unroutable verb is a programming error and should read
        like one.
        """
        if verb is None:
            # The `⋯` is drawn only when something was dropped, so this is never empty (`T-135`).
            self.more_requested.emit(job_id, self._delegate.overflowing(job_id))
            return
        # The signal carries `object` because Qt has no `Verb` type; narrowing here is where the
        # contract is checked rather than assumed. A value that is not a verb is the same class of
        # programming error as an unrouted one, and raises for the same reason.
        if not isinstance(verb, Verb):
            raise TypeError(f"a row reported {verb!r}, which is not one of its verbs")

        # **A group's verbs are routed first, and the model is what says the id is a group.**
        # `job_id` is a *playlist* id when a header reported it, and the two spaces are not
        # distinguishable by inspection. Routing on the verb alone is wrong and was tried:
        # `Show in folder` and `Remove` are offered by ordinary rows as well, so every row's
        # *Remove* would have gone down the group path. `group_jobs` searches the visible groups
        # for that id and answers empty for anything else, which is the authority — a job id
        # cannot name a group unless a group has it, and both are uuid4.
        if self._model.group_jobs(job_id):
            self._on_group_verb(job_id, verb)
            return
        if verb is Verb.CANCEL:
            self._manager.cancel(job_id)
        elif verb is Verb.RETRY:
            self.retry_requested.emit(job_id)
        elif verb is Verb.REMOVE:
            self.remove_requested.emit(job_id)
        elif verb is Verb.MOVE_UP:
            self.move_requested.emit(job_id, -1)
        elif verb is Verb.MOVE_DOWN:
            self.move_requested.emit(job_id, 1)
        elif verb is Verb.OPEN:
            self.open_requested.emit(job_id)
        elif verb is Verb.REVEAL:
            self.reveal_requested.emit(job_id)
        else:
            raise AssertionError(f"the row offered {verb.value} and nothing routes it")

    def _on_group_verb(self, playlist_id: str, verb: Verb) -> None:
        """Act on every member the verb applies to (`T-140`, `UX-005` row 9).

        **Filtered per verb, not applied to all.** `Retry failed` on a group of sixteen with two
        failures must retry two, and cancelling the fourteen that are merely queued would be a
        different and destructive reading of the same click.

        **`Remove` goes out as one signal carrying its members**, because `DAT-005` §4 makes the
        confirmation name its own count and a shell told one id at a time cannot say *these 16*.
        """
        jobs = self._model.group_jobs(playlist_id)
        if verb is Verb.CANCEL_ALL:
            for job in jobs:
                if job.status in _CANCELLABLE:
                    self._manager.cancel(job.id)
        elif verb is Verb.RETRY_FAILED:
            for job in jobs:
                if job.status is JobStatus.FAILED:
                    self.retry_requested.emit(job.id)
        elif verb is Verb.REVEAL:
            # One folder for the whole playlist (`UX-005` row 10), so revealing any member reveals
            # it. The first *completed* member is the one with a file on disk to point at.
            done = next((job for job in jobs if job.status is JobStatus.COMPLETED), None)
            if done is not None:
                self.reveal_requested.emit(done.id)
        elif verb is Verb.REMOVE:
            self.group_remove_requested.emit(playlist_id, [job.id for job in jobs])

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """`Right` opens the focused playlist and `Left` closes it (`T140-R5`, `NFR-005`).

        **Only ever on a group header.** `EXPANDED_ROLE` answers `None` for an ordinary row, so an
        entry or a standalone download sees these keys exactly as it did before — which is what
        keeps this from stealing a key the list may want later.

        **Directional rather than a toggle**, because the two keys already mean something to
        anyone who has used a tree: pressing `Right` on an open group should leave it open, not
        close it. A single toggle key would make the outcome depend on state the user cannot see
        without looking, and a screen-reader user is exactly who cannot.
        """
        if watched is self._list and event.type() == QEvent.Type.KeyPress:
            key = event.key()  # type: ignore[attr-defined]
            if key in (Qt.Key.Key_Right, Qt.Key.Key_Left):
                index = self._list.currentIndex()
                expanded = self._model.data(index, EXPANDED_ROLE)
                playlist_id = self._model.data(index, JOB_ID_ROLE)
                if isinstance(expanded, bool) and isinstance(playlist_id, str) and playlist_id:
                    wants_open = key == Qt.Key.Key_Right
                    if wants_open != expanded:
                        self._model.toggle_group(playlist_id)
                    # Consumed either way: `Right` on an already open group is a no-op the user
                    # asked for, not a request for the list's default horizontal scroll.
                    return True
        return bool(super().eventFilter(watched, event))

    def _row_menu_asked_for(self, position: QPoint) -> None:
        """The Menu key, Shift+F10 or a right-click asked for a row's overflow (`T124-R1`).

        **The current row when the position names none**, which is the keyboard case: Qt raises
        this signal for the Menu key with a position derived from the widget rather than from a
        row, so resolving through `indexAt` alone answered "no row" for every keyboard request and
        the declared route silently did nothing. `NFR-005` asks that the keyboard reach what the
        pointer reaches; a route that only a pointer can aim is not that.

        Routed through `more_requested` — the same signal `⋯` emits — so the shell builds one menu
        for both, and a guard added to one cannot be missing from the other (`trigger_verb`'s
        reasoning, one step earlier in the same path).
        """
        at = self._list.indexAt(position)
        index = at if at.isValid() else self._list.currentIndex()
        if not index.isValid():
            return
        job_id = self._model.data(index, JOB_ID_ROLE)
        if isinstance(job_id, str) and job_id:
            # **Everything, not the overflow.** A keyboard route whose contents changed with the
            # window's width would be a different menu on a maximised window (`NFR-005`, `T-135`).
            self.more_requested.emit(job_id, self.verbs_of(job_id))

    def _commit_open_editor(self) -> None:
        """Write the open editor's choice through **before** the rows are replaced (`T126-R1`).

        The whole correction is the ordering. `QueueModel.refresh()` calls `beginResetModel()` —
        which is what emits the signal this is connected to — and only then rebuilds `_rows`, so
        `setData` still resolves the editor's row number to the job the user was choosing for.
        Committing after the reset reaches Qt's own guard instead: the view no longer owns the
        editor, `commitData` warns and returns, `setData` is never called, and the visible choice
        is discarded without a word while the download runs as whatever it was.

        The job is remembered first, because committing forgets it.
        """
        self._reopen_for = self._delegate.editing_job_id
        self._delegate.commit_and_close_editor()

    def _reopen_editor(self) -> None:
        """Put the editor back on the same **job** after a rebuild (`T126-R1`).

        By id, never by row number: a reorder is one of the three things that causes the reset, so
        the number the editor had is precisely what cannot be trusted. A job that was removed, or
        that a worker has taken since — leaving it outside `Job.RETARGETABLE` and so no longer
        editable — gets no editor back, which is `UX-005` §5: nothing is offered that would be
        refused.
        """
        job_id, self._reopen_for = self._reopen_for, None
        if job_id is None:
            return
        row = self._model.row_of(job_id)
        if row is None:
            return
        index = self._model.index(row, JOB_COLUMN)
        if not self._model.flags(index) & Qt.ItemFlag.ItemIsEditable:
            return
        self._list.setCurrentIndex(index)
        self._list.edit(index)

    def trigger_verb(self, job_id: str, verb: Verb) -> None:
        """Activate a verb from somewhere other than the row — the overflow menu, or a key.

        **The same route a click takes.** The menu could have emitted the shell's signals itself,
        and then the pointer route and the keyboard route would be two implementations of one
        action, differing the first time one of them gained a guard. `NFR-005` asks for the
        keyboard to reach what the pointer reaches; that is only true if it reaches it *the same
        way*.
        """
        self._on_verb(job_id, verb)

    def verbs_of(self, job_id: str) -> tuple[Verb, ...]:
        """What the row for `job_id` offers, asked of the model the delegate asks.

        **Read through the role rather than recomputed.** A second call to `verbs_for` here would
        be a second opinion about what a row offers, and the overflow menu exists to hold exactly
        what the row could not fit — so a menu that disagreed with the row would be worse than no
        menu. Empty for a job the queue does not hold.
        """
        row = self._model.row_of(job_id)
        if row is None:
            return ()
        offered = self._model.data(self._model.index(row, 0), VERBS_ROLE)
        return tuple(offered or ())

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
        # **Through the model's own mapping** (`T140-R1`). This indexed `job_ids()` — the durable
        # order — with a *visible* row number, which agree only while nothing is collapsed.
        return self._model.job_id_at(selected[0].row())

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
        It was the toolbar's per-job actions that made "no job" the news that mattered: clearing the
        selection — with the keyboard, by clicking empty space, or through the model reset a removal
        causes — left Remove, Move up and Move down enabled with no row to act on, and their
        handlers then did nothing, which is a control that lies about what it does.

        **Those three actions are gone** (`T124-R3`, `UX-005` §4): nothing on the toolbar reads a
        selection any more, so the shell no longer connects to this. The signal stays, and stays
        total, because it is this widget's report of *what is selected now* rather than a private
        arrangement with one consumer — `build_queue_view` takes an `on_selected` for whoever wants
        it next. A signal that announced only non-empty selections would be the same trap set for
        that caller.

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
