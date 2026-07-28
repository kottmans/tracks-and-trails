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
from PySide6.QtWidgets import QLabel, QMainWindow, QMessageBox, QWidget

from tracks_and_trails import __version__
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.ui.add_dialog import AddUrlDialog, JobSink
from tracks_and_trails.ui.job_detail import JobProgressView, JobReader, build_progress_view

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
    ) -> None:
        super().__init__()
        self._geometry_file = geometry_file
        self._job_reader = job_reader
        self._retry = retry
        self._view: JobProgressView | None = None
        #: Supplied together or not at all: the add-URL dialog needs all three, and a window
        #: holding two of them could only offer an action that fails. `T-036` passes them.
        self._manager = manager
        self._jobs = jobs
        self._output_directory = output_directory
        self.setObjectName("mainWindow")
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self._build_menus()
        self._environment = QLabel(self)
        self._environment.setObjectName("environmentSummary")
        self._environment.setAccessibleName("Environment")
        self._environment.setTextFormat(Qt.TextFormat.PlainText)
        self.statusBar().addPermanentWidget(self._environment)
        self._restore_geometry()

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
        self.setCentralWidget(self._view)
        return self._view

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
        dialog.open()
        return dialog

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
