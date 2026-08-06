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
from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path
from typing import Final, cast

from platformdirs import user_config_dir
from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QCursor,
    QGuiApplication,
    QIcon,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QSpinBox,
    QToolBar,
    QToolButton,
    QWidget,
)

from tracks_and_trails import __version__
from tracks_and_trails.core import presets, settings
from tracks_and_trails.core.job_state import REORDERABLE
from tracks_and_trails.core.settings import SettingsProblem
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.ui.add_dialog import AddUrlDialog, JobSink
from tracks_and_trails.ui.file_actions import MESSAGE_TIMEOUT_MS, FileActions
from tracks_and_trails.ui.job_detail import JobReader
from tracks_and_trails.ui.queue_view import QueueReader, QueueView, build_queue_view
from tracks_and_trails.ui.row_verbs import LABELS, Verb

APP_NAME: Final = "Tracks & Trails"

#: platformdirs slug, matching the paths in `ARCHITECTURE.md` §5.
APP_SLUG: Final = "tracksandtrails"

#: The two tabs `UX-005` names. The count is appended at runtime, so these are the stems rather
#: than what is displayed — a test asserting on the visible text must expect "Queue (3)".

#: What the toolbar's primary action reads (`UX-005`'s 2026-08-04 amendment, `T-130`).
#:
#: The B1-b mockup names it exactly this. It is the action's `iconText`, not its `text`: the File
#: menu keeps *"Add URLs..."*, where a leading `+` would be a convention nobody uses.
ADD_URLS_BUTTON: Final = "+ Add URLs"

#: The dynamic property the style sheet fills a toolbar's primary button against (`T-132`).
#:
#: **A role, not a name.** `theme.py` must style by class so a widget nobody remembered still gets
#: themed — `test_the_sheet_styles_by_class_so_a_new_widget_inherits_it` — and an object-name
#: selector would have made a second primary action somewhere else silently draw flat. Named here
#: rather than written into both the widget and the sheet, because a selector that stops matching
#: fails silently: the button just goes back to looking like the other three.
#: What the concurrency control's step buttons read (`T-141`, `UX-005` row 11).
#:
#: A true minus sign rather than a hyphen: at this size a hyphen reads as a dash in a sentence,
#: and the pair has to look like a pair.
STEP_DOWN_LABEL: Final = "\u2212"
STEP_UP_LABEL: Final = "+"

#: The dynamic property the sheet styles the concurrency step buttons against (`T-141`).
#: A role, not a name, for the reason `PRIMARY_ACTION_PROPERTY` gives.
STEP_BUTTON_PROPERTY: Final = "stepButton"

PRIMARY_ACTION_PROPERTY: Final = "primaryAction"

#: The dynamic property marking the toolbar's expanding spacer, so the sheet can stop it
#: painting over the toolbar (`T-132`). A role, not a name — same reason as above.
TOOLBAR_SPACER_PROPERTY: Final = "toolbarSpacer"


def _verbs(carried: object) -> tuple[Verb, ...]:
    """Narrow a `more_requested` payload to verbs (`T-135`).

    The signal carries `object` because Qt has no `Verb` type, so this is where the contract is
    checked rather than assumed — the same place and the same reason as `QueueView._on_verb`.
    Anything else is a programming error and is dropped to an empty menu rather than raised,
    because a shell that crashed on a right-click would be a worse failure than a missing menu.
    """
    if not isinstance(carried, tuple | list):
        return ()
    return tuple(verb for verb in carried if isinstance(verb, Verb))


