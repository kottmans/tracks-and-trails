"""Application setup and wiring — **the one place the object graph is built** (`T-036`).

Every other module in this application depends on the *shape* of what it is given: the manager
takes a `JobStore`, the dialog takes a `JobSink`, the progress view takes a `JobReader`, and none
of them knows SQLite exists (`ARCHITECTURE.md` §3). Something has to know, once, and this is it.

`A-004` adds the single-instance guard in Phase 2.

## Why this task exists at all

`T-036` was filed after review, because nothing owned it: every Phase 1 component could pass its
own tests while the application still opened an empty window. It remains the one task that can
fail while everything else is green, which is why `compose()` is a function returning the graph
rather than a sequence of statements inside `run()` — a graph nothing can hold is a graph nothing
can assert on.

## Shutdown is a lifecycle, and it has an order

Closing the window is a **request**. What follows it has to happen in sequence, and each step is
asynchronous because none of them may block the GUI thread (`T013-R2`, `ARC-005`):

1. `DownloadManager.shutdown()` — cancels the running job, escalates on its own timer, reaps the
   worker's process tree, and stops the result pump on its sentinel. It reports `idle` when the
   last session is released *and* the worker-log listener has drained (`T038-R2`).
2. `QueueWriter.close()` — only then, because the manager's final transitions are still being
   written when it goes idle. It reports `closed` when its thread has finished them.
3. The read connection is closed and the process quits.

Quitting anywhere earlier is what leaves an orphaned `ffmpeg`, a dropped log record, or a
half-written row. `setQuitOnLastWindowClosed(False)` is what makes the order possible at all:
Qt's default is to quit the moment the window disappears, which is step zero of the wrong
sequence.

Qt is imported inside the functions below, not at module scope. `__main__.py` must stay importable
without pulling in Qt so `multiprocessing.freeze_support()` runs first in a frozen build
(`REL-001`, `ARCHITECTURE.md` §3), and `tests/unit/test_skeleton.py` asserts exactly that. A
module-level Qt import here would break that guarantee from a file that never mentions freezing.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tracks_and_trails import __version__
from tracks_and_trails.core.models import Preset
from tracks_and_trails.core.settings import Settings as AppSettings

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

    from tracks_and_trails.core.instance_lock import InstanceLock
    from tracks_and_trails.core.job_state import JobStatus
    from tracks_and_trails.downloader.environment import FfmpegReport
    from tracks_and_trails.downloader.manager import DownloadManager
    from tracks_and_trails.persistence.repositories import JobRepository
    from tracks_and_trails.persistence.store import PersistentJobStore
    from tracks_and_trails.persistence.writer import QueueWriter
    from tracks_and_trails.ui.main_window import MainWindow

USAGE = """\
Tracks & Trails {version} — a desktop GUI for yt-dlp.

usage: tracks-and-trails [--version] [--help] [--spawn-probe] [--ytdlp-probe]

  --version      print the version and exit
  --help, -h     print this message and exit
  --spawn-probe  self-test the process model and exit (T-020)
  --ytdlp-probe  self-test the bundled yt-dlp and exit (T-033)

