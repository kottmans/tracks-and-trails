"""The application shell window (`T-007`), and the way in to the add-URL dialog (`T-016`).

A titled, icon-bearing window with a menu bar. What `T-007` established is the frame everything
later hangs off, plus the two behaviors that are annoying to retrofit: geometry that survives a
restart, and a clean shutdown that leaves nothing on stderr.

**`T-016` adds File → Add URLs…, and nothing else.** The queue view is `T-017`; wiring a real
manager and repository into this window is `T-036`. Until that lands the window can be built
without either, and the menu item is **disabled with a status tip that says why** rather than
opening a dialog with nothing behind it — an action that appears to work and quietly does
nothing is the failure mode this project keeps finding.

Window geometry is stored separately from user settings. `ARCHITECTURE.md` §5 assigns
`settings.toml` to `core/settings.py`, which does not exist yet, and window position is not a
user setting — nobody edits it deliberately and losing it costs nothing. Its own file means
the real settings layer arrives without migrating anything. §5's table has no row for window
state at all; see `T-007`'s record, where that gap is reported rather than decided here.
"""

import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Final

from platformdirs import user_config_dir
from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent, QGuiApplication, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QSpinBox,
    QSplitter,
    QToolBar,
    QWidget,
)

from tracks_and_trails import __version__
from tracks_and_trails.core import settings
from tracks_and_trails.core.job_state import REORDERABLE
from tracks_and_trails.core.settings import SettingsProblem
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.ui.add_dialog import AddUrlDialog, JobSink
from tracks_and_trails.ui.history_view import HistoryReader, HistoryView, build_history_view
from tracks_and_trails.ui.job_detail import JobProgressView, JobReader, build_progress_view
from tracks_and_trails.ui.queue_view import QueueReader, QueueView, build_queue_view

APP_NAME: Final = "Tracks & Trails"

#: platformdirs slug, matching the paths in `ARCHITECTURE.md` §5.
APP_SLUG: Final = "tracksandtrails"

#: Used when no geometry has been stored yet, and when what was stored is unusable.
DEFAULT_SIZE: Final = QSize(960, 640)

#: Qt's geometry accessors are C++ `int`. Anything outside this range raises or triggers a
#: shiboken overflow warning before Qt ever sees it (`T027-R1`).
_INT32_MIN: Final = -(2**31)
_INT32_MAX: Final = 2**31 - 1

#: The bound actually enforced on stored coordinates, and it is far tighter than int32 on
#: purpose (`P0-R1`). Merely keeping `x`, `y` and the derived edges inside int32 is not enough:
#: `QRect.intersects` performs its own normalisation arithmetic internally, and at coordinates
#: near `INT32_MIN` that overflows, so an off-screen rectangle is reported as intersecting a
#: screen and the recovery below never fires. Rather than chase which Qt operation overflows
#: where, keep stored coordinates inside a range where none of it can — this matches Qt's own
#: `QWIDGETSIZE_MAX`, and no real display arrangement comes close to 16.7 million pixels.
_MAX_COORD: Final = 2**24 - 1

#: A restored window smaller than this is unusable — the menu bar alone needs more.
MIN_SIZE: Final = QSize(240, 160)

_ICON_DIR: Final = Path(__file__).resolve().parent.parent / "resources" / "icons"


def app_icon() -> QIcon:
    """The application icon, carrying every size Qt may ask for.

    Loads the `.ico` rather than a single PNG: it holds all seven frames (`T-003`), so Qt
    picks the right one for the title bar, task switcher and taskbar instead of rescaling one
    bitmap badly.
    """
    return QIcon(str(_ICON_DIR / "icon.ico"))


def geometry_path() -> Path:
    """`user_config_dir/tracksandtrails/window.toml`, per `ARCHITECTURE.md` §5.

    `appauthor=False` is load-bearing on Windows and a no-op on Linux. platformdirs otherwise
    inserts an author segment defaulting to the app name, giving
    `%APPDATA%\\tracksandtrails\\tracksandtrails\\` — a doubled directory that does not match
    the path §5 specifies. There is no author to name: this is not a vendor-scoped app.
    """
    return Path(user_config_dir(APP_SLUG, appauthor=False)) / "window.toml"