def group_removal_question(count: int) -> str:
    """The queue's group confirmation, naming its own count (`DAT-005` §4, `UX-005` row 9).

    Removing a playlist from the queue stops downloads that have not finished, so the wording says
    *from the queue* rather than anything about records. Singular is written out: "1 downloads" is
    the tell that a message was assembled rather than composed.

    *(It had a sibling, `removal_question`, which said *from history*. That went with the History
    list at `T-169`; the contrast it was written against is why this one names the queue.)*
    """
    return (
        "Remove this download from the queue?"
        if count == 1
        else f"Remove these {count} downloads from the queue?"
    )


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
    ) -> None:
        super().__init__()
        self._geometry_file = geometry_file
        self._job_reader = job_reader
        self._retry = retry
        self._row_counts: dict[int, int] = {}
        self._queue: QueueView | None = None
        #: `T-086`'s open/reveal, one set per table. Held so they outlive `_build_body` — a
        #: `QObject` whose only reference was a local is collected, taking its connections.
        self._file_actions: list[FileActions] = []
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
        #:
        #: **Two, since `T124-R3`.** *Remove*, *Move up* and *Move down* were here too, acting on
        #: the queue's selection, and `UX-005` chose row verbs *"rather than a toolbar acting on a
        #: selection"* — because with two tabs that toolbar has to guess which list it means, and
        #: it guessed wrong: they stayed enabled and aimed at the hidden queue's selection while
        #: History was in front. The row route was added without the rejected one being removed.
        #: What is left is queue-*wide* and unambiguous whichever tab is showing.
        self._pause: QAction | None = None
        self._clear: QAction | None = None
        #: The toolbar's copy of File → Add URLs…, or `None` on a window with no control bar.
        self._add_urls_button: QAction | None = None
        if concurrency is not None:
            self._build_concurrency_control(concurrency)
        self._environment = QLabel(self)
        self._environment.setObjectName("environmentSummary")
        self._environment.setAccessibleName("Environment")
        self._environment.setTextFormat(Qt.TextFormat.PlainText)
        self.statusBar().addPermanentWidget(self._environment)
        self._build_body(queue)
        self._restore_geometry()

    def _build_body(self, queue: QueueReader | None) -> None:
        """The Queue, as the whole of the window (`UX-005`, amended 2026-08-06 by `T-169`).

        **One surface, and no tab widget.** This was `Queue` and `History` as tabs, each with a
        count — the design `UX-005` chose over a splitter, and the counts were what answered the
        objection that a tab hides a list. `T-169` removed History as a product: `REQ-020` is now a
        private ledger with nothing to browse, so the second tab has no contents rather than fewer
        of them.

        **A tab strip holding one tab was rejected rather than overlooked.** It offers a choice the
        user does not have, which is the same objection `UX-005` §5 makes to drawing a verb that
        would be refused. The queue is the central widget directly.

        Built only when composition supplies something to read, exactly as the add action is
        enabled only when it has all three of its collaborators. `T-007`'s tests construct this
        window with no arguments at all, so no central widget is a valid window.
        """
        if queue is None or self._manager is None:
            return
        # **No selection callback.** Selecting a row opened the detail pane; `UX-005` removes the
        # pane, so selecting a row now opens nothing and the row itself carries what a user needs
        # to know (`T-119`'s anatomy). The manager and reader are still held: what becomes of
        # `T-017`'s `JobProgressView` is deferred by `UX-005` rather than decided, so nothing here
        # deletes its collaborators.
        self._queue = build_queue_view(queue, self._manager, None)
        self._connect_row_verbs(self._queue)
        self.setCentralWidget(self._queue)
        self._attach_file_actions()

        # **The declared keyboard route needs the key, not only a row** (`T-152`, second round,
        # `NFR-005`). The first fix gave the view a current index, which is what
        # `_row_menu_asked_for` falls back to — and `Shift+F10` still did nothing, because Qt
        # delivers it to the *focused* widget and nothing here ever focused a view. Measured on a
        # freshly opened window: `QSpinBox concurrencyChoice`, the toolbar's stepper.
        #
        # **Rows arriving is the other moment the key can be placed** — but only the *first* rows
        # (`P2EXIT-R13`). An empty view hides its list and cannot hold focus at construction, so a
        # first run would otherwise start with no view focusable at all.
        self._queue.table.model().modelReset.connect(self._first_rows_arrived)
        self._row_counts = {id(self._queue): self._queue.table.model().rowCount()}
        self._give_the_rows_the_keyboard()

    def _first_rows_arrived(self, *_ignored: object) -> None:
        """Place the keyboard when the queue gains its first rows, and at no other reset.

        **Two conditions, and both are load-bearing** (`P2EXIT-R13`): the view **was empty** and is
        not any more — a refresh of an already-populated list is not a moment anything needs to be
        focused — and `_give_the_rows_the_keyboard` still declines when something in the view
        already holds the keyboard.

        *(The third condition was "the view is the visible one", which stopped a hidden History
        refresh reaching across to the tab the user was on. There is one view now, so the check has
        nothing left to distinguish; the seam it closed is gone with the tab widget.)*

        The count is remembered rather than read from a signal, because `modelReset` carries
        nothing and *"the list is not empty"* is not the question — *"the list just stopped being
        empty"* is.
        """
        if self._queue is None:
            return
        key = id(self._queue)
        was_empty = self._row_counts.get(key, 0) == 0
        now = self._queue.table.model().rowCount()
        self._row_counts[key] = now
        if was_empty and now:
            self._give_the_rows_the_keyboard()

    def _give_the_rows_the_keyboard(self, *_ignored: object) -> None:
        """Focus the queue's rows, so the keyboard route reaches them (`T-152`, `NFR-005`).

        **Through `focus_chain()` rather than at the list directly.** That method is already the
        views' declaration of what is focusable in the state they are in, and it answers empty
        when there are no rows — so this asks the existing authority instead of becoming a second
        opinion that could disagree with it (`T-060`).

        Does nothing when the chain is empty, and nothing when the view already holds the
        keyboard — so a refresh cannot move the keyboard out from under somebody reading rows.
        It **can** take focus from a toolbar control at the moment a first row arrives; that seam
        is stated at the connection above rather than papered over here.
        """
        view = self._queue
        if view is None:
            return
        chain = view.focus_chain()
        if not chain or any(each.hasFocus() for each in chain):
            return
        chain[0].setFocus(Qt.FocusReason.OtherFocusReason)

    def _connect_row_verbs(self, view: QueueView) -> None:
        """Give the row's verbs the same destinations the toolbar's have (`UX-005` §4, `T-124`).

        **Every one lands on an implementation that already existed.** The row is a second route
        to the same effects, not a second implementation of them — a *Remove* on the row that did
        not go through `_remove_job` would be one guard away from behaving differently from the
        toolbar's, and nobody would find out until the two disagreed in front of a user.

        `Cancel` is absent here on purpose: `QueueView` performs it, because asking the manager to
        stop a session it owns is not a write and does not need composition (`ARCHITECTURE.md`
        §7). Every other verb is a write, or opens a file, and both belong to the shell.
        """
        view.retry_requested.connect(self._retry_each_of)
        view.remove_requested.connect(self._remove_job)
        view.group_remove_requested.connect(self._remove_group)
        view.move_requested.connect(self._move_job)
        view.open_requested.connect(lambda job_id: self._file_verb(job_id, reveal=False))
        view.reveal_requested.connect(lambda job_id: self._file_verb(job_id, reveal=True))
        view.more_requested.connect(self._show_row_menu)
        view.model.preset_chosen.connect(self._retarget_job)

    def _retry_each_of(self, job_id: str) -> None:
        """One row's *Retry*, through the same callback the interrupted-jobs offer uses."""
        if self._retry is not None:
            self._retry(job_id)

    def _file_verb(self, job_id: str, *, reveal: bool) -> None:
        """Open or reveal a named job's file, **through `FileActions`** (`REQ-021`, `SEC-001`).

        The row selects itself and then triggers the existing action rather than resolving a path
        of its own. Containment — that the path is inside the download directory — lives in
        `FileActions` and is what makes opening a file safe at all; a second route that resolved
        its own path would be a second place for that check to be missing, which is the shape of
        `SEC-001` failures rather than a style preference.
        """
        if self._queue is None:
            return
        actions = next(
            (each for each in self._file_actions if each.table is self._queue.table), None
        )
        if actions is None:
            return
        self._queue.select(job_id)
        if reveal:
            actions.reveal_selected()
        else:
            actions.open_selected()

    def _retarget_job(self, job_id: str, preset_name: str) -> None:
        """A queue row chose a different format (`UX-005` §6, `T-126`, `REQ-009`).

        **Through `retarget()`**, which is the manager's for `T036-R1`'s reason: a request written
        straight through the store announces nothing, and a row would go on showing the format it
        no longer has. `retarget` also refuses a job past `Job.RETARGETABLE` rather than raising —
        the row only offers the control while it is retargetable, but a worker can take the job
        between the click and the write, and that is an ordinary outcome rather than a fault.

        The refusal is reported in the status bar rather than a dialog: the download the user
        already has is fine, and a modal for "you were a moment too late" is how people learn to
        dismiss dialogs unread (`NFR-006`).
        """
        if self._manager is None or self._queue is None:
            return
        job = self._queue.model.job_for(job_id)
        if job is None:
            return
        try:
            preset = presets.by_name(preset_name)
        except KeyError:
            # A name this build does not have. `by_name` raises rather than substituting, because
            # quietly falling back to "best video" would download something nobody asked for.
            self._report_transiently(f"{preset_name} is not a format this version offers")
            return
        self._manager.retarget(
            job_id,
            presets.to_request(
                preset,
                url=job.request.url,
                output_directory=job.request.output_directory,
            ),
            then=self.refresh_queue,
            otherwise=self._report_transiently,
        )

    def _show_row_menu(self, job_id: str, verbs: object) -> QMenu | None:
        """The queue row's menu, holding whatever the view said to hold.

        **The contents arrive with the request** (`T-135`). This used to call `verbs_of` itself and
        so gave both routes the same menu — which meant the `⋯` on a wide row offered the three
        actions the row was already showing. The view is the only thing that knows which route
        asked and how much the row could draw; deciding here would be deciding without that.

        Returned rather than only shown, and `popup` rather than `exec`, for the reason
        `FileActions._show_menu` gives: `exec` starts a nested event loop a test cannot leave.
        """
        if self._queue is None:
            return None
        return self._row_menu(self._queue, job_id, _verbs(verbs))

    def _row_menu(self, view: QueueView, row_id: str, offered: Sequence[Verb]) -> QMenu | None:
        """One overflow menu, for whichever list asked (`T124-R1`).

        Both tabs draw the same row anatomy (`UX-005` §3), so they get the same overflow rather
        than two that drift. `trigger_verb` is the shared entry point each view already exposes,
        and it is what makes the menu take *the route a click takes* instead of reimplementing it.
        """
        if not offered:
            return None
        menu = QMenu(view)
        menu.setObjectName("rowVerbsMenu")
        for verb in offered:
            action = menu.addAction(LABELS[verb])
            action.setObjectName(f"rowVerb_{verb.value}")
            action.triggered.connect(partial(view.trigger_verb, row_id, verb))
        menu.popup(QCursor.pos())
        return menu

    def _attach_file_actions(self) -> None:
        """Open and Show-in-folder on the queue's table (`T-086`, `REQ-021`).

        **On the table rather than on the toolbar.** A toolbar Open would act on a selection, and
        `UX-005` §4 chose row verbs over a toolbar acting on one. `FileActions` explains the rest.

        *(`REQ-021` named "the history and queue views" and both were on screen at once, which was
        the original reason a single toolbar Open could not work. Since 2026-08-06 it names the
        queue row alone, and the reasoning above is the one that survives.)*

        Attached only when composition supplied an `output_directory`: containment is what makes
        this safe (`SEC-001`), and a window that does not know where downloads go cannot check it —
        so it offers no way to open anything rather than an unchecked one.
        """
        if self._output_directory is None or self._queue is None:
            return
        view = self._queue
        self._file_actions.append(
            FileActions(
                table=view.table,
                selected_path=view.selected_path,
                # Read at the moment of use, not captured: `T-079` lets the download folder
                # change while the window is open, and the boundary checked must be the current
                # one. `_output_directory` is not `None` here — the guard above returned.
                output_directory=lambda: cast("Path", self._output_directory),
                report=self._report_transiently,
                # **The row's `⋯` owns the context menu on these two lists** (`T124-R1`,
                # `UX-005` §4). A table has one `customContextMenuRequested`, and the row menu
                # already carries *Open* and *Show in folder* — through these very actions, for
                # the rows that have a file — plus everything else the row's state permits.
                # Leaving both connected popped two menus on one right-click or Menu key.
                context_menu=False,
                parent=self,
            )
        )

    def report_transiently(self, message: str) -> None:
        """Say something in the status bar. Public, so composition can report too (`T-125`).

        Composition performs the writes `ui/` is not allowed to, so it is also where their
        failures surface — and a failure a user cannot see is the same as one that did not happen.
        """
        self._report_transiently(message)

    def _report_transiently(self, message: str) -> None:
        """Say something in the status bar, without a dialog (`NFR-006`).

        A file that has been moved is the *ordinary* case — `UX-001` promises nothing here deletes
        the user's files, so they are free to move them — and a modal dialog for an ordinary case
        trains people to dismiss dialogs unread.
        """
        self.statusBar().showMessage(message, MESSAGE_TIMEOUT_MS)

    @property
    def file_actions(self) -> list[FileActions]:
        """The open/reveal actions, one set per table. Empty without an output directory."""
        return list(self._file_actions)

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
        # **The primary action comes first** (`UX-005`'s 2026-08-04 amendment, `T-130`). The B1-b
        # mockup opens the toolbar with it and the shipped window had it only under File — so the
        # one thing this application exists to do was the one thing not on its toolbar. The action
        # object is the menu's, not a copy: `T-016`'s enabled state and its status tip are the
        # reasons it is disabled when composition supplied no manager, and two actions would be two
        # places for that to be got right.
        self._add_urls_button = self._add_action
        if self._add_urls_button is not None:
            # **The mockup's label, without putting a `+` in the File menu** (`T130-R2`).
            # `QToolButton` renders `iconText()` in preference to `text()`, so one `QAction` can
            # read *"+ Add URLs"* on the toolbar and *"Add URLs..."* in the menu — which is what
            # the amendment adopted and what the menu convention wants, and it keeps the single
            # action the enabled state depends on. The style is stated rather than inherited,
            # because a default that changed would silently take the label with it.
            self._add_urls_button.setIconText(ADD_URLS_BUTTON)
            bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            bar.addAction(self._add_urls_button)
            # **The role the style sheet fills against** (`T-132`). The mockup draws this one as a
            # filled brand button and the other three as plain ones, so the rule has to reach this
            # button alone — `QToolBar QToolButton` would fill `Pause queue` and `Clear finished`
            # too and put the toolbar back to four equals. `widgetForAction` is the only handle on
            # the button a toolbar builds for an action. The object name is kept for tests and
            # accessibility tooling to find it by; the *styling* hangs off the property.
            rendered = bar.widgetForAction(self._add_urls_button)
            if rendered is not None:
                rendered.setObjectName("addUrlsButton")
                rendered.setProperty(PRIMARY_ACTION_PROPERTY, True)
                # **Setting the property here is enough; do not add a repolish** (`T132-R2`).
                # One was added on 2026-08-04 to fix `T132-R1`, which reported the shipped button
                # rendering neutral. That finding was **withdrawn as reviewer error**: it measured
                # a window built without a job sink or output directory, so `T-016` had disabled
                # the action and `UX-005` row 6 correctly paints a disabled primary `sunken`. A
                # composed window with the action enabled fills it with the brand either way, and
                # the regression below stays green with the repolish gone — which is why it went.
            bar.addSeparator()
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
        # **The steps are labelled buttons, not native arrows** (`T-141`, `UX-005` row 11). The
        # arrows were reported missing twice: first drawn as solid blocks by the CSS
        # border-triangle trick, then drawn correctly as ~10px native wedges in a 23px control and
        # still unreadable. The two step labels are **text**, and no style sheet can silently
        # un-draw text — which is the shared cause of `T-129`, `T-133` and `T-139`.
        box.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        box.valueChanged.connect(self._concurrency_chosen)

        fewer = self._step_button(bar, STEP_DOWN_LABEL, "Fewer concurrent downloads", box.stepDown)
        bar.addWidget(fewer)
        bar.addWidget(box)
        more = self._step_button(bar, STEP_UP_LABEL, "More concurrent downloads", box.stepUp)
        bar.addWidget(more)

        def _limit_the_steps(value: int) -> None:
            """Neither button offers a step the range will not take (`UX-005` §5)."""
            fewer.setEnabled(value > settings.CONCURRENCY_MINIMUM)
            more.setEnabled(value < settings.CONCURRENCY_MAXIMUM)

        box.valueChanged.connect(_limit_the_steps)
        _limit_the_steps(box.value())

        # **The mockup's `.spacer{{flex:1 1 auto}}`** (`T-132`, `UX-005` row 7). What *adds* work
        # and what *acts on work already queued* are different kinds of verb; packed left, the
        # toolbar ran `Clear finished` straight up against the concurrency spinner with nothing
        # between them. A separator here would only draw a line — the ruling is that the queue
        # verbs sit at the far edge, which needs a widget that takes the leftover width.
        spacer = QWidget(bar)
        spacer.setObjectName("toolBarSpacer")
        spacer.setProperty(TOOLBAR_SPACER_PROPERTY, True)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        # It is furniture, so it must not be a stop on the way to the queue verbs (`NFR-005`).
        spacer.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        bar.addWidget(spacer)
        self._build_queue_actions(bar)

        self.addToolBar(bar)
        self._concurrency = box

    def _step_button(
        self, bar: QToolBar, label: str, announced: str, step: Callable[[], None]
    ) -> QToolButton:
        """One of the concurrency control's step buttons (`T-141`).

        **Its accessible name says the direction *and* the setting** (`NFR-005`). "Plus" read on
        its own says nothing about what it increases, and the visible label is a single character
        that a screen reader may or may not pronounce usefully.
        """
        button = QToolButton(bar)
        button.setObjectName(
            f"concurrency{label and 'Step'}{'Up' if label == STEP_UP_LABEL else 'Down'}"
        )
        button.setText(label)
        button.setAccessibleName(announced)
        button.setStatusTip(announced)
        button.setProperty(STEP_BUTTON_PROPERTY, True)
        button.setAutoRepeat(True)
        # **Focus stays on the value, not on the steppers.** A user tabbing to the concurrency
        # control wants the number, and `NFR-005` asks the keyboard to reach what the pointer
        # reaches — Up and Down already do, from the spin box itself, so three tab stops for one
        # setting would be the keyboard reaching it three times rather than once.
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(step)
        return button

    def _build_queue_actions(self, bar: QToolBar) -> None:
        """The verbs that act on a **whole list**, each naming the list it acts on (`UX-001`).

        **Everything per-row went to the row** (`UX-005` §4, `T124-R3`). This built *Remove*,
        *Move up* and *Move down* as well, each acting on `QueueView`'s selection and each enabled
        from `job_selected`. `UX-005` chose the row verbs *"rather than a toolbar acting on a
        selection"*, and the reason is visible in what the code did: with the window on the History
        tab those three actions were still live, still aimed at whatever the hidden queue happened
        to have selected, and a user pressing *Remove* while looking at their history removed a
        download from the queue. The row's own *Remove*, *↑* and *↓* reach the same
        implementations — `_remove_job` and `_move_job` — and cannot be ambiguous about their
        target, because the target is the row they are drawn on.

        *(`P2PLAN-R1`'s distinction is preserved. This said "what is on this toolbar acts on the
        queue", and `T-144` made that false by putting `Clear history` here — so it is rewritten to
        the principle underneath it rather than left standing as a comment that used to be true.
        **Nothing on this toolbar acts on a selection, and every verb on it names the list it
        empties.** That is what made the original rule right: the tab a verb belonged to was never
        what made it unambiguous, and `Clear finished` was never ambiguous while the History tab was
        in front either.)*

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

        # *(`REQ-016`'s reordering is still two named actions rather than a drag gesture, for
        # `T-081`'s reason — they are keyboard-reachable and drag is not, which `NFR-005` makes the
        # requirement rather than the nicety. They live on the row now, as *↑* and *↓*, and the
        # keyboard reaches them through the row's `⋯` (`T124-R1`). What changed is where they are,
        # not whether a keyboard can get to them.)*

        clear = QAction("&Clear finished", self)
        clear.setObjectName("clearCompletedAction")
        clear.setStatusTip("Remove finished downloads from the queue; your files are kept")
        # The files half is the sentence that stops this looking destructive. `UX-001` promises
        # nothing here deletes a download, and a user reading a verb called *Clear*
        # unable to find what they had downloaded.
        clear.setToolTip(
            "Remove completed and cancelled downloads from the queue. Files stay on disk; failed "
            "downloads stay so you can retry them."
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

    def _remove_job(self, job_id: str) -> None:
        """Remove one named job. **The single implementation**, so every route to a removal — the
        row's *Remove* and its `⋯` menu — cannot drift apart."""
        if self._on_remove_requested is not None:
            self._on_remove_requested(job_id)

    def _remove_group(self, playlist_id: str, job_ids: object) -> QMessageBox | None:
        """Remove a whole playlist, after a confirmation that names its count (`DAT-005` §4).

        **The count is why this is not `_remove_job` in a loop.** A bare *Remove* on a row covering
        sixteen files does not say how much is about to go, and a user who clicked the header
        meaning to click an entry has nothing to notice it by. One question, one count, then every
        member through the single removal implementation so the two routes cannot drift.

        Returned rather than only shown, and `open()` rather than `exec()`, so a test can drive it
        without a nested event loop.
        """
        # Qt carries the list as `object`; narrowing here is where the contract is checked
        # rather than assumed, exactly as `_on_verb` narrows its own `Verb`.
        if not isinstance(job_ids, list):
            return None
        ids = [job_id for job_id in job_ids if isinstance(job_id, str)]
        if not ids or self._on_remove_requested is None:
            return None
        confirm = QMessageBox(self)
        confirm.setObjectName("groupRemovalConfirm")
        confirm.setIcon(QMessageBox.Icon.Question)
        confirm.setWindowTitle("Remove from queue")
        confirm.setText(group_removal_question(len(ids)))
        confirm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        # The safe button is the default, for `_confirm_history_removal`'s reason.
        confirm.setDefaultButton(QMessageBox.StandardButton.No)

        def act(button: object) -> None:
            if confirm.standardButton(button) == QMessageBox.StandardButton.Yes:  # type: ignore[arg-type]
                for job_id in ids:
                    self._remove_job(job_id)

        confirm.buttonClicked.connect(act)
        confirm.open()
        return confirm

    def _move_job(self, job_id: str, offset: int) -> None:
        """Move one named job `offset` places, and hand the whole new order over (`T-081`).

        **The whole order, not "move this one".** `JobRepository.reorder` redeals the positions the
        named jobs hold, and the caller that knows what the *user* sees is this one — the table's
        order is what they are rearranging. Sending a delta would make the repository infer the
        arrangement from a position it did not choose.

        **Only reorderable rows are named**, and the neighbour is found among those rather than at
        `index ± 1` in the table. A running job sits in the table between two pending ones, and
        swapping across it must move the pending pair past each other rather than asking the
        repository to move the running one — which it refuses, by design.

        `_is_movable` is asked here rather than assumed from the fact that the row drew the verb:
        the row's answer came from the model a moment ago, and the reorder is what actually has to
        hold.
        """
        if self._on_reorder_requested is None or self._queue is None:
            return
        movable = [
            candidate for candidate in self._queue.model.job_ids() if self._is_movable(candidate)
        ]
        if job_id not in movable:
            return
        index = movable.index(job_id)
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

    @property
    def add_urls_action(self) -> QAction | None:
        """The toolbar's *Add URLs…*, if this window was given a control bar (`T-130`).

        **The same `QAction` the File menu holds**, not a second one. `T-016` disables it, and says
        why in a status tip, when composition supplied no manager — and two actions would be two
        places for that to stay true.
        """
        return self._add_urls_button

    @property
    def pause_action(self) -> QAction | None:
        """The queue's pause toggle, if this window was given a control bar."""
        return self._pause

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
        #: Held so the toolbar can show the *same* action rather than a second one (`T-130`).
        self._add_action = add_action
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

    def offer_to_retry_interrupted(self, job_ids: Sequence[str]) -> QMessageBox | None:
        """Offer to restart downloads an unclean exit left in flight (`T-082`, `REQ-012`).

        **An offer, not an action.** `recover_interrupted` has already moved these rows to a
        retryable failure before anything could read the queue, so nothing is running and nothing
        will start on its own. `REQ-018` reserves automatic restarts for `NETWORK` failures, and an
        application that resumed a queue of downloads because the machine crashed would be spending
        somebody's bandwidth on a decision they never made.

        **"Not now" is the default button.** Enter at startup must not start N downloads — the
        refusable half of the criterion is only real if refusing is the easier thing to do.

        **The plural is the point** (`T-082`'s scope). One interrupted job was Phase 1's case and
        the per-job Retry button already covers it; a queue of twelve is this one, and asking the
        user to open each of them in turn is not an offer.

        Returns `None` when there is nothing to offer, so a clean start shows no dialog at all —
        and `open()` rather than `exec()` for `report_settings_problem`'s reason.
        """
        ids = list(job_ids)
        if not ids:
            return None

        box = QMessageBox(self)
        box.setObjectName("interruptedJobsDialog")
        box.setWindowTitle(APP_NAME)
        box.setIcon(QMessageBox.Icon.Question)
        count = len(ids)
        box.setText(
            f"{count} download{'s were' if count != 1 else ' was'} interrupted when "
            f"{APP_NAME} last closed."
        )
        box.setInformativeText(
            "Nothing has been restarted. Anything already downloaded is still on disk, and these "
            "downloads are waiting in the queue either way — you can retry them individually at "
            "any time."
        )
        retry_all = box.addButton("&Retry all", QMessageBox.ButtonRole.AcceptRole)
        later = box.addButton("&Not now", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(later)
        box.setEscapeButton(later)
        retry_all.clicked.connect(lambda: self._retry_each(ids))
        box.open()
        return box

    def _retry_each(self, job_ids: Sequence[str]) -> None:
        """Retry every recovered job, **through the same route the user's own button uses**.

        Not a new bulk path in the manager: one route means the two cannot come to disagree about
        what a retry is, and `T-080`'s `requeue_at_end` already gives each one a fresh tail
        position so a recovered job does not jump ahead of one that has never run.

        *(This is N writes for N jobs, which `T-082`'s third criterion forbids for **recovery**
        specifically — recovery happens before the window exists and the user cannot decline it.
        This is a retry the user asked for, on the same path as any other. Recorded here because
        the distinction is worth a reviewer disagreeing with rather than worth hiding.)*
        """
        if self._retry is None:
            return
        for job_id in job_ids:
            self._retry(job_id)

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