Run with no arguments to open the application window.
"""


def run(argv: Sequence[str]) -> int:
    """Start the application and return the process exit code."""
    args = list(argv[1:])

    # Handled before constructing a QApplication: `--version` must work on a machine with no
    # display, and without paying Qt's startup cost.
    if "--version" in args:
        print(__version__)
        return 0
    if "--help" in args or "-h" in args:
        print(USAGE.format(version=__version__), end="")
        return 0
    # Before Qt, and before anything else that would make this need a display. The frozen
    # build runs exactly this path in CI to prove that spawning a child does not relaunch the
    # application (REL-001, ARCHITECTURE.md §3, T-020).
    if "--spawn-probe" in args:
        from tracks_and_trails._freeze_probe import run_probe

        return run_probe()
    # Before Qt for the same reason as above: a frozen artifact missing its extractors must be
    # diagnosable without a display (T-033).
    if "--ytdlp-probe" in args:
        from tracks_and_trails._freeze_probe import run_ytdlp_probe

        return run_ytdlp_probe()
    # Before Qt for the same reason: a frozen artifact that cannot create its database must
    # be diagnosable without a display (T-014, T014-R3).
    if "--database-probe" in args:
        from tracks_and_trails._freeze_probe import run_database_probe

        return run_database_probe()
    if args:
        print(USAGE.format(version=__version__), end="")
        return 2

    # Before Qt, and before anything that might log: a diagnostic emitted while the application
    # was still starting is exactly the one worth having, and until this runs there is no
    # redacting handler under it (`T-038`, `REQ-026`). Nothing above this point logs, which is
    # why it sits here rather than at the top — `--version` on a machine with no writable cache
    # directory must still print a version.
    from tracks_and_trails.core.logging import configure_logging

    configure_logging()

    from PySide6.QtWidgets import QApplication

    from tracks_and_trails.ui.main_window import APP_NAME, app_icon

    app = QApplication(list(argv))
    # Set before any window exists: platform integration and some desktop environments read
    # these once, when the first window is created.
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_NAME)
    app.setWindowIcon(app_icon())

    # **The brand palette, applied once to the application** (`T-120`, `ARCHITECTURE.md` §8).
    #
    # Here rather than in `compose()` because it is a property of the *running* application, not
    # of the object graph: a test composing the graph against a temporary database has no business
    # restyling the `QApplication` it shares with every other test in the session.
    #
    # Applied to the application rather than per widget, so a widget added later inherits it
    # instead of becoming the only unstyled thing on the screen.
    from tracks_and_trails.ui import theme

    theme.apply(app)

    from tracks_and_trails.core.instance_lock import AlreadyRunningError

    try:
        composition = compose(app)
    except AlreadyRunningError as refusal:
        # **It says which thing it did** (`ARC-006`): silence is indistinguishable from a hang, and
        # a second launch that exits quietly looks like a broken shortcut. A message box because
        # this is a desktop application launched from an icon, where stderr goes nowhere anybody
        # will see; the same text goes to the log for the case where it was launched from a shell.
        from PySide6.QtWidgets import QMessageBox

        logging.getLogger("tracksandtrails.app").warning("refusing to start: %s", refusal)
        QMessageBox.information(None, APP_NAME, str(refusal))
        # Refusing in favour of the running instance is the outcome `A-004` asks for, not a crash.
        # Non-zero so a script can tell it apart from a normal run that the user closed.
        return 3

    # **The stored palette, once the settings file has been read** (`REQ-023`, `T-146`). The call
    # above dressed the application in the default so anything shown before this point — the
    # already-running refusal, most concretely — is styled; this is the user's own choice, applied
    # before the window is visible so there is no flash of the other theme.
    theme.apply(composition.app, theme.THEMES[composition.theme])

    composition.window.show()
    return app.exec()


def waiting_jobs(repository: JobRepository) -> list[tuple[str, JobStatus]]:
    """The jobs waiting to be downloaded and **only** those, with each status kept.

    A named function rather than a comprehension inside `compose()` so the filter can be asserted
    directly. Without one, "admit everything" is invisible in a test: the state machine refuses
    `FAILED → PROBING` and `COMPLETED → PROBING`, so a filter-less startup produces a burst of
    rejections and no observable change — the defect hides behind a guard meant for something else.

    **`T081-R4` is why that matters.** Relying on a downstream refusal to keep recovered jobs from
    restarting unattended is exactly the shape of rule that finding was about. The filter is the
    guarantee; the state machine is not a substitute for it.

    **`READY` is here because of `UX-003`, and leaving it out was `T-115` all over again.** This
    read `QUEUED` only, which was every waiting job while probing was a button nobody pressed.
    Now a job is probed *before* it is queued, so what a previous run leaves behind is `READY` —
    and a startup that admitted only `QUEUED` would have found nothing and drained nothing. The
    phase proof caught it: `test_a_queue_left_by_a_previous_run_starts_on_the_next_launch` found
    the queue it was handed was `READY` rows.

    Both are safe for the same reason, and it is not that they look similar: `ARC-004` starts a
    session from either, recovery has already moved everything that was *in flight* to `FAILED`,
    and neither status can be reached by a job that a worker was holding when the application
    died. `RUNNING` is absent for exactly that reason and stays absent.

    **The status travels with the id because startup has to admit the two differently**
    (`UX-003`, `ARC-009`), and `T137-R2` is what conflating them cost twice. The add dialog was
    corrected first: an entry built from a flat extraction is `QUEUED`, and admitting it as a
    download skipped the probe `UX-003` promises. This path had the same defect one seam over — the
    durable write and the callback that admits its probe are separate operations, so an application
    that exits between them leaves a flat entry `QUEUED` on disk, and the next start downloaded it
    unprobed.

    Kept as a pair rather than two queries so both come from one read of the table, and so a
    caller cannot ask for one and forget the other.

    **Selected in SQL rather than filtered in Python** (`T-177`); `with_statuses` keeps
    `all_jobs()`' order, which is the part this function depends on.

    Read **after** `recover_interrupted()`, so nothing that was in flight is in this list.

    *(This was two functions. `queued_job_ids` returned the ids alone and had one caller — a test —
    while production read the pair; `T-177` removed it and moved its reasoning here, which is where
    the filter it documented actually lives.)*
    """
    from tracks_and_trails.core.job_state import JobStatus

    waiting = (JobStatus.QUEUED, JobStatus.READY)
    return [(job.id, job.status) for job in repository.with_statuses(waiting)]


def default_output_directory() -> Path:
    """Where downloads go until `core/settings.py` lets the user say otherwise.

    The user's own downloads directory, not a subfolder of it: a downloader that invents a
    folder is one the user has to go looking in. `platformdirs` answers this per platform, and
    the test suite redirects it to `tmp_path`, so nothing here writes into a real home directory
    during a run (`ai/TESTING.md` §5).
    """
    from platformdirs import user_downloads_dir

    return Path(user_downloads_dir())


@dataclass
class _Held:
    """The settings currently in force, so two writers cannot erase each other (`T109-R5`).

    `save()` writes the whole file. The concurrency control and *Save as preset…* each change one
    part of it, and both close over composition's settings — so a closure holding the value read at
    startup would write it back without whatever the other had added since. One cell, replaced on
    every write, is the smallest thing that makes the two composable.
    """

    settings: AppSettings


@dataclass(frozen=True)
class Composition:
    """Everything the running application owns, constructed exactly once.

    Held as a value rather than left in local variables so `T-036`'s acceptance criteria can be
    asserted at all: *the manager holds the concrete repository*, *no component is constructed
    twice*, and *every manager signal the UI needs has exactly one connection* are claims about
    an object graph, and a graph nothing can reach is a graph nothing can check.
    """

    app: Any
    window: MainWindow
    manager: DownloadManager
    store: PersistentJobStore
    writer: QueueWriter
    connection: sqlite3.Connection
    ffmpeg: FfmpegReport
    output_directory: Path
    database_path: Path
    settings_path: Path
    #: The palette the settings file asked for (`REQ-023`, `T-146`). Carried rather than applied,
    #: because `compose()` restyling the `QApplication` would restyle the one every other test in
    #: the session shares — the rule the `theme.apply` note in `run()` states. `run()` applies it.
    theme: str
    #: The cache root this database's instance owns alone (`T-180`). Held for `database_path`'s
    #: reason — the partition is a claim about the assembled graph, and a root nothing can reach
    #: is a root nothing can check (`T180-R2`).
    cache_root: Path
    shutdown: OrderlyShutdown
    instance: InstanceLock


def compose(
    app: QApplication,
    *,
    database: Path | None = None,
    output_directory: Path | None = None,
    ffmpeg_override: Path | None = None,
    geometry_file: Path | None = None,
    settings_file: Path | None = None,
    cache_directory: Path | None = None,
    entry_point: Callable[..., None] | None = None,
) -> Composition:
    """Build the object graph and wire it up, then admit what the last run left queued.

    **Constructing is separate from starting, and the one thing it starts is deliberate.** Since
    `T-115` this admits the rows that were durably `QUEUED` when the application last exited —
    read *after* `recover_interrupted()`, so nothing that was in flight is resumed unattended
    (`T081-R4`). Nothing else here begins work: no download is started for a job the user has not
    already committed to the queue.

    The arguments exist so a test can drive the assembled application against a temporary
    database and a crafted worker (`T-037`), not as configuration — `run()` passes none of them.

    `entry_point` reaches `DownloadManager` unchanged and is not a mocking seam: the tests that
    use it spawn a real process over a real queue (`ai/TESTING.md` §6). It is here because the
    *assembled* application is exactly what `T-036` has to prove, and proving it against a real
    extractor would make the proof depend on a site staying up.
    """
    from tracks_and_trails.core import logging as app_logging
    from tracks_and_trails.core import models as core_models
    from tracks_and_trails.core import paths
    from tracks_and_trails.core import settings as app_settings
    from tracks_and_trails.core.instance_lock import InstanceLock
    from tracks_and_trails.downloader import worker
    from tracks_and_trails.downloader.environment import find_ffmpeg
    from tracks_and_trails.downloader.manager import DownloadManager
    from tracks_and_trails.persistence import db
    from tracks_and_trails.persistence.repositories import JobRepository
    from tracks_and_trails.persistence.store import PersistentJobStore
    from tracks_and_trails.persistence.writer import QueueWriter, open_connection_factory
    from tracks_and_trails.ui import theme as ui_theme
    from tracks_and_trails.ui.main_window import MainWindow

    database_path = database if database is not None else db.database_path()

    # **Ownership before anything opens the database** (`A-004`, `ARC-006`, `T-087`). An atomic
    # kernel lock, not `QLocalServer` — Qt documents two local servers listening on one Windows pipe
    # name simultaneously, so *connect-then-listen* admits the two-writer state the guard exists to
    # prevent. Raising `AlreadyRunningError` out of `compose()` is deliberate: there is nothing
    # useful this process can do against a database another process is writing, and `run()` turns it
    # into a message and a non-zero exit rather than a traceback.
    #
    # Taken *before* `db.connect`, because recovery runs on the very next line and would otherwise
    # rewrite rows belonging to a live instance's in-flight jobs.
    instance = InstanceLock(database_path)
    instance.acquire()

    # **The read connection is opened here and the writer opens its own inside its thread**
    # (`ARC-005`). `check_same_thread` stays on, so the two cannot quietly become one.
    connection = db.connect(database_path)
    # Recovery before anything can read the queue: a row left `RUNNING` by a killed application
    # is not in flight, whatever it says (`T-014`, `NFR-003`).
    # The ids are **kept**, not discarded (`T-082`): recovery is silent by design — it happens
    # before the window exists and the user cannot decline it — and the *offer* to restart them is
    # the thing `REQ-012` wants and the thing this list makes possible.
    recovered = JobRepository(connection).recover_interrupted()
    # **Read after recovery, so nothing recovered is in this list** (`T-115`, and `T081-R4`'s
    # lesson). Recovery moves in-flight rows to `FAILED`; what is left `QUEUED` is work the user
    # asked for and this application never started — a queue closed while it was still going, or
    # added to and then closed. Those are admitted below, once the manager exists.
    #
    # An enumeration on the GUI thread, which `ARC-005` allows only because this is startup: it
    # runs before the writer, the store or the window exist, and `recover_interrupted` has just
    # walked the same table for the same reason.
    durable_waiting = waiting_jobs(JobRepository(connection))
    durable_queued = [job_id for job_id, _ in durable_waiting]
    writer = QueueWriter(open_connection_factory(database_path))
    store = PersistentJobStore(connection, writer)

    # `ARC-007`: composition owns `settings.toml`; the manager receives a value. The read happens
    # here so a settings-format change cannot reach `downloader/`, which `T-097` enforces
    # statically.
    # `ARC-008`: the read answers with the settings *and* why they are not the file's, when the
    # file exists and could not be used. The problem is carried to the window rather than logged
    # here — `core/` cannot show a dialog and composition has no window yet.
    settings_read = app_settings.load(settings_file)
    # **Mutable, because two things now write this file.** The concurrency control and `P-4`'s
    # *Save as preset…* each change one part of `settings.toml`, and `save()` writes the whole
    # file — so a closure holding the settings as they were at startup would erase whatever the
    # other one had added. One current value, replaced on every write.
    # **Before anything is logged, and before the window exists** (`T197-R1`). `load()` reports an
    # unusable cookie path by naming it, and that reason is logged — so the literal most certain to
    # be written was the one nothing had registered. Registering from `secrets` covers the rejected
    # value as well as the accepted one, which is the half that leaked.
    for literal in settings_read.secrets:
        app_logging.remember_a_secret(literal)

    held = _Held(settings_read.settings)

    @dataclass
    class _InForce:
        """The ffmpeg resolution actually in effect, replaced only by an accepted choice.

        A cell rather than a closure variable, for `_Held`'s reason one class up: the refusal path
        must show what is **in force**, and a captured startup value would go stale the moment any
        choice was accepted.
        """

        report: Any

    settings = settings_read.settings

    # **The user's stored location outranks `PATH`, and the explicit argument outranks both**
    # (`REQ-023`, `REQ-024`, `T-199`). Same precedence as the download folder below: the
    # argument is the test seam, the setting is the user's answer, and `find_ffmpeg` falls back to
    # `PATH` when neither says otherwise. `load()` has already discarded a location that is gone or
    # is not a file, and said why — so what arrives here is either usable-looking or `None`, and
    # `find_ffmpeg` makes the final call on whether it can actually run.
    ffmpeg = find_ffmpeg(
        ffmpeg_override if ffmpeg_override is not None else settings.ffmpeg_location
    )
    #: What ffmpeg resolved to, replaced whenever an accepted choice changes it. Held in a cell
    #: for `_Held`'s reason: the refusal path has to show the resolution still **in force**, and a
    #: closure capturing the startup value would show a stale one after any accepted change.
    ffmpeg_problem: str | None = None
    if ffmpeg_override is None and settings.ffmpeg_location is not None and not ffmpeg.available:
        # Stored, passed `load()`'s checks, and the platform still will not run it — a mode bit on
        # POSIX, a missing `PATHEXT` match on Windows. This session falls back to `PATH`, the same
        # ending `resolve_ffmpeg` gives a live choice.
        #
        # **Reported, not only logged** (`T199-R3`). `ARC-008` says an existing setting that cannot
        # be used *reports* rather than reverting silently, and a log line is not a report — the
        # user never sees it. `load()` cannot raise this itself: whether a file can be executed is
        # the platform's answer through `find_ffmpeg`, and `core/` may not ask. So composition,
        # which can, contributes the problem here and it reaches the same dialog every other
        # settings problem does.
        #
        # The file is **not** rewritten: an unplugged drive should not cost the user the setting
        # they chose (`ARC-008` reports; it does not edit).
        ffmpeg_problem = (
            f"The ffmpeg location in your settings cannot be run, so ffmpeg was looked for on "
            f"PATH instead.\n{settings.ffmpeg_location}"
        )
        logging.getLogger("tracksandtrails.app").warning("settings: %s", ffmpeg_problem)
        ffmpeg = find_ffmpeg(None)

    in_force = _InForce(ffmpeg)

    # **Where downloads land, decided here and nowhere else** (`REQ-023`, `T-146`). Three sources,
    # most specific first: the explicit argument (which is how every test redirects downloads away
    # from a real home directory, `ai/TESTING.md` §5), then the user's stored choice, then the
    # platform's own downloads folder. `load()` has already refused a stored folder that is gone,
    # is a file, or cannot be written to, and said why — so by here it is either usable or `None`.
    directory_is_default = output_directory is None and settings.download_directory is None
    downloads = output_directory
    if downloads is None:
        downloads = settings.download_directory
    if downloads is None:
        downloads = default_output_directory()
    downloads.mkdir(parents=True, exist_ok=True)
    manager = DownloadManager(
        store,
        # History is no longer a second injected sink (`T050-R1`, `T050-R2`): a completion is an
        # ordinary `JobStore.update` of one row, so there is no optional collaborator to forget to
        # wire and no partial state to report quietly. It went through a dedicated
        # `JobStore.complete` until `T-175`, which was the same write once `REQ-020` was withdrawn.
        concurrency=settings.concurrency,
        ffmpeg_override=ffmpeg.path,
        entry_point=entry_point if entry_point is not None else worker.spawn_session,
    )

    # **The cookies file reaches workers, never the model** (`REQ-026`, `T-197`, `DAT-003`). Set on
    # the manager exactly as the ffmpeg override is, because a session argument is one of the two
    # sinks the decision authorises. `load()` has already discarded a file that is gone or is not a
    # file, and said why.
    manager.set_cookie_file(settings.cookie_file)

    def retry(job_id: str) -> None:
        """Hand a retry to the manager, which owns job transitions (`T036-R1`).

        This used to write `FAILED → QUEUED` through the store and then call `manager.start()`
        itself. Both halves were wrong: the store has no signal, so nothing announced the
        transition and the progress view kept showing a failure over a re-queued row; and the
        start was attempted once, while the failed session was still being released, so the pool
        of one refused it and nothing tried again.

        `ui/` still holds no writer (`ARCHITECTURE.md` §3) — the view reports `retry_requested`
        and composition routes it, exactly as it would route a cancel.
        """
        manager.retry(job_id)

    def remember(chosen: AppSettings, what: str) -> None:
        """Write the settings file, and **say so when it does not get written** (`T146-R2`).

        `save()` has returned its failure rather than raising since `T109-R9`, and these three
        callers dropped it — so a full disk or a read-only profile directory left the user with a
        setting that had visibly taken effect and would be gone at the next launch. *"A chosen
        directory survives a restart"* is `T-146`'s criterion, and a silent write failure is
        precisely the case where it does not.

        **Transient, not modal.** The change *did* apply — the theme is on screen, the folder is
        what the next job uses — so this is not a refusal to be acknowledged; it is a warning that
        this session is as far as it goes. `report_transiently` exists for exactly this, and says
        so: *"composition performs the writes `ui/` is not allowed to, so it is also where their
        failures surface"*. A modal per failed keystroke on a read-only profile would be
        unusable, which is the shape `_report_transiently` was written against.

        Logged as well as shown, because the status line is gone in thirty seconds and the reason
        — the operating system's own words — is what a bug report needs.
        """
        failure = app_settings.save(chosen, settings_file)
        if failure is None:
            return
        logging.getLogger("tracksandtrails.app").warning(
            "could not save settings to %s: %s", settings_file, failure
        )
        window.report_transiently(
            f"{what.capitalize()} changed for this session only — your settings could not be "
            f"saved: {failure}"
        )

    def choose_concurrency(limit: int) -> None:
        """Apply the user's chosen limit and remember it (`REQ-013`, `ARC-007`).

        **Both halves, in this order, and neither is optional.** Applying without saving makes the
        control forget itself at the next launch; saving without applying makes it appear to do
        nothing until a restart, which is the shape `T-075` was — a control that changes what is
        stored and not what runs.

        Bounded on the way in by `with_concurrency`, so a caller that reached here with a value
        outside `REQ-013`'s range stores a usable one. The spinbox's own range already prevents it;
        this is the bound on the *value*, which is where `ARC-007` puts it.
        """
        chosen = app_settings.with_concurrency(held.settings, limit)
        manager.set_concurrency(chosen.concurrency)
        held.settings = chosen
        remember(chosen, "the number of downloads at once")
        # **Both controls follow the value, from here** (`T-146`). The toolbar spinner and the
        # settings screen's edit one setting, so the window is told what was applied rather than
        # each control telling the other — one writer, two views, and no round trip between them.
        window.show_concurrency(chosen.concurrency)

    def choose_download_directory(directory: Path | None) -> None:
        """Apply and remember where downloads go (`REQ-023`, `T-146`).

        **Both halves, in this order**, for `choose_concurrency`'s reason one function up: the
        window is handed the resolved folder so the *next* add dialog builds its requests against
        it, and the file is written so the choice survives a restart. Applying without saving is a
        setting that forgets itself; saving without applying is `T-075`'s shape — a control that
        changes what is stored and not what runs.

        `None` means *use the platform's downloads folder*, and composition is what resolves that:
        `ui/` is handed a path and never learns what `platformdirs` is (`ARC-007`).
        """
        resolved = directory if directory is not None else default_output_directory()
        resolved.mkdir(parents=True, exist_ok=True)
        chosen = app_settings.with_download_directory(held.settings, directory)
        held.settings = chosen
        window.show_download_directory(resolved, is_default=directory is None)
        remember(chosen, "the download folder")

    def resolve_ffmpeg(location: Path | None) -> tuple[Any, str | None]:
        """The one contract both routes obey: validate, resolve, and fall back saying why.

        **`T199-R3`.** Validation was split three ways and disagreed with itself — the stored
        value was checked at load, the live choice was checked nowhere, and `find_ffmpeg` refused
        a bad override without falling back, so the same unusable path produced a different
        outcome depending on how it arrived. This is the single answer: what
        `unusable_ffmpeg_reason` objects to, and what `find_ffmpeg` cannot run, both end the same
        way — **on `PATH`, with a reason** — which is `REQ-024`'s *report and still start on
        whatever it can find* and `ARC-008`'s report-rather-than-revert-silently in one place.
        """
        if location is None:
            return find_ffmpeg(None), None
        reason = app_settings.unusable_ffmpeg_reason(location)
        if reason is None:
            report = find_ffmpeg(location)
            if report.available:
                return report, None
            # It exists, is a file and is named for ffmpeg, and the platform still will not run
            # it — a mode bit on POSIX, a missing `PATHEXT` match on Windows. `find_ffmpeg` is the
            # authority on that and is deliberately not second-guessed here.
            reason = (
                f"The ffmpeg location cannot be run, so ffmpeg will be looked for on PATH "
                f"instead.\n{location}"
            )
        return find_ffmpeg(None), reason

    def choose_ffmpeg_location(location: Path | None) -> None:
        """Point at an ffmpeg, or go back to `PATH` (`REQ-023`, `REQ-024`, `T-199`).

        **A location is stored only if it resolves**, which is the contract `T199-R3` asked for:
        a choice that cannot be used is refused with a reason and changes nothing, rather than
        being persisted to fail again at the next launch. Clearing is always accepted — it is a
        request, not a value to validate.

        Both halves in this order, for `choose_download_directory`'s reason: what runs is updated
        before what is stored, and **the manager is told too** (`T199-R2`) — it hands the override
        to every child it starts, so a UI following the new answer while workers received the old
        one would offer exactly what the worker then refuses.
        """
        resolved, reason = resolve_ffmpeg(location)
        if reason is not None:
            # **Nothing is applied, and that now includes the manager** (`T199-R3`). This reported
            # and returned, but only *after* pushing the fallback resolution into the environment
            # and into `set_ffmpeg_override` — so refusing a bad choice while a good custom
            # override was in force switched future workers to `PATH` while the stored setting and
            # the screen still named the custom binary. A refusal that changes what runs is not a
            # refusal, and it recreated `T199-R2`'s UI/worker disagreement by the other door.
            logging.getLogger("tracksandtrails.app").warning("ffmpeg location: %s", reason)
            window.report_transiently(reason.splitlines()[0])
            window.show_ffmpeg_location(held.settings.ffmpeg_location, report=in_force.report)
            return
        window.report_environment(resolved.summary(), ffmpeg_available=resolved.available)
        manager.set_ffmpeg_override(resolved.path)
        in_force.report = resolved
        chosen = app_settings.with_ffmpeg_location(held.settings, location)
        held.settings = chosen
        window.show_ffmpeg_location(location, report=resolved)
        remember(chosen, "the ffmpeg location")

    def remember_cookie_path(path: Path | None) -> None:
        """Register a supplied cookie path so it never survives into a log (`T197-R1`).

        **Shape rules cannot cover this and must not try.** `redact`'s `_COOKIE_PATH` and
        `_COOKIE_FILENAME` recognise a path that *looks* like a cookie jar — `cookies.sqlite`,
        `.../cookies.txt`. A user may point at `~/session.txt`, and the review reproduced exactly
        that surviving the real formatter. Guessing harder is the enumeration failure `DAT-003`
        records twice; **knowing** is `remember_a_secret`, which exists for *"a literal this
        application is holding and knows is sensitive"* and had no caller until now.

        Registered rather than replaced-and-forgotten: `forget_the_secrets()` clears every
        registered literal, and a stale entry only over-redacts its own exact string, which is the
        harmless direction.
        """
        if path is not None:
            app_logging.remember_a_secret(str(path))

    def choose_cookie_file(path: Path | None) -> None:
        """Use a cookies file for sites the user is signed in to, or none (`REQ-026`, `T-197`).

        **Applied to the manager, not to any job.** The path may not reach `DownloadRequest`
        (`DAT-003`), so it travels as a session argument — which is what makes it **late-bound**:
        everything already queued and not yet started authenticates with this from now on. That
        consequence is ruled deliberate and the screen says so, because it is a surprise otherwise.

        Refused rather than stored when it cannot be used, on `choose_ffmpeg_location`'s contract:
        downloading unauthenticated where the user asked for authentication is the quiet failure
        `T-197` names, and `REQ-EXCL-002` is emphatic this feature exists for content they already
        have access to.
        """
        if path is not None:
            # Registered **before** the refusal is composed, for the same reason the stored one is:
            # the reason names the path, and the reason is logged (`T197-R1`).
            remember_cookie_path(path)
            reason = app_settings.unusable_cookie_file_reason(path)
            if reason is not None:
                logging.getLogger("tracksandtrails.app").warning("cookies file: %s", reason)
                window.report_transiently(reason.splitlines()[0])
                window.show_cookie_source(held.settings.cookie_file, held.settings.cookie_browser)
                return
        manager.set_cookie_file(path)
        remember_cookie_path(path)
        chosen = app_settings.with_cookie_file(held.settings, path)
        held.settings = chosen
        window.show_cookie_source(chosen.cookie_file, chosen.cookie_browser)
        remember(chosen, "the cookies file")

    def choose_cookie_browser(browser: str | None) -> None:
        """Read cookies from a browser instead of a file, or from neither (`REQ-026`, `T197-R4`).

        Exclusive with the file by construction — `set_cookie_source` refuses both — so choosing a
        browser clears any file and the manager is told about both halves.
        """
        if browser is not None:
            try:
                core_models.parse_browser_specification(browser)
            except ValueError as refusal:
                logging.getLogger("tracksandtrails.app").warning("cookie browser: %s", refusal)
                window.report_transiently(f"That browser cannot be used: {refusal}")
                window.show_cookie_source(held.settings.cookie_file, held.settings.cookie_browser)
                return
        chosen = app_settings.with_cookie_browser(held.settings, browser)
        held.settings = chosen
        # **Not handed to the manager** (`T197-R4`). `DAT-003` rules that a browser profile binds
        # when the job is *queued* — it is a `DownloadRequest` field a preset can carry — so the
        # default is read where a request is built, not where a worker starts. Only the *file* is
        # late-bound, because only the file may not live on the model.
        manager.set_cookie_file(None)
        window.show_cookie_source(chosen.cookie_file, chosen.cookie_browser)
        remember(chosen, "the cookie source")

    def choose_theme(name: str) -> None:
        """Wear a palette now, and at the next launch (`REQ-023`, `ARCHITECTURE.md` §8, `T-146`).

        Applied to the `QApplication`, which is what `ui/theme.py` themes — so every widget
        already built follows, and the criterion that the change needs no restart is this call
        rather than a promise about one.
        """
        chosen = app_settings.with_theme(held.settings, name)
        held.settings = chosen
        ui_theme.apply(app, ui_theme.THEMES[chosen.theme])
        remember(chosen, "the theme")

    def save_preset(preset: Preset) -> str | None:
        """Keep the options editor's answer under a name (`P-4`, `REQ-007`, `T109-R5`).

        **Composition owns `settings.toml`** (`ARC-007`), which is why this lives here rather than
        in the dialog: `ui/` holds no writer, exactly as it holds no queue writer (`T036-R1`).

        Returns the refusal rather than raising it. The only one that exists is a name already
        taken, which the user answers by typing a different one — `add_preset` states it and the
        editor shows it beside the button.
        """
        try:
            updated = app_settings.add_preset(held.settings, preset)
        except ValueError as refusal:
            return str(refusal)
        # **The write's own answer is the caller's** (`T109-R9`). `save()` never raises — a
        # read-only config directory is a real deployment state and not a reason to fall over — and
        # it used to swallow the failure entirely, so a preset that reached no disk was reported to
        # the user as `Saved as …`. The in-memory copy is not advanced either: a preset the file
        # does not have must not occupy its name for the rest of the session.
        failure = app_settings.save(updated, settings_file)
        if failure is not None:
            return f"This preset could not be saved: {failure}"
        held.settings = updated
        return None

    def save_settings(settings: AppSettings) -> str | None:
        """Where the preset manager writes (`T-111`, `ARC-007`).

        `save_preset`'s shape for the whole settings object rather than one preset: the manager's
        five operations each produce a complete `AppSettings`, because `core/settings` returns new
        frozen values rather than mutating one.

        **`held` is advanced only on a successful write**, which is `save_preset`'s rule and for its
        reason: settings the file does not have must not be what the rest of the session believes.
        """
        failure = app_settings.save(settings, settings_file)
        if failure is not None:
            return failure
        held.settings = settings
        return None

    def manage_presets() -> None:
        """Open `docs/UX_SPEC.md` §8's manager (`REQ-007`, `T-111`).

        Modal against the window that asked, so the catalogue cannot be edited in two places at
        once — the add dialog reads the presets afresh each time it is built, and two open managers
        would be two answers to what the list contains.
        """
        from tracks_and_trails.ui.preset_manager import PresetManager

        screen = PresetManager(
            held.settings,
            save=save_settings,
            # `ARC-002`: `ui/` may not ask yt-dlp anything, so `REQ-024`'s question travels through
            # the manager — one answer, derived from yt-dlp's own postprocessor hierarchy, rather
            # than a second one written against the preset's fields.
            requires_ffmpeg=manager.requires_ffmpeg,
            ffmpeg_available=ffmpeg.available,
            parent=window,
        )
        screen.exec()

    def choose_run(running: bool) -> None:
        """Start or stop the queue (`UX-001`, `UX-006`, `T-181`).

        **Not saved to `settings.toml`, unlike the concurrency limit.** A limit is a preference —
        the user chose 5 and means it next time. Whether the queue is running is a *state*, and
        `UX-006` fixes what it is at launch: stopped, every time. So there is nothing to persist
        and nothing to restore, which is the same conclusion this reached when the default was the
        other way round — for a different reason then. `ARC-007`'s file holds settings, and this is
        not one.
        """
        if running:
            manager.start_queue()
        else:
            manager.stop_queue()

    def remove_job(job_id: str) -> None:
        """Route a removal to the manager, which owns it (`T036-R1`, `UX-001`).

        Through the manager rather than the store, for the reason `T036-R1` recorded when a retry
        went the other way: removal of a running job is a cancel *plus* a delete, and only the
        manager knows there is a session to stop. A composition that deleted the row itself would
        leave the worker running and nothing to announce it.
        """
        manager.remove(job_id)

    def reorder_queue(job_ids: list[str]) -> None:
        """Route a reordering to the manager (`REQ-016`, `T-081`).

        Through the manager for `remove_job`'s reason: `_next_waiting` reads `queue_position` to
        decide what starts next, so the object whose scheduling changes is the one that should be
        told.
        """
        manager.reorder(job_ids)

    def clear_finished() -> None:
        """Route a clear-finished to the manager (`REQ-016`, `T-081`)."""
        manager.clear_completed()

    # **The thumbnail cache belongs to this database, not to this machine** (`T-180`, `ARC-006`).
    # One shared directory let two permitted instances — which `ARC-006` explicitly requires not to
    # block one another — sweep each other's pictures, because `_SweepTask` unlinks every entry the
    # sweeping instance's own queue does not name. Composition derives the partition because
    # composition is what knows which database this process opened; `ui/` is handed a root and never
    # learns what a database is.
    #
    # `cache_directory` overrides the platform root for the reason `settings_file` and
    # `geometry_file` do: without it a test of this seam writes into the developer's real cache,
    # which `ai/TESTING.md` §5 forbids — and `T180-R2` is exactly the finding that this seam had
    # no test at all, only one proving `cache_root_for` separates roots handed to it by hand.
    cache_root = paths.cache_root_for(database_path, cache_directory)
    if paths.adopt_legacy_cache(database_path, cache_directory):
        logging.getLogger("tracksandtrails.app").info(
            "adopted the shared thumbnail cache into this database's partition (T-180)"
        )

    window = MainWindow(
        geometry_file,
        manager=manager,
        jobs=store,
        output_directory=downloads,
        job_reader=store,
        retry=retry,
        # Both thumbnail stores in the window get this root, so the queue's sweep and the add
        # dialog's publications stay in one directory this instance owns alone (`T118-R16`).
        cache_root=cache_root,
        concurrency=settings.concurrency,
        on_concurrency_changed=choose_concurrency,
        # `T-146`'s screen: what it opens showing, and the two writers behind it. The theme is
        # applied by `run()` rather than here — `compose()` restyling the shared `QApplication`
        # is what the note above `theme.apply` in `run()` forbids.
        theme=settings.theme,
        directory_is_default=directory_is_default,
        on_directory_chosen=choose_download_directory,
        on_theme_chosen=choose_theme,
        cookie_file=settings.cookie_file,
        cookie_browser=settings.cookie_browser,
        # Read through a callable rather than passed by value, for `presets`' reason: a browser
        # chosen in Settings has to reach the *next* add dialog, which a snapshot cannot do.
        default_cookie_browser=lambda: held.settings.cookie_browser,
        on_cookie_file_chosen=choose_cookie_file,
        on_cookie_browser_chosen=choose_cookie_browser,
        ffmpeg_location=settings.ffmpeg_location,
        ffmpeg_summary=ffmpeg.summary(),
        on_ffmpeg_location_chosen=choose_ffmpeg_location,
        on_run_changed=choose_run,
        on_remove_requested=remove_job,
        on_reorder_requested=reorder_queue,
        on_clear_requested=clear_finished,
        # `P-4`: the options editor offers *Save as preset…*, and composition is what owns the
        # file it saves to (`ARC-007`).
        save_preset=save_preset,
        # `REQ-007`, `T-111`: the manager, and the catalogue it edits. `presets` is a callable for
        # the reason `queued_urls` is one — a preset created in the manager has to be in the list
        # the *next* add dialog offers, which a snapshot taken at startup could not do.
        manage_presets=manage_presets,
        presets=lambda: app_settings.all_presets(held.settings),
        default_preset=lambda: app_settings.default_preset_of(held.settings).name,
        # The same store, through a second protocol: `JobReader` is one job, `QueueReader` is all
        # of them (`T-079`). Two narrow protocols rather than one wide one, so a widget that needs
        # a single row cannot accidentally enumerate the queue.
        queue=store,
        # *(A third protocol was passed here until 2026-08-06: read-only over the table `T-085`
        # wrote, for the History view that enumerated records. `REQ-020` is withdrawn, the table is
        # dropped by migration `0009`, and the argument went with them — `T-176`.)*
    )
    # The control follows the queue, not only the other way round: anything that stops the pool
    # without going through the toolbar still leaves the toggle telling the truth (`T-080`).
    #
    # **The window opens stopped and so does the manager**, so no initial sync is needed here —
    # `_describe_run_action(running=False)` and `_running = False` agree by construction (`UX-006`).
    # A test asserts they still do, because two defaults that must match are two places to drift.
    manager.queue_running.connect(window.show_queue_running)
    window.report_environment(ffmpeg.summary(), ffmpeg_available=ffmpeg.available)
    # `ARC-008`: after the window exists, because that is the earliest a modal can be shown, and
    # before it is interactive, because the reverted setting is what the user would otherwise
    # notice first and have no explanation for.
    # **One report, however many parts** — the same shape `load()` uses to join its own reasons.
    # A settings file that is both unparseable and names an unrunnable ffmpeg is one problem the
    # user reads once, not two dialogs racing each other (`ARC-008`, `T199-R3`).
    settings_problem = settings_read.problem
    if ffmpeg_problem is not None:
        settings_problem = app_settings.SettingsProblem(
            settings_problem.path
            if settings_problem is not None
            else (settings_file if settings_file is not None else app_settings.settings_path()),
            f"{settings_problem.reason}\n\n{ffmpeg_problem}"
            if settings_problem is not None
            else ffmpeg_problem,
        )
    if settings_problem is not None:
        logging.getLogger("tracksandtrails.app").warning(
            "settings: %s (%s)", settings_problem.reason, settings_problem.path
        )
        window.report_settings_problem(settings_problem)
    # After the settings problem, so a user with both sees the one they cannot act on first and the
    # one they can act on second — an offer buried under a warning gets dismissed with it.
    if recovered:
        logging.getLogger("tracksandtrails.app").info(
            "recovered %d interrupted job(s) on startup", len(recovered)
        )
        window.offer_to_retry_interrupted(recovered)

    # **The queue a previous run left behind starts running** (`T-115`). Without this, `admit` on
    # the add dialog would cover only jobs added in this session, and a user who closed the
    # application with work still queued would find it inert on the next launch.
    #
    # **Nothing recovered is admitted.** `durable_queued` was read after `recover_interrupted`, so
    # it holds no row that was in flight — starting those unattended is exactly the defect
    # `T081-R4` filed, and `T-082`'s offer is how a user asks for them instead.
    from tracks_and_trails.core.job_state import JobStatus
    from tracks_and_trails.downloader.protocol import SessionKind

    # **Admitted by status, exactly as the add dialog does** (`ARC-009`, `T137-R2`). Unprobed
    # things get probed; the continuation then carries each one into its download. Writing the
    # rule twice is the risk here, and it is why `waiting_jobs` hands the status over rather than
    # letting this loop guess from the id.
    #
    # **Held until the user starts the queue, not admitted now** (`T-215`). This loop called
    # `admit` here, and a `QUEUED` row is admitted as a *probe* — which the stopped-queue gate
    # exempts, deliberately, so the add dialog can read what the user pastes into a window whose
    # queue is stopped, as `UX-006` says every window's is. So every row a previous run left
    # behind was read the instant this window opened, with nobody watching: a launch with no
    # usable network failed all of them, `REQ-018` retried the network errors and failed them
    # again, and a queue the user had committed became a wall of `Failed` rows to retry by hand.
    # `admit_when_started` carries the reasoning and why the gate is the wrong place for it.
    for job_id, status in durable_waiting:
        kind = SessionKind.PROBE if status is JobStatus.QUEUED else SessionKind.DOWNLOAD
        manager.admit_when_started(job_id, kind)
    if durable_queued:
        logging.getLogger("tracksandtrails.app").info(
            "holding %d job(s) left queued by a previous run until the queue is started",
            len(durable_queued),
        )
    logging.getLogger("tracksandtrails.app").info("environment: %s", ffmpeg.summary())

    # **Nothing re-reads the ledger when a download completes** (`T-170`). There was a refresh
    # here, for a view that listed records; the ledger has no view, and the only number taken from
    # it is the Settings count, which is read when that screen is opened. `T-170`'s criterion that
    # an invisible ledger performs no view refresh is this absence.

    # **Nothing follows `job_changed` into a detail pane any more** (`UX-005`). There was a rule
    # here — claim the pane for the first watchable transition and then leave it to the user, so
    # three running downloads did not evict each other several times a second (`T-079`). The pane
    # is gone, the row carries progress and state itself, and a rule about which job owns a
    # surface that does not exist is worse than no rule. What becomes of `JobProgressView` is
    # deferred by `UX-005`, so this is a disconnection rather than a deletion.

    shutdown = OrderlyShutdown(app, manager, writer, connection, instance)
    window.closing.connect(shutdown.begin)
    # **Every quit, not only the one through the window.** Qt aborts the process if a `QThread`
    # is destroyed while running, so a quit that skipped the lifecycle — `QApplication.quit()`
    # from anywhere, a platform session-end — would exit `-6` rather than `0`. See
    # `OrderlyShutdown.stop_for_exit`.
    app.aboutToQuit.connect(shutdown.stop_for_exit)
    # Qt quits when the last window closes, which is step zero of the wrong order. The shutdown
    # lifecycle quits instead, once the worker is gone and the database is closed.
    app.setQuitOnLastWindowClosed(False)

    return Composition(
        app=app,
        window=window,
        manager=manager,
        store=store,
        writer=writer,
        connection=connection,
        ffmpeg=ffmpeg,
        output_directory=downloads,
        database_path=database_path,
        settings_path=settings_file if settings_file is not None else app_settings.settings_path(),
        theme=settings.theme,
        cache_root=cache_root,
        shutdown=shutdown,
        instance=instance,
    )


class OrderlyShutdown:
    """Closing the window is a request; quitting is what happens when everything has stopped.

    Three steps, in order, each waiting on the previous one's completion **signal** rather than
    on a join (`T013-R2`): the manager stops the worker and its tree, the writer finishes the
    transitions the manager queued on its way down, and only then is the read connection closed
    and the process allowed to exit.

    The order is not cosmetic. Closing the database while the writer thread still holds queued
    revisions loses them; quitting while a worker is alive leaves an orphaned `ffmpeg` on the
    user's disk (`T-019`); and `DownloadManager.idle` deliberately also waits for the worker-log
    listener, because a daemon thread's held records go with the process (`T038-R2`).

    Not a `QObject`: it owns no Qt state and connects to signals as a plain callable, which keeps
    it constructible in a test without an application object.
    """

    def __init__(
        self,
        app: Any,
        manager: DownloadManager,
        writer: QueueWriter,
        connection: sqlite3.Connection,
        instance: InstanceLock | None = None,
    ) -> None:
        self._app = app
        self._manager = manager
        self._writer = writer
        self._connection = connection
        #: Optional, because `T-013`'s tests construct this without one and the ownership guard is
        #: composition's concern rather than the shutdown sequence's. When present it is released
        #: last — see `_writes_are_finished`.
        self._instance = instance
        self._begun = False
        self._finished = False
        manager.idle.connect(self._workers_are_gone)
        writer.closed.connect(self._writes_are_finished)

    @property
    def begun(self) -> bool:
        return self._begun

    @property
    def finished(self) -> bool:
        """Every step has completed and the process may exit."""
        return self._finished

    def begin(self) -> None:
        """Ask the manager to stop. **Returns immediately**; the rest happens on signals."""
        if self._begun:
            return
        self._begun = True
        self._manager.shutdown()

    def _workers_are_gone(self) -> None:
        # `idle` is emitted whenever the last session is released, not only during shutdown, so
        # this has to know whether it was asked for. Closing the writer on an ordinary idle would
        # end persistence while the application was still running.
        if not self._begun or self._finished:
            return
        self._writer.close()

    def stop_for_exit(self) -> None:
        """Last resort for a quit that did not go through the lifecycle. **Bounded, and blocks.**

        Reached from `aboutToQuit`, which Qt emits for every quit — including ones that never
        touched the window. The ordinary path has already finished by then and this does nothing.

        When it has not, the choice is between a bounded wait and `SIGABRT`: Qt aborts the
        process when a running `QThread` is destroyed, which is `exit -6` and a warning on
        stderr instead of a clean exit. `T013-R2`'s rule is that a *lifecycle* is not implemented
        as a wait, and it is not — `begin()` still returns immediately. This is the process
        leaving, where there is no interaction left to block.

        **It cannot reap a worker.** Killing a process tree needs timer ticks and there is no
        event loop left here, so a quit that bypasses the window can still strand a worker. The
        window's own close is the path that does not, which is why it is the one composition
        wires up.
        """
        if self._finished:
            return
        self._manager.shutdown()
        self._writer.close()
        self._writer.wait_for_close()
        self._writes_are_finished()

    def _writes_are_finished(self) -> None:
        if self._finished:
            return
        self._finished = True
        # Last, and only here: every queued revision has been written by now, so nothing is
        # reading or writing this file any more.
        self._connection.close()
        # **After the connection, never before** (`T-087`). The lock says "this process owns this
        # database"; releasing it while a write could still land would let the next launch open a
        # database this one has not finished with. The kernel would release it at exit anyway —
        # doing it here is what makes the ordering true for a process that keeps running, which is
        # every test in `test_composition.py`.
        if self._instance is not None:
            self._instance.release()
        if self._app is not None:
            self._app.quit()