def _coordinate(value: object) -> int | None:
    """Return `value` if it is a geometry integer Qt can actually accept, else `None`.

    Stricter than `int(value)` on purpose, because that was the bug (`T027-R1`):

    - **Booleans are rejected**, though `bool` is a subclass of `int`. TOML `x = true` was
      being silently accepted as `x = 1`, which is a corrupt file read as a valid one.
    - **Floats are rejected outright**, so TOML `inf` and `nan` never reach `int()`, which
      raises on both — from a function whose contract is that it never raises.
    - **The 32-bit range is enforced here**, not left to Qt. `QWidget.setGeometry` takes C++
      `int`; a larger value raises `OverflowError` out of the constructor, or logs a shiboken
      overflow warning and silently truncates.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if not _INT32_MIN <= value <= _INT32_MAX:
        return None
    return value


def load_geometry(path: Path | None = None) -> dict[str, int] | None:
    """Read stored geometry, or `None` if there is nothing usable.

    **Never raises**, for any content whatsoever. A missing file is the normal first run; a
    corrupt one is a file a crash or a user damaged; a hostile one is a file someone wrote by
    hand. None of them is worth refusing to start over.
    """
    path = path or geometry_path()
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except OSError, tomllib.TOMLDecodeError, ValueError, RecursionError:
        return None

    window = data.get("window")
    if not isinstance(window, dict):
        return None

    geometry: dict[str, int] = {}
    for key in ("x", "y", "width", "height"):
        coordinate = _coordinate(window.get(key))
        if coordinate is None:
            return None
        geometry[key] = coordinate

    if geometry["width"] < MIN_SIZE.width() or geometry["height"] < MIN_SIZE.height():
        return None

    # Reject the rectangle, not just its four numbers (`P0-R1`). Each value can be in range
    # while the rectangle they describe is not, and Qt's own geometry arithmetic overflows
    # long before int32 does — see `_MAX_COORD`.
    if any(abs(geometry[key]) > _MAX_COORD for key in ("x", "y")):
        return None
    if geometry["width"] > _MAX_COORD or geometry["height"] > _MAX_COORD:
        return None
    if abs(geometry["x"] + geometry["width"]) > _MAX_COORD:
        return None
    if abs(geometry["y"] + geometry["height"]) > _MAX_COORD:
        return None
    return geometry


def moved_onto_a_screen(rect: QRect) -> QRect:
    """Return `rect` unchanged if any screen can show part of it, otherwise a centred rect.

    A window restored where no screen exists is functionally lost: the user cannot click it,
    move it, or close it. That happens without anything being corrupt — unplugging a second
    monitor is enough (`T027-R2`).
    """
    screens = QGuiApplication.screens()
    if not screens:
        return rect
    if any(screen.availableGeometry().intersects(rect) for screen in screens):
        return rect

    # PySide6 types primaryScreen() as non-optional, but Qt documents it returning null when
    # no primary screen is set — which happens on a headless session and briefly during a
    # display reconfiguration. The stub is optimistic, so the guard stays and mypy is told to
    # allow a check it believes is dead. Removing it would put an AttributeError in a code
    # path whose whole contract is that it never raises.
    primary = QGuiApplication.primaryScreen()
    fallback = screens[0] if primary is None else primary  # type: ignore[redundant-expr]
    available = fallback.availableGeometry()
    size = rect.size().boundedTo(available.size())
    recovered = QRect(available.topLeft(), size)
    recovered.moveCenter(available.center())
    return recovered


def save_geometry(window: QWidget, path: Path | None = None) -> None:
    """Write the window's current frame to disk.

    Never raises: failing to persist a window position must not turn a clean exit into a
    crash on the way out. A read-only config directory is a real deployment state, not a
    hypothetical one.
    """
    path = path or geometry_path()
    frame = window.normalGeometry() if window.isMaximized() else window.geometry()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# Window position and size, written on exit by Tracks & Trails.\n"
            "# Safe to delete: the window falls back to its default size.\n"
            "[window]\n"
            f"x = {frame.x()}\n"
            f"y = {frame.y()}\n"
            f"width = {frame.width()}\n"
            f"height = {frame.height()}\n",
            encoding="utf-8",
        )
    except OSError:
        return


class MainWindow(QMainWindow):
    """The shell window. Owns the menu bar, its own geometry, and the view of the live job."""

    #: The user asked to close. **A request, not an event** — `T-036` connects this to the
    #: shutdown lifecycle, which cancels the running job, reaps its process tree and closes the
    #: database before anything quits. The window hides immediately either way; what waits is
    #: the process, and `AGENTS.md`-approved `T013-R2` is why none of it happens on this thread.
    closing = Signal()

    def __init__(
        self,
        geometry_file: Path | None = None,
        *,
        manager: DownloadManager | None = None,
        jobs: JobSink | None = None,
        output_directory: Path | None = None,
        job_reader: JobReader | None = None,
        retry: Callable[[str], None] | None = None,
        concurrency: int | None = None,
        on_concurrency_changed: Callable[[int], None] | None = None,
        on_pause_changed: Callable[[bool], None] | None = None,
        on_remove_requested: Callable[[str], None] | None = None,
        on_reorder_requested: Callable[[list[str]], None] | None = None,
        on_clear_requested: Callable[[], None] | None = None,
        queue: QueueReader | None = None,
        history: HistoryReader | None = None,
    ) -> None:
        super().__init__()
        self._geometry_file = geometry_file
        self._job_reader = job_reader
        self._retry = retry
        self._view: JobProgressView | None = None
        self._queue: QueueView | None = None
        self._history_view: HistoryView | None = None
        #: Supplied together or not at all: the add-URL dialog needs all three, and a window
        #: holding two of them could only offer an action that fails. `T-036` passes them.
        self._manager = manager
        self._jobs = jobs
        self._output_directory = output_directory
        self.setObjectName("mainWindow")
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self._on_concurrency_changed = on_concurrency_changed
        self._on_pause_changed = on_pause_changed
        self._on_remove_requested = on_remove_requested
        self._on_reorder_requested = on_reorder_requested
        self._on_clear_requested = on_clear_requested
        self._build_menus()
        self._concurrency: QSpinBox | None = None
        #: `T-080`'s queue actions. Built with the control bar, so a window given no `concurrency`
        #: has no toolbar and therefore neither of them — the same all-or-nothing rule the add-URL
        #: action follows, and the reason `T-007`'s bare-window tests keep working.
        self._pause: QAction | None = None
        self._remove: QAction | None = None
        self._move_up: QAction | None = None
        self._move_down: QAction | None = None
        self._clear: QAction | None = None
        if concurrency is not None:
            self._build_concurrency_control(concurrency)
        self._environment = QLabel(self)
        self._environment.setObjectName("environmentSummary")
        self._environment.setAccessibleName("Environment")
        self._environment.setTextFormat(Qt.TextFormat.PlainText)
        self.statusBar().addPermanentWidget(self._environment)
        self._build_body(queue, history)
        self._restore_geometry()

    def _build_body(self, queue: QueueReader | None, history: HistoryReader | None = None) -> None:
        """The queue above, the selected job's detail below (`T-079`).

        **A splitter rather than one or the other**, because the two answer different questions:
        the table says what the queue is doing — all of it, which is the whole point of a pool of
        N — and the detail panel says everything about one job. Phase 1 could put the detail view
        straight into the central widget because there was only ever one job to show.

        The table is built only when composition supplies something to read jobs from, exactly as
        the add action is enabled only when it has all three of its collaborators. A window
        without one still works and still shows detail: `T-007`'s tests construct this window with
        no arguments at all, and a shell that required a repository to open would have made that
        impossible.
        """
        self._body = QSplitter(Qt.Orientation.Vertical, self)
        self._body.setObjectName("shellSplitter")
        self._body.setChildrenCollapsible(False)
        self.setCentralWidget(self._body)
        if queue is None or self._manager is None:
            return
        # Selecting a row shows that job — the table reports, the shell decides. `watch` needs a
        # job reader, so a window given a queue and no reader simply shows no detail rather than
        # raising out of a selection handler.
        self._queue = build_queue_view(
            queue, self._manager, self._watch_if_possible if self._job_reader is not None else None
        )
        # Remove acts on the selection, so it follows the selection rather than being enabled once
        # and left that way. Connected here rather than where the action is built, because the
        # table is built after the toolbar and the action has to exist before it can be enabled.
        self._queue.job_selected.connect(self._selection_changed)
        self._body.addWidget(self._queue)

        # **Below the queue, in the same splitter** (`T-100`). A tab would hide it, and the whole
        # reason it exists is that a user who cleared their completed jobs cannot otherwise find
        # what they downloaded (`P2PLAN-R8`) — a surface you have to go looking for does not solve
        # that. Built only when composition supplies something to read history from, exactly as the
        # queue is.
        if history is not None:
            self._history_view = build_history_view(history)
            self._body.addWidget(self._history_view)

    @property
    def watched_job_id(self) -> str | None:
        """The job the progress view is showing, if a view is installed."""
        return self._view.job_id if self._view is not None else None

    @property
    def progress_view(self) -> JobProgressView | None:
        return self._view

    def watch(self, job_id: str) -> JobProgressView:
        """Show `job_id`'s progress, replacing whatever was shown before (`T-036`, `REQ-014`).

        **The old view is detached, not merely dropped.** `deleteLater` is asynchronous, so a
        replaced view would answer manager signals for however many event loop turns it took to
        die — a second listener rather than a leak, and a second listener is how one job becomes
        two of everything the UI derives from a signal.
        """
        if self._job_reader is None:
            raise RuntimeError(
                "this window has no job reader, so it cannot show progress; composition "
                "supplies one (T-036)"
            )
        if self._view is not None:
            if self._view.job_id == job_id:
                return self._view
            self._view.detach()
            self._view.setParent(None)
            self._view.deleteLater()
        assert self._manager is not None
        self._view = build_progress_view(self._manager, self._job_reader, job_id, self._retry)
        # Into the splitter's lower pane rather than over the whole window (`T-079`): replacing
        # the central widget here would take the queue table off screen every time a job changed.
        self._body.addWidget(self._view)
        return self._view

    def _watch_if_possible(self, job_id: str) -> None:
        """Selection handler. Separate from `watch` because a signal must not raise.

        `watch` refuses without a job reader, and that refusal is right for a caller that asked
        for a view; a selection is the user clicking a row, and an exception out of a Qt slot is
        printed and swallowed rather than handled.

        **An empty id means nothing is selected** (`T081-R3`), and there is no job to show. The
        detail pane keeps whatever it was showing rather than being torn down: a user who cleared
        the selection did not ask to stop looking at what they had open, and `T-079` already
        established that the pane belongs to the user once claimed.
        """
        if job_id and self._job_reader is not None:
            self.watch(job_id)

    @property
    def history_view(self) -> HistoryView | None:
        """The history table, if this window was given something to read history from."""
        return self._history_view

    def refresh_history(self) -> None:
        """Re-read the history table. Composition calls this when the set of records can differ.

        A history row is written once and never changes, so there is nothing to subscribe to — the
        two moments the *set* can differ are a completion and a clear-finished, and composition
        knows about both.
        """
        if self._history_view is not None:
            self._history_view.refresh()

    @property
    def queue_view(self) -> QueueView | None:
        """The queue table, if this window was given something to read jobs from."""
        return self._queue

    def refresh_queue(self) -> None:
        """Re-read the queue. Called when jobs are added, which no manager signal announces."""
        if self._queue is not None:
            self._queue.refresh()

    def report_environment(self, summary: str) -> None:
        """State what this installation can and cannot do, on screen (`REQ-024`).

        In the status bar rather than a dialog: a missing ffmpeg disables features, it does not
        stop the application, and a modal on every start for a condition the user may have chosen
        is how people learn to dismiss dialogs without reading them. It is a permanent widget
        rather than a timed message, because the fact does not stop being true after five seconds.
        """
        self._environment.setText(summary)
        self._environment.setAccessibleName("Environment")
        self._environment.setToolTip(summary)

    def environment_text(self) -> str:
        return self._environment.text()

    @property
    def can_add_urls(self) -> bool:
        """Whether this window was given everything the add-URL dialog needs (`T-036`)."""
        return (
            self._manager is not None
            and self._jobs is not None
            and self._output_directory is not None
        )

    def open_add_dialog(self) -> AddUrlDialog:
        """Build and show the add-URL dialog (`T-016`).

        Returned rather than only shown, so a test can assert on it without driving a modal
        dialog — the same reason `show_about` returns its message box. `open()` rather than
        `exec()` for the same reason: `exec()` starts a nested event loop, and a test that
        entered one would never reach its assertions.
        """
        if self._manager is None or self._jobs is None or self._output_directory is None:
            raise RuntimeError(
                "this window has no download manager, job store or output directory, so it "
                "cannot add URLs; composition supplies all three (T-036)"
            )
        dialog = AddUrlDialog(
            manager=self._manager,
            jobs=self._jobs,
            output_directory=self._output_directory,
            parent=self,
        )
        # **Adding a job is the one queue change nothing announces.** The manager emits
        # `job_changed` when a worker takes a job, so a job that starts appears by itself — but a
        # job added while the pool is saturated is `QUEUED` with no worker and no signal, and
        # `REQ-012`'s promise is that it is visible *because* it is queued. The dialog closing is
        # the moment the additions are done.
        dialog.finished.connect(self.refresh_queue)
        dialog.open()
        return dialog

    def _build_concurrency_control(self, initial: int) -> None:
        """One control for `REQ-013`'s limit, in this window rather than a dialog (`ARC-007`).

        **Why here and not in a settings dialog.** Phase 4 owns the full `REQ-023` dialog covering
        eight settings; a one-control dialog built now is a layout Phase 4 would replace, while a
        control plus the TOML layer beneath it is purely additive. `ARC-007` records that trade and
        what it concedes — one control in a toolbar is easier to miss than a Settings menu item.

        **The range is the settings layer's, read from it rather than restated.** `REQ-013`'s
        minimum and `ARC-007`'s ceiling both live in `core/settings.py`; a spinbox with its own
        numbers would be a second opinion about a bound, and the bound that matters is the one
        applied to the *file* — `settings.toml` is hand-editable, so this range constrains the
        widget and never the value.
        """
        bar = QToolBar("Queue", self)
        bar.setObjectName("queueToolBar")
        bar.setMovable(False)
        # Not closable: a control the user can hide and then not find is worse than a control
        # they ignore, and this is the only way to change the limit until Phase 4's dialog.
        bar.toggleViewAction().setVisible(False)

        label = QLabel("Concurrent downloads:", bar)
        label.setObjectName("concurrencyLabel")
        bar.addWidget(label)

        box = QSpinBox(bar)
        box.setObjectName("concurrencyChoice")
        box.setRange(settings.CONCURRENCY_MINIMUM, settings.CONCURRENCY_MAXIMUM)
        box.setValue(initial)
        # `NFR-005`: the visible label is beside it, but a screen reader reads the control, and a
        # bare number announced as "spin box" says nothing about what it governs.
        box.setAccessibleName("Concurrent downloads")
        box.setAccessibleDescription(
            "How many downloads run at once. Lowering this lets downloads already running finish; "
            "it never stops one."
        )
        box.setStatusTip("How many downloads run at once")
        # `valueChanged` rather than `editingFinished`: raising the limit should start waiting work
        # as soon as the user asks, and `editingFinished` would hold that until focus moved.
        box.valueChanged.connect(self._concurrency_chosen)
        bar.addWidget(box)

        bar.addSeparator()
        self._build_queue_actions(bar)

        self.addToolBar(bar)
        self._concurrency = box

    def _build_queue_actions(self, bar: QToolBar) -> None:
        """Pause/Resume for the queue, Remove for the selected job (`UX-001`, `T-080`).

        **They share a toolbar and not a granularity**, which is the distinction `P2PLAN-R1` found
        the task's own description getting wrong. Pause and resume act on the queue and are always
        available; remove acts on whichever row is selected and is disabled when none is. Putting
        remove on the queue toolbar rather than in the detail pane is deliberate — a user removing
        several finished jobs is working in the table, and making them open each one first would be
        a per-job gesture for a queue-level chore.

        **The pause control is one checkable action, not two buttons.** Pause and Resume are the
        two states of one thing; a pair of buttons would spend the whole session with one of them
        disabled, and a screen reader would read the disabled one too.
        """
        pause = QAction("&Pause queue", self)
        pause.setObjectName("pauseQueueAction")
        pause.setCheckable(True)
        pause.setStatusTip("Stop starting new downloads; let running ones finish")
        # `NFR-005`, through the tooltip rather than through `setAccessibleName`: `QAction` has
        # no accessible-name property in Qt 6 — an action's accessible name comes from its text,
        # and the toolbar button takes its accessible *description* from the tooltip. So the
        # sentence a user is most likely to need goes here, which is that pause does not stop what
        # is already running (`UX-001`).
        pause.setToolTip(
            "Stop starting new downloads. Downloads already running finish; nothing is cancelled "
            "and no partly downloaded file is left behind."
        )
        pause.toggled.connect(self._pause_toggled)
        bar.addAction(pause)
        self._pause = pause

        remove = QAction("&Remove", self)
        remove.setObjectName("removeJobAction")
        remove.setStatusTip("Take the selected job out of the queue; files are left alone")
        # The second sentence is `UX-001`'s promise, and it belongs where the user reads it rather
        # than only in the decision that made it. Tooltip for `pause`'s reason.
        remove.setToolTip(
            "Take the selected download out of the queue. Anything already downloaded stays on "
            "disk; nothing is deleted."
        )
        remove.setEnabled(False)
        remove.triggered.connect(self._remove_selected)
        bar.addAction(remove)
        self._remove = remove

        # `REQ-016` is "reordering", not a gesture (`T-081`'s Out of scope). Two actions rather
        # than drag-and-drop: they are keyboard-reachable, which drag is not, and `NFR-005` makes
        # that the requirement rather than the nicety. Drag can be added later over the same call.
        move_up = QAction("Move &up", self)
        move_up.setObjectName("moveJobUpAction")
        move_up.setStatusTip("Move the selected job earlier in the queue")
        move_up.setToolTip(
            "Move the selected download earlier in the queue. Downloads already running keep "
            "their place — the pool has started them."
        )
        move_up.setEnabled(False)
        move_up.triggered.connect(lambda: self._move_selected(-1))
        bar.addAction(move_up)
        self._move_up = move_up

        move_down = QAction("Move &down", self)
        move_down.setObjectName("moveJobDownAction")
        move_down.setStatusTip("Move the selected job later in the queue")
        move_down.setToolTip(
            "Move the selected download later in the queue. Downloads already running keep their "
            "place — the pool has started them."
        )
        move_down.setEnabled(False)
        move_down.triggered.connect(lambda: self._move_selected(1))
        bar.addAction(move_down)
        self._move_down = move_down

        clear = QAction("&Clear finished", self)
        clear.setObjectName("clearCompletedAction")
        clear.setStatusTip("Remove finished downloads from the queue; files and history are kept")
        # The history half is the sentence that stops this looking destructive. `P2PLAN-R8` filed
        # `T-100` precisely because clearing the queue without a history view would leave somebody
        # unable to find what they had downloaded.
        clear.setToolTip(
            "Remove completed and cancelled downloads from the queue. Files stay on disk and the "
            "history of what was downloaded is kept; failed downloads stay so you can retry them."
        )
        clear.triggered.connect(self._clear_finished)
        bar.addAction(clear)
        self._clear = clear

    def _pause_toggled(self, paused: bool) -> None:
        """Hand the queue's pause state to whoever composition said owns it.

        Injected exactly as `retry` and the concurrency handler are, so the control can be driven
        in a test with no pool behind it (`ARCHITECTURE.md` §3).
        """
        if self._on_pause_changed is not None:
            self._on_pause_changed(paused)

    def _remove_selected(self) -> None:
        """Remove whichever job the table has selected, or nothing if it has none.

        The guard is not defensive clutter: the action is disabled with no selection, and an
        enabled-state check that the handler does not repeat is one keyboard shortcut away from
        being wrong.
        """
        if self._on_remove_requested is None or self._queue is None:
            return
        job_id = self._queue.selected_job_id()
        if job_id is not None:
            self._on_remove_requested(job_id)

    def _move_selected(self, offset: int) -> None:
        """Move the selected job `offset` places, and hand the whole new order over (`T-081`).

        **The whole order, not "move this one".** `JobRepository.reorder` redeals the positions the
        named jobs hold, and the caller that knows what the *user* sees is this one — the table's
        order is what they are rearranging. Sending a delta would make the repository infer the
        arrangement from a position it did not choose.

        **Only reorderable rows are named**, and the neighbour is found among those rather than at
        `index ± 1` in the table. A running job sits in the table between two pending ones, and
        swapping across it must move the pending pair past each other rather than asking the
        repository to move the running one — which it refuses, by design.
        """
        if self._on_reorder_requested is None or self._queue is None:
            return
        selected = self._queue.selected_job_id()
        if selected is None:
            return
        movable = [job_id for job_id in self._queue.model.job_ids() if self._is_movable(job_id)]
        if selected not in movable:
            return
        index = movable.index(selected)
        target = index + offset
        if not 0 <= target < len(movable):
            return
        movable[index], movable[target] = movable[target], movable[index]
        self._on_reorder_requested(movable)

    def _is_movable(self, job_id: str) -> bool:
        """Whether the queue's row for `job_id` is one the user may rearrange.

        Reads the status through the same reader the table does, so this cannot disagree with what
        is on screen. The authority is still `REORDERABLE` in the persistence layer; this asks the
        same question early so a refused reorder is not the way the user finds out.
        """
        if self._queue is None:
            return False
        job = self._queue.model.job_for(job_id)
        return job is not None and job.status in REORDERABLE

    def _clear_finished(self) -> None:
        """Ask composition to clear the finished jobs (`REQ-016`)."""
        if self._on_clear_requested is not None:
            self._on_clear_requested()

    def _selection_changed(self, job_id: str) -> None:
        """Enable the per-job actions once there is something for them to act on.

        Remove takes any row; the move actions take only a row the user may rearrange, so a
        selected running download offers Remove and not Move. An action that is offered and then
        refuses is a UI that lies about what its buttons do (`can_transition`'s note, one layer up).
        """
        if self._remove is not None:
            self._remove.setEnabled(bool(job_id))
        movable = bool(job_id) and self._is_movable(job_id)
        if self._move_up is not None:
            self._move_up.setEnabled(movable)
        if self._move_down is not None:
            self._move_down.setEnabled(movable)

    @property
    def pause_action(self) -> QAction | None:
        """The queue's pause toggle, if this window was given a control bar."""
        return self._pause

    @property
    def remove_action(self) -> QAction | None:
        """The selected job's remove action, if this window was given a control bar."""
        return self._remove

    @property
    def move_up_action(self) -> QAction | None:
        """The selected job's move-earlier action, if this window was given a control bar."""
        return self._move_up

    @property
    def move_down_action(self) -> QAction | None:
        """The selected job's move-later action, if this window was given a control bar."""
        return self._move_down

    @property
    def clear_completed_action(self) -> QAction | None:
        """The clear-finished action, if this window was given a control bar."""
        return self._clear

    def show_queue_paused(self, paused: bool) -> None:
        """Reflect the queue's pause state **without re-emitting it** (`T-080`).

        Composition connects this to `DownloadManager.queue_paused`, so the control follows the
        queue whatever changed it. Signals are blocked for the assignment because `setChecked`
        emits `toggled`, and a round trip — control tells manager, manager tells control, control
        tells manager — is how a toggle ends up fighting itself.
        """
        if self._pause is None:
            return
        blocked = self._pause.blockSignals(True)
        try:
            self._pause.setChecked(paused)
        finally:
            self._pause.blockSignals(blocked)

    def _concurrency_chosen(self, value: int) -> None:
        """Hand the new limit to whoever composition said owns it.

        This window knows neither the manager nor `settings.toml` for this purpose — the handler is
        injected exactly as `retry` is, so the widget can be driven in a test without a pool or a
        file behind it (`ARCHITECTURE.md` §3).
        """
        if self._on_concurrency_changed is not None:
            self._on_concurrency_changed(value)

    @property
    def concurrency_control(self) -> QSpinBox | None:
        """The limit control, if this window was given one."""
        return self._concurrency

    def _build_menus(self) -> None:
        """File → Add URLs…, File → Quit, and Help → About.

        Every action gets an explicit status tip and object name. Visible text is usually
        announced anyway, but `NFR-005` requires screen-reader labels on all controls, and
        relying on a default is exactly what regresses unnoticed.
        """
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")

        # Three ASCII dots rather than U+2026. The Windows convention for "this opens a dialog"
        # is "...", and the character also has to survive being read back out of UI Automation
        # and printed into a CI log — which is the *only* Windows debugging evidence this project
        # has (`ai/TESTING.md` §10), and which mangled the ellipsis to a replacement character on
        # its first run.
        add_action = QAction("&Add URLs...", self)
        add_action.setShortcut(QKeySequence.StandardKey.New)
        add_action.setMenuRole(QAction.MenuRole.NoRole)
        add_action.setObjectName("actionAddUrls")
        add_action.setEnabled(self.can_add_urls)
        add_action.setStatusTip(
            "Paste one or more URLs, probe them, and add them to the queue"
            if self.can_add_urls
            else "Unavailable until the download queue is wired up (T-036)"
        )
        add_action.triggered.connect(self.open_add_dialog)
        file_menu.addAction(add_action)
        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        # Without NoRole, Qt may treat this as an OS-level quit item and relocate or hide it.
        # This window is the whole application; keep the item where the user put their cursor.
        quit_action.setMenuRole(QAction.MenuRole.NoRole)
        quit_action.setStatusTip(f"Exit {APP_NAME}")
        quit_action.setObjectName("actionQuit")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction(f"&About {APP_NAME}", self)
        about_action.setMenuRole(QAction.MenuRole.NoRole)
        about_action.setStatusTip(f"Version and licence information for {APP_NAME}")
        about_action.setObjectName("actionAbout")
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def show_about(self) -> QMessageBox:
        """Build the About box and show it.

        Constructed explicitly rather than via `QMessageBox.about`, which does not reliably
        carry an icon — and `T-007` requires the app icon to appear here. Returned so a test
        can assert on it without driving a modal dialog.
        """
        about = QMessageBox(self)
        about.setObjectName("aboutDialog")
        about.setWindowTitle(f"About {APP_NAME}")
        about.setIconPixmap(app_icon().pixmap(64, 64))
        about.setText(f"<b>{APP_NAME}</b><br>Version {__version__}")
        about.setInformativeText(
            "A desktop front-end for yt-dlp, for Linux and Windows.<br>"
            "MIT licensed. Video and audio are equal first-class citizens."
        )
        about.setStandardButtons(QMessageBox.StandardButton.Close)
        about.open()
        return about

    def report_settings_problem(self, problem: SettingsProblem) -> QMessageBox:
        """Tell the user their settings file could not be read (`ARC-008`, `T-102`).

        **Modal, and justified by rarity rather than severity.** This fires only when a file that
        exists cannot be used — never during normal operation, and never on a first run. A status
        line would be transient and the user this exists for has already missed something: they
        will notice their concurrency back at 3 later, when the message is gone.

        **The words come from `core`**, not from here. `SettingsProblem.summary` composes them so
        they can be asserted with no display attached; this method decides only that they appear in
        a warning box with the path shown as selectable text somebody can copy into a bug report.

        `open()` rather than `exec()`, and the box is returned, exactly as `show_about` does: a
        modal driven by `exec()` blocks the event loop inside a test with nothing to dismiss it.
        """
        box = QMessageBox(self)
        box.setObjectName("settingsProblemDialog")
        box.setWindowTitle(APP_NAME)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(problem.summary)
        # Selectable so the path and the parser's line and column can be copied out. A diagnostic
        # nobody can quote is one that reaches a bug report as "it said something about settings".
        box.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.open()
        return box

    def _restore_geometry(self) -> None:
        stored = load_geometry(self._geometry_file)
        if stored is None:
            self.resize(DEFAULT_SIZE)
            return
        rect = QRect(stored["x"], stored["y"], stored["width"], stored["height"])
        self.setGeometry(moved_onto_a_screen(rect))

    # Qt's override name, hence the camelCase: this is not a project naming choice.
    def closeEvent(self, event: QCloseEvent) -> None:
        """Persist geometry on the way out.

        Runs for every close path — the menu item, the window button, or `close()` from a
        test — so no exit route silently loses the position.

        **And announces the close** (`T-036`). Quitting here would be quitting while a worker is
        still running and the database still open; `closing` starts the lifecycle that stops
        those in order, and the application exits when it reports itself finished.
        """
        save_geometry(self, self._geometry_file)
        self.closing.emit()
        super().closeEvent(event)
