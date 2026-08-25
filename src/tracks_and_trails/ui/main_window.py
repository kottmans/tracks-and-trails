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
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QToolBar,
    QWidget,
)

from tracks_and_trails import __version__
from tracks_and_trails.core import presets, settings
from tracks_and_trails.core.job_state import REORDERABLE
from tracks_and_trails.core.models import MediaInfo, NetworkOptions, Preset
from tracks_and_trails.core.paths import APP_SLUG
from tracks_and_trails.core.settings import SettingsProblem
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.downloader.ytdlp_service import YtdlpService
from tracks_and_trails.ui.add_dialog import AddUrlDialog, JobSink
from tracks_and_trails.ui.file_actions import MESSAGE_TIMEOUT_MS, FileActions
from tracks_and_trails.ui.job_detail import JobReader
from tracks_and_trails.ui.keyboard import route_is_elsewhere
from tracks_and_trails.ui.options_dialog import PresetSink
from tracks_and_trails.ui.queue_view import QueueReader, QueueView, build_queue_view
from tracks_and_trails.ui.row_verbs import LABELS, Verb
from tracks_and_trails.ui.settings_dialog import SettingsDialog

APP_NAME: Final = "Tracks & Trails"

#: platformdirs slug, matching the paths in `ARCHITECTURE.md` §5.

#: The tab names `UX-005` named. The count is appended at runtime, so these are the stems rather
#: than what is displayed — a test asserting on the visible text must expect "Queue (3)".
#:
#: *(This said "the two tabs". `UX-005` named two and `T-169`/`T-170` removed one, so there is a
#: single surface now — `T-186`.)*

#: What the toolbar's primary action reads (`UX-005`'s 2026-08-04 amendment, `T-130`).
#:
#: The B1-b mockup names it exactly this. It is the action's `iconText`, not its `text`: the File
#: menu keeps *"Add URLs..."*, where a leading `+` would be a convention nobody uses.
ADD_URLS_BUTTON: Final = "+ Add URLs"

#: The keyboard route to the two toolbar verbs that are on no menu (`NFR-005`, `T-200`).
#:
#: **Chosen because there was none.** `T-200`'s sweep measured the whole UI holding two shortcuts —
#: `Ctrl+N` and `Ctrl+Q` — and `QToolBar` giving every button `Qt.NoFocus`, so the run control had
#: no keyboard route of any kind while `UX-006` made the queue *stopped until started*. A user
#: without a pointer could not download anything.
#:
#: `Ctrl+R` for the run control reads as *run* and collides with nothing here; this application has
#: no reload. `Ctrl+Shift+C` is deliberately not plain `Ctrl+C`, which every text field on the
#: window already owns for copy.
#:
#: **The mnemonics were believed to be the route and are not.** `test_nothing_on_the_toolbar_can_
#: take_the_keyboard_from_the_rows` records *"each carries a mnemonic (`&Start`)"* as the reason a
#: tab stop was unnecessary. Measured 2026-08-15: every toolbar button's `shortcut()` is **empty**.
#: Qt strips the `&` for display and registers no accelerator, because a `QAction`'s mnemonic binds
#: in a *menu*; the ampersand was doing nothing but hiding the gap.
#:
#: **Neither of these is the discoverable route**, and that is stated rather than glossed: a
#: shortcut is found by someone who goes looking. **A tab stop on the buttons is not the answer** —
#: `T-234`'s criterion forbids a focusable widget on this toolbar, because `T203-R3` recorded one
#: stealing `Shift+F10` from the row menu on a freshly opened window. A **menu** route, which is
#: what Qt's convention assumes exists, is the discoverable option and changes the ruled menu bar;
#: `T-200` records it as the maintainer's to take.
RUN_SHORTCUT: Final = "Ctrl+R"
CLEAR_FINISHED_SHORTCUT: Final = "Ctrl+Shift+C"

#: What `Quit` falls back to when Qt's per-platform standard key resolves to nothing (`T-270`).
#:
#: **`QKeySequence.StandardKey.Quit` is a request, not a guarantee.** Qt answers it from the
#: platform theme, and the Windows theme has no entry for it: on `STARBASE` it resolves **empty**,
#: so `Quit` carried no accelerator there at all. Measured in run `32268124069`, where
#: `test_the_quit_shortcut_is_bound` failed on PySide6 6.11.2 after a fresh resolve floated it off
#: the `>=6.11,<7` floor. That test's own docstring had predicted it — *"Qt may resolve it to
#: nothing at all"* — and the product never guarded it.
#:
#: **`Ctrl+Q` is what the platform that does answer already says.** Measured across four plugins on
#: PySide6 6.11.1: `xcb` and `wayland` both resolve `Quit` to `Ctrl+Q`, so on the two platforms this
#: project supports the fallback either agrees with the theme or replaces nothing. The headless
#: `minimal` and `offscreen` themes answer `Qt.Key_Exit` — a bare hardware key, non-empty and
#: unusable — which is why the offscreen suite could never have caught the Windows gap.
#:
#: **Kept as a fallback rather than a replacement.** Binding `Ctrl+Q` unconditionally would discard
#: a theme's opinion wherever it has one, which is a wider change than the defect; this guards only
#: the hole the defect came through.
QUIT_SHORTCUT_FALLBACK: Final = "Ctrl+Q"


def resolve_quit_shortcut(standard: QKeySequence | None = None) -> QKeySequence:
    """Return the platform's `Quit` sequence, or `QUIT_SHORTCUT_FALLBACK` if it has none.

    `standard` exists so a test can hand in the **empty** sequence Windows produces and drive the
    fallback on any platform. Left `None`, it asks Qt, which needs a `QGuiApplication` to answer.
    """
    if standard is None:
        standard = QKeySequence(QKeySequence.StandardKey.Quit)
    return QKeySequence(QUIT_SHORTCUT_FALLBACK) if standard.isEmpty() else standard


#: The dynamic property the style sheet fills a toolbar's primary button against (`T-132`).
#:
#: **A role, not a name.** `theme.py` must style by class so a widget nobody remembered still gets
#: themed — `test_the_sheet_styles_by_class_so_a_new_widget_inherits_it` — and an object-name
#: selector would have made a second primary action somewhere else silently draw flat. Named here
#: rather than written into both the widget and the sheet, because a selector that stops matching
#: fails silently: the button just goes back to looking like the other three.

#: The dynamic property that marks a status-bar statement the user is expected to **act on**
#: (`T-192`). A role, not a name, for the reason `PRIMARY_ACTION_PROPERTY` gives.
#:
#: **True only while the queue is stopped**, which is the one status-bar line that asks for a press.
#: The running state and the environment summary are reports, and a bar where everything is
#: emphasised emphasises nothing.
#:
#: **`NFR-005` is satisfied before this property exists, not by it**: the label already says
#: *"Queue stopped — press Start to download"* in words, and the weight and colour are a second
#: channel on top. Nothing here is the only carrier of the state.
ACTIONABLE_STATUS_PROPERTY: Final = "actionableStatus"

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

#: The tool's name for **display**, written with a non-breaking hyphen — `U+2011`, not `U+002D`.
#:
#: **This is a deliberate character substitution and it has a cost.** `QMessageBox` sizes itself
#: from its content, and at the About box's natural width Qt's line breaker treats the ordinary
#: hyphen as a break opportunity: the name renders as "yt-" / "dlp" across two lines, which reads
#: as a typo. Measured at 9, 12, 18, 19 and 22 pt — **the default 9 pt breaks too**, so this was
#: never only a large-text problem.
#:
#: **What was tried and rejected** (`T278-R1`):
#:
#: - `<nobr>` — ignored by Qt's width calculation here; rendered identically.
#: - `QLabel#qt_msgbox_informativelabel { min-width: … }` — worked at 9-15 pt and **broke again at
#:   18 and 19**, because a pixel floor does not scale with the font. It also depended on a child
#:   name created inside `QMessageBoxPrivate`, and setting any stylesheet makes
#:   `canBeNativeDialog()` refuse the native message box.
#: - `QMessageBox.setMinimumWidth()` from font metrics — **ignored**; the box measured identical
#:   widths to no fix at every size.
#:
#: **The cost, stated rather than buried:** `U+2011` is a different codepoint from the hyphen in
#: the project's name, so text copied out of this dialog will not match a literal search for
#: `yt-dlp`. It is a hyphen to a screen reader and is metrically identical — same advance width,
#: present in every font checked — so nothing about the rendering or the announcement changes.
#: **Anywhere the string is data rather than display, use the ordinary hyphen.**
YTDLP_DISPLAY_NAME: Final = "yt\u2011dlp"

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


#: A stand-in item for validating a template with no row in hand (`T195-R2`).
#:
#: The settings screen's template applies to downloads that do not exist yet, so there is nothing
#: real to render against — and a refusal must not depend on which row happens to be selected.
#: Every supported field is filled, so a template naming any of them renders rather than failing
#: for want of a value.
_TEMPLATE_PROBE: Final = MediaInfo(
    url="https://example.invalid/preview",
    title="A download",
    uploader="An uploader",
    duration_seconds=1,
    is_playlist=False,
)


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
        control_bar: bool = False,
        on_concurrency_changed: Callable[[int], None] | None = None,
        on_run_changed: Callable[[bool], None] | None = None,
        on_remove_requested: Callable[[str], None] | None = None,
        on_reorder_requested: Callable[[list[str]], None] | None = None,
        on_clear_requested: Callable[[], None] | None = None,
        queue: QueueReader | None = None,
        save_preset: PresetSink | None = None,
        manage_presets: Callable[[], object] | None = None,
        presets: Callable[[], Sequence[Preset]] | None = None,
        default_preset: Callable[[], str] | None = None,
        cache_root: Path | None = None,
        theme: str | None = None,
        directory_is_default: bool = True,
        on_directory_chosen: Callable[[Path | None], None] | None = None,
        on_theme_chosen: Callable[[str], None] | None = None,
        cookie_file: Path | None = None,
        cookie_browser: str | None = None,
        default_cookie_browser: Callable[[], str | None] | None = None,
        on_cookie_file_chosen: Callable[[Path | None], None] | None = None,
        on_cookie_browser_chosen: Callable[[str | None], None] | None = None,
        #: `T-196`: the network options in force, the writer behind them, and — read through a
        #: callable, for `default_cookie_browser`'s reason — the ones a *new* request inherits.
        #: A snapshot could not reach the next add dialog after a change in Settings.
        network: NetworkOptions | None = None,
        default_network: Callable[[], NetworkOptions] | None = None,
        on_network_chosen: Callable[[NetworkOptions], None] | None = None,
        ffmpeg_location: Path | None = None,
        ffmpeg_summary: str = "",
        on_ffmpeg_location_chosen: Callable[[Path | None], None] | None = None,
        preset_names: Callable[[], Sequence[str]] | None = None,
        #: **The stored template, not the resolved one**, and the difference is the point
        #: (`T-195`): the screen shows empty when the user has chosen nothing, with the shipped
        #: template as the placeholder, so *empty* reads as a choice. The add dialog needs the
        #: opposite — see `default_output_template`.
        output_template: Callable[[], str] | None = None,
        default_output_template: Callable[[], str] | None = None,
        shipped_template: str = "",
        on_default_preset_chosen: Callable[[str], None] | None = None,
        on_output_template_chosen: Callable[[str], None] | None = None,
        #: yt-dlp's version and the two actions `REQ-025` asks for (`T-198`). Injected because
        #: it spawns children and reaches the network, neither of which a window owns.
        ytdlp: YtdlpService | None = None,
    ) -> None:
        super().__init__()
        self._geometry_file = geometry_file
        #: `T-146`'s screen, and what composition has to supply for it to do anything: the theme
        #: in force, whether the download folder is a choice or the platform's, and the two
        #: writers. `ui/` owns no settings file (`ARC-007`), so every one of these is handed in.
        self._theme = theme
        self._directory_is_default = directory_is_default
        self._on_directory_chosen = on_directory_chosen
        self._on_theme_chosen = on_theme_chosen
        self._settings_action: QAction | None = None
        self._settings_dialog: SettingsDialog | None = None
        #: `T-199`: where ffmpeg was told to be, what resolving it said, and the writer. Held so
        #: the Settings screen opens on the truth rather than on the stored string.
        #: `T-197`: the cookies file in force, and the writer. `ui/` holds no settings writer.
        self._cookie_file = cookie_file
        self._cookie_browser = cookie_browser
        #: `T197-R4`: the browser a new request inherits when its preset names none. Read through
        #: a callable so a change in Settings reaches the *next* add dialog.
        self._default_cookie_browser = default_cookie_browser
        self._on_cookie_file_chosen = on_cookie_file_chosen
        self._on_cookie_browser_chosen = on_cookie_browser_chosen
        #: `T-196`: the network options the Settings screen opens on, the writer behind it, and
        #: the source a new request reads. Held on the window rather than only on the screen for
        #: `show_download_directory`'s reason — these bind into the job when it is queued
        #: (`ARCHITECTURE.md` §8), so the add dialog is what has to see a change.
        self._network = network if network is not None else NetworkOptions()
        self._default_network = default_network
        self._on_network_chosen = on_network_chosen
        self._ffmpeg_location = ffmpeg_location
        self._ffmpeg_summary = ffmpeg_summary
        self._on_ffmpeg_location_chosen = on_ffmpeg_location_chosen
        #: Asked afresh each time the screen opens, for `presets`' reason in the add dialog: a
        #: preset created or made default in the manager has to be the one this screen shows next
        #: (`T-195`).
        self._preset_names = preset_names
        self._output_template = output_template
        self._default_output_template = default_output_template
        self._shipped_template = shipped_template
        self._on_default_preset_chosen = on_default_preset_chosen
        self._on_output_template_chosen = on_output_template_chosen
        self._ytdlp = ytdlp
        if ytdlp is not None:
            # Connected once, on the window rather than on the screen: the screen is rebuilt every
            # time Settings is opened, and a service that outlives it must not be holding
            # connections to a dialog Qt has destroyed (`T118-R13`'s shape). The window forwards
            # to whichever screen is open, or to none.
            ytdlp.reported.connect(self._on_ytdlp_reported)
            ytdlp.failed.connect(self._on_ytdlp_failed)
            ytdlp.busy_changed.connect(self._on_ytdlp_busy)
        #: The cache root both thumbnail stores write under (`T-180`). Composition derives it from
        #: the database so two permitted instances stop sweeping each other's pictures; this window
        #: only carries it to the two widgets that fetch, and never learns what a database is.
        #: `None` is the pre-`T-180` shared location, which is what a test that names no root means.
        self._cache_root = cache_root
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
        #: Where `P-4`'s *Save as preset…* writes (`T109-R5`). Composition owns `settings.toml`
        #: (`ARC-007`), so it supplies this rather than the window reading the file.
        self._save_preset = save_preset
        #: How `docs/UX_SPEC.md` §8's *Manage presets…* opens (`T-111`). Passed straight through to
        #: the add dialog, which draws the entry only where there is one — this window does not
        #: learn what a preset store is, for `save_preset`'s reason.
        self._manage_presets = manage_presets
        #: The catalogue the add dialog offers (`REQ-007`).
        #:
        #: **A callable, not a sequence**, for `queued_urls`' reason: a preset created or renamed in
        #: the manager must be in the list the *next* dialog offers, and a snapshot taken when this
        #: window was built could not be. `None` falls back to the dialog's own built-ins, which is
        #: the honest answer for a caller that never said what the catalogue is.
        self._presets = presets
        #: What a new paste inherits (`REQ-007`, `P-7`). A callable for `presets`' reason: the
        #: default changes in the manager, and the *next* dialog has to open on the new one.
        self._default_preset = default_preset
        self.setObjectName("mainWindow")
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self._on_concurrency_changed = on_concurrency_changed
        self._on_run_changed = on_run_changed
        self._on_remove_requested = on_remove_requested
        self._on_reorder_requested = on_reorder_requested
        self._on_clear_requested = on_clear_requested
        self._build_menus()
        #: The limit in force, carried for the Settings screen this window opens (`T-234`).
        #:
        #: **A number, not a control.** `UX-013` took the spinner off the toolbar, so the window
        #: shows the limit nowhere — but it still *opens* the screen that sets it, and that screen
        #: has to open on the value in force. `show_concurrency` keeps this in step with
        #: composition.
        self._concurrency_limit: int = (
            concurrency if concurrency is not None else settings.CONCURRENCY_DEFAULT
        )
        #: `T-080`'s queue actions. Built with the control bar, so a window given
        #: `control_bar=False` has no toolbar and therefore neither of them — the same
        #: all-or-nothing rule the add-URL action follows, and the reason `T-007`'s bare-window
        #: tests keep working.
        #:
        #: **The gate is its own parameter since `T-234`.** It was `concurrency is not None`, so
        #: one argument meant both *the initial limit* and *build the whole toolbar* — and when
        #: `UX-013` took the limit away the switch would have gone with it. A switch that says
        #: what it switches cannot be removed by accident.
        #:
        #: **Two, since `T124-R3`.** *Remove*, *Move up* and *Move down* were here too, acting on
        #: the queue's selection, and `UX-005` chose row verbs *"rather than a toolbar acting on a
        #: selection"* — because with two tabs that toolbar has to guess which list it means, and
        #: it guessed wrong: they stayed enabled and aimed at the hidden queue's selection while
        #: History was in front. The row route was added without the rejected one being removed.
        #: What is left is queue-*wide* and unambiguous whichever tab is showing.
        self._run: QAction | None = None
        self._clear: QAction | None = None
        #: The toolbar's copy of File → Add URLs…, or `None` on a window with no control bar.
        self._add_urls_button: QAction | None = None
        if control_bar:
            self._build_control_bar()
        #: Whether the queue is running, said in words and permanently (`UX-006`, `T-181`).
        #:
        #: **A stopped queue that holds work must say so somewhere the user is looking**, and the
        #: toolbar's control alone is not that: a checkable action's unchecked state is a visual
        #: cue, `NFR-005` forbids that being the only one, and a window where nothing happens and
        #: nothing explains why is the one state a user can reasonably read as broken.
        #:
        #: **This and the row's `Held` answer different questions** (`T181-R1`, `T181-R2`). This
        #: one is about the window — *why is nothing happening* — and `QueueModel._chip`'s `Held`
        #: is about a row: *what is this one waiting for*. Both read the manager's gate; neither
        #: stores a copy, so `UX-001`'s rule that the gate is a property of the queue and never of
        #: a job is intact.
        #:
        #: *(This said the state was shown "at queue level rather than on the rows", that writing
        #: `Held` on a row would put a queue-level fact in as many places as there are jobs, and
        #: that the row was not built. All three were the rationale for departing from `UX-006`
        #: item 3, which `T181-R1` found could not stand. The row was built; this comment outlived
        #: the argument by one correction round, which is why `T181-R2` exists.)*
        self._gate = QLabel(self)
        self._gate.setObjectName("queueGateState")
        self._gate.setAccessibleName("Queue state")
        self._gate.setTextFormat(Qt.TextFormat.PlainText)
        #: **On the left, and not a permanent widget** (`T-192`). `addPermanentWidget` packs to the
        #: *right* end, which put this hard against the environment summary — the two ran together
        #: as one sentence (*"…press Start to download  ffmpeg found; all post-processing…"*) and
        #: the one that asks the user to act read as the tail of the one that does not.
        #:
        #: `addWidget` puts it at the left, where the eye starts, and leaves the summary alone on
        #: the right. The gap between them is then the width of the bar rather than a space.
        self.statusBar().addWidget(self._gate)
        #: Whether this installation can merge (`REQ-024`). **Pessimistic until told**: the add
        #: dialog offers the merge mode from this, and claiming a capability nobody has confirmed
        #: is what `REQ-024` exists to prevent. `app.py` reports it during composition.
        self._ffmpeg_available = False
        self._environment = QLabel(self)
        self._environment.setObjectName("environmentSummary")
        self._environment.setAccessibleName("Environment")
        self._environment.setTextFormat(Qt.TextFormat.PlainText)
        self.statusBar().addPermanentWidget(self._environment)
        self._show_gate_state(running=False)
        self._build_body(queue)
        self._restore_geometry()

    def _build_body(self, queue: QueueReader | None) -> None:
        """The Queue, as the whole of the window (`UX-005`, amended 2026-08-06 by `T-169`).

        **One surface, and no tab widget.** This was `Queue` and `History` as tabs, each with a
        count — the design `UX-005` chose over a splitter, and the counts were what answered the
        objection that a tab hides a list. `T-169` removed History as a product, so the second tab
        had no contents rather than fewer of them.

        *(This said `REQ-020` "is now a private ledger with nothing to browse", which was true for
        part of one day. `T-169` narrowed the requirement to a private ledger and `T-170` withdrew
        that too, hours later, after review found it had cost five findings without a user ever
        seeing it; migration `0009` removed the table from upgraded databases. **The application
        keeps no record of what has been downloaded at all** — `T-186`.)*

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
        self._queue = build_queue_view(queue, self._manager, None, cache_root=self._cache_root)
        self._connect_row_verbs(self._queue)
        self.setCentralWidget(self._queue)
        self._attach_file_actions()

        # **The declared keyboard route needs the key, not only a row** (`T-152`, second round,
        # `NFR-005`). The first fix gave the view a current index, which is what
        # `_row_menu_asked_for` falls back to — and `Shift+F10` still did nothing, because Qt
        # delivers it to the *focused* widget and nothing here ever focused a view. Measured on a
        # freshly opened window, focus sat on `QSpinBox concurrencyChoice`, the toolbar's stepper.
        #
        # **Re-measured after `UX-013` removed that spinner** (`T-234`): a freshly opened window
        # now focuses *nothing at all* — the toolbar's remaining widgets are tool buttons, which
        # take no focus. That makes the placement below more necessary, not less: there is no
        # longer even a wrong widget holding the key.
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
            # **The new format, the old connection** (`T197-R4`). A preset describes a format; a
            # request rebuilt from one alone drops the browser the job was bound to when it was
            # queued, which `DAT-003` makes a binding rather than a preference.
            presets.with_connection_of(
                presets.to_request(
                    preset,
                    url=job.request.url,
                    output_directory=job.request.output_directory,
                    # **The new format, the old *naming*** — the same argument as the connection
                    # below, one field over (`T-195`). Retargeting changes what is downloaded, not
                    # what the file is called, and a shipped preset states no template, so without
                    # this the row would silently fall back to the template this application ships:
                    # discarding both the user's Settings default and any naming they set on the
                    # row itself.
                    default_output_template=job.request.output_template,
                ),
                job.request,
            ),
            then=self.refresh_queue,
            otherwise=self._report_transiently,
        )

    def _refuse_template(self, template: str) -> str | None:
        """Why this template cannot be used, asked of the same route the row editor asks.

        **`preview_output_path`, not a subcheck of it** (`T195-R2`). It runs yt-dlp's own syntax
        parser, the supported-field check, a real render and the containment rule — and the row
        editor already refuses through it, so the two surfaces cannot come to disagree about what a
        usable template is.

        A window with no manager answers `None`: it cannot ask, and claiming a refusal it did not
        compute would be worse than deferring to the field-name check the screen falls back to.
        """
        if self._manager is None:
            return None
        request = presets.to_request(
            presets.BUILT_IN_PRESETS[0],
            url="https://example.invalid/preview",
            output_directory=str(self._output_directory),
            default_output_template=template,
        )
        return self._manager.preview_output_path(request, _TEMPLATE_PROBE).refusal

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

        One overflow rather than one per list, because `UX-005` §3's row anatomy is one shape.
        `trigger_verb` is the shared entry point each view already exposes, and it is what makes
        the menu take *the route a click takes* instead of reimplementing it.

        *(This began "Both tabs draw the same row anatomy … so they get the same overflow rather
        than two that drift". There is one tab since `T-169`/`T-170`; the argument survives it,
        because what it prevents is a **second** caller drifting from this one — `T-186`.)*
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
                # **The row's `⋯` owns the context menu on this list** (`T124-R1`,
                # `UX-005` §4). *(Said "these two lists" while History was the second — `T-186`.)*
                # A table has one `customContextMenuRequested`, and the row menu
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

    def report_environment(self, summary: str, *, ffmpeg_available: bool) -> None:
        """State what this installation can and cannot do, on screen (`REQ-024`).

        In the status bar rather than a dialog: a missing ffmpeg disables features, it does not
        stop the application, and a modal on every start for a condition the user may have chosen
        is how people learn to dismiss dialogs without reading them. It is a permanent widget
        rather than a timed message, because the fact does not stop being true after five seconds.

        **The flag is required rather than defaulted** (`T-108`). The add dialog needs it to decide
        whether to offer the merge mode at all (`P-13`), and a default of `True` would mean a caller
        that forgot silently promised a capability the installation may not have — offering a merge
        that fails is exactly what `REQ-024` exists to prevent. Passed beside the summary because
        they are one fact: the sentence *says* whether ffmpeg was found.
        """
        self._ffmpeg_available = ffmpeg_available
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
            default_cookie_browser=self._default_cookie_browser,
            # `T-196`: the network options a request inherits, read when the request is built
            # rather than when this dialog opened — the settings screen can be used while it is up.
            default_network=self._default_network,
            # `P-13`: the merge mode is drawn only where a merge could actually run (`REQ-024`).
            ffmpeg_available=self._ffmpeg_available,
            # `REQ-022`, `T-114`: what the queue holds now, read from the rows the table already
            # has in memory rather than from the database (`T079-R2`). Bound as a callable rather
            # than a snapshot, because the dialog outlives any one answer — a job finishing while
            # it is open must stop being reported as a duplicate.
            queued_urls=self._queued_urls,
            # `P-4`, `T109-R5`: the options editor draws *Save as preset…* only where there is
            # somewhere to save. Composition supplies it; a window built without one says so in
            # the button's place rather than offering a control that cannot act.
            save_preset=self._save_preset,
            # `T-111`: the same division one surface further on — composition owns the store, and
            # the entry is drawn only where something is behind it.
            manage_presets=self._manage_presets,
            # Read at the moment the dialog is built, so a preset created in the manager during the
            # last one is offered by this one. Omitted where composition supplied nothing, which
            # leaves the dialog's own `BUILT_IN_PRESETS` default in place.
            presets=self._presets() if self._presets is not None else presets.BUILT_IN_PRESETS,
            default_preset=self._default_preset() if self._default_preset is not None else "",
            default_output_template=(
                self._default_output_template()
                if self._default_output_template is not None
                else presets.DEFAULT_OUTPUT_TEMPLATE
            ),
            # `T-180`: the same root the queue's store uses. `cache_generation` is keyed by
            # directory precisely so a picture this dialog publishes is one the queue's sweep can
            # still see (`T118-R16`), and two roots would put that count back out of reach.
            cache_root=self._cache_root,
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

    def _queued_urls(self) -> tuple[str, ...]:
        """Every URL the queue is showing, or nothing before a queue view exists (`T-114`).

        Empty rather than an error for a window that has not been given one: this is asked by a
        dialog that reports *no duplicates found*, which is the honest answer when there is nothing
        to compare against.
        """
        return () if self._queue is None else self._queue.model.queued_urls()

    def _build_control_bar(self) -> None:
        """The window's toolbar: three verbs and the gap between two kinds of verb.

        **`+ Add URLs`, the run control, `Clear finished`** — `docs/UX_SPEC.md` §2.1 as amended by
        `UX-013`, in the order `T-220` ruled (option A, 2026-08-12).

        **This used to be `_build_concurrency_control`**, which built the bar as a side effect of
        building a spin box (`T-234`). `ARC-007` had put a concurrency control in the window
        *"until Phase 4's settings dialog replaces it"*; `T-146` built that dialog, and `UX-013`
        completed the sentence — the limit is set in `Settings → Settings…` and nowhere else. The
        bar outlived the control it was built for, so it is named for what it is.
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
            self._declare_toolbar_route(
                bar, self._add_urls_button, "File \u2192 Add URLs..., and Ctrl+N"
            )
            # **Setting the property here is enough; do not add a repolish** (`T132-R2`).
            # One was added on 2026-08-04 to fix `T132-R1`, which reported the shipped button
            # rendering neutral. That finding was **withdrawn as reviewer error**: it measured
            # a window built without a job sink or output directory, so `T-016` had disabled
            # the action and `UX-005` row 6 correctly paints a disabled primary `sunken`. A
            # composed window with the action enabled fills it with the brand either way, and
            # the regression below stays green with the repolish gone — which is why it went.
        # **No separator after the primary action** (`T-234`). One divided `+ Add URLs` from the
        # concurrency control; with the spacer immediately after it, a line and a gap would divide
        # the same two groups twice. The spacer does the dividing.
        #
        # Not closable: a control the user can hide and then not find is worse than a control they
        # ignore. *(This also said "and this is the only way to change the limit until Phase 4's
        # dialog" — the limit left with `UX-013`, so the first half carries it alone now.)*
        bar.toggleViewAction().setVisible(False)

        # **The mockup's `.spacer{{flex:1 1 auto}}`** (`T-132`, `UX-005` row 7). What *adds* work
        # and what *acts on work already queued* are different kinds of verb, and the queue verbs
        # sit at the far edge — which needs a widget that takes the leftover width, not a separator
        # that only draws a line. *(Row 7's own example was `Clear finished` running up against the
        # concurrency spinner. That spinner is gone (`UX-013`) and `T-220` kept the ruling anyway,
        # deliberately: the principle is about kinds of verb, not about the spinner.)*
        spacer = QWidget(bar)
        spacer.setObjectName("toolBarSpacer")
        spacer.setProperty(TOOLBAR_SPACER_PROPERTY, True)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        # It is furniture, so it must not be a stop on the way to the queue verbs (`NFR-005`).
        spacer.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        bar.addWidget(spacer)
        self._build_queue_actions(bar)

        self.addToolBar(bar)

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

        **The run control is one checkable action, not two buttons** (`UX-006`, `T-181`). Start and
        Stop are the two states of one thing; a pair of buttons would spend the whole session with
        one of them disabled, and a screen reader would read the disabled one too.

        **It opens unchecked, because the queue opens stopped.** The label follows the state rather
        than naming a fixed verb: a control reading *Stop* on a window where nothing has ever run
        describes the wrong half of itself.
        """
        run = QAction(self)
        run.setObjectName("runQueueAction")
        run.setCheckable(True)
        run.setShortcut(RUN_SHORTCUT)
        run.toggled.connect(self._run_toggled)
        bar.addAction(run)
        self._run = run
        self._show_in_file_menu(run)
        self._declare_toolbar_route(bar, run, f"the File menu and the {RUN_SHORTCUT} shortcut")
        # Sets text, status tip, tooltip and accessible description together, so the four cannot
        # describe different states of the same control (`NFR-005`).
        self._describe_run_action(running=False)

        # *(`REQ-016`'s reordering is still two named actions rather than a drag gesture, for
        # `T-081`'s reason — they are keyboard-reachable and drag is not, which `NFR-005` makes the
        # requirement rather than the nicety. They live on the row now, as *↑* and *↓*, and the
        # keyboard reaches them through the row's `⋯` (`T124-R1`). What changed is where they are,
        # not whether a keyboard can get to them.)*

        clear = QAction("&Clear finished", self)
        clear.setObjectName("clearCompletedAction")
        clear.setShortcut(CLEAR_FINISHED_SHORTCUT)
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
        self._show_in_file_menu(clear)
        self._declare_toolbar_route(
            bar, clear, f"the File menu and the {CLEAR_FINISHED_SHORTCUT} shortcut"
        )

    def _show_in_file_menu(self, action: QAction) -> None:
        """Put a toolbar verb on the `File` menu as **the same action**, not a copy (`T-246`).

        **A shortcut is a route; a menu item is a place to land.** `T-200` gave both verbs
        `Ctrl+R` and `Ctrl+Shift+C`, which makes them operable without a pointer — and leaves a
        screen-reader user with nothing to hear. `T-234` forbids a focusable widget on this
        toolbar (`T203-R3`: one stole `Shift+F10` from the row menu on a freshly opened window),
        so the drawn buttons take no focus and never will. The menu item is the announcement the
        shortcut cannot make, and Qt draws the shortcut beside it, which is the discoverability an
        undocumented key combination lacks.

        **The same `QAction`, following `T-130`.** The toolbar has shown the File menu's own
        `Add URLs...` action since that task rather than a second one that would drift; these two
        are the exception it left, and this removes it. One object means one enabled state, one
        status tip and one label — the run control's text changes as the queue starts and stops,
        and the menu item changes with it because there is nothing else to change.
        """
        self._file_menu.insertAction(self._before_quit, action)

    @staticmethod
    def _declare_toolbar_route(bar: QToolBar, action: QAction, route: str) -> None:
        """Say where a toolbar verb's keyboard route is, since its button takes no focus.

        **`T-234`'s criterion is why the button is unfocusable** — nothing on this bar may take
        focus, because `T203-R3` recorded a focusable one stealing `Shift+F10` from the row menu on
        a freshly opened window. **`T200-R2` is why it has to say so**: an unfocusable control drops
        out of every sweep that inspects focusable controls, so *deliberately unfocusable* and
        *lost its tab stop* looked identical until the exemption carried its reason.

        The route named here is checked against reality by the accessibility sweep, which requires
        a shortcut or a menu item; the declaration records *which*, for a reader.
        """
        rendered = bar.widgetForAction(action)
        if rendered is not None:
            route_is_elsewhere(rendered, route)

    def _describe_run_action(self, *, running: bool) -> None:
        """Make the run control's four pieces of text say the same state (`UX-006`, `NFR-005`).

        **The label names what pressing it does**, which is the opposite of the current state:
        stopped reads *Start*. The accessible description names the state itself, because a
        screen-reader user who hears only the verb cannot tell whether the queue is running — the
        checked state is a visual cue and `NFR-005` forbids leaving it as the only one.

        **`Start`/`Stop`, not `Start queue`/`Stop queue`** (`T-220`, ruled 2026-08-12). The longer
        form followed the toolbar's habit of naming the list a verb acts on, which is what
        `Clear finished` does — but the status bar already carries the noun, and with the
        concurrency control gone (`UX-013`) the bar is three verbs on a window that *is* a queue.
        The noun earned its width beside a setting; it does not beside two other verbs.

        `QAction` has no accessible-name property in Qt 6 — the name comes from the text, and the
        toolbar button takes its accessible *description* from the tooltip — so the state sentence
        goes in the tooltip, where `T-132` already put this control's explanation.
        """
        if self._run is None:
            return
        self._run.setText("&Stop" if running else "&Start")
        if running:
            self._run.setStatusTip("The queue is running. Stop starting new downloads.")
            self._run.setToolTip(
                "The queue is running. Pressing this stops starting new downloads; downloads "
                "already running finish, nothing is cancelled, and no partly downloaded file is "
                "left behind."
            )
        else:
            self._run.setStatusTip("The queue is stopped. Start downloading what is queued.")
            self._run.setToolTip(
                "The queue is stopped, so nothing downloads until you press Start. Queued items "
                "wait; adding more never starts them on its own."
            )

    def _show_gate_state(self, *, running: bool) -> None:
        """Say whether the queue is running, in words, in the status bar (`UX-006`, `NFR-005`).

        The stopped wording names the remedy rather than only the state: *press Start* is the one
        thing a user looking at a full queue and no activity needs to be told, and a label that
        said only "Queue stopped" would describe the problem without answering it.
        """
        self._gate.setText(
            "Queue running" if running else "Queue stopped — press Start to download"
        )
        # **Emphasised only while stopped** (`T-192`). The stopped line is the one that asks for a
        # press; the running one reports. Re-polished by hand because Qt does not restyle on a
        # property change on its own — a dynamic-property selector that is set and never repolished
        # is a rule that applies once, at construction, and then silently stops.
        self._gate.setProperty(ACTIONABLE_STATUS_PROPERTY, not running)
        style = self._gate.style()
        if style is not None:
            style.unpolish(self._gate)
            style.polish(self._gate)

    def _run_toggled(self, running: bool) -> None:
        """Hand the queue's run state to whoever composition said owns it.

        Injected exactly as `retry` and the concurrency handler are, so the control can be driven
        in a test with no pool behind it (`ARCHITECTURE.md` §3).

        The label is updated here as well as from `show_queue_running`, because a press that
        composition declines — during shutdown, which `stop_queue()` refuses — must not leave a
        control describing a state the queue is not in. `show_queue_running` then corrects it from
        the manager's own signal, which is the authority.
        """
        self._describe_run_action(running=running)
        self._show_gate_state(running=running)
        if self._on_run_changed is not None:
            self._on_run_changed(running)

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
        # **The safe button is the default**, so a dialog dismissed with Enter or Space removes
        # nothing. *(This deferred the reason to `_confirm_history_removal`, which went with the
        # History surface — leaving a comment whose justification could not be read from the code
        # at all. The reason is stated here instead of pointed at: `T-186`.)*
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
    def run_action(self) -> QAction | None:
        """The queue's Start/Stop toggle, if this window was given a control bar."""
        return self._run

    @property
    def clear_completed_action(self) -> QAction | None:
        """The clear-finished action, if this window was given a control bar."""
        return self._clear

    def show_queue_running(self, running: bool) -> None:
        """Reflect the queue's run state **without re-emitting it** (`T-080`, `UX-006`).

        Composition connects this to `DownloadManager.queue_running`, so the control follows the
        queue whatever changed it. Signals are blocked for the assignment because `setChecked`
        emits `toggled`, and a round trip — control tells manager, manager tells control, control
        tells manager — is how a toggle ends up fighting itself.

        **The label is set outside the blocked region on purpose.** Blocking suppresses `toggled`,
        which is what `_run_toggled` would otherwise use to re-describe the control, so a state
        arriving from the manager rather than from a click would leave the text behind.
        """
        if self._run is None:
            return
        blocked = self._run.blockSignals(True)
        try:
            self._run.setChecked(running)
        finally:
            self._run.blockSignals(blocked)
        self._describe_run_action(running=running)
        self._show_gate_state(running=running)

    def _concurrency_chosen(self, value: int) -> None:
        """Hand the new limit to whoever composition said owns it.

        This window knows neither the manager nor `settings.toml` for this purpose — the handler is
        injected exactly as `retry` is, so the widget can be driven in a test without a pool or a
        file behind it (`ARCHITECTURE.md` §3).
        """
        if self._on_concurrency_changed is not None:
            self._on_concurrency_changed(value)

    def _build_menus(self) -> None:
        """File → Add URLs…, File → Quit, Settings → Settings…, and Help → About.

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
        #: Where `Start` and `Clear finished` are inserted, and why they are not appended
        #: (`T-246`).
        #:
        #: **The two queue verbs are built by the control bar, not here.** `_build_queue_actions`
        #: owns them because it owns the text that describes them — the run control's label,
        #: status tip, tooltip and accessible description are one decision made in one place
        #: (`_describe_run_action`) — and a window built with `control_bar=False` has neither
        #: action at all. Appending from there would put both **below `Quit`**, since this menu is
        #: built first; inserting before this separator keeps the verbs together and leaves `Quit`
        #: last, where a user's hand expects it.
        self._file_menu = file_menu
        self._before_quit = file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(resolve_quit_shortcut())
        # Without NoRole, Qt may treat this as an OS-level quit item and relocate or hide it.
        # This window is the whole application; keep the item where the user put their cursor.
        quit_action.setMenuRole(QAction.MenuRole.NoRole)
        quit_action.setStatusTip(f"Exit {APP_NAME}")
        quit_action.setObjectName("actionQuit")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # **`Settings` is its own menu, between File and Help** (`REQ-023`, `T-146`). It was here
        # for six hours on 2026-08-06 holding `T-170`'s one records control, and left with
        # `REQ-020`; this is the screen `T-146` always owned. The Windows accessibility equality
        # in `tests/ui/test_windows_accessibility.py` is written against this menu bar by hand and
        # is the gate that caught the last one, on the Windows job alone.
        settings_menu = menu_bar.addMenu("&Settings")
        settings_action = QAction("&Settings...", self)
        settings_action.setMenuRole(QAction.MenuRole.NoRole)
        settings_action.setObjectName("actionSettings")
        settings_action.setStatusTip("Where downloads go, the theme, and how many run at once")
        settings_action.setEnabled(self._can_open_settings)
        settings_action.triggered.connect(self.open_settings)
        settings_menu.addAction(settings_action)
        #: Held so a test drives the route a user takes rather than the method behind it.
        self._settings_action = settings_action

        help_menu = menu_bar.addMenu("&Help")
        # **"&About", not "&About {APP_NAME}"** — and the short form also fixes a defect. Qt reads
        # `&` in an action's text as a mnemonic marker, so the ampersand *inside* `APP_NAME`
        # was being consumed: the item rendered as "About Tracks _Trails", underlining the T of
        # Trails rather than showing the "&". Escaping it as `&&` would have been the other fix;
        # the maintainer asked for the short label, which removes the ampersand altogether.
        about_action = QAction("&About", self)
        about_action.setMenuRole(QAction.MenuRole.NoRole)
        about_action.setStatusTip(f"Version and licence information for {APP_NAME}")
        about_action.setObjectName("actionAbout")
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    @property
    def _can_open_settings(self) -> bool:
        """Whether composition supplied enough for the screen to change anything.

        Every setting it edits is written by composition (`ARC-007`), so a window built without
        those callbacks — which is most windows in `tests/ui/` — gets the menu item disabled
        rather than a screen whose controls do nothing. The same rule `Add URLs...` follows.
        """
        return (
            self._on_directory_chosen is not None
            and self._on_theme_chosen is not None
            and self._output_directory is not None
            and self._theme is not None
        )

    @property
    def settings_action(self) -> QAction | None:
        """The `Settings` menu item, so a test can drive the route a user takes."""
        return self._settings_action

    def open_settings(self) -> SettingsDialog | None:
        """Open the Settings screen (`REQ-023`, `T-146`).

        Returned so a test drives the same route the user takes, exactly as `open_add_dialog` is
        asserted. `None` when composition supplied no writers — the action is disabled then, and
        this is the second half of that rather than a trust in the first.

        **Held while it is open**, so a setting composition applies while the screen is up reaches
        the screen's own controls. A screen showing a stale number is a screen that will write it
        back. *(This held for concurrency because two controls edited one value; since `UX-013`
        this screen is the only one, and the holding still matters for the settings — the download
        folder, the cookie source — that composition resolves after the screen has opened.)*
        """
        if (
            self._on_directory_chosen is None
            or self._on_theme_chosen is None
            or self._output_directory is None
            or self._theme is None
        ):
            return None
        dialog = SettingsDialog(
            download_directory=self._output_directory,
            directory_is_default=self._directory_is_default,
            theme=self._theme,
            # The limit in force, carried rather than read off a control: since `UX-013` the
            # window has no spinner to read (`T-234`).
            concurrency=self._concurrency_limit,
            on_directory_chosen=self._on_directory_chosen,
            on_theme_chosen=self._theme_chosen,
            cookie_file=self._cookie_file,
            cookie_browser=self._cookie_browser,
            on_cookie_file_chosen=self._on_cookie_file_chosen,
            on_cookie_browser_chosen=self._on_cookie_browser_chosen,
            network=self._network,
            # **`None` when composition wired no writer**, so the screen disables the controls
            # rather than accepting typing it cannot store — the rule the template field follows
            # one section up. Routed through this window when there *is* one, so the value it
            # holds for the next add dialog follows the change (`T-196`).
            on_network_chosen=None if self._on_network_chosen is None else self._network_chosen,
            ffmpeg_location=self._ffmpeg_location,
            ffmpeg_summary=self._ffmpeg_summary,
            on_ffmpeg_location_chosen=self._on_ffmpeg_location_chosen,
            on_concurrency_chosen=self._concurrency_chosen,
            # **Read when the screen opens, not cached at startup** (`T-195`). *Set as default* in
            # the preset manager writes the same key this screen does, so a snapshot taken earlier
            # would let the two disagree — which is `P3EXIT-R1`'s defect, and the one this task's
            # criteria name.
            preset_names=tuple(self._preset_names()) if self._preset_names else (),
            default_preset=self._default_preset() if self._default_preset is not None else "",
            output_template=self._output_template() if self._output_template else "",
            shipped_template=self._shipped_template,
            on_default_preset_chosen=self._on_default_preset_chosen,
            on_output_template_chosen=self._on_output_template_chosen,
            refuse_template=self._refuse_template,
            on_ytdlp_update=None if self._ytdlp is None else self._ytdlp.install_latest_version,
            on_ytdlp_revert=None if self._ytdlp is None else self._ytdlp.revert,
            parent=self,
        )
        self._settings_dialog = dialog
        dialog.finished.connect(self._forget_settings_dialog)
        dialog.open()
        if self._ytdlp is not None:
            # **Asked every time the screen opens, never cached.** A version read at startup is a
            # version that stops being true the moment an update lands — and this screen is where
            # the user does that. The answer arrives on a signal, so the screen shows
            # `YTDLP_VERSION_UNKNOWN` until it does rather than a number nobody read (`REQ-025`).
            self._ytdlp.refresh()
        return dialog

    def _forget_settings_dialog(self) -> None:
        self._settings_dialog = None

    def _on_ytdlp_reported(self, resolution: object) -> None:
        """Pass a worker's answer to the open screen, if one is open."""
        dialog = self._settings_dialog
        if dialog is None:
            return
        dialog.show_ytdlp(
            getattr(resolution, "version", ""),
            getattr(resolution, "source", ""),
            is_user_managed=bool(getattr(resolution, "is_user_managed", False)),
            rejected=tuple(getattr(resolution, "rejected", ())),
        )

    def _on_ytdlp_failed(self, reason: str) -> None:
        dialog = self._settings_dialog
        if dialog is not None:
            dialog.show_ytdlp_problem(reason)

    def _on_ytdlp_busy(self, busy: bool) -> None:
        # Positional `bool` because this is connected to `busy_changed(bool)`.
        dialog = self._settings_dialog
        if dialog is not None:
            dialog.show_ytdlp_busy(busy)

    def _network_chosen(self, options: NetworkOptions) -> None:
        """Remember what the screen picked, so the next paste inherits it (`T-196`).

        **The window holds it, not just the screen**, for `show_download_directory`'s reason: this
        is what a new request is built with, so a change that only reached the settings screen
        would be a setting that appeared to work and moved nothing until a restart — `T-075`'s
        shape. Composition still owns the file and can bound the value; `show_network_options`
        brings its answer back.
        """
        self._network = options
        if self._on_network_chosen is not None:
            self._on_network_chosen(options)

    def show_network_options(self, options: NetworkOptions) -> None:
        """The network options in force, from composition (`T-196`)."""
        self._network = options
        if self._settings_dialog is not None:
            self._settings_dialog.show_network_options(options)

    def _theme_chosen(self, name: str) -> None:
        """Remember what the screen picked, so reopening it shows the theme in force."""
        self._theme = name
        if self._on_theme_chosen is not None:
            self._on_theme_chosen(name)

    def show_download_directory(self, directory: Path, *, is_default: bool) -> None:
        """Take the folder composition resolved, and tell the open screen about it (`T-146`).

        **The window holds it, not just the screen**, because this is the folder the add dialog
        builds its requests against: a change that only reached the settings screen would be a
        setting that appeared to work and moved nothing until a restart, which is the shape
        `T-075` was.
        """
        self._output_directory = directory
        self._directory_is_default = is_default
        if self._settings_dialog is not None:
            self._settings_dialog.show_download_directory(directory, is_default=is_default)

    def show_cookie_source(self, file: Path | None, browser: str | None) -> None:
        """The cookie source in force, both halves (`REQ-026`, `T197-R4`)."""
        self._cookie_file = file
        self._cookie_browser = browser
        if self._settings_dialog is not None:
            self._settings_dialog.show_cookie_source(file, browser)

    def show_ffmpeg_location(self, location: Path | None, *, report: object) -> None:
        """Take the resolution composition performed, and tell the open screen (`T-199`).

        The *report* rather than the stored path, because what a user needs to see after choosing
        a file is whether it turned out to be a usable ffmpeg — which only `find_ffmpeg` knows,
        and which `ui/` may not compute (`downloader/` is not this layer's to call).
        """
        self._ffmpeg_location = location
        summary = getattr(report, "summary", None)
        self._ffmpeg_summary = summary() if callable(summary) else str(report)
        if self._settings_dialog is not None:
            self._settings_dialog.show_ffmpeg_location(location, self._ffmpeg_summary)
            # **The catalogue too** (`T195-R5`). A new ffmpeg makes presets performable that were
            # not, and the combo was built when the screen opened. Asked again rather than
            # recomputed here: composition owns which presets this installation can do.
            if self._preset_names is not None:
                self._settings_dialog.show_preset_names(
                    self._preset_names(),
                    self._default_preset() if self._default_preset is not None else "",
                )

    def show_concurrency(self, limit: int) -> None:
        """Follow a limit changed elsewhere (`T-146`).

        **One control shows it now, not two** (`UX-013`, `T-234`). The window keeps the number so
        the Settings screen opens on the value in force, and forwards it to that screen when one is
        open. *(This blocked signals around a toolbar spinner as well, because two controls
        reporting `valueChanged` would turn one user change into a round trip between them. With
        the spinner gone there is one control and no round trip to prevent — the screen's own
        `show_concurrency` still blocks its own.)*
        """
        self._concurrency_limit = limit
        if self._settings_dialog is not None:
            self._settings_dialog.show_concurrency(limit)

    def show_about(self) -> QMessageBox:
        """Build the About box and show it.

        Constructed explicitly rather than via `QMessageBox.about`, which does not reliably
        carry an icon — and `T-007` requires the app icon to appear here. Returned so a test
        can assert on it without driving a modal dialog.
        """
        about = QMessageBox(self)
        about.setObjectName("aboutDialog")
        # **"About", not "About Tracks & Trails".** The dialog says the name twice already — in
        # its own body text and in the icon beside it — and the title bar is the one place with
        # no room for it. **The Help menu item is "About" too** (`T278-R2`: this comment used to
        # say it kept the long form, which was already false in the commit that wrote it).
        about.setWindowTitle("About")
        # 112, arrived at by looking: 64 was too small, 128 too big a jump. The `.ico`'s 128 px
        # frame is the source, so this is a small downscale of a real frame rather than an upscale
        # of the 64 (`T-277` moved which cut those frames hold, not which frames exist).
        about.setIconPixmap(app_icon().pixmap(112, 112))
        about.setText(f"<b>{APP_NAME}</b><br>Version {__version__}")
        about.setInformativeText(
            f"A desktop front-end for {YTDLP_DISPLAY_NAME}, for Linux and Windows.<br>MIT licensed."
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
